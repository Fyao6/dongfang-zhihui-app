// Pure algorithms live in the shared factory; only the view clock is selected here.
function lcbTimeEngine(){return typeof lcBaziShared==='function'?lcBaziShared():require('./life-chart-core.js').lcBaziShared();}
function lcbViewNow(current){const s=current||(typeof lcGet==='function'?lcGet('bazi'):null);return s?.sampleContext===true&&Number.isFinite(s.sampleAsOfMs)?s.sampleAsOfMs:Date.now();}
function lcbTimeLibrary(){return typeof LCLunar!=='undefined'?LCLunar:typeof Solar!=='undefined'?{Solar}:require('./vendor/lunar-1.7.7.js');}
function lcbTimeCivilMs(value){return lcbTimeEngine().timeCivilMs(value);}
function lcbTimeMoment(value){return lcbTimeEngine().timeMoment(value);}
function lcbTimeTerms(year){return lcbTimeEngine().timeTerms(year);}
function lcbMonthInterval(year,index){return lcbTimeEngine().monthInterval(year,index);}
function lcbCalendarAt(ms){return lcbTimeEngine().calendarAt(ms===undefined?lcbViewNow():ms);}
function lcbCurrentSelection(result,now){return lcbTimeEngine().currentSelection(result,now===undefined?lcbViewNow():now);}
function lcbResolveSelection(result,state,now){return lcbTimeEngine().resolveSelection(result,state,now===undefined?lcbViewNow(state):now);}
if(typeof module==='object'&&module.exports)module.exports={lcbTimeCivilMs,lcbTimeMoment,lcbTimeTerms,lcbMonthInterval,lcbCalendarAt,lcbCurrentSelection,lcbResolveSelection};
