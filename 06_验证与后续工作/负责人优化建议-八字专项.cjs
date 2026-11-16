// Current four-pillar contract. Synthetic browser-only inputs; no production writes.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),src=path.join(root,'04_研发源码/app/r4');
const {setLifeBirth}=require('./生命出生资料测试前置.cjs');
const natalKeys=['year','month','day','time'],allKeys=[...natalKeys,'period','flowYear','flowMonth'];
const compact=v=>String(v??'').replace(/\s/g,'');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
async function ready(p){await p.waitForFunction(()=>!document.documentElement.dataset.ambientTransition);await p.evaluate(()=>document.fonts.ready);}
async function isFourPillars(p){return await p.locator('[data-lcb-presentation=four-pillars]').count()>0;}
async function boardMode(p,full=false){
 assert(await isFourPillars(p),'The new presentation has an explicit four-pillars contract');
 const button=p.locator('[data-lcb-action=board-mode]');assert.equal(await button.count(),1);
 const count=await p.locator('[data-lcb-heading]').count();
 if((count>4)!==full){await button.click();await ready(p);}
 if(full&&await p.locator('[data-lcb-heading]').count()===6){await p.locator('[data-lcb-action=flow-month]').click();await ready(p);}
 assert.equal(await p.locator('[data-lcb-heading]').count(),full?7:4);
}
async function boardDetails(p,open=false){
 const body=p.locator('#lcb-board-extra');assert.equal(await body.count(),1);
 if(await body.evaluate(e=>e.hidden)===open){await p.locator('[data-lcb-action=board-details]').click();await ready(p);}
 assert.equal(await body.evaluate(e=>e.hidden),!open);
 assert.equal(await p.locator('[data-lcb-action=board-details]').getAttribute('aria-expanded'),String(open));
}
async function assertFourPillarsDefault(p){
 assert.equal(await p.locator('[data-lcb-layout=reference][data-lcb-presentation=four-pillars]').count(),1);
 assert.deepEqual(await p.locator('[data-lcb-heading]').evaluateAll(es=>es.map(e=>e.dataset.lcbHeading)),natalKeys);
 assert.equal(await p.locator('#lcb-board-extra').evaluate(e=>e.hidden),true);
 assert.equal(await p.locator('[data-lcb-board-column]:visible').count(),12);
 assert.equal(await p.locator('[data-lcb-board-column]').count(),28);
 const profile=p.locator('details[data-lcb-profile-summary]');assert.equal(await profile.count(),1);assert.equal(await profile.evaluate(e=>e.open),false);
 assert.equal(await p.locator('[data-lcb-element-legend]').count(),1);
 assert.equal(await p.locator('[data-lcb-selected-range]').count(),1);
 assert(await p.locator('[data-lcb-action=board-mode]').isVisible());
 const edit=p.locator('.lc-workspace [data-lc-action=edit][data-kind=bazi],.lc-workspace [data-lb-action=edit]');
 assert(await edit.count()>0&&await edit.first().isVisible(),'Editing remains visible outside the collapsed private profile');
 return {columns:4,defaultCells:12,expandedCells:28};
}
async function assertBoardValues(p,{keys}={}){
 const headings=await p.locator('[data-lcb-heading]').evaluateAll(es=>es.map(e=>e.dataset.lcbHeading));
 if(keys)assert.deepEqual(headings,keys);
 const data=await p.evaluate(()=>{const s=lcGet('bazi'),timing=lcbResolveSelection(s.result,s);return lcbBuildComparison(s.result,{...s.selection,beforeStart:timing.beforeStart});});
 for(const key of headings){
  const actual=data.columns.find(c=>c.key===key);assert(actual);
  for(const field of ['stem','branch','growthStage','naYin','voidBranches']){
   const cell=p.locator('[data-lcb-board-column="'+key+'"][data-field="'+field+'"]');assert.equal(await cell.count(),1);
   assert.equal(compact(await cell.innerText()),actual.available?compact(actual[field]):'—',key+'.'+field);
  }
  if(actual.available){
   const hidden=p.locator('[data-lcb-board-column="'+key+'"][data-field=hiddenStems]');
   assert.deepEqual(await hidden.locator('.lcb-hidden-pair>.lcb-element').allTextContents(),actual.hiddenStems);
   assert.deepEqual(await hidden.locator('.lcb-hidden-pair>[title]').evaluateAll(es=>es.map(e=>e.title)),actual.branchTenGods);
   const god=p.locator('[data-lcb-board-column="'+key+'"][data-field=stemTenGod]');
   if(key==='day')assert.equal(await god.locator('[data-lcb-glossary=dayMaster]').count(),1);else assert.equal(compact(await god.innerText()),actual.stemTenGod);
  }
 }
 return headings.length*7;
}
async function assertStarGroups(p,keys,{expand=true}={}){
 const data=await p.evaluate(()=>{const s=lcGet('bazi'),t=lcbResolveSelection(s.result,s);return lcbBuildAnnotations(s.result,lcbBuildComparison(s.result,{...s.selection,beforeStart:t.beforeStart}));});
 assert.equal(await p.locator('[data-lcb-stars]').count(),keys.length);
 for(const key of keys){
  const column=data.columns.find(c=>c.key===key),cell=p.locator('[data-lcb-stars="'+key+'"]'),group=cell.locator('details[data-lcb-star-group]');
  assert.equal(await group.count(),1);assert.equal(await group.evaluate(e=>e.open),false,'Each pillar initially summarizes its marker count');
  const count=(await group.locator(':scope>summary').innerText()).match(/\d+/);assert(count,'Count must be visible as text');assert.equal(Number(count[0]),column.stars.length);
  const markers=group.locator('details[data-lcb-marker]');assert.equal(await markers.count(),column.stars.length);
  assert.equal(await markers.locator(':scope>summary:visible').count(),0,'Closed group keeps the dense list folded');
  if(expand){
   await group.locator(':scope>summary').click();assert.equal(await group.evaluate(e=>e.open),true);
   assert.deepEqual(await markers.locator(':scope>summary').allTextContents(),column.stars.map(x=>x.name));
   if(column.stars.length){await markers.first().locator(':scope>summary').click();const text=await markers.first().innerText();assert(text.includes(column.stars[0].basis));await markers.first().locator(':scope>summary').click();}
   await group.locator(':scope>summary').click();
  }
 }
 return {pillars:keys.length,markers:data.columns.filter(c=>keys.includes(c.key)).reduce((n,c)=>n+c.stars.length,0)};
}
async function tab(p,view){await p.locator('[data-lcb-action=view][data-view='+view+']').click();await ready(p);assert.equal(await p.locator('.lcb-view-tabs [aria-selected=true]').getAttribute('data-view'),view);}
async function noOverflow(p){assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1&&document.getElementById('app').scrollWidth<=document.getElementById('app').clientWidth+1),'Only local table regions may scroll horizontally');}
async function standalone(){
 const args=Object.fromEntries(process.argv.slice(2).filter(a=>a.startsWith('--')).map(a=>{const n=a.indexOf('=');return [a.slice(2,n<0?undefined:n),n<0?true:a.slice(n+1)];}));
 const base=String(args.base||'http://127.0.0.1:8881'),target=String(args.target||'python'),moduleName=String(args.module||'负责人优化建议-八字四柱');
 assert(/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base)&&!['8879','8880'].includes(new URL(base).port),'Use an explicitly isolated local service');assert(['python','cloud'].includes(target));
 const reportName=String(args.report||moduleName+'-'+target+'专项.json');assert(path.basename(reportName)===reportName&&reportName.endsWith('.json'));
 const reportFile=path.join(__dirname,reportName),artifact=path.join(root,target==='cloud'?'04_研发源码/app/cloud/generated/experience.html':'03_当前APP/东方智慧-首页体验R4.html');
 const sourceNames=['life-chart-core.js','life-chart-bazi.js','life-chart-bazi-layout.js','life-chart-bazi-annotations.js','life-chart-bazi.css','life-birth-entry.js','bazi-time.js','bazi-compare.js','bazi-glossary.js'];
 const report={at:new Date().toISOString(),module:moduleName,target,base,syntheticClientOnly:true,productionWrites:false,scope:'Four widths, two themes and four languages; real UI disclosures and calculations from synthetic birth data. Teacher-approved sample accuracy is not claimed.',sourceHashes:Object.fromEntries(sourceNames.map(n=>[n,hash(fs.readFileSync(path.join(src,n)))])),buildSha256:hash(fs.readFileSync(artifact)),harnessSha256:hash(fs.readFileSync(__filename)),results:[],errors:[],blockedWrites:[],birthWrites:[],captures:[]};
 let browser,context,p;
 const group=async(name,fn)=>{try{report.results.push({name,pass:true,detail:await fn()});console.log('PASS '+name);}catch(e){report.results.push({name,pass:false,error:String(e.stack||e)});console.log('FAIL '+name+': '+e.message);}};
 try{
  const served=Buffer.from(await(await fetch(base+'/experience')).arrayBuffer());assert.equal(hash(served),report.buildSha256,'Service serves the current target build');
  const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
  browser=await chromium.launch({headless:true});context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});context.setDefaultTimeout(15000);
  await context.route('**/api/**',r=>{const q=r.request();if(['GET','HEAD'].includes(q.method()))return r.continue();const record={method:q.method(),path:new URL(q.url()).pathname};report.blockedWrites.push(record);if(/birth|chart/.test(record.path))report.birthWrites.push(record);return r.fulfill({status:401,contentType:'application/json',body:'{"error":"Synthetic client-only test"}'});});
  p=await context.newPage();p.on('pageerror',e=>report.errors.push(e.message));await p.clock.setFixedTime(new Date('2026-11-05T04:00:00Z'));await p.goto(base+'/experience?lang=zh-Hans');await p.waitForFunction(()=>px.loaded&&!pxBootstrapPending);await ready(p);
  await setLifeBirth(p,{name:'QA_FOUR_PILLARS',date:'2005-12-23',sex:'male',time:'08:37'});await p.evaluate(()=>navigate('classicsWisdom'));await ready(p);await p.waitForFunction(()=>!!lcGet('bazi').result);
  if(await p.locator('[data-action=tb-hide]').isVisible())await p.locator('[data-action=tb-hide]').click();
  const birth=await p.evaluate(()=>JSON.stringify(lbProfile())),result=await p.evaluate(()=>JSON.stringify(lcGet('bazi').result));
  await group('四柱默认12格、细项折叠、资料收起与真实图例',async()=>{await assertFourPillarsDefault(p);assert.deepEqual(await p.evaluate(()=>lcGet('bazi').result.pillars.map(x=>x.ganZhi)),['乙酉','戊子','辛巳','壬辰']);return {knownNatalFixture:true,...await assertFourPillarsDefault(p)};});
  await p.evaluate(()=>ewI18n.missing.clear());
  for(const width of [375,390,393,430])for(const mode of ['day','night'])for(const lang of ['zh','zh-Hant','en','bo'])await group(width+'px '+mode+' '+lang+' 四柱详细与完整对照',async()=>{
   await p.setViewportSize({width,height:844});await p.evaluate(({lang,mode})=>{state.lang=lang;state.mode=mode;render(false);},{lang,mode});await ready(p);await tab(p,'flow');await boardMode(p,false);await boardDetails(p,false);await assertFourPillarsDefault(p);await noOverflow(p);
   const primary=await p.locator('[data-lcb-board-column][data-field=stem],[data-lcb-board-column][data-field=branch]').evaluateAll(es=>{const s=document.querySelector('[data-lcb-board-scroll]').getBoundingClientRect();return es.every(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.left>=s.left-1&&r.right<=s.right+1&&parseFloat(getComputedStyle(e.querySelector('.lcb-element')).fontSize)>=24;});});assert(primary,'The four natal stems and branches fit without shrinking below 24px');
   if(['zh','zh-Hant'].includes(lang)){const legend=await p.locator('[data-lcb-element-legend]').innerText();for(const label of ['木','火','土','金','水'])assert(legend.includes(label),'Legend names each element');}
   await boardDetails(p,true);assert.equal(await p.locator('[data-lcb-board-column]:visible').count(),28);await assertBoardValues(p,{keys:natalKeys});
   await boardMode(p,true);assert.equal(await p.locator('[data-lcb-board-column]:visible').count(),49);await assertBoardValues(p,{keys:allKeys});await noOverflow(p);
   const last=p.locator('[data-lcb-board-column=flowMonth][data-field=stem]');await last.scrollIntoViewIfNeeded();assert(await last.evaluate(e=>{const r=e.getBoundingClientRect(),s=e.closest('[data-lcb-board-scroll]').getBoundingClientRect();return r.left>=s.left-1&&r.right<=s.right+1;}),'Last comparison column is reachable through real horizontal scrolling');
   await p.locator('[data-lcb-action=flow-month]').click();await ready(p);assert.equal(await p.locator('[data-lcb-heading]').count(),6);await assertBoardValues(p,{keys:allKeys.slice(0,6)});await boardMode(p,false);await boardDetails(p,false);await noOverflow(p);
   assert.equal(await p.evaluate(()=>JSON.stringify(lbProfile())),birth);assert.equal(await p.evaluate(()=>JSON.stringify(lcGet('bazi').result)),result);
   if(mode==='day'&&lang==='zh'||width===390&&mode==='night'&&['en','bo'].includes(lang)){
    await p.evaluate(()=>document.getElementById('app').scrollTop=0);const file=moduleName+'-'+target+'-'+width+'-'+mode+'-'+lang+'.png';await p.screenshot({path:path.join(__dirname,file)});report.captures.push({file,sha256:hash(fs.readFileSync(path.join(__dirname,file))),width,mode,lang});
   }
   return {width,mode,lang,defaultVisibleCells:12,expandedVisibleCells:28,fullVisibleCells:49,alternateColumns:6};
  });
  await group('神煞按柱数量收起、逐项展开与四七列一致',async()=>{await p.evaluate(()=>{state.lang='zh';state.mode='day';render(false)});await ready(p);await boardMode(p,false);await tab(p,'stars');const basic=await assertStarGroups(p,natalKeys);await boardMode(p,true);const full=await assertStarGroups(p,allKeys);await boardMode(p,false);await tab(p,'flow');return {basic,full};});
  await group('真实日期区间联动、回到当前与本命档案不变',async()=>{
   const current=await p.evaluate(()=>({...lcGet('bazi').selection}));
   for(const [kind,index]of [['period',1],['year',3],['month',5]]){await p.locator('[data-lcb-action='+kind+'][data-index="'+index+'"]').click();await ready(p);}
   const expected=await p.evaluate(()=>{const s=lcGet('bazi');return lcbMonthInterval(s.result.periods[s.selection.period].years[s.selection.year].year,s.selection.month);}),range=await p.locator('[data-lcb-selected-range]').innerText();for(const value of [expected.startJie,expected.endJie,expected.start,expected.end])assert(range.includes(value),'Selected range shows actual boundary '+value);
   assert(range.includes('小暑')&&range.includes('立秋'));await boardDetails(p,true);await boardMode(p,true);await assertBoardValues(p,{keys:allKeys});assert.equal(compact(await p.locator('[data-lcb-board-column=flowYear][data-field=stem]').innerText()),'甲');assert.equal(compact(await p.locator('[data-lcb-board-column=flowMonth][data-field=branch]').innerText()),'未');await boardMode(p,false);await boardDetails(p,false);
   await p.locator('[data-lcb-action=today]').click();await ready(p);assert.deepEqual(await p.evaluate(()=>lcGet('bazi').selection),current);assert.equal(await p.evaluate(()=>JSON.stringify(lbProfile())),birth);assert.equal(await p.evaluate(()=>JSON.stringify(lcGet('bazi').result)),result);return {selectedYear:2014,selectedMonth:5,actualRange:expected,restoredCurrent:true};
  });
  await group('时辰未知不产生伪造四柱',async()=>{await setLifeBirth(p,{name:'QA_FOUR_PILLARS_UNKNOWN',date:'2005-12-23',sex:'male',time:''});await p.evaluate(()=>navigate('classicsWisdom'));await ready(p);assert.equal(await p.locator('[data-lc-result=bazi]').count(),0);assert.equal(await p.locator('[data-lcb-board]').count(),0);return {exactChartAbsent:true};});
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.birthWrites,[]);assert.deepEqual(await p.evaluate(()=>[...ewI18n.missing]),[]);
 }catch(e){report.results.push({name:'本轮专项环境或总体验证',pass:false,error:String(e.stack||e)});console.log('FAIL '+e.message);}
 finally{if(browser)await browser.close();report.pass=report.results.length>0&&report.results.every(x=>x.pass)&&report.errors.length===0&&report.birthWrites.length===0;report.passed=report.results.filter(x=>x.pass).length;report.failed=report.results.filter(x=>!x.pass).length;fs.writeFileSync(reportFile,JSON.stringify(report,null,2),'utf8');console.log(JSON.stringify({pass:report.pass,passed:report.passed,failed:report.failed,report:reportFile}));process.exitCode=report.pass?0:1;}
}
module.exports={isFourPillars,boardMode,boardDetails,assertFourPillarsDefault,assertBoardValues,assertStarGroups};
if(require.main===module)standalone();
