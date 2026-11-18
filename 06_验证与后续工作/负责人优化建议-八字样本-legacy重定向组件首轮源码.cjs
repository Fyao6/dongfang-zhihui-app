'use strict';
// Non-formal native workerd + fresh D1 + real loopback HTTP. Only one old product file is substituted.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'..'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud'),PREFIX='负责人优化建议-八字样本';
const esbuild=require(path.join(CLOUD,'node_modules/esbuild')),{Miniflare,Log,LogLevel}=require(path.join(CLOUD,'node_modules/miniflare'));
const {request}=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const sha=v=>crypto.createHash('sha256').update(v).digest('hex'),rel=p=>path.relative(ROOT,p).replaceAll('\\','/');
const runId=Date.now().toString(36)+'-'+crypto.randomBytes(4).toString('hex'),directory=path.join(CLOUD,'.wrangler','bazi-legacy-redirect-component-'+runId);
assert(!fs.existsSync(directory));fs.mkdirSync(directory,{recursive:true});
const source=path.join(CLOUD,'lib/eastern-api.ts'),backup=path.join(__dirname,PREFIX+'-legacy重定向修复前-eastern-api.ts');
const oldBytes=fs.readFileSync(backup),newBytes=fs.readFileSync(source),secret=crypto.randomBytes(32).toString('hex'),token=crypto.randomBytes(32).toString('hex');
const report={at:new Date().toISOString(),runId,formalAcceptance:false,scope:'Actual original/fixed product API on separate fresh native workerd/D1 states. Real receiver; exact reserved HTTPS mapping only. Native redirect options forwarded unchanged.',results:[],runtimeArtifacts:[],productionEnabled:false,realSupplier:false,externalRequestsAllowed:false,teacherConfirmed:false,professionalValidation:false,sourceBefore:{path:rel(backup),sha256:sha(oldBytes)},sourceAfter:{path:rel(source),sha256:sha(newBytes)}};
const instances=[],contexts=[];let server,receiverBase,receiverMode=200,primaryCalls=[],targetCalls=0;
const safeError=e=>String(e?.stack||e).replaceAll(secret,'[redacted]').replaceAll(token,'[redacted]').slice(0,1800);
async function check(name,work){try{const observed=await work();report.results.push({name,pass:true,observed});console.log('PASS '+name);}catch(error){report.results.push({name,pass:false,error:safeError(error)});throw error;}}
async function receiver(){
 server=http.createServer(async(req,res)=>{
  const send=(status,value,headers={})=>{const body=JSON.stringify(value);res.writeHead(status,{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body),...headers});res.end(body);};
  if(req.url==='/bazi-samples-fixture/redirect-target'){targetCalls++;req.resume();return send(200,{output:[{type:'message',content:[{type:'output_text',text:'REDIRECT_TARGET_MUST_NOT_BE_USED'}]}]});}
  if(req.url!=='/bazi-samples-fixture/alpha/responses'||req.method!=='POST'){req.resume();return send(404,{error:'fixed route only'});}
  if(req.headers.authorization!=='Bearer '+secret){req.resume();return send(401,{error:'fixture auth required'});}
  const parts=[];let length=0;for await(const part of req){length+=part.length;if(length>262144)return send(413,{error:'bounded fixture body'});parts.push(part);}
  const raw=Buffer.concat(parts),payload=JSON.parse(raw.toString('utf8'));
  primaryCalls.push({sequence:primaryCalls.length+1,status:receiverMode,protocol:payload.stream===true?'responses':'legacy-responses',bytes:raw.length,store:payload.store,hasPrivacyMetadata:raw.includes(Buffer.from('consentEpoch')),keys:Object.keys(payload).sort()});
  if([302,307].includes(receiverMode))return send(receiverMode,{error:'synthetic redirect'}, {Location:receiverBase+'/bazi-samples-fixture/redirect-target'});
  if(receiverMode!==200)return send(receiverMode,{error:'synthetic upstream failure'});
  return send(200,{output:[{type:'message',content:[{type:'output_text',text:'SYNTHETIC_LEGACY_NATIVE_RESPONSE'}]}],usage:{input_tokens:3,output_tokens:2}});
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));receiverBase='http://127.0.0.1:'+server.address().port;
 report.receiver={origin:receiverBase,path:'/bazi-samples-fixture/alpha/responses',realLoopbackHttp:true,promptLogging:false};
}
async function makeInstance(variant){
 const state=path.join(directory,variant),bundle=path.join(directory,variant+'.mjs');assert(!fs.existsSync(state));
 const code="import {handleAPI} from './lib/eastern-api';import schema from './drizzle/0000_lethal_lucky_pierre.sql';const nativeFetch=globalThis.fetch.bind(globalThis);let endpoint='',initialization=null;const trace=[];globalThis.fetch=async(input,options)=>{const url=typeof input==='string'?input:input instanceof URL?input.href:input.url;if(url!=='https://alpha.gateway.invalid/v1/responses')throw Error('Owned component blocks unrelated external HTTP');if(!/^http:\\/\\/127\\.0\\.0\\.1:\\d+\\/bazi-samples-fixture$/.test(endpoint))throw Error('Explicit loopback fixture only');try{return await nativeFetch(input instanceof Request?new Request(endpoint+'/alpha/responses',input):endpoint+'/alpha/responses',options);}catch(error){trace.push({name:error?.name||'Error',message:String(error?.message||error),redirect:options?.redirect||null});throw error;}};export default{async fetch(request,env){endpoint=env.PRIVACY_DOMAINS_PROVIDER_ENDPOINT;const u=new URL(request.url);if(u.pathname==='/__component/trace'){if(request.headers.get('X-Owned-Component')!==env.COMPONENT_TOKEN)return new Response('forbidden',{status:403});return Response.json({trace});}if(!initialization)initialization=env.DB.batch(schema.split('--> statement-breakpoint').map(s=>s.trim()).filter(Boolean).map(s=>env.DB.prepare(s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '))));await initialization;return handleAPI(request,env);}}";
 const build=await esbuild.build({absWorkingDir:CLOUD,stdin:{contents:code,resolveDir:CLOUD,sourcefile:'owned-legacy-redirect-component.ts'},outfile:bundle,bundle:true,format:'esm',platform:'browser',target:'es2022',metafile:true,loader:{'.html':'text','.sql':'text'},logLevel:'silent',plugins:[{name:'owned-original-or-current-product',setup(b){
  if(variant==='original')b.onLoad({filter:/[\\/]lib[\\/]eastern-api\.ts$/},args=>({contents:oldBytes.toString('utf8'),resolveDir:path.dirname(args.path),loader:'ts'}));
  b.onResolve({filter:/\?raw$/},args=>({path:path.resolve(args.resolveDir,args.path.slice(0,-4)),namespace:'owned-component-raw'}));
  b.onLoad({filter:/.*/,namespace:'owned-component-raw'},args=>({contents:fs.readFileSync(args.path,'utf8'),loader:'text'}));
 }}]});
 const metafile=bundle+'.metafile.json';fs.writeFileSync(metafile,JSON.stringify(build.metafile,null,2)+'\n',{flag:'wx'});
 const inputs={},overrides={};for(const key of Object.keys(build.metafile.inputs)){
  if(key==='owned-legacy-redirect-component.ts'){inputs['virtual:owned-legacy-redirect-component.ts']=sha(code);continue;}
  const unwrapped=key.replace(/^owned-component-raw:/,''),file=path.isAbsolute(unwrapped)?unwrapped:path.resolve(CLOUD,unwrapped);
  if(variant==='original'&&path.resolve(file)===source){inputs[rel(backup)]=sha(oldBytes);overrides[rel(source)]={compiledFrom:rel(backup),sha256:sha(oldBytes)};}
  else{assert(fs.existsSync(file),'Actual compiler input exists: '+key);inputs[rel(file)]=sha(fs.readFileSync(file));}
 }
 const toolNames=['esbuild/lib/main.js','esbuild/package.json','@esbuild/win32-x64/package.json','@esbuild/win32-x64/esbuild.exe'];
 const artifact={variant,entryVirtualSha256:sha(code),bundle:rel(bundle),bundleSha256:sha(fs.readFileSync(bundle)),metafile:rel(metafile),metafileSha256:sha(fs.readFileSync(metafile)),inputHashes:inputs,compiledInputOverrides:overrides,runtimeDependencyHashes:Object.fromEntries(toolNames.map(n=>{const p=path.join(CLOUD,'node_modules',n);return[rel(p),sha(fs.readFileSync(p))];})),compilerVersion:esbuild.version,originalBusinessOptionsPreserved:true,toolchainIncludedInHandoff:false};report.runtimeArtifacts.push(artifact);
 const password=crypto.randomBytes(24).toString('hex'),salt=crypto.randomBytes(16),verifier=salt.toString('hex')+':'+crypto.pbkdf2Sync(password,salt,100000,32,'sha256').toString('hex');
 const mf=new Miniflare({modules:true,scriptPath:bundle,compatibilityDate:'2026-05-15',compatibilityFlags:['nodejs_compat'],host:'127.0.0.1',port:0,d1Databases:['DB'],d1Persist:path.join(state,'d1'),r2Buckets:['BUCKET'],r2Persist:path.join(state,'r2'),bindings:{DEMO_ADMIN_HASH:verifier,EW_AI_BAZI_SAMPLES_QA:secret,PRIVACY_DOMAINS_PROVIDER_ENDPOINT:receiverBase+'/bazi-samples-fixture',COMPONENT_TOKEN:token,EW_LOCAL_TASK_RUNTIME_ENABLED:'0'},log:new Log(LogLevel.ERROR)});instances.push(mf);
 const origin=(await mf.ready).origin,admin=await request.newContext({baseURL:origin,timeout:30000}),user=await request.newContext({baseURL:origin,timeout:30000});contexts.push(admin,user);
 async function api(context,route,data,method=data===undefined?'GET':'POST',status=200){const response=await context.fetch(route,{method,...(data===undefined?{}:{data})});const body=await response.json();assert.equal(response.status(),status,variant+' '+route+': '+(body.error||response.status()));return body;}
 await api(admin,'/api/auth/login',{username:'demo_admin',password});
 const settings=await api(admin,'/api/admin/settings'),policy='owned_legacy_'+runId+'_'+variant,ai={enabled:true,providerId:'alpha',endpoint:'https://alpha.gateway.invalid/v1/responses',model:'alpha-qa-model',processingRegions:['QA-LOCAL'],privacyPolicyVersion:policy,apiKeyRef:'EW_AI_BAZI_SAMPLES_QA',prompt:'Only synthetic native local redirect component.',knowledge:''};
 await api(admin,'/api/admin/settings',{expectedRevision:settings.secretConfigRevision,requestId:'settings_'+variant+'_'+runId,ai});
 const old=(await api(admin,'/api/admin/privacy/config')).config;
 await api(admin,'/api/admin/privacy/config',{revision:old.revision,policyVersion:policy,controllerName:'Synthetic local component',contact:'Loopback only',recipients:[{id:'alpha',name:'Explicit real loopback HTTP fixture',endpoint:ai.endpoint,models:[ai.model],regions:['QA-LOCAL'],purpose:'Synthetic HTTP component only; not a real model',policyUrl:'https://alpha.gateway.invalid/privacy',retentionDays:null,deletionSupported:false}],retention:{recordsDays:null,conversationsDays:null,backupDays:null,financeDays:null},purposeDetails:{trainingImprovement:'',marketing:''}},'PATCH');
 const credential={username:'lg_'+variant+'_'+runId.replaceAll('-','').slice(0,12),password:crypto.randomBytes(24).toString('hex'),name:'Synthetic redirect component'},registered=await api(user,'/api/auth/register',credential),owner=registered.user.id;
 let preferences=await api(user,'/api/privacy/preferences');preferences=await api(user,'/api/privacy/preferences',{revision:preferences.revision,policyVersion:preferences.disclosure.policyVersion,acknowledged:true,consents:{...preferences.consents,chart:true,saveConversations:false}},'PATCH');
 const payload={messages:[{role:'user',content:'SYNTHETIC_NATIVE_REDIRECT_COMPONENT',privacy:{accountId:owner,providerId:'alpha',providerBinding:preferences.providerBinding,policyVersion:preferences.disclosure.policyVersion,consentEpoch:preferences.consentEpoch,source:'user',category:'general'}}],context:null};
 async function trace(){const r=await admin.get('/__component/trace',{headers:{'X-Owned-Component':token}});assert.equal(r.status(),200);return(await r.json()).trace;}
 return {variant,origin,owner,api,admin,user,payload,trace,state:rel(state)};
}
async function main(){
 await receiver();
 await check('Original bytes retained and product delta is limited to native no-follow handling',async()=>{assert(oldBytes.includes(Buffer.from("redirect:'error'")));assert(newBytes.includes(Buffer.from("redirect:'manual'")));assert(newBytes.includes(Buffer.from("AI服务重定向已拒绝")));assert.equal(sha(fs.readFileSync(backup)),report.sourceBefore.sha256);return{originalSourceSha256:report.sourceBefore.sha256,currentSourceSha256:report.sourceAfter.sha256,originalSourceFileRetained:true};});
 const old=await makeInstance('original');
 await check('Actual original /api/ai/chat returns 504 before any real receiver HTTP call',async()=>{const before=primaryCalls.length,r=await old.api(old.user,'/api/ai/chat',old.payload,'POST',504),trace=await old.trace();assert.equal(primaryCalls.length,before);assert.equal(targetCalls,0);assert(trace.some(t=>t.name==='TypeError'&&t.redirect==='error'&&t.message.includes('Invalid redirect value')));return{apiStatus:504,nativeError:trace.at(-1),receiverDelta:0,targetCalls:0,actualOriginalProductSourceSha256:report.sourceBefore.sha256,error:r.error};});
 const current=await makeInstance('fixed');
 await check('Actual fixed /api/ai/chat receives a real loopback response with original privacy and secretRef gates',async()=>{receiverMode=200;const before=primaryCalls.length,r=await current.api(current.user,'/api/ai/chat',current.payload);assert.equal(r.text,'SYNTHETIC_LEGACY_NATIVE_RESPONSE');assert.equal(primaryCalls.length,before+1);assert.equal(primaryCalls.at(-1).protocol,'legacy-responses');assert.equal(primaryCalls.at(-1).hasPrivacyMetadata,false);assert.equal(primaryCalls.at(-1).store,false);assert.equal((await current.trace()).length,0);return{apiStatus:200,receiverDelta:1,protocol:'legacy-responses',nativeOptionsChangedByFixture:false,realSupplier:false};});
 for(const status of [302,307])await check('Actual HTTP '+status+' is rejected without following or sending a second request',async()=>{receiverMode=status;const before=primaryCalls.length,r=await current.api(current.user,'/api/ai/chat',current.payload,'POST',502);assert(r.error.includes('重定向'));assert.equal(primaryCalls.length,before+1);assert.equal(targetCalls,0);return{receiverStatus:status,apiStatus:502,primaryDelta:1,secondTargetCalls:0,redirectFollowed:false};});
 await check('Actual non-2xx response is still rejected',async()=>{receiverMode=500;const before=primaryCalls.length;await current.api(current.user,'/api/ai/chat',current.payload,'POST',502);assert.equal(primaryCalls.length,before+1);assert.equal(targetCalls,0);return{receiverStatus:500,apiStatus:502};});
 await check('Unlogged actor remains unauthorized and cannot contact receiver',async()=>{const anonymous=await request.newContext({baseURL:current.origin});contexts.push(anonymous);const before=primaryCalls.length;await current.api(anonymous,'/api/ai/chat',current.payload,'POST',401);assert.equal(primaryCalls.length,before);return{apiStatus:401,receiverDelta:0};});
 report.instances=[{variant:old.variant,origin:old.origin,state:old.state},{variant:current.variant,origin:current.origin,state:current.state}];
 report.receiverCalls=primaryCalls;report.redirectTargetCalls=targetCalls;
}
main().catch(error=>{if(!report.results.length||report.results.at(-1).pass)report.results.push({name:'Owned native component setup/execution',pass:false,error:safeError(error)});}).finally(async()=>{
 for(const c of contexts)await c.dispose().catch(()=>{});for(const mf of instances.reverse())await mf.dispose().catch(()=>{});
 if(server){server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));}
 report.ownedRuntimeStopped=true;report.passed=report.results.filter(x=>x.pass).length;report.failed=report.results.filter(x=>!x.pass).length;report.pass=report.failed===0;report.componentSource={path:rel(__filename),sha256:sha(fs.readFileSync(__filename))};report.sourceAfterUnchanged=sha(fs.readFileSync(source))===report.sourceAfter.sha256;
 const output=path.join(__dirname,PREFIX+'-legacy重定向原生组件-'+runId+'.json');fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({pass:report.pass,passed:report.passed,failed:report.failed,formalAcceptance:false,report:rel(output),sha256:sha(fs.readFileSync(output)),ownedRuntimeStopped:true}));process.exitCode=report.pass&&report.sourceAfterUnchanged?0:1;
});
