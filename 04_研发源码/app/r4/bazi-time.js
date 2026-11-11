// Solar-term navigation for lunar-javascript 1.7.7. All civil boundaries use fixed UTC+08:00.
// The library's ordered table includes English aliases for next-year terms; access by its list positions.
var lcbTimeCache=new Map();
function lcbTimeLibrary(){
 const library=typeof LCLunar!=='undefined'?LCLunar:(typeof Solar!=='undefined'?{Solar}:null);
 if(!library?.Solar)throw new Error('The lunar-javascript calculation library is unavailable.');
 return library;
}
function lcbTimeCivilMs(value){
 const text=String(value||'');
 if(!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(text))throw new Error('Invalid fixed-UTC+8 calendar time.');
 const ms=Date.parse(text.replace(' ','T')+'+08:00');
 if(!Number.isFinite(ms))throw new Error('Invalid fixed-UTC+8 calendar time.');
 return ms;
}
function lcbTimeMoment(value){
 const ms=Number(value);
 if(!Number.isFinite(ms)||Math.abs(ms)>8640000000000000)throw new Error('Invalid chart navigation time.');
 return ms;
}
function lcbTimeTerms(year){
 if(!Number.isInteger(year)||year<1800||year>2399)throw new Error('Solar-term navigation year is outside 1800–2399.');
 if(lcbTimeCache.has(year))return lcbTimeCache.get(year);
 const lunar=lcbTimeLibrary().Solar.fromYmdHms(year,7,1,12,0,0).getLunar();
 const keys=lunar.getJieQiList(),table=lunar.getJieQiTable();
 const names=['立春','惊蛰','清明','立夏','芒种','小暑','立秋','白露','寒露','立冬','大雪','小寒','立春'];
 const terms=names.map((name,index)=>{
  const solar=table[keys[4+index*2]];
  if(!solar)throw new Error('The calendar library did not supply a complete solar-term year.');
  const civil=solar.toYmdHms();return {name,civil,ms:lcbTimeCivilMs(civil)};
 });
 if(terms[0].civil.slice(0,4)!==String(year)||terms[12].civil.slice(0,4)!==String(year+1)||terms.some((t,i)=>i&&t.ms<=terms[i-1].ms))throw new Error('Unexpected solar-term table ordering.');
 if(lcbTimeCache.size>=8)lcbTimeCache.delete(lcbTimeCache.keys().next().value);
 lcbTimeCache.set(year,terms);return terms;
}
function lcbMonthInterval(year,index){
 if(!Number.isInteger(index)||index<0||index>11)throw new Error('Solar-term month index must be from 0 to 11.');
 const terms=lcbTimeTerms(year),a=terms[index],b=terms[index+1];
 return {year,index,monthIndex:index,start:a.civil,end:b.civil,startJie:a.name,endJie:b.name,branch:'寅卯辰巳午未申酉戌亥子丑'[index],startUtc:new Date(a.ms).toISOString(),endUtc:new Date(b.ms).toISOString(),startMs:a.ms,endMs:b.ms};
}
function lcbCalendarAt(ms=Date.now()){
 ms=lcbTimeMoment(ms);
 const d=new Date(ms+8*3600000),civilYear=d.getUTCFullYear();
 let year=civilYear;
 if(ms<lcbTimeTerms(year)[0].ms)year--;
 const terms=lcbTimeTerms(year),monthIndex=terms.findIndex((t,i)=>i<12&&ms>=t.ms&&ms<terms[i+1].ms);
 if(monthIndex<0)throw new Error('No solar-term month covers this time.');
 const solar=lcbTimeLibrary().Solar.fromYmdHms(d.getUTCFullYear(),d.getUTCMonth()+1,d.getUTCDate(),d.getUTCHours(),d.getUTCMinutes(),d.getUTCSeconds());
 const lunar=solar.getLunar();
 return {year,monthIndex,yearGanZhi:lunar.getYearInGanZhiExact(),monthGanZhi:lunar.getMonthInGanZhiExact(),civilTime:solar.toYmdHms(),utc:new Date(ms).toISOString(),interval:lcbMonthInterval(year,monthIndex)};
}
function lcbCurrentSelection(result,now=Date.now()){
 now=lcbTimeMoment(now);
 const calendar=lcbCalendarAt(now),rows=[];
 for(let p=0;p<(result?.periods?.length||0);p++)for(let y=0;y<(result.periods[p].years?.length||0);y++){
  const value=result.periods[p].years[y];if(Number.isInteger(value.year)&&value.months?.length)rows.push({period:p,year:y,value});
 }
 const birthMs=lcbTimeCivilMs(result?.calculationCivilTime),startMs=lcbTimeCivilMs(result?.startFortune?.solar);
 if(!rows.length)throw new Error('The chart contains no selectable fortune years.');
 let selected=rows.find(r=>r.value.year===calendar.year);
 const yearUnavailable=!selected;
 if(!selected)selected=rows.reduce((a,b)=>Math.abs(b.value.year-calendar.year)<Math.abs(a.value.year-calendar.year)?b:a);
 const minYear=Math.min(...rows.map(r=>r.value.year)),maxYear=Math.max(...rows.map(r=>r.value.year));
 const outside=now<birthMs?'before-birth':calendar.year>maxYear?'after-range':'';
 return {period:selected.period,year:selected.year,month:Math.min(calendar.monthIndex,selected.value.months.length-1),outside,beforeStart:now>=birthMs&&now<startMs,yearUnavailable,calendarYear:calendar.year,calendarMonthIndex:calendar.monthIndex,selectedYear:selected.value.year,rangeStartYear:minYear,rangeEndYear:maxYear,calendar};
}
function lcbResolveSelection(result,state,now=Date.now()){
 const current=lcbCurrentSelection(result,now),old=state?.selection||{};
 const p=old.period,y=old.year,m=old.month;
 const manual=old.mode==='manual'&&Number.isInteger(p)&&p>=0&&Number.isInteger(y)&&y>=0&&Number.isInteger(m)&&m>=0&&m<12&&!!result.periods?.[p]?.years?.[y]?.months?.[m];
 const selection=manual?{period:p,year:y,month:m,mode:'manual'}:{period:current.period,year:current.year,month:current.month,mode:'current'};
 if(state)state.selection=selection;
 return {...current,...selection,selectedYear:result.periods[selection.period].years[selection.year].year};
}
