// Actual local PAY08 HTTP/browser tests. No production channel or provider is contacted.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {makeHarness}=require('./负责人优化建议-交易测试工具.cjs');
const ROOT=path.resolve(__dirname,'..');
const args=Object.fromEntries(process.argv.slice(2).filter(x=>x.startsWith('--')).map(x=>{const n=x.indexOf('=');return [x.slice(2,n<0?undefined:n),n<0?true:x.slice(n+1)];}));
const target=args.target||'python',uuid=()=>crypto.randomUUID();
const secret=process.env.EW_PAYMENT_CALLBACK_QA_SECRET||crypto.randomBytes(32).toString('hex');
const controlToken=process.env.CALLBACK_TEST_TOKEN||crypto.randomBytes(32).toString('hex');
const ownedDb=path.join(__dirname,'负责人优化建议-支付回调隔离-'+Date.now().toString(36)+'-'+uuid()+'.sqlite3');
const python=process.env.EW_PYTHON||path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
const env={...process.env,EW_PAYMENT_CALLBACK_SANDBOX_ENABLED:'1',EW_PAYMENT_CALLBACK_SANDBOX_SECRET_REF:'EW_PAYMENT_CALLBACK_QA_SECRET',EW_PAYMENT_CALLBACK_QA_SECRET:secret,CALLBACK_TEST_TOKEN:controlToken};
let child,h,childBase;
async function launch(resume=false,port=0){
 const launchArgs=['-B',path.join(__dirname,'负责人优化建议-支付回调Python测试服务.py'),'--db',ownedDb,'--port',String(port),...(resume?['--resume']:[])];
 child=spawn(python,launchArgs,{cwd:ROOT,env,windowsHide:true,stdio:['ignore','pipe','pipe']});
 return new Promise((resolve,reject)=>{
  let output='';const timer=setTimeout(()=>reject(Error('PAY08 isolated service start timed out')),25000);
  child.stdout.on('data',d=>{output+=d;const match=/APP: (http:\/\/127\.0\.0\.1:\d+)/.exec(output);if(match){clearTimeout(timer);resolve(match[1]);}});
  child.stderr.on('data',d=>{output+=d;});
  child.once('error',error=>{clearTimeout(timer);reject(error);});
  child.once('exit',code=>{clearTimeout(timer);reject(Error('PAY08 isolated service exited '+code+': '+output.slice(-1000)));});
 });
}
async function stop(){if(child&&child.exitCode===null){const ended=new Promise(resolve=>child.once('exit',resolve));child.kill();await ended;}}

