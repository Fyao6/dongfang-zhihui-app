"""Real privacy + fresh shared-memory SQLite; no service/provider/original DB."""
import ast,hashlib,json,sqlite3,sys,threading,time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
BACK=ROOT/'04_研发源码/app/r4/backend';sys.path.insert(0,str(BACK))
import memory_service as M,privacy as P
checks=[]
class Error(Exception):
 def __init__(self,status,message):super().__init__(message);self.status=status
def expect(status,fn):
 try:fn()
 except Error as e:assert e.status==status,(status,e.status,str(e));return
 raise AssertionError('expected status '+str(status))
def check(name,fn):
 try:fn();checks.append({'name':name,'pass':True})
 except Exception as e:
  import traceback
  checks.append({'name':name,'pass':False,'error':traceback.format_exc()})
class Store:
 def __init__(self,disk=False):
  self.path=ROOT/'06_验证与后续工作'/('负责人优化建议-记忆并发-'+uuid4().hex+'.sqlite3') if disk else None
  self.uri=str(self.path) if disk else 'file:memory-test-'+uuid4().hex+'?mode=memory&cache=shared';self.anchor=sqlite3.connect(self.uri,uri=not disk);self.anchor.row_factory=sqlite3.Row
 @contextmanager
 def connect(self):
  db=sqlite3.connect(self.uri,uri=True,timeout=5);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
  try:
   with db:yield db
  finally:db.close()
 def setting(self,key):
  with self.connect() as db:r=db.execute('SELECT data FROM settings WHERE key=?',(key,)).fetchone()
  return json.loads(r[0]) if r else {}
 def close(self):
  self.anchor.close()
  if self.path:self.path.unlink()
class H:
 def __init__(self,owner='A'):self.user={'id':owner,'role':'user'};self.data={}
 def require(self,*a):
  if not self.user:raise Error(401,'login')
  return self.user
 def body(self):return self.data
