"""Synthetic complete sandbox deck only; no formal 36-card copy, source artwork or production DB."""
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '04_研发源码/app/r4/backend'))
import card_service as mod
results = []


class Error(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Store:
    def __init__(self):
        self.db = sqlite3.connect(':memory:', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript('CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT);CREATE TABLE media(id TEXT PRIMARY KEY,owner TEXT,mime TEXT);CREATE TABLE contents(kind TEXT,id TEXT,status TEXT);')
        mod.init_schema(self.db)
        self.db.commit()

    @contextmanager
    def connect(self):
        with self.lock:
            with self.db:
                yield self.db

    def setting(self, key):
        with self.connect() as db:
            row = db.execute('SELECT data FROM settings WHERE key=?', (key,)).fetchone()
            return json.loads(row['data']) if row else {}

    def audit(self, *args):
        pass


class Handler:
    def __init__(self, identifier, role='user'):
        self.user, self.payload, self.path = {'id': identifier, 'role': role}, {}, ''

    def require(self, roles=None):
        if not self.user:
            raise Error(401, 'login')
        if roles and self.user['role'] not in roles:
            raise Error(403, 'role')
        return self.user

    def body(self):
        return copy.deepcopy(self.payload)


def call(service, method, path, data=None):
    service.h.path, service.h.payload = path, data or {}
    return service.route(method, path.split('?')[0])


def expect(action, status):
    try:
        action()
    except Error as error:
        assert error.status in ([status] if isinstance(status, int) else status), (error.status, status)
    else:
        raise AssertionError('Expected error ' + str(status))


def fixture():
    store, clock, random_calls = Store(), [int(datetime(2026, 11, 12, 12, tzinfo=timezone.utc).timestamp() * 1000)], []
    def random_index(n):
        random_calls.append(n)
        return 0
    def service(user, role='user'):
        return mod.CardService(store, Handler(user, role), Error, lambda *args: None, test_clock=lambda: clock[0], test_randbelow=random_index)
    admin, user, other = service('admin', 'admin'), service('u1'), service('u2')
    rules = {**mod.RULES, 'version': 'sandbox-rules-1', 'confirmed': True, 'expectedCount': 3, 'dailyLimit': 1, 'dayBoundary': 'user-timezone-natural-day', 'randomMode': 'uniform', 'timezoneChangeCooldownHours': 24, 'withdrawalPolicy': 'notice-withhold-on-issue'}
    cfg = copy.deepcopy(mod.DEFAULT)
    cfg['sandboxRules'] = rules
    cfg = call(admin, 'PATCH', '/api/admin/cards/config', cfg)['config']
    cards = []
    for index, theme in enumerate(mod.THEMES):
        text = {lang: {'name': 'Sandbox card ' + str(index), 'prompt': 'Synthetic fixture only', 'meaning': 'Synthetic reviewed sandbox meaning; not formal wisdom-card copy.', 'question': 'What does this test verify?', 'action': 'Open a real short practice if you choose.'} for lang in ('zh', 'zh-Hant', 'en')}
        cards.append({'id': 'sandbox-card-' + str(index), 'theme': theme, 'text': text, 'frontUrl': 'https://fixture.invalid/card-' + str(index) + '.png', 'backUrl': 'https://fixture.invalid/back.png', 'alt': {lang: 'Synthetic sandbox artwork, not formal material' for lang in ('zh', 'zh-Hant', 'en')}, 'author': 'Synthetic fixture author', 'licenseReference': 'QA-fixture-only; not a production license', 'licenseScope': 'sandbox-only', 'practiceKey': 'breath', 'courseId': '', 'actionSeconds': 60, 'sandboxOnly': True})
    payload = {'deckId': 'sandbox', 'version': 1, 'environment': 'sandbox', 'data': {'name': 'Explicit QA deck, not the proposed 36 cards', 'system': 'daily-wisdom', 'expectedCount': 3, 'cards': cards, 'rightsReference': 'QA fixture only', 'artReviewNote': 'External fixture links are not fetched or dimension-verified'}}
    item = call(admin, 'POST', '/api/admin/cards/decks', payload)['item']
    item = call(admin, 'POST', '/api/admin/cards/decks/' + item['id'] + '/review', {'revision': item['revision'], 'reference': 'QA-manual-review-only'})['item']
    item = call(admin, 'POST', '/api/admin/cards/decks/' + item['id'] + '/publish', {'revision': item['revision']})['item']
    cfg.update({'activeSandboxDeck': item['id'], 'enabled': True, 'sandboxEnabled': True})
    cfg = call(admin, 'PATCH', '/api/admin/cards/config', cfg)['config']
    for actor in (user, other):
        call(actor, 'PATCH', '/api/cards/timezone', {'environment': 'sandbox', 'timezone': 'UTC', 'revision': 0})
    return store, admin, user, other, clock, random_calls, cfg, payload, item


def check(name, function):
    try:
        function()
        results.append({'name': name, 'pass': True})
    except Exception:
        results.append({'name': name, 'pass': False, 'error': traceback.format_exc()})


def defaults():
    store = Store()
    cfg = mod.configuration(store)
    assert not cfg['enabled'] and not cfg['sandboxEnabled'] and not cfg['productionEnabled']
    assert all(cfg['productionRules'][k] is None for k in ('expectedCount', 'dailyLimit', 'dayBoundary', 'randomMode'))
    assert store.db.execute('SELECT count(*) FROM card_deck_versions').fetchone()[0] == 0


check('defaults are closed with unknown rules and no seeded formal deck', defaults)


def draw_idempotence():
    s, admin, u, other, clock, random, cfg, payload, item = fixture()
    first = call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'draw-request-1', 'theme': 'all'})
    assert first['authoritative'] and first['sandboxOnly']
    assert call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'draw-request-1', 'theme': 'all'})['id'] == first['id']
    expect(lambda: call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'draw-request-1', 'theme': 'body'}), 409)
    assert call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'new-request-id', 'theme': 'mind'})['id'] == first['id']
    assert random == [3]
    for value in ('', None, False):
        expect(lambda value=value: call(u, 'POST', '/api/cards/draws', {'environment': value, 'requestId': 'invalid-env'}), 400)
        expect(lambda value=value: call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'invalid-theme', 'theme': value}), 400)
    assert s.db.execute('SELECT count(*) FROM card_draws WHERE owner=?', ('u1',)).fetchone()[0] == 1
    cap = call(u, 'GET', '/api/cards/capabilities?environment=sandbox')
    assert cap['remaining'] == 0 and cap['nextAvailableAt'] > clock[0]
    expect(lambda: call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'client-picks-card', 'cardId': 'sandbox-card-2'}), 400)


