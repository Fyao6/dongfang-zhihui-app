const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {makeHarness} = require('./负责人优化建议-交易测试工具.cjs');
const h = makeHarness();
const {api,check} = h;
const uuid = () => crypto.randomUUID();
const kinds = ['duplicate-charge','payment-missing','restore-failed','cancel-renewal'];
const submit = 'payment-support/tickets';
const queue = 'admin/payment-support/tickets';
const orderRoute = id => 'payment-support/orders/'+id;
const actionRoute = id => queue+'/'+id+'/actions';
const payload = (kind, orderId='', eventId='', message='合成支付问题') => ({requestId:uuid(),kind,orderId,eventId,message});
const action = (version,status,reply='') => ({requestId:uuid(),version,status,reply});

async function main(){
 await h.start();
 const sourceNames=['04_研发源码/app/r4/backend/payment_support.py','04_研发源码/app/cloud/lib/payment-support.ts',
  '04_研发源码/app/r4/payment-support-ui.js','04_研发源码/app/r4/payment-support-admin.js',
  '04_研发源码/app/r4/backend/privacy_retention.py','04_研发源码/app/cloud/lib/privacy-retention.ts',
  '04_研发源码/app/r4/backend/privacy.py','04_研发源码/app/cloud/lib/privacy-api.ts',
  '04_研发源码/app/r4/membership-lifecycle-ui.js','04_研发源码/app/r4/build.py','04_研发源码/app/cloud/prepare.py'];
 const identity=()=>Object.fromEntries(sourceNames.map(name=>[name,h.sha(fs.readFileSync(path.join(h.ROOT,name)))]));
 h.report.paymentSupportSources=identity();
 h.report.scope='Actual isolated HTTP and native browser payment support. Four issue categories, sandbox order facts, owner/admin access, privacy and persistence.';
 const {admin,user,other,anonymous}=await h.seed();
 await api(admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
 const item=(await api(admin,'admin/commerce/products',{title:'PAY19 隔离样品',type:'physical',environment:'sandbox',
  status:'published',currency:'CNY',shippingCountries:['CN'],stock:10,priceMinor:300,sku:'pay-help-'+h.runId})).data.item;
 const place=async account=>(await api(account,'commerce/orders',{
  requestId:uuid(),environment:'sandbox',items:[{skuId:item.skuId,quantity:1}],
  shippingAddress:{name:'合成收件人',country:'CN',city:'测试市',address:'测试路 1 号',postalCode:'000000'}
 })).data;
 const paid=await place(user),unpaid=await place(user),foreign=await place(other);
 for(const [account,order] of [[user,paid],[other,foreign]])await api(account,'commerce/orders/'+order.id+'/sandbox-pay',{requestId:uuid()});
 const first=(await api(user,orderRoute(paid.id))).data;
 const foreignEvent=(await api(other,orderRoute(foreign.id))).data.events[0];
 const tickets={};

 await check('本人可查询已付与未付订单和最小支付事实',async()=>{
  assert.equal(first.order.paymentStatus,'paid');
  assert.equal(first.events.length,1);
  assert.equal(first.events[0].kind,'sandbox_pay');
  assert.equal(first.events[0].amountMinor,300);
  assert.deepEqual(Object.keys(first.order).sort(),['currency','environment','fulfillmentStatus','id','paymentStatus','refundedMinor','totalMinor']);
  assert.deepEqual(Object.keys(first.events[0]).sort(),['amountMinor','created','currency','id','kind']);
  assert.deepEqual((await api(user,orderRoute(unpaid.id))).data.events,[]);
  await api(anonymous,orderRoute(paid.id),undefined,'GET',401);
  await api(other,orderRoute(paid.id),undefined,'GET',404);
 });

 await check('四种问题均有独立工单，支持订单与事件关联及无订单申报',async()=>{
  const paidEvent=first.events[0].id;
  const bodies=[payload(kinds[0],paid.id,paidEvent),payload(kinds[1],unpaid.id),payload(kinds[2],paid.id),payload(kinds[3])];
  for(const body of bodies)tickets[body.kind]=(await api(user,submit,body)).data.ticket;
  for(const [i,kind] of kinds.entries()){
   const ticket=tickets[kind],original=bodies[i];
   assert.equal(ticket.kind,kind);assert.equal(ticket.status,'submitted');
   assert.equal(ticket.orderId,original.orderId||null);assert.equal(ticket.eventId,original.eventId||null);
  }
  assert.equal(new Set(Object.values(tickets).map(t=>t.id)).size,4);
  assert.equal((await api(user,submit)).data.items.length,4);
 });

 await check('拒绝跨账号、错配支付事件、匿名提交及空白无订单请求',async()=>{
  const id=tickets[kinds[0]].id;
  await api(other,submit+'/'+id,undefined,'GET',404);
  await api(other,submit+'?before='+id,undefined,'GET',404);
  assert.deepEqual((await api(other,submit)).data.items,[]);
  await api(other,submit,payload(kinds[0],paid.id,first.events[0].id),'POST',404);
  await api(user,submit,payload(kinds[0],paid.id,foreignEvent.id),'POST',404);
  await api(user,submit,payload(kinds[1],unpaid.id,first.events[0].id),'POST',404);
  await api(anonymous,submit,payload(kinds[3]),'POST',401);
  await api(user,submit,payload(kinds[3],'','',' '),'POST',400);
  await api(user,submit,payload('unknown',paid.id),'POST',400);
  await api(user,queue,undefined,'GET',403);
  await api(user,actionRoute(id),action(1,'accepted'),'POST',403);
 });

 await check('同时提交相同请求只生成一单，改内容复用请求号被拒绝',async()=>{
  const body=payload(kinds[2],paid.id,'','并发重试 🧾');
  const results=await Promise.all([api(user,submit,body),api(user,submit,body)]);
  assert.equal(results[0].data.ticket.id,results[1].data.ticket.id);
  await api(user,submit,{...body,message:'不同内容'},'POST',409);
  assert.equal((await api(user,submit)).data.items.filter(x=>x.id===results[0].data.ticket.id).length,1);
 });

 await check('管理后台可核对关联记录，版本、并发与重复受理有保护',async()=>{
  const id=tickets[kinds[0]].id;
  const detail=(await api(admin,queue+'/'+id)).data;
  assert.equal(detail.ticket.eventId,first.events[0].id);
  assert.deepEqual(detail.payment,first);
  assert.equal(detail.accountClosed,false);
  await api(admin,actionRoute(id),action(1,'resolved','提前办结'),'POST',409);
  const bodies=[action(1,'accepted','开始核对。'),action(1,'accepted','另一操作。')];
  const results=await Promise.all(bodies.map(body=>api(admin,actionRoute(id),body,'POST',null)));
  assert.deepEqual(results.map(r=>r.status).sort(),[200,409]);
  const accepted=results.findIndex(r=>r.status===200);
  assert.equal((await api(admin,actionRoute(id),bodies[accepted])).data.ticket.version,2);
  await api(admin,actionRoute(id),{...bodies[accepted],reply:'改写原受理'},'POST',409);
  await api(admin,actionRoute(id),action(2,'resolved'),'POST',400);
  await api(admin,actionRoute(id),action(2,'resolved','已核对一条测试支付记录。'));
  const owner=(await api(user,submit+'/'+id)).data.ticket;
  assert.equal(owner.status,'resolved');
  assert.deepEqual(owner.replies.map(x=>x.reply),[bodies[accepted].reply,'已核对一条测试支付记录。']);
  assert((await api(admin,queue+'?status=resolved')).data.items.some(row=>row.id===id));
  const listed=(await api(admin,queue+'?status=resolved')).data.items.find(row=>row.id===id);
  assert(!Object.hasOwn(listed,'message')&&!Object.hasOwn(listed,'replies'));
 });

 await check('历史工单稳定分页，上一页和下一页没有重叠',async()=>{
  const account=await h.context();
  await api(account,'auth/register',{username:'paypage_'+h.runId,password:uuid(),name:'工单分页测试'});
  for(let i=0;i<27;i++)await api(account,submit,payload(kinds[3],'','','合成分页 '+i));
  const firstPage=(await api(account,submit)).data;
  assert.equal(firstPage.items.length,25);
  const secondPage=(await api(account,submit+'?before='+firstPage.next)).data;
  assert.equal(secondPage.items.length,2);
  assert.equal(secondPage.next,null);
  assert.equal(new Set([...firstPage.items,...secondPage.items].map(row=>row.id)).size,27);
 });

 await check('本人导出涵盖工单和回复，支付事实及订单状态未被客服修改',async()=>{
  const owner=(await api(user,'privacy/export')).data.serverData;
  const stranger=(await api(other,'privacy/export')).data.serverData;
  assert(owner.paymentSupportTickets.some(row=>row.id===tickets[kinds[0]].id));
  assert(owner.paymentSupportReplies.some(row=>row.reply==='已核对一条测试支付记录。'));
  assert.equal(stranger.paymentSupportTickets.length,0);
  assert.equal(stranger.paymentSupportReplies.length,0);
  assert.deepEqual((await api(user,orderRoute(paid.id))).data,first);
  assert.equal((await api(user,orderRoute(unpaid.id))).data.order.paymentStatus,'unpaid');
 });

 await check('账号关闭事务清理工单正文，保留订单及工单处理事实',async()=>{
  const account=await h.context(),password=uuid();
  await api(account,'auth/register',{username:'payclose_'+h.runId,password,name:'工单关闭测试'});
  const closeOrder=await place(account);
  const ticket=(await api(account,submit,payload(kinds[1],closeOrder.id))).data.ticket;
  await api(admin,actionRoute(ticket.id),action(1,'accepted','关闭前受理回复'));
  const proof={requestId:uuid(),nonce:crypto.randomBytes(32).toString('hex')};
  const {challengeId}=(await api(account,'account-closure/prepare',{...proof,password})).data;
  const {receipt}=(await api(account,'account-closure/confirm',{...proof,challengeId,confirmed:true,renewalAcknowledged:true})).data;
  assert.equal(receipt.accountClosed,true);
  assert(receipt.local.retainedCategories.includes('payment-support-metadata'));
  const detail=(await api(admin,queue+'/'+ticket.id)).data;
  assert.equal(detail.accountClosed,true);
  assert.equal(detail.ticket.message,'');
  assert.equal(detail.ticket.replies[0].reply,'');
  assert.equal(detail.payment.order.id,closeOrder.id);
  await api(account,submit+'/'+ticket.id,undefined,'GET',401);
  await api(admin,actionRoute(ticket.id),action(2,'resolved','关闭后禁止回复'),'POST',409);
 });

 if(!h.args['http-only']){
  await check('订单原生入口提交工单，后台原生控件回复，APP回查及逐级返回',async()=>{
   const page=(await h.browserContext(await user.storageState())).page;
   await page.goto(h.base+'/experience?page=commerceOrders&lang=zh&mode=night');
   await page.locator('[data-commerce-action=environment][data-environment=sandbox]').click();
   await page.locator('.co-navigation [data-to=commerceOrders]').click();
   await page.locator('[data-commerce-action=order][data-id="'+paid.id+'"]').click();
   await page.locator('[data-pay-help=open][data-order="'+paid.id+'"]').click();
   const form=page.locator('#pay-help-form');
   await form.locator('[name=kind]').selectOption('payment-missing');
   await form.locator('[name=eventId]').selectOption(first.events[0].id);
   await form.locator('[name=message]').fill('浏览器实测支付问题 <b>以文本显示</b>');
   const created=page.waitForResponse(r=>r.url().endsWith('/api/'+submit)&&r.request().method()==='POST');
   await form.locator('[type=submit]').click();
   const result=await created;assert.equal(result.status(),200);
   const ticket=(await result.json()).ticket;
   const card=page.locator('[data-pay-help-ticket="'+ticket.id+'"]');
   await card.getByText('浏览器实测支付问题 <b>以文本显示</b>').waitFor();
   assert.equal(await card.locator('b').count(),0);
   await h.capture(page,'APP工单');
   await page.locator('.ew-page-back').click();
   await page.locator('[data-pay-help=open][data-order="'+paid.id+'"]').waitFor();
   const staff=(await h.browserContext(await admin.storageState())).page;
   await staff.goto(h.base+'/admin');
   await staff.locator('[data-nav=commerce]').first().click();
   await staff.locator('[data-pay-admin=load]').click();
   await staff.locator('[data-pay-admin=view][data-id="'+ticket.id+'"]').click();
   await staff.locator('#pay-admin-action button').click();
   await staff.locator('#pay-admin-action textarea[required]').fill('后台实测回复，请查看测试订单。');
   await staff.locator('#pay-admin-action button').click();
   await staff.getByText('后台实测回复，请查看测试订单。',{exact:false}).waitFor();
   await h.capture(staff,'后台回复');
   await page.locator('[data-pay-help=open][data-order="'+paid.id+'"]').click();
   await card.getByText('后台实测回复，请查看测试订单。',{exact:false}).waitFor();
  });

  await check('简繁英藏、两种主题、窄屏与桌面可用，恢复与退订自助入口可往返',async()=>{
   const page=(await h.browserContext(await user.storageState())).page;
   const views=[['zh',320,'night'],['zh-Hant',360,'day'],['en',390,'night'],['bo',390,'day'],['en',1100,'day']];
   for(const [lang,width,mode] of views){
    await page.setViewportSize({width,height:850});
    await page.goto(h.base+'/experience?page=membershipRestore&lang='+lang+'&mode='+mode);
    await page.locator('[data-pay-help=open][data-kind=restore-failed]').click();
    const form=page.locator('#pay-help-form');
    await form.locator('[type=submit]:enabled').waitFor();
    assert.equal(await form.locator('[name=kind]').inputValue(),'restore-failed');
    assert.equal(await form.locator('[name=kind] option').count(),4);
    assert(await page.locator('.pay-help').evaluate(e=>e.scrollWidth<=e.clientWidth+1));
    await form.locator('[data-to=membershipRestore]').click();
    await page.locator('[data-pay-help=open][data-kind=restore-failed]').waitFor();
    await page.goto(h.base+'/experience?page=membershipCancel&lang='+lang+'&mode='+mode);
    await page.locator('[data-pay-help=open][data-kind=cancel-renewal]').click();
    await form.locator('[type=submit]:enabled').waitFor();
    assert.equal(await form.locator('[name=kind]').inputValue(),'cancel-renewal');
    await form.locator('[data-to=membershipCancel]').click();
    await page.locator('[data-pay-help=open][data-kind=cancel-renewal]').waitFor();
   }
   return views;
  });
 }
 await check('专项前后源文件保持同一身份',async()=>assert.deepEqual(identity(),h.report.paymentSupportSources));
}

main().then(()=>h.finish(),error=>h.finish(error));
