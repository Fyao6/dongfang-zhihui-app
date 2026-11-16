// Fresh QA-only local Worker; actual API plus current generated APP/admin. No random/result injection.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
let initialization:Promise<any>|null=null;
globalThis.fetch=(async()=>{throw Error('Card QA blocks all external HTTP');}) as typeof fetch;
async function init(env:any){if(!initialization)initialization=(async()=>{const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));})();await initialization;}
export default {async fetch(request:Request,env:any,context:any){const p=new URL(request.url).pathname;if(p.startsWith('/api/')){await init(env);return (handleAPI as any)(request,env,context);}if(['/','/app','/experience'].includes(p))return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});if(p==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});if(p.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);return new Response('QA route not found',{status:404});}};
