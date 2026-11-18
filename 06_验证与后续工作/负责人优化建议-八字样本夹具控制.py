"""Fixed timing/storage controls for the new owned synthetic namespace only."""
import ast
import ctypes
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import sqlite3
import threading
import textwrap
import time
from uuid import uuid4

LOCK=threading.RLock()
RELEASE=threading.Event()
GATE={'position':'','entered':False}
STATE={'module':None,'namespace':None,'native_node':None,'node_mode':'normal','launches':[],'calls':[]}
TLS=threading.local()
TABLES=tuple('bazi_sample_'+name for name in ('owner_state','sets','versions','cases','runs','workitems','results','raw_chunks','field_results','reviews','operations','erase_guards'))

def configure_app(database,original):
    STATE.update(original_app=Path(original).resolve(),owned_app=Path(database).with_suffix('.runtime-app.html'),missing_node=Path(database).with_name('nonexistent-owned-node.exe'),app_drift=False)

def served_override():
    with LOCK:return STATE['owned_app'].read_bytes() if STATE.get('app_drift') else None

def before(position):
    with LOCK:
        wait=GATE['position']==position and not GATE['entered']
        if wait:GATE['entered']=True
    if wait and not RELEASE.wait(45):raise RuntimeError('Owned sample timing barrier expired')

def suspend(process,resume=False):
    if os.name=='nt':
        fn=ctypes.windll.ntdll.NtResumeProcess if resume else ctypes.windll.ntdll.NtSuspendProcess
        result=fn(ctypes.c_void_p(int(process._handle)))
        if result:raise RuntimeError('Owned child timing operation failed')
    else:os.kill(process.pid,signal.SIGCONT if resume else signal.SIGSTOP)

class IO:
    def __init__(self,native,record,key):self.native,self.record,self.key=native,record,key
    def __getattr__(self,key):return getattr(self.native,key)
    def read(self,*args):
        value=self.native.read(*args)
        with LOCK:self.record[self.key]+=len(value or b'')
        return value
    def write(self,value):
        size=self.native.write(value)
        with LOCK:self.record[self.key]+=size if isinstance(size,int) else len(value)
        return size

def install_hooks(actual):
    cls=actual.BaziSamples
    namespace=cls.process.__globals__
    STATE.update(namespace=namespace,native_node=namespace['NODE'])
    native_worker=namespace['worker_call'];native_subprocess=namespace['subprocess']
    def popen(*args,**kwargs):
        command=args[0] if args else kwargs.get('args')
        expected=[str(Path(namespace['NODE']).resolve()),str(namespace['WORKER'])]
        assert expected[0] in (str(Path(STATE['native_node']).resolve()),str(STATE['missing_node'].resolve())) and list(command)==expected,'Only the actual managed worker or the one fixed missing executable is observed'
        process=native_subprocess.Popen(*args,**kwargs)
        record={'pid':process.pid,'operation':getattr(TLS,'operation',''),'node':expected[0],
                'nodeSha256':hashlib.sha256(Path(expected[0]).read_bytes()).hexdigest(),
                'workerSha256':hashlib.sha256(Path(expected[1]).read_bytes()).hexdigest(),
                'shell':kwargs.get('shell'),'creationFlags':kwargs.get('creationflags',0),
                'environmentKeys':sorted(kwargs.get('env',{})),'started':int(time.time()*1000),
                'stdinBytes':0,'stdoutBytes':0,'stderrBytes':0,'exitCode':None,'suspended':False}
        process.stdin=IO(process.stdin,record,'stdinBytes');process.stdout=IO(process.stdout,record,'stdoutBytes');process.stderr=IO(process.stderr,record,'stderrBytes')
        native_wait=process.wait
        def wait(*values,**options):
            result=native_wait(*values,**options)
            with LOCK:record.update(exitCode=result,finished=int(time.time()*1000),suspended=False)
            return result
        process.wait=wait
        with LOCK:
            record['_process']=process;STATE['launches'].append(record)
            pause=STATE['node_mode']=='suspend-next' and record['operation']=='compute'
            if pause:STATE['node_mode']='normal'
        if pause:
            suspend(process)
            with LOCK:record['suspended']=True
        return process
    class ProcessProxy:
        def __getattr__(self,name):return popen if name=='Popen' else getattr(native_subprocess,name)
    namespace['subprocess']=ProcessProxy()
    def worker(request):
        TLS.operation=request.get('op');started=time.monotonic()
        try:
            if TLS.operation=='compute':before('before-compute')
            value=native_worker(request)
            if TLS.operation=='compute':before('after-compute')
            with LOCK:STATE['calls'].append({'operation':TLS.operation,'elapsedMs':int((time.monotonic()-started)*1000),'ok':True})
            return value
        except Exception as error:
            with LOCK:STATE['calls'].append({'operation':TLS.operation,'elapsedMs':int((time.monotonic()-started)*1000),'ok':False,'code':getattr(error,'code',type(error).__name__)})
            raise
        finally:TLS.operation=None
    namespace['worker_call']=worker
    native_manifest=cls.manifest
    def manifest(self,*args,**kwargs):
        self.app_file=STATE['owned_app'] if STATE.get('app_drift') else STATE['original_app']
        return native_manifest(self,*args,**kwargs)
    cls.manifest=manifest
    source,start=inspect.getsourcelines(cls.process);source_text=textwrap.dedent(''.join(source));tree=ast.parse(source_text)
    transaction_lines=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.With) and node.body:
            first=ast.get_source_segment(source_text,node.body[0]) or ''
            if 'BEGIN IMMEDIATE' in first:transaction_lines.append(start+node.lineno-1)
    transaction_lines.sort();assert len(transaction_lines)==2,'Observe native claim/final transaction entry only'
    native_connect=actual.Store.connect
    def connect(self,*args,**kwargs):
        caller=inspect.currentframe().f_back
        if caller.f_code is cls.process.__code__:
            if caller.f_lineno==transaction_lines[0]:before('before-claim')
            elif caller.f_lineno==transaction_lines[1]:before('before-final')
        return native_connect(self,*args,**kwargs)
    actual.Store.connect=connect

