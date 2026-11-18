// Derived compatibility: original business assertions retained, native stale-read payment race strengthened.
// Frozen source SHA256 9864bc52b10c1dae6877480b2bfd0d720ab22514b870444c3b6d9260e846b2e6
// Real browser membership flows. Uses independently registered fixture owners.
const assert=require('node:assert/strict');
module.exports=async function browserChecks(h,a,helpers){
 const {api,check}=h,{createPlan,status}=helpers;
 let user,browser,context,page,plan,orderId,subscriptionId,periodEnd,adminBrowser,uiAdmin;
 const ready=async()=>page.waitForFunction(()=>px.loaded&&!pxBootstrapPending&&typeof mlState==='function');
 const loaded=async()=>page.waitForFunction(()=>mlState().loaded&&!mlState().loading&&!mlState().busy);
 const go=async name=>{await page.evaluate(name=>navigate(name),name);await loaded();};
 const sandbox=async()=>{if(await page.evaluate(()=>mlState().environment)!=='sandbox'){await page.locator('[data-ml-action=environment]').click();await loaded();}assert.equal(await page.evaluate(()=>mlState().environment),'sandbox');};
 async function hold(pattern,work){
  let releaseGate,notify,finish,used=false,handlerError;const gate=new Promise(r=>releaseGate=r),seen=new Promise(r=>notify=r),delivered=new Promise(r=>finish=r);
  const release=async()=>{releaseGate();if(used)await delivered;};
  const handler=async route=>{if(used)return route.continue();used=true;try{const response=await route.fetch();notify(response);await gate;await route.fulfill({response});}catch(error){if(!/already handled|aborted|Target page.*closed/i.test(error.message))handlerError=error;}finally{finish();}};
  await page.route(pattern,handler);
  try{await work({seen:Promise.race([seen,new Promise((_,reject)=>{const t=setTimeout(()=>reject(Error('Stale read was not captured')),8000);t.unref?.();})]),release});}
  finally{await release();await page.unroute(pattern,handler);if(handlerError)throw handlerError;}
 }
 await check('会员真实页面：三项管理入口与正式服务未开放说明',async()=>{
  user=await h.register('ui');({plan}=await createPlan('browser',{title:'浏览器测试会员 '+h.runId}));
  browser=await h.browserContext(await user.c.storageState());({context,page}=browser);
  await page.goto(h.base+'/experience');await ready();await go('memberCenter');
  for(const name of ['membershipCancel','membershipRefund','membershipRestore'])assert.equal(await page.locator('[data-to="'+name+'"]').count(),1);
  assert((await page.locator('#app').innerText()).includes('正式方案'));
  await sandbox();await page.locator('[data-ml-action=plan][data-id="'+plan.id+'"]').waitFor();
 });
 await check('会员真实下单：先展示有限周期与条款，统一订单保留原成交版本后支付',async()=>{
  await page.locator('[data-ml-action=plan][data-id="'+plan.id+'"]').click();await loaded();
  assert((await page.locator('#app').innerText()).includes(plan.serviceTerms));
  assert((await page.locator('#app').innerText()).includes(plan.refundPolicy));
  const created=page.waitForResponse(r=>r.url().endsWith('/api/commerce/orders')&&r.request().method()==='POST');
  await page.locator('[data-ml-action=order]').click();assert.equal((await created).status(),200);
  await page.waitForFunction(()=>state.page==='commerceOrder'&&coState().order?.id);
  orderId=await page.evaluate(()=>coState().order.id);
  await page.waitForFunction(id=>mlState().orderTerms[id]?.items?.length>0,orderId);
  const terms=page.locator('.ml-order-terms');assert((await terms.innerText()).includes(plan.serviceTerms));
  await page.waitForFunction(()=>!coState().loading&&!coState().busy);
  await hold('**/api/commerce/orders/'+orderId+'/payment-recovery',async({seen,release})=>{
   const oldRead=page.evaluate(()=>coLoad(true));const withheld=await seen;assert.equal(withheld.status(),200);assert.equal((await withheld.json()).order.paymentStatus,'unpaid');
   const paid=page.waitForResponse(r=>r.url().includes('/commerce/orders/'+orderId+'/sandbox-pay'));
   await page.locator('[data-commerce-action=pay]').click();const response=await paid;assert.equal(response.status(),200);assert.equal((await response.json()).paymentStatus,'paid');
   await page.waitForFunction(()=>coState().order?.paymentStatus==='paid'&&!coState().loading&&!coState().busy);
   await release();await oldRead;
   assert.equal(await page.evaluate(()=>coState().order?.paymentStatus),'paid');assert.equal(await page.locator('[data-commerce-action=pay]').count(),0);
   h.report.nativePaymentStaleRead={held:'actual successful unpaid GET response, released after native payment and fresh paid view',paymentStatusBeforeRelease:'paid',paymentStatusAfterRelease:'paid',newPaymentFactsMocked:false};
  });
  const state=await status(user.c),sub=state.items.find(s=>s.periods.some(p=>p.orderId===orderId));assert(sub);
  subscriptionId=sub.id;periodEnd=sub.periodEnd;assert.equal(sub.status,'active');assert.equal(sub.grantsProductionAccess,false);
  await h.capture(page,'成交条款与已付测试订单');
 });
 await check('会员中心本人原成交披露及注销前续期核对，不冒充第三方已取消',async()=>{
  await go('memberCenter');await sandbox();await go('memberCenter');
  const details=page.locator('[data-ml-subscription="'+subscriptionId+'"] .ml-current-plan');await details.locator('summary').click();
  assert((await details.innerText()).includes(plan.serviceTerms));assert((await details.innerText()).includes(plan.refundPolicy));
  assert((await details.innerText()).includes('未启用试用'));assert((await details.innerText()).includes('仅测试渠道'));
  assert.equal(await details.locator('.ml-facts dd').count(),4);
  await page.evaluate(()=>privacyRequestSheet('close-account'));
  await page.locator('[data-ml-renewal-state=ready]').waitFor();
  const reminder=page.locator('.ml-closure-reminder');assert((await reminder.innerText()).includes(plan.title));
  assert((await reminder.innerText()).includes(await page.evaluate(value=>mlDate(value),periodEnd)),'Original next renewal date is disclosed');
  assert((await reminder.innerText()).includes('无法确认其续费状态'));
  assert.equal(await reminder.locator('a[href="https://support.apple.com/en-us/118428"]').count(),1);
  assert.equal(await reminder.locator('a[href^="https://support.google.com/googleplay/"]').count(),1);
  await h.capture(page,'注销前真实测试续期提醒');await page.evaluate(()=>closeSheet());
  await details.locator('summary').click();
 });
 await check('会员及商城环境切换竞态：旧沙箱读取未返回时仍完成正式目录加载',async()=>{
  await go('memberCenter');await sandbox();
  await hold('**/api/membership/catalog?environment=sandbox',async({seen,release})=>{
   await page.evaluate(()=>{void mlLoad(true);});await seen;
   await page.locator('[data-ml-action=environment]').click();
   await page.waitForFunction(()=>mlState().environment==='production'&&mlState().loaded&&!mlState().loading&&mlState().catalog?.environment==='production');
   await release();await page.waitForTimeout(80);
   assert.equal(await page.evaluate(()=>mlState().catalog.environment),'production');
  });
  await sandbox();await go('memberCenter');
  await page.evaluate(()=>navigate('commerceShop'));await page.waitForFunction(()=>coState().loaded&&!coState().loading&&!coState().busy);
  if(await page.evaluate(()=>coState().environment)!=='sandbox'){await page.locator('[data-commerce-action=environment][data-environment=sandbox]').click();await page.waitForFunction(()=>coState().environment==='sandbox'&&coState().loaded&&!coState().loading);}
  await hold('**/api/commerce/catalog?environment=sandbox',async({seen,release})=>{
   const oldRead=page.evaluate(()=>coLoad(true));const withheld=await seen;assert.equal(withheld.status(),200);assert((await withheld.json()).items.length>0);
   const fresh=page.waitForResponse(r=>r.url().endsWith('/api/commerce/catalog?environment=production'));await page.locator('[data-commerce-action=environment][data-environment=production]').click();assert.equal((await fresh).status(),200);
   await page.waitForFunction(()=>coState().environment==='production'&&coState().loaded&&!coState().loading&&!coState().busy&&coState().catalog.length===0);
   await release();await oldRead;assert.equal(await page.evaluate(()=>coState().environment),'production');assert.equal(await page.evaluate(()=>coState().catalog.length),0);
   h.report.nativeCommerceEnvironmentRace={held:'actual sandbox catalog GET',newEnvironmentLoadedBeforeRelease:'production',oldReadFinishedAfterRelease:true,environmentAfterOldRead:'production'};
  });
  await page.locator('[data-commerce-action=environment][data-environment=sandbox]').click();await page.waitForFunction(()=>coState().environment==='sandbox'&&coState().loaded&&!coState().loading);await go('memberCenter');
 });
 await check('会员取消竞态：变更前延迟状态不能覆盖成功后的取消结果，已付期保留',async()=>{
  await hold('**/api/membership/status',async({seen,release})=>{
   await page.evaluate(()=>{void mlLoad(true);});await seen;
   await page.locator('[data-ml-action=cancel][data-id="'+subscriptionId+'"]').click();
   const changed=page.waitForResponse(r=>r.url().includes('/subscriptions/'+subscriptionId+'/cancel-renewal'));
   await page.locator('#ml-action-form button[type=submit],#ml-action-form button').first().click();assert.equal((await changed).status(),200);
   await page.waitForFunction(id=>mlState().status?.items.find(x=>x.id===id)?.autoRenew===false&&!mlState().busy,subscriptionId);
   await release();await page.waitForTimeout(80);
   const sub=await page.evaluate(id=>mlState().status.items.find(x=>x.id===id),subscriptionId);
   assert.equal(sub.autoRenew,false);assert.equal(sub.status,'cancelled_active');assert.equal(sub.periodEnd,periodEnd);
  });
  await h.capture(page,'取消后保留已付周期');
 });
 await check('会员退款入口提交待处理统一售后申请，不冒充退款成功',async()=>{
  await page.locator('[data-ml-action=refund][data-id="'+subscriptionId+'"]').click();
  await page.locator('#ml-action-form [name=reason]').fill('隔离浏览器申请退款，等待人工处理。');
  const changed=page.waitForResponse(r=>r.url().includes('/subscriptions/'+subscriptionId+'/refund-request'));
  await page.locator('#ml-action-form button').first().click();assert.equal((await changed).status(),200);await loaded();
  const o=(await api(user.c,'commerce/orders/'+orderId)).data;
  assert.equal(o.paymentStatus,'paid');assert.equal(o.refundedMinor,0);assert.equal(o.aftersaleRequests.length,1);assert.equal(o.aftersaleRequests[0].status,'pending');
 });
 await check('会员恢复入口核对本人原订单，刷新后不重置时间或重新打开续期',async()=>{
  await go('membershipRestore');await page.locator('#ml-restore-form [name=orderId]').fill(orderId);
  const restored=page.waitForResponse(r=>r.url().endsWith('/api/membership/restore'));
  await page.locator('#ml-restore-form button').click();assert.equal((await restored).status(),200);await loaded();
  const s=(await status(user.c)).items.find(x=>x.id===subscriptionId);
  assert.equal(s.periodEnd,periodEnd);assert.equal(s.autoRenew,false);assert.equal(s.periods.length,1);
  await page.reload();await ready();await go('memberCenter');await sandbox();await go('memberCenter');
  await page.locator('[data-ml-subscription="'+subscriptionId+'"]').waitFor();
 });
 await check('会员四语375/430窄屏及日夜均可使用，无横向溢出',async()=>{
  const observations=[];
  for(const lang of ['zh','zh-Hant','en','bo'])for(const width of [375,430]){
   await page.setViewportSize({width,height:844});
   await page.evaluate(({lang,width})=>{state.lang=lang;state.mode=width===375?'day':'night';render(false);},{lang,width});
   await page.locator('[data-ml-subscription="'+subscriptionId+'"]').waitFor();
   const bounds=await page.locator('.ml-subscription,.ml-management,.ml-mode').evaluateAll(es=>es.filter(e=>e.getClientRects().length).map(e=>({left:e.getBoundingClientRect().left,right:e.getBoundingClientRect().right})));
   assert(bounds.length>2);assert(bounds.every(b=>b.left>=-1&&b.right<=width+1),lang+' '+width+' overflows');
   assert.equal(await page.locator('[data-to=membershipRestore]').isVisible(),true);
   observations.push({lang,width,visibleSubscriptions:await page.locator('.ml-subscription').count()});
   if(width===375)await h.capture(page,'会员中心-'+lang);
  }return observations;
 });
 await check('隐私导出包含本人订阅和原成交条款，排除其他买家的会员资料',async()=>{
  const own=(await api(user.c,'privacy/export')).data.serverData,other=(await api(a.other,'privacy/export')).data.serverData;
  assert(own.membershipSubscriptions.some(x=>x.id===subscriptionId));
  assert(own.membershipOrderTerms.some(x=>x.order_id===orderId));
  assert(!other.membershipSubscriptions.some(x=>x.id===subscriptionId));
  assert(!other.membershipOrderTerms.some(x=>x.order_id===orderId));
  assert.equal(own.membershipPlans,undefined);assert.equal(own.membershipChannelMappings,undefined);
 });
 await check('会员切换真实登录账号：旧账号延迟状态与成交条款不混入新账号',async()=>{
  await hold('**/api/membership/status',async({seen,release})=>{
   await page.evaluate(()=>{void mlLoad(true);});await seen;
   const logout=await context.request.post(h.base+'/api/auth/logout',{data:{}});assert.equal(logout.status(),200);
   const login=await context.request.post(h.base+'/api/auth/login',{data:a.credentials.b});assert.equal(login.status(),200);
   await page.evaluate(async()=>{await pxBootstrap(true);navigate('memberCenter');});await loaded();
   assert.equal(await page.evaluate(()=>px.user.id),a.credentials.b.id);
   await release();await page.waitForTimeout(100);
   assert.equal(await page.evaluate(()=>mlState().actor.scope),a.credentials.b.id);
   assert(!(await page.locator('#app').innerText()).includes(orderId));
   assert.equal(await page.evaluate(id=>!!mlState().orderTerms[id],orderId),false);
   assert.equal(await page.locator('[data-ml-subscription="'+subscriptionId+'"]').count(),0);
  });
 });
 await check('会员后台真实方案版本与渠道草稿表单，普通用户不能访问',async()=>{
  uiAdmin=await h.register('uiadmin');await api(a.admin,'admin/users/'+uiAdmin.credential.id,{role:'admin'},'PATCH');
  adminBrowser=await h.browserContext(await uiAdmin.c.storageState());const p=adminBrowser.page;
  await p.setViewportSize({width:1280,height:900});await p.goto(h.base+'/admin');
  await p.locator('[data-nav=memberSubscriptions]').click();await p.locator('#ml-admin-plan').waitFor();
  await p.locator('[data-ml-admin=edit][data-id="'+plan.id+'"]').click();
  const editor=p.locator('#ml-admin-plan [name=plan]'),value=JSON.parse(await editor.inputValue());value.description='真实后台版本编辑 '+h.runId;
  await editor.fill(JSON.stringify(value,null,2));
  const save=p.waitForResponse(r=>r.url().endsWith('/api/admin/membership/plans')&&r.request().method()==='POST');
  await p.locator('#ml-admin-plan button').click();assert.equal((await save).status(),200);
  await p.waitForFunction(()=>!mlAdmin.busy&&mlAdmin.data.plans.some(x=>x.description.startsWith('真实后台版本编辑')));
  const mapping=p.locator('#ml-admin-mapping');
  await mapping.locator('[name=planId]').selectOption(plan.id);await mapping.locator('[name=channel]').selectOption('apple');
  await mapping.locator('[name=externalProductId]').fill('unverified.qa.'+h.runId);
  const saved=p.waitForResponse(r=>r.url().endsWith('/api/admin/membership/channel-mappings')&&r.request().method()==='POST');
  await mapping.locator('button').click();assert.equal((await saved).status(),200);
  await p.waitForFunction(()=>!mlAdmin.busy&&mlAdmin.data.channelMappings.some(x=>x.channel==='apple'&&x.status==='draft'));
  await h.capture(p,'后台真实方案与渠道草稿');
  await api(a.other,'admin/membership',undefined,'GET',403);
  return {realChannelVerified:false,productionEnabled:false};
 });
};

