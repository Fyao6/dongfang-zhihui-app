"""Exact, default-dry secret-reference integration plan. No build, database or network operations.
Run without flags to review 06 plan JSON. --apply edits only the listed source files after all anchors/preflights pass.
Requires actual closure/finance integration first. Source-only plan; never reads old database/env values or requests a provider.
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
pending=[]
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
imports="""# secret-reference-module:v1
try:
    from secret_references import SecretReferences, init_schema as init_secret_reference_schema, resolve_credential, open_legacy_ai, ai_ready as legacy_ai_ready
except ModuleNotFoundError:
    import importlib.util as _secret_ref_import
    _secret_ref_spec=_secret_ref_import.spec_from_file_location('eastern_secret_references',Path(__file__).with_name('secret_references.py'))
    _secret_ref_module=_secret_ref_import.module_from_spec(_secret_ref_spec);_secret_ref_spec.loader.exec_module(_secret_ref_module)
    SecretReferences,init_secret_reference_schema,resolve_credential,open_legacy_ai,legacy_ai_ready=_secret_ref_module.SecretReferences,_secret_ref_module.init_schema,_secret_ref_module.resolve_credential,_secret_ref_module.open_legacy_ai,_secret_ref_module.ai_ready

"""
patch(server,'class Store:',imports+'class Store:','Python independent reference/resolver imports')
def dependency_patch(file,old,new,label):
    raw=(ROOT/file).read_text(encoding='utf-8')
    if old not in raw and new not in raw:
        pending.append({'path':file,'requiredAnchor':old,'label':label});return
    patch(file,old,new,label)
dependency_patch(server,'            init_after_sales_finance_schema(db)','            init_after_sales_finance_schema(db)\n            init_secret_reference_schema(db)','Python after actual closure and finance schema')
old='            after_sales_result = AfterSales(store, self, ApiError, rate_limit).route(method, path)'
patch(server,old,"""            secret_reference_result = SecretReferences(store,self,ApiError,rate_limit).route(method,path)
            if secret_reference_result is not None:
                return secret_reference_result
