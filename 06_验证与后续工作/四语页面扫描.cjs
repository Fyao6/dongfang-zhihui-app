
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'..'),r=path.join(root,'04_研发源码/app/r4'),pub=path.join(root,'04_研发源码/app/cloud/.netlify/public');
(async()=>{
const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:393,height:852},reducedMotion:'reduce'}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const seed=JSON.parse(fs.readFileSync(path.join(r,'backend/initial-content.json'),'utf8'));
await page.route('http://locale.test/**',route=>{const url=new URL(route.request().url());if(url.pathname==='/api/public')return route.fulfill({json:{content:seed,user:null,settings:{theme:{}},aiReady:false}});
if(url.pathname.startsWith('/api/'))return route.fulfill({json:{items:[],user:null}});
const file=path.join(pub,url.pathname==='/'?'index.html':url.pathname);if(!file.startsWith(pub)||!fs.existsSync(file))return route.fulfill({status:404});
return route.fulfill({path:file,contentType:file.endsWith('.html')?'text/html':file.endsWith('.ttf')?'font/ttf':file.endsWith('.png')?'image/png':file.endsWith('.mp4')?'video/mp4':undefined});});
await page.goto('http://locale.test/?lang=bo');await page.waitForTimeout(450);await page.evaluate(()=>document.fonts.ready);
const checks=await page.evaluate(async()=>{const out=[],residuals=[];for(const lang of ['zh','zh-Hant','en','bo']){state.lang=lang;
for(const key of Object.keys(screens)){try{state.page=key;await render(false);out.push({lang,page:key,overflow:document.getElementById('app').scrollWidth>document.getElementById('app').clientWidth+2,title:document.querySelector('#app h1')?.textContent});if(['en','bo'].includes(lang)){const w=document.createTreeWalker(document.getElementById('app'),NodeFilter.SHOW_TEXT);while(w.nextNode()){const el=w.currentNode.parentElement,s=w.currentNode.textContent.trim();if(el.closest('select,textarea,input,script,style')||!s||!el.getClientRects().length)continue;if(/[\u3400-\u9fff]/u.test(s)||lang==='bo'&&/[a-zA-Z]{3,}\s+[a-zA-Z]{3,}/.test(s))residuals.push({lang,page:key,text:s.slice(0,400)});}}}catch(e){out.push({lang,page:key,error:e.message});}}
}return {pages:out,residuals,missing:[...ewI18n.missing],used:[...ewI18n.used],font:document.fonts.check('18px "EW Tibetan"','ཤེས་རབ།')};});
for(const lang of ['zh','zh-Hant','en','bo']){await page.evaluate(async lang=>{state.lang=lang;state.page='home';await render();},lang);await page.screenshot({path:path.join(__dirname,'四语-首页-'+lang+'.png')});}
await page.evaluate(()=>{state.lang='bo';state.page='academy';render();});await page.screenshot({path:path.join(__dirname,'四语-藏文智慧馆.png')});
fs.writeFileSync(path.join(__dirname,'四语页面扫描.json'),JSON.stringify({...checks,errors,scope:'Isolated frontend with bundled seed; API integration verified separately.'},null,2));
console.log(JSON.stringify({pages:checks.pages.length,renderErrors:checks.pages.filter(x=>x.error),overflows:checks.pages.filter(x=>x.overflow).map(x=>x.lang+':'+x.page),missing:checks.missing.length,errors,font:checks.font},null,2));
await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

