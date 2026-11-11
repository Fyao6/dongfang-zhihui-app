// Reference-proportion Ba Zi workspace. The default table exposes all seven rows.
// Values come from the same deterministic adapters; no copied sample chart is used.
function lcbElement(value){return ({甲:'wood',乙:'wood',寅:'wood',卯:'wood',丙:'fire',丁:'fire',巳:'fire',午:'fire',戊:'earth',己:'earth',辰:'earth',戌:'earth',丑:'earth',未:'earth',庚:'metal',辛:'metal',申:'metal',酉:'metal',壬:'water',癸:'water',亥:'water',子:'water'})[value]||'';}
function lcbColored(value,cls=''){return `<span class="lcb-element ${cls}" data-element="${lcbElement(value)}">${esc(value)}</span>`;}
function lcbShortGod(value){return ({比肩:'比',劫财:'劫',食神:'食',伤官:'伤',偏财:'才',正财:'财',七杀:'杀',正官:'官',偏印:'枭',正印:'印',日主:'元'})[value]||value;}
function lcbHiddenPairs(column,compact=false){return column.hiddenStems.map((stem,i)=>`<span class="lcb-hidden-pair">${lcbColored(stem)}<span title="${esc(column.branchTenGods[i])}">${compact?esc(lcbShortGod(column.branchTenGods[i])):lcbTenGodButtons([column.branchTenGods[i]])}</span></span>`).join('');}
function lcbColumnTitles(){const labels=lcbLabels(),short=(english,label)=>lcbText(english,label,label,label);return {year:short('Year',labels.year),month:short('Month',labels.month),day:short('Day',labels.day),time:short('Hour',labels.time),period:short('Period',labels.periods),flowYear:short('Annual',labels.years),flowMonth:lcbText('Monthly','流月','流月','ཟླ།')};}
function lcbBoard(result,state,timing){
 const labels=lcbLabels(),comparison=lcbBuildComparison(result,{...state.selection,beforeStart:timing.beforeStart}),view=lcbTimelineView(state),columns=comparison.columns.slice(0,view.showFlowMonth?7:6),birth=state.normalized.china,period=result.periods[state.selection.period],year=period.years[state.selection.year],titles=lcbColumnTitles();
 const stamps={year:birth.year,month:String(birth.month).padStart(2,'0'),day:String(birth.day).padStart(2,'0'),time:String(birth.hour).padStart(2,'0')+':'+String(birth.minute).padStart(2,'0'),period:period.startYear,flowYear:year.year,flowMonth:lcbMonthInterval(year.year,state.selection.month).start.slice(5,10)};
 const cell=(column,field,value)=>`<td data-lcb-board-column="${column.key}" data-field="${field}" class="${column.key==='period'?'is-period-start':''}">${column.available?value:'—'}</td>`;
 const row=(field,label,read,cls='')=>`<tr class="${cls}" data-lcb-row="${field}"><th scope="row">${label}</th>${columns.map(p=>cell(p,field,read(p))).join('')}</tr>`;
 const tenGod=p=>p.key==='day'?lcbText('Day master',state.normalized.birth.sex==='male'?'元男':'元女',state.normalized.birth.sex==='male'?'元男':'元女','ཉིན་གྱི་གནམ་སྡོང་།'):p.stemTenGod;
 return `<section class="lcb-board" data-lcb-board><div class="lcb-board-scroll" data-lcb-board-scroll tabindex="0" role="region" aria-label="${lcbText('Natal and selected period table','四柱与所选运年表','四柱與所選運年表','ཀ་བ་བཞི་དང་དུས་རབས་རེའུ་མིག')}" style="--lcb-columns:${columns.length}"><table id="lcb-main-board"><colgroup><col class="lcb-board-label">${columns.map(()=>'<col>').join('')}</colgroup><thead><tr><th scope="col">${lcbText('Time','时间','時間','དུས།')}</th>${columns.map(p=>`<th scope="col" data-lcb-heading="${p.key}" class="${p.key==='period'?'is-period-start':''}"><span>${titles[p.key]}</span><small>${p.available?stamps[p.key]:'—'}</small></th>`).join('')}</tr></thead><tbody>
 ${row('stemTenGod',lcbTermButton('stemTenGod',lcbText('Ten Gods','十神','十神','འབྲེལ་བ།')),p=>`<span data-element="${lcbElement(p.stem)}" class="lcb-element">${p.key==='day'?lcbTermButton('dayMaster',tenGod(p)):lcbTenGodButtons([p.stemTenGod])}</span>`,'lcb-board-gods')}
 ${row('stem',lcbText('Stem','天干','天干','གནམ་སྡོང་།'),p=>lcbColored(p.stem),'lcb-board-symbol')}
 ${row('branch',lcbText('Branch','地支','地支','ས་ཡལ།'),p=>lcbColored(p.branch),'lcb-board-symbol')}
 </tbody><tbody id="lcb-board-extra" ${view.boardExpanded?'':'hidden'}>${row('hiddenStems',lcbTermButton('hiddenStems',labels.hidden),p=>lcbHiddenPairs(p,true),'lcb-board-hidden')}
 ${row('growthStage',lcbTermButton('growthStage',lcbText('Stage','星运','星運','འཚར་སྐྱེ།')),p=>esc(p.growthStage),'lcb-board-meta')}
 ${row('naYin',lcbTermButton('naYin',labels.naYin),p=>esc(p.naYin),'lcb-board-meta')}
 ${row('voidBranches',lcbTermButton('voidBranches',lcbText('Void','空亡','空亡','སྟོང་ཡལ།')),p=>esc(p.voidBranches),'lcb-board-meta')}
 </tbody></table></div><div class="lcb-board-options"><button type="button" data-lcb-action="board-details" aria-controls="lcb-board-extra" aria-expanded="${!!view.boardExpanded}"><span class="ew-disclosure-label">${view.boardExpanded?lcbText('Hide details','收起详细字段','收起詳細欄位','ཞིབ་ཕྲ་བསྡུ།'):lcbText('Hidden stems & details','藏干 · 纳音等','藏干 · 納音等','སྦས་སྡོང་དང་ཞིབ་ཕྲ།')}</span>${icon('chevron','ew-disclosure-icon')}</button><button type="button" data-lcb-action="flow-month" aria-controls="lcb-main-board" aria-pressed="${!!view.showFlowMonth}"><span class="ew-disclosure-label">${view.showFlowMonth?lcbText('Hide month column','收起流月列','收起流月欄','ཟླའི་ཀ་བ་བསྡུ།'):lcbText('Month column','流月列','流月欄','ཟླའི་ཀ་བ།')}</span>${icon('chevron','ew-disclosure-icon')}</button></div></section>`;
}
function lcbTableTimeline(result,state,timing,periodIndex,yearIndex,monthIndex){
 const labels=lcbLabels(),period=result.periods[periodIndex],year=period.years[yearIndex],month=year?.months?.[monthIndex],dayMaster=result.pillars.find(p=>p.key==='day').stem;
 const symbols=ganZhi=>{if(!ganZhi)return `<span class="lcb-rail-before">${lcbText('Before\nstart','起运前','起運前','སྔོན།')}</span>`;const p=lcbDescribePillar(ganZhi,dayMaster);return `<span class="lcb-rail-symbols"><span>${lcbColored(p.stem)}<small>${esc(lcbShortGod(p.stemTenGod))}</small></span><span>${lcbColored(p.branch)}<small>${p.branchTenGods.map(g=>`<i>${esc(lcbShortGod(g))}</i>`).join('')}</small></span></span>`;};
 const heading=(step,title,value,detail,id)=>`<header class="lcb-stage-heading"><h3 id="${id}">${title}</h3><span>${esc(detail)}</span><strong data-lcb-stage-selection>${esc(value)}</strong></header>`;
 const start=result.startFortune;
 return `<section class="lcb-time-axis" data-lcb-time-axis aria-label="${lcbText('Fortune periods, years and solar-term months','大运、流年与节令流月','大運、流年與節令流月','དུས་རབས་དང་ལོ་ཟླ།')}">
 <div class="lcb-flow-toolbar"><span>${state.selection.mode==='manual'?lcbText('Selected periods','手选运年','手選運年','བདམས་པའི་དུས།'):lcbText('Current periods','当前运年','目前運年','ད་ལྟའི་དུས།')}</span><button type="button" data-lcb-action="today">${lcbText('Today','回到当前','回到當前','ད་ལྟར་ལོག')}</button></div>
 <section class="lcb-time-stage" data-lcb-stage="period" aria-labelledby="lcb-period-heading">${heading('1',labels.periods,period.ganZhi||labels.pre,start.solar.slice(0,10)+' · '+start.years+lcbText('y ','年','年','ལོ།')+start.months+lcbText('m to start','月起运','月起運','ཟླ།'),'lcb-period-heading')}<div class="lcb-periods lcb-time-rail" data-lcb-rail="period" data-lcb-context="${periodIndex}" role="group" aria-labelledby="lcb-period-heading">${result.periods.map((p,index)=>p.years.length?`<button type="button" data-lcb-action="period" data-index="${index}" aria-pressed="${periodIndex===index}" aria-label="${esc((p.ganZhi||labels.pre)+' '+p.startYear+'–'+p.endYear)}"><small>${p.startAge}${lcbText('y','岁','歲','ལོ།')}</small><b>${p.startYear}</b>${symbols(p.ganZhi)}</button>`:'').join('')}</div></section>
 <section class="lcb-time-stage" data-lcb-stage="year" aria-labelledby="lcb-year-heading">${heading('2',labels.years,year?.ganZhi||'—',period.startYear+'–'+period.endYear,'lcb-year-heading')}<div class="lcb-years lcb-time-rail" data-lcb-rail="year" data-lcb-context="${periodIndex}:${yearIndex}" role="group" aria-labelledby="lcb-year-heading">${period.years.map((y,index)=>`<button type="button" data-lcb-action="year" data-index="${index}" data-year="${y.year}" aria-pressed="${yearIndex===index}" aria-label="${esc(y.year+' '+y.ganZhi)}"><small>${y.age}${lcbText('y','岁','歲','ལོ།')}</small><b>${y.year}</b>${symbols(y.ganZhi)}</button>`).join('')}</div></section>
 ${year?`<section class="lcb-time-stage" data-lcb-stage="month" aria-labelledby="lcb-month-heading">${heading('3',lcbText('Months','流月','流月','ཟླ།'),month?.ganZhi||'—',String(year.year),'lcb-month-heading')}<div class="lcb-months lcb-time-rail" data-lcb-rail="month" data-lcb-context="${periodIndex}:${yearIndex}:${monthIndex}" role="group" aria-labelledby="lcb-month-heading">${year.months.map((m,index)=>{const r=lcbMonthInterval(year.year,index);return `<button type="button" data-lcb-action="month" data-index="${index}" aria-pressed="${monthIndex===index}" aria-label="${esc(r.startJie+' '+m.ganZhi+' '+r.start)}"><small>${Number(r.start.slice(5,7))}/${Number(r.start.slice(8,10))}</small><b>${esc(r.startJie)}</b>${symbols(m.ganZhi)}</button>`;}).join('')}</div></section>`:''}
</section>`;
}
function lcbMonthDetails(result,state,timing){
 const period=result.periods[state.selection.period],year=period.years[state.selection.year],monthIndex=state.selection.month,month=year?.months?.[monthIndex],labels=lcbLabels();
 return `${month?`<details class="lcb-month-detail"><summary>${lcbText('Selected solar-term month','所选节令月','所選節令月','བདམས་པའི་ཟླ།')} · ${esc(month.ganZhi)}</summary><article data-lcb-selected-month><h3>${labels.selected} · ${year.year} · ${lcbMonthLabel(monthIndex)}</h3>${lcbSelectedRange(year.year,monthIndex)}<p>${labels.void} · ${esc(month.voidBranches)}</p></article>${lcbTimingPanel(result,state,timing).replace(/<button\b[^>]*data-lcb-action="today"[^>]*>[\s\S]*?<\/button>/,'')}</details>`:''}`;
}
function lcbArchivePanel(result,state){
 const b=state.normalized.birth,start=result.startFortune,aux=result.auxiliary,names={mingGong:lcbText('Ming Gong','命宫','命宮','མིང་ཀུང་།'),taiYuan:lcbText('Tai Yuan','胎元','胎元','ཐའེ་ཡོན།'),taiXi:lcbText('Tai Xi','胎息','胎息','ཐའེ་ཞི།'),shenGong:lcbText('Shen Gong','身宫','身宮','ཧྲེན་ཀུང་།')};
 const age=Math.max(1,new Date(Date.now()+8*3600000).getUTCFullYear()-Number(b.date.slice(0,4))+1),branch=result.pillars[0].branch,zodiac='鼠牛虎兔龙蛇马羊猴鸡狗猪'['子丑寅卯辰巳午未申酉戌亥'.indexOf(branch)];
 const row=(label,value)=>`<div><dt>${label}</dt><dd>${value}</dd></div>`;
 return `<section class="lcb-archive" data-lcb-archive><header><h2>${esc(b.name||lcbText('My chart','自己','自己','རང་ཉིད།'))}</h2><button type="button" data-lc-action="edit" data-kind="bazi">${typeof lbState==='function'&&lbState().archiveKind==='bazi'?lcbText('Edit current profile','修改当前资料','修改目前資料','ད་ལྟའི་གནས་ཚུལ་བཟོ་བཅོས།'):lcbText('Edit','编辑','編輯','བཟོ་བཅོས།')}</button></header><p class="lcb-archive-meta">${b.sex==='male'?lcbText('Male','男','男','ཕོ།'):lcbText('Female','女','女','མོ།')} · ${esc(zodiac)} · ${age} ${lcbLabels().age}</p><dl>
 ${row(lcbText('Solar date','阳历','陽曆','སྤྱི་ཚེས།'),esc(b.date+' '+b.time))}${row(lcbText('Lunar date','农历','農曆','ཟླ་ཚེས།'),esc(result.lunarDate))}${row(lcbText('Fortune start','起运','起運','འགོ་ཚུགས།'),`<span data-lcb-start-age>${start.years}${lcbText('y ','年','年','ལོ།')}${start.months}${lcbText('m ','月','月','ཟླ།')}${start.days}${lcbText('d ','天','天','ཉིན།')}${start.hours}${lcbText('h','小时','小時','ཆུ་ཚོད།')}</span><small>${esc(start.solar)} · ${start.forward?lcbText('Forward','顺行','順行','མདུན་སྐྱོད།'):lcbText('Reverse','逆行','逆行','ཕྱིར་སྐྱོད།')}</small>`)}
 ${Object.entries(names).map(([key,label])=>row(lcbTermButton(key,label),`${[...aux[key].ganZhi].map(c=>lcbColored(c)).join('')} <span>${esc(aux[key].naYin)}</span>`)).join('')}
 </dl>${lcbBirthBrief(result,state)}<details data-lcb-natal-details class="lcb-natal-details"><summary>${lcbText('Full natal fields and glossary','本命完整字段与术语','本命完整欄位與術語','སྐྱེས་དུས་ཞིབ་ཕྲ་དང་ཐ་སྙད།')}</summary>${lcbPillarTable(result,lcbLabels())}</details>${lcbExtraPanel(result,state)}${lcbCalculationRules(result)}</section>`;
}
function lcbCalculationRules(result){return `<details class="fl-guide-details"><summary>${lcbText('Calculation rules and version','计算规则与版本','計算規則與版本','རྩིས་ཀྱི་སྲོལ་དང་པར་གཞི།')}</summary><p>${lcbText('Year changes at Li Chun; months change at solar terms. Uses fixed UTC+8 civil time, without true solar time; nominal ages follow the calendar library.','年柱以立春为界，月柱按节令划分；使用 UTC+8 民用时间，不采用真太阳时，年龄按历法库虚岁口径。','年柱以立春為界，月柱按節令劃分；使用 UTC+8 民用時間，不採用真太陽時，年齡按曆法庫虛歲口徑。','ལོ་ཟླའི་མཚམས་དུས་ཚིགས་ལྟར་འབྱེད། UTC+8 དུས་ཚོད་བཀོལ།')}</p><p>lunar-javascript 1.7.7 · MIT · daySect=${result.rules.daySect} · yunSect=${result.rules.yunSect}</p></details>`;}
function lcbMarkerAnchorLabel(anchor){
 if(anchor.pillar==='day')return lcbText('Natal day stem','本命日干','本命日干','སྐྱེས་དུས་ཉིན་གྱི་གནམ་སྡོང་།');
 if(anchor.pillar==='month')return lcbText('Natal solar-term month branch','本命节令月支','本命節令月支','སྐྱེས་དུས་དུས་ཚིགས་ཟླའི་ས་ཡལ།');
 return anchor.field==='stem'?lcbText('Natal year stem','本命年干','本命年干','སྐྱེས་ལོའི་གནམ་སྡོང་།'):lcbText('Natal year branch','本命年支','本命年支','སྐྱེས་ལོའི་ས་ཡལ།');
}
function lcbMarkerTargetLabel(field){return field==='stem'?lcbText('Target stem','目标天干','目標天干','དམིགས་བྱའི་གནམ་སྡོང་།'):lcbText('Target branch','目标地支','目標地支','དམིགས་བྱའི་ས་ཡལ།');}
function lcbMarkerEvidence(entry,source,rule=false){
 const anchor=entry.anchor,target=rule?entry.target:entry.target.field,values=rule?entry.values:[entry.target.value];
 const readable=['zh','zh-Hant'].includes(state.lang)?entry.basis:lcbMarkerAnchorLabel(anchor)+' '+anchor.value+' → '+lcbMarkerTargetLabel(target)+' '+values.join(' / ');
 return `<p data-lcb-star-anchor="${anchor.pillar}:${anchor.field}:${anchor.value}">${esc(lcbMarkerAnchorLabel(anchor)+' '+anchor.value)}</p><p data-lcb-star-basis>${esc(readable)}</p>${source?`<p>${lcbText('Source: ','来源：','來源：','ཁུངས། ')}${rule?esc(source.title):`<a data-lcb-star-source="${source.id}" href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.title)}</a>`}</p>`:''}`;
}
function lcbAnnotationPanel(result,state,timing){
 const comparison=lcbBuildComparison(result,{...state.selection,beforeStart:timing.beforeStart}),annotations=lcbBuildAnnotations(result,comparison),columns=comparison.columns.slice(0,lcbTimelineView(state).showFlowMonth?7:6),titles=lcbColumnTitles(),sourceById=Object.fromEntries(annotations.sources.map(source=>[source.id,source]));
 const period=result.periods[state.selection.period],year=period.years[state.selection.year],context=columns.filter(c=>c.role==='flow').map(c=>titles[c.key]+' '+(c.key==='flowYear'?year.year+' ':'')+(c.available?c.ganZhi:'—')).join(' · ');
 return `<section class="lcb-annotations" data-lcb-annotations><p class="lcb-panel-caption" data-lcb-stars-context>${esc(context)}</p><div class="lcb-star-scroll" tabindex="0" role="region" aria-label="${lcbText('Stars by pillar','各柱神煞','各柱神煞','ཀ་བའི་མཚན་རྟགས།')}" style="--lcb-columns:${columns.length}"><table><colgroup><col class="lcb-board-label">${columns.map(()=>'<col>').join('')}</colgroup><thead><tr><th></th>${columns.map(c=>`<th scope="col">${titles[c.key]}</th>`).join('')}</tr></thead><tbody><tr><th scope="row">${lcbText('Self stage','自坐','自坐','རང་གི་གནས།')}</th>${columns.map(c=>`<td data-lcb-self-stage="${c.key}">${esc(annotations.columns.find(a=>a.key===c.key)?.selfStage||'—')}</td>`).join('')}</tr><tr><th scope="row">${lcbText('Stars','神煞','神煞','མཚན་རྟགས།')}</th>${columns.map(c=>`<td data-lcb-stars="${c.key}">${(annotations.columns.find(a=>a.key===c.key)?.stars||[]).map(entry=>`<details data-lcb-marker="${entry.rule}"><summary>${esc(entry.name)}</summary>${lcbMarkerEvidence(entry,sourceById[entry.source])}</details>`).join('')||'<span class="lcb-no-star">—</span>'}</td>`).join('')}</tr></tbody></table></div><details class="lcb-annotation-rules"><summary>${lcbText('Included rules and sources','收录规则与依据','收錄規則與依據','སྒྲིག་སྲོལ་དང་ཁུངས།')}</summary><p>${lcbText('Self stage uses each column’s own stem and branch. The upper table uses the natal day master. The listed traditional lookups do not predict outcomes.','自坐按各柱自己的天干与地支计算；上表星运按本命日干计算。下列神煞仅按固定传统查表列示，不作吉凶预测。','自坐按各柱自己的天干與地支計算；上表星運按本命日干計算。下列神煞僅按固定傳統查表列示，不作吉凶預測。','རང་གི་གནས་ནི་ཀ་བ་རང་གི་གནམ་སྡོང་དང་ས་ཡལ་ལྟར་རྩིས། སྔོན་བཤད་མི་བྱེད།')}</p><p>${lcbText('Included markers: ','已收录：','已收錄：','བསྡུས་པའི་མཚན་རྟགས། ')}${esc(annotations.includedStars.join('、'))}</p><p>${lcbText('A dash means no match among these twelve rules; other traditions may use other rules.','横线仅表示未命中这十二类已收录规则，不表示没有其他流派神煞。','橫線僅表示未命中這十二類已收錄規則，不表示沒有其他流派神煞。','འཕྲེད་ཐིག་གིས་བསྡུས་པའི་སྒྲིག་སྲོལ་དང་མ་མཐུན་པ་སྟོན། སྲོལ་གཞན་དང་མི་འདྲ།')}</p><p>${lcbText('Guo Yin and Jin Yu use the natal year stem. Applying the same natal lookup to selected period columns is this app’s display convention, not a native four-pillar star API in lunar-javascript. Daily almanac auspicious and inauspicious lists are not used.','国印、金舆明确以本命年干查表。固定本命锚点查所选流运列，是本APP的呈现口径，不是lunar-javascript原生四柱神煞API；不混入黄历每日吉神、凶煞列表。','國印、金輿明確以本命年干查表。固定本命錨點查所選流運欄，是本APP的呈現口徑，不是lunar-javascript原生四柱神煞API；不混入黃曆每日吉神、凶煞列表。','གོ་ཡིན་དང་ཅིན་ཡུ་ནི་སྐྱེས་ལོའི་གནམ་སྡོང་ལྟར་རྩིས། འདི་ནི་APPའི་སྟོན་སྟངས་ཡིན། lunar-javascriptཡི་ཀ་བ་བཞིའི་མཚན་རྟགས་APIམིན།')}</p><div class="lcb-rule-list" data-lcb-rule-list>${annotations.rules.map(entry=>`<details data-lcb-rule="${entry.id}"><summary>${esc(entry.name)}</summary>${lcbMarkerEvidence(entry,sourceById[entry.source],true)}</details>`).join('')}</div><div data-lcb-sources>${annotations.sources.map(source=>`<p><a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${esc(source.title)}</a></p>`).join('')}</div><small>${esc(annotations.rulesVersion)}</small></details></section>`;
}
function lcbReferenceResult(result,state){
 const timing=lcbResolveSelection(result,state),active=lcbTimelineView(state).panel,periodIndex=state.selection.period,yearIndex=state.selection.year,monthIndex=state.selection.month;
 lcbRestoreTimeline(state,result);
 const content=active==='archive'?lcbArchivePanel(result,state):active==='flow'?lcbTableTimeline(result,state,timing,periodIndex,yearIndex,monthIndex):lcbAnnotationPanel(result,state,timing);
 return `<section class="lc-result lcb-result" data-lc-result="bazi">${lcbBoard(result,state,timing)}${lcbViewTabs(active)}${lcbViews().map(([key])=>`<section class="lcb-view-panel" id="lcb-panel-${key}" role="tabpanel" aria-labelledby="lcb-tab-${key}" data-lcb-view-panel="${key}" ${key===active?'':'hidden'}>${key===active?content:''}</section>`).join('')}</section>`;
}

