const {chromium}=require('C:/Users/YIT/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),assert=require('node:assert/strict'),root='C:/Users/YIT/Documents/ChatGPT/app',checks=[],errors=[];
async function check(name,fn){console.log('START '+name);await fn();checks.push(name);console.log('PASS '+name);}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 const page=await browser.newPage({viewport:{width:393,height:852},reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('file:///'+root+'/output/东方智慧-首页体验R4.html');await page.evaluate(()=>{localStorage.clear();location.reload()});await page.waitForTimeout(200);
 const go=async id=>{await page.evaluate(id=>navigate(id),id);};
 const click=async (action,extra='')=>{await page.locator('[data-action="'+action+'"]'+extra).first().click();};
 await check('Five-tab navigation preserves daily features and separates AI support from human community',async()=>{
  assert.deepEqual(await page.locator('#nav span').allTextContents(),['首页','智慧馆','服务','社群','我的']);assert.equal(await page.locator('.home-shortcuts button').count(),5);
  await page.locator('#nav [data-to=service]').click();assert.equal(await page.evaluate(()=>state.page),'service');assert.match(await page.locator('#app').innerText(),/AI客服/);assert.doesNotMatch(await page.locator('#app').innerText(),/\$|立即购买/);
  await page.screenshot({path:root+'/output/R4-AI服务预览.png'});
  await page.locator('#nav [data-to=community]').click();assert.match(await page.locator('#app').innerText(),/真人老师一对一/);await page.screenshot({path:root+'/output/R4-社群预览.png'});
  await go('home');await click('entry-messages');assert.equal(await page.evaluate(()=>state.page),'communityInbox');
 });
 await check('AI common questions, free text, unknown questions and clear-chat flow work honestly offline',async()=>{
  await go('serviceHelp');assert.equal(await page.locator('[data-action=ss-faq]').count(),6);await click('ss-faq','[data-id=courses]');assert.match(await page.locator('#ss-ai-messages').innerText(),/会员课程/);
  await page.locator('#ss-ai-input').fill('怎样联系真人老师？');await page.locator('#ss-ai-form button[type=submit]').click();assert.equal(await page.locator('#ss-ai-messages [data-to=teachers]').count(),1);
  await page.locator('#ss-ai-input').fill('完全不相关的话题XYZ');await page.locator('#ss-ai-form button[type=submit]').click();assert.match(await page.locator('#ss-ai-messages').innerText(),/超出了已配置/);
  await click('ss-ai-clear');await click('ss-ai-clear-confirm');assert.equal(await page.evaluate(()=>state.support.ai.length),0);
 });
 await check('Five basic report types use actual saved records; empty states do not invent results',async()=>{
  await go('serviceReports');assert.equal(await page.locator('[data-action=ss-report]').count(),5);assert.equal(await page.evaluate(()=>ssReports().filter(x=>x.ready).length),0);
  await click('ss-report','[data-id=body]');assert.equal(await page.evaluate(()=>state.page),'bodyAssessment');
  await page.evaluate(()=>editBody());for(const [key,value] of Object.entries({sleep:'restless',energy:'low',stress:'high',comfort:'tense'}))await page.locator('#body-'+key).selectOption(value);await click('body-save');
  await go('traits');for(const [i,key]of ['curiosity','listening','organizing','expression','initiative','reflection'].entries())await page.locator('[data-action=life4-trait-pick][data-trait='+key+'][data-value="'+i%3+'"]').click();await click('life4-trait-save');
  await page.evaluate(()=>editMind());await page.locator('#mind-mood').selectOption({index:1});await page.locator('#mind-note').fill('仅情绪报告可见的测试文字');await page.locator('#mind-next').fill('想给自己留一点安静时间');await click('mind-save');
  await page.evaluate(()=>editLife());await page.locator('#life-direction').fill('仅人生报告可见的测试文字');await click('life-save');
  await page.evaluate(()=>{state.daily.birthProfile={solarDate:'2000-8-16',timeIndex:2,gender:'女',timeConfirmed:true,timezoneBasis:'UTC+8',savedAt:new Date().toISOString()};persist();});
  assert.equal(await page.evaluate(()=>ssReports().filter(x=>x.ready).length),5);
  await go('serviceReports');await click('ss-report','[data-id=body]');assert.match(await page.locator('#app').innerText(),/睡不安稳/);await click('ss-interpret');
  assert.doesNotMatch(await page.locator('#ss-ai-messages').innerText(),/仅情绪报告|仅人生报告|2000-8-16/);assert.match(await page.locator('#ss-ai-messages').innerText(),/器官检测或临床评分/);
  await click('ss-followup');assert.equal(await page.evaluate(()=>state.ssAiContext.id),'body');
  for(const id of ['traits','mind','life','ziwei']){await go('serviceReports');await click('ss-report','[data-id='+id+']');await click('ss-interpret');assert.equal(await page.evaluate(()=>state.ssAiContext.id),id);}
  const report=await page.evaluate(()=>ssReports().find(x=>x.id==='ziwei'));assert.equal(report.rows[1][1],'午');assert.equal(report.rows[2][1],'戌');assert.ok(!JSON.stringify(report.rows).includes('2000-8-16'));
  await click('ss-ai-clear');await click('ss-ai-clear-confirm');assert.equal(await page.evaluate(()=>ssReports().filter(x=>x.ready).length),5);
 });
 await check('Friend search rejects unknown accounts and example contacts support add, rename and draft conversations',async()=>{
  await go('friendSearch');await page.locator('#ss-friend-query').fill('UNKNOWN999');await page.locator('#ss-friend-search-form button').click();assert.match(await page.locator('#app').innerText(),/暂未找到/);
  await click('ss-search-example','[data-id=EW1001]');await click('ss-friend-add');await click('ss-friend-add-confirm');assert.equal(await page.evaluate(()=>state.support.friends.length),1);
  await click('ss-friend-rename');await page.locator('#ss-contact-name').fill('山岚同学 <b>');await click('ss-friend-name-save');assert.match(await page.locator('#app').innerText(),/山岚同学 <b>/);assert.equal(await page.locator('#app b:has-text("山岚同学")').count(),0);
  await click('ss-chat-open');await page.locator('#ss-message-input').fill('今天一起练习一分钟吧。<script>window.bad=1</script>');await page.locator('#ss-message-form button').click();assert.equal(await page.evaluate(()=>state.support.messages.EW1001[0].status),'draft');assert.equal(await page.evaluate(()=>window.bad),undefined);assert.match(await page.locator('#app').innerText(),/草稿/);
  await go('friendSearch');await click('ss-search-example','[data-id=EW1002]');await click('ss-friend-add');await click('ss-friend-add-confirm');assert.equal(await page.evaluate(()=>state.support.friends.length),2);
  await go('communityInbox');assert.equal(await page.locator('[data-action=ss-chat-open]').count(),1);
 });
 await check('Sharing previews include selected public content and reopen originals; personal reports stay excluded',async()=>{
  await page.evaluate(()=>{state.quoteDate=today();state.quoteId=null;});await go('quote');await click('ss-share-current');assert.equal(await page.evaluate(()=>state.ssAttachment.type),'quote');
  await page.locator('#ss-share-text').fill('这一句话，留给今天的自己。');await page.locator('#ss-share-form button[type=submit]').click();assert.equal(await page.evaluate(()=>state.support.posts.length),1);assert.equal(await page.locator('.ss-post').count(),1);assert.doesNotMatch(await page.locator('.ss-post').innerText(),/仅情绪报告|仅人生报告|2000-8-16/);
  await click('ss-shared-open');assert.equal(await page.evaluate(()=>state.page),'quote');
  await page.evaluate(()=>academyOpen('academy-tcm-video'));await click('ss-share-current');await page.locator('#ss-share-target').selectOption('EW1001');await page.locator('#ss-share-form button[type=submit]').click();assert.equal(await page.evaluate(()=>state.page),'conversation');assert.equal(await page.evaluate(()=>state.support.messages.EW1001.at(-1).attachment.type),'academy');await click('ss-shared-open');assert.equal(await page.evaluate(()=>state.academyId),'academy-tcm-video');
  await page.evaluate(()=>musicOpen('night'));await click('ss-share-current');assert.equal(await page.evaluate(()=>state.ssAttachment.id),'night');await click('ss-attach');assert.ok(await page.locator('input[name=ss-share-attachment]').count()>10);assert.doesNotMatch(await page.locator('.ss-share-choices').innerText(),/出生|身心能量评估|情绪觉察记录/);await page.locator('input[name=ss-share-attachment]').first().check();await click('ss-attach-confirm');assert.equal(await page.evaluate(()=>state.ssAttachment.type),'quote');
 });
 await check('Teacher one-to-one requests validate, save, reopen, edit and delete without fake appointments',async()=>{
  await go('teachers');assert.equal(await page.locator('[data-action=ss-teacher-request]').count(),4);await click('ss-teacher-request','[data-topic=healing]');await page.locator('#ss-teacher-question').fill('想讨论如何安排日常练习。');await page.locator('#ss-teacher-time').selectOption('evening');await page.locator('#ss-teacher-form button[type=submit]').click();assert.equal(await page.evaluate(()=>state.support.requests.length),1);assert.equal(await page.evaluate(()=>state.support.requests[0].status),'draft');assert.match(await page.locator('#app').innerText(),/尚未发送给老师/);
  await click('ss-teacher-edit');await page.locator('#ss-teacher-question').fill('想讨论练习节奏与最近的感受。');await page.locator('#ss-teacher-form button[type=submit]').click();assert.equal(await page.evaluate(()=>state.support.requests.length),1);assert.match(await page.locator('#app').innerText(),/最近的感受/);
  await go('communityInbox');assert.equal(await page.locator('[data-action=ss-teacher-open]').count(),1);
 });
 await check('All records persist across reload; clearing drafts leaves original wellbeing data intact',async()=>{
  await page.reload();assert.equal(await page.evaluate(()=>state.support.friends.length),2);assert.equal(await page.evaluate(()=>state.support.posts.length),1);assert.equal(await page.evaluate(()=>state.support.requests.length),1);assert.equal(await page.evaluate(()=>state.support.messages.EW1001.length),2);assert.equal(await page.evaluate(()=>ssReports().filter(x=>x.ready).length),5);
  await go('teachers');await click('ss-teacher-delete');await click('ss-teacher-delete-confirm');assert.equal(await page.evaluate(()=>state.support.requests.length),0);
  await go('community');await click('ss-post-delete');await click('ss-post-delete-confirm');assert.equal(await page.evaluate(()=>state.support.posts.length),0);
  await page.evaluate(()=>{state.ssChatId='EW1002';});await go('friendDetail');await click('ss-friend-remove');await click('ss-friend-remove-confirm');assert.equal(await page.evaluate(()=>state.support.friends.length),1);
 });
 await check('New screens fit both languages, themes and mobile widths with safe text and correct active tabs',async()=>{
  const ids=['home','service','serviceHelp','serviceReports','serviceReport','serviceChat','community','friends','friendSearch','friendDetail','communityInbox','conversation','teachers','teacherRequest','teacherDetail','communityProfile','shareCompose'];
  await page.evaluate(()=>{state.ssChatId='EW1001';state.ssReportId='body';state.ssRequestDraft={topic:'healing',question:'测试',date:'',time:'flexible',format:'text'};});
  for(const width of [320,393]){await page.setViewportSize({width,height:852});for(const lang of ['zh','en'])for(const mode of ['day','night']){await page.evaluate(({lang,mode})=>{state.lang=lang;state.mode=mode},{lang,mode});for(const id of ids){await go(id);const sizes=await page.evaluate(()=>({w:innerWidth,doc:document.documentElement.scrollWidth,app:document.getElementById('app').scrollWidth,text:document.getElementById('app').innerText}));assert.ok(sizes.doc<=sizes.w+1&&sizes.app<=sizes.w+1,JSON.stringify({id,width,lang,mode,...sizes}));assert.doesNotMatch(sizes.text,/undefined|NaN|进入这个模块/);if(id.startsWith('service'))assert.equal(await page.locator('#nav [aria-current=page]').getAttribute('data-to'),'service');}}}
 });
 const review=await browser.newPage({viewport:{width:1440,height:1050},reducedMotion:'reduce'});review.on('pageerror',e=>errors.push(e.message));await review.goto('file:///'+root+'/output/发给负责人-东方智慧首页R4.html');await review.frameLocator('#experience-frame').locator('.home-v4').waitFor();
 await check('Review opens service, reports, community, teachers and friends; homepage features still work',async()=>{for(const id of ['service','serviceReports','community','teachers','friends','home']){await review.locator('[data-page='+id+']').click();await review.waitForTimeout(40);assert.equal(await review.frameLocator('#experience-frame').locator('body').getAttribute('data-page'),id);}await review.screenshot({path:root+'/output/R4-网页预览.png',fullPage:true});});
 assert.deepEqual(errors,[]);await browser.close();fs.writeFileSync(root+'/output/R4服务社群验证.json',JSON.stringify({date:'2026-10-14',checks,errors,layoutCombinations:17*8,scope:'Offline help and local drafts; no live AI, real social delivery or teacher appointments.'},null,2));console.log('ALL '+checks.length+' CHECKS PASSED');
})().catch(e=>{console.error(e);process.exit(1)});
