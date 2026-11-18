"""Actual fresh Python HTTP parent-type negatives. No final acceptance claim."""
import hashlib,http.cookiejar,json,os,socket,sqlite3,subprocess,sys,time,urllib.error,urllib.request
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'06_验证与后续工作';BACKEND=ROOT/'04_研发源码/app/r4/backend'
tag=str(time.time_ns());prefix='负责人优化建议-卡组迁移父节点-'+tag;database=OUT/(prefix+'.sqlite3');log=OUT/(prefix+'.log');report=OUT/(prefix+'.json')
socket_=socket.socket();socket_.bind(('127.0.0.1',0));port=socket_.getsockname()[1];socket_.close();base='http://127.0.0.1:'+str(port)
env={k:os.environ[k] for k in ('SystemRoot','WINDIR','TEMP','TMP') if k in os.environ};env['PATH']='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin'+os.pathsep+os.defpath
client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
checks=[];process=None
def api(path,data=None,key=None):
    body=None if data is None else json.dumps(data,ensure_ascii=False,separators=(',',':')).encode();headers={} if data is None else {'Content-Type':'application/json'}
    if key:headers['X-EW-Request-ID']=key
    request=urllib.request.Request(base+'/api/'+path,body,headers,method='GET' if data is None else 'POST')
    try:
        with client.open(request,timeout=30) as response:return response.status,json.loads(response.read())
    except urllib.error.HTTPError as error:return error.code,json.loads(error.read())
try:
    with log.open('wb') as stream:
        process=subprocess.Popen([sys.executable,'-B',str(BACKEND/'server.py'),'--db',str(database),'--port',str(port),'--web-root',str(ROOT/'03_当前APP')],cwd=ROOT,env=env,stdout=stream,stderr=stream,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        until=time.monotonic()+45
        while True:
            try:
                if api('health')[0]==200:break
            except (OSError,urllib.error.URLError):pass
            if process.poll() is not None or time.monotonic()>until:raise AssertionError('Owned fresh startup failed')
            time.sleep(.15)
        status,user=api('auth/setup',{'username':'parent_type_component','password':'SyntheticOnly!'+uuid4().hex,'name':'合成父节点组件'});assert status==200,(status,user)
        card={'id':'synthetic_parent_card','theme':'life','text':{},'frontUrl':'','backUrl':'','alt':{},'author':'','licenseReference':'','licenseScope':'','practiceKey':'','courseId':'','actionSeconds':None,'sandboxOnly':True}
        value={'schema':1,'deck':{'deckId':'parent_type_component','version':1,'environment':'sandbox','data':{'name':'Synthetic parent-type component','system':'daily-wisdom','expectedCount':None,'cards':[card],'rightsReference':'','artReviewNote':''}},'baseVersionId':None,'baseRevision':None,'provenance':{'sourceType':'synthetic_sandbox','sourceReference':'Explicit synthetic component, no professional approval','sourceDocumentSha256':None,'fieldSources':[]}}
        status,preview=api('admin/cards/imports/preview',value,uuid4().hex);assert status==200 and preview['summary']['applyBlocked'] is False,(status,preview)
        status,applied=api('admin/cards/imports/'+preview['job']['id']+'/apply',{'requestId':uuid4().hex,'confirmed':True,'version':preview['job']['version']});assert status==200,(status,applied)
        base_item=applied['item'];next_value=json.loads(json.dumps(value));next_value.update(baseVersionId=base_item['id'],baseRevision=base_item['revision']);next_value['deck']['version']=2
        for field in ('deck','provenance'):
            for label,parent in [('nonempty-array',[1]),('nonempty-string','x'),('nonzero-number',1),('boolean-true',True)]:
                invalid=json.loads(json.dumps(next_value));invalid[field]=parent;status,result=api('admin/cards/imports/preview',invalid,uuid4().hex)
                passed=status==400 or status==200 and result.get('summary',{}).get('applyBlocked') is True
                checks.append({'field':field,'parentType':label,'status':status,'passed':passed,'applyBlocked':result.get('summary',{}).get('applyBlocked'),'error':result.get('error'),'jobCreated':bool(result.get('job',{}).get('id'))})
        with sqlite3.connect(database) as db:
            counts={table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('card_deck_versions','card_deck_sources','card_import_receipts')}
        assert counts=={'card_deck_versions':1,'card_deck_sources':1,'card_import_receipts':1},counts
finally:
    if process and process.poll() is None:
        process.terminate()
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.kill();process.wait()
    inputs=[BACKEND/'card_imports.py',BACKEND/'card_import_schema.sql',BACKEND/'server.py',BACKEND/'card_import_worker.cjs',ROOT/'04_研发源码/app/r4/card-import-engine.js',Path(__file__)]
    value={'formalAcceptance':False,'scope':'Actual fresh Python product HTTP, existing base plus invalid deck/provenance parents','syntheticOnly':True,'base':base,'database':str(database.relative_to(ROOT)).replace('\\','/'),'ownedProcessStopped':process is not None and process.poll() is not None,'passed':sum(r['passed'] for r in checks),'failed':sum(not r['passed'] for r in checks),'checks':checks,'sourceHashes':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    report.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode());print(report.name,value['passed'],value['failed'])
    if value['failed']:sys.exit(1)