class Fixture:
 def __init__(self,disk=False):
  self.store=Store(disk);self.h=H();self.now=int(time.time()*1000)
  with self.store.connect() as db:
   db.executescript('CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT); CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT); CREATE TABLE account_lifecycle(owner TEXT PRIMARY KEY,status TEXT,epoch INTEGER,closed_at INTEGER,receipt_id TEXT); CREATE TABLE ai_gateway_provider_consents(owner TEXT,provider_id TEXT,provider_binding TEXT,policy_version TEXT,global_revision INTEGER,categories TEXT,created INTEGER,updated INTEGER,revision TEXT,PRIMARY KEY(owner,provider_id)); CREATE TABLE ai_gateway_jobs(id TEXT PRIMARY KEY,owner TEXT,status TEXT,cancel_requested INTEGER DEFAULT 0,output_text TEXT,saved_conversation_id TEXT,fingerprint TEXT NOT NULL DEFAULT ""); CREATE TABLE ai_gateway_wallets(owner TEXT PRIMARY KEY,balance INTEGER,reserved INTEGER); CREATE TABLE commerce_orders(id TEXT PRIMARY KEY,owner TEXT,amount_minor INTEGER); CREATE TABLE privacy_record_epochs(owner TEXT PRIMARY KEY,revision INTEGER); CREATE TABLE card_record_epochs(owner TEXT PRIMARY KEY,revision INTEGER);')
   for owner in ('A','B'):db.execute('INSERT INTO users VALUES(?,?)',(owner,'user'))
   self.cfg={'policyVersion':'p1','controllerName':'Synthetic controller','contact':'fixture.invalid','revision':1,'recipients':[{'id':'provider','name':'Synthetic provider','regions':['fixture-region'],'purpose':'manual selected memory','policyUrl':'https://fixture.invalid/policy','endpoint':'https://fixture.invalid/v1/responses','models':['fixture-model']}],'retention':{'recordsDays':None,'conversationsDays':None,'backupDays':None,'financeDays':None},'purposeDetails':{'trainingImprovement':'','marketing':''}}
   self.ai={'providerId':'provider','endpoint':self.cfg['recipients'][0]['endpoint'],'model':'fixture-model','processingRegions':['fixture-region'],'privacyPolicyVersion':'p1'}
   for k,v in [('privacy',self.cfg),('ai',self.ai)]:db.execute('INSERT INTO settings VALUES(?,?)',(k,json.dumps(v)))
   P.init_schema(db);M.init_schema(db)
   flags=dict.fromkeys(P.CONSENTS,False)
   for owner in ('A','B'):
    binding=P.actual_binding(self.cfg,self.ai)['digest']
    db.execute('INSERT INTO privacy_preferences VALUES(?,?,?,?,?,?)',(owner,json.dumps(flags),'p1',1,self.now,binding))
    db.execute('INSERT INTO ai_gateway_provider_consents VALUES(?,?,?,?,?,?,?,?,?)',(owner,'provider','provider-binding','p1',1,json.dumps(M.CATEGORIES),1,1,'base-receipt'))
    db.execute('INSERT INTO ai_gateway_wallets VALUES(?,?,?)',(owner,100,20));db.execute('INSERT INTO commerce_orders VALUES(?,?,?)',(owner+'-order',owner,123))
    db.execute('INSERT INTO privacy_record_epochs VALUES(?,?)',(owner,2));db.execute('INSERT INTO card_record_epochs VALUES(?,?)',(owner,3))
 def scalar(self,sql,args=()):
  with self.store.connect() as db:r=db.execute(sql,args).fetchone()
  return r[0] if r else None
 def write(self,sql,args=()):
  with self.store.connect() as db:return db.execute(sql,args).rowcount
 def prefs(self):return P.Privacy(self.store,self.h,Error,lambda *a:None).response()
 def enable(self,**extra):
  owner=self.h.user['id']
  with self.store.connect() as db:
   old=json.loads(db.execute('SELECT data FROM privacy_preferences WHERE user_id=?',(owner,)).fetchone()[0]);old.update(longTermMemory=True);old.update(extra);db.execute('UPDATE privacy_preferences SET data=? WHERE user_id=?',(json.dumps(old),owner))
 def auth(self,*args):
  p=self.prefs();return {'accountId':self.h.user['id'],'providerId':'provider','providerBinding':'provider-binding','policyVersion':'p1','globalRevision':p['revision'],'globalBinding':p['providerBinding'],'providerConsentRevision':'base-receipt','authorizedCategories':list(M.CATEGORIES),'receiptValid':True}
 def call(self,path='',data=None,method='POST'):
  self.h.data=data or {};return M.MemoryService(self.store,self.h,Error,lambda *a:None,test_clock=lambda:self.now,provider_authorization=self.auth).route(method,'/api/memory'+path)
 def add(self,key='add00001',category='general',text='Synthetic private memory A'):
  return self.call('',{'requestId':key,'memoryEpoch':self.scalar('SELECT epoch FROM memory_state WHERE owner=?',(self.h.user['id'],)) or 0,'category':category,'title':'Synthetic title','text':text})
 def consent(self,key='consent001'):
  auth=self.auth();return self.call('/providers/provider/consent',{'requestId':key,'acknowledged':True,'providerBinding':auth['providerBinding'],'policyVersion':'p1','globalRevision':1,'memoryEpoch':self.scalar('SELECT epoch FROM memory_state WHERE owner=?',(self.h.user['id'],)) or 0})
 def prepare(self,items,auth=None,legacy=False):
  return M.prepare_ai_memory(self.store,self.h.user['id'],{'memoryEpoch':self.scalar('SELECT epoch FROM memory_state WHERE owner=?',(self.h.user['id'],)) or 0,'items':items},Error,authorization=auth or self.auth(),legacy=legacy)
 def proof(self):
  self.enable();self.consent();r=self.add();return r,self.prepare([{'id':r['currentItem']['id'],'version':1}])
 def guard(self,p):
  sql,args=M.memory_save_guard(p);return bool(self.scalar('SELECT 1 WHERE '+sql,args))
 def fingerprint(self):
  with self.store.connect() as db:return M.fingerprint([dict(x) for t in ('ai_gateway_wallets','commerce_orders','privacy_record_epochs','card_record_epochs') for x in db.execute('SELECT * FROM '+t+' ORDER BY owner')])
 def close(self):self.store.close()
