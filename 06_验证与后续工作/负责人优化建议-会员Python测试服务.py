"""QA-only fresh real server. Controls inject clocks, interruptions and a pre-transaction barrier only."""
import argparse,importlib.util,json,sys,threading,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
root=Path(__file__).resolve().parents[1];backend=root/'04_研发源码/app/r4/backend';sys.path.insert(0,str(backend))
import membership_lifecycle as membership
import commerce
parser=argparse.ArgumentParser();parser.add_argument('--db',type=Path,required=True);parser.add_argument('--token',required=True);args=parser.parse_args()
assert not args.db.exists() and args.db.resolve().is_relative_to(root/'06_验证与后续工作')
lock=threading.RLock();release=threading.Event();control={'nowMs':None,'pauseOrderId':None,'entered':False,'failOrderId':None,'failCount':0}
real_clock=membership.now
def qa_clock():
    with lock:value=control['nowMs']
    return real_clock() if value is None else value
membership.now=qa_clock
original_pay=commerce.Commerce.pay
def interrupted_pay(self,oid,data):
    with lock:
        pause=control['pauseOrderId']==oid
        if pause:control['entered']=True;control['pauseOrderId']=None
    if pause:release.wait(20)
    return original_pay(self,oid,data)
commerce.Commerce.pay=interrupted_pay
original_callback=membership.Membership.on_commerce_payment
def interrupted_callback(self,db,order_id):
    with lock:
        failure=control['failOrderId']==order_id and control['failCount']>0
        if failure:control['failCount']-=1
    if failure:raise RuntimeError('QA_ONLY_MEMBERSHIP_CALLBACK_INTERRUPTED')
    return original_callback(self,db,order_id)
membership.Membership.on_commerce_payment=interrupted_callback
spec=importlib.util.spec_from_file_location('membership_test_actual_server',backend/'server.py');actual=importlib.util.module_from_spec(spec);spec.loader.exec_module(actual)
assert actual.Membership is membership.Membership and actual.Commerce is commerce.Commerce,'Real integrated dispatch is required'
actual.urlopen=lambda *a,**k:(_ for _ in ()).throw(actual.URLError('QA blocks external provider calls'))
base_handler=actual.make_handler(actual.Store(args.db),root/'03_当前APP')
class Handler(base_handler):
    def monitor(self):
        if self.headers.get('X-Membership-Test')!=args.token:return self.send(403,{'error':'test token required'})
        if self.command=='POST':
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=8192:return self.send(400,{'error':'invalid test control'})
            d=json.loads(self.rfile.read(length))
            with lock:
                if 'nowMs' in d:
                    assert d['nowMs'] is None or type(d['nowMs']) is int and 0<d['nowMs']<4_000_000_000_000
                    control['nowMs']=d['nowMs']
                if 'pauseOrderId' in d:control['pauseOrderId']=d['pauseOrderId'];control['entered']=False;release.clear()
                if d.get('release'):release.set()
                if 'failOrderId' in d:control['failOrderId']=d['failOrderId'];control['failCount']=int(d.get('failCount',1))
        with lock:return self.send(200,{'isolated':True,'externalProviderTested':False,'syntheticDataOnly':True,'clockOverride':control['nowMs'],'entered':control['entered'],'callbackFailuresRemaining':control['failCount'],'barrierPosition':'before-original-python-pay-transaction'})
    def do_GET(self):
        if urlsplit(self.path).path=='/__membership-test/control':return self.monitor()
        return super().do_GET()
    def do_POST(self):
        if urlsplit(self.path).path=='/__membership-test/control':return self.monitor()
        return super().do_POST()
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);print('APP: http://127.0.0.1:'+str(server.server_port),flush=True)
try:server.serve_forever()
finally:release.set();server.server_close()

