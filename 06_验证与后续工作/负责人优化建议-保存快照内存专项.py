"""Synthetic owner-scoped saved-snapshot tests; actual frozen privacy/gateway helpers, no HTTP or provider."""
from contextlib import contextmanager
import copy,json,sqlite3,sys,traceback,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'04_研发源码/app/r4/backend'))
import privacy,privacy_saved as mod,ai_gateway
ROOT=Path(__file__).resolve().parents[1];results=[]
class Error(Exception):
 def __init__(self,status,message):super().__init__(message);self.status=status
class Store:
 def __init__(self):
  self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row;self.depth=0;self.db.executescript('CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT);CREATE TABLE audits(id TEXT,actor TEXT,action TEXT,target TEXT,detail TEXT,created INTEGER);');privacy.init_schema(self.db);ai_gateway.init_schema(self.db);mod.init_schema(self.db);self.db.commit()
 @contextmanager
 def connect(self):
  outer=self.depth==0;self.depth+=1
  try:
   if outer:
    with self.db:yield self.db
   else:yield self.db
  finally:self.depth-=1
 def setting(self,k):
  r=self.db.execute('SELECT data FROM settings WHERE key=?',(k,)).fetchone();return json.loads(r['data']) if r else {}
 def set(self,k,v):
  with self.connect() as db:db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data',(k,mod.dump(v)))
 def audit(self,db,actor,action,target,detail=''):db.execute('INSERT INTO audits VALUES(?,?,?,?,?,?)',('qa',actor,action,target,detail,1))
class Handler:
 def __init__(self,id='u1',role='user'):self.user={'id':id,'role':role};self.payload={}
 def require(self):
  if not self.user:raise Error(401,'login')
  return self.user
 def body(self):return copy.deepcopy(self.payload)
def call(s,p,data=None,method='GET'):s.h.payload=data or {};return s.route(method,p)
def expect(status,fn):
 try:fn()
 except Error as e:assert e.status==status
 else:raise AssertionError('Expected '+str(status))
def fixture():
 s=Store();ai={'providerId':'fixture','endpoint':'https://fixture.invalid/responses','model':'fixture-model','processingRegions':['TEST'],'privacyPolicyVersion':'qa-policy'};cfg={**privacy.DEFAULT_CONFIG,'policyVersion':'qa-policy','controllerName':'QA','contact':'fixture','recipients':[{'id':'fixture','name':'QA','endpoint':ai['endpoint'],'models':[ai['model']],'regions':['TEST'],'purpose':'QA only','policyUrl':'https://fixture.invalid/privacy','retentionDays':None,'deletionSupported':False}]};s.set('privacy',cfg);s.set('ai',ai);binding=privacy.actual_binding(privacy.config(s),ai)['digest'];flags=dict.fromkeys(privacy.CONSENTS,False);flags['saveConversations']=True
 with s.connect() as db:
  for uid in ('u1','u2'):db.execute('INSERT INTO privacy_preferences VALUES(?,?,?,?,?,?)',(uid,mod.dump(flags),'qa-policy',1,1,binding))
 def messages(uid='u1',revision=1,text='PRIVATE_QA_A'):return [{'role':'user','content':text,'privacy':{'accountId':uid,'providerId':'fixture','providerBinding':binding,'policyVersion':'qa-policy','consentEpoch':str(revision)+':qa-policy:'+binding,'source':'user','category':'general'}},{'role':'assistant','content':'REPLY_'+text,'privacy':{'accountId':uid,'providerId':'fixture','providerBinding':binding,'policyVersion':'qa-policy','consentEpoch':str(revision)+':qa-policy:'+binding,'source':'assistant','category':'general'}}]
 with s.connect() as db:
  db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',('snapshot-a','u1',mod.dump(messages()),1));db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',('snapshot-overlap','u1',mod.dump(messages()),2));db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',('snapshot-b','u2',mod.dump(messages('u2',text='OTHER_PRIVATE_QA_B')),1))
 return s,mod.SavedConversations(s,Handler(),Error,lambda *a:None),mod.SavedConversations(s,Handler('u2'),Error,lambda *a:None),messages

