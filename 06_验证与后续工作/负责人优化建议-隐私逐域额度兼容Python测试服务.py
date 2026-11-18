"""Owned SQLite QA server; real product accounting and independent HTTP/SSE fixture."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

root = Path(__file__).resolve().parents[1]
backend = root / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(backend))
import commerce
import membership_lifecycle as membership
import membership_ai_quota as quota
import ai_gateway as gateway

parser = argparse.ArgumentParser()
parser.add_argument('--db', type=Path, required=True)
args = parser.parse_args()
token = os.environ['MEMBER_QUOTA_TEST_TOKEN']
endpoint = os.environ['MEMBER_QUOTA_FIXTURE_ENDPOINT']
secret = os.environ['MEMBER_QUOTA_PROVIDER_SECRET']
assert len(token) >= 32 and len(secret) >= 32
assert not args.db.exists() and args.db.name.startswith('负责人优化建议-隐私逐域额度兼容隔离-')
assert args.db.resolve().is_relative_to(root / '06_验证与后续工作')
assert urlsplit(endpoint).hostname == '127.0.0.1' and urlsplit(endpoint).path == '/member-quota-fixture'
with sqlite3.connect(args.db) as db:
    db.executescript(Path(__file__).with_name('负责人优化建议-隐私逐域额度兼容旧库夹具.sql').read_text(encoding='utf-8'))

lock = threading.RLock()
release = threading.Event()
control = {'nowMs': None, 'clockStarted': time.monotonic(), 'pauseOrderId': None, 'entered': False, 'failOrderId': None, 'failCount': 0}
real_clock = gateway.now


def clock():
    with lock:
        value = control['nowMs']
        elapsed = int((time.monotonic() - control['clockStarted']) * 1000)
    return real_clock() if value is None else value + elapsed


commerce.now = membership.now = quota.now = gateway.now = clock
original_pay = commerce.Commerce.pay


def paused_pay(self, oid, data):
    with lock:
        pause = control['pauseOrderId'] == oid
        if pause:
            control['entered'] = True
            control['pauseOrderId'] = None
    if pause:
        release.wait(20)
    return original_pay(self, oid, data)


commerce.Commerce.pay = paused_pay
original_callback = membership.Membership.on_commerce_payment


def interrupted_callback(self, db, oid):
    with lock:
        fail = control['failOrderId'] == oid and control['failCount'] > 0
        if fail:
            control['failCount'] -= 1
    if fail:
        raise RuntimeError('QA_ONLY_MEMBERSHIP_CALLBACK_INTERRUPTED')
    return original_callback(self, db, oid)


membership.Membership.on_commerce_payment = interrupted_callback


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def transport(provider, payload, deadline):
    allowed = {'https://alpha.gateway.invalid/v1/responses': '/alpha/responses',
               'https://beta.gateway.invalid/v1/messages': '/beta/messages'}
    if provider['endpoint'] not in allowed:
        raise gateway.GatewayFailure('qa_unconfigured_endpoint')
    headers = {'Content-Type': 'application/json'}
    headers['X-Api-Key' if provider['authMode'] == 'x-api-key' else 'Authorization'] = secret if provider['authMode'] == 'x-api-key' else 'Bearer ' + secret
    request = Request(endpoint + allowed[provider['endpoint']], data=json.dumps(payload, ensure_ascii=False).encode(), headers=headers, method='POST')
    try:
        return build_opener(NoRedirect).open(request, timeout=max(1, min(25, (deadline - clock()) / 1000)))
    except HTTPError as error:
        raise gateway.GatewayFailure('upstream_http_' + str(error.code), error.code >= 500) from error
    except URLError as error:
        raise gateway.GatewayFailure('upstream_transport_error', True) from error


original_init = gateway.AIGateway.__init__


def injected_init(self, *values, **options):
    options['test_transport'] = transport
    options['test_secret_resolver'] = lambda ref: secret if ref in ('EW_AI_GATEWAY_QA_ALPHA', 'EW_AI_GATEWAY_QA_BETA') else ''
    original_init(self, *values, **options)


gateway.AIGateway.__init__ = injected_init
spec = importlib.util.spec_from_file_location('member_quota_actual_server', backend / 'server.py')
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
actual.urlopen = lambda *_a, **_k: (_ for _ in ()).throw(actual.URLError('QA blocks unrelated external HTTP'))
store = actual.Store(args.db)
base_handler = actual.make_handler(store, root / '03_当前APP')


class Handler(base_handler):
    def monitor(self):
        if self.headers.get('X-Member-Quota-Test') != token:
            return self.send(403, {'error': 'test token required'})
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 8192:
            return self.send(400, {'error': 'invalid control'})
        data = json.loads(self.rfile.read(length))
        with lock:
            if 'nowMs' in data:
                assert data['nowMs'] is None or type(data['nowMs']) is int and 0 < data['nowMs'] < 4_000_000_000_000
                control['nowMs'] = data['nowMs']
                control['clockStarted'] = time.monotonic()
            if 'pauseOrderId' in data:
                control['pauseOrderId'] = data['pauseOrderId']
                control['entered'] = False
                release.clear()
            if data.get('release'):
                release.set()
            if 'failOrderId' in data:
                control['failOrderId'] = data['failOrderId']
                control['failCount'] = int(data.get('failCount', 1))
        with store.connect() as db:
            if data.get('action') == 'fail-allocation':
                db.execute('DROP TRIGGER IF EXISTS member_quota_qa_failure')
                if data.get('enabled'):
                    db.execute("CREATE TRIGGER member_quota_qa_failure BEFORE INSERT ON membership_ai_allocations BEGIN SELECT member_quota_nonexistent_function(); END")
            if data.get('action') == 'expire-job':
                db.execute("UPDATE ai_gateway_jobs SET lease_until=0 WHERE id=? AND owner=? AND status IN ('queued','running')", (data['jobId'], data['owner']))
            value = {'isolated': True, 'externalProviderTested': False, 'syntheticDataOnly': True,
                     'clockOverride': control['nowMs'], 'entered': control['entered'],
                     'callbackFailuresRemaining': control['failCount'], 'barrierPosition': 'before-original-python-pay-transaction'}
            if data.get('action') in ('snapshot', 'migration'):
                owner = data.get('owner', 'quota_migration_canary')
                value.update({
                    'wallets': [dict(r) for r in db.execute('SELECT * FROM ai_gateway_wallets WHERE owner=?', (owner,))],
                    'jobs': [dict(r) for r in db.execute('SELECT id,request_id,status,reserve_credits,charged_credits,quota_source,quota_period_id AS period_id FROM ai_gateway_jobs WHERE owner=? ORDER BY id', (owner,))],
                    'legacyEvents': [dict(r) for r in db.execute('SELECT * FROM ai_gateway_quota_events WHERE owner=? ORDER BY id', (owner,))],
                    'grants': [dict(r) for r in db.execute('SELECT * FROM ai_gateway_grants WHERE owner=? ORDER BY id', (owner,))],
                    'periods': [dict(r) for r in db.execute('SELECT * FROM membership_ai_periods WHERE owner=? ORDER BY cycle_start,id', (owner,))],
                    'allocations': [dict(r) for r in db.execute('SELECT * FROM membership_ai_allocations WHERE owner=? ORDER BY job_id', (owner,))],
                    'events': [dict(r) for r in db.execute('SELECT * FROM membership_ai_events WHERE owner=? ORDER BY created,id', (owner,))]})
        return self.send(200, value)

    def do_POST(self):
        if urlsplit(self.path).path == '/__member-quota-test/control':
            return self.monitor()
        return super().do_POST()


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
server.daemon_threads = True
print('APP: http://127.0.0.1:' + str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    release.set()
    server.server_close()
