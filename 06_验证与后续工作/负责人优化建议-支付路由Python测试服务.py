"""Digital rights actual API/media server; controls are limited to this newly owned synthetic DB."""
import argparse
import hmac
import importlib.util
import json
import os
import sqlite3
import sys
import time
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(BACKEND))
parser = argparse.ArgumentParser()
parser.add_argument('--db', type=Path, required=True)
parser.add_argument('--port', type=int, default=0)
parser.add_argument('--resume', action='store_true')
args = parser.parse_args()
qa_db = args.db.resolve()
assert qa_db.parent == ROOT / '06_验证与后续工作' and qa_db.name.startswith('负责人优化建议-支付路由隔离-')
assert qa_db.is_file()  # The actual bootstrap CLI has exclusively created this new owned marker DB.
assert len(os.environ.get('RECOVERY_TEST_TOKEN', '')) >= 32
endpoint = os.environ.get('EW_PAYMENT_QUERY_SANDBOX_ENDPOINT', '')
query_secret = os.environ.get('EW_PAYMENT_QUERY_QA_SECRET', '')
spec = importlib.util.spec_from_file_location('privacy_domains_actual_server', BACKEND / 'server.py')
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
import ai_gateway
provider_endpoint = os.environ['PRIVACY_DOMAINS_PROVIDER_ENDPOINT']
assert urlsplit(provider_endpoint).hostname == '127.0.0.1' and urlsplit(provider_endpoint).path == '/privacy-domains-fixture'
provider_urls = {'https://alpha.domains.invalid/v1/responses':'/alpha/responses',
                 'https://beta.domains.invalid/v1/messages':'/beta/messages',
                 'https://alpha.gateway.invalid/v1/responses':'/alpha/responses',
                 'https://beta.gateway.invalid/v1/messages':'/beta/messages',
                 'https://legacy.domains.invalid/v1/responses':'/legacy/responses'}
native_transport = ai_gateway.AIGateway.transport


def mapped_transport(self, provider, payload, deadline):
    suffix = provider_urls.get(provider['endpoint'])
    if suffix is None:
        raise ai_gateway.GatewayFailure('qa_unconfigured_endpoint')
    # Only the exact endpoint changes. Native product headers, payload, timeout and redirect handling execute.
    return native_transport(self, {**provider,'endpoint':provider_endpoint+suffix}, payload, deadline)


ai_gateway.AIGateway.transport = mapped_transport
native_urlopen = actual.urlopen


def mapped_legacy_urlopen(request, *values, **options):
    suffix = provider_urls.get(request.full_url if hasattr(request,'full_url') else str(request))
    if suffix is None:
        raise actual.URLError('QA blocks unrelated external HTTP')
    mapped = Request(provider_endpoint+suffix, data=request.data, headers=dict(request.header_items()), method=request.get_method())
    return native_urlopen(mapped, *values, **options)


actual.urlopen = mapped_legacy_urlopen
import digital_entitlements
import privacy_domains
clock_lock = threading.RLock()
clock_state = {'base': None, 'started': time.monotonic()}
real_clock = digital_entitlements.now


def qa_clock():
    with clock_lock:
        base, elapsed = clock_state['base'], int((time.monotonic()-clock_state['started'])*1000)
    return real_clock() if base is None else base+elapsed


digital_entitlements.now = qa_clock
domain_clock_state = {'base': None, 'started': time.monotonic()}
real_domain_clock = privacy_domains.now


def qa_domain_clock():
    with clock_lock:
        base, elapsed = domain_clock_state['base'], int((time.monotonic()-domain_clock_state['started'])*1000)
    return real_domain_clock() if base is None else base+elapsed


privacy_domains.now = qa_domain_clock
routing_spec = importlib.util.spec_from_file_location('owned_routing_control', Path(__file__).with_name('负责人优化建议-支付路由夹具控制.py'))
routing_module = importlib.util.module_from_spec(routing_spec)
routing_spec.loader.exec_module(routing_module)
routing_module.install_hooks(actual)
routing_module.seed_legacy(qa_db, args.resume)

store = actual.Store(qa_db)
BaseHandler = actual.make_handler(store, ROOT / '03_当前APP')
fixture_spec = importlib.util.spec_from_file_location('owned_task_old_privacy_fixture', Path(__file__).with_name('负责人优化建议-支付路由隐私夹具控制.py'))
fixture_module = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture_module)



