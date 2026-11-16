"""CM01-CM06 sandbox accounting. No production commission or transfer capability."""
import csv
import io
import json
import re
import time
from uuid import uuid4

MAX_MINOR = 1_000_000_000
DDL = r'''
CREATE TABLE IF NOT EXISTS commission_config(key TEXT PRIMARY KEY,data TEXT NOT NULL);
INSERT OR IGNORE INTO commission_config VALUES('settings','{"sandboxEnabled":false,"productionEnabled":false,"actualPaymentsEnabled":false,"stackingPolicy":"exclusive_promotion","attributionStrategy":"last_touch"}');
CREATE TABLE IF NOT EXISTS commission_grants(user_id TEXT PRIMARY KEY,permission TEXT NOT NULL CHECK(permission IN ('business','finance','support')),updated INTEGER NOT NULL,actor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commission_rules(rule_id TEXT NOT NULL,version INTEGER NOT NULL,product_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('promotion','author')),effective INTEGER NOT NULL,created INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(rule_id,version));
CREATE TABLE IF NOT EXISTS commission_invites(code TEXT PRIMARY KEY,beneficiary TEXT NOT NULL,valid_until INTEGER NOT NULL,priority INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','revoked')),created INTEGER NOT NULL,data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commission_attributions(id TEXT PRIMARY KEY,owner TEXT NOT NULL,code TEXT NOT NULL,beneficiary TEXT NOT NULL,priority INTEGER NOT NULL,created INTEGER NOT NULL,valid_until INTEGER NOT NULL,request_id TEXT NOT NULL,data TEXT NOT NULL,UNIQUE(owner,request_id));
CREATE TABLE IF NOT EXISTS commission_snapshots(item_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS commission_facts(item_id TEXT PRIMARY KEY,data TEXT NOT NULL,updated INTEGER NOT NULL,actor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commission_ledger(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,item_id TEXT NOT NULL,beneficiary TEXT NOT NULL,rule_id TEXT NOT NULL,rule_version INTEGER NOT NULL,currency TEXT NOT NULL,quantity INTEGER NOT NULL,refunded_quantity INTEGER NOT NULL DEFAULT 0,base_minor INTEGER,amount_minor INTEGER,net_minor INTEGER,status TEXT NOT NULL CHECK(status IN ('waiting_facts','pending_confirmation','frozen','payable','statement_pending','settled_bookkeeping','revoked')),freeze_until INTEGER NOT NULL,payment_event TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(item_id,rule_id,rule_version,beneficiary));
CREATE TABLE IF NOT EXISTS commission_adjustments(id TEXT PRIMARY KEY,ledger_id TEXT NOT NULL,beneficiary TEXT NOT NULL,currency TEXT NOT NULL,refunded_quantity INTEGER NOT NULL,amount_minor INTEGER NOT NULL CHECK(amount_minor>=0),target_minor INTEGER NOT NULL CHECK(target_minor>=0),status TEXT NOT NULL CHECK(status IN ('applied','pending_recovery','reserved','offset_booked')),reason TEXT NOT NULL,source_event TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(ledger_id,refunded_quantity));
CREATE TABLE IF NOT EXISTS commission_statements(id TEXT PRIMARY KEY,beneficiary TEXT NOT NULL,currency TEXT NOT NULL,total_minor INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('awaiting_approval','approved','booked','cancelled')),version INTEGER NOT NULL,creator TEXT NOT NULL,approver TEXT NOT NULL,period_from INTEGER NOT NULL,period_to INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS commission_statement_lines(statement_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('earning','recovery')),source_id TEXT NOT NULL,amount_minor INTEGER NOT NULL,PRIMARY KEY(statement_id,kind,source_id));
CREATE TABLE IF NOT EXISTS commission_payments(id TEXT PRIMARY KEY,statement_id TEXT NOT NULL UNIQUE,request_id TEXT NOT NULL UNIQUE,data TEXT NOT NULL,status TEXT NOT NULL CHECK(status='sandbox_registered'),created INTEGER NOT NULL,actor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commission_events(id TEXT PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TRIGGER IF NOT EXISTS commission_rule_append BEFORE INSERT ON commission_rules BEGIN
 SELECT CASE WHEN NEW.version!=(SELECT coalesce(max(version),0)+1 FROM commission_rules WHERE rule_id=NEW.rule_id) OR EXISTS(SELECT 1 FROM commission_rules WHERE product_id=NEW.product_id AND kind=NEW.kind AND rule_id!=NEW.rule_id) OR EXISTS(SELECT 1 FROM commission_rules WHERE rule_id=NEW.rule_id AND (product_id!=NEW.product_id OR kind!=NEW.kind)) THEN RAISE(ABORT,'commission_rule_version') END;
END;
CREATE TRIGGER IF NOT EXISTS commission_rule_immutable BEFORE UPDATE ON commission_rules BEGIN SELECT RAISE(ABORT,'commission_rule_immutable'); END;
CREATE TRIGGER IF NOT EXISTS commission_rule_no_delete BEFORE DELETE ON commission_rules BEGIN SELECT RAISE(ABORT,'commission_rule_immutable'); END;
CREATE TRIGGER IF NOT EXISTS commission_snapshot_immutable BEFORE UPDATE ON commission_snapshots BEGIN SELECT RAISE(ABORT,'commission_snapshot_immutable'); END;
CREATE TRIGGER IF NOT EXISTS commission_facts_guard BEFORE UPDATE ON commission_facts WHEN EXISTS(SELECT 1 FROM commission_ledger WHERE item_id=OLD.item_id AND status!='waiting_facts') BEGIN SELECT RAISE(ABORT,'commission_facts_locked'); END;
CREATE TRIGGER IF NOT EXISTS commission_adjust_guard BEFORE INSERT ON commission_adjustments BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commission_ledger l JOIN commerce_order_items i ON i.id=l.item_id JOIN commerce_payment_events e ON e.id=NEW.source_event AND e.order_id=l.order_id AND e.kind='refund' AND e.status='applied' WHERE l.id=NEW.ledger_id AND l.beneficiary=NEW.beneficiary AND l.currency=NEW.currency AND i.refunded_quantity=NEW.refunded_quantity AND l.refunded_quantity<NEW.refunded_quantity AND NEW.target_minor<=l.net_minor AND NEW.amount_minor=l.net_minor-NEW.target_minor) THEN RAISE(ABORT,'commission_refund_stale') END;
END;
CREATE TRIGGER IF NOT EXISTS commission_adjust_apply AFTER INSERT ON commission_adjustments BEGIN
 UPDATE commission_ledger SET refunded_quantity=NEW.refunded_quantity,net_minor=NEW.target_minor,status=CASE WHEN status='settled_bookkeeping' THEN status WHEN NEW.target_minor=0 THEN 'revoked' ELSE status END,updated=NEW.created WHERE id=NEW.ledger_id;
END;
CREATE TRIGGER IF NOT EXISTS commission_statement_reserve AFTER INSERT ON commission_statement_lines WHEN NEW.kind='earning' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commission_ledger l JOIN commission_statements s ON s.id=NEW.statement_id WHERE l.id=NEW.source_id AND l.status='payable' AND l.beneficiary=s.beneficiary AND l.currency=s.currency AND l.net_minor=NEW.amount_minor) THEN RAISE(ABORT,'commission_statement_stale') END;
 UPDATE commission_ledger SET status='statement_pending' WHERE id=NEW.source_id;
END;
CREATE TRIGGER IF NOT EXISTS commission_recovery_reserve AFTER INSERT ON commission_statement_lines WHEN NEW.kind='recovery' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commission_adjustments a JOIN commission_statements s ON s.id=NEW.statement_id WHERE a.id=NEW.source_id AND a.status='pending_recovery' AND a.beneficiary=s.beneficiary AND a.currency=s.currency AND a.amount_minor=-NEW.amount_minor) THEN RAISE(ABORT,'commission_recovery_stale') END;
 UPDATE commission_adjustments SET status='reserved' WHERE id=NEW.source_id;
END;
CREATE TRIGGER IF NOT EXISTS commission_statement_close AFTER UPDATE OF status ON commission_statements WHEN NEW.status IN ('booked','cancelled') AND OLD.status!=NEW.status BEGIN
 UPDATE commission_ledger SET status=CASE WHEN NEW.status='booked' THEN 'settled_bookkeeping' WHEN net_minor=0 THEN 'revoked' ELSE 'payable' END WHERE id IN (SELECT source_id FROM commission_statement_lines WHERE statement_id=NEW.id AND kind='earning');
 UPDATE commission_adjustments SET status=CASE WHEN NEW.status='booked' THEN 'offset_booked' ELSE 'pending_recovery' END WHERE id IN (SELECT source_id FROM commission_statement_lines WHERE statement_id=NEW.id AND kind='recovery');
END;
'''

