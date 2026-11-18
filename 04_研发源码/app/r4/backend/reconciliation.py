"""Read-only sandbox consistency diagnostics, never channel reconciliation or alerts."""
import csv
import io
import json
import re
import time
from urllib.parse import parse_qs, urlsplit
try:
    from commission import calculate as commission_calculate, rounded as commission_round
except ModuleNotFoundError:
    import importlib.util
    from pathlib import Path
    _spec=importlib.util.spec_from_file_location('readonly_commission_math',Path(__file__).with_name('commission.py'))
    _module=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_module)
    commission_calculate,commission_round=_module.calculate,_module.rounded

LIMIT=5000
SAFE=9_007_199_254_740_991
# Explicit columns exclude addresses, credentials, messages and full payout receipts.
SOURCES={
 'orders':('commerce_orders','id,owner,environment,status,payment_status,fulfillment_status,currency,subtotal_minor,shipping_minor,tax_minor,total_minor,refunded_minor,created,updated',"environment='sandbox'"),
 'items':('commerce_order_items','id,order_id,sku_id,product_id,type,quantity,price_minor,currency,unit_shipping_minor,unit_tax_minor,content_id,price_version,refunded_quantity','1=1'),
 'payments':('commerce_payment_events','id,owner,environment,order_id,kind,amount_minor,currency,items,status,created',"environment='sandbox'"),
 'entitlements':('commerce_entitlements','id,owner,environment,order_id,item_id,content_id,type,quantity,remaining,status',"environment='sandbox'"),
 'memberSnapshots':('membership_order_snapshots','item_id,owner,environment,order_id,plan_id,plan_version,group_id,data,subscription_id,payment_event_id,period_start,period_end,state',"environment='sandbox'"),
 'subscriptions':('membership_subscriptions','id,owner,environment,original_item_id,current_item_id,plan_id,plan_version,group_id,status,auto_renew,period_start,period_end,grace_end,trial_end,next_charge_at',"environment='sandbox'"),
 'memberEvents':('membership_events','id,owner,environment,subscription_id,kind,created',"environment='sandbox'"),
 'snapshots':('commission_snapshots','item_id,order_id,data,created','1=1'),
 'facts':('commission_facts','item_id,data','1=1'),
 'ledger':('commission_ledger','id,order_id,item_id,beneficiary,rule_id,rule_version,currency,quantity,refunded_quantity,base_minor,amount_minor,net_minor,status,freeze_until,payment_event,data,created,updated','1=1'),
 'adjustments':('commission_adjustments','id,ledger_id,beneficiary,currency,refunded_quantity,amount_minor,target_minor,status,source_event,created','1=1'),
 'statements':('commission_statements','id,beneficiary,currency,total_minor,status,version,created,updated','1=1'),
 'statementLines':('commission_statement_lines','statement_id,kind,source_id,amount_minor','1=1'),
 'payouts':('commission_payments',"id,statement_id,status,json_valid(data) AS data_valid,CASE WHEN json_valid(data) THEN json_extract(data,'$.actualPaid') ELSE NULL END AS actual_paid,CASE WHEN json_valid(data) THEN json_extract(data,'$.proofVerified') ELSE NULL END AS proof_verified,created",'1=1'),
}

def init_schema(db):
    """No report schema or financial mutation is needed."""
    return None

def integer(v):return type(v) is int and abs(v)<=SAFE
def safe(v):return v if integer(v) else None
def parse(v,default=None):
    try:return json.loads(v) if isinstance(v,str) else v
    except (ValueError,TypeError):return default

