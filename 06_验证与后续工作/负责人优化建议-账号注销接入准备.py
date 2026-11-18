"""Exact, default-dry account-closure integration plan. No build, database or network operations.
Run without flags to review 06 plan JSON. --apply edits only the listed source files after all anchors/preflights pass.
Local account disable and session revocation only; provider/backup/billing completion is never claimed. No source changes without --apply.
"""
import argparse, ast, datetime, hashlib, json, os, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
R4=ROOT/'04_研发源码/app/r4'
CLOUD=ROOT/'04_研发源码/app/cloud'
parser=argparse.ArgumentParser()
parser.add_argument('--apply',action='store_true')
args=parser.parse_args()
changes={}
originals={}
anchors=[]
def sha(value):return hashlib.sha256(value if isinstance(value,bytes) else value.encode('utf-8')).hexdigest()
def newline_style(raw):
    crlf=raw.count(b'\r\n');lf=raw.count(b'\n')-crlf
    return ('CRLF' if crlf and not lf else 'LF' if not crlf else 'mixed'), ('\r\n' if crlf>=lf and crlf else '\n')
def patch(file,old,new,label):
    file=ROOT/file
    if file not in originals:originals[file]=file.read_bytes()
    source=changes.get(file, originals[file].decode('utf-8'))
    _,eol=newline_style(originals[file])
    old=old.replace('\n',eol);new=new.replace('\n',eol)
    if source.count(new)==1:
        anchors.append({'file':str(file.relative_to(ROOT)),'label':label,'state':'already-applied'})
        return
    if source.count(old)!=1:
        raise RuntimeError(f'Expected exactly one unchanged anchor for {label} in {file.relative_to(ROOT)}; no source was written.')
    changes[file]=source.replace(old,new,1)
    anchors.append({'file':str(file.relative_to(ROOT)),'label':label,'state':'planned'})


server='04_研发源码/app/r4/backend/server.py'
imports="""# account-closure:v1 (retention must be integrated first)
try:
    from account_write_guard import guard_connection, begin_actor, end_actor, require_roles, settlement_scope
except ModuleNotFoundError:
    import importlib.util as _ac_guard_import, sys as _ac_sys
    _ac_guard_spec=_ac_guard_import.spec_from_file_location('account_write_guard',Path(__file__).with_name('account_write_guard.py'))
    _ac_guard_module=_ac_guard_import.module_from_spec(_ac_guard_spec);_ac_sys.modules['account_write_guard']=_ac_guard_module;_ac_guard_spec.loader.exec_module(_ac_guard_module)
    guard_connection,begin_actor,end_actor,require_roles,settlement_scope=(_ac_guard_module.guard_connection,_ac_guard_module.begin_actor,_ac_guard_module.end_actor,_ac_guard_module.require_roles,_ac_guard_module.settlement_scope)
try:
    from account_closure import AccountClosure, init_schema as init_account_closure_schema, account_active, require_active, can_book_teacher, integrity_response as account_integrity_response
except ModuleNotFoundError:
    import importlib.util as _ac_import
    _ac_spec=_ac_import.spec_from_file_location('eastern_account_closure',Path(__file__).with_name('account_closure.py'))
    _ac_module=_ac_import.module_from_spec(_ac_spec);_ac_spec.loader.exec_module(_ac_module)
    AccountClosure,init_account_closure_schema,account_active,require_active,can_book_teacher,account_integrity_response=(_ac_module.AccountClosure,_ac_module.init_schema,_ac_module.account_active,_ac_module.require_active,_ac_module.can_book_teacher,_ac_module.integrity_response)

"""
patch(server,'class Store:',imports+'class Store:','Python independent closure/guard imports')
patch(server,'            init_card_service_schema(db)','            init_card_service_schema(db)\n            init_account_closure_schema(db)','Python lifecycle and late owned/target schema')
patch(server,'                yield db','                yield guard_connection(db)','Python all request writes final atomic actor fence')
old="WHERE s.token=? AND s.expires>?', (hashlib.sha256(self.session_token.encode()).hexdigest(), now_ms())).fetchone()"
new="WHERE s.token=? AND s.expires>? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status=\'closed\')', (hashlib.sha256(self.session_token.encode()).hexdigest(), now_ms())).fetchone()"
# Use doubled SQL quote inside Python source, not an unescaped quote.
new=new.replace("l.status='closed'","l.status=\\'closed\\'")
patch(server,old,new,'Python session lookup excludes closed')
old="            self.owner = self.user['id'] if self.user else 'visitor:' + self.visitor"
new=old+"""
            self.account_actor_token=begin_actor(self.user['id'] if self.user else None,hashlib.sha256(self.session_token.encode()).hexdigest())
            if self.session_token and self.command not in ('GET','HEAD') and urlsplit(self.path).path not in ('/api/auth/login','/api/auth/register','/api/auth/setup','/api/auth/logout','/api/account-closure/confirm'):
                with store.connect() as db:
                    if db.execute('SELECT 1 FROM account_revoked_sessions WHERE token_hash=?',(hashlib.sha256(self.session_token.encode()).hexdigest(),)).fetchone():
                        raise ApiError(401,'账号已关闭，请使用其他账号。')
"""
patch(server,old,new.rstrip(),'Python revoked cookie cannot become visitor write; static GET unaffected')
old="""        def require(self, roles=None):
            if not self.user:
"""
new="""        def require(self, roles=None):
            if self.user:
                with store.connect() as db:
                    self.user=db.execute("SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')",(hashlib.sha256(self.session_token.encode()).hexdigest(),now_ms())).fetchone()
                self.owner=self.user['id'] if self.user else 'visitor:'+self.visitor
            if not self.user:
"""
patch(server,old,new,'Python require rechecks current session/role/closed')
patch(server,'            return self.user','            require_roles(roles)\n            return self.user','Python roles captured for final write fence')
old="""            with store.connect() as db:
                db.execute('DELETE FROM sessions WHERE expires<?', (now_ms(),))"""