# Executed after commerce_order_items in the SAME order-creation transaction/batch.
# All reads happen within SQL; callers cannot supply a beneficiary or rule snapshot.
SNAPSHOT_SQL = r'''
INSERT OR IGNORE INTO commission_snapshots(item_id,order_id,data,created)
SELECT i.id,o.id,json_object('enabled',json(CASE WHEN json_extract(c.data,'$.sandboxEnabled')=1 THEN 'true' ELSE 'false' END),'config',json(c.data),'rules',json(COALESCE((SELECT json_group_array(json(r.data)) FROM commission_rules r WHERE r.product_id=i.product_id AND r.created<=o.created AND r.effective<=o.created AND r.version=(SELECT max(v.version) FROM commission_rules v WHERE v.rule_id=r.rule_id AND v.created<=o.created AND v.effective<=o.created)),'[]')),'attribution',json(COALESCE((SELECT t.data FROM commission_attributions t JOIN commission_invites n ON n.code=t.code JOIN commission_config ac ON ac.key='settings' WHERE t.owner=o.owner AND t.created<=o.created AND t.valid_until>o.created AND n.status='active' AND n.valid_until>o.created ORDER BY t.priority DESC,CASE WHEN json_extract(ac.data,'$.attributionStrategy')='first_touch' THEN t.created END ASC,CASE WHEN json_extract(ac.data,'$.attributionStrategy')='last_touch' THEN t.created END DESC,t.id LIMIT 1),'null'))),o.created
FROM commerce_order_items i JOIN commerce_orders o ON o.id=i.order_id JOIN commission_config c ON c.key='settings' WHERE o.environment='sandbox' AND o.id=?
'''


def init_schema(db):
    db.executescript(DDL)


def now():
    return time.time_ns() // 1_000_000


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def snapshot_order(db, order_id):
    """Caller owns transaction. Missing hook must never be repaired at payment time."""
    db.execute(SNAPSHOT_SQL, (order_id,))