def check(name,fn):
 try:fn();results.append({'name':name,'pass':True})
 except Exception:results.append({'name':name,'pass':False,'error':traceback.format_exc()})

def list_and_detail():
 s,u,v,m=fixture();x=call(u,'/api/privacy/saved-conversations');assert x['storedSnapshotCount']==2 and x['threadsRepresented'] is False;assert 'PRIVATE_QA_A' not in mod.dump(x) and 'OTHER_PRIVATE_QA_B' not in mod.dump(x);d=call(u,'/api/privacy/saved-conversations/snapshot-a')['item'];assert d['messages'][0]['content']=='PRIVATE_QA_A';assert set(d['messages'][0])=={'role','content'};expect(404,lambda:call(v,'/api/privacy/saved-conversations/snapshot-a'));assert x['memoryAvailable'] is False and x['automaticAIRead'] is False
check('list is actual owner metadata only; explicit detail is sanitized and never an AI restore',list_and_detail)

def deletion():
 s,u,v,m=fixture();p='/api/privacy/saved-conversations/snapshot-a/delete';body={'requestId':'delete-request-1','confirmed':True};r=call(u,p,body,'POST');assert r['item']['details']['local']['deletedSnapshots']==1;assert r['item']['details']['providers'][0]['status']=='pending-confirmation';assert r['item']['details']['backups']['status']=='pending-confirmation';assert r['item']['details']['memory']['available'] is False;assert s.db.execute('SELECT revision FROM privacy_preferences WHERE user_id=?',('u1',)).fetchone()[0]==2;assert call(u,p,body,'POST')['replayed'];assert call(u,p,{'requestId':'another-key','confirmed':True},'POST')['item']['id']==r['item']['id'];expect(409,lambda:call(u,'/api/privacy/saved-conversations/snapshot-overlap/delete',body,'POST'));expect(404,lambda:call(v,p,body,'POST'));assert s.db.execute('SELECT count(*) FROM privacy_conversations WHERE id=?',('snapshot-overlap',)).fetchone()[0]==1;assert 'PRIVATE_QA_A' not in mod.dump(call(u,'/api/privacy/saved-conversations/deletions'));assert 'PRIVATE_QA_A' not in mod.dump([dict(r) for r in s.db.execute('SELECT * FROM audits')]);assert s.db.execute('SELECT revision FROM privacy_preferences WHERE user_id=?',('u1',)).fetchone()[0]==2
check('single deletion is idempotent, owner-only, bumps epoch once and never substring-deletes overlap',deletion)

def gateway_reference():
 s,u,v,m=fixture()
 with s.connect() as db:
  db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',('gateway-snapshot','u1',mod.dump({'jobId':'j1','providerId':'fixture','input':m(),'output':'SAVED_GATEWAY_PRIVATE'}),3));db.execute('INSERT INTO ai_gateway_wallets VALUES(?,100,0,1)',('u1',));values={'id':'j1','owner':'u1','request_id':'qa-job-request','fingerprint':'fixture-fingerprint','scene':'chat','environment':'local-test','status':'queued','cancel_requested':0,'reserve_credits':5,'charged_credits':None,'policy_snapshot':'{"ruleVersion":"qa"}','provider_snapshot':'{}','route_snapshot':'{}','config_revision':1,'provider_id':'fixture','has_output':1,'output_chars':21,'output_text':None,'usage':None,'error_code':'','lease_until':0,'created':1,'updated':1,'saved_conversation_id':'gateway-snapshot'};db.execute('INSERT INTO ai_gateway_jobs('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',tuple(values.values()));db.execute("UPDATE ai_gateway_jobs SET status='succeeded',charged_credits=3 WHERE id='j1'")
 ledger_before=[dict(r) for r in s.db.execute('SELECT * FROM ai_gateway_quota_events')];wallet_before=dict(s.db.execute('SELECT * FROM ai_gateway_wallets WHERE owner=?',('u1',)).fetchone())
 g=ai_gateway.AIGateway(s,Handler(),Error,lambda *a:None);assert g.job(s.db,g.job_row(s.db,'j1'))['text']=='SAVED_GATEWAY_PRIVATE';call(u,'/api/privacy/saved-conversations/gateway-snapshot/delete',{'requestId':'delete-gateway-snapshot','confirmed':True},'POST');out=g.job(s.db,g.job_row(s.db,'j1'));assert out['text'] is None and not out['outputStored'];assert [dict(r) for r in s.db.execute('SELECT * FROM ai_gateway_quota_events')]==ledger_before;assert dict(s.db.execute('SELECT * FROM ai_gateway_wallets WHERE owner=?',('u1',)).fetchone())==wallet_before;assert wallet_before['balance']==97;assert s.db.execute('SELECT output_text,saved_conversation_id FROM ai_gateway_jobs WHERE id=?',('j1',)).fetchone()[1] is None
 try:s.db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',('gateway-snapshot','u1','[]',4))
 except sqlite3.IntegrityError:pass
 else:raise AssertionError('Deleted snapshot ID reinserted')