check('server result, idempotency, theme changes and quota have one draw only', draw_idempotence)


def concurrent():
    s, admin, u, other, clock, random, cfg, payload, item = fixture()
    def task(index):
        actor = mod.CardService(s, Handler('u1'), Error, lambda *args: None, test_clock=lambda: clock[0], test_randbelow=lambda n: (random.append(n) or 0))
        return call(actor, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'parallel-request-' + str(index)})
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(task, (1, 2)))
    assert values[0]['id'] == values[1]['id'] and len(random) == 1
    assert s.db.execute('SELECT count(*) FROM card_daily_quota').fetchone()[0] == 1


check('concurrent different request IDs still produce one authoritative daily result', concurrent)


def snapshots_and_withdrawal():
    s, admin, u, other, clock, random, cfg, payload, item = fixture()
    first = call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'original-draw-1'})
    expect(lambda: call(admin, 'POST', '/api/admin/cards/decks', {**payload, 'id': item['id'], 'revision': item['revision']}), 409)
    changed = copy.deepcopy(payload)
    changed['version'] = 2
    changed['data']['cards'][0]['text']['zh']['name'] = 'Changed sandbox version'
    new = call(admin, 'POST', '/api/admin/cards/decks', changed)['item']
    new = call(admin, 'POST', '/api/admin/cards/decks/' + new['id'] + '/review', {'revision': new['revision'], 'reference': 'QA-new-version'})['item']
    new = call(admin, 'POST', '/api/admin/cards/decks/' + new['id'] + '/publish', {'revision': new['revision']})['item']
    cfg['activeSandboxDeck'] = new['id']
    call(admin, 'PATCH', '/api/admin/cards/config', cfg)
    assert call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'after-version-update'})['id'] == first['id']
    assert call(u, 'GET', '/api/cards/draws/' + first['id'])['snapshot']['card']['text']['zh']['name'] != 'Changed sandbox version'
    call(admin, 'POST', '/api/admin/cards/decks/' + item['id'] + '/withdraw', {'revision': item['revision'], 'reasonKind': 'license', 'reason': 'Synthetic license withdrawal, not reroll'})
    historical = call(u, 'GET', '/api/cards/draws/' + first['id'])
    assert historical['id'] == first['id'] and historical['snapshot']['card'] is None
    assert historical['availability']['notice']
    expect(lambda: call(u, 'POST', '/api/cards/draws/' + first['id'] + '/ai-context', {}), 409)
    assert json.loads(s.db.execute('SELECT snapshot FROM card_draws WHERE id=?', (first['id'],)).fetchone()[0])['card']['id'] == first['cardId']


