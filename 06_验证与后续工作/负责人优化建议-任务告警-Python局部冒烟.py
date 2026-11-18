"""Owned fresh native-HTTP implementation smoke; not a formal regression gate."""
import copy
import hashlib
import hmac
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request,build_opener,HTTPCookieProcessor,ProxyHandler
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
BACK=ROOT/'04_研发源码/app/r4/backend'
OUT=ROOT/'06_验证与后续工作'
PY=Path(sys.executable)
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(BACK))
from local_tasks import DEFAULT,canonical

def freeport():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def main():
    report={'scope':'owned fresh native HTTP smoke only','pass':False,'checks':[],'productionEnabled':False}
    tag=str(uuid4());base='http://127.0.0.1:'+str(freeport());db=OUT/('负责人优化建议-任务告警-Python局部冒烟-'+tag+'.sqlite3');manifest=db.with_suffix('.json')
    secret=secrets.token_urlsafe(40);received={};proc=None;fixture=None
    class Receiver(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_POST(self):
            raw=self.rfile.read(int(self.headers['Content-Length']));event=json.loads(raw)
            stamp=self.headers.get('X-EW-Alert-Timestamp','');sig=self.headers.get('X-EW-Alert-Signature','')
            if self.path!='/task-alert-fixture/events' or not hmac.compare_digest(sig,hmac.new(secret.encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()):self.send_error(401);return
            if event['eventId'] in received and received[event['eventId']]!=raw:self.send_error(409);return
            received[event['eventId']]=raw;body=canonical({'accepted':True,'eventId':event['eventId']}).encode();stamp=str(int(time.time()))
            self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('X-EW-Alert-Timestamp',stamp);self.send_header('X-EW-Alert-Signature',hmac.new(secret.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest());self.end_headers();self.wfile.write(body)
    def check(name,condition):
        report['checks'].append({'name':name,'pass':bool(condition)})
        if not condition:raise AssertionError(name)
    try:
        result=subprocess.run([str(PY),'-B',str(BACK/'local_task_bootstrap.py'),'--backend','python','--state',str(db),'--manifest',str(manifest),'--base',base,'--app',str(ROOT/'03_当前APP/东方智慧-首页体验R4.html')],capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        check('explicit_fresh_bootstrap',result.returncode==0)
        document=json.loads(manifest.read_text(encoding='utf-8'));core=document['core']
        fixture=ThreadingHTTPServer(('127.0.0.1',0),Receiver);threading.Thread(target=fixture.serve_forever,daemon=True).start()
        env=dict(os.environ,EW_LOCAL_TASK_RUNTIME_ENABLED='1',EW_LOCAL_TASK_RUNTIME_ID=core['runtimeId'],EW_LOCAL_TASK_MANIFEST_SHA256=document['manifestSha256'],
            EW_PAYMENT_CALLBACK_SANDBOX_ENABLED='1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF='EW_PAYMENT_CALLBACK_SMOKE_SECRET',EW_PAYMENT_CALLBACK_SMOKE_SECRET=secret,
            EW_LOCAL_ALERT_FIXTURE_ENABLED='1',EW_LOCAL_ALERT_FIXTURE_ENDPOINT='http://127.0.0.1:'+str(fixture.server_port)+'/task-alert-fixture/events',EW_LOCAL_ALERT_FIXTURE_SECRET_REF='EW_LOCAL_ALERT_SMOKE_SECRET',EW_LOCAL_ALERT_SMOKE_SECRET=secret)
        proc=subprocess.Popen([str(PY),'-B',str(BACK/'server.py'),'--db',str(db),'--port',str(urlport:=int(base.rsplit(':',1)[1])),'--web-root',str(ROOT/'03_当前APP')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        jar=http.cookiejar.CookieJar();client=build_opener(ProxyHandler({}),HTTPCookieProcessor(jar))
        def api(path,data=None,method=None,headers=None):
            req=Request(base+path,data=canonical(data).encode() if data is not None else None,method=method or ('POST' if data is not None else 'GET'),headers=dict({'Content-Type':'application/json'},**(headers or {})))
            try:
                with client.open(req,timeout=15) as response:return response.status,json.loads(response.read())
            except HTTPError as error:return error.code,json.loads(error.read())
        deadline=time.monotonic()+15
        while True:
            try:
                if api('/api/health')[0]==200:break
            except OSError:pass
            if time.monotonic()>deadline:raise AssertionError('owned_server_start')
            time.sleep(.1)
        check('anonymous_admin_denied',api('/api/admin/local-tasks/runtime')[0]==401)
        username='ops_smoke_'+tag[:8];password=secrets.token_urlsafe(18)
        check('real_admin_setup',api('/api/auth/setup',{'username':username,'password':password,'name':'isolated ops smoke'})[0]==200)
        status,r=api('/api/admin/local-tasks/runtime');check('actual_app_and_marker',status==200 and r['runtime']['appSha256']==core['appSha256'] and r['runtime']['identityReady'] and not r['config']['enabled'])
        cfg=copy.deepcopy(DEFAULT);cfg.update(enabled=True,confirmed=True,ruleVersion='isolated-smoke-v1');cfg['thresholdSeconds']['callbackBacklog']=0
        for kind in ('payment_callbacks','payment_monitor','alert_notifications'):cfg['tasks'][kind]['enabled']=True
        check('config_revision_cas',api('/api/admin/local-tasks/config',cfg,'PATCH')[0]==200 and api('/api/admin/local-tasks/config',cfg,'PATCH')[0]==409)
        check('explicit_commerce_sandbox_enable',api('/api/admin/commerce/settings',{'sandboxEnabled':True,'productionEnabled':False},'PATCH')[0]==200)
        event={'eventId':'smoke:'+tag,'transactionId':'smoke:'+tag,'orderId':'missing:'+tag,'type':'payment.succeeded','amountMinor':1,'currency':'CNY'};stamp=str(int(time.time()));raw=canonical(event).encode()
        check('actual_signed_inbox',api('/api/payment-callbacks/sandbox',event,headers={'X-EW-Callback-Timestamp':stamp,'X-EW-Callback-Signature':hmac.new(secret.encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()})[0]==202)
        payload={'runtimeId':core['runtimeId'],'workerId':'smoke-worker:'+tag,'requestId':'smoke-tick:'+str(uuid4()),'appSha256':core['appSha256']}
        first=copy.deepcopy(payload);status,r=api('/api/admin/local-tasks/tick',first);check('first_real_tick',status==200)
        check('tick_idempotency',api('/api/admin/local-tasks/tick',first)[1]['replayed'] is True)
        check('request_conflict',api('/api/admin/local-tasks/tick',dict(first,workerId='other:'+tag))[0]==409)
        for index in range(3):payload['requestId']='smoke-tick:'+str(uuid4());check('native_unit_tick_'+str(index+1),api('/api/admin/local-tasks/tick',payload)[0]==200)
        alerts=api('/api/admin/payment-alerts')[1]['items'];check('actual_persisted_alert',len(alerts)==1 and alerts[0]['ruleCode']=='callback_manual_review')
        time.sleep(5.2);payload['requestId']='smoke-tick:'+str(uuid4());check('notification_tick',api('/api/admin/local-tasks/tick',payload)[0]==200)
        detail=api('/api/admin/payment-alerts/'+alerts[0]['id'])[1]
        check('actual_signed_fixture_receipt',len(received)==1 and len(detail['receipts'])==1 and detail['notifications'][0]['status']=='fixture_confirmed' and detail['receipts'][0]['externalSent'] is False)
        ack={'requestId':'ack-smoke:'+tag,'version':detail['item']['version'],'note':'owned smoke acknowledged'}
        check('versioned_ack',api('/api/admin/payment-alerts/'+alerts[0]['id']+'/ack',ack)[0]==200 and api('/api/admin/payment-alerts/'+alerts[0]['id']+'/ack',ack)[1]['replayed'])
        inventory=api('/api/privacy/domains')[1];check('explicit_registry',not inventory['unclassifiedOwnerTables'])
        own=api('/api/privacy/export')[1]['serverData'];serialized=canonical({k:v for k,v in own.items() if k.startswith('localTask') or k.startswith('paymentAlert') or k=='paymentMonitorScans'})
        check('safe_own_export',secret not in serialized and all(key not in serialized for key in ('session_hash','lease_token','adapter_binding','payload_data','note')))
        check('actual_logout',api('/api/auth/logout',{})[0]==200);check('actual_login',api('/api/auth/login',{'username':username,'password':password})[0]==200)
        payload['requestId']='smoke-tick:'+str(uuid4());check('worker_session_sticky',api('/api/admin/local-tasks/tick',payload)[0]==409)
        cfg=api('/api/admin/local-tasks/config')[1]['config'];cfg['enabled']=False;check('disable_config',api('/api/admin/local-tasks/config',cfg,'PATCH')[0]==200)
        payload.update(workerId='new-worker:'+tag,requestId='smoke-tick:'+str(uuid4()));check('disabled_new_claim',api('/api/admin/local-tasks/tick',payload)[0]==503)
        report.update(pass_=True,passCount=len(report['checks']),failCount=0,runtimeId=core['runtimeId'],manifest=str(manifest),state=str(db),appSha256=core['appSha256'],fixtureEvents=len(received),realExternalMessages=False)
        report['pass']=True;report.pop('pass_',None)
    except Exception as error:
        report.update(errorType=type(error).__name__,passCount=sum(x['pass'] for x in report['checks']),failCount=1)
    finally:
        if proc:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        if fixture:fixture.shutdown();fixture.server_close()
        path=OUT/'负责人优化建议-任务告警-Python局部冒烟.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'pass':report['pass'],'passCount':report.get('passCount',0),'failCount':report.get('failCount',0),'failedChecks':[x['name'] for x in report['checks'] if not x['pass']],'errorType':report.get('errorType'),'report':str(path)},ensure_ascii=False))
    return 0 if report['pass'] else 1

if __name__=='__main__':raise SystemExit(main())
