// Loaded after all screen overrides.
function ewChangeLanguage(value){
 state.lang=ewI18n.normalize(value);closeSheet();
 const url=new URL(location.href);url.searchParams.set('lang',ewI18n.locales[state.lang].tag);
 try{history.replaceState(null,'',url);}catch{}
 psSavePreferences();render(false);
}
function ewLanguageSheet(){
 sheet(t('Language','语言'),'<div class="ew-language-options">'+Object.entries(ewI18n.locales).map(([key,info])=>'<button data-action="ew-language" data-language="'+key+'" lang="'+info.tag+'" aria-pressed="'+(state.lang===key)+'"><span>'+info.name+'</span>'+(state.lang===key?icon('check'):icon('arrow'))+'</button>').join('')+'</div>','');
}
const ewLocaleRenderBefore=renderNow;
renderNow=function(reset=true){
 ewLocaleRenderBefore(reset);document.documentElement.lang=ewI18n.locales[state.lang].tag;document.documentElement.dir='ltr';
 document.title=t('Eastern Wisdom · Daily companion','东方智慧 · 日常陪伴');
 document.getElementById('nav').setAttribute('aria-label',t('Main navigation','主导航'));
 const header=document.querySelector('.home-header-actions');
 if(header&&!header.querySelector('[data-action="ew-language-open"]')){
  const b=document.createElement('button');b.className='icon-btn flat ew-language-button';b.dataset.action='ew-language-open';
  b.textContent=state.lang==='bo'?'བོད':state.lang==='en'?'EN':state.lang==='zh-Hant'?'繁/A':'简/A';
  b.setAttribute('aria-label',t('Language','语言'));header.prepend(b);
 }
};
document.addEventListener('click',event=>{
 const b=event.target.closest('[data-action="ew-language-open"],[data-action="ew-language"]');if(!b)return;
 event.preventDefault();if(b.dataset.action==='ew-language-open')ewLanguageSheet();else ewChangeLanguage(b.dataset.language);
});
// Resolve deep links after every screen module has registered. Early module renders
// can otherwise replace a new destination with home before its screen exists.
const ewInitialDestination=initial.page||q.get('page');
if(ewInitialDestination&&typeof screens[ewInitialDestination]==='function'&&state.page!==ewInitialDestination){
 if(typeof ewNavigation!=='undefined'){ewNavigation.current=ewInitialDestination;ewNavigation.trail=[];ewNavigation.returning=false;}
 navigate(ewInitialDestination);
}else render(false);

