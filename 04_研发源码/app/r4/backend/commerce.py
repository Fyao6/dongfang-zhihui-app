"""Sandbox commerce. Production charging and production media grants are forbidden."""
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

try:
    from membership_lifecycle import Membership
except ModuleNotFoundError:
    import importlib.util
    _membership_spec=importlib.util.spec_from_file_location('eastern_membership_lifecycle',__import__('pathlib').Path(__file__).with_name('membership_lifecycle.py'))
    _membership_module=importlib.util.module_from_spec(_membership_spec);_membership_spec.loader.exec_module(_membership_module)
    Membership=_membership_module.Membership

try:
    from commission import snapshot_order as commission_snapshot_order, sync_commission_order as commission_sync_order
except ModuleNotFoundError:
    import importlib.util
    _commission_spec=importlib.util.spec_from_file_location('eastern_commerce_commission',__import__('pathlib').Path(__file__).with_name('commission.py'))
    _commission_module=importlib.util.module_from_spec(_commission_spec);_commission_spec.loader.exec_module(_commission_module)
    commission_snapshot_order,commission_sync_order=_commission_module.snapshot_order,_commission_module.sync_commission_order

HOLD_MS = 15 * 60 * 1000
MAX_MINOR = 1_000_000_000
SUPPORTED_CURRENCIES = {'CNY','USD','EUR','GBP','HKD','TWD','JPY','KRW','CAD','AUD','NZD','SGD','CHF','THB','MYR','IDR','VND','PHP','INR','AED','SAR','BRL','MXN','ZAR','BHD','KWD','OMR','JOD','TND'}

