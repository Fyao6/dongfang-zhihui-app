"""Fresh generated SQLite only; no service/original database/provider."""
import hashlib,json,sqlite3,sys,threading,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
BACK=ROOT/'04_研发源码/app/r4/backend';sys.path.insert(0,str(BACK))
import server,account_closure as M,privacy_retention as R,account_write_guard as W
from commerce import Commerce
results=[]
class Error(Exception):
 def __init__(self,status,message):super().__init__(message);self.status=status
def expect(status,fn):
 try:fn()
 except Error as e:assert e.status==status,(status,e.status);return
 raise AssertionError('expected status '+str(status))
def blocked(fn,needle='account_'):
 try:fn()
 except sqlite3.IntegrityError as e:assert needle in str(e);return
 raise AssertionError('expected atomic trigger rejection')
class Handler:
 def __init__(self,f,owner='buyer',token=None):
  self.f=f;self.owner=owner;self.session_token=token or 'fixture-session-'+owner;self.cookies_out=[];self.data={}
  with f.store.connect() as db:self.user=db.execute('SELECT * FROM users WHERE id=?',(owner,)).fetchone()
 def require(self,roles=None):
  if not self.user:raise Error(401,'login')
  if roles and self.user['role'] not in roles:raise Error(403,'role')
  return self.user
 def body(self):return self.data
class Fixture:
 def __init__(self):
  self.path=ROOT/'06_验证与后续工作'/('负责人优化建议-注销内存-'+uuid4().hex+'.sqlite3')
  self.store=server.Store(self.path);self.now=int(time.time()*1000)
  with self.store.connect() as db:
   R.init_schema(db);M.init_schema(db)
   for owner,role in [('buyer','user'),('other','user'),('admin','admin'),('admin2','admin')]:
    db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(owner,'qa_'+owner,server.password_hash('fixture-password-123'),'QA',role,self.now))
    db.execute('INSERT INTO sessions VALUES(?,?,?)',(M.digest('fixture-session-'+owner),owner,self.now+86400000))
   db.execute('INSERT INTO sessions VALUES(?,?,?)',(M.digest('fixture-session-buyer-second'),'buyer',self.now+86400000))
   for owner in ['buyer','other']:
    db.execute('INSERT INTO records VALUES(?,?,?,?,?)',(owner,'life','2026-01-01','{"private":"fixture"}',self.now))
    db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',(owner+'-snapshot',owner,'[]',self.now))
    db.execute('INSERT INTO privacy_preferences VALUES(?,?,?,?,?,?)',(owner,json.dumps(dict.fromkeys(R.FLAGS,True)),'fixture',8,self.now,'binding'))
    db.execute('INSERT INTO ai_gateway_provider_consents VALUES(?,?,?,?,?,?,?,?,?)',(owner,'fixture','binding','fixture',8,'["general"]',self.now,self.now,'old-nonce'))
  self.h=Handler(self)
 def mod(self,h=None,cleanup=None):return M.AccountClosure(self.store,h or self.h,Error,lambda *a:None,server.check_password,cleanup or R.append_closure_cleanup,clock=lambda:self.now)
 def call(self,path,data=None,h=None,method='POST',cleanup=None):
  h=h or self.h;h.data=data or {};return self.mod(h,cleanup).route(method,'/api/account-closure/'+path)
 def prepare(self,h=None,key='fixture-request',nonce='a'*64):
  d={'requestId':key,'nonce':nonce,'password':'fixture-password-123'}
  c=self.call('prepare',d,h)
  return dict(requestId=key,nonce=nonce,challengeId=c['challengeId'],confirmed=True,renewalAcknowledged=True)
 def close(self,h=None):return self.call('confirm',self.prepare(h),h)
 def scalar(self,s,*a):
  with self.store.connect() as db:return db.execute(s,a).fetchone()[0]
def check(name,fn):
 try:fn();results.append(dict(name=name,pass_=True))
 except Exception as e:results.append(dict(name=name,pass_=False,error=type(e).__name__+': '+str(e)))
