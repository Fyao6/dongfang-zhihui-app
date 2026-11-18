'use strict';
// PREPARED ONLY. Default invocation does not start HTTP, a browser, or a timer.
// This is an isolated browser-media component, not an APP/CDN/mobile benchmark.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const ROOT = path.resolve(__dirname, '..');
const PREFIX = '负责人优化建议-本地可靠性媒体计时';
const MEDIA_RELATIVE = '04_研发源码/app/r4/images/community-preview.mp4';
const MEDIA = path.join(ROOT, MEDIA_RELATIVE);
const PROOF = path.join(__dirname, '负责人优化建议-卡组迁移-最终交付核验.json');
const FINAL_PROOF_SHA256 = '752e36ad70d6812727849f0fa49262c426ef161a911b59f66831cd0617e12f07';
const NODE_MODULES = path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const LIMITS = Object.freeze({startupMs: 30000, playbackMs: 6000, seekPlaybackMs: 3000,
  recoveryMs: 15000, viewport: {width: 1280, height: 800}, maximumSamples: 5000});

function verifyProof(file, expected, authorization) {
  assert.equal(path.resolve(file), PROOF);
  assert.equal(expected, FINAL_PROOF_SHA256, 'Only the completed Stage30 final proof is authorized');
  const bytes = fs.readFileSync(PROOF);
  assert.equal(sha(bytes), expected);
  const proof = JSON.parse(bytes);
  assert(proof.pass === true && proof.stage === 30 && proof.productionEnabled === false);
  assert.equal(proof.allFourteenGatesPassedWithFreshSuccessfulChildren, true);
  assert.deepEqual(proof.perBackendPassed, {Python: 195, Cloud: 195});
  assert.equal(Object.keys(proof.verifiedSHA256).length, proof.verifiedFiles);
  assert(authorization && authorization.originalStage30ProductUnchanged === false);
  assert.deepEqual(Object.keys(authorization.authorizedProductChanges), ['04_研发源码/app/r4/backend/server.py']);
  for (const [relative, digest] of Object.entries(proof.verifiedSHA256)) {
    const filePath = path.resolve(ROOT, relative);
    assert(!path.isAbsolute(relative) && filePath.startsWith(ROOT + path.sep));
    const currentExpected = authorization.currentInheritedInputHashes[relative] || digest;
    if (currentExpected !== digest) assert.equal(relative, '04_研发源码/app/r4/backend/server.py');
    assert.equal(sha(fs.readFileSync(filePath)), currentExpected, 'Unapproved inherited verified bytes changed: ' + relative);
  }
  assert.equal(proof.verifiedSHA256[MEDIA_RELATIVE], sha(fs.readFileSync(MEDIA)));
  return {path: path.relative(ROOT, PROOF), sha256: expected, stage: 30,
    actualVerifiedFileCount: proof.verifiedFiles, exactFinalProof: true,
    originalStage30ProductUnchanged: false,
    currentSourceBinding: 'Only the common verified passing repair record and its exact server.py authorization admit the preserved product delta'};
}

