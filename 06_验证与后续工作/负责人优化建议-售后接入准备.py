"""Exact, default-dry after-sales integration plan. No build, database or network operations.
Run without flags to review 06 plan JSON. --apply edits only the listed source files after all anchors/preflights pass.
The new module remains sandbox-disabled by default. Existing historical idempotent legacy returns stay before the new guard.
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
imports="""# after-sales-module:v1
try:
    from after_sales import AfterSales, init_schema as init_after_sales_schema, service_ready as after_sales_service_ready
except ModuleNotFoundError:
    import importlib.util as _after_sales_import
    _after_sales_spec=_after_sales_import.spec_from_file_location('eastern_after_sales',Path(__file__).with_name('after_sales.py'))
    _after_sales_module=_after_sales_import.module_from_spec(_after_sales_spec);_after_sales_spec.loader.exec_module(_after_sales_module)
    AfterSales,init_after_sales_schema,after_sales_service_ready=_after_sales_module.AfterSales,_after_sales_module.init_schema,_after_sales_module.service_ready

"""
patch(server,'class Store:',imports+'class Store:','Python import fallback')
patch(server,'            init_commerce_schema(db)','            init_commerce_schema(db)\n            init_after_sales_schema(db)','Python same owned Store schema initialization')
old='            commerce_result = Commerce(store, self, ApiError, rate_limit).route(method, path)'
new="""            after_sales_result = AfterSales(store, self, ApiError, rate_limit).route(method, path)
            if after_sales_result is not None:
                return after_sales_result
"""+old
patch(server,old,new,'Python route uses real authenticated handler')
old="cardServiceReady=bool(store.setting('card_service').get('enabled'))"
patch(server,old,old+', afterSalesServiceReady=after_sales_service_ready(store)','Python public sandbox readiness only')

api='04_研发源码/app/cloud/lib/eastern-api.ts'
old="import {initCardService,cardServiceRoute,cardMediaAllowed} from './card-service';"
patch(api,old,old+"\nimport {initAfterSales,afterSalesRoute,afterSalesReady} from './after-sales';",'Cloud import')
old='await initCommerce(this);'
patch(api,old,old+'await initAfterSales(this);','Cloud initialize after existing unified commerce tables')
old='const cards=await cardServiceRoute(this,p,m,fail);'
patch(api,old,'const afterSales=await afterSalesRoute(this,p,m,fail);if(afterSales!==undefined)return afterSales;'+old,'Cloud route')
old="cardServiceReady:!!(await this.setting('card_service')).enabled"
patch(api,old,old+',afterSalesServiceReady:await afterSalesReady(this)','Cloud public sandbox readiness only')

commerce='04_研发源码/app/r4/backend/commerce.py'
old="            remaining=db.execute('SELECT coalesce(sum(quantity-refunded_quantity),0) FROM commerce_order_items WHERE order_id=?',(oid,)).fetchone()[0]"
new="""            # after-sales-legacy-guard:v1; inside the existing BEGIN IMMEDIATE, after historical replay.
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='after_sales_cases'").fetchone() and db.execute("SELECT 1 FROM after_sales_cases WHERE owner=? AND order_id=? AND state!='rejected' LIMIT 1",(self.uid,oid)).fetchone():
                self.fail(409,'本单已有按项售后申请，请到该申请继续处理。')
