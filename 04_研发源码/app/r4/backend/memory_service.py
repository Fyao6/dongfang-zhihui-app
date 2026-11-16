"""Owner-maintained opt-in memory. No automatic extraction, vector store or supplier deletion claim."""
import hashlib
import json
import re
import sqlite3
import time
from uuid import uuid4

CATEGORIES=('general','card','chart','wellbeing')
MAX_ENTRIES=100
MAX_ITEM_CHARS=2000
MAX_SELECTION=5
MAX_SELECTED_CHARS=6000
DISCLOSURE_VERSION='manual-memory-v1'
SCHEMA=[
"CREATE TABLE IF NOT EXISTS memory_state(owner TEXT PRIMARY KEY,epoch INTEGER NOT NULL DEFAULT 0 CHECK(epoch>=0),updated INTEGER NOT NULL)",
"CREATE TABLE IF NOT EXISTS memory_entries(id TEXT PRIMARY KEY,owner TEXT NOT NULL REFERENCES users(id),category TEXT NOT NULL CHECK(category IN ('general','card','chart','wellbeing')),title TEXT NOT NULL,text TEXT NOT NULL,version INTEGER NOT NULL CHECK(version>=1),created INTEGER NOT NULL,updated INTEGER NOT NULL)",
"CREATE INDEX IF NOT EXISTS memory_entries_owner ON memory_entries(owner,updated,id)",
"CREATE TABLE IF NOT EXISTS memory_actions(id TEXT PRIMARY KEY,owner TEXT NOT NULL,request_id TEXT NOT NULL,operation TEXT NOT NULL,entry_id TEXT NOT NULL,semantic_hash TEXT NOT NULL,expected_epoch INTEGER NOT NULL,expected_version INTEGER,applied_version INTEGER,nonce TEXT NOT NULL,details TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,request_id))",
"CREATE TABLE IF NOT EXISTS memory_tombstones(owner TEXT NOT NULL,entry_id TEXT NOT NULL,last_version INTEGER NOT NULL,operation_id TEXT NOT NULL,deleted_at INTEGER NOT NULL,PRIMARY KEY(owner,entry_id))",
"CREATE TABLE IF NOT EXISTS memory_provider_consents(owner TEXT NOT NULL,provider_id TEXT NOT NULL,provider_binding TEXT NOT NULL,policy_version TEXT NOT NULL,global_revision INTEGER NOT NULL,memory_epoch INTEGER NOT NULL,nonce TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,PRIMARY KEY(owner,provider_id))",
"CREATE TABLE IF NOT EXISTS memory_cleanup_receipts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,operation_id TEXT NOT NULL,nonce TEXT NOT NULL,status TEXT NOT NULL,details TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,operation_id))",
"CREATE TABLE IF NOT EXISTS memory_job_bindings(job_id TEXT PRIMARY KEY,owner TEXT NOT NULL,memory_epoch INTEGER NOT NULL,selection TEXT NOT NULL,policy_version TEXT NOT NULL,global_revision INTEGER NOT NULL,global_binding TEXT NOT NULL,created INTEGER NOT NULL,request_fingerprint TEXT NOT NULL,context_characters INTEGER NOT NULL CHECK(context_characters BETWEEN 0 AND 6000))",
"""CREATE TRIGGER IF NOT EXISTS memory_action_check BEFORE INSERT ON memory_actions BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') THEN RAISE(ABORT,'memory_account_closed') END;
 SELECT CASE WHEN NEW.expected_epoch!=coalesce((SELECT epoch FROM memory_state WHERE owner=NEW.owner),0) THEN RAISE(ABORT,'memory_epoch_changed') END;
 SELECT CASE WHEN NEW.operation IN ('edit','delete') AND NOT EXISTS(SELECT 1 FROM memory_entries WHERE id=NEW.entry_id AND owner=NEW.owner AND version=NEW.expected_version) THEN RAISE(ABORT,'memory_version_changed') END;
 SELECT CASE WHEN NEW.operation='add' AND NOT EXISTS(SELECT 1 FROM privacy_preferences WHERE user_id=NEW.owner AND json_extract(data,'$.longTermMemory')=1) THEN RAISE(ABORT,'memory_disabled') END;
 END""",
"""CREATE TRIGGER IF NOT EXISTS memory_entry_insert_check BEFORE INSERT ON memory_entries BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') THEN RAISE(ABORT,'memory_account_closed') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM memory_tombstones WHERE owner=NEW.owner AND entry_id=NEW.id) THEN RAISE(ABORT,'memory_deleted_id') END;
 SELECT CASE WHEN (SELECT count(*) FROM memory_entries WHERE owner=NEW.owner)>=100 THEN RAISE(ABORT,'memory_capacity') END;
 END""",
"CREATE TRIGGER IF NOT EXISTS memory_entry_update_check BEFORE UPDATE ON memory_entries WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') OR NEW.owner!=OLD.owner OR NEW.id!=OLD.id OR NEW.version!=OLD.version+1 BEGIN SELECT RAISE(ABORT,'memory_version_changed'); END",
"INSERT OR IGNORE INTO settings VALUES('memory_service','{\"memoryRetentionDays\":null,\"revision\":0}')",
]
def init_schema(db):
    for sql in SCHEMA:db.execute(sql)
