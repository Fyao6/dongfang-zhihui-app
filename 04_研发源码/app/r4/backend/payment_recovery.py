"""PAY09 owner-scoped recovery using a real HTTP sandbox fixture query.

This explicit fixture protocol is not a production payment-provider adapter.
Only a verified server-side query can enqueue a PAY08 payment event.
"""
import hashlib
import hmac
import json
import os
import re
import socket
import sqlite3
import time
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

from payment_callbacks import PaymentCallbacks, canonical, fixture_secret, now, persist_verified_event

MAX_ATTEMPTS = 5
LEASE_MS = 30_000
STATUSES = ('pending','processing','retry','confirmed','unpaid','manual_review')
DDL = """
CREATE TABLE IF NOT EXISTS payment_recovery_jobs(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,order_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','processing','retry','confirmed','unpaid','manual_review')),
 attempts INTEGER NOT NULL DEFAULT 0,lease_token TEXT NOT NULL DEFAULT '',
 lease_until INTEGER NOT NULL DEFAULT 0,next_attempt INTEGER NOT NULL DEFAULT 0,
 last_error TEXT NOT NULL DEFAULT '',receipt_id TEXT NOT NULL DEFAULT '',
 created INTEGER NOT NULL,updated INTEGER NOT NULL,query_binding TEXT NOT NULL DEFAULT '',UNIQUE(owner,order_id)
);
CREATE INDEX IF NOT EXISTS payment_recovery_queue ON payment_recovery_jobs(status,next_attempt,created,id);
CREATE TABLE IF NOT EXISTS payment_recovery_requests(
 owner TEXT NOT NULL,request_id TEXT NOT NULL,order_id TEXT NOT NULL,job_id TEXT NOT NULL,
 created INTEGER NOT NULL,PRIMARY KEY(owner,request_id)
);
CREATE TABLE IF NOT EXISTS payment_recovery_attempts(
 id TEXT PRIMARY KEY,job_id TEXT NOT NULL,attempt INTEGER NOT NULL,action TEXT NOT NULL,
 actor TEXT NOT NULL,result TEXT NOT NULL,error_code TEXT NOT NULL,created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS payment_recovery_attempt_job ON payment_recovery_attempts(job_id,created,id);
"""


def init_schema(db):
    db.executescript(DDL)
    if 'query_binding' not in {row[1] for row in db.execute('PRAGMA table_info(payment_recovery_jobs)')}:
        db.execute("ALTER TABLE payment_recovery_jobs ADD COLUMN query_binding TEXT NOT NULL DEFAULT ''")


def configuration():
    if os.environ.get('EW_PAYMENT_QUERY_SANDBOX_ENABLED') != '1' or fixture_secret() is None:
        return None
    endpoint = os.environ.get('EW_PAYMENT_QUERY_SANDBOX_ENDPOINT', '')
    match = re.fullmatch(r'http://127\.0\.0\.1:([1-9][0-9]{0,4})/pay09-fixture/query', endpoint)
    ref = os.environ.get('EW_PAYMENT_QUERY_SANDBOX_SECRET_REF', '')
    if not match or int(match[1]) > 65535 or not re.fullmatch(r'EW_PAYMENT_QUERY_[A-Z0-9_]{1,80}', ref):
        return None
    secret = os.environ.get(ref, '')
    return (endpoint, secret) if len(secret) >= 32 else None


def configuration_binding(config=None):
    config = configuration() if config is None else config
    if config is None:
        return ''
    return hashlib.sha256(canonical({'enabled':'1','endpoint':config[0],
        'secretRef':os.environ.get('EW_PAYMENT_QUERY_SANDBOX_SECRET_REF',''),
        'secretHash':hashlib.sha256(config[1].encode('utf-8')).hexdigest()}).encode('utf-8')).hexdigest()


class QueryFailure(Exception):
    def __init__(self, code, transient=True):
        self.code, self.transient = code, transient


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        return None


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('constant')))


