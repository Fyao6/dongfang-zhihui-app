// Real provider metadata and explicit local test credits; credentials remain environment secrets.
labels.aiGateway='AI网关与测试额度';
const agAdmin={epoch:-1,config:null,users:[],busy:false,grantSignature:'',grantKey:null};
function agAdminReset(){if(agAdmin.epoch!==state.authEpoch)Object.assign(agAdmin,{epoch:state.authEpoch,config:null,users:[],busy:false,grantSignature:'',grantKey:null});}
function renderAIGatewayAdmin(){
 if(state.nav!=='aiGateway'||!state.user)return;
 document.getElementById('main').innerHTML=heading('AI网关与测试额度')+`<section class="panel"><p class="hint">网关默认关闭。这里登记实际供应商协议、端点、模型、处理地区、场景路由与测试扣次规则；必须与隐私披露匹配，并由用户逐接收方明确确认。配置可用不等于真实模型已验收。</p><p class="hint">secretRef 只接受 EW_AI_ 前缀的服务端环境变量名，不接收明文密钥。四种场景为 chat、chart、course、card。环境仅 local-test，不会开通生产额度、会员或收费。</p><form id="ag-admin-config"><label>服务端网关配置 JSON<textarea name="configuration" rows="24" maxlength="100000" required>${esc(JSON.stringify(agAdmin.config,null,2))}</textarea></label><p class="error" data-ag-admin-error role="alert"></p><button class="btn" type="submit">保存网关配置</button></form></section><section class="panel"><h2>明确授予本地测试额度</h2><p class="hint">仅增加独立测试钱包，不代表购买、付款或正式会员权益。停止、失败和部分输出均按实际确认的测试规则结算；真实上游费用未知时保持未知。</p><form id="ag-admin-grant" class="grid-form"><label>测试账号<select name="accountId" required><option value="">请选择实际账号</option>${agAdmin.users.map(u=>`<option value="${esc(u.id)}">${esc(u.name)} @${esc(u.username)}</option>`).join('')}</select></label><label>增加测试额度<input type="number" name="credits" min="1" max="1000000" step="1" required></label><p class="error wide" data-ag-admin-error role="alert"></p><button class="btn" type="submit">授予测试额度</button></form></section>`;
}
const agAdminLoadBefore=load;
load=async function(nav){
 if(nav!=='aiGateway')return agAdminLoadBefore(nav);
 if(!state.user||!document.getElementById('main'))return false;agAdminReset();const epoch=state.authEpoch,seq=++state.seq;state.nav=nav;
 document.querySelectorAll('[data-nav]').forEach(b=>b.setAttribute('aria-current',b.dataset.nav===nav?'page':'false'));const main=document.getElementById('main');main.innerHTML=heading('AI网关与测试额度')+'<p class="hint">正在读取…</p>';
 try{const [d,u]=await Promise.all([api('admin/ai-gateway'),api('admin/users')]);if(!authCurrent(epoch)||seq!==state.seq||state.nav!==nav)return false;agAdmin.config=d.config;agAdmin.users=u.items||[];renderAIGatewayAdmin();return true;}
 catch(error){if(authCurrent(epoch)&&seq===state.seq&&main.isConnected&&!error.handled)main.innerHTML=heading('AI网关与测试额度')+'<p class="error">'+esc(error.message)+'</p>';return false;}
};
document.addEventListener('submit',async event=>{
 const form=event.target,formId=form.getAttribute('id');if(!['ag-admin-config','ag-admin-grant'].includes(formId))return;event.preventDefault();event.stopImmediatePropagation();agAdminReset();if(agAdmin.busy)return;
 const epoch=state.authEpoch,fields=new FormData(form),button=form.querySelector('button[type=submit]'),output=form.querySelector('[data-ag-admin-error]');agAdmin.busy=true;button.disabled=true;output.textContent='';
 try{
  if(formId==='ag-admin-config'){const data=JSON.parse(fields.get('configuration'));data.revision=agAdmin.config.revision;await api('admin/ai-gateway/config',data,'PATCH');}
  else{const accountId=String(fields.get('accountId')||''),credits=Number(fields.get('credits')),signature=JSON.stringify({accountId,credits});if(agAdmin.grantSignature!==signature){agAdmin.grantSignature=signature;agAdmin.grantKey=crypto.randomUUID();}await api('admin/ai-gateway/grants',{requestId:agAdmin.grantKey,accountId,credits,environment:'local-test'});if(authCurrent(epoch)){agAdmin.grantKey=null;agAdmin.grantSignature='';}}
  if(!authCurrent(epoch))return;toast(formId==='ag-admin-config'?'网关配置已保存':'测试额度已记录，未产生实际付款');if(state.nav==='aiGateway')await load('aiGateway');
 }catch(error){if(authCurrent(epoch)&&output.isConnected)output.textContent=error.message;}
 finally{if(authCurrent(epoch))agAdmin.busy=false;if(button.isConnected)button.disabled=false;}
},true);
