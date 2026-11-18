// PAY09 local query fixture. This is not an Apple/Google/Stripe/PayPal adapter.
import {paymentCallbacksSandboxReady,prepareVerifiedEvent,verifiedEventReceipt,processRecoveryReceipt} from './payment-callbacks';
import {lateEligible} from './payment-late';

const MAX_ATTEMPTS=5,LEASE_MS=30000,MAX_BYTES=8192;
const STATUSES=['pending','processing','retry','confirmed','unpaid','manual_review'];
const DDL=[
 `CREATE TABLE IF NOT EXISTS payment_recovery_jobs(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,order_id TEXT NOT NULL,status TEXT NOT NULL
 CHECK(status IN ('pending','processing','retry','confirmed','unpaid','manual_review')),
 attempts INTEGER NOT NULL DEFAULT 0,lease_token TEXT NOT NULL DEFAULT '',lease_until INTEGER NOT NULL DEFAULT 0,
 next_attempt INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '',receipt_id TEXT NOT NULL DEFAULT '',
 created INTEGER NOT NULL,updated INTEGER NOT NULL,query_binding TEXT NOT NULL DEFAULT '',UNIQUE(owner,order_id))`,
 'CREATE INDEX IF NOT EXISTS payment_recovery_queue ON payment_recovery_jobs(status,next_attempt,created,id)',
 `CREATE TABLE IF NOT EXISTS payment_recovery_requests(owner TEXT NOT NULL,request_id TEXT NOT NULL,
 order_id TEXT NOT NULL,job_id TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(owner,request_id))`,
 `CREATE TABLE IF NOT EXISTS payment_recovery_attempts(id TEXT PRIMARY KEY,job_id TEXT NOT NULL,attempt INTEGER NOT NULL,
 action TEXT NOT NULL,actor TEXT NOT NULL,result TEXT NOT NULL,error_code TEXT NOT NULL,created INTEGER NOT NULL)`,
 'CREATE INDEX IF NOT EXISTS payment_recovery_attempt_job ON payment_recovery_attempts(job_id,created,id)',
];
const encoder=new TextEncoder();
const canonical=(value:any)=>JSON.stringify(Object.fromEntries(Object.keys(value).sort().map(k=>[k,value[k]])));
const hex=(bytes:ArrayBuffer)=>Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');
const digest=async(value:string)=>hex(await crypto.subtle.digest('SHA-256',encoder.encode(value)));
const errors=(value:any)=>[value?.message,value?.cause?.message,String(value||'')].filter(Boolean).join(' ');
class QueryFailure extends Error {constructor(public code:string,public transient:boolean){super(code);}}

export async function initPaymentRecovery(a:any){
 if(!await a.one("SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_recovery_attempts'"))
  await a.db.batch(DDL.map(sql=>a.stmt(sql)));
 const columns=await a.all('PRAGMA table_info(payment_recovery_jobs)');
 if(!columns.some((row:any)=>row.name==='query_binding')){
  try{await a.run("ALTER TABLE payment_recovery_jobs ADD COLUMN query_binding TEXT NOT NULL DEFAULT ''");}
  catch(error){if(!(await a.all('PRAGMA table_info(payment_recovery_jobs)')).some((r:any)=>r.name==='query_binding'))throw error;}
 }
}

function configuration(a:any){
 const endpoint=a.env.EW_PAYMENT_QUERY_SANDBOX_ENDPOINT,ref=a.env.EW_PAYMENT_QUERY_SANDBOX_SECRET_REF;
 const match=typeof endpoint==='string'&&/^http:\/\/127\.0\.0\.1:([1-9][0-9]{0,4})\/pay09-fixture\/query$/.exec(endpoint);
 const valid=!!match&&Number(match[1])<=65535&&typeof ref==='string'&&/^EW_PAYMENT_QUERY_[A-Z0-9_]{1,80}$/.test(ref);
 const secret=valid?a.env[ref]:undefined;
 return a.env.EW_PAYMENT_QUERY_SANDBOX_ENABLED==='1'&&typeof secret==='string'&&[...secret].length>=32&&paymentCallbacksSandboxReady(a)
  ?{endpoint,secret}:null;
}

async function configurationBinding(a:any){
 const config=configuration(a);if(!config)return '';
 return digest(canonical({enabled:'1',endpoint:config.endpoint,secretRef:a.env.EW_PAYMENT_QUERY_SANDBOX_SECRET_REF,
  secretHash:await digest(config.secret)}));
}
export async function currentPaymentQueryBinding(a:any){return configurationBinding(a);}

