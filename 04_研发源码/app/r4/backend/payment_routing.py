"""Sandbox-only routing admission. Frozen admission never revokes trusted payment facts."""
import copy
import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote
from uuid import uuid4

DEFAULT = {'revision':0,'mode':'legacy_sandbox','confirmed':False,'ruleVersion':'','contextDigest':'','rules':[],'productionEnabled':False}
MODES = ('legacy_sandbox','enforced_sandbox','paused')
PLATFORMS = ('web','app_store','google_play')
CHANNELS = ('sandbox','apple','google','stripe','paypal')
CLASSIFICATIONS = ('physical_goods','digital_content','digital_membership','digital_ai_credits','offline_service','live_one_to_one')
CLASSIFIER = {'physical':'physical_goods','digital':'digital_content','membership':'digital_membership'}
CLASSIFIER_VERSION = 'actual-commerce-type-v1'
TTL = 300_000
DB_NOW = "(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))"
SCHEMA = Path(__file__).with_name('payment_routing_schema.sql').read_text(encoding='utf-8')


def now():
    return time.time_ns()//1_000_000


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def init_schema(db):
    db.executescript(SCHEMA)


def config(db):
    row=db.execute('SELECT data FROM payment_routing_config WHERE id=1').fetchone()
    return {**copy.deepcopy(DEFAULT),**(json.loads(row['data']) if row else {}),'productionEnabled':False}


def strict_json(raw):
    def pairs(values):
        out={}
        for key,value in values:
            if key in out:raise ValueError('duplicate_key')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('invalid_number')))


