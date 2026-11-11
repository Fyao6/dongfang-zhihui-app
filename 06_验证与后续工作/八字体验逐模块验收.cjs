// Browser acceptance shared by the Python and Cloudflare full regression suites.
// All birth inputs are synthetic. Standalone runs use a disposable local DB.
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {spawn}=require('child_process');
const root=path.resolve(__dirname,'..'),source=path.join(root,'04_研发源码/app/r4'),web=path.join(root,'03_当前APP');
const lifeBirth=require('./生命出生资料测试前置.cjs');
const fixedNow='2026-11-05T04:00:00.000Z'; // 12:00, fixed UTC+8; before Li Dong.
const fixture={name:'QA_BAZI_STAGE_M1',date:'1985-01-01',time:'12:00',timezone:'Asia/Shanghai',sex:'male'};
const stageNames={1:'八字M1 当前运年流月定位、节令边界与选择回看',2:'八字M2 本命与运年流月七列真实对照',3:'八字M3 四柱层级、资料折叠与术语实际释义',4:'八字M4 辅助四项、小运联动与旧档案复算'};
const expectedTerms={start:'2026-10-08 14:29:17',end:'2026-11-07 17:52:05',startJie:'寒露',endJie:'立冬'};
// C1 keeps the accepted compact presentation; C2 opts into the full reference
// table explicitly. Calendar fixtures and all four acceptance stages are shared.
async function baziReferenceLayout(page){return await page.locator('[data-lcb-layout=reference]').count()>0;}

async function openBaziTools(p){
 const existing=p.locator('#sheet[open] .lcb-tools-panel');if(await existing.count())return existing;
 assert.equal(await p.locator('#sheet[open]').count(),0,'Close the current sheet before opening chart tools');
 await p.locator('[data-lcb-action=tools]').click();await p.locator('#sheet[open] .lcb-tools-panel').waitFor({state:'visible'});return p.locator('#sheet[open] .lcb-tools-panel');
}
async function closeBaziTools(p){
 if(!await p.locator('#sheet[open] .lcb-tools-panel').count())return;
 await p.locator('#sheet[open] .close-sheet').click();await p.waitForFunction(()=>!document.querySelector('#sheet[open]'));
}
async function baziAction(p,action){
 const tools=await openBaziTools(p),button=tools.locator('[data-lc-action="'+action+'"][data-kind=bazi]');assert.equal(await button.count(),1);assert(await button.isVisible());await button.click();await p.waitForFunction(()=>!document.documentElement.dataset.ambientTransition);await closeBaziTools(p);
}
async function setBaziRules(p,values){
 const tools=await openBaziTools(p),form=tools.locator('form[data-lb-options=bazi]');await form.waitFor({state:'attached'});
 for(const detail of (await form.locator('xpath=ancestor::details').all()).reverse())if(!await detail.evaluate(el=>el.open))await detail.locator(':scope>summary').click();
 for(const [name,value]of Object.entries(values))await form.locator('[name="'+name+'"]').selectOption(String(value));
 await form.locator('button[type=submit]').click();await p.waitForFunction(()=>!document.documentElement.dataset.ambientTransition);await p.waitForFunction(()=>!document.querySelector('#sheet[open] .lcb-tools-panel'));
}
async function baziBoardDetails(p,expanded=true){
 const body=p.locator('#lcb-board-extra');assert.equal(await body.count(),1);
 if(await body.evaluate(el=>el.hidden)===expanded)await p.locator('[data-lcb-action=board-details]').click();
 await p.waitForFunction(expanded=>document.getElementById('lcb-board-extra')?.hidden===!expanded,expanded);
 if(expanded)assert(await body.locator('td').first().isVisible(),'Detailed board values are genuinely exposed by their control');
}
async function ready(page){await page.waitForFunction(()=>!document.documentElement.dataset.ambientTransition);}
async function go(page,id){await closeBaziTools(page);await page.evaluate(id=>navigate(id),id);await ready(page);}
// Navigate actual reading tabs before accessing their lazily rendered content.
async function showBaziView(page,key){
 await closeBaziTools(page);assert(['archive','flow','stars'].includes(key),'Only the three actual Ba Zi views are addressable');
 const tab=page.locator('.lcb-view-tabs [data-lcb-action=view][data-view="'+key+'"]');assert.equal(await tab.count(),1,'The requested real Ba Zi tab exists: '+key);
 if(await tab.getAttribute('aria-selected')!=='true'){await tab.click();await ready(page);}
 await page.waitForFunction(key=>document.querySelector('[data-lcb-view-panel="'+key+'"]')?.hidden===false,key);
 assert.equal(await tab.getAttribute('aria-selected'),'true');assert.equal(await page.locator('[data-lcb-view-panel]:visible').count(),1,'Exactly one Ba Zi reading view is visible');
 return true;
}
async function openNatalDetails(page){
 await showBaziView(page,'archive');const details=page.locator('details[data-lcb-natal-details]');assert.equal(await details.count(),1,'Archive preserves the actual four-pillar record');
 if(!await details.evaluate(el=>el.open)){await details.locator(':scope>summary').click();await ready(page);}
 await details.locator('.lcb-pillars').waitFor({state:'visible'});
 assert(await details.locator('.lcb-pillars').isVisible(),'The four-pillar record is genuinely reachable through its disclosure');return details;
}
async function calculate(page,input=fixture,rules={}){
 await closeBaziTools(page);
 if(await lifeBirth.available(page)){await lifeBirth.setLifeBirth(page,{...lifeBirth.fixture,...input});await go(page,'classicsWisdom');await page.waitForFunction(()=>!!lcGet('bazi').result);await setBaziRules(page,{daySect:String(rules.daySect||2),yunSect:String(rules.yunSect||2)});await page.waitForFunction(v=>lcGet('bazi').result&&lcGet('bazi').normalized.birth.date===v.date&&lcGet('bazi').result.rules.daySect===v.daySect&&lcGet('bazi').result.rules.yunSect===v.yunSect,{date:input.date,daySect:Number(rules.daySect||2),yunSect:Number(rules.yunSect||2)});await ready(page);assert.equal(await page.locator('[data-lc-result=bazi]').count(),1,'Shared birth entry must produce a real chart');return;}

 await go(page,'classicsWisdom');
 const edit=page.locator('[data-lc-action=edit][data-kind=bazi]');
 if(await edit.count()){await edit.click();await ready(page);}
 const form=page.locator('form[data-lc-form=bazi]');
 for(const details of await form.locator('xpath=ancestor::details').all())if(!await details.evaluate(e=>e.open))await details.locator(':scope>summary').click();
 for(const [name,value]of Object.entries(input)){
  const field=form.locator('[name="'+name+'"]');
  if(await field.evaluate(e=>e.tagName==='SELECT'))await field.selectOption(String(value));else await field.fill(String(value));
 }
 await form.locator('[name=daySect]').selectOption(String(rules.daySect||2));await form.locator('[name=yunSect]').selectOption(String(rules.yunSect||2));
 await form.locator('[name=confirmed]').check();await form.locator('button[type=submit]').click();
 await page.waitForFunction(v=>lcGet('bazi').result&&lcGet('bazi').normalized.birth.date===v, input.date);await ready(page);
 assert.equal(await page.locator('[data-lc-result=bazi]').count(),1,'The actual birth form must produce a visible chart');
}
async function view(page){return page.evaluate(()=>lcSnapshot('bazi').view);}
async function selected(page){
 await showBaziView(page,'flow');
 return {
  period:Number(await page.locator('.lcb-periods [aria-pressed=true]').getAttribute('data-index')),
  year:Number(await page.locator('.lcb-years [aria-pressed=true]').getAttribute('data-index')),
  yearLabel:Number(await page.locator('.lcb-years [aria-pressed=true]').getAttribute('data-year')),
  month:Number(await page.locator('.lcb-months [aria-pressed=true]').getAttribute('data-index'))
 };
}
async function assertCurrent2026(page,period,year){
 assert.deepEqual(await selected(page),{period,year,yearLabel:2026,month:8},'The initial view follows the actual 2026 fortune period and the Xu solar-term month, not the first childhood year or Gregorian month number');
 const snapshot=await view(page);assert.equal(snapshot.mode,'current');assert.deepEqual(snapshot.selection,{period,year,month:8});
}
async function openArchive(page,id){await go(page,'lifeReview');await page.locator('.lc-archive [data-lc-action=open][data-id="'+id+'"]').click();await ready(page);assert.equal(await page.evaluate(()=>state.page),'classicsWisdom');await showBaziView(page,'flow');}
async function noOverflow(page){assert(await page.evaluate(()=>{const app=document.getElementById('app');return document.documentElement.scrollWidth<=innerWidth+1&&app.scrollWidth<=app.clientWidth+1;}),'The result must fit the document/app viewport; any comparison scroll belongs inside its own panel');}

