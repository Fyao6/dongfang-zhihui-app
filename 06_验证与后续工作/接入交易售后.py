from pathlib import Path
R=Path(__file__).resolve().parent.parent
p=R/'04_研发源码/app/r4/commerce-ui.js'
s=p.read_text(encoding='utf-8')
def change(old,new):
 global s
 if new in s:return
 assert s.count(old)==1,old[:100]
 s=s.replace(old,new,1)
change("function coOrderPage(){",'''function coAftersaleHistory(o){const items=o.aftersaleRequests||[];return items.length?`<section class="co-aftersale-list"><h3>${coText('After-sales requests','售后进度','售後進度','ཉོ་རྗེས་ཞབས་ཞུ།')}</h3>${items.map(x=>`<article><p>${esc(x.reason)}</p><small>${x.status==='pending'?coText('Awaiting review','待处理','待處理','ལྟ་ཞིབ་སྒུག'):esc(x.status)}</small></article>`).join('')}</section>`:'';}
function coOpenAftersale(){const s=coState();sheet(coText('Request after-sales support','申请售后','申請售後','ཉོ་རྗེས་ཞབས་ཞུ་འདྲི།'),`<p>${esc(s.orderId)}</p><form id="co-aftersale-form"><label>${coText('Reason','申请理由','申請理由','རྒྱུ་མཚན།')}<textarea name="reason" minlength="5" maxlength="1000" required></textarea></label><p>${coText('Submitting a request does not issue a refund. Its progress remains available in your order.','提交申请后由客服处理，不会立即退款。处理进度保留在订单中。','提交申請後由客服處理，不會立即退款。處理進度保留在訂單中。','ཞུ་བ་བཏང་རྗེས་ཞབས་ཞུས་ལྟ་ཞིབ་བྱེད།')}</p><p data-co-aftersale-error role="alert"></p><button type="submit" class="btn full">${coText('Submit request','提交申请','提交申請','ཞུ་བ་འབུལ།')}</button></form>`);}
function coOrderPage(){''')
change('</dl>${pending&&o.environment', '</dl>${coAftersaleHistory(o)}${pending&&o.environment')
start=s.index(" if(a==='support'){")
end=s.index('\n},true);',start)
s=s[:start]+" if(a==='support')coOpenAftersale();"+s[end:]
change(" if(event.target.id!=='co-checkout-form')return;",''' if(event.target.id==='co-aftersale-form'){
  event.preventDefault();event.stopImmediatePropagation();const form=event.target;if(!form.checkValidity())return;const reason=String(new FormData(form).get('reason')||'').trim(),output=form.querySelector('[data-co-aftersale-error]');
  coMutation(async active=>{const signature=active.orderId+':'+reason;if(active.aftersaleSignature!==signature){active.aftersaleRequest=crypto.randomUUID();active.aftersaleSignature=signature;}try{await pxApi('commerce/orders/'+encodeURIComponent(active.orderId)+'/aftersale',{requestId:active.aftersaleRequest,reason});if(coActive(active)){active.aftersaleRequest=null;closeSheet();}}catch(error){if(output?.isConnected)output.textContent=error.message;throw error;}});return;
 }
 if(event.target.id!=='co-checkout-form')return;''')
change("active.checkoutRequest=active.checkoutRequest||crypto.randomUUID();", "const signature=JSON.stringify({environment:active.environment,items,address:active.address});if(active.checkoutSignature!==signature){active.checkoutRequest=crypto.randomUUID();active.checkoutSignature=signature;}active.checkoutRequest=active.checkoutRequest||crypto.randomUUID();")
change("ready:coText('Access granted'", "fulfilled:coText('Access granted','权限已发放','權限已發放','བལྟ་བའི་ཆོག་མཆན་སྤྲད།'),awaiting_fulfillment:coText('Awaiting fulfilment','待履约','待履約','སྐྱེལ་འདྲེན་སྒུག'),ready:coText('Access granted'")
p.write_text(s,encoding='utf-8')
print('Connected real after-sales requests and progress; corrected transaction status labels.')
