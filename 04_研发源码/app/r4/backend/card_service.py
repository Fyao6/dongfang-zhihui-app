"""Versioned, account-scoped authoritative wisdom-card draws. No deck or production rule is seeded."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

THEMES = ('life', 'body', 'mind')
LOCALES = ('zh', 'zh-Hant', 'en', 'bo')
TEXT_FIELDS = ('name', 'prompt', 'meaning', 'question', 'action')
PRACTICES = ('breath', 'scan', 'ground', 'focus', 'sleep')
RULES = {'version': '', 'confirmed': False, 'expectedCount': None, 'dailyLimit': None, 'dayBoundary': None, 'randomMode': None, 'timezoneChangeCooldownHours': None, 'withdrawalPolicy': None}
DEFAULT = {'revision': 0, 'enabled': False, 'sandboxEnabled': False, 'productionEnabled': False, 'activeSandboxDeck': '', 'activeProductionDeck': '', 'sandboxRules': RULES, 'productionRules': RULES}
DDL = '''
CREATE TABLE IF NOT EXISTS card_deck_versions(id TEXT PRIMARY KEY,deck_id TEXT NOT NULL,version INTEGER NOT NULL,environment TEXT NOT NULL,status TEXT NOT NULL,revision INTEGER NOT NULL,data TEXT NOT NULL,withdrawal_kind TEXT NOT NULL DEFAULT '',withdrawal_reason TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(deck_id,version,environment));
CREATE TABLE IF NOT EXISTS card_zone_preferences(owner TEXT NOT NULL,environment TEXT NOT NULL,zone TEXT NOT NULL,pending_zone TEXT NOT NULL,pending_at INTEGER NOT NULL,last_changed INTEGER NOT NULL,revision INTEGER NOT NULL,PRIMARY KEY(owner,environment));
CREATE TABLE IF NOT EXISTS card_draws(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL,business_date TEXT NOT NULL,zone TEXT NOT NULL,deck_version_id TEXT NOT NULL,card_id TEXT NOT NULL,rules_version TEXT NOT NULL,snapshot TEXT NOT NULL,request_id TEXT NOT NULL,next_eligible_at INTEGER NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,environment,business_date));
CREATE TABLE IF NOT EXISTS card_draw_requests(owner TEXT NOT NULL,environment TEXT NOT NULL,request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,draw_id TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(owner,environment,request_id));
CREATE TABLE IF NOT EXISTS card_daily_quota(owner TEXT NOT NULL,environment TEXT NOT NULL,business_date TEXT NOT NULL,next_eligible_at INTEGER NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(owner,environment,business_date));
CREATE TABLE IF NOT EXISTS card_record_epochs(owner TEXT PRIMARY KEY,revision INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS card_draw_actions(owner TEXT NOT NULL,draw_id TEXT NOT NULL,favorite INTEGER NOT NULL DEFAULT 0,note TEXT NOT NULL DEFAULT '',revision INTEGER NOT NULL DEFAULT 0,updated INTEGER NOT NULL,PRIMARY KEY(owner,draw_id));
CREATE TABLE IF NOT EXISTS card_practice_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,draw_id TEXT NOT NULL,request_id TEXT NOT NULL,practice_key TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,request_id));
CREATE INDEX IF NOT EXISTS card_draws_owner ON card_draws(owner,created);
'''


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True, allow_nan=False)


def init_schema(db):
    db.executescript(DDL)
    db.execute('INSERT OR IGNORE INTO card_daily_quota SELECT owner,environment,business_date,next_eligible_at,created FROM card_draws')


def privacy_export(db, owner):
    return {'cardDraws': [dict(r) for r in db.execute('SELECT id,environment,business_date,zone,deck_version_id,card_id,rules_version,next_eligible_at,created FROM card_draws WHERE owner=?', (owner,))], 'cardActions': [dict(r) for r in db.execute('SELECT draw_id,favorite,note,revision,updated FROM card_draw_actions WHERE owner=?', (owner,))], 'cardPracticeOpenings': [dict(r) for r in db.execute('SELECT draw_id,practice_key,created FROM card_practice_events WHERE owner=?', (owner,))], 'cardQuota': [dict(r) for r in db.execute('SELECT environment,business_date,next_eligible_at FROM card_daily_quota WHERE owner=?', (owner,))], 'cardTimezonePreferences': [dict(r) for r in db.execute('SELECT environment,zone,pending_zone,pending_at,last_changed,revision FROM card_zone_preferences WHERE owner=?', (owner,))], 'cardRecordErasureState': [dict(r) for r in db.execute('SELECT revision,updated FROM card_record_epochs WHERE owner=?', (owner,))]}


def privacy_delete_records(db, owner):
    db.execute('INSERT INTO card_record_epochs VALUES(?,1,?) ON CONFLICT(owner) DO UPDATE SET revision=revision+1,updated=excluded.updated', (owner, time.time_ns() // 1_000_000))
    counts = {table: db.execute('DELETE FROM ' + table + ' WHERE owner=?', (owner,)).rowcount for table in ('card_draw_actions', 'card_practice_events', 'card_draw_requests', 'card_draws')}
    return {'deletedCounts': counts, 'retained': ['minimal-daily-card-quota', 'card-timezone-preferences', 'card-record-erasure-epoch'], 'retentionDays': None, 'notice': '保留最小当日防重额度、时区与删除代际；不保留卡义或感受，保留期限待项目方确认。'}


def configuration(store):
    raw = store.setting('card_service')
    value = copy.deepcopy(DEFAULT)
    value.update({k: v for k, v in raw.items() if k in DEFAULT})
    for key in ('sandboxRules', 'productionRules'):
        value[key] = {**RULES, **(raw.get(key) or {})}
    return value


def media_allowed(db, reference, owner=None):
    """For root's existing media ACL hook; published decks only or owner-held ordinary withdrawn history."""
    cfg_row = db.execute("SELECT data FROM settings WHERE key='card_service'").fetchone()
    cfg = json.loads(cfg_row['data']) if cfg_row else DEFAULT
    rows = db.execute("SELECT v.* FROM card_deck_versions v,json_each(v.data,'$.cards') c WHERE json_extract(c.value,'$.frontUrl')=? OR json_extract(c.value,'$.backUrl')=?", (reference, reference)).fetchall()
    for row in rows:
        if row['status'] == 'published' and cfg.get('enabled') and cfg.get(row['environment'] + 'Enabled'):
            return True
        if owner and row['status'] == 'withdrawn' and row['withdrawal_kind'] == 'ordinary' and db.execute('SELECT 1 FROM card_draws WHERE owner=? AND deck_version_id=? LIMIT 1', (owner, row['id'])).fetchone():
            return True
    return False