async function stage1({page,capture}){
 await calculate(page);
 await assertCurrent2026(page,5,0);
 await openMonthDetail(page);const range=(await page.locator('[data-lcb-month-range]').innerText()).replaceAll('T',' ');
 for(const text of Object.values(expectedTerms))assert(range.includes(text),'The selected solar-term month must show its actual UTC+8 boundary: '+text);
 await capture('M1-默认当前运年流月');await closeBaziTools(page);

 // Hard-coded raw 1.7.7 calendar fixtures, independent of the APP adapter.
 const boundary=await page.evaluate(()=>({
  beforeSpring:lcbCalendarAt(Date.parse('2026-02-03T20:02:07Z')),
  atSpring:lcbCalendarAt(Date.parse('2026-02-03T20:02:08Z')),
  beforeWinter:lcbCalendarAt(Date.parse('2026-11-07T09:52:04Z')),
  atWinter:lcbCalendarAt(Date.parse('2026-11-07T09:52:05Z')),
  interval:lcbMonthInterval(2026,8),
  beforeBirth:lcbCurrentSelection(lcGet('bazi').result,Date.parse('1984-01-01T04:00:00Z')),
  afterRange:lcbCurrentSelection(lcGet('bazi').result,Date.parse('2099-11-05T04:00:00Z'))
 }));
 assert.equal(boundary.beforeSpring.year,2025);assert.equal(boundary.beforeSpring.monthIndex,11);
 assert.equal(boundary.atSpring.year,2026);assert.equal(boundary.atSpring.monthIndex,0);
 assert.equal(boundary.beforeWinter.monthIndex,8);assert.equal(boundary.atWinter.monthIndex,9);
 for(const field of ['start','end'])assert(String(boundary.interval[field]).replaceAll('T',' ').includes(expectedTerms[field]));
 assert.equal(boundary.interval.startJie,'寒露');assert.equal(boundary.interval.endJie,'立冬');
 assert.equal(boundary.beforeBirth.outside,'before-birth');assert.equal(boundary.afterRange.outside,'after-range');

 // A second adult fixture must choose a different current decade/year.
 await calculate(page,{...fixture,date:'2005-12-23',time:'08:37'});await assertCurrent2026(page,2,5);
 await calculate(page);
 await showBaziView(page,'flow');await page.locator('.lcb-periods [data-index="1"]').click();await ready(page);
 await page.locator('.lcb-years [data-index="3"]').click();await ready(page);
 await page.locator('.lcb-months [data-index="5"]').click();await ready(page);
 const manual={period:1,year:3,month:5};
 assert.deepEqual(await view(page),{selection:manual,mode:'manual'});
 assert.deepEqual(await selected(page),{...manual,yearLabel:1989});
 const oldNotes=await page.evaluate(()=>JSON.stringify(mapExplorationRecords()));
 await go(page,'lifeResult');await page.locator('.fl-life [data-action=go][data-to=classicsWisdom]').click();await ready(page);
 assert.deepEqual(await selected(page),{...manual,yearLabel:1989},'Leaving and returning must keep the manually selected view');
 await baziAction(page,'save');await ready(page);
 const record=await page.evaluate(()=>lcRecords().find(r=>r.kind==='bazi'));
 assert(record?.id);assert.deepEqual(record.view,{selection:manual,mode:'manual'});

 await page.clock.setFixedTime(new Date('2027-03-01T04:00:00Z'));
 await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>px.loaded);await openArchive(page,record.id);
 assert.deepEqual(await selected(page),{...manual,yearLabel:1989},'Manual archive views do not silently jump to today on a later visit');
 await page.locator('[data-lcb-action=today]').click();await ready(page);
 assert.deepEqual(await selected(page),{period:5,year:1,yearLabel:2027,month:0});
 assert.equal((await view(page)).mode,'current');
 await baziAction(page,'save');await ready(page);
 assert.equal(await page.evaluate(id=>lcRecords().find(r=>r.id===id).view.mode,record.id),'current');

 await page.clock.setFixedTime(new Date('2028-11-05T04:00:00Z'));
 await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>px.loaded);await openArchive(page,record.id);
 assert.deepEqual(await selected(page),{period:5,year:2,yearLabel:2028,month:8},'A current-mode archive follows the new calendar date when reopened');
 // A pre-M1 archive deliberately lacks view. This mutates only this isolated
 // browser fixture, never any service database or production account.
 await page.evaluate(id=>{const key='ew-life-charts-v1:'+lcScope(),rows=JSON.parse(localStorage.getItem(key));delete rows.find(r=>r.id===id).view;localStorage.setItem(key,JSON.stringify(rows));},record.id);
 await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>px.loaded);await openArchive(page,record.id);
 assert.deepEqual(await selected(page),{period:5,year:2,yearLabel:2028,month:8},'Legacy archives without view default to the current calendar, not childhood');
 assert.equal((await view(page)).mode,'current');
 assert.equal(await page.evaluate(()=>JSON.stringify(mapExplorationRecords())),oldNotes,'Chart selection must not change the existing personal notes');
 assert.equal(await page.evaluate(()=>lcRecords().length),1,'Reopening/updating a view must not silently create duplicate charts');

 await page.setViewportSize({width:350,height:740});await page.evaluate(()=>ewI18n.missing.clear());
 for(const lang of ['zh','zh-Hant','en','bo'])for(const mode of ['day','night']){
  await page.evaluate(v=>{state.lang=v.lang;state.mode=v.mode;render(false);},{lang,mode});await ready(page);await noOverflow(page);
  assert.equal(await page.locator('[data-lcb-action=today]').count(),1);assert.equal(await page.locator('.ew-page-back').count(),1);
  assert.deepEqual(await selected(page),{period:5,year:2,yearLabel:2028,month:8},'Language and appearance changes must not reset the chosen view');
  if(lang==='zh')await capture('M1-350-'+mode);
 }
 assert.deepEqual(await page.evaluate(()=>[...ewI18n.missing]),[],'New visible strings need the existing four-language coverage');
}