def closure():
 f=Fixture();d=f.prepare();r=f.call('confirm',d)
 assert r['receipt']['accountClosed'] and r['receipt']['sessionsRevoked']
 assert r['receipt']['providersStatus']=='pending-confirmation' and not r['receipt']['thirdPartyRenewalCancelled']
 assert f.scalar("SELECT count(*) FROM sessions WHERE user_id='buyer'")==0
 assert f.scalar("SELECT count(*) FROM account_revoked_sessions WHERE owner='buyer'")==2
 assert f.scalar("SELECT count(*) FROM records WHERE owner='buyer'")==0
 assert f.scalar("SELECT count(*) FROM privacy_conversations WHERE user_id='buyer'")==0
 assert f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'")==9
 assert f.scalar("SELECT provider_binding FROM privacy_preferences WHERE user_id='buyer'")==''
 assert f.scalar("SELECT global_revision FROM ai_gateway_provider_consents WHERE owner='buyer'")==-1
 assert f.scalar("SELECT revision FROM ai_gateway_provider_consents WHERE owner='buyer'")!='old-nonce'
 assert f.scalar("SELECT count(*) FROM records WHERE owner='other'")==1
 assert f.scalar("SELECT count(*) FROM users WHERE id='buyer'")==1
 assert not f.h.cookies_out
 assert not server.check_password('fixture-password-123',f.scalar("SELECT password FROM users WHERE id='buyer'"))
check('actual authoritative cleanup and all session tombstones are atomic; other owner and users kept',closure)
def wrong():
 f=Fixture();expect(401,lambda:f.call('prepare',dict(requestId='fixture-request',nonce='a'*64,password='wrong')))
 assert f.scalar('SELECT count(*) FROM account_closure_challenges')==0
check('current password is mandatory and verified by actual existing Python verifier',wrong)
def flags():
 f=Fixture();d=f.prepare()
 for k,v in [('confirmed',False),('confirmed',1),('renewalAcknowledged',False)]:
  x=dict(d);x[k]=v
  try:f.call('confirm',x)
  except ValueError:pass
  else:raise AssertionError('confirmation not strict')
 assert f.scalar('SELECT count(*) FROM account_lifecycle')==0
check('second confirmation and independent renewal acknowledgement are strict',flags)
def account_scope():
 f=Fixture();d=f.prepare();expect(404,lambda:f.call('confirm',d,Handler(f,'other')))
 expect(404,lambda:f.call('confirm',d,Handler(f,'buyer','fixture-session-buyer-second')))
check('challenge binds actual owner and exact current session',account_scope)
def expiry():
 f=Fixture();d=f.prepare();f.now+=M.CHALLENGE_TTL_MS
 expect(409,lambda:f.call('confirm',d))
 assert f.scalar('SELECT count(*) FROM account_closure_receipts')==0
 assert f.scalar("SELECT count(*) FROM records WHERE owner='buyer'")==1
check('expired challenge rolls whole claim/cleanup/session state back',expiry)
def credentials():
 f=Fixture();d=f.prepare()
 with f.store.connect() as db:db.execute("DELETE FROM sessions WHERE user_id='buyer'")
 expect(409,lambda:f.call('confirm',d))
check('password/session revocation after password check invalidates final claim',credentials)
def conflicts():
 f=Fixture();f.prepare();expect(409,lambda:f.prepare(nonce='b'*64))
check('same request id cannot change nonce or session',conflicts)
def replay():
 f=Fixture();d=f.prepare();r=f.call('confirm',d);rev=f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'")
 f.h.user=None
 assert f.call('confirm',d)['receipt']==r['receipt']
 assert f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'")==rev
 bad=dict(d,nonce='b'*64);expect(404,lambda:f.call('confirm',bad))
 expect(404,lambda:f.call('confirm',d,Handler(f,'other')))