def rounded(numerator, denominator, rounding):
    if type(numerator) is not int or type(denominator) is not int or numerator < 0 or denominator < 1 or rounding not in ('floor', 'half_up'):
        raise ValueError('invalid integer rounding')
    result = (numerator + (denominator // 2 if rounding == 'half_up' else 0)) // denominator
    if result > 9_007_199_254_740_991:
        raise ValueError('unsafe output integer')
    return result


def calculate(rule, item, facts):
    """Gross already includes item tax/shipping. Unknown costs remain unknown."""
    quantity = item['quantity']
    gross = quantity * (item['price_minor'] + item['unit_tax_minor'] + item['unit_shipping_minor'])
    base = gross
    values = {'tax': quantity * item['unit_tax_minor'], 'shipping': quantity * item['unit_shipping_minor'], 'discount': facts.get('discountMinor'), 'channelFee': facts.get('channelFeeMinor')}
    for key, field in [('tax', 'deductTax'), ('shipping', 'deductShipping'), ('discount', 'deductDiscount'), ('channelFee', 'deductChannelFee')]:
        if rule['basis'][field]:
            if values[key] is None:
                return {'base': None, 'amount': None, 'reason': 'missing_' + key}
            base -= values[key]
    if base < 0:
        return {'base': None, 'amount': None, 'reason': 'negative_basis'}
    amount = rounded(base * rule['rateBps'], 10000, rule['rounding']) if rule['mode'] == 'rate' else rule['fixedMinor'] * quantity
    if rule.get('capMinor') is not None:
        amount = min(amount, rule['capMinor'])
    if amount > gross or amount > MAX_MINOR:
        return {'base': None, 'amount': None, 'reason': 'commission_exceeds_paid'}
    return {'base': base, 'amount': amount, 'reason': ''}


def event(db, actor, action, target, value=None):
    db.execute('INSERT INTO commission_events VALUES(?,?,?,?,?,?)', (str(uuid4()), actor, action, target, dump(value or {}), now()))


def sync_commission_order(db, order_id):
    """Only applied commerce events count; this helper never creates orders/payments."""
    order = db.execute("SELECT * FROM commerce_orders WHERE id=? AND environment='sandbox'", (order_id,)).fetchone()
    if not order:
        return {'synced': False, 'reason': 'order_not_found'}
    items = db.execute('SELECT * FROM commerce_order_items WHERE order_id=? ORDER BY id', (order_id,)).fetchall()
    snapshots = {r['item_id']: json.loads(r['data']) for r in db.execute('SELECT * FROM commission_snapshots WHERE order_id=?', (order_id,)).fetchall()}
    if len(snapshots) != len(items):
        return {'synced': False, 'reason': 'missing_creation_snapshot'}
    paid = db.execute("SELECT * FROM commerce_payment_events WHERE order_id=? AND kind='sandbox_pay' AND status='applied' ORDER BY created,id LIMIT 1", (order_id,)).fetchone()
    if not paid or order['payment_status'] not in ('paid', 'partially_refunded', 'refunded'):
        return {'synced': True, 'reason': 'not_paid', 'created': 0}
    stamp, made = now(), 0
    for item in items:
        snap = snapshots[item['id']]
        if not snap.get('enabled'):
            continue
        selected = []
        for rule in snap['rules']:
            if rule['status'] != 'active' or rule['currency'] != item['currency']:
                continue
            beneficiary = rule['beneficiary'] if rule['kind'] == 'author' else (snap.get('attribution') or {}).get('beneficiary')
            if beneficiary and beneficiary != order['owner']:
                selected.append((rule, beneficiary))
        policy = snap['config']['stackingPolicy']
        if policy != 'allow_both' and len({r['kind'] for r, _ in selected}) > 1:
            selected = [(r, b) for r, b in selected if r['kind'] == ('author' if policy == 'exclusive_author' else 'promotion')]
        # One current rule of each kind per product is enforced at rule creation.
        fact = db.execute('SELECT data FROM commission_facts WHERE item_id=?', (item['id'],)).fetchone()
        facts = json.loads(fact['data']) if fact else {'discountMinor': 0, 'channelFeeMinor': None, 'source': 'unified_commerce_no_discount_feature'}
        calculations = [(r, b, calculate(r, item, facts)) for r, b in selected]
        missing = next((c['reason'] for _, _, c in calculations if c['amount'] is None), '')
        if missing:
            calculations = [(r, b, {'base': None, 'amount': None, 'reason': missing}) for r, b, _ in calculations]
        known_total = sum(c['amount'] or 0 for _, _, c in calculations)
        gross = item['quantity'] * (item['price_minor'] + item['unit_tax_minor'] + item['unit_shipping_minor'])
        for rule, beneficiary, calc in calculations:
            if known_total > gross:
                calc = {'base': None, 'amount': None, 'reason': 'combined_commission_exceeds_paid'}
            lid = item['id'] + ':' + rule['ruleId'] + ':' + str(rule['version']) + ':' + beneficiary
            row = db.execute('SELECT * FROM commission_ledger WHERE id=?', (lid,)).fetchone()
            details = {'rule': rule, 'facts': facts, 'orderItem': {'priceMinor': item['price_minor'], 'unitTaxMinor': item['unit_tax_minor'], 'unitShippingMinor': item['unit_shipping_minor'], 'quantity': item['quantity'], 'currency': item['currency']}, 'attribution': snap.get('attribution') if rule['kind'] == 'promotion' else None, 'productId': item['product_id'], 'contentId': item['content_id'], 'reason': calc['reason'], 'sandboxOnly': True, 'actualPaid': False}
            if not row:
                status = 'waiting_facts' if calc['amount'] is None else 'pending_confirmation'
                db.execute('INSERT INTO commission_ledger VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (lid, order_id, item['id'], beneficiary, rule['ruleId'], rule['version'], item['currency'], item['quantity'], 0, calc['base'], calc['amount'], calc['amount'], status, paid['created'] + rule['freezeDays'] * 86400000, paid['id'], dump(details), stamp, stamp))
                made += 1
            elif row['status'] == 'waiting_facts' and calc['amount'] is not None:
                db.execute("UPDATE commission_ledger SET base_minor=?,amount_minor=?,net_minor=?,status='pending_confirmation',data=?,updated=? WHERE id=? AND status='waiting_facts'", (calc['base'], calc['amount'], calc['amount'], dump(details), stamp, lid))
            row = db.execute('SELECT * FROM commission_ledger WHERE id=?', (lid,)).fetchone()
            if row['amount_minor'] is None or item['refunded_quantity'] <= row['refunded_quantity']:
                continue
            refund_event = db.execute("SELECT id FROM commerce_payment_events WHERE order_id=? AND kind='refund' AND status='applied' AND EXISTS(SELECT 1 FROM json_each(items) WHERE json_extract(value,'$.itemId')=?) ORDER BY created DESC,id DESC LIMIT 1", (order_id, item['id'])).fetchone()
            if not refund_event:
                continue
            # Refund cannot leave an outstanding settlement based on stale amounts.
            open_statements = db.execute("SELECT s.id FROM commission_statements s JOIN commission_statement_lines x ON x.statement_id=s.id WHERE x.kind='earning' AND x.source_id=? AND s.status IN ('awaiting_approval','approved')", (lid,)).fetchall()
            for statement in open_statements:
                db.execute("UPDATE commission_statements SET status='cancelled',version=version+1,updated=? WHERE id=?", (stamp, statement['id']))
            row = db.execute('SELECT * FROM commission_ledger WHERE id=?', (lid,)).fetchone()
            target = rounded(row['amount_minor'] * (item['quantity'] - item['refunded_quantity']), item['quantity'], rule['rounding'])
            status = 'pending_recovery' if row['status'] == 'settled_bookkeeping' else 'applied'
            db.execute('INSERT OR IGNORE INTO commission_adjustments VALUES(?,?,?,?,?,?,?,?,?,?,?)', ('refund:' + lid + ':' + str(item['refunded_quantity']), lid, beneficiary, item['currency'], item['refunded_quantity'], row['net_minor'] - target, target, status, 'sandbox_refund_quantity_proportional', refund_event['id'], stamp))
    return {'synced': True, 'created': made, 'actualPaid': False}


class Commission:
    def __init__(self, store, handler, error, limiter):
        self.store, self.h, self.Error, self.rate = store, handler, error, limiter

    def fail(self, status, message):
        raise self.Error(status, message)

    def text(self, v, maximum=120, minimum=1):
        if not isinstance(v, str) or not minimum <= len(v.strip()) <= maximum:
            self.fail(400, '文本字段格式或长度错误。')
        return v.strip()

    def integer(self, v, minimum=0, maximum=MAX_MINOR):
        if type(v) is not int or not minimum <= v <= maximum:
            self.fail(400, '请使用允许范围内的整数最小币种单位。')
        return v

    def who(self, db, needed=None):
        actor = self.h.require()
        grant = db.execute('SELECT permission FROM commission_grants WHERE user_id=?', (actor['id'],)).fetchone()
        permission = 'admin' if actor['role'] == 'admin' else grant['permission'] if grant and actor['role'] in ('operator', 'reviewer') else 'self'
        if needed is not None and permission != 'admin' and permission not in needed:
            self.fail(403, '当前账号未获此分佣操作权限。')
        return actor, permission

    def settings(self, db):
        return {**json.loads(db.execute("SELECT data FROM commission_config WHERE key='settings'").fetchone()['data']), 'productionEnabled': False, 'actualPaymentsEnabled': False}

    def enabled(self, db):
        if not self.settings(db)['sandboxEnabled']:
            self.fail(503, '分佣沙箱尚未开启；生产计佣和真实打款始终关闭。')

    def ledger(self, r, permission='self'):
        d = json.loads(r['data'])
        result = {'id': r['id'], 'orderId': r['order_id'], 'itemId': r['item_id'], 'beneficiary': r['beneficiary'], 'productId': d['productId'], 'contentId': d['contentId'], 'kind': d['rule']['kind'], 'ruleId': r['rule_id'], 'ruleVersion': r['rule_version'], 'currency': r['currency'], 'status': r['status'], 'reason': d['reason'], 'freezeUntil': r['freeze_until'], 'quantity': r['quantity'], 'refundedQuantity': r['refunded_quantity'], 'createdAt': r['created'], 'sandboxOnly': True, 'actualPaid': False}
        if permission != 'support':
            result.update(baseMinor=r['base_minor'], amountMinor=r['amount_minor'], netMinor=r['net_minor'], paymentEvent=r['payment_event'], orderItem=d.get('orderItem'), rule=d['rule'], facts=d['facts'])
        return result

    def report(self, db, permission, actor, filters=None):
        filters = filters or {}
        rows = db.execute('SELECT * FROM commission_ledger ORDER BY created DESC,id').fetchall()
        items = [self.ledger(r, permission) for r in rows if permission != 'self' or r['beneficiary'] == actor['id']]
        for k in ('beneficiary', 'productId', 'contentId', 'kind', 'currency'):
            if filters.get(k):
                items = [r for r in items if r[k] == filters[k]]
        for k, op in [('from', lambda v, bound: v >= bound), ('to', lambda v, bound: v <= bound)]:
            if filters.get(k) not in (None, ''):
                if not re.fullmatch('[0-9]{1,16}', str(filters[k])):
                    self.fail(400, '时间筛选须为非负整数毫秒。')
                bound = self.integer(int(filters[k]), 0, 9_007_199_254_740_991)
                items = [r for r in items if op(r['createdAt'], bound)]
        visible_ledgers = {r['id'] for r in items}
        owner = actor['id'] if permission == 'self' else None
        adjustments = [dict(r) for r in db.execute('SELECT * FROM commission_adjustments ORDER BY created,id') if (owner is None or r['beneficiary'] == owner) and r['ledger_id'] in visible_ledgers]
        statements = [dict(r) for r in db.execute('SELECT * FROM commission_statements ORDER BY created DESC,id') if (owner is None or r['beneficiary'] == owner) and (not filters.get('beneficiary') or r['beneficiary'] == filters['beneficiary'])]
        for statement in statements:
            statement['lines'] = [dict(r) for r in db.execute('SELECT kind,source_id,amount_minor FROM commission_statement_lines WHERE statement_id=? ORDER BY kind,source_id', (statement['id'],))]
        if filters:
            visible_adjustments = {r['id'] for r in adjustments}
            statements = [s for s in statements if any(line['source_id'] in (visible_ledgers if line['kind'] == 'earning' else visible_adjustments) for line in s['lines'])]
        visible_statements = {s['id'] for s in statements}
        payments = [{**json.loads(r['data']), 'id': r['id'], 'statementId': r['statement_id'], 'status': r['status'], 'createdAt': r['created']} for r in db.execute('SELECT * FROM commission_payments ORDER BY created,id') if not filters or r['statement_id'] in visible_statements] if permission in ('admin', 'finance') else []
        if permission == 'support':
            adjustments = [{'id': r['id'], 'ledgerId': r['ledger_id'], 'status': r['status'], 'reason': r['reason']} for r in adjustments]
            statements = [{'id': r['id'], 'status': r['status']} for r in statements]
        return {'items': items, 'adjustments': adjustments, 'statements': statements, 'statementScope': 'whole_statement', 'payments': payments, 'permission': permission, 'settings': self.settings(db), 'sandboxOnly': True, 'actualPaid': False, 'productionEnabled': False}

    def save_rule(self, db, data, actor):
        rule_id = self.text(data.get('ruleId', str(uuid4())))
        old = db.execute('SELECT * FROM commission_rules WHERE rule_id=? ORDER BY version DESC LIMIT 1', (rule_id,)).fetchone()
        expected = self.integer(data.get('expectedVersion', 0))
        if expected != (old['version'] if old else 0):
            self.fail(409, '规则版本已变化，请刷新。')
        pid = self.text(data.get('productId'))
        product = db.execute("SELECT * FROM commerce_products WHERE id=? AND environment='sandbox'", (pid,)).fetchone()
        if not product:
            self.fail(400, '请选择已有沙箱商品。')
        kind, mode, rounding = data.get('kind'), data.get('mode'), data.get('rounding')
        if kind not in ('promotion', 'author') or mode not in ('rate', 'fixed_per_unit') or rounding not in ('floor', 'half_up') or data.get('status') not in ('active', 'inactive'):
            self.fail(400, '请明确规则类型、计算方式、取舍及状态。')
        if old and (old['product_id'] != pid or old['kind'] != kind):
            self.fail(409, '规则主体不可更换；请新增规则。')
        other = db.execute('SELECT 1 FROM commission_rules WHERE product_id=? AND kind=? AND rule_id!=?', (pid, kind, rule_id)).fetchone()
        if other:
            self.fail(409, '同商品同类规则请追加原规则版本，避免重复计佣。')
        currency = self.text(data.get('currency'), 3, 3).upper()
        if not db.execute('SELECT 1 FROM commerce_skus WHERE product_id=? AND currency=?', (pid, currency)).fetchone():
            self.fail(400, '规则币种须与商品一致，当前不支持换汇。')
        beneficiary = self.text(data.get('beneficiary', ''), 120, 0)
        if kind == 'promotion' and beneficiary:
            self.fail(400, '推广受益人只能由服务端邀请码归属解析。')
        if kind == 'author' and not db.execute("SELECT 1 FROM users WHERE id=? AND role IN ('teacher','admin')", (beneficiary,)).fetchone():
            self.fail(400, '作者受益人须为已存在的老师/管理员账号。')
        basis = data.get('basis')
        keys = ('deductTax', 'deductShipping', 'deductDiscount', 'deductChannelFee')
        if not isinstance(basis, dict) or set(basis) != set(keys) or any(type(basis[k]) is not bool for k in keys):
            self.fail(400, '计佣基数四个扣项必须显式为布尔值。')
        stamp = now()
        effective = self.integer(data.get('effectiveAt', stamp), stamp, 9_007_199_254_740_991)
        rule = {'ruleId': rule_id, 'version': expected + 1, 'productId': pid, 'kind': kind, 'beneficiary': beneficiary, 'currency': currency, 'mode': mode, 'rateBps': self.integer(data.get('rateBps', 0), 0, 10000), 'fixedMinor': self.integer(data.get('fixedMinor', 0)), 'rounding': rounding, 'basis': basis, 'capMinor': None if data.get('capMinor') is None else self.integer(data['capMinor']), 'freezeDays': self.integer(data.get('freezeDays'), 0, 3650), 'minimumSettlementMinor': self.integer(data.get('minimumSettlementMinor')), 'refundMethod': 'quantity_proportional', 'status': data['status'], 'effectiveAt': effective, 'createdAt': stamp, 'note': self.text(data.get('note'), 2000), 'sandboxOnly': True}
        if mode == 'rate' and rule['fixedMinor'] or mode == 'fixed_per_unit' and rule['rateBps']:
            self.fail(400, '比例与固定额只能使用一种。')
        db.execute('INSERT INTO commission_rules VALUES(?,?,?,?,?,?,?)', (rule_id, rule['version'], pid, kind, effective, stamp, dump(rule)))
        event(db, actor['id'], 'rule.version', rule_id, {'version': rule['version']})
        return {'rule': rule, 'actualPaid': False}

    def action(self, db, method, path, data, actor, permission):
        uid, stamp = actor['id'], now()
        if path == '/api/admin/commissions/settings' and method == 'PATCH':
            self.who(db, [])
            if data.get('productionEnabled') not in (None, False) or data.get('actualPaymentsEnabled') not in (None, False) or type(data.get('sandboxEnabled')) is not bool or data.get('stackingPolicy') not in ('allow_both', 'exclusive_author', 'exclusive_promotion') or data.get('attributionStrategy') not in ('first_touch', 'last_touch'):
                self.fail(400, '生产计佣/打款禁止启用；沙箱归因和并行策略须明确。')
            value = {k: data[k] for k in ('sandboxEnabled', 'stackingPolicy', 'attributionStrategy')}
            value.update(productionEnabled=False, actualPaymentsEnabled=False)
            db.execute("UPDATE commission_config SET data=? WHERE key='settings'", (dump(value),))
            event(db, uid, 'settings', 'sandbox')
            return {'settings': value}
        if path == '/api/admin/commissions/grants' and method == 'POST':
            self.who(db, [])
            target = self.text(data.get('userId'))
            target_row = db.execute('SELECT role FROM users WHERE id=?', (target,)).fetchone()
            if not target_row or data.get('permission') not in ('business', 'finance', 'support', 'none') or data.get('permission') != 'none' and target_row['role'] not in ('admin', 'operator', 'reviewer'):
                self.fail(400, '授权账号或权限无效。')
            if data['permission'] == 'none':
                db.execute('DELETE FROM commission_grants WHERE user_id=?', (target,))
            else:
                db.execute('INSERT INTO commission_grants VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET permission=excluded.permission,updated=excluded.updated,actor=excluded.actor', (target, data['permission'], stamp, uid))
            event(db, uid, 'grant', target, {'permission': data['permission']})
            return {'saved': True}
        self.enabled(db)
        if path == '/api/admin/commissions/rules' and method == 'POST':
            self.who(db, ['business'])
            return self.save_rule(db, data, actor)
        if path == '/api/admin/commissions/invites' and method == 'POST':
            self.who(db, ['business'])
            code = self.text(data.get('code'), 64)
            if not re.fullmatch('[A-Za-z0-9_-]{4,64}', code):
                self.fail(400, '邀请码仅支持4至64位字母数字或下划线短横线。')
            old = db.execute('SELECT * FROM commission_invites WHERE code=?', (code,)).fetchone()
            if old:
                if data.get('status') != 'revoked':
                    self.fail(409, '已有邀请码不可改受益人或续期，请新建代码。')
                db.execute("UPDATE commission_invites SET status='revoked' WHERE code=?", (code,))
                event(db, uid, 'invite.revoke', code)
                return {'revoked': True}
            beneficiary = self.text(data.get('beneficiary'))
            if not db.execute('SELECT 1 FROM users WHERE id=?', (beneficiary,)).fetchone():
                self.fail(400, '受益人账号不存在。')
            valid = self.integer(data.get('validUntil'), stamp + 1, 9_007_199_254_740_991)
            priority = self.integer(data.get('priority'), 0, 1000)
            info = {'code': code, 'beneficiary': beneficiary, 'validUntil': valid, 'priority': priority, 'createdAt': stamp, 'sandboxOnly': True}
            db.execute('INSERT INTO commission_invites VALUES(?,?,?,?,?,?,?)', (code, beneficiary, valid, priority, 'active', stamp, dump(info)))
            event(db, uid, 'invite.create', code)
            return {'invite': info}
        if path == '/api/commissions/attributions' and method == 'POST':
            if set(data) - {'code', 'requestId'}:
                self.fail(400, '归因仅接受邀请码和幂等请求号，不接受客户端受益人。')
            code, request = self.text(data.get('code'), 64), self.text(data.get('requestId'), 128)
            old = db.execute('SELECT * FROM commission_attributions WHERE owner=? AND request_id=?', (uid, request)).fetchone()
            if old:
                if old['code'] != code:
                    self.fail(409, '幂等请求号已用于不同邀请码。')
                return {'attribution': json.loads(old['data'])}
            invite = db.execute("SELECT * FROM commission_invites WHERE code=? AND status='active' AND valid_until>?", (code, stamp)).fetchone()
            if not invite or invite['beneficiary'] == uid:
                self.fail(400, '邀请码无效、过期或属于本人。')
            info = {'id': str(uuid4()), 'code': code, 'beneficiary': invite['beneficiary'], 'priority': invite['priority'], 'createdAt': stamp, 'validUntil': invite['valid_until']}
            db.execute('INSERT INTO commission_attributions VALUES(?,?,?,?,?,?,?,?,?)', (info['id'], uid, code, invite['beneficiary'], invite['priority'], stamp, invite['valid_until'], request, dump(info)))
            event(db, uid, 'attribution.capture', info['id'])
            return {'attribution': info}
        self.who(db, ['finance'])
        if path == '/api/admin/commissions/facts' and method == 'POST':
            item = db.execute('SELECT * FROM commerce_order_items WHERE id=?', (self.text(data.get('itemId')),)).fetchone()
            if not item:
                self.fail(404, '订单项不存在。')
            if db.execute("SELECT 1 FROM commission_ledger WHERE item_id=? AND status!='waiting_facts'", (item['id'],)).fetchone():
                self.fail(409, '已确认金额不能静默改费用，须单独审计调整。')
            value = {'channelFeeMinor': None if data.get('channelFeeMinor') is None else self.integer(data['channelFeeMinor']), 'discountMinor': 0, 'source': self.text(data.get('source'), 2000), 'isTestData': True}
            if data.get('isTestData') is not True or data.get('discountMinor', 0) != 0:
                self.fail(400, '当前仅支持沙箱真实事实补录，统一交易尚无优惠功能。')
            db.execute('INSERT INTO commission_facts VALUES(?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET data=excluded.data,updated=excluded.updated,actor=excluded.actor', (item['id'], dump(value), stamp, uid))
            event(db, uid, 'facts', item['id'])
            return {**sync_commission_order(db, item['order_id']), 'facts': value}
        match = re.fullmatch('/api/admin/commissions/orders/([^/]+)/sync', path)
        if match and method == 'POST':
            return sync_commission_order(db, match.group(1))
        if path == '/api/admin/commissions/confirm' and method == 'POST':
            lid = self.text(data.get('ledgerId'), 500)
            row = db.execute('SELECT * FROM commission_ledger WHERE id=?', (lid,)).fetchone()
            if not row:
                self.fail(404, '台账不存在。')
            result = sync_commission_order(db, row['order_id'])
            db.execute("UPDATE commission_ledger SET status='frozen',updated=? WHERE id=? AND status='pending_confirmation'", (stamp, lid))
            event(db, uid, 'ledger.confirm', lid)
            return {'synced': result, 'item': self.ledger(db.execute('SELECT * FROM commission_ledger WHERE id=?', (lid,)).fetchone(), permission)}
        if path == '/api/admin/commissions/advance' and method == 'POST':
            for order in db.execute("SELECT DISTINCT order_id FROM commission_ledger WHERE status IN ('frozen','payable','statement_pending')").fetchall():
                sync_commission_order(db, order['order_id'])
            result = db.execute("UPDATE commission_ledger SET status='payable',updated=? WHERE status='frozen' AND freeze_until<=? AND net_minor>0 AND EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=commission_ledger.order_id AND o.fulfillment_status IN ('fulfilled','delivered') AND o.payment_status IN ('paid','partially_refunded'))", (stamp, stamp))
            event(db, uid, 'ledger.advance', 'sandbox')
            return {'advanced': result.rowcount, 'actualPaid': False}
        if path == '/api/admin/commissions/statements' and method == 'POST':
            beneficiary, currency = self.text(data.get('beneficiary')), self.text(data.get('currency'), 3, 3).upper()
            start, end = self.integer(data.get('from'), 0, 9_007_199_254_740_991), self.integer(data.get('to'), 0, 9_007_199_254_740_991)
            if start > end or end > stamp:
                self.fail(400, '结算周期范围无效。')
            rows = db.execute("SELECT * FROM commission_ledger WHERE beneficiary=? AND currency=? AND status='payable' AND created BETWEEN ? AND ? ORDER BY id", (beneficiary, currency, start, end)).fetchall()
            if not rows:
                self.fail(409, '没有符合周期和币种的可结算项目。')
            for row in rows:
                sync_commission_order(db, row['order_id'])
            rows = db.execute("SELECT * FROM commission_ledger WHERE beneficiary=? AND currency=? AND status='payable' AND created BETWEEN ? AND ? ORDER BY id", (beneficiary, currency, start, end)).fetchall()
            recoveries = db.execute("SELECT * FROM commission_adjustments WHERE beneficiary=? AND currency=? AND status='pending_recovery' ORDER BY created,id", (beneficiary, currency)).fetchall()
            total = sum(r['net_minor'] for r in rows) - sum(r['amount_minor'] for r in recoveries)
            minimum = max([json.loads(r['data'])['rule']['minimumSettlementMinor'] for r in rows] or [1])
            if total <= 0 or total < minimum or total > MAX_MINOR:
                self.fail(409, '扣除待抵扣后未达到本次最低结算额或金额上限。')
            sid = str(uuid4())
            db.execute('INSERT INTO commission_statements VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (sid, beneficiary, currency, total, 'awaiting_approval', 1, uid, '', start, end, stamp, stamp))
            for row in rows:
                db.execute("INSERT INTO commission_statement_lines VALUES(?,'earning',?,?)", (sid, row['id'], row['net_minor']))
            for row in recoveries:
                db.execute("INSERT INTO commission_statement_lines VALUES(?,'recovery',?,?)", (sid, row['id'], -row['amount_minor']))
            event(db, uid, 'statement.create', sid)
            return {'statement': dict(db.execute('SELECT * FROM commission_statements WHERE id=?', (sid,)).fetchone()), 'actualPaid': False}
        match = re.fullmatch('/api/admin/commissions/statements/([^/]+)/(approve|book|cancel|payment)', path)
        if match and method == 'POST':
            sid, action = match.groups()
            row = db.execute('SELECT * FROM commission_statements WHERE id=?', (sid,)).fetchone()
            if not row:
                self.fail(404, '结算单不存在。')
            if action == 'payment':
                if row['status'] != 'booked' or data.get('isTestData') is not True:
                    self.fail(409, '仅记账后的沙箱结算单可登记测试凭证。')
                recipient = data.get('recipient') or {}
                value = {'isTestData': True, 'recipient': {k: self.text(recipient.get(k), 150) for k in ('name', 'country', 'currency', 'channel', 'accountReference')}, 'proofReference': self.text(data.get('proofReference'), 1000), 'proofVerified': False, 'actualPaid': False}
                if value['recipient']['currency'] != row['currency'] or not re.fullmatch('[A-Z]{2}', value['recipient']['country']):
                    self.fail(400, '收款币种或国家代码不符合结算单。')
                request_id = self.text(data.get('requestId'), 128)
                old = db.execute('SELECT * FROM commission_payments WHERE request_id=? OR statement_id=?', (request_id, sid)).fetchone()
                if old:
                    if old['request_id'] != request_id or old['statement_id'] != sid or json.loads(old['data']) != value:
                        self.fail(409, '凭证幂等请求已用于其他内容。')
                    return {'payment': {**value, 'id': old['id'], 'status': old['status']}}
                pid = str(uuid4())
                db.execute('INSERT INTO commission_payments VALUES(?,?,?,?,?,?,?)', (pid, sid, request_id, dump(value), 'sandbox_registered', stamp, uid))
                event(db, uid, 'payment.sandbox_register', pid)
                return {'payment': {**value, 'id': pid, 'status': 'sandbox_registered'}}
            expected = self.integer(data.get('expectedVersion'), 1)
            if expected != row['version']:
                self.fail(409, '结算单版本已变化，请刷新。')
            if action == 'approve' and (row['status'] != 'awaiting_approval' or row['creator'] == uid):
                self.fail(409, '审批须另一位有财务权限的账号完成。')
            if action == 'book' and row['status'] != 'approved' or action == 'cancel' and row['status'] not in ('awaiting_approval', 'approved'):
                self.fail(409, '结算单状态不允许此操作。')
            for source in db.execute("SELECT l.order_id FROM commission_statement_lines x JOIN commission_ledger l ON l.id=x.source_id WHERE x.statement_id=? AND x.kind='earning'", (sid,)).fetchall():
                sync_commission_order(db, source['order_id'])
            fresh = db.execute('SELECT * FROM commission_statements WHERE id=?', (sid,)).fetchone()
            if fresh['version'] != expected:
                return {'statement': dict(fresh), 'invalidatedByRefund': True, 'actualPaid': False}
            status = {'approve': 'approved', 'book': 'booked', 'cancel': 'cancelled'}[action]
            db.execute('UPDATE commission_statements SET status=?,approver=?,version=version+1,updated=? WHERE id=? AND version=?', (status, uid if action == 'approve' else row['approver'], stamp, sid, expected))
            event(db, uid, 'statement.' + action, sid)
            return {'statement': dict(db.execute('SELECT * FROM commission_statements WHERE id=?', (sid,)).fetchone()), 'actualPaid': False}
        self.fail(404, '分佣接口不存在。')

    def route(self, method, path):
        if not path.startswith(('/api/commissions', '/api/admin/commissions')):
            return None
        from urllib.parse import parse_qs, urlsplit
        filters = {k: v[-1] for k, v in parse_qs(urlsplit(self.h.path).query).items()}
        with self.store.connect() as db:
            actor, permission = self.who(db, ['business', 'finance', 'support'] if path.startswith('/api/admin/') else None)
            if method == 'GET':
                if path in ('/api/commissions', '/api/admin/commissions', '/api/admin/commissions/export'):
                    report = self.report(db, permission if path.startswith('/api/admin/') else 'self', actor, filters)
                    if path == '/api/admin/commissions':
                        if permission in ('admin', 'business'):
                            report.update(rules=[json.loads(r['data']) for r in db.execute('SELECT data FROM commission_rules ORDER BY created DESC,version DESC')], invites=[{**json.loads(r['data']), 'status': r['status']} for r in db.execute('SELECT * FROM commission_invites ORDER BY created DESC')])
                        if permission == 'admin':
                            report['grants'] = [dict(r) for r in db.execute('SELECT user_id,permission FROM commission_grants ORDER BY user_id')]
                    if path.endswith('/export'):
                        out = io.StringIO(); fields = ['id', 'orderId', 'itemId', 'beneficiary', 'productId', 'kind', 'ruleId', 'ruleVersion', 'currency', 'status', 'baseMinor', 'amountMinor', 'netMinor', 'actualPaid']
                        writer = csv.writer(out); writer.writerow(fields)
                        for row in report['items']:
                            writer.writerow([("'" + str(row.get(k, ''))) if str(row.get(k, '')).lstrip().startswith(('=', '+', '-', '@')) else row.get(k, '') for k in fields])
                        report['csv'] = out.getvalue()
                    return report
                self.fail(404, '分佣查询接口不存在。')
            self.rate('commissions:' + actor['id'], 60)
            data = self.h.body()
            if not isinstance(data, dict):
                self.fail(400, '请求必须为JSON对象。')
            db.execute('BEGIN IMMEDIATE')
            return self.action(db, method, path, data, actor, permission)
