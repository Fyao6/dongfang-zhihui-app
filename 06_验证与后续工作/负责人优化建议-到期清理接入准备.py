"""Default dry run. Precomputes every patch before optional explicit --apply. No build/service."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent
PLAN=HERE/'负责人优化建议-到期清理接入计划.json'
NODE=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
R4='04_研发源码/app/r4/';CL='04_研发源码/app/cloud/'
OWN=[R4+'backend/privacy_retention.py',CL+'lib/privacy-retention.ts',R4+'privacy-retention.js',R4+'privacy-retention.css',R4+'privacy-retention-admin.js']
def sha(b):return hashlib.sha256(b).hexdigest()
PATCHES=[]
def patch(path,old,new):PATCHES.append((path,old,new))
imports="""# privacy-retention-integration:v1
try:
    from privacy_retention import PrivacyRetention, init_schema as init_privacy_retention_schema, guard_record_epoch, record_erasure_epoch
except ModuleNotFoundError:
    import importlib.util as _retention_import
    _retention_spec=_retention_import.spec_from_file_location('eastern_retention',Path(__file__).with_name('privacy_retention.py'))
    _retention_module=_retention_import.module_from_spec(_retention_spec);_retention_spec.loader.exec_module(_retention_module)
    PrivacyRetention,init_privacy_retention_schema,guard_record_epoch,record_erasure_epoch=_retention_module.PrivacyRetention,_retention_module.init_schema,_retention_module.guard_record_epoch,_retention_module.record_erasure_epoch