new="""            with settlement_scope('session',user_id,user_id), store.connect() as db:
                db.execute('DELETE FROM sessions WHERE expires<?', (now_ms(),))"""
patch(server,old,new,'Python verified login session issuance uses target-active-only internal scope')
old="""            except sqlite3.IntegrityError as exc:
                self.send(409, {'error': '会员方案或订阅状态已变化，请重新确认。' if 'membership_' in str(exc) else '账号或记录已存在，请刷新后重试。'})"""
new="""            except sqlite3.IntegrityError as exc:
                account_error=account_integrity_response(exc)
                self.send(account_error[0] if account_error else 409, {'error':account_error[1] if account_error else ('会员方案或订阅状态已变化，请重新确认。' if 'membership_' in str(exc) else '账号或记录已存在，请刷新后重试。')})"""
patch(server,old,new,'Python safe account conflict mapping without SQL')
old="""            except Exception:
                self.send(500, {'error': '服务暂时无法处理此请求。'})

        def api"""
new="""            except Exception:
                self.send(500, {'error': '服务暂时无法处理此请求。'})
            finally:
                if hasattr(self,'account_actor_token'):
                    end_actor(self.account_actor_token)
                    del self.account_actor_token

        def api"""
patch(server,old,new,'Python request context always reset including streaming')
old='        def api(self, method, path):'
new=old+"""
            closure_result=AccountClosure(store,self,ApiError,rate_limit,check_password).route(method,path)
            if closure_result is not None:
                return closure_result"""
patch(server,old,new,'Python two-step route before legacy pending privacy requests')
old="""            item = json.loads(row['data'])
            if row['kind'] == 'devices':"""
new="""            item = json.loads(row['data'])
            if row['kind']=='teachers':
                with self.connect() as db:
                    if not can_book_teacher(db,row['id'],item):
                        continue
            if row['kind'] == 'devices':"""
patch(server,old,new,'Python closed teachers removed only from new booking directory; works retained')

