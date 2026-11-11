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
if(typeof module==='object'&&module.exports)module.exports={lcbBuildAnnotations};
