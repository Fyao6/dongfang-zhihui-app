'use strict';
// Synthetic geometry component only: no product, API, 51-run or formal acceptance claim.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require(path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const output=path.join(__dirname,'负责人优化建议-任务告警横滑几何组件-非formal.json');
assert(!fs.existsSync(output),'Preserve the previous component report; never overwrite it');
const report={at:new Date().toISOString(),scope:'independent synthetic long-table geometry component; not product/API integration',sourceSha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),formalAcceptance:false,productApiCalls:0,actualProductRows:false,syntheticRowCount:51,nativePlaywrightWheel:true,programmaticScrollLeftAssignment:false,cases:[]};let browser;
(async()=>{try{
 browser=await chromium.launch({headless:true});
 for(const width of [360,1280]){
  const page=await browser.newPage({viewport:{width,height:850}});
  await page.setContent('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;font:16px sans-serif}.spacer{height:1400px}.table-wrap{margin:16px;border:1px solid #555;overflow:auto}table{border-collapse:collapse;min-width:1640px;width:1640px;table-layout:fixed}td,th{height:48px;padding:0 12px;border:1px solid #bbb;text-align:left}</style></head><body><div class="spacer">Synthetic component, no product data</div><div id="owned-long-wrap" class="table-wrap"><table><thead><tr>'+Array.from({length:8},(_,i)=>'<th>Component column '+i+'</th>').join('')+'</tr></thead><tbody>'+Array.from({length:51},(_,row)=>'<tr>'+Array.from({length:8},(_,col)=>'<td>synthetic '+row+'/'+col+'</td>').join('')+'</tr>').join('')+'</tbody></table></div><div class="spacer">Component footer</div></body></html>');
  const wrap=page.locator('#owned-long-wrap');await wrap.scrollIntoViewIfNeeded();const box=await wrap.boundingBox(),viewport=page.viewportSize();assert(box&&viewport);
  const size=await wrap.evaluate(el=>({clientWidth:el.clientWidth,scrollWidth:el.scrollWidth,clientHeight:el.clientHeight,scrollHeight:el.scrollHeight}));assert(size.scrollWidth>size.clientWidth+1);assert(box.height>viewport.height);
  const oldPoint={x:box.x+box.width/2,y:box.y+Math.min(40,box.height/2)};
  const intersection={left:Math.max(0,box.x),top:Math.max(0,box.y),right:Math.min(viewport.width,box.x+box.width),bottom:Math.min(viewport.height,box.y+box.height)};
  assert(intersection.right>intersection.left&&intersection.bottom>intersection.top);
  const visiblePoint={x:(intersection.left+intersection.right)/2,y:(intersection.top+intersection.bottom)/2};
  const hit=point=>page.evaluate(({x,y})=>{const el=document.elementFromPoint(x,y);return {tag:el?.tagName||null,id:el?.id||null,closestWrapId:el?.closest('.table-wrap')?.id||null,insideOwnedWrap:!!el&&document.getElementById('owned-long-wrap').contains(el)};},point);
  const oldHit=await hit(oldPoint),visibleHit=await hit(visiblePoint);
  await page.mouse.move(oldPoint.x,oldPoint.y);await page.mouse.wheel(-2000,0);await page.waitForTimeout(150);const oldBefore=await wrap.evaluate(el=>el.scrollLeft);await page.mouse.wheel(700,0);await page.waitForTimeout(150);const oldAfter=await wrap.evaluate(el=>el.scrollLeft);
  await page.mouse.move(visiblePoint.x,visiblePoint.y);assert((await hit(visiblePoint)).insideOwnedWrap);await page.mouse.wheel(-2000,0);await page.waitForTimeout(150);const visibleBefore=await wrap.evaluate(el=>el.scrollLeft);await page.mouse.wheel(700,0);await page.waitForFunction(before=>document.getElementById('owned-long-wrap').scrollLeft>before+1,visibleBefore,{timeout:3000});const visibleAfter=await wrap.evaluate(el=>el.scrollLeft);
  const oldOutside=oldPoint.x<0||oldPoint.y<0||oldPoint.x>=viewport.width||oldPoint.y>=viewport.height;
  report.cases.push({width,viewport,bbox:box,size,intersection,old:{point:oldPoint,hit:oldHit,outsideViewport:oldOutside,beforeLeft:oldBefore,afterLeft:oldAfter,delta:oldAfter-oldBefore},visible:{point:visiblePoint,hit:visibleHit,beforeLeft:visibleBefore,afterLeft:visibleAfter,delta:visibleAfter-visibleBefore}});
  assert(oldOutside);assert(!oldHit.insideOwnedWrap);assert.equal(oldAfter,oldBefore,'Offscreen pointer does not scroll this wrapper');assert(visibleHit.insideOwnedWrap);assert(visibleAfter>visibleBefore+1,'Visible hit responds to actual native wheel');await page.close();
 }
 report.pass=true;
}catch(error){report.pass=false;report.error=String(error?.stack||error).slice(0,2000);process.exitCode=1;}finally{if(browser)await browser.close();fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({pass:report.pass,report:path.basename(output),cases:report.cases}));}})();
