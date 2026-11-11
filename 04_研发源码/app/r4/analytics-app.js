// Aggregate APP feature usage only. Personal records and page contents never leave here.
const ewAnalyticsTelemetry={pending:false,lastKey:'',lastAt:0,scheduled:false};
function ewAnalyticsFeature(page=state.page){
 if(['home','gate','quote'].includes(page))return 'home';
 if(['lifeResult','lifeReview','lifeJournal','lifeThemes','ziweiChart','ziweiCulture','classicsWisdom','westernAstrology','traits'].includes(page))return 'life';
 if(['body','bodyAssessment','bodyCulture','bodyRecovery','bodyHistory','teaLife','chineseCare','tibetanCare'].includes(page))return 'body';
 if(['mind','mindHistory','zenPractice','emotionAwareness','healingSpace','meditationStudy'].includes(page))return 'mind';
 if(['player','sessionDone','advanced','advancedPlan'].includes(page))return 'practice';
 if(['academy','academyTeacher','academyDetail','academyGuide','lesson','course','buddhistCourses','dharmaLesson','profileCourses'].includes(page))return 'academy';
 if(['community','communityPosts','communityTeachers','communityTeacher','communityProfile','communityInbox','friends','friendSearch','friendDetail','conversation','teachers','teacherDetail','teacherRequest','consult','creatorProfile','creatorWork','publish','shareCompose'].includes(page))return 'community';
 if(page.startsWith('service'))return 'ai';
 if(page==='checkin')return 'checkin';
 if(page==='dailyCard')return 'cards';
 if(['music','musicPlayer','externalMusic'].includes(page))return 'music';
 if(page==='devices')return 'device';
 if(page.startsWith('profile')||page.startsWith('timeBank')||['account','favorites','growth','timeline','portrait'].includes(page))return 'profile';
 return 'other';
}
function ewAnalyticsKey(){
 if(!pxOnline||!px.loaded||!px.user||!['user','teacher'].includes(px.user.role)||document.hidden||navigator.onLine===false)return '';
 const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 return px.user.id+'|'+state.page+'|'+day;
}
async function ewAnalyticsReport(kind='visit'){
 const key=ewAnalyticsKey();if(!key){ewAnalyticsTelemetry.lastKey='';return;}
 if(ewAnalyticsTelemetry.pending||kind==='visit'&&key===ewAnalyticsTelemetry.lastKey)return;
 ewAnalyticsTelemetry.pending=true;
 try{
  const response=await fetch('/api/analytics/activity',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({feature:ewAnalyticsFeature(),kind}),keepalive:true});
  if(response.ok){ewAnalyticsTelemetry.lastKey=key;ewAnalyticsTelemetry.lastAt=Date.now();}
 }catch{/* Collection failure must never interrupt an APP action or fabricate a backlog. */}
 finally{ewAnalyticsTelemetry.pending=false;const current=ewAnalyticsKey();if(current&&current!==key)ewAnalyticsSchedule();}
}
function ewAnalyticsSchedule(){if(ewAnalyticsTelemetry.scheduled)return;ewAnalyticsTelemetry.scheduled=true;queueMicrotask(()=>{ewAnalyticsTelemetry.scheduled=false;ewAnalyticsReport('visit');});}
const ewAnalyticsRenderPrevious=renderNow;
renderNow=function(resetScroll=true){const result=ewAnalyticsRenderPrevious(resetScroll);ewAnalyticsSchedule();return result;};
document.addEventListener('visibilitychange',()=>{if(!document.hidden){ewAnalyticsTelemetry.lastKey='';ewAnalyticsSchedule();}});
window.addEventListener('online',()=>{ewAnalyticsTelemetry.lastKey='';ewAnalyticsSchedule();});
setInterval(()=>{if(!document.hidden&&Date.now()-ewAnalyticsTelemetry.lastAt>=60000)ewAnalyticsReport(ewAnalyticsTelemetry.lastKey===ewAnalyticsKey()?'heartbeat':'visit');},15000);
ewAnalyticsSchedule();