// Server-only check used by both the scoped recovery consumer and PAY08's administrative consumer.
export async function queryReceiptBinding(a:any,receiptId:string){
 const job=await a.one(`SELECT j.id,j.owner,j.order_id,j.query_binding FROM payment_recovery_jobs j
  JOIN payment_callback_inbox i ON i.id=j.receipt_id JOIN payment_callback_transactions t ON t.transaction_id=i.transaction_id
  WHERE t.receipt_id=? AND i.order_id=j.order_id ORDER BY j.created,j.id LIMIT 1`,receiptId);
 const current=await configurationBinding(a);
 return {valid:!!job&&!!current&&job.query_binding===current,jobId:job?.id||'',owner:job?.owner||'',
  orderId:job?.order_id||'',binding:job?.query_binding||''};
}

class PaymentRecovery {
 constructor(private a:any,private fail:(status:number,message:string)=>never){}
 ready(){return configuration(this.a)!==null;}
 summary(row:any){return row?{id:row.id,orderId:row.order_id,status:row.status,attempts:row.attempts,
  receiptId:row.receipt_id,lastError:row.last_error,nextAttempt:row.next_attempt,leaseUntil:row.lease_until,created:row.created,updated:row.updated}:null;}
 orderSummary(row:any){return {id:row.id,paymentStatus:row.payment_status,fulfillmentStatus:row.fulfillment_status,
  totalMinor:row.total_minor,currency:row.currency,environment:'sandbox'};}
 async order(id:string,owner?:string){
  const row=await this.a.one("SELECT * FROM commerce_orders WHERE id=? AND environment='sandbox'"+(owner===undefined?'':' AND owner=?'),id,...(owner===undefined?[]:[owner]));
  if(!row)return this.fail(404,'找不到此订单。');return row;
 }
 async job(id:string){const row=await this.a.one('SELECT * FROM payment_recovery_jobs WHERE id=?',id);if(!row)return this.fail(404,'找不到此支付恢复任务。');return row;}
 async view(order:any){const row=await this.a.one('SELECT * FROM payment_recovery_jobs WHERE owner=? AND order_id=?',order.owner,order.id);
  return {job:this.summary(row),order:this.orderSummary(order),queryReady:this.ready(),productionEnabled:false};}
 async current(row:any,token:string){return !!await this.a.one(`SELECT 1 FROM payment_recovery_jobs j JOIN commerce_orders o ON o.id=j.order_id
  WHERE j.id=? AND j.lease_token=? AND j.status='processing' AND j.lease_until>? AND o.owner=j.owner
  AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=j.owner AND l.status='closed')`,row.id,token,Date.now());}

 localPaidSQL(){return `EXISTS(SELECT 1 FROM commerce_orders o JOIN commerce_payment_events p ON p.order_id=o.id
  WHERE o.id=payment_recovery_jobs.order_id AND o.owner=payment_recovery_jobs.owner AND o.environment='sandbox'
  AND o.payment_status='paid' AND p.owner=o.owner AND p.environment='sandbox' AND p.kind='sandbox_pay' AND p.status='applied')`;}
 async finish(row:any,token:string,status:string,code:string,actor:string,protectLatestOrder=false){
  const stamp=Date.now(),due=status==='retry'?stamp+1000*2**(row.attempts-1):0;
  const paid=this.localPaidSQL(),terminal=`EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=payment_recovery_jobs.order_id
   AND NOT ((o.payment_status='unpaid' AND o.status='awaiting_payment') OR (o.payment_status='expired' AND o.status='closed')))`;
  const confirmed=status==='confirmed'?` AND (${paid} OR EXISTS(SELECT 1 FROM payment_callback_inbox i WHERE i.id=payment_recovery_jobs.receipt_id
   AND i.order_id=payment_recovery_jobs.order_id AND i.status='applied' AND i.last_error!='late_refund_pending'))`:'';
  const assignments=protectLatestOrder?`status=CASE WHEN ${paid} THEN 'confirmed' WHEN ${terminal} THEN 'manual_review' ELSE ? END,
   last_error=CASE WHEN ${paid} THEN '' WHEN ${terminal} THEN 'order_not_payable' ELSE ? END,
   next_attempt=CASE WHEN ${paid} OR ${terminal} THEN 0 ELSE ? END`:'status=?,last_error=?,next_attempt=?';
  await this.a.db.batch([
   this.a.stmt(`UPDATE payment_recovery_jobs SET ${assignments},lease_token='',lease_until=0,updated=?
    WHERE id=? AND status='processing' AND lease_token=? AND lease_until>? AND EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=payment_recovery_jobs.order_id
    AND o.owner=payment_recovery_jobs.owner) AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=payment_recovery_jobs.owner AND l.status='closed')`+confirmed,
    status,code,due,stamp,row.id,token,stamp),
   this.a.stmt(`INSERT INTO payment_recovery_attempts SELECT ?,id,attempts,'complete',?,status,last_error,? FROM payment_recovery_jobs WHERE id=? AND changes()=1`,
    crypto.randomUUID(),actor,stamp,row.id),
  ]);
 }

