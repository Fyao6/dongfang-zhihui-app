'use strict';
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const taskFixtures=require('./负责人优化建议-任务告警用例工具.cjs');
const digitalFixtures=require('./负责人优化建议-数字权益用例工具.cjs');
const quotaFixtures=require('./负责人优化建议-会员额度用例工具.cjs');
const legacy=require('./负责人优化建议-任务告警场景夹具.json');
const FINITE='digitalFiniteGrants',PERIODS='membershipMaterializedQuota',JOBS='membershipBoundJobs';
const FACTS=['commerce_orders','commerce_order_items','commerce_payment_events','commerce_entitlements','commerce_skus',
 'digital_order_snapshots','digital_entitlement_grants','membership_order_snapshots','membership_subscriptions',
 'membership_ai_periods','membership_ai_events','membership_ai_allocations','ai_gateway_jobs','ai_gateway_wallets','ai_gateway_quota_events','ai_gateway_attempts'];
const hash=value=>crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
module.exports=async function monitorCases(ctx){
 const {h,check}=ctx;
 async function scene(name='empty'){
  assert(Object.hasOwn(legacy.scenarios,name));
  const value=await h.scenario(name);return {...value,f:taskFixtures(value.h,value.a),seed:legacy.scenarios[name]};
 }
 const coverage=(result,name)=>{const item=result.alerts.coverage.sources.find(x=>x.source===name);assert(item,'Actual coverage source '+name);return item;};
 const allAlerts=result=>result.alerts.items;
 const matching=(result,rule)=>allAlerts(result).filter(x=>x.ruleCode===rule);
 async function readonly(s,work,tables=FACTS){
  const before=await s.f.snapshot(tables);assert.equal(before.readOnly,true);assert.equal(before.proofRows,0);
  const result=await work(),after=await s.f.snapshot(tables);
  assert.equal(after.readOnly,true);assert.equal(after.proofRows,0);assert.equal(hash(before.tables),hash(after.tables),'Monitor must not sync/grant/charge/refund or change source facts');
  return {result,sourceDigest:hash(after.tables)};
 }
 async function stableScan(s,rule,change={}){return s.f.scan({ruleVersion:rule,...change});}
 function seedEvidence(s){return {instanceId:s.instanceId,seededRows:s.seed.seededRows,createdThroughProductApi:false,actualBootstrapAndProductInit:true};}
 async function flaggedScenario(name,rule,source){
  const s=await scene(name),scan=await readonly(s,()=>stableScan(s,'qa-monitor-stable'));
  assert.equal(coverage(scan.result,source).covered,true);assert(matching(scan.result,rule).length>0,'Expected actual legacy link finding '+rule);
  s.f.safe(scan.result);return {...seedEvidence(s),rule,sourceDigest:scan.sourceDigest};
 }

 await check('21 真实数字成交finite grant独立可核对且监测只读',async()=>{
  const s=await scene(),df=digitalFixtures(s.h,s.a);await df.setup();
  await df.policy({enabled:true,confirmed:true,ruleVersion:s.h.key('digital_policy'),validityDays:2,usesPerUnit:3,leaseSeconds:300});
  const person=await s.h.register('monitor_digital_buyer'),bought=await df.buy(person,'monitor actual digital');
  assert(bought.item?.id);const raw=(await s.f.snapshot(['digital_order_snapshots','digital_entitlement_grants'])).tables;
  assert.equal(raw.digital_order_snapshots.length,1);assert.equal(raw.digital_entitlement_grants.length,1);
  assert.equal(raw.digital_entitlement_grants[0].item_id,bought.order.items[0].id);
  const observed=await readonly(s,()=>stableScan(s,s.h.key('stable_digital_rule')));
  assert.equal(coverage(observed.result,FINITE).covered,true);
  assert(!allAlerts(observed.result).some(x=>x.sourceType===FINITE));
  assert.equal(observed.result.productionEnabled,false);
  return {instanceId:s.instanceId,sourceCreatedThroughActualProductApi:true,orderId:bought.order.id,sourceDigest:observed.sourceDigest};
 });

 await check('22 普通权益存在不能掩盖finite缺发或绑定错误，轮询不重复造episode',async()=>{
  const results=[];
  for(const [name,code]of [['finite-missing','digital_grant_missing'],['finite-binding','digital_grant_binding_mismatch']]){
   const s=await scene(name),policy='qa-monitor-stable',first=await readonly(s,()=>stableScan(s,policy));
   assert.equal((await s.f.snapshot(['commerce_entitlements'])).tables.commerce_entitlements.length,1);
   const old=matching(first.result,code)[0];assert(old);const again=await readonly(s,()=>stableScan(s,policy));
   const item=matching(again.result,code)[0];assert.equal(item.id,old.id);assert.equal(item.episode,old.episode);
   assert(item.seenScanCount>old.seenScanCount);assert.equal(item.firstSeen,old.firstSeen);
   results.push({...seedEvidence(s),rule:code,episode:item.episode,seenScanCount:item.seenScanCount,sourceDigest:again.sourceDigest});
  }
  return {independentSources:results};
 });

 await check('23 退款和期限届满、当前policy关闭不抹掉原finite grant历史',async()=>{
  const s=await scene('finite-refunded-history');
  const before=(await s.f.snapshot(['commerce_orders','digital_entitlement_grants'])).tables;
  assert.equal(before.commerce_orders[0].payment_status,'refunded');assert(before.digital_entitlement_grants[0].expires<Date.now());
  assert.equal((await s.h.api(s.a.admin,'admin/digital-entitlements')).data.policy.enabled,false);
  const observed=await readonly(s,()=>stableScan(s,'qa-monitor-stable'));
  assert.equal(coverage(observed.result,FINITE).covered,true);assert(!allAlerts(observed.result).some(x=>x.sourceType===FINITE));
  return {...seedEvidence(s),sourceDigest:observed.sourceDigest,currentAccessGateNotUsedAsHistory:true};
 });

 await check('24 真实会员懒授到周期桶与实际SSE结算后，退款关policy仍仅核历史事实',async()=>{
  const s=await scene(),qf=quotaFixtures(s.h,s.a);await qf.configure();
  await qf.policy({enabled:true,confirmed:true,ruleVersion:s.h.key('member_quota_policy')});
  const person=await qf.buyer('monitor_member'),bought=await qf.purchase(person,'monitor member',{credits:20});
  const pending=await qf.quota(person.c);assert.equal(pending.grantPending,true);
  assert.equal((await s.f.snapshot(['membership_ai_periods'])).tables.membership_ai_periods.length,0);
  const lazy=await readonly(s,()=>stableScan(s,'qa-monitor-stable'));
  assert.equal(coverage(lazy.result,PERIODS).covered,true);assert(!allAlerts(lazy.result).some(x=>x.sourceType===PERIODS));
  const quota=await qf.quota(person.c,true);assert(quota.periodId);assert.equal(quota.credits,20);
  const body=qf.payload(person.c,'monitor_member_job'),job=await qf.create(person.c,body),events=await qf.stream(person.c,job.id,body);
  const done=qf.done(events);assert(done);assert(['succeeded','partial'].includes(done.status));
  const actual=(await s.f.snapshot(['ai_gateway_jobs','membership_ai_allocations'])).tables;
  const j=actual.ai_gateway_jobs.find(x=>x.id===job.id),allocation=actual.membership_ai_allocations.find(x=>x.job_id===job.id);
  assert.equal(j.quota_source,'membership_period');assert.equal(allocation.period_id,quota.periodId);assert.equal(allocation.state,'settled');assert.equal(allocation.charged_credits,j.charged_credits);
  await qf.refund(bought);await qf.policy({enabled:false});
  const observed=await readonly(s,()=>stableScan(s,'qa-monitor-stable'));
  for(const source of [PERIODS,JOBS]){assert.equal(coverage(observed.result,source).covered,true);assert(!allAlerts(observed.result).some(x=>x.sourceType===source));}
  return {instanceId:s.instanceId,sourceCreatedThroughActualProductApi:true,originalOrderId:bought.order.id,actualMemberJobId:job.id,chargedCredits:j.charged_credits,sourceDigest:observed.sourceDigest};
 });

 await check('25 已物化会员桶缺唯一grant事件与孤儿grant事件均被实际识别',async()=>{
  return {missing:await flaggedScenario('member-missing-grant','membership_grant_event_missing',PERIODS),orphan:await flaggedScenario('member-orphan-grant','membership_grant_event_orphan',PERIODS)};
 });

 await check('26 会员来源job的allocation错桶、错结算及孤儿事实不冒充已正确记账',async()=>{
  return {binding:await flaggedScenario('member-job-binding','membership_job_binding_mismatch',JOBS),
   settlement:await flaggedScenario('member-job-settlement','membership_job_settlement_mismatch',JOBS),
   orphan:await flaggedScenario('member-orphan-allocation','membership_job_binding_mismatch',JOBS)};
 });

 await check('27 null/none、future、未刷新懒授与0额度及暂停历史不被强制补桶',async()=>{
  const s=await scene('member-lazy-zero-history'),before=(await s.f.snapshot(['membership_ai_periods','membership_ai_events','membership_order_snapshots'])).tables;
  assert.equal(before.membership_order_snapshots.length,7);assert.equal(before.membership_ai_periods.length,2);
  assert(before.membership_ai_periods.some(p=>p.credits===0));assert(before.membership_ai_events.some(e=>e.action==='grant'&&e.credits===0));
  const observed=await readonly(s,()=>stableScan(s,'qa-monitor-stable'));
  for(const source of [PERIODS,JOBS]){assert.equal(coverage(observed.result,source).covered,true);assert(!allAlerts(observed.result).some(x=>x.sourceType===source));}
  assert.equal((await s.h.api(s.a.admin,'admin/membership-ai-quota')).data.policy.enabled,false);
  return {...seedEvidence(s),materializedPeriods:2,paidSnapshotRows:7,sourceDigest:observed.sourceDigest,noCurrentLivePredicateRequired:true};
 });

 await check('28 坏冻结JSON及5001真实固定行截断均not-covered且不解除原告警',async()=>{
  const results=[];
  for(const name of ['finite-bad-json','finite-truncated']){
   const s=await scene(name),before=(await s.f.alert('qa-prior-finite-alert')).item;
   assert.equal(before.status,'open');const observed=await stableScan(s,'qa-monitor-stable');
   const source=coverage(observed,FINITE);assert.equal(source.covered,false);assert.equal(observed.alerts.coverage.partial,true);
   if(name==='finite-truncated')assert.equal(source.truncated,true);else assert(/invalid|json|policy/.test(source.reason));
   const after=(await s.f.alert(before.id)).item;assert.equal(after.status,'open');assert.equal(after.version,before.version);assert.equal(after.resolvedAt,0);
   results.push({...seedEvidence(s),covered:false,reason:source.reason,priorAlertStillOpen:true});
  }
  return {independentUncertainty:results};
 });

 await check('29 null老化阈值和规则变化不解除，真实业务清除后不被外部未知指标阻挡',async()=>{
  const s=await scene(),policy='qa-monitor-stable',pending=await s.f.pendingCallback(s.a.admin,'real backlog');
  const first=await stableScan(s,policy,{thresholdSeconds:{callbackBacklog:0}}),alert=matching(first,'callback_backlog').find(x=>x.sourceId===pending.receiptId);assert(alert);
  let observed=await stableScan(s,policy,{thresholdSeconds:{callbackBacklog:null}});
  assert.equal(coverage(observed,'aging:callback_backlog').covered,false);
  assert.equal((await s.f.alert(alert.id)).item.status,'open');
  await stableScan(s,'qa-monitor-changed',{thresholdSeconds:{callbackBacklog:31536000}});
  assert.equal((await s.f.alert(alert.id)).item.status,'open');
  await s.h.api(s.a.admin,'admin/payment-callbacks/process',{limit:1});
  const paid=(await s.h.api(s.a.admin,'commerce/orders/'+encodeURIComponent(pending.order.id))).data;assert.equal(paid.paymentStatus,'paid');
  observed=await stableScan(s,policy,{thresholdSeconds:{callbackBacklog:0}});
  for(const value of Object.values(observed.alerts.coverage.unsupportedMetrics))assert.equal(value,null);
  assert.equal((await s.f.alert(alert.id)).item.status,'resolved');
  return {instanceId:s.instanceId,actualSignedCallback:true,orderId:paid.id,priorAlertId:alert.id,externalFailuresRemainUnknown:true};
 });

 await check('30 实际轮询episode稳定，人工ack幂等不改资金，真实再次异常另立episode',async()=>{
  const s=await scene(),policy='qa-monitor-stable',pending=await s.f.pendingCallback(s.a.admin,'real amount mismatch',{amountMinor:1});
  await s.h.api(s.a.admin,'admin/payment-callbacks/process',{limit:1});
  let observed=await stableScan(s,policy),first=matching(observed,'callback_manual_review').find(x=>x.sourceId===pending.receiptId);assert(first);
  observed=await stableScan(s,policy);const repeated=matching(observed,'callback_manual_review').find(x=>x.id===first.id);assert(repeated);assert(repeated.seenScanCount>first.seenScanCount);
  const request=s.h.key('ack_nonce'),note='本轮合成异常的人工核查记录';const before=(await s.f.snapshot(FACTS)).tables;
  const ack=await s.f.ack(repeated,{id:request,note}),again=await s.f.ack(repeated,{id:request,note});
  assert.equal(ack.item.status,'acknowledged');assert.equal(again.replayed,true);
  await s.f.ack(repeated,{id:s.h.key('stale_ack'),version:repeated.version,note,expected:409});
  assert.equal((await s.f.alert(first.id)).actions.length,1);assert.equal(hash((await s.f.snapshot(FACTS)).tables),hash(before));
  await s.h.api(s.a.admin,'admin/payment-callbacks/'+encodeURIComponent(pending.receiptId)+'/retry',{});
  await stableScan(s,policy);assert.equal((await s.f.alert(first.id)).item.status,'resolved');
  await s.h.api(s.a.admin,'admin/payment-callbacks/process',{limit:1});observed=await stableScan(s,policy);
  const recurrence=matching(observed,'callback_manual_review').filter(x=>x.sourceId===pending.receiptId).find(x=>x.status==='open');assert(recurrence);
  assert.notEqual(recurrence.id,first.id);assert.equal(recurrence.episode,first.episode+1);
  const order=(await s.h.api(s.a.admin,'commerce/orders/'+encodeURIComponent(pending.order.id))).data;assert.equal(order.paymentStatus,'unpaid');
  return {instanceId:s.instanceId,originalEpisode:first.episode,newEpisode:recurrence.episode,actualHumanActionCount:1,fundsChangedByAck:false};
 });

 await check('31 capture后真实租约失效与实际admin撤权均阻断scan告警outbox最终写入',async()=>{
  const s=await scene(),pending=await s.f.pendingCallback(s.a.admin,'held monitor'),observer=await s.h.register('independent_monitor_admin');
  await s.h.api(s.a.admin,'admin/users/'+observer.credential.id,{role:'admin'},'PATCH');
  const tables=['payment_monitor_scans','payment_alerts','payment_alert_notifications','payment_callback_inbox','commerce_orders','commerce_entitlements'];
  await s.f.only('payment_monitor',{ruleVersion:'qa-monitor-stable',thresholdSeconds:{callbackBacklog:0}});await s.f.due('payment_monitor');
  const before=await s.f.snapshot(tables);await s.f.barrier.arm('payment_monitor',1,'after-capture');
  const worker=s.h.key('lease_held_worker'),promise=s.f.tick(worker).then(value=>({value}),error=>({error}));
  try{
   await s.f.barrier.entered();const run=(await s.f.runs({workerId:worker})).items[0];assert(run&&run.status==='running');
   await s.h.control({action:'ops-expire-runtime-lease',runId:run.id});
  }finally{await s.f.barrier.release();}
  const outcome=await promise;if(outcome.error)throw outcome.error;const leaseResult=outcome.value;
  assert(!leaseResult.items?.some(item=>item.status==='succeeded'));
  assert.equal(hash((await s.f.snapshot(tables)).tables),hash(before.tables));
  await s.f.due('payment_monitor');await s.f.barrier.arm('payment_monitor',1,'after-capture');
  const body={runtimeId:s.h.manifest.core.runtimeId,workerId:s.h.key('actor_held_worker'),requestId:s.h.key('held_request'),appSha256:s.h.manifest.core.appSha256};
  const held=s.h.api(s.a.admin,'admin/local-tasks/tick',body,'POST',null).then(value=>({value}),error=>({error}));
  try{
   await s.f.barrier.entered();await s.h.api(observer.c,'admin/users/'+s.a.credentials.admin.id,{role:'user'},'PATCH');
  }finally{await s.f.barrier.release();}
  const terminal=await held;if(terminal.error)throw terminal.error;const denied=terminal.value;
  assert.equal(denied.status,s.h.target==='python'?403:401);assert(!Object.hasOwn(denied.data,'items'));assert(!Object.hasOwn(denied.data,'run'));
  assert(!Object.hasOwn(denied.data,'coverage'));assert(!Object.hasOwn(denied.data,'sourceIds'));
  const currentAuth=await s.h.api(s.a.admin,'auth/status');assert.equal(currentAuth.status,200);
  assert.equal(currentAuth.data.user.id,s.a.credentials.admin.id);assert.equal(currentAuth.data.user.role,'user');
  const observerTasks=taskFixtures(s.h,{...s.a,admin:observer.c}),after=await observerTasks.snapshot(tables);
  assert.equal(hash(after.tables),hash(before.tables));assert.equal(after.proofRows,0);
  const inbox=after.tables.payment_callback_inbox.find(x=>x.id===pending.receiptId);assert.equal(inbox.attempts,0);
  return {instanceId:s.instanceId,actualAfterCaptureBarrier:true,expiredLeaseBlocked:true,actualRoleWithdrawalStatus:denied.status,sourceAttemptsUnchanged:true};
 });
};
