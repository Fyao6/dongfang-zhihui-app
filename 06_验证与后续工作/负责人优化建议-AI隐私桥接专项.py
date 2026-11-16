"""Pure fixtures + in-memory virtual integration. Never modifies frozen privacy sources or calls a provider."""
import ast
import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import time
import traceback
import types

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(BACKEND))
import privacy as frozen
import privacy_gateway_bridge as bridge
import ai_gateway as gateway_module

spec = importlib.util.spec_from_file_location('privacy_bridge_installer', Path(__file__).with_name('负责人优化建议-AI隐私桥接接入.py'))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
fixture = json.loads(Path(__file__).with_name('负责人优化建议-AI隐私桥接夹具.json').read_text(encoding='utf-8'))
source_names = ['04_研发源码/app/r4/backend/privacy.py', '04_研发源码/app/cloud/lib/privacy-api.ts']
sha = lambda value: hashlib.sha256(value).hexdigest()
source_before = {n: sha((ROOT / n).read_bytes()) for n in source_names}
results, bindings = [], {}


def check(name, action):
    try:
        observed = action()
        results.append({'name': name, 'pass': True, **({'observed': observed} if observed is not None else {})})
    except Exception:
        results.append({'name': name, 'pass': False, 'error': traceback.format_exc()})


def expect_error(action, status):
    try:
        action()
    except Error as error:
        assert error.status == status, (error.status, status)
    else:
        raise AssertionError('Expected refusal ' + str(status))


def owner_path(value, dotted):
    parts = dotted.split('.')
    for key in parts[:-1]:
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value, int(parts[-1]) if isinstance(value, list) else parts[-1]


base = bridge.global_binding(fixture['privacy'], {}, fixture['gateway'], frozen.actual_binding)
assert base
for case in fixture['cases']:
    def run_case(case=case):
        value = copy.deepcopy(fixture)
        for dotted, replacement in case.get('set', []):
            owner, key = owner_path(value, dotted)
            owner[key] = replacement
        for dotted in case.get('delete', []):
            owner, key = owner_path(value, dotted)
            del owner[key]
        for dotted in case.get('reverse', []):
            owner, key = owner_path(value, dotted)
            owner[key].reverse()
        legacy = value['legacy'] if case.get('legacy') else {}
        actual = bridge.global_binding(value['privacy'], legacy, value['gateway'], frozen.actual_binding)
        assert bool(actual) is case['valid'], actual
        if actual:
            if case.get('mode') == 'legacy':
                assert actual == frozen.actual_binding(value['privacy'], legacy)
            else:
                assert actual['details']['mode'] == 'gateway-registry'
                assert 'providerId' not in actual['details']
                assert 'secretRef' not in json.dumps(actual)
                assert 'SYNTHETIC_SECRET_NOT_IN_DIGEST' not in json.dumps(actual)
            if 'sameAsBase' in case:
                assert (actual['digest'] == base['digest']) is case['sameAsBase']
        bindings[case['name']] = actual['digest'] if actual else None
    check('fixture: ' + case['name'], run_case)

planned = installer.prepare()
new_source = planned[installer.PYTHON]['updated']
virtual = types.ModuleType('privacy_bridge_virtual')
virtual.__file__ = str(BACKEND / 'privacy.py')
exec(compile(new_source, virtual.__file__, 'exec'), virtual.__dict__)


def plan_integrity():
    assert installer.python_functions(new_source) == installer.python_functions(planned[installer.PYTHON]['current'])
    assert installer.cloud_legacy(planned[installer.CLOUD]['updated']) == installer.cloud_legacy(planned[installer.CLOUD]['current'])
    assert installer.transform_python(new_source)[0] == new_source
    assert installer.transform_cloud(planned[installer.CLOUD]['updated'])[0] == planned[installer.CLOUD]['updated']
    return {'pythonSites': 3, 'cloudSites': 4, 'sourceWrites': False, 'legacyAuthorizeAndSaveUnchanged': True}


check('virtual integration is idempotent and preserves legacy outbound/save functions', plan_integrity)


