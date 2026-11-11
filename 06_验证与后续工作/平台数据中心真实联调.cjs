// Real loopback HTTP/browser acceptance. No production endpoint or dataset is used.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto'),{spawn}=require('child_process');
const {chromium,request}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4'),web=path.join(root,'03_当前APP');
const python=path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
const cloud=process.argv.includes('--cloud'),runId=Date.now().toString(36),db=path.join(__dirname,'平台数据真实联调-'+runId+'.sqlite3');
const checks=[],errors=[],telemetry=[],layouts=[];let base,server,browser,admin,reader,anon;
const reportFile=path.join(__dirname,'平台数据中心真实联调-'+(cloud?'云端':'本机')+'.json');
const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(Date.now());
const query='?start='+today+'&end='+today+'&grain=day';
function appendReport(value){let runs=[];if(fs.existsSync(reportFile))try{runs=JSON.parse(fs.readFileSync(reportFile,'utf8')).runs||[]}catch{}runs.push(value);fs.writeFileSync(reportFile,JSON.stringify({latest:value,runs},null,2));}
async function call(ctx,route,data,method='POST',expected=200){const r=await ctx.fetch(base+'/api/'+route,{method,data}),d=await r.json();assert.equal(r.status(),expected,route+' '+JSON.stringify(d));return d;}
async function stats(){return call(admin,'admin/analytics'+query,undefined,'GET');}
async function step(name,fn){await fn();checks.push(name);console.log('PASS '+name);}
async function layout(page,width,name){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),name+' overflow '+width);layouts.push({width,name,pass:true});}
async function main(){
 if(cloud)base='http://127.0.0.1:8877';
 else{
  server=spawn(python,['-B',path.join(r4,'backend/server.py'),'--port','0','--db',db,'--web-root',web],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
  base=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Local service startup timed out')),15000);server.stdout.on('data',c=>{out+=c;const m=out.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/);if(m){clearTimeout(timer);resolve(m[1]);}});server.stderr.on('data',c=>out+=c);server.on('exit',code=>{clearTimeout(timer);reject(Error('Local service exited '+code+': '+out));});});
 }
 assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
 admin=await request.newContext();reader=await request.newContext();anon=await request.newContext();
 const pass=crypto.randomBytes(20).toString('hex'),username='data_ui_'+runId;
 if(cloud)await call(admin,'auth/login',JSON.parse(fs.readFileSync(path.join(root,'04_研发源码/app/cloud/.env.local-test'),'utf8')));
 else await call(admin,'auth/setup',{username:'data_admin',password:pass,name:'隔离管理员'});
 const before=await stats();
 await call(reader,'auth/register',{username,password:pass,name:'隔离数据联调学员'});
 browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'}),page=await context.newPage();
 page.on('pageerror',e=>errors.push('app: '+e.message));
 page.on('request',req=>{if(new URL(req.url()).pathname==='/api/analytics/activity'){const payload=req.postDataJSON();telemetry.push({method:req.method(),payload});}});
 await step('匿名APP不采集，实际账号登录后仅发送功能标识和事件种类',async()=>{
  await page.goto(base+'/experience?page=account');await page.waitForFunction(()=>px.loaded);await page.locator('#px-account-form').waitFor();assert.equal(telemetry.length,0);
  await page.locator('#px-account-form [name=username]').fill(username);await page.locator('#px-account-form [name=password]').fill(pass);await page.locator('#px-account-form button[value=login]').click();await page.waitForFunction(name=>px.user?.username===name,username);
  await page.waitForFunction(()=>typeof ewAnalyticsReport==='function'&&!ewAnalyticsTelemetry.pending);await page.evaluate(()=>navigate('home'));await page.evaluate(()=>ewAnalyticsReport('visit'));await page.waitForFunction(()=>!ewAnalyticsTelemetry.pending);
  assert(telemetry.length>0);for(const event of telemetry){assert.equal(event.method,'POST');assert.deepEqual(Object.keys(event.payload).sort(),['feature','kind']);assert.equal(typeof event.payload.feature,'string');assert(['visit','heartbeat'].includes(event.payload.kind));}
 });
 const usedFeatures=[];
 await step('首页、地图、智慧馆和社群等实际页面采集去重账号活跃',async()=>{
  for(const route of ['home','lifeResult','body','mind','academy','community','service','profile']){
   await page.waitForFunction(()=>!ewAnalyticsTelemetry.pending);const feature=await page.evaluate(async route=>{navigate(route);await ewAnalyticsReport('visit');return ewAnalyticsFeature();},route);await page.waitForFunction(()=>!ewAnalyticsTelemetry.pending);usedFeatures.push(feature);
  }
  const after=await stats();for(const key of ['day','week','month','year'])assert.equal(after.windows[key].activeUsers,(before.windows[key].activeUsers||0)+1,key+' account dedup');assert.equal(after.summary.activeUsers,(before.summary.activeUsers||0)+1);assert.equal(after.summary.newUsers,before.summary.newUsers+1);
  for(const feature of new Set(usedFeatures)){const row=after.features.find(x=>x.id===feature);assert(row&&row.activeUsers>=1,feature+' feature usage');}
  assert.equal(after.timezone,'Asia/Shanghai');assert.equal(after.range.start,today);assert.equal(after.range.end,today);assert.equal(after.trend.length,1);assert.equal(after.trend[0].activeUsers,after.summary.activeUsers);
 });
 await step('连续访问同功能30秒内去重，心跳维持活跃但不增加访问量',async()=>{
  const feature=usedFeatures.at(-1),a=await stats();await call(reader,'analytics/activity',{feature,kind:'visit'});await call(reader,'analytics/activity',{feature,kind:'visit'});await call(reader,'analytics/activity',{feature,kind:'heartbeat'});const b=await stats();assert.equal(b.summary.visits,a.summary.visits);assert.equal(b.summary.activeUsers,a.summary.activeUsers);
  await call(anon,'analytics/activity',{feature,kind:'visit'},'POST',401);await call(reader,'analytics/activity',{feature:'private-body-notes',kind:'visit'},'POST',400);
  await call(reader,'analytics/activity',{feature,kind:'unknown'},'POST',400);
 });
 await step('后台管理访问不计入用户活跃，统计只供管理员和运营读取',async()=>{
  await call(reader,'admin/analytics'+query,undefined,'GET',403);await call(anon,'admin/analytics'+query,undefined,'GET',401);
  const a=await stats();await call(admin,'analytics/activity',{feature:'home',kind:'visit'});
  const staffContext=await browser.newContext({storageState:await admin.storageState(),reducedMotion:'reduce'}),staffPage=await staffContext.newPage();let staffRequests=0;staffPage.on('request',r=>{if(new URL(r.url()).pathname==='/api/analytics/activity')staffRequests++;});await staffPage.goto(base+'/experience?page=academy');await staffPage.waitForFunction(()=>px.loaded);await staffPage.evaluate(()=>ewAnalyticsReport('visit'));assert.equal(staffRequests,0);await staffContext.close();
  const b=await stats();assert.equal(b.summary.activeUsers,a.summary.activeUsers);assert.equal(b.summary.visits,a.summary.visits);
  for(const role of ['operator','reviewer','teacher']){const c=await request.newContext();try{const account=await call(c,'auth/register',{username:'data_'+role+'_'+runId,password:pass,name:'隔离角色'});await call(admin,'admin/users/'+account.user.id,{role},'PATCH');await call(c,'auth/login',{username:'data_'+role+'_'+runId,password:pass});await call(c,'admin/analytics'+query,undefined,'GET',role==='operator'?200:403);if(role==='teacher'){const x=await stats();await call(c,'analytics/activity',{feature:'academy',kind:'visit'});const y=await stats();assert.equal(y.summary.activeUsers,x.summary.activeUsers+1);}}finally{await c.dispose();}}
 });
 const ac=await browser.newContext({storageState:await admin.storageState(),viewport:{width:1440,height:1000},reducedMotion:'reduce'}),ap=await ac.newPage();ap.on('pageerror',e=>errors.push('admin: '+e.message));
 await step('管理后台实际导航、日期筛选、日周月年粒度和CSV下载',async()=>{
  await ap.goto(base+'/admin');await ap.locator('[data-nav=analytics]').click();await ap.locator('#analytics-filter').waitFor();await ap.waitForFunction(()=>state.analytics?.trend);
  await ap.locator('#analytics-filter [name=start]').fill(today);await ap.locator('#analytics-filter [name=end]').fill(today);
  for(const grain of ['day','week','month','year']){await ap.locator('#analytics-filter [name=grain]').selectOption(grain);await ap.locator('#analytics-filter button').first().click();await ap.waitForFunction(({day,grain})=>state.analytics?.range?.start===day&&state.analytics?.range?.end===day&&state.analytics?.range?.grain===grain,{day:today,grain});assert.equal(await ap.locator('#analytics-filter [name=grain]').inputValue(),grain);}
  const d=ap.waitForEvent('download');await ap.locator('[data-action=analytics-export]').click();const download=await d;assert(download.suggestedFilename().endsWith('.csv'));const csv=fs.readFileSync(await download.path(),'utf8');assert(csv.includes(today));assert(/活跃|访问/.test(csv));assert(!csv.includes(username)&&!csv.includes(pass),'export must contain only aggregate data');assert(!csv.includes('NaN')&&!csv.includes('Infinity'));
  for(const width of [1440,390,360])await layout(ap,width,'analytics');await ap.setViewportSize({width:1440,height:1000});await ap.screenshot({path:path.join(__dirname,(cloud?'云端-':'本机-')+'平台数据中心-桌面.png'),fullPage:true});await ap.setViewportSize({width:390,height:844});await ap.screenshot({path:path.join(__dirname,(cloud?'云端-':'本机-')+'平台数据中心-手机.png'),fullPage:true});
 });
 await step('非法日期区间显示错误并清除旧统计，可重置查询恢复',async()=>{
  const previous=new Date(Date.parse(today+'T00:00:00Z')-86400000).toISOString().slice(0,10);await ap.locator('#analytics-filter [name=start]').fill(today);await ap.locator('#analytics-filter [name=end]').fill(previous);await ap.locator('#analytics-filter button').first().click();await ap.locator('[data-an-reset]').waitFor();assert.equal(await ap.evaluate(()=>state.analytics),null);assert.equal(await ap.locator('[data-action=analytics-export]').count(),0);await ap.locator('[data-an-reset]').click();await ap.locator('#analytics-filter').waitFor();await ap.waitForFunction(()=>state.analytics?.trend);assert(await ap.locator('.an-chart').count()>0);
 });
 await step('未采集历史保留缺数状态，留存无完整观察样本显示未形成',async()=>{
  const first=new Date(Date.parse((await stats()).collectedSince)+8*3600000).toISOString().slice(0,10),previous=new Date(Date.parse(first+'T00:00:00Z')-86400000).toISOString().slice(0,10);
  const past=await call(admin,'admin/analytics?start='+previous+'&end='+previous+'&grain=day',undefined,'GET');assert.equal(past.summary.activeUsers,null);assert.equal(past.summary.visits,null);assert.equal(past.summary.coverage,'uncollected');assert(past.features.every(x=>x.activeUsers===null&&x.visits===null));
  const current=await stats();for(const row of current.retention){assert([1,7].includes(row.days));assert(row.rate===null||row.rate>=0&&row.rate<=100);if(!row.eligibleUsers)assert.equal(row.rate,null);}
  await ap.locator('#analytics-filter [name=start]').fill(previous);await ap.locator('#analytics-filter [name=end]').fill(previous);await ap.locator('#analytics-filter button').first().click();await ap.waitForFunction(()=>state.analytics?.summary?.coverage==='uncollected');assert((await ap.locator('#main').innerText()).includes('未采集'));assert.equal(await ap.locator('.an-chart').count(),0,'uncollected interval must not draw a fabricated zero line');
 });
 assert.deepEqual(errors,[]);await ac.close();await context.close();
 appendReport({at:new Date().toISOString(),pass:true,mode:cloud?'cloud':'python',scope:'Actual loopback HTTP and browser; isolated synthetic accounts only, no production activity',checks,layouts,errors,telemetryPayloadKeys:[...new Set(telemetry.flatMap(x=>Object.keys(x.payload)))].sort(),features:[...new Set(usedFeatures)],sourceHashes:Object.fromEntries(['04_研发源码/app/r4/analytics-app.js','04_研发源码/app/r4/analytics-admin.js','04_研发源码/app/r4/backend/analytics.py','04_研发源码/app/cloud/lib/analytics-api.ts'].filter(name=>fs.existsSync(path.join(root,name))).map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex')])),buildHashes:Object.fromEntries(['东方智慧-首页体验R4.html','计时后台-开发联调.html'].map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(web,name))).digest('hex')]))});
 console.log(JSON.stringify({pass:true,checks:checks.length,mode:cloud?'cloud':'python',report:reportFile}));
}
(async()=>{try{await main();}catch(e){appendReport({at:new Date().toISOString(),pass:false,mode:cloud?'cloud':'python',checks,layouts,errors,error:e.stack||e.message});console.error(e.stack);process.exitCode=1;}finally{await browser?.close();await admin?.dispose();await reader?.dispose();await anon?.dispose();if(server){const ended=new Promise(r=>server.once('exit',r));server.kill();await ended;}for(const suffix of ['','-wal','-shm']){const target=db+suffix;assert.equal(path.dirname(target),__dirname);if(fs.existsSync(target))fs.unlinkSync(target);}}})();