# The same DDL and invariant triggers are used by the D1 adapter.
DDL = r'''
CREATE TABLE IF NOT EXISTS commerce_config(key TEXT PRIMARY KEY,data TEXT NOT NULL);
INSERT OR IGNORE INTO commerce_config VALUES('settings','{"sandboxEnabled":false,"productionEnabled":false}');
CREATE TABLE IF NOT EXISTS commerce_products(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL,type TEXT NOT NULL CHECK(type IN ('digital','physical','membership')),environment TEXT NOT NULL CHECK(environment IN ('sandbox','production')),status TEXT NOT NULL CHECK(status IN ('draft','published','archived')),version INTEGER NOT NULL,content_id TEXT NOT NULL,shipping_countries TEXT NOT NULL,shipping_minor INTEGER NOT NULL CHECK(shipping_minor>=0),tax_minor INTEGER NOT NULL CHECK(tax_minor>=0),mutation_id TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,data TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS commerce_skus(id TEXT PRIMARY KEY,product_id TEXT NOT NULL REFERENCES commerce_products(id),sku TEXT NOT NULL,environment TEXT NOT NULL,price_minor INTEGER NOT NULL CHECK(price_minor>=0),currency TEXT NOT NULL,stock INTEGER NOT NULL CHECK(stock>=0),reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved>=0 AND reserved<=stock),version INTEGER NOT NULL,UNIQUE(environment,sku));
CREATE TABLE IF NOT EXISTS commerce_prices(id TEXT PRIMARY KEY,sku_id TEXT NOT NULL REFERENCES commerce_skus(id),version INTEGER NOT NULL,price_minor INTEGER NOT NULL,currency TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(sku_id,version));
CREATE TABLE IF NOT EXISTS commerce_carts(owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),data TEXT NOT NULL,updated INTEGER NOT NULL,PRIMARY KEY(owner,environment));
CREATE TABLE IF NOT EXISTS commerce_orders(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,status TEXT NOT NULL,payment_status TEXT NOT NULL,fulfillment_status TEXT NOT NULL,aftersale_status TEXT NOT NULL,currency TEXT NOT NULL,subtotal_minor INTEGER NOT NULL,shipping_minor INTEGER NOT NULL,tax_minor INTEGER NOT NULL,total_minor INTEGER NOT NULL,refunded_minor INTEGER NOT NULL DEFAULT 0,shipping_address TEXT NOT NULL,tracking TEXT NOT NULL DEFAULT '{}',reserved_until INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(owner,environment,request_id));
CREATE INDEX IF NOT EXISTS commerce_orders_owner ON commerce_orders(owner,environment,created);
CREATE TABLE IF NOT EXISTS commerce_order_items(id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES commerce_orders(id),sku_id TEXT NOT NULL REFERENCES commerce_skus(id),product_id TEXT NOT NULL,title TEXT NOT NULL,type TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>0),price_minor INTEGER NOT NULL,currency TEXT NOT NULL,unit_shipping_minor INTEGER NOT NULL,unit_tax_minor INTEGER NOT NULL,content_id TEXT NOT NULL,price_version INTEGER NOT NULL,refunded_quantity INTEGER NOT NULL DEFAULT 0 CHECK(refunded_quantity>=0 AND refunded_quantity<=quantity),snapshot_data TEXT NOT NULL DEFAULT '{}',UNIQUE(order_id,sku_id));
CREATE TABLE IF NOT EXISTS commerce_reservations(order_id TEXT NOT NULL REFERENCES commerce_orders(id),sku_id TEXT NOT NULL REFERENCES commerce_skus(id),quantity INTEGER NOT NULL CHECK(quantity>0),state TEXT NOT NULL CHECK(state IN ('held','consumed','released')),PRIMARY KEY(order_id,sku_id));
CREATE TABLE IF NOT EXISTS commerce_payment_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL REFERENCES commerce_orders(id),request_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('sandbox_pay','refund')),fingerprint TEXT NOT NULL,amount_minor INTEGER NOT NULL,currency TEXT NOT NULL,items TEXT NOT NULL,status TEXT NOT NULL CHECK(status='applied'),created INTEGER NOT NULL,UNIQUE(owner,environment,kind,request_id));
CREATE UNIQUE INDEX IF NOT EXISTS commerce_one_payment ON commerce_payment_events(order_id,kind) WHERE kind='sandbox_pay';
CREATE TABLE IF NOT EXISTS commerce_entitlements(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL REFERENCES commerce_orders(id),item_id TEXT NOT NULL UNIQUE REFERENCES commerce_order_items(id),content_id TEXT NOT NULL,type TEXT NOT NULL,quantity INTEGER NOT NULL,remaining INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','revoked')),created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS commerce_aftersale_requests(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL REFERENCES commerce_orders(id),request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,reason TEXT NOT NULL,quantity INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(owner,environment,request_id));
CREATE TABLE IF NOT EXISTS commerce_inventory_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL,item_id TEXT NOT NULL,sku_id TEXT NOT NULL,quantity_delta INTEGER NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TRIGGER IF NOT EXISTS commerce_reserve_check BEFORE INSERT ON commerce_reservations WHEN NEW.state='held' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_skus s JOIN commerce_products p ON p.id=s.product_id JOIN commerce_orders o ON o.id=NEW.order_id JOIN commerce_order_items i ON i.order_id=o.id AND i.sku_id=s.id WHERE s.id=NEW.sku_id AND s.environment=o.environment AND p.environment=o.environment AND p.status='published' AND o.payment_status='unpaid' AND s.stock-s.reserved>=NEW.quantity AND s.version=i.price_version) THEN RAISE(ABORT,'commerce_out_of_stock') END;
END;
CREATE TRIGGER IF NOT EXISTS commerce_reserve_hold AFTER INSERT ON commerce_reservations WHEN NEW.state='held' BEGIN UPDATE commerce_skus SET reserved=reserved+NEW.quantity WHERE id=NEW.sku_id; END;
CREATE TRIGGER IF NOT EXISTS commerce_reserve_release AFTER UPDATE OF state ON commerce_reservations WHEN OLD.state='held' AND NEW.state='released' BEGIN UPDATE commerce_skus SET reserved=reserved-NEW.quantity WHERE id=NEW.sku_id; END;
CREATE TRIGGER IF NOT EXISTS commerce_reserve_consume AFTER UPDATE OF state ON commerce_reservations WHEN OLD.state='held' AND NEW.state='consumed' BEGIN UPDATE commerce_skus SET reserved=reserved-NEW.quantity,stock=stock-NEW.quantity WHERE id=NEW.sku_id; END;
CREATE TRIGGER IF NOT EXISTS commerce_order_closed AFTER UPDATE OF status ON commerce_orders WHEN OLD.status='awaiting_payment' AND NEW.status='closed' BEGIN UPDATE commerce_reservations SET state='released' WHERE order_id=NEW.id AND state='held'; END;
CREATE TRIGGER IF NOT EXISTS commerce_order_paid AFTER UPDATE OF payment_status ON commerce_orders WHEN OLD.payment_status='unpaid' AND NEW.payment_status='paid' BEGIN
 UPDATE commerce_reservations SET state='consumed' WHERE order_id=NEW.id AND state='held';
 INSERT INTO commerce_entitlements SELECT 'sandbox:'||i.id,NEW.owner,'sandbox',NEW.id,i.id,i.content_id,i.type,i.quantity,i.quantity,'active',NEW.updated,NEW.updated FROM commerce_order_items i WHERE i.order_id=NEW.id AND i.type IN ('digital','membership');
END;
CREATE TRIGGER IF NOT EXISTS commerce_refund_check BEFORE INSERT ON commerce_payment_events WHEN NEW.kind='refund' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=NEW.order_id AND o.owner=NEW.owner AND o.environment=NEW.environment AND o.payment_status IN ('paid','partially_refunded')) THEN RAISE(ABORT,'commerce_refund_state') END;
 SELECT CASE WHEN json_array_length(NEW.items)<1 OR EXISTS(SELECT 1 FROM json_each(NEW.items) j LEFT JOIN commerce_order_items i ON i.id=json_extract(j.value,'$.itemId') AND i.order_id=NEW.order_id WHERE i.id IS NULL OR json_type(j.value,'$.quantity')!='integer' OR json_extract(j.value,'$.quantity')<1 OR json_extract(j.value,'$.quantity')>i.quantity-i.refunded_quantity) OR (SELECT count(*) FROM json_each(NEW.items))!=(SELECT count(DISTINCT json_extract(value,'$.itemId')) FROM json_each(NEW.items)) THEN RAISE(ABORT,'commerce_refund_quantity') END;
 SELECT CASE WHEN NEW.amount_minor!=(SELECT sum(json_extract(j.value,'$.quantity')*(i.price_minor+i.unit_shipping_minor+i.unit_tax_minor)) FROM json_each(NEW.items) j JOIN commerce_order_items i ON i.id=json_extract(j.value,'$.itemId') AND i.order_id=NEW.order_id) THEN RAISE(ABORT,'commerce_refund_amount') END;
END;
CREATE TRIGGER IF NOT EXISTS commerce_refund_apply AFTER INSERT ON commerce_payment_events WHEN NEW.kind='refund' BEGIN
 UPDATE commerce_order_items SET refunded_quantity=refunded_quantity+(SELECT json_extract(j.value,'$.quantity') FROM json_each(NEW.items) j WHERE json_extract(j.value,'$.itemId')=commerce_order_items.id) WHERE order_id=NEW.order_id AND id IN (SELECT json_extract(value,'$.itemId') FROM json_each(NEW.items));
 UPDATE commerce_orders SET refunded_minor=refunded_minor+NEW.amount_minor,payment_status=CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=NEW.order_id AND quantity>refunded_quantity) THEN 'refunded' ELSE 'partially_refunded' END,aftersale_status=CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=NEW.order_id AND quantity>refunded_quantity) THEN 'refunded' ELSE 'partially_refunded' END,status=CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=NEW.order_id AND quantity>refunded_quantity) THEN 'refunded' ELSE 'partially_refunded' END,updated=NEW.created WHERE id=NEW.order_id;
 UPDATE commerce_aftersale_requests SET status=CASE WHEN (SELECT payment_status FROM commerce_orders WHERE id=NEW.order_id)='refunded' THEN 'resolved' ELSE 'processing' END,updated=NEW.created WHERE order_id=NEW.order_id AND status IN ('pending','processing');
END;
CREATE TRIGGER IF NOT EXISTS commerce_item_refunded AFTER UPDATE OF refunded_quantity ON commerce_order_items WHEN NEW.refunded_quantity>OLD.refunded_quantity BEGIN
 UPDATE commerce_skus SET stock=stock+NEW.refunded_quantity-OLD.refunded_quantity WHERE id=NEW.sku_id AND (NEW.type!='physical' OR EXISTS(SELECT 1 FROM commerce_orders WHERE id=NEW.order_id AND fulfillment_status NOT IN ('shipped','delivered')));
 INSERT INTO commerce_inventory_events SELECT 'refund:'||NEW.id||':'||NEW.refunded_quantity,o.owner,'sandbox',NEW.order_id,NEW.id,NEW.sku_id,CASE WHEN NEW.type='physical' AND o.fulfillment_status IN ('shipped','delivered') THEN 0 ELSE NEW.refunded_quantity-OLD.refunded_quantity END,CASE WHEN NEW.type='physical' AND o.fulfillment_status IN ('shipped','delivered') THEN 'refund_after_dispatch_no_restock' ELSE 'refund_restock' END,(SELECT max(created) FROM commerce_payment_events WHERE order_id=NEW.order_id) FROM commerce_orders o WHERE o.id=NEW.order_id;
 UPDATE commerce_entitlements SET remaining=NEW.quantity-NEW.refunded_quantity,status=CASE WHEN NEW.quantity=NEW.refunded_quantity THEN 'revoked' ELSE 'active' END,updated=(SELECT max(created) FROM commerce_payment_events WHERE order_id=NEW.order_id) WHERE item_id=NEW.id AND environment='sandbox';
END;
'''