"""+old
patch(commerce,old,new,'Python legacy/new claims mutually exclude inside original transaction')

commerce_ts='04_研发源码/app/cloud/lib/commerce-api.ts'
old="import {commissionSnapshotStatements,syncCommissionOrder} from './commission-api';"
patch(commerce_ts,old,old+"\nimport {legacyAfterSalesInsertGuard} from './after-sales';",'Cloud legacy guard import without changing original ledger')
old="return order(r);}const stamp=now(),id=uid();let out;try{out=await batch([a.stmt(\"INSERT INTO commerce_aftersale_requests SELECT"
new="return order(r);}const legacyGuard=await legacyAfterSalesInsertGuard(a,owner,oid);const stamp=now(),id=uid();let out;try{out=await batch([a.stmt(\"INSERT INTO commerce_aftersale_requests SELECT"
patch(commerce_ts,old,new,'Cloud prepare atomic legacy INSERT predicate after replay')
old='WHERE order_id=?)",id,owner,\'sandbox\',oid,requestId,token,reason,quantity,\'pending\',stamp,stamp,oid,owner,quantity,oid),a.stmt("UPDATE commerce_orders SET aftersale_status='
new='WHERE order_id=?)"+legacyGuard.sql,id,owner,\'sandbox\',oid,requestId,token,reason,quantity,\'pending\',stamp,stamp,oid,owner,quantity,oid,...legacyGuard.bindings),a.stmt("UPDATE commerce_orders SET aftersale_status='
patch(commerce_ts,old,new,'Cloud same-batch legacy/new claims guard; no check-then-insert race')

platform='04_研发源码/app/r4/platform.js'
old='cardServiceReady:!!d.cardServiceReady,'
patch(platform,old,old+'afterSalesReady:!!d.afterSalesServiceReady,','Frontend actual server readiness')

build='04_研发源码/app/r4/build.py'
patch(build,"'privacy-saved.css']","'privacy-saved.css','after-sales-ui.css']",'APP scoped CSS')
patch(build,"'privacy-saved.js','i18n-ui.js'","'privacy-saved.js','after-sales-ui.js','i18n-ui.js'",'APP optional UI source list')
old="bundled_node=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'"
patch(build,old,"# after-sales-ui-install:v1\njs+='\\nAfterSalesUI.install();\\n'\n"+old,'APP explicit UI install after all account/commerce definitions')
old=".replace('/*__COMMISSION_ADMIN__*/',(ROOT/'commission-admin.js').read_text(encoding='utf-8'))"
new=old+".replace('/*__AFTER_SALES_ADMIN__*/',(ROOT/'after-sales-admin.js').read_text(encoding='utf-8')+'\\nAfterSalesAdmin.install();')"
patch(build,old,new,'APP admin source + explicit install')
prepare='04_研发源码/app/cloud/prepare.py'
old=".replace('/*__COMMISSION_ADMIN__*/',(source/'commission-admin.js').read_text(encoding='utf-8'))"
new=old+".replace('/*__AFTER_SALES_ADMIN__*/',(source/'after-sales-admin.js').read_text(encoding='utf-8')+'\\nAfterSalesAdmin.install();')"
patch(prepare,old,new,'Cloud admin source + explicit install')
admin='04_研发源码/app/r4/time-bank-admin.html'
old='/*__COMMISSION_ADMIN__*/'
patch(admin,old,old+'\n/*__AFTER_SALES_ADMIN__*/','Explicit admin module placeholder before existing bootstrap')

exports={
 'afterSalesCases':"SELECT id,environment,order_id,type,reason,rule_version,state,version,created,updated FROM after_sales_cases WHERE owner=?",
 'afterSalesItems':"SELECT id,case_id,order_item_id,sku_id,type,quantity,received_quantity,restocked_quantity,snapshot_data FROM after_sales_items WHERE owner=?",
 'afterSalesActions':"SELECT id,case_id,kind,json_extract(data,'$.reason') AS reason,json_extract(data,'$.note') AS note,created FROM after_sales_actions WHERE owner=?",
 'afterSalesShipments':"SELECT id,case_id,carrier,tracking_number,created FROM after_sales_shipments WHERE owner=?",
 'afterSalesInspections':"SELECT i.id,i.case_id,i.receipt_reference,i.note,i.created FROM after_sales_inspections i JOIN after_sales_cases c ON c.id=i.case_id WHERE c.owner=?",
 'afterSalesReceiptItems':"SELECT i.id,i.inspection_id,i.case_item_id,i.received_quantity,i.restock_quantity,i.condition,i.created FROM after_sales_inspection_items i JOIN after_sales_items x ON x.id=i.case_item_id WHERE x.owner=?"
}
privacy='04_研发源码/app/r4/backend/privacy.py'
old="            'membershipSubscriptions':"
new=''.join('            '+repr(key)+': ('+repr(sql)+',),\n' for key,sql in exports.items())+old
patch(privacy,old,new,'Python owner-only export whitelist; no credentials, global config or other users')
old="'commerce-ledger', 'commission-ledger'"
patch(privacy,old,"'commerce-ledger', 'after-sales-ledger', 'commission-ledger'",'Python deletion receipt truthfully retains warehouse/financial records')
privacy_ts='04_研发源码/app/cloud/lib/privacy-api.ts'
old='   membershipSubscriptions:'
new=''.join('   '+key+':'+json.dumps(sql,ensure_ascii=False)+',\n' for key,sql in exports.items())+old
patch(privacy_ts,old,new,'Cloud owner-only export whitelist')
old="'commerce-ledger','commission-ledger'"
patch(privacy_ts,old,"'commerce-ledger','after-sales-ledger','commission-ledger'",'Cloud deletion receipt retains audit/warehouse records')

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
plan={'at':stamp,'mode':'apply' if args.apply else 'dry-run','productionEnabled':False,'newModuleDefault':'sandbox disabled','anchors':anchors,
      'sourceChanges':[{k:v for k,v in x.items() if k not in ('originalBytes','proposedBytes')} for x in files],
      'hashing':'SHA256 of exact original/proposed UTF-8 bytes; no read_text newline normalization',
      'backupPolicy':'Flat original-byte backup files and mapping JSON in existing 06 directory; no subdirectory/version directory',
      'doesNotRun':['build','database migration against original DB','local service','public deployment','real payment/refund','carrier requests'],
      'legacyClaims':'Python original BEGIN IMMEDIATE; Cloud original conditional INSERT same D1 batch. Historical replay remains ahead of guard.'}
out=ROOT/'06_验证与后续工作'
report=out/'负责人优化建议-售后接入计划.json'
if args.apply:
    # Preflight all raw bytes before any backup or source write.
    for item in files:
        if (ROOT/item['path']).read_bytes()!=item['originalBytes']:raise RuntimeError('Source bytes changed during preflight; no source applied.')
    backup_map=out/('负责人优化建议-售后接入备份映射-'+stamp+'.json')
    backups=[]
    for index,item in enumerate(files,1):
        backup=out/('售后接入前-'+stamp+'-'+str(index).zfill(2)+'-'+Path(item['path']).name+'.bak')
        temporary=out/('售后接入写入-'+stamp+'-'+str(index).zfill(2)+'.tmp')
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
