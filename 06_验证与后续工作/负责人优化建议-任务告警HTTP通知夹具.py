"""Owned durable loopback receiver. It validates signed bytes; it never runs task logic."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import UUID

parser = argparse.ArgumentParser()
parser.add_argument('--db', type=Path, required=True)
parser.add_argument('--port', type=int, default=0)
parser.add_argument('--host', choices=('127.0.0.1', '::1'), default='127.0.0.1')
parser.add_argument('--resume', action='store_true')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parent
DB = args.db.resolve()
assert DB.parent == ROOT and DB.name.startswith('负责人优化建议-任务告警接收夹具-')
assert args.resume == DB.is_file(), 'Receiver uses only its explicit newly owned or resumed file'
if not args.resume:
    with DB.open('xb'):
        pass
TOKEN = os.environ['TASK_ALERT_TEST_TOKEN']
SECRET = os.environ['TASK_ALERT_NOTIFICATION_SECRET']
assert len(TOKEN) >= 32 and 32 <= len(SECRET) <= 500
LOCK = threading.RLock()
HOLDS = {}
FIELDS = {'eventId', 'alertId', 'episode', 'ruleCode', 'severity', 'sourceType', 'sourceId', 'observedAt', 'environment'}
MODES = {'ok', 'ok_charset', 'drop_after_accept', 'http500', 'redirect', 'timeout_after_accept', 'hold_after_accept',
         'bad_signature', 'unsigned', 'expired_timestamp', 'future_timestamp', 'wrong_event', 'accepted_false',
         'accepted_integer', 'accepted_string', 'extra_key', 'bad_json', 'duplicate_key', 'nonfinite', 'invalid_utf8',
         'oversize', 'oversize_chunked', 'bad_content_type', 'bad_charset', 'array_ack', 'status202', 'status204'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def exact_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def strict_json(raw):
    return json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=exact_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=15)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


with connect() as db:
    db.executescript('''
      CREATE TABLE IF NOT EXISTS receiver_config(id INTEGER PRIMARY KEY CHECK(id=1),mode TEXT NOT NULL);
      INSERT OR IGNORE INTO receiver_config VALUES(1,'ok');
      CREATE TABLE IF NOT EXISTS receiver_events(event_id TEXT PRIMARY KEY,payload BLOB NOT NULL,
        received_count INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS receiver_deliveries(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL,
        mode TEXT NOT NULL,payload_sha TEXT NOT NULL,result TEXT NOT NULL,created INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS receiver_stats(id INTEGER PRIMARY KEY CHECK(id=1),redirect_followed INTEGER NOT NULL);
      INSERT OR IGNORE INTO receiver_stats VALUES(1,0);
      CREATE TABLE IF NOT EXISTS receiver_proxy_stats(id INTEGER PRIMARY KEY CHECK(id=1),hits INTEGER NOT NULL);
      INSERT OR IGNORE INTO receiver_proxy_stats VALUES(1,0);
    ''')


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass

    def body(self, limit):
        if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
            chunks, total = [], 0
            while True:
                size = int(self.rfile.readline(100).split(b';', 1)[0], 16)
                if not size:
                    while self.rfile.readline(100) not in (b'\r\n', b''):
                        pass
                    return b''.join(chunks)
                total += size
                if total > limit:
                    raise ValueError('oversize')
                chunks.append(self.rfile.read(size))
                if self.rfile.read(2) != b'\r\n':
                    raise ValueError('chunk framing')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= limit:
            raise ValueError('body size')
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError('truncated request')
        return raw

    def reply(self, code, value):
        body = canonical(value)
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def control(self):
        if self.headers.get('X-Task-Alert-Test') != TOKEN:
            return self.reply(403, {'error': 'private fixture token required'})
        if self.command == 'POST':
            try:
                data = strict_json(self.body(4096))
                assert isinstance(data, dict) and set(data) <= {'mode', 'release'}
                with LOCK:
                    if 'mode' in data:
                        assert data['mode'] in MODES
                        with connect() as db:
                            db.execute('UPDATE receiver_config SET mode=? WHERE id=1', (data['mode'],))
                    if data.get('release') is True:
                        for gate in HOLDS.values():
                            gate.set()
            except (ValueError, AssertionError, TypeError):
                return self.reply(400, {'error': 'invalid fixed receiver control'})
        with LOCK, connect() as db:
            events = [{'eventId': r['event_id'], 'metadataPayloadSha256': hashlib.sha256(r['payload']).hexdigest(),
                       'payload': strict_json(r['payload']), 'receivedCount': r['received_count'],
                       'created': r['created'], 'updated': r['updated']} for r in db.execute('SELECT * FROM receiver_events ORDER BY created,event_id')]
            attempts = [dict(row) for row in db.execute('SELECT id,event_id,mode,payload_sha,result,created FROM receiver_deliveries ORDER BY id')]
            result = {'isolated': True, 'realHttp': True, 'durableReceiver': True, 'externalSent': False,
                      'mode': db.execute('SELECT mode FROM receiver_config WHERE id=1').fetchone()[0],
                      'events': events, 'deliveries': attempts, 'held': sum(not gate.is_set() for gate in HOLDS.values()),
                      'redirectFollowed': db.execute('SELECT redirect_followed FROM receiver_stats WHERE id=1').fetchone()[0],
                      'proxyTrapCount': db.execute('SELECT hits FROM receiver_proxy_stats WHERE id=1').fetchone()[0],
                      'credentialHeadersStored': False}
        return self.reply(200, result)

    def do_GET(self):
        if self.path.startswith(('http://','https://')):
            with connect() as db: db.execute('UPDATE receiver_proxy_stats SET hits=hits+1 WHERE id=1')
            self.close_connection=True
            return self.reply(418, {'error':'owned proxy trap'})
        if self.path == '/__task-alert-fixture/control':
            return self.control()
        if self.path == '/task-alert-fixture/redirect-target':
            with connect() as db:
                db.execute('UPDATE receiver_stats SET redirect_followed=redirect_followed+1 WHERE id=1')
            return self.reply(409, {'error': 'redirect must not be followed'})
        return self.reply(404, {'error': 'not found'})

    def do_POST(self):
        if self.path.startswith(('http://','https://')):
            with connect() as db: db.execute('UPDATE receiver_proxy_stats SET hits=hits+1 WHERE id=1')
            self.close_connection=True
            return self.reply(418, {'error':'owned proxy trap'})
        if self.path == '/__task-alert-fixture/control':
            return self.control()
        if self.path != '/task-alert-fixture/events':
            return self.reply(404, {'error': 'not found'})
        try:
            raw = self.body(8192)
            timestamps = self.headers.get_all('X-EW-Alert-Timestamp') or []
            signatures = self.headers.get_all('X-EW-Alert-Signature') or []
            assert len(timestamps) == len(signatures) == 1
            timestamp, signature = timestamps[0], signatures[0]
            assert re.fullmatch(r'[0-9]{1,12}', timestamp) and abs(time.time() - int(timestamp)) <= 300
            assert re.fullmatch(r'[a-fA-F0-9]{64}', signature)
            expected = hmac.new(SECRET.encode(), timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
            assert hmac.compare_digest(signature.lower(), expected)
            event = strict_json(raw)
            assert isinstance(event, dict) and set(event) == FIELDS and canonical(event) == raw
            assert all(isinstance(event[key], str) and str(UUID(event[key])) == event[key] for key in ('eventId', 'alertId'))
            assert type(event['episode']) is int and event['episode'] > 0
            assert type(event['observedAt']) is int and 0 <= event['observedAt'] <= 9007199254740991
            assert event['severity'] in ('error', 'warning', 'info') and event['environment'] == 'sandbox'
            assert all(isinstance(event[key], str) and re.fullmatch(r'[A-Za-z0-9:_-]{1,100}', event[key]) for key in ('ruleCode', 'sourceType', 'sourceId'))
        except (ValueError, AssertionError, TypeError, KeyError):
            return self.reply(400, {'error': 'signed canonical event required'})
        stamp = time.time_ns() // 1000000
        with LOCK, connect() as db:
            mode = db.execute('SELECT mode FROM receiver_config WHERE id=1').fetchone()[0]
            existing = db.execute('SELECT payload FROM receiver_events WHERE event_id=?', (event['eventId'],)).fetchone()
            if existing and existing[0] != raw:
                return self.reply(409, {'error': 'event id reused with different bytes'})
            result = 'rejected-before-acceptance' if mode in ('http500', 'redirect') else 'accepted'
            if result == 'accepted':
                db.execute('INSERT INTO receiver_events VALUES(?,?,1,?,?) ON CONFLICT(event_id) DO UPDATE SET received_count=received_count+1,updated=excluded.updated', (event['eventId'], raw, stamp, stamp))
            cursor = db.execute('INSERT INTO receiver_deliveries(event_id,mode,payload_sha,result,created) VALUES(?,?,?,?,?)', (event['eventId'], mode, hashlib.sha256(raw).hexdigest(), result, stamp))
            delivery = cursor.lastrowid
        if mode == 'http500':
            return self.reply(500, {'error': 'explicit receiver fixture failure'})
        if mode == 'drop_after_accept':
            self.close_connection = True
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            return
        if mode == 'hold_after_accept':
            gate = threading.Event()
            with LOCK:
                HOLDS[delivery] = gate
            gate.wait(90)
        if mode == 'timeout_after_accept':
            time.sleep(9)
        response = canonical({'accepted': True, 'eventId': event['eventId']})
        if mode == 'wrong_event': response = canonical({'accepted': True, 'eventId': '00000000-0000-4000-8000-000000000000'})
        if mode in ('accepted_false', 'accepted_integer', 'accepted_string'): response = canonical({'accepted': {'accepted_false': False, 'accepted_integer': 1, 'accepted_string': 'true'}[mode], 'eventId': event['eventId']})
        if mode == 'extra_key': response = canonical({'accepted': True, 'eventId': event['eventId'], 'extra': True})
        if mode == 'array_ack': response = canonical([{'accepted': True, 'eventId': event['eventId']}])
        if mode == 'bad_json': response = b'{'
        if mode == 'duplicate_key': response = b'{"accepted":false,"accepted":true,"eventId":' + canonical(event['eventId']) + b'}'
        if mode == 'nonfinite': response = b'{"accepted":NaN,"eventId":' + canonical(event['eventId']) + b'}'
        if mode == 'invalid_utf8': response = b'{"accepted":true,"eventId":"\xff"}'
        if mode in ('oversize', 'oversize_chunked'): response = b' ' * 8193 + response
        signed_time = str(int(time.time()) + (-600 if mode == 'expired_timestamp' else 600 if mode == 'future_timestamp' else 0))
        signed = hmac.new(SECRET.encode(), signed_time.encode() + b'.' + response, hashlib.sha256).hexdigest()
        if mode == 'bad_signature': signed = ('0' if signed[0] != '0' else '1') + signed[1:]
        code = 302 if mode == 'redirect' else 202 if mode == 'status202' else 204 if mode == 'status204' else 200
        content_type = 'text/plain' if mode == 'bad_content_type' else 'application/json; charset=iso-8859-1' if mode == 'bad_charset' else 'Application/JSON; charset=UTF-8' if mode == 'ok_charset' else 'application/json'
        try:
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            if mode == 'redirect': self.send_header('Location', '/task-alert-fixture/redirect-target')
            if mode != 'unsigned':
                self.send_header('X-EW-Alert-Timestamp', signed_time)
                self.send_header('X-EW-Alert-Signature', signed)
            if mode == 'oversize_chunked': self.send_header('Transfer-Encoding', 'chunked')
            else: self.send_header('Content-Length', str(0 if code == 204 else len(response)))
            self.end_headers()
            if code != 204:
                if mode == 'oversize_chunked':
                    for offset in range(0, len(response), 257):
                        chunk = response[offset:offset + 257]
                        self.wfile.write(('%x\r\n' % len(chunk)).encode() + chunk + b'\r\n')
                    self.wfile.write(b'0\r\n\r\n')
                else: self.wfile.write(response)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


class ReceiverServer(ThreadingHTTPServer):
    daemon_threads = True
    address_family = socket.AF_INET6 if args.host == '::1' else socket.AF_INET


server = ReceiverServer((args.host, args.port), Handler)
authority = '[::1]' if args.host == '::1' else args.host
print('TASK_ALERT_FIXTURE: http://' + authority + ':' + str(server.server_port) + '/task-alert-fixture/events', flush=True)
try:
    server.serve_forever()
finally:
    with LOCK:
        for gate in HOLDS.values():
            gate.set()
    server.server_close()
