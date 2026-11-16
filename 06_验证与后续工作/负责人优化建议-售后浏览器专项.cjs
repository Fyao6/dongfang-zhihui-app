'use strict';
// Actual full APP/admin UI checks, run only by the fresh owned two-backend runner after integration/build.
const assert=require('node:assert/strict');
module.exports=async function(h){
 const {api,check,register,admin}=h,key=x=>'as_ui_'+x+'_'+h.runId;
 let browser,context,page,adminBrowser,adminContext,adminPage,user,uiAdmin,order,caseId,lateCase,other;
 const ready=async()=>page.waitForFunction(()=>px.loaded&&!pxBootstrapPending&&typeof AfterSalesUI?.install==='function');
 const go=async p=>page.evaluate(p=>navigate(p),p);
 const details=async id=>{await page.evaluate(id=>AfterSalesUI.openCase(id),id);await page.locator('[data-af-detail="'+id+'"]').waitFor();};
 async function timerSafeRefresh(view){
  const initialCollapsed=await page.evaluate(()=>timeBank.collapsed);
  const timerState=()=>page.evaluate(()=>({stable:{accountId:timeBank.accountId,zone:timeBank.zone,visible:timeBank.visible,collapsed:timeBank.collapsed,dock:timeBank.dock,
   position:{...timeBank.position},runs:timeBank.runs.map(r=>({id:r.id,start:r.start,end:r.end})),running:timeBank.runs.some(r=>r.end===null)},totalMs:tbSummary().totalMs}));
  const measure=()=>page.evaluate(()=>{
   const button=document.querySelector('[data-af-detail] [data-af-action=refresh]'),bar=document.getElementById('tb-float'),app=document.getElementById('app');
   if(!button||!bar||bar.hidden||!app)throw Error('Actual refresh/timer/app is missing');
   const b=button.getBoundingClientRect(),t=bar.getBoundingClientRect(),a=app.getBoundingClientRect(),rect=r=>({left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height});
   const fullyVisible=b.top>=Math.max(0,a.top)&&b.bottom<=Math.min(innerHeight,a.bottom)&&b.left>=0&&b.right<=innerWidth;
   const noOverlap=!(b.left<t.right&&b.right>t.left&&b.top<t.bottom&&b.bottom>t.top);
   const points=[[b.left+4,b.top+4],[b.right-4,b.top+4],[b.left+4,b.bottom-4],[b.right-4,b.bottom-4],[(b.left+b.right)/2,(b.top+b.bottom)/2]];
   const allHit=points.every(([x,y])=>{const el=document.elementFromPoint(x,y);return !!el&&(el===button||button.contains(el));});
   return {button:rect(b),timer:rect(t),app:rect(a),fullyVisible,noOverlap,allHit,collapsed:timeBank.collapsed};
  });
  for(const collapsed of [initialCollapsed,!initialCollapsed]){
   await page.locator('#tb-float').waitFor({state:'visible'});
   if(await page.evaluate(()=>timeBank.collapsed)!==collapsed){await page.locator('#tb-float .timebar-open').press('Enter');await page.waitForFunction(v=>timeBank.collapsed===v,collapsed);}
   // Existing keyboard docking/movement only. Never hide/pause the timer or replace its clock/ledger.
   await page.locator('#tb-float .timebar-open').press('ArrowRight');await page.locator('#tb-float .timebar-open').press('Shift+ArrowDown');
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>resolve())));
   const before=await timerState();assert.equal(before.stable.visible,true);assert.equal(before.stable.running,true);
   await page.evaluate(()=>{const app=document.getElementById('app');app.scrollTop=app.scrollHeight;});
   const pre=await measure();assert.equal(pre.fullyVisible,true,'Last refresh must scroll fully inside the actual app viewport');assert.equal(pre.noOverlap,true,'Timer must not cover the button');assert.equal(pre.allHit,true,'All refresh hit points must target the button');
   assert(collapsed?pre.timer.width<=80:pre.timer.width>=150,'Both actual timer shapes must be exercised');
   const response=page.waitForResponse(r=>r.request().method()==='GET'&&new URL(r.url()).pathname==='/api/after-sales/cases/'+caseId);
   await page.locator('[data-af-detail] [data-af-action=refresh]').click();const received=await response;assert.equal(received.status(),200);
   await page.waitForFunction(()=>!!document.querySelector('[data-af-detail]')&&!document.querySelector('.af-page [role=status]'));
   assert.equal(await page.locator('.af-page [role=alert]').count(),0);
   const after=await timerState(),post=await measure();assert.deepEqual(after.stable,before.stable,'Scrolling/refetching must not alter timer session, start, running or display preference state');assert(after.totalMs>=before.totalMs,'The real clock can advance, never reset for a screenshot');
   assert.equal(post.fullyVisible,true);assert.equal(post.noOverlap,true);assert.equal(post.allHit,true);
   h.recordTimer({...view,shape:collapsed?'compact':'bar',position:'bottom-right via existing keyboard controls',pre,post,refreshResponseStatus:received.status(),
    timerStateUnchanged:true,running:true,stableBefore:before.stable,stableAfter:after.stable,totalMsBefore:before.totalMs,totalMsAfter:after.totalMs});
  }
  if(await page.evaluate(()=>timeBank.collapsed)!==initialCollapsed){await page.locator('#tb-float .timebar-open').press('Enter');await page.waitForFunction(v=>timeBank.collapsed===v,initialCollapsed);}
 }
 async function hold(p,pathname,method,work){
  let enteredResolve,releaseResolve,doneResolve,taken=false,error;
  const entered=new Promise(r=>enteredResolve=r),gate=new Promise(r=>releaseResolve=r),done=new Promise(r=>doneResolve=r);
  const matcher=url=>url.pathname===pathname;
  const handler=async route=>{
   if(taken||route.request().method()!==method)return route.continue();taken=true;
   try{const response=await route.fetch();enteredResolve();await gate;await route.fulfill({response});}
   catch(e){if(!/already handled|aborted|Target.*closed|context.*closed/i.test(e.message))error=e;enteredResolve();}
   finally{doneResolve();}
  };
  await p.route(matcher,handler);
  let timer;
  try{await work({entered:()=>Promise.race([entered,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Owned held response did not arrive')),10000);})]),release:async()=>{releaseResolve();if(taken)await done;}});}
  finally{clearTimeout(timer);releaseResolve();if(taken)await done;await p.unroute(matcher,handler);if(error)throw error;}
 }
 await check('实际APP统一订单售后入口：按项申请、草稿保留、提交后本人进度可查',async()=>{
  user=await register('uiBuyer');other=await register('uiOther');uiAdmin=await register('uiAdmin');
  await api(admin,'admin/users/'+uiAdmin.credential.id,{role:'admin'},'PATCH');
  order=await h.helpers.newOrder(user.c,'ui-order',2);order=await h.helpers.pay(user.c,order,'ui-order');order=await h.helpers.shipOrder(order,'ui-order');
  browser=await h.browserContext(await user.c.storageState());({context,page}=browser);
  await page.goto(h.base+'/experience');await ready();await go('commerceShop');
  await page.locator('[data-commerce-action=environment]').click();await page.waitForFunction(()=>coState().environment==='sandbox'&&coState().loaded);
  await go('commerceOrders');await page.locator('[data-commerce-action=order][data-id="'+order.id+'"]').click();
  await page.locator('[data-commerce-action=support]').click();await page.locator('[data-af-form=request]').waitFor();
  await page.locator('[name=type]').selectOption('return');await page.locator('[name=item]').check();
  await page.locator('[name="quantity:'+order.items[0].id+'"]').fill('1');await page.locator('[name=reason]').fill('实际浏览器合成退货理由');
  await page.evaluate(()=>{state.lang='zh-Hant';render(false);});assert.equal(await page.locator('[name=reason]').inputValue(),'实际浏览器合成退货理由');
  await page.locator('[data-af-form=request] button').click();await page.locator('[data-af-detail]').waitFor();
  caseId=await page.locator('[data-af-detail]').getAttribute('data-af-detail');
  const c=await api(user.c,'after-sales/cases/'+caseId);assert.equal(c.status,'submitted');assert.equal(c.items[0].quantity,1);
  assert.equal((await api(user.c,'commerce/orders/'+order.id)).paymentStatus,'paid');await h.capture(page,'实际逐项申请与进度');
 });
 assert(caseId,'Actual UI case required before dependent UI scenarios');
 await check('实际后台导航/受理表：管理员明确受理与理由，不代表退款',async()=>{
  adminBrowser=await h.browserContext(await uiAdmin.c.storageState());adminContext=adminBrowser.context;adminPage=adminBrowser.page;
  await adminPage.goto(h.base+'/admin');await adminPage.locator('[data-nav=afterSales]').waitFor();
  await adminPage.locator('[data-nav=afterSales]').click();await adminPage.evaluate(id=>AfterSalesAdmin.openCase(id),caseId);
  await adminPage.locator('[data-af-admin-form=decision]').waitFor();await adminPage.locator('[name=decision]').selectOption('accept');
  await adminPage.locator('[name=reason]').fill('实际后台合成受理，等待退货');await adminPage.locator('[data-af-admin-form=decision] button').click();
  await adminPage.waitForFunction(()=>!document.querySelector('[data-af-admin-form=decision]'));
  const c=await api(user.c,'after-sales/cases/'+caseId);assert.equal(c.status,'accepted');assert.equal(c.money.actualFundsMoved,false);assert.equal(c.money.caseRefundConfirmed,false);
 });
 await check('实际本人物流→后台实收0入库表单；原资金不变且库存事件为0',async()=>{
  await details(caseId);await page.locator('[data-af-form=shipping]').waitFor();
  await page.locator('[name=carrier]').fill('实际UI合成承运商');await page.locator('[name=trackingNumber]').fill(key('return'));
  await page.evaluate(()=>{state.mode='day';state.lang='zh';render(false);});assert.equal(await page.locator('[name=trackingNumber]').inputValue(),key('return'));
  await page.locator('[data-af-form=shipping] button').click();await page.waitForFunction(tracking=>document.querySelector('[data-af-detail]')?.textContent.includes(tracking),key('return'));
  let c=await api(user.c,'after-sales/cases/'+caseId);assert.equal(c.status,'returning');assert.equal(c.shipments[0].carrierVerified,false);
  await adminPage.evaluate(()=>load('afterSales'));await adminPage.locator('[data-af-admin-form=inspect]').waitFor();
  const lineId=c.items[0].id;assert.equal(await adminPage.locator('[name="restock:'+lineId+'"]').inputValue(),'0');
  await adminPage.locator('[name=receiptReference]').fill(key('receipt'));await adminPage.locator('[name="received:'+lineId+'"]').fill('1');
  await adminPage.locator('[name="condition:'+lineId+'"]').fill('合成损坏，不可重新出售');await adminPage.locator('[name=note]').fill('实收一件，明确入库零件');
  await adminPage.locator('[data-af-admin-form=inspect] button').click();await adminPage.waitForFunction(()=>document.querySelector('[data-af-admin-detail]')?.textContent.includes('已完成收货验收'));
  c=await api(user.c,'after-sales/cases/'+caseId);assert.equal(c.status,'received');assert.equal(c.items[0].restockedQuantity,0);
  const o=await api(user.c,'commerce/orders/'+order.id);assert.equal(o.paymentStatus,'paid');assert.equal(o.refundedMinor,0);assert.equal(o.inventoryEvents.filter(x=>x.reason==='after_sales_received_no_restock').at(-1).quantityDelta,0);
  await h.capture(adminPage,'实际后台验收零入库');
 });
 await check('实际环境切换：沙箱旧GET晚到不进入关闭的正式视图',async()=>{
  await details(caseId);
  await hold(page,'/api/after-sales/cases','GET',async barrier=>{
   await page.evaluate(()=>{void AfterSalesUI.refresh();});await barrier.entered();
   await page.locator('[data-af-action=environment]').click();await page.waitForFunction(()=>state.page==='afterSalesCenter'&&!document.querySelector('.af-page [role=status]'));
   await barrier.release();assert.equal(await page.locator('[data-af-case]').count(),0);
   assert(!(await page.locator('#app').innerText()).includes('实际浏览器合成退货理由'));
  });
 });
 await check('实际旧详情晚到不覆盖物流提交后的新状态；离开页面的提交回执不拉回',async()=>{
  let o=await h.helpers.newOrder(user.c,'ui-late-order',1);o=await h.helpers.pay(user.c,o,'ui-late-order');o=await h.helpers.shipOrder(o,'ui-late-order');
  let c=(await h.helpers.create(user.c,o,'ui-late-case',1)).item;c=(await h.helpers.decision(c,'accept','ui-late-accept')).item;lateCase=c.id;
  await details(lateCase);await page.locator('[data-af-form=shipping]').waitFor();
  await hold(page,'/api/after-sales/cases/'+lateCase,'GET',async barrier=>{
   await page.evaluate(()=>{void AfterSalesUI.refresh();});await barrier.entered();
   await page.locator('[name=carrier]').fill('合成新承运商');await page.locator('[name=trackingNumber]').fill(key('fresh-tracking'));
   await page.locator('[data-af-form=shipping] button').click();await page.waitForFunction(text=>document.querySelector('#app').textContent.includes(text),key('fresh-tracking'));
   await barrier.release();assert((await page.locator('#app').innerText()).includes(key('fresh-tracking')));
  });
  await hold(page,'/api/after-sales/cases/'+lateCase+'/return-shipping','POST',async barrier=>{
   await page.locator('[name=carrier]').fill('合成晚到承运商');await page.locator('[name=trackingNumber]').fill(key('late-tracking'));
   await page.locator('[data-af-form=shipping] button').click();await barrier.entered();await go('community');
   await barrier.release();assert.equal(await page.evaluate(()=>state.page),'community');
  });
  await go('afterSalesCenter');await page.locator('[data-af-case="'+lateCase+'"]').waitFor();
  assert.equal((await api(user.c,'after-sales/cases/'+lateCase)).shipments.length,2);
 });
 await check('实际四语375/430日夜64视图：真实藏文字体、表单/进度无横溢',async()=>{
  const views=[];
  for(const screen of ['closed','center','request','detail']){
   if(screen==='closed'){await details(caseId);await page.locator('[data-af-action=environment]').click();await page.waitForFunction(()=>!document.querySelector('.af-page [role=status]'));}
   if(screen==='center'){await page.locator('[data-af-action=environment]').click();await page.locator('[data-af-case="'+caseId+'"]').waitFor();}
   if(screen==='request'){await page.evaluate(id=>AfterSalesUI.openOrder(id),order.id);await page.locator('[data-af-form=request]').waitFor();}
   if(screen==='detail')await details(caseId);
   for(const width of [375,430])for(const mode of ['day','night'])for(const lang of ['zh','zh-Hant','en','bo']){
    await page.setViewportSize({width,height:844});
    const font=await page.evaluate(async({mode,lang})=>{if(typeof ewChangeLanguage==='function')ewChangeLanguage(lang);else state.lang=lang;state.mode=mode;render(false);
     if(lang==='bo'){const faces=await document.fonts.load('16px "EW Tibetan"','བོད་ཡིག');await document.fonts.ready;if(!faces.length||faces.some(f=>f.status!=='loaded'))throw Error('Real Tibetan font missing');const family=getComputedStyle(document.querySelector('.af-page')).fontFamily;if(!family.includes('EW Tibetan'))throw Error('Tibetan face not selected');return {faceCount:faces.length,statuses:faces.map(f=>f.status),fontFamily:family};}return null;}, {mode,lang});
    const view={screen,width,mode,lang,noOverflow:!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))};assert.equal(view.noOverflow,true,[screen,width,mode,lang].join(' '));views.push(view);h.recordView(view);if(font)h.recordFont({screen,width,mode,lang,...font});
    if(screen==='detail'){
     const labels=await page.locator('[data-af-event-label]').allTextContents();assert.equal(labels.length,4);
     assert(labels.every(label=>!/(^|\b)(submit|accept|reject|return-shipping|inspect)(\b|$)/i.test(label)),'History must show localized action names, not raw API keys');
     h.recordTimeline({width,mode,lang,labels,rawKeysExposed:false});
     await timerSafeRefresh({width,mode,lang});
    }
    if(screen==='detail'&&width===375&&mode==='night'){await page.waitForTimeout(700);await h.capture(page,'实际四语详情-'+lang);}
   }
  }
  assert.equal(views.length,64);
 });
 await check('实际导出只本人申请/收货，不含全站配置与他人申请',async()=>{
  const own=(await api(user.c,'privacy/export')).serverData,foreign=(await api(other.c,'privacy/export')).serverData;
  assert(own.afterSalesCases.some(c=>c.id===caseId));assert(own.afterSalesInspections.length>0);assert.equal(foreign.afterSalesCases.some(c=>c.id===caseId),false);
  assert.equal(Object.hasOwn(own,'afterSalesConfig'),false);assert.equal(Object.hasOwn(own,'afterSalesSettings'),false);
 });
 await check('实际cookie换账号/Bootstrap后旧本人申请GET晚到不跨账号显示',async()=>{
  await details(caseId);
  await hold(page,'/api/after-sales/cases','GET',async barrier=>{
   await page.evaluate(()=>{void AfterSalesUI.refresh();});await barrier.entered();
   assert.equal((await context.request.post(h.base+'/api/auth/logout',{data:{}})).status(),200);
   assert.equal((await context.request.post(h.base+'/api/auth/login',{data:other.credential})).status(),200);
   await page.evaluate(async()=>{await pxBootstrap(true);navigate('afterSalesCenter');});
   await page.waitForFunction(id=>px.user?.id===id&&psToken().scope===id,other.credential.id);
   await barrier.release();await page.waitForFunction(()=>!document.querySelector('.af-page [role=status]'));
   assert.equal(await page.locator('[data-af-case]').count(),0);assert(!(await page.locator('#app').innerText()).includes('实际浏览器合成退货理由'));
   await h.capture(page,'实际换账号旧读取不泄漏');
  });
 });
 await check('实际后台账号降级为运营：售后导航消失，强读403并清掉旧详情',async()=>{
  await api(admin,'admin/users/'+uiAdmin.credential.id,{role:'operator'},'PATCH');
  await adminPage.evaluate(()=>authBootstrap());await adminPage.waitForFunction(()=>state.user?.role==='operator');
  assert.equal(await adminPage.locator('[data-nav=afterSales]').count(),0);
  await adminPage.evaluate(()=>load('afterSales'));await adminPage.locator('[role=alert]').filter({hasText:/权限|管理员/}).waitFor();
  assert.equal(await adminPage.locator('[data-af-admin-detail]').count(),0);
  await api(uiAdmin.c,'admin/after-sales?environment=sandbox',undefined,'GET',403);
 });
 await context?.close();await adminContext?.close();
};

