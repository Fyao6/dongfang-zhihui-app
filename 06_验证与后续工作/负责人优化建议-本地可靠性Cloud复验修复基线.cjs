'use strict';
// Read-only, exact-path authorization. No old verifier is bypassed or rewritten.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..'),OUT=__dirname;
const PREFIX='负责人优化建议-本地可靠性Cloud复验';
const AUTH='06_验证与后续工作/'+PREFIX+'授权基线-rev3.json';
const PROOF='06_验证与后续工作/负责人优化建议-卡组迁移-最终交付核验.json',PROOF_SHA='752e36ad70d6812727849f0fa49262c426ef161a911b59f66831cd0617e12f07';
const BASELINE='06_验证与后续工作/负责人优化建议-本地可靠性-实施前核对.json',BASELINE_SHA='6fe9d95b438cc5a638ae534f01cbf7f6298f6bd1ab3201b1f4324d507eb06919';
const OLD_AUTH='06_验证与后续工作/负责人优化建议-本地可靠性性能修复授权基线-rev2.json',OLD_AUTH_SHA='1f8b83fa08f0d74dee7d1a1644e023f57b64263410b08fecc2ab202ef7f72edb';
const OLD_REPAIR='06_验证与后续工作/负责人优化建议-本地可靠性-性能修复复验.json',OLD_REPAIR_SHA='06e3519db0e08a94c10795e9b59b620b4a4289737c87ea09bb2157d0f1a00b5b';
const CLOUD_BEFORE='06_验证与后续工作/负责人优化建议-本地可靠性Cloud修复前-原字节清单.json',CLOUD_BEFORE_SHA='7388e2d641f97b7bd146c22c2b4bfab790196abf24780c21b58d94008c27a9ce';
const CANDIDATE='06_验证与后续工作/负责人优化建议-本地可靠性Cloud候选短诊断源码锚.json',CANDIDATE_SHA='81af66ac3e5ab7302c1a4b7afb4d4d640e6fe221e919b5f4aeca3c0b325451de';
const SERVER='04_研发源码/app/r4/backend/server.py',EASTERN='04_研发源码/app/cloud/lib/eastern-api.ts',DIST='04_研发源码/app/cloud/dist/';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function local(name){assert(typeof name==='string'&&!path.isAbsolute(name)&&!name.includes('\\')&&!name.split('/').includes('..'));const file=path.resolve(ROOT,name);assert(file.startsWith(ROOT+path.sep)&&fs.statSync(file).isFile());return file;}
function read(name){return JSON.parse(fs.readFileSync(local(name),'utf8'));}
function checked(entry){assert(entry&&typeof entry.path==='string'&&/^[a-f0-9]{64}$/.test(entry.sha256));assert.equal(sha(fs.readFileSync(local(entry.path))),entry.sha256);return read(entry.path);}
function distFiles(){const result={};const walk=dir=>{for(const e of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,e.name);assert(!e.isSymbolicLink());if(e.isDirectory())walk(file);else{assert(e.isFile());result[path.relative(ROOT,file).replaceAll('\\','/')]=sha(fs.readFileSync(file));}}};walk(path.join(ROOT,DIST));return Object.fromEntries(Object.entries(result).sort(([a],[b])=>a.localeCompare(b,'en')));}
function verifyAuthorization(expectedSha){
 assert(/^[a-f0-9]{64}$/.test(expectedSha||''));assert.equal(sha(fs.readFileSync(local(AUTH))),expectedSha);
 for(const[n,s]of [[PROOF,PROOF_SHA],[BASELINE,BASELINE_SHA],[OLD_AUTH,OLD_AUTH_SHA],[OLD_REPAIR,OLD_REPAIR_SHA],[CLOUD_BEFORE,CLOUD_BEFORE_SHA],[CANDIDATE,CANDIDATE_SHA]])assert.equal(sha(fs.readFileSync(local(n))),s);
 const a=read(AUTH),proof=read(PROOF),old=read(OLD_AUTH),prior=read(OLD_REPAIR),before=read(CLOUD_BEFORE),candidate=read(CANDIDATE);
 assert(a.schemaVersion===1&&a.revision===3&&a.stage===31&&a.authorizedByRoot===true&&a.originalStage30ProductUnchanged===false);
 for(const[k,p,s]of [['previousFinalProof',PROOF,PROOF_SHA],['previousBaseline',BASELINE,BASELINE_SHA],['previousRepairAuthorization',OLD_AUTH,OLD_AUTH_SHA],['previousRepairProof',OLD_REPAIR,OLD_REPAIR_SHA],['cloudBeforeManifest',CLOUD_BEFORE,CLOUD_BEFORE_SHA],['rootCandidateAnchor',CANDIDATE,CANDIDATE_SHA]])assert.deepEqual(a[k],{path:p,sha256:s});
 assert(proof.pass&&proof.stage===30&&proof.allFourteenGatesPassedWithFreshSuccessfulChildren);assert.deepEqual(proof.perBackendPassed,{Python:195,Cloud:195});
 assert(prior.pass&&prior.kind==='performance-fix-business-acceptance');assert.deepEqual(prior.perBackendPassed,{Python:195,Cloud:195});assert.equal(Object.keys(prior.reportIdentityHashes).length,548);
 assert.deepEqual(prior.reportIdentityHashes,before.sourceAndBuildHashes);
 assert.deepEqual(a.cloudProductChanges,candidate.cloudProductChanges);assert.equal(Object.keys(a.cloudProductChanges).length,44);
 assert.deepEqual(a.productChanges,{...old.productChanges,...a.cloudProductChanges});assert.deepEqual(Object.keys(old.productChanges),[SERVER]);
 const saved={};assert.equal(Object.keys(before.preserved).length,76);
 for(const[n,v]of Object.entries(before.preserved)){assert.equal(v.originalBytes.sha256,v.sha256);const file=local(v.originalBytes.path);assert(path.dirname(file)===OUT&&path.basename(file).startsWith('负责人优化建议-本地可靠性Cloud修复前-'));assert.equal(sha(fs.readFileSync(file)),v.sha256);saved[n]=v.sha256;}
 const actual=distFiles(),beforeDist=Object.fromEntries(Object.entries(saved).filter(([n])=>n.startsWith(DIST)));
 assert.deepEqual(a.completeCloudDistBefore,beforeDist);assert.deepEqual(a.completeCloudDistAfter,actual);
 const live={...actual,[EASTERN]:sha(fs.readFileSync(local(EASTERN)))},delta={};
 for(const name of [...new Set([...Object.keys(saved),...Object.keys(live)])].sort())if((saved[name]||null)!==(live[name]||null))delta[name]={beforeSha256:saved[name]||null,afterSha256:live[name]||null,originalBytes:before.preserved[name]?.originalBytes||null};
 assert.deepEqual(a.cloudProductChanges,delta,'Complete Cloud source/dist delta must be exact, including added and deleted files');
 for(const[name,digest]of Object.entries(prior.reportIdentityHashes)){
  const change=a.productChanges[name];
  if(name===SERVER){assert.equal(digest,old.productChanges[SERVER].afterSha256);assert.equal(sha(fs.readFileSync(local(name))),digest);assert.equal(sha(fs.readFileSync(local(old.productChanges[SERVER].originalBytes.path))),old.productChanges[SERVER].beforeSha256);continue;}
  if(change){const original=local(change.originalBytes.path);assert.equal(change.beforeSha256,digest);assert.equal(sha(fs.readFileSync(original)),digest);if(change.afterSha256===null)assert(!fs.existsSync(path.resolve(ROOT,name)));else assert.equal(sha(fs.readFileSync(local(name))),change.afterSha256);}
  else assert.equal(sha(fs.readFileSync(local(name))),digest,'Unauthorized old548 input drift: '+name);
 }
 const receiptName='06_验证与后续工作/负责人优化建议-卡组迁移-实施记录.json',receipt=read(receiptName);assert.equal(sha(fs.readFileSync(local(receiptName))),proof.receiptSHA256);assert.equal(Object.keys(receipt.reportIdentityHashes).length,516);
 const current={};for(const[name,digest]of Object.entries(receipt.reportIdentityHashes)){assert.equal(proof.verifiedSHA256[name],digest);const change=a.productChanges[name];if(change){assert.equal(change.beforeSha256,digest);if(change.afterSha256!==null)current[name]=change.afterSha256;}else current[name]=digest;}
 assert.deepEqual(a.currentStage30InputHashes,current);
 assert.deepEqual(a.currentExecutionBaseHashes,candidate.currentSourceAndBuildHashes);
 for(const[name,digest]of Object.entries(a.currentExecutionBaseHashes))assert.equal(sha(fs.readFileSync(local(name))),digest);
 for(const gate of Object.values(receipt.verification))checked(gate);
 return {path:AUTH,sha256:expectedSha,stage:31,revision:3,originalStage30ProductUnchanged:false,previousFinalProof:a.previousFinalProof,previousBaseline:a.previousBaseline,previousRepairProof:a.previousRepairProof,authorizedProductChanges:a.productChanges,currentInheritedInputHashes:current,currentExecutionBaseHashes:a.currentExecutionBaseHashes,boundary:'Exact accepted Python delta and explicit44 Cloud changes only; authorization is not acceptance and all old516/548 original bytes remain independently bound.'};
}
const REPAIR_PROOF='06_验证与后续工作/'+PREFIX+'-修复复验.json',REPAIR_CANDIDATE='06_验证与后续工作/'+PREFIX+'-修复复验-候选.json';

