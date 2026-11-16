"""Isolated real-commerce after-sales checks. Fresh owned SQLite only; no HTTP/provider/real funds."""
import concurrent.futures,hashlib,json,sys,time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
BACKEND=ROOT/'04_研发源码/app/r4/backend'
sys.path.insert(0,str(BACKEND))
import server,commerce,after_sales
run_id=str(uuid4())
db_path=ROOT/'06_验证与后续工作'/('负责人优化建议-售后隔离-'+run_id+'.sqlite3')
assert not db_path.exists()
store=server.Store(db_path)
with store.connect() as db:
    after_sales.init_schema(db)
    for identifier,role in [('buyer','user'),('other','user'),('admin','admin'),('operator','operator')]:
        db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(identifier,'as_'+identifier+'_'+run_id[:6],'synthetic-no-login','合成售后 '+identifier,role,int(time.time()*1000)))
class H:
    def __init__(self,actor,path,body):
        self.path=path;self.data=body
        with store.connect() as db:self.user=dict(db.execute('SELECT * FROM users WHERE id=?',(actor,)).fetchone()) if actor else None
    def require(self,roles=None):
        if not self.user:raise server.ApiError(401,'sign in')
        if roles and self.user['role'] not in roles:raise server.ApiError(403,'forbidden')
        return self.user
    def body(self):return self.data
def api(actor,path,data=None,method=None,status=200):
    h=H(actor,path,data);method=method or ('POST' if data is not None else 'GET')
    service=after_sales.AfterSales(store,h,server.ApiError,lambda *x:None) if '/after-sales' in path else commerce.Commerce(store,h,server.ApiError,lambda *x:None)
    try:out=service.route(method,urlsplit(path).path);actual=200
    except server.ApiError as e:out={'error':e.message};actual=e.status
    if status is None:return {'status':actual,'data':out}
    assert actual==status,(path,status,actual,out)
    return out
def sqlone(sql,*args):
    with store.connect() as db:return dict(db.execute(sql,args).fetchone())
def scal(sql,*args):
    with store.connect() as db:return db.execute(sql,args).fetchone()[0]
def product(kind='physical',stock=20):
    d={'title':'沙箱合成商品','description':'非正式商品','type':kind,'sku':'AS-'+str(uuid4()),'priceMinor':1000,'currency':'USD','stock':stock,'environment':'sandbox','status':'published','shippingMinor':10 if kind=='physical' else 0,'taxMinor':2,'shippingCountries':['US'] if kind=='physical' else []}
    if kind=='digital':
        content='as-course-'+str(uuid4())
        with store.connect() as db:db.execute('INSERT INTO contents VALUES(?,?,?,?,?,?)',('courses',content,json.dumps({'title':'合成免费课程','access':'free','status':'published'}),'published',0,0))
        d['contentId']=content
    return api('admin','/api/admin/commerce/products',d)['item']
def order(product,quantity=3,paid=True,dispatched=True,actor='buyer'):
    d={'requestId':str(uuid4()),'environment':'sandbox','items':[{'skuId':product['skuId'],'quantity':quantity}]}
    if product['type']=='physical':d['shippingAddress']={'name':'合成收货人','address':'Synthetic street','city':'City','country':'US','postalCode':'00000'}
    row=api(actor,'/api/commerce/orders',d)
    if paid:row=api(actor,'/api/commerce/orders/'+row['id']+'/sandbox-pay',{'requestId':str(uuid4())})
    if paid and dispatched and product['type']=='physical':row=api('admin','/api/admin/commerce/orders/'+row['id']+'/fulfill',{'carrier':'sandbox-carrier','trackingNumber':'TEST-'+str(uuid4()),'status':'delivered'})
    return row
def case(order,quantity=1,kind='return',request_id=None,status=200):
    return api('buyer','/api/after-sales/cases',{'requestId':request_id or str(uuid4()),'environment':'sandbox','orderId':order['id'],'type':kind,'items':[{'itemId':order['items'][0]['id'],'quantity':quantity}],'reason':'合成申请理由'},status=status)