async function run(){
 assert(args.base,'Use the owned late-compensation launcher; baseline wrappers are not started by this derived suite');
 if(target==='cloud'){
  assert(args.base,'Cloud test requires an existing fresh local fixture --base');
  assert(process.env.EW_PAYMENT_CALLBACK_QA_SECRET&&process.env.CALLBACK_TEST_TOKEN,'Cloud fixture credentials must be supplied only in process environment');
 }else if(!args.base)childBase=await launch();
 const base=args.base||childBase;
 h=makeHarness([...process.argv.slice(2),'--base='+base,'--module=负责人优化建议-迟到补偿回调兼容',...(args.report?[]:['--report=负责人优化建议-迟到补偿回调兼容-'+target+'.json'])]);
 await h.start();
 h.report.compatibilityBaseline={path:'06_验证与后续工作/负责人优化建议-支付回调专项.cjs',sha256:h.sha(fs.readFileSync(path.join(__dirname,'负责人优化建议-支付回调专项.cjs'))),replacement:'Only the old expired→manual assertion is replaced by the late-payment positive stock/refund and trusted-query cases. Signature, ownership, manual closure and all other assertions remain.'};
 const lateFiles=['04_研发源码/app/r4/backend/payment_late.py','04_研发源码/app/cloud/lib/payment-late.ts','04_研发源码/app/r4/payment-late-ui.js','04_研发源码/app/r4/payment-late-admin.js'];h.report.lateSources=Object.fromEntries(lateFiles.map(name=>[name,h.sha(fs.readFileSync(path.join(ROOT,name)))]));
 if(childBase)h.report.ownedDatabase=path.relative(ROOT,ownedDb).split(path.sep).join('/');
 h.report.scope='PAY08 compatibility on the final late-compensation build. The old expired→manual assertion is replaced by separately verified positive late-stock and refund-pending cases. All signature, ownership, duplicate, retry, manual-close and UI assertions remain; no real provider or production payment.';
 h.report.coverage={http:true,ui:!args['http-only'],realPayments:false,production:false,signature:'sandbox-hmac-fixture-only',automaticScheduling:false,processRestart:!!childBase};
 const moduleSources=[...lateFiles,'04_研发源码/app/r4/backend/payment_callbacks.py','04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/payment-callbacks.ts','04_研发源码/app/cloud/lib/eastern-api.ts','04_研发源码/app/r4/payment-callback-admin.js','04_研发源码/app/r4/build.py','04_研发源码/app/cloud/prepare.py'];
 const identity=()=>Object.fromEntries(moduleSources.filter(name=>fs.existsSync(path.join(ROOT,name))).map(name=>[name,h.sha(fs.readFileSync(path.join(ROOT,name)))]));
 h.report.callbackSources=identity();
 const sourceIdentity=h.report.callbackSources;
 const {admin,user,other,anonymous}=await h.seed();
 const {api,check}=h,queue='admin/payment-callbacks';
 const control=async(data,expected=200,token=controlToken)=>{
  const response=await anonymous.post(base+'/__callback-test/control',{headers:{'X-Callback-Test':token},data});
  assert.equal(response.status(),expected,'Isolated QA control');return response.json();
 };
 const get=async id=>(await api(admin,queue+'/'+id)).data;
 const snapshot=async(orderId='',receiptId='')=>control({action:'snapshot',orderId,receiptId});
 const consume=async(limit=10)=>(await api(admin,queue+'/process',{limit})).data;
 const callback=async(body,expected=202,options={})=>{
  const raw=options.raw??JSON.stringify(body),stamp=options.timestamp??String(Math.floor(Date.now()/1000));
  const signature=options.signature??crypto.createHmac('sha256',secret).update(stamp+'.').update(raw).digest('hex');
  const response=await anonymous.post(base+(options.route||'/api/payment-callbacks/sandbox'),{
   data:Buffer.from(raw),headers:{'Content-Type':options.contentType||'application/json','X-EW-Callback-Timestamp':stamp,'X-EW-Callback-Signature':signature},
  });
  let data;try{data=await response.json();}catch{data={};}
  h.report.traffic.push({method:'POST',path:options.route||'/api/payment-callbacks/sandbox',status:response.status()});
  assert((Array.isArray(expected)?expected:[expected]).includes(response.status()),'Callback expected '+expected+' got '+response.status()+': '+String(data.error||''));
  assert(!JSON.stringify(data).includes(secret),'Signing secret must not appear in response');
  return data;
 };
 await api(admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
 const physical=(await api(admin,'admin/commerce/products',{title:'PAY08 合成实物样品',type:'physical',environment:'sandbox',status:'published',currency:'CNY',shippingCountries:['CN'],stock:100,priceMinor:300,sku:'pay08-'+h.runId})).data.item;
 const place=async(account=user)=>(await api(account,'commerce/orders',{requestId:uuid(),environment:'sandbox',items:[{skuId:physical.skuId,quantity:1}],shippingAddress:{name:'合成收件人',country:'CN',city:'测试市',address:'测试路 8 号',postalCode:'000000'}})).data;
 const envelope=order=>({eventId:uuid(),transactionId:uuid(),orderId:order.id,type:'payment.succeeded',amountMinor:order.totalMinor,currency:order.currency});
 const order=await place(),body=envelope(order);
 let receipt,alias;

 await check('正式渠道、禁用测试适配与非法服务端密钥引用全部拒绝',async()=>{
  await callback(body,503,{route:'/api/payment-callbacks/production'});
  await callback(body,503,{route:'/api/payment-callbacks/stripe'});
  for(const mode of ['disabled','invalid-ref']){
   await control({action:'gate',mode});
   await callback(body,503);
   const settings=(await api(admin,queue)).data.settings;
   assert.equal(settings.sandboxEnabled,false);assert.equal(settings.productionEnabled,false);
  }
  await control({action:'gate',mode:'enabled'});
  const settings=(await api(admin,queue)).data.settings;
  assert.equal(settings.sandboxEnabled,true);assert.equal(settings.adapter,'sandbox-hmac-fixture');
 });

 await check('缺失错误过期签名与签名后篡改均拒绝，收件数量不变',async()=>{
  const before=(await snapshot()).inboxCount;
  await callback(body,401,{signature:''});
  await callback(body,401,{signature:'0'.repeat(64)});
  await callback(body,401,{timestamp:String(Math.floor(Date.now()/1000)-601)});
  const stamp=String(Math.floor(Date.now()/1000));
  const signed=crypto.createHmac('sha256',secret).update(stamp+'.'+JSON.stringify(body)).digest('hex');
  await callback(body,401,{raw:JSON.stringify({...body,amountMinor:301}),timestamp:stamp,signature:signed});
  assert.equal((await snapshot()).inboxCount,before);
 });

 await check('严格最小负载、整数金额、字段白名单与8192字节边界',async()=>{
  const before=(await snapshot()).inboxCount;
  const invalid=[{...body,ownerId:'do-not-trust-client-owner'},{...body,amountMinor:true},{...body,amountMinor:3.1},{...body,amountMinor:-1},{...body,currency:'cny'},{...body,type:'refund.succeeded'}];
  for(const value of invalid)await callback(value,400);
  await callback(body,400,{raw:'{"eventId":'});
  await callback(body,400,{raw:JSON.stringify(body).replace('"amountMinor":300','"amountMinor":300,"amountMinor":300')});
  await callback(body,413,{raw:' '.repeat(8193)});
  await callback(body,415,{contentType:'text/plain'});
  assert.equal((await snapshot()).inboxCount,before);
 });

 await check('持久化失败不返回接收成功，也不改变账与库存',async()=>{
  const before=await snapshot(order.id);
  await control({action:'fail-receive-on'});
  try{await callback(body,[500,503]);}finally{await control({action:'fail-receive-off'});}
  const after=await snapshot(order.id);
  assert.equal(after.inboxCount,before.inboxCount);assert.equal(after.transactionsCount,before.transactionsCount);
  assert.deepEqual(after.order,before.order);assert.deepEqual(after.ledger,before.ledger);assert.deepEqual(after.inventory,before.inventory);
 });

 await check('返回202之前已落盘，接收与消费分离且未提前扣库存发权益',async()=>{
  const before=await snapshot(order.id);
  receipt=await callback(body);
  assert.equal(receipt.accepted,true);assert.equal(receipt.duplicate,false);assert.equal(receipt.productionEnabled,false);
  const detail=await get(receipt.receiptId),after=await snapshot(order.id,receipt.receiptId);
  assert.equal(detail.item.status,'received');assert.equal(detail.item.attempts,0);assert.equal(detail.item.receivedCount,1);
  assert.equal(after.inbox.event_id,body.eventId);assert.equal(after.order.payment_status,'unpaid');
  assert.deepEqual(after.ledger,before.ledger);assert.deepEqual(after.inventory,before.inventory);assert.deepEqual(after.entitlements,[]);
 });

 await check('并发重复事件只保留一个收件，内容冲突持久审计并返回409',async()=>{
  const replies=await Promise.all(Array.from({length:4},()=>callback(body)));
  assert(replies.every(r=>r.receiptId===receipt.receiptId&&r.duplicate));
  assert.equal((await get(receipt.receiptId)).item.receivedCount,5);
  const before=await snapshot(order.id);
  await callback({...body,amountMinor:301},409);
  const otherOrder=await place(other);
  await callback({...body,eventId:uuid(),orderId:otherOrder.id},409);
  assert.equal((await snapshot()).inboxCount,before.inboxCount);
  const sameTransaction={...body,eventId:uuid()};
  alias=await callback(sameTransaction);
  assert.equal(alias.duplicate,true);assert.notEqual(alias.receiptId,receipt.receiptId);
  assert.equal((await get(alias.receiptId)).item.canonicalReceiptId,receipt.receiptId);
 });

 await check('匿名与普通账号不能读取或消费队列，非法分页与状态明确拒绝',async()=>{
  await api(anonymous,queue,undefined,'GET',401);
  await api(user,queue,undefined,'GET',403);
  await api(user,queue+'/'+receipt.receiptId,undefined,'GET',403);
  await api(user,queue+'/process',{limit:1},'POST',403);
  await api(user,queue+'/'+receipt.receiptId+'/retry',{},'POST',403);
  await api(admin,queue+'?status=unknown',undefined,'GET',400);
  await api(admin,queue+'?before='+uuid(),undefined,'GET',404);
  await api(admin,queue+'/process',{limit:0},'POST',400);
  await api(admin,queue+'/process',{limit:1,owner:'forged'},'POST',400);
  const response=await anonymous.post(base+'/__callback-test/control',{data:{action:'snapshot'}});
  assert.equal(response.status(),403);
 });

 await check('并发消费者与同交易多事件仅结算一次，账和库存状态原子一致',async()=>{
  const before=await snapshot(order.id);
  await Promise.all([consume(1),consume(1)]);
  const main=await get(receipt.receiptId),duplicate=await get(alias.receiptId),after=await snapshot(order.id);
  assert.equal(main.item.status,'applied');assert.equal(duplicate.item.status,'applied');assert.equal(main.item.attempts,1);
  assert.equal(after.ledger.filter(e=>e.kind==='sandbox_pay').length,1);assert.equal(after.order.payment_status,'paid');
  assert.equal(after.inventory[0].stock,before.inventory[0].stock-1);assert.equal(after.inventory[0].reserved,before.inventory[0].reserved-1);assert.equal(after.inventory[0].state,'consumed');
  const ledger=after.ledger;
  await callback(body);await consume(1);
  assert.deepEqual((await snapshot(order.id)).ledger,ledger);
  await api(admin,queue+'/'+receipt.receiptId+'/retry',{},'POST',409);
  assert(main.attempts.some(a=>a.action==='claim'&&a.actor));assert(main.attempts.some(a=>a.result==='applied'));
 });

 await check('未知订单、金额币种不符与主动关闭订单仍进入人工核查',async()=>{
  const mismatchedAmount=await place(),mismatchedCurrency=await place(),closed=await place();
  await control({action:'close-order',orderId:closed.id});
  const cases=[
   [{...envelope(mismatchedAmount),amountMinor:mismatchedAmount.totalMinor+1},'amount_currency_mismatch'],
   [{...envelope(mismatchedCurrency),currency:'USD'},'amount_currency_mismatch'],
   [{...envelope(order),orderId:uuid()},'unknown_order'],
   [envelope(closed),'order_not_payable'],
  ];
  const receipts=[];for(const [value,code] of cases)receipts.push([await callback(value),value,code]);
  await consume(10);
  for(const [accepted,value,code] of receipts){
   const detail=await get(accepted.receiptId);assert.equal(detail.item.status,'manual_review');assert.equal(detail.item.lastError,code);
   assert.equal((await snapshot(value.orderId)).ledger.length,0);
  }
 });

 await check('已付款或已退款订单收到另一交易，不覆盖原账且不复开权益',async()=>{
  const paid=await place(),refunded=await place();
  for(const o of [paid,refunded])await api(user,'commerce/orders/'+o.id+'/sandbox-pay',{requestId:uuid()});
  await api(admin,'admin/commerce/orders/'+refunded.id+'/refund',{requestId:uuid(),items:[{itemId:refunded.items[0].id,quantity:1}]});
  const cases=[];
  for(const o of [paid,refunded])cases.push({order:o,before:await snapshot(o.id),receipt:await callback(envelope(o))});
  await consume(10);
  for(const c of cases){assert.equal((await get(c.receipt.receiptId)).item.status,'manual_review');const after=await snapshot(c.order.id);assert.deepEqual(after.ledger,c.before.ledger);assert.deepEqual(after.inventory,c.before.inventory);assert.deepEqual(after.order,c.before.order);}
 });

 await check('真实SQL暂时故障回滚全部结算，人工重试不重置次数且可恢复',async()=>{
  const o=await place(),accepted=await callback(envelope(o)),before=await snapshot(o.id);
  await control({action:'fail-apply-on',orderId:o.id});
  try{await consume(1);}finally{await control({action:'fail-apply-off'});}
  const failed=await get(accepted.receiptId),after=await snapshot(o.id);
  assert.equal(failed.item.status,'retry');assert.equal(failed.item.attempts,1);assert.equal(failed.item.lastError,'storage_unavailable');assert(failed.item.nextAttempt>Date.now()-200);
  assert.deepEqual(after.ledger,before.ledger);assert.deepEqual(after.inventory,before.inventory);assert.equal(after.order.payment_status,'unpaid');
  await api(admin,queue+'/'+accepted.receiptId+'/retry',{});
  await consume(1);
  const recovered=await get(accepted.receiptId);assert.equal(recovered.item.status,'applied');assert.equal(recovered.item.attempts,2);
  assert.equal((await snapshot(o.id)).ledger.length,1);
 });

 await check('中断后的过期租约可恢复，旧租约不会造成重复结算',async()=>{
  const o=await place(),accepted=await callback(envelope(o));
  await control({action:'expired-lease',receiptId:accepted.receiptId});
  await consume(1);
  const detail=await get(accepted.receiptId);assert.equal(detail.item.status,'applied');assert.equal(detail.item.attempts,2);
  assert(detail.attempts.some(a=>a.errorCode==='lease_expired'));assert.equal((await snapshot(o.id)).ledger.length,1);
 });

 await check('第五次仍失败转人工核查并封顶，重复重试不能绕过上限',async()=>{
  const o=await place(),accepted=await callback(envelope(o));
  await control({action:'attempt-limit',receiptId:accepted.receiptId});await control({action:'fail-apply-on',orderId:o.id});
  try{await consume(1);}finally{await control({action:'fail-apply-off'});}
  const detail=await get(accepted.receiptId);assert.equal(detail.item.status,'manual_review');assert.equal(detail.item.attempts,5);
  await api(admin,queue+'/'+accepted.receiptId+'/retry',{},'POST',409);
  assert.equal((await snapshot(o.id)).ledger.length,0);
 });

 await check('接收成功后新请求仍可读取，Python进程重启后收件和待处理任务保留',async()=>{
  const o=await place(),accepted=await callback(envelope(o));
  if(childBase){const port=Number(new URL(base).port);await stop();assert.equal(await launch(true,port),base);}
  const fresh=await h.context();
  const read=await fresh.get(base+'/api/health');assert.equal(read.status(),200);
  const detail=await get(accepted.receiptId);assert.equal(detail.item.status,'received');assert.equal(detail.item.eventId,(await snapshot('',accepted.receiptId)).inbox.event_id);
  await consume(1);assert.equal((await get(accepted.receiptId)).item.status,'applied');
  return {processRestart:!!childBase,cloudBoundary:'Cloud only verifies separate request/API-object persistence; no worker process restart is claimed'};
 });

 if(!args['http-only'])await check('后台原生刷新横滑查看处理与重试、长编号和商城订单返回',async()=>{
  const o=await place(),longBody={...envelope(o),eventId:'evt_'+('x'.repeat(96)),transactionId:'txn_'+('y'.repeat(96))},accepted=await callback(longBody);
  const page=(await h.browserContext(await admin.storageState())).page;
  await page.goto(base+'/admin');await page.locator('[data-nav=commerce]').first().click();
  const panel=page.locator('#payment-callback-admin');
  await panel.locator('[data-callback-action=load]').click();
  const view=panel.locator('[data-callback-action=view][data-id="'+accepted.receiptId+'"]');
  await view.waitFor();
  for(const width of [1280,360]){
   await page.setViewportSize({width,height:850});
   const bad=await panel.evaluate(el=>{const r=el.getBoundingClientRect();return r.left<0||r.right>innerWidth+1;});assert.equal(bad,false,'Callback panel fits viewport');
   const wrap=panel.locator('.table-wrap').first();await wrap.scrollIntoViewIfNeeded();
   const metrics=await wrap.evaluate(e=>({width:e.clientWidth,scroll:e.scrollWidth}));
   await wrap.hover();await page.mouse.wheel(600,0);await page.waitForTimeout(100);
   if(metrics.scroll>metrics.width+1)assert(await wrap.evaluate(e=>e.scrollLeft>0),'Native horizontal wheel reaches offscreen table columns');
   await view.click();const detail=page.locator('#callback-receipt-detail');
   await detail.getByText('交易编号：'+longBody.transactionId,{exact:false}).waitFor();
   assert(await detail.locator('p').first().evaluate(e=>e.scrollWidth<=e.clientWidth+1),'Long transaction ID remains fully readable');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Admin viewport stays within screen width');
   await h.capture(page,'后台-'+width+'-长编号详情');
  }
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/'+queue+'/process')&&r.request().method()==='POST'),panel.locator('[data-callback-action=process]').click()]);
  await page.locator('#callback-receipt-detail h3').filter({hasText:'已应用'}).waitFor();
  assert.equal((await get(accepted.receiptId)).item.status,'applied');
  await page.locator('[data-co-admin=order][data-id="'+o.id+'"]').click();
  await page.locator('#co-order-editor').getByText(o.id,{exact:false}).waitFor();
  await panel.locator('[data-callback-action=load]').click();
  await view.click();await page.locator('#callback-receipt-detail h3').filter({hasText:'已应用'}).waitFor();
  const retryOrder=await place(),pending=await callback(envelope(retryOrder));
  await control({action:'fail-apply-on',orderId:retryOrder.id});
  try{await consume(1);}finally{await control({action:'fail-apply-off'});}
  await panel.locator('[data-callback-action=load]').click();
  await panel.locator('[data-callback-action=view][data-id="'+pending.receiptId+'"]').click();
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/'+pending.receiptId+'/retry')&&r.request().method()==='POST'),panel.locator('[data-callback-action=retry]').click()]);
  await panel.locator('[data-callback-action=process]:enabled').waitFor();
  await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/'+queue+'/process')&&r.request().method()==='POST'),panel.locator('[data-callback-action=process]').click()]);
  await page.locator('#callback-receipt-detail h3').filter({hasText:'已应用'}).waitFor();
  assert.equal((await get(pending.receiptId)).item.status,'applied');
  assert.equal((await get(pending.receiptId)).item.attempts,2);
  await h.capture(page,'后台重试');
 });

 await check('最终身份与权限边界未变化，不在报告中保存签名或密钥',async()=>{
  assert.deepEqual(identity(),sourceIdentity);assert.equal((await api(admin,queue)).data.settings.productionEnabled,false);
  const serialized=JSON.stringify(h.report);assert(!serialized.includes(secret)&&!serialized.includes(controlToken));
 });
}

run().then(async()=>{await stop();if(h)await h.finish();},async error=>{await stop();if(h)await h.finish(error);else{console.error(error.message);process.exitCode=1;}});