class Error(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class Store:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT);CREATE TABLE users(id TEXT PRIMARY KEY);')
        self.db.executemany('INSERT INTO users VALUES(?)', [('u1',), ('u2',)])
        self.audits = []
        gateway_module.init_schema(self.db)

    @contextmanager
    def connect(self):
        with self.db:
            yield self.db

    def setting(self, key):
        row = self.db.execute('SELECT data FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row['data']) if row else {}

    def put(self, key, value):
        with self.connect() as db:
            db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data', (key, json.dumps(value, ensure_ascii=False)))

    def audit(self, *args):
        self.audits.append(args[2:])


class Handler:
    def __init__(self, identifier):
        self.user = {'id': identifier, 'role': 'user'}
        self.payload = {}

    def require(self, roles=None):
        if not self.user:
            raise Error(401, 'login')
        if roles and self.user['role'] not in roles:
            raise Error(403, 'role')
        return self.user

    def body(self):
        return copy.deepcopy(self.payload)


store, handler, other = Store(), Handler('u1'), Handler('u2')
store.put('privacy', fixture['privacy'])
store.put('ai', {})
store.put('ai_gateway', fixture['gateway'])
privacy = virtual.Privacy(store, handler, Error, lambda *args: None)
other_privacy = virtual.Privacy(store, other, Error, lambda *args: None)
provider = fixture['gateway']['providers'][0]
gateway = gateway_module.AIGateway(store, handler, Error, lambda *args: None, privacy_response=privacy.response)


def acknowledge(instance, user, consents=None, acknowledged=True):
    current = instance.response()
    user.payload = {'revision': current['revision'], 'policyVersion': fixture['privacy']['policyVersion'], 'acknowledged': acknowledged, 'consents': consents or {}}
    return instance.route('PATCH', '/api/privacy/preferences')


def registry_ack():
    original = frozen.Privacy(store, handler, Error, lambda *args: None).response()
    assert original['disclosure']['configured'] is False
    prepared = privacy.response()
    assert prepared['disclosure']['configured'] is True
    assert prepared['disclosure']['activeAI']['mode'] == 'gateway-registry'
    assert prepared['policyAcknowledged'] is False
    result = acknowledge(privacy, handler)
    assert result['policyAcknowledged'] is True
    assert result['providerBinding'] == base['digest']
    assert not any(result['consents'].values())
    assert result['authorizedCategories'] == ['general', 'card']
    assert store.db.execute('SELECT count(*) FROM ai_gateway_provider_consents').fetchone()[0] == 0


check('registry-only actual preferences PATCH acknowledges aggregate without authorizing any provider', registry_ack)


def hook_response():
    old = frozen.Privacy(store, handler, Error, lambda *args: None).response()
    actual = bridge.bridge_privacy_response(old, {}, fixture['gateway'], frozen.actual_binding, 'u1')
    assert actual == privacy.response()
    try:
        bridge.bridge_privacy_response(old, {}, fixture['gateway'], frozen.actual_binding, 'u2')
    except ValueError:
        pass
    else:
        raise AssertionError('Different account cannot use the bridge response')


check('pure response hook equals virtual API and rejects another account', hook_response)


def no_receipt():
    assert gateway.authorization(provider, require_receipt=False)['receiptValid'] is False
    expect_error(lambda: gateway.authorization(provider), 403)
    acknowledge(privacy, handler, {'saveConversations': True})
    assert frozen.save_conversation(store, 'u1', [{'role': 'user', 'content': 'must not save through legacy aggregate'}]) is False
    expect_error(lambda: frozen.authorize_ai(store, handler.user, {'messages': []}, Error, 'alpha', fixture['legacy']), 503)


check('global aggregate never bypasses individual receipt or legacy outbound/save gates', no_receipt)


def individual_receipt():
    auth = gateway.authorization(provider, require_receipt=False)
    assert auth['providerBinding'] != base['digest']
    handler.payload = {'acknowledged': True, 'policyVersion': auth['policyVersion'], 'providerBinding': auth['providerBinding'], 'categories': ['general']}
    gateway.route('POST', '/api/ai-gateway/providers/alpha/consent')
    assert gateway.authorization(provider)['receiptValid'] is True
    expect_error(lambda: gateway.authorization(fixture['gateway']['providers'][1]), 403)
    assert store.db.execute('SELECT count(*) FROM ai_gateway_provider_consents').fetchone()[0] == 1
    acknowledge(other_privacy, other)
    second = gateway_module.AIGateway(store, other, Error, lambda *args: None, privacy_response=other_privacy.response)
    expect_error(lambda: second.authorization(provider), 403)


check('actual provider consent creates only its receipt and remains account/provider isolated', individual_receipt)


def withdraw():
    before = privacy.response()
    withdrawn = acknowledge(privacy, handler, acknowledged=False)
    assert withdrawn['providerBinding'] == '' and withdrawn['policyAcknowledged'] is False
    assert withdrawn['consentEpoch'] != before['consentEpoch']
    expect_error(lambda: gateway.authorization(provider), 403)
    restored = acknowledge(privacy, handler)
    assert restored['policyAcknowledged'] is True
    expect_error(lambda: gateway.authorization(provider), 403)


check('global withdrawal invalidates receipts and reconfirmation does not restore them automatically', withdraw)


def priority_and_change():
    prior = privacy.response()
    changed = copy.deepcopy(fixture['gateway'])
    changed['providers'][0]['model'] = 'alpha-next'
    store.put('ai_gateway', changed)
    assert privacy.response()['policyAcknowledged'] is False
    assert privacy.response()['consentEpoch'] != prior['consentEpoch']
    store.put('ai_gateway', fixture['gateway'])
    store.put('ai', fixture['legacy'])
    result = acknowledge(privacy, handler, {'saveConversations': True})
    assert result['disclosure']['activeAI'].get('mode') is None
    assert result['providerBinding'] == frozen.actual_binding(fixture['privacy'], fixture['legacy'])['digest']
    assert bridge.global_binding(fixture['privacy'], fixture['legacy'], None) == frozen.actual_binding(fixture['privacy'], fixture['legacy'])
    assert frozen.save_conversation(store, 'u1', [{'role': 'user', 'content': 'explicit legacy save'}]) is True


check('provider change invalidates aggregate, valid legacy priority keeps original acknowledgment/save semantics', priority_and_change)
check('frozen privacy files remain unchanged on disk', lambda: source_before == {n: sha((ROOT / n).read_bytes()) for n in source_names} or (_ for _ in ()).throw(AssertionError('Frozen source changed')))
report = {'at': time.time(), 'scope': 'Pure binding fixtures plus transformed-in-memory actual privacy API/gateway receipt hooks. No frozen-source writes, network, builds, original DB or provider calls.', 'productionWrites': False, 'pass': all(r['pass'] for r in results), 'passed': sum(r['pass'] for r in results), 'failed': sum(not r['pass'] for r in results), 'results': results, 'bindings': bindings, 'frozenSourceHashes': source_before, 'helperHash': sha((BACKEND / 'privacy_gateway_bridge.py').read_bytes())}
output = Path(__file__).with_name('负责人优化建议-AI隐私桥接专项-python.json')
history = json.loads(output.read_text(encoding='utf-8')).get('runs', []) if output.exists() else []
history.append(report)
output.write_text(json.dumps({'latest': report, 'runs': history}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'pass': report['pass'], 'passed': report['passed'], 'failed': report['failed']}))
sys.exit(0 if report['pass'] else 1)
