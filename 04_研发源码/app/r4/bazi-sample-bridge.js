// Explicit, account-bound sample view. Never writes personal birth details or archives.
(function(root){
 'use strict';
 let current=null,pending=null,serial=0;
 const clone=value=>JSON.parse(BaziSampleEngine.createEngine({lunar:LCLunar}).canonical(value));
 const problem=code=>Object.assign(new Error(code),{code});
 function actor(){const token=psToken();if(!token.scope||px.user?.id!==token.scope||px.user?.role!=='admin'||!psCurrent(token))throw problem('sample_admin_required');return token;}
 function valid(value=current){return !!value&&value===current&&psCurrent(value.actor)&&px.user?.id===value.actor.scope&&px.user?.role==='admin';}
 function pendingValid(value){return !!value&&value===pending&&value.sequence===serial&&psCurrent(value.actor)&&px.user?.id===value.actor.scope&&px.user?.role==='admin'&&state.page===value.page;}
 function isActive(){if(current&&!valid()||pending&&!pendingValid(pending))destroy();return valid();}
 function destroy(){serial++;const prior=current,wasPending=!!pending;current=null;pending=null;if(prior){if(document.querySelector('#sheet[open] .lcb-tools-panel'))closeSheet();prior.state.result=null;prior.report=null;prior.sampleCase=null;}return !!prior||wasPending;}
 async function freshAdmin(token){const auth=await pxApi('auth/status');if(!psCurrent(token)||auth?.user?.id!==token.scope||auth.user.role!=='admin')throw problem('sample_admin_required');}
 async function open({sampleCase,runId,setVersionId,caseId,manifestHash}={}){
  const token=actor();destroy();const generation=serial,opening={sequence:serial,actor:token,page:state.page};pending=opening;
  try{
  const engine=lcBaziShared();engine.validateCase(sampleCase);if(caseId!==sampleCase.caseId||typeof runId!=='string'||!/^[A-Za-z0-9:_-]{1,100}$/.test(runId)||typeof setVersionId!=='string'||!/^[A-Za-z0-9:_-]{1,100}$/.test(setVersionId)||typeof manifestHash!=='string'||!/^[a-f0-9]{64}$/.test(manifestHash))throw problem('sample_context_invalid');
  const source=clone(sampleCase);await freshAdmin(token);if(!pendingValid(opening))throw problem('sample_context_changed');const report=await engine.computeCase(source);if(!pendingValid(opening))throw problem('sample_context_changed');await freshAdmin(token);
  if(!pendingValid(opening))throw problem('sample_context_changed');
  const stamp=Date.parse(source.context.asOfUtc),temp={input:{...source.input,timezone:source.context.mode==='legacy-reference'?source.context.legacyTimezone:'Etc/GMT-8'},normalized:clone(report.stages.normalizedInput),options:clone(source.options),result:clone(report.stages.rawOutput),selection:report.selection?{period:report.selection.period,year:report.selection.year,month:report.selection.month,mode:report.selection.mode}:{},error:report.errorCode,errorCode:report.errorCode,notice:'',editing:false,savedId:null,b11Readonly:true,calculatedAt:stamp,sampleContext:true,sampleAsOfMs:stamp};
  // Clearing pending before our own committed navigation distinguishes it from an earlier user navigation.
  pending=null;current={contextId:'bazi-sample:'+crypto.randomUUID(),generation,actor:{...token},runId,setVersionId,caseId,manifestHash,asOfUtc:source.context.asOfUtc,sampleCase:source,report,state:temp};
  if(document.querySelector('#sheet[open]'))closeSheet();navigate('classicsWisdom');return snapshot();
  }catch(error){if(pending===opening)pending=null;throw error;}
 }
 function displayState(s){const v=lcbTimelineView(s);return {panel:v.panel,fullBoard:!!v.fullBoard,showFlowMonth:!!v.showFlowMonth,boardExpanded:!!v.boardExpanded,language:state.lang};}
 async function snapshot(){
  if(!isActive())return null;const value=current,engine=lcBaziShared();try{await freshAdmin(value.actor);}catch(error){if(current===value){destroy();if(state.page==='classicsWisdom')render(false);}throw error;}if(!valid(value))return null;
  const view=value.state,display=displayState(view),displayBefore=engine.canonical(display),stages=clone(value.report.stages);
  let timing=null;if(value.report.status==='succeeded'&&view.result){timing=lcbResolveSelection(view.result,view,value.state.sampleAsOfMs);stages.selection={...timing,asOfUtc:value.asOfUtc};stages.comparison=engine.buildComparison(view.result,{...view.selection,beforeStart:timing.beforeStart});stages.annotations=engine.buildAnnotations(view.result,stages.comparison);}
  const selected=engine.canonical(view.selection),fingerprints={};for(const [key,part]of Object.entries(stages))fingerprints[key]=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(engine.canonical(part)))),b=>b.toString(16).padStart(2,'0')).join('');
  if(!valid(value)||engine.canonical(view.selection)!==selected||engine.canonical(displayState(view))!==displayBefore)return null;
  return {contextId:value.contextId,generation:value.generation,actor:{scope:value.actor.scope,epoch:value.actor.epoch},runId:value.runId,setVersionId:value.setVersionId,caseId:value.caseId,manifestHash:value.manifestHash,asOfUtc:value.asOfUtc,status:value.report.status,errorCode:value.report.errorCode,stages,timing,selection:clone(view.selection),fingerprints,display,teacherConfirmed:false,professionalValidation:false,serverDomStatus:'not_run'};
 }
 const beforeGet=lcGet;lcGet=function(kind){if(kind==='bazi'&&isActive())return current.state;return beforeGet(kind);};
 const beforeNavigate=navigate;navigate=function(page,...args){if(pending||isActive()&&page!=='classicsWisdom')destroy();return beforeNavigate(page,...args);};
 const beforeRender=renderNow;renderNow=function(...args){if(current&&(!valid()||state.page!=='classicsWisdom')||pending&&!pendingValid(pending))destroy();return beforeRender(...args);};
 const beforeScreen=screens.classicsWisdom;screens.classicsWisdom=function(){
  if(!isActive())return beforeScreen();const value=current,notice=`<aside class="card" data-bazi-sample-context="${esc(value.contextId)}"><p>${lcText('Temporary sample view · personal records unchanged · no saving or AI sending','临时样本核对 · 不改个人资料 · 禁止存档和AI外发','臨時樣本核對 · 不改個人資料 · 禁止存檔和AI外傳','དཔེ་མཚོན་གནས་སྐབས་བསྡུར་བ། སྒེར་གྱི་ཐོ་མི་བསྒྱུར།')}</p><p>${esc(value.caseId)} · ${esc(value.asOfUtc)}</p><button class="btn secondary" type="button" data-bazi-sample-close>${lcText('Exit sample view','退出样本核对','退出樣本核對','དཔེ་མཚོན་ལས་ཕྱིར་འཐོན།')}</button></aside>`;
  if(value.report.status!=='succeeded')return `<section class="page lc-page lcb-page" data-lc-result="bazi" data-bazi-sample-blocked>${pxTop(lcText('Sample reference','样本核对','樣本核對','དཔེ་མཚོན་བསྡུར་བ།'),'','lifeResult')}${notice}<article class="card"><p role="status">${esc(value.report.errorCode)}</p><p>${esc(value.sampleCase.input.date)} · ${esc(value.sampleCase.input.time||lcText('Unknown time','时间未知','時間未知','དུས་ཚོད་མི་ཤེས།'))}</p></article></section>`;
  return lcBaziScreen().replace('</header>','</header>'+notice);
 };
 const beforeNotes=lcbNotesPanel;lcbNotesPanel=function(){return isActive()?'':beforeNotes();};
 const beforeOptions=lbOptions;lbOptions=function(kind){return kind==='bazi'&&isActive()?'':beforeOptions(kind);};
 const beforeEdit=lbEdit;lbEdit=function(...args){if(isActive()){toast(lcText('Exit the sample view to edit personal birth details.','请先退出样本核对，再修改个人出生资料。','請先退出樣本核對，再修改個人出生資料。','སྒེར་གྱི་གནས་ཚུལ་བཟོ་སྔོན་དཔེ་མཚོན་ལས་འཐོན།'));return;}return beforeEdit(...args);};
 const beforeSaveProfile=lbSaveProfile;lbSaveProfile=function(...args){if(isActive())throw problem('sample_personal_write_blocked');return beforeSaveProfile(...args);};
 const beforeActions=lcResultActions;lcResultActions=function(kind){return kind==='bazi'&&isActive()?'':beforeActions(kind);};
 document.addEventListener('click',event=>{if(!event.target.closest?.('[data-bazi-sample-close]'))return;event.preventDefault();event.stopImmediatePropagation();destroy();if(state.page==='classicsWisdom')render(false);},true);
 // Window capture precedes legacy document listeners; function-level guards above remain authoritative.
 window.addEventListener('submit',event=>{if(isActive()&&event.target.matches?.('#lb-birth-form,form[data-lb-options],form[data-lc-form]')){event.preventDefault();event.stopImmediatePropagation();}},true);
 window.addEventListener('click',event=>{if(isActive()&&event.target.closest?.('[data-lb-action],[data-lc-action],[data-b11-action],[data-b11-ai-action]')){event.preventDefault();event.stopImmediatePropagation();}},true);
 window.addEventListener('ew-personal-scope',()=>{if(current&&!valid())destroy();});
 root.BaziSampleBridge=Object.freeze({open,close:()=>{const changed=destroy();if(changed&&state.page==='classicsWisdom')render(false);return changed;},snapshot,isActive,get active(){return isActive();},get opening(){return !!pending&&pendingValid(pending);}});
})(globalThis);
