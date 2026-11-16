"""Prepared fresh real server with explicit synthetic legacy config and local transport only."""
import argparse,importlib.util,json,os,sys,threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];BACK=ROOT/'04_研发源码/app/r4/backend';sys.path.insert(0,str(BACK))
p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--token',required=True);args=p.parse_args()
assert not args.db.exists() and args.db.resolve().is_relative_to(ROOT/'06_验证与后续工作')
spec=importlib.util.spec_from_file_location('secret_reference_actual_fixture',BACK/'server.py');actual=importlib.util.module_from_spec(spec);spec.loader.exec_module(actual)
# Values are supplied only by the parent test process. Do not read, expose or enumerate other env values.
AI=os.environ['EW_AI_SECRET_QA'];DEVICE=os.environ['EW_DEVICE_SECRET_QA'];calls=[];lock=threading.Lock()
class Response:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,limit):return actual.dump({'output':[{'type':'message','content':[{'type':'output_text','text':'SECRET_REF_LOCAL_FIXTURE_REPLY'}]}]}).encode()
def transport(req,*args,**kwargs):
    if req.full_url!='https://secret-fixture.invalid/v1/responses':raise actual.URLError('Only the explicit local secret-reference fixture is allowed')
    assert req.get_header('Authorization')=='Bearer '+AI,'Synthetic header did not resolve'
    body=req.data.decode();assert AI not in body and DEVICE not in body and 'apiKeyRef' not in body and 'EW_AI_SECRET_QA' not in body,'Credential reached model body'
    with lock:calls.append({'kind':'local-process-fixture','authorizationMatched':True,'modelBodyContainsSecret':False,'modelBodyContainsReference':False})
    return Response()
actual.open_legacy_ai=transport
store=actual.Store(args.db)
with store.connect() as db:
    ai={'enabled':False,'apiKey':AI,'endpoint':'https://secret-fixture.invalid/v1/responses','model':'secret-fixture-model','providerId':'secret-fixture','processingRegions':['QA-LOCAL'],'privacyPolicyVersion':'secret-fixture-policy','prompt':'Explicit local test only','knowledge':''}
    db.execute("UPDATE settings SET data=? WHERE key='ai'",(actual.dump(ai),))
    db.execute("UPDATE settings SET data=? WHERE key='integrations'",(actual.dump({'secret-sensor':{'secret':DEVICE,'fieldMap':{}}}),))
base=actual.make_handler(store,ROOT/'03_当前APP')
class Handler(base):
    def do_GET(self):
        if urlsplit(self.path).path=='/__secret-test/state':
            if self.headers.get('X-Secret-Test')!=args.token:return self.send(403,{'error':'test token required'})
            with store.connect() as db:
                rows={t:[tuple(x) for x in db.execute('SELECT * FROM '+t)] for t in ['settings','secret_reference_plans','secret_reference_actions','audits']}
                non_settings=actual.dump({k:v for k,v in rows.items() if k!='settings'});settings=actual.dump(rows['settings'])
                result={'fixture':'synthetic-local-only','calls':list(calls),'metadataContainsCanary':AI in non_settings or DEVICE in non_settings,'settingsContainsCanary':AI in settings or DEVICE in settings,'actions':len(rows['secret_reference_actions']),'plans':len(rows['secret_reference_plans']),'actualProviderTested':False}
            self.cookies_out=[];return self.send(200,result)
        return super().do_GET()
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);print('APP: http://127.0.0.1:'+str(server.server_port),flush=True)
try:server.serve_forever()
finally:server.server_close()
