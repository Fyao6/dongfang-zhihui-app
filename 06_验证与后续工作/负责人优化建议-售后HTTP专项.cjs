'use strict';
// Actual HTTP tests against the owned fresh service started by 售后实际专项.cjs.
// All commercial records are actual sandbox orders/payments; no direct SQL setup of money or stock.
const assert=require('node:assert/strict');
module.exports=async function(h){
 const {api,check,register,admin}=h,key=x=>'as_'+x+'_'+h.runId;
 const address={name:'合成收件人',country:'CN',address:'隔离测试仓库1号',city:'合成市',postalCode:'000000'};
 let user,other,operator,product,order,mainCase,raceCase,digital,digitalOrder,preOrder;
 const originalSnapshot='成交时售后测试条款，不是正式政策。';
 const finance=o=>({paymentStatus:o.paymentStatus,totalMinor:o.totalMinor,refundedMinor:o.refundedMinor,events:o.events,items:o.items.map(x=>({id:x.id,refundedQuantity:x.refundedQuantity}))});
 const read=async(c,id)=>api(c,'commerce/orders/'+id);
 const readCase=async(c,id)=>api(c,'after-sales/cases/'+id);
 const stock=async()=>((await api(admin,'admin/commerce')).products.find(x=>x.id===product.id)).stock;
 const create=async(c,o,label,quantity=1,type='return')=>api(c,'after-sales/cases',{requestId:key(label),environment:'sandbox',orderId:o.id,type,items:[{itemId:o.items[0].id,quantity}],reason:'合成逐项检查 '+label});
 const decision=async(c,kind,label)=>api(admin,'admin/after-sales/cases/'+c.id+'/decision',{requestId:key(label),version:c.version,decision:kind,reason:'合成后台明确理由 '+label});
 const shipping=async(c,acct,label)=>api(acct,'after-sales/cases/'+c.id+'/return-shipping',{requestId:key(label),version:c.version,carrier:'合成承运商，未核验',trackingNumber:key('return_tracking_'+label)});
 const receiptBody=(c,label,receivedQuantity,restockQuantity)=>({requestId:key('receive_'+label),version:c.version,receiptReference:key('receipt_'+label),items:[{caseItemId:c.items[0].id,receivedQuantity,restockQuantity,condition:'合成实收判断 '+label}],note:'合成验收，只按明确数量入库 '+label});
 const inspect=async(c,body,expected=200)=>api(admin,'admin/after-sales/cases/'+c.id+'/inspect',body,'POST',expected);
 const newOrder=async(acct,label,quantity=1,p=product)=>api(acct,'commerce/orders',{requestId:key('order_'+label),environment:'sandbox',items:[{skuId:p.skuId,quantity}],...(p.type==='physical'?{shippingAddress:address}:{})});
 const pay=async(acct,o,label)=>api(acct,'commerce/orders/'+o.id+'/sandbox-pay',{requestId:key('pay_'+label)});
 const shipOrder=async(o,label)=>api(admin,'admin/commerce/orders/'+o.id+'/fulfill',{status:'delivered',trackingNumber:key('outbound_'+label),carrier:'合成发货'});
 const refund=async(o,label,quantity=1)=>api(admin,'admin/commerce/orders/'+o.id+'/refund',{requestId:key('refund_'+label),items:[{itemId:o.items[0].id,quantity}]});
 user=await register('orders');other=await register('other');operator=await register('operator');
 await api(admin,'admin/users/'+operator.credential.id,{role:'operator'},'PATCH');
 h.accounts={user,other,operator};h.helpers={newOrder,pay,shipOrder,create,decision,shipping,readCase,read,key};
 await check('售后默认关闭/生产固定关闭；匿名与普通及运营管理权限拒绝',async()=>{
  const anonymous=await h.apiContext();await api(anonymous,'after-sales/cases?environment=sandbox',undefined,'GET',401);
  const c=await api(user.c,'after-sales/config');assert.equal(c.settings.sandboxEnabled,false);assert.equal(c.productionEnabled,false);
  assert.equal(c.refundsFunds,false);assert.equal(c.carrierVerificationEnabled,false);
  await api(user.c,'admin/after-sales?environment=sandbox',undefined,'GET',403);await api(operator.c,'admin/after-sales?environment=sandbox',undefined,'GET',403);
  await api(user.c,'admin/after-sales/settings',{sandboxEnabled:true,ruleVersion:'fake'},'PATCH',403);
 });
 await check('启用必须明确沙箱测试规则版本，布尔和正式开关严格校验',async()=>{
  await api(admin,'admin/after-sales/settings',{sandboxEnabled:true,productionEnabled:true,ruleVersion:'fixture'},'PATCH',400);
  await api(admin,'admin/after-sales/settings',{sandboxEnabled:'true',productionEnabled:false,ruleVersion:'fixture'},'PATCH',400);
  await api(admin,'admin/after-sales/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH',400);
  await api(admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
  const c=await api(admin,'admin/after-sales/settings',{sandboxEnabled:true,productionEnabled:false,ruleVersion:'explicit-fixture-v1'},'PATCH');
  assert.equal(c.settings.productionEnabled,false);assert.equal((await api(user.c,'public')).afterSalesServiceReady,true);
  product=(await api(admin,'admin/commerce/products',{title:'售后合成实物 '+h.runId,titleEn:'Synthetic physical goods',titleZh:'合成实物',titleHant:'合成實物',titleBo:'ཚོད་ལྟའི་དངོས་ཟོག',description:'隔离测试，不正式销售。',type:'physical',environment:'sandbox',status:'published',sku:key('physical'),priceMinor:1000,currency:'CNY',stock:30,shippingCountries:['CN'],shippingMinor:50,taxMinor:20,refundPolicy:originalSnapshot})).item;
 });
 assert(product,'Real physical SKU must exist before dependent scenarios');
 await check('必须真实统一测试付款和发货；未付款/未发货不接受实物退货',async()=>{
  order=await newOrder(user.c,'main',3);await create(user.c,order,'unpaid',2).then(()=>assert.fail('Expected unpaid rejection'),e=>assert.match(e.message,/409/));
  order=await pay(user.c,order,'main');await create(user.c,order,'not-shipped',2).then(()=>assert.fail('Expected undispatched rejection'),e=>assert.match(e.message,/409/));
  order=await shipOrder(order,'main');assert.equal(order.fulfillmentStatus,'delivered');assert.equal(await stock(),27);
 });
 await check('实际已付原单按项快照与幂等；异载荷同编号409，正式申请403',async()=>{
  const body={requestId:key('main-case'),environment:'sandbox',orderId:order.id,type:'return',items:[{itemId:order.items[0].id,quantity:2}],reason:'实际原单合成退货申请'};
  const made=await api(user.c,'after-sales/cases',body);mainCase=made.item;assert.equal(made.replayed,false);assert.equal(mainCase.ruleVersion,'explicit-fixture-v1');
  assert.equal(mainCase.items[0].snapshot.terms.refundPolicy,originalSnapshot);assert.equal(mainCase.money.actualFundsMoved,false);assert.equal(mainCase.money.caseRefundConfirmed,false);
  const again=await api(user.c,'after-sales/cases',body);assert.equal(again.replayed,true);assert.equal(again.item.id,mainCase.id);
  await api(user.c,'after-sales/cases',{...body,reason:'同编号异内容'},'POST',409);
  await api(user.c,'after-sales/cases',{...body,requestId:key('prod'),environment:'production'},'POST',403);
 });
 assert(mainCase,'Real per-item case must exist');
 await check('本人隔离：其他账号不能读申请/资格或写物流，用户不能登记仓库验收',async()=>{
  await api(other.c,'after-sales/cases/'+mainCase.id,undefined,'GET',404);
  await api(other.c,'after-sales/orders/'+order.id,undefined,'GET',404);
  await api(other.c,'after-sales/cases/'+mainCase.id+'/return-shipping',{requestId:key('foreign'),version:1,carrier:'合成',trackingNumber:'合成'},'POST',404);
  await api(user.c,'admin/after-sales/cases/'+mainCase.id+'/inspect',receiptBody(mainCase,'forbidden',1,1),'POST',403);
 });
 await check('按项数量严格且不可超原量；同时竞争剩余一件只创建一份申请',async()=>{
  for(const quantity of [true,1.5,0,'1'])await api(other.c,'after-sales/cases',{requestId:key('bad-'+String(quantity)),environment:'sandbox',orderId:order.id,type:'return',items:[{itemId:order.items[0].id,quantity}],reason:'合成严格校验'},'POST',400);
  await api(user.c,'after-sales/cases',{requestId:key('over'),environment:'sandbox',orderId:order.id,type:'return',items:[{itemId:order.items[0].id,quantity:2}],reason:'超额竞争'},'POST',409);
  const results=await Promise.all(['race-a','race-b'].map(x=>api(user.c,'after-sales/cases',{requestId:key(x),environment:'sandbox',orderId:order.id,type:'return',items:[{itemId:order.items[0].id,quantity:1}],reason:'竞争剩余一件'},'POST',null)));
  assert.deepEqual(results.map(x=>x.status).sort(),[200,409]);raceCase=results.find(x=>x.status===200).data.item;
  const eligible=await api(user.c,'after-sales/orders/'+order.id);assert.equal(eligible.items[0].claimedQuantity,3);assert.equal(eligible.items[0].availableReturnQuantity,0);
 });
 await check('受理/驳回有理由且CAS版本保护，不调用退款或变库存',async()=>{
  const money=finance(await read(user.c,order.id)),before=await stock();
  const payload={requestId:key('accept-main'),version:mainCase.version,decision:'accept',reason:'合成受理，等待退货'};
  mainCase=(await api(admin,'admin/after-sales/cases/'+mainCase.id+'/decision',payload)).item;
  assert.equal(mainCase.status,'accepted');assert.equal(mainCase.version,2);
  assert.equal((await api(admin,'admin/after-sales/cases/'+mainCase.id+'/decision',payload)).replayed,true);
  await api(admin,'admin/after-sales/cases/'+mainCase.id+'/decision',{...payload,requestId:key('stale-accept')},'POST',409);
  assert.deepEqual(finance(await read(user.c,order.id)),money);assert.equal(await stock(),before);
  await inspect(mainCase,receiptBody(mainCase,'before-tracking',1,1),409);
 });
 await check('真实物流登记是独立未核验事实，不能代替退款或收货',async()=>{
  const before=finance(await read(user.c,order.id));mainCase=(await shipping(mainCase,user.c,'main')).item;
  assert.equal(mainCase.status,'returning');assert.equal(mainCase.shipments.length,1);assert.equal(mainCase.shipments[0].carrierVerified,false);
  assert.deepEqual(finance(await read(user.c,order.id)),before);assert.equal(mainCase.items[0].receivedQuantity,0);
 });
 let receipt1;
 await check('部分实收明确入库0，单据/版本/资金事实真实且库存不加',async()=>{
  const money=finance(await read(user.c,order.id)),before=await stock();receipt1=receiptBody(mainCase,'partial-zero',1,0);
  mainCase=(await inspect(mainCase,receipt1)).item;assert.equal(mainCase.status,'partially_received');
  assert.equal(mainCase.items[0].receivedQuantity,1);assert.equal(mainCase.items[0].restockedQuantity,0);
  assert.equal(await stock(),before);assert.deepEqual(finance(await read(user.c,order.id)),money);
  const events=(await read(user.c,order.id)).inventoryEvents.filter(x=>x.reason==='after_sales_received_no_restock');assert.equal(events.length,1);assert.equal(events[0].quantityDelta,0);
 });
 await check('同编号重复收货不二次入库；同批次换编号409且整批回滚',async()=>{
  const before=await stock(),version=mainCase.version;assert.equal((await inspect(mainCase,receipt1)).replayed,true);
  await inspect(mainCase,{...receipt1,requestId:key('duplicate-receipt-new-id'),version:mainCase.version},409);
  assert.equal(await stock(),before);assert.equal((await readCase(user.c,mainCase.id)).version,version);
 });
 await check('余下实收明确入库1且库存事件唯一；超收/重复不改账',async()=>{
  const before=await stock(),body=receiptBody(mainCase,'final-one',1,1);
  mainCase=(await inspect(mainCase,body)).item;assert.equal(mainCase.status,'received');assert.equal(mainCase.items[0].restockedQuantity,1);assert.equal(await stock(),before+1);
  await inspect(mainCase,body);assert.equal(await stock(),before+1);
  await inspect(mainCase,receiptBody(mainCase,'over-final',1,1),409);
  assert.equal((await read(user.c,order.id)).inventoryEvents.filter(x=>x.reason==='after_sales_return_restock').length,1);
 });
 await check('已送达原统一部分退款不再回库；新申请不会冒充本案退款或到账',async()=>{
  const before=await stock();order=await refund(order,'main-two',2);
  assert.equal(order.paymentStatus,'partially_refunded');assert.equal(await stock(),before);
  const event=order.inventoryEvents.find(x=>x.reason==='refund_after_dispatch_no_restock');assert(event);assert.equal(event.quantityDelta,0);
  const c=await readCase(user.c,mainCase.id);assert.equal(c.status,'received');assert.equal(c.money.caseRefundLinked,false);assert.equal(c.money.caseRefundConfirmed,false);assert.equal(c.money.actualFundsMoved,false);assert.equal(c.money.orderRefundedMinor,2140);
 });
 await check('明确驳回释放单项额度，历史申请仍保留且不自动退款',async()=>{
  raceCase=(await decision(raceCase,'reject','reject-race')).item;assert.equal(raceCase.status,'rejected');
  const eligible=await api(user.c,'after-sales/orders/'+order.id);assert.equal(eligible.items[0].claimedQuantity,2);assert.equal(eligible.items[0].availableReturnQuantity,1);
 });
 await check('旧申请在先阻止新按项分配；新申请在先阻止旧入口，旧编号重放仍可读',async()=>{
  const legacyUser=await register('legacy');let o=await newOrder(legacyUser.c,'legacy',1);o=await pay(legacyUser.c,o,'legacy');o=await shipOrder(o,'legacy');
  const oldBody={requestId:key('legacy-pending'),reason:'既有旧流程合成申请',quantity:1};
  await api(legacyUser.c,'commerce/orders/'+o.id+'/aftersale',oldBody);
  await api(legacyUser.c,'after-sales/cases',{requestId:key('new-after-legacy'),environment:'sandbox',orderId:o.id,type:'return',items:[{itemId:o.items[0].id,quantity:1}],reason:'不能猜旧申请项'},'POST',409);
  await api(user.c,'commerce/orders/'+order.id+'/aftersale',{requestId:key('old-after-new'),reason:'不得绕开已分配项',quantity:1},'POST',409);
  assert((await api(legacyUser.c,'commerce/orders/'+o.id+'/aftersale',oldBody)).aftersaleRequests.length===1);
 });
 await check('旧/新两个入口真实并发只允许一个建立，未丢库存或超分配',async()=>{
  const race=await register('legacyRace');let o=await newOrder(race.c,'cross-entry-race',1);o=await pay(race.c,o,'cross-entry-race');o=await shipOrder(o,'cross-entry-race');
  const moneyBefore=finance(await read(race.c,o.id)),fulfillmentBefore=o.fulfillmentStatus,stockBefore=await stock();
  const results=await Promise.all([
   api(race.c,'commerce/orders/'+o.id+'/aftersale',{requestId:key('race-legacy'),reason:'合成旧入口竞态',quantity:1},'POST',null),
   api(race.c,'after-sales/cases',{requestId:key('race-modern'),environment:'sandbox',orderId:o.id,type:'return',items:[{itemId:o.items[0].id,quantity:1}],reason:'合成新入口竞态'},'POST',null)
  ]);
  assert.deepEqual(results.map(x=>x.status).sort(),[200,409]);
  const after=await read(race.c,o.id),legacy=after.aftersaleRequests.length,modern=(await api(race.c,'after-sales/cases?environment=sandbox')).items.length;assert.equal(legacy+modern,1);
  assert.deepEqual(finance(after),moneyBefore);assert.equal(after.fulfillmentStatus,fulfillmentBefore);assert.equal(await stock(),stockBefore);
 });
 await check('同原订单两份申请同收货单并发只成功一份，库存仅加1且资金履约不变',async()=>{
  const buyer=await register('receiptRace');let o=await newOrder(buyer.c,'same-receipt-race',2);o=await pay(buyer.c,o,'same-receipt-race');o=await shipOrder(o,'same-receipt-race');
  const cases=[];for(let n=0;n<2;n++){let c=(await create(buyer.c,o,'same-receipt-case-'+n,1)).item;c=(await decision(c,'accept','same-receipt-accept-'+n)).item;c=(await shipping(c,buyer.c,'same-receipt-shipping-'+n)).item;cases.push(c);}
  const moneyBefore=finance(await read(buyer.c,o.id)),fulfillmentBefore=o.fulfillmentStatus,stockBefore=await stock(),reference=key('one-physical-receipt');
  const bodies=cases.map((c,n)=>({...receiptBody(c,'across-cases-'+n,1,1),receiptReference:reference}));
  const results=await Promise.all(cases.map((c,n)=>api(admin,'admin/after-sales/cases/'+c.id+'/inspect',bodies[n],'POST',null)));
  assert.deepEqual(results.map(r=>r.status).sort(),[200,409]);assert.equal(await stock(),stockBefore+1);
  const after=await read(buyer.c,o.id);assert.deepEqual(finance(after),moneyBefore);assert.equal(after.fulfillmentStatus,fulfillmentBefore);
  assert.equal(after.inventoryEvents.filter(x=>x.reason==='after_sales_return_restock').length,1);
  const loser=results.findIndex(r=>r.status===409);
  await api(admin,'admin/after-sales/cases/'+cases[loser].id+'/inspect',{...bodies[loser],requestId:key('same-receipt-serial-replay')},'POST',409);assert.equal(await stock(),stockBefore+1);
 });
 await check('原发货前退款已回库数量扣除，发货后仅余下可实际退回',async()=>{
  const buyer=await register('preRefund');preOrder=await newOrder(buyer.c,'pre-refund',2);preOrder=await pay(buyer.c,preOrder,'pre-refund');
  preOrder=await refund(preOrder,'pre-refund',1);preOrder=await shipOrder(preOrder,'pre-refund');
  const e=await api(buyer.c,'after-sales/orders/'+preOrder.id);assert.equal(e.items[0].autoRestockedQuantity,1);assert.equal(e.items[0].availableReturnQuantity,1);
  await api(buyer.c,'after-sales/cases',{requestId:key('over-old-stock'),environment:'sandbox',orderId:preOrder.id,type:'return',items:[{itemId:preOrder.items[0].id,quantity:2}],reason:'不能重复回旧库存'},'POST',409);
 });
 await check('数字商品仅退款审查，不可登记退货/验收，不自动退款或开正式媒体',async()=>{
  const pub=await api(admin,'public'),template=pub.content.courses[0];assert(template);
  const courseId=key('digital-course'),item={...template,id:courseId,title:'售后合成课程',access:'member',mediaUrl:''};delete item.creatorId;delete item.creatorWorkId;await api(admin,'admin/content/courses',{item,status:'published'});
  digital=(await api(admin,'admin/commerce/products',{title:'售后合成数字商品',type:'digital',environment:'sandbox',status:'published',sku:key('digital'),priceMinor:500,currency:'CNY',stock:10,contentId:courseId,shippingCountries:[],shippingMinor:0,taxMinor:0})).item;
  const buyer=await register('digital');digitalOrder=await newOrder(buyer.c,'digital',1,digital);digitalOrder=await pay(buyer.c,digitalOrder,'digital');
  const made=(await create(buyer.c,digitalOrder,'digital-review',1,'refund-only')).item,accepted=(await decision(made,'accept','digital-accept')).item;
  await api(buyer.c,'after-sales/cases/'+accepted.id+'/return-shipping',{requestId:key('digital-ship'),version:accepted.version,carrier:'合成',trackingNumber:'不能发物流'},'POST',409);
  await inspect(accepted,receiptBody(accepted,'digital-receipt',1,1),409);
  assert.equal((await read(buyer.c,digitalOrder.id)).paymentStatus,'paid');
  const course=(await api(buyer.c,'public')).content.courses.find(x=>x.id===courseId);assert.equal(course.mediaUrl,'');assert.equal(course.requiresMembership,true);
 });
 await check('隐私导出只包含本人售后事实，不导出配置/他人申请；关闭不伪造删除',async()=>{
  const own=(await api(user.c,'privacy/export')).serverData,foreign=(await api(other.c,'privacy/export')).serverData;
  assert(own.afterSalesCases.some(x=>x.id===mainCase.id));assert(own.afterSalesItems.some(x=>x.case_id===mainCase.id));
  assert.equal(foreign.afterSalesCases.some(x=>x.id===mainCase.id),false);assert.equal(Object.hasOwn(own,'afterSalesConfig'),false);
  assert(!JSON.stringify(own.afterSalesActions).includes('fingerprint'));
 });
 await check('关闭沙箱保留本人查询，拒绝新增变更，不改变原付款/退款/库存',async()=>{
  const before=finance(await read(user.c,order.id)),beforeStock=await stock();
  await api(admin,'admin/after-sales/settings',{sandboxEnabled:false,productionEnabled:false,ruleVersion:'explicit-fixture-v1'},'PATCH');
  assert.equal((await readCase(user.c,mainCase.id)).id,mainCase.id);
  await api(user.c,'after-sales/cases',{requestId:key('disabled'),environment:'sandbox',orderId:order.id,type:'return',items:[{itemId:order.items[0].id,quantity:1}],reason:'关闭后不能新增'},'POST',503);
  assert.deepEqual(finance(await read(user.c,order.id)),before);assert.equal(await stock(),beforeStock);
  await api(admin,'admin/after-sales/settings',{sandboxEnabled:true,productionEnabled:false,ruleVersion:'explicit-fixture-v1'},'PATCH');
 });
 h.product=product;
};