function verifySupportingComponents(proof){
 const previous=read(OLD_REPAIR),native=checked(previous.nativeConnectionComponent);
 assert(native.pass===true&&native.componentOnly===true&&native.nativeSQLiteOnly===true&&native.actualHttpCovered===false&&native.passed===4&&native.failed===0);
 assert.equal(native.source.sha256,sha(fs.readFileSync(local(SERVER))));assert.equal(sha(fs.readFileSync(local(native.helper.path))),native.helper.sha256);
 assert.deepEqual(proof.previousPythonNativeComponent,previous.nativeConnectionComponent);
 assert.deepEqual(proof.cloudSchemaComponent,{path:'06_验证与后续工作/负责人优化建议-本地可靠性Cloud安全短专项-35063d60f0cb42bb977e88c272be9d41.json',sha256:'cdedfdf163525fd3be391e7d180ab33d67afd712626cc67eb0ad7a02d7e4188e'});
 const c=checked(proof.cloudSchemaComponent);assert(c.pass===true&&c.status==='candidate-safety-passed'&&c.componentOnly===true&&c.businessAcceptance===false&&c.sourceUnchanged===true);assert.equal(c.runs.length,2);
 assert.equal(sha(fs.readFileSync(local(c.source.path.replaceAll('\\','/')))),c.source.sha256);assert.equal(c.candidateSourceAnchor.sha256,CANDIDATE_SHA);
 const checks=c.runs[1].checks;assert.equal(checks.length,8);assert(checks.every(r=>r.pass===true));assert.equal(new Set(checks.map(r=>r.name)).size,8);
 assert.equal(c.runs[0].cold.concurrency,1);assert.equal(c.runs[1].cold.concurrency,10);
 for(const k of ['CREATE','INSERT','PRAGMA'])assert.equal(c.runs[0].cold.kinds[k],c.runs[1].cold.kinds[k]);assert.equal(c.runs[0].cold.batchCount,c.runs[1].cold.batchCount);
 for(const r of c.runs){assert(r.cleanup.wrapperAlive===false&&r.cleanup.remainingTrackedPids.length===0&&r.cleanup.privateVarsRemaining===false);for(const[n,h]of Object.entries(r.native.inputHashes))assert.equal(proof.reportIdentityHashes[n],h);for(const[n,h]of Object.entries(r.native.runtimeDependencyHashes))assert.equal(sha(fs.readFileSync(local(n))),h);assert.equal(sha(fs.readFileSync(local(r.native.bundle.replaceAll('\\','/')))),r.native.bundleSha256);assert.equal(sha(fs.readFileSync(local(r.native.metafile.replaceAll('\\','/')))),r.native.metafileSha256);}
 assert.deepEqual(proof.boundedCloudDiagnostic,{path:'06_验证与后续工作/负责人优化建议-本地可靠性Cloud短诊断-802b7e53510d467582dce8e24a30fd5b.json',sha256:'13948d9bcbcb01f6ee1bdfdcea839621886ceebde8016cd74956a77006dd5fbd'});checked(proof.boundedCloudDiagnostic);
 return {previousPythonNativeComponent:proof.previousPythonNativeComponent,cloudSchemaComponent:proof.cloudSchemaComponent,boundedCloudDiagnostic:proof.boundedCloudDiagnostic};
}

