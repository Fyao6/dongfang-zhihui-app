'use strict';
// One launcher for new, owned PAY08 QA services. Never reads an existing preview/production DB.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),net=require('node:net'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud');
const runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {request}=require(path.join(runtime,'node/node_modules/playwright'));
const args=Object.fromEntries(process.argv.slice(2).filter(s=>s.startsWith('--')).map(s=>{const n=s.indexOf('=');return [s.slice(2,n<0?undefined:n),n<0?true:s.slice(n+1)];}));
const target=args.target||'python',suite=args.suite||'special';
assert(['python','cloud'].includes(target));assert(['special','full','compat','visual'].includes(suite));assert(!args.base,'This launcher only starts new isolated services');
const qaName='pay08-'+Date.now().toString(36)+'-'+crypto.randomBytes(4).toString('hex');
const freePort=()=>new Promise((resolve,reject)=>{const server=net.createServer();server.once('error',reject);server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>resolve(port));});});
const moduleName='负责人优化建议-支付回调';
let server,http;
async function stop(){
 await http?.dispose().catch(()=>{});
 if(server&&server.exitCode===null){
  if(process.platform==='win32')await new Promise(resolve=>{const task=spawn(path.join(process.env.SystemRoot||'C:\\Windows','System32/taskkill.exe'),['/PID',String(server.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});task.once('exit',resolve);task.once('error',resolve);});
  else server.kill();
 }
}
(async()=>{
 try{
  const secret=crypto.randomBytes(32).toString('hex'),token=crypto.randomBytes(32).toString('hex');
  const env={...process.env,EW_PAYMENT_CALLBACK_SANDBOX_ENABLED:'1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF:'EW_PAYMENT_CALLBACK_QA_SECRET',EW_PAYMENT_CALLBACK_QA_SECRET:secret,CALLBACK_TEST_TOKEN:token,EW_DEVICE_REGRESSION_CANARY:'regression-secret-not-for-real-use'};
  let testArgs;
  if(suite==='special')testArgs=[path.join(__dirname,moduleName+'专项.cjs'),'--target='+target,'--module='+moduleName,'--report='+moduleName+'专项-'+target+'.json',...(args['http-only']?['--http-only']:[])];
  else if(suite==='compat')testArgs=[path.join(__dirname,'负责人优化建议-交易专项.cjs'),'--target='+target,'--module='+moduleName+'交易兼容','--report='+moduleName+'交易兼容-'+target+'.json'];
  else if(suite==='visual')testArgs=[path.join(__dirname,moduleName+'补充视觉.cjs'),'--target='+target,'--module='+moduleName+'补充视觉','--report='+moduleName+'补充视觉-'+target+'.json'];
  else testArgs=[path.join(__dirname,target==='cloud'?'公网适配全量回归.cjs':'全量回归.cjs'),'--module='+moduleName,'--bazi-stage=4',...(target==='python'?['--admin']:[])];
  if(target==='cloud'){
   const state=path.resolve(CLOUD,'.wrangler',qaName),config=path.join(state,'wrangler.json');
   assert(state.startsWith(path.resolve(CLOUD,'.wrangler')+path.sep)&&!fs.existsSync(state));
   fs.mkdirSync(state,{recursive:true});
   const password=crypto.randomBytes(24).toString('hex'),salt=crypto.randomBytes(16).toString('hex');
   const adminHash=salt+':'+crypto.pbkdf2Sync(password,Buffer.from(salt,'hex'),100000,32,'sha256').toString('hex');
   const cfg={name:'pay08-isolated-qa',main:path.join(__dirname,moduleName+'Cloud测试服务.ts'),compatibility_date:'2026-05-15',compatibility_flags:['nodejs_compat'],
    assets:{directory:path.join(CLOUD,'public'),binding:'ASSETS',run_worker_first:true},
    d1_databases:[{binding:'DB',database_name:'pay08-isolated-db',database_id:'00000000-0000-4000-8000-000000000000'}],
    r2_buckets:[{binding:'BUCKET',bucket_name:'pay08-isolated-bucket'}]};
   fs.writeFileSync(config,JSON.stringify(cfg,null,2)+'\n');
   const vars={DEMO_ADMIN_HASH:adminHash,EW_PAYMENT_CALLBACK_SANDBOX_ENABLED:'1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF:'EW_PAYMENT_CALLBACK_QA_SECRET',EW_PAYMENT_CALLBACK_QA_SECRET:secret,CALLBACK_TEST_TOKEN:token,EW_DEVICE_REGRESSION_CANARY:'regression-secret-not-for-real-use'};
   fs.writeFileSync(path.join(state,'.dev.vars'),Object.entries(vars).map(([key,value])=>key+'='+JSON.stringify(value)).join('\n')+'\n');
   const port=await freePort(),base='http://127.0.0.1:'+port;
   server=spawn(process.execPath,['--import','./scripts/sites-env.mjs','./node_modules/wrangler/bin/wrangler.js','dev','--config',config,'--local','--persist-to',path.join(state,'state'),'--ip','127.0.0.1','--port',String(port),'--inspector-port','0'],
    {cwd:CLOUD,windowsHide:true,stdio:['ignore','ignore','ignore'],env:{...env,WRANGLER_SEND_METRICS:'false',CI:'1',NO_COLOR:'1'}});
   http=await request.newContext();let ready=false;
   for(let attempt=0;attempt<220;attempt++){
    if(server.exitCode!==null)throw Error('Owned PAY08 Worker exited before ready; no production service was used');
    try{const response=await http.get(base+'/api/health',{timeout:600});if(response.ok()){ready=true;break;}}catch{}
    await new Promise(resolve=>setTimeout(resolve,150));
   }
   assert(ready,'Owned PAY08 Worker start timeout');
   env.EW_CLOUD_QA_CREDENTIALS=JSON.stringify({username:'demo_admin',password});testArgs.push('--base='+base);
   console.log(JSON.stringify({target,suite,ownedState:path.relative(ROOT,state).split(path.sep).join('/'),port,production:false}));
  }
  if(target==='python'&&suite==='visual'){
   const db=path.join(__dirname,'负责人优化建议-支付回调隔离-'+qaName+'.sqlite3');assert(!fs.existsSync(db));
   const python=process.env.EW_PYTHON||path.join(runtime,'python/python.exe');
   server=spawn(python,['-B',path.join(__dirname,moduleName+'Python测试服务.py'),'--db',db],{cwd:ROOT,env,windowsHide:true,stdio:['ignore','pipe','pipe']});
   const base=await new Promise((resolve,reject)=>{let text='';const timeout=setTimeout(()=>reject(Error('Owned PAY08 visual Python service start timeout')),25000);server.stdout.on('data',data=>{text+=data;const match=/APP: (http:\/\/127\.0\.0\.1:\d+)/.exec(text);if(match){clearTimeout(timeout);resolve(match[1]);}});server.stderr.on('data',data=>{text+=data;});server.once('exit',code=>{clearTimeout(timeout);reject(Error('Owned PAY08 visual Python service exited '+code));});server.once('error',error=>{clearTimeout(timeout);reject(error);});});
   testArgs.push('--base='+base);
   console.log(JSON.stringify({target,suite,ownedDatabase:path.relative(ROOT,db).split(path.sep).join('/'),port:new URL(base).port,production:false}));
  }
  const test=spawn(process.execPath,testArgs,{cwd:ROOT,windowsHide:true,stdio:'inherit',env});
  const code=await new Promise((resolve,reject)=>{test.once('error',reject);test.once('exit',resolve);});
  process.exitCode=code===0?0:1;
 }catch(error){console.error(error.stack||String(error));process.exitCode=1;}
 finally{await stop();}
})();
