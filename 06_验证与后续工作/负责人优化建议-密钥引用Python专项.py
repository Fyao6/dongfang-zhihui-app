"""Synthetic canary env only. Fresh owned SQLite; no production DB/env enumeration/provider calls."""
from pathlib import Path
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import hashlib
import json
import sqlite3
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'04_研发源码/app/r4/backend/secret_references.py'
spec=importlib.util.spec_from_file_location('owned_secret_reference_contract',SOURCE);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
RUN=str(uuid4());CANARIES=[];databases=[];checks=[]
class Error(Exception):
    def __init__(self,status,message):super().__init__(message);self.status,self.message=status,message
class Store:
    def __init__(self,path):self.path=path
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row;db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:yield db
        finally:db.close()
    def audit(self,db,actor,action,target,detail):db.execute('INSERT INTO audits VALUES(?,?,?,?,?,?)',(str(uuid4()),actor,action,target,detail,M.now()))
class Handler:
    def __init__(self,actor,body):self.user={'id':actor,'role':'admin' if actor in ('admin','admin2') else 'operator' if actor=='operator' else 'user'} if actor else None;self.data=body
    def require(self,roles=None):
        if not self.user:raise Error(401,'sign in')
        if roles and self.user['role'] not in roles:raise Error(403,'role')
        return self.user
    def body(self):return self.data
class Fixture:
    def __init__(self,legacy=True):
        self.path=ROOT/'06_验证与后续工作'/('密钥引用隔离-'+RUN+'-'+str(len(databases))+'.sqlite3');assert not self.path.exists();databases.append(str(self.path.relative_to(ROOT)))
        self.store=Store(self.path);self.ai='synthetic-ai-'+str(uuid4());self.device='synthetic-device-'+str(uuid4());CANARIES.extend([self.ai,self.device]);self.env={'EW_AI_LEGACY_TEST':self.ai,'EW_DEVICE_SENSOR_TEST':self.device}
        self.ai_cfg={'enabled':True,'endpoint':'https://fixture.invalid/v1/responses','model':'synthetic','providerId':'synthetic','processingRegions':['synthetic-region'],'privacyPolicyVersion':'synthetic-policy','prompt':'safe','knowledge':'safe',**({'apiKey':self.ai} if legacy else {'apiKeyRef':'EW_AI_LEGACY_TEST'})}
        with self.store.connect() as db:
            db.executescript("CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT);CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT);CREATE TABLE account_lifecycle(owner TEXT PRIMARY KEY,status TEXT,epoch INTEGER,closed_at INTEGER,receipt_id TEXT);CREATE TABLE audits(id TEXT PRIMARY KEY,actor TEXT,action TEXT,target TEXT,detail TEXT,created INTEGER);")
            for ident,role in [('admin','admin'),('admin2','admin'),('buyer','user'),('operator','operator')]:db.execute('INSERT INTO users VALUES(?,?)',(ident,role))
            for k,v in [('ai',self.ai_cfg),('integrations',{'sensor-a':{'fieldMap':{'heart':'heartRate'},**({'secret':self.device} if legacy else {'secretRef':'EW_DEVICE_SENSOR_TEST'})}}),('theme',{})]:db.execute('INSERT INTO settings VALUES(?,?)',(k,M.dump(v)))
            M.init_schema(db)
        self.responses=[]
    def scalar(self,sql,*args):
        with self.store.connect() as db:return db.execute(sql,args).fetchone()[0]
    def config(self,key):return json.loads(self.scalar('SELECT data FROM settings WHERE key=?',key))
    def version(self):return self.scalar('SELECT revision FROM secret_reference_state WHERE id=1')
    def api(self,path,body=None,actor='admin',method=None,status=200):
        h=Handler(actor,body);service=M.SecretReferences(self.store,h,Error,lambda *args:None,resolver=self.env.get)
        try:value=service.route(method or ('POST' if body is not None else 'GET'),path);actual=200
        except Error as e:actual=e.status;value={'error':e.message}
        self.responses.append(value);assert actual==status,(path,status,actual)
        serialized=json.dumps(value,ensure_ascii=False)
        assert not any(c in serialized for c in CANARIES),'Secret canary reached API output'
        return value
    def inventory(self):return self.api('/api/admin/secret-references')
    def plan(self,request=None,mappings=None):return self.api('/api/admin/secret-references/plans',{'requestId':request or str(uuid4()),'expectedRevision':self.version(),'mappings':mappings or [{'kind':'ai','providerId':'','reference':'EW_AI_LEGACY_TEST'},{'kind':'device','providerId':'sensor-a','reference':'EW_DEVICE_SENSOR_TEST'}]})['item']
    def apply(self,p,request=None,status=200):return self.api('/api/admin/secret-references/plans/'+p['id']+'/apply',{'requestId':request or str(uuid4()),'expectedRevision':p['expectedRevision'],'confirmed':True},status=status)
    def settings(self,d,status=200,request=None,version=None):return self.api('/api/admin/settings',{'requestId':request or str(uuid4()),'expectedRevision':self.version() if version is None else version,**d},status=status)
    def facts(self):
        with self.store.connect() as db:return M.dump({t:[tuple(x) for x in db.execute('SELECT * FROM '+t+' ORDER BY 1')] for t in ['settings','secret_reference_state','secret_reference_plans','secret_reference_actions','audits']})
    def no_canary_metadata(self):
        with self.store.connect() as db:
            for t in ['secret_reference_state','secret_reference_plans','secret_reference_actions','audits']:
                text=M.dump([tuple(x) for x in db.execute('SELECT * FROM '+t)])
                assert not any(c in text for c in CANARIES),'Secret body in metadata/audit'
