'use strict';
// Isolated B11 checks: existing deterministic adapter + synthetic birth input; no server/db/build writes.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict'), crypto = require('node:crypto');
if (!globalThis.crypto) globalThis.crypto = crypto.webcrypto;
const base = path.resolve(__dirname, '..'), app = path.join(base, '04_研发源码/app/r4');
const helperPath = path.join(app, 'bazi-result-version.js'), corePath = path.join(app, 'life-chart-core.js'), baziPath = path.join(app, 'life-chart-bazi.js');
const files = [helperPath, path.join(app, 'bazi-result-version-ui.js'), path.join(app, 'bazi-result-version-release.js'), path.join(app, 'bazi-result-version.css'), corePath, baziPath, path.join(app, 'bazi-time.js'), path.join(app, 'life-birth-entry.js'), path.join(app, 'vendor/lunar-1.7.7.js'), __filename];
const hashes = () => Object.fromEntries(files.map(p => [path.relative(base, p).replaceAll('\\', '/'), crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')]));
const initial = hashes(), H = require(helperPath), core = require(corePath);
const context = vm.createContext({screens: {}, document: {addEventListener() {}}, window: {addEventListener() {}}});
vm.runInContext(fs.readFileSync(path.join(app, 'vendor/lunar-1.7.7.js'), 'utf8'), context, {filename: 'lunar-1.7.7.js'});
vm.runInContext(fs.readFileSync(baziPath, 'utf8'), context, {filename: 'life-chart-bazi.js'});
function compute(normalized, options) {
  context.__input = JSON.stringify(normalized); context.__options = JSON.stringify(options);
  return JSON.parse(vm.runInContext('JSON.stringify(lcBaziCalculate(JSON.parse(__input),JSON.parse(__options)))', context));
}
const release = {engine: {name: 'lunar-javascript', version: '1.7.7'}, ruleVersion: 'fixture-release-A', adapterVersion: 'sha256:' + initial['04_研发源码/app/r4/life-chart-bazi.js']};
const nextRelease = {...release, ruleVersion: 'fixture-release-B'};
const birth = {name: 'B11 synthetic', date: '1990-06-15', time: '23:30', timezone: 'Asia/Shanghai', ambiguity: 'reject', sex: 'male', latitude: '', longitude: '', place: '', confirmed: true};
const normalized = core.lcNormalizeInput(birth), options = {daySect: 2, yunSect: 2};
const result = compute(normalized, options), fixedTime = '2026-11-12T06:00:00.000Z', clone = v => JSON.parse(JSON.stringify(v));
const reports = [], state = {scope: 'fixture-owner-A', epoch: 1}, token = {scope: state.scope, epoch: state.epoch};
const isCurrent = t => t.scope === state.scope && t.epoch === state.epoch;
async function check(name, run) {
  try { await run(); reports.push({name, passed: true}); process.stdout.write('PASS ' + name + '\n'); }
  catch (e) { reports.push({name, passed: false, code: e.code || null, error: e.message}); process.stdout.write('FAIL ' + name + ': ' + e.message + '\n'); }
}
const rejects = (promise, code) => assert.rejects(promise, e => e.code === code);
(async () => {
  let saved, next, binding, legacy;
  await check('actual adapter output remains unchanged; fresh snapshot records explicit versions and SHA256', async () => {
    saved = await H.captureCalculation({id: 'original', normalized, options, result, manifest: release, capturedAt: fixedTime, calculatedAt: fixedTime});
    assert.deepEqual(saved.result, result); assert.deepEqual(saved.birth, normalized.birth); assert.deepEqual(saved.options, options);
    assert.match(saved.provenance.outputFingerprint, /^sha256:[a-f0-9]{64}$/);
    assert.match(saved.provenance.cacheKey, /^bazi:v1:[a-f0-9]{64}$/);
    assert.equal((await H.inspectSnapshot(saved, release)).state, 'current');
    assert.equal(H.manifest({...release, teacherConfirmed: true}).teacherConfirmed, false);
  });
  await check('canonical object key order stable; array order and value types remain significant', async () => {
    assert.equal(await H.fingerprint({b: [1, 2], a: 3}), await H.fingerprint({a: 3, b: [1, 2]}));
    assert.notEqual(await H.fingerprint([1, 2]), await H.fingerprint([2, 1]));
    assert.notEqual(await H.fingerprint(1), await H.fingerprint('1'));
  });
  await check('actual day/yun options and normalized input have distinct cache identities', async () => {
    for (const alt of [{daySect: 1, yunSect: 2}, {daySect: 2, yunSect: 1}]) {
      const row = await H.captureCalculation({id: 'alternative', normalized, options: alt, result: compute(normalized, alt), manifest: release, capturedAt: fixedTime});
      assert.notEqual(row.provenance.cacheKey, saved.provenance.cacheKey);
    }
    const n = core.lcNormalizeInput({...birth, time: '22:30'});
    const row = await H.captureCalculation({id: 'input-change', normalized: n, options, result: compute(n, options), manifest: release, capturedAt: fixedTime});
    assert.notEqual(row.provenance.cacheKey, saved.provenance.cacheKey);
  });
  await check('rule/adapter/engine revisions invalidate reuse without recalculating or changing old bytes', async () => {
    const old = JSON.stringify(saved);
    for (const manifest of [nextRelease, {...release, adapterVersion: 'fixture-next-adapter'}, {...release, engine: {...release.engine, version: 'fixture-unavailable-engine'}}]) {
      const x = await H.inspectSnapshot(saved, manifest); assert.equal(x.state, 'outdated'); assert.equal(x.cacheReusable, false);
    }
    assert.equal(JSON.stringify(saved), old);
  });
  await check('stored result/input/options/rules fingerprints detect accidental alteration', async () => {
    for (const edit of [
      r => {r.result.pillars[0].stem = 'altered';},
      r => {r.options.daySect = 1;},
      r => {r.result.rules.daySect = 1;},
      r => {r.engine.version = 'changed display';},
      r => {r.normalized.utc = '1990-06-16T00:00:00.000Z';},
      r => {r.birth.time = '22:30';}
    ]) {
      const row = clone(saved); edit(row);
      await assert.rejects(H.inspectSnapshot(row, release), e => ['VERSION_INTEGRITY', 'VERSION_INPUT'].includes(e.code));
    }
  });
  await check('legacy snapshot stays unverified and original saved time is never invented', async () => {
    legacy = clone(saved); delete legacy.provenance; legacy.id = 'legacy'; legacy.savedAt = 'legacy timestamp unknown';
    const before = JSON.stringify(legacy), x = await H.inspectSnapshot(legacy, release);
    assert.equal(x.state, 'legacy-unverified'); assert.equal(x.cacheReusable, false); assert.equal(x.calculatedAt, null);
    assert.equal(x.savedAt, 'legacy timestamp unknown'); assert.equal(JSON.stringify(legacy), before);
  });
  await check('no explicit consent means no calculation; old ID overwrite is rejected before adapter call', async () => {
    let calls = 0; const args = {record: saved, manifest: nextRelease, context: token, isCurrent, compute() {calls++; return result;}};
    await rejects(H.recalculate({...args, confirmed: false}), 'VERSION_CONFIRM');
    await rejects(H.recalculate({...args, confirmed: true, id: saved.id}), 'VERSION_OVERWRITE');
    assert.equal(calls, 0);
  });
  await check('explicit recalculation calls actual adapter using unchanged archived input and creates a new child', async () => {
    const before = JSON.stringify(saved); let calls = 0;
    next = await H.recalculate({record: saved, manifest: nextRelease, confirmed: true, id: 'child', context: token, isCurrent,
      clock: () => Date.parse(fixedTime) + 1000, compute(n, o) {calls++; assert.deepEqual(n, normalized); assert.deepEqual(o, options); return compute(n, o);}});
    assert.equal(calls, 1); assert.equal(next.id, 'child'); assert.equal(next.provenance.parentRecordId, 'original');
    assert.equal(next.provenance.rootRecordId, 'original'); assert.equal(next.provenance.calculatedAt, '2026-11-12T06:00:01.000Z');
    assert.equal(JSON.stringify(saved), before); assert.deepEqual(next.result, saved.result);
    assert.notEqual(next.provenance.cacheKey, saved.provenance.cacheKey);
  });
  await check('legacy explicit recalculation preserves its old unknown timestamp and links new version', async () => {
    const before = JSON.stringify(legacy);
    const row = await H.recalculate({record: legacy, manifest: release, confirmed: true, id: 'legacy-child', context: token, isCurrent, compute, clock: () => Date.parse(fixedTime)});
    assert.equal(row.provenance.parentRecordId, 'legacy'); assert.equal(row.provenance.rootRecordId, 'legacy');
    assert.equal(JSON.stringify(legacy), before);
    assert.equal((await H.inspectSnapshot(row, release)).cacheReusable, true);
  });
  await check('account/action context is checked before adapter and after late asynchronous completion', async () => {
    let called = 0;
    await rejects(H.recalculate({record: saved, manifest: release, confirmed: true, id: 'stale', context: token, isCurrent: () => false, compute() {called++; return result;}}), 'VERSION_CONTEXT');
    assert.equal(called, 0);
    await rejects(H.recalculate({record: saved, manifest: release, confirmed: true, id: 'late', context: token, isCurrent,
      async compute(n, o) {state.epoch++; return compute(n, o);}}), 'VERSION_CONTEXT');
    state.epoch = token.epoch;
  });
  await check('wrong engine output and absent release declarations fail closed', async () => {
    await rejects(H.captureCalculation({id: 'bad-engine', normalized, options, result, manifest: {...release, engine: {...release.engine, version: 'unknown'}}, capturedAt: fixedTime}), 'VERSION_ENGINE');
    await rejects(H.captureCalculation({id: 'bad-rule', normalized, options, result, manifest: {...release, ruleVersion: ''}, capturedAt: fixedTime}), 'VERSION_MANIFEST');
  });
  await check('append is immutable and requires existing parent in same supplied account archive', async () => {
    const rows = [saved], before = JSON.stringify(rows), answer = await H.appendVersion(rows, next, nextRelease);
    assert.equal(answer.length, 2); assert.equal(answer[0].id, 'child'); assert.equal(JSON.stringify(rows), before);
    assert.equal(JSON.stringify(answer[1]), JSON.stringify(saved), 'Appending must preserve the original record property order and bytes');
    await rejects(H.appendVersion(rows, saved, release), 'VERSION_OVERWRITE');
    await rejects(H.appendVersion([], next, nextRelease), 'VERSION_LINEAGE');
    await rejects(H.appendVersion(rows, next, release), 'VERSION_STALE');
    const differentInput=core.lcNormalizeInput({...birth,time:'22:30'});
    const changed=await H.captureCalculation({id:'input-change-child',normalized:differentInput,options,result:compute(differentInput,options),manifest:nextRelease,capturedAt:fixedTime});
    changed.provenance.parentRecordId=saved.id;changed.provenance.rootRecordId=saved.id;
    await rejects(H.appendVersion(rows,changed,nextRelease),'VERSION_INPUT');
  });
  await check('full archive fails without silently pruning any old record', async () => {
    const full = Array.from({length: 20}, (_, i) => ({...clone(saved), id: i === 0 ? 'original' : 'fixture-' + i}));
    const before = JSON.stringify(full);
    await rejects(H.appendVersion(full, next, nextRelease), 'VERSION_LIMIT');
    assert.equal(JSON.stringify(full), before);
  });
  await check('AI interpretation binds exact current record/key/output; unrelated and historical versions are not reused', async () => {
    binding = await H.bindInterpretation(saved, {id: 'real-response-id-reference-only'}, release);
    assert.deepEqual(await H.interpretationStatus(saved, binding, release), {state: 'current', reusable: true});
    assert.deepEqual(await H.interpretationStatus(saved, binding, nextRelease), {state: 'historical', reusable: false});
    assert.deepEqual(await H.interpretationStatus(next, binding, nextRelease), {state: 'mismatched', reusable: false});
    assert.deepEqual(await H.interpretationStatus(legacy, binding, release), {state: 'unbound', reusable: false});
    await rejects(H.bindInterpretation(legacy, {id: 'unverified'}, release), 'VERSION_AI_UNVERIFIED');
    await rejects(H.bindInterpretation(saved, {id: 'outdated'}, nextRelease), 'VERSION_AI_UNVERIFIED');
  });
  await check('invalid JSON, recursive values and accessors fail before hashing', async () => {
    for (const value of [{x: NaN}, {x: undefined}, (() => {const v={};v.self=v;return v;})(), [ , 1], Object.defineProperty({}, 'x', {get() {throw new Error('getter executed');}, enumerable: true})])
      assert.throws(() => H.canonical(value), e => e.code === 'VERSION_DATA');
  });
  await check('browser module has no event/storage/network side effects and crypto absence fails closed', async () => {
    const c = vm.createContext({TextEncoder, Uint8Array});
    vm.runInContext(fs.readFileSync(helperPath, 'utf8'), c, {filename: 'bazi-result-version.js'});
    assert.equal(vm.runInContext('typeof BaziResultVersion.recalculate', c), 'function');
    await assert.rejects(vm.runInContext('BaziResultVersion.fingerprint({a:1})', c), e => e.code === 'VERSION_CRYPTO');
    assert.equal(vm.runInContext('typeof localStorage', c), 'undefined');
    vm.runInContext(fs.readFileSync(path.join(app,'bazi-result-version-ui.js'),'utf8'),c,{filename:'bazi-result-version-ui.js'});
    assert.equal(vm.runInContext('BaziVersionUI.installed',c),false);
  });
  const final = hashes(), identityUnchanged = JSON.stringify(initial) === JSON.stringify(final);
  const report = {module: 'B11 standalone provenance preparation', ranAt: new Date().toISOString(), integration: 'not integrated; no core/build/server changes',
    result: {passed: reports.filter(x => x.passed).length, failed: reports.filter(x => !x.passed).length}, identityUnchanged, sourceAndTestHashes: final, tests: reports,
    limits: ['Synthetic actual lunar-javascript adapter only; no teacher-approved cases or professional validation.', 'Release versions in tests are explicitly fixture labels, not production policy approvals.', 'No existing user archives or original databases were read.', 'Browser/UI/real AI binding and module full regression remain for integration.']};
  fs.writeFileSync(path.join(__dirname, '负责人优化建议-B11独立专项.json'), JSON.stringify(report, null, 2) + '\n', 'utf8');
  if (report.result.failed || !identityUnchanged) process.exitCode = 1;
})().catch(e => {console.error(e.stack); process.exitCode = 1;});

