"""Owner-selected legacy examples. These archives are never authoritative draws."""
import base64
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

HERE=Path(__file__).resolve().parent
TABLES=['card_history_migration_'+s for s in ('jobs','targets','receipts','operations','guards')]+['card_legacy_archives']
REFERENCE_FIELDS=[('card_history_migration_jobs','data'),('card_history_migration_jobs','source_reference'),('card_history_migration_targets','record_data'),('card_legacy_archives','record_data'),('card_legacy_archives','note'),('card_history_migration_receipts','data'),('card_history_migration_operations','response_data')]
MISSING=['deckVersion','rulesVersion','timezone','originalCardText']
def now():return time.time_ns()//1_000_000
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(v):return hashlib.sha256(v if isinstance(v,bytes) else v.encode('utf-8')).hexdigest()
def init_schema(db):db.executescript((HERE/'card_history_migration_schema.sql').read_text(encoding='utf-8'))
def privacy_registry():return {t:('privacyAndSourceAudits','r.owner=?') for t in TABLES}
EXPORTS={
 'cardLegacyMigrationJobs':('card_history_migration_jobs','id,request_id,status,version,epoch,source_sha256,canonical_sha256,source_reference,data,total,added,duplicate,skipped_changed,protected,missing,undone,not_applied,undo_started,created,updated,erased_at'),
 'cardLegacyMigrationTargets':('card_history_migration_targets','id,job_id,ordinal,source_id,source_hash,record_data,status,archive_id,reason,created,updated'),
 'cardLegacyArchives':('card_legacy_archives','id,source_id,original_hash,record_data,created_job_id,note,favorite,revision,created,updated'),
 'cardLegacyMigrationReceipts':('card_history_migration_receipts','id,job_id,action,version_before,version_after,data,created'),
 'cardLegacyMigrationOperations':('card_history_migration_operations','job_id,request_id,action,fingerprint,receipt_id,created')}
def privacy_export(db,owner):return {k:[dict(r) for r in db.execute('SELECT '+cols+' FROM '+table+' WHERE owner=?',(owner,))] for k,(table,cols) in EXPORTS.items()}
def privacy_delete_records(db,owner):
    # Caller has already increased the real card erasure epoch, in this same transaction.
    counts={}
    for table in ('card_legacy_archives','card_history_migration_targets'):counts[table]=db.execute('DELETE FROM '+table+' WHERE owner=?',(owner,)).rowcount
    counts['card_history_migration_jobs']=db.execute("UPDATE card_history_migration_jobs SET data='{}',source_reference='',status='erased',erased_at=?,version=version+1,updated=? WHERE owner=? AND erased_at=0",(now(),now(),owner)).rowcount
    counts['card_history_migration_receipts']=db.execute("UPDATE card_history_migration_receipts SET data='{}' WHERE owner=? AND data!='{}'",(owner,)).rowcount
    counts['card_history_migration_operations']=db.execute("UPDATE card_history_migration_operations SET response_data='{}' WHERE owner=? AND response_data!='{}'",(owner,)).rowcount
    return {'deletedCounts':counts,'retentionDays':None,'secureWipe':False,'retained':['minimal-source-hashes-and-processing-counts']}

def cursor_encode(value):return base64.urlsafe_b64encode(canonical(value).encode()).rstrip(b'=').decode()
def cursor_decode(value,fail):
    try:
        if not isinstance(value,str) or not 1<=len(value)<=2000 or not re.fullmatch('[A-Za-z0-9_-]+',value):raise ValueError()
        result=json.loads(base64.urlsafe_b64decode(value+'='*((-len(value))%4)).decode('utf-8'))
        if not isinstance(result,dict):raise ValueError()
        return result
    except (ValueError,UnicodeError):fail(400,'invalid_cursor')
def epoch(db,owner):
    row=db.execute('SELECT revision FROM card_record_epochs WHERE owner=?',(owner,)).fetchone();return row[0] if row else 0
