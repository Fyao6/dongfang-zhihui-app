"""Private sample comparisons, using only the managed, actual calculation worker.

Evidence is synthetic/unverified; a successful comparison is not teacher approval.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

HERE=Path(__file__).resolve().parent
SCHEMA=HERE/'bazi_samples_schema.sql'
NOW="(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))"
NODE=shutil.which('node')
WORKER=HERE/'bazi_sample_worker.cjs'
SLOTS=threading.BoundedSemaphore(2)
TABLES=['bazi_sample_'+s for s in ('owner_state','sets','versions','cases','runs','workitems','results','raw_chunks','field_results','reviews','operations','erase_guards')]
COUNTS=dict.fromkeys(('equal','different','notCovered','notApplicable','blocked','provided','total'),0)

def now():return time.time_ns()//1_000_000
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(v):return hashlib.sha256(v if isinstance(v,bytes) else v.encode('utf-8')).hexdigest()
def init_schema(db):db.executescript(SCHEMA.read_text(encoding='utf-8'))
def privacy_registry():return {t:('privacyAndSourceAudits','r.owner=?') for t in TABLES}

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
        readers=[threading.Thread(target=read,args=(process.stdout,0,4*1024*1024),daemon=True),threading.Thread(target=read,args=(process.stderr,1,65536),daemon=True)]
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
        return value['result']
    except (OSError,BrokenPipeError):raise WorkerError('adapter_unavailable') from None
    finally:
        if process:
            if process.poll() is None:process.kill();process.wait()
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream and not stream.closed:stream.close()
        SLOTS.release()

def erase(db,owner,source,receipt_id,stamp):
    old=db.execute("SELECT response_data FROM bazi_sample_operations WHERE owner=? AND kind='erase' AND request_id=?",(owner,receipt_id)).fetchone()
    if old:return json.loads(old[0])
    epoch=db.execute('SELECT epoch FROM bazi_sample_owner_state WHERE owner=?',(owner,)).fetchone()
    db.execute('INSERT INTO bazi_sample_erase_guards VALUES(?,?,?,?,?,?)',(str(uuid4()),owner,epoch[0] if epoch else 1,source,receipt_id,stamp))
    return json.loads(db.execute("SELECT response_data FROM bazi_sample_operations WHERE owner=? AND kind='erase' AND request_id=?",(owner,receipt_id)).fetchone()[0])

def redact_names(value):
    data=copy.deepcopy(value);paths=[]
    def field(f,path):
        if f.get('path') in ('/originalInput/name','/normalizedInput/birth/name'):
            for key in ('expected','actual'):
                if key in f:f[key]=None;paths.append(path+'/'+key)
    def expectation(e,path):
        if not isinstance(e,dict):return
        for key in ('/originalInput/name','/normalizedInput/birth/name'):
            if key in e and 'value' in e[key]:e[key]['value']=None;paths.append(path+'/'+key+'/value')
    if isinstance(data,dict):
        for container,path in [(data,'')]+([(data.get('sampleCase'),'/sampleCase')] if isinstance(data.get('sampleCase'),dict) else []):
            if isinstance(container.get('input'),dict) and 'name' in container['input']:del container['input']['name'];paths.append(path+'/input/name')
            expectation(container.get('expected'),path+'/expected')
        report=data.get('report',data);stages=report.get('stages',{})
        for obj,path in [(stages.get('originalInput'),'/stages/originalInput/name'),((stages.get('normalizedInput') or {}).get('birth'),'/stages/normalizedInput/birth/name')]:
            if isinstance(obj,dict) and 'name' in obj:del obj['name'];paths.append(path)
        expectation(report.get('expectations'),'/expectations')
        for i,f in enumerate(report.get('fieldResults',[])):field(f,'/fieldResults/'+str(i))
        field(data,'')
    return data,paths

def export_metadata(db,owner,include_names=False):
    # Explicit allowlists, including all private sample bodies, excluding lease/session proofs.
    cols={'Sets':'id,set_key,title,created,updated','Versions':'id,set_id,version_key,source_sha256,source_bytes,canonical_sha256,canonical_bytes,case_order,data,created,erased_at',
      'Cases':'version_id,case_id,ordinal,data,canonical_sha256,canonical_bytes,created','Runs':'id,version_id,request_id,case_ids,manifest_data,manifest_hash,state,version,total,processed,succeeded,failed,blocked,counts,created,updated,erased_at',
      'Results':'id,run_id,case_id,status,error_code,data,raw_index,created','RawChunks':'id,result_id,section,period_index,chunk_index,data,sha256,byte_length,created',
      'FieldResults':'id,result_id,path,data,created','Reviews':'id,result_id,field_id,category,evidence,note,retest_run_id,created','OwnerState':'epoch,updated'}
    suffix={'Sets':'sets','Versions':'versions','Cases':'cases','Runs':'runs','Results':'results','RawChunks':'raw_chunks','FieldResults':'field_results','Reviews':'reviews','OwnerState':'owner_state'}
    result={'baziSample'+key:[dict(r) for r in db.execute('SELECT '+columns+' FROM bazi_sample_'+suffix[key]+' WHERE owner=?',(owner,))] for key,columns in cols.items()}
    if not include_names:
        for key in ('baziSampleCases','baziSampleResults','baziSampleFieldResults'):
            for row in result[key]:row['data']=canonical(redact_names(json.loads(row['data']))[0])
    result['baziSampleExportPrivacy']={'includesPrivateNames':include_names,'knownNameFieldsRedacted':not include_names,'freeTextAnonymized':False,'originalSourceBytesAvailable':False}
    return result

def version_item(row):
    data=json.loads(row['data']);return {'id':row['id'],'setId':row['set_id'],'setKey':data.get('setId',''),'version':data.get('version',''),'title':data.get('title',''),
      'caseCount':len(json.loads(row['case_order'])),'sourceBytesSha256':row['source_sha256'],'sourceByteLength':row['source_bytes'],'canonicalSha256':row['canonical_sha256'],'canonicalByteLength':row['canonical_bytes'],'created':row['created'],'erased':bool(row['erased_at']),'teacherConfirmed':False}
def run_item(row):
    return {'id':row['id'],'setVersionId':row['version_id'],'state':row['state'],'version':row['version'],'total':row['total'],'processed':row['processed'],'succeeded':row['succeeded'],'failed':row['failed'],'blocked':row['blocked'],'manifestHash':row['manifest_hash'],'manifest':json.loads(row['manifest_data']),'counts':{**json.loads(row['counts']),'teacherAgreementRate':None},'created':row['created'],'updated':row['updated'],'teacherConfirmed':False,'professionalValidation':False}
def pointer(value,path):
    try:
        for key in path.strip('/').split('/'):
            key=key.replace('~1','/').replace('~0','~');value=value[int(key)] if isinstance(value,list) else value[key]
        return value,True
    except (KeyError,IndexError,ValueError,TypeError):return None,False
def chunks(text):
    # Character boundaries, never replacement decoding a split UTF-8 sequence.
    out=[];part=[];size=0
    for char in text:
        n=len(char.encode('utf-8'))
        if size+n>65536:out.append(''.join(part));part=[];size=0
        part.append(char);size+=n
    out.append(''.join(part));return out

class BaziSamples:
    def __init__(self,store,h,error,limiter,app_file):
        self.store,self.h,self.Error,self.rate,self.app_file=store,h,error,limiter,Path(app_file)
        self.owner=h.user['id'] if h.user else ''
    def fail(self,status,code):raise self.Error(status,code)
    def key(self,value):
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',value):self.fail(400,'invalid_request_id')
        return value
    def body(self,keys):
        data=self.read_body()
        if set(data)!=set(keys):self.fail(400,'invalid_fields')
        return data
    def read_body(self):
        from payment_routing import strict_json
        if self.h.headers.get_content_type()!='application/json':self.fail(415,'json_required')
        try:length=int(self.h.headers.get('Content-Length','0'))
        except ValueError:self.fail(400,'invalid_length')
        if not 0<length<=262144:self.fail(413,'request_too_large')
        try:data=strict_json(self.h.rfile.read(length).decode('utf-8',errors='strict'))
        except (ValueError,UnicodeError):self.fail(400,'invalid_json')
        def safe(v,depth=0):
            if depth>32:self.fail(400,'json_depth_exceeded')
            if isinstance(v,dict):
                if any(k in ('__proto__','constructor','prototype') for k in v):self.fail(400,'forbidden_key')
                for x in v.values():safe(x,depth+1)
            elif isinstance(v,list):
                for x in v:safe(x,depth+1)
            elif isinstance(v,str):
                try:v.encode('utf-8')
                except UnicodeError:self.fail(400,'invalid_unicode')
        safe(data)
        if not isinstance(data,dict):self.fail(400,'invalid_fields')
        return data
    def manifest(self):
        value=worker_call({'op':'identity'})
        if value.get('implementationReady') is not True:self.fail(503,'implementation_not_ready')
        app=self.app_file.read_bytes() if self.app_file.is_file() else None
        value['servedAppSha256']=sha(app) if app is not None else None
        expected=value.get('manifest',{}).get('manifestSha256','')
        marker=b'name="ew-bazi-sample-source" content="'+expected.encode()+b'"'
        if not value['servedAppSha256'] or not expected or marker not in app:self.fail(503,'implementation_not_ready')
        value['sourceBindingVerified']=True
        value['sourceManifestSha256']=expected
        return value
    def processing_manifest(self):
        try:return self.manifest()
        except self.Error as error:
            if error.status==503 and error.message=='implementation_not_ready':self.fail(409,'implementation_changed')
            raise
    def guard(self,db,proof):
        self.h.require(('admin',));proof={**proof,'sessionHash':sha(self.h.session_token)}
        db.execute('INSERT INTO bazi_sample_operations VALUES(?,?,?,?,?,?,?)',(str(uuid4()),self.owner,str(uuid4()),'guard','',canonical(proof),now()))
    def epoch(self,db):
        row=db.execute('SELECT epoch FROM bazi_sample_owner_state WHERE owner=?',(self.owner,)).fetchone();return row[0] if row else 1
    def owned(self,db,table,id):
        row=db.execute('SELECT * FROM '+table+' WHERE id=? AND owner=?',(id,self.owner)).fetchone()
        if not row:self.fail(404,'sample_not_found')
        if 'erased_at' in row.keys() and row['erased_at']:self.fail(410,'sample_erased')
        return row
    def operation(self,db,kind,key,fingerprint):
        row=db.execute('SELECT * FROM bazi_sample_operations WHERE owner=? AND kind=? AND request_id=?',(self.owner,kind,key)).fetchone()
        if row and row['intent_fingerprint']!=fingerprint:self.fail(409,'request_conflict')
        value=json.loads(row['response_data']) if row else None
        if row and not value:self.fail(410,'sample_erased')
        return value
    def save_operation(self,db,kind,key,fingerprint,response):
        db.execute('INSERT INTO bazi_sample_operations VALUES(?,?,?,?,?,?,?)',(str(uuid4()),self.owner,key,kind,fingerprint,canonical(response),now()))
    def page(self,db,table,where,args,before,order='id'):
        if before:
            if not db.execute('SELECT 1 FROM '+table+' WHERE '+where+' AND '+order+'=?',(*args,before)).fetchone():self.fail(400,'invalid_cursor')
            where+=' AND '+order+'<?';args=(*args,before)
        rows=db.execute('SELECT * FROM '+table+' WHERE '+where+' ORDER BY '+order+' DESC LIMIT 51',args).fetchall()
        return rows[:50],rows[49][order] if len(rows)>50 else None
    def import_dataset(self):
        key=self.key(self.h.headers.get('X-EW-Request-ID'))
        if self.h.headers.get_content_type()!='application/json':self.fail(415,'json_required')
        try:length=int(self.h.headers.get('Content-Length','0'))
        except ValueError:self.fail(400,'invalid_length')
        if not 0<length<=2*1024*1024:self.fail(413,'dataset_too_large')
        with self.store.connect() as db:epoch=self.epoch(db)
        raw=self.h.rfile.read(length)
        if len(raw)!=length:self.fail(400,'invalid_length')
        try:text=raw.decode('utf-8',errors='strict')
        except UnicodeError:self.fail(400,'invalid_utf8')
        validated=worker_call({'op':'validate','rawText':text});data=validated['dataset'];fingerprint=validated['canonicalSha256']
        stamp=now();vid=str(uuid4())
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.guard(db,{'epoch':epoch})
            old=self.operation(db,'import',key,fingerprint)
            if old:return old
            parent=db.execute('SELECT * FROM bazi_sample_sets WHERE owner=? AND set_key=?',(self.owner,data['setId'])).fetchone()
            if not parent:
                sid=str(uuid4());db.execute('INSERT INTO bazi_sample_sets VALUES(?,?,?,?,?,?)',(sid,self.owner,data['setId'],data['title'],stamp,stamp))
            else:sid=parent['id']
            row=db.execute('SELECT * FROM bazi_sample_versions WHERE owner=? AND set_id=? AND version_key=?',(self.owner,sid,data['version'])).fetchone()
            if row:
                if row['canonical_sha256']!=fingerprint:self.fail(409,'version_conflict')
                result={'item':version_item(row),'duplicate':True};self.save_operation(db,'import',key,fingerprint,result);return result
            header={k:v for k,v in data.items() if k!='cases'}
            db.execute('INSERT INTO bazi_sample_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,0)',(vid,self.owner,sid,data['version'],sha(raw),len(raw),fingerprint,validated['canonicalByteLength'],canonical([c['caseId'] for c in data['cases']]),canonical(header),stamp))
            meta={c['caseId']:c for c in validated['cases']}
            for ordinal,case in enumerate(data['cases']):
                m=meta[case['caseId']];db.execute('INSERT INTO bazi_sample_cases VALUES(?,?,?,?,?,?,?,?)',(vid,case['caseId'],self.owner,ordinal,canonical(case),m['canonicalSha256'],m['canonicalByteLength'],stamp))
            result={'item':version_item(self.owned(db,'bazi_sample_versions',vid)),'duplicate':False};self.save_operation(db,'import',key,fingerprint,result)
        return result
    def create_run(self):
        data=self.body(('requestId','setVersionId','caseIds'));key=self.key(data['requestId']);self.key(data['setVersionId']);ids=data['caseIds']
        if not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):self.fail(400,'invalid_case_ids')
        fingerprint=sha(canonical({'setVersionId':data['setVersionId'],'caseIds':ids}))
        # Resolve original intent before asking whether the current implementation is available.
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM bazi_sample_runs WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if row:
                if row['intent_fingerprint']!=fingerprint:self.fail(409,'request_conflict')
                if row['erased_at']:self.fail(410,'sample_erased')
                return {'run':run_item(row),'duplicate':True}
        manifest=self.manifest();mh=sha(canonical(manifest));rid=str(uuid4());stamp=now()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');epoch=self.epoch(db);self.guard(db,{'epoch':epoch})
            self.owned(db,'bazi_sample_versions',data['setVersionId'])
            for cid in ids:
                if not db.execute('SELECT 1 FROM bazi_sample_cases WHERE version_id=? AND owner=? AND case_id=?',(data['setVersionId'],self.owner,cid)).fetchone():self.fail(400,'invalid_case_ids')
            old=db.execute('SELECT * FROM bazi_sample_runs WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if old:
                if old['intent_fingerprint']!=fingerprint:self.fail(409,'request_conflict')
                return {'run':run_item(old),'duplicate':True}
            db.execute('INSERT INTO bazi_sample_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)',(rid,self.owner,data['setVersionId'],key,fingerprint,canonical(ids),canonical(manifest),mh,epoch,'pending',1,len(ids),0,0,0,0,canonical(COUNTS),stamp,stamp))
            for ordinal,cid in enumerate(ids):db.execute('INSERT INTO bazi_sample_workitems VALUES(?,?,?,?,?,?,0,\'\',0,\'\',?,?)',(str(uuid4()),self.owner,rid,cid,ordinal,'pending',stamp,stamp))
            return {'run':run_item(self.owned(db,'bazi_sample_runs',rid)),'duplicate':False}
    def result_item(self,row,work=None):
        if not row:return {'id':None,'caseId':work['case_id'],'state':work['state'],'errorCode':work['last_error'],'counts':{**COUNTS,'teacherAgreementRate':None},'fingerprints':{},'rawIndex':None,'domStatus':'not_run','teacherConfirmed':False,'professionalValidation':False,'created':work['created'],'updated':work['updated']}
        data=json.loads(row['data']);return {'id':row['id'],'caseId':row['case_id'],'state':row['status'],'errorCode':row['error_code'],'counts':{**data.get('counts',COUNTS),'teacherAgreementRate':None},'fingerprints':data.get('fingerprints',{}),'rawIndex':json.loads(row['raw_index']),'domStatus':'not_run','teacherConfirmed':False,'professionalValidation':False,'created':row['created'],'updated':row['created']}
    def process(self,rid):
        d=self.body(('requestId','version','limit'));key=self.key(d['requestId'])
        if type(d['version']) is not int or d['limit']!=1 or type(d['limit']) is not int:self.fail(400,'invalid_process')
        fp=sha(canonical({'runId':rid,'version':d['version'],'limit':1}))
        with self.store.connect() as db:
            run=self.owned(db,'bazi_sample_runs',rid);old=self.operation(db,'process',key,fp)
            if old and old.get('done'):return {**old['response'],'duplicate':True}
        manifest=self.processing_manifest();mh=sha(canonical(manifest))
        if mh!=run['manifest_hash']:self.fail(409,'implementation_changed')
        token=str(uuid4());stamp=now()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');run=self.owned(db,'bazi_sample_runs',rid);old=self.operation(db,'process',key,fp)
            if old and old.get('done'):return {**old['response'],'duplicate':True}
            if not old and run['version']!=d['version']:self.fail(409,'run_version_changed')
            proof={'runId':rid,'version':run['version'],'epoch':run['epoch'],'manifestHash':mh};self.guard(db,proof)
            if old:
                work=self.owned(db,'bazi_sample_workitems',old['workId'])
                if work['state'] in ('succeeded','blocked','failed'):
                    result=db.execute('SELECT * FROM bazi_sample_results WHERE run_id=? AND case_id=?',(rid,work['case_id'])).fetchone()
                    if not result:self.fail(409,'sample_result_invalid')
                    response={'run':run_item(run),'item':self.result_item(result),'duplicate':True}
                    db.execute("UPDATE bazi_sample_operations SET response_data=? WHERE owner=? AND kind='process' AND request_id=?",(canonical({'done':True,'response':response}),self.owner,key));return response
            else:
                busy=db.execute('SELECT 1 FROM bazi_sample_workitems WHERE run_id=? AND state=\'processing\' AND lease_until>'+NOW,(rid,)).fetchone()
                if busy:self.fail(409,'run_busy')
                work=db.execute("SELECT * FROM bazi_sample_workitems WHERE run_id=? AND state IN ('pending','processing') ORDER BY ordinal LIMIT 1",(rid,)).fetchone()
            if not work:
                response={'run':run_item(run),'item':None,'duplicate':False};self.save_operation(db,'process',key,fp,{'done':True,'response':response});return response
            changed=db.execute("UPDATE bazi_sample_workitems SET state='processing',attempts=min(attempts+1,5),lease_token=?,lease_until="+NOW+"+30000,updated=? WHERE id=? AND (state='pending' OR (state='processing' AND lease_until<="+NOW+'))',(token,stamp,work['id'])).rowcount
            if not changed:self.fail(409,'run_busy')
            db.execute("UPDATE bazi_sample_runs SET state='processing',version=version+1,updated=? WHERE id=?",(stamp,rid))
            if not old:self.save_operation(db,'process',key,fp,{'done':False,'workId':work['id']})
            case=json.loads(db.execute('SELECT data FROM bazi_sample_cases WHERE version_id=? AND case_id=? AND owner=?',(run['version_id'],work['case_id'],self.owner)).fetchone()[0]);proof['version']=run['version']+1
        try:
            if work['attempts']>=5:raise WorkerError('retry_exhausted',409)
            report=worker_call({'op':'compute','case':case})
        except WorkerError as error:
            report={'caseId':case['caseId'],'status':'failed','errorCode':error.code,'stages':{'originalInput':case['input'],'domObserved':{'status':'not_run'}},'counts':{**COUNTS,'teacherAgreementRate':None},'fingerprints':{},'fieldResults':[],'fieldIndex':[],'domStatus':'not_run','teacherConfirmed':False,'professionalValidation':False}
        if sha(canonical(self.processing_manifest()))!=mh:self.fail(409,'implementation_changed')
        raw=report.get('stages',{}).pop('rawOutput',None);sections=[];rawindex=None
        if raw is not None:
            header={k:v for k,v in raw.items() if k!='periods'};periods=raw.get('periods',[])
            ht=canonical(header);rawindex={'sha256':sha(canonical(raw)),'byteLength':len(canonical(raw).encode()),'headerSha256':sha(ht),'headerByteLength':len(ht.encode()),'periods':[]}
            sections.append(('header',-1,ht))
            for index,period in enumerate(periods):
                text=canonical(period);rawindex['periods'].append({'index':index,'sha256':sha(text),'byteLength':len(text.encode()),'chunkCount':len(chunks(text))});sections.append(('period',index,text))
        result_id=str(uuid4());stamp=now();proof.update({'phase':'final','workId':work['id'],'leaseToken':token})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.guard(db,proof)
            db.execute('INSERT INTO bazi_sample_results VALUES(?,?,?,?,?,?,?,?,?)',(result_id,self.owner,rid,case['caseId'],report['status'],report.get('errorCode',''),canonical(report),canonical(rawindex),stamp))
            for section,index,text in sections:
                for ci,part in enumerate(chunks(text)):db.execute('INSERT INTO bazi_sample_raw_chunks VALUES(?,?,?,?,?,?,?,?,?,?)',(str(uuid4()),self.owner,result_id,section,index,ci,part,sha(part),len(part.encode()),stamp))
            for field in report.get('fieldResults',[]):db.execute('INSERT INTO bazi_sample_field_results VALUES(?,?,?,?,?,?)',(str(uuid4()),self.owner,result_id,field['path'],canonical(field),stamp))
            db.execute('UPDATE bazi_sample_workitems SET state=?,last_error=?,lease_token=\'\',lease_until=0,updated=? WHERE id=?',(report['status'],report.get('errorCode',''),stamp,work['id']))
            current=self.owned(db,'bazi_sample_runs',rid);counts=json.loads(current['counts'])
            for k in COUNTS:counts[k]+=report.get('counts',{}).get(k,0)
            counts['teacherAgreementRate']=None
            db.execute("UPDATE bazi_sample_runs SET processed=processed+1,succeeded=succeeded+?,failed=failed+?,blocked=blocked+?,counts=?,version=version+1,state=CASE WHEN processed+1=total THEN 'completed' ELSE 'pending' END,updated=? WHERE id=?",(int(report['status']=='succeeded'),int(report['status']=='failed'),int(report['status']=='blocked'),canonical(counts),stamp,rid))
            response={'run':run_item(self.owned(db,'bazi_sample_runs',rid)),'item':self.result_item(self.owned(db,'bazi_sample_results',result_id)),'duplicate':False}
            db.execute("UPDATE bazi_sample_operations SET response_data=? WHERE owner=? AND kind='process' AND request_id=?",(canonical({'done':True,'response':response}),self.owner,key))
        return response
    def raw(self,db,row):
        rows=db.execute('SELECT * FROM bazi_sample_raw_chunks WHERE owner=? AND result_id=? ORDER BY section,period_index,chunk_index',(self.owner,row['id'])).fetchall();groups={}
        for chunk in rows:
            if sha(chunk['data'])!=chunk['sha256'] or len(chunk['data'].encode())!=chunk['byte_length']:self.fail(409,'raw_integrity_error')
            groups.setdefault((chunk['section'],chunk['period_index']),[]).append(chunk['data'])
        if not groups:return None
        raw=json.loads(''.join(groups[('header',-1)]));raw['periods']=[json.loads(''.join(groups[('period',p)])) for p in sorted(k[1] for k in groups if k[0]=='period')]
        index=json.loads(row['raw_index'])
        if sha(canonical(raw))!=index['sha256']:self.fail(409,'raw_integrity_error')
        return raw
    def route(self,method,path):
        base='/api/admin/bazi-samples'
        if not (path==base or path.startswith(base+'/')):return None
        self.h.require(('admin',));self.rate('bazi-samples:'+('read:' if method=='GET' else 'write:')+self.owner,180 if method=='GET' else 30)
        try:
            result=self.dispatch(method,path,base);self.h.require(('admin',));return result
        except WorkerError as error:self.fail(error.status,error.code+(':'+error.path if error.path else ''))
        except sqlite3.IntegrityError as error:
            code=re.search(r'bazi_sample_[a-z_]+',str(error))
            if code:self.fail(409,code[0])
            raise
    def dispatch(self,method,path,base):
        query=parse_qs(urlsplit(self.h.path).query);before=query.get('before',[''])[0]
        tail=path[len(base):];parts=[]
        for segment in tail.strip('/').split('/') if tail else []:
            decoded=unquote(segment)
            if not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',decoded):self.fail(400,'invalid_resource_id')
            parts.append(decoded)
        if method=='POST' and parts==['import']:return self.import_dataset()
        if method=='POST' and parts==['runs']:return self.create_run()
        if method=='POST' and len(parts)==3 and parts[0]=='runs' and parts[2]=='process':return self.process(parts[1])
        if method=='POST' and len(parts)==3 and parts[0]=='findings' and parts[2]=='reviews':return self.review(parts[1])
        if method!='GET':self.fail(405,'method_not_allowed')
        with self.store.connect() as db:
            if not parts:
                rows,nxt=self.page(db,'bazi_sample_versions','owner=? AND erased_at=0',(self.owner,),before);return {'items':[version_item(r) for r in rows],'next':nxt}
            if parts[0]!='runs':
                if len(parts)!=1:self.fail(404,'sample_not_found')
                row=self.owned(db,'bazi_sample_versions',parts[0]);rows,nxt=self.page(db,'bazi_sample_cases','owner=? AND version_id=?',(self.owner,row['id']),before,'case_id');header={**json.loads(row['data']),'caseIds':json.loads(row['case_order'])}
                return {'item':version_item(row),'header':header,'cases':[{'caseId':r['case_id'],'ordinal':r['ordinal'],'label':json.loads(r['data'])['label'],'tags':json.loads(r['data'])['tags'],'canonicalSha256':r['canonical_sha256'],'canonicalByteLength':r['canonical_bytes']} for r in rows],'next':nxt}
            if len(parts)<2:self.fail(404,'sample_not_found')
            run=self.owned(db,'bazi_sample_runs',parts[1])
            if len(parts)==2:return {'run':run_item(run)}
            if parts[2]=='export':
                rows=db.execute('SELECT * FROM bazi_sample_workitems WHERE run_id=? ORDER BY ordinal',(run['id'],)).fetchall();items=[self.result_item(db.execute('SELECT * FROM bazi_sample_results WHERE run_id=? AND case_id=?',(run['id'],w['case_id'])).fetchone(),w) for w in rows]
                return {'run':run_item(run),'items':items,'canonicalExport':True,'originalSourceBytesAvailable':False}
            if parts[2]!='cases':self.fail(404,'sample_not_found')
            if len(parts)==3:
                rows,nxt=self.page(db,'bazi_sample_workitems','owner=? AND run_id=?',(self.owner,run['id']),before);return {'items':[self.result_item(db.execute('SELECT * FROM bazi_sample_results WHERE run_id=? AND case_id=?',(run['id'],w['case_id'])).fetchone(),w) for w in rows],'next':nxt}
            case_id=parts[3];sample=db.execute('SELECT * FROM bazi_sample_cases WHERE version_id=? AND case_id=? AND owner=?',(run['version_id'],case_id,self.owner)).fetchone();work=db.execute('SELECT * FROM bazi_sample_workitems WHERE run_id=? AND case_id=?',(run['id'],case_id)).fetchone()
            if not sample or not work:self.fail(404,'sample_not_found')
            row=db.execute('SELECT * FROM bazi_sample_results WHERE run_id=? AND case_id=?',(run['id'],case_id)).fetchone();item=self.result_item(row,work)
            if len(parts)==4:
                reviews,nxt=self.page(db,'bazi_sample_reviews','owner=? AND result_id=?',(self.owner,row['id']),query.get('reviewsBefore',[''])[0]) if row else ([],None)
                return {'item':item,'sampleCase':json.loads(sample['data']),'stages':json.loads(row['data']).get('stages',{}) if row else None,'reviews':[{'id':r['id'],'findingId':r['field_id'],'category':r['category'],'evidence':json.loads(r['evidence']),'note':r['note'],'retestRunId':r['retest_run_id'] or None,'classificationState':'proposed','created':r['created']} for r in reviews],'reviewsNext':nxt}
            if not row:self.fail(409,'case_not_completed')
            report=json.loads(row['data']);raw=self.raw(db,row)
            if parts[4]=='raw':
                index=json.loads(row['raw_index'])
                if len(parts)==5:return {'header':{k:v for k,v in (raw or {}).items() if k!='periods'},'index':index}
                if len(parts)==7 and parts[5]=='periods' and parts[6].isdigit() and raw and int(parts[6])<len(raw['periods']):
                    i=int(parts[6]);return {**index['periods'][i],'data':raw['periods'][i]}
                self.fail(404,'period_not_found')
            report.setdefault('stages',{})['rawOutput']=raw
            if parts[4]=='export':
                result={'item':item,'sampleCase':json.loads(sample['data']),'report':report,'canonicalExport':True,'originalSourceBytesAvailable':False}
                include=query.get('includeName',[''])[0]=='1';paths=[]
                if not include:result,paths=redact_names(result)
                return {**result,'includesPrivateNames':include,'completeFrozenReport':include,'redactedPaths':paths,'freeTextAnonymized':False}
            if parts[4]=='fields':return self.fields(db,row,report,before)
            self.fail(404,'sample_not_found')
    def fields(self,db,row,report,before):
        index=sorted(report.get('fieldIndex',[]),key=lambda x:x['path']);paths=[v['path'] for v in index]
        if before and before not in paths:self.fail(400,'invalid_cursor')
        start=paths.index(before)+1 if before else 0;selected=index[start:start+50];provided={f['path']:f for f in report.get('fieldResults',[])};items=[]
        for entry in selected:
            path=entry['path']
            if path in provided:
                value=copy.deepcopy(provided[path]);stored=db.execute('SELECT id FROM bazi_sample_field_results WHERE result_id=? AND path=?',(row['id'],path)).fetchone();value['id']=stored['id'] if stored else None
            else:
                actual,ok=pointer(report['stages'],path);value={'id':None,'caseId':row['case_id'],'stage':entry.get('stage',''),'path':path,'column':entry.get('column'),'expectedState':'not_covered','expected':None,'actualState':entry.get('actualState','value' if ok else 'unavailable'),'actual':actual,'comparison':'not_covered','reasonCode':'expected_not_provided','category':'undetermined','classificationState':'unclassified','evidence':{'stageFingerprint':report.get('fingerprints',{}).get(entry.get('stage',''))}}
            items.append(value)
        return {'items':items,'next':selected[-1]['path'] if start+50<len(index) else None,'counts':report.get('counts',dict(COUNTS))}
    def review(self,finding):
        d=self.read_body()
        if set(d)-{'requestId','category','evidence','note','retestRunId'} or not {'requestId','category','evidence','note'}<=set(d):self.fail(400,'invalid_fields')
        key=self.key(d['requestId']);e=d['evidence']
        if d['category'] not in ('input','rule','algorithm','display','undetermined') or not isinstance(d['note'],str) or len(d['note'])>2000 or not isinstance(e,dict) or set(e)!={'paths','fingerprints','reference'} or not isinstance(e['paths'],list) or not 1<=len(e['paths'])<=20 or not isinstance(e['fingerprints'],dict) or e['reference'] is not None and (not isinstance(e['reference'],str) or len(e['reference'])>1000):self.fail(400,'invalid_review')
        fp=sha(canonical({'findingId':finding,**{k:v for k,v in d.items() if k!='requestId'}}));stamp=now()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.guard(db,{'epoch':self.epoch(db)})
            old=self.operation(db,'review',key,fp)
            if old:return old
            field=self.owned(db,'bazi_sample_field_results',finding);result=self.owned(db,'bazi_sample_results',field['result_id']);report=json.loads(result['data'])
            if any(p not in [f['path'] for f in report.get('fieldIndex',[])] for p in e['paths']) or any(report.get('fingerprints',{}).get(k)!=v for k,v in e['fingerprints'].items()):self.fail(400,'invalid_evidence')
            retest=d.get('retestRunId') or ''
            if retest:
                self.owned(db,'bazi_sample_runs',retest)
                if retest==result['run_id'] or not db.execute('SELECT 1 FROM bazi_sample_workitems WHERE run_id=? AND case_id=? AND owner=?',(retest,result['case_id'],self.owner)).fetchone():self.fail(400,'invalid_retest_run')
            identifier=str(uuid4());db.execute('INSERT INTO bazi_sample_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?)',(identifier,self.owner,result['id'],finding,key,fp,d['category'],canonical(e),d['note'],retest,stamp))
            response={'item':{'id':identifier,'findingId':finding,'category':d['category'],'evidence':e,'note':d['note'],'retestRunId':retest or None,'classificationState':'proposed','created':stamp}}
            self.save_operation(db,'review',key,fp,response);return response