def build_report(data,metadata,observed_at,filters=None,with_groups=False):
    """Pure computations on one captured snapshot; imported math helpers are pure."""
    filters=filters or {};findings=[];checks=[];related_statements=set();current_group=['']
    def add(code,severity='error',order=None,item=None,source=None,currency=None,observed=None,expected=None,detail=''):
        findings.append({'id':code+':'+str(source or item or order or 'scope'),'code':code,'severity':severity,'orderId':order,'itemId':item,'sourceId':source,'currency':currency,'observed':observed,'expected':expected,'deltaMinor':safe(observed-expected) if integer(observed) and integer(expected) else None,'detail':detail})
        if with_groups:findings[-1]['checkGroup']=current_group[0]
    def ready(code,*tables):
        current_group[0]=code
        missing=[t for t in tables if not metadata[t]['exists'] or metadata[t]['truncated']]
        checks.append({'code':code,'status':'not-covered' if missing else 'covered','sourceTables':list(tables)})
        if missing:add(code+'_not_covered','not-covered',detail='Missing or truncated sources: '+','.join(missing))
        return not missing
    orders={r['id']:r for r in data['orders']};items={r['id']:r for r in data['items']};ledger={r['id']:r for r in data['ledger']};subs={r['id']:r for r in data['subscriptions']};statements={r['id']:r for r in data['statements']};adjustments={r['id']:r for r in data['adjustments']}
    payments={r['id']:r for r in data['payments']};snapshots={r['item_id']:r for r in data['snapshots']};member_snaps={r['item_id']:r for r in data['memberSnapshots']};fact_rows={r['item_id']:r for r in data['facts']}
    eligible=lambda o:o and (not filters.get('orderId') or o['id']==filters['orderId']) and (not filters.get('currency') or o['currency']==filters['currency'])
    valid_int=lambda row,keys:all(integer(row.get(k)) and row[k]>=0 for k in keys)
    totals={}
    def total(currency,key,value):
        if not isinstance(currency,str) or not re.fullmatch('[A-Z]{3}',currency) or not integer(value):return
        t=totals.setdefault(currency,{'paidMinor':0,'refundedMinor':0,'ledgerOriginalKnownMinor':0,'ledgerNetKnownMinor':0,'ledgerUnknownAmountCount':0,'bookedStatementMinor':0,'channelFeeMinor':None,'actualArrivalMinor':None,'actualTransferredMinor':None})
        t[key]=t.get(key,0)+value
    if ready('orders_and_cash','orders','items','payments'):
        for event in data['payments']:
            o=orders.get(event['order_id'])
            if not o:add('orphan_payment_event',source=event['id'],order=event['order_id']);continue
            if not eligible(o):continue
            if event['owner']!=o['owner'] or event['currency']!=o['currency']:add('payment_owner_or_currency',source=event['id'],order=o['id'],currency=event['currency'])
            if not valid_int(event,['amount_minor']):add('payment_invalid_integer',source=event['id'],order=o['id'],currency=event['currency']);continue
            if event['status']=='applied' and event['kind'] in ('sandbox_pay','refund'):total(event['currency'],'paidMinor' if event['kind']=='sandbox_pay' else 'refundedMinor',event['amount_minor'])
        for o in orders.values():
            if not eligible(o):continue
            lines=[i for i in items.values() if i['order_id']==o['id']];ev=[e for e in data['payments'] if e['order_id']==o['id'] and e['status']=='applied'];paid=[e for e in ev if e['kind']=='sandbox_pay'];refunds=[e for e in ev if e['kind']=='refund'];refs={'order':o['id'],'currency':o['currency']}
            if not lines:add('order_without_items',**refs);continue
            if not valid_int(o,['subtotal_minor','shipping_minor','tax_minor','total_minor','refunded_minor']) or not all(valid_int(i,['quantity','price_minor','unit_shipping_minor','unit_tax_minor','refunded_quantity']) and i['quantity']>0 for i in lines):add('order_invalid_integer',**refs);continue
            subtotal=sum(i['quantity']*i['price_minor'] for i in lines);shipping=sum(i['quantity']*i['unit_shipping_minor'] for i in lines);tax=sum(i['quantity']*i['unit_tax_minor'] for i in lines)
            for key,expected in [('subtotal_minor',subtotal),('shipping_minor',shipping),('tax_minor',tax),('total_minor',subtotal+shipping+tax)]:
                if o[key]!=expected:add('order_'+key,observed=o[key],expected=safe(expected),**refs)
            for i in lines:
                if i['currency']!=o['currency']:add('item_currency_mismatch',item=i['id'],observed=i['currency'],expected=o['currency'],**refs)
            expected_paid=o['payment_status'] in ('paid','partially_refunded','refunded')
            if len(paid)!=(1 if expected_paid else 0):add('payment_fact_count',observed=len(paid),expected=1 if expected_paid else 0,**refs)
            if len(paid)==1 and paid[0]['amount_minor']!=o['total_minor']:add('payment_original_amount',source=paid[0]['id'],observed=paid[0]['amount_minor'],expected=o['total_minor'],**refs)
            if refunds and len(paid)!=1:add('refund_without_single_payment_fact',**refs)
            if len(paid)==1:
                expected_state='refunded' if all(i['refunded_quantity']==i['quantity'] for i in lines) else 'partially_refunded' if any(i['refunded_quantity']>0 for i in lines) else 'paid'
                if o['payment_status']!=expected_state:add('payment_refund_state',observed=o['payment_status'],expected=expected_state,**refs)
            refunded={i['id']:0 for i in lines}
            for e in refunds:
                entries=parse(e['items']);amount=0;seen=set()
                if not isinstance(entries,list) or not entries:add('refund_items_invalid',source=e['id'],**refs);continue
                for entry in entries:
                    i=items.get(entry.get('itemId')) if isinstance(entry,dict) else None;q=entry.get('quantity') if isinstance(entry,dict) else None
                    if not i or i['order_id']!=o['id'] or not integer(q) or q<1 or i['id'] in seen:add('refund_item_reference_or_quantity',source=e['id'],**refs);continue
                    seen.add(i['id']);refunded[i['id']]+=q;amount+=q*(i['price_minor']+i['unit_tax_minor']+i['unit_shipping_minor'])
                if amount!=e['amount_minor']:add('refund_event_amount',source=e['id'],observed=e['amount_minor'],expected=safe(amount),**refs)
            for i in lines:
                if refunded[i['id']]!=i['refunded_quantity'] or i['refunded_quantity']>i['quantity']:add('refund_cumulative_quantity',item=i['id'],observed=i['refunded_quantity'],expected=refunded[i['id']],**refs)
            if all(integer(e['amount_minor']) for e in refunds):
                expected=sum(e['amount_minor'] for e in refunds)
                if o['refunded_minor']!=expected:add('refund_order_total',observed=o['refunded_minor'],expected=safe(expected),**refs)
                if expected>o['total_minor']:add('refund_exceeds_original',observed=safe(expected),expected=o['total_minor'],**refs)
    if ready('item_links_and_entitlements','orders','items','entitlements'):
        for i in items.values():
            o=orders.get(i['order_id'])
            if not o:add('orphan_order_item',item=i['id'],order=i['order_id']);continue
            if not eligible(o) or o['payment_status'] not in ('paid','partially_refunded','refunded') or i['type'] not in ('digital','membership'):continue
            ent=[e for e in data['entitlements'] if e['item_id']==i['id']];refs={'order':o['id'],'item':i['id'],'currency':o['currency']}
            if len(ent)!=1:add('paid_item_entitlement_count',observed=len(ent),expected=1,**refs);continue
            e=ent[0];remaining=i['quantity']-i['refunded_quantity'] if valid_int(i,['quantity','refunded_quantity']) else None
            if e['owner']!=o['owner'] or e['order_id']!=o['id'] or e['content_id']!=i['content_id'] or e['type']!=i['type']:add('entitlement_reference',source=e['id'],**refs)
            if e['quantity']!=i['quantity'] or e['remaining']!=remaining or e['status']!=('revoked' if remaining==0 else 'active'):add('entitlement_remaining',source=e['id'],observed=e['remaining'],expected=remaining,**refs)
        for e in data['entitlements']:
            if e['item_id'] not in items:add('orphan_entitlement',source=e['id'],order=e['order_id'],item=e['item_id'])
    if ready('membership_links','orders','items','memberSnapshots','subscriptions','memberEvents','payments'):
        for i in items.values():
            o=orders.get(i['order_id'])
            if not eligible(o) or i['type']!='membership':continue
            refs={'order':o['id'],'item':i['id'],'currency':o['currency']};s=member_snaps.get(i['id'])
            if not s:add('historical_membership_snapshot_missing','not-covered',**refs);continue
            if s['owner']!=o['owner'] or s['order_id']!=o['id']:add('membership_snapshot_owner',**refs)
            terms=parse(s['data'])
            if not isinstance(terms,dict):add('membership_snapshot_invalid','not-covered',**refs);continue
            if terms.get('currency')!=i['currency'] or terms.get('firstPriceMinor')!=i['price_minor'] or terms.get('priceVersion')!=i['price_version']:add('membership_order_terms',**refs)
            if o['payment_status'] not in ('paid','partially_refunded','refunded'):continue
            sub=subs.get(s['subscription_id']);event=payments.get(s['payment_event_id'])
            if not sub or not event:add('paid_membership_link_pending',source=s.get('subscription_id'),**refs);continue
            if sub['owner']!=o['owner'] or sub['group_id']!=s['group_id'] or event['order_id']!=o['id'] or event['kind']!='sandbox_pay':add('membership_subscription_reference',source=sub['id'],**refs)
        for s in subs.values():
            current=items.get(s['current_item_id']);o=orders.get(current['order_id']) if current else None
            if not current or not o:add('orphan_subscription_current_item',source=s['id']);continue
            if not eligible(o):continue
            if o['owner']!=s['owner'] or current['type']!='membership':add('subscription_current_item_owner',source=s['id'],order=o['id'],item=current['id'])
            current_snapshot=member_snaps.get(current['id'])
            if not current_snapshot:add('subscription_current_snapshot_missing','not-covered',source=s['id'],order=o['id'],item=current['id'])
            else:
                if current_snapshot['subscription_id']!=s['id'] or current_snapshot['owner']!=s['owner'] or any(current_snapshot[k]!=s[k] for k in ('group_id','plan_id','plan_version')):add('subscription_current_snapshot_reference',source=s['id'],order=o['id'],item=current['id'])
                if current_snapshot['period_start']!=s['period_start'] or current_snapshot['period_end']!=s['period_end']:add('subscription_current_snapshot_period',source=s['id'],order=o['id'],item=current['id'])
                if s['status']!='revoked' and (current_snapshot['state']!='active' or current['refunded_quantity']>0):add('membership_current_period_requires_sync','warning',source=s['id'],order=o['id'],item=current['id'],detail='Stored current period may require business sync; no write or replacement is executed.')
            if not valid_int(s,['period_start','period_end']) or s['period_end']<=s['period_start']:add('subscription_period_invalid',source=s['id'],order=o['id'])
            elif s['period_end']<=observed_at and s['status'] in ('trialing','active','cancelled_active'):add('membership_effective_state_requires_sync','warning',source=s['id'],order=o['id'],detail='Stored state is observed only; no lifecycle sync is executed.')
        for e in data['memberEvents']:
            s=subs.get(e['subscription_id'])
            if not s or e['owner']!=s['owner']:add('membership_event_reference',source=e['id'])
    if ready('commission_math_and_refunds','orders','items','payments','snapshots','facts','ledger','adjustments'):
        expected_keys=set();verified_snapshot_items=set()
        for i in items.values():
            o=orders.get(i['order_id'])
            if not eligible(o) or o['payment_status'] not in ('paid','partially_refunded','refunded'):continue
            refs={'order':o['id'],'item':i['id'],'currency':o['currency']};raw=snapshots.get(i['id'])
            if not raw:add('historical_commission_snapshot_missing','not-covered',**refs);continue
            snap=parse(raw['data'])
            if not isinstance(snap,dict) or not isinstance(snap.get('rules'),list) or not all(isinstance(r,dict) for r in snap['rules']) or not isinstance(snap.get('config',{}),dict) or snap.get('attribution') is not None and not isinstance(snap['attribution'],dict):add('commission_snapshot_invalid',**refs);continue
            if not snap.get('enabled'):verified_snapshot_items.add(i['id']);continue
            if not valid_int(i,['quantity','price_minor','unit_tax_minor','unit_shipping_minor','refunded_quantity']) or i['quantity']<1 or i['refunded_quantity']>i['quantity']:add('commission_item_invalid_integer','not-covered',**refs);continue
            selected=[]
            for rule in snap['rules']:
                if rule.get('status')!='active' or rule.get('currency')!=i['currency']:continue
                beneficiary=rule.get('beneficiary') if rule.get('kind')=='author' else (snap.get('attribution') or {}).get('beneficiary')
                if beneficiary and beneficiary!=o['owner']:selected.append((rule,beneficiary))
            policy=snap.get('config',{}).get('stackingPolicy')
            if policy!='allow_both' and len({r.get('kind') for r,_ in selected})>1:selected=[(r,b) for r,b in selected if r.get('kind')==('author' if policy=='exclusive_author' else 'promotion')]
            verified_snapshot_items.add(i['id'])
            expected_keys.update((i['id'],r.get('ruleId'),r.get('version'),b) for r,b in selected)
            facts=parse(fact_rows[i['id']]['data']) if i['id'] in fact_rows else {'discountMinor':0,'channelFeeMinor':None,'source':'unified_commerce_no_discount_feature'}
            if not isinstance(facts,dict):add('commission_facts_invalid','not-covered',**refs);continue
            calculations=[]
            try:calculations=[commission_calculate(rule,i,facts) for rule,_ in selected]
            except (KeyError,ValueError,TypeError,OverflowError):add('commission_calculation_unverifiable','not-covered',**refs);continue
            gross=i['quantity']*(i['price_minor']+i['unit_tax_minor']+i['unit_shipping_minor'])
            blocked=any(c['amount'] is None for c in calculations) or sum(c['amount'] or 0 for c in calculations)>gross
            if sum(c['amount'] or 0 for c in calculations)>gross:add('commission_rule_total_exceeds_paid','warning',**refs,detail='The engine must keep this rule group waiting; the report does not enable it.')
            for (rule,beneficiary),calc in zip(selected,calculations):
                key=(i['id'],rule.get('ruleId'),rule.get('version'),beneficiary);expected_keys.add(key);found=[l for l in ledger.values() if (l['item_id'],l['rule_id'],l['rule_version'],l['beneficiary'])==key]
                if len(found)!=1:add('paid_commission_entry_missing_or_duplicate',observed=len(found),expected=1,**refs);continue
                l=found[0];detail=parse(l['data'])
                if not isinstance(detail,dict) or not isinstance(detail.get('facts',{}),dict):add('commission_ledger_data_invalid','not-covered',source=l['id'],**refs);continue
                stored_facts=detail.get('facts',{})
                if l['currency']!=o['currency'] or l['quantity']!=i['quantity']:add('commission_currency_or_quantity',source=l['id'],**refs)
                if any(stored_facts.get(k)!=facts.get(k) for k in ('discountMinor','channelFeeMinor')):add('commission_locked_facts_mismatch',source=l['id'],**refs)
                if facts.get('channelFeeMinor') is None:add('channel_fee_unknown','not-covered',source=l['id'],**refs)
                if blocked:
                    if l['status']!='waiting_facts' or any(l[k] is not None for k in ('base_minor','amount_minor','net_minor')):add('commission_unknown_fact_claimed_amount',source=l['id'],**refs)
                    continue
                if l['amount_minor']!=calc['amount'] or l['base_minor']!=calc['base']:add('commission_original_math',source=l['id'],observed=l['amount_minor'],expected=calc['amount'],**refs)
                try:expected=commission_round(calc['amount']*(i['quantity']-i['refunded_quantity']),i['quantity'],rule['rounding'])
                except (KeyError,ValueError,TypeError,OverflowError):add('commission_refund_unverifiable','not-covered',source=l['id'],**refs);continue
                if l['net_minor']!=expected or l['refunded_quantity']!=i['refunded_quantity']:add('commission_refund_balance',source=l['id'],observed=l['net_minor'],expected=expected,**refs)
                adj=[a for a in data['adjustments'] if a['ledger_id']==l['id']]
                if all(integer(a['amount_minor']) and a['amount_minor']>=0 for a in adj):
                    value=sum(a['amount_minor'] for a in adj)
                    if value!=calc['amount']-expected:add('commission_adjustment_sum',source=l['id'],observed=safe(value),expected=calc['amount']-expected,**refs)
                else:add('commission_adjustment_invalid_integer',source=l['id'],**refs)
        for l in ledger.values():
            o=orders.get(l['order_id'])
            if not o or l['item_id'] not in items:add('orphan_commission_ledger',source=l['id'],order=l['order_id'],item=l['item_id']);continue
            if not eligible(o):continue
            if l['amount_minor'] is None or l['net_minor'] is None:total(l['currency'],'ledgerUnknownAmountCount',1)
            if integer(l['amount_minor']):total(l['currency'],'ledgerOriginalKnownMinor',l['amount_minor'])
            if integer(l['net_minor']):total(l['currency'],'ledgerNetKnownMinor',l['net_minor'])
            if (l['item_id'],l['rule_id'],l['rule_version'],l['beneficiary']) not in expected_keys and l['item_id'] in verified_snapshot_items:add('commission_not_in_creation_snapshot',source=l['id'],order=o['id'],item=l['item_id'])
        for a in data['adjustments']:
            l=ledger.get(a['ledger_id'])
            if not l:add('orphan_commission_adjustment',source=a['id']);continue
            if a['beneficiary']!=l['beneficiary'] or a['currency']!=l['currency']:add('adjustment_owner_or_currency',source=a['id'],order=l['order_id'],item=l['item_id'])
            e=payments.get(a['source_event'])
            if not e or e['order_id']!=l['order_id'] or e['kind']!='refund':add('adjustment_refund_event',source=a['id'],order=l['order_id'],item=l['item_id'])
    if ready('statement_original_lines','statements','statementLines','ledger','adjustments','payouts'):
        for s in statements.values():
            lines=[x for x in data['statementLines'] if x['statement_id']==s['id']]
            if filters.get('orderId'):
                related=False
                for x in lines:
                    l=ledger.get(x['source_id']) if x['kind']=='earning' else ledger.get(adjustments.get(x['source_id'],{}).get('ledger_id'))
                    if l and l['order_id']==filters['orderId']:related=True
                if not related:continue
            related_statements.add(s['id'])
            if filters.get('currency') and s['currency']!=filters['currency']:continue
            if not all(integer(x['amount_minor']) for x in lines):add('statement_invalid_integer',source=s['id'],currency=s['currency']);continue
            value=sum(x['amount_minor'] for x in lines)
            if not lines or value!=s['total_minor']:add('statement_original_line_sum',source=s['id'],currency=s['currency'],observed=s['total_minor'],expected=safe(value))
            for x in lines:
                source=ledger.get(x['source_id']) if x['kind']=='earning' else adjustments.get(x['source_id'])
                if not source or source['beneficiary']!=s['beneficiary'] or source['currency']!=s['currency']:add('statement_line_reference',source=s['id'],currency=s['currency']);continue
                # Booked earnings remain historical even after later refunds.
                if x['kind']=='earning' and s['status'] in ('awaiting_approval','approved') and source['net_minor']!=x['amount_minor']:add('open_statement_stale_amount',source=s['id'],order=source['order_id'],observed=x['amount_minor'],expected=source['net_minor'],currency=s['currency'])
                if x['kind']=='recovery' and (not integer(source['amount_minor']) or x['amount_minor']!=-source['amount_minor']):add('statement_recovery_amount',source=s['id'],currency=s['currency'])
            if s['status']=='booked':total(s['currency'],'bookedStatementMinor',s['total_minor'])
        for x in data['statementLines']:
            if x['statement_id'] not in statements:add('orphan_statement_line',source=x['statement_id'])
        for p in data['payouts']:
            if p['statement_id'] not in statements:add('orphan_test_payment_registration',source=p['id'])
            if not p.get('data_valid'):add('sandbox_payment_registration_invalid_json','not-covered',source=p['id'])
            elif p['actual_paid']!=0 or p['proof_verified']!=0:add('sandbox_payment_claims_real_transfer',source=p['id'])
        for a in data['adjustments']:
            links=[statements.get(x['statement_id']) for x in data['statementLines'] if x['kind']=='recovery' and x['source_id']==a['id']]
            if a['status']=='reserved' and not any(s and s['status'] in ('awaiting_approval','approved') for s in links):add('recovery_reservation_without_open_statement',source=a['id'])
            if a['status']=='offset_booked' and not any(s and s['status']=='booked' for s in links):add('recovery_bookkeeping_without_statement',source=a['id'])
            if a['status']=='pending_recovery' and any(s and s['status'] in ('awaiting_approval','approved','booked') for s in links):add('pending_recovery_already_allocated',source=a['id'])
    # Unsupported sources are explicit, even when no internal mismatches are found.
    uncovered=['real-channel-daily-statement','channel-fees-and-bank-arrivals','payment-failure-event-source','callback-queue-backlog','real-refund-failure-source','chargebacks','external-alert-delivery','historical-as-of-reconstruction']
    aggregate_coverage={'cash':all(metadata[k]['exists'] and not metadata[k]['truncated'] for k in ('orders','items','payments')),'ledger':all(metadata[k]['exists'] and not metadata[k]['truncated'] for k in ('orders','items','payments','snapshots','facts','ledger','adjustments')),'bookedStatements':all(metadata[k]['exists'] and not metadata[k]['truncated'] for k in ('statements','statementLines','ledger','adjustments','payouts'))}
    for t in totals.values():
        if not aggregate_coverage['ledger']:
            for k in ('ledgerOriginalKnownMinor','ledgerNetKnownMinor','ledgerUnknownAmountCount'):t[k]=None
        if not aggregate_coverage['bookedStatements']:t['bookedStatementMinor']=None
        t['netPaidMinor']=t['paidMinor']-t['refundedMinor']
        if not aggregate_coverage['cash']:
            for k in ('paidMinor','refundedMinor','netPaidMinor'):t[k]=None
        for k,v in list(t.items()):
            if v is not None and not integer(v):t[k]=None;t[k+'Exact']=str(v);add('aggregate_outside_safe_integer','not-covered',detail=k)
    if filters.get('orderId'):findings=[f for f in findings if f['orderId']==filters['orderId'] or f['sourceId'] in related_statements or f['severity']=='not-covered']
    if filters.get('currency'):findings=[f for f in findings if f['currency'] in (None,filters['currency'])]
    errors=sum(f['severity']=='error' for f in findings);partial=any(not m['exists'] or m['truncated'] for m in metadata.values())
    return {'schemaVersion':1,'environment':'sandbox','scope':'current-read-only-consistency-snapshot','observedAt':observed_at,'readOnly':True,'productionEnabled':False,'realChannelReconciliationEnabled':False,'externalAlertsEnabled':False,'alertSent':False,'actualPaid':False,'fundsMutated':False,'filters':filters,'sourceScope':'bounded sandbox tables; filters select visible findings/totals and do not remove source truncation','statementScope':'whole statements intersecting the selected order','sources':metadata,'checks':checks,'uncovered':uncovered,'partial':partial,'aggregateCoverage':aggregate_coverage,'findings':findings,'counts':{'errors':errors,'warnings':sum(f['severity']=='warning' for f in findings),'notCovered':sum(f['severity']=='not-covered' for f in findings)},'totalsByCurrency':totals,'crossCurrencyGrandTotal':None,'conclusion':'mismatches-detected' if errors else 'partial-internal-coverage' if partial else 'no-detected-mismatch-in-covered-internal-checks'}

