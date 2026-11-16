"""Independent in-memory SQLite contract tests. Never opens application databases."""
import contextlib
import hashlib
import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'04_研发源码/app/r4/backend/privacy_retention.py'
spec=importlib.util.spec_from_file_location('retention_under_test',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SCHEMA='''
CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT);
CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT);
CREATE TABLE records(owner TEXT,kind TEXT,day TEXT,data TEXT,created INTEGER,PRIMARY KEY(owner,kind,day));
CREATE TABLE privacy_conversations(id TEXT PRIMARY KEY,user_id TEXT,data TEXT,created INTEGER);
CREATE TABLE privacy_preferences(user_id TEXT PRIMARY KEY,data TEXT,policy_version TEXT,revision INTEGER,updated INTEGER,provider_binding TEXT);
CREATE TABLE privacy_saved_deletions(id TEXT PRIMARY KEY,owner TEXT,snapshot_id TEXT,request_id TEXT,details TEXT,created INTEGER,UNIQUE(owner,snapshot_id),UNIQUE(owner,request_id));
CREATE TABLE ai_gateway_jobs(id TEXT PRIMARY KEY,owner TEXT,status TEXT,cancel_requested INTEGER,output_text TEXT,saved_conversation_id TEXT,reserve_credits INTEGER,charged_credits INTEGER);
CREATE TABLE ai_gateway_provider_consents(owner TEXT,provider_id TEXT,provider_binding TEXT,policy_version TEXT,global_revision INTEGER,categories TEXT,created INTEGER,updated INTEGER,revision TEXT,PRIMARY KEY(owner,provider_id));
CREATE TABLE ai_gateway_wallets(owner TEXT PRIMARY KEY,available INTEGER,reserved INTEGER);
CREATE TABLE timer_runs(id TEXT PRIMARY KEY,owner TEXT,start_ms INTEGER,end_ms INTEGER,last_seen INTEGER,zone TEXT);
CREATE TABLE activity_daily(user_id TEXT,day TEXT,feature TEXT,visits INTEGER,first_seen INTEGER,last_seen INTEGER,last_visit INTEGER,PRIMARY KEY(user_id,day,feature));
CREATE TABLE devices(id TEXT PRIMARY KEY,owner TEXT,device_id TEXT);
CREATE TABLE measurements(id TEXT PRIMARY KEY,connection_id TEXT,metric TEXT,value REAL,unit TEXT,measured_at TEXT);
CREATE TABLE card_draws(id TEXT PRIMARY KEY,owner TEXT,snapshot TEXT);
CREATE TABLE card_draw_actions(owner TEXT,draw_id TEXT,note TEXT);
CREATE TABLE card_practice_events(id TEXT PRIMARY KEY,owner TEXT,draw_id TEXT);
CREATE TABLE card_draw_requests(owner TEXT,draw_id TEXT,request_id TEXT);
CREATE TABLE card_daily_quota(owner TEXT,environment TEXT,business_date TEXT,next_eligible_at INTEGER,created INTEGER);
CREATE TABLE card_zone_preferences(owner TEXT,zone TEXT);
CREATE TABLE card_record_epochs(owner TEXT PRIMARY KEY,revision INTEGER,updated INTEGER);
CREATE TABLE commerce_orders(id TEXT PRIMARY KEY,owner TEXT,total_minor INTEGER);
CREATE TABLE after_sales_finance_links(id TEXT PRIMARY KEY,owner TEXT,amount_minor INTEGER);
'''
class Error(Exception):
 def __init__(self,n,t): self.status=n;super().__init__(t)
class Store:
 def __init__(self,db):self.db=db
 @contextlib.contextmanager
 def connect(self):
  try:yield self.db;self.db.commit()
  except: self.db.rollback();raise
class H:
 user={'id':'A','role':'user'}
 def require(self):return self.user
 def body(self):return self.data
def setup():
 db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row;db.executescript(SCHEMA)
 for x in [('A','user'),('B','user'),('ADMIN','admin')]:db.execute('INSERT INTO users VALUES(?,?)',x)
 policy={'policyVersion':'p1','revision':1,'retention':{'recordsDays':1,'conversationsDays':1,'backupDays':None,'financeDays':None}}
 db.execute('INSERT INTO settings VALUES(?,?)',('privacy',m.dump(policy)))
 for o in ('A','B'):
  db.execute('INSERT INTO privacy_preferences VALUES(?,?,?,?,?,?)',(o,m.dump({**m.FLAGS,'saveConversations':True}),'p1',3,1,'binding'))
  db.execute('INSERT INTO ai_gateway_provider_consents VALUES(?,?,?,?,?,?,?,?,?)',(o,'provider','binding','p1',3,'["general"]',1,1,'consent'))
  db.execute('INSERT INTO ai_gateway_wallets VALUES(?,?,?)',(o,100,20))
  db.execute('INSERT INTO commerce_orders VALUES(?,?,?)',('order'+o,o,101))
  db.execute('INSERT INTO after_sales_finance_links VALUES(?,?,?)',('link'+o,o,100))
 db.execute("INSERT INTO records VALUES('A','old','unknown','historical secret',1)")
 db.execute("INSERT INTO records VALUES('B','old','other','other secret',1)")
 m.init_schema(db);db.commit();h=H();h.user={'id':'A','role':'user'};service=m.PrivacyRetention(Store(db),h,Error,lambda *a:None)
 return db,h,service
def payload(req,scopes=None):return {'requestId':req,'scopes':scopes or list(m.SCOPES)}
def route(s,h,path,method='POST',data=None):h.data=data or {};return s.route(method,path)
def enabled(db):db.execute('UPDATE privacy_retention_config SET data=?',(m.dump({'enabled':True,'policyVersion':'p1','revision':1,'retentionDays':dict.fromkeys(m.SCOPES[2:],1)}),));db.commit()
def age(db):db.execute('UPDATE privacy_retention_tracking SET write_at=?',(int(time.time()*1000)-3*86400000,));db.commit()
def insert_all(db):
 now=int(time.time()*1000)
 for sql,args in [
  ('INSERT INTO records VALUES(?,?,?,?,?)',('A','new','day','record secret',1)),
  ('INSERT INTO privacy_conversations VALUES(?,?,?,?)',('conv','A','conversation secret',1)),
  ('INSERT INTO ai_gateway_jobs VALUES(?,?,?,?,?,?,?,?)',('job','A','running',0,'output secret','conv',20,0)),
  ('INSERT INTO timer_runs VALUES(?,?,?,?,?,?)',('timer','A',1,2,2,'UTC')),
  ('INSERT INTO timer_runs VALUES(?,?,?,?,?,?)',('active','A',1,None,now,'UTC')),
  ('INSERT INTO timer_runs VALUES(?,?,?,?,?,?)',('stale','A',1,None,now-50000,'UTC')),
  ('INSERT INTO activity_daily VALUES(?,?,?,?,?,?,?)',('A','day','feature',1,1,1,1)),
  ('INSERT INTO devices VALUES(?,?,?)',('device','A','device secret')),
  ('INSERT INTO measurements VALUES(?,?,?,?,?,?)',('measure','device','stress',2,'score','unknown')),
  ('INSERT INTO card_draws VALUES(?,?,?)',('draw','A','card secret')),
  ('INSERT INTO card_draw_actions VALUES(?,?,?)',('A','draw','note secret')),
  ('INSERT INTO card_practice_events VALUES(?,?,?)',('practice','A','draw')),
  ('INSERT INTO card_draw_requests VALUES(?,?,?)',('A','draw','req')),
  ('INSERT INTO card_daily_quota VALUES(?,?,?,?,?)',('A','sandbox','day',now+1000,1)),
  ('INSERT INTO card_zone_preferences VALUES(?,?)',('A','UTC'))]:db.execute(sql,args)
 db.commit()
def hash_tables(db,names):return hashlib.sha256(m.dump({n:[tuple(r) for r in db.execute('SELECT * FROM '+n+' ORDER BY rowid')] for n in names}).encode()).hexdigest()
checks=[]
def check(name,fn):
 try:fn();checks.append({'name':name,'pass':True})
 except Exception as e:checks.append({'name':name,'pass':False,'error':str(e)})
def assert_(v):assert v
def reject(fn,n):
 try:fn()
 except Error as e:assert e.status==n;return
 raise AssertionError('expected '+str(n))
db,h,s=setup();insert_all(db)
check('disabled by default',lambda:assert_(json.loads(db.execute('SELECT data FROM privacy_retention_config').fetchone()[0])['enabled'] is False))
check('old age unknown never inferred from created',lambda:assert_(not db.execute("SELECT 1 FROM privacy_retention_tracking WHERE k1='old'").fetchone()))
before=hash_tables(db,['records','privacy_conversations','timer_runs','activity_daily','measurements','card_draws','ai_gateway_wallets','commerce_orders'])
p=route(s,h,'/api/privacy/retention/preview',data=payload('preview01'))['item']
check('preview changes no personal/financial data',lambda:assert_(before==hash_tables(db,['records','privacy_conversations','timer_runs','activity_daily','measurements','card_draws','ai_gateway_wallets','commerce_orders'])))
check('preview future asOf rejected',lambda:reject(lambda:route(s,h,'/api/privacy/retention/preview',data={**payload('future001'),'asOf':9999999999999}),400))
check('unconfirmed extra scope days skip',lambda:assert_(p['summary']['scopes']['cards']['skipReason']=='retention-days-unconfirmed'))
check('disabled actual rejected',lambda:reject(lambda:route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data={'requestId':'disabled1','confirmed':True,'policyVersion':'p1','version':0}),409))
enabled(db);age(db)
p=route(s,h,'/api/privacy/retention/preview',data=payload('preview02'))['item']
check('all six scopes truly eligible',lambda:assert_(all(p['summary']['scopes'][x]['eligible'] for x in m.SCOPES)))
check('active timer excluded; stale uses original45s',lambda:assert_(p['summary']['scopes']['timer']['eligible']==2))
# Change a tracked record and heartbeat a stale timer after preview.
db.execute("UPDATE records SET data='new edit remains' WHERE owner='A' AND kind='new'")
db.execute('UPDATE timer_runs SET last_seen=? WHERE id=?',(int(time.time()*1000),'stale'));db.commit()
financial=['commerce_orders','after_sales_finance_links','ai_gateway_wallets','card_daily_quota','card_zone_preferences'];money=hash_tables(db,financial)
d={'requestId':'apply0001','confirmed':True,'policyVersion':'p1','version':0}
r=route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data=d)
check('edited row survives same plan',lambda:assert_(db.execute("SELECT 1 FROM records WHERE data='new edit remains'").fetchone()))
check('heartbeat after plan survives',lambda:assert_(db.execute("SELECT 1 FROM timer_runs WHERE id='stale'").fetchone()))
check('ended timer truly deleted',lambda:assert_(not db.execute("SELECT 1 FROM timer_runs WHERE id='timer'").fetchone()))
check('saved conversation and linked output deleted',lambda:assert_(not db.execute("SELECT 1 FROM privacy_conversations WHERE id='conv'").fetchone() and db.execute("SELECT output_text IS NULL AND saved_conversation_id IS NULL AND cancel_requested=1 FROM ai_gateway_jobs WHERE id='job'").fetchone()[0]))
check('measurements removed; connection retained',lambda:assert_(not db.execute('SELECT 1 FROM measurements').fetchone() and db.execute('SELECT 1 FROM devices').fetchone()))
check('card body and related personal rows removed',lambda:assert_(all(not db.execute('SELECT 1 FROM '+t).fetchone() for t in ['card_draws','card_draw_actions','card_practice_events','card_draw_requests'])))
check('financial quota untouched',lambda:assert_(money==hash_tables(db,financial)))
check('other account remains',lambda:assert_(db.execute("SELECT data FROM records WHERE owner='B'").fetchone()[0]=='other secret'))
check('unknown age remains',lambda:assert_(db.execute("SELECT 1 FROM records WHERE kind='old' AND owner='A'").fetchone()))
check('epoch invalidates inflight AI',lambda:assert_(db.execute("SELECT revision FROM privacy_preferences WHERE user_id='A'").fetchone()[0]==4 and db.execute("SELECT global_revision FROM ai_gateway_provider_consents WHERE owner='A'").fetchone()[0]==-1))
check('receipt contains counts not body',lambda:assert_('secret' not in m.dump(r) and r['item']['details']['counts']['conversations']==1 and r['item']['details']['changedOrMissingSkipped']==2))
check('replay no extra epoch',lambda:assert_(route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data=d)['replayed'] and db.execute("SELECT revision FROM privacy_preferences WHERE user_id='A'").fetchone()[0]==4))
check('new request stale job version conflict',lambda:reject(lambda:route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data={**d,'requestId':'apply0002'}),409))
adopt=route(s,h,'/api/privacy/retention/adopt-history',data={'scopes':['records'],'confirmed':True,'policyVersion':'p1'})
check('history adoption server protection start',lambda:assert_(adopt['counts']['records']==1 and db.execute("SELECT write_at,basis FROM privacy_retention_tracking WHERE owner='A' AND k1='old'").fetchone()['write_at']==adopt['protectionStart']))
check('adoption never deletes',lambda:assert_(adopt['deleted']==0))
h.user={'id':'ADMIN','role':'admin'}
adminp=route(s,h,'/api/admin/privacy/retention/preview',data={**payload('adminprev',['records']),'owner':'A'})['item']
db.execute("UPDATE users SET role='user' WHERE id='ADMIN'");db.commit()
check('admin downgrade immediately denies',lambda:reject(lambda:route(s,h,'/api/admin/privacy/retention/jobs/'+adminp['id']+'/apply',data={'owner':'A',**d}),403))
h.user={'id':'B','role':'user'}
check('cross account plan cannot apply',lambda:reject(lambda:route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data=d),404))
# Authoritative closure rollback / idempotence / retained facts.
db,h,s=setup();insert_all(db);financial=['commerce_orders','after_sales_finance_links','ai_gateway_wallets','card_daily_quota','card_zone_preferences','devices'];money=hash_tables(db,financial)
db.execute('BEGIN IMMEDIATE');x=m.append_closure_cleanup(db,'A','closure1',m.stamp());db.rollback()
check('closure helper never commits caller transaction',lambda:assert_(db.execute("SELECT 1 FROM records WHERE owner='A'").fetchone()))
db.execute('BEGIN IMMEDIATE');x=m.append_closure_cleanup(db,'A','closure1',m.stamp());db.commit()
check('closure removes all allowed personal bodies',lambda:assert_(all(not db.execute('SELECT 1 FROM '+t).fetchone() for t in ['privacy_conversations','timer_runs','activity_daily','measurements','card_draws']) and not db.execute("SELECT 1 FROM records WHERE owner='A'").fetchone()))
check('closure revokes every flag/binding',lambda:assert_(json.loads(db.execute("SELECT data FROM privacy_preferences WHERE user_id='A'").fetchone()[0])==m.FLAGS and db.execute("SELECT policy_version||provider_binding FROM privacy_preferences WHERE user_id='A'").fetchone()[0]==''))
check('closure retains financial/device/quota exactly',lambda:assert_(money==hash_tables(db,financial)))
check('closure pending provider backup honest',lambda:assert_(x['providersStatus']==x['backupsStatus']=='pending-confirmation' and x['counts']['privacy_conversations']==1))
db.execute('BEGIN IMMEDIATE');x2=m.append_closure_cleanup(db,'A','closure1',m.stamp());db.commit()
check('closure replay no duplicate revision',lambda:assert_(x2['replayed'] and db.execute("SELECT revision FROM privacy_preferences WHERE user_id='A'").fetchone()[0]==4))
check('closure other user never erased',lambda:assert_(db.execute("SELECT 1 FROM records WHERE owner='B'").fetchone()))
# Several batches and recoverable transaction failure, using the same real implementation.
db,h,s=setup();enabled(db)
for i in range(205):db.execute('INSERT INTO records VALUES(?,?,?,?,?)',('A','batch',str(i),'batch body',1))
db.commit();age(db);p=route(s,h,'/api/privacy/retention/preview',data=payload('batchprev',['records']))['item']
for i,expected in enumerate((100,100,5)):
 result=route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data={'requestId':'batchreq'+str(i),'version':i,'policyVersion':'p1','confirmed':True})
 check('bounded resumable batch '+str(i),lambda expected=expected,result=result:assert_(result['item']['details']['counts']['records']==expected))
