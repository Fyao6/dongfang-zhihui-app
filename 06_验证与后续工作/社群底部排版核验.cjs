const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const remote=process.argv[2],label=remote?'公网':'本地';
(async()=>{const browser=await chromium.launch({headless:true,args:['--no-proxy-server']});const results=[];try{
const p=await browser.newPage({viewport:{width:390,height:844},reducedMotion:'reduce',hasTouch:true}),errors=[];
p.on('pageerror',e=>errors.push(e.message));
await p.goto(remote?remote+'/experience?lang=zh-Hans':pathToFileURL(path.join(__dirname,'../03_当前APP/东方智慧-首页体验R4.html')).href);
if(remote)await p.waitForFunction(()=>px.loaded);
await p.evaluate(()=>{tbSetVisible(false);navigate('community')});
await p.waitForFunction(()=>document.querySelector('.cf-video-card video').readyState>=2);
await p.waitForTimeout(3500);
for(const viewport of [{width:360,height:740},{width:390,height:844},{width:550,height:850}]){
 await p.setViewportSize(viewport);
 for(const lang of ['zh','zh-Hant','en','bo']){
  await p.evaluate(lang=>{state.lang=lang;render(false)},lang);await p.evaluate(()=>document.fonts.ready);
  const metrics=await p.locator('.cf-video-card').first().evaluate(card=>{
   const box=card.getBoundingClientRect(),cap=card.querySelector('.cf-caption').getBoundingClientRect(),bar=card.querySelector('.cf-playback'),br=bar.getBoundingClientRect();
   return {bottomGap:box.bottom-br.bottom,captionGap:box.bottom-cap.bottom,leftGap:cap.left-box.left,trackHeight:parseFloat(getComputedStyle(bar,':before').height),timeOpacity:getComputedStyle(bar.querySelector('.cf-time')).opacity,extraButtons:bar.querySelectorAll('button').length,inside:cap.top>box.top+70&&cap.right<box.right,overflow:document.documentElement.scrollWidth>innerWidth};
  });
  assert(Math.abs(metrics.bottomGap)<1);assert(metrics.captionGap>=26&&metrics.captionGap<=30);assert(metrics.leftGap>=16&&metrics.leftGap<=20);assert.equal(metrics.trackHeight,2);assert.equal(metrics.timeOpacity,'0');assert.equal(metrics.extraButtons,0);assert(metrics.inside&&!metrics.overflow);
  results.push({viewport,lang,pass:true,metrics});
  if(viewport.width===390)await p.screenshot({path:path.join(__dirname,'社群底部布局-'+label+'-'+lang+'.png')});
 }
}
await p.setViewportSize({width:390,height:844});await p.evaluate(()=>{state.lang='zh';render(false)});await p.waitForFunction(()=>!document.querySelector('[data-cf-seek]').disabled);
const range=p.locator('[data-cf-seek]').first(),box=await range.boundingBox();
await p.mouse.move(box.x+box.width*.2,box.y+box.height/2);await p.mouse.down();assert(await p.locator('.cf-playback').first().evaluate(e=>e.classList.contains('is-seeking')));
await p.mouse.move(box.x+box.width*.68,box.y+box.height/2,{steps:8});
assert(await p.locator('video').first().evaluate(v=>v.currentTime/v.duration>.6));
assert.equal(await p.locator('.cf-time').first().evaluate(e=>getComputedStyle(e).opacity),'1');
await p.screenshot({path:path.join(__dirname,'社群底部布局-'+label+'-拖动.png')});
await p.mouse.up();await p.mouse.move(5,150);await range.evaluate(e=>e.blur());await p.waitForTimeout(180);
assert.equal(await p.locator('.cf-time').first().evaluate(e=>getComputedStyle(e).opacity),'0');
await range.focus();const before=Number(await range.inputValue());await p.keyboard.press('ArrowRight');assert(Number(await range.inputValue())>before);assert((await range.getAttribute('aria-valuetext')).includes('/'));
await range.evaluate(e=>e.blur());
const cdp=await p.context().newCDPSession(p);
await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+box.width*.3,y:box.y+box.height/2}]});
await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:box.x+box.width*.8,y:box.y+box.height/2}]});
await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
assert(await p.locator('video').first().evaluate(v=>v.currentTime/v.duration>.7));
assert.equal(await p.locator('.cf-playback.is-seeking').count(),0);
await p.waitForFunction(()=>!document.querySelector('.cf-video-card video').paused);await p.locator('.cf-stage-toggle').first().click();assert(await p.locator('video').first().evaluate(v=>v.paused));await p.locator('.cf-stage-toggle').first().click();await p.waitForFunction(()=>!document.querySelector('.cf-video-card video').paused);
assert.deepEqual(errors,[]);
fs.writeFileSync(path.join(__dirname,'社群底部布局-'+label+'核验.json'),JSON.stringify({at:new Date().toISOString(),pass:true,results,interactionChecks:['鼠标实际拖动','触摸实际拖动','键盘调整与读屏时间','交互时显示时间和滑块，结束隐藏','点击画面播放暂停'],errors},null,2));
console.log('PASS '+label+' bottom progress, caption placement, 12 locale/viewport layouts, mouse/touch/keyboard seeking.');
}finally{await browser.close();}})().catch(e=>{console.error(e.stack);process.exitCode=1});

