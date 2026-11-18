'use strict';
// Actual owned startup/control probes. These are never the forty-case acceptance suite.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {runOwned,resolveInvocation}=require('./负责人优化建议-八字样本验收启动.cjs');
const {identity,qaFiles,sha,redactText}=require('./负责人优化建议-八字样本测试工具.cjs');
const fixture=require('./负责人优化建议-八字样本夹具.json');
const ROOT=path.resolve(__dirname,'..'),PREFIX='负责人优化建议-八字样本',args=Object.fromEntries(process.argv.slice(2).filter(x=>x.startsWith('--')).map(x=>{const n=x.indexOf('=');return[x.slice(2,n<0?undefined:n),n<0?true:x.slice(n+1)];})),components=!!args.components,target=args.target||'all';
assert(['all','python','cloud'].includes(target));
const report={at:new Date().toISOString(),formalAcceptance:false,scope:'Actual isolated main and self-managed closure startup/control families; a startup probe is not a full compatibility or sample acceptance run.',preparationOnly:components,results:[],artifacts:[]};
const copy=value=>JSON.parse(JSON.stringify(value));
function pythonFullDatabaseSelection(){
 const file=path.join(__dirname,'全量回归.cjs'),text=fs.readFileSync(file,'utf8'),ts=require(path.join(ROOT,'04_研发源码/app/cloud/node_modules/typescript/lib/typescript.js')),ast=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS),declarations=[];
 function visit(node){if(ts.isVariableDeclaration(node)&&ts.isIdentifier(node.name)&&node.name.text==='db'&&node.initializer)declarations.push(node);ts.forEachChild(node,visit);}visit(ast);assert.equal(declarations.length,1,'Actual full runner declares exactly one database selection');
 const call=declarations[0].initializer;assert(ts.isCallExpression(call)&&ts.isPropertyAccessExpression(call.expression)&&call.expression.expression.getText(ast)==='path'&&call.expression.name.text==='join');assert.equal(call.arguments.length,2);assert.equal(call.arguments[0].getText(ast),'__dirname');const choice=call.arguments[1];assert(ts.isConditionalExpression(choice));
 const condition=choice.condition;assert(ts.isCallExpression(condition)&&ts.isPropertyAccessExpression(condition.expression)&&condition.expression.name.text==='test'&&condition.arguments.length===1&&condition.arguments[0].getText(ast)==='qaRequested');const regex=condition.expression.expression;assert.equal(regex.kind,ts.SyntaxKind.RegularExpressionLiteral);const literal=regex.getText(ast),end=literal.lastIndexOf('/'),matcher=new RegExp(literal.slice(1,end),literal.slice(end+1));assert(matcher.test(PREFIX),'The actual full runner must select an isolated database for the sample namespace');
 const yes=choice.whenTrue;assert(ts.isBinaryExpression(yes)&&yes.operatorToken.kind===ts.SyntaxKind.PlusToken&&ts.isStringLiteral(yes.right)&&yes.right.text==='.sqlite3');assert(ts.isBinaryExpression(yes.left)&&yes.left.operatorToken.kind===ts.SyntaxKind.PlusToken&&ts.isStringLiteral(yes.left.left)&&yes.left.left.text==='isolated-full-');const uuid=choice.whenTrue.left.right;assert(ts.isCallExpression(uuid)&&uuid.expression.getText(ast)==='crypto.randomUUID'&&uuid.arguments.length===0,'Fresh full databases use a real random UUID');assert(ts.isStringLiteral(choice.whenFalse)&&choice.whenFalse.text==='本轮回归专用.sqlite3');
 const syntheticName='isolated-full-'+crypto.randomUUID()+'.sqlite3',resolved=path.resolve(__dirname,syntheticName);assert.equal(path.dirname(resolved),path.resolve(__dirname));assert.notEqual(path.basename(resolved),choice.whenFalse.text);
 return {source:path.relative(ROOT,file).replaceAll('\\','/'),sourceSha256:sha(fs.readFileSync(file)),module:PREFIX,regex:literal,namespaceMatchesFreshBranch:true,selectedBasenamePattern:'isolated-full-<crypto.randomUUID()>.sqlite3',legacyNamedDatabaseSelected:false,actualSourceAstVerified:true,opensOrCreatesDatabase:false,scope:'Static proof of the actual child source selection. The separate formal full gate starts and tests its fresh database.'};
}
async function mainProbe(p){
 const c=await p.context(),observed={target:p.plan.target,family:p.plan.family,actualOuterStartup:true,actualBootstrap:true,checks:[],worker:null};
 async function call(route,data,expected=200,headers={},method=data===undefined?'GET':'POST'){
  const r=await c.fetch(p.base+route,{method,headers,...(data===undefined?{}:{data}),timeout:75000});let value;try{value=await r.json();}catch{value={error:'Non-JSON response'};}observed.checks.push({method,route,status:r.status(),expected});assert.equal(r.status(),expected,route+': '+(value.error||r.status()));return value;
 }
 await call('/__bazi-samples-test/control',{action:'sample-snapshot'},200,{'X-Bazi-Samples-Test':p.tokens.sample});
 await call('/__bazi-samples-test/control',{action:'sample-snapshot'},403,{'X-Bazi-Samples-Test':'wrong-owned-test-token'});
 await call('/__privacy-domains-test/control',{action:'domain-fault',enabled:false},200,{'X-Privacy-Domains-Test':p.tokens.privacy});
 await call('/__privacy-domains-test/control',{action:'domain-fault',enabled:false},403,{'X-Privacy-Domains-Test':'wrong-owned-test-token'});
 await call('/__unknown-sample-namespace/control',{action:'read'},404,{},'POST');
 const credential=p.plan.target==='python'?{username:'sp_'+p.runId.replace(/[^A-Za-z0-9_]/g,'_').slice(0,20),password:crypto.randomBytes(24).toString('hex'),name:'合成样本入口预检'}:JSON.parse(p.env.EW_CLOUD_QA_CREDENTIALS);
 await call('/api/auth/'+(p.plan.target==='python'?'setup':'login'),credential);
 const d=copy(fixture.baseDataset);d.setId='preflight_'+p.runId;const raw=Buffer.from(JSON.stringify(d)),imported=await call('/api/admin/bazi-samples/import',raw,200,{'Content-Type':'application/json','X-EW-Request-ID':'import_'+p.runId});assert.equal(imported.item.sourceBytesSha256,sha(raw));assert.equal(imported.item.sourceByteLength,raw.length);assert.equal(imported.item.teacherConfirmed,false);
 const created=await call('/api/admin/bazi-samples/runs',{requestId:'run_'+p.runId,setVersionId:imported.item.id,caseIds:[d.cases[0].caseId]});assert.equal(created.run.manifest.sourceBindingVerified,true);
 const processed=await call('/api/admin/bazi-samples/runs/'+created.run.id+'/process',{requestId:'process_'+p.runId,version:created.run.version,limit:1});assert.equal(processed.run.processed,1);assert.equal(processed.item.state,'succeeded');assert.equal(processed.item.domStatus,'not_run');assert.equal(processed.item.teacherConfirmed,false);
 const rawIndex=await call('/api/admin/bazi-samples/runs/'+created.run.id+'/cases/'+d.cases[0].caseId+'/raw');assert.equal(rawIndex.index.periods.length,10);
 const state=await call('/__bazi-samples-test/control',{action:'sample-worker-state'},200,{'X-Bazi-Samples-Test':p.tokens.sample});
 if(p.plan.target==='python'){
  assert.equal(state.actualManagedChildren,true);const compute=state.launches.filter(row=>row.operation==='compute');assert(compute.length);assert(compute.every(row=>row.pid>0&&row.exitCode===0&&row.stdoutBytes>0&&row.stdoutBytes<=4194304&&row.shell===false));assert(compute.every(row=>!row.environmentKeys.some(key=>/^EW_|SECRET|TOKEN|PASSWORD/i.test(key))));observed.worker={actualPythonHttpNodeChildren:true,pids:compute.map(row=>row.pid),stdoutBytes:compute.map(row=>row.stdoutBytes),nodeSha256:compute[0].nodeSha256,workerSha256:compute[0].workerSha256,environmentKeysOnly:compute[0].environmentKeys};
 }else{assert.equal(state.actualManagedChildren,false);assert(state.calls.some(row=>row.ok));observed.worker={actualWorkerImportedComputation:true,nodeChildApplicable:false};}
 report.artifacts.push(...p.runtimeArtifacts);return observed;
}
async function closureProbe(p){
 const module=PREFIX+'注销兼容入口组件',filename=module+'-'+p.plan.target+'-'+p.runId+'.json',script="const assert=require('node:assert/strict');const {makeHarness}=require('./06_验证与后续工作/负责人优化建议-八字样本注销兼容测试工具.cjs');const h=makeHarness();(async()=>{try{await h.start();await h.check('Actual new closure wrapper/private control startup',async()=>{const right=await h.control({});assert.equal(right.isolated,true);const c=await h.context(),wrong=await c.post(h.base+'/__closure-test/mock',{headers:{'X-Privacy-Test':'wrong-owned-test-token'},data:{}});assert.equal(wrong.status(),403);});h.report.formalAcceptance=false;h.report.preparationOnly="+JSON.stringify(components)+";await h.finish();}catch(error){await h.finish(error);}})();";
 const child=p.startOwned(process.execPath,['--require',path.join(__dirname,PREFIX+'脱敏前置.cjs'),'-e',script,'component','--target='+p.plan.target,'--module='+module,'--report='+filename]);let code;
 try{code=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',resolve);});}finally{await p.stopOwned(child);}
 assert.equal(code,0,'Actual self-managed closure entry probe');const doc=JSON.parse(fs.readFileSync(path.join(__dirname,filename),'utf8')),r=doc.latest||doc;assert.equal(r.passed,1);assert.equal(r.failed,0);assert.equal(r.identityUnchanged,true);report.artifacts.push(...(r.runtimeArtifacts||[]));return {target:p.plan.target,family:'closure',actualSelfManagedStartup:true,actualBootstrap:false,probeReport:filename,probeReportSha256:sha(fs.readFileSync(path.join(__dirname,filename))),privateControlAndWrongTokenCovered:true,ownedState:r.ownedState||null,ownedDatabase:r.ownedDatabase||null};
}
(async()=>{try{
 const targets=target==='all'?['python','cloud']:[target];
 report.pendingFixedQaInputs=qaFiles.filter(name=>!fs.existsSync(path.join(__dirname,PREFIX+name)));if(!components)assert.deepEqual(report.pendingFixedQaInputs,[],'Strict preflight requires every fixed QA input');
 report.entries=targets.flatMap(t=>['full','special','visual','b11-compat','interpretation-compat','privacy-compat','closure-compat'].map(s=>resolveInvocation(t,s)));
 report.pythonFullDatabaseSelection=pythonFullDatabaseSelection();
 families:for(const t of targets)for(const [suite,probe]of [['special',mainProbe],['closure-compat',closureProbe]]){
  try{const observed=await runOwned({target:t,suite,probe,preparation:components});report.results.push({name:t+'/'+suite+' actual startup',pass:true,observed});console.log('PASS '+t+'/'+suite+' actual startup');}
  catch(error){report.results.push({name:t+'/'+suite+' actual startup',pass:false,error:redactText(error.stack||error)});console.log('FAIL '+t+'/'+suite+' actual startup');break families;}
 }
 report.sourceAndBuildHashes=identity({preparation:components});report.inputCount=Object.keys(report.sourceAndBuildHashes).length;report.canonicalSHA256=sha(Buffer.from(JSON.stringify(report.sourceAndBuildHashes)));report.incompleteMap=report.pendingFixedQaInputs.length>0;report.pass=report.results.length===targets.length*2&&report.results.every(r=>r.pass);
 }catch(error){report.pass=false;report.error=redactText(error.stack||error);}finally{
 const output=path.join(__dirname,PREFIX+'入口预检-'+target+'-'+Date.now().toString(36)+'-'+crypto.randomBytes(4).toString('hex')+'.json');fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({pass:report.pass,formalAcceptance:false,preparationOnly:components,incompleteMap:report.incompleteMap,checks:report.results.length,report:path.relative(ROOT,output)}));process.exitCode=report.pass?0:1;
 }})();