check('published versions are immutable; updated decks and withdrawals never reroll history', snapshots_and_withdrawal)


def actions_and_privacy():
    s, admin, u, other, clock, random, cfg, payload, item = fixture()
    draw = call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'actions-draw-1'})
    route = '/api/cards/draws/' + draw['id']
    saved = call(u, 'PATCH', route + '/actions', {'revision': 0, 'favorite': True, 'note': 'PRIVATE_PERSONAL_NOTE'})
    assert saved['favorite'] and saved['note'] == 'PRIVATE_PERSONAL_NOTE'
    expect(lambda: call(u, 'PATCH', route + '/actions', {'revision': 0, 'note': 'stale'}), 409)
    expect(lambda: call(other, 'GET', route), 404)
    context = call(u, 'POST', route + '/ai-context', {'language': 'en'})
    assert set(context['context']['fields']) == {'cardId', 'meaning'} and not context['automaticallySent']
    assert 'PRIVATE_PERSONAL_NOTE' not in json.dumps(context)
    for value in (False, None, ''):
        expect(lambda value=value: call(u, 'POST', route + '/ai-context', {'language': value}), 400)
        expect(lambda value=value: call(u, 'POST', route + '/share', {'selectedText': value}), 400)
    expect(lambda: call(u, 'PATCH', route + '/actions', {'revision': 1, 'note': None}), 400)
    share = call(u, 'POST', route + '/share', {})
    assert share['selectedText'] == {} and share['personalDataIncluded'] is False
    assert 'PRIVATE_PERSONAL_NOTE' not in json.dumps(share)
    expect(lambda: call(u, 'POST', route + '/share', {'selectedText': ['note']}), 400)
    practice = call(u, 'POST', route + '/practice', {'requestId': 'practice-request-1'})
    call(u, 'POST', route + '/practice', {'requestId': 'practice-request-1'})
    assert practice['completed'] is False and practice['durationRecorded'] is False
    assert s.db.execute('SELECT count(*) FROM card_practice_events').fetchone()[0] == 1
    with s.connect() as db:
        erased = mod.privacy_delete_records(db, 'u1')
    assert erased['deletedCounts']['card_draws'] == 1
    result = call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'after-erasure-draw'})
    assert result['resultDeleted'] and result['snapshot'] is None and random == [3]
    assert call(u, 'GET', '/api/cards/capabilities?environment=sandbox')['remaining'] == 0
    changed = copy.deepcopy(payload)
    changed['version'] = 2
    replacement = call(admin, 'POST', '/api/admin/cards/decks', changed)['item']
    replacement = call(admin, 'POST', '/api/admin/cards/decks/' + replacement['id'] + '/review', {'revision': replacement['revision'], 'reference': 'QA-after-erasure-version'})['item']
    replacement = call(admin, 'POST', '/api/admin/cards/decks/' + replacement['id'] + '/publish', {'revision': replacement['revision']})['item']
    call(admin, 'PATCH', '/api/admin/cards/config', {**cfg, 'activeSandboxDeck': replacement['id']})
    for theme in ('life', 'body', 'mind'):
        assert call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'after-deck-erasure-' + theme, 'theme': theme})['resultDeleted']
    assert s.db.execute('SELECT count(*) FROM card_draws WHERE owner=?', ('u1',)).fetchone()[0] == 0
    assert s.db.execute('SELECT count(*) FROM card_zone_preferences WHERE owner=?', ('u1',)).fetchone()[0] == 1
    assert 'PRIVATE_PERSONAL_NOTE' not in json.dumps(mod.privacy_export(s.db, 'u1'))


