// Readable native viewport captures, with one actual digital-entitlement callback fixture.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {makeHarness}=require('./负责人优化建议-交易测试工具.cjs');
const h=makeHarness(),{api,check}=h,uuid=()=>crypto.randomUUID();
const secret=process.env.EW_PAYMENT_CALLBACK_QA_SECRET,token=process.env.CALLBACK_TEST_TOKEN;
const queue='admin/payment-callbacks';
async function run(){
 assert(h.args.base&&secret&&token,'Use the isolated PAY08 launcher --suite=visual');
 await h.start();
 h.report.scope='Supplemental native browser viewport captures of the new Chinese admin panel at 360 and 1280 widths, plus actual sandbox digital entitlement deduplication. No full-page downscaling or pixel editing.';
 h.report.coverage={http:true,ui:true,realPayments:false,production:false,signature:'sandbox-hmac-fixture-only',capture:'native viewport screenshots'};
 const sourceNames=['04_研发源码/app/r4/backend/payment_callbacks.py','04_研发源码/app/cloud/lib/payment-callbacks.ts','04_研发源码/app/r4/payment-callback-admin.js'];
 const identity=()=>Object.fromEntries(sourceNames.map(name=>[name,h.sha(fs.readFileSync(path.join(h.ROOT,name)))]));
 const startIdentity=identity();h.report.callbackSources=startIdentity;
 const {admin,user,other,anonymous}=await h.seed();
 await api(admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
 const course=(await api(anonymous,'public')).data.content.courses[0];assert(course?.id);
 const product=(await api(admin,'admin/commerce/products',{title:'PAY08 合成数字权益',description:'仅隔离测试，不授予正式媒体权限。',type:'digital',environment:'sandbox',status:'published',currency:'CNY',stock:10,priceMinor:300,contentId:course.id,sku:'pay08-visual-'+h.runId})).data.item;
 const place=async()=>(await api(user,'commerce/orders',{requestId:uuid(),environment:'sandbox',items:[{skuId:product.skuId,quantity:1}]})).data;
 const bodyFor=o=>({eventId:uuid(),transactionId:uuid(),orderId:o.id,type:'payment.succeeded',amountMinor:o.totalMinor,currency:o.currency});
 const receive=async body=>{
  const raw=JSON.stringify(body),stamp=String(Math.floor(Date.now()/1000));
  const signature=crypto.createHmac('sha256',secret).update(stamp+'.'+raw).digest('hex');
  const response=await anonymous.post(h.base+'/api/payment-callbacks/sandbox',{data:Buffer.from(raw),headers:{'Content-Type':'application/json','X-EW-Callback-Timestamp':stamp,'X-EW-Callback-Signature':signature}});
  assert.equal(response.status(),202);return response.json();
 };
 const control=async data=>{const r=await anonymous.post(h.base+'/__callback-test/control',{headers:{'X-Callback-Test':token},data});assert.equal(r.status(),200);return r.json();};
 const consume=()=>api(admin,queue+'/process',{limit:10});
 const capture=async(page,label)=>{const file=h.moduleName+'-'+h.target+'-'+h.runId+'-'+label+'.png';await page.screenshot({path:path.join(__dirname,file),fullPage:false});h.report.captures.push(file);};
 const o=await place(),body={...bodyFor(o),eventId:'evt_'+('a'.repeat(96)),transactionId:'txn_'+('b'.repeat(96))};
 const accepted=await receive(body);
 const page=(await h.browserContext(await admin.storageState())).page;
 await page.goto(h.base+'/admin');await page.locator('[data-nav=commerce]').first().click();
 const panel=page.locator('#payment-callback-admin');
 await panel.locator('[data-callback-action=load]').click();
 await panel.locator('[data-callback-action=view][data-id="'+accepted.receiptId+'"]').waitFor();

 await check('360与1280视口显示顶部控件、长编号列表及横向滚动后的操作列',async()=>{
  for(const width of [360,1280]){
   await page.setViewportSize({width,height:850});
   await panel.evaluate(el=>el.scrollIntoView({block:'start'}));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await capture(page,width+'-收件箱顶部与列表');
   const wrap=panel.locator('.table-wrap').first();await wrap.hover();await page.mouse.wheel(800,0);await page.waitForTimeout(100);
   const metrics=await wrap.evaluate(el=>({client:el.clientWidth,scroll:el.scrollWidth,left:el.scrollLeft}));
   if(metrics.scroll>metrics.client+1)assert(metrics.left>0);
   await capture(page,width+'-列表操作列');
  }
 });

 await check('原生消费数字订单后只发一份沙箱权益，重复事件和交易不重复发放',async()=>{
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/'+queue+'/process')&&r.request().method()==='POST'),panel.locator('[data-callback-action=process]').click()]);
  await panel.locator('[data-callback-action=view][data-id="'+accepted.receiptId+'"]:enabled').waitFor();
  await panel.locator('[data-callback-action=view][data-id="'+accepted.receiptId+'"]').click();
  await page.locator('#callback-receipt-detail h3').filter({hasText:'已应用'}).waitFor();
  const before=(await api(user,'commerce/entitlements?environment=sandbox')).data;
  const entries=before.items.filter(item=>item.orderId===o.id);assert.equal(entries.length,1);assert.equal(entries[0].status,'active');assert.equal(entries[0].grantsProductionAccess,false);
  await receive(body);await receive({...body,eventId:uuid()});await consume();
  const after=(await api(user,'commerce/entitlements?environment=sandbox')).data;
  assert.deepEqual(after.items.filter(item=>item.orderId===o.id),entries);assert.equal(after.grantsProductionAccess,false);
  await api(other,'commerce/orders/'+o.id,undefined,'GET',404);
  const raw=await control({action:'snapshot',orderId:o.id,receiptId:accepted.receiptId});assert.equal(raw.ledger.length,1);assert.equal(raw.entitlements.length,1);
 });

 await check('360与1280视口完整阅读通知详情及接收领取应用记录',async()=>{
  await panel.locator('[data-callback-action=load]').click();
  await panel.locator('[data-callback-action=view][data-id="'+accepted.receiptId+'"]').click();
  const detail=page.locator('#callback-receipt-detail');
  await detail.locator('h3').filter({hasText:'已应用'}).waitFor();
  for(const width of [360,1280]){
   await page.setViewportSize({width,height:850});await detail.evaluate(el=>el.scrollIntoView({block:'start'}));
   assert(await detail.locator('p').first().evaluate(el=>el.scrollWidth<=el.clientWidth+1));
   await capture(page,width+'-通知详情与处理记录');
  }
 });

 await check('原生重新排队与恢复处理后的状态有可读视口证据',async()=>{
  const retryOrder=await place(),pending=await receive(bodyFor(retryOrder));
  await control({action:'fail-apply-on',orderId:retryOrder.id});
  try{await consume();}finally{await control({action:'fail-apply-off'});}
  await panel.locator('[data-callback-action=load]').click();await panel.locator('[data-callback-action=view][data-id="'+pending.receiptId+'"]').click();
  const detail=page.locator('#callback-receipt-detail');await detail.locator('[data-callback-action=retry]').waitFor();
  await page.setViewportSize({width:360,height:850});await detail.evaluate(el=>el.scrollIntoView({block:'start'}));
  await capture(page,'360-等待重试详情');
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/'+pending.receiptId+'/retry')),detail.locator('[data-callback-action=retry]').click()]);
  await panel.locator('[data-callback-action=process]:enabled').waitFor();
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/'+queue+'/process')),panel.locator('[data-callback-action=process]').click()]);
  await detail.locator('h3').filter({hasText:'已应用'}).waitFor();await detail.evaluate(el=>el.scrollIntoView({block:'start'}));
  await capture(page,'360-重试成功与处理记录');
  assert.equal((await api(admin,queue+'/'+pending.receiptId)).data.item.attempts,2);
  assert.deepEqual(identity(),startIdentity);assert(!JSON.stringify(h.report).includes(secret));
 });
}
run().then(()=>h.finish(),error=>h.finish(error));