check('lost response replay works after sessions gone without duplicate cleanup; foreign replay rejected',replay)
def last_admin():
 f=Fixture();a=Handler(f,'admin');b=Handler(f,'admin2');da=f.prepare(a);dbody=f.prepare(b)
 f.call('confirm',da,a);expect(409,lambda:f.call('confirm',dbody,b))
 assert f.scalar("SELECT count(*) FROM sessions WHERE user_id='admin2'")==1
 assert f.call('status',h=b,method='GET')['lastActiveAdmin']
check('two admins cannot close the last active admin even after both prepare',last_admin)
def late_owned():
 f=Fixture();f.close()
 with f.store.connect() as db:
  blocked(lambda:db.execute('INSERT INTO records VALUES(?,?,?,?,?)',('buyer','life','2026-01-02','{}',f.now)))
  blocked(lambda:db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',('late','buyer','[]',f.now)))
  blocked(lambda:db.execute('INSERT INTO sessions VALUES(?,?,?)',('late','buyer',f.now+999)))
  blocked(lambda:db.execute("UPDATE privacy_preferences SET data='{}' WHERE user_id='buyer'"))
  blocked(lambda:db.execute("UPDATE users SET password='tamper' WHERE id='buyer'"))
check('already-authorized late records/conversations/sessions/preferences/credentials writes cannot resurrect',late_owned)
def rollback():
 f=Fixture();d=f.prepare()
 def fail(db,*a):
  R.append_closure_cleanup(db,*a);raise RuntimeError('injected failure')
 try:f.call('confirm',d,cleanup=fail)
 except RuntimeError:pass
 else:raise AssertionError('injected failure absent')
 assert f.scalar('SELECT count(*) FROM account_lifecycle')==0
 assert f.scalar("SELECT count(*) FROM records WHERE owner='buyer'")==1
 assert f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'")==8
 assert f.scalar('SELECT count(*) FROM account_closure_receipts')==0
check('cleanup failure rolls back closure claim and every personal/session mutation',rollback)
def parallel():
 f=Fixture();d=f.prepare();out=[];errors=[]
 def run():
  try:out.append(f.call('confirm',d,Handler(f)))
  except Exception as e:errors.append(str(e))
 threads=[threading.Thread(target=run) for _ in range(2)]
 for t in threads:t.start()
 for t in threads:t.join()
 assert not errors,errors
 assert len(out)==2 and out[0]['receipt']['id']==out[1]['receipt']['id']
 assert f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'")==9
check('real SQLite concurrent same challenge commits once and replays same receipt',parallel)
def paid():
 f=Fixture();admin=Handler(f,'admin')
 def commerce(h,p,d=None,method='POST'):
  h.data=d or {};h.path=p;return Commerce(f.store,h,Error,lambda *a:None).route(method,p)
 commerce(admin,'/api/admin/commerce/settings',dict(sandboxEnabled=True,productionEnabled=False), 'PATCH')
 prod=commerce(admin,'/api/admin/commerce/products',dict(title='QA physical',description='QA',type='physical',sku='fixture-physical',priceMinor=100,currency='USD',stock=2,shippingCountries=['US'],shippingMinor=0,taxMinor=0,environment='sandbox',status='published'))
 sku=prod.get('item',prod).get('skuId')
 assert sku,prod
 order=commerce(f.h,'/api/commerce/orders',dict(requestId='paid-order-request',environment='sandbox',items=[dict(skuId=sku,quantity=1)],shippingAddress=dict(name='QA',address='fixture',phone='000000000',city='fixture',postalCode='000',country='US')))
 oid=order.get('order',order)['id']
 pay=commerce(f.h,'/api/commerce/orders/'+oid+'/sandbox-pay',dict(requestId='paid-pay-request'))
 with f.store.connect() as db:
  before={t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in ['commerce_orders','commerce_order_items','commerce_payment_events','commerce_entitlements','commerce_inventory_events']}
 f.close()
 with f.store.connect() as db:
  for t,rows in before.items():assert [tuple(r) for r in db.execute('SELECT * FROM '+t)]==rows,t
 item=before['commerce_order_items'][0][0]
 commerce(admin,'/api/admin/commerce/orders/'+oid+'/refund',dict(requestId='refund-after-closure',items=[dict(itemId=item,quantity=1)]))
 assert f.scalar("SELECT refunded_quantity FROM commerce_order_items WHERE id=?",item)==1
 with f.store.connect() as db:
  assert db.execute("SELECT 1 FROM commerce_payment_events WHERE order_id=? AND kind='refund' AND status='applied'",(oid,)).fetchone()
  class RefundOnly:
   def execute(self,sql,args=()):
    import re
    return db.execute(re.sub(r"p\.kind IN \([^)]+\)",r"\g<0> AND p.kind='refund'",sql),args)
  assert W.validate_fact(RefundOnly(),('order',oid,'buyer'))

check('actual unified paid order/financial ledger untouched by closure; active admin can settle existing refund',paid)
def safe_receipt():
 f=Fixture();r=f.close();s=json.dumps(r)
 assert 'fixture-password' not in s and 'fixture-session' not in s and 'nonce_hash' not in s and 'operation_nonce' not in s
 with f.store.connect() as db:
  try:M.require_active(db,'buyer',Error)
  except Error as e:assert e.status==401
  else:raise AssertionError('closed helper did not reject')
check('minimal response contains no credential/session/nonce and exported auth helper fails closed',safe_receipt)

def guarded_fixture():
 f=Fixture();original=f.store.connect
 from contextlib import contextmanager
 @contextmanager
 def connect():
  with original() as db:yield W.guard_connection(db)
 f.store.connect=connect
 return f
def body_race(kind):
 f=guarded_fixture();owner='admin2' if kind in ('settings','role') else 'buyer'
 cls=server.make_handler(f.store,ROOT/'03_当前APP')
 h=object.__new__(cls);source=Handler(f,owner);h.user=source.user;h.owner=owner;h.session_token=source.session_token;h.cookies_out=[]
 called=threading.Event();release=threading.Event();errors=[]
 payload={'theme':{'--bg':'#123456'}} if kind=='settings' else {'role':'teacher'} if kind=='role' else {'title':'late','body':'late','status':'pending'}
 def body(*a):called.set();assert release.wait(10);return payload
 h.body=body
 original_require=h.require
 def require(roles=None):
  user=original_require(roles);W.require_roles(roles);return user
 h.require=require
 if kind=='upload':
  from email.message import Message
  headers=Message();headers['Content-Length']='8';headers['Content-Type']='image/png';h.headers=headers
  class Stream:
   def read(self,size):called.set();assert release.wait(10);return b'\x89PNG\r\n\x1a\n'
  h.rfile=Stream();h.send=lambda *a:None
 with f.store.connect() as db:before={t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in ['settings','users','posts','media']}
 def worker():
  token=W.begin_actor(owner,M.digest(h.session_token))
  try:
   if kind=='settings':h.admin('POST','/api/admin/settings')
   elif kind=='role':h.admin('PATCH','/api/admin/users/other')
   elif kind=='community':h.community('POST','/api/community/posts')
   else:h.upload()
  except Exception as e:errors.append(e)
  finally:W.end_actor(token)
 t=threading.Thread(target=worker);t.start();assert called.wait(10);f.close(Handler(f,owner));release.set();t.join(10)
 assert not t.is_alive()
 assert len(errors)==1 and isinstance(errors[0],sqlite3.IntegrityError) and 'account_actor_inactive' in str(errors[0]),[str(x) for x in errors]
 with f.store.connect() as db:
  for table,rows in before.items():
   after=[tuple(r) for r in db.execute('SELECT * FROM '+table)]
   if table=='users':
    rows=[r[:2]+r[3:] for r in rows];after=[r[:2]+r[3:] for r in after]
   assert after==rows,table
 assert f.scalar('SELECT count(*) FROM account_action_fences')==0
for kind in ['settings','role','community','upload']:
 check('actual Python '+kind+' require passes/body waits/other session closes/final mutation is denied',lambda kind=kind:body_race(kind))
def guarded_closure():
 f=guarded_fixture();token=W.begin_actor('buyer',M.digest(f.h.session_token))
 try:r=f.close()
 finally:W.end_actor(token)
 assert r['receipt']['accountClosed'] and f.scalar('SELECT count(*) FROM account_action_fences')==0
check('guarded Python closure may revoke its own session inside one transaction; ephemeral fence empty',guarded_closure)
def role_fence():
 f=guarded_fixture()
 with f.store.connect() as db:db.execute("UPDATE users SET role='user' WHERE id='admin2'")
 token=W.begin_actor('admin2',M.digest('fixture-session-admin2'));W.require_roles(['admin'])
 try:
  with f.store.connect() as db:blocked(lambda:db.execute("UPDATE settings SET data='{}' WHERE key='theme'"),'account_actor_inactive')
 finally:W.end_actor(token)
check('Python final SQL checks fresh role, not cached require result',role_fence)
def targets():
 f=Fixture()
 with f.store.connect() as db:
  db.execute("INSERT INTO contents VALUES('teachers','fixture-teacher',?,'published',0,?)",(json.dumps({'creatorId':'buyer','profileType':'real','verified':True}),f.now))
  db.execute("INSERT INTO messages VALUES('retained','other','buyer','fixture',?)",(f.now,))
  db.execute("INSERT INTO devices VALUES('fixture-device','buyer','fixture','fixture','body','connected',?)",(f.now,))
 f.close()
 with f.store.connect() as db:
  blocked(lambda:db.execute("INSERT INTO friendships VALUES('other','buyer','pending',?)",(f.now,)),'account_target_closed')
  blocked(lambda:db.execute("INSERT INTO messages VALUES('late','other','buyer','fixture',?)",(f.now,)),'account_target_closed')
  blocked(lambda:db.execute("INSERT INTO service_requests VALUES('late','other','fixture-teacher','QA','fixture','2026-12-01','pending',?)",(f.now,)),'account_target_closed')
  blocked(lambda:db.execute("INSERT INTO measurements VALUES('late','fixture-device','fixture',1,'x','2026-11-01T00:00:00Z')"))
  assert not M.can_book_teacher(db,'fixture-teacher',{'creatorId':'buyer'})
  assert db.execute("SELECT 1 FROM messages WHERE id='retained'").fetchone()
check('closed teacher/recipient/device cannot receive new personal facts; retained messages remain',targets)
def session_proof():
 f=guarded_fixture()
 with f.store.connect() as db:db.execute("DELETE FROM sessions WHERE user_id='admin2'")
 token=W.begin_actor('admin2',M.digest('fixture-session-admin2'))
 try:
  with W.settlement_scope('session','admin2','admin2'):
   with f.store.connect() as db:
    db.execute('INSERT INTO sessions VALUES(?,?,?)',(M.digest('new-proof-session'),'admin2',f.now+99999))
    blocked(lambda:db.execute("UPDATE settings SET data='{}' WHERE key='theme'"),'account_settlement_denied')
 finally:W.end_actor(token)
 assert f.scalar("SELECT count(*) FROM sessions WHERE user_id='admin2'")==1
check('verified-session internal scope survives valid password session revocation but rejects other writes',session_proof)

out=Path(__file__).with_suffix('.json')
report=dict(scope='fresh SQLite, real server password verifier and authoritative retention; no HTTP or original DB',passed=sum(x['pass_'] for x in results),failed=sum(not x['pass_'] for x in results),results=[dict(name=x['name'],**{'pass':x['pass_']},**({'error':x['error']} if 'error' in x else {})) for x in results],sourceSha256={n:hashlib.sha256((BACK/n).read_bytes()).hexdigest() for n in ['account_closure.py','account_write_guard.py','privacy_retention.py']})
old=json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
runs=old.get('runs',[]);runs.append(report);out.write_text(json.dumps(dict(latest=report,runs=runs),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['passed','failed']}))
sys.exit(bool(report['failed']))