def case(fn):
 f=Fixture()
 try:fn(f)
 finally:f.close()
def assert_eq(a,b):assert a==b,(a,b)
check('new independent Python AST is valid',lambda:ast.parse((BACK/'memory_service.py').read_text(encoding='utf-8')))
check('default off, empty metadata and no fabricated vector/automatic extraction',lambda:case(lambda f:(lambda r:(assert_eq(r['settings']['enabled'],False),assert_eq(r['settings']['vectorStoreAvailable'],False),assert_eq(r['items'],[])))(f.call(method='GET'))))
check('add off rejected; owner can still read empty export',lambda:case(lambda f:(expect(403,f.add),assert_eq(f.call('/export',method='GET')['items'],[]))))
def add_guard(f):
 f.enable();f.write("UPDATE privacy_preferences SET provider_binding='' WHERE user_id='A'");expect(403,f.add)
check('checked checkbox without current global acknowledgement cannot add',lambda:case(add_guard))
def categories(f):
 f.enable();expect(403,lambda:f.add(category='chart'));expect(403,lambda:f.add(category='wellbeing'));f.enable(chart=True);assert_eq(f.add('chart001','chart')['currentItem']['category'],'chart')
check('new chart/wellbeing requires category AND memory consent',lambda:case(categories))
def crud(f):
 f.enable();r=f.add();item=r['currentItem'];assert_eq(item['version'],1);listed=f.call(method='GET');assert 'text' not in listed['items'][0];assert_eq(f.call('/items/'+item['id'],method='GET')['item']['text'],item['text']);assert_eq(f.call('/export',method='GET')['items'][0]['text'],item['text']);assert 'text' not in json.dumps(r['receipt'])
 f.h.user={'id':'B'};expect(404,lambda:f.call('/items/'+item['id'],method='GET'));assert_eq(f.call(method='GET')['items'],[])
check('owner CRUD/export; list metadata only and receipts no body',lambda:case(crud))
def edit_off(f):
 f.enable();r=f.add()['currentItem'];f.enable(longTermMemory=False);r2=f.call('/items/'+r['id'],{'requestId':'edit00001','memoryEpoch':0,'expectedVersion':1,'category':'chart','title':'Changed','text':'Owner may edit while off'},'PATCH')['currentItem'];assert_eq(r2['version'],2);expect(409,lambda:f.call('/items/'+r['id'],{'requestId':'edit00002','memoryEpoch':0,'expectedVersion':1,'category':'general','title':'bad','text':'stale'},'PATCH'));expect(403,lambda:f.add('fresh-off'))
check('off still allows owner edits, version conflict prevents overwrite',lambda:case(edit_off))
def strict(f):
 f.enable()
 for v in (True,1.5,'0',-1,9007199254740992):expect(400,lambda v=v:f.call('',{'requestId':'strict001','memoryEpoch':v,'category':'general','title':'T','text':'t'}))
 for extra in ({'owner':'B'},{'enabled':True},{'provider_snapshot':'x'}):expect(400,lambda extra=extra:f.call('',{'requestId':'strict001','memoryEpoch':0,'category':'general','title':'T','text':'t',**extra}))
 expect(400,lambda:f.add(text='x'*2001));expect(400,lambda:f.add(text='\ud800'));assert_eq(f.add(text='😀'*2000)['currentItem']['characterCount'],2000)
check('strict integer/exact keys/unicode codepoint length, surrogate rejected',lambda:case(strict))
def idempotency(f):
 f.enable();r=f.add();rr=f.add();assert_eq(rr['receipt']['id'],r['receipt']['id']);assert_eq(rr['replayed'],True);expect(409,lambda:f.add(text='different'));assert_eq(f.scalar('SELECT count(*) FROM memory_entries'),1)
