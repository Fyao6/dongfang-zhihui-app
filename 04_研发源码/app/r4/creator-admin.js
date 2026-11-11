// Company-only creator administration. The service enforces every role and ownership check.
const caState={creators:[],teachers:[],works:[],selected:null,filter:'manual_review',settings:null,detailRevision:0};
const caStatuses={pending:'待入驻审核',approved:'已开通',suspended:'已暂停',rejected:'未通过',draft:'草稿',ai_review:'AI审核中',manual_review:'待人工复核',published:'已发布'};
const caTypes={video:'视频',article:'图文',course:'课程'};
function caBadge(value){return '<span class="badge '+esc(value==='manual_review'||value==='ai_review'?'pending':value)+'">'+esc(caStatuses[value]||value)+'</span>';}
function caTime(value){return value?esc(date(value)):'—';}
function caMedia(url,type='video'){
 if(!/^(https:\/\/|\/api\/media\/)/.test(url||''))return '';
 if(type==='image')return '<img class="ca-cover" src="'+esc(url)+'" alt="作品封面" loading="lazy">';
 return type==='audio'?'<audio controls preload="metadata" src="'+esc(url)+'"></audio>':'<video controls playsinline preload="metadata" src="'+esc(url)+'"></video>';
}
function caInstallStyle(){if(document.getElementById('creator-admin-style'))return;const s=document.createElement('style');s.id='creator-admin-style';s.textContent=`
.ca-intro{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.ca-flow{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:12px 0 20px}.ca-flow span{padding:9px 13px;background:#e6f1ef;border-radius:10px;font-size:12px}.ca-flow b{color:var(--muted)}.ca-detail{scroll-margin-top:20px;min-width:0}.ca-detail h2{margin-bottom:10px}.ca-detail .ca-body{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;margin:15px 0;max-height:380px;overflow:auto}.ca-detail video{display:block;max-width:100%;width:100%;max-height:360px;background:#173f44;border-radius:12px;margin:12px 0}.ca-detail audio{width:100%;margin:12px 0}.ca-cover{display:block;max-width:100%;max-height:250px;border-radius:12px;margin:12px 0}.ca-filters{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:18px}.ca-filters button{border:1px solid var(--line);background:#fff;border-radius:9px;padding:7px 12px;min-height:36px;font-size:12px}.ca-filters button[aria-pressed=true]{background:var(--ink);color:#fff;border-color:var(--ink)}.ca-review-row button{white-space:nowrap}.ca-muted{font-size:12px;color:var(--muted)}.ca-history{margin:15px 0;padding:0;list-style:none}.ca-history li{border-left:2px solid var(--line);padding:0 0 16px 14px;margin-left:4px;overflow-wrap:anywhere}.ca-history p{white-space:pre-wrap;font-size:12px;margin-top:4px}.ca-section{padding:12px 0;border-bottom:1px solid var(--line)}.ca-section:last-child{border-bottom:0}.ca-section p{white-space:pre-wrap;overflow-wrap:anywhere}.ca-note{background:#f6f2e8;padding:13px 16px;border-radius:11px;font-size:12px;color:#755e2e;margin:14px 0}.ca-statusline{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.ca-avatar{width:60px;height:60px;object-fit:cover;border-radius:15px}.ca-readonly{border-top:1px solid var(--line);padding-top:16px;margin-top:18px}.ca-loading{color:var(--muted);padding:20px 0}.ca-prose{white-space:pre-wrap;overflow-wrap:anywhere}.ca-review-note{margin-top:14px}.ca-error{white-space:pre-wrap;overflow-wrap:anywhere}.ca-empty{padding:40px 22px}.ca-safety-list{margin:10px 0;padding-left:18px;font-size:12px;color:var(--muted)}.ca-toggle{display:flex;align-items:start;gap:8px;padding:13px;border:1px solid var(--line);border-radius:11px;background:#f8fbfa}.ca-toggle input{margin-top:4px;flex-shrink:0}.ca-toggle small{display:block;font-size:11px;color:var(--muted);margin-top:4px}
@media(max-width:850px){.ca-intro{display:block}.ca-filters{gap:6px}.ca-review-grid{grid-template-columns:1fr}.ca-detail{padding:17px}.ca-flow{gap:7px}.ca-flow span{padding:7px 10px}}
`;document.head.append(s);}
async function loadCreatorAdmin(nav,seq){
 caInstallStyle();caState.selected=null;++caState.detailRevision;
 if(nav==='creators'){
  const d=await api('admin/creators');let teachers=[];
  if(state.user.role==='admin')teachers=(await api('admin/content/teachers')).items||[];
  if(seq!==state.seq)return;caState.creators=d.items||[];caState.teachers=teachers;renderCreatorList();
 }else if(nav==='creatorReviews'){
  const d=await api('admin/creator-reviews');if(seq!==state.seq)return;caState.works=d.items||[];renderCreatorReviews();
 }else if(nav==='moderation'){
  if(state.user.role!=='admin')throw Error('审核规则和知识库仅管理员可修改。');
  const d=await api('admin/moderation-settings');if(seq!==state.seq)return;caState.settings=d;renderModerationSettings();
 }
}
function renderCreatorList(){
 const main=document.getElementById('main'),items=caState.creators;
 main.innerHTML=heading('创作者管理','<button class="btn secondary" data-nav="creators">刷新</button>')+
 '<p class="hint">查看老师入驻申请及账号状态。开通资格后，老师在独立创作者中心管理自己的作品和数据。</p>'+
 '<div class="stats">'+[['pending','待审核'],['approved','已开通'],['suspended','已暂停'],['rejected','未通过']].map(([key,label])=>'<div class="stat"><strong>'+items.filter(x=>x.status===key).length+'</strong><span>'+label+'</span></div>').join('')+'</div>'+
 '<div class="editor-layout ca-review-grid"><div>'+table(['创作者／账号','状态','操作'],items.map(p=>[esc(p.displayName||p.name||p.username)+'<br><span class="meta">'+esc(p.username||p.userId)+'</span>',caBadge(p.status),'<button class="btn secondary small" data-ca-profile="'+esc(p.userId)+'">查看资料</button>']))+'</div><section class="panel ca-detail" id="ca-detail"><h2>入驻资料</h2><p class="hint">选择一位创作者，查看申请资料和账号关联。</p><a href="/creator" target="_blank" rel="noopener">打开创作者中心 ↗</a></section></div>';
 enhanceAdminLists();
}
function renderCreatorProfile(userId){
 const p=caState.creators.find(x=>x.userId===userId);if(!p)return;caState.selected=p;
 const admin=state.user.role==='admin',teachers=caState.teachers.filter(t=>t.profileType!=='demo');
 document.getElementById('ca-detail').innerHTML='<div class="ca-statusline">'+caBadge(p.status)+'<span class="meta">账号：'+esc(p.username||p.userId)+'</span></div><h2 style="margin-top:12px">'+esc(p.displayName||p.name||'未填写名称')+'</h2>'+
 (p.avatarUrl&&/^(https:\/\/|\/api\/media\/)/.test(p.avatarUrl)?'<img class="ca-avatar" src="'+esc(p.avatarUrl)+'" alt="申请人头像">':'')+
 '<p class="ca-body">'+esc(p.bio||'暂未填写个人介绍。')+'</p><p class="meta">账号标识：'+esc(p.userId)+'</p><p class="meta">老师资料：'+esc(p.teacherId||'尚未关联')+'</p>'+
 (p.reason?'<p class="ca-note">最近处理说明：'+esc(p.reason)+'</p>':'')+
 (admin?'<form id="ca-profile-form" class="grid-form ca-readonly" data-user-id="'+esc(p.userId)+'"><label class="wide">关联老师资料<select name="teacherId"><option value="">开通时自动建立老师资料</option>'+teachers.map(t=>'<option value="'+esc(t.id)+'"'+(t.id===p.teacherId?' selected':'')+'>'+esc(t.name||t.id)+(t._status==='published'?'':' · 未发布')+'</option>').join('')+(p.teacherId&&!teachers.some(t=>t.id===p.teacherId)?'<option selected value="'+esc(p.teacherId)+'">'+esc(p.teacherId)+'</option>':'')+'</select><span class="field-note">请核实申请人与老师身份一致。已有老师资料只能关联所属账号。</span></label><label class="wide">处理说明<textarea name="reason" rows="3" maxlength="500" minlength="2" required placeholder="记录核验结果或需补充的资料，申请人可看到此说明。"></textarea></label><div class="actions wide"><button class="btn" name="decision" value="approved">'+(p.status==='approved'?'保存开通与关联':'审核通过并开通')+'</button><button class="btn secondary" name="decision" value="rejected">退回申请</button><button class="btn danger" name="decision" value="suspended">暂停创作者资格</button></div><p class="hint wide">暂停后，该账号无法继续创作，已有创作者内容停止公开展示。</p><p class="error wide" role="alert"></p></form>':'<p class="permission-note ca-readonly">你可以查看入驻资料。资格开通、暂停和老师资料关联由管理员处理。</p>');
 document.getElementById('ca-detail').scrollIntoView({behavior:'smooth',block:'nearest'});
}
function renderCreatorReviews(){
 ++caState.detailRevision;caState.selected=null;
 const items=caState.works,filters=[['manual_review','待人工复核'],['ai_review','AI审核中'],['published','已发布'],['rejected','未通过'],['all','全部作品']],visible=caState.filter==='all'?items:items.filter(w=>w.status===caState.filter);
 document.getElementById('main').innerHTML=heading('创作者内容审核','<button class="btn secondary" data-nav="creatorReviews">刷新</button>')+
 '<div class="ca-flow" aria-label="人工审核流程"><span>创作者提交作品</span><b>→</b><span>平台人工复核</span><b>→</b><span>通过后发布到APP</span></div>'+
 '<p class="hint">当前按人工审核处理，AI接入暂缓。先查看原始内容、素材和审核记录，再作出决定。每次审核对应一个作品版本；作品有更新时需重新读取。</p>'+
 '<div class="ca-filters" aria-label="审核状态">'+filters.map(([key,label])=>'<button data-ca-filter="'+key+'" aria-pressed="'+(caState.filter===key)+'">'+label+' <span>'+ (key==='all'?items.length:items.filter(w=>w.status===key).length)+'</span></button>').join('')+'</div>'+
 '<div class="editor-layout ca-review-grid"><div>'+ (visible.length?table(['作品／作者','状态','操作'],visible.map(w=>[esc(w.title)+'<br><span class="meta">'+esc(w.displayName||w.ownerId)+' · '+esc(caTypes[w.type]||w.type)+'</span>',caBadge(w.status)+'<br><small class="meta">v'+esc(w.version)+'</small>','<button class="btn secondary small" data-ca-review="'+esc(w.id)+'">审阅作品</button>'])):'<div class="empty ca-empty">'+(caState.filter==='manual_review'?'当前没有待人工复核的作品。':'该状态下暂无作品。')+'</div>')+'</div><section class="panel ca-detail" id="ca-detail"><h2>作品审阅</h2><p class="hint">从列表选择作品，查看完整内容和审核轨迹。</p></section></div>';
 enhanceAdminLists();
}
function caHistory(items){
 return items.length?'<ol class="ca-history">'+items.map(r=>'<li><div class="ca-statusline"><b>'+esc({ai:'AI审核',human:'人工复核',appeal:'创作者申诉',submit:'提交审核',system:'系统处理'}[r.stage]||r.stage)+'</b><span class="badge">'+esc({approve:'通过',reject:'未通过',manual:'转人工',manual_review:'转人工',published:'通过',rejected:'未通过'}[r.decision]||r.decision)+'</span></div><p>'+esc(r.reason||'无补充说明')+'</p><small class="meta">'+caTime(r.created||r.createdAt)+(r.ruleVersion?' · 规则版本 '+esc(r.ruleVersion):'')+'</small></li>').join('')+'</ol>':'<p class="hint">暂无审核记录。</p>';
}
async function openCreatorReview(workId){
 const seq=state.seq,revision=++caState.detailRevision,detail=document.getElementById('ca-detail'),active=()=>revision===caState.detailRevision&&seq===state.seq&&state.nav==='creatorReviews'&&detail.isConnected&&document.getElementById('ca-detail')===detail;detail.innerHTML='<p class="ca-loading">正在读取作品与审核记录…</p>';
 try{
  const d=await api('admin/creator-reviews/'+encodeURIComponent(workId));if(!active())return;
  const w=d.item||caState.works.find(x=>x.id===workId);if(!w)throw Error('作品已不存在，请刷新列表。');caState.selected=w;
  const eligible=['manual_review','rejected','published'].includes(w.status),sections=Array.isArray(w.sections)?w.sections:[];
  detail.innerHTML='<div class="ca-statusline">'+caBadge(w.status)+'<span class="meta">'+esc(caTypes[w.type]||w.type)+' · 版本 '+esc(w.version)+'</span></div><h2 style="margin-top:12px">'+esc(w.title)+'</h2><p class="meta">'+esc(w.displayName||w.ownerId)+' · '+caTime(w.updatedAt)+'</p>'+
  caMedia(w.coverUrl,'image')+'<div class="ca-body">'+esc(w.body||'无正文')+'</div>'+caMedia(w.mediaUrl,w.format==='audio'?'audio':'video')+
  (sections.length?'<details><summary>课程章节（'+sections.length+'）</summary>'+sections.map((s,i)=>'<section class="ca-section"><b>'+esc(Array.isArray(s)?s[0]:(s.title||'章节 '+(i+1)))+'</b><p>'+esc(Array.isArray(s)?(s[2]||s[1]||''):(s.body||''))+'</p></section>').join('')+'</details>':'')+
  (w.reason?'<p class="ca-note">当前说明：'+esc(w.reason)+'</p>':'')+
  '<details open><summary>审核轨迹</summary>'+caHistory(d.reviews||d.items||[])+'</details>'+
  (eligible?'<form id="ca-review-form" class="grid-form ca-readonly" data-work-id="'+esc(w.id)+'" data-version="'+esc(w.version)+'"><label class="wide">人工复核说明<textarea name="reason" rows="3" maxlength="500" minlength="2" required placeholder="说明判断依据、具体片段和修改要求，创作者可看到此说明。"></textarea></label><div class="actions wide">'+(w.status==='published'?'':'<button class="btn" value="approve">审核通过并发布</button>')+'<button class="btn danger" value="reject">'+(w.status==='published'?'下架并说明原因':'退回修改')+'</button></div><p class="error ca-error wide" role="alert"></p></form>':'<p class="permission-note ca-readonly">'+(w.status==='draft'?'作品尚未提交审核，不能直接发布。':'AI审核正在处理中，完成后再进行人工复核。')+'</p>');
  detail.scrollIntoView({behavior:'smooth',block:'nearest'});
 }catch(e){if(active())detail.innerHTML='<p class="error ca-error" role="alert">'+esc(e.message)+'</p><button class="btn secondary" data-ca-review="'+esc(workId)+'">重新读取</button>';}
}
function renderModerationSettings(){
 const d=caState.settings||{};
 document.getElementById('main').innerHTML=heading('审核规则与知识库','<button class="btn secondary" data-nav="moderation">刷新</button>')+
 '<section class="panel"><div class="ca-intro"><div><h2>内容审核规则</h2><p class="hint">本阶段保留人工复核与申诉，AI接入暂缓。管理员先依据平台规则查看原始内容与素材，再作出处理。</p></div><span class="badge">当前规则版本 '+esc(d.version||1)+'</span></div><div class="ca-flow"><span>创作者提交</span><b>→</b><span>人工复核与申诉</span><b>→</b><span>通过后发布</span></div>'+
 '<p class="ca-note">AI服务'+(d.aiReady?'已有配置，是否启用以实际开关为准。':'尚未配置，本阶段无需填写模型或凭据。')+' 当前AI接入暂缓；关闭AI初审时，作品直接转人工复核。音视频和图片需实际检查，不以标题或自填文字代替审核。</p>'+
 '<form id="ca-moderation-form" class="grid-form"><label class="wide ca-toggle"><input type="checkbox" name="enabled"'+(d.enabled?' checked':'')+'><span>开启 AI 初审<small>关闭时，提交的作品直接进入人工复核。</small></span></label><label class="wide ca-toggle"><input type="checkbox" name="autoApprove"'+(d.autoApprove?' checked':'')+'><span>允许符合条件的内容自动通过<small>规则与知识库完整、服务正常且内容可被完整分析时才适用。保留人工抽检。</small></span></label><label class="wide">审核规则<textarea name="rules" rows="8" maxlength="20000" placeholder="明确允许、禁止及必须人工复核的内容类别；说明判断依据和处理方式。">'+esc(d.rules||'')+'</textarea></label><label class="wide">公司审核知识库<textarea name="knowledge" rows="10" maxlength="30000" placeholder="维护经公司确认的专业资料、事实依据、术语解释与审核案例。">'+esc(d.knowledge||'')+'</textarea></label><p class="hint wide">每次保存生成新规则版本，历史审核保留当时的规则版本。审核知识和规则与日常AI问答内容分别维护。</p><div class="actions wide"><button class="btn">保存审核规则</button><button type="button" class="btn secondary" data-nav="settings">查看接口配置</button><button type="button" class="btn secondary" data-nav="creatorReviews">进入人工复核</button></div><p class="error wide" role="alert"></p></form></section>';
}
document.addEventListener('click',e=>{
 const profile=e.target.closest('[data-ca-profile]');if(profile){renderCreatorProfile(profile.dataset.caProfile);return;}
 const filter=e.target.closest('[data-ca-filter]');if(filter){caState.filter=filter.dataset.caFilter;renderCreatorReviews();return;}
 const review=e.target.closest('[data-ca-review]');if(review)openCreatorReview(review.dataset.caReview);
});
document.addEventListener('submit',async e=>{
 const form=e.target;if(!['ca-profile-form','ca-review-form','ca-moderation-form'].includes(form.id))return;e.preventDefault();
 const values=Object.fromEntries(new FormData(form)),submitter=e.submitter,output=form.querySelector('.error'),buttons=[...form.querySelectorAll('button')],seq=state.seq;
 output.textContent='';buttons.forEach(b=>b.disabled=true);
 try{
  if(form.id==='ca-profile-form'){
   if(state.user.role!=='admin')throw Error('仅管理员可变更创作者资格。');
   if(!String(values.reason||'').trim())throw Error('请填写处理说明。');
   const status=submitter?.value;if(!['approved','rejected','suspended'].includes(status))throw Error('请选择处理方式。');
   await api('admin/creators/'+encodeURIComponent(form.dataset.userId),{status,teacherId:values.teacherId||'',reason:values.reason.trim()},'PATCH');
   if(seq===state.seq){toast('创作者状态已更新');await load('creators');}
  }else if(form.id==='ca-review-form'){
   if(!String(values.reason||'').trim())throw Error('请填写人工复核说明。');
   const decision=submitter?.value;if(!['approve','reject'].includes(decision))throw Error('请选择审核结果。');
   await api('admin/creator-reviews/'+encodeURIComponent(form.dataset.workId),{decision,reason:values.reason.trim(),version:Number(form.dataset.version)});
   if(seq===state.seq){toast(decision==='approve'?'审核通过，作品已发布':'作品已退回，创作者可查看原因');await load('creatorReviews');}
  }else{
   if(state.user.role!=='admin')throw Error('仅管理员可修改审核规则。');
   const enabled=values.enabled==='on',autoApprove=values.autoApprove==='on';
   if(enabled&&(!String(values.rules||'').trim()||!String(values.knowledge||'').trim()))throw Error('开启AI初审前，请填写审核规则和知识库。');
   await api('admin/moderation-settings',{enabled,autoApprove,rules:values.rules||'',knowledge:values.knowledge||''},'PUT');
   if(seq===state.seq){toast('审核规则与知识库已保存');await load('moderation');}
  }
 }catch(err){if(output.isConnected){output.textContent=err.message;if(form.id==='ca-review-form')output.textContent+=' 如作品已更新，请重新读取最新版本后再审核。';}}finally{buttons.forEach(b=>{if(b.isConnected)b.disabled=false;});}
});
