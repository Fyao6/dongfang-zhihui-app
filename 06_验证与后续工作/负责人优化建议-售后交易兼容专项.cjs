// Unified commerce HTTP and real-browser acceptance. Wait for the final build before running.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {makeHarness}=require('./负责人优化建议-售后交易兼容工具.cjs');
const h=makeHarness(),{api,check,runId}=h,templates=new Map();
const environment='sandbox',address={name:'合成收件人',country:'CN',address:'隔离测试地址1号',city:'测试市',postalCode:'000000'};
let accounts={},shipping,uiBuyer,courseId,mediaId,products={},digitalOrder,physicalOrder,raceOrder,failedOrder,secondaryOrder;
const localizedSnapshot={titleZh:'成交时简体标题',titleHant:'成交時繁體標題',titleEn:'Original sale title',titleBo:'ཉོ་སྒྲུབ་དུས་ཀྱི་ཁ་བྱང་།',descriptionZh:'成交时简体说明',descriptionHant:'成交時繁體說明',descriptionEn:'Original sale description',descriptionBo:'ཉོ་སྒྲུབ་དུས་ཀྱི་གསལ་བཤད།',refundPolicy:'成交时退款条款：提交售后申请后人工核查。'};
const key=label=>'co_'+label+'_'+runId;
const readOrder=async(ctx,id)=>(await api(ctx,'commerce/orders/'+id)).data;
const catalog=async()=>(await api(accounts.admin,'admin/commerce')).data;
const productById=async id=>(await catalog()).products.find(p=>p.id===id);
const entitlements=async(ctx,orderId)=>(await api(ctx,'commerce/entitlements?environment=sandbox')).data.items.filter(e=>!orderId||e.orderId===orderId);
const orderPayload=(id,items,extra={})=>({requestId:key(id),environment,items:items.map(([p,quantity])=>({skuId:p.skuId,quantity})),...extra});
const pay=async(ctx,id,requestId=key('pay_'+id))=>(await api(ctx,'commerce/orders/'+id+'/sandbox-pay',{requestId})).data;
const refund=async(id,requestId,items,expected=200)=>(await api(accounts.admin,'admin/commerce/orders/'+id+'/refund',{requestId,items},'POST',expected)).data;
async function saveProduct(label,changes={}){
 const body={title:'交易专项 '+label+' '+runId,description:'仅用于隔离沙箱专项，不是正式销售商品。',type:'digital',environment,status:'published',sku:key(label),priceMinor:1234,currency:'CNY',stock:30,contentId:courseId,shippingCountries:[],shippingMinor:0,taxMinor:0,...changes};
 const item=(await api(accounts.admin,'admin/commerce/products',body)).data.item;templates.set(item.id,body);return item;
}
async function updateProduct(item,changes){const body={...templates.get(item.id),id:item.id,version:item.version,...changes};const next=(await api(accounts.admin,'admin/commerce/products',body)).data.item;templates.set(item.id,body);return next;}
function line(order,product){const item=order.items.find(i=>i.productId===product.id);assert(item,'Order preserves the requested product snapshot');return item;}
function events(order,kind){return order.events.filter(e=>e.kind===kind);}
async function uploadImage(ctx,name){const response=await ctx.post(h.base+'/api/media',{data:fs.readFileSync(path.join(h.R4,'images/community-preview-poster.jpg')),headers:{'Content-Type':'image/jpeg','X-Filename':name+'.jpg'}});assert.equal(response.status(),200);return response.json();}
async function mediaStatus(ctx,id,expected){const response=await ctx.get(h.base+'/api/media/'+id);assert.equal(response.status(),expected);if(expected===200)assert(/^image\/jpeg/.test(response.headers()['content-type']));return response;}
async function prepareMediaFixture(){
 const publicData=(await api(accounts.admin,'public')).data,template=publicData.content.courses[0];assert(template,'A real platform course schema is available for the isolated fixture');
 const asset=await uploadImage(accounts.admin,'commerce-member-fixture');mediaId=asset.id;courseId=key('member_course');
 const item={...template,id:courseId,title:'隔离测试会员作品 '+runId,access:'member',mediaUrl:asset.url};delete item.creatorId;delete item.creatorWorkId;
 await api(accounts.admin,'admin/content/courses',{item,status:'published'});
 await api(accounts.user,'media/'+mediaId,undefined,'GET',403);
}
async function main(){
 await h.start();accounts=await h.seed();
 for(const name of ['shipping','ui']){const ctx=await h.context();await api(ctx,'auth/register',{username:'co_'+name+'_'+runId.slice(0,18),password:crypto.randomBytes(22).toString('hex'),name:'交易合成 '+name});if(name==='shipping')shipping=ctx;else uiBuyer=ctx;}
 await check('管理员专属交易配置、沙箱明确开启且生产开关拒绝',async()=>{
  await api(accounts.anonymous,'admin/commerce',undefined,'GET',401);await api(accounts.user,'admin/commerce',undefined,'GET',403);
  await api(accounts.user,'admin/commerce/settings',{sandboxEnabled:true},'PATCH',403);
  await api(accounts.admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:true},'PATCH',400);
  await api(accounts.admin,'admin/commerce/settings',{sandboxEnabled:'true'},'PATCH',400);
  const config=(await api(accounts.admin,'admin/commerce/settings',{sandboxEnabled:false,productionEnabled:false},'PATCH')).data.settings;assert.deepEqual(config,{sandboxEnabled:false,productionEnabled:false});
 });
 await check('会员受限素材夹具真实上传发布，普通用户不能读取',async()=>{await prepareMediaFixture();return {memberCourseCreated:true,ordinaryMediaStatus:403};});
 assert(courseId&&mediaId,'Protected-media fixture must exist before commerce acceptance');
 await check('商品金额、数量、币种、商品类型与地址配置严格校验',async()=>{
  const valid={title:'校验夹具 '+runId,type:'digital',environment,status:'published',sku:key('invalid'),priceMinor:100,currency:'CNY',stock:10,contentId:courseId};
  for(const priceMinor of [-1,1.5,true,'100',1000000001])await api(accounts.admin,'admin/commerce/products',{...valid,priceMinor},'POST',400);
  for(const currency of ['US','USDT','U$D','','ZZZ'])await api(accounts.admin,'admin/commerce/products',{...valid,currency},'POST',400);
  for(const stock of [-1,1.5,true])await api(accounts.admin,'admin/commerce/products',{...valid,stock},'POST',400);
  await api(accounts.admin,'admin/commerce/products',{...valid,type:'appointment'},'POST',400);
  await api(accounts.admin,'admin/commerce/products',{...valid,contentId:''},'POST',400);
  await api(accounts.admin,'admin/commerce/products',{...valid,contentId:key('nonexistent_course')},'POST',400);
  await api(accounts.admin,'admin/commerce/products',{...valid,shippingMinor:100},'POST',400);
  await api(accounts.admin,'admin/commerce/products',{...valid,type:'physical',contentId:'',shippingCountries:[]},'POST',400);
  await api(accounts.admin,'admin/commerce/products',{...valid,type:'physical',contentId:'',shippingCountries:['CHINA']},'POST',400);
  return {invalidMoneyInputs:5,invalidCurrencies:5,invalidStockInputs:3};
 });
 await check('SKU、价格版本和沙箱商品保存，重复SKU及普通用户管理拒绝',async()=>{
  products.a=await saveProduct('digital_a',{taxMinor:7,...localizedSnapshot});products.b=await saveProduct('digital_b',{priceMinor:678});
  products.physicalA=await saveProduct('physical_a',{type:'physical',contentId:'',priceMinor:500,stock:10,shippingCountries:['CN'],shippingMinor:50,taxMinor:20});
  products.physicalB=await saveProduct('physical_b',{type:'physical',contentId:'',priceMinor:700,stock:10,shippingCountries:['CN'],shippingMinor:80,taxMinor:30});
  for(const p of Object.values(products)){assert(p.id&&p.skuId&&p.id!==p.skuId);assert.equal(p.version,1);assert.equal(p.priceVersion,1);assert.equal(p.environment,'sandbox');assert(Number.isInteger(p.priceMinor));}
  await api(accounts.admin,'admin/commerce/products',templates.get(products.a.id),'POST',409);
  await api(accounts.user,'admin/commerce/products',{...templates.get(products.a.id),sku:key('forbidden')},'POST',403);
  for(const [name,value] of Object.entries(localizedSnapshot))assert.equal(products.a[name],value,'Saved product round-trips '+name);
 });
 assert(products.a&&products.b&&products.physicalA&&products.physicalB,'Core product fixtures must exist');
 await check('沙箱关闭时不能下单，开启后目录反映真实可买状态',async()=>{
  assert.equal((await api(accounts.anonymous,'commerce/catalog?environment=sandbox')).data.items.length,0);
  await api(accounts.user,'commerce/orders',orderPayload('disabled',[[products.a,1]]),'POST',503);
  const config=(await api(accounts.admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH')).data.settings;assert.equal(config.sandboxEnabled,true);
  const list=(await api(accounts.anonymous,'commerce/catalog?environment=sandbox')).data;assert.equal(list.productionEnabled,false);assert(list.items.some(p=>p.id===products.a.id&&p.purchasable));
 });
 await check('生产订单禁止，默认生产目录不冒充已开真实支付',async()=>{
  await api(accounts.user,'commerce/orders',{...orderPayload('production',[[products.a,1]]),environment:'production'},'POST',403);
  const list=(await api(accounts.anonymous,'commerce/catalog')).data;assert.equal(list.environment,'production');assert.equal(list.productionEnabled,false);assert(list.items.every(p=>p.purchasable===false));
 });
 await check('商品独立封面按上架状态公开，不能引用其他账号私有图片',async()=>{
  const cover=await uploadImage(accounts.admin,'commerce-public-cover'),privateCover=await uploadImage(accounts.user,'commerce-private-cover');
  await mediaStatus(accounts.anonymous,cover.id,403);await mediaStatus(accounts.anonymous,privateCover.id,403);
  await api(accounts.admin,'admin/commerce/products',{...templates.get(products.b.id),sku:key('foreign_image'),imageUrl:privateCover.url},'POST',403);
  let product=await saveProduct('public_cover',{imageUrl:cover.url});assert.equal(product.imageUrl,cover.url);
  const exposed=(await api(accounts.anonymous,'commerce/catalog?environment=sandbox')).data.items.find(p=>p.id===product.id);assert.equal(exposed.imageUrl,cover.url);await mediaStatus(accounts.anonymous,cover.id,200);
  await api(accounts.admin,'admin/commerce/settings',{sandboxEnabled:false},'PATCH');await mediaStatus(accounts.anonymous,cover.id,403);await api(accounts.admin,'admin/commerce/settings',{sandboxEnabled:true},'PATCH');await mediaStatus(accounts.anonymous,cover.id,200);
  product=await updateProduct(product,{status:'archived'});await mediaStatus(accounts.anonymous,cover.id,403);await mediaStatus(accounts.anonymous,privateCover.id,403);await mediaStatus(accounts.user,mediaId,403);
  return {isolatedCoverPublishedAndArchived:true,foreignPrivateImageRejected:true};
 });
 await check('购物车按真实账号隔离，未登录访问拒绝',async()=>{
  await api(accounts.anonymous,'commerce/cart?environment=sandbox',undefined,'GET',401);
  await api(accounts.user,'commerce/cart',{environment,items:[{skuId:products.a.skuId,quantity:1}]},'PATCH');
  assert.deepEqual((await api(accounts.user,'commerce/cart?environment=sandbox')).data.items,[{skuId:products.a.skuId,quantity:1}]);
  assert.deepEqual((await api(accounts.other,'commerce/cart?environment=sandbox')).data.items,[]);
  await api(accounts.user,'commerce/cart',{environment,items:[]},'PATCH');
 });
 await check('订单数量严格整数且不接受重复SKU，不同币种分单',async()=>{
  for(const quantity of [0,-1,1.5,true,'1',100])await api(accounts.other,'commerce/orders',{environment,requestId:key('bad_qty_'+String(quantity)),items:[{skuId:products.b.skuId,quantity}]},'POST',400);
  await api(accounts.other,'commerce/orders',{environment,requestId:key('duplicate_sku'),items:[{skuId:products.b.skuId,quantity:1},{skuId:products.b.skuId,quantity:1}]},'POST',400);
  const usd=await saveProduct('usd',{currency:'USD'});await api(accounts.other,'commerce/orders',orderPayload('currency_mix',[[products.b,1],[usd,1]]),'POST',409);
 });
 await check('数字实物混单明确拒绝且整单失败不遗留预占',async()=>{
  const before=await productById(products.a.id),physicalBefore=await productById(products.physicalA.id);
  const response=await api(accounts.user,'commerce/orders',orderPayload('mixed',[[products.a,1],[products.physicalA,1]],{shippingAddress:address}),'POST',409);assert(/拆|separat|split/i.test(response.data.error));
  assert.equal((await productById(products.a.id)).reserved,before.reserved);assert.equal((await productById(products.physicalA.id)).reserved,physicalBefore.reserved);
 });
 await check('服务端核价、数字无地址、订单项价格与SKU版本完整快照',async()=>{
  const body=orderPayload('digital_main',[[products.a,2]]);body.totalMinor=1;body.currency='USD';body.items[0].priceMinor=1;
  digitalOrder=(await api(accounts.user,'commerce/orders',body)).data;assert.equal(digitalOrder.subtotalMinor,2468);assert.equal(digitalOrder.taxMinor,14);assert.equal(digitalOrder.shippingMinor,0);assert.equal(digitalOrder.totalMinor,2482);assert.equal(digitalOrder.currency,'CNY');assert.deepEqual(digitalOrder.shippingAddress,{});
  const item=line(digitalOrder,products.a);assert.equal(item.skuId,products.a.skuId);assert.equal(item.quantity,2);assert.equal(item.priceMinor,1234);assert.equal(item.priceVersion,1);assert.equal(item.unitTaxMinor,7);assert(item.itemId&&item.itemId===item.id);assert.equal(digitalOrder.paymentStatus,'unpaid');
  for(const [name,value] of Object.entries(localizedSnapshot))assert.equal(item[name],value,'Order snapshots '+name);
 });
 assert(digitalOrder,'A valid server-priced digital order is required');
 await check('创建幂等同负载重放，不同数量或地址负载冲突',async()=>{
  const body=orderPayload('digital_main',[[products.a,2]]),before=(await productById(products.a.id)).reserved;
  const repeated=(await api(accounts.user,'commerce/orders',body)).data;assert.equal(repeated.id,digitalOrder.id);assert.equal((await productById(products.a.id)).reserved,before);
  await api(accounts.user,'commerce/orders',orderPayload('digital_main',[[products.a,1]]),'POST',409);
  await api(accounts.user,'commerce/orders',{...body,shippingAddress:address},'POST',409);
  const orders=(await api(accounts.user,'commerce/orders?environment=sandbox')).data.items;assert.equal(orders.filter(o=>o.requestId===body.requestId).length,1);
 });
 await check('同requestId并发下单只生成一单一次预占',async()=>{
  const body=orderPayload('concurrent_replay',[[products.b,1]]),before=await productById(products.b.id);
  const responses=await Promise.all([api(accounts.other,'commerce/orders',body),api(accounts.other,'commerce/orders',body)]);assert.equal(responses[0].data.id,responses[1].data.id);secondaryOrder=responses[0].data;
  assert.equal((await productById(products.b.id)).reserved,before.reserved+1);
 });
 await check('商品更新保留订单旧快照，付款事件与权益重放不重复',async()=>{
  products.a=await updateProduct(products.a,{title:'新商品标题 '+runId,priceMinor:2000,titleEn:'Changed sale title',refundPolicy:'修改后的退款说明，不应改变旧订单。'});
  const snapshot=line(await readOrder(accounts.user,digitalOrder.id),products.a);assert.equal(snapshot.priceMinor,1234);for(const [name,value] of Object.entries(localizedSnapshot))assert.equal(snapshot[name],value,'Existing order keeps original '+name);
  const requestId=key('digital_pay'),paid=await pay(accounts.user,digitalOrder.id,requestId);assert.equal(paid.totalMinor,2482);assert.equal(paid.paymentStatus,'paid');assert.equal(paid.fulfillmentStatus,'fulfilled');assert.equal(paid.status,'completed');
  const repeated=await pay(accounts.user,digitalOrder.id,requestId),again=await pay(accounts.user,digitalOrder.id,key('digital_pay_new'));assert.equal(events(repeated,'sandbox_pay').length,1);assert.equal(events(again,'sandbox_pay').length,1);
  const rights=await entitlements(accounts.user,digitalOrder.id);assert.equal(rights.length,1);assert.equal(rights[0].remaining,2);assert.equal(rights[0].environment,'sandbox');assert.equal(rights[0].sandboxOnly,true);assert.equal(rights[0].grantsProductionAccess,false);
  const second=(await api(accounts.user,'commerce/orders',orderPayload('pay_conflict',[[products.b,1]]))).data;await api(accounts.user,'commerce/orders/'+second.id+'/sandbox-pay',{requestId},'POST',409);
 });
 await check('沙箱付款不能解锁真实会员媒体或改变账号角色',async()=>{
  const pub=(await api(accounts.user,'public')).data,item=pub.content.courses.find(c=>c.id===courseId);assert(item);assert.equal(item.mediaUrl,'');assert.equal(item.requiresMembership,true);assert.equal(pub.user.role,'user');
  await api(accounts.user,'media/'+mediaId,undefined,'GET',403);const rights=await entitlements(accounts.user,digitalOrder.id);assert(rights.every(e=>e.sandboxOnly&&e.grantsProductionAccess===false));
 });
 await check('完整方案的统一沙箱会员订单激活隔离订阅，仍无正式媒体或角色',async()=>{
  const settings=(await api(accounts.admin,'admin/membership')).data.settings;await api(accounts.admin,'admin/membership/settings',{sandboxEnabled:true,productionEnabled:false,revision:settings.revision},'PATCH');
  const p=await saveProduct('membership',{type:'membership',contentId:key('sandbox_plan'),priceMinor:1999});
  await api(accounts.admin,'admin/membership/plans',{environment:'sandbox',status:'published',skuId:p.skuId,groupId:key('membership_group'),title:'交易专项隔离会员方案',description:'仅此隔离测试，不是正式定价。',billingMode:'recurring',term:{unit:'month',count:1},renewalPriceMinor:1999,benefits:{catalogScope:'member_catalog',courseIds:[],aiCredits:null,aiResetCycle:'none',other:['隔离测试权益']},ruleVersion:key('member_rules'),termsVersion:key('member_terms'),serviceTerms:'只用于验证统一订单与沙箱生命周期，不实际扣费。',refundPolicy:'提交待处理申请后人工核查。',graceDays:0,trialDays:0,promotionsEnabled:false});
  const order=(await api(accounts.other,'commerce/orders',orderPayload('membership',[[p,1]]))).data,terms=(await api(accounts.other,'membership/orders/'+order.id+'/snapshots')).data;assert.equal(terms.items.length,1);assert.equal(terms.items[0].firstPriceMinor,1999);await pay(accounts.other,order.id);
  const rights=await entitlements(accounts.other,order.id),state=(await api(accounts.other,'membership/status')).data,sub=state.items.find(x=>x.periods.some(v=>v.orderId===order.id));assert(sub);assert.equal(sub.status,'active');assert.equal(sub.environment,'sandbox');assert.equal(sub.hasSandboxAccess,true);assert.equal(sub.grantsProductionAccess,false);assert.equal(sub.actualBillingEnabled,false);
  assert.equal(rights.length,1);assert.equal(rights[0].type,'membership');assert.equal(rights[0].sandboxOnly,true);assert.equal(rights[0].grantsProductionAccess,false);assert.equal((await api(accounts.other,'auth/status')).data.user.role,'user');await api(accounts.other,'media/'+mediaId,undefined,'GET',403);
  await refund(order.id,key('membership_refund'),[{itemId:order.items[0].id,quantity:1}]);assert.equal((await entitlements(accounts.other,order.id))[0].status,'revoked');assert.equal((await api(accounts.other,'membership/status')).data.items.find(x=>x.id===sub.id).status,'revoked');
 });
 await check('沙箱关闭或商品下架时付款失败，不产生事件和权益',async()=>{
  let blocked=await saveProduct('blocked_payment');failedOrder=(await api(accounts.other,'commerce/orders',orderPayload('blocked_payment',[[blocked,1]]))).data;
  await api(accounts.admin,'admin/commerce/settings',{sandboxEnabled:false},'PATCH');await api(accounts.other,'commerce/orders/'+failedOrder.id+'/sandbox-pay',{requestId:key('blocked_pay')},'POST',503);await api(accounts.admin,'admin/commerce/settings',{sandboxEnabled:true},'PATCH');
  blocked=await updateProduct(blocked,{status:'archived'});await api(accounts.other,'commerce/orders/'+failedOrder.id+'/sandbox-pay',{requestId:key('blocked_pay')},'POST',409);
  const saved=await readOrder(accounts.other,failedOrder.id);assert.equal(saved.paymentStatus,'unpaid');assert.equal(saved.events.length,0);assert.equal((await entitlements(accounts.other,failedOrder.id)).length,0);
 });
 await check('库存1并发预占只能一单成功，付款扣库和退款回库各一次',async()=>{
  const p=await saveProduct('stock_race',{type:'physical',contentId:'',priceMinor:100,stock:1,shippingCountries:['CN']});
  const contexts=[accounts.user,accounts.other],responses=await Promise.all(contexts.map((ctx,i)=>api(ctx,'commerce/orders',orderPayload('race_'+i,[[p,1]],{shippingAddress:address}),'POST',null)));
  assert.deepEqual(responses.map(r=>r.status).sort(),[200,409]);const winner=responses.findIndex(r=>r.status===200);raceOrder=responses[winner].data;
  let saved=await productById(p.id);assert.equal(saved.stock,1);assert.equal(saved.reserved,1);assert.equal(saved.availableStock,0);
  await pay(contexts[winner],raceOrder.id);saved=await productById(p.id);assert.equal(saved.stock,0);assert.equal(saved.reserved,0);
  const item=raceOrder.items[0],refundId=key('race_refund');await refund(raceOrder.id,refundId,[{itemId:item.id,quantity:1}]);const repeated=await refund(raceOrder.id,refundId,[{itemId:item.id,quantity:1}]);assert.equal((await productById(p.id)).stock,1);assert.equal(repeated.inventoryEvents.length,1);assert.equal(repeated.inventoryEvents[0].quantityDelta,1);assert.equal(repeated.inventoryEvents[0].reason,'refund_restock');
  return {successes:1,stockAfterDuplicateRefund:1};
 });
 await check('已发货实物退款不自动补库存，重复退款不重复记录库存事件',async()=>{
  const p=await saveProduct('dispatched_stock',{type:'physical',contentId:'',priceMinor:100,stock:2,shippingCountries:['CN']}),order=(await api(shipping,'commerce/orders',orderPayload('dispatched_stock',[[p,1]],{shippingAddress:address}))).data;
  await pay(shipping,order.id);assert.equal((await productById(p.id)).stock,1);
  await api(accounts.admin,'admin/commerce/orders/'+order.id+'/fulfill',{trackingNumber:key('dispatched_tracking'),status:'shipped'});
  const items=[{itemId:order.items[0].id,quantity:1}],requestId=key('dispatched_refund');await refund(order.id,requestId,items);const repeated=await refund(order.id,requestId,items);assert.equal((await productById(p.id)).stock,1);assert.equal(repeated.fulfillmentStatus,'shipped');assert.equal(repeated.paymentStatus,'refunded');assert.equal(repeated.inventoryEvents.length,1);assert.equal(repeated.inventoryEvents[0].itemId,order.items[0].id);assert.equal(repeated.inventoryEvents[0].skuId,p.skuId);assert.equal(repeated.inventoryEvents[0].quantityDelta,0);assert.equal(repeated.inventoryEvents[0].reason,'refund_after_dispatch_no_restock');assert.equal(repeated.inventoryEvents[0].environment,'sandbox');
  return {stockBeforeOrder:2,stockAfterPaymentAndDuplicateRefund:1,refundInventoryEvents:1};
 });
 await check('实物地址和配送国家校验，运税按数量核价',async()=>{
  const body=orderPayload('physical',[[products.physicalA,2],[products.physicalB,1]]);
  await api(shipping,'commerce/orders',body,'POST',400);await api(shipping,'commerce/orders',{...body,shippingAddress:{...address,country:'US'}},'POST',400);
  physicalOrder=(await api(shipping,'commerce/orders',{...body,shippingAddress:address})).data;
  assert.equal(physicalOrder.subtotalMinor,1700);assert.equal(physicalOrder.shippingMinor,180);assert.equal(physicalOrder.taxMinor,70);assert.equal(physicalOrder.totalMinor,1950);assert.deepEqual(physicalOrder.shippingAddress,address);
 });
 assert(physicalOrder,'A valid physical order is required');
 await check('实物付款与发货独立状态，未付款和普通用户不能发货退款',async()=>{
  const fulfill='admin/commerce/orders/'+physicalOrder.id+'/fulfill',refundRoute='admin/commerce/orders/'+physicalOrder.id+'/refund';
  await api(accounts.admin,fulfill,{trackingNumber:key('tracking')},'POST',409);await api(shipping,fulfill,{trackingNumber:key('tracking')},'POST',403);await api(shipping,refundRoute,{requestId:key('illegal_refund'),items:[{itemId:physicalOrder.items[0].id,quantity:1}]},'POST',403);
  products.physicalA=await updateProduct(products.physicalA,{priceMinor:999});const paid=await pay(shipping,physicalOrder.id);assert.equal(paid.paymentStatus,'paid');assert.equal(paid.fulfillmentStatus,'awaiting_fulfillment');assert.equal(paid.totalMinor,1950);assert.equal(line(paid,products.physicalA).priceMinor,500);
  const shipped=(await api(accounts.admin,fulfill,{trackingNumber:key('tracking'),carrier:'合成物流',status:'shipped'})).data;assert.equal(shipped.paymentStatus,'paid');assert.equal(shipped.fulfillmentStatus,'shipped');assert.equal(shipped.tracking.trackingNumber,key('tracking'));
  const delivered=(await api(accounts.admin,fulfill,{trackingNumber:key('tracking'),status:'delivered'})).data;assert.equal(delivered.status,'completed');assert.equal(delivered.fulfillmentStatus,'delivered');await api(accounts.admin,fulfill,{trackingNumber:key('tracking'),status:'shipped'},'POST',409);
  assert.equal((await entitlements(shipping,physicalOrder.id)).length,0);
 });
 await check('本人售后申请可靠保存与幂等，不自动退款或改变库存权益',async()=>{
  const route='commerce/orders/'+physicalOrder.id+'/aftersale',body={requestId:key('physical_aftersale'),reason:'隔离测试售后申请，等待人工核查。',quantity:1};
  const beforeA=await productById(products.physicalA.id),beforeB=await productById(products.physicalB.id),requested=(await api(shipping,route,body)).data;
  assert.equal(requested.aftersaleStatus,'requested');assert.equal(requested.paymentStatus,'paid');assert.equal(requested.refundedMinor,0);assert.equal(events(requested,'refund').length,0);assert.equal(requested.aftersaleRequests.length,1);assert.equal(requested.aftersaleRequests[0].reason,body.reason);assert.equal(requested.aftersaleRequests[0].status,'pending');
  const repeated=(await api(shipping,route,body)).data;assert.equal(repeated.aftersaleRequests.length,1);assert.equal(repeated.aftersaleRequests[0].id,requested.aftersaleRequests[0].id);
  await api(shipping,route,{...body,reason:'同一编号下变更申请'},'POST',409);await api(accounts.user,route,{...body,requestId:key('foreign_aftersale')},'POST',404);
  assert.equal((await productById(products.physicalA.id)).stock,beforeA.stock);assert.equal((await productById(products.physicalB.id)).stock,beforeB.stock);
 });
 await check('部分退款仅冲正关联订单项，重复请求不二次退款或加库存',async()=>{
  const a=line(physicalOrder,products.physicalA),b=line(physicalOrder,products.physicalB),refundId=key('partial_physical');
  const beforeA=await productById(products.physicalA.id),beforeB=await productById(products.physicalB.id),items=[{itemId:a.id,quantity:1}];
  const partial=await refund(physicalOrder.id,refundId,items);assert.equal(partial.paymentStatus,'partially_refunded');assert.equal(partial.refundedMinor,570);assert.equal(line(partial,products.physicalA).refundedQuantity,1);assert.equal(line(partial,products.physicalB).refundedQuantity,0);
  const repeated=await refund(physicalOrder.id,refundId,items);assert.equal(repeated.refundedMinor,570);assert.equal(events(repeated,'refund').length,1);assert.equal((await productById(products.physicalA.id)).stock,beforeA.stock);assert.equal((await productById(products.physicalB.id)).stock,beforeB.stock);assert.equal(repeated.inventoryEvents.length,1);assert.equal(repeated.inventoryEvents[0].quantityDelta,0);assert.equal(repeated.inventoryEvents[0].reason,'refund_after_dispatch_no_restock');
  await refund(physicalOrder.id,refundId,[{itemId:b.id,quantity:1}],409);await refund(physicalOrder.id,key('over_refund'),[{itemId:a.id,quantity:2}],409);await refund(physicalOrder.id,key('foreign_item'),[{itemId:digitalOrder.items[0].id,quantity:1}],409);
 });
 await check('全额退款按剩余订单项完成并保持历史支付与履约独立',async()=>{
  const a=line(physicalOrder,products.physicalA),b=line(physicalOrder,products.physicalB),refundId=key('remaining_physical'),items=[{itemId:a.id,quantity:1},{itemId:b.id,quantity:1}];
  const full=await refund(physicalOrder.id,refundId,items);assert.equal(full.paymentStatus,'refunded');assert.equal(full.refundedMinor,1950);assert.equal(full.fulfillmentStatus,'delivered');assert.equal(events(full,'sandbox_pay').length,1);assert.equal(events(full,'refund').length,2);
  assert.equal((await refund(physicalOrder.id,refundId,items)).refundedMinor,1950);await refund(physicalOrder.id,key('already_refunded'),[{itemId:b.id,quantity:1}],409);
  assert.equal((await productById(products.physicalA.id)).stock,8);assert.equal((await productById(products.physicalB.id)).stock,9);assert.equal(full.inventoryEvents.length,3);assert(full.inventoryEvents.every(e=>e.quantityDelta===0&&e.reason==='refund_after_dispatch_no_restock'));
 });
 await check('数字部分退款减对应沙箱权益，全退撤销且真实媒体始终受保护',async()=>{
  const item=digitalOrder.items[0],partial=await refund(digitalOrder.id,key('digital_partial'),[{itemId:item.id,quantity:1}]);assert.equal(partial.refundedMinor,1241);let rights=await entitlements(accounts.user,digitalOrder.id);assert.equal(rights.length,1);assert.equal(rights[0].remaining,1);assert.equal(rights[0].status,'active');
  const full=await refund(digitalOrder.id,key('digital_rest'),[{itemId:item.id,quantity:1}]);assert.equal(full.refundedMinor,2482);rights=await entitlements(accounts.user,digitalOrder.id);assert.equal(rights[0].remaining,0);assert.equal(rights[0].status,'revoked');await api(accounts.user,'media/'+mediaId,undefined,'GET',403);
 });
 await check('订单与权益跨账号隔离，匿名支付和普通用户资金操作拒绝',async()=>{
  await api(accounts.anonymous,'commerce/orders?environment=sandbox',undefined,'GET',401);await api(accounts.other,'commerce/orders/'+digitalOrder.id,undefined,'GET',404);await api(accounts.other,'commerce/orders/'+digitalOrder.id+'/sandbox-pay',{requestId:key('foreign_pay')},'POST',404);await api(accounts.anonymous,'commerce/orders/'+digitalOrder.id+'/sandbox-pay',{requestId:key('anonymous_pay')},'POST',401);
  const own=(await api(accounts.other,'commerce/orders?environment=sandbox')).data.items;assert(!own.some(o=>o.id===digitalOrder.id||o.id===physicalOrder.id));assert(!(await entitlements(accounts.other)).some(e=>e.orderId===digitalOrder.id));
  await api(accounts.other,'admin/commerce/orders/'+physicalOrder.id+'/refund',{requestId:key('foreign_admin'),items:[{itemId:physicalOrder.items[0].id,quantity:1}]},'POST',403);
 });
 await check('商品版本并发控制与库存保护拒绝过期编辑',async()=>{
  const original=products.b,next=await updateProduct(original,{description:'本轮已更新版本'});await api(accounts.admin,'admin/commerce/products',{...templates.get(next.id),id:original.id,version:original.version,title:'旧版本写入'},'POST',409);
  const reserved=(await productById(next.id)).reserved;assert(reserved>0);await api(accounts.admin,'admin/commerce/products',{...templates.get(next.id),id:next.id,version:next.version,stock:reserved-1},'POST',409);
  products.b=next;
 });
 if(!h.args['http-only'])await browserChecks();
}
async function browserChecks(){
 const uiProduct=await saveProduct('ui_work',{priceMinor:880,stock:10});await api(uiBuyer,'commerce/cart',{environment,items:[]},'PATCH');
 const {page}=await h.browserContext(await uiBuyer.storageState());
 const ready=async()=>{await page.waitForFunction(()=>!document.documentElement.dataset.ambientTransition);await page.evaluate(()=>document.fonts.ready);};
 await check('真实社群五标签、商城详情和数字无地址购物车可达',async()=>{
  await page.goto(h.base+'/experience?lang=zh-Hans');await page.waitForFunction(()=>px.loaded&&!pxBootstrapPending);await page.evaluate(()=>navigate('community'));await ready();
  const tabs=page.locator('.community-tabs [data-to]');assert.equal(await tabs.count(),5);const routes=await tabs.evaluateAll(es=>es.map(e=>e.dataset.to));for(const old of ['friends','communityInbox','communityTeachers','community'])assert(routes.includes(old),'Existing community feature remains reachable: '+old);assert(routes.includes('commerceShop'));
  await page.locator('.community-tabs [data-to=commerceShop]').click();await page.waitForFunction(()=>state.page==='commerceShop');await ready();
  const sandbox=page.locator('[data-commerce-action=environment][data-environment=sandbox]');await sandbox.waitFor();await sandbox.click();
  await page.locator('[data-commerce-action=product][data-id="'+uiProduct.id+'"]').waitFor();await page.locator('[data-commerce-action=product][data-id="'+uiProduct.id+'"]').click();await page.waitForFunction(()=>state.page==='commerceProduct');
  await page.locator('[data-commerce-action=add][data-id="'+uiProduct.id+'"]').click();await page.waitForFunction(()=>state.page==='commerceCart'&&!!document.getElementById('co-checkout-form'));await ready();
  assert.equal(await page.locator('#co-checkout-form input[name=country],#co-checkout-form input[name=address],#co-checkout-form input[name=line1]').count(),0);assert((await page.locator('.co-cart-items').innerText()).includes(uiProduct.title));
  await page.waitForFunction(()=>!coState().loading&&!coState().busy);await page.locator('#co-checkout-form input[name=accept]').check();await page.evaluate(()=>render(false));await ready();assert(await page.locator('#co-checkout-form input[name=accept]').isChecked(),'Consent survives an actual render');
  await page.evaluate(()=>coLoad(true));await page.waitForFunction(()=>!coState().loading&&!coState().busy);assert(await page.locator('#co-checkout-form input[name=accept]').isChecked(),'Consent survives the existing asynchronous catalog/cart refresh');
  const changeQuantity=async(sku,delta,quantity)=>{await page.locator('[data-commerce-action=quantity][data-id="'+sku+'"][data-delta="'+delta+'"]').click();await page.waitForFunction(({sku,quantity})=>!coState().loading&&!coState().busy&&(coState().cart.find(i=>i.skuId===sku)?.quantity||0)===quantity,{sku,quantity});};
  await changeQuantity(uiProduct.skuId,-1,0);assert.equal(await page.locator('#co-checkout-form').count(),0);
  const addFromShop=async p=>{await page.locator('.co-navigation [data-to=commerceShop]').click();await page.locator('[data-commerce-action=product][data-id="'+p.id+'"]').click();await page.locator('[data-commerce-action=add][data-id="'+p.id+'"]').click();await page.waitForFunction(()=>state.page==='commerceCart'&&!coState().loading&&!coState().busy&&!!document.getElementById('co-checkout-form'));};
  await addFromShop(products.physicalA);for(const [name,value] of Object.entries(address))await page.locator('#co-checkout-form input[name="'+name+'"]').fill(value);await page.locator('#co-checkout-form input[name=accept]').check();await page.evaluate(()=>render(false));await ready();
  for(const [name,value] of Object.entries(address))assert.equal(await page.locator('#co-checkout-form input[name="'+name+'"]').inputValue(),value,'Address survives render: '+name);assert(await page.locator('#co-checkout-form input[name=accept]').isChecked());
  await changeQuantity(products.physicalA.skuId,1,2);assert.equal(await page.locator('#co-checkout-form input[name=accept]').isChecked(),false,'Changing cart quantity requires fresh consent');for(const [name,value] of Object.entries(address))assert.equal(await page.locator('#co-checkout-form input[name="'+name+'"]').inputValue(),value);
  await changeQuantity(products.physicalA.skuId,-1,1);await changeQuantity(products.physicalA.skuId,-1,0);await addFromShop(uiProduct);assert.equal(await page.locator('#co-checkout-form input[name=accept]').isChecked(),false);assert.equal(await page.locator('#co-checkout-form input[name=address]').count(),0);
  await h.capture(page,'数字购物车');
 });
 let uiOrderId;
 await check('浏览器创建订单、沙箱付款、重新查询和订单历史真实闭环',async()=>{
  await page.locator('#co-checkout-form input[name=accept]').check();const created=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/commerce/orders'&&r.request().method()==='POST');await page.locator('#co-checkout-form button[type=submit]').click();const response=await created;assert.equal(response.status(),200);const order=await response.json();uiOrderId=order.id;assert.equal(order.totalMinor,880);await page.locator('[data-commerce-order="'+uiOrderId+'"]').waitFor();
  const payment=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/commerce/orders/'+uiOrderId+'/sandbox-pay'&&r.request().method()==='POST');await page.locator('[data-commerce-action=pay][data-id="'+uiOrderId+'"]').click();assert.equal((await payment).status(),200);await page.waitForFunction(id=>coState().order?.id===id&&coState().order.paymentStatus==='paid',uiOrderId);assert.equal((await readOrder(uiBuyer,uiOrderId)).events.length,1);
  await page.locator('[data-commerce-action=refresh]').click();await page.waitForFunction(()=>!coState().loading);await page.locator('.co-navigation [data-to=commerceOrders]').click();await page.locator('[data-commerce-action=order][data-id="'+uiOrderId+'"]').waitFor();await page.locator('[data-commerce-action=order][data-id="'+uiOrderId+'"]').click();await page.locator('[data-commerce-order="'+uiOrderId+'"]').waitFor();await h.capture(page,'已支付订单');
  await page.reload();await page.waitForFunction(()=>px.loaded&&!pxBootstrapPending);await page.evaluate(()=>navigate('commerceShop'));await page.locator('[data-commerce-action=environment][data-environment=sandbox]').waitFor();await page.locator('[data-commerce-action=environment][data-environment=sandbox]').click();await page.locator('.co-navigation [data-to=commerceOrders]').click();await page.locator('[data-commerce-action=order][data-id="'+uiOrderId+'"]').waitFor();
  return {paidOrderRecovered:true,bankCharge:false};
 });
 await check('浏览器售后申请持久化、同理由重复提交幂等且不自动退款',async()=>{
  assert(uiOrderId);await page.locator('[data-commerce-action=order][data-id="'+uiOrderId+'"]').click();await page.locator('[data-commerce-order="'+uiOrderId+'"]').waitFor();await ready();
  const reason='浏览器隔离售后申请：请求人工核查，不执行自动退款。';
  for(let attempt=0;attempt<2;attempt++){
   await page.locator('button[data-commerce-action=support]').click();await page.locator('#co-aftersale-form textarea[name=reason]').fill(reason);
   const submitted=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/commerce/orders/'+uiOrderId+'/aftersale'&&r.request().method()==='POST');await page.locator('#co-aftersale-form button[type=submit]').click();const response=await submitted;assert.equal(response.status(),200);const order=await response.json();assert.equal(order.aftersaleRequests.length,1);assert.equal(order.paymentStatus,'paid');assert.equal(order.refundedMinor,0);assert.equal(events(order,'refund').length,0);
   await page.locator('#co-aftersale-form').waitFor({state:'hidden'});await page.waitForFunction(({id,reason})=>coState().order?.id===id&&coState().order.aftersaleRequests?.some(x=>x.reason===reason),{id:uiOrderId,reason});assert((await page.locator('.co-aftersale-list').innerText()).includes(reason));
  }
  const saved=await readOrder(uiBuyer,uiOrderId);assert.equal(saved.aftersaleStatus,'requested');assert.equal(saved.aftersaleRequests.length,1);assert.equal(saved.aftersaleRequests[0].status,'pending');assert.equal(saved.paymentStatus,'paid');assert.equal(saved.refundedMinor,0);
  await page.locator('[data-commerce-action=refresh]').click();await page.waitForFunction(()=>!coState().loading);assert((await page.locator('.co-aftersale-list').innerText()).includes(reason));await h.capture(page,'售后申请进度');return {persistedRequests:1,duplicateSubmissions:2,automaticRefund:false};
 });
 await check('商城订单四语、窄屏布局与实际返回入口可用',async()=>{
  for(const width of [375,430])for(const lang of ['zh','zh-Hant','en','bo']){await page.setViewportSize({width,height:844});await page.evaluate(({lang})=>{state.lang=lang;render(false);},{lang});await ready();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1&&document.getElementById('app').scrollWidth<=document.getElementById('app').clientWidth+1));assert(await page.locator('.co-page .ew-page-back').first().isVisible());}
  assert.deepEqual(h.report.errors,[]);return {widths:[375,430],languages:4};
 });
}
(async()=>{let fatal;try{await main();}catch(e){fatal=e;}await h.finish(fatal);})();