function validateRepairProof(proofName,expectedProofSHA,expectedAuthSHA){
 const authorization=verifyAuthorization(expectedAuthSHA);
 assert([REPAIR_PROOF,REPAIR_CANDIDATE].includes(proofName));
 assert(/^[a-f0-9]{64}$/.test(expectedProofSHA||''));assert.equal(sha(fs.readFileSync(local(proofName))),expectedProofSHA);
 const proof=read(proofName);assert(proof.pass===true&&proof.stage===31&&proof.kind==='cloud-schema-singleflight-business-acceptance');
 assert.deepEqual(proof.perBackendPassed,{Python:195,Cloud:195});
 assert.deepEqual(proof.authorization,{path:AUTH,sha256:expectedAuthSHA});
 const checked=entry=>{assert(entry&&typeof entry.path==='string'&&/^[a-f0-9]{64}$/.test(entry.sha256));assert.equal(sha(fs.readFileSync(local(entry.path))),entry.sha256);return read(entry.path);};
 const snapshot=checked(proof.executionSnapshot),preflight=checked(proof.strictPreflight);
 assert(snapshot.pass===true&&snapshot.sourceAndBuildHashes&&Object.keys(snapshot.sourceAndBuildHashes).length===snapshot.inputCount);
 assert.equal(snapshot.canonicalSHA256,sha(JSON.stringify(snapshot.sourceAndBuildHashes)));
 assert.deepEqual(proof.reportIdentityHashes,snapshot.sourceAndBuildHashes);
 for(const[name,digest]of Object.entries(snapshot.sourceAndBuildHashes))assert.equal(sha(fs.readFileSync(local(name))),digest,'Current repaired execution input changed: '+name);
 assert(preflight.pass===true&&preflight.preparationOnly===false&&preflight.results.length===4&&preflight.results.every(row=>row.pass));
 assert.deepEqual(preflight.sourceAndBuildHashes,snapshot.sourceAndBuildHashes);assert.equal(preflight.entries.length,14);
 const counts={full:60,special:40,visual:4,'b11-compat':11,'card-compat':25,'privacy-compat':28,'closure-compat':27},seen=new Set(),totals={Python:0,Cloud:0};
 assert.equal(Object.keys(proof.verification).length,14);
 for(const entry of Object.values(proof.verification)){
  const doc=checked(entry),r=doc.latest||doc,m=r.cloudReliabilityRegressionLauncher;
  assert(m&&m.childExitCode===0&&m.reportFreshForInvocation===true&&m.identityUnchanged===true);
  assert(m.sourceUnchangedRelativeToRepairSnapshot===true&&m.cleanup?.resourceFactoryFinallyCompleted===true&&m.cleanup.ownedProcessInventoryComplete===true);
  assert.equal(m.cleanup.remainingOwnedPids.length,0);assert.equal(m.cleanup.privateVarsRemaining.length,0);
  const {target,suite}=m.actualInvocation;assert(['python','cloud'].includes(target)&&Object.hasOwn(counts,suite));const label=target+'/'+suite;assert(!seen.has(label));seen.add(label);
  assert(r.pass===true&&r.failed===0&&r.passed===counts[suite]&&entry.passed===r.passed);
  assert.deepEqual(m.sourceAndBuildHashes,snapshot.sourceAndBuildHashes);assert.deepEqual(m.preRunSnapshot.path,proof.executionSnapshot.path);assert.deepEqual(m.preRunSnapshot.sha256,proof.executionSnapshot.sha256);
  assert.equal(m.repairAuthorization.sha256,expectedAuthSHA);assert(Date.parse(m.invocationStarted)>=Date.parse(snapshot.at));
  if(target==='cloud')assert(m.runtimeArtifacts.length>0);
  for(const artifact of m.runtimeArtifacts){
   assert.equal(sha(fs.readFileSync(local(artifact.bundle))),artifact.bundleSha256);assert.equal(sha(fs.readFileSync(local(artifact.metafile))),artifact.metafileSha256);
   assert(artifact.preparationOnly===false&&artifact.originalBusinessOptionsPreserved===true&&artifact.rawReadsActualSourceBytes===true);
   const meta=read(artifact.metafile),actual={};
   for(const name of Object.keys(meta.inputs)){const unwrapped=name.replace(/^task-alert-owned-raw:/,''),file=path.isAbsolute(unwrapped)?unwrapped:path.resolve(ROOT,unwrapped),relative=path.relative(ROOT,file).replaceAll('\\','/');assert(!relative.startsWith('../'));actual[relative]=sha(fs.readFileSync(local(relative)));}
   assert.deepEqual(Object.keys(actual).sort(),Object.keys(artifact.inputHashes).sort());
   for(const[name,digest]of Object.entries(actual)){assert.equal(artifact.inputHashes[name],digest);assert.equal(snapshot.sourceAndBuildHashes[name],digest);}
   assert.equal(Object.keys(artifact.runtimeDependencyHashes).length,4);for(const[name,digest]of Object.entries(artifact.runtimeDependencyHashes))assert.equal(sha(fs.readFileSync(local(name))),digest);
  }
  totals[target==='python'?'Python':'Cloud']+=r.passed;
 }
 assert.deepEqual(totals,{Python:195,Cloud:195});verifySupportingComponents(proof);
 return {authorization,repairProof:{path:proofName,sha256:expectedProofSHA,stage:31,kind:proof.kind,pass:true,perBackendPassed:totals,
  executionSnapshot:proof.executionSnapshot,strictPreflight:proof.strictPreflight,previousPythonRepairProof:authorization.previousRepairProof,
  reportIdentityHashes:proof.reportIdentityHashes,originalStage30ProductUnchanged:false,toolchainIncludedInHandoff:false}};
}
function verifyRepairProof(expectedProofSHA,expectedAuthSHA){return validateRepairProof(REPAIR_PROOF,expectedProofSHA,expectedAuthSHA);}
function inspectRepairProof(expectedCandidateSHA,expectedAuthSHA){const result=validateRepairProof(REPAIR_CANDIDATE,expectedCandidateSHA,expectedAuthSHA);return {inspectionOnly:true,opsExecutionAllowed:false,pass:true,verifiedCandidate:{path:REPAIR_CANDIDATE,sha256:expectedCandidateSHA},authorization:result.authorization,perBackendPassed:result.repairProof.perBackendPassed,inputCount:Object.keys(result.repairProof.reportIdentityHashes).length};}

