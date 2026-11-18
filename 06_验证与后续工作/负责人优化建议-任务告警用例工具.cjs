'use strict';
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const TASKS=['payment_callbacks','payment_recovery','privacy_objects','payment_monitor','alert_notifications'];
const CONFIG_KEYS=['revision','enabled','confirmed','ruleVersion','tasks','thresholdSeconds'];
const THRESHOLDS=['callbackBacklog','recoveryBacklog','lateRefundPending','lateRefundProcessing','privacyObjectPending'];
const EVENT_KEYS=['eventId','alertId','episode','ruleCode','severity','sourceType','sourceId','observedAt','environment'];
module.exports=function taskFixtures(h,a){
 const {api}=h,enc=encodeURIComponent;let serial=0,receiverContext;
 const context=value=>value?.c||value;
 const owner=value=>value?.credential?.id||value?.credentials?.id||value?.id;
 const requestId=label=>h.key(label+'_'+(++serial));
 const runtime=async(c=a.admin)=>(await api(context(c),'admin/local-tasks/runtime')).data;
 const settings=async(c=a.admin)=>(await api(context(c),'admin/local-tasks/config')).data;
 const query=value=>{const params=new URLSearchParams(Object.entries(value||{}).filter(([,v])=>v!==undefined&&v!==null).map(([k,v])=>[k,String(v)]));return params.size?'?'+params:'';};
 async function config(change={},c=a.admin,expected=200){
  const old=(await settings(c)).config,body=Object.fromEntries(CONFIG_KEYS.map(key=>[key,old[key]]));
  Object.assign(body,change);body.tasks=Object.fromEntries(TASKS.map(kind=>[kind,{...old.tasks[kind],...change.tasks?.[kind]}]));body.thresholdSeconds={...old.thresholdSeconds,...change.thresholdSeconds};
  return (await api(context(c),'admin/local-tasks/config',body,'PATCH',expected)).data;
 }
 async function only(kind,change={}){
  if(h.prepareTaskWrites)await h.prepareTaskWrites(a.admin,8);
  const tasks=Object.fromEntries(TASKS.map(name=>[name,{enabled:name===kind,...change.tasks?.[name]}]));
  return config({enabled:true,confirmed:true,ruleVersion:requestId('confirmed_rule'),...change,tasks});
 }
 function tick(workerId,{request=requestId('tick'),c=a.admin,expected=200,body={}}={}){
  const pending=(async()=>{assert(h.manifest?.core,'Only the actual bootstrap manifest supplies runtime and APP identity');return (await api(context(c),'admin/local-tasks/tick',{runtimeId:h.manifest.core.runtimeId,workerId,requestId:request,appSha256:h.manifest.core.appSha256,...body},'POST',expected)).data;})();
  pending.catch(()=>{});return pending; // Observe transport rejection during a held-response test; the real awaited promise still rejects.
 }
 const runs=async(parameters={},c=a.admin)=>(await api(context(c),'admin/local-tasks/runs'+query(parameters))).data;
 const run=async(id,c=a.admin)=>(await api(context(c),'admin/local-tasks/runs/'+enc(id))).data;
 const workers=async(parameters={},c=a.admin)=>(await api(context(c),'admin/local-tasks/workers'+query(parameters))).data;
 const alerts=async(parameters={},c=a.admin)=>(await api(context(c),'admin/payment-alerts'+query(parameters))).data;
 const alert=async(id,parameters={},c=a.admin)=>(await api(context(c),'admin/payment-alerts/'+enc(id)+query(parameters))).data;
 const ack=async(item,{id=requestId('ack'),note='本轮隔离告警的明确人工确认',c=a.admin,expected=200,version=item.version}={})=>(await api(context(c),'admin/payment-alerts/'+enc(item.id)+'/ack',{requestId:id,version,note},'POST',expected)).data;
 const retry=async(id,c=a.admin,expected=200)=>(await api(context(c),'admin/payment-alerts/notifications/'+enc(id)+'/retry',{},'POST',expected)).data;
 async function receiver(data){
  const endpoint=h.receiverEndpoint;assert(/^http:\/\/(?:127\.0\.0\.1|\[::1\]):[1-9][0-9]{0,4}\/task-alert-fixture\/events$/.test(endpoint),'Receiver controls remain in their one owned loopback fixture');
  receiverContext??=await h.context();const response=await receiverContext.fetch(new URL('/__task-alert-fixture/control',endpoint).href,{method:data?'POST':'GET',headers:{'X-Task-Alert-Test':process.env.TASK_ALERT_TEST_TOKEN},...(data?{data}:{})});assert.equal(response.status(),200);const value=await response.json();assert.equal(value.isolated,true);assert.equal(value.externalSent,false);assert.equal(value.credentialHeadersStored,false);return value;
 }
 async function waitFor(read,predicate,{timeout=30000,interval=1000}={}){const start=Date.now();let latest;while(Date.now()-start<timeout){latest=await read();if(predicate(latest))return latest;await new Promise(resolve=>setTimeout(resolve,interval));}throw Error('Actual state did not reach the expected bounded condition');}
 function safe(value,{allowAdminNote=true}={}){
  const forbidden=/^(session_hash|sessionHash|lease_token|leaseToken|run_lease_token|runLeaseToken|schedule_lease_token|scheduleLeaseToken|adapter_binding|adapterBinding|secretHash|secret_hash|password|passwordHash|apiKey|object_key|objectKey)$/i;
  const walk=item=>{if(!item||typeof item!=='object')return;for(const [key,v]of Object.entries(item)){assert(!forbidden.test(key),'No private proof or credential field '+key);if(!allowAdminNote)assert(!['note','ackBy','actor','owner'].includes(key),'No private actor/note in outbound fixture data');walk(v);}};walk(value);
  const encoded=JSON.stringify(value);for(const [key,secret]of Object.entries(process.env))if(/SECRET|TOKEN|PASSWORD|CREDENTIAL/i.test(key)&&secret&&secret.length>=12)assert(!encoded.includes(secret),'No environment value in public metadata');return true;
 }
 function event(value){assert.deepEqual(Object.keys(value).sort(),[...EVENT_KEYS].sort());assert.equal(value.environment,'sandbox');assert.equal(typeof value.episode,'number');assert(Number.isSafeInteger(value.episode)&&value.episode>0);assert(Number.isSafeInteger(value.observedAt)&&value.observedAt>=0);safe(value,{allowAdminNote:false});return value;}
 async function pendingCallback(person,label='queued',change={},existingProduct=null){
  const c=context(person);if(!existingProduct)await api(a.admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
  const product=existingProduct||(await api(a.admin,'admin/commerce/products',{title:'任务告警隔离样品 '+label,type:'physical',environment:'sandbox',status:'published',currency:'CNY',shippingCountries:['CN'],stock:500,priceMinor:300,sku:requestId('sku')})).data.item;
  const order=(await api(c,'commerce/orders',{requestId:requestId('order'),environment:'sandbox',items:[{skuId:product.skuId,quantity:1}],shippingAddress:{name:'合成收件人',country:'CN',city:'测试市',address:'本机隔离测试路 1 号',postalCode:'000000'}})).data;
  const body={eventId:crypto.randomUUID(),transactionId:crypto.randomUUID(),orderId:order.id,type:'payment.succeeded',amountMinor:order.totalMinor,currency:order.currency,...change},raw=JSON.stringify(body),stamp=String(Math.floor(Date.now()/1000));
  const response=await a.anonymous.post(h.base+'/api/payment-callbacks/sandbox',{data:Buffer.from(raw),headers:{'Content-Type':'application/json','X-EW-Callback-Timestamp':stamp,'X-EW-Callback-Signature':crypto.createHmac('sha256',process.env.EW_PAYMENT_CALLBACK_QA_SECRET).update(stamp+'.'+raw).digest('hex')}});assert.equal(response.status(),202);const received=await response.json();return {person,product,order,body,receiptId:received.receiptId};
 }
 const due=kind=>h.control({action:'ops-due',kind});
 const snapshot=async(tables)=>h.control({action:'ops-snapshot',...(tables?{tables}:{})});
 async function scan(change={}){await only('payment_monitor',change);await due('payment_monitor');const result=await tick(requestId('monitor_worker'));return {...result,alerts:await alerts()};}
 const barrier={arm:(kind,at=1,phase='before-claim')=>h.control({action:'ops-barrier-arm',kind,at,phase}),state:()=>h.control({action:'ops-barrier-state'}),entered:()=>waitFor(()=>h.control({action:'ops-barrier-state'}),value=>value.entered,{timeout:20000,interval:100}),release:()=>h.control({action:'ops-barrier-release'})};
 return {TASKS,CONFIG_KEYS,THRESHOLDS,EVENT_KEYS,context,owner,requestId,runtime,settings,config,only,tick,runs,run,workers,alerts,alert,ack,retry,receiver,waitFor,safe,event,pendingCallback,due,snapshot,scan,barrier};
};
