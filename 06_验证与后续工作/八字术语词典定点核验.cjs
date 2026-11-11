// Semantic checks against all 100 day/target-stem relations; browser sheet/focus checks run separately.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),file=path.join(root,'04_研发源码/app/r4/bazi-glossary.js'),source=fs.readFileSync(file,'utf8');
const library=require(path.join(root,'04_研发源码/app/r4/vendor/lunar-1.7.7.js'));
const sheetCalls=[],events=[];let language=1,closed=0;
const context={lcText:(...a)=>a[language],sheet:(...a)=>sheetCalls.push(a),closeSheet:()=>closed++,document:{addEventListener:(...a)=>events.push(a)}};
vm.createContext(context);vm.runInContext(source,context,{filename:'bazi-glossary.js'});
const results=[];function check(name,fn){try{fn();results.push({name,pass:true});console.log('PASS '+name);}catch(error){results.push({name,pass:false,error:error.stack});console.log('FAIL '+name+': '+error.message);}}
const base=['dayMaster','ganZhi','hiddenStems','fiveElements','stemTenGod','branchTenGods','naYin','growthStage','xun','voidBranches'];
const gods=['比肩','劫财','食神','伤官','偏财','正财','七杀','正官','偏印','正印'];
const auxiliary=['taiYuan','taiXi','mingGong','shenGong','smallFortune'];
check('Original twenty M3 entries remain, with exactly five auxiliary M4 entries added',()=>{
 assert.equal(Object.keys(context.lcbGlossaryData).length,25);for(const id of base)assert(context.lcbGlossaryEntry(id));for(const name of gods)assert(context.lcbGlossaryEntry(context.lcbGlossaryGods[name]));for(const id of auxiliary)assert(context.lcbGlossaryEntry(id));
 assert.equal(context.lcbGlossaryEntry('branchTenGod').id,'branchTenGods');assert.equal(context.lcbGlossaryEntry('__proto__'),null);assert.equal(context.lcbGlossaryEntry('unknown'),null);
});
check('All twenty-five entries have English/Chinese/Traditional/Tibetan title and copy slots',()=>{
 for(const id of Object.keys(context.lcbGlossaryData)){
  const row=context.lcbGlossaryData[id];assert.equal(row.title.length,4);assert.equal(row.copy.length,4);
  for(let i=0;i<4;i++){language=i;const e=context.lcbGlossaryEntry(id);assert.equal(e.title,row.title[i]);assert.equal(e.copy,row.copy[i]);assert(e.title.trim());assert(e.copy.trim().length>12);assert(!e.copy.includes('undefined'));}
  assert(/[\u0f00-\u0fff]/.test(row.copy[3]));
 }language=1;
});
check('Definition semantics match all 100 official day-master/target-stem relationships',()=>{
 const stems='甲乙丙丁戊己庚辛壬癸';
 for(let day=0;day<10;day++)for(let target=0;target<10;target++){
  const a=Math.floor(day/2),b=Math.floor(target/2);let relation;
  if(a===b)relation='same';else if((a+1)%5===b)relation='produces';else if((a+2)%5===b)relation='controls';else if((b+1)%5===a)relation='producedBy';else relation='controlledBy';
  const name=library.LunarUtil.SHI_SHEN[stems[day]+stems[target]],entry=context.lcbGlossaryEntry(context.lcbGlossaryGods[name]);assert(entry,stems[day]+stems[target]);
  const text=entry.copy;const patterns={same:/^与日主五行相同/,produces:/^日主五行所生/,controls:/^日主五行所克/,producedBy:/^生日主五行/,controlledBy:/^克日主五行/};assert.match(text,patterns[relation]);assert.match(text,day%2===target%2?/阴阳属性[^。]*相同/:/阴阳属性[^。]*相反/);
 }
});
check('Core definitions distinguish reference, hidden-stem multiplicity and unweighted elements',()=>{
 assert.match(context.lcbGlossaryEntry('dayMaster').copy,/本命日柱的天干/);assert.match(context.lcbGlossaryEntry('hiddenStems').copy,/一至三个藏干/);assert.match(context.lcbGlossaryEntry('hiddenStems').copy,/不提供权重或占比/);assert.match(context.lcbGlossaryEntry('branchTenGods').copy,/顺序与藏干列表一致/);assert.match(context.lcbGlossaryEntry('fiveElements').copy,/不能直接判断旺衰/);
});
check('Potentially misleading stage and void names have explicit calculation boundaries',()=>{
 assert.match(context.lcbGlossaryEntry('growthStage').copy,/不表示现实疾病、生死或寿命/);assert.match(context.lcbGlossaryEntry('voidBranches').copy,/该柱自身所属旬/);assert.match(context.lcbGlossaryEntry('voidBranches').copy,/不自动判定与本命/);assert.match(context.lcbGlossaryEntry('god-qiSha').copy,/不表示现实中的暴力或危险/);assert.match(context.lcbGlossaryEntry('god-jieCai').copy,/不表示现实中会被夺走钱财/);
});
check('Plain-text labels, unknown names and attribute hints are escaped safely',()=>{
 const html=context.lcbTermButton('dayMaster','<img src=x onerror="bad">&\'');assert(!html.includes('<img'));assert(html.includes('&lt;img'));assert(html.includes('&quot;bad&quot;'));assert(html.includes('&amp;&#39;'));assert(html.includes('type="button"'));assert(html.includes('class="lcb-term-button"'));assert(html.includes('data-lcb-glossary="dayMaster"'));
 assert.equal(context.lcbTermButton('unknown','<script>'), '&lt;script&gt;');assert.equal(context.lcbTenGodButtons(['<b>']), '&lt;b&gt;');
});
check('Ten Gods renderer handles scalar/array/day-master without adding extra text to cells',()=>{
 const scalar=context.lcbTenGodButtons('正印'),array=context.lcbTenGodButtons(['正印','偏财']);assert(scalar.includes('data-lcb-glossary="god-zhengYin"'));assert.equal(scalar.replace(/<[^>]*>/g,''),'正印');assert.equal(array.replace(/<[^>]*>/g,''),'正印 · 偏财');assert(context.lcbTenGodButtons('日主').includes('data-lcb-glossary="dayMaster"'));assert.equal(context.lcbTenGodButtons(null),'—');
});
check('Ten Gods overview gives all ten definitions through details without nested sheets',()=>{
 context.lcbOpenGlossary('stemTenGod');const [title,body,actions]=sheetCalls.at(-1);assert.equal(title,'天干十神');assert.equal((body.match(/<details>/g)||[]).length,10);assert(!body.includes('data-lcb-glossary='));assert(body.includes('lcb-glossary-content'));assert(body.includes('data-lcb-glossary-entry="stemTenGod"'));assert(actions.includes('data-action="close-sheet"'));assert(!body.includes('data-lcb-action'));
});
check('The existing sheet close API is reused and unknown entries do not open it',()=>{
 const count=sheetCalls.length;assert.equal(context.lcbOpenGlossary('unknown'),false);assert.equal(sheetCalls.length,count);context.lcbCloseGlossary();assert.equal(closed,1);
});
check('Glossary click routing is independent of chart navigation and does not call render',()=>{
 assert.equal(events.length,1);assert.equal(events[0][0],'click');assert.equal(events[0][2],true);
 let prevented=false,stopped=false,focused=false;const trigger={dataset:{lcbGlossary:'god-zhengYin'},focus:()=>focused=true};events[0][1]({target:{closest:selector=>selector==='[data-lcb-glossary]'?trigger:null},preventDefault:()=>prevented=true,stopImmediatePropagation:()=>stopped=true});
 assert(prevented&&stopped&&focused);assert.equal(sheetCalls.at(-1)[0],'正印');assert(!/\brender\s*\(/.test(source));assert(!/\bfetch\s*\(|localStorage|sessionStorage/.test(source));
});
check('Five auxiliary definitions distinguish formulas from conception, health and annual pillars',()=>{
 assert.match(context.lcbGlossaryEntry('taiYuan').copy,/月干进一位、月支进三位/);assert.match(context.lcbGlossaryEntry('taiYuan').copy,/不是实际受孕日期、孕期记录或健康判断/);
 assert.match(context.lcbGlossaryEntry('taiXi').copy,/五合配对、日支的六合配对/);assert.match(context.lcbGlossaryEntry('taiXi').copy,/不是实际受孕日期/);assert.match(context.lcbGlossaryEntry('taiXi').copy,/不描述胎儿呼吸或健康/);
 assert.equal(context.lcbGlossaryEntry('mingGong').title,'八字命宫');assert.match(context.lcbGlossaryEntry('mingGong').copy,/与紫微斗数的十二宫结构分开/);
 assert.equal(context.lcbGlossaryEntry('shenGong').title,'八字身宫');assert.match(context.lcbGlossaryEntry('shenGong').copy,/不是身体测量或医学结果/);
 assert.match(context.lcbGlossaryEntry('smallFortune').copy,/本命时柱为起点/);assert.match(context.lcbGlossaryEntry('smallFortune').copy,/不同于以当年干支为依据的流年/);
});
check('Each auxiliary term opens the existing sheet with escaped caller text in all four languages',()=>{
 for(let lang=0;lang<4;lang++){language=lang;for(const id of auxiliary){const entry=context.lcbGlossaryEntry(id),button=context.lcbTermButton(id,'<img src=x onerror="bad">');assert(button.includes(`data-lcb-glossary="${id}"`));assert(button.includes('&lt;img'));assert(!button.includes('<img'));assert(context.lcbOpenGlossary(id));const [title,body]=sheetCalls.at(-1);assert.equal(title,context.lcbGlossaryEscape(entry.title));assert(body.includes(context.lcbGlossaryEscape(entry.copy)));assert(body.includes(`data-lcb-glossary-entry="${id}"`));assert(!body.includes('data-lcb-action'));}}language=1;
});
const report={at:new Date().toISOString(),module:'M3 core glossary and M4 auxiliary vocabulary semantic and interaction contracts',pass:results.every(r=>r.pass),passed:results.filter(r=>r.pass).length,failed:results.filter(r=>!r.pass).length,entryCounts:{current:25,m3Historical:20,basic:10,tenGods:10,auxiliary:5},sourceSha256:crypto.createHash('sha256').update(source).digest('hex'),sources:{relationships:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/lunar.js#L4670-L4770',stages:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/lunar.js#L5636-L5733',auxiliary:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/lunar.js#L5734-L5778',smallFortune:'https://github.com/6tail/lunar-javascript/blob/4c45a59f79b856125516f31aefa8295035c16afd/lunar.js#L5884-L5913'},scope:'Checks all original twenty vocabulary entries and 100 stem relationships, plus five auxiliary entries (25 total), safe escaping and isolated sheet routing. Actual browser focus/close state is covered by the separate UI regression. Tibetan wording remains subject to native-language review.',results};
const output=path.join(__dirname,'八字术语词典定点核验.json');let runs=[];if(fs.existsSync(output))try{const old=JSON.parse(fs.readFileSync(output,'utf8'));runs=old.runs||[old];}catch{}runs.push(report);fs.writeFileSync(output,JSON.stringify({latest:report,runs:runs.slice(-20)},null,2));console.log(JSON.stringify({pass:report.pass,passed:report.passed,failed:report.failed,report:output}));process.exitCode=report.pass?0:1;
