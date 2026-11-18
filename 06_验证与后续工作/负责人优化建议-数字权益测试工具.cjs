'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {makeHarness:commerceHarness}=require('./负责人优化建议-交易测试工具.cjs');
const ROOT=path.resolve(__dirname,'..'),prefix='负责人优化建议-数字权益',sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const qaFiles=['测试工具.cjs','验收启动.cjs','用例工具.cjs','专项.cjs','补充视觉.cjs','Python测试服务.py','Cloud测试服务.ts','回调兼容.cjs','恢复兼容.cjs','迟到兼容.cjs'];
const sourceFiles=[
 '04_研发源码/app/r4/backend/digital_entitlements.py','04_研发源码/app/cloud/lib/digital-entitlements.ts',
 '04_研发源码/app/r4/backend/commerce.py','04_研发源码/app/cloud/lib/commerce-api.ts',
 '04_研发源码/app/r4/backend/payment_callbacks.py','04_研发源码/app/cloud/lib/payment-callbacks.ts',
 '04_研发源码/app/r4/backend/payment_recovery.py','04_研发源码/app/cloud/lib/payment-recovery.ts',
 '04_研发源码/app/r4/backend/payment_late.py','04_研发源码/app/cloud/lib/payment-late.ts',
 '04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/eastern-api.ts',
 '04_研发源码/app/r4/backend/privacy.py','04_研发源码/app/cloud/lib/privacy-api.ts',
 '04_研发源码/app/r4/backend/account_write_guard.py','04_研发源码/app/cloud/lib/account-write-guard.ts',
 '04_研发源码/app/r4/digital-entitlements-ui.js','04_研发源码/app/r4/digital-entitlements-admin.js','04_研发源码/app/r4/digital-entitlements-ui.css',
 '04_研发源码/app/r4/commerce-ui.js','04_研发源码/app/r4/commerce-ui.css','04_研发源码/app/r4/commerce-admin.js',
 '04_研发源码/app/r4/account-closure.js','04_研发源码/app/r4/membership-lifecycle-ui.js',
 '04_研发源码/app/r4/platform.js','04_研发源码/app/r4/build.py','04_研发源码/app/cloud/prepare.py',
 '03_当前APP/东方智慧-首页体验R4.html','03_当前APP/计时后台-开发联调.html',
 '04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/generated/admin.html','04_研发源码/app/cloud/generated/review.html','04_研发源码/app/cloud/dist/server/index.js',
 '04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql','04_研发源码/app/cloud/scripts/sites-env.mjs',
 ...qaFiles.map(name=>'06_验证与后续工作/'+prefix+name),
 '06_验证与后续工作/负责人优化建议-支付恢复HTTP查询夹具.py','06_验证与后续工作/负责人优化建议-交易测试工具.cjs',
 '06_验证与后续工作/负责人优化建议-交易专项.cjs','06_验证与后续工作/全量回归.cjs','06_验证与后续工作/公网适配全量回归.cjs',
];
const identity=()=>Object.fromEntries(sourceFiles.filter(name=>fs.existsSync(path.join(ROOT,name))).map(name=>[name,sha(fs.readFileSync(path.join(ROOT,name)))]));
function makeHarness(){
 const h=commerceHarness(),token=process.env.DIGITAL_TEST_TOKEN;assert(h.args.base,'Use the new isolated digital entitlement launcher');assert(token?.length>=32);let before,serial=0;
 const start=h.start,finish=h.finish,originalBrowser=h.browserContext,check=h.check;
 const redact=value=>{let text=String(value).replace(/(\bew_session=)[^\s;,"'\\]+/gi,'$1[REDACTED_SESSION]');for(const secret of [process.env.DIGITAL_TEST_TOKEN,process.env.RECOVERY_TEST_TOKEN,process.env.EW_PAYMENT_QUERY_QA_SECRET,process.env.EW_PAYMENT_CALLBACK_QA_SECRET].filter(Boolean))text=text.split(secret).join('[REDACTED_QA_SECRET]');return text;};
 const cleanError=error=>{const cleaned=new Error(redact(error?.message||error));cleaned.name=error?.name||'Error';cleaned.stack=redact(error?.stack||error);return cleaned;};
 const cleanReport=value=>{for(const key of Object.keys(value||{})){if(typeof value[key]==='string')value[key]=redact(value[key]);else if(value[key]&&typeof value[key]==='object')cleanReport(value[key]);}};
 h.check=(name,work)=>check(name,async()=>{try{return await work();}catch(error){throw cleanError(error);}});
 h.start=async()=>{await start();before=identity();h.report.digitalSources=before;h.report.coverage={...h.report.coverage,actualServerHttp:true,actualMediaBytes:true,actualMediaRange:true,realPaymentProvider:false,syntheticDataOnly:true,production:false,processRestartCovered:false};const c=await h.context(),r=await c.get(h.base+'/experience');assert.equal(sha(await r.body()),before[h.target==='python'?'03_当前APP/东方智慧-首页体验R4.html':'04_研发源码/app/cloud/generated/experience.html']);};
 h.finish=async error=>{if(before){h.report.digitalSourcesUnchanged=JSON.stringify(before)===JSON.stringify(identity());if(!h.report.digitalSourcesUnchanged)h.report.results.push({name:'数字权益产品构建与实际QA执行文件保持身份',pass:false});}cleanReport(h.report);await finish(error?cleanError(error):undefined);};
 h.browserContext=async storage=>{const result=await originalBrowser(storage);result.page.on('response',response=>{const u=new URL(response.url());if(u.origin===h.base&&u.pathname.startsWith('/api/'))h.report.traffic.push({kind:'native-browser',method:response.request().method(),path:u.pathname,status:response.status()});});return result;};
 h.key=label=>'de_'+label+'_'+h.runId;
 h.register=async label=>{const c=await h.context(),credential={username:'di_'+(++serial).toString(36)+'_'+label.replace(/[^a-zA-Z0-9]/g,'').slice(0,8)+'_'+h.runId.slice(0,12),password:crypto.randomBytes(20).toString('hex'),name:'数字权益合成 '+label};assert(credential.username.length<=32);let r=await h.api(c,'auth/register',credential,'POST',null);
  if(r.status===429){console.log('SETUP registration rate limited; waiting 61 real seconds without changing the real limiter');h.report.setupThrottle=[...(h.report.setupThrottle||[]),{route:'/api/auth/register',waitMs:61000,scope:'unchanged registration setup only'}];await new Promise(resolve=>setTimeout(resolve,61000));r=await h.api(c,'auth/register',credential,'POST',null);}assert.equal(r.status,200);credential.id=r.data.user.id;return {c,credential,credentials:credential};};
 h.seed=async()=>{const admin=await h.context(),anonymous=await h.context();let credential;if(h.target==='python'){credential={username:'di_admin_'+h.runId.slice(0,12),password:crypto.randomBytes(24).toString('hex'),name:'数字权益隔离管理员'};await h.api(admin,'auth/setup',credential);}else{credential=JSON.parse(process.env.EW_CLOUD_QA_CREDENTIALS||'{}');assert(credential.username&&credential.password);await h.api(admin,'auth/login',credential);}credential.id=(await h.api(admin,'auth/status')).data.user.id;const a=await h.register('a'),b=await h.register('b');return {admin,anonymous,user:a.c,other:b.c,owner:{id:credential.id},first:{id:a.credential.id},second:{id:b.credential.id},credentials:{admin:credential,a:a.credential,b:b.credential}};};
 h.control=async data=>{const c=await h.context(),r=await c.post(h.base+'/__digital-test/control',{headers:{'X-Digital-Test':token},data:data||{}});assert.equal(r.status(),200);const value=await r.json();assert.equal(value.isolated,true);return value;};
 h.paymentControl=async data=>{const c=await h.context(),r=await c.post(h.base+'/__late-test/control',{headers:{'X-Late-Test':process.env.RECOVERY_TEST_TOKEN},data});assert.equal(r.status(),200);return r.json();};
 h.queryFixture=async data=>{const c=await h.context(),url=process.env.EW_PAYMENT_QUERY_SANDBOX_ENDPOINT.replace(/\/query$/,'/control'),r=await c.fetch(url,{method:data===undefined?'GET':'POST',headers:{'X-Recovery-Test':process.env.RECOVERY_TEST_TOKEN},...(data===undefined?{}:{data})});assert.equal(r.status(),200);return r.json();};
 h.media=async(c,url,{method='GET',range,headers={},expected=200}={})=>{const u=new URL(url,h.base);assert.equal(u.origin,h.base);const r=await c.fetch(u.href,{method,headers:{...headers,...(range?{Range:range}:{})}}),bytes=await r.body();h.report.traffic.push({method,path:u.pathname,status:r.status(),range:range||'',responseBytes:bytes.length});assert.equal(r.status(),expected,method+' '+u.pathname+' media status');return {response:r,bytes,headers:r.headers()};};
 h.viewportCapture=async(page,label)=>{const name=h.moduleName+'-'+h.target+'-'+h.runId+'-'+label+'.png';await page.screenshot({path:path.join(__dirname,name),fullPage:false});h.report.captures.push(name);return name;};
 return h;
}
module.exports={makeHarness,identity,sourceFiles};
