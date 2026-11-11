// Focused HTTP validation against an isolated local service; never production.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{spawn}=require('child_process');
const {request}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4'),python=path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
const db=path.join(__dirname,'分类认证接口专项.sqlite3'),cloud=process.argv[2];let base=cloud,server;const contexts=[],checks=[];
async function start(){server=spawn(python,['-B',path.join(r4,'backend/server.py'),'--port','0','--db',db,'--web-root',path.join(root,'03_当前APP')],{windowsHide:true,stdio:['ignore','pipe','pipe']});return new Promise((resolve,reject)=>{let out='';const t=setTimeout(()=>reject(Error('No isolated service')),15000);server.stdout.on('data',b=>{out+=b;const m=out.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/);if(m){clearTimeout(t);resolve(m[1]);}});server.on('error',reject);});}
async function stop(){if(server){const end=new Promise(r=>server.once('exit',r));server.kill();await end;server=null;}}
(async()=>{try{
 if(cloud)assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(cloud),'Only isolated local API allowed');else{assert(!fs.existsSync(db),'Do not overwrite an existing database');base=await start();}
 async function context(){const c=await request.newContext({baseURL:base});contexts.push(c);return c;}
 const admin=await context(),user=await context(),operator=await context(),anon=await context();
 const credentials=cloud?JSON.parse(fs.readFileSync(path.join(root,'04_研发源码/app/cloud/.env.local-test'),'utf8')):{username:'schema_admin',password:'SchemaTestOnly_2026'};
 assert.equal((await admin.post('/api/auth/'+(cloud?'login':'setup'),{data:credentials})).status(),200);
 const memberResponse=await user.post('/api/auth/register',{data:{username:'schema_user',password:'SchemaTestOnly_2026'}});assert.equal(memberResponse.status(),200);
 const operatorResponse=await operator.post('/api/auth/register',{data:{username:'schema_operator',password:'SchemaTestOnly_2026'}});assert.equal(operatorResponse.status(),200);
 const operatorId=(await operatorResponse.json()).user.id;assert.equal((await admin.patch('/api/admin/users/'+operatorId,{data:{role:'operator'}})).status(),200);
 async function expect(ctx,url,body,status,label,method='POST'){const res=await ctx.fetch('/api/'+url,{method,data:body});assert.equal(res.status(),status,label+' '+await res.text());checks.push(label);return res;}
 let content=(await (await anon.get('/api/public')).json()).content;
 assert(content.courseCategories.some(c=>c.id==='cat-audiobook'&&c.enabled===true)&&content.courseCategories.some(c=>c.id==='cat-video'));assert(content.courses.filter(c=>c.format==='audio').every(c=>c.categoryIds.includes('cat-audiobook')));checks.push('默认分类及既有课程迁移');
 await expect(anon,'admin/content/courseCategories',{item:{id:'deny',name:'拒绝'},status:'published'},401,'匿名分类写入拒绝');
 await expect(user,'admin/content/courseCategories',{item:{id:'deny',name:'拒绝'},status:'published'},403,'学员分类写入拒绝');
 await expect(admin,'admin/content/courseCategories',{item:{id:'all',name:'全部'},status:'published'},400,'全部保留编号校验');
 await expect(admin,'admin/content/courseCategories',{item:{id:'bad-enabled',name:'错误',enabled:'yes'},status:'published'},400,'分类布尔状态校验');
 const category={id:'schema-tea',name:'茶道',nameEn:'Tea practice',nameHant:'茶道',nameBo:'ཇ།',enabled:true};
 await expect(operator,'admin/content/courseCategories',{item:category,status:'published',position:-99},200,'运营新增自定义分类');
 content=(await (await anon.get('/api/public')).json()).content;assert.equal(content.courseCategories[0].id,category.id);checks.push('分类发布顺序同步公开接口');
 const course=content.courses[0],originalCourse={...course};
 await expect(admin,'admin/content/courses',{item:{...course,categoryIds:['missing-category']},status:'published'},400,'不存在课程分类校验');
 await expect(admin,'admin/content/courses',{item:{...course,categoryIds:[category.id,category.id]},status:'published'},400,'重复课程分类校验');
 await expect(admin,'admin/content/courses',{item:{...course,categoryIds:[...new Set([...(course.categoryIds||[]),category.id])]},status:'published'},200,'课程关联多分类');
 await expect(operator,'admin/content/courseCategories',{item:{...category,name:'茶道入门',enabled:false},status:'published'},200,'分类名称及启停编辑');
 const saved=(await (await admin.get('/api/admin/content/courseCategories')).json()).items.find(x=>x.id===category.id);assert.equal(saved.name,'茶道入门');assert.equal(saved.enabled,false);checks.push('后台分类查询');
 await expect(operator,'admin/content/courseCategories/'+category.id,undefined,200,'删除分类','DELETE');
 content=(await (await anon.get('/api/public')).json()).content;assert(!content.courseCategories.some(c=>c.id===category.id));const afterDelete=content.courses.find(c=>c.id===course.id);assert(afterDelete&&!afterDelete.categoryIds.includes(category.id));checks.push('删除分类仅解绑，课程保留');
 const demo=content.teachers.find(t=>t.profileType==='demo');assert(demo&&demo.verified===false&&demo.recommended===false);const day=new Date().toISOString().slice(0,10);
 await expect(user,'service-requests',{teacherId:demo.id,date:day,body:'仅测试'},403,'示例老师咨询拒绝');
 const real={id:'schema-certified',name:'接口测试老师',profileType:'real',specialty:'测试',verified:false,recommended:false};
 await expect(operator,'admin/content/teachers',{item:{...real,verified:true},status:'published'},403,'运营不可授予认证');
 await expect(admin,'admin/content/teachers',{item:{...real,profileType:'demo',verified:true},status:'published'},400,'示例不可认证');
 await expect(admin,'admin/content/teachers',{item:{...real,recommended:true},status:'published'},400,'未认证不可推荐');
 await expect(admin,'admin/content/teachers',{item:real,status:'published'},200,'真实资料待认证状态');
 await expect(user,'service-requests',{teacherId:real.id,date:day,body:'仅测试'},403,'未认证老师咨询拒绝');
 await expect(admin,'admin/content/teachers',{item:{...real,verified:true,recommended:true},status:'published'},200,'管理员认证及推荐');
 await expect(operator,'admin/content/teachers',{item:{...real,verified:true,recommended:false},status:'published'},403,'运营不可取消推荐');
 await expect(operator,'admin/content/teachers',{item:{id:real.id,name:'运营仅编辑介绍',profileType:'real'},status:'published'},200,'运营无认证字段编辑时保留认证');
 let teacher=(await (await admin.get('/api/admin/content/teachers')).json()).items.find(t=>t.id===real.id);assert(teacher.verified===true&&teacher.recommended===true);checks.push('省略认证字段不会降级老师');
 await expect(user,'service-requests',{teacherId:real.id,date:day,body:'接口认证咨询回归'},200,'认证老师咨询请求');
 const revisions=(await (await admin.get('/api/admin/revisions')).json()).items.filter(r=>r.kind==='teachers'&&r.item_id===real.id);
 let rejectedRollback=false;
 for(const revision of revisions){const res=await operator.post('/api/admin/revisions/'+revision.id,{data:{}});if(res.status()===403){rejectedRollback=true;break;}}
 assert(rejectedRollback);checks.push('运营不可通过版本回滚修改认证');
 await expect(admin,'admin/content/courseCategories/cat-video',undefined,200,'删除默认分类','DELETE');
 if(!cloud){await stop();base=await start();const fresh=await request.newContext({baseURL:base});contexts.push(fresh);content=(await (await fresh.get('/api/public')).json()).content;}
 else content=(await (await anon.get('/api/public')).json()).content;
 assert(!content.courseCategories.some(c=>c.id==='cat-video'));checks.push('默认分类删除后启动或重复初始化不复活');
 if(cloud){const initial=JSON.parse(fs.readFileSync(path.join(r4,'backend/initial-content.json'),'utf8')).courseCategories.find(c=>c.id==='cat-video');await expect(admin,'admin/content/courseCategories',{item:initial,status:'published',position:1},200,'恢复隔离云端测试默认分类');}
 const report={at:new Date().toISOString(),pass:true,backend:cloud?'local Worker':'Python',checks};fs.writeFileSync(path.join(__dirname,'动态分类与老师认证-'+(cloud?'云端适配':'本机')+'核验.json'),JSON.stringify(report,null,2),'utf8');console.log('PASS category and teacher certification: '+checks.length+' checks ('+report.backend+')');
}finally{for(const c of contexts)await c.dispose();await stop();if(!cloud)for(const suffix of ['','-wal','-shm']){const file=db+suffix;if(path.dirname(file)===__dirname&&fs.existsSync(file))fs.unlinkSync(file);}}})().catch(e=>{console.error(e.stack);process.exitCode=1});