def decision(c,accept=True,request_id=None,status=200):
    return api('admin','/api/admin/after-sales/cases/'+c['id']+'/decision',{'requestId':request_id or str(uuid4()),'version':c['version'],'decision':'accept' if accept else 'reject','reason':'合成受理说明' if accept else '合成驳回理由'},status=status)
def shipping(c,status=200):
    return api('buyer','/api/after-sales/cases/'+c['id']+'/return-shipping',{'requestId':str(uuid4()),'version':c['version'],'carrier':'sandbox-return-carrier','trackingNumber':'RETURN-'+str(uuid4())},status=status)
def inspect(c,received=1,restock=0,request_id=None,status=200):
    request_id=request_id or str(uuid4())
    return api('admin','/api/admin/after-sales/cases/'+c['id']+'/inspect',{'requestId':request_id,'receiptReference':'RECEIPT-'+request_id,'version':c['version'],'items':[{'caseItemId':c['items'][0]['id'],'receivedQuantity':received,'restockQuantity':restock,'condition':'resalable' if restock else 'damaged'}],'note':'沙箱人工验收记录，不代表承运商验证'},status=status)
def money_hash():
    with store.connect() as db:
        data={t:[tuple(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY 1')] for t in ['commerce_orders','commerce_order_items','commerce_payment_events','commerce_entitlements']}
    return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()
tests=[]
def check(name,fn):
    try:fn();tests.append({'name':name,'pass':True});print('PASS '+name,flush=True)
    except Exception as e:tests.append({'name':name,'pass':False,'error':repr(e)});print('FAIL '+name+': '+str(e),flush=True)
check('default closed, production false, anonymous and ordinary management denied',lambda:(
    (lambda x: (__import__('builtins').exec('assert x["settings"]["sandboxEnabled"] is False and x["productionEnabled"] is False',{'x':x})))(api('buyer','/api/after-sales/config')),
    api(None,'/api/after-sales/cases',status=401),api('buyer','/api/admin/after-sales',status=403),api('operator','/api/admin/after-sales',status=403)))
api('admin','/api/admin/commerce/settings',{'sandboxEnabled':True,'productionEnabled':False},'PATCH')
check('settings require explicit sandbox rule and cannot enable production',lambda:(
    api('admin','/api/admin/after-sales/settings',{'sandboxEnabled':True,'productionEnabled':True,'ruleVersion':'fixture'},'PATCH',400),
    api('admin','/api/admin/after-sales/settings',{'sandboxEnabled':True,'productionEnabled':False,'ruleVersion':None},'PATCH',400),
    api('admin','/api/admin/after-sales/settings',{'sandboxEnabled':True,'productionEnabled':False,'ruleVersion':'sandbox-fixture-v1'},'PATCH')))
p=product();o=order(p,3);original_stock=scal('SELECT stock FROM commerce_skus WHERE id=?',p['skuId']);c=None
def create_replay():
    global c
    request_id=str(uuid4());first=case(o,2,request_id=request_id);c=first['item'];again=case(o,2,request_id=request_id)
    assert again['replayed'] and again['item']['id']==c['id']
    case(o,1,request_id=request_id,status=409)
    assert c['items'][0]['snapshot']['priceMinor']==1000 and c['ruleVersion']=='sandbox-fixture-v1'
check('real paid dispatched order creates immutable per-item case and idempotent replay',create_replay)
check('unpaid, undispatched and cross-account order cannot become return cases',lambda:(
    case(order(product(),1,paid=False,dispatched=False),status=409),
    case(order(product(),1,dispatched=False),status=409),
    api('other','/api/after-sales/cases/'+c['id'],status=404),
    api('other','/api/after-sales/cases',{'requestId':str(uuid4()),'environment':'sandbox','orderId':o['id'],'type':'return','reason':'cross','items':[{'itemId':o['items'][0]['id'],'quantity':1}]},status=404)))
check('per-item allocation cannot exceed original quantity',lambda:case(o,2,status=409))
def strict():
    for bad in [-1,0,1.5,True,'1',100]:
        api('buyer','/api/after-sales/cases',{'requestId':str(uuid4()),'environment':'sandbox','orderId':o['id'],'type':'return','reason':'invalid','items':[{'itemId':o['items'][0]['id'],'quantity':bad}]},status=400)
    api('buyer','/api/after-sales/cases',[],status=400)
    api('buyer','/api/after-sales/cases',{'requestId':str(uuid4()),'environment':'production','orderId':o['id'],'type':'return','reason':'prod','items':[{'itemId':o['items'][0]['id'],'quantity':1}]},status=403)
check('strict integers, JSON object and production rejection',strict)
def accept_once():
    global c
    before=money_hash();request_id=str(uuid4());first=decision(c,request_id=request_id);again=decision(c,request_id=request_id)
    assert again['replayed'] and again['item']['version']==first['item']['version']
    decision(c,False,request_id=request_id,status=409)
    decision(c,status=409)
    c=first['item'];assert c['status']=='accepted' and c['money']['caseRefundConfirmed'] is False
    assert money_hash()==before and scal('SELECT stock FROM commerce_skus WHERE id=?',p['skuId'])==original_stock
check('accept/reject have reasons and CAS/idempotence but do not refund or restock',accept_once)
check('inspection requires owner shipping and ordinary user cannot inspect',lambda:(
    inspect(c,status=409),
    api('buyer','/api/admin/after-sales/cases/'+c['id']+'/inspect',{'requestId':str(uuid4()),'version':c['version'],'items':[],'note':'invalid'},status=403),
    api('other','/api/after-sales/cases/'+c['id']+'/return-shipping',{'requestId':str(uuid4()),'version':c['version'],'carrier':'x','trackingNumber':'x'},status=404)))
c=shipping(c)['item']
def partial():
    global c
    before=money_hash();first=inspect(c,1,0);c=first['item']
    assert c['status']=='partially_received' and c['items'][0]['receivedQuantity']==1 and c['items'][0]['restockedQuantity']==0
    assert c['shipments'][0]['carrierVerified'] is False
    assert scal("SELECT count(*) FROM commerce_inventory_events WHERE order_id=? AND reason='after_sales_received_no_restock'",o['id'])==1
    assert scal('SELECT stock FROM commerce_skus WHERE id=?',p['skuId'])==original_stock and money_hash()==before
check('partial receipt with zero explicitly approved restock leaves stock/funds unchanged',partial)
def receive_rest():
    global c
    before=money_hash();request_id=str(uuid4());old=c
    c=inspect(old,1,1,request_id=request_id)['item'];again=inspect(old,1,1,request_id=request_id)
    assert again['replayed'] and c['status']=='received' and c['items'][0]['restockedQuantity']==1
    inspect(old,1,0,request_id=request_id,status=409);inspect(c,1,1,status=409)
    assert scal('SELECT stock FROM commerce_skus WHERE id=?',p['skuId'])==original_stock+1 and money_hash()==before
    assert scal("SELECT count(*) FROM commerce_inventory_events WHERE order_id=? AND reason='after_sales_return_restock'",o['id'])==1
check('final receipt applies one stock event only; replay/conflict/over-receipt cannot double restock',receive_rest)
def digital():
    d=product('digital');od=order(d,2)
    case(od,1,'return',status=409)
    cd=case(od,1,'refund-only')['item'];cd=decision(cd)['item']
    shipping(cd,status=409);inspect(cd,status=409)
    assert cd['money']['caseRefundConfirmed'] is False and cd['money']['orderPaymentStatus']=='paid'
check('digital refund review never accepts return logistics or warehouse receipt',digital)
def rejection():
    op=order(product(),2);first=case(op,2)['item'];rejected=decision(first,False)['item']
    assert rejected['status']=='rejected'
    next_case=case(op,2)['item'];assert next_case['id']!=first['id']
check('reasoned rejection releases quantity allocation for a distinct new request',rejection)
def refund_first():
    pp=product(stock=10);op=order(pp,3,dispatched=False);line=op['items'][0]['id']
    api('admin','/api/admin/commerce/orders/'+op['id']+'/refund',{'requestId':str(uuid4()),'items':[{'itemId':line,'quantity':1}]})
    op=api('admin','/api/admin/commerce/orders/'+op['id']+'/fulfill',{'carrier':'test','trackingNumber':'TRACK','status':'shipped'})
    case(op,3,status=409);r=case(op,2)['item'];r=decision(r)['item'];r=shipping(r)['item'];r=inspect(r,2,2)['item']
    assert scal('SELECT stock FROM commerce_skus WHERE id=?',pp['skuId'])==10
    assert scal('SELECT sum(quantity_delta) FROM commerce_inventory_events WHERE item_id=? AND quantity_delta>0',line)==3
check('pre-dispatch original refund restock is deducted and cannot be added again',refund_first)
def refund_after():
    pp=product(stock=10);op=order(pp,3);line=op['items'][0]['id'];request_id=str(uuid4())
    r=case(op,3)['item'];r=decision(r)['item'];r=shipping(r)['item']
    payload={'requestId':request_id,'items':[{'itemId':line,'quantity':3}]};api('admin','/api/admin/commerce/orders/'+op['id']+'/refund',payload)
    assert scal('SELECT stock FROM commerce_skus WHERE id=?',pp['skuId'])==7
    r=inspect(r,3,2)['item'];api('admin','/api/admin/commerce/orders/'+op['id']+'/refund',payload)
    assert scal('SELECT stock FROM commerce_skus WHERE id=?',pp['skuId'])==9
    assert r['money']['orderPaymentStatus']=='refunded' and r['money']['caseRefundLinked'] is False and r['money']['actualFundsMoved'] is False
check('post-dispatch actual commerce refund stays zero-stock; inspection restocks only explicit safe units',refund_after)
def concurrent_create():
    op=order(product(),3)
    def work(i):
        try:return case(op,2)['item']['id']
        except AssertionError as e:
            if ', 200, 409,' in str(e):return None
            raise
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(work,[1,2]))
    assert sum(x is not None for x in results)==1,results
check('concurrent different requests cannot over-allocate original item quantity',concurrent_create)
def concurrent_same():
    op=order(product(),2);request_id=str(uuid4())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:case(op,2,request_id=request_id),[1,2]))
    assert len({x['item']['id'] for x in values})==1
    assert scal('SELECT count(*) FROM after_sales_cases WHERE order_id=?',op['id'])==1
