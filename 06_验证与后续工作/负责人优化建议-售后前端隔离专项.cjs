'use strict';
// Isolated real-browser components with explicit synthetic account/API fixtures.
// Does not substitute for integrated HTTP/auth tests on the real two backends.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {chromium}=require(path.join(runtime,'node/node_modules/playwright'));
const ROOT=path.resolve(__dirname,'..'),R4=path.join(ROOT,'04_研发源码/app/r4');
const names=['after-sales-ui.js','after-sales-ui.css','after-sales-admin.js'];
const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
const hashes=()=>Object.fromEntries(names.map(n=>[n,sha(fs.readFileSync(path.join(R4,n)))]));
const before=hashes(),runId=Date.now().toString(36)+'_'+crypto.randomBytes(3).toString('hex');
const font=fs.readFileSync(path.join(ROOT,'04_研发源码/app/cloud/public/assets/NotoSerifTibetan.woff2'));
const html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+
fs.readFileSync(path.join(R4,'base.css'),'utf8')+'\n'+fs.readFileSync(path.join(R4,'i18n.css'),'utf8').replaceAll('__TIBETAN_FONT__','/assets/NotoSerifTibetan.woff2')+'\n'+fs.readFileSync(path.join(R4,'after-sales-ui.css'),'utf8')+
'\n@font-face{font-family:"EW Tibetan";src:url("/assets/NotoSerifTibetan.woff2")}html[lang=bo] body{font-family:"EW Tibetan",serif}html,body{min-height:100%;height:auto}body{display:block;overflow:auto;margin:0}#app{position:relative;max-width:430px;width:100%;height:auto;overflow:visible;margin:auto}#main{max-width:900px;margin:auto;padding:16px}button,input,select,textarea{font:inherit}fieldset{min-width:0}.page{padding:16px}.panel{margin:16px 0}table{max-width:100%;border-collapse:collapse}td,th{padding:8px;border:1px solid #777;overflow-wrap:anywhere}form label{display:block;margin:12px 0}form input,form textarea,form select{max-width:100%}body[data-mode=day]{background:#fff;color:#152c35}body[data-mode=night]{background:#0d202a;color:#eee}label{overflow-wrap:anywhere}</style></head><body><main id="app"></main><main id="main"></main></body></html>';
const server=http.createServer((req,res)=>{
 if(req.url==='/assets/NotoSerifTibetan.woff2'){res.writeHead(200,{'Content-Type':'font/woff2'});return res.end(font);}
 res.writeHead(200,{'Content-Type':'text/html;charset=utf-8'});res.end(html);
});
const report={at:new Date().toISOString(),runId,kind:'isolated real-browser after-sales components',fullAPPIntegrated:false,actualServerAuthTested:false,
 syntheticAccountAndApi:true,productionWrites:false,providerRequests:0,results:[],views:[],captures:[],errors:[],sourceHashes:before};