api='04_研发源码/app/cloud/lib/eastern-api.ts'
old="import {initAfterSales,afterSalesRoute,afterSalesReady} from './after-sales';"
new=old+"""
import {initAccountClosure,accountClosureRoute,requireAccountActive,refreshAccountAuth,canBookTeacher,accountFailure} from './account-closure';
import {bindAccountDatabase,accountRequiredRoles,verifiedSessionApi} from './account-write-guard';"""
patch(api,old,new,'Cloud closure and final write guard imports')
patch(api,'this.db=env.DB;','this.db=bindAccountDatabase(this,env.DB);','Cloud prepare/run/first/all/batch guard proxy')
patch(api,'return this.user}\n async body','accountRequiredRoles(this,roles);return this.user}\n async body','Cloud role requirement recorded for final DML')
patch(api,"  const c=Object.fromEntries","  await initAccountClosure(this,false);\n  const c=Object.fromEntries",'Cloud lifecycle schema before cookie lookup')
old="'SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>?'"
new='"SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status=\'closed\')"'
patch(api,old,new,'Cloud cookie lookup excludes closed')
patch(api,'await initCardService(this);','await initCardService(this);await initAccountClosure(this);','Cloud final personal/target guards after all schemas')
old="if(item.creatorId&&!await this.one("
new="if(row.kind==='teachers'&&!await canBookTeacher(this,row.id,item))continue;"+old
patch(api,old,new,'Cloud closed teachers excluded from booking targets; published works retained')
old="async login(uid:string){const token=id()+id();await this.db.batch([this.stmt('DELETE FROM sessions WHERE expires<?',now()),this.stmt('INSERT INTO sessions VALUES (?,?,?)',await hash(token),uid,now()+604800000)]);"
new="async login(uid:string){await requireAccountActive(this,uid,fail);const sessionApi=await verifiedSessionApi(this,uid),token=id()+id();await sessionApi.db.batch([sessionApi.stmt('DELETE FROM sessions WHERE expires<?',now()),sessionApi.stmt('INSERT INTO sessions VALUES (?,?,?)',await hash(token),uid,now()+604800000)]);"
patch(api,old,new,'Cloud actual verified password login issuance; closed target final trigger retained')
old="async route(){const p=this.url.pathname.replace(/\\/+$/,'')||'/',m=this.method;"
new=old+"await refreshAccountAuth(this,fail);const closure=await accountClosureRoute(this,p,m,fail,{verifyPassword:async(plain,stored)=>equal(stored,await password(plain,stored.split(':')[0]))});if(closure!==undefined)return closure;"
patch(api,old,new,'Cloud auth refresh and two-phase closure before cached module routes')
patch(api,"const conflict=/UNIQUE constraint|membership_/","const account=accountFailure(e);const conflict=/UNIQUE constraint|membership_/",'Cloud classify safe closure conflicts')
patch(api,'if(!expected&&!conflict)console.error','if(!expected&&!conflict&&!account)console.error','Cloud expected account rejection not raw logged')
patch(api,'error:expected?e.message:conflict?','error:expected?e.message:account?account.message:conflict?','Cloud no SQL account response')
patch(api,'status:expected?e.status:conflict?','status:expected?e.status:account?account.status:conflict?','Cloud proper closure status mapping')


# Preserve the existing Python transaction/epoch/nonce/settings gate and add an explicit SQL final condition.
patch('04_研发源码/app/r4/backend/ai_gateway.py',
      "db.execute('INSERT INTO privacy_conversations VALUES(?,?,?,?)',(saved_id,self.owner,dump(content),now()))",
      'inserted=db.execute("INSERT INTO privacy_conversations SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM privacy_preferences WHERE user_id=? AND revision=? AND provider_binding=? AND json_extract(data,\'$.saveConversations\')=1) AND NOT EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=? AND status=\'closed\')",(saved_id,self.owner,dump(content),now(),self.owner,active_authorization[\'globalRevision\'],active_authorization[\'globalBinding\'],self.owner))\n                        if not inserted.rowcount:saved_id=None',
      'Python actual authorized gateway save remains conditional under trusted settlement scope')

# Internal existing-fact settlement. No user input flag/endpoint enables these adapters.
gateway='04_研发源码/app/cloud/lib/ai-gateway.ts'
old="import {"
source=(ROOT/gateway).read_bytes().decode('utf-8')
first=source.splitlines()[0]
# Stable imported module anchor; independent import at file start.
if "from './account-write-guard'" not in source:
    patch(gateway,first,"import {trustedSettlementApi} from './account-write-guard';\n"+first,'Cloud gateway internal settled fact adapter import')
old="if(!claimed.meta.changes)fail(409,'请求已启动、取消或过期。');let activeController"
new="if(!claimed.meta.changes)fail(409,'请求已启动、取消或过期。');a=await trustedSettlementApi(a,'gateway',id,owner);let activeController"
patch(gateway,old,new,'Cloud trusted runtime only after guarded existing job claim')

gateway_py='04_研发源码/app/r4/backend/ai_gateway.py'
raw=(ROOT/gateway_py).read_bytes();source=changes.get(ROOT/gateway_py,raw.decode('utf-8'));style,eol=newline_style(raw)
if "# account-closure-existing-job-settlement:v1" not in source:
    tree=ast.parse(source);method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='run' and [a.arg for a in n.args.args]==['self','jid','raw','emit'])
    lines=source.splitlines(keepends=True);old=''.join(lines[method.lineno-1:method.end_lineno])
    marker="            if not result.rowcount:self.fail(409,'请求已启动、取消或过期。')"+eol
    assert old.count(marker)==1
    prefix,rest=old.split(marker,1)
    new=prefix+marker+"        # account-closure-existing-job-settlement:v1"+eol+"        from account_write_guard import settlement_scope"+eol+"        with settlement_scope('gateway',jid,self.owner):"+eol+''.join('    '+line if line.strip() else line for line in rest.splitlines(keepends=True))
    patch(gateway_py,old.replace(eol,'\n'),new.replace(eol,'\n'),'Python trusted gateway runtime only after guarded job claim')
