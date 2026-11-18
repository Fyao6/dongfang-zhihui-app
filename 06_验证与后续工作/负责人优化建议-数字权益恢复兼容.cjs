// New module compatibility; original business assertions retained.
// Source 迟到补偿恢复兼容.cjs SHA256 fb0b410873d5e297f6d95faa482f4b91e43dc1cbec9533a7f0d7a0e57e47268a
// PAY09 actual HTTP, persistence, concurrency and native browser acceptance. No real provider calls.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {makeHarness}=require('./负责人优化建议-交易测试工具.cjs');
const ROOT=path.resolve(__dirname,'..'),uuid=()=>crypto.randomUUID();
const args=Object.fromEntries(process.argv.slice(2).filter(s=>s.startsWith('--')).map(s=>{const n=s.indexOf('=');return [s.slice(2,n<0?undefined:n),n<0?true:s.slice(n+1)];}));
const target=args.target||'python',endpoint=process.env.EW_PAYMENT_QUERY_SANDBOX_ENDPOINT,token=process.env.RECOVERY_TEST_TOKEN,callbackSecret=process.env.EW_PAYMENT_CALLBACK_QA_SECRET;
const python=process.env.EW_PYTHON||path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
const ownedDb=path.join(__dirname,'负责人优化建议-数字权益隔离-'+Date.now().toString(36)+'-'+uuid()+'.sqlite3');
let child,h;
async function launch(resume=false,port=0){
 child=spawn(python,['-B',path.join(__dirname,'负责人优化建议-数字权益Python测试服务.py'),'--db',ownedDb,'--port',String(port),...(resume?['--resume']:[])],{cwd:ROOT,env:process.env,windowsHide:true,stdio:['ignore','pipe','pipe']});
 return new Promise((resolve,reject)=>{let output='';const timeout=setTimeout(()=>reject(Error('Owned PAY09 Python startup timeout')),25000);child.stdout.on('data',data=>{output+=data;const match=/APP: (http:\/\/127\.0\.0\.1:\d+)/.exec(output);if(match){clearTimeout(timeout);resolve(match[1]);}});child.stderr.on('data',()=>{});child.once('error',error=>{clearTimeout(timeout);reject(error);});child.once('exit',code=>{clearTimeout(timeout);reject(Error('Owned PAY09 Python exited '+code));});});
}
async function stop(){if(child&&child.exitCode===null){const done=new Promise(resolve=>child.once('exit',resolve));child.kill();await done;}}
async function run(){
 assert(args.base,'Use the owned late-compensation launcher; baseline wrappers are not started by this derived suite');
 assert(endpoint&&token&&callbackSecret,'Use the isolated PAY09 launcher');
 const base=args.base||(target==='python'?await launch():null);assert(base,'Cloud requires a fresh fixture --base');
 h=makeHarness([...process.argv.slice(2),'--base='+base,'--module=负责人优化建议-数字权益恢复兼容',...(args.report?[]:['--report=负责人优化建议-数字权益恢复兼容-'+target+'.json'])]);
 await h.start();if(child)h.report.ownedDatabase=path.relative(ROOT,ownedDb).split(path.sep).join('/');
 h.report.compatibilityBaseline={path:'06_验证与后续工作/负责人优化建议-支付恢复专项.cjs',sha256:h.sha(fs.readFileSync(path.join(__dirname,'负责人优化建议-支付恢复专项.cjs'))),replacement:'Only expired-order zero-HTTP terminal assertion is replaced by actual positive/stock-unavailable late-query acceptance in the late compensation special. Manual close, paid/refunded terminal protection and all other assertions remain.'};
 const lateFiles=['04_研发源码/app/r4/backend/payment_late.py','04_研发源码/app/cloud/lib/payment-late.ts','04_研发源码/app/r4/payment-late-ui.js','04_研发源码/app/r4/payment-late-admin.js'];h.report.lateSources=Object.fromEntries(lateFiles.map(name=>[name,h.sha(fs.readFileSync(path.join(ROOT,name)))]));
 h.report.scope='PAY09 compatibility on the final late-compensation build. The old expired zero-HTTP assertion is replaced by separately verified late-payment query success and shortage cases. All other trusted HTTP, owner, lease, retry, account-close, paid/refunded terminal and native UI assertions remain; no real provider.';
 h.report.coverage={http:true,ui:!args['http-only'],realPayments:false,production:false,realHttpFixture:true,processRestart:!!child};
 const sourceNames=[...lateFiles,'04_研发源码/app/r4/backend/payment_recovery.py','04_研发源码/app/cloud/lib/payment-recovery.ts','04_研发源码/app/r4/backend/payment_callbacks.py','04_研发源码/app/cloud/lib/payment-callbacks.ts','04_研发源码/app/r4/payment-recovery-ui.js','04_研发源码/app/r4/payment-recovery-admin.js','04_研发源码/app/r4/commerce-ui.js','04_研发源码/app/r4/build.py','04_研发源码/app/cloud/prepare.py'];
 const identity=()=>Object.fromEntries(sourceNames.map(name=>[name,h.sha(fs.readFileSync(path.join(ROOT,name)))]));const sourceIdentity=identity();h.report.recoverySources=sourceIdentity;
 const {admin,user,other,anonymous}=await h.seed(),{api,check}=h;
 const control=async data=>{const r=await anonymous.post(base+'/__recovery-test/control',{headers:{'X-Recovery-Test':token},data});assert.equal(r.status(),200,'Owned DB control');return r.json();};
 const fixture=async data=>{const r=await anonymous.post(new URL(endpoint).origin+'/pay09-fixture/control',{headers:{'X-Recovery-Test':token},data});assert.equal(r.status(),200,'Independent HTTP fixture control');return r.json();};
 const configure=(order,mode,extra={})=>fixture({action:'configure',orderId:order.id,mode,...extra});
 const calls=async order=>(await fixture({action:'stats',orderId:order.id})).calls;
 const snapshot=order=>control({action:'snapshot',orderId:order.id});
 const route=order=>'commerce/orders/'+order.id+'/payment-recovery';
 const read=async order=>(await api(order.account,route(order))).data;
 const query=async(order,requestId=uuid(),expected=200)=>(await api(order.account,route(order),{requestId},'POST',expected)).data;
 const queue='admin/payment-recovery';
 const waitCalls=async(order,count)=>{for(let i=0;i<40;i++){if((await calls(order)).length>=count)return;await new Promise(resolve=>setTimeout(resolve,50));}throw Error('Expected actual upstream query did not arrive');};
 let buyerIndex=0,orderCount=0,buyer={ctx:user};
 async function register(){const ctx=await h.context(),password=crypto.randomBytes(20).toString('hex');const result=(await api(ctx,'auth/register',{username:'pr_'+h.runId+'_'+(++buyerIndex),password,name:'PAY09 合成账号'})).data;return {ctx,password,id:result.user.id};}
 await api(admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
 const course=(await api(anonymous,'public')).data.content.courses[0];
 const product=(await api(admin,'admin/commerce/products',{title:'PAY09 合成数字权益',type:'digital',environment:'sandbox',status:'published',currency:'CNY',stock:500,priceMinor:300,contentId:course.id,sku:'pay09-'+h.runId})).data.item;
 async function place(explicit){if(!explicit&&orderCount>0&&orderCount%3===0)buyer=await register();orderCount++;const account=explicit?.ctx||buyer.ctx;const order=(await api(account,'commerce/orders',{requestId:uuid(),environment:'sandbox',items:[{skuId:product.skuId,quantity:1}]})).data;return {...order,account};}
 const callback=async(order,transactionId)=>{const body={eventId:uuid(),transactionId,orderId:order.id,type:'payment.succeeded',amountMinor:order.totalMinor,currency:order.currency},raw=JSON.stringify(body),stamp=String(Math.floor(Date.now()/1000));const r=await anonymous.post(base+'/api/payment-callbacks/sandbox',{data:Buffer.from(raw),headers:{'Content-Type':'application/json','X-EW-Callback-Timestamp':stamp,'X-EW-Callback-Signature':crypto.createHmac('sha256',callbackSecret).update(stamp+'.'+raw).digest('hex')}});assert.equal(r.status(),202);return r.json();};
 const stateUnchanged=async(order,before)=>{const after=await snapshot(order);assert.deepEqual(after.ledger,before.ledger);assert.deepEqual(after.entitlements,before.entitlements);assert.deepEqual(after.inventory,before.inventory);assert.deepEqual(after.order,before.order);};
 const gateOrder=await place();

 await check('关闭与非法服务端配置拒绝查询，不向任意地址发送HTTP',async()=>{
  for(const mode of ['disabled','invalid-ref','host','query','userinfo','fragment','callback-disabled']){
   await control({action:'query-config',mode});assert.equal((await read(gateOrder)).queryReady,false);await query(gateOrder,uuid(),[400,503]);assert.equal((await calls(gateOrder)).length,0);
  }
  await control({action:'query-config',mode:'enabled'});assert.equal((await read(gateOrder)).queryReady,true);
 });

 await check('本人归属与后台权限、请求号和字段白名单在真实接口执行',async()=>{
  await api(anonymous,route(gateOrder),undefined,'GET',401);await api(other,route(gateOrder),undefined,'GET',404);await api(other,route(gateOrder),{requestId:uuid()},'POST',404);
  await api(anonymous,queue,undefined,'GET',401);await api(user,queue,undefined,'GET',403);await api(user,queue+'/process',{limit:1},'POST',403);
  for(const data of [{},{requestId:''},{requestId:uuid(),state:'paid'},{requestId:uuid(),amountMinor:1},{requestId:uuid(),transactionId:uuid()},{requestId:uuid(),endpoint:'http://example.invalid'}])await api(gateOrder.account,route(gateOrder),data,'POST',400);
  assert.equal((await calls(gateOrder)).length,0);
 });

 await check('GET只回查持久结果，无任务时返回null且绝不主动请求上游',async()=>{
  const before=await snapshot(gateOrder);for(let i=0;i<3;i++){const result=await read(gateOrder);assert.equal(result.job,null);assert.equal(result.productionEnabled,false);assert.equal(result.order.id,gateOrder.id);assert.equal(result.order.environment,'sandbox');}
  assert.equal((await calls(gateOrder)).length,0);assert.equal((await snapshot(gateOrder)).jobsCount,before.jobsCount);
 });

 await check('并发同请求只发一次真实查单，异单复用请求号409且不重置任务',async()=>{
  const order=await place(),requestId=uuid();await configure(order,'paid');
  const results=await Promise.all([query(order,requestId),query(order,requestId)]);assert.equal(results[0].job.id,results[1].job.id);
  const result=await read(order);assert.equal(result.job.status,'confirmed');assert.equal(result.job.attempts,1);assert.equal((await calls(order)).length,1);
  await query(order,requestId);assert.equal((await calls(order)).length,1);
  const another=(await api(order.account,'commerce/orders',{requestId:uuid(),environment:'sandbox',items:[{skuId:product.skuId,quantity:1}]})).data;another.account=order.account;
  await query(another,requestId,409);assert.equal((await calls(another)).length,0);
 });

 await check('未付款待处理未找到与渠道失败保持未付，GET不重复查单',async()=>{
  for(const [mode,status,code] of [['unpaid','unpaid','query_unpaid'],['pending','retry','query_pending'],['not_found','retry','query_not_found'],['failed','retry','query_failed']]){
   const order=await place();await configure(order,mode);const before=await snapshot(order),result=await query(order);
   assert.equal(result.job.status,status);assert.equal(result.job.lastError,code);assert.equal(result.order.paymentStatus,'unpaid');
   await read(order);await read(order);assert.equal((await calls(order)).length,1);await stateUnchanged(order,before);
  }
 });

 await check('真实HTTP500与8秒超时产生有限退避，不制造付款或权益',async()=>{
  for(const mode of ['http500','timeout']){
   const order=await place();await configure(order,mode);const before=await snapshot(order),started=Date.now(),result=await query(order);
   assert.equal(result.job.status,'retry');assert.equal(result.job.lastError,mode==='timeout'?'query_timeout':'query_http_error');assert.equal(result.job.attempts,1);assert(result.job.nextAttempt>Date.now()-200);
   if(mode==='timeout')assert(Date.now()-started>=7000,'Actual upstream timeout was exercised');await stateUnchanged(order,before);
  }
 });

 await check('签名时效大小JSON白名单与订单金额币种逐项绑定，2xx不能冒充可信成功',async()=>{
  const modes=['bad-signature','expired-signature','malformed','oversize','extra-field','mismatch-order','mismatch-query','mismatch-amount','mismatch-currency'];
  for(const mode of modes){const order=await place();await configure(order,mode);const before=await snapshot(order),result=await query(order);assert.equal(result.job.status,'manual_review',mode);assert(['invalid_query_signature','invalid_query_response','query_mismatch'].includes(result.job.lastError),mode+': '+result.job.lastError);assert(!result.job.receiptId);await stateUnchanged(order,before);}
 });

 await check('真实302重定向被拒绝，夹具目标端点未被访问',async()=>{
  const order=await place();await configure(order,'redirect');const result=await query(order);assert.equal(result.job.status,'retry');assert.equal(result.job.lastError,'query_http_error');const all=(await fixture({action:'stats'})).calls;assert(!all.some(call=>call.mode==='redirect-target'));
 });

 await check('可信查询只消费本人指定收件，数字权益唯一发放而其他回调保持待处理',async()=>{
  const unrelated=await place(),pending=await callback(unrelated,'other:'+uuid());const order=await place();await configure(order,'paid');const result=await query(order);assert.equal(result.job.status,'confirmed');assert(result.job.receiptId);
  const raw=await snapshot(order);assert.equal(raw.ledger.length,1);assert.equal(raw.entitlements.length,1);assert.equal((await api(admin,'admin/payment-callbacks/'+pending.receiptId)).data.item.status,'received');
  const before=await snapshot(order);await query(order);await read(order);await stateUnchanged(order,before);assert.equal((await calls(order)).length,1);
  const rights=(await api(order.account,'commerce/entitlements?environment=sandbox')).data;assert.equal(rights.grantsProductionAccess,false);
 });

 await check('成功查询与同交易回调并发仅入账一次，后续重放不重复发权益',async()=>{
  const order=await place(),transactionId='race:'+uuid();await configure(order,'hold',{transactionId,heldState:'paid'});
  const inflight=query(order);await waitCalls(order,1);await callback(order,transactionId);await fixture({action:'release',orderId:order.id});await inflight;
  const result=await read(order);assert.equal(result.job.status,'confirmed');const raw=await snapshot(order);assert.equal(raw.ledger.length,1);assert.equal(raw.entitlements.length,1);await callback(order,transactionId);await query(order);assert.equal((await snapshot(order)).ledger.length,1);
 });

 await check('旧pending查询晚于成功回调返回，订单付款与既有权益不会回退',async()=>{
  const order=await place(),transactionId='late:'+uuid();await configure(order,'hold',{transactionId,heldState:'pending'});
  const inflight=query(order);await waitCalls(order,1);const paid=await callback(order,transactionId);await api(admin,'admin/payment-callbacks/process',{limit:10});assert.equal((await api(admin,'admin/payment-callbacks/'+paid.receiptId)).data.item.status,'applied');
  const before=await snapshot(order);await fixture({action:'release',orderId:order.id});await inflight;await stateUnchanged(order,before);
 });

 await check('租约过期后新查询先确认，旧租约迟到响应不能覆盖新结果',async()=>{
  const order=await place();await configure(order,'hold',{heldState:'pending'});const first=query(order);await waitCalls(order,1);const current=await read(order);assert.equal(current.job.status,'processing');
  await control({action:'expired-lease',jobId:current.job.id});await configure(order,'paid');
  if(!args['http-only']){
   const page=(await h.browserContext(await order.account.storageState())).page;await page.setViewportSize({width:360,height:850});
   await page.goto(base+'/experience?page=commerceOrders&lang=zh&mode=day');await page.locator('[data-commerce-action=environment][data-environment=sandbox]').click();await page.locator('.co-navigation [data-to=commerceOrders]').click();await page.locator('[data-commerce-action=order][data-id="'+order.id+'"]').click();
   const panel=page.locator('#payment-recovery-panel');await panel.locator('[data-recovery-action=query]:enabled').waitFor();
   assert((await panel.innerText()).includes('中断'),'Expired processing lease offers the actual owner a recovery action');
   const capture='负责人优化建议-支付恢复-'+target+'-'+h.runId+'-过期租约本人恢复.png';await panel.evaluate(el=>el.scrollIntoView({block:'start'}));await page.screenshot({path:path.join(__dirname,capture),fullPage:false});h.report.captures.push(capture);
   const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/'+order.id+'/payment-recovery')&&r.request().method()==='POST'),panel.locator('[data-recovery-action=query]').click()]);assert.equal(response.status(),200);assert.equal((await response.json()).job.status,'confirmed');
  }else assert.equal((await query(order)).job.status,'confirmed');
  await fixture({action:'release',orderId:order.id});await first;const result=await read(order);assert.equal(result.job.status,'confirmed');assert.equal(result.job.attempts,2);assert.equal((await snapshot(order)).ledger.length,1);
 });

 await check('五次上限和稳定订单任务防止更换requestId绕过退避与重试限制',async()=>{
  const order=await place();await configure(order,'pending');const first=await query(order);await control({action:'attempt-limit',jobId:first.job.id});const limited=await query(order);assert.equal(limited.job.attempts,5);assert.equal(limited.job.status,'manual_review');
  const count=(await calls(order)).length,next=await query(order);assert.equal(next.job.id,limited.job.id);assert.equal(next.job.attempts,5);assert.equal((await calls(order)).length,count);await api(admin,queue+'/'+limited.job.id+'/retry',{},'POST',409);
 });

 await check('SQL应用故障保留可信receipt，恢复只续消费而不重复向上游查单',async()=>{
  const order=await place();await configure(order,'paid');const before=await snapshot(order);await control({action:'fail-apply-on'});let failed;
  try{failed=await query(order);}finally{await control({action:'fail-apply-off'});}
  assert.equal(failed.job.status,'retry');assert(failed.job.receiptId);await stateUnchanged(order,before);const count=(await calls(order)).length;
  await control({action:'due',jobId:failed.job.id});const result=await query(order);assert.equal(result.job.status,'confirmed');assert.equal((await calls(order)).length,count);assert.equal((await snapshot(order)).ledger.length,1);
 });

 await check('真实查询在途时禁用适配或撤回引用或轮换密钥，旧paid响应不能入账',async()=>{
  for(const mode of ['disabled','invalid-ref','rotated-secret']){
   const order=await place();await configure(order,'hold',{heldState:'paid'});const inflight=query(order,uuid(),[200,409,503]);await waitCalls(order,1);
   await control({action:'query-config',mode});await fixture({action:'release',orderId:order.id});
   try{await inflight;}finally{await control({action:'query-config',mode:'enabled'});}
   const raw=await snapshot(order);assert.equal(raw.ledger.length,0);assert.equal(raw.entitlements.length,0);assert.equal(raw.callbacks.length,0);assert.equal(raw.order.payment_status,'unpaid');
  }
 });

 await check('查询期间账号关闭及主动关闭已付已退，成功响应不越过最终门禁',async()=>{
  const closedBuyer=await register(),order=await place(closedBuyer);await configure(order,'hold',{heldState:'paid'});const inflight=query(order,uuid(),[200,401,409]);await waitCalls(order,1);
  const proof={requestId:uuid(),nonce:crypto.randomBytes(32).toString('hex')};const prepared=(await api(closedBuyer.ctx,'account-closure/prepare',{...proof,password:closedBuyer.password})).data;
  await api(closedBuyer.ctx,'account-closure/confirm',{...proof,challengeId:prepared.challengeId,confirmed:true,renewalAcknowledged:true});await fixture({action:'release',orderId:order.id});await inflight;assert.equal((await snapshot(order)).ledger.length,0);
  for(const mode of ['close-order']){const o=await place();await control({action:mode,orderId:o.id});await configure(o,'paid');const before=await snapshot(o);await query(o,uuid(),[200,409]);assert.equal((await calls(o)).length,0);await stateUnchanged(o,before);}
  for(const mode of ['paid','refunded']){
   const o=await place();await api(o.account,'commerce/orders/'+o.id+'/sandbox-pay',{requestId:uuid()});
   if(mode==='refunded')await api(admin,'admin/commerce/orders/'+o.id+'/refund',{requestId:uuid(),items:[{itemId:o.items[0].id,quantity:1}]});
   await configure(o,'paid');const before=await snapshot(o);await query(o);assert.equal((await calls(o)).length,0);await stateUnchanged(o,before);
  }
 });

 await check(child?'Python实际进程重启不丢持久任务，后台详情可查轨迹':'独立GET不丢持久任务，后台详情可查轨迹（不声明进程重启）',async()=>{
  const order=await place();await configure(order,'pending');const first=await query(order),count=(await calls(order)).length;
  if(child){const port=Number(new URL(base).port);await stop();assert.equal(await launch(true,port),base);}
  const result=await read(order);assert.equal(result.job.id,first.job.id);assert.equal(result.job.attempts,1);assert.equal((await calls(order)).length,count);
  const detail=(await api(admin,queue+'/'+first.job.id)).data;assert.equal(detail.job.id,first.job.id);assert(Array.isArray(detail.attempts));await api(other,queue+'/'+first.job.id,undefined,'GET',403);
 });

 if(!args['http-only'])await check('APP四语日夜360与1280原生查询回查，离页返回与浮层真实计时保持',async()=>{
  for(const [index,lang] of ['zh','zh-Hant','en','bo'].entries()){
   const order=await place();await configure(order,'paid');const page=(await h.browserContext(await order.account.storageState())).page;await page.setViewportSize({width:index%2?1280:360,height:850});
   await page.goto(base+'/experience?page=commerceOrders&lang='+lang+'&mode='+(index%2?'day':'night'));
   await page.locator('[data-commerce-action=environment][data-environment=sandbox]').click();await page.locator('.co-navigation [data-to=commerceOrders]').click();await page.locator('[data-commerce-action=order][data-id="'+order.id+'"]').click();
   const panel=page.locator('#payment-recovery-panel');await panel.locator('[data-recovery-action=query]').waitFor();
   const elapsed=await page.evaluate(()=>tbSummary().totalMs);
   await Promise.all([page.waitForResponse(r=>r.url().endsWith('/'+order.id+'/payment-recovery')&&r.request().method()==='POST'),panel.locator('[data-recovery-action=query]').click()]);
   await page.waitForFunction(()=>document.querySelector('[data-recovery-status]')?.textContent.trim()===recoveryStatus('confirmed'));assert.equal((await read(order)).job.status,'confirmed');
   await page.locator('.ew-page-back').click();await page.locator('[data-commerce-action=order][data-id="'+order.id+'"]').click();await panel.locator('[data-recovery-action=refresh]').click();
   assert(await page.evaluate(()=>tbSummary().totalMs)>=elapsed);assert(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth+1));
   for(const width of [360,1280])for(const mode of ['day','night']){await page.setViewportSize({width,height:850});await page.evaluate(mode=>{state.mode=mode;render(false);},mode);await panel.waitFor();assert(await panel.evaluate(el=>el.scrollWidth<=el.clientWidth+1));}
   const name='负责人优化建议-支付恢复-'+target+'-'+h.runId+'-'+lang+'-APP视口.png';await panel.evaluate(el=>el.scrollIntoView({block:'start'}));await page.screenshot({path:path.join(__dirname,name),fullPage:false});h.report.captures.push(name);
  }
 });

 await check('源构建身份、最小日志和生产关闭保持到专项结束',async()=>{const observed=await fixture({action:'stats'});h.report.actualHttpFixtureCalls=observed.calls;h.report.fixtureRejections=observed.rejections;assert.deepEqual(identity(),sourceIdentity);const report=JSON.stringify(h.report);for(const value of [token,callbackSecret,process.env.EW_PAYMENT_QUERY_QA_SECRET])assert(!report.includes(value));assert.equal((await read(gateOrder)).productionEnabled,false);});
}
run().then(async()=>{await stop();if(h)await h.finish();},async error=>{await stop();if(h)await h.finish(error);else{console.error(error.message);process.exitCode=1;}});
