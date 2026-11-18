'use strict';
// PREPARED ONLY. The default/import path never starts a process, browser, or network call.
// Actual execution requires the immutable Stage30 parent, the separate actual repair proof,
// and an explicit operator window. Loopback backend evidence is not APP/CDN/device evidence.
const fs = require('node:fs'), path = require('node:path'), os = require('node:os');
const crypto = require('node:crypto'), assert = require('node:assert/strict');
const {spawn, execFile} = require('node:child_process'), {promisify} = require('node:util');
const {performance} = require('node:perf_hooks');
const exec = promisify(execFile);
const ROOT = path.resolve(__dirname, '..'), CLOUD = path.join(ROOT, '04_研发源码/app/cloud');
const BACKEND = path.join(ROOT, '04_研发源码/app/r4/backend');
const PREFIX = '负责人优化建议-本地可靠性后端媒体';
const RUNTIME = path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies');
const PYTHON = path.join(RUNTIME, 'python/python.exe');
const NODE_MODULES = path.join(RUNTIME, 'node/node_modules');
const MEDIA_RELATIVE = '04_研发源码/app/r4/images/community-preview.mp4';
const MEDIA = path.join(ROOT, MEDIA_RELATIVE);
const PARENT_PROOF = path.join(__dirname, '负责人优化建议-卡组迁移-最终交付核验.json');
const PARENT_SHA = '752e36ad70d6812727849f0fa49262c426ef161a911b59f66831cd0617e12f07';
const VERIFIER = path.join(__dirname, '负责人优化建议-本地可靠性修复基线.cjs');
const LIMITS = Object.freeze({samples: 5, startupMs: 60000, apiMs: 30000, authGapMs: 3100,
  playbackMs: 6000, seekPlaybackMs: 3000, recoveryMs: 15000, maximumSamples: 5000,
  maximumMediaRequestsPerSample: 200, viewport: {width: 1280, height: 800}});
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const alive = pid => {try {process.kill(pid, 0); return true;} catch {return false;}};
function inside(file, folder) {const relative = path.relative(folder, path.resolve(file)); return relative && !relative.startsWith('..') && !path.isAbsolute(relative);}
function parseArgs(argv) {
  const entries = argv.map(value => {assert(value.startsWith('--')); const at = value.indexOf('=');
    return at < 0 ? [value.slice(2), true] : [value.slice(2, at), value.slice(at + 1)];});
  assert.equal(new Set(entries.map(([key]) => key)).size, entries.length);
  return Object.fromEntries(entries);
}
const args = require.main === module ? parseArgs(process.argv.slice(2)) : {};
function minimalEnv(extra = {}) {
  const env = {};
  for (const key of ['SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC']) if (process.env[key]) env[key] = process.env[key];
  env.PATH = path.dirname(process.execPath) + path.delimiter + path.dirname(PYTHON);
  return {...env, ...extra};
}
async function ownedProcessTree(parent) {
  assert.equal(process.platform, 'win32', 'This prepared process cleanup targets this Windows lab only');
  const script = '$all=@(Get-CimInstance Win32_Process);$ids=[System.Collections.Generic.HashSet[int]]::new();[void]$ids.Add(' + Number(parent) + ');do{$before=$ids.Count;foreach($row in $all){if($ids.Contains([int]$row.ParentProcessId)){[void]$ids.Add([int]$row.ProcessId)}}}while($ids.Count -gt $before);@($all|Where-Object{$ids.Contains([int]$_.ProcessId)}|Select-Object ProcessId,ParentProcessId,CreationDate,ExecutablePath,Name)|ConvertTo-Json -Compress';
  const result = await exec(path.join(process.env.SystemRoot || 'C:/Windows', 'System32/WindowsPowerShell/v1.0/powershell.exe'),
    ['-NoProfile', '-NonInteractive', '-Command', '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);' + script],
    {windowsHide: true, encoding: 'utf8', timeout: 15000, maxBuffer: 1048576});
  const parsed = result.stdout.trim() ? JSON.parse(result.stdout) : [];
  return (Array.isArray(parsed) ? parsed : [parsed]).filter(row => row.ProcessId !== process.pid).map(row => ({
    pid: row.ProcessId, parentPid: row.ParentProcessId, creationDate: row.CreationDate, name: row.Name,
    executable: row.ExecutablePath || null,
    executableSha256: row.ExecutablePath && fs.existsSync(row.ExecutablePath) ? sha(fs.readFileSync(row.ExecutablePath)) : null}));
}

