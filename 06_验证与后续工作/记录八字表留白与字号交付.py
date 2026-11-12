"""Record the spacing-only revision after real acceptance; never build, test, deploy or ZIP."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import copy
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / '06_验证与后续工作'
MODULE = '八字留白与字号优化'
OLD = '06_验证与后续工作/真实星盘档案交付记录.json'
RECORD = '06_验证与后续工作/八字表留白与字号交付记录.json'
GUIDE = '05_后台与研发说明/八字表留白与字号优化说明.txt'
PAGES_SMOKE = '06_验证与后续工作/八字留白与字号Pages冒烟.json'
PAGES_PUBLICATION = '06_验证与后续工作/八字留白与字号Pages发布记录.json'
SELF = '06_验证与后续工作/记录八字表留白与字号交付.py'
SPACING_REPORT = '06_验证与后续工作/八字留白字号优化核验.json'
SPACING_BASELINE = '06_验证与后续工作/八字留白字号优化-改前.json'
PAGES_INPUTS = ['.github/workflows/online-preview.yml', '06_验证与后续工作/准备GitHub在线预览.py', '06_验证与后续工作/GitHub静态预览提示.js']


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))


def sha(relative):
    with (ROOT / relative).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tool(name, filename):
    spec = importlib.util.spec_from_file_location(name, Q / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selected_run(relative, phase=None):
    document = read(relative)
    if phase is None:
        return document.get('latest', document)
    candidates = [document.get('phases', {}).get(phase), document.get('latest', document), *reversed(document.get('runs', []))]
    return next((run for run in candidates if isinstance(run, dict) and run.get('phase') == phase and run.get('module') == MODULE), {})


def checked_run(relative, minimum, app_hash, package, base, phase=None, require_sources=True):
    base.safe_file(relative, package)
    run = selected_run(relative, phase)
    need(run.get('pass') is True and run.get('failed') == 0 and run.get('passed', 0) >= minimum and run.get('module') == MODULE, 'Current successful run missing: ' + relative + ('/' + phase if phase else ''))
    need(package.report_app(run) == app_hash, 'Run is not bound to current APP: ' + relative)
    need(not require_sources or run.get('sourceHashes'), 'Current source hashes missing: ' + relative)
    for path, value in {**run.get('sourceHashes', {}), **run.get('dependencyHashes', {})}.items():
        base.safe_file(path, package)
        need(sha(path) == value, 'Run source/dependency changed: ' + path)
    for folder, field in [('03_当前APP', 'buildHashes'), ('04_研发源码/app/cloud', 'cloudBuildHashes')]:
        for path, value in run.get(field, {}).items():
            full = path if path.startswith(('03_当前APP/', '04_研发源码/')) else folder + '/' + path
            base.safe_file(full, package)
            need(sha(full) == value, 'Run build changed: ' + full)
    return run, {'report': relative, 'sha256': sha(relative), 'at': run['at'], 'module': MODULE, 'passed': run['passed']}


def prepare_delivery(args):
    base = tool('spacing_document_helpers', '记录改动文档交付.py')
    package = base.packager_module()
    old = read(OLD)
    need(old.get('pass') is True and old.get('real_western_revision') is True, 'Immutable W1 receipt missing')
    app_hash = sha('03_当前APP/东方智慧-首页体验R4.html')
    full, all_runs = {}, []
    for key, filename in [('local', '本轮全量回归结果.json'), ('cloudflare', '公网适配全量回归结果.json')]:
        run, full[key] = checked_run('06_验证与后续工作/' + filename, 60, app_hash, package, base, require_sources=False)
        need(run.get('buildHashes') and (key != 'cloudflare' or run.get('cloudBuildHashes')), 'Full regression build inventory missing')
        all_runs.append(run)
    runs, verification = {}, {}
    for key, (filename, minimum) in package.UI_REPORTS.items():
        runs[key], verification[key] = checked_run('06_验证与后续工作/' + filename, minimum, app_hash, package, base)
        all_runs.append(runs[key])
    runs['spacing'], verification['spacing'] = checked_run(SPACING_REPORT, 6, app_hash, package, base)
    all_runs.append(runs['spacing'])
    phases = ['local', 'public'] if args.pages_state == 'published' else ['local']
    for phase in phases:
        key = 'pages_' + phase
        runs[key], verification[key] = checked_run(args.pages_smoke_report, 4, app_hash, package, base, phase=phase)
        need(runs[key].get('productionWrites') is False, 'Pages smoke must be isolated')
        all_runs.append(runs[key])
    published = args.pages_state == 'published'
    record = copy.deepcopy(old)
    record.update({
        'checked_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'pass': True, 'revision_module': MODULE, 'ui_revision': True,
        'bazi_spacing_revision': True, 'document_revision': False, 'reference_revision': False,
        'structure_revision': False, 'real_western_revision': False,
        'scope': '仅调整八字表留白、字号与阅读比例；计算、规则、出生资料、档案及账号边界保留。当前03/Cloud构建经本轮双端完整回归和五专项验收；Pages仅提供静态APP预览，Sites/Netlify及账号后台未更新，AI暂缓。',
        'app_build_sha256': app_hash, 'current_full': full, 'verification': verification,
        'guide': GUIDE, 'local_scope_complete': True, 'bazi_spacing_local_scope_complete': True,
        'all_planned_work_complete': False, 'paused_by_user': False,
        'current_source_published': published, 'current_full_stack_source_published': False,
        'github_pages_current_app_published': published, 'zip_repacked': False,
        'production_writes': False, 'deployment_attempted_this_revision': published,
        'previous_real_western_revision': {'report': OLD, 'sha256': sha(OLD), 'app_build_sha256': old['app_build_sha256'], 'scope': 'Immutable W1 acceptance, frozen reports and earlier receipts; not current CSS acceptance.'},
    })
    record['publication'].update({'current_source_published': False, 'public_deployment_pending': True, 'package_matches_public': False, 'github_pages_current_app_published': published, 'scope': 'Original Sites/Netlify and account backend remain unchanged. GitHub Pages static preview has an independently verified state in pages_preview.'})
    before = read(SPACING_BASELINE)
    record['spacing_baseline'] = {'report': SPACING_BASELINE, 'sha256': sha(SPACING_BASELINE), 'at': before['at'], 'app_build_sha256': before['buildSha256'], 'scope': 'Immutable measured before CSS/public APP and two screenshots; not current acceptance.'}
    record['pages_preview'] = {'status': 'published_verified' if published else 'pending', 'published': published, 'url': package.PAGES_URL, 'artifact': package.pages_artifact_identity(), 'scope': 'Static APP guest preview only; no server/account/AI deployment.'}
    if published:
        base.safe_file(args.pages_publication_report, package)
        record['pages_preview']['publication_record'] = {'report': args.pages_publication_report, 'sha256': sha(args.pages_publication_report)}
    prior_zip = read('06_验证与后续工作/最新打包校验结果.json')
    latest_zip = Path(prior_zip['project_archive']).name
    need(sha(latest_zip) == prior_zip['sha256'] and prior_zip.get('crc_pass') is True and prior_zip.get('all_file_hashes_pass') is True, 'Most recent original delivery ZIP changed/unverified')
    record['previous_zip'] = {'path': latest_zip, 'sha256': prior_zip['sha256'], 'app_build_sha256': prior_zip['app_build_sha256'], 'unchanged': True}
    record['preserved_archives'] = [copy.deepcopy(old['previous_zip'])]
    if record['previous_zip'] not in record['preserved_archives']:
        record['preserved_archives'].append(copy.deepcopy(record['previous_zip']))
    record['changed_app_sources'] = sorted(path for path, value in old['source_sha256'].items() if path.startswith('04_研发源码/app/r4/') and sha(path) != value)
    history_fields = ['foundation_baseline', 'previous_ui_revision', 'previous_document_revision', 'previous_reference_revision', 'previous_structure_revision', 'previous_real_western_revision']
    record['historical_receipts_sha256'] = {record[field]['report']: record[field]['sha256'] for field in history_fields}
    package.bazi_spacing_history(record, {})
    checks, historical = {}, {}
    package.historical_foundation(record, checks, historical)
    available = package.collect_files()
    sources = set(old['source_sha256']) | set(PAGES_INPUTS) | {SELF, SPACING_BASELINE, '06_验证与后续工作/八字留白字号优化核验.cjs', '06_验证与后续工作/打包当前交付.py'}
    for relative in available:
        path = Path(relative)
        if relative.startswith('04_研发源码/app/r4/'):
            tail = path.parts[3:]
            if len(tail) == 1 or tail and tail[0] in {'backend', 'vendor'}:
                sources.add(relative)
        elif relative.startswith('04_研发源码/app/cloud/') and '/generated/' not in relative and path.suffix.lower() in {'.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.css', '.html', '.json', '.toml', '.sql', '.txt', '.md'}:
            sources.add(relative)
    for run in all_runs:
        sources.update(run.get('sourceHashes', {}))
        sources.update(run.get('dependencyHashes', {}))
        if run.get('harnessSha256'):
            matches = [p.relative_to(ROOT).as_posix() for p in Q.glob('*.cjs') if sha(p.relative_to(ROOT)) == run['harnessSha256']]
            need(matches, 'Reported current harness not found by SHA')
            sources.update(matches)
    mutable_outputs = {RECORD, GUIDE, args.pages_publication_report, '06_验证与后续工作/最新打包校验结果.json', *[ref['report'] for ref in full.values()], *[ref['report'] for ref in verification.values()]}
    need(not sources.intersection(mutable_outputs), 'A mutable receipt/guide/current report was recursively included in source identities')
    for relative in sources:
        base.safe_file(relative, package)
        need(relative in available, 'Private/runtime source in new receipt: ' + relative)
    record['source_sha256'] = {path: sha(path) for path in sorted(sources)}
    need(len(old['build_sha256']) == 11, 'Historical build inventory differs')
    record['build_sha256'] = {path: sha(path) for path in old['build_sha256']}
    record['embedded_sources'] = ['04_研发源码/app/r4/' + name for name in package.build_inputs()]
    app = (ROOT / '03_当前APP/东方智慧-首页体验R4.html').read_text('utf-8')
    for name in package.build_inputs():
        need(package.embedded_text(name) in app, 'Actual APP build input missing: ' + name)
    review = (ROOT / '03_当前APP/发给负责人-东方智慧首页R4.html').read_text('utf-8')
    embedded, _ = json.JSONDecoder().raw_decode(review.split('const APP=', 1)[1])
    need(embedded.replace('__INITIAL__', '{}') == app, 'Owner preview contains another APP')
    record['unchanged_backend_sha256'] = copy.deepcopy(old['unchanged_backend_sha256'])
    for relative, value in record['unchanged_backend_sha256'].items():
        need(sha(relative) == value, 'Backend/API changed in CSS-only revision')
    for relative, value in old['vendored_fixed_sha256'].items():
        need(sha(relative) == value, 'Fixed engine/license changed')
    package.city_snapshot(record, checks)
    package.bazi_spacing_pages(record, checks, runs)
    w1 = tool('spacing_measure_helpers', '记录真实星盘档案交付.py')
    measured = w1.measured_summary(runs['layout'])
    record['layout_measurement'] = {'report': verification['layout']['report'], 'at': runs['layout']['at'], 'viewport': runs['layout'].get('viewport'), 'baseline': runs['layout'].get('baseline'), 'comparison': runs['layout'].get('beforeAfterMeasures') or runs['layout'].get('comparison'), 'summary': measured}
    record['captures_sha256'] = base.captures_from(all_runs, package)
    record['captures_sha256'].update(base.captures_from([before], package))
    package.bazi_spacing_baseline(record, checks, runs)
    record['limits'] = ['本轮仅CSS阅读布局改动，不改算法、术语、用户资料或固定引擎。', 'Pages只托管静态APP与游客本机交互，不托管账号、社交、后台、数据库或AI。', 'Pages状态以pages_preview为准，Sites/Netlify未更新；未发布时不把旧线上当当前APP。', '旧W1/F05及历轮收据和冻结报告按其原构建保留；旧隔离恢复不是当前UI的新恢复或生产恢复。', '原ZIP不覆盖、不重压、不嵌套；本记录器不生成ZIP、不部署。', '出生资料、档案和本机隔离边界不变，不代表完整跨设备同步。']
    for relative, value in record['historical_receipts_sha256'].items():
        need(sha(relative) == value, 'Historical receipt changed')
    return package, record, measured


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages-state', choices=['pending', 'published'], default='pending')
    parser.add_argument('--pages-smoke-report', default=PAGES_SMOKE)
    parser.add_argument('--pages-publication-report', default=PAGES_PUBLICATION)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    package, record, measured = prepare_delivery(args)
    if args.validate_only:
        print(json.dumps({'pass': True, 'read_only': True, 'module': MODULE, 'app_build_sha256': record['app_build_sha256'], 'pages_state': record['pages_preview']['status'], 'sources': len(record['source_sha256']), 'builds': len(record['build_sha256']), 'scope': 'No receipt/guide/manifest/ZIP/deployment writes.'}, ensure_ascii=False))
        return
    pages = '已发布并完成本轮公网验收' if record['pages_preview']['published'] else '待发布，现在线上仍为前一版'
    guide = '东方智慧APP · 八字表留白与字号优化\n\n' + record['scope'] + '\n\n仅调整真实八字表的留白、字号与阅读比例；完整数据、七列对照、三级流运、神煞依据、词典、保存复算、未知时间边界不变。\n\nPython和本地Cloud完整回归分别' + str(record['current_full']['local']['passed']) + '、' + str(record['current_full']['cloudflare']['passed']) + '项通过且均0失败；五专项分别' + '/'.join(str(record['verification'][name]['passed']) for name in package.UI_REPORTS) + '项，全部绑定本轮实际源码与构建。字号专项另有' + str(record['verification']['spacing']['passed']) + '项；改前JSON及两张基线图由spacing_baseline和captures_sha256保留来源。\n' + measured + '\n\nGitHub Pages静态APP预览' + pages + '：' + package.PAGES_URL + '\nSites/Netlify及账号后台未更新，AI继续暂缓。Pages local/public实际批次与四项产物身份见本轮记录，未发布状态不拿旧线上结果替代。\n\n旧W1、F05及历轮收据/冻结报告、18:36和其他历史ZIP保持原字节；旧恢复只作未改后端的历史证据。本记录器不执行打包或部署，不将旧W1回归冒充本轮结果。\n当前APP SHA-256：' + record['app_build_sha256'] + '\n实际记录：' + RECORD + '\n'
    # All gates above run before either output is written. Existing historical files are never rewritten.
    (ROOT / GUIDE).write_text(guide, encoding='utf-8')
    (ROOT / RECORD).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'pass': True, 'record': RECORD, 'guide': GUIDE, 'module': MODULE, 'app_build_sha256': record['app_build_sha256'], 'pages_state': record['pages_preview']['status'], 'source_count': len(record['source_sha256']), 'build_count': len(record['build_sha256']), 'zip_repacked': False, 'deployed_by_this_tool': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
