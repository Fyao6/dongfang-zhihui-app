'use strict';
// Prepared only: execute after B11 integration + new APP/Cloud builds + parent's module gates.
// Starts an owned random SQLite or D1/R2 service; never connects to a supplied existing base URL.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),net=require('node:net'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),R4=path.join(ROOT,'04_研发源码/app/r4'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud'),runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {chromium,request}=require(path.join(runtime,'node/node_modules/playwright'));
const argv=Object.fromEntries(process.argv.slice(2).map(s=>{const i=s.indexOf('=');return [s.slice(2,i<0?undefined:i),i<0?true:s.slice(i+1)];}));
const target=String(argv.target||'python');assert(['python','cloud'].includes(target));assert(!argv.base,'Only owned fresh test services are permitted');
const runId=Date.now().toString(36)+'_'+crypto.randomBytes(3).toString('hex'),adminPass=crypto.randomBytes(24).toString('hex');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),freePort=()=>new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});
const names=['04_研发源码/app/r4/bazi-result-version.js','04_研发源码/app/r4/bazi-result-version-ui.js','04_研发源码/app/r4/bazi-result-version-release.js','04_研发源码/app/r4/bazi-result-version.css','04_研发源码/app/r4/life-chart-core.js','04_研发源码/app/r4/life-chart-bazi.js','04_研发源码/app/r4/life-chart-bazi-layout.js','04_研发源码/app/r4/life-birth-entry.js','04_研发源码/app/r4/life-western-profile.js','04_研发源码/app/r4/bazi-time.js','04_研发源码/app/r4/vendor/lunar-1.7.7.js','04_研发源码/app/r4/base.js','04_研发源码/app/r4/build.py','04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/eastern-api.ts','03_当前APP/东方智慧-首页体验R4.html','04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/dist/server/index.js','04_研发源码/app/cloud/public/assets/NotoSerifTibetan.woff2','06_验证与后续工作/负责人优化建议-B11实际专项.cjs','06_验证与后续工作/负责人优化建议-B11浏览器专项.cjs','06_验证与后续工作/负责人优化建议-B11Python测试服务.py','06_验证与后续工作/负责人优化建议-B11Cloud测试服务.ts'];
const identity=()=>Object.fromEntries(names.map(n=>[n,sha(fs.readFileSync(path.join(ROOT,n)))])),before=identity();
const buildName=target==='python'?'03_当前APP/东方智慧-首页体验R4.html':'04_研发源码/app/cloud/generated/experience.html',expected=fs.readFileSync(path.join(ROOT,buildName));
assert(expected.includes(Buffer.from('root.BAZI_RELEASE_MANIFEST'))&&expected.includes(Buffer.from('root.BaziVersionUI.install')),'B11 must be integrated into the actual current build before this test runs');
const report={at:new Date().toISOString(),target,runId,syntheticDataOnly:true,realAIRequests:0,productionWrites:false,sourceBuildTestHashes:before,results:[],captures:[],errors:[],traffic:[],limits:['Teacher rules and reference cases unavailable; actual adapter checks are not professional validation.','The late-account fixture holds real browser SHA256, not a mocked provider response.','No app database, existing service or external provider is used.']};
const contexts=[],browsers=[];let base,child,activePage,finishing;
async function apiContext(){const c=await request.newContext({timeout:30000});contexts.push(c);return c;}
async function api(c,route,data,method=data===undefined?'GET':'POST',expectedStatus=200){const r=await c.fetch(base+'/api/'+route,{method,...(data===undefined?{}:{data})});const d=await r.json();report.traffic.push({method,path:'/api/'+route.replace(/\?.*$/,''),status:r.status()});assert.equal(r.status(),expectedStatus,route+': '+(d.error||r.status()));return d;}
async function register(label){const c=await apiContext(),credential={username:'bz_'+label+'_'+runId.slice(0,16),password:crypto.randomBytes(20).toString('hex'),name:'B11 合成 '+label};credential.id=(await api(c,'auth/register',credential)).user.id;return {c,credential};}
async function browserContext(storageState){const browser=await chromium.launch({headless:true});browsers.push(browser);const context=await browser.newContext({storageState,viewport:{width:390,height:844},reducedMotion:'reduce',acceptDownloads:true}),page=await context.newPage();activePage=page;page.on('pageerror',e=>report.errors.push(e.message));page.on('response',r=>{const u=new URL(r.url());if(u.origin===base&&u.pathname.startsWith('/api/'))report.traffic.push({kind:'browser',method:r.request().method(),path:u.pathname,status:r.status()});});return {browser,context,page};}
async function capture(page,label){const name='负责人优化建议-B11-'+target+'-'+runId+'-'+label+'.png';await page.screenshot({path:path.join(__dirname,name),fullPage:true});report.captures.push(name);}
async function check(name,fn){try{await fn();report.results.push({name,pass:true});console.log('PASS '+name);}catch(e){report.results.push({name,pass:false,error:e.stack||e.message});if(activePage&&!activePage.isClosed())await capture(activePage,'失败'+report.results.length).catch(()=>{});console.log('FAIL '+name+': '+e.message);}}
async function start(){
 if(target==='python'){
  const db=path.join(__dirname,'负责人优化建议-B11HTTP隔离-'+runId+'.sqlite3');assert(!fs.existsSync(db));report.ownedDatabase=path.relative(ROOT,db);
  child=spawn(path.join(runtime,'python/python.exe'),['-B',path.join(__dirname,'负责人优化建议-B11Python测试服务.py'),'--db',db],{cwd:ROOT,windowsHide:true,stdio:['ignore','pipe','pipe']});
 }else{
  const name='bz'+crypto.randomBytes(4).toString('hex'),state=path.join(CLOUD,'.wrangler',name),cfgDir=path.join(CLOUD,'.wrangler',name+'c');assert(!fs.existsSync(state)&&!fs.existsSync(cfgDir));fs.mkdirSync(cfgDir,{recursive:true});
  const salt=crypto.randomBytes(16),hash=salt.toString('hex')+':'+crypto.pbkdf2Sync(adminPass,salt,100000,32,'sha256').toString('hex');
  const cfg={name:'b11-isolated-qa',assets:{directory:path.join(CLOUD,'public'),binding:'ASSETS',run_worker_first:true},main:path.join(__dirname,'负责人优化建议-B11Cloud测试服务.ts'),compatibility_date:'2026-05-15',compatibility_flags:['nodejs_compat'],vars:{DEMO_ADMIN_HASH:hash},d1_databases:[{binding:'DB',database_name:'b11-qa',database_id:'00000000-0000-4000-8000-000000000000'}],r2_buckets:[{binding:'BUCKET',bucket_name:'b11-qa'}],rules:[{type:'Text',globs:['**/*.html','**/*.sql'],fallthrough:true}]};
  const file=path.join(cfgDir,'wrangler.json');fs.writeFileSync(file,JSON.stringify(cfg));base='http://127.0.0.1:'+await freePort();report.ownedState=path.relative(ROOT,state);
  child=spawn(process.execPath,['--import','./scripts/sites-env.mjs','./node_modules/wrangler/bin/wrangler.js','dev','--config',file,'--local','--persist-to',state,'--ip','127.0.0.1','--port',new URL(base).port,'--inspector-port','0'],{cwd:CLOUD,windowsHide:true,stdio:['ignore','pipe','pipe'],env:{...process.env,WRANGLER_SEND_METRICS:'false',CI:'1',NO_COLOR:'1'}});
 }
 let output='',startError;child.stdout.on('data',b=>{output+=b;const m=output.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/);if(m&&target==='python')base=m[1];});child.stderr.on('data',()=>{});child.once('error',e=>startError=e);
 const probe=await apiContext();let ready=false;
 for(let i=0;i<220;i++){if(startError||child.exitCode!==null)throw Error('Owned B11 service exited before ready');if(base)try{const r=await probe.get(base+'/api/health',{timeout:600});if(r.ok()){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,150));}
 assert(ready,'B11 fresh service startup timed out');report.base=base;
 assert.equal(sha(await(await probe.get(base+'/experience')).body()),sha(expected));report.servedBuildSha256=sha(expected);if(target==='cloud'){const f=await probe.get(base+'/assets/NotoSerifTibetan.woff2'),bytes=await f.body();assert.equal(f.status(),200);assert.equal(sha(bytes),sha(fs.readFileSync(path.join(CLOUD,'public/assets/NotoSerifTibetan.woff2'))));report.fontAsset={status:f.status(),bytes:bytes.length,sha256:sha(bytes)};}
 const admin=await apiContext();await api(admin,target==='python'?'auth/setup':'auth/login',{username:target==='python'?'b11_admin_'+runId.slice(0,12):'demo_admin',password:adminPass,name:'B11 隔离管理员'});
}
async function finish(fatal){
 if(finishing)return finishing;
 finishing=(async()=>{
  if(fatal)report.results.push({name:'B11专项执行环境',pass:false,error:fatal.stack||String(fatal)});
  for(const b of browsers)await b.close().catch(()=>{});for(const c of contexts)await c.dispose().catch(()=>{});
  if(child&&child.exitCode===null){if(target==='cloud'&&process.platform==='win32')await new Promise(resolve=>{const p=spawn(path.join(process.env.SystemRoot||'C:\\Windows','System32/taskkill.exe'),['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});p.once('exit',resolve);p.once('error',resolve);});else child.kill();}
  report.identityUnchanged=JSON.stringify(before)===JSON.stringify(identity());if(!report.identityUnchanged)report.results.push({name:'运行期间源码构建与测试身份一致',pass:false});
  if(report.errors.length)report.results.push({name:'浏览器无运行错误',pass:false,error:report.errors.join('\n')});
  report.passed=report.results.filter(x=>x.pass).length;report.failed=report.results.filter(x=>!x.pass).length;report.pass=report.passed>0&&!report.failed;
  const file=path.join(__dirname,'负责人优化建议-B11实际专项-'+target+'.json');let runs=[];if(fs.existsSync(file)){const old=JSON.parse(fs.readFileSync(file,'utf8'));runs=old.runs||[old.latest||old];}runs.push(report);fs.writeFileSync(file,JSON.stringify({latest:report,runs},null,2)+'\n');
  console.log(JSON.stringify({target,pass:report.pass,passed:report.passed,failed:report.failed,report:file}));process.exitCode=report.pass?0:1;
 })();return finishing;
}
(async()=>{try{await start();await require('./负责人优化建议-B11浏览器专项.cjs')({check,capture,register,browserContext,get base(){return base;}});await finish();}catch(e){await finish(e);}})();

