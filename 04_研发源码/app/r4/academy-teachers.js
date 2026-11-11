
const academyTeacherSeed = [
 {id:'demo-qinghe',name:'清和',nameEn:'Qinghe',nameBo:'ཆིང་ཧོ།',specialty:'认识自己',bio:'从东方文化出发，慢慢认识自己。',bioEn:'Explore yourself through Eastern culture, at your own pace.',bioBo:'ཤར་ཕྱོགས་རིག་གནས་བརྒྱུད་ནས་རང་ཉིད་རིམ་བཞིན་ངོ་ཤེས་པར་བྱེད།',profileType:'demo'},
 {id:'demo-anran',name:'安然',nameEn:'Anran',nameBo:'ཨན་རན།',specialty:'修复自己',bio:'从呼吸与身体觉察开始，照顾日常身心。',bioEn:'Care for body and mind through breathing and everyday awareness.',bioBo:'དབུགས་གཏོང་ལེན་དང་ལུས་ཀྱི་ཚོར་བར་དོ་སྣང་བྱས་ནས་ཉིན་རེའི་ལུས་སེམས་གསོ་སྐྱོང་བྱེད།',profileType:'demo'},
 {id:'demo-zhiwei',name:'知微',nameEn:'Zhiwei',nameBo:'ཀྲི་ཝེ།',specialty:'提升自己',bio:'为情绪留一点空间，把练习带进生活。',bioEn:'Make room for feelings and bring practice into everyday life.',bioBo:'སེམས་ཚོར་ལ་གོ་ས་ཞིག་བཞག་ནས་སྦྱོང་བརྡར་ཉིན་རེའི་འཚོ་བར་འཇུག་པར་བྱེད།',profileType:'demo'}
];
const academyDemoTeacherForTheme={ziwei:'demo-qinghe',tcm:'demo-anran',healing:'demo-zhiwei'};
state.academyView='courses'; state.academyTeacherId=''; state.academyBack='academy'; state.academyCategoryId='all';
function academyOfflineContent(){return typeof ACADEMY_CONTENT_SEED==='undefined'?{}:ACADEMY_CONTENT_SEED;}
function academyPlatformContent(){try{return px.loaded?px.content:null;}catch{return null;}}
function academyCategories(){
 const content=academyPlatformContent(),source=content?(content.courseCategories||[]):(academyOfflineContent().courseCategories||[]);
 const seen=new Set();return source.map((item,index)=>({item,index})).filter(({item})=>{
  if(!item||typeof item.id!=='string'||seen.has(item.id)||item.enabled!==true||(item._status&&item._status!=='published'))return false;
  seen.add(item.id);return true;
 }).sort((a,b)=>(Number.isFinite(a.item._position)?a.item._position:a.index)-(Number.isFinite(b.item._position)?b.item._position:b.index)||a.index-b.index).map(({item})=>item);
}
function academySelectedCategory(){
 if(state.academyCategoryId!=='all'&&!academyCategories().some(item=>item.id===state.academyCategoryId))state.academyCategoryId='all';
 return state.academyCategoryId;
}
function academyCourseCategoryIds(course){
 const offline=!academyPlatformContent(),seed=offline?(academyOfflineContent().courses||[]).find(item=>item.id===course.id):null;
 const ids=course.categoryIds??seed?.categoryIds;return Array.isArray(ids)?ids.filter(id=>typeof id==='string'):[];
}
function academyCategoryStrip(count){
 const selected=academySelectedCategory(),options=[{id:'all',name:t('All courses','全部课程')},...academyCategories()];
 return '<div class="academy-category-strip" role="group" aria-label="'+t('Course categories','课程分类')+'"><div class="academy-category-options">'+options.map(item=>'<button type="button" data-action="academy-category" data-id="'+esc(item.id)+'" aria-pressed="'+(selected===item.id)+'">'+esc(item.id==='all'?item.name:ewI18n.field(item,'name',state.lang))+'</button>').join('')+'</div><span class="academy-category-count" role="status" aria-live="polite">'+count+' '+t('courses','门课程')+'</span></div>';
}
function academyTeachers(){const content=academyPlatformContent();return content?(content.teachers||[]):academyTeacherSeed;}
function academyPublishedCourses(){const content=academyPlatformContent();if(!content)return academyCatalog;const order=new Map((content.courses||[]).map((c,i)=>[c.id,i]));return academyCatalog.filter(c=>order.has(c.id)).sort((a,b)=>order.get(a.id)-order.get(b.id));}
function academyTeacherName(teacher){return teacher?ewI18n.field(teacher,'name',state.lang):t('Platform courses','平台课程');}
function academyTeacherGroup(course){return academyTeachers().some(x=>x.id===course.teacherId)?course.teacherId:'unassigned';}
function academyTeacherBadge(teacher){return teacher?.profileType==='demo'?'<span class="at-demo">'+t('Sample teacher','示例老师')+'</span>':'';}
function academyTeacherPortrait(teacher){return teacher?.coverUrl?'<img src="'+esc(teacher.coverUrl)+'" alt="" loading="lazy" class="at-avatar-image">':icon('user','icon-lg');}
function academyTeacherCard(teacher,items){
 const name=academyTeacherName(teacher),id=teacher?.id||'unassigned';
 return '<button class="at-teacher-card" data-action="at-open" data-id="'+esc(id)+'"><span class="at-portrait">'+academyTeacherPortrait(teacher)+'</span><span class="at-copy"><span class="at-name"><b>'+esc(name)+'</b>'+academyTeacherBadge(teacher)+'</span><span class="at-specialty">'+esc(teacher?ewI18n.field(teacher,'specialty',state.lang):t('Selected introductions and practices','精选导读与练习'))+'</span><span class="at-preview">'+items.slice(0,2).map(c=>esc(ewI18n.content(c,'',state.lang))).join(' · ')+'</span><span class="at-foot"><span>'+items.length+' '+t('courses','门课程')+'</span><span>'+t('View courses','查看课程')+icon('arrow')+'</span></span></span></button>';
}
function academyResultCards(){
 const items=academyResults();
 return academyCategoryStrip(items.length)+academyCourseList(items,true);
}
function academyTeacherPage(){
 const teacher=academyTeachers().find(x=>x.id===state.academyTeacherId),id=teacher?.id||'unassigned';
 const items=academyPublishedCourses().filter(c=>academyTeacherGroup(c)===id);
 return '<section class="page academy-page at-teacher-page">'+pxTop(t('Teacher courses','老师课程'),'','academy')+'<header class="at-profile"><span class="at-portrait">'+academyTeacherPortrait(teacher)+'</span><div>'+academyTeacherBadge(teacher)+'<h2>'+esc(academyTeacherName(teacher))+'</h2><p>'+esc(teacher?ewI18n.field(teacher,'specialty',state.lang):t('Selected introductions and practices','精选导读与练习'))+'</p></div></header>'+(teacher?.bio?'<p class="at-bio">'+esc(ewI18n.field(teacher,'bio',state.lang))+'</p>':'')+'<div class="academy-results-heading"><h2>'+t('All courses','全部课程')+'</h2><span>'+items.length+' '+t('courses','门课程')+'</span></div>'+academyCourseList(items)+'</section>';
}
function academyCourseTeacher(course){
 const teacher=academyTeachers().find(x=>x.id===course.teacherId);if(!teacher)return '';
 return '<div class="at-course-author"><span class="at-author-symbol">'+icon('user')+'</span><span><b>'+esc(academyTeacherName(teacher))+'</b></span>'+academyTeacherBadge(teacher)+'</div>';
}
screens.academyTeacher=academyTeacherPage;
document.addEventListener('click',e=>{
 const el=e.target.closest('[data-action]');if(!el?.dataset.action.startsWith('at-'))return;e.preventDefault();e.stopImmediatePropagation();
 if(el.dataset.action==='at-open'){state.academyTeacherId=el.dataset.id;navigate('academyTeacher');}
},true);
document.addEventListener('error',e=>{if(e.target.matches?.('.at-avatar-image'))e.target.replaceWith(Object.assign(document.createElement('span'),{className:'at-avatar-fallback',textContent:'◇'}));},true);