check('same key/payload replays; changed payload conflicts',lambda:case(idempotency))
def deletes(f):
 f.enable();r=f.add()['currentItem'];before=f.fingerprint();d={'requestId':'delete001','memoryEpoch':0,'expectedVersion':1,'confirmed':True};out=f.call('/items/'+r['id']+'/delete',d);assert_eq(out['memoryEpoch'],1);assert_eq(f.call('/items/'+r['id']+'/delete',d)['receipt']['id'],out['receipt']['id']);assert_eq(f.scalar('SELECT count(*) FROM memory_tombstones'),1);assert_eq(before,f.fingerprint());expect(409,lambda:f.call('/clear',{'requestId':'clearold1','memoryEpoch':0,'confirmed':True}));empty=f.call('/clear',{'requestId':'clearempty','memoryEpoch':1,'confirmed':True});assert_eq(empty['memoryEpoch'],2)
check('delete tombstone/empty clear invalidate only memory epoch and idempotent replay',lambda:case(deletes))
def closed(f):
 f.enable();f.write("INSERT INTO account_lifecycle VALUES('A','closed',1,1,'fixture')");expect(401,f.add);expect(401,lambda:f.call(method='GET'))
check('closed actor cannot view/add/revoke',lambda:case(closed))
def cap(f):
 f.enable()
 for i in range(100):f.add('capacity'+str(i))
 expect(409,lambda:f.add('capacity-extra'));assert_eq(f.scalar('SELECT count(*) FROM memory_entries'),100)
check('100 entry capacity refuses new entry without deleting old ones',lambda:case(cap))
def selection(f):
 f.enable();r=f.add()['currentItem'];expect(403,lambda:f.prepare([{'id':r['id'],'version':1}]));f.consent();p=f.prepare([{'id':r['id'],'version':1}]);assert_eq(p['data'][0]['text'],r['text']);assert_eq(f.guard(p),True)
 expect(400,lambda:f.prepare([{'id':r['id'],'version':1}]*2));expect(404,lambda:f.prepare([{'id':'foreign','version':1}]));expect(409,lambda:f.prepare([{'id':r['id'],'version':2}]));expect(400,lambda:f.prepare([{'id':'i'+str(i),'version':1} for i in range(6)]))
check('explicit selection requires extra actual-provider receipt/owner/version/limits',lambda:case(selection))
def check_proof(f):
 r,p=f.proof();f.call('/items/'+r['currentItem']['id'],{'requestId':'editproof','memoryEpoch':0,'expectedVersion':1,'category':'general','title':'T','text':'New'},'PATCH');assert_eq(f.guard(p),False);expect(409,lambda:M.check_ai_memory(f.store,'A',p,Error,authorization=f.auth()))
check('edit invalidates in-flight proof and atomic final SQL guard',lambda:case(check_proof))
def independent_gate(kind):
 def fn(f):
  _,p=f.proof()
  if kind=='off':f.enable(longTermMemory=False)
  elif kind=='binding':f.write("UPDATE privacy_preferences SET provider_binding='' WHERE user_id='A'")
  elif kind=='endpoint':f.write("UPDATE settings SET data=json_set(data,'$.endpoint','https://other.invalid/responses') WHERE key='ai'")
  elif kind=='base':f.write("UPDATE ai_gateway_provider_consents SET revision='changed' WHERE owner='A'")
  elif kind=='memory':f.write("UPDATE memory_provider_consents SET nonce='changed' WHERE owner='A'")
  elif kind=='closed':f.write("INSERT INTO account_lifecycle VALUES('A','closed',1,1,'fixture')")
  assert_eq(f.guard(p),False)
 return fn
for k in ('off','binding','endpoint','base','memory','closed'):check('final SQL rejects fresh '+k,lambda k=k:case(independent_gate(k)))
def legacy(f):
 f.enable();r=f.add()['currentItem'];p=f.prefs();a={**f.auth(),'providerBinding':p['providerBinding']};proof=f.prepare([{'id':r['id'],'version':1}],a,True);assert_eq(f.guard(proof),True);expect(403,lambda:f.prepare([{'id':r['id'],'version':1}],{**a,'providerId':'other'},True))