def capture_snapshot(db):
    """Server-only pure read capture; caller supplies its consistent read transaction."""
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    data={};metadata={}
    for name,(table,columns,where) in SOURCES.items():
        exists=table in tables
        count=db.execute('SELECT count(*) FROM '+table+' WHERE '+where).fetchone()[0] if exists else 0
        rows=[dict(r) for r in db.execute('SELECT '+columns+' FROM '+table+' WHERE '+where+' ORDER BY 1 LIMIT ?',(LIMIT,))] if exists else []
        data[name]=rows
        metadata[name]={'table':table,'exists':exists,'totalRows':count,'loadedRows':len(rows),'truncated':count>LIMIT,'limit':LIMIT}
    return data, metadata


def capture_report(db, observed_at=None, filters=None):
    data,metadata=capture_snapshot(db)
    return build_report(data,metadata,time.time_ns()//1_000_000 if observed_at is None else observed_at,filters)


class Reconciliation:
    def __init__(self,store,handler,error,limiter):self.store,self.h,self.Error,self.rate=store,handler,error,limiter
    def fail(self,status,message):raise self.Error(status,message)
    def route(self,method,path):
        if path not in ('/api/admin/reconciliation','/api/admin/reconciliation/export'):return None
        user=self.h.require()
        if method!='GET':self.fail(405,'沙箱内部对账仅允许只读查询；未启用真实渠道对账或外部告警。')
        self.rate('sandbox-reconciliation:'+user['id'],30)
        query={k:v[-1] for k,v in parse_qs(urlsplit(self.h.path).query).items()}
        if set(query)-{'orderId','currency'} or any(not isinstance(v,str) or len(v)>120 for v in query.values()) or query.get('currency') and not re.fullmatch('[A-Z]{3}',query['currency']):self.fail(400,'只支持沙箱订单编号及大写三位币种筛选。')
        with self.store.connect() as db:
            previous=db.execute('PRAGMA query_only').fetchone()[0];db.execute('PRAGMA query_only=ON')
            try:
                db.execute('BEGIN')
                tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                actor=db.execute('SELECT role FROM users WHERE id=?',(user['id'],)).fetchone();grant=db.execute('SELECT permission FROM commission_grants WHERE user_id=?',(user['id'],)).fetchone() if 'commission_grants' in tables else None
                if not actor or not(actor['role']=='admin' or actor['role'] in ('operator','reviewer') and grant and grant['permission']=='finance'):self.fail(403,'只允许管理员或当前后台账号且获财务专项授权者查看。')
                data={};metadata={}
                for name,(table,columns,where) in SOURCES.items():
                    exists=table in tables;count=db.execute('SELECT count(*) FROM '+table+' WHERE '+where).fetchone()[0] if exists else 0
                    rows=[dict(r) for r in db.execute('SELECT '+columns+' FROM '+table+' WHERE '+where+' ORDER BY 1 LIMIT ?',(LIMIT,))] if exists else []
                    data[name]=rows;metadata[name]={'table':table,'exists':exists,'totalRows':count,'loadedRows':len(rows),'truncated':count>LIMIT,'limit':LIMIT}
                result=build_report(data,metadata,time.time_ns()//1_000_000,query)
            finally:
                db.rollback();db.execute('PRAGMA query_only='+str(previous))
        if path.endswith('/export'):
            fields=['code','severity','orderId','itemId','sourceId','currency','observed','expected','deltaMinor','detail'];out=io.StringIO();writer=csv.writer(out);writer.writerow(fields)
            for f in result['findings']:
                values=[]
                for key in fields:
                    value=str(f.get(key) if f.get(key) is not None else '')
                    values.append("'"+value if value.lstrip().startswith(('=','+','-','@')) else value)
                writer.writerow(values)
            result['csv']=out.getvalue()
        return result
