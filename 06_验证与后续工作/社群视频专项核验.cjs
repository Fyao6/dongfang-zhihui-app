
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(pathToFileURL(path.join(__dirname,'../03_当前APP/东方智慧-首页体验R4.html')).href);await p.evaluate(()=>navigate('community'));
assert.deepEqual(await p.locator('.community-tabs button').allTextContents(),['我的好友','我的对话','推荐视频']);
assert.equal(await p.locator('.ew-community-tools,.ew-teacher-entry,[data-action=px-publish]').count(),0);
await p.waitForFunction(()=>document.querySelector('.cf-video-card video').currentTime>.5);assert(await p.locator('video').evaluate(v=>v.videoWidth===1080&&v.muted));
await p.locator('[data-cf=sound]').click();assert.equal(await p.locator('video').evaluate(v=>v.muted),false);
await p.locator('.community-tabs [data-to=friends]').click();assert.equal(await p.locator('.cf-video-card').count(),0);assert.equal(await p.locator('.community-tabs [aria-current=page]').getAttribute('data-to'),'friends');
await p.locator('.community-tabs [data-to=communityInbox]').click();assert.equal(await p.locator('.community-tabs [aria-current=page]').getAttribute('data-to'),'communityInbox');
await p.evaluate(()=>{cfCurrentId='';px.posts=[{id:'feed-fixture-a',title:'测试视频 A',body:'滑动验证',authorName:'测试',mediaUrl:COMMUNITY_PREVIEW_VIDEO},{id:'feed-fixture-b',title:'测试视频 B',body:'暂停验证',authorName:'测试',mediaUrl:COMMUNITY_PREVIEW_VIDEO},{id:'text-only',title:'纯文字',body:'不进入推荐视频'}];navigate('community');});
assert.equal(await p.locator('.cf-video-card').count(),3);
await p.waitForFunction(()=>document.querySelectorAll('.cf-video-card video')[0].currentTime>.3);
await p.locator('.cf-video-card').first().locator('[data-cf=next]').click();await p.waitForFunction(()=>document.querySelectorAll('.cf-video-card video')[0].paused&&!document.querySelectorAll('.cf-video-card video')[1].paused);
await p.locator('.cf-video-card').nth(1).locator('[data-cf-seek]').fill('500');assert(await p.locator('video').nth(1).evaluate(v=>v.currentTime>4));
await p.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));});assert(await p.locator('.cf-video-card video').evaluateAll(es=>es.every(v=>v.paused)));
await p.evaluate(()=>{delete document.hidden;px.posts=[];cfCurrentId='';navigate('community');document.getElementById('toast').textContent='';});await p.evaluate(()=>document.fonts.ready);
for(const lang of ['zh','zh-Hant','en','bo']){await p.evaluate(lang=>{state.lang=lang;render(false)},lang);await p.evaluate(()=>document.fonts.ready);assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert(await p.locator('.cf-feed').evaluate(e=>e.clientHeight>500));await p.screenshot({path:path.join(__dirname,'社群视频-'+lang+'.png')});}
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(__dirname,'社群视频专项核验.json'),JSON.stringify({at:new Date().toISOString(),pass:true,checks:['三标签导航与精简入口','真实视频播放及声音开关','好友与对话导航','只展示视频内容','上下切换仅一个视频播放','进度拖动','隐藏页面及离页暂停','四语言布局'],errors},null,2));console.log('PASS community navigation, real video controls, feed switching, pause lifecycle and four locales');
}finally{await b.close();}})().catch(e=>{console.error(e.stack);process.exitCode=1});