def query_fixture(job, order):
    config = configuration()
    if config is None:
        raise QueryFailure('adapter_disabled')
    endpoint, secret = config
    if not job['query_binding'] or configuration_binding(config)!=job['query_binding']:
        raise QueryFailure('adapter_disabled')
    raw = canonical({'queryId':job['id'],'orderId':order['id'],
                     'amountMinor':order['total_minor'],'currency':order['currency']}).encode('utf-8')
    stamp = str(int(time.time()))
    signature = hmac.new(secret.encode('utf-8'), stamp.encode('ascii')+b'.'+raw, hashlib.sha256).hexdigest()
    request = Request(endpoint, data=raw, method='POST', headers={
        'Content-Type':'application/json','X-EW-Query-Timestamp':stamp,'X-EW-Query-Signature':signature})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=8) as response:
            if response.status != 200:
                raise QueryFailure('query_http_error')
            declared = response.headers.get('Content-Length')
            if declared is not None and (not re.fullmatch(r'[0-9]{1,6}', declared) or int(declared)>8192):
                raise QueryFailure('invalid_query_response', False)
            body = response.read(8193)
            if len(body)>8192:
                raise QueryFailure('invalid_query_response', False)
            response_stamp = response.headers.get('X-EW-Query-Timestamp', '')
            response_signature = response.headers.get('X-EW-Query-Signature', '')
    except (TimeoutError, socket.timeout):
        raise QueryFailure('query_timeout') from None
    except HTTPError:
        raise QueryFailure('query_http_error') from None
    except URLError as exc:
        raise QueryFailure('query_timeout' if isinstance(exc.reason, (TimeoutError, socket.timeout)) else 'transport_unavailable') from None
    except (OSError, ValueError):
        raise QueryFailure('transport_unavailable') from None
    except HTTPException:
        raise QueryFailure('invalid_query_response', False) from None
    if not re.fullmatch(r'[0-9]{1,12}', response_stamp) or abs(int(response_stamp)-int(time.time()))>300 or not re.fullmatch(r'[0-9a-fA-F]{64}', response_signature):
        raise QueryFailure('invalid_query_signature', False)
    expected = hmac.new(secret.encode('utf-8'), response_stamp.encode('ascii')+b'.'+body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, response_signature.lower()):
        raise QueryFailure('invalid_query_signature', False)
    try:
        data = strict_json(body)
    except (ValueError, UnicodeError):
        raise QueryFailure('invalid_query_response', False) from None
    if not isinstance(data, dict) or set(data)!={'queryId','orderId','state','transactionId','amountMinor','currency'}:
        raise QueryFailure('invalid_query_response', False)
    if not isinstance(data['state'], str) or data['state'] not in ('paid','unpaid','pending','not_found','failed'):
        raise QueryFailure('invalid_query_response', False)
    if not isinstance(data['transactionId'], str) or (data['state']=='paid' and not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}', data['transactionId'])) or (data['state']!='paid' and data['transactionId']!=''):
        raise QueryFailure('invalid_query_response', False)
    if type(data['amountMinor']) is not int or not 0<=data['amountMinor']<=1_000_000_000 or not isinstance(data['currency'], str) or not re.fullmatch(r'[A-Z]{3}', data['currency']):
        raise QueryFailure('invalid_query_response', False)
    if data['queryId']!=job['id'] or data['orderId']!=order['id'] or data['amountMinor']!=order['total_minor'] or data['currency']!=order['currency']:
        raise QueryFailure('query_mismatch', False)
    return data


