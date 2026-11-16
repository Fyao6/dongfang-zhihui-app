// QA Worker only. Actual integrated API/pages, fresh local D1/R2, no external calls.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
let initialization:Promise<any>|null=null;
const qaErrors:string[]=[];const originalConsoleError=console.error;console.error=(...args:any[])=>{if(args[0]==='api_error')qaErrors.push(args.map(String).join(' '));originalConsoleError(...args);};
globalThis.fetch=(async()=>{throw Error('Commission QA forbids all external calls and real payment providers');}) as typeof fetch;
async function init(env:any){if(!initialization)initialization=(async()=>{const sql=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));await env.DB.batch(sql.map((s:string)=>env.DB.prepare(s)));})();await initialization;}
export default {async fetch(request:Request,env:any){const u=new URL(request.url);
 if(u.pathname==='/__commission-test/snapshot'){
  if(request.headers.get('X-Commission-Test')!==env.COMMISSION_TEST_TOKEN)return new Response('QA token required',{status:403});
  const oid=u.searchParams.get('orderId')||'';if(!/^[a-f0-9-]{36}$/.test(oid))return new Response('invalid QA order',{status:400});
  const rows=await env.DB.prepare('SELECT item_id,data FROM commission_snapshots WHERE order_id=?').bind(oid).all();return Response.json({isolated:true,rows:rows.results.map((r:any)=>({itemId:r.item_id,snapshot:JSON.parse(r.data)}))});
 }
 if(u.pathname==='/__commission-test/fault'){
  if(request.method!=='POST'||request.headers.get('X-Commission-Test')!==env.COMMISSION_TEST_TOKEN)return new Response('QA token required',{status:403});
  const d:any=await request.json();if(!/^[a-f0-9-]{36}$/.test(d.orderId||'')||!['ledger','adjustment'].includes(d.stage)||typeof d.enabled!=='boolean')return new Response('invalid QA fault fixture',{status:400});
  if(!await env.DB.prepare('SELECT 1 FROM commerce_orders WHERE id=?').bind(d.orderId).first())return new Response('new QA order required',{status:404});
  await env.DB.prepare('DROP TRIGGER IF EXISTS commission_qa_fault').run();if(d.enabled){const table=d.stage==='ledger'?'commission_ledger':'commission_adjustments',condition=d.stage==='ledger'?"NEW.order_id='"+d.orderId+"'":"EXISTS(SELECT 1 FROM commission_ledger WHERE id=NEW.ledger_id AND order_id='"+d.orderId+"')";await env.DB.prepare("CREATE TRIGGER commission_qa_fault BEFORE INSERT ON "+table+" WHEN "+condition+" BEGIN SELECT RAISE(ABORT,'commission_qa_fault'); END").run();}
  return Response.json({isolated:true,enabled:d.enabled,stage:d.stage,actualPaid:false});
 }
 if(u.pathname==='/__commission-test/status')return request.headers.get('X-Commission-Test')===env.COMMISSION_TEST_TOKEN?Response.json({isolated:true,sandboxOnly:true,actualPaid:false,externalCallsAllowed:false,apiErrors:qaErrors.slice(-20)}):new Response('test token required',{status:403});
 if(u.pathname.startsWith('/api/')){await init(env);return handleAPI(request,env);}
 if(['/','/app','/experience'].includes(u.pathname))return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(u.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(u.pathname.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);
 return new Response('isolated commission QA route not found',{status:404});
}};