"""
patch(R4+'backend/server.py','# privacy-saved-integration:v1',imports+'# privacy-saved-integration:v1')
patch(R4+'backend/server.py','            init_card_service_schema(db)','            init_card_service_schema(db)\n            init_privacy_retention_schema(db)')
patch(R4+'backend/server.py','        def api(self, method, path):','        def api(self, method, path):\n            retention_result = PrivacyRetention(store, self, ApiError, rate_limit).route(method, path)\n            if retention_result is not None:\n                return retention_result')
patch(R4+'backend/server.py',"            if path == '/api/records' and method == 'POST':", "            if path == '/api/records' and method == 'GET':\n                with store.connect() as db:\n                    return {'accountId': self.owner, 'recordErasureEpoch': record_erasure_epoch(db,self.owner)}\n            if path == '/api/records' and method == 'POST':")
patch(R4+'backend/server.py',"                with store.connect() as db:\n                    if kind in ('checkin', 'card'):","                with store.connect() as db:\n                    db.execute('BEGIN IMMEDIATE')\n                    guard_record_epoch(db,self.owner,data.get('retentionEpoch'),ApiError)\n                    if kind in ('checkin', 'card'):")
# Only old explicit delete-records increments the new records epoch, inside its existing transaction.
patch(R4+'backend/privacy.py',"            elif kind == 'delete-records':\n                deleted['records']", "            elif kind == 'delete-records':\n                db.execute('INSERT INTO privacy_record_epochs VALUES(?,1,?) ON CONFLICT(owner) DO UPDATE SET revision=revision+1,updated=excluded.updated',(self.uid,stamp()))\n                deleted['records']")
patch(CL+'lib/eastern-api.ts',"import {initPrivacySaved,privacySavedRoute,guardedLegacySnapshotSave} from './privacy-saved';", "import {initPrivacySaved,privacySavedRoute,guardedLegacySnapshotSave} from './privacy-saved';\nimport {initPrivacyRetention,privacyRetentionRoute,recordEpochGuard,recordErasureEpoch} from './privacy-retention';")
patch(CL+'lib/eastern-api.ts','await initCardService(this);','await initCardService(this);await initPrivacyRetention(this);')
patch(CL+'lib/eastern-api.ts'," async route(){const p=this.url.pathname.replace(/\\/+$/,'')||'/',m=this.method;", " async route(){const p=this.url.pathname.replace(/\\/+$/,'')||'/',m=this.method;const retention=await privacyRetentionRoute(this,p,m,fail);if(retention!==undefined)return retention;")
old="  if(p==='/api/records'&&m==='POST'){const d=await this.body();if(!['checkin','card','body','life','mind'].includes(d.kind))fail(400,'无效记录类型。');const day=date(d.date),value=dump(d.data??{});if(['checkin','card'].includes(d.kind))await this.run('INSERT OR IGNORE INTO records VALUES (?,?,?,?,?)',this.owner,d.kind,day,value,now());else await this.run('INSERT INTO records VALUES (?,?,?,?,?) ON CONFLICT(owner,kind,day) DO UPDATE SET data=excluded.data',this.owner,d.kind,day,value,now());return {ok:true}}"
new="""  if(p==='/api/records'&&m==='GET')return {accountId:this.owner,recordErasureEpoch:await recordErasureEpoch(this,this.owner)};
  if(p==='/api/records'&&m==='POST'){
   const d=await this.body();if(!['checkin','card','body','life','mind'].includes(d.kind))fail(400,'无效记录类型。');const day=date(d.date),value=dump(d.data??{}),g=recordEpochGuard(this.owner,d.retentionEpoch),ignore=['checkin','card'].includes(d.kind);
   const sql='INSERT '+(ignore?'OR IGNORE ':'')+'INTO records SELECT ?,?,?,?,? WHERE '+g.sql+(ignore?'':' ON CONFLICT(owner,kind,day) DO UPDATE SET data=excluded.data');
   const r=await this.db.batch([this.stmt(sql,this.owner,d.kind,day,value,now(),...g.bindings),this.stmt('SELECT CASE WHEN '+g.sql+' THEN 1 ELSE 0 END ok',...g.bindings)]);
   if(!r[1].results[0]?.ok)fail(409,'资料清理代际已变化，请刷新后核对并主动重存。');return {ok:true};
  }"""
patch(CL+'lib/eastern-api.ts',old,new)
patch(CL+'lib/privacy-api.ts',"   if(kind==='delete-records')actions.push(...cardPrivacyDeletionStatements(a,uid));", "   if(kind==='delete-records'){actions.push(...cardPrivacyDeletionStatements(a,uid));actions.push(a.stmt('INSERT INTO privacy_record_epochs VALUES(?,1,?) ON CONFLICT(owner) DO UPDATE SET revision=revision+1,updated=excluded.updated',uid,t));}")
patch(R4+'build.py',"'privacy-center.css'","'privacy-center.css','privacy-retention.css'")
patch(R4+'build.py',"'privacy-center.js'","'privacy-center.js','privacy-retention.js'")
for p,prefix in [(R4+'build.py','ROOT'),(CL+'prepare.py','source')]:
 old=f".replace('/*__RECONCILIATION_ADMIN__*/',({prefix}/'reconciliation-admin.js').read_text(encoding='utf-8'))"
 patch(p,old,old+f".replace('/*__RETENTION_ADMIN__*/',({prefix}/'privacy-retention-admin.js').read_text(encoding='utf-8'))")
patch(R4+'time-bank-admin.html','/*__RECONCILIATION_ADMIN__*/','/*__RECONCILIATION_ADMIN__*/\n/*__RETENTION_ADMIN__*/')
patch(R4+'privacy-center.js','${privacyLocalTools()}${runtime.error?', '${privacyLocalTools()}${rtLink()}${runtime.error?')
patch(R4+'privacy-center.js',"   const data=await pxApi('privacy/requests',body);", "   if(kind==='delete-records'&&typeof rtRecordInvalidated==='function')rtRecordInvalidated(token);\n   const data=await pxApi('privacy/requests',body);")

def compute():
 before={};after={};anchors=[]
 for rel,old,new in PATCHES:
  if rel not in before:before[rel]=(ROOT/rel).read_bytes();after[rel]=before[rel].decode('utf-8')
  text=after[rel]
  # Match mixed CRLF/LF without rewriting any unrelated byte.
  pattern=re.escape(old).replace('\\\n','\\r?\\n')
  matches=list(re.finditer(pattern,text));already=list(re.finditer(re.escape(new).replace('\\\n','\\r?\\n'),text))
  if len(already)==1:anchors.append({'path':rel,'anchor':sha(old.encode()),'already':True});continue
  if len(matches)!=1:raise RuntimeError('anchor count '+rel+': '+str(len(matches))+' '+old[:70])
  hit=matches[0];newline='\r\n' if '\r\n' in hit.group() else '\n';replacement=new.replace('\n',newline)
  after[rel]=text[:hit.start()]+replacement+text[hit.end():];anchors.append({'path':rel,'anchor':sha(old.encode()),'already':False})
 return before,{p:s.encode('utf-8') for p,s in after.items()},anchors

def validate(after):
 def read(rel):return after.get(rel,(ROOT/rel).read_bytes()).decode('utf-8')
 for p,b in after.items():
  if p.endswith('.py'):ast.parse(b.decode('utf-8'))
 tree=ast.parse(read(R4+'build.py'));assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='js' for t in n.targets));files=next(n for n in ast.walk(assignment) if isinstance(n,ast.List) and all(isinstance(x,ast.Constant) and isinstance(x.value,str) for x in n.elts))
 app='\n'.join(read(R4+n.value) for n in files.elts)
 admin=read(R4+'time-bank-admin.html');mapping={'CREATOR':'creator','ANALYTICS':'analytics','COMMERCE':'commerce','PRIVACY':'privacy','HOME_VIDEO':'home-video','AI_GATEWAY':'ai-gateway','MEMBERSHIP':'membership-lifecycle','CARD_SERVICE':'card-service','COMMISSION':'commission','AFTER_SALES':'after-sales','RECONCILIATION':'reconciliation','RETENTION':'privacy-retention'}
 for marker,name in mapping.items():admin=admin.replace('/*__'+marker+'_ADMIN__*/',read(R4+name+'-admin.js'))
 for text in [app,*re.findall(r'<script>([\s\S]*?)</script>',admin)]:
  r=subprocess.run([str(NODE),'--check'],input=text,encoding='utf-8',capture_output=True)
  if r.returncode:raise RuntimeError(r.stderr)
 ts="const ts=require('./04_研发源码/app/cloud/node_modules/typescript');let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>{const r=ts.transpileModule(s,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true});if(r.diagnostics.length){console.error(r.diagnostics);process.exit(1)}});"
 for p in [CL+'lib/eastern-api.ts',CL+'lib/privacy-api.ts',CL+'lib/privacy-retention.ts']:
  r=subprocess.run([str(NODE),'-e',ts],input=read(p),encoding='utf-8',capture_output=True,cwd=ROOT)
  if r.returncode:raise RuntimeError(r.stderr)

before,after,anchors=compute();validate(after)
plan={'module':'privacy-retention-v1','defaultDryRun':True,'prerequisites':{p:sha((ROOT/p).read_bytes()) for p in OWN},'files':{p:{'beforeSHA256':sha(before[p]),'afterSHA256':sha(after[p])} for p in before},'anchors':anchors,'validation':{'pythonAST':True,'fullAPPAndAdminJS':True,'typeScriptSyntax':True},'buildExecuted':False,'serviceStarted':False}
if '--plan' in sys.argv:
 if PLAN.exists() and '--refresh-plan' not in sys.argv:raise RuntimeError('plan exists; explicit --refresh-plan required')
 PLAN.write_bytes(json.dumps(plan,ensure_ascii=False,indent=2).encode('utf-8'))
elif PLAN.exists():
 expected=json.loads(PLAN.read_bytes())
 if plan['prerequisites']!=expected['prerequisites']:raise RuntimeError('module source prerequisites changed')
 for p,v in expected['files'].items():
  if sha(before[p]) not in (v['beforeSHA256'],v['afterSHA256']) or sha(after[p])!=v['afterSHA256']:raise RuntimeError('shared source identity changed: '+p)
else:raise RuntimeError('first prepare explicit --plan')
if '--apply' in sys.argv:
 for p in before:
  if (ROOT/p).read_bytes()!=before[p]:raise RuntimeError('preflight race: '+p)
 for p in before:
  if before[p]==after[p]:continue
  backup=HERE/('负责人优化建议-到期清理接入前-'+Path(p).name+'-'+sha(before[p])[:12]+'.bak')
  if backup.exists() and backup.read_bytes()!=before[p]:raise RuntimeError('backup identity conflict')
  backup.write_bytes(before[p]);(ROOT/p).write_bytes(after[p])
print(json.dumps({'dryRun':'--apply' not in sys.argv,'files':len(before),'anchors':len(anchors),'alreadyAtTarget':sum(before[p]==after[p] for p in before),'validation':plan['validation'],'plan':str(PLAN)},ensure_ascii=True))
