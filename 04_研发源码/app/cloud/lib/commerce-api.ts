import {initDigitalEntitlements,captureDigitalStatements,digitalOrderTerms,digitalCatalogReadiness} from './digital-entitlements';
// Sandbox-only commerce. No production payment or production media permission is issued.
import {initMembership,MembershipLifecycle} from './membership-lifecycle';
import {commissionSnapshotStatements,syncCommissionOrder} from './commission-api';
import {legacyAfterSalesInsertGuard} from './after-sales';
import {trustedSettlementApi} from './account-write-guard';
import {latePaymentSummary} from './payment-late';
import {initPaymentRouting,PaymentRouting,decorateRoutingCatalog,routingStorageError} from './payment-routing';
const DDL: string[] = ["CREATE TABLE IF NOT EXISTS commerce_config(key TEXT PRIMARY KEY,data TEXT NOT NULL)", "INSERT OR IGNORE INTO commerce_config VALUES('settings','{\"sandboxEnabled\":false,\"productionEnabled\":false}')", "CREATE TABLE IF NOT EXISTS commerce_products(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL,type TEXT NOT NULL CHECK(type IN ('digital','physical','membership')),environment TEXT NOT NULL CHECK(environment IN ('sandbox','production')),status TEXT NOT NULL CHECK(status IN ('draft','published','archived')),version INTEGER NOT NULL,content_id TEXT NOT NULL,shipping_countries TEXT NOT NULL,shipping_minor INTEGER NOT NULL CHECK(shipping_minor>=0),tax_minor INTEGER NOT NULL CHECK(tax_minor>=0),mutation_id TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,data TEXT NOT NULL DEFAULT '{}')", "CREATE TABLE IF NOT EXISTS commerce_skus(id TEXT PRIMARY KEY,product_id TEXT NOT NULL UNIQUE REFERENCES commerce_products(id),sku TEXT NOT NULL,environment TEXT NOT NULL,price_minor INTEGER NOT NULL CHECK(price_minor>=0),currency TEXT NOT NULL,stock INTEGER NOT NULL CHECK(stock>=0),reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved>=0 AND reserved<=stock),version INTEGER NOT NULL,UNIQUE(environment,sku))", "CREATE TABLE IF NOT EXISTS commerce_prices(id TEXT PRIMARY KEY,sku_id TEXT NOT NULL REFERENCES commerce_skus(id),version INTEGER NOT NULL,price_minor INTEGER NOT NULL,currency TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(sku_id,version))", "CREATE TABLE IF NOT EXISTS commerce_carts(owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),data TEXT NOT NULL,updated INTEGER NOT NULL,PRIMARY KEY(owner,environment))", "CREATE TABLE IF NOT EXISTS commerce_orders(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,status TEXT NOT NULL,payment_status TEXT NOT NULL,fulfillment_status TEXT NOT NULL,aftersale_status TEXT NOT NULL,currency TEXT NOT NULL,subtotal_minor INTEGER NOT NULL,shipping_minor INTEGER NOT NULL,tax_minor INTEGER NOT NULL,total_minor INTEGER NOT NULL,refunded_minor INTEGER NOT NULL DEFAULT 0,shipping_address TEXT NOT NULL,tracking TEXT NOT NULL DEFAULT '{}',reserved_until INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(owner,environment,request_id))", "CREATE INDEX IF NOT EXISTS commerce_orders_owner ON commerce_orders(owner,environment,created)", "CREATE TABLE IF NOT EXISTS commerce_order_items(id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES commerce_orders(id),sku_id TEXT NOT NULL REFERENCES commerce_skus(id),product_id TEXT NOT NULL,title TEXT NOT NULL,type TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>0),price_minor INTEGER NOT NULL,currency TEXT NOT NULL,unit_shipping_minor INTEGER NOT NULL,unit_tax_minor INTEGER NOT NULL,content_id TEXT NOT NULL,price_version INTEGER NOT NULL,refunded_quantity INTEGER NOT NULL DEFAULT 0 CHECK(refunded_quantity>=0 AND refunded_quantity<=quantity),snapshot_data TEXT NOT NULL DEFAULT '{}',UNIQUE(order_id,sku_id))", "CREATE TABLE IF NOT EXISTS commerce_reservations(order_id TEXT NOT NULL REFERENCES commerce_orders(id),sku_id TEXT NOT NULL REFERENCES commerce_skus(id),quantity INTEGER NOT NULL CHECK(quantity>0),state TEXT NOT NULL CHECK(state IN ('held','consumed','released')),PRIMARY KEY(order_id,sku_id))", "CREATE TABLE IF NOT EXISTS commerce_payment_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL REFERENCES commerce_orders(id),request_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('sandbox_pay','refund')),fingerprint TEXT NOT NULL,amount_minor INTEGER NOT NULL,currency TEXT NOT NULL,items TEXT NOT NULL,status TEXT NOT NULL CHECK(status='applied'),created INTEGER NOT NULL,UNIQUE(owner,environment,kind,request_id))", "CREATE UNIQUE INDEX IF NOT EXISTS commerce_one_payment ON commerce_payment_events(order_id,kind) WHERE kind='sandbox_pay'", "CREATE TABLE IF NOT EXISTS commerce_entitlements(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL REFERENCES commerce_orders(id),item_id TEXT NOT NULL UNIQUE REFERENCES commerce_order_items(id),content_id TEXT NOT NULL,type TEXT NOT NULL,quantity INTEGER NOT NULL,remaining INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','revoked')),created INTEGER NOT NULL,updated INTEGER NOT NULL)", "CREATE TABLE IF NOT EXISTS commerce_aftersale_requests(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL REFERENCES commerce_orders(id),request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,reason TEXT NOT NULL,quantity INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(owner,environment,request_id))", "CREATE TABLE IF NOT EXISTS commerce_inventory_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL,item_id TEXT NOT NULL,sku_id TEXT NOT NULL,quantity_delta INTEGER NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL)", "CREATE TRIGGER IF NOT EXISTS commerce_reserve_check BEFORE INSERT ON commerce_reservations WHEN NEW.state='held' BEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_skus s JOIN commerce_products p ON p.id=s.product_id JOIN commerce_orders o ON o.id=NEW.order_id JOIN commerce_order_items i ON i.order_id=o.id AND i.sku_id=s.id WHERE s.id=NEW.sku_id AND s.environment=o.environment AND p.environment=o.environment AND p.status='published' AND o.payment_status='unpaid' AND s.stock-s.reserved>=NEW.quantity AND s.version=i.price_version) THEN RAISE(ABORT,'commerce_out_of_stock') END;\nEND", "CREATE TRIGGER IF NOT EXISTS commerce_reserve_hold AFTER INSERT ON commerce_reservations WHEN NEW.state='held' BEGIN UPDATE commerce_skus SET reserved=reserved+NEW.quantity WHERE id=NEW.sku_id; END", "CREATE TRIGGER IF NOT EXISTS commerce_reserve_release AFTER UPDATE OF state ON commerce_reservations WHEN OLD.state='held' AND NEW.state='released' BEGIN UPDATE commerce_skus SET reserved=reserved-NEW.quantity WHERE id=NEW.sku_id; END", "CREATE TRIGGER IF NOT EXISTS commerce_reserve_consume AFTER UPDATE OF state ON commerce_reservations WHEN OLD.state='held' AND NEW.state='consumed' BEGIN UPDATE commerce_skus SET reserved=reserved-NEW.quantity,stock=stock-NEW.quantity WHERE id=NEW.sku_id; END", "CREATE TRIGGER IF NOT EXISTS commerce_order_closed AFTER UPDATE OF status ON commerce_orders WHEN OLD.status='awaiting_payment' AND NEW.status='closed' BEGIN UPDATE commerce_reservations SET state='released' WHERE order_id=NEW.id AND state='held'; END", "CREATE TRIGGER IF NOT EXISTS commerce_order_paid AFTER UPDATE OF payment_status ON commerce_orders WHEN OLD.payment_status='unpaid' AND NEW.payment_status='paid' BEGIN\n UPDATE commerce_reservations SET state='consumed' WHERE order_id=NEW.id AND state='held';\n INSERT INTO commerce_entitlements SELECT 'sandbox:'||i.id,NEW.owner,'sandbox',NEW.id,i.id,i.content_id,i.type,i.quantity,i.quantity,'active',NEW.updated,NEW.updated FROM commerce_order_items i WHERE i.order_id=NEW.id AND i.type IN ('digital','membership');\nEND", "CREATE TRIGGER IF NOT EXISTS commerce_refund_check BEFORE INSERT ON commerce_payment_events WHEN NEW.kind='refund' BEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=NEW.order_id AND o.owner=NEW.owner AND o.environment=NEW.environment AND o.payment_status IN ('paid','partially_refunded')) THEN RAISE(ABORT,'commerce_refund_state') END;\n SELECT CASE WHEN json_array_length(NEW.items)<1 OR EXISTS(SELECT 1 FROM json_each(NEW.items) j LEFT JOIN commerce_order_items i ON i.id=json_extract(j.value,'$.itemId') AND i.order_id=NEW.order_id WHERE i.id IS NULL OR json_type(j.value,'$.quantity')!='integer' OR json_extract(j.value,'$.quantity')<1 OR json_extract(j.value,'$.quantity')>i.quantity-i.refunded_quantity) OR (SELECT count(*) FROM json_each(NEW.items))!=(SELECT count(DISTINCT json_extract(value,'$.itemId')) FROM json_each(NEW.items)) THEN RAISE(ABORT,'commerce_refund_quantity') END;\n SELECT CASE WHEN NEW.amount_minor!=(SELECT sum(json_extract(j.value,'$.quantity')*(i.price_minor+i.unit_shipping_minor+i.unit_tax_minor)) FROM json_each(NEW.items) j JOIN commerce_order_items i ON i.id=json_extract(j.value,'$.itemId') AND i.order_id=NEW.order_id) THEN RAISE(ABORT,'commerce_refund_amount') END;\nEND", "CREATE TRIGGER IF NOT EXISTS commerce_refund_apply AFTER INSERT ON commerce_payment_events WHEN NEW.kind='refund' BEGIN\n UPDATE commerce_order_items SET refunded_quantity=refunded_quantity+(SELECT json_extract(j.value,'$.quantity') FROM json_each(NEW.items) j WHERE json_extract(j.value,'$.itemId')=commerce_order_items.id) WHERE order_id=NEW.order_id AND id IN (SELECT json_extract(value,'$.itemId') FROM json_each(NEW.items));\n UPDATE commerce_orders SET refunded_minor=refunded_minor+NEW.amount_minor,payment_status=CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=NEW.order_id AND quantity>refunded_quantity) THEN 'refunded' ELSE 'partially_refunded' END,aftersale_status=CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=NEW.order_id AND quantity>refunded_quantity) THEN 'refunded' ELSE 'partially_refunded' END,status=CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=NEW.order_id AND quantity>refunded_quantity) THEN 'refunded' ELSE 'partially_refunded' END,updated=NEW.created WHERE id=NEW.order_id;\n UPDATE commerce_aftersale_requests SET status=CASE WHEN (SELECT payment_status FROM commerce_orders WHERE id=NEW.order_id)='refunded' THEN 'resolved' ELSE 'processing' END,updated=NEW.created WHERE order_id=NEW.order_id AND status IN ('pending','processing');\nEND", "CREATE TRIGGER IF NOT EXISTS commerce_item_refunded AFTER UPDATE OF refunded_quantity ON commerce_order_items WHEN NEW.refunded_quantity>OLD.refunded_quantity BEGIN\n UPDATE commerce_skus SET stock=stock+NEW.refunded_quantity-OLD.refunded_quantity WHERE id=NEW.sku_id AND (NEW.type!='physical' OR EXISTS(SELECT 1 FROM commerce_orders WHERE id=NEW.order_id AND fulfillment_status NOT IN ('shipped','delivered')));\n INSERT INTO commerce_inventory_events SELECT 'refund:'||NEW.id||':'||NEW.refunded_quantity,o.owner,'sandbox',NEW.order_id,NEW.id,NEW.sku_id,CASE WHEN NEW.type='physical' AND o.fulfillment_status IN ('shipped','delivered') THEN 0 ELSE NEW.refunded_quantity-OLD.refunded_quantity END,CASE WHEN NEW.type='physical' AND o.fulfillment_status IN ('shipped','delivered') THEN 'refund_after_dispatch_no_restock' ELSE 'refund_restock' END,(SELECT max(created) FROM commerce_payment_events WHERE order_id=NEW.order_id) FROM commerce_orders o WHERE o.id=NEW.order_id;\n UPDATE commerce_entitlements SET remaining=NEW.quantity-NEW.refunded_quantity,status=CASE WHEN NEW.quantity=NEW.refunded_quantity THEN 'revoked' ELSE 'active' END,updated=(SELECT max(created) FROM commerce_payment_events WHERE order_id=NEW.order_id) WHERE item_id=NEW.id AND environment='sandbox';\nEND;"];
const HOLD_MS=900000, MAX_MINOR=1000000000;
const legacySkuTable=DDL.find(sql=>sql.startsWith('CREATE TABLE IF NOT EXISTS commerce_skus('))!;
const skuTable=legacySkuTable.replace('product_id TEXT NOT NULL UNIQUE REFERENCES','product_id TEXT NOT NULL REFERENCES');
const variantDDL=[
 'CREATE INDEX IF NOT EXISTS commerce_skus_product ON commerce_skus(product_id)',
 'CREATE TABLE IF NOT EXISTS commerce_sku_variants(sku_id TEXT PRIMARY KEY REFERENCES commerce_skus(id),options TEXT NOT NULL,active INTEGER NOT NULL CHECK(active IN (0,1)))',
];
const skuColumns="s.id sku_id,s.sku,s.price_minor,s.currency,s.stock,s.reserved,s.version price_version,coalesce(v.options,'[]') sku_options,coalesce(v.active,1) sku_active";
const skuJoin='JOIN commerce_skus s ON s.product_id=p.id LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id';
const CURRENCIES=new Set(['CNY','USD','EUR','GBP','HKD','TWD','JPY','KRW','CAD','AUD','NZD','SGD','CHF','THB','MYR','IDR','VND','PHP','INR','AED','SAR','BRL','MXN','ZAR','BHD','KWD','OMR','JOD','TND']);
const uid=()=>crypto.randomUUID(), now=()=>Date.now(), iso=(n:number)=>new Date(n).toISOString();
const canonical=(x:any):any=>Array.isArray(x)?x.map(canonical):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;
const dump=(x:any)=>JSON.stringify(canonical(x));
async function fingerprint(x:any){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(dump(x)))),v=>v.toString(16).padStart(2,'0')).join('');}

