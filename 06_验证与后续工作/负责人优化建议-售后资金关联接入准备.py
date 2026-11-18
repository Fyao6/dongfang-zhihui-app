"""Exact, default-dry after-sales-finance integration plan. No build, database or network operations.
Run without flags to review 06 plan JSON. --apply edits only the listed source files after all anchors/preflights pass.
Requires prior actual retention/closure integration; never creates a refund or touches original financial facts.
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
imports="""# after-sales-finance-module:v1
try:
    from after_sales_finance import AfterSalesFinance, init_schema as init_after_sales_finance_schema
except ModuleNotFoundError:
    import importlib.util as _asf_import
    _asf_spec=_asf_import.spec_from_file_location('eastern_after_sales_finance',Path(__file__).with_name('after_sales_finance.py'))
    _asf_module=_asf_import.module_from_spec(_asf_spec);_asf_spec.loader.exec_module(_asf_module)
    AfterSalesFinance,init_after_sales_finance_schema=_asf_module.AfterSalesFinance,_asf_module.init_schema

"""
patch(server,'class Store:',imports+'class Store:','Python import fallback')
def dependency_patch(file,old,new,label):
    raw=(ROOT/file).read_text(encoding='utf-8')
    if old not in raw and new not in raw:
        pending.append({'path':file,'requiredAnchor':old,'label':label})
        return
    patch(file,old,new,label)
dependency_patch(server,'            init_account_closure_schema(db)','            init_account_closure_schema(db)\n            init_after_sales_finance_schema(db)','Python finance initialized after actual closure lifecycle')
old='            after_sales_result = AfterSales(store, self, ApiError, rate_limit).route(method, path)'
patch(server,old,"""            after_sales_finance_result = AfterSalesFinance(store, self, ApiError, rate_limit).route(method, path)
            if after_sales_finance_result is not None:
                return after_sales_finance_result
"""+old,'Python owner/admin real handler route')
api='04_研发源码/app/cloud/lib/eastern-api.ts'
old="import {initAfterSales,afterSalesRoute,afterSalesReady} from './after-sales';"
patch(api,old,old+"\nimport {initAfterSalesFinance,afterSalesFinanceRoute} from './after-sales-finance';",'Cloud independent import')
dependency_patch(api,'await initAccountClosure(this);','await initAccountClosure(this);await initAfterSalesFinance(this);','Cloud finance after final actual closure lifecycle init')
old='const afterSales=await afterSalesRoute(this,p,m,fail);'
patch(api,old,'const afterSalesFinance=await afterSalesFinanceRoute(this,p,m,fail);if(afterSalesFinance!==undefined)return afterSalesFinance;'+old,'Cloud real owner/admin route')
build='04_研发源码/app/r4/build.py'
patch(build,"'after-sales-ui.css'","'after-sales-ui.css','after-sales-finance.css'",'APP finance scoped CSS list')
patch(build,"'after-sales-ui.js'","'after-sales-ui.js','after-sales-finance-money.js','after-sales-finance-ui.js'",'APP exact money and owner components')
old="js+='\\nAfterSalesUI.install();\\n'"
patch(build,old,"js+='\\nAfterSalesUI.install();\\nAfterSalesFinanceUI.install();\\n'",'APP explicit install after original afterSales install')
admin='04_研发源码/app/r4/time-bank-admin.html'
patch(admin,'/*__AFTER_SALES_ADMIN__*/','/*__AFTER_SALES_ADMIN__*/\n/*__AFTER_SALES_FINANCE_ADMIN__*/','Admin placeholder before actual bootstrap')
for file,prefix in [(build,'ROOT'),('04_研发源码/app/cloud/prepare.py','source')]:
    old=".replace('/*__AFTER_SALES_ADMIN__*/',("+prefix+"/'after-sales-admin.js').read_text(encoding='utf-8')+'\\nAfterSalesAdmin.install();')"
    new=old+".replace('/*__AFTER_SALES_FINANCE_ADMIN__*/',("+prefix+"/'after-sales-finance-money.js').read_text(encoding='utf-8')+'\\n'+("+prefix+"/'after-sales-finance-admin.js').read_text(encoding='utf-8')+'\\nAfterSalesFinanceAdmin.install();')"
    patch(file,old,new,'Admin money/component explicit install '+prefix)
    variable='admin_source' if prefix=='ROOT' else 'admin'
    old=variable+"="+variable+".replace('</style>',("+prefix+"/'card-service.css').read_text(encoding='utf-8')+'</style>',1)"
    new=old+"\n"+variable+"="+variable+".replace('</style>',("+prefix+"/'after-sales-finance.css').read_text(encoding='utf-8')+'</style>',1)"
    patch(file,old,new,'Admin isolated CSS '+prefix)
exports={
'afterSalesFinanceHeads':"SELECT case_id,order_id,environment,currency,version,approval_id,last_action,created,updated FROM after_sales_finance_heads WHERE owner=?",
'afterSalesFinanceActions':"SELECT id,case_id,environment,currency,kind,expected_version,json_extract(data,'$.reason') AS reason,json_extract(data,'$.ruleLabel') AS rule_label,created FROM after_sales_finance_actions WHERE owner=?",
'afterSalesFinanceTargets':"SELECT approval_id,case_item_id,case_id,approved_minor FROM after_sales_finance_targets WHERE owner=?",
'afterSalesFinanceLinks':"SELECT id,action_id,case_id,case_item_id,environment,currency,refund_event_id,order_item_id,amount_minor,created FROM after_sales_finance_links WHERE owner=?",
'afterSalesFinanceReversals':"SELECT id,action_id,link_id,case_id,amount_minor,created FROM after_sales_finance_reversals WHERE owner=?"
}
privacy='04_研发源码/app/r4/backend/privacy.py'
old="            'membershipSubscriptions':"
patch(privacy,old,''.join('            '+repr(k)+': ('+repr(v)+',),\n' for k,v in exports.items())+old,'Python 5-table owner-only financial metadata export whitelist')
privacy_ts='04_研发源码/app/cloud/lib/privacy-api.ts'
old='   membershipSubscriptions:'
patch(privacy_ts,old,''.join('   '+k+':'+json.dumps(v,ensure_ascii=False)+',\n' for k,v in exports.items())+old,'Cloud owner-only financial metadata whitelist')
# Both legacy serializers inherit their existing owner/admin route authorization.
# The summary is read-only, same-case scoped, and shares the exact projection used by the new endpoint.
old_as='04_研发源码/app/r4/backend/after_sales.py'
finance_import="""try:
    from after_sales_finance import case_finance_summary
