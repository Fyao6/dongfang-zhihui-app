// PAY09 actual API wrapper. Query transport uses a separate real loopback HTTP server.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import review from '../04_研发源码/app/cloud/generated/review.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
let initialization:Promise<any>|null=null;
let mode='enabled';
let runtimeEnv:any=null;
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
 Object.assign(runtimeEnv,env,{EW_PAYMENT_QUERY_SANDBOX_ENABLED:mode==='disabled'?'0':'1',EW_PAYMENT_QUERY_SANDBOX_SECRET_REF:mode==='invalid-ref'?'INVALID_REF':'EW_PAYMENT_QUERY_QA_SECRET',EW_PAYMENT_QUERY_SANDBOX_ENDPOINT:endpoint,EW_PAYMENT_CALLBACK_SANDBOX_ENABLED:mode==='callback-disabled'?'0':'1',EW_PAYMENT_QUERY_QA_SECRET:mode==='rotated-secret'?env.EW_PAYMENT_QUERY_QA_SECRET+'-rotated-qa':env.EW_PAYMENT_QUERY_QA_SECRET});
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
  order:await stmt('SELECT id,owner,payment_status,status,total_minor,currency FROM commerce_orders WHERE id=?',d.orderId||'').first(),
  job:await stmt('SELECT * FROM payment_recovery_jobs WHERE order_id=?',d.orderId||'').first(),
  ledger:await all('SELECT id,kind,request_id,amount_minor,status FROM commerce_payment_events WHERE order_id=? ORDER BY created,id',d.orderId||''),
  entitlements:await all('SELECT item_id,remaining,status FROM commerce_entitlements WHERE order_id=?',d.orderId||''),
  inventory:await all('SELECT s.id,s.stock,s.reserved,r.state FROM commerce_reservations r JOIN commerce_skus s ON s.id=r.sku_id WHERE r.order_id=? ORDER BY s.id',d.orderId||''),
  callbacks:await all('SELECT id,event_id,transaction_id,status,attempts FROM payment_callback_inbox WHERE order_id=? ORDER BY created,id',d.orderId||''),
  jobsCount:(await stmt('SELECT count(*) n FROM payment_recovery_jobs').first()).n,
 };
 if(d.action==='query-config'){
  if(!['enabled','disabled','invalid-ref','host','query','userinfo','fragment','callback-disabled','rotated-secret'].includes(d.mode))throw Error('Unsupported fixture mode');
  mode=d.mode;configured(env);return {changed:true};
 }
 if(['fail-apply-on','fail-apply-off'].includes(d.action)){
  await stmt('DROP TRIGGER IF EXISTS recovery_qa_apply_fault').run();
  if(d.action==='fail-apply-on')await stmt("CREATE TRIGGER recovery_qa_apply_fault BEFORE INSERT ON commerce_payment_events WHEN NEW.kind='sandbox_pay' BEGIN SELECT pay09_fixture_transient_failure(); END").run();
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
 if(u.pathname==='/__recovery-test/control'){
  if(request.method!=='POST'||!env.RECOVERY_TEST_TOKEN||request.headers.get('X-Recovery-Test')!==env.RECOVERY_TEST_TOKEN)return new Response('QA control token required',{status:403});
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
