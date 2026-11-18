// Isolated D1/R2 API wrapper. Only the reserved QA provider endpoints map to a real loopback SSE process.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import {MembershipLifecycle} from '../04_研发源码/app/cloud/lib/membership-lifecycle';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import review from '../04_研发源码/app/cloud/generated/review.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
import legacy from './负责人优化建议-任务告警额度兼容旧库夹具.sql';
let initialization:Promise<void>|null=null,nowMs:number|null=null,clockStarted=Date.now(),fixtureEndpoint='';
let pauseOrderId:string|null=null,entered=false,release:(()=>void)|null=null,failOrderId:string|null=null,failCount=0;
const realClock=Date.now.bind(Date),nativeFetch=globalThis.fetch.bind(globalThis);
const clock=()=>nowMs===null?realClock():nowMs+Math.max(0,realClock()-clockStarted);
MembershipLifecycle.prototype.clock=function(){return clock();};
const originalCallback=MembershipLifecycle.prototype.onCommercePayment;
MembershipLifecycle.prototype.onCommercePayment=async function(orderId:string){if(failOrderId===orderId&&failCount>0){--failCount;throw Error('QA_ONLY_MEMBERSHIP_CALLBACK_INTERRUPTED');}return originalCallback.call(this,orderId);};
globalThis.fetch=(async(input:any,options:any={})=>{
 const original=typeof input==='string'?input:input instanceof URL?input.href:input.url;
 const paths:Record<string,string>={'https://alpha.gateway.invalid/v1/responses':'/alpha/responses','https://beta.gateway.invalid/v1/messages':'/beta/messages'};
 if(!paths[original]||!/^http:\/\/127\.0\.0\.1:\d+\/member-quota-fixture$/.test(fixtureEndpoint))throw Error('Member quota QA blocks unrelated external HTTP');
 return nativeFetch(fixtureEndpoint+paths[original],options);
}) as typeof fetch;
async function init(env:any){
 if(!initialization)initialization=(async()=>{
  const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));
  await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));
  const old=legacy.split(/\r?\n/).map((s:string)=>s.trim()).filter((s:string)=>s&&!s.startsWith('--'));
  await env.DB.batch(old.map((s:string)=>env.DB.prepare(s)));
 })();await initialization;
}
function controlledDB(db:any){
 const statements=new WeakMap<object,{sql:string,args:any[]}>();
 return new Proxy(db,{get(target,key){
  if(key==='prepare')return (sql:string)=>{const statement=target.prepare(sql);statements.set(statement,{sql,args:[]});return new Proxy(statement,{get(native,method){
   if(method==='bind')return (...input:any[])=>{const args=[...input];
    // The only altered input is the trusted clock at creation of a genuine sandbox payment event.
    // Guards, amount, owner, snapshot, inventory and accounting remain the product's real SQL.
    if(nowMs!==null&&/^INSERT INTO commerce_payment_events\b/.test(sql)&&args[5]==='sandbox_pay'&&args[10]==='applied')args[11]=clock();
    const bound=native.bind(...args);statements.set(bound,{sql,args});return bound;
   };const value=Reflect.get(native,method);return typeof value==='function'?value.bind(native):value;
  }});};
  if(key==='batch')return async(ops:any[])=>{if(pauseOrderId&&ops.some(op=>{const s=statements.get(op);return s&&/^INSERT INTO commerce_payment_events/.test(s.sql)&&s.args.includes(pauseOrderId)&&s.args.includes('sandbox_pay');})){pauseOrderId=null;entered=true;await new Promise<void>(resolve=>{release=resolve;setTimeout(resolve,20000);});}return target.batch(ops);};
  const value=Reflect.get(target,key);return typeof value==='function'?value.bind(target):value;
 }});
}
async function control(data:any,env:any){
 if('nowMs'in data){if(data.nowMs!==null&&(!Number.isSafeInteger(data.nowMs)||data.nowMs<=0||data.nowMs>=4000000000000))throw Error('invalid test clock');nowMs=data.nowMs;clockStarted=realClock();}
 if('pauseOrderId'in data){pauseOrderId=data.pauseOrderId;entered=false;}
 if(data.release){release?.();release=null;}
 if('failOrderId'in data){failOrderId=data.failOrderId;failCount=data.failCount??1;}
 const stmt=(sql:string,...args:any[])=>env.DB.prepare(sql).bind(...args),all=async(sql:string,...args:any[])=>(await stmt(sql,...args).all()).results;
 if(data.action==='fail-allocation'){
  await env.DB.prepare('DROP TRIGGER IF EXISTS member_quota_qa_failure').run();
  if(data.enabled)await env.DB.prepare('CREATE TRIGGER member_quota_qa_failure BEFORE INSERT ON membership_ai_allocations BEGIN SELECT member_quota_nonexistent_function(); END').run();
 }
 if(data.action==='expire-job')await stmt("UPDATE ai_gateway_jobs SET lease_until=0 WHERE id=? AND owner=? AND status IN ('queued','running')",data.jobId,data.owner).run();
 const value:any={isolated:true,externalProviderTested:false,syntheticDataOnly:true,clockOverride:nowMs,clockAdvancesWithRealElapsed:true,entered,callbackFailuresRemaining:failCount,barrierPosition:'immediately-before-real-d1-payment-batch'};
 if(['snapshot','migration'].includes(data.action)){
  const owner=data.owner||'quota_migration_canary';
  Object.assign(value,{wallets:await all('SELECT * FROM ai_gateway_wallets WHERE owner=?',owner),jobs:await all('SELECT id,request_id,status,reserve_credits,charged_credits,quota_source,quota_period_id AS period_id FROM ai_gateway_jobs WHERE owner=? ORDER BY id',owner),legacyEvents:await all('SELECT * FROM ai_gateway_quota_events WHERE owner=? ORDER BY id',owner),grants:await all('SELECT * FROM ai_gateway_grants WHERE owner=? ORDER BY id',owner),periods:await all('SELECT * FROM membership_ai_periods WHERE owner=? ORDER BY cycle_start,id',owner),allocations:await all('SELECT * FROM membership_ai_allocations WHERE owner=? ORDER BY job_id',owner),events:await all('SELECT * FROM membership_ai_events WHERE owner=? ORDER BY created,id',owner)});
 }
 return value;
}
export default {async fetch(request:Request,env:any,ctx:any){
 fixtureEndpoint=env.MEMBER_QUOTA_FIXTURE_ENDPOINT;
 const url=new URL(request.url);await init(env);
 if(url.pathname==='/__member-quota-test/control'){
  if(request.headers.get('X-Member-Quota-Test')!==env.MEMBER_QUOTA_TEST_TOKEN)return Response.json({error:'test token required'},{status:403});
  return Response.json(await control(await request.json(),env));
 }
 if(url.pathname.startsWith('/api/'))return handleAPI(request,{...env,DB:controlledDB(env.DB)},ctx);
 const html=url.pathname==='/experience'?experience:url.pathname==='/admin'?admin:['/','/app'].includes(url.pathname)?review:null;
 if(html)return new Response(html,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 return env.ASSETS.fetch(request);
}};