except ModuleNotFoundError:
    import importlib.util as _asf_summary_import
    from pathlib import Path as _asf_summary_path
    _asf_summary_spec=_asf_summary_import.spec_from_file_location('eastern_after_sales_finance_summary',_asf_summary_path(__file__).with_name('after_sales_finance.py'))
    _asf_summary_module=_asf_summary_import.module_from_spec(_asf_summary_spec);_asf_summary_spec.loader.exec_module(_asf_summary_module)
    case_finance_summary=_asf_summary_module.case_finance_summary

"""
patch(old_as,"DEFAULT = {'sandboxEnabled':",finance_import+"DEFAULT = {'sandboxEnabled':",'Original Python serializer pure-summary import')
patch(old_as,"'caseRefundLinked':False,'caseRefundConfirmed':False,","**case_finance_summary(db,row['id'],row['owner'],row['order_id']),",'Original Python money uses the same case-scoped net projection')
old_notice='仅原统一订单的累计沙箱退款事实，不代表本售后申请已退款或真实到账。'
new_notice='订单累计金额和事件来自原统一交易；本申请关联状态仅表示明确批准目标与已有沙箱退款的净金额匹配，不代表真实到账。物流独立，未明确分配的累计退款不归属本申请。'
patch(old_as,old_notice,new_notice,'Original Python separates order facts from sandbox case matching')
old_as_ts='04_研发源码/app/cloud/lib/after-sales.ts'
patch(old_as_ts,'export async function initAfterSales(a:any){',"import {caseFinanceSummary} from './after-sales-finance';\nexport async function initAfterSales(a:any){",'Original Cloud serializer pure-summary import')
patch(old_as_ts,'caseRefundLinked:false,caseRefundConfirmed:false,','...await caseFinanceSummary(this.a,row.id,row.owner,row.order_id),','Original Cloud money shares same case-scoped net projection')
patch(old_as_ts,old_notice,new_notice,'Original Cloud separates original order facts from case matching')
if args.apply and pending:raise RuntimeError('Required closure integration anchors are not yet present; no source was written: '+json.dumps(pending,ensure_ascii=False))
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
plan={'at':stamp,'mode':'apply' if args.apply else 'dry-run','productionEnabled':False,'newModuleDefault':'approval null; production false; no automatic allocation','pendingDependencyAnchors':pending,'anchors':anchors,
      'sourceChanges':[{k:v for k,v in x.items() if k not in ('originalBytes','proposedBytes')} for x in files],
      'hashing':'SHA256 of exact original/proposed UTF-8 bytes; no read_text newline normalization',
      'backupPolicy':'Flat original-byte backup files and mapping JSON in existing 06 directory; no subdirectory/version directory',
      'doesNotRun':['build','database migration against original DB','local service','public deployment','real payment/refund','carrier requests'],
      'financialEffects':'Only new attribution tables and audit rows; original refund/stock/entitlement/member/commission/logistics facts are never written.'}
out=ROOT/'06_验证与后续工作'
report=out/'负责人优化建议-售后资金关联接入计划.json'
if args.apply:
    # Preflight all raw bytes before any backup or source write.
    for item in files:
        if (ROOT/item['path']).read_bytes()!=item['originalBytes']:raise RuntimeError('Source bytes changed during preflight; no source applied.')
    backup_map=out/('负责人优化建议-售后资金关联接入备份映射-'+stamp+'.json')
    backups=[]
    for index,item in enumerate(files,1):
        backup=out/('售后资金关联接入前-'+stamp+'-'+str(index).zfill(2)+'-'+Path(item['path']).name+'.bak')
        temporary=out/('售后资金关联接入写入-'+stamp+'-'+str(index).zfill(2)+'.tmp')
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
