'use strict';
// Real two-tab Web Locks probe only; no app, credential, original storage or database is opened.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto'),assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
const runtime=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
const {chromium}=require(path.join(runtime,'node/node_modules/playwright'));
const file=path.join(__dirname,'负责人优化建议-B11-WebLocks探针.html'),runId=Date.now().toString(36)+'_'+crypto.randomBytes(3).toString('hex');
const report={at:new Date().toISOString(),runId,scope:'Owned synthetic pages, no actual app; browser semantics only',reference:'https://w3c.github.io/web-locks/',results:[]};
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const root=path.resolve(__dirname,'..'),sources=['life-chart-core.js','life-chart-bazi.js','life-birth-entry.js','bazi-time.js','bazi-result-version.js','bazi-result-version-ui.js'].map(n=>path.join(root,'04_研发源码/app/r4',n));
const before=Object.fromEntries(sources.map(p=>[path.relative(root,p),sha(p)]));
const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'});res.end(fs.readFileSync(file));});
(async()=>{
 let browser;
 try{
  await new Promise(r=>server.listen(0,'127.0.0.1',r));
  browser=await chromium.launch({headless:true});report.browserVersion=browser.version();
  async function scenario(name,url){
   const context=await browser.newContext(),a=await context.newPage(),b=await context.newPage(),key='b11-probe-storage:'+runId,lock='b11-probe-lock:'+runId;
   const r={name,urlKind:name,observations:{},checks:[]};report.results.push(r);
   try{
    await Promise.all([a.goto(url),b.goto(url)]);
    r.observations.features=await a.evaluate(()=>{let storage=false;try{const k='b11-probe-feature';localStorage.setItem(k,'1');localStorage.removeItem(k);storage=true;}catch{}return {isSecureContext,origin:location.origin,locks:typeof navigator.locks?.request==='function',localStorage:storage};});
    const check=(name,pass,observed)=>{r.checks.push({name,pass,observed});assert(pass,name);};
    await a.evaluate(({lock})=>{
     window.__hold={entered:false,done:false,error:null};
     window.__hold.promise=navigator.locks.request(lock,async()=>{window.__hold.entered=true;await new Promise(resolve=>window.__hold.release=resolve);}).then(()=>window.__hold.done=true).catch(e=>window.__hold.error={name:e.name,message:e.message});
    },{lock});
    await a.waitForFunction(()=>window.__hold.entered||window.__hold.error,{},{timeout:2000});
    const acquisition=await a.evaluate(()=>({entered:window.__hold.entered,error:window.__hold.error}));
    r.observations.acquisition=acquisition;
    if(!acquisition.entered){r.available=false;return;}
    r.available=true;check('actual exclusive lock acquired',true);
    const unavailable=await b.evaluate(lock=>navigator.locks.request(lock,{ifAvailable:true},value=>value===null),lock);
    check('same name in another tab is excluded',unavailable,unavailable);
    const other=await b.evaluate(lock=>navigator.locks.request(lock+':other-account',value=>!!value),lock);
    check('another account resource is independent',other,other);
    const aborted=await b.evaluate(async lock=>{let ran=false;const ac=new AbortController(),timer=setTimeout(()=>ac.abort(),80);try{await navigator.locks.request(lock,{signal:ac.signal},()=>{ran=true;});return {ran,error:null};}catch(e){return {ran,error:e.name};}finally{clearTimeout(timer);}},lock);
    check('queued request can abort without callback',!aborted.ran&&aborted.error==='AbortError',aborted);
    await a.evaluate(key=>localStorage.setItem(key,JSON.stringify([])),key);
    const storageShared=await b.evaluate(key=>localStorage.getItem(key)==='[]',key);
    r.observations.storageShared=storageShared;check('same URL tabs share synthetic storage',storageShared);
    await Promise.all([a.evaluate(key=>window.__stale=JSON.parse(localStorage.getItem(key)),key),b.evaluate(key=>window.__stale=JSON.parse(localStorage.getItem(key)),key)]);
    await a.evaluate(key=>localStorage.setItem(key,JSON.stringify([...window.__stale,'A'])),key);
    await b.evaluate(key=>localStorage.setItem(key,JSON.stringify([...window.__stale,'B'])),key);
    const lost=await a.evaluate(key=>JSON.parse(localStorage.getItem(key)),key);
    check('unlocked whole-array update demonstrates lost append',JSON.stringify(lost)==='["B"]',lost);
    await a.evaluate(key=>localStorage.setItem(key,'[]'),key);
    await b.evaluate(({key,lock})=>{
     window.__writer={entered:false,done:false,error:null};
     window.__writer.promise=navigator.locks.request(lock,()=>{window.__writer.entered=true;const rows=JSON.parse(localStorage.getItem(key));rows.push('B');localStorage.setItem(key,JSON.stringify(rows));}).then(()=>window.__writer.done=true).catch(e=>window.__writer.error=e.name);
    },{key,lock});
    await b.waitForTimeout(80);
    check('second writer remains queued',await b.evaluate(()=>!window.__writer.entered));
    await a.evaluate(key=>{const rows=JSON.parse(localStorage.getItem(key));rows.push('A');localStorage.setItem(key,JSON.stringify(rows));window.__hold.release();},key);
    await b.waitForFunction(()=>window.__writer.done||window.__writer.error);
    const merged=await a.evaluate(key=>JSON.parse(localStorage.getItem(key)),key);
    check('lock plus reread preserves both appended records',JSON.stringify(merged)==='["A","B"]',merged);
    const afterError=await a.evaluate(async lock=>{try{await navigator.locks.request(lock,()=>{throw Error('synthetic');});}catch{}return navigator.locks.request(lock,l=>!!l);},lock);
    check('throwing callback releases lock',afterError);
    await a.evaluate(lock=>{window.__closing={entered:false};void navigator.locks.request(lock,async()=>{window.__closing.entered=true;await new Promise(()=>{});});},lock);
    await a.waitForFunction(()=>window.__closing.entered);
    await b.evaluate(lock=>{window.__afterClose={entered:false};void navigator.locks.request(lock,()=>{window.__afterClose.entered=true;});},lock);
    await a.close();await b.waitForFunction(()=>window.__afterClose.entered,{},{timeout:2000});
    check('closing lock owner releases it for next tab',true);
   }catch(e){r.error=e.stack||e.message;r.available=r.available??false;}
   finally{await b.evaluate(key=>localStorage.removeItem(key),key).catch(()=>{});await context.close();}
  }
  await Promise.all([scenario('localhost','http://127.0.0.1:'+server.address().port+'/probe'),scenario('file',pathToFileURL(file).href)]);
 }catch(e){report.error=e.stack||e.message;}
 finally{
  await browser?.close();await new Promise(r=>server.close(r));
  const after=Object.fromEntries(sources.map(p=>[path.relative(root,p),sha(p)]));
  report.sourceUnchanged=JSON.stringify(before)===JSON.stringify(after);report.sourceHashes=after;
  report.pass=!report.error&&report.sourceUnchanged&&report.results.every(r=>!r.error&&r.checks.every(c=>c.pass));
  fs.writeFileSync(path.join(__dirname,'负责人优化建议-B11-WebLocks探针.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));if(!report.pass)process.exitCode=1;
 }
})();

