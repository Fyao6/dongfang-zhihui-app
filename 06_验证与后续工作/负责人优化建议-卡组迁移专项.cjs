'use strict';
// Integrated actual HTTP and native DOM only. Pure component reports are separate evidence.
const assert=require('node:assert/strict');
const {makeHarness}=require('./负责人优化建议-卡组迁移测试工具.cjs');
const h=makeHarness();
(async()=>{try{await h.start();const a=await h.seed(),f=require('./负责人优化建议-卡组迁移用例工具.cjs')(h,a),ctx={h,a,f,api:h.api,check:h.check,key:h.key};
 await require('./负责人优化建议-卡组迁移导入专项.cjs')(ctx);
 await require('./负责人优化建议-卡组迁移版本专项.cjs')(ctx);
 await require('./负责人优化建议-卡组迁移归档专项.cjs')(ctx);
 await require('./负责人优化建议-卡组迁移原生专项.cjs')(ctx);
 assert.equal(h.report.results.length,40,'All forty actual business checks must run');await h.finish();
}catch(error){await h.finish(error);}})();
