// Owned digital/media API wrapper. Signed payment queries use a separate real loopback HTTP server.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import {DigitalEntitlements} from '../04_研发源码/app/cloud/lib/digital-entitlements';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import review from '../04_研发源码/app/cloud/generated/review.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
let initialization:Promise<any>|null=null;
let mode='enabled';
let callbackMode='enabled';
let runtimeEnv:any=null;
let digitalNow:number|null=null,digitalClockStarted=Date.now();
const realClock=Date.now.bind(Date);
DigitalEntitlements.prototype.clock=function(){return digitalNow===null?realClock():digitalNow+Math.max(0,realClock()-digitalClockStarted);};
const networkFetch=globalThis.fetch.bind(globalThis);
let allowedEndpoint='';
function configured(env:any){
 if(!runtimeEnv)runtimeEnv={...env};
 allowedEndpoint=env.EW_PAYMENT_QUERY_SANDBOX_ENDPOINT;
 let endpoint=allowedEndpoint;
 if(mode==='host')endpoint=endpoint.replace('127.0.0.1','localhost');
 else if(mode==='query')endpoint+='?arbitrary=1';
 else if(mode==='userinfo')endpoint=endpoint.replace('http://','http://username:password@');
 else if(mode==='fragment')endpoint+='#part';
 Object.assign(runtimeEnv,env,{EW_PAYMENT_QUERY_SANDBOX_ENABLED:mode==='disabled'?'0':'1',EW_PAYMENT_QUERY_SANDBOX_SECRET_REF:mode==='invalid-ref'?'INVALID_REF':'EW_PAYMENT_QUERY_QA_SECRET',EW_PAYMENT_QUERY_SANDBOX_ENDPOINT:endpoint,EW_PAYMENT_CALLBACK_SANDBOX_ENABLED:mode==='callback-disabled'||callbackMode==='disabled'?'0':'1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF:callbackMode==='invalid-ref'?'INVALID_REF':'EW_PAYMENT_CALLBACK_QA_SECRET',EW_PAYMENT_QUERY_QA_SECRET:mode==='rotated-secret'?env.EW_PAYMENT_QUERY_QA_SECRET+'-rotated-qa':env.EW_PAYMENT_QUERY_QA_SECRET});
 return runtimeEnv;
}
globalThis.fetch=(async(input:any,options:any)=>{
 const value=typeof input==='string'?input:input instanceof URL?input.href:input.url;
 if(value!==allowedEndpoint)throw Error('PAY09 QA blocks unrelated external HTTP');
 return networkFetch(input,options);
}) as typeof fetch;
async function init(env:any){
 if(!initialization)initialization=(async()=>{
  const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));
  await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));
 })();await initialization;
}
async function control(d:any,env:any){
 const stmt=(sql:string,...args:any[])=>env.DB.prepare(sql).bind(...args);
 const all=async(sql:string,...args:any[])=>(await stmt(sql,...args).all()).results;
 if(d.action==='clock'){
  if(d.nowMs!==null&&(!Number.isSafeInteger(d.nowMs)||d.nowMs<=0||d.nowMs>=4000000000000))throw Error('Invalid owned test clock');
  digitalNow=d.nowMs;digitalClockStarted=realClock();return {clockOverride:digitalNow,clockAdvancesWithRealElapsed:true};
 }
 if(d.action==='digital-snapshot'){
  const owner=d.owner||'',order=d.orderId||'';
  return {grants:await all('SELECT * FROM digital_entitlement_grants WHERE owner=? OR order_id=? ORDER BY id',owner,order),snapshots:await all('SELECT * FROM digital_order_snapshots WHERE owner=? OR order_id=? ORDER BY item_id',owner,order),leases:await all('SELECT id,owner,grant_id,request_id,created,expires FROM digital_access_leases WHERE owner=? OR grant_id IN (SELECT id FROM digital_entitlement_grants WHERE order_id=?) ORDER BY id',owner,order),uses:await all('SELECT * FROM digital_entitlement_uses WHERE owner=? OR grant_id IN (SELECT id FROM digital_entitlement_grants WHERE order_id=?) ORDER BY id',owner,order),assets:await all('SELECT * FROM digital_sandbox_assets ORDER BY media_id'),order:await all('SELECT id,payment_status,status,refunded_minor FROM commerce_orders WHERE id=?',order),legacy:await all('SELECT * FROM commerce_entitlements WHERE owner=? OR order_id=? ORDER BY id',owner,order),ledger:await all('SELECT id,kind,amount_minor FROM commerce_payment_events WHERE order_id=? ORDER BY id',order)};
 }
 if(['digital-fail-grant-on','digital-fail-grant-off','digital-fail-lease-on','digital-fail-lease-off'].includes(d.action)){
  const grant=d.action.includes('grant'),name=grant?'digital_qa_grant_fault':'digital_qa_lease_fault',table=grant?'digital_entitlement_grants':'digital_entitlement_uses';
  await env.DB.prepare('DROP TRIGGER IF EXISTS '+name).run();if(d.action.endsWith('-on'))await env.DB.prepare('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT sh06_fixture_storage_failure(); END').run();return {changed:true};
 }
 if(d.action==='transport-probe'){
  const raw=JSON.stringify({amountMinor:300,currency:'CNY',orderId:'transport-probe',queryId:'transport-probe'}),stamp=String(Math.floor(Date.now()/1000));
  const encoder=new TextEncoder(),key=await crypto.subtle.importKey('raw',encoder.encode(env.EW_PAYMENT_QUERY_QA_SECRET),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const signature=Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,encoder.encode(stamp+'.'+raw))),x=>x.toString(16).padStart(2,'0')).join('');
  try{
   const response=await networkFetch(env.EW_PAYMENT_QUERY_SANDBOX_ENDPOINT,{method:'POST',redirect:'manual',headers:{'Content-Type':'application/json','X-EW-Query-Timestamp':stamp,'X-EW-Query-Signature':signature},body:raw});
   const sample=(await response.text()).slice(0,200).replace(/[a-fA-F0-9]{64}/g,'[digest]');
   return {status:response.status,type:response.headers.get('content-type'),sample};
  }catch(error:any){return {name:error?.name,message:String(error?.message||error).slice(0,200).replace(/[a-fA-F0-9]{64}/g,'[digest]')};}
 }
 if(d.action==='snapshot')return {
  order:await stmt('SELECT id,owner,payment_status,fulfillment_status,aftersale_status,status,total_minor,refunded_minor,currency FROM commerce_orders WHERE id=?',d.orderId||'').first(),
  job:await stmt('SELECT * FROM payment_recovery_jobs WHERE order_id=?',d.orderId||'').first(),
  inbox:await stmt('SELECT * FROM payment_callback_inbox WHERE id=?',d.receiptId||'').first(),
  ledger:await all('SELECT id,kind,request_id,amount_minor,status FROM commerce_payment_events WHERE order_id=? ORDER BY created,id',d.orderId||''),
  entitlements:await all('SELECT item_id,remaining,status FROM commerce_entitlements WHERE order_id=?',d.orderId||''),
  inventory:await all('SELECT s.id,s.stock,s.reserved,r.state,r.quantity FROM commerce_reservations r JOIN commerce_skus s ON s.id=r.sku_id WHERE r.order_id=? ORDER BY s.id',d.orderId||''),
  callbacks:await all('SELECT id,event_id,transaction_id,status,attempts FROM payment_callback_inbox WHERE order_id=? ORDER BY created,id',d.orderId||''),
  lateCases:await all('SELECT * FROM payment_late_cases WHERE order_id=?',d.orderId||''),
  lateAttempts:await all('SELECT a.* FROM payment_late_attempts a JOIN payment_late_cases c ON c.id=a.case_id WHERE c.order_id=? ORDER BY a.created,a.id',d.orderId||''),
  jobsCount:(await stmt('SELECT count(*) n FROM payment_recovery_jobs').first()).n,
  inboxCount:(await stmt('SELECT count(*) n FROM payment_callback_inbox').first()).n,
  transactionsCount:(await stmt('SELECT count(*) n FROM payment_callback_transactions').first()).n,
 };
 if(d.action==='gate'){callbackMode=d.mode;configured(env);return {changed:true};}
 if(d.action==='query-config'){
  if(!['enabled','disabled','invalid-ref','host','query','userinfo','fragment','callback-disabled','rotated-secret'].includes(d.mode))throw Error('Unsupported fixture mode');
  mode=d.mode;configured(env);return {changed:true};
 }
 if(['fail-apply-on','fail-apply-off'].includes(d.action)){
  await stmt('DROP TRIGGER IF EXISTS recovery_qa_apply_fault').run();
  if(d.action==='fail-apply-on')await stmt("CREATE TRIGGER recovery_qa_apply_fault BEFORE INSERT ON commerce_payment_events WHEN NEW.kind='sandbox_pay' BEGIN SELECT pay09_fixture_transient_failure(); END").run();
  return {changed:true};
 }
 if(['fail-late-on','fail-late-off','fail-receive-on','fail-receive-off'].includes(d.action)){
  const name=d.action.startsWith('fail-late')?'late_qa_case_fault':'late_qa_receive_fault';
  const table=d.action.startsWith('fail-late')?'payment_late_cases':'payment_callback_inbox';
  await stmt('DROP TRIGGER IF EXISTS '+name).run();
  if(d.action.endsWith('-on'))await stmt('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT late_fixture_transient_failure(); END').run();
  return {changed:true};
 }
 if(d.receiptId&&['expired-lease','attempt-limit','due'].includes(d.action)){
  if(d.action==='expired-lease')await stmt("UPDATE payment_callback_inbox SET status='processing',attempts=1,lease_token='abandoned-qa-lease',lease_until=?,next_attempt=0 WHERE id=?",Date.now()-1000,d.receiptId).run();
  else if(d.action==='attempt-limit')await stmt("UPDATE payment_callback_inbox SET status='retry',attempts=4,lease_token='',lease_until=0,next_attempt=0 WHERE id=?",d.receiptId).run();
  else await stmt('UPDATE payment_callback_inbox SET next_attempt=0 WHERE id=?',d.receiptId).run();
  return {changed:true};
 }
 const actions:any={
  'expire-order':['UPDATE commerce_orders SET reserved_until=0 WHERE id=?',[d.orderId]],
  'close-order':["UPDATE commerce_orders SET status='closed' WHERE id=?",[d.orderId]],
  'expired-lease':['UPDATE payment_recovery_jobs SET lease_until=?,next_attempt=0 WHERE id=?',[Date.now()-1000,d.jobId]],
  'attempt-limit':["UPDATE payment_recovery_jobs SET status='retry',attempts=4,lease_token='',lease_until=0,next_attempt=0 WHERE id=?",[d.jobId]],
  due:['UPDATE payment_recovery_jobs SET next_attempt=0 WHERE id=?',[d.jobId]],
 };
 if(!actions[d.action])throw Error('Unsupported QA control');
 await stmt(actions[d.action][0],...actions[d.action][1]).run();
 if(d.action==='due')await stmt('UPDATE payment_callback_inbox SET next_attempt=0 WHERE id=(SELECT receipt_id FROM payment_recovery_jobs WHERE id=?)',d.jobId).run();
 return {changed:true};
}
export default {async fetch(request:Request,env:any,ctx:any){
 const u=new URL(request.url);
 if(!['127.0.0.1','localhost'].includes(u.hostname))return new Response('Local QA only',{status:403});
 if(['/__digital-test/control','/__recovery-test/control','/__callback-test/control','/__late-test/control'].includes(u.pathname)){
  const header=u.pathname==='/__digital-test/control'?'X-Digital-Test':u.pathname==='/__callback-test/control'?'X-Callback-Test':u.pathname==='/__late-test/control'?'X-Late-Test':'X-Recovery-Test';
  const token=u.pathname==='/__digital-test/control'?env.DIGITAL_TEST_TOKEN:env.RECOVERY_TEST_TOKEN;
  if(request.method!=='POST'||!token||request.headers.get(header)!==token)return new Response('QA control token required',{status:403});
  const raw=await request.text();if(raw.length>4096)return new Response('QA request too large',{status:413});
  try{return Response.json({isolated:true,...await control(JSON.parse(raw),env)});}catch{return Response.json({error:'Invalid isolated QA control'},{status:400});}
 }
 if(u.pathname.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);
 if(u.pathname.startsWith('/api/')){
  await init(env);return handleAPI(request,configured(env),ctx);
 }
 if(u.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(['/','/app'].includes(u.pathname))return new Response(review,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(u.pathname==='/experience')return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 return new Response('PAY09 isolated QA route not found',{status:404});
}};
