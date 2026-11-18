// Fixed twelve sourced rules are implemented once in the shared factory.
function lcbAnnotationEngine(){return typeof lcBaziShared==='function'?lcBaziShared():require('./life-chart-core.js').lcBaziShared();}
function lcbAnnotationUtil(){return typeof LCLunar!=='undefined'?LCLunar.LunarUtil:typeof LunarUtil!=='undefined'?LunarUtil:require('./vendor/lunar-1.7.7.js').LunarUtil;}
function lcbAnnotationPillar(p,u,allowEmpty=false){return lcbAnnotationEngine().annotationPillar(p,u,allowEmpty);}
function lcbAnnotationSelfStage(stem,branch,u){return lcbAnnotationEngine().annotationSelfStage(stem,branch,u);}
function lcbBuildAnnotations(result,comparison){return lcbAnnotationEngine().buildAnnotations(result,comparison);}
if(typeof module==='object'&&module.exports)module.exports={lcbBuildAnnotations};
