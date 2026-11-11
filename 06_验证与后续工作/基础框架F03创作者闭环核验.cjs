// F03 source/built fault injection and isolated real-service acceptance; loopback only.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('node:assert/strict');
const {chromium,request}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4'),web=path.join(root,'03_当前APP'),cloud=path.join(root,'04_研发源码/app/cloud'),args=process.argv.slice(2);
const value=name=>{const i=args.indexOf(name);return i<0?'':args[i+1]||''};
const sourceProbe=args.includes('--source-probe'),probe=args.includes('--probe'),cloudReport=args.includes('--cloud-report'),base=value('--base').replace(/\/$/,'');
const digest=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const sourcePaths=['04_研发源码/app/r4/creator-center.html','04_研发源码/app/r4/creator-admin.js','04_研发源码/app/r4/creator-app.js','04_研发源码/app/cloud/lib/creator-api.ts','04_研发源码/app/r4/backend/creator.py','04_研发源码/app/r4/base.js','04_研发源码/app/r4/platform.js','04_研发源码/app/r4/build.py','04_研发源码/app/cloud/prepare.py'];
const identities=()=>({
 sourceHashes:Object.fromEntries(sourcePaths.map(p=>[p,digest(path.join(root,p))])),
 buildHashes:sourceProbe?{}:Object.fromEntries(['东方智慧-首页体验R4.html','发给负责人-东方智慧首页R4.html','计时后台-开发联调.html','创作者中心.html'].map(p=>[p,digest(path.join(web,p))])),
 cloudBuildHashes:sourceProbe?{}:Object.fromEntries(['generated/experience.html','generated/review.html','generated/admin.html','generated/creator.html','worker/index.ts','lib/eastern-api.ts','dist/server/index.js'].map(p=>[p,digest(path.join(cloud,p))]))
});
const reportName='基础框架F03创作者闭环核验-'+(sourceProbe?'源码预检':(cloudReport?'云端':'本机')+(probe?'-probe':''))+'.json',reportFile=path.join(__dirname,reportName);
function appendReport(run){let runs=[];if(fs.existsSync(reportFile))try{const old=JSON.parse(fs.readFileSync(reportFile,'utf8'));runs=old.runs||[old.latest||old]}catch{}runs.push(run);fs.writeFileSync(reportFile,JSON.stringify({latest:run,runs},null,2)+'\n')}


