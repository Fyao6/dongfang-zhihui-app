'use strict';
// Integrated actual HTTP and native DOM only. Pure component reports are separate evidence.
const assert=require('node:assert/strict');
const {makeHarness}=require('./负责人优化建议-卡组迁移测试工具.cjs');
const h=makeHarness();
// The expected first-entry dialog is handled by a real shown-dialog native click.
// Every original import/migration business assertion and native interaction follows unchanged.
const originalBrowserContext=h.browserContext;
h.browserContext=async(...args)=>{const value=await originalBrowserContext.apply(h,args);await value.page.addLocatorHandler(value.page.locator('dialog.der-dialog[open][data-der-shown="true"]'),async dialog=>{assert(await dialog.isVisible());await dialog.locator('[data-der-action="close"]').first().click();await dialog.waitFor({state:'hidden'});h.report.expectedDailyDialogNativeCloses=(h.report.expectedDailyDialogNativeCloses||0)+1;});return value;};
(async()=>{try{await h.start();const a=await h.seed(),f=require('./负责人优化建议-卡组迁移用例工具.cjs')(h,a),ctx={h,a,f,api:h.api,check:h.check,key:h.key};
 await require('./负责人优化建议-卡组迁移导入专项.cjs')(ctx);
 await require('./负责人优化建议-卡组迁移版本专项.cjs')(ctx);
 await require('./负责人优化建议-卡组迁移归档专项.cjs')(ctx);
 await require('./负责人优化建议-卡组迁移原生专项.cjs')(ctx);
 assert.equal(h.report.results.length,40,'All forty actual business checks must run');await h.finish();
}catch(error){await h.finish(error);}})();
