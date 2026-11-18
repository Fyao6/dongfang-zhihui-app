"""Owned short diagnostic: original HTTP/business handlers, measured SQLite calls.

No SQL/arguments/headers/bodies are saved; only fixed categories and timings.
"""
import argparse
from contextlib import contextmanager
import hashlib
from http.server import ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
PREFIX = '负责人优化建议-本地可靠性热点隔离-'
LOCK = threading.Lock()
STATE = {'phase': 'startup', 'categories': {}, 'connectionsOpened': 0, 'connectionsClosed': 0,
         'activeConnections': 0, 'peakConnections': 0, 'activeRequests': 0, 'peakRequests': 0,
         'completedRequests': 0, 'routes': {}, 'schemaRefreshes': 0}


def measurement(kind, wall, cpu, error=False, first=False, affected=None):
    with LOCK:
        item = STATE['categories'].setdefault(kind, {'count': 0, 'wallMs': 0, 'cpuMs': 0,
                    'maxWallMs': 0, 'errors': 0, 'firstOnConnection': 0,
                    'zeroAffected': 0, 'affectedRows': 0})
        item['count'] += 1
        item['wallMs'] += wall
        item['cpuMs'] += cpu
        item['maxWallMs'] = max(item['maxWallMs'], wall)
        item['errors'] += int(error)
        item['firstOnConnection'] += int(first)
        if affected is not None and affected >= 0:
            item['zeroAffected'] += int(affected == 0)
            item['affectedRows'] += affected


def category(sql):
    value = sql.lstrip().upper()
    if value.startswith('BEGIN IMMEDIATE'):
        return 'BEGIN_IMMEDIATE'
    if value.startswith('INSERT INTO ACCOUNT_ACTION_FENCES'):
        return 'ACCOUNT_FENCE_INSERT'
    if value.startswith('UPDATE COMMERCE_ORDERS') and "PAYMENT_STATUS='EXPIRED'" in value:
        return 'EXPIRY_UPDATE'
    if value.startswith('PRAGMA SCHEMA_VERSION'):
        return 'PRAGMA_SCHEMA_VERSION'
    if value.startswith('PRAGMA'):
        return 'PRAGMA_OTHER'
    if value.startswith(('CREATE ', 'ALTER ', 'DROP ')):
        return 'DDL'
    if value.startswith('SELECT') and ('SQLITE_MASTER' in value or 'SQLITE_SCHEMA' in value):
        return 'SCHEMA_SELECT'
    return next((key for key in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'BEGIN', 'COMMIT', 'ROLLBACK')
                 if value.startswith(key)), 'OTHER')


