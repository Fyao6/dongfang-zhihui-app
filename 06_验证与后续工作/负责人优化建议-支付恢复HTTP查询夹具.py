"""Independent signed PAY09 HTTP fixture. Synthetic local protocol, never a real payment provider."""
import argparse
import hashlib
import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

secret = os.environ['EW_PAYMENT_QUERY_QA_SECRET']
control_token = os.environ['RECOVERY_TEST_TOKEN']
assert len(secret) >= 32 and len(control_token) >= 32
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=0)
args = parser.parse_args()
lock = threading.Lock()
policies, releases, calls, rejections = {}, {}, [], []
ALLOWED = {'paid', 'unpaid', 'pending', 'not_found', 'failed', 'timeout', 'http500', 'malformed',
           'oversize', 'redirect', 'bad-signature', 'expired-signature', 'mismatch-order',
           'mismatch-query', 'mismatch-amount', 'mismatch-currency', 'extra-field', 'hold'}


def encode(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_raw(self, status, raw, signature=True, expired=False, headers=None):
        stamp = str(int(time.time()) - (601 if expired else 0))
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        if signature:
            self.send_header('X-EW-Query-Timestamp', stamp)
            self.send_header('X-EW-Query-Signature', hmac.new(secret.encode(), stamp.encode()+b'.'+raw, hashlib.sha256).hexdigest())
        else:
            self.send_header('X-EW-Query-Timestamp', stamp)
            self.send_header('X-EW-Query-Signature', '0'*64)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == '/pay09-fixture/redirect-target':
            with lock:
                calls.append({'mode': 'redirect-target', 'verified': False})
            return self.send_raw(200, encode({'unexpected': 'redirect was followed'}))
        return self.send_raw(404, encode({'error': 'fixture route not found'}))

    def do_POST(self):
        length = self.headers.get('Content-Length', '')
        if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
            chunks = bytearray()
            try:
                while True:
                    line = self.rfile.readline(128)
                    size = int(line.split(b';', 1)[0].strip(), 16)
                    if size == 0:
                        while self.rfile.readline(8192).strip():
                            pass
                        break
                    if not 0 < size <= 8192-len(chunks):
                        raise ValueError('body too large')
                    part = self.rfile.read(size)
                    if len(part) != size or self.rfile.read(2) != b'\r\n':
                        raise ValueError('invalid chunk')
                    chunks.extend(part)
                raw = bytes(chunks)
            except (ValueError, OSError):
                raw = None
        elif length.isdigit() and 0 < int(length) <= 8192:
            raw = self.rfile.read(int(length))
        else:
            raw = None
        if not raw:
            with lock:
                rejections.append({'reason': 'body_framing'})
            return self.send_raw(413, b'{}')
        if self.path == '/pay09-fixture/control':
            if not hmac.compare_digest(self.headers.get('X-Recovery-Test', ''), control_token):
                return self.send_raw(403, b'{}')
            try:
                data = json.loads(raw)
                action = data.get('action')
                if action == 'configure':
                    oid, mode = data['orderId'], data['mode']
                    if mode not in ALLOWED:
                        raise ValueError('Unsupported mode')
                    with lock:
                        policies[oid] = {'mode': mode, 'transactionId': data.get('transactionId', 'fixture:'+oid), 'heldState': data.get('heldState', 'pending')}
                        if mode == 'hold':
                            releases[oid] = threading.Event()
                    result = {'configured': True}
                elif action == 'release':
                    with lock:
                        event = releases.get(data['orderId'])
                    if event:
                        event.set()
                    result = {'released': event is not None}
                elif action == 'stats':
                    with lock:
                        selected = [dict(call) for call in calls if not data.get('orderId') or call.get('orderId') == data['orderId']]
                    result = {'calls': selected, 'rejections': list(rejections)}
                else:
                    raise ValueError('Unsupported control')
            except (KeyError, ValueError, TypeError):
                return self.send_raw(400, b'{}')
            return self.send_raw(200, encode({'isolated': True, **result}))
        if self.path != '/pay09-fixture/query':
            return self.send_raw(404, b'{}')
        stamp, signature = self.headers.get('X-EW-Query-Timestamp', ''), self.headers.get('X-EW-Query-Signature', '')
        expected = hmac.new(secret.encode(), stamp.encode()+b'.'+raw, hashlib.sha256).hexdigest()
        verified = stamp.isdigit() and abs(int(stamp)-int(time.time())) <= 300 and hmac.compare_digest(expected, signature)
        try:
            data = json.loads(raw)
            if not verified or set(data) != {'queryId', 'orderId', 'amountMinor', 'currency'}:
                raise ValueError('Invalid signed query')
            oid = data['orderId']
        except (ValueError, TypeError):
            with lock:
                rejections.append({'reason': 'request_signature_or_shape'})
            return self.send_raw(401, b'{}')
        with lock:
            policy = dict(policies.get(oid, {'mode': 'pending', 'transactionId': 'fixture:'+oid}))
            mode = policy['mode']
            if mode == 'hold':
                releases[oid] = threading.Event()
            calls.append({'queryId': data['queryId'], 'orderId': oid, 'amountMinor': data['amountMinor'], 'currency': data['currency'], 'mode': mode, 'verified': True})
            held = releases.get(oid)
        if mode == 'timeout':
            time.sleep(9)
        if mode == 'hold' and held:
            held.wait(12)
        state = policy.get('heldState', 'pending') if mode == 'hold' else mode if mode in ('paid', 'unpaid', 'pending', 'not_found', 'failed') else 'paid'
        response = {'queryId': data['queryId'], 'orderId': oid, 'state': state,
                    'transactionId': policy['transactionId'] if state == 'paid' else '',
                    'amountMinor': data['amountMinor'], 'currency': data['currency']}
        if mode == 'http500':
            return self.send_raw(500, encode({'error': 'synthetic temporary outage'}))
        if mode == 'redirect':
            return self.send_raw(302, b'{}', headers={'Location': '/pay09-fixture/redirect-target'})
        if mode == 'malformed':
            return self.send_raw(200, b'{"state":')
        if mode == 'oversize':
            return self.send_raw(200, b' '*8193)
        if mode == 'mismatch-order':
            response['orderId'] = 'other-order'
        if mode == 'mismatch-query':
            response['queryId'] = 'other-query'
        if mode == 'mismatch-amount':
            response['amountMinor'] += 1
        if mode == 'mismatch-currency':
            response['currency'] = 'USD' if data['currency'] != 'USD' else 'CNY'
        if mode == 'extra-field':
            response['ownerId'] = 'do-not-trust-provider-extra-fields'
        return self.send_raw(200, encode(response), signature=mode!='bad-signature', expired=mode=='expired-signature')


server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
print('QUERY_FIXTURE: http://127.0.0.1:'+str(server.server_port)+'/pay09-fixture/query', flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