class CardService:
    def __init__(self, store, handler, error, limiter, *, test_clock=None, test_randbelow=None):
        self.store, self.h, self.Error, self.rate = store, handler, error, limiter
        self.owner = handler.user['id'] if handler.user else ''
        self.clock = test_clock or (lambda: time.time_ns() // 1_000_000)
        self.randbelow = test_randbelow or secrets.randbelow

    def fail(self, status, message):
        raise self.Error(status, message)

    def text(self, value, maximum, minimum=0):
        if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
            self.fail(400, '抽卡文字字段格式或长度不正确。')
        return value.strip()

    def integer(self, value, minimum=0, maximum=500):
        if type(value) is not int or not minimum <= value <= maximum:
            self.fail(400, '抽卡数值须为明确的范围内整数。')
        return value

    def environment(self, value):
        if value not in ('sandbox', 'production'):
            self.fail(400, '抽卡环境须明确为sandbox或production。')
        return value

    def rules(self, cfg, environment):
        return cfg[environment + 'Rules']

    def ready_rules(self, rules):
        return bool(rules['confirmed'] is True and rules['version'] and type(rules['expectedCount']) is int and 1 <= rules['expectedCount'] <= 500 and rules['dailyLimit'] == 1 and type(rules['dailyLimit']) is int and rules['dayBoundary'] == 'user-timezone-natural-day' and rules['randomMode'] == 'uniform' and type(rules['timezoneChangeCooldownHours']) is int and 1 <= rules['timezoneChangeCooldownHours'] <= 8760 and rules['withdrawalPolicy'] == 'notice-withhold-on-issue')

    def clean_rules(self, value):
        if not isinstance(value, dict) or set(value) != set(RULES) or type(value['confirmed']) is not bool:
            self.fail(400, '规则字段须完整，未确认项保留null。')
        result = {**value, 'version': self.text(value['version'], 100)}
        for key in ('expectedCount', 'dailyLimit', 'timezoneChangeCooldownHours'):
            if value[key] is not None:
                self.integer(value[key], 1, 8760 if key == 'timezoneChangeCooldownHours' else 500)
        for key, expected in (('dayBoundary', 'user-timezone-natural-day'), ('randomMode', 'uniform'), ('withdrawalPolicy', 'notice-withhold-on-issue')):
            if value[key] is not None and value[key] != expected:
                self.fail(400, '该日界、随机或下架策略尚未实现，不能写成已支持规则。')
        if result['confirmed'] and not self.ready_rules(result):
            self.fail(409, '首期仅实现明确确认的每日一次、本人时区自然日、均匀随机与时区冷却规则；不得把未定规则当作确认。')
        return result

    def local_media(self, db, value, retained=()):
        value = self.text(value, 1500)
        if not value:
            return {'url': '', 'typeChecked': False, 'ownership': 'missing', 'dimensionsVerified': False}
        match = re.fullmatch('/api/media/([a-f0-9-]{36})', value)
        if match:
            row = db.execute('SELECT owner,mime FROM media WHERE id=?', (match.group(1),)).fetchone()
            if not row or not row['mime'].startswith('image/'):
                self.fail(400, '卡面与卡背须为真实上传的图片素材。')
            if row['owner'] != self.owner and value not in retained:
                self.fail(403, '新增本地卡图只能绑定当前管理员上传的素材。')
            return {'url': value, 'typeChecked': True, 'ownership': 'current-uploader' if row['owner'] == self.owner else 'retained-approved-reference', 'dimensionsVerified': False}
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            self.fail(400, '卡图地址须为本项目图片或HTTPS，不接受带凭据地址。')
        return {'url': value, 'typeChecked': False, 'ownership': 'external-declaration-not-fetched', 'dimensionsVerified': False}

    def clean_deck(self, db, data, retained=(), complete=False):
        allowed = {'name', 'system', 'expectedCount', 'cards', 'rightsReference', 'artReviewNote'}
        if not isinstance(data, dict) or set(data) - allowed or data.get('system') != 'daily-wisdom':
            self.fail(400, '当前仅实现每日智慧卡；其他体系须另行确认规则，不能只改名称。')
        cards = data.get('cards')
        if not isinstance(cards, list) or len(cards) > 500:
            self.fail(400, '卡组须为不超过500项的数组。')
        count = data.get('expectedCount')
        if count is not None:
            self.integer(count, 1, 500)
        clean = []
        for card in cards:
            fields = {'id', 'theme', 'text', 'frontUrl', 'backUrl', 'alt', 'author', 'licenseReference', 'licenseScope', 'practiceKey', 'courseId', 'actionSeconds', 'sandboxOnly'}
            if not isinstance(card, dict) or set(card) - fields:
                self.fail(400, '卡片包含未知字段。')
            cid = self.text(card.get('id'), 100, 1)
            if not re.fullmatch(r'[A-Za-z0-9_-]+', cid) or card.get('theme') not in THEMES or type(card.get('sandboxOnly')) is not bool:
                self.fail(400, '卡片ID、主题或沙箱标识不正确。')
            texts = card.get('text', {})
            if not isinstance(texts, dict) or set(texts) - set(LOCALES):
                self.fail(400, '文案语言字段不正确。')
            localized = {}
            for lang, value in texts.items():
                if not isinstance(value, dict) or set(value) != set(TEXT_FIELDS):
                    self.fail(400, '每个语言须列卡名、提示、卡义、自问和行动。')
                localized[lang] = {k: self.text(v, 2000 if k == 'meaning' else 800, 1 if complete else 0) for k, v in value.items()}
            if complete and any(lang not in localized for lang in ('zh', 'zh-Hant', 'en')):
                self.fail(409, '发布前须有完整简体、繁体、英文审核文案。')
            alt = card.get('alt', {})
            if not isinstance(alt, dict) or set(alt) - set(LOCALES):
                self.fail(400, '图片替代文本语言不正确。')
            alt = {k: self.text(v, 500, 1 if complete else 0) for k, v in alt.items()}
            if complete and any(not alt.get(lang) for lang in ('zh', 'zh-Hant', 'en')):
                self.fail(409, '发布前须列三语言图片替代文本。')
            front, back = self.local_media(db, card.get('frontUrl', ''), retained), self.local_media(db, card.get('backUrl', ''), retained)
            if complete and (not front['url'] or not back['url']):
                self.fail(409, '卡面和统一卡背资料尚未齐全。')
            practice = self.text(card.get('practiceKey', ''), 50)
            if practice and practice not in PRACTICES:
                self.fail(400, '练习入口不在现有真实练习清单中。')
            course = self.text(card.get('courseId', ''), 100)
            if course and not db.execute("SELECT 1 FROM contents WHERE kind='courses' AND id=? AND status='published'", (course,)).fetchone():
                self.fail(400, '关联课程必须真实存在并已发布。')
            seconds = card.get('actionSeconds')
            if seconds is not None:
                self.integer(seconds, 1, 180)
            clean.append({'id': cid, 'theme': card['theme'], 'text': localized, 'frontUrl': front['url'], 'backUrl': back['url'], 'alt': alt, 'author': self.text(card.get('author', ''), 200, 1 if complete else 0), 'licenseReference': self.text(card.get('licenseReference', ''), 1000, 1 if complete else 0), 'licenseScope': self.text(card.get('licenseScope', ''), 1000, 1 if complete else 0), 'practiceKey': practice, 'courseId': course, 'actionSeconds': seconds, 'sandboxOnly': card['sandboxOnly'], 'mediaChecks': {'front': front, 'back': back}})
        if len({c['id'] for c in clean}) != len(clean):
            self.fail(409, '卡组中卡ID不得重复。')
        if complete and (count is None or len(clean) != count or not clean or len({c['backUrl'] for c in clean}) != 1):
            self.fail(409, '须核足最终预期张数，且全卡组使用统一卡背；不能默认认作36张。')
        return {'name': self.text(data.get('name', ''), 160, 1 if complete else 0), 'system': 'daily-wisdom', 'expectedCount': count, 'cards': clean, 'rightsReference': self.text(data.get('rightsReference', ''), 2000, 1 if complete else 0), 'artReviewNote': self.text(data.get('artReviewNote', ''), 2000), 'verification': {'rights': 'manual-review-record-not-system-verified', 'externalImagesFetched': False, 'imageDimensionsVerified': False}}

    def deck(self, db, identifier):
        row = db.execute('SELECT * FROM card_deck_versions WHERE id=?', (identifier,)).fetchone()
        if not row:
            self.fail(404, '卡组版本不存在。')
        return row

    def deck_item(self, row):
        return {'id': row['id'], 'deckId': row['deck_id'], 'version': row['version'], 'revision': row['revision'], 'environment': row['environment'], 'status': row['status'], 'data': json.loads(row['data']), 'withdrawal': {'kind': row['withdrawal_kind'], 'reason': row['withdrawal_reason']}, 'createdAt': row['created'], 'updatedAt': row['updated']}

    def zone(self, db, environment):
        row = db.execute('SELECT * FROM card_zone_preferences WHERE owner=? AND environment=?', (self.owner, environment)).fetchone()
        if row and row['pending_zone'] and row['pending_at'] <= self.clock():
            db.execute("UPDATE card_zone_preferences SET zone=pending_zone,pending_zone='',pending_at=0,revision=revision+1 WHERE owner=? AND environment=? AND revision=?", (self.owner, environment, row['revision']))
            row = db.execute('SELECT * FROM card_zone_preferences WHERE owner=? AND environment=?', (self.owner, environment)).fetchone()
        return {'timezone': row['zone'], 'pendingTimezone': row['pending_zone'] or None, 'effectiveAt': row['pending_at'] or None, 'revision': row['revision']} if row else {'timezone': None, 'pendingTimezone': None, 'effectiveAt': None, 'revision': 0}

    def next_day(self, stamp, zone):
        current = datetime.fromtimestamp(stamp / 1000, timezone.utc).astimezone(ZoneInfo(zone))
        return int(datetime.combine(current.date() + timedelta(days=1), datetime.min.time(), ZoneInfo(zone)).timestamp() * 1000)

    def own_draw(self, db, identifier):
        row = db.execute('SELECT * FROM card_draws WHERE id=? AND owner=?', (identifier, self.owner)).fetchone()
        if not row:
            self.fail(404, '未找到本人抽取记录。')
        return row

    def erased_result(self, quota, environment):
        return {'id': None, 'environment': environment, 'sandboxOnly': environment == 'sandbox', 'authoritative': True, 'businessDate': quota['business_date'], 'resultDeleted': True, 'snapshot': None, 'nextEligibleAt': quota['next_eligible_at'], 'notice': '当日次数已使用，原结果已按本人请求清除；不会恢复内容或另抽一张。'}

    def draw_item(self, db, row):
        snapshot = json.loads(row['snapshot'])
        version = self.deck(db, row['deck_version_id'])
        withheld = version['status'] == 'withdrawn' and version['withdrawal_kind'] in ('content-error', 'license')
        action = db.execute('SELECT * FROM card_draw_actions WHERE owner=? AND draw_id=?', (self.owner, row['id'])).fetchone()
        return {'id': row['id'], 'environment': row['environment'], 'sandboxOnly': row['environment'] == 'sandbox', 'authoritative': True, 'businessDate': row['business_date'], 'timezone': row['zone'], 'deckVersionId': row['deck_version_id'], 'cardId': row['card_id'], 'rulesVersion': row['rules_version'], 'requestId': row['request_id'], 'createdAt': row['created'], 'nextEligibleAt': row['next_eligible_at'], 'snapshot': {**snapshot, 'card': None if withheld else snapshot['card']}, 'availability': {'contentVisible': not withheld, 'status': version['status'], 'reasonKind': version['withdrawal_kind'], 'notice': version['withdrawal_reason']}, 'favorite': bool(action and action['favorite']), 'note': action['note'] if action else '', 'actionRevision': action['revision'] if action else 0}

    def available(self, db, cfg, environment):
        rules = self.rules(cfg, environment)
        if not cfg['enabled'] or not cfg[environment + 'Enabled'] or not self.ready_rules(rules):
            self.fail(503, '卡组或已确认规则尚未就绪，不执行正式抽取；沙箱也须显式完整配置。')
        identifier = cfg['activeSandboxDeck' if environment == 'sandbox' else 'activeProductionDeck']
        row = self.deck(db, identifier)
        data = json.loads(row['data'])
        if row['environment'] != environment or row['status'] != 'published' or data['expectedCount'] != rules['expectedCount']:
            self.fail(503, '当前卡组版本未发布或与确认规则张数不符。')
        return row, data, rules

    def capabilities(self, environment):
        cfg = configuration(self.store)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            zone = self.zone(db, environment)
            latest = db.execute('SELECT * FROM card_daily_quota WHERE owner=? AND environment=? ORDER BY created DESC,business_date DESC LIMIT 1', (self.owner, environment)).fetchone()
            date = datetime.fromtimestamp(self.clock() / 1000, timezone.utc).astimezone(ZoneInfo(zone['timezone'])).date().isoformat() if zone['timezone'] else None
            today = db.execute('SELECT * FROM card_daily_quota WHERE owner=? AND environment=? AND business_date=?', (self.owner, environment, date)).fetchone() if date else None
            ready, deck, reason = False, None, ''
            try:
                row, data, rules = self.available(db, cfg, environment)
                deck, ready = {'id': row['id'], 'deckId': row['deck_id'], 'version': row['version'], 'name': data['name'], 'cardCount': len(data['cards']), 'backUrl': data['cards'][0]['backUrl']}, True
            except self.Error as error:
                reason = str(error)
            blocked = today or (latest if latest and latest['next_eligible_at'] > self.clock() else None)
            next_at = max(blocked['next_eligible_at'], self.next_day(self.clock(), zone['timezone']) if today else 0) if blocked and zone['timezone'] else None
            existing = db.execute('SELECT * FROM card_draws WHERE owner=? AND environment=? AND business_date=?', (self.owner, environment, blocked['business_date'])).fetchone() if blocked else None
            result = self.draw_item(db, existing) if existing else self.erased_result(blocked, environment) if blocked else None
            return {'environment': environment, 'enabled': cfg['enabled'], 'ready': ready, 'sandboxOnly': environment == 'sandbox', 'productionEnabled': cfg['productionEnabled'], 'blockingReason': reason, 'rules': self.rules(cfg, environment), 'timezone': zone, 'deck': deck, 'remaining': 0 if blocked else 1 if ready and zone['timezone'] else 0, 'nextAvailableAt': next_at, 'today': result, 'serverNow': self.clock(), 'materialsVerifiedBySystem': False}

    def draw(self, data):
        if set(data) - {'requestId', 'environment', 'theme'}:
            self.fail(400, '客户端不得指定卡ID、出生资料、权重、结果或日期。')
        environment = self.environment(data.get('environment', 'production'))
        key = self.text(data.get('requestId'), 128, 8)
        theme = data.get('theme', 'all')
        if theme not in ('all', *THEMES):
            self.fail(400, '主题不正确。')
        fingerprint = hashlib.sha256(dump({'environment': environment, 'theme': theme}).encode()).hexdigest()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM card_draw_requests WHERE owner=? AND environment=? AND request_id=?', (self.owner, environment, key)).fetchone()
            if old:
                if old['fingerprint'] != fingerprint:
                    self.fail(409, '同一请求号已用于不同的抽取内容。')
                return self.draw_item(db, self.own_draw(db, old['draw_id']))
            cfg = configuration(self.store)
            zone = self.zone(db, environment)
            if not zone['timezone']:
                self.available(db, cfg, environment)
                self.fail(409, '请先明确选择本次抽卡使用的本人时区。')
            stamp = self.clock()
            date = datetime.fromtimestamp(stamp / 1000, timezone.utc).astimezone(ZoneInfo(zone['timezone'])).date().isoformat()
            quota = db.execute('SELECT * FROM card_daily_quota WHERE owner=? AND environment=? AND business_date=?', (self.owner, environment, date)).fetchone()
            latest = db.execute('SELECT * FROM card_daily_quota WHERE owner=? AND environment=? ORDER BY created DESC,business_date DESC LIMIT 1', (self.owner, environment)).fetchone()
            quota = quota or (latest if latest and latest['next_eligible_at'] > stamp else None)
            existing = db.execute('SELECT * FROM card_draws WHERE owner=? AND environment=? AND business_date=?', (self.owner, environment, quota['business_date'])).fetchone() if quota else None
            if quota and not existing:
                return self.erased_result(quota, environment)
            if not existing:
                version, deck, rules = self.available(db, cfg, environment)
                pool = [c for c in deck['cards'] if theme == 'all' or c['theme'] == theme]
                if not pool:
                    self.fail(409, '该版本在所选主题中没有已审核卡片。')
                index = self.randbelow(len(pool))
                if type(index) is not int or not 0 <= index < len(pool):
                    self.fail(500, '随机服务未返回有效索引。')
                card = pool[index]
                public = {k: card[k] for k in ('id', 'theme', 'text', 'frontUrl', 'backUrl', 'alt', 'author', 'practiceKey', 'courseId', 'actionSeconds')}
                snapshot = {'deckId': version['deck_id'], 'deckVersion': version['version'], 'deckName': deck['name'], 'rules': rules, 'card': public, 'contentReviewed': True, 'reviewType': 'manual-admin-review', 'sandboxOnly': environment == 'sandbox'}
                identifier = str(uuid4())
                db.execute('INSERT INTO card_draws VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (identifier, self.owner, environment, date, zone['timezone'], version['id'], card['id'], rules['version'], dump(snapshot), key, self.next_day(stamp, zone['timezone']), stamp))
                db.execute('INSERT INTO card_daily_quota VALUES(?,?,?,?,?)', (self.owner, environment, date, self.next_day(stamp, zone['timezone']), stamp))
                existing = self.own_draw(db, identifier)
                self.store.audit(db, self.owner, 'cards.draw', identifier, environment + '；服务端均匀随机；无收费')
            db.execute('INSERT INTO card_draw_requests VALUES(?,?,?,?,?,?)', (self.owner, environment, key, fingerprint, existing['id'], stamp))
            return self.draw_item(db, existing)

    def admin(self, method, path):
        self.h.require(('admin',))
        if path == '/api/admin/cards' and method == 'GET':
            with self.store.connect() as db:
                return {'config': configuration(self.store), 'decks': [self.deck_item(r) for r in db.execute('SELECT * FROM card_deck_versions ORDER BY updated DESC,id').fetchall()], 'productionMaterialsVerifiedBySystem': False}
        data = self.h.body()
        if path == '/api/admin/cards/config' and method == 'PATCH':
            if set(data) != set(DEFAULT) or any(type(data[k]) is not bool for k in ('enabled', 'sandboxEnabled', 'productionEnabled')):
                self.fail(400, '抽卡配置字段须完整，启用项须为布尔。')
            clean = {**data, 'sandboxRules': self.clean_rules(data['sandboxRules']), 'productionRules': self.clean_rules(data['productionRules'])}
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                old = configuration(self.store)
                if self.integer(data['revision'], 0, 2**31 - 1) != old['revision']:
                    self.fail(409, '抽卡配置已变更，请刷新。')
                for environment, active in (('sandbox', 'activeSandboxDeck'), ('production', 'activeProductionDeck')):
                    clean[active] = self.text(clean[active], 100)
                    if clean[environment + 'Enabled']:
                        check_cfg = {**clean, 'enabled': True}
                        self.available(db, check_cfg, environment)
                clean['revision'] = old['revision'] + 1
                db.execute("INSERT INTO settings VALUES('card_service',?) ON CONFLICT(key) DO UPDATE SET data=excluded.data", (dump(clean),))
                self.store.audit(db, self.owner, 'cards.config', 'cards', '规则版本及启用条件已更新')
            return {'config': clean}
        if path == '/api/admin/cards/decks' and method == 'POST':
            allowed = {'id', 'deckId', 'version', 'revision', 'environment', 'data'}
            if set(data) - allowed:
                self.fail(400, '卡组版本包含未知字段。')
            identifier = self.text(data.get('id') or str(uuid4()), 100, 1)
            environment = self.environment(data.get('environment'))
            deck_id, version = self.text(data.get('deckId'), 100, 1), self.integer(data.get('version'), 1, 2**31 - 1)
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                old = db.execute('SELECT * FROM card_deck_versions WHERE id=?', (identifier,)).fetchone()
                retained = []
                if old:
                    if old['status'] in ('published', 'withdrawn') or old['deck_id'] != deck_id or old['environment'] != environment or old['version'] != version:
                        self.fail(409, '已发布版本内容不可修改，请新建后续版本。')
                    if type(data.get('revision')) is not int or data['revision'] != old['revision']:
                        self.fail(409, '卡组草稿已变更。')
                    retained = [c.get(k, '') for c in json.loads(old['data'])['cards'] for k in ('frontUrl', 'backUrl')]
                elif version != (db.execute('SELECT coalesce(max(version),0)+1 FROM card_deck_versions WHERE deck_id=? AND environment=?', (deck_id, environment)).fetchone()[0]):
                    self.fail(409, '新卡组须使用下一版本号。')
                content = self.clean_deck(db, data.get('data'), retained)
                if environment == 'production' and any(c['sandboxOnly'] for c in content['cards']):
                    self.fail(409, '沙箱测试卡不得发布到正式卡组。')
                content['review'] = {'status': 'pending', 'reviewerId': None, 'reference': '', 'notes': '', 'reviewedAt': None}
                stamp, revision = self.clock(), old['revision'] + 1 if old else 1
                if old:
                    db.execute("UPDATE card_deck_versions SET data=?,status='draft',revision=?,updated=? WHERE id=?", (dump(content), revision, stamp, identifier))
                else:
                    db.execute('INSERT INTO card_deck_versions VALUES(?,?,?,?,?,?,?,?,?,?,?)', (identifier, deck_id, version, environment, 'draft', revision, dump(content), '', '', stamp, stamp))
                self.store.audit(db, self.owner, 'cards.deck.draft', identifier, '内容变更需重新审核')
                return {'item': self.deck_item(self.deck(db, identifier))}
        match = re.fullmatch('/api/admin/cards/decks/([^/]+)/(review|publish|withdraw)', path)
        if match and method == 'POST':
            identifier, action = match.groups()
            expected_keys = {'review': {'revision', 'reference', 'notes'}, 'publish': {'revision'}, 'withdraw': {'revision', 'reasonKind', 'reason'}}[action]
            if set(data) - expected_keys:
                self.fail(400, '审核、发布或下架包含未知字段。')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = self.deck(db, identifier)
                if type(data.get('revision')) is not int or data['revision'] != row['revision']:
                    self.fail(409, '卡组版本已变化。')
                content = json.loads(row['data'])
                if action in ('review', 'publish'):
                    if row['status'] not in ('draft', 'reviewed'):
                        self.fail(409, '已发布或下架的版本不可再次修改审核。')
                    retained = [c[k] for c in content['cards'] for k in ('frontUrl', 'backUrl')]
                    check_data = {k: content[k] for k in ('name', 'system', 'expectedCount', 'cards', 'rightsReference', 'artReviewNote')}
                    for card in check_data['cards']:
                        card.pop('mediaChecks', None)
                    clean = self.clean_deck(db, check_data, retained, True)
                    if action == 'review':
                        clean['review'] = {'status': 'approved', 'reviewerId': self.owner, 'reference': self.text(data.get('reference'), 1000, 1), 'notes': self.text(data.get('notes', ''), 2000), 'reviewedAt': self.clock()}
                        status = 'reviewed'
                    else:
                        if row['status'] != 'reviewed' or content.get('review', {}).get('status') != 'approved':
                            self.fail(409, '发布须先完成明确的人工内容与授权资料审核。')
                        rules = self.rules(configuration(self.store), row['environment'])
                        if not self.ready_rules(rules) or rules['expectedCount'] != clean['expectedCount']:
                            self.fail(409, '卡组张数与已确认规则尚未匹配。')
                        if row['environment'] == 'production' and any(c['sandboxOnly'] for c in clean['cards']):
                            self.fail(409, '沙箱素材不能成为正式卡组。')
                        clean['review'], clean['publishedAt'] = content['review'], self.clock()
                        status = 'published'
                    db.execute('UPDATE card_deck_versions SET data=?,status=?,revision=revision+1,updated=? WHERE id=?', (dump(clean), status, self.clock(), identifier))
                else:
                    kind = data.get('reasonKind')
                    if kind not in ('ordinary', 'content-error', 'license'):
                        self.fail(400, '下架须明确普通、内容错误或授权原因。')
                    db.execute("UPDATE card_deck_versions SET status='withdrawn',withdrawal_kind=?,withdrawal_reason=?,revision=revision+1,updated=? WHERE id=?", (kind, self.text(data.get('reason'), 2000, 1), self.clock(), identifier))
                self.store.audit(db, self.owner, 'cards.deck.' + action, identifier, '保留原抽取快照，不替换结果')
                return {'item': self.deck_item(self.deck(db, identifier))}
        self.fail(404, '未找到卡组管理接口。')

    def route(self, method, path):
        if not (path.startswith('/api/cards/') or path == '/api/admin/cards' or path.startswith('/api/admin/cards/')):
            return None
        self.h.require()
        if path.startswith('/api/admin/'):
            return self.admin(method, path)
        self.rate(('cards-read:' if method == 'GET' else 'cards-write:') + self.owner, 180 if method == 'GET' else 40)
        query = parse_qs(urlsplit(self.h.path).query)
        environment = self.environment(query.get('environment', ['production'])[0])
        if path == '/api/cards/capabilities' and method == 'GET':
            return self.capabilities(environment)
        if path == '/api/cards/draws':
            if method == 'POST':
                return self.draw(self.h.body())
            if method == 'GET':
                with self.store.connect() as db:
                    rows = db.execute('SELECT * FROM card_draws WHERE owner=? AND environment=? ORDER BY created DESC,id DESC LIMIT 100', (self.owner, environment)).fetchall()
                    return {'items': [self.draw_item(db, r) for r in rows], 'environment': environment}
        if path == '/api/cards/timezone' and method == 'PATCH':
            data = self.h.body()
            if set(data) != {'environment', 'timezone', 'revision'}:
                self.fail(400, '时区设置须明确环境、本人选择和当前版本。')
            environment = self.environment(data['environment'])
            zone = self.text(data['timezone'], 100, 1)
            try:
                ZoneInfo(zone)
            except (ZoneInfoNotFoundError, ValueError):
                self.fail(400, '时区名称不可用。')
            rules = self.rules(configuration(self.store), environment)
            if not self.ready_rules(rules):
                self.fail(503, '时区及日界规则尚未确认。')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                current = self.zone(db, environment)
                if type(data['revision']) is not int or data['revision'] != current['revision']:
                    self.fail(409, '时区设置已变更。')
                old = db.execute('SELECT * FROM card_zone_preferences WHERE owner=? AND environment=?', (self.owner, environment)).fetchone()
                if old and (zone == old['zone'] or zone == old['pending_zone']):
                    return {'timezone': current}
                stamp = self.clock()
                if old:
                    if stamp < old['last_changed'] + rules['timezoneChangeCooldownHours'] * 3600000:
                        self.fail(409, '时区调整冷却期尚未结束，不会通过改时区增加抽取。')
                    latest = db.execute('SELECT max(next_eligible_at) FROM card_daily_quota WHERE owner=? AND environment=?', (self.owner, environment)).fetchone()[0] or 0
                    effective = max(self.next_day(stamp, old['zone']), latest)
                    db.execute('UPDATE card_zone_preferences SET pending_zone=?,pending_at=?,last_changed=?,revision=revision+1 WHERE owner=? AND environment=?', (zone, effective, stamp, self.owner, environment))
                else:
                    db.execute('INSERT INTO card_zone_preferences VALUES(?,?,?,?,?,?,?)', (self.owner, environment, zone, '', 0, stamp, 1))
                return {'timezone': self.zone(db, environment)}
        match = re.fullmatch('/api/cards/draws/([^/]+)(/(?:actions|practice|ai-context|share))?', path)
        if match:
            identifier, action = match.groups()
            with self.store.connect() as db:
                row = self.own_draw(db, identifier)
                result = self.draw_item(db, row)
                if not action and method == 'GET':
                    return result
                if action == '/actions' and method == 'PATCH':
                    data = self.h.body()
                    if set(data) - {'revision', 'favorite', 'note'} or type(data.get('revision')) is not int or 'favorite' in data and type(data['favorite']) is not bool:
                        self.fail(400, '收藏与感受更新字段不正确。')
                    db.execute('BEGIN IMMEDIATE')
                    row = self.own_draw(db, identifier)
                    old = db.execute('SELECT * FROM card_draw_actions WHERE owner=? AND draw_id=?', (self.owner, identifier)).fetchone()
                    if data['revision'] != (old['revision'] if old else 0):
                        self.fail(409, '收藏或感受已被其他页面更新。')
                    favorite = int(data.get('favorite', bool(old and old['favorite'])))
                    note = self.text(data.get('note', old['note'] if old else ''), 4000)
                    db.execute('INSERT INTO card_draw_actions VALUES(?,?,?,?,?,?) ON CONFLICT(owner,draw_id) DO UPDATE SET favorite=excluded.favorite,note=excluded.note,revision=excluded.revision,updated=excluded.updated', (self.owner, identifier, favorite, note, data['revision'] + 1, self.clock()))
                    return self.draw_item(db, row)
                if action in ('/ai-context', '/share', '/practice') and method == 'POST':
                    data = self.h.body()
                    card = result['snapshot']['card']
                    if not card:
                        self.fail(409, '该版本因内容或授权原因暂停展示，不能继续解读或分享。')
                    if action == '/ai-context':
                        if set(data) - {'language'} or data.get('language', 'zh') not in LOCALES:
                            self.fail(400, '卡片AI上下文不接受个人档案或客户端卡义。')
                        lang = data.get('language', 'zh')
                        used = lang if lang in card['text'] else 'en'
                        return {'context': {'category': 'card', 'fields': {'cardId': row['card_id'], 'meaning': card['text'][used]['meaning']}}, 'languageUsed': used, 'requiresSeparateAIConsentAndQuota': True, 'automaticallySent': False}
                    if action == '/share':
                        if set(data) - {'language', 'selectedText'} or data.get('language', 'zh') not in LOCALES or not isinstance(data.get('selectedText', []), list) or any(k not in TEXT_FIELDS for k in data.get('selectedText', [])):
                            self.fail(400, '分享只允许主动选择的卡片文字，不包含个人记录。')
                        lang = data.get('language', 'zh')
                        text = card['text'].get(lang) or card['text']['en']
                        return {'imageUrl': card['frontUrl'], 'imageAlt': card['alt'].get(lang) or card['alt']['en'], 'selectedText': {k: text[k] for k in dict.fromkeys(data.get('selectedText', []))}, 'languageUsed': lang if lang in card['text'] else 'en', 'personalDataIncluded': False}
                    if set(data) != {'requestId'}:
                        self.fail(400, '练习入口仅接受幂等请求号。')
                    request_id = self.text(data['requestId'], 128, 8)
                    practice = card['practiceKey']
                    if not practice:
                        self.fail(409, '该卡未关联现有练习。')
                    old = db.execute('SELECT * FROM card_practice_events WHERE owner=? AND request_id=?', (self.owner, request_id)).fetchone()
                    if old and old['draw_id'] != identifier:
                        self.fail(409, '请求号已关联另一抽卡记录。')
                    if not old:
                        inserted = db.execute('INSERT INTO card_practice_events SELECT ?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM card_draws WHERE id=? AND owner=?)', (str(uuid4()), self.owner, identifier, request_id, practice, self.clock(), identifier, self.owner))
                        if not inserted.rowcount:
                            self.fail(404, '本人抽取记录已清除。')
                    return {'practiceKey': practice, 'event': 'opened', 'completed': False, 'durationRecorded': False}
        self.fail(404, '未找到抽卡接口。')