 async query(row:any,order:any){
  const config=configuration(this.a);if(!config)throw new QueryFailure('adapter_disabled',true);
  if(!row.query_binding||await configurationBinding(this.a)!==row.query_binding)throw new QueryFailure('adapter_disabled',true);
  const raw=canonical({queryId:row.id,orderId:order.id,amountMinor:order.total_minor,currency:order.currency});
  const timestamp=String(Math.floor(Date.now()/1000));
  const key=await crypto.subtle.importKey('raw',encoder.encode(config.secret),{name:'HMAC',hash:'SHA-256'},false,['sign','verify']);
  const signature=hex(await crypto.subtle.sign('HMAC',key,encoder.encode(timestamp+'.'+raw)));
  let response:Response;
  try{response=await fetch(config.endpoint,{method:'POST',redirect:'manual',signal:AbortSignal.timeout(8000),
   headers:{'Content-Type':'application/json','X-EW-Query-Timestamp':timestamp,'X-EW-Query-Signature':signature},body:raw});}
  catch(error:any){throw new QueryFailure(error?.name==='TimeoutError'||error?.name==='AbortError'?'query_timeout':/redirect/i.test(errors(error))?'query_http_error':'transport_unavailable',true);}
  if(response.status!==200){await response.body?.cancel();throw new QueryFailure('query_http_error',true);}
  const declared=response.headers.get('content-length');
  if(declared!==null&&(!/^[0-9]{1,6}$/.test(declared)||Number(declared)>MAX_BYTES)){await response.body?.cancel();throw new QueryFailure('invalid_query_response',false);}
  const reader=response.body?.getReader();if(!reader)throw new QueryFailure('invalid_query_response',false);
  const chunks:Uint8Array[]=[];let size=0;
  try{while(true){const next=await reader.read();if(next.done)break;size+=next.value.length;
   if(size>MAX_BYTES){await reader.cancel();throw new QueryFailure('invalid_query_response',false);}chunks.push(next.value);}}
  catch(error:any){if(error instanceof QueryFailure)throw error;throw new QueryFailure(error?.name==='TimeoutError'||error?.name==='AbortError'?'query_timeout':'transport_unavailable',true);}
  finally{reader.releaseLock();}
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
  let body:string;try{body=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{throw new QueryFailure('invalid_query_response',false);}
  const stamp=response.headers.get('X-EW-Query-Timestamp')||'',sig=response.headers.get('X-EW-Query-Signature')||'';
  if(!/^\d{1,12}$/.test(stamp)||Math.abs(Math.floor(Date.now()/1000)-Number(stamp))>300||!/^[a-fA-F0-9]{64}$/.test(sig)||
   !await crypto.subtle.verify('HMAC',key,Uint8Array.from(sig.match(/../g)!,v=>parseInt(v,16)),encoder.encode(stamp+'.'+body)))
   throw new QueryFailure('invalid_query_signature',false);
  let result:any;try{result=JSON.parse(body);}catch{throw new QueryFailure('invalid_query_response',false);}
  const tokens=[...body.matchAll(/"(?:\\.|[^"\\])*"/g)].filter(m=>/^\s*:/.test(body.slice(m.index!+m[0].length))),keys=tokens.map(m=>JSON.parse(m[0]));
  const amountToken=tokens.find(m=>JSON.parse(m[0])==='amountMinor');
  if(new Set(keys).size!==keys.length||!amountToken||!/^\s*:\s*-?(?:0|[1-9]\d*)(?=\s*[,}])/.test(body.slice(amountToken.index!+amountToken[0].length))||
   !result||typeof result!=='object'||Array.isArray(result)||Object.keys(result).sort().join(',')!=='amountMinor,currency,orderId,queryId,state,transactionId'||
   !['paid','unpaid','pending','not_found','failed'].includes(result.state)||typeof result.transactionId!=='string'||
   (result.state==='paid'?!/^[A-Za-z0-9:_-]{1,100}$/.test(result.transactionId):result.transactionId!=='')||
   !Number.isSafeInteger(result.amountMinor)||result.amountMinor<0||result.amountMinor>1000000000||typeof result.currency!=='string'||!/^[A-Z]{3}$/.test(result.currency))
   throw new QueryFailure('invalid_query_response',false);
  if(result.queryId!==row.id||result.orderId!==order.id||result.amountMinor!==order.total_minor||result.currency!==order.currency)
   throw new QueryFailure('query_mismatch',false);
  if(await configurationBinding(this.a)!==row.query_binding)throw new QueryFailure('adapter_disabled',true);
  return result;
 }

