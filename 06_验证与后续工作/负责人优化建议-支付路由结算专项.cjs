'use strict';
// Checks 25–32. Every successful payment is an actual product transaction or signed fixture response.
const assert=require('node:assert/strict');
const digitalFixtures=require('./负责人优化建议-数字权益用例工具.cjs');

module.exports=async function settlementChecks({h,a,f,api,check,key}){
 let primary,secondary;
 const buyer=async()=>primary||(primary=await h.register('route-settle'));
 const stranger=async()=>secondary||(secondary=await h.register('route-other'));
 const actor=p=>p.c||p;
 const endpoint=o=>'commerce/orders/'+encodeURIComponent(o.id)+'/payment-recovery';
 const byOrder=(rows,id)=>rows.filter(row=>row.order_id===id);
 async function facts(id){
  const t=await f.snapshot(['commerce_orders','commerce_order_items','commerce_reservations','commerce_order_payment_routes',
    'payment_routing_quote_consumptions','payment_routing_confirmations','commerce_payment_events','commerce_entitlements']);
  return {order:t.commerce_orders.find(x=>x.id===id),items:byOrder(t.commerce_order_items,id),reservations:byOrder(t.commerce_reservations,id),
   routes:byOrder(t.commerce_order_payment_routes,id),consumptions:byOrder(t.payment_routing_quote_consumptions,id),
   confirmations:byOrder(t.payment_routing_confirmations,id),ledger:byOrder(t.commerce_payment_events,id),entitlements:byOrder(t.commerce_entitlements,id)};
 }
 async function receiptDone(receipt){
  for(let i=0;i<10;i++){
   const detail=await f.callbackDetail(receipt.receiptId);
   if(['applied','manual_review'].includes(detail.item.status))return detail;
   await f.processCallbacks(10);
  }
  throw Error('Actual receipt did not reach a durable terminal status within bounded consumer batches');
 }
 const equalAdmission=(before,after)=>{
  assert.deepEqual(after.routes,before.routes);assert.deepEqual(after.items,before.items);
  assert.deepEqual(after.reservations,before.reservations);assert.deepEqual(after.ledger,before.ledger);
  assert.deepEqual(after.entitlements,before.entitlements);assert.deepEqual(after.order,before.order);
 };

 await check('25 原价重新确认只追加事实，目的/归属/确认与幂等不能改成交及预占',async()=>{
  const p=await buyer(),other=await stranger();await f.enforce();
  const product=await f.product('原价重确认',{priceMinor:731}),q=await f.quote(p,product),order=await f.consume(p,q),before=await facts(order.id);
  await f.updateProduct(product,{priceMinor:1193});await f.enforce();
  const denied=await f.pay(p,order,{expected:409});assert.equal(denied.error,'route_reconfirmation_required');
  const rq=(await f.reconfirmQuote(p,order)).quote;
  assert.equal(rq.purpose,'order_reconfirm');assert.equal(rq.orderId,order.id);
  assert.equal(rq.items[0].unitPriceMinor,731);assert.equal(rq.totals.totalMinor,order.totalMinor);
  await api(other.c,'commerce/quotes/'+encodeURIComponent(rq.id),undefined,'GET',404);
  await api(other.c,'commerce/orders/'+order.id+'/payment-route/quote',{requestId:key('foreign_reconfirm')},'POST',404);
  await f.confirm(other,order,rq,{expected:404});await f.confirm(p,order,q,{expected:409});
  await f.confirm(p,order,rq,{confirmed:false,expected:400});
  const requestId=key('one_confirmation'),confirmed=await f.confirm(p,order,rq,{requestId});
  assert.equal(confirmed.currentUsability.usable,true);assert.equal(confirmed.route.policyRevision,order.paymentRoute.policyRevision);
  const replay=await f.confirm(p,order,rq,{requestId});assert.deepEqual(replay.confirmation,confirmed.confirmation);
  const rq2=(await f.reconfirmQuote(p,order)).quote;await f.confirm(p,order,rq2,{requestId,expected:409});
  await f.config({mode:'paused'});const pausedReplay=await f.confirm(p,order,rq,{requestId});
  assert.deepEqual(pausedReplay.confirmation,confirmed.confirmation);assert.equal(pausedReplay.currentUsability.usable,false);
  const after=await facts(order.id);equalAdmission(before,after);assert.equal(after.confirmations.length,1);
 });

 await check('26 确认期限以真实SQL时钟到期，过期单不复活且规格身份变化须主动新单',async()=>{
  const p=await buyer();await f.enforce();const product=await f.product('确认期限'),q=await f.quote(p,product),order=await f.consume(p,q);
  await f.enforce();const rq=(await f.reconfirmQuote(p,order)).quote;
  await h.prepareRoutingWrites(p.c,2);await h.control({action:'routing-clock',offsetMs:-298000});
  let confirmed;try{confirmed=await f.confirm(p,order,rq);}finally{await h.control({action:'routing-clock',offsetMs:null});}
  assert.equal(confirmed.confirmation.expires-confirmed.confirmation.created,300000);
  const started=Date.now();await new Promise(resolve=>setTimeout(resolve,Math.max(0,confirmed.confirmation.expires-Date.now()+180)));
  (h.report.expiryProof??=[]).push({confirmationId:confirmed.confirmation.id,fixtureOffsetMs:-298000,ttlMs:300000,
   actualWaitMs:Date.now()-started,sqlClockUnchanged:true,real300SecondsWaitClaimed:false});
  const before=await facts(order.id),denied=await f.pay(p,order,{expected:409});
  assert.equal(denied.error,'route_reconfirmation_required');equalAdmission(before,await facts(order.id));
  await h.control({action:'expire-order',orderId:order.id});const expired=await f.getOrder(p,order.id);
  assert.equal(expired.paymentStatus,'expired');await f.reconfirmQuote(p,order,{expected:409});
  const expiredFacts=await facts(order.id);assert(expiredFacts.reservations.every(row=>row.state==='released'));assert.equal(expiredFacts.ledger.length,0);
  const unsafeProduct=await f.product('规格换绑'),uq=await f.quote(p,unsafeProduct),unsafe=await f.consume(p,uq);
  await f.updateProduct(unsafeProduct,{variants:[{skuId:unsafeProduct.item.skuId,sku:unsafeProduct.item.sku,
   stock:unsafeProduct.item.stock,priceMinor:unsafeProduct.item.priceMinor,active:true,options:[{name:'edition',value:'changed'}]}]});
  const rejected=await f.reconfirmQuote(p,unsafe,{expected:409});assert.equal(rejected.error,'order_requote_required');
  assert.equal((await facts(unsafe.id)).ledger.length,0);
 });

 await check('27 暂停与上下文/规则改变不否认原可信HMAC付款，事件/交易重放仍唯一',async()=>{
  const p=await buyer();await f.enforce();const product=await f.product('可信回调'),q=await f.quote(p,product),order=await f.consume(p,q);
  const originalRoute=(await facts(order.id)).routes;
  await f.config({mode:'paused',ruleVersion:key('new_unrelated_policy')});await h.control({action:'routing-context',mode:'revision2'});
  await f.pay(p,order,{expected:503});
  const eventId=key('signed_event'),transactionId=key('signed_transaction'),receipt=await f.callback(order,{eventId,transactionId});
  assert.equal((await receiptDone(receipt)).item.status,'applied');
  const replay=await f.callback(order,{eventId,transactionId});assert.equal(replay.receiptId,receipt.receiptId);assert.equal(replay.duplicate,true);
  const alias=await f.callback(order,{transactionId});assert.equal(alias.duplicate,true);
  await f.processCallbacks(10);const after=await facts(order.id),paid=await f.getOrder(p,order.id);
  assert.equal(paid.paymentStatus,'paid');assert.equal(after.ledger.filter(x=>x.kind==='sandbox_pay').length,1);
  assert.deepEqual(after.routes,originalRoute);assert(after.reservations.every(x=>x.state==='consumed'));
  const skus=await f.snapshot(['commerce_skus']);const sku=skus.commerce_skus.find(x=>x.id===product.item.skuId);
  assert.equal(sku.stock,99);assert.equal(sku.reserved,0);
 });

 await check('28 本人服务端真实HTTP查单及迟到有货/缺货共用原收据链，退款待办不伪到账',async()=>{
  const p=await buyer();await f.enforce();const normalProduct=await f.product('主动查单'),goodProduct=await f.product('迟到有货'),shortProduct=await f.product('迟到缺货',{stock:1});
  const orders=[];for(const product of [normalProduct,goodProduct,shortProduct])orders.push(await f.consume(p,await f.quote(p,product)));
  for(const order of orders.slice(1)){await h.control({action:'expire-order',orderId:order.id});assert.equal((await f.getOrder(p,order.id)).paymentStatus,'expired');}
  await f.updateProduct(shortProduct,{stock:0});await f.config({mode:'paused'});await h.control({action:'routing-context',mode:'disabled'});
  for(let i=0;i<orders.length;i++){
   const order=orders[i],requestId=key('trusted_query_'+i),transactionId=key('provider_query_transaction_'+i);
   await f.queryFixture({action:'configure',orderId:order.id,mode:'paid',transactionId});
   const result=(await api(p.c,endpoint(order),{requestId})).data;
   assert.equal(result.job.status,i===2?'manual_review':'confirmed');assert.equal(result.order.paymentStatus,i===2?'refund_pending':'paid');
   if(i===2)assert.equal(result.job.lastError,'late_refund_pending');
   await api(p.c,endpoint(order),undefined,'GET');await api(p.c,endpoint(order),{requestId});
   const calls=(await f.queryFixture({action:'stats',orderId:order.id})).calls;assert.equal(calls.length,1);assert(calls[0].verified);
   const durable=await h.control({action:'snapshot',orderId:order.id});
   assert.equal(durable.ledger.filter(x=>x.kind==='sandbox_pay').length,i===2?0:1);
   if(i){assert.equal(durable.lateCases.length,1);assert.equal(durable.lateCases[0].status,i===2?'refund_pending':'fulfilled');}
   if(i===2){assert.equal(durable.order.refunded_minor,0);assert.equal(durable.ledger.filter(x=>x.kind==='refund').length,0);assert.equal(durable.entitlements.length,0);}
  }
  (h.report.routingSettlement??=[]).push({source:'actual signed query HTTP fixture',expiredOrdersPreparedByOwnedControl:2,realFifteenMinuteWaitClaimed:false,productionEnabled:false});
 });

 await check('29 实际会员续期与有限数字权益唯一发放，路由不赠AI或开放正式/裸媒体',async()=>{
  const p=await h.register('route-member');await f.enforce([f.rule('physical_goods'),f.rule('digital_membership'),f.rule('digital_content')]);
  const offer=await f.member('实际续期',{credits:null}),q=await f.quote(p,offer.product),first=await f.consume(p,q);
  const firstPaid=await f.pay(p,first),status=(await api(p.c,'membership/status')).data;
  assert.equal(firstPaid.paymentStatus,'paid');const sub=status.items.find(x=>x.periods.some(period=>period.orderId===first.id));assert(sub);
  const renewalQuote=await f.quote(p,offer.product,{membershipRenewalOf:sub.id}),renewal=await f.consume(p,renewalQuote);
  const requestId=key('renewal_pay');await f.pay(p,renewal,{requestId});await f.pay(p,renewal,{requestId});
  const renewed=(await api(p.c,'membership/status')).data.items.find(x=>x.id===sub.id);
  assert.equal(renewed.periods.length,2);assert(renewed.periodEnd>sub.periodEnd);assert.equal(renewed.actualBillingEnabled,false);assert.equal(renewed.grantsProductionAccess,false);
  const quotaRows=await f.snapshot(['membership_ai_periods']);assert.equal(quotaRows.membership_ai_periods.filter(x=>x.owner===p.credential.id).length,0);
  const d=digitalFixtures(h,a),policy=await d.policy({enabled:true,confirmed:true,ruleVersion:key('finite_policy'),validityDays:2,usesPerUnit:3,leaseSeconds:300});
  const course=await f.course('有限隔离媒体',{sandboxOnly:true}),asset=await d.asset('PAY05有限隔离',{course:{item:course,actor:a.admin}});
  const product=await f.product('有限数字作品',{type:'digital',contentId:course.id}),quote=await f.quote(p,product),order=await f.consume(p,quote);
  assert.equal(quote.items[0].digitalTerms.validityDays,2);assert.equal(quote.items[0].digitalTerms.usesPerUnit,3);
  const transactionId=key('finite_paid_transaction'),eventId=key('finite_paid_event'),receipt=await f.callback(order,{transactionId,eventId});
  assert.equal((await receiptDone(receipt)).item.status,'applied');await f.callback(order,{transactionId,eventId});await f.processCallbacks(10);
  const saved=await d.snapshot(p.credential.id,order.id);assert.equal(saved.grants.filter(x=>x.order_id===order.id).length,1);
  const finite=(await d.list(p.c)).items.find(x=>x.orderId===order.id);assert(finite);assert.equal(finite.totalUses,3);assert.equal(finite.used,0);
  const raw=await p.c.get(h.base+asset.media.url);assert.equal(raw.status(),403);
  const contents=(await api(p.c,'public')).data.content.courses;assert(!contents.some(x=>x.id===course.id));
  assert.equal(policy.productionEnabled,false);assert.equal(finite.productionEnabled,false);
 });

 await check('30 七表明确归类、本人交易留存期限未知，最小导出隔离他人/正文/内部引用',async()=>{
  const p=await buyer(),other=await stranger();await f.enforce();const product=await f.product('导出隔离');
  const foreign=await f.consume(other,await f.quote(other,product));
  const inventory=(await api(p.c,'privacy/domains')).data;
  for(const table of ['payment_routing_config','payment_routing_versions','payment_routing_quotes','commerce_order_payment_routes',
    'payment_routing_quote_consumptions','payment_routing_confirmations','payment_routing_atomic_guards'])assert(!inventory.unclassifiedOwnerTables.includes(table));
  const retained=inventory.retained.find(x=>x.id==='commerceAndFulfilment');assert(retained);assert.equal(retained.retentionDays,null);assert.equal(retained.policyConfirmed,false);
  const own=(await api(p.c,'privacy/export')).data.serverData,staff=(await api(a.admin,'privacy/export')).data.serverData;
  const keys=['paymentRoutingVersions','paymentRoutingQuotes','orderPaymentRoutes','paymentRoutingQuoteConsumptions','paymentRoutingConfirmations'];
  const only=Object.fromEntries(keys.map(name=>{assert(Array.isArray(own[name]));return [name,own[name]];}));
  const text=JSON.stringify(only);assert(!text.includes(foreign.id));
  for(const forbidden of ['QA_PRIVATE_ADDRESS_BODY_CANARY','QA_ADDRESS_PHONE_CANARY','PAY05_INTERNAL_REF_NOT_FOR_PUBLIC_EXPORT','snapshot_data','fingerprint','session_hash'])assert(!text.includes(forbidden));
  assert(!JSON.stringify(Object.fromEntries(keys.map(k=>[k,staff[k]]))).includes('PAY05_INTERNAL_REF_NOT_FOR_PUBLIC_EXPORT'));
  const rows=await f.snapshot(['payment_routing_quotes','commerce_order_payment_routes','payment_routing_quote_consumptions','payment_routing_confirmations','payment_routing_atomic_guards']);
  for(const [table,name,id] of [['payment_routing_quotes','paymentRoutingQuotes','id'],['commerce_order_payment_routes','orderPaymentRoutes','order_id'],
    ['payment_routing_quote_consumptions','paymentRoutingQuoteConsumptions','quote_id'],['payment_routing_confirmations','paymentRoutingConfirmations','id']]){
   const expected=rows[table].filter(r=>r.owner===p.credential.id).map(r=>r[id]).sort();assert.deepEqual(only[name].map(r=>r[id]).sort(),expected);
  }
  assert.equal(rows.payment_routing_atomic_guards.length,0);
 });

 await check('31 真实服务进程重启后原报价/路由/消费仍持久，旧请求只读重放不再预占',async()=>{
  const p=await buyer();await f.enforce();const product=await f.product('真实重启'),quote=await f.quote(p,product),requestId=key('restart_order');
  const order=await f.consume(p,quote,{requestId}),unconsumed=await f.quote(p,product),before=await facts(order.id);
  const rowBefore=await f.snapshot(['payment_routing_quotes']);
  const restart=await h.restart();assert.notEqual(restart.beforePid,restart.afterPid);
  const read=(await f.getQuote(p,quote.id)).quote,waiting=(await f.getQuote(p,unconsumed.id)).quote;
  for(const name of ['id','created','expires','items','totals','decision']){assert.deepEqual(read[name],quote[name]);assert.deepEqual(waiting[name],unconsumed[name]);}
  const replay=await f.consume(p,quote,{requestId});assert.equal(replay.id,order.id);equalAdmission(before,await facts(order.id));
  const after=await f.snapshot(['payment_routing_quotes']);assert.deepEqual(after.payment_routing_quotes,rowBefore.payment_routing_quotes);
 });

 await check('32 真实浏览器已提交响应中断后同request恢复，DB仍唯一订单/路由/消费/预占',async()=>{
  assert(!h.args['http-only'],'Actual browser fetch is required for this transport boundary');
  const p=await buyer();await f.enforce();const product=await f.product('真实浏览器响应中断'),quote=await f.quote(p,product),requestId=key('lost_browser_response');
  await h.prepareRoutingWrites(p.c,3);
  const body={...f.intent(product),requestId,quoteId:quote.id};
  const browser=await h.browserContext(await p.c.storageState()),page=browser.page;
  let committed;let intercepted=0;let interceptionError;
  try{
   await page.goto(h.base+'/experience?page=commerceCart&lang=zh&mode=day');
   await page.waitForFunction(()=>typeof px!=='undefined'&&px.loaded&&!pxBootstrapPending);
   await page.route(h.base+'/api/commerce/orders',async route=>{
    if(route.request().method()!=='POST')return route.continue();
    try{const actual=await route.fetch();assert.equal(actual.status(),200);committed=await actual.json();intercepted++;}
    catch(error){interceptionError=error;}
    finally{
     // Only the response to this browser is lost. The actual server response is never fabricated.
     await route.abort('failed').catch(error=>{interceptionError=interceptionError||error;});
    }
   });
   const client=await page.evaluate(async payload=>{
    try{const response=await fetch('/api/commerce/orders',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});await response.json();return {rejected:false};}
    catch(error){return {rejected:true,errorName:error.name};}
   },body);
   if(interceptionError)throw interceptionError;
   assert.equal(client.rejected,true);assert.equal(intercepted,1);assert(committed?.id);
   await page.unroute(h.base+'/api/commerce/orders');
   const replay=(await api(p.c,'commerce/orders',body)).data;assert.equal(replay.id,committed.id);
   const another=(await api(p.c,'commerce/orders',body)).data;assert.equal(another.id,committed.id);
   const rows=await f.snapshot(['commerce_orders','commerce_order_payment_routes','payment_routing_quote_consumptions','commerce_reservations','commerce_order_items']);
   assert.equal(rows.commerce_orders.filter(x=>x.owner===p.credential.id&&x.request_id===requestId).length,1);
   assert.equal(byOrder(rows.commerce_order_payment_routes,committed.id).length,1);
   assert.equal(rows.payment_routing_quote_consumptions.filter(x=>x.quote_id===quote.id&&x.order_id===committed.id).length,1);
   const reservations=byOrder(rows.commerce_reservations,committed.id);assert.equal(reservations.length,1);assert.equal(reservations[0].state,'held');assert.equal(reservations[0].quantity,1);
   assert.equal(byOrder(rows.commerce_order_items,committed.id).length,1);
   (h.report.routingTransportProof??=[]).push({kind:'actual-browser-fetch',responseAbortedAfterActualServerCommit:true,manufacturedServerResponse:false,
    orderId:committed.id,actualReplays:2,orderCount:1,routeCount:1,consumptionCount:1,reservationCount:1,nativeUiVisualScopeClaimed:false});
  }finally{await page.close();}
 });
};
