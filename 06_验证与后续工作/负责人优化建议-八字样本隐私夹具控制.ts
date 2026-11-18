// Fixed synthetic DB controls and native R2 fault/hold observation. No product decision is mocked.
import spec from './负责人优化建议-隐私逐域场景夹具.json';
const faults=new Map<string,any>(),events:any[]=[];
let nativeBucket:any,nativeDB:any;
const proxies=new WeakMap<object,any>();
const uuid=()=>crypto.randomUUID(),now=()=>Date.now();
const stmt=(db:any,sql:string,...args:any[])=>db.prepare(sql).bind(...args);
async function all(db:any,sql:string,...args:any[]){return (await stmt(db,sql,...args).all()).results;}
async function batch(db:any,ops:any[]){for(let i=0;i<ops.length;i+=100)await db.batch(ops.slice(i,i+100));}
async function keyForMedia(db:any,mediaId:string){
 if(!/^[a-f0-9-]{36}$/i.test(mediaId))throw Error('Known fixture media required');
 const row=await stmt(db,'SELECT object_key FROM media WHERE id=? UNION ALL SELECT object_key FROM privacy_object_deletions WHERE media_id=? LIMIT 1',mediaId,mediaId).first();
 if(!row||row.object_key!=='media/'+mediaId)throw Error('Only exact managed owned media keys are controllable');return row.object_key;
}
async function faultAt(key:string,method:string,when:string){
 const state=faults.get(key);if(!state||state.method!==method||state.when!==when||state.remaining<1)return;
 --state.remaining;state.entered++;events.push({method,when,mediaId:key.slice(6),event:state.kind});
 if(state.kind==='throw')throw Error('QA_ONLY_NATIVE_STORAGE_FAILURE');
 await new Promise<void>(resolve=>{const timer=setTimeout(resolve,30000);state.waiters.push(()=>{clearTimeout(timer);resolve();});});
}
export function controlledBucket(bucket:any,db:any){
 nativeBucket=bucket;nativeDB=db;if(proxies.has(bucket))return proxies.get(bucket);
 const proxy=new Proxy(bucket,{get(target,method){const value=Reflect.get(target,method);if(typeof value!=='function')return value;
  if(!['put','head','get','delete'].includes(String(method)))return value.bind(target);
  return async(...args:any[])=>{const key=args[0],managed=typeof key==='string'&&/^media\/[a-f0-9-]{36}$/i.test(key);if(managed){events.push({method,mediaId:key.slice(6),event:'called'});await faultAt(key,String(method),'before');}const result=await value.apply(target,args);if(managed){events.push({method,mediaId:key.slice(6),event:'native-completed',...(method==='head'?{exists:!!result}:{})});await faultAt(key,String(method),'after');}return result;};
 }});proxies.set(bucket,proxy);return proxy;
}
export async function bucketControl(data:any,db:any){
 if(!String(data.action||'').startsWith('bucket-'))return undefined;
 if(!nativeBucket)throw Error('Native fixture bucket unavailable');
 if(data.action==='bucket-clear'){for(const state of faults.values())for(const release of state.waiters)release();faults.clear();return {cleared:true};}
 if(data.action==='bucket-stats')return {events:events.map(x=>({...x})),held:[...faults.values()].reduce((n,x)=>n+x.waiters.length,0),nativeR2:true,objectKeysIncluded:false};
 if(data.action==='bucket-seed-media'){const count=data.count??1;if(!Number.isInteger(count)||count<1||count>60||!await stmt(db,'SELECT 1 FROM users WHERE id=?',data.owner).first())throw Error('Bounded owned synthetic media seed required');const ids=Array.from({length:count},uuid),binary=Uint8Array.from(atob(spec.bulkWavBase64),c=>c.charCodeAt(0)),proxy=controlledBucket(nativeBucket,db);for(const id of ids)await proxy.put('media/'+id,binary,{httpMetadata:{contentType:'audio/wav'}});await batch(db,ids.map(id=>stmt(db,'INSERT INTO media(id,owner,mime,filename,object_key,created) VALUES(?,?,?,?,?,?)',id,data.owner,'audio/wav','synthetic-bulk.wav','media/'+id,now())));return {seededRows:ids.length,ids,domain:'privateMedia',actualR2Puts:ids.length,syntheticOnly:true};}
 const key=await keyForMedia(db,data.mediaId);
 if(data.action==='bucket-share-key'){if(!await stmt(db,'SELECT 1 FROM media WHERE id=?',data.otherMediaId).first()||data.otherMediaId===data.mediaId)throw Error('Second actual synthetic media required');await stmt(db,'UPDATE media SET object_key=? WHERE id=?',key,data.otherMediaId).run();return {shared:true,mediaId:data.mediaId,otherMediaId:data.otherMediaId,syntheticLegacyMetadata:true};}
 if(data.action==='bucket-unmanage-key'){await stmt(db,'UPDATE media SET object_key=? WHERE id=?','foreign-fixture/'+data.mediaId,data.mediaId).run();return {unmanaged:true,mediaId:data.mediaId,syntheticLegacyMetadata:true};}
 if(data.action==='bucket-probe'){const value=await nativeBucket.head(key);return {mediaId:data.mediaId,exists:!!value,bytes:value?.size||0,nativeR2Head:true};}
 if(data.action==='bucket-release'){const state=faults.get(key);if(state){while(state.waiters.length)state.waiters.shift()();}return {released:true};}
 if(data.action==='bucket-fault'){
  if(!['delete','head','get'].includes(data.method)||!['before','after'].includes(data.when)||!['throw','hold'].includes(data.kind)||!Number.isInteger(data.remaining)||data.remaining<1||data.remaining>5)throw Error('Invalid fixed bucket fault');
  faults.set(key,{method:data.method,when:data.when,kind:data.kind,remaining:data.remaining,entered:0,waiters:[]});return {armed:true,mediaId:data.mediaId,method:data.method,when:data.when,kind:data.kind};
 }
 throw Error('Unknown fixed bucket action');
}
export async function fixtureControl(data:any,db:any){
 const action=String(data.action||'');if(!action.startsWith('domain-')||action==='domain-clock')return undefined;
 const owner=data.owner||'',stamp=now();
 if(action==='domain-seed-legacy-output'){const row=await stmt(db,"SELECT id FROM ai_gateway_jobs WHERE id=? AND owner=? AND status IN ('succeeded','partial','failed','cancelled') AND charged_credits IS NOT NULL",data.jobId,owner).first();if(!row)throw Error('Actual terminal synthetic gateway job required');await stmt(db,'UPDATE ai_gateway_jobs SET output_text=? WHERE id=? AND owner=?',spec.canaries.gatewayOutput,row.id,owner).run();return {seededLegacyOutputRows:1,jobId:row.id,actualTerminalAccountingPreserved:true,syntheticOnly:true};}
 if(action==='domain-create-unknown-table'){await db.prepare('CREATE TABLE IF NOT EXISTS qa_domain_unclassified(id TEXT PRIMARY KEY,owner TEXT NOT NULL,body TEXT NOT NULL)').run();return {created:true,table:'qa_domain_unclassified',syntheticOnly:true};}
 if(['domain-unknown-reference','domain-attempt-dead-unknown','domain-unknown-unrelated'].includes(action)){
  if(!await stmt(db,'SELECT 1 FROM users WHERE id=?',owner).first())throw Error('Existing synthetic owner required');let mediaId=data.mediaId||'';
  if(action==='domain-unknown-reference'){if(!await stmt(db,'SELECT 1 FROM media WHERE id=? AND owner=?',mediaId,owner).first())throw Error('Owned fixture media required');}
  else if(action==='domain-attempt-dead-unknown'){if(!await stmt(db,'SELECT 1 FROM privacy_media_tombstones WHERE media_id=? AND owner=?',mediaId,owner).first())throw Error('Owned tombstone required');}
  else{mediaId=uuid();if(await stmt(db,'SELECT 1 FROM privacy_media_tombstones WHERE media_id=?',mediaId).first())throw Error('Unrelated synthetic identity required');}
  const payload='{"media":"'+[...mediaId].map(c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0')).join('')+'"}';
  try{await stmt(db,'INSERT INTO qa_domain_unclassified VALUES(?,?,?)',uuid(),owner,payload).run();return {blocked:false,mediaId,jsonUnicodeBareMediaId:true,actualDatabaseTrigger:true,syntheticOnly:true};}catch(error:any){if(!String(error?.message||error).includes('privacy_deleted_media_reference'))throw error;return {blocked:true,jsonUnicodeBareMediaId:true,actualDatabaseTrigger:true,syntheticOnly:true};}
 }
 if(['domain-seed-service','domain-seed-draft','domain-seed-profile','domain-seed-unknown'].includes(action)){
  if(!await stmt(db,'SELECT 1 FROM users WHERE id=?',owner).first())throw Error('Existing synthetic owner required');
  const count=data.count??1;if(!Number.isInteger(count)||count<1||count>spec.bulkLimit)throw Error('Invalid synthetic seed count');
  let ids=Array.from({length:count},uuid),body=spec.canaries.body,domain='serviceRequestContent';const ops:any[]=[];
  if(data.mediaId){if(!await stmt(db,'SELECT 1 FROM media WHERE id=? AND owner=?',data.mediaId,owner).first())throw Error('Owned fixture media required');body+=' /api/media/'+data.mediaId;}
  if(action==='domain-seed-service')for(const id of ids)ops.push(stmt(db,spec.serviceInsert,id,owner,'privacy-domain-qa-teacher','独立合成老师标识',body+'_'+id,'2030-01-02','pending',stamp));
  else if(action==='domain-seed-draft'){domain='creatorDrafts';const status=data.status||'draft';if(!['draft','published','rejected','manual_review'].includes(status))throw Error('Invalid fixed draft state');const payload=JSON.stringify({type:'article',title:'逐域合成草稿',body,format:'article',theme:'healing',categoryIds:[],mediaUrl:'',coverUrl:'',sections:[],duration:0});for(const id of ids)ops.push(stmt(db,spec.draftInsert,id,owner,payload,status,'',1,stamp,stamp));}
  else if(action==='domain-seed-profile'){domain='creatorPrivateProfiles';const status=data.status||'pending';if(count!==1||!['pending','rejected','approved','suspended'].includes(status))throw Error('Invalid fixed profile state');ids=[owner];ops.push(stmt(db,spec.profileInsert,owner,JSON.stringify({displayName:'逐域合成申请',bio:body,avatarUrl:''}),status,'',stamp,stamp));}
  else{await db.prepare('CREATE TABLE IF NOT EXISTS qa_domain_unclassified(id TEXT PRIMARY KEY,owner TEXT NOT NULL,body TEXT NOT NULL)').run();await batch(db,ids.map(id=>stmt(db,'INSERT INTO qa_domain_unclassified VALUES(?,?,?)',id,owner,spec.canaries.unknownBody)));return {seededRows:ids.length,ids,unknownTable:'qa_domain_unclassified',syntheticOnly:true};}
  await batch(db,ops);if(data.historicalUnknown!==undefined&&typeof data.historicalUnknown!=='boolean')throw Error('Boolean history flag required');if(data.historicalUnknown)await batch(db,ids.map(id=>stmt(db,'DELETE FROM privacy_retention_tracking WHERE owner=? AND scope=? AND k1=?',owner,domain,id)));
  return {seededRows:ids.length,ids,domain,historicalUnknownFixture:!!data.historicalUnknown,syntheticOnly:true};
 }
 if(action==='domain-fault'){const table=data.table||'privacy_domain_receipts';if(typeof data.enabled!=='boolean'||!['privacy_domain_receipts','privacy_media_tombstones'].includes(table))throw Error('Invalid fixed SQL fault');const name=table==='privacy_domain_receipts'?'qa_domain_receipt_fault':'qa_domain_media_fault';await db.prepare('DROP TRIGGER IF EXISTS '+name).run();if(data.enabled)await db.prepare('CREATE TRIGGER '+name+' BEFORE INSERT ON '+table+' BEGIN SELECT qa_storage_unavailable(); END').run();return {faultEnabled:data.enabled,table,syntheticOnly:true};}
 if(action==='domain-reference'){if(!await stmt(db,'SELECT 1 FROM media WHERE id=? AND owner=?',data.mediaId,owner).first()||!['settings','history-revision'].includes(data.kind))throw Error('Invalid owned fixed reference');const id=uuid();let payload=JSON.stringify({fixtureMedia:'/api/media/'+data.mediaId});if(data.escapedSlash===true)payload=payload.replaceAll('/','\\/');if(data.kind==='settings')await stmt(db,'INSERT INTO settings VALUES(?,?)','qa_domain_reference_'+id,payload).run();else await stmt(db,'INSERT INTO revisions VALUES(?,?,?,?,?,?)',id,owner,'courses',uuid(),payload,stamp).run();return {referenceId:id,kind:data.kind,syntheticOnly:true};}
 if(action==='domain-draft-history'){if(!await stmt(db,'SELECT 1 FROM creator_works WHERE id=? AND owner_id=?',data.resourceId,owner).first()||!['review','post-copy','course-copy'].includes(data.kind))throw Error('Invalid owned draft');if(data.kind==='review')await stmt(db,'INSERT INTO creator_reviews VALUES(?,?,?,?,?,?,?)',uuid(),data.resourceId,'manual','rejected','Synthetic historical review',1,stamp).run();else if(data.kind==='post-copy')await stmt(db,'INSERT INTO posts VALUES(?,?,?,?,?,?,?,?,?)',data.resourceId,owner,'合成历史公开作品',spec.canaries.body,'','withdrawn','',stamp,stamp).run();else await stmt(db,'INSERT INTO contents VALUES(?,?,?,?,?,?)','courses',data.resourceId,JSON.stringify({title:'合成历史课程拷贝',creatorId:owner}),'archived',0,stamp).run();return {resourceId:data.resourceId,historyKind:data.kind,syntheticOnly:true};}
 if(action==='domain-attempt-dead-reference'){if(!await stmt(db,'SELECT 1 FROM privacy_media_tombstones WHERE media_id=? AND owner=?',data.mediaId,owner).first())throw Error('Existing owned tombstone required');const kind=data.kind||'settings';if(!['settings','history-revision'].includes(kind))throw Error('Unknown fixed reference kind');try{if(kind==='history-revision')await stmt(db,'INSERT INTO revisions VALUES(?,?,?,?,?,?)',uuid(),owner,'courses',uuid(),JSON.stringify({mediaUrl:'/api/media/'+data.mediaId}),stamp).run();else await stmt(db,'INSERT INTO settings VALUES(?,?)','qa_domain_dead_'+uuid(),JSON.stringify({mediaUrl:'/api/media/'+data.mediaId})).run();return {blocked:false,actualDatabaseTrigger:true,syntheticOnly:true};}catch(error:any){if(!String(error?.message||error).includes('privacy_deleted_media_reference'))throw error;return {blocked:true,actualDatabaseTrigger:true,syntheticOnly:true};}}
 if(action==='domain-attempt-dead-media'){if(!await stmt(db,'SELECT 1 FROM privacy_media_tombstones WHERE media_id=? AND owner=?',data.mediaId,owner).first())throw Error('Existing owned tombstone required');const row=await stmt(db,'SELECT object_key FROM privacy_object_deletions WHERE media_id=? AND owner=?',data.mediaId,owner).first();if(!row||row.object_key!=='media/'+data.mediaId)throw Error('Existing immutable managed object identity required');const attemptedMediaId=data.reuseKey===true?uuid():data.mediaId;try{await stmt(db,'INSERT INTO media VALUES(?,?,?,?,?,?)',attemptedMediaId,owner,'audio/wav','dead-identity-fixture.wav',row.object_key,stamp).run();return {blocked:false,actualDatabaseTrigger:true,syntheticOnly:true,objectKeyReuseApplicable:true};}catch(error:any){if(!String(error?.message||error).includes('privacy_deleted_media_identity'))throw error;return {blocked:true,actualDatabaseTrigger:true,syntheticOnly:true,objectKeyReuseApplicable:true,reusedKeyAttempt:data.reuseKey===true};}}
 if(action==='domain-snapshot'){
  if(!await stmt(db,'SELECT 1 FROM users WHERE id=?',owner).first())throw Error('Existing synthetic owner required');const rows:any={};for(const [domain,source] of Object.entries(spec.domains)){const cols=domain==='privateMedia'?'id,owner,mime,filename,created':'*';rows[domain]=await all(db,'SELECT '+cols+' FROM '+source.table+' WHERE '+source.owner+'=? ORDER BY '+source.id,owner);}
  for(const table of ['privacy_domain_jobs','privacy_domain_targets','privacy_domain_receipts','privacy_media_tombstones'])rows[table]=await all(db,'SELECT * FROM '+table+' WHERE owner=?',owner);
  rows.privacy_object_deletions=await all(db,'SELECT id,owner,receipt_id,media_id,status,attempts,lease_until,next_attempt,last_error,created,updated FROM privacy_object_deletions WHERE owner=?',owner);rows.tracking=await all(db,'SELECT * FROM privacy_retention_tracking WHERE owner=?',owner);
  if(await stmt(db,"SELECT 1 FROM sqlite_master WHERE type='table' AND name='qa_domain_unclassified'").first())rows.unclassified=await all(db,'SELECT * FROM qa_domain_unclassified WHERE owner=?',owner);
  rows.gateway=await all(db,'SELECT id,status,reserve_credits,charged_credits,quota_source,quota_period_id,has_output,output_chars,output_text,saved_conversation_id,usage,error_code,created,updated FROM ai_gateway_jobs WHERE owner=?',owner);rows.wallet=await all(db,'SELECT balance,reserved FROM ai_gateway_wallets WHERE owner=?',owner);
  const protectedFacts:any={};for(const [table,predicate] of [['commerce_orders','owner'],['commerce_order_items','order_id IN (SELECT id FROM commerce_orders WHERE owner=?)'],['commerce_payment_events','owner'],['commerce_entitlements','owner'],['digital_entitlement_grants','owner'],['digital_entitlement_uses','owner'],['membership_ai_periods','owner'],['membership_ai_allocations','owner'],['ai_gateway_quota_events','owner']])protectedFacts[table]=await all(db,'SELECT * FROM '+table+' WHERE '+(predicate.includes('?')?predicate:predicate+'=?'),owner);
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(protectedFacts)));rows.protectedFactsDigest=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('');return rows;
 }
 throw Error('Unknown fixed privacy domain QA action');
}