class TimedConnection(sqlite3.Connection):
    def execute(self, sql, parameters=()):
        first = not getattr(self, '_observed_any', False)
        self._observed_any = True
        wall, cpu, error, affected = time.perf_counter_ns(), time.thread_time_ns(), False, None
        try:
            result = super().execute(sql, parameters)
            affected = result.rowcount
            return result
        except Exception:
            error = True
            raise
        finally:
            measurement(category(sql), (time.perf_counter_ns()-wall)/1e6,
                        (time.thread_time_ns()-cpu)/1e6, error, first, affected)

    def executescript(self, script):
        wall, cpu, error = time.perf_counter_ns(), time.thread_time_ns(), False
        try:
            return super().executescript(script)
        except Exception:
            error = True
            raise
        finally:
            measurement('EXECUTESCRIPT', (time.perf_counter_ns()-wall)/1e6,
                        (time.thread_time_ns()-cpu)/1e6, error)

    def __exit__(self, *args):
        wall, cpu, error = time.perf_counter_ns(), time.thread_time_ns(), False
        active = self.in_transaction
        try:
            return super().__exit__(*args)
        except Exception:
            error = True
            raise
        finally:
            measurement('COMMIT_ACTIVE' if active else 'TRANSACTION_EXIT_READ', (time.perf_counter_ns()-wall)/1e6,
                        (time.thread_time_ns()-cpu)/1e6, error)

    def close(self):
        if getattr(self, '_closed_observed', False):
            return
        self._closed_observed = True
        wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
        try:
            return super().close()
        finally:
            measurement('CONNECTION_CLOSE', (time.perf_counter_ns()-wall)/1e6,
                        (time.thread_time_ns()-cpu)/1e6)
            with LOCK:
                STATE['connectionsClosed'] += 1
                STATE['activeConnections'] -= 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--metrics', required=True)
    parser.add_argument('--phase', required=True, choices=('auth', 'privacy', 'cart'))
    args = parser.parse_args()
    db_path, metrics = Path(args.db).resolve(), Path(args.metrics).resolve()
    assert db_path.parent == OUT and db_path.name.startswith(PREFIX) and not db_path.exists()
    assert metrics.parent == OUT and metrics.name.startswith(PREFIX) and not metrics.exists()
    token = os.environ['EW_RELIABILITY_DIAG_TOKEN']
    assert re.fullmatch('[a-f0-9]{64}', token)
    source = ROOT / '04_研发源码/app/r4/backend/server.py'
    spec = importlib.util.spec_from_file_location('owned_hotspot_server', source)
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    original_connect = sqlite3.connect

    def connect(*a, **kw):
        assert Path(a[0]).resolve() == db_path
        wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
        kw['factory'] = TimedConnection
        connection = original_connect(*a, **kw)
        measurement('CONNECTION_OPEN', (time.perf_counter_ns()-wall)/1e6,
                    (time.thread_time_ns()-cpu)/1e6)
        with LOCK:
            STATE['connectionsOpened'] += 1
            STATE['activeConnections'] += 1
            STATE['peakConnections'] = max(STATE['peakConnections'], STATE['activeConnections'])
        return connection

    sqlite3.connect = connect
    store = app.Store(db_path)
    with store.connect() as db:
        journal = db.execute('PRAGMA journal_mode').fetchone()[0]
        schema = db.execute("SELECT count(*),sum(length(sql)) FROM sqlite_master WHERE type='trigger'").fetchone()
    original_guards = app.privacy_reference_guard_sql

    def guarded_schema(*a, **kw):
        with LOCK:
            STATE['schemaRefreshes'] += 1
        return original_guards(*a, **kw)
    app.privacy_reference_guard_sql = guarded_schema
    Base = app.make_handler(store, ROOT / '03_当前APP')
    state_ready = False

    def snapshot():
        with LOCK:
            value = json.loads(json.dumps(STATE))
        return {**value, 'processCpuMs': time.process_time()*1000, 'monotonicMs': time.perf_counter()*1000,
                'threads': threading.active_count(), 'journalMode': journal,
                'schemaTriggers': schema[0], 'triggerSqlCharacters': schema[1],
                'listenBacklog': server.request_queue_size,
                'sqlArgumentsOrBodiesRecorded': False, 'observationalWrapperOnly': True}

    class Handler(Base):
        def log_message(self, *args):
            pass

        def route(self, method):
            nonlocal state_ready
            if self.path == '/__owned-hotspot-control':
                self.cookies_out = []
                if self.headers.get('X-Owned-Hotspot') != token:
                    return self.send(404, {'error': 'not_found'})
                if method == 'POST':
                    with LOCK:
                        STATE.update(phase=args.phase, categories={}, connectionsOpened=0,
                            connectionsClosed=0, activeConnections=0, peakConnections=0,
                            activeRequests=0, peakRequests=0, completedRequests=0,
                            routes={}, schemaRefreshes=0)
                    state_ready = True
                return self.send(200, snapshot())
            label = {'/api/auth/status': 'auth_status', '/api/privacy/preferences': 'privacy_preferences',
                     '/api/commerce/cart': 'commerce_cart'}.get(self.path, 'setup_other')
            with LOCK:
                STATE['activeRequests'] += 1
                STATE['peakRequests'] = max(STATE['peakRequests'], STATE['activeRequests'])
            wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
            try:
                return super().route(method)
            finally:
                with LOCK:
                    STATE['activeRequests'] -= 1
                    STATE['completedRequests'] += 1
                    item = STATE['routes'].setdefault(label, {'count': 0, 'wallMs': 0, 'cpuMs': 0})
                    item['count'] += 1
                    item['wallMs'] += (time.perf_counter_ns()-wall)/1e6
                    item['cpuMs'] += (time.thread_time_ns()-cpu)/1e6

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    def heartbeat():
        while True:
            if state_ready:
                data = json.dumps(snapshot(), separators=(',', ':')).encode()
                temp = metrics.with_suffix('.tmp')
                temp.write_bytes(data)
                os.replace(temp, metrics)
            time.sleep(1)
    threading.Thread(target=heartbeat, daemon=True).start()
    print(json.dumps({'base': 'http://127.0.0.1:'+str(server.server_port), 'pid': os.getpid(),
                      'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest()}), flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
