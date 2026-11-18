// Fixed owned-fixture controls; every statement/result is forwarded to the actual D1 binding.
const KINDS=['payment_callbacks','payment_recovery','privacy_objects','payment_monitor','alert_notifications'];
let gate={kind:'',at:1,seen:0,entered:false,phase:'before-claim'},release:(()=>void)|null=null;
const nativeStatements=new WeakMap<object,any>(),sqls=new WeakMap<object,string>(),dbs=new WeakMap<object,any>();
const originals:Record<string,string>={},overrides:Record<string,string>={};
export function applyTaskEnv(env:any){return Object.assign(env,overrides);}
async function barrier(kind:string,phase='before-claim'){
 if(gate.kind!==kind||gate.phase!==phase)return;gate.seen++;if(gate.seen!==gate.at)return;gate.entered=true;
 await new Promise<void>((resolve,reject)=>{const timer=setTimeout(()=>{release=null;reject(Error('owned_fixture_barrier_timeout'));},95000);release=()=>{clearTimeout(timer);release=null;resolve();};});
}
export function controlledDB(native:any){
 if(dbs.has(native))return dbs.get(native);
 const statement=(value:any,sql:string):any=>{const proxy=new Proxy(value,{get(target,key){if(key==='bind')return(...args:any[])=>statement(target.bind(...args),sql);const result=Reflect.get(target,key);return typeof result==='function'?result.bind(target):result;}});nativeStatements.set(proxy,value);sqls.set(proxy,sql);return proxy;};
 const proxy=new Proxy(native,{get(target,key){
  if(key==='prepare')return(sql:string)=>statement(target.prepare(sql),sql);
  if(key==='batch')return async(values:any[])=>{
   const sql=values.map(v=>sqls.get(v)||'').join('\n'),proof=/INSERT\s+INTO\s+ops_claim_fences/i.test(sql);
   if(proof){let kind='';if(/INSERT\s+INTO\s+payment_monitor_scans/i.test(sql))await barrier('payment_monitor','after-capture');
    else{if(/UPDATE\s+payment_callback_inbox\b/i.test(sql)&&/attempts\s*=\s*attempts\s*\+\s*1/i.test(sql))kind='payment_callbacks';
     if(/UPDATE\s+payment_recovery_jobs\b/i.test(sql)&&/attempts\s*=\s*attempts\s*\+\s*1/i.test(sql))kind='payment_recovery';
     if(/UPDATE\s+privacy_object_deletions\b/i.test(sql)&&/attempts\s*\+\s*1/i.test(sql))kind='privacy_objects';
     if(/UPDATE\s+payment_alert_notifications\b/i.test(sql)&&/attempts\s*=\s*attempts\s*\+\s*1/i.test(sql))kind='alert_notifications';if(kind)await barrier(kind);
    }
   }return target.batch(values.map(v=>nativeStatements.get(v)||v));
  };const value=Reflect.get(target,key);return typeof value==='function'?value.bind(target):value;
 }});dbs.set(native,proxy);return proxy;
}
const TABLES=['ops_runtime_identity','ops_task_config','ops_task_schedules','ops_task_runs','ops_workers','ops_claim_fences','payment_monitor_scans','payment_alerts','payment_alert_actions','payment_alert_notifications','payment_alert_notification_attempts','payment_alert_notification_receipts','payment_callback_inbox','payment_recovery_jobs','payment_late_cases','privacy_object_deletions','commerce_orders','commerce_products','digital_sandbox_assets','commerce_order_items','commerce_payment_events','commerce_entitlements','commerce_reservations','commerce_skus','digital_order_snapshots','digital_entitlement_grants','membership_ai_periods','membership_ai_events','membership_ai_allocations','ai_gateway_jobs','ai_gateway_attempts','ai_gateway_wallets','ai_gateway_quota_events','membership_order_snapshots','membership_subscriptions'];
const PRIVATE=new Set(['session_hash','lease_token','run_lease_token','schedule_lease_token','adapter_binding','token','password_hash']);
export async function taskControl(d:any,db:any,env:any){
 const action=d.action||'';if(!action.startsWith('ops-')&&!['notification-adapter','notification-proxy-env','due-notification','expire-notification-lease'].includes(action))return undefined;
 const stmt=(sql:string,...args:any[])=>db.prepare(sql).bind(...args),all=async(sql:string,...args:any[])=>(await stmt(sql,...args).all()).results;
 if(action==='ops-barrier-arm'){if(!KINDS.includes(d.kind)||!Number.isInteger(d.at??1)||(d.at??1)<1||(d.at??1)>10||!['before-claim','after-capture'].includes(d.phase??'before-claim'))throw Error('Invalid barrier');gate={kind:d.kind,at:d.at??1,seen:0,entered:false,phase:d.phase??'before-claim'};return {armed:true,beforeNativeTransaction:gate.phase==='before-claim'};}
 if(action==='ops-barrier-state')return {...gate};
 if(action==='ops-barrier-release'){release?.();gate.kind='';return {released:true};}
 if(action==='notification-proxy-env'){if(!['enabled','restore'].includes(d.mode))throw Error('Invalid proxy mode');for(const name of ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy']){originals[name]??=env[name]||'';overrides[name]=d.mode==='restore'?originals[name]:name.toLowerCase()==='no_proxy'?'':env.TASK_ALERT_RECEIVER_ENDPOINT.split('/task-alert-fixture/')[0];}applyTaskEnv(env);return {changed:true,serverEnvironmentOnly:true,hostileProxyEnabled:d.mode==='enabled',proxyValuesReturned:false,scope:'Worker environment binding; native fetch uses no environment proxy'};}
 if(['ops-runtime-env','notification-adapter'].includes(action)){
  const names=action==='ops-runtime-env'?['EW_LOCAL_TASK_RUNTIME_ENABLED','EW_LOCAL_TASK_RUNTIME_ID','EW_LOCAL_TASK_MANIFEST_SHA256']:['EW_LOCAL_ALERT_FIXTURE_ENABLED','EW_LOCAL_ALERT_FIXTURE_ENDPOINT','EW_LOCAL_ALERT_FIXTURE_SECRET_REF','EW_LOCAL_ALERT_QA_SECRET'];for(const name of names){originals[name]??=env[name]||'';overrides[name]=originals[name];}
  const mode=d.mode||'enabled';if(action==='ops-runtime-env'){if(mode==='disabled')overrides[names[0]]='0';else if(mode==='runtime-mismatch')overrides[names[1]]=crypto.randomUUID();else if(mode==='manifest-mismatch')overrides[names[2]]='0'.repeat(64);else if(mode!=='enabled')throw Error('Invalid mode');}
  else{const endpoint=originals[names[1]],invalid:Record<string,string>={host:endpoint.replace('127.0.0.1','localhost'),'short-ip':endpoint.replace('127.0.0.1','127.1'),'integer-ip':endpoint.replace('127.0.0.1','2130706433'),userinfo:endpoint.replace('http://','http://qa:qa@'),query:endpoint+'?qa=1',fragment:endpoint+'#qa',path:endpoint+'/other','leading-space':' '+endpoint,'mapped-ip':endpoint.replace('127.0.0.1','[::ffff:127.0.0.1]'),https:endpoint.replace('http:','https:')};if(mode==='disabled')overrides[names[0]]='0';else if(mode==='invalid-ref')overrides[names[2]]='INVALID_REF';else if(mode==='rotated-secret')overrides[names[3]]=originals[names[3]]+'-rotated';else if(mode in invalid)overrides[names[1]]=invalid[mode];else if(mode!=='enabled')throw Error('Invalid mode');}applyTaskEnv(env);return {changed:true,serverEnvironmentOnly:true,mode};
 }
 if(action==='ops-due'){if(!KINDS.includes(d.kind))throw Error('Invalid task');await stmt('UPDATE ops_task_schedules SET next_due=0 WHERE kind=?',d.kind).run();return {changed:true,scheduleOnly:true};}
 if(action==='due-notification'){await stmt('UPDATE payment_alert_notifications SET next_attempt=0 WHERE id=?',d.id).run();return {changed:true,attemptsUnchanged:true};}
 if(action==='expire-notification-lease'){await stmt('UPDATE payment_alert_notifications SET lease_until=? WHERE id=?',Date.now()-1000,d.id).run();return {fixtureMutation:true,deadlineOnly:true,attemptsUnchanged:true};}
 if(action==='ops-expire-runtime-lease'){const stamp=Date.now()-1000;await db.batch([stmt('UPDATE ops_task_runs SET lease_until=? WHERE id=?',stamp,d.runId),stmt('UPDATE ops_task_schedules SET lease_until=? WHERE last_run_id=?',stamp,d.runId)]);return {fixtureMutation:true,deadlineOnly:true};}
 if(action==='ops-snapshot'){const selected=d.tables||TABLES;if(!Array.isArray(selected)||selected.some((name:string)=>!TABLES.includes(name)))throw Error('Invalid snapshot');const tables:any={};for(const table of selected){if(!await stmt("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",table).first()){tables[table]=null;continue;}const columns=(await all('PRAGMA table_info('+table+')')).map((r:any)=>r.name).filter((name:string)=>!PRIVATE.has(name));tables[table]=await all('SELECT '+columns.map((name:string)=>'"'+name+'"').join(',')+' FROM '+table+' LIMIT 6000');}return {tables,readOnly:true,databaseNow:Date.now(),proofRows:(await stmt('SELECT count(*) n FROM ops_claim_fences').first()).n};}
 if(action==='ops-marker-immutability'){const blocked=[];for(const sql of ['UPDATE ops_runtime_identity SET created=created+1 WHERE id=1','DELETE FROM ops_runtime_identity WHERE id=1','INSERT OR REPLACE INTO ops_runtime_identity SELECT * FROM ops_runtime_identity']){try{await db.prepare(sql).run();}catch{blocked.push(true);continue;}throw Error('Marker unprotected');}return {blocked,actualDatabaseTriggers:true};}
 if(action==='ops-change-lease'){if(d.mode==='run-token')await stmt("UPDATE ops_task_runs SET lease_token='owned-invalid-run-token' WHERE id=?",d.runId).run();else if(d.mode==='schedule-token')await stmt("UPDATE ops_task_schedules SET lease_token='owned-invalid-schedule-token' WHERE last_run_id=?",d.runId).run();else if(d.mode==='budget'){const stamp=Date.now()+500;await db.batch([stmt('UPDATE ops_task_runs SET lease_until=? WHERE id=?',stamp,d.runId),stmt('UPDATE ops_task_schedules SET lease_until=? WHERE last_run_id=?',stamp,d.runId)]);}else throw Error('Invalid lease mutation');return {fixtureMutation:true,leaseOnly:true};}
 if(action==='ops-callback-state'){if(!['received','retry','manual_review','applied'].includes(d.status))throw Error('Invalid state');await stmt('UPDATE payment_callback_inbox SET status=?,next_attempt=0,lease_until=0 WHERE id=?',d.status,d.id).run();return {fixtureMutation:true,statusOnly:true};}
 throw Error('Unsupported fixed task control');
}
