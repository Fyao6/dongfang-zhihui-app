
// Compact community navigation and a vertical video feed.
let cfAbort,cfFrame=0,cfCurrentId='',cfWantsPlay=false,cfMuted=true,cfInFeed=false,cfResizeObserver;
const cfProgress=new Map();
function communityHeader(active='community'){
 return '<nav class="community-tabs" aria-label="'+t('Community','社群')+'">'+[
 ['friends',t('Friends','我的好友')],['communityInbox',t('Messages','我的对话')],['communityTeachers',t('Teachers','老师推荐')],['community',t('For you','推荐视频')]
 ].map(([id,label])=>'<button data-action="go" data-to="'+id+'" aria-current="'+(active===id?'page':'false')+'"><span class="community-tab-label">'+label+'</span></button>').join('')+'</nav>';
}
state.communityTeacherId='';
function ctVerifiedTeachers(){return (px.content.teachers||[]).filter(teacher=>teacher.profileType==='real'&&teacher.verified===true&&(!teacher._status||teacher._status==='published'));}
function ctTeacherName(teacher){return ewI18n.field(teacher,'name',state.lang);}
function ctTeacherPortrait(teacher){return teacher.coverUrl?'<img class="ct-avatar-image" src="'+esc(teacher.coverUrl)+'" alt="" loading="lazy">':icon('user','icon-lg');}
function ctVerifiedBadge(){return '<span class="ct-certified">'+icon('check')+t('Verified','已认证')+'</span>';}
function ctTeacherRequests(teacherId=''){
 const requests=(px.requests||[]).filter(request=>!teacherId||request.teacherId===teacherId);
 return '<section class="ct-requests"><h2>'+t('My requests','我的需求')+'</h2>'+(!px.user?'<p class="ct-muted">'+t('Sign in to view your requests.','登录后查看你的咨询记录。')+'</p>'+go(t('Sign in','登录账号'),'account','secondary full'):requests.length?requests.map(request=>'<article class="ct-request"><div><b>'+esc(request.teacherName)+'</b><span class="ct-request-status">'+esc({pending:t('Pending','待处理'),accepted:t('Accepted','已受理'),closed:t('Closed','已结束'),cancelled:t('Cancelled','已取消')}[request.status]||request.status)+'</span></div><p>'+esc(request.body)+'</p><small>'+esc(request.date)+'</small>'+(request.status==='pending'?'<button data-action="px-cancel-request" data-id="'+esc(request.id)+'">'+t('Cancel','取消')+'</button>':'')+'</article>').join(''):'<p class="ct-muted">'+t('Your teacher requests will appear here.','向老师提交的咨询需求会显示在这里。')+'</p>')+'</section>';
}
function communityTeachersPage(){
 const teachers=ctVerifiedTeachers().filter(teacher=>teacher.recommended===true);
 return '<section class="page community-teachers-page">'+communityHeader('communityTeachers')+'<div class="ct-content"><header class="ct-intro"><span class="ew-page-eyebrow">'+t('Verified teacher support','认证老师支持')+'</span><h1>'+t('Recommended teachers','老师推荐')+'</h1><p>'+t('Meet a verified teacher and request a conversation.','了解认证老师，提出你的交流需求。')+'</p></header>'+(teachers.length?'<div class="ct-teacher-list">'+teachers.map(teacher=>'<button class="ct-teacher-card" data-action="ct-teacher-open" data-id="'+esc(teacher.id)+'"><span class="ct-avatar">'+ctTeacherPortrait(teacher)+'</span><span class="ct-teacher-copy"><span class="ct-name"><b>'+esc(ctTeacherName(teacher))+'</b>'+ctVerifiedBadge()+'</span><span class="ct-specialty">'+esc(ewI18n.field(teacher,'specialty',state.lang))+'</span><span class="ct-bio-preview">'+esc(ewI18n.field(teacher,'bio',state.lang)||teacher.body||'')+'</span><span class="ct-card-action">'+t('View teacher','查看老师')+icon('arrow')+'</span></span></button>').join('')+'</div>':'<div class="ct-empty"><span class="ct-empty-symbol">'+icon('user','icon-lg')+'</span><h2>'+t('Verified teachers are being prepared','认证老师正在准备中')+'</h2><p>'+t('Teacher profiles will appear here after verification and recommendation.','老师通过认证并开放推荐后，资料会显示在这里。')+'</p></div>')+ctTeacherRequests()+'</div></section>';
}
function communityTeacherPage(){
 const teacher=ctVerifiedTeachers().find(item=>item.id===state.communityTeacherId);
 if(!teacher)return '<section class="page community-teachers-page">'+communityHeader('communityTeachers')+'<div class="ct-content">'+pxTop(t('Teacher profile','老师介绍'),'','communityTeachers')+'<div class="ct-empty"><h2>'+t('Teacher support is not available','老师服务暂未开放')+'</h2>'+go(t('View recommended teachers','查看推荐老师'),'communityTeachers','secondary full')+'</div></div></section>';
 return '<section class="page community-teachers-page">'+communityHeader('communityTeachers')+'<div class="ct-content">'+pxTop(t('Teacher profile','老师介绍'),'','communityTeachers')+'<header class="ct-profile"><span class="ct-avatar">'+ctTeacherPortrait(teacher)+'</span><div>'+ctVerifiedBadge()+'<h1>'+esc(ctTeacherName(teacher))+'</h1><p>'+esc(ewI18n.field(teacher,'specialty',state.lang))+'</p></div></header><p class="ct-profile-bio">'+esc(ewI18n.field(teacher,'bio',state.lang)||teacher.body||'')+'</p><button class="btn full ct-consult" data-action="px-service-request" data-id="'+esc(teacher.id)+'">'+icon('chat')+t('Request a consultation','发起咨询')+'</button>'+ctTeacherRequests(teacher.id)+'</div></section>';
}
document.addEventListener('click',event=>{const control=event.target.closest('[data-action="ct-teacher-open"]');if(!control)return;event.preventDefault();event.stopImmediatePropagation();state.communityTeacherId=control.dataset.id;navigate('communityTeacher');},true);
document.addEventListener('error',event=>{if(event.target.matches?.('.ct-avatar-image'))event.target.replaceWith(Object.assign(document.createElement('span'),{className:'ct-avatar-fallback',textContent:'◇'}));},true);
function communityVideoCard(post,preview=false){
 const id=preview?'provided-preview':post.id,title=preview?t('A clip in the community','社群短视频展示'):post.title;
 const author=preview?t('Video preview','视频预览'):post.authorName||'',body=preview?t('Your supplied clip','你提供的短视频'):post.body||'';
 return '<article class="cf-video-card '+(preview?'community-preview-video':'')+'" data-video-id="'+esc(id)+'" data-video-fit="fit" data-video-shape="unknown" aria-label="'+esc(title)+'">'+
 '<video playsinline muted loop preload="metadata"'+(preview?' poster="'+esc(COMMUNITY_PREVIEW_POSTER)+'"':'')+' src="'+esc(preview?COMMUNITY_PREVIEW_VIDEO:post.mediaUrl)+'" aria-label="'+esc(title)+'"></video>'+
 '<button class="cf-stage-toggle" data-cf="toggle" aria-label="'+t('Play','播放')+'"><span class="cf-play-symbol">'+icon('play','icon-lg')+'</span></button>'+
 '<div class="cf-caption"><span class="cf-author">'+(preview?esc(author):'@'+esc(author))+'</span><h2>'+esc(title)+'</h2>'+
 (body?'<details class="cf-description"><summary><span>'+esc(body)+'</span><b>'+t('More','更多')+'</b></summary><p>'+esc(body)+'</p></details>':'')+'</div>'+
 '<div class="cf-actions"><button data-cf="sound" aria-label="'+t('Sound on','打开声音')+'" aria-pressed="false">'+icon('volume')+'<span class="cf-sound-off">×</span></button>'+
 '<button data-cf="previous" aria-label="'+t('Previous video','上一个视频')+'">'+icon('back')+'</button><button data-cf="next" aria-label="'+t('Next video','下一个视频')+'">'+icon('arrow')+'</button></div>'+
 '<div class="cf-playback"><span class="cf-time" aria-hidden="true"><span class="cf-elapsed">0:00</span> / <span class="cf-duration">0:00</span></span><input type="range" min="0" max="1000" value="0" step="1" data-cf-seek aria-label="'+t('Video progress','视频进度')+'"></div>'+
 '<p class="cf-error" role="status" hidden>'+t('Video unavailable. Please retry.','视频暂时无法播放，请重试。')+' <button data-cf="retry">'+t('Retry','重试')+'</button></p></article>';
}
function communityFeedPage(){
 const videos=px.posts.filter(p=>p.mediaUrl);
 return '<section class="community-feed-page" data-video-layout="fit">'+communityHeader()+'<div class="cf-feed" tabindex="0" aria-label="'+t('For you','推荐视频')+'">'+videos.map(p=>communityVideoCard(p)).join('')+communityVideoCard({},true)+'</div></section>';
}
function communityOwnPosts(){
 return '<section class="page community-posts-page">'+pxTop(t('My videos & posts','我的视频与发布'),'','profile')+
 '<button class="btn secondary full" data-action="px-publish">'+icon('video')+t('Post a video','发布视频')+'</button>'+
 '<div class="cf-own-posts">'+(px.mine.length?px.mine.map(p=>pxPostCard(p,true)).join(''):'<div class="empty-state"><p>'+t('Revisit your drafts, submissions and published posts here.','你的草稿、已提交与已发布内容，都可以在这里回看。')+'</p></div>')+'</div></section>';
}
function cfDispose(){
 cancelAnimationFrame(cfFrame);cfAbort?.abort();cfResizeObserver?.disconnect();
 for(const card of document.querySelectorAll('.cf-video-card')){const v=card.querySelector('video');if(Number.isFinite(v.currentTime))cfProgress.set(card.dataset.videoId,v.currentTime);v.pause();}
}
function cfMount(){
 const feed=document.querySelector('.cf-feed');if(!feed){cfWantsPlay=false;cfInFeed=false;return;}
 if(!cfInFeed)cfWantsPlay=true;cfInFeed=true;
 cfAbort=new AbortController();const signal=cfAbort.signal,cards=[...feed.querySelectorAll('.cf-video-card')];
 let current=Math.max(0,cards.findIndex(c=>c.dataset.videoId===cfCurrentId)),restoring=true,playAttempt=0;
 const clock=value=>Number.isFinite(value)?Math.floor(value/60)+':'+String(Math.floor(value%60)).padStart(2,'0'):'0:00';
 function updateGeometry(card){
  const v=card.querySelector('video'),source=v.videoWidth/v.videoHeight,frame=card.clientWidth/card.clientHeight;
  if(!Number.isFinite(source)||!Number.isFinite(frame)||source<=0||frame<=0)return;
  const portrait=source<.82,crop=1-Math.min(source/frame,frame/source),fit=portrait&&crop<=.18?'fill':'fit';
  card.dataset.videoFit=fit;card.dataset.videoShape=portrait?'portrait':source>1.15?'landscape':'square';card.dataset.videoRatio=source.toFixed(4);
  if(cards[current]===card)feed.parentElement.dataset.videoLayout=fit;
 }
 function paint(card){
  const v=card.querySelector('video'),playing=!v.paused&&!v.ended;
  card.classList.toggle('is-playing',playing);
  card.querySelector('.cf-elapsed').textContent=clock(v.currentTime);card.querySelector('.cf-duration').textContent=clock(v.duration);
  const range=card.querySelector('[data-cf-seek]');range.disabled=!Number.isFinite(v.duration)||v.duration<=0;range.value=range.disabled?0:Math.round(v.currentTime/v.duration*1000);
  range.parentElement.style.setProperty('--cf-progress',Number(range.value)/10+'%');range.setAttribute('aria-valuetext',clock(v.currentTime)+' / '+clock(v.duration));
  card.querySelectorAll('[data-cf=toggle]').forEach(b=>{b.setAttribute('aria-label',playing?t('Pause','暂停'):t('Play','播放'));if(b.closest('.cf-playback'))b.innerHTML=icon(playing?'pause':'play');});
  const sound=card.querySelector('[data-cf=sound]');sound.setAttribute('aria-label',v.muted?t('Sound on','打开声音'):t('Mute','关闭声音'));sound.setAttribute('aria-pressed',String(!v.muted));card.classList.toggle('is-muted',v.muted);
  card.querySelector('[data-cf=previous]').disabled=current===0;card.querySelector('[data-cf=next]').disabled=current===cards.length-1;
  if(cards[current]===card)feed.parentElement.dataset.videoLayout=card.dataset.videoFit||'fit';
 }
 function pauseOthers(index){cards.forEach((c,i)=>{if(i!==index)c.querySelector('video').pause();});}
 async function playCurrent(){
  if(document.hidden||!cfWantsPlay)return;pauseOthers(current);
  const card=cards[current],v=card?.querySelector('video'),attempt=++playAttempt;if(!v)return;
  const active=()=>!signal.aborted&&feed.isConnected&&cards[current]===card&&attempt===playAttempt;
  card.classList.add('is-starting');
  try{await v.play();}
  catch(error){
   if(!active()||!cfWantsPlay||document.hidden)return;
   // Browsers can reject sound after a reload; retry the current video muted.
   if(error.name==='NotAllowedError'&&!v.muted){
    cfMuted=true;cards.forEach(c=>{c.querySelector('video').muted=true;});
    try{await v.play();}catch{if(active()&&!document.hidden)cfWantsPlay=false;}
   }else if(error.name!=='AbortError')cfWantsPlay=false;
  }finally{if(active()){card.classList.remove('is-starting');if(!cfWantsPlay||document.hidden)v.pause();paint(card);}}
 }
 function activate(index,play=true){current=Math.max(0,Math.min(index,cards.length-1));cfCurrentId=cards[current].dataset.videoId;cfWantsPlay=play;pauseOthers(current);cards.forEach(paint);if(play)playCurrent();}
 function move(delta){const index=Math.max(0,Math.min(current+delta,cards.length-1));pauseOthers(index);feed.scrollTo({top:index*feed.clientHeight,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});activate(index);}
 for(const [index,card] of cards.entries()){
  const v=card.querySelector('video');v.muted=cfMuted;
  v.addEventListener('loadedmetadata',()=>{const saved=cfProgress.get(card.dataset.videoId);if(saved&&saved<v.duration)v.currentTime=saved;updateGeometry(card);paint(card);},{signal});
  v.addEventListener('resize',()=>updateGeometry(card),{signal});
  ['timeupdate','pause','volumechange','durationchange'].forEach(event=>v.addEventListener(event,()=>paint(card),{signal}));
  v.addEventListener('play',()=>{if(index!==current||document.hidden||!cfWantsPlay){v.pause();return;}pauseOthers(index);musicStop();pxNativeStop();paint(card);},{signal});
  v.addEventListener('error',()=>{card.querySelector('.cf-error').hidden=false;if(index===current)cfWantsPlay=false;paint(card);},{signal});
  card.addEventListener('click',e=>{const control=e.target.closest('[data-cf]');if(!control)return;const action=control.dataset.cf;
   if(action==='toggle'){if(index!==current)activate(index,false);if(v.paused){cfWantsPlay=true;playCurrent();}else{cfWantsPlay=false;v.pause();}}
   if(action==='sound'){cfMuted=!v.muted;cards.forEach(c=>{c.querySelector('video').muted=cfMuted;});}
   if(action==='previous')move(-1);if(action==='next')move(1);
   if(action==='retry'){card.querySelector('.cf-error').hidden=true;v.load();cfWantsPlay=true;playCurrent();}
  },{signal});
  const seek=card.querySelector('[data-cf-seek]'),playback=seek.parentElement;
  seek.addEventListener('pointerdown',()=>playback.classList.add('is-seeking'),{signal});
  const endSeek=()=>playback.classList.remove('is-seeking');
  window.addEventListener('pointerup',endSeek,{signal});window.addEventListener('pointercancel',endSeek,{signal});seek.addEventListener('blur',endSeek,{signal});
  seek.addEventListener('input',e=>{if(Number.isFinite(v.duration)&&v.duration>0){v.currentTime=Number(e.target.value)*v.duration/1000;paint(card);}},{signal});
  paint(card);
  updateGeometry(card);
 }
 feed.addEventListener('scroll',()=>{if(restoring)return;cancelAnimationFrame(cfFrame);cfFrame=requestAnimationFrame(()=>{const index=Math.max(0,Math.min(Math.round(feed.scrollTop/feed.clientHeight),cards.length-1));if(index!==current)activate(index);});},{signal,passive:true});
 feed.addEventListener('keydown',e=>{if(e.target.closest('button,input,summary'))return;if(['ArrowDown','PageDown','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();move(['ArrowDown','PageDown'].includes(e.key)?1:-1);}},{signal});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)cards.forEach(c=>c.querySelector('video').pause());else if(cfWantsPlay)playCurrent();},{signal});
 window.addEventListener('pagehide',()=>{cards.forEach(c=>c.querySelector('video').pause());},{signal});
 window.addEventListener('pageshow',()=>{if(cfWantsPlay)playCurrent();},{signal});
 const resize=()=>cards.forEach(updateGeometry);window.addEventListener('resize',resize,{signal});
 if(typeof ResizeObserver!=='undefined'){cfResizeObserver=new ResizeObserver(resize);cfResizeObserver.observe(feed);}
 feed.scrollTop=current*feed.clientHeight;activate(current,cfWantsPlay);requestAnimationFrame(()=>{restoring=false;});
}
screens.community=communityFeedPage;screens.communityPosts=communityOwnPosts;screens.communityTeachers=communityTeachersPage;screens.communityTeacher=communityTeacherPage;screens.teachers=communityTeachersPage;screens.consult=communityTeachersPage;
const cfRenderBefore=renderNow;
renderNow=function(reset=true){cfDispose();cfRenderBefore(reset);cfMount();};
render(false);

