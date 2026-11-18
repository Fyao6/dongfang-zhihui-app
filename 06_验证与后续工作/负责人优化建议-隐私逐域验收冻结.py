"""Stage 26 freezer. Prepared only; running it requires every final, fresh dual-backend gate.

No test service is started here. No old receipt/report/database is rewritten.
Expected case counts are explicit and must be revised if the actual approved QA plan changes.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import ast
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-隐私逐域'
BASELINE = OUT / (PREFIX + '-实施前核对.json')
BASELINE_SHA256 = '96271eabb122519f594a670c13942a1ce700c0bb13850dbbd0822638b37a6f08'
SUITES = [('full', '全量', 60), ('special', '专项', 28), ('visual', '补充视觉', 4),
          ('privacy-compat', '隐私兼容', 27), ('retention-compat', '清理兼容', 26),
          ('closure-compat', '注销兼容', 27), ('memory-compat', '记忆兼容', 10),
          ('digital-compat', '数字兼容', 24), ('quota-compat', '额度兼容专项', 21)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(name):
    assert isinstance(name, str) and name and '\\' not in name and '\x00' not in name, name
    relative = Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts, name
    path = (ROOT / relative).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(), name
    return path


def hashes_match(mapping, label):
    assert isinstance(mapping, dict) and mapping, (label, 'empty identity map')
    for name, expected in mapping.items():
        assert isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected), (label, name)
        assert sha(local_path(name)) == expected, (label, 'current bytes differ', name)


def required_identity_paths():
    """Independent product inventory plus the launcher's explicit, reviewed QA dependency list."""
    paths = set()
    for folder, suffixes in [('04_研发源码/app/r4/backend', {'.py'}),
                              ('04_研发源码/app/cloud/lib', {'.ts'}),
                              ('04_研发源码/app/r4', {'.js', '.css'})]:
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).iterdir()
                     if p.is_file() and p.suffix in suffixes)
    paths.update(['04_研发源码/app/r4/build.py', '04_研发源码/app/r4/time-bank-admin.html',
                  '04_研发源码/app/cloud/prepare.py', '04_研发源码/app/cloud/worker/index.ts',
                  '04_研发源码/app/cloud/scripts/sites-env.mjs',
                  '04_研发源码/app/cloud/scripts/tool-environment.mjs',
                  '04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql',
                  '03_当前APP/东方智慧-首页体验R4.html', '03_当前APP/计时后台-开发联调.html',
                  '03_当前APP/发给负责人-东方智慧首页R4.html',
                  '04_研发源码/app/r4/backend/initial-content.json',
                  '04_研发源码/app/cloud/generated/experience.html',
                  '04_研发源码/app/cloud/generated/admin.html',
                  '04_研发源码/app/cloud/generated/review.html',
                  '04_研发源码/app/cloud/generated/seed.json',
                  '04_研发源码/app/cloud/dist/server/BUILD_ID',
                  '04_研发源码/app/r4/images/community-preview-poster.jpg',
                  '04_研发源码/app/r4/vendor/NotoSerifTibetan.woff2',
                  '04_研发源码/app/cloud/public/assets/NotoSerifTibetan.woff2',
                  '04_研发源码/app/cloud/dist/server/index.js'])
    paths.update('04_研发源码/app/cloud/public/assets/' + name for name in [
        'community-preview-poster.jpg', 'community-preview.mp4', 'living-light.png',
        'map-body.png', 'map-life.png', 'map-mind.png', 'quiet-hour.png',
        'quote-landscape.png', 'still-water.png'])
    # The reused digital harness reads these bytes for its own before/after identity;
    # this does not claim that their standalone test entry points are executed.
    paths.update('06_验证与后续工作/负责人优化建议-数字权益' + name for name in [
        '测试工具.cjs', '验收启动.cjs', '用例工具.cjs', '专项.cjs', '补充视觉.cjs',
        'Python测试服务.py', 'Cloud测试服务.ts', '回调兼容.cjs', '恢复兼容.cjs', '迟到兼容.cjs'])
    paths.add('06_验证与后续工作/负责人优化建议-交易专项.cjs')
    tool = OUT / (PREFIX + '测试工具.cjs')
    match = re.search(r'const qaFiles=(\[[^;]+\]);', tool.read_text(encoding='utf-8'))
    assert match, 'Explicit QA file list is missing; inspect the launcher contract'
    qa_files = ast.literal_eval(match[1])
    assert isinstance(qa_files, list) and qa_files and len(qa_files) == len(set(qa_files))
    assert all(isinstance(n, str) and '/' not in n and '\\' not in n for n in qa_files)
    paths.update('06_验证与后续工作/' + PREFIX + n for n in qa_files)
    paths.update('06_验证与后续工作/' + n for n in [
        PREFIX + '-接口合同.json', '全量回归.cjs', '公网适配全量回归.cjs', '后台单元回归.py',
        '负责人优化建议-交易测试工具.cjs', '负责人优化建议-数字权益专项.cjs',
        '负责人优化建议-数字权益测试工具.cjs', '负责人优化建议-数字权益用例工具.cjs',
        '负责人优化建议-支付恢复HTTP查询夹具.py', '负责人优化建议-会员额度用例工具.cjs'])
    # Independently follow local literal imports; a hand-maintained list cannot validate its own omissions.
    script_suffixes = ('.cjs', '.js', '.mjs', '.ts')
    pending = [name for name in paths if name.startswith('06_') and Path(name).suffix in script_suffixes]
    inspected = set()
    while pending:
        name = pending.pop()
        if name in inspected:
            continue
        inspected.add(name)
        source = local_path(name)
        code = source.read_text(encoding='utf-8')
        dependencies = re.findall(r'''(?:require|import)\(\s*['"](\.[^'"]+)['"]\s*\)''', code)
        dependencies += re.findall(r'''(?:\bfrom\s*|\bimport\s*)['"](\.[^'"]+)['"]''', code)
        for dependency in dependencies:
            candidate = (source.parent / dependency.split('?', 1)[0]).resolve()
            if not candidate.is_file():
                candidate = next((Path(str(candidate) + ext) for ext in ('.cjs', '.js', '.mjs', '.ts', '.json')
                                  if Path(str(candidate) + ext).is_file()), candidate)
            assert candidate.is_relative_to(ROOT) and candidate.is_file(), ('Unbound local QA dependency', name, dependency)
            relative = candidate.relative_to(ROOT).as_posix()
            paths.add(relative)
            if candidate.suffix in script_suffixes:
                pending.append(relative)
    for name in paths:
        local_path(name)
    return paths


