// Company analytics: aggregated users only; no personal record or conversation export.
const anStyle=document.createElement('style');
anStyle.textContent='.an-controls{display:flex;align-items:end;gap:12px;flex-wrap:wrap}.an-controls label{flex:1;min-width:140px;font-size:12px}.an-controls .actions{padding-bottom:1px}.an-presets{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px}.an-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:18px 0}.an-summary span,.an-retention small{display:block;color:var(--muted);font-size:12px}.an-summary strong{font-size:22px}.an-chart{display:block;width:100%;height:auto;max-height:300px;margin-top:16px}.an-chart text{font:12px Arial,sans-serif;fill:var(--muted)}.an-grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:20px}.an-grid>section{min-width:0}.an-retention{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:20px 0}.an-retention strong{display:block;font-size:26px}.an-detail{margin-top:16px}.an-window small{display:block;font-size:11px;color:var(--muted);margin-top:9px}.an-state{font-size:11px;color:var(--muted)}@media(max-width:900px){.an-grid{grid-template-columns:1fr}}@media(max-width:600px){.an-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.an-window strong{font-size:25px}.an-controls .actions{width:100%}.an-retention{gap:12px}.an-chart text{font-size:29px}}';
document.head.append(anStyle);
function anToday(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
function anShift(day,n){return new Date(Date.parse(day+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);}
function anNumber(n){return n===null||n===undefined?'未采集':Number(n).toLocaleString('zh-CN',{maximumFractionDigits:2});}
function anCoverage(value){return ({uncollected:'未采集',partial:'部分覆盖／进行中',complete:'完整覆盖'})[value]||'';}
function anLocalTime(value){return value?new Date(value).toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'}):'尚未开始';}
function anTable(headers,rows){return table(headers,rows).replace('class="table-wrap"','class="table-wrap" data-enhanced="true"');}
function anChart(rows){
 const values=rows.map(x=>x.activeUsers),valid=values.filter(x=>typeof x==='number');
 if(!valid.length)return '<div class="empty">所选区间尚未采集活跃数据</div>';
 const left=94,right=780,top=20,bottom=192,max=Math.max(2,Math.ceil(Math.max(...valid)/2)*2),x=i=>left+(rows.length===1?(right-left)/2:i/(rows.length-1)*(right-left)),y=v=>bottom-v/max*(bottom-top);
 let lines='',points=[];
 function flush(){if(!points.length)return;lines+='<polyline points="'+points.join(' ')+'" fill="none" stroke="#087e83" stroke-width="2.5"/>';points=[];}
 values.forEach((v,i)=>{if(typeof v==='number')points.push(x(i).toFixed(1)+','+y(v).toFixed(1));else flush();});flush();
 if(valid.length===1){const i=values.findIndex(v=>typeof v==='number');lines+='<circle cx="'+x(i)+'" cy="'+y(values[i])+'" r="4" fill="#087e83"/>';}
 const labels=[0,Math.floor((rows.length-1)/2),rows.length-1].filter((v,i,a)=>a.indexOf(v)===i);
 return '<svg class="an-chart" viewBox="0 0 820 230" role="img" aria-label="所选区间每个周期内去重的活跃用户趋势；未采集时段留空"><title>活跃用户趋势，单位：人</title>'+[0,.5,1].map(p=>'<line x1="'+left+'" y1="'+y(max*p)+'" x2="'+right+'" y2="'+y(max*p)+'" stroke="#d7e3e6" stroke-dasharray="4 4"/><text x="82" y="'+(y(max*p)+4)+'" text-anchor="end">'+new Intl.NumberFormat('zh-CN',{notation:'compact',maximumFractionDigits:1}).format(Math.round(max*p))+'</text>').join('')+lines+labels.map(i=>'<text x="'+x(i)+'" y="219" text-anchor="'+(i===0?'start':i===rows.length-1?'end':'middle')+'">'+esc(rows[i].date)+'</text>').join('')+'</svg>';
}
async function loadAnalyticsAdmin(seq){
 const end=anToday();state.analyticsFilters??={start:anShift(end,-29),end,grain:'day'};
 let data;try{data=await api('admin/analytics?'+new URLSearchParams(state.analyticsFilters));}catch(error){if(seq===state.seq)state.analytics=null;throw error;}
 if(seq!==state.seq||state.nav!=='analytics')return;
 state.analytics=data;renderAnalyticsAdmin();
}
function renderAnalyticsAdmin(){
 const d=state.analytics,f=state.analyticsFilters,today=anToday();
 const windows=[['day','今日活跃','DAU'],['week','本周活跃','WAU'],['month','本月活跃','MAU'],['year','本年活跃','YAU']];
 const featureRows=(d.features||[]).filter(x=>x.activeUsers>0||x.visits>0);
 document.getElementById('main').innerHTML=heading('数据中心','<div class="actions"><button class="btn secondary" data-nav="analytics">刷新</button><button class="btn" data-action="analytics-export">导出汇总 CSV</button></div>')+
 '<p class="hint">北京时间 · APP 内登录的普通用户与创作者 · 不含管理人员和未登录访问</p><div class="stats">'+windows.map(([key,label,short])=>{const w=d.windows[key];return '<div class="stat an-window"><span>'+label+' · '+short+'</span><strong>'+anNumber(w.activeUsers)+'</strong><small>'+esc(w.start)+' 至 '+esc(w.end)+'</small><small>'+anCoverage(w.coverage)+'</small></div>';}).join('')+'</div>'+
 '<p class="hint">以上四项按自然日、周一开始的自然周、自然月、自然年去重，截至当前。同一账号在一个周期内只计 1 人。</p>'+
 '<section class="panel"><h2>活跃趋势</h2><p class="hint">采集开始：'+esc(anLocalTime(d.collectedSince))+'。此前活跃数据标为“未采集”；今天仍在累计，未覆盖时段不补算。</p>'+
 '<form id="analytics-filter" class="an-controls"><label>开始日期<input type="date" name="start" value="'+esc(f.start)+'" max="'+today+'" required></label><label>结束日期<input type="date" name="end" value="'+esc(f.end)+'" max="'+today+'" required></label><label>汇总周期<select name="grain">'+[['day','按日'],['week','按周'],['month','按月'],['year','按年']].map(([k,v])=>'<option value="'+k+'" '+(f.grain===k?'selected':'')+'>'+v+'</option>').join('')+'</select></label><div class="actions"><button class="btn">查询</button></div></form>'+
 '<div class="an-presets">'+[7,30,90,365].map(n=>'<button class="btn secondary small" data-an-days="'+n+'">近 '+n+' 天</button>').join('')+'</div>'+
 '<p class="an-state">区间活跃覆盖：'+anCoverage(d.summary.coverage)+'</p><div class="an-summary">'+[['区间活跃用户',d.summary.activeUsers],['区间新增用户',d.summary.newUsers],['当前用户账号',d.summary.registeredUsers],['区间功能访问',d.summary.visits]].map(([label,value])=>'<div><span>'+label+'</span><strong>'+anNumber(value)+'</strong></div>').join('')+'</div>'+anChart(d.trend)+
 '<p class="hint">曲线为每个周期内去重的活跃人数，跨周期相加不等于区间活跃人数。功能访问按同账号、同功能 30 秒去重；续用心跳只计活跃，不增加访问。</p>'+
 '<details class="an-detail"><summary>查看周期数据明细</summary>'+anTable(['周期开始','周期结束','活跃用户','新增用户','功能访问','覆盖情况'],d.trend.map(x=>[esc(x.date),esc(x.end),anNumber(x.activeUsers),anNumber(x.newUsers),anNumber(x.visits),anCoverage(x.coverage)]))+'</details></section>'+
 '<div class="an-grid"><section class="panel"><h2>功能使用</h2><p class="hint">所选区间内实际使用的功能；同一用户可使用多个功能，各行人数不相加。</p>'+(d.summary.coverage==='uncollected'?'<div class="empty">所选区间未采集功能使用数据</div>':anTable(['功能','使用用户','访问次数'],featureRows.map(x=>[esc(x.label),anNumber(x.activeUsers),anNumber(x.visits)])))+'</section>'+
 '<section class="panel"><h2>新增用户留存</h2><div class="an-retention">'+(d.retention||[]).map(x=>'<div><span>'+(x.days===1?'次日留存':x.days+' 日留存')+'</span><strong>'+(x.rate===null?'—':anNumber(x.rate)+'%')+'</strong><small>'+(x.eligibleUsers?anNumber(x.returnedUsers)+' / '+anNumber(x.eligibleUsers)+' 个成熟样本':'暂无成熟样本')+'</small></div>').join('')+'</div><p class="hint">按所选区间内注册的账号计算第 1／7 个自然日是否活跃。仅纳入采集开始后注册，且观察日已完整结束的账号；采集前注册及尚未到期的账号不进入分母。</p></section></div>'+
 '<p class="hint">新增用户来自账号注册时间；活跃与功能使用来自 APP 前台实际采集。仅汇总账号关联的功能使用与时间，不采集出生资料、自评或聊天正文。更新于 '+esc(anLocalTime(d.generatedAt))+'。</p>';
}
function exportAnalyticsAdmin(){
 const d=state.analytics;if(!d)return;
 const rows=[['数据集','周期开始','周期结束','指标','数值','单位','说明']],add=(group,start,end,label,value,unit,note='')=>rows.push([group,start,end,label,value===null?'未采集':value,unit,note]);
 add('口径','','','统计时区',d.timezone,'','');add('口径','','','活跃采集开始',d.collectedSince,'','采集前不补算；仅APP登录普通用户与创作者');
 for(const [key,w] of Object.entries(d.windows))add('当前周期活跃',w.start,w.end,({day:'日活DAU',week:'周活WAU',month:'月活MAU',year:'年活YAU'})[key],w.activeUsers,'人',anCoverage(w.coverage));
 for(const [key,label] of [['activeUsers','区间去重活跃用户'],['newUsers','区间新增用户'],['registeredUsers','当前用户账号'],['visits','区间功能访问']])add('区间汇总',d.range.start,d.range.end,label,d.summary[key],key==='visits'?'次':'人',key==='registeredUsers'?'当前账号数，不受日期筛选影响':key==='newUsers'?'真实账号注册数据':anCoverage(d.summary.coverage));
 for(const x of d.trend)for(const [key,label,unit] of [['activeUsers','活跃用户','人'],['newUsers','新增用户','人'],['visits','功能访问','次']])add('趋势/'+d.range.grain,x.date,x.end,label,x[key],unit,key==='newUsers'?'真实账号注册数据':anCoverage(x.coverage));
 for(const x of d.features)for(const [key,label,unit] of [['activeUsers','使用用户','人'],['visits','访问次数','次']])add('功能使用',d.range.start,d.range.end,x.label+'/'+label,x[key],unit,'同账号同功能30秒去重');
 for(const x of d.retention)for(const [key,label,unit] of [['eligibleUsers','成熟样本','人'],['returnedUsers','回访用户','人'],['rate','留存率','%']])add(x.days+'日留存',d.range.start,d.range.end,label,x[key]===null?'暂无成熟样本':x[key],unit,'观察日完整结束；采集启用后注册');
 downloadAdmin('东方智慧数据中心-'+d.range.start+'至'+d.range.end+'-'+d.range.grain+'.csv','\ufeff'+rows.map(row=>row.map(csvCell).join(',')).join('\r\n'),'text/csv;charset=utf-8');toast('已导出当前查询的完整汇总数据');
}
document.addEventListener('submit',e=>{if(e.target.id!=='analytics-filter')return;e.preventDefault();state.analyticsFilters=Object.fromEntries(new FormData(e.target));load('analytics');});
document.addEventListener('click',e=>{if(e.target.closest('[data-an-reset]')){state.analyticsFilters=null;load('analytics');return;}const preset=e.target.closest('[data-an-days]');if(preset){const end=anToday();state.analyticsFilters={start:anShift(end,1-Number(preset.dataset.anDays)),end,grain:state.analyticsFilters?.grain||'day'};load('analytics');return;}if(e.target.closest('[data-action="analytics-export"]'))exportAnalyticsAdmin();});
