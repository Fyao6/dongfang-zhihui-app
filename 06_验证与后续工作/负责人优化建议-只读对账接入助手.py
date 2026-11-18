"""Root-owned integration helper. Default dry-run; never builds, starts services or opens DBs.

Uses unique insertion anchors against LIVE sources, so later B11 build-list edits survive.
All five complete candidates and checks finish before the first source write.
"""
import argparse,ast,difflib,hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R4='04_研发源码/app/r4/';CLOUD='04_研发源码/app/cloud/'
FROZEN={R4+'backend/reconciliation.py':'8dc5978fdd2784a515bfe2c637a4505b0b8da802750773cb966939c4c6b9ba58',CLOUD+'lib/reconciliation-api.ts':'d9ff619366779968c56a0f77f99799c87ec73b122e396379e75259ba27531dfc',R4+'reconciliation-admin.js':'4db74c54eb6fa7e275ed6644cf33c0bc437a662e569085fdb0f62a9cf057f116'}
OPERATIONS=[
 (R4+'backend/server.py','import read-only service; no schema',"try:\n    from creator import Creator, init_schema as init_creator_schema",'''# reconciliation-integration:v1
try:
    from reconciliation import Reconciliation
except ModuleNotFoundError:
    import importlib.util as _reconciliation_import
    _reconciliation_spec=_reconciliation_import.spec_from_file_location('eastern_reconciliation',Path(__file__).with_name('reconciliation.py'))
    _reconciliation_module=_reconciliation_import.module_from_spec(_reconciliation_spec);_reconciliation_spec.loader.exec_module(_reconciliation_module)
    Reconciliation=_reconciliation_module.Reconciliation
try:
    from creator import Creator, init_schema as init_creator_schema'''),
 (R4+'backend/server.py','route before commerce and generic admin','            commerce_result = Commerce(store, self, ApiError, rate_limit).route(method, path)', '''            reconciliation_result = Reconciliation(store, self, ApiError, rate_limit).route(method, path)
            if reconciliation_result is not None:
                return reconciliation_result
            commerce_result = Commerce(store, self, ApiError, rate_limit).route(method, path)'''),
 (CLOUD+'lib/eastern-api.ts','import read-only route only',"import {initCommission,commissionRoute} from './commission-api';", "import {initCommission,commissionRoute} from './commission-api';\nimport {reconciliationRoute} from './reconciliation-api';"),
 (CLOUD+'lib/eastern-api.ts','route before commerce and generic admin','const commerce=await commerceRoute(this,p,m,fail);', 'const reconciliationResult=await reconciliationRoute(this,p,m,fail);if(reconciliationResult!==undefined)return reconciliationResult;const commerce=await commerceRoute(this,p,m,fail);'),
 (R4+'time-bank-admin.html','marker immediately after commission admin','/*__COMMISSION_ADMIN__*/','/*__COMMISSION_ADMIN__*/\n/*__RECONCILIATION_ADMIN__*/'),
 (R4+'build.py','admin injection only; preserve all B11/App lists',".replace('/*__COMMISSION_ADMIN__*/',(ROOT/'commission-admin.js').read_text(encoding='utf-8'))", ".replace('/*__COMMISSION_ADMIN__*/',(ROOT/'commission-admin.js').read_text(encoding='utf-8')).replace('/*__RECONCILIATION_ADMIN__*/',(ROOT/'reconciliation-admin.js').read_text(encoding='utf-8'))"),
 (CLOUD+'prepare.py','Cloud admin injection only',".replace('/*__COMMISSION_ADMIN__*/',(source/'commission-admin.js').read_text(encoding='utf-8'))", ".replace('/*__COMMISSION_ADMIN__*/',(source/'commission-admin.js').read_text(encoding='utf-8')).replace('/*__RECONCILIATION_ADMIN__*/',(source/'reconciliation-admin.js').read_text(encoding='utf-8'))"),
]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def inside(name):
    p=(ROOT/name).resolve();assert p.is_relative_to(ROOT.resolve()),'Outside project: '+name;return p
def checked_run(command,stdin,cwd=ROOT):
    r=subprocess.run(command,input=stdin,text=True,encoding='utf-8',capture_output=True,cwd=cwd)
    if r.returncode:raise RuntimeError('Candidate validation failed:\n'+r.stderr+r.stdout)
    return r.stdout