check('concurrent identical request converges to one case and one quantity allocation',concurrent_same)
def legacy():
    op=order(product(),2)
    api('buyer','/api/commerce/orders/'+op['id']+'/aftersale',{'requestId':str(uuid4()),'reason':'legacy','quantity':1})
    case(op,1,status=409)
    with store.connect() as db:assert after_sales.legacy_request_allowed(db,'buyer',o['id']) is False
check('legacy pending request is not guessed into per-item lines; future legacy guard is exposed',legacy)
def extra_contracts():
    eligible=api('buyer','/api/after-sales/orders/'+o['id'])
    assert eligible['items'][0]['claimedQuantity']==2 and eligible['items'][0]['availableReturnQuantity']==1
    api('other','/api/after-sales/orders/'+o['id'],status=404)
check('eligibility reads original quantities and claimed units with account isolation',extra_contracts)
def duplicate_receipt():
    pp=product();op=order(pp,2);cc=case(op,2)['item'];cc=decision(cc)['item'];cc=shipping(cc)['item'];rid=str(uuid4())
    cc=inspect(cc,1,1,request_id=rid)['item'];before=scal('SELECT stock FROM commerce_skus WHERE id=?',pp['skuId']);actions=scal('SELECT count(*) FROM after_sales_actions')
    api('admin','/api/admin/after-sales/cases/'+cc['id']+'/inspect',{'requestId':str(uuid4()),'receiptReference':'RECEIPT-'+rid,'version':cc['version'],'items':[{'caseItemId':cc['items'][0]['id'],'receivedQuantity':1,'restockQuantity':1,'condition':'resalable'}],'note':'same physical receipt, different request'},status=409)
    assert scal('SELECT stock FROM commerce_skus WHERE id=?',pp['skuId'])==before and scal('SELECT count(*) FROM after_sales_actions')==actions
