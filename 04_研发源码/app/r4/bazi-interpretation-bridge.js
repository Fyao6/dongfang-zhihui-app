// Local provenance for actual new Ba Zi AI replies. Persistence uses the existing, separately authorized personal store.
// Load after bazi-result-version-release.js and all pxAsk wrappers. Never reassign the const API client.
(function(root){
 'use strict';
 if(root.BaziInterpretationBridge)return;
 const version=root.BaziResultVersion,plans=new WeakMap(),bindings=new WeakMap(),restores=new WeakMap(),frames=new Map();
 let serial=0;
 const copy=value=>JSON.parse(JSON.stringify(value)),canonical=value=>version.canonical(value);
 const messageKey=message=>canonical({id:message.id,gatewayJobId:message.gatewayJobId||null,text:message.text,privacy:message.privacy});
 const release=()=>root.BaziVersionUI?.manifest||root.BAZI_RELEASE_MANIFEST;
 const label=(en,zh,hant,bo)=>lcText(en,zh,hant,bo);
 function sampleMode(){return root.BaziSampleBridge?.isActive?.()===true;}
 function actorCurrent(actor){return !sampleMode()&& !!actor?.scope&&psCurrent(actor);}
 function snapshot(s){return {normalized:copy(s.normalized),options:copy(s.options||{}),result:copy(s.result),selection:copy(s.selection||{})};}
 function key(s){return canonical(snapshot(s));}
 function current(plan){
  if(!actorCurrent(plan.actor)||lcGet('bazi')!==plan.page||plan.page.editing||!plan.page.result)return false;
  try{return key(plan.page)===plan.calculation&&canonical(release())===plan.releaseKey&&
   (plan.page.savedId||null)===plan.recordId&&(!plan.recordId||lcRecords().some(row=>row.kind==='bazi'&&row.id===plan.recordId&&canonical(row)===plan.archiveFingerprint));}catch{return false;}
 }
 function selected(plan){return current(plan)&&state.ssAiContext?.context===plan.context;}
 function frame(){
  if(sampleMode())return null;
  const s=lcGet('bazi');if(!version||!release()||!s.result||!s.normalized||s.editing)return null;
  return {actor:psToken(),page:s,calculation:key(s),recordId:s.savedId||null,releaseKey:canonical(release())};
 }
 function frameCurrent(value){
  if(!value||!actorCurrent(value.actor)||lcGet('bazi')!==value.page||value.page.editing)return false;
  try{return key(value.page)===value.calculation&&(value.page.savedId||null)===value.recordId&&canonical(release())===value.releaseKey;}catch{return false;}
 }
 function contextFor(data){
  const pillars=data.result.pillars;if(!Array.isArray(pillars)||pillars.length!==4)throw Error('B11_AI_PILLARS');
  const fields={chartType:'bazi',pillars:pillars.map(p=>String(p.key)+': '+String(p.ganZhi))};
  const p=data.result.periods?.[data.selection.period],y=p?.years?.[data.selection.year],m=y?.months?.[data.selection.month];
  if(p&&y&&m)fields.summary=['Selected major period: '+(p.ganZhi||'before first period')+' '+p.startYear+'–'+p.endYear,
   'Selected year: '+y.year+' '+y.ganZhi,'Selected solar-term month: '+m.ordinal+' '+m.ganZhi].join('; ');
  return {category:'chart',fields};
 }
 async function prepare(plan,data,archived){
  let record;
  if(plan.recordId){
   if(!archived||archived.id!==plan.recordId||canonical({normalized:archived.normalized,options:archived.options||{},result:archived.result})!==plan.archiveCalculation)return null;
   record=archived;
  }else{
   if(plan.page.b11Readonly||plan.page.b11Record||!Number.isFinite(plan.page.calculatedAt))return null;
   // This transient ID is never a saved archive ID. Public metadata explicitly has recordId:null.
   record=await version.captureCalculation({id:'live-b11-'+crypto.randomUUID(),normalized:data.normalized,options:data.options,
    result:data.result,manifest:plan.manifest,calculatedAt:Number.isFinite(plan.page.calculatedAt)?new Date(plan.page.calculatedAt).toISOString():null});
  }
  const inspected=await version.inspectSnapshot(record,plan.manifest);
  if(inspected.cacheReusable)return {record,manifest:plan.manifest,historical:false};
  // An intact old snapshot keeps its original manifest; it is never relabelled with today's implementation.
  if(plan.recordId&&record.provenance?.manifest){
   const old=await version.inspectSnapshot(record,record.provenance.manifest);
   if(old.cacheReusable)return {record,manifest:copy(record.provenance.manifest),historical:true};
  }
  return null;
 }
 async function interpret(value){
  if(!frameCurrent(value)||px.busy)return;
  const data=snapshot(value.page),manifest=copy(release()),context=contextFor(data),archived=value.recordId?copy(lcRecords().find(row=>row.kind==='bazi'&&row.id===value.recordId)||{}):null;
  if(value.recordId&&canonical(value.page.b11Record||{})!==canonical(archived))return;
  const plan={...value,manifest,context,archiveCalculation:canonical({normalized:data.normalized,options:data.options,result:data.result}),archiveFingerprint:archived?canonical(archived):null};
  plans.set(context,plan);plan.prepared=prepare(plan,data,archived).catch(()=>null);
  state.ssAiContext={title:label('Selected Ba Zi chart','本次选定的八字排盘','本次選定的八字排盤','བདམས་པའི་བ་ཙི་ས་ཁྲ།'),context};
  if(document.querySelector('#sheet[open]'))closeSheet();
  // The existing gateway intentionally shows its rules before a first request. Make that first view visible.
  if(px.gatewayReady&&!agState().loaded)navigate('serviceChat');
  return pxAsk(label('Please explain the four pillars and selected periods.','请帮我理解本次四柱与所选流运。','請幫我理解本次四柱與所選流運。','ཀ་བ་བཞི་དང་བདམས་པའི་དུས་རབས་གསལ་བཤད་བྱོས།'),false,context,'report');
 }
 function status(message){
  const entry=bindings.get(message);if(!entry||!actorCurrent(entry.plan.actor)||!state.support.ai.includes(message))return {state:'unbound',reusable:false,recordId:null};
  try{if(messageKey(message)!==entry.identity)return {state:'unbound',reusable:false,recordId:entry.metadata.recordId};}catch{return {state:'unbound',reusable:false,recordId:null};}
  const runtime=privacyState().data;
  if(!runtime?.policyAcknowledged||runtime.accountId!==entry.plan.actor.scope||runtime.revision!==entry.globalRevision||runtime.providerBinding!==entry.globalBinding)return {state:'unbound',reusable:false,recordId:entry.metadata.recordId};
  const reusable=!entry.historical&&current(entry.plan);
  return {...copy(entry.metadata),state:reusable?'current':'historical',reusable};
 }
 function sameAuthorization(prefs,caps,tag,gateway){
  if(!prefs?.policyAcknowledged||prefs.accountId!==tag?.accountId||!prefs.consents?.chart||prefs.disclosure.policyVersion!==tag.policyVersion)return false;
  if(!gateway)return prefs.consentEpoch===tag.consentEpoch&&prefs.providerBinding===tag.providerBinding;
  const auth=caps?.providers?.find(p=>p.id===tag.providerId)?.authorization;
  return !!auth?.receiptValid&&auth.consentEpoch===tag.consentEpoch&&auth.providerBinding===tag.providerBinding&&auth.policyVersion===tag.policyVersion&&
   prefs.revision===auth.globalRevision&&prefs.providerBinding===auth.globalBinding&&prefs.disclosure.policyVersion===auth.policyVersion;
 }
 function localPermission(prefs,save=false){
  const local=privacyState().data;return !!local?.policyAcknowledged&&local.accountId===prefs.accountId&&local.revision===prefs.revision&&
   local.providerBinding===prefs.providerBinding&&(!save||local.consents?.saveConversations===true&&prefs.consents?.saveConversations===true);
 }
 function validStored(message,actor){
  const m=message?.baziInterpretation;
  return !!m&&m.schema===1&&m.origin==='b11-new-assistant'&&m.accountId===actor.scope&&m.messageId===message.id&&
   m.interpretationId===(message.gatewayJobId||message.id)&&m.gatewayJobId===(message.gatewayJobId||null)&&message.role==='assistant'&&!message.restored&&
   message.privacy?.accountId===actor.scope&&message.privacy.category==='chart'&&message.privacy.source==='assistant'&&
   (m.recordId===null||typeof m.recordId==='string')&&/^bazi:v1:[a-f0-9]{64}$/.test(m.cacheKey)&&
   ['outputFingerprint','selectedViewFingerprint','replyFingerprint'].every(key=>/^sha256:[a-f0-9]{64}$/.test(m[key]))&&
   m.authorization?.consentEpoch===message.privacy.consentEpoch&&m.authorization.providerBinding===message.privacy.providerBinding&&
   m.authorization.policyVersion===message.privacy.policyVersion&&m.authorization.providerId===message.privacy.providerId;
 }
 async function restore(message){
  if(sampleMode())return false;
  const actor=psToken(),run=px.privacyRun;if(!validStored(message,actor)||!state.support.ai.includes(message)||bindings.has(message))return false;
  const stored=copy(message.baziInterpretation),identity=messageKey(message),page=lcGet('bazi'),nowRelease=copy(release()),source=stored.recordId?lcRecords().find(row=>row.kind==='bazi'&&row.id===stored.recordId):null;
  const alive=()=>actorCurrent(actor)&&px.privacyRun===run&&state.support.ai.includes(message)&&canonical(message.baziInterpretation)===canonical(stored)&&
   messageKey(message)===identity&&canonical(release())===canonical(nowRelease)&&
   (!stored.recordId||lcRecords().some(row=>row.id===stored.recordId&&canonical(row)===canonical(source)));
  try{
   if(!stored.selection||Object.keys(stored.selection).some(key=>!['period','year','month','mode'].includes(key)))return false;
   if(await version.fingerprint(stored.selection)!==stored.selectedViewFingerprint||await version.fingerprint({id:message.id,gatewayJobId:message.gatewayJobId||null,text:message.text})!==stored.replyFingerprint)return false;
   let record=source?copy(source):null;
   if(stored.recordId&&!record)return false;
   if(!record){
    // An unsaved result has no archive to reconstruct. Only a real current calculation with the original release can verify it.
    if(page.savedId||page.b11Readonly||page.b11Record||!page.result||!page.normalized||!Number.isFinite(page.calculatedAt)||
     canonical(version.manifest(nowRelease))!==canonical(version.manifest(stored.manifest)))return false;
    record=await version.captureCalculation({id:'live-b11-'+crypto.randomUUID(),normalized:copy(page.normalized),options:copy(page.options||{}),result:copy(page.result),manifest:nowRelease,calculatedAt:new Date(page.calculatedAt).toISOString()});
   }
   const inspected=await version.inspectSnapshot(record,stored.manifest);
   if(!inspected.cacheReusable||inspected.cacheKey!==stored.cacheKey||inspected.outputFingerprint!==stored.outputFingerprint)return false;
   const plan={actor,page,recordId:stored.recordId,releaseKey:canonical(nowRelease),
    calculation:canonical({normalized:record.normalized,options:record.options||{},result:record.result,selection:stored.selection}),archiveFingerprint:source?canonical(source):null};
   const [prefs,caps]=await Promise.all([pxApi('privacy/preferences'),message.gatewayJobId?pxApi('ai-gateway/capabilities'):null]);
   if(!alive()||!sameAuthorization(prefs,caps,message.privacy,!!message.gatewayJobId)||!localPermission(prefs,true)||
    prefs.revision!==stored.authorization.globalRevision||prefs.providerBinding!==stored.authorization.globalBinding)return false;
   bindings.set(message,{plan,identity,historical:canonical(version.manifest(nowRelease))!==canonical(version.manifest(stored.manifest)),globalRevision:prefs.revision,globalBinding:prefs.providerBinding,
    metadata:{schema:1,interpretationId:stored.interpretationId,recordId:stored.recordId,cacheKey:stored.cacheKey,outputFingerprint:stored.outputFingerprint,
     selectedViewFingerprint:stored.selectedViewFingerprint,storage:'existing-personal-store'}});
   return true;
  }catch{return false;}
 }
 const askBefore=pxAsk;
 pxAsk=async function(text,retry=false,context=state.ssAiContext?.context||null,source='user'){
  if(sampleMode()){toast(label('Exit the sample view before using AI.','请先退出样本核对，再使用AI。','請先退出樣本核對，再使用AI。','AI བཀོལ་སྔོན་དཔེ་མཚོན་ལས་འཐོན།'));return;} 
  const chosen=retry?px.retry?.context:context,plan=chosen&&plans.get(chosen);
  if(!plan||px.busy)return askBefore(text,retry,context,source);
  if(!selected(plan))return;
  const before=new Set(state.support.ai),ids=new Set(state.support.ai.map(m=>m.id)),jobs=new Set(state.support.ai.map(m=>m.gatewayJobId).filter(Boolean));
  const previousRun=px.privacyRun,promise=askBefore(text,retry,context,source),run=px.privacyRun;
  const answer=await promise;
  const alive=()=>actorCurrent(plan.actor)&&px.privacyRun===run&&run===previousRun+1&&selected(plan);
  if(!alive())return answer;
  const candidates=state.support.ai.filter(m=>!before.has(m)&&m.id&&!ids.has(m.id)&&m.role==='assistant'&&typeof m.text==='string'&&m.text.trim()&&!m.restored&&
   m.privacy?.accountId===plan.actor.scope&&m.privacy.category==='chart'&&m.privacy.source==='assistant'&&(!m.gatewayJobId||!jobs.has(m.gatewayJobId)));
  if(candidates.length!==1)return answer;
  const message=candidates[0],identity=messageKey(message),sameMessage=()=>messageKey(message)===identity,
   prepared=await plan.prepared;if(!prepared||!alive()||!sameMessage())return answer;
  try{
   const binding=await version.bindInterpretation(prepared.record,{id:message.gatewayJobId||message.id},prepared.manifest),selection=copy(plan.page.selection||{}),
    selectedViewFingerprint=await version.fingerprint(selection),replyFingerprint=await version.fingerprint({id:message.id,gatewayJobId:message.gatewayJobId||null,text:message.text});
   if(!alive()||!state.support.ai.includes(message)||!sameMessage())return answer;
   // Recheck the actual account's latest permission after all fingerprint work. No cached save flag is trusted.
   const [prefs,caps,job]=await Promise.all([pxApi('privacy/preferences'),message.gatewayJobId?pxApi('ai-gateway/capabilities'):null,
    message.gatewayJobId?pxApi('ai-gateway/jobs/'+encodeURIComponent(message.gatewayJobId)):null]);
   if(!alive()||!state.support.ai.includes(message)||!sameMessage()||!prefs.policyAcknowledged||prefs.accountId!==plan.actor.scope||!prefs.consents?.chart)return answer;
   const tag=message.privacy;
   if(job?.status!=='succeeded'&&message.gatewayJobId||!sameAuthorization(prefs,caps,tag,!!message.gatewayJobId)||!localPermission(prefs))return answer;
   let storage='memory-only';
   if(localPermission(prefs,true)&&!Object.prototype.hasOwnProperty.call(message,'baziInterpretation')){
    message.baziInterpretation={schema:1,origin:'b11-new-assistant',accountId:plan.actor.scope,messageId:message.id,gatewayJobId:message.gatewayJobId||null,
     interpretationId:binding.interpretationId,recordId:plan.recordId,cacheKey:binding.cacheKey,outputFingerprint:binding.outputFingerprint,selectedViewFingerprint,replyFingerprint,
     manifest:version.manifest(prepared.manifest),selection,authorization:{providerId:tag.providerId,providerBinding:tag.providerBinding,consentEpoch:tag.consentEpoch,
      policyVersion:tag.policyVersion,globalRevision:prefs.revision,globalBinding:prefs.providerBinding}};
    try{if(persist())storage='existing-personal-store';else delete message.baziInterpretation;}catch{delete message.baziInterpretation;}
   }
   bindings.set(message,{plan,identity,historical:prepared.historical,globalRevision:prefs.revision,globalBinding:prefs.providerBinding,
    metadata:{schema:1,interpretationId:binding.interpretationId,recordId:plan.recordId,cacheKey:binding.cacheKey,outputFingerprint:binding.outputFingerprint,
     selectedViewFingerprint,storage}});
   // Only this new object may receive metadata. Archive rows and server snapshots are never rewritten.
   if(alive()&&['service','serviceChat'].includes(state.page))render(false);
  }catch{/* Provenance failures never manufacture a successful reply or bypass the AI client's error state. */}
  return answer;
 };
 const actionsBefore=lcResultActions;
 lcResultActions=function(kind){
  const html=actionsBefore(kind);if(kind!=='bazi')return html;
  let value;try{value=frame();}catch{return html;}if(!value)return html;
  const id=String(++serial);frames.set(id,value);while(frames.size>50)frames.delete(frames.keys().next().value);
  return html+`<div class="lc-result-actions"><button type="button" class="btn secondary" data-b11-ai-action="interpret" data-b11-ai-frame="${id}">${label('Explain this chart with AI','用AI解读当前排盘','用AI解讀目前排盤','AI ཡིས་ས་ཁྲ་གསལ་བཤད།')}</button></div><p class="small">${label('Only the four pillars and selected periods are sent after your permission. Reply links are saved on this device only when conversation saving is enabled.','授权后仅发送四柱与所选流运摘要；仅在开启会话保存时，关联信息才随回复保存在本机。','授權後僅傳送四柱與所選流運摘要；僅在開啟對話儲存時，關聯資訊才隨回覆儲存在本機。','ཆོག་མཆན་རྗེས་ཀ་བ་བཞི་དང་བདམས་དུས་ཀྱི་བསྡུས་དོན་ཙམ་གཏོང་།')}</p>`;
 };
 document.addEventListener('click',event=>{const button=event.target.closest?.('[data-b11-ai-action=interpret]');if(!button)return;
  event.preventDefault();event.stopImmediatePropagation();const value=frames.get(button.dataset.b11AiFrame);if(frameCurrent(value))interpret(value).catch(()=>{});
 },true);
 const renderBefore=renderNow;
 renderNow=function(resetScroll=true){
  renderBefore(resetScroll);
  if(!['service','serviceChat'].includes(state.page))return;
  const articles=document.querySelectorAll('#px-ai-messages > article.ss-message');
  state.support.ai.forEach((message,index)=>{if(message.role!=='assistant')return;const hasBinding=bindings.has(message),chart=message.privacy?.category==='chart';if(!hasBinding&&!chart)return;
   if(!hasBinding&&validStored(message,psToken())){
    let attemptKey;try{attemptKey=canonical({actor:psToken(),run:px.privacyRun,revision:privacyState().data?.revision??null,release:release(),calculation:lcGet('bazi').result?key(lcGet('bazi')):null});}catch{attemptKey='invalid';}
    if(restores.get(message)!==attemptKey){restores.set(message,attemptKey);queueMicrotask(async()=>{if(await restore(message)&&['service','serviceChat'].includes(state.page))render(false);});}
   }
   const value=status(message),node=document.createElement('small');node.dataset.b11AiStatus=value.state;node.dataset.b11AiReply=message.id||'';node.className='small';
   node.textContent=value.state==='current'?label(value.recordId?'Linked to this saved chart':'Linked to this unsaved calculation',value.recordId?'已关联本次已保存排盘':'已关联本次计算（未保存排盘）',value.recordId?'已關聯本次已儲存排盤':'已關聯本次計算（未儲存排盤）','ས་ཁྲ་འདི་དང་འབྲེལ་ཡོད།'):
    value.state==='historical'?label('Earlier chart or version · not reusable','对应先前排盘或版本 · 不复用','對應先前排盤或版本 · 不重用','སྔར་གྱི་ས་ཁྲ་དང་ཐོན་རིམ།'):
    label('Chart version is unbound','未关联排盘版本','未關聯排盤版本','ས་ཁྲའི་ཐོན་རིམ་དང་མ་འབྲེལ།');
   articles[index]?.append(node);
  });
 };
 root.BaziInterpretationBridge=Object.freeze({schema:1,storage:'existing-consent-only',status,restore,interpretCurrent:()=>interpret(frame()),get installed(){return true;}});
})(globalThis);
