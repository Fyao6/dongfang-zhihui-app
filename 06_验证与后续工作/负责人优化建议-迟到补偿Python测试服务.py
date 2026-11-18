"""Late-payment actual local API wrapper. Authenticated fault controls touch only this owned synthetic DB."""
import argparse
import hmac
import importlib.util
import json
import os
import sqlite3
import sys
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(BACKEND))
parser = argparse.ArgumentParser()
parser.add_argument('--db', type=Path, required=True)
parser.add_argument('--port', type=int, default=0)
parser.add_argument('--resume', action='store_true')
args = parser.parse_args()
qa_db = args.db.resolve()
assert qa_db.is_relative_to(ROOT / '06_验证与后续工作') and qa_db.name.startswith('负责人优化建议-迟到补偿隔离-')
assert args.resume == qa_db.exists()
assert len(os.environ.get('RECOVERY_TEST_TOKEN', '')) >= 32
endpoint = os.environ.get('EW_PAYMENT_QUERY_SANDBOX_ENDPOINT', '')
query_secret = os.environ.get('EW_PAYMENT_QUERY_QA_SECRET', '')
spec = importlib.util.spec_from_file_location('late_actual_server', BACKEND / 'server.py')
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
store = actual.Store(qa_db)
BaseHandler = actual.make_handler(store, ROOT / '03_当前APP')


