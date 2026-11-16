"""Synthetic in-memory financial corruption fixtures; original databases are never opened."""
import ast
import contextlib
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/'04_研发源码/app/r4/backend';sys.path.insert(0,str(BACKEND))
import reconciliation as rc
import membership_lifecycle as membership
import commission

# Reuse the actual unified-commerce fixture setup without its report-writing runner.
fixture_script=Path(__file__).with_name('负责人优化建议-分佣隔离自检.py');tree=ast.parse(fixture_script.read_text(encoding='utf-8'));nodes=[]
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='report' for t in node.targets):break
    nodes.append(node)
scope={'__file__':str(fixture_script),'__name__':'readonly_fixture_setup'};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(fixture_script),'exec'),scope);scope['run']()
base=scope['store'].db;base.execute("UPDATE users SET role='operator' WHERE id='finance'");base.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT NOT NULL)');base.execute("INSERT INTO settings VALUES('membership_lifecycle','{\"sandboxEnabled\":true}')");base.commit();membership.init_schema(base)
scope['store'].setting=lambda key:json.loads(base.execute('SELECT data FROM settings WHERE key=?',(key,)).fetchone()[0]) if base.execute('SELECT 1 FROM settings WHERE key=?',(key,)).fetchone() else {}
sku=base.execute("SELECT id FROM commerce_skus WHERE product_id='p'").fetchone()[0]
member_order=scope['c']('buyer').create_order(dict(requestId='readonly-member-fixture',environment='sandbox',items=[dict(skuId=sku,quantity=1)]));oid=member_order['id'];item=member_order['items'][0];iid=item['itemId'];stamp=time.time_ns()//1_000_000;start=stamp-1000;end=stamp+86400000
base.execute("UPDATE commerce_order_items SET type='membership' WHERE id=?",(iid,));base.commit()
terms={'currency':'USD','firstPriceMinor':item['priceMinor'],'priceVersion':item['priceVersion'],'sandboxOnly':True}
base.execute('INSERT INTO membership_order_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(iid,'buyer','sandbox',oid,'readonly-plan',1,'readonly-group',json.dumps(terms),None,None,None,None,'pending',stamp)) if False else None
# Explicit column lists preserve the real schema's optional/default columns.
base.execute('INSERT INTO membership_order_snapshots(item_id,owner,environment,order_id,plan_id,plan_version,group_id,data,state,created) VALUES(?,?,?,?,?,?,?,?,?,?)',(iid,'buyer','sandbox',oid,'readonly-plan',1,'readonly-group',json.dumps(terms),'pending',stamp))
eid='readonly-member-payment';base.execute('INSERT INTO commerce_payment_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(eid,'buyer','sandbox',oid,'readonly-member-pay','sandbox_pay','TEST',member_order['totalMinor'],'USD','[]','applied',stamp));base.execute("UPDATE commerce_orders SET payment_status='paid',status='completed',fulfillment_status='fulfilled',updated=? WHERE id=?",(stamp,oid))
base.execute('INSERT INTO membership_subscriptions(id,owner,environment,group_id,original_item_id,current_item_id,plan_id,plan_version,status,auto_renew,period_start,period_end,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('readonly-sub','buyer','sandbox','readonly-group',iid,iid,'readonly-plan',1,'active',0,start,end,stamp,stamp))
base.execute("UPDATE membership_order_snapshots SET subscription_id='readonly-sub',payment_event_id=?,period_start=?,period_end=?,state='linked' WHERE item_id=?",(eid,start,end,iid));base.execute('INSERT INTO membership_events VALUES(?,?,?,?,?,?,?,?,?)',('readonly-member-event','buyer','sandbox','readonly-sub','readonly-member-event-request','sandbox_payment','TEST','{}',stamp));commission.sync_commission_order(base,oid);base.commit()
# Add a legitimate waiting_facts entry. Unknown cost is deliberately not zero.
scope['action']('business','/api/admin/commissions/rules','POST',scope['rule'](expectedVersion=3,beneficiary='author2',mode='fixed_per_unit',rateBps=0,fixedMinor=101,basis=dict(deductTax=True,deductShipping=True,deductDiscount=True,deductChannelFee=True)))
unknown=scope['c']('buyer').create_order(dict(requestId='readonly-unknown-facts',environment='sandbox',items=[dict(skuId=sku,quantity=1)]));scope['c']('buyer').pay(unknown['id'],dict(requestId='readonly-unknown-pay'));base.commit()
blob=base.serialize();FIXED_NOW=time.time_ns()//1_000_000

class Store:
    def __init__(self,db):self.db=db
    @contextlib.contextmanager
    def connect(self):
        try:yield self.db;self.db.commit()
        except BaseException:self.db.rollback();raise
class Error(Exception):
    def __init__(self,status,message):super().__init__(message);self.status=status
class Handler:
    def __init__(self,uid='admin'):self.user={'id':uid,'role':'operator'} if uid else None;self.path='/api/admin/reconciliation'
    def require(self):
        if not self.user:raise Error(401,'login')
        return self.user
def fresh():
    db=sqlite3.connect(':memory:');db.deserialize(blob);db.row_factory=sqlite3.Row;return db
def financial_hash(db):
    names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'commerce_%' OR name LIKE 'membership_%' OR name LIKE 'commission_%') ORDER BY name")];value={}
    for name in names:value[name]=sorted(json.dumps(dict(r),sort_keys=True,ensure_ascii=False) for r in db.execute('SELECT * FROM '+name))
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def request(db,uid='admin',path='/api/admin/reconciliation',method='GET'):
    h=Handler(uid);h.path=path;return rc.Reconciliation(Store(db),h,Error,lambda *a:None).route(method,path.split('?')[0])
checks=[];fixture_cases=[]
def case(name,sql=None,expected_code=None,uid='admin',expected_status=None,params=(),assertion=None,path='/api/admin/reconciliation'):
    db=fresh()
    try:
        if sql:db.execute(sql,params);db.commit()
        before=financial_hash(db)
        if expected_status:
            try:request(db,uid);raise AssertionError('expected status '+str(expected_status))
            except Error as e:assert e.status==expected_status
            result=None
        else:
            result=request(db,uid,path=path)
            if expected_code:assert any(f['code']==expected_code for f in result['findings']),(name,expected_code,result['findings'])
            if assertion:assertion(result)
        assert financial_hash(db)==before,name+' changed a financial original table'
        checks.append({'name':name,'passed':True,'financialHashUnchanged':True})
        fixture_cases.append({'name':name,'sql':sql,'params':list(params),'expectedCode':expected_code,'uid':uid,'expectedStatus':expected_status,'path':path})
        return result
    finally:db.close()
def require(v):assert v
report={'checks':checks,'originalDatabaseOpened':False,'database':':memory:','servicesStarted':False,'financialMutationsByReports':False}
try:
    baseline=case('normal historical settled refund and physical fulfillment cause no mismatch',assertion=lambda r:require(r['counts']['errors']==0))
    case('finance has read access',uid='finance',assertion=lambda r:require(r['readOnly']))
    for uid in ['buyer','author','business','support']:case(uid+' cannot view finance snapshot',uid=uid,expected_status=403)
    case('anonymous denied',uid=None,expected_status=401)
    case('cached staff identity downgraded in DB loses access',"UPDATE users SET role='user' WHERE id='finance'",uid='finance',expected_status=403)
    case('order total damage located',"UPDATE commerce_orders SET total_minor=total_minor+1 WHERE id=?",'order_total_minor',params=(oid,))
    case('refund state label cannot override actual refund facts',"UPDATE commerce_orders SET payment_status='paid' WHERE payment_status='partially_refunded'",'payment_refund_state')
    case('payment original amount damage located',"UPDATE commerce_payment_events SET amount_minor=amount_minor+1 WHERE id=?",'payment_original_amount',params=(eid,))
    case('refund event amount damage located',"UPDATE commerce_payment_events SET amount_minor=amount_minor+1 WHERE id=(SELECT id FROM commerce_payment_events WHERE kind='refund' LIMIT 1)",'refund_event_amount')
    case('cumulative refund quantity damage located',"UPDATE commerce_order_items SET refunded_quantity=0 WHERE id=(SELECT item_id FROM commission_ledger WHERE refunded_quantity>0 LIMIT 1)",'refund_cumulative_quantity')
    case('paid entitlement deletion located',"DELETE FROM commerce_entitlements WHERE item_id=?",'paid_item_entitlement_count',params=(iid,))
    case('wrong entitlement remaining located',"UPDATE commerce_entitlements SET remaining=remaining+1 WHERE item_id=?",'entitlement_remaining',params=(iid,))
    case('current subscription plan cannot drift from its paid snapshot',"UPDATE membership_subscriptions SET plan_id='different-plan' WHERE id='readonly-sub'",'subscription_current_snapshot_reference')
    case('current subscription period cannot silently grow beyond paid snapshot',"UPDATE membership_subscriptions SET period_end=period_end+1 WHERE id='readonly-sub'",'subscription_current_snapshot_period')
    case('subscription owner damage located',"UPDATE membership_subscriptions SET owner='other' WHERE id='readonly-sub'",'membership_subscription_reference')
    case('historical membership missing snapshot is not-covered',"DELETE FROM membership_order_snapshots WHERE item_id=?",'historical_membership_snapshot_missing',params=(iid,))
    case('expiry is observed without lifecycle mutation',"UPDATE membership_subscriptions SET period_start=1,period_end=2 WHERE id='readonly-sub'",'membership_effective_state_requires_sync')
    case('commission original amount damage located',"UPDATE commission_ledger SET amount_minor=amount_minor+1 WHERE id=(SELECT id FROM commission_ledger WHERE amount_minor IS NOT NULL LIMIT 1)",'commission_original_math')
    case('commission refund balance damage located',"UPDATE commission_ledger SET net_minor=net_minor+1 WHERE id=(SELECT id FROM commission_ledger WHERE amount_minor IS NOT NULL LIMIT 1)",'commission_refund_balance')
    case('original statement total damage located',"UPDATE commission_statements SET total_minor=total_minor+1 WHERE status='booked'",'statement_original_line_sum')
    db=fresh();link=db.execute("SELECT l.order_id,s.id statement_id FROM commission_statements s JOIN commission_statement_lines x ON x.statement_id=s.id AND x.kind='earning' JOIN commission_ledger l ON l.id=x.source_id WHERE s.status='booked' LIMIT 1").fetchone();db.close()
    case('order filter retains associated whole-statement mismatch',"UPDATE commission_statements SET total_minor=total_minor+1 WHERE id=?",'statement_original_line_sum',params=(link['statement_id'],),path='/api/admin/reconciliation?orderId='+link['order_id'])
    case('unlinked recovery reservation located',"UPDATE commission_adjustments SET status='reserved' WHERE id=(SELECT id FROM commission_adjustments WHERE status='pending_recovery' LIMIT 1)",'recovery_reservation_without_open_statement')
    case('sandbox real-payment claim located',"UPDATE commission_payments SET data=json_set(data,'$.actualPaid',json('true'))",'sandbox_payment_claims_real_transfer')
    case('missing historical commission snapshot remains not-covered',"DELETE FROM commission_snapshots WHERE item_id=?",'historical_commission_snapshot_missing',params=(iid,))
    case('invalid snapshot JSON is explicit',"DROP TRIGGER commission_snapshot_immutable",assertion=lambda r:require(r['counts']['errors']==0))
    db=fresh();db.execute('DROP TRIGGER commission_snapshot_immutable');db.execute("UPDATE commission_snapshots SET data='invalid-json' WHERE item_id=?",(iid,));db.commit();before=financial_hash(db);r=request(db);require(any(f['code']=='commission_snapshot_invalid' for f in r['findings']));require(financial_hash(db)==before);checks.append({'name':'malformed snapshot JSON located without repair','passed':True,'financialHashUnchanged':True});db.close()
    case('unknown fees and unknown ledger amounts are not zero',assertion=lambda r:require(r['totalsByCurrency']['USD']['channelFeeMinor'] is None and r['totalsByCurrency']['USD']['ledgerUnknownAmountCount']>=1))
    case('currencies stay separate and have no grand total',assertion=lambda r:require(set(r['totalsByCurrency'])=={'USD','JPY'} and r['crossCurrencyGrandTotal'] is None))
    db=fresh();before=financial_hash(db)
    for _ in range(100):request(db,'finance')
    require(financial_hash(db)==before);checks.append({'name':'100 refreshes leave all financial original tables identical','passed':True,'financialHashUnchanged':True});db.close()
    db=fresh();db.execute('DROP TABLE commission_payments');db.commit();before=financial_hash(db);r=request(db);require(r['partial'] and not r['sources']['payouts']['exists']);require(r['aggregateCoverage']['bookedStatements'] is False and all(t['bookedStatementMinor'] is None for t in r['totalsByCurrency'].values()));require(financial_hash(db)==before);checks.append({'name':'missing table is partial not a false clean pass','passed':True,'financialHashUnchanged':True});db.close()
    db=fresh();table='commission_facts';rows=[('limit-fixture-'+str(i),'{}',0,'TEST') for i in range(rc.LIMIT+1)];db.executemany('INSERT INTO '+table+' VALUES(?,?,?,?)',rows);db.commit();before=financial_hash(db);r=request(db);require(r['partial'] and r['sources']['facts']['truncated']);require(r['aggregateCoverage']['ledger'] is False and all(t['ledgerOriginalKnownMinor'] is None and t['ledgerNetKnownMinor'] is None and t['ledgerUnknownAmountCount'] is None for t in r['totalsByCurrency'].values()));require(any(f['code']=='commission_math_and_refunds_not_covered' for f in r['findings']));require(financial_hash(db)==before);checks.append({'name':'truncated source disables dependent math rather than asserting missing rows','passed':True,'financialHashUnchanged':True});db.close()
    db=fresh();before=financial_hash(db);r=request(db,path='/api/admin/reconciliation/export');require('TEST-NOT-A-BANK-ACCOUNT' not in json.dumps(r) and 'LOCAL-TEST-PROOF' not in json.dumps(r));require(financial_hash(db)==before);checks.append({'name':'CSV and report exclude payout recipient and proof contents','passed':True,'financialHashUnchanged':True});db.close()
    case('invalid payout JSON cannot crash snapshot SQL or claim a transfer',"UPDATE commission_payments SET data='invalid-json'",'sandbox_payment_registration_invalid_json')
    # Export synthetic raw schema/rows for the equivalent Cloud D1-memory contract.
    db=fresh();schema=[dict(r) for r in db.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END,name")];raw={}
    for row in schema:
        if row['type']=='table':raw[row['name']]={'columns':[c[1] for c in db.execute('PRAGMA table_info('+row['name']+')')],'rows':[list(x) for x in db.execute('SELECT * FROM '+row['name'])]}
    data={};metadata={}
    for name,(table,columns,where) in rc.SOURCES.items():
        captured=[dict(x) for x in db.execute('SELECT '+columns+' FROM '+table+' WHERE '+where+' ORDER BY 1 LIMIT ?',(rc.LIMIT,))];n=db.execute('SELECT count(*) FROM '+table+' WHERE '+where).fetchone()[0];data[name]=captured;metadata[name]={'table':table,'exists':True,'totalRows':n,'loadedRows':len(captured),'truncated':n>rc.LIMIT,'limit':rc.LIMIT}
    gold=rc.build_report(data,metadata,FIXED_NOW)
    import copy
    pure_cases=[]
    def pure_case(name,source,index,column,value,code):
        d=copy.deepcopy(data);d[source][index][column]=value;r=rc.build_report(d,metadata,FIXED_NOW)
        require(any(f['code']==code for f in r['findings']));checks.append({'name':name,'passed':True,'pureComputationOnly':True})
        pure_cases.append({'name':name,'source':source,'index':index,'column':column,'value':value,'code':code,'golden':r})
    pure_case('malformed membership terms stay not-covered','memberSnapshots',0,'data','null','membership_snapshot_invalid')
    value=json.loads(data['snapshots'][0]['data']);value['rules']=[None];pure_case('malformed creation rules are explicitly invalid','snapshots',0,'data',json.dumps(value),'commission_snapshot_invalid')
    pure_case('malformed ledger locked facts remain not-covered','ledger',0,'data','null','commission_ledger_data_invalid')
    pure_case('fractional item quantity is not rounded into a fact','items',0,'quantity',1.5,'order_invalid_integer')
    d=copy.deepcopy(data)
    for e in d['payments']:
        if e['kind']=='sandbox_pay' and e['currency']=='USD':e['amount_minor']=rc.SAFE
    r=rc.build_report(d,metadata,FIXED_NOW);require(r['totalsByCurrency']['USD']['paidMinor'] is None);require('paidMinorExact' in r['totalsByCurrency']['USD']);checks.append({'name':'unsafe aggregate is null with exact integer text, never rounded','passed':True,'pureComputationOnly':True})
    pure_cases.append({'name':'unsafe aggregate is null with exact integer text, never rounded','data':d,'golden':r})
    d=copy.deepcopy(data);d['payments']=[];md=copy.deepcopy(metadata);md['payments'].update(exists=False,totalRows=0,loadedRows=0);r=rc.build_report(d,md,FIXED_NOW)
    require(r['aggregateCoverage']['cash'] is False and all(t['paidMinor'] is None and t['refundedMinor'] is None and t['netPaidMinor'] is None for t in r['totalsByCurrency'].values()));checks.append({'name':'missing cash source cannot turn known statement currency into zero paid total','passed':True,'pureComputationOnly':True})
    pure_cases.append({'name':'missing cash source cannot turn known statement currency into zero paid total','data':d,'metadata':md,'golden':r})
    fixture={'syntheticOnly':True,'originalDatabaseOpened':False,'pureCases':pure_cases,'schema':schema,'tables':raw,'cases':fixture_cases,'data':data,'metadata':metadata,'observedAt':FIXED_NOW,'golden':gold,'memberOrderId':oid,'memberItemId':iid}
    (ROOT/'06_验证与后续工作/负责人优化建议-只读对账合成夹具.json').write_text(json.dumps(fixture,ensure_ascii=False,indent=2),encoding='utf-8');db.close()
    report['passed']=len(checks);report['failed']=0
except BaseException:
    report['failed']=1;report['error']=traceback.format_exc();print(report['error'])
finally:
    report['sourceSha256']=hashlib.sha256((BACKEND/'reconciliation.py').read_bytes()).hexdigest();(ROOT/'06_验证与后续工作/负责人优化建议-只读对账Python专项.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':report.get('passed'),'failed':report['failed']}))
if report['failed']:raise SystemExit(1)