def control(data):
    routing_result = routing_module.handle(qa_db, data)
    if routing_result is not None:
        return routing_result
    domain_result = fixture_module.handle(qa_db, data)
    if domain_result is not None:
        return domain_result
    action = data.get('action')
    if action == 'domain-clock':
        value = data.get('nowMs')
        if value is not None and (type(value) is not int or not 0 < value < 4_000_000_000_000):
            raise ValueError('Invalid owned privacy test clock')
        with clock_lock:
            domain_clock_state.update(base=value, started=time.monotonic())
        return {'clockOverride': value, 'clockAdvancesWithRealElapsed': True}
    if action == 'clock':
        value = data.get('nowMs')
        if value is not None and (type(value) is not int or not 0 < value < 4_000_000_000_000):
            raise ValueError('Invalid owned test clock')
        with clock_lock:
            clock_state.update(base=value, started=time.monotonic())
        return {'clockOverride': value, 'clockAdvancesWithRealElapsed': True}
    with sqlite3.connect(qa_db) as db:
        db.row_factory = sqlite3.Row
        if action == 'digital-snapshot':
            owner, oid = data.get('owner',''), data.get('orderId','')
            return {
                'grants': [dict(r) for r in db.execute('SELECT * FROM digital_entitlement_grants WHERE owner=? OR order_id=? ORDER BY id',(owner,oid))],
                'snapshots': [dict(r) for r in db.execute('SELECT * FROM digital_order_snapshots WHERE owner=? OR order_id=? ORDER BY item_id',(owner,oid))],
                'leases': [dict(r) for r in db.execute('SELECT id,owner,grant_id,request_id,created,expires FROM digital_access_leases WHERE owner=? OR grant_id IN (SELECT id FROM digital_entitlement_grants WHERE order_id=?) ORDER BY id',(owner,oid))],
                'uses': [dict(r) for r in db.execute('SELECT * FROM digital_entitlement_uses WHERE owner=? OR grant_id IN (SELECT id FROM digital_entitlement_grants WHERE order_id=?) ORDER BY id',(owner,oid))],
                'assets': [dict(r) for r in db.execute('SELECT * FROM digital_sandbox_assets ORDER BY media_id')],
                'order': [dict(r) for r in db.execute('SELECT id,payment_status,status,refunded_minor FROM commerce_orders WHERE id=?',(oid,))],
                'legacy': [dict(r) for r in db.execute('SELECT * FROM commerce_entitlements WHERE owner=? OR order_id=? ORDER BY id',(owner,oid))],
                'ledger': [dict(r) for r in db.execute('SELECT id,kind,amount_minor FROM commerce_payment_events WHERE order_id=? ORDER BY id',(oid,))],
            }
        if action in ('digital-fail-grant-on','digital-fail-grant-off','digital-fail-lease-on','digital-fail-lease-off'):
            grant = 'grant' in action
            name = 'digital_qa_grant_fault' if grant else 'digital_qa_lease_fault'
            db.execute('DROP TRIGGER IF EXISTS '+name)
            if action.endswith('-on'):
                table = 'digital_entitlement_grants' if grant else 'digital_entitlement_uses'
                db.execute('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT sh06_fixture_storage_failure(); END')
            return {'changed': True}
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
        if route not in ('/__routing-test/control','/__privacy-domains-test/control','/__digital-test/control','/__recovery-test/control', '/__callback-test/control', '/__late-test/control'):
            return super().do_POST()
        header = 'X-Routing-Test' if route=='/__routing-test/control' else 'X-Privacy-Domains-Test' if route=='/__privacy-domains-test/control' else 'X-Digital-Test' if route=='/__digital-test/control' else 'X-Callback-Test' if route=='/__callback-test/control' else 'X-Late-Test' if route=='/__late-test/control' else 'X-Recovery-Test'
        expected = os.environ['ROUTING_TEST_TOKEN'] if route=='/__routing-test/control' else os.environ['PRIVACY_DOMAINS_TEST_TOKEN'] if route=='/__privacy-domains-test/control' else os.environ['DIGITAL_TEST_TOKEN'] if route=='/__digital-test/control' else os.environ['CALLBACK_TEST_TOKEN'] if route=='/__callback-test/control' else os.environ['RECOVERY_TEST_TOKEN']
        if not hmac.compare_digest(self.headers.get(header, ''), expected):
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
