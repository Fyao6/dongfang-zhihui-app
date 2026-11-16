"""Account-scoped payment inquiries and staff replies for the local sandbox."""

import re
from time import time_ns
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

KINDS = {'duplicate-charge', 'payment-missing', 'restore-failed', 'cancel-renewal'}
ORDER = """SELECT id,environment,payment_status AS paymentStatus,fulfillment_status AS fulfillmentStatus,
total_minor AS totalMinor,refunded_minor AS refundedMinor,currency
FROM commerce_orders WHERE id=? AND owner=? AND environment='sandbox'"""
EVENTS = """SELECT id,kind,amount_minor AS amountMinor,currency,created FROM commerce_payment_events
WHERE order_id=? AND owner=? AND environment='sandbox' AND status='applied' ORDER BY created,id"""
DDL = """
CREATE TABLE IF NOT EXISTS payment_support_tickets(
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, order_id TEXT REFERENCES commerce_orders(id),
 event_id TEXT REFERENCES commerce_payment_events(id), kind TEXT NOT NULL
 CHECK(kind IN ('duplicate-charge','payment-missing','restore-failed','cancel-renewal')),
 message TEXT NOT NULL, request_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'submitted'
 CHECK(status IN ('submitted','accepted','resolved')), version INTEGER NOT NULL DEFAULT 1,
 created INTEGER NOT NULL, updated INTEGER NOT NULL, UNIQUE(owner,request_id)
);
CREATE INDEX IF NOT EXISTS payment_support_owner ON payment_support_tickets(owner,created DESC,id DESC);
CREATE INDEX IF NOT EXISTS payment_support_queue ON payment_support_tickets(status,created DESC,id DESC);
CREATE TABLE IF NOT EXISTS payment_support_actions(
 ticket_id TEXT NOT NULL REFERENCES payment_support_tickets(id), version INTEGER NOT NULL,
 actor TEXT NOT NULL, request_id TEXT NOT NULL, status TEXT NOT NULL
 CHECK(status IN ('accepted','resolved')), reply TEXT NOT NULL, created INTEGER NOT NULL,
 PRIMARY KEY(ticket_id,version), UNIQUE(actor,request_id)
);
CREATE TRIGGER IF NOT EXISTS payment_support_advance BEFORE INSERT ON payment_support_actions
BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM payment_support_tickets WHERE id=NEW.ticket_id
 AND version=NEW.version-1 AND ((status='submitted' AND NEW.status='accepted')
 OR (status='accepted' AND NEW.status='resolved'))) THEN RAISE(ABORT,'payment_support_stale') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM account_lifecycle l JOIN payment_support_tickets t
 ON t.owner=l.owner WHERE t.id=NEW.ticket_id AND l.status='closed')
 THEN RAISE(ABORT,'payment_support_closed') END;
 UPDATE payment_support_tickets SET status=NEW.status,version=NEW.version,updated=NEW.created
 WHERE id=NEW.ticket_id;
END;
"""


def init_schema(db):
    db.executescript(DDL)


