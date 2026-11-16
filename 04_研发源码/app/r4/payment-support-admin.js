const payAdminTypes={'duplicate-charge':'重复扣款','payment-missing':'支付未到账','restore-failed':'无法恢复购买','cancel-renewal':'取消订阅续费'};
const payAdminStatuses={submitted:'已提交',accepted:'处理中',resolved:'已回复并办结'};
let payAdminSession;
function payAdminState(){
 if(!payAdminSession||payAdminSession.epoch!==state.authEpoch||payAdminSession.seq!==state.seq)
  payAdminSession={epoch:state.authEpoch,seq:state.seq,filter:'',items:[],next:null};
 return payAdminSession;
}
function payAdminPanel(){
 return '<section class="panel" id="payment-support-admin"><h2>支付客服</h2><p class="hint">处理测试工单，核对订单状态与已记录的支付事件。</p><button type="button" class="btn secondary" data-pay-admin="load">查看支付工单</button></section>';
}
function payAdminActive(s){
 return authCurrent(s.epoch)&&s.seq===state.seq&&state.nav==='commerce'&&state.user?.role==='admin';
}
function payAdminRender(s){
 const panel=document.getElementById('payment-support-admin');
 if(!payAdminActive(s)||!panel)return;
 const ticket=s.detail?.ticket,payment=s.detail?.payment;
 panel.innerHTML=`<h2>支付客服</h2><div class="actions"><label>工单状态 <select id="pay-admin-filter">
 <option value="">全部状态</option>${Object.entries(payAdminStatuses).map(([key,label])=>`<option value="${key}" ${s.filter===key?'selected':''}>${label}</option>`).join('')}</select></label>
 <button type="button" class="btn secondary" data-pay-admin="load" ${s.busy?'disabled':''}>刷新工单</button></div>
 ${s.busy?'<p role="status">正在处理…</p>':''}${s.error?`<p class="error" role="alert">${esc(s.error)}</p>`:''}
 ${s.items.length?table(['工单','问题','状态','订单','操作'],s.items.map(item=>[
  esc(item.id),payAdminTypes[item.kind],payAdminStatuses[item.status],esc(item.orderId||'未关联'),
  `<button type="button" class="btn secondary small" data-pay-admin="view" data-id="${esc(item.id)}" ${s.busy?'disabled':''}>查看工单</button>`
 ])):`<p class="hint">${s.loaded?'暂无符合条件的工单。':''}</p>`}
 ${s.next?`<button type="button" class="btn secondary" data-pay-admin="more" ${s.busy?'disabled':''}>更早的工单</button>`:''}
 ${ticket?`<section class="panel"><h3>${payAdminTypes[ticket.kind]} · ${payAdminStatuses[ticket.status]}</h3>
 <p style="overflow-wrap:anywhere;white-space:pre-wrap">${esc(ticket.message)}</p>
 ${payment?`<p>订单 ${esc(payment.order.id)} · ${coAdminStatus(payment.order.paymentStatus)} · ${coAdminStatus(payment.order.fulfillmentStatus)} · ${esc(coAdminPrice(payment.order.totalMinor,payment.order.currency))}</p>
 ${payment.events.length?table(['记录编号','类型','金额','时间'],payment.events.map(e=>[
  esc(e.id)+(e.id===ticket.eventId?'（已关联）':''),e.kind==='refund'?'测试退款':'测试支付',esc(coAdminPrice(e.amountMinor,e.currency)),esc(new Date(e.created).toLocaleString('zh-CN'))
 ])):'<p>此订单暂无支付记录。</p>'}`:'<p>此工单未关联订单。</p>'}
 ${ticket.replies.map(r=>`<p style="overflow-wrap:anywhere;white-space:pre-wrap"><strong>${payAdminStatuses[r.status]}</strong> · ${esc(new Date(r.created).toLocaleString('zh-CN'))}<br>${esc(r.reply)}</p>`).join('')}
 ${ticket.status!=='resolved'&&!s.detail.accountClosed?`<form id="pay-admin-action" class="grid-form"><label class="wide">给用户的回复${ticket.status==='submitted'?'（选填）':''}<textarea name="reply" rows="3" maxlength="750" ${ticket.status==='accepted'?'required':''} ${s.busy?'disabled':''}>${esc(s.reply||'')}</textarea></label>
 <p class="hint wide">填写核查结果或下一步操作，请勿填写支付凭据和敏感资料。</p><button type="submit" class="btn" ${s.busy?'disabled':''}>${ticket.status==='submitted'?'受理工单':'回复并办结'}</button></form>`:''}
 ${s.detail.accountClosed?'<p class="hint">账号已关闭，工单正文已清理。</p>':''}
 </section>`:''}`;
}
async function payAdminLoad(s,more=false){
 const query=new URLSearchParams();
 if(s.filter)query.set('status',s.filter);
 if(more)query.set('before',s.next);
 const data=await api('admin/payment-support/tickets?'+query);
 if(!payAdminActive(s))return;
 s.loaded=true;s.items=more?s.items.concat(data.items.filter(item=>!s.items.some(old=>old.id===item.id))):data.items;s.next=data.next;
}
async function payAdminRun(s,work){
 if(s.busy||!payAdminActive(s))return;
 const reply=document.querySelector('#pay-admin-action textarea');
 if(reply)s.reply=reply.value;
 s.busy=true;s.error='';payAdminRender(s);
 try{await work();}
 catch(error){if(payAdminActive(s)&&!error.handled)s.error=error.message;}
 finally{s.busy=false;payAdminRender(s);}
}
document.addEventListener('click',event=>{
 const control=event.target.closest('[data-pay-admin]');if(!control)return;
 event.preventDefault();event.stopImmediatePropagation();
 const s=payAdminState(),action=control.dataset.payAdmin;
 payAdminRun(s,async()=>{
  if(action==='view'){
   const detail=await api('admin/payment-support/tickets/'+encodeURIComponent(control.dataset.id));
   if(!payAdminActive(s))return;
   if(s.detail?.ticket.id!==detail.ticket.id)s.reply='';
   s.detail=detail;
  }else{
   if(action==='load'&&s.detail){
    s.detail=await api('admin/payment-support/tickets/'+encodeURIComponent(s.detail.ticket.id));
   }
   await payAdminLoad(s,action==='more');
  }
 });
},true);
document.addEventListener('change',event=>{
 if(event.target.id!=='pay-admin-filter')return;
 const s=payAdminState();s.filter=event.target.value;s.next=null;
 payAdminRun(s,()=>payAdminLoad(s));
});
document.addEventListener('submit',event=>{
 if(event.target.id!=='pay-admin-action')return;
 event.preventDefault();event.stopImmediatePropagation();
 const s=payAdminState(),ticket=s.detail?.ticket;
 if(!ticket)return;
 const reply=new FormData(event.target).get('reply').trim();
 const body={version:ticket.version,status:ticket.status==='submitted'?'accepted':'resolved',reply};
 const signature=JSON.stringify([ticket.id,body]);
 if(s.signature!==signature){s.signature=signature;s.requestId=crypto.randomUUID();}
 payAdminRun(s,async()=>{
  const data=await api('admin/payment-support/tickets/'+encodeURIComponent(ticket.id)+'/actions',{...body,requestId:s.requestId});
  if(!payAdminActive(s))return;
  s.detail.ticket=data.ticket;s.reply='';s.signature='';
  await payAdminLoad(s);
 });
},true);
