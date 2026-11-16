// Optional admin module. Call AfterSalesAdmin.install() from the existing admin build after account/commerce modules.
(function(root){
 'use strict';
 let installed=false,runtime=null;
 function get(){if(!runtime||runtime.epoch!==state.authEpoch)runtime={epoch:state.authEpoch,caseId:'',data:null,detail:null,busy:false,loading:false,error:'',keys:{},retry:null};return runtime;}
 function active(r,seq){return runtime===r&&authCurrent(r.epoch)&&state.nav==='afterSales'&&(seq===undefined||seq===state.seq);}
 const label=v=>({submitted:'待受理',accepted:'已受理',rejected:'已驳回',returning:'已登记退货物流',partially_received:'部分实收',received:'已完成收货验收'})[v]||v;
 const price=(n,c)=>typeof coAdminPrice==='function'?coAdminPrice(n,c):esc(String(n)+' '+c);
 function draw(){
  const r=get();if(state.nav!=='afterSales'||!state.user)return;const d=r.data,detail=r.detail,disabled=r.busy?'disabled':'';
  let html=heading('售后受理与退货验收','<button class="btn secondary" data-af-admin="refresh" '+disabled+'>重新查询</button>')+
   '<section class="panel"><h2>独立沙箱流程</h2><p class="hint">本模块不收款、不执行退款，不将受理/物流/验收当作资金到账。真实生产售后、承运商核验和退换货条款尚未启用。只接受统一沙箱已付款原单，原资金事实继续在统一交易模块记录。</p>'+
   (r.error?'<p class="error" role="alert">'+esc(r.error)+'</p>':'')+(r.retry?'<button class="btn secondary" data-af-admin="retry" '+disabled+'>同编号重试上次操作</button>':'')+'</section>';
  if(!d){document.getElementById('main').innerHTML=html+'<p>'+(r.loading?'正在读取…':'尚未读取到有权查看的售后资料。')+'</p>';return;}
  html+='<section class="panel"><h2>测试配置</h2><form data-af-admin-form="settings"><fieldset '+disabled+'><label class="inline-check"><input type="checkbox" name="sandboxEnabled" '+(d.settings.sandboxEnabled?'checked':'')+'>开启售后沙箱（统一交易沙箱也须开启）</label><label>明确测试规则版本<input name="ruleVersion" maxlength="120" value="'+esc(d.settings.ruleVersion||'')+'"></label><p class="hint">正式开关始终关闭；版本只是测试流程版本，不是负责人已审核的正式售后政策。</p><button class="btn">保存测试配置</button></fieldset></form></section>';
  html+='<section class="panel"><h2>申请列表</h2>'+table(['申请/原订单','账号','类型/状态','数量','操作'],d.items.map(c=>[esc(c.id)+'<br><small>'+esc(c.orderId)+'</small>',esc(c.ownerId),esc(c.type)+' / '+esc(label(c.status)),c.items.reduce((n,x)=>n+x.quantity,0),'<button class="btn secondary small" data-af-admin="open" data-id="'+esc(c.id)+'" '+disabled+'>查看</button>']))+'</section>';
  if(detail){
   const c=detail,m=c.money,canDecide=c.status==='submitted',canReceive=c.type==='return'&&['accepted','returning','partially_received'].includes(c.status)&&c.shipments.length>0&&d.settings.sandboxEnabled;
   html+='<section class="panel" data-af-admin-detail="'+esc(c.id)+'"><h2>'+esc(label(c.status))+'</h2><p>'+esc(c.reason)+'</p><p class="hint">原订单 '+esc(c.orderId)+' · 测试规则 '+esc(c.ruleVersion)+' · 版本 '+c.version+'</p>'+
    table(['订单项','类型','申请','实收','已入库','原项累计退款数量'],c.items.map(x=>[esc(x.snapshot.title)+'<br><small>'+esc(x.itemId)+'</small>',esc(x.type),x.quantity,x.receivedQuantity,x.restockedQuantity,x.orderItemRefundedQuantity]))+
    '<div class="hint"><p>资金独立：'+esc(m.orderPaymentStatus||'—')+'；原订单累计沙箱退款 '+price(m.orderRefundedMinor||0,m.currency||'USD')+'</p><p>该累计事实未逐笔绑定本申请，不表示本申请已退款或真实到账。此页不调用退款接口。</p></div>';
   if(canDecide)html+='<form data-af-admin-form="decision" data-case="'+esc(c.id)+'"><fieldset '+disabled+'><legend>受理或驳回</legend><label>决定<select name="decision" required><option value="">请选择</option><option value="accept">受理申请（不自动退款）</option><option value="reject">驳回申请</option></select></label><label>向申请人显示的理由<textarea name="reason" maxlength="2000" required></textarea></label><button class="btn">记录决定</button></fieldset></form>';
   html+='<h3>退货物流登记</h3>'+(c.shipments.length?table(['承运商','物流单号','登记日期','核验'],c.shipments.map(x=>[esc(x.carrier),esc(x.trackingNumber),esc(new Date(x.created).toISOString()),'用户登记，未接承运商核验'])):'<p class="hint">尚无物流登记；数字和会员申请不接受物流或仓库验收。</p>');
   if(canReceive){
    const lines=c.items.map(x=>{const left=x.quantity-x.receivedQuantity;return '<fieldset class="af-admin-receipt-item" '+(!left||r.busy?'disabled':'')+'><legend>'+esc(x.snapshot.title)+'</legend><p class="hint">本申请尚可登记实收 '+left+' 件。可入库数量必须由本次验收明确填写，默认0。</p><label>本次实际收到数量<input type="number" name="received:'+esc(x.id)+'" min="0" max="'+left+'" step="1" value="0"></label><label>本次可重新入库数量<input type="number" name="restock:'+esc(x.id)+'" min="0" max="'+left+'" step="1" value="0"></label><label>本次物品状态/判断依据<input name="condition:'+esc(x.id)+'" maxlength="200"></label></fieldset>';}).join('');
    html+='<form data-af-admin-form="inspect" data-case="'+esc(c.id)+'"><fieldset '+disabled+'><legend>收货验收与明确入库</legend><label>唯一收货批次/验收单号<input name="receiptReference" maxlength="100" required></label><p class="hint">同一原订单的该单号只能使用一次（跨申请也不重复）；网络不确定时用“同编号重试”，不能换编号重复登记同批物品。登记不代表真实承运核验。</p>'+lines+'<label>验收说明<textarea name="note" maxlength="2000" required></textarea></label><button class="btn">记录实收及明确入库数量</button></fieldset></form>';
   }
   html+='<h3>验收记录</h3>'+table(['验收单号','说明','数量/入库/状态','库存事件'],c.inspections.flatMap(x=>x.items.map(i=>[esc(x.receiptReference),esc(x.note),i.receivedQuantity+' / '+i.restockQuantity+' / '+esc(i.condition),esc(i.inventoryEventId)])))+
    '<details><summary>完整操作记录</summary>'+table(['日期','操作','说明'],c.history.map(x=>[esc(new Date(x.created).toISOString()),esc(x.kind),esc(x.data.reason||x.data.note||'')]))+'</details></section>';
  }
  document.getElementById('main').innerHTML=html;
 }
 async function loadHere(){
  const r=get();if(!state.user)return false;if(r.busy){draw();return false;}const seq=++state.seq;r.loading=true;r.error='';
  try{const jobs=[api('admin/after-sales?environment=sandbox')];if(r.caseId)jobs.push(api('admin/after-sales/cases/'+encodeURIComponent(r.caseId)));const result=await Promise.all(jobs);if(!active(r,seq))return false;r.data=result[0];r.detail=r.caseId?result[1]:null;return true;}
  catch(e){if(active(r,seq)){r.error=e.message;if(e.status===401||e.status===403){r.data=null;r.detail=null;r.retry=null;}}return false;}
  finally{if(active(r,seq)){r.loading=false;draw();}}
 }
 function requestKey(r,path,payload){const k=JSON.stringify([path,payload]);return r.keys[k]||(r.keys[k]=crypto.randomUUID());}
 async function mutate(path,payload,method='POST'){
  const r=get();if(r.busy)return;const seq=++state.seq;r.loading=false;r.busy=true;r.error='';r.mutationSeq=seq;let handled=false;
  const body=method==='POST'?{...payload,requestId:payload.requestId||requestKey(r,path,payload)}:payload;r.retry={path,body,method};draw();
  try{await api(path,body,method);if(!active(r,seq))return;handled=true;r.busy=false;r.retry=null;await loadHere();}
  catch(e){if(active(r,seq)){handled=true;r.busy=false;r.error=e.message;if(e.status===401||e.status===403){r.data=null;r.detail=null;r.retry=null;}draw();}}
  finally{if(runtime===r&&authCurrent(r.epoch)&&r.mutationSeq===seq){r.busy=false;if(!handled&&state.nav==='afterSales')void loadHere();}}
 }
 function install(){
  if(installed)return;if(typeof load!=='function'||typeof api!=='function'||typeof labels!=='object')throw Error('Load existing admin framework first');installed=true;labels.afterSales='售后受理与退货验收';
   if(typeof allowedNavs==='function'){const priorAllowed=allowedNavs;allowedNavs=function(user=state.user){const items=priorAllowed(user).filter(k=>k!=='afterSales');if(user?.role==='admin')items.push('afterSales');return items;};}
  const previousLoad=load;load=async function(nav){if(nav!=='afterSales')return previousLoad(nav);state.nav=nav;document.querySelectorAll('[data-nav]').forEach(b=>b.setAttribute('aria-current',b.dataset.nav===nav?'page':'false'));return loadHere();};
  document.addEventListener('click',event=>{
   const b=event.target.closest?.('[data-af-admin]');if(!b)return;event.preventDefault();event.stopImmediatePropagation();const r=get();if(r.busy)return;
   if(b.dataset.afAdmin==='refresh')void loadHere();
   if(b.dataset.afAdmin==='open'){r.caseId=b.dataset.id;r.detail=null;r.retry=null;void loadHere();}
   if(b.dataset.afAdmin==='retry'&&r.retry)void mutate(r.retry.path,r.retry.body,r.retry.method);
  },true);
  document.addEventListener('submit',event=>{
   const form=event.target.closest?.('[data-af-admin-form]');if(!form)return;event.preventDefault();event.stopImmediatePropagation();const r=get();if(r.busy||state.nav!=='afterSales'||!form.reportValidity())return;const f=new FormData(form),kind=form.dataset.afAdminForm;
   if(kind==='settings'){void mutate('admin/after-sales/settings',{sandboxEnabled:f.get('sandboxEnabled')==='on',productionEnabled:false,ruleVersion:String(f.get('ruleVersion')||'').trim()||null},'PATCH');return;}
   const c=r.detail;if(!c||c.id!==form.dataset.case)return;
   if(kind==='decision')void mutate('admin/after-sales/cases/'+encodeURIComponent(c.id)+'/decision',{version:c.version,decision:String(f.get('decision')),reason:String(f.get('reason'))});
   if(kind==='inspect'){
    const items=[];
    for(const x of c.items){
     const receivedQuantity=Number(f.get('received:'+x.id)||0),restockQuantity=Number(f.get('restock:'+x.id)||0);
     if(!receivedQuantity&&!restockQuantity)continue;
     const condition=String(f.get('condition:'+x.id)||'').trim();
     if(!Number.isSafeInteger(receivedQuantity)||receivedQuantity<1||!Number.isSafeInteger(restockQuantity)||restockQuantity<0||restockQuantity>receivedQuantity||!condition){r.error='请逐项填写实际实收、明确入库数量及状态依据；不可自动全入库。';draw();return;}
     items.push({caseItemId:x.id,receivedQuantity,restockQuantity,condition});
    }
    if(!items.length){r.error='请至少填写一项本次实际收到的数量。';draw();return;}
    void mutate('admin/after-sales/cases/'+encodeURIComponent(c.id)+'/inspect',{version:c.version,receiptReference:String(f.get('receiptReference')),items,note:String(f.get('note'))});
   }
  },true);
 }
 root.AfterSalesAdmin=Object.freeze({install,openCase(id){const r=get();r.caseId=String(id);r.detail=null;r.retry=null;return load('afterSales');}});
})(typeof globalThis==='object'?globalThis:this);

