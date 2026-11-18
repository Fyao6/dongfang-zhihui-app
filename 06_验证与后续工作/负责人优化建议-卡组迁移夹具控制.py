"""Fixed observations/timing/storage faults for this fresh synthetic namespace only."""
import ast
import ctypes
import hashlib
import inspect
import json
import os
import re
from pathlib import Path
import signal
import sqlite3
import sys
import textwrap
import threading
import time

LOCK=threading.RLock()
TLS=threading.local()
STATE={'namespace':None,'native_node':None,'node_mode':'normal','launches':[],'calls':[],'spawnFailures':[],'clock':None,'started':time.monotonic(),'hashes':{},'image_mime':{}}
GATES={kind:{'armed':False,'entered':False,'release':threading.Event()} for kind in ('ci','cm')}
TABLES=tuple(('card_import_diagnostics card_import_jobs card_deck_sources card_import_receipts card_deck_activation_events card_import_guards card_import_erase_guards card_history_migration_jobs card_history_migration_targets card_history_migration_receipts card_history_migration_operations card_history_migration_guards card_legacy_archives card_deck_versions card_draws card_draw_requests card_daily_quota card_zone_preferences card_record_epochs card_draw_actions card_practice_events ai_gateway_wallets ai_gateway_jobs ai_gateway_quota_events ai_gateway_attempts membership_ai_periods membership_ai_allocations membership_ai_events commerce_orders commerce_order_items commerce_payment_events commerce_entitlements contents media').split())

def before(kind):
    gate=GATES[kind]
    with LOCK:
        pause=gate['armed'] and not gate['entered']
        if pause:gate['entered']=True
    if pause and not gate['release'].wait(45):raise RuntimeError('Owned card timing barrier expired')

def file_hash(file):
    p=Path(file);s=p.stat();fingerprint=(str(p.resolve()),s.st_size,s.st_mtime_ns)
    with LOCK:
        if fingerprint not in STATE['hashes']:STATE['hashes'][fingerprint]=hashlib.sha256(p.read_bytes()).hexdigest()
        return STATE['hashes'][fingerprint]

def suspend(process,resume=False):
    if os.name=='nt':
        fn=ctypes.windll.ntdll.NtResumeProcess if resume else ctypes.windll.ntdll.NtSuspendProcess
        if fn(ctypes.c_void_p(int(process._handle))):raise RuntimeError('Owned child timing operation failed')
    else:os.kill(process.pid,signal.SIGCONT if resume else signal.SIGSTOP)

class IO:
    def __init__(self,native,row,key):self.native,self.row,self.key=native,row,key
    def __getattr__(self,key):return getattr(self.native,key)
    def read(self,*args):
        value=self.native.read(*args)
        with LOCK:self.row[self.key]+=len(value or b'')
        return value
    def write(self,value):
        result=self.native.write(value)
        with LOCK:self.row[self.key]+=result if isinstance(result,int) else len(value)
        return result