function timingSummary(measured) {
  const initial = measured.segments.initial, seek = measured.segments.seek;
  const end = measured.events.find(e => e.name === 'native-finish')?.at;
  const start = initial.requestedAt, intervals = []; let waiting = null;
  assert(Number.isFinite(start) && Number.isFinite(end) && end >= start);
  for (const e of measured.events) {
    if (e.name === 'waiting' && waiting === null) waiting = e.at;
    if (waiting !== null && ['playing', 'pause', 'ended', 'error', 'abort', 'seeking', 'native-finish'].includes(e.name)) {
      const from = Math.max(start, waiting), to = Math.min(end, e.at);
      if (to > from) intervals.push({startAt: from, endAt: to, milliseconds: to - from,
        closedBy: e.name, beginsDuringSeekRecovery: from >= seek.requestedAt && from <= (seek.firstPresentedFrame?.at ?? seek.seekedAt)});
      waiting = null;
    }
  }
  const span = end - start, waitingMs = intervals.reduce((n, x) => n + x.milliseconds, 0);
  return {
    loadeddata: {covered: measured.loadeddataAt !== null, atFromNavigationMs: measured.loadeddataAt,
      elapsedRelativeToNativePlayRequestMs: measured.loadeddataAt === null ? null : measured.loadeddataAt - start,
      alreadyLoadedBeforePlay: measured.loadeddataAt !== null && measured.loadeddataAt < start,
      isPresentedFirstFrame: false},
    presentedFirstFrame: {covered: !!initial.firstPresentedFrame,
      elapsedFromNativePlayRequestMs: initial.firstPresentedFrame?.elapsedFromRequestMs ?? null,
      mediaTime: initial.firstPresentedFrame?.mediaTime ?? null, source: 'requestVideoFrameCallback',
      unavailableReason: initial.firstPresentedFrame ? null : 'requestVideoFrameCallback_unavailable_or_unobserved'},
    seek: {nativeButtonTriggeredProgrammaticSeek: true, targetSeconds: seek.target,
      seekedEventLatencyMs: seek.seekedAt - seek.requestedAt,
      presentedFrameRecoveryLatencyMs: seek.firstPresentedFrame?.elapsedFromRequestMs ?? null,
      realPostSeekPlaybackObserved: true, isNativeScrubberDragTest: false},
    waiting: {waitingEventCount: measured.events.filter(e => e.name === 'waiting').length,
      stalledNetworkEventCount: measured.events.filter(e => e.name === 'stalled').length,
      intervals, observedWaitingMilliseconds: waitingMs, scriptedObservationSpanMs: span,
      waitingRatioOfScriptedObservation: span > 0 ? waitingMs / span : null,
      definition: 'waiting until playing/pause/ended/error/abort/seeking/finish, clipped to the scripted play-to-finish window; startup and seek waits included',
      networkStalledDoesNotProvePlaybackStopped: true, professionalStallRateClaimed: false},
    sampleCount: measured.samples.length, latencySampleCount: 1, latencyPercentiles: null,
    percentileBoundary: 'One isolated component run is not a population P95 or a target-country benchmark'
  };
}

function rangeFor(header, length) {
  if (header === undefined) return {status: 200, start: 0, end: length - 1};
  const match = /^bytes=(\d*)-(\d*)$/.exec(header);
  if (!match || (!match[1] && !match[2])) return null;
  let start, end;
  if (!match[1]) {
    const count = Number(match[2]);
    if (!Number.isSafeInteger(count) || count <= 0) return null;
    start = Math.max(0, length - count); end = length - 1;
  } else {
    start = Number(match[1]); end = match[2] ? Number(match[2]) : length - 1;
    if (![start, end].every(Number.isSafeInteger) || start < 0 || start >= length || end < start) return null;
    end = Math.min(length - 1, end);
  }
  return {status: 206, start, end};
}

// Measurements use actual HTMLMediaElement events and the browser's clock.
// loadeddata is kept separate from a presented frame; it never substitutes for RVFC.
const HTML = `<!doctype html><html><head><meta charset="utf-8"><title>Local media component</title>
<style>body{font:18px/1.6 sans-serif;margin:24px;background:#eee;color:#111}video{display:block;width:720px;max-width:100%;height:405px;background:#111}button{font:inherit;margin:16px 16px 0 0;padding:10px}p{max-width:900px}</style></head>
<body><h1>本机合成媒体计时组件</h1><p>仅测固定本地 MP4 的浏览器播放与跳转。没有目标国、CDN、真实手机或生产性能结论。</p>
<video id="media" controls preload="metadata" playsinline src="/media.mp4"></video>
<button id="play" type="button">原生点击播放</button><button id="seek" type="button">跳转到固定位置并继续</button><button id="pause" type="button">暂停并结束观测</button>
<script>
const video=document.querySelector('#media'),state={events:[],samples:[],segments:{},frameApiAvailable:typeof video.requestVideoFrameCallback==='function',errors:[],loadeddataAt:null,playingIntervals:[],activePlaying:null,closed:false};
window.mediaMeasurement=state;
const now=()=>performance.now();
function event(name,extra={}){state.events.push({name,at:now(),mediaTime:video.currentTime,readyState:video.readyState,networkState:video.networkState,...extra});}
function endPlaying(){if(state.activePlaying!==null){state.playingIntervals.push({start:state.activePlaying,end:now()});state.activePlaying=null;}}
for(const name of ['loadstart','loadedmetadata','loadeddata','canplay','play','playing','waiting','stalled','seeking','seeked','pause','ended','error','abort','suspend'])video.addEventListener(name,()=>{event(name);if(name==='loadeddata'&&state.loadeddataAt===null)state.loadeddataAt=now();if(name==='playing'&&state.activePlaying===null)state.activePlaying=now();if(['pause','waiting','stalled','seeking','ended','error','abort'].includes(name))endPlaying();if(name==='error')state.errors.push({kind:'media',code:video.error?.code||null});});
function requestFrame(segment){if(!state.frameApiAvailable)return;video.requestVideoFrameCallback((stamp,metadata)=>{segment.firstPresentedFrame={at:stamp,elapsedFromRequestMs:stamp-segment.requestedAt,mediaTime:metadata.mediaTime,presentedFrames:metadata.presentedFrames,expectedDisplayTime:metadata.expectedDisplayTime,width:metadata.width,height:metadata.height};event('presented-frame',{segment:segment.name});});}
document.querySelector('#play').onclick=()=>{const segment=state.segments.initial={name:'initial',requestedAt:now(),startMediaTime:video.currentTime};event('native-play-request');requestFrame(segment);video.play().then(()=>{segment.playPromiseResolvedAt=now();}).catch(e=>{state.errors.push({kind:'play-rejected',name:e.name});});};
document.querySelector('#seek').onclick=()=>{const target=Math.min(video.duration-0.75,video.duration*0.6),segment=state.segments.seek={name:'seek',requestedAt:now(),fromMediaTime:video.currentTime,target};event('native-seek-request',{target});video.addEventListener('seeked',()=>{segment.seekedAt=now();requestFrame(segment);},{once:true});video.currentTime=target;video.play().catch(e=>{state.errors.push({kind:'seek-play-rejected',name:e.name});});};
document.querySelector('#pause').onclick=()=>{video.pause();endPlaying();state.closed=true;event('native-finish');};
const sample=setInterval(()=>{if(state.closed){clearInterval(sample);return;}if(state.samples.length<${LIMITS.maximumSamples})state.samples.push({at:now(),mediaTime:video.currentTime,paused:video.paused,seeking:video.seeking,readyState:video.readyState});else state.errors.push({kind:'sample-bound-exceeded'});},250);
</script></body></html>`;

