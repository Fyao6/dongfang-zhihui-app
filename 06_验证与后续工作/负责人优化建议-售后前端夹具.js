// Explicit synthetic browser/account/API fixtures. Never included in a product build.
window.__actor={scope:'account-A',epoch:1};window.state={page:'afterSalesCenter',lang:'en',mode:'night',nav:'afterSales',authEpoch:1,seq:0,user:{id:'admin-A',role:'admin'}};window.px={user:{id:'account-A'}};
window.screens={};window.__calls=[];window.__deny=false;window.__hold=null;window.__settings={sandboxEnabled:true,productionEnabled:false,ruleVersion:'fixture-test-v1'};
window.flText=(en,zh,hant,bo)=>({'zh':zh,'zh-Hant':hant,'bo':bo}[state.lang]||en);
window.psToken=()=>({...__actor});window.psCurrent=t=>t.scope!==null&&t.scope===__actor.scope&&t.epoch===__actor.epoch;
window.esc=v=>String(v??'').replace(/[&<>"]/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[x]));
window.pxTop=t=>'<header><h1>'+esc(t)+'</h1></header>';window.ewFormatDate=d=>d.toISOString().slice(0,10);window.coMoney=(n,c)=>n+' '+c+' minor';
window.render=()=>{document.documentElement.lang=state.lang;document.body.dataset.mode=state.mode;document.querySelector('#app').innerHTML=screens[state.page]?.()||'<p data-other-page>Other page</p>';};
window.navigate=p=>{state.page=p;render();};window.persist=()=>true;
window.__case={id:'case-A',ownerId:'account-A',environment:'sandbox',sandboxOnly:true,productionEnabled:false,orderId:'order-A',type:'return',reason:'Fixture return reason',ruleVersion:'fixture-test-v1',status:'accepted',version:2,
 items:[{id:'case-item-A',itemId:'item-A',skuId:'sku-A',type:'physical',quantity:2,receivedQuantity:0,restockedQuantity:0,originalQuantity:3,orderItemRefundedQuantity:0,snapshot:{title:'Synthetic physical item',priceMinor:1000,currency:'USD'}}],
 shipments:[],inspections:[],history:[{id:'action-A',actorId:'admin-A',kind:'accept',data:{reason:'Fixture acceptance only'},created:1794490000000}],created:1794490000000,updated:1794490000000,
 money:{source:'original-commerce-payment-events',caseRefundLinked:false,caseRefundConfirmed:false,actualFundsMoved:false,orderPaymentStatus:'paid',orderFulfillmentStatus:'delivered',currency:'USD',orderTotalMinor:3000,orderRefundedMinor:0,events:[]}};
window.__eligible={orderId:'order-A',environment:'sandbox',sandboxOnly:true,settings:__settings,paymentConfirmed:true,legacyPending:false,canApply:true,paymentStatus:'paid',fulfillmentStatus:'delivered',
 items:[{itemId:'item-A',skuId:'sku-A',title:'Synthetic physical item',type:'physical',quantity:3,refundedQuantity:0,claimedQuantity:0,autoRestockedQuantity:0,availableReturnQuantity:3,availableRefundOnlyQuantity:3,priceMinor:1000,currency:'USD',snapshot:{refundPolicy:'Fixture test terms'}}]};
window.__reply=(path,body,method)=>{
 if(__deny&&path.startsWith('admin/'))throw Object.assign(Error('Fixture access revoked'),{status:403});
 if(method==='GET'){
  if(path.startsWith('after-sales/config'))return {settings:__settings,environment:path.includes('sandbox')?'sandbox':'production',productionEnabled:false,refundsFunds:false};
  if(path.startsWith('after-sales/orders/'))return {...__eligible,settings:__settings,canApply:__settings.sandboxEnabled};
  if(path.startsWith('admin/after-sales/cases/')||path.startsWith('after-sales/cases/'))return __case;
  if(path.startsWith('admin/after-sales'))return {items:[__case],settings:__settings,environment:'sandbox'};
  if(path.startsWith('after-sales/cases'))return {items:__actor.scope==='account-A'&&path.includes('sandbox')?[__case]:[],settings:__settings};
 }
 if(path==='admin/after-sales/settings'){__settings={...body};return {settings:__settings};}
 if(path==='after-sales/cases'){__case={...__case,id:'created-case',status:'submitted',version:1,reason:body.reason};return {item:__case};}
 if(path.endsWith('/return-shipping')){__case={...__case,status:'returning',version:__case.version+1,shipments:[...__case.shipments,{id:'shipment-fixture',carrier:body.carrier,trackingNumber:body.trackingNumber,created:1794490000000,carrierVerified:false}]};return {item:__case};}
 if(path.endsWith('/decision')){__case={...__case,status:body.decision==='accept'?'accepted':'rejected',version:__case.version+1};return {item:__case};}
 if(path.endsWith('/inspect')){__case={...__case,status:'partially_received',version:__case.version+1,items:__case.items.map(x=>({...x,receivedQuantity:x.receivedQuantity+body.items[0].receivedQuantity,restockedQuantity:x.restockedQuantity+body.items[0].restockQuantity})),inspections:[{id:'receipt-fixture',receiptReference:body.receiptReference,note:body.note,created:1794490000000,items:body.items.map(x=>({...x,id:'inspection-item',inventoryEventId:'fixture-inventory-event'}))}]};return {item:__case};}
 throw Error('Unexpected fixture API path '+path);
};
window.__request=async(path,body,method)=>{method=method||(body?'POST':'GET');__calls.push({path,method,body:body?JSON.parse(JSON.stringify(body)):null});const result=JSON.parse(JSON.stringify(__reply(path,body,method)));const h=__hold;if(h&&!h.used&&h.path===path&&h.method===method){h.used=true;h.entered=true;await new Promise(resolve=>h.release=resolve);}return result;};
Object.defineProperty(window,'pxApi',{value:__request,writable:false});Object.defineProperty(window,'api',{value:__request,writable:false});
window.labels={};window.authCurrent=e=>e===state.authEpoch;window.heading=(t,a='')=>'<h1>'+esc(t)+'</h1>'+a;window.coAdminPrice=(n,c)=>n+' '+c+' minor';
window.table=(headers,rows)=>'<table><thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
window.load=async nav=>{state.nav=nav;state.seq++;document.querySelector('#main').innerHTML='<p>Other admin page</p>';};