def install_hooks(actual):
    namespace=actual.CardImports.preview.__globals__
    STATE.update(namespace=namespace,native_node=namespace['NODE'],missing_node=Path(__file__).with_name('nonexistent-owned-card-node.exe'))
    native_worker=namespace['worker_call'];native_process=namespace['subprocess']
    def popen(*args,**kwargs):
        command=args[0] if args else kwargs.get('args')
        expected=[str(Path(namespace['NODE']).resolve()),str(namespace['WORKER'])]
        assert expected[0] in (str(Path(STATE['native_node']).resolve()),str(STATE['missing_node'].resolve())) and list(command)==expected
        started=time.monotonic()
        try:process=native_process.Popen(*args,**kwargs)
        except OSError as error:
            with LOCK:STATE['spawnFailures'].append({'operation':getattr(TLS,'operation',''),'actualOsError':type(error).__name__,'fixedMissingExecutable':expected[0]==str(STATE['missing_node'].resolve()),'pid':None})
            raise
        row={'pid':process.pid,'operation':getattr(TLS,'operation',''),'nodeSha256':file_hash(expected[0]),'workerSha256':file_hash(expected[1]),'shell':kwargs.get('shell'),'creationflags':kwargs.get('creationflags',0),'environmentKeys':sorted(kwargs.get('env',{})),'stdinBytes':0,'stdoutBytes':0,'stderrBytes':0,'exitCode':None,'suspended':False,'started':int(time.time()*1000),'stdinLimitBytes':6*1024*1024,'stdoutLimitBytes':8*1024*1024,'stderrLimitBytes':65536,'timeoutMs':15000}
        if getattr(TLS,'expected_failure',None):row['expectedFailure']=dict(TLS.expected_failure)
        process.stdin=IO(process.stdin,row,'stdinBytes');process.stdout=IO(process.stdout,row,'stdoutBytes');process.stderr=IO(process.stderr,row,'stderrBytes')
        native_wait=process.wait
        def wait(*values,**options):
            result=native_wait(*values,**options)
            with LOCK:row.update(exitCode=result,finished=int(time.time()*1000),elapsedMs=int((time.monotonic()-started)*1000),suspended=False)
            return result
        process.wait=wait
        with LOCK:
            row['_process']=process;STATE['launches'].append(row)
            pause=STATE['node_mode']=='suspend-next'
            if pause:STATE['node_mode']='normal'
        if pause:
            suspend(process)
            with LOCK:row['suspended']=True
        return process
    class ProcessProxy:
        def __getattr__(self,key):return popen if key=='Popen' else getattr(native_process,key)
    namespace['subprocess']=ProcessProxy()
    def worker(request):
        TLS.operation=request.get('op');started=time.monotonic()
        with LOCK:TLS.expected_failure=STATE.get('expected_failure')
        try:
            result=native_worker(request)
            with LOCK:STATE['calls'].append({'operation':TLS.operation,'elapsedMs':int((time.monotonic()-started)*1000),'ok':True})
            return result
        except Exception as error:
            with LOCK:STATE['calls'].append({'operation':TLS.operation,'elapsedMs':int((time.monotonic()-started)*1000),'ok':False,'code':getattr(error,'code',type(error).__name__)})
            raise
        finally:TLS.operation=None;TLS.expected_failure=None
    namespace['worker_call']=worker
    actual.CardHistoryMigration.process.__globals__['worker_call']=worker
    # Pause immediately before native BEGIN, never while its write lock is held.
    targets={}
    for cls,method,kind in ((actual.CardImports,'apply','ci'),(actual.CardHistoryMigration,'process','cm')):
        native=getattr(cls,method);source,start=inspect.getsourcelines(native);text=textwrap.dedent(''.join(source));tree=ast.parse(text);lines=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='execute' and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value=='BEGIN IMMEDIATE':lines.add(start+node.lineno-1)
        assert lines,'Native final transaction line must be found'
        targets[native.__code__]=(kind,lines)
        def wrapped(self,*args,__native=native,**kwargs):
            old=sys.gettrace()
            def trace(frame,event,arg):
                if event=='line' and frame.f_code in targets:
                    observed,positions=targets[frame.f_code]
                    if frame.f_lineno in positions:before(observed)
                return trace
            sys.settrace(trace)
            try:return __native(self,*args,**kwargs)
            finally:sys.settrace(old)
        setattr(cls,method,wrapped)
    native_init=actual.CardService.__init__
    def init(self,*args,**kwargs):
        def clock():
            with LOCK:base,started=STATE['clock'],STATE['started']
            return time.time_ns()//1000000 if base is None else base+int((time.monotonic()-started)*1000)
        kwargs['test_clock']=clock
        return native_init(self,*args,**kwargs)
    actual.CardService.__init__=init

