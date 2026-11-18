'use strict';
// Prepared control component only. Import/default invocation starts no process.
// It interrupts the unchanged two-account interface probe, never the full load sizing.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {spawn, execFile} = require('node:child_process');
const {promisify} = require('node:util');
const {performance} = require('node:perf_hooks');
const {StringDecoder} = require('node:string_decoder');
const os = require('node:os');
const exec = promisify(execFile);
const ROOT = path.resolve(__dirname, '..');
const PREFIX = '负责人优化建议-本地可靠性';
const DRIVER = path.join(__dirname, PREFIX + '登录负载.cjs');
const DRIVER_SHA = 'de8af7755af83e629105f0ad00084baaea82dfbcef519831d14cef7e4011d88d';
const PYTHON = path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
const VERIFIER = path.join(__dirname, PREFIX + '修复基线.cjs');
const PARENT = path.join(__dirname, '负责人优化建议-卡组迁移-最终交付核验.json');
const PARENT_SHA = '752e36ad70d6812727849f0fa49262c426ef161a911b59f66831cd0617e12f07';
const LIMITS = Object.freeze({controllerMs: 180000, pollMs: 25, logReadBytes: 65536, lineBytes: 65536});
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const alive = pid => {try {process.kill(pid, 0); return true;} catch {return false;}};
function argsOf(argv) {
  const result = {};
  for (const value of argv) {
    assert(value.startsWith('--'));
    const at = value.indexOf('='), key = value.slice(2, at < 0 ? undefined : at);
    assert(!Object.hasOwn(result, key));
    result[key] = at < 0 ? true : value.slice(at + 1);
  }
  return result;
}
function minimalEnv() {
  const result = {};
  for (const key of ['SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC']) if (process.env[key]) result[key] = process.env[key];
  result.PATH = [path.dirname(process.execPath),
    path.join(process.env.SystemRoot || 'C:/Windows', 'System32/WindowsPowerShell/v1.0')].join(path.delimiter);
  return result;
}
async function ownedTree(pid) {
  const powershell = path.join(process.env.SystemRoot || 'C:/Windows', 'System32/WindowsPowerShell/v1.0/powershell.exe');
  const script = '$all=@(Get-CimInstance Win32_Process);$ids=[System.Collections.Generic.HashSet[int]]::new();[void]$ids.Add(' + Number(pid) + ');do{$n=$ids.Count;foreach($p in $all){if($ids.Contains([int]$p.ParentProcessId)){[void]$ids.Add([int]$p.ProcessId)}}}while($n -ne $ids.Count);@($all|Where-Object{$ids.Contains([int]$_.ProcessId)}|Select-Object ProcessId,ParentProcessId,CreationDate,Name)|ConvertTo-Json -Compress';
  const response = await exec(powershell, ['-NoProfile', '-NonInteractive', '-Command', '[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);' + script],
    {windowsHide: true, encoding: 'utf8', timeout: 15000, maxBuffer: 1048576});
  const parsed = response.stdout.trim() ? JSON.parse(response.stdout) : [];
  return (Array.isArray(parsed) ? parsed : [parsed]).map(row => ({pid: row.ProcessId,
    parentPid: row.ParentProcessId, creationDate: row.CreationDate, name: row.Name}));
}
function exactRunPaths(message, target, pid) {
  assert.equal(message.phase, 'run-created');
  assert.equal(message.target, target); assert.equal(message.driverPid, pid);
  assert.equal(message.mode, 'interface-component-only');
  assert(/^[a-f0-9]{32}$/.test(message.runId));
  const base = PREFIX + '-' + target + '-interfaces-' + message.runId;
  const relative = suffix => path.relative(ROOT, path.join(__dirname, base + suffix));
  assert.equal(message.controlFile, relative('-stop.json'));
  assert.equal(message.observationFile, relative('-service-observation.ndjson'));
  assert.equal(message.rawFile, relative('-requests.ndjson'));
  assert.deepEqual(message.stopPayload, {action: 'stop', runId: message.runId});
  return {runId: message.runId, control: path.join(__dirname, base + '-stop.json'),
    database: path.join(__dirname, PREFIX + '隔离-python-' + message.runId + '.sqlite3'),
    observation: path.join(__dirname, base + '-service-observation.ndjson'),
    raw: path.join(__dirname, base + '-requests.ndjson'), report: path.join(__dirname, base + '.json')};
}
async function execute(options) {
  assert.equal(process.platform, 'win32');
  assert.deepEqual(Object.keys(options).sort(), ['execute-stop-probe', 'target', 'repair-proof-sha256', 'repair-authorization-sha256'].sort());
  assert.equal(options['execute-stop-probe'], true);
  assert.equal(options.target, 'python', 'This control barrier observes actual Python HTTP access logs only');
  assert.equal(sha(fs.readFileSync(DRIVER)), DRIVER_SHA, 'Only the reviewed unchanged driver is admitted');
  const binding = require(VERIFIER).verifyRepairProof(options['repair-proof-sha256'], options['repair-authorization-sha256']);
  assert.equal(sha(fs.readFileSync(PARENT)), PARENT_SHA);
  const id = crypto.randomUUID().replaceAll('-', ''), output = path.join(__dirname, PREFIX + '-受控停止组件-' + options.target + '-' + id + '.json');
  assert(!fs.existsSync(output));
  const report = {schemaVersion: 1, stage: 31, kind: 'driver-initialization-controlled-stop-component',
    pass: false, componentOnly: true, thirtyMinuteCompleted: false, formalAcceptance: false,
    productionEnabled: false, target: options.target, controllerRunId: id, startedAt: new Date().toISOString(),
    tool: {path: path.relative(ROOT, __filename), sha256: sha(fs.readFileSync(__filename))},
    driver: {path: path.relative(ROOT, DRIVER), sha256: DRIVER_SHA},
    repairProof: {path: binding.repairProof.path, sha256: binding.repairProof.sha256},
    repairAuthorization: {path: binding.authorization.path, sha256: options['repair-authorization-sha256']},
    limits: LIMITS, unchangedFullLoadLimits: {users: 100, rps: 20, seconds: 1800, requests: 36000},
    scope: 'Negative control of the unchanged real two-account interface probe during initialization; not a load pass',
    forcedCleanup: false, stdoutArbitraryTextPersisted: false, stderrArbitraryTextPersisted: false};
  let child, ended = false, spawnFailure, paths, stdoutPending = '', offset = 0, observationPending = '', firstRegister, stopWritten = false;
  let stdoutBytes = 0, stderrBytes = 0, stdoutLines = 0, tracked = [], acceptData = true, lastDatabaseRead = -Infinity;
  const stdoutDecoder = new StringDecoder('utf8'), observationDecoder = new StringDecoder('utf8');
  const stdoutHash = crypto.createHash('sha256'), stderrHash = crypto.createHash('sha256');
  const started = performance.now();
  try {
    const argv = [DRIVER, '--probe-local-interfaces', '--target=' + options.target,
      '--stage30-proof=' + PARENT, '--proof-sha256=' + PARENT_SHA,
      '--repair-proof-sha256=' + options['repair-proof-sha256'],
      '--repair-authorization-sha256=' + options['repair-authorization-sha256']];
    child = spawn(process.execPath, argv, {cwd: ROOT, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: minimalEnv()});
    report.driver.pid = child.pid;
    child.once('error', error => {spawnFailure = {code: error.code || 'SPAWN_ERROR'};});
    child.once('close', (code, signal) => {ended = true; report.driver.exitCode = code; report.driver.signal = signal;});
    child.stdout.on('data', bytes => {
      if (!acceptData) return;
      stdoutBytes += bytes.length; stdoutHash.update(bytes); stdoutPending += stdoutDecoder.write(bytes);
      if (Buffer.byteLength(stdoutPending) > LIMITS.lineBytes) {spawnFailure = {code: 'STDOUT_LINE_BOUND'}; return;}
      let at;
      while ((at = stdoutPending.indexOf('\n')) >= 0) {
        const line = stdoutPending.slice(0, at); stdoutPending = stdoutPending.slice(at + 1); stdoutLines++;
        try {
          const message = JSON.parse(line);
          if (message.phase === 'run-created') {
            assert(!paths); paths = exactRunPaths(message, options.target, child.pid);
            report.actualDriverRunId = paths.runId;
            report.actualPaths = Object.fromEntries(Object.entries(paths).filter(([key]) => key !== 'runId').map(([key, file]) => [key, path.relative(ROOT, file)]));
          }
        } catch (error) {if (error.name !== 'SyntaxError') spawnFailure = {code: 'RUN_ANNOUNCEMENT_INVALID'};}
      }
    });
    child.stderr.on('data', bytes => {if (!acceptData) return; stderrBytes += bytes.length; stderrHash.update(bytes);});
    while (!ended) {
      assert(!spawnFailure, 'Driver spawn/announcement failed');
      assert(performance.now() - started < LIMITS.controllerMs, 'Controlled-stop component deadline');
      if (paths && !firstRegister && fs.existsSync(paths.database) && performance.now() - lastDatabaseRead >= 250) {
        lastDatabaseRead = performance.now();
        const script = "import pathlib,sqlite3,sys,json\np=pathlib.Path(sys.argv[1]).resolve()\ntry:\n d=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=0.1)\n d.execute('PRAGMA query_only=ON')\n n=d.execute(\"SELECT count(*) FROM users WHERE role='user'\").fetchone()[0]\n d.close()\n print(json.dumps({'normalUsers':n}))\nexcept sqlite3.OperationalError:\n print(json.dumps({'normalUsers':0,'schemaNotReady':True}))";
        const observed = await exec(PYTHON, ['-B', '-X', 'utf8', '-c', script, paths.database],
          {cwd: ROOT, env: minimalEnv(), windowsHide: true, encoding: 'utf8', timeout: 3000, maxBuffer: 1024});
        const value = JSON.parse(observed.stdout);
        if (value.normalUsers >= 1) firstRegister = {kind: 'native-sqlite-committed-normal-user-count',
          normalUsers: value.normalUsers, queryOnly: true, actualDatabase: path.relative(ROOT, paths.database), at: new Date().toISOString()};
      }
      if (paths && fs.existsSync(paths.observation) && !stopWritten) {
        const stat = fs.statSync(paths.observation), size = Math.min(LIMITS.logReadBytes, stat.size - offset);
        if (size > 0) {
          const fd = fs.openSync(paths.observation, 'r');
          const bytes = Buffer.alloc(size);
          try {fs.readSync(fd, bytes, 0, size, offset);} finally {fs.closeSync(fd);}
          offset += size; observationPending += observationDecoder.write(bytes);
          assert(Buffer.byteLength(observationPending) <= LIMITS.lineBytes);
          let at;
          while ((at = observationPending.indexOf('\n')) >= 0) {
            const line = observationPending.slice(0, at); observationPending = observationPending.slice(at + 1);
            const value = JSON.parse(line);
            if (value.kind === 'service-log' && value.category === 'http-status' && value.method === 'POST' && value.route === '/api/auth/register' && value.status === 200) firstRegister ||= {at: value.at, monotonicMs: value.monotonicMs};
          }
        }
        if (firstRegister) {
          assert(!fs.existsSync(paths.control));
          const bytes = Buffer.from(JSON.stringify({action: 'stop', runId: paths.runId}) + '\n');
          fs.writeFileSync(paths.control, bytes, {flag: 'wx'}); stopWritten = true;
          report.stopRequest = {path: path.relative(ROOT, paths.control), sha256: sha(bytes),
            actualRunId: paths.runId, action: 'stop', at: new Date().toISOString(),
            firstActualRegistration: firstRegister, during: 'real-account-initialization'};
        }
      }
      await wait(LIMITS.pollMs);
    }
    assert(!spawnFailure); assert(paths && stopWritten && firstRegister, 'Must stop only after an observed real registration');
    assert.notEqual(report.driver.exitCode, 0); assert.equal(report.driver.signal, null);
    const result = JSON.parse(fs.readFileSync(paths.report, 'utf8'));
    assert.equal(result.runId, paths.runId); assert.equal(result.target, options.target);
    assert.equal(result.mode, 'interface-component-only'); assert.equal(result.control.consumed, true);
    assert.equal(result.control.path, path.relative(ROOT, paths.control));
    assert.equal(result.control.requestSha256, report.stopRequest.sha256);
    assert.equal(result.stopReason, 'owned_control_file'); assert.equal(result.interruption.reason, 'owned_control_file');
    assert.equal(result.interfaceComponentPassed, false); assert.equal(result.localBaselineCompleted, false);
    assert.equal(result.thirtyMinuteCompleted, false); assert(!result.measurementStartedAt);
    assert(result.requestedAuthenticatedUsers === 2 && result.users.length < 2);
    assert(!result.interfaceRequests || result.interfaceRequests.length === 0);
    assert.equal(result.rawEvidence.actualLineCount, 0); assert.equal(result.rawEvidence.integrityMatched, true);
    assert.equal(result.sourceIdentityUnchanged, true); assert.equal(result.serviceObservation.integrityMatched, true);
    assert(Object.values(result.serviceObservation.streams).every(row => row.ended));
    assert.equal(result.cleanup.ownedServerStillAlive, false); assert.equal(result.cleanup.pidInventoryComplete, true);
    assert.deepEqual(result.cleanup.trackedRemainingPids, []); assert.equal(result.cleanup.privateVarsRemaining, 0);
    assert.equal(sha(fs.readFileSync(DRIVER)), DRIVER_SHA);
    report.driverEvidence = {path: path.relative(ROOT, paths.report), sha256: sha(fs.readFileSync(paths.report)),
      authenticatedUsersAtStop: result.users.length, requestedAuthenticatedUsers: result.requestedAuthenticatedUsers,
      controlConsumed: true, stopReason: result.stopReason, measurementNeverStarted: true,
      originalProbeDidNotPass: true, finallyCleanup: result.cleanup,
      raw: {path: path.relative(ROOT, paths.raw), sha256: sha(fs.readFileSync(paths.raw))},
      serviceObservation: {path: path.relative(ROOT, paths.observation), sha256: sha(fs.readFileSync(paths.observation))}};
    report.pass = true;
  } catch (error) {
    report.error = {name: error.name, code: error.code || null, messageSha256: sha(String(error.message))};
  } finally {
    if (child?.pid && !ended && child.exitCode === null && child.signalCode === null && alive(child.pid)) {
      report.forcedCleanup = true; report.pass = false;
      try {tracked = await ownedTree(child.pid);} catch {report.processInventoryUnavailable = true;}
      const command = path.join(process.env.SystemRoot || 'C:/Windows', 'System32/taskkill.exe');
      try {if (!ended && child.exitCode === null && child.signalCode === null && alive(child.pid))
        await exec(command, ['/PID', String(child.pid), '/T', '/F'], {windowsHide: true, timeout: 15000, maxBuffer: 1048576});}
      catch {report.forcedCleanupCommandFailed = true;}
      const until = Date.now() + 5000;
      while (!ended && Date.now() < until) await wait(50);
    }
    acceptData = false;
    report.streams = {stdout: {bytes: stdoutBytes, lines: stdoutLines, sha256: stdoutHash.digest('hex')},
      stderr: {bytes: stderrBytes, sha256: stderrHash.digest('hex')}, childCloseObserved: ended};
    report.cleanup = {driverPidAlive: child?.pid ? alive(child.pid) : false,
      forcedRemainingPids: tracked.filter(row => alive(row.pid)).map(row => row.pid)};
    if (!ended || report.cleanup.driverPidAlive || report.cleanup.forcedRemainingPids.length || report.forcedCleanup) report.pass = false;
    report.finishedAt = new Date().toISOString();
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
    console.log(JSON.stringify({path: path.relative(ROOT, output), sha256: sha(fs.readFileSync(output)), pass: report.pass,
      componentOnly: true, thirtyMinuteCompleted: false, forcedCleanup: report.forcedCleanup}));
    if (!report.pass) process.exitCode = 1;
  }
}
if (require.main === module) {
  const options = argsOf(process.argv.slice(2));
  if (!Object.keys(options).length || options.describe === true) {
    assert(Object.keys(options).every(key => key === 'describe'));
    console.log(JSON.stringify({status: 'prepared-not-run', actualRuns: 0,
      scope: 'Python run-specific stop during unchanged two-account interface initialization; Cloud access-log barrier not implemented',
      servicesStarted: 0, changesToFullLoadLimits: false, explicitExecutionWindowRequired: true}));
  } else execute(options).catch(error => {console.error(JSON.stringify({status: 'gate-refused', name: error.name,
    code: error.code || null, rawMessagePersisted: false})); process.exitCode = 1;});
}
module.exports = {LIMITS, argsOf, exactRunPaths};
