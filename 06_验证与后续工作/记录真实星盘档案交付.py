"""Record the single W1 birth-city and full personal chart revision only after final acceptance. Never build, test, publish or ZIP."""
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
OLD = '06_验证与后续工作/完整星盘交付记录.json'
RECORD = '06_验证与后续工作/真实星盘档案交付记录.json'
LEDGER = '06_验证与后续工作/真实星盘档案实施记录.json'
GUIDE = '05_后台与研发说明/真实星盘出生城市与档案验收说明.txt'
GALLERY = '06_验证与后续工作/原创命盘效果查看.html'
SOURCE_REVIEW = '02_需求与设计参考/出生城市离线索引来源-20261111.json'
TIME_BASIS_REVIEW = '02_需求与设计参考/出生城市时间口径核对-20261111.json'
MODULE = '真实星盘W1-出生城市与完整档案'
UNKNOWN_RANGE_POLICY = '未建立星盘独立档案时保留原固定北京时间25点参考；独立城市档案未知时刻按该城市真实本地日期起止计算，常见23/24/25小时，也处理半小时等调整，以至多1小时步长加末端动态采样。当地午夜不存在则明确报错；午夜重复取最早时刻仅作为整日边界，不推定出生时刻。'
SMOKES = {'real_western_smoke': ('真实星盘档案冒烟.json', 10), 'structure_smoke': ('完整星盘结构冒烟.json', 8), 'reference_western_smoke': ('准了参考星盘冒烟.json', 7)}
SCOPE = '按用户最新授权，仅在星盘档案恢复出生城市，离线真实城市候选自动提供时区与坐标；准确生辰和实际城市生成完整个人盘，城市未知时刻取真实本地日期范围，未找到不猜。主生辰四字段、紫微/八字原规则、已有档案与功能保留。AI/托管/飞书暂停，只本地完成，未发布、未新打包。'

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
    need(run.get('pass') is True and run.get('failed') == 0 and run.get('passed', 0) >= minimum and run.get('module') == MODULE, 'Final W1 run missing/failed: ' + relative)
    need(package.report_app(run) == app_hash and run.get('sourceHashes'), 'Final W1 build/source identity missing: ' + relative)
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
    need(old.get('pass') is True and old.get('structure_revision') is True, 'Immutable S1 receipt absent')
    app_hash = sha('03_当前APP/东方智慧-首页体验R4.html')
    full = {}
    for key, filename in [('local', '本轮全量回归结果.json'), ('cloudflare', '公网适配全量回归结果.json')]:
        rel = '06_验证与后续工作/' + filename
        run = latest(rel)
        need(run.get('pass') is True and run.get('failed') == 0 and run.get('passed', 0) >= 60 and run.get('module') == MODULE and package.report_app(run) == app_hash, 'Final W1 full missing: ' + key)
        need(run.get('buildHashes') and (key != 'cloudflare' or run.get('cloudBuildHashes')), 'Final full build identity absent')
        for folder, field in [('03_当前APP', 'buildHashes'), ('04_研发源码/app/cloud', 'cloudBuildHashes')]:
            for path, value in run.get(field, {}).items():
                base.safe_file(folder + '/' + path, package)
                need(sha(folder + '/' + path) == value, 'Final full build changed: ' + path)
        full[key] = {'report': rel, 'sha256': sha(rel), 'at': run['at'], 'module': MODULE, 'passed': run['passed']}
    runs, verification = {}, {}
    for key, (filename, minimum) in base.SPECIALTIES.items():
        runs[key], verification[key] = current_run('06_验证与后续工作/' + filename, minimum, app_hash, package, base)
    for key, (filename, minimum) in SMOKES.items():
        runs[key], verification[key] = current_run('06_验证与后续工作/' + filename, minimum, app_hash, package, base)
        need(runs[key].get('productionWrites') is False, 'Final reference smoke must be isolated')
    ledger = read(LEDGER)
    record = copy.deepcopy(old)
    record.update({
        'checked_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'pass': True, 'scope': SCOPE, 'ui_revision': True, 'document_revision': False,
        'reference_revision': False, 'structure_revision': False, 'real_western_revision': True, 'revision_module': MODULE, 'guide': GUIDE, 'preview_html': GALLERY,
        'app_build_sha256': app_hash, 'local_scope_complete': True, 'real_western_local_scope_complete': True,
        'all_planned_work_complete': False, 'paused_by_user': False, 'current_full': full,
        'verification': verification, 'complete_real_western_modules': ['W1'],
        'real_western_module_ledger': {'report': LEDGER, 'sha256': sha(LEDGER), 'modules': copy.deepcopy(ledger['modules'])},
        'previous_structure_revision': {'report': OLD, 'sha256': sha(OLD), 'app_build_sha256': old['app_build_sha256'], 'scope': 'Immutable S1 receipt and ledger. Earlier C1/C2, M1–M5 and F05 preserved; W1 adds city-selected Western personal profiles under the latest user authorization.'},
        'zip_repacked': False, 'production_writes': False, 'deployment_attempted_this_revision': False,
        'current_source_published': False, 'visual_approved_by_user': False,
        'source_review': {'report': SOURCE_REVIEW, 'sha256': sha(SOURCE_REVIEW)},
        'time_basis_review': {'report': TIME_BASIS_REVIEW, 'sha256': sha(TIME_BASIS_REVIEW)},
    })
    checks, historical = {}, {}
    package.historical_foundation(record, checks, historical)
    package.real_western_module(record, checks)
    city_review = read(SOURCE_REVIEW)
    record['city_data_snapshot'] = {'report': SOURCE_REVIEW, 'sha256': sha(SOURCE_REVIEW), 'snapshot': copy.deepcopy(city_review['snapshot']), 'coverage': copy.deepcopy(city_review['coverage']), 'runtime': copy.deepcopy(city_review['output']), 'notice': copy.deepcopy(city_review['notice']), 'source_files': copy.deepcopy(city_review['official_sources']), 'raw_archives_in_payload': False}
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
    sources.update([SOURCE_REVIEW, TIME_BASIS_REVIEW, '06_验证与后续工作/记录真实星盘档案交付.py', '06_验证与后续工作/记录真实星盘档案任务.py', '06_验证与后续工作/生成离线出生城市索引.py', '06_验证与后续工作/打包当前交付.py'])
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
    package.city_snapshot(record, checks)
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
    record['publication'].update({'current_source_published': False, 'current_chart_ui_published': False, 'public_deployment_pending': True, 'package_matches_public': False, 'all_public_entry_points_current': False, 'scope': '本轮W1只本地完成。Sites v15/Netlify v14没有本轮改动；托管、飞书、AI暂缓，不发布/重试/监测/购买。'})
    record['captures_sha256'] = base.captures_from(list(runs.values()), package)
    record['previous_revisions'] = [*copy.deepcopy(old.get('previous_revisions', [])), {key: copy.deepcopy(old[key]) for key in ['checked_beijing', 'scope', 'revision_module', 'app_build_sha256', 'source_sha256', 'build_sha256', 'current_full', 'verification', 'layout_measurement', 'previous_zip']}]
    record['limits'] = [UNKNOWN_RANGE_POLICY, '最新授权仅恢复星盘档案城市，主生辰与紫微/八字不恢复地域输入。', '完整个人盘要求准确时刻和真实选择城市；未知时间不默认零点、不猜个人宫位或确定相位。', '城市索引为GeoNames cities15000固定快照，覆盖范围/条目数读取实际来源；不覆盖所有村庄/医院/门牌，找不到就明确失败。', '城市坐标代表命名地点，非精确出生地址；GeoNames原始IANA字段保留。仅目录时区为Asia/Urumqi的城市，必须明确出生记录用北京时间或新疆时间；不凭城市推断，其他城市自动用目录IANA规则。', '所有原始多语言别名保留，简繁查询复用OpenCC，同名需国/省/城市候选实际选择。', 'GeoNames署名、CC BY4许可链接及改编说明保留；原始ZIP只留本地而不打进交付包。', 'S1/C1C2/M1M5/F05旧receipt/台账/ZIP原样保留，历史恢复不是W1新恢复或生产恢复。', 'AI/托管/飞书继续暂停；只本地验收，视觉待用户评价，未发布/未新打包，不代表完整跨设备同步或实机验收。']
    counts = 'Python与本地Cloud完整回归分别' + str(full['local']['passed']) + '、' + str(full['cloudflare']['passed']) + '项通过且均0失败；出生/三盘/交互/长度/八字专项分别' + '/'.join(str(verification[key]['passed']) for key in base.SPECIALTIES) + '项，档案/结构/星盘守护冒烟分别' + '/'.join(str(verification[key]['passed']) for key in SMOKES) + '项。全部绑定本轮最终构建。'
    return base, package, record, counts, measured