check('legacy actual binding checked without borrowing gateway receipt',lambda:case(legacy))
def budget():
 raw={'messages':[{'role':'user','content':'😀 question'}],'context':{'category':'general','fields':{'question':'x'*100}}};proof={'data':[{'category':'general','title':'T','text':''}]};size=M.memory_request_semantic(raw,proof,Error)['contextCharacters'];proof['data'][0]['text']='x'*(6000-size);r=M.memory_request_semantic(raw,proof,Error);assert_eq(r['contextCharacters'],6000);assert_eq(r['inputCharacters'],6000+len('😀 question'));proof['data'][0]['text']+='x';expect(400,lambda:M.memory_request_semantic(raw,proof,Error))
check('expanded body and report share strict 6000 context characters',budget)
def semantic():
 raw={'messages':[{'role':'user','content':'Q'}],'memorySelection':{'memoryEpoch':0,'items':[{'id':'id','version':1}]}};a={'data':[{'category':'general','title':'T','text':'one'}],'memoryConsentNonce':'a'};one=M.memory_request_semantic(raw,a,Error);two=M.memory_request_semantic(raw,{**a,'memoryConsentNonce':'b'},Error);changed=M.memory_request_semantic(raw,{'data':[{'category':'general','title':'T','text':'two'}]},Error);assert_eq(one,two);assert one['fingerprint']!=changed['fingerprint'];assert_eq(one['requestFingerprint'],changed['requestFingerprint'])
check('expanded fingerprint binds text; receipt nonce not semantic; no plaintext audit',semantic)
def no_memory():
 class NoDB:
  def execute(self,*a):raise AssertionError('ordinary request touched memory table')
 raw={'messages':[{'role':'user','content':'Q'}]};s=M.memory_request_semantic(raw,None,Error);assert_eq(s['fingerprint'],s['requestFingerprint']);assert_eq(M.prepare_ai_memory(None,'A',None,Error,authorization=None),None);assert_eq(M.memory_job_replay_matches(NoDB(),'A',{'owner':'A','id':'old','fingerprint':s['fingerprint']},raw),True);assert_eq(M.memory_job_replay_matches(NoDB(),'B',{'owner':'A','id':'old','fingerprint':s['fingerprint']},raw),False)
check('ordinary unselected request performs zero memory-entry reads',no_memory)
def job(f):
 r,p=f.proof();raw={'messages':[{'role':'user','content':'Q'}],'memorySelection':p['selection']};s=M.memory_request_semantic(raw,p,Error)
 with f.store.connect() as db:
  db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO ai_gateway_jobs VALUES(?,?,?,?,?,?,?)',('job','A','running',0,'retained output','saved',s['fingerprint']));M.capture_memory_job(db,'A','job',p,f.now,s)
 assert_eq(f.scalar('SELECT count(*) FROM memory_job_bindings'),1)
 f.call('/clear',{'requestId':'clearjob1','memoryEpoch':0,'confirmed':True});assert_eq(f.scalar('SELECT cancel_requested FROM ai_gateway_jobs'),1);assert_eq(f.scalar('SELECT output_text FROM ai_gateway_jobs'),'retained output');assert_eq(f.scalar('SELECT saved_conversation_id FROM ai_gateway_jobs'),'saved')
 with f.store.connect() as db:
  row=db.execute('SELECT * FROM ai_gateway_jobs').fetchone();db.set_trace_callback(lambda sql: (_ for _ in ()).throw(AssertionError(sql)) if 'memory_entries' in sql else None);assert_eq(M.memory_job_replay_matches(db,'A',row,raw),True);assert_eq(M.memory_job_replay_matches(db,'A',row,{**raw,'messages':[{'role':'user','content':'different'}]}),False)
 expect(409,lambda:M.prepare_ai_memory(f.store,'A',p['selection'],Error,authorization=f.auth()))