def marker_map(build):
    found={}
    for n in ast.walk(ast.parse(build)):
        if not(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='replace' and len(n.args)>=2 and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) and re.fullmatch(r'/\*__[A-Z_]+_ADMIN__\*/',n.args[0].value)):continue
        marker=n.args[0].value;read=n.args[1]
        assert isinstance(read,ast.Call) and isinstance(read.func,ast.Attribute) and read.func.attr=='read_text'
        join=read.func.value;assert isinstance(join,ast.BinOp) and isinstance(join.op,ast.Div) and isinstance(join.right,ast.Constant) and isinstance(join.right.value,str)
        assert marker not in found,'Duplicate build marker: '+marker;found[marker]=join.right.value
    return found
def candidates(rollback=False):
    originals={};working={};ops={};already=[]
    for name,_,_,_ in OPERATIONS:
        if name not in originals:originals[name]=inside(name).read_bytes();working[name]=originals[name].decode('utf-8');ops[name]=[]
    for name,label,before,after in (list(reversed(OPERATIONS)) if rollback else OPERATIONS):
        eol='\r\n' if b'\r\n' in originals[name] else '\n';before=before.replace('\n',eol);after=after.replace('\n',eol);text=working[name]
        # Insertion anchors remain inside targets. Check both counts to reject duplicate drift.
        if rollback:
            if text.count(after)==0:
                assert text.count(before)==1,(name,label,'neither unique before nor after');already.append(name+':'+label);continue
            assert text.count(after)==1 and text.count(before)==1,(name,label,'reverse anchor ambiguity');old,new=after,before
        else:
            if text.count(after)==1:
                assert text.count(before)==1,(name,label,'duplicate before anchor');already.append(name+':'+label);continue
            assert text.count(after)==0 and text.count(before)==1,(name,label,'unique anchor required');old,new=before,after
        working[name]=text.replace(old,new);ops[name].append((label,old,new))
    for name,text in working.items():
        reversed_text=text
        for _,old,new in reversed(ops[name]):
            assert reversed_text.count(new)==1,(name,'reverse validation');reversed_text=reversed_text.replace(new,old)
        assert reversed_text.encode('utf-8')==originals[name],name+' non-owned bytes were changed'
    return originals,working,ops,already
def validate(originals,working,rollback,node):
    checks=[]
    for name,text in working.items():
        if name.endswith('.py'):ast.parse(text,filename=name)
    checks.append('complete server/build/prepare AST')
    # Existing Saved/card hooks and B11 lists remain byte-for-byte outside the seven inserts.
    protected={R4+'backend/server.py':['guarded_legacy_save','SavedConversations(','CardService('],CLOUD+'lib/eastern-api.ts':['guardedLegacySnapshotSave','privacySavedRoute(','cardServiceRoute('],R4+'build.py':["'privacy-saved.js'","'card-service-ui.js'","'privacy-saved.css'"],CLOUD+'prepare.py':['/*__CARD_SERVICE_ADMIN__*/']}
    for name,tokens in protected.items():
        before=originals[name].decode('utf-8');after=working[name]
        for token in tokens:assert before.count(token)>0 and before.count(token)==after.count(token),(name,'protected hook',token)
    assert 'state.commissionPermission=d.commissionPermission||null' in working[R4+'time-bank-admin.html'],'Existing staff finance metadata hook missing'
    if not rollback:
        assert working[R4+'backend/server.py'].index('reconciliation_result =')<working[R4+'backend/server.py'].index("if path.startswith('/api/admin/'):")
        assert working[CLOUD+'lib/eastern-api.ts'].index('const reconciliationResult=await')<working[CLOUD+'lib/eastern-api.ts'].index("if(p.startsWith('/api/admin/'))return this.admin(p);")
    checks.append('Saved/card/finance metadata preserved; routing precedes generic admin')
    # Derive actual admin markers from each complete candidate build AST, never execute builds.
    bm=marker_map(working[R4+'build.py']);cm=marker_map(working[CLOUD+'prepare.py']);assert bm==cm,'APP/Cloud admin marker mapping differs'
    html=working[R4+'time-bank-admin.html'].replace('__SNAPSHOT__','null')
    markers=re.findall(r'/\*__[A-Z_]+_ADMIN__\*/',html)
    assert len(markers)==len(set(markers)) and set(markers)==set(bm),'Admin markers missing/duplicated/unmapped'
    if not rollback:assert html.index('/*__COMMISSION_ADMIN__*/')<html.index('/*__RECONCILIATION_ADMIN__*/')
    for marker,module in bm.items():html=html.replace(marker,inside(R4+module).read_text(encoding='utf-8'))
    for script in re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>',html):checked_run([str(node),'--check'],script)
    checks.append('complete assembled admin JS, both build marker maps')
    # Virtual TypeScript host overlays the full candidate, emits no file. Existing diagnostics
    # are exposed and unchanged; a candidate may not introduce any new strict diagnostic.
    program=r'''
const fs=require('fs'),path=require('path'),ts=require('./node_modules/typescript');
const p=JSON.parse(fs.readFileSync(0,'utf8')),cfg=ts.readConfigFile('tsconfig.json',ts.sys.readFile);if(cfg.error)throw Error(ts.flattenDiagnosticMessageText(cfg.error.messageText,'\n'));
const parsed=ts.parseJsonConfigFileContent(cfg.config,ts.sys,process.cwd()),options={...parsed.options,target:ts.ScriptTarget.ES2020,noEmit:true,incremental:false};
const file=path.resolve('lib/eastern-api.ts'),key=x=>path.resolve(x).toLowerCase();
function diagnostics(source){const host=ts.createCompilerHost(options),read=host.readFile.bind(host),get=host.getSourceFile.bind(host);host.readFile=f=>key(f)===key(file)?source:read(f);host.getSourceFile=(f,lang,onError,fresh)=>key(f)===key(file)?ts.createSourceFile(f,source,lang,true):get(f,lang,onError,fresh);const program=ts.createProgram([file,path.resolve('lib/reconciliation-api.ts')],options,host);return ts.getPreEmitDiagnostics(program).map(d=>({code:d.code,file:d.file?path.relative(process.cwd(),d.file.fileName):'',start:d.start??0,message:ts.flattenDiagnosticMessageText(d.messageText,'\n')}));}
const before=diagnostics(p.before),after=diagnostics(p.after),old=new Map(),added=[];for(const d of before){const k=JSON.stringify({...d,start:undefined});old.set(k,(old.get(k)||0)+1)}for(const d of after){const k=JSON.stringify({...d,start:undefined}),n=old.get(k)||0;if(n)old.set(k,n-1);else added.push(d)}if(added.length){console.error(JSON.stringify({newStrictDiagnostics:added},null,2));process.exit(1)}console.log(JSON.stringify({virtualTypeScript:true,noEmit:true,baselineStrictDiagnostics:before.length,candidateStrictDiagnostics:after.length,newStrictDiagnostics:0}));
'''
    ts=json.loads(checked_run([str(node),'-e',program],json.dumps({'before':originals[CLOUD+'lib/eastern-api.ts'].decode('utf-8'),'after':working[CLOUD+'lib/eastern-api.ts']}),inside(CLOUD)))
    checks.append(ts)
    return checks
