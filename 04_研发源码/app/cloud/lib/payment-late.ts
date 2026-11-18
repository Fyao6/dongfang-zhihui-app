// PAY10/PAY13 sandbox late settlement. Refund cases are liabilities, never proof of money returned.
const STATUSES=['fulfilled','refund_pending','refund_processing'];
const DDL=[
 `CREATE TABLE IF NOT EXISTS payment_late_cases(id TEXT PRIMARY KEY,owner TEXT NOT NULL,
 order_id TEXT NOT NULL UNIQUE,transaction_id TEXT NOT NULL UNIQUE,receipt_id TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('fulfilled','refund_pending','refund_processing')),reason TEXT NOT NULL,
 amount_minor INTEGER NOT NULL,currency TEXT NOT NULL,ledger_id TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,updated INTEGER NOT NULL)`,
 'CREATE INDEX IF NOT EXISTS payment_late_queue ON payment_late_cases(status,created,id)',
 `CREATE TABLE IF NOT EXISTS payment_late_attempts(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,action TEXT NOT NULL,
 actor TEXT NOT NULL,request_id TEXT NOT NULL DEFAULT '',note TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL)`,
 "CREATE UNIQUE INDEX IF NOT EXISTS payment_late_request ON payment_late_attempts(actor,request_id) WHERE request_id!=''",
 'CREATE INDEX IF NOT EXISTS payment_late_history ON payment_late_attempts(case_id,created,id)',
];
const canonical=(value:any)=>JSON.stringify(Object.fromEntries(Object.keys(value).sort().map(k=>[k,value[k]])));
const digest=async(value:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),v=>v.toString(16).padStart(2,'0')).join('');
export type LateReceiptProof={sql:string,args:any[],revalidate?:()=>Promise<boolean>};

export async function initPaymentLate(a:any){
 if(!await a.one("SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_late_attempts'"))
  await a.db.batch(DDL.map(sql=>a.stmt(sql)));
}

export function lateEligible(order:any,stamp=Date.now()){
 return order.status==='awaiting_payment'&&order.payment_status==='unpaid'&&order.reserved_until<=stamp||
  order.status==='closed'&&order.payment_status==='expired';
}

function summary(row:any){return row?{id:row.id,status:row.status,reason:row.reason,amountMinor:row.amount_minor,currency:row.currency,
 created:row.created,updated:row.updated,sandboxOnly:true,productionEnabled:false}:null;}
function adminItem(row:any){return {...summary(row),orderId:row.order_id,transactionId:row.transaction_id,receiptId:row.receipt_id,ledgerId:row.ledger_id};}
export async function latePaymentSummary(a:any,orderId:string,owner:string){
 return summary(await a.one('SELECT * FROM payment_late_cases WHERE order_id=? AND owner=?',orderId,owner));
}