// Transcribed from the pinned LunarUtil maps and EightChar natal fixture.
// These expected values never call the APP comparison helper to derive them.
const comparisonColumns=['year','month','day','time','period','flowYear','flowMonth'];
const comparisonFields=['ganZhi','hiddenStems','fiveElements','stemTenGod','branchTenGods','naYin','growthStage','xun','voidBranches'];
const natalComparison={
 year:['乙酉','辛','木金','偏财','比肩','泉中水','临官','甲申','午未'],
 month:['戊子','癸','土水','正印','食神','霹雳火','长生','甲申','午未'],
 day:['辛巳','丙庚戊','金火','日主','正官劫财正印','白蜡金','死','甲戌','申酉'],
 time:['壬辰','戊乙癸','水土','伤官','正印偏财食神','长流水','墓','甲申','午未']
};
const currentComparison={...natalComparison,
 period:['丙戌','戊辛丁','火土','正官','正印比肩七杀','屋上土','冠带','甲申','午未'],
 flowYear:['丙午','丁己','火火','正官','七杀偏印','天河水','病','甲辰','寅卯'],
 flowMonth:['戊戌','戊辛丁','土土','正印','正印比肩七杀','平地木','冠带','甲午','辰巳']
};
const manualComparison={...natalComparison,
 period:['丁亥','壬甲','火水','七杀','伤官正财','屋上土','沐浴','甲申','午未'],
 flowYear:['甲午','丁己','木火','正财','七杀偏印','沙中金','病','甲午','辰巳'],
 flowMonth:['辛未','己丁乙','金土','比肩','偏印七杀偏财','路旁土','衰','甲子','戌亥']
};
function compact(value){return (Array.isArray(value)?value.join(''):String(value??'')).replace(/[\s·、，,/]/g,'');}
async function assertComparison(page,expected){
 const panel=await revealComparison(page);
 const data=await page.evaluate(()=>{const s=lcGet('bazi');return lcbBuildComparison(s.result,lcbResolveSelection(s.result,s));});
 assert.equal(data.dayMaster,'辛');assert.deepEqual(data.columns.map(c=>c.key),comparisonColumns);
 for(const key of comparisonColumns)for(const [index,field]of comparisonFields.entries()){
  const target=expected[key][index],column=data.columns.find(c=>c.key===key);
  assert.equal(compact(column[field]),target,key+'.'+field+' must be calculated relative to the natal Xin day master');
  const cell=panel.locator('[data-lcb-column="'+key+'"][data-field="'+field+'"]');assert.equal(await cell.count(),1);
  assert.equal(compact(await cell.innerText()),target,'Visible '+key+'.'+field+' must agree with the actual chart data');
 }
}
async function revealComparison(page){
 const tools=await openBaziTools(page),panel=tools.locator('details[data-lcb-comparison]');assert.equal(await panel.count(),1,'The real tools sheet retains the full seven-column comparison');
 for(const details of (await panel.locator('xpath=ancestor::details').all()).reverse())if(!await details.evaluate(e=>e.open))await details.locator(':scope>summary').click();
 if(!await panel.evaluate(e=>e.open))await panel.locator(':scope>summary').click();
 assert(await panel.locator('[data-lcb-column][data-field]').first().isVisible(),'Comparison values are genuinely expanded in the tools sheet');
 return panel;
}
async function stage2({page,capture}){
 await calculate(page,{...fixture,name:'QA_BAZI_STAGE_M2',date:'2005-12-23',time:'08:37'});
 await assertComparison(page,currentComparison);await page.locator('[data-lcb-comparison]').scrollIntoViewIfNeeded();await capture('M2-当前七列对照');
 await showBaziView(page,'flow');await page.locator('.lcb-periods [data-index="1"]').click();await ready(page);
 await page.locator('.lcb-years [data-index="3"]').click();await ready(page);
 await page.locator('.lcb-months [data-index="5"]').click();await ready(page);
 await assertComparison(page,manualComparison);
 assert.equal(compact(await page.locator('[data-lcb-comparison] [data-lcb-column=flowMonth][data-field=stemTenGod]').innerText()),'比肩','A selected flow-month Xin stem is a peer, not a second natal day master');
 await page.setViewportSize({width:350,height:740});await noOverflow(page);
 const scrolling=await page.locator('[data-lcb-comparison]').evaluate(panel=>[panel,...panel.querySelectorAll('*')].filter(e=>/(auto|scroll)/.test(getComputedStyle(e).overflowX)&&e.scrollWidth>e.clientWidth+1).map(e=>({width:e.clientWidth,scroll:e.scrollWidth})));
 assert(scrolling.length>0,'Seven comparison columns scroll inside a local panel at 350px');
 await page.evaluate(()=>ewI18n.missing.clear());
 for(const lang of ['zh','zh-Hant','en','bo'])for(const mode of ['day','night']){
  await page.evaluate(v=>{state.lang=v.lang;state.mode=v.mode;render(false);},{lang,mode});await ready(page);await noOverflow(page);
  assert.deepEqual(await selected(page),{period:1,year:3,yearLabel:2014,month:5});
  if(lang==='zh'){
   await assertComparison(page,manualComparison);await page.locator('[data-lcb-comparison]').scrollIntoViewIfNeeded();
   await page.locator('[data-lcb-comparison]').evaluate(panel=>{const e=[panel,...panel.querySelectorAll('*')].find(e=>/(auto|scroll)/.test(getComputedStyle(e).overflowX)&&e.scrollWidth>e.clientWidth+1);if(e)e.scrollLeft=0;});
   await capture('M2-350-'+mode);
   await page.locator('[data-lcb-comparison]').evaluate(panel=>{const e=[panel,...panel.querySelectorAll('*')].find(e=>/(auto|scroll)/.test(getComputedStyle(e).overflowX)&&e.scrollWidth>e.clientWidth+1);if(e)e.scrollLeft=e.scrollWidth;});
   await capture('M2-350-'+mode+'-运年流月侧');
  }
 }
 assert.deepEqual(await page.evaluate(()=>[...ewI18n.missing]),[]);
 await closeBaziTools(page);await page.evaluate(()=>{state.lang='zh';state.mode='night';render(false);});
 await calculate(page,{...fixture,name:'QA_BAZI_STAGE_M2 before fortune',date:'2026-11-04',time:'12:00'});
 const before=await page.evaluate(()=>{const s=lcGet('bazi'),selection=lcbResolveSelection(s.result,s);return {selection,comparison:lcbBuildComparison(s.result,selection)};});
 assert(before.selection.beforeStart,'The synthetic baby fixture is before its precise first fortune-start time');
 assert(!before.comparison.columns.find(c=>c.key==='period')?.ganZhi,'A current view before the first fortune start must not fabricate a decade stem–branch');
 await revealComparison(page);
 const periodCell=page.locator('[data-lcb-comparison] [data-lcb-column=period][data-field=ganZhi]');
 assert(!/[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]/.test(await periodCell.innerText()),'The visible pre-fortune column must also remain empty/unavailable');
 await showBaziView(page,'flow');await page.locator('.lcb-periods [data-index="1"]').click();await ready(page);
 await revealComparison(page);
 const future=await page.evaluate(()=>{const s=lcGet('bazi');return {expected:s.result.periods[1].ganZhi,view:lcSnapshot('bazi').view,comparison:lcbBuildComparison(s.result,lcbResolveSelection(s.result,s))};});
 assert.equal(future.view.mode,'manual');assert(future.expected);
 assert.equal(future.comparison.columns.find(c=>c.key==='period').ganZhi,future.expected,'Manual inspection of a future decade is allowed even before the first fortune start');
 assert.equal(compact(await periodCell.innerText()),future.expected);
}

