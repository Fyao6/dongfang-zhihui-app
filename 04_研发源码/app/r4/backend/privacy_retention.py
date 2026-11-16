from memory_service import memory_cleanup_statements, append_memory_cleanup
"""Bounded local retention. No invented historical ages or provider/backup erasure."""
import json
import re
import time
from uuid import uuid4

SCOPES = ('records', 'conversations', 'timer', 'activity', 'measurements', 'cards', 'memory')
FLAGS = dict.fromkeys(('chart', 'wellbeing', 'saveConversations', 'longTermMemory', 'trainingImprovement', 'marketing'), False)
DEFAULT = {'enabled': False, 'policyVersion': '', 'revision': 0, 'retentionDays': dict.fromkeys(SCOPES[2:])}
NOW_SQL = "(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))"
RETAINED = ['account', 'device-connections-retained-policy-unconfirmed', 'financial-and-fulfilment-ledgers', 'membership-and-commission', 'after-sales-and-case-finance','payment-support-metadata', 'ai-quota-and-attempt-metadata', 'card-daily-quota-timezone-epoch', 'source-audits', 'public-works-and-community-messages']
DDL = [
 'CREATE TABLE IF NOT EXISTS privacy_retention_tracking(owner TEXT NOT NULL,scope TEXT NOT NULL,k1 TEXT NOT NULL,k2 TEXT NOT NULL,write_at INTEGER NOT NULL,version INTEGER NOT NULL,nonce TEXT NOT NULL,basis TEXT NOT NULL,PRIMARY KEY(owner,scope,k1,k2))',
 'CREATE TABLE IF NOT EXISTS privacy_retention_jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,actor TEXT NOT NULL,request_id TEXT NOT NULL,scopes TEXT NOT NULL,as_of INTEGER NOT NULL,policy_data TEXT NOT NULL,executor_data TEXT NOT NULL,pref_revision INTEGER NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL,summary TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(actor,request_id))',
 'CREATE TABLE IF NOT EXISTS privacy_retention_targets(job_id TEXT NOT NULL,owner TEXT NOT NULL,scope TEXT NOT NULL,k1 TEXT NOT NULL,k2 TEXT NOT NULL,write_at INTEGER NOT NULL,version INTEGER NOT NULL,nonce TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(job_id,scope,k1,k2))',
 'CREATE TABLE IF NOT EXISTS privacy_retention_receipts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,operation_id TEXT NOT NULL,nonce TEXT NOT NULL,status TEXT NOT NULL,details TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,operation_id))',
 'CREATE TABLE IF NOT EXISTS privacy_retention_config(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL)',
 'CREATE TABLE IF NOT EXISTS privacy_record_epochs(owner TEXT PRIMARY KEY,revision INTEGER NOT NULL,updated INTEGER NOT NULL)',
 "INSERT OR IGNORE INTO privacy_retention_config VALUES(1,'{\"enabled\":false,\"policyVersion\":\"\",\"revision\":0,\"retentionDays\":{\"timer\":null,\"activity\":null,\"measurements\":null,\"cards\":null}}')",
 'CREATE INDEX IF NOT EXISTS privacy_retention_target_pending ON privacy_retention_targets(job_id,processed,scope,k1,k2)',
]


