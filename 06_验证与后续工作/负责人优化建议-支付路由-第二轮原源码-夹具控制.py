"""Fixed controls for the new owned PAY05 database; never imported by production."""
import inspect
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

LOCK = threading.RLock()
RELEASE = threading.Event()
GATE = {'operation': '', 'entered': False, 'seen': 0, 'at': 1}
CLOCK = {'offsetMs': None}
BASE_CONTEXT = {'schema': 1, 'id': 'pay05-owned-fixture', 'revision': 1, 'platform': 'web', 'region': 'CN'}
TABLES = ('payment_routing_config', 'payment_routing_versions', 'payment_routing_quotes',
          'commerce_order_payment_routes', 'payment_routing_quote_consumptions',
          'payment_routing_confirmations', 'payment_routing_atomic_guards',
          'commerce_orders', 'commerce_order_items', 'commerce_reservations',
          'commerce_payment_events', 'commerce_entitlements', 'commerce_skus',
          'digital_order_snapshots', 'digital_entitlement_grants', 'membership_order_snapshots',
          'membership_subscriptions', 'membership_ai_periods', 'membership_ai_events',
          'payment_callback_inbox', 'payment_recovery_jobs', 'payment_late_cases')
LEGACY = json.loads(Path(__file__).with_name('负责人优化建议-支付路由旧订单夹具.json').read_text(encoding='utf-8'))


def seed_legacy(path, resume=False):
    if os.environ.get('ROUTING_LEGACY_SCENARIO') != '1': return
    database = Path(path).resolve()
    assert database.parent == Path(__file__).resolve().parent and database.is_file() and database.name.startswith('负责人优化建议-支付路由隔离-')
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        for sql in LEGACY['schema']: db.execute(sql)
        for table, rows in LEGACY['rows'].items():
            keys = LEGACY['primaryKeys'][table]
            for row in rows:
                previous = db.execute('SELECT * FROM '+table+' WHERE '+' AND '.join(key+'=?' for key in keys), tuple(row[key] for key in keys)).fetchone()
                if previous:
                    assert all(previous[key] == value for key, value in row.items()), 'Historical fixture bytes changed'
                else:
                    assert not resume, 'Restart cannot silently reconstruct historical rows'
                    names = list(row)
                    db.execute('INSERT INTO '+table+'('+','.join(names)+') VALUES('+','.join('?' for _ in names)+')', tuple(row[name] for name in names))


def context_value(mode):
    value = dict(BASE_CONTEXT)
    flag = '1'
    if mode == 'disabled': flag = '0'
    elif mode == 'nonliteral-enabled': flag = 'true'
    elif mode == 'revision2': value['revision'] = 2
    elif mode == 'app-store': value['platform'] = 'app_store'
    elif mode == 'google-play': value['platform'] = 'google_play'
    elif mode == 'region-us': value['region'] = 'US'
    elif mode == 'boolean-revision': value['revision'] = True
    elif mode == 'zero-revision': value['revision'] = 0
    elif mode == 'fractional-revision': value['revision'] = 1.5
    elif mode == 'lowercase-region': value['region'] = 'cn'
    elif mode == 'unknown-platform': value['platform'] = 'android'
    elif mode == 'whitespace-id': value['id'] += ' '
    elif mode == 'extra-field': value['untrusted'] = True
    elif mode == 'nested': value['region'] = {'value': 'CN'}
    elif mode == 'long-id': value['id'] = 'q' * 100
    elif mode not in ('enabled', 'bad-json', 'duplicate-key', 'float-lexeme', 'reordered'):
        raise ValueError('Unsupported fixed routing context mode')
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if mode == 'reordered': raw = json.dumps(value, sort_keys=True, separators=(',', ':'))
    if mode == 'bad-json': raw = '{"schema":'
    if mode == 'duplicate-key': raw = raw.replace('"schema":1', '"schema":1,"schema":1')
    if mode == 'float-lexeme': raw = raw.replace('"revision":1', '"revision":1.0')
    return flag, raw


def install_hooks(server_module):
    import payment_routing
    native_clock = payment_routing.PaymentRouting.clock
    def clock(self):
        with LOCK: offset = CLOCK['offsetMs']
        return native_clock(self) if offset is None else int(time.time() * 1000) + offset
    payment_routing.PaymentRouting.clock = clock
    native_begin = payment_routing.PaymentRouting.begin_order
    def begin_order(self, *args, **kwargs):
        before_native('env-recheck')
        return native_begin(self, *args, **kwargs)
    payment_routing.PaymentRouting.begin_order = begin_order
    native_connect = server_module.Store.connect
    def connect(self, *args, **kwargs):
        caller = inspect.currentframe().f_back
        function, filename = caller.f_code.co_name, Path(caller.f_code.co_filename).name
        operation = 'order' if filename == 'commerce.py' and function == 'create_order' else 'pay' if filename == 'commerce.py' and function == 'pay' else 'routing' if filename == 'payment_routing.py' else ''
        before_native(operation)
        return native_connect(self, *args, **kwargs)
    server_module.Store.connect = connect