class PaymentSupport:
    def __init__(self, store, handler, error, rate):
        self.store, self.h, self.Error, self.rate = store, handler, error, rate

    def fail(self, status, message):
        raise self.Error(status, message)

    def field(self, value, limit, required=True):
        if not isinstance(value, str):
            self.fail(400, '支付客服表单格式错误。')
        value = value.strip()
        if len(value.encode('utf-8', 'surrogatepass')) > limit or (required and not value) or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff]', value):
            self.fail(400, '支付客服表单内容无效或过长。')
        return value

    def order(self, db, order_id, owner):
        row = db.execute(ORDER, (order_id, owner)).fetchone()
        if not row:
            self.fail(404, '找不到此订单。')
        return {'order': dict(row), 'events': [dict(e) for e in db.execute(EVENTS, (order_id, owner))]}

    def ticket(self, db, ticket_id, owner=None):
        sql = 'SELECT * FROM payment_support_tickets WHERE id=?'
        row = db.execute(sql if owner is None else sql+' AND owner=?',
                         (ticket_id,) if owner is None else (ticket_id, owner)).fetchone()
        if not row:
            self.fail(404, '找不到此支付客服工单。')
        return row

    def serialize(self, db, row, summary=False):
        item = dict(id=row['id'], orderId=row['order_id'], kind=row['kind'], status=row['status'],
                    version=row['version'], created=row['created'], updated=row['updated'])
        if not summary:
            replies = db.execute('SELECT status,reply,created FROM payment_support_actions WHERE ticket_id=? AND version<=? ORDER BY version', (row['id'], row['version']))
            item.update(eventId=row['event_id'], message=row['message'], replies=[dict(r) for r in replies])
        return item

    def create(self, db, owner, data):
        kind = self.field(data.get('kind'), 32)
        if kind not in KINDS:
            self.fail(400, '请选择支付问题类型。')
        order_id = self.field(data.get('orderId', ''), 80, False) or None
        event_id = self.field(data.get('eventId', ''), 80, False) or None
        message = self.field(data.get('message', ''), 3000, False)
        request = self.field(data.get('requestId'), 100)
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM payment_support_tickets WHERE owner=? AND request_id=?', (owner, request)).fetchone()
        if row:
            if (row['order_id'], row['event_id'], row['kind'], row['message']) != (order_id, event_id, kind, message):
                self.fail(409, '该提交编号已用于其他内容。')
            return {'ticket': self.serialize(db, row)}
        summary = self.order(db, order_id, owner) if order_id else None
        if event_id and (not summary or not any(event['id'] == event_id for event in summary['events'])):
            self.fail(404, '找不到此订单的支付记录。')
        if not order_id and not message:
            self.fail(400, '未关联订单时，请补充问题说明。')
        ticket_id, now = str(uuid4()), time_ns() // 1_000_000
        db.execute('''INSERT INTO payment_support_tickets
                    (id,owner,order_id,event_id,kind,message,request_id,created,updated) VALUES(?,?,?,?,?,?,?,?,?)''',
                   (ticket_id, owner, order_id, event_id, kind, message, request, now, now))
        return {'ticket': self.serialize(db, self.ticket(db, ticket_id, owner))}

    def act(self, db, actor, ticket_id, data):
        request = self.field(data.get('requestId'), 100)
        status = self.field(data.get('status'), 16)
        reply = self.field(data.get('reply', ''), 3000, status == 'resolved')
        version = data.get('version')
        if type(version) is not int or version not in (1, 2) or status not in ('accepted', 'resolved'):
            self.fail(400, '工单状态或版本无效。')
        db.execute('BEGIN IMMEDIATE')
        row = self.ticket(db, ticket_id)
        previous = db.execute('SELECT * FROM payment_support_actions WHERE actor=? AND request_id=?', (actor, request)).fetchone()
        if previous:
            if (previous['ticket_id'], previous['version'], previous['status'], previous['reply']) != (ticket_id, version+1, status, reply):
                self.fail(409, '该操作编号已用于其他内容。')
        else:
            if db.execute("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'", (row['owner'],)).fetchone():
                self.fail(409, '该账号已关闭，无法继续处理此工单。')
            if row['version'] != version or (row['status'], status) not in (('submitted', 'accepted'), ('accepted', 'resolved')):
                self.fail(409, '工单已更新，请刷新后处理。')
            db.execute('INSERT INTO payment_support_actions VALUES(?,?,?,?,?,?,?)',
                       (ticket_id, version+1, actor, request, status, reply, time_ns() // 1_000_000))
        return {'ticket': self.serialize(db, self.ticket(db, ticket_id))}

    def list(self, db, owner, query):
        scope = [] if owner is None else ['owner=?']
        args = [] if owner is None else [owner]
        status = query.get('status', [''])[0]
        if status:
            if status not in ('submitted', 'accepted', 'resolved'):
                self.fail(400, '工单状态无效。')
            scope.append('status=?')
            args.append(status)
        before = query.get('before', [''])[0]
        if before:
            row = self.ticket(db, before, owner)
            scope.append('(created,id)<(?,?)')
            args.extend((row['created'], row['id']))
        where = ' WHERE '+' AND '.join(scope) if scope else ''
        rows = db.execute('SELECT * FROM payment_support_tickets'+where+' ORDER BY created DESC,id DESC LIMIT 26', args).fetchall()
        return {'items': [self.serialize(db, row, summary=owner is None) for row in rows[:25]],
                'next': rows[24]['id'] if len(rows) > 25 else None}

    def route(self, method, path):
        prefix = '/api/admin/payment-support/' if path.startswith('/api/admin/payment-support/') else '/api/payment-support/'
        if not path.startswith(prefix):
            return None
        admin = prefix.startswith('/api/admin/')
        actor = self.h.require(['admin'] if admin else None)['id']
        self.rate('payment-support:'+('read:' if method == 'GET' else 'write:')+actor, 180 if method == 'GET' else 30)
        owner = None if admin else actor
        subpath = path[len(prefix):]
        with self.store.connect() as db:
            if subpath == 'tickets':
                if method == 'GET':
                    return self.list(db, owner, parse_qs(urlsplit(self.h.path).query))
                if method == 'POST' and not admin:
                    return self.create(db, actor, self.h.body())
            order = re.fullmatch(r'orders/([^/]+)', subpath)
            if order and not admin and method == 'GET':
                return self.order(db, order[1], actor)
            ticket = re.fullmatch(r'tickets/([^/]+)(/actions)?', subpath)
            if ticket and ticket[2] and admin and method == 'POST':
                return self.act(db, actor, ticket[1], self.h.body())
            if ticket and not ticket[2] and method == 'GET':
                row = self.ticket(db, ticket[1], owner)
                result = {'ticket': self.serialize(db, row), 'payment': self.order(db, row['order_id'], row['owner']) if row['order_id'] else None}
                if admin:
                    result['accountClosed'] = bool(db.execute("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'", (row['owner'],)).fetchone())
                return result
        self.fail(404, '找不到此支付客服功能。')
