// Shared deterministic Ba Zi computation. No DOM, account store or provider access.
// Calendar implementation remains the bundled lunar-javascript 1.7.7 (MIT).
(function(root,factory){
 'use strict';
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.BaziSampleEngine=api;
})(typeof globalThis==='object'?globalThis:this,function(){
 'use strict';
 const LIMITS=Object.freeze({maxImportBytes:2097152,maxCases:100,maxCaseCanonicalBytes:262144,maxDepth:32,maxExpectedFieldsPerCase:2000,maxExpectedValueBytes:8192,maxCaseWorkerOutputBytes:4194304,listPageSize:50});
 const TAGS=Object.freeze(['ordinary','male','female','solar-term','midnight','year-boundary','leap-month','overseas','dst-gap','dst-overlap','unknown-time','legacy-utc','selection','annotations','not-applicable','rule-variation']);
 const ENGINE=Object.freeze({name:'lunar-javascript',version:'1.7.7'});
 const RULE_VERSION='bazi-fixed-utc8-1',ADAPTER_VERSION='bazi-sample-engine-1';
 function createEngine({lunar,sha256}={}){
  const LCLunar=lunar,lcText=en=>en;
  const hash=async text=>{if(typeof sha256!=='function')throw fault('adapter_unavailable','');const value=await sha256(text);if(!/^[a-f0-9]{64}$/.test(value))throw fault('adapter_unavailable','');return value;};
function lcFailure(code,en,zh,hant,bo){const error=new Error(lcText(en,zh,hant,bo));error.code=code;error.translations=[en,zh,hant,bo];return error;}
function lcParts(ms,zone){const parts=new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(ms));const out={};for(const p of parts)if(['year','month','day','hour','minute','second'].includes(p.type))out[p.type]=Number(p.value);if(out.hour===24)out.hour=0;return out;}
function lcChinaParts(iso){const p=lcParts(Date.parse(iso),'Etc/GMT-8'),pad=n=>String(n).padStart(2,'0');return {...p,date:p.year+'-'+pad(p.month)+'-'+pad(p.day),time:pad(p.hour)+':'+pad(p.minute)};}
function lcNormalizeInput(raw,options={}){
 const date=String(raw.date||'').trim(),time=String(raw.time||'').trim(),timezone=String(raw.timezone||'').trim(),m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(date),h=/^(\d{2}):(\d{2})$/.exec(time);
 if(!m||!h)throw lcFailure('BIRTH_REQUIRED','Enter an exact local birth date and time.','请填写准确的当地出生日期和时间。','請填寫準確的當地出生日期和時間。','ཡུལ་དེའི་སྐྱེས་ཉིན་དང་དུས་ཚོད་ཡང་དག་འབྲི་རོགས།');
 const y=Number(m[1]),mo=Number(m[2]),d=Number(m[3]),hour=Number(h[1]),minute=Number(h[2]),wall=Date.UTC(y,mo-1,d,hour,minute,0),check=new Date(wall);
 if(y<1900||y>2099||mo<1||mo>12||hour>23||minute>59||check.getUTCFullYear()!==y||check.getUTCMonth()!==mo-1||check.getUTCDate()!==d)throw lcFailure('DATE_RANGE','Use a valid Gregorian date from 1900 to 2099 and a 24-hour time.','请输入1900至2099年的有效公历日期及24小时制时间。','請輸入1900至2099年的有效公曆日期及24小時制時間。','༡༩༠༠ ནས་༢༠༩༩ བར་གྱི་སྤྱི་ལོའི་ཚེས་དང་ཆུ་ཚོད་༢༤ ཡི་དུས་ཚོད་ཡང་དག་འབྲི།');
 try{lcParts(wall,timezone);}catch{throw lcFailure('TIMEZONE','Enter a valid IANA time zone, for example Asia/Shanghai.','请填写有效的IANA时区，例如 Asia/Shanghai。','請填寫有效的IANA時區，例如 Asia/Shanghai。','དཔེར་ན་Asia/Shanghai ལྟ་བུའི་IANA དུས་ཁུལ་ཡང་དག་འབྲི།');}
 const offsets=new Set();for(const hours of [-48,-36,-24,-12,0,12,24,36,48]){const probe=wall+hours*3600000,p=lcParts(probe,timezone);offsets.add(Date.UTC(p.year,p.month-1,p.day,p.hour,p.minute,p.second)-probe);}
 const candidates=[];for(const offset of offsets){const utc=wall-offset,p=lcParts(utc,timezone);if(p.year===y&&p.month===mo&&p.day===d&&p.hour===hour&&p.minute===minute&&p.second===0)candidates.push(utc);}candidates.sort((a,b)=>a-b);
 if(!options.archivedUtc&&!candidates.length)throw lcFailure('NONEXISTENT_TIME','This local time did not exist because the clock changed. Check the recorded birth time.','该当地时间处于时钟调整的缺失时段，请核对出生记录。','該當地時間處於時鐘調整的缺失時段，請核對出生記錄。','ཆུ་ཚོད་བསྒྱུར་བས་ཡུལ་དེར་དུས་ཚོད་འདི་མ་བྱུང་། སྐྱེས་དུས་ཟིན་ཐོ་ལ་བསྐྱར་བལྟ་བྱོས།');
 const ambiguity=['earlier','later'].includes(raw.ambiguity)?raw.ambiguity:'reject';
 if(!options.archivedUtc&&candidates.length>1&&ambiguity==='reject')throw lcFailure('AMBIGUOUS_TIME','This local time occurred twice. Confirm the earlier or later occurrence.','该当地时间曾出现两次，请确认采用较早或较晚的一次。','該當地時間曾出現兩次，請確認採用較早或較晚的一次。','ཡུལ་དེའི་དུས་ཚོད་འདི་ཐེངས་གཉིས་བྱུང་། སྔ་མའམ་ཕྱི་མ་འདེམས་རོགས།');
 let instant=options.archivedUtc?Date.parse(options.archivedUtc):(ambiguity==='later'?candidates[candidates.length-1]:candidates[0]);if(!Number.isFinite(instant))throw new Error('Invalid archived UTC instant');
 const sex=raw.sex||'male';if(!['male','female'].includes(sex))throw lcFailure('SEX_PARAMETER','Choose the traditional algorithm parameter.','请选择传统算法参数。','請選擇傳統算法參數。','སྲོལ་རྒྱུན་རྩིས་ཀྱི་ཚད་གྲངས་འདེམས་རོགས།');
 const latitude=raw.latitude===''||raw.latitude===undefined?null:Number(raw.latitude),longitude=raw.longitude===''||raw.longitude===undefined?null:Number(raw.longitude);
 if(options.location&&(!Number.isFinite(latitude)||!Number.isFinite(longitude)||Math.abs(latitude)>=90||Math.abs(longitude)>180))throw lcFailure('COORDINATES','Confirm a birth latitude between -90 and 90 and longitude between -180 and 180.','请确认出生地纬度在-90至90之间，经度在-180至180之间。','請確認出生地緯度在-90至90之間，經度在-180至180之間。','སྐྱེས་ཡུལ་གྱི་འཕྲེད་ཐིག་-90 ནས་90 དང་གཞུང་ཐིག་-180 ནས་180 བར་ངེས་གཏན་བྱོས།');
 const utc=new Date(instant).toISOString(),birth={name:String(raw.name||'').trim().slice(0,60),date,time,timezone,ambiguity,sex,latitude,longitude,place:String(raw.place||'').trim().slice(0,80),timeConfirmed:true};
 return {birth,utc,china:lcChinaParts(utc),offsetMinutes:(wall-instant)/60000,candidateCount:candidates.length,timeMethod:'IANA Intl; local civil time → UTC; no true-solar-time adjustment'};
}
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
// Display-only pillar comparisons. All relationships use the already-calculated natal day stem.
// Calendar tables: lunar-javascript 1.7.7 (MIT). This module does not evaluate strength or predictions.
function lcbComparisonUtil(){
 const util=typeof LCLunar!=='undefined'?LCLunar.LunarUtil:(typeof LunarUtil!=='undefined'?LunarUtil:null);
 if(!util?.JIA_ZI||!util?.SHI_SHEN)throw new Error('The lunar-javascript comparison tables are unavailable.');
 return util;
}
function lcbDescribePillar(ganZhi,dayMaster,context={}){
 const u=lcbComparisonUtil();
 if(typeof dayMaster!=='string'||u.GAN.indexOf(dayMaster)<1)throw new RangeError('Invalid natal day stem.');
 if(typeof ganZhi!=='string')throw new TypeError('A pillar must be a stem-branch string.');
 const base={key:context.key||'',role:context.role||'flow',available:ganZhi!=='',ganZhi,
  relationBasis:{dayMaster,tenGod:'natal-day-stem',growthStage:'natal-day-stem-to-target-branch'}};
 if(!ganZhi)return {...base,stem:'',branch:'',hiddenStems:[],fiveElements:'',stemTenGod:'',branchTenGods:[],naYin:'',growthStage:'',xun:'',voidBranches:'',unavailableReason:context.unavailableReason||'no-pillar'};
 if(u.JIA_ZI.indexOf(ganZhi)<0)throw new RangeError('Invalid sexagenary pillar: '+ganZhi);
 const stem=ganZhi.charAt(0),branch=ganZhi.charAt(1),stemIndex=u.GAN.indexOf(dayMaster)-1,branchIndex=u.ZHI.indexOf(branch)-1;
 const stageIndex=((u.CHANG_SHENG_OFFSET[dayMaster]+(stemIndex%2===0?branchIndex:-branchIndex))%12+12)%12;
 const hiddenStems=[...u.ZHI_HIDE_GAN[branch]];
 return {...base,stem,branch,hiddenStems,fiveElements:u.WU_XING_GAN[stem]+u.WU_XING_ZHI[branch],
  stemTenGod:context.role==='natal'&&context.key==='day'?'日主':u.SHI_SHEN[dayMaster+stem],
  branchTenGods:hiddenStems.map(hidden=>u.SHI_SHEN[dayMaster+hidden]),naYin:u.NAYIN[ganZhi],
  growthStage:u.CHANG_SHENG[stageIndex],xun:u.getXun(ganZhi),voidBranches:u.getXunKong(ganZhi)};
}
function lcbComparisonPick(items,index,label){
 if(!Array.isArray(items))throw new TypeError('Missing '+label+' list.');
 const n=index===undefined?0:index;
 if(!Number.isInteger(n)||n<0||n>=items.length&&!(items.length===0&&n===0))throw new RangeError('Invalid '+label+' selection.');
 return items[n]||null;
}
function lcbBuildComparison(result,selection={}){
 if(!result||!Array.isArray(result.pillars))throw new TypeError('A calculated natal chart is required.');
 if(!selection||typeof selection!=='object'||Array.isArray(selection))throw new TypeError('Invalid comparison selection.');
 const dayPillar=result.pillars.find(p=>p?.key==='day'),dayMaster=dayPillar?.stem;
 const u=lcbComparisonUtil();
 if(typeof dayMaster!=='string'||u.GAN.indexOf(dayMaster)<1)throw new RangeError('The calculated chart has no valid natal day stem.');
 const fields=['ganZhi','stem','branch','fiveElements','stemTenGod','naYin','growthStage','xun','voidBranches'];
 const columns=['year','month','day','time'].map(key=>{
  const matches=result.pillars.filter(p=>p?.key===key),p=matches[0];
  if(matches.length!==1||fields.some(field=>typeof p[field]!=='string')||u.JIA_ZI.indexOf(p.ganZhi)<0||p.stem!==p.ganZhi.charAt(0)||p.branch!==p.ganZhi.charAt(1)||!Array.isArray(p.hiddenStems)||!Array.isArray(p.branchTenGods)||p.hiddenStems.length!==p.branchTenGods.length)throw new TypeError('Invalid calculated natal pillar: '+key);
  const copy={key,role:'natal',available:true};
  fields.forEach(field=>{copy[field]=p[field];});
  copy.hiddenStems=[...p.hiddenStems];copy.branchTenGods=[...p.branchTenGods];
  copy.relationBasis={dayMaster,tenGod:'natal-day-stem',growthStage:'natal-day-stem-to-target-branch'};
  return copy;
 });
 const period=lcbComparisonPick(result.periods,selection.period,'period');
 const year=period?lcbComparisonPick(period.years,selection.year,'year'):null;
 const month=year?lcbComparisonPick(year.months,selection.month,'month'):null;
 const notStarted=selection.mode==='current'&&selection.beforeStart===true;
 columns.push(lcbDescribePillar(notStarted?'':period?.ganZhi||'',dayMaster,{key:'period',role:'flow',unavailableReason:notStarted?'before-first-start':'before-first-period'}));
 columns.push(lcbDescribePillar(year?.ganZhi||'',dayMaster,{key:'flowYear',role:'flow',unavailableReason:'no-selected-year'}));
 columns.push(lcbDescribePillar(month?.ganZhi||'',dayMaster,{key:'flowMonth',role:'flow',unavailableReason:'no-selected-month'}));
 return {dayMaster,columns};
}
// Deterministic display annotations for already-calculated Ba Zi pillars.
// Does not calculate a birth time, replace the calendar adapter or predict outcomes.
// Fixed scope: twelve sourced lookup rules. Natal anchors never follow the selected flow columns.
function lcbAnnotationUtil(){
 const u=typeof LCLunar!=='undefined'?LCLunar.LunarUtil:(typeof LunarUtil!=='undefined'?LunarUtil:null);
 if(!u?.JIA_ZI||!u?.CHANG_SHENG_OFFSET||!u?.CHANG_SHENG||!u?.LU)throw new Error('The fixed lunar-javascript annotation tables are unavailable.');
 return u;
}
function lcbAnnotationPillar(p,u,allowEmpty=false){
 if(!p||typeof p.ganZhi!=='string')throw new TypeError('A calculated stem-branch pillar is required.');
 if(p.ganZhi===''){
  if(!allowEmpty||p.available===true)throw new TypeError('A natal/available pillar cannot be empty.');
  return {key:p.key,available:false,stem:'',branch:'',ganZhi:''};
 }
 if(p.available===false||u.JIA_ZI.indexOf(p.ganZhi)<0)throw new RangeError('Invalid calculated stem-branch pillar.');
 const stem=p.ganZhi.charAt(0),branch=p.ganZhi.charAt(1);
 if(p.stem!==undefined&&p.stem!==stem||p.branch!==undefined&&p.branch!==branch)throw new TypeError('Pillar characters disagree with its stem-branch value.');
 return {key:p.key,available:true,stem,branch,ganZhi:p.ganZhi};
}
function lcbAnnotationSelfStage(stem,branch,u){
 const stemIndex=u.GAN.indexOf(stem)-1,branchIndex=u.ZHI.indexOf(branch)-1;
 if(stemIndex<0||branchIndex<0)throw new RangeError('A valid stem and branch are needed for its own growth stage.');
 const index=((u.CHANG_SHENG_OFFSET[stem]+(stemIndex%2===0?branchIndex:-branchIndex))%12+12)%12;
 return u.CHANG_SHENG[index];
}
function lcbBuildAnnotations(result,comparison){
 const u=lcbAnnotationUtil(),natalKeys=['year','month','day','time'],allowed=[...natalKeys,'period','flowYear','flowMonth'];
 if(!result||!Array.isArray(result.pillars)||result.pillars.length!==4)throw new TypeError('Four calculated natal pillars are required.');
 const natal=natalKeys.map(key=>{
  const matches=result.pillars.filter(p=>p?.key===key);
  if(matches.length!==1)throw new TypeError('Each natal pillar must appear exactly once.');
  return lcbAnnotationPillar(matches[0],u);
 });
 if(!comparison||!Array.isArray(comparison.columns)||![6,7].includes(comparison.columns.length))throw new TypeError('Six or seven comparison columns are required.');
 const used=new Set(),targets=comparison.columns.map(p=>{
  if(!allowed.includes(p?.key)||used.has(p.key))throw new TypeError('Unknown or duplicate comparison column.');
  used.add(p.key);const target=lcbAnnotationPillar(p,u,!natalKeys.includes(p.key));
  const original=natal.find(n=>n.key===p.key);
  if(original&&original.ganZhi!==target.ganZhi)throw new TypeError('Comparison must retain the calculated natal pillars.');
  return target;
 });
 if(natalKeys.some(key=>!used.has(key))||!used.has('period')||!used.has('flowYear'))throw new TypeError('Comparison is missing a required natal or selected period/year column.');
 const day=natal.find(p=>p.key==='day'),year=natal.find(p=>p.key==='year'),month=natal.find(p=>p.key==='month');
 if(comparison.dayMaster!==undefined&&comparison.dayMaster!==day.stem)throw new TypeError('Comparison day master differs from the natal day stem.');
 const groups=[
  {branches:['申','子','辰'],horse:'寅',general:'子',canopy:'辰',robbery:'巳',loss:'亥',virtue:'壬'},
  {branches:['寅','午','戌'],horse:'申',general:'午',canopy:'戌',robbery:'亥',loss:'巳',virtue:'丙'},
  {branches:['巳','酉','丑'],horse:'亥',general:'酉',canopy:'丑',robbery:'寅',loss:'申',virtue:'庚'},
  {branches:['亥','卯','未'],horse:'巳',general:'卯',canopy:'未',robbery:'申',loss:'寅',virtue:'甲'}
 ];
 const yearGroup=groups.find(g=>g.branches.includes(year.branch)),monthGroup=groups.find(g=>g.branches.includes(month.branch));
 // The six added rules use the separately reviewed tables in the audit record.
 // In particular, Yin-stem Yang Ren is NOT the library's reverse Di Shi table.
 const tables={
  tianYi:{甲:['丑','未'],乙:['子','申'],丙:['亥','酉'],丁:['亥','酉'],戊:['丑','未'],己:['子','申'],庚:['丑','未'],辛:['寅','午'],壬:['卯','巳'],癸:['卯','巳']},
  wenChang:{甲:['巳'],乙:['午'],丙:['申'],丁:['酉'],戊:['申'],己:['酉'],庚:['亥'],辛:['子'],壬:['寅'],癸:['卯']},
  yangRen:{甲:['卯'],乙:['辰'],丙:['午'],丁:['未'],戊:['午'],己:['未'],庚:['酉'],辛:['戌'],壬:['子'],癸:['丑']},
  guoYin:{甲:['戌'],乙:['亥'],丙:['丑'],丁:['寅'],戊:['丑'],己:['寅'],庚:['辰'],辛:['巳'],壬:['未'],癸:['申']},
  jinYu:{甲:['辰'],乙:['巳'],丙:['未'],丁:['申'],戊:['未'],己:['申'],庚:['戌'],辛:['亥'],壬:['丑'],癸:['寅']}
 };
 const anchor=(pillar,field,value)=>({pillar,field,value});
 const dayStem=anchor('day','stem',day.stem),yearBranch=anchor('year','branch',year.branch),monthBranch=anchor('month','branch',month.branch),yearStem=anchor('year','stem',year.stem);
 const rule=(name,id,from,target,values,source,method)=>({name,id,anchor:from,target,values:[...values],source,method});
 const markerRules=[
  rule('禄神','lu-day-stem',dayStem,'branch',[u.LU[day.stem]],'lunar-1.7.7','日干查禄支'),
  rule('驿马','horse-year-branch',yearBranch,'branch',[yearGroup.horse],'sanming-03',yearGroup.branches.join('')+'组查驿马'),
  rule('将星','general-year-branch',yearBranch,'branch',[yearGroup.general],'sanming-02',yearGroup.branches.join('')+'组三合中位'),
  rule('华盖','canopy-year-branch',yearBranch,'branch',[yearGroup.canopy],'sanming-02',yearGroup.branches.join('')+'组三合库支'),
  rule('劫煞','robbery-year-branch',yearBranch,'branch',[yearGroup.robbery],'sanming-03-markers',yearGroup.branches.join('')+'组查劫煞'),
  rule('亡神','loss-year-branch',yearBranch,'branch',[yearGroup.loss],'sanming-03-markers',yearGroup.branches.join('')+'组查亡神'),
  rule('天乙贵人','tian-yi-day-stem',dayStem,'branch',tables.tianYi[day.stem],'mingli-tanyuan','日主表，两支兼列，不另分昼夜贵'),
  rule('文昌','wen-chang-day-stem',dayStem,'branch',tables.wenChang[day.stem],'mingli-tanyuan','命理探源日主表，不混同三命通会同名另一表'),
  rule('羊刃','yang-ren-day-stem',dayStem,'branch',tables.yangRen[day.stem],'mingli-tanyuan','命理探源所列渊海子平十干表，不以阴干帝旺替代'),
  rule('月德','yue-de-month-branch',monthBranch,'stem',[monthGroup.virtue],'mingli-tanyuan',monthGroup.branches.join('')+'节令月组查目标天干'),
  rule('国印','guo-yin-year-stem',yearStem,'branch',tables.guoYin[year.stem],'gujin-guoyin','本命年干星命起例，不采用日干法'),
  rule('金舆','jin-yu-year-stem',yearStem,'branch',tables.jinYu[year.stem],'sanming-03','本命年干禄支顺进二辰，不采用日干或驿马前二辰法')
 ];
 const anchorName=from=>from.pillar==='day'?'本命日干':from.pillar==='month'?'本命节令月支':from.field==='stem'?'本命年干':'本命年支';
 const basis=entry=>anchorName(entry.anchor)+entry.anchor.value+'；'+entry.method+'；目标'+(entry.target==='stem'?'干':'支')+'：'+entry.values.join('、');
 const columns=targets.map(p=>({
  key:p.key,available:p.available,
  selfStage:p.available?lcbAnnotationSelfStage(p.stem,p.branch,u):'',
  stars:p.available?markerRules.filter(entry=>entry.values.includes(p[entry.target])).map(entry=>({
   name:entry.name,basis:basis(entry)+'；当前目标'+p[entry.target],rule:entry.id,source:entry.source,
   anchor:{...entry.anchor},target:{field:entry.target,value:p[entry.target]}
  })):[],
  selfStageBasis:'each-column-stem-to-its-own-branch'
 }));
 return {
  columns,rulesVersion:'eastern-bazi-annotations-2',includedStars:markerRules.map(entry=>entry.name),
  rules:markerRules.map(entry=>({name:entry.name,id:entry.id,anchor:{...entry.anchor},target:entry.target,values:[...entry.values],source:entry.source,basis:basis(entry)})),
  anchorPolicy:{lu:'natal-day-stem',horse:'natal-year-branch',general:'natal-year-branch',canopy:'natal-year-branch',robbery:'natal-year-branch',loss:'natal-year-branch',tianYi:'natal-day-stem',wenChang:'natal-day-stem',yangRen:'natal-day-stem',yueDe:'natal-solar-term-month-branch',guoYin:'natal-year-stem',jinYu:'natal-year-stem',targets:'all-available-comparison-columns'},
  limits:['只收录所列十二类规则；空数组表示未命中已收录规则，不代表没有其他流派神煞。','国印、金舆固定使用本命年干；天乙、文昌、羊刃和禄神使用本命日干；月德使用实际节令月支。','原书查表条件用于所选流运列是本APP的呈现口径，不是lunar-javascript原生四柱神煞API。','自坐使用该柱自身天干对本支的长生，不同于以本命日干计算的星运。','不使用黄历每日吉神宜趋、凶煞宜忌充当四柱神煞，不输出命运或吉凶预测。'],
  sources:[
   {id:'lunar-1.7.7',title:'lunar-javascript 1.7.7 · LunarUtil / EightChar',url:'https://github.com/6tail/lunar-javascript/blob/v1.7.7/lunar.js',scope:'固定MIT引擎的LU及CHANG_SHENG_OFFSET/CHANG_SHENG；不提供完整四柱神煞API。'},
   {id:'sanming-02',title:'三命通会（四库全书本）卷二',url:'https://zh.wikisource.org/w/index.php?oldid=761691',scope:'将星三合中位、华盖三合库支；本产品沿用年支锚点。'},
   {id:'sanming-03',title:'三命通会（四库全书本）卷三',url:'https://zh.wikisource.org/w/index.php?oldid=657369',scope:'十干禄、驿马、金舆。金舆采用本命年干禄前二辰法，不混马前二辰法。'},
   {id:'sanming-03-markers',title:'三命通会·卷三·论劫煞亡神',url:'https://zh.wikisource.org/wiki/三命通會/卷三#论劫煞亡神',scope:'劫煞、亡神四组三合目标表，沿用本命年支法。'},
   {id:'mingli-tanyuan',title:'命理探源·卷三·神煞',url:'https://book.taiyi.me/命/命理探源',scope:'天乙、文昌、羊刃的日主查表及月德的节令月支表。文昌按同段作者按语核定，不混三命通会另一同名表。'},
   {id:'gujin-guoyin',title:'古今图书集成·艺术典·禄勋阳刃唐符国印',url:'https://www.shidianguji.com/zh/book/GJTS17/chapter/1lpfcu0bj3602',scope:'国印逐干表；本APP采用本命年干星命起例，不暗换现代日干口径。'}
  ]
 };
}

// SAMPLE_SCHEMA_AND_REPORT_API
 function fault(code,path='',status=400){return Object.assign(new Error(code),{code,path,status});}
 const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k),plain=o=>!!o&&typeof o==='object'&&!Array.isArray(o)&&[Object.prototype,null].includes(Object.getPrototypeOf(o));
 const dangerous=k=>['__proto__','prototype','constructor'].includes(k),bytes=s=>new TextEncoder().encode(s).length;
 const pointerEscape=s=>String(s).replace(/~/g,'~0').replace(/\//g,'~1');
 function stringOK(s){for(let i=0;i<s.length;i++){const c=s.charCodeAt(i);if(c>=0xd800&&c<=0xdbff){const d=s.charCodeAt(++i);if(!(d>=0xdc00&&d<=0xdfff))return false;}else if(c>=0xdc00&&c<=0xdfff)return false;}return true;}
 function canonical(value){
  const seen=new Set();
  function encode(v,depth){
   if(depth>LIMITS.maxDepth)throw fault('json_depth_exceeded');
   if(v===null||typeof v==='boolean')return JSON.stringify(v);
   if(typeof v==='string'){if(!stringOK(v))throw fault('invalid_unicode');return JSON.stringify(v);}
   if(typeof v==='number'){if(!Number.isFinite(v)||Number.isInteger(v)&&!Number.isSafeInteger(v))throw fault('invalid_number');return JSON.stringify(v);}
   if(!Array.isArray(v)&&!plain(v)||seen.has(v))throw fault('invalid_json_value');
   seen.add(v);let result;
   if(Array.isArray(v)){for(let i=0;i<v.length;i++){const d=Object.getOwnPropertyDescriptor(v,String(i));if(!d||!own(d,'value'))throw fault('invalid_json_value');}if(Object.keys(v).some(k=>!/^(0|[1-9]\d*)$/.test(k)||Number(k)>=v.length))throw fault('invalid_json_value');result='['+v.map(x=>encode(x,depth+1)).join(',')+']';}
   else{const keys=Object.keys(v).sort();if(keys.some(dangerous))throw fault('forbidden_key');result='{'+keys.map(k=>{const d=Object.getOwnPropertyDescriptor(v,k);if(!d||!own(d,'value'))throw fault('invalid_json_value');return JSON.stringify(k)+':'+encode(d.value,depth+1);}).join(',')+'}';}
   seen.delete(v);return result;
  }
  return encode(value,0);
 }
 const clone=v=>JSON.parse(canonical(v));
 function strictParse(text,maxBytes=LIMITS.maxImportBytes){
  if(typeof text!=='string'||!stringOK(text))throw fault('invalid_utf8');
  if(bytes(text)>maxBytes)throw fault('import_too_large','',413);
  let at=0;const ws=()=>{while(/[\x20\t\r\n]/.test(text.charAt(at))&&at<text.length)at++;};
  function str(){const start=at++;while(at<text.length){const ch=text.charAt(at++);if(ch==='"'){let s;try{s=JSON.parse(text.slice(start,at));}catch{throw fault('invalid_json');}if(!stringOK(s))throw fault('invalid_unicode');return s;}if(ch==='\\'){if(at>=text.length)break;at++;}else if(ch.charCodeAt(0)<32)throw fault('invalid_json');}throw fault('invalid_json');}
  function value(depth,path){
   if(depth>LIMITS.maxDepth)throw fault('json_depth_exceeded',path);ws();const ch=text.charAt(at);
   if(ch==='"')return str();
   if(ch==='{'){at++;ws();const out=Object.create(null),keys=new Set();if(text.charAt(at)==='}'){at++;return out;}while(true){ws();if(text.charAt(at)!=='"')throw fault('invalid_json',path);const key=str(),p=path+'/'+pointerEscape(key);if(dangerous(key))throw fault('forbidden_key',p);if(keys.has(key))throw fault('duplicate_key',p);keys.add(key);ws();if(text.charAt(at++)!==':')throw fault('invalid_json',p);out[key]=value(depth+1,p);ws();const end=text.charAt(at++);if(end==='}')return out;if(end!==',')throw fault('invalid_json',path);}}
   if(ch==='['){at++;ws();const out=[];if(text.charAt(at)===']'){at++;return out;}while(true){out.push(value(depth+1,path+'/'+out.length));ws();const end=text.charAt(at++);if(end===']')return out;if(end!==',')throw fault('invalid_json',path);}}
   for(const [word,result] of [['true',true],['false',false],['null',null]])if(text.slice(at,at+word.length)===word){at+=word.length;return result;}
   const m=/-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(at));if(!m||m.index!==0)throw fault('invalid_json',path);at+=m[0].length;const number=Number(m[0]);if(!Number.isFinite(number)||Number.isInteger(number)&&!Number.isSafeInteger(number))throw fault('invalid_number',path);return number;
  }
  const result=value(0,'');ws();if(at!==text.length)throw fault('invalid_json');return result;
 }
 function keys(o,required,optional,path){if(!plain(o))throw fault('invalid_object',path);for(const k of Object.keys(o))if(!required.includes(k)&&!optional.includes(k))throw fault('unknown_field',path+'/'+pointerEscape(k));for(const k of required)if(!own(o,k))throw fault('missing_field',path+'/'+k);}
 function text(v,min,max,path){if(typeof v!=='string'||!stringOK(v)||v.length<min||v.length>max||/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(v))throw fault('invalid_string',path);return v;}
 function nullableText(v,max,path){if(v!==null)text(v,1,max,path);}
 function id(v,path){text(v,1,100,path);if(!/^[A-Za-z0-9:_-]{1,100}$/.test(v))throw fault('invalid_id',path);}
 function sha(v,path){if(v!==null&&(typeof v!=='string'||!/^[a-f0-9]{64}$/.test(v)))throw fault('invalid_sha256',path);}
 function member(v,values,path){if(!values.includes(v))throw fault('invalid_enum',path);}
 function gregorian(v,path){if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(v))throw fault('invalid_date',path);const [y,m,d]=v.split('-').map(Number),date=new Date(Date.UTC(y,m-1,d));if(y<1900||y>2099||date.getUTCFullYear()!==y||date.getUTCMonth()+1!==m||date.getUTCDate()!==d)throw fault('invalid_date',path);}
 function instant(v,path){text(v,20,35,path);const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?(Z|[+-]\d{2}:\d{2})$/.exec(v);if(!m||!Number.isFinite(Date.parse(v)))throw fault('invalid_instant',path);const y=Number(m[1]),mo=Number(m[2]),d=Number(m[3]),h=Number(m[4]),mi=Number(m[5]),s=Number(m[6]),test=new Date(Date.UTC(y,mo-1,d));if(test.getUTCFullYear()!==y||test.getUTCMonth()+1!==mo||test.getUTCDate()!==d||h>23||mi>59||s>59||m[8]!=='Z'&&(Number(m[8].slice(1,3))>23||Number(m[8].slice(4))>59))throw fault('invalid_instant',path);return Date.parse(v);}
 function options(v,path){keys(v,['daySect','yunSect','trueSolarTime'],[],path);if(!Number.isInteger(v.daySect)||![1,2].includes(v.daySect)||!Number.isInteger(v.yunSect)||![1,2].includes(v.yunSect)||v.trueSolarTime!==false)throw fault('invalid_options',path);}
 const PILLAR_FIELDS='(?:key|ganZhi|stem|branch|hiddenStems(?:/\\d+)?|fiveElements|stemTenGod|branchTenGods(?:/\\d+)?|naYin|growthStage|xun|voidBranches)';
 const FLOW_FIELDS='(?:year|age|ganZhi|xun|voidBranches)',MONTH_FIELDS='(?:index|ordinal|monthName|ganZhi|xun|voidBranches)';
 const NA_REASONS=Object.freeze(['not_applicable','birth_time_unknown','before-first-start','before-first-period','no-selected-year','no-selected-month','no-pillar','unavailable_column']);
 function pathAllowed(path){
  if(typeof path!=='string'||path.length>500||!path.startsWith('/')||/~(?![01])/.test(path)||path.split('/').some(x=>dangerous(x.replace(/~1/g,'/').replace(/~0/g,'~'))))return false;
  const patterns=[
   '^/originalInput/(?:date|time|sex|name)$',
   '^/normalizedInput/(?:utc|offsetMinutes|candidateCount|timeMethod|birth/(?:name|date|time|timezone|ambiguity|sex|latitude|longitude|place|timeConfirmed)|china/(?:year|month|day|hour|minute|second|date|time))$',
   '^/rawOutput/(?:kind|schemaVersion|lunarDate|calculationCivilTime|engine/(?:name|version|license)|rules/(?:calculationTimeZone|trueSolarTime|yearBoundary|monthBoundary|daySect|dayBoundary|yunSect|ageMode|monthSequence|auxBasis|smallFortuneBasis)|pillars/[0-3]/'+PILLAR_FIELDS+'|auxiliary/(?:taiYuan|taiXi|mingGong|shenGong)/(?:ganZhi|naYin)|startFortune/(?:forward|years|months|days|hours|solar))$',
   '^/rawOutput/periods/[0-9]/(?:index|ganZhi|startYear|endYear|startAge|endAge|xun|voidBranches|smallFortunes/\\d+/'+FLOW_FIELDS+'|years/\\d+/(?:'+FLOW_FIELDS+'|months/(?:[0-9]|1[01])/'+MONTH_FIELDS+'))$',
   '^/selection/(?:period|year|month|mode|outside|beforeStart|yearUnavailable|calendarYear|calendarMonthIndex|selectedYear|rangeStartYear|rangeEndYear|asOfUtc|calendar/(?:year|monthIndex|yearGanZhi|monthGanZhi|civilTime|utc|interval/(?:year|index|monthIndex|start|end|startJie|endJie|branch|startUtc|endUtc|startMs|endMs)))$',
   '^/comparison/(?:dayMaster|columns/[0-6]/(?:'+PILLAR_FIELDS+'|role|available|unavailableReason|relationBasis/(?:dayMaster|tenGod|growthStage)))$',
   '^/annotations/(?:rulesVersion|includedStars(?:/\\d+)?|limits(?:/\\d+)?|anchorPolicy/(?:lu|horse|general|canopy|robbery|loss|tianYi|wenChang|yangRen|yueDe|guoYin|jinYu|targets)|sources/\\d+/(?:id|title|url|scope)|rules/\\d+/(?:name|id|target|values(?:/\\d+)?|source|basis|anchor/(?:pillar|field|value))|columns/[0-6]/(?:key|available|selfStage|selfStageBasis|stars(?:/\\d+/(?:name|basis|rule|source|anchor/(?:pillar|field|value)|target/(?:field|value)))?))$',
   '^/domObserved/(?:status|columns/[0-6]/(?:stem|branch|ganZhi|hiddenStems|branchTenGods|stemTenGod|growthStage|selfStage|naYin|voidBranches|stars))$'
  ];return patterns.some(p=>new RegExp(p).test(path));
 }
 function validateCase(c,path='/case'){
  canonical(c);
  keys(c,['caseId','label','tags','input','context','options','selection','expected','expectedRuleIdentity','teacherApproval'],[],path);id(c.caseId,path+'/caseId');text(c.label,1,120,path+'/label');
  if(!Array.isArray(c.tags)||c.tags.length>20||new Set(c.tags).size!==c.tags.length||c.tags.some(t=>!TAGS.includes(t)))throw fault('invalid_tags',path+'/tags');
  keys(c.input,['date','time','sex'],['name'],path+'/input');gregorian(c.input.date,path+'/input/date');member(c.input.sex,['male','female'],path+'/input/sex');if(c.input.time!==null&&(typeof c.input.time!=='string'||!/^([01]\d|2[0-3]):[0-5]\d$/.test(c.input.time)))throw fault('invalid_time',path+'/input/time');if(own(c.input,'name'))text(c.input.name,0,60,path+'/input/name');
  keys(c.context,['mode','legacyTimezone','archivedUtc','sourceRecordSha256','ambiguity','asOfUtc'],[],path+'/context');member(c.context.mode,['shared-current','legacy-reference','isolated-fixture'],path+'/context/mode');member(c.context.ambiguity,['reject','earlier','later'],path+'/context/ambiguity');instant(c.context.asOfUtc,path+'/context/asOfUtc');sha(c.context.sourceRecordSha256,path+'/context/sourceRecordSha256');
  if(c.context.mode==='legacy-reference'){text(c.context.legacyTimezone,1,100,path+'/context/legacyTimezone');try{lcParts(0,c.context.legacyTimezone);}catch{throw fault('invalid_timezone',path+'/context/legacyTimezone');}if(c.context.archivedUtc!==null)instant(c.context.archivedUtc,path+'/context/archivedUtc');}
  else if(c.context.legacyTimezone!==null||c.context.archivedUtc!==null||c.context.sourceRecordSha256!==null)throw fault('legacy_context_forbidden',path+'/context');
  options(c.options,path+'/options');keys(c.selection,['mode','period','year','month'],[],path+'/selection');member(c.selection.mode,['current','manual'],path+'/selection/mode');for(const k of ['period','year','month'])if(c.selection[k]!==null&&(!Number.isSafeInteger(c.selection[k])||c.selection[k]<0||c.selection[k]>(k==='month'?11:k==='period'?9:200)))throw fault('invalid_selection',path+'/selection/'+k);if(c.selection.mode==='manual'&&['period','year','month'].some(k=>c.selection[k]===null))throw fault('invalid_selection',path+'/selection');if(c.selection.mode==='current'&&['period','year','month'].some(k=>c.selection[k]!==null))throw fault('invalid_selection',path+'/selection');
  if(!plain(c.expected)||Object.keys(c.expected).length>LIMITS.maxExpectedFieldsPerCase)throw fault('too_many_expected_fields',path+'/expected');
  for(const [p,e] of Object.entries(c.expected)){const at=path+'/expected/'+pointerEscape(p);if(!pathAllowed(p))throw fault('invalid_expected_path',at);if(!plain(e))throw fault('invalid_expectation',at);if(e.state==='value'){keys(e,['state','value'],[],at);if(bytes(canonical(e.value))>LIMITS.maxExpectedValueBytes)throw fault('expected_value_too_large',at,413);}else if(e.state==='not_applicable'){keys(e,['state','reasonCode'],[],at);member(e.reasonCode,NA_REASONS,at+'/reasonCode');}else throw fault('invalid_expectation',at);}
  if(c.expectedRuleIdentity!==null){const r=c.expectedRuleIdentity;keys(r,['engine','ruleVersion','annotationRulesVersion','options'],[],path+'/expectedRuleIdentity');if(r.engine!==null){keys(r.engine,['name','version'],[],path+'/expectedRuleIdentity/engine');text(r.engine.name,1,100,path+'/expectedRuleIdentity/engine/name');text(r.engine.version,1,100,path+'/expectedRuleIdentity/engine/version');}nullableText(r.ruleVersion,200,path+'/expectedRuleIdentity/ruleVersion');nullableText(r.annotationRulesVersion,200,path+'/expectedRuleIdentity/annotationRulesVersion');if(r.options!==null)options(r.options,path+'/expectedRuleIdentity/options');}
  keys(c.teacherApproval,['claimedReviewer','evidenceReference','evidenceSha256','verification'],[],path+'/teacherApproval');nullableText(c.teacherApproval.claimedReviewer,200,path+'/teacherApproval/claimedReviewer');nullableText(c.teacherApproval.evidenceReference,2000,path+'/teacherApproval/evidenceReference');sha(c.teacherApproval.evidenceSha256,path+'/teacherApproval/evidenceSha256');if(c.teacherApproval.verification!=='unverified-external-claim')throw fault('teacher_approval_forbidden',path+'/teacherApproval/verification');
  if(bytes(canonical(c))>LIMITS.maxCaseCanonicalBytes)throw fault('case_too_large',path,413);return c;
 }
 async function validateDataset(rawText){
  const data=strictParse(rawText);keys(data,['schema','setId','version','title','source','cases'],[],'');if(data.schema!==1)throw fault('invalid_schema','/schema');id(data.setId,'/setId');text(data.version,1,100,'/version');text(data.title,1,120,'/title');keys(data.source,['kind','reference','documentSha256','permissionReference'],[],'/source');member(data.source.kind,['synthetic','teacher-provided','legacy-reference'],'/source/kind');text(data.source.reference,1,2000,'/source/reference');sha(data.source.documentSha256,'/source/documentSha256');nullableText(data.source.permissionReference,2000,'/source/permissionReference');if(!Array.isArray(data.cases)||!data.cases.length||data.cases.length>LIMITS.maxCases)throw fault('invalid_case_count','/cases');
  const seen=new Set(),cases=[];for(let i=0;i<data.cases.length;i++){const c=validateCase(data.cases[i],'/cases/'+i);if(seen.has(c.caseId))throw fault('duplicate_case_id','/cases/'+i+'/caseId');seen.add(c.caseId);if(c.context.mode==='isolated-fixture'&&data.source.kind!=='synthetic')throw fault('fixture_source_required','/cases/'+i+'/context/mode');const encoded=canonical(c);cases.push({caseId:c.caseId,ordinal:i,canonicalSha256:await hash(encoded),canonicalByteLength:bytes(encoded)});}
  const encoded=canonical(data);return {dataset:data,sourceBytesSha256:await hash(rawText),sourceByteLength:bytes(rawText),canonicalSha256:await hash(encoded),canonicalByteLength:bytes(encoded),cases,teacherConfirmed:false,teacherConfirmedCaseCount:0,professionalValidation:false};
 }
 function atPath(stages,path){let v=stages;for(const segment of path.slice(1).split('/').map(s=>s.replace(/~1/g,'/').replace(/~0/g,'~'))){if(v===null||typeof v!=='object'||!own(v,segment))return {exists:false,value:null};v=v[segment];}return {exists:true,value:v};}
 function columnFor(path){let m=/^\/(?:rawOutput\/pillars|comparison\/columns|annotations\/columns|domObserved\/columns)\/([0-6])(?:\/|$)/.exec(path);if(m)return ['year','month','day','time','period','flowYear','flowMonth'][Number(m[1])];if(path.startsWith('/rawOutput/periods/'))return path.includes('/months/')?'flowMonth':path.includes('/years/')?'flowYear':path.includes('/smallFortunes/')?null:'period';return null;}
 function actualAt(report,path){
  const stage=path.split('/')[1],found=atPath(report.stages,path);
  if(stage==='domObserved'&&path!=='/domObserved/status')return {actualState:'unavailable',actual:null,reasonCode:'dom_not_run'};
  if(!found.exists)return {actualState:'unavailable',actual:null,reasonCode:report.errorCode||'field_unavailable'};
  let m=/^\/comparison\/columns\/(\d+)\/([^/]+)/.exec(path);if(m&&report.stages.comparison?.columns[Number(m[1])]?.available===false&&!['key','role','available','unavailableReason','relationBasis'].includes(m[2]))return {actualState:'not_applicable',actual:found.value,reasonCode:report.stages.comparison.columns[Number(m[1])].unavailableReason||'unavailable_column'};
  m=/^\/annotations\/columns\/(\d+)\/(selfStage|stars)(?:\/|$)/.exec(path);if(m&&report.stages.annotations?.columns[Number(m[1])]?.available===false)return {actualState:'not_applicable',actual:found.value,reasonCode:'unavailable_column'};
  m=/^\/rawOutput\/periods\/0\/(ganZhi|xun|voidBranches)$/.exec(path);if(m&&report.stages.rawOutput?.periods[0]?.ganZhi==='')return {actualState:'not_applicable',actual:found.value,reasonCode:'before-first-period'};
  return {actualState:'value',actual:found.value,reasonCode:''};
 }
 function enumerate(stages,expected){const paths=new Set(Object.keys(expected||{}));function walk(v,p){if(p&&pathAllowed(p))paths.add(p);if(v!==null&&typeof v==='object')for(const [k,x]of Object.entries(v))walk(x,p+'/'+pointerEscape(k));}walk(stages,'');return [...paths].sort();}
 function field(report,path){const e=report.expectations?.[path],a=actualAt(report,path),has=!!e;let comparison='not_covered',reasonCode='expected_not_provided';if(e){if(e.state==='not_applicable'){comparison=a.actualState==='not_applicable'&&(e.reasonCode==='not_applicable'||e.reasonCode===a.reasonCode)?'not_applicable':a.actualState==='unavailable'?'blocked':'different';reasonCode=comparison==='not_applicable'?a.reasonCode:comparison==='blocked'?a.reasonCode:'applicability_mismatch';}else if(a.actualState==='unavailable'){comparison='blocked';reasonCode=a.reasonCode;}else if(a.actualState==='not_applicable'){comparison='different';reasonCode='applicability_mismatch';}else{comparison=canonical(e.value)===canonical(a.actual)?'equal':'different';reasonCode=comparison==='equal'?'':'value_mismatch';}}
  return {caseId:report.caseId,stage:path.split('/')[1],path,column:columnFor(path),expectedState:has?(e.state==='not_applicable'?'not_applicable':'provided'):'not_covered',expected:e?.state==='value'?clone(e.value):null,...a,comparison,reasonCode,category:'undetermined',classificationState:'unclassified',evidence:{stageFingerprint:report.fingerprints?.[path.split('/')[1]]||null}};
 }
 function listFields(report,{before=null,limit=50}={}){if(!Number.isInteger(limit)||limit<1||limit>50)throw fault('invalid_page_size');const index=report.fieldIndex||enumerate(report.stages,report.expectations).map(path=>({path}));let start=0;if(before!==null){start=index.findIndex(row=>row.path===before);if(start<0)throw fault('invalid_cursor','',404);start++;}const rows=index.slice(start,start+limit),next=start+rows.length<index.length?rows[rows.length-1]?.path||null:null;return {items:rows.map(r=>field(report,r.path)),next,counts:report.counts};}
 async function splitRaw(raw){if(raw===null)return {header:null,headerSha256:null,headerByteLength:0,periods:[],sha256:null,byteLength:0};const header=clone(raw);delete header.periods;const head=canonical(header),whole=canonical(raw),periods=[];for(let i=0;i<raw.periods.length;i++){const data=clone(raw.periods[i]),encoded=canonical(data);periods.push({index:i,data,sha256:await hash(encoded),byteLength:bytes(encoded)});}return {header,headerSha256:await hash(head),headerByteLength:bytes(head),periods,sha256:await hash(whole),byteLength:bytes(whole)};}
 async function computeCase(input){
  canonical(input);const c=clone(validateCase(input)),stages={originalInput:clone(c.input),normalizedInput:null,rawOutput:null,selection:null,comparison:null,annotations:null,domObserved:{status:'not_run'}};
  const report={caseId:c.caseId,status:'succeeded',errorCode:'',stages,timing:null,selection:null,expectations:clone(c.expected),fieldResults:[],fieldIndex:[],counts:{equal:0,different:0,notCovered:0,notApplicable:0,blocked:0,provided:Object.keys(c.expected).length,total:0,teacherAgreementRate:null},fingerprints:{},rawIndex:{sha256:null,byteLength:0,periodCount:0,yearCount:0,monthCount:0,smallFortuneCount:0},teacherConfirmed:false,teacherConfirmedCaseCount:0,professionalValidation:false,domStatus:'not_run'};
  try{
   const timezone=c.context.mode==='legacy-reference'?c.context.legacyTimezone:'Etc/GMT-8';
   if(c.input.time===null){stages.normalizedInput={birth:{...clone(c.input),timezone,timeConfirmed:false},utc:null,china:null,offsetMinutes:null,candidateCount:0,timeMethod:'date-reference-only'};throw fault('birth_time_unknown','/input/time');}
   stages.normalizedInput=lcNormalizeInput({...c.input,timezone,ambiguity:c.context.ambiguity},{archivedUtc:c.context.mode==='legacy-reference'?c.context.archivedUtc:null});
   stages.rawOutput=lcBaziCalculate(stages.normalizedInput,c.options);
   if(c.selection.mode==='manual'&&!stages.rawOutput.periods[c.selection.period]?.years[c.selection.year]?.months[c.selection.month])throw fault('invalid_selection','/selection');
   const state={selection:c.selection.mode==='manual'?clone(c.selection):{}},timing=lcbResolveSelection(stages.rawOutput,state,instant(c.context.asOfUtc,'/context/asOfUtc'));
   stages.selection={...timing,asOfUtc:c.context.asOfUtc};report.timing=clone(stages.selection);report.selection=clone(stages.selection);
   stages.comparison=lcbBuildComparison(stages.rawOutput,{...state.selection,beforeStart:timing.beforeStart});stages.annotations=lcbBuildAnnotations(stages.rawOutput,stages.comparison);
  }catch(error){const known={NONEXISTENT_TIME:'nonexistent_time',AMBIGUOUS_TIME:'ambiguous_time',DATE_RANGE:'date_out_of_range',TIMEZONE:'invalid_timezone',BIRTH_REQUIRED:'birth_time_unknown',SEX_PARAMETER:'invalid_sex'};const code=known[error.code]||error.code||(error.message==='Solar-term navigation year is outside 1800–2399.'?'navigation_out_of_range':!lunar?.Solar?'adapter_unavailable':'calculation_failed');report.status=code==='calculation_failed'||code==='adapter_unavailable'?'failed':'blocked';report.errorCode=code;}
  for(const [stage,value]of Object.entries(stages))report.fingerprints[stage]=await hash(canonical(value));report.fingerprints.input=await hash(canonical(c));report.fingerprints.normalized=report.fingerprints.normalizedInput;
  if(stages.rawOutput){const raw=stages.rawOutput,encoded=canonical(raw);report.rawIndex={sha256:report.fingerprints.rawOutput,byteLength:bytes(encoded),periodCount:raw.periods.length,yearCount:raw.periods.reduce((n,p)=>n+p.years.length,0),monthCount:raw.periods.reduce((n,p)=>n+p.years.reduce((s,y)=>s+y.months.length,0),0),smallFortuneCount:raw.periods.reduce((n,p)=>n+p.smallFortunes.length,0)};}
  const paths=enumerate(stages,c.expected);report.fieldIndex=paths.map(path=>({path,stage:path.split('/')[1],column:columnFor(path),actualState:actualAt(report,path).actualState}));
  const mapping={equal:'equal',different:'different',not_covered:'notCovered',not_applicable:'notApplicable',blocked:'blocked'};
  for(const path of paths){const row=field(report,path);report.counts[mapping[row.comparison]]++;if(own(c.expected,path))report.fieldResults.push(row);}report.counts.total=paths.length;
  report.ruleIdentity={expected:clone(c.expectedRuleIdentity),actual:{engine:ENGINE,ruleVersion:RULE_VERSION,annotationRulesVersion:'eastern-bazi-annotations-2',options:clone(c.options)},teacherConfirmed:false};
  if(bytes(canonical(report))>LIMITS.maxCaseWorkerOutputBytes-1024)throw fault('output_too_large','',413);return report;
 }
 return Object.freeze({canonical,strictParse,validateDataset,validateCase,computeCase,listFields,splitRaw,pathAllowed,actualAt,normalizeInput:lcNormalizeInput,parts:lcParts,chinaParts:lcChinaParts,calculate:lcBaziCalculate,resolveSelection:lcbResolveSelection,currentSelection:lcbCurrentSelection,calendarAt:lcbCalendarAt,monthInterval:lcbMonthInterval,timeTerms:lcbTimeTerms,timeCivilMs:lcbTimeCivilMs,timeMoment:lcbTimeMoment,buildComparison:lcbBuildComparison,describePillar:lcbDescribePillar,comparisonPick:lcbComparisonPick,buildAnnotations:lcbBuildAnnotations,annotationPillar:lcbAnnotationPillar,annotationSelfStage:lcbAnnotationSelfStage,limits:LIMITS,tags:TAGS,notApplicableReasons:NA_REASONS,engine:ENGINE,ruleVersion:RULE_VERSION,adapterVersion:ADAPTER_VERSION});
 }
 return Object.freeze({createEngine,LIMITS,TAGS,ENGINE,RULE_VERSION,ADAPTER_VERSION});
});
