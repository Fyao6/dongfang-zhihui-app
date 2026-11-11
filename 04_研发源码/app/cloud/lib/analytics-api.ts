// Server-owned identity/time; only account/day/feature aggregates are stored.
const features:Record<string,string>={home:'首页',life:'生命地图',body:'身体地图',mind:'心智地图',practice:'禅修与练习',academy:'智慧馆',community:'社群',ai:'AI对话',profile:'我的',checkin:'签到',cards:'智慧卡片',music:'音乐',device:'设备',other:'其他页面'};
const members="u.role IN ('user','teacher')",dayMs=86400000,offset=8*3600000;
const dayAt=(n:number)=>new Date(n+offset).toISOString().slice(0,10),midnight=(s:string)=>Date.parse(s+'T00:00:00Z')-offset,addDays=(s:string,n:number)=>new Date(Date.parse(s+'T00:00:00Z')+n*dayMs).toISOString().slice(0,10);
const ddl=[`CREATE TABLE IF NOT EXISTS activity_daily(user_id TEXT NOT NULL REFERENCES users(id),day TEXT NOT NULL,feature TEXT NOT NULL,visits INTEGER NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,last_visit INTEGER NOT NULL,PRIMARY KEY(user_id,day,feature))`,`CREATE INDEX IF NOT EXISTS activity_daily_day ON activity_daily(day,user_id)`];
const upsert=`INSERT INTO activity_daily VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id,day,feature) DO UPDATE SET visits=activity_daily.visits+CASE WHEN excluded.visits=1 AND (activity_daily.last_visit=0 OR excluded.last_visit-activity_daily.last_visit>=30000) THEN 1 ELSE 0 END,last_seen=max(activity_daily.last_seen,excluded.last_seen),last_visit=CASE WHEN excluded.visits=1 AND (activity_daily.last_visit=0 OR excluded.last_visit-activity_daily.last_visit>=30000) THEN excluded.last_visit ELSE activity_daily.last_visit END`;
function bucketStart(s:string,grain:string){if(grain==='week')return addDays(s,-((new Date(s+'T00:00:00Z').getUTCDay()+6)%7));if(grain==='month')return s.slice(0,7)+'-01';if(grain==='year')return s.slice(0,4)+'-01-01';return s;}
function nextBucket(s:string,grain:string){if(grain==='week')return addDays(s,7);if(grain==='month'){const d=new Date(s+'T00:00:00Z');d.setUTCMonth(d.getUTCMonth()+1);return d.toISOString().slice(0,10)}if(grain==='year')return String(Number(s.slice(0,4))+1)+'-01-01';return addDays(s,1);}
export async function initAnalytics(a:any){if(!await a.one("SELECT 1 FROM settings WHERE key='analytics_started_v1'"))await a.db.batch([...ddl.map(s=>a.stmt(s)),a.stmt('INSERT OR IGNORE INTO settings VALUES (?,?)','analytics_started_v1',JSON.stringify({startedAt:Date.now()}))]);}
export async function analyticsRoute(a:any,p:string,m:string,fail:(n:number,s:string)=>never){
 if(!['/api/analytics/activity','/api/admin/analytics'].includes(p))return undefined;
 if(p==='/api/analytics/activity'){
  if(m!=='POST')fail(405,'不支持的操作。');a.require();const d=await a.body(),feature=d.feature,kind=Object.hasOwn(d,'kind')?d.kind:'visit';
  if(Object.keys(d).some(k=>!['feature','kind'].includes(k))||typeof feature!=='string'||!Object.hasOwn(features,feature)||!['visit','heartbeat'].includes(kind))fail(400,'统计仅接受指定功能及访问或心跳事件。');
  if(!['user','teacher'].includes(a.user.role))return {ok:true,ignored:true};
  const stamp=Date.now(),visit=kind==='visit'?1:0;await a.rate('analytics:'+a.user.id,180);await a.run(upsert,a.user.id,dayAt(stamp),feature,visit,stamp,stamp,visit?stamp:0);return {ok:true};
 }
 if(m!=='GET')fail(405,'不支持的操作。');a.require(['admin','operator']);
 const stamp=Date.now(),today=dayAt(stamp),params=a.url.searchParams;
 if([...params.keys()].some((k:string)=>!['start','end','grain'].includes(k)||params.getAll(k).length!==1))fail(400,'统计筛选参数无效。');
 function parseDay(key:string,fallback:string){const s=params.get(key)??fallback;if(!/^\d{4}-\d{2}-\d{2}$/.test(s)||s<'1970-01-01'||!Number.isFinite(Date.parse(s+'T00:00:00Z'))||new Date(s+'T00:00:00Z').toISOString().slice(0,10)!==s)fail(400,'日期须为合法的YYYY-MM-DD，且不早于1970年。');return s;}
 const start=parseDay('start',addDays(today,-29)),end=parseDay('end',today),grain=params.get('grain')??'day';
 if(!['day','week','month','year'].includes(grain)||start>end||end>today||(midnight(end)-midnight(start))/dayMs>=3660)fail(400,'请选择不含未来日期、最长3660天的有效日期范围和统计周期。');
 const since=Number(JSON.parse((await a.one("SELECT data FROM settings WHERE key='analytics_started_v1'")).data).startedAt);
 const coverage=(first:string,last:string)=>midnight(addDays(last,1))<=since?'uncollected':midnight(first)>=since&&midnight(addDays(last,1))<=stamp?'complete':'partial';
 const state=coverage(start,end),userDay="date(u.created/1000,'unixepoch','+8 hours')";
 const bucket=(x:string)=>({day:x,week:`date(${x},'-'||((CAST(strftime('%w',${x}) AS INTEGER)+6)%7)||' days')`,month:`substr(${x},1,7)||'-01'`,year:`substr(${x},1,4)||'-01-01'`} as Record<string,string>)[grain];
 const starts:Record<string,string>={day:today,week:bucketStart(today,'week'),month:bucketStart(today,'month'),year:bucketStart(today,'year')};
 const [summaryRow,usersRow,windowRow,eventRows,newRows,featureRows]=await Promise.all([
  a.one(`SELECT count(DISTINCT a.user_id) activeUsers,coalesce(sum(a.visits),0) visits FROM activity_daily a JOIN users u ON u.id=a.user_id WHERE ${members} AND a.day>=? AND a.day<=? AND a.first_seen<=?`,start,end,stamp),
  a.one(`SELECT count(*) registeredUsers,coalesce(sum(CASE WHEN u.created>=? AND u.created<=? THEN 1 ELSE 0 END),0) newUsers FROM users u WHERE ${members} AND u.created<=?`,midnight(start),Math.min(stamp,midnight(addDays(end,1))-1),stamp),
  a.one(`SELECT ${Object.keys(starts).map(key=>`count(DISTINCT CASE WHEN a.day>=? THEN a.user_id END) AS "${key}"`).join(',')} FROM activity_daily a JOIN users u ON u.id=a.user_id WHERE ${members} AND a.day>=? AND a.day<=? AND a.first_seen<=?`,...Object.values(starts),Object.values(starts).sort()[0],today,stamp),
  a.all(`SELECT ${bucket('a.day')} bucket,count(DISTINCT a.user_id) activeUsers,coalesce(sum(a.visits),0) visits FROM activity_daily a JOIN users u ON u.id=a.user_id WHERE ${members} AND a.day>=? AND a.day<=? AND a.first_seen<=? GROUP BY bucket`,start,end,stamp),
  a.all(`SELECT ${bucket(userDay)} bucket,count(*) n FROM users u WHERE ${members} AND u.created>=? AND u.created<=? GROUP BY bucket`,midnight(start),Math.min(stamp,midnight(addDays(end,1))-1)),
  a.all(`SELECT a.feature,count(DISTINCT a.user_id) activeUsers,coalesce(sum(a.visits),0) visits FROM activity_daily a JOIN users u ON u.id=a.user_id WHERE ${members} AND a.day>=? AND a.day<=? AND a.first_seen<=? GROUP BY a.feature`,start,end,stamp)
 ]);
 const summary={...usersRow,activeUsers:state==='uncollected'?null:summaryRow.activeUsers,visits:state==='uncollected'?null:summaryRow.visits,coverage:state};
 const windows=Object.fromEntries(Object.entries(starts).map(([key,first])=>[key,{start:first,end:today,activeUsers:coverage(first,today)==='uncollected'?null:windowRow[key],coverage:coverage(first,today)}]));
 const events=new Map(eventRows.map((r:any)=>[r.bucket,r])),newUsers=new Map(newRows.map((r:any)=>[r.bucket,r.n])),trend:any[]=[];
 for(let cursor=start;cursor<=end;){const natural=bucketStart(cursor,grain),last=[end,addDays(nextBucket(natural,grain),-1)].sort()[0],row:any=events.get(natural)||{},c=coverage(cursor,last);trend.push({date:cursor,end:last,activeUsers:c==='uncollected'?null:row.activeUsers||0,newUsers:newUsers.get(natural)||0,visits:c==='uncollected'?null:row.visits||0,coverage:c});cursor=addDays(last,1);}
 const byFeature=new Map(featureRows.map((r:any)=>[r.feature,r]));
 const featureStats=Object.entries(features).map(([id,label])=>{const row:any=byFeature.get(id)||{};return {id,label,activeUsers:state==='uncollected'?null:row.activeUsers||0,visits:state==='uncollected'?null:row.visits||0}});
 const retention=await Promise.all([1,7].map(async days=>{const r=await a.one(`WITH cohort AS (SELECT u.id,${userDay} day FROM users u WHERE ${members} AND u.created>=? AND u.created>=? AND u.created<=? AND date(${userDay},?)<?) SELECT count(*) eligibleUsers,coalesce(sum(CASE WHEN EXISTS(SELECT 1 FROM activity_daily a WHERE a.user_id=c.id AND a.day=date(c.day,?)) THEN 1 ELSE 0 END),0) returnedUsers FROM cohort c`,since,midnight(start),Math.min(stamp,midnight(addDays(end,1))-1),`+${days} days`,today,`+${days} days`);return {days,eligibleUsers:r.eligibleUsers,returnedUsers:r.returnedUsers,rate:r.eligibleUsers?Math.round(r.returnedUsers*10000/r.eligibleUsers)/100:null};}));
 return {timezone:'Asia/Shanghai',generatedAt:new Date(stamp).toISOString(),collectedSince:new Date(since).toISOString(),range:{start,end,grain},windows,summary,trend,features:featureStats,retention};
}
