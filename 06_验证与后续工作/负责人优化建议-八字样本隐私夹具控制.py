"""Fixed synthetic controls for this module's newly owned SQLite database only."""
import hashlib
import base64
import json
import sqlite3
import time
from pathlib import Path
from uuid import uuid4


SPEC = json.loads(Path(__file__).with_name('负责人优化建议-隐私逐域场景夹具.json').read_text(encoding='utf-8'))
DOMAINS = tuple(SPEC['domains'])


def handle(path, data):
    action = data.get('action', '')
    if not action.startswith('domain-') or action == 'domain-clock':
        return None
    database = Path(path).resolve()
    assert database.parent == Path(__file__).resolve().parent and database.is_file()
    assert database.name.startswith('负责人优化建议-八字样本隔离-')
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        owner = data.get('owner', '')
        stamp = time.time_ns() // 1_000_000
        if action == 'domain-seed-legacy-output':
            row = db.execute("SELECT id FROM ai_gateway_jobs WHERE id=? AND owner=? AND status IN ('succeeded','partial','failed','cancelled') AND charged_credits IS NOT NULL",(data.get('jobId'),owner)).fetchone()
            assert row
            db.execute('UPDATE ai_gateway_jobs SET output_text=? WHERE id=? AND owner=?',(SPEC['canaries']['gatewayOutput'],row['id'],owner))
            return {'seededLegacyOutputRows':1,'jobId':row['id'],'actualTerminalAccountingPreserved':True,'syntheticOnly':True}
        if action == 'domain-create-unknown-table':
            db.execute('CREATE TABLE IF NOT EXISTS qa_domain_unclassified(id TEXT PRIMARY KEY,owner TEXT NOT NULL,body TEXT NOT NULL)')
            return {'created':True,'table':'qa_domain_unclassified','syntheticOnly':True}
        if action in ('domain-unknown-reference','domain-attempt-dead-unknown','domain-unknown-unrelated'):
            assert db.execute('SELECT 1 FROM users WHERE id=?', (owner,)).fetchone()
            media_id = data.get('mediaId','')
            if action == 'domain-unknown-reference':
                assert db.execute('SELECT 1 FROM media WHERE id=? AND owner=?', (media_id,owner)).fetchone()
            elif action == 'domain-attempt-dead-unknown':
                assert db.execute('SELECT 1 FROM privacy_media_tombstones WHERE media_id=? AND owner=?', (media_id,owner)).fetchone()
            else:
                media_id = str(uuid4())
                assert not db.execute('SELECT 1 FROM privacy_media_tombstones WHERE media_id=?', (media_id,)).fetchone()
            payload = '{"media":"'+''.join('\\u%04x' % ord(char) for char in media_id)+'"}'
            try:
                db.execute('INSERT INTO qa_domain_unclassified VALUES(?,?,?)', (str(uuid4()),owner,payload))
            except sqlite3.IntegrityError as error:
                assert 'privacy_deleted_media_reference' in str(error)
                return {'blocked':True,'jsonUnicodeBareMediaId':True,'actualDatabaseTrigger':True,'syntheticOnly':True}
            return {'blocked':False,'mediaId':media_id,'jsonUnicodeBareMediaId':True,'actualDatabaseTrigger':True,'syntheticOnly':True}
        if action in ('domain-seed-service', 'domain-seed-draft', 'domain-seed-profile', 'domain-seed-unknown','domain-seed-media'):
            assert db.execute('SELECT 1 FROM users WHERE id=?', (owner,)).fetchone()
            count = data.get('count', 1)
            assert type(count) is int and 1 <= count <= SPEC['bulkLimit']
            ids = [str(uuid4()) for _ in range(count)]
            body = SPEC['canaries']['body']
            media_id = data.get('mediaId', '')
            if media_id:
                assert db.execute('SELECT 1 FROM media WHERE id=? AND owner=?', (media_id,owner)).fetchone()
                body += ' /api/media/'+media_id
            domain = 'serviceRequestContent'
            if action == 'domain-seed-service':
                db.executemany(SPEC['serviceInsert'], [(ident, owner, 'privacy-domain-qa-teacher', '独立合成老师标识', body+'_'+ident, '2030-01-02', 'pending', stamp) for ident in ids])
            elif action == 'domain-seed-draft':
                domain = 'creatorDrafts'
                state = data.get('status', 'draft')
                assert state in ('draft', 'published', 'rejected', 'manual_review')
                payload = json.dumps({'type':'article','title':'逐域合成草稿','body':body,'format':'article','theme':'healing','categoryIds':[],'mediaUrl':'','coverUrl':'','sections':[],'duration':0}, ensure_ascii=False)
                db.executemany(SPEC['draftInsert'], [(ident, owner, payload, state, '', 1, stamp, stamp) for ident in ids])
            elif action == 'domain-seed-profile':
                domain = 'creatorPrivateProfiles'
                state = data.get('status', 'pending')
                assert state in ('pending', 'rejected', 'approved', 'suspended')
                assert count == 1
                ids = [owner]
                db.execute(SPEC['profileInsert'], (owner, json.dumps({'displayName':'逐域合成申请','bio':body,'avatarUrl':''}, ensure_ascii=False), state, '', stamp, stamp))
            elif action == 'domain-seed-media':
                domain = 'privateMedia'
                binary = base64.b64decode(SPEC['bulkWavBase64'])
                db.executemany('INSERT INTO media VALUES(?,?,?,?,?,?)', [(ident,owner,'audio/wav','synthetic-bulk.wav',binary,stamp) for ident in ids])
            else:
                db.execute('CREATE TABLE IF NOT EXISTS qa_domain_unclassified(id TEXT PRIMARY KEY,owner TEXT NOT NULL,body TEXT NOT NULL)')
                db.executemany('INSERT INTO qa_domain_unclassified VALUES(?,?,?)', [(ident, owner, SPEC['canaries']['unknownBody']) for ident in ids])
                return {'seededRows':count,'ids':ids,'unknownTable':'qa_domain_unclassified','syntheticOnly':True}
            unknown = data.get('historicalUnknown', False)
            assert type(unknown) is bool
            if unknown:
                for ident in ids:
                    db.execute('DELETE FROM privacy_retention_tracking WHERE owner=? AND scope=? AND k1=?', (owner, domain, ident))
            return {'seededRows':len(ids),'ids':ids,'domain':domain,'historicalUnknownFixture':unknown,'syntheticOnly':True}
        if action == 'domain-fault':
            enabled = data.get('enabled')
            assert type(enabled) is bool
            table = data.get('table', 'privacy_domain_receipts')
            assert table in ('privacy_domain_receipts', 'privacy_media_tombstones')
            name = 'qa_domain_receipt_fault' if table == 'privacy_domain_receipts' else 'qa_domain_media_fault'
            db.execute('DROP TRIGGER IF EXISTS '+name)
            if enabled:
                db.execute('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT qa_storage_unavailable(); END')
            return {'faultEnabled':enabled,'table':table,'syntheticOnly':True}
        if action == 'domain-reference':
            media_id, kind = data.get('mediaId'), data.get('kind')
            assert db.execute('SELECT 1 FROM media WHERE id=? AND owner=?', (media_id,owner)).fetchone()
            assert kind in ('settings', 'history-revision')
            ident = str(uuid4())
            payload = json.dumps({'fixtureMedia':'/api/media/'+media_id}, ensure_ascii=False)
            if data.get('escapedSlash') is True:
                payload = payload.replace('/', '\\/')
            if kind == 'settings':
                db.execute('INSERT INTO settings VALUES(?,?)', ('qa_domain_reference_'+ident,payload))
            else:
                db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?)', (ident,owner,'courses',str(uuid4()),payload,stamp))
            return {'referenceId':ident,'kind':kind,'syntheticOnly':True}
        if action == 'domain-draft-history':
            ident, kind = data.get('resourceId'), data.get('kind')
            assert db.execute('SELECT 1 FROM creator_works WHERE id=? AND owner_id=?', (ident,owner)).fetchone()
            assert kind in ('review', 'post-copy', 'course-copy')
            if kind == 'review':
                db.execute('INSERT INTO creator_reviews VALUES(?,?,?,?,?,?,?)', (str(uuid4()),ident,'manual','rejected','Synthetic historical review',1,stamp))
            elif kind == 'post-copy':
                db.execute('INSERT INTO posts VALUES(?,?,?,?,?,?,?,?,?)', (ident,owner,'合成历史公开作品',SPEC['canaries']['body'],'','withdrawn','',stamp,stamp))
            else:
                db.execute('INSERT INTO contents VALUES(?,?,?,?,?,?)', ('courses',ident,json.dumps({'title':'合成历史课程拷贝','creatorId':owner}), 'archived',0,stamp))
            return {'resourceId':ident,'historyKind':kind,'syntheticOnly':True}
        if action == 'domain-attempt-dead-reference':
            media_id = data.get('mediaId')
            assert db.execute('SELECT 1 FROM privacy_media_tombstones WHERE media_id=? AND owner=?', (media_id,owner)).fetchone()
            kind = data.get('kind','settings')
            assert kind in ('settings','history-revision')
            try:
                if kind == 'history-revision':
                    db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?)',(str(uuid4()),owner,'courses',str(uuid4()),json.dumps({'mediaUrl':'/api/media/'+media_id}),stamp))
                else:
                    db.execute('INSERT INTO settings VALUES(?,?)', ('qa_domain_dead_'+str(uuid4()),json.dumps({'mediaUrl':'/api/media/'+media_id})))
            except sqlite3.IntegrityError as error:
                assert 'privacy_deleted_media_reference' in str(error)
                return {'blocked':True,'actualDatabaseTrigger':True,'syntheticOnly':True}
            return {'blocked':False,'actualDatabaseTrigger':True,'syntheticOnly':True}
        if action == 'domain-attempt-dead-media':
            media_id = data.get('mediaId')
            assert db.execute('SELECT 1 FROM privacy_media_tombstones WHERE media_id=? AND owner=?',(media_id,owner)).fetchone()
            try:
                db.execute('INSERT INTO media VALUES(?,?,?,?,?,?)',(media_id,owner,'audio/wav','dead-identity-fixture.wav',base64.b64decode(SPEC['bulkWavBase64']),stamp))
            except sqlite3.IntegrityError as error:
                assert 'privacy_deleted_media_identity' in str(error)
                return {'blocked':True,'actualDatabaseTrigger':True,'syntheticOnly':True,'objectKeyReuseApplicable':False}
            return {'blocked':False,'actualDatabaseTrigger':True,'syntheticOnly':True,'objectKeyReuseApplicable':False}
        if action == 'domain-snapshot':
            assert db.execute('SELECT 1 FROM users WHERE id=?', (owner,)).fetchone()
            rows = {}
            for domain, source in SPEC['domains'].items():
                columns = 'id,owner,mime,filename,created' if domain == 'privateMedia' else '*'
                rows[domain] = [dict(row) for row in db.execute('SELECT '+columns+' FROM '+source['table']+' WHERE '+source['owner']+'=? ORDER BY '+source['id'], (owner,))]
            available = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ('privacy_domain_jobs','privacy_domain_targets','privacy_domain_receipts','privacy_media_tombstones'):
                rows[table] = [dict(row) for row in db.execute('SELECT * FROM '+table+' WHERE owner=?', (owner,))]
            rows['privacy_object_deletions'] = [dict(row) for row in db.execute('SELECT id,owner,receipt_id,media_id,status,attempts,lease_until,next_attempt,last_error,created,updated FROM privacy_object_deletions WHERE owner=?', (owner,))]
            rows['tracking'] = [dict(row) for row in db.execute('SELECT * FROM privacy_retention_tracking WHERE owner=?', (owner,))]
            if 'qa_domain_unclassified' in available:
                rows['unclassified'] = [dict(row) for row in db.execute('SELECT * FROM qa_domain_unclassified WHERE owner=?', (owner,))]
            rows['gateway'] = [dict(row) for row in db.execute('SELECT id,status,reserve_credits,charged_credits,quota_source,quota_period_id,has_output,output_chars,output_text,saved_conversation_id,usage,error_code,created,updated FROM ai_gateway_jobs WHERE owner=?', (owner,))]
            rows['wallet'] = [dict(row) for row in db.execute('SELECT balance,reserved FROM ai_gateway_wallets WHERE owner=?', (owner,))]
            protected = {}
            for table, predicate in [('commerce_orders','owner'),('commerce_order_items','order_id IN (SELECT id FROM commerce_orders WHERE owner=?)'),('commerce_payment_events','owner'),('commerce_entitlements','owner'),('digital_entitlement_grants','owner'),('digital_entitlement_uses','owner'),('membership_ai_periods','owner'),('membership_ai_allocations','owner'),('ai_gateway_quota_events','owner')]:
                where = predicate if '?' in predicate else predicate+'=?'
                protected[table] = [dict(row) for row in db.execute('SELECT * FROM '+table+' WHERE '+where, (owner,))]
            rows['protectedFactsDigest'] = hashlib.sha256(json.dumps(protected, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
            return rows
        raise ValueError('Unknown fixed privacy domain QA action')
