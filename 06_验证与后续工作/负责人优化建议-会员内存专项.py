"""Explicit isolated unified-commerce subscription fixtures. No real provider is called."""
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime,timezone
import ast,copy,hashlib,json,sqlite3,sys,threading
ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/'04_研发源码/app/r4/backend';sys.path.insert(0,str(BACKEND))
import commerce as co
import membership_lifecycle as mb
class Error(Exception):
    def __init__(self,status,message):self.status,self.message=status,message
class Store:
    def __init__(self):
        self.db=sqlite3.connect(':memory:',check_same_thread=False);self.db.row_factory=sqlite3.Row;self.lock=threading.RLock();self.audits=[]
        self.db.executescript("CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT NOT NULL);CREATE TABLE users(id TEXT PRIMARY KEY);CREATE TABLE contents(kind TEXT,id TEXT,data TEXT,status TEXT,position INTEGER);CREATE TABLE media(id TEXT PRIMARY KEY,mime TEXT,owner TEXT);")
        co.init_schema(self.db);mb.init_schema(self.db);self.db.executemany('INSERT INTO users VALUES(?)',[('u1',),('u2',),('admin',)]);self.db.commit()
    @contextmanager
    def connect(self):
        with self.lock:
            with self.db:yield self.db
    def setting(self,key):
        with self.connect() as db:
            r=db.execute('SELECT data FROM settings WHERE key=?',(key,)).fetchone();return json.loads(r['data']) if r else {}
    def audit(self,db,actor,action,target,detail=''):self.audits.append((actor,action,target,detail))
class Handler:
    def __init__(self,id='u1',role='user'):self.user={'id':id,'role':role};self.path='';self.payload={}
    def require(self,roles=None):
        if not self.user:raise Error(401,'login')
        if roles and self.user['role'] not in roles:raise Error(403,'role')
        return self.user
    def body(self):return copy.deepcopy(self.payload)
store=Store();user=Handler();other=Handler('u2');admin=Handler('admin','admin');clock={'now':co.now()}
member=mb.Membership(store,user,Error,lambda *a:None,test_clock=lambda:clock['now'])
other_member=mb.Membership(store,other,Error,lambda *a:None,test_clock=lambda:clock['now'])
manager=mb.Membership(store,admin,Error,lambda *a:None,test_clock=lambda:clock['now'])
commerce=co.Commerce(store,user,Error,lambda *a:None);co_admin=co.Commerce(store,admin,Error,lambda *a:None)
def api(module,h,path,body=None,method='POST'):h.path=path;h.payload=body or {};return module.route(method,path.partition('?')[0])
def check(name,action):
    try:action();results.append({'name':name,'pass':True})
    except Exception as e:results.append({'name':name,'pass':False,'errorType':type(e).__name__,'error':str(e)[:180]})
def expect(status,fn):
    try:fn()
    except Error as e:assert e.status==status,(e.status,status);return
    raise AssertionError('expected '+str(status))
results=[]
check('default production catalog empty and real channels closed',lambda:__import__('builtins').exec("assert not api(member,user,'/api/membership/catalog',method='GET')['items'];assert api(member,user,'/api/membership/status',method='GET')['externalChannels'][0]['verificationEnabled'] is False",globals()))
check('nonadmin cannot configure',lambda:expect(403,lambda:api(member,user,'/api/admin/membership/settings',{'sandboxEnabled':True,'revision':0})))
check('production cannot be enabled',lambda:expect(400,lambda:api(manager,admin,'/api/admin/membership/settings',{'sandboxEnabled':True,'productionEnabled':True,'revision':0},'PATCH')))
api(manager,admin,'/api/admin/membership/settings',{'sandboxEnabled':True,'productionEnabled':False,'revision':0},'PATCH')
api(co_admin,admin,'/api/admin/commerce/settings',{'sandboxEnabled':True,'productionEnabled':False},'PATCH')
def product(group,kind='membership'):
    return co_admin.save_product({'title':'Synthetic '+group,'description':'Isolated fixture only','type':kind,'sku':'fixture-'+group,'priceMinor':500,'currency':'USD','stock':100,'shippingCountries':[],'shippingMinor':0,'taxMinor':0,'environment':'sandbox','status':'published','contentId':'course-fixture' if kind=='digital' else ''})['item']
