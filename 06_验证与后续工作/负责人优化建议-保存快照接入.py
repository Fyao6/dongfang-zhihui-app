"""Saved-snapshot supplemental integration. Default dry-run; root applies after card module gates."""
import argparse,ast,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
files={};changes=[];before={}
def once(name,marker,old,new):
 p=ROOT/name
 if p not in files:files[p]=p.read_text(encoding='utf-8-sig');before[p]=hashlib.sha256(p.read_bytes()).hexdigest()
 text=files[p]
 if marker in text:return
 if text.count(old)!=1:raise RuntimeError('Snapshot integration anchor is not unique: '+name+' / '+marker)
 files[p]=text.replace(old,new,1);changes.append({'file':name,'marker':marker})
server='04_研发源码/app/r4/backend/server.py';cloud='04_研发源码/app/cloud/lib/eastern-api.ts';build='04_研发源码/app/r4/build.py'
imports="""# privacy-saved-integration:v1
try:
    from privacy_saved import SavedConversations, init_schema as init_privacy_saved_schema, guarded_legacy_save
except ModuleNotFoundError:
    import importlib.util as _privacy_saved_import
    _privacy_saved_spec=_privacy_saved_import.spec_from_file_location('eastern_privacy_saved',Path(__file__).with_name('privacy_saved.py'))
    _privacy_saved_module=_privacy_saved_import.module_from_spec(_privacy_saved_spec);_privacy_saved_spec.loader.exec_module(_privacy_saved_module)
    SavedConversations,init_privacy_saved_schema,guarded_legacy_save=_privacy_saved_module.SavedConversations,_privacy_saved_module.init_schema,_privacy_saved_module.guarded_legacy_save
"""
once(server,'# privacy-saved-integration:v1','from zoneinfo import ZoneInfo, ZoneInfoNotFoundError\n','from zoneinfo import ZoneInfo, ZoneInfoNotFoundError\n'+imports)
once(server,'            init_privacy_saved_schema(db)','            init_privacy_schema(db)','            init_privacy_schema(db)\n            init_privacy_saved_schema(db)')
once(server,'            saved_result = SavedConversations','            privacy_result = Privacy',"            saved_result = SavedConversations(store, self, ApiError, rate_limit).route(method, path)\n            if saved_result is not None:\n                return saved_result\n            privacy_result = Privacy")
once(server,"guarded_legacy_save(store, self.user['id'], messages +", "privacy_save_conversation(store, self.user['id'], messages +", "guarded_legacy_save(store, self.user['id'], messages +")
once(cloud,"from './privacy-saved'", "import {initPrivacy,privacyRoute,authorizeAI,savePrivacyConversation} from './privacy-api';", "import {initPrivacy,privacyRoute,authorizeAI,savePrivacyConversation} from './privacy-api';\nimport {initPrivacySaved,privacySavedRoute,guardedLegacySnapshotSave} from './privacy-saved';")
once(cloud,'await initPrivacySaved(this);','await initPrivacy(this);','await initPrivacy(this);await initPrivacySaved(this);')
once(cloud,'const savedSnapshots=await privacySavedRoute','const privacy=await privacyRoute(this,p,m,fail);',"const savedSnapshots=await privacySavedRoute(this,p,m,fail);if(savedSnapshots!==undefined)return savedSnapshots;const privacy=await privacyRoute(this,p,m,fail);")
once(cloud,'await guardedLegacySnapshotSave(this,this.user.id,','await savePrivacyConversation(this,this.user.id,','await guardedLegacySnapshotSave(this,this.user.id,')
once(build,"'privacy-saved.js'", "'i18n-ui.js'", "'privacy-saved.js','i18n-ui.js'")
# Keep this compatible whether card-service.css has already been integrated or not.
p=ROOT/build
css_tree=ast.parse(files[p]);css_list=next(n for n in ast.walk(css_tree) if isinstance(n,ast.List) and any(isinstance(v,ast.Constant) and v.value=='base.css' for v in n.elts))
css_anchor=ast.get_source_segment(files[p],css_list)
once(build,"'privacy-saved.css'",css_anchor,css_anchor[:-1]+",'privacy-saved.css']")
# prepare.py consumes the r4-built APP; it does not own a separate JS/CSS list or snapshot admin UI.
prepare=ROOT/'04_研发源码/app/cloud/prepare.py';prepare_text=prepare.read_text(encoding='utf-8-sig')
assert "03_当前APP/东方智慧-首页体验R4.html" in prepare_text and "(generated/'experience.html').write_text(html" in prepare_text, 'Cloud prepare must consume the actual current r4 output'
for p,text in files.items():
 if p.suffix=='.py':ast.parse(text)
# Validate planned TS syntax and the full planned APP program before any optional write.
node=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
if not node.is_file():raise RuntimeError('Bundled Node is required for pre-write syntax validation')
ts_path=ROOT/'04_研发源码/app/cloud/node_modules/typescript'
parse_ts="const fs=require('node:fs'),p=JSON.parse(fs.readFileSync(0,'utf8')),ts=require(p.library),f=ts.createSourceFile(p.filename,p.content,ts.ScriptTarget.ES2022,true,ts.ScriptKind.TS);if(f.parseDiagnostics.length){for(const d of f.parseDiagnostics)process.stderr.write(ts.flattenDiagnosticMessageText(d.messageText,' '));process.exit(1);}"
check=subprocess.run([str(node),'-e',parse_ts],input=json.dumps({'library':str(ts_path),'filename':cloud,'content':files[ROOT/cloud]}),capture_output=True,encoding='utf8')
if check.returncode:raise RuntimeError('Planned Cloud API syntax failed: '+check.stderr)
tree=ast.parse(files[ROOT/build]);jsnames=ast.literal_eval(next(n for n in ast.walk(tree) if isinstance(n,ast.List) and any(isinstance(v,ast.Constant) and v.value=='base.js' for v in n.elts)))
r4=ROOT/'04_研发源码/app/r4';program='\n'.join(files.get(r4/name,(r4/name).read_text(encoding='utf-8-sig')) for name in jsnames)
check=subprocess.run([str(node),'--check'],input=program,capture_output=True,encoding='utf8')
if check.returncode:raise RuntimeError('Planned combined APP syntax failed: '+check.stderr)
if args.apply:
 # All anchors and all Python syntax are checked before any write; no entire-file hash lock.
 for p,text in files.items():p.write_text(text,encoding='utf8')
report={'mode':'apply' if args.apply else 'dry-run','applicationFilesWritten':len(files) if args.apply else 0,'plannedFiles':len(files),'plannedChanges':len(changes),'changes':changes,'files':[{'path':str(p.relative_to(ROOT)),'beforeSha256':before[p],'plannedSha256':hashlib.sha256(text.encode()).hexdigest()} for p,text in files.items()],'preWriteValidation':['all-anchors-unique','all-files-precomputed','Python-AST','Cloud-TS-parse','combined-APP-syntax'],'cloudPrepareConsumesR4Build':True,'cloudPrepareModified':False,'frozenPrivacyFilesModified':False,'ownerExportsModified':False,'buildExecuted':False,'databaseAccessed':False}
p=Path(__file__).with_suffix('.json');runs=json.loads(p.read_text(encoding='utf8')).get('runs',[]) if p.exists() else [];runs.append(report);p.write_text(json.dumps({'latest':report,'runs':runs},ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({k:report[k] for k in ('mode','applicationFilesWritten','plannedFiles','plannedChanges','buildExecuted','databaseAccessed')}))
