'use strict';
// Actual owner-selected legacy HTTP. Synthetic records never become authoritative draws.
const assert=require('node:assert/strict'),crypto=require('node:crypto');
module.exports=async function({h,a,f,api,check,key}){
 let sequence=0;const K=s=>key(s+'_'+(++sequence)),C=f.context,O=f.owner;
 const legacyTables=['card_history_migration_jobs','card_history_migration_targets','card_legacy_archives','card_history_migration_receipts','card_history_migration_operations','card_history_migration_guards'];
 const safeKeys=['cardLegacyMigrationJobs','cardLegacyMigrationTargets','cardLegacyArchives','cardLegacyMigrationReceipts','cardLegacyMigrationOperations'];
 const moneyKeys=['aiGatewayWallet','aiGatewayGrants','aiGatewayRequests','aiGatewayQuotaEvents','aiGatewayAttempts','membershipAIPeriods','membershipAIAllocations','membershipAIEvents','orders','payments'];
 const digest=v=>f.sha(f.canonical(v)),own=(s,p)=>Object.fromEntries(Object.entries(s).map(([t,rows])=>[t,rows.filter(r=>r.owner===O(p))]));
 async function complete(p,records){const preview=await f.migrationPreview(p,records);let current=preview;const receipts=[];while(current.summary.remaining){current=await f.migrationApply(p,current.job);receipts.push(current.receipt);assert(receipts.length<=10);}return{preview,...current,receipts};}
 async function allTargets(p,job){let d=await f.migrationDetail(p,job),items=[...d.targets],next=d.next;const seen=new Set();while(next){assert(!seen.has(next));seen.add(next);d=await f.migrationDetail(p,job,{before:next});assert(d.targets.length<=50);items.push(...d.targets);next=d.next;}return{items,pages:seen.size+1,cursors:[...seen]};}
 async function allReceipts(p,job){let d=await f.migrationDetail(p,job),items=[...d.receipts],next=d.receiptsNext;const seen=new Set();while(next){assert(!seen.has(next));seen.add(next);d=await f.migrationDetail(p,job,{receiptsBefore:next});assert(d.receipts.length<=50);items.push(...d.receipts);next=d.receiptsNext;}return{items,pages:seen.size+1,cursors:[...seen]};}
 async function close(p){const requestId=K('close'),nonce=crypto.randomBytes(32).toString('hex'),prepared=(await api(C(p),'account-closure/prepare',{requestId,nonce,password:(p.credential||p.credentials).password})).data,proof={requestId,nonce,challengeId:prepared.challengeId,confirmed:true,renewalAcknowledged:true};return{proof,response:(await api(C(p),'account-closure/confirm',proof)).data};}
 async function exported(p){return(await api(C(p),'privacy/export')).data;}
 function ownerFacts(snapshot,p){return own(snapshot,p);}

 await check('25 legacy明确选raw文件、严格三字段及未知事实，不按当前卡补造',async()=>{
  const p=await h.register('mraw'),records=f.legacyRecords(2),sourceReference='SYNTHETIC_EXPLICIT_FILE_'+K('source'),file={schema:1,sourceReference,records},raw=Buffer.from(JSON.stringify(file,null,2)),before=await f.cardFacts(p),request=K('raw');
  const d=await f.migrationPreview(p,file,{key:request,raw});assert.equal(d.job.sourceSha256,f.sha(raw));assert.equal(d.job.canonicalSha256,f.sha(f.canonical(file)));assert.deepEqual(d.targets.map(t=>t.record),records);assert(d.targets.every(t=>t.status==='pending'));assert.equal(d.authoritative,false);assert.equal(d.contentReviewed,false);assert.equal(d.summary.added,0);
  for(const r of [{...records[0],text:'Do not infer original text'},{...records[0],timezone:'Etc/GMT-8'},{...records[0],owner:O(p)},{...records[0],date:'2025-02-29'},{...records[0],drawnAt:true}])await f.migrationPreview(p,[r],{expected:400});
  await f.migrationPreview(p,{...file,deckVersion:'untrusted'},{expected:400});await f.migrationPreview(p,records,{raw:Buffer.from('{"schema":1,"schem\\u0061":1}'),expected:400});await f.migrationPreview(p,records,{raw:Buffer.concat([Buffer.from([0xef,0xbb,0xbf]),raw]),expected:400});
  await f.migrationPreview(p,file,{key:request,raw:Buffer.concat([raw,Buffer.from(' ')]),expected:409});const replay=await f.migrationPreview(p,file,{key:request,raw});assert.equal(replay.job.id,d.job.id);assert.deepEqual(await f.cardFacts(p),before);
  const applied=await f.migrationApply(p,d.job),archives=await f.archives(p);assert.equal(applied.summary.added,2);for(const item of archives.items){assert.equal(item.authoritative,false);assert.equal(item.contentReviewed,false);assert.equal(item.sourceType,'legacy_local_example');assert.deepEqual(item.factsMissing,['deckVersion','rulesVersion','timezone','originalCardText']);assert(!('snapshot' in item));assert(!('rulesVersion' in item.record));}
  return{actualRawBytes:raw.length,sourceDigestVerified:true,selectedSyntheticRecords:2,professionalContentInferred:false};
 });

 await check('26 preview不写归档或quota，文件内及跨job去重与owner隔离真实统计',async()=>{
  const p=await h.register('mdedup'),other=await h.register('mdedother'),record=f.legacyRecords(1)[0],before=await f.cardFacts(p),d=await f.migrationPreview(p,[record,record]);assert.equal((await f.archives(p)).items.length,0);assert.deepEqual(await f.cardFacts(p),before);assert.equal(d.summary.added,0);assert.equal(d.summary.remaining,2);
  const result=await f.migrationApply(p,d.job);assert.equal(result.receipt.counts.selected,2);assert.equal(result.receipt.counts.added,1);assert.equal(result.receipt.counts.duplicate,1);assert.equal((await f.archives(p)).items.length,1);
  const again=await f.migrationPreview(p,[record],{sourceReference:'A different selected file; same original three fields'}),duplicate=await f.migrationApply(p,again.job);assert.equal(duplicate.receipt.counts.added,0);assert.equal(duplicate.receipt.counts.duplicate,1);assert.equal((await f.archives(p)).items.length,1);
  const foreign=await complete(other,[record]);assert.equal(foreign.summary.added,1);assert.notEqual((await f.archives(other)).items[0].id,(await f.archives(p)).items[0].id);await f.migrationDetail(other,d.job,{expected:404});await f.migrationApply(other,d.job,{expected:404});await api(a.anonymous,'cards/legacy-migrations',undefined,'GET',401);
  assert.deepEqual(await f.cardFacts(p),before);return{fileTargets:2,firstAdded:1,inFileDuplicate:1,crossJobDuplicate:1,otherOwnerSeparatelyAdded:1};
 });

 await check('27 101目标100加1续批、精确回执幂等与并发CAS只一批提交',async()=>{
  const p=await h.register('mbatch'),d=await f.migrationPreview(p,f.legacyRecords(101)),request=K('batch'),first=await f.migrationApply(p,d.job,{key:request});assert.equal(first.receipt.counts.selected,100);assert.equal(first.summary.added,100);assert.equal(first.summary.remaining,1);assert.equal(first.job.version,d.job.version+1);
  assert.deepEqual(await f.migrationApply(p,d.job,{key:request}),first);await f.migrationApply(p,d.job,{key:request,version:first.job.version,expected:409});await f.migrationApply(p,d.job,{confirmed:false,expected:400});
  const route='cards/legacy-migrations/'+d.job.id+'/apply',bodies=[0,1].map(i=>({requestId:K('race'+i),confirmed:true,version:first.job.version}));const ongoing=bodies.map(body=>api(C(p),route,body,'POST',null));for(const promise of ongoing)promise.catch(()=>{});const raced=await Promise.all(ongoing);assert.deepEqual(raced.map(r=>r.status).sort(),[200,409]);const winner=raced.find(r=>r.status===200).data;assert.equal(winner.receipt.counts.selected,1);assert.equal(winner.summary.added,101);assert.equal(winner.summary.remaining,0);
  const detail=await f.migrationDetail(p,d.job),all=await allTargets(p,d.job);assert.equal(detail.job.version,3);assert.equal(detail.receipts.length,2);assert.equal(all.items.filter(t=>t.status==='added').length,101);assert.equal((await f.allPages(p,'cards/legacy-archives')).items.length,101);
  return{firstSelected:100,secondSelected:1,actualCommittedReceipts:2,concurrentStatuses:[200,409],sourceRowsSeeded:0};
 });

 await check('28 持久job列表和实际owned进程重开后按原版本续办，不重新preview',async()=>{
  const p=await h.register('mrestart'),d=await f.migrationPreview(p,f.legacyRecords(101)),first=await f.migrationApply(p,d.job),before=await f.migrationDetail(p,d.job);assert.equal(first.summary.remaining,1);assert((await f.allPages(p,'cards/legacy-migrations')).items.some(j=>j.id===d.job.id));assert.equal(typeof h.restart,'function');
  const restarted=await h.restart();assert.equal(restarted.restarted,true);assert(Number.isInteger(restarted.beforePid));assert(Number.isInteger(restarted.afterPid));assert.notEqual(restarted.beforePid,restarted.afterPid);assert.equal(restarted.base,h.base);
  const reopened=await f.migrationDetail(p,d.job);assert.deepEqual(reopened,before);const second=await f.migrationApply(p,reopened.job);assert.equal(second.receipt.counts.selected,1);assert.equal(second.summary.added,101);assert.equal(second.summary.remaining,0);
  return{actualChildRestarted:true,beforePid:restarted.beforePid,afterPid:restarted.afterPid,sameOwnedState:true,oldJobResumed:true};
 });

 await check('29 合法note和favorite修订保留新值，旧revision或他人编辑不覆盖',async()=>{
  const p=await h.register('medit'),other=await h.register('meditother'),done=await complete(p,f.legacyRecords(3)),item=(await f.archives(p)).items[0],note='SYNTHETIC_OWNER_NOTE_'+K('personal');const edited=await f.editArchive(p,item,{note,favorite:true});assert.equal(edited.item.revision,1);assert.equal(edited.item.note,note);assert.equal(edited.item.favorite,true);
  await f.editArchive(p,item,{note:'stale revision'}, {expected:409});await f.editArchive(other,edited.item,{note:'foreign'}, {expected:404});await f.editArchive(p,edited.item,{favorite:1},{expected:400});await f.editArchive(p,edited.item,{note:'x'.repeat(2001)},{expected:400});
  const undo=await f.migrationUndo(p,done.job);assert.equal(undo.receipt.counts.skippedChanged,1);assert.equal(undo.receipt.counts.undone,2);const remaining=(await f.archives(p)).items;assert.equal(remaining.length,1);assert.deepEqual(remaining[0],edited.item);
  return{laterRevision:1,undoSkippedChanged:1,actuallyUndone:2,personalEditPreserved:true};
 });

 await check('30 undo只删本job新增且未引用原件，重复与另一job归档不被误删',async()=>{
  const p=await h.register('morigin'),records=f.legacyRecords(3),original=await complete(p,records),other=await complete(p,[records[0],{...records[0],cardId:'separate-new-origin'}]),facts=await f.cardFacts(p),all=(await f.archives(p)).items,kept=new Set([all.find(r=>r.record.cardId===records[0].cardId).id,all.find(r=>r.record.cardId==='separate-new-origin').id]);assert.equal(other.summary.added,1);assert.equal(other.summary.duplicate,1);
  const undo=await f.migrationUndo(p,original.job);assert.equal(undo.receipt.counts.protected,1);assert.equal(undo.receipt.counts.undone,2);const after=(await f.archives(p)).items;assert.equal(after.length,2);assert.deepEqual(new Set(after.map(r=>r.id)),kept);assert.deepEqual(await f.cardFacts(p),facts);
  return{actuallyUndone:2,protectedByLaterJobReference:1,separateJobOriginalPreserved:true,authoritativeCardFactsUnchanged:true};
 });

 await check('31 201目标撤销100加100加1，后改冲突和每批回执精确重放',async()=>{
  const p=await h.register('mundo'),done=await complete(p,f.legacyRecords(201)),item=(await f.archives(p)).items[0];await f.editArchive(p,item,{favorite:true});let current=done,undone=0,changed=0;const selected=[];
  for(let i=0;i<3;i++){const request=K('undo_batch'),before=current.job,result=await f.migrationUndo(p,before,{key:request});selected.push(result.receipt.counts.selected);undone+=result.receipt.counts.undone;changed+=result.receipt.counts.skippedChanged;assert.deepEqual(await f.migrationUndo(p,before,{key:request}),result);await f.migrationUndo(p,before,{expected:409});current=result;}
  assert.deepEqual(selected,[100,100,1]);assert.equal(undone,200);assert.equal(changed,1);assert.equal(current.job.status,'undone');assert.equal(current.summary.undoRemaining,0);assert.equal(current.summary.added,201);assert.equal((await f.archives(p)).items.length,1);await f.migrationApply(p,current.job,{expected:409});const targets=await allTargets(p,current.job);assert.equal(targets.items.filter(t=>t.status==='undone').length,200);assert.equal(targets.items.filter(t=>t.status==='skipped_changed').length,1);
  return{actualSelected:selected,actualUndone:undone,actualChanged:changed,historicalAddedCounter:201,wholeDatabaseRestore:false};
 });

 await check('32 preview和apply及note和undo全程不改draw请求、额度、时区或清理epoch',async()=>{
  const p=await h.register('mfacts'),before=await f.cardFacts(p),otherBefore=await f.cardFacts({id:a.second.id}),d=await f.migrationPreview(p,f.legacyRecords(4));assert.deepEqual(await f.cardFacts(p),before);const applied=await f.migrationApply(p,d.job);assert.deepEqual(await f.cardFacts(p),before);const archived=(await f.archives(p)).items[0];await f.editArchive(p,archived,{note:'later note'});assert.deepEqual(await f.cardFacts(p),before);await f.migrationUndo(p,applied.job);assert.deepEqual(await f.cardFacts(p),before);assert.deepEqual(await f.cardFacts({id:a.second.id}),otherBefore);
  const rows=await f.snapshot(legacyTables);assert.equal(rows.card_history_migration_guards.length,0);return{actualOldCardTablesCompared:f.cardTables,epochWrittenByMigration:false,quotaGranted:false,timezoneInferred:false,temporaryGuardRows:0};
 });

 await check('33 真实records清理使冻结epoch失效，held最终批不得复活归档或源正文',async()=>{
  const p=await h.register('mclear'),other=await h.register('mclearother'),canary='LEGACY_PRIVATE_CLEAR_'+K('canary'),kept=await complete(other,[{...f.legacyRecords(1)[0],cardId:'KEPT_OTHER_OWNER'}]),d=await f.migrationPreview(p,[{...f.legacyRecords(1)[0],cardId:canary}]),beforeOther=ownerFacts(await f.snapshot(legacyTables),other);
  await f.barrier('cm','arm',{stage:'before-final'});const pending=api(C(p),'cards/legacy-migrations/'+d.job.id+'/apply',{requestId:K('held_clear'),version:d.job.version,confirmed:true},'POST',null);pending.catch(()=>{});
  try{await f.waitEntered('cm');const cleared=(await api(C(p),'privacy/requests',{requestId:K('records_clear'),kind:'delete-records'})).data.item;assert(cleared.details.local.deletedCounts.cardLegacy);}
  finally{await f.barrier('cm','release');}
  const response=await pending;assert.equal(response.status,h.target==='python'?410:409);await f.migrationApply(p,d.job,{expected:410});await f.migrationDetail(p,d.job,{expected:410});assert.equal((await f.archives(p)).items.length,0);
  const ownExport=await exported(p);assert(!JSON.stringify(ownExport.serverData).includes(canary));const rows=ownerFacts(await f.snapshot(legacyTables),p);assert(rows.card_history_migration_jobs.every(j=>j.status==='erased'&&j.data==='{}'&&j.source_reference===''));assert.equal(rows.card_history_migration_targets.length,0);assert.equal(rows.card_legacy_archives.length,0);assert.deepEqual(ownerFacts(await f.snapshot(legacyTables),other),beforeOther);assert((await f.archives(other)).items.some(r=>r.record.cardId==='KEPT_OTHER_OWNER'));
  return{actualConcurrentClear:true,heldFinalStatus:response.status,noLateArchive:true,otherOwnerPreserved:true,secureWipe:false};
 });

 await check('34 真实闭户挡在途final和旧session；管理员不能代另一owner归档',async()=>{
  const p=await h.register('mclosed'),other=await h.register('mclosedother'),d=await f.migrationPreview(p,f.legacyRecords(2)),keep=await complete(other,[{...f.legacyRecords(1)[0],cardId:'KEPT_AFTER_OTHER_CLOSURE'}]),beforeOther=ownerFacts(await f.snapshot(legacyTables),other);await f.migrationApply(a.admin,d.job,{expected:404});
  await f.barrier('cm','arm',{stage:'before-final'});const pending=api(C(p),'cards/legacy-migrations/'+d.job.id+'/apply',{requestId:K('held_closed'),version:d.job.version,confirmed:true},'POST',null);pending.catch(()=>{});let closed;
  try{await f.waitEntered('cm');closed=await close(p);assert.equal(closed.response.receipt.accountClosed,true);}finally{await f.barrier('cm','release');}
  const response=await pending;assert.equal(response.status,401);await api(C(p),'cards/legacy-migrations',undefined,'GET',401);await f.migrationApply(p,d.job,{expected:401});const rows=ownerFacts(await f.snapshot(legacyTables),p);assert.equal(rows.card_legacy_archives.length,0);assert.equal(rows.card_history_migration_targets.length,0);assert(rows.card_history_migration_jobs.every(j=>j.erased_at>0&&j.data==='{}'));assert.deepEqual(ownerFacts(await f.snapshot(legacyTables),other),beforeOther);
  const beforeReplay=digest(rows);assert.equal((await api(C(p),'account-closure/confirm',closed.proof)).data.receipt.accountClosed,true);assert.equal(digest(ownerFacts(await f.snapshot(legacyTables),p)),beforeReplay);
  return{actualClosure:true,heldFinalStatus:401,adminDelegationDenied:404,otherOwnerPreserved:true,nonceReplayReadOnly:true};
 });

 await check('35 六表显式本人盘点和安全导出，实际清理正文保资金及公司draft',async()=>{
  const p=await f.administrator('mexport'),other=await h.register('mexpother'),canary='PRIVATE_LEGACY_BODY_'+K('export'),x=await complete(p,[{...f.legacyRecords(1)[0],cardId:canary}]),foreign=await complete(other,[{...f.legacyRecords(1)[0],cardId:'FOREIGN_PRIVATE_LEGACY'}]),archive=(await f.archives(p)).items[0];await f.editArchive(p,archive,{note:canary});
  const deck=f.payload([f.card('company_retained')]),draftPreview=await f.importPreview(p,deck),draft=await f.importApply(p,draftPreview.job);assert.equal(draft.item.status,'draft');const companyId=draft.item.id,companyBefore=digest((await f.snapshot(['card_deck_versions'])).card_deck_versions.find(r=>r.id===companyId));
  await api(a.admin,'admin/ai-gateway/grants',{requestId:K('financial_grant'),accountId:O(p),credits:17,environment:'local-test'});const inventory=(await api(C(p),'privacy/domains')).data;for(const table of legacyTables)assert(!inventory.unclassifiedOwnerTables.includes(table),table+' is explicitly personal');assert(inventory.retained.some(r=>r.id==='privacyAndSourceAudits'&&r.recordCount>0));
  const ownExport=await exported(p),data=Object.fromEntries(safeKeys.map(k=>{assert(Array.isArray(ownExport.serverData[k]));return[k,ownExport.serverData[k]];})),text=JSON.stringify(data);assert(text.includes(canary));assert(!text.includes('FOREIGN_PRIVATE_LEGACY'));assert(!/"(?:session_hash|sessionHash|password|lease_token|token_hash)"/.test(text));const money=digest(Object.fromEntries(moneyKeys.map(k=>[k,ownExport.serverData[k]||[]]))),beforeOther=ownerFacts(await f.snapshot(legacyTables),other);
  const erased=(await api(C(p),'privacy/requests',{requestId:K('clear'),kind:'delete-records'})).data.item,proof=erased.details.local.deletedCounts.cardLegacy;assert.equal(proof.secureWipe,false);assert.equal(proof.retentionDays,null);assert(proof.deletedCounts.card_legacy_archives>=1);const after=await exported(p);assert(!JSON.stringify(Object.fromEntries(safeKeys.map(k=>[k,after.serverData[k]]))).includes(canary));assert.equal(digest(Object.fromEntries(moneyKeys.map(k=>[k,after.serverData[k]||[]]))),money);assert.deepEqual(ownerFacts(await f.snapshot(legacyTables),other),beforeOther);assert.equal(digest((await f.snapshot(['card_deck_versions'])).card_deck_versions.find(r=>r.id===companyId)),companyBefore);
  return{explicitKnownOwnerTables:6,safeExportSections:safeKeys,actualWalletCreditsGranted:17,sourceAndNoteErased:true,companyDraftPreserved:true,retentionDays:null,secureWipe:false};
 });

 await check('36 jobs和targets及receipts和archives超过50完整分页，游标owner和kind绑定',async()=>{
  const p=await h.register('mpages'),other=await h.register('mpageother'),d=await f.migrationPreview(p,f.legacyRecords(105)),done=await f.migrationApply(p,d.job),done2=await f.migrationApply(p,done.job);let current=done2;
  // Each additional receipt is a real confirmed zero-remaining operation, never fixture-seeded.
  for(let i=0;i<49;i++){const next=await f.migrationApply(p,current.job);assert.equal(next.receipt.counts.selected,0);assert.equal(next.receipt.counts.added,0);assert.equal(next.summary.added,105);current=next;}
  for(let i=0;i<50;i++)await f.migrationPreview(p,[{...f.legacyRecords(1)[0],cardId:'PAGE_JOB_'+i}]);
  const jobs=await f.allPages(p,'cards/legacy-migrations'),archives=await f.allPages(p,'cards/legacy-archives'),targets=await allTargets(p,d.job),receipts=await allReceipts(p,d.job);assert.equal(jobs.items.length,51);assert.equal(jobs.pages,2);assert.equal(archives.items.length,105);assert.equal(archives.pages,3);assert.equal(targets.items.length,105);assert.equal(targets.pages,3);assert.equal(receipts.items.length,51);assert.equal(receipts.pages,2);for(const rows of [jobs.items,archives.items,targets.items,receipts.items])assert.equal(new Set(rows.map(r=>r.id)).size,rows.length);
  const first=await f.migrationDetail(p,d.job);assert(first.next&&first.receiptsNext);await f.migrationDetail(p,d.job,{before:first.receiptsNext,expected:400});await f.migrationDetail(p,d.job,{receiptsBefore:first.next,expected:400});await f.archives(other,{before:archives.cursors[0],expected:400});await api(C(p),'cards/legacy-migrations?before='+encodeURIComponent(archives.cursors[0]),undefined,'GET',400);await f.migrationDetail(other,d.job,{before:first.next,expected:404});
  return{actualJobs:51,actualArchives:105,actualTargets:105,actualReceipts:51,pageLimit:50,fixtureSeededRows:0,zeroRemainingOperationsRecorded:49};
 });
};