check('owner actions/practice/minimal AI/share and erasure preserve quota without restoring private content', actions_and_privacy)


def timezone_and_dst():
    s, admin, u, other, clock, random, cfg, payload, item = fixture()
    draw = call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'timezone-initial'})
    expect(lambda: call(u, 'PATCH', '/api/cards/timezone', {'environment': 'sandbox', 'timezone': 'Asia/Tokyo', 'revision': 1}), 409)
    clock[0] += 86400001
    zone = call(u, 'PATCH', '/api/cards/timezone', {'environment': 'sandbox', 'timezone': 'Asia/Tokyo', 'revision': 1})['timezone']
    assert zone['timezone'] == 'UTC' and zone['effectiveAt'] > clock[0] and zone['effectiveAt'] >= draw['nextEligibleAt']
    second = call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'timezone-before-effective'})
    assert second['timezone'] == 'UTC'
    clock[0] = zone['effectiveAt']
    third = call(u, 'POST', '/api/cards/draws', {'environment': 'sandbox', 'requestId': 'timezone-after-effective'})
    assert third['timezone'] == 'Asia/Tokyo' and third['createdAt'] >= second['nextEligibleAt']
    for date, expected in ((datetime(2026, 3, 8, tzinfo=ZoneInfo('America/New_York')), 23), (datetime(2026, 11, 1, tzinfo=ZoneInfo('America/New_York')), 25)):
        stamp = int(date.timestamp() * 1000)
        assert u.next_day(stamp, 'America/New_York') - stamp == expected * 3600000


check('timezone cooldown/effective boundary cannot advance eligibility; DST uses natural-day boundaries', timezone_and_dst)


def publishing_and_media():
    s, admin, u, other, clock, random, cfg, payload, item = fixture()
    expect(lambda: call(u, 'GET', '/api/admin/cards'), 403)
    expect(lambda: call(admin, 'PATCH', '/api/admin/cards/config', {**cfg, 'productionEnabled': True}), 503)
    expect(lambda: call(u, 'POST', '/api/cards/draws', {'environment': 'production', 'requestId': 'production-not-ready'}), 503)
    invalid = copy.deepcopy(payload)
    invalid['version'] = 2
    invalid['environment'] = 'production'
    invalid['version'] = 1
    expect(lambda: call(admin, 'POST', '/api/admin/cards/decks', invalid), 409)
    image = '12345678-1234-4234-8234-123456789012'
    s.db.execute('INSERT INTO media VALUES(?,?,?)', (image, 'u2', 'image/jpeg'))
    s.db.commit()
    invalid = copy.deepcopy(payload)
    invalid['version'] = 2
    invalid['data']['cards'][0]['frontUrl'] = '/api/media/' + image
    expect(lambda: call(admin, 'POST', '/api/admin/cards/decks', invalid), 403)
    item_data = item['data']
    assert item_data['verification']['imageDimensionsVerified'] is False
    assert item_data['verification']['rights'] == 'manual-review-record-not-system-verified'
    assert item_data['cards'][0]['mediaChecks']['front']['typeChecked'] is False


check('publication gates do not seed/enable production or claim external artwork verification', publishing_and_media)
report = {'scope': 'Python in-memory explicit synthetic sandbox deck; no public integration, build, original DB, actual card content or production enablement.', 'productionWrites': False, 'passed': sum(r['pass'] for r in results), 'failed': sum(not r['pass'] for r in results), 'pass': all(r['pass'] for r in results), 'results': results, 'sourceSha256': hashlib.sha256((ROOT / '04_研发源码/app/r4/backend/card_service.py').read_bytes()).hexdigest()}
output = Path(__file__).with_suffix('.json')
history = json.loads(output.read_text(encoding='utf8')).get('runs', []) if output.exists() else []
history.append(report)
output.write_text(json.dumps({'latest': report, 'runs': history}, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({k: report[k] for k in ('pass', 'passed', 'failed')}))
sys.exit(0 if report['pass'] else 1)
