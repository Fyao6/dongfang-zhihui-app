"""Owner-private card file previews; imports never approve or publish a deck."""
import copy,base64,hashlib,json,os,re,shutil,sqlite3,subprocess,threading,time
from pathlib import Path
from urllib.parse import parse_qs,unquote,urlsplit
from uuid import uuid4
from card_import_wire import pack_wire,decode_wire,worker_result
HERE=Path(__file__).resolve().parent
NODE=shutil.which('node')
WORKER=HERE/'card_import_worker.cjs'
SLOTS=threading.BoundedSemaphore(2)
TABLES=['card_import_diagnostics','card_import_jobs','card_deck_sources','card_import_receipts','card_deck_activation_events','card_import_guards','card_import_erase_guards']
REF_FIELDS=[('card_import_diagnostics','data'),('card_import_jobs','payload_data'),('card_import_jobs','raw_data'),('card_import_jobs','base_data'),('card_import_jobs','preview_data'),('card_deck_sources','source_data'),('card_import_receipts','result_data'),('card_deck_activation_events','result_data'),('card_import_guards','data')]
def now():return time.time_ns()//1000000
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(v):return hashlib.sha256(v if isinstance(v,bytes) else v.encode('utf-8')).hexdigest()
def init_schema(db):
    db.executescript((HERE/'card_import_schema.sql').read_text(encoding='utf-8'))
    from card_service import DEFAULT
    db.execute("INSERT OR IGNORE INTO settings VALUES('card_service',?)",(canonical(DEFAULT),))
def privacy_export(db,owner):return {key:[dict(r) for r in db.execute('SELECT '+cols+' FROM '+t+' WHERE owner=?',(owner,))] for key,t,cols in [('cardImportJobs','card_import_jobs','id,source_sha256,canonical_sha256,status,version,result_version_id,created,updated,erased_at'),('cardDeckSourceMetadata','card_deck_sources','id,deck_version_id,digest,created'),('cardImportReceipts','card_import_receipts','id,job_id,result_data,created'),('cardDeckActivations','card_deck_activation_events','id,result_data,created')]}
def erase(db,owner,source,receipt_id,stamp):
    counts={t:db.execute('SELECT count(*) FROM '+t+' WHERE owner=? AND '+predicate,(owner,)).fetchone()[0] for t,predicate in [('card_import_diagnostics','1'),('card_import_jobs','erased_at=0'),('card_deck_sources',"source_data!='{}'"),('card_import_receipts',"coalesce(json_extract(result_data,'$.erased'),0)!=1"),('card_deck_activation_events',"json_type(result_data,'$.receipt.reason') IS NOT NULL")]}
    db.execute('INSERT INTO card_import_erase_guards VALUES(?,?,?,?,?)',(str(uuid4()),owner,source,receipt_id,stamp))
    return {'deletedCounts':counts,'retentionDays':None,'secureWipe':False,'retained':['business-deck-data','minimal-source-hashes-and-processing-counts']}
class WorkerError(Exception):
    def __init__(self,code,status=503,path=''):self.code,self.status,self.path=code,status,path

