// Local PAY08 QA wrapper. The real API is unchanged; fault controls exist only here.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import review from '../04_研发源码/app/cloud/generated/review.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
let initialization:Promise<any>|null=null;
let gate='enabled';
globalThis.fetch=(async()=>{throw Error('PAY08 QA blocks external HTTP');}) as typeof fetch;
async function init(env:any){
 if(!initialization)initialization=(async()=>{
  const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));
  await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));
 })();
 await initialization;
}
async function control(d:any,env:any){
 const stmt=(sql:string,...args:any[])=>env.DB.prepare(sql).bind(...args);
 const all=async(sql:string,...args:any[])=>(await stmt(sql,...args).all()).results;
 if(d.action==='snapshot')return {
  order:await stmt('SELECT id,payment_status,status,total_minor,currency FROM commerce_orders WHERE id=?',d.orderId||'').first(),
  inbox:await stmt('SELECT * FROM payment_callback_inbox WHERE id=?',d.receiptId||'').first(),
  ledger:await all('SELECT id,kind,amount_minor,status FROM commerce_payment_events WHERE order_id=? ORDER BY created,id',d.orderId||''),
  entitlements:await all('SELECT item_id,remaining,status FROM commerce_entitlements WHERE order_id=?',d.orderId||''),
  inventory:await all('SELECT s.id,s.stock,s.reserved,r.state FROM commerce_reservations r JOIN commerce_skus s ON s.id=r.sku_id WHERE r.order_id=? ORDER BY s.id',d.orderId||''),
  inboxCount:(await stmt('SELECT count(*) n FROM payment_callback_inbox').first()).n,
  transactionsCount:(await stmt('SELECT count(*) n FROM payment_callback_transactions').first()).n,
 };
 if(d.action==='gate'){gate=d.mode;return {changed:true};}
 if(['fail-apply-on','fail-apply-off'].includes(d.action)){
  await env.DB.batch([
   stmt('CREATE TABLE IF NOT EXISTS callback_qa_faults(order_id TEXT PRIMARY KEY)'),
   stmt('DELETE FROM callback_qa_faults'),
   ...(d.action==='fail-apply-on'?[stmt('INSERT INTO callback_qa_faults VALUES(?)',d.orderId)]:[]),
   stmt('DROP TRIGGER IF EXISTS callback_qa_apply_fault'),
   ...(d.action==='fail-apply-on'?[stmt("CREATE TRIGGER callback_qa_apply_fault BEFORE INSERT ON commerce_payment_events WHEN NEW.kind='sandbox_pay' AND EXISTS(SELECT 1 FROM callback_qa_faults WHERE order_id=NEW.order_id) BEGIN SELECT pay08_fixture_transient_failure(); END")]:[]),
  ]);return {changed:true};
 }
 if(['fail-receive-on','fail-receive-off'].includes(d.action)){
  await stmt('DROP TRIGGER IF EXISTS callback_qa_receive_fault').run();
  if(d.action==='fail-receive-on')await stmt('CREATE TRIGGER callback_qa_receive_fault BEFORE INSERT ON payment_callback_inbox BEGIN SELECT pay08_fixture_transient_failure(); END').run();
  return {changed:true};
 }
 const actions:any={
  'expire-order':['UPDATE commerce_orders SET reserved_until=0 WHERE id=?',[d.orderId]],
  'close-order':["UPDATE commerce_orders SET status='closed' WHERE id=?",[d.orderId]],
  'expired-lease':["UPDATE payment_callback_inbox SET status='processing',attempts=1,lease_token='abandoned-qa-lease',lease_until=?,next_attempt=0 WHERE id=?",[Date.now()-1000,d.receiptId]],
  'attempt-limit':["UPDATE payment_callback_inbox SET status='retry',attempts=4,lease_token='',lease_until=0,next_attempt=0 WHERE id=?",[d.receiptId]],
  due:['UPDATE payment_callback_inbox SET next_attempt=0 WHERE id=?',[d.receiptId]],
 };
 if(!actions[d.action])throw Error('Unsupported isolated QA action');
 await stmt(actions[d.action][0],...actions[d.action][1]).run();return {changed:true};
}
export default {async fetch(request:Request,env:any,ctx:any){
 const u=new URL(request.url);
 if(u.hostname!=='127.0.0.1'&&u.hostname!=='localhost')return new Response('Local QA only',{status:403});
 if(u.pathname==='/__callback-test/control'){
  if(request.method!=='POST'||!env.CALLBACK_TEST_TOKEN||request.headers.get('X-Callback-Test')!==env.CALLBACK_TEST_TOKEN)return new Response('QA control token required',{status:403});
  const raw=await request.text();if(raw.length>4096)return new Response('QA request too large',{status:413});
  try{return Response.json({isolated:true,...await control(JSON.parse(raw),env)});}catch{return Response.json({error:'Invalid isolated QA control'},{status:400});}
 }
 if(u.pathname.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);
 if(u.pathname.startsWith('/api/')){await init(env);return handleAPI(request,{...env,EW_PAYMENT_CALLBACK_SANDBOX_ENABLED:gate==='disabled'?'0':'1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF:gate==='invalid-ref'?'INVALID_REF':'EW_PAYMENT_CALLBACK_QA_SECRET'},ctx);}
 if(u.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(['/','/app'].includes(u.pathname))return new Response(review,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 if(u.pathname==='/experience')return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});
 return new Response('PAY08 isolated QA route not found',{status:404});
}};
