
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium,request}=require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=path.resolve(__dirname,'..'),cloud=path.join(root,'04_研发源码/app/cloud'),base=process.argv[2]||'http://127.0.0.1:8878',remote=base.startsWith('https:'),results=[],errors=[];
let browser,admin,anon,created=[];
async function test(name,fn){try{await fn();results.push({name,pass:true});console.log('PASS '+name);}catch(e){results.push({name,pass:false,error:e.message});console.log('FAIL '+name+': '+e.message);}}
(async()=>{try{
browser=await chromium.launch({headless:true,args:['--no-proxy-server']});const context=await browser.newContext({viewport:{width:393,height:852},reducedMotion:'reduce',locale:'zh-CN'});const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
await page.goto(base+'/experience?lang=zh-Hans');await page.waitForFunction(()=>typeof px!=='undefined'&&px.loaded);await page.evaluate(()=>document.fonts.ready);
await test('首页四语言切换、HTML语言标记与刷新持久性',async()=>{
 for(const [key,tag,label]of[['zh-Hant','zh-Hant','首頁'],['en','en','Home'],['bo','bo','གཙོ་ངོས'],['zh','zh-Hans','首页']]){
  await page.evaluate(()=>navigate('home'));await page.locator('[data-action=ew-language-open]').click();
  assert.equal(await page.locator('[data-action=ew-language]').count(),4);
  await page.locator('[data-language="'+key+'"]').click();assert.equal(await page.locator('html').getAttribute('lang'),tag);
  assert((await page.locator('#nav').innerText()).includes(label));
  await page.reload();await page.waitForFunction(()=>px.loaded);assert.equal(await page.evaluate(()=>state.lang),key);
 }
});
await test('设置语言选项、原始聊天与收藏不被改写、计时不中断',async()=>{
 await page.evaluate(()=>{state.support.ai=[{id:'locale_fixture',role:'user',text:'我的原文 stays unchanged',at:new Date().toISOString()}];state.daily.favorites=[{type:'lesson',id:'academy-healing-video',at:new Date().toISOString()}];persist();navigate('profileSettings');});
 const saved=await page.evaluate(()=>JSON.stringify({ai:state.support.ai,favorites:state.daily.favorites}));
 const before=await page.evaluate(()=>tbSummary().totalMs);
 assert.equal(await page.locator('#language-select option').count(),4);
 await page.locator('#language-select').selectOption('bo');
 assert.equal(await page.evaluate(()=>JSON.stringify({ai:state.support.ai,favorites:state.daily.favorites})),saved);
 assert(await page.evaluate(()=>tbSummary().totalMs)>=before);
 await page.reload();await page.waitForFunction(()=>px.loaded);assert.equal(await page.evaluate(()=>JSON.stringify({ai:state.support.ai,favorites:state.daily.favorites})),saved);
});
await test('四语言课程搜索与分类筛选',async()=>{
 const result=await page.evaluate(()=>Object.keys(ewI18n.locales).map(lang=>{state.lang=lang;const lesson=academyCatalog.find(c=>c.id==='academy-healing-video'),title=ewI18n.content(lesson,'',lang);state.academyFilters={theme:'all',access:'all',format:'all',query:title};return {lang,found:academyResults().some(x=>x.id===lesson.id)};}));assert(result.every(x=>x.found),JSON.stringify(result));
 await page.evaluate(()=>{state.academyFilters={theme:'all',access:'all',format:'all',query:''};});
});
await test('藏文日期和本地完整字体',async()=>{
 await page.evaluate(()=>{state.lang='bo';navigate('checkin');});await page.evaluate(()=>document.fonts.ready);
 assert(await page.evaluate(()=>document.fonts.check('18px "EW Tibetan"','གཟའ་ཟླ་བ། སྒྲིག')));
 const dates=await page.evaluate(()=>[dateLabel(today()),ewFormatDate(new Date(),{weekday:'short'})]);
 assert(dates.every(s=>/[\u0F40-\u0FBC]/u.test(s)&&!/[月日周]/u.test(s)));
 const f=await page.request.get(base+'/assets/NotoSerifTibetan.woff2');if(remote||base.includes('8878'))assert.equal(f.status(),200);
});
await test('四语言主要页面在 360、393、430 像素布局及核心文字无裁切',async()=>{
 for(const width of[360,393,430]){await page.setViewportSize({width,height:852});for(const lang of['zh','zh-Hant','en','bo']){
  await page.evaluate(async lang=>{state.lang=lang;await navigate('home');},lang);
  const checks=await page.evaluate(()=>[...document.querySelectorAll('.home-map-copy>b')].map(el=>({text:el.textContent,clip:el.scrollWidth>el.clientWidth+1})));
  assert(!checks.some(x=>x.clip),lang+' '+width+' '+JSON.stringify(checks));
  for(const key of['home','academy','service','community','profile','body','mind','profileSettings']){await page.evaluate(key=>navigate(key),key);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),lang+' '+key+' '+width);}
 }}
});
await test('藏文关键术语、提示及未配置 AI 错误',async()=>{
 await page.evaluate(()=>{state.lang='bo';navigate('service');});
 const info=await page.evaluate(()=>({known:t('Restore yourself','修复自己'),error:ewI18n.error('AI服务尚未连接，请先在管理后台配置模型与凭据。',state.lang)}));
 assert.equal(info.known,'ལུས་སེམས་གསོ་སྐྱོང་།');assert(/[\u0f40-\u0fbc]/u.test(info.error)&&!/[未连接]/u.test(info.error));
 await page.evaluate(()=>state.lang='zh');assert((await page.evaluate(()=>ewI18n.error('AI服务尚未连接，请先在管理后台配置模型与凭据。',state.lang))).includes('尚未连接'));
});
if(!remote){
admin=await request.newContext({baseURL:base});anon=await request.newContext({baseURL:base});
const creds=JSON.parse(fs.readFileSync(path.join(cloud,'.env.test'),'utf8'));assert.equal((await admin.post('/api/auth/login',{data:creds})).status(),200);
await test('后台四语字段保存、课程章节和轮播同步、归档',async()=>{
 const id='locale_review_'+Date.now().toString(36),item={id,zh:'多语课程验证',en:'Locale verification course',hant:'多語課程驗證',bo:'སྐད་ཡིག་ཚོད་ལྟ།',summaryZh:'课程摘要',summaryEn:'Course summary',summaryHant:'課程摘要',summaryBo:'སློབ་ཚན་གནད་བསྡུས།',theme:'healing',format:'video',access:'public',goalsZh:['认识感受'],goalsEn:['Notice feelings'],goalsBo:['ཚོར་བ་ངོ་ཤེས།'],sections:[['章一','Chapter one','正文','Body']],sectionsBo:[['ས་བཅད་དང་པོ།','ནང་དོན་ཚོད་ལྟ།']]};
 created.push(['courses',item]);const response=await admin.post('/api/admin/content/courses',{data:{item,status:'published'}});assert.equal(response.status(),200);
 await page.evaluate(()=>pxBootstrap());await page.waitForFunction(id=>px.content.courses.some(x=>x.id===id),id);
 for(const lang of['zh','zh-Hant','en','bo']){await page.evaluate(({id,lang})=>{state.lang=lang;state.academyId=id;navigate('academyDetail');},{id,lang});assert((await page.locator('#app').innerText()).includes(({zh:item.zh,'zh-Hant':item.hant,en:item.en,bo:item.bo})[lang]));}
 await page.evaluate(id=>{state.lang='bo';state.lessonId=id;navigate('academyGuide');},id);assert((await page.locator('#app').innerText()).includes(item.sectionsBo[0][1]));
 const banner={id:id+'_banner',zh:'轮播测试',en:'Banner test',hant:'輪播測試',bo:'རེས་མོས་ཚོད་ལྟ།',bannerLabel:'广告',bannerLabelBo:'ཁྱབ་བསྒྲགས།',description:'说明',descriptionBo:'གསལ་བཤད།',buttonLabel:'阅读',buttonLabelBo:'ཀློག',target:'academy'};created.push(['quotes',banner]);
 assert.equal((await admin.post('/api/admin/content/quotes',{data:{item:banner,status:'published',position:-9999}})).status(),200);
 await page.evaluate(()=>pxBootstrap());await page.evaluate(id=>{state.lang='bo';state.quoteOffset=-px.content.quotes.findIndex(x=>x.id===id);navigate('home');},banner.id);
 // Rendering chooses a date-based quote; select the item's offset deterministically.
 const field=await page.evaluate(id=>{const b=px.content.quotes.find(x=>x.id===id);return [ewI18n.content(b,'',state.lang),ewI18n.field(b,'bannerLabel',state.lang),ewI18n.field(b,'description',state.lang)];},banner.id);
 assert.deepEqual(field,[banner.bo,banner.bannerLabelBo,banner.descriptionBo]);
 const ac=await browser.newContext({storageState:await admin.storageState(),viewport:{width:1280,height:900}}),ap=await ac.newPage();await ap.goto(base+'/admin');await ap.locator('.sidebar [data-nav=courses]').click();await ap.locator('[data-edit="'+id+'"]').click();assert.equal(await ap.locator('[name=bo]').inputValue(),item.bo);assert((await ap.locator('[name=sectionsBo]').inputValue()).includes('\n'));await ac.close();
 for(const[kind,value]of created){assert.equal((await admin.post('/api/admin/content/'+kind,{data:{item:value,status:'archived'}})).status(),200);}
 const publicContent=(await(await anon.get('/api/public')).json()).content;assert(!publicContent.courses.some(x=>x.id===id));created=[];
});
}
await test('电脑查看页语言控件与 iframe 四语联动',async()=>{
 await page.goto(base+'/app?lang=bo');const frame=page.frameLocator('#experience-frame');await frame.locator('[data-action=ew-language-open]').waitFor();assert.equal(await frame.locator('html').getAttribute('lang'),'bo');
 await page.locator('#review-language').selectOption('zh-Hant');await page.waitForTimeout(100);assert.equal(await frame.locator('html').getAttribute('lang'),'zh-Hant');
});
await test('浏览器无运行异常',async()=>assert.deepEqual(errors,[]));
}finally{
if(admin){for(const[kind,item]of created)await admin.post('/api/admin/content/'+kind,{data:{item,status:'archived'}}).catch(()=>{});await admin.dispose();}await anon?.dispose();await browser?.close();
const report={at:new Date().toISOString(),base,scope:remote?'Deployed read-only language checks':'Local full-stack language checks',pass:results.every(x=>x.pass),results,errors};
fs.writeFileSync(path.join(__dirname,remote?'四语公网验收.json':'四语专项联调.json'),JSON.stringify(report,null,2));if(!report.pass)process.exitCode=1;
}})().catch(e=>{console.error(e);process.exitCode=1});

