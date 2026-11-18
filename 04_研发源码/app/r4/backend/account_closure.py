"""Final local account closure. No provider/backup/billing completion claims."""
import hashlib
import hmac
import json
import re
import sqlite3
import secrets
import time
from uuid import uuid4

CHALLENGE_TTL_MS = 300_000
SCHEMA_STATEMENTS = [
"""CREATE TABLE IF NOT EXISTS account_revoked_sessions(token_hash TEXT PRIMARY KEY,owner TEXT NOT NULL,revoked_at INTEGER NOT NULL)""",
"""CREATE TABLE IF NOT EXISTS account_lifecycle(owner TEXT PRIMARY KEY REFERENCES users(id),status TEXT NOT NULL CHECK(status IN ('active','closed')),epoch INTEGER NOT NULL CHECK(epoch>=1),closed_at INTEGER,receipt_id TEXT)""",
"""CREATE TABLE IF NOT EXISTS account_closure_challenges(id TEXT PRIMARY KEY,owner TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,nonce_hash TEXT NOT NULL,session_hash TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,consumed INTEGER NOT NULL DEFAULT 0,UNIQUE(owner,request_id))""",
"""CREATE TABLE IF NOT EXISTS account_closure_receipts(id TEXT PRIMARY KEY,owner TEXT NOT NULL REFERENCES users(id),challenge_id TEXT NOT NULL UNIQUE,request_id TEXT NOT NULL,nonce_hash TEXT NOT NULL,operation_nonce TEXT NOT NULL,created INTEGER NOT NULL,details TEXT NOT NULL,UNIQUE(owner,request_id))""",
"""CREATE TRIGGER IF NOT EXISTS account_closure_claim BEFORE INSERT ON account_closure_receipts BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM account_closure_challenges c JOIN sessions s ON s.token=c.session_hash AND s.user_id=c.owner JOIN users u ON u.id=c.owner WHERE c.id=NEW.challenge_id AND c.owner=NEW.owner AND c.request_id=NEW.request_id AND c.nonce_hash=NEW.nonce_hash AND c.consumed=0 AND c.expires>NEW.created AND s.expires>NEW.created) THEN RAISE(ABORT,'account_closure_challenge_invalid') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') THEN RAISE(ABORT,'account_closed') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM users WHERE id=NEW.owner AND role='admin') AND (SELECT count(*) FROM users u WHERE u.role='admin' AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))<=1 THEN RAISE(ABORT,'account_closure_last_admin') END;
 END""",
"""CREATE TRIGGER IF NOT EXISTS account_lifecycle_no_reopen BEFORE UPDATE ON account_lifecycle WHEN OLD.status='closed' BEGIN SELECT RAISE(ABORT,'account_closed'); END""",
]
# Personal data guards only. Existing financial facts must remain settleable.
GUARDS = {
 'users': ('NEW.id','both'), 'sessions': ('NEW.user_id','both'),
 'records': ('NEW.owner','both'), 'timer_runs': ('NEW.owner','both'),
 'activity_daily': ('NEW.user_id','both'), 'devices': ('NEW.owner','both'),
 'measurements': ('(SELECT owner FROM devices WHERE id=NEW.connection_id)','both'),
 'privacy_preferences': ('NEW.user_id','both'),
 'privacy_conversations': ('NEW.user_id','both'),
 'ai_gateway_provider_consents': ('NEW.owner','both'),
 'card_draws': ('NEW.owner','both'), 'card_draw_actions': ('NEW.owner','both'),
 'card_practice_events': ('NEW.owner','both'), 'card_draw_requests': ('NEW.owner','both'),
 'posts': ('NEW.author_id','insert'), 'messages': ('NEW.sender','insert'),
 'service_requests': ('NEW.user_id','insert'), 'media': ('NEW.owner','insert'),
 'creator_works': ('NEW.owner_id','insert'),
}
def guard_statements(tables):
    statements=[]
    for table,(owner,mode) in GUARDS.items():
        if table not in tables: continue
        for action in ('INSERT','UPDATE') if mode=='both' else ('INSERT',):
            statements.append(f"CREATE TRIGGER IF NOT EXISTS account_closed_{table}_{action.lower()} BEFORE {action} ON {table} WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner={owner} AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END")
    if 'ai_gateway_jobs' in tables:
        statements += [
          "CREATE TRIGGER IF NOT EXISTS account_closed_ai_job_insert BEFORE INSERT ON ai_gateway_jobs WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END",
          "CREATE TRIGGER IF NOT EXISTS account_closed_ai_job_body BEFORE UPDATE OF output_text,saved_conversation_id ON ai_gateway_jobs WHEN (NEW.output_text IS NOT NULL OR NEW.saved_conversation_id IS NOT NULL) AND EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END"]
    if 'friendships' in tables:
        for action in ('INSERT','UPDATE'):
            statements.append(f"CREATE TRIGGER IF NOT EXISTS account_closed_friend_target_{action.lower()} BEFORE {action} ON friendships WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE status='closed' AND owner IN (NEW.sender,NEW.recipient)) BEGIN SELECT RAISE(ABORT,'account_target_closed'); END")
    if 'messages' in tables:
        statements.append("CREATE TRIGGER IF NOT EXISTS account_closed_message_target BEFORE INSERT ON messages WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.recipient AND status='closed') BEGIN SELECT RAISE(ABORT,'account_target_closed'); END")
    if 'service_requests' in tables and 'creator_profiles' in tables:
        statements.append("CREATE TRIGGER IF NOT EXISTS account_closed_service_target BEFORE INSERT ON service_requests WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE status='closed' AND (owner=NEW.teacher_id OR owner IN (SELECT user_id FROM creator_profiles WHERE teacher_id=NEW.teacher_id) OR owner IN (SELECT json_extract(data,'$.creatorId') FROM contents WHERE kind='teachers' AND id=NEW.teacher_id))) BEGIN SELECT RAISE(ABORT,'account_target_closed'); END")
    return statements

