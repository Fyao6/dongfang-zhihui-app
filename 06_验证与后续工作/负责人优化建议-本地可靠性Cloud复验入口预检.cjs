'use strict';
// No service is started by import/default describe. Four owned startups require
// the exact new repair authorization and independent pre-run input snapshot.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const outer=require('./负责人优化建议-本地可靠性Cloud复验验收启动.cjs');
const h=require('./负责人优化建议-本地可靠性Cloud复验测试工具.cjs');
const catalog=require('./负责人优化建议-本地可靠性Cloud复验入口清单.json');
function fullFreshSelection(){
 const file=path.join(__dirname,'全量回归.cjs'),ts=require(path.join(h.ROOT,'04_研发源码/app/cloud/node_modules/typescript/lib/typescript.js'));
 const text=fs.readFileSync(file,'utf8'),tree=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS),found=[];
 const walk=n=>{if(ts.isVariableDeclaration(n)&&ts.isIdentifier(n.name)&&n.name.text==='db')found.push(n.initializer);ts.forEachChild(n,walk);};walk(tree);assert.equal(found.length,1);
 const call=found[0];assert(ts.isCallExpression(call)&&call.expression.getText(tree)==='path.join'&&call.arguments[0].getText(tree)==='__dirname');
 const choice=call.arguments[1];assert(ts.isConditionalExpression(choice));const test=choice.condition;assert(ts.isCallExpression(test)&&test.expression.name.text==='test'&&test.arguments[0].getText(tree)==='qaRequested');
 const literal=test.expression.expression.getText(tree),at=literal.lastIndexOf('/'),matcher=new RegExp(literal.slice(1,at),literal.slice(at+1));assert(matcher.test(catalog.fullNamespaceAlias));
 assert.equal(choice.whenTrue.getText(tree),"'isolated-full-'+crypto.randomUUID()+'.sqlite3'");assert.equal(choice.whenFalse.text,'本轮回归专用.sqlite3');
 return {actualSource:file,sha256:h.sha(fs.readFileSync(file)),module:catalog.fullNamespaceAlias,namespaceMatchesFreshBranch:true,actualAstVerified:true,opensDatabase:false};
}
async function mainProbe(p){
 const c=await p.context(),checks=[];
 const call=async(route,data,expected=200,headers={})=>{const r=await c.fetch(p.base+route,{method:data===undefined?'GET':'POST',headers,...(data===undefined?{}:{data})});checks.push({route,status:r.status(),expected});assert.equal(r.status(),expected);return expected===200?r.json():null;};
 await call('/__card-migration-test/control',{action:'card-snapshot'},200,{'X-Card-Migration-Test':p.tokens.card});
 await call('/__card-migration-test/control',{action:'card-snapshot'},403,{'X-Card-Migration-Test':'wrong-owned-token'});
 await call('/__privacy-domains-test/control',{action:'domain-fault',enabled:false},200,{'X-Privacy-Domains-Test':p.tokens.privacy});
 await call('/__privacy-domains-test/control',{action:'domain-fault',enabled:false},403,{'X-Privacy-Domains-Test':'wrong-owned-token'});
 await call('/__unknown-repair-namespace/control',{action:'read'},404);
 const credential=p.plan.target==='python'?{username:'repair_'+p.runId.replace(/[^a-z0-9]/gi,'').slice(0,18),password:crypto.randomBytes(24).toString('hex'),name:'性能复验入口管理员'}:JSON.parse(p.env.EW_CLOUD_QA_CREDENTIALS);
 await call('/api/auth/'+(p.plan.target==='python'?'setup':'login'),credential);
 const status=await call('/api/auth/status');assert.equal(status.user.role,'admin');
 return {actualStartup:true,actualPrivateControls:true,wrongTokenRejected:true,wrongNamespaceRejected:true,checks,runtimeArtifacts:p.runtimeArtifacts};
}
async function closureProbe(p){
 const filename=h.PREFIX+'-注销入口组件-'+p.plan.target+'-'+p.runId+'.json';
 const script="const assert=require('node:assert/strict');const {makeHarness}=require('./06_验证与后续工作/负责人优化建议-卡组迁移注销兼容测试工具.cjs');const h=makeHarness();(async()=>{try{await h.start();await h.check('Actual closure wrapper and token controls',async()=>{assert.equal((await h.control({})).isolated,true);const c=await h.context(),r=await c.post(h.base+'/__closure-test/mock',{headers:{'X-Privacy-Test':'wrong-owned-token'},data:{}});assert.equal(r.status(),403);});h.report.formalAcceptance=false;await h.finish();}catch(e){await h.finish(e);}})();";
 const child=p.startOwned(process.execPath,['--require',path.join(__dirname,'负责人优化建议-卡组迁移脱敏前置.cjs'),'-e',script,'component','--target='+p.plan.target,'--module='+catalog.closureNamespaceAlias+'入口组件','--report='+filename]);
 const code=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('exit',resolve);});assert.equal(code,0);
 const file=path.join(__dirname,filename),doc=JSON.parse(fs.readFileSync(file,'utf8')),report=doc.latest||doc;assert(report.pass&&report.passed===1&&report.failed===0&&report.identityUnchanged);
 return {actualSelfManagedStartup:true,probeReport:{path:path.relative(h.ROOT,file),sha256:h.sha(fs.readFileSync(file))},inlineChildSha256:h.sha(script),runtimeArtifacts:report.runtimeArtifacts||[]};
}
async function run(a){
 assert.equal(a.target,'all','Strict preflight covers all four actual startup families');
 assert.equal(catalog.formalReady,true);const before=h.identity(),report={at:new Date().toISOString(),formalAcceptance:false,preparationOnly:false,results:[],pythonFullDatabaseSelection:fullFreshSelection(),entries:catalog.targets.flatMap(t=>Object.keys(catalog.suites).map(s=>outer.resolveInvocation(t,s)))};
 assert.deepEqual(report.entries,catalog.entries);assert.equal(report.entries.length,14);assert.equal(new Set(report.entries.map(p=>p.report)).size,14);
 try{for(const target of catalog.targets)for(const [suite,probe]of [['special',mainProbe],['closure-compat',closureProbe]]){
  const observed=await outer.run({target,suite,authorizationSha256:a['authorization-sha256'],snapshot:a.snapshot,snapshotSha256:a['snapshot-sha256'],probe});
  report.results.push({name:target+'/'+suite,pass:true,resource:observed});
 }assert.deepEqual(h.identity(),before);report.pass=report.results.length===4;}
 catch(error){report.pass=false;report.errorCode=error.code||error.name;}
 report.sourceAndBuildHashes=before;report.inputCount=Object.keys(before).length;report.canonicalSHA256=h.sha(JSON.stringify(before));
 const output=path.join(__dirname,h.PREFIX+'-入口预检-'+Date.now()+'-'+crypto.randomBytes(4).toString('hex')+'.json');fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n',{flag:'wx'});
 console.log(JSON.stringify({pass:report.pass,checks:report.results.length,report:path.relative(h.ROOT,output),sha256:h.sha(fs.readFileSync(output)),formalAcceptance:false}));if(!report.pass)process.exitCode=1;
}
module.exports={fullFreshSelection,mainProbe,closureProbe,run};
if(require.main===module){const a=outer.args(process.argv.slice(2));if(!Object.keys(a).length)console.log(JSON.stringify({status:'prepared-not-run',formalReady:catalog.formalReady,actualStartupFamilies:0,plannedStartupFamilies:4}));else run(a).catch(error=>{console.error(JSON.stringify({pass:false,errorCode:error.code||error.name,actualStartupClaimed:false}));process.exitCode=1;});}
