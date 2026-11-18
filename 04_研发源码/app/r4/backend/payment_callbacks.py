"""Durable PAY08 inbox and explicitly invoked sandbox-only callback consumer.

The HMAC fixture is not a payment-provider adapter. Late sandbox receipts may
use guarded inventory compensation; real charges/refunds, an automatic scheduler
and membership callback activation remain disabled.
"""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

STATUSES = ('received', 'processing', 'retry', 'applied', 'manual_review')
MAX_ATTEMPTS = 5
LEASE_MS = 30_000
DDL = """
CREATE TABLE IF NOT EXISTS payment_callback_inbox(
 id TEXT PRIMARY KEY,event_id TEXT NOT NULL UNIQUE,transaction_id TEXT NOT NULL,
 order_id TEXT NOT NULL,fingerprint TEXT NOT NULL,amount_minor INTEGER NOT NULL,
 currency TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('received','processing','retry','applied','manual_review')),
 attempts INTEGER NOT NULL DEFAULT 0,lease_token TEXT NOT NULL DEFAULT '',
 lease_until INTEGER NOT NULL DEFAULT 0,next_attempt INTEGER NOT NULL DEFAULT 0,
 last_error TEXT NOT NULL DEFAULT '',received_count INTEGER NOT NULL DEFAULT 1,
 created INTEGER NOT NULL,updated INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS payment_callback_queue ON payment_callback_inbox(status,next_attempt,created,id);
CREATE INDEX IF NOT EXISTS payment_callback_transaction ON payment_callback_inbox(transaction_id);
CREATE TABLE IF NOT EXISTS payment_callback_transactions(
 transaction_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,fingerprint TEXT NOT NULL,
 receipt_id TEXT NOT NULL,ledger_id TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,updated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_callback_attempts(
 id TEXT PRIMARY KEY,receipt_id TEXT NOT NULL,attempt INTEGER NOT NULL,action TEXT NOT NULL,
 actor TEXT NOT NULL,result TEXT NOT NULL,error_code TEXT NOT NULL,created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS payment_callback_attempt_receipt ON payment_callback_attempts(receipt_id,created,id);
CREATE TABLE IF NOT EXISTS payment_callback_guards(id TEXT PRIMARY KEY,ok INTEGER NOT NULL CHECK(ok=1));
"""


def init_schema(db):
    db.executescript(DDL)


def now():
    return time.time_ns() // 1_000_000


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def fixture_secret():
    ref = os.environ.get('EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF', '')
    if os.environ.get('EW_PAYMENT_CALLBACK_SANDBOX_ENABLED') != '1' or not re.fullmatch(r'EW_PAYMENT_CALLBACK_[A-Z0-9_]{1,80}', ref):
        return None
    value = os.environ.get(ref, '')
    return value if len(value) >= 32 else None


