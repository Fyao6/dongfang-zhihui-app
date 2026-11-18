from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
js=ROOT/'04_研发源码/app/r4/growth-tree.js'
old=js.read_text(encoding='utf-8')
baseline=json.loads((ROOT/'06_验证与后续工作/当前产品可靠性-最终稳定构建记录.json').read_text(encoding='utf-8'))
assert hashlib.sha256(js.read_bytes()).hexdigest()==baseline['actualSourceAndBuildHashes']['04_研发源码/app/r4/growth-tree.js'], 'One-time historical patch requires the original tree source; do not reapply to the later statistics implementation.'
prefix=old[:old.index('  function ensure()')]
projection=old[old.index('  function project(personal)'):old.index('  function screen()')]
fields=old[old.index('  function fill('):old.index('  function shownChildren(')]
install=old[old.index('  function install()'):]
install=install.replace('{install,project,screen,candidateOnly:false,explicitInstallationRequired:true}', '{install,project,screen,statistics,period,buckets,candidateOnly:false,explicitInstallationRequired:true}')
prefix=prefix.replace('/* Connected personal-record tree. The product build explicitly calls\n * GrowthTreeCandidate.install() after existing feature modules.\n * No network, storage migration, seed, timer, or business write is performed.\n */','/* Growth statistics, following the user\'s 2026-11-18 visual reference.\n * The existing module name is retained for build compatibility.\n * Read-only projection: no migration, synthetic history or timer writes.\n */')
ui=r'''
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
    const days=records.filter(n=>n.day&&n.day<=today).map(n=>n.day).sort();
    return {from:days[0]||today,to:today};
  }
  const activityKinds=new Set(['life','body','mind','session','music','checkin','card','traits']);
  function activity(n) {return activityKinds.has(n.recordKind)||(n.recordKind==='action'&&isObject(n.value)&&!!n.value.doneAt);}
  function measured(n) {
    if(!['session','music'].includes(n.recordKind)||!isObject(n.value))return 0;
    const value=n.value.seconds;
    return typeof value==='number'&&Number.isFinite(value)&&value>=0?value:0;
  }
  function statistics(records,from,to,today=todayKey()) {
    const real=records.filter(n=>activity(n)&&n.day&&n.day>=from&&n.day<=to&&n.day<=today);
    const practices=real.filter(n=>n.recordKind==='session'),listens=real.filter(n=>n.recordKind==='music');
    return {seconds:real.reduce((sum,n)=>sum+measured(n),0),records:real.length,practices:practices.length,listens:listens.length,
      days:new Set(real.map(n=>n.day)).size,reflections:real.filter(n=>['life','body','mind'].includes(n.recordKind)).length};
  }
  function buckets(range,bounds,records,today=todayKey()) {
    const result=[];
    if(range==='week'||range==='month') {for(let d=bounds.from;d<=bounds.to;d=shift(d,1))result.push({from:d,to:d,label:range==='week'?d.slice(5):String(Number(d.slice(8)))});}
    else if(range==='year')for(let m=1;m<=12;m++){const from=bounds.from.slice(0,4)+'-'+String(m).padStart(2,'0')+'-01';result.push({from,to:monthEnd(from),label:String(m)});}
    else {
      const actual=[...new Set(records.filter(n=>activity(n)&&n.day&&n.day<=today).map(n=>n.day.slice(0,4)))].sort();
      const first=Number(actual[0]||today.slice(0,4)),last=Number(today.slice(0,4));
      const years=last-first<=30?Array.from({length:last-first+1},(_,i)=>String(first+i).padStart(4,'0')):actual;
      for(const year of years)result.push({from:year+'-01-01',to:year+'-12-31',label:year});
    }
    return result.map(b=>({...b,...statistics(records,b.from,b.to,today)}));
  }
  function duration(seconds) {
    const n=Math.floor(seconds),h=Math.floor(n/3600),m=Math.floor(n%3600/60),s=n%60;
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
    const values=series.map(b=>r.metric==='duration'?b.seconds:b.records),max=Math.max(1,...values),durationMetric=r.metric==='duration';
    const axisMax=durationMetric?Math.max(60,Math.ceil(max/(max>3600?3600:max>600?600:60))*(max>3600?3600:max>600?600:60)):Math.max(3,Math.ceil(max/3)*3);
    const axis=n=>durationMetric?(axisMax>=3600?numberLabel(Math.round(n/360)/10)+'h':numberLabel(Math.round(n/6)/10)+text('m','分','分','སྐར་མ།')):numberLabel(Math.round(n));
    let html='<section class="gs-chart-card"><div class="gs-section-heading"><h2>'+escape(text('Your growth over time','成长分布','成長分布','འཚར་ལོངས་ཁྱབ་ཚུལ།'))+'</h2><span aria-hidden="true">▥</span></div><div class="gs-metrics" role="group" aria-label="'+escape(text('Chart metric','图表指标','圖表指標','རིས་ཀྱི་ཚད།'))+'">'+button(text('Duration','时长','時長','དུས་ཡུན།'),'data-gs-metric="duration" aria-pressed="'+durationMetric+'"')+button(text('Records','记录','記錄','ཟིན་ཐོ།'),'data-gs-metric="records" aria-pressed="'+!durationMetric+'"')+'</div>';
    html+='<div class="gs-plot"><div class="gs-chart-scroll" tabindex="0" aria-label="'+escape(text('Time chart. Scroll horizontally for more dates.','时间分布图，可横向滑动查看更多日期。','時間分布圖，可橫向滑動查看更多日期。','དུས་ཀྱི་རིས། གཡས་གཡོན་སྤོ་ནས་ལྟ་ཆོག'))+'"><div class="gs-chart-grid" style="--gs-columns:'+series.length+';min-width:'+Math.max(210,series.length*36)+'px">';
    series.forEach((b,i)=>{const value=values[i],selected=r.selection?.from===b.from&&r.selection?.to===b.to;html+='<button type="button" class="gs-bar" data-gs-bar data-from="'+b.from+'" data-to="'+b.to+'" data-value="'+value+'" aria-pressed="'+selected+'" aria-label="'+escape(b.from+' — '+b.to+' · '+(durationMetric?duration(value):numberLabel(value)+' '+text('records','条记录','條記錄','ཟིན་ཐོ།')))+'"><span class="gs-bar-track"><span class="gs-bar-fill" style="height:'+(value?Math.max(1.5,value/axisMax*100):0)+'%"></span></span><span class="gs-bar-label">'+escape(b.label)+'</span></button>';});
    html+='</div></div><div class="gs-y-axis" aria-hidden="true">'+[axisMax,axisMax*2/3,axisMax/3,0].map(n=>'<span>'+escape(axis(n))+'</span>').join('')+'</div></div>';
    const peak=series.reduce((best,b)=>!best||(durationMetric?b.seconds>best.seconds:b.records>best.records)?b:best,null);
    const peakValue=peak&&(durationMetric?peak.seconds:peak.records);
    html+='<p class="gs-chart-insight">'+escape(peakValue?peak.label+' · '+(durationMetric?duration(peak.seconds):numberLabel(peak.records)+' '+text('records','条记录','條記錄','ཟིན་ཐོ།')):text('Your next saved record starts here.','下一次真实记录，从这里开始。','下一次真實記錄，從這裡開始。','ཟིན་ཐོ་རྗེས་མ་འདི་ནས་འགོ་འཛུགས།'))+'</p>';
    if(!durationMetric&&r.range==='all'&&series.length>1&&Number(series.at(-1).label)-Number(series[0].label)>30)html+='<p class="gs-note">'+escape(text('Only years with recorded activity are displayed.','仅展示有实际记录的年份。','僅展示有實際記錄的年份。','ཟིན་ཐོ་ཡོད་པའི་ལོ་མངོན།'))+'</p>';
    return html+'</section>';
  }
  function draw(r,focusSelector) {
    if(!valid(r))return;
    const panel=r.root.querySelector('[data-gs-panel]'),today=todayKey(),records=r.records,bounds=period(r.range,r.anchor,today,records),summary=statistics(records,bounds.from,bounds.to,today);
    r.bounds=bounds;
    r.root.querySelectorAll('[data-gs-tab]').forEach(b=>{const selected=b.dataset.gsTab===r.range;b.setAttribute('aria-selected',String(selected));b.tabIndex=selected?0:-1;});
    panel.setAttribute('aria-labelledby','gs-tab-'+r.range);
    if(r.range==='history') {
      panel.innerHTML='<p class="gs-history-intro">'+escape(text('Every saved record, note and current plan remains available here.','每一条原记录、笔记与当前安排，都可以在这里回看。','每一條原記錄、筆記與目前安排，都可以在這裡回看。','ཟིན་ཐོ་དང་ཟིན་བྲིས་འཆར་གཞི་ཚང་མ་འདིར་ལྟ་ཆོག'))+'</p><label class="gs-type-filter">'+escape(text('Record type','记录类型','記錄類型','ཟིན་ཐོའི་རིགས།'))+'<select data-gs-type><option value="all">'+escape(text('All saved information','全部原资料','全部原資料','སྔར་གྱི་གནས་ཚུལ་ཚང་མ།'))+'</option>'+[...new Set(records.map(n=>n.recordKind))].map(kind=>'<option value="'+kind+'" '+(r.filter===kind?'selected':'')+'>'+escape(title(kind))+'</option>').join('')+'<option value="undated" '+(r.filter==='undated'?'selected':'')+'>'+escape(text('No original date','原资料无日期','原資料無日期','སྔར་གྱི་ཚེས་གྲངས་མེད།'))+'</option></select></label>'+recordList(r,records.filter(n=>r.filter==='all'||r.filter==='undated'?!n.day||r.filter==='all':n.recordKind===r.filter),text('My history','我的履历','我的履歷','ངའི་ཟིན་ཐོ།'));
    } else {
      const seconds=Math.floor(summary.seconds),h=Math.floor(seconds/3600),m=Math.floor(seconds%3600/60),s=seconds%60;
      const nav=r.range==='all'?'':'<div class="gs-period">'+button('‹','data-gs="previous" aria-label="'+escape(text('Previous period','上一时段','上一時段','སྔ་མའི་དུས།'))+'"')+'<label><span>'+escape(text('Choose a date','选择日期','選擇日期','ཚེས་འདེམས།'))+'</span><input type="date" data-gs-anchor value="'+r.anchor+'" min="0001-01-01" max="'+today+'"></label>'+button('›','data-gs="next" '+(bounds.to>=today?'disabled ':'')+'aria-label="'+escape(text('Next period','下一时段','下一時段','རྗེས་མའི་དུས།'))+'"')+button(text('Today','回到今天','回到今天','དེ་རིང་།'),'data-gs="today"','gs-today')+'</div>';
      let html=nav+'<section class="gs-summary" data-gs-summary data-from="'+bounds.from+'" data-to="'+bounds.to+'" '+Object.entries(summary).map(([key,value])=>'data-'+key+'="'+value+'"').join(' ')+'><p class="gs-eyebrow">'+escape(text('PRACTICE & LISTENING','练习与聆听时长','練習與聆聽時長','ཉམས་ལེན་དང་ཉན་པའི་དུས་ཡུན།'))+'</p><div class="gs-total-time" aria-label="'+escape(duration(seconds))+'">'+[[h,text('h','小时','小時','ཆུ་ཚོད།')],[m,text('m','分','分','སྐར་མ།')],[s,text('s','秒','秒','སྐར་ཆ།')]].map(([n,unit])=>'<span><strong>'+escape(numberLabel(n))+'</strong><small>'+escape(unit)+'</small></span>').join('')+'</div><p class="gs-date-caption">'+escape(bounds.from+' — '+(bounds.to>today?today:bounds.to))+'</p><div class="gs-stat-grid">'+[['session',summary.practices,text('Practices','练习','練習','ཉམས་ལེན།')],['music',summary.listens,text('Listening sessions','聆听','聆聽','ཉན་པ།')],['days',summary.days,text('Recorded days','记录天数','記錄天數','ཟིན་ཐོའི་ཉིན།')],['reflection',summary.reflections,text('Reflections','觉察','覺察','ལྟ་ཞིབ།')]].map(([key,value,label])=>button('', 'data-gs-stat="'+key+'"','gs-stat').replace('></button>','><span>'+escape(label)+'</span><strong>'+escape(numberLabel(value))+'</strong><span aria-hidden="true">›</span></button>')).join('')+'</div></section>';
      if(r.range==='all') {
        const years=buckets('all',bounds,records,today).filter(b=>b.records>0).slice(-3).reverse();
        if(years.length)html+='<div class="gs-year-cards" aria-label="'+escape(text('Yearly overviews','年度概览','年度概覽','ལོའི་སྤྱི་བལྟ།'))+'">'+years.map(y=>{const months=buckets('year',{from:y.from,to:y.to},records,today),max=Math.max(1,...months.map(m=>m.records));return '<button type="button" class="gs-year-card" data-gs-year="'+y.label+'"><strong>'+escape(y.label)+'</strong><small>'+escape(text('Year in review','年度概览','年度概覽','ལོའི་སྤྱི་བལྟ།'))+'</small><span class="gs-spark" aria-hidden="true">'+months.map(m=>'<i style="--gs-height:'+(m.records?Math.max(8,m.records/max*100):0)+'%"></i>').join('')+'</span></button>';}).join('')+'</div>';
      }
      html+=chart(r,buckets(r.range,bounds,records,today));
      const undated=records.filter(n=>!n.day);
      html+='<p class="gs-note">'+escape(text('Saved practice and listening time only. App-open time is recorded separately.','仅统计已保存的实际练习与聆听时长，打开 APP 的陪伴时长独立记录。','僅統計已儲存的實際練習與聆聽時長，打開 APP 的陪伴時長獨立記錄。','ཉར་བའི་ཉམས་ལེན་དང་ཉན་པའི་དུས་ཡུན་བསྡོམས། APP སྤྱོད་དུས་ལོགས་སུ་བཀོད།'))+'</p>';
      if(undated.length)html+=button(text('Undated information · ','无日期资料 · ','無日期資料 · ','ཚེས་མེད་གནས་ཚུལ། · ')+numberLabel(undated.length),'data-gs="undated"','gs-undated')+'<p class="gs-note">'+escape(text('Undated information remains in History and is not assigned a date or included in time statistics.','无日期资料保留在履历中，不推测日期、不计入时间分布。','無日期資料保留在履歷中，不推測日期、不計入時間分布。','ཚེས་མེད་གནས་ཚུལ་ཟིན་ཐོར་ཉར། ཚེས་མི་ཚོད་དཔག'))+'</p>';
      if(r.selection){let selected=records.filter(n=>n.day&&n.day>=r.selection.from&&n.day<=r.selection.to&&n.day<=today);if(r.selection.kind==='session'||r.selection.kind==='music')selected=selected.filter(n=>n.recordKind===r.selection.kind);else if(r.selection.kind==='reflection')selected=selected.filter(n=>['life','body','mind'].includes(n.recordKind));else selected=selected.filter(activity);html+=recordList(r,selected,r.selection.label||r.selection.from+' — '+r.selection.to);}
      else html+=button(text('View every saved record','查看全部成长履历','查看全部成長履歷','ཟིན་ཐོ་ཚང་མ་ལ་ལྟ།'),'data-gs="history"','gs-history-link');
      panel.innerHTML=html;
    }
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
      if(b.hasAttribute('data-gs-record')){const node=r.graph.index.get(b.dataset.gsRecord);if(node?.kind==='record'){r.selected=node.key;const panel=root.querySelector('[data-gtc-detail]');panel.hidden=false;detail(r,node);const close=element('button','gs-detail-back',text('Back to records','返回记录','返回記錄','ཟིན་ཐོར་ལོག'));close.type='button';close.dataset.gs='close-detail';panel.prepend(close);panel.scrollIntoView({block:'start',behavior:'auto'});close.focus({preventScroll:true});}return;}
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
'''
js.write_text(prefix+ui[:ui.index('  function todayKey()')]+projection+ui+fields+install,encoding='utf-8',newline='\n')
print('Updated existing growth module with statistics UI; preserved original projection and detail fields.')
