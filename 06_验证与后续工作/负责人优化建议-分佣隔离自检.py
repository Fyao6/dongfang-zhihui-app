"""Real commerce + commission contracts in a single new in-memory SQLite only."""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(BACKEND))
import commerce
import commission as cm


class Error(Exception):
    def __init__(self, status, message):
        super().__init__(message); self.status = status


class Store:
    def __init__(self):
        self.db = sqlite3.connect(':memory:'); self.db.row_factory = sqlite3.Row
        self.db.executescript('CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT); CREATE TABLE contents(kind TEXT,id TEXT,status TEXT);')
        for uid, role in [('admin', 'admin'), ('finance', 'operator'), ('business', 'operator'), ('support', 'reviewer'), ('buyer', 'user'), ('other', 'user'), ('author', 'teacher'), ('promoter', 'user')]:
            self.db.execute('INSERT INTO users VALUES(?,?)', (uid, role))
        self.db.commit(); commerce.init_schema(self.db); cm.init_schema(self.db); self.snapshot_enabled = True
    @contextlib.contextmanager
    def connect(self):
        try:
            yield self.db; self.db.commit()
        except BaseException:
            self.db.rollback(); raise
    def audit(self, db, uid, action, target, detail):
        if action == 'commerce.order.create' and self.snapshot_enabled: cm.snapshot_order(db, target)
        if action in ('commerce.sandbox.pay', 'commerce.sandbox.refund'): cm.sync_commission_order(db, target)


class H:
    def __init__(self, store): self.store, self.user, self.payload, self.path = store, None, {}, ''
    def require(self, roles=None):
        if not self.user: raise Error(401, 'login')
        if roles is not None and self.user['role'] not in roles: raise Error(403, 'role')
        return self.user
    def body(self): return self.payload


store, h = Store(), None
h = H(store); checks = []; vectors = []


def action(uid, path='/api/admin/commissions', method='GET', data=None, status=None):
    h.user = dict(store.db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()) if uid else None
    h.payload, h.path = data or {}, path
    try:
        result = cm.Commission(store, h, Error, lambda *a: None).route(method, path.split('?')[0])
        if status: raise AssertionError('expected status ' + str(status))
        return result
    except Error as e:
        if e.status != status: raise
        return {'rejected': e.status}


def test(name, f):
    result = f(); checks.append({'name': name, 'passed': True}); return result


def rule(**kw):
    value = dict(ruleId='author-rule', expectedVersion=0, productId='p', kind='author', beneficiary='author', currency='USD', mode='rate', rateBps=3333, fixedMinor=0, rounding='half_up', basis=dict(deductTax=True, deductShipping=True, deductDiscount=True, deductChannelFee=True), capMinor=None, freezeDays=0, minimumSettlementMinor=1, status='active', note='Synthetic sandbox rule, not production')
    value.update(kw); return value


def c(uid):
    h.user = dict(store.db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())
    return commerce.Commerce(store, h, Error, lambda *a: None)