"""+old,'Python exact settings/reference route before old generic admin')
# Replace the original settings branch as well, so direct internal calls cannot retain the plaintext setter.
raw=(ROOT/server).read_bytes();source=raw.decode('utf-8');_,eol=newline_style(raw);tree=ast.parse(source)
candidates=[n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='path' and len(n.test.comparators)==1 and isinstance(n.test.comparators[0],ast.Constant) and n.test.comparators[0].value=='/api/admin/settings']
assert len(candidates)==1,'Exactly one original Python settings branch is required'
n=candidates[0];old=''.join(source.splitlines(keepends=True)[n.lineno-1:n.end_lineno]).replace(eol,'\n')
if 'return SecretReferences(store,self,ApiError,rate_limit).settings' not in old:
    new="            if path == '/api/admin/settings':\n                return SecretReferences(store,self,ApiError,rate_limit).settings(method,None if method=='GET' else self.body())\n"
    patch(server,old,new,'Python original settings method delegates; no old plaintext setter remains reachable')
else:anchors.append({'file':server,'label':'Python original settings delegates','state':'already-applied'})
patch(server,"'knowledge': '', 'apiKey': ''","'knowledge': '', 'apiKeyRef': ''",'Python fresh default contains reference only')
old="aiReady=bool(ai.get('enabled') and ai.get('apiKey') and ai.get('model'))"
patch(server,old,'aiReady=legacy_ai_ready(ai)','Python public readiness resolves reference and rejects unmigrated')
old="            if not ai.get('enabled') or not ai.get('apiKey') or not ai.get('model'):"
patch(server,old,"            if not legacy_ai_ready(ai):",'Python real legacy call readiness')
old="            request = Request(ai['endpoint'], data=payload, headers={'Authorization': 'Bearer ' + ai['apiKey'], 'Content-Type': 'application/json'}, method='POST')"
new="            credential=resolve_credential(ai,'ai',ApiError)\n            request = Request(ai['endpoint'], data=payload, headers={'Authorization': 'Bearer ' + credential, 'Content-Type': 'application/json'}, method='POST')"
patch(server,old,new,'Python ephemeral header credential never added to privacy ai_config or model body')
patch(server,'with urlopen(request, timeout=60) as response:','with open_legacy_ai(request, timeout=60) as response:','Python legacy-only transport refuses every redirect; media/global opener unchanged')
patch(server,"                secret = provider_config.get('secret', '')","                secret = resolve_credential(provider_config,'device',ApiError)",'Python actual device authentication uses same purpose-limited resolver')
api='04_研发源码/app/cloud/lib/eastern-api.ts'
old="import {initAfterSales,afterSalesRoute,afterSalesReady} from './after-sales';"
patch(api,old,old+"\nimport {initSecretReferences,secretReferencesRoute,SecretReferencesService,resolveCredential,legacyAIReady} from './secret-references';",'Cloud shared server resolver imports')
dependency_patch(api,'await initAfterSalesFinance(this);','await initAfterSalesFinance(this);await initSecretReferences(this);','Cloud after actual active closure/finance init')
old='const afterSales=await afterSalesRoute(this,p,m,fail);'
patch(api,old,'const secretReferences=await secretReferencesRoute(this,p,m,fail);if(secretReferences!==undefined)return secretReferences;'+old,'Cloud exact settings/reference route')
raw=(ROOT/api).read_bytes();source=raw.decode('utf-8');_,eol=newline_style(raw);start=source.index(' async settings(){');end=source.index(eol+' async admin(',start);old=source[start:end].replace(eol,'\n')
new=" async settings(){return new SecretReferencesService(this,fail).settings(this.method,this.method==='GET'?undefined:await this.body());}"
patch(api,old,new,'Cloud original settings delegates to controlled CAS service')
patch(api,"knowledge:'',apiKey:''","knowledge:'',apiKeyRef:''",'Cloud fresh defaults reference only')
patch(api,'aiReady:!!(a.enabled&&a.apiKey&&a.model)','aiReady:legacyAIReady(a,this.env)','Cloud public readiness is truthful')
patch(api,"if(!a.enabled||!a.apiKey||!a.model)fail(503,", "if(!legacyAIReady(a,this.env))fail(503,",'Cloud real legacy readiness')
patch(api,"headers:{Authorization:'Bearer '+a.apiKey,'Content-Type':'application/json'}", "headers:{Authorization:'Bearer '+resolveCredential(a,'ai',this.env,fail),'Content-Type':'application/json'}",'Cloud header only, binding metadata unchanged')
old="if(!config.secret||!equal(this.request.headers.get('authorization')||'','Bearer '+config.secret))"
patch(api,old,"if(!equal(this.request.headers.get('authorization')||'','Bearer '+resolveCredential(config,'device',this.env,fail)))",'Cloud device verifies resolved controlled reference')
admin='04_研发源码/app/r4/time-bank-admin.html'
patch(admin,'/*__AFTER_SALES_ADMIN__*/','/*__AFTER_SALES_ADMIN__*/\n/*__SECRET_REFERENCES_ADMIN__*/','Admin explicit reference component placeholder')
for file,prefix in [('04_研发源码/app/r4/build.py','ROOT'),('04_研发源码/app/cloud/prepare.py','source')]:
    old=".replace('/*__AFTER_SALES_ADMIN__*/',("+prefix+"/'after-sales-admin.js').read_text(encoding='utf-8')+'\\nAfterSalesAdmin.install();')"
    patch(file,old,old+".replace('/*__SECRET_REFERENCES_ADMIN__*/',("+prefix+"/'secret-references-admin.js').read_text(encoding='utf-8')+'\\nSecretReferencesAdmin.install();')",'Explicit admin source/install '+prefix)
    v='admin_source' if prefix=='ROOT' else 'admin'
    old=v+"="+v+".replace('</style>',("+prefix+"/'card-service.css').read_text(encoding='utf-8')+'</style>',1)"
    patch(file,old,old+"\n"+v+"="+v+".replace('</style>',("+prefix+"/'secret-references-admin.css').read_text(encoding='utf-8')+'</style>',1)",'Admin reference component scoped CSS '+prefix)
if args.apply and pending:raise RuntimeError('Finance is not active yet; no shared source written: '+json.dumps(pending,ensure_ascii=False))
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
plan={'at':stamp,'mode':'apply' if args.apply else 'dry-run','productionEnabled':False,'newModuleDefault':'no plaintext fallback; explicit opaque metadata preview; no old DB/env migration automatic','pendingDependencyAnchors':pending,'anchors':anchors,
      'sourceChanges':[{k:v for k,v in x.items() if k not in ('originalBytes','proposedBytes')} for x in files],
      'hashing':'SHA256 of exact original/proposed UTF-8 bytes; no read_text newline normalization',
      'backupPolicy':'Flat original-byte backup files and mapping JSON in existing 06 directory; no subdirectory/version directory',
      'doesNotRun':['build','database migration against original DB','local service','public deployment','real payment/refund','carrier requests'],
      'privacyBinding':'Existing actual provider/endpoint/model/regions/policy binding is unchanged. Resolved header credentials are never inserted into ai_config, context, model body or returned API metadata.'}
out=ROOT/'06_验证与后续工作'
report=out/'负责人优化建议-密钥引用接入计划.json'
if args.apply:
    # Preflight all raw bytes before any backup or source write.
    for item in files:
        if (ROOT/item['path']).read_bytes()!=item['originalBytes']:raise RuntimeError('Source bytes changed during preflight; no source applied.')
    backup_map=out/('负责人优化建议-密钥引用接入备份映射-'+stamp+'.json')
    backups=[]
    for index,item in enumerate(files,1):
        backup=out/('密钥引用接入前-'+stamp+'-'+str(index).zfill(2)+'-'+Path(item['path']).name+'.bak')
        temporary=out/('密钥引用接入写入-'+stamp+'-'+str(index).zfill(2)+'.tmp')
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
