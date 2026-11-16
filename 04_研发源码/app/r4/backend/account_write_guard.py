"""Request write fences; trusted internal settlement is limited to existing facts."""
from contextvars import ContextVar
from contextlib import contextmanager
import re
import sqlite3
import time
from uuid import uuid4

ACTOR=ContextVar('account_request_actor',default=None)
SERVICE=ContextVar('account_settlement',default=None)
DDL=[
"CREATE TABLE IF NOT EXISTS account_action_fences(id TEXT PRIMARY KEY,actor TEXT NOT NULL,session_hash TEXT NOT NULL,roles TEXT NOT NULL,created INTEGER NOT NULL)",
"""CREATE TRIGGER IF NOT EXISTS account_action_fence_check BEFORE INSERT ON account_action_fences BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.id=NEW.actor AND s.token=NEW.session_hash AND s.expires>NEW.created AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed') AND (json_array_length(NEW.roles)=0 OR u.role IN (SELECT value FROM json_each(NEW.roles)))) THEN RAISE(ABORT,'account_actor_inactive') END;
 END""",
"CREATE TRIGGER IF NOT EXISTS account_action_fence_forget AFTER INSERT ON account_action_fences BEGIN DELETE FROM account_action_fences WHERE id=NEW.id; END"
]
def init_schema(db):
    for sql in DDL: db.execute(sql)
def begin_actor(owner,session_hash):return ACTOR.set({'owner':owner,'sessionHash':session_hash,'roles':[]})
def end_actor(token):ACTOR.reset(token)
def require_roles(roles):
    actor=ACTOR.get()
    if actor is not None and roles:actor['roles']=list(roles)
def mutation(sql):return bool(re.match(r'\s*(INSERT|UPDATE|DELETE|REPLACE)\b',sql,re.I))
def target(sql):
    m=re.match(r'\s*(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|REPLACE\s+INTO|UPDATE(?:\s+OR\s+\w+)?|DELETE\s+FROM)\s+([a-z_][a-z_0-9]*)',sql,re.I)
    return m.group(1).lower() if m else ''
def service_allowed(sql,kind):
    table=target(sql);op=sql.lstrip().split()[0].upper()
    if table=='audits' and op=='INSERT':return True
    if kind=='session':return table=='sessions' and op in ('INSERT','DELETE')
    if kind=='gateway':
        if table=='ai_gateway_jobs':return op=='UPDATE'
        if table=='ai_gateway_attempts':return op in ('INSERT','UPDATE')
        if table=='privacy_transfers':return op=='INSERT'
        if table=='privacy_conversations':
            return op=='INSERT' and 'SELECT' in sql.upper() and all(x in sql for x in ('revision','provider_binding','saveConversations'))
        return False
    return kind=='order' and (table.startswith('membership_') or table.startswith('commission_'))
def validate_fact(db,scope):
    kind,ident,owner=scope
    if kind=='session':
        return db.execute("SELECT 1 FROM users u WHERE id=? AND NOT EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=u.id AND status='closed')",(owner,)).fetchone()
    if kind=='gateway':return db.execute('SELECT 1 FROM ai_gateway_jobs WHERE id=? AND owner=?',(ident,owner)).fetchone()
    if kind=='order':return db.execute("SELECT 1 FROM commerce_orders o WHERE o.id=? AND o.owner=? AND EXISTS(SELECT 1 FROM commerce_payment_events p WHERE p.order_id=o.id AND p.status='applied' AND p.kind IN ('sandbox_pay','refund'))",(ident,owner)).fetchone()
    return False
@contextmanager
def settlement_scope(kind,ident,owner):
    if kind not in ('gateway','order','session'):raise ValueError('unsupported internal settlement')
    token=SERVICE.set((kind,ident,owner))
    try:yield
    finally:SERVICE.reset(token)
class GuardedConnection:
    def __init__(self,db):self._db=db;self._fenced=False
    def __getattr__(self,key):return getattr(self._db,key)
    def execute(self,sql,args=()):
        if mutation(sql):
            if not self._db.in_transaction:self._fenced=False
            scope=SERVICE.get()
            if scope:
                if not self._db.in_transaction:self._db.execute('BEGIN IMMEDIATE')
                if not service_allowed(sql,scope[0]) or not validate_fact(self._db,scope):raise sqlite3.IntegrityError('account_settlement_denied')
            elif target(sql)=='audits' and sql.lstrip().upper().startswith('INSERT'):
                pass
            elif not self._fenced:
                actor=ACTOR.get()
                if actor and actor['owner']:
                    import json
                    if not self._db.in_transaction:self._db.execute('BEGIN IMMEDIATE')
                    self._db.execute('INSERT INTO account_action_fences VALUES(?,?,?,?,?)',(str(uuid4()),actor['owner'],actor['sessionHash'],json.dumps(actor['roles']),time.time_ns()//1_000_000))
                    self._fenced=True
        return self._db.execute(sql,args)
    def executemany(self,sql,args):
        cursor=None
        for row in args:cursor=self.execute(sql,row)
        return cursor
    def executescript(self,script):
        if ACTOR.get() is None and SERVICE.get() is None:return self._db.executescript(script)
        statement=''
        for character in script:
            statement+=character
            if sqlite3.complete_statement(statement):self.execute(statement);statement=''
        if statement.strip():self.execute(statement)
        return self
def guard_connection(db):return GuardedConnection(db)