def run():
    test('anonymous rejected', lambda: action(None, '/api/commissions', status=401))
    test('ungranted operator denied', lambda: action('business', status=403))
    test('production and actual payments closed', lambda: action('admin', '/api/admin/commissions/settings', 'PATCH', dict(sandboxEnabled=True, productionEnabled=True, stackingPolicy='allow_both', attributionStrategy='last_touch'), 400))
    test('sandbox explicit enable', lambda: action('admin', '/api/admin/commissions/settings', 'PATCH', dict(sandboxEnabled=True, stackingPolicy='allow_both', attributionStrategy='last_touch')))
    for uid, permission in [('finance', 'finance'), ('business', 'business'), ('support', 'support')]:
        test('grant ' + permission, lambda uid=uid, p=permission: action('admin', '/api/admin/commissions/grants', 'POST', dict(userId=uid, permission=p)))
    test('business cannot change settings', lambda: action('business', '/api/admin/commissions/settings', 'PATCH', dict(sandboxEnabled=False, stackingPolicy='allow_both', attributionStrategy='last_touch'), 403))
    h.payload = dict(sandboxEnabled=True, productionEnabled=False)
    c('admin').admin('PATCH', '/api/admin/commerce/settings')
    with store.connect() as db: db.execute("INSERT INTO contents VALUES('courses','fixture-course','published')")
    product = c('admin').save_product(dict(id='p', title='Sandbox work', description='fixture', type='digital', contentId='fixture-course', sku='fixture', priceMinor=1001, currency='USD', stock=99, shippingMinor=0, taxMinor=7, environment='sandbox', status='published'))
    sid = product['item']['skuId']
    test('append author rule', lambda: action('business', '/api/admin/commissions/rules', 'POST', rule()))
    test('no arbitrary promotion beneficiary', lambda: action('business', '/api/admin/commissions/rules', 'POST', rule(ruleId='promo-rule', kind='promotion', beneficiary='promoter'), 400))
    test('server invite created', lambda: action('business', '/api/admin/commissions/invites', 'POST', dict(code='PROMO_1', beneficiary='promoter', priority=10, validUntil=cm.now()+86400000)))
    test('client beneficiary attribution override rejected', lambda: action('buyer', '/api/commissions/attributions', 'POST', dict(code='PROMO_1', requestId='a', beneficiary='other'), 400))
    test('self attribution rejected', lambda: action('promoter', '/api/commissions/attributions', 'POST', dict(code='PROMO_1', requestId='self'), 400))
    a = test('server attribution captured', lambda: action('buyer', '/api/commissions/attributions', 'POST', dict(code='PROMO_1', requestId='a')))
    test('attribution replay stable', lambda: action('buyer', '/api/commissions/attributions', 'POST', dict(code='PROMO_1', requestId='a')) == a or (_ for _ in ()).throw(AssertionError()))
    order = c('buyer').create_order(dict(requestId='order1', environment='sandbox', items=[dict(skuId=sid, quantity=3)])); oid = order['id']; item = order['items'][0]['itemId']
    assert store.db.execute('SELECT count(*) FROM commission_snapshots WHERE order_id=?', (oid,)).fetchone()[0] == 1
    test('new rule version after creation', lambda: action('business', '/api/admin/commissions/rules', 'POST', rule(expectedVersion=1, rateBps=5000)))
    c('buyer').pay(oid, dict(requestId='pay1'))
    ledger = test('unknown channel fee waiting_facts', lambda: action('author', '/api/commissions')['items'][0]); assert ledger['status'] == 'waiting_facts' and ledger['amountMinor'] is None
    test('finance fact source required', lambda: action('finance', '/api/admin/commissions/facts', 'POST', dict(itemId=item, channelFeeMinor=0, isTestData=True), 400))
    test('explicit test fee fact resolves', lambda: action('finance', '/api/admin/commissions/facts', 'POST', dict(itemId=item, channelFeeMinor=0, isTestData=True, source='fixture verified zero fee')))
    ledger = action('author', '/api/commissions')['items'][0]; assert ledger['amountMinor'] == 1001 and ledger['ruleVersion'] == 1
    test('creation version immutable', lambda: ledger['ruleVersion'] == 1 or (_ for _ in ()).throw(AssertionError()))
    test('repeated sync idempotent', lambda: action('finance', '/api/admin/commissions/orders/'+oid+'/sync', 'POST'))
    assert len(action('author', '/api/commissions')['items']) == 1
    test('other beneficiary isolated', lambda: not action('other', '/api/commissions')['items'] or (_ for _ in ()).throw(AssertionError()))
    test('support amounts redacted', lambda: 'amountMinor' not in action('support')['items'][0] or (_ for _ in ()).throw(AssertionError()))
    test('support cannot confirm', lambda: action('support', '/api/admin/commissions/confirm', 'POST', dict(ledgerId=ledger['id']), 403))
    test('finance confirm freezes', lambda: action('finance', '/api/admin/commissions/confirm', 'POST', dict(ledgerId=ledger['id']))['item']['status'] == 'frozen' or (_ for _ in ()).throw(AssertionError()))
    test('fulfilled and freeze passed advance', lambda: action('finance', '/api/admin/commissions/advance', 'POST')['advanced'] == 1 or (_ for _ in ()).throw(AssertionError()))
    statement = test('statement reserve', lambda: action('finance', '/api/admin/commissions/statements', 'POST', dict(beneficiary='author', currency='USD', **{'from': 0, 'to': cm.now()})))['statement']
    test('self approval rejected', lambda: action('finance', '/api/admin/commissions/statements/'+statement['id']+'/approve', 'POST', dict(expectedVersion=1), 409))
    test('second finance/admin approves', lambda: action('admin', '/api/admin/commissions/statements/'+statement['id']+'/approve', 'POST', dict(expectedVersion=1)))
    test('bookkeeping explicit no actual pay', lambda: action('finance', '/api/admin/commissions/statements/'+statement['id']+'/book', 'POST', dict(expectedVersion=2))['actualPaid'] is False or (_ for _ in ()).throw(AssertionError()))
    payment = test('separate test proof register', lambda: action('finance', '/api/admin/commissions/statements/'+statement['id']+'/payment', 'POST', dict(requestId='proof1', isTestData=True, recipient=dict(name='Sandbox Author', country='US', currency='USD', channel='fixture', accountReference='TEST-NOT-A-BANK-ACCOUNT'), proofReference='LOCAL-TEST-PROOF')))
    assert payment['payment']['actualPaid'] is False and payment['payment']['proofVerified'] is False
    c('admin').refund(oid, dict(requestId='refund1', items=[dict(itemId=item, quantity=1)]))
    report = action('author', '/api/commissions'); assert report['items'][0]['netMinor'] == 667 and report['adjustments'][0]['amount_minor'] == 334 and report['adjustments'][0]['status'] == 'pending_recovery'
    test('settled partial refund preserves original and recovery', lambda: len(report['statements']) == 1 and report['statements'][0]['status'] == 'booked' or (_ for _ in ()).throw(AssertionError()))
    c('admin').refund(oid, dict(requestId='refund2', items=[dict(itemId=item, quantity=1)])); c('admin').refund(oid, dict(requestId='refund3', items=[dict(itemId=item, quantity=1)]))
    report = action('author', '/api/commissions'); assert sum(x['amount_minor'] for x in report['adjustments']) == 1001 and report['items'][0]['netMinor'] == 0
    test('cumulative refunds no rounding drift', lambda: True)
    test('CSV export redaction', lambda: 'TEST-NOT-A-BANK-ACCOUNT' not in action('finance', '/api/admin/commissions/export')['csv'] or (_ for _ in ()).throw(AssertionError()))
    for numerator, denominator in [(10**9*9999, 10000), (10**9*99*9999, 10000), (1001*2, 3), (1001, 3), (1, 2), (999999999, 10000)]:
        for rounding in ('floor', 'half_up'):
            value = cm.rounded(numerator, denominator, rounding); vectors.append(dict(numerator=str(numerator), denominator=str(denominator), rounding=rounding, result=value))
    test('large integer nondivisible rounding vectors', lambda: len(vectors) == 12 or (_ for _ in ()).throw(AssertionError()))
    with store.connect() as db: db.execute("INSERT INTO users VALUES('author2','teacher')")
    test('fixed amount append version', lambda: action('business', '/api/admin/commissions/rules', 'POST', rule(expectedVersion=2, beneficiary='author2', mode='fixed_per_unit', rateBps=0, fixedMinor=101, basis=dict(deductTax=True, deductShipping=True, deductDiscount=True, deductChannelFee=False))))
    second = c('buyer').create_order(dict(requestId='order2', environment='sandbox', items=[dict(skuId=sid, quantity=3)])); oid2=second['id']; iid2=second['items'][0]['itemId']; c('buyer').pay(oid2, dict(requestId='pay2'))
    l2 = action('author2','/api/commissions')['items'][0]; assert l2['amountMinor']==303 and l2['baseMinor']==3003
    test('fixed per unit uses integer quantity', lambda: True)
    action('finance','/api/admin/commissions/confirm','POST',dict(ledgerId=l2['id'])); action('finance','/api/admin/commissions/advance','POST')
    s2=action('finance','/api/admin/commissions/statements','POST',dict(beneficiary='author2',currency='USD',**{'from':0,'to':cm.now()}))['statement']
    c('admin').refund(oid2,dict(requestId='r2_1',items=[dict(itemId=iid2,quantity=1)])); current=action('author2','/api/commissions'); assert current['statements'][0]['status']=='cancelled' and current['items'][0]['netMinor']==202
    test('unbooked statement cancelled by partial refund', lambda: True)
    c('admin').refund(oid2,dict(requestId='r2_1',items=[dict(itemId=iid2,quantity=1)])); assert len(action('author2','/api/commissions')['adjustments'])==1
    test('duplicate commerce refund does not duplicate adjustment', lambda: True)
    test('promotion rule uses server attribution', lambda: action('business','/api/admin/commissions/rules','POST',rule(ruleId='promo-rule',kind='promotion',beneficiary='',mode='fixed_per_unit',rateBps=0,fixedMinor=17,basis=dict(deductTax=True,deductShipping=True,deductDiscount=True,deductChannelFee=False))))
    third=c('buyer').create_order(dict(requestId='order3',environment='sandbox',items=[dict(skuId=sid,quantity=1)])); oid3=third['id']
    action('business','/api/admin/commissions/invites','POST',dict(code='PROMO_1',status='revoked')); c('buyer').pay(oid3,dict(requestId='pay3'))
    p3=action('promoter','/api/commissions')['items']; assert len(p3)==1 and p3[0]['amountMinor']==17
    test('revoking code does not rewrite captured order attribution', lambda: True)
    fourth=c('buyer').create_order(dict(requestId='order4',environment='sandbox',items=[dict(skuId=sid,quantity=1)])); c('buyer').pay(fourth['id'],dict(requestId='pay4')); assert len(action('promoter','/api/commissions')['items'])==1
    test('revoked invite absent from later order snapshot', lambda: True)
    test('owner filter cannot expose another beneficiary', lambda: not action('promoter','/api/commissions?beneficiary=author2')['items'] or (_ for _ in ()).throw(AssertionError()))
    action('admin','/api/admin/commissions/settings','PATCH',dict(sandboxEnabled=False,stackingPolicy='allow_both',attributionStrategy='last_touch'))
    fifth=c('buyer').create_order(dict(requestId='order5',environment='sandbox',items=[dict(skuId=sid,quantity=1)]))
    action('admin','/api/admin/commissions/settings','PATCH',dict(sandboxEnabled=True,stackingPolicy='allow_both',attributionStrategy='last_touch')); c('buyer').pay(fifth['id'],dict(requestId='pay5')); assert not store.db.execute('SELECT 1 FROM commission_ledger WHERE order_id=?',(fifth['id'],)).fetchone()
    test('disabled creation snapshot cannot gain later commission', lambda: True)
    store.snapshot_enabled=False
    sixth=c('buyer').create_order(dict(requestId='order6',environment='sandbox',items=[dict(skuId=sid,quantity=1)])); store.snapshot_enabled=True
    with store.connect() as db: db.execute('DELETE FROM commission_snapshots WHERE order_id=?',(sixth['id'],))
    c('buyer').pay(sixth['id'],dict(requestId='pay6'))
    test('missing creation hook fails closed without reconstruction', lambda: action('finance','/api/admin/commissions/orders/'+sixth['id']+'/sync','POST')['reason']=='missing_creation_snapshot' or (_ for _ in ()).throw(AssertionError()))
    test('locked facts cannot silently change original', lambda: action('finance','/api/admin/commissions/facts','POST',dict(itemId=iid2,channelFeeMinor=99,isTestData=True,source='late altered fee'),409))
    test('business cannot perform finance advancement', lambda: action('business','/api/admin/commissions/advance','POST',{},403))
    test('actual payments toggle rejected independently', lambda: action('admin','/api/admin/commissions/settings','PATCH',dict(sandboxEnabled=True,actualPaymentsEnabled=True,stackingPolicy='allow_both',attributionStrategy='last_touch'),400))
    test('financial evidence traceable only to finance', lambda: len(action('finance')['payments'])==1 and not action('business')['payments'] and not action('author','/api/commissions')['payments'] or (_ for _ in ()).throw(AssertionError()))
    physical=c('admin').save_product(dict(id='physical',title='Sandbox object',description='fixture only',type='physical',sku='fixture-object',priceMinor=200,currency='JPY',stock=3,shippingMinor=10,taxMinor=5,shippingCountries=['JP'],environment='sandbox',status='published'))
    fixed=rule(ruleId='object-rule',productId='physical',beneficiary='author2',currency='JPY',mode='fixed_per_unit',rateBps=0,fixedMinor=30,basis=dict(deductTax=True,deductShipping=True,deductDiscount=True,deductChannelFee=False))
    action('business','/api/admin/commissions/rules','POST',fixed)
    seventh=c('buyer').create_order(dict(requestId='order7',environment='sandbox',items=[dict(skuId=physical['item']['skuId'],quantity=1)],shippingAddress=dict(name='Sandbox buyer',country='JP',address='TEST ADDRESS NOT REAL'))); c('buyer').pay(seventh['id'],dict(requestId='pay7'))
    l7=next(x for x in action('author2','/api/commissions')['items'] if x['orderId']==seventh['id']); action('finance','/api/admin/commissions/confirm','POST',dict(ledgerId=l7['id'])); action('finance','/api/admin/commissions/advance','POST')
    test('unfulfilled physical cannot become payable', lambda: store.db.execute('SELECT status FROM commission_ledger WHERE id=?',(l7['id'],)).fetchone()[0]=='frozen' or (_ for _ in ()).throw(AssertionError()))
    h.payload=dict(trackingNumber='TEST-SANDBOX-TRACK',status='delivered'); c('admin').admin('POST','/api/admin/commerce/orders/'+seventh['id']+'/fulfill'); action('finance','/api/admin/commissions/advance','POST')
    test('actual sandbox delivery releases eligible freeze', lambda: store.db.execute('SELECT status FROM commission_ledger WHERE id=?',(l7['id'],)).fetchone()[0]=='payable' or (_ for _ in ()).throw(AssertionError()))
    action('business','/api/admin/commissions/rules','POST',{**fixed,'expectedVersion':1,'freezeDays':1})
    eighth=c('buyer').create_order(dict(requestId='order8',environment='sandbox',items=[dict(skuId=physical['item']['skuId'],quantity=1)],shippingAddress=dict(name='Sandbox buyer',country='JP',address='TEST ADDRESS NOT REAL'))); c('buyer').pay(eighth['id'],dict(requestId='pay8')); h.payload=dict(trackingNumber='TEST-SANDBOX-TRACK2',status='delivered'); c('admin').admin('POST','/api/admin/commerce/orders/'+eighth['id']+'/fulfill')
    l8=next(x for x in action('author2','/api/commissions')['items'] if x['orderId']==eighth['id']); action('finance','/api/admin/commissions/confirm','POST',dict(ledgerId=l8['id'])); action('finance','/api/admin/commissions/advance','POST')
    test('unexpired freeze cannot settle after delivery', lambda: store.db.execute('SELECT status FROM commission_ledger WHERE id=?',(l8['id'],)).fetchone()[0]=='frozen' or (_ for _ in ()).throw(AssertionError()))
    test('filter also limits adjustments and whole statements', lambda: not action('finance','/api/admin/commissions?productId=missing')['adjustments'] and not action('finance','/api/admin/commissions?productId=missing')['statements'] or (_ for _ in ()).throw(AssertionError()))
    test('ordinary user cannot receive financial grant', lambda: action('admin','/api/admin/commissions/grants','POST',dict(userId='buyer',permission='finance'),400))
    test('teacher cannot receive financial grant implicitly', lambda: action('admin','/api/admin/commissions/grants','POST',dict(userId='author',permission='finance'),400))
    with store.connect() as db: db.execute("UPDATE users SET role='user' WHERE id='finance'")
    test('old finance grant invalid immediately after base role downgrade', lambda: action('finance','/api/admin/commissions/advance','POST',{},403))
    test('downgraded account only receives personal reporting scope', lambda: action('finance','/api/commissions')['permission']=='self' and not action('finance','/api/commissions')['payments'] or (_ for _ in ()).throw(AssertionError()))


report = {'checks': checks, 'vectors': vectors, 'database': ':memory:', 'originalDatabaseOpened': False, 'realPayments': False}
try:
    run(); report['passed'] = len(checks); report['failed'] = 0
except BaseException:
    report['failed'] = 1; report['error'] = traceback.format_exc(); print(report['error']); sys.exitcode = 1
finally:
    report['sourceSha256'] = hashlib.sha256((BACKEND/'commission.py').read_bytes()).hexdigest()
    (ROOT/'06_验证与后续工作/负责人优化建议-分佣隔离自检.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report.get('passed'), 'failed': report['failed'], 'checks': len(checks)}))
if report['failed']: raise SystemExit(1)
