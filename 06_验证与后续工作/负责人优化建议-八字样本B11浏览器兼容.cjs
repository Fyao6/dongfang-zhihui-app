// Prepared real browser B11 checks. Run only after explicit integration/build on a fresh owned test service.
// No actual AI response or teacher confirmation is fabricated.
const assert = require('node:assert/strict');
module.exports = async function browserChecks(h) {
  let browser, context, page, user, other, originalId, legacyId, legacyJSON, originalBirth, originalRows, linkedId;
  const ready = async () => page.waitForFunction(() => px.loaded && !pxBootstrapPending && BaziVersionUI.installed);
  const go = async name => page.evaluate(name => navigate(name), name);
  const records = async () => page.evaluate(() => lcRecords());
  async function chartAction(p,kind,name) {
    const selector=kind==='lc'?'[data-lc-action="'+name+'"][data-kind=bazi]':'[data-b11-action="'+name+'"]';
    if(!await p.locator(selector+':visible').count()) {
      await p.locator('[data-lcb-action=tools]').click();
      await p.locator('#sheet[open] .lcb-tools-panel').waitFor({state:'visible'});
    }
    await p.locator(selector+':visible').first().click();
    if(await p.locator('#sheet[open] .lcb-tools-panel').count()) {
      await p.locator('#sheet[open] .close-sheet').click();
      await p.waitForFunction(()=>!document.querySelector('#sheet[open]'));
    }
  }

  const open = async id => {
    await go('lifeReview');
    await page.locator('[data-lc-action="open"][data-kind="bazi"][data-id="' + id + '"]').click();
    await page.waitForFunction(id => lcGet('bazi').b11Readonly && lcGet('bazi').savedId === id, id);
  };
  await h.check('B11真实生辰入口与保存：当前库实际计算、独立版本、原出生四字段不变', async () => {
    user = await h.register('bazi'); other = await h.register('other');
    browser = await h.browserContext(await user.c.storageState()); ({context, page} = browser);
    await page.goto(h.base + '/experience'); await ready(); await go('lifeResult');
    const form = page.locator('#lb-birth-form'); await form.locator('[name=date]').fill('1990-06-15');
    await form.locator('[name=sex]').selectOption('male'); await form.locator('[name=name]').fill('B11 浏览器合成档案');
    await form.locator('[name=time]').fill('23:30'); await form.locator('[type=submit]').click();
    await page.waitForFunction(() => !!lbProfile() && !lbState().editing);
    originalBirth = await page.evaluate(() => localStorage.getItem('ew-life-birth-v1:' + lcScope()));
    await go('classicsWisdom'); await page.locator('[data-lc-result=bazi]').waitFor();
    await page.setViewportSize({width:375,height:740});
    await page.locator('[data-lcb-action=view][data-view=flow]').click();
    await page.evaluate(()=>{document.getElementById('app').scrollTop=0;});
    const firstScreen=await page.locator('.lcb-board td[data-field=stem],.lcb-board td[data-field=branch]').evaluateAll(es=>{
      const area=document.getElementById('app').getBoundingClientRect();
      return {count:es.length,visible:es.every(el=>{const r=el.getBoundingClientRect();return r.top>=area.top&&r.bottom<=area.bottom;})};
    });
    assert.equal(firstScreen.count,8,'Default four natal columns each show a stem and a branch');
    assert.equal(firstScreen.visible,true,'Default fresh 375px flow screen keeps all upper stems and branches visible');
    await page.locator('[data-lcb-action=board-mode]').click();
    await page.evaluate(()=>{document.getElementById('app').scrollTop=0;});
    const fullBoard=await page.locator('.lcb-board td[data-field=stem],.lcb-board td[data-field=branch]').evaluateAll(es=>{const area=document.getElementById('app').getBoundingClientRect();return {count:es.length,visible:es.every(el=>{const r=el.getBoundingClientRect();return r.top>=area.top&&r.bottom<=area.bottom;})};});
    assert.equal(fullBoard.count,14,'Full comparison initially includes the selected month: seven actual columns');
    assert.equal(fullBoard.visible,true,'Seven-column comparison keeps all upper symbols in the first screen');
    await page.locator('[data-lcb-action=flow-month]').click();
    await page.evaluate(()=>{document.getElementById('app').scrollTop=0;});
    const sixColumns=await page.locator('.lcb-board td[data-field=stem],.lcb-board td[data-field=branch]').evaluateAll(es=>{const area=document.getElementById('app').getBoundingClientRect();return {count:es.length,visible:es.every(el=>{const r=el.getBoundingClientRect();return r.top>=area.top&&r.bottom<=area.bottom;})};});
    assert.equal(sixColumns.count,12,'Explicitly hiding the month produces six actual columns');
    assert.equal(sixColumns.visible,true,'Six-column comparison also keeps all upper symbols in the first screen');
    assert.equal(await page.locator('[data-b11-readonly-notice]').count(),0,'Fresh calculation has no historical banner above the chart');
    assert.equal(await page.locator('[data-b11-manifest]').getAttribute('open'),null,'Version information starts collapsed');
    const belowBoard=await page.evaluate(()=>document.querySelector('[data-b11-manifest]').getBoundingClientRect().top>=document.querySelector('.lcb-board').getBoundingClientRect().bottom);
    assert.equal(belowBoard,true,'Real expandable version information is placed after the chart');
    await page.locator('[data-b11-manifest] summary').click();
    await page.locator('[data-b11-teacher-confirmed=false]').waitFor({state:'visible'});
    await page.locator('[data-b11-manifest] summary').click();
    await page.evaluate(()=>{document.getElementById('app').scrollTop=0;});
    await h.capture(page,'375首屏干支与折叠版本入口');
    await page.setViewportSize({width:430,height:844});
    await chartAction(page,'lc','save');
    await page.waitForFunction(() => !!lcGet('bazi').b11Record?.provenance);
    const row = await page.evaluate(() => lcGet('bazi').b11Record);
    originalId = row.id; assert.equal(row.result.engine.version, '1.7.7'); assert(row.provenance.cacheKey.startsWith('bazi:v1:'));
    assert.equal(row.provenance.manifest.teacherConfirmed, false);
    assert.equal(await page.evaluate(() => localStorage.getItem('ew-life-birth-v1:' + lcScope())), originalBirth);
    await h.capture(page, '当前真实结果与版本');
  });
  if(!originalId)throw Error('The first real birth/save fixture did not complete; dependent scenarios cannot run meaningfully.');
  await h.check('B11旧档案查看只读：没有调用适配器，没有修改旧日期/结果/原生辰', async () => {
    const fixture = await page.evaluate(() => {
      const source = JSON.parse(JSON.stringify(lcGet('bazi').b11Record));
      const legacy = JSON.parse(JSON.stringify(source)); legacy.id = 'b11-legacy-synthetic'; delete legacy.provenance; legacy.savedAt = '2021-02-03T04:05:06.000Z';
      const n = JSON.parse(JSON.stringify(source.normalized));
      const create = (kind, options, id) => {const result = lcCompute(kind, n, options); return {schema: 1, id, kind, title: 'B11 synthetic ' + kind,
        birth: n.birth, normalized: n, options, result, engine: result.engine, rules: result.rules, savedAt: '2022-03-04T05:06:07.000Z'};};
      const ziwei = create('ziwei', {timeBasis: 'UTC+8', fixLeap: true}, 'b11-ziwei-synthetic');
      const western = create('western', {mode: 'geocentric'}, 'b11-western-synthetic');
      if (!lcWriteRecords([legacy, ziwei, western, ...lcRecords()])) throw Error('Fixture storage failed');
      const original = lcBaziCalculate;
      window.__b11AdapterCalls = 0; lcBaziCalculate = function(...args) {window.__b11AdapterCalls++; return original(...args);};
      return {id: legacy.id, legacyJSON: JSON.stringify(legacy), rows: lcRecords()};
    });
    legacyId = fixture.id; legacyJSON = fixture.legacyJSON; originalRows = fixture.rows;
    await open(legacyId);
    assert.equal(await page.evaluate(() => window.__b11AdapterCalls), 0);
    assert.equal(await page.locator('[data-b11-state="snapshot-legacy-unverified"]').count(), 1);
    assert.equal(await page.locator('form[data-lb-options=bazi]').count(), 0);
    assert.equal(JSON.stringify((await records()).find(x => x.id === legacyId)), legacyJSON);
    assert.equal(await page.evaluate(() => localStorage.getItem('ew-life-birth-v1:' + lcScope())), originalBirth);
    await page.locator('[data-b11-manifest] summary').click();
    assert((await page.locator('[data-b11-manifest]').innerText()).includes('2021-02-03T04:05:06.000Z'));
    assert.equal(await page.locator('[data-b11-teacher-confirmed=false]').count(), 1);
    await h.capture(page, '旧快照原日期与未知历史版本');
  });
  await h.check('B11显式重算：取消不计算；确认后按原UTC/选项实际重算并另存新id/parent', async () => {
    await chartAction(page,'b11','recalculate-request');
    await page.locator('[data-b11-action=recalculate-cancel]').click();
    assert.equal(await page.evaluate(() => window.__b11AdapterCalls), 0);
    assert.equal((await records()).length, originalRows.length);
    await chartAction(page,'b11','recalculate-request');
    await page.locator('[data-b11-action=recalculate-confirm]').click();
    await page.waitForFunction(id => lcGet('bazi').b11Record?.provenance?.parentRecordId === id, legacyId);
    const next = await page.evaluate(() => lcGet('bazi').b11Record);
    linkedId = next.id; assert.notEqual(linkedId, legacyId); assert.equal(next.provenance.rootRecordId, legacyId);
    assert.equal(await page.evaluate(() => window.__b11AdapterCalls), 1);
    const old = (await records()).find(x => x.id === legacyId);
    assert.equal(JSON.stringify(old), legacyJSON); assert.deepEqual(next.normalized, old.normalized); assert.deepEqual(next.options, old.options);
    assert.deepEqual(next.result, old.result); assert.notEqual(next.savedAt, old.savedAt);
    assert.equal(await page.evaluate(() => localStorage.getItem('ew-life-birth-v1:' + lcScope())), originalBirth);
    await h.capture(page, '明确确认后原档案与新版本并存');
  });
  await h.check('B11容量已满20：真实点击重算明确拒绝且不淘汰任何旧档案', async () => {
    const before = await page.evaluate(() => {
      const rows = lcRecords(), source = rows.find(x => x.kind === 'ziwei');
      while (rows.length < 20) rows.push({...JSON.parse(JSON.stringify(source)), id: 'b11-capacity-' + rows.length});
      if (!lcWriteRecords(rows)) throw Error('Capacity fixture failed'); return JSON.stringify(lcRecords());
    });
    const calls = await page.evaluate(() => window.__b11AdapterCalls);
    await chartAction(page,'b11','recalculate-request');
    await page.locator('.b11-provenance [role=alert]').waitFor();
    assert((await page.locator('.b11-provenance [role=alert]').innerText()).includes('20'));
    assert.equal(await page.locator('[data-b11-action=recalculate-confirm]').count(), 0);
    assert.equal(await page.evaluate(() => JSON.stringify(lcRecords())), before);
    assert.equal(await page.evaluate(() => window.__b11AdapterCalls), calls);
    await h.capture(page, '20份满容量明确拒绝');
    await page.evaluate(() => {if (!lcWriteRecords(lcRecords().filter(r => !r.id.startsWith('b11-capacity-')))) throw Error('Fixture cleanup failed');});
  });
  await h.check('B11保存原快照不覆盖；导出JSON保持原日期和原结果', async () => {
    await open(legacyId); const before = JSON.stringify(await records());
    await chartAction(page,'lc','save');
    assert.equal(JSON.stringify(await records()), before);
    const download = page.waitForEvent('download'); await chartAction(page,'lc','export');
    const file = await download, stream = await file.createReadStream(), chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    assert.equal(JSON.stringify(data), legacyJSON); assert.equal(JSON.stringify(await records()), before);
  });
  await h.check('B11解读版本绑定：仅元数据夹具，旧规则/不匹配指纹不可复用，不调用AI', async () => {
    const statuses = await page.evaluate(async id => {
      const row = lcRecords().find(x => x.id === id), current = BAZI_RELEASE_MANIFEST;
      const binding = await BaziResultVersion.bindInterpretation(row, {id: 'fixture-reference-no-provider-call'}, current);
      return {current: await BaziVersionUI.inspectInterpretation(row, binding),
        old: await BaziResultVersion.interpretationStatus(row, binding, {...current, ruleVersion: 'fixture-new-release-not-approved'}),
        mismatch: await BaziVersionUI.inspectInterpretation(row, {...binding, outputFingerprint: 'sha256:wrong'})};
    }, linkedId);
    assert.deepEqual(statuses.current, {state: 'current', reusable: true});
    assert.deepEqual(statuses.old, {state: 'historical', reusable: false});
    assert.deepEqual(statuses.mismatch, {state: 'mismatched', reusable: false});
    assert.equal(await page.locator('[data-b11-ai-version]').count(), 1);
  });
  await h.check('B11对紫微/西方档案只透传原打开逻辑且原存档及四字段不变', async () => {
    const before = await records();
    for (const [kind, id, target] of [['ziwei', 'b11-ziwei-synthetic', 'ziweiChart'], ['western', 'b11-western-synthetic', 'westernAstrology']]) {
      await go('lifeReview');
      await page.locator('[data-lc-action=open][data-kind="' + kind + '"][data-id="' + id + '"]').click();
      await page.waitForFunction(({kind, id, target}) => state.page === target && lcGet(kind).savedId === id, {kind, id, target});
      assert.equal(await page.locator('[data-b11-state]').count(), 0);
      assert.equal(JSON.stringify((await records()).find(x => x.id === id)), JSON.stringify(before.find(x => x.id === id)));
    }
    assert.equal(await page.evaluate(() => localStorage.getItem('ew-life-birth-v1:' + lcScope())), originalBirth);
  });
  await h.check('B11四语375/430日夜：版本指纹换行可读且页面无横向溢出', async () => {
    await open(originalId);
    await page.waitForFunction(()=>!document.querySelector('#toast')?.textContent.trim(),null,{timeout:6000});
    for (const width of [375, 430]) for (const mode of ['day', 'night']) for (const lang of ['zh', 'zh-Hant', 'en', 'bo']) {
      await page.setViewportSize({width, height: 844});
      await page.evaluate(async ({lang, mode}) => {if(typeof ewChangeLanguage==='function')ewChangeLanguage(lang);else state.lang=lang;state.mode=mode;persist();render(false);if(lang==='bo'){const faces=await document.fonts.load('16px '+JSON.stringify('EW Tibetan'),'བོད་ཡིག');await document.fonts.ready;if(!faces.length||faces.some(f=>f.status!=='loaded'))throw Error('Actual EW Tibetan font did not load');if(!getComputedStyle(document.querySelector('.b11-provenance')).fontFamily.includes('EW Tibetan'))throw Error('Tibetan font was not selected');}}, {lang, mode});
      await page.locator('.b11-manifest summary').click();
      await page.locator('[data-b11-manifest] dd').nth(5).scrollIntoViewIfNeeded();
      assert.equal(await page.locator('[data-b11-teacher-confirmed=false]').count(), 1);
      assert.equal(await page.locator('[data-b11-manifest]').getAttribute('open'),'','The version section actually expanded');
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2);
      assert.equal(overflow, false, lang + ' ' + width + ' ' + mode);
      if (width===375 && mode==='night') await h.capture(page, '四语版本追溯-' + lang);
    }
  });
  await h.check('B11真实双标签协作：两次明确重算都保留，删除与另存共用同名账号锁', async () => {
    const second=await context.newPage();
    const lock=await page.evaluate(()=>'ew-life-charts-write-v1:'+encodeURIComponent(psToken().scope));
    const secondOpen=async()=>{await second.evaluate(()=>navigate('lifeReview'));await second.locator('[data-lc-action=open][data-kind=bazi][data-id="'+legacyId+'"]').click();await second.waitForFunction(id=>lcGet('bazi').b11Readonly&&lcGet('bazi').savedId===id,legacyId);};
    const hold=async()=>{await page.evaluate(lock=>{window.__b11LockBarrier={entered:false};void navigator.locks.request(lock,async()=>{__b11LockBarrier.entered=true;await new Promise(resolve=>__b11LockBarrier.release=resolve);});},lock);await page.waitForFunction(()=>__b11LockBarrier.entered);};
    const queued=async n=>page.waitForFunction(async({lock,n})=>(await navigator.locks.query()).pending.filter(x=>x.name===lock).length>=n,{lock,n},{timeout:8000});
    const release=async()=>page.evaluate(()=>window.__b11LockBarrier.release());
    const confirm=async p=>{await chartAction(p,'b11','recalculate-request');await p.locator('[data-b11-action=recalculate-confirm]').click();};
    try {
      await second.goto(h.base+'/experience');await second.waitForFunction(()=>px.loaded&&!pxBootstrapPending&&BaziVersionUI.installed);
      await open(legacyId);await secondOpen();const before=await records(),ids=before.map(x=>x.id);
      await hold();await Promise.all([confirm(page),confirm(second)]);await queued(2);await release();
      await page.waitForFunction(({ids,parent})=>lcRecords().filter(x=>!ids.includes(x.id)&&x.provenance?.parentRecordId===parent).length===2,{ids,parent:legacyId});
      await Promise.all([page.waitForFunction(ids=>!ids.includes(lcGet('bazi').b11Record?.id),ids),second.waitForFunction(ids=>!ids.includes(lcGet('bazi').b11Record?.id),ids)]);
      const after=await records(),children=after.filter(x=>!ids.includes(x.id));assert.equal(after.length,before.length+2);
      for(const row of before)assert.equal(JSON.stringify(after.find(x=>x.id===row.id)),JSON.stringify(row));
      const deletion=children[0].id,prior=await records();
      await secondOpen();await go('lifeReview');await hold();
      await page.locator('[data-lc-action=delete][data-kind=bazi][data-id="'+deletion+'"]').click();
      await page.locator('[data-lc-action=delete-confirm][data-kind=bazi]').click();await queued(1);
      await confirm(second);await queued(2);await release();
      await page.waitForFunction(({id,n})=>!lcRecords().some(x=>x.id===id)&&lcRecords().length===n,{id:deletion,n:prior.length});
      const merged=await records();assert(!merged.some(x=>x.id===deletion));assert(merged.some(x=>!prior.some(y=>y.id===x.id)));
      for(const row of prior.filter(x=>x.id!==deletion))assert.equal(JSON.stringify(merged.find(x=>x.id===row.id)),JSON.stringify(row));
      assert.equal(JSON.stringify(merged.find(x=>x.id===legacyId)),legacyJSON);
      await h.capture(page,'双标签另存与删除协作');
    } finally {await page.evaluate(()=>window.__b11LockBarrier?.release?.()).catch(()=>{});await second.close();}
  });
  await h.check('B11无协作锁环境明确停写：新保存、重算、删除均不落盘，原快照仍能查看导出', async () => {
    const p=await context.newPage(),before=JSON.stringify(await records());
    try {
      await p.goto(h.base+'/experience');await p.waitForFunction(()=>px.loaded&&!pxBootstrapPending&&BaziVersionUI.installed);
      await p.evaluate(()=>{Object.defineProperty(navigator,'locks',{configurable:true,value:undefined});navigate('classicsWisdom');});
      await chartAction(p,'lc','save');
      await p.locator('[data-b11-manifest] summary').click();await p.locator('[data-b11-write-support=unavailable]').waitFor({state:'visible'});assert.equal(JSON.stringify(await records()),before);
      await p.evaluate(()=>navigate('lifeReview'));await p.locator('[data-lc-action=delete][data-kind=bazi][data-id="'+legacyId+'"]').click();
      await p.locator('[data-lc-action=delete-confirm][data-kind=bazi]').click();assert.equal(JSON.stringify(await records()),before);
      await p.evaluate(()=>closeSheet());
      await p.locator('[data-lc-action=open][data-kind=bazi][data-id="'+legacyId+'"]').click();
      await p.waitForFunction(id=>lcGet('bazi').b11Readonly&&lcGet('bazi').savedId===id,legacyId);
      await chartAction(p,'b11','recalculate-request');assert.equal(await p.locator('[data-b11-action=recalculate-confirm]').count(),0);
      const download=p.waitForEvent('download');await chartAction(p,'lc','export');assert((await download).suggestedFilename().includes(legacyId));
      assert.equal(JSON.stringify(await records()),before);
    } finally {await p.close();}
  });
  await h.check('B11换账号迟到：真实cookie切换/Bootstrap后旧SHA工作不另存到任何账号', async () => {
    await page.evaluate(() => {state.lang='zh';render(false);}); await open(legacyId);
    const ownKey = await page.evaluate(() => 'ew-life-charts-v1:' + lcScope()), ownBefore = await page.evaluate(k => localStorage.getItem(k), ownKey);
    await page.evaluate(() => {
      const original = crypto.subtle.digest.bind(crypto.subtle), hold={seen:false,done:false,release:null,original};
      const gate = new Promise(resolve=>hold.release=resolve);
      crypto.subtle.digest = async function(...args) {const result=await original(...args);if(!hold.seen){hold.seen=true;await gate;hold.done=true;}return result;};
      window.__b11DigestHold=hold;
    });
    await chartAction(page,'b11','recalculate-request');
    await page.locator('[data-b11-action=recalculate-confirm]').click();
    await page.waitForFunction(()=>window.__b11DigestHold.seen);
    assert.equal((await context.request.post(h.base+'/api/auth/logout',{data:{}})).status(),200);
    assert.equal((await context.request.post(h.base+'/api/auth/login',{data:other.credential})).status(),200);
    await page.evaluate(async()=>{await pxBootstrap(true);navigate('lifeResult');});
    await page.waitForFunction(id=>px.user?.id===id&&psToken().scope===id,other.credential.id);
    await page.evaluate(()=>{const h=window.__b11DigestHold;crypto.subtle.digest=h.original;h.release();});
    await page.waitForFunction(()=>window.__b11DigestHold.done);await page.waitForTimeout(250);
    assert.equal(await page.evaluate(k=>localStorage.getItem(k),ownKey),ownBefore);
    assert.deepEqual(await records(),[]);
    assert.equal(await page.locator('[data-b11-state]').count(),0);
    await h.capture(page,'真实换账号迟到不保存');
  });
  await context?.close();
};