def planned_outputs(base, package, record, counts, measured):
    esc = lambda value: html.escape(str(value), quote=True)
    guide = '东方智慧APP · 真实星盘出生城市与档案验收说明\n\n' + SCOPE + '\n\nW1：用户明确允许只在星盘档案恢复出生城市，并自动处理时区与经纬度。此项最新授权优先于此前该处地域禁令；不恢复主生辰表城市控件，不改变紫微/八字原规则。星盘独立资料沿当前账号本机保存，旧完整档案按原资料复算，不静默覆盖其他档案。\n城市搜索来自GeoNames固定离线索引，支持真实中文别名、拼音/英文规范化与简繁等价；同名明确显示国家地区/省区候选，必须实际选定城市id，坐标与IANA时区从该id反查。只输入文字不视为已确认；未找到城市明确失败，不猜测或用固定默认城市代替。城市名所代表的位置不是出生医院/门牌。\nGeoNames原始时区字段不改。仅目录时区为Asia/Urumqi的城市需明确出生记录所用北京时间或新疆时间；未选择不默认任一口径。档案保留catalogTimeZone与clockBasis，其他城市自动使用目录IANA规则；不新增技术时区/坐标表单。时间口径依据见' + TIME_BASIS_REVIEW + '。\n有准确生日、时间和实际城市后，按当地民用时间及历史时区规则归一化，计算完整个人星盘。重复/不存在的本地时刻需按实际规则处理，不静默猜测。未知时间不默认零点、不伪造个人ASC/宫位或确定相位。' + UNKNOWN_RANGE_POLICY + '\n真实天体仍由Astronomy2.1.19计算，既有相位和宫制在APP内实现；lunar1.7.7用于历法/八字，不能冒称西方星盘API。结构参考线与个人宫位区别说明，计算/资料来源可查。\n\nGeoNames数据CC BY4.0，来源、许可链接和改编说明在vendor署名及' + SOURCE_REVIEW + '保留。索引含官方cities15000城市，非所有村镇；原始ZIP本地留存并按既有过滤排除，不递归进入交付包。\n旧S1、C1/C2、M1—M5、F01—F05 receipt/台账与ZIP完全原样保留，旧恢复只为未改后端的历史隔离证据，不是W1新恢复或生产恢复。\n计时、三地图4/4/3、四语、创作者与数据中心继续保留。生辰/资料/排盘/笔记按本浏览器账号保存，不代表完整跨设备云同步。藏文真实换行和滚动保留，仍待母语审校。\nAI、托管、飞书继续暂停；仅本地完成、视觉待用户评价，Sites v15/Netlify v14不含W1，未发布、未生成或覆盖完整ZIP。8880/8879用户预览保留。\n\n实际验收：\n' + counts + '\n' + measured + '\n城市覆盖：' + str(record['city_data_snapshot']['coverage']['cities']) + '条/国家地区代码' + str(record['city_data_snapshot']['coverage']['countryCodes']) + '个；快照' + record['city_data_snapshot']['snapshot']['version'] + '\nAPP SHA-256：' + record['app_build_sha256'] + '\n交付记录：' + RECORD + '\nW1台账：' + LEDGER + '\n'
    links = '<p><a href="' + GUIDE + '">本轮说明</a> · <a href="' + RECORD + '">最终证据</a> · <a href="' + LEDGER + '">W1台账</a> · <a href="' + GALLERY + '">当前效果</a> · <a href="03_当前APP/发给负责人-东方智慧首页R4.html">离线APP</a></p>'
    section = '<section id="real-western-delivery"><h2>真实星盘 · 出生城市与完整档案</h2><p>' + esc(SCOPE) + '</p><p>' + esc(counts) + '</p><p>' + esc(measured) + '</p><p>下方旧轮验收保留历史；当前星盘城市/档案以上方W1记录为准，其他两盘继续沿用。未知不造精确盘、AI/托管/飞书暂停、未发布/未新打包。</p>' + links + '</section>'
    outputs = {GUIDE: guide, RECORD: json.dumps(record, ensure_ascii=False, indent=2) + '\n'}
    for relative in ['打开这里.html', '改动任务表-2026-10-22.html']:
        text = (ROOT / relative).read_text(encoding='utf-8')
        text = re.sub(r'<!-- real-western-delivery:start -->[\s\S]*?<!-- real-western-delivery:end -->\s*', '', text)
        block = '<!-- real-western-delivery:start -->' + section + '<!-- real-western-delivery:end -->'
        text, count = re.subn(r'(<main\b[^>]*>)', lambda match: match.group(1) + '\n' + block, text, count=1)
        need(count == 1, 'Entry main missing')
        outputs[relative] = text
    notice = record['checked_beijing'] + '\n' + SCOPE + '\n' + counts + '\n' + measured + '\n说明：' + GUIDE + '\n证据：' + RECORD + '；台账：' + LEDGER + '\n旧轮界面及旧包为历史快照，未发布、未新打包。\n'
    for relative in ['先读我.txt', '交付包说明.txt']:
        text = (ROOT / relative).read_text(encoding='utf-8')
        text = re.sub(r'【真实星盘档案本地验收】[\s\S]*?【真实星盘档案本地验收结束】\s*', '', text)
        outputs[relative] = '【真实星盘档案本地验收】\n' + notice + '【真实星盘档案本地验收结束】\n\n此前星盘结构作为历史，当前以W1为准；已验收紫微/八字继续沿用。\n' + text
    gallery = '<!doctype html><html lang="zh-Hans"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>真实星盘 · 当前出生城市档案</title><style>body{margin:0;background:#f7f5ef;color:#25323b;font:15px/1.8 sans-serif}main{max-width:1050px;margin:auto;padding:24px}a{color:#866019}figure{margin:24px 0}img{display:block;width:100%;max-width:430px;height:auto;border:1px solid #aaa}figcaption{overflow-wrap:anywhere}</style><main><h1>真实星盘出生城市档案 · 本地效果</h1><p>' + esc(SCOPE) + '</p><p>' + esc(counts) + '</p><p>' + esc(measured) + '</p><p>合成夹具截图仅用于验收，不是业务默认或用户档案。视觉仍待用户评价。</p><p><a href="../' + GUIDE + '">说明</a> · <a href="真实星盘档案交付记录.json">证据</a></p>'
    for relative in record['captures_sha256']:
        name = Path(relative).relative_to('06_验证与后续工作').as_posix()
        gallery += '<figure><figcaption>' + esc(Path(name).stem) + '</figcaption><a href="' + esc(name) + '"><img loading="lazy" src="' + esc(name) + '" alt="' + esc(Path(name).stem) + '"></a></figure>'
    outputs[GALLERY] = gallery + '</main></html>'
    agents = (ROOT / 'AGENTS.md').read_text(encoding='utf-8-sig')
    agents = re.sub(r'<!-- real-western-final-verified:start -->[\s\S]*?<!-- real-western-final-verified:end -->\s*', '', agents)
    outputs['AGENTS.md'] = agents + '\n\n<!-- real-western-final-verified:start -->\n### ' + record['checked_beijing'][:10] + ' 真实星盘W1本地验收\n' + SCOPE + '\n' + counts + '\n旧S1/C1C2/M1M5记录保留；仅星盘档案城市新授权例外，主生辰与两盘不改；' + UNKNOWN_RANGE_POLICY + '紫微/八字未知不造精确盘。来源：' + SOURCE_REVIEW + '；时间口径依据：' + TIME_BASIS_REVIEW + '；当前证据：' + RECORD + '；说明：' + GUIDE + '。未发布、未新打包，视觉待用户评价。\n<!-- real-western-final-verified:end -->\n'
    base.validate_output_links(outputs, package)
    return outputs

