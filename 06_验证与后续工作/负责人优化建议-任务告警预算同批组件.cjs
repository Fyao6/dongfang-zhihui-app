'use strict';
// Isolated native D1 component: actual product fence + trigger + same-batch mutation.
// This is not an HTTP, bootstrap, callback or notification integration suite.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud');
const esbuild=require(path.join(CLOUD,'node_modules/esbuild')),{Miniflare}=require(path.join(CLOUD,'node_modules/miniflare'));
const sha=value=>crypto.createHash('sha256').update(value).digest('hex'),tag='ops-budget-'+Date.now()+'-'+crypto.randomBytes(4).toString('hex');
const owned=path.join(CLOUD,'.wrangler',tag),bundle=path.join(owned,'product.cjs'),reportFile=path.join(__dirname,'负责人优化建议-任务告警预算同批组件-'+tag+'.json');
const product=path.join(CLOUD,'lib/local-tasks.ts'),qa=path.join(__dirname,'负责人优化建议-任务告警通知专项.cjs');
const report={at:new Date().toISOString(),scope:'actual native Miniflare D1 same-batch component; not full HTTP/auth/bootstrap integration',productionEnabled:false,sourceSha256:sha(fs.readFileSync(product)),notificationQaSha256:sha(fs.readFileSync(qa)),ownedState:path.relative(ROOT,owned),cases:[]};let mf;
(async()=>{try{
 assert(!fs.existsSync(owned));fs.mkdirSync(owned,{recursive:true});
 await esbuild.build({entryPoints:[product],bundle:true,format:'cjs',platform:'node',target:'es2022',outfile:bundle,plugins:[{name:'actual-raw',setup(build){build.onResolve({filter:/\?raw$/},args=>({path:path.resolve(args.resolveDir,args.path.slice(0,-4)),namespace:'actual-raw'}));build.onLoad({filter:/.*/,namespace:'actual-raw'},args=>({contents:'export default '+JSON.stringify(fs.readFileSync(args.path,'utf8'))+';',loader:'js'}));}}]});
 const {LOCAL_TASK_DDL,LOCAL_TASK_DEFAULT,LocalTasks}=require(bundle);
 mf=new Miniflare({modules:true,script:'export default {fetch(){return new Response("component only")}}',compatibilityDate:'2026-05-15',d1Databases:{DB:'owned-ops-budget'},d1Persist:path.join(owned,'d1')});
 const db=await mf.getD1Database('DB'),stmt=(sql,...args)=>db.prepare(sql).bind(...args),one=(sql,...args)=>stmt(sql,...args).first();
 await db.batch([
  stmt('CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT NOT NULL)'),stmt('CREATE TABLE sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires INTEGER NOT NULL)'),stmt('CREATE TABLE account_lifecycle(owner TEXT PRIMARY KEY,status TEXT NOT NULL)'),
  ...LOCAL_TASK_DDL.map(sql=>stmt(sql)),stmt('CREATE TABLE owned_component_mutations(id INTEGER PRIMARY KEY,attempts INTEGER NOT NULL)'),stmt('INSERT INTO owned_component_mutations VALUES(1,0)')
 ]);
 const runtime=crypto.randomUUID(),manifest=sha('owned component manifest '+tag),actor='component-admin',token=crypto.randomBytes(32).toString('hex'),session=sha(token),runId='component-run',worker='component-worker',runToken='component-run-token',scheduleToken='component-schedule-token';
 const cfg={...LOCAL_TASK_DEFAULT,revision:1,enabled:true,confirmed:true,ruleVersion:'component-budget-v1',tasks:Object.fromEntries(Object.entries(LOCAL_TASK_DEFAULT.tasks).map(([k,v])=>[k,{...v,enabled:true}]))};
 await db.batch([
  stmt("INSERT INTO ops_runtime_identity VALUES(1,?,'local-isolated',?,?)",runtime,Date.now(),manifest),stmt('INSERT INTO ops_task_config VALUES(1,?)',JSON.stringify(cfg)),
  stmt("INSERT INTO users VALUES(?,'admin')",actor),stmt('INSERT INTO sessions VALUES(?,?,?)',session,actor,Date.now()+300000),
  stmt("INSERT INTO ops_workers VALUES(?,?,?,?,?,'active','',?,?)",worker,runtime,actor,session,Date.now(),Date.now(),Date.now()),
  stmt("INSERT INTO ops_task_schedules VALUES('payment_callbacks',0,?,?,1,?)",scheduleToken,Date.now()+60000,runId),
  stmt("INSERT INTO ops_task_runs VALUES(?,?,?,?,'payment_callbacks','component-request','component-fingerprint',1,?,?,'running',?,0,0,'','[]')",runId,runtime,actor,worker,runToken,Date.now()+60000,Date.now())
 ]);
 const api={env:{EW_LOCAL_TASK_RUNTIME_ENABLED:'1',EW_LOCAL_TASK_RUNTIME_ID:runtime,EW_LOCAL_TASK_MANIFEST_SHA256:manifest},token,one,stmt,db,require(roles){assert.deepEqual(roles,['admin']);return {id:actor,role:'admin'};}};
 const task=new LocalTasks(api,(status,message)=>{throw Error(status+': '+message)});
 const captured={id:runId,lease_token:runToken,scheduleToken,config_revision:1,actor,lease_until:Date.now()+60000};
 async function leases(runMs,scheduleMs){const now=Date.now();await db.batch([stmt('UPDATE ops_task_runs SET lease_until=? WHERE id=?',now+runMs,runId),stmt("UPDATE ops_task_schedules SET lease_until=? WHERE kind='payment_callbacks'",now+scheduleMs)]);}
 async function check(name,{runMs,scheduleMs,deadline=0,allowed,delay=0}){
  captured.lease_until=Date.now()+60000;const prefix=await task.fence(captured,deadline),before=(await one('SELECT attempts FROM owned_component_mutations WHERE id=1')).attempts;
  await leases(runMs,scheduleMs);if(delay)await new Promise(resolve=>setTimeout(resolve,delay));
  let error='';try{await db.batch([...prefix,stmt('UPDATE owned_component_mutations SET attempts=attempts+1 WHERE id=1')]);}catch(e){error=[e?.message,e?.cause?.message].filter(Boolean).join(' ');}
  const after=(await one('SELECT attempts FROM owned_component_mutations WHERE id=1')).attempts,proofs=(await one('SELECT count(*) n FROM ops_claim_fences')).n;
  if(allowed){assert.equal(error,'',name);assert.equal(after,before+1);}else{assert.match(error,/ops_claim_rejected/);assert.equal(after,before,'Rejected same-batch work must not mutate attempts');}
  assert.equal(proofs,0,'Proof is cleared on success or rolled back on rejection');report.cases.push({name,deadlineMs:deadline,requiredBudgetMs:deadline+1000,actualRunRemainingAtSetupMs:runMs,actualScheduleRemainingAtSetupMs:scheduleMs,delayBeforeBatchMs:delay,allowed,attemptDelta:after-before,proofRows:proofs,pass:true});
 }
 await check('Current valid dual leases allow exactly one unit',{runMs:60000,scheduleMs:60000,allowed:true});
 await check('Captured long run cannot override two actual 500ms leases',{runMs:500,scheduleMs:500,allowed:false});
 await check('Actual run budget alone is independently enforced',{runMs:500,scheduleMs:60000,allowed:false});
 await check('Actual schedule budget alone is independently enforced',{runMs:60000,scheduleMs:500,allowed:false});
 await check('New network unit requires actual 9000ms budget',{runMs:2500,scheduleMs:2500,deadline:8000,allowed:false});
 await check('Sufficient network budget allows one unit',{runMs:15000,scheduleMs:15000,deadline:8000,allowed:true});
 await check('Post-IO default fence retains 1000ms budget',{runMs:2500,scheduleMs:2500,allowed:true});
 await check('SQL clock evaluates budget after queue delay',{runMs:1200,scheduleMs:1200,delay:350,allowed:false});
 report.identityUnchanged=report.sourceSha256===sha(fs.readFileSync(product))&&report.notificationQaSha256===sha(fs.readFileSync(qa));assert(report.identityUnchanged);report.bundleSha256=sha(fs.readFileSync(bundle));report.harnessSha256=sha(fs.readFileSync(__filename));report.nativeD1SameBatch=true;report.passed=report.cases.length;report.failed=0;report.pass=true;
}catch(error){report.pass=false;report.error=String(error?.stack||error).slice(0,2500);process.exitCode=1;}finally{if(mf)await mf.dispose();fs.writeFileSync(reportFile,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({pass:report.pass,passed:report.cases.length,report:path.relative(ROOT,reportFile),sourceSha256:report.sourceSha256}));}})();
