/* Growth statistics, following the user's 2026-11-18 visual reference.
 * The existing module name is retained for build compatibility.
 * Read-only projection: no migration, synthetic history or timer writes.
 */
(function (global) {
  'use strict';
  let runtime = null, installed = false;
  const original = {};
  const isObject = value => value !== null && typeof value === 'object';
  const own = (value, key) => isObject(value) && Object.prototype.hasOwnProperty.call(value, key);
  const entries = value => isObject(value) ? Object.entries(value) : [];
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const definitions = {
    life: ['Life reflections','生活觉察','生活覺察','མི་ཚེའི་བསམ་གཞིགས།'],
    body: ['Body check-ins','身体感受','身體感受','ལུས་ཀྱི་ཚོར་བ།'],
    mind: ['Mood and reflections','情绪与觉察','情緒與覺察','སེམས་ཁམས་དང་བསམ་གཞིགས།'],
    session: ['Actual practices','实际练习','實際練習','དངོས་ཀྱི་ཉམས་ལེན།'],
    music: ['Actual listening','实际聆听','實際聆聽','དངོས་ཀྱི་ཉན་པ།'],
    checkin: ['Check-ins','每日签到','每日簽到','ཉིན་རེའི་འབྱོར་ཐོ།'],
    card: ['Saved daily cards','原有每日卡片','原有每日卡片','ཉིན་རེའི་བྱང་བུ།'],
    traits: ['My observations','特质观察','特質觀察','ངའི་ལྟ་ཞིབ།'],
    action: ['Actions I chose','自主小行动','自主小行動','རང་གིས་བདམས་པའི་བྱ་སྤྱོད།'],
    legacy: ['Earlier notes','原有笔记','原有筆記','སྔར་གྱི་ཟིན་ཐོ།'],
    plan: ['My current daily plan','当前每日安排','目前每日安排','ད་ལྟའི་ཉིན་རེའི་འཆར་གཞི།'],
    checkpoint: ['Unfinished practice','尚未结束的练习','尚未結束的練習','མཇུག་མ་སྒྲིལ་བའི་ཉམས་ལེན།'],
    learning: ['Last opened learning','上次查看的学习内容','上次查看的學習內容','ཐེངས་སྔོན་བལྟས་པའི་སློབ་ཚན།'],
    other: ['Other existing fields','其他原有字段','其他原有欄位','སྔར་ཡོད་ཀྱི་གནས་ཚུལ་གཞན།']
  };
  const labels = {
    intention:['Intention','意向','意向','བསམ་འདུན།'], strength:['Strength','优势','優勢','ནུས་པ།'],
    relation:['Connection','关系观察','關係觀察','འབྲེལ་བ།'], direction:['Direction','方向','方向','ཕྱོགས།'],
    theme:['Theme','课题','課題','བརྗོད་གཞི།'], sleep:['Sleep','睡眠','睡眠','གཉིད།'],
    energy:['Energy','精力','精力','སྟོབས་ཤུགས།'], stress:['Stress','压力','壓力','སེམས་གནོན།'],
    comfort:['Comfort','舒适度','舒適度','བདེ་ཚོར།'], mood:['Feeling','心情','心情','སེམས་ཚོར།'],
    note:['My words','原有文字','原有文字','རང་གི་ཡི་གེ།'], next:['Next step','下一步','下一步','གོམ་པ་རྗེས་མ།'],
    id:['Record ID','记录编号','記錄編號','ཟིན་ཐོའི་ཨང་།'], date:['Original date','原记录日期','原記錄日期','སྔར་གྱི་ཚེས་གྲངས།'],
    practice:['Practice','练习','練習','ཉམས་ལེན།'], seconds:['Seconds actually recorded','实际记录秒数','實際記錄秒數','དངོས་བཀོད་སྐར་ཆ།'],
    complete:['Completed','是否完成','是否完成','མཇུག་སྒྲིལ་མིན།'], feeling:['My feedback','练习后感受','練習後感受','ཉམས་ལེན་རྗེས་ཀྱི་ཚོར་བ།'],
    endedAt:['Ended at','结束时间','結束時間','མཇུག་སྒྲིལ་དུས།'], createdAt:['Created at','创建时间','建立時間','བཟོས་པའི་དུས།'],
    updatedAt:['Updated at','更新时间','更新時間','གསར་བསྒྱུར་དུས།'], at:['Original time','原有时间','原有時間','སྔར་གྱི་དུས།'],
    plannedTime:['Planned time','原定时间','原定時間','འཆར་གཞིའི་དུས།'], slot:['Plan slot','安排时段','安排時段','འཆར་གཞིའི་དུས་མཚམས།'],
    cardId:['Card ID','卡片编号','卡片編號','བྱང་བུའི་ཨང་།'], trackId:['Track ID','音轨编号','音軌編號','སྒྲའི་ཨང་།'],
    track:['Original track','原有音轨','原有音軌','སྔར་གྱི་སྒྲ།'], snapshot:['Original saved content','原有内容快照','原有內容快照','སྔར་ཉར་བའི་ནང་དོན།'],
    selection:['Selection method','选择方式','選擇方式','འདེམས་སྟངས།'], drawnAt:['Selected at','抽取时间','抽取時間','འདེམས་པའི་དུས།'],
    answers:['Original answers','原有回答','原有回答','སྔར་གྱི་ལན།'], title:['Original title','原有标题','原有標題','སྔར་གྱི་ཁ་བྱང་།'],
    action:['Chosen action','所选行动','所選行動','བདམས་པའི་བྱ་སྤྱོད།'], actionEn:['Original English action','原有英文行动','原有英文行動','སྔར་གྱི་དབྱིན་ཡིག་བྱ་སྤྱོད།'],
    doneAt:['Self-reported completion time','本人标记完成时间','本人標記完成時間','རང་གིས་མཇུག་སྒྲིལ་བཀོད་པའི་དུས།'],
    sourceDrawDate:['Original card date','来源卡片日期','來源卡片日期','བྱང་བུའི་ཚེས་གྲངས།'], time:['Time','时间','時間','དུས།']
  };
  function text(en, zh, hant, bo) {
    const lang = typeof state === 'object' ? state.lang : 'zh';
    const normalized = typeof ewI18n === 'object' ? ewI18n.normalize(lang) : lang;
    if (normalized === 'bo' && bo) return bo;
    if (normalized === 'zh-Hant' && hant) return hant;
    return typeof ewI18n === 'object' ? ewI18n.text(en, zh, normalized) : normalized === 'en' ? en : zh;
  }
  const title = kind => text(...definitions[kind]);
  function token() {return typeof psToken === 'function' ? psToken() : {scope:null,epoch:-1};}
  function same(t) {const current=token(); return t.scope !== null && current.scope===t.scope && current.epoch===t.epoch;}
  function date(value) {
    if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return null;
    const parsed=new Date(value+'T12:00:00Z');
    return Number.isFinite(parsed.getTime())&&parsed.toISOString().slice(0,10)===value?value:null;
  }
  const numberLabel = n => typeof ewIntlLocale === 'function' ? new Intl.NumberFormat(ewIntlLocale()).format(n) : String(n);

  function project(personal) {
    const root={key:'root',kind:'root',children:[],level:1,label:text('My growth','我的成长','我的成長','ངའི་འཚར་ལོངས།')};
    const categories=new Map(), dayGroups=new Map(), index=new Map([['root',root]]);
    function add(kind,key,value,day,source) {
      let category=categories.get(kind);
      if(!category){category={key:'kind:'+kind,kind:'category',recordKind:kind,label:title(kind),children:[],parent:root,level:2};categories.set(kind,category);root.children.push(category);index.set(category.key,category);}
      const dated=date(day), groupKey=category.key+':date:'+(dated||'undated');let group=dayGroups.get(groupKey);
      if(!group){group={key:groupKey,kind:'date',label:dated||text('No original date','原资料无日期','原資料無日期','སྔར་གྱི་ཚེས་གྲངས་མེད།'),day:dated,children:[],parent:category,level:3};dayGroups.set(groupKey,group);category.children.push(group);index.set(group.key,group);}
      const leaf={key:'record:'+key,kind:'record',recordKind:kind,day:dated,source,originalKey:key,value,parent:group,children:[],level:4,
        label:title(kind)+' · '+numberLabel(group.children.length+1)};
      group.children.push(leaf);index.set(leaf.key,leaf);
    }
    const w=isObject(personal.wellness)?personal.wellness:{},daily=isObject(personal.daily)?personal.daily:{},continuity=isObject(w.continuity)?w.continuity:{};
    for(const [kind,property] of [['life','intentions'],['body','body'],['mind','mind']]) {
      if(!own(w,property))continue;
      if(isObject(w[property]))for(const [day,value] of entries(w[property]))add(kind,'wellness.'+property+'.'+day,value,day,{container:'wellness.'+property,entry:day});
      else if(w[property]!==null&&w[property]!==undefined)add(kind,'wellness.'+property,w[property],null,{container:'wellness',entry:property});
    }
    function collection(kind,container,path) {
      if(container===null||container===undefined)return;
      if(isObject(container))for(const [key,value] of entries(container))add(kind,path+'.'+key,value,isObject(value)?value.date:null,{container:path,entry:key});
      else add(kind,path,container,null,{container:path,entry:null});
    }
    collection('session',w.sessions,'wellness.sessions');
    collection('music',daily.musicSessions,'daily.musicSessions');
    for(const [kind,property] of [['checkin','checkins'],['card','draws']]) {
      if(isObject(daily[property]))for(const [day,value] of entries(daily[property]))add(kind,'daily.'+property+'.'+day,value,day,{container:'daily.'+property,entry:day});
      else if(own(daily,property)&&daily[property]!==null)add(kind,'daily.'+property,daily[property],null,{container:'daily',entry:property});
    }
    if(own(daily,'traits')&&daily.traits!==null)add('traits','daily.traits',daily.traits,isObject(daily.traits)?daily.traits.date:null,{container:'daily',entry:'traits'});
    collection('action',continuity.cardActions,'wellness.continuity.cardActions');
    if(own(personal,'lifeNotes')&&personal.lifeNotes!==null)add('legacy','lifeNotes',personal.lifeNotes,null,{container:'personal',entry:'lifeNotes'});
    if(own(personal,'journal')&&personal.journal!==''&&personal.journal!==null)add('legacy','journal',personal.journal,null,{container:'personal',entry:'journal'});
    collection('plan',w.plan,'wellness.plan');
    for(const kind of ['checkpoint','learning'])if(own(continuity,kind)&&continuity[kind]!==null)add(kind,'wellness.continuity.'+kind,continuity[kind],isObject(continuity[kind])?continuity[kind].date:null,{container:'wellness.continuity',entry:kind});
    for(const [key,value] of entries(w))if(!['intentions','body','mind','sessions','plan','continuity'].includes(key))add('other','wellness.'+key,value,null,{container:'wellness',entry:key});
    for(const [key,value] of entries(continuity))if(!['cardActions','checkpoint','learning'].includes(key))add('other','wellness.continuity.'+key,value,null,{container:'wellness.continuity',entry:key});
    if(own(w,'continuity')&&w.continuity!==null&&!isObject(w.continuity))add('other','wellness.continuity',w.continuity,null,{container:'wellness',entry:'continuity'});
    // Favorites remain an independent feature. Unrecognized daily fields are
    // still readable here instead of being silently discarded by a projection.
    for(const [key,value] of entries(daily))if(!['checkins','draws','musicSessions','traits','favorites','arrivalSeen'].includes(key))add('other','daily.'+key,value,null,{container:'daily',entry:key});
    for(const category of root.children)category.children.sort((a,b)=>a.day&&b.day?b.day.localeCompare(a.day):a.day?-1:b.day?1:0);
    function total(node){node.count=node.kind==='record'?1:node.children.reduce((n,child)=>n+total(child),0);return node.count;}
    total(root);return {root,index};
  }

  function todayKey() { return typeof localDate==='function'?localDate():new Date().toLocaleDateString('en-CA'); }
  function ensure() {
    const actor=token();
    if(!runtime||runtime.actor.scope!==actor.scope||runtime.actor.epoch!==actor.epoch){
      runtime?.abort?.abort();
      runtime={actor,range:'all',anchor:todayKey(),metric:'duration',filter:'all',limit:50,selection:null,selected:null};
    }
    return runtime;
  }
  function valid(r) {return runtime===r&&same(r.actor)&&r.root?.isConnected&&r.root===document.querySelector('[data-gtc-root]')&&r.page===(typeof state==='object'?state.page:null);}
  function shift(day,days) {const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);}
  function monthEnd(day) {const d=new Date(day.slice(0,7)+'-01T12:00:00Z');d.setUTCMonth(d.getUTCMonth()+1);d.setUTCDate(0);return d.toISOString().slice(0,10);}
  function period(range,anchor,today,records=[]) {
    anchor=date(anchor)||today;
    if(range==='week') {const d=new Date(anchor+'T12:00:00Z'),from=shift(anchor,-((d.getUTCDay()+6)%7));return {from,to:shift(from,6)};}
    if(range==='month')return {from:anchor.slice(0,7)+'-01',to:monthEnd(anchor)};
    if(range==='year')return {from:anchor.slice(0,4)+'-01-01',to:anchor.slice(0,4)+'-12-31'};
    const days=statisticalRecords(records).records.filter(n=>n.day&&n.day<=today).map(n=>n.day).sort();
    return {from:days[0]||today,to:today};
  }
  const activityKinds=new Set(['life','body','mind','session','music','checkin','card','traits']);
  function activity(n) {return activityKinds.has(n.recordKind);}
  function sameRawValue(a,b,seen=new Map()) {
    if(Object.is(a,b))return true;
    if(!isObject(a)||!isObject(b)||Array.isArray(a)!==Array.isArray(b)||Array.isArray(a)&&a.length!==b.length)return false;
    let matches=seen.get(a);if(matches?.has(b))return true;
    if(!matches){matches=new Set();seen.set(a,matches);}matches.add(b);
    const keys=Object.keys(a),other=Object.keys(b);
    return keys.length===other.length&&keys.every(key=>own(b,key)&&sameRawValue(a[key],b[key],seen));
  }
  function statisticalRecords(records) {
    const candidates=records.filter(activity),groups=new Map(),groupFor=new Map();
    for(const node of candidates){
      // Only native session/listening IDs identify events; other original id
      // fields can refer to content or metadata and must not merge days.
      if(!['session','music'].includes(node.recordKind))continue;
      const id=isObject(node.value)?node.value.id:null;
      if(!(typeof id==='string'&&id.trim()!==''||typeof id==='number'&&Number.isFinite(id)))continue;
      let byId=groups.get(node.recordKind);if(!byId){byId=new Map();groups.set(node.recordKind,byId);}
      const identity=typeof id+':'+String(id);let group=byId.get(identity);
      if(!group){group=[];byId.set(identity,group);}group.push(node);groupFor.set(node,group);
    }
    const accepted=new Set();let duplicateRecords=0,conflictRecords=0;
    for(const byId of groups.values())for(const group of byId.values()){
      if(group.every(node=>sameRawValue(group[0].value,node.value))){accepted.add(group[0]);duplicateRecords+=group.length-1;}
      else conflictRecords+=group.length;
    }
    return {records:candidates.filter(node=>!groupFor.has(node)||accepted.has(node)),duplicateRecords,conflictRecords};
  }
  function measured(n) {
    if(!['session','music'].includes(n.recordKind)||!isObject(n.value))return null;
    const value=n.value.seconds;
    return typeof value==='number'&&Number.isSafeInteger(value)&&value>=0?value:null;
  }
  const maxSafeSeconds=BigInt(Number.MAX_SAFE_INTEGER);
  function exactSeconds(value) {
    if(typeof value==='bigint')return value>=0n?value:0n;
    if(typeof value==='number'&&Number.isSafeInteger(value)&&value>=0)return BigInt(value);
    if(typeof value==='string'&&/^\d+$/.test(value))return BigInt(value);
    return 0n;
  }
  function publicSeconds(value) {return value<=maxSafeSeconds?Number(value):value.toString();}
  function durationParts(value) {const n=exactSeconds(value);return {h:n/3600n,m:n/60n%60n,s:n%60n};}
  function qualityNotice(records) {
    const quality=statisticalRecords(records),missing=quality.records.filter(n=>['session','music'].includes(n.recordKind)&&measured(n)===null).length;
    if(!quality.duplicateRecords&&!quality.conflictRecords&&!missing)return '';
    const duplicate=numberLabel(quality.duplicateRecords),conflict=numberLabel(quality.conflictRecords),unknown=numberLabel(missing);
    return text(`Identical duplicate records counted once: ${duplicate}. Records with conflicting IDs excluded from statistics: ${conflict}. Records without valid duration: ${unknown}; they add no duration or practice/listening count. All original information remains in History.`,
      `相同重复资料已合并统计 ${duplicate} 条；编号内容冲突、未纳统计 ${conflict} 条；未记录有效时长 ${unknown} 条，不计时长或练习／聆听次数。全部原资料均保留在履历中。`,
      `相同重複資料已合併統計 ${duplicate} 條；編號內容衝突、未納統計 ${conflict} 條；未記錄有效時長 ${unknown} 條，不計時長或練習／聆聽次數。全部原資料均保留在履歷中。`,
      `ཟློས་པ་གཅིག་ཏུ་བརྩིས། ${duplicate} ཨང་གཅིག་ནང་དོན་མི་མཐུན་པ་མ་བསྡོམས། ${conflict} དུས་ཡུན་མེད་པ་དུས་ཡུན་དང་ཉམས་ལེན་གྲངས་སུ་མ་བརྩིས། ${unknown} སྔར་གྱི་གནས་ཚུལ་ཚང་མ་ཟིན་ཐོར་ཉར།`);
  }
  function statistics(records,from,to,today=todayKey()) {
    const real=statisticalRecords(records).records.filter(n=>n.day&&n.day>=from&&n.day<=to&&n.day<=today);
    const practices=real.filter(n=>n.recordKind==='session'&&measured(n)!==null),listens=real.filter(n=>n.recordKind==='music'&&measured(n)!==null);
    const practiceSeconds=practices.reduce((sum,n)=>sum+BigInt(measured(n)),0n),listeningSeconds=listens.reduce((sum,n)=>sum+BigInt(measured(n)),0n);
    return {seconds:publicSeconds(practiceSeconds+listeningSeconds),practiceSeconds:publicSeconds(practiceSeconds),listeningSeconds:publicSeconds(listeningSeconds),records:real.length,practices:practices.length,listens:listens.length,
      days:new Set(real.map(n=>n.day)).size,reflections:real.filter(n=>['life','body','mind'].includes(n.recordKind)).length};
  }
  function buckets(range,bounds,records,today=todayKey()) {
    const result=[];
    if(range==='week'||range==='month') {for(let d=bounds.from;d<=bounds.to;d=shift(d,1))result.push({from:d,to:d,label:range==='week'?d.slice(5):String(Number(d.slice(8)))});}
    else if(range==='year')for(let m=1;m<=12;m++){const from=bounds.from.slice(0,4)+'-'+String(m).padStart(2,'0')+'-01';result.push({from,to:monthEnd(from),label:String(m)});}
    else {
      const actual=[...new Set(statisticalRecords(records).records.filter(n=>n.day&&n.day<=today).map(n=>n.day.slice(0,4)))].sort();
      const first=Number(actual[0]||today.slice(0,4)),last=Number(today.slice(0,4));
      const years=last-first<=30?Array.from({length:last-first+1},(_,i)=>String(first+i).padStart(4,'0')):actual;
      for(const year of years)result.push({from:year+'-01-01',to:year+'-12-31',label:year});
    }
    return result.map(b=>({...b,...statistics(records,b.from,b.to,today)}));
  }
  function duration(seconds) {
    if(seconds===null)return text('Duration not recorded','未记录时长','未記錄時長','དུས་ཡུན་བཀོད་མེད།');
    const {h,m,s}=durationParts(seconds);
    return text(`${numberLabel(h)}h ${numberLabel(m)}m ${numberLabel(s)}s`,`${numberLabel(h)}小时${numberLabel(m)}分${numberLabel(s)}秒`,`${numberLabel(h)}小時${numberLabel(m)}分${numberLabel(s)}秒`,`${numberLabel(h)} ཆུ་ཚོད། ${numberLabel(m)} སྐར་མ། ${numberLabel(s)} སྐར་ཆ།`);
  }
  function button(label,attrs='',cls='') {return '<button type="button" class="'+cls+'" '+attrs+'>'+escape(label)+'</button>';}
  function screen() {
    ensure();const name=text('Growth records','成长记录','成長記錄','འཚར་ལོངས་ཟིན་ཐོ།');
    const header=typeof pxTop==='function'?pxTop(name,'','profile'):'<header><h1>'+escape(name)+'</h1></header>';
    return '<section class="page gs-page" data-gtc-root data-growth-view="statistics">'+header+
      '<div class="gs-tabs" role="tablist" aria-label="'+escape(text('Time range','时间范围','時間範圍','དུས་ཀྱི་ཁྱབ་ཁོངས།'))+'">'+
      [['week',text('Week','周','週','བདུན་ཕྲག')],['month',text('Month','月','月','ཟླ།')],['year',text('Year','年','年','ལོ།')],['all',text('Total','总','總','བསྡོམས།')],['history',text('History','履历','履歷','ཟིན་ཐོ།')]].map(([id,label])=>button(label,'role="tab" data-gs-tab="'+id+'" id="gs-tab-'+id+'" aria-controls="gs-panel"')).join('')+'</div>'+
      '<div id="gs-panel" role="tabpanel" data-gs-panel></div><section class="gtc-detail" data-gtc-detail hidden></section></section>';
  }
  function recordList(r,records,heading) {
    const sorted=records.slice().sort((a,b)=>(b.day||'').localeCompare(a.day||'')||a.key.localeCompare(b.key));
    let html='<section class="gs-record-section"><div class="gs-section-heading"><h2>'+escape(heading)+'</h2><span>'+escape(numberLabel(sorted.length))+'</span></div><div class="gs-records" data-gs-records>';
    for(const node of sorted.slice(0,r.limit))html+=button('', 'data-gs-record="'+escape(node.key)+'"','gs-record').replace('></button>','><span><b>'+escape(title(node.recordKind))+'</b><small>'+escape(node.day||text('Original date unavailable','原资料无日期','原資料無日期','སྔར་གྱི་ཚེས་གྲངས་མེད།'))+'</small></span><span>'+escape(['session','music'].includes(node.recordKind)?duration(measured(node)):'')+' <span aria-hidden="true">›</span></span></button>');
    html+='</div>';
    if(!sorted.length)html+='<p class="gs-empty">'+escape(text('No saved records in this period.','这段时间还没有保存的记录。','這段時間還沒有儲存的記錄。','དུས་འདིར་ཉར་བའི་ཟིན་ཐོ་མེད།'))+'</p>';
    if(sorted.length>r.limit)html+=button(text('Show more records','继续查看记录','繼續查看記錄','ཟིན་ཐོ་མུ་མཐུད་ལྟ།'),'data-gs="more"','gs-more');
    return html+'</section>';
  }
  function chart(r,series) {
    const durationMetric=r.metric==='duration',values=series.map(b=>durationMetric?b.seconds:b.records),precise=values.map(exactSeconds),max=precise.reduce((best,n)=>n>best?n:best,0n);
    const step=durationMetric?(max>3600n?3600n:max>600n?600n:60n):3n,rounded=(max+step-1n)/step*step,axisMax=rounded>step?rounded:step;
    const axis=n=>{if(!durationMetric)return numberLabel(n);const unit=axisMax>=3600n?3600n:60n,tenths=(n*10n+unit/2n)/unit;return numberLabel(tenths/10n)+(tenths%10n?'.'+numberLabel(tenths%10n):'')+(unit===3600n?text('h','小时','小時','ཆུ་ཚོད།'):text('m','分','分','སྐར་མ།'));};
    let html='<section class="gs-chart-card"><div class="gs-section-heading"><h2>'+escape(text('A rhythm of your own','日常的节奏','日常的節奏','ཉིན་རེའི་འགྲོས།'))+'</h2><span aria-hidden="true">▥</span></div><div class="gs-metrics" role="group" aria-label="'+escape(text('Chart metric','图表指标','圖表指標','རིས་ཀྱི་ཚད།'))+'">'+button(text('Duration','时长','時長','དུས་ཡུན།'),'data-gs-metric="duration" aria-pressed="'+durationMetric+'"')+button(text('Records','记录','記錄','ཟིན་ཐོ།'),'data-gs-metric="records" aria-pressed="'+!durationMetric+'"')+'</div>';
    if(durationMetric)html+='<div class="gs-chart-legend"><span><i aria-hidden="true"></i>'+escape(text('Practice','练习','練習','ཉམས་ལེན།'))+'</span><span><i class="gs-listen-key" aria-hidden="true"></i>'+escape(text('Listening','聆听','聆聽','ཉན་པ།'))+'</span></div>';
    html+='<div class="gs-plot"><div class="gs-chart-scroll" tabindex="0" aria-label="'+escape(text('Time chart. Scroll horizontally for more dates.','时间分布图，可横向滑动查看更多日期。','時間分布圖，可橫向滑動查看更多日期。','དུས་ཀྱི་རིས། གཡས་གཡོན་སྤོ་ནས་ལྟ་ཆོག'))+'"><div class="gs-chart-grid" style="--gs-columns:'+series.length+';min-width:'+Math.max(210,series.length*36)+'px">';
    series.forEach((b,i)=>{
      const value=values[i],selected=r.selection?.from===b.from&&r.selection?.to===b.to,total=exactSeconds(b.seconds);
      const listeningShare=total>0n?Number(exactSeconds(b.listeningSeconds))/Number(total)*100:0;
      const layers=durationMetric?'<span class="gs-listening-segment" style="height:'+listeningShare+'%"></span><span class="gs-practice-segment" style="height:'+(100-listeningShare)+'%"></span>':'';
      const caption=b.from+' — '+b.to+' · '+(durationMetric?duration(value)+' · '+text('Practice ','练习 ','練習 ','ཉམས་ལེན། ')+duration(b.practiceSeconds)+' · '+text('Listening ','聆听 ','聆聽 ','ཉན་པ། ')+duration(b.listeningSeconds):numberLabel(value)+' '+text('records','条记录','條記錄','ཟིན་ཐོ།'));
      html+='<button type="button" class="gs-bar" data-gs-bar data-from="'+b.from+'" data-to="'+b.to+'" data-value="'+value+'" data-practice-seconds="'+b.practiceSeconds+'" data-listening-seconds="'+b.listeningSeconds+'" aria-pressed="'+selected+'" aria-label="'+escape(caption)+'"><span class="gs-bar-track"><span class="gs-bar-fill" style="height:'+(precise[i]>0n?Math.max(.6,Number(precise[i])/Number(axisMax)*100):0)+'%">'+layers+'</span></span><span class="gs-bar-label">'+escape(b.label)+'</span></button>';
    });
    html+='</div></div><div class="gs-y-axis" aria-hidden="true">'+[axisMax,axisMax*2n/3n,axisMax/3n,0n].map(n=>'<span>'+escape(axis(n))+'</span>').join('')+'</div></div>';
    const peak=series.reduce((best,b)=>!best||exactSeconds(durationMetric?b.seconds:b.records)>exactSeconds(durationMetric?best.seconds:best.records)?b:best,null);
    const peakValue=peak&&(durationMetric?peak.seconds:peak.records);
    html+='<p class="gs-chart-insight">'+escape(exactSeconds(peakValue)>0n?peak.label+' · '+(durationMetric?duration(peak.seconds):numberLabel(peak.records)+' '+text('records','条记录','條記錄','ཟིན་ཐོ།')):text('Your next saved record starts here.','下一次真实记录，从这里开始。','下一次真實記錄，從這裡開始。','ཟིན་ཐོ་རྗེས་མ་འདི་ནས་འགོ་འཛུགས།'))+'</p>';
    if(r.range==='all'&&series.length>1&&Number(series.at(-1).label)-Number(series[0].label)>30)html+='<p class="gs-note">'+escape(text('Only years with recorded activity are displayed.','仅展示有实际记录的年份。','僅展示有實際記錄的年份。','ཟིན་ཐོ་ཡོད་པའི་ལོ་མངོན།'))+'</p>';
    return html+'</section>';
  }
  function draw(r,focusSelector) {
    if(!valid(r))return;
    const panel=r.root.querySelector('[data-gs-panel]'),today=todayKey(),records=r.records,bounds=period(r.range,r.anchor,today,records),summary=statistics(records,bounds.from,bounds.to,today);
    r.bounds=bounds;
    r.root.querySelectorAll('[data-gs-tab]').forEach(b=>{const selected=b.dataset.gsTab===r.range;b.setAttribute('aria-selected',String(selected));b.tabIndex=selected?0:-1;});
    panel.setAttribute('aria-labelledby','gs-tab-'+r.range);
    if(r.range==='history') {
      panel.innerHTML='<p class="gs-history-intro">'+escape(text('Every saved record, note and current plan remains available here.','每一条原记录、笔记与当前安排，都可以在这里回看。','每一條原記錄、筆記與目前安排，都可以在這裡回看。','ཟིན་ཐོ་དང་ཟིན་བྲིས་འཆར་གཞི་ཚང་མ་འདིར་ལྟ་ཆོག'))+'</p><label class="gs-type-filter">'+escape(text('Record type','记录类型','記錄類型','ཟིན་ཐོའི་རིགས།'))+'<select data-gs-type><option value="all">'+escape(text('All saved information','全部原资料','全部原資料','སྔར་གྱི་གནས་ཚུལ་ཚང་མ།'))+'</option>'+[...new Set(records.map(n=>n.recordKind))].map(kind=>'<option value="'+kind+'" '+(r.filter===kind?'selected':'')+'>'+escape(title(kind))+'</option>').join('')+'<option value="undated" '+(r.filter==='undated'?'selected':'')+'>'+escape(text('No original date','原资料无日期','原資料無日期','སྔར་གྱི་ཚེས་གྲངས་མེད།'))+'</option></select></label>'+recordList(r,records.filter(n=>r.filter==='all'?true:r.filter==='undated'?!n.day:n.recordKind===r.filter),text('My history','我的履历','我的履歷','ངའི་ཟིན་ཐོ།'));
    } else {
      const seconds=summary.seconds,{h,m,s}=durationParts(seconds);
      const nav=r.range==='all'?'':'<div class="gs-period">'+button('‹','data-gs="previous" aria-label="'+escape(text('Previous period','上一时段','上一時段','སྔ་མའི་དུས།'))+'"')+'<label><span>'+escape(text('Choose a date','选择日期','選擇日期','ཚེས་འདེམས།'))+'</span><input type="date" data-gs-anchor value="'+r.anchor+'" min="0001-01-01" max="'+today+'"></label>'+button('›','data-gs="next" '+(bounds.to>=today?'disabled ':'')+'aria-label="'+escape(text('Next period','下一时段','下一時段','རྗེས་མའི་དུས།'))+'"')+button(text('Today','回到今天','回到今天','དེ་རིང་།'),'data-gs="today"','gs-today')+'</div>';
      let html=nav+'<section class="gs-summary" data-gs-summary data-from="'+bounds.from+'" data-to="'+bounds.to+'" '+Object.entries(summary).map(([key,value])=>'data-'+key+'="'+value+'"').join(' ')+'><p class="gs-masthead">'+escape(text('GROWTH · YOUR EVERYDAY','成长足迹 · 日常里的积累','成長足跡 · 日常裡的積累','འཚར་ལོངས་ཀྱི་རྗེས་ཤུལ།'))+'</p><h2 class="gs-message">'+escape(text('Every mindful moment leaves a trace.','把用心，留成看得见的日常。','把用心，留成看得見的日常。','ཉིན་རེའི་སེམས་འཇོག་ཟིན་ཐོར་འཇོག'))+'</h2><p class="gs-eyebrow">'+escape(text('Time in practice & listening','练习与聆听时长','練習與聆聽時長','ཉམས་ལེན་དང་ཉན་པའི་དུས་ཡུན།'))+'</p><div class="gs-total-time" aria-label="'+escape(duration(seconds))+'">'+[[h,text('h','小时','小時','ཆུ་ཚོད།')],[m,text('m','分','分','སྐར་མ།')],[s,text('s','秒','秒','སྐར་ཆ།')]].map(([n,unit])=>'<span><strong>'+escape(numberLabel(n))+'</strong><small>'+escape(unit)+'</small></span>').join('')+'</div><p class="gs-date-caption">'+escape(bounds.from+' — '+(bounds.to>today?today:bounds.to))+'</p><div class="gs-growth-footnote"><span><strong>'+escape(numberLabel(summary.days))+'</strong>'+escape(text('recorded days','个记录日','個記錄日','ཟིན་ཐོའི་ཉིན།'))+'</span><span><strong>'+escape(numberLabel(summary.records))+'</strong>'+escape(text('saved moments','条日常记录','條日常記錄','ཉིན་རེའི་ཟིན་ཐོ།'))+'</span></div><div class="gs-stat-grid">'+[['reflection',summary.reflections,text('Reflections','觉察','覺察','ལྟ་ཞིབ།')],['session',summary.practices,text('Practices','练习','練習','ཉམས་ལེན།')],['music',summary.listens,text('Listening','聆听','聆聽','ཉན་པ།')]].map(([key,value,label])=>button('', 'data-gs-stat="'+key+'"','gs-stat').replace('></button>','><span>'+escape(label)+'</span><strong>'+escape(numberLabel(value))+'</strong><span aria-hidden="true">›</span></button>')).join('')+'</div></section>';
      html+=chart(r,buckets(r.range,bounds,records,today));
      if(r.range==='all') {
        const years=buckets('all',bounds,records,today).filter(b=>b.records>0).reverse();
        if(years.length)html+='<section class="gs-year-strip"><h3>'+escape(text('Revisit a year','回望某一年','回望某一年','ལོ་གཅིག་ལ་ཕྱིར་ལྟ།'))+'</h3><div>'+years.map(y=>button(y.label,'data-gs-year="'+y.label+'"')).join('')+'</div></section>';
      }
      const undated=records.filter(n=>!n.day);
      html+='<p class="gs-note">'+escape(text('Saved practice and listening time only. App-open time is recorded separately.','仅统计已保存的实际练习与聆听时长，打开 APP 的陪伴时长独立记录。','僅統計已儲存的實際練習與聆聽時長，打開 APP 的陪伴時長獨立記錄。','ཉར་བའི་ཉམས་ལེན་དང་ཉན་པའི་དུས་ཡུན་བསྡོམས། APP སྤྱོད་དུས་ལོགས་སུ་བཀོད།'))+'</p>';
      if(undated.length)html+=button(text('Undated information · ','无日期资料 · ','無日期資料 · ','ཚེས་མེད་གནས་ཚུལ། · ')+numberLabel(undated.length),'data-gs="undated"','gs-undated')+'<p class="gs-note">'+escape(text('Undated information remains in History and is not assigned a date or included in time statistics.','无日期资料保留在履历中，不推测日期、不计入时间分布。','無日期資料保留在履歷中，不推測日期、不計入時間分布。','ཚེས་མེད་གནས་ཚུལ་ཟིན་ཐོར་ཉར། ཚེས་མི་ཚོད་དཔག'))+'</p>';
      if(r.selection){let selected=records.filter(n=>n.day&&n.day>=r.selection.from&&n.day<=r.selection.to&&n.day<=today);if(r.selection.kind==='session'||r.selection.kind==='music')selected=selected.filter(n=>n.recordKind===r.selection.kind);else if(r.selection.kind==='reflection')selected=selected.filter(n=>['life','body','mind'].includes(n.recordKind));else selected=selected.filter(activity);html+=recordList(r,selected,r.selection.label||r.selection.from+' — '+r.selection.to);}
      else html+=button(text('View every saved record','查看全部成长履历','查看全部成長履歷','ཟིན་ཐོ་ཚང་མ་ལ་ལྟ།'),'data-gs="history"','gs-history-link');
      panel.innerHTML=html;
    }
    const notice=qualityNotice(records);if(notice){const note=element('p','gs-note',notice);note.dataset.gsQuality='true';panel.prepend(note);}
    const details=r.root.querySelector('[data-gtc-detail]');details.hidden=!r.selected;
    if(r.selected){const node=r.graph.index.get(r.selected);if(node)detail(r,node);else{r.selected=null;details.hidden=true;}}
    if(focusSelector)r.root.querySelector(focusSelector)?.focus({preventScroll:true});
  }
  function mount() {
    const r=ensure(),root=document.querySelector('[data-gtc-root]');r.abort?.abort();r.root=root;if(!root)return;r.page=state.page;
    if(!same(r.actor)){root.querySelector('[data-gs-panel]').textContent=text('Confirm the account before reading records.','确认当前账号后再读取记录。','確認目前帳號後再讀取記錄。','རྩིས་ཐོ་ངེས་གཏན་བྱེད།');return;}
    r.graph=project({wellness:state.wellness,daily:state.daily,lifeNotes:state.lifeNotes,journal:state.journal});r.records=[...r.graph.index.values()].filter(n=>n.kind==='record');
    r.abort=new AbortController();const options={signal:r.abort.signal};
    function refresh(focus){r.selected=null;draw(r,focus);}
    root.addEventListener('click',e=>{
      const b=e.target.closest('button');if(!b||!valid(r))return;
      if(b.hasAttribute('data-gs-record')){const node=r.graph.index.get(b.dataset.gsRecord);if(node?.kind==='record'){r.selected=node.key;const panel=root.querySelector('[data-gtc-detail]');panel.hidden=false;detail(r,node);panel.scrollIntoView({block:'start',behavior:'auto'});panel.querySelector('[data-gs="close-detail"]')?.focus({preventScroll:true});}return;}
      if(b.dataset.gsTab){r.range=b.dataset.gsTab;r.limit=50;r.selection=null;r.filter='all';refresh('[data-gs-tab="'+r.range+'"]');}
      else if(b.dataset.gsMetric){r.metric=b.dataset.gsMetric;refresh('[data-gs-metric="'+r.metric+'"]');}
      else if(b.hasAttribute('data-gs-bar')){r.selection={from:b.dataset.from,to:b.dataset.to};r.limit=50;refresh('[data-gs-bar][data-from="'+b.dataset.from+'"]');root.querySelector('[data-gs-records]')?.scrollIntoView({block:'nearest'});}
      else if(b.dataset.gsStat){r.selection={...r.bounds,kind:b.dataset.gsStat,label:b.innerText.replace('›','').trim()};r.limit=50;refresh();root.querySelector('[data-gs-records]')?.scrollIntoView({block:'nearest'});}
      else if(b.dataset.gsYear){r.range='year';r.anchor=b.dataset.gsYear+'-01-01';r.selection=null;refresh('[data-gs-tab="year"]');}
      else if(b.dataset.gs){const action=b.dataset.gs;
        if(action==='history'||action==='undated'){r.range='history';r.filter=action==='undated'?'undated':'all';r.limit=50;r.selection=null;refresh('[data-gs-tab="history"]');}
        else if(action==='more'){r.limit+=50;refresh();}
        else if(action==='close-detail'){r.selected=null;root.querySelector('[data-gtc-detail]').hidden=true;root.querySelector('[data-gs-record]')?.focus({preventScroll:true});}
        else {if(action==='today')r.anchor=todayKey();else if(action==='previous'||action==='next'){const delta=action==='next'?1:-1;if(r.range==='week')r.anchor=shift(r.bounds.from,delta*7);else{const d=new Date(r.bounds.from+'T12:00:00Z');if(r.range==='month')d.setUTCMonth(d.getUTCMonth()+delta);else d.setUTCFullYear(d.getUTCFullYear()+delta);r.anchor=d.toISOString().slice(0,10);}if(r.anchor<='0000-12-31')r.anchor='0001-01-01';if(r.anchor>todayKey())r.anchor=todayKey();}r.selection=null;r.limit=50;refresh('[data-gs="'+action+'"]');}
      }
    },options);
    root.addEventListener('change',e=>{if(!valid(r))return;if(e.target.matches('[data-gs-anchor]')){const day=date(e.target.value);if(day&&day<=todayKey()){r.anchor=day;r.selection=null;r.limit=50;refresh('[data-gs-anchor]');}}else if(e.target.matches('[data-gs-type]')){r.filter=e.target.value;r.limit=50;refresh('[data-gs-type]');}},options);
    root.addEventListener('keydown',e=>{const tab=e.target.closest('[data-gs-tab]');if(!tab||!['ArrowRight','ArrowLeft','Home','End'].includes(e.key)||!valid(r))return;e.preventDefault();const tabs=[...root.querySelectorAll('[data-gs-tab]')],i=tabs.indexOf(tab),index=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;r.range=tabs[index].dataset.gsTab;r.limit=50;r.selection=null;r.filter='all';refresh('[data-gs-tab="'+r.range+'"]');},options);
    draw(r);
  }
  function fill(element,value){element.textContent=String(value);return element;}
  function element(tag,cls,value){const node=document.createElement(tag);if(cls)node.className=cls;if(value!==undefined)fill(node,value);return node;}
  function fields(value,label,ancestors=new Set()) {
    if(!isObject(value)) {
      const row=element('div','gtc-field'),key=element('span','gtc-field-name',label);
      const displayed=value===null?text('Not supplied (null)','未提供（null）','未提供（null）','བཀོད་མེད། (null)'):value===undefined?text('Not supplied','未提供','未提供','བཀོད་མེད།'):typeof value==='boolean'?(value?text('Yes','是','是','ཡིན།'):text('No','否','否','མིན།')):value===''?text('Empty text','空文本','空文字','ཡི་གེ་སྟོང་པ།'):String(value);
      row.append(key,element('div','gtc-field-value',displayed));return row;
    }
    if(ancestors.has(value))return element('p','gtc-field-value',text('This existing value refers to an earlier field.','此原有值引用了前面的字段。','此原有值引用了前面的欄位。','གནས་ཚུལ་འདི་སྔོན་གྱི་ས་ཁོངས་དང་འབྲེལ།'));
    const next=new Set(ancestors);next.add(value);const group=element('details','gtc-field-branch');group.open=ancestors.size<2;
    const values=entries(value),summary=element('summary','',label+' · '+numberLabel(values.length));group.append(summary);
    const body=element('div','gtc-field-children');
    if(!values.length)body.append(element('p','gtc-empty-value',Array.isArray(value)?'[]':'{}'));
    for(const [key,child] of values){const name=Array.isArray(value)&&/^(0|[1-9]\d*)$/.test(key)?text('Item ','第 ','第 ','ཨང་')+numberLabel(Number(key)+1):Object.prototype.hasOwnProperty.call(labels,key)?text(...labels[key])+' · '+key:key;body.append(fields(child,name,next));}
    group.append(body);return group;
  }
  function detail(r,node) {
    if(!valid(r))return;const panel=r.root.querySelector('[data-gtc-detail]');panel.replaceChildren();
    const close=element('button','gs-detail-back',text('Back to records','返回记录','返回記錄','ཟིན་ཐོར་ལོག'));close.type='button';close.dataset.gs='close-detail';panel.append(close,element('h2','',node.label));
    if(node.kind!=='record') {if(node.recordKind==='plan')panel.append(element('p','gtc-detail-note',text('A default or current plan is an arrangement, not a completed practice.','默认或当前计划是安排，不代表已经完成练习。','預設或目前計畫是安排，不代表已經完成練習。','ཉིན་རེའི་འཆར་གཞི་ནི་ཉམས་ལེན་མཇུག་སྒྲིལ་བ་མིན།')));panel.append(element('p','',text('Select a connected record node to read its original fields.','选择相连的记录节点，查看原有字段。','選擇相連的記錄節點，查看原有欄位。','སྦྲེལ་བའི་ཟིན་ཐོ་བདམས་ནས་གནས་ཚུལ་ལ་ལྟ།')));return;}
    if(['plan','checkpoint','learning','action'].includes(node.recordKind))panel.append(element('p','gtc-detail-note',text('A plan, saved progress, opened content or self-reported action is kept as originally recorded; it does not add measured practice time.','安排、暂存进度、查看内容和本人标记的小行动均按原样保留，不增加实际练习时长。','安排、暫存進度、查看內容和本人標記的小行動均按原樣保留，不增加實際練習時長。','འཆར་གཞི་དང་ཉར་བའི་འཕེལ་རིམ་སྔར་ལྟར་འཇོག ཉམས་ལེན་དུས་ཚོད་མི་སྣོན།')));
    const actions=element('div','gtc-detail-actions');
    const all=element('button','',text('Expand every field','展开全部字段','展開全部欄位','གནས་ཚུལ་ཚང་མ་ཁ་ཕྱེ།'));all.type='button';all.onclick=()=>{if(valid(r))panel.querySelectorAll('details').forEach(d=>{d.open=true;});};actions.append(all);
    if(['life','body','mind'].includes(node.recordKind)&&node.day&&isObject(node.value)&&!Array.isArray(node.value)) {
      const edit=element('button','',text('Edit my original record','编辑原有记录','編輯原有記錄','སྔར་གྱི་ཟིན་ཐོ་བཟོ་བཅོས།'));edit.type='button';edit.onclick=()=>{
        if(!valid(r))return;
        if(node.recordKind==='life'&&typeof editLife==='function')editLife(node.day);
        else if(node.recordKind==='body'&&typeof editBody==='function')editBody(node.day);
        else if(node.recordKind==='mind'&&typeof editMind==='function')editMind(node.day);
      };actions.append(edit);
    }
    panel.append(actions,fields(node.value,text('Original fields','原有字段','原有欄位','སྔར་གྱི་གནས་ཚུལ།')));
  }
  function install() {
    if(installed)return true;if(typeof screens!=='object'||typeof renderNow!=='function')return false;
    original.growth=screens.growth;original.render=renderNow;screens.growth=screen;
    if(typeof journeyGrowth==='function'){original.journeyGrowth=journeyGrowth;journeyGrowth=screen;}
    if(typeof showGrowth==='function'){original.showGrowth=showGrowth;showGrowth=screen;}
    renderNow=function(...args){const result=original.render.apply(this,args);mount();return result;};
    if(typeof psSwitch==='function'){original.switch=psSwitch;psSwitch=function(...args){const before=token(),result=original.switch.apply(this,args),after=token();if(before.scope!==after.scope||before.epoch!==after.epoch){runtime?.abort?.abort();runtime?.resize?.disconnect();const root=document.querySelector('[data-gtc-root]');if(root)root.replaceChildren();runtime=null;}return result;};}
    installed=true;if(typeof state==='object'&&state.page==='growth'&&typeof render==='function')render(false);return true;
  }
  const api=Object.freeze({install,project,screen,statistics,period,buckets,qualityNotice,candidateOnly:false,explicitInstallationRequired:true});
  if(typeof module==='object'&&module.exports)module.exports=api;
  else global.GrowthTreeCandidate=api;
})(typeof window==='object'?window:globalThis);