def check(name,fn):
    try:fn();checks.append({'name':name,'pass':True});print('PASS '+name,flush=True)
    except Exception as e:
        message=repr(e)
        for canary in CANARIES:message=message.replace(canary,'[CANARY REDACTED]')
        checks.append({'name':name,'pass':False,'error':message[:1000]});print('FAIL '+name,flush=True)

def inventory_safe():
    f=Fixture();d=f.inventory();assert len(d['items'])==2 and all(x['unmigrated'] and not x['refReady'] for x in d['items']);a=f.api('/api/admin/settings');assert 'apiKey' not in a['ai'] and 'secret' not in a['integrations']['sensor-a'];assert not d['managedCloudVerified'];f.no_canary_metadata()
check('inventory/settings redact legacy values; only three credential booleans and reference metadata',inventory_safe)
def no_fallback():
    f=Fixture();
    for kind,cfg in [('ai',f.ai_cfg),('device',f.config('integrations')['sensor-a'])]:
        try:M.resolve_credential(cfg,kind,Error,f.env.get);raise AssertionError('plain fallback')
        except Error as e:assert e.status==503
    assert not M.ai_ready(f.ai_cfg,f.env.get)
check('legacy plaintext never silently calls a provider or authenticates a device',no_fallback)
def reference_scope():
    f=Fixture(False)
    for ref,kind in [('PATH','ai'),('HOME','device'),('EW_DEVICE_SENSOR_TEST','ai'),('EW_AI_LEGACY_TEST','device'),('EW_AI_x','ai'),('EW_AI_','ai')]:assert not M.env_value(ref,kind,f.env.get)
    assert M.resolve_credential(f.ai_cfg,'ai',Error,f.env.get)==f.ai
    assert M.resolve_credential(f.config('integrations')['sensor-a'],'device',Error,f.env.get)==f.device
check('controlled purpose prefixes never expose arbitrary OS variables or cross-purpose references',reference_scope)
def deny_new_plain():
    for legacy in (False,True):
        f=Fixture(legacy);before=f.facts()
        for d in [{'ai':{'apiKey':f.ai}},{'ai':{'apiKey':''}},{'ai':{'clearApiKey':True}},{'integrations':{'sensor-a':{'secret':f.device}}},{'integrations':{'sensor-a':{'clearSecret':False}}}]:f.settings(d,400)
        assert f.facts()==before
