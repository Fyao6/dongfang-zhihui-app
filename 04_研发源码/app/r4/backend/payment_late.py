"""PAY10/PAY13 late sandbox payment facts and inventory compensation.

No real refund is executed or reported as completed. Refund candidates are
durable staff work items, separate from ordinary stock-restoring refunds.
"""
import hashlib
import json
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

STATUSES = ('fulfilled','refund_pending','refund_processing')
DDL = """
CREATE TABLE IF NOT EXISTS payment_late_cases(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,order_id TEXT NOT NULL UNIQUE,
 transaction_id TEXT NOT NULL UNIQUE,receipt_id TEXT NOT NULL,status TEXT NOT NULL
 CHECK(status IN ('fulfilled','refund_pending','refund_processing')),reason TEXT NOT NULL,
 amount_minor INTEGER NOT NULL,currency TEXT NOT NULL,ledger_id TEXT NOT NULL DEFAULT '',
 created INTEGER NOT NULL,updated INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS payment_late_queue ON payment_late_cases(status,created,id);
CREATE TABLE IF NOT EXISTS payment_late_attempts(
 id TEXT PRIMARY KEY,case_id TEXT NOT NULL,action TEXT NOT NULL,actor TEXT NOT NULL,
 request_id TEXT NOT NULL DEFAULT '',note TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS payment_late_request ON payment_late_attempts(actor,request_id) WHERE request_id!='';
CREATE INDEX IF NOT EXISTS payment_late_case_actions ON payment_late_attempts(case_id,created,id);
"""


def init_schema(db):
    db.executescript(DDL)


def now():
    return time.time_ns()//1_000_000


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


class LateReview(Exception):
    pass


def eligible(order, stamp):
    return ((order['status']=='awaiting_payment' and order['payment_status']=='unpaid' and order['reserved_until']<=stamp)
            or (order['status']=='closed' and order['payment_status']=='expired'))


def serialize(row, admin=False):
    if row is None:
        return None
    result = {'id':row['id'],'status':row['status'],'reason':row['reason'],
        'amountMinor':row['amount_minor'],'currency':row['currency'],
        'created':row['created'],'updated':row['updated'],'sandboxOnly':True,'productionEnabled':False}
    if admin:
        result.update(orderId=row['order_id'],transactionId=row['transaction_id'],receiptId=row['receipt_id'],ledgerId=row['ledger_id'])
    return result


def order_summary(db, order_id):
    return serialize(db.execute('SELECT * FROM payment_late_cases WHERE order_id=?',(order_id,)).fetchone())


def option_identity(value):
    if not isinstance(value,list) or any(not isinstance(item,dict) or set(item)!={'name','value'}
            or not isinstance(item['name'],str) or not isinstance(item['value'],str) for item in value):
        return None
    return sorted((item['name'],item['value']) for item in value)


def reason_for(db, order, lines):
    if not lines or any(line['type'] not in ('physical','digital') or line['refunded_quantity'] or line['currency']!=order['currency'] for line in lines):
        return 'invalid_order_items'
    reservations = {row['sku_id']:row for row in db.execute('SELECT * FROM commerce_reservations WHERE order_id=?',(order['id'],))}
    if len(reservations)!=len(lines) or any(line['sku_id'] not in reservations
            or reservations[line['sku_id']]['state']!='released'
            or reservations[line['sku_id']]['quantity']!=line['quantity'] for line in lines):
        return 'reservation_unavailable'
    products,skus = {},{}
    for line in lines:
        products[line['id']] = db.execute('SELECT * FROM commerce_products WHERE id=?',(line['product_id'],)).fetchone()
        skus[line['id']] = db.execute('''SELECT s.*,coalesce(v.active,1) active,coalesce(v.options,'[]') options
            FROM commerce_skus s LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id WHERE s.id=?''',(line['sku_id'],)).fetchone()
    if any(products[line['id']] is None or products[line['id']]['status']!='published' for line in lines):
        return 'product_unavailable'
    if any(skus[line['id']] is None or not skus[line['id']]['active'] for line in lines):
        return 'sku_unavailable'
    for line in lines:
        product,sku = products[line['id']],skus[line['id']]
        if product['environment']!='sandbox' or product['type']!=line['type'] or product['content_id']!=line['content_id'] or sku['environment']!='sandbox' or sku['product_id']!=line['product_id'] or sku['currency']!=line['currency']:
            return 'binding_changed'
        try:
            snapshot = json.loads(line['snapshot_data'])
            original = option_identity(snapshot.get('options',[])) if isinstance(snapshot,dict) else None
            current = option_identity(json.loads(sku['options']))
        except (ValueError,TypeError):
            return 'binding_changed'
        if original is None or current is None or original!=current:
            return 'binding_changed'
        if line['type']=='digital' and not db.execute("SELECT 1 FROM contents WHERE kind='courses' AND id=? AND status='published'",(line['content_id'],)).fetchone():
            return 'binding_changed'
    if any(skus[line['id']]['stock']-skus[line['id']]['reserved']<line['quantity'] for line in lines):
        return 'insufficient_stock'
    return ''


