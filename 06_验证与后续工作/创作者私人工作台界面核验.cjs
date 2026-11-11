// UI privacy semantics: real browser with isolated API fixtures, never production.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),q=__dirname,r4=path.join(root,'04_研发源码/app/r4'),origin='https://creator-private-ui.invalid';
const html=fs.readFileSync(path.join(r4,'creator-center.html'),'utf8');
const sentinel='公开简介哨兵：只用于APP作者展示资料，不能替代工作台说明。';
const user={id:'private-owner',username:'private_creator',name:'工作台界面核验创作者',role:'teacher'};
const profile={userId:user.id,displayName:user.name,bio:sentinel,avatarUrl:'',teacherId:'private-teacher',status:'approved',reason:''};
const work={id:'private-work',ownerId:user.id,type:'article',title:'我的隔离测试作品',body:'仅验证编辑与发布说明。',mediaUrl:'',coverUrl:'',theme:'healing',format:'article',duration:0,categoryIds:[],sections:[],status:'published',reason:'',version:2,createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()};
const totals={followers:0,newFollowers:0,profileViews:0,impressions:0,views:0,plays:0,watchSeconds:0,completions:0,likes:0,favorites:0,shares:0,learners:0,consultations:0};
const checks=[],errors=[],calls=[],layouts=[];let browser;
(async()=>{try{
 browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});let signed=true;
 await context.route('**/*',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;if(url.origin!==origin)return route.abort();if(p==='/creator')return route.fulfill({contentType:'text/html; charset=utf-8',body:html});calls.push({method:req.method(),path:p});let data={items:[]};
  if(p==='/api/creator/me')data={user:signed?user:null,profile:signed?profile:null,eligible:signed};
  else if(p==='/api/creator/works')data={items:[work]};
  else if(p==='/api/creator/analytics')data={days:7,comparisonAvailable:false,totals,previousTotals:{},daily:Array.from({length:7},(_,i)=>({date:new Date(Date.now()-(6-i)*86400000).toISOString().slice(0,10),...totals})),works:[{...work,...totals}],startedAt:new Date().toISOString()};
  else if(p==='/api/public')data={content:{courseCategories:[]},user,settings:{theme:{}},aiReady:false};
  else if(p==='/api/auth/logout'){signed=false;data={ok:true};}
  else if(p==='/api/creator/profile'&&req.method()==='PATCH'){Object.assign(profile,req.postDataJSON());data={profile};}
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(origin+'/creator?userId=another-creator');await page.locator('.account-strip').waitFor();
 const summary=await page.locator('.account-strip').innerText();assert(summary.includes(user.username));assert(!summary.includes(sentinel));assert(!summary.includes('让学员了解'));assert(!summary.includes('分享东方智慧'));assert(/你|本人|当前/.test(summary));
 checks.push('账号首页使用私人工作台说明，不再展示公开简介或面向学员的个人宣传；URL不能切换为其他账号');
 await page.screenshot({path:path.join(q,'创作者私人工作台-首页-公开简介不外露.png'),fullPage:true});
 profile.bio='';await page.reload();await page.locator('.account-strip').waitFor();assert(!(await page.locator('.account-strip').innerText()).includes('完善个人简介，让学员了解'));checks.push('未填写公开简介时也保持私人工作台语境');
 const publicLink=page.locator('.sidebar-bottom a[href*="creatorProfile"]');assert.equal(await publicLink.count(),1);assert((await publicLink.innerText()).includes('APP'));assert((await publicLink.getAttribute('href')).includes(encodeURIComponent(user.id)));checks.push('对外资料预览明确指向APP作者展示页，和工作台入口区分');
 await page.locator('[data-tab=profile]:visible').first().click();await page.locator('#profile-form').waitFor();const settings=await page.locator('#content').innerText();assert(settings.includes(user.username));assert(settings.includes('APP'));assert(settings.includes('公开'));assert(/仅本人|登录账号|登录信息|账号信息/.test(settings));
 profile.bio=sentinel;await page.reload();await page.locator('.account-strip').waitFor();await page.locator('[data-tab=profile]:visible').first().click();await page.locator('#profile-form').waitFor();assert.equal(await page.locator('#profile-form [name=bio]').inputValue(),sentinel);checks.push('账号设置分清本人登录信息与APP作者公开展示资料，原资料仍可编辑');
 await page.screenshot({path:path.join(q,'创作者私人工作台-账号与APP资料分区.png'),fullPage:true});
 await page.locator('[data-tab=overview]:visible').first().click();const visitMetric=page.locator('[data-chart-metric=profileViews]').first();assert((await visitMetric.innerText()).includes('APP'));await visitMetric.click();assert((await page.locator('.chart-legend').first().innerText()).includes('APP'));checks.push('作者页访问指标明确统计APP公开页面，不混入后台访问');
 await page.locator('[data-tab=works]:visible').first().click();await page.locator('[data-edit="'+work.id+'"]').click();await page.locator('#work-form').waitFor();const editor=await page.locator('#content').innerText();assert(editor.includes('APP'));assert(/草稿/.test(editor));assert(/APP.*预览|预览.*APP|APP.*展示/.test(editor));assert((await page.locator('.editor-footer').innerText()).includes('APP'));checks.push('编辑器预览与审核后展示均明确为APP作品，草稿留在本人工作台');
 await page.locator('[data-tab=services]:visible').first().click();await page.locator('#guide-privacy summary').click();const privacy=await page.locator('#guide-privacy').innerText();assert(/本人|当前登录账号/.test(privacy));assert(privacy.includes('APP'));assert(privacy.includes('独立'));assert(!privacy.includes('公司授权人员开放'));checks.push('归属说明区分本人工作台和公司独立复核，不暗示其他人员进入创作者后台');
 for(const width of [1440,390,360]){await page.setViewportSize({width,height:900});for(const tab of ['overview','profile','analytics']){await page.locator('[data-tab='+tab+']:visible').first().click();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));layouts.push({width,tab,pass:true});}}checks.push('私人工作台首页、资料与数据页在桌面和手机均无横向溢出');
 for(const role of ['operator','reviewer']){signed=true;user.role=role;const before=calls.length;await page.goto(origin+'/creator');await page.getByRole('heading',{name:'请切换创作者账号',exact:true}).waitFor();assert.equal(await page.locator('#profile-form,.account-strip,#work-form').count(),0);assert((await page.locator('body').innerText()).includes('创作者账号'));assert(!calls.slice(before).some(c=>['/api/creator/works','/api/creator/analytics','/api/creator/consultations'].includes(c.path)));await page.locator('[data-do=logout]').click();await page.locator('#login-form').waitFor();}checks.push('运营与审核员账号即使被错误标记eligible也不显示入驻或私人工作台，且不请求数据；可退出切换创作者账号');
 assert(!calls.some(c=>c.path.startsWith('/api/admin/')));assert.deepEqual(errors,[]);const report={at:new Date().toISOString(),pass:true,scope:'Actual browser with isolated owner API fixtures; no production requests',checks,layouts,errors,sourceSha256:crypto.createHash('sha256').update(html).digest('hex'),builtCreatorSha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'03_当前APP/创作者中心.html'))).digest('hex')};fs.writeFileSync(path.join(q,'创作者私人工作台界面核验.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{await browser?.close();}})().catch(e=>{console.error(e.stack);process.exitCode=1});
