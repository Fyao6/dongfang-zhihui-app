// Connection feedback uses the existing page; retries never navigate or resend writes.
function fwText(en,zh,hant,bo){return flText(en,zh,hant,bo);}
function fwCaptureForms(){return [...document.querySelectorAll('#app form')].map(form=>({id:form.id,fields:[...form.elements].filter(e=>e.name&&!['password','file','hidden','submit','button'].includes(e.type)).map(e=>({name:e.name,type:e.type,value:e.value,checked:e.checked}))}));}
function fwRestoreForms(forms){for(const row of forms||[]){const form=document.getElementById(row.id);if(!form)continue;for(const field of row.fields){for(const element of form.elements){if(element.name!==field.name||element.type!==field.type||['radio','checkbox'].includes(element.type)&&element.value!==field.value)continue;if(['radio','checkbox'].includes(element.type))element.checked=field.checked;else element.value=field.value;}}}}
function fwPaintConnection(){
 const app=document.getElementById('app');if(!app)return;
 let notice=document.getElementById('fw-connection');
 const local=!pxOnline,offline=pxOnline&&navigator.onLine===false,loading=pxConnection.status==='loading'||pxConnection.status==='idle',failed=pxConnection.status==='error';
 const waiting=document.querySelector('[data-lb-loading]');
 if(waiting){const template=document.createElement('template');template.innerHTML=lbLoading();waiting.querySelector('[role="status"]').textContent=template.content.querySelector('[role="status"]').textContent;waiting.querySelector('[data-lb-action="reconnect"]').disabled=!!(lbRuntime.reconnecting||loading||offline);notice?.remove();return;}
 if(!local&&!offline&&!loading&&!failed){notice?.remove();return;}
 if(!notice){notice=document.createElement('aside');notice.id='fw-connection';notice.className='fw-connection';notice.setAttribute('role','status');app.prepend(notice);}
 const message=local?fwText('Local preview · account and server features need the online app.','本机预览：账号与后台功能需在线打开。','本機預覽：帳號與後台功能需線上開啟。','རང་འཕྲུལ་སྔོན་ལྟ། རྩིས་ཐོ་དང་ཞབས་ཞུར་དྲ་མཐུད་དགོས།'):offline?fwText('Network disconnected. Your current page stays open.','网络已断开，当前页面仍保留。','網絡已斷開，目前頁面仍保留。','དྲ་མཐུད་ཆད་འདུག ད་ལྟའི་ཤོག་ངོས་ཉར་ཡོད།'):loading?fwText('Connecting…','正在连接…','正在連線…','མཐུད་བཞིན་ཡོད།'):fwText('Connection failed. Retry to load current account and content.','连接暂未成功，请重试以读取当前账号与内容。','連線暫未成功，請重試以讀取目前帳號與內容。','མཐུད་མ་ཐུབ། རྩིས་ཐོ་དང་ནང་དོན་ཀློག་ཕྱིར་བསྐྱར་ཚོད་བྱོས།');
 const text=document.createElement('span');text.textContent=message;notice.replaceChildren(text);
 if(pxOnline){const button=document.createElement('button');button.type='button';button.className='link';button.dataset.fwAction='retry';button.disabled=loading||offline;button.textContent=fwText('Retry connection','重新连接','重新連線','བསྐྱར་མཐུད།');notice.append(button);}
}
const fwRenderBefore=renderNow;renderNow=function(reset=true){fwRenderBefore(reset);fwPaintConnection();};
document.addEventListener('click',event=>{const button=event.target.closest('[data-fw-action="retry"]');if(!button)return;event.preventDefault();event.stopImmediatePropagation();pxBootstrap();},true);
window.addEventListener('offline',fwPaintConnection);
window.addEventListener('online',()=>{fwPaintConnection();if(pxOnline&&(!px.loaded||pxConnection.status==='error'))pxBootstrap();});
fwPaintConnection();