check('receipt reference prevents another request ID from counting the same receipt twice',duplicate_receipt)
def same_order_receipt_concurrency():
    p=product(stock=5);o=order(p,2)
    cases=[shipping(decision(case(o,1)['item'])['item'])['item'] for _ in range(2)]
    reference='SAME-ORDER-'+str(uuid4())
    def payload(c):return {'requestId':str(uuid4()),'receiptReference':reference,'version':c['version'],'items':[{'caseItemId':c['items'][0]['id'],'receivedQuantity':1,'restockQuantity':1,'condition':'synthetic resalable'}],'note':'Same physical receipt must never be counted twice across cases'}
    before_money=money_hash();before_stock=scal('SELECT stock FROM commerce_skus WHERE id=?',p['skuId'])
    def request(c):return api('admin','/api/admin/after-sales/cases/'+c['id']+'/inspect',payload(c),status=None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(request,cases))
    assert sorted(r['status'] for r in results)==[200,409],[r['status'] for r in results]
    assert scal('SELECT stock FROM commerce_skus WHERE id=?',p['skuId'])==before_stock+1
    assert money_hash()==before_money
    assert scal('SELECT count(*) FROM after_sales_inspections i JOIN after_sales_cases c ON c.id=i.case_id WHERE c.order_id=?',o['id'])==1
    assert scal("SELECT count(*) FROM commerce_inventory_events WHERE order_id=? AND reason='after_sales_return_restock'",o['id'])==1
    loser=cases[next(i for i,r in enumerate(results) if r['status']==409)]
    api('admin','/api/admin/after-sales/cases/'+loser['id']+'/inspect',payload(loser),status=409)
    assert scal('SELECT stock FROM commerce_skus WHERE id=?',p['skuId'])==before_stock+1
