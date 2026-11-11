// Run with Node; writes only the named JSON report alongside this file.
// Fixed expectations below are hand-entered, never generated from the implementation under test.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root=path.resolve(__dirname,'..'),app=path.join(root,'04_研发源码','app','r4');
const library=require(path.join(app,'vendor','lunar-1.7.7.js'));
const context={LCLunar:library};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(app,'bazi-compare.js'),'utf8')+'\nthis.compare={lcbDescribePillar,lcbBuildComparison};',context);
const calculatorSource=fs.readFileSync(path.join(app,'life-chart-bazi.js'),'utf8').split('function lcbText(')[0];
vm.runInContext(calculatorSource+'\nthis.calculate=lcBaziCalculate;',context);
const {lcbDescribePillar:describe,lcbBuildComparison:build}=context.compare;
const plain=value=>JSON.parse(JSON.stringify(value)),checks=[];
function check(category,name,run){try{run();checks.push({category,name,passed:true});}catch(error){checks.push({category,name,passed:false,error:error.message});}}
// Columns: day master, pillar, hidden stems, stem god, hidden-stem gods, five elements,
// Na Yin, natal-day-stem growth stage, own pillar's xun, own pillar's void branches.
const fixed=[
 ['甲','甲子',['癸'],'比肩',['正印'],'木水','海中金','沐浴','甲子','戌亥'],
 ['甲','乙丑',['己','癸','辛'],'劫财',['正财','正印','正官'],'木土','海中金','冠带','甲子','戌亥'],
 ['甲','丙寅',['甲','丙','戊'],'食神',['比肩','食神','偏财'],'火木','炉中火','临官','甲子','戌亥'],
 ['甲','丁卯',['乙'],'伤官',['劫财'],'火木','炉中火','帝旺','甲子','戌亥'],
 ['甲','戊辰',['戊','乙','癸'],'偏财',['偏财','劫财','正印'],'土土','大林木','衰','甲子','戌亥'],
 ['甲','己巳',['丙','庚','戊'],'正财',['食神','七杀','偏财'],'土火','大林木','病','甲子','戌亥'],
 ['甲','庚午',['丁','己'],'七杀',['伤官','正财'],'金火','路旁土','死','甲子','戌亥'],
 ['甲','辛未',['己','丁','乙'],'正官',['正财','伤官','劫财'],'金土','路旁土','墓','甲子','戌亥'],
 ['甲','壬申',['庚','壬','戊'],'偏印',['七杀','偏印','偏财'],'水金','剑锋金','绝','甲子','戌亥'],
 ['甲','癸酉',['辛'],'正印',['正官'],'水金','剑锋金','胎','甲子','戌亥'],
 ['乙','甲戌',['戊','辛','丁'],'劫财',['正财','七杀','食神'],'木土','山头火','墓','甲戌','申酉'],
 ['乙','乙亥',['壬','甲'],'比肩',['正印','劫财'],'木水','山头火','死','甲戌','申酉'],
 ['乙','丙子',['癸'],'伤官',['偏印'],'火水','涧下水','病','甲戌','申酉'],
 ['乙','丁丑',['己','癸','辛'],'食神',['偏财','偏印','七杀'],'火土','涧下水','衰','甲戌','申酉'],
 ['乙','戊寅',['甲','丙','戊'],'正财',['劫财','伤官','正财'],'土木','城头土','帝旺','甲戌','申酉'],
 ['乙','己卯',['乙'],'偏财',['比肩'],'土木','城头土','临官','甲戌','申酉'],
 ['乙','庚辰',['戊','乙','癸'],'正官',['正财','比肩','偏印'],'金土','白蜡金','冠带','甲戌','申酉'],
 ['乙','辛巳',['丙','庚','戊'],'七杀',['伤官','正官','正财'],'金火','白蜡金','沐浴','甲戌','申酉'],
 ['乙','壬午',['丁','己'],'正印',['食神','偏财'],'水火','杨柳木','长生','甲戌','申酉'],
 ['乙','癸未',['己','丁','乙'],'偏印',['偏财','食神','比肩'],'水土','杨柳木','养','甲戌','申酉']
];
const comparedFields=['hiddenStems','stemTenGod','branchTenGods','fiveElements','naYin','growthStage','xun','voidBranches'];
for(const [dm,gz,...values] of fixed)check('fixed',dm+'日干对'+gz,()=>{
 const actual=plain(describe(gz,dm,{key:'flowYear'}));
 assert.equal(actual.ganZhi,gz);assert.equal(actual.stem,gz[0]);assert.equal(actual.branch,gz[1]);assert.equal(actual.available,true);
 comparedFields.forEach((field,i)=>assert.deepEqual(actual[field],values[i],field));
});
// Compatibility checks cover all 10 natal day stems × 12 target branches.
// They deliberately compare to the public EightChar API, not an independently sourced ephemeris.
const seen=new Set();
for(let year=1990;year<2002;year++)for(let day=1;day<=20;day++){
 const eight=library.Solar.fromYmdHms(year,6,day,12,0,0).getLunar().getEightChar();
 const dm=eight.getDayGan(),gz=eight.getYear(),pair=dm+eight.getYearZhi();if(seen.has(pair))continue;seen.add(pair);
 check('adapter',pair,()=>{
  const actual=plain(describe(gz,dm));
  const expected={hiddenStems:eight.getYearHideGan(),stemTenGod:eight.getYearShiShenGan(),branchTenGods:eight.getYearShiShenZhi(),fiveElements:eight.getYearWuXing(),naYin:eight.getYearNaYin(),growthStage:eight.getYearDiShi(),xun:eight.getYearXun(),voidBranches:eight.getYearXunKong()};
  comparedFields.forEach(field=>assert.deepEqual(actual[field],expected[field],field));
 });
}
function chart(daySect=2){return plain(context.calculate({china:{year:1990,month:1,day:1,hour:23,minute:30,second:0},birth:{sex:'male'}},{daySect,yunSect:2}));}
const natal=chart(),select={period:1,year:0,month:0,mode:'manual'};
check('structure','seven ordered columns reuse calculated natal values',()=>{
 const result=plain(build(natal,select));assert.deepEqual(result.columns.map(c=>c.key),['year','month','day','time','period','flowYear','flowMonth']);
 for(let i=0;i<4;i++)for(const field of ['ganZhi','stem','branch',...comparedFields])assert.deepEqual(result.columns[i][field],natal.pillars[i][field]);
 assert.equal(result.dayMaster,natal.pillars[2].stem);assert.equal(result.columns[2].stemTenGod,'日主');
});
check('selection','flow columns follow actual selected source records',()=>{
 const chosen={period:2,year:3,month:7},p=natal.periods[2],y=p.years[3],m=y.months[7],cols=build(natal,chosen).columns;
 assert.deepEqual(Array.from(cols.slice(4),c=>c.ganZhi),[p.ganZhi,y.ganZhi,m.ganZhi]);
});
check('selection','empty pre-fortune pillar stays unavailable',()=>{
 const result=plain(build(natal,{period:0,year:0,month:0})),p=result.columns[4];
 assert.equal(p.available,false);assert.equal(p.ganZhi,'');assert.equal(p.stem,'');assert.deepEqual(p.hiddenStems,[]);assert.equal(p.naYin,'');
 assert.notEqual(natal.pillars[1].ganZhi,p.ganZhi);
});
check('selection','current before exact first start hides period only',()=>{
 const manual=plain(build(natal,select)),current=plain(build(natal,{...select,mode:'current',beforeStart:true}));
 assert.equal(current.columns[4].available,false);assert.equal(current.columns[4].ganZhi,'');assert.equal(current.columns[4].unavailableReason,'before-first-start');
 assert.deepEqual(current.columns.slice(5),manual.columns.slice(5));
});
check('selection','manual viewing remains available before first start',()=>{
 assert.equal(build(natal,{...select,beforeStart:true}).columns[4].available,true);
});
check('selection','no selection uses first records without guessing another pillar',()=>{
 const result=build(natal);assert.equal(result.columns[4].available,false);assert.equal(result.columns[5].ganZhi,natal.periods[0].years[0].ganZhi);
});
check('rules','late Zi sect changes comparison day master from result',()=>{
 const a=chart(1),b=chart(2);assert.notEqual(a.pillars[2].stem,b.pillars[2].stem);
 for(const r of [a,b]){const v=build(r,select);assert.equal(v.dayMaster,r.pillars[2].stem);assert.equal(v.columns[5].stemTenGod,library.LunarUtil.SHI_SHEN[r.pillars[2].stem+v.columns[5].stem]);}
});
check('rules','flow stem equal to natal day stem is 比肩, not 日主',()=>assert.equal(describe('甲子','甲',{key:'flowYear'}).stemTenGod,'比肩'));
check('rules','growth uses natal day stem rather than target stem',()=>{
 assert.equal(describe('丙寅','甲').growthStage,'临官');assert.equal(describe('丙寅','丙').growthStage,'长生');
});
check('rules','own-pillar xun and void are not natal-hit predictions',()=>{
 const v=describe('甲戌','甲');assert.equal(v.xun,'甲戌');assert.equal(v.voidBranches,'申酉');assert.equal(v.natalVoidHit,undefined);
});
check('mutation','building and editing output does not mutate source or selection',()=>{
 const before=JSON.stringify(natal),s={...select},beforeSelection=JSON.stringify(s),out=build(natal,s);
 out.columns[0].hiddenStems.push('fake');out.columns[0].branchTenGods[0]='fake';out.columns[0].ganZhi='fake';
 assert.equal(JSON.stringify(natal),before);assert.equal(JSON.stringify(s),beforeSelection);
});
check('validation','invalid sexagenary pair rejected',()=>assert.throws(()=>describe('甲丑','甲'),/Invalid sexagenary/));
check('validation','invalid natal day stem rejected',()=>assert.throws(()=>describe('甲子','子'),/Invalid natal/));
check('validation','invalid explicit period index rejected',()=>assert.throws(()=>build(natal,{period:999}),/Invalid period/));
check('validation','invalid explicit year index rejected',()=>assert.throws(()=>build(natal,{period:1,year:-1}),/Invalid year/));
check('validation','invalid explicit month index rejected',()=>assert.throws(()=>build(natal,{period:1,year:0,month:12}),/Invalid month/));
check('validation','fractional and string selection indices rejected',()=>{
 assert.throws(()=>build(natal,{period:.5}),/Invalid period/);assert.throws(()=>build(natal,{period:'1'}),/Invalid period/);
});
check('validation','missing or duplicate calculated day pillar rejected',()=>{
 const a=plain(natal);a.pillars=a.pillars.filter(p=>p.key!=='day');assert.throws(()=>build(a,select),/day stem/);
 const b=plain(natal);b.pillars.push({...b.pillars[2]});assert.throws(()=>build(b,select),/natal pillar/);
});
check('validation','invalid selection object rejected',()=>assert.throws(()=>build(natal,null),/Invalid comparison/));
check('validation','unsupported fields such as strength and favorable elements absent',()=>{
 const text=JSON.stringify(build(natal,select));for(const key of ['strengthScore','favorableElements','prediction','luckScore'])assert.equal(text.includes('"'+key+'"'),false);
});
const report={executedAt:new Date().toISOString(),engine:{name:'lunar-javascript',version:'1.7.7'},scope:'M2 pillar descriptors and selected natal/fortune/year/month comparison; no UI or full application regression',
 sources:{commit:'4c45a59f79b856125516f31aefa8295035c16afd',eightChar:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/lunar.js#L5636-L5733',officialGrowthTable:'https://6tail.cn/calendar/lunar.bazi.html',officialTenGods:'https://6tail.cn/calendar/lunar.shishen.html',officialNaYin:'https://6tail.cn/calendar/lunar.nayin.html',officialXun:'https://6tail.cn/calendar/lunar.xun.html'},
 methodology:{fixed:'20 hand-entered expected pillar records; expectations are constants, not calculated from the helper or LunarUtil at run time.',adapter:'120 natal-day-stem × target-branch comparisons with the existing public EightChar API. This is same-library adapter compatibility, not independent astronomical accuracy certification.',limits:'Traditional table relationships only. No strength, favorable-element inference or prediction. Full UI and application regression are separate.'},
 fixedFixtures:fixed.map(([dayMaster,ganZhi,...values])=>({dayMaster,ganZhi,expected:Object.fromEntries(comparedFields.map((field,i)=>[field,values[i]]))})),
 totals:{fixed:checks.filter(c=>c.category==='fixed').length,adapter:checks.filter(c=>c.category==='adapter').length,other:checks.filter(c=>!['fixed','adapter'].includes(c.category)).length,total:checks.length,passed:checks.filter(c=>c.passed).length,failed:checks.filter(c=>!c.passed).length},checks};
fs.writeFileSync(path.join(__dirname,'八字本命运程对照核验.json'),JSON.stringify(report,null,2)+'\n','utf8');
console.log(JSON.stringify(report.totals));for(const c of checks.filter(c=>!c.passed))console.error(c.name+': '+c.error);
if(report.totals.failed)process.exitCode=1;