else:anchors.append({'file':gateway_py,'label':'Python trusted gateway runtime','state':'already-applied'})

commerce='04_研发源码/app/cloud/lib/commerce-api.ts'
old="import {legacyAfterSalesInsertGuard} from './after-sales';"
patch(commerce,old,old+"\nimport {trustedSettlementApi} from './account-write-guard';",'Cloud committed order internal settlement import')
patch(commerce,'syncCommissionOrder(a,r.id)',"syncCommissionOrder(['paid','partially_refunded','refunded'].includes(r.payment_status)?await trustedSettlementApi(a,'order',r.id,r.owner):a,r.id)",'Cloud existing paid/refunded order commission completion')
patch(commerce,"const lifecycle=new MembershipLifecycle(a,fail);if(refund)","const settlement=await trustedSettlementApi(a,'order',oid,row.owner),lifecycle=new MembershipLifecycle(settlement,fail);if(refund)",'Cloud paid order membership callback survives owner closure without new payment authority')

build='04_研发源码/app/r4/build.py'
patch(build,"'after-sales-ui.css'","'after-sales-ui.css','account-closure.css'",'APP closure scoped CSS')
patch(build,"'after-sales-ui.js',","'after-sales-ui.js','account-closure.js',",'APP two-step closure UI after membership reminders and saved snapshots')
exports={
'accountLifecycle':"SELECT status,epoch,closed_at,receipt_id FROM account_lifecycle WHERE owner=?",
'accountClosureReceipts':"SELECT id,request_id,created,details FROM account_closure_receipts WHERE owner=?"
}
privacy='04_研发源码/app/r4/backend/privacy.py'
old="            'membershipSubscriptions':"
patch(privacy,old,''.join('            '+repr(k)+': ('+repr(v)+',),\n' for k,v in exports.items())+old,'Python owner-only closure receipt export; no credential/nonce/session tables')
privacy_ts='04_研发源码/app/cloud/lib/privacy-api.ts'
old='   membershipSubscriptions:'
patch(privacy_ts,old,''.join('   '+k+':'+json.dumps(v,ensure_ascii=False)+',\n' for k,v in exports.items())+old,'Cloud owner-only closure receipt export')


unit='06_验证与后续工作/后台单元回归.py'
patch(unit,'import importlib.util\n','import importlib.util\nimport hashlib\n','Original adapter unit: explicit real token hash fixture')
old="""    def test_responses_adapter_with_reasoning_item(self):
        class Configuration:
            def setting(self, _):"""
new="""    def test_responses_adapter_with_reasoning_item(self):
        fixture_store=app.Store(database)
        unit_token='synthetic-unit-session-token'
        with fixture_store.connect() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',('unit-test-user','unit_test_user',app.password_hash('synthetic-unit-password'),'Synthetic unit user','user',app.now_ms()))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(unit_token.encode()).hexdigest(),'unit-test-user',app.now_ms()+60000))
        class Configuration:
            def connect(self):
                return fixture_store.connect()
            def setting(self, _):"""
patch(unit,old,new,'Original adapter unit: real isolated Store/session; no mock require')
old="        handler.user = {'id': 'unit-test-user', 'role': 'user'}"
new=old+"""
        handler.session_token=unit_token
        handler.visitor='0'*32
        handler.owner='unit-test-user'
        handler.cookies_out=[]"""
patch(unit,old,new,'Original adapter unit identity fields for fresh require')

# All anchors must validate before writing any source. No runtime module import or database initialization.
for file,text in changes.items():
    if file.suffix=='.py':ast.parse(text.lstrip('\ufeff'),filename=str(file))
node=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
typescript=CLOUD/'node_modules/typescript'
ts_check="const ts=require(process.argv[1]);let s='';process.stdin.on('data',b=>s+=b).on('end',()=>{const rows=JSON.parse(s);let bad=false;for(const [name,body]of rows){const kind=name.endsWith('.ts')?ts.ScriptKind.TS:ts.ScriptKind.JS;const f=ts.createSourceFile(name,body,ts.ScriptTarget.Latest,true,kind);for(const d of f.parseDiagnostics){bad=true;process.stderr.write(name+': '+ts.flattenDiagnosticMessageText(d.messageText,'\\n')+'\\n');}}if(bad)process.exitCode=1;});"
scripts=[(str(p),s) for p,s in changes.items() if p.suffix in ('.ts','.js')]
if scripts:
    subprocess.run([str(node),'-e',ts_check,str(typescript)],input=json.dumps(scripts),text=True,encoding='utf-8',check=True,capture_output=True)
