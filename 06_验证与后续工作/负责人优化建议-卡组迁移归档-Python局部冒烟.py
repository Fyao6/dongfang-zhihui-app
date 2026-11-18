"""Actual fresh product HTTP, synthetic legacy examples; not final acceptance."""
import hashlib,http.cookiejar,json,os,socket,sqlite3,subprocess,sys,time,urllib.error,urllib.request
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'06_验证与后续工作';BACKEND=ROOT/'04_研发源码/app/r4/backend';NODE=Path('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin')
tag=str(time.time_ns());prefix='负责人优化建议-卡组迁移归档-局部-'+tag
dbpath=OUT/(prefix+'.sqlite3');report=OUT/(prefix+'.json');logpath=OUT/(prefix+'.log')
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();base='http://127.0.0.1:'+str(port)
env={k:os.environ[k] for k in ('SystemRoot','WINDIR','TEMP','TMP') if k in os.environ};env['PATH']=str(NODE)+os.pathsep+os.defpath;env['PYTHONDONTWRITEBYTECODE']='1'
checks=[];password='ComponentOnly!'+uuid4().hex;server=None
def client():return urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
owner,other,anonymous=client(),client(),client()
def request(c,method,path,data=None,raw=None,headers=None):
    headers=dict(headers or {})
    if data is not None:raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
    if raw is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(base+path,raw,headers,method=method)
    try:
        with c.open(req,timeout=25) as response:return response.status,json.loads(response.read())
    except urllib.error.HTTPError as error:return error.code,json.loads(error.read())
def get(path,c=owner):
    status,data=request(c,'GET',path);assert status==200,(path,status,data);return data
def post(path,data=None,raw=None,headers=None,c=owner):
    status,value=request(c,'POST',path,data,raw,headers);assert status==200,(path,status,value);return value
def check(name,fn):
    try:fn();checks.append({'name':name,'passed':True})
    except Exception as error:checks.append({'name':name,'passed':False,'error':str(error)});raise
