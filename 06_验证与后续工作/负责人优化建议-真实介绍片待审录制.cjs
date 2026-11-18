// Real APP recording only. Fresh SQLite, synthetic birth form, no voice/music/AI footage.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict'),{spawn,execFileSync}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),R4=path.join(ROOT,'04_研发源码/app/r4'),OUT=path.join(ROOT,'02_需求与设计参考'),runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {chromium,request}=require(path.join(runtime,'node/node_modules/playwright')),{setLifeBirth}=require('./生命出生资料测试前置.cjs');
const ffmpeg=path.join(require('node:os').homedir(),'AppData/Local/ms-playwright/ffmpeg-1011/ffmpeg-win64.exe');assert(fs.existsSync(ffmpeg));assert(fs.existsSync(OUT));
const runId=Date.now().toString(36)+'_'+crypto.randomBytes(3).toString('hex'),db=path.join(__dirname,'负责人优化建议-介绍片录制隔离-'+runId+'.sqlite3');assert(!fs.existsSync(db));
const master=path.join(OUT,'东方智慧APP介绍片-待审初剪-无旁白无音乐-无字幕母版.webm'),cover=path.join(OUT,'东方智慧APP介绍片-待审初剪-真实首页封面.png'),rawFile=path.join(__dirname,'负责人优化建议-介绍片源录屏-'+runId+'-待审.webm');
assert(!fs.existsSync(master),'Do not overwrite a reviewed or previous draft without explicit review');
const report={runId,status:'待审初剪，无旁白无音乐',formalIntroductionProduced:false,realAPPFootageOnly:true,communityClipUsed:false,syntheticBirthOnly:true,originalDatabaseOpened:false,publicDeployed:false,ownedDatabase:path.relative(ROOT,db),scenes:[],errors:[],externalRequestsBlocked:[],outputs:[],mediaCapabilities:{encoder:'Playwright bundled ffmpeg libvpx',container:'WebM',h264Available:false,audio:false}};
let server,browser,base,context,recordPage;
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
async function start(){
 server=spawn(path.join(runtime,'python/python.exe'),['-B',path.join(R4,'backend/server.py'),'--port','0','--db',db,'--web-root',path.join(ROOT,'03_当前APP')],{cwd:ROOT,windowsHide:true,stdio:['ignore','pipe','pipe']});let log='';server.stdout.on('data',b=>{log+=b;const m=log.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/);if(m)base=m[1];});server.stderr.on('data',()=>{});
 const probe=await request.newContext();let ready=false;for(let i=0;i<180;i++){if(server.exitCode!==null)throw Error('Recording isolation service exited');if(base)try{if((await probe.get(base+'/api/health',{timeout:500})).ok()){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}await probe.dispose();assert(ready);report.base=base;browser=await chromium.launch({headless:true});
}
async function blockExternal(ctx){await ctx.route('**/*',route=>{const u=new URL(route.request().url());if(['http:','https:'].includes(u.protocol)&&u.origin!==base){report.externalRequestsBlocked.push(u.origin);return route.abort();}return route.continue();});}
async function go(page,route){assert(await page.evaluate(route=>typeof screens[route]==='function',route),'Actual route exists: '+route);await page.evaluate(route=>navigate(route),route);await page.waitForFunction(()=>!document.documentElement.dataset.ambientTransition);assert.equal(await page.evaluate(()=>state.page),route);}
async function run(){
 await start();
 const warm=await browser.newContext({viewport:{width:960,height:540},deviceScaleFactor:2});await blockExternal(warm);const preparation=await warm.newPage();await preparation.goto(base+'/experience');await preparation.waitForFunction(()=>px.loaded);await preparation.evaluate(()=>ewChangeLanguage('zh'));
 await setLifeBirth(preparation,{name:'演示样本',date:'1990-01-01',sex:'male',time:'12:00'});
 for(const route of ['lifeResult','ziweiChart','classicsWisdom','westernAstrology','body','teaLife','chineseCare','tibetanCare','mind','healingSpace','meditationStudy','academy','home'])await go(preparation,route);
 const storageState=await warm.storageState();await warm.close();
 context=await browser.newContext({storageState,viewport:{width:960,height:540},deviceScaleFactor:2,recordVideo:{dir:__dirname,size:{width:1920,height:1080}}});await blockExternal(context);
 const sourceRequest=await request.newContext(),sourceResponse=await sourceRequest.get(base+'/experience'),loadedHTML=(await sourceResponse.body()).toString('utf8');await sourceRequest.dispose();report.recordedAppSha256=sha(Buffer.from(loadedHTML));
 const expectedScript=sha([...loadedHTML.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1].replace(/\r\n?/g,'\n')).join('\n'));
 const beforePage=Date.now();recordPage=await context.newPage();recordPage.on('pageerror',e=>report.errors.push(e.message));await recordPage.goto(base+'/experience');await recordPage.waitForFunction(()=>px.loaded);
 report.loadedScriptSha256=await recordPage.evaluate(async()=>{const bytes=new TextEncoder().encode([...document.querySelectorAll('script')].map(s=>s.textContent).join('\n')),hash=await crypto.subtle.digest('SHA-256',bytes);return [...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('');});assert.equal(report.loadedScriptSha256,expectedScript,'Actual loaded script matches the recorded APP source identity');
 await recordPage.evaluate(()=>ewChangeLanguage('zh'));await go(recordPage,'home');await recordPage.evaluate(()=>document.fonts.ready);
 const sceneStart=Date.now(),trimOffset=(sceneStart-beforePage)/1000;
 await recordPage.screenshot({path:cover,fullPage:false});
 const schedule=[
  [0,'home','品牌与真实首页'],[5,'lifeResult','生命地图实际入口'],[7,'ziweiChart','真实紫微盘'],[9,'classicsWisdom','真实八字'],[10.7,'westernAstrology','实际星盘参考页'],
  [12,'body','身体地图'],[14,'teaLife','茶道生活'],[15.7,'chineseCare','中医养护'],[17.3,'tibetanCare','藏医养护'],
  [19,'mind','心智地图'],[21.3,'healingSpace','疗愈空间'],[23.6,'meditationStudy','禅修修习'],
  [26,'academy','智慧馆实际课程与时间银行'],[29,'academy','课程列表真实滚动'],[31.5,'timeBank','实际时间银行与计时条'],[34,'home','回到首页体验入口']
 ];
 for(const [seconds,route,label] of schedule){
  const wait=sceneStart+seconds*1000-Date.now();if(wait>0)await new Promise(r=>setTimeout(r,wait));
  await go(recordPage,route);
  if(seconds===29)await recordPage.locator('#app').evaluate(el=>el.scrollBy({top:500,behavior:'smooth'}));
  report.scenes.push({plannedStartSeconds:seconds,actualStartSeconds:(Date.now()-sceneStart)/1000,route,label,syntheticBirthDate:route==='lifeResult'?'1990-01-01':undefined});
 }
 const remaining=sceneStart+40500-Date.now();if(remaining>0)await new Promise(r=>setTimeout(r,remaining));
 const recorded=recordPage.video();await context.close();context=null;const generated=await recorded.path();assert(path.resolve(generated).startsWith(path.resolve(__dirname)+path.sep));fs.renameSync(generated,rawFile);
 // This is actual browser footage. Only timing is trimmed; no fake app frame is inserted.
 // Playwright's recorder captures CSS pixels, ignoring the screenshot DPR. Its
 // larger recording canvas adds gray padding; remove only that recorder padding.
 const stderr=execFileSync(ffmpeg,['-hide_banner','-y','-ss',trimOffset.toFixed(3),'-i',rawFile,'-t','40','-an','-vf','crop=960:540:0:0,scale=1920:1080:flags=lanczos','-c:v','libvpx','-deadline','realtime','-cpu-used','8','-b:v','3500k',master],{windowsHide:true,encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:120000});
 // Use a settled real homepage frame instead of the first transition frame.
 execFileSync(ffmpeg,['-hide_banner','-y','-ss','2','-i',master,'-frames:v','1','-c:v','png',cover],{windowsHide:true,stdio:'pipe',timeout:30000});
 void stderr;
 const chapterTimes=[['00:00.000','00:05.000'],['00:05.000','00:12.000'],['00:12.000','00:19.000'],['00:19.000','00:26.000'],['00:26.000','00:34.000'],['00:34.000','00:40.000']];
 const lines={zh:['东方智慧 与自己重新连接\n认识自己 · 修复自己 · 提升自己','生命地图\n紫微 · 星盘 · 国学智慧','身体地图\n茶道生活 · 中医养护 · 藏医养护','心智地图\n疗愈空间 · 禅修修习','智慧馆与时间银行\n学习、练习，记录投入自己的时间','从今天开始 认识东方智慧\n待审初剪 · 无旁白无音乐'],hant:['東方智慧 與自己重新連結\n認識自己 · 修復自己 · 提升自己','生命地圖\n紫微 · 星盤 · 國學智慧','身體地圖\n茶道生活 · 中醫養護 · 藏醫養護','心智地圖\n療癒空間 · 禪修修習','智慧館與時間銀行\n學習、練習，記錄投入自己的時間','從今天開始 認識東方智慧\n待審初剪 · 無旁白無音樂'],en:['Eastern Wisdom\nKnow yourself · Restore yourself · Grow yourself','Explore the Life Map\nZi Wei · Astrology · Chinese classics','Care through the Body Map\nTea life · Chinese and Tibetan wellbeing','Make room in the Mind Map\nHealing space · Meditation practice','Wisdom Hall and Time Bank\nLearn, practise and keep time for yourself','Begin with Eastern Wisdom today\nReview draft · No narration or music']};
 for(const [lang,cues] of Object.entries(lines)){const vtt='WEBVTT\n\n'+cues.map((text,i)=>(i+1)+'\n'+chapterTimes[i][0]+' --> '+chapterTimes[i][1]+'\n'+text+'\n').join('\n');const file=path.join(OUT,'东方智慧APP介绍片-待审初剪-'+lang+'.vtt');fs.writeFileSync(file,vtt);report.outputs.push(path.relative(ROOT,file));}
 const preview=path.join(OUT,'东方智慧APP介绍片-待审初剪-本地预览.html'),name=path.basename(master);
 fs.writeFileSync(preview,'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>东方智慧介绍片 待审初剪</title><style>body{margin:0;background:#102028;color:#f2eee4;font:16px/1.8 system-ui;padding:25px;max-width:1280px;margin:auto}video{display:block;width:100%;background:#081318}select{padding:8px}a{color:#e7bd7c}</style><h1>东方智慧APP介绍片 待审初剪</h1><p>仅使用真实APP界面和合成演示资料。无旁白、无音乐，未作正式成片、商用授权或iOS/Android播放验收。主片兼无字幕母版为WebM；字幕独立，可下方选择。双击文件预览时浏览器可能限制外置字幕，请通过本地静态服务打开。</p><video controls playsinline poster="'+path.basename(cover)+'" src="'+name+'">'+[['zh','zh-Hans','简体中文'],['hant','zh-Hant','繁體中文'],['en','en','English']].map(([file,lang,label])=>'<track kind="subtitles" srclang="'+lang+'" label="'+label+'" src="东方智慧APP介绍片-待审初剪-'+file+'.vtt"'+(file==='zh'?' default':'')+'>').join('')+'</video><p><label>字幕 <select id="captions"><option value="0">简体中文</option><option value="1">繁體中文</option><option value="2">English</option><option value="-1">关闭</option></select></label></p><p><a href="'+name+'" download>下载待审初剪母版</a> · <a href="'+path.basename(cover)+'" download>封面候选</a></p><script>const v=document.querySelector("video");function choose(){for(let i=0;i<v.textTracks.length;i++)v.textTracks[i].mode=i===Number(document.getElementById("captions").value)?"showing":"disabled";}document.getElementById("captions").onchange=choose;v.onloadedmetadata=choose;</script>');
 report.outputs.unshift(path.relative(ROOT,master),path.relative(ROOT,cover));report.outputs.push(path.relative(ROOT,preview));report.rawRecording=path.relative(ROOT,rawFile);report.trimOffsetSeconds=trimOffset;report.durationTargetSeconds=40;report.outputDimensions=[1920,1080];report.noNarration=true;report.noMusic=true;report.currentDiskAppSha256=sha(fs.readFileSync(path.join(ROOT,'03_当前APP','东方智慧-首页体验R4.html')));report.matchesCurrentDiskBuild=report.currentDiskAppSha256===report.recordedAppSha256;
 assert.equal(report.errors.length,0,'No JavaScript errors during real footage recording');
 for(const file of report.outputs)assert(fs.statSync(path.join(ROOT,file)).size>0);
 report.hashes=Object.fromEntries(report.outputs.map(file=>[file,sha(fs.readFileSync(path.join(ROOT,file)))]));
}
async function finish(error){if(error){report.error=error.stack||String(error);report.status='录制未完成';}await context?.close().catch(()=>{});if(error&&recordPage?.video())try{const failed=await recordPage.video().path(),target=path.join(__dirname,'负责人优化建议-介绍片失败录屏-'+runId+'.webm');if(fs.existsSync(failed)){fs.renameSync(failed,target);report.failedRaw=path.relative(ROOT,target);}}catch{}await browser?.close();if(server&&server.exitCode===null)server.kill();const logFile=path.join(__dirname,'负责人优化建议-真实介绍片待审录制.json');let runs=[];if(fs.existsSync(logFile)){const old=JSON.parse(fs.readFileSync(logFile));runs=old.runs||[old.latest||old];}runs.push(report);fs.writeFileSync(logFile,JSON.stringify({latest:report,runs},null,2));if(error){console.error(error);process.exitCode=1;}else console.log(JSON.stringify({status:report.status,outputs:report.outputs,recordedAppSha256:report.recordedAppSha256}));}
run().then(()=>finish(),error=>finish(error));
