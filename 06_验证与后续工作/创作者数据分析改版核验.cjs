// Both deployed handler SQL and local analytics SQL, isolated SQLite and fixed clock.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{spawnSync}=require('child_process');
const {DatabaseSync}=require('node:sqlite');
const root=path.resolve(__dirname,'..'),cloud=path.join(root,'04_研发源码/app/cloud'),esbuild=require(path.join(cloud,'node_modules/esbuild'));
const stamp=Date.parse('2026-11-04T04:00:00Z'),at=s=>Date.parse(s),users=['alice','bob','reader'];
const profileRows=[['alice',JSON.stringify({displayName:'Alice',bio:'',avatarUrl:''}),'approved','teacher-a',at('2026-10-01T00:00Z'),stamp],['bob',JSON.stringify({displayName:'Bob',bio:'',avatarUrl:''}),'approved','teacher-b',at('2026-11-01T00:00Z'),stamp]];
const workRows=[['a1','alice',{type:'course',title:'课程A',coverUrl:'/api/media/test-cover',duration:120}],['a2','alice',{type:'video',title:'视频A',coverUrl:'',duration:30}],['b1','bob',{type:'video',title:'其他老师',duration:60}]].map(([id,owner,d])=>[id,owner,JSON.stringify(d),'published','',1,at('2026-10-30T00:00Z'),stamp]);
let seq=0;const event=(owner,id,visitor,event,value,date)=>['e'+(++seq),owner,id,visitor,event,'s'+seq,value,typeof date==='number'?date:at(date)];
const events=[
 event('alice','a1','u1','impression',1,'2026-10-28T16:00Z'),event('alice','a1','u1','view',1,'2026-10-28T16:00Z'),event('alice','a2','u1','view',1,'2026-10-30T00:00Z'),
 event('alice','a1','u1','play',1,'2026-10-30T00:00Z'),event('alice','a1','u1','watch',35.4,'2026-10-30T00:01Z'),event('alice','a1','u1','complete',1,'2026-11-01T00:00Z'),
 event('alice','a1','u1','learn',1,'2026-10-30T00:00Z'),event('alice','a1','u1','learn',1,'2026-10-31T00:00Z'),event('alice','a1','u2','learn',1,'2026-11-01T00:00Z'),event('alice','profile:alice','u3','profile_view',1,'2026-11-02T00:00Z'),
 event('alice','a1','u2','view',1,'2026-10-28T15:59:59.999Z'),event('alice','a2','u2','play',1,'2026-10-25T00:00Z'),event('alice','a2','u2','watch',9.5,'2026-10-25T00:01Z'),event('alice','a1','u2','learn',1,'2026-10-25T00:00Z'),event('alice','a1','u2','learn',1,'2026-10-26T00:00Z'),
 event('alice','a1','u4','view',1,'2026-10-21T00:00Z'),event('alice','a1','u4','view',1,stamp+1),event('bob','b1','u3','view',1,'2026-11-01T00:00Z')];
