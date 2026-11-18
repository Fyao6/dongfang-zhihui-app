'use strict';
// Starts only a fresh owned local service for the unchanged current31 compatibility contract.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),net=require('node:net'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud');
const runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {request}=require(path.join(runtime,'node/node_modules/playwright'));
const args=Object.fromEntries(process.argv.slice(2).map(s=>{const n=s.indexOf('=');return [s.slice(2,n<0?undefined:n),n<0?true:s.slice(n+1)];}));
const target=String(args.target||'python');assert(['python','cloud'].includes(target));assert(!args.base,'Only fresh owned compatibility services are allowed');
const freePort=()=>new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});
let server,context;
(async()=>{
 try{
  const env={...process.env,AFTER_SALES_COMPAT_LAUNCHER:__filename};
  const testArgs=[path.join(__dirname,'负责人优化建议-售后交易兼容专项.cjs'),'--target='+target,'--module=负责人优化建议-售后交易兼容','--report=负责人优化建议-售后交易兼容专项-'+target+'.json'];
  if(target==='cloud'){
   const name='ac'+crypto.randomBytes(4).toString('hex'),state=path.join(CLOUD,'.wrangler',name),config=path.join(__dirname,'负责人优化建议-售后交易兼容Cloud配置-'+name+'.json');
   assert(!fs.existsSync(state)&&!fs.existsSync(config));
   const password=crypto.randomBytes(24).toString('hex'),salt=crypto.randomBytes(16),hash=salt.toString('hex')+':'+crypto.pbkdf2Sync(password,salt,100000,32,'sha256').toString('hex');
   const cfg={name:'after-sales-compatibility-qa',assets:{directory:path.join(CLOUD,'public'),binding:'ASSETS',run_worker_first:true},
    main:path.join(__dirname,'负责人优化建议-售后Cloud测试服务.ts'),compatibility_date:'2026-05-15',compatibility_flags:['nodejs_compat'],vars:{DEMO_ADMIN_HASH:hash},
    d1_databases:[{binding:'DB',database_name:'after-sales-compatibility',database_id:'00000000-0000-4000-8000-000000000000'}],
    r2_buckets:[{binding:'BUCKET',bucket_name:'after-sales-compatibility'}],rules:[{type:'Text',globs:['**/*.html','**/*.sql'],fallthrough:true}]};
   fs.writeFileSync(config,JSON.stringify(cfg));
   const base='http://127.0.0.1:'+await freePort();assert.notEqual(new URL(base).port,'8878');
   server=spawn(process.execPath,['--import','./scripts/sites-env.mjs','./node_modules/wrangler/bin/wrangler.js','dev','--config',config,'--local','--persist-to',state,'--ip','127.0.0.1','--port',new URL(base).port,'--inspector-port','0'],
    {cwd:CLOUD,windowsHide:true,stdio:['ignore','ignore','ignore'],env:{...process.env,WRANGLER_SEND_METRICS:'false',CI:'1',NO_COLOR:'1'}});
   context=await request.newContext();let ready=false;
   for(let n=0;n<220;n++){if(server.exitCode!==null)throw Error('Owned compatibility worker exited');try{const r=await context.get(base+'/api/health',{timeout:600});if(r.ok()){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,150));}
   assert(ready,'Owned compatibility worker startup timeout');env.AFTER_SALES_COMPAT_TEST_PASSWORD=password;testArgs.push('--base='+base);
   console.log(JSON.stringify({target,ownedState:path.relative(ROOT,state),ownedLoopbackPort:new URL(base).port,production:false}));
  }
  const test=spawn(process.execPath,testArgs,{cwd:ROOT,windowsHide:true,stdio:'inherit',env});
  const code=await new Promise((resolve,reject)=>{test.once('error',reject);test.once('exit',resolve);});process.exitCode=code||0;
 }catch(e){console.error(e.stack);process.exitCode=1;}
 finally{
  await context?.dispose().catch(()=>{});
  if(server&&server.exitCode===null){if(process.platform==='win32')await new Promise(resolve=>{const p=spawn(path.join(process.env.SystemRoot||'C:\\Windows','System32/taskkill.exe'),['/PID',String(server.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});p.once('exit',resolve);p.once('error',resolve);});else server.kill();}
 }
})();

