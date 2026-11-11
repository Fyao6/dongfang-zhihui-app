
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium,request}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const base=process.argv[2]||'http://127.0.0.1:8878',remote=base.startsWith('https:'),label=remote?'公网':'本地';
(async()=>{const browser=await chromium.launch({headless:true,args:['--no-proxy-server']});let api;try{
 const p=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(base+'/experience?lang=zh-Hans');await p.waitForFunction(()=>px.loaded);
 await p.evaluate(()=>navigate('academy'));assert.equal(await p.locator('[data-action=at-view][aria-pressed=true]').getAttribute('data-view'),'teachers');assert(await p.locator('.at-teacher-card').count()>=3);
 await p.locator('[data-action=at-open][data-id=demo-qinghe]').click();assert.equal(await p.locator('.academy-course').count(),3);await p.locator('.academy-course').first().click();assert(await p.locator('.at-course-author').isVisible());await p.locator('.px-top [data-to=academyTeacher]').click();assert.equal(await p.locator('.academy-course').count(),3);
 for(const lang of ['zh','zh-Hant','en','bo']){
  await p.evaluate(lang=>{state.lang=lang;state.wellness.continuity.learning=null;navigate('academy');},lang);await p.evaluate(()=>document.fonts.ready);
  await p.screenshot({path:path.join(__dirname,'老师分类-'+label+'-'+lang+'.png')});
  await p.locator('#nav [data-to=community]').click();await p.locator('video').first().waitFor();await p.waitForFunction(()=>document.querySelector('.cf-video-card video').readyState>=2);await p.evaluate(()=>document.fonts.ready);
  assert.equal(await p.locator('.community-tabs button').count(),3);assert.equal(await p.locator('.ew-community-tools,.ew-teacher-entry,[data-action=px-publish]').count(),0);
  assert(await p.locator('.community-preview-video video').evaluate(v=>new Promise(resolve=>{const image=new Image();image.onload=()=>resolve(image.naturalWidth===1080&&image.naturalHeight===1920);image.onerror=()=>resolve(false);image.src=v.poster;})));
  await p.waitForTimeout(120);
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await p.screenshot({path:path.join(__dirname,'社群视频-'+label+'-'+lang+'.png')});
 }
 await p.evaluate(()=>{state.lang='zh';render(false)});await p.waitForFunction(()=>document.querySelector('.cf-video-card video').currentTime>.3&&!document.querySelector('.cf-video-card video').paused);
 await p.locator('.community-tabs [data-to=friends]').click();assert.equal(await p.locator('.cf-video-card').count(),0);assert(await p.locator('.community-tabs [data-to=communityInbox]').isVisible());await p.locator('.community-tabs [data-to=communityInbox]').click();assert.equal(await p.locator('.community-tabs [aria-current=page]').getAttribute('data-to'),'communityInbox');
 await p.locator('#nav [data-to=profile]').click();await p.locator('[data-to=communityPosts]').click();assert(await p.locator('[data-action=px-publish]').isVisible());assert.equal(await p.locator('.cf-video-card').count(),0);
 const creds=JSON.parse(fs.readFileSync(path.join(__dirname,'../04_研发源码/app/cloud/.env.test'),'utf8'));api=await request.newContext({baseURL:base});assert.equal((await api.post('/api/auth/login',{data:creds})).status(),200);
 const c=await browser.newContext({storageState:await api.storageState(),viewport:{width:1280,height:900}}),admin=await c.newPage();await admin.goto(base+'/admin');await admin.locator('.sidebar [data-nav=courses]').click();await admin.locator('[data-edit=academy-ziwei-video]').click();assert.equal(await admin.locator('[name=teacherId]').inputValue(),'demo-qinghe');assert(await admin.locator('[name=teacherId] option').count()>=4);
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(__dirname,'老师社群-'+label+'验收.json'),JSON.stringify({at:new Date().toISOString(),base,pass:true,scope:'Actual API and browser, read-only except login and heartbeat',checks:['默认老师分类与已发布课程归属','课程详情与返回老师','四语言页面与视频布局','移除分享心得与旧社群大头部','真实视频播放及离页停止','好友与对话入口','我的发布入口','后台老师归属下拉框'],errors},null,2));console.log('PASS '+label+' teacher collections, four locales, video and navigation, admin association field');
}finally{await api?.dispose();await browser.close();}})().catch(e=>{console.error(e.stack);process.exitCode=1});