def stamp():return time.time_ns()//1_000_000
def dump(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),sort_keys=True,allow_nan=False)
def fingerprint(value):return hashlib.sha256(dump(value).encode()).hexdigest()
def epoch(db,owner):
    row=db.execute('SELECT epoch FROM memory_state WHERE owner=?',(owner,)).fetchone()
    return row[0] if row else 0
def bump_epoch(db,owner,now):
    db.execute('INSERT INTO memory_state VALUES(?,1,?) ON CONFLICT(owner) DO UPDATE SET epoch=memory_state.epoch+1,updated=excluded.updated',(owner,now))
    return epoch(db,owner)
def on_preferences_change(db,owner,old_consents,new_consents,now):
    # Same preferences transaction. No duplicated enabled flag or generic record/card epoch.
    if old_consents.get('longTermMemory') is True and new_consents.get('longTermMemory') is not True:
        value=bump_epoch(db,owner,now);cancel_memory_jobs(db,owner);return value
    return epoch(db,owner)
def public_memory_state(store,owner,prefs,*,include_count=True):
    with store.connect() as db:
        value=epoch(db,owner)
        count=db.execute('SELECT count(*) FROM memory_entries WHERE owner=?',(owner,)).fetchone()[0] if include_count else None
        has_retention=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='privacy_retention_config'").fetchone()
        row=db.execute('SELECT data FROM privacy_retention_config WHERE id=1').fetchone() if has_retention else None
    cfg=json.loads(row[0]) if row else {}
    return {'available':True,'enabled':prefs['consents'].get('longTermMemory') is True,
       'memoryEpoch':value,'storedCount':count,'items':[],'automaticRead':False,'automaticExtraction':False,
       'vectorStoreAvailable':False,'disclosureVersion':DISCLOSURE_VERSION,'memoryRetentionDays':cfg.get('retentionDays',{}).get('memory'),
       'limits':{'storedItems':MAX_ENTRIES,'itemCharacters':MAX_ITEM_CHARS,'selectedItems':MAX_SELECTION,'selectedCharacters':MAX_SELECTED_CHARS}}
def assert_active(db,owner,Error):
    if not db.execute('SELECT 1 FROM users WHERE id=?',(owner,)).fetchone():raise Error(401,'请重新登录。')
    if db.execute("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'",(owner,)).fetchone():raise Error(401,'账号已关闭。')
def require_enabled(p,Error):
    if not p.get('policyAcknowledged') or not p.get('disclosure',{}).get('configured'):raise Error(403,'请先确认当前数据处理说明。')
    if p.get('consents',{}).get('longTermMemory') is not True:raise Error(403,'长期记忆已关闭；AI不会读取既有记忆。')
def exact(data,allowed,Error):
    if not isinstance(data,dict) or set(data)-set(allowed):raise Error(400,'记忆请求包含不支持的字段。')
def integer(value,Error,label='版本',minimum=0):
    if type(value) is not int or value<minimum or value>9007199254740991:raise Error(400,label+'须为有效整数。')
    return value
def text(value,maximum,Error,label):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any((ord(c)<32 and c not in '\t\r\n') or 0xD800<=ord(c)<=0xDFFF for c in value):raise Error(400,label+'格式不正确或超过长度限制。')
    return value
def request_id(data,Error):
    value=data.get('requestId')
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{8,100}',value):raise Error(400,'需要8至100位幂等请求编号。')
    return value
def metadata(row):
    return {'id':row['id'],'category':row['category'],'title':row['title'],'version':row['version'],'characterCount':len(row['text']),'createdAt':row['created'],'updatedAt':row['updated']}
def entry(row):
    return {**metadata(row),'text':row['text']} if row else None

