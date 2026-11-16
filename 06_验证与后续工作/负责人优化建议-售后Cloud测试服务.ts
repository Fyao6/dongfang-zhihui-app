// Prepared AfterSales isolated wrapper. Actual API/schema/build; no fake AI, payment or chart response.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
let initialization:Promise<any>|null=null;
globalThis.fetch=(async()=>{throw Error('AfterSales QA blocks external provider calls');}) as typeof fetch;
async function init(env:any){
 if(!initialization)initialization=(async()=>{
  const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));
  await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));
 })();
 await initialization;
}
export default {async fetch(request:Request,env:any,ctx:any){
 const u=new URL(request.url);
 if(u.pathname.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);
 if(u.pathname.startsWith('/api/')){await init(env);return handleAPI(request,env,ctx);}
 if(u.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(['/','/app','/experience'].includes(u.pathname))return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 return new Response('AfterSales isolated QA route not found',{status:404});
}};