def plan(product,group):
    return {'environment':'sandbox','status':'published','skuId':product['skuId'],'groupId':group,'title':'Synthetic '+group,'description':'Isolated finite subscription','billingMode':'recurring','term':{'unit':'month','count':1},'renewalPriceMinor':500,'benefits':{'catalogScope':'member_catalog','courseIds':[],'aiCredits':None,'aiResetCycle':'none','other':['synthetic sandbox benefit']},'ruleVersion':'fixture-rule-1','termsVersion':'fixture-terms-1','serviceTerms':'Synthetic sandbox only, no actual billing','refundPolicy':'Request then review, no automatic refund','graceDays':2,'trialDays':0,'promotionsEnabled':False}
prod=product('main');draft=plan(prod,'main');p=api(manager,admin,'/api/admin/membership/plans',draft)['item']
check('public plan uses unified integer money and explicit nullable AI quota',lambda:__import__('builtins').exec("assert p['firstPriceMinor']==500 and p['currency']=='USD' and p['benefits']['aiCredits'] is None;assert api(member,user,'/api/membership/catalog?environment=sandbox',method='GET')['items'][0]['purchasable']",globals()))
check('unconfirmed trial and unlimited AI refused',lambda:expect(400,lambda:api(manager,admin,'/api/admin/membership/plans',{**draft,'trialDays':7})))
check('real channel mappings cannot be activated',lambda:expect(400,lambda:api(manager,admin,'/api/admin/membership/channel-mappings',{'environment':'sandbox','channel':'apple','externalProductId':'synthetic.apple','planId':p['id'],'planVersion':1,'status':'published'})))
mapping=api(manager,admin,'/api/admin/membership/channel-mappings',{'environment':'sandbox','channel':'apple','externalProductId':'synthetic.apple','planId':p['id'],'planVersion':1,'status':'draft'})
check('draft channel map does not imply verified integration',lambda:__import__('builtins').exec("assert mapping['item']['integrationEnabled'] is False",globals()))
serial={'n':0}
def order_with_hook(product,renewal=None,who=member,cm=commerce):
    serial['n']+=1;items=[{'skuId':product['skuId'],'quantity':1}]
    with store.connect() as db:snapshot=who.snapshot_for_checkout(db,who.owner,items,'sandbox',renewal)
    order=cm.create_order({'requestId':'fixture-order-'+str(serial['n']),'environment':'sandbox','items':items})
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');who.capture_order_snapshots(db,who.owner,order['id'],snapshot)
    return order,snapshot