class MemoryService:
    def __init__(self,store,h,Error,limiter,*,test_clock=None,provider_authorization=None):
        self.store,self.h,self.Error,self.rate=store,h,Error,limiter
        self.owner=h.user['id'] if h.user else ''
        self.clock=test_clock or stamp
        self.provider_authorization=provider_authorization or self.default_provider_authorization
    def fail(self,n,message):raise self.Error(n,message)
    def privacy(self):
        from privacy import Privacy
        return Privacy(self.store,self.h,self.Error,self.rate).response()
    def state(self):
        p=self.privacy()
        return {'accountId':self.owner,**public_memory_state(self.store,self.owner,p),
          'authorizedForNewMemory':bool(p.get('policyAcknowledged') and p.get('disclosure',{}).get('configured') and p['consents'].get('longTermMemory')),
          'policyVersion':p['disclosure']['policyVersion'],'providerBinding':p.get('providerBinding'),'privacyRevision':p['revision']}
    def own(self,db,ident):
        row=db.execute('SELECT * FROM memory_entries WHERE id=? AND owner=?',(ident,self.owner)).fetchone()
        if not row:self.fail(404,'未找到本人这条记忆。')
        return row
    def result(self,db,row,replayed=False):
        details=json.loads(row['details'])
        current=db.execute('SELECT * FROM memory_entries WHERE id=? AND owner=?',(row['entry_id'],self.owner)).fetchone() if row['entry_id'] else None
        return {'receipt':{'id':row['id'],'operation':row['operation'],'entryId':row['entry_id'] or None,'appliedVersion':row['applied_version'],'createdAt':row['created'],'details':details},
                'currentItem':entry(current),'memoryEpoch':epoch(db,self.owner),'replayed':replayed}
    def mutate(self,operation,data,ident=''):
        allowed=('requestId','memoryEpoch','category','title','text') if operation=='add' else ('requestId','memoryEpoch','expectedVersion','category','title','text') if operation=='edit' else ('requestId','memoryEpoch','expectedVersion','confirmed') if operation=='delete' else ('requestId','memoryEpoch','confirmed')
        exact(data,allowed,self.Error);key=request_id(data,self.Error);expected=integer(data.get('memoryEpoch'),self.Error,'记忆版本')
        version=integer(data.get('expectedVersion'),self.Error,minimum=1) if operation in ('edit','delete') else None
        values={}
        if operation in ('add','edit'):
            category=data.get('category')
            if category not in CATEGORIES:self.fail(400,'请选择有效记忆类别。')
            values={'category':category,'title':text(data.get('title'),80,self.Error,'标题'),'text':text(data.get('text'),MAX_ITEM_CHARS,self.Error,'记忆内容')}
        elif data.get('confirmed') is not True:self.fail(400,'请明确确认删除。')
        semantic=fingerprint({'operation':operation,'entryId':ident,'memoryEpoch':expected,'expectedVersion':version,**values})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');assert_active(db,self.owner,self.Error)
            old=db.execute('SELECT * FROM memory_actions WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if old:
                if old['semantic_hash']!=semantic:self.fail(409,'请求编号已用于不同的记忆操作。')
                return self.result(db,old,True)
            if epoch(db,self.owner)!=expected:self.fail(409,'记忆已变更，请重新读取后再操作。')
            if operation=='add':
                p=self.privacy();require_enabled(p,self.Error)
                if values['category'] in ('chart','wellbeing') and p['consents'].get(values['category']) is not True:self.fail(403,'此类记忆需要对应资料授权。')
            if operation in ('edit','delete'):
                previous=self.own(db,ident)
                if previous['version']!=version:self.fail(409,'这条记忆已更新，请重新查看。')
            else:previous=None
            now=self.clock();action=str(uuid4());nonce=str(uuid4());target=ident or (str(uuid4()) if operation=='add' else '')
            applied=1 if operation=='add' else version+1 if operation=='edit' else version
            details={'localStatus':'completed','savedConversationsDeleted':False,'automaticExtraction':False}
            if operation in ('delete','clear'):details.update(providersStatus='pending-confirmation',backupsStatus='pending-confirmation',vectorStoreStatus='not-implemented')
            db.execute('INSERT INTO memory_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(action,self.owner,key,operation,target,semantic,expected,version,applied,nonce,dump(details),now))
            if operation=='add':
                db.execute('INSERT INTO memory_entries VALUES(?,?,?,?,?,?,?,?)',(target,self.owner,values['category'],values['title'],values['text'],1,now,now))
            elif operation=='edit':
                db.execute('UPDATE memory_entries SET category=?,title=?,text=?,version=version+1,updated=? WHERE id=? AND owner=? AND version=?',(values['category'],values['title'],values['text'],now,target,self.owner,version))
            else:
                where='owner=?'+(' AND id=?' if operation=='delete' else '');args=[self.owner]+([target] if operation=='delete' else [])
                deleted=db.execute('SELECT id,version FROM memory_entries WHERE '+where,args).fetchall()
                for item in deleted:db.execute('INSERT OR IGNORE INTO memory_tombstones VALUES(?,?,?,?,?)',(self.owner,item['id'],item['version'],action,now))
                db.execute('DELETE FROM memory_entries WHERE '+where,args);bump_epoch(db,self.owner,now);cancel_memory_jobs(db,self.owner)
                details['deletedItems']=len(deleted)
                db.execute('UPDATE memory_actions SET details=? WHERE id=?',(dump(details),action))
            return self.result(db,db.execute('SELECT * FROM memory_actions WHERE id=?',(action,)).fetchone())
    def route(self,method,path):
        try:return self._route(method,path)
        except sqlite3.IntegrityError as exc:
            message=str(exc)
            if 'memory_account_closed' in message:self.fail(401,'账号已关闭。')
            if 'memory_disabled' in message:self.fail(403,'长期记忆已关闭。')
            if 'memory_' in message or 'UNIQUE' in message or 'CHECK constraint' in message:self.fail(409,'记忆或授权已变化，请重新读取后操作。')
            raise
    def _route(self,method,path):
        if path!='/api/memory' and not path.startswith('/api/memory/'):return None
        self.h.require();self.owner=self.h.user['id']
        self.rate(('memory-read:' if method=='GET' else 'memory-write:')+self.owner,180 if method=='GET' else 30)
        with self.store.connect() as db:assert_active(db,self.owner,self.Error)
        if path=='/api/memory' and method=='GET':
            with self.store.connect() as db:rows=db.execute('SELECT * FROM memory_entries WHERE owner=? ORDER BY updated DESC,id LIMIT 100',(self.owner,)).fetchall()
            return {'items':[metadata(r) for r in rows],'settings':self.state(),'onlyRequestedEntriesReadByAI':True}
        if path=='/api/memory/settings' and method=='GET':return self.state()
        if path=='/api/memory/export' and method=='GET':
            with self.store.connect() as db:rows=db.execute('SELECT * FROM memory_entries WHERE owner=? ORDER BY created,id',(self.owner,)).fetchall()
            return {'accountId':self.owner,'items':[entry(r) for r in rows],'settings':self.state(),'providerDeletionConfirmed':False,'backupDeletionConfirmed':False}
        if path=='/api/memory' and method=='POST':return self.mutate('add',self.h.body())
        if path=='/api/memory/clear' and method=='POST':return self.mutate('clear',self.h.body())
        if path=='/api/memory/providers' and method=='GET':return self.providers()
        provider=re.fullmatch(r'/api/memory/providers/([A-Za-z0-9_-]{1,80})/consent',path)
        if provider and method=='POST':return self.provider_consent(provider.group(1),self.h.body())
        if provider and method=='DELETE':return self.provider_revoke(provider.group(1),self.h.body())
        match=re.fullmatch(r'/api/memory/items/([A-Za-z0-9_-]{1,100})(/delete)?',path)
        if match:
            ident,action=match.groups()
            if method=='GET' and not action:
                with self.store.connect() as db:return {'item':entry(self.own(db,ident)),'settings':self.state(),'automaticAIRead':False}
            if method=='PATCH' and not action:return self.mutate('edit',self.h.body(),ident)
            if method=='POST' and action:return self.mutate('delete',self.h.body(),ident)
        self.fail(404,'未找到本人记忆接口。')

    def default_provider_authorization(self,provider_id,require_receipt):
        from ai_gateway import AIGateway
        gateway=AIGateway(self.store,self.h,self.Error,self.rate)
        return gateway.authorization(gateway.provider(provider_id),require_receipt=require_receipt)
    def providers(self):
        p=self.privacy();items=[]
        with self.store.connect() as db:
            current_epoch=epoch(db,self.owner)
            rows={r['provider_id']:r for r in db.execute('SELECT * FROM memory_provider_consents WHERE owner=?',(self.owner,))}
        for provider in p['disclosure']['recipients']:
            auth=None;error=''
            try:auth=self.provider_authorization(provider['id'],False)
            except self.Error as exc:error=str(exc)
            row=rows.get(provider['id'])
            valid=bool(auth and auth.get('receiptValid') and row and row['nonce'] and row['provider_binding']==auth['providerBinding'] and row['policy_version']==auth['policyVersion'] and row['global_revision']==p['revision'] and row['memory_epoch']==current_epoch and p.get('policyAcknowledged') and p['consents'].get('longTermMemory'))
            items.append({'id':provider['id'],'name':provider['name'],'purpose':provider['purpose'],'regions':provider['regions'],'policyUrl':provider['policyUrl'],'authorization':auth,'memoryAcknowledged':valid,'blockingReason':error})
        return {'items':items,'memoryEpoch':current_epoch,'disclosureVersion':DISCLOSURE_VERSION}
    def provider_consent(self,provider_id,data):
        exact(data,('requestId','acknowledged','providerBinding','policyVersion','globalRevision','memoryEpoch'),self.Error)
        key=request_id(data,self.Error);expected=integer(data.get('memoryEpoch'),self.Error,'记忆版本');integer(data.get('globalRevision'),self.Error,'隐私版本')
        if data.get('acknowledged') is not True:self.fail(400,'须单独明确确认当前供应商使用长期记忆。')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');assert_active(db,self.owner,self.Error)
            p=self.privacy();require_enabled(p,self.Error)
            auth=self.provider_authorization(provider_id,True);_authorization_matches(auth,p,self.owner,self.Error)
            if auth['providerId']!=provider_id or auth.get('receiptValid') is not True or not auth.get('providerConsentRevision') or data.get('providerBinding')!=auth['providerBinding'] or data.get('policyVersion')!=auth['policyVersion'] or data['globalRevision']!=auth['globalRevision'] or expected!=epoch(db,self.owner):self.fail(409,'供应商或隐私版本已变化，请重新确认。')
            semantic=fingerprint({'operation':'provider-consent','providerId':provider_id,'providerBinding':data['providerBinding'],'policyVersion':data['policyVersion'],'globalRevision':data['globalRevision'],'memoryEpoch':expected})
            old=db.execute('SELECT * FROM memory_actions WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if old:
                if old['semantic_hash']!=semantic:self.fail(409,'该请求号已用于其他确认。')
                return {'receipt':{'id':old['id'],'operation':'provider-consent'},'replayed':True}
            action=str(uuid4());nonce=str(uuid4());now=self.clock()
            db.execute("INSERT INTO memory_actions VALUES(?,?,?,'provider-consent',?,?,?,NULL,NULL,?,?,?)",(action,self.owner,key,provider_id,semantic,expected,nonce,dump({'memoryScopeAcknowledged':True,'receiptContainsBody':False}),now))
            db.execute('INSERT INTO memory_provider_consents VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(owner,provider_id) DO UPDATE SET provider_binding=excluded.provider_binding,policy_version=excluded.policy_version,global_revision=excluded.global_revision,memory_epoch=excluded.memory_epoch,nonce=excluded.nonce,updated=excluded.updated',(self.owner,provider_id,auth['providerBinding'],auth['policyVersion'],auth['globalRevision'],expected,nonce,now,now))
            return {'receipt':{'id':action,'operation':'provider-consent'},'replayed':False}
    def provider_revoke(self,provider_id,data):
        exact(data,('requestId',),self.Error);key=request_id(data,self.Error)
        semantic=fingerprint({'operation':'provider-revoke','providerId':provider_id})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');assert_active(db,self.owner,self.Error)
            old=db.execute('SELECT * FROM memory_actions WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
            if old:
                if old['semantic_hash']!=semantic:self.fail(409,'该请求号已用于其他操作。')
                return {'receipt':{'id':old['id'],'operation':'provider-revoke','providerId':provider_id,'memoryGenerationInvalidated':True},'memoryEpoch':epoch(db,self.owner),'replayed':True}
            now=self.clock();action=str(uuid4());nonce=str(uuid4());expected=epoch(db,self.owner)
            db.execute("INSERT INTO memory_actions VALUES(?,?,?,'provider-revoke',?,?,?,NULL,NULL,?,?,?)",(action,self.owner,key,provider_id,semantic,expected,nonce,dump({'memoryScopeRevoked':True,'receiptContainsBody':False}),now))
            new_epoch=bump_epoch(db,self.owner,now)
            db.execute('UPDATE memory_provider_consents SET memory_epoch=-1,global_revision=-1,nonce=?,updated=? WHERE owner=?',(str(uuid4()),now,self.owner))
            cancel_memory_jobs(db,self.owner)
            return {'receipt':{'id':action,'operation':'provider-revoke','providerId':provider_id,'memoryGenerationInvalidated':True},'memoryEpoch':new_epoch,'replayed':False}

SETTINGS_SQL="""SELECT coalesce((SELECT data FROM settings WHERE key='privacy'),'') privacy_config,coalesce((SELECT json_object('providerId',json_extract(data,'$.providerId'),'endpoint',json_extract(data,'$.endpoint'),'model',json_extract(data,'$.model'),'processingRegions',json_extract(data,'$.processingRegions'),'privacyPolicyVersion',json_extract(data,'$.privacyPolicyVersion')) FROM settings WHERE key='ai'),'') legacy_binding,coalesce((SELECT data FROM settings WHERE key='ai_gateway'),'') gateway_config"""
def settings_guard(db):return dict(db.execute(SETTINGS_SQL).fetchone())
def privacy_view(store,owner,Error):
    from privacy import Privacy
    from types import SimpleNamespace
    # Caller supplies its authenticated owner. This carrier is only for frozen disclosure construction.
    return Privacy(store,SimpleNamespace(user={'id':owner}),Error,lambda *a:None).response()
def preference_guard(owner,p,guard):
    sql="""EXISTS(SELECT 1 FROM privacy_preferences WHERE user_id=? AND revision=? AND policy_version=? AND provider_binding=? AND json_extract(data,'$.longTermMemory')=1) AND coalesce((SELECT data FROM settings WHERE key='privacy'),'')=? AND coalesce((SELECT json_object('providerId',json_extract(data,'$.providerId'),'endpoint',json_extract(data,'$.endpoint'),'model',json_extract(data,'$.model'),'processingRegions',json_extract(data,'$.processingRegions'),'privacyPolicyVersion',json_extract(data,'$.privacyPolicyVersion')) FROM settings WHERE key='ai'),'')=? AND coalesce((SELECT data FROM settings WHERE key='ai_gateway'),'')=?"""
    return sql,[owner,p['revision'],p['disclosure']['policyVersion'],p['providerBinding'],guard['privacy_config'],guard['legacy_binding'],guard['gateway_config']]
def _authorization_matches(auth,p,owner,Error):
    if not isinstance(auth,dict) or auth.get('accountId')!=owner or auth.get('policyVersion')!=p['disclosure']['policyVersion'] or auth.get('globalRevision')!=p['revision'] or auth.get('globalBinding')!=p['providerBinding'] or not isinstance(auth.get('providerId'),str) or not auth['providerId'] or not isinstance(auth.get('providerBinding'),str) or not auth['providerBinding']:
        raise Error(403,'本次实际供应商授权快照已失效。')
def selection_value(selection,Error):
    exact(selection,('memoryEpoch','items'),Error);integer(selection.get('memoryEpoch'),Error,'记忆版本')
    items=selection.get('items')
    if not isinstance(items,list) or not 1<=len(items)<=MAX_SELECTION:raise Error(400,'请明确选择1至5条本人记忆。')
    for item in items:
        exact(item,('id','version'),Error)
        if not isinstance(item.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',item['id']):raise Error(400,'记忆编号不正确。')
        integer(item.get('version'),Error,'条目版本',1)
    if len({x['id'] for x in items})!=len(items):raise Error(400,'不能重复选择同一条记忆。')
    return {'memoryEpoch':selection['memoryEpoch'],'items':[{'id':x['id'],'version':x['version']} for x in items]}

def prepare_ai_memory(store,owner,selection,Error,*,authorization,legacy=False):
    if selection is None:return None
    selected=selection_value(selection,Error)
    with store.connect() as db:
        assert_active(db,owner,Error)
        if not db.execute('SELECT 1 FROM users WHERE id=?',(owner,)).fetchone():raise Error(401,'请重新登录。')
        guard=settings_guard(db)
    p=privacy_view(store,owner,Error);require_enabled(p,Error);_authorization_matches(authorization,p,owner,Error)
    auth=authorization;data=[];categories=set();total=0
    with store.connect() as db:
        if selected['memoryEpoch']!=epoch(db,owner):raise Error(409,'记忆已关闭或变更，请重新选择。')
        for item in selected['items']:
            row=db.execute('SELECT * FROM memory_entries WHERE id=? AND owner=?',(item['id'],owner)).fetchone()
            if not row:raise Error(404,'未找到本人选择的记忆。')
            if row['version']!=item['version']:raise Error(409,'所选记忆已有更新，请重新核对。')
            if row['category'] in ('chart','wellbeing') and p['consents'].get(row['category']) is not True:raise Error(403,'此类记忆需要对应资料授权。')
            if row['category'] not in auth.get('authorizedCategories',[]):raise Error(403,'实际供应商未获所选记忆类别授权。')
            total+=len(row['title'])+len(row['text'])
            if total>MAX_SELECTED_CHARS:raise Error(400,'所选记忆超过本次6000字限制。')
            data.append({'category':row['category'],'title':row['title'],'text':row['text']});categories.add(row['category'])
        nonce=''
        if legacy:
            if (p['disclosure'].get('activeAI') or {}).get('providerId')!=auth['providerId'] or auth['providerBinding']!=p['providerBinding']:raise Error(403,'原AI实际接收方已变化。')
        else:
            if auth.get('receiptValid') is not True or not auth.get('providerConsentRevision'):raise Error(403,'请先确认该供应商基础授权。')
            row=db.execute('SELECT * FROM memory_provider_consents WHERE owner=? AND provider_id=?',(owner,auth['providerId'])).fetchone()
            if not row or row['provider_binding']!=auth['providerBinding'] or row['policy_version']!=auth['policyVersion'] or row['global_revision']!=auth['globalRevision'] or row['memory_epoch']!=selected['memoryEpoch'] or not row['nonce']:raise Error(403,'请先单独确认该供应商使用长期记忆。')
            nonce=row['nonce']
        if guard!=settings_guard(db):raise Error(409,'数据处理配置已变化，请重新确认。')
    return {'owner':owner,'memoryEpoch':selected['memoryEpoch'],'selection':selected,'categories':sorted(categories),'data':data,'policyVersion':auth['policyVersion'],'globalRevision':auth['globalRevision'],'globalBinding':auth['globalBinding'],'providerId':auth['providerId'],'providerBinding':auth['providerBinding'],'providerConsentRevision':'' if legacy else auth['providerConsentRevision'],'memoryConsentNonce':nonce,'settingsGuard':guard,'legacy':bool(legacy)}

def check_ai_memory(store,owner,proof,Error,*,authorization):
    if proof is None:return None
    if proof['owner']!=owner:raise Error(403,'记忆所属账号已变化。')
    current=prepare_ai_memory(store,owner,proof['selection'],Error,authorization=authorization,legacy=proof['legacy'])
    if dump(current)!=dump(proof):raise Error(409,'记忆或授权已变化，本次不继续发送或保存。')
    return current

def memory_save_guard(proof):
    if proof is None:return '1',[]
    owner=proof['owner'];p={'revision':proof['globalRevision'],'disclosure':{'policyVersion':proof['policyVersion']},'providerBinding':proof['globalBinding']}
    first,args=preference_guard(owner,p,proof['settingsGuard'])
    clauses=[first,"NOT EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed') AND coalesce((SELECT epoch FROM memory_state WHERE owner=?),0)=?"];args += [owner,owner,proof['memoryEpoch']]
    for item in proof['selection']['items']:
        clauses.append('EXISTS(SELECT 1 FROM memory_entries WHERE owner=? AND id=? AND version=?)');args += [owner,item['id'],item['version']]
    for category in proof['categories']:
        if category in ('chart','wellbeing'):
            clauses.append("EXISTS(SELECT 1 FROM privacy_preferences WHERE user_id=? AND json_extract(data,?)=1)");args += [owner,'$.'+category]
    if not proof['legacy']:
        clauses.append('EXISTS(SELECT 1 FROM memory_provider_consents WHERE owner=? AND provider_id=? AND provider_binding=? AND policy_version=? AND global_revision=? AND memory_epoch=? AND nonce=?)')
        args += [owner,proof['providerId'],proof['providerBinding'],proof['policyVersion'],proof['globalRevision'],proof['memoryEpoch'],proof['memoryConsentNonce']]
        clauses.append('EXISTS(SELECT 1 FROM ai_gateway_provider_consents WHERE owner=? AND provider_id=? AND provider_binding=? AND policy_version=? AND global_revision=? AND revision=?)')
        args += [owner,proof['providerId'],proof['providerBinding'],proof['policyVersion'],proof['globalRevision'],proof['providerConsentRevision']]
    return ' AND '.join('('+x+')' for x in clauses),args

def memory_request_semantic(raw,proof,Error):
    request_hash=fingerprint(raw)
    context=raw.get('context')
    if proof is None:
        context_characters=len(dump(context)) if context is not None else 0
        expanded=request_hash
    else:
        context_characters=len(dump({'context':context,'selectedMemory':proof['data']}))
        if context_characters>MAX_SELECTED_CHARS:raise Error(400,'所选记忆与本次资料合计超过6000字上下文预算。')
        expanded=fingerprint({'request':raw,'selectedMemory':proof['data']})
    return {'requestFingerprint':request_hash,'fingerprint':expanded,'contextCharacters':context_characters,
            'inputCharacters':sum(len(m.get('content','')) for m in raw.get('messages',[]) if isinstance(m,dict) and isinstance(m.get('content'),str))+context_characters}

def memory_job_replay_matches(db,owner,job_row,raw):
    # Metadata-only replay: no memory-entry query, no model call, no quota mutation.
    if job_row['owner']!=owner:return False
    original=fingerprint(raw)
    if raw.get('memorySelection') is None:return job_row['fingerprint']==original
    row=db.execute('SELECT request_fingerprint FROM memory_job_bindings WHERE job_id=? AND owner=?',(job_row['id'],owner)).fetchone()
    return bool(row and row['request_fingerprint']==original)

def memory_replay_state(public_job):
    keys=('id','requestId','environment','status','reservedCredits','chargedCredits','errorCode','createdAt','updatedAt')
    return {**{k:public_job[k] for k in keys if k in public_job},'alreadyProcessed':True,'memoryReplay':True,'bodyReturned':False,'newProviderCall':False}

def capture_memory_job(db,owner,job_id,proof,now,semantic):
    if proof is None:return
    if owner!=proof['owner'] or not isinstance(semantic,dict) or not re.fullmatch(r'[a-f0-9]{64}',str(semantic.get('requestFingerprint',''))):raise ValueError('trusted memory semantic required')
    if type(semantic.get('contextCharacters')) is not int or not 0<=semantic['contextCharacters']<=6000:raise ValueError('invalid memory context budget')
    guard,args=memory_save_guard(proof)
    if not db.execute('SELECT 1 WHERE '+guard,args).fetchone():raise sqlite3.IntegrityError('memory_binding_changed_before_job_capture')
    job=db.execute('SELECT 1 FROM ai_gateway_jobs WHERE id=? AND owner=? AND fingerprint=?',(job_id,owner,semantic['fingerprint'])).fetchone()
    if not job:raise ValueError('memory capture requires actual same-transaction accepted job')
    db.execute('INSERT INTO memory_job_bindings VALUES(?,?,?,?,?,?,?,?,?,?)',(job_id,owner,proof['memoryEpoch'],dump(proof['selection']),proof['policyVersion'],proof['globalRevision'],proof['globalBinding'],now,semantic['requestFingerprint'],semantic['contextCharacters']))

def cancel_memory_jobs(db,owner):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_gateway_jobs'").fetchone():
        db.execute("UPDATE ai_gateway_jobs SET cancel_requested=1 WHERE owner=? AND status IN ('queued','running') AND EXISTS(SELECT 1 FROM memory_job_bindings m WHERE m.job_id=ai_gateway_jobs.id AND m.owner=?)",(owner,owner))

def memory_cleanup_statements(available,owner,operation_id,now,guard='1',bindings=(),*,reason='delete-memory',targets=None):
    if reason not in ('close-account','delete-memory','retention'):raise ValueError('trusted cleanup reason required')
    if not {'memory_entries','memory_state','memory_cleanup_receipts'}<=set(available):raise ValueError('memory schema must be initialized before cleanup')
    if targets is not None:
        if not isinstance(targets,list) or any(not isinstance(x,dict) or set(x)!=set(('id','version')) or not isinstance(x['id'],str) or type(x['version']) is not int or x['version']<1 for x in targets) or len({x['id'] for x in targets})!=len(targets):raise ValueError('invalid trusted memory targets')
    if reason=='retention' and targets is None:raise ValueError('retention requires exact tracked targets')
    match='1' if targets is None else '('+' OR '.join('(id=? AND version=?)' for _ in targets)+')' if targets else '0'
    params=[] if targets is None else [value for x in targets for value in (x['id'],x['version'])]
    where='owner=? AND '+match;wa=[owner,*params]
    receipt=str(uuid4());nonce=str(uuid4())
    details={'reason':reason,'localStatus':'completed','providersStatus':'pending-confirmation','backupsStatus':'pending-confirmation','vectorStoreStatus':'not-implemented','savedConversationsDeleted':False,'genericRecordEpochChanged':False,'cardEpochChanged':False,'receiptContainsBody':False}
    statements=[(f"INSERT OR IGNORE INTO memory_cleanup_receipts SELECT ?,?,?,?,'claimed',json_set(?,'$.counts.memoryEntries',(SELECT count(*) FROM memory_entries WHERE {where})),? WHERE {guard}",[receipt,owner,operation_id,nonce,dump(details),*wa,now,*bindings])]
    g=f"({guard}) AND EXISTS(SELECT 1 FROM memory_cleanup_receipts WHERE id=? AND owner=? AND nonce=? AND status='claimed')";ga=[*bindings,receipt,owner,nonce]
    invalidate=g+(f" AND EXISTS(SELECT 1 FROM memory_cleanup_receipts WHERE id=? AND json_extract(details,'$.counts.memoryEntries')>0)" if reason=='retention' else '')
    ia=[*ga,*([receipt] if reason=='retention' else [])]
    statements += [
      (f'INSERT OR IGNORE INTO memory_tombstones SELECT owner,id,version,?,? FROM memory_entries WHERE {where} AND {g}',[operation_id,now,*wa,*ga]),
      (f'DELETE FROM memory_entries WHERE {where} AND {g}',[*wa,*ga]),
      (f'INSERT INTO memory_state SELECT ?,1,? WHERE {invalidate} ON CONFLICT(owner) DO UPDATE SET epoch=memory_state.epoch+1,updated=excluded.updated',[owner,now,*ia]),
      (f'UPDATE memory_provider_consents SET memory_epoch=-1,global_revision=-1,nonce=?,updated=? WHERE owner=? AND {invalidate}',[str(uuid4()),now,owner,*ia])]
    if 'ai_gateway_jobs' in available:
        statements.append((f"UPDATE ai_gateway_jobs SET cancel_requested=1 WHERE owner=? AND status IN ('queued','running') AND EXISTS(SELECT 1 FROM memory_job_bindings m WHERE m.job_id=ai_gateway_jobs.id AND m.owner=?) AND {invalidate}",[owner,owner,*ia]))
    statements.append((f"UPDATE memory_cleanup_receipts SET status='completed' WHERE id=? AND {g}",[receipt,*ga]))
    return {'statements':statements,'receiptId':receipt,'nonce':nonce,
      'receiptQuery':{'sql':'SELECT id,owner,operation_id,status,details,created FROM memory_cleanup_receipts WHERE owner=? AND operation_id=?','bindings':[owner,operation_id]},
      'receiptJSONSql':{'sql':"(SELECT details FROM memory_cleanup_receipts WHERE owner=? AND operation_id=? AND status='completed')",'bindings':[owner,operation_id]}}

def append_memory_cleanup(db,owner,operation_id,now,*,reason='delete-memory',targets=None):
    if not db.in_transaction:raise ValueError('memory cleanup requires caller transaction')
    old=db.execute('SELECT * FROM memory_cleanup_receipts WHERE owner=? AND operation_id=?',(owner,operation_id)).fetchone()
    if old:return {**json.loads(old['details']),'receiptId':old['id'],'replayed':True}
    available={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    plan=memory_cleanup_statements(available,owner,operation_id,now,reason=reason,targets=targets)
    for sql,args in plan['statements']:db.execute(sql,args)
    row=db.execute(plan['receiptQuery']['sql'],plan['receiptQuery']['bindings']).fetchone()
    return {**json.loads(row['details']),'receiptId':row['id'],'replayed':False}
