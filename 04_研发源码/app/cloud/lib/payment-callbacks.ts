// PAY08 durable sandbox callback inbox. This HMAC fixture is not a payment-provider protocol.
import {applyLatePayment} from './payment-late';
// Real channels stay closed; settlement is a separate, explicitly invoked admin consumer.
const STATUSES = ['received','processing','retry','applied','manual_review'];
const MAX_ATTEMPTS = 5, LEASE_MS = 30000, MAX_BYTES = 8192;
const DDL = [
 `CREATE TABLE IF NOT EXISTS payment_callback_inbox(
 id TEXT PRIMARY KEY,event_id TEXT NOT NULL UNIQUE,transaction_id TEXT NOT NULL,
 order_id TEXT NOT NULL,fingerprint TEXT NOT NULL,amount_minor INTEGER NOT NULL,currency TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('received','processing','retry','applied','manual_review')),
 attempts INTEGER NOT NULL DEFAULT 0,lease_token TEXT NOT NULL DEFAULT '',lease_until INTEGER NOT NULL DEFAULT 0,
 next_attempt INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '',received_count INTEGER NOT NULL DEFAULT 1,
 created INTEGER NOT NULL,updated INTEGER NOT NULL)`,
 'CREATE INDEX IF NOT EXISTS payment_callback_queue ON payment_callback_inbox(status,next_attempt,created,id)',
 'CREATE INDEX IF NOT EXISTS payment_callback_transaction ON payment_callback_inbox(transaction_id)',
 `CREATE TABLE IF NOT EXISTS payment_callback_transactions(
 transaction_id TEXT PRIMARY KEY,order_id TEXT NOT NULL,fingerprint TEXT NOT NULL,receipt_id TEXT NOT NULL,
 ledger_id TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,updated INTEGER NOT NULL)`,
 `CREATE TABLE IF NOT EXISTS payment_callback_attempts(
 id TEXT PRIMARY KEY,receipt_id TEXT NOT NULL,attempt INTEGER NOT NULL,action TEXT NOT NULL,
 actor TEXT NOT NULL,result TEXT NOT NULL,error_code TEXT NOT NULL,created INTEGER NOT NULL)`,
 'CREATE INDEX IF NOT EXISTS payment_callback_attempt_receipt ON payment_callback_attempts(receipt_id,created,id)',
 // A transient CHECK guard makes a stale preflight abort the entire D1 settlement batch.
 'CREATE TABLE IF NOT EXISTS payment_callback_guards(id TEXT PRIMARY KEY,ok INTEGER NOT NULL CHECK(ok=1))',
];
const encoder = new TextEncoder();
const hex = (bytes:ArrayBuffer) => Array.from(new Uint8Array(bytes),n=>n.toString(16).padStart(2,'0')).join('');
const digest = async(text:string) => hex(await crypto.subtle.digest('SHA-256',encoder.encode(text)));
const canonical = (value:any):any => value && typeof value === 'object' && !Array.isArray(value)
 ? Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])])) : value;
const failureText = (value:any) => [value?.message,value?.cause?.message,String(value||'')].filter(Boolean).join(' ');
export type RecoveryReceiptScope={jobId:string,owner:string,jobLease:string,receiptId:string,queryBinding:string};

export async function initPaymentCallbacks(a:any) {
 if (!await a.one("SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_callback_guards'"))
  await a.db.batch(DDL.map(sql=>a.stmt(sql)));
}

// Server-only normalized-event persistence. Public callers still pass the HMAC verifier below.
// Query adapters compose these statements with their own authenticated job/lease transaction guard.
export async function prepareVerifiedEvent(a:any,data:any) {
 const fingerprint=await digest(JSON.stringify(canonical({transactionId:data.transactionId,orderId:data.orderId,
  type:data.type,amountMinor:data.amountMinor,currency:data.currency})));
 const id=crypto.randomUUID(),stamp=Date.now();
 return {id,eventId:data.eventId,transactionId:data.transactionId,fingerprint,statements:[
  a.stmt(`INSERT OR IGNORE INTO payment_callback_transactions(transaction_id,order_id,fingerprint,receipt_id,created,updated)
   SELECT ?,?,?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM payment_callback_inbox WHERE event_id=? AND fingerprint!=?)`,
   data.transactionId,data.orderId,fingerprint,id,stamp,stamp,data.eventId,fingerprint),
  a.stmt(`INSERT OR IGNORE INTO payment_callback_inbox
   (id,event_id,transaction_id,order_id,fingerprint,amount_minor,currency,status,attempts,lease_token,lease_until,next_attempt,last_error,received_count,created,updated)
   SELECT ?,?,?,?,?,?,?,coalesce(i.status,'received'),0,'',coalesce(i.lease_until,0),coalesce(i.next_attempt,0),coalesce(i.last_error,''),0,?,?
   FROM payment_callback_transactions t LEFT JOIN payment_callback_inbox i ON i.id=t.receipt_id
   WHERE t.transaction_id=? AND t.fingerprint=?`,id,data.eventId,data.transactionId,data.orderId,fingerprint,data.amountMinor,data.currency,stamp,stamp,data.transactionId,fingerprint),
  a.stmt('UPDATE payment_callback_inbox SET received_count=received_count+1,updated=? WHERE event_id=? AND fingerprint=?',stamp,data.eventId,fingerprint),
  a.stmt(`INSERT INTO payment_callback_attempts SELECT ?,id,0,'receive','',status,'',? FROM payment_callback_inbox
   WHERE id=? AND event_id=? AND fingerprint=?`,crypto.randomUUID(),stamp,id,data.eventId,fingerprint),
 ]};
}