check('same original order receipt cannot be counted across two cases: concurrent and serial replay leave one stock event',same_order_receipt_concurrency)

def role_race():
    op=order(product(),1);cc=case(op,1)['item'];path='/api/admin/after-sales/cases/'+cc['id']+'/decision'
    h=H('admin',path,{'requestId':str(uuid4()),'version':cc['version'],'decision':'accept','reason':'stale admin'})
    service=after_sales.AfterSales(store,h,server.ApiError,lambda *x:None)
    with store.connect() as db:db.execute("UPDATE users SET role='operator' WHERE id='admin'")
    try:
        try:service.route('POST',path);raise AssertionError('downgraded actor wrote action')
        except server.ApiError as e:assert e.status==403
        assert scal('SELECT count(*) FROM after_sales_actions WHERE case_id=? AND kind=?',cc['id'],'accept')==0
    finally:
        with store.connect() as db:db.execute("UPDATE users SET role='admin' WHERE id='admin'")
check('transaction rechecks admin role after the request actor was cached',role_race)
def disabled():
    before=scal('SELECT count(*) FROM after_sales_actions')
    api('admin','/api/admin/after-sales/settings',{'sandboxEnabled':False,'productionEnabled':False,'ruleVersion':'sandbox-fixture-v1'},'PATCH')
    assert api('buyer','/api/after-sales/cases/'+c['id'])['id']==c['id']
    case(order(product(),1),status=503)
    assert scal('SELECT count(*) FROM after_sales_actions')==before
check('disabled module remains readable and refuses new mutations without original funds changes',disabled)
report={'at':time.time(),'pass':all(x['pass'] for x in tests),'passed':sum(x['pass'] for x in tests),'failed':sum(not x['pass'] for x in tests),'tests':tests,'ownedDatabase':str(db_path.relative_to(ROOT)),'realProviderRequests':0,'actualFundsMoved':False,'productionEnabled':False,'scope':'actual integrated Commerce methods + independent new AfterSales, synthetic users, fresh SQLite only'}
path=ROOT/'06_验证与后续工作/负责人优化建议-售后Python隔离专项.json';runs=[]
if path.exists():
    old=json.loads(path.read_text(encoding='utf-8'));runs=old.get('runs',[old.get('latest',old)])
runs.append(report);path.write_text(json.dumps({'latest':report,'runs':runs},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='tests'},ensure_ascii=False))
if not report['pass']:sys.exit(1)