def paged(db,table,owner,before,fail,kind,where='',args=()):
    e=epoch(db,owner);scope=sha(owner+'|'+kind);clause='owner=?'+(' AND '+where if where else '');values=(owner,*args)
    upper=db.execute('SELECT created,id FROM '+table+' WHERE '+clause+' ORDER BY created DESC,id DESC LIMIT 1',values).fetchone()
    if before:
        c=cursor_decode(before,fail)
        if set(c)!={'scope','epoch','upper','position'} or c['scope']!=scope or c['epoch']!=e or any(not isinstance(c[k],list) or len(c[k])!=2 or type(c[k][0]) is not int or not isinstance(c[k][1],str) for k in ('upper','position')):fail(400,'invalid_cursor')
        for anchor in (c['upper'],c['position']):
            if not db.execute('SELECT 1 FROM '+table+' WHERE '+clause+' AND created=? AND id=?',(*values,*anchor)).fetchone():fail(400,'invalid_cursor')
        upper=c['upper'];clause+=' AND (created<? OR(created=? AND id<?))';values=(*values,c['position'][0],*c['position'])
    else:c={'scope':scope,'epoch':e,'upper':list(upper) if upper else None}
    if not upper:return [],None
    clause+=' AND (created<? OR(created=? AND id<=?))';values=(*values,upper[0],*upper)
    found=db.execute('SELECT * FROM '+table+' WHERE '+clause+' ORDER BY created DESC,id DESC LIMIT 51',values).fetchall()
    nxt=cursor_encode({**c,'position':[found[49]['created'],found[49]['id']]}) if len(found)>50 else None
    return found[:50],nxt
def draw_history_page(db,owner,environment,before,fail):
    rows,nxt=paged(db,'card_draws',owner,before,fail,'draws:'+environment,'environment=?',(environment,));return {'rows':rows,'next':nxt}

def summary(db,j):
    pending=db.execute("SELECT count(*) FROM card_history_migration_targets WHERE job_id=? AND status='pending'",(j['id'],)).fetchone()[0]
    undo=db.execute("SELECT count(*) FROM card_history_migration_targets WHERE job_id=? AND status IN('pending','added','duplicate')",(j['id'],)).fetchone()[0] if j['undo_started'] else 0
    return {'total':j['total'],'added':j['added'],'duplicate':j['duplicate'],'skippedChanged':j['skipped_changed'],'protected':j['protected'],'missing':j['missing'],'remaining':pending,'undoRemaining':undo}
def job_item(db,j):return {'id':j['id'],'status':j['status'],'version':j['version'],'sourceSha256':j['source_sha256'],'canonicalSha256':j['canonical_sha256'],'summary':summary(db,j),'created':j['created'],'updated':j['updated']}
def archive_item(r):return {'id':r['id'],'record':json.loads(r['record_data']),'sourceType':'legacy_local_example','authoritative':False,'contentReviewed':False,'factsMissing':MISSING,'note':r['note'],'favorite':bool(r['favorite']),'revision':r['revision'],'created':r['created'],'updated':r['updated']}
def receipt_item(r):return {'id':r['id'],'jobId':r['job_id'],'action':r['action'],'versionBefore':r['version_before'],'versionAfter':r['version_after'],'counts':json.loads(r['data']),'created':r['created']}