export async function verifiedEventReceipt(a:any,prepared:any) {
 const row=await a.one('SELECT * FROM payment_callback_inbox WHERE event_id=?',prepared.eventId);
 const transaction=await a.one('SELECT * FROM payment_callback_transactions WHERE transaction_id=?',prepared.transactionId);
 const conflict=!row||row.fingerprint!==prepared.fingerprint||!transaction||transaction.fingerprint!==prepared.fingerprint;
 return {receiptId:conflict?null:row.id,canonicalReceiptId:conflict?null:transaction.receipt_id,
  duplicate:!conflict&&(row.received_count>1||transaction.receipt_id!==row.id),conflict};
}

export async function persistVerifiedEvent(a:any,data:any) {
 const prepared=await prepareVerifiedEvent(a,data);await a.db.batch(prepared.statements);
 return verifiedEventReceipt(a,prepared);
}

class PaymentCallbacks {
 constructor(private a:any,private fail:(status:number,message:string)=>never) {}

 settings() {
  const ref = this.a.env.EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF;
  const valid = typeof ref === 'string' && /^EW_PAYMENT_CALLBACK_[A-Z0-9_]{1,80}$/.test(ref);
  const secret = valid ? this.a.env[ref] : undefined;
  return {sandboxEnabled:this.a.env.EW_PAYMENT_CALLBACK_SANDBOX_ENABLED==='1' &&
   typeof secret==='string' && [...secret].length>=32,productionEnabled:false,adapter:'sandbox-hmac-fixture'};
 }

 async summary(row:any) {
  const transaction = await this.a.one('SELECT t.receipt_id,i.attempts FROM payment_callback_transactions t JOIN payment_callback_inbox i ON i.id=t.receipt_id WHERE t.transaction_id=?',row.transaction_id);
  return {id:row.id,eventId:row.event_id,transactionId:row.transaction_id,orderId:row.order_id,
   amountMinor:row.amount_minor,currency:row.currency,status:row.status,attempts:transaction?.attempts??row.attempts,
   receivedCount:row.received_count,lastError:row.last_error,nextAttempt:row.next_attempt,
   leaseUntil:row.lease_until,created:row.created,updated:row.updated,
   canonicalReceiptId:transaction?.receipt_id||row.id,duplicate:!!transaction&&transaction.receipt_id!==row.id,
   sandboxOnly:true,productionEnabled:false};
 }

 async receipt(id:string) {
  const row=await this.a.one('SELECT * FROM payment_callback_inbox WHERE id=?',id);
  if(!row)return this.fail(404,'找不到此回调收件。');
  return row;
 }