 async persistPaid(row:any,token:string,result:any,actor:string){
  if(!row.query_binding||await configurationBinding(this.a)!==row.query_binding)throw new QueryFailure('adapter_disabled',true);
  const data={eventId:'query:'+row.id,transactionId:result.transactionId,orderId:row.order_id,type:'payment.succeeded',amountMinor:result.amountMinor,currency:result.currency};
  const event=await prepareVerifiedEvent(this.a,data),stamp=Date.now(),guardId=crypto.randomUUID();
  await this.a.db.batch([
   this.a.stmt(`INSERT INTO payment_callback_guards VALUES(?,CASE WHEN EXISTS(SELECT 1 FROM payment_recovery_jobs j JOIN commerce_orders o ON o.id=j.order_id
    WHERE j.id=? AND j.owner=? AND j.order_id=? AND j.status='processing' AND j.lease_token=? AND j.lease_until>? AND j.query_binding=?
    AND o.owner=j.owner AND o.environment='sandbox' AND o.total_minor=? AND o.currency=?
    AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=j.owner AND l.status='closed')) THEN 1 ELSE 0 END)`,
    guardId,row.id,row.owner,row.order_id,token,stamp,row.query_binding,result.amountMinor,result.currency),
   ...event.statements,
   this.a.stmt(`UPDATE payment_recovery_jobs SET receipt_id=coalesce((SELECT i.id FROM payment_callback_inbox i JOIN payment_callback_transactions t
    ON t.transaction_id=i.transaction_id WHERE i.event_id=? AND i.fingerprint=? AND t.fingerprint=?),''),updated=?
    WHERE id=? AND lease_token=? AND status='processing'`,event.eventId,event.fingerprint,event.fingerprint,stamp,row.id,token),
   this.a.stmt(`INSERT INTO payment_recovery_attempts SELECT ?,id,attempts,'query',?,'paid','',? FROM payment_recovery_jobs WHERE id=? AND lease_token=? AND receipt_id!=''`,
    crypto.randomUUID(),actor,stamp,row.id,token),
   this.a.stmt('DELETE FROM payment_callback_guards WHERE id=?',guardId),
  ]);
  const receipt=await verifiedEventReceipt(this.a,event);
  if(receipt.conflict){await this.a.run('INSERT INTO audits VALUES(?,?,?,?,?,?)',crypto.randomUUID(),actor,'payment_recovery.receipt_conflict',row.id,'query receipt conflict',Date.now());
   throw new QueryFailure('receipt_conflict',false);}
  return receipt.receiptId!;
 }