const actions=[['a1','u1','like',at('2026-10-31T00:00Z')],['a1','u2','favorite',at('2026-10-31T00:00Z')],['a2','u3','share',at('2026-11-01T00:00Z')],['a2','u4','like',at('2026-10-25T00:00Z')],['a2','future','like',stamp+1],['b1','u5','share',at('2026-11-01T00:00Z')]];
const follows=[['alice','old',at('2026-10-10T00:00Z')],['alice','current',at('2026-11-02T00:00Z')],['alice','previous',at('2026-10-26T00:00Z')],['alice','future',stamp+1],['bob','other',at('2026-11-02T00:00Z')]];
const services=[['s1','reader','teacher-a','Alice','咨询','2026-11-04','pending',at('2026-11-01T00:00Z')],['s2','reader','teacher-a','Alice','过去咨询','2026-10-28','closed',at('2026-10-25T00:00Z')],['s3','reader','teacher-a','Alice','未来','2026-11-05','pending',stamp+1],['s4','reader','teacher-b','Bob','其他','2026-11-04','pending',at('2026-11-01T00:00Z')]];
const fixtures={stamp,profiles:profileRows,works:workRows,events,actions,follows,services},checks=[];
function verify(d,who){
 assert.equal(d.daily.length,7);assert.deepEqual(d.period,{from:'2026-10-29',to:'2026-11-04',previousFrom:'2026-10-22',previousTo:'2026-10-28',timeZone:'Asia/Shanghai'});
 if(who==='alice'){
  assert.deepEqual(d.totals,{followers:3,newFollowers:1,profileViews:1,impressions:1,views:2,plays:1,watchSeconds:35.4,completions:1,likes:1,favorites:1,shares:1,learners:2,consultations:1});
  assert.deepEqual(d.previousTotals,{followers:null,newFollowers:1,profileViews:0,impressions:0,views:1,plays:1,watchSeconds:9.5,completions:0,likes:1,favorites:0,shares:0,learners:1,consultations:1});
  assert.equal(d.comparisonAvailable,true);assert.equal(d.daily.reduce((s,x)=>s+x.views,0),2);assert.equal(d.daily.reduce((s,x)=>s+x.likes,0),1);assert.equal(d.daily.reduce((s,x)=>s+x.learners,0),3);assert.equal(d.daily[0].views,1);assert.equal(d.daily[0].date,'2026-10-29');assert.equal(d.daily[6].date,'2026-11-04');
  const w=d.works.find(x=>x.id==='a1');assert.equal(w.impressions,1);assert.equal(w.coverUrl,'/api/media/test-cover');assert.equal(w.duration,120);assert.equal(w.learners,2);assert.equal(w.createdAt,'2026-10-30T00:00:00.000Z');assert(d.works.every(x=>x.id!=='b1'));
 }else{assert.equal(d.totals.views,1);assert.equal(d.totals.shares,1);assert.equal(d.totals.followers,1);assert.equal(d.comparisonAvailable,false);assert.equal(d.previousTotals.views,0);assert.equal(d.works.length,1);assert.equal(d.works[0].id,'b1');}
}
(async()=>{
 const compiled=await esbuild.build({entryPoints:[path.join(cloud,'lib/eastern-api.ts')],bundle:true,platform:'node',format:'esm',write:false});const {handleAPI}=await import('data:text/javascript;base64,'+Buffer.from(compiled.outputFiles[0].text).toString('base64'));
 const sqlite=new DatabaseSync(':memory:');sqlite.exec(fs.readFileSync(path.join(cloud,'drizzle/0000_lethal_lucky_pierre.sql'),'utf8'));
 const db={prepare(sql){let params=[];return{bind(...p){params=p;return this},async first(){return sqlite.prepare(sql).get(...params)||null},async all(){return{results:sqlite.prepare(sql).all(...params)}},async run(){return{meta:{changes:sqlite.prepare(sql).run(...params).changes}}}}},async batch(stmts){sqlite.exec('BEGIN');try{const r=[];for(const s of stmts)r.push(await s.run());sqlite.exec('COMMIT');return r}catch(e){sqlite.exec('ROLLBACK');throw e}}};
 for(const [k,v] of [['cloud_bootstrap_v1','true'],['course_categories_v1','true'],['ai','{}'],['theme','{}']])sqlite.prepare('INSERT INTO settings VALUES (?,?)').run(k,v);
 const cookies={};for(const name of users){sqlite.prepare('INSERT INTO users VALUES (?,?,?,?,?,?)').run(name,name,'unused',name,name==='reader'?'user':'teacher',stamp-10000000);const token='analytics-session-'+name,hash=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token))).toString('hex');sqlite.prepare('INSERT INTO sessions VALUES (?,?,?)').run(hash,name,stamp+10000000);cookies[name]='ew_session='+token;}
 const realNow=Date.now;Date.now=()=>stamp;
 try{const init=await handleAPI(new Request('https://test.local/api/creator/me',{headers:{cookie:cookies.alice}}),{DB:db});assert.equal(init.status,200);
  for(const [table,rows] of [['creator_profiles',profileRows],['creator_works',workRows],['creator_events',events],['creator_actions',actions],['creator_follows',follows],['service_requests',services]])for(const row of rows)sqlite.prepare('INSERT OR REPLACE INTO '+table+' VALUES ('+row.map(()=>'?').join(',')+')').run(...row);
  const cloudData={};for(const who of ['alice','bob']){const r=await handleAPI(new Request('https://test.local/api/creator/analytics?days=7',{headers:{cookie:cookies[who]}}),{DB:db});assert.equal(r.status,200);cloudData[who]=await r.json();verify(cloudData[who],who);}
  checks.push('云端：两个北京时间完整周期、边界毫秒与未来事件排除');checks.push('云端：所有趋势指标、聚合去重学习人数与作品元数据');checks.push('云端：前期可比性与其他老师账号隔离');
  const py=String.raw`
import sys,json,tempfile,sqlite3
from pathlib import Path
r=Path(sys.argv[1]);sys.path.insert(0,str(r/'04_研发源码/app/r4/backend'))
import server,creator
f=json.load(sys.stdin);creator.now=lambda:f['stamp']
dbpath=r/'06_验证与后续工作/创作者数据分析临时.sqlite3'
assert not dbpath.exists()
try:
 store=server.Store(dbpath)
 with store.connect() as db:
  for name in ['alice','bob','reader']:db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)',(name,name,'unused',name,'user' if name=='reader' else 'teacher',f['stamp']-10000000))
  for table,key in [('creator_profiles','profiles'),('creator_works','works'),('creator_events','events'),('creator_actions','actions'),('creator_follows','follows'),('service_requests','services')]:
   for row in f[key]:db.execute('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in row)+')',row)
 result={}
 for who in ['alice','bob']:
  class H:
   path='/api/creator/analytics?days=7'
   user={'id':who,'role':'teacher'}
  handler=creator.Creator(store,H(),server.ApiError,lambda *a:None)
  with store.connect() as db:p=db.execute('SELECT * FROM creator_profiles WHERE user_id=?',(who,)).fetchone()
  result[who]=handler.analytics(p)
 print(json.dumps(result,ensure_ascii=False))
finally:
 for suffix in ['','-wal','-shm']:
  p=Path(str(dbpath)+suffix)
  if p.exists():p.unlink()
`;
  const python=path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');const result=spawnSync(python,['-X','utf8','-c',py,root],{input:JSON.stringify(fixtures),encoding:'utf8',windowsHide:true,maxBuffer:4000000});assert.equal(result.status,0,result.stderr);const localData=JSON.parse(result.stdout);
  // Python ISO formatting omits milliseconds; normalize only date serializations before parity.
  for(const who of ['alice','bob']){for(const w of localData[who].works){w.createdAt=new Date(w.createdAt).toISOString();w.updatedAt=new Date(w.updatedAt).toISOString()}verify(localData[who],who);localData[who].startedAt=new Date(localData[who].startedAt).toISOString();assert.deepEqual(localData[who],cloudData[who]);}
  checks.push('本机：同一数据集的所有指标、周期、趋势与云端逐字段一致');checks.push('真实互动关系按当前保留状态统计；历史粉丝存量返回null而非伪造');
 }finally{Date.now=realNow;sqlite.close();}
 const report={at:new Date().toISOString(),pass:true,checks,scope:'Actual local/cloud analytics SQL with fixed-clock seeded SQLite fixtures; no production activity or model calls'};fs.writeFileSync(path.join(__dirname,'创作者数据分析改版核验.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
})().catch(e=>{console.error(e);process.exitCode=1});