check('actual job binding, delete replay minimal and no output/quota resurrection',lambda:case(job))
def capture_stale(f):
 _,p=f.proof();s=M.memory_request_semantic({'messages':[]},p,Error);f.enable(longTermMemory=False)
 try:
  with f.store.connect() as db:
   db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO ai_gateway_jobs VALUES(?,?,?,?,?,?,?)',('job','A','queued',0,None,None,s['fingerprint']));M.capture_memory_job(db,'A','job',p,f.now,s)
 except sqlite3.IntegrityError:pass
 else:raise AssertionError('stale capture accepted')
 assert_eq(f.scalar('SELECT count(*) FROM ai_gateway_jobs'),0);assert_eq(f.scalar('SELECT count(*) FROM memory_job_bindings'),0)
check('capture failure rolls back same-transaction job; no quota reservation leak',lambda:case(capture_stale))
def cleanup(f):
 f.enable();r=f.add()['currentItem'];before=f.fingerprint()
 with f.store.connect() as db:
  db.execute('BEGIN IMMEDIATE');out=M.append_memory_cleanup(db,'A','cleanup-01',f.now);assert_eq(out['counts']['memoryEntries'],1)
 with f.store.connect() as db:
  db.execute('BEGIN IMMEDIATE');again=M.append_memory_cleanup(db,'A','cleanup-01',f.now);assert_eq(again['receiptId'],out['receiptId']);assert_eq(again['replayed'],True)
 assert_eq(f.scalar('SELECT epoch FROM memory_state'),1);assert_eq(before,f.fingerprint());assert_eq(out['providersStatus'],'pending-confirmation');assert 'Synthetic private' not in json.dumps(out)
check('unified cleanup idempotent and financial/record/card epochs unchanged',lambda:case(cleanup))
def cleanup_fence(f):
 f.enable();f.add()
 with f.store.connect() as db:
  db.execute('BEGIN IMMEDIATE');plan=M.memory_cleanup_statements({'memory_entries','memory_state','memory_cleanup_receipts'},'A','guardzero',f.now,'0')
  for sql,args in plan['statements']:db.execute(sql,args)
 assert_eq(f.scalar('SELECT count(*) FROM memory_entries'),1);assert_eq(f.scalar('SELECT count(*) FROM memory_cleanup_receipts'),0)
 try:
  with f.store.connect() as db:
   db.execute('BEGIN IMMEDIATE');M.append_memory_cleanup(db,'A','rollback',f.now);db.execute('INSERT INTO nonexistent VALUES(1)')
 except sqlite3.OperationalError:pass
 assert_eq(f.scalar('SELECT count(*) FROM memory_entries'),1);assert_eq(f.scalar('SELECT count(*) FROM memory_tombstones'),0)
check('cleanup guard false and transactional rollback leave memory intact',lambda:case(cleanup_fence))
def expiry(f):
 f.enable();r=f.add()['currentItem'];f.call('/items/'+r['id'],{'requestId':'editexpiry','memoryEpoch':0,'expectedVersion':1,'category':'general','title':'Fresh','text':'Fresh'},'PATCH')
 with f.store.connect() as db:
  db.execute('BEGIN IMMEDIATE');out=M.append_memory_cleanup(db,'A','expiry-old',f.now,reason='retention',targets=[{'id':r['id'],'version':1}]);assert_eq(out['counts']['memoryEntries'],0)
 assert_eq(f.scalar('SELECT epoch FROM memory_state'),None)
 with f.store.connect() as db:
  db.execute('BEGIN IMMEDIATE');out=M.append_memory_cleanup(db,'A','expiry-new',f.now,reason='retention',targets=[{'id':r['id'],'version':2}]);assert_eq(out['counts']['memoryEntries'],1)
 assert_eq(f.scalar('SELECT count(*) FROM memory_entries'),0);assert_eq(f.scalar('SELECT epoch FROM memory_state'),1)
