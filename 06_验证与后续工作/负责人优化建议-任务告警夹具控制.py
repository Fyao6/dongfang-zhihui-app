"""Fixed owned-fixture controls; native arguments/results and business math are preserved."""
import os
import inspect
import json
from pathlib import Path
import sqlite3
import threading
import time
from uuid import uuid4
LOCK=threading.RLock()
GATE={'kind':'','at':1,'seen':0,'entered':False,'phase':'before-claim'}
RELEASE=threading.Event()
ORIGINAL_ENV={}
KINDS=('payment_callbacks','payment_recovery','privacy_objects','payment_monitor','alert_notifications')
TABLES=('ops_runtime_identity','ops_task_config','ops_task_schedules','ops_task_runs','ops_workers','ops_claim_fences','payment_monitor_scans','payment_alerts','payment_alert_actions','payment_alert_notifications','payment_alert_notification_attempts','payment_alert_notification_receipts','payment_callback_inbox','payment_recovery_jobs','payment_late_cases','privacy_object_deletions','commerce_orders','commerce_products','digital_sandbox_assets','commerce_order_items','commerce_payment_events','commerce_entitlements','commerce_reservations','commerce_skus','digital_order_snapshots','digital_entitlement_grants','membership_ai_periods','membership_ai_events','membership_ai_allocations','ai_gateway_jobs','ai_gateway_attempts','ai_gateway_wallets','ai_gateway_quota_events','membership_order_snapshots','membership_subscriptions')
PRIVATE={'session_hash','lease_token','run_lease_token','schedule_lease_token','adapter_binding','token','password_hash'}
def seed_scenario(database):
    name=os.environ.get('TASK_ALERT_SCENARIO')
    if not name:return
    source=Path(__file__).with_name('负责人优化建议-任务告警场景夹具.json')
    scenario=json.loads(source.read_text(encoding='utf-8'))['scenarios'][name]
    with sqlite3.connect(database) as db:
        for sql in scenario.get('schema',[]):
            if not sql.lstrip().upper().startswith(('CREATE TABLE','CREATE INDEX','CREATE UNIQUE INDEX')):raise ValueError('Only fixed preinit table schema')
            db.execute(sql.replace("CREATE TABLE ","CREATE TABLE IF NOT EXISTS ",1).replace("CREATE INDEX ","CREATE INDEX IF NOT EXISTS ",1).replace("CREATE UNIQUE INDEX ","CREATE UNIQUE INDEX IF NOT EXISTS ",1))
        for table,rows in scenario.get('rows',{}).items():
            if not table.replace('_','').isalnum():raise ValueError('Invalid fixed table')
            for row in rows:
                columns=list(row)
                if any(not c.replace('_','').isalnum() for c in columns):raise ValueError('Invalid fixed column')
                db.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?'for _ in columns)+')',tuple(row[c]for c in columns))
def barrier(kind,phase='before-claim'):
    with LOCK:
        if GATE['kind']!=kind or GATE['phase']!=phase:return
        GATE['seen']+=1
        wait=GATE['seen']==GATE['at']
        if wait:GATE['entered']=True
    if wait and not RELEASE.wait(95):raise RuntimeError('owned_fixture_barrier_timeout')
def install_hooks(server_module):
    import payment_callbacks,payment_recovery,local_tasks
    for cls,kind in ((payment_callbacks.PaymentCallbacks,'payment_callbacks'),(payment_recovery.PaymentRecovery,'payment_recovery')):
        original=cls.claim
        def wrapped(self,*args,_native=original,_kind=kind,**kwargs):
            if kwargs.get('claim_guard') is not None:barrier(_kind)
            return _native(self,*args,**kwargs)
        cls.claim=wrapped
    native=local_tasks.collect_monitor
    def collected(*args,**kwargs):
        result=native(*args,**kwargs)
        barrier('payment_monitor','after-capture')
        return result
    local_tasks.collect_monitor=collected
    # The first direct connect in process_notifications is immediately BEFORE
    # its native BEGIN IMMEDIATE. The later completion connect is never held.
    native_connect=server_module.Store.connect
    lines,start=inspect.getsourcelines(local_tasks.LocalTasks.process_notifications)
    claim_line=next(start+i for i,line in enumerate(lines) if 'with self.store.connect() as db:' in line)
    code=local_tasks.LocalTasks.process_notifications.__code__
    def connect(self,*args,**kwargs):
        frame=inspect.currentframe().f_back
        if frame.f_code is code and frame.f_lineno==claim_line:barrier('alert_notifications')
        return native_connect(self,*args,**kwargs)
    server_module.Store.connect=connect