async function openMonthDetail(page){
 await showBaziView(page,'flow');await openBaziTools(page);const detail=page.locator('#sheet[open] details.lcb-month-detail');assert.equal(await detail.count(),1);
 if(!await detail.evaluate(el=>el.open)){await detail.locator(':scope>summary').click();await ready(page);}
 assert(await detail.locator('[data-lcb-selected-month]').isVisible());return detail;
}
async function assertBaziBoard(page,expected,month=false){
 const keys=comparisonColumns.slice(0,month?7:6),board=page.locator('.lcb-board');
 assert.equal(await board.count(),1);await baziBoardDetails(page);assert.deepEqual(await board.locator('[data-lcb-heading]').evaluateAll(es=>es.map(e=>e.dataset.lcbHeading)),keys);
 assert.equal(await board.locator('td[data-lcb-board-column][data-field]').count(),keys.length*7);
 for(const key of keys){const values=expected[key],cell=field=>board.locator('[data-lcb-board-column="'+key+'"][data-field="'+field+'"]');
  assert.equal(compact(await cell('stem').innerText()),values[0][0]);assert.equal(compact(await cell('branch').innerText()),values[0][1]);
  assert.equal(compact(await cell('hiddenStems').locator('.lcb-hidden-pair>.lcb-element').allTextContents()),values[1]);
  for(const [field,index] of [['growthStage',6],['naYin',5],['voidBranches',8]])assert.equal(compact(await cell(field).innerText()),values[index],'Board '+key+'.'+field+' retains the actual value');
  if(key!=='day')assert.equal(compact(await cell('stemTenGod').innerText()),values[3]);
  else assert(await cell('stemTenGod').locator('[data-lcb-glossary=dayMaster]').count()>0,'The natal day-master label remains explainable');
 }
}
async function stage3({page,capture}){
 await calculate(page,{...fixture,name:'QA_BAZI_STAGE_M3',date:'2005-12-23',time:'08:37'});assert.equal(await page.locator('.lcb-view-tabs [aria-selected=true]').getAttribute('data-view'),'flow');assert.deepEqual(await page.locator('.lcb-view-tabs [data-view]').evaluateAll(es=>es.map(e=>e.dataset.view)),['archive','flow','stars']);const referenceLayout=await baziReferenceLayout(page);assert.equal(await page.locator('#lcb-board-extra').evaluate(el=>el.hidden),!referenceLayout,referenceLayout?'Reference board exposes every detailed row by default':'Accepted compact board folds the extra fields');assert.equal(await page.locator('.lcb-board td[data-lcb-board-column][data-field]:visible').count(),referenceLayout?42:18);await assertBaziBoard(page,currentComparison);await page.locator('[data-lcb-action=flow-month]').click();await ready(page);await assertBaziBoard(page,currentComparison,true);await page.locator('[data-lcb-action=flow-month]').click();await ready(page);await assertBaziBoard(page,currentComparison);await baziBoardDetails(page,false);await showBaziView(page,'archive');
 assert.equal((await page.locator('.lcb-page .px-top h1').innerText()).trim(),'八字排盘');assert.equal(await page.locator('[data-lcb-action=view][data-view=relations],[data-lcb-view-panel=relations],[data-lcb-relation],.lcb-relations').count(),0,'Removed relation UI is absent rather than hidden');
 const detail=page.locator('details[data-lcb-birth-detail]');assert.equal(await detail.count(),1);assert.equal(await detail.evaluate(e=>e.open),false);
 assert.equal(await detail.locator('.lc-normalized').isVisible(),false,'Repeated UTC conversion details are available behind the initially closed birth detail');
 await detail.locator(':scope>summary').click();
 const birthText=await detail.innerText();for(const text of ['QA_BAZI_STAGE_M3','2005-12-23 08:37'])assert(birthText.includes(text),'Birth summary retains '+text);assert(!/Asia\/Shanghai|Etc\/GMT|UTC|纬度|经度/.test(birthText),'Removed regional technical details do not reappear in the birth summary');assert.equal(await page.evaluate(()=>lcGet('bazi').normalized.utc),'2005-12-23T00:37:00.000Z','Internal exact UTC remains available for recalculation');
 await detail.locator(':scope>summary').click();
 assert.equal(await page.locator('details[data-lcb-comparison]').count(),0,'Archive does not stack the complete relation table below the birth details');
 await openBaziTools(page);assert.equal(await page.locator('#sheet[open] details[data-lcb-comparison]').evaluate(e=>e.open),false,'The tools sheet initially folds the complete seven-column record');
 await page.locator('details[data-lcb-comparison]>summary').click();assert.equal(await page.locator('details[data-lcb-comparison]').evaluate(e=>e.open),true);
 await page.locator('details[data-lcb-comparison]>summary').click();assert.equal(await page.locator('details[data-lcb-comparison]').evaluate(e=>e.open),false,'The complete comparison remains actually collapsible');
 await showBaziView(page,'archive');assert.equal(await page.locator('details[data-lcb-natal-details]').evaluate(e=>e.open),false,'The separate complete natal record is initially folded');await openNatalDetails(page);
 const native=page.locator('.lcb-pillars');
 for(const field of ['ganZhi','stemTenGod','fiveElements'])assert.equal(await native.locator('[data-pillar=year][data-field="'+field+'"]').isVisible(),true);
 assert.equal(await native.locator('[data-pillar=year][data-field=hiddenStems]').isVisible(),false);
 await page.locator('[data-lcb-action=details]').click();await ready(page);await openNatalDetails(page);
 assert.equal(await native.locator('[data-pillar=year][data-field=hiddenStems]').isVisible(),true);
 for(const key of ['year','month','day','time'])for(const [index,field]of comparisonFields.entries())assert.equal(compact(await native.locator('[data-pillar="'+key+'"][data-field="'+field+'"]').innerText()),natalComparison[key][index],'Expanded natal '+key+'.'+field+' retains the real calculated value');
 await page.locator('[data-lcb-action=details]').click();await ready(page);await openNatalDetails(page);
 assert.equal(await native.locator('[data-pillar=year][data-field=hiddenStems]').isVisible(),false);
 await showBaziView(page,'flow');await page.locator('.lcb-periods [data-index="1"]').click();await ready(page);await page.locator('.lcb-years [data-index="3"]').click();await ready(page);await page.locator('.lcb-months [data-index="5"]').click();await ready(page);
 const manualView=await view(page);
 await openMonthDetail(page);const selectedTiming=await page.locator('[data-lcb-time-panel]').innerText();assert(selectedTiming.includes('小暑')&&selectedTiming.includes('立秋'),'The manual year/month panel must describe the selected Wei month, not the current Xu-month boundaries');await closeBaziTools(page);
 await openBaziTools(page);const overview=page.locator('#sheet[open] [data-lcb-overview]');assert.equal(await overview.locator('[data-lcb-overview-column]').count(),3);
 for(const key of ['period','flowYear','flowMonth'])assert((await overview.locator('[data-lcb-overview-column="'+key+'"]').innerText()).includes(manualComparison[key][0]),'The compact '+key+' card follows the manually selected chart');
 await revealComparison(page);await assertComparison(page,manualComparison);await page.locator('details[data-lcb-comparison]>summary').click();
 assert.deepEqual(await view(page),manualView,'Opening and folding the detailed comparison does not reset the selected view');
 const toolsComparison=await revealComparison(page);await toolsComparison.locator('[data-lcb-glossary=hiddenStems]').first().click();assert.equal(await page.locator('dialog[open]').count(),1,'The glossary replaces tools without nesting dialogs');assert.equal(await page.locator('#sheet[open] [data-lcb-glossary-entry=hiddenStems]').count(),1);assert.equal(await page.locator('#sheet[open] .lcb-tools-panel').count(),0);
 await page.locator('#sheet[open] [data-lcb-action=tools-return]').click();const returned=page.locator('#sheet[open] .lcb-tools-panel details[data-lcb-comparison]');assert(await returned.evaluate(e=>e.open),'Returning from the glossary restores the actual open comparison');assert.equal(await returned.locator('[data-lcb-column][data-field]').count(),63);assert(await returned.locator('[data-lcb-column][data-field]').first().isVisible());assert.deepEqual(await view(page),manualView);
 await returned.locator('[data-lcb-glossary=hiddenStems]').first().click();await page.locator('#sheet[open] .close-sheet').click();await page.waitForFunction(()=>!document.querySelector('#sheet[open]'));assert.equal(await page.evaluate(()=>document.activeElement?.dataset.lcbAction),'tools','Closing a glossary opened from tools returns to its live tools trigger');assert.deepEqual(await view(page),manualView,'The tools/glossary round trip preserves the selected periods');
 await openNatalDetails(page);await page.locator('[data-lcb-action=details]').click();await ready(page);await openNatalDetails(page);
 const glossaryKeys=['dayMaster','ganZhi','hiddenStems','fiveElements','stemTenGod','branchTenGods','naYin','growthStage','xun','voidBranches'];
 for(const key of glossaryKeys)assert(await page.locator('.lcb-natal [data-lcb-glossary="'+key+'"]').count()>0,'The natal view exposes the '+key+' explanation');
 async function explain(trigger,key,semantic){
  await trigger.click();const dialog=page.locator('dialog[open]');assert.equal(await dialog.count(),1);const text=await dialog.innerText();assert(text.length>45,'An actual explanation should replace a name-only popup');
  if(semantic)await semantic(text,dialog);
  await dialog.locator('.close-sheet').click();await page.waitForFunction(()=>!document.querySelector('dialog[open]'));
  await page.waitForFunction(e=>document.activeElement===e,await trigger.elementHandle(),{timeout:1200});
  assert(await trigger.evaluate(e=>document.activeElement===e),'Closing the glossary returns focus to the original term');
  assert.deepEqual(await view(page),manualView,'Explaining '+key+' must not reset the chosen fortune period, year or month');
 }
 await explain(page.locator('.lcb-natal [data-lcb-glossary=dayMaster]').first(),'dayMaster',text=>{assert(text.includes('日柱')&&text.includes('天干'),'Day master is explained as the natal day pillar stem');});
 await explain(page.locator('.lcb-natal [data-lcb-glossary=hiddenStems]').first(),'hiddenStems',text=>{assert(text.includes('地支')&&text.includes('天干'),'Hidden stems describe stems associated with a branch');});
 await explain(page.locator('.lcb-natal [data-lcb-glossary=stemTenGod]').first(),'stemTenGod',async(text,dialog)=>{
  assert(text.includes('日主')&&text.includes('阴阳')&&text.includes('生克'),'Ten gods are relative to the natal day master through element relationships and polarity');
  assert.equal(await dialog.locator('.lcb-glossary-related details').count(),10,'All ten relationship definitions remain accessible inside the original explanation');
  const yin=dialog.locator('.lcb-glossary-related details').filter({has:page.locator('summary',{hasText:'正印'})});await yin.locator('summary').click();
  assert((await yin.innerText()).includes('相反'));assert.equal(await page.locator('dialog[open]').count(),1,'Expanding related terms must not create nested sheets');
 });
 await explain(page.locator('.lcb-natal [data-lcb-glossary=voidBranches]').first(),'voidBranches',text=>{assert(text.includes('旬')&&text.includes('地支'),'Void branches are defined through the ten-day cycle');});
 const print=page.locator('.lcb-pillars [data-pillar=month][data-field=stemTenGod] [data-lcb-glossary]');assert.equal(compact(await print.innerText()),'正印');
 await explain(print,'正印',text=>{assert(/生我|生助日主|生日主/.test(text)&&/不同|相异|异性|相反/.test(text),'The Zheng Yin value explains generating the day master with opposite polarity');});
 await page.locator('[data-lcb-action=details]').click();await ready(page);await openNatalDetails(page);

 await page.evaluate(()=>ewI18n.missing.clear());
 for(const width of [350,390,1280])for(const lang of ['zh','zh-Hant','en','bo'])for(const mode of ['day','night']){
  await page.setViewportSize({width,height:width===350?740:900});await page.evaluate(v=>{state.lang=v.lang;state.mode=v.mode;render(false);document.getElementById('app').scrollTop=0;},{lang,mode});await ready(page);await showBaziView(page,'flow');await page.evaluate(()=>{document.getElementById('app').scrollTop=0;});await assertBaziBoard(page,manualComparison);await baziBoardDetails(page,referenceLayout);const primary=await page.locator('.lcb-board td[data-field=stem],.lcb-board td[data-field=branch]').evaluateAll(es=>{const area=document.getElementById('app').getBoundingClientRect();return es.every(el=>{const r=el.getBoundingClientRect();return r.top>=area.top&&r.bottom<=area.bottom;});});await openNatalDetails(page);await native.scrollIntoViewIfNeeded();await noOverflow(page);
  const cells=[];
  for(const key of ['year','month','day','time']){
   const cell=native.locator('[data-pillar="'+key+'"][data-field=ganZhi]');const box=await cell.boundingBox();assert(box);cells.push(box);
   assert.equal(compact(await cell.innerText()),natalComparison[key][0]);
   assert(await cell.evaluate(e=>[e,...e.querySelectorAll('*')].some(n=>getComputedStyle(n).writingMode.startsWith('vertical')&&n.textContent.trim()===e.textContent.trim())),'Each pillar displays the same deliberate vertical stem–branch layout');
  }
  assert(Math.max(...cells.map(c=>c.width))-Math.min(...cells.map(c=>c.width))<=1.1,'All four natal columns have equal widths');
  const highlight=await native.evaluate(table=>{const day=table.querySelector('[data-pillar=day][data-field=ganZhi]'),year=table.querySelector('[data-pillar=year][data-field=ganZhi]'),a=getComputedStyle(day),b=getComputedStyle(year);return day.classList.contains('is-day-master')&&(a.backgroundColor!==b.backgroundColor||a.boxShadow!==b.boxShadow);});assert(highlight,'The natal day pillar is visibly distinguished, not only named in the DOM');
  if(lang==='zh'){
   const appBox=await page.locator('#app').boundingBox();assert(primary,'All six upper-table stems and branches are visible in the default flow screen');assert(cells.every(c=>c.y>=appBox.y&&c.y+c.height<=appBox.y+appBox.height),'The opened four-pillar record is actually readable after scrolling to it');
   const title=await page.locator('.lcb-page .px-top h1').boundingBox();assert(title.height<45,'The short Chinese title fits a single line');
   if(width===350)await capture('M3-350-'+mode+'-本命首屏');
  }
  assert.deepEqual(await view(page),manualView,'Responsive, language and theme changes preserve the selected manual view');
  const trigger=page.locator('.lcb-natal [data-lcb-glossary=dayMaster]').first();await explain(trigger,'dayMaster');
 }
 assert.deepEqual(await page.evaluate(()=>[...ewI18n.missing]),[],'The compact UI and new glossary need all four language entries');
}