 async run(id:string,actor:string,fence?:()=>Promise<any[]>){
  const claimBatch=async(ops:any[])=>{const prefix=fence?await fence():[];return (await this.a.db.batch([...prefix,...ops])).slice(prefix.length);};
  let row=await this.job(id);const stamp=Date.now();
  if(!['pending','retry','processing'].includes(row.status)||row.next_attempt>stamp||(row.status==='processing'&&row.lease_until>stamp))return row;
  const localOrder=await this.order(row.order_id,row.owner);
  const ownerClosed=!!await this.a.one("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'",row.owner);
  const localPaid=!!await this.a.one('SELECT 1 FROM payment_recovery_jobs WHERE id=? AND '+this.localPaidSQL(),id);
  const terminal=!row.receipt_id&&!(localOrder.payment_status==='unpaid'&&localOrder.status==='awaiting_payment')&&!lateEligible(localOrder,stamp);
  if(ownerClosed||terminal){
   const status=localPaid&&!ownerClosed?'confirmed':'manual_review';
   const code=ownerClosed?'account_closed':status==='confirmed'?'':localOrder.reserved_until<=stamp?'order_expired':'order_not_payable';
   const terminalGuard=ownerClosed?"EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=payment_recovery_jobs.owner AND status='closed')":
    status==='confirmed'?this.localPaidSQL():`EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=payment_recovery_jobs.order_id
    AND NOT ((o.payment_status='unpaid' AND o.status='awaiting_payment') OR (o.payment_status='expired' AND o.status='closed')))`;
   await claimBatch([
    this.a.stmt(`UPDATE payment_recovery_jobs SET status=?,last_error=?,next_attempt=0,lease_token='',lease_until=0,updated=?
     WHERE id=? AND status=? AND attempts=? AND lease_token=? AND (status!='processing' OR lease_until<=?) AND `+terminalGuard,
     status,code,stamp,id,row.status,row.attempts,row.lease_token,stamp),
    this.a.stmt(`INSERT INTO payment_recovery_attempts SELECT ?,id,attempts,'complete',?,status,last_error,? FROM payment_recovery_jobs WHERE id=? AND changes()=1`,
     crypto.randomUUID(),actor,stamp,id),
   ]);return this.job(id);
  }
  if(row.attempts>=MAX_ATTEMPTS){await claimBatch([this.a.stmt(`UPDATE payment_recovery_jobs SET status='manual_review',last_error='retry_exhausted',lease_token='',lease_until=0,next_attempt=0,updated=?
   WHERE id=? AND attempts>=? AND ((status IN ('pending','retry') AND next_attempt<=?) OR (status='processing' AND lease_until<=?))`,stamp,id,MAX_ATTEMPTS,stamp,stamp)]);return this.job(id);}
  const token=crypto.randomUUID(),queryBinding=await configurationBinding(this.a);
  const claimed=await claimBatch([
   this.a.stmt(`UPDATE payment_recovery_jobs SET status='processing',attempts=attempts+1,lease_token=?,lease_until=?,next_attempt=0,last_error='',updated=?,
    query_binding=CASE WHEN receipt_id='' THEN ? ELSE query_binding END
    WHERE id=? AND attempts<? AND ((status IN ('pending','retry') AND next_attempt<=?) OR (status='processing' AND lease_until<=?))
    AND EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=payment_recovery_jobs.order_id AND o.owner=payment_recovery_jobs.owner)
    AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=payment_recovery_jobs.owner AND l.status='closed')`,token,stamp+LEASE_MS,stamp,queryBinding,id,MAX_ATTEMPTS,stamp,stamp),
   this.a.stmt(`INSERT INTO payment_recovery_attempts SELECT ?,id,attempts,'claim',?,'processing',?,? FROM payment_recovery_jobs WHERE id=? AND lease_token=?`,
    crypto.randomUUID(),actor,row.status==='processing'?'lease_expired':'',stamp,id,token),
   this.a.stmt('SELECT * FROM payment_recovery_jobs WHERE id=? AND lease_token=?',id,token),
  ]);
  row=claimed[2].results?.[0];if(!row)return this.job(id);
  try{
   const order=await this.order(row.order_id,row.owner);
   if(!row.receipt_id){
    if(!(order.payment_status==='unpaid'&&order.status==='awaiting_payment')&&!lateEligible(order))throw new QueryFailure('order_not_payable',false);
    const result=await this.query(row,order);
    if(!await this.current(row,token))return this.job(id);
    if(result.state==='unpaid'){await this.finish(row,token,'unpaid','query_unpaid',actor,true);return this.job(id);}
    if(result.state!=='paid')throw new QueryFailure('query_'+result.state,true);
    row.receipt_id=await this.persistPaid(row,token,result,actor);
   }
   if(!await this.current(row,token))return this.job(id);
   if(!row.query_binding||await configurationBinding(this.a)!==row.query_binding)throw new QueryFailure('adapter_disabled',true);
   const receipt=await processRecoveryReceipt(this.a,row.receipt_id,actor,{jobId:row.id,owner:row.owner,jobLease:token,receiptId:row.receipt_id,queryBinding:row.query_binding},this.fail);
   if(receipt.status==='applied'&&receipt.lastError==='late_refund_pending')await this.finish(row,token,'manual_review','late_refund_pending',actor);
   else if(receipt.status==='applied')await this.finish(row,token,'confirmed','',actor);
   else if(receipt.status==='manual_review')await this.finish(row,token,'manual_review',receipt.lastError||'receipt_conflict',actor);
   else await this.finish(row,token,row.attempts>=MAX_ATTEMPTS?'manual_review':'retry',receipt.lastError||'receipt_processing',actor);
  }catch(error){
   if(/account_actor_|account_settlement_/.test(errors(error)))throw error;
   if(!await this.current(row,token))return this.job(id);
   const reason=error instanceof QueryFailure?error:new QueryFailure(errors(error).includes('payment_query_binding_changed')?'adapter_disabled':'storage_unavailable',true);
   await this.finish(row,token,reason.transient&&row.attempts<MAX_ATTEMPTS?'retry':'manual_review',reason.code,actor,true);
  }
  return this.job(id);
 }

