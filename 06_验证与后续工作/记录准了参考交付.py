"""Record C1/C2 only after final acceptance. Never build, test, publish or ZIP."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import copy
import csv
import html
import importlib.util
import io
import json
import math
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / '06_验证与后续工作'
OLD = '06_验证与后续工作/改动文档交付记录.json'
RECORD = '06_验证与后续工作/准了参考交付记录.json'
LEDGER = '06_验证与后续工作/准了参考实施记录.json'
GUIDE = '05_后台与研发说明/准了参考比例重做与验收说明.txt'
GALLERY = '06_验证与后续工作/原创命盘效果查看.html'
SOURCE_REVIEW = '02_需求与设计参考/准了参考排盘来源复核-20261111.json'
MODULE = '准了参考C2-八字比例重做'
SMOKES = {'reference_western_smoke': '准了参考星盘冒烟.json', 'reference_bazi_smoke': '准了参考八字冒烟.json'}
SCOPE = '11月11日用户两张准了参考图的星盘盘面与八字比例重做，按C1、C2分别冒烟及双端完整回归后本地完成。固定真实计算、本人资料与既有功能；旧M1—M5事实保留，其视觉由本轮反馈替代。未发布、未新打包，AI/托管/飞书继续暂缓。'

def load_tool(name, filename):
    spec = importlib.util.spec_from_file_location(name, Q / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def need(ok, text):
    if not ok:
        raise AssertionError(text)

def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))

def sha(relative):
    import hashlib
    with (ROOT / relative).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def latest(relative):
    document = read(relative)
    return document.get('latest', document)

def current_run(relative, minimum, app_hash, package, base):
    run = latest(relative)
    need(run.get('pass') is True and run.get('failed') == 0 and run.get('passed', 0) >= minimum and run.get('module') == MODULE, 'Final C2 run missing/failed: ' + relative)
    need(package.report_app(run) == app_hash and run.get('sourceHashes'), 'Final C2 build/source identity missing: ' + relative)
    for rel, value in run['sourceHashes'].items():
        base.safe_file(rel, package)
        need(sha(rel) == value, 'Current source changed: ' + rel)
    for folder, key in [('03_当前APP', 'buildHashes'), ('04_研发源码/app/cloud', 'cloudBuildHashes')]:
        for rel, value in run.get(key, {}).items():
            path = folder + '/' + rel
            base.safe_file(path, package)
            need(sha(path) == value, 'Current build changed: ' + path)
    return run, {'report': relative, 'sha256': sha(relative), 'at': run['at'], 'module': MODULE, 'passed': run['passed']}

def measured_summary(run):
    rows = run.get('measurements', [])
    comparisons = run.get('beforeAfterMeasures') or run.get('comparison') or []
    keys = [(row['id'], row.get('variant', 'default')) for row in rows]
    need(rows and len(keys) == len(set(keys)) and len(comparisons) == len(rows), 'Measured routes absent/duplicated')
    for item in comparisons:
        row = next((r for r in rows if r['id'] == item['id'] and r.get('variant', 'default') == item.get('variant', 'default')), None)
        need(row and item.get('afterScroll') == row['scrollDistance'] and item.get('afterScreens') == row['screens'], 'Current length row differs')
        need(row.get('documentOverflow') is False, 'Document overflow in measured route')
        for field in ['scrollDistance', 'scrollHeight', 'clientHeight']:
            value = row[field]
            need(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0, 'Invalid measured length')
        if item.get('baselineAvailable') is False:
            need(all(field in item and item[field] is None for field in ['beforeScroll', 'beforeScreens', 'reduction']), 'Unmeasured old layout invented')
    values = []
    for variant, label in [('default', '390×844'), ('desktop-958x676', '958×676')]:
        row = next((r for r in rows if r['id'] == 'classicsWisdom' and r.get('variant', 'default') == variant), None)
        need(row, 'Current Ba Zi viewport measurement absent: ' + variant)
        values.append(label + '额外滚动' + str(row['scrollDistance']) + 'px')
    return '本轮八字默认实测：' + '；'.join(values) + '。仅对应所测状态与视口，主动展开仍可滚动；缺历史同构测量不推算缩短比例。'

def prepare_delivery():
    base = load_tool('previous_document_recorder', '记录改动文档交付.py')
    package = base.packager_module()
    old = read(OLD)
    need(old.get('pass') is True and old.get('document_revision') is True, 'Immutable document receipt absent')
    app_hash = sha('03_当前APP/东方智慧-首页体验R4.html')
    full = {}
    for key, filename in [('local', '本轮全量回归结果.json'), ('cloudflare', '公网适配全量回归结果.json')]:
        rel = '06_验证与后续工作/' + filename
        run = latest(rel)
        need(run.get('pass') is True and run.get('failed') == 0 and run.get('passed', 0) >= 60 and run.get('module') == MODULE and package.report_app(run) == app_hash, 'Final C2 full missing: ' + key)
        need(run.get('buildHashes') and (key != 'cloudflare' or run.get('cloudBuildHashes')), 'Final full build identity absent')
        for folder, field in [('03_当前APP', 'buildHashes'), ('04_研发源码/app/cloud', 'cloudBuildHashes')]:
            for path, value in run.get(field, {}).items():
                base.safe_file(folder + '/' + path, package)
                need(sha(folder + '/' + path) == value, 'Final full build changed: ' + path)
        full[key] = {'report': rel, 'sha256': sha(rel), 'at': run['at'], 'module': MODULE, 'passed': run['passed']}
    runs, verification = {}, {}
    for key, (filename, minimum) in base.SPECIALTIES.items():
        runs[key], verification[key] = current_run('06_验证与后续工作/' + filename, minimum, app_hash, package, base)
    for key, filename in SMOKES.items():
        runs[key], verification[key] = current_run('06_验证与后续工作/' + filename, 1, app_hash, package, base)
        need(runs[key].get('productionWrites') is False, 'Final reference smoke must be isolated')
    ledger = read(LEDGER)
    record = copy.deepcopy(old)
    record.update({
        'checked_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'pass': True, 'scope': SCOPE, 'ui_revision': True, 'document_revision': False,
        'reference_revision': True, 'revision_module': MODULE, 'guide': GUIDE, 'preview_html': GALLERY,
        'app_build_sha256': app_hash, 'local_scope_complete': True, 'reference_local_scope_complete': True,
        'all_planned_work_complete': False, 'paused_by_user': False, 'current_full': full,
        'verification': verification, 'complete_reference_modules': ['C1', 'C2'],
        'reference_module_ledger': {'report': LEDGER, 'sha256': sha(LEDGER), 'modules': copy.deepcopy(ledger['modules'])},
        'previous_document_revision': {'report': OLD, 'sha256': sha(OLD), 'app_build_sha256': old['app_build_sha256'], 'scope': 'Immutable historical M1–M5 receipt and ledger; prior visual layout superseded by the November 11 request.'},
        'zip_repacked': False, 'production_writes': False, 'deployment_attempted_this_revision': False,
        'current_source_published': False, 'visual_approved_by_user': False,
        'source_review': {'report': SOURCE_REVIEW, 'sha256': sha(SOURCE_REVIEW)},
    })
    checks, historical = {}, {}
    package.historical_foundation(record, checks, historical)
    package.reference_modules(record, checks)
    measured = measured_summary(runs['layout'])
    record['layout_measurement'] = {'report': verification['layout']['report'], 'at': runs['layout']['at'], 'viewport': runs['layout']['viewport'], 'baseline': runs['layout'].get('baseline'), 'comparison': runs['layout'].get('beforeAfterMeasures') or runs['layout'].get('comparison'), 'compactTargets': runs['layout'].get('compactTargets'), 'summary': measured}
    available = package.collect_files()
    sources = set(old['source_sha256'])
    for rel in available:
        pure = Path(rel)
        if rel.startswith('04_研发源码/app/r4/'):
            tail = pure.parts[3:]
            if len(tail) == 1 or tail and tail[0] in {'backend', 'vendor'}:
                sources.add(rel)
        elif rel.startswith('04_研发源码/app/cloud/') and '/generated/' not in rel and pure.suffix.lower() in {'.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.css', '.html', '.json', '.toml', '.sql', '.txt', '.md'}:
            sources.add(rel)
    for run in runs.values():
        sources.update(run['sourceHashes'])
    sources.update([SOURCE_REVIEW, '06_验证与后续工作/记录准了参考交付.py', '06_验证与后续工作/记录准了参考任务.py', '06_验证与后续工作/打包当前交付.py'])
    for name, value in base.FIXED_VENDOR.items():
        rel = '04_研发源码/app/r4/vendor/' + name
        need(sha(rel) == value, 'Fixed engine/license changed: ' + name)
        sources.add(rel)
    for rel in sources:
        base.safe_file(rel, package)
        need(rel in available, 'Runtime/private file in source identity: ' + rel)
    record['source_sha256'] = {rel: sha(rel) for rel in sorted(sources)}
    record['vendored_fixed_sha256'] = {'04_研发源码/app/r4/vendor/' + name: value for name, value in base.FIXED_VENDOR.items()}
    inputs = package.build_inputs()
    record['embedded_sources'] = ['04_研发源码/app/r4/' + name for name in inputs]
    app = (ROOT / '03_当前APP/东方智慧-首页体验R4.html').read_text(encoding='utf-8')
    for name in inputs:
        need(package.embedded_text(name) in app, 'APP input missing: ' + name)
    need(len(old['build_sha256']) == 11, 'Previous build inventory changed')
    record['build_sha256'] = {rel: sha(rel) for rel in old['build_sha256']}
    need((ROOT / '03_当前APP/创作者中心.html').read_bytes() == (ROOT / '04_研发源码/app/r4/creator-center.html').read_bytes(), 'Creator standalone mismatch')
    review = (ROOT / '03_当前APP/发给负责人-东方智慧首页R4.html').read_text(encoding='utf-8')
    embedded, _ = json.JSONDecoder().raw_decode(review.split('const APP=', 1)[1])
    need(embedded.replace('__INITIAL__', '{}') == app, 'Review embeds another APP')
    protected = [rel for rel in old['source_sha256'] if '/backend/' in rel or '/cloud/lib/' in rel or '/cloud/worker/' in rel]
    need(all(sha(rel) == old['source_sha256'][rel] for rel in protected), 'Backend/API changed; original restore cannot be reused')
    record['unchanged_backend_sha256'] = {rel: sha(rel) for rel in protected}
    prior_zip = read('06_验证与后续工作/最新打包校验结果.json')
    zip_name = Path(prior_zip['project_archive']).name
    need(zip_name == old['previous_zip']['path'] and sha(zip_name) == prior_zip['sha256'] == old['previous_zip']['sha256'], 'Old delivered ZIP differs')
    record['previous_zip'] = copy.deepcopy(old['previous_zip'])
    record['publication'].update({'current_source_published': False, 'current_chart_ui_published': False, 'public_deployment_pending': True, 'package_matches_public': False, 'all_public_entry_points_current': False, 'scope': '本轮C1/C2只本地完成。Sites v15/Netlify v14没有本轮改动；托管、飞书、AI暂缓，不发布/重试/监测/购买。'})
    record['captures_sha256'] = base.captures_from(list(runs.values()), package)
    record['previous_revisions'] = [*copy.deepcopy(old.get('previous_revisions', [])), {key: copy.deepcopy(old[key]) for key in ['checked_beijing', 'scope', 'revision_module', 'app_build_sha256', 'source_sha256', 'build_sha256', 'current_full', 'verification', 'layout_measurement', 'previous_zip']}]
    record['limits'] = ['视觉测试通过不代表用户已认可；旧M1—M5视觉被本次参考反馈替代，其真实计算和验收事实保留。', '未知西盘为逐小时25样本全天范围，不宣称连续极值或精确出生位置。', '紫微/八字未知时刻不造精确盘，无坐标不猜ASC/宫位；四字段生辰不改。', '十二类神煞按本APP明确锚点查表，不冒称lunar原生完整神煞API。', 'AI/托管/飞书继续暂缓，未发布/未新打包；旧receipt/ledger/ZIP原样保留。', '旧F05为未改后端历史隔离恢复证据，不等同当前UI新恢复、生产恢复、跨设备同步或原生实机验收。', '藏文首页存在真实额外滚动，仍待母语审校。']
    counts = 'Python与本地Cloud完整回归分别' + str(full['local']['passed']) + '、' + str(full['cloudflare']['passed']) + '项通过且均0失败；出生/三盘/交互/长度/八字专项分别' + '/'.join(str(verification[key]['passed']) for key in base.SPECIALTIES) + '项，星盘/八字冒烟分别' + '/'.join(str(verification[key]['passed']) for key in SMOKES) + '项。全部绑定本轮最终构建。'
    return base, package, record, counts, measured

def planned_outputs(base, package, record, counts, measured):
    esc = lambda value: html.escape(str(value), quote=True)
    guide = '东方智慧APP · 11月11日准了参考比例重做与验收说明\n\n' + SCOPE + '\n\nC1：星盘盘面比例、刻度、真实天体与标签层级按本轮用户参考重做。准确时刻无坐标仍是地心模式；旧完整档案仍按原资料复算；未知时间保持真实全天范围，不绘制假宫位或ASC。\nC2：八字六列表与流运比例按本轮用户参考重做。本人保存生辰、固定lunar1.7.7四柱及运年月、档案/流运/神煞三页、十二类明确锚点规则与来源、完整七列详情/词典/小运、笔记/保存/导出/复算保留。\n\n八字来源是lunar-javascript1.7.7，西盘来源是Astronomy Engine2.1.19，两者不能混用。来源复核见' + SOURCE_REVIEW + '。\n必须先本人实际保存生日/性别；称呼与时间选填，不恢复地域控件。紫微/八字未知时间不造精确盘；西盘未知时刻只显示按保存日期固定北京时间的25样本全天范围，不给出单一出生位置、确定相位、ASC或宫位。\n保留三地图4/4/3、逐级返回、计时、四语、创作者、数据中心。个人生辰/排盘/笔记仍按本浏览器账号保存，不代表完整跨设备云同步。藏文首页允许真实滚动，藏文仍待母语审校。\n旧改动文档M1—M5记录、台账和交付ZIP原样保留；旧视觉由本轮最新反馈替代，不删除或改写历史验收事实。F01—F05与隔离SQLite/本地D1恢复仍是历史证据，仅核后端/API未改，不称生产恢复或当前UI新恢复。\n本轮只本地完成，视觉仍待用户评价。AI、托管、飞书继续暂缓；Sites v15/Netlify v14不含本轮UI，不发布、不监测、不购买，也未生成或覆盖完整ZIP。8880/8879用户预览继续保留。\n\n实际验收：\n' + counts + '\n' + measured + '\nAPP SHA-256：' + record['app_build_sha256'] + '\n交付记录：' + RECORD + '\n两模块台账：' + LEDGER + '\n'
    links = '<p><a href="' + GUIDE + '">本轮说明</a> · <a href="' + RECORD + '">最终证据</a> · <a href="' + LEDGER + '">C1/C2台账</a> · <a href="' + GALLERY + '">当前效果</a> · <a href="03_当前APP/发给负责人-东方智慧首页R4.html">离线APP</a></p>'
    section = '<section id="reference-chart-delivery"><h2>11月11日 · 星盘与八字参考比例重做</h2><p>' + esc(SCOPE) + '</p><p>' + esc(counts) + '</p><p>' + esc(measured) + '</p><p>下方旧轮验收与视觉作为历史；当前效果以上方本轮记录为准。未知不造精确盘、AI/托管/飞书暂停、未发布/未新打包。</p>' + links + '</section>'
    outputs = {GUIDE: guide, RECORD: json.dumps(record, ensure_ascii=False, indent=2) + '\n'}
    for relative in ['打开这里.html', '改动任务表-2026-10-22.html']:
        text = (ROOT / relative).read_text(encoding='utf-8')
        text = re.sub(r'<!-- reference-chart-delivery:start -->[\s\S]*?<!-- reference-chart-delivery:end -->\s*', '', text)
        block = '<!-- reference-chart-delivery:start -->' + section + '<!-- reference-chart-delivery:end -->'
        text, count = re.subn(r'(<main\b[^>]*>)', lambda match: match.group(1) + '\n' + block, text, count=1)
        need(count == 1, 'Entry main missing')
        outputs[relative] = text
    notice = record['checked_beijing'] + '\n' + SCOPE + '\n' + counts + '\n' + measured + '\n说明：' + GUIDE + '\n证据：' + RECORD + '；台账：' + LEDGER + '\n旧轮界面及旧包为历史快照，未发布、未新打包。\n'
    for relative in ['先读我.txt', '交付包说明.txt']:
        text = (ROOT / relative).read_text(encoding='utf-8')
        text = re.sub(r'【准了参考本地验收】[\s\S]*?【准了参考本地验收结束】\s*', '', text)
        outputs[relative] = '【准了参考本地验收】\n' + notice + '【准了参考本地验收结束】\n\n此前记录保留历史，当前比例以本轮为准。\n' + text
    gallery = '<!doctype html><html lang="zh-Hans"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>星盘与八字 · 当前参考比例</title><style>body{margin:0;background:#f7f5ef;color:#25323b;font:15px/1.8 sans-serif}main{max-width:1050px;margin:auto;padding:24px}a{color:#866019}figure{margin:24px 0}img{display:block;width:100%;max-width:430px;height:auto;border:1px solid #aaa}figcaption{overflow-wrap:anywhere}</style><main><h1>11月11日星盘与八字 · 本地效果</h1><p>' + esc(SCOPE) + '</p><p>' + esc(counts) + '</p><p>' + esc(measured) + '</p><p>合成夹具截图仅用于验收，不是业务默认或用户档案。视觉仍待用户评价。</p><p><a href="../' + GUIDE + '">说明</a> · <a href="准了参考交付记录.json">证据</a></p>'
    for relative in record['captures_sha256']:
        name = Path(relative).relative_to('06_验证与后续工作').as_posix()
        gallery += '<figure><figcaption>' + esc(Path(name).stem) + '</figcaption><a href="' + esc(name) + '"><img loading="lazy" src="' + esc(name) + '" alt="' + esc(Path(name).stem) + '"></a></figure>'
    outputs[GALLERY] = gallery + '</main></html>'
    agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8-sig')
    agents = re.sub(r'<!-- reference-charts-final-verified:start -->[\s\S]*?<!-- reference-charts-final-verified:end -->\s*', '', agents)
    outputs['AGENTS.md'] = agents + '\n\n<!-- reference-charts-final-verified:start -->\n### ' + record['checked_beijing'][:10] + ' 准了参考C1/C2本地验收\n' + SCOPE + '\n' + counts + '\n旧M1—M5原记录保留；未知西盘为25样本全天范围，紫微/八字未知不造精确盘。来源：' + SOURCE_REVIEW + '；当前证据：' + RECORD + '；说明：' + GUIDE + '。未发布、未新打包，视觉待用户评价。\n<!-- reference-charts-final-verified:end -->\n'
    base.validate_output_links(outputs, package)
    return outputs

def refresh_manifests(package, record):
    files = [{'path': rel, 'bytes': path.stat().st_size, 'sha256': sha(rel)} for rel, path in sorted(package.collect_files().items()) if rel not in package.SELF]
    inventory = read('原始来源与文件校验.json')
    inventory['files'] = files
    inventory['current_revision'] = {'updated_beijing': record['checked_beijing'], 'scope': SCOPE, 'delivery_record': RECORD, 'app_build_sha256': record['app_build_sha256'], 'local_scope_complete': True, 'public_deployment_pending': True, 'zip_repacked': False, 'reference_module_ledger': LEDGER}
    inventory['delivery_filter'] = {'manifest_scope': 'Current authored project except self manifests; no ZIP generated', 'private_runtime_excluded': True, 'historical_zips_excluded': True, 'no_wrapper': True, 'zip_repacked': False}
    (ROOT / '原始来源与文件校验.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['包内相对位置', '字节数', 'SHA-256'])
    writer.writerows((row['path'], row['bytes'], row['sha256']) for row in files)
    (ROOT / '资料校验清单.csv').write_text(out.getvalue(), encoding='utf-8-sig', newline='')
    for row in files:
        need((ROOT / row['path']).stat().st_size == row['bytes'] and sha(row['path']) == row['sha256'], 'Workspace changed during manifest refresh')
    return len(files)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    base, package, record, counts, measured = prepare_delivery()
    outputs = planned_outputs(base, package, record, counts, measured)
    if '--validate-only' in sys.argv:
        print(json.dumps({'pass': True, 'read_only': True, 'module': MODULE, 'app_build_sha256': record['app_build_sha256'], 'source_count': len(record['source_sha256']), 'build_count': len(record['build_sha256']), 'scope': 'No receipt/guide/entry/manifest/PREFLIGHT/ZIP/publication writes.'}, ensure_ascii=False))
        return
    for relative, text in outputs.items():
        (ROOT / relative).write_text(text, encoding='utf-8')
    count = refresh_manifests(package, record)
    need(sha(OLD) == record['previous_document_revision']['sha256'] and sha(record['document_module_ledger']['report']) == record['document_module_ledger']['sha256'] and sha(record['previous_zip']['path']) == record['previous_zip']['sha256'], 'Historical receipt/ledger/ZIP changed')
    print(json.dumps({'pass': True, 'record': RECORD, 'module': MODULE, 'app_build_sha256': record['app_build_sha256'], 'sources': len(record['source_sha256']), 'builds': len(record['build_sha256']), 'manifest_files': count, 'deployed': False, 'zip_repacked': False}, ensure_ascii=False))

if __name__ == '__main__':
    main()
