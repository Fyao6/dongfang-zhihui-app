'use strict';
// Sole local launcher: new owned SQLite/D1/R2, random secrets, independent real HTTP/SSE upstream.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),net=require('node:net'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud'),moduleName='负责人优化建议-任务告警额度兼容';
const runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies'),python=process.env.EW_PYTHON||path.join(runtime,'python/python.exe');
const {request}=require(path.join(runtime,'node/node_modules/playwright'));
const {bundleCloud}=require('./负责人优化建议-任务告警测试工具.cjs'),runtimeArtifacts=[];
const args=Object.fromEntries(process.argv.slice(2).filter(s=>s.startsWith('--')).map(s=>{const n=s.indexOf('=');return [s.slice(2,n<0?undefined:n),n<0?true:s.slice(n+1)];}));
const target=args.target||'python',suite=args.suite||'special';assert(['python','cloud'].includes(target));assert(['special','full','compat','visual','member-compat','gateway-compat'].includes(suite));assert(!args.base,'Only newly owned state is accepted');
const runId=Date.now().toString(36)+'-'+crypto.randomBytes(4).toString('hex'),qaName='member-quota-'+runId,sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const identity=()=>Object.fromEntries([
 '04_研发源码/app/r4/backend/membership_ai_quota.py','04_研发源码/app/cloud/lib/membership-ai-quota.ts','04_研发源码/app/r4/backend/ai_gateway.py','04_研发源码/app/cloud/lib/ai-gateway.ts',
 '04_研发源码/app/r4/backend/membership_lifecycle.py','04_研发源码/app/cloud/lib/membership-lifecycle.ts','04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/eastern-api.ts',
 '04_研发源码/app/r4/membership-lifecycle-ui.css','04_研发源码/app/r4/ai-gateway-ui.css',
 '04_研发源码/app/r4/commerce-ui.js','04_研发源码/app/r4/account-closure.js',
 '03_当前APP/东方智慧-首页体验R4.html','03_当前APP/计时后台-开发联调.html','04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/generated/admin.html','04_研发源码/app/cloud/dist/server/index.js',
 ...fs.readdirSync(__dirname).filter(n=>n.startsWith(moduleName)&&/\.(cjs|py|ts|sql)$/.test(n)).map(n=>'06_验证与后续工作/'+n)
].filter(n=>fs.existsSync(path.join(ROOT,n))).map(n=>[n,sha(fs.readFileSync(path.join(ROOT,n)))]));
const freePort=()=>new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});
function readyProcess(proc,pattern,label){return new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error(label+' startup timeout')),30000);proc.stdout.on('data',data=>{output+=data;const m=pattern.exec(output);if(m){clearTimeout(timer);resolve(m[1]);}});proc.stderr.on('data',()=>{});proc.once('error',e=>{clearTimeout(timer);reject(e);});proc.once('exit',code=>{clearTimeout(timer);reject(Error(label+' exited '+code));});});}
async function kill(proc){if(!proc||proc.exitCode!==null)return;if(process.platform==='win32')await new Promise(resolve=>{const child=spawn(path.join(process.env.SystemRoot||'C:\\Windows','System32/taskkill.exe'),['/PID',String(proc.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});child.once('exit',resolve);child.once('error',resolve);});else proc.kill();}
// Bind only a report produced by this exact child invocation. A stale report is
// retained byte for byte; any malformed/nonfresh child candidate is kept separately.
function bindFreshReport({reportFile,priorBytes,previousTag,testStarted,metadata,diagnosticFile}){
 const currentBytes=fs.existsSync(reportFile)?fs.readFileSync(reportFile):null;let report,current,observedTag=null;
 try{if(currentBytes){report=JSON.parse(currentBytes.toString('utf8'));current=report.latest||report;observedTag=JSON.stringify([current.at,current.runId??null]);}}catch{}
 const bytesChanged=!!currentBytes&&(!priorBytes||!currentBytes.equals(priorBytes)),tagChanged=!!current&&observedTag!==previousTag,atValid=!!current&&Number.isFinite(Date.parse(current.at))&&Date.parse(current.at)>=testStarted;
 if(!bytesChanged||!tagChanged||!atValid){
  let childCandidate=null;if(priorBytes&&currentBytes&&!currentBytes.equals(priorBytes)){childCandidate=diagnosticFile+'.child-report.json';fs.writeFileSync(childCandidate,currentBytes);}
  if(priorBytes&&(!currentBytes||!currentBytes.equals(priorBytes)))fs.writeFileSync(reportFile,priorBytes);
  fs.writeFileSync(diagnosticFile,JSON.stringify({at:new Date().toISOString(),pass:false,reason:'child_report_not_fresh',reportFreshForInvocation:false,originalReportPreserved:priorBytes?fs.existsSync(reportFile)&&fs.readFileSync(reportFile).equals(priorBytes):true,report:path.relative(ROOT,reportFile),childCandidate:childCandidate?path.relative(ROOT,childCandidate):null,bytesChanged,tagChanged,atValid,invocationStarted:new Date(testStarted).toISOString(),childExitCode:metadata.childExitCode,runtimeArtifacts:metadata.runtimeArtifacts,runId:metadata.runId},null,2)+'\n');
  return false;
 }
 current.membershipQuotaLauncher={...metadata,reportFreshForInvocation:true,invocationStarted:new Date(testStarted).toISOString()};if(report.runs?.length)report.runs[report.runs.length-1]=current;fs.writeFileSync(reportFile,JSON.stringify(report,null,2)+'\n');return true;
}
module.exports={bindFreshReport};
let server,upstream,http,privateVars;
if(require.main===module)(async()=>{
 try{
  const token=crypto.randomBytes(32).toString('hex'),secret=crypto.randomBytes(32).toString('hex');
  const env={...process.env,MEMBER_QUOTA_TEST_TOKEN:token,MEMBER_QUOTA_PROVIDER_SECRET:secret,EW_AI_GATEWAY_QA_ALPHA:secret,EW_AI_GATEWAY_QA_BETA:secret,EW_DEVICE_REGRESSION_CANARY:'regression-secret-not-for-real-use'};
  upstream=spawn(python,['-B',path.join(__dirname,moduleName+'HTTP流式夹具.py')],{cwd:ROOT,env,windowsHide:true,stdio:['ignore','pipe','pipe']});
  env.MEMBER_QUOTA_FIXTURE_ENDPOINT=await readyProcess(upstream,/MEMBER_QUOTA_FIXTURE: (http:\/\/127\.0\.0\.1:\d+\/member-quota-fixture)/,'independent SSE fixture');
  const label=suite==='special'?'专项':suite==='visual'?'补充视觉':suite==='compat'?'交易兼容':suite==='member-compat'?'会员兼容':'网关兼容';
  let reportName=suite==='full'?moduleName+'-'+(target==='python'?'本轮':'公网适配')+'全量回归结果.json':moduleName+label+'-'+target+'.json';
  let testArgs=suite==='full'?[path.join(__dirname,target==='python'?'全量回归.cjs':'公网适配全量回归.cjs'),'--module='+moduleName,'--bazi-stage=4',...(target==='python'?['--admin']:[])]:[path.join(__dirname,suite==='compat'?'负责人优化建议-交易专项.cjs':moduleName+label+'.cjs'),'--target='+target,'--module='+moduleName+label,'--report='+reportName,...(suite==='member-compat'?['--compat=membership']:suite==='gateway-compat'?['--compat=gateway']:[]),...(args['http-only']?['--http-only']:[])];
  if(suite==='full')for(const name of fs.readdirSync(__dirname).filter(n=>n.startsWith(moduleName+'-'+target+'-')&&/\.(png|webm)$/.test(n)))fs.copyFileSync(path.join(__dirname,name),path.join(__dirname,moduleName+'-full前存-'+runId+'-'+name));
  if(target==='cloud'){
   const state=path.resolve(CLOUD,'.wrangler',qaName);assert(state.startsWith(path.resolve(CLOUD,'.wrangler')+path.sep)&&!fs.existsSync(state));fs.mkdirSync(state,{recursive:true});
   const password=crypto.randomBytes(24).toString('hex'),salt=crypto.randomBytes(16),hash=salt.toString('hex')+':'+crypto.pbkdf2Sync(password,salt,100000,32,'sha256').toString('hex');
   const compiled=await bundleCloud(path.join(__dirname,moduleName+'Cloud测试服务.ts'),path.join(state,'fixture-entry.mjs'));runtimeArtifacts.push(compiled);const config={name:'member-quota-isolated-qa',main:path.join(ROOT,compiled.bundle),compatibility_date:'2026-05-15',compatibility_flags:['nodejs_compat'],assets:{directory:path.join(CLOUD,'public'),binding:'ASSETS',run_worker_first:true},d1_databases:[{binding:'DB',database_name:'member-quota-isolated-db',database_id:'00000000-0000-4000-8000-000000000000'}],r2_buckets:[{binding:'BUCKET',bucket_name:'member-quota-isolated-bucket'}],rules:[{type:'Text',globs:['**/*.html','**/*.sql'],fallthrough:true}]};
   const file=path.join(state,'wrangler.json');fs.writeFileSync(file,JSON.stringify(config,null,2)+'\n');
   const vars={DEMO_ADMIN_HASH:hash,MEMBER_QUOTA_TEST_TOKEN:token,MEMBER_QUOTA_PROVIDER_SECRET:secret,MEMBER_QUOTA_FIXTURE_ENDPOINT:env.MEMBER_QUOTA_FIXTURE_ENDPOINT,EW_AI_GATEWAY_QA_ALPHA:secret,EW_AI_GATEWAY_QA_BETA:secret,EW_DEVICE_REGRESSION_CANARY:'regression-secret-not-for-real-use'};
   privateVars=path.join(state,'.dev.vars');fs.writeFileSync(privateVars,Object.entries(vars).map(([k,v])=>k+'='+JSON.stringify(v)).join('\n')+'\n');
   const base='http://127.0.0.1:'+await freePort();
   server=spawn(process.execPath,['--import','./scripts/sites-env.mjs','./node_modules/wrangler/bin/wrangler.js','dev','--config',file,'--local','--persist-to',path.join(state,'state'),'--ip','127.0.0.1','--port',new URL(base).port,'--inspector-port','0'],{cwd:CLOUD,env:{...env,WRANGLER_SEND_METRICS:'false',CI:'1',NO_COLOR:'1'},windowsHide:true,stdio:['ignore','ignore','ignore']});
   server.stdout?.resume();server.stderr?.resume();http=await request.newContext();let ready=false;const startupDeadline=Date.now()+60000;for(let i=0;i<220&&Date.now()<startupDeadline;i++){if(server.exitCode!==null)throw Error('Owned quota Worker exited');try{if((await http.get(base+'/api/health',{timeout:15000})).ok()){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,200));}assert(ready,'Owned quota Worker startup timeout');
   env.EW_CLOUD_QA_CREDENTIALS=JSON.stringify({username:'demo_admin',password});testArgs.push('--base='+base);
   console.log(JSON.stringify({target,suite,ownedState:path.relative(ROOT,state),port:new URL(base).port,providerMode:'independent-real-loopback-http-sse'}));
  }else if(suite!=='full'){
   const db=path.join(__dirname,moduleName+'隔离-'+runId+'.sqlite3');assert(!fs.existsSync(db));
   server=spawn(python,['-B',path.join(__dirname,moduleName+'Python测试服务.py'),'--db',db],{cwd:ROOT,env,windowsHide:true,stdio:['ignore','pipe','pipe']});
   const base=await readyProcess(server,/APP: (http:\/\/127\.0\.0\.1:\d+)/,'owned quota Python server');testArgs.push('--base='+base);
   console.log(JSON.stringify({target,suite,ownedDatabase:path.relative(ROOT,db),port:new URL(base).port,providerMode:'independent-real-loopback-http-sse'}));
  }
  const before=identity(),reportFile=path.join(__dirname,reportName),priorBytes=fs.existsSync(reportFile)?fs.readFileSync(reportFile):null,priorReport=priorBytes?JSON.parse(priorBytes.toString('utf8')):null,priorLatest=priorReport?(priorReport.latest||priorReport):null,previousTag=priorLatest?JSON.stringify([priorLatest.at,priorLatest.runId??null]):null,testStarted=Date.now();
  const child=spawn(process.execPath,testArgs,{cwd:ROOT,env,windowsHide:true,stdio:'inherit'}),code=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',resolve);});
  const after=identity();if(JSON.stringify(after)!==JSON.stringify(before)){
   const changedPaths=[...new Set([...Object.keys(before),...Object.keys(after)])].filter(name=>before[name]!==after[name]);
   const failureName=moduleName+'启动身份失败-'+target+'-'+suite+'-'+runId+'.json';
   fs.writeFileSync(path.join(__dirname,failureName),JSON.stringify({at:new Date().toISOString(),target,suite,runId,pass:false,reason:'source_build_or_qa_changed',expected:before,actual:after,changedPaths,rawReportPreserved:reportName,childExitCode:code},null,2)+'\n');
   throw Error('Product/build/QA identity changed; independent failure record '+failureName);
  }
  const fresh=bindFreshReport({reportFile,priorBytes,previousTag,testStarted,metadata:{runId,suite,runtimeArtifacts,syntheticDataOnly:true,realSupplier:false,realHttpSseFixture:true,sourceAndBuildHashes:before,identityUnchanged:true,childExitCode:code},diagnosticFile:path.join(__dirname,moduleName+'启动新鲜度失败-'+target+'-'+suite+'-'+runId+'.json')});if(!fresh)throw Error('Owned quota child did not produce a fresh report; previous bytes retained');
  process.exitCode=code===0?0:1;
 }catch(error){console.error(error.stack||String(error));process.exitCode=1;}
 finally{await http?.dispose().catch(()=>{});await kill(server);await kill(upstream);if(privateVars){assert(path.resolve(privateVars).startsWith(path.resolve(CLOUD,'.wrangler')+path.sep));if(fs.existsSync(privateVars))fs.unlinkSync(privateVars);}}
})();