/* Native factory copied as source, never require() the load driver's automatic CLI. */
async function nativeCloudServer(){
 assert.deepEqual(Object.keys(args).sort(),['cloud-server','run','state'].sort());assert(typeof process.send==='function'&&/^[a-f0-9]{32}:[a-f0-9]{64}$/.test(process.env.EW_LOCAL_RELIABILITY_DEMO_HASH||''),'Private owned IPC child only');
 const state=path.resolve(String(args.state||''));assert(inside(state,path.join(CLOUD,'.wrangler'))&&path.basename(state).startsWith(PREFIX+'隔离-cloud-'));assert(!fs.existsSync(state),'Fresh owned state only');assert(/^[a-f0-9]{32}$/.test(String(args.run||'')));fs.mkdirSync(state,{recursive:true});
 const esbuild=require(path.join(CLOUD,'node_modules/esbuild')),{Miniflare,Log,LogLevel}=require(path.join(CLOUD,'node_modules/miniflare')),bundle=path.join(state,'native-entry.mjs');
 const platformDir=path.join(CLOUD,'node_modules/@esbuild',process.platform+'-'+process.arch),dependencyFiles=[path.join(CLOUD,'node_modules/esbuild/lib/main.js'),path.join(CLOUD,'node_modules/esbuild/package.json'),path.join(platformDir,'package.json'),path.join(platformDir,process.platform==='win32'?'esbuild.exe':'bin/esbuild'),require.resolve(path.join(CLOUD,'node_modules/miniflare')),path.join(CLOUD,'node_modules/miniflare/package.json')],runtimeDependencyHashes=Object.fromEntries(dependencyFiles.map(file=>{assert(inside(file,path.join(CLOUD,'node_modules'))&&fs.existsSync(file));return[path.relative(ROOT,file).replaceAll('\\','/'),sha(fs.readFileSync(file))];}));
 const contents="import {handleAPI} from './lib/eastern-api';import schema from './drizzle/0000_lethal_lucky_pierre.sql';let ready;export default{async fetch(request,env){if(!ready)ready=env.DB.batch(schema.split('--> statement-breakpoint').filter(s=>s.trim()).map(s=>env.DB.prepare(s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '))));await ready;return handleAPI(request,env);}}";
 const compiled=await esbuild.build({absWorkingDir:CLOUD,stdin:{contents,resolveDir:CLOUD,sourcefile:'owned-local-reliability-entry.ts'},outfile:bundle,bundle:true,format:'esm',platform:'browser',target:'es2022',metafile:true,loader:{'.html':'text','.sql':'text'},logLevel:'silent',plugins:[{name:'actual-raw-source',setup(b){b.onResolve({filter:/\?raw$/},a=>({path:path.resolve(a.resolveDir,a.path.slice(0,-4)),namespace:'raw'}));b.onLoad({filter:/.*/,namespace:'raw'},a=>({contents:fs.readFileSync(a.path,'utf8'),loader:'text'}));}}]});const metafile=bundle+'.metafile.json';fs.writeFileSync(metafile,JSON.stringify(compiled.metafile)+'\n');
 const inputHashes=Object.fromEntries(Object.keys(compiled.metafile.inputs).filter(name=>name!=='owned-local-reliability-entry.ts').map(name=>{const stripped=name.replace(/^raw:/,'');const file=path.isAbsolute(stripped)?stripped:path.resolve(CLOUD,stripped);assert(inside(file,ROOT));return[path.relative(ROOT,file).replaceAll('\\','/'),sha(fs.readFileSync(file))];}));
 const native=new Miniflare({modules:true,scriptPath:bundle,compatibilityDate:'2026-05-15',compatibilityFlags:['nodejs_compat'],host:'127.0.0.1',port:0,d1Databases:['DB'],d1Persist:path.join(state,'d1'),r2Buckets:['BUCKET'],r2Persist:path.join(state,'r2'),bindings:{DEMO_ADMIN_HASH:process.env.EW_LOCAL_RELIABILITY_DEMO_HASH},log:new Log(LogLevel.ERROR)});let closing=false;
 process.on('message',async m=>{if(m?.action==='stop-owned-runtime'&&!closing){closing=true;await native.dispose();process.exit(0);}});process.on('disconnect',async()=>{if(!closing){closing=true;await native.dispose();process.exit(1);}});
 for(const[name,digest]of Object.entries(runtimeDependencyHashes))assert.equal(sha(fs.readFileSync(path.join(ROOT,name))),digest);process.send({kind:'native-local-cloud-ready',base:(await native.ready).origin,pid:process.pid,bundle:path.relative(ROOT,bundle),bundleSha256:sha(fs.readFileSync(bundle)),metafile:path.relative(ROOT,metafile),metafileSha256:sha(fs.readFileSync(metafile)),inputHashes,runtimeDependencyHashes,toolchainIncludedInHandoff:false,embeddedNativeAdapterSha256:sha(contents),adapterContainedInOwnHelper:true,esbuildVersion:esbuild.version,miniflareVersion:require(path.join(CLOUD,'node_modules/miniflare/package.json')).version,nativeWorkerd:true,frameworkAdapterCovered:false});
}