async function creatorWriteFailureSuite({browser,html,origin='https://f03-center.invalid',poster}) {
 const context=await browser.newContext({viewport:{width:1280,height:900}});
 const user={id:'f03-creator',username:'f03_creator',name:'隔离创作者',role:'teacher'};
 const profile={userId:user.id,displayName:user.name,bio:'隔离验证',avatarUrl:'',teacherId:'f03-teacher',status:'approved',reason:''};
 const calls=[],works=[];let saveGate=null,uploadGate=null,submitFailures=0,analyticsFailures=0,uploadFailures=0;
 const mediaUrl='/api/media/33333333-3333-4333-8333-333333333333';
 const analytics=()=>({days:7,comparisonAvailable:false,totals:{},daily:[],works:[]});
 const defer=()=>{let release;const promise=new Promise(r=>release=r);return {promise,release}};
 await context.route('**/*',async route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname,m=req.method();
  if(u.origin!==origin)return route.abort();
  if(p==='/creator')return route.fulfill({contentType:'text/html; charset=utf-8',body:html});
  if(p.startsWith('/api/media/')&&m==='GET')return route.fulfill({contentType:'image/png',body:poster});
  const data=(req.headers()['content-type']||'').includes('application/json')?req.postDataJSON():{};
  calls.push({p,m,data});let body={},status=200;
  if(p==='/api/creator/me')body={user,profile,eligible:true};
  else if(p==='/api/creator/works'&&m==='GET')body={items:works};
  else if(p==='/api/creator/analytics'){if(analyticsFailures-->0){status=503;body={error:'隔离统计读取失败'}}else body=analytics()}
  else if(p==='/api/creator/consultations')body={items:[]};
  else if(p==='/api/public')body={content:{courseCategories:[]},user,aiReady:false};
  else if(p==='/api/media'&&m==='POST'){
   if(uploadGate)await uploadGate.promise;
   if(uploadFailures-->0){status=503;body={error:'隔离上传失败'}}else body={url:mediaUrl};
  }else if(p==='/api/creator/works'&&m==='POST'){
   if(saveGate)await saveGate.promise;
   const item={...data,id:'f03-'+(works.length+1),ownerId:user.id,status:'draft',reason:'',version:1,createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()};
   works.unshift(item);body={item};
  }else if(p.startsWith('/api/creator/works/')){
   const id=p.split('/')[4],item=works.find(w=>w.id===id);
   if(!item){status=404;body={error:'作品不存在'}}
   else if(data.version!==item.version){status=409;body={error:'隔离版本冲突'}}
   else if(p.endsWith('/submit')){
    if(submitFailures-->0){status=503;body={error:'隔离提交失败'}}
    else {item.status='manual_review';item.version++;body={item}}
   }else if(m==='PATCH'){Object.assign(item,data,{status:'draft',version:item.version+1});body={item}}
  }else {status=404;body={error:'隔离路由未覆盖'};}
  await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 const page=await context.newPage();await page.goto(origin+'/creator');
 await page.locator('[data-tab=works]:visible').first().waitFor();
 const publish=async title=>{
  await page.locator('[data-tab=overview]:visible').first().click();
  await page.locator('[data-publish=article]:visible').first().click();
  await page.locator('#work-form [name=title]').fill(title);
  await page.locator('#work-form [name=body]').fill('隔离验证正文，不进入生产环境。');
 };
 const postCount=()=>calls.filter(c=>c.p==='/api/creator/works'&&c.m==='POST').length;
 // Delay the acknowledgement, then attempt the second actual submit control.
 await publish('隔离并发保存');saveGate=defer();const arriving=page.waitForRequest(r=>r.url().endsWith('/api/creator/works')&&r.method()==='POST');
 await page.locator('#work-form button[type=submit]').first().click();await arriving;
 assert.equal(await page.locator('#work-form button[name=submitAfter]').isDisabled(),true);
 await page.locator('#work-form').evaluate(form=>form.requestSubmit(form.querySelector('[name=submitAfter]')));
 saveGate.release();saveGate=null;await page.locator('#work-results').waitFor();
 assert.equal(postCount(),1);assert.equal(works.length,1);
 // Acknowledged draft must retain its id/version when only submission fails.
 await publish('隔离提交失败恢复');submitFailures=1;
 await page.locator('#work-form button[name=submitAfter]').click();
 await page.locator('#work-form .statusline').filter({hasText:'草稿已保存'}).waitFor();
 const beforeRetry=postCount(),draftId=works[0].id;
 await page.locator('#work-form button[name=submitAfter]').click();await page.locator('#work-results').waitFor();
 assert.equal(postCount(),beforeRetry);assert.equal(works.find(w=>w.id===draftId).status,'manual_review');
 assert(calls.some(c=>c.p==='/api/creator/works/'+draftId&&c.m==='PATCH'));
 // Failed follow-up reads must not turn an acknowledged save into a failed write.
 await publish('隔离统计失败');analyticsFailures=1;
 await page.locator('#work-form button[type=submit]').first().click();await page.locator('#work-results').waitFor();
 assert(works.some(w=>w.title==='隔离统计失败'));
 await page.getByText(/草稿已保存；列表或数据暂未刷新/).waitFor();
 // Upload gate: no save is possible until the new URL is available.
 await publish('隔离上传等待');uploadGate=defer();const uploading=page.waitForRequest(r=>r.url().endsWith('/api/media')&&r.method()==='POST');
 await page.locator('[data-upload=coverUrl]').setInputFiles({name:'f03.png',mimeType:'image/png',buffer:poster});await uploading;
 assert.equal(await page.locator('#work-form button[type=submit]').first().isDisabled(),true);
 assert.equal(await page.locator('#work-form button[name=submitAfter]').isDisabled(),true);
 const beforeUpload=postCount();await page.locator('#work-form').evaluate(form=>form.requestSubmit());
 assert.equal(postCount(),beforeUpload);uploadGate.release();uploadGate=null;
 await page.waitForFunction(url=>document.querySelector('#work-form [name=coverUrl]')?.value===url,mediaUrl);
 await page.locator('#work-form button[type=submit]').first().click();await page.locator('#work-results').waitFor();
 assert.equal(works[0].coverUrl,mediaUrl);
 // Failed uploads recover the controls and permit retrying the same local file.
 await publish('隔离上传失败');uploadFailures=1;
 const file={name:'same-file.png',mimeType:'image/png',buffer:poster};
 await page.locator('[data-upload=coverUrl]').setInputFiles(file);
 await page.locator('.upload-status').filter({hasText:'隔离上传失败'}).waitFor();
 assert.equal(await page.locator('#work-form [name=coverUrl]').inputValue(),'');
 assert.equal(await page.locator('#work-form button[type=submit]').first().isEnabled(),true);
 await page.locator('[data-upload=coverUrl]').setInputFiles(file);
 await page.waitForFunction(url=>document.querySelector('#work-form [name=coverUrl]')?.value===url,mediaUrl);
 await context.close();
 return ['表单并发保存只创建一份作品','已保存后提交失败沿同id/version恢复','统计读取失败不误报保存失败','上传未完成不保存旧素材','失败上传保留旧值并可重试同文件'];
}

async function actualF03Suite({browser,base,results,errors}) {
 const owned=[],runId=Date.now().toString(36),password=crypto.randomBytes(18).toString('hex');
 const api=async(ctx,route,data,method=data===undefined?'GET':'POST',status=200)=>{
  const response=await ctx.fetch(base+'/api/'+route,{method,...(data===undefined?{}:{data})});
  const body=await response.json();assert.equal(response.status(),status,route+': '+JSON.stringify(body));return body;
 };
 const step=async(name,fn)=>{try{await fn();results.push({name,pass:true});console.log('PASS '+name)}catch(error){results.push({name,pass:false,error:error.message});throw error}};
 const requestContext=async()=>{const c=await request.newContext();owned.push(c);return c};
 const browserContext=async options=>{const c=await browser.newContext({viewport:{width:1280,height:900},reducedMotion:'reduce',...options});owned.push(c);return c};
 const admin=await requestContext();let shared,app,center,company;
 const gate=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}};
 const settle=async page=>{await page.evaluate(()=>new Promise(r=>setTimeout(r,60)))};
 const makeTeacher=async label=>{
  const context=await browserContext(),username='f03_'+label+'_'+runId,name='F03 '+label;
  const account=(await api(context.request,'auth/register',{username,password,name})).user;
  await api(context.request,'creator/apply',{displayName:name,bio:'隔离F03真实HTTP资料',avatarUrl:''});
  await api(admin,'admin/creators/'+account.id,{status:'approved',reason:'隔离F03开通'},'PATCH');
  const me=await api(context.request,'creator/me');assert.equal(me.user.role,'teacher');
  return {context,username,password,id:me.user.id,name,profile:me.profile};
 };
 const makeWork=async(account,title,status='manual_review')=>{
  const saved=await api(account.context.request,'creator/works',{type:'article',format:'article',theme:'healing',title,body:'F03隔离真实作品正文',mediaUrl:'',coverUrl:'',duration:0,categoryIds:[],sections:[]});
  const submitted=await api(account.context.request,'creator/works/'+saved.item.id+'/submit',{version:saved.item.version});
  assert.equal(submitted.item.status,'manual_review','AI关闭时真实提交必须进入人工复核');
  if(status==='manual_review')return submitted.item;
  return (await api(admin,'admin/creator-reviews/'+saved.item.id,{version:submitted.item.version,decision:status==='published'?'approve':'reject',reason:'隔离F03人工'+status})).item;
 };
 const centerReady=async account=>center.waitForFunction(id=>state.me?.user?.id===id&&!!document.querySelector('[data-tab=works]'),account.id);
 const appReady=async account=>app.waitForFunction(id=>px.loaded&&px.user?.id===id&&personalStorage.scope===id,account.id);
 const appSetActor=async account=>{
  const current=await api(shared.request,'auth/status');if(current.user?.id!==account.id)await api(shared.request,'auth/login',{username:account.username,password});
  await app.evaluate(async()=>{pxInvalidateBootstrap();await pxBootstrap(true);psBroadcastIdentity()});
  await appReady(account);await centerReady(account);
 };
 const centerLogin=async account=>{
  const logout=center.locator('[data-do=logout]:visible').first();if(await logout.count()){await logout.click();await center.locator('#login-form').waitFor()}
  await center.locator('#login-form [name=username]').fill(account.username);
  await center.locator('#login-form [name=password]').fill(password);
  await center.locator('#login-form button[type=submit]').click();
 };
 const delayed=async(page,pattern,{method='GET',reject=false}={})=>{
  const arrived=gate(),release=gate(),completed=gate();let captured=false;
  const handler=async route=>{
   if(captured||route.request().method()!==method)return route.continue();
   captured=true;try{const response=reject?null:await route.fetch();arrived.resolve();await release.promise;if(reject)await route.abort('failed');else await route.fulfill({response});}finally{completed.resolve()}
  };
  await page.route(pattern,handler);
  return {arrived:arrived.promise,async finish(){release.resolve();await completed.promise;await settle(page);await page.unroute(pattern,handler)}};
 };
 try{
  const status=await api(admin,'auth/status');
  if(status.setupRequired)await api(admin,'auth/setup',{username:'f03_admin_'+runId,password,name:'F03隔离管理员'});
  else{
   const credentialsFile=value('--credentials-file')||(cloudReport?path.join(cloud,'.env.local-test'):'');
   const credentials=credentialsFile?JSON.parse(fs.readFileSync(credentialsFile,'utf8')):{username:'reg_admin',password:'Regression_Only_2026'};
   await api(admin,'auth/login',credentials);
  }
  const moderation=await api(admin,'admin/moderation-settings');
  await api(admin,'admin/moderation-settings',{enabled:false,autoApprove:false,rules:moderation.rules||'',knowledge:moderation.knowledge||''},'PUT');
  const target=await makeTeacher('target'),a=await makeTeacher('actor_a'),b=await makeTeacher('actor_b');
  shared=a.context;
  let published,reviewA,reviewB;
  await step('真实人工提交/审核/APP发布及成熟12指标入口保留',async()=>{
   published=await makeWork(target,'F03已发布-'+runId,'published');
   reviewA=await makeWork(target,'F03待审A-'+runId);reviewB=await makeWork(target,'F03待审B-'+runId);
   const publicProfile=await api(b.context.request,'creators/'+target.id);
   assert(publicProfile.works.some(w=>w.id===published.id));
   assert(!publicProfile.works.some(w=>[reviewA.id,reviewB.id].includes(w.id)));
   center=await shared.newPage();app=await shared.newPage();
   await Promise.all([center.goto(base+'/creator'),app.goto(base+'/experience?lang=zh')]);
   await centerReady(a);await appReady(a);
   await center.locator('[data-tab=analytics]:visible').first().click();
   assert.equal(await center.locator('[data-chart-metric]').count(),12);
  });
  await step('申诉1000字接受/1001字拒绝且未越过人工审核',async()=>{
   const accepted=await makeWork(target,'F03申诉允许-'+runId,'rejected');
   const denied=await makeWork(target,'F03申诉超限-'+runId,'rejected');
   const result=await api(target.context.request,'creator/works/'+accepted.id+'/appeal',{version:accepted.version,reason:'申'.repeat(1000)});
   assert.equal(result.item.status,'manual_review');
   await api(target.context.request,'creator/works/'+denied.id+'/appeal',{version:denied.version,reason:'申'.repeat(1001)},'POST',400);
   const works=await api(target.context.request,'creator/works');assert.equal(works.items.find(w=>w.id===denied.id).status,'rejected');
  });
  await step('重复开通保留老师推荐/特长/多语及登录字段，新老师默认不推荐',async()=>{
   let current=(await api(admin,'admin/content/teachers')).items.find(t=>t.id===target.profile.teacherId);
   const item=Object.fromEntries(Object.entries(current).filter(([key])=>!key.startsWith('_')));
   Object.assign(item,{recommended:true,specialty:'F03平台特长',specialtyEn:'F03 specialty',bioEn:'F03 translated bio'});
   await api(admin,'admin/content/teachers',{item,status:'published'});
   const before=(await api(admin,'admin/content/teachers')).items.find(t=>t.id===item.id);
   const loginBefore=(await api(target.context.request,'auth/status')).user;
   await api(admin,'admin/creators/'+target.id,{status:'approved',teacherId:item.id,reason:'F03保留运营资料'},'PATCH');
   const after=(await api(admin,'admin/content/teachers')).items.find(t=>t.id===item.id);
   for(const key of Object.keys(before).filter(key=>!key.startsWith('_')))assert.deepEqual(after[key],before[key],key);
   assert.deepEqual((await api(target.context.request,'auth/status')).user,loginBefore);
   assert.equal((await api(admin,'admin/content/teachers')).items.find(t=>t.id===b.profile.teacherId).recommended,false);
  });
  await step('APP实际退出/登录B的nonce清除独立中心A编辑，中心登录A同步APP',async()=>{
   await center.locator('[data-tab=overview]:visible').first().click();
   await center.locator('[data-publish=article]:visible').first().click();
   const secret='A旧编辑仅本人-'+runId;
   await center.locator('#work-form [name=title]').fill(secret);
   await app.evaluate(()=>navigate('account'));
   await app.locator('[data-action=px-logout]').click();await app.locator('#px-account-form').waitFor();
   await app.locator('#px-account-form [name=username]').fill(b.username);
   await app.locator('#px-account-form [name=password]').fill(password);
   await app.locator('#px-account-form button[value=login]').click();
   await appReady(b);await centerReady(b);
   assert.equal(await center.locator('#work-form').count(),0);
   assert(!(await center.locator('body').innerText()).includes(secret));
   assert.equal(await center.evaluate(()=>state.editing),null);
   await centerLogin(a);await centerReady(a);await appReady(a);
  });
  await step('学生/内部账号从独立中心登录保持实际角色和适当提示',async()=>{
   const student=await requestContext(),operator=await requestContext();
   const studentName='f03_student_'+runId,operatorName='f03_operator_'+runId;
   const studentUser=(await api(student,'auth/register',{username:studentName,password,name:'F03学生'})).user;
   const operatorUser=(await api(operator,'auth/register',{username:operatorName,password,name:'F03内部账号'})).user;
   await api(admin,'admin/users/'+operatorUser.id,{role:'operator'},'PATCH');
   await centerLogin({username:studentName});await center.locator('#profile-form').waitFor();
   assert.equal(await center.evaluate(()=>state.me.user.role),'user');assert.equal(await center.evaluate(()=>state.me.eligible),false);
   await centerLogin({username:operatorName});await center.getByText('请切换创作者账号',{exact:true}).waitFor();
   assert.equal(await center.evaluate(()=>state.me.user.role),'operator');
   await centerLogin(a);await centerReady(a);await appReady(a);
  });
  await step('中心旧epoch网络拒绝不能覆盖B已加载工作台',async()=>{
   await appSetActor(a);
   const old=await delayed(center,'**/api/creator/me',{reject:true});
   await center.evaluate(()=>{void load().catch(creatorLoadError)});await old.arrived;
   await appSetActor(b);await old.finish();
   assert.equal(await center.evaluate(()=>state.me.user.id),b.id);
   assert.equal(await center.locator('.error-page').count(),0);
  });
  await step('作者资料迟成功/迟失败跨账号均不恢复A关注关系',async()=>{
   await appSetActor(a);
   await api(a.context.request,'creators/'+target.id+'/follow',{active:true});
   await api(b.context.request,'creators/'+target.id+'/follow',{active:false});
   for(const reject of [false,true]){
    await appSetActor(a);
    const old=await delayed(app,'**/api/creators/'+target.id,{reject});
    await app.goto(base+'/experience?creator='+target.id+'&lang=zh');await old.arrived;
    await appSetActor(b);
    await app.locator('[data-creator-follow="'+target.id+'"]').waitFor();
    assert.equal(await app.locator('[data-creator-follow="'+target.id+'"]').getAttribute('aria-pressed'),'false');
    await old.finish();
    assert.equal(await app.locator('[data-creator-follow="'+target.id+'"]').getAttribute('aria-pressed'),'false');
    assert.equal(await app.locator('.creator-profile-error').count(),0);
   }
  });
  await step('迟关注响应不触发新账号操作或覆盖B公开关系',async()=>{
   await appSetActor(a);await app.goto(base+'/experience?creator='+target.id+'&lang=zh');await app.locator('[data-creator-follow="'+target.id+'"]').waitFor();
   const old=await delayed(app,'**/api/creators/'+target.id+'/follow',{method:'POST'});
   await app.locator('[data-creator-follow="'+target.id+'"]').click();await old.arrived;
   await appSetActor(b);await app.locator('[data-creator-follow="'+target.id+'"]').waitFor();
   await old.finish();
   assert.equal((await api(shared.request,'creators/'+target.id)).following,false);
   assert.equal(await app.locator('[data-creator-follow="'+target.id+'"]').getAttribute('aria-pressed'),'false');
  });
  await step('迟互动数据不覆盖B作品收藏状态',async()=>{
   await appSetActor(a);
   await api(a.context.request,'creator-actions',{workId:published.id,action:'favorite',active:true});
   await api(b.context.request,'creator-actions',{workId:published.id,action:'favorite',active:false});
   await appSetActor(a);
   const old=await delayed(app,'**/api/creator-actions?workId='+published.id);
   await app.goto(base+'/experience?creator='+target.id+'&work='+published.id+'&lang=zh');await old.arrived;
   await appSetActor(b);await app.locator('[data-creator-action=favorite]').waitFor();await old.finish();
   await app.waitForFunction(()=>[...document.querySelectorAll('[data-creator-action=favorite]')].every(el=>el.getAttribute('aria-pressed')==='false'));
   assert.equal((await api(shared.request,'creator-actions?workId='+published.id)).favorited,false);
  });
  const companyContext=await browserContext({storageState:await admin.storageState()});company=await companyContext.newPage();await company.goto(base+'/admin');
  await company.locator('[data-nav=creatorReviews]:visible').first().click();await company.locator('[data-ca-review="'+reviewB.id+'"]').waitFor();
  await step('同页连续审阅A/B的迟成功和迟失败均不覆盖B审核表单',async()=>{
   for(const reject of [false,true]){
    const old=await delayed(company,'**/api/admin/creator-reviews/'+reviewA.id,{reject});
    await company.locator('[data-ca-review="'+reviewA.id+'"]').click();await old.arrived;
    await company.locator('[data-ca-review="'+reviewB.id+'"]').click();
    await company.locator('#ca-review-form[data-work-id="'+reviewB.id+'"]').waitFor();
    await old.finish();
    assert.equal(await company.locator('#ca-review-form').getAttribute('data-work-id'),reviewB.id);
    assert.equal(Number(await company.locator('#ca-review-form').getAttribute('data-version')),reviewB.version);
   }
   assert((await company.locator('body').innerText()).includes('平台人工复核'));
  });
 }finally{for(const context of owned.reverse())await (typeof context.close==='function'?context.close():context.dispose()).catch(()=>{})}
}