check('retention exact id/version cannot erase a concurrent later edit',lambda:case(expiry))
def revoke(f):
 f.enable();f.consent();f.add();before=f.fingerprint();f.enable(longTermMemory=False);f.write("UPDATE settings SET data='{}' WHERE key='privacy'");d={'requestId':'revoke001'};out=f.call('/providers/provider/consent',d,'DELETE');assert_eq(out['memoryEpoch'],1);again=f.call('/providers/provider/consent',d,'DELETE');assert_eq(again['receipt']['id'],out['receipt']['id']);assert_eq(again['replayed'],True);expect(409,lambda:f.call('/providers/other/consent',d,'DELETE'));assert_eq(f.scalar('SELECT count(*) FROM memory_entries'),1);assert_eq(f.scalar("SELECT revision FROM ai_gateway_provider_consents WHERE owner='A'"),'base-receipt');assert_eq(before,f.fingerprint())
check('provider-only memory withdrawal works off/unconfigured without touching base permission',lambda:case(revoke))
def offhook(f):
 f.enable();before=f.fingerprint()
 with f.store.connect() as db:
  db.execute('BEGIN IMMEDIATE');assert_eq(M.on_preferences_change(db,'A',{'longTermMemory':False},{'longTermMemory':False},f.now),0);assert_eq(M.on_preferences_change(db,'A',{'longTermMemory':True},{'longTermMemory':False},f.now),1)
 assert_eq(before,f.fingerprint())
check('normal preference off invalidates only independent memory epoch',lambda:case(offhook))
def concurrent(operation):
 f=Fixture(disk=True)
 try:
  f.enable();r=f.add()['currentItem'];barrier=threading.Barrier(2);out=[];errors=[]
  path='/clear' if operation=='clear' else '/items/'+r['id']+'/delete' if operation=='delete' else '/providers/provider/consent'
  data={'requestId':'concurrent-'+operation,'memoryEpoch':0,'confirmed':True}
  if operation=='delete':data['expectedVersion']=1
  if operation=='revoke':data={'requestId':'concurrent-revoke'}
  def worker():
   try:
    h=H();h.data=dict(data);service=M.MemoryService(f.store,h,Error,lambda *a:None,test_clock=lambda:f.now,provider_authorization=f.auth);barrier.wait();out.append(service.route('DELETE' if operation=='revoke' else 'POST','/api/memory'+path))
   except Exception as exc:errors.append(repr(exc))
  threads=[threading.Thread(target=worker) for _ in range(2)]
  for t in threads:t.start()
  for t in threads:t.join(10)
  assert not any(t.is_alive() for t in threads);assert_eq(errors,[]);assert_eq(len(out),2);assert_eq(out[0]['receipt']['id'],out[1]['receipt']['id']);assert_eq(f.scalar('SELECT epoch FROM memory_state'),1)
 finally:f.close()
for op in ('clear','delete','revoke'):check('real fresh file SQLite concurrent same-key '+op+' applies once',lambda op=op:concurrent(op))
report={'at':time.time(),'kind':'independent-Python-real-privacy-native-SQLite','pass':all(x['pass'] for x in checks),'passed':sum(x['pass'] for x in checks),'failed':sum(not x['pass'] for x in checks),'checks':checks,'sourceSHA':hashlib.sha256((BACK/'memory_service.py').read_bytes()).hexdigest(),'testSHA':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':['No shared/public integration, HTTP service or real provider call.','Synthetic fixtures only; no original DB. Hashes are integrity data, not anonymization or encryption.']}
dest=Path(__file__).with_name('负责人优化建议-长期记忆内存结果.json');prior=[]
if dest.exists():
 old=json.loads(dest.read_text(encoding='utf-8-sig'));prior=old.get('runs',[old])
dest.write_text(json.dumps({**report,'runs':[*prior,report]},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('pass','passed','failed')},ensure_ascii=False));print(json.dumps([x for x in checks if not x['pass']],ensure_ascii=False))
sys.exit(0 if report['pass'] else 1)
