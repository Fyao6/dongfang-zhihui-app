// PAY09: only request an account-scoped server check; never submit payment facts.
function recoveryStatus(value){return ({
 pending:coText('Awaiting check','等待查询','等待查詢','འཚོལ་བཤེར་སྒུག'),
 processing:coText('Checking payment','正在查询付款','正在查詢付款','དངུལ་སྤྲོད་འཚོལ་བཞིན།'),
 retry:coText('Not confirmed yet','尚未确认付款','尚未確認付款','དངུལ་སྤྲོད་ངོས་མ་འཛིན།'),
 confirmed:coText('Payment confirmed','付款已确认','付款已確認','དངུལ་སྤྲོད་ངོས་འཛིན་ཟིན།'),
 unpaid:coText('Query result: unpaid','查询结果：未付款','查詢結果：未付款','འཚོལ་བཤེར་འབྲས་བུ། དངུལ་མ་སྤྲད།'),
 manual_review:coText('Needs support review','需要人工核查','需要人工核查','མིས་ལྟ་ཞིབ་དགོས།')
})[value]||coText('No recovery request yet','尚无查询记录','尚無查詢紀錄','འཚོལ་བཤེར་ཟིན་ཐོ་མེད།');}
function paymentRecoveryPanel(order){
 const s=coState(),data=s.paymentRecovery?.order?.id===order.id?s.paymentRecovery:null,job=data?.job;
 const terminal=['paid','partially_refunded','refunded','refund_pending'].includes(order.paymentStatus),processing=job?.status==='processing'&&Number(job.leaseUntil||0)>Date.now();
 return `<section class="co-order-detail payment-recovery" id="payment-recovery-panel" aria-labelledby="payment-recovery-title">
 <h3 id="payment-recovery-title">${coText('Check a payment','核查付款记录','核查付款紀錄','དངུལ་སྤྲོད་ཟིན་ཐོ་ལྟ།')}</h3>
 <p>${coText('This checks payment records. It never charges your account.','查询付款记录，不会再次扣款。','查詢付款紀錄，不會再次扣款。','དངུལ་སྤྲོད་ཟིན་ཐོ་འཚོལ། སླར་དངུལ་མི་ལེན།')}</p>
 <p role="status" data-recovery-status>${s.recoveryBusy?recoveryStatus('processing'):job?.status==='processing'&&!processing?coText('The previous check stopped. You can query again.','上次查询已中断，可以重新查询。','上次查詢已中斷，可以重新查詢。','འཚོལ་བཤེར་སྔ་མ་ཆད་སོང་། བསྐྱར་འཚོལ་བྱ་ཆོག'):recoveryStatus(job?.status)}</p>
 ${job?`<p class="hint">${coText('Attempts','已查询次数','已查詢次數','འཚོལ་བཤེར་ཐེངས།')} ${Number(job.attempts)}${job.nextAttempt?' · '+coText('Next check after','下次可查时间','下次可查時間','བསྐྱར་འཚོལ་དུས།')+' '+esc(new Date(job.nextAttempt).toLocaleString(state.lang==='bo'?'en':state.lang==='zh-Hant'?'zh-TW':state.lang)):''}</p>`:''}
 ${job?.status==='retry'?`<p>${coText('The result is not confirmed. Your order has not been marked paid. Check again later or ask payment support.','结果尚未确认，订单不会因此标记为已付款。稍后可再查询，也可进入支付帮助。','結果尚未確認，訂單不會因此標記為已付款。稍後可再查詢，也可進入付款協助。','འབྲས་བུ་ངོས་མ་འཛིན། ཕྱིས་སུ་བསྐྱར་འཚོལ་བྱ་ཆོག')}</p>`:''}
 ${job?.status==='manual_review'?`<p>${coText('Payment support needs to review this result. No new charge or automatic refund was made.','此结果需要人工核查，未再次扣款，也未自动退款。','此結果需要人工核查，未再次扣款，也未自動退款。','འབྲས་བུ་འདི་མིས་ལྟ་ཞིབ་དགོས། སླར་དངུལ་མ་བླངས།')}</p>`:''}
 ${data&&!data.queryReady?`<p>${coText('Payment query service is not connected yet. Your saved order remains available.','付款查单服务尚未接通，已保存的订单仍可回查。','付款查單服務尚未接通，已儲存的訂單仍可回查。','དངུལ་སྤྲོད་འཚོལ་བཤེར་ཞབས་ཞུ་ད་དུང་མ་མཐུད།')}</p>`:''}
 ${s.recoveryError?`<p class="co-error" role="alert">${esc(s.recoveryError)}</p>`:''}
 <div class="co-navigation"><button type="button" class="btn secondary" data-recovery-action="query" data-id="${esc(order.id)}" ${s.busy||s.recoveryBusy||processing||terminal||!data?.queryReady||job?.status==='manual_review'?'disabled':''}>${coText('Query payment record','查询付款记录','查詢付款紀錄','དངུལ་སྤྲོད་ཟིན་ཐོ་འཚོལ།')}</button>
 <button type="button" class="btn secondary" data-recovery-action="refresh" data-id="${esc(order.id)}" ${s.recoveryBusy?'disabled':''}>${coText('Refresh recovery status','刷新核查进度','重新整理核查進度','ལྟ་ཞིབ་གནས་སྟངས་བསྐྱར་ལྟ།')}</button></div>
 </section>`;
}
document.addEventListener('click',async event=>{
 const button=event.target.closest('#payment-recovery-panel [data-recovery-action]');if(!button)return;
 event.preventDefault();event.stopImmediatePropagation();
 const s=coState(),orderId=button.dataset.id;if(s.recoveryBusy||!px.user||s.orderId!==orderId)return;
 const actor=s.actor,action=button.dataset.recoveryAction;
 s.recoveryBusy=true;s.recoveryError='';render(false);
 try{
  const route='commerce/orders/'+encodeURIComponent(orderId)+'/payment-recovery';
  const reply=action==='query'?await pxApi(route,{requestId:crypto.randomUUID()}):await pxApi(route);
  if(!coActive(s)||!psCurrent(actor)||s.orderId!==orderId)return;
  s.paymentRecovery=reply;s.order={...s.order,...reply.order};
  const full=await pxApi('commerce/orders/'+encodeURIComponent(orderId));
  if(coActive(s)&&psCurrent(actor)&&s.orderId===orderId)s.order=full;
 }catch(error){if(coActive(s)&&s.orderId===orderId)s.recoveryError=error.message;}
 finally{if(coActive(s)){s.recoveryBusy=false;if(state.page==='commerceOrder')render(false);}}
},true);
