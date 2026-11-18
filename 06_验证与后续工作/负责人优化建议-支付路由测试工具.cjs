'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const previous=require('./负责人优化建议-隐私逐域测试工具.cjs'),inventoryBase=require('./负责人优化建议-任务告警测试工具.cjs');
const ROOT=path.resolve(__dirname,'..'),PREFIX='负责人优化建议-支付路由';
const qaFiles=['测试工具.cjs','验收启动.cjs','用例工具.cjs','专项.cjs','结算专项.cjs','补充视觉.cjs','入口预检.cjs','入口清单.json','旧订单夹具.json','Python测试服务.py','Cloud测试服务.ts','夹具控制.py','夹具控制.ts','隐私夹具控制.py','隐私夹具控制.ts','会员Python测试服务.py','会员Cloud测试服务.ts','回调兼容.cjs','恢复兼容.cjs','迟到兼容.cjs','脱敏前置.cjs'];
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function sourceFiles({preparation=false}={}){
 const actualQa=qaFiles.map(name=>'06_验证与后续工作/'+PREFIX+name).filter(name=>!preparation||fs.existsSync(path.join(ROOT,name)));
 const files=new Set([...inventoryBase.sourceFiles(),...actualQa,
 '06_验证与后续工作/'+PREFIX+'-实施合同.json','04_研发源码/app/r4/backend/payment_routing_schema.sql','04_研发源码/app/cloud/generated/payment-routing-schema.sql',
 '06_验证与后续工作/负责人优化建议-会员额度会员兼容.cjs','06_验证与后续工作/负责人优化建议-会员额度会员浏览器兼容.cjs','06_验证与后续工作/负责人优化建议-会员专项.cjs','06_验证与后续工作/负责人优化建议-会员浏览器专项.cjs','06_验证与后续工作/负责人优化建议-数字权益迟到兼容.cjs']);
 // The unchanged member harness reads this exact namespace only as SHA metadata.
 for(const name of fs.readdirSync(__dirname).filter(n=>n.startsWith('负责人优化建议-会员额度')&&/\.(cjs|py|ts|sql)$/.test(n)))files.add('06_验证与后续工作/'+name);
 const pending=[...files].filter(name=>/\.(cjs|js|mjs|ts|mts)$/.test(name)),seen=new Set();
 while(pending.length){const name=pending.pop();if(seen.has(name))continue;seen.add(name);const absolute=path.join(ROOT,name);assert(fs.existsSync(absolute),'Fixed execution/metadata input missing: '+name);const text=fs.readFileSync(absolute,'utf8');
  for(const match of text.matchAll(/(?:\brequire\(\s*['"](\.[^'"]+)['"]\s*\)|\bfrom\s*['"](\.[^'"]+)['"]|\bimport\s*['"](\.[^'"]+)['"]|\bimport\(\s*['"](\.[^'"]+)['"]\s*\))/g)){
   const base=path.resolve(path.dirname(absolute),(match[1]||match[2]||match[3]||match[4]).split('?')[0]),candidate=[base,base.replace(/\.mjs$/,'.mts'),base.replace(/\.js$/,'.ts'),...['.cjs','.js','.mjs','.ts','.mts','.json','.html','.sql'].map(ext=>base+ext)].find(f=>fs.existsSync(f)&&fs.statSync(f).isFile());assert(candidate,'Unresolved local dependency from '+name);const rel=path.relative(ROOT,candidate).replaceAll('\\','/');assert(!rel.startsWith('..'));files.add(rel);if(/\.(cjs|js|mjs|ts|mts)$/.test(rel))pending.push(rel);
  }
 }
 return [...files].sort();
}
const identity=(options={})=>Object.fromEntries(sourceFiles(options).map(name=>[name,sha(fs.readFileSync(path.join(ROOT,name)))]));
async function bundleCloud(entry,outfile,{preparation=false}={}){
 const cloud=path.join(ROOT,'04_研发源码/app/cloud'),absolute=path.resolve(entry),output=path.resolve(outfile),owned=path.join(cloud,'.wrangler')+path.sep;
 assert(output.startsWith(owned),'Compiled fixture remains in explicitly owned runtime storage');assert(absolute.startsWith(ROOT+path.sep));assert(!fs.existsSync(output),'Do not replace an older runtime artifact');
 const before=identity({preparation}),allowed=new Set(Object.keys(before)),apiFile=path.join(cloud,'node_modules/esbuild/lib/main.js'),packageFile=path.join(cloud,'node_modules/esbuild/package.json'),platformName=process.platform+'-'+process.arch,platformFolder=path.join(cloud,'node_modules/@esbuild',platformName),platformPackage=path.join(platformFolder,'package.json'),binary=path.join(platformFolder,process.platform==='win32'?'esbuild.exe':'bin/esbuild');
 const toolFiles=[apiFile,packageFile,platformPackage,binary];for(const file of toolFiles)assert(fs.existsSync(file),'Installed bundled compiler dependency required');
 const dependencies=Object.fromEntries(toolFiles.map(file=>[path.relative(ROOT,file).replaceAll('\\','/'),sha(fs.readFileSync(file))])),priorBinary=process.env.ESBUILD_BINARY_PATH;process.env.ESBUILD_BINARY_PATH=binary;
 try{
  const esbuild=require(path.join(cloud,'node_modules/esbuild'));assert.equal(esbuild.version,JSON.parse(fs.readFileSync(packageFile,'utf8')).version);
  const result=await esbuild.build({absWorkingDir:ROOT,entryPoints:[absolute],outfile:output,bundle:true,format:'esm',platform:'neutral',target:'es2022',external:['node:*'],loader:{'.html':'text','.sql':'text'},metafile:true,logLevel:'silent',plugins:[{name:'task-alert-owned-raw',setup(build){
   build.onResolve({filter:/\?raw$/},args=>{const file=path.resolve(args.resolveDir,args.path.slice(0,-4)),name=path.relative(ROOT,file).replaceAll('\\','/');assert(allowed.has(name),'Raw project input is missing from the common map: '+name);return {path:file,namespace:'task-alert-owned-raw'};});
   build.onLoad({filter:/.*/,namespace:'task-alert-owned-raw'},args=>({contents:'export default '+JSON.stringify(fs.readFileSync(args.path,'utf8'))+';',loader:'js'}));
  }}]});
  const inputs={};for(const name of Object.keys(result.metafile.inputs)){const unwrapped=name.replace(/^task-alert-owned-raw:/,''),file=path.isAbsolute(unwrapped)?unwrapped:path.resolve(ROOT,unwrapped),relative=path.relative(ROOT,file).replaceAll('\\','/');assert(allowed.has(relative),'Actual compiled project input is missing from common map: '+relative);const value=sha(fs.readFileSync(file));assert.equal(value,before[relative],'Project input changed while compiling fixture: '+relative);inputs[relative]=value;}
  for(const [name,value]of Object.entries(dependencies))assert.equal(sha(fs.readFileSync(path.join(ROOT,name))),value,'Compiler dependency changed during compilation');
  const meta=output+'.metafile.json';fs.writeFileSync(meta,JSON.stringify(result.metafile,null,2)+'\n');return {entry:path.relative(ROOT,absolute).replaceAll('\\','/'),bundle:path.relative(ROOT,output).replaceAll('\\','/'),bundleSha256:sha(fs.readFileSync(output)),metafile:path.relative(ROOT,meta).replaceAll('\\','/'),metafileSha256:sha(fs.readFileSync(meta)),inputHashes:inputs,runtimeDependencyHashes:dependencies,compilerVersion:esbuild.version,toolchainIncludedInHandoff:false,rawReadsActualSourceBytes:true,originalBusinessOptionsPreserved:true,preparationOnly:preparation,missingFixedQaInputs:preparation?qaFiles.filter(name=>!fs.existsSync(path.join(__dirname,PREFIX+name))):[]};
 }finally{if(priorBinary===undefined)delete process.env.ESBUILD_BINARY_PATH;else process.env.ESBUILD_BINARY_PATH=priorBinary;}
}
function makeHarness(){
 const h=previous.makeHarness(),start=h.start,finish=h.finish,check=h.check,originalApi=h.api;let before;const secrets=[];
 assert(process.env.ROUTING_TEST_TOKEN?.length>=32,'Only the newly owned routing launcher is accepted');
 h.addPrivateValue=value=>secrets.push(value);
 h.key=label=>'pr_'+label.replace(/[^A-Za-z0-9:_-]/g,'_').slice(0,35)+'_'+h.runId;
 const cleanError=error=>previous.redactError(error,secrets);
 h.start=async()=>{await start();before=identity();h.report.routingSources=before;h.report.coverage={...h.report.coverage,actualServerHttp:true,production:false,realPaymentProvider:false,clientContextTrusted:false,globalDateNowChanged:false};};
 h.control=async data=>{const c=await h.context(),r=await c.post(h.base+'/__routing-test/control',{headers:{'X-Routing-Test':process.env.ROUTING_TEST_TOKEN},data:data||{},timeout:30000});assert.equal(r.status(),200,'Owned routing control');return r.json();};
 h.check=(name,work)=>check(name,async()=>{try{return await work();}catch(error){throw cleanError(error);}finally{await h.control({action:'routing-barrier-release'}).catch(()=>{});}});
 const actors=new WeakMap(),times=new Map();
 h.prepareRoutingWrites=async(c,needed=1)=>{const key=actors.get(c)||c,list=times.get(key)||[];while(list.length&&list[0]<Date.now()-61000)list.shift();if(list.length+needed>24){const wait=Math.max(1,61010-(Date.now()-list[0]));(h.report.actualRequestPacing??=[]).push({waitMs:wait,reason:'Unmodified real routing/commerce write limiter',businessRetry:false});await new Promise(r=>setTimeout(r,wait));while(list.length&&list[0]<Date.now()-61000)list.shift();}times.set(key,list);};
 h.api=async(c,route,data,method=data===undefined?'GET':'POST',expected=200)=>{if(method!=='GET'&&/^(admin\/payment-routing|commerce\/(quote|orders))/.test(route)){await h.prepareRoutingWrites(c);const key=actors.get(c)||c;times.get(key).push(Date.now());}const result=await originalApi(c,route,data,method,expected);if(result.data?.user?.id)actors.set(c,result.data.user.id);return result;};
 h.restart=async()=>{const c=await h.context(),r=await c.post(process.env.ROUTING_LAUNCHER_CONTROL,{headers:{'X-Routing-Test':process.env.ROUTING_TEST_TOKEN},data:{action:'restart'},timeout:75000});assert.equal(r.status(),200);const value=await r.json();assert(value.restarted&&value.beforePid!==value.afterPid&&value.base===h.base);(h.report.processRestarts??=[]).push(value);return value;};
 h.finish=async error=>{if(before){h.report.routingSourcesUnchanged=JSON.stringify(before)===JSON.stringify(identity());if(!h.report.routingSourcesUnchanged)h.report.results.push({name:'Routing actual source/build/QA inputs remain unchanged',pass:false});}previous.redactReport(h.report,secrets);await finish(error?cleanError(error):undefined);};
 return h;
}
module.exports={makeHarness,identity,sourceFiles,qaFiles,bundleCloud,sha,redactText:previous.redactText};
