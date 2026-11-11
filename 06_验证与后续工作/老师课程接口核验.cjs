
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{spawn}=require('child_process');
const {chromium,request}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r=path.join(root,'04_研发源码/app/r4'),db=path.join(__dirname,'老师分类专项.sqlite3');
(async()=>{let server,browser,api;try{
for(const suffix of['','-wal','-shm']){const f=db+suffix;if(fs.existsSync(f))fs.unlinkSync(f);}
server=spawn(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'),['-B',path.join(r,'backend/server.py'),'--port','0','--db',db,'--web-root',path.join(root,'03_当前APP')],{windowsHide:true,stdio:['ignore','pipe','pipe']});
const base=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Startup timeout')),15000);server.stdout.on('data',d=>{const m=d.toString().match(/APP: (http:\/\/127.0.0.1:\d+)/);if(m){clearTimeout(timer);resolve(m[1]);}});});
api=await request.newContext({baseURL:base});assert.equal((await api.post('/api/auth/setup',{data:{username:'teacher_check_admin',password:'Isolated_Check_2026',name:'专项测试'}})).status(),200);
browser=await chromium.launch({headless:true});const context=await browser.newContext({storageState:await api.storageState(),viewport:{width:390,height:844},reducedMotion:'reduce'}),p=await context.newPage(),errors=[];
p.on('pageerror',e=>errors.push(e.message));await p.goto(base+'/experience');await p.waitForFunction(()=>px.loaded);
await p.evaluate(()=>navigate('academy'));assert.equal(await p.locator('.at-teacher-card').count(),3);
const course=(await(await api.get('/api/admin/content/courses')).json()).items.find(x=>x.id==='academy-ziwei-video');
const ac=await browser.newContext({storageState:await api.storageState(),viewport:{width:1280,height:900}}),ap=await ac.newPage();await ap.goto(base+'/admin');await ap.locator('.sidebar [data-nav=courses]').click();await ap.locator('[data-edit="'+course.id+'"]').click();
assert.equal(await ap.locator('[name=teacherId]').inputValue(),'demo-qinghe');await ap.locator('[name=teacherId]').selectOption('demo-anran');await ap.locator('#content-form button[value=published]').click();await ap.waitForFunction(()=>!state.editing);
await p.evaluate(()=>pxBootstrap());await p.evaluate(()=>{state.academyTeacherId='demo-anran';navigate('academyTeacher')});assert.equal(await p.locator('.academy-course').count(),4);
await p.evaluate(()=>{state.academyTeacherId='demo-qinghe';navigate('academyTeacher')});assert.equal(await p.locator('.academy-course').count(),2);
const item=(await(await api.get('/api/admin/content/courses')).json()).items.find(x=>x.id===course.id);const archived=await api.post('/api/admin/content/courses',{data:{item,status:'archived'}});assert.equal(archived.status(),200,await archived.text());
await p.evaluate(()=>pxBootstrap());await p.evaluate(()=>{state.academyTeacherId='demo-anran';navigate('academyTeacher')});assert.equal(await p.locator('.academy-course').count(),3);
const teacher=(await(await api.get('/api/admin/content/teachers')).json()).items.find(x=>x.id==='demo-anran');assert.equal((await api.post('/api/admin/content/teachers',{data:{item:teacher,status:'archived'}})).status(),200);
await p.evaluate(()=>pxBootstrap());await p.evaluate(()=>{state.academyFilters={theme:'all',access:'all',format:'all',query:''};navigate('academy')});assert.equal(await p.locator('[data-action=at-open][data-id=demo-anran]').count(),0);await p.locator('[data-action=at-open][data-id=unassigned]').click();assert.equal(await p.locator('.academy-course').count(),3);
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(__dirname,'老师课程接口核验.json'),JSON.stringify({at:new Date().toISOString(),pass:true,scope:'Isolated local database and actual admin UI',checks:['后台选择课程所属老师','发布后的课程归属更新','原老师课程同步移除','归档课程不再出现在老师页','老师归档后平台课程仍可访问'],errors},null,2));console.log('PASS teacher/course admin binding, publication, reassignment and archive lifecycle');
}finally{await browser?.close();await api?.dispose();server?.kill();}})().catch(e=>{console.error(e.stack);process.exitCode=1});