def handle(path,data):
    action=str(data.get('action',''))
    if not action.startswith(('ci-','cm-','card-')):return None
    p=Path(path).resolve();assert p.parent==Path(__file__).resolve().parent and p.name.startswith('负责人优化建议-卡组迁移隔离-') and p.is_file()
    for kind in ('ci','cm'):
        if action.startswith(kind+'-barrier-'):
            gate=GATES[kind];operation=action.rsplit('-',1)[1]
            if operation=='arm':
                assert data.get('stage','before-final')=='before-final'
                with LOCK:gate.update(armed=True,entered=False);gate['release'].clear()
                return {'armed':True,'stage':'before-final','nativeTransactionUnchanged':True}
            if operation=='release':
                gate['release'].set()
                with LOCK:gate['armed']=False
                return {'released':True}
            if operation=='state':
                with LOCK:return {k:v for k,v in gate.items() if k!='release'}
    if action=='ci-worker-state':
        with LOCK:return {'backend':'python','actualManagedChildren':True,'nativeImportedComputation':False,'launches':[{k:v for k,v in row.items() if not k.startswith('_')} for row in STATE['launches']],'calls':list(STATE['calls']),'spawnFailures':list(STATE['spawnFailures'])}
    if action=='ci-worker-mode':
        assert data.get('mode') in ('normal','missing','suspend-next')
        failure=data.get('expectedFailure')
        if failure is not None:assert set(failure)<=set(('caseName','kind','expectedStatus')) and isinstance(failure.get('caseName'),str)
        with LOCK:STATE.update(node_mode=data['mode'],expected_failure=failure);STATE['namespace']['NODE']=str(STATE['missing_node']) if data['mode']=='missing' else STATE['native_node']
        return {'mode':data['mode'],'onlyFixedOwnedExecutable':True}
    if action in ('ci-worker-release','ci-worker-kill'):
        with LOCK:active=[row for row in STATE['launches'] if row['_process'].poll() is None]
        if action=='ci-worker-kill':
            rows=[row for row in active if row['pid']==data.get('pid')];assert len(rows)==1;rows[0]['_process'].kill();return {'killedOwnedPid':rows[0]['pid']}
        for row in active:
            if row['suspended']:suspend(row['_process'],True);row['suspended']=False
        with LOCK:STATE.update(node_mode='normal',expected_failure=None);STATE['namespace']['NODE']=STATE['native_node']
        return {'releasedOwnedChildren':len(active)}
    if action=='card-clock':
        value=data.get('nowMs');assert value is None or type(value) is int and 0<value<4000000000000
        with LOCK:STATE.update(clock=value,started=time.monotonic())
        return {'nowMs':value,'clockFixture':'sandbox_synthetic_business_days','authenticationAndDatabaseClockUnchanged':True}
    if action=='card-snapshot':
        tables=data.get('tables',TABLES);assert isinstance(tables,(list,tuple)) and all(t in TABLES for t in tables)
        with sqlite3.connect(p) as db:
            db.row_factory=sqlite3.Row
            return {'tables':{table:[dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in tables},'readOnly':True}
    if action=='card-owned-image-mime':
        assert data.get('mode') in ('unavailable','restore');identifier=data.get('versionId')
        with sqlite3.connect(p) as db:
            db.row_factory=sqlite3.Row
            if data['mode']=='restore':
                with LOCK:original=STATE['image_mime'].pop(identifier,None)
                assert original
                for media_id,mime in original.items():db.execute('UPDATE media SET mime=? WHERE id=?',(mime,media_id))
                return {'fixtureMutation':True,'metadataRestored':True,'affectedMedia':len(original),'objectBytesChanged':False}
            row=db.execute('SELECT * FROM card_deck_versions WHERE id=?',(identifier,)).fetchone();assert row and row['environment']=='sandbox' and row['status']=='published';deck=json.loads(row['data']);owner=deck.get('review',{}).get('reviewerId');assert owner and deck['cards'] and all(c.get('sandboxOnly') is True for c in deck['cards']);ids=set()
            for c in deck['cards']:
                for field in ('frontUrl','backUrl'):
                    matched=re.fullmatch(r'/api/media/([a-f0-9-]{36})',c[field]);assert matched;ids.add(matched[1])
            original={}
            for media_id in ids:
                media=db.execute('SELECT * FROM media WHERE id=? AND owner=?',(media_id,owner)).fetchone();assert media and media['mime'].startswith('image/');original[media_id]=media['mime']
            with LOCK:assert identifier not in STATE['image_mime'];STATE['image_mime'][identifier]=original
            for media_id in original:db.execute("UPDATE media SET mime='audio/wav' WHERE id=?",(media_id,))
        return {'fixtureMutation':True,'metadataUnavailable':True,'affectedMedia':len(original),'objectBytesChanged':False,'onlySyntheticSandbox':True}
    if action in ('ci-fault','cm-fault'):
        table=({'draft':'card_deck_versions','source':'card_deck_sources','receipt':'card_import_receipts'} if action=='ci-fault' else {'archive':'card_legacy_archives','receipt':'card_history_migration_receipts','target':'card_history_migration_targets'}).get(data.get('kind'));assert table and type(data.get('enabled')) is bool
        name=action[:2]+'_owned_qa_'+data['kind']+'_fault'
        with sqlite3.connect(p) as db:
            db.execute('DROP TRIGGER IF EXISTS '+name)
            if data['enabled']:db.execute('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT card_owned_storage_failure(); END')
        return {'actualDatabaseTrigger':True,'enabled':data['enabled']}
    if action=='card-referenced-delete-attempt':
        with sqlite3.connect(p) as db:
            db.row_factory=sqlite3.Row;row=db.execute('SELECT * FROM card_deck_versions WHERE id=?',(data.get('versionId'),)).fetchone();assert row and row['status']=='draft'
            assert db.execute('SELECT 1 FROM card_deck_sources WHERE deck_version_id=? UNION ALL SELECT 1 FROM card_import_jobs WHERE base_version_id=? OR result_version_id=?',(row['id'],row['id'],row['id'])).fetchone()
            db.execute('SAVEPOINT ci_reference_probe');blocked=False
            try:db.execute('DELETE FROM card_deck_versions WHERE id=?',(row['id'],))
            except sqlite3.IntegrityError as error:blocked='card_deck_protected' in str(error)
            finally:db.execute('ROLLBACK TO ci_reference_probe');db.execute('RELEASE ci_reference_probe')
            return {'operation':'delete','blocked':blocked,'unchanged':dict(db.execute('SELECT * FROM card_deck_versions WHERE id=?',(row['id'],)).fetchone())==dict(row),'actualDatabaseTriggers':True,'actualReferenceRequired':True}
    if action=='card-immutable-attempts':
        checks=[]
        with sqlite3.connect(p) as db:
            db.row_factory=sqlite3.Row;row=db.execute('SELECT * FROM card_deck_versions WHERE id=?',(data.get('versionId'),)).fetchone();assert row and row['status'] in ('published','withdrawn');original=dict(row)
            for op in ('update','delete','replace'):
                db.execute('SAVEPOINT ci_immutable_probe');blocked=False
                try:
                    if op=='update':db.execute("UPDATE card_deck_versions SET data=data||' ' WHERE id=?",(row['id'],))
                    elif op=='delete':db.execute('DELETE FROM card_deck_versions WHERE id=?',(row['id'],))
                    else:db.execute('INSERT OR REPLACE INTO card_deck_versions VALUES('+','.join('?' for _ in row)+')',tuple(row))
                except sqlite3.IntegrityError:blocked=True
                finally:db.execute('ROLLBACK TO ci_immutable_probe');db.execute('RELEASE ci_immutable_probe')
                checks.append({'operation':op,'blocked':blocked,'unchanged':dict(db.execute('SELECT * FROM card_deck_versions WHERE id=?',(row['id'],)).fetchone())==original})
        return {'checks':checks,'actualDatabaseTriggers':True}
    raise ValueError('Unsupported fixed card control')
