// Automatic app-session ledger. Visibility and dragging never change accumulation.
let TB_KEY=personalStorage.scope?'ew-time-bank-v2:'+personalStorage.scope:'';
const tbZone=Intl.DateTimeFormat().resolvedOptions().timeZone||'Asia/Shanghai';
const tbRead=()=>{try{return initial.persist===false||!TB_KEY?null:JSON.parse(localStorage.getItem(TB_KEY)||(personalStorage.scope==='guest'&&(!psRead('eastern-wisdom-time-bank-v1')?.accountId||['local','guest'].includes(psRead('eastern-wisdom-time-bank-v1')?.accountId))?localStorage.getItem('eastern-wisdom-time-bank-v1'):null)||'null');}catch{return null;}};
const tbSaved=tbRead(),tbUid=()=>crypto.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2);
const tbLegacy=psRead('eastern-wisdom-time-bank-v1')||{},tbPrefs=psRead('ew-timer-preferences-v1')||tbLegacy;
const timeBank={version:2,zone:tbZone,accountId:personalStorage.scope||'pending',visible:tbPrefs.visible!==false,collapsed:tbPrefs.collapsed===true,position:tbPrefs.position||{x:.5,y:1},dock:tbPrefs.dock,runs:[],lastSeen:Date.now(),...tbSaved,visible:tbPrefs.visible!==false,collapsed:tbPrefs.collapsed===true,position:tbPrefs.position||{x:.5,y:1},dock:tbPrefs.dock};
timeBank.collapsed=timeBank.collapsed===true;
if(!Array.isArray(timeBank.runs))timeBank.runs=[];
timeBank.runs=timeBank.runs.filter(r=>r&&Number.isFinite(r.start)&&(r.end===null||Number.isFinite(r.end)&&r.end>=r.start));
try{new Intl.DateTimeFormat('en',{timeZone:timeBank.zone}).format();}catch{timeBank.zone=tbZone;}
timeBank.position={x:.5,y:1,...timeBank.position};
for(const k of ['x','y'])timeBank.position[k]=Math.max(0,Math.min(1,Number(timeBank.position[k])||0));
timeBank.dock=['left','right'].includes(timeBank.dock)?timeBank.dock:timeBank.position.x<.5?'left':'right';
timeBank.position.x=timeBank.dock==='left'?0:1;
let tbFloatMotion=null;
let tbFloatPointerActive=false;
const tbBackend={enabled:initial.backend===true||['http:','https:'].includes(location.protocol),connected:false,pending:false,error:'',serverAt:0,monotonicAt:0};
let tbRequestRevision=0;
const tbActive=()=>timeBank.runs.find(r=>r.end===null);
function tbSave(){if(initial.persist===false)return true;if(!TB_KEY)return false;try{localStorage.setItem(TB_KEY,JSON.stringify(timeBank));const p=JSON.stringify({visible:timeBank.visible,collapsed:timeBank.collapsed,position:timeBank.position,dock:timeBank.dock});if(localStorage.getItem('ew-timer-preferences-v1')!==p)localStorage.setItem('ew-timer-preferences-v1',p);return true;}catch{return false;}}
function tbSwitchScope(scope){const active=tbActive();if(active)active.end=Math.max(active.start,timeBank.lastSeen||active.start);tbSave();++tbRequestRevision;Object.assign(tbBackend,{connected:false,pending:false,error:'',serverAt:0,monotonicAt:0});TB_KEY=scope?'ew-time-bank-v2:'+scope:'';const saved=scope?tbRead():null;Object.assign(timeBank,{version:2,zone:tbZone,accountId:scope||'pending',runs:[],lastSeen:Date.now()},Object.fromEntries(Object.entries(saved||{}).filter(([key])=>['version','zone','accountId','runs','lastSeen'].includes(key))));if(!Array.isArray(timeBank.runs))timeBank.runs=[];if(scope)tbLocalHeartbeat();tbUpdateCounters();}
function tbNow(){return tbBackend.connected?tbBackend.serverAt+performance.now()-tbBackend.monotonicAt:Date.now();}
function tbLocalHeartbeat(){if(!personalStorage.scope)return;const now=Date.now(),active=tbActive();if(active&&(timeBank.version!==2||now-(timeBank.lastSeen||active.start)>45000)){const knownEnd=timeBank.version===2?(timeBank.lastSeen||active.start):active.start;active.end=Math.max(active.start,Math.min(now,knownEnd));}if(!tbActive())timeBank.runs.push({id:tbUid(),start:now,end:null,zone:timeBank.zone});timeBank.version=2;timeBank.lastSeen=now;tbSave();}
tbLocalHeartbeat();
function tbDayKey(ms,zone=timeBank.zone){return new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ms));}
function tbMidnightAfter(ms,zone){const parts=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(ms)).map(p=>[p.type,Number(p.value)]));const target=Date.UTC(parts.year,parts.month-1,parts.day+1);let guess=target;for(let i=0;i<4;i++){const p=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(guess)).map(x=>[x.type,Number(x.value)]));const offset=Date.UTC(p.year,p.month-1,p.day,p.hour,p.minute,p.second)-guess;guess=target-offset;}return Math.max(ms+1,guess);}
function tbSummary(now=tbNow(),runs=timeBank.runs){const days={},sessions=[];let totalMs=0;for(const r of runs){let end=Math.max(r.start,Math.min(r.end??now,now));if(r.end===null&&!tbBackend.connected)end=Math.min(end,(timeBank.lastSeen||now)+20000);const duration=Math.max(0,end-r.start);totalMs+=duration;sessions.push({...r,duration});let cursor=r.start;while(cursor<end){const stop=Math.min(end,tbMidnightAfter(cursor,r.zone||timeBank.zone)),day=tbDayKey(cursor,r.zone||timeBank.zone);days[day]=(days[day]||0)+stop-cursor;cursor=stop;}}return {todayMs:days[tbDayKey(now)]||0,totalMs,days,sessions};}
function tbClock(ms){const s=Math.max(0,Math.floor(ms/1000));return [Math.floor(s/3600),Math.floor(s%3600/60),s%60].map(x=>String(x).padStart(2,'0')).join(':');}
function tbShort(ms){const s=Math.floor(ms/1000);return s<60?s+t('s','秒'):s<3600?Math.floor(s/60)+t('m','分'):(s/3600).toFixed(1)+t('h','小时');}
function tbTodayKeyOffset(offset){const p=new Intl.DateTimeFormat('en-CA',{timeZone:timeBank.zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(tbNow()));const d=new Date(p+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+offset);return d.toISOString().slice(0,10);}
function tbApplyServer(d){if(!d||!Array.isArray(d.runs))throw new Error('Invalid ledger');timeBank.runs=d.runs;timeBank.accountId=d.accountId;timeBank.zone=d.zone;tbBackend.connected=true;tbBackend.serverAt=d.serverNow;tbBackend.monotonicAt=performance.now();timeBank.lastSeen=d.serverNow;tbSave();tbUpdateCounters();}
async function tbSync(){if(!tbBackend.enabled||tbBackend.pending||!personalStorage.scope||personalStorage.switching)return;const token=psToken(),revision=++tbRequestRevision;tbBackend.pending=true;try{const r=await fetch('/api/time-bank/heartbeat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({zone:timeBank.zone}),credentials:'same-origin'});const d=await r.json();if(!psCurrent(token)||revision!==tbRequestRevision)return;if(!r.ok)throw new Error(d.error||'Unable to sync');if(token.scope==='guest'?!String(d.accountId).startsWith('visitor:'):d.accountId!==token.scope)throw new Error(psText('Account changed. Reconnect to refresh this ledger.','账号已变化，请重新连接刷新时长。','帳號已變更，請重新連線重新整理時長。','རྩིས་ཐོ་བརྗེས་ཟིན། དུས་ཡུན་གསར་བཟོར་སླར་མཐུད་རོགས།'));tbApplyServer(d);tbBackend.error='';}catch(e){if(!psCurrent(token)||revision!==tbRequestRevision)return;tbBackend.error=e.message;if(tbBackend.connected){tbBackend.connected=false;tbLocalHeartbeat();}}finally{if(psCurrent(token)&&revision===tbRequestRevision)tbBackend.pending=false;}}
function tbSetRunning(){return true;} // Backward-compatible call sites cannot pause the ledger.
function tbSetVisible(visible){timeBank.visible=!!visible;tbSave();tbRenderFloat();if(['timeBank','timeBankSettings'].includes(state.page))render(false);}
function tbBounds(){const bar=document.getElementById('tb-float'),width=bar?.offsetWidth||210,height=bar?.offsetHeight||36,nav=document.getElementById('nav').getBoundingClientRect(),status=document.querySelector('.status').getBoundingClientRect(),view=window.visualViewport,left=view?.offsetLeft||0,top=view?.offsetTop||0,right=left+(view?.width||innerWidth),bottom=top+(view?.height||innerHeight),minY=Math.max(top+6,status.bottom+6);return {minX:left+6,maxX:Math.max(left+6,right-width-6),minY,maxY:Math.max(minY,Math.min(bottom,nav.height?nav.top:bottom)-height-9)};}
function tbPosition(){const bar=document.getElementById('tb-float');if(!bar||bar.hidden)return;const b=tbBounds();bar.style.left=b.minX+(b.maxX-b.minX)*timeBank.position.x+'px';bar.style.top=b.minY+(b.maxY-b.minY)*timeBank.position.y+'px';}
function tbSetPixelPosition(x,y){const b=tbBounds();timeBank.position={x:b.maxX===b.minX?.5:Math.max(0,Math.min(1,(x-b.minX)/(b.maxX-b.minX))),y:b.maxY===b.minY?1:Math.max(0,Math.min(1,(y-b.minY)/(b.maxY-b.minY)))};tbPosition();}
function tbStopFloatMotion(){tbFloatMotion?.cancel();tbFloatMotion=null;}
function tbSnapToEdge(side,animate=true){
 const bar=document.getElementById('tb-float');if(!bar||bar.hidden)return;
 const before=bar.getBoundingClientRect();tbStopFloatMotion();const b=tbBounds();
 timeBank.dock=side||((before.left+before.width/2)<(b.minX+b.maxX+before.width)/2?'left':'right');
 tbSetPixelPosition(timeBank.dock==='left'?b.minX:b.maxX,before.top);
 bar.dataset.dock=timeBank.dock;tbSave();
 const after=bar.getBoundingClientRect(),dx=before.left-after.left,dy=before.top-after.top;
 if(animate&&!matchMedia('(prefers-reduced-motion: reduce)').matches&&(Math.abs(dx)>.5||Math.abs(dy)>.5)){
  const motion=bar.animate([{transform:`translate(${dx}px,${dy}px)`},{transform:'translate(0,0)'}],{duration:260,easing:'cubic-bezier(.16,1,.3,1)'});tbFloatMotion=motion;
  motion.finished.then(()=>{if(tbFloatMotion===motion)tbFloatMotion=null;}).catch(()=>{});
 }
}
function tbSetCollapsed(collapsed){const bar=document.getElementById('tb-float'),box=bar?.getBoundingClientRect(),focused=bar?.contains(document.activeElement);tbStopFloatMotion();timeBank.collapsed=!!collapsed;tbRenderFloat();if(box){const b=tbBounds(),next=bar.getBoundingClientRect();tbSetPixelPosition(timeBank.dock==='left'?b.minX:b.maxX,box.top+box.height/2-next.height/2);}tbSave();if(focused)bar.querySelector('.timebar-open')?.focus({preventScroll:true});if(!matchMedia('(prefers-reduced-motion: reduce)').matches){const motion=bar.animate([{transform:'scale(.94)'},{transform:'scale(1)'}],{duration:180,easing:'cubic-bezier(.16,1,.3,1)'});tbFloatMotion=motion;motion.finished.then(()=>{if(tbFloatMotion===motion)tbFloatMotion=null;}).catch(()=>{});}}
function tbBindDrag(){
 const bar=document.getElementById('tb-float');if(!bar)return;let drag=null;
 bar.onpointerdown=e=>{
  if(e.button!==0||e.isPrimary===false||e.target.closest('.timebar-close'))return;
  const box=bar.getBoundingClientRect();tbStopFloatMotion();tbSetPixelPosition(box.left,box.top);
  tbFloatPointerActive=true;
  drag={id:e.pointerId,x:e.clientX,y:e.clientY,dx:e.clientX-box.left,dy:e.clientY-box.top,moved:false};
  bar.setPointerCapture(e.pointerId);e.preventDefault();
 };
 bar.onpointermove=e=>{
  if(drag?.id!==e.pointerId)return;
  if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>6)drag.moved=true;
  if(drag.moved){bar.classList.add('is-dragging');tbSetPixelPosition(e.clientX-drag.dx,e.clientY-drag.dy);e.preventDefault();}
 };
 const finish=e=>{
  if(!drag||e.pointerId!==drag.id)return;
  const tap=e.type==='pointerup'&&!drag.moved;drag=null;tbFloatPointerActive=false;bar.classList.remove('is-dragging');
  if(bar.hasPointerCapture(e.pointerId))bar.releasePointerCapture(e.pointerId);
  if(tap)tbSetCollapsed(!timeBank.collapsed);else{tbSnapToEdge();tbRenderFloat();}
 };
 bar.onpointerup=finish;bar.onpointercancel=finish;bar.onlostpointercapture=finish;
 // Pointer-up handles taps directly: touch browsers can omit click after SVG pointer capture.
 // Keyboard and assistive activation still use click; pointer clicks must not toggle twice.
 bar.onclick=e=>{if(e.target.closest('.timebar-close'))return;e.preventDefault();e.stopPropagation();if(e.detail===0)tbSetCollapsed(!timeBank.collapsed);};
 bar.onkeydown=e=>{if(e.target.closest('.timebar-close')||!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();if(['ArrowLeft','ArrowRight'].includes(e.key)){tbSnapToEdge(e.key==='ArrowLeft'?'left':'right');return;}tbStopFloatMotion();const box=bar.getBoundingClientRect(),d=e.shiftKey?24:8;tbSetPixelPosition(box.left,box.top+(e.key==='ArrowDown'?d:-d));tbSave();};
}
function tbRenderFloat(){let bar=document.getElementById('tb-float');if(bar&&tbFloatPointerActive)return;if(!bar){bar=document.createElement('aside');bar.id='tb-float';document.body.append(bar);}bar.className='timebar'+(timeBank.collapsed?' is-collapsed':'');bar.dataset.dock=timeBank.dock;bar.hidden=!timeBank.visible;document.body.classList.toggle('tb-float-room',timeBank.visible);bar.setAttribute('aria-label',t('Floating timer. Tap to resize; drag and release to dock.','悬浮计时，轻点切换大小，拖动松手自动贴边'));const label=timeBank.collapsed?t('Expand timer; drag to dock','展开计时条；拖动松手贴边'):t('Collapse timer; drag to dock','收起为小方块；拖动松手贴边');bar.innerHTML=`<button class="timebar-handle" id="tb-drag" aria-label="${t('Drag to dock, or move with arrow keys; tap to collapse','拖动松手贴边，或使用方向键移动；轻点收起')}">${icon('grip')}</button><button class="timebar-open" aria-label="${label}" title="${label}" aria-expanded="${!timeBank.collapsed}">${icon('clock')}<span class="timebar-clock" data-tb-today>${tbClock(tbSummary().todayMs)}</span></button><button class="timebar-close" data-action="tb-hide" aria-label="${t('Hide timer; keep counting','隐藏计时条，继续累计')}">${icon('close')}</button>`;tbPosition();tbBindDrag();}
function tbUpdateCounters(){const s=tbSummary();for(const [selector,value] of [['[data-tb-today]',s.todayMs],['[data-tb-total]',s.totalMs]])document.querySelectorAll(selector).forEach(e=>e.textContent=tbClock(value));}
function tbExport(){const s=tbSummary();return {schemaVersion:2,kind:'eastern-wisdom-time-bank',exportedAt:new Date(tbNow()).toISOString(),accountId:timeBank.accountId,zone:timeBank.zone,clockBasis:tbBackend.connected?'server':'device',runs:timeBank.runs,summary:s};}
function tbDownload(){const url=URL.createObjectURL(new Blob([JSON.stringify(tbExport(),null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='计时记录-'+tbDayKey(tbNow())+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function tbChart(s){const keys=Array.from({length:7},(_,i)=>tbTodayKeyOffset(i-6)),max=Math.max(60000,...keys.map(k=>s.days[k]||0));return `<div class="tb-chart">${keys.map(k=>`<div class="tb-chart-day"><span>${tbShort(s.days[k]||0)}</span><div class="tb-chart-track"><i style="height:${Math.max(2,(s.days[k]||0)/max*100)}%"></i></div><small>${k.slice(5)}</small></div>`).join('')}</div>`;}
function tbPage(){const s=tbSummary();return `<section class="page">${head(t('TIME RECORDS','陪伴时长'),t('Time together','陪伴时长'),'','profile')}<article class="tb-hero"><small>${t('TODAY TOGETHER','今日陪伴')}</small><strong data-tb-today>${tbClock(s.todayMs)}</strong><span class="px-status-dot" style="font-size:12px">${t('Counting automatically','自动累计中')}</span></article><div class="px-stat-row"><div><strong data-tb-total style="font-size:17px">${tbClock(s.totalMs)}</strong><small>${t('Total','累计时长')}</small></div><div><strong>${Object.keys(s.days).length}</strong><small>${t('Days','累计天数')}</small></div><div><strong>${timeBank.runs.length}</strong><small>${t('Sessions','使用记录')}</small></div></div><div class="row"><button class="btn secondary" data-action="tb-toggle">${timeBank.visible?t('Hide timer','隐藏计时条'):t('Show timer','显示计时条')}</button><button class="btn secondary" data-action="tb-export">${t('Export','导出记录')}</button></div><details><summary>${t('Past seven days','近七天趋势')}</summary>${tbChart(s)}</details><details><summary>${t('Session details','计时明细')}</summary>${s.sessions.slice().reverse().slice(0,100).map(r=>`<div class="row" style="padding:9px 0;font-size:12px"><span>${esc(new Date(r.start).toLocaleString())}</span><b>${tbShort(r.duration)}</b></div>`).join('')}</details><p class="px-note">${t('Time starts automatically when you open the app. Hiding the widget keeps it running.','打开APP自动累计，隐藏计时条仍继续。')}</p>${go(t('How time is recorded','计时说明'),'timeBankSettings','link')}</section>`;}
function tbSettings(){return `<section class="page">${head(t('TIMER SETTINGS','计时说明'),t('Timer settings','计时说明'),'','timeBank')}<label class="settings-row"><span>${t('Show floating timer','显示浮动计时条')}</span><input type="checkbox" id="tb-visible-setting" ${timeBank.visible?'checked':''}></label><p class="px-note">${t('App sessions accumulate automatically. There is no manual pause. Periodic heartbeats settle closed or disconnected sessions after 45 seconds; multiple tabs do not count twice.','打开APP自动累计，无手动暂停。通过定期心跳识别退出和断线；超过45秒未收到心跳时结束旧会话，多窗口不重复计时。')}</p><p class="px-note">${t('Practice and listening durations are recorded separately.','练习和音乐的实际时长分别记录。')}</p></section>`;}
Object.assign(paths,{grip:'M8 5h1m5 0h1M8 12h1m5 0h1M8 19h1m5 0h1'});
Object.assign(screens,{timeBank:tbPage,timeBankSettings:tbSettings,timeBankSessions:tbPage});
const tbRenderBefore=renderNow;renderNow=function(resetScroll=true){tbRenderBefore(resetScroll);tbRenderFloat();};
document.addEventListener('click',e=>{const el=e.target.closest('[data-action]');if(!el||!el.dataset.action.startsWith('tb-'))return;e.preventDefault();e.stopImmediatePropagation();if(el.dataset.action==='tb-hide')tbSetVisible(false);else if(el.dataset.action==='tb-toggle')tbSetVisible(!timeBank.visible);else if(el.dataset.action==='tb-export')tbDownload();},true);
document.addEventListener('change',e=>{if(e.target.id==='tb-visible-setting')tbSetVisible(e.target.checked);});
function tbResizeFloat(){tbStopFloatMotion();timeBank.position.x=timeBank.dock==='left'?0:1;tbPosition();}
window.addEventListener('resize',tbResizeFloat);
window.visualViewport?.addEventListener('resize',tbResizeFloat);
window.visualViewport?.addEventListener('scroll',tbResizeFloat);
window.addEventListener('storage',e=>{if(personalStorage.scope&&e.key===TB_KEY&&e.newValue){try{const saved=JSON.parse(e.newValue);if(saved.accountId===timeBank.accountId&&saved.lastSeen>timeBank.lastSeen)Object.assign(timeBank,saved);tbRenderFloat();}catch{}}});
document.addEventListener('visibilitychange',()=>{if(!document.hidden){tbLocalHeartbeat();tbSync();tbUpdateCounters();}});
window.addEventListener('pagehide',()=>{timeBank.lastSeen=Date.now();tbSave();});
window.addEventListener('message',e=>{if(e.source===parent&&e.data?.type==='ew-time-bank-request')parent.postMessage({type:'ew-time-bank-snapshot',snapshot:tbExport()},'*');});
setInterval(tbUpdateCounters,1000);setInterval(()=>{if(!tbBackend.connected)tbLocalHeartbeat();tbSync();},10000);
tbSync();render();