export async function initCommerce(a:any){
 if(!await a.one("SELECT 1 FROM settings WHERE key='commerce_schema_v1'")){
  await a.db.batch([...DDL.map(sql=>a.stmt(sql===legacySkuTable?skuTable:sql)),a.stmt("INSERT OR IGNORE INTO settings VALUES ('commerce_schema_v1','true')")]);
 }
 if(await a.one("SELECT 1 FROM settings WHERE key='commerce_sku_variants_v1'"))return;
 const row=await a.one("SELECT sql FROM sqlite_master WHERE name='commerce_skus'");
 const migrate=row.sql.includes('product_id TEXT NOT NULL UNIQUE REFERENCES')?[
  'PRAGMA defer_foreign_keys=ON',
  'CREATE TABLE commerce_skus_copy AS SELECT * FROM commerce_skus',
  'DROP TABLE commerce_skus',
  skuTable,
  'INSERT INTO commerce_skus SELECT * FROM commerce_skus_copy',
  'DROP TABLE commerce_skus_copy',
  'CREATE TABLE commerce_sku_fk_check(count INTEGER CHECK(count=0))',
  "INSERT INTO commerce_sku_fk_check SELECT count(*) FROM pragma_foreign_key_check WHERE parent='commerce_skus'",
  'DROP TABLE commerce_sku_fk_check',
  'PRAGMA defer_foreign_keys=OFF',
 ]:[];
 const claim="INSERT INTO settings VALUES ('commerce_sku_variants_v1','true')";
 try{await a.db.batch([claim,...migrate,...variantDDL].map(sql=>a.stmt(sql)));}
 catch(error){if(!await a.one("SELECT 1 FROM settings WHERE key='commerce_sku_variants_v1'"))throw error;}
}

