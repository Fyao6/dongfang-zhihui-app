"""Default-dry real regression fixture compatibility plan for secret references. No build, database or network operations.
Run without flags to review 06 plan JSON. --apply edits only the listed source files after all anchors/preflights pass.
Synthetic test-process environment refs only; original assertions and historical branches are retained.
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


helper="""async function referenceSettingsCall(ctx,body){const current=await (await ctx.get(base+'/api/admin/settings')).json();return call(ctx,'admin/settings',Number.isInteger(current.secretConfigRevision)?{requestId:'sr_regression_'+crypto.randomUUID(),expectedRevision:current.secretConfigRevision,...body}:body);}
"""
old="async function call(ctx,url,body,method='POST'){const r=await ctx.fetch(base+'/api/'+url,{method,data:body});const d=await r.json();return {r,d};}"
for file in ['06_验证与后续工作/全量回归.cjs','06_验证与后续工作/公网适配全量回归.cjs']:
    patch(file,old,old+'\n'+helper,'Regression opaque settings version helper '+file)
    original="await call(admin,'admin/settings',{integrations:{test_band:{secret,fieldMap:{}}}});"
    changed="const referenceMode=Number.isInteger((await (await admin.get(base+'/api/admin/settings')).json()).secretConfigRevision);const configured=await referenceSettingsCall(admin,{integrations:{test_band:referenceMode?{secretRef:'EW_DEVICE_REGRESSION_CANARY',fieldMap:{}}:{secret,fieldMap:{}}}});assert.equal(configured.r.status(),200);if(referenceMode){const flags=(await (await admin.get(base+'/api/admin/settings')).json()).integrations.test_band;assert(flags.hasCredential&&flags.refReady&&!flags.unmigrated);}"
    # Deliberately no weak fallback: on new API, server env must truly resolve to the header canary.
    patch(file,original,changed,'Actual device fixture config via env ref; old branch retained '+file)
    source=(ROOT/file).read_text(encoding='utf-8');old_ui=next(line for line in source.splitlines() if "await ap.locator('.sidebar [data-nav=settings]').click();" in line and '#integration-form' in line)
    old_norm=old_ui.strip();marker="await ap.locator('.sidebar [data-nav=settings]').click();"
    legacy=old_norm[len(marker):]
    new_ui=marker+"await ap.locator('#sr-device-form,#integration-form').waitFor();if(await ap.locator('#sr-device-form').count()){await ap.locator('[data-sr-edit=test_band]').click();assert.equal(await ap.locator('#sr-device-form [name=provider]').inputValue(),'test_band');await ap.locator('#sr-device-form [name=fieldMap]').fill('{\"heart_rate\":\"heartRate\"}');await ap.locator('#sr-device-form button').click();await ap.waitForFunction(()=>state.settings?.integrations?.test_band?.fieldMap?.heart_rate==='heartRate');const configured=(await (await admin.get(base+'/api/admin/settings')).json()).integrations.test_band;assert(configured.hasCredential&&configured.refReady&&!configured.unmigrated);await ap.locator('[data-sr-edit=test_band]').click();await ap.locator('#sr-device-form [name=secretRef]').fill('');await ap.locator('#sr-device-form button').click();await ap.waitForFunction(()=>state.settings?.integrations?.test_band?.hasCredential===false&&state.settings?.integrations?.test_band?.refReady===false);assert.equal((await referenceSettingsCall(admin,{integrations:{'invalid provider':{fieldMap:{}}}})).r.status(),400);}else{"+legacy+"}"
    patch(file,old_ui,' '+new_ui,'Real UI reference edit/clear preserves data/auth/invalid-provider assertions '+file)
# Only the test child inherits this public synthetic constant; no application source receives a fallback or fake secret.
file='06_验证与后续工作/全量回归.cjs'
old="{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});base=await new Promise"
new="{cwd:root,env:{...process.env,EW_DEVICE_REGRESSION_CANARY:'regression-secret-not-for-real-use'},windowsHide:true,stdio:['ignore','pipe','pipe']});base=await new Promise"
patch(file,old,new,'Python full60 child actual test env injection')
file='06_验证与后续工作/后台单元回归.py'
patch(file,"'apiKey': 'unit-test-only'","'apiKeyRef': 'EW_AI_UNIT_TEST'",'Adapter-only fixture uses env reference')
old="        with patch.object(app, 'urlopen', return_value=Response()) as network,"
patch(file,old,"        with patch.dict('os.environ', {'EW_AI_UNIT_TEST': 'unit-test-only'}, clear=False), patch.object(app, 'open_legacy_ai', return_value=Response()) as network,",'Actual test process env ref resolution; provider remains explicitly mocked')
old="        self.assertFalse(sent['store'])"
patch(file,old,old+"\n        self.assertEqual(network.call_args.args[0].get_header('Authorization'), 'Bearer unit-test-only')",'Stronger outbound header assertion proves actual reference resolution')
# All anchors must validate before writing any source. No runtime module import or database initialization.
for file,text in changes.items():
    if file.suffix=='.py':ast.parse(text.lstrip('\ufeff'),filename=str(file))
node=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
typescript=CLOUD/'node_modules/typescript'
ts_check="const ts=require(process.argv[1]);let s='';process.stdin.on('data',b=>s+=b).on('end',()=>{const rows=JSON.parse(s);let bad=false;for(const [name,body]of rows){const kind=name.endsWith('.ts')?ts.ScriptKind.TS:ts.ScriptKind.JS;const f=ts.createSourceFile(name,body,ts.ScriptTarget.Latest,true,kind);for(const d of f.parseDiagnostics){bad=true;process.stderr.write(name+': '+ts.flattenDiagnosticMessageText(d.messageText,'\\n')+'\\n');}}if(bad)process.exitCode=1;});"
scripts=[(str(p),s) for p,s in changes.items() if p.suffix in ('.ts','.js','.cjs')]
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
plan={'at':stamp,'mode':'apply' if args.apply else 'dry-run','productionEnabled':False,'fixtureOnly':True,'cloudFreshServiceRequiredVars':['EW_DEVICE_REGRESSION_CANARY=the public synthetic device canary from 密钥引用测试环境.cjs'],'noAssertionRelaxed':True,'anchors':anchors,
      'sourceChanges':[{k:v for k,v in x.items() if k not in ('originalBytes','proposedBytes')} for x in files],
      'hashing':'SHA256 of exact original/proposed UTF-8 bytes; no read_text newline normalization',
      'backupPolicy':'Flat original-byte backup files and mapping JSON in existing 06 directory; no subdirectory/version directory',
      'doesNotRun':['build','database migration against original DB','local service','public deployment','real payment/refund','carrier requests'],
      'compatibility':'Current real ref branch plus original legacy branch retained; real header/device/privacy/permissions/clear assertions preserved and env/header proof strengthened.'}
out=ROOT/'06_验证与后续工作'
report=out/'负责人优化建议-密钥引用回归兼容计划.json'
if args.apply:
    # Preflight all raw bytes before any backup or source write.
    for item in files:
        if (ROOT/item['path']).read_bytes()!=item['originalBytes']:raise RuntimeError('Source bytes changed during preflight; no source applied.')
    backup_map=out/('负责人优化建议-密钥引用回归兼容备份映射-'+stamp+'.json')
    backups=[]
    for index,item in enumerate(files,1):
        backup=out/('密钥引用回归兼容前-'+stamp+'-'+str(index).zfill(2)+'-'+Path(item['path']).name+'.bak')
        temporary=out/('密钥引用回归兼容写入-'+stamp+'-'+str(index).zfill(2)+'.tmp')
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
