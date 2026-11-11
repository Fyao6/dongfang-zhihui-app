
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{pathToFileURL}=require('url');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{const b=await chromium.launch({headless:true});try{const p=await b.newPage({viewport:{width:390,height:844},reducedMotion:'reduce'}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(pathToFileURL(path.join(__dirname,'../03_当前APP/东方智慧-首页体验R4.html')).href);await p.evaluate(()=>navigate('academy'));
assert.equal(await p.locator('.at-teacher-card').count(),3);assert.equal(await p.locator('.at-demo').count(),3);
await p.locator('.at-teacher-card').first().click();assert.equal(await p.locator('.academy-course').count(),3);assert(await p.locator('.academy-course').evaluateAll(es=>es.every(e=>e.classList.contains('academy-theme-ziwei'))));
await p.locator('.academy-course').first().click();assert(await p.locator('.at-course-author').isVisible());await p.locator('.px-top [data-to=academyTeacher]').click();assert.equal(await p.locator('.academy-course').count(),3);
for(const lang of ['zh','zh-Hant','en','bo']){await p.evaluate(lang=>{state.lang=lang;navigate('academy');},lang);await p.evaluate(()=>document.fonts.ready);assert.equal(await p.locator('.at-teacher-card').count(),3);assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await p.screenshot({path:path.join(__dirname,'老师分类-'+lang+'.png')});}
await p.evaluate(()=>{state.lang='zh';navigate('academy')});await p.locator('#academy-search').fill('清和');assert.equal(await p.locator('.at-teacher-card').count(),1);
await p.locator('[data-action=at-view][data-view=courses]').click();assert.equal(await p.locator('.academy-course').count(),3);
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(__dirname,'老师分类页面核验.json'),JSON.stringify({at:new Date().toISOString(),pass:true,checks:['老师分类与示例标记','老师课程归属','课程详情返回老师','四语布局','按老师姓名搜索'],errors},null,2));console.log('PASS teacher collections, course attribution, return path, four locales and search');}finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});