 async raw() {
  if((this.a.request.headers.get('content-type')||'').split(';')[0].trim().toLowerCase()!=='application/json')
   return this.fail(415,'回调须使用JSON。');
  const declared=this.a.request.headers.get('content-length');
  if(declared && (!/^\d+$/.test(declared)||Number(declared)>MAX_BYTES))return this.fail(413,'回调内容超出大小限制。');
  const reader=this.a.request.body?.getReader();
  if(!reader)return this.fail(400,'回调内容为空。');
  const chunks:Uint8Array[]= [];let size=0;
  try {
   while(true){const next=await reader.read();if(next.done)break;size+=next.value.byteLength;
    if(size>MAX_BYTES){await reader.cancel();return this.fail(413,'回调内容超出大小限制。');}chunks.push(next.value);}
  } finally {reader.releaseLock();}
  if(!size)return this.fail(400,'回调内容为空。');
  const bytes=new Uint8Array(size);let offset=0;
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
  try{return new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{return this.fail(400,'回调编码无效。');}
 }

 async receive() {
  if(!this.settings().sandboxEnabled)return this.fail(503,'沙箱回调适配未配置；正式支付渠道保持关闭。');
  await this.a.rate('payment-callback:ingress',120);
  const timestamp=this.a.request.headers.get('X-EW-Callback-Timestamp')||'';
  const signature=this.a.request.headers.get('X-EW-Callback-Signature')||'';
  if(!/^\d{1,12}$/.test(timestamp)||Math.abs(Math.floor(Date.now()/1000)-Number(timestamp))>300||!/^[a-fA-F0-9]{64}$/.test(signature))
   return this.fail(401,'回调签名或时间戳无效。');
  const raw=await this.raw();
  const secret=this.a.env[this.a.env.EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF];
  const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['verify']);
  const signatureBytes=Uint8Array.from(signature.match(/../g)!,value=>parseInt(String(value),16));
  if(!await crypto.subtle.verify('HMAC',key,signatureBytes,encoder.encode(timestamp+'.'+raw)))
   return this.fail(401,'回调签名或时间戳无效。');
  let data:any;try{data=JSON.parse(raw);}catch{return this.fail(400,'回调JSON格式错误。');}
  // Complete JSON string tokens expose duplicate keys without inspecting substrings inside string values.
  const keyTokens=[...raw.matchAll(/"(?:\\.|[^"\\])*"/g)]
   .filter(match=>/^\s*:/.test(raw.slice(match.index!+match[0].length)));
  const inputKeys=keyTokens.map(match=>JSON.parse(match[0]));
  if(new Set(inputKeys).size!==inputKeys.length)return this.fail(400,'回调字段不可重复。');
  const amountToken=keyTokens.find(match=>JSON.parse(match[0])==='amountMinor');
  if(!amountToken||!/^\s*:\s*-?(?:0|[1-9]\d*)(?=\s*[,}])/.test(raw.slice(amountToken.index!+amountToken[0].length)))
   return this.fail(400,'回调金额须为整数。');
  const keys=['amountMinor','currency','eventId','orderId','transactionId','type'];
  if(!data||typeof data!=='object'||Array.isArray(data)||Object.keys(data).sort().join(',')!==keys.join(',')||
   !['eventId','transactionId','orderId'].every(k=>typeof data[k]==='string'&&/^[A-Za-z0-9:_-]{1,100}$/.test(data[k]))||
   data.type!=='payment.succeeded'||!Number.isSafeInteger(data.amountMinor)||data.amountMinor<0||data.amountMinor>1000000000||
   typeof data.currency!=='string'||!/^[A-Z]{3}$/.test(data.currency))return this.fail(400,'回调字段无效。');
  const receipt=await persistVerifiedEvent(this.a,data);
  if(receipt.conflict){
   await this.a.run('INSERT INTO audits VALUES(?,?,?,?,?,?)',crypto.randomUUID(),'system:payment-callback-fixture','payment_callback.conflict',data.eventId,'沙箱回调标识内容冲突；原收件与账本未改写。',Date.now());
   return this.fail(409,'回调标识已用于不同内容。');
  }
  return Response.json({accepted:true,receiptId:receipt.receiptId,duplicate:receipt.duplicate,
   sandboxOnly:true,productionEnabled:false},{status:202});
 }

 async list() {
  const query=this.a.url.searchParams,status=query.get('status'),before=query.get('before');
  const where:string[]=[],args:any[]=[];
  if(status){if(!STATUSES.includes(status))return this.fail(400,'回调状态无效。');where.push('status=?');args.push(status);}
  if(before){const cursor=await this.receipt(before);where.push('(created,id)<(?,?)');args.push(cursor.created,cursor.id);}
  const rows=await this.a.all('SELECT * FROM payment_callback_inbox'+(where.length?' WHERE '+where.join(' AND '):'')+' ORDER BY created DESC,id DESC LIMIT 26',...args);
  return {items:await Promise.all(rows.slice(0,25).map((r:any)=>this.summary(r))),next:rows.length>25?rows[24].id:null,settings:this.settings()};
 }

 async finish(row:any,token:string,status:string,error:string,actor:string) {
  const stamp=Date.now(),next=status==='retry'?stamp+Math.min(60000,1000*2**(row.attempts-1)):0;
  const completionId=crypto.randomUUID();
  const ops=[
   this.a.stmt(`UPDATE payment_callback_inbox SET status=?,last_error=?,next_attempt=?,lease_token='',lease_until=0,updated=?
    WHERE id=? AND status='processing' AND lease_token=? AND lease_until>?`,status,error,next,stamp,row.id,token,stamp),
   this.a.stmt(`INSERT INTO payment_callback_attempts SELECT ?,id,attempts,'complete',?,?,?,? FROM payment_callback_inbox
    WHERE id=? AND changes()=1`,completionId,actor,status,error,stamp,row.id),
   this.a.stmt(`UPDATE payment_callback_inbox SET status=?,last_error=?,next_attempt=?,lease_token='',lease_until=0,updated=?
    WHERE transaction_id=? AND id!=? AND EXISTS(SELECT 1 FROM payment_callback_attempts WHERE id=?)`,
    status,error,next,stamp,row.transaction_id,row.id,completionId),
  ];
  await this.a.db.batch(ops);
  return this.summary(await this.receipt(row.id));
 }

 async reason(row:any) {
  if(!this.settings().sandboxEnabled)return 'adapter_disabled';
  if(row.event_id.startsWith('query:')){
   const source=await import('./payment-recovery');
   if(!(await source.queryReceiptBinding(this.a,row.id)).valid)return 'adapter_disabled';
  }
  const setting=await this.a.one("SELECT data FROM commerce_config WHERE key='settings'");
  if(!setting||JSON.parse(setting.data).sandboxEnabled!==true)return 'commerce_sandbox_disabled';
  const order=await this.a.one("SELECT * FROM commerce_orders WHERE id=? AND environment='sandbox'",row.order_id);
  if(!order)return 'unknown_order';
  if(await this.a.one("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'",order.owner))return 'account_closed';
  if(!await this.a.one('SELECT 1 FROM users WHERE id=?',order.owner))return 'account_closed';
  if(order.total_minor!==row.amount_minor||order.currency!==row.currency)return 'amount_currency_mismatch';
  if(order.payment_status!=='unpaid'||order.status!=='awaiting_payment')return 'order_not_payable';
  if(order.reserved_until<=Date.now())return 'order_expired';
  if(await this.a.one("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='membership'",row.order_id))return 'membership_requires_adapter';
  if(!await this.a.one('SELECT 1 FROM commerce_order_items WHERE order_id=?',row.order_id))return 'invalid_order_items';
  if(await this.a.one("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type NOT IN ('digital','physical')",row.order_id))return 'unsupported_order_type';
  if(await this.a.one("SELECT 1 FROM commerce_order_items i LEFT JOIN commerce_products p ON p.id=i.product_id WHERE i.order_id=? AND (p.id IS NULL OR p.status!='published' OR p.environment!='sandbox')",row.order_id))return 'product_unavailable';
  if(await this.a.one(`SELECT 1 FROM commerce_order_items i LEFT JOIN commerce_reservations r ON r.order_id=i.order_id AND r.sku_id=i.sku_id
   LEFT JOIN commerce_skus s ON s.id=i.sku_id WHERE i.order_id=? AND
   (r.state IS NULL OR r.state!='held' OR r.quantity!=i.quantity OR s.id IS NULL OR s.environment!='sandbox' OR s.reserved<r.quantity OR s.stock<s.reserved)`,row.order_id))return 'reservation_unavailable';
  if(await this.a.one("SELECT 1 FROM commerce_payment_events WHERE order_id=? AND kind='sandbox_pay'",row.order_id))return 'order_already_paid';
  return '';
 }

 recoveryBinding(scope:RecoveryReceiptScope,orderId:string,stamp:number) {
  return {sql:`EXISTS(SELECT 1 FROM payment_recovery_jobs j JOIN commerce_orders o ON o.id=j.order_id
   WHERE j.id=? AND j.owner=? AND j.lease_token=? AND j.status='processing' AND j.lease_until>?
   AND j.receipt_id=? AND j.order_id=? AND j.query_binding=? AND o.owner=j.owner AND o.environment='sandbox'
   AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=j.owner AND l.status='closed'))`,
   args:[scope.jobId,scope.owner,scope.jobLease,stamp,scope.receiptId,orderId,scope.queryBinding]};
 }

 async tryLate(row:any,token:string,actor:string,scope?:RecoveryReceiptScope){
  const stamp=Date.now();let queryProof:any=null;
  const revalidate=async()=>{
   if(!this.settings().sandboxEnabled)return false;
   if(row.event_id.startsWith('query:')||scope){const source=await import('./payment-recovery');
    if(scope&&await source.currentPaymentQueryBinding(this.a)!==scope.queryBinding)return false;
    if(row.event_id.startsWith('query:'))return (await source.queryReceiptBinding(this.a,row.id)).valid;
   }return true;
  };
  if(!await revalidate())throw Error('payment_query_binding_changed');
  if(row.event_id.startsWith('query:'))queryProof=await (await import('./payment-recovery')).queryReceiptBinding(this.a,row.id);
  let sql=`EXISTS(SELECT 1 FROM payment_callback_inbox i JOIN payment_callback_transactions t ON t.transaction_id=i.transaction_id
   JOIN commerce_orders o ON o.id=i.order_id JOIN users u ON u.id=o.owner WHERE i.id=? AND i.status='processing' AND i.lease_token=? AND i.lease_until>?
   AND t.receipt_id=i.id AND t.fingerprint=i.fingerprint AND t.ledger_id='' AND o.environment='sandbox'
   AND o.total_minor=i.amount_minor AND o.currency=i.currency
   AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=o.owner AND l.status='closed')
   AND EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1))`;
  const args:any[]=[row.id,token,stamp];
  if(scope){const binding=this.recoveryBinding(scope,row.order_id,stamp);sql+=' AND '+binding.sql;args.push(...binding.args);}
  if(queryProof){sql+=` AND EXISTS(SELECT 1 FROM payment_recovery_jobs j JOIN payment_callback_inbox q ON q.id=j.receipt_id
   JOIN payment_callback_transactions t ON t.transaction_id=q.transaction_id WHERE j.id=? AND j.owner=? AND j.order_id=?
   AND j.query_binding=? AND q.order_id=j.order_id AND t.receipt_id=?)`;
   args.push(queryProof.jobId,queryProof.owner,queryProof.orderId,queryProof.binding,row.id);}
  const result=await applyLatePayment(this.a,row,token,actor,{sql,args,revalidate});
  if(result.handled)return this.summary(await this.receipt(row.id));
  if(result.error)return this.finish(row,token,'manual_review',result.error,actor);
  return undefined;
 }

 async apply(row:any,token:string,actor:string,scope?:RecoveryReceiptScope) {
  const stamp=Date.now(),ledgerId='callback:'+row.id,requestId='callback:'+row.transaction_id;
  let queryProof:any=null;
  if(row.event_id.startsWith('query:')||scope){
   const source=await import('./payment-recovery');
   if(scope&&await source.currentPaymentQueryBinding(this.a)!==scope.queryBinding)throw Error('payment_query_binding_changed');
   if(row.event_id.startsWith('query:')){queryProof=await source.queryReceiptBinding(this.a,row.id);if(!queryProof.valid)throw Error('payment_query_binding_changed');}
  }
  const ledgerFingerprint=await digest(JSON.stringify(canonical({orderId:row.order_id,kind:'sandbox_pay'})));
  // All predicates are re-read inside the D1 batch, behind a CHECK guard. No user impersonation.
  let valid=`EXISTS(SELECT 1 FROM payment_callback_inbox i JOIN payment_callback_transactions t
   ON t.transaction_id=i.transaction_id JOIN commerce_orders o ON o.id=i.order_id JOIN users u ON u.id=o.owner
   WHERE i.id=? AND i.lease_token=? AND i.status='processing' AND i.lease_until>?
   AND t.receipt_id=i.id AND t.fingerprint=i.fingerprint AND t.ledger_id=''
   AND o.environment='sandbox' AND o.status='awaiting_payment' AND o.payment_status='unpaid' AND o.reserved_until>?
   AND o.total_minor=i.amount_minor AND o.currency=i.currency
   AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=o.owner AND l.status='closed')
   AND EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1)
   AND EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=o.id)
   AND NOT EXISTS(SELECT 1 FROM commerce_order_items x LEFT JOIN commerce_reservations r ON r.order_id=x.order_id AND r.sku_id=x.sku_id
    LEFT JOIN commerce_products p ON p.id=x.product_id LEFT JOIN commerce_skus s ON s.id=x.sku_id WHERE x.order_id=o.id AND
    (x.type NOT IN ('digital','physical') OR p.id IS NULL OR p.status!='published' OR p.environment!='sandbox'
    OR r.state IS NULL OR r.state!='held' OR r.quantity!=x.quantity OR s.id IS NULL OR s.environment!='sandbox' OR s.reserved<r.quantity OR s.stock<s.reserved)))`;
  const bindings:any[]=[row.id,token,stamp,stamp];
  if(scope){const binding=this.recoveryBinding(scope,row.order_id,stamp);valid+=' AND '+binding.sql;bindings.push(...binding.args);}
  if(queryProof){valid+=` AND EXISTS(SELECT 1 FROM payment_recovery_jobs j JOIN payment_callback_inbox q ON q.id=j.receipt_id
   JOIN payment_callback_transactions t ON t.transaction_id=q.transaction_id WHERE j.id=? AND j.owner=? AND j.order_id=?
   AND j.query_binding=? AND q.order_id=j.order_id AND t.receipt_id=?)`;
   bindings.push(queryProof.jobId,queryProof.owner,queryProof.orderId,queryProof.binding,row.id);}
  await this.a.db.batch([
   this.a.stmt('INSERT INTO payment_callback_guards VALUES(?,CASE WHEN '+valid+' THEN 1 ELSE 0 END)',token,...bindings),
   this.a.stmt(`INSERT INTO commerce_payment_events
    SELECT ?,o.owner,'sandbox',o.id,?,'sandbox_pay',?,o.total_minor,o.currency,'[]','applied',?
    FROM commerce_orders o WHERE o.id=?`,ledgerId,requestId,ledgerFingerprint,stamp,row.order_id),
   this.a.stmt(`UPDATE commerce_orders SET status=CASE WHEN EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='physical')
    THEN 'paid' ELSE 'completed' END,payment_status='paid',fulfillment_status=CASE WHEN EXISTS(SELECT 1 FROM commerce_order_items
    WHERE order_id=? AND type='physical') THEN 'awaiting_fulfillment' ELSE 'fulfilled' END,updated=? WHERE id=?`,row.order_id,row.order_id,stamp,row.order_id),
   this.a.stmt("DELETE FROM commerce_carts WHERE environment='sandbox' AND owner=(SELECT owner FROM commerce_orders WHERE id=?)",row.order_id),
   this.a.stmt('UPDATE payment_callback_transactions SET ledger_id=?,updated=? WHERE transaction_id=?',ledgerId,stamp,row.transaction_id),
   this.a.stmt(`UPDATE payment_callback_inbox SET status='applied',last_error='',next_attempt=0,lease_token='',lease_until=0,updated=? WHERE transaction_id=?`,stamp,row.transaction_id),
   this.a.stmt("INSERT INTO payment_callback_attempts VALUES(?,?,?,'complete',?,'applied','',?)",crypto.randomUUID(),row.id,row.attempts,actor,stamp),
   this.a.stmt('DELETE FROM payment_callback_guards WHERE id=?',token),
   this.a.stmt('INSERT INTO audits VALUES(?,?,?,?,?,?)',crypto.randomUUID(),actor,'payment_callback.applied',row.id,'sandbox；已应用隔离订单，无真实资金流动。',stamp),
  ]);
  return this.summary(await this.receipt(row.id));
 }

 async processRecoveryReceipt(receiptId:string,actor:string,scope:RecoveryReceiptScope) {
  const requested=await this.receipt(receiptId),tx=await this.a.one('SELECT * FROM payment_callback_transactions WHERE transaction_id=?',requested.transaction_id);
  if(!tx)return this.fail(409,'恢复收件关联无效。');
  const primary=await this.receipt(tx.receipt_id),binding=this.recoveryBinding(scope,primary.order_id,Date.now());
  if(scope.receiptId!==receiptId||!await this.a.one('SELECT 1 WHERE '+binding.sql,...binding.args))return this.summary(primary);
  if(['applied','manual_review'].includes(primary.status))return this.summary(primary);
  const stamp=Date.now(),token=crypto.randomUUID();
  if(primary.attempts>=MAX_ATTEMPTS)return this.summary(primary);
  const guard=this.recoveryBinding(scope,primary.order_id,stamp);
  const claim=await this.a.db.batch([
   this.a.stmt(`UPDATE payment_callback_inbox SET status='processing',attempts=attempts+1,lease_token=?,lease_until=?,next_attempt=0,last_error='',updated=?
    WHERE id=? AND attempts<? AND ((status IN ('received','retry') AND next_attempt<=?) OR (status='processing' AND lease_until<=?)) AND `+guard.sql,
    token,stamp+LEASE_MS,stamp,primary.id,MAX_ATTEMPTS,stamp,stamp,...guard.args),
   this.a.stmt(`UPDATE payment_callback_inbox SET status='processing',lease_until=?,next_attempt=0,last_error='',updated=?
    WHERE transaction_id=? AND id!=? AND EXISTS(SELECT 1 FROM payment_callback_inbox WHERE id=? AND lease_token=?)`,stamp+LEASE_MS,stamp,primary.transaction_id,primary.id,primary.id,token),
   this.a.stmt(`INSERT INTO payment_callback_attempts SELECT ?,id,attempts,'claim',?,'processing',?,? FROM payment_callback_inbox WHERE id=? AND lease_token=?`,
    crypto.randomUUID(),actor,primary.status==='processing'?'lease_expired':'',stamp,primary.id,token),
   this.a.stmt('SELECT * FROM payment_callback_inbox WHERE id=? AND lease_token=?',primary.id,token),
  ]);
  const row=claim[3].results?.[0];if(!row)return this.summary(await this.receipt(primary.id));
  const current=async()=>{const b=this.recoveryBinding(scope,row.order_id,Date.now());return !!await this.a.one('SELECT 1 WHERE '+b.sql,...b.args);};
  try{
   const transaction=await this.a.one('SELECT * FROM payment_callback_transactions WHERE transaction_id=? AND receipt_id=? AND fingerprint=?',row.transaction_id,row.id,row.fingerprint);
   if(!await current())return this.summary(await this.receipt(primary.id));
   if(!transaction)return this.finish(row,token,'manual_review','transaction_conflict',actor);
   if(transaction.ledger_id)return this.finish(row,token,'applied','',actor);
   const reason=await this.reason(row);
   if(reason==='order_expired'||reason==='order_not_payable'){
    const late=await this.tryLate(row,token,actor,scope);if(late)return late;
   }
   if(reason){const retry=['adapter_disabled','commerce_sandbox_disabled'].includes(reason)&&row.attempts<MAX_ATTEMPTS;
    if(!await current())return this.summary(await this.receipt(primary.id));
    return this.finish(row,token,retry?'retry':'manual_review',reason,actor);}
   return await this.apply(row,token,actor,scope);
  }catch(error){
   const message=failureText(error);if(/account_actor_|account_settlement_/.test(message))throw error;
   if(!await current())return this.summary(await this.receipt(primary.id));
   const conflict=/UNIQUE constraint|CHECK constraint|FOREIGN KEY constraint|constraint failed|commerce_|membership_/i.test(message);
   return this.finish(row,token,conflict||row.attempts>=MAX_ATTEMPTS?'manual_review':'retry',message.includes('payment_query_binding_changed')?'adapter_disabled':conflict?'application_conflict':'storage_unavailable',actor);
  }
 }

 async process(limit:number,actor:string,fence?:()=>Promise<any[]>) {
  const claimBatch=async(ops:any[])=>{const prefix=fence?await fence():[];return (await this.a.db.batch([...prefix,...ops])).slice(prefix.length);};
  const items:any[]=[];
  for(let iteration=0;iteration<limit;iteration++){
   const token=crypto.randomUUID(),now=Date.now();
   const candidate=await this.a.one(`SELECT i.* FROM payment_callback_inbox i JOIN payment_callback_transactions t ON t.receipt_id=i.id
    WHERE (i.status IN ('received','retry') AND i.next_attempt<=?) OR (i.status='processing' AND i.lease_until<=?)
    ORDER BY i.created,i.id LIMIT 1`,now,now);
   if(!candidate)break;
   if(candidate.attempts>=MAX_ATTEMPTS){
    await claimBatch([
     this.a.stmt(`UPDATE payment_callback_inbox SET status='manual_review',last_error='retry_exhausted',lease_token='',lease_until=0,next_attempt=0,updated=?
      WHERE id=? AND attempts>=? AND ((status IN ('received','retry') AND next_attempt<=?) OR (status='processing' AND lease_until<=?))`,now,candidate.id,MAX_ATTEMPTS,now,now),
     this.a.stmt(`UPDATE payment_callback_inbox SET status='manual_review',last_error='retry_exhausted',lease_token='',lease_until=0,next_attempt=0,updated=?
      WHERE transaction_id=? AND id!=? AND EXISTS(SELECT 1 FROM payment_callback_inbox WHERE id=? AND status='manual_review' AND updated=?)`,now,candidate.transaction_id,candidate.id,candidate.id,now),
     this.a.stmt(`INSERT INTO payment_callback_attempts SELECT ?,id,attempts,'recover',?,'manual_review','retry_exhausted',?
      FROM payment_callback_inbox WHERE id=? AND status='manual_review' AND updated=?`,crypto.randomUUID(),actor,now,candidate.id,now),
    ]);
    items.push(await this.summary(await this.receipt(candidate.id)));continue;
   }
   const claimed=await claimBatch([
    this.a.stmt(`UPDATE payment_callback_inbox SET status='processing',attempts=attempts+1,lease_token=?,lease_until=?,next_attempt=0,last_error='',updated=?
     WHERE id=? AND attempts<? AND (status='received' OR (status='retry' AND next_attempt<=?) OR (status='processing' AND lease_until<=?))`,token,now+LEASE_MS,now,candidate.id,MAX_ATTEMPTS,now,now),
    this.a.stmt(`UPDATE payment_callback_inbox SET status='processing',lease_until=?,next_attempt=0,last_error='',updated=?
     WHERE transaction_id=? AND id!=? AND EXISTS(SELECT 1 FROM payment_callback_inbox WHERE id=? AND lease_token=?)`,now+LEASE_MS,now,candidate.transaction_id,candidate.id,candidate.id,token),
    this.a.stmt(`INSERT INTO payment_callback_attempts SELECT ?,id,attempts,'claim',?,'processing',?,? FROM payment_callback_inbox WHERE id=? AND lease_token=?`,
     crypto.randomUUID(),actor,candidate.status==='processing'?'lease_expired':'',now,candidate.id,token),
    this.a.stmt('SELECT * FROM payment_callback_inbox WHERE id=? AND lease_token=?',candidate.id,token),
   ]);
   const row=claimed[3].results?.[0];if(!row)continue;
   try{
    const transaction=await this.a.one('SELECT * FROM payment_callback_transactions WHERE transaction_id=? AND receipt_id=? AND fingerprint=?',row.transaction_id,row.id,row.fingerprint);
    if(!transaction){items.push(await this.finish(row,token,'manual_review','transaction_conflict',actor));continue;}
    if(transaction.ledger_id){items.push(await this.finish(row,token,'applied','',actor));continue;}
    const reason=await this.reason(row);
    if(reason==='order_expired'||reason==='order_not_payable'){
     const late=await this.tryLate(row,token,actor);if(late){items.push(late);continue;}
    }
    if(reason){const retry=['adapter_disabled','commerce_sandbox_disabled'].includes(reason)&&row.attempts<MAX_ATTEMPTS;
     items.push(await this.finish(row,token,retry?'retry':'manual_review',reason,actor));continue;}
    items.push(await this.apply(row,token,actor));
   }catch(error){
    // Losing an admin session/role must still fail at the existing account fence, never be converted into success.
    const message=failureText(error);
    if(/account_actor_|account_settlement_/.test(message))throw error;
    const conflict=/UNIQUE constraint|CHECK constraint|FOREIGN KEY constraint|constraint failed|commerce_|membership_/i.test(message);
    items.push(await this.finish(row,token,conflict||row.attempts>=MAX_ATTEMPTS?'manual_review':'retry',message.includes('payment_query_binding_changed')?'adapter_disabled':conflict?'application_conflict':'storage_unavailable',actor));
   }
  }
  return {items,processed:items.length,settings:this.settings()};
 }

 async retry(id:string,actor:string) {
  const row=await this.receipt(id),transaction=await this.a.one('SELECT receipt_id,ledger_id FROM payment_callback_transactions WHERE transaction_id=?',row.transaction_id);
  if(transaction?.receipt_id!==id)return this.fail(409,'请在原始回调收件上重试。');
  if(!['retry','manual_review'].includes(row.status)||row.attempts>=MAX_ATTEMPTS||row.lease_until>Date.now()||transaction.ledger_id)return this.fail(409,'此收件不可重试或已达到次数上限。');
  const stamp=Date.now();
  await this.a.db.batch([
   this.a.stmt(`UPDATE payment_callback_inbox SET status='retry',next_attempt=0,last_error='',lease_token='',lease_until=0,updated=?
    WHERE transaction_id=? AND status IN ('retry','manual_review') AND EXISTS(SELECT 1 FROM payment_callback_inbox c JOIN payment_callback_transactions t ON t.receipt_id=c.id
    WHERE c.id=? AND c.status IN ('retry','manual_review') AND c.attempts<? AND c.lease_until<=? AND t.ledger_id='')`,stamp,row.transaction_id,id,MAX_ATTEMPTS,stamp),
   this.a.stmt(`INSERT INTO payment_callback_attempts SELECT ?,id,attempts,'retry',?,'retry','',? FROM payment_callback_inbox
    WHERE id=? AND status='retry' AND updated=?`,crypto.randomUUID(),actor,stamp,id,stamp),
   this.a.stmt('INSERT INTO audits VALUES(?,?,?,?,?,?)',crypto.randomUUID(),actor,'payment_callback.retry',id,'管理员请求重试；未重置次数或确认付款。',stamp),
  ]);
  const current=await this.receipt(id);
  if(current.status!=='retry'||current.updated!==stamp)return this.fail(409,'收件状态已变化，请刷新后重试。');
  return {item:await this.summary(current)};
 }
}

