'use strict';
// Actual Cloud commerce + new after-sales in isolated SQLite-backed D1 batches, not a real payment provider.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto'),{DatabaseSync}=require('node:sqlite');
const ROOT=path.resolve(__dirname,'..'),cloud=path.join(ROOT,'04_研发源码/app/cloud'),ts=require(path.join(cloud,'node_modules/typescript'));
const previous=require.extensions['.ts'];require.extensions['.ts']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText,f);
if(!globalThis.crypto)globalThis.crypto=crypto.webcrypto;
let externalRequests=0;globalThis.fetch=async()=>{externalRequests++;throw Error('No external provider in isolated after-sales test');};
const {commerceRoute,initCommerce}=require(path.join(cloud,'lib/commerce-api.ts')),{initMembership}=require(path.join(cloud,'lib/membership-lifecycle.ts')),{initCommission}=require(path.join(cloud,'lib/commission-api.ts')),{afterSalesRoute,initAfterSales,legacyAfterSalesAllowed}=require(path.join(cloud,'lib/after-sales.ts'));
class StatusError extends Error{constructor(status,message){super(message);this.status=status;}}const fail=(s,m)=>{throw new StatusError(s,m);};
const db=new DatabaseSync(':memory:');db.exec("PRAGMA foreign_keys=ON;CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT NOT NULL);CREATE TABLE users(id TEXT PRIMARY KEY,role TEXT);CREATE TABLE contents(kind TEXT,id TEXT,data TEXT,status TEXT,position INTEGER,updated INTEGER);CREATE TABLE media(id TEXT PRIMARY KEY,mime TEXT,owner TEXT);CREATE TABLE audits(id TEXT PRIMARY KEY,actor TEXT,action TEXT,target TEXT,detail TEXT,created INTEGER);");
for(const [id,role]of [['buyer','user'],['other','user'],['admin','admin'],['operator','operator']])db.prepare('INSERT INTO users VALUES(?,?)').run(id,role);
function adapter(id='buyer',role='user'){
 const a={user:id?{id,role}:null,url:new URL('https://isolated.example.test'),payload:{},beforeBatch:null,
 require(roles){if(!this.user)fail(401,'login');if(roles&&!roles.includes(this.user.role))fail(403,'role');return this.user;},
 async body(){return structuredClone(this.payload);},async rate(){},async one(sql,...args){return db.prepare(sql).get(...args)||null;},async all(sql,...args){return db.prepare(sql).all(...args);},async run(sql,...args){const r=db.prepare(sql).run(...args);return {meta:{changes:Number(r.changes)}};},stmt(sql,...args){return {sql,args};},
 async setting(key){const r=await this.one('SELECT data FROM settings WHERE key=?',key);return r?JSON.parse(r.data):{};},async audit(action,target,detail){await this.run('INSERT INTO audits VALUES(?,?,?,?,?,?)',crypto.randomUUID(),this.user.id,action,target,detail,Date.now());}};
 a.db={async batch(ops){if(a.beforeBatch){const hook=a.beforeBatch;a.beforeBatch=null;await hook(ops);}db.exec('BEGIN IMMEDIATE');try{const out=ops.map(({sql,args})=>{const r=db.prepare(sql).run(...args);return {meta:{changes:Number(r.changes)}};});db.exec('COMMIT');return out;}catch(e){db.exec('ROLLBACK');throw e;}}};return a;
}
const buyer=adapter(),other=adapter('other'),admin=adapter('admin','admin'),operator=adapter('operator','operator'),anon=adapter(null);
async function call(a,path,data=undefined,method=data===undefined?'GET':'POST',status=200){
 a.url=new URL(path,'https://isolated.example.test');a.payload=data;let value,actual=200;
 try{value=path.includes('/after-sales')?await afterSalesRoute(a,a.url.pathname,method,fail):await commerceRoute(a,a.url.pathname,method,fail);}catch(e){if(!e.status)throw e;actual=e.status;value={error:e.message};}
 if(status===null)return {status:actual,data:value};assert.equal(actual,status,path+': '+JSON.stringify(value));return value;
}
const scalar=(sql,...args)=>Object.values(db.prepare(sql).get(...args))[0],key=()=>crypto.randomUUID(),clone=x=>JSON.parse(JSON.stringify(x));
function moneyHash(){const data=Object.fromEntries(['commerce_orders','commerce_order_items','commerce_payment_events','commerce_entitlements'].map(t=>[t,db.prepare('SELECT * FROM '+t+' ORDER BY 1').all()]));return crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex');}
async function product(type='physical',stock=20){
 const contentId=type==='digital'?'course-'+key():'';if(contentId)db.prepare('INSERT INTO contents VALUES(?,?,?,?,?,?)').run('courses',contentId,JSON.stringify({title:'Synthetic free course',access:'free',status:'published'}),'published',0,0);
 return (await call(admin,'/api/admin/commerce/products',{title:'Synthetic sandbox product',description:'Not a production product',type,sku:'AS-'+key(),priceMinor:1000,currency:'USD',stock,environment:'sandbox',status:'published',shippingMinor:type==='physical'?10:0,taxMinor:2,shippingCountries:type==='physical'?['US']:[],contentId})).item;
}
async function order(p,quantity=3,paid=true,dispatched=true,who=buyer){
 const payload={requestId:key(),environment:'sandbox',items:[{skuId:p.skuId,quantity}]};
 if(p.type==='physical')payload.shippingAddress={name:'Synthetic recipient',address:'Synthetic street',city:'City',country:'US',postalCode:'00000'};
 let o=await call(who,'/api/commerce/orders',payload);
 if(paid)o=await call(who,'/api/commerce/orders/'+o.id+'/sandbox-pay',{requestId:key()});
 if(paid&&dispatched&&p.type==='physical')o=await call(admin,'/api/admin/commerce/orders/'+o.id+'/fulfill',{carrier:'sandbox-carrier',trackingNumber:'TEST-'+key(),status:'delivered'});
 return o;
}
const request=(o,q=1,type='return',requestId=key())=>({requestId,environment:'sandbox',orderId:o.id,type,reason:'Synthetic reason',items:[{itemId:o.items[0].id,quantity:q}]});
const makeCase=(o,q=1,type='return',requestId=key(),status=200,who=buyer)=>call(who,'/api/after-sales/cases',request(o,q,type,requestId),'POST',status);
const decide=(c,accept=true,requestId=key(),status=200)=>call(admin,'/api/admin/after-sales/cases/'+c.id+'/decision',{requestId,version:c.version,decision:accept?'accept':'reject',reason:'Synthetic '+(accept?'accept':'reject')+' reason'},'POST',status);
const ship=(c,status=200)=>call(buyer,'/api/after-sales/cases/'+c.id+'/return-shipping',{requestId:key(),version:c.version,carrier:'sandbox-return-carrier',trackingNumber:'RETURN-'+key()},'POST',status);
const receiptBody=(c,q=1,restock=0,requestId=key())=>({requestId,receiptReference:'RECEIPT-'+requestId,version:c.version,items:[{caseItemId:c.items[0].id,receivedQuantity:q,restockQuantity:restock,condition:restock?'resalable':'damaged'}],note:'Synthetic human receipt, not a carrier verification'});
const inspect=(c,q=1,restock=0,requestId=key(),status=200)=>call(admin,'/api/admin/after-sales/cases/'+c.id+'/inspect',receiptBody(c,q,restock,requestId),'POST',status);
const checks=[];async function check(name,fn){try{await fn();checks.push({name,pass:true});console.log('PASS '+name);}catch(e){checks.push({name,pass:false,error:e.stack||e.message});console.log('FAIL '+name+': '+e.message);}}
(async()=>{
 await initCommerce(admin);await initMembership(admin);await initCommission(admin);await initAfterSales(admin);
 let p,o,c,stock;
 await check('default production closed; anonymous and ordinary management denied',async()=>{
  const d=await call(buyer,'/api/after-sales/config');assert.equal(d.settings.sandboxEnabled,false);assert.equal(d.productionEnabled,false);
  await call(anon,'/api/after-sales/cases',undefined,'GET',401);await call(buyer,'/api/admin/after-sales',undefined,'GET',403);await call(operator,'/api/admin/after-sales',undefined,'GET',403);
 });
 await call(admin,'/api/admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
 await check('explicit sandbox rule required and production/null enable rejected',async()=>{
  for(const body of [{sandboxEnabled:true,productionEnabled:true,ruleVersion:'test'},{sandboxEnabled:true,productionEnabled:null,ruleVersion:'test'},{sandboxEnabled:true,productionEnabled:false,ruleVersion:null}])await call(admin,'/api/admin/after-sales/settings',body,'PATCH',400);
  await call(admin,'/api/admin/after-sales/settings',{sandboxEnabled:true,productionEnabled:false,ruleVersion:'sandbox-fixture-v1'},'PATCH');
 });
 p=await product();o=await order(p);stock=scalar('SELECT stock FROM commerce_skus WHERE id=?',p.skuId);
 await check('real unified paid order yields per-item immutable case; replay and mismatch',async()=>{
  const id=key(),first=await makeCase(o,2,'return',id);c=first.item;const again=await makeCase(o,2,'return',id);assert(again.replayed);assert.equal(again.item.id,c.id);
  await makeCase(o,1,'return',id,409);assert.equal(c.items[0].snapshot.priceMinor,1000);assert.equal(c.ruleVersion,'sandbox-fixture-v1');
 });
 await check('unpaid, unshipped and cross-account order rejected',async()=>{
  await makeCase(await order(await product(),1,false,false),1,'return',key(),409);
  await makeCase(await order(await product(),1,true,false),1,'return',key(),409);
  await call(other,'/api/after-sales/cases/'+c.id,undefined,'GET',404);await makeCase(o,1,'return',key(),404,other);
 });
 await check('allocation and strict quantities/JSON/production',async()=>{
  await makeCase(o,2,'return',key(),409);
  for(const q of [-1,0,1.5,true,'1',100])await makeCase(o,q,'return',key(),400);
  await call(buyer,'/api/after-sales/cases',[],'POST',400);await call(buyer,'/api/after-sales/cases',{...request(o),environment:'production'},'POST',403);
 });
 await check('accept/reject version and replay are independent of funds and stock',async()=>{
  const money=moneyHash(),id=key(),old=c;c=(await decide(old,true,id)).item;assert((await decide(old,true,id)).replayed);
  await decide(old,false,id,409);await decide(old,true,key(),409);assert.equal(c.status,'accepted');assert.equal(c.money.caseRefundConfirmed,false);
  assert.equal(moneyHash(),money);assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',p.skuId),stock);
 });
 await check('receipt requires owner logistics and normal user cannot inspect',async()=>{
  await inspect(c,1,0,key(),409);await call(buyer,'/api/admin/after-sales/cases/'+c.id+'/inspect',receiptBody(c),'POST',403);
  await call(other,'/api/after-sales/cases/'+c.id+'/return-shipping',{requestId:key(),version:c.version,carrier:'x',trackingNumber:'x'},'POST',404);
 });
 c=(await ship(c)).item;
 await check('partial receipt with zero approved restock leaves financial tables intact',async()=>{
  const before=moneyHash();c=(await inspect(c,1,0)).item;assert.equal(c.status,'partially_received');assert.equal(c.items[0].restockedQuantity,0);assert.equal(c.shipments[0].carrierVerified,false);
  assert.equal(scalar("SELECT count(*) FROM commerce_inventory_events WHERE order_id=? AND reason='after_sales_received_no_restock'",o.id),1);
  assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',p.skuId),stock);assert.equal(moneyHash(),before);
 });
 await check('final receipt applies one event; idempotent replay never repeats stock',async()=>{
  const before=moneyHash(),old=c,id=key();c=(await inspect(old,1,1,id)).item;assert((await inspect(old,1,1,id)).replayed);assert.equal(c.status,'received');assert.equal(c.items[0].restockedQuantity,1);
  await inspect(old,1,0,id,409);await inspect(c,1,1,key(),409);
  assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',p.skuId),stock+1);assert.equal(moneyHash(),before);
 });
 await check('digital refund review denies logistics/warehouse and does not refund',async()=>{
  const op=await order(await product('digital'),2);await makeCase(op,1,'return',key(),409);
  let cd=(await makeCase(op,1,'refund-only')).item;cd=(await decide(cd)).item;await ship(cd,409);await inspect(cd,1,0,key(),409);
  assert.equal(cd.money.caseRefundConfirmed,false);assert.equal(cd.money.orderPaymentStatus,'paid');
 });
 await check('rejection releases allocation for a distinct new request',async()=>{
  const op=await order(await product(),2),first=(await makeCase(op,2)).item;assert.equal((await decide(first,false)).item.status,'rejected');
  assert.notEqual((await makeCase(op,2)).item.id,first.id);
 });
 await check('original pre-dispatch refund stock is deducted from new return capacity',async()=>{
  const pp=await product('physical',10);let op=await order(pp,3,true,false);const line=op.items[0].id;
  await call(admin,'/api/admin/commerce/orders/'+op.id+'/refund',{requestId:key(),items:[{itemId:line,quantity:1}]});
  op=await call(admin,'/api/admin/commerce/orders/'+op.id+'/fulfill',{carrier:'test',trackingNumber:'TRACK',status:'shipped'});await makeCase(op,3,'return',key(),409);
  let cc=(await makeCase(op,2)).item;cc=(await decide(cc)).item;cc=(await ship(cc)).item;await inspect(cc,2,2);
  assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',pp.skuId),10);assert.equal(scalar('SELECT sum(quantity_delta) FROM commerce_inventory_events WHERE item_id=? AND quantity_delta>0',line),3);
 });
 await check('actual commerce post-dispatch refund does not double stock with receipt',async()=>{
  const pp=await product('physical',10),op=await order(pp,3),body={requestId:key(),items:[{itemId:op.items[0].id,quantity:3}]};
  let cc=(await makeCase(op,3)).item;cc=(await decide(cc)).item;cc=(await ship(cc)).item;await call(admin,'/api/admin/commerce/orders/'+op.id+'/refund',body);
  assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',pp.skuId),7);cc=(await inspect(cc,3,2)).item;await call(admin,'/api/admin/commerce/orders/'+op.id+'/refund',body);
  assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',pp.skuId),9);assert.equal(cc.money.orderPaymentStatus,'refunded');assert.equal(cc.money.caseRefundLinked,false);assert.equal(cc.money.actualFundsMoved,false);
 });
 await check('D1 concurrent different case requests cannot over-allocate',async()=>{
  const op=await order(await product(),3),a1=adapter(),a2=adapter();
  const run=async a=>{try{return await call(a,'/api/after-sales/cases',request(op,2));}catch(e){assert.match(e.message,/售后数量|409/);return null;}};
  const results=await Promise.all([run(a1),run(a2)]);assert.equal(results.filter(Boolean).length,1);assert.equal(scalar('SELECT count(*) FROM after_sales_cases WHERE order_id=?',op.id),1);
 });
 await check('D1 concurrent same request converges to one case even after initial stale read',async()=>{
  const op=await order(await product(),2),body=request(op,2),values=await Promise.all([call(adapter(),'/api/after-sales/cases',body),call(adapter(),'/api/after-sales/cases',body)]);
  assert.equal(new Set(values.map(x=>x.item.id)).size,1);assert.equal(scalar('SELECT count(*) FROM after_sales_cases WHERE order_id=?',op.id),1);
 });
 await check('D1 same receipt request concurrently applies once',async()=>{
  const pp=await product(),op=await order(pp,1);let cc=(await makeCase(op,1)).item;cc=(await decide(cc)).item;cc=(await ship(cc)).item;
  const body=receiptBody(cc,1,1),a1=adapter('admin','admin'),a2=adapter('admin','admin'),result=await Promise.all([call(a1,'/api/admin/after-sales/cases/'+cc.id+'/inspect',body),call(a2,'/api/admin/after-sales/cases/'+cc.id+'/inspect',body)]);
  assert.equal(result[0].item.id,result[1].item.id);assert.equal(scalar("SELECT count(*) FROM commerce_inventory_events WHERE order_id=? AND reason='after_sales_return_restock'",op.id),1);
 });
 await check('disabled-between-validation-and-batch aborts all allocation writes',async()=>{
  const op=await order(await product(),1),a=adapter();a.beforeBatch=async ops=>{if(ops.some(x=>x.sql.startsWith('INSERT INTO after_sales_cases')))db.prepare("UPDATE after_sales_config SET data=? WHERE key='settings'").run(JSON.stringify({sandboxEnabled:false,productionEnabled:false,ruleVersion:'sandbox-fixture-v1'}));};
  await call(a,'/api/after-sales/cases',request(op), 'POST',409);assert.equal(scalar('SELECT count(*) FROM after_sales_cases WHERE order_id=?',op.id),0);
  await call(admin,'/api/admin/after-sales/settings',{sandboxEnabled:true,productionEnabled:false,ruleVersion:'sandbox-fixture-v1'},'PATCH');
 });
 await check('legacy pending request blocks ambiguous per-item import; guard hook is truthful',async()=>{
  const op=await order(await product(),2);await call(buyer,'/api/commerce/orders/'+op.id+'/aftersale',{requestId:key(),reason:'legacy',quantity:1});await makeCase(op,1,'return',key(),409);
  assert.equal(await legacyAfterSalesAllowed(buyer,'buyer',o.id),false);
 });
 await check('eligibility reports claimed original units and is account isolated',async()=>{
  const value=await call(buyer,'/api/after-sales/orders/'+o.id);assert.equal(value.items[0].claimedQuantity,2);assert.equal(value.items[0].availableReturnQuantity,1);
  await call(other,'/api/after-sales/orders/'+o.id,undefined,'GET',404);
 });
 await check('different request ID cannot reuse a physical receipt reference',async()=>{
  const pp=await product(),op=await order(pp,2);let cc=(await makeCase(op,2)).item;cc=(await decide(cc)).item;cc=(await ship(cc)).item;const rid=key();
  cc=(await inspect(cc,1,1,rid)).item;const before=scalar('SELECT stock FROM commerce_skus WHERE id=?',pp.skuId),actions=scalar('SELECT count(*) FROM after_sales_actions');
  const body={...receiptBody(cc,1,1),receiptReference:'RECEIPT-'+rid};await call(admin,'/api/admin/after-sales/cases/'+cc.id+'/inspect',body,'POST',409);
  assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',pp.skuId),before);assert.equal(scalar('SELECT count(*) FROM after_sales_actions'),actions);
 });
 await check('same original order receipt across two cases is atomic and cannot be reused under another request',async()=>{
   const p=await product('physical',5),o=await order(p,2),cases=[];
   for(let n=0;n<2;n++)cases.push((await ship((await decide((await makeCase(o)).item)).item)).item);
   const reference='SAME-ORDER-'+key(),body=c=>({...receiptBody(c,1,1),receiptReference:reference});
   const money=moneyHash(),stock=scalar('SELECT stock FROM commerce_skus WHERE id=?',p.skuId);
   const results=await Promise.all(cases.map(c=>call(adapter('admin','admin'),'/api/admin/after-sales/cases/'+c.id+'/inspect',body(c),'POST',null)));
   assert.deepEqual(results.map(r=>r.status).sort(),[200,409]);assert.equal(moneyHash(),money);assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',p.skuId),stock+1);
   assert.equal(scalar('SELECT count(*) FROM after_sales_inspections i JOIN after_sales_cases c ON c.id=i.case_id WHERE c.order_id=?',o.id),1);
   assert.equal(scalar("SELECT count(*) FROM commerce_inventory_events WHERE order_id=? AND reason='after_sales_return_restock'",o.id),1);
   const loser=cases[results.findIndex(r=>r.status===409)];await call(admin,'/api/admin/after-sales/cases/'+loser.id+'/inspect',body(loser),'POST',409);assert.equal(scalar('SELECT stock FROM commerce_skus WHERE id=?',p.skuId),stock+1);
  });
  await check('D1 batch rechecks role downgrade and rolls back before warehouse action',async()=>{
  const op=await order(await product(),1),cc=(await makeCase(op,1)).item,a=adapter('admin','admin');
  a.beforeBatch=async ops=>{if(ops.some(x=>x.sql.startsWith('INSERT INTO after_sales_actions')))db.prepare("UPDATE users SET role='operator' WHERE id='admin'").run();};
  try{await call(a,'/api/admin/after-sales/cases/'+cc.id+'/decision',{requestId:key(),version:cc.version,decision:'accept',reason:'cached actor'},'POST',403);assert.equal(scalar("SELECT count(*) FROM after_sales_actions WHERE case_id=? AND kind='accept'",cc.id),0);}
  finally{db.prepare("UPDATE users SET role='admin' WHERE id='admin'").run();}
 });
 await check('disabled module remains readable and does not mutate original money',async()=>{
  const newOrder=await order(await product(),1),before=moneyHash(),actionCount=scalar('SELECT count(*) FROM after_sales_actions');
  await call(admin,'/api/admin/after-sales/settings',{sandboxEnabled:false,productionEnabled:false,ruleVersion:'sandbox-fixture-v1'},'PATCH');
  assert.equal((await call(buyer,'/api/after-sales/cases/'+c.id)).id,c.id);await makeCase(newOrder,1,'return',key(),503);
  assert.equal(moneyHash(),before);assert.equal(scalar('SELECT count(*) FROM after_sales_actions'),actionCount);
 });
 const report={at:new Date().toISOString(),pass:checks.every(x=>x.pass),passed:checks.filter(x=>x.pass).length,failed:checks.filter(x=>!x.pass).length,tests:checks,realProviderRequests:externalRequests,productionEnabled:false,actualFundsMoved:false,scope:'real Commerce TS methods and independent new after-sales; synthetic in-memory SQLite D1 atomic batches'};
 const file=path.join(__dirname,'负责人优化建议-售后Cloud内存专项.json');let runs=[];if(fs.existsSync(file)){const old=JSON.parse(fs.readFileSync(file,'utf8'));runs=old.runs||[old.latest||old];}runs.push(report);fs.writeFileSync(file,JSON.stringify({latest:report,runs},null,2)+'\n');console.log(JSON.stringify({pass:report.pass,passed:report.passed,failed:report.failed,realProviderRequests:externalRequests}));if(!report.pass||externalRequests)process.exitCode=1;
})().catch(e=>{console.error(e.stack);process.exitCode=1;}).finally(()=>{if(previous)require.extensions['.ts']=previous;else delete require.extensions['.ts'];db.close();});