def can_book_teacher(db,teacher_id,profile):
    owners=[teacher_id,profile.get('creatorId','')]
    owners += [r[0] for r in db.execute('SELECT user_id FROM creator_profiles WHERE teacher_id=?',(teacher_id,))]
    return all(account_active(db,owner) for owner in owners if owner)

def init_schema(db):
    for sql in SCHEMA_STATEMENTS: db.execute(sql)
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for sql in guard_statements(tables): db.execute(sql)
    try:
        from account_write_guard import init_schema as init_write_guard
    except ModuleNotFoundError:
        import importlib.util,sys
        from pathlib import Path
        spec=importlib.util.spec_from_file_location('account_write_guard',Path(__file__).with_name('account_write_guard.py'))
        authority=importlib.util.module_from_spec(spec);sys.modules['account_write_guard']=authority;spec.loader.exec_module(authority)
        init_write_guard=authority.init_schema
    init_write_guard(db)

def account_active(db, owner):
    return not db.execute("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'",(owner,)).fetchone()

def require_active(db, owner, Error):
    if not account_active(db,owner): raise Error(401,'账号已关闭，请使用其他账号。')

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def valid_request(data, keys):
    if set(data)-set(keys): raise ValueError('请求包含不支持的字段。')
    key=data.get('requestId')
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{8,100}',key): raise ValueError('需要8至100位幂等编号。')
    nonce=data.get('nonce')
    if not isinstance(nonce,str) or not re.fullmatch(r'[a-f0-9]{64}',nonce): raise ValueError('需要本次确认凭证。')
    return key,digest(nonce)