def control(data):
    action = data.get('action')
    with sqlite3.connect(qa_db) as db:
        db.row_factory = sqlite3.Row
        if action == 'snapshot':
            oid = data.get('orderId', '')
            order = db.execute('SELECT id,owner,payment_status,fulfillment_status,aftersale_status,status,total_minor,refunded_minor,currency FROM commerce_orders WHERE id=?', (oid,)).fetchone()
            job = db.execute('SELECT * FROM payment_recovery_jobs WHERE order_id=?', (oid,)).fetchone()
            inbox = db.execute('SELECT * FROM payment_callback_inbox WHERE id=?', (data.get('receiptId',''),)).fetchone()
            return {
                'order': dict(order) if order else None,
                'job': dict(job) if job else None,
                'inbox': dict(inbox) if inbox else None,
                'ledger': [dict(r) for r in db.execute('SELECT id,kind,request_id,amount_minor,status FROM commerce_payment_events WHERE order_id=? ORDER BY created,id', (oid,))],
                'entitlements': [dict(r) for r in db.execute('SELECT item_id,remaining,status FROM commerce_entitlements WHERE order_id=?', (oid,))],
                'inventory': [dict(r) for r in db.execute('SELECT s.id,s.stock,s.reserved,r.state,r.quantity FROM commerce_reservations r JOIN commerce_skus s ON s.id=r.sku_id WHERE r.order_id=? ORDER BY s.id', (oid,))],
                'callbacks': [dict(r) for r in db.execute('SELECT id,event_id,transaction_id,status,attempts FROM payment_callback_inbox WHERE order_id=? ORDER BY created,id', (oid,))],
                'lateCases': [dict(r) for r in db.execute('SELECT * FROM payment_late_cases WHERE order_id=?', (oid,))],
                'lateAttempts': [dict(r) for r in db.execute('SELECT a.* FROM payment_late_attempts a JOIN payment_late_cases c ON c.id=a.case_id WHERE c.order_id=? ORDER BY a.created,a.id', (oid,))],
                'jobsCount': db.execute('SELECT count(*) FROM payment_recovery_jobs').fetchone()[0],
                'inboxCount': db.execute('SELECT count(*) FROM payment_callback_inbox').fetchone()[0],
                'transactionsCount': db.execute('SELECT count(*) FROM payment_callback_transactions').fetchone()[0],
            }
        if action == 'gate':
            os.environ['EW_PAYMENT_CALLBACK_SANDBOX_ENABLED'] = '0' if data.get('mode') == 'disabled' else '1'
            os.environ['EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF'] = 'INVALID_REF' if data.get('mode') == 'invalid-ref' else 'EW_PAYMENT_CALLBACK_QA_SECRET'
            return {'changed': True}
        if action == 'query-config':
            mode = data.get('mode')
            if mode not in ('enabled', 'disabled', 'invalid-ref', 'host', 'query', 'userinfo', 'fragment', 'callback-disabled', 'rotated-secret'):
                raise ValueError('Unsupported config mode')
            os.environ['EW_PAYMENT_QUERY_SANDBOX_ENABLED'] = '0' if mode == 'disabled' else '1'
            os.environ['EW_PAYMENT_QUERY_SANDBOX_SECRET_REF'] = 'INVALID_REF' if mode == 'invalid-ref' else 'EW_PAYMENT_QUERY_QA_SECRET'
            value = endpoint
            if mode == 'host':
                value = endpoint.replace('127.0.0.1', 'localhost')
            elif mode == 'query':
                value += '?arbitrary=1'
            elif mode == 'userinfo':
                value = endpoint.replace('http://', 'http://username:password@')
            elif mode == 'fragment':
                value += '#part'
            os.environ['EW_PAYMENT_QUERY_SANDBOX_ENDPOINT'] = value
            os.environ['EW_PAYMENT_CALLBACK_SANDBOX_ENABLED'] = '0' if mode == 'callback-disabled' else '1'
            os.environ['EW_PAYMENT_QUERY_QA_SECRET'] = query_secret+'-rotated-qa' if mode == 'rotated-secret' else query_secret
            return {'changed': True}
        if action in ('fail-apply-on', 'fail-apply-off'):
            db.execute('DROP TRIGGER IF EXISTS recovery_qa_apply_fault')
            if action == 'fail-apply-on':
                db.execute("CREATE TRIGGER recovery_qa_apply_fault BEFORE INSERT ON commerce_payment_events WHEN NEW.kind='sandbox_pay' BEGIN SELECT pay09_fixture_transient_failure(); END")
            return {'changed': True}
        if action in ('fail-late-on', 'fail-late-off', 'fail-receive-on', 'fail-receive-off'):
            name = 'late_qa_case_fault' if action.startswith('fail-late') else 'late_qa_receive_fault'
            table = 'payment_late_cases' if action.startswith('fail-late') else 'payment_callback_inbox'
            db.execute('DROP TRIGGER IF EXISTS '+name)
            if action.endswith('-on'):
                db.execute('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT late_fixture_transient_failure(); END')
            return {'changed': True}
        if action == 'expire-order':
            db.execute('UPDATE commerce_orders SET reserved_until=0 WHERE id=?', (data['orderId'],))
        elif action == 'close-order':
            db.execute("UPDATE commerce_orders SET status='closed' WHERE id=?", (data['orderId'],))
        elif action == 'expired-lease':
            if data.get('receiptId'):
                db.execute("UPDATE payment_callback_inbox SET status='processing',attempts=1,lease_token='abandoned-qa-lease',lease_until=?,next_attempt=0 WHERE id=?", (int(time.time()*1000)-1000, data['receiptId']))
            else:
                db.execute("UPDATE payment_recovery_jobs SET lease_until=?,next_attempt=0 WHERE id=?", (int(time.time()*1000)-1000, data['jobId']))
        elif action == 'attempt-limit':
            if data.get('receiptId'):
                db.execute("UPDATE payment_callback_inbox SET status='retry',attempts=4,lease_token='',lease_until=0,next_attempt=0 WHERE id=?", (data['receiptId'],))
            else:
                db.execute("UPDATE payment_recovery_jobs SET status='retry',attempts=4,lease_token='',lease_until=0,next_attempt=0 WHERE id=?", (data['jobId'],))
        elif action == 'due':
            db.execute('UPDATE payment_recovery_jobs SET next_attempt=0 WHERE id=?', (data['jobId'],))
            job = db.execute('SELECT receipt_id FROM payment_recovery_jobs WHERE id=?', (data['jobId'],)).fetchone()
            if job and job['receipt_id']:
                db.execute('UPDATE payment_callback_inbox SET next_attempt=0 WHERE id=?', (job['receipt_id'],))
        else:
            raise ValueError('Unsupported QA action')
        return {'changed': True}


class Handler(BaseHandler):
    def do_POST(self):
        route = self.path.split('?')[0]
        if route not in ('/__recovery-test/control', '/__callback-test/control', '/__late-test/control'):
            return super().do_POST()
        header = 'X-Callback-Test' if route=='/__callback-test/control' else 'X-Late-Test' if route=='/__late-test/control' else 'X-Recovery-Test'
        if not hmac.compare_digest(self.headers.get(header, ''), os.environ['RECOVERY_TEST_TOKEN']):
            return self.send(403, {'error': 'QA control token required'})
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 4096:
            return self.send(413, {'error': 'QA request too large'})
        try:
            result = control(json.loads(self.rfile.read(length)))
        except (ValueError, KeyError, sqlite3.Error):
            return self.send(400, {'error': 'Invalid isolated QA control'})
        return self.send(200, {'isolated': True, **result})


server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
print('APP: http://127.0.0.1:'+str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
