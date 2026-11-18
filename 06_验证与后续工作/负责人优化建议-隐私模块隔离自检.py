"""In-memory contract checks only. Never opens an existing database or a network."""
from pathlib import Path
from contextlib import contextmanager
import ast
import copy
import hashlib
import importlib.util
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
BACK = ROOT / '04_研发源码/app/r4/backend'
sys.dont_write_bytecode = True


def load(name):
    spec = importlib.util.spec_from_file_location('privacy_test_' + name, BACK / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


privacy, commerce, creator, analytics = [load(x) for x in ('privacy', 'commerce', 'creator', 'analytics')]
tree = ast.parse((BACK / 'server.py').read_text(encoding='utf-8'))
store_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Store')
core = next(n.args[0].value for n in ast.walk(store_class) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'executescript' and isinstance(n.args[0], ast.Constant))


class Error(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class MemoryStore:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(core)
        for module in (privacy, commerce, creator, analytics):
            module.init_schema(self.db)
        for uid in ('one', 'two', 'admin'):
            salt = '01' * 16
            password = salt + ':' + hashlib.pbkdf2_hmac('sha256', b'synthetic-password', bytes.fromhex(salt), 260000).hex()
            self.db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)', (uid, uid, password, uid, 'admin' if uid == 'admin' else 'user', 1))
        self.db.commit()

    @contextmanager
    def connect(self):
        with self.db:
            yield self.db

    def setting(self, key):
        row = self.db.execute('SELECT data FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row['data']) if row else {}

    def audit(self, db, actor, action, target, detail=''):
        db.execute('INSERT INTO audits VALUES (?,?,?,?,?,?)', (str(privacy.uuid4()), actor, action, target, detail, 1))


class Handler:
    def __init__(self, store, uid):
        self.user = store.db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        self.data = {}

    def require(self, roles=None):
        if not self.user:
            raise Error(401, 'login')
        if roles and self.user['role'] not in roles:
            raise Error(403, 'role')
        return self.user

    def body(self):
        return self.data


store = MemoryStore()
handler, admin = Handler(store, 'one'), Handler(store, 'admin')
api = privacy.Privacy(store, handler, Error, lambda *args: None)
manager = privacy.Privacy(store, admin, Error, lambda *args: None)
checks = []


def check(name, predicate):
    assert predicate, name
    checks.append({'name': name, 'passed': True})


def rejects(name, expected, call):
    try:
        call()
    except Error as error:
        check(name, error.status == expected)
    else:
        raise AssertionError(name + ' did not reject')


def authorize(data, provider='fixture', snapshot=None):
    return privacy.authorize_ai(store, handler.user, data, Error, provider, store.setting('ai') if snapshot is None else snapshot)


def set_ai(value):
    with store.connect() as db:
        db.execute("INSERT INTO settings VALUES ('ai',?) ON CONFLICT(key) DO UPDATE SET data=excluded.data", (json.dumps(value),))


p = api.route('GET', '/api/privacy/preferences')
check('all six permissions default off and no invented memory', not any(p['consents'].values()) and p['memory'] == {'available': False, 'enabled': False, 'items': []})
rejects('unconfigured disclosure blocks outbound general chat', 503, lambda: privacy.authorize_ai(store, handler.user, {'messages': []}, Error))
cfg = copy.deepcopy(privacy.DEFAULT_CONFIG)
cfg.update(policyVersion='fixture-v1', controllerName='Synthetic test controller', contact='test-only', recipients=[{'id': 'fixture', 'name': 'Synthetic provider', 'endpoint': 'https://example.invalid/ai', 'models': ['model-one', 'model-two'], 'regions': ['test-region'], 'purpose': 'Synthetic contract check only', 'policyUrl': 'https://example.invalid/policy', 'retentionDays': None, 'deletionSupported': False}])
admin.data = cfg
manager.route('PATCH', '/api/admin/privacy/config')
check('incomplete real provider configuration cannot enable acknowledgment', not api.route('GET', '/api/privacy/preferences')['disclosure']['configured'])
actual_ai = {'providerId': 'fixture', 'endpoint': 'https://example.invalid/ai', 'model': 'model-one', 'processingRegions': ['test-region'], 'privacyPolicyVersion': 'fixture-v1'}
set_ai(actual_ai)
rejects('provider argument mandatory even with exactly one receiver', 503, lambda: privacy.authorize_ai(store, handler.user, {}, Error))
rejects('actual outbound configuration snapshot mandatory', 503, lambda: privacy.authorize_ai(store, handler.user, {}, Error, 'fixture'))
rejects('no disclosure acknowledgment blocks general chat', 403, lambda: authorize({}))
handler.data = {'revision': 0, 'policyVersion': 'fixture-v1', 'acknowledged': True, 'consents': {'chart': True, 'saveConversations': True}}
api.route('PATCH', '/api/privacy/preferences')
check('ordinary chat needs no wellbeing permission', authorize({}) is None)
rejects('unknown actual receiver blocks sending', 503, lambda: authorize({}, 'wrong-provider'))
check('chart context limited to approved fields', authorize({'context': {'category': 'chart', 'fields': {'chartType': 'bazi', 'pillars': ['a', 'b']}}})['fields']['pillars'] == ['a', 'b'])
rejects('wellbeing separate permission enforced', 403, lambda: authorize({'context': {'category': 'wellbeing', 'fields': {'mood': 'test'}}}))
rejects('extra name/contact field rejected', 400, lambda: authorize({'context': {'category': 'chart', 'fields': {'name': 'private'}}}))
rejects('nested personal profile rejected', 400, lambda: authorize({'context': {'category': 'chart', 'fields': {'summary': {'phone': 'secret'}}}}))
rejects('untyped legacy context rejected', 400, lambda: authorize({'context': {'title': 'legacy'}}))
rejects('memory read rejected', 409, lambda: authorize({'useMemory': True}))
for field, replacement in [('endpoint', 'https://different.invalid/ai'), ('processingRegions', ['other-region']), ('privacyPolicyVersion', 'other-version')]:
    set_ai({**actual_ai, field: replacement})
    rejects('actual '+field+' mismatch blocks old consent', 503, lambda: authorize({}))
    check('actual '+field+' mismatch disables acknowledgment', not api.route('GET', '/api/privacy/preferences')['policyAcknowledged'])
set_ai({**actual_ai, 'model': 'model-two'})
rejects('model change invalidates old binding even when model is allowlisted', 403, lambda: authorize({}))
rejects('stale outbound configuration snapshot rejected', 409, lambda: authorize({}, snapshot=actual_ai))
set_ai(actual_ai)
auth = api.route('GET', '/api/privacy/preferences')
tag = {'accountId': 'one', 'consentEpoch': auth['consentEpoch'], 'providerId': 'fixture', 'providerBinding': auth['providerBinding'], 'policyVersion': 'fixture-v1', 'source': 'user', 'category': 'general'}
check('current explicit ordinary message metadata accepted', authorize({'messages': [{'role': 'user', 'content': 'typed text', 'privacy': tag}]}) is None)
rejects('unmarked legacy history never automatically resends', 403, lambda: authorize({'messages': [{'role': 'user', 'content': 'legacy record'}]}))
rejects('report cannot be relabeled as ordinary general history', 403, lambda: authorize({'messages': [{'role': 'user', 'content': 'auto record', 'privacy': {**tag, 'source': 'report'}}]}))
handler.data = {'revision': 1, 'policyVersion': 'fixture-v1', 'consents': {'longTermMemory': True}}
rejects('unavailable memory cannot be enabled', 409, lambda: api.route('PATCH', '/api/privacy/preferences'))
handler.data = {'revision': 1, 'policyVersion': 'fixture-v1', 'consents': {'trainingImprovement': True}}
rejects('unspecified new training purpose cannot be preauthorized', 409, lambda: api.route('PATCH', '/api/privacy/preferences'))
handler.data = {'revision': 0, 'consents': {'chart': False}}
rejects('stale settings revision rejected', 409, lambda: api.route('PATCH', '/api/privacy/preferences'))
handler.data = {'revision': 1, 'consents': {'chart': False}}
api.route('PATCH', '/api/privacy/preferences')
rejects('revoked chart consent immediately blocks next call', 403, lambda: authorize({'context': {'category': 'chart', 'fields': {'date': 'test'}}}))
rejects('any consent revision stops automatic old-history resend', 403, lambda: authorize({'messages': [{'role': 'user', 'content': 'typed old', 'privacy': tag}]}))
check('optional conversation storage honors separate permission', privacy.save_conversation(store, 'one', [{'role': 'user', 'content': 'own-test'}]))
with store.connect() as db:
    db.execute('INSERT INTO messages VALUES (?,?,?,?,?)', ('sent', 'one', 'two', 'own-message', 1))
    db.execute('INSERT INTO messages VALUES (?,?,?,?,?)', ('received', 'two', 'one', 'OTHER-PRIVATE-CONTENT', 2))
    for uid in ('one', 'two'):
        db.execute('INSERT INTO records VALUES (?,?,?,?,?)', (uid, 'body', '2026-11-12', json.dumps({'owner': uid}), 1))
export = api.route('GET', '/api/privacy/export')
text = json.dumps(export)
check('exports own message only and excludes credentials', 'own-message' in text and 'OTHER-PRIVATE-CONTENT' not in text and 'synthetic-password' not in text and store.db.execute("SELECT password FROM users WHERE id='one'").fetchone()[0] not in text)
check('commerce allowlist queries compile against actual new schema', 'commerceOrders' in export['serverData'] and 'commerceOrderItems' in export['serverData'] and 'commerceAftersaleRequests' in export['serverData'])
handler.data = {'kind': 'delete-records', 'requestId': 'fixture-delete-records'}
request = api.route('POST', '/api/privacy/requests')['item']
check('record deletion isolated to owner', not store.db.execute("SELECT 1 FROM records WHERE owner='one'").fetchone() and bool(store.db.execute("SELECT 1 FROM records WHERE owner='two'").fetchone()))
check('provider and backup deletion never claimed complete', request['status'] == 'pending-provider' and request['details']['backups']['status'] == 'pending-confirmation')
check('duplicate request returns same processing id', api.route('POST', '/api/privacy/requests')['item']['id'] == request['id'])
handler.data = {'kind': 'close-account', 'requestId': 'fixture-close-wrong', 'password': 'wrong', 'renewalAcknowledged': True}
rejects('account closure verifies own password', 403, lambda: api.route('POST', '/api/privacy/requests'))
handler.data = {'kind': 'close-account', 'requestId': 'fixture-close-correct', 'password': 'synthetic-password', 'renewalAcknowledged': True}
close = api.route('POST', '/api/privacy/requests')['item']
check('closure creates honest pending task and leaves account open', close['status'] == 'pending-review' and not close['details']['accountClosed'] and bool(store.db.execute("SELECT 1 FROM users WHERE id='one'").fetchone()))
check('closure withdraws all optional permissions', not any(api.route('GET', '/api/privacy/preferences')['consents'].values()))
rejects('closure pending blocks new outbound AI', 403, lambda: authorize({}))
rejects('ordinary account cannot administer privacy config', 403, lambda: api.route('GET', '/api/admin/privacy/config'))
check('unknown nonprivacy routes not intercepted', api.route('GET', '/api/unrelated') is None)
second_handler = Handler(store, 'two')
second = privacy.Privacy(store, second_handler, Error, lambda *args: None)
second_handler.data = {'revision': 0, 'policyVersion': 'fixture-v1', 'acknowledged': True, 'consents': {'chart': True, 'saveConversations': True}}
second.route('PATCH', '/api/privacy/preferences')
second_handler.data = {'revision': 1, 'policyVersion': 'fixture-v1', 'acknowledged': False, 'consents': {'chart': True}}
withdrawn = second.route('PATCH', '/api/privacy/preferences')
check('overall acknowledgment withdrawal clears stored policy and provider receipt', not withdrawn['policyAcknowledged'] and withdrawn['policyVersion'] == '' and withdrawn['providerBinding'] == '' and not any(withdrawn['consents'].values()) and withdrawn['authorizedCategories'] == [])
rejects('overall withdrawal blocks ordinary AI even when fields were previously allowed', 403, lambda: privacy.authorize_ai(store, second_handler.user, {}, Error, 'fixture', actual_ai))
result = {'kind': 'isolated-in-memory-contract-checks', 'passed': len(checks), 'failed': 0, 'original_database_accessed': False, 'network_calls': 0, 'checks': checks}
(ROOT / '06_验证与后续工作/负责人优化建议-隐私模块隔离自检.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'passed': len(checks), 'failed': 0}))
