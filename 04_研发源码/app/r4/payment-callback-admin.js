// Durable sandbox receipts. Credentials and signature material stay on the server.
const callbackStatuses={received:'待处理',processing:'处理中',retry:'等待重试',applied:'已应用',manual_review:'待人工核查'};
const callbackErrors={late_refund_pending:'迟到付款已进入退款待办',late_transaction_conflict:'订单已有其他迟到付款记录',unknown_order:'未找到对应订单',amount_currency_mismatch:'金额或币种与订单不一致',order_not_payable:'订单已关闭、已付款或已退款',invalid_order_items:'订单项目异常',unsupported_order_type:'此类订单需单独核查',reservation_unavailable:'库存预占状态不符合要求',application_conflict:'应用时订单状态发生冲突',storage_unavailable:'处理暂时失败，可重试',adapter_disabled:'沙箱回调适配未启用',commerce_sandbox_disabled:'沙箱交易已关闭',transaction_already_applied:'同一笔交易已经应用',order_not_found:'未找到对应订单',amount_mismatch:'金额与订单不一致',currency_mismatch:'币种与订单不一致',order_expired:'订单预占已到期',order_closed:'订单已关闭',order_already_paid:'订单已有其他付款',order_refunded:'订单已退款',account_closed:'订单账号已关闭',sandbox_disabled:'沙箱交易已关闭',membership_requires_adapter:'会员订单需单独核查',product_unavailable:'商品已下架',reservation_invalid:'库存预占状态不符合要求',transaction_conflict:'交易编号与其他付款冲突',processing_failed:'处理暂时失败',retry_exhausted:'已达到重试上限',lease_expired:'上次处理已中断'};
let callbackAdminSession;
const callbackAdminStyles=`<style>
#payment-callback-admin .table-wrap{overflow-x:auto;overscroll-behavior-x:contain}
#payment-callback-admin table{min-width:850px;table-layout:fixed}
#payment-callback-admin th:first-child{width:300px}
#payment-callback-admin th:nth-child(2){width:95px}
#payment-callback-admin th:nth-child(3),#payment-callback-admin th:nth-child(4){width:85px}
#payment-callback-admin th:nth-child(5){width:180px}
#payment-callback-admin th:nth-child(6){width:105px}
#payment-callback-admin td:first-child{overflow-wrap:anywhere;word-break:break-word}
#payment-callback-admin td:nth-child(2),#payment-callback-admin td:nth-child(5){white-space:nowrap}
#callback-receipt-detail table{min-width:690px}
#callback-receipt-detail th:first-child{width:180px}
#callback-receipt-detail th:nth-child(2){width:85px}
#callback-receipt-detail th:nth-child(3){width:105px}
#callback-receipt-detail th:nth-child(4){width:100px}
#callback-receipt-detail th:nth-child(5){width:220px}
#callback-receipt-detail td:first-child{white-space:nowrap}
#callback-receipt-detail td:nth-child(5){white-space:normal}
</style>`;
function callbackAdminState(){
 if(!callbackAdminSession||callbackAdminSession.epoch!==state.authEpoch||callbackAdminSession.seq!==state.seq)
  callbackAdminSession={epoch:state.authEpoch,seq:state.seq,filter:'',items:[],next:null};
 return callbackAdminSession;
}
function callbackAdminActive(s){return authCurrent(s.epoch)&&s.seq===state.seq&&state.nav==='commerce'&&state.user?.role==='admin';}
function callbackAdminPanel(){return '<section class="panel" id="payment-callback-admin">'+callbackAdminStyles+'<h2>支付回调收件箱</h2><p class="hint">查看沙箱通知的接收与处理进度。正式支付渠道尚未启用。</p><button type="button" class="btn secondary" data-callback-action="load">查看回调收件箱</button></section>';}
function callbackTime(value){return value?new Date(value).toLocaleString('zh-CN'):'—';}
function callbackProblem(code){return callbackErrors[code]||code||'—';}
function callbackAdminRender(s){
 const panel=document.getElementById('payment-callback-admin');if(!panel||!callbackAdminActive(s))return;
 const item=s.detail?.item;
 panel.innerHTML=`${callbackAdminStyles}<h2>支付回调收件箱</h2><p class="hint">正式支付渠道尚未启用。收到通知仅表示已保存；订单是否付款，以处理结果为准。当前支持数字与实物沙箱订单，异常及会员通知保留待核查。</p>
 <div class="list-tools"><label>处理状态<select id="callback-status-filter"><option value="">全部状态</option>${Object.entries(callbackStatuses).map(([key,label])=>`<option value="${key}" ${s.filter===key?'selected':''}>${label}</option>`).join('')}</select></label>
 <button class="btn secondary" type="button" data-callback-action="load" ${s.busy?'disabled':''}>刷新收件箱</button>
 <button class="btn secondary" type="button" data-callback-action="process" ${s.busy||!s.loaded?'disabled':''}>处理最多10条待处理通知</button></div>
 <p class="hint">处理按钮从全部待处理通知中领取，状态筛选只影响列表。等待重试的通知到期后才可领取。</p>
 ${s.busy?'<p role="status">正在处理…</p>':''}${s.error?`<p class="error" role="alert">${esc(s.error)}</p>`:''}${s.notice?`<p role="status">${esc(s.notice)}</p>`:''}
 ${s.items.length?table(['通知与订单','状态','接收次数','处理次数','最近更新','操作'],s.items.map(row=>[
  esc(row.eventId)+'<br>'+esc(row.orderId),esc(callbackStatuses[row.status]||row.status),Number(row.receivedCount),Number(row.attempts),esc(callbackTime(row.updated)),
  `<button type="button" class="btn secondary small" data-callback-action="view" data-id="${esc(row.id)}" ${s.busy?'disabled':''}>查看通知</button>`
 ])):`<p class="hint">${s.loaded?'暂无符合条件的通知。':'点击查看收件箱以读取记录。'}</p>`}
 ${s.next?`<button type="button" class="btn secondary" data-callback-action="more" ${s.busy?'disabled':''}>更早的通知</button>`:''}
 ${item?`<section class="panel" id="callback-receipt-detail"><h3>通知详情 · ${esc(callbackStatuses[item.status]||item.status)}</h3>
 <p style="overflow-wrap:anywhere">通知编号：${esc(item.eventId)}<br>交易编号：${esc(item.transactionId)}<br>订单编号：${esc(item.orderId)}<br>金额：${esc(coAdminPrice(item.amountMinor,item.currency))}<br>接收时间：${esc(callbackTime(item.created))}<br>下次重试：${esc(callbackTime(item.nextAttempt))}<br>问题：${esc(callbackProblem(item.lastError))}</p>
 ${item.duplicate?'<p class="hint">此通知属于同一笔交易的重复接收，不会再次发放权益或扣减库存。</p>':''}
 ${['retry','manual_review'].includes(item.status)&&item.attempts<5&&!item.duplicate?`<p class="hint">核对问题后可重新排队，累计最多处理5次。重新排队不会直接改动订单。</p><button type="button" class="btn secondary" data-callback-action="retry" data-id="${esc(item.id)}" ${s.busy?'disabled':''}>重新排队</button>`:''}
 ${(s.detail.attempts||[]).length?table(['时间','处理次数','操作','结果','问题'],s.detail.attempts.map(row=>[esc(callbackTime(row.created)),Number(row.attempt),esc(({claim:'领取',apply:'应用',retry:'重新排队',receive:'接收',duplicate:'重复接收',recover:'中断恢复',complete:'处理结束',failed:'处理失败'})[row.action]||row.action),esc(callbackStatuses[row.result]||row.result),esc(callbackProblem(row.errorCode))])):'<p class="hint">尚无处理记录。</p>'}
 </section>`:''}`;
}
async function callbackAdminLoad(s,more=false){
 const query=new URLSearchParams();if(s.filter)query.set('status',s.filter);if(more)query.set('before',s.next);
 const data=await api('admin/payment-callbacks?'+query);if(!callbackAdminActive(s))return;
 s.items=more?s.items.concat(data.items.filter(item=>!s.items.some(old=>old.id===item.id))):data.items;s.next=data.next;s.loaded=true;
}
async function callbackAdminRun(s,work){
 if(s.busy||!callbackAdminActive(s))return;s.busy=true;s.error='';s.notice='';callbackAdminRender(s);
 try{await work();}catch(error){if(callbackAdminActive(s)&&!error.handled)s.error=error.message;}
 finally{s.busy=false;callbackAdminRender(s);}
}
document.addEventListener('click',event=>{
 const control=event.target.closest('[data-callback-action]');if(!control)return;
 event.preventDefault();event.stopImmediatePropagation();const s=callbackAdminState(),action=control.dataset.callbackAction;
 callbackAdminRun(s,async()=>{
  if(action==='view'){
   const detail=await api('admin/payment-callbacks/'+encodeURIComponent(control.dataset.id));if(callbackAdminActive(s))s.detail=detail;return;
  }
  if(action==='process'){
   const result=await api('admin/payment-callbacks/process',{limit:10});if(!callbackAdminActive(s))return;
   s.notice=`本次处理 ${result.processed} 条通知。请查看各通知的处理结果。`;
  }else if(action==='retry'){
   await api('admin/payment-callbacks/'+encodeURIComponent(control.dataset.id)+'/retry',{});if(!callbackAdminActive(s))return;
   s.notice='已重新排队，请核对问题后处理待处理通知。';
  }
  if(s.detail){const detail=await api('admin/payment-callbacks/'+encodeURIComponent(s.detail.item.id));if(!callbackAdminActive(s))return;s.detail=detail;}
  await callbackAdminLoad(s,action==='more');
 });
},true);
document.addEventListener('change',event=>{
 if(event.target.id!=='callback-status-filter')return;
 const s=callbackAdminState();s.filter=event.target.value;s.next=null;callbackAdminRun(s,()=>callbackAdminLoad(s));
});
