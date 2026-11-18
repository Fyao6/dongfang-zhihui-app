'use strict';
const assert=require('node:assert/strict');
const {makeHarness}=require('./负责人优化建议-卡组迁移测试工具.cjs');
const h=makeHarness();
const memoryTimer=setInterval(()=>console.log('CASE06_CLIENT_MEMORY:'+JSON.stringify({at:new Date().toISOString(),pid:process.pid,...process.memoryUsage()})),5000);memoryTimer.unref();
(async()=>{try{await h.start();const a=await h.seed(),f=require('./负责人优化建议-卡组迁移用例工具.cjs')(h,a),skipped=[];let selected=0;
 await require('./负责人优化建议-卡组迁移导入专项.cjs')({h,a,f,api:h.api,key:h.key,check:async(name,work)=>{if(!name.startsWith('06 ')){skipped.push(name);return;}selected++;await h.check(name,work);}});
 assert.equal(selected,1);assert.equal(h.report.results.length,1);h.report.componentOnly=true;h.report.formalAcceptance=false;h.report.selectedOriginalCases=[6];h.report.explicitlySkipped=skipped;h.report.clientMemoryAtFinish=process.memoryUsage();await h.finish();
 }catch(error){h.report.componentOnly=true;h.report.formalAcceptance=false;await h.finish(error);}})();
