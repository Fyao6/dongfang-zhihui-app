// In-app parent navigation. No browser-history mutation and no practice or timer records are created.
const ewNavigationRoots=new Set(['home','academy','service','community','profile']);
const ewNavigationDefaults={
 gate:'home',lifeResult:'home',body:'home',mind:'home',
 ziweiChart:'lifeResult',ziweiCulture:'ziweiChart',traits:'lifeResult',lifeThemes:'lifeResult',lifeReview:'lifeResult',lifeJournal:'lifeReview',classicsWisdom:'lifeResult',westernAstrology:'lifeResult',
 teaLife:'body',chineseCare:'body',tibetanCare:'body',bodyHistory:'body',bodyAssessment:'chineseCare',bodyCulture:'chineseCare',bodyRecovery:'healingSpace',
 healingSpace:'mind',meditationStudy:'mind',mindHistory:'mind',emotionAwareness:'healingSpace',zenPractice:'meditationStudy',buddhistCourses:'meditationStudy',dharmaLesson:'buddhistCourses',timeline:'meditationStudy',
 academyDetail:'academy',academyTeacher:'academy',academyRead:'academyDetail',academyGuide:'academyDetail',course:'academy',lesson:'buddhistCourses',wisdom:'academy',
 profileRecords:'profile',profileServices:'profile',profileCourses:'profile',profileSettings:'profile',profileData:'profile',profileEdit:'profile',favorites:'profile',growth:'profile',account:'profile',devices:'profile',
 timeBank:'profile',timeBankSettings:'timeBank',timeBankSessions:'timeBank',communityPosts:'profile',publish:'communityPosts',
 memberCenter:'profile',membership:'memberCenter',memberBenefits:'memberCenter',memberBenefit:'memberBenefits',memberContent:'memberCenter',memberCheckout:'membership',memberResult:'membership',memberEvents:'memberBenefits',memberGifts:'memberBenefits',
 communityTeachers:'community',communityTeacher:'communityTeachers',teachers:'communityTeachers',friends:'community',communityInbox:'community',creatorProfile:'communityTeachers',
 serviceChat:'service',consult:'service',portrait:'service',advanced:'service',advancedPlan:'advanced',
 dailyCard:'home',checkin:'home',music:'home',externalMusic:'music'
};
const ewNavigation={current:state.page,trail:[],returning:false,headerParents:Object.create(null)};
function ewValidParent(value){return typeof value==='string'&&value!==state.page&&typeof screens[value]==='function';}
function ewPageBackTarget(){
 if(['player','sessionDone'].includes(state.page))return ewValidParent(state.audioReturn)?state.audioReturn:'meditationStudy';
 while(ewNavigation.trail.length&&(!ewValidParent(ewNavigation.trail[ewNavigation.trail.length-1])||ewNavigation.trail[ewNavigation.trail.length-1]==='player'))ewNavigation.trail.pop();
 return ewNavigation.trail[ewNavigation.trail.length-1]||ewNavigationDefaults[state.page]||ewNavigation.headerParents[state.page]||'home';
}
function ewObservePage(next){
 const previous=ewNavigation.current;if(previous===next)return;
 if(!ewNavigation.returning){
  if(ewNavigationRoots.has(next))ewNavigation.trail=[];
  else if(next==='player'||(previous==='player'&&[state.audioReturn,'sessionDone'].includes(next))||(previous==='sessionDone'&&next===state.audioReturn)){}
  else if(ewNavigation.trail.includes(next))ewNavigation.trail=ewNavigation.trail.slice(0,ewNavigation.trail.lastIndexOf(next));
  else if(typeof screens[previous]==='function'&&ewNavigation.trail[ewNavigation.trail.length-1]!==previous){ewNavigation.trail.push(previous);ewNavigation.trail=ewNavigation.trail.slice(-40);}
 }
 ewNavigation.current=next;ewNavigation.returning=false;
}
function ewDecorateBack(button,player=false){
 if(!button)return;
 const original=button.dataset.to;if(original&&ewValidParent(original)&&!ewNavigation.headerParents[state.page])ewNavigation.headerParents[state.page]=original;
 button.classList.add('ew-page-back');button.type='button';
 button.dataset.action=player?'close-player':'ew-page-back';button.dataset.to=ewPageBackTarget();
 button.setAttribute('aria-label',t('Back','返回'));
 // Replace only the button's contents; the map scene remains connected in its header.
 button.innerHTML=icon('back')+'<span>'+t('Back','返回')+'</span>';
}
function ewInstallPageBack(){
 if(ewNavigationRoots.has(state.page))return;
 const page=document.querySelector('#app>.page,#app>.player,#app>section');if(!page)return;
 if(state.page==='player'){
  const close=page.querySelector('[data-action="close-player"]');if(close)ewDecorateBack(close,true);return;
 }
 const mapHeader=page.querySelector('.fl-map-heading');
 if(mapHeader){
  const title=mapHeader.querySelector('h1');if(!title)return;
  let row=mapHeader.querySelector('.ew-map-title-row');
  if(!row){row=document.createElement('div');row.className='ew-map-title-row';mapHeader.insertBefore(row,title);row.append(title);}
  let button=row.querySelector('.ew-page-back');if(!button){button=document.createElement('button');row.prepend(button);}ewDecorateBack(button);return;
 }
 let back=page.querySelector('.px-top>button[data-action="go"],.page-head .row>button[data-action="go"],header .ew-page-back');
 if(!back){
  back=Array.from(page.querySelectorAll('header button[data-action="go"]')).find(button=>button.getAttribute('aria-label')===t('Back','返回'));
 }
 if(!back){
  const row=document.createElement('div');row.className='ew-page-back-row';back=document.createElement('button');row.append(back);page.prepend(row);
 }
 ewDecorateBack(back);
}
function ewGoBack(){
 if(ewNavigation.returning)return;
 const target=ewPageBackTarget();
 if(ewNavigation.trail[ewNavigation.trail.length-1]===target)ewNavigation.trail.pop();
 ewNavigation.returning=true;navigate(target);
}
const ewBackRenderBefore=renderNow;
renderNow=function(resetScroll=true){ewObservePage(state.page);const result=ewBackRenderBefore(resetScroll);ewInstallPageBack();return result;};
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-action="ew-page-back"]');if(!button)return;
 event.preventDefault();event.stopImmediatePropagation();ewGoBack();
},true);