def before_native(operation):
    wait = False
    with LOCK:
        if operation and operation == GATE['operation']:
            GATE['seen'] += 1
            if GATE['seen'] == GATE['at']:
                GATE['entered'] = True
                wait = True
    # env-recheck is only used with an environment-only control; no concurrent DB write is needed.
    if wait and not RELEASE.wait(25): raise RuntimeError('Owned routing test barrier expired')


def handle(path, data):
    action = data.get('action', '')
    if not action.startswith('routing-'): return None
    database = Path(path).resolve()
    assert database.parent == Path(__file__).resolve().parent and database.is_file()
    assert database.name.startswith('负责人优化建议-支付路由隔离-')
    if action == 'routing-context':
        flag, raw = context_value(data.get('mode', 'enabled'))
        os.environ['EW_PAYMENT_ROUTING_SANDBOX_CONTEXT_ENABLED'] = flag
        os.environ['EW_PAYMENT_ROUTING_SANDBOX_CONTEXT_JSON'] = raw
        return {'changed': True, 'fixedMode': data.get('mode', 'enabled'), 'serverEnvironmentOnly': True}
    if action == 'routing-clock':
        offset = data.get('offsetMs')
        if offset is not None and (type(offset) is not int or not -299_000 <= offset <= 0): raise ValueError('Only an explicit near-expiry offset is allowed')
        with LOCK: CLOCK['offsetMs'] = offset
        return {'offsetMs': offset, 'globalDateNowChanged': False, 'sqlCurrentTimeChanged': False, 'fixtureOnly': True}
    if action == 'routing-barrier-arm':
        if data.get('operation') not in ('order', 'pay', 'routing', 'env-recheck'): raise ValueError('Invalid fixed operation')
        with LOCK:
            GATE.update(operation=data['operation'], entered=False, seen=0, at=1)
            RELEASE.clear()
        return {'armed': True, 'position': 'before-original-environment-revalidation' if data['operation']=='env-recheck' else 'before-native-connect-and-BEGIN'}
    if action == 'routing-barrier-release':
        RELEASE.set()
        with LOCK: GATE['operation'] = ''
        return {'released': True}
    if action == 'routing-barrier-state':
        with LOCK: return dict(GATE)
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        if action == 'routing-snapshot':
            selected = data.get('tables', list(TABLES))
            if not isinstance(selected, list) or any(table not in TABLES for table in selected): raise ValueError('Invalid snapshot table')
            return {'tables': {table: [dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')] for table in selected}, 'readOnly': True, 'sqlNow': db.execute("SELECT CAST((julianday('now')-2440587.5)*86400000 AS INTEGER)").fetchone()[0]}
        if action == 'routing-fault':
            table = {'route': 'commerce_order_payment_routes', 'consumption': 'payment_routing_quote_consumptions', 'confirmation': 'payment_routing_confirmations'}.get(data.get('kind'))
            if not table or type(data.get('enabled')) is not bool: raise ValueError('Invalid fixed fault')
            name = 'pay05_qa_'+data['kind']+'_fault'
            db.execute('DROP TRIGGER IF EXISTS '+name)
            if data['enabled']: db.execute('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT pay05_fixture_storage_failure(); END')
            return {'changed': True, 'actualSqliteTrigger': True, 'syntheticOnly': True}
        if action == 'routing-immutable-attempts':
            checks = []
            for table, key in [('payment_routing_versions', 'id'), ('payment_routing_quotes', 'id'), ('commerce_order_payment_routes', 'order_id'), ('payment_routing_quote_consumptions', 'quote_id'), ('payment_routing_confirmations', 'id')]:
                row = db.execute('SELECT '+key+' FROM '+table+' ORDER BY rowid LIMIT 1').fetchone()
                if not row: continue
                for operation in ('update', 'delete'):
                    db.execute('SAVEPOINT immutable_probe')
                    blocked = False
                    try:
                        db.execute(('UPDATE '+table+' SET created=created+1 WHERE '+key+'=?') if operation == 'update' else ('DELETE FROM '+table+' WHERE '+key+'=?'), (row[0],))
                    except sqlite3.IntegrityError: blocked = True
                    finally:
                        db.execute('ROLLBACK TO immutable_probe'); db.execute('RELEASE immutable_probe')
                    checks.append({'table': table, 'operation': operation, 'blocked': blocked})
            return {'checks': checks, 'actualDatabaseTriggers': True, 'mutationsRolledBack': True}
    raise ValueError('Unsupported fixed routing control')
