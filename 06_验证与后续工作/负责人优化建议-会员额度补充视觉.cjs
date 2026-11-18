'use strict';
const assert=require('node:assert/strict');
const {makeHarness}=require('./负责人优化建议-会员额度测试工具.cjs');
const h=makeHarness(),{api,check}=h;
async function run(){
 await h.start();const a=await h.seed(),f=require('./负责人优化建议-会员额度用例工具.cjs')(h,a);await f.configure();await f.policy({enabled:true,confirmed:true,ruleVersion:h.key('visual_policy')});
 h.report.scope='Four native browser checks: actual claim and persisted source; four languages/day-night/360-1280, original timer drag/return, admin policy confirmation. Native viewport pixels, no image cropping or editing.';
 const active=await f.buyer('visualactive');await f.purchase(active,'visualactive',{credits:20});
 const exhausted=await f.buyer('visualexhausted');await f.purchase(exhausted,'visualexhausted',{credits:4});await f.grant(exhausted,100);await f.quota(exhausted.c,true);const body=f.payload(exhausted.c,'visual_exhaust'),job=await f.create(exhausted.c,body);await f.stream(exhausted.c,job.id,body);
 const page=(await h.browserContext(await active.c.storageState())).page;await page.setViewportSize({width:360,height:850});
 const ready=async p=>{await p.waitForFunction(()=>px.loaded&&!pxBootstrapPending&&agState().loaded&&!agState().loading&&!document.documentElement.dataset.ambientTransition);await p.evaluate(()=>document.fonts.ready);};
 await check('APP原生领取一次并刷新回读同一周期，不表示正式AI服务或收费已开放',async()=>{
  await page.goto(h.base+'/experience?page=aiGatewaySettings&lang=zh&mode=day');await ready(page);const panel=page.locator('[data-membership-quota=gateway]');assert((await panel.innerText()).includes('本期额度尚未发放'));
  await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api/membership/ai-quota/refresh'&&r.request().method()==='POST'),panel.locator('[data-membership-quota-refresh]').click()]);await page.waitForFunction(()=>document.querySelector('[data-membership-available]')?.textContent==='20');const before=await f.quota(active.c);
  await page.reload();await ready(page);assert.equal((await f.quota(active.c)).periodId,before.periodId);assert.equal(await panel.locator('[data-membership-available]').innerText(),'20');await panel.scrollIntoViewIfNeeded();await h.viewportCapture(page,'zh-360-实际领取后');
 });
 await check('可用及耗尽状态四语日夜360/1280完整可读，无横溢或缩字隐藏',async()=>{
  let combinations=0;h.report.paragraphMetrics=[];for(const person of [active,exhausted]){const p=person===active?page:(await h.browserContext(await person.c.storageState())).page;
   for(const lang of ['zh','zh-Hant','en','bo']){await p.goto(h.base+'/experience?page=aiGatewaySettings&lang='+lang+'&mode=day');await ready(p);
    for(const width of [360,1280])for(const mode of ['day','night']){
     await p.setViewportSize({width,height:850});await p.evaluate(({lang,mode})=>{state.lang=lang;state.mode=mode;render(false);},{lang,mode});await ready(p);const panel=p.locator('[data-membership-quota=gateway]');
     assert(await panel.isVisible());assert(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth+1));assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await panel.locator('.ml-facts dd').count(),5);assert.equal(await panel.locator('[data-membership-available]').innerText(),person===active?'20':'0');
     const paragraphs=[];h.report.paragraphMetrics.push({lang,width,mode,status:person===active?'available':'exhausted',paragraphs});for(const paragraph of await panel.locator('p').all()){
      assert(await paragraph.isVisible());await paragraph.scrollIntoViewIfNeeded();
      const metric=await paragraph.evaluate(el=>{
       const css=getComputedStyle(el),panel=el.closest('[data-membership-quota]'),panelCss=getComputedStyle(panel),range=document.createRange();range.selectNodeContents(el);
       const rect=el.getBoundingClientRect(),text=range.getBoundingClientRect(),nextElement=el.nextElementSibling,next=nextElement?.getBoundingClientRect(),nextCss=nextElement?getComputedStyle(nextElement):null,nextRange=document.createRange(),ancestors=[];if(nextElement)nextRange.selectNodeContents(nextElement);const nextText=nextElement?nextRange.getBoundingClientRect():null;
       for(let parent=el.parentElement;parent;parent=parent.parentElement){const c=getComputedStyle(parent),b=parent.getBoundingClientRect();if(['auto','scroll','hidden','clip'].includes(c.overflowY)&&parent.clientHeight>0)ancestors.push({tag:parent.id||parent.tagName,overflowY:c.overflowY,clientHeight:parent.clientHeight,scrollHeight:parent.scrollHeight,scrollTop:parent.scrollTop,top:b.top,bottom:b.bottom,textTop:text.top,textBottom:text.bottom,contentTextBottom:text.bottom-b.top+parent.scrollTop});}
       return {fontSize:Number.parseFloat(css.fontSize),lineHeight:css.lineHeight,marginTop:css.marginTop,marginBottom:css.marginBottom,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight,overflowY:css.overflowY,maxHeight:css.maxHeight,lineClamp:css.webkitLineClamp,panelOverflowY:panelCss.overflowY,panelMaxHeight:panelCss.maxHeight,panelLineClamp:panelCss.webkitLineClamp,box:{top:rect.top,bottom:rect.bottom,height:rect.height},textRange:{top:text.top,bottom:text.bottom,height:text.height},nextTag:nextElement?.tagName,nextTop:next?.top,nextMarginTop:nextCss?.marginTop,nextLineHeight:nextCss?.lineHeight,nextTextRange:nextText?{top:nextText.top,bottom:nextText.bottom,height:nextText.height}:null,ancestors};
      });paragraphs.push(metric);
      assert(metric.fontSize>=12,'Original readable paragraph font remains at least 12px');
      assert.equal(metric.maxHeight,'none');assert.equal(metric.panelMaxHeight,'none');assert(['none','0',''].includes(metric.lineClamp));assert(['none','0',''].includes(metric.panelLineClamp));
      assert(!['hidden','clip'].includes(metric.overflowY));assert(!['hidden','clip'].includes(metric.panelOverflowY));
      if(metric.scrollHeight>metric.clientHeight+1){assert.equal(metric.overflowY,'visible');metric.verticalOverflowExplanation='Tibetan glyph ink can exceed the line box; visible overflow remains painted, with no max-height or line clamp.';}
      if(metric.nextTop!==undefined)assert(metric.textRange.bottom<=metric.nextTop+1,'Text range does not overlap the next paragraph or control');
      for(const ancestor of metric.ancestors){if(['hidden','clip'].includes(ancestor.overflowY))assert(metric.textRange.top>=ancestor.top-2&&metric.textRange.bottom<=ancestor.bottom+2,'Native scrolling brings the complete paragraph inside clipping ancestor '+ancestor.tag);else assert(ancestor.contentTextBottom<=ancestor.scrollHeight+2,'Complete text is reachable in the real scrolling container '+ancestor.tag);}
     }
     await panel.evaluate(el=>el.scrollIntoView({block:'start'}));await h.viewportCapture(p,lang+'-'+width+'-'+mode+'-'+(person===active?'available':'exhausted'));combinations++;
    }
   }
  }return {combinations,nativeLanguageReviewPending:true};
 });
 await check('计时真实累计、整块拖动及收展返回不中断，耗尽不静默改扣手工余额',async()=>{
  await page.setViewportSize({width:360,height:850});await page.goto(h.base+'/experience?page=aiGatewaySettings&lang=zh&mode=day');await ready(page);const initial=await page.evaluate(()=>tbSummary().totalMs),timer=page.locator('#tb-float');await timer.waitFor();const expanded=await page.locator('#tb-float .timebar-open').getAttribute('aria-expanded');await page.locator('#tb-float .timebar-open').click();assert.notEqual(await page.locator('#tb-float .timebar-open').getAttribute('aria-expanded'),expanded);assert.match(await timer.locator('[data-tb-today]').innerText(),/\d+:\d{2}:\d{2}/);
  const box=await timer.boundingBox();assert(box);await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(12,Math.min(450,box.y+120),{steps:12});await page.mouse.up();await page.waitForTimeout(1200);const moved=await timer.boundingBox();assert(moved.x>=0&&moved.x+moved.width<=361);await page.evaluate(()=>navigate('memberCenter'));await page.waitForFunction(()=>!document.documentElement.dataset.ambientTransition&&mlState().loaded&&!mlState().loading);await page.locator('.ew-page-back').first().click();assert(await page.evaluate(()=>tbSummary().totalMs)>initial+700);await page.evaluate(()=>navigate('aiGatewaySettings'));await ready(page);await page.locator('[data-membership-quota=gateway] [data-membership-quota-refresh]').click();assert.equal((await f.quota(active.c)).available,20);
  const state=await f.snapshot(exhausted.credential.id);assert.equal(state.wallets[0].balance,100);assert.equal(state.wallets[0].reserved,0);await h.viewportCapture(page,'360-拖动收展返回后额度与计时');
 });
 await check('后台360/1280完整规则及原生确认保存、普通角色不可管理，秘密不在界面报告',async()=>{
  const staff=(await h.browserContext(await a.admin.storageState())).page;await staff.goto(h.base+'/admin');await staff.locator('[data-nav=aiGateway]').click();const panel=staff.locator('#membership-quota-admin'),form=panel.locator('#membership-quota-policy-form');await form.waitFor();for(const width of [360,1280]){await staff.setViewportSize({width,height:850});assert(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth+1));await panel.evaluate(el=>el.scrollIntoView({block:'start'}));await h.viewportCapture(staff,width+'-后台完整规则');await form.locator('input[name=confirm]').scrollIntoViewIfNeeded();await h.viewportCapture(staff,width+'-后台原生确认入口');}
  const before=(await api(a.admin,'admin/membership-ai-quota')).data.policy;await form.locator('input[name=confirm]').check();await Promise.all([staff.waitForResponse(r=>new URL(r.url()).pathname==='/api/admin/membership-ai-quota'&&r.request().method()==='PATCH'),form.locator('[type=submit]').click()]);assert.equal((await api(a.admin,'admin/membership-ai-quota')).data.policy.revision,before.revision+1);await api(a.user,'admin/membership-ai-quota',undefined,'GET',403);
  for(const value of [process.env.MEMBER_QUOTA_TEST_TOKEN,process.env.MEMBER_QUOTA_PROVIDER_SECRET]){assert(!JSON.stringify(h.report).includes(value));assert(!(await panel.innerText()).includes(value));}await h.viewportCapture(staff,'后台保存后正式服务仍关闭');
 });
 assert.equal(h.report.results.length,4);
}
run().then(()=>h.finish(),error=>h.finish(error));