def persist_verified_event(db, data):
    """Server-only persistence for an already verified sandbox adapter result.

    The caller owns the transaction. Conflicts are returned, so their minimal
    audit can commit before a public endpoint returns HTTP 409.
    """
    token = hashlib.sha256(canonical({key: value for key, value in data.items() if key != 'eventId'}).encode('utf-8')).hexdigest()
    stamp = now()
    old = db.execute('SELECT * FROM payment_callback_inbox WHERE event_id=?', (data['eventId'],)).fetchone()
    tx = db.execute('SELECT * FROM payment_callback_transactions WHERE transaction_id=?', (data['transactionId'],)).fetchone()
    conflict = 'event_id_conflict' if old and old['fingerprint'] != token else 'transaction_id_conflict' if tx and tx['fingerprint'] != token else ''
    if conflict:
        receipt = old['id'] if old else tx['receipt_id']
        db.execute('INSERT INTO audits VALUES(?,?,?,?,?,?)', (str(uuid4()), 'system:payment-callback-fixture', 'payment_callback.conflict', receipt, conflict, stamp))
        return {'receiptId': receipt, 'duplicate': False, 'conflict': conflict}
    if old:
        db.execute('UPDATE payment_callback_inbox SET received_count=received_count+1,updated=? WHERE id=?', (stamp, old['id']))
        return {'receiptId': old['id'], 'duplicate': True, 'conflict': ''}
    receipt = str(uuid4())
    primary = db.execute('SELECT * FROM payment_callback_inbox WHERE id=?', (tx['receipt_id'],)).fetchone() if tx else None
    status = primary['status'] if primary else 'received'
    db.execute('''INSERT INTO payment_callback_inbox
        (id,event_id,transaction_id,order_id,fingerprint,amount_minor,currency,status,created,updated)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', (receipt, data['eventId'], data['transactionId'], data['orderId'], token, data['amountMinor'], data['currency'], status, stamp, stamp))
    if primary:
        db.execute('UPDATE payment_callback_inbox SET lease_until=?,next_attempt=?,last_error=? WHERE id=?', (primary['lease_until'], primary['next_attempt'], primary['last_error'], receipt))
    else:
        db.execute('INSERT INTO payment_callback_transactions VALUES(?,?,?,?,?,?,?)', (data['transactionId'], data['orderId'], token, receipt, '', stamp, stamp))
    db.execute('INSERT INTO payment_callback_attempts VALUES(?,?,?,?,?,?,?,?)', (str(uuid4()), receipt, 0, 'receive', '', status, '', stamp))
    return {'receiptId': receipt, 'duplicate': bool(tx), 'conflict': ''}


class CallbackReply:
    def __init__(self, data):
        self.data = data

    def send(self, handler):
        return handler.send(202, self.data)


class Review(Exception):
    pass


class RetryLater(Exception):
    pass


class PaymentCallbacks:
    def __init__(self, store, handler, error, rate):
        self.store, self.h, self.Error, self.rate = store, handler, error, rate

    def fail(self, status, message):
        raise self.Error(status, message)

    def settings(self):
        return {'sandboxEnabled': fixture_secret() is not None, 'productionEnabled': False,
                'adapter': 'sandbox-hmac-fixture'}

    def row(self, db, receipt_id):
        row = db.execute('SELECT * FROM payment_callback_inbox WHERE id=?', (receipt_id,)).fetchone()
        if not row:
            self.fail(404, '找不到此回调收件。')
        return row

    def serialize(self, db, row):
        tx = db.execute('''SELECT t.receipt_id,i.attempts FROM payment_callback_transactions t
            JOIN payment_callback_inbox i ON i.id=t.receipt_id WHERE t.transaction_id=?''', (row['transaction_id'],)).fetchone()
        primary = tx['receipt_id'] if tx else row['id']
        return {'id': row['id'], 'eventId': row['event_id'], 'transactionId': row['transaction_id'],
                'orderId': row['order_id'], 'amountMinor': row['amount_minor'], 'currency': row['currency'],
                'status': row['status'], 'attempts': tx['attempts'] if tx else row['attempts'], 'leaseUntil': row['lease_until'],
                'nextAttempt': row['next_attempt'], 'lastError': row['last_error'],
                'receivedCount': row['received_count'], 'created': row['created'], 'updated': row['updated'],
                'canonicalReceiptId': primary, 'duplicate': primary != row['id'],
                'sandboxOnly': True, 'productionEnabled': False}

    def log(self, db, receipt_id, attempt, action, actor, result, code='', stamp=None):
        db.execute('INSERT INTO payment_callback_attempts VALUES(?,?,?,?,?,?,?,?)',
                   (str(uuid4()), receipt_id, attempt, action, actor, result, code, now() if stamp is None else stamp))

    def verified_body(self):
        secret = fixture_secret()
        if secret is None:
            self.fail(503, '沙箱回调测试适配尚未启用。')
        if self.h.headers.get_content_type() != 'application/json':
            self.fail(415, '需要 JSON 数据。')
        if self.h.headers.get('Transfer-Encoding'):
            self.fail(400, '回调请求格式无效。')
        length = self.h.headers.get('Content-Length', '')
        if not re.fullmatch(r'[0-9]{1,6}', length) or not 0 < int(length) <= 8192:
            self.fail(413, '回调请求内容为空或超出限制。')
        stamp = self.h.headers.get('X-EW-Callback-Timestamp', '')
        signature = self.h.headers.get('X-EW-Callback-Signature', '')
        if not re.fullmatch(r'[0-9]{1,12}', stamp) or abs(int(stamp) - int(time.time())) > 300 or not re.fullmatch(r'[0-9a-fA-F]{64}', signature):
            self.fail(401, '回调验证失败。')
        raw = self.h.rfile.read(int(length))
        if len(raw) != int(length):
            self.fail(400, '回调请求不完整。')
        expected = hmac.new(secret.encode('utf-8'), stamp.encode('ascii') + b'.' + raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.lower()):
            self.fail(401, '回调验证失败。')
        def pairs(values):
            result = {}
            for key, value in values:
                if key in result:
                    raise ValueError('duplicate')
                result[key] = value
            return result
        try:
            data = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('constant')))
        except (ValueError, UnicodeError):
            self.fail(400, '回调内容格式无效。')
        if not isinstance(data, dict) or set(data) != {'eventId', 'transactionId', 'orderId', 'type', 'amountMinor', 'currency'}:
            self.fail(400, '回调内容字段无效。')
        if any(not isinstance(data[key], str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}', data[key]) for key in ('eventId', 'transactionId', 'orderId')):
            self.fail(400, '回调编号无效。')
        if data['type'] != 'payment.succeeded' or type(data['amountMinor']) is not int or not 0 <= data['amountMinor'] <= 1_000_000_000 or not isinstance(data['currency'], str) or not re.fullmatch(r'[A-Z]{3}', data['currency']):
            self.fail(400, '回调事件或金额币种无效。')
        return data

    def receive(self):
        data = self.verified_body()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result = persist_verified_event(db, data)
        if result['conflict']:
            self.fail(409, '回调编号已用于不同内容。')
        return CallbackReply({'accepted': True, 'receiptId': result['receiptId'], 'duplicate': result['duplicate'],
                              'sandboxOnly': True, 'productionEnabled': False})

    def list(self, db, query):
        status, before = query.get('status', [''])[0], query.get('before', [''])[0]
        where, args = [], []
        if status:
            if status not in STATUSES:
                self.fail(400, '回调状态无效。')
            where.append('status=?'); args.append(status)
        if before:
            cursor = self.row(db, before)
            where.append('(created,id)<(?,?)'); args.extend((cursor['created'], cursor['id']))
        rows = db.execute('SELECT * FROM payment_callback_inbox' + (' WHERE ' + ' AND '.join(where) if where else '') + ' ORDER BY created DESC,id DESC LIMIT 26', args).fetchall()
        return {'items': [self.serialize(db, row) for row in rows[:25]], 'next': rows[24]['id'] if len(rows) > 25 else None,
                'settings': self.settings()}

    def transition(self, db, row, status, code='', due=0):
        stamp = now()
        db.execute('''UPDATE payment_callback_inbox SET status=?,lease_token='',lease_until=0,
                    next_attempt=?,last_error=?,updated=? WHERE transaction_id=?''',
                   (status, due, code, stamp, row['transaction_id']))

    def claim(self, actor, *, claim_guard=None):
        stamp = now()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if claim_guard is not None:
                claim_guard(db)
            row = db.execute('''SELECT i.* FROM payment_callback_inbox i JOIN payment_callback_transactions t ON t.receipt_id=i.id
                WHERE ((i.status IN ('received','retry') AND i.next_attempt<=?) OR (i.status='processing' AND i.lease_until<=?))
                ORDER BY i.created,i.id LIMIT 1''', (stamp, stamp)).fetchone()
            if not row:
                return None
            if row['attempts'] >= MAX_ATTEMPTS:
                self.transition(db, row, 'manual_review', 'retry_exhausted')
                self.log(db, row['id'], row['attempts'], 'recover', actor, 'manual_review', 'retry_exhausted', stamp)
                return (row['id'], '')
            lease = str(uuid4())
            changed = db.execute('''UPDATE payment_callback_inbox SET status='processing',attempts=attempts+1,
                lease_token=?,lease_until=?,next_attempt=0,last_error='',updated=? WHERE id=? AND status=? AND attempts=?
                AND (status!='processing' OR lease_until<=?)''',
                (lease, stamp+LEASE_MS, stamp, row['id'], row['status'], row['attempts'], stamp)).rowcount
            if changed != 1:
                return None
            db.execute("UPDATE payment_callback_inbox SET status='processing',lease_until=?,next_attempt=0,last_error='',updated=? WHERE transaction_id=? AND id!=?",
                       (stamp+LEASE_MS, stamp, row['transaction_id'], row['id']))
            self.log(db, row['id'], row['attempts']+1, 'claim', actor, 'processing', 'lease_expired' if row['status']=='processing' else '', stamp)
            return (row['id'], lease)

    def recovery_guard(self, canonical_id, binding, stamp):
        job_id, owner, requested_receipt, job_lease, query_binding = binding
        return ('''EXISTS(SELECT 1 FROM payment_recovery_jobs j
            JOIN commerce_orders ro ON ro.id=j.order_id AND ro.owner=j.owner AND ro.environment='sandbox'
            JOIN payment_callback_inbox ri ON ri.id=j.receipt_id AND ri.order_id=ro.id
            JOIN payment_callback_transactions rt ON rt.transaction_id=ri.transaction_id AND rt.order_id=ro.id
            WHERE j.id=? AND j.owner=? AND j.receipt_id=? AND j.status='processing'
            AND j.lease_token=? AND j.lease_until>? AND rt.receipt_id=? AND j.query_binding=?
            AND NOT EXISTS(SELECT 1 FROM account_lifecycle al WHERE al.owner=j.owner AND al.status='closed'))''',
            (job_id, owner, requested_receipt, job_lease, stamp, canonical_id, query_binding))

    def recovery_current(self, db, canonical_id, binding, stamp):
        from payment_recovery import configuration_binding
        if not binding[4] or configuration_binding()!=binding[4]:
            return False
        sql, args = self.recovery_guard(canonical_id, binding, stamp)
        return bool(db.execute('SELECT 1 WHERE '+sql, args).fetchone())

    def process_receipt(self, receipt_id, actor, *, job_id, owner, job_lease, query_binding):
        """Only the receipt linked to this live owner-bound recovery job may run."""
        binding = (job_id, owner, receipt_id, job_lease, query_binding)
        lease = ''
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            requested = self.row(db, receipt_id)
            tx = db.execute('SELECT * FROM payment_callback_transactions WHERE transaction_id=?', (requested['transaction_id'],)).fetchone()
            if not tx or not self.recovery_current(db, tx['receipt_id'], binding, now()):
                return None
            primary = self.row(db, tx['receipt_id'])
            stamp = now()
            if primary['status'] in ('applied', 'manual_review') or (primary['status']=='retry' and primary['next_attempt']>stamp) or (primary['status']=='processing' and primary['lease_until']>stamp):
                return self.serialize(db, requested)
            if primary['attempts'] >= MAX_ATTEMPTS:
                self.transition(db, primary, 'manual_review', 'retry_exhausted')
                self.log(db, primary['id'], primary['attempts'], 'recover', actor, 'manual_review', 'retry_exhausted')
                return self.serialize(db, self.row(db, receipt_id))
            lease = str(uuid4())
            guard, args = self.recovery_guard(primary['id'], binding, stamp)
            changed = db.execute('''UPDATE payment_callback_inbox SET status='processing',attempts=attempts+1,
                lease_token=?,lease_until=?,next_attempt=0,last_error='',updated=? WHERE id=? AND status=? AND attempts=?
                AND (status!='processing' OR lease_until<=?) AND '''+guard,
                (lease, stamp+LEASE_MS, stamp, primary['id'], primary['status'], primary['attempts'], stamp, *args)).rowcount
            if changed != 1:
                return None
            db.execute("UPDATE payment_callback_inbox SET status='processing',lease_until=?,next_attempt=0,last_error='',updated=? WHERE transaction_id=? AND id!=?", (stamp+LEASE_MS, stamp, primary['transaction_id'], primary['id']))
            self.log(db, primary['id'], primary['attempts']+1, 'claim', actor, 'processing', 'lease_expired' if primary['status']=='processing' else '')
            canonical_id = primary['id']
        try:
            self.apply(canonical_id, lease, actor, recovery=binding)
        except Review as exc:
            self.failed(canonical_id, lease, actor, str(exc), False, recovery=binding)
        except RetryLater as exc:
            self.failed(canonical_id, lease, actor, str(exc), True, recovery=binding)
        except sqlite3.OperationalError:
            self.failed(canonical_id, lease, actor, 'storage_unavailable', True, recovery=binding)
        except sqlite3.IntegrityError as exc:
            if 'account_actor_' in str(exc) or 'account_settlement_' in str(exc):
                raise
            self.failed(canonical_id, lease, actor, 'application_conflict', False, recovery=binding)
        with self.store.connect() as db:
            return self.serialize(db, self.row(db, receipt_id))

    def apply(self, receipt_id, lease, actor, recovery=None):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self.row(db, receipt_id)
            stamp = now()
            if row['status'] != 'processing' or row['lease_token'] != lease or row['lease_until'] <= stamp:
                return
            if recovery and not self.recovery_current(db, receipt_id, recovery, stamp):
                return
            if row['event_id'].startswith('query:'):
                from payment_recovery import configuration_binding
                linked = db.execute('SELECT query_binding FROM payment_recovery_jobs WHERE receipt_id=?', (receipt_id,)).fetchone()
                if not linked or not linked['query_binding'] or configuration_binding()!=linked['query_binding']:
                    raise RetryLater('adapter_disabled')
            if fixture_secret() is None:
                raise RetryLater('adapter_disabled')
            settings = db.execute("SELECT data FROM commerce_config WHERE key='settings'").fetchone()
            if not settings or json.loads(settings['data']).get('sandboxEnabled') is not True:
                raise RetryLater('commerce_sandbox_disabled')
            tx = db.execute('SELECT * FROM payment_callback_transactions WHERE transaction_id=? AND receipt_id=? AND fingerprint=?',
                            (row['transaction_id'], row['id'], row['fingerprint'])).fetchone()
            if not tx:
                raise Review('transaction_conflict')
            if tx['ledger_id']:
                self.transition(db, row, 'applied')
                self.log(db, row['id'], row['attempts'], 'complete', actor, 'applied', 'transaction_already_applied')
                return
            order = db.execute("SELECT * FROM commerce_orders WHERE id=? AND environment='sandbox'", (row['order_id'],)).fetchone()
            if not order:
                raise Review('unknown_order')
            if order['total_minor'] != row['amount_minor'] or order['currency'] != row['currency']:
                raise Review('amount_currency_mismatch')
            if not db.execute("SELECT 1 FROM users u WHERE u.id=? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')", (order['owner'],)).fetchone():
                raise Review('account_closed')
            from payment_late import apply_verified_late, LateReview
            extra, extra_args = self.recovery_guard(receipt_id,recovery,stamp) if recovery else ('1',())
            late_guard = '''EXISTS(SELECT 1 FROM payment_callback_inbox WHERE id=? AND status='processing'
                AND lease_token=? AND lease_until>?) AND NOT EXISTS(SELECT 1 FROM account_lifecycle
                WHERE owner=? AND status='closed') AND '''+extra
            late_args = (receipt_id,lease,stamp,order['owner'],*extra_args)
            try:
                late = apply_verified_late(db,order,row,actor,late_guard,late_args,stamp)
            except LateReview as exc:
                raise Review(str(exc)) from None
            if late is not None:
                if late['ledger_id']:
                    db.execute("UPDATE payment_callback_transactions SET ledger_id=?,updated=? WHERE transaction_id=? AND ledger_id=''",(late['ledger_id'],stamp,row['transaction_id']))
                code = '' if late['status']=='fulfilled' else 'late_refund_pending'
                self.transition(db,row,'applied',code)
                self.log(db,row['id'],row['attempts'],'complete',actor,'applied',code,stamp)
                self.store.audit(db,actor,'payment_callback.late',row['id'],late['status'])
                return
            if order['payment_status'] != 'unpaid' or order['status'] != 'awaiting_payment':
                raise Review('order_not_payable')
            if order['reserved_until'] <= stamp:
                raise Review('order_expired')
            lines = db.execute('SELECT * FROM commerce_order_items WHERE order_id=?', (order['id'],)).fetchall()
            if not lines:
                raise Review('invalid_order_items')
            if any(line['type']=='membership' for line in lines):
                raise Review('membership_requires_adapter')
            if any(line['type'] not in ('digital','physical') for line in lines):
                raise Review('unsupported_order_type')
            if db.execute("SELECT 1 FROM commerce_order_items i LEFT JOIN commerce_products p ON p.id=i.product_id WHERE i.order_id=? AND (p.id IS NULL OR p.status!='published' OR p.environment!='sandbox')", (order['id'],)).fetchone():
                raise Review('product_unavailable')
            if db.execute('''SELECT 1 FROM commerce_order_items i LEFT JOIN commerce_reservations r ON r.order_id=i.order_id AND r.sku_id=i.sku_id
                LEFT JOIN commerce_skus s ON s.id=i.sku_id WHERE i.order_id=? AND
                (r.state IS NULL OR r.state!='held' OR r.quantity!=i.quantity OR s.id IS NULL OR s.environment!='sandbox' OR s.reserved<r.quantity OR s.stock<s.reserved)''', (order['id'],)).fetchone():
                raise Review('reservation_unavailable')
            if db.execute("SELECT 1 FROM commerce_payment_events WHERE order_id=? AND kind='sandbox_pay'", (order['id'],)).fetchone():
                raise Review('order_already_paid')
            ledger = str(uuid4())
            ledger_token = hashlib.sha256(canonical({'orderId': order['id'], 'kind':'sandbox_pay'}).encode()).hexdigest()
            db.execute('INSERT INTO commerce_payment_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       (ledger, order['owner'], 'sandbox', order['id'], 'callback:'+row['transaction_id'], 'sandbox_pay', ledger_token,
                        row['amount_minor'], row['currency'], '[]', 'applied', stamp))
            physical = any(line['type']=='physical' for line in lines)
            guard, guard_args = self.recovery_guard(receipt_id, recovery, stamp) if recovery else ('1', ())
            changed = db.execute('''UPDATE commerce_orders SET status=?,payment_status='paid',fulfillment_status=?,updated=?
                WHERE id=? AND owner=? AND environment='sandbox' AND status='awaiting_payment' AND payment_status='unpaid'
                AND reserved_until>? AND total_minor=? AND currency=? AND EXISTS(SELECT 1 FROM payment_callback_inbox
                WHERE id=? AND status='processing' AND lease_token=? AND lease_until>?)
                AND NOT EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=commerce_orders.owner AND status='closed') AND '''+guard,
                ('paid' if physical else 'completed', 'awaiting_fulfillment' if physical else 'fulfilled', stamp,
                 order['id'], order['owner'], stamp, row['amount_minor'], row['currency'], row['id'], lease, stamp, *guard_args)).rowcount
            if changed != 1:
                raise Review('application_conflict')
            db.execute("DELETE FROM commerce_carts WHERE owner=? AND environment='sandbox'", (order['owner'],))
            db.execute("UPDATE payment_callback_transactions SET ledger_id=?,updated=? WHERE transaction_id=? AND ledger_id=''", (ledger, stamp, row['transaction_id']))
            self.transition(db, row, 'applied')
            self.log(db, row['id'], row['attempts'], 'complete', actor, 'applied', stamp=stamp)
            self.store.audit(db, actor, 'payment_callback.sandbox.apply', row['id'], 'sandbox-only; no production access')

    def failed(self, receipt_id, lease, actor, code, transient, recovery=None):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self.row(db, receipt_id)
            if row['status'] != 'processing' or row['lease_token'] != lease or row['lease_until'] <= now():
                return
            if recovery and not self.recovery_current(db, receipt_id, recovery, now()):
                return
            retry = transient and row['attempts'] < MAX_ATTEMPTS
            status = 'retry' if retry else 'manual_review'
            due = now()+1000*(2**(row['attempts']-1)) if retry else 0
            self.transition(db, row, status, code, due)
            self.log(db, row['id'], row['attempts'], 'complete', actor, status, code)

    def process(self, actor, data, *, claim_guard=None):
        limit = data.get('limit', 1)
        if set(data)-{'limit'} or type(limit) is not int or not 1 <= limit <= 10:
            self.fail(400, '每次须处理1至10份收件。')
        items = []
        for _ in range(limit):
            claimed = self.claim(actor, claim_guard=claim_guard)
            if claimed is None:
                break
            receipt, lease = claimed
            if lease:
                try:
                    self.apply(receipt, lease, actor)
                except Review as exc:
                    self.failed(receipt, lease, actor, str(exc), False)
                except RetryLater as exc:
                    self.failed(receipt, lease, actor, str(exc), True)
                except sqlite3.OperationalError:
                    self.failed(receipt, lease, actor, 'storage_unavailable', True)
                except sqlite3.IntegrityError as exc:
                    if 'account_actor_' in str(exc) or 'account_settlement_' in str(exc):
                        raise
                    self.failed(receipt, lease, actor, 'application_conflict', False)
            with self.store.connect() as db:
                items.append(self.serialize(db, self.row(db, receipt)))
        return {'items': items, 'processed': len(items), 'settings': self.settings()}

    def retry(self, db, receipt_id, actor, data):
        if data:
            self.fail(400, '重试请求不接受额外字段。')
        db.execute('BEGIN IMMEDIATE')
        row = self.row(db, receipt_id)
        tx = db.execute('SELECT * FROM payment_callback_transactions WHERE transaction_id=?', (row['transaction_id'],)).fetchone()
        if not tx or tx['receipt_id'] != receipt_id:
            self.fail(409, '请对主收件执行重试。')
        if row['status'] not in ('retry', 'manual_review') or row['lease_until'] > now() or tx['ledger_id']:
            self.fail(409, '当前收件不能重试，请刷新后核对。')
        if row['attempts'] >= MAX_ATTEMPTS:
            self.fail(409, '该收件已达到重试上限，需要另行人工核查。')
        self.transition(db, row, 'retry')
        self.log(db, row['id'], row['attempts'], 'retry', actor, 'retry')
        self.store.audit(db, actor, 'payment_callback.retry', receipt_id, 'explicit sandbox retry')
        return {'item': self.serialize(db, self.row(db, receipt_id))}

    def route(self, method, path):
        public, admin = '/api/payment-callbacks', '/api/admin/payment-callbacks'
        if path == public or path.startswith(public+'/'):
            self.rate('payment-callbacks:receive:'+self.h.client_address[0], 120)
            if path != public+'/sandbox':
                self.fail(503, '正式支付渠道回调尚未接入。')
            if method != 'POST':
                self.fail(405, '不支持的回调操作。')
            return self.receive()
        if path != admin and not path.startswith(admin+'/'):
            return None
        actor = self.h.require(['admin'])['id']
        self.rate('payment-callbacks:'+('read:' if method=='GET' else 'write:')+actor, 180 if method=='GET' else 30)
        if path == admin+'/process' and method == 'POST':
            return self.process(actor, self.h.body())
        with self.store.connect() as db:
            if path == admin and method == 'GET':
                return self.list(db, parse_qs(urlsplit(self.h.path).query))
            match = re.fullmatch(re.escape(admin)+r'/([A-Za-z0-9:_-]{1,100})(/retry)?', path)
            if match and match[2] and method == 'POST':
                return self.retry(db, match[1], actor, self.h.body())
            if match and not match[2] and method == 'GET':
                row = self.row(db, match[1])
                attempts = db.execute('SELECT * FROM payment_callback_attempts WHERE receipt_id=? ORDER BY created,id', (row['id'],)).fetchall()
                return {'item': self.serialize(db, row), 'attempts': [dict(id=a['id'], receiptId=a['receipt_id'], attempt=a['attempt'], action=a['action'], actor=a['actor'], result=a['result'], errorCode=a['error_code'], created=a['created']) for a in attempts]}
        self.fail(404, '找不到此回调管理功能。')
