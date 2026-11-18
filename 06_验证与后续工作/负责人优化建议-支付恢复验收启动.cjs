'use strict';
// Fresh local PAY09 services plus an independent, signed HTTP upstream process.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),net=require('node:net'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud');
const runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {request}=require(path.join(runtime,'node/node_modules/playwright'));
const python=process.env.EW_PYTHON||path.join(runtime,'python/python.exe');
const args=Object.fromEntries(process.argv.slice(2).filter(s=>s.startsWith('--')).map(s=>{const n=s.indexOf('=');return [s.slice(2,n<0?undefined:n),n<0?true:s.slice(n+1)];}));
const target=args.target||'python',suite=args.suite||'special',moduleName='负责人优化建议-支付恢复';
assert(['python','cloud'].includes(target));assert(['special','full','compat','visual','pay08','probe'].includes(suite));assert(!args.base,'This launcher starts only new owned services');assert(suite!=='probe'||target==='cloud');
const qaName='pay09-'+Date.now().toString(36)+'-'+crypto.randomBytes(4).toString('hex');
const freePort=()=>new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});
let server,upstream,http;
function readyProcess(process,pattern,label){return new Promise((resolve,reject)=>{let output='';const timeout=setTimeout(()=>reject(Error(label+' startup timeout')),25000);process.stdout.on('data',data=>{output+=data;const match=pattern.exec(output);if(match){clearTimeout(timeout);resolve(match[1]);}});process.stderr.on('data',()=>{});process.once('error',error=>{clearTimeout(timeout);reject(error);});process.once('exit',code=>{clearTimeout(timeout);reject(Error(label+' exited '+code));});});}
async function kill(proc){
 if(!proc||proc.exitCode!==null)return;
 if(process.platform==='win32')await new Promise(resolve=>{const p=spawn(path.join(process.env.SystemRoot||'C:\\Windows','System32/taskkill.exe'),['/PID',String(proc.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});p.once('exit',resolve);p.once('error',resolve);});
 else proc.kill();
}
(async()=>{
 try{
  const querySecret=crypto.randomBytes(32).toString('hex'),callbackSecret=crypto.randomBytes(32).toString('hex'),token=crypto.randomBytes(32).toString('hex');
  const env={...process.env,EW_PAYMENT_QUERY_SANDBOX_ENABLED:'1',EW_PAYMENT_QUERY_SANDBOX_SECRET_REF:'EW_PAYMENT_QUERY_QA_SECRET',EW_PAYMENT_QUERY_QA_SECRET:querySecret,
   EW_PAYMENT_CALLBACK_SANDBOX_ENABLED:'1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF:'EW_PAYMENT_CALLBACK_QA_SECRET',EW_PAYMENT_CALLBACK_QA_SECRET:callbackSecret,RECOVERY_TEST_TOKEN:token,CALLBACK_TEST_TOKEN:token,EW_DEVICE_REGRESSION_CANARY:'regression-secret-not-for-real-use'};
  upstream=spawn(python,['-B',path.join(__dirname,moduleName+'HTTP查询夹具.py')],{cwd:ROOT,env,windowsHide:true,stdio:['ignore','pipe','pipe']});
  const endpoint=await readyProcess(upstream,/QUERY_FIXTURE: (http:\/\/127\.0\.0\.1:\d+\/pay09-fixture\/query)/,'PAY09 signed HTTP fixture');env.EW_PAYMENT_QUERY_SANDBOX_ENDPOINT=endpoint;
  let testArgs;
  if(suite==='special')testArgs=[path.join(__dirname,moduleName+'专项.cjs'),'--target='+target,'--module='+moduleName,'--report='+moduleName+'专项-'+target+'.json',...(args['http-only']?['--http-only']:[])];
  else if(suite==='pay08')testArgs=[path.join(__dirname,'负责人优化建议-支付回调专项.cjs'),'--target='+target,'--module='+moduleName+'PAY08兼容','--report='+moduleName+'-PAY08兼容-'+target+'.json'];
  else if(suite==='visual')testArgs=[path.join(__dirname,moduleName+'补充视觉.cjs'),'--target='+target,'--module='+moduleName+'补充视觉','--report='+moduleName+'补充视觉-'+target+'.json'];
  else if(suite==='compat')testArgs=[path.join(__dirname,'负责人优化建议-交易专项.cjs'),'--target='+target,'--module='+moduleName+'交易兼容','--report='+moduleName+'交易兼容-'+target+'.json'];
  else testArgs=[path.join(__dirname,target==='cloud'?'公网适配全量回归.cjs':'全量回归.cjs'),'--module='+moduleName,'--bazi-stage=4',...(target==='python'?['--admin']:[])];
  if(target==='cloud'){
   const state=path.resolve(CLOUD,'.wrangler',qaName),config=path.join(state,'wrangler.json');assert(state.startsWith(path.resolve(CLOUD,'.wrangler')+path.sep)&&!fs.existsSync(state));fs.mkdirSync(state,{recursive:true});
   const password=crypto.randomBytes(24).toString('hex'),salt=crypto.randomBytes(16).toString('hex');const hash=salt+':'+crypto.pbkdf2Sync(password,Buffer.from(salt,'hex'),100000,32,'sha256').toString('hex');
   const cfg={name:'pay09-isolated-qa',main:path.join(__dirname,suite==='pay08'?'负责人优化建议-支付回调Cloud测试服务.ts':moduleName+'Cloud测试服务.ts'),compatibility_date:'2026-05-15',compatibility_flags:['nodejs_compat'],assets:{directory:path.join(CLOUD,'public'),binding:'ASSETS',run_worker_first:true},
    d1_databases:[{binding:'DB',database_name:'pay09-isolated-db',database_id:'00000000-0000-4000-8000-000000000000'}],r2_buckets:[{binding:'BUCKET',bucket_name:'pay09-isolated-bucket'}]};
   fs.writeFileSync(config,JSON.stringify(cfg,null,2)+'\n');
   const vars={DEMO_ADMIN_HASH:hash,EW_PAYMENT_QUERY_SANDBOX_ENABLED:'1',EW_PAYMENT_QUERY_SANDBOX_SECRET_REF:'EW_PAYMENT_QUERY_QA_SECRET',EW_PAYMENT_QUERY_QA_SECRET:querySecret,EW_PAYMENT_QUERY_SANDBOX_ENDPOINT:endpoint,
    EW_PAYMENT_CALLBACK_SANDBOX_ENABLED:'1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF:'EW_PAYMENT_CALLBACK_QA_SECRET',EW_PAYMENT_CALLBACK_QA_SECRET:callbackSecret,RECOVERY_TEST_TOKEN:token,CALLBACK_TEST_TOKEN:token,EW_DEVICE_REGRESSION_CANARY:'regression-secret-not-for-real-use'};
   fs.writeFileSync(path.join(state,'.dev.vars'),Object.entries(vars).map(([key,value])=>key+'='+JSON.stringify(value)).join('\n')+'\n');
   const port=await freePort(),base='http://127.0.0.1:'+port;
   server=spawn(process.execPath,['--import','./scripts/sites-env.mjs','./node_modules/wrangler/bin/wrangler.js','dev','--config',config,'--local','--persist-to',path.join(state,'state'),'--ip','127.0.0.1','--port',String(port),'--inspector-port','0'],{cwd:CLOUD,windowsHide:true,stdio:['ignore','ignore','ignore'],env:{...env,WRANGLER_SEND_METRICS:'false',CI:'1',NO_COLOR:'1'}});
   http=await request.newContext();let ready=false;for(let i=0;i<220;i++){if(server.exitCode!==null)throw Error('Owned PAY09 Worker exited');try{const r=await http.get(base+'/api/health',{timeout:600});if(r.ok()){ready=true;break;}}catch{}await new Promise(resolve=>setTimeout(resolve,150));}assert(ready,'Owned PAY09 Worker start timeout');
   env.EW_CLOUD_QA_CREDENTIALS=JSON.stringify({username:'demo_admin',password});testArgs.push('--base='+base);
   console.log(JSON.stringify({target,suite,ownedState:path.relative(ROOT,state).split(path.sep).join('/'),port,upstreamPort:new URL(endpoint).port,production:false}));
   if(suite==='probe'){
    const response=await http.post(base+'/__recovery-test/control',{headers:{'X-Recovery-Test':token},data:{action:'transport-probe'}});
    console.log(JSON.stringify({probeStatus:response.status(),diagnostic:await response.json()}));return;
   }
  }
  if(target==='python'&&suite==='visual'){
   const db=path.join(__dirname,'负责人优化建议-支付恢复隔离-'+qaName+'.sqlite3');assert(!fs.existsSync(db));
   server=spawn(python,['-B',path.join(__dirname,moduleName+'Python测试服务.py'),'--db',db],{cwd:ROOT,env,windowsHide:true,stdio:['ignore','pipe','pipe']});const base=await readyProcess(server,/APP: (http:\/\/127\.0\.0\.1:\d+)/,'PAY09 Python fixture');testArgs.push('--base='+base);
   console.log(JSON.stringify({target,suite,ownedDatabase:path.relative(ROOT,db).split(path.sep).join('/'),port:new URL(base).port,upstreamPort:new URL(endpoint).port,production:false}));
  }
  const test=spawn(process.execPath,testArgs,{cwd:ROOT,windowsHide:true,stdio:'inherit',env});const code=await new Promise((resolve,reject)=>{test.once('error',reject);test.once('exit',resolve);});process.exitCode=code===0?0:1;
 }catch(error){console.error(error.stack||String(error));process.exitCode=1;}
 finally{await http?.dispose().catch(()=>{});await kill(server);await kill(upstream);}
})();