check('new plaintext/old clear fields rejected even empty; every failed batch is unchanged',deny_new_plain)
def direct_config_refs():
    f=Fixture(False);r=f.settings({'ai':{'apiKeyRef':'EW_AI_LEGACY_TEST'},'integrations':{'sensor-a':{'secretRef':'EW_DEVICE_SENSOR_TEST','fieldMap':{'x':'y'}}}});assert r['revision']>0;assert 'apiKey' not in f.config('ai');assert 'secret' not in f.config('integrations')['sensor-a'];assert M.ai_ready(f.config('ai'),f.env.get);f.no_canary_metadata()
check('reference-only config persists no new secret bodies and actual resolver readiness is truthful',direct_config_refs)
def complete_migration():
    f=Fixture();before={k:f.config(k) for k in ['ai','integrations']};p=f.plan();assert p['status']=='prepared' and f.config('ai')==before['ai'];result=f.apply(p);assert not result['replayed'];assert f.config('ai')['apiKeyRef']=='EW_AI_LEGACY_TEST' and 'apiKey' not in f.config('ai');assert 'secret' not in f.config('integrations')['sensor-a'];assert f.config('integrations')['sensor-a']['secretRef']=='EW_DEVICE_SENSOR_TEST';assert M.resolve_credential(f.config('ai'),'ai',Error,f.env.get)==f.ai;f.no_canary_metadata()
check('preview never changes settings; explicit matching migration removes old values and retains callable refs',complete_migration)
def mismatch_blocks():
    f=Fixture();f.env['EW_DEVICE_SENSOR_TEST']='mismatch-device-'+str(uuid4());p=f.plan();assert p['status']=='blocked';before=f.facts();f.apply(p,status=409);assert f.facts()==before and 'apiKey' in f.config('ai') and 'secret' in f.config('integrations')['sensor-a']
check('one mismatching env target blocks entire migration without partial removal',mismatch_blocks)
def changed_env():
    f=Fixture();p=f.plan();f.env['EW_AI_LEGACY_TEST']='different';before=f.facts();f.apply(p,status=409);assert f.facts()==before
check('env is re-resolved at actual apply, not trusted from preview readiness',changed_env)
def config_drift():
    f=Fixture();p=f.plan()
    with f.store.connect() as db:db.execute("UPDATE settings SET data=json_set(data,'$.model','changed') WHERE key='ai'")
    assert f.version()!=p['expectedRevision'];before=f.facts();f.apply(p,status=409);assert f.facts()==before
check('any direct settings mutation bumps opaque revision; stale plan cannot remove credentials',config_drift)
def rawhash_guard():
    f=Fixture();p=f.plan()
    with f.store.connect() as db:
        db.execute("UPDATE settings SET data=json_set(data,'$.model','changed') WHERE key='ai'")
        db.execute('UPDATE secret_reference_state SET revision=? WHERE id=1',(p['expectedRevision'],))
    before=f.facts();f.apply(p,status=409);assert f.facts()==before
check('internal original-config hash independently detects drift even if revision was reset in fixture',rawhash_guard)
def owner_roles():
    f=Fixture()
    for actor,status in [(None,401),('buyer',403),('operator',403)]:f.api('/api/admin/secret-references',actor=actor,status=status)
    p=f.plan();f.api('/api/admin/secret-references/plans/'+p['id'],actor='admin2',status=404)
check('anonymous/ordinary/operator denied; another admin cannot fetch or apply private plan',owner_roles)
def closed_actor():
    f=Fixture();p=f.plan()
    with f.store.connect() as db:db.execute("INSERT INTO account_lifecycle VALUES('admin','closed',1,1,'fixture')")
    before=f.facts();f.apply(p,status=401);assert f.facts()==before
check('closed administrator cannot execute retained preview plan',closed_actor)
def stale_role():
    f=Fixture();p=f.plan()
    with f.store.connect() as db:db.execute("UPDATE users SET role='operator' WHERE id='admin'")
    before=f.facts();f.apply(p,status=403);assert f.facts()==before
