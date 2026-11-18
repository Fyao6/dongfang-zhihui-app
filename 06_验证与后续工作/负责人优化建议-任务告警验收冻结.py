"""Stage27 evidence gate. Import/--inspect writes nothing; default freeze requires all final gates.

No service, business test, progress updater or spreadsheet author is invoked here.
Old receipts/reports and the preview database are checked, never rewritten.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-任务告警'
BASELINE = OUT / (PREFIX + '-实施前核对.json')
BASELINE_SHA256 = 'a105f2ec63cdba3ad212c23e8a63746160cab0936868e09092766184754c9443'
INITIAL_SNAPSHOT_SHA256 = '285c38cc4242ead5c3336258a1fea0aa0ba3b4a54ecf69127c7b4766a8d853fc'
FIRST_FAILURE_SHA256 = '1369ff62079a5b1e5f565f77547c099e522d87daa3e242f7e7789cd3271ddc1b'
SECOND_SNAPSHOT_SHA256 = 'c2d71f4aad9516bb824578516f9c963d48c848c1fe66c3330f4cba567627ce84'
SECOND_FAILURE_SHA256 = '9433b062d515ca01427541cde2f937f64e6992d3e17175d210a7bd57a3ecc527'
THIRD_SNAPSHOT_SHA256 = '4cf09b7660e1b70821ab78d1470adc3c6c982430f16a172e92266450e29079fc'
THIRD_FAILURE_SHA256 = 'b25995daf6592543ba3f677337621f39d4b2ad0fb10335393cc040117ef64165'
FOURTH_SNAPSHOT_SHA256 = '17e7583e83e93ebfbbaf6f3935cc4a2ea0af2b0973195fd880fceeb1324e9e00'
FOURTH_FAILURE_SHA256 = '983f0ea581ea577c6a31b7645639716c168726f83e7448ac40161ca4c03c8240'
IDS = ['PAY18', 'SV04']
SUITES = [('full', '全量', 60), ('special', '专项', 40), ('visual', '补充视觉', 4),
          ('callback-compat', '回调兼容', 16), ('recovery-compat', '恢复兼容', 19),
          ('privacy-compat', '逐域兼容', 28), ('digital-compat', '数字兼容', 24),
          ('quota-compat', '额度兼容专项', 21), ('closure-compat', '注销兼容', 27)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def local_path(name):
    assert isinstance(name, str) and name and '\\' not in name and '\x00' not in name, name
    relative = Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts, name
    path = (ROOT / relative).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(), name
    return path


def hashes_match(mapping, label):
    assert isinstance(mapping, dict) and mapping, (label, 'empty identity')
    for name, expected in mapping.items():
        assert isinstance(expected, str) and re.fullmatch('[a-f0-9]{64}', expected), (label, name)
        assert sha(local_path(name)) == expected, (label, 'current bytes differ', name)


def inventory_module():
    path = OUT / (PREFIX + '依赖盘点.py')
    spec = importlib.util.spec_from_file_location('stage27_independent_inventory', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def required_identity_paths():
    return inventory_module().required_identity_paths()


def report_name(target, suite, title):
    if suite == 'full':
        return PREFIX + '-' + ('本轮' if target == 'python' else '公网适配') + '全量回归结果.json'
    return PREFIX + title + '-' + target + '.json'


def parsed_stamp(value):
    assert isinstance(value, str) and value
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert stamp.tzinfo is not None
    return stamp


def validate_nested_quota(run, common, snapshot_at, label):
    nested = run['membershipQuotaLauncher']
    assert nested['suite'] == 'special' and nested['identityUnchanged'] is True, (label, 'nested quota identity')
    assert nested['childExitCode'] == 0 and nested['reportFreshForInvocation'] is True, (label, 'nested failed child / stale report')
    assert isinstance(nested['runId'], str) and nested['runId']
    started = parsed_stamp(nested['invocationStarted'])
    assert started >= snapshot_at and parsed_stamp(run['at']) >= started, (label, 'nested gate predates final snapshot / child start')
    assert nested['syntheticDataOnly'] is True and nested['realSupplier'] is False and nested['realHttpSseFixture'] is True
    identity = nested['sourceAndBuildHashes']
    assert isinstance(identity, dict) and identity and set(identity) <= set(common), (label, 'unbound nested inputs')
    for name, expected in identity.items():
        assert common[name] == expected == sha(local_path(name)), (label, 'nested input differs from complete current map', name)
    return {'runId': nested['runId'], 'childExitCode': 0, 'reportFreshForInvocation': True,
            'invocationStarted': nested['invocationStarted'], 'recordedInputCount': len(identity)}


def diagnostic_hashes():
    """Only pre-existing attempt/diagnostic JSON, never receipt/progress/final-proof outputs."""
    result = {}
    for path in OUT.glob(PREFIX + '*.json'):
        if any(word in path.name for word in ('启动诊断', '诊断保全', '首轮', 'failure', 'failed', '冒烟', '静态核验', '场景核对', '组件', '探测', '停止核验', '完整依赖诊断', '依赖盘点')):
            document = read(path)
            result[path.relative_to(ROOT).as_posix()] = sha(path)
            copies = document.get('preservedReportCopiesSHA256', {})
            if copies:
                hashes_match(copies, 'preserved failed-report copies')
                result.update(copies)
    for path in OUT.glob(PREFIX + '*复验Cloud构建.log'):
        result[path.relative_to(ROOT).as_posix()] = sha(path)
    # These reviewed component/smoke sources are delivery diagnostics, not extra
    # formal gates or additions to the common execution map.
    for suffix in ('-Python局部冒烟.py', '-预算修复局部冒烟.py', '-预算守卫组件.py',
                   '预算同批组件.cjs', '横滑几何组件-非formal.cjs'):
        path = OUT / (PREFIX + suffix)
        assert path.is_file(), ('Missing owned diagnostic source', path.name)
        result[path.relative_to(ROOT).as_posix()] = sha(path)
    return result


def normalize_compiler_path(name):
    name = name.removeprefix('task-alert-owned-raw:')
    path = Path(name)
    path = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(), ('Invalid compiler input path', name)
    return path.relative_to(ROOT).as_posix()


def validate_runtime_artifacts(run, common, target, label):
    """Verify the actual executed Cloud bundle and its compiler input graph, not only TS sources."""
    artifacts = []
    for container in (run, run.get('taskAlertLauncher', {}), run.get('membershipQuotaLauncher', {})):
        artifacts.extend(container.get('runtimeArtifacts', []))
    unique = {}
    for item in artifacts:
        previous = unique.setdefault(item['bundle'], item)
        assert previous == item, (label, 'Contradictory runtime artifact records')
    artifacts = list(unique.values())
    if target == 'python':
        assert not artifacts, (label, 'Unexpected compiled Cloud execution claim')
        return [], {}, None
    assert artifacts, (label, 'Actual Cloud bundle evidence missing')
    verified, compiler_common = {}, None
    expected_tools = {
        '04_研发源码/app/cloud/node_modules/esbuild/lib/main.js',
        '04_研发源码/app/cloud/node_modules/esbuild/package.json',
        '04_研发源码/app/cloud/node_modules/@esbuild/win32-x64/package.json',
        '04_研发源码/app/cloud/node_modules/@esbuild/win32-x64/esbuild.exe',
    }
    for item in artifacts:
        assert item['bundle'].startswith('04_研发源码/app/cloud/.wrangler/')
        assert item['metafile'] == item['bundle'] + '.metafile.json'
        assert item['toolchainIncludedInHandoff'] is False and item['rawReadsActualSourceBytes'] is True
        assert item['originalBusinessOptionsPreserved'] is True
        assert item['entry'] in common, (label, 'Unbound compiler entry')
        for field, digest in (('bundle', 'bundleSha256'), ('metafile', 'metafileSha256')):
            assert sha(local_path(item[field])) == item[digest], (label, 'Runtime artifact changed', item[field])
            verified[item[field]] = item[digest]
        metadata = read(local_path(item['metafile']))
        actual_inputs = {normalize_compiler_path(name) for name in metadata['inputs']}
        assert actual_inputs == set(item['inputHashes']), (label, 'Metafile graph/input map differs')
        assert actual_inputs <= set(common), (label, 'Actual runtime source omitted from common map', sorted(actual_inputs - set(common)))
        for name, expected in item['inputHashes'].items():
            assert common[name] == expected == sha(local_path(name)), (label, 'Compiled input changed', name)
        outputs = {normalize_compiler_path(name): value for name, value in metadata['outputs'].items()}
        assert item['bundle'] in outputs, (label, 'Bundle absent from compiler outputs')
        output = outputs[item['bundle']]
        assert normalize_compiler_path(output['entryPoint']) == item['entry']
        assert output['bytes'] == local_path(item['bundle']).stat().st_size
        assert all(row.get('external') is True and row['path'].startswith('node:') for row in output.get('imports', [])), (label, 'Unbound runtime import')
        tools = item['runtimeDependencyHashes']
        assert set(tools) == expected_tools, (label, 'Unexpected or missing actual compiler dependency')
        hashes_match(tools, label + ' actual compiler dependencies')
        package = read(local_path('04_研发源码/app/cloud/node_modules/esbuild/package.json'))
        assert package['version'] == item['compilerVersion']
        if compiler_common is None:
            compiler_common = tools
        assert tools == compiler_common, (label, 'Compiler changed between runtime artifacts')
        verified.update(tools)
    return artifacts, verified, compiler_common


def collect():
    assert sha(BASELINE) == BASELINE_SHA256, 'Preflight bytes changed'
    baseline = read(BASELINE)
    assert baseline['currentStage'] == 26 and baseline['stageToImplement'] == 27
    assert len(baseline['files']) == 909
    preserved = baseline['protectedHistoricalSHA256']
    assert len(preserved) == 612, 'Use the explicit protected inventory, not a directory-derived substitute'
    hashes_match(preserved, '612 protected historical inputs')
    assert sha(OUT / '负责人优化建议-隔离预览.sqlite3') == baseline['previewDBSHA256']
    required = required_identity_paths()
    initial_snapshot_path = OUT / (PREFIX + '-完整依赖诊断.json')
    first_failure_path = OUT / (PREFIX + '-首轮诊断保全.json')
    assert sha(initial_snapshot_path) == INITIAL_SNAPSHOT_SHA256, 'Original pre-run snapshot changed'
    assert sha(first_failure_path) == FIRST_FAILURE_SHA256, 'Preserved first-round failure record changed'
    hashes_match(read(first_failure_path)['preservedReportCopiesSHA256'], 'preserved first-round diagnostic files')
    second_snapshot_path = OUT / (PREFIX + '-复验完整依赖诊断.json')
    second_failure_path = OUT / (PREFIX + '-第二轮视觉诊断保全.json')
    assert sha(second_snapshot_path) == SECOND_SNAPSHOT_SHA256, 'Second-round pre-run snapshot changed'
    assert sha(second_failure_path) == SECOND_FAILURE_SHA256, 'Second-round visual diagnostic record changed'
    second_copies = read(second_failure_path)['preservedReportCopiesSHA256']
    assert len(second_copies) == 16, 'Second-round preservation inventory changed'
    hashes_match(second_copies, 'preserved second-round main/visual/QA/screens evidence')
    third_snapshot_path = OUT / (PREFIX + '-视觉复验完整依赖诊断.json')
    assert sha(third_snapshot_path) == THIRD_SNAPSHOT_SHA256, 'Third-round visual-retry snapshot changed'
    third_failure_path = OUT / (PREFIX + '-第三轮兼容诊断保全.json')
    assert sha(third_failure_path) == THIRD_FAILURE_SHA256, 'Third-round compatibility diagnostic record changed'
    third_copies = read(third_failure_path)['preservedReportCopiesSHA256']
    assert len(third_copies) == 34, 'Third-round preservation inventory changed'
    hashes_match(third_copies, 'preserved third-round nine-gate/source/screenshot evidence')
    fourth_snapshot_path = OUT / (PREFIX + '-兼容复验完整依赖诊断.json')
    fourth_failure_path = OUT / (PREFIX + '-第四轮启动器诊断保全.json')
    assert sha(fourth_snapshot_path) == FOURTH_SNAPSHOT_SHA256, 'Fourth-round compatibility-retry snapshot changed'
    assert sha(fourth_failure_path) == FOURTH_FAILURE_SHA256, 'Fourth-round nested-launcher diagnostic record changed'
    fourth_copies = read(fourth_failure_path)['preservedReportCopiesSHA256']
    assert len(fourth_copies) == 34, 'Fourth-round preservation inventory changed'
    hashes_match(fourth_copies, 'preserved fourth-round compatibility/nested-launcher evidence')
    snapshot_path = OUT / (PREFIX + '-启动器复验完整依赖诊断.json')
    snapshot = read(snapshot_path)
    assert snapshot['pass'] is True and snapshot['inputCount'] == len(required)
    assert snapshot['independentRequiredCount'] == snapshot['harnessCount'] == len(required)
    assert not snapshot['missingFromHarness'] and not snapshot['harnessAdditional']
    common = snapshot['sourceAndBuildHashes']
    assert set(common) == required
    hashes_match(common, 'independent pre-run snapshot')
    canonical = json.dumps(common, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    assert hashlib.sha256(canonical).hexdigest() == snapshot['canonicalSHA256']
    hashes_match(snapshot['buildPreparationInputHashes'], 'separately declared generator inputs')
    compiler_snapshot = snapshot['runtimeCompilerDependencyHashes']
    assert set(compiler_snapshot) == inventory_module().runtime_compiler_paths()
    hashes_match(compiler_snapshot, 'pre-run actual Cloud compiler dependencies')
    snapshot_at = parsed_stamp(snapshot['at'])
    verification, captures, build_checks, failures, native = {}, {}, [], [], {}
    runtime_artifacts, runtime_hashes, common_compiler = {}, {}, None
    nested_quota_checks = {}
    invocation_ids = set()
    for target in ('python', 'cloud'):
        for suite, title, count in SUITES:
            label = ('Python' if target == 'python' else 'Cloud') + title
            path = OUT / report_name(target, suite, title)
            raw = read(path)
            run = raw.get('latest', raw)
            assert run['pass'] is True and run['failed'] == 0 and run['passed'] == count, (label, 'not passed / wrong count')
            results = run['results']
            assert len(results) == count and all(row['pass'] is True for row in results), label
            assert len({row['name'] for row in results}) == count, (label, 'duplicate checks')
            launcher = run['taskAlertLauncher']
            assert launcher['suite'] == suite and launcher['identityUnchanged'] is True, label
            assert launcher['childExitCode'] == 0 and launcher['reportFreshForInvocation'] is True, (label, 'failed child / stale report')
            assert launcher['syntheticOnly'] is True and launcher['productionEnabled'] is False, label
            assert launcher['runId'] and launcher['runId'] not in invocation_ids, (label, 'duplicate invocation')
            invocation_ids.add(launcher['runId'])
            assert parsed_stamp(launcher['invocationStarted']) >= snapshot_at, (label, 'predates complete pre-run snapshot')
            assert parsed_stamp(run['at']) >= parsed_stamp(launcher['invocationStarted']), (label, 'stale run timestamp')
            assert launcher['sourceAndBuildHashes'] == common, (label, 'different final source/build/QA map')
            if suite == 'quota-compat':
                nested_quota_checks[label] = validate_nested_quota(run, common, snapshot_at, label)
            artifacts, artifact_hashes, compiler = validate_runtime_artifacts(run, common, target, label)
            if target == 'cloud':
                runtime_artifacts[label] = artifacts
                runtime_hashes.update(artifact_hashes)
                if common_compiler is None:
                    common_compiler = compiler
                assert compiler == common_compiler == compiler_snapshot, (label, 'Different actual compiler across snapshot/Cloud gates')
            if suite in ('special', 'visual'):
                assert launcher['actualBootstrapCli'] is True and launcher['runtimeManifest']['backend'] == target, label
                assert run['taskAlertSourcesUnchanged'] is True and run['taskAlertSources'] == common, (label, 'inner/outer mismatch')
                app_name = '03_当前APP/东方智慧-首页体验R4.html' if target == 'python' else '04_研发源码/app/cloud/generated/experience.html'
                assert launcher['runtimeManifest']['appSha256'] == common[app_name], (label, 'actual APP marker mismatch')
            if raw.get('runs'):
                assert raw['runs'][-1] == run, (label, 'latest/history mismatch')
            if suite == 'full':
                assert {'东方智慧-首页体验R4.html', '发给负责人-东方智慧首页R4.html', '计时后台-开发联调.html'} <= set(run['buildHashes'])
                if target == 'cloud':
                    assert {'generated/experience.html', 'generated/admin.html', 'generated/review.html', 'lib/eastern-api.ts', 'worker/index.ts', 'dist/server/index.js'} <= set(run['cloudBuildHashes'])
                for field, folder in [('buildHashes', '03_当前APP'), ('cloudBuildHashes', '04_研发源码/app/cloud')]:
                    for name, expected in run.get(field, {}).items():
                        relative = folder + '/' + name
                        assert sha(local_path(relative)) == expected, (label, 'full build mismatch', relative)
                        build_checks.append({'gate': label, 'path': relative, 'sha256': expected})
            if suite == 'special':
                coverage = run['coverage']
                for field in ('actualRunnerProcesses', 'actualApiProcessRestart', 'actualReceiverProcessRestart', 'actualNativeClaimFence', 'signedLocalNotifications'):
                    assert coverage[field] is True, (label, 'missing actual native coverage', field)
                assert coverage['realSupplier'] is False and coverage['production'] is False
                pids = {row['pid'] for row in run['runnerProcesses']}
                assert len(pids) >= 2 and all(isinstance(pid, int) and pid > 0 for pid in pids)
                assert run['paginationProof']['actualNewWorkers'] == run['paginationProof']['actualNewRuns'] == 51
                assert run['paginationProof']['actualNewBacklogAlerts'] == 51
                if target == 'cloud':
                    assert coverage['actualR2DeleteAndHead'] is True
                native[target] = {'coverage': coverage, 'runnerProcesses': run['runnerProcesses'],
                                  'actualRestarts': run['actualRestarts'], 'paginationProof': run['paginationProof']}
            for name in run.get('captures', []):
                relative = name if name.startswith('06_') else '06_验证与后续工作/' + name
                captures[relative] = sha(local_path(relative))
            verification[label] = {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'passed': count, 'failed': 0,
                                   'at': run.get('at'), 'reportRunId': run.get('runId'), 'launcherRunId': launcher['runId'], 'freshReportVerified': True}
            for previous in raw.get('runs', []):
                if previous.get('pass') is not True:
                    failures.append({'report': path.name, 'at': previous.get('at'), 'passed': previous.get('passed'),
                                     'failed': previous.get('failed'), 'failedNames': [r['name'] for r in previous.get('results', []) if r.get('pass') is not True]})
    assert len(verification) == 18
    assert all(sum(row['passed'] for name, row in verification.items() if name.startswith(target)) == 239 for target in ('Python', 'Cloud'))
    assert len(build_checks) >= 12
    builds = {name: sha(local_path(name)) for name in baseline['buildHashes']}
    generator = snapshot['buildPreparationInputHashes']
    helpers = {p.relative_to(ROOT).as_posix(): sha(p) for p in [Path(__file__), OUT / (PREFIX + '依赖盘点.py')]}
    return {'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'module': PREFIX,
        'stage': 27, 'taskIds': IDS, 'pass': True, 'status': 'local-continuous-tasks-and-alert-records-verified-production-pending',
        'scope': '显式fresh runtime与manifest、真实管理员session运行器持续进程/重启恢复、逐业务单元同事务双租约门禁、五白名单任务、只读本地对账及有限数字/会员已物化事实监测、版本化异常受理与持久HMAC本机通知回执；中文后台与四语APP兼容。',
        'verification': verification, 'perBackendGateCount': 239, 'recordedIdentityChecked': True,
        'identityMeaning': 'All 18 fresh successful child invocations and main/visual inner maps bind the same complete pre-run execution inventory and current bytes; no production deployment claim.',
        'reportIdentityHashes': common, 'source_hashes': {n: v for n, v in common.items() if n not in builds},
        'build_hashes': builds, 'buildPreparationInputHashes': generator, 'actualFullBuildIdentityChecks': build_checks,
        'currentOnlyBuildArtifacts': sorted(set(builds) - (set(common) | {x['path'] for x in build_checks})),
        'visualEvidenceSHA256': captures, 'nativeRuntimeEvidence': native,
        'runtimeArtifactEvidence': runtime_artifacts, 'runtimeArtifactSHA256': runtime_hashes,
        'nestedQuotaFreshnessChecks': nested_quota_checks,
        'runtimeArtifactBoundary': 'Each actual Cloud bundle/metafile graph is checked against the common current project inputs and four recorded compiler files. Owned runtime state and node_modules toolchain are evidence at verification time, not represented as carried production state or bundled workspace dependencies.',
        'preflight': {'path': BASELINE.relative_to(ROOT).as_posix(), 'sha256': BASELINE_SHA256, 'originalFileCount': 909, 'preservedHistoricalFileCount': 612},
        'fullInputPreRunSnapshot': {'path': snapshot_path.relative_to(ROOT).as_posix(), 'sha256': sha(snapshot_path), 'inputCount': len(required), 'runtimeCompilerDependencyCount': len(compiler_snapshot), 'canonicalSHA256': snapshot['canonicalSHA256'], 'boundary': snapshot['boundary']},
        'initialRoundEvidence': {'snapshot': {'path': initial_snapshot_path.relative_to(ROOT).as_posix(), 'sha256': INITIAL_SNAPSHOT_SHA256},
            'diagnostic': {'path': first_failure_path.relative_to(ROOT).as_posix(), 'sha256': FIRST_FAILURE_SHA256},
            'countedAsPassedGate': False},
        'secondRoundEvidence': {'snapshot': {'path': second_snapshot_path.relative_to(ROOT).as_posix(), 'sha256': SECOND_SNAPSHOT_SHA256},
            'diagnostic': {'path': second_failure_path.relative_to(ROOT).as_posix(), 'sha256': SECOND_FAILURE_SHA256},
            'preservedCopyCount': len(second_copies), 'countedAsFinalGate': False},
        'thirdRoundEvidence': {'snapshot': {'path': third_snapshot_path.relative_to(ROOT).as_posix(), 'sha256': THIRD_SNAPSHOT_SHA256},
            'diagnostic': {'path': third_failure_path.relative_to(ROOT).as_posix(), 'sha256': THIRD_FAILURE_SHA256},
            'preservedCopyCount': len(third_copies), 'countedAsFinalGate': False},
        'fourthRoundEvidence': {'snapshot': {'path': fourth_snapshot_path.relative_to(ROOT).as_posix(), 'sha256': FOURTH_SNAPSHOT_SHA256},
            'diagnostic': {'path': fourth_failure_path.relative_to(ROOT).as_posix(), 'sha256': FOURTH_FAILURE_SHA256},
            'preservedCopyCount': len(fourth_copies), 'countedAsFinalGate': False},
        'authorizedWorkbookBaselineSHA256': baseline['authorizedWorkbookBaselineSHA256'],
        'preservedHistoricalSHA256': preserved, 'failureHistory': failures, 'diagnosticEvidenceSHA256': diagnostic_hashes(),
        'deliveryHelperSHA256': helpers, 'freezeHelperSHA256': sha(Path(__file__)),
        'production': {'productionDeployed': False, 'productionScheduler': False, 'realExternalNotification': False, 'realRefundSettlement': False, 'originalDatabaseUsed': False},
        'limitations': ['默认关闭，仅显式fresh本机隔离runtime与当前真实管理员授权；manifest磁盘路径是启动者声明，HTTP不证明物理路径。',
            '本机持续进程与重启恢复不等于生产cron、受管服务部署或目标设备验收；失去会话/角色须重新明确授权，不自动登录。',
            '通知仅签名loopback-fixture真实HTTP确认，externalSent=false；真实渠道/退款失败源未知为null，真实外部通知仍待实施。',
            '监测纯读且按完整本地source/规则解除；缺失、截断、坏JSON、未配置龄规则不伪称健康0；会员未物化懒授不报漏发。',
            'IO超时/旧租约不证明外部操作停止；已有业务领取按原门禁完成，不伪取消或重置有限attempts。',
            '原7scope/新4域的生产到期扫描、外部供应商/备份/向量清理、生产监控策略与渠道联调继续按实际缺口推进。',
            '四语范围由APP完整回归覆盖；任务操作台为中文，不宣称四语后台、藏语母语审校或实机验证。'],
        'frozenBytes': 'UTF-8 LF write_bytes; no previous receipt/report/helper is overwritten.'}


def freeze():
    target = OUT / (PREFIX + '-实施记录.json')
    assert not target.exists(), 'Never overwrite a frozen receipt'
    receipt = collect()
    target.write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'stage': 27, 'receipt': str(target), 'sha256': sha(target), 'perBackendGateCount': 239}, ensure_ascii=True))


if __name__ == '__main__':
    if '--inspect' in sys.argv:
        result = collect()
        print(json.dumps({'pass': True, 'stage': 27, 'gateCount': len(result['verification']), 'perBackendGateCount': 239}, ensure_ascii=True))
    else:
        freeze()