const auxiliaryFixture={
 taiYuan:{ganZhi:'己卯',naYin:'城头土'},taiXi:{ganZhi:'丙申',naYin:'山下火'},
 mingGong:{ganZhi:'己丑',naYin:'霹雳火'},shenGong:{ganZhi:'辛巳',naYin:'白蜡金'}
};
async function openExtra(page){await showBaziView(page,'archive');const extra=page.locator('details[data-lcb-extra]');assert.equal(await extra.count(),1);if(!await extra.evaluate(e=>e.open))await extra.locator(':scope>summary').click();return extra;}
async function assertAuxiliary(page,expected=auxiliaryFixture){
 const extra=await openExtra(page),actual=await page.evaluate(()=>lcGet('bazi').result.auxiliary);
 for(const [key,values]of Object.entries(expected))for(const field of ['ganZhi','naYin']){
  assert.equal(actual[key][field],values[field],'Actual '+key+'.'+field+' matches the pinned raw calendar fixture');
  assert.equal(compact(await extra.locator('[data-lcb-aux="'+key+'"] [data-field="'+field+'"]').innerText()),values[field],'Visible '+key+'.'+field+' is actually calculated');
 }
}
async function assertSmallFortune(page,year,expected){
 const extra=await openExtra(page),row=extra.locator('[data-lcb-small-year="'+year+'"]');assert.equal(await row.count(),1);
 for(const [field,value]of Object.entries(expected)){
  const text=compact(await row.locator('[data-field="'+field+'"]').innerText());
  if(field==='age')assert.equal(Number(text.match(/\d+/)?.[0]),value,'Small fortune '+year+' displays the actual nominal age');
  else assert.equal(text, String(value),'Small fortune '+year+'.'+field+' uses its own calculated sequence');
 }
 assert.equal(await row.getAttribute('aria-current'),'true','The small-fortune row follows the selected flow year');
}
async function stage4({page,capture}){
 const birth={...fixture,name:'QA_BAZI_STAGE_M4',date:'2005-12-23',time:'08:37'};
 await calculate(page,birth);await showBaziView(page,'archive');assert.equal(await page.locator('details[data-lcb-extra]').evaluate(e=>e.open),false,'Auxiliary symbols and small fortunes are initially folded in the actual archive view');
 await assertAuxiliary(page);
 await assertSmallFortune(page,2026,{age:22,ganZhi:'庚午',xun:'甲子',voidBranches:'戌亥'});
 assert.equal(await page.locator('[data-lcb-small-year]').count(),10);
 const small2026=await page.locator('[data-lcb-small-year="2026"] [data-field=ganZhi]').innerText();await showBaziView(page,'flow');const flow2026=(await page.locator('.lcb-years [data-year="2026"] .lcb-rail-symbols>span>.lcb-element').allTextContents()).join('');assert.notEqual(small2026,flow2026,'Small fortune must remain distinct from the flow-year stem–branch');await openExtra(page);
 await page.locator('[data-lcb-aux=taiYuan]').scrollIntoViewIfNeeded();await capture('M4-辅助四项');
 await showBaziView(page,'flow');await page.locator('.lcb-periods [data-index="1"]').click();await ready(page);await page.locator('.lcb-years [data-index="3"]').click();await ready(page);
 await assertSmallFortune(page,2014,{age:10,ganZhi:'壬午',xun:'甲戌',voidBranches:'申酉'});
 assert.equal(await page.locator('[data-lcb-small-year]').count(),10);assert.equal(await page.locator('[data-lcb-small-year="2026"]').count(),0,'Changing the major period replaces its small-fortune list');
 await page.locator('[data-lcb-small-year="2014"]').scrollIntoViewIfNeeded();await capture('M4-小运跟随所选2014年');
 await showBaziView(page,'flow');await page.locator('.lcb-periods [data-index="0"]').click();await ready(page);await openExtra(page);
 assert.equal(await page.locator('[data-lcb-small-year]').count(),6,'The pre-fortune segment contains its actual six listed years, not a fabricated ten');
 assert.equal(compact(await page.locator('[data-lcb-small-year="2005"] [data-field=ganZhi]').innerText()),'辛卯');
 assert.equal(compact(await page.locator('[data-lcb-small-year="2010"] [data-field=ganZhi]').innerText()),'丙戌');
 await calculate(page,{...birth,sex:'female'});await assertAuxiliary(page);await assertSmallFortune(page,2026,{age:22,ganZhi:'甲寅',xun:'甲寅',voidBranches:'子丑'});
 assert.equal(await page.evaluate(()=>lcGet('bazi').result.startFortune.forward),true,'Female and male synthetic cases exercise both actual small-fortune directions');
 await calculate(page,{...birth,date:'1988-02-15',time:'23:30'},{daySect:2});
 await assertAuxiliary(page,{taiYuan:{ganZhi:'乙巳',naYin:'覆灯火'},taiXi:{ganZhi:'乙丑',naYin:'海中金'},mingGong:{ganZhi:'乙卯',naYin:'大溪水'},shenGong:{ganZhi:'乙卯',naYin:'大溪水'}});
 await calculate(page,{...birth,date:'1988-02-15',time:'23:30'},{daySect:1});
 await assertAuxiliary(page,{taiYuan:{ganZhi:'乙巳',naYin:'覆灯火'},taiXi:{ganZhi:'丙子',naYin:'涧下水'},mingGong:{ganZhi:'乙卯',naYin:'大溪水'},shenGong:{ganZhi:'乙卯',naYin:'大溪水'}});

 await calculate(page,birth);await showBaziView(page,'flow');await page.locator('.lcb-periods [data-index="1"]').click();await ready(page);await page.locator('.lcb-years [data-index="3"]').click();await ready(page);
 await baziAction(page,'save');const saved=await page.evaluate(()=>lcRecords().find(r=>r.kind==='bazi'));assert(saved?.id&&saved.result.auxiliary&&saved.result.periods[1].smallFortunes.length===10);
 // Emulate the data shape of a valid pre-M4 archive. Its inputs/UTC/rules are
 // intact; only the cached newly introduced results are absent.
 await page.evaluate(id=>{const key='ew-life-charts-v1:'+lcScope(),rows=JSON.parse(localStorage.getItem(key)),row=rows.find(r=>r.id===id);delete row.result.auxiliary;for(const period of row.result.periods)delete period.smallFortunes;localStorage.setItem(key,JSON.stringify(rows));},saved.id);
 await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>px.loaded);await openArchive(page,saved.id);await assertAuxiliary(page);await assertSmallFortune(page,2014,{age:10,ganZhi:'壬午',xun:'甲戌',voidBranches:'申酉'});
 assert.equal(await page.evaluate(()=>lcRecords().length),1,'Restoring newly computed fields must not create duplicate archive records');
 const snapshot=await page.evaluate(()=>lcSnapshot('bazi'));assert(snapshot.result.auxiliary&&snapshot.result.periods.every(p=>Array.isArray(p.smallFortunes)),'The exact snapshot used by local JSON export carries the new calculated fields and sequences');
 const manualView=await view(page);
 for(const key of ['taiYuan','taiXi','mingGong','shenGong','smallFortune']){
  const selector=key==='smallFortune'?'details[data-lcb-extra] [data-lcb-glossary=smallFortune],details[data-lcb-extra] [data-lcb-glossary=xiaoYun]':'details[data-lcb-extra] [data-lcb-glossary="'+key+'"]';
  const trigger=page.locator(selector).first();assert(await trigger.count()>0);await trigger.click();const dialog=page.locator('dialog[open]');const text=await dialog.innerText();assert(text.length>45);
  if(key==='mingGong')assert(text.includes('紫微')&&text.includes('十二宫'),'Ba Zi Ming Gong is explained separately from the Zi Wei twelve-palace system');
  if(key==='smallFortune')assert(text.includes('时柱')&&text.includes('流年'),'Small fortune is explained as an hour-pillar-derived sequence distinct from the flow year');
  await dialog.locator('.close-sheet').click();await page.waitForFunction(e=>document.activeElement===e,await trigger.elementHandle(),{timeout:1200});assert.deepEqual(await view(page),manualView);
 }
 await page.evaluate(()=>ewI18n.missing.clear());
 for(const width of [350,390,1280])for(const lang of ['zh','zh-Hant','en','bo'])for(const mode of ['day','night']){
  await page.setViewportSize({width,height:width===350?740:900});await page.evaluate(v=>{state.lang=v.lang;state.mode=v.mode;render(false);},{lang,mode});await ready(page);await openExtra(page);await noOverflow(page);assert.deepEqual(await view(page),manualView);
  assert.equal(await page.locator('[data-lcb-aux]').count(),4);assert.equal(await page.locator('[data-lcb-small-year="2014"][aria-current=true]').count(),1);
  if(lang==='zh'&&width===350){await assertAuxiliary(page);await page.locator('[data-lcb-aux=taiYuan]').scrollIntoViewIfNeeded();await capture('M4-350-'+mode+'-辅助项');await page.locator('[data-lcb-small-year="2014"]').scrollIntoViewIfNeeded();await capture('M4-350-'+mode+'-小运');}
 }
 assert.deepEqual(await page.evaluate(()=>[...ewI18n.missing]),[],'New auxiliary/small-fortune labels need four-language entries');
 await page.evaluate(()=>{state.lang='zh';state.mode='night';render(false);});
 await calculate(page,{...birth,date:'1990-01-05',time:'12:00',sex:'female'});await openExtra(page);
 assert.equal(await page.evaluate(()=>lcGet('bazi').result.periods[0].smallFortunes.length),0);
 const empty=page.locator('[data-lcb-small-empty][data-period="0"]');assert.equal(await empty.count(),1);assert((await empty.innerText()).includes('出生当年起运'),'A same-year fortune start explains its empty pre-fortune segment without inventing years');
 await showBaziView(page,'flow');assert.equal(await page.locator('.lcb-periods [data-index="0"]').count(),0,'An empty pre-fortune segment is not exposed as an invalid selectable year');await openExtra(page);
 assert.equal(await page.locator('[data-lcb-small-year]').count(),10,'The selected nonempty period still has its actual small fortunes beside the historical empty-state note');
 assert.equal(await page.locator('[data-lcb-small-year="2026"][aria-current=true]').count(),1);
 await empty.scrollIntoViewIfNeeded();await capture('M4-同年起运空期0附注');
}