(async()=>{
 let browser;const results=[],errors=[];const started=identities();let identity=started;
 try{
  assert(sourceProbe||/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base),'Only disposable loopback service allowed');
  const source=fs.readFileSync(path.join(r4,'creator-center.html'),'utf8');
  let html=source;
  if(!sourceProbe){const response=await fetch(base+'/creator');assert.equal(response.status,200);html=await response.text();assert.equal(Buffer.from(html).toString('hex'),fs.readFileSync(path.join(web,'创作者中心.html')).toString('hex'),'Served creator page must be exact tested built bytes');assert.equal(html,source,'Creator source must match built page');const app=await(await fetch(base+'/experience')).text();assert(app.includes(fs.readFileSync(path.join(r4,'creator-app.js'),'utf8')),'Served APP must embed current creator-app source')}
  browser=await chromium.launch({headless:true});
  const labels=await creatorWriteFailureSuite({browser,html,poster:fs.readFileSync(path.join(r4,'images/community-preview-poster.jpg'))});
  for(const name of labels)results.push({name,pass:true});
  if(!sourceProbe&&!probe){await actualF03Suite({browser,base,results,errors})}
 }catch(error){errors.push(error.stack||String(error));if(!results.some(row=>!row.pass))results.push({name:'F03专项执行',pass:false,error:error.message})}
 finally{await browser?.close()}
 const ended=identities();if(JSON.stringify(started)!==JSON.stringify(ended)){errors.push('Source/build changed during acceptance');results.push({name:'执行期间源码与构建保持一致',pass:false})}
 const run={at:new Date().toISOString(),module:'基础框架F03',pass:errors.length===0&&results.every(r=>r.pass),passed:results.filter(r=>r.pass).length,failed:results.filter(r=>!r.pass).length,results,errors,...identity,productionWrites:false,partial:sourceProbe||probe,sourceProbe,syntheticClientOnly:sourceProbe||probe,scope:sourceProbe?'isolated source browser fault injection; not built or real API acceptance':probe?'isolated served-built browser fault injection; partial probe only':'isolated served-built browser and real HTTP API acceptance',testHashes:{['06_验证与后续工作/'+path.basename(__filename)]:digest(__filename)}};
 appendReport(run);console.log(JSON.stringify({report:reportName,pass:run.pass,passed:run.passed,failed:run.failed,partial:run.partial,errors}));if(!run.pass)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1});

