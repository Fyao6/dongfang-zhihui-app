// QA-only wrapper around actual handleAPI. Fresh local D1/R2; no successful provider responses are fabricated.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import {MembershipLifecycle} from '../04_研发源码/app/cloud/lib/membership-lifecycle';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
let initialization:Promise<any>|null=null,nowMs:number|null=null,pauseOrderId:string|null=null,entered=false,release:(()=>void)|null=null,failOrderId:string|null=null,failCount=0;
const realClock=MembershipLifecycle.prototype.clock;
MembershipLifecycle.prototype.clock=function(){return nowMs??realClock.call(this);};
const originalCallback=MembershipLifecycle.prototype.onCommercePayment;
MembershipLifecycle.prototype.onCommercePayment=async function(orderId:string){if(failOrderId===orderId&&failCount>0){--failCount;throw Error('QA_ONLY_MEMBERSHIP_CALLBACK_INTERRUPTED');}return originalCallback.call(this,orderId);};
globalThis.fetch=(async()=>{throw Error('Membership QA blocks external provider calls');}) as typeof fetch;
async function init(env:any){if(!initialization)initialization=(async()=>{const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));})();await initialization;}
function controlledDB(db:any){
 const statements=new WeakMap<object,{sql:string,args:any[]}>();
 return new Proxy(db,{get(target,key){
  if(key==='prepare')return (sql:string)=>{const stmt=target.prepare(sql);statements.set(stmt,{sql,args:[]});return new Proxy(stmt,{get(native,method){if(method==='bind')return (...args:any[])=>{const bound=native.bind(...args);statements.set(bound,{sql,args});return bound;};const v=Reflect.get(native,method);return typeof v==='function'?v.bind(native):v;}});};
  if(key==='batch')return async(ops:any[])=>{if(pauseOrderId&&ops.some(op=>{const s=statements.get(op);return s&&/^INSERT INTO commerce_payment_events/.test(s.sql)&&s.args.includes(pauseOrderId)&&s.args.includes('sandbox_pay');})){pauseOrderId=null;entered=true;await new Promise<void>(resolve=>{release=resolve;setTimeout(resolve,20000);});}return target.batch(ops);};
  const value=Reflect.get(target,key);return typeof value==='function'?value.bind(target):value;
 }});
}
export default {async fetch(request:Request,env:any,ctx:any){
 const u=new URL(request.url);
 if(u.pathname==='/__membership-test/control'){
  if(request.headers.get('X-Membership-Test')!==env.MEMBERSHIP_TEST_TOKEN)return new Response('test token required',{status:403});
  if(request.method==='POST'){const d:any=await request.json();if('nowMs'in d){if(d.nowMs!==null&&(!Number.isSafeInteger(d.nowMs)||d.nowMs<=0||d.nowMs>=4000000000000))return new Response('invalid test clock',{status:400});nowMs=d.nowMs;}if('pauseOrderId'in d){pauseOrderId=d.pauseOrderId;entered=false;}if(d.release){release?.();release=null;}if('failOrderId'in d){failOrderId=d.failOrderId;failCount=d.failCount??1;}}
  return Response.json({isolated:true,externalProviderTested:false,syntheticDataOnly:true,clockOverride:nowMs,entered,callbackFailuresRemaining:failCount,barrierPosition:'immediately-before-real-d1-payment-batch'});
 }
 if(u.pathname.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);
 if(u.pathname.startsWith('/api/')){await init(env);return handleAPI(request,{...env,DB:controlledDB(env.DB)},ctx);}
 if(['/','/app','/experience'].includes(u.pathname))return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(u.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 return new Response('isolated QA route not found',{status:404});
}};