check('fresh transaction role rejects stale admin handler before deletion',stale_role)
def replay_plan():
    f=Fixture();key=str(uuid4());p=f.plan(key);again=f.plan(key);assert p['id']==again['id'];d={'requestId':key,'expectedRevision':f.version(),'mappings':[{'kind':'ai','providerId':'','reference':'EW_AI_OTHER'}]};f.api('/api/admin/secret-references/plans',d,status=409)
check('plan same-key replay is exact; changed mapping conflicts',replay_plan)
def replay_apply():
    f=Fixture();p=f.plan();key=str(uuid4());a=f.apply(p,key);before=f.facts();b=f.apply(p,key);assert b['replayed'] and a['actionId']==b['actionId'];assert f.facts()==before;f.apply(p,status=409)
check('migration replay never re-removes or mutates settings/audit; new apply key cannot reuse applied plan',replay_apply)
def concurrent_apply():
    f=Fixture();p=f.plan();key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(lambda _:f.apply(p,key),range(2)))
    assert out[0]['actionId']==out[1]['actionId'] and f.scalar('SELECT count(*) FROM secret_reference_actions')==1
check('independent SQLite concurrent same-key migration commits once with one replay',concurrent_apply)
def malformed_input():
    f=Fixture()
    for version in [True,'0',0.1,-1,2147483647]:f.api('/api/admin/secret-references/plans',{'requestId':str(uuid4()),'expectedRevision':version,'mappings':[]},status=400)
    for ref in ['HOME','EW_DEVICE_BAD','EW_AI_abc','EW_AI_'+'A'*81]:
        f.api('/api/admin/secret-references/plans',{'requestId':str(uuid4()),'expectedRevision':f.version(),'mappings':[{'kind':'ai','providerId':'','reference':ref}]},status=400)
check('strict request versions and controlled references reject type/length/scope tricks',malformed_input)
def legacy_edit_blocked():
    f=Fixture();before=f.facts();f.settings({'ai':{'model':'change'}},409);f.settings({'integrations':{'sensor-a':{'fieldMap':{}}}},409);assert f.facts()==before
    f.settings({'theme':{'--bg':'#123456'}});assert 'apiKey' in f.config('ai') and 'secret' in f.config('integrations')['sensor-a']
check('unmigrated target edits cannot copy/rewrite plaintext; unrelated explicit theme remains usable',legacy_edit_blocked)
def settings_replay():
    f=Fixture(False);v=f.version();key=str(uuid4());a=f.settings({'ai':{'model':'synthetic2'}},request=key,version=v);before=f.facts();b=f.settings({'ai':{'model':'synthetic2'}},request=key,version=v);assert a['actionId']==b['actionId'] and b['replayed'];assert f.facts()==before;f.settings({'ai':{'model':'other'}},409,request=key,version=v)
check('reference-only settings maintain exact action idempotence and configuration versions',settings_replay)
def blank_reference():
    f=Fixture(False);f.settings({'ai':{'apiKeyRef':''}});assert not M.ai_ready(f.config('ai'),f.env.get)
    try:M.resolve_credential(f.config('ai'),'ai',Error,f.env.get);raise AssertionError('missing ref accepted')
    except Error as e:assert e.status==503
check('explicit clear of a migrated reference disables readiness without falling back',blank_reference)
def unsafe_endpoint():
    f=Fixture(False)
    for url in ['http://fixture.invalid/v1/responses','https://127.0.0.1/v1/responses','https://[::1]/v1/responses','https://[fc00::1]/v1/responses','https://x.internal/v1/responses','https://u:p@fixture.invalid/v1/responses','https://fixture.invalid/v1/responses?key=synthetic','https://fixture.invalid:abc/v1/responses','https://fixture.invalid:65536/v1/responses','https://fixture.invalid:0/v1/responses','https://fixture.invalid:12.3/v1/responses','https://fixture.invalid/ v1/responses','https://fixt\ture.invalid/v1/responses']:
        f.settings({'ai':{'endpoint':url}},400)
