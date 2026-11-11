// Deterministic Ba Zi adapter and interactive view. Calendar source: lunar-javascript 1.7.7 (MIT).
// Dates passed to this adapter have already been converted to fixed UTC+08:00 by the shared birth form.
function lcBaziCalculate(normalized,options={}){
 const library=typeof LCLunar!=='undefined'?LCLunar:(typeof Solar!=='undefined'?{Solar}:null);
 if(!library?.Solar)throw new Error('The lunar-javascript calculation library is unavailable.');
 const c=normalized?.china,b=normalized?.birth;
 if(!c||!b||!['male','female'].includes(b.sex))throw new Error('Complete the birth time and calculation gender first.');
 const daySect=Number(options.daySect??2),yunSect=Number(options.yunSect??2);
 if(![1,2].includes(daySect)||![1,2].includes(yunSect))throw new Error('Unknown Ba Zi calculation rule.');
 const solar=library.Solar.fromYmdHms(c.year,c.month,c.day,c.hour,c.minute,c.second||0),lunar=solar.getLunar(),eight=lunar.getEightChar();
 eight.setSect(daySect);
 const columns=[['year','Year'],['month','Month'],['day','Day'],['time','Time']];
 const pillars=columns.map(([key,method])=>({
  key,ganZhi:eight['get'+method](),stem:eight['get'+method+'Gan'](),branch:eight['get'+method+'Zhi'](),
  hiddenStems:[...eight['get'+method+'HideGan']()],fiveElements:eight['get'+method+'WuXing'](),
  stemTenGod:eight['get'+method+'ShiShenGan'](),branchTenGods:[...eight['get'+method+'ShiShenZhi']()],
  naYin:eight['get'+method+'NaYin'](),growthStage:eight['get'+method+'DiShi'](),xun:eight['get'+method+'Xun'](),voidBranches:eight['get'+method+'XunKong']()
 }));
 const auxiliary={
  taiYuan:{ganZhi:eight.getTaiYuan(),naYin:eight.getTaiYuanNaYin()},
  taiXi:{ganZhi:eight.getTaiXi(),naYin:eight.getTaiXiNaYin()},
  mingGong:{ganZhi:eight.getMingGong(),naYin:eight.getMingGongNaYin()},
  shenGong:{ganZhi:eight.getShenGong(),naYin:eight.getShenGongNaYin()}
 };
 const yun=eight.getYun(b.sex==='male'?1:0,yunSect);
 const periods=yun.getDaYun(10).map(period=>{
  const ganZhi=period.getGanZhi();
  return {index:period.getIndex(),ganZhi,startYear:period.getStartYear(),endYear:period.getEndYear(),startAge:period.getStartAge(),endAge:period.getEndAge(),
   xun:ganZhi?period.getXun():'',voidBranches:ganZhi?period.getXunKong():'',
   smallFortunes:period.getXiaoYun().map(small=>({year:small.getYear(),age:small.getAge(),ganZhi:small.getGanZhi(),xun:small.getXun(),voidBranches:small.getXunKong()})),
   years:period.getLiuNian().map(year=>({year:year.getYear(),age:year.getAge(),ganZhi:year.getGanZhi(),xun:year.getXun(),voidBranches:year.getXunKong(),
    months:year.getLiuYue().map(month=>({index:month.getIndex(),ordinal:month.getIndex()+1,monthName:month.getMonthInChinese(),ganZhi:month.getGanZhi(),xun:month.getXun(),voidBranches:month.getXunKong()}))
   }))
  };
 });
 return {kind:'bazi',schemaVersion:1,engine:{name:'lunar-javascript',version:'1.7.7',license:'MIT'},
  rules:{calculationTimeZone:'UTC+08:00',trueSolarTime:false,yearBoundary:'LiChun',monthBoundary:'JieQi',daySect,dayBoundary:daySect===1?'23:00':'00:00',yunSect,ageMode:'nominal',monthSequence:'Yin through Chou; solar-term month sequence',auxBasis:'EightChar auxiliary methods; TaiXi follows selected daySect',smallFortuneBasis:'DaYun.getXiaoYun; natal time pillar, Yun direction and nominal calendar-year ages'},
  calculationCivilTime:solar.toYmdHms(),lunarDate:lunar.toString(),pillars,auxiliary,
  startFortune:{forward:yun.isForward(),years:yun.getStartYear(),months:yun.getStartMonth(),days:yun.getStartDay(),hours:yun.getStartHour(),solar:yun.getStartSolar().toYmdHms()},periods};
}
function lcbText(en,zh,hant,bo){return lcText(en,zh,hant,bo);}
function lcbLabels(){return {
 title:lcbText('Ba Zi chart','八字排盘','八字排盤','བ་ཙི་སྐར་རྩིས།'),
 intro:lcbText('Four pillars, fortune periods and year/month selection','四柱八字、起运、大运与流年流月','四柱八字、起運、大運與流年流月','ཀ་བ་བཞི་དང་དུས་རབས། ལོ་དང་ཟླ་བའི་འདེམས་ཀ།'),
 year:lcbText('Year pillar','年柱','年柱','ལོའི་ཀ་བ།'),month:lcbText('Month pillar','月柱','月柱','ཟླ་བའི་ཀ་བ།'),day:lcbText('Day pillar','日柱','日柱','ཉིན་གྱི་ཀ་བ།'),time:lcbText('Hour pillar','时柱','時柱','ཆུ་ཚོད་ཀྱི་ཀ་བ།'),
 ganZhi:lcbText('Stem–branch','干支','干支','གནམ་སྡོང་དང་ས་ཡལ།'),hidden:lcbText('Hidden stems','藏干','藏干','སྦས་པའི་གནམ་སྡོང་།'),elements:lcbText('Five elements','五行','五行','འབྱུང་བ་ལྔ།'),
 stemGod:lcbText('Stem relationship','天干十神','天干十神','གནམ་སྡོང་གི་འབྲེལ་བ།'),branchGod:lcbText('Hidden-stem relationships','地支十神','地支十神','ས་ཡལ་གྱི་འབྲེལ་བ།'),
 naYin:lcbText('Na Yin','纳音','納音','ན་ཡིན།'),growth:lcbText('Twelve growth stages','十二长生','十二長生','འཚར་སྐྱེའི་རིམ་པ་བཅུ་གཉིས།'),void:lcbText('Void branches','旬空／空亡','旬空／空亡','སྟོང་པའི་ས་ཡལ།'),
 pre:lcbText('Before first fortune period','起运前','起運前','དུས་རབས་ཐོག་མའི་སྔོན།'),
 periods:lcbText('Major fortune periods','大运','大運','དུས་རབས་ཆེན་པོ།'),years:lcbText('Select a year','流年','流年','ལོ་འདེམས་པ།'),months:lcbText('Solar-term months','流月（节令月序）','流月（節令月序）','དུས་ཚིགས་ཀྱི་ཟླ་བའི་རིམ་པ།'),
 age:lcbText('nominal age','虚岁','虛歲','སྲོལ་རྒྱུན་གྱི་ལོ།'),selected:lcbText('Selected month','所选流月','所選流月','བདམས་པའི་ཟླ་བ།')
 };}