export async function commerceMediaPublic(a:any,reference:string){
 return !!await a.one("SELECT 1 FROM commerce_products p WHERE p.status='published' AND json_extract(p.data,'$.imageUrl')=? AND (p.environment='production' OR (p.environment='sandbox' AND EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1)))",reference);
}

export async function commerceRoute(a:any,p:string,m:string,fail:(n:number,s:string)=>never){
 if(!(p.startsWith('/api/commerce/')||p==='/api/admin/commerce'||p.startsWith('/api/admin/commerce/')||p==='/api/admin/payment-routing'||p.startsWith('/api/admin/payment-routing/')))return undefined;
 await initCommerce(a);await initMembership(a);await initDigitalEntitlements(a);await initPaymentRouting(a);
 const str=(v:any,max:number,min=0)=>{if(typeof v!=='string'||v.trim().length<min||v.trim().length>max)fail(400,'文本格式或长度不符合要求。');return v.trim();};
 const integer=(v:any,min=0,max=MAX_MINOR)=>{if(!Number.isSafeInteger(v)||v<min||v>max)fail(400,'金额、数量与库存必须为允许范围内的整数。');return v;};
 const environment=(v:any)=>{if(!['sandbox','production'].includes(v))fail(400,'无效交易环境。');return v;};
 const user=()=>a.require().id;
 const settings=async()=>{const r=await a.one("SELECT data FROM commerce_config WHERE key='settings'"),v=r?JSON.parse(r.data):{};return {sandboxEnabled:v.sandboxEnabled===true,productionEnabled:false};};
 const enabled=async(env:string)=>{if(env!=='sandbox')fail(403,'正式交易尚未启用；此模块只允许沙箱测试，不会真实扣款。');if(!(await settings()).sandboxEnabled)fail(503,'沙箱交易尚未由管理员开启。');};
 const batch=async(st:any[])=>{try{return await a.db.batch(st)}catch(e:any){if(/payment_routing_/.test(String(e?.message||'')+' '+String(e?.cause?.message||'')))routingStorageError(e);if(/commerce_|membership_|digital_|UNIQUE|CHECK constraint/i.test(String(e?.message||e?.cause?.message||'')))fail(409,'商品、库存或订单已变化，请刷新后重试。');throw e;}};
 const expire=async()=>a.run("UPDATE commerce_orders SET status='closed',payment_status='expired',updated=? WHERE status='awaiting_payment' AND payment_status='unpaid' AND reserved_until<=?",now(),now());
 const product=(r:any)=>({...JSON.parse(r.data),id:r.id,productId:r.id,title:r.title,description:r.description,type:r.type,environment:r.environment,status:r.status,version:r.version,contentId:r.content_id,shippingCountries:JSON.parse(r.shipping_countries),shippingMinor:r.shipping_minor,taxMinor:r.tax_minor,sandboxOnly:r.environment==='sandbox'});
 const variant=(r:any)=>({skuId:r.sku_id,sku:r.sku,options:JSON.parse(r.sku_options),active:!!r.sku_active,priceVersion:r.price_version,priceMinor:r.price_minor,currency:r.currency,stock:r.stock,reserved:r.reserved,availableStock:r.stock-r.reserved,purchasable:r.environment==='sandbox'&&r.status==='published'&&!!r.sku_active&&r.stock>r.reserved});
 const products=async(env?:string,published=false)=>{
  const conditions:string[]=[],args:string[]=[];
  if(env){conditions.push('p.environment=?');args.push(env);}
  if(published)conditions.push("p.status='published' AND coalesce(v.active,1)=1");
  const rows=await a.all(`SELECT p.*,${skuColumns} FROM commerce_products p ${skuJoin}`+(conditions.length?' WHERE '+conditions.join(' AND '):'')+' ORDER BY p.updated DESC,p.id,s.sku COLLATE BINARY',...args);
  const grouped=new Map<string,{base:ReturnType<typeof product>,variants:ReturnType<typeof variant>[]}>();
  for(const row of rows){
   if(!grouped.has(row.id))grouped.set(row.id,{base:product(row),variants:[]});
   grouped.get(row.id)!.variants.push(variant(row));
  }
  const digitalReady=await digitalCatalogReadiness(a,[...grouped.values()].filter(({base})=>base.type==='digital'&&base.environment==='sandbox').map(({base})=>base.contentId));
  for(const {base,variants} of grouped.values()){const access=digitalReady.get(base.contentId);if(base.type==='digital'&&base.environment==='sandbox'&&access?.marked&&!access.ready)for(const sku of variants)sku.purchasable=false;}
  return [...grouped.values()].map(({base,variants})=>({...base,...(variants.find(sku=>sku.active)||variants[0]),variants,purchasable:variants.some(sku=>sku.purchasable)}));
 };
 const ownOrder=async(id:string,admin=false)=>{const r=admin?await a.one('SELECT * FROM commerce_orders WHERE id=?',id):await a.one('SELECT * FROM commerce_orders WHERE id=? AND owner=?',id,user());if(!r)fail(404,'未找到订单。');return r;};
 const commissionProcessing=async(r:any):Promise<any>=>{
  try{const result=await syncCommissionOrder(['paid','partially_refunded','refunded'].includes(r.payment_status)?await trustedSettlementApi(a,'order',r.id,r.owner):a,r.id),rows=await a.all('SELECT status FROM commission_ledger WHERE order_id=?',r.id);if(!result.synced)return {status:result.reason||'unavailable',retryAvailable:false,sandboxOnly:true,actualPaid:false};return {status:!['paid','partially_refunded','refunded'].includes(r.payment_status)?'awaiting_payment':rows.some((x:any)=>x.status==='waiting_facts')?'waiting_facts':'synchronized',ledgerItemCount:rows.length,retryAvailable:false,sandboxOnly:true,actualPaid:false};}
  catch{try{await a.audit('commission.sync.pending',r.id,'统一交易事实保留；派生佣金可刷新重试，不重复付款或退款。');}catch{}return {status:'sync_pending',retryAvailable:true,retryAction:'refresh-order',sandboxOnly:true,actualPaid:false};}
 };
 const order=async(r:any)=>{if(!r)fail(404,'未找到订单。');const digitalTerms=await digitalOrderTerms(a,r.id,r.owner);const lines=await a.all('SELECT * FROM commerce_order_items WHERE order_id=? ORDER BY id',r.id),events=await a.all('SELECT id,kind,request_id,amount_minor,currency,status,created FROM commerce_payment_events WHERE order_id=? ORDER BY created,id',r.id);let membershipProcessing:any=null;if(lines.some((i:any)=>i.type==='membership')){const snapshots=await a.all('SELECT item_id,subscription_id FROM membership_order_snapshots WHERE order_id=? AND owner=?',r.id,r.owner),complete=snapshots.length===lines.filter((i:any)=>i.type==='membership').length,linked=complete&&snapshots.every((v:any)=>v.subscription_id),paid=['paid','partially_refunded','refunded'].includes(r.payment_status);membershipProcessing={environment:'sandbox',status:linked?'linked':!complete?'unavailable':paid?'pending':'awaiting_payment',retryAvailable:!!(complete&&paid&&!linked&&r.payment_status!=='refunded'),subscriptionIds:[...new Set<string>(snapshots.map((v:any)=>v.subscription_id).filter(Boolean))].sort(),grantsProductionAccess:false};}return {paymentRoute:await routing.routeSummary(r.id,r.owner),paymentRouteUsability:await routing.paymentUsability(r.id,r.owner),latePayment:await latePaymentSummary(a,r.id,r.owner),commissionProcessing:await commissionProcessing(r),membershipProcessing,id:r.id,ownerId:r.owner,aftersaleRequests:(await a.all('SELECT id,request_id,reason,quantity,status,created,updated FROM commerce_aftersale_requests WHERE order_id=? ORDER BY created,id',r.id)).map((q:any)=>({id:q.id,requestId:q.request_id,reason:q.reason,quantity:q.quantity,status:q.status,environment:'sandbox',createdAt:iso(q.created),updatedAt:iso(q.updated)})),environment:r.environment,sandboxOnly:true,grantsProductionAccess:false,requestId:r.request_id,status:r.status,paymentStatus:r.payment_status,fulfillmentStatus:r.fulfillment_status,aftersaleStatus:r.aftersale_status,currency:r.currency,subtotalMinor:r.subtotal_minor,shippingMinor:r.shipping_minor,taxMinor:r.tax_minor,totalMinor:r.total_minor,refundedMinor:r.refunded_minor,shippingAddress:JSON.parse(r.shipping_address),inventoryEvents:(await a.all('SELECT * FROM commerce_inventory_events WHERE order_id=? ORDER BY created,id',r.id)).map((v:any)=>({id:v.id,skuId:v.sku_id,itemId:v.item_id,quantityDelta:v.quantity_delta,reason:v.reason,environment:'sandbox',createdAt:iso(v.created)})),tracking:JSON.parse(r.tracking),reservedUntil:iso(r.reserved_until),createdAt:iso(r.created),updatedAt:iso(r.updated),items:lines.map((i:any)=>({...JSON.parse(i.snapshot_data||'{}'),id:i.id,itemId:i.id,skuId:i.sku_id,productId:i.product_id,title:i.title,type:i.type,quantity:i.quantity,priceMinor:i.price_minor,currency:i.currency,unitShippingMinor:i.unit_shipping_minor,unitTaxMinor:i.unit_tax_minor,totalMinor:i.quantity*(i.price_minor+i.unit_shipping_minor+i.unit_tax_minor),contentId:i.content_id,priceVersion:i.price_version,refundedQuantity:i.refunded_quantity,digitalTerms:digitalTerms[i.id]||null})),events:events.map((e:any)=>({id:e.id,kind:e.kind,requestId:e.request_id,amountMinor:e.amount_minor,currency:e.currency,status:e.status,environment:'sandbox',createdAt:iso(e.created)}))};};
 const itemList=(v:any)=>{if(!Array.isArray(v)||v.length<1||v.length>30)fail(400,'请选择1至30种商品。');const result=v.map((x:any)=>{if(!x||typeof x!=='object'||Array.isArray(x))fail(400,'商品项目格式错误。');return {skuId:str(x.skuId,100,1),quantity:integer(x.quantity,1,99)};});if(new Set(result.map((x:any)=>x.skuId)).size!==result.length)fail(400,'同一SKU请合并数量。');return result.sort((x:any,y:any)=>x.skuId.localeCompare(y.skuId));};
 const address=(v:any)=>{if(v===undefined||v===null)return {};if(typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!['name','phone','country','region','city','address','postalCode'].includes(k)))fail(400,'收货信息格式错误。');const out:any=Object.fromEntries(Object.entries(v).map(([k,val])=>[k,str(val,k==='address'?400:100)]));if(out.country){out.country=out.country.toUpperCase();if(!/^[A-Z]{2}$/.test(out.country))fail(400,'配送国家须使用两位国家代码。');}return out;};
 const quote=async(requested:any[],addr:any,allowMixed=false)=>{const lines:any[]=[],currencies=new Set<string>(),physical=new Set<boolean>();for(const item of requested){const r=await a.one(`SELECT p.*,${skuColumns} FROM commerce_products p ${skuJoin} WHERE s.id=? AND s.environment='sandbox' AND p.environment='sandbox' AND p.status='published' AND coalesce(v.active,1)=1`,item.skuId);if(!r)fail(409,'商品已下架或不属于沙箱。');if(r.stock-r.reserved<item.quantity)fail(409,'商品库存不足。');currencies.add(r.currency);physical.add(r.type==='physical');if(r.type==='physical'){if(!addr.name||!addr.country||!addr.address)fail(400,'实物订单请填写收货人、国家与地址。');if(!JSON.parse(r.shipping_countries).includes(addr.country))fail(400,'该商品不配送至所选国家。');}lines.push({r,q:item.quantity});}if(!allowMixed&&physical.size>1)fail(409,'数字商品与实物商品须拆成独立订单。');if(!allowMixed&&currencies.size>1)fail(409,'不同币种的商品须拆成独立订单。');const subtotal=lines.reduce((s,x)=>s+x.r.price_minor*x.q,0),shipping=lines.reduce((s,x)=>s+(x.r.type==='physical'?x.r.shipping_minor:0)*x.q,0),tax=lines.reduce((s,x)=>s+x.r.tax_minor*x.q,0);integer(subtotal+shipping+tax);return {lines,currency:[...currencies][0],subtotal,shipping,tax};};
 const normalizeRoutingIntent=(d:any)=>{const semantic:any={environment:environment(d.environment??'production'),items:itemList(d.items),shippingAddress:address(d.shippingAddress)};if(d.membershipRenewalOf!==undefined&&d.membershipRenewalOf!==null)semantic.membershipRenewalOf=str(d.membershipRenewalOf,100,1);return semantic;};
 const routing=new PaymentRouting(a,{normalizeIntent:normalizeRoutingIntent,quoteNew:async(items,addr)=>{await enabled('sandbox');return quote(items,addr,true);}});
 const routed=await routing.route(p,m);if(routed!==undefined)return routed;
 // Existing commerce routes retain their expiry behavior; admission reads above are pure.
 await expire();
 const createOrder=async(d:any)=>{
  const env=environment(d.environment??'production'),owner=user(),requestId=str(d.requestId,128,1),requested=itemList(d.items),addr=address(d.shippingAddress),renewalOf=d.membershipRenewalOf===undefined||d.membershipRenewalOf===null?null:str(d.membershipRenewalOf,100,1);
  const semantic:any={environment:env,items:requested,shippingAddress:addr};if(renewalOf!==null)semantic.membershipRenewalOf=renewalOf;
  const token=await fingerprint(d.quoteId===undefined||d.quoteId===null?semantic:{...semantic,quoteId:d.quoteId});await enabled(env);
  const old=await a.one('SELECT * FROM commerce_orders WHERE owner=? AND environment=? AND request_id=?',owner,env,requestId);
  if(old){if(old.fingerprint!==token)fail(409,'幂等编号已用于不同的订单内容。');return order(old);}
  await routing.assertNewOrderRequest(d.quoteId);
  const {lines,currency,subtotal,shipping,tax}=await quote(requested,addr),hasMembership=lines.some((x:any)=>x.r.type==='membership'),lifecycle=hasMembership?new MembershipLifecycle(a,fail):null;
  if(renewalOf&&!hasMembership)fail(400,'续期关联只能用于会员订单。');
  const snapshots=lifecycle?await lifecycle.snapshotForCheckout(owner,requested,env,renewalOf||undefined):{},oid=uid(),stamp=now(),ops:any[]=[],preparedLines:any[]=[];
  const routePlan=await routing.prepareOrder(oid,owner,token,semantic,{lines,currency,subtotal,shipping,tax},d.quoteId,stamp);ops.push(...routePlan.beginStatements());
  ops.push(a.stmt('INSERT INTO commerce_orders(id,owner,environment,request_id,fingerprint,status,payment_status,fulfillment_status,aftersale_status,currency,subtotal_minor,shipping_minor,tax_minor,total_minor,refunded_minor,shipping_address,tracking,reserved_until,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',oid,owner,'sandbox',requestId,token,'awaiting_payment','unpaid','awaiting_payment','none',currency,subtotal,shipping,tax,subtotal+shipping+tax,0,dump(lines[0].r.type==='physical'?addr:{}),'{}',stamp+HOLD_MS,stamp,stamp));
  for(const {r,q} of lines){const itemId=uid();preparedLines.push({id:itemId,skuId:r.sku_id,type:r.type,quantity:q,contentId:r.content_id});ops.push(a.stmt('INSERT INTO commerce_order_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',itemId,oid,r.sku_id,r.id,r.title,r.type,q,r.price_minor,currency,r.type==='physical'?r.shipping_minor:0,r.tax_minor,r.content_id,r.price_version,0,dump({...JSON.parse(r.data),sku:r.sku,options:JSON.parse(r.sku_options)})));ops.push(a.stmt("INSERT INTO commerce_reservations VALUES(?,?,?,'held')",oid,r.sku_id,q));}
  if(lifecycle)ops.push(...lifecycle.captureStatements(owner,oid,preparedLines,snapshots));
  ops.push(...await captureDigitalStatements(a,owner,oid,preparedLines,stamp,fail));
  ops.push(...commissionSnapshotStatements(a,oid));
  ops.push(...routePlan.captureStatements(),...routePlan.finishStatements());await routePlan.revalidateEnv();
  try{await batch(ops);}catch(e){const replay=await a.one('SELECT * FROM commerce_orders WHERE owner=? AND environment=? AND request_id=?',owner,env,requestId);if(!replay)throw e;if(replay.fingerprint!==token)fail(409,'幂等编号已用于不同的订单内容。');return order(replay);}
  await a.audit('commerce.order.create',oid,'sandbox；无真实扣款');return order(await ownOrder(oid));
 };
 const completeMembership=async(oid:string,admin=false,refund=false):Promise<any>=>{
  const row=await ownOrder(oid,admin);let pending=false;
  if(await a.one("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='membership'",oid)){
   try{const settlement=await trustedSettlementApi(a,'order',oid,row.owner),lifecycle=new MembershipLifecycle(settlement,fail);if(refund)await lifecycle.onCommerceRefund(oid);else if(['paid','partially_refunded'].includes(row.payment_status))await lifecycle.onCommercePayment(oid);}
   catch{pending=true;try{await a.audit(refund?'membership.refund.sync_pending':'membership.activation.pending',oid,'统一沙箱付款/退款事实已提交；会员同步可重试，不声明真实渠道验单。');}catch{}}
  }
  const result:any=await order(await ownOrder(oid,admin));if(pending&&result.membershipProcessing)result.membershipProcessing={...result.membershipProcessing,syncPending:true,retryAction:refund?'membership/status':'membership/orders/'+oid+'/activate'};return result;
 };
 const pay=async(oid:string,d:any)=>{
  const owner=user(),requestId=str(d.requestId,128,1),token=await fingerprint({orderId:oid,kind:'sandbox_pay'});await enabled('sandbox');let r=await ownOrder(oid);
  const old=await a.one("SELECT * FROM commerce_payment_events WHERE owner=? AND environment='sandbox' AND kind='sandbox_pay' AND request_id=?",owner,requestId);
  if(old){if(old.fingerprint!==token)fail(409,'幂等编号已用于另一笔付款。');return completeMembership(oid);}
  if(['paid','partially_refunded','refunded'].includes(r.payment_status))return completeMembership(oid);
  if(r.status!=='awaiting_payment'||r.payment_status!=='unpaid')fail(409,'订单已关闭或不能付款。');
  if(await a.one("SELECT 1 FROM commerce_order_items i JOIN commerce_products p ON p.id=i.product_id WHERE i.order_id=? AND p.status!='published'",oid))fail(409,'订单商品已下架，不能付款。');
  if(await a.one("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='membership'",oid))await new MembershipLifecycle(a,fail).validateCommercePayment(oid);
  const stamp=now(),eid=uid(),physical=!!await a.one("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='physical'",oid),guard="EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=? AND o.owner=? AND o.status='awaiting_payment' AND o.payment_status='unpaid' AND o.reserved_until>?) AND NOT EXISTS(SELECT 1 FROM commerce_order_items i JOIN commerce_products p ON p.id=i.product_id WHERE i.order_id=? AND p.status!='published')";
  const routePlan=await routing.prepareManualPayment(oid,owner,eid);await routePlan.revalidateEnv();try{await batch([...routePlan.beginStatements(),a.stmt('INSERT INTO commerce_payment_events SELECT ?,?,?,?,?,?,?,?,?,?,?,? WHERE '+guard,eid,owner,'sandbox',oid,requestId,'sandbox_pay',token,r.total_minor,r.currency,'[]','applied',stamp,oid,owner,stamp,oid),a.stmt("UPDATE commerce_orders SET status=?,payment_status='paid',fulfillment_status=?,updated=? WHERE id=? AND payment_status='unpaid' AND EXISTS(SELECT 1 FROM commerce_payment_events WHERE id=?)",physical?'paid':'completed',physical?'awaiting_fulfillment':'fulfilled',stamp,oid,eid),a.stmt("DELETE FROM commerce_carts WHERE owner=? AND environment='sandbox' AND EXISTS(SELECT 1 FROM commerce_payment_events WHERE id=?)",owner,eid),...routePlan.finishStatements()]);}
  catch(e){const replay=await a.one("SELECT * FROM commerce_payment_events WHERE owner=? AND environment='sandbox' AND kind='sandbox_pay' AND request_id=?",owner,requestId);if(replay?.fingerprint===token)return completeMembership(oid);r=await ownOrder(oid);if(['paid','partially_refunded','refunded'].includes(r.payment_status))return completeMembership(oid);throw e;}
  r=await ownOrder(oid);if(r.payment_status==='unpaid')fail(409,'订单已过期或商品已变化，付款未完成。');await a.audit('commerce.sandbox.pay',oid,'仅沙箱权益，不授予正式媒体权限');return completeMembership(oid);
 };
 type VariantInput={id:string,sku:string,price:number,stock:number,active:boolean,options:{name:string,value:string}[],expectedStock:number|null};
 const validateVariants=(d:any,existing:Map<string,any>,type:string):VariantInput[]=>{
  let raw=d.variants;
  if(!Object.hasOwn(d,'variants')){
   if(existing.size>1||[...existing.values()].some(v=>JSON.parse(v.options).length))fail(409,'请使用规格编辑器保存此商品。');
   raw=[{skuId:existing.keys().next().value,sku:d.sku,priceMinor:d.priceMinor,stock:d.stock,active:true,options:[]}];
  }
  if(!Array.isArray(raw)||!raw.length||raw.length>20||(type==='membership'&&raw.length!==1))fail(400,'商品须保留1至20个SKU，会员商品只允许一个SKU。');
  const seenIds=new Set<string>(),seenCodes=new Set<string>(),seenOptions=new Set<string>();
  const result=raw.map((value:any)=>{
   if(!value||typeof value!=='object'||Array.isArray(value)||(Object.hasOwn(value,'active')&&typeof value.active!=='boolean'))fail(400,'SKU格式错误。');
   const sid=value.skuId,sku=str(value.sku,100,1);
   if(sid!=null&&(typeof sid!=='string'||!existing.has(sid)||seenIds.has(sid)))fail(400,'规格编号无效、重复或不属于当前商品。');
   const entries=Object.hasOwn(value,'options')?value.options:[];
   if(!Array.isArray(entries)||entries.length>4||entries.some(o=>!o||typeof o!=='object'||Object.keys(o).length!==2||!Object.hasOwn(o,'name')||!Object.hasOwn(o,'value')))fail(400,'每个SKU最多可填写4组规格名称与取值。');
   const options=entries.map(o=>({name:str(o.name,40,1),value:str(o.value,80,1)}));
   const names=new Set(options.map(o=>o.name.toLowerCase()));
   const signature=dump(Object.fromEntries(options.map(o=>[o.name.toLowerCase(),o.value.toLowerCase()])));
   const active=value.active??true;
   if((type==='membership'&&options.length)||names.size!==options.length||seenCodes.has(sku)||(active&&seenOptions.has(signature)))fail(400,'SKU编码、规格名称或在售规格组合重复，会员商品无需规格。');
   if(sid!=null)seenIds.add(sid);
   seenCodes.add(sku);
   if(active)seenOptions.add(signature);
   return {id:sid??uid(),sku,price:integer(value.priceMinor),stock:integer(value.stock),options,active,
    expectedStock:Object.hasOwn(value,'expectedStock')?integer(value.expectedStock):null};
  });
  if(seenIds.size!==existing.size)fail(409,'已有SKU须保留，停用时请将其设为下架。');
  return result;
 };
 const saveProduct=async(d:any)=>{
  const env=environment(d.environment??'production'),title=str(d.title,120,1),description=str(d.description??'',5000),type=d.type,status=d.status??'draft';
  const currency=str(d.currency,3,3).toUpperCase(),shipping=integer(d.shippingMinor??0),tax=integer(d.taxMinor??0);
  const countries=d.shippingCountries??[],content=str(d.contentId??'',100);
  if(!['digital','physical','membership'].includes(type)||!['draft','published','archived'].includes(status))fail(400,'无效商品类型或状态；预约尚未启用。');
  if(!CURRENCIES.has(currency))fail(400,'该币种尚未列入沙箱支持范围。');
  if(type!=='physical'&&shipping)fail(400,'非实物商品不能收取运费。');
  if(!Array.isArray(countries)||countries.length>250||countries.some(c=>typeof c!=='string'||!/^[A-Z]{2}$/.test(c)))fail(400,'配送国家须为两位大写国家代码数组。');
  if(type==='physical'&&status==='published'&&!countries.length)fail(400,'上架实物须配置配送国家。');
  if(type==='digital'&&status==='published'&&(!content||!await a.one("SELECT 1 FROM contents WHERE kind='courses' AND id=? AND status='published'",content)))fail(400,'数字作品须绑定已发布智慧馆内容。');
  const pid=str(d.id||uid(),100,1),stamp=now(),mutation=uid(),old=await a.one('SELECT * FROM commerce_products WHERE id=?',pid);
  if(old){
   if(integer(d.version,1)!==old.version)fail(409,'商品已更新，请刷新。');
   if(old.environment!==env||old.type!==type)fail(409,'已有商品不能更换交易环境或类型。');
  }else if(d.version!=null&&d.version!==0)fail(409,'新商品不能使用已有版本。');
  const skuRows=await a.all("SELECT s.*,coalesce(v.options,'[]') options FROM commerce_skus s LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id WHERE s.product_id=?",pid);
  const existing=new Map<string,any>(skuRows.map((r:any)=>[r.id,r]));
  const variants=validateVariants(d,existing,type);
  if(status==='published'&&!variants.some(v=>v.active))fail(400,'上架商品须至少保留一个在售SKU。');
  const extra=old?JSON.parse(old.data):{},oldImage=extra.imageUrl||'';
  for(const k of ['refundPolicy','titleZh','titleEn','titleHant','titleBo','descriptionZh','descriptionEn','descriptionHant','descriptionBo','imageUrl']){
   if(k in d)extra[k]=str(d[k],k.startsWith('description')?5000:k==='refundPolicy'?2000:k==='imageUrl'?1500:120);
  }
  if(extra.imageUrl){
   if(/^\/api\/media\/[a-f0-9-]{36}$/.test(extra.imageUrl)){
    const asset=await a.one('SELECT mime,owner FROM media WHERE id=?',extra.imageUrl.split('/').pop());
    if(!asset||!asset.mime.startsWith('image/'))fail(400,'商品封面须为已上传图片。');
    if(extra.imageUrl!==oldImage&&asset.owner!==user())fail(403,'新增商品封面只能引用当前管理员上传的图片。');
   }else{
    let url:URL;
    try{url=new URL(extra.imageUrl);}catch{fail(400,'商品封面须为HTTPS或本项目上传图片。');}
    if(url!.protocol!=='https:'||!url!.hostname||url!.username||url!.password)fail(400,'商品封面须为HTTPS或本项目上传图片。');
   }
  }
  const version=old?old.version+1:1,ops:any[]=[];
  const countryList=dump([...new Set(countries)].sort()), claim='EXISTS(SELECT 1 FROM commerce_products WHERE id=? AND mutation_id=?)';
  if(old){
   const guard="NOT EXISTS(SELECT 1 FROM commerce_skus s JOIN json_each(?) v ON s.id=json_extract(v.value,'$.id') WHERE s.reserved>json_extract(v.value,'$.stock') OR (json_extract(v.value,'$.expectedStock') IS NOT NULL AND s.stock!=json_extract(v.value,'$.expectedStock')) OR (s.reserved>0 AND (s.currency!=? OR commerce_products.content_id!=?)))";
   ops.push(a.stmt('UPDATE commerce_products SET title=?,description=?,status=?,version=?,content_id=?,shipping_countries=?,shipping_minor=?,tax_minor=?,mutation_id=?,updated=?,data=? WHERE id=? AND version=? AND '+guard,
    title,description,status,version,content,countryList,shipping,tax,mutation,stamp,dump(extra),pid,old.version,dump(variants),currency,content));
  }else{
   ops.push(a.stmt('INSERT INTO commerce_products(id,title,description,type,environment,status,version,content_id,shipping_countries,shipping_minor,tax_minor,mutation_id,created,updated,data) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
    pid,title,description,type,env,status,version,content,countryList,shipping,tax,mutation,stamp,stamp,dump(extra)));
  }
  for(const v of variants){
   if(existing.has(v.id)&&existing.get(v.id).sku!==v.sku)ops.push(a.stmt('UPDATE commerce_skus SET sku=? WHERE id=? AND '+claim,'swap:'+uid(),v.id,pid,mutation));
  }
  for(const v of variants){
   ops.push(a.stmt('INSERT INTO commerce_skus SELECT ?,?,?,?,?,?,?,?,? WHERE '+claim+' ON CONFLICT(id) DO UPDATE SET sku=excluded.sku,price_minor=excluded.price_minor,currency=excluded.currency,stock=excluded.stock,version=excluded.version',
    v.id,pid,v.sku,env,v.price,currency,v.stock,0,version,pid,mutation));
   ops.push(a.stmt('INSERT INTO commerce_sku_variants SELECT ?,?,? WHERE '+claim+' ON CONFLICT(sku_id) DO UPDATE SET options=excluded.options,active=excluded.active',
    v.id,dump(v.options),Number(v.active),pid,mutation));
   ops.push(a.stmt('INSERT INTO commerce_prices SELECT ?,?,?,?,?,? WHERE '+claim,uid(),v.id,version,v.price,currency,stamp,pid,mutation));
  }
  const results=await batch(ops);
  if(!results[0].meta.changes)fail(409,'商品或库存已更新，请刷新。');
  await a.audit('commerce.product.save',pid,env+'；版本'+version);
  return {item:(await products(env)).find(v=>v.id===pid),environment:env,productionEnabled:false};
 };
 const refund=async(oid:string,d:any)=>{const requestId=str(d.requestId,128,1);if(!Array.isArray(d.items)||d.items.length<1||d.items.length>30)fail(400,'请指定退款订单项及数量。');const items=d.items.map((x:any)=>{if(!x||typeof x!=='object'||Array.isArray(x))fail(400,'退款项目格式错误。');return {itemId:str(x.itemId,100,1),quantity:integer(x.quantity,1,99)};}).sort((x:any,y:any)=>x.itemId.localeCompare(y.itemId));if(new Set(items.map((x:any)=>x.itemId)).size!==items.length)fail(400,'退款项目不可重复。');const token=await fingerprint({orderId:oid,items});await enabled('sandbox');const r=await ownOrder(oid,true),old=await a.one("SELECT * FROM commerce_payment_events WHERE owner=? AND environment='sandbox' AND kind='refund' AND request_id=?",r.owner,requestId);if(old){if(old.fingerprint!==token)fail(409,'退款幂等编号已用于不同请求。');return completeMembership(oid,true,true);}if(!['paid','partially_refunded'].includes(r.payment_status))fail(409,'订单当前不能退款。');let amount=0;for(const item of items){const i=await a.one('SELECT * FROM commerce_order_items WHERE id=? AND order_id=?',item.itemId,oid);if(!i||item.quantity>i.quantity-i.refunded_quantity)fail(409,'退款数量超过该订单项可退数量。');amount+=item.quantity*(i.price_minor+i.unit_shipping_minor+i.unit_tax_minor);}try{await batch([a.stmt('INSERT INTO commerce_payment_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',uid(),r.owner,'sandbox',oid,requestId,'refund',token,amount,r.currency,dump(items),'applied',now())]);}catch(e){const replay=await a.one("SELECT * FROM commerce_payment_events WHERE owner=? AND environment='sandbox' AND kind='refund' AND request_id=?",r.owner,requestId);if(replay?.fingerprint===token)return completeMembership(oid,true,true);if(replay)fail(409,'退款幂等编号已用于不同请求。');throw e;}await a.audit('commerce.sandbox.refund',oid,'按项退款；无真实资金流动');return completeMembership(oid,true,true);};
 const aftersale=async(oid:string,d:any)=>{const owner=user(),requestId=str(d.requestId,128,1),reason=str(d.reason,2000,1),quantity=integer(d.quantity??1,1,2970),token=await fingerprint({orderId:oid,reason,quantity});await enabled('sandbox');const r=await ownOrder(oid),old=await a.one("SELECT * FROM commerce_aftersale_requests WHERE owner=? AND environment='sandbox' AND request_id=?",owner,requestId);if(old){if(old.fingerprint!==token)fail(409,'售后幂等编号已用于不同请求。');return order(r);}const legacyGuard=await legacyAfterSalesInsertGuard(a,owner,oid);const stamp=now(),id=uid();let out;try{out=await batch([a.stmt("INSERT INTO commerce_aftersale_requests SELECT ?,?,?,?,?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM commerce_orders WHERE id=? AND owner=? AND payment_status IN ('paid','partially_refunded')) AND ?<=(SELECT coalesce(sum(quantity-refunded_quantity),0) FROM commerce_order_items WHERE order_id=?)"+legacyGuard.sql,id,owner,'sandbox',oid,requestId,token,reason,quantity,'pending',stamp,stamp,oid,owner,quantity,oid,...legacyGuard.bindings),a.stmt("UPDATE commerce_orders SET aftersale_status='requested',updated=? WHERE id=? AND EXISTS(SELECT 1 FROM commerce_aftersale_requests WHERE id=?)",stamp,oid,id)]);}catch(e){const replay=await a.one("SELECT * FROM commerce_aftersale_requests WHERE owner=? AND environment='sandbox' AND request_id=?",owner,requestId);if(replay?.fingerprint===token)return order(await ownOrder(oid));if(replay)fail(409,'售后幂等编号已用于不同请求。');throw e;}if(!out[0].meta.changes)fail(409,'订单状态或可售后数量不符合要求。');await a.audit('commerce.aftersale.request',oid,'sandbox；等待人工处理，不自动退款');return order(await ownOrder(oid));};
 if(p.startsWith('/api/admin/')){
  a.require(['admin']);
  const detail=/^\/api\/admin\/commerce\/orders\/([^/]+)$/.exec(p);
  if(detail&&m==='GET')return order(await ownOrder(detail[1],true));
  if(p==='/api/admin/commerce'&&m==='GET')return {settings:await settings(),products:await products(),orders:await Promise.all((await a.all('SELECT * FROM commerce_orders ORDER BY created DESC LIMIT 200')).map(order)),environment:'sandbox',productionEnabled:false};
  if(p==='/api/admin/commerce/settings'&&m==='PATCH'){const d=await a.body();if(d.productionEnabled!==undefined&&d.productionEnabled!==false||typeof d.sandboxEnabled!=='boolean')fail(400,'正式交易禁止启用，sandboxEnabled须为布尔值。');const s={sandboxEnabled:d.sandboxEnabled,productionEnabled:false};await a.run("UPDATE commerce_config SET data=? WHERE key='settings'",dump(s));await a.audit('commerce.settings','sandbox','沙箱开关变更');return {settings:s};}
  if(p==='/api/admin/commerce/products'&&m==='POST')return saveProduct(await a.body());
  const match=/^\/api\/admin\/commerce\/orders\/([^/]+)\/(fulfill|refund)$/.exec(p);
  if(match&&m==='POST'){const d=await a.body(),oid=match[1];if(match[2]==='refund')return refund(oid,d);const tracking={trackingNumber:str(d.trackingNumber,100,1),carrier:str(d.carrier??'',100)},state=d.status??'shipped';if(!['shipped','delivered'].includes(state))fail(400,'无效履约状态。');await enabled('sandbox');const r=await ownOrder(oid,true);if(!['paid','partially_refunded'].includes(r.payment_status)||!await a.one("SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='physical' AND quantity>refunded_quantity",oid))fail(409,'仅已付款且尚有未退实物的订单可发货。');if(r.fulfillment_status==='delivered'&&state!=='delivered')fail(409,'已送达订单不能倒退履约状态。');const out=await a.run("UPDATE commerce_orders SET tracking=?,fulfillment_status=?,status=?,updated=? WHERE id=? AND payment_status IN ('paid','partially_refunded') AND (?='delivered' OR fulfillment_status!='delivered') AND EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=? AND type='physical' AND quantity>refunded_quantity)",dump(tracking),state,state==='delivered'?'completed':'fulfilling',now(),oid,state,oid);if(!out.meta.changes)fail(409,'订单已变化，请刷新。');await a.audit('commerce.fulfill',oid,'sandbox；'+state);return order(await ownOrder(oid,true));}
  fail(405,'不支持的交易后台操作。');
 }
 const env=environment(a.url.searchParams.get('environment')||'production');
 if(p==='/api/commerce/catalog'&&m==='GET'){const s=await settings(),items=env==='production'||s.sandboxEnabled?await products(env,true):[];for(const item of items)item.purchasable=item.purchasable&&s.sandboxEnabled;await decorateRoutingCatalog(a,items);const cfg=await routing.config();return {items,settings:s,paymentRouting:{mode:cfg.mode,policyRevision:cfg.revision,context:await routing.context(),productionEnabled:false},environment:env,sandboxOnly:env==='sandbox',productionEnabled:false};}
 user();if(['POST','PATCH'].includes(m))await a.rate('commerce:'+user(),30);
 if(p==='/api/commerce/cart'&&['GET','PATCH'].includes(m)){
  const d=m==='PATCH'?await a.body():{},scope=environment(d.environment??env),owner=user();
  if(m==='PATCH'){
   await enabled(scope);
   const items=Array.isArray(d.items)&&d.items.length===0?[]:itemList(d.items);
   const guard=`NOT EXISTS(SELECT 1 FROM json_each(?) i
    WHERE json_extract(i.value,'$.quantity')>coalesce((SELECT json_extract(old.value,'$.quantity') FROM commerce_carts c,json_each(c.data) old WHERE c.owner=? AND c.environment=? AND json_extract(old.value,'$.skuId')=json_extract(i.value,'$.skuId')),0)
    AND NOT EXISTS(SELECT 1 FROM commerce_products p ${skuJoin} WHERE s.id=json_extract(i.value,'$.skuId') AND s.environment=? AND p.environment=? AND p.status='published' AND coalesce(v.active,1)=1 AND s.stock-s.reserved>=json_extract(i.value,'$.quantity')))`;
   const data=dump(items);
   const result=await a.run('INSERT INTO commerce_carts SELECT ?,?,?,? WHERE '+guard+' ON CONFLICT(owner,environment) DO UPDATE SET data=excluded.data,updated=excluded.updated',owner,scope,data,now(),data,owner,scope,scope,scope);
   if(!result.meta.changes)fail(409,'购物车规格已下架或库存不足。');
  }
  const row=await a.one('SELECT data FROM commerce_carts WHERE owner=? AND environment=?',owner,scope);
  return {items:row?JSON.parse(row.data):[],environment:scope,settings:await settings()};
 }
 if(p==='/api/commerce/orders'&&m==='POST')return createOrder(await a.body());
 if(p==='/api/commerce/orders'&&m==='GET')return {items:await Promise.all((await a.all('SELECT * FROM commerce_orders WHERE owner=? AND environment=? ORDER BY created DESC LIMIT 200',user(),env)).map(order)),environment:env};
 if(p==='/api/commerce/entitlements'&&m==='GET'){const rows=await a.all('SELECT * FROM commerce_entitlements WHERE owner=? AND environment=? ORDER BY created DESC',user(),env);return {items:rows.map((r:any)=>({id:r.id,environment:'sandbox',sandboxOnly:true,grantsProductionAccess:false,orderId:r.order_id,itemId:r.item_id,contentId:r.content_id,type:r.type,quantity:r.quantity,remaining:r.remaining,status:r.status})),environment:env,grantsProductionAccess:false};}
 const match=/^\/api\/commerce\/orders\/([^/]+)(\/(?:sandbox-pay|aftersale))?$/.exec(p);
 if(match){if(match[2]==='/aftersale'&&m==='POST')return aftersale(match[1],await a.body());if(match[2]==='/sandbox-pay'&&m==='POST')return pay(match[1],await a.body());if(!match[2]&&m==='GET')return order(await ownOrder(match[1]));}
 fail(405,'不支持的交易操作。');
}
