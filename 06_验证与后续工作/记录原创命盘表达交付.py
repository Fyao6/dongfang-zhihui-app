"""Bind the local chart revision to actual current tests; never publishes or packages."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import importlib.util
import io
import json
import math
import re
import html as H

ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / '06_验证与后续工作'
BASELINE = '06_验证与后续工作/基础框架本地验收及发布待续记录.json'
RECORD = '06_验证与后续工作/原创命盘表达交付记录.json'
GUIDE = '05_后台与研发说明/原创命盘表达与验收说明.txt'
GALLERY = '06_验证与后续工作/原创命盘效果查看.html'
UI_MODULE = '八字紧凑同屏优化'
LENGTH_BASELINE = {
    'at': '2026-11-09T10:32:54.233Z',
    'module': '八字参考排版重做',
    'buildSha256': '44a328b1238a7dd652d87d7a95989deae5bd9312b12203227b5a838bbf4707eb',
    'report': '06_验证与后续工作/页面长度与日间命盘优化核验.json'
}

def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))

def sha(relative):
    with (ROOT / relative).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def need(ok, message):
    if not ok:
        raise AssertionError(message)

def write(relative, data):
    (ROOT / relative).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def latest(relative):
    data = read(relative)
    return data.get('latest', data)

def block(file, key, content, prepend=False):
    p = ROOT / file
    body = p.read_text(encoding='utf-8-sig')
    marker = '<!-- ' + key
    pattern = r'<!-- ' + re.escape(key) + r':start -->[\s\S]*?<!-- ' + re.escape(key) + r':end -->\s*'
    body = re.sub(pattern, '', body)
    result = '<!-- ' + key + ':start -->\n' + content + '\n<!-- ' + key + ':end -->\n'
    if prepend:
        body = result + '\n' + body
    elif re.search(r'<main\b[^>]*>', body):
        body = re.sub(r'(<main\b[^>]*>)', lambda m: m[1] + '\n' + result, body, count=1)
    else:
        body = body.rstrip() + '\n\n' + result
    p.write_text(body, encoding='utf-8')

def main():
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    baseline = read(BASELINE)
    app_hash = sha('03_当前APP/东方智慧-首页体验R4.html')
    full = {}
    for key, name in [('local', '本轮全量回归结果.json'), ('cloudflare', '公网适配全量回归结果.json')]:
        path = '06_验证与后续工作/' + name
        run = latest(path)
        need(run['pass'] and run['failed'] == 0 and run['passed'] >= 60 and run['module'] == UI_MODULE, 'Current full regression missing: ' + name)
        for rel, expected in run['buildHashes'].items():
            need(sha('03_当前APP/' + rel) == expected, 'Full APP mismatch: ' + rel)
        for rel, expected in run.get('cloudBuildHashes', {}).items():
            need(sha('04_研发源码/app/cloud/' + rel) == expected, 'Full Cloud mismatch: ' + rel)
        full[key] = {'report': path, 'at': run['at'], 'module': run['module'], 'passed': run['passed'], 'sha256': sha(path)}
    verification = {}
    specialty_runs = {}
    for key, name, count in [('birth', '出生资料地域移除核验-本机.json', 8), ('charts', '三盘实际排盘联调.json', 14), ('expression', '原创命盘交互核验.json', 15), ('layout', '页面长度与日间命盘优化核验.json', 16), ('bazi_reference', '八字参考排版核验.json', 12)]:
        path = '06_验证与后续工作/' + name
        run = latest(path)
        bound_hash = run.get('buildSha256') or run.get('appBuildSha256') or run.get('buildHashes', {}).get('东方智慧-首页体验R4.html')
        need(run['pass'] and run['failed'] == 0 and run['passed'] >= count and bound_hash == app_hash, 'Current chart specialty missing: ' + name)
        for rel, expected in run.get('sourceHashes', {}).items():
            need(sha(rel) == expected, 'Specialty source mismatch: ' + rel)
        verification[key] = {'report': path, 'at': run['at'], 'passed': run['passed'], 'sha256': sha(path)}
        if run.get('module'):
            verification[key]['module'] = run['module']
        specialty_runs[key] = run
    layout_run = specialty_runs['layout']
    need(layout_run.get('module') == UI_MODULE and layout_run.get('baseline'), 'Current length measurement/baseline provenance missing')
    need(all(layout_run['baseline'].get(key) == value for key, value in LENGTH_BASELINE.items()), 'Compact measurement must use the accepted 44a328 reference-layout baseline')
    layout_document = read(LENGTH_BASELINE['report'])
    prior_runs = [layout_document.get('latest'), *layout_document.get('runs', []), layout_document.get('after'), layout_document.get('before')]
    prior_layout = next((run for run in prior_runs if run and all(run.get(key) == LENGTH_BASELINE[key] for key in ['at', 'module', 'buildSha256'])), None)
    need(prior_layout and prior_layout.get('pass') is True and prior_layout.get('failed') == 0, 'Accepted reference-layout measurements are missing from history')
    need(layout_run.get('viewport') == prior_layout.get('viewport'), 'Length comparison viewport differs from accepted reference-layout baseline')
    measures = layout_run.get('beforeAfterMeasures') or layout_run.get('comparison') or []
    prior_keys = {(entry['id'], entry.get('variant', 'default')) for entry in prior_layout['measurements']}
    comparison_keys = [(entry['id'], entry.get('variant', 'default')) for entry in measures]
    need(len(comparison_keys) == len(set(comparison_keys)) and prior_keys <= set(comparison_keys), 'Historical length comparison rows are missing or duplicated')
    for item in measures:
        prior = next((entry for entry in prior_layout['measurements'] if entry.get('id') == item.get('id') and entry.get('variant', 'default') == item.get('variant', 'default')), None)
        current = [entry for entry in layout_run['measurements'] if entry.get('id') == item.get('id') and entry.get('variant', 'default') == item.get('variant', 'default')]
        need(len(current) == 1 and item.get('afterScroll') == current[0].get('scrollDistance') and item.get('afterScreens') == current[0].get('screens'), 'Length comparison differs from actual current measurements: ' + str(item.get('id')))
        need(all(isinstance(item.get(key), (int, float)) and not isinstance(item.get(key), bool) and math.isfinite(item[key]) and item[key] >= 0 for key in ['afterScroll', 'afterScreens']), 'Invalid current length measurement: ' + str(item.get('id')))
        if prior:
            need(item.get('beforeScroll') == prior.get('scrollDistance') and item.get('beforeScreens') == prior.get('screens') and item.get('baselineAvailable') is not False, 'Length comparison does not use actual accepted baseline measurements: ' + str(item.get('id')))
        else:
            need((item.get('id'), item.get('variant')) == ('classicsWisdom', 'desktop-958x676') and item.get('baselineAvailable') is False and all(key in item and item[key] is None for key in ['beforeScroll', 'beforeScreens', 'reduction']), 'New desktop measurement must explicitly have no historical baseline')
    labels = {('ziweiChart', 'default'): '紫微默认页', ('classicsWisdom', 'default'): '八字默认页', ('academy', 'default'): '智慧馆默认页', ('westernAstrology', 'legacy-complete'): '完整旧星盘默认页'}
    length_notes = []
    for item in measures:
        label = labels.get((item.get('id'), item.get('variant', 'default')))
        if not label:
            continue
        before, after = item.get('beforeScroll'), item.get('afterScroll')
        need(all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) and n >= 0 for n in [before, after]), 'Invalid measured scroll distance: ' + label)
        delta = after - before
        change = '未变' if delta == 0 else ('增加' if delta > 0 else '减少') + (f'{abs(delta) / before * 100:.1f}%' if before else f'{abs(delta):g}px')
        length_notes.append(f'{label}{before:g}→{after:g}px（{change}）')
    need(len(length_notes) == len(labels), 'Current length comparison is incomplete')
    viewport = layout_run['viewport']
    length_summary = f"{viewport['width']}×{viewport['height']}同一合成夹具，额外滚动实测：" + '；'.join(length_notes) + '。仅对应所测视口与默认状态，主动展开仍可滚动。'
    counts = f"双端完整{full['local']['passed']}/0与{full['cloudflare']['passed']}/0，" + '、'.join(label + str(verification[key]['passed']) + '/0' for key, label in [('birth', '出生'), ('charts', '三盘'), ('expression', '原创交互'), ('layout', '页面测量'), ('bazi_reference', '八字紧凑交互')])
    chart_sources = ['life-chart-core.js', 'life-chart-ziwei.js', 'life-chart-bazi.js', 'life-chart-bazi-layout.js', 'life-chart-bazi-annotations.js', 'life-chart-western.js', 'life-birth-entry.js', 'life-charts.css', 'life-chart-workspace.css', 'life-chart-bazi.css', 'life-chart-western.css', 'app-density.css', 'academy.js', 'academy-teachers.js']
    app = (ROOT / '03_当前APP/东方智慧-首页体验R4.html').read_text(encoding='utf-8')
    for name in chart_sources:
        need((ROOT / '04_研发源码/app/r4' / name).read_text(encoding='utf-8') in app, 'Missing embedded chart source: ' + name)
    previous = read(RECORD) if (ROOT / RECORD).is_file() else None
    source_paths = sorted(set(baseline['source_sha256']) | set(previous.get('source_sha256', {}) if previous else {}) | {'04_研发源码/app/r4/' + n for n in chart_sources})
    record = json.loads(json.dumps(baseline))
    record.update({
        'checked_beijing': stamp, 'pass': True, 'ui_revision': True,
        'scope': '八字紧凑同屏优化本地验收：六列默认十神/干支，藏干等详细字段通过按钮展开；档案/流运/神煞/关系四页与三级时间尺保留，保存/导出/笔记/参数及完整节令月详情通过真实更多工具弹层进入，关系紧凑呈现；计算、六类神煞规则及出生门禁不变；未发布、未更新旧ZIP',
        'revision_module': UI_MODULE,
        'app_build_sha256': app_hash,
        'source_sha256': {p: sha(p) for p in source_paths},
        'build_sha256': {p: sha(p) for p in baseline['build_sha256']},
        'foundation_baseline': {'report': BASELINE, 'sha256': sha(BASELINE), 'scope': '此前F01—F05及隔离恢复验收；本轮未修改后端/API/schema，不把旧恢复结果称为新UI恢复验收'},
        'current_full': full, 'verification': verification, 'guide': GUIDE,
        'layout_measurement': {'report': verification['layout']['report'], 'at': layout_run['at'], 'viewport': viewport, 'baseline': layout_run['baseline'], 'comparison': measures, 'summary': length_summary},
        'preview_html': GALLERY, 'visual_approved_by_user': False,
        'zip_repacked': False, 'production_writes': False, 'deployment_attempted_this_revision': False
    })
    history = list(previous.get('previous_revisions', [])) if previous else []
    if previous and (previous.get('app_build_sha256') != app_hash or previous.get('revision_module') != UI_MODULE):
        history.append({k: previous.get(k) for k in ['checked_beijing', 'scope', 'revision_module', 'app_build_sha256', 'source_sha256', 'build_sha256', 'current_full', 'verification', 'layout_measurement', 'previous_zip', 'zip_repacked', 'foundation_baseline', 'publication']})
    record['previous_revisions'] = history
    record['publication'].update({
        'current_source_published': False, 'current_chart_ui_published': False,
        'public_deployment_pending': True, 'package_matches_public': False,
        'all_public_entry_points_current': False,
        'scope': '本轮八字紧凑同屏优化仅本地源码/构建。此前Sites v15与Netlify v14保持，当前命盘未发布到任一公网入口。继续等待用户决定恢复额度，不重试、不监测、不购买。'
    })
    protected = [p for p in baseline['source_sha256'] if '/backend/' in p or '/cloud/lib/' in p or '/cloud/worker/' in p]
    need(all(sha(p) == baseline['source_sha256'][p] for p in protected), 'Backend changed; historical baseline cannot be reused')
    record['unchanged_backend_sha256'] = {p: sha(p) for p in protected}
    old_zip = '东方智慧APP完整概念方向包-2026-11-10-14时55分57秒.zip'
    expected_zip = '5a358050c8b29041b27a24212d2dfe2bcb2de806447b9eab24f1f25d6592f51b'
    need(sha(old_zip) == expected_zip, 'Earlier delivered ZIP unexpectedly changed')
    record['previous_zip'] = {'path': old_zip, 'sha256': expected_zip, 'unchanged': True}
    # Screenshot names come from the passing current-build report, never an old gallery.
    capture_files = [entry.get('file') if isinstance(entry, dict) else entry for entry in specialty_runs['bazi_reference'].get('captures', [])]
    gallery = '''<!doctype html><html lang="zh-Hans"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>东方智慧 · 八字紧凑同屏优化</title><style>body{margin:0;background:#101e27;color:#efe9dc;font:15px/1.8 "Microsoft YaHei",sans-serif}main{max-width:940px;padding:36px 22px;margin:auto}h1{font-size:28px;font-weight:500}p{color:#c0c8cc}a{color:#e7be7c}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;margin-top:30px}figure{margin:0}figcaption{margin-bottom:12px}img{display:block;width:100%;height:auto;border:1px solid #34444e;border-radius:8px}small{display:block;color:#b2bec5;margin-top:10px}@media(max-width:700px){.grid{grid-template-columns:1fr}figure{max-width:390px;margin:auto}}</style><main><h1>东方智慧 · 八字紧凑同屏优化</h1>'''
    gallery += '<p>六列默认十神/干支，详细字段按需展开；档案、流运、神煞、关系四页与三级时间尺保留，保存/导出/笔记/参数在工具弹层中实际可达。' + H.escape(counts) + '通过；视觉仍待评价。本轮未发布公网，11月10日14:55交付ZIP保持原快照。</p><p>' + H.escape(length_summary) + '</p>'
    gallery += '<p><a href="http://127.0.0.1:8880/experience?lang=zh-Hans&amp;page=lifeResult">打开本机互动APP（本地服务需保持运行）</a> · <a href="../' + GUIDE + '">实现与使用说明</a></p><div class="grid">'
    for role, aliases, title, note in [
        ('board', ['board', '上表与流运'], '01 主表 · 四柱与所选运年', '年、月、日、时、大运、流年六列默认显示十神和干支；藏干、纳音、星运、空亡通过详情按钮展开，可选显示流月列。'),
        ('flow', ['flow', '流运'], '02 流运 · 三级选择', '三级时间尺压缩间距，仍可真实选择大运、流年及节令月；干支、藏干十神及节气日期来自现有实际计算。'),
        ('archive', ['archive', '档案'], '03 档案 · 出生资料与完整数据', '完整四柱、辅助资料、小运与规则继续可打开；保存、导出、笔记、排盘参数及完整节令月详情通过真实更多工具弹层进入。'),
        ('stars', ['stars', '神煞'], '04 神煞 · 六类固定标记与自坐', '只收录禄神、驿马、将星、华盖、劫煞、亡神；逐条列明本命日干或年支依据，自坐与日主长生分别说明。'),
        ('relations', ['relations', '关系'], '05 关系 · 实际柱间组合', '紧凑列出五合、六合、六冲及三支齐全的三合；不据此判断合化成立或人生吉凶，完整七列对照仍可展开。')]:
        candidates = [prefix + alias + '.png' for prefix in ['八字紧凑同屏-390-', '八字参考排版-390-'] for alias in aliases]
        image_name = next((name for name in candidates if name in capture_files), None)
        need(image_name and Path(image_name).name == image_name and (Q / image_name).is_file(), 'Missing current screenshot for view: ' + role)
        gallery += '<figure><figcaption>' + H.escape(title) + '</figcaption><a href="' + image_name + '"><img src="' + image_name + '" alt="' + H.escape(title) + '"></a><small>' + H.escape(note) + '</small></figure>'
    gallery += '</div><p>图中为合成示例，不使用用户提供截图中的出生资料。实际截图与本轮批次绑定；测量只代表报告记录的视口与展开状态。出生四字段、未知时间不造盘及原计时功能继续保留。</p></main></html>'
    write(RECORD, record)
    (ROOT / GALLERY).write_text(gallery, encoding='utf-8')
    summary_html = '<p>' + H.escape(counts) + '通过；本轮记录与实际构建绑定。' + H.escape(length_summary) + '</p>'
    scope_html = '<p>本轮八字默认显示六列十神/干支，详细字段通过按钮展开；四页签及三级时间尺保留，保存/导出/笔记/参数及完整节令月详情移入真实更多工具弹层，关系紧凑呈现。默认主干数据与全部真实计算、术语、规则和保存复算均保留。神煞仍为六类固定锚点查表；关系只列组合，不推断吉凶。未知时间不造盘，AI继续暂缓。</p>'
    links_html = '<p><a href="' + GALLERY + '">查看本轮八字四页效果</a> · <a href="' + GUIDE + '">使用说明</a> · <a href="' + RECORD + '">本轮证据</a></p>'
    block('改动任务表-2026-10-22.html', 'original-chart-expression', '<section id="original-chart-expression"><h2>当前新增：' + H.escape(UI_MODULE) + '（' + stamp[:10] + '）</h2>' + scope_html + summary_html + '<p>本轮未发布；Sites v15、Netlify v14及等待免费额度的安排保持。前序基础框架与原命盘UI结果保留历史，11月10日14:55交付ZIP保持原快照。</p>' + links_html + '</section>')
    block('打开这里.html', 'original-chart-expression', '<section><h2>当前本地新增：' + H.escape(UI_MODULE) + '</h2>' + scope_html + summary_html + '<p>本轮未发布、未更新旧ZIP；当前状态以本轮构建及交付记录为准。</p>' + links_html + '</section>')
    notice = stamp + '\n当前最新本地模块：' + UI_MODULE + '。六列主表详情按需展开，四页签与三级时间尺保留，工具弹层可实际进入。' + counts + '通过。' + length_summary + '\n当前源码/构建见' + RECORD + '，说明见' + GUIDE + '。基础框架与前轮UI证据保留历史；旧F05恢复仅证明当时隔离恢复及未改后端。Sites v15与Netlify v14均未含本轮优化，继续等待免费额度；11月10日14:55交付ZIP保持原快照。\n'
    for file in ['先读我.txt', '交付包说明.txt', '05_后台与研发说明/基础框架阶段说明与验收.txt']:
        block(file, 'original-chart-expression', notice, prepend=True)
    block(GUIDE, 'bazi-reference-verified', '本轮实际验收记录 · ' + UI_MODULE + '\n' + stamp + '\n' + counts + '通过；当前源码和构建已绑定本轮报告。\n' + length_summary + '\n本轮仅本地验收，视觉仍待用户评价；未发布、未更新11月10日14:55交付ZIP。上轮43份源码/11份构建及其双端完整和专项结果保留历史，不代替本轮验收；旧基础框架恢复证据保留，详见' + RECORD + '。\n', prepend=True)
    block('AGENTS.md', 'original-chart-expression-verified', '### ' + stamp[:10] + ' ' + UI_MODULE + '本地验收完成\n' + counts + '通过，实际批次/源码/构建绑定见' + RECORD + '。' + length_summary + '\n六列主表默认十神/干支、详细字段实际展开；四页签与三级时间尺保留，保存/导出/笔记/参数通过工具弹层进入。六类神煞规则与计算不改。出生四字段、未知时间不造盘、AI暂缓继续。前序43份源码/11份构建及双端验收保留历史；基础框架记录与恢复证据保留原hash，本轮后端/API/schema未改，不能把旧恢复当当前UI的新恢复验收。当前本地源码与Sites v15/Netlify v14均不同，未发布、未更新11月10日14:55交付ZIP；用户视觉认可仍待确认。')
    spec = importlib.util.spec_from_file_location('delivery_inventory', Q / '打包当前交付.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    files = [{'path': rel, 'bytes': p.stat().st_size, 'sha256': sha(rel)} for rel, p in sorted(module.collect_files().items()) if rel not in module.SELF]
    manifest = read('原始来源与文件校验.json')
    manifest['files'] = files
    manifest['current_revision'] = {'updated_beijing': stamp, 'scope': record['scope'], 'delivery_record': RECORD, 'public_deployment_pending': True, 'app_build_sha256': app_hash, 'zip_repacked': False}
    manifest['delivery_filter'] = {'manifest_scope': 'Current authored workspace except two self manifests; earlier ZIP unchanged', 'zip_repacked': False, 'private_runtime_excluded': True, 'historical_zips_excluded': True, 'no_wrapper': True}
    write('原始来源与文件校验.json', manifest)
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['包内相对位置', '字节数', 'SHA-256'])
    writer.writerows((f['path'], f['bytes'], f['sha256']) for f in files)
    (ROOT / '资料校验清单.csv').write_text(buffer.getvalue(), encoding='utf-8-sig', newline='')
    for f in files:
        need((ROOT / f['path']).stat().st_size == f['bytes'] and sha(f['path']) == f['sha256'], 'Manifest changed: ' + f['path'])
    print(json.dumps({'pass': True, 'record': RECORD, 'manifest_files': len(files), 'app_build_sha256': app_hash, 'deployed': False, 'zip_repacked': False}, ensure_ascii=False))

if __name__ == '__main__':
    main()

