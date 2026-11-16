"""Controlled server env references. No plaintext fallback, provider probes or secret-bearing receipts."""
import copy
import hashlib
import hmac
import ipaddress
import json
import os
import re
import sqlite3
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.error import HTTPError
from uuid import uuid4

DDL = r'''
CREATE TABLE IF NOT EXISTS secret_reference_state(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL DEFAULT 0,updated INTEGER NOT NULL);
INSERT OR IGNORE INTO secret_reference_state VALUES(1,0,0);
CREATE TABLE IF NOT EXISTS secret_reference_plans(id TEXT PRIMARY KEY,actor TEXT NOT NULL,request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,expected_revision INTEGER NOT NULL,sources_hash TEXT NOT NULL,targets TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('prepared','blocked','applied')),created INTEGER NOT NULL,applied_action TEXT,UNIQUE(actor,request_id));
CREATE TABLE IF NOT EXISTS secret_reference_actions(id TEXT PRIMARY KEY,actor TEXT NOT NULL,request_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('settings','migration')),plan_id TEXT REFERENCES secret_reference_plans(id),expected_revision INTEGER NOT NULL,fingerprint TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(actor,request_id),UNIQUE(plan_id));
CREATE TRIGGER IF NOT EXISTS secret_reference_action_check BEFORE INSERT ON secret_reference_actions BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.actor AND status='closed') THEN RAISE(ABORT,'secret_reference_closed') END;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.actor AND role='admin') THEN RAISE(ABORT,'secret_reference_admin_required') END;
 SELECT CASE WHEN NEW.expected_revision!=(SELECT revision FROM secret_reference_state WHERE id=1) THEN RAISE(ABORT,'secret_reference_stale') END;
 SELECT CASE WHEN NEW.kind='migration' AND NOT EXISTS(SELECT 1 FROM secret_reference_plans WHERE id=NEW.plan_id AND actor=NEW.actor AND state='prepared' AND expected_revision=NEW.expected_revision) THEN RAISE(ABORT,'secret_reference_plan_changed') END;
END;
CREATE TRIGGER IF NOT EXISTS secret_reference_action_apply AFTER INSERT ON secret_reference_actions BEGIN
 UPDATE secret_reference_state SET revision=revision+1,updated=NEW.created WHERE id=1;
 UPDATE secret_reference_plans SET state='applied',applied_action=NEW.id WHERE id=NEW.plan_id AND NEW.kind='migration';
END;
CREATE TRIGGER IF NOT EXISTS secret_reference_plan_check BEFORE INSERT ON secret_reference_plans BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.actor AND status='closed') THEN RAISE(ABORT,'secret_reference_closed') END;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.actor AND role='admin') THEN RAISE(ABORT,'secret_reference_admin_required') END;
 SELECT CASE WHEN NEW.expected_revision!=(SELECT revision FROM secret_reference_state WHERE id=1) THEN RAISE(ABORT,'secret_reference_stale') END;
END;
CREATE TRIGGER IF NOT EXISTS secret_reference_plan_immutable BEFORE UPDATE ON secret_reference_plans WHEN NEW.id!=OLD.id OR NEW.actor!=OLD.actor OR NEW.request_id!=OLD.request_id OR NEW.fingerprint!=OLD.fingerprint OR NEW.expected_revision!=OLD.expected_revision OR NEW.sources_hash!=OLD.sources_hash OR NEW.targets!=OLD.targets OR NEW.created!=OLD.created OR OLD.state!='prepared' OR NEW.state!='applied' OR NOT EXISTS(SELECT 1 FROM secret_reference_actions WHERE id=NEW.applied_action AND plan_id=OLD.id) BEGIN SELECT RAISE(ABORT,'secret_reference_immutable'); END;
CREATE TRIGGER IF NOT EXISTS secret_reference_plan_no_delete BEFORE DELETE ON secret_reference_plans BEGIN SELECT RAISE(ABORT,'secret_reference_immutable'); END;
CREATE TRIGGER IF NOT EXISTS secret_reference_action_no_update BEFORE UPDATE ON secret_reference_actions BEGIN SELECT RAISE(ABORT,'secret_reference_immutable'); END;
CREATE TRIGGER IF NOT EXISTS secret_reference_action_no_delete BEFORE DELETE ON secret_reference_actions BEGIN SELECT RAISE(ABORT,'secret_reference_immutable'); END;
CREATE TRIGGER IF NOT EXISTS secret_reference_settings_insert AFTER INSERT ON settings WHEN NEW.key IN ('ai','integrations','theme') BEGIN UPDATE secret_reference_state SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS secret_reference_settings_update AFTER UPDATE OF data ON settings WHEN NEW.key IN ('ai','integrations','theme') BEGIN UPDATE secret_reference_state SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER IF NOT EXISTS secret_reference_settings_delete AFTER DELETE ON settings WHEN OLD.key IN ('ai','integrations','theme') BEGIN UPDATE secret_reference_state SET revision=revision+1 WHERE id=1; END;
'''
AI_FIELDS = ('enabled','endpoint','model','prompt','knowledge','providerId','processingRegions','privacyPolicyVersion','apiKeyRef')
def dump(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def now():return time.time_ns()//1_000_000
def init_schema(db):
    for table in ('settings','users','account_lifecycle'):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():raise RuntimeError('Initialize active secret-reference dependency: '+table)
    db.executescript(DDL)
def valid_provider(value):return isinstance(value,str) and value not in ('__proto__','constructor','prototype') and bool(re.fullmatch('[A-Za-z0-9_-]{1,80}',value))
def valid_reference(reference,kind):return isinstance(reference,str) and bool(re.fullmatch(r'EW_'+('AI' if kind=='ai' else 'DEVICE')+r'_[A-Z0-9_]{1,80}',reference))
def env_value(reference,kind,resolver=None):
    if not valid_reference(reference,kind):return ''
    value=(resolver or os.environ.get)(reference)
    return value if isinstance(value,str) and (1 if kind=='ai' else 24)<=len(value)<=500 and bool(re.fullmatch(r'[A-Za-z0-9._~+/-]+=*',value)) else ''
class NoRedirectHandler(HTTPRedirectHandler):
    """Legacy AI only: a disclosed endpoint cannot forward credentials to any redirect."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, 'Legacy AI redirects are disabled.', headers, fp)

def open_legacy_ai(request, timeout=60):
    # Per-call opener; never modifies urllib's global opener or media requests.
    return build_opener(NoRedirectHandler()).open(request, timeout=timeout)

def credential_status(config,kind,resolver=None):
    plain=config.get('apiKey' if kind=='ai' else 'secret');ref=config.get('apiKeyRef' if kind=='ai' else 'secretRef','')
    return {'hasCredential':bool(plain or ref),'refReady':bool(env_value(ref,kind,resolver)),'unmigrated':bool(plain)}
def resolve_credential(config,kind,Error,resolver=None):
    if config.get('apiKey' if kind=='ai' else 'secret'):raise Error(503,'凭据仍需迁移到服务端引用，已阻止使用旧明文。')
    value=env_value(config.get('apiKeyRef' if kind=='ai' else 'secretRef'),kind,resolver)
    if not value:raise Error(503,'服务端凭据引用尚未就绪。')
    return value
def safe_ai(config,resolver=None):return {**{k:copy.deepcopy(config[k]) for k in AI_FIELDS if k in config},**credential_status(config,'ai',resolver)}
def safe_device(config,resolver=None):return {'secretRef':config.get('secretRef',''),'fieldMap':copy.deepcopy(config.get('fieldMap',{})),**credential_status(config,'device',resolver)}
def ai_ready(config,resolver=None):return bool(config.get('enabled') and config.get('model') and not credential_status(config,'ai',resolver)['unmigrated'] and credential_status(config,'ai',resolver)['refReady'])

class SecretReferences:
    def __init__(self,store,handler,error,limiter,*,resolver=None):self.store,self.h,self.Error,self.rate,self.resolver=store,handler,error,limiter,resolver
    def fail(self,status,message):raise self.Error(status,message)
    @property
    def actor(self):return self.h.user['id']
    def active(self,db):
        if db.execute("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'",(self.actor,)).fetchone():self.fail(401,'账号已关闭，请重新登录。')
        if not db.execute("SELECT 1 FROM users u WHERE id=? AND role='admin' AND NOT EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=u.id AND status='closed')",(self.actor,)).fetchone():self.fail(403,'管理员账号或权限已失效。')
    def integer(self,v):
        if type(v) is not int or not 0<=v<=2_147_483_646:self.fail(400,'需要明确的配置版本。')
        return v
    def text(self,v,maximum=128,minimum=1):
        if not isinstance(v,str) or not minimum<=len(v.strip())<=maximum or any(0xD800<=ord(c)<=0xDFFF for c in v):self.fail(400,'文本字段不符合要求。')
        return v.strip()
    def request(self,data,fields):
        if not isinstance(data,dict) or set(data)-set(fields):self.fail(400,'请求字段不符合要求；不能提交凭据原值。')
        return self.text(data.get('requestId')),self.integer(data.get('expectedRevision'))
    def snapshot(self,db):
        raw={k:(db.execute('SELECT data FROM settings WHERE key=?',(k,)).fetchone() or {'data':'{}'})['data'] for k in ('ai','integrations')}
        try:parsed={k:json.loads(v) for k,v in raw.items()}
        except Exception:self.fail(409,'原配置格式异常，尚未修改。')
        if any(not isinstance(v,dict) for v in parsed.values()):self.fail(409,'原配置格式异常，尚未修改。')
        return raw,parsed
    def revision(self,db):return db.execute('SELECT revision FROM secret_reference_state WHERE id=1').fetchone()[0]
    def inventory(self,db):
        self.active(db);_,s=self.snapshot(db)
        return {'revision':self.revision(db),'items':[{'kind':'ai','providerId':'','reference':s['ai'].get('apiKeyRef',''),**credential_status(s['ai'],'ai',self.resolver)}]+[{'kind':'device','providerId':k,'reference':v.get('secretRef',''),**credential_status(v,'device',self.resolver)} for k,v in sorted(s['integrations'].items()) if isinstance(v,dict)],'managedCloudVerified':False,'providerRequestsMade':False,'automaticMigration':False}
    def plan_item(self,row):
        return {'id':row['id'],'expectedRevision':row['expected_revision'],'status':row['state'],'targets':json.loads(row['targets']),'appliedActionId':row['applied_action'],'createdAt':row['created'],'dryRun':row['state']!='applied'}
    def mapping(self,data,parsed):
        if not isinstance(data,list) or not 1<=len(data)<=50:self.fail(400,'请选择明确的迁移目标。')
        rows=[];seen=set()
        for x in data:
            if not isinstance(x,dict) or set(x)!={'kind','providerId','reference'} or x['kind'] not in ('ai','device'):self.fail(400,'迁移目标字段无效。')
            kind=x['kind'];provider=self.text(x['providerId'],80,0)
            if (kind=='ai' and provider) or (kind=='device' and not valid_provider(provider)):self.fail(400,'设备供应商编号无效。')
            reference=x['reference']
            if not valid_reference(reference,kind):self.fail(400,'仅允许用途对应的EW_AI_或EW_DEVICE_环境引用。')
            ident=kind+':'+provider
            if ident in seen:self.fail(400,'同一凭据不能重复迁移。')
            seen.add(ident);cfg=parsed['ai'] if kind=='ai' else parsed['integrations'].get(provider,{})
            if not isinstance(cfg,dict):self.fail(409,'原设备配置格式异常。')
            plain=cfg.get('apiKey' if kind=='ai' else 'secret');value=env_value(reference,kind,self.resolver)
            match=isinstance(plain,str) and bool(plain) and bool(value) and hmac.compare_digest(plain.encode(),value.encode())
            rows.append({'kind':kind,'providerId':provider,'reference':reference,'hasCredential':bool(plain),'unmigrated':bool(plain),'refReady':match})
        return sorted(rows,key=lambda x:(x['kind'],x['providerId']))
    def create_plan(self,data):
        request,version=self.request(data,('requestId','expectedRevision','mappings'));token=digest(dump({'revision':version,'mappings':data.get('mappings')}))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.active(db)
            old=db.execute('SELECT * FROM secret_reference_plans WHERE actor=? AND request_id=?',(self.actor,request)).fetchone()
            if old:
                if old['fingerprint']!=token:self.fail(409,'该编号已用于其他迁移计划。')
                return {'item':self.plan_item(old),'replayed':True}
            if self.revision(db)!=version:self.fail(409,'配置版本已变化，请重新预览。')
            raw,parsed=self.snapshot(db);targets=self.mapping(data.get('mappings'),parsed);ident=str(uuid4())
            db.execute('INSERT INTO secret_reference_plans VALUES(?,?,?,?,?,?,?,?,?,NULL)',(ident,self.actor,request,token,version,dump({k:digest(v) for k,v in raw.items()}),dump(targets),'prepared' if all(x['refReady'] for x in targets) else 'blocked',now()))
            self.store.audit(db,self.actor,'secret-reference.preview',ident,'仅元数据迁移计划；不记录凭据、原文或原哈希')
            return {'item':self.plan_item(db.execute('SELECT * FROM secret_reference_plans WHERE id=?',(ident,)).fetchone()),'replayed':False}
    def apply_plan(self,ident,data):
        request,version=self.request(data,('requestId','expectedRevision','confirmed'))
        if data.get('confirmed') is not True:self.fail(400,'需明确确认执行此迁移计划。')
        token=digest(dump({'planId':ident,'revision':version,'confirmed':True}))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.active(db)
            old=db.execute('SELECT * FROM secret_reference_actions WHERE actor=? AND request_id=?',(self.actor,request)).fetchone()
            if old:
                if old['kind']!='migration' or old['fingerprint']!=token:self.fail(409,'该编号已用于其他配置操作。')
                return {'actionId':old['id'],'revision':self.revision(db),'replayed':True,'status':self.inventory(db)}
            row=db.execute('SELECT * FROM secret_reference_plans WHERE id=? AND actor=?',(ident,self.actor)).fetchone()
            if not row:self.fail(404,'迁移计划不存在或不属于当前管理员。')
            if row['state']!='prepared' or row['expected_revision']!=version or self.revision(db)!=version:self.fail(409,'计划或配置已变化。')
            raw,parsed=self.snapshot(db)
            if dump({k:digest(v) for k,v in raw.items()})!=row['sources_hash']:self.fail(409,'原配置已变化，请重新创建迁移计划。')
            targets=self.mapping([{k:x[k] for k in ('kind','providerId','reference')} for x in json.loads(row['targets'])],parsed)
            if not all(x['refReady'] for x in targets):self.fail(409,'服务端引用尚未与旧配置一致，整批未修改。')
            action=str(uuid4());db.execute('INSERT INTO secret_reference_actions VALUES(?,?,?,?,?,?,?,?)',(action,self.actor,request,'migration',ident,version,token,now()))
            for x in targets:
                if x['kind']=='ai':db.execute("UPDATE settings SET data=json_set(json_remove(data,'$.apiKey'),'$.apiKeyRef',?) WHERE key='ai'",(x['reference'],))
                else:
                    base='$.'+json.dumps(x['providerId'],ensure_ascii=False)
                    db.execute("UPDATE settings SET data=json_set(json_remove(data,?),?,?) WHERE key='integrations'",(base+'.secret',base+'.secretRef',x['reference']))
            self.store.audit(db,self.actor,'secret-reference.migrate',ident,'仅迁移已逐项匹配的服务端引用；无供应商请求、轮换或云KMS验证')
            return {'actionId':action,'revision':self.revision(db),'replayed':False,'status':self.inventory(db)}
    def updated_ai(self,old,changes):
        if not isinstance(changes,dict) or set(changes)-set(AI_FIELDS):self.fail(400,'AI配置仅接受元数据与apiKeyRef，不接收凭据原值。')
        if old.get('apiKey'):self.fail(409,'旧AI凭据须先通过明确迁移计划处理，未修改配置。')
        result={k:copy.deepcopy(v) for k,v in old.items() if k in AI_FIELDS};result.update(changes)
        if type(result.get('enabled',False)) is not bool:self.fail(400,'AI开关必须是布尔值。')
        endpoint=self.text(result.get('endpoint'),500)
        try:
            u=urlsplit(endpoint);host=u.hostname or '';port=u.port
            if any(c.isspace() for c in endpoint) or (port is not None and not 1<=port<=65535):raise ValueError()
            if u.scheme!='https' or not host or u.username or u.password or u.query or u.fragment or not u.path.endswith('/responses') or host=='localhost' or host.endswith(('.local','.internal')):raise ValueError()
            try:address=ipaddress.ip_address(host)
            except ValueError:address=None
            if address is not None and not address.is_global:raise ValueError()
        except Exception:self.fail(400,'AI地址须为公开HTTPS Responses端点。')
        result['endpoint']=endpoint
        for k,limit in [('model',120),('prompt',8000),('knowledge',20000),('providerId',80),('privacyPolicyVersion',80)]:result[k]=self.text(result.get(k,''),limit,0)
        if result['providerId'] and not re.fullmatch('[A-Za-z0-9_-]{1,80}',result['providerId']):self.fail(400,'供应商编号无效。')
        regions=result.get('processingRegions',[])
        if not isinstance(regions,list) or len(regions)>12 or any(not isinstance(x,str) or not 1<=len(x.strip())<=80 for x in regions):self.fail(400,'实际处理地区无效。')
        result['processingRegions']=[x.strip() for x in regions];ref=self.text(result.get('apiKeyRef',''),90,0)
        if ref and not valid_reference(ref,'ai'):self.fail(400,'AI仅允许EW_AI_服务端环境引用。')
        result['apiKeyRef']=ref;return result
    def updated_devices(self,old,changes):
        if not isinstance(changes,dict) or len(changes)>100:self.fail(400,'设备配置格式无效。')
        for key,v in changes.items():
            if not valid_provider(key) or not isinstance(v,dict) or set(v)-{'secretRef','fieldMap'}:self.fail(400,'设备仅接受secretRef与字段映射，不接收凭据原值。')
        if any(not isinstance(v,dict) for v in old.values()):self.fail(409,'原设备配置格式异常，尚未修改。')
        if any(v.get('secret') for v in old.values()):self.fail(409,'设备组仍含未迁移旧凭据；须先明确迁移该组全部遗留凭据，旧值仍保留，设备配置未修改。')
        result=copy.deepcopy(old)
        for key,v in changes.items():
            dest=result.get(key,{})
            if not isinstance(dest,dict):self.fail(409,'原设备配置格式异常。')
            if dest.get('secret'):self.fail(409,'该设备旧凭据须先通过明确迁移计划处理。')
            ref=self.text(v.get('secretRef',dest.get('secretRef','')),90,0)
            if ref and not valid_reference(ref,'device'):self.fail(400,'设备仅允许EW_DEVICE_服务端环境引用。')
            fields=v.get('fieldMap',dest.get('fieldMap',{}))
            if not isinstance(fields,dict) or len(fields)>100 or any(not isinstance(a,str) or not isinstance(b,str) or not 1<=len(a)<=60 or not 1<=len(b)<=60 for a,b in fields.items()):self.fail(400,'设备字段映射无效。')
            result[key]={'secretRef':ref,'fieldMap':copy.deepcopy(fields)}
        return result
    def settings(self,method,data=None):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE' if method in ('POST','PATCH') else 'BEGIN');self.active(db);raw,values=self.snapshot(db)
            if method=='GET':
                row=db.execute("SELECT data FROM settings WHERE key='theme'").fetchone()
                return {'ai':safe_ai(values['ai'],self.resolver),'integrations':{k:safe_device(v,self.resolver) for k,v in values['integrations'].items() if isinstance(v,dict)},'theme':json.loads(row[0]) if row else {},'secretConfigRevision':self.revision(db)}
            if method not in ('POST','PATCH'):self.fail(405,'不支持此配置方法。')
            request,version=self.request(data,('requestId','expectedRevision','ai','integrations','theme'))
            # Validate every payload before writes, including rejected credentials, then record only its digest.
            updates={}
            if 'ai' in data:updates['ai']=self.updated_ai(values['ai'],data['ai'])
            if 'integrations' in data:updates['integrations']=self.updated_devices(values['integrations'],data['integrations'])
            if 'theme' in data:
                theme=data['theme']
                if not isinstance(theme,dict) or any(k not in ('--bg','--ink','--cta') or not isinstance(v,str) or not re.fullmatch('#[a-fA-F0-9]{6}',v) for k,v in theme.items()):self.fail(400,'主题只支持合法六位颜色。')
                updates['theme']=theme
            if not updates:self.fail(400,'没有明确配置变更。')
            token=digest(dump({'revision':version,'changes':data}));old=db.execute('SELECT * FROM secret_reference_actions WHERE actor=? AND request_id=?',(self.actor,request)).fetchone()
            if old:
                if old['kind']!='settings' or old['fingerprint']!=token:self.fail(409,'该编号已用于其他配置操作。')
                return {'ok':True,'actionId':old['id'],'revision':self.revision(db),'replayed':True}
            action=str(uuid4());db.execute('INSERT INTO secret_reference_actions VALUES(?,?,?,?,?,?,?,?)',(action,self.actor,request,'settings',None,version,token,now()))
            for k,v in updates.items():db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data',(k,dump(v)))
            self.store.audit(db,self.actor,'settings.update','system','仅元数据与服务端引用；不记录凭据或配置正文')
            return {'ok':True,'actionId':action,'revision':self.revision(db),'replayed':False}
    def route(self,method,path):
        if not (path=='/api/admin/settings' or path=='/api/admin/secret-references' or path.startswith('/api/admin/secret-references/')):return None
        self.h.require(['admin']);self.rate('secret-reference:'+('read:' if method=='GET' else 'write:')+self.actor,180 if method=='GET' else 30)
        try:
            if path=='/api/admin/settings':return self.settings(method,None if method=='GET' else self.h.body())
            if path=='/api/admin/secret-references' and method=='GET':
                with self.store.connect() as db:db.execute('BEGIN');return self.inventory(db)
            if path=='/api/admin/secret-references/plans' and method=='POST':return self.create_plan(self.h.body())
            match=re.fullmatch('/api/admin/secret-references/plans/([^/]+)(/apply)?',path)
            if match:
                if method=='POST' and match[2]:return self.apply_plan(match[1],self.h.body())
                if method=='GET' and not match[2]:
                    with self.store.connect() as db:
                        self.active(db);row=db.execute('SELECT * FROM secret_reference_plans WHERE id=? AND actor=?',(match[1],self.actor)).fetchone()
                        if not row:self.fail(404,'迁移计划不存在或不属于当前管理员。')
                        return {'item':self.plan_item(row)}
            self.fail(405,'不支持此凭据配置操作。')
        except sqlite3.IntegrityError as e:
            if 'secret_reference_closed' in str(e):self.fail(401,'账号已关闭，请重新登录。')
            if 'secret_reference_admin_required' in str(e):self.fail(403,'管理员账号或权限已失效。')
            if 'secret_reference_' in str(e) or 'UNIQUE' in str(e):self.fail(409,'配置或操作编号已变化，请重新读取。')
            raise
