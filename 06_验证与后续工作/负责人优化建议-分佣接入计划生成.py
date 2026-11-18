"""Create guarded CM integration artifacts only. NEVER writes business sources."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
R4='04_研发源码/app/r4/'
CLOUD='04_研发源码/app/cloud/'
BASE_COMMIT='9b98ae9'
files={}
def sha(v):return hashlib.sha256(v).hexdigest()
def patch(file,label,old,new,count=1):
    if file not in files:
        raw=(ROOT/file).read_bytes();text=raw.decode('utf-8');files[file]={'path':file,'beforeSha256':sha(raw),'before':text,'candidate':text,'operations':[]}
    f=files[file];eol='\r\n' if '\r\n' in f['before'] else '\n';old=old.replace('\n',eol);new=new.replace('\n',eol)
    assert f['candidate'].count(old)==count,(file,label,f['candidate'].count(old),count)
    f['operations'].append({'label':label,'anchor':old,'replacement':new,'expectedCount':count})
    f['candidate']=f['candidate'].replace(old,new)

server=R4+'backend/server.py';commerce=R4+'backend/commerce.py';cloud=CLOUD+'lib/eastern-api.ts';co=CLOUD+'lib/commerce-api.ts'
patch(server,'import CM with supported module-loader fallback','try:\n    from creator import Creator, init_schema as init_creator_schema', '''try:
    from commission import Commission, init_schema as init_commission_schema
except ModuleNotFoundError:
    import importlib.util
    _commission_spec=importlib.util.spec_from_file_location('eastern_commission',Path(__file__).with_name('commission.py'))
    _commission_module=importlib.util.module_from_spec(_commission_spec);_commission_spec.loader.exec_module(_commission_module)
    Commission,init_commission_schema=_commission_module.Commission,_commission_module.init_schema
try:
    from creator import Creator, init_schema as init_creator_schema''')
patch(server,'initialize after unified commerce/membership','            init_membership_schema(db)','            init_membership_schema(db)\n            init_commission_schema(db)')
patch(server,'route before commerce and generic admin','            commerce_result = Commerce(store, self, ApiError, rate_limit).route(method, path)', '''            commission_result = Commission(store, self, ApiError, rate_limit).route(method, path)
            if commission_result is not None:
                return commission_result
            commerce_result = Commerce(store, self, ApiError, rate_limit).route(method, path)''')
patch(server,'own staff-only access metadata on auth status', "                return {'user': public_user(self.user), 'setupRequired': setup}", '''                    commission_grant = db.execute('SELECT permission FROM commission_grants WHERE user_id=?',(self.user['id'],)).fetchone() if self.user and self.user['role'] in ('operator','reviewer') else None
                commission_permission = 'admin' if self.user and self.user['role']=='admin' else commission_grant['permission'] if commission_grant else None
                return {'user': public_user(self.user), 'setupRequired': setup, 'commissionPermission': commission_permission}''')
patch(cloud,'import CM API',"import {initMembership,membershipRoute} from './membership-lifecycle';", "import {initMembership,membershipRoute} from './membership-lifecycle';\nimport {initCommission,commissionRoute} from './commission-api';")
patch(cloud,'initialize CM after existing membership','await initMembership(this);await initPrivacy(this);','await initMembership(this);await initCommission(this);await initPrivacy(this);')
anchor="const commerceResult=await commerceRoute(this,p,m,fail);"
if anchor not in (ROOT/cloud).read_text(encoding='utf-8'):
    # Current gate uses snake-style local names; record the exact actual segment.
    text=(ROOT/cloud).read_text(encoding='utf-8');match=re.search(r'const (\w+)=await commerceRoute\(this,p,m,fail\);',text);assert match;anchor=match.group(0)
patch(cloud,'route CM before existing commerce',anchor,"const commissionResult=await commissionRoute(this,p,m,fail);if(commissionResult!==undefined)return commissionResult;"+anchor)
patch(cloud,'own staff-only access metadata',"if(p==='/api/auth/status'&&m==='GET')return {user:pubUser(this.user),setupRequired:false};", "if(p==='/api/auth/status'&&m==='GET')return {user:pubUser(this.user),setupRequired:false,commissionPermission:this.user?.role==='admin'?'admin':['operator','reviewer'].includes(this.user?.role)?(await this.one('SELECT permission FROM commission_grants WHERE user_id=?',this.user.id))?.permission||null:null};")
patch(commerce,'import CM derivation helpers','HOLD_MS = 15 * 60 * 1000', '''try:
    from commission import snapshot_order as commission_snapshot_order, sync_commission_order as commission_sync_order
except ModuleNotFoundError:
    import importlib.util
    _commission_spec=importlib.util.spec_from_file_location('eastern_commerce_commission',__import__('pathlib').Path(__file__).with_name('commission.py'))
    _commission_module=importlib.util.module_from_spec(_commission_spec);_commission_spec.loader.exec_module(_commission_module)
    commission_snapshot_order,commission_sync_order=_commission_module.snapshot_order,_commission_module.sync_commission_order

HOLD_MS = 15 * 60 * 1000''')
patch(commerce,'capture in SAME creation transaction after membership snapshot','            if lifecycle:lifecycle.capture_order_snapshots(db,self.uid,oid,snapshots)', '            if lifecycle:lifecycle.capture_order_snapshots(db,self.uid,oid,snapshots)\n            commission_snapshot_order(db,oid)')
patch(commerce,'best-effort derivative at all authorized order return paths','    def order(self, db, row):', '''    def commission_processing(self, db, row):
        opened=False
        try:
            db.execute('SAVEPOINT commission_derive');opened=True
            result=commission_sync_order(db,row['id'])
            rows=db.execute('SELECT status FROM commission_ledger WHERE order_id=?',(row['id'],)).fetchall()
            db.execute('RELEASE SAVEPOINT commission_derive');opened=False
            if not result.get('synced'):
                return {'status':result.get('reason','unavailable'),'retryAvailable':False,'sandboxOnly':True,'actualPaid':False}
            paid=row['payment_status'] in ('paid','partially_refunded','refunded')
            return {'status':'awaiting_payment' if not paid else 'waiting_facts' if any(x['status']=='waiting_facts' for x in rows) else 'synchronized','ledgerItemCount':len(rows),'retryAvailable':False,'sandboxOnly':True,'actualPaid':False}
        except Exception:
            if opened:
                try:
                    db.execute('ROLLBACK TO SAVEPOINT commission_derive');db.execute('RELEASE SAVEPOINT commission_derive')
                except Exception:
                    pass
            return {'status':'sync_pending','retryAvailable':True,'retryAction':'refresh-order','sandboxOnly':True,'actualPaid':False}

    def order(self, db, row):''')
patch(commerce,'include truthful processing receipt', "return {'membershipProcessing':membership_processing,'id': row['id']", "return {'commissionProcessing':self.commission_processing(db,row),'membershipProcessing':membership_processing,'id': row['id']")
patch(co,'import snapshot and derivative helper',"import {initMembership,MembershipLifecycle} from './membership-lifecycle';", "import {initMembership,MembershipLifecycle} from './membership-lifecycle';\nimport {commissionSnapshotStatements,syncCommissionOrder} from './commission-api';")
patch(co,'snapshot statements combined with existing membership SAME batch','  if(lifecycle)ops.push(...lifecycle.captureStatements(owner,oid,preparedLines,snapshots));','  if(lifecycle)ops.push(...lifecycle.captureStatements(owner,oid,preparedLines,snapshots));\n  ops.push(...commissionSnapshotStatements(a,oid));')
patch(co,'committed-commerce safe derivative', ' const order=async(r:any)=>{', ''' const commissionProcessing=async(r:any):Promise<any>=>{
  try{const result=await syncCommissionOrder(a,r.id),rows=await a.all('SELECT status FROM commission_ledger WHERE order_id=?',r.id);if(!result.synced)return {status:result.reason||'unavailable',retryAvailable:false,sandboxOnly:true,actualPaid:false};return {status:!['paid','partially_refunded','refunded'].includes(r.payment_status)?'awaiting_payment':rows.some((x:any)=>x.status==='waiting_facts')?'waiting_facts':'synchronized',ledgerItemCount:rows.length,retryAvailable:false,sandboxOnly:true,actualPaid:false};}
  catch{try{await a.audit('commission.sync.pending',r.id,'统一交易事实保留；派生佣金可刷新重试，不重复付款或退款。');}catch{}return {status:'sync_pending',retryAvailable:true,retryAction:'refresh-order',sandboxOnly:true,actualPaid:false};}
 };
 const order=async(r:any)=>{''')
patch(co,'truthful receipt on paid/refund/fulfill/GET/replay serializer','return {membershipProcessing,id:r.id,ownerId:r.owner,','return {commissionProcessing:await commissionProcessing(r),membershipProcessing,id:r.id,ownerId:r.owner,')

admin=R4+'time-bank-admin.html'
old="function allowedNavs(user=state.user){return Object.keys(labels).filter(k=>user?.role==='admin'||user?.role==='operator'&&!['users','settings','moderation','commerce','privacy','aiGateway','memberSubscriptions'].includes(k)||user?.role==='reviewer'&&['dashboard','posts','audits','creators','creatorReviews'].includes(k));}"
new="function allowedNavs(user=state.user){const cmAllowed=user?.role==='admin'||['operator','reviewer'].includes(user?.role)&&['business','finance','support'].includes(state.commissionPermission);return Object.keys(labels).filter(k=>k==='commission'?cmAllowed:user?.role==='admin'||user?.role==='operator'&&!['users','settings','moderation','commerce','privacy','aiGateway','memberSubscriptions','commission'].includes(k)||user?.role==='reviewer'&&['dashboard','posts','audits','creators','creatorReviews'].includes(k));}"
patch(admin,'default denied, explicit staff grant navigation',old,new)
patch(admin,'clear access receipt on identity invalidation','Object.assign(state,{user:null,items:[],editing:null,settings:null,records:null,analytics:null,','Object.assign(state,{user:null,commissionPermission:null,items:[],editing:null,settings:null,records:null,analytics:null,')
patch(admin,'authoritative status receipt before shell', "state.user=d.user;if(state.user&&['admin','operator','reviewer'].includes(state.user.role))shell();", "state.user=d.user;state.commissionPermission=d.commissionPermission||null;if(state.user&&['admin','operator','reviewer'].includes(state.user.role))shell();")
patch(admin,'login repeats authoritative bootstrap for fine-grained permission','return;}shell();}catch(error){if(authCurrent(loginEpoch)', 'return;}await authBootstrap();}catch(error){if(authCurrent(loginEpoch)')
patch(admin,'new source marker before bootstrap','/*__MEMBERSHIP_ADMIN__*/','/*__MEMBERSHIP_ADMIN__*/\n/*__COMMISSION_ADMIN__*/')
build=R4+'build.py';prepare=CLOUD+'prepare.py'
patch(build,'CSS inclusion',"'membership-lifecycle-ui.css'])","'membership-lifecycle-ui.css','commission-center.css'])")
patch(build,'APP module before i18n finalization',"'membership-lifecycle-ui.js','i18n-ui.js'","'membership-lifecycle-ui.js','commission-center.js','i18n-ui.js'")
patch(build,'admin injection',".replace('/*__MEMBERSHIP_ADMIN__*/',(ROOT/'membership-lifecycle-admin.js').read_text(encoding='utf-8'))", ".replace('/*__MEMBERSHIP_ADMIN__*/',(ROOT/'membership-lifecycle-admin.js').read_text(encoding='utf-8')).replace('/*__COMMISSION_ADMIN__*/',(ROOT/'commission-admin.js').read_text(encoding='utf-8'))")
patch(prepare,'Cloud admin injection',".replace('/*__MEMBERSHIP_ADMIN__*/',(source/'membership-lifecycle-admin.js').read_text(encoding='utf-8'))", ".replace('/*__MEMBERSHIP_ADMIN__*/',(source/'membership-lifecycle-admin.js').read_text(encoding='utf-8')).replace('/*__COMMISSION_ADMIN__*/',(source/'commission-admin.js').read_text(encoding='utf-8'))")
profile=R4+'frame-home-profile.js'
anchor="${flRow('clock',t('Time bank','时间银行'),t('Your actual time, in one place.','记录真实停留，回看日常累积。'),'timeBank')}"
link="${flRow('report',flText('My commission reports','我的分佣报表','我的分佣報表','རང་གི་བགོ་འགྲེམ་རྩིས་ཐོ།'),flText('My account · sandbox bookkeeping','本人账号 · 沙箱记账','本人帳號 · 沙箱記帳','རང་གི་རྩིས་ཐོ། ཚོད་ལྟའི་རྩིས་ཐོ།'),'commissionCenter')}"
patch(profile,'personal account real destination',anchor,anchor+link)
creator=R4+'creator-center.html'
anchor='<a href="/experience">返回东方智慧 APP '
patch(creator,'creator real account report destination',anchor,'<a href="/experience?page=commissionCenter">本人分佣报表（沙箱记账）</a>'+anchor)
nav=R4+'navigation-back.js'
patch(nav,'back hierarchy retains profile', 'const ewNavigation={', "ewNavigationDefaults.commissionCenter='profile';\nconst ewNavigation={")
ui=R4+'commerce-ui.js'
notice='''function coCommissionProcessing(o){const p=o.commissionProcessing;if(!p||p.status==='awaiting_payment')return '';const pending=p.status==='sync_pending',missing=p.status==='missing_creation_snapshot';return `<section class="co-commission-processing"><p>${pending?coText('The payment/refund record is retained. Commission synchronization is pending; retrying does not charge again.','付款/退款事实已保留，分佣同步待处理；重试不会再次扣款。','付款/退款事實已保留，分佣同步待處理；重試不會再次扣款。','དངུལ་སྤྲོད་ཟིན་ཐོ་ཉར་ཡོད། བགོ་དངུལ་མཐུན་སྒྲིག་སྒུག་པ།'):missing?coText('This historical order has no commission snapshot. Current rules will not be applied retrospectively.','此历史订单没有成交时分佣快照，不会按当前规则补算。','此歷史訂單沒有成交時分佣快照，不會依目前規則補算。','མངགས་ཐོ་རྙིང་པ་ལ་བགོ་འགྲེམ་སྒྲིག་གཞི་མེད།'):p.status==='waiting_facts'?coText('Commission bookkeeping awaits confirmed fee facts. No real transfer has occurred.','分佣记账仍待费用事实确认，未发生真实转账。','分佣記帳仍待費用事實確認，未發生真實轉帳。','གྲོན་དངུལ་ངོས་ལེན་སྒུག་པ། དངུལ་མ་བསྐུར།'):coText('Sandbox commission facts were checked. This is separate from settlement and real payments.','沙箱分佣事实已核对，与结算记账和真实付款分别处理。','沙箱分佣事實已核對，與結算記帳及真實付款分別處理。','ཚོད་ལྟའི་བགོ་དངུལ་ཞིབ་བཤེར། དངོས་དངུལ་མ་བསྐུར།')}</p>${pending?`<button class="btn secondary full" type="button" data-commerce-action="refresh">${coText('Retry commission synchronization','重试分佣同步','重試分佣同步','བསྐྱར་དུ་མཐུན་སྒྲིག')}</button>`:''}</section>`;}
function coOrderPage(){'''
patch(ui,'owner-visible derivative failure/retry status','function coOrderPage(){',notice)
patch(ui,'receipt inside actual order view','${coAftersaleHistory(o)}','${coAftersaleHistory(o)}${coCommissionProcessing(o)}')

exports={
'commissionLedger':"SELECT id,order_id,item_id,rule_id,rule_version,currency,quantity,refunded_quantity,base_minor,amount_minor,net_minor,status,freeze_until,payment_event,json_extract(data,'$.rule') AS rule_snapshot,json_extract(data,'$.orderItem') AS order_item,created,updated FROM commission_ledger WHERE beneficiary=?",
'commissionAdjustments':"SELECT id,ledger_id,currency,refunded_quantity,amount_minor,target_minor,status,reason,source_event,created FROM commission_adjustments WHERE beneficiary=?",
'commissionStatements':"SELECT id,currency,total_minor,status,version,period_from,period_to,created,updated FROM commission_statements WHERE beneficiary=?",
'commissionStatementLines':"SELECT l.statement_id,l.kind,l.source_id,l.amount_minor FROM commission_statement_lines l JOIN commission_statements s ON s.id=l.statement_id WHERE s.beneficiary=?",
'commissionPaymentSummary':"SELECT p.id,p.statement_id,p.status,json_extract(p.data,'$.actualPaid') AS actual_paid,json_extract(p.data,'$.proofVerified') AS proof_verified,p.created FROM commission_payments p JOIN commission_statements s ON s.id=p.statement_id WHERE s.beneficiary=?",
'commissionOwnAttributions':"SELECT id,code,priority,created,valid_until FROM commission_attributions WHERE owner=?",
'commissionOwnInvitations':"SELECT code,priority,status,valid_until,created FROM commission_invites WHERE beneficiary=?",
}
privacy=R4+'backend/privacy.py';prcloud=CLOUD+'lib/privacy-api.ts'
anchor="            'aiGatewayWallet': ('SELECT balance,reserved,updated FROM ai_gateway_wallets WHERE owner=?',),"
insert='\n'.join('            '+repr(k)+': ('+repr(v)+',),' for k,v in exports.items())
patch(privacy,'explicit owner/beneficiary export whitelist',anchor,insert+'\n'+anchor)
anchor="   aiGatewayWallet:'SELECT balance,reserved,updated FROM ai_gateway_wallets WHERE owner=?',"
insert='\n'.join('   '+k+':'+json.dumps(v,ensure_ascii=False)+',' for k,v in exports.items())
patch(prcloud,'explicit owner/beneficiary export whitelist',anchor,insert+'\n'+anchor)
patch(privacy,'financial retention is explicit, no ledger deletion',"'commerce-ledger', 'ai-request-quota-metadata'", "'commerce-ledger', 'commission-ledger', 'ai-request-quota-metadata'")
patch(prcloud,'financial retention is explicit, no ledger deletion',"'commerce-ledger','ai-request-quota-metadata'", "'commerce-ledger','commission-ledger','ai-request-quota-metadata'")

plan={'baseCommit':BASE_COMMIT,'scope':'CM integration only; root applies after previous module gate','files':[],'newSourcePrerequisites':json.loads((ROOT/'06_验证与后续工作/负责人优化建议-分佣模块准备记录.json').read_text(encoding='utf-8-sig'))['sourceSha256'],'exports':exports,'notExecuted':True}
diff=[]
for name,f in files.items():
    assert f['candidate']!=f['before']
    if name.endswith('.py'):ast.parse(f['candidate'],filename=name)
    reversed_text=f['candidate']
    for op in reversed(f['operations']):
        assert reversed_text.count(op['replacement'])==op['expectedCount'],('reverse ambiguity',name,op['label'])
        reversed_text=reversed_text.replace(op['replacement'],op['anchor'])
    assert reversed_text==f['before']
    committed=subprocess.run(['git','show',BASE_COMMIT+':'+name],cwd=ROOT,capture_output=True,check=True).stdout.decode('utf-8')
    assert committed.replace('\r\n','\n')==f['before'].replace('\r\n','\n'),('not membership frozen baseline',name)
    out={k:v for k,v in f.items() if k not in ('before','candidate')};out['afterSha256']=sha(f['candidate'].encode('utf-8'));plan['files'].append(out)
    diff.extend(difflib.unified_diff(f['before'].splitlines(keepends=True),f['candidate'].splitlines(keepends=True),fromfile='a/'+name,tofile='b/'+name))
outdir=ROOT/'06_验证与后续工作'
(outdir/'负责人优化建议-分佣接入计划.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
(outdir/'负责人优化建议-分佣接入待审.patch').write_text(''.join(diff),encoding='utf-8')
print(json.dumps({'plannedFiles':len(plan['files']),'anchors':sum(len(f['operations']) for f in plan['files']),'businessSourcesModified':False}))