order,snap=order_with_hook(prod)
terms=api(member,user,'/api/membership/orders/'+order['id']+'/snapshots',method='GET')
check('unpaid order terms are owner-only immutable checkout snapshot',lambda:__import__('builtins').exec("assert terms['items'][0]['planVersion']==1 and terms['items'][0]['ruleVersion']=='fixture-rule-1' and terms['items'][0]['firstPriceMinor']==500",globals()))
check('another account cannot read checkout terms',lambda:expect(404,lambda:api(other_member,other,'/api/membership/orders/'+order['id']+'/snapshots',method='GET')))
check('unpaid order cannot activate',lambda:expect(409,lambda:api(member,user,'/api/membership/orders/'+order['id']+'/activate',{})))
check('unpaid same-group duplicate blocked before any payment',lambda:expect(409,lambda:order_with_hook(prod)))
commerce.pay(order['id'],{'requestId':'fixture-pay-1'});clock['now']=co.now()
activated=api(member,user,'/api/membership/orders/'+order['id']+'/activate',{});sub=activated['items'][0];sid=sub['id']
check('paid unified order activates isolated subscription only',lambda:__import__('builtins').exec("assert sub['status']=='active' and sub['hasSandboxAccess'] and not sub['grantsProductionAccess'] and not sub['actualBillingEnabled'];assert store.db.execute('SELECT count(*) FROM commerce_orders').fetchone()[0]==2;assert store.db.execute('SELECT member FROM users LIMIT 1').fetchone() is None",globals()) if False else __import__('builtins').exec("assert sub['status']=='active' and sub['hasSandboxAccess'] and sub['grantsProductionAccess'] is False and sub['actualBillingEnabled'] is False;assert store.db.execute('SELECT count(*) FROM commerce_payment_events').fetchone()[0]==1",globals()))
again=api(member,user,'/api/membership/orders/'+order['id']+'/activate',{})
check('repeated activation has one subscription and payment',lambda:__import__('builtins').exec("assert again['items'][0]['id']==sid;assert store.db.execute('SELECT count(*) FROM membership_subscriptions').fetchone()[0]==1;assert store.db.execute('SELECT count(*) FROM commerce_payment_events').fetchone()[0]==1",globals()))
check('another account cannot activate or cancel',lambda:(expect(404,lambda:api(other_member,other,'/api/membership/orders/'+order['id']+'/activate',{})),expect(404,lambda:api(other_member,other,'/api/membership/subscriptions/'+sid+'/cancel-renewal',{'requestId':'cross'}))))
p2=api(manager,admin,'/api/admin/membership/plans',{**draft,'id':p['id'],'version':1,'ruleVersion':'fixture-rule-2','refundPolicy':'Changed later'})['item']
read=api(member,user,'/api/membership/status',method='GET')['items'][0]
check('later plan edits preserve purchased rule version and terms',lambda:__import__('builtins').exec("assert read['plan']['version']==1 and read['plan']['ruleVersion']=='fixture-rule-1' and read['plan']['refundPolicy']!='Changed later'",globals()))
check('active duplicate purchase denied',lambda:expect(409,lambda:order_with_hook(prod)))
renewal_order,_=order_with_hook(prod,sid);commerce.pay(renewal_order['id'],{'requestId':'fixture-pay-renew'});renewed=api(member,user,'/api/membership/orders/'+renewal_order['id']+'/activate',{})['items'][0]
check('renewal requires new paid order and extends same subscription once',lambda:__import__('builtins').exec("assert renewed['id']==sid and len(renewed['periods'])==2 and renewed['periodEnd']>sub['periodEnd'];assert renewed['plan']['version']==2",globals()))
req=api(member,user,'/api/membership/subscriptions/'+sid+'/refund-request',{'requestId':'refund-request','reason':'Synthetic review'})
req2=api(member,user,'/api/membership/subscriptions/'+sid+'/refund-request',{'requestId':'refund-request','reason':'Synthetic review'})
check('refund request is separate pending unified aftersale, not a refund',lambda:__import__('builtins').exec("assert req['request']['id']==req2['request']['id'] and req['fundsRefunded'] is False;assert store.db.execute(\"SELECT count(*) FROM commerce_payment_events WHERE kind='refund'\").fetchone()[0]==0;assert store.db.execute('SELECT count(*) FROM commerce_aftersale_requests').fetchone()[0]==1",globals()))
check('refund request conflicts on changed reason',lambda:expect(409,lambda:api(member,user,'/api/membership/subscriptions/'+sid+'/refund-request',{'requestId':'refund-request','reason':'Different'})))
cancelled=api(member,user,'/api/membership/subscriptions/'+sid+'/cancel-renewal',{'requestId':'cancel-1'});cancel_again=api(member,user,'/api/membership/subscriptions/'+sid+'/cancel-renewal',{'requestId':'cancel-1'})
check('cancel keeps paid access and dates, stops only sandbox renewal idempotently',lambda:__import__('builtins').exec("assert cancelled['status']=='cancelled_active' and cancelled['hasSandboxAccess'] and not cancelled['autoRenew'] and cancelled['nextChargeAt'] is None;assert cancelled['periodEnd']==renewed['periodEnd'] and cancel_again['version']==cancelled['version']",globals()))
restored=api(member,user,'/api/membership/restore',{'requestId':'restore','environment':'sandbox','orderId':order['id']})
check('restore preserves cancellation and original paid period',lambda:__import__('builtins').exec("assert restored['items'][0]['id']==sid and restored['items'][0]['periodEnd']==cancelled['periodEnd'] and not restored['items'][0]['autoRenew'] and not restored['providerVerified']",globals()))
check('real-channel restore is explicitly unavailable',lambda:expect(403,lambda:api(member,user,'/api/membership/restore',{'requestId':'real','environment':'production','receipt':'not-a-receipt'})))
check('cross-account restore is rejected',lambda:expect(404,lambda:api(other_member,other,'/api/membership/restore',{'requestId':'cross-restore','environment':'sandbox','orderId':order['id']})))
prod_state=product('state');sp=api(manager,admin,'/api/admin/membership/plans',plan(prod_state,'state'))['item'];so,_=order_with_hook(prod_state);commerce.pay(so['id'],{'requestId':'pay-state'});clock['now']=co.now();state_sub=api(member,user,'/api/membership/orders/'+so['id']+'/activate',{})['items'][0];state_id=state_sub['id']
def state_event(event,key):
    return api(manager,admin,'/api/admin/membership/sandbox-events',{'requestId':key,'environment':'sandbox','subscriptionId':state_id,'event':event})
