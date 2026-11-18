// Administrative privacy declarations contain no provider credentials or user message bodies.
let privacyAdminData=null;
async function loadPrivacyAdmin(seq){
 const epoch=state.authEpoch,[d,r]=await Promise.all([api('admin/privacy/config'),api('admin/privacy/requests')]);
 if(!authCurrent(epoch)||seq!==state.seq||state.nav!=='privacy')return;privacyAdminData=d.config;
 const cfg=d.config,field=(key,label,max)=>`<label>${label}<input name="${key}" value="${esc(cfg[key]||'')}" maxlength="${max}" required></label>`;
 document.getElementById('main').innerHTML=heading('隐私配置与处理申请')+`<section class="panel"><p class="hint">填写真实处理主体、供应商与已确认条款；未确认的保存期限留空。不在这里保存API密钥。数据处理规则改变时必须更新政策版本，用户需要重新确认。</p><form id="privacy-admin-form" class="grid-form">${field('policyVersion','政策版本',80)}${field('controllerName','处理主体',120)}${field('contact','联系路径',240)}<label class="wide">接收方清单 JSON<textarea name="recipients" rows="12" required>${esc(JSON.stringify(cfg.recipients||[],null,2))}</textarea></label><p class="hint wide">每项含 id、name、endpoint、models数组、regions数组、purpose、policyUrl、retentionDays（未知为null）、deletionSupported。实际AI配置中的供应商ID、完整地址、模型、地区及政策版本必须与此一致；不能用显示名称代替实际接收方。</p>${[['recordsDays','个人记录保存天数'],['conversationsDays','会话保存天数'],['backupDays','备份清理天数'],['financeDays','财务保留天数']].map(([k,label])=>`<label>${label}<input name="${k}" type="number" min="0" max="36500" step="1" value="${esc(cfg.retention[k]??'')}" placeholder="尚未确认"></label>`).join('')}${[['trainingImprovement','训练改进的独立用途说明'],['marketing','营销的独立用途说明']].map(([k,label])=>`<label class="wide">${label}<textarea name="${k}" maxlength="2000">${esc(cfg.purposeDetails[k]||'')}</textarea></label>`).join('')}<p class="error wide" data-privacy-admin-error role="alert"></p><button class="btn" type="submit">保存披露版本</button></form></section><section class="panel"><h2>本人提交的处理申请</h2><p class="hint">当前存储、供应商和备份分别核查；待处理申请不会自动标成已删除或已注销。这里仅展示处理元数据，不含会话正文。</p>${table(['申请时间','账号','类型','当前状态','供应商／备份'],r.items.map(x=>[date(x.createdAt),esc(x.accountId),esc(x.kind),esc(x.status),esc(JSON.stringify({providers:x.details.providers,backups:x.details.backups}))]))}</section>${privacyDomainsAdminPanel()}`;
}
document.addEventListener('submit',async event=>{
 if(event.target.id!=='privacy-admin-form')return;event.preventDefault();event.stopImmediatePropagation();
 const form=event.target,epoch=state.authEpoch,values=Object.fromEntries(new FormData(form)),output=form.querySelector('[data-privacy-admin-error]'),button=form.querySelector('button');button.disabled=true;
 try{
  const retention=Object.fromEntries(['recordsDays','conversationsDays','backupDays','financeDays'].map(k=>[k,values[k]===''?null:Number(values[k])]));
  await api('admin/privacy/config',{revision:privacyAdminData.revision,policyVersion:values.policyVersion,controllerName:values.controllerName,contact:values.contact,recipients:JSON.parse(values.recipients),retention,purposeDetails:{trainingImprovement:values.trainingImprovement,marketing:values.marketing}},'PATCH');
  if(!authCurrent(epoch))return;toast('隐私披露版本已保存');await load('privacy');
 }catch(error){if(authCurrent(epoch)&&output.isConnected)output.textContent=error.message;}finally{if(button.isConnected)button.disabled=false;}
},true);
