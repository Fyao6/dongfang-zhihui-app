'use strict';
const assert=require('node:assert/strict');
const {makeHarness}=require('./负责人优化建议-任务告警测试工具.cjs'),h=makeHarness(),{api,check}=h,key=h.key;
async function run(){
 await h.start();const a=await h.seed(),f=require('./负责人优化建议-任务告警用例工具.cjs')(h,a),person=label=>h.register(label),digital=require('./负责人优化建议-数字权益用例工具.cjs')(h,a),quota=require('./负责人优化建议-会员额度用例工具.cjs')(h,a),commerce=require('./负责人优化建议-隐私逐域用例工具.cjs')(h,a);
 const ctx={h,api,a,f,key,check,person,digital,quota,commerce,scan:f.scan,due:f.due,barrier:f.barrier,snapshot:f.snapshot};
 h.report.scope='40 actual isolated HTTP/native process cases. Genuine CLI bootstrap, two real runner PIDs, hard process restarts, per-native-unit SQL claim fences, read-only monitor source completeness/episodes, durable HMAC loopback notification receipts. No production scheduler, channel settlement, provider deletion, automatic refunds or external notification claim.';
 await require('./负责人优化建议-任务告警运行专项.cjs')(ctx);
 await require('./负责人优化建议-任务告警消费专项.cjs')(ctx);
 await require('./负责人优化建议-任务告警监测专项.cjs')(ctx);
 await require('./负责人优化建议-任务告警通知专项.cjs')(ctx);
 await check('39 实际51个worker和run及51个真实收件告警跨页回查不混游标',async()=>{
  await f.config({enabled:true,confirmed:true,ruleVersion:key('pagination_rules'),tasks:Object.fromEntries(f.TASKS.map(kind=>[kind,{enabled:false}]))});
  const p=await person('pagination'),workerIds=[],receiptIds=[];let product;
  for(let i=0;i<51;i++){
   if(i&&i%22===0){h.report.actualPaginationPacing??=[];h.report.actualPaginationPacing.push({afterActualRows:i,waitMs:61000,reason:'unchanged original order/task write limits'});await new Promise(resolve=>setTimeout(resolve,61000));}
   const source=await f.pendingCallback(p,'page_'+i,{},product);product??=source.product;receiptIds.push(source.receiptId);const worker=key('page_worker_'+i);workerIds.push(worker);const tick=await f.tick(worker);assert.equal(tick.run.kind,'idle');assert.equal(tick.run.processed,0);
  }
  const runPage=await f.runs(),workerPage=await f.workers();assert.equal(runPage.items.length,50);assert(runPage.next);assert.equal(workerPage.items.length,50);assert(workerPage.next);
  const collect=async read=>{const output=[];let before;for(let i=0;i<30;i++){const page=await read(before?{before}:{});output.push(...page.items);if(!page.next)return output;before=page.next;}throw Error('Actual pagination did not terminate');};
  const runs=await collect(f.runs),workers=await collect(f.workers);assert.equal(new Set(runs.map(row=>row.id)).size,runs.length);assert(workerIds.every(id=>runs.some(row=>row.workerId===id)&&workers.some(row=>row.id===id)));
  await f.scan({thresholdSeconds:{callbackBacklog:0}});const alerts=await collect(f.alerts);assert(receiptIds.every(id=>alerts.some(row=>row.ruleCode==='callback_backlog'&&row.sourceId===id)));assert.equal(new Set(alerts.map(row=>row.id)).size,alerts.length);
  await api(a.admin,'admin/local-tasks/runs?before='+workerIds[0],undefined,'GET',404);await api(a.admin,'admin/local-tasks/workers?before='+runPage.items[0].id,undefined,'GET',404);
  const detail=await f.alert(alerts.find(row=>receiptIds.includes(row.sourceId)).id);assert(Array.isArray(detail.actions)&&Array.isArray(detail.notifications)&&Array.isArray(detail.attempts)&&Array.isArray(detail.receipts));f.safe(detail);
  h.report.paginationProof={actualNewWorkers:51,actualNewRuns:51,actualNewCallbackReceipts:51,actualNewBacklogAlerts:51,pageSize:50,attemptsAndReceiptsOver50Covered:false,attemptsAndReceiptsBoundary:'At most five attempts and one durable receipt per notification; no fabricated impossible pages.'};
 });
 await check('40 新9域显式归属与本人导出最小化、闭户和空临时proof不泄漏别人',async()=>{
  const p=await person('exportowner'),other=await person('exportother'),one=await f.pendingCallback(p,'own'),two=await f.pendingCallback(other,'foreign');await f.scan({thresholdSeconds:{callbackBacklog:0}});
  const inventory=(await api(p.c,'privacy/domains')).data;assert(Array.isArray(inventory.unclassifiedOwnerTables));for(const name of ['ops_task_runs','ops_workers','ops_claim_fences','payment_monitor_scans','payment_alerts','payment_alert_actions','payment_alert_notifications','payment_alert_notification_attempts','payment_alert_notification_receipts'])assert(!inventory.unclassifiedOwnerTables.some(value=>(typeof value==='string'?value:value.table||value.name)===name),'Explicitly registered '+name);
  const exported=(await api(p.c,'privacy/domains/export')).data;f.safe(exported);assert(JSON.stringify(exported.serverData).includes(one.receiptId));assert(!JSON.stringify(exported.serverData).includes(two.receiptId));assert.equal(exported.credentialsIncluded,false);assert.equal(exported.binaryIncluded,false);for(const name of ['localTaskRuns','localTaskWorkers','paymentMonitorScans','paymentAlerts','paymentAlertActions','paymentAlertNotifications','paymentAlertNotificationAttempts','paymentAlertNotificationReceipts'])assert(Array.isArray(exported.serverData[name]),'Explicit safe own metadata '+name);
  assert.equal((await f.snapshot(['ops_claim_fences'])).proofRows,0);await commerce.close(p);await api(p.c,'privacy/domains/export',undefined,'GET',401);await api(p.c,'admin/payment-alerts',undefined,'GET',401);assert.equal((await f.snapshot(['ops_claim_fences'])).proofRows,0);
  return {newTablesExplicitlyOwned:true,temporaryProofRows:0,sourceBodiesOrAdminNotesExported:false,productionEnabled:false,externalSent:false};
 });
 assert.equal(h.report.results.length,40,'Exactly forty real case results');
}
run().then(()=>h.finish()).catch(error=>h.finish(error));
