"""Prepared, not run: owned-lab SQLite snapshots and read-only migration checks.

Import has no side effects. The default CLI only describes this preparation.
Every mutating primitive requires an explicitly armed, SHA-bound lab manifest.
There is deliberately no arbitrary database-path or shell-command parameter.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
CLOUD = ROOT / '04_研发源码/app/cloud'
PREFIX = '负责人优化建议-当前产品可靠性恢复'
PYTHON = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
NODE = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
APP = ROOT / '03_当前APP/东方智慧-首页体验R4.html'
BACKEND = ROOT / '04_研发源码/app/r4/backend/server.py'
FORBIDDEN_PORTS = {8877, 8878, 8879, 8880, 8881}
RELIABILITY_BASELINE_SHA = '6fe9d95b438cc5a638ae534f01cbf7f6298f6bd1ab3201b1f4324d507eb06919'
SERVER_RELATIVE = '04_研发源码/app/r4/backend/server.py'
MUTABLE_NAMES = {
    '06_验证与后续工作/东方智慧APP需求进度表-20261116.xlsx',
    '06_验证与后续工作/东方智慧APP优化任务表_依据v1.0_20261112.xlsx',
    '06_验证与后续工作/公司同步-进度与记忆.json', '公司同步-先读我.txt',
    '06_验证与后续工作/负责人优化建议-交付收尾推进.json',
    '06_验证与后续工作/负责人优化建议-任务拆解.json',
    '06_验证与后续工作/负责人优化建议-98项最终覆盖审计.txt', 'AGENTS.md',
    '06_验证与后续工作/负责人优化建议-98项最终覆盖审计.json'
}


class Refusal(Exception):
    pass


def require(value, code):
    if not value:
        raise Refusal(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':')).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate_json_key')
            result[k] = v
        return result
    return json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refusal('nonfinite_json')))


def checked_path(path, parent, prefix, exists=None):
    p = Path(path)
    require(p.is_absolute(), 'absolute_owned_path_required')
    # Reject reparse points in the supplied path before resolving, including symlinks.
    require(not any(q.exists() and (q.is_symlink() or bool(getattr(q.stat(), 'st_file_attributes', 0) & 0x400))
                    for q in (p, *p.parents) if q != q.parent), 'reparse_path_forbidden')
    p = p.resolve()
    require(p.parent == parent.resolve() and p.name.startswith(prefix), 'owned_namespace_required')
    require(not any(x.lower() in ('rq01', 'node_modules', '.git') for x in p.parts), 'protected_path')
    if exists is not None:
        require(p.exists() is exists, 'owned_path_existence_mismatch')
    return p


def safe_base(base):
    m = re.fullmatch(r'http://127\.0\.0\.1:([1-9][0-9]{0,4})', base)
    require(m and 1024 <= int(m[1]) <= 65535 and int(m[1]) not in FORBIDDEN_PORTS,
            'explicit_safe_loopback_port_required')
    return base


def verify_repair(proof_sha, authorization_sha):
    require(isinstance(proof_sha, str) and re.fullmatch('[a-f0-9]{64}', proof_sha), 'explicit_current_binding_sha_required')
    require(isinstance(authorization_sha, str) and re.fullmatch('[a-f0-9]{64}', authorization_sha), 'explicit_authorization_sha_required')
    helper = OUT / '负责人优化建议-当前产品可靠性-基线.cjs'
    environment = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC') if key in os.environ}
    environment['PATH'] = str(NODE.parent)
    try:
        result = subprocess.run([str(NODE), str(helper), '--verify-repair-proof',
            '--repair-proof-sha256=' + proof_sha, '--repair-authorization-sha256=' + authorization_sha],
            cwd=ROOT, env=environment, shell=False, capture_output=True, timeout=90,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal('actual_current_binding_verification_failed')
    require(result.returncode == 0 and len(result.stdout) <= 262144, 'actual_current_binding_verification_failed')
    verified = strict_json(result.stdout.strip())
    require(verified.get('pass') is True and verified.get('stage') == 31
            and verified.get('startsService') is False, 'current_binding_not_accepted')
    current = verified.get('currentSourceAndBuildHashes')
    require(isinstance(current, dict) and len(current) > 0, 'complete_current_product_map_required')
    for name, digest in current.items():
        p = (ROOT / name).resolve()
        require(not Path(name).is_absolute() and p.is_relative_to(ROOT) and p.is_file()
                and re.fullmatch('[a-f0-9]{64}', digest) and sha(p.read_bytes()) == digest,
                'current_product_source_changed')
    return verified, verified['binding']


def stage30_proof(path, expected, repair_proof_sha, repair_authorization_sha):
    verified, _binding = verify_repair(repair_proof_sha, repair_authorization_sha)
    require(expected == '752e36ad70d6812727849f0fa49262c426ef161a911b59f66831cd0617e12f07', 'exact_stage30_parent_sha_required')
    proof = checked_path(path, OUT, '负责人优化建议-卡组迁移-最终交付核验.json', True)
    require(proof.name == '负责人优化建议-卡组迁移-最终交付核验.json', 'exact_stage30_final_proof_required')
    require(sha(proof.read_bytes()) == expected, 'stage30_proof_hash_changed')
    final = strict_json(proof.read_bytes())
    require(final.get('stage') == 30 and final.get('pass') is True
            and final.get('allFourteenGatesPassedWithFreshSuccessfulChildren') is True
            and final.get('perBackendPassed') == {'Python': 195, 'Cloud': 195}, 'stage30_historical_gates_not_final')
    anchor = verified['stage30ProofAnchor']
    require((ROOT / anchor['path']).resolve() == proof and anchor['sha256'] == expected,
            'shared_verifier_historical_parent_binding')
    # The shared verifier checks every prior source SHA through its exact preserved
    # byte alias and all current module acceptance evidence. No old map is relabeled.
    return proof


def write_new(path, value):
    with open(path, 'xb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path.read_bytes())}


def load_lab(path, *, armed=False):
    p = checked_path(path, OUT, PREFIX + '-manifest-', True)
    lab = strict_json(p.read_bytes())
    require(set(lab) == {'schemaVersion', 'core', 'manifestSha256'}, 'lab_manifest_shape')
    core = lab['core']
    require(lab['schemaVersion'] == 1 and lab['manifestSha256'] == sha(canonical(core)), 'lab_manifest_hash')
    require(core['status'] == 'armed-local-only' and core['productionEnabled'] is False,
            'lab_not_armed')
    require(re.fullmatch('[a-f0-9]{32}', core['runId']) is not None, 'lab_run_id')
    require(core['backend'] in ('python', 'cloud'), 'lab_backend')
    if core['backend'] == 'cloud':
        require(core.get('cloudStateBasename') == 'rl-' + core['runId'], 'explicit_short_owned_cloud_state_required')
    safe_base(core['base'])
    require(sha(Path(core['nodeExecutable']).read_bytes()) == core['nodeExecutableSha256'], 'node_executable_changed')
    require(Path(core['nodeExecutable']).resolve() == NODE.resolve(), 'fixed_node_required')
    require(sha(PYTHON.read_bytes()) == core['pythonExecutableSha256'], 'python_executable_changed')
    for rel, digest in core['runtimeToolHashes'].items():
        require(sha((ROOT / rel).read_bytes()) == digest, 'runtime_tool_changed')
    repair = core['performanceRepair']
    stage30_proof(ROOT / core['stage30Proof']['path'], core['stage30Proof']['sha256'],
                  repair['repairProofSha256'], repair['authorizationSha256'])
    for rel, digest in core['sourceAndToolHashes'].items():
        source = (ROOT / rel).resolve()
        require(source.is_relative_to(ROOT) and source.is_file() and sha(source.read_bytes()) == digest,
                'source_or_tool_changed')
    for rel, digest in core['sourceCopiesSHA256'].items():
        source = checked_path(ROOT / rel, OUT, PREFIX + '-' + core['runId'] + '-source-', True)
        require(sha(source.read_bytes()) == digest, 'owned_source_copy_changed')
    require(core['explicitExecutionAuthorization'] is True if armed else True, 'execution_not_authorized')
    return lab


def role_path(lab, role, *, exists=None):
    require(role in ('live', 'snapshot', 'restored', 'rollback'), 'unknown_database_role')
    run = lab['core']['runId']
    return checked_path(OUT / (PREFIX + '-' + run + '-' + role + '.sqlite3'),
                        OUT, PREFIX + '-' + run + '-', exists)


def report(lab, operation, observed):
    result = {'schemaVersion': 1, 'runId': lab['core']['runId'], 'operation': operation,
              'observedAtMs': time.time_ns() // 1_000_000, 'formalAcceptance': False,
              'productionEnabled': False, 'syntheticOnly': True,
              'labManifestSha256': lab['manifestSha256'], **observed}
    target = OUT / (PREFIX + '-' + lab['core']['runId'] + '-' + operation + '-' + uuid.uuid4().hex + '.json')
    return write_new(target, result)


def readonly(path):
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)
    db.execute('PRAGMA query_only=ON')
    return db


def normalize(v):
    if isinstance(v, bytes):
        return {'sqliteBlobSha256': sha(v), 'bytes': len(v)}
    return v


def database_facts(db):
    """Call inside one read transaction; emit digests, never row bodies/credentials."""
    catalog = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    tables = {}
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        quoted = '"' + name.replace('"', '""') + '"'
        columns = [r[1] for r in db.execute('PRAGMA table_info(' + quoted + ')')]
        values = [canonical([normalize(v) for v in row]) for row in db.execute('SELECT * FROM ' + quoted)]
        values.sort()
        rolling = hashlib.sha256()
        for value in values:
            rolling.update(str(len(value)).encode('ascii') + b':' + value)
        tables[name] = {'count': len(values), 'columns': columns, 'sha256': rolling.hexdigest()}
    return {'catalogSha256': sha(canonical(catalog)), 'tables': tables,
            'allTablesSha256': sha(canonical(tables))}


def business_links(db):
    config = strict_json((OUT / (PREFIX + '-关联查询.json')).read_bytes())
    values = {}
    for item in config['queries']:
        result = db.execute(item['sql']).fetchone()[0]
        require(type(result) is int and result >= 0, 'native_association_count_type')
        if 'minimum' in item:
            require(result >= item['minimum'], 'native_nonempty_' + item['name'])
        if 'exact' in item:
            require(result == item['exact'], 'native_association_' + item['name'])
        values[item['name']] = result
    return {'actualNativeSql': True, 'counts': values, 'allRequiredRelationsValid': True,
            'sourceQuerySha256': sha((OUT / (PREFIX + '-关联查询.json')).read_bytes())}


def preflight(lab, role='live'):
    require(lab['core']['backend'] == 'python', 'sqlite_backend_only')
    path = role_path(lab, role, exists=True)
    with readonly(path) as db:
        db.execute('BEGIN')
        integrity = [r[0] for r in db.execute('PRAGMA integrity_check')]
        fk = db.execute('PRAGMA foreign_key_check').fetchall()
        facts = database_facts(db)
        marker = db.execute('SELECT runtime_id,mode,manifest_hash FROM ops_runtime_identity WHERE id=1').fetchone()
        result = {'readOnly': True, 'pathRole': role, 'integrityCheckOk': integrity == ['ok'],
                  'foreignKeyViolations': len(fk), 'userVersion': db.execute('PRAGMA user_version').fetchone()[0],
                  'sqliteVersion': sqlite3.sqlite_version, 'facts': facts,
                  'businessLinks': business_links(db),
                  'marker': list(marker) if marker else None,
                  'walPhysicalErasureClaimed': False, 'migrationExecuted': False}
    require(result['integrityCheckOk'] and result['foreignKeyViolations'] == 0,
            'readonly_preflight_failed')
    return result


def exclusive_db(path):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    return sqlite3.connect(path)


def snapshot(lab):
    require(lab['core']['backend'] == 'python', 'sqlite_backend_only')
    source = role_path(lab, 'live', exists=True)
    target = role_path(lab, 'snapshot', exists=False)
    started = time.monotonic_ns()
    with readonly(source) as src:
        src.execute('BEGIN')
        before = database_facts(src)
        with exclusive_db(target) as dst:
            # SQLite online-backup API copies one actual read snapshot, including WAL commits.
            src.backup(dst)
    with readonly(target) as copied:
        copied.execute('BEGIN')
        after = database_facts(copied)
        require(before == after, 'snapshot_logical_mismatch')
        require(copied.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'snapshot_integrity')
        require(not copied.execute('PRAGMA foreign_key_check').fetchall(), 'snapshot_foreign_key')
    result = {'sourceRole': 'live', 'targetRole': 'snapshot', 'snapshotSha256': sha(target.read_bytes()),
              'durationMs': (time.monotonic_ns() - started) / 1_000_000, 'snapshotFacts': after,
              'onlineBackupApi': True, 'acknowledgedWritesAfterSnapshotRecovered': None,
              'productionRPO': None, 'productionRTO': None, 'r2Included': False}
    return report(lab, 'snapshot', result)


def restore(lab, receipt_path, *, rollback=False):
    require(lab['core']['backend'] == 'python', 'sqlite_backend_only')
    rp = checked_path(receipt_path, OUT, PREFIX + '-' + lab['core']['runId'] + '-snapshot-', True)
    receipt = strict_json(rp.read_bytes())
    require(receipt['labManifestSha256'] == lab['manifestSha256'] and receipt['operation'] == 'snapshot',
            'snapshot_receipt_binding')
    source = role_path(lab, 'snapshot', exists=True)
    require(sha(source.read_bytes()) == receipt['snapshotSha256'], 'backup_bytes_changed')
    target_role = 'rollback' if rollback else 'restored'
    target = role_path(lab, target_role, exists=False)
    started = time.monotonic_ns()
    with readonly(source) as src, exclusive_db(target) as dst:
        src.backup(dst)
    actual = preflight(lab, target_role)
    require(actual['facts'] == receipt['snapshotFacts'], 'restored_facts_mismatch')
    require(sha(source.read_bytes()) == receipt['snapshotSha256'], 'original_backup_changed')
    return report(lab, target_role, {'snapshotReceipt': {'path': str(rp.relative_to(ROOT)), 'sha256': sha(rp.read_bytes())},
                  'freshTargetRole': target_role, 'durationMs': (time.monotonic_ns() - started) / 1_000_000,
                  'preflight': actual, 'sourceLiveDatabaseOverwritten': False,
                  'processOrTrafficSwitched': False, 'recoveredApiVerified': False,
                  'immutableRuntimeMarkerPreserved': True,
                  'physicalStatePathFromLabManifestNotOriginalMarker': True})


class OwnedPython:
    """Future drill controller: own Popen handle, exact DB roles, no arbitrary PID kill.

    Keep this controller alive through crash/restart; an unrelated process cannot
    submit a PID. Child stdout/stderr are drained, never persisted with raw bodies.
    """
    def __init__(self, lab):
        require(lab['core']['backend'] == 'python', 'python_backend_only')
        self.lab, self.child, self.started_ns = lab, None, None
        self.stderr_bytes = self.stdout_bytes = 0

    def start(self, role, environment):
        import threading
        require(self.child is None or self.child.poll() is not None, 'owned_child_already_running')
        path = role_path(self.lab, role, exists=True)
        port = int(safe_base(self.lab['core']['base']).rsplit(':', 1)[1])
        allowed = {'EW_LOCAL_TASK_RUNTIME_ENABLED', 'EW_LOCAL_TASK_RUNTIME_ID', 'EW_LOCAL_TASK_MANIFEST_SHA256'}
        require(set(environment) <= allowed, 'unexpected_runtime_environment')
        env = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC') if k in os.environ}
        env.update(environment)
        env['PATH'] = str(PYTHON.parent) + os.pathsep + str(Path(self.lab['core']['nodeExecutable']).parent)
        self.started_ns = time.monotonic_ns()
        self.child = subprocess.Popen([str(PYTHON), '-B', str(BACKEND), '--port', str(port), '--db', str(path),
                                       '--web-root', str(APP.parent)], cwd=ROOT, env=env, shell=False,
                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                      stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def drain(stream, attr):
            for data in iter(lambda: stream.read(4096), b''):
                setattr(self, attr, getattr(self, attr) + len(data))
        for stream, attr in ((self.child.stdout, 'stdout_bytes'), (self.child.stderr, 'stderr_bytes')):
            threading.Thread(target=drain, args=(stream, attr), daemon=True).start()
        return {'pid': self.child.pid, 'role': role, 'base': self.lab['core']['base'],
                'popenHandleOwned': True, 'appSha256': sha(APP.read_bytes())}

    def crash(self):
        require(self.child is not None and self.child.poll() is None, 'no_live_owned_child')
        pid, stamp = self.child.pid, time.monotonic_ns()
        self.child.kill()  # Only the child represented by this live OS handle.
        code = self.child.wait(timeout=20)
        return {'pid': pid, 'exitCode': code, 'method': 'owned-popen-kill',
                'durationMs': (time.monotonic_ns() - stamp) / 1_000_000,
                'acknowledgedBytesCannotBeRecalled': True, 'gracefulShutdownClaimed': False}


def arm(proof_path, proof_sha, backend, base, node, repair_proof_sha, repair_authorization_sha):
    safe_base(base)
    proof = stage30_proof(proof_path, proof_sha, repair_proof_sha, repair_authorization_sha)
    require(backend in ('python', 'cloud'), 'backend_required')
    node = Path(node).resolve()
    require(node == NODE.resolve() and node.is_file(), 'fixed_actual_node_required')
    run = uuid.uuid4().hex
    sources = [Path(__file__), BACKEND, APP, ROOT / '04_研发源码/app/cloud/generated/experience.html',
               OUT / '负责人优化建议-当前产品可靠性恢复D1快照.cjs', OUT / '负责人优化建议-本地可靠性沙箱场景.cjs',
               OUT / (PREFIX + '协调.cjs'), OUT / (PREFIX + '-关联查询.json'),
               OUT / '负责人优化建议-当前产品可靠性-基线.cjs',
               OUT / '负责人优化建议-当前产品可靠性恢复SQL计划.py',
               ROOT / '04_研发源码/app/r4/backend/local_task_bootstrap.py',
               OUT / (PREFIX + '-候选合同.json')]
    verified_current, _binding = verify_repair(repair_proof_sha, repair_authorization_sha)
    sources += [ROOT / verified_current['binding']['path']]
    core = {'runId': run, 'backend': backend, 'base': base, 'createdMs': time.time_ns() // 1_000_000,
            'status': 'armed-local-only', 'explicitExecutionAuthorization': True, 'productionEnabled': False,
            'nodeExecutable': str(node), 'nodeExecutableSha256': sha(node.read_bytes()),
            'pythonExecutableSha256': sha(PYTHON.read_bytes()),
            'd1DatabaseId': str(uuid.uuid4()),
            'cloudStateBasename': 'rl-' + run if backend == 'cloud' else None,
            'performanceRepair': {'repairProofSha256': repair_proof_sha,
                'authorizationSha256': repair_authorization_sha,
                'sharedReadOnlyVerifierRequired': True, 'candidateAloneAllowsExecution': False},
            'stage30Proof': {'path': str(proof.relative_to(ROOT)), 'sha256': proof_sha},
            'sourceAndToolHashes': {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p.read_bytes()) for p in sources}}
    core['sourceAndToolHashes'] = {**verified_current['currentSourceAndBuildHashes'], **core['sourceAndToolHashes']}
    core['currentProductBinding'] = verified_current['binding']
    tools = [CLOUD / 'node_modules/wrangler/bin/wrangler.js', CLOUD / 'node_modules/wrangler/package.json',
             CLOUD / 'node_modules/esbuild/lib/main.js', CLOUD / 'node_modules/esbuild/package.json',
             CLOUD / 'node_modules/@esbuild/win32-x64/package.json',
             CLOUD / 'node_modules/@esbuild/win32-x64/esbuild.exe',
             CLOUD / 'node_modules/miniflare/package.json']
    package = strict_json((CLOUD / 'node_modules/miniflare/package.json').read_bytes())
    tools.append(CLOUD / 'node_modules/miniflare' / package['main'])
    core['runtimeToolHashes'] = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p.read_bytes()) for p in tools}
    baseline = strict_json((OUT / '负责人优化建议-本地可靠性-实施前核对.json').read_bytes())
    historical = {**baseline['authorizedWorkbookBaselineSHA256'], **baseline['mutableHandoffAtStartSHA256']}
    core['authorizedMutableHistory'] = {'baselineSha256': RELIABILITY_BASELINE_SHA,
        'historicalSHA256': historical,
        'currentSHA256AtArm': {name: sha((ROOT / name).read_bytes()) for name in sorted(MUTABLE_NAMES)},
        'historicalAnchorsAreNotCurrentProductIdentity': True}
    copies = {}
    for source in sources:
        if source.parent != OUT:
            continue
        data = source.read_bytes()
        target = OUT / (PREFIX + '-' + run + '-source-' + source.name + '.txt')
        with target.open('xb') as handle:
            handle.write(data)
        copies[str(target.relative_to(ROOT)).replace('\\', '/')] = sha(data)
    core['sourceCopiesSHA256'] = copies
    document = {'schemaVersion': 1, 'core': core, 'manifestSha256': sha(canonical(core))}
    return write_new(OUT / (PREFIX + '-manifest-' + run + '.json'), document)


def main():
    parser = argparse.ArgumentParser(description='Prepared-only by default. No default database.')
    parser.add_argument('--operation', choices=('describe', 'arm', 'preflight', 'snapshot', 'restore', 'rollback-target'), default='describe')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--manifest')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--snapshot-receipt')
    parser.add_argument('--backend', choices=('python', 'cloud'))
    parser.add_argument('--base')
    parser.add_argument('--node')
    parser.add_argument('--stage30-proof')
    parser.add_argument('--proof-sha256')
    parser.add_argument('--repair-proof-sha256')
    parser.add_argument('--repair-authorization-sha256')
    args = parser.parse_args()
    if args.operation == 'describe':
        print(json.dumps({'status': 'prepared-not-run', 'actualDrills': 0, 'productionEnabled': False,
                          'requiresExplicitRootExecutionOrderAndStage30FinalProof': True}))
        return
    require(args.execute, 'explicit_execution_flag_required')
    if args.operation == 'arm':
        result = arm(args.stage30_proof, args.proof_sha256, args.backend, args.base, args.node,
                     args.repair_proof_sha256, args.repair_authorization_sha256)
    else:
        lab = load_lab(args.manifest, armed=True)
        require(sha(Path(args.manifest).read_bytes()) == args.manifest_sha256, 'manifest_file_hash_required')
        try:
            if args.operation == 'preflight':
                result = report(lab, 'preflight', preflight(lab))
            elif args.operation == 'snapshot':
                result = snapshot(lab)
            else:
                result = restore(lab, args.snapshot_receipt, rollback=args.operation == 'rollback-target')
        except Exception as error:
            report(lab, args.operation + '-failed', {'ok': False,
                   'errorCode': str(error) if isinstance(error, Refusal) else type(error).__name__,
                   'partialOwnedTargetsPreserved': True, 'automaticRetry': False})
            raise
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not print exception arguments: a malformed path/JSON could contain private input.
        code = str(error) if isinstance(error, Refusal) else type(error).__name__
        print(json.dumps({'ok': False, 'errorCode': code, 'productionEnabled': False}))
        raise SystemExit(1)
