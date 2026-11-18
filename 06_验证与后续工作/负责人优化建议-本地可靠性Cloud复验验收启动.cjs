'use strict';
// Fresh Stage30 resource factory is reused read-only; its old formal path is never called.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const factory=require('./负责人优化建议-卡组迁移验收启动.cjs');
const h=require('./负责人优化建议-本地可靠性Cloud复验测试工具.cjs');
const gate=require('./负责人优化建议-本地可靠性Cloud复验修复基线.cjs');
const catalog=require('./负责人优化建议-本地可靠性Cloud复验入口清单.json');
const execFile=require('node:util').promisify(require('node:child_process').execFile);
async function ownedProcesses(){
 assert.equal(process.platform,'win32','Current owned cleanup inventory supports the actual Windows lab only');
 const script="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$all=@(Get-CimInstance Win32_Process);$ids=[System.Collections.Generic.HashSet[int]]::new();[void]$ids.Add("+process.pid+");do{$n=$ids.Count;foreach($r in $all){if($ids.Contains([int]$r.ParentProcessId)){[void]$ids.Add([int]$r.ProcessId)}}}while($n -ne $ids.Count);@($all|Where-Object{$ids.Contains([int]$_.ProcessId) -and $_.ProcessId -ne "+process.pid+"}|Select-Object ProcessId,ParentProcessId,CreationDate,Name,ExecutablePath)|ConvertTo-Json -Compress";
 const r=await execFile(path.join(process.env.SystemRoot||'C:\\Windows','System32/WindowsPowerShell/v1.0/powershell.exe'),['-NoProfile','-NonInteractive','-Command',script],{windowsHide:true,encoding:'utf8',timeout:15000,maxBuffer:1048576});const value=r.stdout.trim()?JSON.parse(r.stdout):[];return (Array.isArray(value)?value:[value]).map(row=>({...row,executableSha256:row.ExecutablePath&&fs.existsSync(row.ExecutablePath)?h.sha(fs.readFileSync(row.ExecutablePath)):null}));
}
async function cleanupEvidence(before,artifacts){
 const compilerServices=before.filter(row=>row.Name==='esbuild.exe');
 if(artifacts.length){for(const artifact of artifacts){assert.equal(Object.keys(artifact.runtimeDependencyHashes).length,4);for(const[name,digest]of Object.entries(artifact.runtimeDependencyHashes))assert.equal(h.sha(fs.readFileSync(gate.local(name))),digest);}require(path.join(h.ROOT,'04_研发源码/app/cloud/node_modules/esbuild/lib/main.js')).stop();}
 const alive=await ownedProcesses(),remaining=alive.filter(row=>before.some(old=>old.ProcessId===row.ProcessId&&old.CreationDate===row.CreationDate));
 const files=new Set(artifacts.map(row=>path.join(path.dirname(path.resolve(h.ROOT,row.bundle)),'.dev.vars')));
 for(const file of files)assert(file.startsWith(path.join(h.ROOT,'04_研发源码/app/cloud/.wrangler')+path.sep));
 const privateVarsRemaining=[...files].filter(file=>fs.existsSync(file)).map(file=>path.relative(h.ROOT,file));
 assert.equal(remaining.length,0,'Owned descendants survived resource factory finally');assert.equal(privateVarsRemaining.length,0,'Owned private vars survived cleanup');
 return {resourceFactoryFinallyCompleted:true,ownedProcessInventoryComplete:true,trackedOwnedProcesses:before,trackedCompilerServices:compilerServices,fixedCompilerSdkStopRequested:artifacts.length>0,remainingOwnedPids:[],privateVarsRemaining,privateVarsChecked:[...files].map(file=>path.relative(h.ROOT,file))};
}
function resolveInvocation(target,suite){
 assert(catalog.targets.includes(target)&&Object.hasOwn(catalog.suites,suite));
 const full=suite==='full',closure=suite==='closure-compat';
 const labels={special:'专项',visual:'补充视觉','b11-compat':'B11兼容','privacy-compat':'逐域兼容','card-compat':'抽卡兼容'};
 const module=full?catalog.fullNamespaceAlias:closure?catalog.closureNamespaceAlias:h.PREFIX+labels[suite];
 const entry=full?(target==='python'?'全量回归.cjs':'公网适配全量回归.cjs'):closure?'负责人优化建议-卡组迁移注销兼容.cjs':suite==='privacy-compat'?'负责人优化建议-隐私逐域专项.cjs':suite==='card-compat'?'负责人优化建议-卡组迁移抽卡兼容.cjs':'负责人优化建议-卡组迁移'+labels[suite]+'.cjs';
 const report=full?module+'-'+(target==='python'?'本轮':'公网适配')+'全量回归结果.json':h.PREFIX+'-'+suite+'-'+target+'.json';
 const argv=['--module='+module,...(full?['--bazi-stage=4',...(target==='python'?['--admin']:[])]:['--target='+target,'--report='+report])];
 return {target,suite,module,entry:'06_验证与后续工作/'+entry,report,argv,expectedCount:catalog.suites[suite],
  resourceSuite:suite,family:closure?'closure':full&&target==='python'?'product-full':'main'};
}
async function run({target,suite,authorizationSha256,snapshot,snapshotSha256,probe}){
 assert.equal(catalog.formalReady,true,'This new plan requires an exact authorized source/build delta');
 const authorization=gate.verifyAuthorization(authorizationSha256),anchor=h.verifySnapshot(snapshot,snapshotSha256),plan=resolveInvocation(target,suite),before=h.identity();
 const runId=Date.now().toString(36)+'-'+crypto.randomBytes(5).toString('hex'),began=Date.now();let actual,probeObservation,pendingReport;let tracked=[],allArtifacts=[],cleanError=value=>String(value).replace(/ew_session=[^;\s"']+/g,'ew_session=[REDACTED]');
 try{
  await factory.runOwned({target,suite:plan.resourceSuite,probe:async p=>{
   actual={resourceRunId:p.runId,ownedDatabase:p.ownedDatabase?path.relative(h.ROOT,p.ownedDatabase):null,ownedState:p.ownedState?path.relative(h.ROOT,p.ownedState):null};
   cleanError=value=>p.clean(String(value)).replace(/ew_session=[^;\s"']+/g,'ew_session=[REDACTED]');
   if(probe){try{probeObservation=await probe({...p,actualPlan:plan,authorization,anchor});allArtifacts=[...p.runtimeArtifacts,...(probeObservation.runtimeArtifacts||[])];return probeObservation;}finally{tracked=await ownedProcesses();}}
   const reportFile=path.join(__dirname,plan.report),prior=fs.existsSync(reportFile)?fs.readFileSync(reportFile):null;
   if(prior)fs.writeFileSync(path.join(__dirname,h.PREFIX+'-原报告前存-'+target+'-'+suite+'-'+runId+'.json'),prior,{flag:'wx'});
   const old=prior?JSON.parse(prior):null,tag=value=>JSON.stringify([value?.at,value?.runId||null]);
   const previousTag=tag(old?.latest||old),started=Date.now();
   const argv=['--require',path.join(__dirname,'负责人优化建议-卡组迁移脱敏前置.cjs'),'--require',path.join(__dirname,'负责人优化建议-本地可靠性Cloud复验脱敏前置.cjs'),path.join(h.ROOT,plan.entry),...plan.argv,...(p.base&&plan.family!=='closure'?['--base='+p.base]:[])];
   const child=p.startOwned(process.execPath,argv);child.stdout?.on('data',data=>process.stdout.write(p.clean(data)));child.stderr?.on('data',data=>process.stderr.write(p.clean(data)));
   const code=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',resolve);});
   assert.deepEqual(h.identity(),before);
   const bytes=fs.existsSync(reportFile)?fs.readFileSync(reportFile):null,doc=bytes?JSON.parse(bytes):null,current=doc?.latest||doc;
   assert(current&&tag(current)!==previousTag&&Date.parse(current.at)>=started&&(!prior||!bytes.equals(prior)),'No fresh child report; old report is not relabelled');
   assert.equal(code,0);assert.equal(current.pass,true);assert.equal(current.failed,0);assert.equal(current.passed,plan.expectedCount);
   const artifacts=plan.family==='closure'?(current.runtimeArtifacts||[]):p.runtimeArtifacts;
    allArtifacts=[...artifacts];
   if(target==='cloud')assert(artifacts.length>0,'Actual native compiler artifacts required');
   for(const artifact of artifacts){for(const[name,digest]of Object.entries(artifact.inputHashes||{}))assert.equal(before[name],digest,'Compiler input absent or different in current complete map');}
   current.cloudReliabilityRegressionLauncher={runId,resourceRunId:p.runId,actualInvocation:plan,resourceFactoryPlan:p.plan,
    childExitCode:code,reportFreshForInvocation:true,identityUnchanged:true,invocationStarted:new Date(started).toISOString(),
    sourceAndBuildHashes:before,preRunSnapshot:anchor,repairAuthorization:authorization,originalStage30ProductUnchanged:false,
    sourceUnchangedRelativeToRepairSnapshot:true,runtimeArtifacts:artifacts,buildPreparationInputs:h.buildPreparationInputs(),
    syntheticOnly:true,productionEnabled:false,actualOwnedState:actual};
   if(doc.runs?.length)doc.runs[doc.runs.length-1]=current;
   fs.writeFileSync(reportFile,JSON.stringify(doc,null,2)+'\n');
    pendingReport={file:reportFile,doc,current};tracked=await ownedProcesses();
  }});
   assert.deepEqual(h.identity(),before);const cleanup=await cleanupEvidence(tracked,allArtifacts);
   if(pendingReport){pendingReport.current.cloudReliabilityRegressionLauncher.cleanup=cleanup;fs.writeFileSync(pendingReport.file,JSON.stringify(pendingReport.doc,null,2)+'\n');}
   return {pass:true,plan,runId,actual,probeObservation,cleanup,resourceFactoryFinallyCompleted:true};
 }catch(error){
  const file=path.join(__dirname,h.PREFIX+'-启动诊断-'+target+'-'+suite+'-'+runId+'.json');
  fs.writeFileSync(file,JSON.stringify({pass:false,at:new Date().toISOString(),startedAt:new Date(began).toISOString(),runId,plan,actual,anchor,
   originalStage30ProductUnchanged:false,reportFreshForInvocation:false,originalReportPreserved:true,errorCode:error.code||error.name,errorStack:cleanError(error.stack||error.name).slice(0,2500),
   message:'The new managed invocation failed; original child report/artifacts are preserved. See live redacted console for the fixed assertion.',productionEnabled:false},null,2)+'\n',{flag:'wx'});throw error;
 }
}
function args(argv){const entries=argv.map(value=>{assert(value.startsWith('--'));const i=value.indexOf('=');return i<0?[value.slice(2),true]:[value.slice(2,i),value.slice(i+1)];});assert.equal(new Set(entries.map(([k])=>k)).size,entries.length);return Object.fromEntries(entries);}
module.exports={resolveInvocation,run,args};
if(require.main===module){const a=args(process.argv.slice(2));if(!Object.keys(a).length||a.describe)console.log(JSON.stringify({status:'prepared-not-run',formalReady:catalog.formalReady,entries:catalog.targets.flatMap(t=>Object.keys(catalog.suites).map(s=>resolveInvocation(t,s)))}));else{
 assert.deepEqual(Object.keys(a).sort(),['target','suite','authorization-sha256','snapshot','snapshot-sha256'].sort());
 run({target:a.target,suite:a.suite,authorizationSha256:a['authorization-sha256'],snapshot:a.snapshot,snapshotSha256:a['snapshot-sha256']}).then(result=>console.log(JSON.stringify(result))).catch(error=>{console.error(JSON.stringify({pass:false,errorCode:error.code||error.name,message:'New managed repair regression failed; diagnostic preserved.'}));process.exitCode=1;});
}}