async function execute(args) {
  assert.deepEqual(Object.keys(args).sort(), ['probe-local-media', 'proof-sha256', 'stage30-proof', 'repair-proof-sha256', 'repair-authorization-sha256'].sort());
  assert.equal(args['probe-local-media'], true);
  const {verifyRepairProof} = require('./负责人优化建议-本地可靠性修复基线.cjs');
  const repair = verifyRepairProof(args['repair-proof-sha256'], args['repair-authorization-sha256']);
  const proof = verifyProof(args['stage30-proof'], args['proof-sha256'], repair.authorization);
  const sourceBefore = sha(fs.readFileSync(__filename));
  const verifierFile = path.join(__dirname, '负责人优化建议-本地可靠性修复基线.cjs');
  const verifierBefore = sha(fs.readFileSync(verifierFile));
  const mediaBefore = sha(fs.readFileSync(MEDIA));
  const size = fs.statSync(MEDIA).size;
  assert(size > 0);
  const runId = crypto.randomUUID().replaceAll('-', '');
  const output = path.join(__dirname, PREFIX + '-' + runId + '.json');
  const screenshot = path.join(__dirname, PREFIX + '-' + runId + '.png');
  const report = {runId, startedAt: new Date().toISOString(), status: 'running-component',
    role: 'mediaComponent', componentOnly: true, formalAcceptance: false, productionEnabled: false, stage30Proof: proof,
    repairProof: repair.repairProof, repairAuthorization: repair.authorization,
    localBrowserMediaCovered: false, productAppPlaybackCovered: false, cdnCovered: false,
    targetCountryCovered: false, physicalMobileCovered: false, loadTestCovered: false,
    professionalLatencyThresholdConfirmed: false, limits: LIMITS,
    input: {path: MEDIA_RELATIVE, sha256: mediaBefore, bytes: size, existingFixedRepositoryAsset: true},
    source: {path: path.relative(ROOT, __filename), sha256: sourceBefore,
      commonVerifier: {path: path.relative(ROOT, verifierFile), sha256: verifierBefore}},
    httpByteAccounting: 'bytesSent counts fixed-file stream data queued into the response, not browser consumption or TCP acknowledgements; finish/close status is separate',
    runtime: {nodeExecutableSha256: sha(fs.readFileSync(process.execPath)), nodeVersion: process.version,
      hostPlatform: process.platform, cpuCount: os.cpus().length, freeMemoryBeforeBytes: os.freemem(),
      serverAndBrowserOnSameMachine: true, backgroundLoadControlled: false},
    httpRequests: [], browserErrors: [], externalRequests: []};
  let browser, context, server, interrupted = false;
  const streams = new Set();
  const interrupt = () => { interrupted = true; if (browser) browser.close().catch(() => {}); };
  process.once('SIGINT', interrupt); process.once('SIGTERM', interrupt);
  try {
    server = http.createServer((req, res) => {
      const row = {method: req.method, path: req.url, status: null, range: req.headers.range || null,
        bytesSent: 0, startedAt: new Date().toISOString(), completed: false};
      report.httpRequests.push(row);
      const send = (status, body) => { row.status = status; res.writeHead(status, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'}); res.end(body); };
      res.once('finish', () => { row.completed = true; });
      if (!['GET', 'HEAD'].includes(req.method)) return send(405, 'Method not allowed');
      if (req.url === '/') return send(200, req.method === 'HEAD' ? '' : HTML);
      if (req.url !== '/media.mp4') return send(404, 'Not found');
      const range = rangeFor(req.headers.range, size);
      if (!range) { row.status = 416; res.writeHead(416, {'Content-Range': 'bytes */' + size}); return res.end(); }
      row.status = range.status; row.start = range.start; row.end = range.end;
      res.writeHead(range.status, {'Content-Type': 'video/mp4', 'Accept-Ranges': 'bytes',
        'Content-Length': range.end - range.start + 1, 'Cache-Control': 'no-store',
        ...(range.status === 206 ? {'Content-Range': 'bytes ' + range.start + '-' + range.end + '/' + size} : {})});
      if (req.method === 'HEAD') return res.end();
      const stream = fs.createReadStream(MEDIA, {start: range.start, end: range.end});
      streams.add(stream);
      stream.on('data', part => { row.bytesSent += part.length; });
      stream.once('close', () => streams.delete(stream));
      stream.once('error', () => res.destroy());
      res.once('close', () => stream.destroy());
      stream.pipe(res);
    });
    await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
    const port = server.address().port;
    assert(![8877, 8878, 8879, 8880, 8881].includes(port));
    const base = 'http://127.0.0.1:' + port;
    report.base = base;
    const playwrightPath = require.resolve(path.join(NODE_MODULES, 'playwright'));
    const {chromium} = require(playwrightPath);
    report.runtime.playwrightEntry = {path: playwrightPath, sha256: sha(fs.readFileSync(playwrightPath))};
    report.runtime.browserExecutable = {path: chromium.executablePath(), sha256: sha(fs.readFileSync(chromium.executablePath()))};
    browser = await chromium.launch({headless: true});
    report.runtime.browserVersion = browser.version();
    context = await browser.newContext({viewport: LIMITS.viewport});
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin !== base) { report.externalRequests.push({protocol: url.protocol, hostname: url.hostname}); return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => report.browserErrors.push({name: error.name, message: String(error.message).slice(0, 200)}));
    await page.goto(base + '/', {waitUntil: 'domcontentloaded', timeout: LIMITS.startupMs});
    await page.waitForFunction(() => Number.isFinite(document.querySelector('#media').duration) && document.querySelector('#media').duration > 2, null, {timeout: LIMITS.startupMs});
    await page.locator('#play').click();
    await page.waitForFunction(() => document.querySelector('#media').currentTime > 0.25, null, {timeout: LIMITS.recoveryMs});
    await page.waitForTimeout(LIMITS.playbackMs);
    await page.locator('#seek').click();
    await page.waitForFunction(() => {
      const s = window.mediaMeasurement.segments.seek, v = document.querySelector('#media');
      return s && s.seekedAt && !v.seeking && v.currentTime >= s.target + 0.1;
    }, null, {timeout: LIMITS.recoveryMs});
    await page.waitForTimeout(LIMITS.seekPlaybackMs);
    await page.locator('#pause').click();
    report.measurement = await page.evaluate(() => ({...window.mediaMeasurement,
      durationSeconds: document.querySelector('#media').duration,
      finalCurrentTime: document.querySelector('#media').currentTime,
      finalPaused: document.querySelector('#media').paused}));
    const measured = report.measurement;
    assert.equal(report.externalRequests.length, 0);
    assert.equal(report.browserErrors.length, 0);
    assert.equal(measured.errors.length, 0);
    assert(measured.samples.some(s => !s.paused && s.mediaTime > 0.25));
    assert(measured.segments.seek.seekedAt >= measured.segments.seek.requestedAt);
    if (measured.frameApiAvailable) {
      assert(measured.segments.initial.firstPresentedFrame && measured.segments.seek.firstPresentedFrame);
      for (const segment of [measured.segments.initial, measured.segments.seek]) {
        assert(segment.firstPresentedFrame.width > 0 && segment.firstPresentedFrame.height > 0);
        assert(Number.isFinite(segment.firstPresentedFrame.mediaTime));
      }
      report.presentedFirstFrameCovered = true;
    } else { report.presentedFirstFrameCovered = false; report.firstFrameUnavailableReason = 'requestVideoFrameCallback_not_supported'; }
    report.loadeddataCovered = measured.loadeddataAt !== null;
    report.playingEventIntervalsMs = measured.playingIntervals.reduce((total, p) => total + p.end - p.start, 0);
    report.playingEventIntervalDefinition = 'Raw playing-event intervals end on waiting/stalled/seeking/pause/ended/error; they are not measured rendered watch time';
    report.timing = timingSummary(measured);
    report.waitingEvents = measured.events.filter(e => e.name === 'waiting');
    report.stalledEvents = measured.events.filter(e => e.name === 'stalled');
    report.realSeekRecovered = true;
    report.localBrowserMediaCovered = true;
    await page.screenshot({path: screenshot, fullPage: true});
    report.screenshot = {path: path.relative(ROOT, screenshot), sha256: sha(fs.readFileSync(screenshot))};
    report.status = 'local-browser-media-component-passed';
  } catch (error) {
    report.status = interrupted ? 'interrupted' : 'local-browser-media-component-failed';
    report.localBrowserMediaCovered = false;
    report.error = {name: error.name, code: error.code || null, message: String(error.message).slice(0, 800)};
    process.exitCode = 1;
  } finally {
    let browserClosed = !browser;
    if (context) await context.close().catch(() => {});
    if (browser) await browser.close().then(() => { browserClosed = true; }).catch(() => {});
    await Promise.all([...streams].map(stream => new Promise(resolve => {
      stream.once('close', resolve); stream.destroy();
    })));
    let serverClosed = !server;
    if (server) {
      server.closeAllConnections();
      await new Promise(resolve => server.close(() => { serverClosed = true; resolve(); }));
    }
    process.removeListener('SIGINT', interrupt); process.removeListener('SIGTERM', interrupt);
    report.cleanup = {browserCloseConfirmed: browserClosed, ownedHttpServerClosed: serverClosed,
      ownedServerListening: server ? server.listening : false,
      managedStreamsRemaining: streams.size, privateVarsFilesCreated: 0};
    report.sourceUnchanged = sha(fs.readFileSync(__filename)) === sourceBefore;
    report.commonVerifierUnchanged = sha(fs.readFileSync(verifierFile)) === verifierBefore;
    report.mediaUnchanged = sha(fs.readFileSync(MEDIA)) === mediaBefore;
    report.componentPassed = report.localBrowserMediaCovered && browserClosed && serverClosed &&
      streams.size === 0 && report.sourceUnchanged && report.commonVerifierUnchanged && report.mediaUnchanged;
    if (!report.componentPassed) { report.status = 'local-browser-media-component-failed'; process.exitCode = 1; }
    report.finishedAt = new Date().toISOString();
    report.runtime.freeMemoryAfterBytes = os.freemem();
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
    console.log(JSON.stringify({report: path.relative(ROOT, output), sha256: sha(fs.readFileSync(output)),
      status: report.status, localBrowserMediaCovered: report.localBrowserMediaCovered, productionEnabled: false}));
  }
}

if (require.main === module) {
  const entries = process.argv.slice(2).map(arg => {
    assert(arg.startsWith('--'));
    const at = arg.indexOf('=');
    return at < 0 ? [arg.slice(2), true] : [arg.slice(2, at), arg.slice(at + 1)];
  });
  assert.equal(new Set(entries.map(([name]) => name)).size, entries.length, 'Duplicate arguments forbidden');
  const args = Object.fromEntries(entries);
  if (Object.keys(args).length === 0) console.log(JSON.stringify({status: 'prepared-not-run',
    actualMediaRuns: 0, actualServices: 0, requiresExplicitRootOrder: true,
    componentOnly: true, productionEnabled: false, fixedMedia: MEDIA_RELATIVE, limits: LIMITS}));
  else execute(args).catch(error => { console.error(JSON.stringify({status: 'gate-refused-or-early-failed',
    errorCode: error.code || error.name, productionEnabled: false})); process.exitCode = 1; });
}

module.exports = {rangeFor, LIMITS};
