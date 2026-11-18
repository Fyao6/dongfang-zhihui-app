'use strict';
const assert=require('node:assert/strict');
const {makeHarness}=require('./负责人优化建议-八字样本测试工具.cjs'),h=makeHarness();
(async()=>{try{
 await h.start();const a=await h.seed(),f=require('./负责人优化建议-八字样本用例工具.cjs')(h,a),ctx={h,a,f,api:h.api,check:h.check,key:h.key};
 h.report.formalAcceptance=true;h.report.scope='Forty actual HTTP/native browser sample-tool checks against the same isolated final build. Teacher verification remains zero; synthetic fixture and platform-specific coverage are explicit.';
 await require('./负责人优化建议-八字样本导入专项.cjs')(ctx);
 await require('./负责人优化建议-八字样本计算专项.cjs')(ctx);
 await require('./负责人优化建议-八字样本一致性专项.cjs')(ctx);
 await require('./负责人优化建议-八字样本原生专项.cjs')(ctx);
 assert.equal(h.report.results.length,40,'Exactly forty actual sample checks');await h.finish();
}catch(error){await h.finish(error);}})();
