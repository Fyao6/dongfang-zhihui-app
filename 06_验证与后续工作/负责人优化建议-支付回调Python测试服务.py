"""Local PAY08 QA wrapper: real API and an authenticated, synthetic DB fault controller."""
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
assert qa_db.is_relative_to(ROOT / '06_验证与后续工作')
assert qa_db.name.startswith('负责人优化建议-支付回调隔离-')
assert args.resume == qa_db.exists(), 'Only an explicit resume may open this owned QA database'
assert len(os.environ.get('CALLBACK_TEST_TOKEN', '')) >= 32
spec = importlib.util.spec_from_file_location('pay08_actual_server', BACKEND / 'server.py')
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
actual.urlopen = lambda *a, **k: (_ for _ in ()).throw(actual.URLError('PAY08 QA blocks external HTTP'))
store = actual.Store(qa_db)
BaseHandler = actual.make_handler(store, ROOT / '03_当前APP')


def control(data):
    action = data.get('action')
    with sqlite3.connect(qa_db) as db:
        db.row_factory = sqlite3.Row
        if action == 'snapshot':
            oid, rid = data.get('orderId', ''), data.get('receiptId', '')
            order = db.execute('SELECT id,payment_status,status,total_minor,currency FROM commerce_orders WHERE id=?', (oid,)).fetchone()
            inbox = db.execute('SELECT * FROM payment_callback_inbox WHERE id=?', (rid,)).fetchone()
            return {
                'order': dict(order) if order else None,
                'inbox': dict(inbox) if inbox else None,
                'ledger': [dict(r) for r in db.execute('SELECT id,kind,amount_minor,status FROM commerce_payment_events WHERE order_id=? ORDER BY created,id', (oid,))],
                'entitlements': [dict(r) for r in db.execute('SELECT item_id,remaining,status FROM commerce_entitlements WHERE order_id=?', (oid,))],
                'inventory': [dict(r) for r in db.execute('SELECT s.id,s.stock,s.reserved,r.state FROM commerce_reservations r JOIN commerce_skus s ON s.id=r.sku_id WHERE r.order_id=? ORDER BY s.id', (oid,))],
                'inboxCount': db.execute('SELECT count(*) FROM payment_callback_inbox').fetchone()[0],
                'transactionsCount': db.execute('SELECT count(*) FROM payment_callback_transactions').fetchone()[0],
            }
        if action == 'gate':
            mode = data.get('mode')
            os.environ['EW_PAYMENT_CALLBACK_SANDBOX_ENABLED'] = '0' if mode == 'disabled' else '1'
            os.environ['EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF'] = 'INVALID_REF' if mode == 'invalid-ref' else 'EW_PAYMENT_CALLBACK_QA_SECRET'
            return {'changed': True}
        if action in ('fail-apply-on', 'fail-apply-off'):
            db.execute('CREATE TABLE IF NOT EXISTS callback_qa_faults(order_id TEXT PRIMARY KEY)')
            db.execute('DELETE FROM callback_qa_faults')
            if action == 'fail-apply-on':
                db.execute('INSERT INTO callback_qa_faults VALUES(?)', (data['orderId'],))
            db.execute('DROP TRIGGER IF EXISTS callback_qa_apply_fault')
            if action == 'fail-apply-on':
                db.execute("""CREATE TRIGGER callback_qa_apply_fault BEFORE INSERT ON commerce_payment_events
                    WHEN NEW.kind='sandbox_pay' AND EXISTS(SELECT 1 FROM callback_qa_faults WHERE order_id=NEW.order_id)
                    BEGIN SELECT pay08_fixture_transient_failure(); END""")
            return {'changed': True}
        if action in ('fail-receive-on', 'fail-receive-off'):
            db.execute('DROP TRIGGER IF EXISTS callback_qa_receive_fault')
            if action == 'fail-receive-on':
                db.execute('CREATE TRIGGER callback_qa_receive_fault BEFORE INSERT ON payment_callback_inbox BEGIN SELECT pay08_fixture_transient_failure(); END')
            return {'changed': True}
        if action == 'expire-order':
            db.execute('UPDATE commerce_orders SET reserved_until=0 WHERE id=?', (data['orderId'],))
        elif action == 'close-order':
            db.execute("UPDATE commerce_orders SET status='closed' WHERE id=?", (data['orderId'],))
        elif action == 'expired-lease':
            db.execute("UPDATE payment_callback_inbox SET status='processing',attempts=1,lease_token='abandoned-qa-lease',lease_until=?,next_attempt=0 WHERE id=?", (int(time.time()*1000)-1000, data['receiptId']))
        elif action == 'attempt-limit':
            db.execute("UPDATE payment_callback_inbox SET status='retry',attempts=4,lease_token='',lease_until=0,next_attempt=0 WHERE id=?", (data['receiptId'],))
        elif action == 'due':
            db.execute('UPDATE payment_callback_inbox SET next_attempt=0 WHERE id=?', (data['receiptId'],))
        else:
            raise ValueError('Unsupported QA action')
        return {'changed': True}


class Handler(BaseHandler):
    def do_POST(self):
        if self.path.split('?')[0] != '/__callback-test/control':
            return super().do_POST()
        supplied = self.headers.get('X-Callback-Test', '')
        if not hmac.compare_digest(supplied, os.environ['CALLBACK_TEST_TOKEN']):
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
print('APP: http://127.0.0.1:' + str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
