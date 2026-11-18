// PAY09 native app/admin controls and readable viewport evidence, using a real signed HTTP fixture.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {makeHarness}=require('./负责人优化建议-交易测试工具.cjs');
const h=makeHarness(),{api,check}=h,uuid=()=>crypto.randomUUID();
const endpoint=process.env.EW_PAYMENT_QUERY_SANDBOX_ENDPOINT,token=process.env.RECOVERY_TEST_TOKEN;
async function run(){
 assert(h.args.base&&endpoint&&token,'Use the owned PAY09 launcher --suite=visual');await h.start();
 h.report.scope='Native APP query/refresh/return and Chinese admin queue controls. Four languages, both themes, 360/1280 viewports, true horizontal scrolling and timer continuity. Signed HTTP fixture only; captures use native viewport pixels.';
 const {admin,user,anonymous}=await h.seed();
 const sources=['04_研发源码/app/r4/payment-recovery-ui.js','04_研发源码/app/r4/payment-recovery-admin.js','04_研发源码/app/r4/backend/payment_recovery.py','04_研发源码/app/cloud/lib/payment-recovery.ts'];
 const identity=()=>Object.fromEntries(sources.map(name=>[name,h.sha(fs.readFileSync(path.join(h.ROOT,name)))]));const sourceIdentity=identity();h.report.recoverySources=sourceIdentity;
 const fixture=async data=>{const r=await anonymous.post(new URL(endpoint).origin+'/pay09-fixture/control',{headers:{'X-Recovery-Test':token},data});assert.equal(r.status(),200);return r.json();};
 const control=async data=>{const r=await anonymous.post(h.base+'/__recovery-test/control',{headers:{'X-Recovery-Test':token},data});assert.equal(r.status(),200);return r.json();};
 const capture=async(page,label)=>{const file=h.moduleName+'-'+h.target+'-'+h.runId+'-'+label+'.png';await page.screenshot({path:path.join(__dirname,file),fullPage:false});h.report.captures.push(file);};
 await api(admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
 const product=(await api(admin,'admin/commerce/products',{title:'PAY09 合成视觉订单',type:'physical',environment:'sandbox',status:'published',currency:'CNY',stock:100,priceMinor:300,shippingCountries:['CN'],sku:'pay09-visual-'+h.runId})).data.item;
 const place=async()=>(await api(user,'commerce/orders',{requestId:uuid(),environment:'sandbox',items:[{skuId:product.skuId,quantity:1}],shippingAddress:{name:'合成收件人',country:'CN',city:'测试市',address:'测试路 9 号',postalCode:'000000'}})).data;
 const own=order=>'commerce/orders/'+order.id+'/payment-recovery';
 const page=(await h.browserContext(await user.storageState())).page;

 await check('四语真实查询待确认与确认结果，日夜360和1280全控件可达',async()=>{
  for(const lang of ['zh','zh-Hant','en','bo']){
   const order=await place();await fixture({action:'configure',orderId:order.id,mode:'pending'});
   await page.setViewportSize({width:360,height:850});await page.goto(h.base+'/experience?page=commerceOrders&lang='+lang+'&mode=day');
   await page.locator('[data-commerce-action=environment][data-environment=sandbox]').click();await page.locator('.co-navigation [data-to=commerceOrders]').click();await page.locator('[data-commerce-action=order][data-id="'+order.id+'"]').click();
   const panel=page.locator('#payment-recovery-panel');await panel.locator('[data-recovery-action=query]:enabled').waitFor();
   await Promise.all([page.waitForResponse(r=>r.url().endsWith('/'+order.id+'/payment-recovery')&&r.request().method()==='POST'),panel.locator('[data-recovery-action=query]').click()]);
   await page.waitForFunction(()=>document.querySelector('[data-recovery-status]')?.textContent.trim()===recoveryStatus('retry'));
   const result=(await api(user,own(order))).data;assert.equal(result.order.paymentStatus,'unpaid');
   for(const width of [360,1280])for(const mode of ['day','night']){
    await page.setViewportSize({width,height:850});await page.evaluate(mode=>{state.mode=mode;render(false);},mode);await panel.waitFor();
    assert(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth+1),lang+' panel retains full width');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await panel.locator('[data-recovery-action=refresh]').click();await panel.locator('[data-recovery-action=refresh]:enabled').waitFor();
    await panel.evaluate(el=>el.scrollIntoView({block:'start'}));await capture(page,lang+'-'+width+'-'+mode+'-待确认');
   }
   await fixture({action:'configure',orderId:order.id,mode:'paid'});await control({action:'due',jobId:result.job.id});
   await Promise.all([page.waitForResponse(r=>r.url().endsWith('/'+order.id+'/payment-recovery')&&r.request().method()==='POST'),panel.locator('[data-recovery-action=query]').click()]);
   await page.waitForFunction(()=>document.querySelector('[data-recovery-status]')?.textContent.trim()===recoveryStatus('confirmed'));
   await page.setViewportSize({width:360,height:850});await panel.evaluate(el=>el.scrollIntoView({block:'start'}));await capture(page,lang+'-360-已确认');
  }
 });

 await check('离页返回回查真实任务，浮层计时会话及累计时间不丢',async()=>{
  const before=await page.evaluate(()=>({time:tbSummary().totalMs,session:timeBank.active?.id||timeBank.runId||null}));
  await page.locator('.ew-page-back').click();await page.locator('[data-commerce-action=order]').first().click();
  await page.locator('#payment-recovery-panel [data-recovery-action=refresh]').click();await page.locator('#payment-recovery-panel [data-recovery-action=refresh]:enabled').waitFor();
  const after=await page.evaluate(()=>({time:tbSummary().totalMs,session:timeBank.active?.id||timeBank.runId||null}));assert(after.time>=before.time);assert.equal(after.session,before.session);
 });

 await check('后台360和1280原生刷新查看横滑，待重试记录和处理轨迹完整可读',async()=>{
  const order=await place();await fixture({action:'configure',orderId:order.id,mode:'pending'});const result=(await api(user,own(order),{requestId:uuid()})).data;
  const staff=(await h.browserContext(await admin.storageState())).page;await staff.goto(h.base+'/admin');await staff.locator('[data-nav=commerce]').first().click();
  const panel=staff.locator('#payment-recovery-admin');await panel.locator('[data-recovery-action=load]').click();await panel.locator('[data-recovery-action=view][data-id="'+result.job.id+'"]').waitFor();
  for(const width of [360,1280]){
   await staff.setViewportSize({width,height:850});await panel.evaluate(el=>el.scrollIntoView({block:'start'}));await capture(staff,width+'-后台任务列表');
   const wrap=panel.locator('.table-wrap').first();await wrap.hover();await staff.mouse.wheel(800,0);await staff.waitForTimeout(100);const m=await wrap.evaluate(el=>({client:el.clientWidth,scroll:el.scrollWidth,left:el.scrollLeft}));if(m.scroll>m.client+1)assert(m.left>0);
   await panel.locator('[data-recovery-action=view][data-id="'+result.job.id+'"]').click();const detail=staff.locator('#recovery-job-detail');await detail.waitFor();await detail.evaluate(el=>el.scrollIntoView({block:'start'}));await capture(staff,width+'-后台详情与记录');assert(await staff.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  }
  await fixture({action:'configure',orderId:order.id,mode:'paid'});
  await Promise.all([staff.waitForResponse(r=>r.url().endsWith('/'+result.job.id+'/retry')),panel.locator('[data-recovery-action=retry][data-id="'+result.job.id+'"]').click()]);
  await panel.locator('[data-recovery-action=process]:enabled').waitFor();
  await Promise.all([staff.waitForResponse(r=>r.url().endsWith('/api/admin/payment-recovery/process')),panel.locator('[data-recovery-action=process]').click()]);
  await staff.locator('#recovery-job-detail h3').filter({hasText:'已确认付款'}).waitFor();await staff.locator('#recovery-job-detail').evaluate(el=>el.scrollIntoView({block:'start'}));await capture(staff,'后台-重新排队与确认');
  assert.equal((await api(user,own(order))).data.order.paymentStatus,'paid');
 });

 await check('补充视觉同一最终源码与构建，凭据未进入报告',async()=>{assert.deepEqual(identity(),sourceIdentity);for(const value of [token,process.env.EW_PAYMENT_QUERY_QA_SECRET,process.env.EW_PAYMENT_CALLBACK_QA_SECRET])assert(!JSON.stringify(h.report).includes(value));});
}
run().then(()=>h.finish(),error=>h.finish(error));