def refresh_manifests(package, record):
    files = [{'path': rel, 'bytes': path.stat().st_size, 'sha256': sha(rel)} for rel, path in sorted(package.collect_files().items()) if rel not in package.SELF]
    inventory = read('原始来源与文件校验.json')
    inventory['files'] = files
    inventory['current_revision'] = {'updated_beijing': record['checked_beijing'], 'scope': SCOPE, 'delivery_record': RECORD, 'app_build_sha256': record['app_build_sha256'], 'local_scope_complete': True, 'public_deployment_pending': True, 'zip_repacked': False, 'real_western_module_ledger': LEDGER}
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
    need(sha(OLD) == record['previous_structure_revision']['sha256'] and sha(record['structure_module_ledger']['report']) == record['structure_module_ledger']['sha256'] and sha(record['reference_module_ledger']['report']) == record['reference_module_ledger']['sha256'] and sha(record['document_module_ledger']['report']) == record['document_module_ledger']['sha256'] and sha(record['previous_zip']['path']) == record['previous_zip']['sha256'], 'Historical receipt/ledger/ZIP changed')
    print(json.dumps({'pass': True, 'record': RECORD, 'module': MODULE, 'app_build_sha256': record['app_build_sha256'], 'sources': len(record['source_sha256']), 'builds': len(record['build_sha256']), 'manifest_files': count, 'deployed': False, 'zip_repacked': False}, ensure_ascii=False))

if __name__ == '__main__':
    main()
