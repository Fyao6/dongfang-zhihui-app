const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const remote=process.argv[2],label=remote?'公网':'本地',entry=remote?remote+'/':pathToFileURL(path.join(__dirname,'../03_当前APP/东方智慧-首页体验R4.html')).href;
(async()=>{const b=await chromium.launch({headless:true,args:['--no-proxy-server','--autoplay-policy=document-user-activation-required']}),checks=[],errors=[];try{
let p,context;
for(const lang of ['zh-Hans','zh-Hant','en','bo']){
 const c=await b.newContext({viewport:{width:390,height:844},hasTouch:true,reducedMotion:'reduce'}),page=await c.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(entry+'?lang='+lang+'&page=community');if(remote)await page.waitForFunction(()=>px.loaded);
 await page.waitForFunction(()=>{const v=document.querySelector('.cf-video-card video');return v&&!v.paused&&v.currentTime>.3});
 assert(await page.locator('.cf-video-card video').first().evaluate(v=>v.muted&&v.videoWidth>0));
 assert.equal(await page.locator('.cf-play-symbol').first().evaluate(e=>getComputedStyle(e).visibility),'hidden');
 checks.push(lang+' 无手势直接进入自动静音播放');
 if(lang==='zh-Hans'){p=page;context=c;}else await c.close();
}
await p.evaluate(()=>{window.departingVideo=document.querySelector('.cf-video-card video');navigate('home')});assert(await p.evaluate(()=>window.departingVideo.paused));checks.push('离开社群立即暂停');
await p.locator('#nav [data-to=community]').click();await p.waitForFunction(()=>!document.querySelector('.cf-video-card video').paused);checks.push('点击社群直接播放');
await p.locator('.cf-stage-toggle').first().click();assert(await p.locator('video').first().evaluate(v=>v.paused));
await p.evaluate(()=>render(false));await p.waitForTimeout(350);assert(await p.locator('video').first().evaluate(v=>v.paused));checks.push('手动暂停在页面重绘后保留');
await p.locator('.community-tabs [data-to=friends]').click();await p.locator('.community-tabs [data-to=community]').click();await p.waitForFunction(()=>!document.querySelector('.cf-video-card video').paused);checks.push('好友返回推荐自动播放');
await p.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))});assert(await p.locator('video').evaluateAll(v=>v.every(x=>x.paused)));
await p.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))});await p.waitForFunction(()=>!document.querySelector('.cf-video-card video').paused);checks.push('后台暂停并在回来时恢复');
await p.locator('.cf-stage-toggle').first().click();await p.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))});await p.waitForTimeout(200);assert(await p.locator('video').first().evaluate(v=>v.paused));checks.push('主动暂停不会因切换窗口被取消');
await p.evaluate(()=>{navigate('home');px.posts=[{id:'autoplay-a',title:'播放测试A',body:'仅浏览器测试',mediaUrl:COMMUNITY_PREVIEW_VIDEO},{id:'autoplay-b',title:'播放测试B',body:'仅浏览器测试',mediaUrl:COMMUNITY_PREVIEW_VIDEO}];cfCurrentId='';navigate('community')});
await p.waitForFunction(()=>!document.querySelectorAll('.cf-video-card video')[0].paused);
await p.locator('.cf-stage-toggle').first().click();await p.locator('.cf-video-card').first().locator('[data-cf=next]').click();
await p.waitForFunction(()=>document.querySelectorAll('.cf-video-card video')[0].paused&&!document.querySelectorAll('.cf-video-card video')[1].paused);
assert.equal(await p.locator('video').evaluateAll(v=>v.filter(x=>!x.paused).length),1);checks.push('暂停当前视频后切换下一条仍自动播放且仅一条播放');
await p.locator('.cf-feed').evaluate(e=>{e.scrollTop=e.clientHeight*2});await p.waitForFunction(()=>!document.querySelectorAll('.cf-video-card video')[2].paused&&document.querySelectorAll('.cf-video-card video')[1].paused);checks.push('上下滑动切换自动播放');
await p.evaluate(()=>{navigate('home');px.posts=[];cfCurrentId='';cfMuted=false;window.realVideoPlay=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){return this.muted?window.realVideoPlay.call(this):Promise.reject(new DOMException('Browser sound policy','NotAllowedError'))};navigate('community')});
await p.waitForFunction(()=>{const v=document.querySelector('.cf-video-card video');return v.muted&&!v.paused&&v.currentTime>.2});
await p.evaluate(()=>{HTMLMediaElement.prototype.play=window.realVideoPlay});checks.push('有声被浏览器拒绝时自动静音重试');
await p.evaluate(()=>{navigate('home');HTMLMediaElement.prototype.play=function(){return Promise.reject(new DOMException('Autoplay blocked','NotAllowedError'))};navigate('community')});await p.waitForTimeout(200);
assert.equal(await p.locator('.cf-play-symbol').first().evaluate(e=>getComputedStyle(e).visibility),'visible');
await p.evaluate(()=>{HTMLMediaElement.prototype.play=window.realVideoPlay});await p.locator('.cf-stage-toggle').first().click();await p.waitForFunction(()=>!document.querySelector('.cf-video-card video').paused);checks.push('浏览器完全禁止自动播放时保留可用播放入口');
await p.evaluate(()=>{tbSetVisible(false);document.getElementById('toast').classList.remove('show')});await p.waitForTimeout(200);await p.screenshot({path:path.join(__dirname,'推荐视频自动播放-'+label+'.png')});
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(__dirname,'推荐视频自动播放-'+label+'核验.json'),JSON.stringify({at:new Date().toISOString(),pass:true,checks,errors},null,2));console.log('PASS '+label+' autoplay: '+checks.length+' checks');
}finally{await b.close();}})().catch(e=>{console.error(e.stack);process.exitCode=1});

