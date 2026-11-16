const payHelpCopy = coText;
const payHelpTitle = () => payHelpCopy('Payment help','支付与订阅帮助','支付與訂閱協助','དངུལ་སྤྲོད་རོགས་རམ།');
const payHelpKinds = () => ({
 'duplicate-charge':payHelpCopy('Duplicate charge','重复扣款','重複扣款','དངུལ་ཐེངས་གཉིས་བླངས་པ།'),
 'payment-missing':payHelpCopy('Payment not reflected','支付未到账','付款未入帳','དངུལ་སྤྲད་པ་མ་འབྱོར།'),
 'restore-failed':payHelpCopy('Cannot restore purchase','无法恢复购买','無法恢復購買','ཉོས་པ་སླར་གསོ་མི་ཐུབ།'),
 'cancel-renewal':payHelpCopy('Cancel subscription renewal','取消订阅续费','取消訂閱續費','རང་འགུལ་དུས་འགྱངས་མཚམས་འཇོག')
});
const payHelpStatus = value => ({
 submitted:payHelpCopy('Submitted','已提交','已提交','ཕུལ་ཟིན།'),
 accepted:payHelpCopy('In review','处理中','處理中','ལྟ་ཞིབ་བཞིན།'),
 resolved:payHelpCopy('Closed with reply','已回复并办结','已回覆並結案','ལན་བཏབ་ཅིང་མཇུག་བསྡུས།')
})[value];
let payHelpSession;
function payHelpState(){
 const actor=psToken();
 if(!payHelpSession||payHelpSession.actor.scope!==actor.scope||payHelpSession.actor.epoch!==actor.epoch)
  payHelpSession={actor,orderId:'',kind:'duplicate-charge',message:'',eventId:'',items:[],next:null,loading:false,loaded:false,serial:0};
 return payHelpSession;
}
function payHelpEntry(orderId='',kind=''){
 return `<button type="button" class="btn secondary full" data-pay-help="open" data-order="${esc(orderId)}" data-kind="${esc(kind)}">${payHelpTitle()}</button>`;
}
function payHelpFormatDate(time){
 const locale={zh:'zh-CN','zh-Hant':'zh-TW',en:'en',bo:'bo'}[state.lang];
 return new Intl.DateTimeFormat(locale,{dateStyle:'short',timeStyle:'short'}).format(time);
}
function payHelpEvent(event){
 const title=event.kind==='refund'?payHelpCopy('Sandbox refund','测试退款','測試退款','ཚོད་ལྟའི་དངུལ་ཕྱིར་སྤྲད།'):
  payHelpCopy('Sandbox payment','测试支付','測試付款','ཚོད་ལྟའི་དངུལ་སྤྲོད།');
 return title+' · '+coMoney(event.amountMinor,event.currency)+' · '+payHelpFormatDate(event.created);
}
function payHelpSummary(payment){
 const {order,events}=payment;
 return `<div class="pay-help-summary"><p>${payHelpCopy('Sandbox order','测试订单','測試訂單','ཚོད་ལྟའི་ཉོ་ཐོ།')} <b>${esc(order.id)}</b></p>
 <p>${esc(coStatus(order.paymentStatus))} · ${esc(coStatus(order.fulfillmentStatus))} · ${esc(coMoney(order.totalMinor,order.currency))}</p>
 ${events.length?`<ul>${events.map(event=>`<li>${esc(payHelpEvent(event))}</li>`).join('')}</ul>`:
 `<p>${payHelpCopy('No payment record for this order yet.','此订单暂无支付记录。','此訂單暫無付款紀錄。','ཉོ་ཐོ་འདིར་དངུལ་སྤྲོད་ཟིན་ཐོ་མེད།')}</p>`}</div>`;
}
function payHelpPage(){
 const s=payHelpState(),labels=payHelpKinds(),loggedIn=Boolean(px.user);
 if(loggedIn&&!s.loaded&&!s.loading)queueMicrotask(()=>payHelpLoad(s));
 return `<section class="page co-page"><div class="co-content pay-help">${pxTop(payHelpTitle(),'','commerceOrders')}
 ${loggedIn?`<p class="co-environment">${payHelpCopy('Sandbox support','测试客服','測試客服','ཚོད་ལྟའི་ཞབས་ཞུ།')}</p>
 <article class="co-order-detail"><form id="pay-help-form" class="pay-help-form">
 <label>${payHelpCopy('Issue','问题类型','問題類型','གནད་དོན།')}<select name="kind">${Object.entries(labels).map(([key,label])=>`<option value="${key}" ${key===s.kind?'selected':''}>${label}</option>`).join('')}</select></label>
 <div class="pay-help-links">
 ${s.kind==='restore-failed'?go(payHelpCopy('Restore purchases','恢复购买','恢復購買','ཉོས་པ་སླར་གསོ།'),'membershipRestore','secondary'):
 s.kind==='cancel-renewal'?go(payHelpCopy('Manage renewal','管理续费','管理續費','དུས་འགྱངས་དོ་དམ།'),'membershipCancel','secondary'):
 go(payHelpCopy('Find my order','查找我的订单','查找我的訂單','རང་གི་ཉོ་ཐོ་ལྟ།'),'commerceOrders','secondary')}
 </div>
 ${s.orderId?`<p>${payHelpCopy('Linked order','已选订单','已選訂單','འབྲེལ་བའི་ཉོ་ཐོ།')} <b>${esc(s.orderId)}</b></p>
 ${s.payment?payHelpSummary(s.payment):''}
 ${s.payment?.events.length?`<label>${payHelpCopy('Payment record','支付记录','付款紀錄','དངུལ་སྤྲོད་ཟིན་ཐོ།')}<select name="eventId"><option value="">${payHelpCopy('Link order only','仅关联订单','只連結訂單','ཉོ་ཐོ་ཁོ་ན་འབྲེལ།')}</option>${s.payment.events.map(event=>`<option value="${esc(event.id)}" ${event.id===s.eventId?'selected':''}>${esc(payHelpEvent(event))}</option>`).join('')}</select></label>`:''}
 <button type="button" class="btn secondary" data-pay-help="clear" ${s.sending?'disabled':''}>${payHelpCopy('Remove order link','移除订单关联','移除訂單連結','ཉོ་ཐོའི་འབྲེལ་བ་སེལ།')}</button>`:''}
 <label>${payHelpCopy('Describe the issue','问题说明','問題說明','གནད་དོན་གསལ་བཤད།')}<textarea name="message" rows="3" maxlength="750" ${s.orderId?'':'required'} aria-describedby="pay-help-private">${esc(s.message)}</textarea></label>
 <p id="pay-help-private">${payHelpCopy('Include only what support needs. Omit card numbers, passwords, and verification codes.','只填写处理所需的信息，请勿填写银行卡号、密码或验证码。','只填寫處理所需的資訊，請勿填寫銀行卡號、密碼或驗證碼。','མཁོ་བའི་གནས་ཚུལ་ཁོ་ན་འབྲི། དངུལ་ཁང་བྱང་བུའི་ཨང་དང་གསང་ཨང་མ་འབྲི།')}</p>
 <button type="submit" class="btn full" ${s.sending||s.loading||s.orderId&&!s.payment?'disabled':''}>${payHelpCopy('Submit support request','提交客服工单','提交客服單','ཞབས་ཞུའི་ཞུ་བ་འབུལ།')}</button></form></article>
 <p class="co-feedback" role="status">${s.loading?payHelpCopy('Loading…','正在读取…','正在讀取…','ཀློག་བཞིན།'):s.notice||''}</p>
 ${s.error?`<p class="co-feedback co-error" role="alert">${esc(s.error)}</p>`:''}
 <section><h2>${payHelpCopy('My support requests','我的客服工单','我的客服單','ངའི་ཞབས་ཞུའི་ཞུ་བ།')}</h2>
 <button type="button" class="btn secondary" data-pay-help="refresh" ${s.loading||s.sending?'disabled':''}>${payHelpCopy('Refresh status','刷新进度','更新進度','གནས་སྟངས་གསར་བཅོས།')}</button>
 ${s.loaded&&!s.loading&&!s.items.length&&!s.error?`<p>${payHelpCopy('No support requests yet.','暂无工单。','暫無客服單。','ཞུ་བ་མེད།')}</p>`:''}
 <div class="pay-help-tickets">${s.items.map(ticket=>`<details class="co-order-detail" data-pay-help-ticket="${esc(ticket.id)}" ${ticket.id===s.latest?'open':''}>
 <summary>${labels[ticket.kind]} · ${payHelpStatus(ticket.status)}</summary><p>${esc(ticket.id)} · ${esc(payHelpFormatDate(ticket.created))}</p>
 ${ticket.orderId?`<p>${esc(ticket.orderId)}</p>`:''}
 ${ticket.eventId?`<p>${payHelpCopy('Payment record','支付记录','付款紀錄','དངུལ་སྤྲོད་ཟིན་ཐོ།')} ${esc(ticket.eventId)}</p>`:''}
 ${ticket.message?`<p>${esc(ticket.message)}</p>`:''}
 ${ticket.replies.map(reply=>`<p><strong>${payHelpStatus(reply.status)}</strong> · ${esc(payHelpFormatDate(reply.created))}<br>${esc(reply.reply)}</p>`).join('')}
 </details>`).join('')}</div>
 ${s.next?`<button type="button" class="btn secondary full" data-pay-help="more" ${s.loading?'disabled':''}>${payHelpCopy('Older requests','更早的工单','更早的客服單','ཞུ་བ་སྔོན་མ།')}</button>`:''}</section>`:coUserGate()}</div></section>`;
}
screens.paymentSupport=payHelpPage;
ewNavigationDefaults.paymentSupport='commerceOrders';