def handle(path,data):
    if not str(data.get('action','')).startswith('sample-'):return None
    p=Path(path).resolve();assert p.parent==Path(__file__).resolve().parent and p.name.startswith('负责人优化建议-八字样本隔离-') and p.is_file()
    action=data['action']
    if action=='sample-barrier-arm':
        assert data.get('position') in ('before-claim','before-compute','after-compute','before-final')
        with LOCK:GATE.update(position=data['position'],entered=False);RELEASE.clear()
        return {'armed':True,'position':data['position'],'nativeComputationUnchanged':True}
    if action=='sample-barrier-release':
        RELEASE.set()
        with LOCK:GATE['position']=''
        return {'released':True}
    if action=='sample-barrier-state':
        with LOCK:return dict(GATE)
    if action=='sample-worker-state':
        with LOCK:return {'launches':[{k:v for k,v in item.items() if not k.startswith('_')} for item in STATE['launches']],'calls':list(STATE['calls']),'actualManagedChildren':True}
    if action=='sample-app-drift':
        assert type(data.get('enabled')) is bool
        original=STATE['original_app'].read_bytes();changed=original+b'\n<!-- owned synthetic served-APP drift; no shared source mutation -->\n'
        if data['enabled']:STATE['owned_app'].write_bytes(changed)
        with LOCK:STATE['app_drift']=data['enabled']
        return {'actualServedArtifactChanged':data['enabled'],'oldSha256':hashlib.sha256(original).hexdigest(),'newSha256':hashlib.sha256(changed if data['enabled'] else original).hexdigest(),'ownedRuntimeFile':str(STATE['owned_app']),'sharedSourceChanged':False}
    if action=='sample-node-mode':
        assert data.get('mode') in ('normal','missing','suspend-next')
        with LOCK:
            STATE['node_mode']=data['mode'];STATE['namespace']['NODE']=str(STATE['missing_node']) if data['mode']=='missing' else STATE['native_node']
        return {'mode':data['mode'],'fixtureOnly':True}
    if action in ('sample-node-release','sample-node-kill'):
        with LOCK:active=[row for row in STATE['launches'] if row['_process'].poll() is None and row['operation']=='compute']
        if action=='sample-node-kill':
            selected=[row for row in active if row['pid']==data.get('pid')];assert len(selected)==1
            selected[0]['_process'].kill();return {'killedOwnedPid':selected[0]['pid']}
        for row in active:
            if row['suspended']:suspend(row['_process'],True);row['suspended']=False
        STATE['node_mode']='normal';STATE['namespace']['NODE']=STATE['native_node']
        return {'releasedOwnedChildren':len(active)}
    if action=='sample-snapshot':
        tables=data.get('tables',TABLES);assert isinstance(tables,(list,tuple)) and all(t in TABLES for t in tables)
        with sqlite3.connect(p) as db:
            db.row_factory=sqlite3.Row
            return {'tables':{t:[dict(row) for row in db.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in tables},'readOnly':True}
    if action=='sample-historical-run':
        receipt=json.loads(Path(__file__).with_name('负责人优化建议-支付路由-实施记录.json').read_text(encoding='utf-8'))
        previous=receipt['reportIdentityHashes']['03_当前APP/东方智慧-首页体验R4.html']
        with sqlite3.connect(p) as db:
            db.row_factory=sqlite3.Row
            original=db.execute('SELECT * FROM bazi_sample_runs WHERE id=?',(data.get('baseRunId'),)).fetchone();assert original and original['state']=='pending' and original['processed']==0
            row=dict(original);old=dict(row);manifest=json.loads(row['manifest_data']);current=manifest['servedAppSha256'];assert previous!=current
            manifest['servedAppSha256']=previous;encoded=json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':'))
            row.update(id=str(uuid4()),request_id='historical_'+str(uuid4()),manifest_data=encoded,manifest_hash=hashlib.sha256(encoded.encode()).hexdigest())
            names=list(row);db.execute('INSERT INTO bazi_sample_runs('+','.join(names)+') VALUES('+','.join('?' for _ in names)+')',tuple(row[k] for k in names))
            for item in db.execute('SELECT * FROM bazi_sample_workitems WHERE run_id=? ORDER BY ordinal',(old['id'],)).fetchall():
                item=dict(item);assert item['state']=='pending';item.update(id=str(uuid4()),run_id=row['id']);keys=list(item);db.execute('INSERT INTO bazi_sample_workitems('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',tuple(item[k] for k in keys))
            assert dict(db.execute('SELECT * FROM bazi_sample_runs WHERE id=?',(old['id'],)).fetchone())==old
            run=STATE['namespace']['run_item'](row)
        return {'run':run,'requestId':row['request_id'],'caseIds':json.loads(row['case_ids']),'setVersionId':row['version_id'],'fixtureMutation':True,'fixtureKind':'synthetic-historical-unfinished','previousAppSha256':previous,'currentAppSha256':current,'originalRowsUnchanged':True,'actualDeploymentSwitchCovered':False}
    if action=='sample-immutable-attempts':
        checks=[]
        with sqlite3.connect(p) as db:
            db.row_factory=sqlite3.Row
            result=db.execute('SELECT * FROM bazi_sample_results WHERE id=?',(data.get('resultId'),)).fetchone();assert result
            for table in ('bazi_sample_results','bazi_sample_raw_chunks','bazi_sample_field_results'):
                item=db.execute('SELECT * FROM '+table+' WHERE '+('id' if table=='bazi_sample_results' else 'result_id')+'=? LIMIT 1',(result['id'],)).fetchone()
                if not item:continue
                for operation in ('update','delete'):
                    before_row=dict(item);db.execute('SAVEPOINT sample_immutable_probe');blocked=False
                    try:db.execute(('UPDATE '+table+" SET data=data||' ' WHERE id=?") if operation=='update' else 'DELETE FROM '+table+' WHERE id=?',(item['id'],))
                    except sqlite3.IntegrityError as error:blocked='bazi_sample_immutable' in str(error)
                    finally:db.execute('ROLLBACK TO sample_immutable_probe');db.execute('RELEASE sample_immutable_probe')
                    unchanged=dict(db.execute('SELECT * FROM '+table+' WHERE id=?',(item['id'],)).fetchone())==before_row
                    checks.append({'table':table,'operation':operation,'blocked':blocked,'unchanged':unchanged})
        return {'checks':checks,'actualDatabaseTriggers':True}
    if action=='sample-fault':
        table={'result':'bazi_sample_results','chunk':'bazi_sample_raw_chunks','field':'bazi_sample_field_results'}.get(data.get('kind'));assert table and type(data.get('enabled')) is bool
        name='sample_owned_qa_'+data['kind']+'_fault'
        with sqlite3.connect(p) as db:
            db.execute('DROP TRIGGER IF EXISTS '+name)
            if data['enabled']:db.execute('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT sample_owned_storage_failure(); END')
        return {'actualDatabaseTrigger':True,'enabled':data['enabled']}
    raise ValueError('Unsupported fixed sample control')