/* Browser event collection is the actual existing component HTML, with a backend URL. */
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

function percentile(values, fraction) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.ceil(sorted.length * fraction) - 1];
}
function metric(values) {
  assert(values.every(Number.isFinite));
  return {n: values.length, values, p50Ms: percentile(values, 0.5), p95Ms: percentile(values, 0.95),
    p99Ms: percentile(values, 0.99), minimumMs: values.length ? Math.min(...values) : null,
    maximumMs: values.length ? Math.max(...values) : null};
}
function summarize(samples) {
  const metrics = {
    firstPresentedFrameFromNativePlay: metric(samples.map(row => row.timing.presentedFirstFrame.elapsedFromNativePlayRequestMs)),
    loadeddataFromContentSetRequest: metric(samples.map(row => row.loadeddataFromContentSetRequestMs)),
    loadeddataRelativeToNativePlay: metric(samples.map(row => row.timing.loadeddata.elapsedRelativeToNativePlayRequestMs)),
    seekedEventFromNativeSeek: metric(samples.map(row => row.timing.seek.seekedEventLatencyMs)),
    presentedFrameRecoveryFromNativeSeek: metric(samples.map(row => row.timing.seek.presentedFrameRecoveryLatencyMs)),
    firstMediaRequestTTFB: metric(samples.map(row => row.firstMediaRequestTTFBMs))
  };
  for (const value of Object.values(metrics)) assert.equal(value.n, LIMITS.samples);
  return {sampleCount: samples.length, metrics,
    percentileMethod: 'nearest-rank: sorted[ceil(n*p)-1]; n=5 per metric, therefore P95/P99 equal the maximum of these five actual samples',
    waitingEventCount: samples.reduce((n, row) => n + row.timing.waiting.waitingEventCount, 0),
    stalledNetworkEventCount: samples.reduce((n, row) => n + row.timing.waiting.stalledNetworkEventCount, 0),
    observedWaitingMilliseconds: samples.reduce((n, row) => n + row.timing.waiting.observedWaitingMilliseconds, 0),
    scriptedObservationSpanMs: samples.reduce((n, row) => n + row.timing.waiting.scriptedObservationSpanMs, 0),
    professionalStallRateClaimed: false, countryOrDeviceLatencyClaimed: false};
}
function currentHashes(expected) {
  return Object.fromEntries(Object.keys(expected).map(relative => {
    const file = path.resolve(ROOT, relative);
    assert(!path.isAbsolute(relative) && inside(file, ROOT));
    return [relative, sha(fs.readFileSync(file))];
  }));
function verifyGates(options) {
  assert.deepEqual(Object.keys(options).sort(), ['probe-authenticated-backend-media', 'target', 'stage30-proof',
    'proof-sha256', 'repair-proof-sha256', 'repair-authorization-sha256'].sort());
  assert.equal(options['probe-authenticated-backend-media'], true);
  assert(['python', 'cloud'].includes(options.target));
  assert.equal(path.resolve(options['stage30-proof']), PARENT_PROOF);
  assert.equal(options['proof-sha256'], PARENT_SHA);
  assert.equal(sha(fs.readFileSync(PARENT_PROOF)), PARENT_SHA);
  const parent = JSON.parse(fs.readFileSync(PARENT_PROOF, 'utf8'));
  assert(parent.stage === 30 && parent.pass === true && parent.productionEnabled === false);
  assert.equal(parent.allFourteenGatesPassedWithFreshSuccessfulChildren, true);
  assert.deepEqual(parent.perBackendPassed, {Python: 195, Cloud: 195});
  const repair = require(VERIFIER).verifyRepairProof(options['repair-proof-sha256'], options['repair-authorization-sha256']);
  assert.equal(repair.authorization.originalStage30ProductUnchanged, false);
  assert.deepEqual(Object.keys(repair.authorization.authorizedProductChanges), ['04_研发源码/app/r4/backend/server.py']);
  const expected = repair.repairProof.reportIdentityHashes;
  assert.deepEqual(currentHashes(expected), expected);
  assert.equal(parent.verifiedSHA256[MEDIA_RELATIVE], sha(fs.readFileSync(MEDIA)));
  return {repair, expected, parent: {path: path.relative(ROOT, PARENT_PROOF).replaceAll('\\', '/'), sha256: PARENT_SHA,
    stage: 30, immutableParent: true, currentProductUnchangedFromOriginalStage30: false,
    boundary: 'Only the separate actual passing repair proof authorizes its preserved server.py delta'}};
}
function hashOnlyLog(stream, name, observations) {
  const digest = crypto.createHash('sha256');
  const row = observations[name] = {bytes: 0, sha256: null, ended: false, rawTextPersisted: false};
  stream.on('data', bytes => {row.bytes += bytes.length; digest.update(bytes);});
  stream.once('end', () => {row.sha256 = digest.digest('hex'); row.ended = true;});
}
async function execute(options) {
  const gate = verifyGates(options), target = options.target;
  const runId = crypto.randomUUID().replaceAll('-', ''), baseName = PREFIX + '-' + target + '-' + runId;
  const output = path.join(__dirname, baseName + '.json');
  const db = path.join(__dirname, PREFIX + '隔离-python-' + runId + '.sqlite3');
  const state = path.join(CLOUD, '.wrangler', PREFIX + '隔离-cloud-' + runId);
  for (const file of [output, db, state]) assert(!fs.existsSync(file), 'Fresh run resources only');
  const toolSha = sha(fs.readFileSync(__filename)), verifierSha = sha(fs.readFileSync(VERIFIER));
  const media = fs.readFileSync(MEDIA), mediaSha = sha(media);
  const report = {schemaVersion: 1, stage: 31, runId, target, role: target === 'python' ? 'mediaPython' : 'mediaCloud',
    status: 'prepared-component-started-not-acceptance', componentOnly: true, componentPassed: false, pass: false,
    startedAt: new Date().toISOString(), productionEnabled: false, formalAcceptance: false,
    stage30Proof: gate.parent, repairProof: gate.repair.repairProof, repairAuthorization: gate.repair.authorization,
    sourceAndBuildHashes: gate.expected,
    tool: {path: path.relative(ROOT, __filename).replaceAll('\\', '/'), sha256: toolSha,
      commonVerifier: {path: path.relative(ROOT, VERIFIER).replaceAll('\\', '/'), sha256: verifierSha}},
    limits: LIMITS, input: {path: MEDIA_RELATIVE, sha256: mediaSha, bytes: media.length, existingFixedRepositoryAsset: true},
    scope: {actualAuthenticatedBackendMediaApi: true, nativeLocalCloud: target === 'cloud',
      frameworkAdapterCovered: false, appPlayerIntegrationCovered: false, cdnCovered: false,
      targetCountryCovered: false, physicalMobileCovered: false, loadTestCovered: false,
      realSupplierCovered: false, backendAndBrowserOnSameMachine: true, loopbackOnly: true},
    runtime: {nodeVersion: process.version, nodeExecutableSha256: sha(fs.readFileSync(process.execPath)),
      pythonExecutableSha256: sha(fs.readFileSync(PYTHON)), cpuModel: os.cpus()[0]?.model || null,
      logicalProcessors: os.cpus().length, totalMemoryBytes: os.totalmem(), freeMemoryBeforeBytes: os.freemem()},
    runtimeArtifacts: [], accounts: [], setup: [], authorizationProof: {}, samples: [],
    externalRequests: [], browserErrors: [], serviceObservation: {}};
  let child, base, startupError = null, childClosed, expectedStop = false, browser, interrupted = false;
  let tracked = [], lastAuth = -Infinity, liveBrowserContexts = 0;
  const apiContexts = [], browserContexts = [];
  const stop = () => {interrupted = true; if (browser) browser.close().catch(() => {});};
  process.once('SIGINT', stop); process.once('SIGTERM', stop);
  const temporaryAdminPassword = crypto.randomBytes(24).toString('base64url'), salt = crypto.randomBytes(16);
  const demoHash = salt.toString('hex') + ':' + crypto.pbkdf2Sync(temporaryAdminPassword, salt, 100000, 32, 'sha256').toString('hex');
  let prepared = false;
  try {
    if (target === 'python') {
      report.ownedDatabase = path.relative(ROOT, db);
      child = spawn(PYTHON, ['-B', path.join(BACKEND, 'server.py'), '--port', '0', '--db', db,
        '--web-root', path.join(ROOT, '03_当前APP')],
      {cwd: ROOT, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: minimalEnv()});
      let pending = '';
      child.stdout.on('data', bytes => {pending = (pending + bytes.toString()).slice(-8192);
        const found = pending.match(/APP: (http:\/\/127\.0\.0\.1:\d+)/); if (found) base = found[1];});
    } else {
      report.ownedState = path.relative(ROOT, state);
      child = spawn(process.execPath, [__filename, '--cloud-server', '--state=' + state, '--run=' + runId],
        {cwd: ROOT, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
          env: minimalEnv({EW_LOCAL_RELIABILITY_DEMO_HASH: demoHash})});
      child.on('message', message => {
        if (message?.kind === 'native-local-cloud-ready') {
          try {
            for (const [name, digest] of Object.entries(message.inputHashes)) assert.equal(gate.expected[name], digest);
            report.runtime.nativeCloud = message;
            report.runtimeArtifacts = [{bundle: message.bundle, bundleSha256: message.bundleSha256,
              metafile: message.metafile, metafileSha256: message.metafileSha256,
              inputHashes: message.inputHashes, runtimeDependencyHashes: message.runtimeDependencyHashes}];
            base = message.base;
          } catch {startupError = 'actual_native_compiler_binding_mismatch';}
        } else if (message?.kind === 'native-local-cloud-startup-failed') startupError = 'actual_native_cloud_startup_failed';
      });
    }
    child.once('error', error => {startupError = 'owned_spawn_failed';
      report.runtime.spawnFailure = {code: typeof error.code === 'string' ? error.code : 'SPAWN_ERROR'};});
    hashOnlyLog(child.stdout, 'stdout', report.serviceObservation);
    hashOnlyLog(child.stderr, 'stderr', report.serviceObservation);
    childClosed = new Promise(resolve => child.once('close', resolve));
    child.once('exit', (code, signal) => {report.runtime.serviceExit = {code, signal, at: new Date().toISOString(), expected: expectedStop};
      if (!expectedStop) startupError = 'owned_service_exited';});
    report.ownedServerPid = child.pid;
    const deadline = Date.now() + LIMITS.startupMs;
    while (!base) {assert(!startupError, startupError); assert(!interrupted && Date.now() < deadline, 'owned_startup_deadline'); await wait(100);}
    const origin = new URL(base); assert.equal(origin.hostname, '127.0.0.1');
    assert(Number(origin.port) > 0 && ![8877, 8878, 8879, 8880, 8881].includes(Number(origin.port)));
    report.base = origin.origin; base = origin.origin;
    const playwrightPath = require.resolve(path.join(NODE_MODULES, 'playwright'));
    const {request, chromium} = require(playwrightPath);
    report.runtime.playwrightEntry = {path: playwrightPath, sha256: sha(fs.readFileSync(playwrightPath))};
    report.runtime.browserExecutable = {path: chromium.executablePath(), sha256: sha(fs.readFileSync(chromium.executablePath()))};
    const makeApi = async () => {const context = await request.newContext({baseURL: base, timeout: LIMITS.apiMs,
      extraHTTPHeaders: {Accept: 'application/json'}}); apiContexts.push(context); return context;};
    const anonymous = await makeApi(), owner = await makeApi(), other = await makeApi();
    const json = async (context, route, method = 'GET', data) => {
      assert(route.startsWith('/api/') && !route.includes('://'));
      const response = await context.fetch(route, {method, ...(data === undefined ? {} : {data}), maxRedirects: 0});
      report.setup.push({route, method, status: response.status()});
      assert.equal(response.status(), 200, 'Actual setup request rejected: ' + route);
      return response.json();
    };
    assert.equal((await json(anonymous, '/api/health')).ok, true);
    const auth = async (context, route, data) => {
      await wait(Math.max(0, lastAuth + LIMITS.authGapMs - performance.now()));
      assert(!interrupted); lastAuth = performance.now(); return json(context, route, 'POST', data);
    };
    if (target === 'python') {
      const admin = await makeApi();
      await auth(admin, '/api/auth/setup', {username: 'media_admin_' + runId.slice(0, 8),
        password: temporaryAdminPassword, name: '媒体组件合成管理员'});
    }
    for (const [index, context] of [owner, other].entries()) {
      const value = await auth(context, '/api/auth/register', {username: 'media_' + runId.slice(0, 8) + '_' + index,
        password: crypto.randomBytes(24).toString('base64url'), name: '媒体组件合成用户' + index});
      const status = await json(context, '/api/auth/status');
      assert.equal(status.user.id, value.user.id); assert.equal(status.user.role, 'user');
      report.accounts.push({index, accountId: status.user.id, role: status.user.role, currentAuthVerified: true});
    }
    assert.notEqual(report.accounts[0].accountId, report.accounts[1].accountId);
    const ownerStorage = await owner.storageState(), otherStorage = await other.storageState();
    const session = storage => storage.cookies.find(cookie => cookie.name === 'ew_session')?.value;
    assert(session(ownerStorage) && session(otherStorage)); assert.notEqual(session(ownerStorage), session(otherStorage));
    report.uniqueAuthenticatedSessions = 2; report.storageStatePersistedToDisk = false;
    const uploadResponse = await owner.post('/api/media', {data: media, headers: {'Content-Type': 'video/mp4',
      'Content-Length': String(media.length), 'X-Filename': 'local-authenticated-media-fixture.mp4'}, maxRedirects: 0});
    assert.equal(uploadResponse.status(), 200); const uploaded = await uploadResponse.json();
    assert.equal(uploaded.size, media.length); assert.equal(uploaded.mime, 'video/mp4');
    assert(/^[a-f0-9-]{36}$/.test(uploaded.id)); assert.equal(uploaded.url, '/api/media/' + uploaded.id);
    report.authorizationProof.upload = {status: 200, mediaId: uploaded.id, url: uploaded.url,
      bytes: uploaded.size, mime: uploaded.mime, sourceSha256: mediaSha};
    const readMedia = async (context, range) => {
      const started = performance.now(), response = await context.get(uploaded.url,
        {maxRedirects: 0, headers: range ? {Range: range} : {}});
      const bytes = await response.body();
      return {status: response.status(), bytes: bytes.length, sha256: sha(bytes),
        contentType: response.headers()['content-type'] || null, contentRange: response.headers()['content-range'] || null,
        cacheControl: response.headers()['cache-control'] || null, elapsedMs: performance.now() - started};
    };
    const full = await readMedia(owner), range = await readMedia(owner, 'bytes=0-1023');
    assert.equal(full.status, 200); assert.equal(full.bytes, media.length); assert.equal(full.sha256, mediaSha);
    assert.equal(range.status, 206); assert.equal(range.bytes, 1024); assert.equal(range.sha256, sha(media.subarray(0, 1024)));
    assert.equal(range.contentRange, 'bytes 0-1023/' + media.length);
    assert(full.contentType?.startsWith('video/mp4') && range.contentType?.startsWith('video/mp4'));
    assert(full.cacheControl?.includes('private') && full.cacheControl?.includes('no-store'));
    report.authorizationProof.ownerFull = full; report.authorizationProof.ownerRange = range;
    for (const [name, context] of [['anonymous', anonymous], ['otherOwner', other]]) {
      const deniedFull = await readMedia(context), deniedRange = await readMedia(context, 'bytes=0-1023');
      for (const denied of [deniedFull, deniedRange]) {
        assert.equal(denied.status, 403); assert(!denied.contentType?.startsWith('video/'));
        assert.notEqual(denied.sha256, mediaSha); assert.notEqual(denied.sha256, sha(media.subarray(0, 1024)));
      }
      report.authorizationProof[name] = {full: deniedFull, range: deniedRange};
    }
    report.authorizationProof.verified = true;
    browser = await chromium.launch({headless: true}); report.runtime.browserVersion = browser.version();
    tracked = await ownedProcessTree(process.pid);
    for (let index = 0; index < LIMITS.samples; index++) {
      assert(!interrupted && !startupError && alive(child.pid));
      const context = await browser.newContext({storageState: ownerStorage, viewport: LIMITS.viewport,
        serviceWorkers: 'block'}); browserContexts.push(context); liveBrowserContexts++;
      const page = await context.newPage();
      const cdp = await context.newCDPSession(page);
      await cdp.send('Network.enable'); await cdp.send('Network.setCacheDisabled', {cacheDisabled: true});
      const sample = {index, cacheDisabled: true, isolatedBrowserContext: true, backendSessionOwnerIndex: 0,
        mediaRequests: [], errors: []}; report.samples.push(sample);
      const pendingRequests = new Map();
      page.on('pageerror', error => {sample.errors.push({kind: 'pageerror', name: error.name}); report.browserErrors.push({sample: index, name: error.name});});
      await context.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== base) {report.externalRequests.push({protocol: url.protocol, hostname: url.hostname}); return route.abort();}
        return route.continue();
      });
      page.on('request', request => {
        if (request.url() !== base + uploaded.url) return;
        assert(sample.mediaRequests.length < LIMITS.maximumMediaRequestsPerSample);
        const row = {method: request.method(), path: uploaded.url, range: request.headers().range || null,
          status: null, completed: false, failure: null, timing: null};
        sample.mediaRequests.push(row); pendingRequests.set(request, row);
      });
      page.on('response', response => {
        const row = pendingRequests.get(response.request()); if (!row) return;
        row.status = response.status(); row.timing = response.request().timing();
        row.contentRange = response.headers()['content-range'] || null;
        row.contentType = response.headers()['content-type'] || null;
        row.fromServiceWorker = response.fromServiceWorker();
      });
      page.on('requestfinished', request => {const row = pendingRequests.get(request); if (row) {row.completed = true; row.timing = request.timing();}});
      page.on('requestfailed', request => {const row = pendingRequests.get(request); if (row) {row.failure = request.failure()?.errorText || 'request_failed'; row.timing = request.timing();}});
      const navigated = await page.goto(base + '/api/health', {waitUntil: 'domcontentloaded', timeout: LIMITS.startupMs});
      assert.equal(navigated.status(), 200); assert.equal(new URL(page.url()).origin, base);
      sample.documentOriginVerified = true; sample.contentSetRequestedAt = await page.evaluate(() => performance.now());
      await page.setContent(HTML.replace('src="/media.mp4"', 'src="' + uploaded.url + '"')
        .replace('本机合成媒体计时组件', '本机后端鉴权媒体计时组件')
        .replace('仅测固定本地 MP4 的浏览器播放与跳转。', '固定 MP4 经本人真实会话读取实际后端媒体接口，测浏览器播放与跳转。'), {waitUntil: 'domcontentloaded'});
      await page.waitForFunction(() => Number.isFinite(document.querySelector('#media').duration) && document.querySelector('#media').duration > 2,
        null, {timeout: LIMITS.startupMs});
      await page.locator('#play').click();
      await page.waitForFunction(() => document.querySelector('#media').currentTime > 0.25, null, {timeout: LIMITS.recoveryMs});
      await page.waitForTimeout(LIMITS.playbackMs);
      await page.locator('#seek').click();
      await page.waitForFunction(() => {const s = window.mediaMeasurement.segments.seek, v = document.querySelector('#media');
        return s && s.seekedAt && !v.seeking && v.currentTime >= s.target + 0.1;}, null, {timeout: LIMITS.recoveryMs});
      await page.waitForTimeout(LIMITS.seekPlaybackMs); await page.locator('#pause').click();
      sample.measurement = await page.evaluate(() => ({...window.mediaMeasurement,
        durationSeconds: document.querySelector('#media').duration, finalCurrentTime: document.querySelector('#media').currentTime,
        finalPaused: document.querySelector('#media').paused}));
      assert.equal(sample.errors.length, 0); assert.equal(sample.measurement.errors.length, 0);
      assert.equal(sample.measurement.frameApiAvailable, true, 'Presented-frame evidence requires actual RVFC');
      for (const segment of [sample.measurement.segments.initial, sample.measurement.segments.seek]) {
        assert(segment.firstPresentedFrame && segment.firstPresentedFrame.width > 0 && segment.firstPresentedFrame.height > 0);
        assert(Number.isFinite(segment.firstPresentedFrame.mediaTime) && segment.firstPresentedFrame.elapsedFromRequestMs >= 0);
      }
      assert(sample.measurement.samples.some(row => !row.paused && row.mediaTime > 0.25));
      sample.timing = timingSummary(sample.measurement);
      sample.loadeddataFromContentSetRequestMs = sample.measurement.loadeddataAt - sample.contentSetRequestedAt;
      assert(Number.isFinite(sample.measurement.loadeddataAt) && sample.loadeddataFromContentSetRequestMs >= 0);
      await wait(100);
      const requests = sample.mediaRequests.filter(row => Number.isFinite(row.timing?.responseStart) && row.timing.responseStart >= 0)
        .sort((left, right) => left.timing.startTime - right.timing.startTime);
      assert(requests.length > 0); assert(requests.every(row => [200, 206].includes(row.status) && row.fromServiceWorker === false));
      assert(requests.some(row => row.status === 206 && row.range), 'Browser must actually read the authenticated Range endpoint');
      sample.firstMediaRequestTTFBMs = requests[0].timing.responseStart;
      sample.ttfbDefinition = 'Playwright Request.timing.responseStart: first response byte offset from that actual media request start; cookies never exported';
      const capture = path.join(__dirname, baseName + '-sample-' + index + '.png');
      await page.screenshot({path: capture, fullPage: false});
      sample.capture = {path: path.relative(ROOT, capture), sha256: sha(fs.readFileSync(capture))};
      sample.passed = true;
      await context.close(); liveBrowserContexts--; browserContexts.pop();
      console.log(JSON.stringify({role: report.role, phase: 'actual-authenticated-media-sample', completed: index + 1, total: LIMITS.samples}));
    }
    assert.equal(report.samples.length, LIMITS.samples); assert.equal(report.externalRequests.length, 0);
    report.summary = summarize(report.samples); prepared = true;
  } catch (error) {
    report.error = {name: error.name, code: typeof error.code === 'string' ? error.code : null,
      message: String(error.message).replace(/ew_session=[^;\s"']+/gi, 'ew_session=[REDACTED]').slice(0, 500)};
    report.status = interrupted ? 'interrupted-authenticated-backend-media' : 'authenticated-backend-media-failed';
    process.exitCode = 1;
  } finally {
    try {
      const latest = await ownedProcessTree(process.pid), union = new Map([...tracked, ...latest].map(row => [row.pid + ':' + row.creationDate, row]));
      tracked = [...union.values()]; report.runtime.trackedOwnedProcessUnion = tracked;
    } catch {report.runtime.cleanupInventoryUnavailable = true;}
    let browserClosed = !browser;
    for (const context of browserContexts) await context.close().catch(() => {});
    if (browser) await browser.close().then(() => {browserClosed = true; liveBrowserContexts = 0;}).catch(() => {});
    let apiContextsDisposed = 0;
    for (const context of apiContexts) await context.dispose().then(() => {apiContextsDisposed++;}).catch(() => {});
    expectedStop = true;
    if (child && child.exitCode === null && child.signalCode === null) {
      if (target === 'cloud' && child.connected) child.send({action: 'stop-owned-runtime'});
      else child.kill();
      for (let index = 0; index < 150 && child.exitCode === null && child.signalCode === null; index++) await wait(100);
      if (child.exitCode === null && child.signalCode === null) child.kill();
    }
    if (childClosed) await Promise.race([childClosed, wait(3000)]);
    process.removeListener('SIGINT', stop); process.removeListener('SIGTERM', stop);
    const remaining = tracked.filter(row => alive(row.pid)).map(row => row.pid);
    report.cleanup = {browserCloseConfirmed: browserClosed, browserContextsRemaining: liveBrowserContexts,
      apiContextsCreated: apiContexts.length, apiContextsDisposed, ownedServerStillAlive: child?.pid ? alive(child.pid) : false,
      remainingOwnedPids: remaining, ownedProcessInventoryComplete: report.runtime.cleanupInventoryUnavailable !== true,
      privateVarsFilesCreated: 0, privateVarsRemaining: fs.existsSync(path.join(state, '.dev.vars')) ? 1 : 0,
      windowsPythonCleanupUsesOwnedProcessTermination: target === 'python'};
    report.sourceUnchanged = sha(fs.readFileSync(__filename)) === toolSha && sha(fs.readFileSync(VERIFIER)) === verifierSha;
    try {assert.deepEqual(currentHashes(gate.expected), gate.expected);} catch {report.sourceUnchanged = false;}
    report.mediaUnchanged = sha(fs.readFileSync(MEDIA)) === mediaSha;
    report.finishedAt = new Date().toISOString(); report.runtime.freeMemoryAfterBytes = os.freemem();
    report.componentPassed = prepared && browserClosed && !liveBrowserContexts && apiContextsDisposed === apiContexts.length &&
      !report.cleanup.ownedServerStillAlive && !remaining.length && report.cleanup.ownedProcessInventoryComplete &&
      !report.cleanup.privateVarsRemaining && report.sourceUnchanged && report.mediaUnchanged &&
      Object.values(report.serviceObservation).every(row => row.ended);
    report.pass = report.componentPassed;
    report.status = report.componentPassed ? 'actual-authenticated-backend-media-passed' : 'authenticated-backend-media-failed';
    if (!report.componentPassed) process.exitCode = 1;
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
    console.log(JSON.stringify({role: report.role, report: path.relative(ROOT, output), sha256: sha(fs.readFileSync(output)),
      pass: report.pass, samples: report.samples.length, formalAcceptance: false, productionEnabled: false, cleanup: report.cleanup}));
  }
}
if (require.main === module) {
  if (args['cloud-server']) nativeCloudServer().catch(() => {
    if (process.send) process.send({kind: 'native-local-cloud-startup-failed'}); process.exit(1);
  });
  else if (Object.keys(args).length === 0 || args.describe === true) {
    assert(Object.keys(args).every(key => key === 'describe'));
    console.log(JSON.stringify({status: 'prepared-not-run', roles: ['mediaPython', 'mediaCloud'], limits: LIMITS,
      actualServices: 0, actualMediaRuns: 0, requiresActualRepairProofAndExplicitExecutionWindow: true, productionEnabled: false}));
  } else execute(args).catch(error => {console.error(JSON.stringify({status: 'gate-refused-or-early-failed',
    errorCode: error.code || error.name, productionEnabled: false})); process.exitCode = 1;});
}
module.exports = {LIMITS, parseArgs, percentile, metric, summarize};