 async start(order:any,data:any,actor:string){
  if(!data||Object.keys(data).join(',')!=='requestId'||typeof data.requestId!=='string'||!/^[A-Za-z0-9:_-]{1,100}$/.test(data.requestId))
   return this.fail(400,'恢复请求仅接受有效请求编号。');
  if(!this.ready())return this.fail(503,'主动查单测试适配尚未配置；正式支付未启用。');
  const existing=await this.a.one('SELECT * FROM payment_recovery_requests WHERE owner=? AND request_id=?',actor,data.requestId);
  if(existing&&existing.order_id!==order.id)return this.fail(409,'该请求编号已用于其他订单。');
  const stamp=Date.now(),jobId=crypto.randomUUID();
  const writes=await this.a.db.batch([
   this.a.stmt(`INSERT OR IGNORE INTO payment_recovery_jobs(id,owner,order_id,status,created,updated)
    SELECT ?,?,?,'pending',?,? WHERE NOT EXISTS(SELECT 1 FROM payment_recovery_requests WHERE owner=? AND request_id=? AND order_id!=?)
    AND EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=? AND o.owner=? AND o.environment='sandbox')`,jobId,actor,order.id,stamp,stamp,actor,data.requestId,order.id,order.id,actor),
   this.a.stmt(`INSERT OR IGNORE INTO payment_recovery_requests SELECT ?,?,?,id,? FROM payment_recovery_jobs WHERE owner=? AND order_id=?`,
    actor,data.requestId,order.id,stamp,actor,order.id),
   this.a.stmt('SELECT * FROM payment_recovery_requests WHERE owner=? AND request_id=?',actor,data.requestId),
  ]);
  const request=writes[2].results?.[0];if(!request||request.order_id!==order.id)return this.fail(409,'该请求编号已用于其他订单。');
  if(writes[1].meta?.changes){await this.a.db.batch([
   this.a.stmt(`UPDATE payment_recovery_jobs SET status='pending',last_error='',next_attempt=0,updated=? WHERE id=? AND status='unpaid' AND attempts<?`,stamp,request.job_id,MAX_ATTEMPTS),
   this.a.stmt(`INSERT INTO payment_recovery_attempts SELECT ?,id,attempts,'request',?,status,'',? FROM payment_recovery_jobs WHERE id=?`,crypto.randomUUID(),actor,stamp,request.job_id),
  ]);}
  await this.run(request.job_id,actor);
  return this.view(await this.order(order.id,actor));
 }

 async retry(id:string,actor:string,data:any){
  if(Object.keys(data).length)return this.fail(400,'重试请求不接受额外字段。');
  const row=await this.job(id),stamp=Date.now();
  if(!['retry','unpaid','manual_review'].includes(row.status)||row.attempts>=MAX_ATTEMPTS||row.lease_until>stamp)return this.fail(409,'任务不可重试或已达到次数上限。');
  if(!await this.a.one("SELECT 1 FROM users u WHERE id=? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')",row.owner))return this.fail(409,'该账号已关闭，不能重试。');
  await this.a.db.batch([
   this.a.stmt(`UPDATE payment_recovery_jobs SET status='retry',last_error='',next_attempt=0,lease_token='',lease_until=0,updated=?
    WHERE id=? AND status IN ('retry','unpaid','manual_review') AND attempts<? AND lease_until<=?
    AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=payment_recovery_jobs.owner AND l.status='closed')`,stamp,id,MAX_ATTEMPTS,stamp),
   this.a.stmt(`INSERT INTO payment_recovery_attempts SELECT ?,id,attempts,'retry',?,'retry','',? FROM payment_recovery_jobs WHERE id=? AND status='retry' AND updated=?`,crypto.randomUUID(),actor,stamp,id,stamp),
  ]);
  return {job:this.summary(await this.job(id)),queryReady:this.ready(),productionEnabled:false};
 }