function lcbNotesPanel(){return `<details class="fl-guide-details lcb-notes"><summary>${lcbText('Keep reading and personal notes','阅读与个人笔记','閱讀與個人筆記','ཀློག་པ་དང་སྒེར་གྱི་ཟིན་ཐོ།')}</summary><p>${lcbText('Your earlier study notes are kept separately from calculated chart data.','原有学习笔记与排盘数据分别保留。','原有學習筆記與排盤資料分別保留。','སྔར་གྱི་སློབ་སྦྱོང་ཟིན་ཐོ་དང་རྩིས་འབྲས་ཁ་ཁར་ཉར་ཡོད།')}</p>${typeof mxForm==='function'?mxForm('classics',lcbText('My study note','我的学习笔记','我的學習筆記','ངའི་སློབ་སྦྱོང་ཟིན་ཐོ།'),lcbText('Topic','学习主题','學習主題','སློབ་གཞི།'),lcbText('What would you like to remember?','想记住什么？','想記住什麼？','གང་ཞིག་དྲན་འདོད་དམ།'))+mxHistory('classics'):''}</details>`;}

function lcbOpenTools(trigger){
 lcbToolsGlossary=null;trigger?.focus({preventScroll:true});
 const state=lcGet('bazi'),result=state.result,timing=lcbResolveSelection(result,state);
 sheet(lcbText('Chart tools','排盘工具','排盤工具','ས་ཁྲའི་ལག་ཆ།'),`<div class="lcb-tools-panel">${lcResultActions('bazi')}${lcbComparisonPanel(result,state,timing,false)}${lcbMonthDetails(result,state,timing)}${lbOptions('bazi')}${lcbNotesPanel()}</div>`);
}
// A glossary opened inside More replaces the same dialog. Retain the actual
// tools node (including disclosures and draft inputs), and give every exit a
// connected page focus target rather than a term removed by innerHTML.
let lcbToolsGlossary=null;
const lcbOpenGlossaryBeforeTools=lcbOpenGlossary;
lcbOpenGlossary=function(id,trigger){
 const tools=trigger?.closest?.('#sheet .lcb-tools-panel');
 if(!tools){lcbToolsGlossary=null;return lcbOpenGlossaryBeforeTools(id,trigger);}
 const state=lcGet('bazi'),saved={tools,trigger,state,result:state.result,selection:JSON.stringify(state.selection||{}),actor:typeof psToken==='function'?psToken():null};
 if(!lcbOpenGlossaryBeforeTools(id,trigger))return false;
 lcbToolsGlossary=saved;priorFocus=document.querySelector('.lcb-page [data-lcb-action=tools]');
 const dialog=document.getElementById('sheet');
 dialog.insertAdjacentHTML('beforeend',`<button type="button" class="btn secondary full" data-lcb-action="tools-return">${lcbText('Return to chart tools','返回排盘工具','返回排盤工具','ས་ཁྲའི་ལག་ཆར་ཕྱིར་ལོག')}</button>`);
 dialog.querySelector('.close-sheet')?.focus({preventScroll:true});return true;
};
function lcbReturnTools(){
 const saved=lcbToolsGlossary,trigger=document.querySelector('.lcb-page [data-lcb-action=tools]');
 if(!saved||!trigger||document.body.dataset.page!=='classicsWisdom'||lcGet('bazi')!==saved.state||saved.state.result!==saved.result||saved.actor&&typeof psCurrent==='function'&&!psCurrent(saved.actor)){closeSheet();return;}
 lcbToolsGlossary=null;
 if(JSON.stringify(saved.state.selection||{})!==saved.selection){lcbOpenTools(trigger);return;}
 sheet(lcbText('Chart tools','排盘工具','排盤工具','ས་ཁྲའི་ལག་ཆ།'),'');
 document.getElementById('sheet').append(saved.tools);priorFocus=trigger;
 (saved.trigger?.isConnected?saved.trigger:document.querySelector('#sheet .lcb-comparison>summary'))?.focus({preventScroll:true});
}
document.getElementById('sheet')?.addEventListener('close',event=>{
 const dialog=event.currentTarget;
 if(!dialog.open){lcbToolsGlossary=null;if(dialog.querySelector('.lcb-tools-panel'))dialog.replaceChildren();}
});
// Let the existing chart/notes handlers do their actual work. Close the tools
// only after a successful form operation; a failed save keeps the input visible.
window.addEventListener('click',event=>{
 const action=event.target.closest?.('#sheet .lcb-tools-panel [data-lc-action]');
 if(action){closeSheet();return;}
 const remove=event.target.closest?.('#sheet .lcb-tools-panel [data-map-explore-action=delete]');
 if(remove){const history=remove.closest('.mx-history'),id=remove.dataset.recordId;requestAnimationFrame(()=>{if(history?.isConnected&&!mxReadRecords().some(r=>r.id===id))history.outerHTML=mxHistory('classics');});}
},true);
window.addEventListener('submit',event=>{
 const form=event.target.closest?.('#sheet .lcb-tools-panel form');if(!form||!form.checkValidity())return;
 const result=lcGet('bazi').result,before=typeof mxReadRecords==='function'?JSON.stringify(mxReadRecords()):'';
 requestAnimationFrame(()=>{
  if(!form.isConnected||!document.querySelector('#sheet[open] .lcb-tools-panel'))return;
  const success=form.matches('[data-lb-options]')?lcGet('bazi').result!==result:form.matches('[data-map-explore-form]')&&JSON.stringify(mxReadRecords())!==before;
  if(success){closeSheet();document.querySelector('.lcb-page [data-lcb-action=tools]')?.focus({preventScroll:true});}
 });
},true);