check('legacy metadata validation retains public HTTPS/no embedded credentials/private IP rejection',unsafe_endpoint)
def no_secret_snapshot():
    f=Fixture();p=f.plan();f.apply(p);f.no_canary_metadata();whole=f.facts();assert not any(c in whole for c in CANARIES);assert 'sources_hash' not in json.dumps(f.inventory());assert 'fingerprint' not in json.dumps(f.api('/api/admin/secret-references/plans/'+p['id']))
check('after migration all owned DB rows and API/audit receipts contain zero secret canary values or public raw hashes',no_secret_snapshot)

def provider_structure():
    f=Fixture(False);before=f.facts()
    for bad in ['__proto__','prototype','constructor']:f.settings({'integrations':{bad:{'secretRef':'EW_DEVICE_SENSOR_TEST','fieldMap':{}}}},400)
    assert f.facts()==before
    with f.store.connect() as db:db.execute("UPDATE settings SET data=json_set(data,'$.broken',json('[]')) WHERE key='integrations'")
    before=f.facts();f.settings({'integrations':{'broken':{'secretRef':'EW_DEVICE_SENSOR_TEST','fieldMap':{}}}},409)
    f.api('/api/admin/secret-references/plans',{'requestId':str(uuid4()),'expectedRevision':f.version(),'mappings':[{'kind':'device','providerId':'broken','reference':'EW_DEVICE_SENSOR_TEST'}]},status=409)
    assert f.facts()==before
check('reserved object keys and malformed existing device structures cannot become implicit credential targets',provider_structure)

def invalid_env_values():
    f=Fixture(False)
    for kind,ref in [('ai','EW_AI_LEGACY_TEST'),('device','EW_DEVICE_SENSOR_TEST')]:
        for value in ['', ' '*30, '\t'*30, 'synthetic-token'+'\x7f', 'synthetic-token'+'\x01', 'synthetic-token'+'\n', 'synthetic-token'+'\r', 'synthetic-'+('密'*30), 'synthetic-token:opaque-punctuation', 'x'*501]:
            env={ref:value};assert M.env_value(ref,kind,env.get)==''
            cfg={'apiKeyRef' if kind=='ai' else 'secretRef':ref,'enabled':True,'model':'synthetic'}
            assert not M.credential_status(cfg,kind,env.get)['refReady']
        valid='Synthetic-token_opaque-unchanged.123456789~+/=='
        assert M.env_value(ref,kind,{ref:valid}.get)==valid
        assert M.env_value(ref+'\n',kind,{ref+'\n':valid}.get)==''
check('actual Bearer use rejects whitespace/control/invalid header tokens without trimming; valid exact token preserved',invalid_env_values)

def device_group_guard():
    f=Fixture();config=f.config('integrations');config['migrated-b']={'secretRef':'EW_DEVICE_SENSOR_TEST','fieldMap':{}}
    with f.store.connect() as db:db.execute("UPDATE settings SET data=? WHERE key='integrations'",(M.dump(config),))
    before=f.facts();f.settings({'integrations':{'migrated-b':{'fieldMap':{'new':'field'}}}},409);assert f.facts()==before
    f.settings({'theme':{'--cta':'#123456'}});assert f.config('integrations')==config
check('normal edit of migrated device B cannot rewrite unmigrated device A; independent theme remains usable',device_group_guard)

def partial_device_migration():
    f=Fixture();other='synthetic-second-device-'+str(uuid4());CANARIES.append(other);f.env['EW_DEVICE_SECOND_TEST']=other;config=f.config('integrations');config['second']={'secret':other,'fieldMap':{'x':'y'}}
    with f.store.connect() as db:db.execute("UPDATE settings SET data=? WHERE key='integrations'",(M.dump(config),))
    p=f.plan(mappings=[{'kind':'device','providerId':'second','reference':'EW_DEVICE_SECOND_TEST'}]);f.apply(p)
    after=f.config('integrations');assert after['sensor-a']==config['sensor-a'] and after['second']=={'secretRef':'EW_DEVICE_SECOND_TEST','fieldMap':{'x':'y'}}
    before=f.facts();f.settings({'integrations':{'second':{'fieldMap':{}}}},409);assert f.facts()==before;f.no_canary_metadata()