check('batch205 complete no hidden delete old row',lambda:assert_(db.execute("SELECT count(*) FROM records WHERE owner='A'").fetchone()[0]==1))
db.execute("INSERT INTO records VALUES('A','fail','row','must rollback',1)");db.commit();age(db)
p=route(s,h,'/api/privacy/retention/preview',data=payload('failprev1',['records']))['item']
db.execute("CREATE TRIGGER fail_retention BEFORE DELETE ON records WHEN OLD.kind='fail' BEGIN SELECT RAISE(ABORT,'fixture_failure'); END");db.commit()
try:route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data={'requestId':'failreq01','version':0,'policyVersion':'p1','confirmed':True})
except sqlite3.IntegrityError:pass
check('failed batch leaves no claimed receipt and no epoch bump',lambda:assert_(not db.execute("SELECT 1 FROM privacy_retention_receipts WHERE operation_id LIKE '%failreq01'").fetchone() and db.execute('SELECT version FROM privacy_retention_jobs WHERE id=?',(p['id'],)).fetchone()[0]==0))
db.execute('DROP TRIGGER fail_retention');db.commit()
check('same failed batch request can recover',lambda:assert_(route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data={'requestId':'failreq01','version':0,'policyVersion':'p1','confirmed':True})['item']['details']['counts']['records']==1))
db.execute('BEGIN IMMEDIATE')
check('legacy record missing epoch denied after cleanup',lambda:reject(lambda:m.guard_record_epoch(db,'A',None,Error),409))
check('legacy record stale epoch denied after cleanup',lambda:reject(lambda:m.guard_record_epoch(db,'A',3,Error),409))
check('legacy record fresh epoch accepted',lambda:assert_(m.guard_record_epoch(db,'A',m.record_erasure_epoch(db,'A'),Error) is None))
db.rollback()
db,h,s=setup();enabled(db)
db.execute("UPDATE privacy_preferences SET revision=90 WHERE user_id='A'");db.commit();db.execute('BEGIN IMMEDIATE')
check('consent-only changes never block epoch0 legacy records',lambda:assert_(m.guard_record_epoch(db,'A',None,Error) is None));db.rollback()
db.execute("INSERT INTO privacy_conversations VALUES('only-conversation','A','synthetic',1)");db.commit();age(db)
p=route(s,h,'/api/privacy/retention/preview',data=payload('convonly1',['conversations']))['item']
route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data={'requestId':'convapply1','version':0,'policyVersion':'p1','confirmed':True})
check('conversation-only expiry does not change records erasure epoch',lambda:assert_(m.record_erasure_epoch(db,'A')==0))
check('conversation-only expiry never cancels an unrelated card draw epoch',lambda:assert_(not db.execute("SELECT 1 FROM card_record_epochs WHERE owner='A'").fetchone()))
check('conversation-only cleanup does invalidate AI consent revision',lambda:assert_(db.execute("SELECT revision FROM privacy_preferences WHERE user_id='A'").fetchone()[0]==91))
db.execute("INSERT INTO card_draws VALUES('new-card','A','body')");db.commit();age(db)
p=route(s,h,'/api/privacy/retention/preview',data=payload('noteprev1',['cards']))['item']
db.execute("INSERT INTO card_draw_actions VALUES('A','new-card','new feeling')");db.commit()
result=route(s,h,'/api/privacy/retention/jobs/'+p['id']+'/apply',data={'requestId':'noteapply1','version':0,'policyVersion':'p1','confirmed':True})
check('late card note protects draw and note from prior plan',lambda:assert_(result['item']['details']['counts']['cards']==0 and db.execute("SELECT 1 FROM card_draw_actions WHERE draw_id='new-card'").fetchone()))
report={'pass':all(x['pass'] for x in checks),'passed':sum(x['pass'] for x in checks),'failed':sum(not x['pass'] for x in checks),'checks':checks,'sourceSHA256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'scope':'in-memory SQLite; no live service or original DB'}
if '--fixture' in sys.argv:
 (ROOT/'06_验证与后续工作/负责人优化建议-到期清理测试夹具.json').write_bytes(json.dumps({'schema':SCHEMA},ensure_ascii=False).encode())
out=ROOT/'06_验证与后续工作/负责人优化建议-到期清理Python内存结果.json';out.write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode())
print(json.dumps(report,ensure_ascii=True));sys.exit(0 if report['pass'] else 1)