def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--apply',action='store_true');g.add_argument('--rollback',action='store_true');p.add_argument('--show-diff',action='store_true');args=p.parse_args()
    for name,expected in FROZEN.items():assert sha(inside(name).read_bytes())==expected,'Frozen module changed: '+name
    node=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe';assert node.is_file(),'Bundled Node missing; no source written'
    originals,working,ops,already=candidates(args.rollback);checks=validate(originals,working,args.rollback,node)
    changed={name:text.encode('utf-8') for name,text in working.items() if text.encode('utf-8')!=originals[name]}
    report={'mode':'rollback' if args.rollback else 'apply' if args.apply else 'dry-run','validatedFiles':len(working),'proposedFiles':len(changed),'proposedAnchors':sum(len(v) for v in ops.values()),'alreadyAtTarget':already,'checks':checks,'wholeBuildShaPinned':False,'schemaMigrationAdded':False,'buildExecuted':False,'databaseOpened':False,'serviceStarted':False,'files':{name:{'liveBeforeSha256':sha(originals[name]),'candidateSha256':sha(working[name].encode('utf-8'))} for name in working},'writtenFiles':0}
    if args.show_diff:
        for name,text in working.items():print(''.join(difflib.unified_diff(originals[name].decode('utf-8').splitlines(keepends=True),text.splitlines(keepends=True),fromfile='a/'+name,tofile='b/'+name)),end='')
    if args.apply or args.rollback:
        # TOCTOU guard after all complete-file checks, before the first mutation.
        for name,raw in originals.items():assert inside(name).read_bytes()==raw,'Live source changed during checks; no source written: '+name
        written=[]
        try:
            for name,data in changed.items():
                file=inside(name);temp=file.with_name(file.name+'.reconciliation-helper.tmp');assert not temp.exists(),'Owned temporary file already exists';temp.write_bytes(data);os.replace(temp,file);written.append(name)
            report['writtenFiles']=len(written)
        except BaseException:
            for name in reversed(written):
                file=inside(name)
                if file.read_bytes()==changed[name]:file.write_bytes(originals[name])
                else:raise RuntimeError('Concurrent write detected; refusing to overwrite '+name)
            raise
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