const REASON_SQL=`CASE
 WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=o.id)
 OR EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=o.id AND (type NOT IN ('digital','physical') OR refunded_quantity!=0 OR currency!=o.currency)) THEN 'invalid_order_items'
 WHEN (SELECT count(*) FROM commerce_reservations WHERE order_id=o.id)!=(SELECT count(*) FROM commerce_order_items WHERE order_id=o.id)
 OR EXISTS(SELECT 1 FROM commerce_order_items i LEFT JOIN commerce_reservations r ON r.order_id=i.order_id AND r.sku_id=i.sku_id
 WHERE i.order_id=o.id AND (r.state IS NULL OR r.state!='released' OR r.quantity!=i.quantity)) THEN 'reservation_unavailable'
 WHEN EXISTS(SELECT 1 FROM commerce_order_items i LEFT JOIN commerce_products p ON p.id=i.product_id
 WHERE i.order_id=o.id AND (p.id IS NULL OR p.status!='published')) THEN 'product_unavailable'
 WHEN EXISTS(SELECT 1 FROM commerce_order_items i LEFT JOIN commerce_skus s ON s.id=i.sku_id
 LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id WHERE i.order_id=o.id AND (s.id IS NULL OR coalesce(v.active,1)!=1)) THEN 'sku_unavailable'
 WHEN EXISTS(SELECT 1 FROM commerce_order_items i JOIN commerce_products p ON p.id=i.product_id JOIN commerce_skus s ON s.id=i.sku_id
 LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id WHERE i.order_id=o.id AND (p.environment!='sandbox' OR p.type!=i.type
 OR p.content_id!=i.content_id OR s.product_id!=i.product_id OR s.environment!='sandbox' OR s.currency!=i.currency
 OR NOT EXISTS(SELECT 1 FROM json_each(o.options_proof) proof WHERE json_extract(proof.value,'$.itemId')=i.id
  AND json_extract(proof.value,'$.snapshot')=i.snapshot_data AND json_extract(proof.value,'$.variant')=coalesce(v.options,'[]')
  AND json_extract(proof.value,'$.matches')=1)
 OR (i.type='digital' AND NOT EXISTS(SELECT 1 FROM contents WHERE kind='courses' AND id=i.content_id AND status='published')))) THEN 'binding_changed'
 WHEN EXISTS(SELECT 1 FROM commerce_order_items i JOIN commerce_skus s ON s.id=i.sku_id
 WHERE i.order_id=o.id AND s.stock-s.reserved<i.quantity) THEN 'insufficient_stock'
 ELSE '' END`;

