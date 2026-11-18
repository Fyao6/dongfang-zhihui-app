'use strict';
// All services are owned by this module's launcher. Existing frozen harnesses are unchanged.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {makeHarness:commerceHarness}=require('./负责人优化建议-交易测试工具.cjs');
const ROOT=path.resolve(__dirname,'..'),prefix='负责人优化建议-会员额度',sha=x=>crypto.createHash('sha256').update(x).digest('hex');
function makeHarness(){
 const h=commerceHarness(),token=process.env.MEMBER_QUOTA_TEST_TOKEN;assert(h.args.base,'Use the module launcher with newly owned state');assert(token?.length>=32);
 if(h.args.compat==='gateway'||h.args.compat==='membership'){
  const origin=h.args.compat==='gateway'?'负责人优化建议-AI网关专项.cjs':'负责人优化建议-会员专项.cjs';
  h.report.compatibilitySource={file:origin,sha256:sha(fs.readFileSync(path.join(__dirname,origin))),businessAssertions:'retained unchanged',adaptation:'new owned-state harness, independent real HTTP/SSE fixture, module-specific report'};
  if(h.args.compat==='membership')h.report.compatibilitySource.browser={file:'负责人优化建议-会员浏览器专项.cjs',sha256:sha(fs.readFileSync(path.join(__dirname,'负责人优化建议-会员浏览器专项.cjs'))),derived:'负责人优化建议-会员额度会员浏览器兼容.cjs',businessAssertions:'original assertions retained; payment case additionally holds a real unpaid GET until after native payment; next renewal date asserted'};
 }
 const originalStart=h.start,originalFinish=h.finish;let before;
 const files=()=>[
  '04_研发源码/app/r4/backend/membership_ai_quota.py','04_研发源码/app/cloud/lib/membership-ai-quota.ts',
  '04_研发源码/app/r4/backend/membership_lifecycle.py','04_研发源码/app/cloud/lib/membership-lifecycle.ts',
  '04_研发源码/app/r4/backend/ai_gateway.py','04_研发源码/app/cloud/lib/ai-gateway.ts',
  '04_研发源码/app/r4/membership-ai-quota-ui.js','04_研发源码/app/r4/membership-ai-quota-admin.js',
  '04_研发源码/app/r4/membership-lifecycle-ui.js','04_研发源码/app/r4/membership-lifecycle-admin.js',
  '04_研发源码/app/r4/membership-lifecycle-ui.css','04_研发源码/app/r4/ai-gateway-ui.css',
  '04_研发源码/app/r4/commerce-ui.js','04_研发源码/app/r4/account-closure.js',
  '04_研发源码/app/r4/ai-gateway-ui.js','04_研发源码/app/r4/ai-gateway-admin.js',
  '04_研发源码/app/r4/backend/privacy.py','04_研发源码/app/cloud/lib/privacy-api.ts',
  ...fs.readdirSync(__dirname).filter(n=>n.startsWith(prefix)&&/\.(cjs|py|ts|sql)$/.test(n)).map(n=>'06_验证与后续工作/'+n)
 ].filter(n=>fs.existsSync(path.join(ROOT,n)));
 const identity=()=>Object.fromEntries(files().map(n=>[n,sha(fs.readFileSync(path.join(ROOT,n)))]));
 h.start=async()=>{await originalStart();before=identity();h.report.quotaSources=before;h.report.coverage={...h.report.coverage,actualServerHttp:true,upstream:'independent loopback HTTP/SSE fixture via exact reserved .invalid endpoint mapping',realSupplier:false,syntheticClock:true,production:false};
  const c=await h.context(),r=await c.get(h.base+'/experience'),relative=h.target==='python'?'03_当前APP/东方智慧-首页体验R4.html':'04_研发源码/app/cloud/generated/experience.html';assert.equal(sha(await r.body()),sha(fs.readFileSync(path.join(ROOT,relative))));h.report.servedBuildSha256=sha(await r.body());};
 h.finish=async fatal=>{if(before){h.report.quotaSourcesUnchanged=JSON.stringify(before)===JSON.stringify(identity());if(!h.report.quotaSourcesUnchanged)h.report.results.push({name:'会员额度源码与QA执行文件保持同一身份',pass:false});}await originalFinish(fatal);};
 h.register=async label=>{const c=await h.context(),credential={username:'mq_'+label.replace(/[^A-Za-z0-9]/g,'').slice(0,11)+'_'+h.runId.slice(0,16),password:crypto.randomBytes(20).toString('hex'),name:'额度合成 '+label};assert(credential.username.length<=32);let result=await h.api(c,'auth/register',credential,'POST',null);
  if(result.status===429){console.log('SETUP auth/register reached the real IP rate limit; waiting 61 real seconds before retrying the unchanged synthetic registration');h.report.setupThrottle=[...(h.report.setupThrottle||[]),{route:'/api/auth/register',status:429,waitMs:61000,scope:'setup only; no job or stream retries'}];await new Promise(resolve=>setTimeout(resolve,61000));result=await h.api(c,'auth/register',credential,'POST',null);}
  assert.equal(result.status,200,'Synthetic registration must succeed without weakening the real limiter');credential.id=result.data.user.id;return {c,credential,credentials:credential};};
 h.seed=async()=>{const admin=await h.context(),anonymous=await h.context();let credential;
  if(h.target==='python'){credential={username:'mq_admin_'+h.runId.slice(0,12),password:crypto.randomBytes(24).toString('hex'),name:'会员额度隔离管理员'};await h.api(admin,'auth/setup',credential);}
  else{credential=JSON.parse(process.env.EW_CLOUD_QA_CREDENTIALS||'{}');assert(credential.username&&credential.password);await h.api(admin,'auth/login',credential);}
  credential.id=(await h.api(admin,'auth/status')).data.user.id;const a=await h.register('a'),b=await h.register('b');return {admin,anonymous,user:a.c,other:b.c,owner:{id:credential.id},first:{id:a.credential.id},second:{id:b.credential.id},credentials:{admin:credential,a:a.credential,b:b.credential}};
 };
 h.fixture=async data=>{const c=await h.context(),r=await c.fetch(process.env.MEMBER_QUOTA_FIXTURE_ENDPOINT+'/control',{method:data===undefined?'GET':'POST',headers:{'X-Member-Quota-Test':token},...(data===undefined?{}:{data})});assert.equal(r.status(),200);return r.json();};
 h.quotaControl=async data=>{const c=await h.context(),r=await c.post(h.base+'/__member-quota-test/control',{headers:{'X-Member-Quota-Test':token},data:data||{}});assert.equal(r.status(),200);const value=await r.json();assert.equal(value.isolated,true);return value;};
 h.control=async data=>h.args.compat==='gateway'?h.fixture(data):h.quotaControl(data);
 h.mockCalls=async()=>(await h.fixture()).calls;
 h.viewportCapture=async(page,label)=>{const file=h.moduleName+'-'+h.target+'-'+h.runId+'-'+label+'.png';await page.screenshot({path:path.join(__dirname,file),fullPage:false});h.report.captures.push(file);return file;};
 h.key=label=>'mq_'+label+'_'+h.runId;
 h.waitCalls=async count=>{for(let i=0;i<200;i++){const calls=await h.mockCalls();if(calls.length>=count)return calls;await new Promise(r=>setTimeout(r,25));}throw Error('Independent HTTP fixture did not receive the actual upstream request');};
 return h;
}
module.exports={makeHarness};