def context():
    unknown={'schema':1,'id':None,'revision':0,'platform':None,'region':None,'source':'unknown',
             'ready':False,'digest':None,'reasonCode':'context_unverified','productionEnabled':False}
    if os.environ.get('EW_PAYMENT_ROUTING_SANDBOX_CONTEXT_ENABLED')!='1':return unknown
    try:
        raw=os.environ.get('EW_PAYMENT_ROUTING_SANDBOX_CONTEXT_JSON','')
        if len(raw.encode('utf-8'))>8192:raise ValueError('context_invalid')
        data=strict_json(raw)
        if (not isinstance(data,dict) or set(data)!={'schema','id','revision','platform','region'}
            or type(data['schema']) is not int or data['schema']!=1
            or not isinstance(data['id'],str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',data['id'])
            or type(data['revision']) is not int or not 1<=data['revision']<=2147483647
            or data['platform'] not in PLATFORMS or not isinstance(data['region'],str)
            or not re.fullmatch(r'[A-Z]{2}',data['region'])):raise ValueError('context_invalid')
        digest=fingerprint({'enabled':'1',**data})
        return {**data,'source':'server_fixed_sandbox','ready':True,'digest':digest,'reasonCode':'ready_sandbox','productionEnabled':False}
    except (ValueError,TypeError,UnicodeError):return unknown


def routing_summary(db):
    cfg=config(db)
    return {'mode':cfg['mode'],'policyRevision':cfg['revision'],'context':context(),'productionEnabled':False}


def resolve(db,items,*,simulation=None):
    cfg=config(db);ctx=context() if simulation is None else simulation
    mode='enforced_sandbox' if simulation is not None else cfg['mode']
    out={'eligible':False,'mode':mode,'channel':None,'matrixApplied':mode=='enforced_sandbox',
         'reasonCode':'ready_sandbox','blockedReasons':[],'policyRevision':cfg['revision'],
         'ruleVersion':cfg['ruleVersion'] if mode=='enforced_sandbox' else '', 'ruleIds':[],
         'classifierVersion':CLASSIFIER_VERSION,'contextDigest':ctx['digest'] if mode=='enforced_sandbox' else None,
         'adapterReady':False,'productionEnabled':False}
    reason=''
    if any(item.get('environment')!='sandbox' for item in items):reason='production_disabled'
    elif mode=='paused':reason='routing_paused'
    elif mode=='legacy_sandbox':
        out.update(eligible=True,channel='sandbox',reasonCode='legacy_sandbox',adapterReady=True)
        return out
    elif not ctx['ready']:reason='context_unverified'
    elif simulation is None and (cfg['confirmed'] is not True or not cfg['ruleVersion'] or cfg['contextDigest']!=ctx['digest']):reason='context_confirmation_required'
    elif len({item['currency'] for item in items})>1 or len({item['type']=='physical' for item in items})>1:reason='split_required'
    channels=set();rule_ids=set()
    if not reason:
        for item in items:
            kind=CLASSIFIER.get(item.get('type'))
            if kind not in CLASSIFICATIONS:reason='classification_not_implemented';break
            matched=[rule for rule in cfg['rules'] if (rule['environment'],rule['platform'],rule['region'],rule['classification'],rule['currency'])==
                     ('sandbox',ctx['platform'],ctx['region'],kind,item['currency'])]
            if not matched:reason='rule_unmatched';break
            if len(matched)>1:reason='rule_ambiguous';break
            channels.add(matched[0]['channel']);rule_ids.add(matched[0]['id'])
        if not reason and len(channels)>1:reason='split_required'
        if not reason and channels!={'sandbox'}:reason='adapter_unavailable'
    out['ruleIds']=sorted(rule_ids)
    out['channel']=next(iter(channels)) if len(channels)==1 else None
    out['adapterReady']=out['channel']=='sandbox'
    out['eligible']=not reason
    out['reasonCode']=reason or 'ready_sandbox'
    out['blockedReasons']=[reason] if reason else []
    return out


def catalog_decision(db,product):
    return resolve(db,[{'type':product['type'],'currency':product['currency'],'environment':product['environment']}])


def decorate_catalog(db,items):
    for product in items:
        for sku in product.get('variants',[]):
            sku['paymentRoute']=catalog_decision(db,{**product,**sku})
            sku['purchasable']=bool(sku['purchasable'] and sku['paymentRoute']['eligible'])
        product['paymentRoute']=catalog_decision(db,product)
        product['purchasable']=bool(product['purchasable'] and product['paymentRoute']['eligible'])
    return items


def decorate_membership_catalog(db,result):
    for plan in result.get('items',[]):
        decision=resolve(db,[{'type':'membership','currency':plan['currency'],'environment':plan['environment']}])
        plan['paymentRoute']=decision;plan['purchasable']=bool(plan['purchasable'] and decision['eligible'])
    result['paymentRouting']=routing_summary(db)
    return result


def route_summary(db,order):
    row=db.execute('SELECT * FROM commerce_order_payment_routes WHERE order_id=? AND owner=?',(order['id'],order['owner'])).fetchone()
    if row:
        data=json.loads(row['snapshot_data'])
        return {key:data[key] for key in ('mode','matrixApplied','channel','policyRevision','ruleVersion','contextDigest','quoteId','created','productionEnabled')}
    return {'mode':'legacy_unrouted','matrixApplied':False,'channel':'sandbox','policyRevision':0,'ruleVersion':'',
            'contextDigest':None,'quoteId':None,'created':None,'productionEnabled':False}


def original_terms(db,oid):
    return {'membership':[{'itemId':r['item_id'],'data':r['data']} for r in db.execute('SELECT item_id,data FROM membership_order_snapshots WHERE order_id=? ORDER BY item_id',(oid,))],
            'digital':[{'itemId':r['item_id'],'contentId':r['content_id'],'mediaId':r['media_id'],'policyData':r['policy_snapshot']} for r in db.execute('SELECT * FROM digital_order_snapshots WHERE order_id=? ORDER BY item_id',(oid,))]}


def compatible_order(db,order):
    """Current fulfilment identity; price changes alone never rewrite an old order."""
    for line in db.execute('SELECT * FROM commerce_order_items WHERE order_id=?',(order['id'],)):
        current=db.execute('''SELECT p.*,s.currency,coalesce(v.active,1) active,coalesce(v.options,'[]') options
          FROM commerce_skus s JOIN commerce_products p ON p.id=s.product_id
          LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id WHERE s.id=?''',(line['sku_id'],)).fetchone()
        if (not current or current['id']!=line['product_id'] or current['environment']!='sandbox' or current['status']!='published'
            or not current['active'] or current['type']!=line['type'] or current['content_id']!=line['content_id'] or current['currency']!=line['currency']
            or json.loads(current['options'])!=json.loads(line['snapshot_data']).get('options',[])):return False
    return True


def order_usability(db,order,*,stamp=None):
    cfg=config(db);ctx=context();stamp=now() if stamp is None else stamp
    out={'usable':False,'reasonCode':'order_not_payable','checkedAt':stamp,'currentMode':cfg['mode'],
         'currentPolicyRevision':cfg['revision'],'currentContextDigest':ctx['digest']}
    if order['status']!='awaiting_payment' or order['payment_status']!='unpaid' or order['reserved_until']<=stamp:return out
    if cfg['mode']=='paused':out['reasonCode']='routing_paused';return out
    route=db.execute('SELECT * FROM commerce_order_payment_routes WHERE order_id=?',(order['id'],)).fetchone()
    if not route or route['mode']=='legacy_sandbox':out.update(usable=True,reasonCode='legacy_sandbox');return out
    if cfg['mode']!='enforced_sandbox' or not ctx['ready'] or cfg['confirmed'] is not True or cfg['contextDigest']!=ctx['digest']:
        out['reasonCode']='route_reconfirmation_required';return out
    if not compatible_order(db,order):out['reasonCode']='order_requote_required';return out
    accepted=route['policy_revision']==cfg['revision'] and route['context_digest']==ctx['digest']
    if not accepted:
        for row in db.execute('''SELECT * FROM payment_routing_confirmations WHERE owner=? AND order_id=?
            AND policy_revision=? AND context_digest=? AND expires>? ORDER BY created DESC,id DESC''',
            (order['owner'],order['id'],cfg['revision'],ctx['digest'],stamp)):
            data=json.loads(row['snapshot_data'])
            if data['orderFingerprint']==order['fingerprint'] and data.get('originalTerms')==original_terms(db,order['id']):accepted=True;break
    out.update(usable=accepted,reasonCode='ready_sandbox' if accepted else 'route_reconfirmation_required')
    return out


def privacy_registry():
    out={name:('commerceAndFulfilment','r.owner=?') for name in ('payment_routing_quotes','commerce_order_payment_routes','payment_routing_quote_consumptions','payment_routing_confirmations')}
    out['payment_routing_versions']=('commerceAndFulfilment','r.actor=?')
    return out


def export_metadata(db,owner):
    # Deliberate allowlist: no request fingerprint, raw bindings, internal rule references or address copy.
    queries={
      'paymentRoutingQuotes':'SELECT id,request_id,purpose,order_id,mode,policy_revision,context_digest,created,expires FROM payment_routing_quotes WHERE owner=?',
      'orderPaymentRoutes':'SELECT order_id,mode,quote_id,policy_revision,context_digest,matrix_applied,digest,created FROM commerce_order_payment_routes WHERE owner=?',
      'paymentRoutingQuoteConsumptions':'SELECT quote_id,order_id,created FROM payment_routing_quote_consumptions WHERE owner=?',
      'paymentRoutingConfirmations':'SELECT id,order_id,quote_id,request_id,policy_revision,context_digest,digest,created,expires FROM payment_routing_confirmations WHERE owner=?',
      'paymentRoutingVersions':'SELECT id,revision,rule_version,context_digest,digest,created FROM payment_routing_versions WHERE actor=?'}
    return {key:[dict(r) for r in db.execute(sql,(owner,))] for key,sql in queries.items()}


class PaymentRouting:
    def __init__(self,store,handler,error,rate,*,test_clock=None):
        self.store,self.h,self.Error,self.rate=store,handler,error,rate
        self.owner=handler.user['id'] if handler.user else '';self._clock=test_clock or now

    def clock(self):return self._clock()

    def body(self):
        if self.h.headers.get_content_type()!='application/json':self.fail(415,'json_required')
        try:length=int(self.h.headers.get('Content-Length','0'))
        except ValueError:self.fail(400,'invalid_request')
        if not 0<length<=262144:self.fail(413,'request_too_large')
        try:data=strict_json(self.h.rfile.read(length).decode('utf-8',errors='strict'))
        except (ValueError,UnicodeError):self.fail(400,'invalid_json')
        if not isinstance(data,dict):self.fail(400,'invalid_request')
        return data

    def fail(self,status,code):raise self.Error(status,code)

    def commerce(self):
        from commerce import Commerce
        return Commerce(self.store,self.h,self.Error,self.rate)

    def identifier(self,value):
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',value):self.fail(400,'invalid_request')
        return value

    def normalize(self,data):
        if set(data)-{'requestId','environment','items','shippingAddress','membershipRenewalOf'}:self.fail(400,'invalid_request')
        c=self.commerce();env=c.environment(data.get('environment','production'))
        semantic={'environment':env,'items':c.items(data.get('items')),'shippingAddress':c.address(data.get('shippingAddress'))}
        if data.get('membershipRenewalOf') is not None:semantic['membershipRenewalOf']=c.text(data['membershipRenewalOf'],100,1)
        return semantic

    def read_facts(self,db,requested,address,*,frozen_order=None,preview=False):
        """Pure reads; no member.sync, expire, commission serializer or fulfilment."""
        from commerce import SKU_COLUMNS,SKU_JOIN,MAX_MINOR
        from digital_entitlements import catalog_ready as digital_ready,policy as digital_policy
        items=[];bindings={'skus':[],'plans':[],'digital':[]}
        old={r['sku_id']:r for r in db.execute('SELECT * FROM commerce_order_items WHERE order_id=?',(frozen_order['id'],))} if frozen_order else {}
        for req in requested:
            r=db.execute(f'SELECT p.*,{SKU_COLUMNS} FROM commerce_products p {SKU_JOIN} WHERE s.id=?',(req['skuId'],)).fetchone()
            if not r or r['environment']!='sandbox' or r['status']!='published' or not r['sku_active']:self.fail(409,'product_unavailable')
            qty=req['quantity'];line=old.get(req['skuId'])
            if not preview and not frozen_order and r['stock']-r['reserved']<qty:self.fail(409,'insufficient_stock')
            if not preview and r['type']=='physical' and not frozen_order:
                if not all(address.get(k) for k in ('name','country','address')):self.fail(400,'shipping_address_required')
                if address['country'] not in json.loads(r['shipping_countries']):self.fail(400,'shipping_country_unavailable')
            data=json.loads(r['data']);options=json.loads(r['sku_options']);member=None;digital=None
            if line:
                data=json.loads(line['snapshot_data']);options=data.get('options',[])
            if r['type']=='membership':
                plan=db.execute("SELECT * FROM membership_plans WHERE sku_id=? AND environment='sandbox' AND status='published'",(r['sku_id'],)).fetchone()
                if not plan:self.fail(409,'order_requote_required' if frozen_order else 'membership_plan_unavailable')
                bindings['plans'].append({'skuId':r['sku_id'],'planId':plan['id'],'version':plan['version'],'status':plan['status'],'data':plan['data']})
                member={**json.loads(plan['data']),'id':plan['id'],'version':plan['version'],'status':plan['status'],'skuId':plan['sku_id'],'groupId':plan['group_id'],'environment':plan['environment']}
                if line:
                    term=db.execute('SELECT data FROM membership_order_snapshots WHERE item_id=?',(line['id'],)).fetchone()
                    if not term:self.fail(409,'order_requote_required')
                    member=json.loads(term['data'])
                elif qty!=1 or member['priceVersion']!=r['price_version'] or member['firstPriceMinor']!=r['price_minor'] or member['currency']!=r['currency']:
                    self.fail(409,'membership_plan_changed')
            if r['type']=='digital':
                product={'type':r['type'],'environment':r['environment'],'contentId':r['content_id']}
                readiness=digital_ready(db,product)
                if readiness is False:self.fail(409,'digital_terms_unavailable')
                if readiness is True:
                    asset=db.execute('SELECT * FROM digital_sandbox_assets WHERE content_id=?',(r['content_id'],)).fetchone()
                    course=db.execute("SELECT * FROM contents WHERE kind='courses' AND id=?",(r['content_id'],)).fetchone()
                    policyrow=db.execute("SELECT data FROM settings WHERE key='digital_entitlements'").fetchone()
                    bindings['digital'].append({'skuId':r['sku_id'],'contentId':r['content_id'],'mediaId':asset['media_id'],
                        'assetOwner':asset['owner'],'assetStatus':asset['status'],'assetUpdated':asset['updated'],
                        'courseUpdated':course['updated'],'courseData':course['data'],'policyData':policyrow['data']})
                    digital={**digital_policy(db),'contentId':r['content_id'],'mediaId':asset['media_id']}
                    if line:
                        term=db.execute('SELECT * FROM digital_order_snapshots WHERE item_id=?',(line['id'],)).fetchone()
                        if not term:self.fail(409,'order_requote_required')
                        digital={**json.loads(term['policy_snapshot']),'contentId':term['content_id'],'mediaId':term['media_id']}
            item={'skuId':r['sku_id'],'productId':r['id'],'quantity':qty,'type':r['type'],'classification':CLASSIFIER.get(r['type']),
                  'title':line['title'] if line else r['title'],'environment':'sandbox','priceMinor':line['price_minor'] if line else r['price_minor'],
                  'currency':line['currency'] if line else r['currency'],'unitShippingMinor':line['unit_shipping_minor'] if line else r['shipping_minor'] if r['type']=='physical' else 0,
                  'unitTaxMinor':line['unit_tax_minor'] if line else r['tax_minor'],'priceVersion':line['price_version'] if line else r['price_version'],
                  'productVersion':r['version'],'contentId':line['content_id'] if line else r['content_id'],'options':options,
                  'refundPolicy':data.get('refundPolicy',''),'membershipTerms':member,'digitalTerms':digital}
            item['unitPriceMinor']=item['priceMinor'];items.append(item)
            bindings['skus'].append({'skuId':r['sku_id'],'productId':r['id'],'productVersion':r['version'],'priceVersion':r['price_version'],
                'priceMinor':r['price_minor'],'currency':r['currency'],'type':r['type'],'contentId':r['content_id'],
                'options':r['sku_options'],'shippingCountries':r['shipping_countries'],'shippingMinor':r['shipping_minor'],'taxMinor':r['tax_minor']})
        totals=None
        if len({i['currency'] for i in items})==1:
            totals={'currency':items[0]['currency'],'subtotalMinor':sum(i['priceMinor']*i['quantity'] for i in items),
                    'shippingMinor':sum(i['unitShippingMinor']*i['quantity'] for i in items),'taxMinor':sum(i['unitTaxMinor']*i['quantity'] for i in items)}
            totals['totalMinor']=sum(totals[key] for key in ('subtotalMinor','shippingMinor','taxMinor'))
            if totals['totalMinor']>MAX_MINOR:self.fail(400,'amount_out_of_range')
        return items,totals,bindings

    def bindings_current(self,db,snapshot,*,order=None):
        try:
            requested=[{'skuId':i['skuId'],'quantity':i['quantity']} for i in snapshot['items']]
            items,totals,bindings=self.read_facts(db,requested,{},frozen_order=order,preview=True)
            return bindings==snapshot['bindings']
        except self.Error:return False

    def quote_usability(self,db,row):
        cfg=config(db);ctx=context();stamp=self.clock();data=json.loads(row['snapshot_data'])
        reason=''
        if cfg['mode']=='paused':reason='routing_paused'
        elif row['expires']<=stamp:reason='quote_stale'
        elif cfg['mode']!='enforced_sandbox' or not ctx['ready'] or cfg['confirmed'] is not True or cfg['contextDigest']!=ctx['digest'] or cfg['revision']!=row['policy_revision'] or ctx['digest']!=row['context_digest']:reason='quote_stale'
        elif data['decision']['eligible'] is not True:reason=data['decision']['reasonCode']
        elif row['purpose']=='new_order' and db.execute('SELECT 1 FROM payment_routing_quote_consumptions WHERE quote_id=?',(row['id'],)).fetchone():reason='quote_consumed'
        else:
            order=None
            if row['purpose']=='order_reconfirm':
                order=db.execute('SELECT * FROM commerce_orders WHERE id=? AND owner=?',(row['order_id'],row['owner'])).fetchone()
                if not order or order['payment_status']!='unpaid' or order['status']!='awaiting_payment' or order['reserved_until']<=stamp:reason='order_not_payable'
                elif order['fingerprint']!=data['orderFingerprint'] or original_terms(db,order['id'])!=data['originalTerms'] or not compatible_order(db,order):reason='order_requote_required'
            if not reason and not self.bindings_current(db,data,order=order):reason='quote_stale'
        return {'usable':not reason,'reasonCode':reason or 'ready_sandbox','checkedAt':stamp,'currentMode':cfg['mode'],
                'currentPolicyRevision':cfg['revision'],'currentContextDigest':ctx['digest']}

    def quote_view(self,db,row):
        data=json.loads(row['snapshot_data']);used=db.execute('SELECT order_id FROM payment_routing_quote_consumptions WHERE quote_id=?',(row['id'],)).fetchone()
        return {'id':row['id'],'purpose':row['purpose'],'orderId':row['order_id'] or None,'created':row['created'],'expires':row['expires'],
                'items':data['items'],'totals':data['totals'],'decision':data['decision'],'usability':self.quote_usability(db,row),
                'groups':data.get('groups',[]),'consumedOrderId':used['order_id'] if used else None,'productionEnabled':False}

    def groups(self,db,items,simulation=None):
        grouped={}
        for item in items:
            d=resolve(db,[item],simulation=simulation);key=(item['type']=='physical',item['currency'],d['channel'])
            grouped.setdefault(key,{'type':'physical' if key[0] else 'nonphysical','currency':key[1],'channel':key[2],'items':[],'decision':d})['items'].append({'skuId':item['skuId'],'quantity':item['quantity']})
        return list(grouped.values())

    def create_quote(self,data,*,order_id=None):
        request=self.identifier(data.get('requestId'))
        if order_id:
            if set(data)!={'requestId'}:self.fail(400,'invalid_request')
            token=fingerprint({'purpose':'order_reconfirm','orderId':order_id});semantic=None
        else:
            semantic=self.normalize(data);token=fingerprint({'purpose':'new_order','intent':semantic})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM payment_routing_quotes WHERE owner=? AND request_id=?',(self.owner,request)).fetchone()
            if old:
                if old['fingerprint']!=token:self.fail(409,'request_conflict')
                return {'quote':self.quote_view(db,old),'productionEnabled':False}
            cfg=config(db);ctx=context()
            if cfg['mode']=='paused':self.fail(503,'routing_paused')
            if cfg['mode']!='enforced_sandbox':self.fail(409,'quote_not_required')
            if not ctx['ready']:self.fail(409,'context_unverified')
            if cfg['confirmed'] is not True or cfg['contextDigest']!=ctx['digest']:self.fail(409,'context_confirmation_required')
            self.commerce().enabled(db,'sandbox')
            order=None
            if order_id:
                order=self.commerce().own_order(db,order_id)
                route=db.execute('SELECT mode FROM commerce_order_payment_routes WHERE order_id=?',(order_id,)).fetchone()
                if not route or route['mode']!='enforced_sandbox':self.fail(409,'quote_not_required')
                if order['payment_status']!='unpaid' or order['status']!='awaiting_payment' or order['reserved_until']<=self.clock():self.fail(409,'order_not_payable')
                if not compatible_order(db,order):self.fail(409,'order_requote_required')
                requested=[{'skuId':r['sku_id'],'quantity':r['quantity']} for r in db.execute('SELECT * FROM commerce_order_items WHERE order_id=? ORDER BY sku_id',(order_id,))]
                address=json.loads(order['shipping_address'])
            else:
                if semantic['environment']!='sandbox':self.fail(403,'production_disabled')
                requested=semantic['items'];address=semantic['shippingAddress']
            items,totals,bindings=self.read_facts(db,requested,address,frozen_order=order)
            decision=resolve(db,items);stamp=self.clock();qid=str(uuid4())
            snapshot={'schema':1,'intentFingerprint':fingerprint(semantic) if semantic else '',
                'shippingCountry':address.get('country') or None,'renewalOf':semantic.get('membershipRenewalOf') if semantic else None,
                'items':items,'totals':totals,'bindings':bindings,'decision':decision,'context':ctx,'groups':self.groups(db,items)}
            if order:snapshot.update(orderFingerprint=order['fingerprint'],originalTerms=original_terms(db,order_id))
            if context()['digest']!=ctx['digest']:self.fail(409,'context_confirmation_required')
            db.execute('INSERT INTO payment_routing_quotes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(qid,self.owner,request,token,'order_reconfirm' if order else 'new_order',order_id or '',
                'enforced_sandbox',cfg['revision'],ctx['digest'],canonical(snapshot),stamp,stamp+TTL))
            return {'quote':self.quote_view(db,db.execute('SELECT * FROM payment_routing_quotes WHERE id=?',(qid,)).fetchone()),'productionEnabled':False}

    def admit_order(self,db,semantic,quote_id,lines,totals):
        cfg=config(db)
        if cfg['mode']=='paused':self.fail(503,'routing_paused')
        if cfg['mode']=='legacy_sandbox':
            if quote_id is not None:self.fail(400,'quote_not_required')
            # Preserve the old admission/capture path and its errors exactly.
            # Terms below are read only after those original captures succeeded.
            currency,subtotal,shipping,tax=totals
            quoted={'currency':currency,'subtotalMinor':subtotal,'shippingMinor':shipping,'taxMinor':tax,'totalMinor':subtotal+shipping+tax}
            return {'mode':'legacy_sandbox','policyRevision':cfg['revision'],'items':None,'totals':quoted,'quote':None,'decision':resolve(db,[])}
        if quote_id is None:self.fail(409,'quote_required')
        quote_id=self.identifier(quote_id)
        row=db.execute('SELECT * FROM payment_routing_quotes WHERE id=? AND owner=?',(quote_id,self.owner)).fetchone()
        if not row or row['purpose']!='new_order':self.fail(409,'quote_stale')
        snap=json.loads(row['snapshot_data'])
        if snap['intentFingerprint']!=fingerprint(semantic):self.fail(409,'quote_intent_mismatch')
        usability=self.quote_usability(db,row)
        if not usability['usable']:self.fail(409,usability['reasonCode'])
        currency,subtotal,shipping,tax=totals
        if snap['totals']!={'currency':currency,'subtotalMinor':subtotal,'shippingMinor':shipping,'taxMinor':tax,'totalMinor':subtotal+shipping+tax}:self.fail(409,'quote_stale')
        return {'mode':'enforced_sandbox','policyRevision':row['policy_revision'],'items':snap['items'],'totals':snap['totals'],'quote':dict(row),'decision':snap['decision']}

    def begin_order(self,db,oid,admission):
        guard=str(uuid4());cfg=config(db)
        if cfg['mode']!=admission['mode'] or cfg['revision']!=admission['policyRevision']:self.fail(409,'quote_stale')
        if admission['mode']=='enforced_sandbox' and context()['digest']!=admission['quote']['context_digest']:self.fail(409,'quote_stale')
        db.execute('INSERT INTO payment_routing_atomic_guards SELECT ?,CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_orders WHERE id=?) THEN 1 ELSE 0 END',(guard,oid))
        admission['guard']=guard

    def capture_route(self,db,order,admission):
        quote=admission['quote'];decision=admission['decision'];enforced=admission['mode']=='enforced_sandbox'
        if not enforced:
            items=[]
            for line in db.execute('SELECT * FROM commerce_order_items WHERE order_id=? ORDER BY sku_id',(order['id'],)):
                data=json.loads(line['snapshot_data']);member=db.execute('SELECT data FROM membership_order_snapshots WHERE item_id=?',(line['id'],)).fetchone()
                digital=db.execute('SELECT * FROM digital_order_snapshots WHERE item_id=?',(line['id'],)).fetchone()
                p=db.execute('SELECT version FROM commerce_products WHERE id=?',(line['product_id'],)).fetchone()
                items.append({'skuId':line['sku_id'],'productId':line['product_id'],'quantity':line['quantity'],'type':line['type'],
                    'classification':CLASSIFIER.get(line['type']),'title':line['title'],'environment':'sandbox',
                    'priceMinor':line['price_minor'],'unitPriceMinor':line['price_minor'],'currency':line['currency'],
                    'unitShippingMinor':line['unit_shipping_minor'],'unitTaxMinor':line['unit_tax_minor'],'priceVersion':line['price_version'],
                    'productVersion':p['version'],'contentId':line['content_id'],'options':data.get('options',[]),'refundPolicy':data.get('refundPolicy',''),
                    'membershipTerms':json.loads(member['data']) if member else None,
                    'digitalTerms':{**json.loads(digital['policy_snapshot']),'contentId':digital['content_id'],'mediaId':digital['media_id']} if digital else None})
            admission['items']=items
        if enforced and context()['digest']!=quote['context_digest']:self.fail(409,'quote_stale')
        snap={'schema':1,'mode':admission['mode'],'matrixApplied':enforced,'channel':'sandbox','contextRequired':enforced,
              'policyRevision':admission['policyRevision'],'ruleVersion':decision['ruleVersion'] if enforced else '',
              'contextDigest':quote['context_digest'] if enforced else None,'quoteId':quote['id'] if enforced else None,
              'created':order['created'],'productionEnabled':False,'orderFingerprint':order['fingerprint'],
              'items':admission['items'],'totals':admission['totals'],'decision':decision,'admissionGuard':admission['guard']}
        db.execute('INSERT INTO commerce_order_payment_routes VALUES(?,?,?,?,?,?,?,?,?,?)',(order['id'],order['owner'],admission['mode'],quote['id'] if enforced else None,
            admission['policyRevision'],quote['context_digest'] if enforced else '',int(enforced),canonical(snap),fingerprint(snap),order['created']))
        if enforced:db.execute('INSERT INTO payment_routing_quote_consumptions VALUES(?,?,?,?)',(quote['id'],order['id'],order['owner'],order['created']))
        db.execute('INSERT INTO payment_routing_atomic_guards SELECT ?,CASE WHEN EXISTS(SELECT 1 FROM commerce_order_payment_routes WHERE order_id=? AND owner=?) THEN 1 ELSE 0 END',(str(uuid4()),order['id'],order['owner']))
        # All proofs are transaction-local and must leave no retained personal payload.
        db.execute('DELETE FROM payment_routing_atomic_guards')

    def authorize_manual_pay(self,db,order):
        if config(db)['mode']=='paused':self.fail(503,'routing_paused')
        route=db.execute('SELECT mode FROM commerce_order_payment_routes WHERE order_id=?',(order['id'],)).fetchone()
        if not route or route['mode']=='legacy_sandbox':return order_usability(db,order,stamp=self.clock())
        view=order_usability(db,order,stamp=self.clock())
        if not view['usable']:self.fail(503 if view['reasonCode']=='routing_paused' else 409,view['reasonCode'])
        return view

    def manual_guard(self,db,order,proof):
        """Final new-manual-initiation check; never called by callback/query/late."""
        route=db.execute('SELECT mode FROM commerce_order_payment_routes WHERE order_id=?',(order['id'],)).fetchone()
        enforced=bool(route and route['mode']=='enforced_sandbox')
        if enforced:
            current=context()
            if not current['ready'] or current['digest']!=proof['currentContextDigest']:self.fail(409,'route_reconfirmation_required')
        guard=str(uuid4())
        sql='''INSERT INTO payment_routing_atomic_guards
          SELECT ?,CASE WHEN EXISTS(SELECT 1 FROM commerce_orders o JOIN payment_routing_config c ON c.id=1
          WHERE o.id=? AND o.owner=? AND o.environment='sandbox' AND o.status='awaiting_payment'
          AND o.payment_status='unpaid' AND o.reserved_until>'''+DB_NOW+'''
          AND json_extract(c.data,'$.mode')=? AND json_extract(c.data,'$.mode')!='paused'
          AND json_extract(c.data,'$.revision')=? AND (?=0 OR
            (json_extract(c.data,'$.mode')='enforced_sandbox' AND json_type(c.data,'$.confirmed')='true'
             AND json_extract(c.data,'$.contextDigest')=? AND
             (EXISTS(SELECT 1 FROM commerce_order_payment_routes r WHERE r.order_id=o.id AND r.owner=o.owner
               AND r.policy_revision=json_extract(c.data,'$.revision') AND r.context_digest=?)
              OR EXISTS(SELECT 1 FROM payment_routing_confirmations f WHERE f.order_id=o.id AND f.owner=o.owner
               AND f.policy_revision=json_extract(c.data,'$.revision') AND f.context_digest=? AND f.expires>'''+DB_NOW+'''))))
          ) THEN 1 ELSE 0 END'''
        db.execute(sql,(guard,order['id'],order['owner'],proof['currentMode'],proof['currentPolicyRevision'],int(enforced),
            proof['currentContextDigest'],proof['currentContextDigest'],proof['currentContextDigest']))
        db.execute('DELETE FROM payment_routing_atomic_guards WHERE id=?',(guard,))

    def confirmation_view(self,row):
        return {'id':row['id'],'orderId':row['order_id'],'quoteId':row['quote_id'],'policyRevision':row['policy_revision'],
                'contextDigest':row['context_digest'],'created':row['created'],'expires':row['expires'],'productionEnabled':False}

    def confirm(self,oid,data):
        if set(data)!={'requestId','quoteId','confirmed'} or data['confirmed'] is not True:self.fail(400,'invalid_request')
        request=self.identifier(data['requestId']);qid=self.identifier(data['quoteId']);token=fingerprint({'orderId':oid,'quoteId':qid,'confirmed':True})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');order=self.commerce().own_order(db,oid)
            old=db.execute('SELECT * FROM payment_routing_confirmations WHERE owner=? AND request_id=?',(self.owner,request)).fetchone()
            if old:
                if old['fingerprint']!=token:self.fail(409,'request_conflict')
                return {'confirmation':self.confirmation_view(old),'route':route_summary(db,order),'currentUsability':order_usability(db,order),'productionEnabled':False}
            q=db.execute('SELECT * FROM payment_routing_quotes WHERE id=? AND owner=?',(qid,self.owner)).fetchone()
            if not q or q['purpose']!='order_reconfirm' or q['order_id']!=oid:self.fail(409,'quote_stale')
            if db.execute('SELECT 1 FROM payment_routing_confirmations WHERE quote_id=?',(qid,)).fetchone():self.fail(409,'quote_consumed')
            usability=self.quote_usability(db,q)
            if not usability['usable']:self.fail(409,usability['reasonCode'])
            stamp=self.clock();ident=str(uuid4());snapshot=json.loads(q['snapshot_data'])
            data={'schema':1,'orderFingerprint':order['fingerprint'],'quoteId':qid,'items':snapshot['items'],'totals':snapshot['totals'],
                  'decision':snapshot['decision'],'originalTerms':snapshot['originalTerms']}
            if context()['digest']!=q['context_digest']:self.fail(409,'quote_stale')
            db.execute('INSERT INTO payment_routing_confirmations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(ident,self.owner,oid,qid,request,token,q['policy_revision'],q['context_digest'],canonical(data),fingerprint(data),stamp,stamp+TTL))
            row=db.execute('SELECT * FROM payment_routing_confirmations WHERE id=?',(ident,)).fetchone()
            return {'confirmation':self.confirmation_view(row),'route':route_summary(db,order),'currentUsability':order_usability(db,order),'productionEnabled':False}

    def validate_config(self,data):
        if set(data)!=set(DEFAULT) or type(data.get('revision')) is not int or data['revision']<0 or data.get('mode') not in MODES or type(data.get('confirmed')) is not bool or data.get('productionEnabled') is not False:self.fail(400,'invalid_config')
        if not isinstance(data['ruleVersion'],str) or len(data['ruleVersion'])>100 or data['ruleVersion']!=data['ruleVersion'].strip() or not isinstance(data['contextDigest'],str) or (data['contextDigest'] and not re.fullmatch('[a-f0-9]{64}',data['contextDigest'])):self.fail(400,'invalid_config')
        rules=data['rules']
        if not isinstance(rules,list) or len(rules)>500:self.fail(400,'invalid_rules')
        ids=set();matches=set()
        for r in rules:
            if not isinstance(r,dict) or set(r)!={'id','environment','platform','region','classification','currency','channel','reference'}:self.fail(400,'invalid_rules')
            self.identifier(r['id'])
            if r['environment']!='sandbox' or r['platform'] not in PLATFORMS or r['classification'] not in CLASSIFICATIONS or r['channel'] not in CHANNELS or not isinstance(r['region'],str) or not re.fullmatch('[A-Z]{2}',r['region']) or not isinstance(r['currency'],str) or not re.fullmatch('[A-Z]{3}',r['currency']) or not isinstance(r['reference'],str) or len(r['reference'])>1000:self.fail(400,'invalid_rules')
            key=tuple(r[k] for k in ('environment','platform','region','classification','currency'))
            if r['id'] in ids or key in matches:self.fail(400,'rule_ambiguous')
            ids.add(r['id']);matches.add(key)
        ctx=context()
        if data['mode']=='enforced_sandbox' and (not data['confirmed'] or not data['ruleVersion'] or not ctx['ready'] or data['contextDigest']!=ctx['digest']):self.fail(409,'context_confirmation_required')

    def admin_view(self,db,query):
        before=query.get('before',[''])[0];args=[];where='1'
        if before:
            cursor=db.execute('SELECT revision FROM payment_routing_versions WHERE id=?',(before,)).fetchone()
            if not cursor:self.fail(400,'invalid_cursor')
            where='revision<?';args=[cursor['revision']]
        rows=db.execute('SELECT * FROM payment_routing_versions WHERE '+where+' ORDER BY revision DESC LIMIT 51',args).fetchall()
        versions=[{'id':r['id'],'revision':r['revision'],'ruleVersion':r['rule_version'],'contextDigest':r['context_digest'],'config':json.loads(r['data']),'created':r['created']} for r in rows[:50]]
        return {'config':config(db),'versions':versions,'next':rows[49]['id'] if len(rows)>50 else None,'context':context(),
                'adapterReadiness':[{'channel':channel,'ready':channel=='sandbox','productionEnabled':False,'reasonCode':'ready_sandbox' if channel=='sandbox' else 'adapter_unavailable'} for channel in CHANNELS],'productionEnabled':False}

    def route(self,method,path):
        admin='/api/admin/payment-routing'
        match=re.fullmatch(r'/api/commerce/orders/([^/]+)/payment-route/(quote|confirm)',path)
        quote_get=re.fullmatch(r'/api/commerce/quotes/([^/]+)',path)
        if path not in (admin,admin+'/preview','/api/commerce/payment-context','/api/commerce/quote') and not match and not quote_get:return None
        if path=='/api/commerce/payment-context' and method=='GET':
            with self.store.connect() as db:return {'mode':config(db)['mode'],'context':context(),'productionEnabled':False}
        self.owner=self.h.require(['admin'] if path.startswith(admin) else None)['id']
        self.rate('payment-routing:'+('read:' if method=='GET' else 'write:')+self.owner,180 if method=='GET' else 30)
        query=parse_qs(urlsplit(self.h.path).query)
        if path.startswith(admin):
            if path==admin and method=='GET':
                with self.store.connect() as db:return self.admin_view(db,query)
            if path==admin and method=='PATCH':
                data=self.body();self.validate_config(data)
                with self.store.connect() as db:
                    db.execute('BEGIN IMMEDIATE');current=config(db)
                    if current['revision']!=data['revision']:self.fail(409,'config_changed')
                    self.validate_config(data);value={**data,'revision':current['revision']+1};raw=canonical(value)
                    db.execute('INSERT INTO payment_routing_versions VALUES(?,?,?,?,?,?,?,?)',(str(uuid4()),value['revision'],value['ruleVersion'],value['contextDigest'],raw,fingerprint(value),self.owner,self.clock()))
                    changed=db.execute('UPDATE payment_routing_config SET data=? WHERE id=1 AND json_extract(data,\'$.revision\')=?',(raw,current['revision'])).rowcount
                    if changed!=1:self.fail(409,'config_changed')
                    self.store.audit(db,self.owner,'payment_routing.config','sandbox','sandbox mode/revision; production disabled')
                    return self.admin_view(db,{})
            if path==admin+'/preview' and method=='POST':
                data=self.body()
                if set(data)!={'context','items','environment'} or data['environment']!='sandbox' or not isinstance(data['context'],dict) or set(data['context'])!={'platform','region'}:self.fail(400,'invalid_request')
                ctx=data['context']
                if ctx['platform'] not in PLATFORMS or not isinstance(ctx['region'],str) or not re.fullmatch('[A-Z]{2}',ctx['region']):self.fail(400,'invalid_request')
                simulation={**ctx,'ready':True,'digest':None}
                with self.store.connect() as db:
                    items,totals,bindings=self.read_facts(db,self.commerce().items(data['items']),{},preview=True)
                    return {'simulation':True,'decision':resolve(db,items,simulation=simulation),'groups':self.groups(db,items,simulation),'productionEnabled':False}
            self.fail(405,'method_not_allowed')
        if path=='/api/commerce/quote' and method=='POST':return self.create_quote(self.body())
        if quote_get and method=='GET':
            ident=self.identifier(unquote(quote_get[1],errors='strict'))
            with self.store.connect() as db:
                row=db.execute('SELECT * FROM payment_routing_quotes WHERE id=? AND owner=?',(ident,self.owner)).fetchone()
                if not row:self.fail(404,'quote_not_found')
                return {'quote':self.quote_view(db,row),'productionEnabled':False}
        if match and method=='POST':
            oid=self.identifier(unquote(match[1],errors='strict'))
            return self.create_quote(self.body(),order_id=oid) if match[2]=='quote' else self.confirm(oid,self.body())
        self.fail(405,'method_not_allowed')
