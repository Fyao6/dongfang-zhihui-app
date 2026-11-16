// Fresh local D1/R2 only. Actual integrated API/pages; token-only synthetic fixture tools.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
import fixture from './负责人优化建议-只读对账合成夹具.json';
let initialization:Promise<any>|null=null,actors:Record<string,string>={},baselineTriggers:any[]|null=null;
const financial=(name:string)=>/^(commerce_|membership_|commission_)/.test(name);
globalThis.fetch=(async()=>{throw Error('Read-only reconciliation QA forbids all external calls');}) as typeof fetch;
async function init(env:any){if(!initialization)initialization=(async()=>{const sql=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));await env.DB.batch(sql.map((s:string)=>env.DB.prepare(s)));})();await initialization;}
const identityFields=new Set(['owner','beneficiary','actor','approver','creator','user_id','owner_id','userId','ownerId','accountId','authorId','createdBy','approvedBy']);function rewrite(v:any,field=''):any{if(Array.isArray(v))return v.map(x=>rewrite(x,field));if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,rewrite(x,k)]));if(typeof v==='string'){if(identityFields.has(field)&&actors[v])return actors[v];try{const x=JSON.parse(v);if(x&&typeof x==='object')return JSON.stringify(rewrite(x));}catch{}}return v;}
export default {async fetch(request:Request,env:any){const u=new URL(request.url);
 if(u.pathname.startsWith('/__reconciliation-test/')){
  if(request.headers.get('X-Reconciliation-Test')!==env.RECONCILIATION_TEST_TOKEN)return new Response('QA token required',{status:403});
  try{
   if(u.pathname.endsWith('/hash')&&request.method==='GET'){const tables=(await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").all()).results.filter((r:any)=>financial(r.name));const rows=await env.DB.batch(tables.map((t:any)=>env.DB.prepare('SELECT * FROM '+t.name)));const value:any={};tables.forEach((t:any,i:number)=>{value[t.name]=rows[i].results.map((r:any)=>JSON.stringify(Object.fromEntries(Object.entries(r).sort(([a],[b])=>a.localeCompare(b))))).sort();});const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)));return Response.json({isolated:true,sha256:Array.from(new Uint8Array(digest)).map(x=>x.toString(16).padStart(2,'0')).join(''),tableCount:tables.length,actualPaid:false});}
   if(request.method!=='POST')return new Response('QA method',{status:405});const d:any=await request.json(),f:any=fixture;
   if(u.pathname.endsWith('/seed')){
    if(!f.syntheticOnly||!d.actors||!f.tables.users.rows.every(([id]:any[])=>d.actors[id])||!Object.values(d.actors).every(v=>typeof v==='string'&&/^[a-zA-Z0-9_-]{1,100}$/.test(v)))throw Error('Invalid synthetic actor mapping');actors=d.actors;
    const schemaRows=(await env.DB.prepare("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE type IN ('trigger','table')").all()).results,triggers=schemaRows.filter((r:any)=>r.type==='trigger'&&financial(r.tbl_name)),names=new Set(schemaRows.filter((r:any)=>r.type==='table'&&financial(r.name)).map((r:any)=>r.name));if(baselineTriggers===null)baselineTriggers=triggers;
    const ops=[env.DB.prepare('PRAGMA defer_foreign_keys=ON'),...triggers.map((t:any)=>env.DB.prepare('DROP TRIGGER '+t.name)),...Array.from(names).map(name=>env.DB.prepare('DELETE FROM '+name))];
    for(const [name,t] of Object.entries(f.tables) as [string,any][]){if(!financial(name))continue;if(!names.has(name))throw Error('Financial schema not integrated: '+name);for(const row of t.rows)ops.push(env.DB.prepare('INSERT INTO '+name+'('+t.columns.join(',')+') VALUES('+t.columns.map(()=>'?').join(',')+')').bind(...row.map((v:any,i:number)=>rewrite(v,t.columns[i]))));}
    for(const [id,role] of f.tables.users.rows)ops.push(env.DB.prepare('UPDATE users SET role=? WHERE id=?').bind(role,actors[id]));for(const [key,value] of f.tables.settings?.rows||[])if(key==='membership_lifecycle')ops.push(env.DB.prepare('INSERT OR REPLACE INTO settings VALUES(?,?)').bind(key,value));for(const t of baselineTriggers||[])ops.push(env.DB.prepare(t.sql));await env.DB.batch(ops);return Response.json({isolated:true,syntheticOnly:true,actualPaid:false});
   }
   if(u.pathname.endsWith('/damage')){if(!Number.isInteger(d.case)||d.case<0||d.case>=f.cases.length||!f.cases[d.case].sql)throw Error('Invalid fixture case');const c=f.cases[d.case];let sql=c.sql;for(const [source,target] of Object.entries(actors))sql=sql.replaceAll("'"+source+"'","'"+target+"'");await env.DB.prepare(sql).bind(...c.params.map((v:any)=>typeof v==='string'?actors[v]||v:v)).run();return Response.json({isolated:true,case:d.case,actualPaid:false});}
   if(u.pathname.endsWith('/missing')){if(d.table!=='commission_payments')throw Error('Invalid missing source');await env.DB.batch([env.DB.prepare('ALTER TABLE commission_payments RENAME TO qa_held_commission_payments'),env.DB.prepare('CREATE VIEW commission_payments AS SELECT * FROM qa_held_commission_payments')]);return Response.json({isolated:true});}
   if(u.pathname.endsWith('/truncate')){for(let start=0;start<5001;start+=80)await env.DB.batch(Array.from({length:Math.min(80,5001-start)},(_,n)=>env.DB.prepare('INSERT INTO commission_facts VALUES(?,?,?,?)').bind('limit-http-'+(start+n),'{}',0,'TEST')));return Response.json({isolated:true});}
   return new Response('QA route',{status:404});
  }catch(e:any){return Response.json({error:e.message},{status:400});}
 }
 if(u.pathname.startsWith('/api/')){await init(env);return handleAPI(request,env);}
 if(['/','/app','/experience'].includes(u.pathname))return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(u.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(u.pathname.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);
 return new Response('isolated read-only reconciliation QA route not found',{status:404});
}};
