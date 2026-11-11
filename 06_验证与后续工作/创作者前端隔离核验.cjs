// Browser fixtures only. No production requests or data mutations.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4'),origin='https://creator-ui.invalid';
const center=fs.readFileSync(path.join(r4,'creator-center.html'),'utf8');
let app=fs.readFileSync(path.join(root,'03_当前APP/东方智慧-首页体验R4.html'),'utf8');if(!app.includes('Creator surfaces and first-party analytics'))app=app.replace('</body>','<script>'+fs.readFileSync(path.join(r4,'creator-app.js'),'utf8')+'</script></body>');
const user={id:'creator-one',username:'creator_one',name:'隔离测试老师',role:'teacher'},profile={userId:user.id,displayName:'隔离测试老师',bio:'仅用于浏览器隔离验证，不会发布。',avatarUrl:'',teacherId:'teacher-one',status:'approved',reason:''};
const seed=JSON.parse(fs.readFileSync(path.join(r4,'backend/initial-content.json'),'utf8')),calls=[],checks=[],errors=[];
let signed=true,following=false,liked=false,favorited=false;
const works=[{id:'creator-work-one',ownerId:user.id,type:'article',title:'隔离图文作品',body:'这是实际接口渲染的测试作品。',theme:'healing',format:'article',status:'published',reason:'',version:1,createdAt:Date.now(),updatedAt:Date.now(),sections:[]}];
const data=()=>({days:7,totals:{followers:0,newFollowers:0,profileViews:0,impressions:0,views:0,plays:0,watchSeconds:0,completions:0,likes:0,favorites:0,shares:0,learners:0,consultations:0},daily:[{date:'2026-11-03',views:0},{date:'2026-11-04',views:0}],works:works.map(w=>({...w,views:0})),startedAt:Date.now()});
(async()=>{const browser=await chromium.launch({headless:true});try{
const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
await context.route('**/*',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname,m=req.method();if(url.origin!==origin)return route.abort();if(p==='/creator')return route.fulfill({contentType:'text/html',body:center});if(p==='/experience')return route.fulfill({contentType:'text/html',body:app});let body={items:[]},status=200;
const d=()=>req.postDataJSON();calls.push({p,m,...(m==='POST'||m==='PATCH'?{data:d()}: {})});
if(p==='/api/creator/me')body={user:signed?user:null,profile:signed?profile:null,eligible:signed};
else if(p==='/api/creator/works'&&m==='GET')body={items:works};
else if(p==='/api/creator/works'&&m==='POST'){const w={...d(),id:'creator-work-two',ownerId:user.id,version:1,status:'draft',createdAt:Date.now(),updatedAt:Date.now()};works.unshift(w);body={item:w}}
else if(p.endsWith('/submit')&&p.startsWith('/api/creator/works')){const w=works.find(x=>p.includes(x.id));w.status='manual_review';w.reason='AI 未配置，已转人工。';w.version++;body={item:w}}
else if(p.endsWith('/withdraw')){const w=works.find(x=>p.includes(x.id));w.status='draft';w.version++;body={item:w}}
else if(p.endsWith('/reviews'))body={items:[{stage:'ai',decision:'manual_review',reason:'AI 未配置，已转人工。',ruleVersion:1,created:Date.now()}]};
else if(p==='/api/creator/analytics')body=data();
else if(p==='/api/public')body={content:seed,user:signed?user:null,settings:{theme:{}},aiReady:false};
else if(p==='/api/auth/logout'){signed=false;body={ok:true}}
else if(p==='/api/auth/login'){signed=true;body={user}}
else if(p==='/api/creators/creator-one')body={profile,works:works.filter(w=>w.status==='published'),followers:following?1:0,following};
else if(p==='/api/creators/creator-one/follow'){following=d().active;body={ok:true}}
else if(p==='/api/creator-actions'){if(m==='POST'){if(d().action==='like')liked=d().active;if(d().action==='favorite')favorited=d().active}body={likes:liked?1:0,favorites:favorited?1:0,shares:0,liked,favorited}}
else if(p.startsWith('/api/time-bank/'))body={schemaVersion:2,accountId:user.id,zone:'Asia/Shanghai',clockBasis:'server',serverNow:Date.now(),running:true,runs:[],summary:{totalMs:0,todayMs:0,days:{}}};
await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)})});
const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(origin+'/creator');await page.locator('h1').filter({hasText:'创作工作台'}).waitFor();assert.equal(await page.locator('.metric strong').first().innerText(),'0');checks.push('真实零数据仪表盘正常渲染，无示例业绩');
for(const width of [1440,1024,390,360]){await page.setViewportSize({width,height:900});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('[data-tab=analytics]').first().click();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.locator('[data-tab=overview]').first().click()}checks.push('桌面、平板及360/390手机仪表盘和数据中心无横向溢出');
await page.setViewportSize({width:1440,height:1000});await page.locator('[data-do=new]').first().click();await page.locator('[name=type]').selectOption('article');await page.locator('[name=format]').selectOption('article');await page.locator('[name=title]').fill('真实表单草稿');await page.locator('[name=body]').fill('来自隔离 UI 表单的完整正文。');await page.locator('#work-form button[type=submit]').first().click();await page.locator('[data-submit=creator-work-two]').waitFor();assert.equal(works[0].status,'draft');await page.locator('[data-submit=creator-work-two]').click();await page.locator('[data-withdraw=creator-work-two]').waitFor();assert.equal(works[0].status,'manual_review');checks.push('新建作品表单保存并提交审核，展示真实人工复核状态');
await page.locator('[data-reviews=creator-work-two]').click();await page.locator('#dialog').waitFor();assert((await page.locator('#dialog').innerText()).includes('已转人工'));await page.locator('[data-do=close-dialog]').click();await page.locator('[data-withdraw=creator-work-two]').click();await page.locator('[data-confirm-withdraw=creator-work-two]').click();await page.locator('[data-submit=creator-work-two]').waitFor();assert.equal(works[0].status,'draft');checks.push('审核记录、撤回确认与草稿恢复');
await page.locator('[data-tab=overview]').first().click();await page.screenshot({path:path.join(__dirname,'创作者中心-工作台隔离预览.png'),fullPage:true});
await page.locator('[data-do=logout]').click();await page.locator('#login-form').waitFor();await page.locator('[name=username]').fill('creator_one');await page.locator('[name=password]').fill('FixtureOnly123!');await page.locator('#login-form button').click();await page.locator('[data-do=logout]').waitFor();checks.push('退出和 APP 账号登录流程');
const ap=await context.newPage();ap.on('pageerror',e=>errors.push(e.message));await ap.setViewportSize({width:390,height:844});await ap.goto(origin+'/experience');await ap.waitForFunction(()=>px.loaded);await ap.evaluate(()=>{tbSetVisible(false);navigate('profile')});assert.equal(await ap.locator('a[href="/creator"]').count(),1);checks.push('APP 我的页面创作者中心独立入口');
await ap.goto(origin+'/experience?page=creatorProfile&creator=creator-one');await ap.locator('[data-creator-open-work=creator-work-one]').waitFor();await ap.locator('[data-creator-open-work=creator-work-one]').click();await ap.locator('.creator-work-body').waitFor();assert((await ap.locator('.creator-work-body').textContent()).includes('测试作品'));await ap.locator('[data-creator-action=like]').click();await ap.waitForFunction(()=>document.querySelector('[data-creator-action=like]')?.getAttribute('aria-pressed')==='true');checks.push('创作者公开主页、图文详情及真实点赞请求');
for(const lang of ['zh','zh-Hant','en','bo']){await ap.evaluate(lang=>{state.lang=lang;render(false)},lang);assert(await ap.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))}checks.push('新增 APP 作品互动控件四语无横向溢出');
assert(calls.some(x=>x.p==='/api/creator-events'&&x.data?.event==='profile_view'));assert(calls.some(x=>x.p==='/api/creator-events'&&x.data?.event==='view'));assert.deepEqual(errors,[]);
const report={at:new Date().toISOString(),pass:true,scope:'Intercepted browser fixtures only, no production data changed',checks,errors};fs.writeFileSync(path.join(__dirname,'创作者前端隔离核验.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