failed=state_event('renewal_failed','failed');grace=state_event('grace_started','grace');paused=state_event('paused','paused');held=state_event('account_hold','held');resumed=state_event('resumed','resumed')
check('sandbox failure grace pause hold resume derive from paid subscription without adding time',lambda:__import__('builtins').exec("assert [failed['status'],grace['status'],paused['status'],held['status'],resumed['status']]==['renewal_failed','grace','paused','past_due','active'];assert grace['graceEnd']==state_sub['periodEnd']+2*86400000 and not paused['hasSandboxAccess'] and not held['hasSandboxAccess'];assert resumed['periodEnd']==state_sub['periodEnd']",globals()))
check('nonadmin cannot simulate lifecycle events',lambda:expect(403,lambda:api(member,user,'/api/admin/membership/sandbox-events',{'requestId':'fake','environment':'sandbox','subscriptionId':state_id,'event':'paused'})))
check('status event cannot claim payment or add time',lambda:expect(400,lambda:state_event('payment_succeeded','fake-pay')))
check('early expiry event denied',lambda:expect(409,lambda:state_event('expired','early-expiry')))
paused=state_event('paused','pause-again');paused_cancel=api(member,user,'/api/membership/subscriptions/'+state_id+'/cancel-renewal',{'requestId':'cancel-paused'})
check('cancelling paused subscription does not re-enable access',lambda:__import__('builtins').exec("assert paused_cancel['status']=='paused' and not paused_cancel['hasSandboxAccess'] and not paused_cancel['autoRenew']",globals()))
with store.connect() as db:db.execute("INSERT INTO contents VALUES('courses','course-fixture',?,'published',0)",(co.dump({'zh':'Synthetic course','access':'member'}),))
digital=product('digital','digital');serial['n']+=1;do=commerce.create_order({'requestId':'digital-order','environment':'sandbox','items':[{'skuId':digital['skuId'],'quantity':1}]});commerce.pay(do['id'],{'requestId':'pay-digital'})
co_admin.refund(renewal_order['id'],{'requestId':'refund-new-period','items':[{'itemId':renewal_order['items'][0]['id'],'quantity':1}]})
partial_status=api(member,user,'/api/membership/status',method='GET');after_refund=next(x for x in partial_status['items'] if x['id']==sid)
check('refund of latest period falls back to prior paid period',lambda:__import__('builtins').exec("assert after_refund['periodEnd']==sub['periodEnd'] and after_refund['hasSandboxAccess'];assert partial_status['independentPurchases'][0]['status']=='active'",globals()))
co_admin.refund(order['id'],{'requestId':'refund-original','items':[{'itemId':order['items'][0]['id'],'quantity':1}]})
with store.connect() as db:admin_refund_sync=manager.on_commerce_refund(db,order['id'])
check('admin refund callback derives buyer owner and restores actor context',lambda:__import__('builtins').exec("assert admin_refund_sync['ownerId']=='u1' and manager.owner=='admin';assert store.db.execute('SELECT status FROM membership_subscriptions WHERE id=?',(sid,)).fetchone()[0]=='revoked'",globals()))
fully=api(member,user,'/api/membership/status',method='GET');revoked=next(x for x in fully['items'] if x['id']==sid)
check('all member periods refunded revoke only member subscription',lambda:__import__('builtins').exec("assert revoked['status']=='revoked' and not revoked['hasSandboxAccess'];assert fully['independentPurchases'][0]['status']=='active'",globals()))
clock['now']=state_sub['periodEnd']+1;expired=api(member,user,'/api/membership/status',method='GET');expired_sub=next(x for x in expired['items'] if x['id']==state_id)
check('expiry stops sandbox membership without deleting independent purchase',lambda:__import__('builtins').exec("assert expired_sub['status']=='expired' and not expired_sub['hasSandboxAccess'];assert expired['independentPurchases'][0]['status']=='active';assert expired['accountClosureReminder']['thirdPartyRenewalStatus']=='not-connected'",globals()))
late_restore=api(member,user,'/api/membership/restore',{'requestId':'restore-expired','environment':'sandbox','orderId':so['id']})
check('restore never resets expired or refunded subscriptions',lambda:__import__('builtins').exec("assert next(x for x in late_restore['items'] if x['id']==state_id)['status']=='expired';assert next(x for x in late_restore['items'] if x['id']==sid)['status']=='revoked'",globals()))
check('calendar month clamps leap and nonleap boundaries',lambda:__import__('builtins').exec("a=int(datetime(2024,1,31,tzinfo=timezone.utc).timestamp()*1000);assert datetime.fromtimestamp(mb.add_period(a,{'unit':'month','count':1})/1000,timezone.utc).day==29;b=int(datetime(2025,1,31,tzinfo=timezone.utc).timestamp()*1000);assert datetime.fromtimestamp(mb.add_period(b,{'unit':'month','count':1})/1000,timezone.utc).day==28",globals()))
clock['now']=co.now()
without_plan=product('missing-plan')
check('membership SKU without approved sandbox plan is blocked',lambda:expect(503,lambda:order_with_hook(without_plan)))
raw_order=commerce.create_order({'requestId':'unbound-order','environment':'sandbox','items':[{'skuId':without_plan['skuId'],'quantity':1}]})
check('unbound order terms endpoint refuses current-plan guessing',lambda:expect(409,lambda:api(member,user,'/api/membership/orders/'+raw_order['id']+'/snapshots',method='GET')))
def unbound_payment_blocked():
    try:commerce.pay(raw_order['id'],{'requestId':'unbound-pay'})
    except sqlite3.IntegrityError as e:
        assert 'membership_payment_' in str(e)
        assert store.db.execute('SELECT payment_status FROM commerce_orders WHERE id=?',(raw_order['id'],)).fetchone()[0]=='unpaid'
        return
    raise AssertionError('unbound paid')