class CardHistoryMigration:
    def __init__(self,store,h,error,limiter):self.store,self.h,self.Error,self.rate=store,h,error,limiter;self.owner=h.user['id'] if h.user else ''
    def fail(self,status,code):raise self.Error(status,code)
    def key(self,v):
        if not isinstance(v,str) or not re.fullmatch(r'[\x20-\x7e]{1,120}',v):self.fail(400,'invalid_request_id')
        return v
    def raw(self):
        if self.h.headers.get_content_type()!='application/json':self.fail(415,'json_required')
        try:size=int(self.h.headers.get('Content-Length','0'))
        except ValueError:self.fail(400,'invalid_length')
        if not 0<size<=262144:self.fail(413,'migration_file_too_large')
        raw=self.h.rfile.read(size)
        if len(raw)!=size:self.fail(400,'invalid_length')
        try:text=raw.decode('utf-8',errors='strict')
        except UnicodeError:self.fail(400,'invalid_utf8')
        from card_imports import worker_call
        value=worker_call({'op':'parse','rawText':text})
        if not isinstance(value,dict):self.fail(400,'invalid_fields')
        return raw,value
    def guard(self,db,resource,version,action,key='',fp='',e=None):
        self.h.require();ident=str(uuid4());db.execute('INSERT INTO card_history_migration_guards VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,self.owner,sha(self.h.session_token),epoch(db,self.owner) if e is None else e,resource,version,action,key,fp,now()));return ident
    def owned(self,db,table,ident):
        row=db.execute('SELECT * FROM '+table+' WHERE id=? AND owner=?',(ident,self.owner)).fetchone()
        if not row:self.fail(404,'legacy_record_not_found')
        if 'erased_at' in row.keys() and row['erased_at']:self.fail(410,'legacy_migration_erased')
        return row
    def view(self,db,j,q):
        after=-1
        if q.get('before',[''])[0]:
            c=cursor_decode(q['before'][0],self.fail)
            if set(c)!={'scope','epoch','position','upper'} or c['scope']!=sha(self.owner+'|targets:'+j['id']) or c['epoch']!=j['epoch'] or c['upper']!=j['total']-1 or type(c['position']) is not int or not 0<=c['position']<j['total']:self.fail(400,'invalid_cursor')
            after=c['position']
        found=db.execute('SELECT * FROM card_history_migration_targets WHERE owner=? AND job_id=? AND ordinal>? ORDER BY ordinal LIMIT 51',(self.owner,j['id'],after)).fetchall()
        nxt=cursor_encode({'scope':sha(self.owner+'|targets:'+j['id']),'epoch':j['epoch'],'position':found[49]['ordinal'],'upper':j['total']-1}) if len(found)>50 else None
        receipts,rn=paged(db,'card_history_migration_receipts',self.owner,q.get('receiptsBefore',[''])[0],self.fail,'receipts:'+j['id'],'job_id=?',(j['id'],))
        item=job_item(db,j)
        planned=db.execute('SELECT count(DISTINCT source_id) FROM card_history_migration_targets t WHERE t.job_id=? AND t.owner=? AND NOT EXISTS(SELECT 1 FROM card_legacy_archives a WHERE a.owner=t.owner AND a.source_id=t.source_id)',(j['id'],self.owner)).fetchone()[0]
        return {'job':item,'summary':item['summary'],'previewPlan':{'newRecords':planned,'duplicates':j['total']-planned,'currentEstimate':True} if j['status']=='preview' else None,'targets':[{'id':r['id'],'ordinal':r['ordinal'],'sourceId':r['source_id'],'sourceHash':r['source_hash'],'record':json.loads(r['record_data']),'status':r['status'],'archiveId':r['archive_id'] or None,'reasonCode':r['reason']} for r in found[:50]],'next':nxt,'receipts':[receipt_item(r) for r in receipts],'receiptsNext':rn,'authoritative':False,'contentReviewed':False}
    def preview(self):
        key=self.key(self.h.headers.get('X-EW-Request-ID'))
        with self.store.connect() as db:e=epoch(db,self.owner)
        raw,d=self.raw()
        if set(d)!={'schema','sourceReference','records'} or type(d['schema']) is not int or d['schema']!=1 or not isinstance(d['sourceReference'],str) or not 1<=len(d['sourceReference'])<=2000 or not isinstance(d['records'],list) or not 1<=len(d['records'])<=1000:self.fail(400,'invalid_legacy_file')
        for r in d['records']:
            if not isinstance(r,dict) or set(r)!={'cardId','date','drawnAt'} or not isinstance(r['cardId'],str) or not re.fullmatch(r'[\x20-\x7e]{1,100}',r['cardId']) or not isinstance(r['date'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',r['date']) or type(r['drawnAt']) is not int or not 0<=r['drawnAt']<=9007199254740991:self.fail(400,'invalid_legacy_record')
            try:date.fromisoformat(r['date'])
            except ValueError:self.fail(400,'invalid_legacy_record')
        source=sha(raw);identifier=str(uuid4());stamp=now()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');guard=self.guard(db,identifier,0,'preview',key,source,e)
            old=db.execute('SELECT * FROM card_history_migration_jobs WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if old:
                if old['erased_at']:self.fail(410,'legacy_migration_erased')
                if old['source_sha256']!=source:self.fail(409,'request_conflict')
                db.execute('DELETE FROM card_history_migration_guards WHERE id=?',(guard,));return self.view(db,old,{})
            db.execute("INSERT INTO card_history_migration_jobs(id,owner,request_id,status,version,epoch,source_sha256,canonical_sha256,source_reference,data,total,created,updated) VALUES(?,?,?,'preview',1,?,?,?,?,?,?,?,?)",(identifier,self.owner,key,e,source,sha(canonical(d)),d['sourceReference'],canonical(d),len(d['records']),stamp,stamp))
            for i,r in enumerate(d['records']):
                encoded=canonical(r);source_id=sha(encoded);db.execute("INSERT INTO card_history_migration_targets(id,owner,job_id,ordinal,source_id,source_hash,record_data,status,created,updated) VALUES(?,?,?,?,?,?,?,'pending',?,?)",(str(uuid4()),self.owner,identifier,i,source_id,source_id,encoded,stamp,stamp))
            db.execute('DELETE FROM card_history_migration_guards WHERE id=?',(guard,));return self.view(db,self.owned(db,'card_history_migration_jobs',identifier),{})
    def operation(self,db,key,fp):
        row=db.execute('SELECT * FROM card_history_migration_operations WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
        if not row:return None
        if row['fingerprint']!=fp:self.fail(409,'request_conflict')
        value=json.loads(row['response_data'])
        if not value:self.fail(410,'legacy_migration_erased')
        value['job']['summary']=value['summary'];return value
    def process(self,identifier,action):
        _,d=self.raw()
        if set(d)!={'requestId','confirmed','version'} or d['confirmed'] is not True or type(d['version']) is not int or d['version']<1:self.fail(400,'invalid_confirmation')
        key=self.key(d['requestId']);fp=sha(canonical({'jobId':identifier,'action':action,**d}))
        try:
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE');self.h.require();j=self.owned(db,'card_history_migration_jobs',identifier);old=self.operation(db,key,fp)
                if old:return old
                self.guard(db,identifier,d['version'],action,key,fp,j['epoch']);self.guard(db,identifier,d['version']+1,'finish',key,fp,j['epoch'])
                return self.operation(db,key,fp)
        except sqlite3.IntegrityError:
            with self.store.connect() as db:
                self.h.require();old=self.operation(db,key,fp)
                if old:return old
            raise
    def route(self,method,path):
        base='/api/cards/legacy-migrations';archives='/api/cards/legacy-archives'
        if not(path==base or path.startswith(base+'/') or path==archives or path.startswith(archives+'/')):return None
        self.h.require();self.rate(('card-legacy-read:' if method=='GET' else 'card-legacy-write:')+self.owner,180 if method=='GET' else 40)
        from card_imports import WorkerError
        try:
            result=self.dispatch(method,path,base,archives);self.h.require();return result
        except WorkerError as error:self.fail(error.status,error.code)
        except sqlite3.IntegrityError as error:
            match=re.search(r'card_history_[a-z_]+',str(error))
            if match:self.fail(409,match[0])
            raise
    def dispatch(self,method,path,base,archives):
        q=parse_qs(urlsplit(self.h.path).query);before=q.get('before',[''])[0]
        if path==base+'/preview' and method=='POST':return self.preview()
        suffix=path[len(base):] if path.startswith(base) else path[len(archives):];parts=[unquote(p) for p in suffix.strip('/').split('/') if p]
        if any(not re.fullmatch('[A-Za-z0-9:_-]{1,120}',p) for p in parts):self.fail(400,'invalid_resource_id')
        if path.startswith(base) and len(parts)==2 and parts[1] in ('apply','undo') and method=='POST':return self.process(parts[0],parts[1])
        if path.startswith(archives) and len(parts)==1 and method=='PATCH':
            _,d=self.raw()
            if set(d)-{'revision','note','favorite'} or type(d.get('revision')) is not int or len(d)<2 or 'favorite' in d and type(d['favorite']) is not bool or 'note' in d and (not isinstance(d['note'],str) or len(d['note'])>2000):self.fail(400,'invalid_legacy_action')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE');r=self.owned(db,'card_legacy_archives',parts[0]);guard=self.guard(db,r['id'],d['revision'],'edit',e=r['epoch']);db.execute('UPDATE card_legacy_archives SET note=?,favorite=?,revision=revision+1,updated=? WHERE id=? AND owner=? AND revision=?',(d.get('note',r['note']),int(d.get('favorite',r['favorite'])),now(),r['id'],self.owner,d['revision']));db.execute('DELETE FROM card_history_migration_guards WHERE id=?',(guard,));return {'item':archive_item(self.owned(db,'card_legacy_archives',r['id']))}
        if method!='GET':self.fail(405,'method_not_allowed')
        with self.store.connect() as db:
            if path==archives:
                found,nxt=paged(db,'card_legacy_archives',self.owner,before,self.fail,'archives');return {'items':[archive_item(r) for r in found],'next':nxt}
            if path==base:
                found,nxt=paged(db,'card_history_migration_jobs',self.owner,before,self.fail,'jobs','erased_at=0');return {'items':[job_item(db,r) for r in found],'next':nxt}
            if path.startswith(base) and len(parts)==1:return self.view(db,self.owned(db,'card_history_migration_jobs',parts[0]),q)
        self.fail(404,'legacy_record_not_found')
