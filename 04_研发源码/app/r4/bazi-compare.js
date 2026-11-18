// Original public helpers delegate to the same deterministic factory used by the servers.
function lcbComparisonEngine(){return typeof lcBaziShared==='function'?lcBaziShared():require('./life-chart-core.js').lcBaziShared();}
function lcbComparisonUtil(){return typeof LCLunar!=='undefined'?LCLunar.LunarUtil:typeof LunarUtil!=='undefined'?LunarUtil:require('./vendor/lunar-1.7.7.js').LunarUtil;}
function lcbDescribePillar(ganZhi,dayMaster,context={}){return lcbComparisonEngine().describePillar(ganZhi,dayMaster,context);}
function lcbComparisonPick(items,index,label){return lcbComparisonEngine().comparisonPick(items,index,label);}
function lcbBuildComparison(result,selection={}){return lcbComparisonEngine().buildComparison(result,selection);}
if(typeof module==='object'&&module.exports)module.exports={lcbDescribePillar,lcbBuildComparison};