# HTML module placeholder is inside the existing script; no executable new inline code is introduced by this edit.
files=[]
for file,text in changes.items():
    original=originals[file];proposed=text.encode('utf-8')
    style,_=newline_style(original)
    files.append({'path':str(file.relative_to(ROOT)),'beforeSha256':sha(original),'afterSha256':sha(proposed),
                  'originalBytes':original,'proposedBytes':proposed,'originalNewlineStyle':style,
                  'editingNewlinePolicy':'Original untouched bytes retained; inserted/replaced blocks use the file dominant newline.'})
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
plan={'at':stamp,'mode':'apply' if args.apply else 'dry-run','externalDeletionClaimed':False,'newModuleDefault':'two-phase local closure; no external deletion claims','anchors':anchors,
      'sourceChanges':[{k:v for k,v in x.items() if k not in ('originalBytes','proposedBytes')} for x in files],
      'hashing':'SHA256 of exact original/proposed UTF-8 bytes; no read_text newline normalization',
      'backupPolicy':'Flat original-byte backup files and mapping JSON in existing 06 directory; no subdirectory/version directory',
      'doesNotRun':['build','database migration against original DB','local service','public deployment','real payment/refund','carrier requests'],
      'contract':'Atomic local disable/session revocation/authoritative cleanup; final user-write fences; narrow existing-fact settlement.'}
out=ROOT/'06_验证与后续工作'
report=out/'负责人优化建议-账号注销接入计划.json'
if args.apply:
    # Preflight all raw bytes before any backup or source write.
    for item in files:
        if (ROOT/item['path']).read_bytes()!=item['originalBytes']:raise RuntimeError('Source bytes changed during preflight; no source applied.')
    backup_map=out/('负责人优化建议-账号注销接入备份映射-'+stamp+'.json')
    backups=[]
    for index,item in enumerate(files,1):
        backup=out/('账号注销接入前-'+stamp+'-'+str(index).zfill(2)+'-'+Path(item['path']).name+'.bak')
        temporary=out/('账号注销接入写入-'+stamp+'-'+str(index).zfill(2)+'.tmp')
        if backup.exists() or temporary.exists():raise RuntimeError('Refuse overwrite of an existing backup or temporary source.')
        backups.append({'source':item['path'],'backup':str(backup.relative_to(ROOT)),'sha256':item['beforeSha256'],
                        'bytes':len(item['originalBytes']),'proposedSha256':item['afterSha256'],
                        'originalNewlineStyle':item['originalNewlineStyle'],'temporary':str(temporary.relative_to(ROOT))})
    if backup_map.exists():raise RuntimeError('Refuse overwrite of an existing backup mapping.')
    for item,entry in zip(files,backups):
        backup=ROOT/entry['backup'];backup.write_bytes(item['originalBytes'])
        if sha(backup.read_bytes())!=entry['sha256']:raise RuntimeError('Original-byte backup verification failed; no source applied.')
    backup_map.write_bytes((json.dumps({'at':stamp,'policy':'flat original bytes; no new directories','files':backups},ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    # Check all targets again after backup; check each one again immediately before its replacement.
    for item in files:
        if (ROOT/item['path']).read_bytes()!=item['originalBytes']:raise RuntimeError('Source bytes changed after backup; no source applied.')
    for item,entry in zip(files,backups):
        file=ROOT/item['path']
        if file.read_bytes()!=item['originalBytes']:raise RuntimeError('Source bytes changed before replacement; original backups are in 06 mapping.')
        temporary=ROOT/entry['temporary'];temporary.write_bytes(item['proposedBytes']);os.replace(temporary,file)
        if sha(file.read_bytes())!=item['afterSha256']:raise RuntimeError('Applied bytes differ; inspect exact original backups in 06 mapping.')
    plan['backupMapping']=str(backup_map.relative_to(ROOT))
    plan['backupFiles']=[{k:v for k,v in x.items() if k!='temporary'} for x in backups]
report.write_bytes((json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'mode':plan['mode'],'plannedFiles':len(files),'anchors':len(anchors),'report':str(report.relative_to(ROOT))},ensure_ascii=False))
