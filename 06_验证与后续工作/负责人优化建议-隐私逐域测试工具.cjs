'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {makeHarness:commerceHarness}=require('./负责人优化建议-交易测试工具.cjs');
const ROOT=path.resolve(__dirname,'..'),prefix='负责人优化建议-隐私逐域',sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const qaFiles=['测试工具.cjs','验收启动.cjs','用例工具.cjs','专项.cjs','批次专项.cjs','存储专项.cjs','补充视觉.cjs','Python测试服务.py','Cloud测试服务.ts','夹具控制.py','夹具控制.ts','网络工具.cjs','HTTP流式夹具.py','场景夹具.json','隐私兼容.cjs','隐私兼容测试工具.cjs','隐私兼容Python测试服务.py','隐私兼容Cloud测试服务.ts','清理兼容.cjs','清理兼容测试工具.cjs','清理兼容Python测试服务.py','清理兼容Cloud测试服务.ts','清理兼容夹具.json','注销兼容.cjs','注销兼容测试工具.cjs','注销兼容Python测试服务.py','注销兼容Cloud测试服务.ts','记忆兼容.cjs','记忆兼容测试工具.cjs','记忆兼容Python测试服务.py','记忆兼容Cloud测试服务.ts','额度兼容专项.cjs','额度兼容测试工具.cjs','额度兼容用例工具.cjs','额度兼容Python测试服务.py','额度兼容Cloud测试服务.ts','额度兼容旧库夹具.sql','额度兼容HTTP流式夹具.py','额度兼容验收启动.cjs'];
const fixedSourceFiles=()=>[
 ...fs.readdirSync(path.join(ROOT,'04_研发源码/app/r4/backend')).filter(name=>name.endsWith('.py')).map(name=>'04_研发源码/app/r4/backend/'+name),
 ...fs.readdirSync(path.join(ROOT,'04_研发源码/app/cloud/lib')).filter(name=>name.endsWith('.ts')).map(name=>'04_研发源码/app/cloud/lib/'+name),
 ...fs.readdirSync(path.join(ROOT,'04_研发源码/app/r4')).filter(name=>/\.(js|css)$/.test(name)).map(name=>'04_研发源码/app/r4/'+name),
 '04_研发源码/app/r4/build.py','04_研发源码/app/r4/time-bank-admin.html','04_研发源码/app/cloud/prepare.py','04_研发源码/app/cloud/worker/index.ts','04_研发源码/app/cloud/scripts/sites-env.mjs',
 '04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql','03_当前APP/东方智慧-首页体验R4.html','03_当前APP/计时后台-开发联调.html',
 '04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/generated/admin.html','04_研发源码/app/cloud/generated/review.html','04_研发源码/app/cloud/dist/server/index.js',
 '04_研发源码/app/r4/vendor/NotoSerifTibetan.woff2','04_研发源码/app/cloud/public/assets/NotoSerifTibetan.woff2',
 ...qaFiles.map(name=>'06_验证与后续工作/'+prefix+name),
 '06_验证与后续工作/负责人优化建议-隐私逐域-接口合同.json','06_验证与后续工作/全量回归.cjs','06_验证与后续工作/公网适配全量回归.cjs',
 '06_验证与后续工作/负责人优化建议-交易测试工具.cjs','06_验证与后续工作/负责人优化建议-数字权益专项.cjs','06_验证与后续工作/负责人优化建议-数字权益测试工具.cjs','06_验证与后续工作/负责人优化建议-数字权益用例工具.cjs','06_验证与后续工作/负责人优化建议-支付恢复HTTP查询夹具.py','06_验证与后续工作/负责人优化建议-会员额度用例工具.cjs',
 // Fixed files actually read by a child process, seed loader, identity check or byte fixture.
 '06_验证与后续工作/后台单元回归.py','03_当前APP/发给负责人-东方智慧首页R4.html',
 '04_研发源码/app/r4/backend/initial-content.json','04_研发源码/app/cloud/generated/seed.json',
 '04_研发源码/app/cloud/dist/server/BUILD_ID','04_研发源码/app/r4/images/community-preview-poster.jpg',
 '04_研发源码/app/cloud/scripts/tool-environment.mjs',
 ...['quiet-hour.png','still-water.png','living-light.png','quote-landscape.png','map-life.png','map-body.png','map-mind.png','community-preview.mp4','community-preview-poster.jpg'].map(name=>'04_研发源码/app/cloud/public/assets/'+name),
];
function sourceFiles(){
 const files=new Set(fixedSourceFiles());
 // The unchanged digital compatibility harness hashes these old files as metadata;
 // this does not claim execution of their standalone suites.
 for(const name of require('./负责人优化建议-数字权益测试工具.cjs').sourceFiles)files.add(name);
 const pending=[...files].filter(name=>name.startsWith('06_')&&/\.(cjs|js|mjs|ts|mts)$/.test(name));pending.push('04_研发源码/app/cloud/scripts/sites-env.mjs');
 const inspected=new Set();
 while(pending.length){const name=pending.pop();if(inspected.has(name))continue;inspected.add(name);const absolute=path.join(ROOT,name);assert(fs.existsSync(absolute),'Actual dependency missing: '+name);const text=fs.readFileSync(absolute,'utf8');
  for(const match of text.matchAll(/(?:\brequire\(\s*['"](\.[^'"]+)['"]\s*\)|\bfrom\s*['"](\.[^'"]+)['"]|\bimport\s*['"](\.[^'"]+)['"]|\bimport\(\s*['"](\.[^'"]+)['"]\s*\))/g)){
   const specifier=(match[1]||match[2]||match[3]||match[4]).split('?')[0],base=path.resolve(path.dirname(absolute),specifier),candidates=[base,base.replace(/\.mjs$/,'.mts'),base.replace(/\.js$/,'.ts'),...['.cjs','.js','.mjs','.ts','.mts','.json','.html','.sql'].map(extension=>base+extension),...['index.cjs','index.js','index.ts'].map(index=>path.join(base,index))];
   const dependency=candidates.find(file=>fs.existsSync(file)&&fs.statSync(file).isFile());assert(dependency,'Unresolved actual local import: '+name+' -> '+specifier);const relative=path.relative(ROOT,dependency);assert(!relative.startsWith('..')&&!path.isAbsolute(relative),'Dependency must remain inside this project');const normalized=relative.replaceAll('\\','/');files.add(normalized);if(/\.(cjs|js|mjs|ts|mts)$/.test(normalized)&&!inspected.has(normalized))pending.push(normalized);
  }
 }
 return [...files].sort();
}
const identity=()=>Object.fromEntries([...new Set(sourceFiles())].sort().map(name=>{assert(fs.existsSync(path.join(ROOT,name)),'Actual QA dependency missing: '+name);return [name,sha(fs.readFileSync(path.join(ROOT,name)))];}));
function redactText(value,extra=[]){let result=String(value).replace(/(\bew_session=)[^\s;,"'\\]+/gi,'$1[REDACTED_SESSION]').replace(/(\bBearer\s+)[A-Za-z0-9._~+\/-]+/gi,'$1[REDACTED_TOKEN]');const secrets=[...extra,...Object.entries(process.env).filter(([name,value])=>/(SECRET|TOKEN|PASSWORD|CREDENTIAL|^EW_AI_)/i.test(name)&&value?.length>=12).map(([,value])=>value)];try{secrets.push(JSON.parse(process.env.EW_CLOUD_QA_CREDENTIALS||'{}').password);}catch{}for(const secret of secrets.filter(x=>typeof x==='string'&&x.length>=8))result=result.split(secret).join('[REDACTED_QA_SECRET]');return result;}
function redactError(error,extra=[]){const cleaned=new Error(redactText(error?.message||error,extra));cleaned.name=error?.name||'Error';cleaned.stack=redactText(error?.stack||error,extra);return cleaned;}
function redactReport(value,extra=[]){for(const key of Object.keys(value||{})){if(typeof value[key]==='string')value[key]=redactText(value[key],extra);else if(value[key]&&typeof value[key]==='object')redactReport(value[key],extra);}}
function makeHarness(){
 const h=commerceHarness(),token=process.env.PRIVACY_DOMAINS_TEST_TOKEN;assert(h.args.base,'Use the new isolated privacy-domain launcher');assert(token?.length>=32);let before,serial=0;const privateValues=[];
 const start=h.start,finish=h.finish,originalBrowser=h.browserContext,check=h.check,originalApi=h.api;
 h.api=async(ctx,route,data,method=data===undefined?'GET':'POST',expected=200)=>{if(!['auth/login','auth/setup'].includes(route)||method!=='POST'||expected!==200)return originalApi(ctx,route,data,method,expected);let result=await originalApi(ctx,route,data,method,null);if(result.status===429){console.log('SETUP authentication rate limited; waiting 61 real seconds without changing the limiter');h.report.setupThrottle=[...(h.report.setupThrottle||[]),{route:'/api/'+route,waitMs:61000,scope:'unchanged authentication setup only'}];await new Promise(resolve=>setTimeout(resolve,61000));result=await originalApi(ctx,route,data,method,null);}assert.equal(result.status,200);return result;};
 const redact=value=>redactText(value,privateValues);
 const cleanError=error=>{const cleaned=new Error(redact(error?.message||error));cleaned.name=error?.name||'Error';cleaned.stack=redact(error?.stack||error);return cleaned;};
 const cleanReport=value=>{for(const key of Object.keys(value||{})){if(typeof value[key]==='string')value[key]=redact(value[key]);else if(value[key]&&typeof value[key]==='object')cleanReport(value[key]);}};
 h.check=(name,work)=>check(name,async()=>{try{return await work();}catch(error){throw cleanError(error);}});
 h.start=async()=>{await start();before=identity();h.report.privacyDomainSources=before;h.report.coverage={...h.report.coverage,actualServerHttp:true,actualMediaBytes:false,actualMediaRange:false,realSupplier:false,syntheticDataOnly:true,production:false,processRestartCovered:false,r2DeleteAndHeadCovered:false,sqliteSecureErasure:false,providerDeletion:false,backupDeletion:false};const c=await h.context(),r=await c.get(h.base+'/experience');assert.equal(sha(await r.body()),before[h.target==='python'?'03_当前APP/东方智慧-首页体验R4.html':'04_研发源码/app/cloud/generated/experience.html']);};
 h.finish=async error=>{if(before){h.report.privacyDomainSourcesUnchanged=JSON.stringify(before)===JSON.stringify(identity());if(!h.report.privacyDomainSourcesUnchanged)h.report.results.push({name:'隐私逐域产品构建与实际QA执行文件保持身份',pass:false});}cleanReport(h.report);await finish(error?cleanError(error):undefined);};
 h.browserContext=async storage=>{const result=await originalBrowser(storage);result.page.on('response',response=>{const u=new URL(response.url());if(u.origin===h.base&&u.pathname.startsWith('/api/'))h.report.traffic.push({kind:'native-browser',method:response.request().method(),path:u.pathname,status:response.status()});});return result;};
 h.key=label=>'pd_'+label.replace(/[^A-Za-z0-9_-]/g,'_').slice(0,40)+'_'+h.runId;
 h.register=async label=>{const c=await h.context(),credential={username:'pd_'+(++serial).toString(36)+'_'+label.replace(/[^a-zA-Z0-9]/g,'').slice(0,8)+'_'+h.runId.slice(0,12),password:crypto.randomBytes(20).toString('hex'),name:('隐私逐域合成 '+label).slice(0,24)};privateValues.push(credential.password);assert(credential.username.length<=32);let r=await h.api(c,'auth/register',credential,'POST',null);
  if(r.status===429){console.log('SETUP registration rate limited; waiting 61 real seconds without changing the real limiter');h.report.setupThrottle=[...(h.report.setupThrottle||[]),{route:'/api/auth/register',waitMs:61000,scope:'unchanged registration setup only'}];await new Promise(resolve=>setTimeout(resolve,61000));r=await h.api(c,'auth/register',credential,'POST',null);}assert.equal(r.status,200);credential.id=r.data.user.id;return {c,credential,credentials:credential};};
 h.seed=async()=>{const admin=await h.context(),anonymous=await h.context();let credential;if(h.target==='python'){credential={username:'pd_admin_'+h.runId.slice(0,12),password:crypto.randomBytes(24).toString('hex'),name:'隐私逐域隔离管理员'};privateValues.push(credential.password);await h.api(admin,'auth/setup',credential);}else{credential=JSON.parse(process.env.EW_CLOUD_QA_CREDENTIALS||'{}');assert(credential.username&&credential.password);await h.api(admin,'auth/login',credential);}credential.id=(await h.api(admin,'auth/status')).data.user.id;const a=await h.register('a'),b=await h.register('b');return {admin,anonymous,user:a.c,other:b.c,owner:{id:credential.id},first:{id:a.credential.id},second:{id:b.credential.id},credentials:{admin:credential,a:a.credential,b:b.credential}};};
 h.control=async data=>{const c=await h.context(),r=await c.post(h.base+'/__privacy-domains-test/control',{headers:{'X-Privacy-Domains-Test':token},data:data||{}});assert.equal(r.status(),200);const value=await r.json();assert.equal(value.isolated,true);return value;};
 h.restart=async()=>{const endpoint=process.env.PRIVACY_DOMAINS_RESTART_ENDPOINT;assert(/^http:\/\/127\.0\.0\.1:\d+\/restart$/.test(endpoint),'Only the owned launcher may restart its own child');const c=await h.context(),r=await c.post(endpoint,{headers:{'X-Privacy-Domains-Test':token},data:{action:'restart'},timeout:60000});assert.equal(r.status(),200);const data=await r.json();assert(data.isolated&&data.restarted);assert(Number.isInteger(data.beforePid)&&Number.isInteger(data.afterPid)&&data.beforePid!==data.afterPid);assert.equal(data.base,h.base);h.report.coverage.processRestartCovered=true;(h.report.processRestarts??=[]).push({target:h.target,beforePid:data.beforePid,afterPid:data.afterPid,sameOwnedState:true});return data;};
 h.paymentControl=async data=>{const c=await h.context(),r=await c.post(h.base+'/__late-test/control',{headers:{'X-Late-Test':process.env.RECOVERY_TEST_TOKEN},data});assert.equal(r.status(),200);return r.json();};
 h.queryFixture=async data=>{const c=await h.context(),url=process.env.EW_PAYMENT_QUERY_SANDBOX_ENDPOINT.replace(/\/query$/,'/control'),r=await c.fetch(url,{method:data===undefined?'GET':'POST',headers:{'X-Recovery-Test':process.env.RECOVERY_TEST_TOKEN},...(data===undefined?{}:{data})});assert.equal(r.status(),200);return r.json();};
 h.media=async(c,url,{method='GET',range,headers={},expected=200}={})=>{const u=new URL(url,h.base);assert.equal(u.origin,h.base);const sentHeaders={...headers,...(range?{Range:range}:{})},sentRange=Object.entries(sentHeaders).find(([name])=>name.toLowerCase()==='range')?.[1],r=await c.fetch(u.href,{method,headers:sentHeaders}),bytes=await r.body();h.report.traffic.push({method,path:u.pathname,status:r.status(),range:sentRange||'',responseBytes:bytes.length});assert.equal(r.status(),expected,method+' '+u.pathname+' media status');if(sentRange)h.report.coverage.actualMediaRange=true;if(method==='GET'&&[200,206].includes(r.status())&&/^(audio|video)\//.test(r.headers()['content-type']||'')&&bytes.length)h.report.coverage.actualMediaBytes=true;return {response:r,bytes,headers:r.headers()};};
 h.viewportCapture=async(page,label)=>{const name=h.moduleName+'-'+h.target+'-'+h.runId+'-'+label+'.png';await page.screenshot({path:path.join(__dirname,name),fullPage:false});h.report.captures.push(name);return name;};
 return h;
}
module.exports={makeHarness,identity,sourceFiles,qaFiles,redactText,redactError,redactReport};