let browser,base,activePage;
async function check(name,fn){try{await fn();report.results.push({name,pass:true});console.log('PASS '+name);}catch(e){
 report.results.push({name,pass:false,error:e.stack||String(e)});console.log('FAIL '+name+': '+e.message);
 if(activePage&&!activePage.isClosed())await capture(activePage,'失败'+report.results.length).catch(()=>{});
}}
async function capture(p,label){const name='负责人优化建议-售后组件-'+runId+'-'+label+'.png';await p.screenshot({path:path.join(__dirname,name),fullPage:true});report.captures.push(name);}
async function fixture(p,script){await p.goto(base);await p.addScriptTag({path:path.join(__dirname,'负责人优化建议-售后前端夹具.js')});if(script)await p.addScriptTag({path:path.join(R4,script)});}
async function waitDetail(p,id){await p.locator('[data-af-detail="'+id+'"]').waitFor();}
async function calls(p,method,path){return p.evaluate(({method,path})=>__calls.filter(x=>x.method===method&&x.path===path),{method,path});}
(async()=>{
 let user,admin;
 try{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));base='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({headless:true});report.browserVersion=browser.version();
  user=await browser.newContext({viewport:{width:430,height:844}});const p=await user.newPage();activePage=p;p.on('pageerror',e=>report.errors.push(e.message));
  await check('模块显式安装前不联网/不登记页面；正式默认关闭，API常量不重赋',async()=>{
   await fixture(p,'after-sales-ui.js');assert.equal(await p.evaluate(()=>__calls.length),0);
   assert.equal(await p.evaluate(()=>typeof screens.afterSalesCenter),'undefined');
   await p.evaluate(()=>{window.__legacyCalls=0;window.coState=()=>({order:{id:'order-A',environment:'sandbox'}});window.coOpenAftersale=()=>{__legacyCalls++;};screens.commerceOrders=()=>'<section>Original unified orders</section>';AfterSalesUI.install();render();});
   await p.locator('.af-page').waitFor();await p.waitForFunction(()=>__calls.length>=2);
   assert.equal(await p.locator('[data-af-case]').count(),0);
   assert((await p.locator('#app').innerText()).includes('Production after-sales is not enabled'));
   assert.equal(await p.evaluate(()=>Object.getOwnPropertyDescriptor(window,'pxApi').writable),false);
   await p.evaluate(()=>{px.afterSalesReady=false;coOpenAftersale();});
   assert.equal(await p.evaluate(()=>__legacyCalls),1,'Closed module preserves the existing support entry');
   await p.evaluate(()=>{px.afterSalesReady=true;coOpenAftersale();});await p.locator('[data-af-form=request]').waitFor();
   await p.locator('[data-af-action=environment]').click();
   await p.evaluate(()=>navigate('commerceOrders'));await p.locator('[data-af-action=center]').click();
   assert.equal(await p.evaluate(()=>state.page),'afterSalesCenter','Actual order-list action reaches own after-sales center');
  });
  await check('测试本人列表/详情真实组件读取累计资金说明，不显示本申请已到账',async()=>{
   await p.locator('[data-af-action=environment]').click();await p.locator('[data-af-case=case-A]').waitFor();
   await p.locator('[data-af-action=open]').click();await waitDetail(p,'case-A');
   await p.locator('.af-money summary').click();const money=await p.locator('.af-money').innerText();
   assert(money.includes('do not confirm a refund for this case or real funds received'));assert.equal(await p.locator('[data-af-form=shipping]').count(),1);
  });
  await check('真实申请表按项数量和理由提交；切语言保留草稿与幂等编号',async()=>{
   await p.evaluate(()=>AfterSalesUI.openOrder('order-A'));await p.locator('[data-af-form=request]').waitFor();
   await p.locator('[name=type]').selectOption('return');await p.locator('[name=item]').check();
   await p.locator('[name="quantity:item-A"]').fill('2');await p.locator('[name=reason]').fill('合成物品外观检查');
   await p.evaluate(()=>{state.lang='zh';render();});assert.equal(await p.locator('[name=reason]').inputValue(),'合成物品外观检查');
   assert.equal(await p.locator('[name="quantity:item-A"]').inputValue(),'2');await p.locator('[data-af-form=request] button').click();
   await waitDetail(p,'created-case');const posted=(await calls(p,'POST','after-sales/cases')).at(-1).body;
   assert.equal(posted.environment,'sandbox');assert.equal(posted.type,'return');assert.deepEqual(posted.items,[{itemId:'item-A',quantity:2}]);assert(posted.requestId);
  });
  await check('真实物流表不冒充承运核验；语言样式重绘保留草稿和版本',async()=>{
   await p.evaluate(()=>{__case.status='accepted';__case.version=2;state.lang='en';});
   await p.evaluate(()=>AfterSalesUI.refresh());await p.locator('[data-af-form=shipping]').waitFor();
   await p.locator('[name=carrier]').fill('Synthetic carrier');await p.locator('[name=trackingNumber]').fill('RETURN-FIXTURE-001');
   await p.evaluate(()=>{state.lang='zh-Hant';state.mode='day';render();});
   assert.equal(await p.locator('[name=trackingNumber]').inputValue(),'RETURN-FIXTURE-001');
   await p.locator('[data-af-form=shipping] button').click();await p.waitForFunction(()=>document.querySelector('#app').textContent.includes('RETURN-FIXTURE-001'));
   const posted=(await calls(p,'POST','after-sales/cases/created-case/return-shipping')).at(-1).body;
   assert.equal(posted.version,2);assert(posted.requestId);assert((await p.locator('#app').innerText()).includes('未接承運商核驗'));
  });
  await check('旧详情读取晚到不能覆盖物流提交后的新状态',async()=>{
   await p.evaluate(()=>{__hold={method:'GET',path:'after-sales/cases/created-case'};void AfterSalesUI.refresh();});
   await p.waitForFunction(()=>__hold.entered);await p.locator('[name=trackingNumber]').fill('RETURN-NEW-002');await p.locator('[name=carrier]').fill('Synthetic new carrier');
   await p.locator('[data-af-form=shipping] button').click();await p.waitForFunction(()=>document.querySelector('#app').textContent.includes('RETURN-NEW-002'));
   await p.evaluate(()=>__hold.release());await p.waitForTimeout(80);assert((await p.locator('#app').innerText()).includes('RETURN-NEW-002'));
  });
  await check('提交晚到不拉回离开页面，返回后不锁死busy',async()=>{
   await p.evaluate(()=>{__hold={method:'POST',path:'after-sales/cases/created-case/return-shipping'};});
   await p.locator('[name=carrier]').fill('Synthetic late');await p.locator('[name=trackingNumber]').fill('RETURN-LATE-003');
   await p.locator('[data-af-form=shipping] button').click();await p.waitForFunction(()=>__hold.entered);
   await p.evaluate(()=>{navigate('community');__hold.release();});await p.waitForTimeout(80);assert.equal(await p.evaluate(()=>state.page),'community');
   await p.evaluate(()=>navigate('afterSalesCenter'));await p.locator('[data-af-case=created-case]').waitFor();
  });
  await check('切换账号时旧列表响应不显示前一账号申请或草稿',async()=>{
   await p.evaluate(()=>{__hold={method:'GET',path:'after-sales/cases?environment=sandbox'};void AfterSalesUI.refresh();});
   await p.waitForFunction(()=>__hold.entered);
   await p.evaluate(()=>{__actor={scope:'account-B',epoch:2};px.user={id:'account-B'};navigate('afterSalesCenter');__hold.release();});
   await p.waitForFunction(()=>document.querySelector('.af-page')&&!document.querySelector('[role=status]'));
   assert.equal(await p.locator('[data-af-case]').count(),0);assert(!(await p.locator('#app').innerText()).includes('合成物品外观检查'));
  });
  await check('四语375/430日夜64视图：实际藏文字体加载、表单和详情无横向溢出',async()=>{
   await p.evaluate(()=>{__actor={scope:'account-A',epoch:3};px.user={id:'account-A'};state.lang='en';navigate('afterSalesCenter');});
   await p.waitForTimeout(60);
   for(const screen of ['closed','center','request','detail']){
    if(screen==='closed'){await p.evaluate(()=>navigate('afterSalesCenter'));}
    if(screen==='center'){await p.locator('[data-af-action=environment]').click();await p.locator('[data-af-case=created-case]').waitFor();}
    if(screen==='request'){await p.evaluate(()=>AfterSalesUI.openOrder('order-A'));await p.locator('[data-af-form=request]').waitFor();}
    if(screen==='detail'){await p.evaluate(()=>{__case.history=['submit','accept','reject','return-shipping','inspect','unknown-fixture-event'].map((kind,i)=>({id:'fixture-event-'+i,kind,created:'2026-11-12T00:00:00Z',data:{}}));AfterSalesUI.openCase('created-case');});await waitDetail(p,'created-case');}
    for(const width of [375,430])for(const mode of ['day','night'])for(const lang of ['zh','zh-Hant','en','bo']){
     await p.setViewportSize({width,height:844});
     const seen=await p.evaluate(async({lang,mode})=>{state.lang=lang;state.mode=mode;render();let faces=[];
      if(lang==='bo'){faces=await document.fonts.load('16px "EW Tibetan"','བོད་ཡིག');await document.fonts.ready;if(!faces.length||faces.some(x=>x.status!=='loaded'))throw Error('Real Tibetan font missing');}
      return {overflow:document.documentElement.scrollWidth>innerWidth+2,font:getComputedStyle(document.querySelector('.af-page')).fontFamily,fontLoaded:lang!=='bo'||faces.every(x=>x.status==='loaded')};
     },{lang,mode});
     assert.equal(seen.overflow,false,[screen,width,mode,lang].join(' '));if(lang==='bo')assert(seen.font.includes('EW Tibetan'));
     if(screen==='detail'){
      const labels=await p.locator('[data-af-event-label]').allTextContents();assert.equal(labels.length,6);
      assert(labels.every(label=>!/(^|\b)(submit|accept|reject|return-shipping|inspect|unknown-fixture-event)(\b|$)/i.test(label)),'Controlled history labels must not expose API keys');
      assert.equal(labels[5],({zh:'状态已更新','zh-Hant':'狀態已更新',en:'Status updated',bo:'གནས་ཚུལ་གསར་སྒྱུར་བྱས།'})[lang]);
      assert((await p.locator('.af-page').evaluate(e=>parseFloat(getComputedStyle(e).paddingBottom)))>=144,'Scrollable footer space is part of the new page layout');
     }
     report.views.push({screen,width,mode,lang,...seen});
     if(screen==='detail'&&width===375&&mode==='night'){await p.waitForTimeout(700);await capture(p,'详情-'+lang);}
    }
   }
   assert.equal(report.views.length,64);
  });
  admin=await browser.newContext({viewport:{width:1280,height:900}});const a=await admin.newPage();activePage=a;a.on('pageerror',e=>report.errors.push(e.message));
  await check('后台真实受理表必须选择决定与理由，带版本/编号且不调用资金接口',async()=>{
   await fixture(a,'after-sales-admin.js');await a.evaluate(()=>{__case.status='submitted';__case.version=1;window.allowedNavs=()=>['dashboard','afterSales'];AfterSalesAdmin.install();});
   assert.equal(await a.evaluate(()=>allowedNavs({role:'operator'}).includes('afterSales')),false);assert.equal(await a.evaluate(()=>allowedNavs({role:'admin'}).includes('afterSales')),true);
   await a.evaluate(()=>AfterSalesAdmin.openCase('case-A'));await a.locator('[data-af-admin-form=decision]').waitFor();
   await a.locator('[name=decision]').selectOption('accept');await a.locator('[name=reason]').fill('合成验收流程审核');
   await a.locator('[data-af-admin-form=decision] button').click();await a.waitForFunction(()=>!document.querySelector('[data-af-admin-form=decision]'));
   const posted=(await calls(a,'POST','admin/after-sales/cases/case-A/decision')).at(-1).body;
   assert.equal(posted.version,1);assert.equal(posted.decision,'accept');assert(posted.requestId);assert.equal(await a.evaluate(()=>Object.getOwnPropertyDescriptor(window,'api').writable),false);
   assert.equal(await a.evaluate(()=>__calls.some(x=>x.path.includes('/refund'))),false);
  });
  await check('后台收货真实表默认入库0，唯一批次和判断依据原样提交，不自动退款',async()=>{
   await a.evaluate(()=>{__case.shipments=[{id:'fixture-shipping',carrier:'Synthetic',trackingNumber:'R-001',created:'2026-11-12T00:00:00Z'}];});
   await a.evaluate(()=>load('afterSales'));await a.locator('[data-af-admin-form=inspect]').waitFor();
   assert.equal(await a.locator('[name="restock:case-item-A"]').inputValue(),'0');
   await a.locator('[name=receiptReference]').fill('SYNTHETIC-RECEIPT-001');await a.locator('[name="received:case-item-A"]').fill('1');
   await a.locator('[name="condition:case-item-A"]').fill('合成破损物，不重新出售');await a.locator('[name=note]').fill('明确实收1，入库0');
   await a.locator('[data-af-admin-form=inspect] button').click();await a.waitForFunction(()=>document.querySelector('#main').textContent.includes('SYNTHETIC-RECEIPT-001'));
   const posted=(await calls(a,'POST','admin/after-sales/cases/case-A/inspect')).at(-1).body;
   assert.equal(posted.receiptReference,'SYNTHETIC-RECEIPT-001');assert.deepEqual(posted.items,[{caseItemId:'case-item-A',receivedQuantity:1,restockQuantity:0,condition:'合成破损物，不重新出售'}]);
   assert.equal(await a.evaluate(()=>__calls.some(x=>x.path.includes('/refund'))),false);await capture(a,'后台真实验收表');
  });
  await check('后台权限降级403清除缓存申请详情，不保留可操作表单',async()=>{
   await a.evaluate(()=>{__deny=true;});await a.evaluate(()=>load('afterSales'));
   await a.locator('[role=alert]').waitFor();assert.equal(await a.locator('[data-af-admin-detail]').count(),0);
   assert.equal(await a.locator('[data-af-admin-form=inspect]').count(),0);
  });
 }catch(e){report.fatal=e.stack||String(e);}
 finally{
  await user?.close().catch(()=>{});await admin?.close().catch(()=>{});await browser?.close().catch(()=>{});await new Promise(r=>server.close(r));
  report.identityUnchanged=JSON.stringify(before)===JSON.stringify(hashes());report.passed=report.results.filter(x=>x.pass).length;report.failed=report.results.filter(x=>!x.pass).length;
  report.pass=!report.fatal&&report.identityUnchanged&&!report.errors.length&&!report.failed&&report.passed===11&&report.views.length===64;
  const file=path.join(__dirname,'负责人优化建议-售后前端隔离专项.json');let runs=[];
  if(fs.existsSync(file)){const old=JSON.parse(fs.readFileSync(file,'utf8'));runs=old.runs||[old.latest||old];}
  runs.push(report);fs.writeFileSync(file,JSON.stringify({latest:report,runs},null,2)+'\n');
  console.log(JSON.stringify({pass:report.pass,passed:report.passed,failed:report.failed,errors:report.errors,fatal:report.fatal,views:report.views.length,file}));
  if(!report.pass)process.exitCode=1;
 }
})();