def worker_call(request):
    """Fixed executable/script, no shell, no inherited credentials, bounded pipes."""
    if not NODE or not WORKER.is_file():raise WorkerError('adapter_unavailable')
    if not SLOTS.acquire(blocking=False):raise WorkerError('adapter_busy')
    process=None
    try:
        body=canonical(request).encode('utf-8')
        if len(body)>6*1024*1024:raise WorkerError('worker_input_too_large',413)
        env={k:os.environ[k] for k in ('SystemRoot','WINDIR','TEMP','TMP') if k in os.environ}
        env.update({'PATH':str(Path(NODE).parent),'TZ':'UTC','LANG':'C.UTF-8'})
        process=subprocess.Popen([str(Path(NODE).resolve()),str(WORKER)],cwd=str(HERE),env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        output=[bytearray(),bytearray()];overflow=threading.Event()
        def read(stream,index,cap):
            while True:
                chunk=stream.read(8192)
                if not chunk:break
                if len(output[index])+len(chunk)>cap:
                    overflow.set();process.kill();break
                output[index].extend(chunk)
        readers=[threading.Thread(target=read,args=(process.stdout,0,8*1024*1024),daemon=True),threading.Thread(target=read,args=(process.stderr,1,65536),daemon=True)]
        for thread in readers:thread.start()
        def write():
            try:process.stdin.write(body);process.stdin.close()
            except (OSError,BrokenPipeError):pass
        writer=threading.Thread(target=write,daemon=True);writer.start()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill();process.wait();raise WorkerError('compute_timeout',504) from None
        writer.join(timeout=1)
        for thread in readers:thread.join(timeout=1)
        if overflow.is_set():raise WorkerError('worker_output_too_large',413)
        if process.returncode:raise WorkerError('adapter_failed')
        try:value=json.loads(output[0].decode('utf-8',errors='strict'))
        except (ValueError,UnicodeError):raise WorkerError('invalid_worker_response') from None
        if value.get('ok') is not True:
            error=value.get('error') or {};raise WorkerError(error.get('code','invalid_sample'),error.get('status',400),error.get('path',''))
        try:return worker_result(value)
        except ValueError:raise WorkerError('invalid_worker_response') from None
    except (OSError,BrokenPipeError):raise WorkerError('adapter_unavailable') from None
    finally:
        if process:
            if process.poll() is None:process.kill();process.wait()
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream and not stream.closed:stream.close()
        SLOTS.release()

def item(row):return {'id':row['id'],'status':row['status'],'version':row['version'],'sourceSha256':row['source_sha256'],'canonicalSha256':row['canonical_sha256'],'baseVersionId':row['base_version_id'] or None,'baseRevision':row['base_revision'],'resultVersionId':row['result_version_id'] or None,'created':row['created']}
def editable(data):
    value={k:copy.deepcopy(data[k]) for k in ('name','system','expectedCount','cards','rightsReference','artReviewNote') if k in data}
    for c in value.get('cards',[]):
        if isinstance(c,dict):c.pop('mediaChecks',None)
    return value


class CardImportExportReply:
    def __init__(self,store,owner,session_hash,job_id):self.store,self.owner,self.session_hash,self.job_id=store,owner,session_hash,job_id
    def authorized(self,db):
        return db.execute("SELECT j.* FROM card_import_jobs j JOIN users u ON u.id=j.owner JOIN sessions s ON s.user_id=u.id WHERE j.id=? AND j.owner=? AND j.erased_at=0 AND u.role='admin' AND s.token=? AND s.expires>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)) AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')",(self.job_id,self.owner,self.session_hash)).fetchone()
    def send(self,h):
        h.require(('admin',))
        with self.store.connect() as db:
            row=self.authorized(db)
            if not row:return h.send(410,{'error':'import_erased_or_access_revoked'})
            if sha(row['raw_data'])!=row['source_sha256']:return h.send(409,{'error':'source_integrity_error'})
            summary=json.loads(row['preview_data'])['summary'];header={'type':'header','schema':1,'job':item(row),'summary':summary,'sourceSha256':row['source_sha256'],'canonicalSha256':row['canonical_sha256'],'rawByteCount':len(row['raw_data'].encode('utf-8')),'originalSourceBytesAvailable':True,'productionMaterialsVerifiedBySystem':False};source={'type':'source','rawText':row['raw_data'],'payload':json.loads(row['payload_data'])}
        h.send_response(200);h.send_header('Content-Type','application/x-ndjson; charset=utf-8');h.send_header('Cache-Control','private, no-store');h.send_header('Referrer-Policy','no-referrer');h.send_header('Content-Disposition','attachment; filename="card-import-'+self.job_id+'.ndjson"');h.send_header('Connection','close');h.end_headers();h.close_connection=True
        def line(value):return (canonical(value)+'\n').encode('utf-8')
        manifest=[];counts={'issues':0,'diff':0}
        try:
            h.wfile.write(line(header));h.wfile.write(line(source))
            for kind in ('issues','diff'):
                for ordinal in range((summary[kind]+49)//50):
                    with self.store.connect() as db:
                        if not self.authorized(db):h.wfile.write(line({'type':'error','code':'access_revoked','complete':False}));return
                        chunk=db.execute('SELECT data FROM card_import_diagnostics WHERE job_id=? AND owner=? AND kind=? AND ordinal=?',(self.job_id,self.owner,kind,ordinal)).fetchone()
                    if not chunk:h.wfile.write(line({'type':'error','code':'diagnostics_incomplete','complete':False}));return
                    values=decode_wire(json.loads(chunk[0]))
                    if not isinstance(values,list) or len(values)!=min(50,summary[kind]-ordinal*50):h.wfile.write(line({'type':'error','code':'diagnostics_incomplete','complete':False}));return
                    counts[kind]+=len(values);lines=[line({'type':'issue' if kind=='issues' else 'diff','index':ordinal*50+i,'item':value}) for i,value in enumerate(values)];m={'kind':kind,'ordinal':ordinal,'count':len(values),'sha256':sha(b''.join(lines))};manifest.append(m);h.wfile.write(line({'type':'chunk',**m,'hashFormat':'following-item-lines-utf8-lf'}))
                    for value in lines:h.wfile.write(value)
                    h.wfile.flush()
            with self.store.connect() as db:
                if not self.authorized(db):h.wfile.write(line({'type':'error','code':'access_revoked','complete':False}));return
            h.wfile.write(line({'type':'complete','complete':True,'issues':counts['issues'],'diff':counts['diff'],'chunkManifestSha256':sha(canonical(manifest))}));h.wfile.flush()
        except (OSError,BrokenPipeError):return

class CardImports:
    def __init__(self,store,h,error,limiter):self.store,self.h,self.Error,self.rate=store,h,error,limiter;self.owner=h.user['id'] if h.user else ''
    def fail(self,status,code):raise self.Error(status,code)
    def key(self,key):
        if not isinstance(key,str) or not re.fullmatch(r'[\x20-\x7e]{1,120}',key):self.fail(400,'invalid_request_id')
        return key
    def token(self):return sha(self.h.session_token)
    def guard(self,db,proof):
        self.h.require(('admin',))
        db.execute('INSERT INTO card_import_guards VALUES(?,?,?,?,?)',(str(uuid4()),self.owner,self.token(),canonical(proof),now()))
    def epoch(self,db):
        r=db.execute('SELECT revision FROM card_record_epochs WHERE owner=?',(self.owner,)).fetchone();return r[0] if r else 0
    def raw(self):
        if self.h.headers.get_content_type()!='application/json':self.fail(415,'json_required')
        try:n=int(self.h.headers.get('Content-Length','0'))
        except ValueError:self.fail(400,'invalid_length')
        if not 0<n<=262144:self.fail(413,'request_too_large')
        raw=self.h.rfile.read(n)
        try:text=raw.decode('utf-8',errors='strict')
        except UnicodeError:self.fail(400,'invalid_utf8')
        try:return raw,worker_call({'op':'parse','rawText':text})
        except WorkerError as e:self.fail(e.status,e.code)
    def body(self,keys):
        _,d=self.raw()
        if not isinstance(d,dict) or set(d)!=set(keys):self.fail(400,'invalid_fields')
        return d
    def owned(self,db,id):
        r=db.execute('SELECT * FROM card_import_jobs WHERE id=? AND owner=?',(id,self.owner)).fetchone()
        if not r:self.fail(404,'import_not_found')
        if r['erased_at']:self.fail(410,'import_erased')
        return r
    def page(self,total,row,kind,cursor):
        start=0
        if cursor:
            try:
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,1000}',cursor):raise ValueError()
                c=json.loads(base64.urlsafe_b64decode(cursor+'='*((-len(cursor))%4)).decode('utf-8'));start=c['offset']
                if set(c)!={'job','kind','sha','offset'} or c['job']!=row['id'] or c['kind']!=kind or c['sha']!=row['canonical_sha256'] or type(start) is not int or start<1 or start>=total or start%50:raise ValueError()
            except (ValueError,KeyError,TypeError):self.fail(400,'invalid_cursor')
        end=start+50;next=base64.urlsafe_b64encode(canonical({'job':row['id'],'kind':kind,'sha':row['canonical_sha256'],'offset':end}).encode()).decode().rstrip('=') if end<total else None
        return start,next
    def view(self,row,query=None,db=None):
        q=query or {}
        if db is None:
            with self.store.connect() as actual:return self.view(row,q,actual)
        p=json.loads(row['preview_data']);pages={}
        for kind in ('issues','diff'):
            start,nxt=self.page(p['summary'][kind],row,kind,q.get(kind+'Before',[''])[0]);chunk=db.execute('SELECT data FROM card_import_diagnostics WHERE job_id=? AND owner=? AND kind=? AND ordinal=?',(row['id'],self.owner,kind,start//50)).fetchone();pages[kind]=decode_wire(json.loads(chunk[0])) if chunk else [];pages[kind+'Next']=nxt
        frozen=json.loads(row['payload_data']);deck=frozen.get('deck');provenance=frozen.get('provenance');deck=deck if isinstance(deck,dict) else None;provenance=provenance if isinstance(provenance,dict) else {}
        target={'deckId':deck.get('deckId') if isinstance(deck.get('deckId'),str) else None,'version':deck.get('version') if type(deck.get('version')) in (int,float) else None,'environment':deck.get('environment') if isinstance(deck.get('environment'),str) else None} if deck is not None else None
        source={k:provenance.get(k) if isinstance(provenance.get(k),str) else None for k in ('sourceType','sourceReference','sourceDocumentSha256')};source['fieldSources']=len(provenance['fieldSources']) if isinstance(provenance.get('fieldSources'),list) else None
        return {'job':item(row),'summary':p['summary'],'target':target,'provenanceSummary':source,**pages,'productionMaterialsVerifiedBySystem':False}
    def full_report(self,db,row):
        r={'summary':json.loads(row['preview_data'])['summary']}
        for kind in ('issues','diff'):r[kind]=[v for chunk in db.execute('SELECT data FROM card_import_diagnostics WHERE job_id=? AND owner=? AND kind=? ORDER BY ordinal',(row['id'],self.owner,kind)) for v in decode_wire(json.loads(chunk[0]))]
        return r
    def inspect(self,db,payload,base,structured=True):
        try:r=worker_call({'op':'inspect','payload':payload,'baseData':editable(json.loads(base['data'])) if base else None}) if structured else {'payload':payload,'issues':[],'diff':[],'summary':{'cards':len(payload['deck']['data'].get('cards',[])),'diff':0}}
        except WorkerError as e:self.fail(e.status,e.code)
        retained={c.get(k,'') for c in json.loads(base['data']).get('cards',[]) for k in ('frontUrl','backUrl')} if base and base['status'] in ('reviewed','published') else set();media=[];courses=[]
        def issue(i,c,path,code):r['issues'].append({'cardId':c.get('id') if isinstance(c,dict) else None,'cardIndex':i,'language':None,'path':path,'code':code,'severity':'error','blocksApply':True,'blocksPublish':True,'message':code,'sourceReference':None})
        deck=payload.get('deck') if isinstance(payload,dict) else {};data=deck.get('data') if isinstance(deck,dict) else {};cards=data.get('cards',[]) if isinstance(data,dict) else []
        for i,c in enumerate(cards if isinstance(cards,list) else []):
            if not isinstance(c,dict):continue
            for k in ('frontUrl','backUrl'):
                url=c.get(k,'');path='/deck/data/cards/'+str(i)+'/'+k
                if not isinstance(url,str) or not url:continue
                match=re.fullmatch('/api/media/([a-f0-9-]{36})',url)
                if match:
                    m=db.execute('SELECT id,owner,mime FROM media WHERE id=?',(match[1],)).fetchone()
                    if not m or not m['mime'].startswith('image/'):issue(i,c,path,'invalid_image')
                    elif db.execute('SELECT 1 FROM privacy_media_tombstones WHERE media_id=? UNION ALL SELECT 1 FROM digital_sandbox_assets WHERE media_id=?',(m['id'],m['id'])).fetchone():issue(i,c,path,'media_unavailable')
                    elif m['owner']!=self.owner and url not in retained:issue(i,c,path,'media_owner_mismatch')
                    else:media.append(dict(m))
                else:
                    try:u=urlsplit(url);valid=u.scheme=='https' and u.hostname and not u.username and not u.password
                    except ValueError:valid=False
                    if not valid:issue(i,c,path,'invalid_image_url')
            course=c.get('courseId','')
            if isinstance(course,str) and course:
                if not db.execute("SELECT 1 FROM contents WHERE kind='courses' AND id=? AND status='published'",(course,)).fetchone():issue(i,c,'/deck/data/cards/'+str(i)+'/courseId','course_unavailable')
                else:courses.append(course)
        r['summary'].update(issues=len(r['issues']),errors=sum(i['severity']=='error' for i in r['issues']),warnings=sum(i['severity']=='warning' for i in r['issues']),applyBlocked=any(i['blocksApply'] for i in r['issues']),publishBlocked=any(i['blocksPublish'] for i in r['issues']))
        return r,media,courses,retained
    def preview(self):
        with self.store.connect() as initial:epoch=getattr(self,'request_epoch',self.epoch(initial))
        key=self.key(self.h.headers.get('X-EW-Request-ID'));raw,payload=self.raw();source=sha(raw)
        self.preview_replay=(key,source,epoch)
        with self.store.connect() as db:
            old=db.execute('SELECT * FROM card_import_jobs WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if old:
                if old['source_sha256']!=source:self.fail(409,'request_conflict')
                self.owned(db,old['id']);return self.view(old)
            base=None
            if isinstance(payload,dict) and isinstance(payload.get('baseVersionId'),str) and payload.get('baseVersionId'):
                base=db.execute('SELECT * FROM card_deck_versions WHERE id=?',(payload['baseVersionId'],)).fetchone()
                if not base:self.fail(404,'base_not_found')
            r,media,courses,_=self.inspect(db,payload,base);bid=payload.get('baseVersionId') if isinstance(payload.get('baseVersionId'),str) else None;br=payload.get('baseRevision') if type(payload.get('baseRevision')) is int else None
            deck=payload.get('deck')
            if base and (base['revision']!=br or isinstance(deck,dict) and (base['deck_id']!=deck.get('deckId') or base['environment']!=deck.get('environment'))):self.fail(409,'base_changed')
            stamp=now();identifier=str(uuid4());frozen=worker_call({'op':'canonical','payload':payload});db.execute('BEGIN IMMEDIATE');self.guard(db,{'epoch':epoch,**({'baseId':base['id'],'baseRevision':base['revision'],'baseData':base['data']} if base else {}),'media':media,'courses':courses})
            db.execute('INSERT INTO card_import_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)',(identifier,self.owner,key,source,sha(frozen),frozen,raw.decode('utf-8'),bid or '',br,base['data'] if base else '',epoch,canonical({'summary':r['summary']}),'preview',1,'',stamp,stamp))
            for kind in ('issues','diff'):
                for start in range(0,len(r[kind]),50):db.execute('INSERT INTO card_import_diagnostics VALUES(?,?,?,?,?)',(identifier,self.owner,kind,start//50,canonical(pack_wire(r[kind][start:start+50]))))
            return self.view(self.owned(db,identifier),db=db)
    def apply(self,identifier,d):
        if d.get('confirmed') is not True or type(d.get('version')) is not int:self.fail(400,'confirmation_required')
        key=self.key(d['requestId']);fp=sha(canonical({'jobId':identifier,'version':d['version'],'confirmed':True}))
        with self.store.connect() as db:
            row=self.owned(db,identifier);self.replay_request=('card_import_receipts',key,fp,row['epoch']);old=db.execute('SELECT * FROM card_import_receipts WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if old:
                if old['fingerprint']!=fp:self.fail(409,'request_conflict')
                return json.loads(old['result_data'])
            if row['result_version_id']:
                old=db.execute('SELECT result_data FROM card_import_receipts WHERE job_id=? ORDER BY created,id LIMIT 1',(identifier,)).fetchone();db.execute('BEGIN IMMEDIATE');self.guard(db,{'epoch':row['epoch']});db.execute('INSERT INTO card_import_receipts VALUES(?,?,?,?,?,?,?)',(str(uuid4()),self.owner,identifier,key,fp,old[0],now()));return json.loads(old[0])
            if row['version']!=d['version']:self.fail(409,'import_changed')
            payload=json.loads(row['payload_data']);base=db.execute('SELECT * FROM card_deck_versions WHERE id=?',(row['base_version_id'],)).fetchone() if row['base_version_id'] else None
            if row['base_version_id'] and (not base or base['revision']!=row['base_revision'] or base['data']!=row['base_data']):self.fail(409,'base_changed')
            r,media,courses,retained=self.inspect(db,payload,base)
            if r['summary']['applyBlocked']:self.fail(409,'import_blocked')
            from card_service import CardService
            service=CardService(self.store,self.h,self.Error,self.rate);deck=payload['deck'];clean=service.clean_deck(db,deck['data'],retained);clean['review']={'status':'pending','reviewerId':None,'reference':'','notes':'','reviewedAt':None};vid=str(uuid4());stamp=now()
            db.execute('BEGIN IMMEDIATE')
            self.guard(db,{'epoch':row['epoch'],'jobId':identifier,'version':row['version'],'status':'preview','nextVersion':deck['version'],'deckId':deck['deckId'],'environment':deck['environment'],'media':media,'courses':courses,**({'baseId':base['id'],'baseRevision':base['revision'],'baseData':base['data']} if base else {})})
            db.execute('INSERT INTO card_deck_versions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(vid,deck['deckId'],deck['version'],deck['environment'],'draft',1,canonical(clean),'','',stamp,stamp));sid=str(uuid4());db.execute('INSERT INTO card_deck_sources VALUES(?,?,?,?,?,?)',(sid,self.owner,vid,canonical(payload['provenance']),sha(canonical(payload['provenance'])),stamp));db.execute("UPDATE card_import_jobs SET status='applied',version=version+1,result_version_id=?,updated=? WHERE id=? AND version=?",(vid,stamp,identifier,row['version']))
            receipt={'id':str(uuid4()),'jobId':identifier,'actor':self.owner,'requestId':key,'status':'applied','sourceSha256':row['source_sha256'],'canonicalSha256':row['canonical_sha256'],'baseVersionId':row['base_version_id'] or None,'createdDeckVersionId':vid,'createdRevision':1,'counts':r['summary'],'created':stamp};response={'job':item(self.owned(db,identifier)),'item':service.deck_item(service.deck(db,vid)),'receipt':receipt};db.execute('INSERT INTO card_import_receipts VALUES(?,?,?,?,?,?,?)',(receipt['id'],self.owner,identifier,key,fp,canonical(response),stamp));self.guard(db,{'epoch':row['epoch'],'jobId':identifier,'version':row['version']+1,'status':'applied'});return response
    def activation(self,db,d,override=None):
        from card_service import CardService,configuration
        s=CardService(self.store,self.h,self.Error,self.rate);cfg=override or configuration(self.store);env=d.get('environment');target=d.get('targetVersionId');blocked=[];media=[];courses=[];row=None
        if env not in ('sandbox','production') or not isinstance(target,str) or type(d.get('revision')) is not int:self.fail(400,'invalid_activation')
        if cfg['revision']!=d['revision']:self.fail(409,'config_changed')
        if target:
            row=db.execute('SELECT * FROM card_deck_versions WHERE id=?',(target,)).fetchone()
            if not row or row['status']!='published' or row['environment']!=env:blocked.append('target_not_published')
            else:
                data=json.loads(row['data']);rules=cfg[env+'Rules']
                if not s.ready_rules(rules) or data.get('expectedCount')!=rules['expectedCount'] or data.get('review',{}).get('status')!='approved':blocked.append('rules_or_review_unready')
                payload={'schema':1,'deck':{'deckId':row['deck_id'],'version':row['version'],'environment':env,'data':editable(data)},'baseVersionId':row['id'],'baseRevision':row['revision'],'provenance':{'sourceType':'author_submitted','sourceReference':'Existing published version, no new rights declaration','sourceDocumentSha256':None,'fieldSources':[]}}
                facts,media,courses,_=self.inspect(db,payload,row,structured=False)
                if facts['summary']['applyBlocked']:blocked.append('materials_unavailable')
                try:s.clean_deck(db,editable(data),[c.get(k,'') for c in data['cards'] for k in ('frontUrl','backUrl')],True)
                except self.Error:blocked.append('materials_unavailable')
                if env=='production' and any(c.get('sandboxOnly') for c in data.get('cards',[])):blocked.append('sandbox_materials')
        return {'from':cfg['activeSandboxDeck' if env=='sandbox' else 'activeProductionDeck'],'to':target,'eligible':not blocked,'blockedReasons':blocked,'currentRevision':cfg['revision']},cfg,row,media,courses
    def activate(self,d):
        if d.get('confirmed') is not True or d.get('kind') not in ('activate','rollback') or not isinstance(d.get('reason'),str) or not 1<=len(d['reason'])<=2000 or not d.get('targetVersionId') and d['kind']!='activate':self.fail(400,'invalid_activation')
        with self.store.connect() as initial:captured_epoch=getattr(self,'request_epoch',self.epoch(initial))
        key=self.key(d['requestId']);fp=sha(canonical({k:v for k,v in d.items() if k!='requestId'}))
        self.replay_request=('card_deck_activation_events',key,fp,captured_epoch)
        with self.store.connect() as db:
            old=db.execute('SELECT * FROM card_deck_activation_events WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if old:
                if old['fingerprint']!=fp:self.fail(409,'request_conflict')
                return json.loads(old['result_data'])
            view,cfg,row,media,courses=self.activation(db,d)
            if not view['eligible']:self.fail(409,'activation_blocked')
            old_data=db.execute("SELECT data FROM settings WHERE key='card_service'").fetchone();db.execute('BEGIN IMMEDIATE');self.guard(db,{'epoch':captured_epoch,'configData':old_data[0] if old_data else '{}','media':media,'courses':courses,**({'targetId':row['id'],'targetRevision':row['revision'],'targetData':row['data'],'environment':d['environment']} if row else {})});cfg['activeSandboxDeck' if d['environment']=='sandbox' else 'activeProductionDeck']=d['targetVersionId'];cfg['revision']+=1;db.execute("INSERT INTO settings VALUES('card_service',?) ON CONFLICT(key) DO UPDATE SET data=excluded.data",(canonical(cfg),));receipt={'id':str(uuid4()),'actor':self.owner,'requestId':key,'kind':d['kind'],'environment':d['environment'],'from':view['from'],'to':view['to'],'configRevision':cfg['revision'],'reason':d['reason'],'created':now()};response={'config':cfg,'receipt':receipt};db.execute('INSERT INTO card_deck_activation_events VALUES(?,?,?,?,?,?)',(receipt['id'],self.owner,key,fp,canonical(response),receipt['created']));return response
    def dispatch(self,method,path):
        if not (path.startswith('/api/admin/cards/imports') or path.startswith('/api/admin/cards/activation')):return None
        self.h.require(('admin',))
        if method!='GET':
            with self.store.connect() as initial:self.request_epoch=self.epoch(initial)
        self.rate(('card-import-read:' if method=='GET' else 'card-import-write:')+self.owner,180 if method=='GET' else 30);q=parse_qs(urlsplit(self.h.path).query)
        try:
            if path=='/api/admin/cards/imports/preview' and method=='POST':return self.preview()
            if path=='/api/admin/cards/imports' and method=='GET':
                with self.store.connect() as db:
                    args=[self.owner];where='owner=?';before=q.get('before',[''])[0]
                    if before:
                        old=db.execute('SELECT created,id FROM card_import_jobs WHERE owner=? AND id=?',(self.owner,before)).fetchone()
                        if not old:self.fail(400,'invalid_cursor')
                        where+=' AND (created,id)<(?,?)';args.extend(old)
                    rows=db.execute('SELECT * FROM card_import_jobs WHERE '+where+' ORDER BY created DESC,id DESC LIMIT 51',args).fetchall();return {'items':[item(r) for r in rows[:50]],'next':rows[49]['id'] if len(rows)>50 else None}
            m=re.fullmatch(r'/api/admin/cards/imports/([A-Za-z0-9_-]{1,100})(/(?:apply|export))?',path)
            if m:
                id,action=m.groups()
                if action=='/apply' and method=='POST':return self.apply(id,self.body(['requestId','confirmed','version']))
                if method=='GET':
                    with self.store.connect() as db:
                        row=self.owned(db,id);receipt=db.execute('SELECT result_data FROM card_import_receipts WHERE job_id=?',(id,)).fetchone()
                        if action=='/export':return CardImportExportReply(self.store,self.owner,self.token(),row['id'])
                        if action is None:return {**self.view(row,q),'receipt':json.loads(receipt[0])['receipt'] if receipt else None}
            if path=='/api/admin/cards/activation/preview' and method=='POST':
                with self.store.connect() as db:return self.activation(db,self.body(['environment','targetVersionId','revision']))[0]
            if path=='/api/admin/cards/activation/apply' and method=='POST':return self.activate(self.body(['requestId','confirmed','environment','targetVersionId','revision','reason','kind']))
            self.fail(404,'not_found')
        except WorkerError as e:self.fail(e.status,e.code)
        except sqlite3.IntegrityError as e:
            if getattr(self,'preview_replay',None):
                key,source,epoch=self.preview_replay
                with self.store.connect() as db:
                    row=db.execute('SELECT * FROM card_import_jobs WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
                    if row and row['source_sha256']==source:
                        self.guard(db,{'epoch':epoch});self.owned(db,row['id']);return self.view(row)
            if getattr(self,'replay_request',None):
                table,key,fp,epoch=self.replay_request
                with self.store.connect() as db:
                    row=db.execute('SELECT * FROM '+table+' WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
                    if row and row['fingerprint']==fp:
                        self.guard(db,{'epoch':epoch});return json.loads(row['result_data'])
            if any(k in str(e) for k in ('card_import','card_deck','card_activation','card_withdrawal')):self.fail(409,'card_import_changed')
            raise


    def route(self,method,path):
        result=self.dispatch(method,path)
        if result is not None:self.h.require(('admin',))
        return result


def configuration_admission(db,service,prior,next):
    """Called inside the original configuration transaction; no config write or commit."""
    imports=CardImports(service.store,service.h,service.Error,service.rate)
    raw=db.execute("SELECT data FROM settings WHERE key='card_service'").fetchone()
    for env,key in [('sandbox','activeSandboxDeck'),('production','activeProductionDeck')]:
        if prior[key]==next[key]:continue
        proposal={**next,'revision':prior['revision']}
        view,cfg,target,media,courses=imports.activation(db,{'environment':env,'targetVersionId':next[key],'revision':prior['revision']},proposal)
        if not view['eligible']:imports.fail(409,'activation_blocked')
        imports.guard(db,{'epoch':imports.epoch(db),**({'configData':raw[0]} if raw else {}),'media':media,'courses':courses,**({'targetId':target['id'],'targetRevision':target['revision'],'targetData':target['data'],'environment':env} if target else {})})
        stamp=now();identifier=str(uuid4());request=str(uuid4());receipt={'id':identifier,'actor':imports.owner,'requestId':request,'kind':'activate','environment':env,'from':prior[key],'to':next[key],'configRevision':next['revision'],'reason':'Explicit active-pointer change through the existing configuration endpoint','created':stamp}
        db.execute('INSERT INTO card_deck_activation_events VALUES(?,?,?,?,?,?)',(identifier,imports.owner,request,sha(canonical({'from':receipt['from'],'to':receipt['to'],'revision':next['revision']})),canonical({'receipt':receipt}),stamp))
