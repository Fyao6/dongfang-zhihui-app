// Privacy controls read only the current account's state. Exports stay in this browser.
const prText=(en,zh,hant,bo)=>flText(en,zh,hant,bo);
let privacyRuntime={scope:null,epoch:-1,status:'idle',data:null,requests:[],error:'',busy:false};
function privacyState(){const token=psToken();if(privacyRuntime.scope!==token.scope||privacyRuntime.epoch!==token.epoch)privacyRuntime={scope:token.scope,epoch:token.epoch,status:'idle',data:null,requests:[],error:'',busy:false};return privacyRuntime;}
function privacySignedIn(){const token=psToken();return !!(px.user?.id&&px.user.id===token.scope);}
function privacyTitle(){return prText('Privacy & AI settings','隐私与AI设置','隱私與AI設定','གསང་བ་དང་AI སྒྲིག་འགོད།');}
const privacyConsentLabels=()=>[
 ['chart',prText('Use selected chart data for AI','允许AI使用本次选定命盘资料','允許AI使用本次選定命盤資料','AI ལ་བདམས་པའི་རྩིས་གཞི་སྤྱོད་པ།')],
 ['wellbeing',prText('Use selected body or emotion records for AI','允许AI使用本次选定身体或情绪记录','允許AI使用本次選定身體或情緒記錄','AI ལ་ལུས་སེམས་ཀྱི་ཟིན་ཐོ་སྤྱོད་པ།')],
 ['saveConversations',prText('Save new AI conversations','保存新的AI会话','儲存新的AI對話','AI གླེང་མོལ་གསར་པ་ཉར་བ།')],
 ['longTermMemory',prText('Long-term memory','长期记忆','長期記憶','ཡུན་རིང་དྲན་ཐོ།')],
 ['trainingImprovement',prText('Separate permission for training or improvement','允许另行说明的训练或改进用途','允許另行說明的訓練或改進用途','སློབ་སྦྱོང་དང་ལེགས་བཅོས་ལ་ཆོག་མཆན།')],
 ['marketing',prText('Receive marketing messages','接收营销信息','接收行銷資訊','ཚོང་འཕྲིན་ལེན་པ།')]
];
function privacyError(error){return error?.status?ewI18n.error(error.message,state.lang):prText('Unable to connect. Check the service and retry.','暂时无法连接，请检查服务后重试。','暫時無法連線，請檢查服務後重試。','སྦྲེལ་མཐུད་མ་ཐུབ། ཡང་བསྐྱར་ཚོད་ལྟ་བྱོས།');}
async function privacyLoad(force=false){
 const token=psToken(),runtime=privacyState();if(!privacySignedIn()||runtime.busy||runtime.status==='loading'||runtime.status==='ready'&&!force)return false;
 runtime.status='loading';runtime.error='';if(state.page==='privacyCenter')render(false);
 try{const [data,requests]=await Promise.all([pxApi('privacy/preferences'),pxApi('privacy/requests')]);if(!psCurrent(token)||privacyState()!==runtime)return false;runtime.data=data;runtime.requests=requests.items||[];runtime.status='ready';return true;}
 catch(error){if(psCurrent(token)&&privacyState()===runtime){runtime.status='error';runtime.error=privacyError(error);}return false;}
 finally{if(psCurrent(token)&&privacyState()===runtime&&state.page==='privacyCenter')render(false);}
}
function privacyStatusLabel(status){return ({completed:prText('Completed','已完成','已完成','ལེགས་གྲུབ།'),'pending-review':prText('Awaiting review','待处理确认','待處理確認','ཞིབ་བཤེར་སྒུག་པ།'),'pending-provider':prText('Awaiting provider confirmation','待供应商确认','待供應商確認','མཁོ་འདོན་པའི་ངོས་ལེན་སྒུག་པ།'),'pending-backup':prText('Awaiting backup cleanup confirmation','待备份清理确认','待備份清理確認','གྲབས་ཉར་གཙང་བཟོའི་ངོས་ལེན་སྒུག་པ།')})[status]||status;}
function privacyKindLabel(kind){return ({'delete-memory':prText('Clear long-term memory','清除长期记忆','清除長期記憶','ཡུན་རིང་དྲན་ཐོ་གཙང་བཟོ།'),'delete-conversations':prText('Delete saved AI conversations','删除已保存AI会话','刪除已儲存AI對話','ཉར་བའི་AI གླེང་མོལ་སུབ་པ།'),'delete-records':prText('Delete personal records','删除个人记录','刪除個人記錄','སྒེར་གྱི་ཟིན་ཐོ་སུབ་པ།'),'close-account':prText('Request account closure','申请注销账号','申請註銷帳號','རྩིས་ཐོ་སྒོ་རྒྱག་རེ་ཞུ།')})[kind]||kind;}
function privacyCenter(){
 const runtime=privacyState(),signed=privacySignedIn(),top=pxTop(privacyTitle(),'','profileSettings');
 const localNote=prText('Birth details, charts and notes saved on this device are separate from server data. Exporting them here never uploads them.','本机生辰、命盘与笔记和服务端资料分别保存；在这里合并导出不会上传本机资料。','本機生辰、命盤與筆記和伺服器資料分別儲存；在此合併匯出不會上傳本機資料。','འཕྲུལ་ཆས་ཀྱི་སྐྱེས་གཞི་དང་ཟིན་ཐོ་ཞབས་ཞུའི་གཞི་གྲངས་དང་སོ་སོར་ཉར། ཕྱིར་འདོན་གྱིས་དེ་དག་ཡར་མི་སྐྱེལ།');
 if(!signed)return `<section class="page pr-page">${top}<p>${prText('Sign in to manage this account’s permissions and server data.','登录后管理本人账号授权与服务端资料。','登入後管理本人帳號授權與伺服器資料。','རང་གི་རྩིས་ཐོའི་ཆོག་མཆན་དོ་དམ་ལ་ཐོ་འཇུག་བྱོས།')}</p>${go(prText('Sign in','登录账号','登入帳號','ཐོ་འཇུག'), 'account','btn full')}<p>${localNote}</p>${privacyLocalTools()}</section>`;
 if(runtime.status==='idle')queueMicrotask(()=>privacyLoad());
 if(runtime.status!=='ready')return `<section class="page pr-page">${top}<p role="status">${esc(runtime.error||prText('Loading your settings…','正在读取本人设置…','正在讀取本人設定…','རང་གི་སྒྲིག་འགོད་ལེན་བཞིན་པ།'))}</p>${runtime.status==='error'?`<button class="btn secondary" data-action="privacy-retry">${prText('Retry','重试','重試','ཡང་བསྐྱར།')}</button>`:''}<p>${localNote}</p>${privacyLocalTools()}</section>`;
 const data=runtime.data,cfg=data.disclosure,p=data.consents,unknown=prText('Not yet confirmed','尚未确认','尚未確認','ད་དུང་ངོས་མ་ལེན།');
 const consentDisabled=key=>(key==='longTermMemory'&&!cfg.memoryAvailable)||(['trainingImprovement','marketing'].includes(key)&&!cfg.purposeDetails?.[key]&&!p[key])||!cfg.configured&&!p[key];
 const bindingNotice=!cfg.configured?`<p class="pr-note" role="status">${prText('The server’s actual provider, endpoint, model, processing regions and policy version are not fully matched. AI sending and new permissions remain blocked.','服务端实际供应商、端点、模型、地区与政策版本尚未完整匹配，已阻止AI发送与新增授权。','伺服器實際供應商、端點、模型、地區與政策版本尚未完整匹配，已阻止AI傳送與新增授權。','ཞབས་ཞུའི་མཁོ་འདོན་པ་དང་དཔེ་གཞི་དང་ས་ཁུལ་དང་སྲིད་ཇུས་ཆ་ཚང་མ་མཐུན་པས་AI ལ་གཏོང་བ་བཀག་ཡོད།')}</p>`:'';
 const recipients=(cfg.recipients||[]).map(r=>`<li><b>${esc(r.name)}</b><span>${esc(r.regions.join(' / '))}</span><p>${esc(r.purpose)}</p><a href="${esc(r.policyUrl)}" target="_blank" rel="noopener noreferrer">${prText('Provider policy','接收方政策','接收方政策','མཁོ་འདོན་པའི་སྲིད་ཇུས།')}</a></li>`).join('');
 return `<section class="page pr-page">${top}<section class="pr-section"><h2>${prText('Where AI data goes','AI资料如何处理','AI資料如何處理','AI གཞི་གྲངས་ཇི་ལྟར་བཀོལ་སྤྱོད།')}</h2><p>${prText('Ordinary chat does not attach your profile, chart, health records, private messages or shopping details. Permissions below are separate.','普通聊天不会自动附上个人档案、命盘、身体记录、私信或购物资料；下列授权分别控制。','一般聊天不會自動附上個人檔案、命盤、身體記錄、私訊或購物資料；以下授權分別控制。','སྤྱིར་བཏང་གླེང་མོལ་ལ་སྒེར་གྱི་ཡིག་ཚགས་དང་ལུས་སེམས་ཀྱི་ཟིན་ཐོ་རང་འགུལ་མི་སྦྱར།')}</p><dl><dt>${prText('Controller','处理主体','處理主體','དོ་དམ་ཚོགས་པ།')}</dt><dd>${esc(cfg.controllerName||unknown)}</dd><dt>${prText('Policy version','政策版本','政策版本','སྲིད་ཇུས་ཐོན་རིམ།')}</dt><dd>${esc(cfg.policyVersion||unknown)}</dd><dt>${prText('Contact','联系路径','聯絡途徑','འབྲེལ་གཏུག')}</dt><dd>${esc(cfg.contact||unknown)}</dd></dl>${recipients?`<ul class="pr-recipients">${recipients}</ul>`:`<p class="pr-note">${prText('Recipients and processing regions are unconfirmed. External AI sending is blocked.','接收方与处理地区尚未确认，已阻止向外部AI发送资料。','接收方與處理地區尚未確認，已阻止向外部AI傳送資料。','ལེན་མཁན་དང་ས་ཁུལ་ངོས་མ་ལེན་པས་ཕྱིར་གཞི་གྲངས་གཏོང་བ་བཀག་ཡོད།')}</p>`}</section>
 <form id="privacy-preferences-form" class="pr-section"><h2>${prText('Separate permissions','分项授权','分項授權','སོ་སོའི་ཆོག་མཆན།')}</h2>${bindingNotice}${privacyConsentLabels().map(([key,label])=>`<label class="pr-toggle"><span>${label}${cfg.purposeDetails?.[key]?`<small class="pr-note">${esc(cfg.purposeDetails[key])}</small>`:''}</span><input type="checkbox" name="${key}" ${p[key]?'checked':''} ${consentDisabled(key)?'disabled':''}></label>`).join('')}<p class="pr-note">${prText('Memory starts off. Choose entries for each AI request. Saving conversations is separate; switching it off does not erase existing conversations. Training and marketing are off by default.','长期记忆默认关闭。每次发送需选择条目。会话保存独立控制，关闭不会自动删除已有会话。训练改进与营销默认关闭。','長期記憶預設關閉。每次傳送需選擇條目。對話儲存獨立控制，關閉不會自動刪除既有對話。訓練改進與行銷預設關閉。','ཡུན་རིང་དྲན་ཐོ་སྔོན་ཚུད་སྒོ་རྒྱག རེ་ཞུ་རེར་བདམས་དགོས། གླེང་མོལ་ཉར་བ་སོ་སོར་བདམས་ཆོག སྒོ་བརྒྱབ་ཀྱང་སྔར་གྱི་ཟིན་ཐོ་རང་འགུལ་མི་སུབ།')}</p><label class="pr-ack"><input type="checkbox" name="acknowledged" ${data.policyAcknowledged?'checked':''} ${!cfg.configured?'disabled':''}><span>${prText('I have read the purposes, data categories, recipients and regions for this policy version.','我已阅读本版本的处理目的、资料类别、接收方与处理地区。','我已閱讀本版本的處理目的、資料類別、接收方與處理地區。','ཐོན་རིམ་འདིའི་དམིགས་ཡུལ་དང་གཞི་གྲངས་རིགས་དང་ལེན་མཁན་དང་ས་ཁུལ་བཀླགས་ཟིན།')}</span></label><button class="btn full" ${runtime.busy?'disabled':''}>${prText('Save permissions','保存授权设置','儲存授權設定','ཆོག་མཆན་ཉར་བ།')}</button></form>
 <section class="pr-section"><h2>${prText('Retention and deletion','保存期限与删除','儲存期限與刪除','ཉར་ཡུན་དང་སུབ་པ།')}</h2><dl>${[['recordsDays',prText('Records','个人记录','個人記錄','སྒེར་ཟིན།')],['conversationsDays',prText('Conversations','会话','對話','གླེང་མོལ།')],['backupDays',prText('Backup cleanup','备份清理','備份清理','གྲབས་ཉར་གཙང་བཟོ།')],['financeDays',prText('Financial retention','财务保留','財務保留','དངུལ་རྩིས་ཉར་ཡུན།')]].map(([key,label])=>`<dt>${label}</dt><dd>${cfg.retention[key]===null?unknown:cfg.retention[key]+' '+prText('days','天','天','ཉིན།')}</dd>`).join('')}</dl><p>${prText('Unconfirmed periods are shown as unconfirmed. Local deletion does not prove backups or a provider have deleted their copies.','尚未确认的期限如实列明；本地删除不代表备份或受托服务商已完成删除。','尚未確認的期限如實列明；本地刪除不代表備份或受託服務商已完成刪除。','ཉར་ཡུན་ངོས་མ་ལེན་པ་གསལ་བཤད་བྱེད། རང་སར་སུབ་པས་གྲབས་ཉར་དང་ཕྱིའི་ཞབས་ཞུའི་མཁོ་འདོན་པས་སུབ་ཟིན་པ་མི་མཚོན།')}</p><label class="pr-ack"><input id="privacy-export-local" type="checkbox"><span>${prText('Include this account’s local birth details, charts, notes and AI chats in the downloaded export','下载时合并本人本机生辰、命盘、笔记与AI聊天','下載時合併本人本機生辰、命盤、筆記與AI聊天','ཕྱིར་འདོན་ཡིག་ཆར་རང་གི་འཕྲུལ་ཆས་ཀྱི་སྐྱེས་གཞི་དང་ཟིན་ཐོ་མཉམ་བསྡུ།')}</span></label><button class="btn secondary full" data-action="privacy-export" ${runtime.busy?'disabled':''}>${prText('Export my data','导出本人资料','匯出本人資料','རང་གི་གཞི་གྲངས་ཕྱིར་འདོན།')}</button><div class="pr-actions">${['delete-conversations','delete-records','delete-memory','close-account'].map(kind=>`<button class="menu-button" data-action="privacy-request-open" data-kind="${kind}" ${runtime.busy?'disabled':''}>${privacyKindLabel(kind)}${icon('arrow')}</button>`).join('')}</div></section>
 <section class="pr-section"><h2>${prText('Processing status','处理状态','處理狀態','སྒྲུབ་བཞིན་གནས་ཚུལ།')}</h2>${runtime.requests.length?runtime.requests.map(r=>`<article class="pr-request"><b>${privacyKindLabel(r.kind)}</b><span>${privacyStatusLabel(r.status)}</span><small>${esc(new Date(r.createdAt).toISOString())}</small><p>${r.details.local.status==='completed'?prText('Current server records cleared. Backup and provider confirmation are tracked separately.','当前服务端对应记录已清理；备份及供应商确认另行跟踪。','目前伺服器對應記錄已清理；備份及供應商確認另行追蹤。','ཞབས་ཞུའི་ཟིན་ཐོ་གཙང་བཟོ་ཟིན། གྲབས་ཉར་དང་མཁོ་འདོན་པའི་ངོས་ལེན་སོ་སོར་རྗེས་འདེད།'):r.kind==='close-account'?prText('Closure is awaiting processing. Your account has not been closed and third-party renewals have not been cancelled.','注销申请待处理；账号尚未关闭，第三方续费未取消。','註銷申請待處理；帳號尚未關閉，第三方續費未取消。','རྩིས་ཐོ་སྒོ་རྒྱག་རེ་ཞུ་སྒྲུབ་བཞིན་ཡིན། ད་ལྟ་རྩིས་ཐོ་སྒོ་བརྒྱབ་མེད།'):prText('This historical request has no verified completion record. Check its processing status.','此历史申请未记录已核实完成，请查看其处理状态。','此歷史申請未記錄已核實完成，請查看其處理狀態。','སྔར་གྱི་རེ་ཞུ་འདི་གྲུབ་པ་མ་ངེས། སྒྲུབ་ཚུལ་ལྟ་རོགས།')}</p></article>`).join(''):`<p>${prText('No processing requests yet.','暂无处理申请。','尚無處理申請。','རེ་ཞུ་མེད།')}</p>`}</section><p>${localNote}</p>${privacyLocalTools()}${rtLink()}${pdLink()}${runtime.error?`<p class="error" role="alert">${esc(runtime.error)}</p>`:''}</section>`;
}
function privacyLocalTools(){return `<section class="pr-section"><h2>${prText('This device only','仅此设备','僅此裝置','འཕྲུལ་ཆས་འདི་ཁོ་ན།')}</h2><p>${prText('These actions affect only the current account’s local copy. Server data and third-party services are handled separately.','以下操作只处理当前账号的本机副本；服务端和第三方资料需另行处理。','以下操作僅處理目前帳號的本機副本；伺服器和第三方資料需另行處理。','འདིས་ད་ལྟའི་རྩིས་ཐོའི་རང་སའི་འདྲ་བཤུས་ཁོ་ན་སྒྲུབ།')}</p><button class="btn secondary full" data-action="privacy-local-export">${prText('Export this device’s copy','导出本机副本','匯出本機副本','རང་སའི་འདྲ་བཤུས་ཕྱིར་འདོན།')}</button><button class="menu-button" data-action="privacy-local-open" data-kind="conversations">${prText('Clear AI chats on this device','清除本机AI聊天','清除本機AI聊天','རང་སའི་AI གླེང་མོལ་གཙང་བཟོ།')}${icon('arrow')}</button><button class="menu-button" data-action="privacy-local-open" data-kind="records">${prText('Clear my local birth details and records','清除本机生辰与个人记录','清除本機生辰與個人記錄','རང་སའི་སྐྱེས་གཞི་དང་ཟིན་ཐོ་གཙང་བཟོ།')}${icon('arrow')}</button></section>`;}
function privacyLocalExport(token){
 if(!psCurrent(token))throw Error('Account changed');
 const snapshot=psClone(psSnapshot()),support=snapshot.support||{};
 // Do not export other people's private messages, contact lists or account credentials.
 snapshot.support={ai:support.ai||[],profile:{name:support.profile?.name||''}};
 const scoped={};for(const prefix of ['ew-life-birth-v1:','ew-western-birth-v1:','ew-life-charts-v1:','ew-map-exploration-v1:','ew-time-bank-v2:']){
  const raw=localStorage.getItem(prefix+token.scope);if(raw!==null){try{scoped[prefix]=JSON.parse(raw);}catch{scoped[prefix]={unreadable:true};}}
 }
 return {accountId:token.scope,exportedAt:new Date().toISOString(),personal:snapshot,scopedRecords:scoped,excluded:'other-users-private-messages'};
}
function privacyDownload(data,token){if(!psCurrent(token))return;const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='eastern-wisdom-privacy-'+new Date().toISOString().slice(0,10)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function privacyClearLocal(kind,token){
 if(!psCurrent(token))return false;
 if(kind==='conversations'){window.ewPrivacyExplicitErase=token.scope;try{if(!psCommit(()=>{state.support.ai=[];}))return false;}finally{window.ewPrivacyExplicitErase=null;}state.ssAiContext=null;return true;}
 if(kind!=='records')return false;
 const prefixes=['ew-life-birth-v1:','ew-western-birth-v1:','ew-life-charts-v1:','ew-map-exploration-v1:','ew-time-bank-v2:'],backup=prefixes.map(p=>[p+token.scope,localStorage.getItem(p+token.scope)]);
 try{
  for(const [key] of backup){if(!psCurrent(token))return false;localStorage.removeItem(key);}
  if(!psCommit(()=>{state.wellness=defaultWellness();state.daily={checkins:{},draws:{},favorites:[],musicSessions:[]};state.lifeNotes=null;state.journal='';state.answers={};state.hasAnswers=false;state.completed=false;state.checkedIn=false;}))throw Error('save');
  if(typeof lcRuntime!=='undefined'){lcRuntime.pages=Object.create(null);lcRuntime.scope='';}if(typeof lbRuntime!=='undefined')lbRuntime.scope='';if(typeof lwpRuntime!=='undefined')lwpRuntime.scope='';
  if(typeof timeBank!=='undefined'){timeBank.runs=[];timeBank.lastSeen=Date.now();if(typeof tbBackend!=='undefined'){tbBackend.connected=false;tbBackend.serverAt=0;}tbSave();tbLocalHeartbeat();}
  state.ssAiContext=null;return true;
 }catch{if(psCurrent(token))for(const [key,value] of backup)try{value===null?localStorage.removeItem(key):localStorage.setItem(key,value);}catch{}return false;}
}
function privacyRequestSheet(kind,local=false){
 if(!['delete-memory','delete-conversations','delete-records','close-account','conversations','records'].includes(kind))return;
 const close=kind==='close-account',requestId=crypto.randomUUID();
 const explanation=local?prText('Only this account’s copy on this device will be cleared. Other accounts are preserved. Server data can return when reconnected. This cannot be undone.','仅清除当前账号在此设备的副本，其他账号保留；重连后服务端资料可能重新出现，此操作不可撤销。','僅清除目前帳號在此裝置的副本，其他帳號保留；重新連線後伺服器資料可能再次出現，此操作無法復原。','རྩིས་ཐོ་འདིའི་རང་སའི་འདྲ་བཤུས་ཁོ་ན་སུབ། རྩིས་ཐོ་གཞན་མི་སུབ། སྦྲེལ་མཐུད་བསྐྱར་བྱས་ཚེ་ཞབས་ཞུའི་གཞི་གྲངས་སླར་འབྱུང་སྲིད།'):close?prText('This submits a real closure request and immediately withdraws AI permissions. Your account stays open until processing is verified. Apple, Google and other third-party renewals must be cancelled separately.','这会提交真实注销申请并立即撤回AI授权；核实处理前账号仍开放。Apple、Google及其他第三方续费需另行取消。','此操作會提交真實註銷申請並立即撤回AI授權；核實處理前帳號仍開放。Apple、Google及其他第三方續費需另行取消。','རྩིས་ཐོ་སྒོ་རྒྱག་རེ་ཞུ་བསྐྱལ་ནས་AI ཆོག་མཆན་ཕྱིར་ལེན། ཞིབ་བཤེར་མ་ཚར་བར་རྩིས་ཐོ་སྒོ་མི་རྒྱག ཕྱི་ཕྱོགས་ཀྱི་རིན་བསྡུ་སོ་སོར་བཀག་དགོས།'):prText('Current server copies will be cleared for this category. Provider and backup copies remain pending until verified. This device’s copy is separate.','将清理当前服务端对应资料；供应商与备份删除须等待核实，本机副本另行处理。','將清理目前伺服器對應資料；供應商與備份刪除須等待核實，本機副本另行處理。','ཞབས་ཞུའི་གཞི་གྲངས་སུབ། མཁོ་འདོན་པ་དང་གྲབས་ཉར་གྱི་སུབ་པའི་ངོས་ལེན་སྒུག་དགོས།');
 sheet(local?prText('Confirm local deletion','确认清除本机副本','確認清除本機副本','རང་སར་སུབ་པ་ངོས་ལེན།'):privacyKindLabel(kind),`<form id="privacy-request-form" data-kind="${kind}" data-local="${local}" data-request-id="${requestId}"><p>${explanation}</p>${close?`<label>${prText('Your current password','本人当前密码','本人目前密碼','རང་གི་གསང་ཨང་།')}<input class="input" type="password" name="password" autocomplete="current-password" maxlength="128" required></label><label class="pr-ack"><input name="renewalAcknowledged" type="checkbox" required><span>${prText('I understand third-party renewals are not cancelled by this request.','我已了解本申请不会自动取消第三方续费。','我已了解本申請不會自動取消第三方續費。','རེ་ཞུ་འདིས་ཕྱིའི་རིན་བསྡུ་རང་འགུལ་མི་བཀག་པ་ཤེས་ཡོད།')}</span></label>`:''}<p class="error" id="privacy-request-error" role="alert"></p><button class="btn full">${prText('Confirm','确认操作','確認操作','ངོས་ལེན།')}</button></form>`,button(prText('Cancel','取消','取消','ཕྱིར་འཐེན།'),'close-sheet','','secondary full'));
}
async function privacyBeforeAI(context=null){
 const token=psToken();if(!privacySignedIn())throw Error(prText('Sign in first.','请先登录账号。','請先登入帳號。','སྔོན་ལ་ཐོ་འཇུག་བྱོས།'));
 const data=await pxApi('privacy/preferences');if(!psCurrent(token))throw Error('Account changed');privacyState().data=data;
 if(!data.policyAcknowledged||!data.disclosure.configured){navigate('privacyCenter');throw Error(prText('Confirm the current privacy disclosure first.','请先确认当前隐私说明。','請先確認目前隱私說明。','སྔོན་ལ་གསང་བའི་གསལ་བཤད་ངོས་ལེན་བྱོས།'));}
 if(context&&['chart','wellbeing'].includes(context.category)&&!data.consents[context.category]){navigate('privacyCenter');throw Error(prText('Grant the specific record permission first.','请先单独授权这类资料。','請先單獨授權此類資料。','གཞི་གྲངས་རིགས་འདི་ལ་ཆོག་མཆན་སོ་སོར་གནང་རོགས།'));}
 return {context,consentEpoch:data.consentEpoch,policyVersion:data.disclosure.policyVersion,providerId:data.disclosure.activeAI.providerId,providerBinding:data.disclosure.providerBinding,authorizedCategories:data.authorizedCategories||[],accountId:token.scope};
}
function privacyAIHistory(messages,authorization,token=psToken(),memorySelection=null){
 if(!psCurrent(token)||authorization?.accountId!==token.scope||!Array.isArray(messages))return [];
 return messages.filter(message=>{
  const tag=message?.privacy;if(!tag||tag.accountId!==token.scope||tag.consentEpoch!==authorization.consentEpoch||tag.providerId!==authorization.providerId||tag.providerBinding!==authorization.providerBinding||tag.policyVersion!==authorization.policyVersion||!['user','assistant','report'].includes(tag.source)||!authorization.authorizedCategories.includes(tag.category)||tag.source==='report'&&tag.category==='general')return false;
  if(tag.memorySelection&&(!memorySelection||JSON.stringify(tag.memorySelection)!==JSON.stringify(memorySelection)))return false;
  return ['user','assistant'].includes(message.role)&&typeof (message.content??message.text)==='string'&&(message.content??message.text).trim();
 }).slice(-12).map(message=>({role:message.role,content:message.content??message.text,privacy:{...message.privacy}}));
}
function privacyConversationSaveAllowed(){const runtime=privacyState();return !!(privacySignedIn()&&runtime.data?.policyAcknowledged&&runtime.data.consents.saveConversations);}
function privacyConversationForStorage(current){
 if(!window.ewPrivacyReady||window.ewPrivacyExplicitErase===personalStorage.scope||privacyConversationSaveAllowed())return current;
 // Preserve an existing saved conversation; disabling saving must not delete it.
 const token=psToken();if(!token.scope)return [];
 const saved=psRead(psKey(token.scope));return saved?.scope===token.scope&&Array.isArray(saved.data?.support?.ai)?psClone(saved.data.support.ai):[];
}
window.ewPrivacyReady=true;
screens.privacyCenter=privacyCenter;
document.addEventListener('click',async event=>{
 const control=event.target.closest('[data-action^="privacy-"]');if(!control)return;event.preventDefault();event.stopImmediatePropagation();
 const action=control.dataset.action,token=psToken(),runtime=privacyState();if(runtime.busy)return;
 if(action==='privacy-retry')return privacyLoad(true);
 if(action==='privacy-request-open')return privacyRequestSheet(control.dataset.kind);
 if(action==='privacy-local-open')return privacyRequestSheet(control.dataset.kind,true);
 if(action==='privacy-local-export'){try{privacyDownload({schemaVersion:1,localData:privacyLocalExport(token)},token);}catch{toast(prText('Local export failed.','本机导出失败。','本機匯出失敗。','རང་སའི་ཕྱིར་འདོན་མ་ཐུབ།'));}return;}
 if(action==='privacy-export'){
  const include=document.getElementById('privacy-export-local')?.checked;runtime.busy=true;runtime.error='';render(false);
  try{const data=await pxApi('privacy/export');if(!psCurrent(token)||privacyState()!==runtime)return;if(include){data.localData=privacyLocalExport(token);data.localDataIncluded=true;}privacyDownload(data,token);}
  catch(error){if(psCurrent(token))runtime.error=privacyError(error);}finally{if(psCurrent(token)&&privacyState()===runtime){runtime.busy=false;if(state.page==='privacyCenter')render(false);}}
 }
},true);
document.addEventListener('submit',async event=>{
 const form=event.target;if(!['privacy-preferences-form','privacy-request-form'].includes(form.id))return;event.preventDefault();event.stopImmediatePropagation();
 const token=psToken(),runtime=privacyState();if(runtime.busy)return;const fields=new FormData(form);runtime.busy=true;runtime.error='';
 try{
  if(form.id==='privacy-preferences-form'){
   const p=runtime.data;if(!p)throw Error('No preferences');const consents=Object.fromEntries(privacyConsentLabels().map(([key])=>[key,fields.has(key)]));
   const data=await pxApi('privacy/preferences',{consents,revision:p.revision,policyVersion:p.disclosure.policyVersion,acknowledged:fields.has('acknowledged')},'PATCH');
   if(!psCurrent(token)||privacyState()!==runtime)return;runtime.data=data;
  }else if(form.dataset.local==='true'){
   if(!privacyClearLocal(form.dataset.kind,token))throw Error('Local deletion failed');if(psCurrent(token))closeSheet();
  }else{
   const kind=form.dataset.kind,body={kind,requestId:form.dataset.requestId};if(kind==='close-account'){body.password=String(fields.get('password')||'');body.renewalAcknowledged=fields.has('renewalAcknowledged');}
   if(kind==='delete-records'&&typeof rtRecordInvalidated==='function')rtRecordInvalidated(token);
   const data=await pxApi('privacy/requests',body);body.password='';if(!psCurrent(token)||privacyState()!==runtime)return;runtime.requests=[data.item,...runtime.requests.filter(r=>r.id!==data.item.id)];runtime.data=null;closeSheet();
  }
 }catch(error){if(psCurrent(token)&&privacyState()===runtime){runtime.error=privacyError(error);const box=document.getElementById('privacy-request-error');if(box)box.textContent=runtime.error;}}
 finally{const password=form.querySelector('input[type=password]');if(password)password.value='';if(psCurrent(token)&&privacyState()===runtime){runtime.busy=false;if(runtime.data===null)runtime.status='idle';if(state.page==='privacyCenter'&&!document.getElementById('sheet')?.open)render(false);}}
},true);
