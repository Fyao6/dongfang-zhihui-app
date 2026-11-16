// Homepage media starts only after an explicit play action. No placeholder clip is supplied.
const hvText=(en,zh,hant,bo)=>flText(en,zh,hant,bo);
let homeVideoSession=null,homeVideoSequence=0;
const hvLanguages={'zh':'简体中文','zh-Hant':'繁體中文',en:'English',bo:'བོད་ཡིག'};
function homeVideoURL(value,uploaded=true){try{if(typeof value!=='string')return '';if(uploaded&&/^\/api\/media\/[a-f0-9-]{36}$/.test(value))return value;const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?value:'';}catch{return '';}}
function homeVideoCurrent(){const quote=dailyQuote(shiftedDate(state.quoteOffset||0));return homeBannerItems().find(item=>item.id===quote.id);}
const homeVideoItemsBefore=homeBannerItems;
homeBannerItems=function(){const rows=homeVideoItemsBefore();return (Array.isArray(rows)?rows:[]).filter(item=>item.mediaType!=='video'||item.enabled!==false);};
const homeVideoQuoteBefore=dailyQuote;
dailyQuote=function(date=today()){
 const rows=homeBannerItems();if(!rows.length)return px.loaded?{id:'cms_no_quote',zh:'每日一句准备中',en:'Daily thoughts are being prepared'}:homeVideoQuoteBefore(date);
 const day=Math.floor(Date.parse(date+'T12:00:00Z')/86400000),item=rows[((day%rows.length)+rows.length)%rows.length];return {...item,zh:item.zh||item.title||'',en:item.en||item.zh||item.title||''};
};
const homeVideoBannerBefore=dailyBanner;
dailyBanner=function(){
 const count=homeBannerCount();if(Math.abs(state.quoteOffset||0)>=count)state.quoteOffset=0;const item=homeVideoCurrent();if(item?.mediaType!=='video')return homeVideoBannerBefore();
 const title=ewI18n.content(item,'',state.lang),cover=homeVideoURL(item.coverUrl),description=ewI18n.field(item,'description',state.lang);
 return `<div class="quote-banner-wrap hv-banner-wrap" role="region" aria-roledescription="${hvText('carousel','轮播','輪播','རེས་འཁོར།')}" aria-label="${hvText('Featured content','首页精选轮播','首頁精選輪播','མདུན་ངོས་ཀྱི་ནང་དོན།')}"><article class="hv-banner quote-banner" data-home-video="${esc(item.id)}">${cover?`<img class="hv-banner-cover" src="${esc(cover)}" alt="">`:''}<div class="hv-banner-copy"><span class="quote-overline">${esc(ewI18n.field(item,'bannerLabel',state.lang)||hvText('ABOUT THE APP','认识东方智慧','認識東方智慧','ཤར་ཕྱོགས་ཤེས་རབ་ངོ་སྤྲོད།'))}</span><h2>${esc(title)}</h2>${description?`<p>${esc(description)}</p>`:''}<button class="hv-play-entry" data-action="home-video-open" data-id="${esc(item.id)}">${icon('play')}<span>${hvText('Play introduction','播放介绍片','播放介紹片','ངོ་སྤྲོད་བརྙན་གཏོང་།')}</span></button></div></article><div class="quote-pagination"><div class="home-banner-dots">${Array.from({length:count},(_,index)=>`<button data-action="quote-slide" data-offset="${-index}" aria-label="${hvText('Slide ','第','第','ཤོག་ངོས། ')}${index+1}" aria-pressed="${state.quoteOffset===-index}"><span></span></button>`).join('')}</div><button class="home-banner-pause" data-action="home-banner-pause">${state.bannerPaused?hvText('Play','播放轮播','播放輪播','རེས་འཁོར་གཏོང་།'):hvText('Pause','暂停轮播','暫停輪播','རེས་འཁོར་འཇོག་པ།')}</button></div></div>`;
};
function homeVideoSetStatus(session,message,error=false){
 if(homeVideoSession!==session)return;const host=document.getElementById('home-video-player');if(!host)return;
 const status=host.querySelector('[data-hv-status]'),retry=host.querySelector('[data-action="home-video-retry"]'),fallback=host.querySelector('.hv-player-fallback');
 status.textContent=message;status.hidden=!message;retry.hidden=!error;host.dataset.mediaError=error?'true':'false';if(fallback)fallback.hidden=!error;
}
function homeVideoPaint(session){
 if(homeVideoSession!==session)return;const host=document.getElementById('home-video-player');if(!host)return;const v=session.video;
 const play=host.querySelector('[data-action="home-video-play"]'),sound=host.querySelector('[data-action="home-video-sound"]');
 if(play)play.textContent=v.paused?hvText('Play','播放','播放','གཏོང་།'):hvText('Pause','暂停','暫停','མཚམས་འཇོག');
 if(sound){sound.textContent=v.muted?hvText('Turn sound on','开启声音','開啟聲音','སྒྲ་ཕྱེ།'):hvText('Mute','静音','靜音','སྒྲ་སྒོ་རྒྱག');sound.setAttribute('aria-pressed',String(!v.muted));}
}
function homeVideoCaptions(session,lang){
 if(homeVideoSession!==session)return;session.caption=lang;
 for(let i=0;i<session.video.textTracks.length;i++)session.video.textTracks[i].mode=session.tracks[i]?.lang===lang?'showing':'disabled';
}
async function homeVideoPlay(session){
 if(homeVideoSession!==session)return;const revision=++session.playRevision;session.wantsPlay=true;homeVideoSetStatus(session,hvText('Loading video…','正在加载视频…','正在載入影片…','བརྙན་ལེན་བཞིན་པ།'));
 try{await session.video.play();if(homeVideoSession!==session||revision!==session.playRevision||!session.wantsPlay){if(homeVideoSession!==session||!session.wantsPlay)session.video.pause();return;}homeVideoSetStatus(session,'');homeVideoPaint(session);}
 catch{if(homeVideoSession===session&&revision===session.playRevision&&session.wantsPlay){session.video.pause();homeVideoPaint(session);homeVideoSetStatus(session,hvText('Playback could not start. Use Play or retry; the app remains available.','暂时未能开始播放，可重试或使用播放器；首页其他功能仍可使用。','暫時未能開始播放，可重試或使用播放器；首頁其他功能仍可使用。','བརྙན་གཏོང་མ་ཐུབ། ཡང་བསྐྱར་ཚོད་ལྟ་བྱོས། གཞན་གྱི་བྱེད་ལས་སྤྱོད་ཆོག'),true);}}
}
function homeVideoPause(session){session.wantsPlay=false;session.playRevision++;session.video.pause();homeVideoPaint(session);}
function homeVideoCleanup(){
 const session=homeVideoSession;if(!session)return;homeVideoSession=null;session.wantsPlay=false;session.playRevision++;session.abort.abort();clearTimeout(session.timeout);session.video.pause();session.video.removeAttribute('src');session.video.load();for(const url of session.blobs)URL.revokeObjectURL(url);
 state.bannerPaused=session.previousPaused;if(state.page==='home'&&typeof homeBannerMount==='function')homeBannerMount();
}
const homeVideoSheetBefore=sheet;
sheet=function(title,body,footer){if(homeVideoSession)homeVideoCleanup();return homeVideoSheetBefore(title,body,footer);};
function homeVideoOpen(id){
 const item=homeBannerItems().find(row=>row.id===id&&row.mediaType==='video'&&row.enabled!==false);if(!item)return;const source=homeVideoURL(item.mediaUrl);if(!source){toast(hvText('The video is not configured yet.','视频资料尚未配置。','影片資料尚未設定。','བརྙན་ད་དུང་མ་བསྒྲིགས།'));return;}
 homeVideoCleanup();const previousPaused=state.bannerPaused;state.bannerPaused=true;if(typeof homeBannerMount==='function')homeBannerMount();
 const title=ewI18n.content(item,'',state.lang),poster=homeVideoURL(item.coverUrl),tracks=(Array.isArray(item.subtitleTracks)?item.subtitleTracks:[]).filter(track=>hvLanguages[track.lang]&&(track.text||homeVideoURL(track.url,false)));
 const caption=tracks.some(track=>track.lang===state.lang)?state.lang:tracks.some(track=>track.lang==='en')?'en':tracks[0]?.lang||'',blobs=[];
 const trackMarkup=tracks.map(track=>{const url=track.text?URL.createObjectURL(new Blob([track.text],{type:'text/vtt;charset=utf-8'})):homeVideoURL(track.url,false);if(track.text)blobs.push(url);return `<track kind="subtitles" srclang="${track.lang==='zh'?'zh-Hans':track.lang}" label="${esc(track.label||hvLanguages[track.lang])}" src="${esc(url)}" ${track.lang===caption?'default':''}>`;}).join('');
 sheet(title,`<section id="home-video-player" class="hv-player" data-media-error="false"><div class="hv-player-stage"><video controls playsinline preload="none" ${poster?`poster="${esc(poster)}"`:''} aria-label="${esc(title)}">${trackMarkup}</video>${poster?`<img class="hv-player-fallback" src="${esc(poster)}" alt="${esc(title)}" hidden>`:`<div class="hv-player-fallback" hidden>${esc(title)}</div>`}</div><div class="hv-controls"><button type="button" data-action="home-video-play">${hvText('Play','播放','播放','གཏོང་།')}</button><button type="button" data-action="home-video-sound" aria-pressed="false">${hvText('Turn sound on','开启声音','開啟聲音','སྒྲ་ཕྱེ།')}</button><button type="button" data-action="home-video-fullscreen">${hvText('Full screen','全屏','全螢幕','བརྙན་ཡོལ་ཆ་ཚང་།')}</button></div>${tracks.length?`<label class="hv-caption-label">${hvText('Subtitles','字幕','字幕','ཡིག་བརྙན།')}<select data-hv-captions><option value="">${hvText('Off','关闭','關閉','སྒོ་རྒྱག')}</option>${tracks.map(track=>`<option value="${track.lang}" ${caption===track.lang?'selected':''}>${esc(track.label||hvLanguages[track.lang])}</option>`).join('')}</select></label>`:''}<p data-hv-status role="status"></p><button class="btn secondary full" data-action="home-video-retry" hidden>${hvText('Retry video','重新加载视频','重新載入影片','བརྙན་སླར་ལེན།')}</button>${item.target?`<button class="btn secondary full" data-action="home-video-target" data-id="${esc(item.id)}">${esc(ewI18n.field(item,'buttonLabel',state.lang)||hvText('Explore the app','开始体验','開始體驗','ཉམས་ལེན་འགོ་འཛུགས།'))}</button>`:''}</section>`,button(hvText('Close video','关闭视频','關閉影片','བརྙན་སྒོ་རྒྱག'),'home-video-close','','secondary full'));
 const host=document.getElementById('home-video-player'),video=host.querySelector('video'),abort=new AbortController(),session={id:++homeVideoSequence,item,video,abort,blobs,previousPaused,tracks,caption,timeout:0,playRevision:0,wantsPlay:false};homeVideoSession=session;video.muted=true;
 // Cross-origin text tracks require the media server to provide CORS headers too.
 if(tracks.some(track=>track.url&&new URL(track.url).origin!==location.origin))video.crossOrigin='anonymous';video.src=source;
 const signal=abort.signal;video.addEventListener('play',()=>{if(!video.paused)session.wantsPlay=true;homeVideoPaint(session);},{signal});video.addEventListener('pause',()=>{if(video.paused){session.wantsPlay=false;session.playRevision++;}homeVideoPaint(session);},{signal});video.addEventListener('volumechange',()=>homeVideoPaint(session),{signal});
 video.addEventListener('playing',()=>{clearTimeout(session.timeout);homeVideoSetStatus(session,'');},{signal});
 video.addEventListener('waiting',()=>homeVideoSetStatus(session,hvText('Buffering…','正在缓冲…','正在緩衝…','སྒུག་བཞིན་པ།')),{signal});
 video.addEventListener('loadedmetadata',()=>homeVideoCaptions(session,session.caption),{signal});
 video.addEventListener('error',()=>{video.pause();homeVideoSetStatus(session,hvText('The video is unavailable. The cover is kept; retry or close to continue.','视频暂不可用，已保留封面；可重试或关闭后继续使用。','影片暫不可用，已保留封面；可重試或關閉後繼續使用。','བརྙན་གཏོང་མི་ཐུབ། ཕྱི་ཤོག་ཉར་ཡོད། ཡང་བསྐྱར་བྱོས་ཡང་ན་སྒོ་རྒྱག'),true);},{signal});
 for(const track of host.querySelectorAll('track'))track.addEventListener('error',()=>{homeVideoSetStatus(session,hvText('A subtitle track could not load. Retry or choose another subtitle.','部分字幕未能加载，可重试或选择其他字幕。','部分字幕未能載入，可重試或選擇其他字幕。','ཡིག་བརྙན་ལེན་མ་ཐུབ། གཞན་ཞིག་འདེམས་རོགས།'));if(homeVideoSession===session)host.querySelector('[data-action="home-video-retry"]').hidden=false;},{signal});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)homeVideoPause(session);},{signal});window.addEventListener('pagehide',()=>homeVideoCleanup(),{signal});
 const dialog=document.getElementById('sheet');dialog.addEventListener('close',()=>homeVideoCleanup(),{signal});dialog.addEventListener('cancel',()=>homeVideoCleanup(),{signal});
 session.timeout=setTimeout(()=>{if(homeVideoSession===session&&video.readyState<2)homeVideoSetStatus(session,hvText('Loading is taking longer. Retry or close; other app features remain usable.','加载较慢，可重试或关闭；APP其他功能仍可使用。','載入較慢，可重試或關閉；APP其他功能仍可使用。','ལེན་པ་འགོར་བཞིན་པས་ཡང་བསྐྱར་བྱོས།'),true);},15000);
 homeVideoCaptions(session,caption);homeVideoPlay(session); // The initiating user click is the only startup trigger.
}
const homeVideoRenderBefore=renderNow;
renderNow=function(reset=true){
 const active=homeVideoSession,current=state.page==='home'?homeVideoCurrent():null;if(active&&(state.page!=='home'||current?.id!==active.item.id||current?.mediaUrl!==active.item.mediaUrl||!document.getElementById('sheet')?.open)){homeVideoCleanup();if(document.getElementById('home-video-player'))closeSheet();}
 return homeVideoRenderBefore(reset);
};
document.addEventListener('click',event=>{
 const control=event.target.closest('[data-action^="home-video-"]');if(!control)return;event.preventDefault();event.stopImmediatePropagation();const action=control.dataset.action;
 if(action==='home-video-open')return homeVideoOpen(control.dataset.id);
 if(action==='home-video-close'){homeVideoCleanup();closeSheet();if(state.page==='home')render(false);return;}
 if(action==='home-video-target'){const item=homeBannerItems().find(row=>row.id===control.dataset.id);homeVideoCleanup();closeSheet();if(item?.target?.startsWith('https://'))window.open(item.target,'_blank','noopener,noreferrer');else if(item&&['academy','dailyCard','music','body','mind','lifeResult','service','membership'].includes(item.target))navigate(item.target);return;}
 const session=homeVideoSession;if(!session)return;const video=session.video;
 if(action==='home-video-play'){if(video.paused)homeVideoPlay(session);else homeVideoPause(session);}
 if(action==='home-video-sound'){video.muted=!video.muted;homeVideoPaint(session);}
 if(action==='home-video-retry'){video.load();homeVideoPlay(session);}
 if(action==='home-video-fullscreen'){const fallback=()=>toast(hvText('Use the player’s full-screen control on this device.','请使用此设备播放器的全屏按钮。','請使用此裝置播放器的全螢幕按鈕。','བརྙན་གཏོང་ཆས་ཀྱི་ཡོལ་ཆ་ཚང་མཐེབ་གནོན།'));try{if(!video.requestFullscreen&&!video.webkitEnterFullscreen){fallback();return;}const result=video.requestFullscreen?video.requestFullscreen():video.webkitEnterFullscreen();result?.catch?.(fallback);}catch{fallback();}}
},true);
document.addEventListener('change',event=>{if(event.target.matches('[data-hv-captions]')&&homeVideoSession)homeVideoCaptions(homeVideoSession,event.target.value);},true);
