'use strict';
// Read-only authorization. No mismatch bypass or product path wildcard exists.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..'),OUT=__dirname;
const PROOF='06_验证与后续工作/负责人优化建议-卡组迁移-最终交付核验.json';
const PROOF_SHA='752e36ad70d6812727849f0fa49262c426ef161a911b59f66831cd0617e12f07';
const BASELINE='06_验证与后续工作/负责人优化建议-本地可靠性-实施前核对.json';
const BASELINE_SHA='6fe9d95b438cc5a638ae534f01cbf7f6298f6bd1ab3201b1f4324d507eb06919';
const AUTH='06_验证与后续工作/负责人优化建议-本地可靠性性能修复授权基线-rev2.json';
const SERVER='04_研发源码/app/r4/backend/server.py';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
function local(name){assert(typeof name==='string'&&!path.isAbsolute(name)&&!name.includes('\\')&&!name.split('/').includes('..'));const file=path.resolve(ROOT,name);assert(file.startsWith(ROOT+path.sep)&&fs.statSync(file).isFile());return file;}
function read(name){return JSON.parse(fs.readFileSync(local(name),'utf8'));}
function verifyAuthorization(expectedSha){
 assert(/^[a-f0-9]{64}$/.test(expectedSha||''),'Exact root-authored repair authorization SHA required');
 assert.equal(sha(fs.readFileSync(local(AUTH))),expectedSha);
 assert.equal(sha(fs.readFileSync(local(PROOF))),PROOF_SHA);
 assert.equal(sha(fs.readFileSync(local(BASELINE))),BASELINE_SHA);
 const a=read(AUTH),proof=read(PROOF),baseline=read(BASELINE);
 assert(a.schemaVersion===1&&a.revision===2&&a.stage===31&&a.authorizedByRoot===true);
 assert.equal(a.originalStage30ProductUnchanged,false);
 assert.deepEqual(a.previousFinalProof,{path:PROOF,sha256:PROOF_SHA});
 assert.deepEqual(a.previousBaseline,{path:BASELINE,sha256:BASELINE_SHA});
 assert(proof.pass===true&&proof.stage===30&&proof.allFourteenGatesPassedWithFreshSuccessfulChildren===true);
 assert.deepEqual(proof.perBackendPassed,{Python:195,Cloud:195});
 const receiptName='06_验证与后续工作/负责人优化建议-卡组迁移-实施记录.json',receipt=read(receiptName);
 assert.equal(sha(fs.readFileSync(local(receiptName))),proof.receiptSHA256);
 assert.equal(Object.keys(receipt.reportIdentityHashes).length,516);
 assert.deepEqual(Object.keys(a.productChanges),[SERVER],'Only the explicitly authorized server.py delta is permitted');
 const delta=a.productChanges[SERVER];
 assert.equal(delta.beforeSha256,receipt.reportIdentityHashes[SERVER]);
 assert(/^[a-f0-9]{64}$/.test(delta.afterSha256)&&delta.afterSha256!==delta.beforeSha256);
 assert.equal(delta.originalBytes.sha256,delta.beforeSha256);
 const original=local(delta.originalBytes.path);
 assert(path.dirname(original)===OUT&&path.basename(original).startsWith('负责人优化建议-本地可靠性'));
 assert.equal(sha(fs.readFileSync(original)),delta.beforeSha256,'Original Stage30 server bytes must remain preserved');
 const current={};
 for(const[name,digest]of Object.entries(receipt.reportIdentityHashes)){
  assert.equal(proof.verifiedSHA256[name],digest);
  const expected=name===SERVER?delta.afterSha256:digest;
  assert.equal(sha(fs.readFileSync(local(name))),expected,'Unexpected Stage30 source/build/QA drift: '+name);
  current[name]=expected;
 }
 assert.deepEqual(a.currentStage30InputHashes,current,'Root must explicitly approve the entire current inherited input set');
 for(const gate of Object.values(receipt.verification))assert.equal(sha(fs.readFileSync(local(gate.path))),gate.sha256);
 assert.equal(baseline.nextLocalStage,31);
 return {path:AUTH,sha256:expectedSha,stage:31,revision:2,originalStage30ProductUnchanged:false,
  previousFinalProof:{path:PROOF,sha256:PROOF_SHA},previousBaseline:{path:BASELINE,sha256:BASELINE_SHA},
  authorizedProductChanges:a.productChanges,currentInheritedInputHashes:current,
  boundary:'The completed Stage30 proof and all unchanged inherited inputs remain exact. Only the root-bound preserved server.py delta is accepted; this is not a skip-proof flag.'};
}
const REPAIR_PROOF='06_验证与后续工作/负责人优化建议-本地可靠性-性能修复复验.json';
const REPAIR_CANDIDATE='06_验证与后续工作/负责人优化建议-本地可靠性-性能修复复验-候选.json';
function validateRepairProof(proofName,expectedProofSHA,expectedAuthSHA){
 const authorization=verifyAuthorization(expectedAuthSHA);
 assert([REPAIR_PROOF,REPAIR_CANDIDATE].includes(proofName));
 assert(/^[a-f0-9]{64}$/.test(expectedProofSHA||''));assert.equal(sha(fs.readFileSync(local(proofName))),expectedProofSHA);
 const proof=read(proofName);assert(proof.pass===true&&proof.stage===31&&proof.kind==='performance-fix-business-acceptance');
 assert.deepEqual(proof.perBackendPassed,{Python:195,Cloud:195});
 assert.deepEqual(proof.authorization,{path:AUTH,sha256:expectedAuthSHA});
 const checked=entry=>{assert(entry&&typeof entry.path==='string'&&/^[a-f0-9]{64}$/.test(entry.sha256));assert.equal(sha(fs.readFileSync(local(entry.path))),entry.sha256);return read(entry.path);};
 const snapshot=checked(proof.executionSnapshot),preflight=checked(proof.strictPreflight),component=checked(proof.nativeConnectionComponent);
 assert(snapshot.pass===true&&snapshot.sourceAndBuildHashes&&Object.keys(snapshot.sourceAndBuildHashes).length===snapshot.inputCount);
 assert.equal(snapshot.canonicalSHA256,sha(JSON.stringify(snapshot.sourceAndBuildHashes)));
 assert.deepEqual(proof.reportIdentityHashes,snapshot.sourceAndBuildHashes);
 for(const[name,digest]of Object.entries(snapshot.sourceAndBuildHashes))assert.equal(sha(fs.readFileSync(local(name))),digest,'Current repaired execution input changed: '+name);
 assert(preflight.pass===true&&preflight.preparationOnly===false&&preflight.results.length===4&&preflight.results.every(row=>row.pass));
 assert.deepEqual(preflight.sourceAndBuildHashes,snapshot.sourceAndBuildHashes);assert.equal(preflight.entries.length,14);
 assert(component.pass===true&&component.componentOnly===true&&component.nativeSQLiteOnly===true&&component.passed===4&&component.failed===0);
 assert.equal(proof.nativeConnectionComponent.passed,4);assert.equal(component.actualHttpCovered,false);assert.equal(component.source.sha256,authorization.authorizedProductChanges[SERVER].afterSha256);
 assert.equal(sha(fs.readFileSync(local(component.helper.path))),component.helper.sha256);
 const counts={full:60,special:40,visual:4,'b11-compat':11,'card-compat':25,'privacy-compat':28,'closure-compat':27},seen=new Set(),totals={Python:0,Cloud:0};
 assert.equal(Object.keys(proof.verification).length,14);
 for(const entry of Object.values(proof.verification)){
  const doc=checked(entry),r=doc.latest||doc,m=r.localReliabilityRegressionLauncher;
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
 assert.deepEqual(totals,{Python:195,Cloud:195});
 return {authorization,repairProof:{path:proofName,sha256:expectedProofSHA,stage:31,kind:proof.kind,pass:true,perBackendPassed:totals,
  executionSnapshot:proof.executionSnapshot,strictPreflight:proof.strictPreflight,nativeConnectionComponent:proof.nativeConnectionComponent,
  reportIdentityHashes:proof.reportIdentityHashes,originalStage30ProductUnchanged:false,toolchainIncludedInHandoff:false}};
}
function verifyRepairProof(expectedProofSHA,expectedAuthSHA){return validateRepairProof(REPAIR_PROOF,expectedProofSHA,expectedAuthSHA);}
function inspectRepairProof(expectedCandidateSHA,expectedAuthSHA){const result=validateRepairProof(REPAIR_CANDIDATE,expectedCandidateSHA,expectedAuthSHA);return {inspectionOnly:true,opsExecutionAllowed:false,pass:true,verifiedCandidate:{path:REPAIR_CANDIDATE,sha256:expectedCandidateSHA},authorization:result.authorization,perBackendPassed:result.repairProof.perBackendPassed,inputCount:Object.keys(result.repairProof.reportIdentityHashes).length};}
module.exports={verifyAuthorization,verifyRepairProof,inspectRepairProof,AUTH,PROOF,BASELINE,REPAIR_PROOF,REPAIR_CANDIDATE,SERVER,sha,local};
if(require.main===module){
 const values=process.argv.slice(2);
 if(!values.length)console.log(JSON.stringify({status:'prepared-not-run',stage:31,authorization:AUTH,repairProof:REPAIR_PROOF,authorizedChangedPaths:[SERVER],opensDatabase:false,startsService:false}));
 else{const a=Object.fromEntries(values.map(v=>{assert(v.startsWith('--'));const i=v.indexOf('=');return i<0?[v.slice(2),true]:[v.slice(2,i),v.slice(i+1)];}));assert.equal(values.length,Object.keys(a).length);
  try{const inspect=a['inspect-repair-proof']===true;assert.deepEqual(Object.keys(a).sort(),[inspect?'inspect-repair-proof':'verify-repair-proof','repair-proof-sha256','repair-authorization-sha256'].sort());assert.equal(a[inspect?'inspect-repair-proof':'verify-repair-proof'],true);if(inspect)console.log(JSON.stringify(inspectRepairProof(a['repair-proof-sha256'],a['repair-authorization-sha256'])));else{const verified=verifyRepairProof(a['repair-proof-sha256'],a['repair-authorization-sha256']);console.log(JSON.stringify({pass:true,stage:31,authorization:{path:AUTH,sha256:a['repair-authorization-sha256']},repairProof:{path:REPAIR_PROOF,sha256:a['repair-proof-sha256']},perBackendPassed:verified.repairProof.perBackendPassed,inputCount:Object.keys(verified.repairProof.reportIdentityHashes).length,originalStage30ProductUnchanged:false,startsService:false}));}}
  catch(error){console.error(JSON.stringify({pass:false,stage:31,errorCode:error.code||error.name,startsService:false}));process.exitCode=1;}
 }
}