async function runBaziStages({browser,base,step,stage=1,errors=[],prefix='',captureDirectory=__dirname}){
 assert(Number.isInteger(stage)&&stage>=1&&stage<=4,'Implemented Ba Zi acceptance stage must currently be from 1 to 4');
 assert(!String(base).startsWith('https:'),'This full acceptance writes isolated browser fixtures and must not target production');
 const captures=[];
 for(let current=1;current<=stage;current++)await step(stageNames[current],async()=>{
  const context=await browser.newContext({viewport:{width:390,height:844},locale:'zh-CN',timezoneId:'America/New_York',reducedMotion:'reduce'});
  const page=await context.newPage(),ownErrors=[],birthWrites=[];
  page.on('pageerror',e=>{ownErrors.push(e.message);errors.push('bazi-stage-'+current+': '+e.message);});
  page.on('request',r=>{if(r.method()!=='GET'&&(r.postData()||'').includes('QA_BAZI_STAGE_'))birthWrites.push({url:r.url(),method:r.method()});});
  const capture=async name=>{const file=prefix+'八字体验-'+name+'.png';await page.screenshot({path:path.join(captureDirectory,file),fullPage:true});captures.push(file);};
  try{
   await page.clock.setFixedTime(new Date(fixedNow));
   await page.goto(base+'/experience?lang=zh-Hans',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>typeof px!=='undefined'&&px.loaded);
   await ({1:stage1,2:stage2,3:stage3,4:stage4}[current])({page,capture});assert.deepEqual(ownErrors,[]);assert.deepEqual(birthWrites,[],'Synthetic birth details must remain in the browser');
  }catch(error){await capture('M'+current+'-失败').catch(()=>{});throw error;}finally{await context.close();}
 });
 return {stage,captures};
}

