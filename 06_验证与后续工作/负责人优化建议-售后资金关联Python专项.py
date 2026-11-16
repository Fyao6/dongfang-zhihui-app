"""Fresh owned SQLite, real original Commerce/AfterSales and finance service; no HTTP or external funds."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
import hashlib
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(BACKEND))
import server
import commerce
import after_sales
import after_sales_finance as finance

RUN = str(uuid4())
DB = ROOT / '06_验证与后续工作' / ('负责人优化建议-售后资金关联隔离-' + RUN + '.sqlite3')
assert not DB.exists()
store = server.Store(DB)
with store.connect() as db:
    # Explicit minimal lifecycle-table contract. Actual lifecycle HTTP integration is a later root gate.
    db.execute("CREATE TABLE IF NOT EXISTS account_lifecycle(owner TEXT PRIMARY KEY REFERENCES users(id),status TEXT NOT NULL CHECK(status IN ('active','closed')),epoch INTEGER NOT NULL,closed_at INTEGER,receipt_id TEXT)")
    after_sales.init_schema(db)
    finance.init_schema(db)
    for name, role in [('buyer', 'user'), ('other', 'user'), ('admin', 'admin'), ('admin2', 'admin'), ('operator', 'operator')]:
        db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)', (name, 'asf_' + name + RUN[:6], 'synthetic-no-login', '合成关联 ' + name, role, int(time.time() * 1000)))

class Handler:
    def __init__(self, actor, path, body):
        self.path, self.data = path, body
        with store.connect() as db:
            self.user = dict(db.execute('SELECT * FROM users WHERE id=?', (actor,)).fetchone()) if actor else None
    def require(self, roles=None):
        if not self.user:
            raise server.ApiError(401, 'sign in')
        if roles and self.user['role'] not in roles:
            raise server.ApiError(403, 'forbidden')
        return self.user
    def body(self):
        return self.data

def scalar(sql, *args):
    with store.connect() as db:
        return db.execute(sql, args).fetchone()[0]

def original_digest():
    with store.connect() as db:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'commerce_%' OR name LIKE 'membership_%' OR name LIKE 'commission_%' OR name LIKE 'after_sales_%' OR name IN ('users','account_lifecycle')) AND name NOT LIKE 'after_sales_finance_%' ORDER BY name")]
        data = {name: [tuple(r) for r in db.execute('SELECT * FROM "' + name + '" ORDER BY 1')] for name in names}
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

def api(actor, path, body=None, method=None, expected=200):
    h = Handler(actor, path, body)
    method = method or ('POST' if body is not None else 'GET')
    is_finance = '/after-sales-finance' in path
    before = original_digest() if is_finance else None
    cls = finance.AfterSalesFinance if is_finance else after_sales.AfterSales if '/after-sales' in path else commerce.Commerce
    try:
        data, status = cls(store, h, server.ApiError, lambda *args: None).route(method, urlsplit(path).path), 200
    except server.ApiError as error:
        data, status = {'error': error.message}, error.status
    if is_finance:
        assert original_digest() == before, 'Finance operation changed original ledger, stock, entitlements or logistics'
    if expected is None:
        return {'status': status, 'data': data}
    assert status == expected, (path, expected, status, data)
    return data

def seed(quantity=4, price=1000, currency='CNY', tax=2, shipping=10, kind='physical', buyer='buyer'):
    p = {'title': '合成原成交快照', 'description': '测试商品', 'sku': str(uuid4()), 'type': kind, 'priceMinor': price, 'currency': currency,
         'stock': 100, 'environment': 'sandbox', 'status': 'published', 'shippingMinor': shipping if kind == 'physical' else 0, 'taxMinor': tax, 'shippingCountries': ['CN'] if kind == 'physical' else []}
    if kind == 'digital':
        content = 'asf-course-' + str(uuid4())
        with store.connect() as db:
            db.execute('INSERT INTO contents VALUES(?,?,?,?,?,?)', ('courses', content, '{}', 'published', 0, 0))
        p['contentId'] = content
    product = api('admin', '/api/admin/commerce/products', p)['item']
    payload = {'requestId': str(uuid4()), 'environment': 'sandbox', 'items': [{'skuId': product['skuId'], 'quantity': quantity}]}
    if kind == 'physical':
        payload['shippingAddress'] = {'name': '合成收件人', 'country': 'CN', 'address': 'Synthetic address'}
    order = api(buyer, '/api/commerce/orders', payload)
    order = api(buyer, '/api/commerce/orders/' + order['id'] + '/sandbox-pay', {'requestId': str(uuid4())})
    if kind == 'physical':
        order = api('admin', '/api/admin/commerce/orders/' + order['id'] + '/fulfill', {'trackingNumber': 'SYNTHETIC', 'status': 'delivered'})
    return product, order

def case(order, quantity=1, accepted=True, buyer='buyer'):
    c = api(buyer, '/api/after-sales/cases', {'requestId': str(uuid4()), 'environment': 'sandbox', 'orderId': order['id'], 'type': 'return' if order['items'][0]['type'] == 'physical' else 'refund-only', 'items': [{'itemId': order['items'][0]['id'], 'quantity': quantity}], 'reason': '合成申请'})['item']
    if accepted:
        c = api('admin', '/api/admin/after-sales/cases/' + c['id'] + '/decision', {'requestId': str(uuid4()), 'version': c['version'], 'decision': 'accept', 'reason': '明确受理'})['item']
    return c

def refund(order, quantity=1, item_id=None):
    request = str(uuid4())
    api('admin', '/api/admin/commerce/orders/' + order['id'] + '/refund', {'requestId': request, 'items': [{'itemId': item_id or order['items'][0]['id'], 'quantity': quantity}]})
    with store.connect() as db:
        return dict(db.execute("SELECT * FROM commerce_payment_events WHERE request_id=? AND kind='refund'", (request,)).fetchone())

def detail(c, actor='admin'):
    return api(actor, '/api/' + ('admin/' if actor.startswith('admin') else '') + 'after-sales-finance/cases/' + c['id'])

def approve(c, amount, version=0, request=None, actor='admin', expected=200):
    body = {'requestId': request or str(uuid4()), 'environment': 'sandbox', 'currency': 'CNY', 'expectedVersion': version, 'ruleLabel': '明确测试批准v1', 'reason': '管理员逐项明确核准，不冒充正式政策', 'items': [{'caseItemId': x['id'], 'approvedMinor': amount} for x in c['items']]}
    return api(actor, '/api/admin/after-sales-finance/cases/' + c['id'] + '/approve', body, expected=expected)

def link(c, event, approval, amount, version, request=None, actor='admin', expected=200):
    body = {'requestId': request or str(uuid4()), 'environment': 'sandbox', 'currency': 'CNY', 'expectedVersion': version, 'approvalId': approval, 'refundEventId': event['id'], 'reason': '明确关联既有事件', 'items': [{'caseItemId': c['items'][0]['id'], 'amountMinor': amount}]}
    return api(actor, '/api/admin/after-sales-finance/cases/' + c['id'] + '/link', body, expected=expected)

def reverse(c, link_id, amount, version, request=None, expected=200):
    return api('admin', '/api/admin/after-sales-finance/cases/' + c['id'] + '/reverse', {'requestId': request or str(uuid4()), 'environment': 'sandbox', 'currency': 'CNY', 'expectedVersion': version, 'reason': '撤销错误关联，绝非撤销退款', 'items': [{'linkId': link_id, 'amountMinor': amount}]}, expected=expected)

def assert_summary(c, status):
    before=original_digest()
    with store.connect() as db:
        value=finance.case_finance_summary(db,c['id'],'buyer',c['orderId'])
        assert finance.case_finance_summary(db,c['id'],'other',c['orderId'])['caseRefundStatus']=='unknown'
        assert finance.case_finance_summary(db,c['id'],'buyer','wrong-order')['caseLinkedMinor'] is None
    d=detail(c,'buyer')
    assert value['caseRefundStatus']==status==d['status']
    assert value['caseRefundLinked']==(d['linkedMinor']>0) and value['caseRefundMatched']==(status=='sandbox_matched')
    assert value['caseRefundConfirmed'] is False and value['caseLinkedMinor']==d['linkedMinor']
    assert value['caseApprovedMinor']==d['approvedMinor'] and value['caseRemainingMinor']==d['remainingMinor']
    assert original_digest()==before

checks = []
def check(name, fn):
    try:
        fn()
        checks.append({'name': name, 'pass': True})
        print('PASS ' + name, flush=True)
    except Exception as error:
        checks.append({'name': name, 'pass': False, 'error': repr(error)})
        print('FAIL ' + name + ': ' + str(error), flush=True)

api('admin', '/api/admin/commerce/settings', {'sandboxEnabled': True, 'productionEnabled': False}, 'PATCH')
api('admin', '/api/admin/after-sales/settings', {'sandboxEnabled': True, 'productionEnabled': False, 'ruleVersion': 'explicit-base-fixture-v1'}, 'PATCH')
p, order = seed()
c1, c2 = case(order), case(order)

def default_unknown():
    result = detail(c1, 'buyer')
    assert result['approvedMinor'] is None and result['remainingMinor'] is None and result['status'] == 'unknown'
    assert_summary(c1, 'unknown')
    assert result['financialVersion'] == 0 and not result['caseRefundConfirmed'] and not result['actualFundsMoved']
    api('other', '/api/after-sales-finance/cases/' + c1['id'], expected=404)
    api(None, '/api/after-sales-finance/cases/' + c1['id'], expected=401)
    approve(c1, 10, actor='buyer', expected=403)
    approve(c1, 10, actor='operator', expected=403)
check('unknown target remains null; owner, anonymous and role boundaries', default_unknown)

def no_schema_read_only():
    import sqlite3
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    traced=[];db.set_trace_callback(traced.append)
    value=finance.case_finance_summary(db,'not-owned','not-owner','not-order')
    assert value['caseRefundStatus']=='unknown' and value['caseLinkedMinor'] is None
    assert not value['caseRefundLinked'] and not value['caseRefundMatched'] and not value['caseRefundConfirmed']
    assert db.total_changes==0 and all(x.lstrip().upper().startswith('SELECT') for x in traced)
    db.close()
check('pure original-case summary without schema stays unknown and performs SELECT only',no_schema_read_only)

def explicit_zero():
    response = approve(c1, 0)
    assert response['item']['status'] == 'no_refund_due' and response['item']['approvedMinor'] == 0
    assert_summary(c1, 'no_refund_due')
    assert not response['item']['caseRefundConfirmed'] and not response['item']['caseRefundLinked']
    assert response['item']['financialDecisionComplete'] and response['item']['logisticsStatus'] == 'accepted'
check('explicit zero means no refund due, never a fictional zero-amount refund', explicit_zero)

def approval_replay():
    request = str(uuid4())
    first, replay = approve(c1, 1000, 1, request), approve(c1, 1000, 1, request)
    assert first['actionId'] == replay['actionId'] and replay['replayed'] and replay['appliedVersion'] == 2
    approve(c1, 999, 1, request, expected=409)
    approve(c1, 1000, 1, expected=409)
check('approval append version, idempotence and stale ordering guards', approval_replay)

event = refund(order)
def allocation_and_caps():
    approval = detail(c1)['latestApproval']['id']
    first = link(c1, event, approval, 600, 2)
    assert_summary(c1, 'partially_matched')
    assert first['item']['status'] == 'partially_matched' and first['item']['linkedMinor'] == 600
    approve(c1, 599, 3, expected=409)
    approve(c1, None, 3, expected=409)
    link(c1, event, approval, 401, 3, expected=409)
    approve(c2, 1000)
    second = link(c2, event, detail(c2)['latestApproval']['id'], 412, 1)
    assert second['item']['linkedMinor'] == 412
    link(c2, event, detail(c2)['latestApproval']['id'], 1, 2, expected=409)
check('case target, real event item and cross-case event totals are atomic bounds', allocation_and_caps)

def reverse_releases_only_metadata():
    before = original_digest()
    link_id = detail(c1)['links'][0]['id']
    key = str(uuid4())
    first = reverse(c1, link_id, 200, 3, key)
    replay = reverse(c1, link_id, 200, 3, key)
    assert replay['replayed'] and replay['actionId'] == first['actionId'] and first['item']['linkedMinor'] == 400
    reverse(c1, link_id, 401, 4, expected=409)
    link(c2, event, detail(c2)['latestApproval']['id'], 200, 2)
    assert_summary(c1, 'partially_matched')
    assert original_digest() == before
check('append-only reversal releases actual net capacity without refund/stock/entitlement effects', reverse_releases_only_metadata)

def strict_amounts():
    for invalid in [True, '1', 0.5, -1, 1_000_000_001, 9_007_199_254_740_992]:
        approve(c1, invalid, 4, expected=400)
    for amount in [False, '10', 0, -1, 0.1]:
        reverse(c1, detail(c1)['links'][0]['id'], amount, 4, expected=400)
check('strict bounded safe integer amounts reject bool/string/fraction/negative/unsafe', strict_amounts)

def fixture(amount=1000, qty=4, buyer='buyer'):
    _, o = seed(quantity=qty, buyer=buyer)
    c = case(o, buyer=buyer)
    a = approve(c, amount)
    return o, c, a['actionId']

def finish_positive():
    o,c,a=fixture(); e=refund(o)
    response=link(c,e,a,1000,1)['item']
    assert response['status']=='sandbox_matched' and response['caseRefundMatched'] and not response['caseRefundConfirmed'] and not response['actualFundsMoved']
    assert_summary(c,'sandbox_matched')
    reverse(c,response['links'][0]['id'],1000,2)
    assert_summary(c,'awaiting_allocation')
    assert response['remainingMinor']==0 and response['logisticsStatus']=='accepted'
check('only exact real net amount completes a positive target; logistics stays independent', finish_positive)

def cross_source():
    o,c,a=fixture(); _,wrong=seed(buyer='other'); e=refund(wrong)
    link(c,e,a,1,1,expected=409)
    _,wrong_same=seed(); e=refund(wrong_same);link(c,e,a,1,1,expected=409)
    with store.connect() as db: pay=dict(db.execute("SELECT * FROM commerce_payment_events WHERE order_id=? AND kind='sandbox_pay'",(o['id'],)).fetchone())
    link(c,pay,a,1,1,expected=409)
check('other owner, another same-owner order and payment-kind sources cannot be borrowed', cross_source)

def wrong_currency_env():
    o,c,a=fixture();e=refund(o)
    body={'requestId':str(uuid4()),'environment':'sandbox','currency':'USD','expectedVersion':1,'approvalId':a,'refundEventId':e['id'],'reason':'wrong','items':[{'caseItemId':c['items'][0]['id'],'amountMinor':1}]}
    path='/api/admin/after-sales-finance/cases/'+c['id']+'/link'
    api('admin',path,body,expected=409);body['currency']='CNY';body['environment']='production';api('admin',path,body,expected=403)
check('original currency and sandbox environment are mandatory', wrong_currency_env)

def malformed_source():
    o,c,a=fixture();e=refund(o);raw=e['items']
    bad=['not-json','{}','[null]','[1]','["text"]','[]',json.dumps([{'itemId':o['items'][0]['id']}]),json.dumps([{'itemId':o['items'][0]['id'],'quantity':True}]),json.dumps([{'itemId':o['items'][0]['id'],'quantity':'1'}]),json.dumps([{'itemId':o['items'][0]['id'],'quantity':0}]),json.dumps([{'itemId':'missing','quantity':1}]),json.dumps([{'itemId':o['items'][0]['id'],'quantity':1}]*2)]
    for value in bad:
        with store.connect() as db: db.execute('UPDATE commerce_payment_events SET items=? WHERE id=?',(value,e['id']))
        events=api('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/events')['items']
        fact=next(x for x in events if x['id']==e['id']);assert not fact['sourceReliable'] and fact['availableMinor'] is None
        link(c,e,a,1,1,expected=409)
    with store.connect() as db:db.execute('UPDATE commerce_payment_events SET items=? WHERE id=?',(raw,e['id']))
check('missing/malformed legacy per-item facts stay unknown and never infer allocation', malformed_source)

def inconsistent_amount():
    o,c,a=fixture();e=refund(o)
    with store.connect() as db:db.execute('UPDATE commerce_payment_events SET amount_minor=amount_minor+1 WHERE id=?',(e['id'],))
    link(c,e,a,1,1,expected=409)
    result=api('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/events')['items'][0];assert not result['sourceReliable']
check('original event total must exactly match original immutable item allocations', inconsistent_amount)

def no_catalogue_guess():
    p,o=seed();c=case(o);a=approve(c,1000)['actionId'];e=refund(o)
    with store.connect() as db: db.execute('UPDATE commerce_skus SET price_minor=1 WHERE id=?',(p['skuId'],))
    events=api('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/events')['items'];assert events[0]['items'][0]['capacityMinor']==1012
    assert link(c,e,a,1000,1)['item']['status']=='sandbox_matched'
check('current catalogue price is irrelevant; original unit snapshot fixes event capacity', no_catalogue_guess)

def stale_approval():
    o,c,a=fixture();e=refund(o);new=approve(c,1000,1)
    link(c,e,a,1,2,expected=409)
    assert link(c,e,new['actionId'],1000,2)['item']['financialVersion']==3
check('revised approval requires its exact current reference, including same-amount revisions', stale_approval)

def immutable_audit():
    o,c,a=fixture();e=refund(o);link(c,e,a,1000,1);l=detail(c)['links'][0]['id'];reverse(c,l,1000,2)
    d=detail(c);assert d['linkedMinor']==0 and len(d['links'])==1 and len(d['reversals'])==1
    with store.connect() as db:
        for table in ['after_sales_finance_actions','after_sales_finance_targets','after_sales_finance_links','after_sales_finance_reversals']:
            for verb in ['DELETE FROM '+table,'UPDATE '+table+' SET owner=owner']:
                try:db.execute(verb);raise AssertionError('mutable '+table)
                except __import__('sqlite3').IntegrityError:pass
    assert detail(c)['latestApproval']['id']==a
check('original links and approval/reversal history are append-only and actor-attributed', immutable_audit)

def true_concurrent_event():
    o,c1,a1=fixture();c2=case(o);a2=approve(c2,1000)['actionId'];e=refund(o)
    before=original_digest()
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(lambda x:link(x[0],e,x[1],700,1,expected=None),[(c1,a1),(c2,a2)]))
    assert sorted(x['status'] for x in values)==[200,409]
    assert detail(c1)['linkedMinor']+detail(c2)['linkedMinor']==700 and original_digest()==before
check('two independent SQLite transactions cannot oversubscribe one refund event', true_concurrent_event)

def true_concurrent_reverse():
    o,c,a=fixture();e=refund(o);link(c,e,a,1000,1);l=detail(c)['links'][0]['id']
    with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:reverse(c,l,700,2,expected=None),range(2)))
    assert sorted(x['status'] for x in values)==[200,409] and detail(c)['linkedMinor']==300
check('concurrent double reversal cannot release the same net amount twice', true_concurrent_reverse)

def true_same_request():
    o,c,a=fixture();e=refund(o);key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:link(c,e,a,1000,1,key),range(2)))
    assert values[0]['actionId']==values[1]['actionId'] and len(detail(c)['links'])==1
check('same request replay under concurrency yields one original action and one link', true_same_request)

def closed_actor():
    o,c,a=fixture();e=refund(o)
    with store.connect() as db:db.execute("INSERT INTO account_lifecycle VALUES('admin2','closed',1,1,'synthetic-closed')")
    link(c,e,a,1,1,actor='admin2',expected=403)
    api('admin2','/api/admin/after-sales-finance/cases/'+c['id'],expected=403)
    with store.connect() as db:db.execute("DELETE FROM account_lifecycle WHERE owner='admin2'")
    assert link(c,e,a,1000,1,actor='admin2')['item']['status']=='sandbox_matched'
check('closed admin cannot read/write; another active admin may settle retained buyer facts', closed_actor)

def closed_buyer_retained():
    o,c,a=fixture();e=refund(o)
    with store.connect() as db:db.execute("INSERT INTO account_lifecycle VALUES('buyer','closed',1,1,'synthetic-closed')")
    assert link(c,e,a,1000,1)['item']['status']=='sandbox_matched'
    with store.connect() as db:db.execute("DELETE FROM account_lifecycle WHERE owner='buyer'")
check('buyer lifecycle closure never removes original ownership or prevents active-admin attribution', closed_buyer_retained)

def stale_role():
    o,c,a=fixture();e=refund(o);h=Handler('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/link',{})
    data={'requestId':str(uuid4()),'environment':'sandbox','currency':'CNY','expectedVersion':1,'approvalId':a,'refundEventId':e['id'],'reason':'stale role','items':[{'caseItemId':c['items'][0]['id'],'amountMinor':1}]}
    with store.connect() as db:db.execute("UPDATE users SET role='operator' WHERE id='admin'")
    try:
        try:finance.AfterSalesFinance(store,h,server.ApiError,lambda *args:None).mutate(c['id'],'link',data);raise AssertionError('stale role accepted')
        except server.ApiError as error:assert error.status==403
    finally:
        with store.connect() as db:db.execute("UPDATE users SET role='admin' WHERE id='admin'")
check('fresh transaction role rejects a stale admin handler', stale_role)

def disabled_sandbox():
    o,c,a=fixture();e=refund(o)
    api('admin','/api/admin/after-sales/settings',{'sandboxEnabled':False,'productionEnabled':False,'ruleVersion':'explicit-base-fixture-v1'},'PATCH')
    link(c,e,a,1,1,expected=503)
    api('admin','/api/admin/after-sales/settings',{'sandboxEnabled':True,'productionEnabled':False,'ruleVersion':'explicit-base-fixture-v1'},'PATCH')
    assert link(c,e,a,1000,1)['item']['status']=='sandbox_matched'
check('sandbox closure between approval and linking denies new facts without deleting history', disabled_sandbox)

def unaccepted_case():
    _,o=seed();c=case(o,accepted=False);approve(c,0,expected=409)
    api('admin','/api/admin/after-sales/cases/'+c['id']+'/decision',{'requestId':str(uuid4()),'version':c['version'],'decision':'reject','reason':'explicit rejection'})
    approve(c,0,expected=409)
check('submitted or rejected logistics cases cannot acquire an approval fact', unaccepted_case)

def invalid_payloads():
    o,c,a=fixture();path='/api/admin/after-sales-finance/cases/'+c['id']+'/approve'
    body={'requestId':str(uuid4()),'environment':'sandbox','currency':'CNY','expectedVersion':1,'ruleLabel':'explicit','reason':'reason','items':[{'caseItemId':c['items'][0]['id'],'approvedMinor':None}]}
    for change in [{'items':[]},{'items':body['items']*2},{'items':[{'caseItemId':'other','approvedMinor':1}]},{'items':[{'caseItemId':c['items'][0]['id']}]},{'extra':1},{'reason':''},{'ruleLabel':''}]:
        x={**body,**change};api('admin',path,x,expected=409 if change.get('items') and change['items'][0].get('caseItemId')=='other' else 400)
check('unknown fields, duplicate/missing rows and empty approval basis are rejected', invalid_payloads)

def no_legacy_autoassign():
    o,c,a=fixture(None);e=refund(o);d=detail(c)
    assert d['originalOrderRefundedMinor']==1012 and d['status']=='unknown' and d['linkedMinor']==0 and d['approvedMinor'] is None
check('a cumulative real sandbox refund is never silently claimed by an unapproved case', no_legacy_autoassign)

def cross_case_reversal():
    o,c,a=fixture();c2=case(o);e=refund(o);link(c,e,a,1000,1)
    reverse(c2,detail(c)['links'][0]['id'],1,0,expected=409)
check('a reversal cannot point at another case or borrow its link capacity', cross_case_reversal)

def approval_cap():
    _,o=seed();c=case(o);approve(c,1013,expected=409)
    assert approve(c,1012)['item']['approvedMinor']==1012
check('explicit approval cannot exceed the actual claimed original item gross amount', approval_cap)

def currency_snapshot():
    for currency,price in [('JPY',12),('KWD',1234),('TND',1001)]:
        _,o=seed(currency=currency,price=price,tax=0,shipping=0);c=case(o)
        body={'requestId':str(uuid4()),'environment':'sandbox','currency':currency,'expectedVersion':0,'ruleLabel':'explicit exponent test','reason':'no inferred rule','items':[{'caseItemId':c['items'][0]['id'],'approvedMinor':price}]}
        a=api('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/approve',body);e=refund(o)
        b={'requestId':str(uuid4()),'environment':'sandbox','currency':currency,'expectedVersion':1,'approvalId':a['actionId'],'refundEventId':e['id'],'reason':'exact original minor','items':[{'caseItemId':c['items'][0]['id'],'amountMinor':price}]}
        d=api('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/link',b)['item'];assert d['status']=='sandbox_matched' and d['linkedMinor']==price
check('zero/three decimal currencies retain original integer minor facts without conversion', currency_snapshot)

def mixed_zero_positive():
    products=[seed(kind='digital')[0] for _ in range(2)]
    o=api('buyer','/api/commerce/orders',{'requestId':str(uuid4()),'environment':'sandbox','items':[{'skuId':p['skuId'],'quantity':2} for p in products]})
    o=api('buyer','/api/commerce/orders/'+o['id']+'/sandbox-pay',{'requestId':str(uuid4())})
    c=api('buyer','/api/after-sales/cases',{'requestId':str(uuid4()),'environment':'sandbox','orderId':o['id'],'type':'refund-only','reason':'explicit mixed items','items':[{'itemId':x['id'],'quantity':1} for x in o['items']]})['item']
    c=api('admin','/api/admin/after-sales/cases/'+c['id']+'/decision',{'requestId':str(uuid4()),'version':c['version'],'decision':'accept','reason':'explicit'})['item']
    a=api('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/approve',{'requestId':str(uuid4()),'environment':'sandbox','currency':'CNY','expectedVersion':0,'ruleLabel':'explicit zero/positive','reason':'not formal policy','items':[{'caseItemId':c['items'][0]['id'],'approvedMinor':0},{'caseItemId':c['items'][1]['id'],'approvedMinor':1000}]})
    e=refund(o,item_id=c['items'][1]['itemId'])
    b={'requestId':str(uuid4()),'environment':'sandbox','currency':'CNY','expectedVersion':1,'approvalId':a['actionId'],'refundEventId':e['id'],'reason':'only matching original item','items':[{'caseItemId':c['items'][0]['id'],'amountMinor':1}]}
    api('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/link',b,expected=409)
    b['requestId']=str(uuid4());b['items']=[{'caseItemId':c['items'][1]['id'],'amountMinor':1000}]
    d=api('admin','/api/admin/after-sales-finance/cases/'+c['id']+'/link',b)['item'];assert d['status']=='sandbox_matched'
    assert next(x for x in d['items'] if x['id']==c['items'][0]['id'])['status']=='no_refund_due'
check('mixed zero/positive case matches only the corresponding real original item', mixed_zero_positive)

def split_events():
    _,o=seed();c=case(o,quantity=2);a=approve(c,2000)['actionId'];e1=refund(o);e2=refund(o)
    link(c,e1,a,1000,1);d=link(c,e2,a,1000,2)['item']
    assert d['status']=='sandbox_matched' and len(d['links'])==2 and d['linkedMinor']==2000
check('one approved target may explicitly link multiple independent real refund events', split_events)

def reverse_then_unknown():
    o,c,a=fixture();e=refund(o);link(c,e,a,1000,1);l=detail(c)['links'][0]['id'];reverse(c,l,1000,2)
    d=approve(c,None,3)['item'];assert d['status']=='unknown' and d['approvedMinor'] is None and d['linkedMinor']==0
    assert len(d['approvals'])==2 and len(d['links'])==1 and len(d['reversals'])==1
check('after explicit full reversal target may return unknown without erasing any history', reverse_then_unknown)

def owner_no_actor():
    o,c,a=fixture();e=refund(o);link(c,e,a,1000,1)
    assert all('actorId' not in x for x in detail(c,'buyer')['actions'])
    assert all(x['actorId']=='admin' for x in detail(c)['actions'])
check('admin audit attribution is retained without exposing actor IDs in owner projection', owner_no_actor)

report = {'at': time.time_ns() // 1_000_000, 'runId': RUN, 'kind': 'isolated-real-original-commerce-and-after-sales-sqlite',
          'realFundsMoved': False, 'productionDatabaseOpened': False, 'httpOrServiceStarted': False, 'lifecycleTableFixtureOnly': True,
          'ownedDatabase': str(DB.relative_to(ROOT)), 'checks': checks, 'passed': sum(x['pass'] for x in checks), 'failed': sum(not x['pass'] for x in checks),
          'sourceSha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [BACKEND / 'after_sales_finance.py', BACKEND / 'after_sales.py', BACKEND / 'commerce.py']}}
report['pass'] = report['failed'] == 0
out = ROOT / '06_验证与后续工作/负责人优化建议-售后资金关联Python专项.json'
old_runs = []
if out.exists():
    old = json.loads(out.read_text(encoding='utf-8'))
    old_runs = old.get('runs', [old.get('latest', old)])
out.write_bytes((json.dumps({'latest': report, 'runs': old_runs + [report]}, ensure_ascii=False, indent=2) + '\n').encode())
print(json.dumps({'passed': report['passed'], 'failed': report['failed'], 'runId': RUN}))
raise SystemExit(0 if report['pass'] else 1)