 async detail(id:string){const row=await this.job(id),order=await this.order(row.order_id);
  const history=await this.a.all('SELECT * FROM payment_recovery_attempts WHERE job_id=? ORDER BY created,id',id);
  return {job:this.summary(row),order:this.orderSummary(order),attempts:history.map((r:any)=>({id:r.id,jobId:r.job_id,attempt:r.attempt,
   action:r.action,actor:r.actor,result:r.result,errorCode:r.error_code,created:r.created})),queryReady:this.ready(),productionEnabled:false};}
 async list(){const status=this.a.url.searchParams.get('status'),before=this.a.url.searchParams.get('before'),where:string[]=[],args:any[]=[];
  if(status){if(!STATUSES.includes(status))return this.fail(400,'恢复状态无效。');where.push('status=?');args.push(status);}
  if(before){const row=await this.job(before);where.push('(created,id)<(?,?)');args.push(row.created,row.id);}
  const rows=await this.a.all('SELECT * FROM payment_recovery_jobs'+(where.length?' WHERE '+where.join(' AND '):'')+' ORDER BY created DESC,id DESC LIMIT 26',...args);
  return {items:rows.slice(0,25).map((r:any)=>this.summary(r)),next:rows.length>25?rows[24].id:null,queryReady:this.ready(),productionEnabled:false};}
 async process(data:any,actor:string,fence?:()=>Promise<any[]>){const limit=data.limit??1;if(Object.keys(data).some(k=>k!=='limit')||!Number.isInteger(limit)||limit<1||limit>5)return this.fail(400,'单次须处理1至5份恢复任务。');
  const stamp=Date.now(),rows=await this.a.all(`SELECT id FROM payment_recovery_jobs WHERE
   (status IN ('pending','retry') AND next_attempt<=?) OR (status='processing' AND lease_until<=?) ORDER BY created,id LIMIT ?`,stamp,stamp,limit);
  const items=[];for(const row of rows)items.push(this.summary(await this.run(row.id,actor,fence)));
  return {items,processed:items.length,queryReady:this.ready(),productionEnabled:false};}
}

export async function paymentRecoveryRoute(a:any,path:string,method:string,fail:(status:number,message:string)=>never){
 const mine=/^\/api\/commerce\/orders\/([A-Za-z0-9:_-]{1,100})\/payment-recovery$/.exec(path);
 const admin=path==='/api/admin/payment-recovery'||path.startsWith('/api/admin/payment-recovery/');
 if(!mine&&!admin)return undefined;
 const actor=a.require(admin?['admin']:undefined).id,service=new PaymentRecovery(a,fail);
 await a.rate('payment-recovery:'+(method==='GET'?'read:':'write:')+actor,method==='GET'?180:30);
 if(mine){const order=await service.order(mine[1],actor);if(method==='GET')return service.view(order);
  if(method==='POST')return service.start(order,await a.body(),actor);return fail(405,'不支持的支付恢复操作。');}
 if(path==='/api/admin/payment-recovery'&&method==='GET')return service.list();
 if(path==='/api/admin/payment-recovery/process'&&method==='POST')return service.process(await a.body(),actor);
 const detail=/^\/api\/admin\/payment-recovery\/([A-Za-z0-9:_-]{1,100})(\/retry)?$/.exec(path);
 if(detail&&detail[2]&&method==='POST')return service.retry(detail[1],actor,await a.body());
 if(detail&&!detail[2]&&method==='GET')return service.detail(detail[1]);
 return fail(404,'找不到此支付恢复功能。');
}

export function paymentRecoverySandboxReady(a:any){return !!configuration(a);}
export async function processPaymentRecovery(a:any,limit:number,fail:(s:number,m:string)=>never,fence?:()=>Promise<any[]>){
 const actor=a.require(['admin']).id;await a.rate('payment-recovery:write:'+actor,30);
 return new PaymentRecovery(a,fail).process({limit},actor,fence);
}