class PaymentRecovery:
    def __init__(self, store, handler, error, rate):
        self.store, self.h, self.Error, self.rate = store, handler, error, rate

    def fail(self, status, message):
        raise self.Error(status, message)

    def job(self, db, job_id):
        row = db.execute('SELECT * FROM payment_recovery_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            self.fail(404, '找不到此支付恢复任务。')
        return row

    def order(self, db, order_id, owner=None):
        sql = "SELECT * FROM commerce_orders WHERE id=? AND environment='sandbox'"
        row = db.execute(sql+(' AND owner=?' if owner is not None else ''),
                         (order_id, owner) if owner is not None else (order_id,)).fetchone()
        if not row:
            self.fail(404, '找不到此订单。')
        return row

    def public_job(self, row):
        return None if row is None else {'id':row['id'],'orderId':row['order_id'],'status':row['status'],
            'attempts':row['attempts'],'receiptId':row['receipt_id'],'lastError':row['last_error'],
            'nextAttempt':row['next_attempt'],'leaseUntil':row['lease_until'],'created':row['created'],'updated':row['updated']}

    def view(self, db, order, job=None):
        return {'job':self.public_job(job),'order':{'id':order['id'],'paymentStatus':order['payment_status'],
            'fulfillmentStatus':order['fulfillment_status'],'totalMinor':order['total_minor'],
            'currency':order['currency'],'environment':'sandbox'},
            'queryReady':configuration() is not None,'productionEnabled':False}

    def log(self, db, job, action, actor, result, code=''):
        db.execute('INSERT INTO payment_recovery_attempts VALUES(?,?,?,?,?,?,?,?)',
                   (str(uuid4()),job['id'],job['attempts'],action,actor,result,code,now()))

    def owner_active(self, db, owner):
        return bool(db.execute("SELECT 1 FROM users u WHERE u.id=? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')", (owner,)).fetchone())

    def current(self, db, job_id, lease, binding=None):
        row = self.job(db, job_id)
        if row['status']!='processing' or row['lease_token']!=lease or row['lease_until']<=now():
            return None
        if not self.owner_active(db, row['owner']):
            return None
        if binding is not None and (not binding or row['query_binding']!=binding or configuration_binding()!=binding):
            raise QueryFailure('adapter_disabled')
        # This guarded mutation revalidates the current request actor after HTTP.
        changed = db.execute('''UPDATE payment_recovery_jobs SET updated=updated WHERE id=? AND status='processing'
            AND lease_token=? AND lease_until>? AND EXISTS(SELECT 1 FROM commerce_orders o
            WHERE o.id=payment_recovery_jobs.order_id AND o.owner=payment_recovery_jobs.owner AND o.environment='sandbox')
            AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=payment_recovery_jobs.owner AND l.status='closed')''', (job_id,lease,now())).rowcount
        return self.job(db, job_id) if changed==1 else None

    def finish(self, db, job, lease, status, code='', due=0, receipt=None):
        changed = db.execute('''UPDATE payment_recovery_jobs SET status=?,lease_token='',lease_until=0,
            next_attempt=?,last_error=?,receipt_id=?,updated=? WHERE id=? AND status='processing'
            AND lease_token=? AND lease_until>? AND EXISTS(SELECT 1 FROM commerce_orders o
            WHERE o.id=payment_recovery_jobs.order_id AND o.owner=payment_recovery_jobs.owner AND o.environment='sandbox')
            AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=payment_recovery_jobs.owner AND l.status='closed')''',
            (status,due,code,job['receipt_id'] if receipt is None else receipt,now(),job['id'],lease,now())).rowcount
        return changed==1

    def create(self, owner, order_id, data):
        if set(data)!={'requestId'} or not isinstance(data.get('requestId'), str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}', data['requestId']):
            self.fail(400, '请提供有效的支付恢复请求编号。')
        if configuration() is None:
            self.fail(503, '沙箱主动查单适配尚未启用。')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.order(db, order_id, owner)
            request = db.execute('SELECT * FROM payment_recovery_requests WHERE owner=? AND request_id=?', (owner,data['requestId'])).fetchone()
            if request:
                if request['order_id']!=order_id:
                    self.fail(409, '该恢复请求编号已用于其他订单。')
                return request['job_id']
            job = db.execute('SELECT * FROM payment_recovery_jobs WHERE owner=? AND order_id=?', (owner,order_id)).fetchone()
            stamp = now()
            if job is None:
                job_id = str(uuid4())
                db.execute('''INSERT INTO payment_recovery_jobs(id,owner,order_id,status,created,updated)
                    VALUES(?,?,?,'pending',?,?)''', (job_id,owner,order_id,stamp,stamp))
                job = self.job(db, job_id)
            else:
                job_id = job['id']
                if job['status']=='unpaid' and job['attempts']<MAX_ATTEMPTS:
                    db.execute("UPDATE payment_recovery_jobs SET status='pending',next_attempt=0,last_error='',updated=? WHERE id=? AND status='unpaid' AND attempts<?", (stamp,job_id,MAX_ATTEMPTS))
            db.execute('INSERT INTO payment_recovery_requests VALUES(?,?,?,?,?)', (owner,data['requestId'],order_id,job_id,stamp))
            self.log(db, self.job(db,job_id), 'request', owner, self.job(db,job_id)['status'])
            return job_id

    def claim(self, job_id, actor, *, claim_guard=None):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if claim_guard is not None:
                claim_guard(db)
            job = self.job(db, job_id)
            stamp = now()
            if job['status'] not in ('pending','retry','processing') or (job['status']=='retry' and job['next_attempt']>stamp) or (job['status']=='processing' and job['lease_until']>stamp):
                return None
            order = self.order(db,job['order_id'],job['owner'])
            status, code = None, ''
            if not self.owner_active(db,job['owner']):
                status,code = 'manual_review','account_closed'
            elif job['attempts']>=MAX_ATTEMPTS:
                status,code = 'manual_review','retry_exhausted'
            elif not job['receipt_id'] and order['payment_status'] in ('paid','partially_refunded','refunded'):
                status,code = ('confirmed','') if order['payment_status']=='paid' else ('manual_review','order_not_payable')
            elif not job['receipt_id'] and order['payment_status']=='refund_pending':
                status,code = 'manual_review','late_refund_pending'
            elif not job['receipt_id'] and not ((order['status']=='awaiting_payment' and order['payment_status']=='unpaid') or (order['status']=='closed' and order['payment_status']=='expired')):
                status,code = 'manual_review','order_not_payable'
            if status:
                db.execute("UPDATE payment_recovery_jobs SET status=?,lease_token='',lease_until=0,next_attempt=0,last_error=?,updated=? WHERE id=?", (status,code,stamp,job_id))
                self.log(db,job,'complete',actor,status,code)
                return None
            lease = str(uuid4())
            binding = job['query_binding'] if job['receipt_id'] else configuration_binding()
            changed = db.execute('''UPDATE payment_recovery_jobs SET status='processing',attempts=attempts+1,
                lease_token=?,lease_until=?,next_attempt=0,last_error='',updated=? WHERE id=? AND status=?
                AND attempts=? AND (status!='processing' OR lease_until<=?)''',
                (lease,stamp+LEASE_MS,stamp,job_id,job['status'],job['attempts'],stamp)).rowcount
            if changed!=1:
                return None
            db.execute('UPDATE payment_recovery_jobs SET query_binding=? WHERE id=? AND lease_token=?', (binding,job_id,lease))
            job = self.job(db,job_id)
            self.log(db,job,'claim',actor,'processing')
            return dict(job),dict(order),lease

    def fail_attempt(self, job_id, lease, actor, code, transient):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = self.current(db,job_id,lease)
            if job is None:
                return
            order = self.order(db,job['order_id'],job['owner'])
            if order['payment_status']=='paid' and not job['receipt_id']:
                status,code,due = 'confirmed','',0
            elif order['payment_status']=='refund_pending':
                status,code,due = 'manual_review','late_refund_pending',0
            elif order['payment_status'] in ('refunded','partially_refunded'):
                status,code,due = 'manual_review','order_not_payable',0
            else:
                retry = transient and job['attempts']<MAX_ATTEMPTS
                status,due = ('retry',now()+1000*2**(job['attempts']-1)) if retry else ('manual_review',0)
            if self.finish(db,job,lease,status,code,due):
                self.log(db,job,'complete',actor,status,code)

    def save_result(self, job_id, lease, actor, data, binding):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = self.current(db,job_id,lease,binding)
            if job is None:
                return None
            order = self.order(db,job['order_id'],job['owner'])
            if data['orderId']!=order['id'] or data['amountMinor']!=order['total_minor'] or data['currency']!=order['currency']:
                if self.finish(db,job,lease,'manual_review','query_mismatch'):
                    self.log(db,job,'complete',actor,'manual_review','query_mismatch')
                return None
            if data['state']=='paid':
                result = persist_verified_event(db, {'eventId':'query:'+job_id,'transactionId':data['transactionId'],
                    'orderId':order['id'],'type':'payment.succeeded','amountMinor':data['amountMinor'],'currency':data['currency']})
                if result['conflict']:
                    if self.finish(db,job,lease,'manual_review','receipt_conflict'):
                        self.log(db,job,'complete',actor,'manual_review','receipt_conflict')
                    return None
                changed = db.execute("UPDATE payment_recovery_jobs SET receipt_id=?,updated=? WHERE id=? AND status='processing' AND lease_token=? AND lease_until>? AND query_binding=?", (result['receiptId'],now(),job_id,lease,now(),binding)).rowcount
                if changed!=1:
                    raise sqlite3.IntegrityError('payment_recovery_stale')
                self.log(db,job,'query',actor,'paid')
                return result['receiptId']
            if order['payment_status']=='paid':
                status,code,due = 'confirmed','',0
            elif order['payment_status']=='refund_pending':
                status,code,due = 'manual_review','late_refund_pending',0
            elif order['payment_status'] in ('partially_refunded','refunded') or not ((order['status']=='awaiting_payment' and order['payment_status']=='unpaid') or (order['status']=='closed' and order['payment_status']=='expired')):
                status,code,due = 'manual_review','order_not_payable',0
            elif data['state']=='unpaid':
                status,code,due = 'unpaid','query_unpaid',0
            else:
                retry = job['attempts']<MAX_ATTEMPTS
                status,code,due = ('retry' if retry else 'manual_review'),'query_'+data['state'],now()+1000*2**(job['attempts']-1) if retry else 0
            if self.finish(db,job,lease,status,code,due):
                self.log(db,job,'complete',actor,status,code)
            return None

    def consume_receipt(self, job_id, lease, actor, owner, receipt_id, binding):
        if not binding or configuration_binding()!=binding:
            raise QueryFailure('adapter_disabled')
        callbacks = PaymentCallbacks(self.store,self.h,self.Error,self.rate)
        item = callbacks.process_receipt(receipt_id,actor,job_id=job_id,owner=owner,job_lease=lease,query_binding=binding)
        if item is None:
            return
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = self.current(db,job_id,lease,binding)
            if job is None:
                return
            if item['status']=='applied' and item['lastError']=='late_refund_pending':
                status,code,due = 'manual_review','late_refund_pending',0
            elif item['status']=='applied':
                status,code,due = 'confirmed','',0
            elif item['status']=='manual_review':
                status,code,due = 'manual_review',item['lastError'],0
            else:
                retry = job['attempts']<MAX_ATTEMPTS
                status,code,due = ('retry' if retry else 'manual_review'),item['lastError'] or 'receipt_processing',max(item['nextAttempt'],now()+1000*2**(job['attempts']-1)) if retry else 0
            if self.finish(db,job,lease,status,code,due):
                self.log(db,job,'complete',actor,status,code)

    def execute(self, job_id, actor, *, claim_guard=None):
        claimed = self.claim(job_id,actor,claim_guard=claim_guard)
        if claimed is None:
            return
        job,order,lease = claimed
        try:
            receipt = job['receipt_id']
            if not receipt:
                result = query_fixture(job,order)
                receipt = self.save_result(job_id,lease,actor,result,job['query_binding'])
            if receipt:
                self.consume_receipt(job_id,lease,actor,job['owner'],receipt,job['query_binding'])
        except QueryFailure as exc:
            self.fail_attempt(job_id,lease,actor,exc.code,exc.transient)
        except sqlite3.OperationalError:
            self.fail_attempt(job_id,lease,actor,'storage_unavailable',True)
        except sqlite3.IntegrityError as exc:
            if 'account_actor_' in str(exc) or 'account_settlement_' in str(exc):
                raise
            self.fail_attempt(job_id,lease,actor,'application_conflict',False)

    def process_batch(self, actor, data, *, claim_guard=None):
        limit = data.get('limit',1)
        if set(data)-{'limit'} or type(limit) is not int or not 1<=limit<=5:
            self.fail(400, '每次须处理1至5个任务。')
        with self.store.connect() as db:
            rows = db.execute("SELECT id FROM payment_recovery_jobs WHERE (status IN ('pending','retry') AND next_attempt<=?) OR (status='processing' AND lease_until<=?) ORDER BY created,id LIMIT ?",(now(),now(),limit)).fetchall()
        for row in rows:
            self.execute(row['id'],actor,claim_guard=claim_guard)
        with self.store.connect() as db:
            return {'items':[self.public_job(self.job(db,row['id'])) for row in rows],'processed':len(rows),'queryReady':configuration() is not None,'productionEnabled':False}

    def retry(self, db, job_id, actor, data):
        if data:
            self.fail(400, '重试请求不接受额外字段。')
        db.execute('BEGIN IMMEDIATE')
        job = self.job(db,job_id)
        if job['status'] not in ('retry','manual_review','unpaid') or job['attempts']>=MAX_ATTEMPTS or job['lease_until']>now():
            self.fail(409, '当前任务不能重试或已达到上限。')
        if not self.owner_active(db,job['owner']):
            self.fail(409, '该账号已关闭，不能重试。')
        db.execute("UPDATE payment_recovery_jobs SET status='retry',next_attempt=0,last_error='',lease_token='',lease_until=0,updated=? WHERE id=? AND status=? AND attempts<?", (now(),job_id,job['status'],MAX_ATTEMPTS))
        self.log(db,job,'retry',actor,'retry')
        return {'job':self.public_job(self.job(db,job_id)),'queryReady':configuration() is not None,'productionEnabled':False}

    def route(self, method, path):
        own = re.fullmatch(r'/api/commerce/orders/([A-Za-z0-9:_-]{1,100})/payment-recovery',path)
        admin = '/api/admin/payment-recovery'
        if own:
            actor = self.h.require()['id']
            self.rate('payment-recovery:'+('read:' if method=='GET' else 'write:')+actor,180 if method=='GET' else 30)
            if method=='POST':
                job_id = self.create(actor,own[1],self.h.body())
                self.execute(job_id,actor)
            elif method!='GET':
                self.fail(405, '不支持的支付恢复操作。')
            self.h.require()
            with self.store.connect() as db:
                order = self.order(db,own[1],actor)
                job = db.execute('SELECT * FROM payment_recovery_jobs WHERE owner=? AND order_id=?',(actor,own[1])).fetchone()
                return self.view(db,order,job)
        if path!=admin and not path.startswith(admin+'/'):
            return None
        actor = self.h.require(['admin'])['id']
        self.rate('payment-recovery:admin:'+('read:' if method=='GET' else 'write:')+actor,180 if method=='GET' else 30)
        if path==admin+'/process' and method=='POST':
            return self.process_batch(actor,self.h.body())
        with self.store.connect() as db:
            if path==admin and method=='GET':
                query = parse_qs(urlsplit(self.h.path).query)
                status,before = query.get('status',[''])[0],query.get('before',[''])[0]
                where,args = [],[]
                if status:
                    if status not in STATUSES:
                        self.fail(400, '任务状态无效。')
                    where.append('status=?'); args.append(status)
                if before:
                    row = self.job(db,before)
                    where.append('(created,id)<(?,?)'); args.extend((row['created'],row['id']))
                rows = db.execute('SELECT * FROM payment_recovery_jobs'+(' WHERE '+' AND '.join(where) if where else '')+' ORDER BY created DESC,id DESC LIMIT 26',args).fetchall()
                return {'items':[self.public_job(row) for row in rows[:25]],'next':rows[24]['id'] if len(rows)>25 else None,'queryReady':configuration() is not None,'productionEnabled':False}
            match = re.fullmatch(re.escape(admin)+r'/([A-Za-z0-9:_-]{1,100})(/retry)?',path)
            if match and match[2] and method=='POST':
                return self.retry(db,match[1],actor,self.h.body())
            if match and not match[2] and method=='GET':
                job = self.job(db,match[1])
                result = self.view(db,self.order(db,job['order_id'],job['owner']),job)
                result['attempts'] = [dict(id=row['id'],jobId=row['job_id'],attempt=row['attempt'],action=row['action'],actor=row['actor'],result=row['result'],errorCode=row['error_code'],created=row['created']) for row in db.execute('SELECT * FROM payment_recovery_attempts WHERE job_id=? ORDER BY created,id',(job['id'],))]
                return result
        self.fail(404, '找不到此支付恢复功能。')