class AccountClosure:
    def __init__(self,store,h,Error,limiter,verify_password,cleanup=None,*,clock=None):
        self.store,self.h,self.Error,self.limit=store,h,Error,limiter
        self.verify=verify_password
        if cleanup is None:
            try:
                from privacy_retention import append_closure_cleanup
            except ModuleNotFoundError:
                import importlib.util
                from pathlib import Path
                spec=importlib.util.spec_from_file_location('eastern_closure_cleanup',Path(__file__).with_name('privacy_retention.py'))
                authority=importlib.util.module_from_spec(spec);spec.loader.exec_module(authority)
                append_closure_cleanup=authority.append_closure_cleanup
            cleanup=append_closure_cleanup
        self.cleanup=cleanup
        self.clock=clock or (lambda:int(time.time()*1000))

    def receipt(self,row,db=None):
        details=json.loads(row['details'])
        from privacy_domains import closure_snapshot
        domain_cleanup=closure_snapshot(db,row['owner'],row['id']) if db is not None else None
        return {'receipt':{'id':row['id'],'status':'closed','accountClosed':True,'sessionsRevoked':True,
                 'credentialVerifierInvalidated':True,'closedAt':row['created'],'local':details,'providersStatus':'pending-confirmation',
                 'backupsStatus':'pending-confirmation','thirdPartyRenewalCancelled':False,
                 'localBrowserCleared':False,'domainCleanup':domain_cleanup},'reauthenticate':True}

    def clear_cookie(self):
        self.h.cookies_out.append('ew_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict')

    def route(self,method,path):
        if not path.startswith('/api/account-closure'): return None
        if method=='GET' and path=='/api/account-closure/status':
            u=self.h.require()
            with self.store.connect() as db:
                require_active(db,u['id'],self.Error)
                admins=db.execute("SELECT count(*) FROM users u WHERE role='admin' AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')").fetchone()[0]
            return {'accountId':u['id'],'accountClosed':False,'canClose':u['role']!='admin' or admins>1,
              'lastActiveAdmin':u['role']=='admin' and admins<=1,'passwordConfirmationSeconds':CHALLENGE_TTL_MS//1000,
              'thirdPartyRenewalCancelled':False,'providersStatus':'pending-confirmation','backupsStatus':'pending-confirmation'}
        if method!='POST' or path not in ('/api/account-closure/prepare','/api/account-closure/confirm'):
            raise self.Error(404,'未找到此账号关闭接口。')
        d=self.h.body()
        if path.endswith('/prepare'): return self.prepare(d)
        try:
            return self.confirm(d)
        except sqlite3.IntegrityError as exc:
            if 'account_closure_last_admin' in str(exc): raise self.Error(409,'这是最后一个有效管理员，请先移交管理权限。') from None
            if 'account_closure_' in str(exc): raise self.Error(409,'确认已失效或账号状态已变化，请重新登录确认。') from None
            if 'account_closed' in str(exc): raise self.Error(401,'账号已关闭，请使用其他账号。') from None
            raise

    def prepare(self,d):
        key,nh=valid_request(d,('requestId','nonce','password'))
        u=self.h.require();owner=u['id'];self.limit('closure-prepare:'+owner,5)
        password=d.get('password')
        if not isinstance(password,str) or not 1<=len(password)<=128: raise ValueError('需要本人当前密码。')
        sh=digest(self.h.session_token);stamp=self.clock()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');require_active(db,owner,self.Error)
            live=db.execute('SELECT * FROM users WHERE id=?',(owner,)).fetchone()
            if not live or not self.verify(password,live['password']): raise self.Error(401,'当前密码不正确。')
            if not db.execute('SELECT 1 FROM sessions WHERE token=? AND user_id=? AND expires>?',(sh,owner,stamp)).fetchone(): raise self.Error(401,'请重新登录后确认。')
            old=db.execute('SELECT * FROM account_closure_challenges WHERE owner=? AND request_id=?',(owner,key)).fetchone()
            if old:
                if old['nonce_hash']!=nh or old['session_hash']!=sh: raise self.Error(409,'确认编号已用于另一操作。')
                row=old
            else:
                cid=str(uuid4())
                db.execute('INSERT INTO account_closure_challenges VALUES (?,?,?,?,?,?,?,0)',(cid,owner,key,nh,sh,stamp,stamp+CHALLENGE_TTL_MS))
                row=db.execute('SELECT * FROM account_closure_challenges WHERE id=?',(cid,)).fetchone()
        return {'challengeId':row['id'],'expiresAt':row['expires'],'secondConfirmationRequired':True,
                'accountClosed':False,'thirdPartyRenewalCancelled':False}

    def confirm(self,d):
        key,nh=valid_request(d,('requestId','nonce','challengeId','confirmed','renewalAcknowledged'))
        if d.get('confirmed') is not True or d.get('renewalAcknowledged') is not True: raise ValueError('请明确确认关闭账号及第三方续费提示。')
        cid=d.get('challengeId')
        if not isinstance(cid,str) or not 1<=len(cid)<=100: raise ValueError('确认凭证无效。')
        stamp=self.clock()
        # Completed replay accepts only the original strong nonce; no authenticated account access.
        self.limit('closure-confirm:'+digest(cid)[:24],10)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM account_closure_receipts WHERE challenge_id=?',(cid,)).fetchone()
            if old:
                if (self.h.user and self.h.user['id']!=old['owner']) or old['request_id']!=key or not hmac.compare_digest(old['nonce_hash'],nh): raise self.Error(404,'确认凭证无效。')
                result=self.receipt(old,db)
            else:
                u=self.h.require();owner=u['id'];require_active(db,owner,self.Error)
                challenge=db.execute('SELECT * FROM account_closure_challenges WHERE id=? AND owner=?',(cid,owner)).fetchone()
                if not challenge or challenge['request_id']!=key or challenge['nonce_hash']!=nh or challenge['session_hash']!=digest(self.h.session_token): raise self.Error(404,'确认凭证无效。')
                rid=str(uuid4())
                db.execute('INSERT INTO account_closure_receipts VALUES (?,?,?,?,?,?,?,?)',(rid,owner,cid,key,nh,str(uuid4()),stamp,'{}'))
                cleanup=self.cleanup(db,owner,rid,stamp)
                from card_imports import erase as card_import_erase
                from card_history_migration import privacy_delete_records as card_history_erase
                cleanup['cardImports']=card_import_erase(db,owner,'closure',rid,stamp);cleanup['cardLegacy']=card_history_erase(db,owner)
                from bazi_samples import erase as sample_erase
                cleanup['baziSamples']=sample_erase(db,owner,'closure',rid,stamp)
                db.execute('UPDATE account_closure_receipts SET details=? WHERE id=?',(json.dumps(cleanup,ensure_ascii=False),rid))
                from privacy_domains import append_closure_cleanup as append_domain_cleanup
                append_domain_cleanup(db,owner,rid,stamp)
                db.execute('UPDATE users SET password=? WHERE id=?',(secrets.token_hex(16)+':'+secrets.token_hex(32),owner))
                db.execute('UPDATE account_closure_challenges SET consumed=1 WHERE owner=?',(owner,))
                db.execute('INSERT OR IGNORE INTO account_revoked_sessions SELECT token,user_id,? FROM sessions WHERE user_id=?',(stamp,owner))
                db.execute('DELETE FROM sessions WHERE user_id=?',(owner,))
                db.execute("INSERT INTO account_lifecycle VALUES (?,'closed',1,?,?) ON CONFLICT(owner) DO UPDATE SET status='closed',epoch=epoch+1,closed_at=excluded.closed_at,receipt_id=excluded.receipt_id",(owner,stamp,rid))
                result=self.receipt(db.execute('SELECT * FROM account_closure_receipts WHERE id=?',(rid,)).fetchone(),db)
        return result


def integrity_response(exc):
    value=str(exc)
    if 'account_actor_inactive' in value or 'account_closed' in value:return (401,'账号或权限已失效，请重新登录。')
    if 'account_target_closed' in value:return (409,'对方账号已关闭，暂不可继续此操作。')
    if 'account_closure_last_admin' in value:return (409,'这是最后一个有效管理员，请先移交管理权限。')
    if 'account_' in value:return (409,'账号状态已变化，请重新确认。')
    return None
