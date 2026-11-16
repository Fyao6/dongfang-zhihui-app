// Optional independent customer after-sales screens. Call AfterSalesUI.install() after account/commerce UI.
(function(root){
 'use strict';
 let installed=false,runtime=null;
 const text=(en,zh,hant,bo)=>flText(en,zh,hant,bo),pages=['afterSalesCenter','afterSalesRequest','afterSalesDetail'];
 function current(s,seq){return runtime===s&&psCurrent(s.actor)&&(seq===undefined||s.sequence===seq);}
 function get(){const actor=psToken();if(!runtime||runtime.actor.scope!==actor.scope||runtime.actor.epoch!==actor.epoch)runtime={actor,sequence:0,mutation:0,environment:'production',orderId:'',caseId:'',loaded:false,loading:false,scheduled:false,busy:false,error:'',config:null,items:[],eligibility:null,detail:null,draft:{type:'refund-only',items:{}},shippingDraft:{},keys:{},retry:null};return runtime;}
 const signature=s=>JSON.stringify([s.environment,s.orderId,s.caseId]);
 function reset(s){s.sequence++;s.mutation++;s.loaded=false;s.loading=false;s.scheduled=false;s.busy=false;s.error='';s.retry=null;}
 function ensure(){const s=get();if(px.user&&!s.loaded&&!s.loading&&!s.scheduled&&!s.busy){s.scheduled=true;const key=signature(s);queueMicrotask(()=>{if(current(s)&&signature(s)===key){s.scheduled=false;void load();}});}return s;}
 async function load(force=false){
  const s=get();if(!px.user||s.busy||!force&&(s.loading||s.loaded))return;
  const seq=++s.sequence,key=signature(s);s.loading=true;s.scheduled=false;s.error='';
  try{
   const jobs=[pxApi('after-sales/config?environment='+s.environment),pxApi('after-sales/cases?environment='+s.environment)];
   if(s.orderId)jobs.push(pxApi('after-sales/orders/'+encodeURIComponent(s.orderId)));
   else if(s.caseId)jobs.push(pxApi('after-sales/cases/'+encodeURIComponent(s.caseId)));
   const result=await Promise.all(jobs);if(!current(s,seq)||signature(s)!==key)return;
   s.config=result[0];s.items=result[1].items||[];if(s.orderId)s.eligibility=result[2];else if(s.caseId)s.detail=result[2];s.loaded=true;
  }catch(e){if(current(s,seq)&&signature(s)===key){s.error=e.message;s.loaded=true;}}
  finally{if(current(s,seq)&&signature(s)===key){s.loading=false;if(pages.includes(state.page))render(false);}}
 }
 function status(v){return ({submitted:text('Submitted','待受理','待受理','འབུལ་ཟིན།'),accepted:text('Accepted for review','已受理','已受理','དང་ལེན་བྱས།'),rejected:text('Rejected with reason','已驳回','已駁回','ཕྱིར་བསྐྱུར།'),returning:text('Return tracking registered','已登记退货物流','已登記退貨物流','ཕྱིར་སློག་འགྲུལ་ཐོ་བཀོད་ཟིན།'),partially_received:text('Partially received','部分实收','部分實收','ཁ་ཤས་ལེན་ཟིན།'),received:text('Receipt inspected','已完成收货验收','已完成收貨驗收','དངོས་ཟོག་ལེན་ཞིབ་བཤེར་ཟིན།')})[v]||v;}
 function eventLabel(kind){
  const labels={
   submit:text('Request submitted','已提交申请','已提交申請','རེ་ཞུ་འབུལ་ཟིན།'),
   accept:text('Request accepted','已受理申请','已受理申請','རེ་ཞུ་དང་ལེན་བྱས།'),
   reject:text('Request declined','已驳回申请','已駁回申請','རེ་ཞུ་ཕྱིར་བསྐྱུར།'),
   'return-shipping':text('Return tracking registered','已登记退货物流','已登記退貨物流','ཕྱིར་སློག་འགྲུལ་ཐོ་བཀོད་ཟིན།'),
   inspect:text('Receipt recorded','已登记收货验收','已登記收貨驗收','དངོས་ཟོག་ལེན་ཞིབ་བཤེར་ཐོ་བཀོད་ཟིན།')
  };
  return Object.prototype.hasOwnProperty.call(labels,kind)?labels[kind]:text('Status updated','状态已更新','狀態已更新','གནས་ཚུལ་གསར་སྒྱུར་བྱས།');
 }
 function date(v){try{return ewFormatDate(new Date(v),{year:'numeric',month:'2-digit',day:'2-digit'});}catch{return '—';}}
 function mode(s){return '<div class="af-mode"><span>'+text('After-sales · sandbox only, no actual funds moved','售后流程 · 仅沙箱，不发生真实资金流动','售後流程 · 僅沙箱，不發生真實資金流動','ཞབས་ཞུ་རྗེས་མ། ཚོད་ལྟ་ཙམ་ཡིན། དངོས་དངུལ་མི་སྒྱུར།')+'</span><button class="link" data-af-action="environment">'+(s.environment==='sandbox'?text('Return to closed production view','返回正式关闭态','返回正式關閉態','དངོས་སྤྱོད་སྒོ་བརྒྱབ་རྣམ་པར་ལོག'):text('View sandbox','查看测试流程','查看測試流程','ཚོད་ལྟར་ལྟ་བ།'))+'</button></div>';}
 function notice(s){
  const retry=s.retry?'<button class="btn secondary" data-af-action="retry">'+text('Retry the same request ID','同编号重试','同編號重試','ཨང་གྲངས་དེ་གས་སླར་ཚོད།')+'</button>':'';
  return (s.loading?'<p role="status">'+text('Loading…','正在读取…','正在讀取…','ཀློག་བཞིན་ཡོད།')+'</p>':'')+(s.error?'<p class="lc-error" role="alert">'+esc(s.error)+'</p>':'')+retry;
 }
 function shell(title,body,s){return '<section class="page af-page">'+pxTop(title,'',state.page==='afterSalesDetail'?'afterSalesCenter':state.page==='afterSalesRequest'?'commerceOrder':'commerceOrders')+mode(s)+notice(s)+body+'</section>';}
 function caseCard(c){return '<article class="card af-case" data-af-case="'+esc(c.id)+'"><h2>'+esc(status(c.status))+'</h2><p>'+esc(c.reason)+'</p><p class="small">'+esc(date(c.created))+' · '+esc(c.type)+' · '+esc(c.orderId)+'</p><button class="btn secondary" data-af-action="open" data-id="'+esc(c.id)+'">'+text('View progress','查看进度','查看進度','འཕེལ་རིམ་ལྟ་བ།')+'</button></article>';}
 function center(){
  const s=ensure();let body='';
  if(!px.user)body='<p>'+text('Sign in to view your requests.','登录后查看本人申请。','登入後查看本人申請。','ཐོ་འཇུག་ནས་རང་གི་རེ་ཞུ་ལྟ་བ།')+'</p>';
  else if(s.environment!=='sandbox')body='<article class="card"><p>'+text('Production after-sales is not enabled. Existing test cases are in the sandbox view.','正式售后尚未启用，已有测试申请请切换沙箱查看。','正式售後尚未啟用，已有測試申請請切換沙箱查看。','དངོས་སྤྱོད་ཞབས་ཞུ་རྗེས་མ་མ་ཕྱེ། ཚོད་ལྟའི་རེ་ཞུ་ཚོད་ལྟའི་ཁོངས་ནས་ལྟ་བ།')+'</p></article>';
  else body=(s.items.length?s.items.map(caseCard).join(''):'<p>'+text('No requests in this account.','本账号暂无申请。','本帳號暫無申請。','རྩིས་ཐོ་འདིར་རེ་ཞུ་མེད།')+'</p>')+'<button class="btn secondary full" data-action="go" data-to="commerceOrders">'+text('Choose an original order','从统一订单选择商品','從統一訂單選擇商品','མངགས་ཐོ་ནས་འདེམས།')+'</button>';
  return shell(text('My after-sales requests','我的售后申请','我的售後申請','རང་གི་ཞབས་ཞུ་རྗེས་མའི་རེ་ཞུ།'),body,s);
 }
 function requestScreen(){
  const s=ensure(),e=s.eligibility;
  if(!e)return shell(text('Request after-sales','申请售后','申請售後','ཞབས་ཞུ་རྗེས་མ་རེ་ཞུ།'),'<p>'+text('Choose an original order to continue.','请从统一订单详情进入。','請從統一訂單詳情進入。','མངགས་ཐོ་ངོ་མ་ནས་འཇུག་རོགས།')+'</p>',s);
  const type=s.draft.type,available=x=>type==='return'?x.availableReturnQuantity:x.availableRefundOnlyQuantity,disabled=s.busy||!e.canApply;
  const rows=e.items.map(x=>{const n=available(x),draft=s.draft.items[x.itemId]||{};return '<fieldset class="af-item" '+(!n||disabled?'disabled':'')+'><label class="af-check"><input type="checkbox" name="item" value="'+esc(x.itemId)+'" '+(draft.checked&&n?'checked':'')+'><strong>'+esc(x.title)+'</strong></label><p>'+esc(text('Available quantity: ','当前可申请数量：','目前可申請數量：','རེ་ཞུ་བྱེད་ཐུབ་གྲངས། ')+n)+' · '+esc(x.type)+'</p><label>'+text('Quantity','申请数量','申請數量','གྲངས།')+'<input name="quantity:'+esc(x.itemId)+'" type="number" min="1" max="'+Math.max(1,n)+'" step="1" value="'+esc(Math.min(n||1,draft.quantity||1))+'"></label></fieldset>';}).join('');
  let blocked='';
  if(e.legacyPending)blocked=text('This order has an existing legacy request. Review it in the original order flow first.','本单已有旧流程待处理申请，请先在原订单查看。','本單已有舊流程待處理申請，請先在原訂單查看。','མངགས་ཐོ་འདིར་རེ་ཞུ་རྙིང་པ་སྒྲུབ་སྒུག་ཡོད།');
  else if(!e.paymentConfirmed)blocked=text('A verified unified test payment is required.','须先有统一测试付款确认。','須先有統一測試付款確認。','མངགས་ཐོའི་ཚོད་ལྟ་དངུལ་སྤྲོད་ངེས་གཏན་དགོས།');
  else if(!e.canApply)blocked=text('The administrator has not enabled this test workflow.','管理员尚未开启本测试流程。','管理員尚未開啟本測試流程。','དོ་དམ་པས་ཚོད་ལྟའི་ལས་རིམ་མ་ཕྱེ།');
  const body='<p class="af-context">'+esc(e.orderId)+'</p><p class="small">'+text('Requests and warehouse receipts do not automatically issue a refund.','提交申请或登记退货均不会自动退款。','提交申請或登記退貨均不會自動退款。','རེ་ཞུ་དང་དངོས་ཟོག་ཕྱིར་ལེན་གྱིས་དངུལ་རང་འགུལ་དུ་མི་སློག')+'</p>'+(blocked?'<p role="status">'+esc(blocked)+'</p>':'')+
   '<form data-af-form="request" data-order="'+esc(e.orderId)+'"><label>'+text('Request type','申请类型','申請類型','རེ་ཞུའི་རིགས།')+'<select name="type" '+(s.busy?'disabled':'')+'><option value="refund-only" '+(type==='refund-only'?'selected':'')+'>'+text('Refund review only','仅退款申请','僅退款申請','དངུལ་ཕྱིར་སློག་ཞིབ་བཤེར།')+'</option><option value="return" '+(type==='return'?'selected':'')+'>'+text('Return dispatched physical goods','已发货实物退货','已發貨實物退貨','བཏང་ཟིན་དངོས་ཟོག་ཕྱིར་སློག')+'</option></select></label>'+rows+'<label>'+text('Reason','申请理由','申請理由','རྒྱུ་མཚན།')+'<textarea name="reason" required maxlength="2000" '+(disabled?'disabled':'')+'>'+esc(s.draft.reason||'')+'</textarea></label><button class="btn full" '+(disabled?'disabled':'')+'>'+text('Submit request','提交申请','提交申請','རེ་ཞུ་འབུལ་བ།')+'</button></form>';
  return shell(text('Request after-sales','申请售后','申請售後','ཞབས་ཞུ་རྗེས་མ་རེ་ཞུ།'),body,s);
 }
 function detailScreen(){
  const s=ensure(),c=s.detail;if(!c)return shell(text('Request progress','售后进度','售後進度','རེ་ཞུའི་འཕེལ་རིམ།'),'',s);
  const items=c.items.map(x=>'<article class="af-item"><h3>'+esc(x.snapshot.title)+'</h3><p>'+esc(text('Requested / received / restocked: ','申请 / 实收 / 已入库：','申請 / 實收 / 已入庫：','རེ་ཞུ། / དངོས་ལེན། / ཉར་ས་བཅུག ')+[x.quantity,x.receivedQuantity,x.restockedQuantity].join(' / '))+'</p></article>').join('');
  const history=c.history.map(x=>'<li><span>'+esc(date(x.created))+' · <strong data-af-event-label>'+esc(eventLabel(x.kind))+'</strong></span><p>'+esc(x.data.reason||x.data.note||'')+'</p></li>').join('');
  const ships=c.shipments.map(x=>'<li>'+esc(x.carrier+' · '+x.trackingNumber)+'<p class="small">'+text('Registered here; carrier tracking is not verified.','仅登记物流，未接承运商核验。','僅登記物流，未接承運商核驗。','འགྲུལ་ཐོ་བཀོད་ཙམ། འདྲེན་མཁན་གྱིས་ངེས་གཏན་མ་བྱས།')+'</p></li>').join('');
  const canShip=c.type==='return'&&['accepted','returning','partially_received'].includes(c.status)&&s.config?.settings.sandboxEnabled;
  const form=canShip?'<form data-af-form="shipping" data-case="'+esc(c.id)+'"><fieldset '+(s.busy?'disabled':'')+'><legend>'+text('Register return tracking','登记退货物流','登記退貨物流','ཕྱིར་སློག་འགྲུལ་ཐོ།')+'</legend><label>'+text('Carrier','承运商','承運商','འདྲེན་མཁན།')+'<input name="carrier" required maxlength="100" value="'+esc(s.shippingDraft.carrier||'')+'"></label><label>'+text('Tracking number','退货物流单号','退貨物流單號','འགྲུལ་ཐོའི་ཨང་།')+'<input name="trackingNumber" required maxlength="100" value="'+esc(s.shippingDraft.trackingNumber||'')+'"></label><button class="btn full">'+text('Save tracking','保存物流','儲存物流','འགྲུལ་ཐོ་ཉར།')+'</button></fieldset></form>':'';
  const money=c.money,financial='<details class="af-money"><summary>'+text('Original order payment records','原订单付款记录','原訂單付款紀錄','མངགས་ཐོ་ངོ་མའི་དངུལ་སྤྲོད་ཐོ།')+'</summary><p>'+text('These are cumulative sandbox facts from the original order. They do not confirm a refund for this case or real funds received.','这里是原订单累计沙箱事实，不表示本申请已退款或真实到账。','這裡是原訂單累計沙箱事實，不表示本申請已退款或真實到帳。','འདི་མངགས་ཐོ་ངོ་མའི་ཚོད་ལྟའི་ཐོ་ཡིན། རེ་ཞུ་འདིའི་དངུལ་དངོས་ཕྱིར་ཐོབ་པར་མི་བརྩི།')+'</p><p>'+esc(money.orderPaymentStatus||'—')+' · '+esc(typeof coMoney==='function'?coMoney(money.orderRefundedMinor||0,money.currency||'USD'):String(money.orderRefundedMinor||0))+'</p></details>';
  return shell(text('Request progress','售后进度','售後進度','རེ་ཞུའི་འཕེལ་རིམ།'),'<div data-af-detail="'+esc(c.id)+'"><h2>'+esc(status(c.status))+'</h2><p>'+esc(c.reason)+'</p>'+items+financial+'<ol class="af-timeline">'+history+'</ol>'+(ships?'<ul class="af-timeline">'+ships+'</ul>':'')+form+'<button class="btn secondary full" data-af-action="refresh">'+text('Refresh status','重新查询进度','重新查詢進度','འཕེལ་རིམ་སླར་ཀློག')+'</button></div>',s);
 }
 function captureDraft(form){const s=get(),f=new FormData(form);s.draft.type=String(f.get('type')||'refund-only');s.draft.reason=String(f.get('reason')||'');s.draft.items={};for(const id of f.getAll('item'))s.draft.items[id]={checked:true,quantity:Number(f.get('quantity:'+id))};}
 function requestKey(s,path,payload){const id=JSON.stringify([path,payload]);return s.keys[id]||(s.keys[id]=crypto.randomUUID());}
 function openOrder(id){const s=get();reset(s);s.environment='sandbox';s.orderId=String(id);s.caseId='';s.eligibility=null;s.detail=null;s.keys={};s.draft={type:'refund-only',reason:'',items:{}};navigate('afterSalesRequest');}
 function openCase(id){const s=get();reset(s);s.environment='sandbox';s.orderId='';s.caseId=String(id);s.detail=null;s.shippingDraft={};navigate('afterSalesDetail');}
 async function mutate(path,payload){
  const s=get();if(s.busy)return;const actor=s.actor,nonce=++s.mutation,page=state.page,key=signature(s);s.sequence++;s.loading=false;s.scheduled=false;s.busy=true;s.error='';
  const active=()=>current(s)&&s.mutation===nonce&&psCurrent(actor)&&state.page===page&&signature(s)===key;
  const body={...payload,requestId:payload.requestId||requestKey(s,path,payload)};s.retry={path,body};render(false);
  try{const result=await pxApi(path,body,'POST',{timeout:15000});if(!active())return;s.busy=false;s.retry=null;openCase(result.item.id);}
  catch(e){if(active()){s.error=e.message;s.busy=false;render(false);}}
  finally{if(current(s)&&s.mutation===nonce){s.busy=false;if(!active()){s.loaded=false;if(pages.includes(state.page))render(false);}}}
 }
 function install(){
  if(installed)return;if(typeof psToken!=='function'||typeof pxApi!=='function'||typeof screens!=='object')throw Error('Load account/commerce UI first');installed=true;
  screens.afterSalesCenter=center;screens.afterSalesRequest=requestScreen;screens.afterSalesDetail=detailScreen;
   if(typeof ewNavigationDefaults==='object')Object.assign(ewNavigationDefaults,{afterSalesCenter:'commerceOrders',afterSalesRequest:'commerceOrder',afterSalesDetail:'afterSalesCenter'});
   if(typeof coOpenAftersale==='function'){
    const priorSupport=coOpenAftersale;
    coOpenAftersale=function(){const c=typeof coState==='function'?coState():null;if(px.afterSalesReady&&c?.order?.environment==='sandbox')return openOrder(c.order.id);return priorSupport();};
   }
   if(typeof screens.commerceOrders==='function'){
    const priorOrders=screens.commerceOrders;
    screens.commerceOrders=function(){const html=priorOrders();if(!px.user)return html;const at=html.lastIndexOf('</section>');if(at<0)return html;return html.slice(0,at)+'<button class="btn secondary full" data-af-action="center">'+text('My after-sales requests','我的售后申请','我的售後申請','རང་གི་ཞབས་ཞུ་རྗེས་མའི་རེ་ཞུ།')+'</button>'+html.slice(at);};
   }
  document.addEventListener('input',event=>{const form=event.target.closest?.('[data-af-form]');if(!form||get().busy)return;if(form.dataset.afForm==='request'&&get().orderId===form.dataset.order)captureDraft(form);if(form.dataset.afForm==='shipping'&&get().caseId===form.dataset.case){const f=new FormData(form);get().shippingDraft={carrier:String(f.get('carrier')||''),trackingNumber:String(f.get('trackingNumber')||'')};}},true);
  document.addEventListener('change',event=>{const form=event.target.closest?.('[data-af-form=request]');if(form&&get().orderId===form.dataset.order&&!get().busy){captureDraft(form);if(event.target.name==='type')render(false);}},true);
  document.addEventListener('click',event=>{
   const b=event.target.closest?.('[data-af-action]');if(!b)return;event.preventDefault();event.stopImmediatePropagation();const s=get(),action=b.dataset.afAction;
   if(action==='open')openCase(b.dataset.id);
    if(action==='center'){reset(s);s.caseId='';s.orderId='';s.detail=null;s.eligibility=null;navigate('afterSalesCenter');}
   if(action==='refresh')void load(true);
   if(action==='retry'&&s.retry)void mutate(s.retry.path,s.retry.body);
   if(action==='environment'){reset(s);s.environment=s.environment==='sandbox'?'production':'sandbox';s.caseId='';s.orderId='';s.detail=null;s.eligibility=null;navigate('afterSalesCenter');}
  },true);
  document.addEventListener('submit',event=>{
   const form=event.target.closest?.('[data-af-form]');if(!form)return;event.preventDefault();event.stopImmediatePropagation();
   const s=get();if(s.busy||!form.reportValidity())return;const f=new FormData(form);
   if(form.dataset.afForm==='request'&&s.orderId===form.dataset.order){
    captureDraft(form);const items=[...f.getAll('item')].map(id=>({itemId:String(id),quantity:Number(f.get('quantity:'+id))}));if(!items.length){s.error=text('Choose at least one item.','请至少选择一个订单项。','請至少選擇一個訂單項。','དངོས་ཟོག་གཅིག་འདེམས་རོགས།');render(false);return;}
    void mutate('after-sales/cases',{environment:'sandbox',orderId:s.orderId,type:String(f.get('type')),items,reason:String(f.get('reason'))});
   }else if(form.dataset.afForm==='shipping'&&s.detail&&s.caseId===form.dataset.case){
    void mutate('after-sales/cases/'+encodeURIComponent(s.caseId)+'/return-shipping',{version:s.detail.version,carrier:String(f.get('carrier')),trackingNumber:String(f.get('trackingNumber'))});
   }
  },true);
 }
 root.AfterSalesUI=Object.freeze({install,openOrder,openCase,refresh:()=>load(true)});
})(typeof globalThis==='object'?globalThis:this);

