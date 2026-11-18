'use strict';
// Fresh actual workerd/D1 timing component. This is not the forty-case final gate.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {runOwned}=require('./负责人优化建议-卡组迁移验收启动.cjs');
const tooling=require('./负责人优化建议-卡组迁移测试工具.cjs'),factory=require('./负责人优化建议-卡组迁移用例工具.cjs');
const ROOT=path.resolve(__dirname,'..'),PREFIX='负责人优化建议-卡组迁移',sha=v=>crypto.createHash('sha256').update(v).digest('hex'),privateValues=[],before=tooling.identity();
const report={at:new Date().toISOString(),formalAcceptance:false,syntheticOnly:true,production:false,scope:'Actual Cloud native prefixed D1 batch timing: owner records erasure409 and account closure401; no mocked business response; CardImports tracer is outside this legacy-only component',results:[],traffic:[],sourceAndBuildHashes:before,sourceCanonicalSHA256:sha(JSON.stringify(before)),componentScript:{path:path.relative(ROOT,__filename).replaceAll('\\','/'),sha256:sha(fs.readFileSync(__filename))}};
let serial=0,ownedState;
const clean=value=>tooling.redactText(String(value),privateValues);
async function main(){
 try{
  await runOwned({target:'cloud',suite:'special',probe:async p=>{
   report.runtimeArtifacts=p.runtimeArtifacts;
   const controllerPath=path.join(__dirname,PREFIX+'夹具控制.ts'),accountPath=path.join(ROOT,'04_研发源码/app/cloud/lib/account-write-guard.ts'),controller=fs.readFileSync(controllerPath,'utf8'),account=fs.readFileSync(accountPath,'utf8');
   assert(controller.includes("text.filter(sql=>/^\\s*INSERT\\s+INTO\\s+card_history_migration_guards\\b/i.test(sql)).length===2"),'Entered cm barrier is conditional on exactly two actual business guard INSERTs');
   assert(controller.includes('return target.batch(items.map(item=>nativeStatements.get(item)||item))'),'All original native statements and bindings remain forwarded');
   assert(account.includes('db.batch([fence,...raw])'),'Current real account fence remains prepended');
   report.nativeBatchSourceBinding={businessGuardInsertCount:2,accountFencePreserved:true,guardCountMeaning:'Real entered event is behind this exact source-bound predicate; no runtime trace is invented',controllerSHA256:sha(fs.readFileSync(controllerPath)),accountFenceSHA256:sha(fs.readFileSync(accountPath)),cardImportsTracerClaimed:false};
   const key=s=>'cmc_'+s+'_'+(++serial)+'_'+p.runId;
   const h={base:p.base,key,report,context:p.context};
   h.api=async(c,route,data,method=data===undefined?'GET':'POST',expected=200)=>{const response=await c.fetch(p.base+'/api/'+route,{method,...(data===undefined?{}:{data}),timeout:75000});let data_;try{data_=await response.json();}catch{data_={error:'Non-JSON response'};}report.traffic.push({method,path:'/api/'+route,status:response.status()});if(expected!==null)assert.equal(response.status(),expected,route+': '+(data_.error||''));return{data:data_,status:response.status(),response};};
   h.rawApi=async(c,route,raw,{headers={},expected=200}={})=>{const response=await c.post(p.base+'/api/'+route,{headers:{'Content-Type':'application/json',...headers},data:raw,timeout:75000}),data=await response.json();report.traffic.push({method:'POST',path:'/api/'+route,status:response.status(),requestBytes:Buffer.byteLength(raw)});assert.equal(response.status(),expected,route+': '+(data.error||''));return{response,status:response.status(),data};};
   h.cardControl=async data=>{const c=await p.context(),response=await c.post(p.base+'/__card-migration-test/control',{headers:{'X-Card-Migration-Test':p.tokens.card},data,timeout:30000});assert.equal(response.status(),200,'Owned fixed control');return response.json();};
   const admin=await p.context(),credential=JSON.parse(p.env.EW_CLOUD_QA_CREDENTIALS);await h.api(admin,'auth/login',credential);
   const actualApp=await admin.get(p.base+'/experience');assert.equal(actualApp.status(),200);assert.equal(sha(await actualApp.body()),before['04_研发源码/app/cloud/generated/experience.html']);
   const f=factory(h,{admin});
   async function register(label){const c=await p.context(),credential={username:('cmc_'+label+'_'+p.runId.replace(/[^A-Za-z0-9_]/g,'')).slice(0,32),password:crypto.randomBytes(24).toString('hex'),name:'合成屏障 '+label};privateValues.push(credential.password);const response=await h.api(c,'auth/register',credential);credential.id=response.data.user.id;return{c,credential};}
   const tables=['card_history_migration_jobs','card_history_migration_targets','card_legacy_archives','card_history_migration_receipts','card_history_migration_operations','card_history_migration_guards'];
   const ownerRows=(s,person)=>Object.fromEntries(tables.map(t=>[t,s[t].filter(r=>r.owner===person.credential.id)]));
   const snapshot=async person=>ownerRows(await f.snapshot(tables),person),digest=value=>sha(f.canonical(value));
   async function add(person,label){const record={cardId:label,date:'2020-02-29',drawnAt:1582934400000},preview=await f.migrationPreview(person,[record]);return f.migrationApply(person,preview.job);}
   const keep=await register('keep');await add(keep,'SYNTHETIC_OTHER_OWNER_KEPT');const preserved=digest(await snapshot(keep));
   report.actualRuntime={runId:p.runId,base:p.base,serverPid:p.serverPid,ownedState:p.ownedState,configuredNodeSha256:sha(fs.readFileSync(process.execPath)),actualAppSha256:sha(await actualApp.body())};ownedState=p.ownedState;
   const manifest=path.join(__dirname,PREFIX+'manifest-'+p.runId+'.json');assert(fs.existsSync(manifest));report.actualRuntime.manifest={path:path.relative(ROOT,manifest).replaceAll('\\','/'),sha256:sha(fs.readFileSync(manifest))};
   for(const mode of ['clear','close']){
    const started=Date.now();let pending;
    try{
     const person=await register(mode);await add(person,'SYNTHETIC_'+mode+'_OLD_ARCHIVE');const preview=await f.migrationPreview(person,[{cardId:'SYNTHETIC_'+mode+'_PENDING',date:'2020-03-01',drawnAt:1583020800000}]);
     await f.barrier('cm','arm',{stage:'before-final'});
     pending=h.api(person.c,'cards/legacy-migrations/'+preview.job.id+'/apply',{requestId:key(mode+'_apply'),confirmed:true,version:preview.job.version},'POST',null);pending.catch(()=>{});
     let afterErasure,receipt;
     try{
      await f.waitEntered('cm');const barrier=await f.barrier('cm','state');assert.equal(barrier.entered,true,'Real guarded native batch reached the fixture timing point');
      if(mode==='clear'){receipt=(await h.api(person.c,'privacy/requests',{kind:'delete-records',requestId:key('clear')})).data.item;assert(receipt.details.local.deletedCounts.cardLegacy.deletedCounts.card_legacy_archives>=1);}
      else{const closed=await f.close(person);receipt=closed.response.receipt;assert.equal(receipt.accountClosed,true);}
      afterErasure=await snapshot(person);assert.equal(afterErasure.card_legacy_archives.length,0);assert.equal(afterErasure.card_history_migration_targets.length,0);assert(afterErasure.card_history_migration_jobs.every(j=>j.status==='erased'&&j.data==='{}'&&j.source_reference===''&&j.erased_at>0));assert(afterErasure.card_history_migration_operations.every(o=>o.response_data==='{}'));assert.equal(afterErasure.card_history_migration_guards.length,0);
     }finally{await f.barrier('cm','release');}
     const final=await pending;assert.equal(final.status,mode==='clear'?409:401,'Exact existing native final gate result');assert.equal(digest(await snapshot(person)),digest(afterErasure),'Late final cannot mutate the same-owner erased graph');assert.equal(digest(await snapshot(keep)),preserved,'Another owner remains exactly unchanged');assert.equal((await f.snapshot(tables)).card_history_migration_guards.length,0);
     if(mode==='clear'){await f.migrationDetail(person,preview.job,{expected:410});assert.equal((await f.archives(person)).items.length,0);}else await h.api(person.c,'cards/legacy-archives',undefined,'GET',401);
     report.results.push({name:mode==='clear'?'Actual held native batch then owner records erasure409':'Actual held native batch then password/nonce account closure401',pass:true,ms:Date.now()-started,barrierActuallyEntered:true,finalStatus:final.status,privateBodiesRevived:false,otherOwnerPreserved:true,remainingGuardRows:0,erasureReceiptId:receipt.id});
    }catch(error){report.results.push({name:mode+' actual native guarded batch',pass:false,error:p.clean(clean(error.stack||error))});throw error;}
    finally{await f.barrier('cm','release').catch(()=>{});if(pending)await pending.catch(()=>{});}
   }
   report.cardImportsTracerClaimed=false;
   for(const artifact of p.runtimeArtifacts){assert.equal(sha(fs.readFileSync(path.join(ROOT,artifact.bundle))),artifact.bundleSha256);assert.equal(sha(fs.readFileSync(path.join(ROOT,artifact.metafile))),artifact.metafileSha256);for(const [name,hash]of Object.entries(artifact.inputHashes))assert.equal(before[name],hash);for(const [name,hash]of Object.entries(artifact.runtimeDependencyHashes))assert.equal(sha(fs.readFileSync(path.join(ROOT,name))),hash);}
  }});
  assert.deepEqual(tooling.identity(),before,'Actual product/build/QA graph remains unchanged');assert(ownedState&&path.isAbsolute(ownedState));assert.equal(path.dirname(ownedState),path.resolve(ROOT,'04_研发源码/app/cloud/.wrangler'));assert.equal(path.basename(ownedState),'card-migration-special-'+report.actualRuntime.runId);assert(!fs.existsSync(path.resolve(ownedState,'.dev.vars')),'Owned private vars are removed by the actual outer cleanup');report.identityUnchanged=true;report.ownedVarsPresent=false;report.pass=report.results.length===2&&report.results.every(r=>r.pass);
 }catch(error){report.pass=false;report.error=clean(error.stack||error);}
 finally{
  report.passed=report.results.filter(r=>r.pass).length;report.failed=report.results.filter(r=>!r.pass).length;const file=path.join(__dirname,PREFIX+'Cloud批次屏障组件-'+Date.now().toString(36)+'-'+crypto.randomBytes(4).toString('hex')+'.json');fs.writeFileSync(file,JSON.stringify(report,(_key,value)=>typeof value==='string'?clean(value):value,2)+'\n',{flag:'wx'});console.log(JSON.stringify({formalAcceptance:false,pass:report.pass,passed:report.passed,failed:report.failed,report:path.relative(ROOT,file),sha256:sha(fs.readFileSync(file))}));process.exitCode=report.pass?0:1;
 }
}
main();
