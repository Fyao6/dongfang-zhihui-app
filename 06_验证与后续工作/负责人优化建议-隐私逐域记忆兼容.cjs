const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {chromium, request} = require(path.join(require('node:os').homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const {makeHarness}=require('./负责人优化建议-隐私逐域记忆兼容测试工具.cjs');
const h=makeHarness(),target=h.target,token=h.fixtureToken;let base,adminCredentials;
const root = path.resolve(__dirname,'..');
const runId=h.runId;
const results = [], contexts = [], errors = [];
const buildPath = target==='python'?'03_当前APP/东方智慧-首页体验R4.html':'04_研发源码/app/cloud/generated/experience.html';
const sha = bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
let browser;
async function context(){
 const c=await request.newContext();
 contexts.push(c);
 return c;
}
async function api(c,route,data,method=data===undefined?'GET':'POST',status=200){
 const r=await c.fetch(base+'/api/'+route,{method,...(data===undefined?{}:{data})});
 const result=await r.json();
 assert.equal(r.status(),status,method+' '+route+' '+(result.error||''));
 return result;
}
async function check(name,fn){
 try{await fn();results.push({name,pass:true});console.log('PASS '+name);}
 catch(error){results.push({name,pass:false,error:h.redact(error.stack)});console.log('FAIL '+name+' '+h.redact(error.message));}
}
const key=()=>crypto.randomUUID();
const getSettings=c=>api(c,'memory/settings');
async function preferences(c,consents){
 const p=await api(c,'privacy/preferences');
 return api(c,'privacy/preferences',{revision:p.revision,policyVersion:p.disclosure.policyVersion,consents,acknowledged:true},'PATCH');
}
async function add(c,text){
 const s=await getSettings(c);
 return (await api(c,'memory',{requestId:key(),memoryEpoch:s.memoryEpoch,category:'general',title:'QA entry',text})).currentItem;
}
async function fixture(c,data){
 const r=await c.fetch(base+'/__memory-test/mock',{headers:{'X-Memory-Test':token},...(data?{method:'POST',data}:{})});
 assert.equal(r.status(),200);
 const f=await r.json();
 assert.equal(f.externalProviderTested,false);
 return f;
}
const receiver=(id,endpoint,model)=>({id,name:id,regions:['QA-LOCAL'],purpose:'Synthetic local fixture',policyUrl:'https://policy.invalid/'+id,endpoint,models:[model],retentionDays:null,deletionSupported:false});
async function main(){
 await h.start();base=h.base;const initial=await h.seed();adminCredentials={username:initial.adminCredentials.username,password:initial.adminCredentials.password};
 const admin=await context(), user=await context(), other=await context(), anon=await context();
 const health=await api(anon,'health');
 assert.equal(health.deployment==='cloud',target==='cloud');
 const served=await anon.get(base+'/experience');
 assert.equal(sha(await served.body()),sha(fs.readFileSync(path.join(root,buildPath))));
 await api(admin,'auth/login',adminCredentials);
 for(const [ctx,suffix] of [[user,'a'],[other,'b']])await api(ctx,'auth/register',{username:'memqa_'+suffix+'_'+runId.replace('-','_'),password:key(),name:'Memory QA '+suffix});
 const original=(await api(admin,'admin/privacy/config')).config;
 const policy={revision:original.revision,policyVersion:'memory-fixture-v1',controllerName:'Synthetic QA',contact:'Fixture only',recipients:[
  receiver('legacy-memory','https://memory-legacy.invalid/v1/responses','memory-legacy-model'),
  receiver('alpha','https://alpha.memory.invalid/v1/responses','alpha-memory-model'),
  receiver('beta','https://beta.memory.invalid/v1/messages','beta-memory-model'),
 ],retention:{recordsDays:null,conversationsDays:null,backupDays:null,financeDays:null},purposeDetails:{trainingImprovement:'',marketing:''}};
 await api(admin,'admin/privacy/config',policy,'PATCH');
 const retention=(await api(admin,'admin/privacy/retention/config')).config;
 await api(admin,'admin/privacy/retention/config',{confirmed:true,enabled:true,policyVersion:policy.policyVersion,revision:retention.revision,retentionDays:{timer:null,activity:null,measurements:null,cards:null,memory:0}},'PATCH');
 let selected, spare, selection, prefs;
 await check('本人默认关闭、匿名拒绝、独立保留期限',async()=>{
  await api(anon,'memory',undefined,'GET',401);
  const settings=await getSettings(user);
  assert.equal(settings.enabled,false);
  assert.equal(settings.memoryRetentionDays,0);
  await api(user,'memory',{requestId:key(),memoryEpoch:0,category:'general',title:'Denied',text:'Denied'},'POST',403);
 });
 await check('本人开启、创建和查看，列表及他人访问无正文',async()=>{
  prefs=await preferences(user,{longTermMemory:true,saveConversations:true});
  selected=await add(user,'MEM_SELECTED_BODY_CANARY');
  spare=await add(user,'MEM_UNSELECTED_BODY_CANARY');
  selection={memoryEpoch:(await getSettings(user)).memoryEpoch,items:[{id:selected.id,version:selected.version}]};
  const listing=await api(user,'memory');
  assert.equal(listing.items.length,2);
  assert(!JSON.stringify(listing).includes('BODY_CANARY'));
  await api(other,'memory/items/'+selected.id,undefined,'GET',404);
  assert.equal((await api(user,'memory/items/'+selected.id)).item.text,selected.text);
  assert.equal((await api(user,'privacy/export')).serverData.memoryItems.length,2);
 });
 const legacy=()=>({messages:[{role:'user',content:'Local synthetic question',privacy:{
  accountId:prefs.accountId,consentEpoch:prefs.consentEpoch,providerId:'legacy-memory',providerBinding:prefs.providerBinding,
  policyVersion:prefs.disclosure.policyVersion,source:'user',category:'general',
 }}],context:null});
 await check('旧 AI 实际入口仅传选定条目，无选择及旧记忆历史门禁',async()=>{
  const selectedReply=await api(user,'ai/chat',{...legacy(),memorySelection:selection});
  assert.equal(selectedReply.text,'MEMORY_LOCAL_FIXTURE_LEGACY');
  assert.deepEqual(selectedReply.privacy.memorySelection,selection);
  const regular=await api(user,'ai/chat',legacy());
  assert(!Object.hasOwn(regular,'privacy'));
  await api(user,'ai/chat',{messages:[{role:'assistant',content:selectedReply.text,privacy:selectedReply.privacy},...legacy().messages]},'POST',403);
  const calls=(await fixture(anon)).calls.slice(-2);
  assert.equal(calls.length,2);
  assert.equal(calls[0].selectedBodyPresent,true);
  assert.equal(calls[1].selectedBodyPresent,false);
  for(const call of calls)assert(!call.unselectedBodyPresent&&!call.localMemoryMetadataPresent&&!call.privacyTagsPresent);
 });
 const oldGateway=(await api(admin,'admin/ai-gateway')).config;
 const model=(id,protocol)=>({id,name:id,protocol,endpoint:'https://'+id+'.memory.invalid/v1/'+(id==='alpha'?'responses':'messages'),model:id+'-memory-model',secretRef:'EW_AI_MEMORY_QA_'+id.toUpperCase(),processingRegions:['QA-LOCAL'],privacyPolicyVersion:policy.policyVersion,enabled:true,streaming:true,authMode:id==='alpha'?'bearer':'x-api-key',apiVersion:id==='alpha'?'':'2026-10-21',timeoutSeconds:12,maxOutputTokens:128,prompt:'Local fixture'});
 await api(admin,'admin/ai-gateway/config',{revision:oldGateway.revision,enabled:true,allowExternalCalls:true,environment:'local-test',providers:[model('alpha','responses'),model('beta','anthropic_messages')],routes:Object.fromEntries(['chat','chart','course','card'].map(k=>[k,{primary:'alpha',fallback:['beta']}])),requestTimeoutSeconds:15,charging:{confirmed:true,ruleVersion:'qa-memory',successCredits:4,failureCredits:1,partialCredits:2,cancelCredits:1}},'PATCH');
 prefs=await preferences(user,{longTermMemory:true,saveConversations:true});
 await api(admin,'admin/ai-gateway/grants',{requestId:key(),accountId:prefs.accountId,credits:100,environment:'local-test'});
 async function baseConsent(id){
  const p=(await api(user,'ai-gateway/capabilities')).providers.find(p=>p.id===id).authorization;
  return (await api(user,'ai-gateway/providers/'+id+'/consent',{acknowledged:true,policyVersion:p.policyVersion,providerBinding:p.providerBinding,categories:['general','card']})).authorization;
 }
 const auth=await baseConsent('alpha');
 await baseConsent('beta');
 async function memoryConsent(id){
  const p=(await api(user,'memory/providers')).items.find(p=>p.id===id).authorization;
  return api(user,'memory/providers/'+id+'/consent',{requestId:key(),acknowledged:true,providerBinding:p.providerBinding,policyVersion:p.policyVersion,globalRevision:p.globalRevision,memoryEpoch:(await getSettings(user)).memoryEpoch});
 }
 const payload=(memorySelection=selection)=>({requestId:key(),scene:'chat',environment:'local-test',messages:[{role:'user',content:'Synthetic gateway question',privacy:{accountId:auth.accountId,providerId:auth.providerId,providerBinding:auth.providerBinding,policyVersion:auth.policyVersion,consentEpoch:auth.consentEpoch,source:'user',category:'general'}}],context:null,...(memorySelection?{memorySelection}:{})});
 async function stream(job,body){
  const r=await user.post(base+'/api/ai-gateway/jobs/'+job.id+'/stream',{data:body});
  assert.equal(r.status(),200,r.ok()?'':await r.text());
  const blocks=(await r.text()).replaceAll('\r\n','\n').split('\n\n');
  const done=blocks.find(block=>block.startsWith('event: gateway.done\n'));
  assert(done,blocks.join(' ').slice(0,400));
  return JSON.parse(done.split('\n').find(line=>line.startsWith('data: ')).slice(6));
 }
 let originalJob, originalPayload;
 await check('网关需额外供应商授权，真实 SSE 成功并且同请求只重放状态',async()=>{
  await api(user,'ai-gateway/jobs',payload(),'POST',403);
  await memoryConsent('alpha');
  const overBudget={...payload(),context:{category:'general',fields:{question:'x'.repeat(5975)}}};
  const before=(await api(user,'ai-gateway/capabilities')).wallet;
  await api(user,'ai-gateway/jobs',overBudget,'POST',400);
  assert.deepEqual((await api(user,'ai-gateway/capabilities')).wallet,before);
  originalPayload=payload();
  originalJob=await api(user,'ai-gateway/jobs',originalPayload);
  const done=await stream(originalJob,originalPayload);
  assert.equal(done.status,'succeeded');
  const replay=await api(user,'ai-gateway/jobs',originalPayload);
  assert.equal(replay.memoryReplay,true);
  assert.equal(replay.id,originalJob.id);
  assert(!Object.hasOwn(replay,'text'));
  const call=(await fixture(anon)).calls.at(-1);
  assert.equal(call.selectedBodyPresent,true);
  assert(!call.unselectedBodyPresent&&!call.localMemoryMetadataPresent&&!call.privacyTagsPresent);
 });
 await check('备用供应商独立授权，未授权时不发送',async()=>{
  await fixture(anon,{mode:'primary-fails'});
  const before=(await fixture(anon)).calls.length;
  const first=payload(),firstJob=await api(user,'ai-gateway/jobs',first);
  assert.equal((await stream(firstJob,first)).status,'failed');
  assert.deepEqual((await fixture(anon)).calls.slice(before).map(c=>c.providerId),['alpha']);
  await memoryConsent('beta');
  const second=payload(),secondJob=await api(user,'ai-gateway/jobs',second);
  assert.equal((await stream(secondJob,second)).status,'succeeded');
  assert.equal((await fixture(anon)).calls.at(-1).providerId,'beta');
  await fixture(anon,{mode:'success'});
 });
 await check('浏览器通过原生控件管理条目，四语窄屏和桌面',async()=>{
  const edge=[process.env['ProgramFiles(x86)'],process.env.ProgramFiles,process.env.LOCALAPPDATA].filter(Boolean).map(p=>path.join(p,'Microsoft/Edge/Application/msedge.exe')).find(p=>fs.existsSync(p));
  browser=await chromium.launch({headless:true,...(edge?{executablePath:edge}:{})});
  const c=await browser.newContext({storageState:await user.storageState(),viewport:{width:360,height:780},reducedMotion:'reduce'});
  const page=await c.newPage();
  page.on('pageerror',e=>errors.push(h.redact(e.message)));
  for(const [lang,width,mode] of [['zh',360,'night'],['zh-Hant',390,'day'],['en',360,'day'],['bo',390,'night'],['en',1120,'night']]){
   await page.setViewportSize({width,height:840});
   await page.goto(base+'/experience?lang='+lang+'&mode='+mode+'&page=privacyMemory');
   await page.waitForFunction(()=>typeof px!=='undefined'&&px.loaded);
   const memory=page.locator('.mm-wrap');
   await memory.locator('[data-mm-action=view]').first().waitFor();
   await memory.locator('[data-mm-action=view]').first().click();
   await memory.locator('.mm-body').waitFor();
   await page.evaluate(()=>document.fonts.ready.then(()=>null));
   assert(await memory.evaluate(el=>el.scrollWidth<=el.clientWidth+2));
   const capture='负责人优化建议-隐私逐域记忆兼容-'+target+'-'+runId+'-'+lang+'-'+width+'.png';await page.screenshot({path:path.join(__dirname,capture),fullPage:true});h.report.captures.push(capture);(h.report.captureHashes??={})[capture]=sha(fs.readFileSync(path.join(__dirname,capture)));
  }
  assert.deepEqual(errors,[]);
  await page.goto(base+'/experience?lang=zh&page=privacyMemory');
  const selectedControl=page.locator('[data-mm-select="'+selected.id+'"]');
  await selectedControl.check();
  const priorCalls=(await fixture(anon)).calls.length;
  await page.locator('#nav [data-to=service]').click();
  await page.waitForFunction(()=>agState().loaded&&!agState().loading&&px.gatewayReady);
  const requestStarted=page.waitForRequest(r=>new URL(r.url()).pathname==='/api/ai-gateway/jobs'&&r.method()==='POST');
  await page.locator('#ss-ai-input').fill('QA browser explicit memory');
  await page.locator('#ss-ai-form button').click();
  const requestBody=(await requestStarted).postDataJSON();
  assert.deepEqual(requestBody.memorySelection,selection);
  await page.waitForFunction(()=>!px.busy);
  assert.equal(await page.evaluate(()=>state.support.ai.at(-1)?.role),'assistant');
  assert.equal((await fixture(anon)).calls.length,priorCalls+1);
  assert.equal((await fixture(anon)).calls.at(-1).selectedBodyPresent,true);
  await page.locator('#ss-ai-input').fill('QA browser ordinary follow-up');
  const nextRequest=page.waitForRequest(r=>new URL(r.url()).pathname==='/api/ai-gateway/jobs'&&r.method()==='POST');
  await page.locator('#ss-ai-form button').click();
  const nextBody=(await nextRequest).postDataJSON();
  assert(!Object.hasOwn(nextBody,'memorySelection'));
  assert(nextBody.messages.every(message=>!Object.hasOwn(message.privacy,'memorySelection')));
  await page.waitForFunction(()=>!px.busy);
  assert.equal((await fixture(anon)).calls.at(-1).selectedBodyPresent,false);
  assert.deepEqual(errors,[]);
 });
 await check('撤回正在流式发送的记忆授权，迟到结果不落库',async()=>{
  await fixture(anon,{mode:'hold-before-first'});
  const calls=(await fixture(anon)).calls.length;
  const body=payload();
  const job=await api(user,'ai-gateway/jobs',body);
  const pending=stream(job,body);
  try {
   for(let attempt=0;attempt<100&&(await fixture(anon)).calls.length===calls;attempt++)await new Promise(resolve=>setTimeout(resolve,30));
   assert((await fixture(anon)).calls.length>calls,'Upstream fixture started');
   const revoked=await api(user,'memory/providers/all/consent',{requestId:key()},'DELETE');
   assert(revoked.memoryEpoch>selection.memoryEpoch);
  } finally {
   await fixture(anon,{mode:'success',release:true});
  }
  assert.notEqual((await pending).status,'succeeded');
  assert.equal((await api(user,'ai-gateway/jobs/'+job.id)).outputStored,false);
  await api(user,'ai-gateway/jobs',payload(),'POST',409);
 });
 await check('到期清理仅作用于记忆，旧请求在删除后依旧只重放状态',async()=>{
  const previous=await api(user,'privacy/retention');
  const preview=(await api(user,'privacy/retention/preview',{requestId:key(),scopes:['memory']})).item;
  assert(preview.summary.planned>=2);
  const receipt=(await api(user,'privacy/retention/jobs/'+preview.id+'/apply',{requestId:key(),confirmed:true,policyVersion:policy.policyVersion,version:preview.version})).item;
  assert(receipt.details.counts.memory>=2);
  assert.equal(receipt.details.memoryStatus,'completed');
  assert.equal((await api(user,'privacy/retention')).recordErasureEpoch,previous.recordErasureEpoch);
  assert.equal((await api(user,'memory')).items.length,0);
  const replay=await api(user,'ai-gateway/jobs',originalPayload);
  assert.equal(replay.memoryReplay,true);
  assert.equal(replay.id,originalJob.id);
 });
 await check('旧隐私清除入口同步写入计数及备份待确认',async()=>{
  await add(user,'another synthetic memory');
  const d=await api(user,'privacy/requests',{kind:'delete-memory',requestId:key()});
  assert.equal(d.item.details.local.deletedCounts.memoryEntries,1);
  assert.equal(d.item.details.backups.status,'pending-confirmation');
 });
 await check('注销实际删除本人记忆并撤销会话',async()=>{
  const account=await context(),password=key();
  await api(account,'auth/register',{username:'memclose_'+runId.replace('-','_'),password,name:'QA closure'});
  await preferences(account,{longTermMemory:true});
  await add(account,'Synthetic closure memory');
  const nonce=crypto.randomBytes(32).toString('hex');
  const requestId=key();
  const challenge=await api(account,'account-closure/prepare',{requestId,nonce,password});
  const done=await api(account,'account-closure/confirm',{requestId,nonce,challengeId:challenge.challengeId,confirmed:true,renewalAcknowledged:true});
  assert.equal(done.receipt.accountClosed,true);
  assert.equal(done.receipt.local.counts.memoryEntries,1);
  assert.equal(done.receipt.local.memoryStatus,'completed');
  await api(account,'memory',undefined,'GET',401);
 });

}
main().catch(error=>results.push({name:'专项执行',pass:false,error:h.redact(error.stack)})).finally(async()=>{
 await browser?.close();for(const c of contexts)await c.dispose().catch(()=>{});
 h.report.results.push(...results);h.report.errors.push(...errors);h.report.syntheticOnly=true;h.report.realProviderTested=false;
 h.report.buildSHA=sha(fs.readFileSync(path.join(root,buildPath)));await h.finish();
});
