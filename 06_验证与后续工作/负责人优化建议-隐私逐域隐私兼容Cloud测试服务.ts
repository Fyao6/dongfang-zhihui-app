// QA-only Worker. Uses actual API modules and generated APP; no production entry is changed.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';

const calls:any[]=[];
globalThis.fetch=(async(input:any,options:any={})=>{
 const url=typeof input==='string'?input:input.url;
 if(new URL(url).hostname!=='privacy-fixture.invalid')throw Error('QA blocks all external provider calls');
 const raw=options.body??(input instanceof Request?await input.text():'{}');
 calls.push({url,payload:JSON.parse(raw)});
 return Response.json({output:[{type:'message',content:[{type:'output_text',text:'PRIVACY_LOCAL_MOCK_RESPONSE'}]}]});
}) as typeof fetch;
let initialization:Promise<any>|null=null;
async function init(env:any){
 if(!initialization)initialization=(async()=>{
  const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));
  await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));
 })();
 await initialization;
}
export default {async fetch(request:Request,env:any,context:any){
 const url=new URL(request.url);
 if(url.pathname==='/__privacy-test/mock')return request.headers.get('X-Privacy-Test')===env.PRIVACY_TEST_TOKEN?Response.json({isolated:true,kind:'local-process-mock',externalProviderTested:false,calls}):new Response('test token required',{status:403});
 if(url.pathname.startsWith('/api/')){await init(env);return handleAPI(request,env,context);}
 if(['/','/app','/experience'].includes(url.pathname))return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(url.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(url.pathname.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);
 return new Response('QA route not found',{status:404});
}};
