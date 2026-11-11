// The real handlers and SQL on isolated databases; no production mutations.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process'),{DatabaseSync}=require('node:sqlite');
const root=path.resolve(__dirname,'..'),cloud=path.join(root,'04_研发源码/app/cloud'),esbuild=require(path.join(cloud,'node_modules/esbuild')),stamp=Date.parse('2026-11-05T04:00:00Z');
const mid='12345678-1234-1234-1234-123456789abc',patch={displayName:'新的APP作者名',bio:'更新的公开简介',avatarUrl:'/api/media/'+mid,username:'intruder',verified:true,recommended:false,profileType:'demo'};
const people=[['creator','teacher'],['othercreator','teacher'],['reader','user'],['other','user'],['admin','admin']];
const cp=[['creator',JSON.stringify({displayName:'原作者',bio:'旧简介',avatarUrl:'',reason:'私密审核原因'}),'approved','t-creator',stamp,stamp],['othercreator',JSON.stringify({displayName:'停用作者',bio:'',avatarUrl:''}),'suspended','t-other',stamp,stamp]];
const teacher={id:'t-creator',creatorId:'creator',name:'原作者',nameEn:'Old Name',nameHant:'原作者繁體',nameBo:'old-name',bio:'旧简介',bioEn:'Old biography',bioBo:'old-bio',coverUrl:'',profileType:'real',verified:false,recommended:true,specialty:'保留平台特长',specialtyEn:'Kept specialty'};
const workDefs=[['video','creator','video','published'],['course','creator','course','published'],['draft','creator','article','draft'],['hidden','creator','article','published'],['archived','creator','course','published'],['suspended','othercreator','article','published']];
const works=workDefs.map(([id,owner,type,status])=>[id,owner,JSON.stringify({type,title:'标题'+id,body:'公开正文'+id,format:type==='video'?'video':'article',mediaUrl:'',coverUrl:'',duration:type==='video'?120:0,theme:'healing',categoryIds:[],sections:[]}),status,'private reason',1,stamp,stamp]);
const posts=workDefs.filter(x=>x[2]!=='course').map(([id,owner,type,status])=>[id,owner,'标题'+id,'公开正文'+id,'',id==='hidden'?'withdrawn':status,'private reason',stamp,stamp]);
const contents=[['teachers','t-creator',JSON.stringify(teacher),'published',0,stamp],...['course','archived'].map(id=>['courses',id,JSON.stringify({id,creatorId:'creator',teacherId:'t-creator',zh:'标题'+id,format:'article',access:'public'}),id==='archived'?'archived':'published',0,stamp])];
const favorites=[...workDefs.map(([id])=>[id,'reader','favorite',stamp]),['course','other','favorite',stamp],['video','reader','like',stamp]];
const fixture={stamp,people,cp,works,posts,contents,favorites,mid,patch};
function verify(d){assert.deepEqual(d.eventContract,{early:false,later:true,cap:120,completeCount:1,self:false});assert.equal(d.beforeMapping.profile.teacherId,'');assert.equal(d.afterMapping.profile.teacherId,'t-creator');assert.deepEqual(d.saved.items.map(x=>x.id),['course','video']);assert.deepEqual(d.other.items.map(x=>x.id),['course']);assert.equal(d.saved.items[0].displayName,patch.displayName);assert.equal(d.saved.items[1].duration,120);assert.equal(d.feed.items.find(x=>x.id==='video').authorName,patch.displayName);assert.equal(d.feed.items.find(x=>x.id==='video').duration,120);assert.equal(d.teacher.name,patch.displayName);assert.equal(d.teacher.bio,patch.bio);assert.equal(d.teacher.coverUrl,patch.avatarUrl);assert.equal(d.teacher.verified,false);assert.equal(d.teacher.recommended,true);assert.equal(d.teacher.profileType,'real');assert.equal(d.teacher.specialty,'保留平台特长');assert.equal(d.teacher.specialtyEn,'Kept specialty');assert(!Object.hasOwn(d.teacher,'nameEn'));assert(!Object.hasOwn(d.teacher,'bioEn'));assert.equal(d.user.username,'creator');assert.equal(d.user.name,'login-name-creator');assert.equal(d.privateFields,false);assert.equal(d.withdrawn.items.length,0);assert.equal(d.unverified.profile.teacherId,'');assert.equal(d.archivedMapping.profile.teacherId,'');assert.equal(d.remaining.items.length,0);}
const py=String.raw`
import sys,json,threading,hashlib
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
r=Path(sys.argv[1]);sys.path.insert(0,str(r/'04_研发源码/app/r4/backend'));import server,creator
f=json.load(sys.stdin);clock=[f['stamp']];creator.now=lambda:clock[0];server.now_ms=lambda:clock[0]
dbpath=r/'06_验证与后续工作/收藏资料专项隔离.sqlite3';assert not dbpath.exists();httpd=None
try:
 store=server.Store(dbpath)
 with store.connect() as db:
  for uid,role in f['people']:
   db.execute('INSERT INTO users VALUES (?,?,?,?,?,?)',(uid,uid,'unused','login-name-'+uid,role,f['stamp']))
   db.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(('saved-'+uid).encode()).hexdigest(),uid,4102444800000))
  for table,key in [('creator_profiles','cp'),('creator_works','works'),('posts','posts'),('contents','contents'),('creator_actions','favorites')]:
   for row in f[key]:db.execute('INSERT OR REPLACE INTO '+table+' VALUES ('+','.join('?' for _ in row)+')',row)
  db.execute('INSERT INTO media VALUES (?,?,?,?,?,?)',(f['mid'],'creator','image/png','avatar.png',b'fixture',f['stamp']))
 httpd=ThreadingHTTPServer(('127.0.0.1',0),server.make_handler(store,r/'03_当前APP'));threading.Thread(target=httpd.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(httpd.server_port)
 def call(who,method,url,data=None,status=200):
  try:
   with urlopen(Request(base+url,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Content-Type':'application/json','Cookie':'ew_session=saved-'+who}),timeout=15) as response:code=response.status;d=json.load(response)
  except HTTPError as e:code=e.code;d=json.load(e)
  assert code==status,(url,code,status,d);return d
 call('','GET','/api/creator-saved',None,401);call('reader','POST','/api/creator-saved',{},405)
 result={'beforeMapping':call('reader','GET','/api/creators/creator')}
 ev=lambda event,**extra:dict(workId='video',sessionId='contract-session',event=event,**extra)
 for invalid in [-1,'10',True,None]:call('reader','POST','/api/creator-events',ev('watch',seconds=invalid),400)
 call('reader','POST','/api/creator-events',ev('watch',seconds=1),409)
 own=call('creator','POST','/api/creator-events',ev('play'))['counted']
 call('reader','POST','/api/creator-events',ev('play'));clock[0]+=200000
 assert call('reader','POST','/api/creator-events',ev('watch',seconds=107.9))['counted'] is True
 early=call('reader','POST','/api/creator-events',ev('complete'))['counted']
 call('reader','POST','/api/creator-events',ev('watch',seconds=108.1))
 later=call('reader','POST','/api/creator-events',ev('complete'))['counted'];call('reader','POST','/api/creator-events',ev('complete'))
 call('reader','POST','/api/creator-events',ev('watch',seconds=1000000))
 with store.connect() as db:
  cap=db.execute("SELECT value FROM creator_events WHERE work_id='video' AND visitor='reader' AND event='watch' AND session_id='contract-session'").fetchone()[0]
  count=db.execute("SELECT count(*) FROM creator_events WHERE work_id='video' AND visitor='reader' AND event='complete' AND session_id='contract-session'").fetchone()[0]
 result['eventContract']=dict(early=early,later=later,cap=cap,completeCount=count,self=own)
 call('creator','PATCH','/api/creator/profile',f['patch'])
 with store.connect() as db:
  result['teacher']=json.loads(db.execute("SELECT data FROM contents WHERE kind='teachers' AND id='t-creator'").fetchone()['data']);result['user']=dict(db.execute("SELECT username,name FROM users WHERE id='creator'").fetchone())
  t=dict(result['teacher']);t['verified']=True;db.execute("UPDATE contents SET data=? WHERE kind='teachers' AND id='t-creator'",(json.dumps(t),))
 result['afterMapping']=call('reader','GET','/api/creators/creator');result['saved']=call('reader','GET','/api/creator-saved?owner=other');result['other']=call('other','GET','/api/creator-saved');result['feed']=call('reader','GET','/api/community/posts')
 result['privateFields']=any(k in json.dumps(result['saved']) for k in ['private reason','reason','version','username','ownerId'])
 call('reader','POST','/api/creator-actions',{'workId':'video','action':'favorite','active':True});call('reader','POST','/api/creator-actions',{'workId':'video','action':'favorite','active':False})
 with store.connect() as db:db.execute("UPDATE contents SET status='archived' WHERE kind='courses' AND id='course'")
 result['withdrawn']=call('reader','GET','/api/creator-saved')
 with store.connect() as db:
  t['verified']=False;db.execute("UPDATE contents SET data=? WHERE kind='teachers' AND id='t-creator'",(json.dumps(t),))
 result['unverified']=call('reader','GET','/api/creators/creator')
 with store.connect() as db:db.execute("UPDATE contents SET status='archived' WHERE kind='teachers' AND id='t-creator'")
 result['archivedMapping']=call('reader','GET','/api/creators/creator');result['remaining']=call('creator','GET','/api/creator-saved');print(json.dumps(result,ensure_ascii=False))
finally:
 if httpd:httpd.shutdown();httpd.server_close()
 for suffix in ['','-wal','-shm']:
  p=Path(str(dbpath)+suffix)
  if p.exists():p.unlink()
`;
(async()=>{const bundled=await esbuild.build({entryPoints:[path.join(cloud,'lib/eastern-api.ts')],bundle:true,format:'esm',platform:'node',write:false}),{handleAPI}=await import('data:text/javascript;base64,'+Buffer.from(bundled.outputFiles[0].text).toString('base64'));
 const sqlite=new DatabaseSync(':memory:');sqlite.exec(fs.readFileSync(path.join(cloud,'drizzle/0000_lethal_lucky_pierre.sql'),'utf8'));const db={prepare(sql){let p=[];return{bind(...v){p=v;return this},async first(){return sqlite.prepare(sql).get(...p)||null},async all(){return{results:sqlite.prepare(sql).all(...p)}},async run(){return{meta:{changes:sqlite.prepare(sql).run(...p).changes}}}}},async batch(stmts){sqlite.exec('BEGIN');try{const r=[];for(const s of stmts)r.push(await s.run());sqlite.exec('COMMIT');return r}catch(e){sqlite.exec('ROLLBACK');throw e}}};
 for(const [k,v] of [['cloud_bootstrap_v1','true'],['course_categories_v1','true'],['ai','{}'],['theme','{}']])sqlite.prepare('INSERT INTO settings VALUES (?,?)').run(k,v);for(const [id,role] of people){sqlite.prepare('INSERT INTO users VALUES (?,?,?,?,?,?)').run(id,id,'unused','login-name-'+id,role,stamp);const hash=Buffer.from(await crypto.subtle.digest('SHA-256',new TextEncoder().encode('saved-'+id))).toString('hex');sqlite.prepare('INSERT INTO sessions VALUES (?,?,?)').run(hash,id,4102444800000);}
 const realNow=Date.now;let clock=stamp;Date.now=()=>clock;const call=async(who,m,url,data=null,status=200)=>{const r=await handleAPI(new Request('https://test.local'+url,{method:m,headers:{cookie:'ew_session=saved-'+who,'Content-Type':'application/json'},...(data!==null?{body:JSON.stringify(data)}:{})}),{DB:db,BUCKET:{}}),d=await r.json();assert.equal(r.status,status,url+': '+JSON.stringify(d));return d};
 try{await call('admin','GET','/api/auth/status');for(const [table,key] of [['creator_profiles','cp'],['creator_works','works'],['posts','posts'],['contents','contents'],['creator_actions','favorites']])for(const row of fixture[key])sqlite.prepare('INSERT OR REPLACE INTO '+table+' VALUES ('+row.map(()=>'?').join(',')+')').run(...row);sqlite.prepare('INSERT INTO media VALUES (?,?,?,?,?,?)').run(mid,'creator','image/png','avatar.png','fixture',stamp);
 await call('','GET','/api/creator-saved',null,401);await call('reader','POST','/api/creator-saved',{},405);const d={beforeMapping:await call('reader','GET','/api/creators/creator')};const ev=(event,extra={})=>({workId:'video',sessionId:'contract-session',event,...extra});for(const invalid of [-1,'10',true,null])await call('reader','POST','/api/creator-events',ev('watch',{seconds:invalid}),400);await call('reader','POST','/api/creator-events',ev('watch',{seconds:1}),409);const self=(await call('creator','POST','/api/creator-events',ev('play'))).counted;await call('reader','POST','/api/creator-events',ev('play'));clock+=200000;assert.equal((await call('reader','POST','/api/creator-events',ev('watch',{seconds:107.9}))).counted,true);const early=(await call('reader','POST','/api/creator-events',ev('complete'))).counted;await call('reader','POST','/api/creator-events',ev('watch',{seconds:108.1}));const later=(await call('reader','POST','/api/creator-events',ev('complete'))).counted;await call('reader','POST','/api/creator-events',ev('complete'));await call('reader','POST','/api/creator-events',ev('watch',{seconds:1000000}));d.eventContract={early,later,cap:sqlite.prepare("SELECT value FROM creator_events WHERE work_id='video' AND visitor='reader' AND event='watch' AND session_id='contract-session'").get().value,completeCount:sqlite.prepare("SELECT count(*) n FROM creator_events WHERE work_id='video' AND visitor='reader' AND event='complete' AND session_id='contract-session'").get().n,self};await call('creator','PATCH','/api/creator/profile',patch);d.teacher=JSON.parse(sqlite.prepare("SELECT data FROM contents WHERE kind='teachers' AND id='t-creator'").get().data);d.user=sqlite.prepare("SELECT username,name FROM users WHERE id='creator'").get();let t={...d.teacher,verified:true};sqlite.prepare("UPDATE contents SET data=? WHERE kind='teachers' AND id='t-creator'").run(JSON.stringify(t));d.afterMapping=await call('reader','GET','/api/creators/creator');d.saved=await call('reader','GET','/api/creator-saved?owner=other');d.other=await call('other','GET','/api/creator-saved');d.feed=await call('reader','GET','/api/community/posts');d.privateFields=['private reason','reason','version','username','ownerId'].some(k=>JSON.stringify(d.saved).includes(k));await call('reader','POST','/api/creator-actions',{workId:'video',action:'favorite',active:true});await call('reader','POST','/api/creator-actions',{workId:'video',action:'favorite',active:false});sqlite.prepare("UPDATE contents SET status='archived' WHERE kind='courses' AND id='course'").run();d.withdrawn=await call('reader','GET','/api/creator-saved');t.verified=false;sqlite.prepare("UPDATE contents SET data=? WHERE kind='teachers' AND id='t-creator'").run(JSON.stringify(t));d.unverified=await call('reader','GET','/api/creators/creator');sqlite.prepare("UPDATE contents SET status='archived' WHERE kind='teachers' AND id='t-creator'").run();d.archivedMapping=await call('reader','GET','/api/creators/creator');d.remaining=await call('creator','GET','/api/creator-saved');verify(d);
 const python=path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'),run=spawnSync(python,['-X','utf8','-c',py,root],{input:JSON.stringify(fixture),encoding:'utf8',windowsHide:true,maxBuffer:6000000});assert.equal(run.status,0,run.stderr);const local=JSON.parse(run.stdout);verify(local);const normalize=v=>JSON.parse(JSON.stringify(v,(k,v)=>['createdAt','updatedAt','savedAt'].includes(k)?new Date(v).toISOString():v));assert.deepEqual(normalize(local),normalize(d));
 const report={at:new Date(realNow()).toISOString(),pass:true,checks:['完播首报未达阈值可重试，watch参数/时间/素材时长上界和counted契约双端一致','服务端本人收藏唯一真源与跨账号隔离，普通用户可查，匿名401','收藏排除草稿、撤回、下架课程及停用创作者，不返回审核/登录字段','收藏增删幂等，隐藏内容自动不再出现在列表','公开teacherId仅映射已发布、real且verified的本创作者老师资料','公开展示名/简介/头像同步老师与视频作者，清除失效翻译回退同源','PATCH不改登录username/name和平台verified/recommended/profileType/特长','Python真实HTTP与Cloud Request+SQLite关键响应逐字段一致'],sourceHashes:Object.fromEntries(['r4/backend/creator.py','r4/backend/server.py','cloud/lib/creator-api.ts','cloud/lib/eastern-api.ts'].map(p=>['04_研发源码/app/'+p,require('crypto').createHash('sha256').update(fs.readFileSync(path.join(root,'04_研发源码/app',p))).digest('hex')])),scope:'Isolated synthetic fixtures; no production changes.'};fs.writeFileSync(path.join(__dirname,'创作者收藏与资料同源核验.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{Date.now=realNow;sqlite.close();}
})().catch(e=>{console.error(e);const p=path.join(__dirname,'创作者收藏与资料同源失败记录.json'),runs=fs.existsSync(p)?JSON.parse(fs.readFileSync(p)):[];runs.push({at:new Date().toISOString(),error:String(e.stack||e)});fs.writeFileSync(p,JSON.stringify(runs,null,2));process.exitCode=1});
