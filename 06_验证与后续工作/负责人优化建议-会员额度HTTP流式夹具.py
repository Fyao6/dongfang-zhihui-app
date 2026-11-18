"""Independent loopback HTTP/SSE provider fixture. No quota math or prompt logging."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ['MEMBER_QUOTA_TEST_TOKEN']
SECRET = os.environ['MEMBER_QUOTA_PROVIDER_SECRET']
assert len(TOKEN) >= 32 and len(SECRET) >= 32
lock = threading.RLock()
state = {'mode': 'success', 'calls': [], 'held': [], 'redirectFollowed': 0}


def frame(kind, data):
    return ('event: ' + kind + '\ndata: ' + json.dumps(data, ensure_ascii=False) + '\n\n').encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass

    def reply(self, code, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
            parts, size = [], 0
            while True:
                count = int(self.rfile.readline(100).split(b';', 1)[0], 16)
                if not count:
                    self.rfile.readline(100)
                    break
                size += count
                if size > 200_000:
                    raise ValueError('oversize')
                parts.append(self.rfile.read(count))
                if self.rfile.read(2) != b'\r\n':
                    raise ValueError('invalid chunk')
            return b''.join(parts)
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 200_000:
            raise ValueError('invalid length')
        return self.rfile.read(length)

    def do_GET(self):
        if self.path == '/member-quota-fixture/redirect-target':
            with lock:
                state['redirectFollowed'] += 1
            return self.reply(409, {'error': 'redirect trap must never be followed'})
        if self.path != '/member-quota-fixture/control' or self.headers.get('X-Member-Quota-Test') != TOKEN:
            return self.reply(404, {'error': 'not found'})
        with lock:
            self.reply(200, {'isolated': True, 'realSupplier': False, 'promptLogging': False,
                             'mode': state['mode'], 'calls': list(state['calls']),
                             'held': sum(not x.is_set() for x in state['held']), 'redirectFollowed': state['redirectFollowed']})

    def do_POST(self):
        if self.path == '/member-quota-fixture/control':
            if self.headers.get('X-Member-Quota-Test') != TOKEN:
                return self.reply(403, {'error': 'test token required'})
            try:
                data = json.loads(self.body())
                with lock:
                    if 'mode' in data:
                        assert data['mode'] in ('success', 'primary-fails', 'redirect', 'partial', 'no-usage', 'hold', 'hold-before-first')
                        state['mode'] = data['mode']
                    if data.get('release'):
                        for gate in state['held']:
                            gate.set()
                return self.do_GET()
            except (AssertionError, ValueError, KeyError):
                return self.reply(400, {'error': 'invalid fixture control'})
        if self.path not in ('/member-quota-fixture/alpha/responses', '/member-quota-fixture/beta/messages'):
            return self.reply(404, {'error': 'not found'})
        if self.headers.get('Authorization') != 'Bearer ' + SECRET and self.headers.get('X-Api-Key') != SECRET:
            return self.reply(401, {'error': 'synthetic fixture authentication required'})
        try:
            payload = json.loads(self.body())
            assert payload.get('stream') is True
        except (ValueError, AssertionError):
            return self.reply(400, {'error': 'invalid fixture request'})
        provider = 'alpha' if '/alpha/' in self.path else 'beta'
        serialized = json.dumps(payload, ensure_ascii=False)
        with lock:
            mode = state['mode']
            sequence = len(state['calls']) + 1
            state['calls'].append({'sequence': sequence, 'providerId': provider,
                                   'protocol': 'responses' if provider == 'alpha' else 'anthropic_messages',
                                   'payloadChars': len(serialized), 'privacyTagsPresent': 'consentEpoch' in serialized,
                                   'forbiddenLegacyPresent': 'GW_LEGACY_PRIVATE_CANARY' in serialized,
                                   'forbiddenBirthPresent': 'GW_LOCAL_BIRTH_CANARY' in serialized})
            gate = threading.Event()
            if mode in ('hold', 'hold-before-first'):
                state['held'].append(gate)
        if mode == 'primary-fails' and provider == 'alpha':
            return self.reply(503, {'error': 'synthetic provider unavailable'})
        if mode == 'redirect':
            self.send_response(302)
            self.send_header('Location', 'http://127.0.0.1:' + str(self.server.server_port) + '/member-quota-fixture/redirect-target')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('request-id', 'MEMBER_QUOTA_HTTP_FIXTURE_' + str(sequence))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        if mode == 'hold-before-first':
            gate.wait(20)
        if provider == 'alpha':
            initial = [frame('response.output_text.delta', {'type': 'response.output_text.delta', 'delta': 'AG_LOCAL_MOCK_甲'})]
            final = [frame('response.completed', {'type': 'response.completed', 'response': {} if mode == 'no-usage' else {'usage': {'input_tokens': 7, 'output_tokens': 3}}})]
        else:
            initial = [frame('message_start', {'type': 'message_start', 'message': {} if mode == 'no-usage' else {'usage': {'input_tokens': 7}}}),
                       frame('content_block_delta', {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': 'AG_LOCAL_MOCK_乙'}})]
            final = [frame('message_delta', {'type': 'message_delta', **({} if mode == 'no-usage' else {'usage': {'output_tokens': 3}})}),
                     frame('message_stop', {'type': 'message_stop'})]
        try:
            for value in initial:
                self.wfile.write(value)
                self.wfile.flush()
            if mode == 'hold':
                gate.wait(20)
            if mode != 'partial':
                for value in final:
                    self.wfile.write(value)
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
server.daemon_threads = True
print('MEMBER_QUOTA_FIXTURE: http://127.0.0.1:' + str(server.server_port) + '/member-quota-fixture', flush=True)
try:
    server.serve_forever()
finally:
    with lock:
        for gate in state['held']:
            gate.set()
    server.server_close()
