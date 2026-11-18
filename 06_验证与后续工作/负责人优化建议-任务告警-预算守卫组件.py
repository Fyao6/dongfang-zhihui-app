"""Fresh synthetic SQLite component checks for the exact product fence INSERT/trigger.

No HTTP auth is faked and no business service is called.  This is a SQL component
check, not a formal business gate.  Each case uses a new in-memory database and
an actual callback inbox row to prove a rejected proof cannot increment attempts.
"""
from pathlib import Path
from datetime import datetime, timezone
import ast
import copy
import hashlib
import json
import sqlite3
import sys

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
BACK=ROOT/'04_研发源码/app/r4/backend'
sys.path.insert(0,str(BACK))
import local_tasks as product
import payment_callbacks

source=BACK/'local_tasks.py'
source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
tree=ast.parse(source.read_text(encoding='utf-8'))
fence=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='fence')
call=next(n for n in ast.walk(fence) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
          and n.func.attr=='execute' and n.args and 'INSERT INTO ops_claim_fences' in ast.unparse(n.args[0]))
sql=eval(compile(ast.Expression(call.args[0]),str(source),'eval'),{'NOW_SQL':product.NOW_SQL})
assert sql.count('?')==8 and product.NOW_SQL in sql


def component(name,budget,run_remaining,schedule_remaining,accepted,*,run_token='run-proof',role='admin',enabled=True):
    db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
    db.executescript('CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT);CREATE TABLE sessions(token TEXT PRIMARY KEY,user_id TEXT,expires INTEGER);CREATE TABLE account_lifecycle(owner TEXT,status TEXT);')
    db.executescript(product.DDL);db.executescript(product.claim_trigger_sql());db.executescript(payment_callbacks.DDL)
    cfg=copy.deepcopy(product.DEFAULT);cfg.update(enabled=enabled,confirmed=True,ruleVersion='component-approved',revision=7)
    cfg['tasks']['payment_callbacks']['enabled']=True
    stamp=db.execute('SELECT '+product.NOW_SQL).fetchone()[0]
    db.execute('INSERT INTO users VALUES(?,?)',('component-admin',role))
    db.execute('INSERT INTO sessions VALUES(?,?,?)',('component-session-hash','component-admin',stamp+60000))
    db.execute('INSERT INTO ops_runtime_identity VALUES(1,?,?,?,?)',('component-runtime','local-isolated',stamp,'component-manifest'))
    db.execute('INSERT INTO ops_task_config VALUES(1,?)',(product.canonical(cfg),))
    db.execute('INSERT INTO ops_workers VALUES(?,?,?,?,?,?,?,?,?)',('component-worker','component-runtime','component-admin','component-session-hash',stamp,'active','',stamp,stamp))
    db.execute('INSERT INTO ops_task_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('component-run','component-runtime','component-admin','component-worker','payment_callbacks','component-request','component-fingerprint',7,'run-proof',stamp+run_remaining,'running',stamp,0,0,'','{}'))
    db.execute('INSERT INTO ops_task_schedules VALUES(?,?,?,?,?,?)',('payment_callbacks',0,'schedule-proof',stamp+schedule_remaining,7,'component-run'))
    db.execute("INSERT INTO payment_callback_inbox(id,event_id,transaction_id,order_id,fingerprint,amount_minor,currency,status,created,updated) VALUES('component-receipt','component-event','component-transaction','component-order','component-fingerprint',300,'CNY','received',?,?)",(stamp,stamp))
    db.commit();blocked=False;error=''
    try:
        db.execute('BEGIN IMMEDIATE')
        db.execute(sql,('component-proof','component-run',run_token,'schedule-proof',7,'component-admin','component-session-hash',budget))
        # This is the native ordering being verified: proof before attempt++.
        db.execute("UPDATE payment_callback_inbox SET status='processing',attempts=attempts+1 WHERE id='component-receipt'")
        db.commit()
    except sqlite3.IntegrityError as exc:
        error=str(exc);assert error=='ops_claim_rejected';blocked=True;db.rollback()
    current=db.execute('SELECT '+product.NOW_SQL).fetchone()[0]
    attempts=db.execute("SELECT attempts FROM payment_callback_inbox WHERE id='component-receipt'").fetchone()[0]
    assert blocked is (not accepted),(name,'unexpected fence result',error)
    assert attempts==(1 if accepted else 0),(name,'attempt changed after rejected fence')
    assert db.execute('SELECT count(*) FROM ops_claim_fences').fetchone()[0]==0
    result={'name':name,'pass':True,'budgetMs':budget,'initialRunRemainingMs':run_remaining,
            'initialScheduleRemainingMs':schedule_remaining,'elapsedMs':current-stamp,
            'accepted':accepted,'callbackAttempts':attempts,'proofRows':0}
    db.close();return result


def main():
    checks=[
        component('callback_actual_run_500ms_rejected_before_attempt',1000,500,60000,False),
        component('callback_actual_schedule_500ms_rejected_before_attempt',1000,60000,500,False),
        component('callback_strict_1000ms_boundary_rejected',1000,1000,1000,False),
        component('callback_above_1000ms_accepted',1000,1200,1200,True),
        component('recovery_actual_500ms_rejected',9000,500,500,False),
        component('recovery_strict_9000ms_boundary_rejected',9000,9000,9000,False),
        component('recovery_above_9000ms_accepted',9000,9200,9200,True),
        component('metadata_zero_budget_keeps_valid_500ms',0,500,500,True),
        component('token_guard_preserved',1000,60000,60000,False,run_token='wrong-proof'),
        component('current_admin_guard_preserved',1000,60000,60000,False,role='user'),
        component('current_config_guard_preserved',1000,60000,60000,False,enabled=False),
    ]
    assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
    report={'at':datetime.now(timezone.utc).isoformat(),'pass':True,'passed':len(checks),'failed':0,
            'scope':'Actual product fence INSERT extracted from AST and unchanged trigger SQL on fresh synthetic SQLite; no formal HTTP/auth/settlement claim.',
            'sourceSHA256':source_hash,'sqlInsert':sql,'checks':checks,'productionEnabled':False,
            'oldDatabaseUsed':False,'businessOrQAFileChanged':False}
    path=OUT/'负责人优化建议-任务告警-预算守卫组件.json'
    assert not path.exists(),'Preserve previous component evidence'
    path.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'passed':len(checks),'failed':0,'sourceSHA256':source_hash,'report':str(path)},ensure_ascii=True))


if __name__=='__main__':main()
