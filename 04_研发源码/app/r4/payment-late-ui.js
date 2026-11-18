// PAY10/PAY13: display only the persisted, owner-scoped settlement result.
function latePaymentStatus(value){return ({
 fulfilled:coText('Late payment processed','迟到付款已处理','遲到付款已處理','དུས་ལས་འཕྱི་བའི་དངུལ་སྤྲོད་ལེགས་གྲུབ།'),
 refund_pending:coText('Refund review pending','等待退款处理','等待退款處理','དངུལ་ཕྱིར་སྤྲོད་ལྟ་ཞིབ་སྒུག'),
 refund_processing:coText('Refund review accepted','退款待办已受理','退款待辦已受理','དངུལ་ཕྱིར་སྤྲོད་ལྟ་ཞིབ་དང་ལེན་བྱས།')
})[value]||coText('Payment needs review','付款需要核查','付款需要核查','དངུལ་སྤྲོད་ལྟ་ཞིབ་དགོས།');}
function latePaymentPanel(order){
 const item=order.latePayment;if(!item)return '';
 const fulfilled=item.status==='fulfilled';
 return `<section id="payment-late-notice" class="co-order-detail" aria-labelledby="payment-late-title"><h3 id="payment-late-title">${latePaymentStatus(item.status)}</h3>
 <p role="status">${fulfilled?coText('Payment was confirmed after the reservation expired. Stock was checked again and this order resumed at its original price. See the fulfilment status for delivery progress.','库存预占到期后确认付款，已重新核查库存，并按原成交价格接续订单。实物配送进度请查看履约状态。','庫存預占到期後確認付款，已重新核查庫存，並按原成交價格接續訂單。實物配送進度請查看履約狀態。','དངུལ་སྤྲོད་དུས་ལས་འཕྱི་བས། མཛོད་ཉར་བསྐྱར་བཤེར་བྱས་ནས་ཉོ་ཐོ་ལེགས་གྲུབ།'):coText('Payment was confirmed after the reservation expired, but this order could not be fulfilled. A refund task was saved for support to review.','库存预占到期后确认付款，此订单未能履约，已保存退款待办供客服处理。','庫存預占到期後確認付款，此訂單未能履約，已儲存退款待辦供客服處理。','དངུལ་སྤྲོད་དུས་ལས་འཕྱི་བས་ཉོ་ཐོ་མ་གྲུབ། དངུལ་ཕྱིར་སྤྲོད་ལྟ་ཞིབ་ཟིན་ཐོ་ཉར་ཟིན།')}</p>
 ${!fulfilled?`<p>${coText('A saved or accepted task does not mean a refund has arrived. Reopen this order to check progress or contact payment support.','待办已保存或已受理，不代表退款到账。重新打开此订单可查看进度，也可进入支付帮助。','待辦已儲存或已受理，不代表退款到帳。重新開啟此訂單可查看進度，也可進入付款協助。','ཟིན་ཐོ་ཉར་བ་དང་དང་ལེན་བྱས་པས་དངུལ་ཕྱིར་འབྱོར་བ་མི་མཚོན། ཉོ་ཐོ་བསྐྱར་ཕྱེ་ནས་ལྟ་ཆོག')}</p>`:''}
 <p class="co-order-id">${coText('Record','处理记录','處理紀錄','ཟིན་ཐོ།')} ${esc(item.id)}</p></section>`;
}