module.exports={ROOT,AUTH,PROOF,BASELINE,SERVER,REPAIR_PROOF,REPAIR_CANDIDATE,verifyAuthorization,verifyRepairProof,inspectRepairProof,verifySupportingComponents,sha,local,read,checked};

if(require.main===module){
 const a=Object.fromEntries(process.argv.slice(2).map(v=>{const i=v.indexOf('=');assert(v.startsWith('--'));return i<0?[v.slice(2),true]:[v.slice(2,i),v.slice(i+1)];}));
 if(!Object.keys(a).length)console.log(JSON.stringify({status:'prepared-not-run',stage:31,authorization:AUTH,repairProof:REPAIR_PROOF,startsService:false}));
 else try{let result;if(a['verify-authorization']){assert.deepEqual(Object.keys(a).sort(),['verify-authorization','authorization-sha256'].sort());result={authorization:verifyAuthorization(a['authorization-sha256'])};}else{const inspect=a['inspect-repair-proof']===true;assert.deepEqual(Object.keys(a).sort(),[inspect?'inspect-repair-proof':'verify-repair-proof','repair-proof-sha256','repair-authorization-sha256'].sort());result=inspect?inspectRepairProof(a['repair-proof-sha256'],a['repair-authorization-sha256']):verifyRepairProof(a['repair-proof-sha256'],a['repair-authorization-sha256']);}console.log(JSON.stringify({pass:true,stage:31,authorization:{path:result.authorization.path,sha256:result.authorization.sha256},...(result.repairProof?{repairProof:{path:result.repairProof.path,sha256:result.repairProof.sha256},perBackendPassed:result.repairProof.perBackendPassed,inputCount:Object.keys(result.repairProof.reportIdentityHashes).length}:{}),...(result.inspectionOnly?{inspectionOnly:true,opsExecutionAllowed:false}:{}),originalStage30ProductUnchanged:false,startsService:false}));}catch(e){console.error(JSON.stringify({pass:false,errorCode:e.code||e.name,message:e.message,startsService:false}));process.exitCode=1;}
}
