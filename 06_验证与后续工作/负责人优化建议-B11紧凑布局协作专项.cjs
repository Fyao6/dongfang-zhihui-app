'use strict';
// Isolated real-browser test of new B11 UI hooks + actual core/archive/BaZi adapter.
// Synthetic account helpers only; not a real-account/full-app or typography acceptance.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto'),assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
const runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies'),{chromium}=require(path.join(runtime,'node/node_modules/playwright'));
const ROOT=path.resolve(__dirname,'..'),R4=path.join(ROOT,'04_研发源码/app/r4'),file=path.join(__dirname,'负责人优化建议-B11-WebLocks探针.html');
const sources=['vendor/lunar-1.7.7.js','life-chart-core.js','life-chart-bazi.js','bazi-result-version.js','bazi-result-version-ui.js'],hashes=()=>Object.fromEntries(sources.map(n=>[n,crypto.createHash('sha256').update(fs.readFileSync(path.join(R4,n))).digest('hex')]));
const before=hashes(),report={at:new Date().toISOString(),kind:'isolated real browser two-tab B11 hook verification',actualAdapter:'lunar-javascript 1.7.7',syntheticAccountContext:true,fullAPPTest:false,providerRequests:0,results:[]};
const html=fs.readFileSync(file),server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html;charset=utf-8'});res.end(html);});
(async()=>{
 let browser;
 try{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));browser=await chromium.launch({headless:true});report.browserVersion=browser.version();
  async function scenario(name,url){
   const context=await browser.newContext({acceptDownloads:true}),a=await context.newPage(),b=await context.newPage(),hold=await context.newPage(),r={environment:name,checks:[],errors:[]};report.results.push(r);
   for(const page of [a,b,hold])page.on('pageerror',e=>r.errors.push(e.message));
   const scope='fixture-B11-A',key='ew-life-charts-v1:'+scope,lock='ew-life-charts-write-v1:'+encodeURIComponent(scope);
   async function boot(p){
    await p.goto(url);await p.evaluate(()=>{
     document.body.innerHTML='<main id="app"></main><dialog id="sheet"></dialog><div id="toast"></div>';
     window.personalStorage={scope:'fixture-B11-A',epoch:1};window.state={page:'classicsWisdom',lang:'en',daily:{}};
     window.screens={lifeReview:()=>'<section>archive</section>'};window.__toasts=[];
     window.psToken=()=>({scope:personalStorage.scope,epoch:personalStorage.epoch});window.psCurrent=t=>t.scope!==null&&t.scope===personalStorage.scope&&t.epoch===personalStorage.epoch;
     window.flText=en=>en;window.esc=v=>String(v).replace(/[&<>"]/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[x]));
     window.pxTop=()=>'<header></header>';window.render=()=>{document.querySelector('#app').innerHTML=screens.classicsWisdom();};
     window.navigate=p=>{state.page=p;render();};window.toast=s=>{__toasts.push(s);document.querySelector('#toast').textContent=s;};
     window.sheet=(title,body,footer)=>{const d=document.querySelector('#sheet');d.innerHTML='<h2>'+title+'</h2>'+body+footer;d.open=true;};
     window.closeSheet=()=>{const d=document.querySelector('#sheet');d.open=false;d.innerHTML='';};
     const bs={archiveKind:null};window.lbState=()=>bs;
    });
    for(const n of sources)await p.addScriptTag({content:fs.readFileSync(path.join(R4,n),'utf8')});
    await p.evaluate(async()=>{
     window.__release={engine:{name:'lunar-javascript',version:'1.7.7'},ruleVersion:'fixture-implementation-only',adapterVersion:'fixture-actual-source',teacherConfirmed:false};
     screens.classicsWisdom=()=>'<section>'+lcResultActions('bazi')+'</section>';
     BaziVersionUI.install({manifest:__release});
     window.__n=lcNormalizeInput({name:'synthetic B11',date:'1990-06-15',time:'23:30',sex:'male',timezone:'Etc/GMT-8',ambiguity:'reject',latitude:'',longitude:'',place:''});
     window.__o={daySect:2,yunSect:2};window.__result=lcBaziCalculate(__n,__o);
     window.__fresh=()=>{const s=lcGet('bazi');Object.assign(s,{normalized:JSON.parse(JSON.stringify(__n)),options:JSON.parse(JSON.stringify(__o)),result:JSON.parse(JSON.stringify(__result)),selection:{},savedId:null,calculatedAt:Date.now()});delete s.b11Readonly;delete s.b11Record;delete s.b11Status;state.page='classicsWisdom';};
     if(!lcRecords().length){const row=await BaziResultVersion.captureCalculation({id:'original-fixture',normalized:__n,options:__o,result:__result,manifest:__release,capturedAt:'2021-01-02T03:04:05.000Z'});lcWriteRecords([row]);}
     __fresh();render();
    });
   }
   const current=()=>a.evaluate(()=>lcRecords()),raw=()=>a.evaluate(k=>localStorage.getItem(k),key);
   async function check(label,fn){try{await fn();r.checks.push({name:label,pass:true});console.log('PASS '+name+' '+label);}catch(e){r.checks.push({name:label,pass:false,error:e.stack||e.message});console.log('FAIL '+name+' '+label+': '+e.message);}}
   async function block(){await hold.evaluate(lock=>{window.__barrier={entered:false};void navigator.locks.request(lock,async()=>{__barrier.entered=true;await new Promise(resolve=>__barrier.release=resolve);});},lock);await hold.waitForFunction(()=>__barrier.entered);}
   async function queued(n){await hold.waitForFunction(async({lock,n})=>(await navigator.locks.query()).pending.filter(x=>x.name===lock).length>=n,{lock,n},{timeout:8000});}
   async function release(){await hold.evaluate(()=>__barrier.release());}
   async function open(p,id='original-fixture'){await p.evaluate(async id=>{state.page='lifeReview';await lcHandleAction('open','bazi',{dataset:{id}});},id);}
   async function recalc(p){await p.locator('[data-b11-action=recalculate-request]').click();await p.locator('[data-b11-action=recalculate-confirm]').click();}
   try{
    await Promise.all([boot(a),boot(b)]);await hold.goto(url);
    const original=JSON.stringify((await current()).find(x=>x.id==='original-fixture'));
    await check('two concurrent fresh saves serialize and preserve both new IDs',async()=>{
     await block();await Promise.all([a.evaluate(()=>{window.__save=lcHandleAction('save','bazi',{});}),b.evaluate(()=>{window.__save=lcHandleAction('save','bazi',{});})]);await queued(2);await release();
     await Promise.all([a.evaluate(()=>__save),b.evaluate(()=>__save)]);
     const rows=await current();assert.equal(rows.length,3);assert.equal(new Set(rows.map(x=>x.id)).size,3);assert(JSON.stringify(rows.find(x=>x.id==='original-fixture'))===original,'Original archive bytes/order changed');
    });
    await check('two explicit recomputations preserve both children and original timestamp',async()=>{
     await Promise.all([open(a),open(b)]);await block();await Promise.all([recalc(a),recalc(b)]);await queued(2);await release();
     await a.waitForFunction(()=>lcRecords().filter(r=>r.provenance?.parentRecordId==='original-fixture').length===2);
     await Promise.all([a.waitForFunction(()=>lcGet('bazi').b11Record?.provenance?.parentRecordId==='original-fixture'),b.waitForFunction(()=>lcGet('bazi').b11Record?.provenance?.parentRecordId==='original-fixture')]);
     const rows=await current();assert.equal(rows.length,5);assert(JSON.stringify(rows.find(x=>x.id==='original-fixture'))===original,'Original archive bytes/order changed');
    });
    await check('Bazi delete-confirm joins the same lock without dropping another tab save',async()=>{
     const rows=await current(),id=rows.find(x=>x.provenance?.parentRecordId==='original-fixture').id;
     await block();await a.evaluate(id=>{window.__delete=lcHandleAction('delete-confirm','bazi',{dataset:{id}});},id);await queued(1);
     await b.evaluate(()=>{__fresh();window.__save=lcHandleAction('save','bazi',{});});await queued(2);await release();
     await Promise.all([a.evaluate(()=>__delete),b.evaluate(()=>__save)]);
     const next=await current();assert.equal(next.length,rows.length);assert(!next.some(x=>x.id===id));assert(next.some(x=>!rows.some(y=>y.id===x.id)));
    });
    await check('account changes while queued prevent a stale archive append',async()=>{
     const before=await raw();await block();await b.evaluate(()=>{__fresh();window.__save=lcHandleAction('save','bazi',{});});await queued(1);
     await b.evaluate(()=>{personalStorage.scope='fixture-B11-B';personalStorage.epoch++;});await release();await b.evaluate(()=>__save);
     assert.equal(await raw(),before);assert.equal(await b.evaluate(()=>localStorage.getItem('ew-life-charts-v1:fixture-B11-B')),null);
     await b.evaluate(()=>{personalStorage.scope='fixture-B11-A';personalStorage.epoch++;__fresh();});
    });
    await check('deleting a queued child parent stops stale recomputation from resurrecting it',async()=>{
     await open(b);const before=await current();await block();
     await a.evaluate(()=>{window.__delete=lcHandleAction('delete-confirm','bazi',{dataset:{id:'original-fixture'}});});await queued(1);
     await recalc(b);await queued(2);await release();await a.evaluate(()=>__delete);
     await b.waitForFunction(()=>__toasts.some(x=>x.includes('original archive changed')));
     const next=await current();assert.equal(next.length,before.length-1);assert(!next.some(x=>x.id==='original-fixture'));
    });
    await check('no Web Locks means no save/delete; snapshots remain viewable and exportable',async()=>{
     const p=await context.newPage();await boot(p);const before=await raw(),id=(await current())[0].id;await open(p,id);
     await p.evaluate(()=>Object.defineProperty(navigator,'locks',{configurable:true,value:undefined}));
     await p.locator('[data-lc-action=save][data-kind=bazi]').click();
     await p.locator('[data-b11-action=recalculate-request]').click();assert.equal(await p.locator('[data-b11-action=recalculate-confirm]').count(),0);
     await p.evaluate(id=>lcHandleAction('delete-confirm','bazi',{dataset:{id}}),id);
     assert.equal(await raw(),before);assert.equal(await p.locator('[data-b11-write-support=unavailable]').count(),1);
     const d=p.waitForEvent('download');await p.locator('[data-lc-action=export][data-kind=bazi]').click();const downloaded=await d;assert(downloaded.suggestedFilename().includes(id));
     await p.close();
    });
   }catch(e){r.error=e.stack||e.message;}finally{await hold.evaluate(()=>window.__barrier?.release?.()).catch(()=>{});await context.close();}
  }
  await Promise.all([scenario('localhost','http://127.0.0.1:'+server.address().port+'/probe'),scenario('file',pathToFileURL(file).href)]);
 }catch(e){report.error=e.stack||e.message;}
 finally{await browser?.close();await new Promise(r=>server.close(r));report.sourceUnchanged=JSON.stringify(before)===JSON.stringify(hashes());report.sourceHashes=hashes();report.pass=!report.error&&report.sourceUnchanged&&report.results.every(r=>!r.error&&!r.errors.length&&r.checks.length===6&&r.checks.every(x=>x.pass));fs.writeFileSync(path.join(__dirname,'负责人优化建议-B11紧凑布局协作专项.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({pass:report.pass,results:report.results.map(r=>({environment:r.environment,error:r.error,errors:r.errors,checks:r.checks.map(x=>({name:x.name,pass:x.pass,error:x.error?.split('\n')[0]}))}))}));if(!report.pass)process.exitCode=1;}
})();