check('atomic payment guard rejects missing snapshot without payment event',unbound_payment_blocked)
check('unbound order is not granted subscription',lambda:expect(409,lambda:api(member,user,'/api/membership/orders/'+raw_order['id']+'/activate',{})))
check('paid order cannot be retrofitted with a current plan',lambda:expect(409,lambda:member.capture_order_snapshots(store.db,'u1',order['id'],{})))
check('trial boolean is rejected rather than treated as zero',lambda:expect(400,lambda:api(manager,admin,'/api/admin/membership/plans',{**draft,'trialDays':False})))
concurrent_product=product('concurrency');api(manager,admin,'/api/admin/membership/plans',plan(concurrent_product,'concurrency'))
concurrent_order,_=order_with_hook(concurrent_product);commerce.pay(concurrent_order['id'],{'requestId':'concurrency-pay'});clock['now']=co.now()
def concurrent_activate():
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:api(member,user,'/api/membership/orders/'+concurrent_order['id']+'/activate',{}),range(2)))
    assert values[0]['items'][0]['id']==values[1]['items'][0]['id']
    return values[0]['items'][0]
concurrent_sub=concurrent_activate()
check('concurrent activation consumes one unified payment once',lambda:__import__('builtins').exec("assert len(concurrent_sub['periods'])==1;assert store.db.execute('SELECT count(*) FROM membership_events WHERE subscription_id=? AND kind=?',(concurrent_sub['id'],'sandbox_activation')).fetchone()[0]==1",globals()))
pending_renew,_=order_with_hook(concurrent_product,concurrent_sub['id'])
check('second pending renewal is refused before another payment',lambda:expect(409,lambda:order_with_hook(concurrent_product,concurrent_sub['id'])))
commerce.pay(pending_renew['id'],{'requestId':'pending-renew-pay'});new_renew=api(member,user,'/api/membership/orders/'+pending_renew['id']+'/activate',{})['items'][0]
check('renewal advances by exactly the purchased period',lambda:__import__('builtins').exec("assert new_renew['periodEnd']==mb.add_period(concurrent_sub['periodEnd'],{'unit':'month','count':1})",globals()))
def immutable_snapshot():
    try:
        with store.connect() as db:db.execute("UPDATE membership_order_snapshots SET data='{}' WHERE item_id=?",(concurrent_order['items'][0]['id'],))
    except sqlite3.IntegrityError:return
    raise AssertionError('snapshot changed')
