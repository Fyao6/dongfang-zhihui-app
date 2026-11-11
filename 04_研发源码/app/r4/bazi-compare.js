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
if(typeof module==='object'&&module.exports)module.exports={lcbDescribePillar,lcbBuildComparison};
