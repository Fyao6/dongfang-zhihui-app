"""Actual Runner + real HTTP + its real STOP event; no CLI signal claim on Windows."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'04_研发源码/app/r4/backend'))
import local_task_runner as native
parser=argparse.ArgumentParser()
parser.add_argument('--manifest',required=True)
parser.add_argument('--base',required=True)
parser.add_argument('--worker-id',required=True)
parser.add_argument('--session-ref',required=True)
args=parser.parse_args()
_,document=native.load_manifest(args.manifest)
assert args.base==document['core']['base']
session=os.environ[args.session_ref]
runner=native.Runner(document,args.base,args.worker_id,session)
observer=native.Runner(document,args.base,args.worker_id,session)
native.STOP.clear()
result={}
def work():
    try:result['code']=runner.run()
    except BaseException as error:result['errorType']=type(error).__name__
thread=threading.Thread(target=work,daemon=True)
thread.start()
path='/api/admin/local-tasks/runs?'+urlencode({'workerId':args.worker_id})
deadline=time.monotonic()+45
while time.monotonic()<deadline:
    rows=observer.http(path)['items']
    if rows and all(row['status']!='running' for row in rows):break
    if not thread.is_alive():raise RuntimeError('Actual Runner stopped before a real tick')
    time.sleep(.2)
else:raise RuntimeError('No actual bounded Runner tick')
native.STOP.set()
thread.join(76)
assert not thread.is_alive() and result.get('code')==0 and 'errorType'not in result
before=observer.http(path)['items']
time.sleep(2)
after=observer.http(path)['items']
assert before==after
print('TASK_ALERT_STOP_PROOF: '+json.dumps({'realHttp':True,'pid':os.getpid(),'workerId':args.worker_id,'runCountBefore':len(before),'runCountAfter':len(after),'nativeStopEvent':True,'cliSignalGracefulCovered':False,'exitCode':0}),flush=True)