check('database rejects modifying purchased plan snapshot',immutable_snapshot)
stale_product=product('stale-entitlement');api(manager,admin,'/api/admin/membership/plans',plan(stale_product,'stale-entitlement'));stale_order,_=order_with_hook(stale_product);commerce.pay(stale_order['id'],{'requestId':'pay-stale-entitlement'});clock['now']=co.now();stale_sub=api(member,user,'/api/membership/orders/'+stale_order['id']+'/activate',{})['items'][0]
co_admin.refund(stale_order['id'],{'requestId':'refund-stale-entitlement','items':[{'itemId':stale_order['items'][0]['id'],'quantity':1}]})
with store.connect() as db:before_sync=member.subscription(db,member.own(db,stale_sub['id']))
check('access checks actual commerce entitlement even before cached lifecycle sync',lambda:__import__('builtins').exec("assert before_sync['status']=='active' and not before_sync['hasSandboxAccess']",globals()))
legal_product=product('legal-quote');legal_draft=plan(legal_product,'legal-quote');legal_plan=api(manager,admin,'/api/admin/membership/plans',legal_draft)['item'];legal_order,_=order_with_hook(legal_product)
api(manager,admin,'/api/admin/membership/plans',{**legal_draft,'id':legal_plan['id'],'version':1,'ruleVersion':'changed-before-payment'})
co_admin.save_product({'id':legal_product['id'],'version':legal_product['version'],'title':'Synthetic legal-quote','description':'Changed public price','type':'membership','sku':'fixture-legal-quote','priceMinor':600,'currency':'USD','stock':100,'shippingCountries':[],'shippingMinor':0,'taxMinor':0,'environment':'sandbox','status':'published'})
commerce.pay(legal_order['id'],{'requestId':'pay-old-legal-quote'});clock['now']=co.now();old_quote_sub=api(member,user,'/api/membership/orders/'+legal_order['id']+'/activate',{})['items'][0]
check('legal unpaid quote survives later plan and SKU price changes',lambda:__import__('builtins').exec("assert old_quote_sub['plan']['firstPriceMinor']==500 and old_quote_sub['plan']['version']==1 and old_quote_sub['plan']['ruleVersion']=='fixture-rule-1';assert store.db.execute('SELECT amount_minor FROM commerce_payment_events WHERE order_id=?',(legal_order['id'],)).fetchone()[0]==500",globals()))
race_product=product('cancel-before-pay');api(manager,admin,'/api/admin/membership/plans',plan(race_product,'cancel-before-pay'));race_initial,_=order_with_hook(race_product);commerce.pay(race_initial['id'],{'requestId':'pay-race-initial'});clock['now']=co.now();race_sub=api(member,user,'/api/membership/orders/'+race_initial['id']+'/activate',{})['items'][0];race_renew,_=order_with_hook(race_product,race_sub['id'])
with store.connect() as db:assert member.validate_commerce_payment(db,race_renew['id'])
api(member,user,'/api/membership/subscriptions/'+race_sub['id']+'/cancel-renewal',{'requestId':'cancel-before-pay'})
check('friendly payment validation catches cancelled renewal',lambda:expect(409,lambda:member.validate_commerce_payment(store.db,race_renew['id'])))
def cancelled_renewal_atomic_guard():
    before=store.db.execute('SELECT count(*) FROM commerce_payment_events').fetchone()[0]
    try:commerce.pay(race_renew['id'],{'requestId':'pay-after-cancel'})
    except sqlite3.IntegrityError as e:
        assert 'membership_payment_renewal_changed' in str(e)
        assert store.db.execute('SELECT count(*) FROM commerce_payment_events').fetchone()[0]==before
        assert store.db.execute('SELECT payment_status FROM commerce_orders WHERE id=?',(race_renew['id'],)).fetchone()[0]=='unpaid'
        return
    raise AssertionError('cancelled renewal paid')
check('atomic pay guard blocks cancellation after earlier valid checkout',cancelled_renewal_atomic_guard)
report={'kind':'isolated-memory-with-real-unified-sandbox-orders','realProviderRequests':0,'productionDatabaseAccess':False,'passed':sum(x['pass'] for x in results),'failed':sum(not x['pass'] for x in results),'checks':results,'sourceSha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [BACKEND/'commerce.py',BACKEND/'membership_lifecycle.py']}}
out=ROOT/'06_验证与后续工作/负责人优化建议-会员内存专项.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:report[k] for k in ('kind','realProviderRequests','passed','failed')}))
for r in results:
    if not r['pass']:print(json.dumps(r,ensure_ascii=False))
raise SystemExit(1 if report['failed'] else 0)