def apply_verified_late(db, order, receipt, actor, guard_sql, guard_args, stamp):
    """Called only inside the verified callback's guarded write transaction."""
    existing = db.execute('SELECT * FROM payment_late_cases WHERE order_id=? OR transaction_id=?', (order['id'],receipt['transaction_id'])).fetchone()
    if existing:
        if existing['order_id']!=order['id'] or existing['transaction_id']!=receipt['transaction_id'] or existing['amount_minor']!=receipt['amount_minor'] or existing['currency']!=receipt['currency']:
            raise LateReview('late_transaction_conflict')
        return existing
    if not eligible(order,stamp):
        return None
    lines = db.execute('SELECT * FROM commerce_order_items WHERE order_id=? ORDER BY id',(order['id'],)).fetchall()
    if any(line['type']=='membership' for line in lines):
        raise LateReview('membership_requires_adapter')
    if db.execute("SELECT 1 FROM commerce_payment_events WHERE order_id=? AND kind='sandbox_pay'",(order['id'],)).fetchone():
        raise LateReview('order_already_paid')
    # Close this expired order first, firing the original held-release trigger.
    if order['status']=='awaiting_payment':
        changed = db.execute("UPDATE commerce_orders SET status='closed',payment_status='expired',updated=? WHERE id=? AND owner=? AND environment='sandbox' AND status='awaiting_payment' AND payment_status='unpaid' AND reserved_until<=? AND "+guard_sql,
                             (stamp,order['id'],order['owner'],stamp,*guard_args)).rowcount
        if changed!=1:
            raise LateReview('application_conflict')
    else:
        # A previous close may already have released all reservations. Only this
        # order is touched, and replaying a release never decrements twice.
        db.execute("UPDATE commerce_reservations SET state='released' WHERE order_id=? AND state='held'",(order['id'],))
    reason = reason_for(db,order,lines)
    status = 'refund_pending' if reason else 'fulfilled'
    case_id,ledger = str(uuid4()),str(uuid4()) if not reason else ''
    db.execute('INSERT INTO payment_late_cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
               (case_id,order['owner'],order['id'],receipt['transaction_id'],receipt['id'],status,reason,receipt['amount_minor'],receipt['currency'],ledger,stamp,stamp))
    if reason:
        changed = db.execute("UPDATE commerce_orders SET status='refund_pending',payment_status='refund_pending',fulfillment_status='refund_pending',updated=? WHERE id=? AND owner=? AND status='closed' AND payment_status='expired' AND "+guard_sql,
                             (stamp,order['id'],order['owner'],*guard_args)).rowcount
        if changed!=1:
            raise LateReview('application_conflict')
    else:
        for line in lines:
            changed = db.execute('UPDATE commerce_skus SET stock=stock-? WHERE id=? AND environment=\'sandbox\' AND stock-reserved>=? AND '+guard_sql,
                                 (line['quantity'],line['sku_id'],line['quantity'],*guard_args)).rowcount
            if changed!=1:
                raise LateReview('application_conflict')
            changed = db.execute("UPDATE commerce_reservations SET state='consumed' WHERE order_id=? AND sku_id=? AND quantity=? AND state='released' AND "+guard_sql,
                                 (order['id'],line['sku_id'],line['quantity'],*guard_args)).rowcount
            if changed!=1:
                raise LateReview('application_conflict')
            db.execute('INSERT INTO commerce_inventory_events VALUES(?,?,?,?,?,?,?,?,?)',
                       ('late:'+case_id+':'+line['id'],order['owner'],'sandbox',order['id'],line['id'],line['sku_id'],-line['quantity'],'late_payment_consumed',stamp))
        fingerprint = hashlib.sha256(canonical({'kind':'sandbox_pay','orderId':order['id']}).encode('utf-8')).hexdigest()
        db.execute('INSERT INTO commerce_payment_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                   (ledger,order['owner'],'sandbox',order['id'],'callback:'+receipt['transaction_id'],'sandbox_pay',fingerprint,receipt['amount_minor'],receipt['currency'],'[]','applied',stamp))
        physical = any(line['type']=='physical' for line in lines)
        changed = db.execute("UPDATE commerce_orders SET status=?,payment_status='paid',fulfillment_status=?,updated=? WHERE id=? AND owner=? AND status='closed' AND payment_status='expired' AND total_minor=? AND currency=? AND "+guard_sql,
            ('paid' if physical else 'completed','awaiting_fulfillment' if physical else 'fulfilled',stamp,order['id'],order['owner'],receipt['amount_minor'],receipt['currency'],*guard_args)).rowcount
        if changed!=1:
            raise LateReview('application_conflict')
        # expired->paid does not invoke the old unpaid->paid trigger.
        for line in lines:
            if line['type']=='digital':
                db.execute('INSERT INTO commerce_entitlements VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                           ('sandbox:'+line['id'],order['owner'],'sandbox',order['id'],line['id'],line['content_id'],line['type'],line['quantity'],line['quantity'],'active',stamp,stamp))
        db.execute("DELETE FROM commerce_carts WHERE owner=? AND environment='sandbox'",(order['owner'],))
    db.execute('INSERT INTO payment_late_attempts VALUES(?,?,?,?,?,?,?)',(str(uuid4()),case_id,status,actor,'','',stamp))
    return db.execute('SELECT * FROM payment_late_cases WHERE id=?',(case_id,)).fetchone()


class PaymentLate:
    def __init__(self,store,handler,error,rate):
        self.store,self.h,self.Error,self.rate = store,handler,error,rate

    def fail(self,status,message):
        raise self.Error(status,message)

    def case(self,db,case_id):
        row = db.execute('SELECT * FROM payment_late_cases WHERE id=?',(case_id,)).fetchone()
        if row is None:
            self.fail(404,'找不到此迟到付款记录。')
        return row

    def ack(self,db,case_id,actor,data):
        if set(data)!={'requestId','note'} or not isinstance(data.get('requestId'),str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',data['requestId']) or not isinstance(data.get('note'),str):
            self.fail(400,'请填写有效的受理请求编号和备注。')
        note = data['note'].strip()
        if not 1<=len(note)<=1000 or len(note.encode('utf-8','surrogatepass'))>4000 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff]',note):
            self.fail(400,'受理备注格式无效或过长。')
        db.execute('BEGIN IMMEDIATE')
        row = self.case(db,case_id)
        old = db.execute('SELECT * FROM payment_late_attempts WHERE actor=? AND request_id=?',(actor,data['requestId'])).fetchone()
        if old:
            if old['case_id']!=case_id or old['note']!=note:
                self.fail(409,'该受理编号已用于不同内容。')
            return {'item':serialize(row,True)}
        if row['status']!='refund_pending':
            self.fail(409,'仅退款待办可标为已受理。')
        stamp = now()
        changed = db.execute("UPDATE payment_late_cases SET status='refund_processing',updated=? WHERE id=? AND status='refund_pending'",(stamp,case_id)).rowcount
        if changed!=1:
            self.fail(409,'记录已更新，请刷新。')
        db.execute('INSERT INTO payment_late_attempts VALUES(?,?,?,?,?,?,?)',(str(uuid4()),case_id,'ack',actor,data['requestId'],note,stamp))
        self.store.audit(db,actor,'payment_late.ack',case_id,'sandbox refund work item acknowledged; no funds moved')
        return {'item':serialize(self.case(db,case_id),True)}

    def route(self,method,path):
        prefix = '/api/admin/payment-late'
        if path!=prefix and not path.startswith(prefix+'/'):
            return None
        actor = self.h.require(['admin'])['id']
        self.rate('payment-late:'+('read:' if method=='GET' else 'write:')+actor,180 if method=='GET' else 30)
        with self.store.connect() as db:
            if path==prefix and method=='GET':
                query = parse_qs(urlsplit(self.h.path).query)
                status,before = query.get('status',[''])[0],query.get('before',[''])[0]
                where,args = [],[]
                if status:
                    if status not in STATUSES:
                        self.fail(400,'迟到付款状态无效。')
                    where.append('status=?');args.append(status)
                if before:
                    cursor = self.case(db,before)
                    where.append('(created,id)<(?,?)');args.extend((cursor['created'],cursor['id']))
                rows = db.execute('SELECT * FROM payment_late_cases'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY created DESC,id DESC LIMIT 26',args).fetchall()
                return {'items':[serialize(row,True) for row in rows[:25]],'next':rows[24]['id'] if len(rows)>25 else None,'productionEnabled':False}
            match = re.fullmatch(re.escape(prefix)+r'/([A-Za-z0-9:_-]{1,100})(/(?:ack|detail))?',path)
            if match and match[2]=='/ack' and method=='POST':
                return self.ack(db,match[1],actor,self.h.body())
            if match and match[2] in (None,'/detail') and method=='GET':
                row = self.case(db,match[1])
                attempts = [dict(id=a['id'],caseId=a['case_id'],action=a['action'],actor=a['actor'],requestId=a['request_id'],note=a['note'],created=a['created']) for a in db.execute('SELECT * FROM payment_late_attempts WHERE case_id=? ORDER BY created,id',(row['id'],))]
                return {'item':serialize(row,True),'attempts':attempts,'productionEnabled':False}
        self.fail(404,'找不到此迟到付款功能。')
