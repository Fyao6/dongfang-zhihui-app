// QA-only entry: real API and generated pages, fresh local-only D1/R2.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
let initialization:Promise<any>|null=null;
globalThis.fetch=(async()=>{throw Error('Video QA does not permit external provider calls');}) as typeof fetch;
async function init(env:any){
 if(!initialization)initialization=(async()=>{const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));})();
 await initialization;
}
export default {async fetch(request:Request,env:any){
 const u=new URL(request.url);
 if(u.pathname==='/__video-test/status')return request.headers.get('X-Video-Test')===env.VIDEO_TEST_TOKEN?Response.json({isolated:true,formalIntroductionProduced:false,externalCallsAllowed:false}):new Response('test token required',{status:403});
 if(u.pathname.startsWith('/api/')){await init(env);return handleAPI(request,env);}
 if(['/','/app','/experience'].includes(u.pathname))return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(u.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 return new Response('isolated QA route not found',{status:404});
}};