def report_name(target, suite, label):
    if suite == 'full':
        return PREFIX + '-' + ('本轮' if target == 'python' else '公网适配') + '全量回归结果.json'
    return PREFIX + label + '-' + target + '.json'


def collect():
    assert sha(BASELINE) == BASELINE_SHA256, 'The original preflight anchor changed'
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    assert len(baseline['files']) == 643 and baseline['currentStage'] == 25
    preserved = {}
    for name, expected in baseline['files'].items():
        if name.startswith('06_') and not name.endswith('.xlsx'):
            actual = sha(local_path(name))
            assert actual == expected, ('Historical receipt/report/QA/preview DB changed', name)
            preserved[name] = actual
    assert len(preserved) == 436, 'Original protected history inventory changed'
    required = required_identity_paths()
    snapshot_path = OUT / (PREFIX + '-完整依赖诊断.json')
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
    assert snapshot['inputCount'] == len(required) == 286
    assert set(snapshot['sourceAndBuildHashes']) == required
    hashes_match(snapshot['sourceAndBuildHashes'], 'independent pre-run input snapshot')
    canonical = json.dumps(snapshot['sourceAndBuildHashes'], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    assert hashlib.sha256(canonical).hexdigest() == snapshot['canonicalSHA256']
    verification, captures, build_checks, failures = {}, {}, [], []
    common_identity = None
    storage_proof = {}
    for target in ('python', 'cloud'):
        for suite, title, count in SUITES:
            label = ('Python' if target == 'python' else 'Cloud') + title
            path = OUT / report_name(target, suite, title)
            raw = json.loads(path.read_text(encoding='utf-8'))
            run = raw.get('latest', raw)
            assert run['pass'] is True and run['failed'] == 0, (label, 'not passed')
            results = run['results']
            assert len(results) == count and run['passed'] == count, (label, 'actual gate count differs')
            assert all(row['pass'] is True for row in results), (label, 'failed result')
            names = [row['name'] for row in results]
            assert len(set(names)) == count, (label, 'duplicate result names')
            launcher = run['privacyDomainsLauncher']
            assert launcher['invocationStarted'] >= snapshot['at'], (label, 'gate predates the complete pre-run input snapshot')
            assert launcher['suite'] == suite and launcher['identityUnchanged'] is True, (label, 'launcher identity')
            # A failed child must never relabel a previous passed report with a new launcher identity.
            assert launcher['childExitCode'] == 0 and launcher['reportFreshForInvocation'] is True, (label, 'stale report or failed child')
            assert isinstance(launcher['runId'], str) and launcher['runId'], (label, 'missing invocation ID')
            identity = launcher['sourceAndBuildHashes']
            assert identity == snapshot['sourceAndBuildHashes'], (label, 'not bound to the complete pre-run snapshot')
            assert required <= set(identity), (label, 'omitted executed dependencies', sorted(required - set(identity)))
            hashes_match(identity, label)
            if common_identity is None:
                common_identity = identity
            assert identity == common_identity, (label, 'gates do not bind the same final bytes')
            if suite in ('special', 'visual'):
                assert run['privacyDomainSourcesUnchanged'] is True, (label, 'inner identity changed')
                assert run['privacyDomainSources'] == identity, (label, 'inner/outer dependency maps differ')
            if raw.get('runs'):
                assert raw['runs'][-1] == run, (label, 'latest/run history mismatch')
            if suite == 'full':
                required03 = {'东方智慧-首页体验R4.html', '发给负责人-东方智慧首页R4.html', '计时后台-开发联调.html'}
                assert required03 <= set(run['buildHashes']), (label, '03 build identity missing')
                if target == 'cloud':
                    assert {'generated/experience.html', 'generated/admin.html', 'generated/review.html',
                            'lib/eastern-api.ts', 'worker/index.ts', 'dist/server/index.js'} <= set(run['cloudBuildHashes'])
                for field, folder in [('buildHashes', '03_当前APP'), ('cloudBuildHashes', '04_研发源码/app/cloud')]:
                    for name, expected in run.get(field, {}).items():
                        relative = folder + '/' + name
                        assert sha(local_path(relative)) == expected, (label, 'full build mismatch', relative)
                        build_checks.append({'gate': label, 'path': relative, 'sha256': expected})
            if suite == 'special':
                coverage = run['coverage']
                assert coverage['r2DeleteAndHeadCovered'] is (target == 'cloud'), (label, 'R2 boundary')
                for field in ('sqliteSecureErasure', 'providerDeletion', 'backupDeletion'):
                    assert coverage[field] is False, (label, 'unsupported erasure claim', field)
                proof = run['storageProof']
                assert proof['secureWipe'] is False and isinstance(proof['stages'], list)
                if target == 'cloud':
                    assert proof['backend'] == 'cloud-r2' and proof['r2Operated'] is True
                    assert proof['nativeR2DeleteCount'] > 0 and proof['nativeR2HeadCount'] > 0
                    assert proof['nativeR2HeadMissingCount'] > 0, (label, 'no actual missing HEAD observation')
                else:
                    assert proof['backend'] == 'sqlite-blob' and proof['r2Operated'] is False
                    assert proof['sqliteRowAndBlobLogicalRemoval'] is True
                    assert all(proof[key] == 0 for key in ('nativeR2DeleteCount', 'nativeR2HeadCount', 'nativeR2HeadMissingCount'))
                storage_proof[target] = proof
            for name in run.get('captures', []):
                relative = name if name.startswith('06_') else '06_验证与后续工作/' + name
                captures[relative] = sha(local_path(relative))
            verification[label] = {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path),
                'passed': count, 'failed': 0, 'at': run.get('at'), 'reportRunId': run.get('runId'),
                'launcherRunId': launcher['runId'], 'freshReportVerified': True}
            for previous in raw.get('runs', []):
                if previous.get('pass') is not True:
                    failures.append({'report': path.name, 'at': previous.get('at'),
                        'passed': previous.get('passed'), 'failed': previous.get('failed'),
                        'failedNames': [r['name'] for r in previous.get('results', []) if r.get('pass') is not True]})
    assert sum(v['passed'] for k, v in verification.items() if k.startswith('Python')) == 227
    assert sum(v['passed'] for k, v in verification.items() if k.startswith('Cloud')) == 227
    assert len(build_checks) >= 12, 'Actual current full-regression build hashes missing'
    current_builds = {name: sha(local_path(name)) for name in baseline['buildHashes']}
    bound_builds = set(common_identity) | {item['path'] for item in build_checks}
    current_only = sorted(set(current_builds) - bound_builds)
    diagnostics = {p.relative_to(ROOT).as_posix(): sha(p) for p in OUT.glob(PREFIX + '*.json')
                   if any(word in p.name for word in ('启动执行失败', '启动身份失败', '首轮', '诊断', '探测', 'failure', 'failed'))}
    for name in list(diagnostics):
        document = json.loads(local_path(name).read_text(encoding='utf-8'))
        copies = document.get('preservedReportCopiesSHA256', {})
        if copies:
            hashes_match(copies, 'preserved diagnostic reports')
            diagnostics.update(copies)
    receipt = {'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'module': PREFIX, 'stage': 26, 'taskIds': ['PR04', 'PR05'], 'pass': True,
        'status': 'local-personal-domain-cleanup-verified-external-erasure-pending',
        'scope': '本人逐域清点、四新增域跟踪与手动/确认期限清理、历史起点纳管、版本/nonce/引用保护、闭户首100及受限续办、永久媒体墓碑、Cloud真实对象删除与HEAD缺失核验、本人导出及分页回执；旧七scope及资金/额度/权益事实保留。',
        'verification': verification, 'perBackendGateCount': 227,
        'recordedIdentityChecked': True, 'identityMeaning': 'Every final report is fresh for its successful launcher invocation; all report dependency maps match the current local bytes. This does not assert production deployment.',
        'reportIdentityHashes': common_identity,
        'source_hashes': {name: value for name, value in common_identity.items() if name not in current_builds},
        'build_hashes': current_builds,
        'actualFullBuildIdentityChecks': build_checks,
        'currentOnlyBuildArtifacts': current_only,
        'currentOnlyBuildBoundary': 'These additional current build files are hashed for delivery, without claiming they appear in each test report identity map.',
        'visualEvidenceSHA256': captures, 'storageProof': storage_proof,
        'preflight': {'path': BASELINE.relative_to(ROOT).as_posix(), 'sha256': BASELINE_SHA256,
                      'originalFileCount': 643, 'preservedHistoricalFileCount': len(preserved)},
        'fullInputPreRunSnapshot': {'path': snapshot_path.relative_to(ROOT).as_posix(),
            'sha256': sha(snapshot_path), 'inputCount': len(required),
            'canonicalSHA256': snapshot['canonicalSHA256'],
            'boundary': snapshot['boundary']},
        'authorizedWorkbookBaselineSHA256': {name: value for name, value in baseline['files'].items() if name.endswith('.xlsx')},
        'preservedHistoricalSHA256': preserved, 'failureHistory': failures,
        'diagnosticEvidenceSHA256': diagnostics,
        'diagnosticBoundary': 'Separate startup/identity/diagnostic attempts are preserved by hash and are not counted as passing gates.',
        'freezeHelperSHA256': sha(Path(__file__)),
        'production': {'productionDeployed': False, 'realSupplierDeletionVerified': False,
                       'backupsAndWALSecurelyErased': False, 'originalDatabaseUsed': False},
        'limitations': ['仅当前本方数据库逻辑清理与当前Cloud对象缺失核验，不表示空闲页/WAL/历史版本/备份或受托商已删除。',
            '公开、共有、交易、权益、配额、审核及最小处理证明继续按实际归属保护；正式保留天数未确认仍null。',
            '历史未知年龄只可明确手动删除或从服务端纳管时间开始保护，不伪称历史最后写入日。',
            '已授权并实际传输的媒体字节无法追回；浏览器副本须另行操作。',
            '记录列表实际覆盖51/57条的跨页读取；jobs、receipts、objects仅覆盖接口shape、游标归属和正常数量，本轮未专门完成这三类超过50项的实际分页。',
            '未部署自动调度，不把本机浏览器验证说成生产或目标设备验收。'],
        'frozenBytes': 'UTF-8 LF via write_bytes; old frozen bytes are read-only and checked before writing.'}
    return receipt


def freeze():
    target = OUT / (PREFIX + '-实施记录.json')
    assert not target.exists(), 'Never overwrite a frozen receipt'
    receipt = collect()
    target.write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'stage': 26, 'receipt': str(target), 'sha256': sha(target),
                      'perBackendGateCount': receipt['perBackendGateCount']}, ensure_ascii=False))


if __name__ == '__main__':
    freeze()