async function standalone(){
 const stage=Number(process.argv.find(x=>x.startsWith('--bazi-stage='))?.slice('--bazi-stage='.length)||1);
 const explicit=process.argv.find(x=>x.startsWith('--base='))?.slice(7),python=process.env.EW_PYTHON||path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
 const db=path.join(__dirname,'八字体验验收隔离.sqlite3'),reportFile=path.join(__dirname,'八字体验逐模块验收.json'),results=[],errors=[];
 let server,browser,base=explicit,evidence;
 const clean=()=>{for(const suffix of ['','-wal','-shm']){const target=db+suffix;assert.equal(path.dirname(target),__dirname);if(fs.existsSync(target))fs.unlinkSync(target);}};
 const step=async(name,fn)=>{try{await fn();results.push({name,pass:true});console.log('PASS '+name);}catch(error){results.push({name,pass:false,error:error.stack});console.log('FAIL '+name+': '+error.message);}};
 try{
  assert(!explicit||explicit.startsWith('http://127.0.0.1:'),'An explicit target must be an isolated localhost service');
  if(!explicit){clean();server=spawn(python,['-B',path.join(source,'backend/server.py'),'--port','0','--db',db,'--web-root',web],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});base=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error('Local Ba Zi test service did not start')),15000);server.stdout.on('data',chunk=>{output+=chunk.toString();const match=output.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/);if(match){clearTimeout(timer);resolve(match[1]);}});server.stderr.on('data',chunk=>output+=chunk.toString());server.once('exit',code=>{clearTimeout(timer);reject(Error('Local test service exited '+code+': '+output));});});}
  const {chromium}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
  browser=await chromium.launch({headless:true});evidence=await runBaziStages({browser,base,step,stage,errors});
 }catch(error){results.push({name:'八字分模块验收环境',pass:false,error:error.stack});console.log('FATAL '+error.message);}
 finally{
  if(browser)await browser.close();if(server&&server.exitCode===null){const stopped=new Promise(resolve=>server.once('exit',resolve));server.kill();await stopped;}if(!explicit)clean();
  const report={module:'改动文档M4-八字真实数据与三页对齐',at:new Date().toISOString(),stage,base,scope:'Synthetic exact-birth browser flows and private local chart views; no real personal data, AI interpretation or physical-device claims',pass:results.length>0&&results.every(x=>x.pass),passed:results.filter(x=>x.pass).length,failed:results.filter(x=>!x.pass).length,results,errors,...evidence,buildSha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(web,'东方智慧-首页体验R4.html'))).digest('hex')};
  let runs=[];if(fs.existsSync(reportFile))try{const old=JSON.parse(fs.readFileSync(reportFile));runs=old.runs||[old];}catch{}runs.push(report);fs.writeFileSync(reportFile,JSON.stringify({latest:report,runs:runs.slice(-30)},null,2));console.log(JSON.stringify({pass:report.pass,passed:report.passed,failed:report.failed,stage,report:reportFile}));process.exitCode=report.pass?0:1;
 }
}
module.exports={runBaziStages};
if(require.main===module)standalone();
