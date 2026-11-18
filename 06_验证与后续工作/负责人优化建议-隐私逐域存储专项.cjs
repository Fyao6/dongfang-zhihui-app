'use strict';
// Four actual storage/restart checks. Only the owning launcher may provide the private controls.
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const {largeWav,pausedMedia}=require('./负责人优化建议-隐私逐域网络工具.cjs');
const digest=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));

module.exports=async function storageScenarios(ctx){
 const {h,api,a,f,key,check,person,clear,finishObjects,receiptSafe,inaccessible,sum,sourceCount,storageCounters}=ctx;
 const owner=p=>f.owner(p),context=p=>f.context(p);
 async function held(mediaId,method){
  for(let i=0;i<100;i++){const state=await f.bucket('stats');if(state.events.some(x=>x.mediaId===mediaId&&x.method===method&&x.event==='hold'))return state;await pause(50);}
  throw Error('Actual native bucket request did not enter the bounded hold');
 }
 const mediaEvents=async id=>(await f.bucket('stats')).events.filter(x=>x.mediaId===id);
 const proof=()=>h.report.storageProof??={backend:h.target==='cloud'?'cloud-r2':'sqlite-blob',nativeR2DeleteCount:0,nativeR2HeadCount:0,nativeR2HeadMissingCount:0,sqliteRowAndBlobLogicalRemoval:h.target==='python',secureWipe:false,r2Operated:h.target==='cloud',stages:[],nativeEpochs:[]};
 const stage=(name,counts)=>{proof().stages.push({name,...counts});};
 async function deniedRange(c,url){
  const response=await c.get(h.base+url,{headers:{Range:'bytes=0-63','If-None-Match':'*'}});
  h.report.traffic.push({method:'GET',path:url,status:response.status(),range:'bytes=0-63'});
  assert([401,403,404,410].includes(response.status()),'Range/cache conditions cannot bypass current authorization');
  assert(!String(response.headers()['content-type']||'').startsWith('audio/'));
  h.report.coverage.actualMediaRange=true;
 }

 await check('存储专项24：Cloud原生delete/HEAD故障有限五次与核验重试；SQLite真实BLOB事务失败原子回滚',async()=>{
  const p=await person('storefault');
  if(h.target==='python'){
   const media=await f.upload(p),job=(await f.preview(p,['privateMedia'])).job,before=await f.snapshot(p),requestId=key('blob_atomic_failure');
   await h.control({action:'domain-fault',enabled:true,table:'privacy_media_tombstones'});
   try{await api(context(p),'privacy/domains/jobs/'+job.id+'/apply',{requestId,confirmed:true,version:job.version},'POST',[500,503]);}
   finally{await h.control({action:'domain-fault',enabled:false,table:'privacy_media_tombstones'});}
   const failed=await f.snapshot(p);assert.equal(sourceCount(failed,'privateMedia'),1);assert.equal(failed.privacy_media_tombstones.length,0);assert.equal(failed.privacy_domain_receipts.length,0);assert.equal(failed.privacy_object_deletions.length,0);
   assert.equal(failed.privacy_domain_jobs.find(x=>x.id===job.id).version,job.version);assert(failed.privacy_domain_targets.filter(x=>x.job_id===job.id).every(x=>x.processed===0));assert.equal(failed.protectedFactsDigest,before.protectedFactsDigest);
   assert.deepEqual((await h.media(context(p),media.url)).bytes,media.bytes,'A failed logical-delete transaction retains the actual BLOB bytes');
   const applied=await f.apply(p,job,requestId);receiptSafe(applied.receipt);assert.equal(applied.receipt.localDatabase.counts.privateMedia,1);assert.equal(applied.receipt.objects.applicable,false);assert.equal((await f.snapshot(p)).privacy_object_deletions.length,0);await inaccessible(context(p),media.url);await deniedRange(context(p),media.url);
   stage('sqlite-blob-tombstone-fault-rollback',{deleteCount:0,headCount:0,headMissingCount:0});
   return;
  }
  const exhausted=await f.upload(p),deleted=await clear(p,['privateMedia']);assert.equal(deleted.job.pendingObjects,1);
  await f.bucket('fault',{mediaId:exhausted.id,method:'delete',when:'before',kind:'throw',remaining:5});
  let last;
  for(let attempt=1;attempt<=5;attempt++){
   const response=await f.objects(p,1);assert.equal(response.processed,1);last=response.items[0];assert.equal(last.mediaId,exhausted.id);assert.equal(last.attempts,attempt);assert.equal(last.status,attempt===5?'manual_review':'retry');assert((attempt===5?['storage_delete_failed','retry_exhausted']:['storage_delete_failed']).includes(last.lastError));
   assert.equal((await f.bucket('probe',{mediaId:exhausted.id})).exists,true,'Injected pre-delete failure cannot manufacture missing object evidence');
   if(attempt<5){assert(last.nextAttempt>0);await f.clock(last.nextAttempt+1);}
  }
  await f.retry(last.id,409);assert.equal((await f.objects(p,1)).processed,0);assert.equal((await f.snapshot(p)).privacy_object_deletions.find(x=>x.id===last.id).attempts,5);
  const failedCounters=storageCounters(await mediaEvents(exhausted.id));assert.deepEqual(failedCounters,{deleteCount:0,headCount:0,headMissingCount:0});stage('injected-pre-delete-failure-five-attempts',failedCounters);
  await f.bucket('clear');
  const verify=await f.upload(p),verifyDeletion=await clear(p,['privateMedia']);await f.bucket('fault',{mediaId:verify.id,method:'head',when:'before',kind:'throw',remaining:1});
  const failed=(await f.objects(p,1)).items[0];assert.equal(failed.mediaId,verify.id);assert.equal(failed.attempts,1);assert.equal(failed.status,'retry');assert.equal(failed.lastError,'storage_verification_failed');assert.equal((await f.bucket('probe',{mediaId:verify.id})).exists,false,'Native delete completed, while product HEAD was injected to fail');
  const beforeRetry=storageCounters(await mediaEvents(verify.id));assert.equal(beforeRetry.deleteCount,1);assert.equal(beforeRetry.headMissingCount,0);
  await f.bucket('clear');const queued=(await f.retry(failed.id)).item;assert.equal(queued.attempts,1);const completed=(await f.objects(p,1)).items[0];assert.equal(completed.id,failed.id);assert.equal(completed.status,'completed');assert.equal(completed.attempts,2);
  const record=(await f.job(p,verifyDeletion.job.id)).receipts;record.forEach(receiptSafe);assert.equal(record[0].objects.verified,1);assert.equal(record[0].objects.pending,0);assert.equal(record[0].objects.retry,0);
  const counters=storageCounters(await mediaEvents(verify.id));assert(counters.deleteCount>=beforeRetry.deleteCount);assert(counters.headCount>0&&counters.headMissingCount>0);stage('native-delete-head-verification-retry',counters);
 });

 await check('存储专项25：真实PID重启保同DB/state及原批次，Cloud未过期并发租约不重领且过期只恢复原任务',async()=>{
  const p=await person('storerestart');await f.seed(p,'service',{count:101});const preview=(await f.preview(p,['serviceRequestContent'])).job,first=await f.apply(p,preview);assert.equal(first.receipt.localDatabase.counts.serviceRequestContent,100);assert.equal(first.job.pending,1);
  const media=await f.upload(p),erased=await clear(p,['privateMedia']);let interrupted,lease;
  try{
   if(h.target==='cloud'){
    await f.bucket('fault',{mediaId:media.id,method:'delete',when:'before',kind:'hold',remaining:1});
    interrupted=context(p).post(h.base+'/api/privacy/domains/objects/process',{data:{limit:1},timeout:60000}).then(r=>({status:r.status()}),()=>({interrupted:true}));
    await held(media.id,'delete');const competing=await f.objects(p,1);assert.equal(competing.processed,0);
    lease=(await f.snapshot(p)).privacy_object_deletions.find(x=>x.media_id===media.id);assert.equal(lease.status,'processing');assert.equal(lease.attempts,1);assert(lease.lease_until>0);assert.equal(storageCounters(await mediaEvents(media.id)).deleteCount,0);
   }else{assert.equal(erased.receipt.objects.applicable,false);assert.equal((await f.snapshot(p)).privacy_object_deletions.length,0);}
   if(h.target==='cloud')(proof().nativeEpochs??=[]).push({name:'before-real-restart',...storageCounters((await f.bucket('stats')).events)});
   const restarted=await h.restart();assert.notEqual(restarted.beforePid,restarted.afterPid);assert.equal(restarted.sameOwnedState,true);assert.equal(restarted.base,h.base);if(interrupted)await interrupted;
   const recovered=await f.job(p,first.job.id);assert.equal(recovered.job.id,first.job.id);assert.equal(recovered.job.version,first.job.version);assert.equal(recovered.job.pending,1);assert(recovered.receipts.some(x=>x.id===first.receipt.id));await inaccessible(context(p),media.url);
   const requests=[key('restart_batch_a'),key('restart_batch_b')],responses=await Promise.all(requests.map(requestId=>api(context(p),'privacy/domains/jobs/'+recovered.job.id+'/apply',{requestId,confirmed:true,version:recovered.job.version},'POST',null)));
   assert.deepEqual(responses.map(x=>x.status).sort(),[200,409]);const winner=responses.find(x=>x.status===200).data;receiptSafe(winner.receipt);assert.equal(winner.receipt.localDatabase.counts.serviceRequestContent,1);assert.equal(winner.job.pending,0);const rows=(await f.snapshot(p)).serviceRequestContent;assert.equal(rows.length,101);assert(rows.every(x=>x.body===''&&x.preferred_date===''));
   if(h.target==='cloud'){
    const persisted=(await f.snapshot(p)).privacy_object_deletions.find(x=>x.id===lease.id);assert.equal(persisted.status,'processing');assert.equal(persisted.attempts,1);assert.equal(persisted.lease_until,lease.lease_until);
    await f.clock(lease.lease_until+1);const consumed=await Promise.all([f.objects(p,1),f.objects(p,1)]);assert.equal(sum(consumed.map(x=>x.processed)),1);const done=(await f.snapshot(p)).privacy_object_deletions.find(x=>x.id===lease.id);assert.equal(done.status,'completed');assert.equal(done.attempts,2);
    const counters=storageCounters(await mediaEvents(media.id));assert.deepEqual(counters,{deleteCount:1,headCount:1,headMissingCount:1});stage('real-restart-expired-lease-recovery',counters);
   }
  }finally{if(h.target==='cloud')await f.bucket('clear');if(interrupted)await interrupted;}
 });

 await check('存储专项26：GET和Range在途最终授权拒墓碑；Python已授权慢收流在网络锁外且不阻本人的真实数据库清理',async()=>{
  const p=await person('storeread');
  if(h.target==='cloud'){
   for(const range of [null,'bytes=0-63']){
    const media=await f.upload(p);await f.bucket('fault',{mediaId:media.id,method:'get',when:'after',kind:'hold',remaining:1});
    const pending=context(p).get(h.base+media.url,{...(range?{headers:{Range:range}}:{}),timeout:45000}).then(async response=>({status:response.status(),type:response.headers()['content-type'],bytes:await response.body()}));pending.catch(()=>{});
    try{await held(media.id,'get');const erased=await clear(p,['privateMedia']);assert.equal(erased.receipt.localDatabase.counts.privateMedia,1);await f.bucket('release',{mediaId:media.id});const result=await pending;assert([403,404,410].includes(result.status));assert(!String(result.type).startsWith('audio/'));assert.notDeepEqual(result.bytes,media.bytes);await inaccessible(context(p),media.url);await deniedRange(context(p),media.url);await finishObjects(p);}
    finally{await f.bucket('release',{mediaId:media.id});await pending.catch(()=>{});}
   }
   (h.report.storageReadBoundary??=[]).push({backend:'cloud-r2',nativeGetHeldBeforeFinalAuthorization:true,ordinaryGetAndRangeDenied:true,alreadyTransmittedBytesRetracted:false});
   return;
  }
  const media=await f.upload(p,{bytes:largeWav(),name:'owned-slow-receiver.wav'});await f.seed(p);const job=(await f.preview(p,['serviceRequestContent'])).job;let slow;
  try{
   slow=await pausedMedia(h,context(p),media.url);assert.equal(slow.status,200);assert.equal(slow.contentLength,media.bytes.length);assert.equal(slow.pausedAfterHeaders,true);assert.equal(slow.finished(),false);
   const start=Date.now(),applied=await f.apply(p,job),elapsed=Date.now()-start;receiptSafe(applied.receipt);assert.equal(applied.receipt.localDatabase.counts.serviceRequestContent,1);assert(elapsed<12000,'A paused network receiver must not hold the SQLite writer lock through its 15-second timeout');
   const erased=await clear(p,['privateMedia']);assert.equal(erased.receipt.localDatabase.counts.privateMedia,1);assert.equal(erased.receipt.objects.applicable,false);await inaccessible(context(p),media.url);await deniedRange(context(p),media.url);
   slow.resume();const completion=await slow.completion;assert.equal(completion.bytes,media.bytes.length);assert.equal(completion.sha256,digest(media.bytes));
   (h.report.storageReadBoundary??=[]).push({backend:'sqlite-blob',actualPausedTcpReceiver:true,writeWhilePausedMs:elapsed,previouslyAuthorizedSnapshotContinued:true,responseBytes:completion.bytes,sha256:completion.sha256,subsequentGetAndRangeDenied:true,alreadyTransmittedBytesRetracted:false});
  }finally{slow?.close();}
 });

 await check('存储专项27：新引用与历史恢复材料、原媒体ID/key复用由最终DB守卫阻断，未知表Unicode裸ID正反检查不越权',async()=>{
  const p=await person('storeguard'),first=await f.upload(p),referenced=await f.upload(p);await h.control({action:'domain-create-unknown-table'});const inventory=await f.inventory(p);assert(inventory.unclassifiedOwnerTables.includes('qa_domain_unclassified'));
  const unrelated=await h.control({action:'domain-unknown-unrelated',owner:owner(p)});assert.equal(unrelated.blocked,false);const live=await h.control({action:'domain-unknown-reference',owner:owner(p),mediaId:referenced.id});assert.equal(live.blocked,false);assert.equal(live.jsonUnicodeBareMediaId,true);assert.equal(live.actualDatabaseTrigger,true);
  const planned=(await f.preview(p,['privateMedia'])).job;assert.equal(planned.planned,1);const newReference=await h.control({action:'domain-unknown-reference',owner:owner(p),mediaId:first.id});assert.equal(newReference.blocked,false);const skipped=await f.apply(p,planned);receiptSafe(skipped.receipt);assert.equal(skipped.receipt.localDatabase.counts.privateMedia,0);assert.equal(skipped.receipt.localDatabase.skippedReferenced,1);assert.equal(sourceCount(await f.snapshot(p),'privateMedia'),2);assert.equal((await f.preview(p,['privateMedia'])).job.planned,0);
  const dead=await f.upload(p),erased=await clear(p,['privateMedia']);assert.equal(erased.receipt.localDatabase.counts.privateMedia,1);await finishObjects(p);await inaccessible(context(p),dead.url);
  for(const data of [{action:'domain-attempt-dead-reference'},{action:'domain-attempt-dead-reference',kind:'history-revision'},{action:'domain-attempt-dead-unknown'},{action:'domain-attempt-dead-media'},...(h.target==='cloud'?[{action:'domain-attempt-dead-media',reuseKey:true}]:[])]){
   const result=await h.control({...data,owner:owner(p),mediaId:dead.id});assert.equal(result.blocked,true);assert.equal(result.actualDatabaseTrigger,true);if(data.action==='domain-attempt-dead-unknown')assert.equal(result.jsonUnicodeBareMediaId,true);
  }
  const after=await f.snapshot(p);assert.equal(sourceCount(after,'privateMedia'),2);assert(!after.privateMedia.some(x=>x.id===dead.id));assert.equal(after.privacy_media_tombstones.filter(x=>x.media_id===dead.id).length,1);await deniedRange(context(p),dead.url);
  const listing=await f.records(p,'privateMedia');assert(listing.items.every(x=>x.eligibility===false&&x.blockedReasons.includes('referenced')));f.safe(listing);
 });
};
