const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto'),{spawn}=require('child_process');
const {chromium,request}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4'),python=path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
const db=path.join(__dirname,'登录信息专项.sqlite3');let server,browser;const contexts=[],cloud=process.argv[2];let base=cloud;
(async()=>{const results=[];try{
 if(cloud)assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(cloud),'Only isolated local test service allowed');
 else{
  assert(!fs.existsSync(db),'Existing test database must not be overwritten');
  server=spawn(python,['-B',path.join(r4,'backend/server.py'),'--port','0','--db',db,'--web-root',path.join(root,'03_当前APP')],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  base=await new Promise((resolve,reject)=>{let out='';const t=setTimeout(()=>reject(Error('No test server')),15000);server.stdout.on('data',b=>{out+=b;const m=out.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/);if(m){clearTimeout(t);resolve(m[1]);}});server.on('error',reject);});
 }
 async function context(){const c=await request.newContext({baseURL:base});contexts.push(c);return c;}
 const admin=await context(),anon=await context(),member=await context(),otherSession=await context();
 const old={username:'credentials_owner',password:'OnlyForRegression_2026'};
 if(cloud){
  const boot=await context(),creds=JSON.parse(fs.readFileSync(path.join(root,'04_研发源码/app/cloud/',fs.existsSync(path.join(root,'04_研发源码/app/cloud/.env.local-test'))?'.env.local-test':'.env.test'),'utf8'));
  assert.equal((await boot.post('/api/auth/login',{data:creds})).status(),200);
  const reg=await admin.post('/api/auth/register',{data:old});assert.equal(reg.status(),200);const uid=(await reg.json()).user.id;
  assert.equal((await boot.patch('/api/admin/users/'+uid,{data:{role:'admin'}})).status(),200);
 }else assert.equal((await admin.post('/api/auth/setup',{data:old})).status(),200);
 assert.equal((await member.post('/api/auth/register',{data:{username:'credentials_taken',password:'OnlyForRegression_2026'}})).status(),200);
 assert.equal((await otherSession.post('/api/auth/login',{data:old})).status(),200);
 const before=(await (await admin.get('/api/auth/status')).json()).user;
 const body={currentPassword:old.password,username:'credentials_new',password:String(crypto.randomInt(100000,1000000))};
 async function expect(c,data,status,name){const r=await c.post('/api/auth/credentials',{data});assert.equal(r.status(),status,name);results.push(name);}
 await expect(anon,body,401,'匿名拒绝');
 await expect(member,body,403,'非管理员拒绝');
 await expect(admin,{...body,currentPassword:'WrongPassword'},401,'原密码校验');
 await expect(admin,{...body,password:body.password.slice(0,5)},400,'修改密码拒绝5位，至少6位');
 await expect(admin,{...body,username:'invalid name'},400,'用户名格式校验');
 await expect(admin,{...body,username:'credentials_taken'},409,'重复用户名回滚且会话保留');
 assert.equal((await admin.get('/api/admin/dashboard')).status(),200);
 await expect(admin,{...body,role:'user',userId:'someone-else'},200,'只修改本人，忽略额外目标和角色');
 assert.equal((await otherSession.get('/api/admin/dashboard')).status(),401);
 assert.equal((await admin.get('/api/admin/dashboard')).status(),401);results.push('全部旧会话注销');
 const fresh=await context();
 assert.equal((await fresh.post('/api/auth/login',{data:old})).status(),401);
 assert.equal((await fresh.post('/api/auth/login',{data:{username:body.username,password:old.password}})).status(),401);
 const login=await fresh.post('/api/auth/login',{data:{username:body.username,password:body.password}});assert.equal(login.status(),200);
 const after=(await login.json()).user;assert.equal(after.id,before.id);assert.equal(after.role,'admin');assert.equal(after.name,before.name);results.push('新6位密码有效、旧凭据失效、原ID权限昵称保留');
 assert.equal((await fresh.get('/api/admin/dashboard')).status(),200);
 browser=await chromium.launch({headless:true});const p=await browser.newPage();await p.goto(base+'/admin');await p.locator('[name=username]').fill(body.username);await p.locator('[name=password]').fill(body.password);await p.locator('#auth-form button').click();await p.locator('.sidebar').waitFor();results.push('真实后台登录表单接受6位密码');
 const creatorPage=await browser.newPage();await creatorPage.goto(base+'/creator');await creatorPage.locator('#login-form').waitFor();assert(Number(await creatorPage.locator('[name=password]').getAttribute('minlength'))<=6);await creatorPage.locator('[name=username]').fill(body.username);await creatorPage.locator('[name=password]').fill(body.password);await creatorPage.locator('#login-form button[type=submit]').click();await creatorPage.locator('.global-header').waitFor();await creatorPage.locator('.account-info').waitFor();results.push('真实创作者中心登录表单接受6位密码并进入本人工作台');
 const audit=await (await fresh.get('/api/admin/audits')).json();const serialized=JSON.stringify(audit);assert(!serialized.includes(body.password)&&!serialized.includes(old.password));results.push('审计不包含密码');
 fs.writeFileSync(path.join(__dirname,'登录信息修改-'+(cloud?'云端适配':'本机')+'核验.json'),JSON.stringify({at:new Date().toISOString(),pass:true,checks:results},null,2));
 console.log('PASS credentials: '+results.length+' checks ('+(cloud?'local Worker':'Python')+')');
}finally{for(const c of contexts)await c.dispose();await browser?.close();if(server){const stopped=new Promise(r=>server.once('exit',r));server.kill();await stopped;for(const suffix of ['','-wal','-shm']){const file=db+suffix;if(path.dirname(file)===__dirname&&fs.existsSync(file))fs.unlinkSync(file);}}}})().catch(e=>{console.error(e.stack);process.exitCode=1});

