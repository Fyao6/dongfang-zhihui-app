// Account closure: a second explicit confirmation, never an external cancellation claim.
const acRuntime={run:0,stage:'password',challenge:null,nonce:'',requestId:'',receipt:null,busy:false,actor:null,summary:null};
const acText=(en,zh,hant,bo)=>({en,zh,'zh-Hant':hant,bo})[state.lang]||zh;
const acClosedKey=owner=>'ew-account-closed-v1:'+owner;
function acClosed(owner){try{return !!owner&&localStorage.getItem(acClosedKey(owner))!==null;}catch{return false;}}
const acOriginalPersist=persist;
persist=function(automatic=false){if(acClosed(personalStorage.scope))return false;return acOriginalPersist(automatic);};
const acOriginalPsCurrent=psCurrent;
psCurrent=function(token){return acOriginalPsCurrent(token)&&!acClosed(token.scope);};
if(typeof tbSave==='function'){const prior=tbSave;tbSave=function(...args){if(acClosed(personalStorage.scope))return false;return prior(...args);};}
function acCurrent(token,run){return psCurrent(token)&&run===acRuntime.run&&px.user?.id===token.scope;}
function acEraseLocal(owner){
 // Switch first: existing scope-switch hooks may save the old timer/personal payload.
 // A tombstone prevents this version's persist hooks from resurrecting that payload.
 let ok=true;
 try{localStorage.setItem(acClosedKey(owner),JSON.stringify({closed:true}));}catch{ok=false;}
 pxInvalidateBootstrap();
 psSwitch('guest');px.user=null;px.loaded=false;
 for(const prefix of ['ew-personal-v1:','ew-life-birth-v1:','ew-western-birth-v1:','ew-life-charts-v1:','ew-map-exploration-v1:','ew-time-bank-v2:']){
  try{localStorage.removeItem(prefix+owner);}catch{ok=false;}
 }
 psBroadcastIdentity();
 return ok;
}
function acStopAI(){
 if(typeof px!=='undefined'){px.privacyRun=(px.privacyRun||0)+1;px.aiRun=(px.aiRun||0)+1;px.aiController?.abort?.();px.aiPending=null;px.aiRetry=null;px.aiLive=null;}
 state.ssAiContext=null;
}
function acDescription(){
 return acText('Closing this account disables sign-in and revokes all its sessions. Personal server records and saved AI snapshots are cleared. Orders, payments, fulfilment, public works and community messages are retained. Provider and backup deletion are pending confirmation. Third-party subscriptions must be cancelled separately.',
 '关闭后将停用账号并撤销全部登录会话，清理本人服务端个人记录与已保存AI快照。订单、支付、履约、公开作品与社群消息保留；供应商及备份删除仍待确认。第三方订阅需另行取消。',
 '關閉後將停用帳號並撤銷全部登入會話，清理本人伺服器個人記錄與已保存AI快照。訂單、支付、履約、公開作品與社群訊息保留；供應商及備份刪除仍待確認。第三方訂閱需另行取消。',
 'རྩིས་ཐོ་སྒོ་བརྒྱབ་ནས་ཐོ་འཇུག་ཆ་ཚང་ཕྱིར་འབུད། རང་གི་ཟིན་ཐོ་དང་AI ཉར་བ་སུབ། ཉོ་ཐོ་དང་རིན་བསྡུའི་ཐོ་འགོད་ཉར། ཕྱི་ཕྱོགས་ཀྱི་འཁོར་རིན་སོ་སོར་བཀག་དགོས།')+' '+pdClosureDisclosure();
}
function acSheet(stage='password'){
 const token=psToken();if(!px.user||token.scope!==px.user.id)return;
 acRuntime.stage=stage;acRuntime.actor=token;
 const second=stage==='confirm';
 sheet(acText('Close this account','关闭本账号','關閉本帳號','རྩིས་ཐོ་འདི་སྒོ་རྒྱག'),`<form id="account-closure-form" data-stage="${stage}" data-run="${acRuntime.run}"><p>${acDescription()}</p><div id="account-closure-renewals"></div>${second?`<p class="ac-warning">${acText('Password verified. Confirm once more to disable this account. This cannot be undone here.','密码已核验。请再次明确确认停用本账号，此处无法恢复。','密碼已核驗。請再次明確確認停用本帳號，此處無法恢復。','གསང་ཨང་བདེན་དཔང་ཟིན། རྩིས་ཐོ་སྒོ་རྒྱག་པ་སླར་ངོས་ལེན་གནང་།')}</p><label class="ac-ack"><input name="confirmed" type="checkbox" required>${acText('Disable this account and revoke all sessions','确认停用账号并撤销全部会话','確認停用帳號並撤銷全部會話','རྩིས་ཐོ་དང་ཐོ་འཇུག་ཆ་ཚང་ཕྱིར་འབུད།')}</label>`:`<label>${acText('Current password','本人当前密码','本人目前密碼','ད་ལྟའི་གསང་ཨང་།')}<input class="input" type="password" name="password" maxlength="128" autocomplete="current-password" required></label>`}<label class="ac-ack"><input name="renewalAcknowledged" type="checkbox" required>${acText('I understand third-party renewals are not cancelled','我已了解第三方续费不会自动取消','我已了解第三方續費不會自動取消','ཕྱི་ཕྱོགས་འཁོར་རིན་རང་འགུལ་མི་བཀག་པ་ཤེས་ཡོད།')}</label><p id="account-closure-error" class="error" role="alert"></p><button class="btn full" ${acRuntime.busy?'disabled':''}>${second?acText('Confirm account closure','再次确认关闭','再次確認關閉','སྒོ་རྒྱག་པ་ངོས་ལེན།'):acText('Verify password and continue','验证密码并继续','驗證密碼並繼續','གསང་ཨང་བདེན་དཔང་བྱས་ནས་མུ་མཐུད།')}</button></form>`,button(acText('Cancel','取消','取消','ཕྱིར་འཐེན།'),'close-sheet','','secondary full'));
 const run=acRuntime.run,form=document.getElementById('account-closure-form');
 Promise.all([pxApi('account-closure/status'),pxApi('membership/status')]).then(([s,m])=>{
  if(!acCurrent(token,run)||document.getElementById('account-closure-form')!==form)return;
  if(!s.canClose){form.querySelector('button').disabled=true;form.querySelector('#account-closure-error').textContent=acText('Transfer administration before closing the last active administrator.','这是最后一个有效管理员，请先移交管理权限。','這是最後一個有效管理員，請先移交管理權限。','དོ་དམ་པ་མཐའ་མ་སྒོ་མ་བརྒྱབ་གོང་དབང་ཆ་སྤྲོད་དགོས།');}
  const renewals=form.querySelector('#account-closure-renewals');renewals.className='ml-closure-reminder';renewals.dataset.mlRenewalState='ready';renewals.innerHTML=mlRenewalReminder(m);
 }).catch(e=>{if(acCurrent(token,run)&&document.getElementById('account-closure-form')===form){form.querySelector('button').disabled=true;form.querySelector('#account-closure-error').textContent=e.message;}});
}
const acOldSheet=privacyRequestSheet;
privacyRequestSheet=function(kind,local=false){
 if(kind!=='close-account'||local)return acOldSheet(kind,local);
 acRuntime.run++;acRuntime.busy=false;acRuntime.challenge=null;
 acRuntime.nonce=Array.from(crypto.getRandomValues(new Uint8Array(32))).map(n=>n.toString(16).padStart(2,'0')).join('');
 acRuntime.requestId=crypto.randomUUID();acSheet();
};
const acOldLabel=privacyKindLabel;
privacyKindLabel=function(kind){return kind==='close-account'?acText('Close this account','关闭本账号','關閉本帳號','རྩིས་ཐོ་སྒོ་རྒྱག'):acOldLabel(kind);};
document.addEventListener('submit',async e=>{
 const form=e.target;if(form?.id!=='account-closure-form')return;e.preventDefault();
 const token=acRuntime.actor,run=Number(form.dataset.run);
 if(!token||!acCurrent(token,run)||acRuntime.busy)return;
 const values=new FormData(form);if(values.get('renewalAcknowledged')!=='on')return;
 acRuntime.busy=true;form.querySelector('button').disabled=true;
 try{
  if(form.dataset.stage==='password'){
   const password=String(values.get('password')||'');form.elements.password.value='';
   const d=await pxApi('account-closure/prepare',{requestId:acRuntime.requestId,nonce:acRuntime.nonce,password});
   if(!acCurrent(token,run)||document.getElementById('account-closure-form')!==form)return;
   acRuntime.challenge=d.challengeId;acRuntime.busy=false;acSheet('confirm');
  }else{
   if(values.get('confirmed')!=='on')return;
   const d=await pxApi('account-closure/confirm',{requestId:acRuntime.requestId,nonce:acRuntime.nonce,challengeId:acRuntime.challenge,confirmed:true,renewalAcknowledged:true});
   if(!psCurrent(token)||px.user?.id!==token.scope)return;
   if(d.receipt?.accountClosed!==true)throw Error('Account closure was not confirmed');
   acStopAI();const localCleared=acEraseLocal(token.scope);
   acRuntime.receipt={id:d.receipt.id,closedAt:d.receipt.closedAt,localBrowserCleared:localCleared,domainCleanup:d.receipt.domainCleanup||null};acRuntime.run++;acRuntime.nonce='';acRuntime.challenge=null;
   closeSheet();navigate('accountClosureReceipt');
  }
 }catch(err){if(acCurrent(token,run)&&document.getElementById('account-closure-form')===form)form.querySelector('#account-closure-error').textContent=err.message||String(err);}
 finally{if(run===acRuntime.run){acRuntime.busy=false;if(document.getElementById('account-closure-form')===form)form.querySelector('button').disabled=false;}}
});
screens.accountClosureReceipt=()=>!acRuntime.receipt?`<section class="page"><p>${acText('No closure receipt is loaded. Sign in to check your account.','当前没有注销回执，请登录查看账号状态。','目前沒有註銷回執，請登入查看帳號狀態。','སྒོ་རྒྱག་པའི་འབྱོར་འཛིན་མེད།')}</p></section>`:`<section class="page ac-page">${pxTop(acText('Account closed','账号已关闭','帳號已關閉','རྩིས་ཐོ་སྒོ་བརྒྱབ་ཟིན།'),'','account')}<article class="card"><p>${acText('Sign-in is disabled and all sessions were revoked.','账号已停用，全部登录会话已撤销。','帳號已停用，全部登入會話已撤銷。','ཐོ་འཇུག་སྒོ་བཀག་ནས་ཐོ་འཇུག་ཆ་ཚང་ཕྱིར་འབུད་ཟིན།')}</p><p>${acDescription()}</p>${pdClosureReceiptFragment(acRuntime.receipt.domainCleanup)}<p>${acRuntime.receipt?.localBrowserCleared?acText('This account’s known local copies on this device were cleared.','本账号在此设备的已知本机副本已清理。','本帳號在此裝置的已知本機副本已清理。','རང་སའི་འདྲ་བཤུས་གཙང་བཟོ་ཟིན།'):acText('Local browser deletion was not confirmed. Clear this account’s device copies separately.','本机副本清理未确认，请另行清除此账号在设备上的副本。','本機副本清理未確認，請另行清除此帳號在裝置上的副本。','རང་སའི་སུབ་པ་ངོས་ལེན་མ་བྱས།')}</p><button class="btn full" data-go="account">${acText('Sign in with another account','使用其他账号登录','使用其他帳號登入','རྩིས་ཐོ་གཞན་གྱིས་ཐོ་འཇུག')}</button></article></section>`;
window.addEventListener('storage',event=>{
 if(!event.key?.startsWith('ew-account-closed-v1:')||!event.newValue)return;
 const owner=event.key.slice('ew-account-closed-v1:'.length);
 if(personalStorage.scope===owner){acRuntime.run++;acStopAI();acEraseLocal(owner);navigate('account');}
});