function lcbRuleFields(state){
 const d=Number(state.options?.daySect||2),y=Number(state.options?.yunSect||2);
 return `<label><span>${lcbText('Day-pillar boundary','日柱换日规则','日柱換日規則','ཉིན་གྱི་ཀ་བ་བརྗེ་བའི་སྲོལ།')}</span><select name="daySect"><option value="2" ${d===2?'selected':''}>${lcbText('00:00 · late Zi remains on this day (sect 2)','00:00 换日 · 晚子时归当日（流派2）','00:00 換日 · 晚子時歸當日（流派2）','00:00 ལ་ཉིན་བརྗེ། སྲོལ་2།')}</option><option value="1" ${d===1?'selected':''}>${lcbText('23:00 · late Zi uses the next day (sect 1)','23:00 换日 · 晚子时归次日（流派1）','23:00 換日 · 晚子時歸次日（流派1）','23:00 ལ་ཉིན་བརྗེ། སྲོལ་1།')}</option></select></label>
 <label><span>${lcbText('Fortune-start calculation','起运算法','起運算法','དུས་རབས་འགོ་ཚུགས་རྩིས་ཐབས།')}</span><select name="yunSect"><option value="2" ${y===2?'selected':''}>${lcbText('Minute-based rule (sect 2)','按分钟折算（流派2）','按分鐘折算（流派2）','སྐར་མ་ལྟར་རྩིས་པ། སྲོལ་2།')}</option><option value="1" ${y===1?'selected':''}>${lcbText('Days and time-branches (sect 1)','按天与时辰折算（流派1）','按天與時辰折算（流派1）','ཉིན་དང་ཆུ་ཚོད་ལྟར་རྩིས་པ། སྲོལ་1།')}</option></select></label>`;
}
function lcbPillarTable(result,labels){
 const expanded=!!lcGet('bazi').showPillarDetails;
 const rows=[['ganZhi',labels.ganZhi,p=>p.ganZhi],['stemTenGod',labels.stemGod,p=>p.stemTenGod],['fiveElements',labels.elements,p=>p.fiveElements],['hiddenStems',labels.hidden,p=>p.hiddenStems.join(' · ')],['branchTenGods',labels.branchGod,p=>p.branchTenGods.join(' · ')],['naYin',labels.naYin,p=>p.naYin],['growthStage',labels.growth,p=>p.growthStage],['xun',lcbText('Ten-day cycle','所属旬','所屬旬','ཉིན་བཅུའི་འཁོར།'),p=>p.xun],['voidBranches',labels.void,p=>p.voidBranches]];
 const renderRow=([field,label,read])=>`<tr><th scope="row">${lcbTermButton(field,label)}</th>${result.pillars.map(p=>`<td data-pillar="${p.key}" data-field="${field}" class="${p.key==='day'?'is-day-master':''}">${field==='stemTenGod'?lcbTenGodButtons(read(p)):field==='branchTenGods'?lcbTenGodButtons(p.branchTenGods):lcbTermButton(field,read(p))}</td>`).join('')}</tr>`;
 return `<section class="lcb-natal" data-lcb-pillar-axis><div class="section-title lcb-axis-heading"><div><span class="lcb-section-kicker">${lcbText('01 · NATAL AXIS','01 · 四柱主轴','01 · 四柱主軸','01 · ཀ་བ་བཞི།')}</span><h2>${lcbText('Natal pillars','本命四柱','本命四柱','སྐྱེས་དུས་ཀ་བ་བཞི།')}</h2></div>${lcbTermButton('dayMaster',lcbText('Day master','日主','日主','ཉིན་གྱི་གནམ་སྡོང་།')+' · '+result.pillars.find(p=>p.key==='day').stem)}</div><div class="lcb-table-wrap"><table class="lcb-pillars"><colgroup><col class="lcb-label-col">${result.pillars.map(()=>'<col>').join('')}</colgroup><thead><tr><th scope="col">${labels.ganZhi}</th>${result.pillars.map(p=>`<th scope="col" class="${p.key==='day'?'is-day-master':''}">${labels[p.key]}</th>`).join('')}</tr></thead><tbody>${rows.slice(0,3).map(renderRow).join('')}</tbody><tbody id="lcb-pillar-detail-fields" class="lcb-more-fields" ${expanded?'':'hidden'}>${rows.slice(3).map(renderRow).join('')}</tbody></table></div><button type="button" class="lcb-detail-toggle" data-lcb-action="details" aria-controls="lcb-pillar-detail-fields" aria-expanded="${expanded}">${expanded?lcbText('Collapse detailed fields','收起四柱详细资料','收起四柱詳細資料','ཀ་བ་བཞིའི་ཞིབ་ཕྲ་བསྡུ།'):lcbText('Show hidden stems, Na Yin and more','展开藏干、纳音等详细资料','展開藏干、納音等詳細資料','སྦས་སྡོང་དང་ཞིབ་ཕྲ་སྟོན།')}</button></section>`;
}
function lcbBirthBrief(result,state){const b=state.normalized.birth;return `<div class="lcb-birth-brief"><b>${esc(b.name||lcbText('My natal chart','我的本命','我的本命','ངའི་སྐྱེས་དུས་ས་ཁྲ།'))}</b><span>${esc(b.date+' '+b.time)}</span><small>${esc(result.lunarDate)}</small></div><details class="lcb-birth-detail" data-lcb-birth-detail><summary>${lcbText('Birth details and time conversion','出生资料与时间换算','出生資料與時間換算','སྐྱེས་དུས་དང་དུས་ཚོད་བསྒྱུར་བ།')}</summary>${lcNormalizedSummary('bazi')}</details>`;}
function lcbMonthLabel(index){const branch=['寅','卯','辰','巳','午','未','申','酉','戌','亥','子','丑'][index];return branch+' · '+lcbText('term month','节令月','節令月','དུས་ཚིགས་ཟླ།');}
function lcbSelectedRange(year,index){const range=lcbMonthInterval(year,index);return `<p class="lcb-month-range" data-lcb-month-range><b>${esc(range.startJie)} → ${esc(range.endJie)}</b><span>${esc(range.start)} → ${esc(range.end)} · UTC+08:00</span></p>`;}
function lcbTimingPanel(result,state,timing){
 const current=lcbCalendarAt(),p=result.periods[state.selection.period],y=p.years[state.selection.year],manual=state.selection.mode==='manual';
 const displayedRange=manual?lcbMonthInterval(y.year,state.selection.month):current.interval;
 let status=displayedRange.startJie+' → '+displayedRange.endJie+' · UTC+08:00';
 if(timing.outside==='before-birth')status=lcbText('The entered birth time is in the future. Showing the earliest listed year.','出生时刻尚未到达，当前展示运表最早年份。','出生時刻尚未到達，目前顯示運表最早年份。','བཀོད་པའི་སྐྱེས་དུས་མ་སླེབས། ལོ་ཐོའི་ལོ་སྔ་ཤོས་སྟོན།');
 else if(timing.outside==='after-range')status=lcbText('Today is beyond this chart’s listed years. Showing the nearest listed year.','当前年月超出这份运表范围，展示最近的已列年份。','目前年月超出這份運表範圍，顯示最近的已列年份。','ད་ལྟའི་ལོ་འདིའི་ལོ་ཐོའི་ཁྱབ་ལས་བརྒལ། ཉེ་ཤོས་ཀྱི་ལོ་སྟོན།');
 else if(timing.yearUnavailable)status=lcbText('The current solar-term year is not listed in this chart.','当前节令年未列入这份运表。','目前節令年未列入這份運表。','ད་ལྟའི་དུས་ཚིགས་ལོ་འདི་ལོ་ཐོ་འདིར་མེད།');
 else if(timing.beforeStart)status=lcbText('The first fortune period has not started yet. The table below follows calendar-year ranges.','当前尚未到首次起运时刻，下表按库的年份段查看。','目前尚未到首次起運時刻，下表按庫的年份區間查看。','དུས་རབས་ཐོག་མ་མ་འགོ་ཚུགས། འོག་གི་ལོ་ཐོ་ལོའི་ཁྱབ་ལྟར་སྟོན།');
 return `<article class="lcb-time-panel" data-lcb-time-panel><div><span>${manual?lcbText('Viewing a selected period','正在回看所选年月','正在回看所選年月','བདམས་པའི་ལོ་ཟླ་བསྐྱར་ལྟ།'):lcbText('View for today','查看当前年月','查看當前年月','ད་ལྟའི་ལོ་ཟླ་ལ་ལྟ།')}</span><button class="btn secondary" data-lcb-action="today">${lcbText('Back to today','回到当前','回到當前','ད་ལྟར་ལོག')}</button></div><strong>${y?.year??'—'} · ${esc(y?.ganZhi||'')} · ${lcbMonthLabel(state.selection.month)}</strong><p>${status}</p></article>`;
}
function lcbFlowOverview(result,state,comparison){const p=result.periods[state.selection.period],y=p.years[state.selection.year];return `<div class="lcb-flow-summary" data-lcb-overview>${comparison.columns.slice(4).map(column=>`<article data-lcb-overview-column="${column.key}"><small>${{period:lcbText('Major period','大运','大運','དུས་རབས་ཆེན་པོ།'),flowYear:lcbText('Year','流年','流年','ལོ།'),flowMonth:lcbText('Month','流月','流月','ཟླ།')}[column.key]}</small><strong>${esc(column.available?column.ganZhi:'—')}</strong><span>${column.key==='period'?p.startYear+'–'+p.endYear:column.key==='flowYear'?y.year:lcbMonthLabel(state.selection.month)}</span></article>`).join('')}</div>`;}
function lcbComparisonPanel(result,state,timing,expanded=false){
 const labels=lcbLabels(),comparison=lcbBuildComparison(result,{...state.selection,beforeStart:timing.beforeStart}),titles={year:labels.year,month:labels.month,day:labels.day,time:labels.time,period:labels.periods,flowYear:labels.years,flowMonth:labels.months};
 const rows=[['ganZhi',labels.ganZhi,p=>p.ganZhi],['hiddenStems',labels.hidden,p=>p.hiddenStems.join(' · ')],['fiveElements',labels.elements,p=>p.fiveElements],['stemTenGod',labels.stemGod,p=>p.stemTenGod],['branchTenGods',labels.branchGod,p=>p.branchTenGods.join(' · ')],['naYin',labels.naYin,p=>p.naYin],['growthStage',labels.growth,p=>p.growthStage],['xun',lcbText('Ten-day cycle','所属旬','所屬旬','ཉིན་བཅུའི་འཁོར།'),p=>p.xun],['voidBranches',labels.void,p=>p.voidBranches]];
 return `<section class="lcb-analysis-overview">${lcbFlowOverview(result,state,comparison)}<details class="lcb-comparison" data-lcb-comparison ${expanded?'open':''}><summary>${lcbText('Expand all seven comparison columns','展开本命与运年月完整对照','展開本命與運年月完整對照','ཀ་བ་བདུན་གྱི་བསྡུར་བ་ཚང་མ་སྟོན།')}</summary><header><h3>${lcbText('Natal chart and selected periods','本命与运年月对照','本命與運年月對照','སྐྱེས་དུས་དང་བདམས་པའི་དུས་རབས་བསྡུར།')}</h3><span>${lcbText('Day master','日主','日主','ཉིན་གྱི་གནམ་སྡོང་།')} · ${esc(comparison.dayMaster)}</span></header><p>${lcbText('The four natal pillars stay fixed. The final three columns follow your selections in the Periods view, using the same natal day master.','四柱本命保持不变，右侧三列对应流运页所选的大运、流年、流月，均以本命日干为日主对照。','四柱本命保持不變，右側三欄對應流運頁所選的大運、流年、流月，均以本命日干為日主對照。','སྐྱེས་དུས་ཀ་བ་བཞི་མི་འགྱུར། མཐའ་མའི་ཀ་བ་གསུམ་དུས་རབས་བདམས་པ་ལྟར་འགྱུར།')}</p><div class="lcb-comparison-scroll" role="region" tabindex="0" aria-label="${lcbText('Scroll to compare all seven columns','横向滑动查看七列对照','橫向滑動查看七欄對照','གཡས་གཡོན་དྲུད་ནས་ཀ་བ་བདུན་ལ་བལྟ།')}"><table><thead><tr><th scope="col">${labels.ganZhi}</th>${comparison.columns.map(p=>`<th scope="col" class="${p.key==='day'?'is-day-master':p.key==='period'?'is-period-start':''}">${titles[p.key]}</th>`).join('')}</tr></thead><tbody>${rows.map(([field,label,value])=>`<tr><th scope="row">${lcbTermButton(field,label)}</th>${comparison.columns.map(p=>`<td data-lcb-column="${p.key}" data-field="${field}" class="${p.key==='day'?'is-day-master':p.key==='period'?'is-period-start':''}">${p.available?(field==='stemTenGod'?lcbTenGodButtons(value(p)):field==='branchTenGods'?lcbTenGodButtons(p.branchTenGods):lcbTermButton(field,value(p))):'—'}</td>`).join('')}</tr>`).join('')}</tbody></table></div><small>${lcbText('Swipe horizontally to compare all columns. Each void-branch entry belongs to that pillar’s own ten-day cycle.','可横向滑动查看完整对照；各列旬空指该柱自身所属旬，不自动判为命中本命空亡。','可橫向滑動查看完整對照；各欄旬空指該柱自身所屬旬，不自動判為命中本命空亡。','ཀ་བ་ཚང་མ་བསྡུར་བར་གཡས་གཡོན་དྲུད། སྟོང་ཡལ་སོ་སོའི་ཉིན་བཅུ་ལྟར་ཡིན།')}</small></details></section>`;
}
function lcbExtraPanel(result,state){
 if(!result.auxiliary)return '';
 const labels=lcbLabels(),period=result.periods[state.selection.period],year=period.years[state.selection.year],small=period.smallFortunes||[],names={taiYuan:lcbText('Tai Yuan','胎元','胎元','ཐའེ་ཡོན།'),taiXi:lcbText('Tai Xi','胎息','胎息','ཐའེ་ཞི།'),mingGong:lcbText('Ba Zi Ming Gong','八字命宫','八字命宮','བ་ཙིའི་མིང་ཀུང་།'),shenGong:lcbText('Ba Zi Shen Gong','八字身宫','八字身宮','བ་ཙིའི་ཧྲེན་ཀུང་།')};
 return `<details class="lcb-extra" data-lcb-extra><summary>${lcbText('Auxiliary chart details and minor periods','八字辅助资料与小运','八字輔助資料與小運','བ་ཙིའི་ཁ་སྣོན་གནས་ཚུལ་དང་དུས་རབས་ཆུང་བ།')}</summary><p>${lcbText('These auxiliary stem–branch and Na Yin values follow the selected traditional rules. Tai Yuan and Tai Xi are symbolic calculations rather than actual conception or health information. Ba Zi Ming Gong and Shen Gong belong to this system, separate from Zi Wei palaces.','以下辅助干支及纳音按所选传统规则计算。胎元、胎息是传统推算标记，不对应真实受孕日期或健康资料；这里的命宫、身宫属于八字体系，与紫微斗数宫位分别查看。','以下輔助干支及納音按所選傳統規則計算。胎元、胎息是傳統推算標記，不對應真實受孕日期或健康資料；這裡的命宮、身宮屬於八字體系，與紫微斗數宮位分別查看。','ཁ་སྣོན་གནམ་སྡོང་ས་ཡལ་དང་ན་ཡིན་ནི་བདམས་པའི་སྲོལ་ལྟར་རྩིས། ཐའེ་ཡོན་དང་ཐའེ་ཞི་ནི་མངལ་ཆགས་དུས་དངོས་དང་བདེ་ཐང་གི་གནས་ཚུལ་མིན། བ་ཙིའི་ཁང་མིག་དང་ཙི་ཝེ་ཁང་མིག་སོ་སོ་ཡིན།')}</p><div class="lcb-aux-grid">${Object.entries(names).map(([key,title])=>{const value=result.auxiliary[key];return `<article data-lcb-aux="${key}"><h4>${lcbTermButton(key,title)}</h4><strong data-field="ganZhi">${esc(value.ganZhi)}</strong><span data-field="naYin">${esc(value.naYin)}</span></article>`;}).join('')}</div><h3>${lcbTermButton('smallFortune',lcbText('Minor periods','小运','小運','དུས་རབས་ཆུང་བ།'))} · ${period.startYear}–${period.endYear}</h3><p>${lcbText('Minor periods follow the natal hour pillar and the same forward/reverse convention. They are listed separately from flowing years. The highlighted card matches the selected year; ages use the library’s nominal-age convention.','小运按本命时柱及同一顺逆规则逐年推算，与流年分开列示。高亮项对应当前所选流年，年龄按库的虚岁口径。','小運按本命時柱及同一順逆規則逐年推算，與流年分開列示。高亮項對應目前所選流年，年齡按庫的虛歲口徑。','དུས་རབས་ཆུང་བ་སྐྱེས་དུས་ཀྱི་ཆུ་ཚོད་ཀ་བ་དང་སྔ་ཕྱི་སྲོལ་ལྟར་ལོ་རེར་རྩིས། ལོའི་ཀ་བ་དང་ཁ་ཁར་སྟོན། མཚན་རྟགས་ནི་བདམས་པའི་ལོ་ཡིན།')}</p>${result.periods[0]?.smallFortunes?.length===0?`<p class="small" data-lcb-small-empty data-period="0">${lcbText('The first fortune period starts in the birth year, so the pre-start segment has no calendar-year minor-period entries.','出生当年起运，起运前阶段没有按年份列出的小运条目。','出生當年起運，起運前階段沒有按年份列出的小運條目。','སྐྱེས་ལོར་དུས་རབས་འགོ་ཚུགས་པས་སྔོན་གྱི་ཁག་ལ་ལོའི་ཟིན་ཐོ་མེད།')}</p>`:''}<div class="lcb-small-fortunes">${small.map(value=>`<article data-lcb-small-year="${value.year}" aria-current="${value.year===year.year}"><span>${value.year} · <i data-field="age">${value.age}</i> ${labels.age}</span><strong data-field="ganZhi">${esc(value.ganZhi)}</strong><small>${lcbText('Cycle','旬','旬','ཉིན་བཅུ།')} <span data-field="xun">${esc(value.xun)}</span><br>${labels.void} <span data-field="voidBranches">${esc(value.voidBranches)}</span></small></article>`).join('')}</div></details>`;
}
// Viewport and focus are transient UI state, separate from saved chart data.
const lcbTimelineViews=new WeakMap();
function lcbTimelineView(state){let view=lcbTimelineViews.get(state);if(!view||view.result!==state.result){view={result:state.result,rails:Object.create(null),focus:null,panel:'flow',showFlowMonth:false,boardExpanded:true};lcbTimelineViews.set(state,view);}if(!['archive','flow','stars'].includes(view.panel))view.panel='flow';return view;}
function lcbRailPosition(rail){return {left:rail.scrollLeft,context:rail.dataset.lcbContext,width:rail.clientWidth,itemWidth:rail.querySelector('[aria-pressed=true]')?.offsetWidth};}
function lcbRememberTimeline(state,button){
 const view=lcbTimelineView(state);
 view.disclosures=view.disclosures||{};
 for(const selector of ['[data-lcb-natal-details]','[data-lcb-birth-detail]','[data-lcb-extra]','[data-lcb-comparison]','.lcb-month-detail']){const detail=document.querySelector('.lcb-page '+selector);if(detail)view.disclosures[selector]=detail.open;}
 const board=document.querySelector('.lcb-board-scroll');if(board)view.boardScroll=board.scrollLeft;
 for(const rail of document.querySelectorAll('.lcb-page [data-lcb-rail]'))view.rails[rail.dataset.lcbRail]=lcbRailPosition(rail);
 if(button)view.focus={action:button.dataset.lcbAction,index:button.dataset.index,view:button.dataset.view};
}
function lcbRestoreTimeline(state,result,restoreDisclosures=true){
 const sequence=renderSequence;
 const current=()=>sequence===renderSequence&&document.body.dataset.page==='classicsWisdom'&&lcGet('bazi')===state&&state.result===result;
 // Restore native details before the next input task, never in a later paint
 // callback that could overwrite a summary the user has just opened.
 if(restoreDisclosures)queueMicrotask(()=>{
  if(!current())return;
  const view=lcbTimelineView(state);
  for(const [selector,open] of Object.entries(view.disclosures||{})){const detail=document.querySelector('.lcb-page '+selector);if(detail)detail.open=open;}
 });
 requestAnimationFrame(()=>{
  if(!current())return;
  const view=lcbTimelineView(state);
  const board=document.querySelector('.lcb-board-scroll');if(board&&view.boardScroll!==undefined)board.scrollLeft=view.boardScroll;
  for(const rail of document.querySelectorAll('.lcb-page [data-lcb-rail]')){
   const saved=view.rails[rail.dataset.lcbRail],selected=rail.querySelector('[aria-pressed=true]');
   if(saved?.context===rail.dataset.lcbContext&&saved.width===rail.clientWidth&&saved.itemWidth===selected?.offsetWidth)rail.scrollLeft=saved.left;
   else if(selected){const a=selected.getBoundingClientRect(),b=rail.getBoundingClientRect();rail.scrollLeft+=a.left-b.left-rail.clientWidth/2+a.width/2;}
   view.rails[rail.dataset.lcbRail]=lcbRailPosition(rail);
  }
  if(view.focus){
   const target=view.focus;view.focus=null;
   const selector='.lcb-page [data-lcb-action="'+target.action+'"]'+(target.index===undefined?'':'[data-index="'+target.index+'"]')+(target.view===undefined?'':'[data-view="'+target.view+'"]');
   const button=document.querySelector(selector);button?.focus({preventScroll:true});
   if(button&&target.action==='view'){
    const app=document.getElementById('app'),tabs=button.closest('[role=tablist]'),box=tabs?.getBoundingClientRect(),header=document.querySelector('.lcb-page>.px-top')?.getBoundingClientRect(),bounds=app?.getBoundingClientRect();
    if(box&&bounds){const top=Math.max(bounds.top,header?.bottom||bounds.top)+8;if(box.top<top||box.bottom>bounds.bottom)app.scrollTop+=box.top-top;}
   }
  }
 });
}
function lcbTimeline(result,state,timing,periodIndex,yearIndex,monthIndex){return lcbTableTimeline(result,state,timing,periodIndex,yearIndex,monthIndex);}
function lcbViews(){return [
 ['archive',lcbText('Profile','档案','檔案','ཟིན་ཐོ།')],
 ['flow',lcbText('Periods','流运','流運','དུས་རབས།')],
 ['stars',lcbText('Stars','神煞','神煞','མཚན་རྟགས།')]
 ];}
