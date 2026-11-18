"""Validate final evidence; --write creates four core, two compatibility and four supporting exclusive snapshots plus one implementation record.
No tests, services, builds, business sources, task statuses or databases are executed or changed.
Prepared for root; do not execute until the final dual full60, bridge16, gateway25 and visual review finish.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-八字解读关联'
BRIDGE = '04_研发源码/app/r4/bazi-interpretation-bridge.js'
BACKENDS = ['04_研发源码/app/r4/backend/ai_gateway.py', '04_研发源码/app/cloud/lib/ai-gateway.ts']
REQUIRED_SOURCES = [BRIDGE, *BACKENDS,
    *['04_研发源码/app/r4/' + n for n in ['bazi-result-version.js', 'bazi-result-version-ui.js', 'bazi-result-version-release.js', 'bazi-result-version.css',
       'life-chart-core.js', 'life-chart-bazi.js', 'life-chart-bazi-layout.js', 'bazi-time.js', 'bazi-compare.js', 'bazi-glossary.js', 'life-birth-entry.js',
       'vendor/lunar-1.7.7.js', 'vendor/NotoSerifTibetan.woff2', 'base.js', 'platform.js', 'service-social.js', 'privacy-center.js', 'privacy-ai-client.js',
       'ai-gateway-ui.js', 'backend/privacy.py', 'backend/privacy_saved.py', 'backend/privacy_gateway_bridge.py', 'backend/server.py', 'build.py']],
    *['04_研发源码/app/cloud/' + n for n in ['lib/eastern-api.ts', 'lib/privacy-api.ts', 'lib/privacy-saved.ts', 'lib/privacy-gateway-bridge.ts', 'worker/index.ts', 'prepare.py']]]
LOCAL_BUILDS = ['东方智慧-首页体验R4.html', '发给负责人-东方智慧首页R4.html', '计时后台-开发联调.html']
CLOUD_BUILDS = ['generated/experience.html', 'generated/admin.html', 'generated/review.html', 'lib/eastern-api.ts', 'worker/index.ts', 'dist/server/index.js']
REQUIRED_BUILDS = ['03_当前APP/' + n for n in LOCAL_BUILDS] + ['04_研发源码/app/cloud/' + n for n in [
    'generated/experience.html', 'generated/admin.html', 'generated/review.html', 'dist/server/index.js', 'dist/server/BUILD_ID', 'public/assets/NotoSerifTibetan.woff2']]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def project_file(value, base=ROOT):
    path = (base / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    assert path.is_relative_to(ROOT.resolve()) and path.is_file(), ('Missing/outside-project evidence', str(value))
    return path

def relative(path):
    return path.resolve().relative_to(ROOT.resolve()).as_posix()

def read_report(path):
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    return obj.get('latest', obj)

def passed(path, count, key='results'):
    obj = read_report(path)
    assert obj.get('pass', True) is True and obj.get('passed') == count and obj.get('failed') == 0, (path.name, 'gate failed')
    assert len(obj[key]) == count and all(row.get('pass') is True for row in obj[key]), (path.name, 'incorrect case receipts')
    return obj

def check_hashes(mapping, base=ROOT):
    assert mapping, 'Missing identity map'
    for name, digest in mapping.items():
        assert re.fullmatch('[a-f0-9]{64}', digest) and sha(project_file(name, base)) == digest, ('Identity drift', name)

def json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def node_identity_sha(identity):
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-full', type=Path, default=OUT / (PREFIX + '-本轮全量回归结果.json'))
    parser.add_argument('--cloud-full', type=Path, default=OUT / (PREFIX + '-公网适配全量回归结果.json'))
    parser.add_argument('--write', action='store_true', help='Explicitly write immutable final evidence after every check passes')
    args = parser.parse_args()
    snapshots, verification, watched, actual, identities = {}, {}, {}, {}, {}

    def verify_receipt(label, path, obj, snapshot=None):
        path = project_file(path)
        watched[relative(path)] = sha(path)
        if snapshot:
            target = OUT / (PREFIX + '-' + snapshot + '.json')
            assert not target.exists(), ('Refuse overwrite frozen evidence', target.name)
            data = json_bytes(obj)
            snapshots[target] = data
            verification[label] = {'path': relative(target), 'sha256': hashlib.sha256(data).hexdigest(),
                'passed': obj.get('passed'), 'at': obj.get('at'), 'runId': obj.get('runId'),
                'sourceReport': relative(path), 'sourceReportSha256': sha(path)}
        else:
            verification[label] = {'path': relative(path), 'sha256': sha(path), 'passed': obj.get('passed'), 'runId': obj.get('runId')}

    for label, path, suffix in [('Python全量', args.python_full, '本机全量验收'), ('Cloud全量', args.cloud_full, '本地Cloud全量验收')]:
        path = project_file(path)
        report = passed(path, 60)
        assert report['coverage']['backend'] is True and report['coverage']['adminUi'] is True
        assert report['coverage']['liveAi'] is False
        for name in LOCAL_BUILDS:
            assert report['buildHashes'].get(name) == sha(project_file('03_当前APP/' + name)), (label, name, 'wrong HTML')
        for name, digest in report['buildHashes'].items():
            target = ROOT / name if (ROOT / name).is_file() else ROOT / '03_当前APP' / name
            assert sha(project_file(target)) == digest, (label, name, 'build drift')
        if label == 'Cloud全量':
            assert report.get('cloudWorker') is True
            assert all(name in report.get('cloudBuildHashes', {}) for name in CLOUD_BUILDS), 'Incomplete Cloud build receipts'
        if report.get('cloudBuildHashes'):
            check_hashes(report['cloudBuildHashes'], ROOT / '04_研发源码/app/cloud')
        verify_receipt(label, path, report, suffix)

    for target, label, suffix in [('python', 'Python专项', 'Python专项验收'), ('cloud', 'Cloud专项', 'Cloud专项验收')]:
        path = OUT / ('负责人优化建议-B11解读桥专项-' + target + '.json')
        report = passed(path, 16)
        actual[target] = report
        assert report['target'] == target and report['identityUnchanged'] is True
        assert report['syntheticDataOnly'] is True and report['productionWrites'] is False
        assert report['providerMode'] == 'local-process-mock' and report['externalProviderTested'] is False and report['promptLogging'] is False
        assert report['coverage']['realHttp'] is True and report['coverage']['realBrowser'] is True and report['coverage']['realSupplier'] is False
        assert not report.get('errors') and not report.get('browserRateLimits'), 'Unexpected browser errors or ordinary-flow throttling'
        assert not report.get('gatewayRateWindowPacingMs'), 'Paced diagnostic run is not a final acceptance gate'
        budget = report['rateBudgets']
        assert budget == {'readsPerMinute': 180, 'read181Status': 429, 'writesPerMinute': 30, 'write31Status': 429,
            'readDoesNotSpendWriteBudget': True, 'writeDoesNotSpendReadBudget': True, 'noJobOrQuotaCreated': True, 'limiterDisabled': False}
        for name in REQUIRED_SOURCES:
            assert name in report['identity']['sources'], (label, 'missing source', name)
        for name in REQUIRED_BUILDS:
            assert name in report['identity']['builds'], (label, 'missing build/font/worker identity', name)
        check_hashes(report['identity']['sources'])
        check_hashes(report['identity']['builds'])
        check_hashes(report['testHashes'], OUT)
        app_path = '03_当前APP/东方智慧-首页体验R4.html' if target == 'python' else '04_研发源码/app/cloud/generated/experience.html'
        assert report['servedBuildSha256'] == sha(project_file(app_path))
        font = report['fontIdentity']
        assert report['realAppFontLoaded'] is True and font['sha256'] == sha(project_file(font['sourcePath']))
        assert font['sourcePath'] == '04_研发源码/app/r4/vendor/NotoSerifTibetan.woff2' and font['bytes'] > 1000
        if target == 'python':
            assert font['embeddedVerified'] is True
        else:
            assert font['assetVerified'] is True and report['localFontAssetVerified'] is True
            assert font['sha256'] == sha(project_file('04_研发源码/app/cloud/public/assets/NotoSerifTibetan.woff2'))
        captures = report['captureEvidence']
        assert len(captures) == len(report['captures']) == 4, 'Expected four reviewed key screenshots, no failed-capture substitution'
        for item, filename in zip(captures, report['captures']):
            assert item['path'] == '06_验证与后续工作/' + filename and target + '-' + report['runId'] in filename
            assert item['target'] == target and item['runId'] == report['runId'] and item['servedBuildSha256'] == report['servedBuildSha256']
            assert item['sourceIdentitySha256'] == node_identity_sha(report['identity'])
            image = project_file(item['path'])
            assert image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') and sha(image) == item['sha256']
            watched[relative(image)] = item['sha256']
        identities[target] = report['identity']
        verify_receipt(label, path, report, suffix)
    assert identities['python'] == identities['cloud'], 'Actual targets did not test the same final source/build/font snapshot'

    for target, label in [('python', 'Python原网关兼容'), ('cloud', 'Cloud原网关兼容')]:
        path = OUT / ('负责人优化建议-AI网关专项-' + target + '.json')
        report = passed(path, 25)
        assert report['identityUnchanged'] is True and report['productionWrites'] is False and report['externalProviderTested'] is False
        assert report['coverage']['realHttp'] is True and report['coverage']['realBrowser'] is True and not report.get('errors')
        assert report['module'] == '负责人优化建议-八字解读关联-网关兼容'
        for name in BACKENDS:
            assert report['identity']['sources'].get(name) == sha(project_file(name)), 'Gateway compatibility used stale backend'
        check_hashes(report['identity']['sources'])
        check_hashes(report['identity']['builds'])
        check_hashes(report['testHashes'], OUT)
        verify_receipt(label, path, report, 'Python网关兼容验收' if target == 'python' else 'Cloud网关兼容验收')

    vm_path = OUT / '负责人优化建议-B11解读桥VM专项.json'
    vm = passed(vm_path, 24)
    assert vm['sourceSha256'] == sha(project_file(BRIDGE)) and vm['upstreamCalled'] is False
    verify_receipt('桥接VM', vm_path, vm, '桥接VM验收')
    for label, name, count, source_key, source_path in [
        ('Python网关内存', '负责人优化建议-AI网关内存专项.json', 47, BACKENDS[0], BACKENDS[0]),
        ('Cloud网关内存', '负责人优化建议-AI网关Cloud内存专项.json', 44, 'lib/ai-gateway.ts', BACKENDS[1])]:
        path = OUT / name
        report = passed(path, count, 'checks')
        assert report['realModelRequests'] == 0 and report['productionDatabaseAccess'] is False
        source_hashes = {k.replace('\\', '/'): v for k, v in report['sourceSha256'].items()}
        assert source_hashes[source_key] == sha(project_file(source_path))
        check_hashes(source_hashes, ROOT / '04_研发源码/app/cloud' if label.startswith('Cloud') else ROOT)
        verify_receipt(label, path, report, label + '验收')

    visual_path = OUT / '负责人优化建议-B11解读桥最终视觉核验.json'
    visual = read_report(project_file(visual_path))
    assert visual['pass'] is True and visual['allKeyImagesViewed'] is True
    assert visual['runIds'] == {target: obj['runId'] for target, obj in actual.items()}
    expected_images = {item['path']: item['sha256'] for report in actual.values() for item in report['captureEvidence']}
    assert {item['path']: item['sha256'] for item in visual['images']} == expected_images
    assert all(item['viewed'] is True and item['pass'] is True for item in visual['images'])
    for name, digest in expected_images.items():
        assert sha(project_file(name)) == digest
    verify_receipt('关键截图目视核验', visual_path, visual, '关键截图目视核验')

    identity = identities['python']
    watched.update(identity['sources'])
    watched.update(identity['builds'])
    record = {'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'module': PREFIX, 'pass': True,
        'scope': '实际四柱AI入口的最小摘要授权发送、真实新增legacy/SSE回复与原排盘/UTC/规则/实现和当时流运的本机关联；默认会话保存关闭，授权后纯metadata随既有个人存储往返恢复；真实源缺失或未知未绑定，完整旧版本保留原版本并标historical；本人GET网关180/min独立于原非GET30/min预算。',
        'verification': verification, 'source_hashes': identity['sources'], 'build_hashes': identity['builds'],
        'app_sha256': sha(project_file('03_当前APP/东方智慧-首页体验R4.html')),
        'admin_sha256': sha(project_file('03_当前APP/计时后台-开发联调.html')),
        'worker_sha256': sha(project_file('04_研发源码/app/cloud/dist/server/index.js')),
        'build_id_sha256': sha(project_file('04_研发源码/app/cloud/dist/server/BUILD_ID')),
        'actual_run_ids': {target: obj['runId'] for target, obj in actual.items()},
        'source_build_identity_sha256': node_identity_sha(identity), 'vm_receipt': vm,
        'font_identity': {target: obj['fontIdentity'] for target, obj in actual.items()},
        'screenshots': [item for obj in actual.values() for item in obj['captureEvidence']], 'visual_review': visual,
        'taskStatusesChanged': False, 'teacherConfirmed': False, 'providerMode': 'explicit-local-process-fixture', 'realModelRequests': 0,
        'limitations': ['真实legacy/网关客户端和本机明示fixture已验，实际外部模型连接、输出质量或供应商清理未验。',
            '默认saveConversations=false；仅原epoch/actor/run/目标消息一致且新鲜保存授权仍开时，纯metadata随既有persist保存。',
            '本机关联只说明排盘来源/版本匹配，不是服务器签名、供应商授权或自动AI缓存复用权限。',
            'restore无真实本人存档或同实现实际当前计算则unbound；旧无metadata/损坏档案/旧restored/server-only快照不自动迁移或补领。',
            'metadata未进入实际客户端模型请求/本机provider出站；正式老师规则和30条确认样本仍未提供，teacherConfirmed保持false。',
            '供应商、备份、长期记忆和注销的既有未完成边界不由本模块替代；藏文仍待母语审校，视口检查不是实机验收。'],
        'failure_history': ['保留最初附加构建文件名误写的启动失败；未接原库。',
            '保留原混合30/min读写预算造成正常第三次回复无关联的实际失败；旧paced16仅诊断，不作最终门禁。',
            '按指令仅两端rate分为GET独立180与非GET原30，保留授权/nonce/credits/并发与所有桥guard；未禁limiter或等待窗口。',
            '保留旧cookie被浏览器logout撤销后的401夹具失败；后续操作使用实际当前session，原保存字节往返、删除晚写和180/181/30/31均以最终fresh服务验证。']}
    target = OUT / (PREFIX + '-实施记录.json')
    assert not target.exists(), ('Refuse overwrite implementation record', target.name)
    snapshots[target] = json_bytes(record)
    for path in snapshots:
        assert not path.exists(), ('Refuse overwrite frozen evidence', path.name)
    # Every report, source/build, screenshot is rechecked immediately before evidence writes.
    check_hashes(watched)
    if args.write:
        for path, data in snapshots.items():
            with path.open('xb') as stream:
                stream.write(data)
    print(json.dumps({'mode': 'write' if args.write else 'validate-only', 'pass': True, 'immutableCoreSnapshots': 4, 'immutableCompatibilitySnapshots': 2,
        'immutableSupportingSnapshots': 4, 'implementationRecords': 1, 'written': len(snapshots) if args.write else 0, 'taskStatusesChanged': False,
        'businessSourcesChanged': False, 'buildExecuted': False, 'databaseOpened': False}, ensure_ascii=False))

if __name__ == '__main__':
    main()
