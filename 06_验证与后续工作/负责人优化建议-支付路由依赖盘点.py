"""Independent stage28 execution inventory; no services or artifact authors are started.

The reviewed launcher inputs are explicit.  The old freezer is imported only for
its read-only required_identity_paths(), never collect()/freeze().  Generator
inputs are reported separately and are not falsely called executed QA inputs.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-支付路由'
NODE = Path('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
QA_FILES = ('测试工具.cjs', '验收启动.cjs', '用例工具.cjs', '专项.cjs', '结算专项.cjs', '补充视觉.cjs', '入口预检.cjs', '入口清单.json', 'Python测试服务.py', 'Cloud测试服务.ts', '夹具控制.py', '夹具控制.ts', '隐私夹具控制.py', '隐私夹具控制.ts', '会员Python测试服务.py', '会员Cloud测试服务.ts', '回调兼容.cjs', '恢复兼容.cjs', '迟到兼容.cjs', '脱敏前置.cjs', '旧订单夹具.json')
EXTRA_INPUTS = ('负责人优化建议-支付路由-实施合同.json', '负责人优化建议-会员额度会员兼容.cjs', '负责人优化建议-会员额度会员浏览器兼容.cjs', '负责人优化建议-会员专项.cjs', '负责人优化建议-会员浏览器专项.cjs', '负责人优化建议-数字权益迟到兼容.cjs', '负责人优化建议-会员额度Python测试服务.py', '负责人优化建议-会员额度专项.cjs', '负责人优化建议-会员额度-进度表校验.py', '负责人优化建议-会员额度Cloud测试服务.ts', '负责人优化建议-会员额度HTTP流式夹具.py', '负责人优化建议-会员额度用例工具.cjs', '负责人优化建议-会员额度测试工具.cjs', '负责人优化建议-会员额度旧库夹具.sql', '负责人优化建议-会员额度进度回填.py', '负责人优化建议-会员额度补充视觉.cjs', '负责人优化建议-会员额度网关兼容.cjs', '负责人优化建议-会员额度验收冻结.py', '负责人优化建议-会员额度验收启动.cjs')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_path(name):
    assert isinstance(name, str) and name and '\\' not in name and '\x00' not in name
    relative = Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts
    path = (ROOT / relative).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(), ('Missing fixed input', name)
    return path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def required_identity_paths():
    previous = load_module('stage27_read_only_inventory', OUT / '负责人优化建议-任务告警依赖盘点.py')
    paths = set(previous.required_identity_paths())
    paths.update('06_验证与后续工作/' + PREFIX + suffix for suffix in QA_FILES)
    paths.update('06_验证与后续工作/' + suffix for suffix in EXTRA_INPUTS)
    paths.update({'04_研发源码/app/r4/backend/payment_routing_schema.sql', '04_研发源码/app/cloud/generated/payment-routing-schema.sql'})
    # Include the actual --import bootstrap, not just require()/from imports.
    # Product/raw and emitted entry imports are execution inputs too. The previous
    # stage only followed QA imports; follow all current declared entry sources.
    pending = [name for name in paths if Path(name).suffix in {'.cjs', '.js', '.mjs', '.ts', '.mts'}]
    pending.append('04_研发源码/app/cloud/scripts/sites-env.mjs')
    inspected = set()
    while pending:
        name = pending.pop()
        if name in inspected:
            continue
        inspected.add(name)
        source = local_path(name)
        code = source.read_text(encoding='utf-8')
        imports = re.findall(r'''(?:\brequire|\bimport)\(\s*['"](\.[^'"]+)['"]\s*\)''', code)
        imports += re.findall(r'''(?:\bfrom\s*|\bimport\s*)['"](\.[^'"]+)['"]''', code)
        for dependency in imports:
            base = (source.parent / dependency.split('?', 1)[0]).resolve()
            choices = [base, Path(str(base).removesuffix('.mjs') + '.mts') if str(base).endswith('.mjs') else base,
                       Path(str(base).removesuffix('.js') + '.ts') if str(base).endswith('.js') else base]
            choices += [Path(str(base) + ext) for ext in ('.cjs', '.js', '.mjs', '.ts', '.mts', '.json', '.html', '.sql')]
            candidate = next((p for p in choices if p.is_file()), None)
            assert candidate and candidate.is_relative_to(ROOT), ('Unbound local import', name, dependency)
            relative = candidate.relative_to(ROOT).as_posix()
            paths.add(relative)
            if candidate.suffix in {'.cjs', '.js', '.mjs', '.ts', '.mts'}:
                pending.append(relative)
    for name in paths:
        local_path(name)
    assert '06_验证与后续工作/' + PREFIX + '脱敏前置.cjs' in paths
    return paths


def build_preparation_paths():
    """Actual generator FS inputs, apart from files already in the execution map."""
    r4 = '04_研发源码/app/r4/'
    names = ['assets.json', 'build_i18n.py', 'i18n-bo.json', 'i18n-bo-draft.json', 'i18n-extra.json',
             'creator-center.html', 'review.html', 'vendor/iztro-LICENSE.txt', 'vendor/iztro-2.6.2.min.js',
             'vendor/opencc-cn2t-1.0.5.js', 'vendor/opencc-LICENSE.txt', 'vendor/opencc-data-LICENSE.txt',
             'vendor/lunar-1.7.7.js', 'vendor/lunar-1.7.7-LICENSE.txt',
             'vendor/astronomy-engine-2.1.19.min.js', 'vendor/astronomy-engine-LICENSE.txt',
             'vendor/NotoSerifTibetan-OFL.txt', 'images/quote-landscape.png', 'images/map-life.png',
             'images/map-body.png', 'images/map-mind.png', 'images/community-preview.mp4']
    paths = {r4 + name for name in names if (ROOT / r4 / name).is_file()}
    paths.add('06_验证与后续工作/四语文案清单.json')
    for name in ('package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts', '.openai/hosting.json', 'db/schema.ts'):
        relative = '04_研发源码/app/cloud/' + name
        if (ROOT / relative).is_file():
            paths.add(relative)
    return paths


def runtime_compiler_paths():
    # These installed executable dependencies are deliberately not project source
    # or handoff contents, but the actual Cloud prebundle now reads/runs them.
    return {
        '04_研发源码/app/cloud/node_modules/esbuild/lib/main.js',
        '04_研发源码/app/cloud/node_modules/esbuild/package.json',
        '04_研发源码/app/cloud/node_modules/@esbuild/win32-x64/package.json',
        '04_研发源码/app/cloud/node_modules/@esbuild/win32-x64/esbuild.exe',
    }


def inventory():
    required = required_identity_paths()
    command = "const h=require('./06_验证与后续工作/负责人优化建议-支付路由测试工具.cjs');process.stdout.write(JSON.stringify({files:h.sourceFiles(),qaFiles:h.qaFiles,identity:h.identity()}));"
    actual = json.loads(subprocess.check_output([str(NODE), '-e', command], cwd=ROOT, text=True, encoding='utf-8'))
    assert set(actual['qaFiles']) == set(QA_FILES) and len(actual['qaFiles']) == len(QA_FILES), 'Reviewed QA list drifted'
    assert len(actual['files']) == len(set(actual['files'])), 'Duplicate identity paths'
    missing = sorted(required - set(actual['files']))
    extra = sorted(set(actual['files']) - required)
    assert not missing and not extra, ('Independent/harness input inventory mismatch', missing, extra)
    mapping = {name: sha(local_path(name)) for name in sorted(required)}
    assert mapping == actual['identity'], 'Harness and independent hashes differ'
    canonical = json.dumps(mapping, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    generator = {name: sha(local_path(name)) for name in sorted(build_preparation_paths() - required)}
    compiler = {name: sha(local_path(name)) for name in sorted(runtime_compiler_paths())}
    return {'at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), 'pass': True,
            'inputCount': len(mapping), 'sourceAndBuildHashes': mapping,
            'canonicalSHA256': hashlib.sha256(canonical).hexdigest(),
            'independentRequiredCount': len(required), 'harnessCount': len(actual['files']),
            'missingFromHarness': missing, 'harnessAdditional': extra,
            'explicitChildPreload': '06_验证与后续工作/' + PREFIX + '脱敏前置.cjs',
            'buildPreparationInputHashes': generator,
            'runtimeCompilerDependencyHashes': compiler,
            'runtimeCompilerBoundary': 'Four installed esbuild API/package/platform/binary inputs are bound separately from project execution inputs; node_modules is not included in handoff.',
            'boundary': 'Independent actual project source/build/QA execution inventory matched before gates. Generator-only FS inputs and four actual installed Cloud compiler dependencies are separately bound, without inflating the project input count or claiming each QA gate executes generator inputs. No service, test, freeze, progress update or workbook author is started.'}


if __name__ == '__main__':
    import sys
    result = inventory()
    target = OUT / (PREFIX + '-依赖盘点.json')
    snapshot_flags = {'--snapshot', '--retry-snapshot', '--context-retry-snapshot', '--visual-retry-snapshot', '--compat-retry-snapshot', '--launcher-retry-snapshot'} & set(sys.argv)
    assert len(snapshot_flags) <= 1, 'Choose exactly one distinct snapshot generation'
    if '--context-retry-snapshot' in sys.argv:
        target = OUT / (PREFIX + '-上下文复验完整依赖诊断.json')
        assert not target.exists(), 'Never overwrite the strict-context retry snapshot'
    elif '--launcher-retry-snapshot' in sys.argv:
        target = OUT / (PREFIX + '-启动器复验完整依赖诊断.json')
        assert not target.exists(), 'Never overwrite the launcher-retry pre-run snapshot'
    elif '--compat-retry-snapshot' in sys.argv:
        target = OUT / (PREFIX + '-兼容复验完整依赖诊断.json')
        assert not target.exists(), 'Never overwrite the compatibility-retry pre-run snapshot'
    elif '--visual-retry-snapshot' in sys.argv:
        target = OUT / (PREFIX + '-视觉复验完整依赖诊断.json')
        assert not target.exists(), 'Never overwrite the visual-retry pre-run snapshot'
    elif '--retry-snapshot' in sys.argv:
        target = OUT / (PREFIX + '-复验完整依赖诊断.json')
        assert not target.exists(), 'Never overwrite a retry pre-run snapshot'
    elif '--snapshot' in sys.argv:
        target = OUT / (PREFIX + '-完整依赖诊断.json')
        assert not target.exists(), 'Never overwrite the independent pre-run snapshot'
    if snapshot_flags:
        target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'inputCount': result['inputCount'], 'canonicalSHA256': result['canonicalSHA256'], 'report': str(target) if snapshot_flags else None, 'readOnly': not bool(snapshot_flags)}, ensure_ascii=True))