check('explicit partial migration removes only matched field via JSON paths; remaining legacy group is still blocked',partial_device_migration)

def no_redirect_chain():
    import io,socket
    from email.message import Message
    from urllib.request import Request,HTTPHandler,HTTPSHandler,build_opener
    from urllib.response import addinfourl
    from urllib.error import HTTPError
    from unittest.mock import patch
    token='synthetic-redirect-'+str(uuid4());CANARIES.append(token)
    for code in (301,302,303,307,308):
        for location in ('https://other.invalid/redirected','http://other.invalid/redirected','https://fixture.invalid/same-host'):
            requests=[]
            def answer(req):
                requests.append({'url':req.full_url,'method':req.get_method(),'auth':req.get_header('Authorization'),'body':req.data})
                headers=Message();headers['Location']=location
                response=addinfourl(io.BytesIO(b'not a provider reply'),headers,req.full_url,code);response.msg='Synthetic redirect';return response
            class FakeHTTP(HTTPHandler):
                def http_open(self,req):return answer(req)
            class FakeHTTPS(HTTPSHandler):
                def https_open(self,req):return answer(req)
            with patch.object(M,'build_opener',side_effect=lambda *handlers:build_opener(*handlers,FakeHTTP(),FakeHTTPS())),patch.object(socket,'create_connection',side_effect=AssertionError('External connection prohibited')):
                try:M.open_legacy_ai(Request('https://fixture.invalid/v1/responses',data=b'{"synthetic":true}',headers={'Authorization':'Bearer '+token},method='POST'));raise AssertionError('Redirect was accepted')
                except HTTPError as error:assert error.code==code
            assert len(requests)==1 and requests[0]['url']=='https://fixture.invalid/v1/responses' and requests[0]['auth']=='Bearer '+token
check('real dedicated opener rejects301/302/303/307/308 fake response chains with no second request or external network',no_redirect_chain)

def direct_transport():
    import io,socket
    from email.message import Message
    from urllib.request import Request,HTTPSHandler,build_opener
    from urllib.response import addinfourl
    from unittest.mock import patch
    requests=[]
    class FakeHTTPS(HTTPSHandler):
        def https_open(self,req):
            requests.append((req.get_header('Authorization'),req.data,req.timeout))
            response=addinfourl(io.BytesIO(b'local synthetic direct reply'),Message(),req.full_url,200);response.msg='Synthetic OK';return response
    with patch.object(M,'build_opener',side_effect=lambda *handlers:build_opener(*handlers,FakeHTTPS())),patch.object(socket,'create_connection',side_effect=AssertionError('External connection prohibited')):
        with M.open_legacy_ai(Request('https://fixture.invalid/v1/responses',data=b'safe body',headers={'Authorization':'Bearer synthetic-direct'},method='POST'),timeout=17) as response:assert response.read()==b'local synthetic direct reply'
    assert requests==[('Bearer synthetic-direct',b'safe body',17)]
check('dedicated direct-response transport retains exact header/body/timeout and does not alter global urllib opener',direct_transport)

out=ROOT/'06_验证与后续工作/负责人优化建议-密钥引用Python专项.json';old=json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
report={'at':M.now(),'runId':RUN,'kind':'fresh-owned-native-sqlite-controlled-synthetic-env-canary','checks':checks,'passed':sum(x['pass'] for x in checks),'failed':sum(not x['pass'] for x in checks),'sourceSha256':{str(SOURCE.relative_to(ROOT)):hashlib.sha256(SOURCE.read_bytes()).hexdigest()},'ownedDatabases':databases,'productionDatabaseOpened':False,'actualEnvironmentRead':False,'providerRequests':0,'serviceStarted':False};report['pass']=report['failed']==0
out.write_bytes((json.dumps({'latest':report,'runs':old.get('runs',[])+[report]},ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'passed':report['passed'],'failed':report['failed'],'runId':RUN}));raise SystemExit(0 if report['pass'] else 1)
