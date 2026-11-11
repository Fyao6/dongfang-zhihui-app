// M4 calculation checks. No user data, services or UI are involved.
// Prior regression scripts execute unchanged; their report writes are captured in memory.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict'),crypto=require('crypto'),{createRequire}=require('module');
const root=path.resolve(__dirname,'..'),app=path.join(root,'04_研发源码','app','r4'),adapter=path.join(app,'life-chart-bazi.js');
const source=fs.readFileSync(adapter,'utf8'),ui=source.slice(source.indexOf('function lcbText('));
const library=require(path.join(app,'vendor','lunar-1.7.7.js')),context={LCLunar:library};
vm.createContext(context);
vm.runInContext(source.split('function lcbText(')[0]+'\nthis.calculate=lcBaziCalculate;',context);
vm.runInContext(fs.readFileSync(path.join(app,'bazi-time.js'),'utf8'),context);
const plain=v=>JSON.parse(JSON.stringify(v)),results=[];
function check(name,run){try{run();results.push({name,pass:true});}catch(error){results.push({name,pass:false,error:error.stack});}}
function calculate(date,time,sex='male',options={daySect:2,yunSect:2}){
 const [year,month,day]=date.split('-').map(Number),[hour,minute,second=0]=time.split(':').map(Number);
 return plain(context.calculate({birth:{date,time,timezone:'Etc/GMT-8',sex},china:{year,month,day,hour,minute,second},utc:new Date(Date.UTC(year,month-1,day,hour-8,minute,second)).toISOString()},options));
}
const sources={commit:'4c45a59f79b856125516f31aefa8295035c16afd',officialAuxiliaryFixtures:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/__tests__/EightChar.test.js',auxiliaryMethods:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/lunar.js#L5734-L5778',smallFortuneMethods:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/lunar.js#L5884-L5991'};
// Explicit constants from the pinned official tests. Tests do not derive expectations from the adapter.
const official=[
 {date:'2005-12-23',time:'08:37',expected:{taiYuan:'己卯',mingGong:'己丑'}},
 {date:'1995-12-18',time:'10:28',expected:{taiYuan:'己卯',mingGong:'戊子',shenGong:'壬午'}},
 {date:'1998-06-11',time:'04:28',expected:{mingGong:'辛酉'}},
 {date:'1994-12-06',time:'02:00',expected:{shenGong:'丁丑'}},
 {date:'1990-12-11',time:'06:00',expected:{shenGong:'庚辰'}},
 {date:'1993-05-23',time:'04:00',expected:{shenGong:'庚申'}},
 {date:'2024-01-29',time:'09:30',expected:{mingGong:'癸亥',shenGong:'己未'}},
 {date:'1986-02-16',time:'08:00',expected:{mingGong:'己亥',shenGong:'乙未'}}
];
for(const fixture of official)check('Official auxiliary constants '+fixture.date+' '+fixture.time,()=>{
 const r=calculate(fixture.date,fixture.time);for(const [key,value] of Object.entries(fixture.expected))assert.equal(r.auxiliary[key].ganZhi,value,key);
});
// Hand-entered Na Yin and stem/branch-combination expectations, separate from runtime lookup.
check('Four auxiliary records carry fixed stem-branch and Na Yin values',()=>{
 assert.deepEqual(calculate('1995-12-18','10:28').auxiliary,{
  taiYuan:{ganZhi:'己卯',naYin:'城头土'},taiXi:{ganZhi:'戊午',naYin:'天上火'},
  mingGong:{ganZhi:'戊子',naYin:'霹雳火'},shenGong:{ganZhi:'壬午',naYin:'杨柳木'}
 });
});
check('Late Zi TaiXi follows the selected day pillar: 丁卯→壬戌, 丙寅→辛亥',()=>{
 const a=calculate('1990-01-01','23:30','male',{daySect:1,yunSect:2}),b=calculate('1990-01-01','23:30','male',{daySect:2,yunSect:2});
 assert.equal(a.pillars[2].ganZhi,'丁卯');assert.equal(b.pillars[2].ganZhi,'丙寅');
 assert.deepEqual(a.auxiliary.taiXi,{ganZhi:'壬戌',naYin:'大海水'});assert.deepEqual(b.auxiliary.taiXi,{ganZhi:'辛亥',naYin:'钗钏金'});
 for(const key of ['taiYuan','mingGong','shenGong'])assert.deepEqual(a.auxiliary[key],b.auxiliary[key]);
 assert.deepEqual(a.periods.map(p=>p.smallFortunes),b.periods.map(p=>p.smallFortunes));
});
// Both dates have 丙午 natal time pillars. One nominal year moves one sexagenary step.
const directions=[
 {date:'1990-06-01',sex:'male',forward:true,firstYear:1990,first:['丁未','戊申'],firstPeriodYear:1992,firstPeriodAge:3,firstPeriodPillar:'己酉'},
 {date:'1990-06-01',sex:'female',forward:false,firstYear:1990,first:['乙巳','甲辰'],firstPeriodYear:1999,firstPeriodAge:10,firstPeriodPillar:'丙申'},
 {date:'1991-06-01',sex:'male',forward:false,firstYear:1991,first:['乙巳','甲辰'],firstPeriodYear:2000,firstPeriodAge:10,firstPeriodPillar:'丙申'},
 {date:'1991-06-01',sex:'female',forward:true,firstYear:1991,first:['丁未','戊申'],firstPeriodYear:1993,firstPeriodAge:3,firstPeriodPillar:'己酉'}
];
for(const f of directions)check('Fixed annual small-fortune direction '+f.date+' '+f.sex,()=>{
 const r=calculate(f.date,'12:00',f.sex),pre=r.periods[0].smallFortunes,p=r.periods[1].smallFortunes;
 assert.equal(r.pillars[3].ganZhi,'丙午');assert.equal(r.startFortune.forward,f.forward);
 assert.deepEqual(pre.slice(0,2).map(x=>x.ganZhi),f.first);assert.equal(pre[0].year,f.firstYear);assert.equal(pre[0].age,1);
 assert.deepEqual(p[0],{year:f.firstPeriodYear,age:f.firstPeriodAge,ganZhi:f.firstPeriodPillar,xun:f.forward?'甲辰':'甲午',voidBranches:f.forward?'寅卯':'辰巳'});
});
check('January direction uses the previous Li-Chun year, not Gregorian year parity',()=>{
 const r=calculate('1990-01-01','23:30');assert.equal(r.pillars[0].ganZhi,'己巳');assert.equal(r.startFortune.forward,false);
 assert.deepEqual(r.periods[0].smallFortunes[0],{year:1990,age:1,ganZhi:'己亥',xun:'甲午',voidBranches:'辰巳'});
});
check('Pre-first-period small fortunes exist although the major pillar is empty',()=>{
 const p=calculate('1995-12-18','10:28').periods[0];assert.equal(p.ganZhi,'');assert.equal(p.smallFortunes.length,4);
 assert.deepEqual(p.smallFortunes[0],{year:1995,age:1,ganZhi:'丙辰',xun:'甲寅',voidBranches:'子丑'});
 assert.deepEqual(p.smallFortunes[p.smallFortunes.length-1],{year:1998,age:4,ganZhi:'癸丑',xun:'甲辰',voidBranches:'寅卯'});
});
check('Same-calendar-year start leaves an empty pre-first-period array',()=>{
 const r=calculate('1990-06-06','00:00');assert.equal(r.startFortune.solar,'1990-07-09 20:00:00');assert.deepEqual(r.periods[0].smallFortunes,[]);
 assert.deepEqual(r.periods[1].smallFortunes[0],{year:1990,age:1,ganZhi:'辛丑',xun:'甲午',voidBranches:'辰巳'});
});
check('Before the exact first start, the current year still has a small-fortune record',()=>{
 const r=calculate('1990-06-06','00:00'),selection=context.lcbCurrentSelection(r,Date.parse('1990-06-07T12:00:00+08:00'));
 assert.equal(selection.beforeStart,true);assert.equal(selection.period,1);assert.equal(selection.selectedYear,1990);
 const x=r.periods[selection.period].smallFortunes.find(item=>item.year===selection.selectedYear);assert.equal(x.ganZhi,'辛丑');
});
check('Exact-term zero waiting period has valid small fortunes and no pre-start row',()=>{
 const r=calculate('2012-09-07','13:29:01','female');assert.equal(r.startFortune.solar,'2012-09-07 13:29:01');assert.deepEqual(r.periods[0].smallFortunes,[]);assert.equal(r.periods[1].smallFortunes.length,10);
});
check('Each period small-fortune year and age align with its existing flow-year rows',()=>{
 for(const sex of ['male','female'])for(const daySect of [1,2])for(const yunSect of [1,2]){
  const r=calculate('1990-01-01','23:30',sex,{daySect,yunSect});
  for(const p of r.periods){assert.equal(p.smallFortunes.length,p.years.length);assert.deepEqual(p.smallFortunes.map(x=>[x.year,x.age]),p.years.map(x=>[x.year,x.age]));for(const x of p.smallFortunes)assert.deepEqual(Object.keys(x),['year','age','ganZhi','xun','voidBranches']);}
 }
});
check('Different calculations do not share mutable auxiliary or small-fortune records',()=>{
 const a=calculate('1995-12-18','10:28'),expected=plain(a);a.auxiliary.taiXi.ganZhi='changed';a.periods[0].smallFortunes[0].ganZhi='changed';
 calculate('2005-12-23','08:37','female');assert.deepEqual(calculate('1995-12-18','10:28'),expected);
});
check('Repeated calculations and JSON round-trip remain deterministic and finite',()=>{
 const a=calculate('2005-12-23','08:37'),b=calculate('2005-12-23','08:37');assert.deepEqual(a,b);assert.deepEqual(plain(a),a);
 function inspect(v){if(typeof v==='number')assert(Number.isFinite(v));else if(Array.isArray(v))v.forEach(inspect);else if(v&&typeof v==='object')Object.values(v).forEach(inspect);else assert(['string','boolean'].includes(typeof v)||v===null);}
 inspect(a);assert.equal(a.schemaVersion,1);assert.equal(a.kind,'bazi');
});
check('All auxiliary fields are plain paired values and factual rules are recorded',()=>{
 const r=calculate('2005-12-23','08:37');assert.deepEqual(Object.keys(r.auxiliary),['taiYuan','taiXi','mingGong','shenGong']);
 for(const v of Object.values(r.auxiliary)){assert.deepEqual(Object.keys(v),['ganZhi','naYin']);assert.equal(typeof v.ganZhi,'string');assert.equal(typeof v.naYin,'string');}
 assert.equal(r.rules.auxBasis,'EightChar auxiliary methods; TaiXi follows selected daySect');assert.equal(r.rules.smallFortuneBasis,'DaYun.getXiaoYun; natal time pillar, Yun direction and nominal calendar-year ages');
});
if(process.argv.includes('--verify-untouched-ui'))check('UI suffix outside the authorized calculation function is unchanged',()=>{
 assert.equal(crypto.createHash('sha256').update(ui.replace(/\r\n/g,'\n')).digest('hex'),'f92ab249900f4cf2a835cad0125997db2b3e7f3dbb1ecf1b84e5ff35054daade');
});
function runPrior(name){
 const filename=path.join(__dirname,name),nativeRequire=createRequire(filename),writes=[],logs=[],sandboxProcess={exitCode:0,env:process.env};
 const safeFs={...fs,writeFileSync(file,data){if(!String(file).endsWith('.json'))throw new Error('Unexpected regression write: '+file);writes.push({file:String(file),data:String(data)});}};
 const safeRequire=id=>id==='fs'||id==='node:fs'?safeFs:nativeRequire(id),safeConsole={log:(...v)=>logs.push(v.join(' ')),error:(...v)=>logs.push(v.join(' '))};
 // Use the normal Node realm so assert.deepStrictEqual sees the same array prototypes as normal CJS execution.
 const wrapper=vm.runInThisContext('(function(exports,require,module,__filename,__dirname,process,console){\n'+fs.readFileSync(filename,'utf8')+'\n})',{filename});
 wrapper({},safeRequire,{exports:{}},filename,path.dirname(filename),sandboxProcess,safeConsole);
 assert.equal(sandboxProcess.exitCode||0,0,logs.filter(l=>/FAIL|failed/.test(l)).join('\n'));assert.equal(writes.length,1);
 const captured=JSON.parse(writes[0].data),report=captured.latest||captured,totals=report.totals||{passed:report.passed,failed:report.failed,total:report.passed+report.failed};
 assert.equal(totals.failed,0);return {script:name,reportWrites:'captured in memory; original report unchanged',totals,report};
}
const regressions=[];
for(const [name,count] of [['八字计算样例核验.cjs',14],['八字当前运程边界核验.cjs',20],['八字本命运程对照核验.cjs',160]])check('Unchanged earlier regression '+name,()=>{
 const run=runPrior(name);assert.equal(run.totals.passed,count);regressions.push(run);
});
const report={executedAt:new Date().toISOString(),module:'M4 auxiliary pillars and annual small fortunes',scope:'Calculation adapter only; official fixed auxiliary constants, hand-entered relation/sequence fixtures, and unchanged prior calculation regressions. No UI/full application regression or publication.',sources,
 methodology:{official:'Auxiliary ganZhi expectations are fixed values from the pinned official EightChar.test.js.',handEntered:'TaiXi late-Zi constants, Na Yin names and small-fortune sequences are fixed manually; no expected values are generated from the adapter under test. These are not an independent astronomical ephemeris certification.',priorRuns:'Original source scripts execute in the normal Node realm; only their final JSON report writes are captured in memory and included below.',uiIsolation:'The completed pre-UI adapter run verified the untouched UI suffix. Pass --verify-untouched-ui only when checking that original editing boundary; later authorized UI work may change it.'},
 sourceSha256:crypto.createHash('sha256').update(source).digest('hex'),uiSuffixSha256:crypto.createHash('sha256').update(ui.replace(/\r\n/g,'\n')).digest('hex'),uiSuffixHashNormalization:'CRLF to LF, matching the pre-edit read baseline',officialFixtures:official,directionFixtures:directions,
 pass:results.every(r=>r.pass),passed:results.filter(r=>r.pass).length,failed:results.filter(r=>!r.pass).length,results,regressions};
const output=path.join(__dirname,'八字辅助与小运核验.json');let runs=[];
if(fs.existsSync(output))try{const old=JSON.parse(fs.readFileSync(output,'utf8'));runs=old.runs||[old];}catch{}
runs.push(report);fs.writeFileSync(output,JSON.stringify({latest:report,runs:runs.slice(-10)},null,2)+'\n','utf8');
console.log(JSON.stringify({passed:report.passed,failed:report.failed,regressions:regressions.map(r=>({script:r.script,...r.totals}))}));
for(const result of results.filter(r=>!r.pass))console.error(result.name+': '+result.error);
if(!report.pass)process.exitCode=1;
