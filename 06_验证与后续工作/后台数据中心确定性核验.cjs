// Actual Python HTTP and Cloud API handlers, isolated databases and a fixed Beijing clock.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process');
const {DatabaseSync}=require('node:sqlite');
const root=path.resolve(__dirname,'..'),cloud=path.join(root,'04_研发源码/app/cloud'),esbuild=require(path.join(cloud,'node_modules/esbuild'));
const at=s=>Date.parse(s),started=at('2026-10-20T12:00:00+08:00'),stamp=at('2026-11-05T12:00:00+08:00');
const people=[['admin','admin','2026-10-01'],['operator','operator','2026-10-01'],['reviewer','reviewer','2026-10-01'],['alice','user','2026-10-25'],['bob','teacher','2026-11-02'],['old','user','2026-10-01'],['today','user','2026-11-05'],['yearonly','user','2026-10-21']].map(([id,role,date])=>({id,role,created:at(date+'T01:00:00+08:00')}));
const activity=[
 ['yearonly','home','visit','2026-10-21T12:00:00+08:00'],
 ['alice','home','visit','2026-10-25T12:00:00+08:00'],
 ['alice','home','visit','2026-10-25T12:00:05+08:00'],
 ['alice','home','heartbeat','2026-10-25T12:00:10+08:00'],
 ['alice','practice','visit','2026-10-26T12:00:00+08:00'],
 ['alice','community','visit','2026-11-01T12:00:00+08:00'],
 ['bob','academy','visit','2026-11-02T12:00:00+08:00'],
 ['bob','community','visit','2026-11-03T12:00:00+08:00'],
 ['old','home','visit','2026-11-04T23:59:59+08:00'],
 ['old','home','heartbeat','2026-11-05T00:00:00+08:00'],
 ['alice','life','visit','2026-11-05T11:00:00+08:00'],
 ['bob','community','visit','2026-11-05T11:00:00+08:00']
].map(([who,feature,kind,date])=>({who,data:{feature,kind},stamp:at(date)}));
const queries={day:'start=2026-11-01&end=2026-11-05&grain=day',week:'start=2026-10-20&end=2026-11-05&grain=week',month:'start=2026-10-20&end=2026-11-05&grain=month',year:'start=2026-10-20&end=2026-11-05&grain=year',uncollected:'start=2026-10-19&end=2026-10-19&grain=day',mixed:'start=2026-10-19&end=2026-10-21&grain=day',retention:'start=2026-10-20&end=2026-11-05&grain=day',october:'start=2026-10-25&end=2026-10-25&grain=day'};
const boundaryActivity=[{who:'alice',data:{feature:'home',kind:'visit'},stamp:at('2026-12-31T23:59:59+08:00')},{who:'bob',data:{feature:'home',kind:'visit'},stamp:at('2027-01-01T00:00:00+08:00')}],boundaryStamp=at('2027-01-01T12:00:00+08:00');
const invalid=[
 ['','GET','/api/admin/analytics',null,401],['alice','GET','/api/admin/analytics',null,403],['reviewer','GET','/api/admin/analytics',null,403],
 ['','POST','/api/analytics/activity',{feature:'home'},401],
 ['alice','POST','/api/analytics/activity',{feature:'invented'},400],['alice','POST','/api/analytics/activity',{feature:'home',kind:'invented'},400],
 ['alice','POST','/api/analytics/activity',{feature:'home',owner:'admin'},400],['alice','POST','/api/analytics/activity',{feature:'home',time:0},400],
 ['admin','GET','/api/admin/analytics?start=2026-02-30&end=2026-11-05',null,400],['admin','GET','/api/admin/analytics?start=2026-11-05&end=2026-11-04',null,400],
 ['admin','GET','/api/admin/analytics?start=2026-11-01&end=2026-11-06',null,400],['admin','GET','/api/admin/analytics?start=2000-01-01&end=2026-11-05',null,400],
 ['admin','GET','/api/admin/analytics?grain=hour',null,400],['admin','POST','/api/admin/analytics',{},405],['alice','GET','/api/analytics/activity',null,405]
];
const fixtures={started,stamp,people,activity,queries,invalid,boundaryActivity,boundaryStamp};
function verify(data,label){
 assert.equal(data.initial.summary.activeUsers,0);assert.equal(data.initial.summary.visits,0);assert(data.initial.features.every(x=>x.activeUsers===0&&x.visits===0));assert(data.initial.retention.every(x=>x.eligibleUsers===0&&x.rate===null));assert.equal(data.initial.trend.at(-1).coverage,'partial');assert.equal(data.initial.trend[0].activeUsers,null);
 const d=data.day;
 assert.equal(d.timezone,'Asia/Shanghai',label);assert.equal(Date.parse(d.collectedSince),started);assert.deepEqual(d.range,{start:'2026-11-01',end:'2026-11-05',grain:'day'});
 assert.equal(d.windows.day.start,'2026-11-05');assert.equal(d.windows.week.start,'2026-11-02');assert.equal(d.windows.month.start,'2026-11-01');assert.equal(d.windows.year.start,'2026-01-01');
 assert.deepEqual(Object.values(d.windows).map(x=>x.activeUsers),[3,3,3,4]);assert(Object.values(d.windows).every(x=>x.end==='2026-11-05'&&x.coverage==='partial'));
 assert.equal(d.summary.registeredUsers,5);assert.equal(d.summary.newUsers,2);assert.equal(d.summary.activeUsers,3);assert.equal(d.summary.visits,6);
 assert.deepEqual(d.trend.map(x=>x.activeUsers),[1,1,1,1,3]);assert.deepEqual(d.trend.map(x=>x.visits),[1,1,1,1,2]);assert.equal(d.trend.at(-1).coverage,'partial');
 const features=Object.fromEntries(d.features.map(x=>[x.id,x]));assert.equal(features.home.activeUsers,1);assert.equal(features.home.visits,1);assert.equal(features.community.activeUsers,2);assert.equal(features.community.visits,3);
 assert.equal(data.october.summary.visits,1,'30秒重复和心跳不应增加访问');assert.equal(data.october.summary.activeUsers,1);
 assert.equal(data.month.trend.length,2);assert.deepEqual(data.month.trend.map(x=>x.activeUsers),[2,3]);assert.equal(data.month.summary.activeUsers,4,'跨月用户需整体去重');
 assert.equal(data.year.trend.length,1);assert.equal(data.year.trend[0].activeUsers,4);assert.equal(data.year.trend[0].date,'2026-10-20');assert.equal(data.year.trend[0].end,'2026-11-05');
 assert.equal(data.week.trend[0].date,'2026-10-20');assert.equal(data.week.trend[0].end,'2026-10-25');assert.equal(data.week.trend.at(-1).date,'2026-11-02');
 const retention=Object.fromEntries(data.retention.retention.map(x=>[x.days,x]));assert.equal(retention[1].eligibleUsers,3);assert.equal(retention[1].returnedUsers,2);assert.equal(retention[1].rate,66.67);assert.equal(retention[7].eligibleUsers,2);assert.equal(retention[7].returnedUsers,1);assert.equal(retention[7].rate,50);
 assert.equal(data.uncollected.summary.activeUsers,null);assert.equal(data.uncollected.summary.visits,null);assert.equal(data.uncollected.trend[0].coverage,'uncollected');assert.equal(data.uncollected.trend[0].activeUsers,null);
 assert.equal(data.mixed.trend[0].activeUsers,null);assert.equal(data.mixed.trend[1].coverage,'partial');assert.equal(data.mixed.summary.activeUsers,1);
 assert.equal(data.day.retention.find(x=>x.days===7).rate,null,'未成熟留存样本应为空');
 assert.equal(data.operator.summary.activeUsers,3);assert.equal(data.default.range.end,'2026-11-05');
 assert.deepEqual(Object.values(data.newyear.windows).map(x=>x.activeUsers),[1,2,1,1]);assert.equal(data.newyear.windows.week.start,'2026-12-28');assert.equal(data.newyear.windows.year.start,'2027-01-01');assert.deepEqual(data.newyear.trend.map(x=>x.activeUsers),[1,1]);
 assert.equal(data.concurrent.features.find(x=>x.id==='music').visits,1,'并发默认visit只计一次');assert.equal(data.concurrent.summary.activeUsers,2);
 assert(data.ignored.every(x=>x.ok&&x.ignored),'公司管理操作应排除');
 const serialized=JSON.stringify(data);for(const key of ['password','username','userId','user_id','birth','message','session_token'])assert(!serialized.includes('"'+key+'"'),'不得返回个人明细 '+key);
}
const python=String.raw`
import sys,json,threading,hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
r=Path(sys.argv[1]);sys.path.insert(0,str(r/'04_研发源码/app/r4/backend'))
import server,analytics
f=json.load(sys.stdin);clock=[f['started']];analytics.now=lambda:clock[0]
dbpath=r/'06_验证与后续工作/后台数据中心专项隔离.sqlite3'
assert not dbpath.exists(),'上次专项数据库仍在，请先审查'
httpd=None
try:
 store=server.Store(dbpath)
 with store.connect() as db:
  for p in f['people']:
   db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)',(p['id'],p['id'],'unused',p['id'],p['role'],p['created']))
   db.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(('analytics-'+p['id']).encode()).hexdigest(),p['id'],4102444800000))
 httpd=ThreadingHTTPServer(('127.0.0.1',0),server.make_handler(store,r/'03_当前APP'));threading.Thread(target=httpd.serve_forever,daemon=True).start()
 base='http://127.0.0.1:'+str(httpd.server_port)
 def call(who,method,url,data=None,status=200):
  body=json.dumps(data).encode() if data is not None else None
  try:
   with urlopen(Request(base+url,data=body,method=method,headers={'Content-Type':'application/json','Cookie':'ew_session=analytics-'+who}),timeout=15) as response:code=response.status;result=json.load(response)
  except HTTPError as e:code=e.code;result=json.load(e)
  assert code==status,(url,code,status,result)
  return result
 initial=call('admin','GET','/api/admin/analytics')
 for activity in f['activity']:
  clock[0]=activity['stamp'];call(activity['who'],'POST','/api/analytics/activity',activity['data'])
 clock[0]=f['stamp'];result={'initial':initial,'ignored':[call(who,'POST','/api/analytics/activity',{'feature':'home'}) for who in ['admin','operator','reviewer']]}
 for args in f['invalid']:call(*args)
 for name,query in f['queries'].items():result[name]=call('admin','GET','/api/admin/analytics?'+query)
 result['operator']=call('operator','GET','/api/admin/analytics?'+f['queries']['day']);result['default']=call('admin','GET','/api/admin/analytics')
 for activity in f['boundaryActivity']:
  clock[0]=activity['stamp'];call(activity['who'],'POST','/api/analytics/activity',activity['data'])
 clock[0]=f['boundaryStamp'];result['newyear']=call('admin','GET','/api/admin/analytics?start=2026-12-31&end=2027-01-01&grain=day')
 with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda _:call('alice','POST','/api/analytics/activity',{'feature':'music'}),range(6)))
 result['concurrent']=call('admin','GET','/api/admin/analytics?start=2027-01-01&end=2027-01-01&grain=day')
 server.Store(dbpath)
 assert call('admin','GET','/api/admin/analytics')['collectedSince']==result['default']['collectedSince'],'重启不得重置采集起点'
 print(json.dumps(result,ensure_ascii=False))
finally:
 if httpd:httpd.shutdown();httpd.server_close()
 for suffix in ['','-wal','-shm']:
  p=Path(str(dbpath)+suffix)
  if p.exists():p.unlink()
`;
(async()=>{
 const compiled=await esbuild.build({entryPoints:[path.join(cloud,'lib/eastern-api.ts')],bundle:true,platform:'node',format:'esm',write:false});const {handleAPI}=await import('data:text/javascript;base64,'+Buffer.from(compiled.outputFiles[0].text).toString('base64'));
 const sqlite=new DatabaseSync(':memory:');sqlite.exec(fs.readFileSync(path.join(cloud,'drizzle/0000_lethal_lucky_pierre.sql'),'utf8'));
 const db={prepare(sql){let params=[];return{bind(...p){params=p;return this},async first(){return sqlite.prepare(sql).get(...params)||null},async all(){return{results:sqlite.prepare(sql).all(...params)}},async run(){return{meta:{changes:sqlite.prepare(sql).run(...params).changes}}}}},async batch(stmts){sqlite.exec('BEGIN');try{const result=[];for(const s of stmts)result.push(await s.run());sqlite.exec('COMMIT');return result}catch(e){sqlite.exec('ROLLBACK');throw e}}};
 for(const [k,v] of [['cloud_bootstrap_v1','true'],['course_categories_v1','true'],['ai','{}'],['theme','{}']])sqlite.prepare('INSERT INTO settings VALUES (?,?)').run(k,v);
 for(const p of people){sqlite.prepare('INSERT INTO users VALUES (?,?,?,?,?,?)').run(p.id,p.id,'unused',p.id,p.role,p.created);const hash=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode('analytics-'+p.id))).toString('hex');sqlite.prepare('INSERT INTO sessions VALUES (?,?,?)').run(hash,p.id,4102444800000);}
 let clock=started;const realNow=Date.now;Date.now=()=>clock;
 try{
  async function call(who,method,url,data=null,status=200){const response=await handleAPI(new Request('https://test.local'+url,{method,headers:{cookie:'ew_session=analytics-'+who,'Content-Type':'application/json'},...(data!==null?{body:JSON.stringify(data)}:{})}),{DB:db,BUCKET:{}});const result=await response.json();assert.equal(response.status,status,url+': '+JSON.stringify(result));return result;}
  await call('admin','GET','/api/auth/status');
  const initial=await call('admin','GET','/api/admin/analytics');
  for(const a of activity){clock=a.stamp;await call(a.who,'POST','/api/analytics/activity',a.data);}
  clock=stamp;const data={initial,ignored:[]};for(const who of ['admin','operator','reviewer'])data.ignored.push(await call(who,'POST','/api/analytics/activity',{feature:'home'}));
  for(const args of invalid)await call(...args);for(const [name,query] of Object.entries(queries))data[name]=await call('admin','GET','/api/admin/analytics?'+query);
  data.operator=await call('operator','GET','/api/admin/analytics?'+queries.day);data.default=await call('admin','GET','/api/admin/analytics');
  for(const a of boundaryActivity){clock=a.stamp;await call(a.who,'POST','/api/analytics/activity',a.data);}clock=boundaryStamp;data.newyear=await call('admin','GET','/api/admin/analytics?start=2026-12-31&end=2027-01-01&grain=day');
  await Promise.all(Array.from({length:6},()=>call('alice','POST','/api/analytics/activity',{feature:'music'})));data.concurrent=await call('admin','GET','/api/admin/analytics?start=2027-01-01&end=2027-01-01&grain=day');verify(data,'Cloud handler');
  const py=path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');const run=spawnSync(py,['-X','utf8','-c',python,root],{input:JSON.stringify(fixtures),encoding:'utf8',windowsHide:true,maxBuffer:8000000});assert.equal(run.status,0,run.stderr);const local=JSON.parse(run.stdout);verify(local,'Python HTTP');
  const normalize=d=>JSON.parse(JSON.stringify(d,(k,v)=>['collectedSince','generatedAt'].includes(k)?new Date(v).toISOString():v));assert.deepEqual(normalize(local),normalize(data),'Python和Cloud逐字段一致');
  const checks=['Python真实本地HTTP与Cloud Request处理器均通过同一确定性数据集','北京时间午夜切分、周一起始自然周、自然月与自然年','跨天/跨功能/跨月用户去重，未把日活相加','30秒重复访问去重、心跳跨日续活跃且不增加访问','匿名及角色权限、公司管理操作不计入活跃','非法功能/事件/客户端身份时间、非法日期/未来/超长范围拒绝','完整观察期的次日/七日留存，旧注册及未成熟样本排除','历史未采集null、覆盖不足partial、已覆盖无使用0','持久化采集起点、接口仅返回汇总、不暴露用户资料','Python与Cloud所有响应逐字段一致'];
  const hashes=Object.fromEntries(['04_研发源码/app/r4/backend/analytics.py','04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/analytics-api.ts','04_研发源码/app/cloud/lib/eastern-api.ts'].map(p=>[p,require('crypto').createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex')]));
  const report={at:new Date(realNow()).toISOString(),pass:true,checks,sourceHashes:hashes,scope:'Isolated SQLite fixtures, actual Python HTTP and Cloud API Request handler; no production writes or synthetic historical backfill.'};fs.writeFileSync(path.join(__dirname,'后台数据中心确定性核验.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{Date.now=realNow;sqlite.close();}
})().catch(e=>{const file=path.join(__dirname,'后台数据中心确定性失败记录.json'),runs=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):[];runs.push({at:new Date().toISOString(),error:String(e.stack||e)});fs.writeFileSync(file,JSON.stringify(runs,null,2));console.error(e);process.exitCode=1});