export function paymentCallbacksSandboxReady(a:any) {
 return new PaymentCallbacks(a,()=>{throw Error('callback_configuration');}).settings().sandboxEnabled;
}

export async function processRecoveryReceipt(a:any,receiptId:string,actor:string,scope:RecoveryReceiptScope,fail:(status:number,message:string)=>never) {
 const user=a.require();
 if(user.id!==actor||(user.role!=='admin'&&user.id!==scope.owner))return fail(403,'无权处理此订单恢复收件。');
 if(user.role==='admin')a.require(['admin']);
 return new PaymentCallbacks(a,fail).processRecoveryReceipt(receiptId,actor,scope);
}

export async function paymentCallbacksRoute(a:any,path:string,method:string,fail:(status:number,message:string)=>never) {
 const receiver=path==='/api/payment-callbacks'||path.startsWith('/api/payment-callbacks/');
 const admin=path==='/api/admin/payment-callbacks'||path.startsWith('/api/admin/payment-callbacks/');
 if(!receiver&&!admin)return undefined;
 const service=new PaymentCallbacks(a,fail);
 if(receiver){
  if(path!=='/api/payment-callbacks/sandbox')return fail(503,'正式支付渠道回调尚未接入。');
  if(method!=='POST')return fail(405,'回调仅支持POST。');
  return service.receive();
 }
 const actor=a.require(['admin']).id;
 await a.rate('payment-callback:admin:'+(method==='GET'?'read:':'write:')+actor,method==='GET'?180:30);
 if(path==='/api/admin/payment-callbacks'&&method==='GET')return service.list();
 if(path==='/api/admin/payment-callbacks/process'&&method==='POST'){
  const data=await a.body(),limit=data.limit??1;
  if(!Number.isInteger(limit)||limit<1||limit>10||Object.keys(data).some(k=>k!=='limit'))return fail(400,'单次处理数量须为1至10。');
  return service.process(limit,actor);
 }
 const detail=/^\/api\/admin\/payment-callbacks\/([^/]+)(\/retry)?$/.exec(path);
 if(detail&&detail[2]&&method==='POST'){
  const data=await a.body();if(Object.keys(data).length)return fail(400,'重试不接受付款或额度参数。');
  return service.retry(detail[1],actor);
 }
 if(detail&&!detail[2]&&method==='GET'){
  const row=await service.receipt(detail[1]);
  const attempts=await a.all('SELECT * FROM payment_callback_attempts WHERE receipt_id=? ORDER BY created,id',row.id);
  return {item:await service.summary(row),attempts:attempts.map((item:any)=>({id:item.id,receiptId:item.receipt_id,attempt:item.attempt,
   action:item.action,actor:item.actor,result:item.result,errorCode:item.error_code,created:item.created}))};
 }
 return fail(404,'找不到此回调管理功能。');
}

// Server-only native consumer; no request body or identity substitution.
export async function processPaymentCallbacks(a:any,limit:number,fail:(s:number,m:string)=>never,fence?:()=>Promise<any[]>){
 const actor=a.require(['admin']).id;await a.rate('payment-callback:admin:write:'+actor,30);
 if(!Number.isInteger(limit)||limit<1||limit>10)fail(400,'单次处理数量须为1至10。');
 return new PaymentCallbacks(a,fail).process(limit,actor,fence);
}
