
const fs=require('fs'),path=require('path');const {chromium}=require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'..');
(async()=>{const browser=await chromium.launch({headless:true});const page=await browser.newPage();let html=fs.readFileSync(path.join(root,'03_当前APP/东方智慧-首页体验R4.html'),'utf8');html=html.replace("const t = (en, zh) => state.lang === 'zh' ? zh : en;","window.__localePairs=new Map();const t=(en,zh)=>{if(typeof zh==='string')window.__localePairs.set(zh,en);return state.lang==='zh'?zh:en;};");
await page.route('**/*',route=>route.request().url().endsWith('/experience')?route.fulfill({body:html,contentType:'text/html'}):route.abort());
await page.goto('http://localhost:9981/experience');await page.waitForTimeout(300);
const data=await page.evaluate(()=>{const errors=[];for(const [key,fn] of Object.entries(screens)){try{state.page=key;fn();}catch(e){errors.push([key,e.message]);}}return {pairs:[...window.__localePairs].map(([zh,en])=>({zh,en})),errors,pages:Object.keys(screens)};});
fs.writeFileSync(path.join(__dirname,'四语实际页面文案.json'),JSON.stringify(data,null,2));console.log(JSON.stringify({pairs:data.pairs.length,pages:data.pages.length,errors:data.errors},null,2));await browser.close();})().catch(e=>{console.error(e);process.exit(1)});

