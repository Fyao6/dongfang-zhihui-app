const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{spawn}=require('child_process');
const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4'),web=path.join(root,'03_当前APP'),python=path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
const db=path.join(__dirname,'课程分类浏览器.sqlite3'),id='browser-tea-category';let server,browser;
const checks=[],layouts=[],errors=[];
(async()=>{try{
 assert(!fs.existsSync(db),'Existing browser-test database must not be overwritten.');
 server=spawn(python,['-B',path.join(r4,'backend/server.py'),'--port','0','--db',db,'--web-root',web],{windowsHide:true,stdio:['ignore','pipe','pipe']});
 const base=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Isolated server did not start')),15000);server.stdout.on('data',chunk=>{out+=chunk;const match=out.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/);if(match){clearTimeout(timer);resolve(match[1]);}});server.once('error',reject);server.stderr.on('data',chunk=>{out+=chunk});});
 browser=await chromium.launch({headless:true});const adminContext=await browser.newContext({viewport:{width:1440,height:1000}}),admin=await adminContext.newPage();admin.on('pageerror',e=>errors.push('admin: '+e.message));
 await admin.goto(base+'/admin');await admin.locator('#auth-form [name=username]').fill('category_browser_admin');await admin.locator('#auth-form [name=password]').fill('CategoryBrowser_2026');await admin.locator('#auth-form [name=name]').fill('分类浏览器验收');await admin.locator('#auth-form button').click();await admin.locator('.sidebar').waitFor();
 const originals=(await (await admin.request.get(base+'/api/admin/content/courses')).json()).items,originalIds=originals.map(x=>x.id).sort();
 assert.equal(originalIds.length,9);checks.push('真实后台页面创建隔离管理员');
 async function nav(kind){await admin.locator('.sidebar [data-nav='+kind+']').click();await admin.waitForFunction(kind=>state.nav===kind&&!document.querySelector('#main>.loading'),kind);await admin.locator('#main .editor-layout').waitFor();}
 async function publish(kind){const response=admin.waitForResponse(r=>r.url()===base+'/api/admin/content/'+kind&&r.request().method()==='POST');await admin.locator('#content-form button[value=published]').click();const r=await response;assert.equal(r.status(),200,await r.text());await admin.waitForFunction(()=>state.editing===null&&!!document.querySelector('.editor-layout'));await admin.waitForTimeout(80);}
 await nav('courseCategories');assert.equal(await admin.locator('tbody tr').count(),2);await admin.locator('[data-action=new-content]').click();await admin.locator('#content-form [name=id]').fill(id);
 const names={name:'茶道',nameEn:'Tea practice',nameHant:'茶道',nameBo:'ཇ་ཡི་ལམ།'};
 for(const [key,value] of Object.entries(names))await admin.locator('#content-form [name='+key+']').fill(value);
 await admin.locator('#content-form [name=enabled]').check();await admin.locator('#content-form [name=position]').fill('100');await publish('courseCategories');
 await admin.locator('[data-edit='+id+']').waitFor();await admin.locator('[data-list-search]').fill('茶道');assert.equal(await admin.locator('tbody tr:visible').count(),1);await admin.locator('[data-list-search]').fill('');checks.push('后台界面新增发布四语分类并查找');
 const firstAudio=originals.find(x=>x.format==='audio'),selectedCourses=[firstAudio,originals.find(x=>x.format==='video'&&x.theme!==firstAudio.theme)];assert(selectedCourses.every(Boolean));
 for(const course of selectedCourses){await nav('courses');await admin.locator('[data-edit='+course.id+']').click();const selected=[...new Set([...(course.categoryIds||[]),id])];await admin.locator('select[name=categoryIds]').selectOption(selected);await publish('courses');}
 checks.push('后台课程编辑器多选分类并发布两门课程');
 const user=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'}),p=await user.newPage();p.on('pageerror',e=>errors.push('app: '+e.message));await p.goto(base+'/experience?lang=zh-Hans&page=academy');await p.waitForFunction(()=>px.loaded);await p.locator('.academy-category-strip').waitFor();
 assert.equal(await p.locator('.at-browse-tabs,[data-action=at-view],.at-teacher-card').count(),0);assert.equal(await p.locator('.academy-course').count(),9);assert.deepEqual(await p.locator('.academy-category-options button').allTextContents(),['全部课程','有声书','视频教程','茶道']);
 await p.locator('[data-action=academy-category][data-id='+id+']').click();assert.equal(await p.locator('.academy-course').count(),2);
 const themes=[...new Set(selectedCourses.map(x=>x.theme))];assert(themes.length>1);
 await p.locator('[data-action=academy-filter][data-key=theme][data-value='+themes[0]+']').first().click();assert.equal(await p.locator('.academy-course').count(),1);
 await p.locator('#academy-search').fill('不会匹配任何课程');assert.equal(await p.locator('.academy-course').count(),0);await p.locator('[data-action=academy-reset]').click();assert.equal(await p.locator('.academy-course').count(),9);assert.equal(await p.evaluate(()=>state.academyCategoryId),'all');checks.push('直接打开page=academy无初始化错误，图文列表、动态分类、组合筛选、计数与空结果重置');
 for(const viewport of [{width:360,height:740},{width:390,height:844},{width:550,height:850}]){
  await p.setViewportSize(viewport);
  for(const lang of ['zh','zh-Hant','en','bo']){
   await p.evaluate(lang=>{state.lang=lang;navigate('academy')},lang);await p.evaluate(()=>document.fonts.ready);assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await p.locator('[data-action=academy-category][data-id='+id+']').click();assert.equal(await p.locator('.academy-course').count(),2);
   const label=await p.locator('[data-action=academy-category][data-id='+id+']').innerText();assert.equal(label,lang==='en'?names.nameEn:lang==='bo'?names.nameBo:names.name);
   layouts.push({lang,...viewport,pass:true});if(viewport.width===390)await p.screenshot({path:path.join(__dirname,'课程动态分类-'+lang+'.png')});
  }
 }
 checks.push('四语言与三种手机尺寸的分类名称、筛选和页面宽度');
 await nav('courseCategories');await admin.locator('[data-edit='+id+']').click();await admin.locator('[name=enabled]').uncheck();await publish('courseCategories');
 await p.evaluate(()=>pxBootstrap());await p.waitForFunction(()=>state.academyCategoryId==='all');assert.equal(await p.locator('[data-action=academy-category][data-id='+id+']').count(),0);assert.equal(await p.locator('.academy-course').count(),9);checks.push('停用当前选中分类后前台自动回到全部，课程保留');
 await admin.locator('[data-edit='+id+']').click();await admin.locator('[name=enabled]').check();await admin.locator('[name=name]').fill('茶道入门');await admin.locator('[name=nameEn]').fill('Tea foundations');await admin.locator('[name=position]').fill('-100');await publish('courseCategories');
 await p.evaluate(()=>{state.lang='zh';return pxBootstrap()});await p.waitForFunction(()=>document.querySelectorAll('.academy-category-options button')[1]?.textContent==='茶道入门');await p.reload();await p.waitForFunction(()=>px.loaded);assert.equal(await p.locator('.academy-category-options button').nth(1).innerText(),'茶道入门');checks.push('后台修改名称与排序后刷新仍生效');
 await p.locator('[data-action=academy-category][data-id='+id+']').click();assert.equal(await p.locator('.academy-course').count(),2);
 admin.once('dialog',d=>d.accept());const deleted=admin.waitForResponse(r=>r.url()===base+'/api/admin/content/courseCategories/'+id&&r.request().method()==='DELETE');await admin.locator('[data-action=delete-category][data-id='+id+']').click();assert.equal((await deleted).status(),200);
 await p.evaluate(()=>pxBootstrap());await p.waitForFunction(()=>state.academyCategoryId==='all');assert.equal(await p.locator('[data-action=academy-category][data-id='+id+']').count(),0);assert.equal(await p.locator('.academy-course').count(),9);
 const after=(await (await admin.request.get(base+'/api/admin/content/courses')).json()).items;assert.deepEqual(after.map(x=>x.id).sort(),originalIds);assert(after.every(x=>!(x.categoryIds||[]).includes(id)));for(const original of selectedCourses){const found=after.find(x=>x.id===original.id);assert.deepEqual(found.categoryIds,original.categoryIds);}checks.push('后台删除分类清理引用且全部课程与原分类关联保留');
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(__dirname,'课程动态分类浏览器核验.json'),JSON.stringify({at:new Date().toISOString(),pass:true,scope:'Isolated Python database, actual admin and APP browser pages, no production requests',checks,layouts,errors},null,2),'utf8');console.log('PASS dynamic category admin/UI integration: '+checks.length+' checks, '+layouts.length+' locale/viewport layouts.');
}finally{
 await browser?.close();if(server){const stopped=new Promise(resolve=>server.once('exit',resolve));server.kill();await stopped;for(const suffix of ['','-wal','-shm']){const file=db+suffix;assert.equal(path.dirname(file),__dirname);if(fs.existsSync(file))fs.unlinkSync(file);}}
}})().catch(e=>{console.error(JSON.stringify({error:e.stack,pageErrors:errors},null,2));process.exitCode=1});

