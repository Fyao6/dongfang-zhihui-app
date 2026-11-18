/* Explicit owner-only entry. Server actual output is never fed into the APP calculator. */
const bzsLoaderCopy=(en,zh,hant,bo)=>coText(en,zh,hant,bo);
let bzsLoaderState=null;
function bzsLoaderActor(){return {token:psToken(),owner:px.user?.id,role:px.user?.role};}
function bzsLoaderCurrent(s){const a=bzsLoaderActor();return s===bzsLoaderState&&s.actor.owner===a.owner&&a.role==='admin'&&a.token.scope===s.actor.token.scope&&a.token.epoch===s.actor.token.epoch&&(s.opening||s.entered||s.page===state.page);}
function bzsLoaderDrop(){document.querySelector('[data-bzs-loader]')?.remove();document.querySelector('[data-bzs-banner]')?.remove();bzsLoaderState=null;}
function bzsLoaderDialog(s,body){if(!bzsLoaderCurrent(s))return;document.querySelector('[data-bzs-loader]')?.remove();const node=document.createElement('dialog');node.className='bzs-loader';node.dataset.bzsLoader='';node.setAttribute('aria-modal','true');node.setAttribute('aria-labelledby','bzs-loader-title');node.innerHTML='<h2 id="bzs-loader-title">'+bzsLoaderCopy('Temporary sample review','临时样本核对','臨時樣本核對','དཔེ་མཚོན་ཞིབ་བསྡུར།')+'</h2>'+body;node.addEventListener('cancel',()=>{globalThis.BaziSampleBridge?.close();bzsLoaderDrop();});document.body.append(node);node.showModal();node.querySelector('button')?.focus();}
function bzsLoaderCloseLabel(){return bzsLoaderCopy('Close','关闭','關閉','ཁ་རྒྱག');}
async function bzsLoaderFetch(s,path){const response=await fetch('/api/admin/bazi-samples'+path,{credentials:'same-origin'}),data=await response.json();if(!bzsLoaderCurrent(s))throw Error('sample_actor_changed');if(!response.ok)throw Error(data.error||'sample_load_failed');return data;}
async function bzsLoaderStart(runId,caseId){
 const s={actor:bzsLoaderActor(),runId,caseId,page:state.page,ready:false,opening:false,entered:false};bzsLoaderState=s;
 bzsLoaderDialog(s,'<p role="status">'+bzsLoaderCopy('Loading private sample…','正在读取当前账号的样本…','正在讀取目前帳號的樣本…','དཔེ་མཚོན་ཀློག་བཞིན།')+'</p><button class="btn secondary" data-bzs-loader-action="close">'+bzsLoaderCloseLabel()+'</button>');
 try{const run=await bzsLoaderFetch(s,'/runs/'+encodeURIComponent(runId)),detail=await bzsLoaderFetch(s,'/runs/'+encodeURIComponent(runId)+'/cases/'+encodeURIComponent(caseId));if(!bzsLoaderCurrent(s))return;
  const source=globalThis.BAZI_SAMPLE_SOURCE_MANIFEST;
  if(!source?.implementationReady||!source.manifestSha256||source.manifestSha256!==run.run.manifest?.sourceManifestSha256)throw Error('implementation_changed');
  s.run=run.run;s.sampleCase=detail.sampleCase;s.ready=true;
  bzsLoaderDialog(s,'<p class="bzs-boundary">'+bzsLoaderCopy('This private sample uses a temporary chart. Teacher confirmation: 0; professional validation: pending.','此样本使用临时命盘。老师确认样本：0；专业算法验收：待完成。','此樣本使用臨時命盤。老師確認樣本：0；專業演算法驗收：待完成。','དཔེ་མཚོན་འདི་གནས་སྐབས་ཀྱི་ཞིབ་བསྡུར་ཡིན།')+'</p><p>'+esc(s.sampleCase.label)+' · '+esc(caseId)+'</p><pre class="bzs-json">'+esc(JSON.stringify({input:s.sampleCase.input,context:s.sampleCase.context,options:s.sampleCase.options,selection:s.sampleCase.selection},null,2))+'</pre><p>'+bzsLoaderCopy('Review the source and reference time, then enter explicitly. Leaving this chart closes the temporary context.','核对来源与参考时刻后进入；离开命盘即关闭临时状态。','核對來源與參考時刻後進入；離開命盤即關閉臨時狀態。','དུས་ཚོད་དང་ཁུངས་ཞིབ་བསྡུར་བྱོས།')+'</p><p><code>'+esc(s.run.manifestHash)+'</code></p><div class="actions"><button class="btn" data-bzs-loader-action="open">'+bzsLoaderCopy('Enter temporary review','进入临时核对视图','進入臨時核對檢視','གནས་སྐབས་ཞིབ་བསྡུར་ལ་འཇུག')+'</button><button class="btn secondary" data-bzs-loader-action="close">'+bzsLoaderCloseLabel()+'</button></div>');
 }catch(error){if(bzsLoaderCurrent(s))bzsLoaderDialog(s,'<p role="alert">'+bzsLoaderCopy('Sample unavailable. Check the account and implementation version.','样本暂不可用，请核对账号与实现版本。','樣本暫不可用，請核對帳號與實作版本。','དཔེ་མཚོན་སྤྱོད་མི་ཐུབ།')+' '+esc(error.message)+'</p><button class="btn secondary" data-bzs-loader-action="close">'+bzsLoaderCloseLabel()+'</button>');}
}
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-bzs-loader-action]');if(!button)return;event.preventDefault();const s=bzsLoaderState;if(!s)return;
 if(button.dataset.bzsLoaderAction==='close'){globalThis.BaziSampleBridge?.close();bzsLoaderDrop();return;}
 if(!bzsLoaderCurrent(s)||!s.ready||s.opening)return;s.opening=true;button.disabled=true;
 try{await globalThis.BaziSampleBridge.open({sampleCase:s.sampleCase,runId:s.runId,setVersionId:s.run.setVersionId,caseId:s.caseId,manifestHash:s.run.manifestHash});if(!bzsLoaderCurrent(s)||!globalThis.BaziSampleBridge.isActive()){globalThis.BaziSampleBridge.close();bzsLoaderDrop();return;}s.entered=true;s.opening=false;document.querySelector('[data-bzs-loader]')?.remove();}
 catch(error){if(bzsLoaderCurrent(s)){if(error.code==='sample_context_changed'||error.message==='sample_context_changed'||state.page!==s.page){bzsLoaderDrop();return;}s.opening=false;button.disabled=false;const p=document.createElement('p');p.setAttribute('role','alert');p.textContent=error.message;button.parentElement.append(p);}}

});
/* Timer only observes account/page identity; it never changes the sample asOf or practice timer. */
const bzsLoaderParams=new URLSearchParams(location.search),bzsLoaderRun=bzsLoaderParams.get('baziSampleRun'),bzsLoaderCase=bzsLoaderParams.get('baziSampleCase');
let bzsLoaderAttempted=false;
setInterval(()=>{
 if(bzsLoaderState&&!bzsLoaderCurrent(bzsLoaderState)){globalThis.BaziSampleBridge?.close();bzsLoaderDrop();}
 if(bzsLoaderState?.entered&&!globalThis.BaziSampleBridge?.isActive?.())bzsLoaderDrop();
 if(bzsLoaderAttempted||!bzsLoaderRun||!bzsLoaderCase||!px.loaded||!px.user)return;
 bzsLoaderAttempted=true;
 if(px.user.role==='admin'&&/^[A-Za-z0-9:_-]{1,100}$/.test(bzsLoaderRun)&&/^[A-Za-z0-9:_-]{1,100}$/.test(bzsLoaderCase))bzsLoaderStart(bzsLoaderRun,bzsLoaderCase);
},300);