def dump(v):
    return json.dumps(v, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def stamp():
    return time.time_ns() // 1_000_000


def tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def tracking_ddl(available):
    result = []
    for scope in SCOPES:
        table, owner, k1, k2 = source(scope)
        if table not in available:
            continue
        new2, old2 = 'NEW.' + k2 if k2 else "''", 'OLD.' + k2 if k2 else "''"
        new_owner, old_owner = owner_expr(scope, 'NEW'), owner_expr(scope, 'OLD')
        for action in ('INSERT', 'UPDATE'):
            result.append(f"CREATE TRIGGER IF NOT EXISTS retention_track_{table}_{action.lower()} AFTER {action} ON {table} BEGIN INSERT INTO privacy_retention_tracking VALUES({new_owner},'{scope}',NEW.{k1},{new2},{NOW_SQL},1,lower(hex(randomblob(16))),'observed-write') ON CONFLICT(owner,scope,k1,k2) DO UPDATE SET write_at=excluded.write_at,version=privacy_retention_tracking.version+1,nonce=excluded.nonce,basis=excluded.basis; END")
        result.append(f"CREATE TRIGGER IF NOT EXISTS retention_track_{table}_delete AFTER DELETE ON {table} BEGIN DELETE FROM privacy_retention_tracking WHERE owner={old_owner} AND scope='{scope}' AND k1=OLD.{k1} AND k2={old2}; END")
    for table in ('card_draw_actions', 'card_practice_events'):
        if table in available and 'card_draws' in available:
            for action in ('INSERT', 'UPDATE'):
                result.append(f"CREATE TRIGGER IF NOT EXISTS retention_track_{table}_{action.lower()} AFTER {action} ON {table} BEGIN INSERT INTO privacy_retention_tracking SELECT owner,'cards',id,'',{NOW_SQL},1,lower(hex(randomblob(16))),'observed-write' FROM card_draws WHERE id=NEW.draw_id AND owner=NEW.owner ON CONFLICT(owner,scope,k1,k2) DO UPDATE SET write_at=excluded.write_at,version=privacy_retention_tracking.version+1,nonce=excluded.nonce,basis=excluded.basis; END")
    return result


def init_schema(db):
    # Startup only. Does not commit an enclosing account-closure transaction.
    for sql in DDL + tracking_ddl(tables(db)):
        db.execute(sql)


def receipt_item(row):
    return {'id': row['id'], 'operationId': row['operation_id'], 'status': row['status'], 'createdAt': row['created'], 'details': json.loads(row['details'])}


def fence(receipt, owner, nonce):
    return ('EXISTS(SELECT 1 FROM privacy_retention_receipts WHERE id=? AND owner=? AND nonce=? AND status=\'claimed\')', [receipt, owner, nonce])


def invalidation_statements(available, owner, stamp_ms, guard, args, *, revoke=False, records_erased=False, cards_erased=False):
    result = []
    if records_erased:
        result.append((f'INSERT INTO privacy_record_epochs SELECT ?,1,? WHERE {guard} ON CONFLICT(owner) DO UPDATE SET revision=privacy_record_epochs.revision+1,updated=excluded.updated', [owner, stamp_ms, *args]))
    if 'privacy_preferences' in available:
        update = 'data=excluded.data,policy_version=\'\',provider_binding=\'\',' if revoke else ''
        result.append((f"INSERT INTO privacy_preferences SELECT ?,?,'',1,?,'' WHERE {guard} ON CONFLICT(user_id) DO UPDATE SET {update}revision=privacy_preferences.revision+1,updated=excluded.updated", [owner, dump(FLAGS), stamp_ms, *args]))
    if 'ai_gateway_provider_consents' in available:
        result.append((f"UPDATE ai_gateway_provider_consents SET global_revision=-1,revision=?,categories=CASE WHEN ? THEN '[]' ELSE categories END,updated=? WHERE owner=? AND {guard}", [str(uuid4()), int(revoke), stamp_ms, owner, *args]))
    if 'ai_gateway_jobs' in available:
        result.append((f"UPDATE ai_gateway_jobs SET cancel_requested=1 WHERE owner=? AND status IN ('queued','running') AND {guard}", [owner, *args]))
    if cards_erased and 'card_record_epochs' in available:
        result.append((f'INSERT INTO card_record_epochs SELECT ?,1,? WHERE {guard} ON CONFLICT(owner) DO UPDATE SET revision=card_record_epochs.revision+1,updated=excluded.updated', [owner, stamp_ms, *args]))
    return result


def closure_cleanup_statements(available, owner, operation_id, now_ms, guard='1', bindings=()):
    """Trusted server-only SQL guard. Claim nonce fences every mutation, including replay."""
    receipt, nonce = str(uuid4()), str(uuid4())
    specs = [('records', 'owner=?'), ('timer_runs', 'owner=?'), ('activity_daily', 'user_id=?'), ('measurements', 'connection_id IN (SELECT id FROM devices WHERE owner=?)'), ('card_draw_actions', 'owner=?'), ('card_practice_events', 'owner=?'), ('card_draw_requests', 'owner=?'), ('card_draws', 'owner=?'), ('privacy_conversations', 'user_id=?')]
    specs = [(t, w) for t, w in specs if t in available and (t != 'measurements' or 'devices' in available)]
    details = {'mode': 'account-closure', 'localStatus': 'completed', 'providersStatus': 'pending-confirmation', 'backupsStatus': 'pending-confirmation', 'localBrowserCleared': False, 'memoryStatus': 'service-not-implemented', 'retainedCategories': RETAINED, 'receiptContainsBody': False}
    pairs, params = [], []
    for table, where in specs:
        pairs.extend(["'" + table + "'", f'(SELECT count(*) FROM {table} WHERE {where})'])
        params.append(owner)
    if 'ai_gateway_jobs' in available:
        pairs.extend(["'gatewayOutputs'", '(SELECT count(*) FROM ai_gateway_jobs WHERE owner=? AND (output_text IS NOT NULL OR saved_conversation_id IS NOT NULL))'])
        params.append(owner)
    counts = 'json_object(' + ','.join(pairs) + ')'
    result = [(f"INSERT OR IGNORE INTO privacy_retention_receipts SELECT ?,?,?,?,'claimed',json_set(?,'$.counts',{counts}),? WHERE {guard}", [receipt, owner, operation_id, nonce, dump(details), *params, now_ms, *bindings])]
    g, ga = fence(receipt, owner, nonce)
    result += invalidation_statements(available, owner, now_ms, g, ga, revoke=True, records_erased=True, cards_erased=True)
    if 'ai_gateway_jobs' in available:
        result.append((f'UPDATE ai_gateway_jobs SET output_text=NULL,saved_conversation_id=NULL WHERE owner=? AND {g}', [owner, *ga]))
    if 'payment_support_tickets' in available:
        result.append((f"UPDATE payment_support_tickets SET message='' WHERE owner=? AND {g}", [owner, *ga]))
        result.append((f"UPDATE payment_support_actions SET reply='' WHERE ticket_id IN (SELECT id FROM payment_support_tickets WHERE owner=?) AND {g}", [owner, *ga]))
    # Tombstones prevent snapshot-ID recreation. No body, title or body hash is retained.
    if 'privacy_saved_deletions' in available and 'privacy_conversations' in available:
        result.append((f"INSERT OR IGNORE INTO privacy_saved_deletions SELECT lower(hex(randomblob(16))),user_id,id,?||':'||id,?,? FROM privacy_conversations WHERE user_id=? AND {g}", [receipt, dump({'local': {'status': 'completed'}, 'reason': 'account-closure', 'receiptContainsBody': False}), now_ms, owner, *ga]))
    for table, where in specs:
        result.append((f'DELETE FROM {table} WHERE {where} AND {g}', [owner, *ga]))
    if 'memory_entries' in available:
        memory=memory_cleanup_statements(available,owner,'closure-memory:'+operation_id,now_ms,g,ga,reason='close-account')
        result += memory['statements']
        detail=memory['receiptJSONSql']
        result.append((f"UPDATE privacy_retention_receipts SET details=json_set(details,'$.memoryStatus','completed','$.counts.memoryEntries',json_extract({detail['sql']},'$.counts.memoryEntries')) WHERE id=? AND {g}",[*detail['bindings'],receipt,*ga]))
    result.append((f"UPDATE privacy_retention_receipts SET status='completed' WHERE id=? AND {g}", [receipt, *ga]))
    return {'statements': result, 'receiptId': receipt, 'nonce': nonce, 'receiptQuery': {'sql': 'SELECT id,owner,operation_id,status,details,created FROM privacy_retention_receipts WHERE owner=? AND operation_id=?', 'bindings': [owner, operation_id]}, 'receiptJSONSql': {'sql': "(SELECT details FROM privacy_retention_receipts WHERE owner=? AND operation_id=? AND status='completed')", 'bindings': [owner, operation_id]}}


def append_closure_cleanup(db, owner, operation_id, now_ms):
    if not db.in_transaction:
        raise ValueError('closure cleanup requires caller transaction')
    old = db.execute('SELECT * FROM privacy_retention_receipts WHERE owner=? AND operation_id=?', (owner, operation_id)).fetchone()
    if old:
        return {**json.loads(old['details']), 'receiptId': old['id'], 'replayed': True}
    plan = closure_cleanup_statements(tables(db), owner, operation_id, now_ms)
    for sql, args in plan['statements']:
        db.execute(sql, args)
    row = db.execute(plan['receiptQuery']['sql'], plan['receiptQuery']['bindings']).fetchone()
    return {**json.loads(row['details']), 'receiptId': row['id'], 'replayed': False}


def source(scope):
    return {'records': ('records','owner','kind','day'), 'conversations': ('privacy_conversations','user_id','id',None), 'timer': ('timer_runs','owner','id',None), 'activity': ('activity_daily','user_id','day','feature'), 'measurements': ('measurements','connection_id','id',None), 'cards': ('card_draws','owner','id',None), 'memory': ('memory_entries','owner','id',None)}[scope]


def record_erasure_epoch(db, owner):
    row = db.execute('SELECT revision FROM privacy_record_epochs WHERE owner=?', (owner,)).fetchone()
    return row['revision'] if row else 0


def bump_record_epoch(db, owner, now_ms):
    if not db.in_transaction:
        raise ValueError('record erasure requires caller transaction')
    db.execute('INSERT INTO privacy_record_epochs VALUES(?,1,?) ON CONFLICT(owner) DO UPDATE SET revision=revision+1,updated=excluded.updated', (owner, now_ms))


def guard_record_epoch(db, owner, supplied, Error):
    """Call in the SAME write transaction as legacy record INSERT/UPSERT; no commit."""
    if not db.in_transaction:
        raise ValueError('record guard requires write transaction')
    revision = record_erasure_epoch(db, owner)
    if supplied is None and revision == 0:
        return  # Epoch0 old clients, including anonymous visitors, remain compatible.
    if type(supplied) is not int or supplied != revision:
        raise Error(409, '资料清理或授权代际已变化，请刷新后重新主动保存。')


def owner_expr(scope, alias):
    return f'(SELECT owner FROM devices WHERE id={alias}.connection_id)' if scope == 'measurements' else alias + '.' + source(scope)[1]


def safe_source(scope, alias='r'):
    return f'({alias}.end_ms IS NOT NULL OR {alias}.last_seen<{NOW_SQL}-45000)' if scope == 'timer' else '1'


def retention_days(cfg, executor, scope):
    return cfg.get('retention', {}).get(scope + 'Days') if scope in SCOPES[:2] else executor.get('retentionDays', {}).get(scope)


def join_expr(scope, alias='r', tracker='t'):
    _, owner, k1, k2 = source(scope)
    return f'{tracker}.owner={owner_expr(scope, alias)} AND {tracker}.scope=\'{scope}\' AND {tracker}.k1={alias}.{k1} AND {tracker}.k2=' + (f'{alias}.{k2}' if k2 else "''")


class PrivacyRetention:
    def __init__(self, store, h, Error, limiter, *, test_clock=None):
        self.store, self.h, self.Error, self.rate = store, h, Error, limiter
        self.clock = test_clock or stamp

    def fail(self, n, text):
        raise self.Error(n, text)

    def actor(self, db, owner):
        user = self.h.require()
        actual = db.execute('SELECT id,role FROM users WHERE id=?', (user['id'],)).fetchone()
        if not actual or (actual['id'] != owner and actual['role'] != 'admin'):
            self.fail(403, '只能处理本人资料；代办须当前管理员明确授权。')
        if not db.execute('SELECT 1 FROM users WHERE id=?', (owner,)).fetchone():
            self.fail(404, '目标账号不存在；不对匿名访客猜测归属。')
        if 'account_lifecycle' in tables(db) and db.execute("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'", (actual['id'],)).fetchone():
            self.fail(403, '当前账号已停用。')
        if 'account_lifecycle' in tables(db) and db.execute("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'", (owner,)).fetchone():
            self.fail(409, '目标账号已停用，跳过到期批次；不重启授权。')
        return actual

    def context(self, db, owner):
        row = db.execute("SELECT data FROM settings WHERE key='privacy'").fetchone()
        raw = row['data'] if row else '{}'
        ex = db.execute('SELECT data FROM privacy_retention_config WHERE id=1').fetchone()['data']
        pref = db.execute('SELECT revision FROM privacy_preferences WHERE user_id=?', (owner,)).fetchone()
        return raw, ex, pref['revision'] if pref else 0

    def scopes(self, value):
        if not isinstance(value, list) or not value or len(set(value)) != len(value) or any(v not in SCOPES for v in value):
            self.fail(400, '请明确选择支持的六类个人资料范围。')
        return sorted(value)

    def key(self, value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', value):
            self.fail(400, '请提供8至100位幂等请求号。')
        return value

    def scheduled_batch(self, owner, job_id, data):
        """Host integration prepared only. No timer or implicit privileged actor is installed."""
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if self.actor(db, owner)['role'] != 'admin':
                self.fail(403, '定时批次须有效管理员授权主体。')
            return self.apply(db, owner, job_id, data)

    def preview(self, db, owner, data):
        actor = self.actor(db, owner)
        scopes, key = self.scopes(data.get('scopes')), self.key(data.get('requestId'))
        if set(data) - {'owner', 'scopes', 'requestId'}:
            self.fail(400, '预览时间由服务器生成，不接受客户端日期或未来时间。')
        old = db.execute('SELECT * FROM privacy_retention_jobs WHERE actor=? AND request_id=?', (actor['id'], key)).fetchone()
        if old:
            if old['owner'] != owner or json.loads(old['scopes']) != scopes:
                self.fail(409, '该请求号已用于其他范围。')
            return self.job_item(db, old)
        raw, ex, rev = self.context(db, owner)
        cfg, stamp_ms, identifier = json.loads(raw), self.clock(), str(uuid4())
        summary = {'scopes': {}, 'unknownHistoricalAgeSkipped': True, 'truncated': False, 'limit': 1000, 'unsupportedAutomaticScopes': ['unlinked-gateway-output'], 'retainedCategories': RETAINED, 'providersStatus': 'pending-confirmation', 'backupsStatus': 'pending-confirmation'}
        all_targets = []
        for scope in scopes:
            table, own, k1, k2 = source(scope)
            if table not in tables(db):
                summary['scopes'][scope] = {'retentionDays': None, 'total': None, 'eligible': 0, 'ageUnknown': None, 'skipReason': 'source-table-unavailable'}
                continue
            days = retention_days(cfg, json.loads(ex), scope)
            known_days = type(days) is int and 0 <= days <= 36500
            eligible = f't.write_at<=? AND {safe_source(scope)}' if known_days else '0'
            cutoff = stamp_ms - days * 86400000 if known_days else None
            j = join_expr(scope)
            counts = db.execute(f"SELECT count(*) total,sum(CASE WHEN t.nonce IS NULL THEN 1 ELSE 0 END) unknown FROM {table} r LEFT JOIN privacy_retention_tracking t ON {j} WHERE {owner_expr(scope,'r')}=?", (owner,)).fetchone()
            targets = db.execute(f"SELECT t.* FROM {table} r JOIN privacy_retention_tracking t ON {j} WHERE {owner_expr(scope,'r')}=? AND {eligible} ORDER BY t.write_at,t.k1,t.k2 LIMIT 1001", (owner, cutoff) if known_days else (owner,)).fetchall()
            full_count = db.execute(f"SELECT count(*) FROM {table} r JOIN privacy_retention_tracking t ON {j} WHERE {owner_expr(scope,'r')}=? AND {eligible}", (owner, cutoff) if known_days else (owner,)).fetchone()[0]
            summary['scopes'][scope] = {'retentionDays': days if known_days else None, 'total': counts['total'], 'ageUnknown': counts['unknown'] or 0, 'eligible': full_count, 'skipReason': None if known_days else 'retention-days-unconfirmed'}
            all_targets += [dict(r) for r in targets]
        summary['truncated'] = len(all_targets) > 1000 or any(v['eligible'] > 1000 for v in summary['scopes'].values())
        all_targets = all_targets[:1000]
        summary['planned'] = len(all_targets)
        db.execute('INSERT INTO privacy_retention_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (identifier, owner, actor['id'], key, dump(scopes), stamp_ms, raw, ex, rev, 'preview', 0, dump(summary), stamp_ms))
        db.executemany('INSERT INTO privacy_retention_targets VALUES(?,?,?,?,?,?,?,?,0)', [(identifier, owner, t['scope'], t['k1'], t['k2'], t['write_at'], t['version'], t['nonce']) for t in all_targets])
        return self.job_item(db, db.execute('SELECT * FROM privacy_retention_jobs WHERE id=?', (identifier,)).fetchone())

    def job_item(self, db, row):
        pending = db.execute('SELECT count(*) FROM privacy_retention_targets WHERE job_id=? AND processed=0', (row['id'],)).fetchone()[0]
        cfg, ex = json.loads(row['policy_data']), json.loads(row['executor_data'])
        return {'id': row['id'], 'accountId': row['owner'], 'asOf': row['as_of'], 'policyVersion': cfg.get('policyVersion', ''), 'policyRevision': cfg.get('revision', 0), 'executorRevision': ex['revision'], 'preferenceRevision': row['pref_revision'], 'version': row['version'], 'status': row['status'], 'pending': pending, 'summary': json.loads(row['summary']), 'dryRun': row['status']=='preview', 'executorEnabled': ex['enabled'], 'localBrowserCleared': False}

    def apply(self, db, owner, job_id, data):
        self.actor(db, owner)
        if set(data) != {'requestId', 'confirmed', 'policyVersion', 'version'} or data['confirmed'] is not True:
            self.fail(400, '实际执行须明确确认当前政策及预览版本。')
        key = self.key(data['requestId'])
        operation = 'expiry:' + job_id + ':' + key
        old = db.execute('SELECT * FROM privacy_retention_receipts WHERE owner=? AND operation_id=?', (owner, operation)).fetchone()
        if old:
            return {'item': receipt_item(old), 'replayed': True}
        job = db.execute('SELECT * FROM privacy_retention_jobs WHERE id=? AND owner=?', (job_id, owner)).fetchone()
        if not job:
            self.fail(404, '未找到当前账号的清理预览。')
        raw, ex, rev = self.context(db, owner)
        cfg, executor = json.loads(raw), json.loads(ex)
        if raw != job['policy_data'] or ex != job['executor_data'] or rev != job['pref_revision'] or type(data['version']) is not int or data['version'] != job['version']:
            self.fail(409, '政策、授权或任务版本已变化，请重新预览。')
        if not executor['enabled'] or not cfg.get('policyVersion') or executor['policyVersion'] != cfg['policyVersion'] or data['policyVersion'] != cfg['policyVersion']:
            self.fail(409, '到期清理尚未获得当前政策版本的执行授权。')
        selected = db.execute('SELECT * FROM privacy_retention_targets WHERE job_id=? AND processed=0 ORDER BY scope,k1,k2 LIMIT 100', (job_id,)).fetchall()
        deleted = dict.fromkeys(SCOPES, 0)
        available, stamp_ms = tables(db), self.clock()
        receipt, nonce = str(uuid4()), str(uuid4())
        db.execute("INSERT INTO privacy_retention_receipts VALUES(?,?,?,?,'claimed','{}',?)", (receipt, owner, operation, nonce, stamp_ms))
        for t in selected:
            table, own, k1, k2 = source(t['scope'])
            live = db.execute('SELECT * FROM privacy_retention_tracking WHERE owner=? AND scope=? AND k1=? AND k2=?', (owner, t['scope'], t['k1'], t['k2'])).fetchone()
            if live and live['nonce'] == t['nonce'] and live['version'] == t['version'] and live['write_at'] == t['write_at']:
                where = f'{owner_expr(t["scope"],"r")}=? AND {k1}=?' + (f' AND {k2}=?' if k2 else '') + ' AND ' + safe_source(t['scope'])
                args = (owner, t['k1'], t['k2']) if k2 else (owner, t['k1'])
                exists = db.execute(f'SELECT 1 FROM {table} r WHERE {where}', args).fetchone()
                if exists and t['scope'] == 'conversations':
                    if 'privacy_saved_deletions' in available:
                        db.execute('INSERT OR IGNORE INTO privacy_saved_deletions VALUES(?,?,?,?,?,?)', (str(uuid4()), owner, t['k1'], receipt + ':' + t['k1'], dump({'reason': 'retention-expiry', 'local': {'status': 'completed'}, 'receiptContainsBody': False}), stamp_ms))
                    if 'ai_gateway_jobs' in available:
                        db.execute('UPDATE ai_gateway_jobs SET output_text=NULL,saved_conversation_id=NULL WHERE owner=? AND saved_conversation_id=?', (owner, t['k1']))
                if exists and t['scope'] == 'cards':
                    for child in ('card_draw_actions', 'card_practice_events', 'card_draw_requests'):
                        if child in available:
                            db.execute(f'DELETE FROM {child} WHERE owner=? AND draw_id=?', (owner,t['k1']))
                if exists and t['scope']=='memory':
                    current=db.execute('SELECT version FROM memory_entries WHERE id=? AND owner=?',(t['k1'],owner)).fetchone()
                    result=append_memory_cleanup(db,owner,'expiry-memory:'+receipt+':'+t['k1'],stamp_ms,reason='retention',targets=[{'id':t['k1'],'version':current['version']}])
                    deleted['memory']+=result['counts']['memoryEntries']
                else:deleted[t['scope']] += db.execute(f'DELETE FROM {table} AS r WHERE {where}', args).rowcount
            db.execute('UPDATE privacy_retention_targets SET processed=1 WHERE job_id=? AND scope=? AND k1=? AND k2=?', (job_id, t['scope'], t['k1'], t['k2']))
        if sum(v for k,v in deleted.items() if k!='memory'):
            for sql, args in invalidation_statements(available, owner, stamp_ms, '1', [], records_erased=any(v for k,v in deleted.items() if k not in ('conversations','memory')), cards_erased=deleted['cards']>0):
                db.execute(sql, args)
        next_revision = self.context(db, owner)[2]
        pending = db.execute('SELECT count(*) FROM privacy_retention_targets WHERE job_id=? AND processed=0', (job_id,)).fetchone()[0]
        db.execute('UPDATE privacy_retention_jobs SET version=version+1,pref_revision=?,status=? WHERE id=?', (next_revision, 'ready' if pending else 'completed', job_id))
        details = {'mode': 'retention-expiry', 'jobId': job_id, 'asOf': job['as_of'], 'policyVersion': cfg['policyVersion'], 'counts': deleted, 'selected': len(selected), 'changedOrMissingSkipped': len(selected) - sum(deleted.values()), 'pending': pending, 'nextVersion': job['version'] + 1, 'localStatus': 'batch-completed', 'providersStatus': 'pending-confirmation', 'backupsStatus': 'pending-confirmation', 'memoryStatus': 'completed' if deleted.get('memory') else 'not-selected-or-no-expired-memory', 'retainedCategories': RETAINED, 'localBrowserCleared': False, 'receiptContainsBody': False}
        db.execute("UPDATE privacy_retention_receipts SET status='completed',details=? WHERE id=?", (dump(details), receipt))
        return {'item': receipt_item(db.execute('SELECT * FROM privacy_retention_receipts WHERE id=?', (receipt,)).fetchone()), 'replayed': False}

    def route(self, method, path):
        if not (path.startswith('/api/privacy/retention') or path.startswith('/api/admin/privacy/retention')):
            return None
        user = self.h.require()
        self.rate('retention:' + user['id'], 40)
        data = self.h.body() if method in ('POST', 'PATCH') else {}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE' if method in ('POST', 'PATCH') else 'BEGIN')
            if path == '/api/admin/privacy/retention/config':
                actual = self.actor(db, user['id'])
                if actual['role'] != 'admin':
                    self.fail(403, '仅当前管理员可配置执行授权。')
                raw, ex, _ = self.context(db, user['id'])
                old, policy = json.loads(ex), json.loads(raw)
                if method == 'PATCH':
                    if set(data) != {'enabled', 'policyVersion', 'revision', 'confirmed', 'retentionDays'} or type(data['enabled']) is not bool or data['confirmed'] is not True or type(data['revision']) is not int or data['revision'] != old['revision']:
                        self.fail(409, '请明确确认最新配置版本。')
                    if not isinstance(data['retentionDays'],dict) or set(data['retentionDays']) not in (set(SCOPES[2:]),set(SCOPES[2:-1])) or any(v is not None and (type(v) is not int or not 0<=v<=36500) for v in data['retentionDays'].values()):
                        self.fail(400, '各类期限须独立明确天数或null未确认。')
                    if data['enabled'] and (not policy.get('policyVersion') or data['policyVersion'] != policy['policyVersion']):
                        self.fail(409, '当前隐私政策版本尚未确认。')
                    old = {'enabled': data['enabled'], 'policyVersion': data['policyVersion'] if data['enabled'] else '', 'revision': old['revision'] + 1, 'retentionDays':{'memory':old.get('retentionDays',{}).get('memory'),**data['retentionDays']}}
                    db.execute('UPDATE privacy_retention_config SET data=? WHERE id=1', (dump(old),))
                return {'config': old, 'policyVersion': policy.get('policyVersion', ''), 'retention': policy.get('retention', {}), 'schedulerDeployed': False}
            owner = data.get('owner', user['id'])
            # Cross-owner reads deliberately require explicit /admin route + owner query integration, not guesswork.
            if not isinstance(owner, str) or not owner:
                self.fail(400, '必须明确当前账号。')
            if owner != user['id'] and not path.startswith('/api/admin/'):
                self.fail(403, '代办必须使用明确管理员入口。')
            self.actor(db, owner)
            base = '/api/admin/privacy/retention' if path.startswith('/api/admin/') else '/api/privacy/retention'
            if path == base and method == 'GET':
                raw, ex, rev = self.context(db, owner)
                return {'accountId': owner, 'config': json.loads(ex), 'policy': json.loads(raw).get('policyVersion', ''), 'retention': json.loads(raw).get('retention', {}), 'preferenceRevision': rev, 'recordErasureEpoch':record_erasure_epoch(db,owner), 'items': [self.job_item(db, r) for r in db.execute('SELECT * FROM privacy_retention_jobs WHERE owner=? ORDER BY created DESC LIMIT 30', (owner,))], 'receipts': [receipt_item(r) for r in db.execute('SELECT * FROM privacy_retention_receipts WHERE owner=? ORDER BY created DESC LIMIT 30', (owner,))], 'schedulerDeployed': False, 'supportedAutomaticScopes': list(SCOPES), 'memoryImplemented': True}
            if path == base + '/preview' and method == 'POST':
                return {'item': self.preview(db, owner, data)}
            if path == base + '/adopt-history' and method == 'POST':
                if set(data) - {'owner', 'scopes', 'confirmed', 'policyVersion'} or data.get('confirmed') is not True:
                    self.fail(400, '纳管旧记录须明确确认，以服务器当前时间为保护起点。')
                cfg = json.loads(self.context(db, owner)[0])
                if not cfg.get('policyVersion') or data.get('policyVersion') != cfg['policyVersion']:
                    self.fail(409, '政策版本已变化。')
                counts, stamp_ms = {}, self.clock()
                for scope in self.scopes(data.get('scopes')):
                    table, own, k1, k2 = source(scope)
                    if table not in tables(db):
                        counts[scope] = None
                        continue
                    j = join_expr(scope)
                    counts[scope] = db.execute(f"INSERT OR IGNORE INTO privacy_retention_tracking SELECT {owner_expr(scope,'r')},?,r.{k1},{'r.' + k2 if k2 else chr(39)+chr(39)},?,1,lower(hex(randomblob(16))),'protection-start' FROM {table} r WHERE {owner_expr(scope,'r')}=? AND NOT EXISTS(SELECT 1 FROM privacy_retention_tracking t WHERE {j})", (scope, stamp_ms, owner)).rowcount
                return {'counts': counts, 'protectionStart': stamp_ms, 'historicalLastWriteKnown': False, 'deleted': 0}
            match = re.fullmatch(re.escape(base) + r'/jobs/([^/]+)/apply', path)
            if match and method == 'POST':
                clean = {k: v for k, v in data.items() if k != 'owner'}
                return self.apply(db, owner, match[1], clean)
            self.fail(404, '未找到到期清理接口。')
