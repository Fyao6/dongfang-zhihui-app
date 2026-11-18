"""Owned fresh HTTP smoke, not the formal stage acceptance suite."""
import hashlib,hmac,http.cookiejar,json,os,pathlib,sys,threading,time,traceback,io,wave
from urllib.request import build_opener,ProxyHandler,HTTPCookieProcessor,Request
from urllib.error import HTTPError
from uuid import uuid4

ROOT=pathlib.Path(__file__).resolve().parent.parent
BACKEND=ROOT/'04_研发源码/app/r4/backend'
sys.path.insert(0,str(BACKEND))
from server import Store,make_handler,ThreadingHTTPServer

def main():
    run=uuid4().hex[:12];prefix='负责人优化建议-支付路由Python组件-'+run
    dbpath=ROOT/'06_验证与后续工作'/(prefix+'.sqlite3')
    reportpath=dbpath.with_suffix('.json');checks=[]
    secret=uuid4().hex+uuid4().hex
    os.environ.update(EW_PAYMENT_CALLBACK_SANDBOX_ENABLED='1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF='EW_PAYMENT_CALLBACK_COMPONENT_SECRET',EW_PAYMENT_CALLBACK_COMPONENT_SECRET=secret,
        EW_PAYMENT_ROUTING_SANDBOX_CONTEXT_ENABLED='1',EW_PAYMENT_ROUTING_SANDBOX_CONTEXT_JSON=json.dumps({'schema':1,'id':'component-web','revision':1,'platform':'web','region':'US'}))
    store=Store(dbpath)
    ActualHandler=make_handler(store,ROOT/'03_可查看原型')
    class ComponentHandler(ActualHandler):
        def api(self,method,path):
            try:return super().api(method,path)
            except Exception as exc:
                self.server.component_error=type(exc).__name__+': '+str(exc)
                raise
    server=ThreadingHTTPServer(('127.0.0.1',0),ComponentHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    opener=build_opener(ProxyHandler({}),HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def api(method,path,data=None,expected=200,headers=None):
        raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode() if data is not None else None
        req=Request(base+path,data=raw,method=method,headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with opener.open(req,timeout=12) as r:status=r.status;out=json.loads(r.read())
        except HTTPError as r:status=r.code;out=json.loads(r.read())
        if status!=expected:raise AssertionError((method,path,status,out))
        return out
    def check(label,assertion=True):
        if not assertion:raise AssertionError(label)
        checks.append({'name':label,'pass':True})
    def cfg(mode,rule='component-v1'):
        current=api('GET','/api/admin/payment-routing')['config']
        ctx=api('GET','/api/commerce/payment-context')['context']
        return api('PATCH','/api/admin/payment-routing',{**current,'mode':mode,'confirmed':True,'ruleVersion':rule,
            'contextDigest':ctx['digest'],'rules':[{'id':classification+'-us','environment':'sandbox','platform':'web','region':'US',
              'classification':classification,'currency':'USD','channel':'sandbox','reference':'synthetic component'} for classification in ('physical_goods','digital_content','digital_membership')]})
    try:
        with store.connect() as db:
            for table in ('payment_routing_config','payment_routing_versions','payment_routing_quotes','commerce_order_payment_routes',
                          'payment_routing_quote_consumptions','payment_routing_confirmations','payment_routing_atomic_guards','commerce_payment_events','payment_late_cases'):
                columns=list(db.execute('PRAGMA table_info('+table+')'))
                db.execute('EXPLAIN INSERT INTO '+table+' VALUES('+','.join('?' for _ in columns)+')',tuple(None for _ in columns)).fetchall()
        check('all seven tables and trusted ledger/late trigger INSERT statements compile against actual Store')
        api('POST','/api/auth/setup',{'username':'routing_'+run,'password':secret,'name':'Synthetic Routing'})
        api('PATCH','/api/admin/commerce/settings',{'sandboxEnabled':True,'productionEnabled':False})
        data={'title':'Synthetic item','description':'Local fixture only','type':'physical','environment':'sandbox','status':'published',
              'currency':'USD','sku':'test-'+run,'priceMinor':100,'stock':20,'shippingCountries':['US'],'shippingMinor':5,'taxMinor':2,'refundPolicy':'Synthetic refund terms'}
        product=api('POST','/api/admin/commerce/products',data)['item'];sku=product['skuId']
        intent={'environment':'sandbox','items':[{'skuId':sku,'quantity':1}],'shippingAddress':{'name':'Synthetic','country':'US','address':'Synthetic address'}}
        legacy=api('POST','/api/commerce/orders',{**intent,'requestId':'legacy'})
        check('legacy immutable minimum route',legacy['paymentRoute']['mode']=='legacy_sandbox' and legacy['paymentRoute']['matrixApplied'] is False)
        legacy_paid=api('POST','/api/commerce/orders/'+legacy['id']+'/sandbox-pay',{'requestId':'legacy-pay'})
        check('legacy actual paid ledger',legacy_paid['paymentStatus']=='paid')
        api('PATCH','/api/admin/membership/settings',{'sandboxEnabled':True,'productionEnabled':False,'revision':0})
        mp=api('POST','/api/admin/commerce/products',{'title':'Synthetic membership','type':'membership','environment':'sandbox','status':'published',
            'currency':'USD','sku':'member-'+run,'priceMinor':150,'stock':20})['item']
        api('POST','/api/admin/membership/plans',{'environment':'sandbox','status':'published','skuId':mp['skuId'],'groupId':'component',
            'title':'Synthetic membership','description':'Only fixture','billingMode':'one_time','term':{'unit':'month','count':1},'renewalPriceMinor':None,
            'benefits':{'catalogScope':'none','courseIds':[],'aiCredits':None,'aiResetCycle':'none','other':[]},'ruleVersion':'component-v1',
            'termsVersion':'component-v1','serviceTerms':'Synthetic finite terms','refundPolicy':'Synthetic refund','graceDays':0,'trialDays':0,'promotionsEnabled':False})
        mo=api('POST','/api/commerce/orders',{'requestId':'member-order','environment':'sandbox','items':[{'skuId':mp['skuId'],'quantity':1}]})
        paidmember=api('POST','/api/commerce/orders/'+mo['id']+'/sandbox-pay',{'requestId':'member-pay'})
        check('legacy member original capture and activation preserved',paidmember['membershipProcessing']['status']=='linked')
        cfg('enforced_sandbox')
        admin_opener=opener;opener=build_opener(ProxyHandler({}),HTTPCookieProcessor(http.cookiejar.CookieJar()))
        api('POST','/api/auth/register',{'username':'buyer_'+run,'password':secret,'name':'Synthetic Buyer'})
        mi={'requestId':'member-quote','environment':'sandbox','items':[{'skuId':mp['skuId'],'quantity':1}]}
        mq=api('POST','/api/commerce/quote',mi)['quote']
        me=api('POST','/api/commerce/orders',{**mi,'requestId':'member-enforced','quoteId':mq['id']})
        mep=api('POST','/api/commerce/orders/'+me['id']+'/sandbox-pay',{'requestId':'member-enforced-pay'})
        check('enforced member actual frozen terms capture and activation',mep['membershipProcessing']['status']=='linked')
        opener=admin_opener
        course='course-'+run
        api('POST','/api/admin/content/courses',{'item':{'id':course,'zh':'Synthetic isolated course','sandboxOnly':True,'mediaUrl':'','audioUrl':'','creatorId':'','categoryIds':[]},'status':'published'})
        audio=io.BytesIO()
        with wave.open(audio,'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000);wav.writeframes(b'\0\0'*64)
        with opener.open(Request(base+'/api/media',method='POST',data=audio.getvalue(),headers={'Content-Type':'audio/wav','X-Filename':'synthetic.wav'}),timeout=12) as r:media=json.loads(r.read())
        policy=api('GET','/api/admin/digital-entitlements')['policy']
        policy=api('PATCH','/api/admin/digital-entitlements',{**policy,'enabled':True,'confirmed':True,'ruleVersion':'component-v1','validityDays':2,'usesPerUnit':3})['policy']
        api('POST','/api/admin/digital-entitlements/assets',{'contentId':course,'mediaId':media['id'],'sandboxOnly':True})
        dp=api('POST','/api/admin/commerce/products',{'title':'Synthetic finite course','description':'Local fixture','type':'digital','contentId':course,
            'environment':'sandbox','status':'published','currency':'USD','sku':'digital-'+run,'priceMinor':175,'stock':20})['item']
        di={'requestId':'digital-quote','environment':'sandbox','items':[{'skuId':dp['skuId'],'quantity':1}]}
        dq=api('POST','/api/commerce/quote',di)['quote'];de=api('POST','/api/commerce/orders',{**di,'requestId':'digital-enforced','quoteId':dq['id']})
        dep=api('POST','/api/commerce/orders/'+de['id']+'/sandbox-pay',{'requestId':'digital-pay'})
        grants=api('GET','/api/digital-entitlements')['items']
        check('enforced finite digital actual snapshot and unique grant',dep['paymentStatus']=='paid' and sum(x['orderId']==de['id'] for x in grants)==1)
        cfg('legacy_sandbox')
        api('PATCH','/api/admin/digital-entitlements',{**policy,'enabled':False})
        api('POST','/api/commerce/orders',{**di,'requestId':'legacy-disabled-digital'},503)
        check('legacy digital disabled admission retains original 503')
        cfg('enforced_sandbox')
        euro=api('POST','/api/admin/commerce/products',{**data,'sku':'euro-'+run,'currency':'EUR'})['item']
        mixed={**intent,'items':[{'skuId':sku,'quantity':1},{'skuId':euro['skuId'],'quantity':1}]}
        split=api('POST','/api/commerce/quote',{**mixed,'requestId':'split-before-unmatched'})['quote']
        preview=api('POST','/api/admin/payment-routing/preview',{'context':{'platform':'web','region':'US'},'environment':'sandbox','items':mixed['items']})
        check('R4 original currency split precedes missing rule while groups preserve real decisions',split['decision']['reasonCode']=='split_required'
            and preview['decision']['reasonCode']=='split_required' and any(g['decision']['reasonCode']=='rule_unmatched' for g in split['groups']))
        quote=api('POST','/api/commerce/quote',{**intent,'requestId':'quote-one'})['quote']
        check('enforced actual quote ready with true money/terms',quote['usability']['usable'] and quote['totals']['totalMinor']==107 and quote['items'][0]['unitPriceMinor']==100 and quote['items'][0]['refundPolicy']=='Synthetic refund terms')
        created=api('POST','/api/commerce/orders',{**intent,'requestId':'enforced-one','quoteId':quote['id']})
        check('quote consumed and route atomic',created['paymentRoute']['quoteId']==quote['id'])
        again=api('POST','/api/commerce/orders',{**intent,'requestId':'different-request','quoteId':quote['id']},409)
        check('quote single consumption',again['error']=='quote_consumed')
        cfg('paused')
        replay=api('POST','/api/commerce/orders',{**intent,'requestId':'enforced-one','quoteId':quote['id']})
        check('paused permits original order intent replay',replay['id']==created['id'])
        denied=api('POST','/api/commerce/orders/'+created['id']+'/sandbox-pay',{'requestId':'denied-pay'},503)
        check('paused rejects new manual initiation',denied['error']=='routing_paused')
        event={'eventId':'event-'+run,'transactionId':'transaction-'+run,'orderId':created['id'],'type':'payment.succeeded','amountMinor':107,'currency':'USD'}
        raw=json.dumps(event,ensure_ascii=False,separators=(',',':')).encode();stamp=str(int(time.time()))
        signature=hmac.new(secret.encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
        received=api('POST','/api/payment-callbacks/sandbox',event,202,{'X-EW-Callback-Timestamp':stamp,'X-EW-Callback-Signature':signature})
        api('POST','/api/admin/payment-callbacks/process',{'limit':1})
        paid=api('GET','/api/commerce/orders/'+created['id'])
        check('paused does not reject trusted signed callback',received['accepted'] and paid['paymentStatus']=='paid')
        cfg('enforced_sandbox','component-v2')
        q=api('POST','/api/commerce/quote',{**intent,'requestId':'quote-two'})['quote']
        order=api('POST','/api/commerce/orders',{**intent,'requestId':'enforced-two','quoteId':q['id']})
        cfg('enforced_sandbox','component-v3')
        denied=api('POST','/api/commerce/orders/'+order['id']+'/sandbox-pay',{'requestId':'stale-pay'},409)
        check('changed policy requires explicit reconfirmation',denied['error']=='route_reconfirmation_required')
        q3=api('POST','/api/commerce/quote',{**intent,'requestId':'quote-three'})['quote']
        order3=api('POST','/api/commerce/orders',{**intent,'requestId':'enforced-three','quoteId':q3['id']})
        current=next(x for x in api('GET','/api/admin/commerce')['products'] if x['id']==product['id'])
        api('POST','/api/admin/commerce/products',{**data,'id':product['id'],'version':current['version'],'stock':current['stock'],'priceMinor':200})
        pay3=api('POST','/api/commerce/orders/'+order3['id']+'/sandbox-pay',{'requestId':'original-price-pay'})
        check('current price change preserves original enforced payable terms',pay3['totalMinor']==107 and pay3['paymentStatus']=='paid')
        rq=api('POST','/api/commerce/orders/'+order['id']+'/payment-route/quote',{'requestId':'route-quote'})['quote']
        check('reconfirm quote keeps original price despite current SKU change',rq['items'][0]['unitPriceMinor']==100 and rq['totals']['totalMinor']==107)
        confirmed=api('POST','/api/commerce/orders/'+order['id']+'/payment-route/confirm',{'requestId':'route-confirm','quoteId':rq['id'],'confirmed':True})
        check('confirmation immutable append',confirmed['currentUsability']['usable'] and confirmed['route']['policyRevision']==order['paymentRoute']['policyRevision'])
        pay=api('POST','/api/commerce/orders/'+order['id']+'/sandbox-pay',{'requestId':'confirmed-pay'})
        check('reconfirmed manual payment uses original price',pay['paymentStatus']=='paid' and pay['totalMinor']==107)
        late_orders=[]
        for label in ('late-fulfilled','late-refund'):
            quote_late=api('POST','/api/commerce/quote',{**intent,'requestId':label+'-quote'})['quote']
            late_orders.append(api('POST','/api/commerce/orders',{**intent,'requestId':label,'quoteId':quote_late['id']}))
        # Explicit owned fixture clock mutation: do not claim a real 15-minute wait.
        with store.connect() as db:
            for value in late_orders:db.execute('UPDATE commerce_orders SET reserved_until=? WHERE id=?',(int(time.time()*1000)-10,value['id']))
        for value in late_orders:
            check('owned expired order releases held '+value['requestId'],api('GET','/api/commerce/orders/'+value['id'])['paymentStatus']=='expired')
        cfg('paused')
        for index,value in enumerate(late_orders):
            if index:
                current=next(x for x in api('GET','/api/admin/commerce')['products'] if x['id']==product['id'])
                api('POST','/api/admin/commerce/products',{**data,'id':product['id'],'version':current['version'],'stock':0,'priceMinor':200})
            event={'eventId':'late-event-'+str(index)+'-'+run,'transactionId':'late-tx-'+str(index)+'-'+run,'orderId':value['id'],'type':'payment.succeeded','amountMinor':207,'currency':'USD'}
            raw=json.dumps(event,ensure_ascii=False,separators=(',',':')).encode();stamp=str(int(time.time()))
            signature=hmac.new(secret.encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
            api('POST','/api/payment-callbacks/sandbox',event,202,{'X-EW-Callback-Timestamp':stamp,'X-EW-Callback-Signature':signature})
            api('POST','/api/admin/payment-callbacks/process',{'limit':1})
            result=api('GET','/api/commerce/orders/'+value['id'])
            check('trusted late fulfilment' if not index else 'trusted late refund pending fact without fake paid ledger',
                result['latePayment']['status']==('fulfilled' if not index else 'refund_pending'))
        export=api('GET','/api/privacy/export')['serverData']
        check('本人safe export includes route facts without address duplicate','orderPaymentRoutes' in export and all('fingerprint' not in x and 'snapshot_data' not in x for x in export['orderPaymentRoutes']))
        with store.connect() as db:
            check('atomic proofs leave zero rows',db.execute('SELECT count(*) FROM payment_routing_atomic_guards').fetchone()[0]==0)
            try:
                db.execute('UPDATE commerce_order_payment_routes SET policy_revision=999')
            except Exception as exc:
                check('frozen route mutation rejected','payment_routing_immutable' in str(exc));db.rollback()
            else:raise AssertionError('route mutable')
    except Exception as exc:
        checks.append({'name':'component failure','pass':False,'error':str(exc)[:1200]})
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
        report={'formalAcceptance':False,'scope':'owned fresh actual HTTP backend component; no current UI/build acceptance','runId':run,'database':str(dbpath),'base':base,
            'passed':sum(x['pass'] for x in checks),'failed':sum(not x['pass'] for x in checks),'checks':checks,
            'sourceHashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [BACKEND/(n+'.py') for n in ('payment_routing','commerce','server','privacy','privacy_domains')]+[BACKEND/'payment_routing_schema.sql']},
            'syntheticDataOnly':True,'productionEnabled':False,'ownServerStopped':not thread.is_alive(),'backendError':getattr(server,'component_error',None),
            'fixtureMutations':[{'target':'two actual API-created late orders','field':'reserved_until','purpose':'explicit owned expiry; no claim of real fifteen-minute wait'}]}
        reportpath.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'report':str(reportpath),'passed':report['passed'],'failed':report['failed'],'errors':[x for x in checks if not x['pass']],'backendError':report['backendError']},ensure_ascii=False))
    return report['failed']

if __name__=='__main__':raise SystemExit(main())
