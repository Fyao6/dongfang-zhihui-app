// Isolated browser fixtures: no requests or changes to production data.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4'),origin='https://creator-admin-test.invalid';
const html=fs.readFileSync(path.join(r4,'time-bank-admin.html'),'utf8').replace('/*__CREATOR_ADMIN__*/',()=>fs.readFileSync(path.join(r4,'creator-admin.js'),'utf8'));
const profiles=[{userId:'teacher-a',username:'teacher_a',displayName:'待入驻老师',bio:'真实测试资料',status:'pending',teacherId:''}];
const works=[{id:'work-a',ownerId:'teacher-a',displayName:'待入驻老师',type:'article',title:'<img src=x onerror=window.XSS=1>',body:'测试正文\n第二段',status:'manual_review',version:3,reason:'AI无法判断，转人工复核',sections:[],updatedAt:new Date().toISOString()}];
let role='admin',conflict=false,settings={enabled:false,autoApprove:false,rules:'',knowledge:'',version:1,aiReady:false};const mutations=[],errors=[],checks=[];
(async()=>{const browser=await chromium.launch({headless:true,args:['--no-proxy-server']});try{
 const context=await browser.newContext({viewport:{width:1280,height:900}}),page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{const req=route.request(),url=new URL(req.url());if(url.origin!==origin)return route.abort();if(url.pathname==='/admin')return route.fulfill({contentType:'text/html',body:html});let data={},status=200;const p=url.pathname,m=req.method(),body=m==='GET'?{}:req.postDataJSON();
 if(p==='/api/auth/status')data={user:{id:'manager',name:'测试管理员',role},setupRequired:false};
 else if(p==='/api/admin/dashboard')data={counts:{}};
 else if(p==='/api/admin/creators')data={items:profiles};
 else if(p==='/api/admin/content/teachers')data={items:[{id:'teacher-profile',name:'已有真实老师',profileType:'real',_status:'published'},{id:'demo-profile',name:'示例老师',profileType:'demo'}]};
 else if(p==='/api/admin/creators/teacher-a'&&m==='PATCH'){mutations.push({p,body});Object.assign(profiles[0],body);data={profile:profiles[0]};}
 else if(p==='/api/admin/creator-reviews')data={items:works};
 else if(p==='/api/admin/creator-reviews/work-a'&&m==='GET')data={item:works[0],reviews:[{id:'r1',stage:'ai',decision:'manual',reason:'知识库未覆盖当前内容',ruleVersion:2,created:Date.now()}]};
 else if(p==='/api/admin/creator-reviews/work-a'&&m==='POST'){mutations.push({p,body});if(conflict){status=409;data={error:'作品版本已变化，请重新读取。'};}else{works[0].status=body.decision==='approve'?'published':'rejected';works[0].version++;data={item:works[0]};}}
 else if(p==='/api/admin/moderation-settings'&&m==='GET')data=settings;
 else if(p==='/api/admin/moderation-settings'&&m==='PUT'){mutations.push({p,body});settings={...settings,...body,version:settings.version+1};data=settings;}
 else{status=404;data={error:'Unexpected fixture request: '+p};}
 await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
 });
 await page.goto(origin+'/admin');await page.locator('[data-nav=creators]').click();await page.locator('[data-ca-profile]').click();assert.equal(await page.locator('[name=teacherId] option[value=demo-profile]').count(),0);
 await page.locator('#ca-profile-form [name=reason]').fill('已核对老师本人申请资料');await page.locator('#ca-profile-form button[value=approved]').click();await page.waitForFunction(()=>document.querySelector('tbody')?.textContent.includes('已开通'));
 assert.equal(profiles[0].status,'approved');checks.push('管理员审核入驻，屏蔽示例老师绑定，保存真实审核说明');
 await page.locator('[data-nav=creatorReviews]').click();await page.locator('[data-ca-review]').click();await page.locator('#ca-review-form').waitFor();assert.equal(await page.evaluate(()=>window.XSS),undefined);assert.equal(await page.locator('#ca-detail h2 img').count(),0);assert((await page.locator('.ca-history').innerText()).includes('规则版本 2'));checks.push('审阅内容转义，查看AI转人工原因和规则版本');
 conflict=true;await page.locator('#ca-review-form [name=reason]').fill('已完整审阅原始内容');await page.locator('#ca-review-form button[value=approve]').click();await page.waitForFunction(()=>document.querySelector('#ca-review-form .error')?.textContent.includes('版本已变化'));assert.equal(works[0].status,'manual_review');assert.equal(mutations.at(-1).body.version,3);checks.push('人工复核提交作品版本，冲突显示错误且不冒充发布成功');
 conflict=false;await page.locator('#ca-review-form button[value=approve]').click();await page.locator('[data-ca-filter=published]').click();await page.locator('[data-ca-review]').click();await page.locator('#ca-review-form').waitFor();assert.equal(await page.locator('#ca-review-form button[value=approve]').count(),0);assert.equal(await page.locator('#ca-review-form button[value=reject]').innerText(),'下架并说明原因');checks.push('审核通过刷新队列，已发布作品提供下架复核');
 await page.locator('[data-nav=moderation]').click();await page.locator('#ca-moderation-form').waitFor();assert((await page.locator('.ca-note').innerText()).includes('尚未就绪'));await page.locator('[name=enabled]').check();await page.locator('#ca-moderation-form button:not([type=button])').click();await page.waitForFunction(()=>document.querySelector('#ca-moderation-form .error')?.textContent.includes('知识库'));
 await page.locator('[name=rules]').fill('有明确依据可通过；无法判断转人工。');await page.locator('[name=knowledge]').fill('公司已核准的内容依据。');await page.locator('#ca-moderation-form button:not([type=button])').click();await page.waitForFunction(()=>document.querySelector('main')?.textContent.includes('当前规则版本 2'));assert.equal(settings.enabled,true);checks.push('未配置AI提示、规则知识完整性检查与版本更新');
 await page.setViewportSize({width:390,height:844});for(const nav of ['creators','creatorReviews','moderation']){await page.locator('[data-nav='+nav+']').click();await page.waitForTimeout(100);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}checks.push('三个新增后台页面手机宽度无溢出');
 await page.setViewportSize({width:1280,height:900});role='reviewer';await page.reload();await page.locator('[data-nav=creators]').waitFor();assert.equal(await page.locator('[data-nav=moderation]').count(),0);await page.locator('[data-nav=creators]').click();await page.locator('[data-ca-profile]').click();assert.equal(await page.locator('#ca-profile-form').count(),0);await page.locator('[data-nav=creatorReviews]').click();await page.locator('[data-ca-filter=published]').click();await page.locator('[data-ca-review]').click();await page.locator('#ca-review-form').waitFor();checks.push('审核员可审阅内容和查看创作者，无法修改资格或知识库');
 assert.deepEqual(errors,[]);await page.screenshot({path:path.join(__dirname,'创作者公司后台-隔离核验.png'),fullPage:true});
 const report={at:new Date().toISOString(),pass:true,scope:'Isolated browser API fixtures only; no production writes',checks,errors};fs.writeFileSync(path.join(__dirname,'创作者公司后台界面核验.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
