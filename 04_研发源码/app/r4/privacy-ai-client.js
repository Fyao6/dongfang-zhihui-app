// Legacy conversations remain visible. Only messages with the current consent receipt are sent.
const privacySnapshotBefore=psSnapshot;
psSnapshot=function(){const value=privacySnapshotBefore();if(value.support)value.support={...value.support,ai:privacyConversationForStorage(value.support.ai||[])};return value;};
px.privacyActor=psToken();px.privacyRun=0;px.retry=null;
const privacyClearBefore=privacyClearLocal;
privacyClearLocal=function(kind,token){const cleared=privacyClearBefore(kind,token);if(cleared&&['conversations','records'].includes(kind)){++px.privacyRun;px.busy=false;px.retry=null;}return cleared;};
function privacyClientScope(){const actor=psToken();if(px.privacyActor.scope!==actor.scope||px.privacyActor.epoch!==actor.epoch){px.privacyActor=actor;++px.privacyRun;px.busy=false;px.aiError='';px.retry=null;}return actor;}
function privacyMessageTag(auth,category,source){return {accountId:auth.accountId,consentEpoch:auth.consentEpoch,providerId:auth.providerId,providerBinding:auth.providerBinding,policyVersion:auth.policyVersion,category,source};}
pxAsk=async function(text,retry=false,selected=state.ssAiContext?.context||null,source='user'){
 const token=privacyClientScope();if(px.busy||!text?.trim()||!token.scope)return;
 let memorySelection=retry?px.retry?.memorySelection:null;
 if(retry){if(!px.retry||px.retry.scope!==token.scope||px.retry.epoch!==token.epoch)return;({text,context:selected,source}=px.retry);}
 const run=++px.privacyRun,before=psClone(state.support.ai);px.busy=true;px.aiError='';px.retry={scope:token.scope,epoch:token.epoch,text:text.trim(),context:selected,source};render(false);
 try{
  if(!px.aiReady)throw Error(prText('AI connection is not configured.','AI服务尚未连接，请先完成服务配置。','AI服務尚未連線，請先完成服務設定。','AI ཞབས་ཞུ་ད་དུང་མ་མཐུད།'));
  const auth=await privacyBeforeAI(selected);if(!psCurrent(token)||run!==px.privacyRun)return;
  if(!retry)memorySelection=await MemoryServiceUI.selectForRequest();
  if(!psCurrent(token)||run!==px.privacyRun)return;
  px.retry.memorySelection=memorySelection;
  const category=selected?.category||'general',tag=privacyMessageTag(auth,category,source),last=state.support.ai.at(-1);
  if(!retry||last?.role!=='user'||last.text!==text.trim()||last.privacy?.consentEpoch!==auth.consentEpoch)state.support.ai.push({id:ssId(),role:'user',text:text.trim(),at:new Date().toISOString(),privacy:tag});
  state.support.ai=state.support.ai.slice(-40);if(!persist()){state.support.ai=before;throw Error(psSaveError());}
  state.page='serviceChat';render(false);pxScrollChat();
  const messages=privacyAIHistory(state.support.ai,auth,token,memorySelection);if(!messages.length)throw Error(prText('Start a new question with the current permissions.','请按当前授权重新输入问题。','請依目前授權重新輸入問題。','ད་ལྟའི་ཆོག་མཆན་ལྟར་འདྲི་བ་གསར་པ་འདྲི།'));
  const reply=await pxApi('ai/chat',{messages,context:auth.context,...(memorySelection?{memorySelection}:{})});if(!psCurrent(token)||run!==px.privacyRun)return;
  const fresh=await pxApi('privacy/preferences');if(!psCurrent(token)||run!==px.privacyRun)return;privacyState().data=fresh;
  if(!fresh.policyAcknowledged||fresh.consentEpoch!==auth.consentEpoch)throw Error(prText('Permissions changed. This response was discarded.','授权已变更，本次回复已丢弃。','授權已變更，本次回覆已捨棄。','ཆོག་མཆན་བསྒྱུར་བས་ལན་འདི་མི་ཉར།'));
  if(memorySelection&&(!fresh.memory?.enabled||fresh.memory.memoryEpoch!==memorySelection.memoryEpoch))throw Error(prText('Memory permission changed.','记忆授权已变化。','記憶授權已變更。','དྲན་ཐོའི་ཆོག་མཆན་བསྒྱུར།'));
  state.support.ai.push({id:ssId(),role:'assistant',text:reply.text,at:new Date().toISOString(),privacy:reply.privacy||privacyMessageTag(auth,category,'assistant')});if(!persist())px.aiError=psSaveError();
 }catch(error){if(psCurrent(token)&&run===px.privacyRun)px.aiError=error.message;}
 finally{if(psCurrent(token)&&run===px.privacyRun){px.busy=false;if(['service','serviceChat'].includes(state.page)){render(false);pxScrollChat();}}}
};
ssInterpret=function(id){
 const report=ssReportById(id);if(!report?.ready)return;
 const category=id==='ziwei'?'chart':'wellbeing',fields=category==='chart'?{chartType:'ziwei',palaces:report.rows.map(([a,b])=>a+': '+b),summary:report.summary}:{note:report.rows.map(([a,b])=>a+': '+b).join('\n').slice(0,4500)};
 const context={category,fields};state.ssAiContext={title:report.title,context};
 return pxAsk(prText('Please explain the record I selected.','请帮我理解本次选定的记录。','請幫我理解本次選定的記錄。','ཐེངས་འདིར་བདམས་པའི་ཟིན་ཐོ་གསལ་བཤད་བྱོས།'),false,context,'report');
};
const privacyChatBefore=pxChat;
pxChat=function(){return privacyChatBefore().replace('<form id="ss-ai-form"',`<p class="pr-note">${prText('New conversations are saved only with separate permission. Earlier chats are not automatically sent to AI.','新的会话仅在单独授权后保存；旧聊天不会自动发送给AI。','新的對話僅在單獨授權後儲存；舊聊天不會自動傳送給AI。','ཆོག་མཆན་སོ་སོར་ཡོད་ན་གླེང་མོལ་གསར་པ་ཉར། སྔར་གྱི་གླེང་མོལ་རང་འགུལ་མི་གཏོང་།')} ${go(privacyTitle(),'privacyCenter','secondary')}</p><form id="ss-ai-form"`);};
screens.service=pxChat;screens.serviceChat=pxChat;ewNavigationDefaults.privacyCenter='profileSettings';
const privacyClientRenderBefore=renderNow;
renderNow=function(resetScroll=true){privacyClientScope();privacyClientRenderBefore(resetScroll);if(state.page==='privacyCenter')document.querySelectorAll('#nav [data-to]').forEach(b=>{const active=b.dataset.to==='profile';b.classList.toggle('selected',active);if(active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});};
