// Server-authorized catalog and sandbox order operations in the existing console.
const coAdmin={epoch:-1,data:null,editing:null,order:null,pending:null};
function coAdminReset(){if(coAdmin.epoch!==state.authEpoch)Object.assign(coAdmin,{epoch:state.authEpoch,data:null,editing:null,order:null,pending:null});}
function coAdminPrice(v,c='CNY'){try{const f=new Intl.NumberFormat('zh-CN',{style:'currency',currency:c});return f.format(Number(v||0)/10**f.resolvedOptions().maximumFractionDigits);}catch{return String(v||0)+' '+c;}}
function coAdminStatus(v){return ({expired:'预占已到期',pending:'待支付',unpaid:'待支付',paid:'已支付',closed:'已关闭',refunded:'已退款',partially_refunded:'部分退款',ready:'已发权益',unfulfilled:'待履约',shipped:'已发货',delivered:'已完成',cancelled:'已取消',draft:'草稿',published:'已上架',archived:'已下架',refund_pending:'待退款'})[v]||v||'—';}
async function loadCommerceAdmin(seq){
 coAdminReset();const epoch=state.authEpoch,d=await api('admin/commerce');if(seq!==state.seq||!authCurrent(epoch)||state.nav!=='commerce')return;coAdmin.data=d;renderCommerceAdmin();
}
function coAdminField(name,label,type='text',value='',extra=''){return `<label>${label}<input name="${name}" type="${type}" value="${esc(value??'')}" ${extra}></label>`;}
function coAdminSkuFields(v={},remove=false){
 const options=v.options||[];
 return `<fieldset class="grid-form wide" data-co-sku-row data-sku-id="${esc(v.skuId||'')}" data-stock="${esc(v.stock??0)}">
 <legend>${v.sku?esc(v.sku):'新规格'}</legend>
 ${coAdminField('variantSku','SKU编码','text',v.sku,'required maxlength="100"')}
 ${coAdminField('variantPrice','价格（最小货币单位）','number',v.priceMinor??0,'required min="0" max="1000000000" step="1"')}
 ${coAdminField('variantStock','总库存','number',v.stock??0,'required min="0" max="1000000000" step="1"')}
 <label class="inline-check"><input type="checkbox" name="variantActive" ${v.active!==false?'checked':''}>在售</label>
 <div class="wide grid-form">${Array.from({length:4},(_,i)=>coAdminField('optionName','规格名称','text',options[i]?.name,'maxlength="40"')+coAdminField('optionValue','规格取值','text',options[i]?.value,'maxlength="80"')).join('')}</div>
 ${v.skuId?`<p class="hint wide">已预占 ${Number(v.reserved||0)} 件。取消在售可停止该规格的新购买。</p>`:remove?'<button class="btn secondary" type="button" data-co-admin="remove-sku">移除未保存规格</button>':''}
 </fieldset>`;
}
function coAdminOrderLine(item){const options=(item.options||[]).map(o=>o.name+' · '+o.value).join(' / ');return [item.title||item.snapshot?.title||item.skuId,options,item.sku].filter(Boolean).join(' · ');}
function coAdminProductForm(){
 const p=coAdmin.editing||{},option=(v,label,selected)=>`<option value="${v}" ${selected===v?'selected':''}>${label}</option>`;
 return `<section class="panel" id="co-product-editor"><h2>${p.id?'编辑商品':'新增商品'}</h2><form id="co-product-form" class="grid-form">${coAdminField('title','商品名称','text',p.title,'required maxlength="120"')}<label>商品类型<select name="type">${[['digital','数字作品'],['physical','实物商品'],['membership','会员方案']].map(([v,n])=>option(v,n,p.type||'digital')).join('')}</select></label><label>交易环境<select name="environment">${option('sandbox','沙箱测试，不正式售卖',p.environment||'sandbox')}${option('production','正式商品资料，支付仍关闭',p.environment||'sandbox')}</select></label>${coAdminField('currency','币种 三位ISO代码','text',p.currency||'CNY','required pattern="[A-Z]{3}" maxlength="3"')}${coAdminField('contentId','数字作品对应课程ID','text',p.contentId,'maxlength="100"')}${coAdminField('imageUrl','商品图片 HTTPS或已上传地址','text',p.imageUrl,'maxlength="1500"')}${coAdminField('shippingCountries','配送国家代码 逗号分隔','text',(p.shippingCountries||[]).join(','),'maxlength="600"')}${coAdminField('shippingMinor','运费 最小货币单位整数','number',p.shippingMinor??0,'required min="0" max="1000000000" step="1"')}${coAdminField('taxMinor','税费 最小货币单位整数','number',p.taxMinor??0,'required min="0" max="1000000000" step="1"')}<div class="wide" id="co-variants"><h3>商品规格</h3><p class="hint">填写每个SKU的价格和库存。单规格可以留空规格名称与取值。</p><div data-co-sku-list>${(p.variants||[p]).map((v,i)=>coAdminSkuFields(v,i>0)).join('')}</div><button class="btn secondary" type="button" data-co-admin="add-sku">新增规格</button></div><label class="wide">商品介绍<textarea name="description" maxlength="5000">${esc(p.description||'')}</textarea></label><label class="wide">退款与使用条款<textarea name="refundPolicy" maxlength="2000">${esc(p.refundPolicy||'')}</textarea></label><details class="wide"><summary>简繁英藏商品文案</summary><div class="grid-form">${[['Zh','简体中文'],['Hant','繁体中文'],['En','英文'],['Bo','藏文']].map(([suffix,label])=>`<label>${label}标题<input name="title${suffix}" value="${esc(p['title'+suffix]||'')}" maxlength="120"></label><label>${label}说明<textarea name="description${suffix}" maxlength="5000">${esc(p['description'+suffix]||'')}</textarea></label>`).join('')}</div></details><label>发布状态<select name="status">${[['draft','保存草稿'],['published','上架'],['archived','下架']].map(([v,n])=>option(v,n,p.status||'draft')).join('')}</select></label><p class="hint">CNY 100表示人民币1元，JPY 100表示100日元。正式价格、商品授权和条款需项目方确认；当前仅沙箱可模拟交易。数字商品不会因测试订单获得正式内容权限。</p><p class="wide error" data-co-admin-error role="alert"></p><div class="actions wide"><button class="btn" type="submit">保存商品</button><button class="btn secondary" type="button" data-co-admin="new">清空表单</button></div></form></section>`;
}
function coAdminOrderDetail(){
 const o=coAdmin.order;if(!o)return '';
 const paid=['paid','partially_refunded'].includes(o.paymentStatus||o.status),physical=(o.items||[]).some(x=>x.type==='physical'||x.snapshot?.type==='physical');
 return `<section class="panel" id="co-order-editor"><h2>订单详情</h2><p class="hint">${esc(o.id)} · ${o.environment==='sandbox'?'沙箱订单，没有真实扣款':'正式订单'} · ${coAdminStatus(o.paymentStatus||o.status)}</p>${table(['商品','数量','已退款数量','单价'],(o.items||[]).map(x=>[esc(coAdminOrderLine(x)),Number(x.quantity),Number(x.refundedQuantity||0),esc(coAdminPrice(x.unitPriceMinor??x.priceMinor,o.currency))]))}<p class="hint">应付 ${esc(coAdminPrice(o.totalMinor,o.currency))}　履约 ${coAdminStatus(o.fulfillmentStatus)}　售后 ${esc(o.aftersaleStatus||'none')}</p>${o.shippingAddress?`<details><summary>收货资料</summary><p class="hint">${esc(Object.values(o.shippingAddress).filter(Boolean).join(' '))}</p></details>`:''}${(o.aftersaleRequests||[]).length?`<h3>售后申请</h3>${table(['原因','状态','时间'],o.aftersaleRequests.map(x=>[esc(x.reason),esc(x.status),date(x.createdAt||x.created)]))}`:''}${paid&&state.user.role==='admin'?`${physical?`<form id="co-fulfill-form" class="grid-form">${coAdminField('carrier','承运方','text',o.tracking?.carrier,'required maxlength="100"')}${coAdminField('trackingNumber','物流单号','text',o.tracking?.trackingNumber,'required maxlength="120"')}<button class="btn secondary" type="submit">登记发货</button><p data-co-admin-error class="error" role="alert"></p></form>`:''}<h3>按项退款</h3><p class="hint">此操作只处理该订单环境的退款账与权益。沙箱不会发起银行退款。每项数量不得超过未退款数量。</p><form id="co-refund-form" class="grid-form">${(o.items||[]).map(x=>coAdminField('refund_'+x.id,esc(coAdminOrderLine(x))+' 退款数量','number',0,`min="0" max="${Math.max(0,x.quantity-(x.refundedQuantity||0))}" step="1"`)).join('')}<label class="inline-check wide"><input type="checkbox" name="confirm" required>确认按所选订单项及数量办理退款</label><button class="btn" type="submit">登记所选项退款</button><p data-co-admin-error class="error" role="alert"></p></form>`:''}</section>`;
}
function renderCommerceAdmin(){
 coAdminReset();const d=coAdmin.data;if(!d||!state.user||state.nav!=='commerce')return;
 const main=document.getElementById('main'),write=state.user.role==='admin';
 main.innerHTML=heading('商城与统一订单','<button class="btn secondary" data-nav="commerce">刷新</button>')+`<p class="hint">商品、订单项、价格快照和权益统一管理。当前正式支付关闭，生产价格及渠道尚待确认；沙箱记录与正式权益隔离。</p>${write?`<section class="panel"><h2>交易开关</h2><form id="co-settings-form"><label class="inline-check"><input name="sandboxEnabled" type="checkbox" ${d.settings?.sandboxEnabled?'checked':''}>开启沙箱商城和模拟付款</label><p class="hint">正式支付开关保持关闭。开通真实渠道及价格规则确认后另行联调。</p><button class="btn secondary" type="submit">保存测试开关</button><p data-co-admin-error class="error" role="alert"></p></form></section>`:''}<section class="panel"><h2>商品目录</h2>${table(['商品','SKU','环境','价格','库存','状态','操作'],(d.products||[]).map(p=>[esc(p.title),esc((p.variants||[p]).map(v=>v.sku+(v.active===false?'（下架）':'')).join(' / ')),p.environment==='sandbox'?'沙箱':'正式',esc((p.variants||[p]).map(v=>coAdminPrice(v.priceMinor,v.currency)).join(' / ')),(p.variants||[p]).map(v=>String(v.availableStock??v.stock)).join(' / '),coAdminStatus(p.status),write?`<button class="btn secondary small" data-co-admin="edit" data-id="${esc(p.id)}">编辑</button>`:'只读']))}</section>${write?coAdminProductForm():''}<section class="panel"><h2>订单</h2>${table(['订单','环境','金额','付款','履约','售后','操作'],(d.orders||[]).map(o=>[esc(o.id),o.environment==='sandbox'?'沙箱':'正式',esc(coAdminPrice(o.totalMinor,o.currency)),coAdminStatus(o.paymentStatus||o.status),coAdminStatus(o.fulfillmentStatus),esc(o.aftersaleStatus||'none'),`<button class="btn secondary small" data-co-admin="order" data-id="${esc(o.id)}">查看</button>`]))}</section>${coAdminOrderDetail()}${write?payAdminPanel():''}${write?callbackAdminPanel():''}${write?recoveryAdminPanel():''}${write?lateAdminPanel():''}${write?digitalAdminPanel():''}${write?opsAdminPanel():''}${write?payRouteAdminPanel():''}`;
}
document.addEventListener('click',async event=>{
 const b=event.target.closest('[data-co-admin]');if(!b)return;event.preventDefault();event.stopImmediatePropagation();coAdminReset();const epoch=state.authEpoch,seq=state.seq,active=()=>authCurrent(epoch)&&state.seq===seq&&state.nav==='commerce';
 try{
  if(b.dataset.coAdmin==='add-sku'){
   const list=document.querySelector('[data-co-sku-list]');
   if(list.children.length>=20)throw Error('最多维护20个SKU。');
   list.insertAdjacentHTML('beforeend',coAdminSkuFields({},true));
   list.lastElementChild.querySelector('input').focus();
   return;
  }
  if(b.dataset.coAdmin==='remove-sku'){
   b.closest('[data-co-sku-row]').remove();
   return;
  }
  if(b.dataset.coAdmin==='new'){coAdmin.editing=null;renderCommerceAdmin();return;}
  if(b.dataset.coAdmin==='edit'){coAdmin.editing=coAdmin.data?.products.find(p=>p.id===b.dataset.id);renderCommerceAdmin();document.getElementById('co-product-editor')?.scrollIntoView({block:'start'});return;}
  if(b.dataset.coAdmin==='order'){const order=await api('admin/commerce/orders/'+encodeURIComponent(b.dataset.id));if(active()){coAdmin.order=order;coAdmin.pending=null;renderCommerceAdmin();document.getElementById('co-order-editor')?.scrollIntoView({block:'start'});}}
 }catch(error){if(active())showError(error);}
},true);
document.addEventListener('submit',async event=>{
 const form=event.target;if(!['co-product-form','co-settings-form','co-fulfill-form','co-refund-form'].includes(form.id))return;event.preventDefault();event.stopImmediatePropagation();if(!form.checkValidity())return;
 const epoch=state.authEpoch,seq=state.seq,active=()=>authCurrent(epoch)&&seq===state.seq&&state.nav==='commerce',values=Object.fromEntries(new FormData(form)),submit=event.submitter;
 if(submit)submit.disabled=true;
 try{
  if(form.id==='co-settings-form')await api('admin/commerce/settings',{sandboxEnabled:values.sandboxEnabled==='on',productionEnabled:false},'PATCH');
  else if(form.id==='co-product-form'){
   const p=coAdmin.editing||{};
   const variants=[...form.querySelectorAll('[data-co-sku-row]')].map(row=>{
    const fields=name=>[...row.querySelectorAll(`[name="${name}"]`)];
    const input=name=>fields(name)[0];
    const options=fields('optionName').map((field,i)=>({name:field.value.trim(),value:fields('optionValue')[i].value.trim()})).filter(option=>option.name||option.value);
    return {...(row.dataset.skuId?{skuId:row.dataset.skuId,expectedStock:Number(row.dataset.stock)}:{}),
     sku:input('variantSku').value,priceMinor:Number(input('variantPrice').value),stock:Number(input('variantStock').value),active:input('variantActive').checked,options};
   });
   for(const name of ['variantSku','variantPrice','variantStock','variantActive','optionName','optionValue'])delete values[name];
   const item={id:p.id,version:p.version,...values,variants,shippingMinor:Number(values.shippingMinor),taxMinor:Number(values.taxMinor),shippingCountries:String(values.shippingCountries||'').split(',').map(s=>s.trim().toUpperCase()).filter(Boolean)};
   await api('admin/commerce/products',item);
  }else if(form.id==='co-fulfill-form')await api('admin/commerce/orders/'+encodeURIComponent(coAdmin.order.id)+'/fulfill',values);
  else if(form.id==='co-refund-form'){
   const items=(coAdmin.order.items||[]).map(x=>({itemId:x.id,quantity:Number(values['refund_'+x.id]||0)})).filter(x=>x.quantity>0);if(!items.length)throw Error('请填写至少一项退款数量。');const signature=JSON.stringify(items);if(coAdmin.pending?.signature!==signature)coAdmin.pending={signature,requestId:crypto.randomUUID()};await api('admin/commerce/orders/'+encodeURIComponent(coAdmin.order.id)+'/refund',{requestId:coAdmin.pending.requestId,items});
  }
  if(!active())return;const selected=coAdmin.order?.id;coAdmin.pending=null;coAdmin.editing=null;coAdmin.data=await api('admin/commerce');if(!active())return;if(selected)coAdmin.order=await api('admin/commerce/orders/'+encodeURIComponent(selected));if(active()){renderCommerceAdmin();toast('已保存，可在订单和审计记录中核对。');}
 }catch(error){if(!active()||error.handled)return;const output=form.querySelector('[data-co-admin-error]');if(output?.isConnected)output.textContent=error.message;else showError(error);}
 finally{if(submit?.isConnected)submit.disabled=false;}
},true);