function payHelpError(error){
 if(state.lang==='zh')return error.message;
 if(error.status===404)return payHelpCopy('This order or payment record could not be found.','找不到此订单或支付记录。','找不到此訂單或付款紀錄。','ཉོ་ཐོ་ཡང་ན་དངུལ་སྤྲོད་ཟིན་ཐོ་མ་རྙེད།');
 return payHelpCopy('Could not complete the request. Check your details and retry.','操作未完成，请检查后重试。','操作未完成，請檢查後重試。','ཞུ་བ་མ་འགྲུབ། བརྟགས་ནས་སླར་ཚོད་ལྟ་བྱོས།');
}
function payHelpReadForm(s,form){
 const data=new FormData(form);
 s.kind=data.get('kind');s.message=data.get('message');s.eventId=data.get('eventId')||'';
}
function payHelpRender(s){if(payHelpSession===s&&psCurrent(s.actor)&&state.page==='paymentSupport')render(false);}
async function payHelpLoad(s,more=false){
 if(s.loading||!psCurrent(s.actor)||state.page!=='paymentSupport')return;
 const serial=++s.serial,orderId=s.orderId;
 const current=()=>payHelpSession===s&&psCurrent(s.actor)&&serial===s.serial;
 s.loaded=true;s.loading=true;s.error='';payHelpRender(s);
 try{
  const [list,payment]=await Promise.allSettled([
   pxApi('payment-support/tickets'+(more?'?before='+encodeURIComponent(s.next):'')),
   orderId&&!more?pxApi('payment-support/orders/'+encodeURIComponent(orderId)):s.payment
  ]);
  if(!current())return;
  if(list.status==='fulfilled'){
   const items=list.value.items;
   s.items=more?s.items.concat(items.filter(item=>!s.items.some(old=>old.id===item.id))):items;
   s.next=list.value.next;
  }
  if(payment.status==='fulfilled')s.payment=payment.value;
  const failure=[list,payment].find(result=>result.status==='rejected');
  if(failure)s.error=payHelpError(failure.reason);
 }finally{if(current()){s.loading=false;payHelpRender(s);}}
}
document.addEventListener('click',event=>{
 const control=event.target.closest('[data-pay-help]');if(!control)return;
 event.preventDefault();event.stopImmediatePropagation();
 const s=payHelpState(),action=control.dataset.payHelp,form=document.getElementById('pay-help-form');
 if(action==='open'){
  const orderId=control.dataset.order||'';
  if(s.orderId!==orderId){s.orderId=orderId;s.payment=null;s.eventId='';}
  if(control.dataset.kind)s.kind=control.dataset.kind;
  s.serial++;s.loading=false;s.loaded=false;s.error='';
  navigate('paymentSupport');return;
 }
 if(form)payHelpReadForm(s,form);
 if(action==='clear'){
  s.serial++;s.loading=false;s.orderId='';s.payment=null;s.eventId='';s.error='';
  payHelpRender(s);return;
 }
 if(action==='refresh'||action==='more')payHelpLoad(s,action==='more');
},true);
document.addEventListener('input',event=>{
 const form=event.target.closest('#pay-help-form');if(!form)return;
 const s=payHelpState();payHelpReadForm(s,form);
 if(event.target.name==='kind'){
  payHelpRender(s);
  document.querySelector('#pay-help-form [name=kind]')?.focus({preventScroll:true});
 }
});
document.addEventListener('submit',async event=>{
 const form=event.target;if(form.id!=='pay-help-form')return;
 event.preventDefault();event.stopImmediatePropagation();
 const s=payHelpState();
 if(s.sending||s.loading)return;
 payHelpReadForm(s,form);
 const body={kind:s.kind,orderId:s.orderId,eventId:s.eventId,message:s.message.trim()},signature=JSON.stringify(body);
 if(s.signature!==signature){s.signature=signature;s.requestId=crypto.randomUUID();}
 s.sending=true;s.error='';s.notice='';payHelpRender(s);
 try{
  const {ticket}=await pxApi('payment-support/tickets',{...body,requestId:s.requestId},'POST',{timeout:12000});
  if(!psCurrent(s.actor))return;
  if(s.message.trim()===body.message)s.message='';
  s.signature='';s.latest=ticket.id;s.items=[ticket,...s.items.filter(item=>item.id!==ticket.id)];
  s.notice=payHelpCopy('Support request submitted.','客服工单已提交。','客服單已提交。','ཞབས་ཞུའི་ཞུ་བ་ཕུལ་ཟིན།');
 }catch(error){if(psCurrent(s.actor))s.error=payHelpError(error);}
 finally{s.sending=false;payHelpRender(s);}
},true);
