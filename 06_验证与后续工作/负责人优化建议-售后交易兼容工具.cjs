// Shared local-only harness for the unified commerce module. No action on import.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),R4=path.join(ROOT,'04_研发源码/app/r4'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud'),WEB=path.join(ROOT,'03_当前APP');
const runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {request,chromium}=require(path.join(runtime,'node/node_modules/playwright'));
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const parsedArgs=argv=>Object.fromEntries(argv.filter(a=>a.startsWith('--')).map(a=>{const n=a.indexOf('=');return [a.slice(2,n<0?undefined:n),n<0?true:a.slice(n+1)];}));
function makeHarness(argv=process.argv.slice(2)){
 const args=parsedArgs(argv),target=String(args.target||'python');assert(['python','cloud'].includes(target),'Select --target=python|cloud');
 const moduleName=String(args.module||'负责人优化建议-统一交易'),runId=Date.now().toString(36)+'_'+crypto.randomBytes(3).toString('hex');
 assert(/^[^\\/:]+$/.test(moduleName),'Module name must be a safe filename label');
 const customReport=args.report&&String(args.report);assert(!customReport||path.basename(customReport)===customReport&&customReport.endsWith('.json'));
 const reportFile=path.join(__dirname,customReport||'负责人优化建议-交易专项-'+target+'.json');
 let base=String(args.base||'').replace(/\/$/,'');
 if(base){const u=new URL(base);assert(u.protocol==='http:'&&['127.0.0.1','localhost'].includes(u.hostname)&&u.port&&!['8880','8879','8878'].includes(u.port)&&u.pathname==='/'&&!u.username&&!u.password,'Only isolated loopback ports are accepted; user preview ports forbidden');}
 assert(target!=='cloud'||base,'Cloud requires an already-started fresh isolated local Worker via --base');
 const db=path.join(__dirname,'负责人优化建议-交易隔离-'+runId+'.sqlite3');
 const report={at:new Date().toISOString(),module:moduleName,runId,target,base,syntheticDataOnly:true,productionWrites:false,scope:'Actual isolated HTTP and browser commerce flow. Sandbox transactions remain separate from real member/media permissions.',results:[],errors:[],captures:[],traffic:[],coverage:{http:true,ui:!args['http-only'],realPayments:false,production:false},harnessSha256:{}};
 let server,browser,activePage;const contexts=[];let identity;
 const sources=['04_研发源码/app/r4/backend/after_sales.py','04_研发源码/app/cloud/lib/after-sales.ts','04_研发源码/app/r4/after-sales-ui.js','04_研发源码/app/r4/after-sales-ui.css','04_研发源码/app/r4/after-sales-admin.js','04_研发源码/app/r4/backend/commerce.py','04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/commerce-api.ts','04_研发源码/app/cloud/lib/eastern-api.ts','04_研发源码/app/r4/commerce-ui.js','04_研发源码/app/r4/commerce-ui.css','04_研发源码/app/r4/commerce-admin.js'];
 function snapshot(){return {sources:Object.fromEntries(sources.filter(n=>fs.existsSync(path.join(ROOT,n))).map(n=>[n,sha(fs.readFileSync(path.join(ROOT,n)))])),builds:Object.fromEntries(['03_当前APP/东方智慧-首页体验R4.html','03_当前APP/计时后台-开发联调.html','04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/generated/admin.html','04_研发源码/app/cloud/dist/server/index.js','04_研发源码/app/cloud/dist/server/BUILD_ID','04_研发源码/app/cloud/worker/index.ts','04_研发源码/app/cloud/public/assets/NotoSerifTibetan.woff2'].filter(n=>fs.existsSync(path.join(ROOT,n))).map(n=>[n,sha(fs.readFileSync(path.join(ROOT,n)))]))};}
 async function context(){const c=await request.newContext({timeout:20000});contexts.push(c);return c;}
 async function api(ctx,route,data,method=data===undefined?'GET':'POST',expected=200){
  const start=Date.now(),response=await ctx.fetch(base+'/api/'+route,{method,...(data===undefined?{}:{data})});let body;
  try{body=await response.json();}catch{body={error:'Non-JSON response'};}
  report.traffic.push({method,path:'/api/'+route.replace(/\?.*$/,''),status:response.status(),ms:Date.now()-start});
  if(expected!==null){const statuses=Array.isArray(expected)?expected:[expected];assert(statuses.includes(response.status()),method+' '+route+' expected '+statuses.join('/')+' got '+response.status()+(body.error?': '+String(body.error).slice(0,180):''));}
  return {status:response.status(),data:body,response};
 }
 async function check(name,fn){const start=Date.now();try{const observed=await fn();report.results.push({name,pass:true,ms:Date.now()-start,...(observed===undefined?{}:{observed})});console.log('PASS '+name);}catch(e){let screenshot;if(activePage&&!activePage.isClosed()){screenshot=moduleName+'-'+target+'-'+runId+'-失败-'+report.results.length+'.png';await activePage.screenshot({path:path.join(__dirname,screenshot),fullPage:true}).catch(()=>{});report.captures.push(screenshot);}report.results.push({name,pass:false,ms:Date.now()-start,error:e.stack||String(e),...(screenshot?{screenshot}:{})});console.log('FAIL '+name+': '+e.message);}}
 async function start(){
  if(!base){assert(!fs.existsSync(db),'Never reuse an existing QA database');server=spawn(path.join(runtime,'python/python.exe'),['-B',path.join(R4,'backend/server.py'),'--port','0','--db',db,'--web-root',WEB],{cwd:ROOT,windowsHide:true,stdio:['ignore','pipe','pipe']});base=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error('Fresh isolated Python service start timeout')),20000);server.stdout.on('data',d=>{output+=d;const m=output.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/);if(m){clearTimeout(timer);resolve(m[1]);}});server.stderr.on('data',d=>{output+=d;});server.once('exit',code=>{clearTimeout(timer);reject(Error('Isolated Python exited '+code));});});report.ownedDatabase=path.relative(ROOT,db).split(path.sep).join('/');}
  report.base=base;identity=snapshot();report.identity=identity;
  report.harnessSha256=Object.fromEntries([__filename,process.argv[1],process.env.AFTER_SALES_COMPAT_LAUNCHER].filter(f=>f&&fs.existsSync(f)).map(f=>[path.relative(ROOT,f).split(path.sep).join('/'),sha(fs.readFileSync(f))]));
  const anonymous=await context(),health=await api(anonymous,'health');assert.equal(health.data.ok,true);assert.equal(health.data.deployment==='cloud',target==='cloud','The provided service matches --target');
  const expected=path.join(ROOT,target==='cloud'?'04_研发源码/app/cloud/generated/experience.html':'03_当前APP/东方智慧-首页体验R4.html'),served=await anonymous.get(base+'/experience');assert.equal(served.status(),200);assert.equal(sha(await served.body()),sha(fs.readFileSync(expected)),'The actual service serves the current target build');report.servedBuildSha256=sha(await served.body());
 }
 async function seed(){
  const admin=await context(),user=await context(),other=await context(),anonymous=await context(),pass=crypto.randomBytes(22).toString('hex');
  const status=await api(admin,'auth/status');
  if(status.data.setupRequired){await api(admin,'auth/setup',{username:'commerce_admin_'+runId.slice(0,14),password:pass,name:'交易隔离管理员'});}
  else{const password=process.env.AFTER_SALES_COMPAT_TEST_PASSWORD;assert(password,'Fresh owned Cloud fixture credentials must be provided by the compatibility launcher');await api(admin,'auth/login',{username:'demo_admin',password});}
  const owner=(await api(admin,'auth/status')).data.user;assert.equal(owner.role,'admin');
  const first=(await api(user,'auth/register',{username:'co_a_'+runId.slice(0,20),password:pass,name:'交易合成买家A'})).data.user;
  const second=(await api(other,'auth/register',{username:'co_b_'+runId.slice(0,20),password:pass,name:'交易合成买家B'})).data.user;
  return {admin,user,other,anonymous,owner,first,second};
 }
 async function browserContext(storageState){browser=browser||await chromium.launch({headless:true});const c=await browser.newContext({storageState,viewport:{width:390,height:844},reducedMotion:'reduce'});const p=await c.newPage();activePage=p;p.on('pageerror',e=>report.errors.push(e.message));return {context:c,page:p};}
 async function capture(page,label){const file=moduleName+'-'+target+'-'+runId+'-'+label+'.png';await page.screenshot({path:path.join(__dirname,file),fullPage:true});report.captures.push(file);return file;}
 async function finish(fatal){
  if(fatal){report.results.push({name:'交易专项环境与执行',pass:false,error:fatal.stack||String(fatal)});console.log('FAIL '+fatal.message);}
  if(identity){const final=snapshot();report.identityUnchanged=JSON.stringify(final)===JSON.stringify(identity);if(!report.identityUnchanged)report.results.push({name:'源构建在专项期间保持同一身份',pass:false,error:'Sources or builds changed during the test'});}
  if(report.errors.length)report.results.push({name:'浏览器无运行错误',pass:false,error:report.errors.join('\n')});
  await browser?.close();for(const c of contexts)await c.dispose().catch(()=>{});
  if(server&&server.exitCode===null){const ended=new Promise(r=>server.once('exit',r));server.kill();await ended;}
  report.pass=report.results.length>0&&report.results.every(r=>r.pass);report.passed=report.results.filter(r=>r.pass).length;report.failed=report.results.filter(r=>!r.pass).length;
  // Keep failed runs and the fresh QA DB for diagnosis; never overwrite a prior run.
  let runs=[];if(fs.existsSync(reportFile)){const old=JSON.parse(fs.readFileSync(reportFile,'utf8'));runs=old.runs||[old.latest||old];}runs.push(report);fs.writeFileSync(reportFile,JSON.stringify({latest:report,runs},null,2)+'\n');console.log(JSON.stringify({module:moduleName,target,pass:report.pass,passed:report.passed,failed:report.failed,report:reportFile}));process.exitCode=report.pass?0:1;
 }
 return {args,target,moduleName,runId,report,api,check,start,seed,context,browserContext,capture,finish,get base(){return base;},get page(){return activePage;},ROOT,R4,CLOUD,WEB,sha};
}
module.exports={makeHarness};
