// Browser-only integration fixtures. Requests are intercepted; no live data is written.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4'),origin='https://community-qa.invalid';
const html=fs.readFileSync(path.join(root,'03_当前APP/东方智慧-首页体验R4.html'),'utf8');
const seed=JSON.parse(fs.readFileSync(path.join(r4,'backend/initial-content.json'),'utf8'));
const api={posts:[],requests:[],submissions:[]};
const teacher={id:'qa-certified-teacher',name:'认证老师测试',nameEn:'Verified teacher fixture',nameHant:'認證老師測試',nameBo:'དགེ་རྒན།',specialty:'呼吸与觉察',specialtyEn:'Breathing and awareness',specialtyBo:'དབུགས་གཏོང་ལེན།',bio:'仅用于浏览器隔离测试的老师资料。',bioEn:'A teacher profile used only in isolated browser tests.',bioBo:'དགེ་རྒན་གྱི་ངོ་སྤྲོད།',profileType:'real',verified:true,recommended:true};
seed.teachers=[teacher,{...teacher,id:'qa-sample',name:'示例老师不推荐',profileType:'demo'},{...teacher,id:'qa-unverified',name:'未认证不推荐',verified:false},{...teacher,id:'qa-not-recommended',name:'未推荐不展示',recommended:false}];
const user={id:'qa-student',username:'qa_student',name:'测试学员',role:'user'};
(async()=>{const browser=await chromium.launch({headless:true,args:['--autoplay-policy=document-user-activation-required']}),checks=[],ratioCases=[],errors=[];try{
const page=await browser.newPage({viewport:{width:390,height:844},hasTouch:true,reducedMotion:'reduce'});
page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',async route=>{
 const req=route.request(),url=new URL(req.url());
 if(url.origin!==origin)return route.abort();
 if(url.pathname==='/experience')return route.fulfill({contentType:'text/html; charset=utf-8',body:html});
 let body={items:[]},status=200;
 if(url.pathname==='/api/public')body={content:seed,user,settings:{theme:{}},aiReady:false};
 else if(url.pathname==='/api/community/posts')body={items:api.posts};
 else if(url.pathname==='/api/service-requests'&&req.method()==='POST'){
  const d=req.postDataJSON();api.submissions.push(d);const request={id:'qa-request-'+(api.requests.length+1),teacherId:d.teacherId,teacherName:teacher.name,body:d.body,date:d.date,status:'pending'};api.requests.push(request);body={id:request.id,status:request.status};
 }else if(url.pathname==='/api/service-requests')body={items:api.requests};
 else if(url.pathname.startsWith('/api/service-requests/')&&req.method()==='PATCH'){
  const item=api.requests.find(r=>r.id===url.pathname.split('/').pop());if(item)item.status='cancelled';body={ok:true};
 }else if(url.pathname.startsWith('/api/time-bank/'))body={schemaVersion:2,accountId:user.id,zone:'Asia/Shanghai',clockBasis:'server',serverNow:Date.now(),running:true,runs:[],summary:{totalMs:0,todayMs:0,days:{}}};
 return route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
});
await page.goto(origin+'/experience');await page.waitForFunction(()=>px.loaded&&typeof communityTeachersPage==='function');
await page.evaluate(()=>{tbSetVisible(false);navigate('communityTeachers')});
assert.deepEqual(await page.locator('.community-tabs button').allTextContents(),['我的好友','我的对话','老师推荐','推荐视频']);
assert.equal(await page.locator('.ct-teacher-card').count(),1);assert.equal(await page.locator('.ct-teacher-card').getAttribute('data-id'),teacher.id);checks.push('四入口与已认证、真实、推荐老师筛选');
await page.locator('.ct-teacher-card').click();assert.equal(await page.locator('.ct-profile h1').textContent(),teacher.name);
await page.locator('[data-action=px-service-request]').click();await page.locator('#px-service-form').waitFor();
assert.equal(await page.locator('#px-service-form [name=teacherId]').inputValue(),teacher.id);
await page.locator('#px-service-form [name=body]').fill('隔离浏览器咨询联调，不提交到公网。');
await page.locator('#px-service-form [name=date]').fill(new Date(Date.now()+86400000).toISOString().slice(0,10));
await page.locator('#px-service-form button').click();await page.locator('#px-service-form').waitFor({state:'hidden'});
await page.waitForFunction(()=>document.querySelector('.ct-request')?.textContent.includes('隔离浏览器咨询联调'));
assert.equal(api.submissions.length,1);assert.equal(api.submissions[0].teacherId,teacher.id);checks.push('老师详情及咨询表单传递真实目标、提交后显示记录（隔离API）');
await page.evaluate(()=>{document.getElementById('toast').textContent=''});
for(const viewport of [{width:360,height:740},{width:390,height:844},{width:430,height:932},{width:550,height:850}]){
 await page.setViewportSize(viewport);
 for(const lang of ['zh','zh-Hant','en','bo']){
  await page.evaluate(lang=>{state.lang=lang;navigate('communityTeachers')},lang);await page.evaluate(()=>document.fonts.ready);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert(await page.locator('.community-tabs button').evaluateAll(es=>es.every(e=>{const b=e.getBoundingClientRect();return b.left>=0&&b.right<=innerWidth+1})));
  if(viewport.width===390)await page.screenshot({path:path.join(__dirname,'老师推荐-四语-'+lang+'.png')});
 }
}
checks.push('老师推荐四语言与360/390/430/550宽度布局无溢出');
const clips=await page.evaluate(async()=>{
 const specs=[['9x16',144,256],['3x4',192,256],['1x1',256,256],['16x9',320,180]],result=[];
 for(const [id,width,height] of specs){
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d'),stream=canvas.captureStream(12),chunks=[],recorder=new MediaRecorder(stream,{mimeType:'video/webm'});
  const done=new Promise(resolve=>{recorder.onstop=()=>resolve(new Blob(chunks,{type:'video/webm'}))});recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
  let frame=0;const draw=()=>{ctx.fillStyle='#123b43';ctx.fillRect(0,0,width,height);ctx.strokeStyle='#f2f2d9';ctx.lineWidth=4;ctx.strokeRect(3,3,width-6,height-6);ctx.fillStyle='#60bdaa';ctx.fillRect(5,5,width-10,Math.max(18,height*.08));ctx.fillStyle='#4576ad';ctx.fillRect(5,height-Math.max(24,height*.1),width-10,Math.max(18,height*.08));ctx.fillStyle='#e5c28a';ctx.beginPath();ctx.arc(width/2,height/2,Math.min(width,height)*.2,0,Math.PI*2);ctx.fill();ctx.fillStyle='#17333b';ctx.font='bold '+Math.max(16,Math.floor(width*.1))+'px sans-serif';ctx.textAlign='center';ctx.fillText(id,width/2,height/2+6);ctx.fillStyle='#fff';ctx.font='12px sans-serif';ctx.fillText('TOP · '+(++frame),width/2,18);ctx.fillText('BOTTOM',width/2,height-10);};
  draw();recorder.start();const timer=setInterval(draw,60);await new Promise(r=>setTimeout(r,430));clearInterval(timer);recorder.stop();const blob=await done;stream.getTracks().forEach(t=>t.stop());
  result.push({id:'ratio-'+id,title:'比例验证 '+id,body:'真实Canvas录制视频，顶部与底部有安全边界标记。',authorName:'隔离测试',mediaUrl:URL.createObjectURL(blob),width,height,ratio:id});
 }
 return result;
});
api.posts=clips.map(({width,height,ratio,...post})=>post);
await page.evaluate(posts=>{px.posts=posts;cfCurrentId='';navigate('community')},api.posts);
for(const viewport of [{width:360,height:740},{width:390,height:844},{width:430,height:932},{width:550,height:850}]){
 await page.setViewportSize(viewport);
 for(const lang of ['zh','zh-Hant','en','bo']){
  for(const clip of clips){
   await page.evaluate(({lang,id})=>{state.lang=lang;cfCurrentId=id;render(false)},{lang,id:clip.id});
   await page.evaluate(()=>document.fonts.ready);
   const selector='.cf-video-card[data-video-id="'+clip.id+'"]';
   await page.waitForFunction(id=>{const v=document.querySelector('.cf-video-card[data-video-id="'+id+'"] video');return v&&v.videoWidth>0&&!v.paused&&v.currentTime>.02},clip.id);
   const metric=await page.locator(selector).evaluate(card=>{
    const v=card.querySelector('video'),ratio=v.videoWidth/v.videoHeight,frame=card.clientWidth/card.clientHeight;
    return {videoWidth:v.videoWidth,videoHeight:v.videoHeight,ratio,frame,crop:1-Math.min(ratio/frame,frame/ratio),mode:card.dataset.videoFit,shape:card.dataset.videoShape,fit:getComputedStyle(v).objectFit,pageMode:card.closest('.community-feed-page').dataset.videoLayout,playing:!v.paused,activeCount:[...document.querySelectorAll('.cf-video-card video')].filter(x=>!x.paused).length,progressGap:Math.abs(card.getBoundingClientRect().bottom-card.querySelector('.cf-playback').getBoundingClientRect().bottom),captionGap:card.getBoundingClientRect().bottom-card.querySelector('.cf-caption').getBoundingClientRect().bottom,overflow:document.documentElement.scrollWidth>innerWidth};
   });
   assert.equal(metric.videoWidth,clip.width);assert.equal(metric.videoHeight,clip.height);assert.equal(metric.activeCount,1);assert(metric.playing&&!metric.overflow);assert(metric.progressGap<1&&metric.captionGap>=26&&metric.captionGap<=30);
   const expected=metric.ratio<.82&&metric.crop<=.18?'fill':'fit';assert.equal(metric.mode,expected);assert.equal(metric.pageMode,expected);assert.equal(metric.fit,expected==='fill'?'cover':'contain');if(expected==='fill')assert(metric.crop<=.18);
   assert(await page.locator('.community-tabs button').evaluateAll(es=>es.every(e=>{const box=e.getBoundingClientRect();return box.left>=0&&box.right<=innerWidth+1})));
   ratioCases.push({viewport,lang,source:clip.ratio,...metric});
   if(viewport.width===390&&lang==='zh')await page.screenshot({path:path.join(__dirname,'推荐视频比例-'+clip.ratio+'.png')});
  }
 }
}
checks.push('四种真实录制比例×四语言×四尺寸共64例，自动播放且只播放当前视频，保留底部进度和左下文案');
await page.evaluate(()=>{cfCurrentId='ratio-9x16';state.lang='zh';render(false)});
await page.waitForFunction(()=>!document.querySelector('.cf-video-card[data-video-id="ratio-9x16"] video').paused);
await page.locator('.cf-video-card[data-video-id="ratio-9x16"] .cf-stage-toggle').click();assert(await page.locator('.cf-video-card[data-video-id="ratio-9x16"] video').evaluate(v=>v.paused));
await page.evaluate(()=>render(false));await page.waitForTimeout(200);assert(await page.locator('.cf-video-card[data-video-id="ratio-9x16"] video').evaluate(v=>v.paused));checks.push('手动暂停在页面重绘后保留');
await page.locator('.cf-video-card[data-video-id="ratio-9x16"] [data-cf=next]').click();await page.waitForFunction(()=>!document.querySelector('.cf-video-card[data-video-id="ratio-3x4"] video').paused);checks.push('从已暂停视频切换下一条自动播放');
await page.evaluate(()=>{window.leftVideo=document.querySelector('.cf-video-card[data-video-id="ratio-3x4"] video');navigate('communityTeachers')});assert(await page.evaluate(()=>window.leftVideo.paused));checks.push('离开推荐视频切换老师页立即暂停');
await page.evaluate(()=>{px.content.teachers=[];navigate('communityTeachers')});assert.equal(await page.locator('.ct-teacher-card').count(),0);assert(await page.locator('.ct-empty').isVisible());checks.push('无认证推荐老师时显示真实空状态');
assert.deepEqual(errors,[]);
const report={at:new Date().toISOString(),pass:true,buildSHA256:crypto.createHash('sha256').update(html).digest('hex'),scope:'Local current build with browser-isolated API fixtures; canvas MediaRecorder WebM files are real media metadata/playback. No live account, content or API writes.',checks,ratioCases,errors};
fs.writeFileSync(path.join(__dirname,'视频比例与老师推荐核验.json'),JSON.stringify(report,null,2));
console.log('PASS community teachers and real video ratios: '+checks.length+' checks, '+ratioCases.length+' ratio/locale/viewport cases');
}finally{await browser.close()}})().catch(e=>{console.error(e.stack);process.exitCode=1});