def init_schema(db):
    db.executescript(DDL)
    schema = db.execute("SELECT sql FROM sqlite_master WHERE name='commerce_skus'").fetchone()[0]
    if 'product_id TEXT NOT NULL UNIQUE REFERENCES' in schema:
        db.execute('BEGIN IMMEDIATE')
        schema = db.execute("SELECT sql FROM sqlite_master WHERE name='commerce_skus'").fetchone()[0]
        if 'product_id TEXT NOT NULL UNIQUE REFERENCES' in schema:
            for sql in sku_migration():
                db.execute(sql)
    for sql in VARIANT_DDL:
        db.execute(sql)


SKU_TABLE = next(line for line in DDL.splitlines() if line.startswith('CREATE TABLE IF NOT EXISTS commerce_skus('))
VARIANT_DDL = (
    'CREATE INDEX IF NOT EXISTS commerce_skus_product ON commerce_skus(product_id)',
    'CREATE TABLE IF NOT EXISTS commerce_sku_variants(sku_id TEXT PRIMARY KEY REFERENCES commerce_skus(id),options TEXT NOT NULL,active INTEGER NOT NULL CHECK(active IN (0,1)))',
)


def sku_migration():
    # Recreate under the original name so child references and triggers retain their targets.
    # Check deferred references before clearing the transient DROP violation.
    return (
        'PRAGMA defer_foreign_keys=ON',
        'CREATE TABLE commerce_skus_copy AS SELECT * FROM commerce_skus',
        'DROP TABLE commerce_skus',
        SKU_TABLE,
        'INSERT INTO commerce_skus SELECT * FROM commerce_skus_copy',
        'DROP TABLE commerce_skus_copy',
        'CREATE TABLE commerce_sku_fk_check(count INTEGER CHECK(count=0))',
        "INSERT INTO commerce_sku_fk_check SELECT count(*) FROM pragma_foreign_key_check WHERE parent='commerce_skus'",
        'DROP TABLE commerce_sku_fk_check',
        'PRAGMA defer_foreign_keys=OFF',
    )


SKU_COLUMNS = 's.id sku_id,s.sku,s.price_minor,s.currency,s.stock,s.reserved,s.version price_version,coalesce(v.options,\'[]\') sku_options,coalesce(v.active,1) sku_active'
SKU_JOIN = 'JOIN commerce_skus s ON s.product_id=p.id LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id'


def public_media(db, reference):
    """Only a published, validated imageUrl is a public cover grant, never order media."""
    return bool(db.execute("SELECT 1 FROM commerce_products p WHERE p.status='published' AND json_extract(p.data,'$.imageUrl')=? AND (p.environment='production' OR (p.environment='sandbox' AND EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1)))",(reference,)).fetchone())


def now():
    return time.time_ns() // 1_000_000


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()


def iso(value):
    return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