function lcbViewTabs(active){return `<div class="lcb-tabbar"><nav class="lcb-view-tabs" data-lcb-view-tabs role="tablist" aria-label="${lcbText('Ba Zi views','八字查看方式','八字查看方式','བ་ཙི་ལྟ་སྟངས།')}">${lcbViews().map(([key,label])=>`<button type="button" id="lcb-tab-${key}" role="tab" data-lcb-action="view" data-view="${key}" aria-selected="${key===active}" aria-controls="lcb-panel-${key}" tabindex="${key===active?0:-1}">${label}</button>`).join('')}</nav><button type="button" class="lcb-tools-trigger" data-lcb-action="tools" aria-haspopup="dialog" aria-controls="sheet" aria-label="${lcbText('Chart tools','更多排盘工具','更多排盤工具','ས་ཁྲའི་ལག་ཆ།')}">${icon('more','ew-more-icon')}<small>${lcbText('More','更多','更多','དེ་ལས་མང་བ།')}</small></button></div>`;}
function lcbResult(result,state){return lcbReferenceResult(result,state);}
function lcBaziScreen(){
 const state=lcGet('bazi'),labels=lcbLabels();
 return `<section class="page fl-detail lc-page lcb-page" data-lcb-layout="reference">${pxTop(labels.title,labels.intro,'lifeResult')}${!state.result||state.editing?lcBirthForm('bazi',{gender:true,extra:lcbRuleFields(state)}):''}${state.result?lcbResult(state.result,state):`<article class="card lc-empty"><h2>${lcbText('Begin with your birth details','从出生资料开始','從出生資料開始','སྐྱེས་དུས་ཀྱི་གནས་ཚུལ་ནས་འགོ་འཛུགས།')}</h2><p>${lcbText('Generate a chart to see the four pillars and select real calculated periods, years and months.','排盘后显示四柱，并可切换实际计算的大运、流年与流月。','排盤後顯示四柱，並可切換實際計算的大運、流年與流月。','སྐར་རྩིས་བཟོས་རྗེས་ཀ་བ་བཞི་དང་དུས་རབས། ལོ་དང་ཟླ་བ་འདེམས་ཆོག')}</p></article>`}${!state.result?lcbNotesPanel():''}</section>`;
}
screens.classicsWisdom=lcBaziScreen;
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-lcb-action]');if(!button)return;
 event.preventDefault();event.stopImmediatePropagation();
 const state=lcGet('bazi'),result=state.result;if(!result)return;
 lcbRememberTimeline(state,button);
 if(button.dataset.lcbAction==='view'){const panel=button.dataset.view;if(lcbViews().some(([key])=>key===panel)){lcbTimelineView(state).panel=panel;render(false);}return;}
 if(button.dataset.lcbAction==='tools'){lcbOpenTools(button);return;}
  if(button.dataset.lcbAction==='tools-return'){lcbReturnTools();return;}
 if(button.dataset.lcbAction==='board-details'){lcbTimelineView(state).boardExpanded=!lcbTimelineView(state).boardExpanded;render(false);return;}
 if(button.dataset.lcbAction==='flow-month'){lcbTimelineView(state).showFlowMonth=!lcbTimelineView(state).showFlowMonth;render(false);return;}
 if(button.dataset.lcbAction==='details'){state.showPillarDetails=!state.showPillarDetails;render(false);return;}
 if(button.dataset.lcbAction==='today'){state.selection={mode:'current'};render(false);return;}
 const index=Number(button.dataset.index);if(!Number.isInteger(index)||index<0)return;
 const selection=state.selection||(state.selection={});
 if(button.dataset.lcbAction==='period'&&index<result.periods.length&&result.periods[index].years.length){const oldYear=result.periods[selection.period]?.years[selection.year]?.year;selection.period=index;const same=result.periods[index].years.findIndex(y=>y.year===oldYear);selection.year=same<0?0:same;selection.mode='manual';}
 else if(button.dataset.lcbAction==='year'&&index<(result.periods[selection.period??1]?.years.length||0)){selection.year=index;selection.mode='manual';}
 else if(button.dataset.lcbAction==='month'&&index<12){selection.month=index;selection.mode='manual';}
 else return;
 render(false);
},true);