// Caller supplies the same authenticated callback/query lease proof used by the ordinary settlement path.
// D1 evaluates stock availability after releasing this order, inside one transaction; no stale availability branch.
export async function applyLatePayment(a:any,row:any,token:string,actor:string,proof:LateReceiptProof){
 const order=await a.one("SELECT * FROM commerce_orders WHERE id=? AND environment='sandbox'",row.order_id);
 if(!order)return {handled:false,error:''};
 const existing=await a.one('SELECT * FROM payment_late_cases WHERE order_id=? OR transaction_id=?',row.order_id,row.transaction_id);
 if(existing){
  if(existing.order_id!==row.order_id||existing.transaction_id!==row.transaction_id||existing.amount_minor!==row.amount_minor||existing.currency!==row.currency)return {handled:false,error:'late_transaction_conflict'};
  const stamp=Date.now(),error=existing.status==='fulfilled'?'':'late_refund_pending';
  if(proof.revalidate&&!await proof.revalidate())throw Error('payment_query_binding_changed');
  await a.db.batch([
   a.stmt('INSERT INTO payment_callback_guards VALUES(?,CASE WHEN '+proof.sql+' THEN 1 ELSE 0 END)',token,...proof.args),
   a.stmt("UPDATE payment_callback_inbox SET status='applied',last_error=?,next_attempt=0,lease_token='',lease_until=0,updated=? WHERE transaction_id=?",error,stamp,row.transaction_id),
   a.stmt("INSERT INTO payment_callback_attempts VALUES(?,?,?,'complete',?,'applied',?,?)",crypto.randomUUID(),row.id,row.attempts,actor,error,stamp),
   a.stmt('DELETE FROM payment_callback_guards WHERE id=?',token),
  ]);
  return {handled:true,error};
 }
 if(!lateEligible(order))return {handled:false,error:''};
 if(await a.one("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'",order.owner))return {handled:false,error:'account_closed'};
 if(await a.one("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='membership'",order.id))return {handled:false,error:'membership_requires_adapter'};
 const id=crypto.randomUUID(),ledger='callback:'+row.id,stamp=Date.now(),tail=crypto.randomUUID();
 const ledgerFingerprint=await digest(canonical({orderId:order.id,kind:'sandbox_pay'}));
 const optionIdentity=(value:any)=>{
  if(!Array.isArray(value)||value.some(item=>!item||typeof item!=='object'||Array.isArray(item)||Object.keys(item).sort().join(',')!=='name,value'||
   typeof item.name!=='string'||typeof item.value!=='string'))return null;
  return JSON.stringify(value.map(item=>[item.name,item.value]).sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:a[1]<b[1]?-1:a[1]>b[1]?1:0));
 };
 const originalOptions=await a.all(`SELECT i.id,i.snapshot_data,coalesce(v.options,'[]') options FROM commerce_order_items i
  LEFT JOIN commerce_sku_variants v ON v.sku_id=i.sku_id WHERE i.order_id=? ORDER BY i.id`,order.id);
 const optionsProof=JSON.stringify(originalOptions.map((item:any)=>{
  let matches=false;try{const snapshot=JSON.parse(item.snapshot_data),original=snapshot&&typeof snapshot==='object'&&!Array.isArray(snapshot)?optionIdentity(snapshot.options===undefined?[]:snapshot.options):null,
   current=optionIdentity(JSON.parse(item.options));matches=original!==null&&current!==null&&original===current;}catch{}
  return {itemId:item.id,snapshot:item.snapshot_data,variant:item.options,matches};
 }));
 const eligible=`EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=? AND o.environment='sandbox'
  AND ((o.status='awaiting_payment' AND o.payment_status='unpaid' AND o.reserved_until<=?) OR (o.status='closed' AND o.payment_status='expired'))
  AND NOT EXISTS(SELECT 1 FROM commerce_payment_events WHERE order_id=o.id AND kind='sandbox_pay')
  AND NOT EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=o.id AND type='membership')
  AND NOT EXISTS(SELECT 1 FROM payment_late_cases WHERE order_id=o.id OR transaction_id=?))`;
 if(proof.revalidate&&!await proof.revalidate())throw Error('payment_query_binding_changed');
 await a.db.batch([
  a.stmt('INSERT INTO payment_callback_guards VALUES(?,CASE WHEN '+proof.sql+' AND '+eligible+' THEN 1 ELSE 0 END)',
   token,...proof.args,row.order_id,stamp,row.transaction_id),
  // The original order_closed trigger releases only this order's held reservations.
  a.stmt("UPDATE commerce_orders SET status='closed',payment_status='expired',updated=? WHERE id=? AND status='awaiting_payment' AND payment_status='unpaid' AND reserved_until<=?",stamp,order.id,stamp),
  a.stmt("UPDATE commerce_reservations SET state='released' WHERE order_id=? AND state='held'",order.id),
  a.stmt(`INSERT INTO payment_late_cases(id,owner,order_id,transaction_id,receipt_id,status,reason,amount_minor,currency,ledger_id,created,updated)
   SELECT ?,o.owner,o.id,?,?,CASE WHEN o.late_reason='' THEN 'fulfilled' ELSE 'refund_pending' END,o.late_reason,
   o.total_minor,o.currency,CASE WHEN o.late_reason='' THEN ? ELSE '' END,?,?
   FROM (SELECT o.*,${REASON_SQL} AS late_reason FROM (SELECT o.*,? AS options_proof FROM commerce_orders o WHERE o.id=?) o) o`,
   id,row.transaction_id,row.id,ledger,stamp,stamp,optionsProof,order.id),
  a.stmt(`UPDATE commerce_skus SET stock=stock-(SELECT i.quantity FROM commerce_order_items i WHERE i.order_id=? AND i.sku_id=commerce_skus.id)
   WHERE id IN(SELECT sku_id FROM commerce_order_items WHERE order_id=?) AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')`,order.id,order.id,id),
  // released -> consumed does not invoke the old held -> consumed trigger; stock was decremented once above.
  a.stmt("UPDATE commerce_reservations SET state='consumed' WHERE order_id=? AND state='released' AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')",order.id,id),
  a.stmt(`INSERT INTO commerce_payment_events SELECT ?,o.owner,'sandbox',o.id,?,'sandbox_pay',?,o.total_minor,o.currency,'[]','applied',?
   FROM commerce_orders o WHERE o.id=? AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')`,ledger,'callback:'+row.transaction_id,ledgerFingerprint,stamp,order.id,id),
  // expired -> paid intentionally skips the original unpaid -> paid grant trigger.
  a.stmt(`UPDATE commerce_orders SET status=CASE WHEN EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='physical') THEN 'paid' ELSE 'completed' END,
   payment_status='paid',fulfillment_status=CASE WHEN EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='physical') THEN 'awaiting_fulfillment' ELSE 'fulfilled' END,updated=?
   WHERE id=? AND status='closed' AND payment_status='expired' AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')`,order.id,order.id,stamp,order.id,id),
  a.stmt(`INSERT INTO commerce_entitlements SELECT 'sandbox:'||i.id,o.owner,'sandbox',o.id,i.id,i.content_id,i.type,i.quantity,i.quantity,'active',?,?
   FROM commerce_order_items i JOIN commerce_orders o ON o.id=i.order_id WHERE o.id=? AND i.type='digital'
   AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')`,stamp,stamp,order.id,id),
  a.stmt(`INSERT INTO commerce_inventory_events SELECT 'late:'||?||':'||i.id,o.owner,'sandbox',o.id,i.id,i.sku_id,-i.quantity,'late_payment_consumed',?
   FROM commerce_order_items i JOIN commerce_orders o ON o.id=i.order_id WHERE o.id=? AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')`,id,stamp,order.id,id),
  a.stmt("DELETE FROM commerce_carts WHERE owner=? AND environment='sandbox' AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')",order.owner,id),
  a.stmt(`UPDATE commerce_orders SET status='refund_pending',payment_status='refund_pending',fulfillment_status='refund_pending',updated=?
   WHERE id=? AND status='closed' AND payment_status='expired' AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='refund_pending')`,stamp,order.id,id),
  // Recheck the actor/account/callback/query authorization proof before finalizing the receipt.
  a.stmt('INSERT INTO payment_callback_guards VALUES(?,CASE WHEN '+proof.sql+' THEN 1 ELSE 0 END)',tail,...proof.args),
  a.stmt(`UPDATE payment_callback_transactions SET ledger_id=?,updated=? WHERE transaction_id=? AND ledger_id=''
   AND EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')`,ledger,stamp,row.transaction_id,id),
  a.stmt(`UPDATE payment_callback_inbox SET status='applied',last_error=CASE WHEN EXISTS(SELECT 1 FROM payment_late_cases WHERE id=? AND status='fulfilled')
   THEN '' ELSE 'late_refund_pending' END,next_attempt=0,lease_token='',lease_until=0,updated=? WHERE transaction_id=?`,id,stamp,row.transaction_id),
  a.stmt(`INSERT INTO payment_callback_attempts SELECT ?,i.id,i.attempts,'complete',?,'applied',i.last_error,? FROM payment_callback_inbox i WHERE i.id=?`,crypto.randomUUID(),actor,stamp,row.id),
  a.stmt("INSERT INTO payment_late_attempts VALUES(?,?,'create',?,'','',?)",crypto.randomUUID(),id,actor,stamp),
  a.stmt(`INSERT INTO audits SELECT ?,?,'payment_late.process',id,status||'; sandbox only; no real refund',? FROM payment_late_cases WHERE id=?`,crypto.randomUUID(),actor,stamp,id),
  a.stmt('DELETE FROM payment_callback_guards WHERE id IN (?,?)',token,tail),
 ]);
 return {handled:true,error:(await a.one('SELECT status FROM payment_late_cases WHERE id=?',id)).status==='fulfilled'?'':'late_refund_pending'};
}

