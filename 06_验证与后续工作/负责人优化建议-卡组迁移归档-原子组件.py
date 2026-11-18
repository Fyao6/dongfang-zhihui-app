"""Fresh in-memory SQL components; not an HTTP or final acceptance gate."""
import hashlib,json,sqlite3,sys,time,traceback
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'04_研发源码/app/r4/backend'))
import card_history_migration as m
OUT=ROOT/'06_验证与后续工作'
checks=[]
def check(name,fn):
    try:fn();checks.append({'name':name,'passed':True})
    except Exception as error:checks.append({'name':name,'passed':False,'error':str(error)});raise
def eq(a,b):
    assert a==b,(a,b)
db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
db.executescript('CREATE TABLE users(id TEXT PRIMARY KEY);CREATE TABLE sessions(token TEXT,user_id TEXT,expires INTEGER);CREATE TABLE account_lifecycle(owner TEXT,status TEXT);CREATE TABLE card_record_epochs(owner TEXT PRIMARY KEY,revision INTEGER);CREATE TABLE records(owner TEXT,data TEXT);CREATE TABLE privacy_conversations(user_id TEXT,data TEXT);CREATE TABLE card_draw_actions(owner TEXT,note TEXT);')
m.init_schema(db)
owner='component-owner';token=hashlib.sha256(b'not-a-real-session').hexdigest()
db.execute('INSERT INTO users VALUES(?)',(owner,));db.execute('INSERT INTO sessions VALUES(?,?,?)',(token,owner,m.now()+600000));db.commit()
def guard(job,version,action,key='',fp='',epoch=0):
    ident=str(uuid4());db.execute('INSERT INTO card_history_migration_guards VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,owner,token,epoch,job,version,action,key,fp,m.now()));return ident
def preview(count,request=None,offset=0):
    ident=str(uuid4());request=request or str(uuid4());stamp=m.now()
    with db:
        gid=guard(ident,0,'preview',request,'digest')
        db.execute("INSERT INTO card_history_migration_jobs(id,owner,request_id,status,version,epoch,source_sha256,canonical_sha256,source_reference,data,total,created,updated) VALUES(?,?,?,'preview',1,0,?,?,?,'{}',?,?,?)",(ident,owner,request,'a'*64,'b'*64,'component',count,stamp,stamp))
        for ordinal in range(count):
            record=m.canonical({'cardId':'synthetic-'+str(ordinal+offset),'date':'2026-11-17','drawnAt':ordinal+offset});digest=m.sha(record)
            db.execute("INSERT INTO card_history_migration_targets(id,owner,job_id,ordinal,source_id,source_hash,record_data,status,created,updated) VALUES(?,?,?,?,?,?,?,'pending',?,?)",(str(uuid4()),owner,ident,ordinal,digest,digest,record,stamp,stamp))
        db.execute('DELETE FROM card_history_migration_guards WHERE id=?',(gid,))
    return ident
def process(job,version,action,key=None):
    key=key or str(uuid4());fp=m.sha(m.canonical([job,version,action,key]))
    with db:
        guard(job,version,action,key,fp);guard(job,version+1,'finish',key,fp)
    value=json.loads(db.execute('SELECT response_data FROM card_history_migration_operations WHERE owner=? AND request_id=?',(owner,key)).fetchone()[0]);return value
try:
    check('portable DDL installed',lambda:eq(db.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name LIKE 'card_history%' OR name='card_legacy_archives'").fetchone()[0],6))
    job=preview(101)
    def first():
        result=process(job,1,'apply');eq(result['receipt']['counts']['selected'],100);eq(result['summary']['added'],100);eq(result['summary']['remaining'],1);eq(db.execute('SELECT count(*) FROM card_legacy_archives').fetchone()[0],100)
    check('first real batch exactly100',first)
    def second():
        result=process(job,2,'apply');eq(result['receipt']['counts']['selected'],1);eq(result['summary']['added'],101);eq(result['summary']['remaining'],0)
    check('resume real remainder1',second)
    second_job=preview(101)
    def duplicate():
        result=process(second_job,1,'apply');eq(result['receipt']['counts']['added'],0);eq(result['receipt']['counts']['duplicate'],100);process(second_job,2,'apply');eq(db.execute('SELECT count(*) FROM card_legacy_archives').fetchone()[0],101)
    check('record hash repeated in other file never duplicated',duplicate)
    def undo_protected():
        result=process(job,3,'undo');eq(result['receipt']['counts']['protected'],100);eq(result['receipt']['counts']['undone'],0)
    check('later migrated references prevent undo',undo_protected)
    own=preview(3,offset=10000);process(own,1,'apply')
    changed=db.execute('SELECT * FROM card_legacy_archives WHERE created_job_id=? ORDER BY id LIMIT 1',(own,)).fetchone()
    def edit():
        with db:
            gid=guard(changed['id'],0,'edit');db.execute("UPDATE card_legacy_archives SET note='later personal note',favorite=1,revision=revision+1 WHERE id=?",(changed['id'],));db.execute('DELETE FROM card_history_migration_guards WHERE id=?',(gid,))
        result=process(own,2,'undo');eq(result['receipt']['counts']['skippedChanged'],1);eq(result['receipt']['counts']['undone'],2);eq(db.execute('SELECT count(*) FROM card_legacy_archives WHERE created_job_id=?',(own,)).fetchone()[0],1)
    check('note revision prevents undo while unchanged originals removed',edit)
    def stale():
        before=db.execute('SELECT count(*) FROM card_history_migration_receipts').fetchone()[0]
        try:process(own,2,'undo')
        except sqlite3.IntegrityError as error:eq(str(error),'card_history_changed')
        else:raise AssertionError('stale version accepted')
        eq(db.execute('SELECT count(*) FROM card_history_migration_receipts').fetchone()[0],before)
    check('stale CAS rolls back without receipt',stale)
    def closed():
        with db:db.execute("INSERT INTO account_lifecycle VALUES(?,'closed')",(owner,))
        try:process(second_job,3,'undo')
        except sqlite3.IntegrityError as error:eq(str(error),'account_actor_inactive')
        else:raise AssertionError('closed actor accepted')
        with db:db.execute('DELETE FROM account_lifecycle')
    check('actual session and closed actor final SQL fence',closed)
    def erase():
        with db:
            db.execute('INSERT INTO card_record_epochs VALUES(?,1)',(owner,));result=m.privacy_delete_records(db,owner)
        eq(db.execute('SELECT count(*) FROM card_legacy_archives').fetchone()[0],0);eq(db.execute('SELECT count(*) FROM card_history_migration_targets').fetchone()[0],0);eq(db.execute("SELECT count(*) FROM card_history_migration_jobs WHERE data!='{}' OR source_reference!='' OR status!='erased'").fetchone()[0],0)
        assert result['secureWipe'] is False
        try:guard(second_job,3,'undo')
        except sqlite3.IntegrityError as error:eq(str(error),'card_history_erased')
        else:raise AssertionError('old epoch accepted')
    check('same TX body erasure and old epoch rejection',erase)
finally:
    report={'module':'card-history-migration-atomic-component','at':m.now(),'formalAcceptance':False,'actualSQLite':True,'syntheticDataOnly':True,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks),'checks':checks,'sourceHashes':{str(p.relative_to(ROOT)).replace('\\','/'):m.sha(p.read_bytes()) for p in [Path(m.__file__),Path(m.__file__).with_name('card_history_migration_schema.sql')]}}
    path=OUT/('负责人优化建议-卡组迁移归档-原子组件-'+str(time.time_ns())+'.json');path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(path.name,report['passed'],report['failed'])
