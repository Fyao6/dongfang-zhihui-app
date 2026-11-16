from memory_service import memory_save_guard, dump as memory_dump
"""Owner-only saved request snapshots. Long-term memory is not implemented or enabled."""
import importlib.util
import json
from pathlib import Path
import re
import time
from uuid import uuid4

DDL='''
CREATE TABLE IF NOT EXISTS privacy_saved_deletions(id TEXT PRIMARY KEY,owner TEXT NOT NULL,snapshot_id TEXT NOT NULL,request_id TEXT NOT NULL,details TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,request_id),UNIQUE(owner,snapshot_id));
CREATE INDEX IF NOT EXISTS privacy_saved_deletions_owner ON privacy_saved_deletions(owner,created);
CREATE TRIGGER IF NOT EXISTS privacy_saved_deleted_id_guard BEFORE INSERT ON privacy_conversations WHEN EXISTS(SELECT 1 FROM privacy_saved_deletions WHERE owner=NEW.user_id AND snapshot_id=NEW.id) BEGIN SELECT RAISE(ABORT,'privacy_saved_snapshot_deleted'); END;
'''

def init_schema(db):
    db.executescript(DDL)

def stamp():return time.time_ns()//1_000_000
def dump(v):return json.dumps(v,ensure_ascii=False,separators=(',',':'),sort_keys=True,allow_nan=False)
def privacy_module():
    try:
        import privacy
        return privacy
    except ModuleNotFoundError:
        spec=importlib.util.spec_from_file_location('saved_snapshot_frozen_privacy',Path(__file__).with_name('privacy.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

def decoded(row):
    try:data=json.loads(row['data'])
    except (ValueError,TypeError):data=None
    gateway=isinstance(data,dict) and isinstance(data.get('input'),list) and isinstance(data.get('output'),str)
    raw=data['input'] if gateway else data if isinstance(data,list) else None
    messages=[];providers=set()
    if raw is not None:
        for m in raw:
            if not isinstance(m,dict) or m.get('role') not in ('user','assistant'):continue
            text=m.get('content',m.get('text'))
            if isinstance(text,str):messages.append({'role':m['role'],'content':text})
            tag=m.get('privacy')
            if isinstance(tag,dict) and isinstance(tag.get('providerId'),str) and re.fullmatch('[A-Za-z0-9_-]{1,80}',tag['providerId']):providers.add(tag['providerId'])
    if gateway:
        messages.append({'role':'assistant','content':data['output']})
        if isinstance(data.get('providerId'),str) and re.fullmatch('[A-Za-z0-9_-]{1,80}',data['providerId']):providers.add(data['providerId'])
    return {'format':'gateway-request-snapshot' if gateway else 'message-history-snapshot' if raw is not None else 'unrecognized-saved-record','messages':messages,'providerIds':sorted(providers),'recognized':raw is not None}

def metadata(row):
    d=decoded(row)
    return {'id':row['id'],'createdAt':row['created'],'kind':'saved-request-snapshot','format':d['format'],'messageCount':len(d['messages']) if d['recognized'] else None,'bodyAvailable':d['recognized'],'providerIds':d['providerIds']}

def deletion_item(row):return {'id':row['id'],'snapshotId':row['snapshot_id'],'requestId':row['request_id'],'createdAt':row['created'],'details':json.loads(row['details'])}

def guarded_legacy_save(store,user_id,messages,memory_proof=None):
    """Replace the legacy entry hook only when this independent module is integrated. No provider call."""
    if not isinstance(messages,list) or not 1<=len(messages)<=13:return False
    try:content=dump(messages)
    except (TypeError,ValueError):return False
    if len(content)>100000:return False
    pmod=privacy_module()
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        p=pmod.preferences(db,user_id);cfg=pmod.config(store);ai=store.setting('ai');binding=pmod.actual_binding(cfg,ai)
        if not binding or not p['consents']['saveConversations'] or p['policyVersion']!=cfg['policyVersion'] or p['providerBinding']!=binding['digest']:return False
        if db.execute("SELECT 1 FROM privacy_requests WHERE user_id=? AND kind='close-account' AND status!='cancelled'",(user_id,)).fetchone():return False
        epoch=str(p['revision'])+':'+cfg['policyVersion']+':'+binding['digest'];allowed=['general','card']+[k for k in ('chart','wellbeing') if p['consents'][k]]
        for m in messages:
            if not isinstance(m,dict) or m.get('role') not in ('user','assistant') or not isinstance(m.get('content'),str):return False
            tag=m.get('privacy')
            if not isinstance(tag,dict) or tag.get('accountId')!=user_id or tag.get('providerId')!=ai.get('providerId') or tag.get('providerBinding')!=binding['digest'] or tag.get('policyVersion')!=cfg['policyVersion'] or tag.get('consentEpoch')!=epoch or tag.get('category') not in allowed or tag.get('source') not in ('user','assistant','report') or tag.get('source')=='report' and tag.get('category')=='general':return False
        memory_sql,memory_args=memory_save_guard(memory_proof)
        if not db.execute('SELECT 1 WHERE '+memory_sql,memory_args).fetchone():return False
        for m in messages:
            selected=m['privacy'].get('memorySelection')
            if selected is not None and (memory_proof is None or memory_dump(selected)!=memory_dump(memory_proof['selection'])):return False
        db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',(str(uuid4()),user_id,content,stamp()))
        return True

class SavedConversations:
    def __init__(self,store,handler,error,limiter):self.store,self.h,self.Error,self.rate=store,handler,error,limiter
    def fail(self,n,s):raise self.Error(n,s)
    def route(self,method,path):
        if path!='/api/privacy/saved-conversations' and not path.startswith('/api/privacy/saved-conversations/'):return None
        user=self.h.require();owner=user['id'];self.rate('privacy-snapshots:'+owner,60)
        with self.store.connect() as db:
            if path=='/api/privacy/saved-conversations' and method=='GET':
                rows=db.execute('SELECT * FROM privacy_conversations WHERE user_id=? ORDER BY created DESC,id DESC LIMIT 100',(owner,)).fetchall()
                count=db.execute('SELECT count(*) FROM privacy_conversations WHERE user_id=?',(owner,)).fetchone()[0]
                return {'items':[metadata(r) for r in rows],'storedSnapshotCount':count,'returnedCount':len(rows),'hasMore':count>len(rows),'threadsRepresented':False,'memoryAvailable':False,'automaticAIRead':False}
            if path=='/api/privacy/saved-conversations/deletions' and method=='GET':return {'items':[deletion_item(r) for r in db.execute('SELECT * FROM privacy_saved_deletions WHERE owner=? ORDER BY created DESC LIMIT 100',(owner,))]}
            match=re.fullmatch('/api/privacy/saved-conversations/([^/]+)(/delete)?',path)
            if not match:self.fail(404,'未找到本人保存快照接口。')
            identifier,action=match.groups()
            if not action and method=='GET':
                row=db.execute('SELECT * FROM privacy_conversations WHERE user_id=? AND id=?',(owner,identifier)).fetchone()
                if not row:self.fail(404,'未找到本人已保存快照。')
                return {'item':{**metadata(row),'messages':decoded(row)['messages']},'automaticAIRead':False}
            if action=='/delete' and method=='POST':
                data=self.h.body()
                if set(data)!={'requestId','confirmed'} or data['confirmed'] is not True or not isinstance(data['requestId'],str) or not 8<=len(data['requestId'])<=100:self.fail(400,'删除须明确确认当前快照并提供幂等请求号。')
                db.execute('BEGIN IMMEDIATE')
                old=db.execute('SELECT * FROM privacy_saved_deletions WHERE owner=? AND request_id=?',(owner,data['requestId'])).fetchone()
                if old:
                    if old['snapshot_id']!=identifier:self.fail(409,'删除请求号已用于另一条保存快照。')
                    return {'item':deletion_item(old),'replayed':True}
                old=db.execute('SELECT * FROM privacy_saved_deletions WHERE owner=? AND snapshot_id=?',(owner,identifier)).fetchone()
                if old:return {'item':deletion_item(old),'replayed':True}
                row=db.execute('SELECT * FROM privacy_conversations WHERE user_id=? AND id=?',(owner,identifier)).fetchone()
                if not row:self.fail(404,'未找到本人已保存快照。')
                providers=decoded(row)['providerIds'];cfg=self.store.setting('privacy');now=stamp();receipt=str(uuid4())
                details={'local':{'status':'completed','deletedSnapshots':1},'providers':[{'id':p,'status':'pending-confirmation'} for p in providers],'unknownProviderNeedsReview':not bool(providers),'backups':{'status':'pending-confirmation','retentionDays':(cfg.get('retention') or {}).get('backupDays')},'vectorIndex':{'available':False,'status':'not-implemented'},'memory':{'available':False,'status':'not-stored'},'localBrowserCleared':False,'otherSavedSnapshotsDeleted':False,'retainedCategories':['account','ai-request-quota-metadata','snapshot-deletion-receipt'],'receiptContainsBody':False}
                db.execute('INSERT INTO privacy_saved_deletions VALUES(?,?,?,?,?,?)',(receipt,owner,identifier,data['requestId'],dump(details),now))
                db.execute("INSERT INTO privacy_preferences VALUES(?,?,?,1,?,'') ON CONFLICT(user_id) DO UPDATE SET revision=revision+1,updated=excluded.updated",(owner,dump(dict.fromkeys(('chart','wellbeing','saveConversations','longTermMemory','trainingImprovement','marketing'),False)),'',now))
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_gateway_jobs'").fetchone():db.execute('UPDATE ai_gateway_jobs SET saved_conversation_id=NULL,output_text=NULL WHERE owner=? AND saved_conversation_id=?',(owner,identifier))
                db.execute('DELETE FROM privacy_conversations WHERE user_id=? AND id=?',(owner,identifier))
                self.store.audit(db,owner,'privacy.saved_snapshot.delete',identifier,'仅删除本人选定保存快照；供应商及备份待确认；审计无正文')
                return {'item':deletion_item(db.execute('SELECT * FROM privacy_saved_deletions WHERE id=?',(receipt,)).fetchone()),'replayed':False}
        self.fail(404,'未找到本人保存快照接口。')
