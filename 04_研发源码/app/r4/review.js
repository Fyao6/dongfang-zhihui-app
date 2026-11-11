const preview=document.getElementById('experience-frame');
const requestedMemberPage=new URLSearchParams(location.search).get('page');
const requestedLanguage=new URLSearchParams(location.search).get('lang');
let savedReviewLanguage='zh';try{savedReviewLanguage=JSON.parse(localStorage.getItem('eastern-wisdom-r4')||'{}').lang||'zh';}catch{} 
let previewState={lang:({'zh-Hans':'zh','zh-CN':'zh','zh-TW':'zh-Hant'}[requestedLanguage]||(['zh','zh-Hant','en','bo'].includes(requestedLanguage)?requestedLanguage:savedReviewLanguage)),mode:'night'},previewPage=['membership','memberCenter','profile'].includes(requestedMemberPage)?requestedMemberPage:'home';
preview.srcdoc=APP.replace('__INITIAL__',JSON.stringify({...previewState,page:previewPage,persist:true,backend:location.protocol==='http:'&&['127.0.0.1','localhost'].includes(location.hostname)}));
const previewPages=[['home','首页'],['gate','三大地图'],['lifeResult','认识自己'],['body','修复自己'],['mind','提升自己'],['academy','智慧馆'],['service','AI服务'],['serviceReports','基础报告解析'],['community','社群'],['teachers','老师一对一'],['friends','好友与交流'],['communityInbox','我的对话'],['dailyCard','每日抽卡'],['checkin','每日签到'],['music','冥想音乐'],['favorites','我的收藏'],['growth','成长记录'],['timeline','每日时间轴'],['profile','我的']];
const pageLinks=document.getElementById('review-links');
previewPages.push(['timeBank','计时记录'],['membership','会员服务'],['memberCenter','会员中心']);
previewPages.forEach(([id,name])=>{const b=document.createElement('button');b.textContent=name;b.dataset.page=id;b.classList.toggle('active',id===previewPage);pageLinks.append(b);});
function previewSend(){preview.contentWindow?.postMessage({type:'ew-settings',...previewState,page:previewPage},'*');}
pageLinks.addEventListener('click',e=>{const b=e.target.closest('[data-page]');if(b){previewPage=b.dataset.page;previewSend();}});
document.getElementById('review-language').addEventListener('change',e=>{previewState.lang=e.target.value;previewSend();});
document.getElementById('review-mode').addEventListener('change',e=>{previewState.mode=e.target.value;previewSend();});
window.addEventListener('message',e=>{if(e.source!==preview.contentWindow||e.data?.type!=='ew-state')return;previewPage=e.data.page;previewState.lang=e.data.lang;previewState.mode=e.data.mode;document.getElementById('review-language').value=previewState.lang;document.getElementById('review-mode').value=previewState.mode;pageLinks.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.page===previewPage));});
new ResizeObserver(entries=>{for(const {target} of entries)target.style.setProperty('--zoom',target.clientWidth/393);}).observe(document.getElementById('phone'));