check('actual frozen gateway job loses deleted text/link and tombstone prevents exact-ID resurrection',gateway_reference)

def legacy_late_save():
 s,u,v,m=fixture();assert mod.guarded_legacy_save(s,'u1',m());before=s.db.execute('SELECT count(*) FROM privacy_conversations WHERE user_id=?',('u1',)).fetchone()[0];call(u,'/api/privacy/saved-conversations/snapshot-a/delete',{'requestId':'legacy-delete-race','confirmed':True},'POST');assert mod.guarded_legacy_save(s,'u1',m()) is False;assert s.db.execute('SELECT count(*) FROM privacy_conversations WHERE user_id=?',('u1',)).fetchone()[0]==before-1;assert mod.guarded_legacy_save(s,'u1',m(revision=2,text='EXPLICIT_NEW_REQUEST')) is True;assert mod.guarded_legacy_save(s,'u1',m('u2',revision=2)) is False;assert mod.guarded_legacy_save(s,'u1',[{'role':'user','content':'UNTAGGED_OLD_HISTORY'}]) is False
check('legacy atomic save rejects old deleted epoch/foreign/untagged and allows explicit current request',legacy_late_save)

def optout_and_unknown():
 s,u,v,m=fixture()
 with s.connect() as db:db.execute("UPDATE privacy_preferences SET data=json_set(data,'$.saveConversations',0) WHERE user_id='u1'");db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',('unknown-legacy','u1','{"privateUnknownKey":"DO_NOT_DUMP"}',4))
 assert mod.guarded_legacy_save(s,'u1',m()) is False;d=call(u,'/api/privacy/saved-conversations/unknown-legacy')['item'];assert d['bodyAvailable'] is False and d['messageCount'] is None and d['messages']==[];assert 'DO_NOT_DUMP' not in mod.dump(d);assert privacy.Privacy(s,Handler(),Error,lambda *a:None).response()['memory']['available'] is False;u.h.user=None;expect(401,lambda:call(u,'/api/privacy/saved-conversations'))
check('saving optout remains effective, unknown formats are not dumped, memory unavailable and login required',optout_and_unknown)
report={'scope':'Isolated SQLite synthetic saved snapshots; actual frozen privacy/gateway read helpers; no HTTP, build, original DB or real supplier.','productionWrites':False,'pass':all(r['pass'] for r in results),'passed':sum(r['pass'] for r in results),'failed':sum(not r['pass'] for r in results),'results':results,'sourceSha256':hashlib.sha256((ROOT/'04_研发源码/app/r4/backend/privacy_saved.py').read_bytes()).hexdigest()};p=Path(__file__).with_suffix('.json');runs=json.loads(p.read_text(encoding='utf8')).get('runs',[]) if p.exists() else [];runs.append(report);p.write_text(json.dumps({'latest':report,'runs':runs},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:report[k] for k in ('pass','passed','failed')}));sys.exit(0 if report['pass'] else 1)