class Commerce:
    def __init__(self, store, handler, error, limiter):
        self.store, self.h, self.Error, self.rate = store, handler, error, limiter
        self.uid = handler.user['id'] if handler.user else ''

    def fail(self, status, message):
        raise self.Error(status, message)

    def text(self, value, maximum, minimum=0):
        if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
            self.fail(400, '文本格式或长度不符合要求。')
        return value.strip()

    def integer(self, value, minimum=0, maximum=MAX_MINOR):
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            self.fail(400, '金额、数量与库存必须为允许范围内的整数。')
        return value

    def environment(self, value):
        if value not in ('production', 'sandbox'):
            self.fail(400, '无效交易环境。')
        return value

    def settings(self, db):
        row = db.execute("SELECT data FROM commerce_config WHERE key='settings'").fetchone()
        value = json.loads(row['data']) if row else {}
        return {'sandboxEnabled': value.get('sandboxEnabled') is True, 'productionEnabled': False}

    def enabled(self, db, environment):
        if environment != 'sandbox':
            self.fail(403, '正式交易尚未启用；此模块只允许沙箱测试，不会真实扣款。')
        if not self.settings(db)['sandboxEnabled']:
            self.fail(503, '沙箱交易尚未由管理员开启。')

    def expire(self, db):
        db.execute("UPDATE commerce_orders SET status='closed',payment_status='expired',updated=? WHERE status='awaiting_payment' AND payment_status='unpaid' AND reserved_until<=?", (now(), now()))

    def product(self, row):
        return {**json.loads(row['data']), 'id': row['id'], 'productId': row['id'], 'title': row['title'], 'description': row['description'], 'type': row['type'], 'environment': row['environment'], 'status': row['status'], 'version': row['version'], 'contentId': row['content_id'], 'shippingCountries': json.loads(row['shipping_countries']), 'shippingMinor': row['shipping_minor'], 'taxMinor': row['tax_minor'], 'sandboxOnly': row['environment']=='sandbox'}

    def variant(self, row):
        return {'skuId': row['sku_id'], 'sku': row['sku'], 'options': json.loads(row['sku_options']), 'active': bool(row['sku_active']), 'priceVersion': row['price_version'], 'priceMinor': row['price_minor'], 'currency': row['currency'], 'stock': row['stock'], 'reserved': row['reserved'], 'availableStock': row['stock']-row['reserved'], 'purchasable': row['environment']=='sandbox' and row['status']=='published' and bool(row['sku_active']) and row['stock']>row['reserved']}

    def products(self, db, environment=None, published=False):
        conditions, args = [], []
        if environment:
            conditions.append('p.environment=?'); args.append(environment)
        if published:
            conditions.append("p.status='published' AND coalesce(v.active,1)=1")
        query = f'SELECT p.*,{SKU_COLUMNS} FROM commerce_products p {SKU_JOIN}'
        if conditions:
            query += ' WHERE '+' AND '.join(conditions)
        products = {}
        for row in db.execute(query+' ORDER BY p.updated DESC,p.id,s.sku COLLATE BINARY', args):
            variant = self.variant(row)
            product = products.setdefault(row['id'], {**self.product(row), **variant, 'variants': []})
            product['variants'].append(variant)
        for product in products.values():
            primary = next((sku for sku in product['variants'] if sku['active']), product['variants'][0])
            product.update(primary, purchasable=any(sku['purchasable'] for sku in product['variants']))
        return list(products.values())

    def commission_processing(self, db, row):
        opened=False
        try:
            db.execute('SAVEPOINT commission_derive');opened=True
            result=commission_sync_order(db,row['id'])
            rows=db.execute('SELECT status FROM commission_ledger WHERE order_id=?',(row['id'],)).fetchall()
            db.execute('RELEASE SAVEPOINT commission_derive');opened=False
            if not result.get('synced'):
                return {'status':result.get('reason','unavailable'),'retryAvailable':False,'sandboxOnly':True,'actualPaid':False}
            paid=row['payment_status'] in ('paid','partially_refunded','refunded')
            return {'status':'awaiting_payment' if not paid else 'waiting_facts' if any(x['status']=='waiting_facts' for x in rows) else 'synchronized','ledgerItemCount':len(rows),'retryAvailable':False,'sandboxOnly':True,'actualPaid':False}
        except Exception:
            if opened:
                try:
                    db.execute('ROLLBACK TO SAVEPOINT commission_derive');db.execute('RELEASE SAVEPOINT commission_derive')
                except Exception:
                    pass
            return {'status':'sync_pending','retryAvailable':True,'retryAction':'refresh-order','sandboxOnly':True,'actualPaid':False}

    def order(self, db, row):
        if not row:
            self.fail(404, '未找到订单。')
        lines = db.execute('SELECT * FROM commerce_order_items WHERE order_id=? ORDER BY id', (row['id'],)).fetchall()
        events = db.execute('SELECT id,kind,request_id,amount_minor,currency,status,created FROM commerce_payment_events WHERE order_id=? ORDER BY created,id', (row['id'],)).fetchall()
        requests=db.execute('SELECT id,request_id,reason,quantity,status,created,updated FROM commerce_aftersale_requests WHERE order_id=? ORDER BY created,id',(row['id'],)).fetchall()
        membership_processing=None
        membership_lines=[i for i in lines if i['type']=='membership']
        if membership_lines:
            snapshots=db.execute('SELECT item_id,subscription_id FROM membership_order_snapshots WHERE order_id=? AND owner=?',(row['id'],row['owner'])).fetchall()
            complete=len(snapshots)==len(membership_lines);linked=complete and all(v['subscription_id'] for v in snapshots)
            paid=row['payment_status'] in ('paid','partially_refunded','refunded')
            membership_processing={'environment':'sandbox','status':'linked' if linked else 'unavailable' if not complete else 'pending' if paid else 'awaiting_payment','retryAvailable':bool(complete and paid and not linked and row['payment_status']!='refunded'),'subscriptionIds':sorted({v['subscription_id'] for v in snapshots if v['subscription_id']}),'grantsProductionAccess':False}
        return {'commissionProcessing':self.commission_processing(db,row),'membershipProcessing':membership_processing,'id': row['id'], 'ownerId': row['owner'], 'environment': row['environment'], 'sandboxOnly': True, 'grantsProductionAccess': False, 'requestId': row['request_id'], 'status': row['status'], 'paymentStatus': row['payment_status'], 'fulfillmentStatus': row['fulfillment_status'], 'aftersaleStatus': row['aftersale_status'], 'currency': row['currency'], 'subtotalMinor': row['subtotal_minor'], 'shippingMinor': row['shipping_minor'], 'taxMinor': row['tax_minor'], 'totalMinor': row['total_minor'], 'refundedMinor': row['refunded_minor'], 'shippingAddress': json.loads(row['shipping_address']), 'inventoryEvents':[{'id':v['id'],'skuId':v['sku_id'],'itemId':v['item_id'],'quantityDelta':v['quantity_delta'],'reason':v['reason'],'environment':'sandbox','createdAt':iso(v['created'])} for v in db.execute('SELECT * FROM commerce_inventory_events WHERE order_id=? ORDER BY created,id',(row['id'],)).fetchall()], 'tracking': json.loads(row['tracking']), 'reservedUntil': iso(row['reserved_until']), 'createdAt': iso(row['created']), 'updatedAt': iso(row['updated']), 'items': [{**json.loads(i['snapshot_data']), 'id': i['id'], 'itemId': i['id'], 'skuId': i['sku_id'], 'productId': i['product_id'], 'title': i['title'], 'type': i['type'], 'quantity': i['quantity'], 'priceMinor': i['price_minor'], 'currency': i['currency'], 'unitShippingMinor': i['unit_shipping_minor'], 'unitTaxMinor': i['unit_tax_minor'], 'totalMinor': i['quantity']*(i['price_minor']+i['unit_shipping_minor']+i['unit_tax_minor']), 'contentId': i['content_id'], 'priceVersion': i['price_version'], 'refundedQuantity': i['refunded_quantity']} for i in lines], 'events': [{'id': e['id'], 'kind': e['kind'], 'requestId': e['request_id'], 'amountMinor': e['amount_minor'], 'currency': e['currency'], 'status': e['status'], 'environment': 'sandbox', 'createdAt': iso(e['created'])} for e in events], 'aftersaleRequests':[{'id':r['id'],'requestId':r['request_id'],'reason':r['reason'],'quantity':r['quantity'],'status':r['status'],'environment':'sandbox','createdAt':iso(r['created']),'updatedAt':iso(r['updated'])} for r in requests]}

    def own_order(self, db, order_id, admin=False):
        if admin:
            row = db.execute('SELECT * FROM commerce_orders WHERE id=?', (order_id,)).fetchone()
        else:
            row = db.execute('SELECT * FROM commerce_orders WHERE id=? AND owner=?', (order_id, self.uid)).fetchone()
        if not row:
            self.fail(404, '未找到订单。')
        return row

    def items(self, value):
        if not isinstance(value, list) or not 1 <= len(value) <= 30:
            self.fail(400, '请选择1至30种商品。')
        result = []
        for item in value:
            if not isinstance(item, dict):
                self.fail(400, '商品项目格式错误。')
            result.append({'skuId': self.text(item.get('skuId'), 100, 1), 'quantity': self.integer(item.get('quantity'), 1, 99)})
        if len({i['skuId'] for i in result}) != len(result):
            self.fail(400, '同一SKU请合并数量。')
        return sorted(result, key=lambda i: i['skuId'])

    def address(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict) or any(k not in ('name','phone','country','region','city','address','postalCode') for k in value):
            self.fail(400, '收货信息格式错误。')
        result = {key: self.text(v, 400 if key=='address' else 100) for key, v in value.items()}
        if result.get('country'):
            result['country'] = result['country'].upper()
            if not re.fullmatch('[A-Z]{2}', result['country']):
                self.fail(400, '配送国家须使用两位国家代码。')
        return result

    def quote(self, db, requested, address):
        lines, currencies, physical = [], set(), set()
        for item in requested:
            row = db.execute(f"SELECT p.*,{SKU_COLUMNS} FROM commerce_products p {SKU_JOIN} WHERE s.id=? AND s.environment='sandbox' AND p.environment='sandbox' AND p.status='published' AND coalesce(v.active,1)=1", (item['skuId'],)).fetchone()
            if not row:
                self.fail(409, '商品已下架或不属于沙箱。')
            if row['stock']-row['reserved'] < item['quantity']:
                self.fail(409, '商品库存不足。')
            currencies.add(row['currency']); physical.add(row['type']=='physical')
            if row['type']=='physical':
                if not all(address.get(k) for k in ('name','country','address')):
                    self.fail(400, '实物订单请填写收货人、国家与地址。')
                if address['country'] not in json.loads(row['shipping_countries']):
                    self.fail(400, '该商品不配送至所选国家。')
            lines.append((row,item['quantity']))
        if len(physical)>1:
            self.fail(409, '数字商品与实物商品须拆成独立订单。')
        if len(currencies)>1:
            self.fail(409, '不同币种的商品须拆成独立订单。')
        subtotal=sum(r['price_minor']*q for r,q in lines)
        shipping=sum((r['shipping_minor'] if r['type']=='physical' else 0)*q for r,q in lines)
        tax=sum(r['tax_minor']*q for r,q in lines)
        self.integer(subtotal+shipping+tax, 0, MAX_MINOR)
        return lines,currencies.pop(),subtotal,shipping,tax

    def create_order(self, data):
        environment=self.environment(data.get('environment','production'))
        request_id=self.text(data.get('requestId'),128,1)
        requested=self.items(data.get('items')); address=self.address(data.get('shippingAddress'))
        renewal_of=self.text(data['membershipRenewalOf'],100,1) if data.get('membershipRenewalOf') is not None else None
        semantic={'environment':environment,'items':requested,'shippingAddress':address}
        if renewal_of is not None:semantic['membershipRenewalOf']=renewal_of
        token=fingerprint(semantic)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); self.expire(db); self.enabled(db,environment)
            old=db.execute('SELECT * FROM commerce_orders WHERE owner=? AND environment=? AND request_id=?',(self.uid,environment,request_id)).fetchone()
            if old:
                if old['fingerprint']!=token: self.fail(409,'幂等编号已用于不同的订单内容。')
                return self.order(db,old)
            lines,currency,subtotal,shipping,tax=self.quote(db,requested,address)
            has_membership=any(r['type']=='membership' for r,q in lines)
            if renewal_of and not has_membership:self.fail(400,'续期关联只能用于会员订单。')
            lifecycle=Membership(self.store,self.h,self.Error,self.rate) if has_membership else None
            snapshots=lifecycle.snapshot_for_checkout(db,self.uid,requested,environment,renewal_of) if lifecycle else {}
            oid=str(uuid4()); timestamp=now(); is_physical=lines[0][0]['type']=='physical'
            db.execute('INSERT INTO commerce_orders(id,owner,environment,request_id,fingerprint,status,payment_status,fulfillment_status,aftersale_status,currency,subtotal_minor,shipping_minor,tax_minor,total_minor,refunded_minor,shipping_address,tracking,reserved_until,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,self.uid,'sandbox',request_id,token,'awaiting_payment','unpaid','awaiting_payment','none',currency,subtotal,shipping,tax,subtotal+shipping+tax,0,dump(address if is_physical else {}),'{}',timestamp+HOLD_MS,timestamp,timestamp))
            for r,q in lines:
                snapshot = {**json.loads(r['data']), 'sku': r['sku'], 'options': json.loads(r['sku_options'])}
                db.execute('INSERT INTO commerce_order_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid4()),oid,r['sku_id'],r['id'],r['title'],r['type'],q,r['price_minor'],currency,r['shipping_minor'] if r['type']=='physical' else 0,r['tax_minor'],r['content_id'],r['price_version'],0,dump(snapshot)))
                db.execute("INSERT INTO commerce_reservations VALUES(?,?,?,'held')",(oid,r['sku_id'],q))
            if lifecycle:lifecycle.capture_order_snapshots(db,self.uid,oid,snapshots)
            commission_snapshot_order(db,oid)
            self.store.audit(db,self.uid,'commerce.order.create',oid,'sandbox；无真实扣款')
            return self.order(db,self.own_order(db,oid))

    def pay(self, oid, data):
        request_id=self.text(data.get('requestId'),128,1)
        token=fingerprint({'orderId':oid,'kind':'sandbox_pay'})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); self.expire(db); self.enabled(db,'sandbox')
            row=self.own_order(db,oid)
            old=db.execute("SELECT * FROM commerce_payment_events WHERE owner=? AND environment='sandbox' AND kind='sandbox_pay' AND request_id=?",(self.uid,request_id)).fetchone()
            if old:
                if old['fingerprint']!=token: self.fail(409,'幂等编号已用于另一笔付款。')
                return self.order(db,row)
            if row['payment_status'] in ('paid','partially_refunded','refunded'):
                return self.order(db,row)
            if row['payment_status']!='unpaid' or row['status']!='awaiting_payment':
                self.fail(409,'订单已关闭或不能付款。')
            if db.execute("SELECT 1 FROM commerce_order_items i JOIN commerce_products p ON p.id=i.product_id WHERE i.order_id=? AND p.status!='published'",(oid,)).fetchone():
                self.fail(409,'订单商品已下架，不能付款。')
            lifecycle=Membership(self.store,self.h,self.Error,self.rate) if db.execute("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='membership'",(oid,)).fetchone() else None
            if lifecycle:lifecycle.validate_commerce_payment(db,oid)
            timestamp=now()
            db.execute('INSERT INTO commerce_payment_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid4()),self.uid,'sandbox',oid,request_id,'sandbox_pay',token,row['total_minor'],row['currency'],'[]','applied',timestamp))
            physical=db.execute("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='physical'",(oid,)).fetchone()
            db.execute("UPDATE commerce_orders SET status=?,payment_status='paid',fulfillment_status=?,updated=? WHERE id=?",('paid' if physical else 'completed','awaiting_fulfillment' if physical else 'fulfilled',timestamp,oid))
            db.execute("DELETE FROM commerce_carts WHERE owner=? AND environment='sandbox'",(self.uid,))
            if lifecycle:lifecycle.on_commerce_payment(db,oid)
            self.store.audit(db,self.uid,'commerce.sandbox.pay',oid,'仅沙箱权益，不授予正式媒体权限')
            return self.order(db,self.own_order(db,oid))

    def validate_variants(self, data, existing, kind):
        if 'variants' in data:
            raw = data['variants']
        else:
            if len(existing) > 1 or any(json.loads(row['options']) for row in existing.values()):
                self.fail(409, '请使用规格编辑器保存此商品。')
            raw = [{'skuId': next(iter(existing), None), 'sku': data.get('sku'), 'priceMinor': data.get('priceMinor'),
                    'stock': data.get('stock'), 'active': True, 'options': []}]
        if not isinstance(raw, list) or not 1 <= len(raw) <= 20 or (kind == 'membership' and len(raw) != 1):
            self.fail(400, '商品须保留1至20个SKU，会员商品只允许一个SKU。')
        result, seen_ids, seen_codes, seen_options = [], set(), set(), set()
        for value in raw:
            if not isinstance(value, dict) or type(value.get('active', True)) is not bool:
                self.fail(400, 'SKU格式错误。')
            sid = value.get('skuId')
            if sid is not None and (not isinstance(sid, str) or sid not in existing or sid in seen_ids):
                self.fail(400, '规格编号无效、重复或不属于当前商品。')
            sku = self.text(value.get('sku'), 100, 1)
            options = value.get('options', [])
            if not isinstance(options, list) or len(options) > 4 or any(not isinstance(o, dict) or set(o) != {'name', 'value'} for o in options):
                self.fail(400, '每个SKU最多可填写4组规格名称与取值。')
            options = [{'name': self.text(o['name'], 40, 1), 'value': self.text(o['value'], 80, 1)} for o in options]
            names = {o['name'].lower() for o in options}
            signature = tuple(sorted((o['name'].lower(), o['value'].lower()) for o in options))
            active = value.get('active', True)
            if (kind == 'membership' and options) or len(names) != len(options) or sku in seen_codes or (active and signature in seen_options):
                self.fail(400, 'SKU编码、规格名称或在售规格组合重复，会员商品无需规格。')
            if sid is not None:
                seen_ids.add(sid)
            seen_codes.add(sku)
            if active:
                seen_options.add(signature)
            result.append({'id': sid or str(uuid4()), 'sku': sku, 'price': self.integer(value.get('priceMinor')),
                           'stock': self.integer(value.get('stock')), 'options': options, 'active': active,
                           'expectedStock': self.integer(value['expectedStock']) if 'expectedStock' in value else None})
        if seen_ids != set(existing):
            self.fail(409, '已有SKU须保留，停用时请将其设为下架。')
        return result

    def save_product(self, data):
        environment=self.environment(data.get('environment','production'))
        title=self.text(data.get('title'),120,1); description=self.text(data.get('description',''),5000)
        kind=data.get('type'); status=data.get('status','draft')
        if kind not in ('digital','physical','membership') or status not in ('draft','published','archived'):
            self.fail(400,'无效商品类型或状态；预约尚未启用。')
        currency=self.text(data.get('currency'),3,3).upper()
        if currency not in SUPPORTED_CURRENCIES: self.fail(400,'该币种尚未列入沙箱支持范围。')
        shipping=self.integer(data.get('shippingMinor',0)); tax=self.integer(data.get('taxMinor',0))
        if kind!='physical' and shipping: self.fail(400,'非实物商品不能收取运费。')
        countries=data.get('shippingCountries',[])
        if not isinstance(countries,list) or len(countries)>250 or any(not isinstance(c,str) or not re.fullmatch('[A-Z]{2}',c) for c in countries): self.fail(400,'配送国家须为两位大写国家代码数组。')
        if kind=='physical' and status=='published' and not countries: self.fail(400,'上架实物须配置配送国家。')
        content=self.text(data.get('contentId',''),100)
        if kind=='digital' and status=='published' and not content: self.fail(400,'数字作品上架须绑定内容ID。')
        pid=self.text(data.get('id') or str(uuid4()),100,1); timestamp=now(); mutation=str(uuid4())
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if kind=='digital' and status=='published' and not db.execute("SELECT 1 FROM contents WHERE kind='courses' AND id=? AND status='published'",(content,)).fetchone(): self.fail(400,'数字作品须绑定已发布智慧馆内容。')
            old=db.execute('SELECT * FROM commerce_products WHERE id=?',(pid,)).fetchone()
            current = db.execute("SELECT s.*,coalesce(v.options,'[]') options FROM commerce_skus s LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id WHERE s.product_id=?", (pid,)).fetchall()
            existing = {row['id']: row for row in current}
            variants = self.validate_variants(data, existing, kind)
            if status == 'published' and not any(row['active'] for row in variants):
                self.fail(400, '上架商品须至少保留一个在售SKU。')
            extra=json.loads(old['data']) if old else {}
            old_image=extra.get('imageUrl','')
            for key in ('refundPolicy','titleZh','titleEn','titleHant','titleBo','descriptionZh','descriptionEn','descriptionHant','descriptionBo','imageUrl'):
                if key in data: extra[key]=self.text(data[key],5000 if key.startswith('description') else 2000 if key=='refundPolicy' else 1500 if key=='imageUrl' else 120)
            if extra.get('imageUrl'):
                image=extra['imageUrl']; parsed=urlsplit(image)
                if re.fullmatch('/api/media/[a-f0-9-]{36}',image):
                    asset=db.execute('SELECT mime,owner FROM media WHERE id=?',(image.rsplit('/',1)[1],)).fetchone()
                    if not asset or not asset['mime'].startswith('image/'): self.fail(400,'商品封面须为已上传图片。')
                    if image!=old_image and asset['owner']!=self.uid: self.fail(403,'新增商品封面只能引用当前管理员上传的图片。')
                elif parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password: self.fail(400,'商品封面须为HTTPS或本项目上传图片。')
            if old:
                if self.integer(data.get('version'),1)!=old['version']: self.fail(409,'商品已更新，请刷新。')
                if old['environment']!=environment or old['type']!=kind: self.fail(409,'已有商品不能更换交易环境或类型。')
                for variant in variants:
                    sr = existing.get(variant['id'])
                    if sr and variant['expectedStock'] is not None and variant['expectedStock'] != sr['stock']:
                        self.fail(409, '规格库存已变化，请刷新商品。')
                    if sr and variant['stock'] < sr['reserved']:
                        self.fail(409,'库存不能低于已预占数量。')
                    if sr and sr['reserved'] and (content != old['content_id'] or currency != sr['currency']):
                        self.fail(409,'存在预占订单时不能修改币种或内容绑定。')
                version=old['version']+1
                db.execute('UPDATE commerce_products SET title=?,description=?,status=?,version=?,content_id=?,shipping_countries=?,shipping_minor=?,tax_minor=?,mutation_id=?,updated=? WHERE id=?',(title,description,status,version,content,dump(sorted(set(countries))),shipping,tax,mutation,timestamp,pid))
            else:
                if data.get('version') not in (None,0): self.fail(409,'新商品不能使用已有版本。')
                version=1
                db.execute('INSERT INTO commerce_products(id,title,description,type,environment,status,version,content_id,shipping_countries,shipping_minor,tax_minor,mutation_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,title,description,kind,environment,status,version,content,dump(sorted(set(countries))),shipping,tax,mutation,timestamp,timestamp))
            db.execute('UPDATE commerce_products SET data=? WHERE id=?',(dump(extra),pid))
            # Move changed codes out of the way first so codes can be swapped in one save.
            for v in variants:
                if v['id'] in existing and existing[v['id']]['sku'] != v['sku']:
                    db.execute('UPDATE commerce_skus SET sku=? WHERE id=?', ('swap:'+str(uuid4()), v['id']))
            for v in variants:
                sid, sku, price, stock = (v[k] for k in ('id', 'sku', 'price', 'stock'))
                db.execute('INSERT INTO commerce_skus VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET sku=excluded.sku,price_minor=excluded.price_minor,currency=excluded.currency,stock=excluded.stock,version=excluded.version',
                           (sid,pid,sku,environment,price,currency,stock,0,version))
                db.execute('INSERT INTO commerce_sku_variants VALUES(?,?,?) ON CONFLICT(sku_id) DO UPDATE SET options=excluded.options,active=excluded.active',
                           (sid,dump(v['options']),int(v['active'])))
                db.execute('INSERT INTO commerce_prices VALUES(?,?,?,?,?,?)',(str(uuid4()),sid,version,price,currency,timestamp))
            self.store.audit(db,self.uid,'commerce.product.save',pid,environment+'；版本'+str(version))
            return {'item':next(p for p in self.products(db,environment) if p['id']==pid),'environment':environment,'productionEnabled':False}

    def refund(self, oid, data):
        request_id=self.text(data.get('requestId'),128,1)
        values=data.get('items')
        if not isinstance(values,list) or not 1<=len(values)<=30: self.fail(400,'请指定退款订单项及数量。')
        items=[]
        for item in values:
            if not isinstance(item,dict): self.fail(400,'退款项目格式错误。')
            items.append({'itemId':self.text(item.get('itemId'),100,1),'quantity':self.integer(item.get('quantity'),1,99)})
        items.sort(key=lambda i:i['itemId'])
        if len({i['itemId'] for i in items})!=len(items): self.fail(400,'退款项目不可重复。')
        token=fingerprint({'orderId':oid,'items':items})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); self.enabled(db,'sandbox')
            row=self.own_order(db,oid,True)
            old=db.execute("SELECT * FROM commerce_payment_events WHERE owner=? AND environment='sandbox' AND kind='refund' AND request_id=?",(row['owner'],request_id)).fetchone()
            if old:
                if old['fingerprint']!=token: self.fail(409,'退款幂等编号已用于不同请求。')
                return self.order(db,row)
            if row['payment_status'] not in ('paid','partially_refunded'): self.fail(409,'订单当前不能退款。')
            amount=0
            for item in items:
                line=db.execute('SELECT * FROM commerce_order_items WHERE id=? AND order_id=?',(item['itemId'],oid)).fetchone()
                if not line or item['quantity']>line['quantity']-line['refunded_quantity']: self.fail(409,'退款数量超过该订单项可退数量。')
                amount+=item['quantity']*(line['price_minor']+line['unit_shipping_minor']+line['unit_tax_minor'])
            db.execute('INSERT INTO commerce_payment_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(str(uuid4()),row['owner'],'sandbox',oid,request_id,'refund',token,amount,row['currency'],dump(items),'applied',now()))
            if db.execute("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='membership'",(oid,)).fetchone():Membership(self.store,self.h,self.Error,self.rate).on_commerce_refund(db,oid)
            self.store.audit(db,self.uid,'commerce.sandbox.refund',oid,'按项退款；无真实资金流动')
            return self.order(db,self.own_order(db,oid,True))

    def aftersale(self, oid, data):
        request_id=self.text(data.get('requestId'),128,1); reason=self.text(data.get('reason'),2000,1); quantity=self.integer(data.get('quantity',1),1,2970)
        token=fingerprint({'orderId':oid,'reason':reason,'quantity':quantity})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); self.enabled(db,'sandbox'); row=self.own_order(db,oid)
            old=db.execute("SELECT * FROM commerce_aftersale_requests WHERE owner=? AND environment='sandbox' AND request_id=?",(self.uid,request_id)).fetchone()
            if old:
                if old['fingerprint']!=token: self.fail(409,'售后幂等编号已用于不同请求。')
                return self.order(db,row)
            # after-sales-legacy-guard:v1; inside the existing BEGIN IMMEDIATE, after historical replay.
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='after_sales_cases'").fetchone() and db.execute("SELECT 1 FROM after_sales_cases WHERE owner=? AND order_id=? AND state!='rejected' LIMIT 1",(self.uid,oid)).fetchone():
                self.fail(409,'本单已有按项售后申请，请到该申请继续处理。')
            remaining=db.execute('SELECT coalesce(sum(quantity-refunded_quantity),0) FROM commerce_order_items WHERE order_id=?',(oid,)).fetchone()[0]
            if row['payment_status'] not in ('paid','partially_refunded') or quantity>remaining: self.fail(409,'订单状态或可售后数量不符合要求。')
            timestamp=now()
            db.execute('INSERT INTO commerce_aftersale_requests VALUES(?,?,?,?,?,?,?,?,?,?,?)',(str(uuid4()),self.uid,'sandbox',oid,request_id,token,reason,quantity,'pending',timestamp,timestamp))
            db.execute("UPDATE commerce_orders SET aftersale_status='requested',updated=? WHERE id=?",(timestamp,oid))
            self.store.audit(db,self.uid,'commerce.aftersale.request',oid,'sandbox；等待人工处理，不自动退款')
            return self.order(db,self.own_order(db,oid))

    def admin(self, method, path):
        self.h.require(['admin'])
        detail=re.fullmatch('/api/admin/commerce/orders/([^/]+)',path)
        if detail and method=='GET':
            with self.store.connect() as db:
                return self.order(db,self.own_order(db,detail.group(1),True))
        if path=='/api/admin/commerce' and method=='GET':
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE'); self.expire(db)
                return {'settings':self.settings(db),'products':self.products(db),'orders':[self.order(db,r) for r in db.execute('SELECT * FROM commerce_orders ORDER BY created DESC LIMIT 200').fetchall()],'environment':'sandbox','productionEnabled':False}
        if path=='/api/admin/commerce/settings' and method=='PATCH':
            data=self.h.body()
            if data.get('productionEnabled') not in (None,False) or not isinstance(data.get('sandboxEnabled'),bool): self.fail(400,'正式交易禁止启用，sandboxEnabled须为布尔值。')
            settings={'sandboxEnabled':data['sandboxEnabled'],'productionEnabled':False}
            with self.store.connect() as db:
                db.execute("UPDATE commerce_config SET data=? WHERE key='settings'",(dump(settings),)); self.store.audit(db,self.uid,'commerce.settings','sandbox','沙箱开关变更')
            return {'settings':settings}
        if path=='/api/admin/commerce/products' and method=='POST': return self.save_product(self.h.body())
        match=re.fullmatch('/api/admin/commerce/orders/([^/]+)/(fulfill|refund)',path)
        if match and method=='POST':
            data=self.h.body(); oid,action=match.groups()
            if action=='refund': return self.refund(oid,data)
            tracking={'trackingNumber':self.text(data.get('trackingNumber'),100,1),'carrier':self.text(data.get('carrier',''),100)}
            state=data.get('status','shipped')
            if state not in ('shipped','delivered'): self.fail(400,'无效履约状态。')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE'); self.enabled(db,'sandbox'); row=self.own_order(db,oid,True)
                if row['payment_status'] not in ('paid','partially_refunded') or not db.execute("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='physical' AND quantity>refunded_quantity",(oid,)).fetchone(): self.fail(409,'仅已付款且尚有未退实物的订单可发货。')
                if row['fulfillment_status']=='delivered' and state!='delivered': self.fail(409,'已送达订单不能倒退履约状态。')
                db.execute('UPDATE commerce_orders SET tracking=?,fulfillment_status=?,status=?,updated=? WHERE id=?',(dump(tracking),state,'completed' if state=='delivered' else 'fulfilling',now(),oid))
                self.store.audit(db,self.uid,'commerce.fulfill',oid,'sandbox；'+state)
                return self.order(db,self.own_order(db,oid,True))
        self.fail(405,'不支持的交易后台操作。')

    def route(self, method, path):
        if not (path.startswith('/api/commerce/') or path=='/api/admin/commerce' or path.startswith('/api/admin/commerce/')):
            return None
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); self.expire(db)
        if path.startswith('/api/admin/'): return self.admin(method,path)
        query=parse_qs(urlsplit(self.h.path).query)
        environment=self.environment(query.get('environment',['production'])[0])
        if path=='/api/commerce/catalog' and method=='GET':
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE'); self.expire(db); settings=self.settings(db)
                items=self.products(db,environment,True) if environment=='production' or settings['sandboxEnabled'] else []
                for item in items: item['purchasable']=item['purchasable'] and settings['sandboxEnabled']
                return {'items':items,'settings':settings,'environment':environment,'sandboxOnly':environment=='sandbox','productionEnabled':False}
        self.h.require()
        if method in ('POST','PATCH'): self.rate('commerce:'+self.uid,30)
        if path=='/api/commerce/cart' and method in ('GET','PATCH'):
            data=self.h.body() if method=='PATCH' else {}
            environment=self.environment(data.get('environment',environment))
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE'); self.expire(db)
                if method=='PATCH':
                    self.enabled(db,environment)
                    requested=[] if data.get('items')==[] else self.items(data.get('items'))
                    old=db.execute('SELECT data FROM commerce_carts WHERE owner=? AND environment=?',(self.uid,environment)).fetchone()
                    old_quantities={item['skuId']:item['quantity'] for item in json.loads(old['data'])} if old else {}
                    for item in requested:
                        if item['quantity'] <= old_quantities.get(item['skuId'], 0):
                            continue
                        sku=db.execute(f"SELECT s.stock-s.reserved available FROM commerce_products p {SKU_JOIN} WHERE s.id=? AND s.environment=? AND p.environment=? AND p.status='published' AND coalesce(v.active,1)=1",(item['skuId'],environment,environment)).fetchone()
                        if not sku or sku['available'] < item['quantity']: self.fail(409,'购物车规格已下架或库存不足。')
                    db.execute('INSERT INTO commerce_carts VALUES(?,?,?,?) ON CONFLICT(owner,environment) DO UPDATE SET data=excluded.data,updated=excluded.updated',(self.uid,environment,dump(requested),now()))
                row=db.execute('SELECT data FROM commerce_carts WHERE owner=? AND environment=?',(self.uid,environment)).fetchone()
                return {'items':json.loads(row['data']) if row else [],'environment':environment,'settings':self.settings(db)}
        if path=='/api/commerce/orders' and method=='POST': return self.create_order(self.h.body())
        if path=='/api/commerce/orders' and method=='GET':
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE'); self.expire(db)
                return {'items':[self.order(db,r) for r in db.execute('SELECT * FROM commerce_orders WHERE owner=? AND environment=? ORDER BY created DESC LIMIT 200',(self.uid,environment)).fetchall()],'environment':environment}
        if path=='/api/commerce/entitlements' and method=='GET':
            with self.store.connect() as db:
                rows=db.execute('SELECT * FROM commerce_entitlements WHERE owner=? AND environment=? ORDER BY created DESC',(self.uid,environment)).fetchall()
                return {'items':[{'id':r['id'],'environment':'sandbox','sandboxOnly':True,'grantsProductionAccess':False,'orderId':r['order_id'],'itemId':r['item_id'],'contentId':r['content_id'],'type':r['type'],'quantity':r['quantity'],'remaining':r['remaining'],'status':r['status']} for r in rows],'environment':environment,'grantsProductionAccess':False}
        match=re.fullmatch('/api/commerce/orders/([^/]+)(/(?:sandbox-pay|aftersale))?',path)
        if match:
            oid,pay=match.groups()
            if pay=='/aftersale' and method=='POST': return self.aftersale(oid,self.h.body())
            if pay and method=='POST': return self.pay(oid,self.h.body())
            if not pay and method=='GET':
                with self.store.connect() as db:
                    db.execute('BEGIN IMMEDIATE'); self.expire(db)
                    return self.order(db,self.own_order(db,oid))
        self.fail(405,'不支持的交易操作。')