def handle(database,data):
    action=data.get('action','')
    if not action.startswith('ops-') and action not in ('notification-adapter','notification-proxy-env','due-notification','expire-notification-lease'):return None
    path=Path(database).resolve()
    assert path.parent==Path(__file__).resolve().parent and path.name.startswith('负责人优化建议-任务告警隔离-')
    if action=='ops-barrier-arm':
        kind,at,phase=data.get('kind'),data.get('at',1),data.get('phase','before-claim')
        if kind not in KINDS or type(at)is not int or not 1<=at<=10 or phase not in ('before-claim','after-capture'):raise ValueError('Invalid barrier')
        with LOCK:GATE.update(kind=kind,at=at,phase=phase,seen=0,entered=False);RELEASE.clear()
        return {'armed':True,'beforeNativeTransaction':phase=='before-claim'}
    if action=='ops-barrier-state':
        with LOCK:return dict(GATE)
    if action=='ops-barrier-release':
        RELEASE.set()
        with LOCK:GATE['kind']=''
        return {'released':True}
    if action=='notification-proxy-env':
        names=('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy')
        for name in names:ORIGINAL_ENV.setdefault(name,os.environ.get(name,''))
        mode=data.get('mode')
        if mode not in ('enabled','restore'):raise ValueError('Invalid proxy mode')
        origin=os.environ['TASK_ALERT_RECEIVER_ENDPOINT'].split('/task-alert-fixture/')[0]
        for name in names:os.environ[name]=ORIGINAL_ENV[name] if mode=='restore' else '' if name.lower()=='no_proxy' else origin
        return {'changed':True,'serverEnvironmentOnly':True,'hostileProxyEnabled':mode=='enabled','proxyValuesReturned':False}
    if action in ('ops-runtime-env','notification-adapter'):
        names=('EW_LOCAL_TASK_RUNTIME_ENABLED','EW_LOCAL_TASK_RUNTIME_ID','EW_LOCAL_TASK_MANIFEST_SHA256') if action=='ops-runtime-env' else ('EW_LOCAL_ALERT_FIXTURE_ENABLED','EW_LOCAL_ALERT_FIXTURE_ENDPOINT','EW_LOCAL_ALERT_FIXTURE_SECRET_REF','EW_LOCAL_ALERT_QA_SECRET')
        for name in names:
            ORIGINAL_ENV.setdefault(name,os.environ.get(name,''));os.environ[name]=ORIGINAL_ENV[name]
        mode=data.get('mode','enabled')
        if action=='ops-runtime-env':
            if mode=='disabled':os.environ[names[0]]='0'
            elif mode=='runtime-mismatch':os.environ[names[1]]=str(uuid4())
            elif mode=='manifest-mismatch':os.environ[names[2]]='0'*64
            elif mode!='enabled':raise ValueError('Invalid mode')
        else:
            endpoint=ORIGINAL_ENV[names[1]]
            invalid={'host':endpoint.replace('127.0.0.1','localhost'),'short-ip':endpoint.replace('127.0.0.1','127.1'),'integer-ip':endpoint.replace('127.0.0.1','2130706433'),'userinfo':endpoint.replace('http://','http://qa:qa@'),'query':endpoint+'?qa=1','fragment':endpoint+'#qa','path':endpoint+'/other','leading-space':' '+endpoint,'mapped-ip':endpoint.replace('127.0.0.1','[::ffff:127.0.0.1]'),'https':endpoint.replace('http:','https:')}
            if mode=='disabled':os.environ[names[0]]='0'
            elif mode=='invalid-ref':os.environ[names[2]]='INVALID_REF'
            elif mode=='rotated-secret':os.environ[names[3]]=ORIGINAL_ENV[names[3]]+'-rotated'
            elif mode in invalid:os.environ[names[1]]=invalid[mode]
            elif mode!='enabled':raise ValueError('Invalid adapter mode')
        return {'changed':True,'serverEnvironmentOnly':True,'mode':mode}
    with sqlite3.connect(path,timeout=15) as db:
        db.row_factory=sqlite3.Row
        if action=='ops-due':
            if data.get('kind')not in KINDS:raise ValueError('Invalid task')
            db.execute('UPDATE ops_task_schedules SET next_due=0 WHERE kind=?',(data['kind'],));return {'changed':True,'scheduleOnly':True}
        if action=='due-notification':
            db.execute('UPDATE payment_alert_notifications SET next_attempt=0 WHERE id=?',(data.get('id'),));return {'changed':True,'attemptsUnchanged':True}
        if action=='expire-notification-lease':
            db.execute('UPDATE payment_alert_notifications SET lease_until=? WHERE id=?',(int(time.time()*1000)-1000,data.get('id')));return {'fixtureMutation':True,'deadlineOnly':True,'attemptsUnchanged':True}
        if action=='ops-expire-runtime-lease':
            stamp=int(time.time()*1000)-1000;db.execute('UPDATE ops_task_runs SET lease_until=? WHERE id=?',(stamp,data.get('runId')));db.execute('UPDATE ops_task_schedules SET lease_until=? WHERE last_run_id=?',(stamp,data.get('runId')));return {'fixtureMutation':True,'deadlineOnly':True}
        if action=='ops-snapshot':
            selected=data.get('tables',list(TABLES))
            if not isinstance(selected,list)or any(name not in TABLES for name in selected):raise ValueError('Invalid snapshot')
            output={}
            for table in selected:
                if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():output[table]=None;continue
                columns=[r['name']for r in db.execute('PRAGMA table_info('+table+')')if r['name']not in PRIVATE]
                output[table]=[dict(r)for r in db.execute('SELECT '+','.join('"'+c+'"'for c in columns)+' FROM '+table+' LIMIT 6000')]
            return {'tables':output,'readOnly':True,'databaseNow':int(time.time()*1000),'proofRows':db.execute('SELECT count(*) FROM ops_claim_fences').fetchone()[0]}
        if action=='ops-marker-immutability':
            blocked=[]
            for sql in ('UPDATE ops_runtime_identity SET created=created+1 WHERE id=1','DELETE FROM ops_runtime_identity WHERE id=1','INSERT OR REPLACE INTO ops_runtime_identity SELECT * FROM ops_runtime_identity'):
                try:db.execute(sql)
                except sqlite3.IntegrityError:blocked.append(True)
                else:raise ValueError('Marker unprotected')
            return {'blocked':blocked,'actualDatabaseTriggers':True}
        if action=='ops-change-lease':
            run,mode=data.get('runId'),data.get('mode')
            if mode=='run-token':db.execute("UPDATE ops_task_runs SET lease_token='owned-invalid-run-token' WHERE id=?",(run,))
            elif mode=='schedule-token':db.execute("UPDATE ops_task_schedules SET lease_token='owned-invalid-schedule-token' WHERE last_run_id=?",(run,))
            elif mode=='budget':
                stamp=int(time.time()*1000)+500;db.execute('UPDATE ops_task_runs SET lease_until=? WHERE id=?',(stamp,run));db.execute('UPDATE ops_task_schedules SET lease_until=? WHERE last_run_id=?',(stamp,run))
            else:raise ValueError('Invalid lease mutation')
            return {'fixtureMutation':True,'leaseOnly':True}
        if action=='ops-callback-state':
            status=data.get('status')
            if status not in ('received','retry','manual_review','applied'):raise ValueError('Invalid callback state')
            db.execute('UPDATE payment_callback_inbox SET status=?,next_attempt=0,lease_until=0 WHERE id=?',(status,data.get('id')));return {'fixtureMutation':True,'statusOnly':True}
        raise ValueError('Unsupported fixed task control')