// Scrolling changes the user's offset, never the layout stamp. Browser clamping
// during resize must not make a changed layout appear already restored.
document.addEventListener('scroll',event=>{const rail=event.target;if(!rail?.matches?.('.lcb-page [data-lcb-rail]'))return;const state=lcGet('bazi');if(!state.result)return;const saved=lcbTimelineView(state).rails[rail.dataset.lcbRail],current=lcbRailPosition(rail);if(saved?.context===current.context&&saved.width===current.width&&saved.itemWidth===current.itemWidth)saved.left=current.left;},{capture:true,passive:true});
window.addEventListener('resize',()=>{const state=lcGet('bazi');if(state.result&&document.querySelector('.lcb-page [data-lcb-rail]'))lcbRestoreTimeline(state,state.result,false);},{passive:true});
document.addEventListener('keydown',event=>{
 const tab=event.target.closest?.('.lcb-view-tabs [role=tab]');if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)||event.altKey||event.ctrlKey||event.metaKey)return;
 const tabs=[...tab.parentElement.querySelectorAll('[role=tab]')],index=tabs.indexOf(tab),next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
 event.preventDefault();event.stopImmediatePropagation();if(next!==index)tabs[next].click();
},true);
document.addEventListener('keydown',event=>{
 const button=event.target.closest?.('.lcb-time-rail [data-lcb-action]');if(!button||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)||event.altKey||event.ctrlKey||event.metaKey)return;
 const buttons=[...button.parentElement.querySelectorAll('button[data-lcb-action]')],index=buttons.indexOf(button);if(index<0)return;
 const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:Math.max(0,Math.min(buttons.length-1,index+(event.key==='ArrowRight'?1:-1)));
 event.preventDefault();event.stopImmediatePropagation();if(next!==index)buttons[next].click();
},true);