export async function paymentLateRoute(a:any,path:string,method:string,fail:(status:number,message:string)=>never){
 const prefix='/api/admin/payment-late';if(path!==prefix&&!path.startsWith(prefix+'/'))return undefined;
 const actor=a.require(['admin']).id;await a.rate('payment-late:'+(method==='GET'?'read:':'write:')+actor,method==='GET'?180:30);
 const find=async(id:string)=>{const row=await a.one('SELECT * FROM payment_late_cases WHERE id=?',id);if(!row)return fail(404,'找不到此迟到付款处理记录。');return row;};
 if(path===prefix&&method==='GET'){
  const where:string[]=[],args:any[]=[],status=a.url.searchParams.get('status'),before=a.url.searchParams.get('before');
  if(status){if(!STATUSES.includes(status))return fail(400,'迟到付款状态无效。');where.push('status=?');args.push(status);}
  if(before){const cursor=await find(before);where.push('(created,id)<(?,?)');args.push(cursor.created,cursor.id);}
  const rows=await a.all('SELECT * FROM payment_late_cases'+(where.length?' WHERE '+where.join(' AND '):'')+' ORDER BY created DESC,id DESC LIMIT 26',...args);
  return {items:rows.slice(0,25).map(adminItem),next:rows.length>25?rows[24].id:null,productionEnabled:false};
 }
 const detail=/^\/api\/admin\/payment-late\/([A-Za-z0-9:_-]{1,100})(\/ack)?$/.exec(path);
 if(detail&&detail[2]&&method==='POST'){
  const data=await a.body();if(Object.keys(data).sort().join(',')!=='note,requestId'||typeof data.requestId!=='string'||!/^[A-Za-z0-9:_-]{1,100}$/.test(data.requestId)||
   typeof data.note!=='string'||![...data.note.trim()].length||[...data.note.trim()].length>1000||/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\uD800-\uDFFF]/u.test(data.note))return fail(400,'请填写有效受理编号和说明。');
  const note=data.note.trim(),row=await find(detail[1]);
  const previous=await a.one("SELECT * FROM payment_late_attempts WHERE actor=? AND request_id=?",actor,data.requestId);
  if(previous){if(previous.case_id!==row.id||previous.note!==note)return fail(409,'该受理编号已用于其他内容。');return {item:adminItem(row)};}
  if(row.status!=='refund_pending')return fail(409,'此记录已受理或无需退款受理。');
  const id=crypto.randomUUID(),stamp=Date.now();
  await a.db.batch([
   a.stmt(`INSERT OR IGNORE INTO payment_late_attempts SELECT ?,id,'ack',?,?,?,? FROM payment_late_cases WHERE id=? AND status='refund_pending'`,id,actor,data.requestId,note,stamp,row.id),
   a.stmt(`UPDATE payment_late_cases SET status='refund_processing',updated=? WHERE id=? AND status='refund_pending' AND EXISTS(SELECT 1 FROM payment_late_attempts WHERE id=?)`,stamp,row.id,id),
   a.stmt(`INSERT INTO audits SELECT ?,?,'payment_late.ack',?, 'accepted; no real refund',? WHERE EXISTS(SELECT 1 FROM payment_late_attempts WHERE id=?)`,crypto.randomUUID(),actor,row.id,stamp,id),
  ]);
  const action=await a.one('SELECT * FROM payment_late_attempts WHERE actor=? AND request_id=?',actor,data.requestId);
  if(!action||action.case_id!==row.id||action.note!==note)return fail(409,'该记录或受理编号已变化，请刷新后核对。');
  return {item:adminItem(await find(row.id))};
 }
 if(detail&&!detail[2]&&method==='GET'){
  const row=await find(detail[1]),history=await a.all('SELECT * FROM payment_late_attempts WHERE case_id=? ORDER BY created,id',row.id);
  return {item:adminItem(row),attempts:history.map((r:any)=>({id:r.id,caseId:r.case_id,action:r.action,actor:r.actor,requestId:r.request_id,note:r.note,created:r.created})),productionEnabled:false};
 }
 return fail(404,'找不到此迟到付款后台功能。');
}
