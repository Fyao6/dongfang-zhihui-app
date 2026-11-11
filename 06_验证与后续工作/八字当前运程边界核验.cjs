// Fixed official calendar fixtures, half-open second boundaries, and current/manual navigation contracts.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4');
const files={helper:path.join(r4,'bazi-time.js'),adapter:path.join(r4,'life-chart-bazi.js'),vendor:path.join(r4,'vendor/lunar-1.7.7.js')};
const library=require(files.vendor),context={LCLunar:library,screens:{},document:{addEventListener(){}},lcText:(_en,zh)=>zh};
vm.createContext(context);for(const file of [files.helper,files.adapter])vm.runInContext(fs.readFileSync(file,'utf8'),context,{filename:path.basename(file)});
const sources={commit:'4c45a59f79b856125516f31aefa8295035c16afd',terms:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/__tests__/JieQi.test.js',fortune:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/__tests__/Yun.test.js',implementation:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/lunar.js#L3887'};
const results=[];
function check(name,fn){try{fn();results.push({name,pass:true});console.log('PASS '+name);}catch(error){results.push({name,pass:false,error:error.stack});console.log('FAIL '+name+': '+error.message);}}
const ms=civil=>Date.parse(civil.replace(' ','T')+'+08:00'),plain=value=>JSON.parse(JSON.stringify(value));
function calculate(date,time,sex='male'){
 const [year,month,day]=date.split('-').map(Number),[hour,minute,second=0]=time.split(':').map(Number);
 return plain(context.lcBaziCalculate({birth:{date,time,timezone:'Asia/Shanghai',sex},china:{year,month,day,hour,minute,second},utc:new Date(Date.UTC(year,month-1,day,hour-8,minute,second)).toISOString()},{daySect:2,yunSect:2}));
}
check('Official White Dew fixture has the fixed second and correct UTC offset',()=>{
 const i=context.lcbMonthInterval(2012,7);assert.equal(i.start,'2012-09-07 13:29:01');assert.equal(i.startUtc,'2012-09-07T05:29:01.000Z');assert.equal(i.startJie,'白露');assert.equal(i.endJie,'寒露');assert.equal(i.branch,'酉');
});
check('Official 2050 Great Snow fixture also resolves the next-year alias edge',()=>{
 const i=context.lcbMonthInterval(2050,10);assert.equal(i.start,'2050-12-07 06:41:54');assert.equal(i.startJie,'大雪');assert.equal(i.endJie,'小寒');assert(i.end.startsWith('2051-01-'));
});
check('White Dew is half-open: one second before, exact, and one second after',()=>{
 const t=ms('2012-09-07 13:29:01');assert.equal(context.lcbCalendarAt(t-1000).monthIndex,6);assert.equal(context.lcbCalendarAt(t).monthIndex,7);assert.equal(context.lcbCalendarAt(t+1000).monthIndex,7);assert.equal(context.lcbCalendarAt(t).monthGanZhi,'己酉');
});
check('January Small Cold belongs to the previous solar-term year, not month one',()=>{
 const i=context.lcbMonthInterval(2025,11);assert.equal(i.start,'2026-01-05 16:23:10');assert.equal(i.end,'2026-02-04 04:02:08');assert.equal(i.branch,'丑');
 const t=ms(i.start),a=context.lcbCalendarAt(t-1000),b=context.lcbCalendarAt(t);assert.equal(a.year,2025);assert.equal(a.monthIndex,10);assert.equal(b.year,2025);assert.equal(b.monthIndex,11);
});
check('Li Chun changes both solar-term year and month precisely at its second',()=>{
 const t=ms('2026-02-04 04:02:08'),a=context.lcbCalendarAt(t-1000),b=context.lcbCalendarAt(t),c=context.lcbCalendarAt(t+1000);
 assert.equal(a.year,2025);assert.equal(a.monthIndex,11);assert.equal(a.yearGanZhi,'乙巳');assert.equal(b.year,2026);assert.equal(b.monthIndex,0);assert.equal(b.yearGanZhi,'丙午');assert.equal(c.year,2026);assert.equal(b.monthGanZhi,'庚寅');
});
check('A middle solar term does not start another month',()=>{
 const l=library.Solar.fromYmdHms(2026,7,1,12,0,0).getLunar(),t=ms(l.getJieQiTable()[l.getJieQiList()[3]].toYmdHms());
 assert.equal(context.lcbCalendarAt(t-1000).monthIndex,11);assert.equal(context.lcbCalendarAt(t).monthIndex,11);assert.equal(context.lcbCalendarAt(t+1000).monthIndex,11);
});
check('Late Zi and civil midnight do not prematurely change month or year',()=>{
 for(const text of ['2026-02-03 22:59:59','2026-02-03 23:00:00','2026-02-04 00:00:00','2026-02-04 04:02:07']){
  const c=context.lcbCalendarAt(ms(text));assert.equal(c.year,2025);assert.equal(c.monthIndex,11);
 }
});
check('All twelve intervals are contiguous across English next-year keys',()=>{
 for(const year of [1899,1900,2012,2025,2026,2099,2100]){
  let last;for(let i=0;i<12;i++){const r=context.lcbMonthInterval(year,i);if(last)assert.equal(r.startMs,last.endMs);assert(r.endMs-r.startMs>25*86400000);assert(r.endMs-r.startMs<33*86400000);const c=context.lcbCalendarAt(r.startMs);assert.equal(c.year,year);assert.equal(c.monthIndex,i);last=r;}
  assert.equal(last.endMs,context.lcbMonthInterval(year+1,0).startMs);
 }
});
check('1900 and 2099 input-year edges retain valid adjacent-year boundaries',()=>{
 const a=context.lcbCalendarAt(ms('1900-01-01 00:00:00')),b=context.lcbCalendarAt(ms('2099-12-31 23:59:59'));
 assert.equal(a.year,1899);assert.equal(a.monthIndex,10);assert.equal(b.year,2099);assert.equal(b.monthIndex,10);assert(b.interval.end.startsWith('2100-01-'));
});
check('UTC instants and boundaries do not depend on the machine timezone',()=>{
 const original=process.env.TZ;try{let expected;for(const timezone of ['UTC','America/Los_Angeles','Asia/Shanghai']){process.env.TZ=timezone;const r=plain(context.lcbCalendarAt(Date.parse('2026-02-03T20:02:08Z')));if(expected)assert.deepEqual(r,expected);else expected=r;}}finally{if(original===undefined)delete process.env.TZ;else process.env.TZ=original;}
});
const sample=calculate('2005-12-23','08:37');
check('Current navigation chooses the real current year and solar-term month',()=>{
 const c=context.lcbCurrentSelection(sample,ms('2026-11-05 12:00:00'));assert.equal(c.period,2);assert.equal(c.year,5);assert.equal(c.month,8);assert.equal(c.selectedYear,2026);assert.equal(c.outside,'');assert.equal(c.beforeStart,false);
});
check('Legal manual selections remain unchanged across renders and Li Chun',()=>{
 const state={selection:{mode:'manual',period:1,year:2,month:7,stale:'drop'}};
 for(const time of ['2026-02-04 04:02:07','2026-02-04 04:02:08']){const r=context.lcbResolveSelection(sample,state,ms(time));assert.equal(r.period,1);assert.equal(r.year,2);assert.equal(r.month,7);assert.equal(r.mode,'manual');}
 assert.deepEqual(plain(state.selection),{period:1,year:2,month:7,mode:'manual'});
});
check('Current mode refreshes at Li Chun and persists only four navigation fields',()=>{
 const state={selection:{mode:'current',period:1,year:2,month:7}};
 const a=context.lcbResolveSelection(sample,state,ms('2026-02-04 04:02:07')),b=context.lcbResolveSelection(sample,state,ms('2026-02-04 04:02:08'));
 assert.equal(a.year,4);assert.equal(a.month,11);assert.equal(b.year,5);assert.equal(b.month,0);assert.deepEqual(Object.keys(state.selection).sort(),['mode','month','period','year']);
});
check('Invalid manual values and an empty initial selection fall back to current',()=>{
 for(const selection of [{},{mode:'manual',period:999,year:0,month:0},{mode:'manual',period:1,year:99,month:0},{mode:'manual',period:1,year:0,month:12},{mode:'manual',period:'1',year:0,month:0}]){
  const state={selection},r=context.lcbResolveSelection(sample,state,ms('2026-11-05 12:00:00'));assert.equal(r.mode,'current');assert.equal(r.period,2);assert.equal(r.year,5);assert.equal(r.month,8);
 }
});
check('Future birth is explicitly outside and never described as a current fortune',()=>{
 const r=context.lcbCurrentSelection(calculate('2099-12-31','23:59'),ms('2026-11-05 12:00:00'));assert.equal(r.outside,'before-birth');assert.equal(r.beforeStart,false);assert.equal(r.yearUnavailable,true);
});
check('Dates after the final represented Li Chun year are explicitly outside',()=>{
 const r=calculate('1900-01-01','12:00'),max=Math.max(...r.periods.flatMap(p=>p.years.map(y=>y.year))),edge=context.lcbMonthInterval(max+1,0).startMs;
 assert.equal(context.lcbCurrentSelection(r,edge-1000).outside,'');assert.equal(context.lcbCurrentSelection(r,edge).outside,'after-range');
});
check('Official first-start date gates beforeStart even within its table start year',()=>{
 const r=calculate('2022-03-09','20:51');assert.equal(r.startFortune.solar.slice(0,10),'2030-12-12');const edge=ms(r.startFortune.solar),a=context.lcbCurrentSelection(r,edge-1000),b=context.lcbCurrentSelection(r,edge);
 assert.equal(a.beforeStart,true);assert.equal(a.period,1);assert.equal(a.selectedYear,2030);assert.equal(b.beforeStart,false);assert.equal(b.outside,'');
});
check('A January birth before Li Chun does not invent a missing earlier flow year',()=>{
 const r=calculate('1900-01-02','12:00'),c=context.lcbCurrentSelection(r,ms('1900-01-03 12:00:00'));
 assert.equal(c.outside,'');assert.equal(c.yearUnavailable,true);assert.equal(c.calendarYear,1899);assert.equal(c.selectedYear,1900);assert.equal(c.beforeStart,true);
});
check('Zero-wait start skips the empty pre-start period without an invalid selection',()=>{
 const r=calculate('2012-09-07','13:29:01','female');assert.equal(r.periods[0].years.length,0);
 const state={selection:{mode:'manual',period:0,year:0,month:0}},c=context.lcbResolveSelection(r,state,ms('2012-09-07 13:29:01'));assert.equal(c.period,1);assert.equal(c.mode,'current');assert.equal(c.beforeStart,false);assert.equal(c.month,7);
});
check('Invalid helper arguments reject instead of creating fictitious periods',()=>{
 for(const i of [-1,12,1.5,'1'])assert.throws(()=>context.lcbMonthInterval(2026,i));assert.throws(()=>context.lcbMonthInterval('2026',0));assert.throws(()=>context.lcbCalendarAt(NaN));assert.throws(()=>context.lcbCurrentSelection({periods:[]},ms('2026-11-05 12:00:00')));
});
const hashes=Object.fromEntries(Object.entries(files).map(([key,file])=>[key,crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')]));
const report={at:new Date().toISOString(),module:'M1 Ba Zi current/manual selection and exact solar-term boundaries',pass:results.every(x=>x.pass),passed:results.filter(x=>x.pass).length,failed:results.filter(x=>!x.pass).length,engine:'lunar-javascript 1.7.7',sources,sourceSha256:hashes,scope:'Numerical navigation and deterministic fixtures. Official fixed second expectations cover 2012 White Dew and 2050 Great Snow; 2026 boundaries are pinned engine regression values. Period/year rows retain the source library calendar-year convention; beforeStart is separately gated by the actual first start instant. No UI, service, archive, or publication operation is performed.',results};
const output=path.join(__dirname,'八字当前运程边界核验.json');let runs=[];if(fs.existsSync(output))try{const old=JSON.parse(fs.readFileSync(output,'utf8'));runs=old.runs||[old];}catch{}runs.push(report);fs.writeFileSync(output,JSON.stringify({latest:report,runs:runs.slice(-20)},null,2));console.log(JSON.stringify({pass:report.pass,passed:report.passed,failed:report.failed,report:output}));process.exitCode=report.pass?0:1;