def eq(a,b):assert a==b,(a,b)
def rawfile(records):return json.dumps({'schema':1,'sourceReference':'explicit synthetic component file','records':records},ensure_ascii=False,separators=(',',':')).encode()
def preview(raw,key=None):return post('/api/cards/legacy-migrations/preview',raw=raw,headers={'X-EW-Request-ID':key or uuid4().hex})
def process(job,action='apply',key=None):return post('/api/cards/legacy-migrations/'+job['id']+'/'+action,{'requestId':key or uuid4().hex,'confirmed':True,'version':job['version']})
try:
    with logpath.open('wb') as log:
        server=subprocess.Popen([sys.executable,'-B',str(BACKEND/'server.py'),'--port',str(port),'--db',str(dbpath),'--web-root',str(ROOT/'03_当前APP')],cwd=str(ROOT),env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        until=time.monotonic()+45
        while True:
            try:
                if request(anonymous,'GET','/api/health')[0]==200:break
            except (OSError,urllib.error.URLError):pass
            if server.poll() is not None or time.monotonic()>until:raise AssertionError('fresh product startup failed; see owned log')
            time.sleep(.2)
        post('/api/auth/setup',{'username':'migration_admin','password':password,'name':'Synthetic owner'})
        post('/api/auth/register',{'username':'migration_other','password':password,'name':'Synthetic other'},c=other)
        records=[{'cardId':'legacy-'+str(i),'date':'2026-11-17','drawnAt':i} for i in range(101)]
        raw=rawfile(records);key=uuid4().hex;p=preview(raw,key);job=p['job'];path='/api/cards/legacy-migrations/'+job['id']
        check('actual raw preview has101 pending and50 target page',lambda:(eq(p['summary']['remaining'],101),eq(len(p['targets']),50),eq(p['previewPlan']['newRecords'],101),eq(bool(p['next']),True)))
        check('preview exact raw idempotence',lambda:eq(preview(raw,key)['job']['id'],job['id']))
        check('same request changed raw rejected',lambda:eq(request(owner,'POST','/api/cards/legacy-migrations/preview',raw=raw+b' ',headers={'X-EW-Request-ID':key})[0],409))
        check('decoded duplicate JSON keys rejected before write',lambda:eq(request(owner,'POST','/api/cards/legacy-migrations/preview',raw=b'{"schema":1,"schema":1}',headers={'X-EW-Request-ID':uuid4().hex})[0],400))
        check('foreign owner and anonymous blocked',lambda:(eq(request(other,'GET',path)[0],404),eq(request(anonymous,'GET',path)[0],401)))
        applykey=uuid4().hex;result=process(job,key=applykey)
        check('actual product first batch100 and remainder1',lambda:(eq(result['receipt']['counts']['selected'],100),eq(result['summary']['added'],100),eq(result['summary']['remaining'],1)))
        check('exact operation replay despite stale version returns original receipt',lambda:eq(process(job,key=applykey),result))
        check('same operation request different semantics409',lambda:eq(request(owner,'POST',path+'/undo',{'requestId':applykey,'confirmed':True,'version':2})[0],409))
        result=process(result['job']);job=result['job']
        check('second actual batch1 reaches101',lambda:(eq(result['receipt']['counts']['selected'],1),eq(result['summary']['added'],101),eq(result['summary']['remaining'],0)))
        archives=get('/api/cards/legacy-archives');more=get('/api/cards/legacy-archives?before='+archives['next'])
        check('archives stable50 cursor and factual missing labels',lambda:(eq(len(archives['items']),50),eq(len(more['items']),50),eq(archives['items'][0]['authoritative'],False),eq(len(archives['items'][0]['factsMissing']),4)))
        check('foreign and malformed cursors400',lambda:(eq(request(other,'GET','/api/cards/legacy-archives?before='+archives['next'])[0],400),eq(request(owner,'GET','/api/cards/legacy-archives?before=garbage')[0],400)))
        item=archives['items'][0];status,edited=request(owner,'PATCH','/api/cards/legacy-archives/'+item['id'],{'revision':0,'note':'Later synthetic personal note','favorite':True});eq(status,200)
        check('personal note favorite revision and stale CAS409',lambda:(eq(edited['item']['revision'],1),eq(request(owner,'PATCH','/api/cards/legacy-archives/'+item['id'],{'revision':0,'note':'stale'})[0],409)))
        u=process(job,'undo');u2=process(u['job'],'undo')
        check('undo protects later edit and removes exactly100 unchanged originals',lambda:(eq(u2['summary']['skippedChanged'],1),eq(len(get('/api/cards/legacy-archives')['items']),1),eq(u['receipt']['counts']['undone']+u2['receipt']['counts']['undone'],100)))
        p2=preview(raw);r2=process(p2['job']);pending=r2['job']
        exported=get('/api/privacy/export');blob=json.dumps(exported)
        check('safe owner export includes migration and excludes proof secrets',lambda:(eq('cardLegacyArchives' in exported['serverData'],True),eq('session_hash' in blob,False),eq('sessionHash' in blob,False)))
        post('/api/privacy/requests',{'kind':'delete-records','requestId':uuid4().hex})
        check('actual records clear erases source and archives invalidates pending job',lambda:(eq(len(get('/api/cards/legacy-archives')['items']),0),eq(request(owner,'POST','/api/cards/legacy-migrations/'+pending['id']+'/apply',{'requestId':uuid4().hex,'confirmed':True,'version':pending['version']})[0],410)))
        with sqlite3.connect(dbpath) as db:
            check('migration never grants serverdraw quota or timezone and no guard remains',lambda:(eq(db.execute('SELECT count(*) FROM card_draws').fetchone()[0],0),eq(db.execute('SELECT count(*) FROM card_daily_quota').fetchone()[0],0),eq(db.execute('SELECT count(*) FROM card_zone_preferences').fetchone()[0],0),eq(db.execute('SELECT count(*) FROM card_history_migration_guards').fetchone()[0],0),eq(db.execute("SELECT count(*) FROM card_history_migration_jobs WHERE data!='{}' OR source_reference!=''").fetchone()[0],0)))
finally:
    if server and server.poll() is None:
        server.terminate()
        try:server.wait(timeout=8)
        except subprocess.TimeoutExpired:server.kill();server.wait()
    paths=[BACKEND/'card_history_migration.py',BACKEND/'card_history_migration_schema.sql',ROOT/'04_研发源码/app/cloud/lib/card-history-migration.ts',BACKEND/'server.py',BACKEND/'card_imports.py',BACKEND/'card_import_worker.cjs',ROOT/'04_研发源码/app/r4/card-import-engine.js']
    value={'scope':'actual fresh Python HTTP only; not formal acceptance; APP rendering not tested','formalAcceptance':False,'syntheticDataOnly':True,'realExternalService':False,'base':base,'database':str(dbpath.relative_to(ROOT)).replace('\\','/'),'ownedProcessStopped':server is not None and server.poll() is not None,'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'checks':checks,'sourceHashes':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    report.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode());print(report.name,value['passed'],value['failed'],flush=True)
