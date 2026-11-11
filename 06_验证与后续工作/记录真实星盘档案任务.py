"""Maintain the existing task table for the single W1 birth-city and complete personal chart revision."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parent.parent
LEDGER = '06_验证与后续工作/真实星盘档案实施记录.json'
PREVIOUS = '06_验证与后续工作/完整星盘交付记录.json'
BASELINE = '06_验证与后续工作/真实星盘档案实施前核验.json'
MODULES = {
    'W1': ('真实星盘W1-出生城市与完整档案', '星盘出生城市与完整个人档案',
           '依最新用户授权只在星盘档案恢复出生城市，离线GeoNames候选真实选择，自动取IANA时区及坐标；准确时间与城市可算完整个人盘；独立城市未知时间取真实本地日范围，未找到不猜；其余主生辰/两盘不改。'),
}

def need(ok, text):
    if not ok:
        raise AssertionError(text)

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))

def app_hash(run):
    return run.get('buildSha256') or run.get('appBuildSha256') or run.get('buildHashes', {}).get('东方智慧-首页体验R4.html')

def safe_file(relative):
    path = (ROOT / relative).resolve()
    need(path.is_relative_to(ROOT.resolve()) and path.is_file() and not path.is_symlink(), 'Unsafe/missing file: ' + relative)
    return path

def new_ledger():
    prior = read(PREVIOUS)
    baseline = {'report': BASELINE, 'sha256': None, 'app_sha256': prior['app_build_sha256'], 'status': '待根冻结检查点'}
    if (ROOT / BASELINE).exists():
        before = read(BASELINE)
        need(before['app_sha256'] == prior['app_build_sha256'], 'W1 checkpoint is not the accepted S1 APP')
        baseline.update({'sha256': sha(safe_file(BASELINE)), 'status': '已冻结'})
    review = '02_需求与设计参考/出生城市离线索引来源-20261111.json'
    return {
        'scope': '仅星盘档案的出生城市与完整个人盘；最新用户授权覆盖此前该处城市禁令，主生辰与紫微/八字不恢复地域控件。AI/托管/飞书暂停，不打包不发布。',
        'references': [], 'baseline': baseline,
        'source_review': {'report': review, 'sha256': sha(safe_file(review))},
        'previous_structure_revision': {'report': PREVIOUS, 'sha256': sha(safe_file(PREVIOUS)), 'scope': '保留S1、C1/C2和更早冻结证据；W1只增加星盘出生城市与完整资料能力。'},
        'modules': {key: {'name': value[0], 'title': value[1], 'requirement': value[2], 'status': '待实施', 'reports': []} for key, value in MODULES.items()},
        'history': [],
    }

def accepted_reports(module, names):
    need(names, 'Completion needs actual smoke and both full reports')
    current = sha(ROOT / '03_当前APP/东方智慧-首页体验R4.html')
    refs, targets, smokes = [], set(), 0
    for name in names:
        path = safe_file(name)
        need(path.is_relative_to((ROOT / '06_验证与后续工作').resolve()), 'Report outside verification directory')
        document = read(name)
        run = document.get('latest', document)
        results = run.get('results', run.get('checks', []))
        need(run.get('pass') is True and run.get('failed') == 0 and run.get('module') == MODULES[module][0], 'Wrong or failed current module report: ' + name)
        need(results and all(row.get('pass') is True for row in results), 'Report has missing/failed checks: ' + name)
        need(run.get('passed') == len(results) and app_hash(run) == current, 'Report count/build differs: ' + name)
        for rel, value in run.get('sourceHashes', {}).items():
            need(sha(safe_file(rel)) == value, 'Report source differs: ' + rel)
        for folder, field in [('03_当前APP', 'buildHashes'), ('04_研发源码/app/cloud', 'cloudBuildHashes')]:
            for rel, value in run.get(field, {}).items():
                need(sha(safe_file(folder + '/' + rel)) == value, 'Report build differs: ' + rel)
        if '全量' in path.name:
            need(run['passed'] >= 60, 'Incomplete full regression')
            targets.add('cloud' if run.get('cloudWorker') or 'cloud' in path.name.lower() else 'python')
        if '冒烟' in path.name:
            need(run.get('productionWrites') is False, 'Smoke must use isolated data')
            smokes += 1
        refs.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path), 'count': run['passed']})
    need(targets == {'python', 'cloud'} and smokes, 'Need Python + local Cloud full regressions and smoke')
    return refs, current

def task_section(record):
    esc = html.escape
    row = record['modules']['W1']
    links = ''.join('<br><a href="' + esc(ref['path'], quote=True) + '">' + str(ref['count']) + '项实际证据</a>' for ref in row['reports'])
    return '<!-- real-western-20261111:start --><section id="real-western-20261111"><h2>当前执行：星盘出生城市与完整个人档案</h2><p>用户最新明确允许只在星盘档案恢复出生城市，由城市自动处理时区和经纬度。本轮授权优先于此前该处城市禁令；不恢复主生辰表地域字段，不改变紫微/八字原规则。</p><p>使用固定GeoNames全球离线城市索引，候选必须实际选择，按id取真实城市坐标和IANA时区；中文/拼音/英文搜索，同名显示国家地区/省区，不猜不存在的城市。准确时间加真实城市才能生成完整个人盘，未知时间继续范围参考，不默认零点或猜宫位。</p><p>未建立星盘独立档案时保留原固定北京时间25点参考；独立城市档案未知时刻按该城市真实本地日期起止计算，常见23/24/25小时，也处理半小时等调整，以至多1小时步长加末端动态采样。当地午夜不存在则明确报错；午夜重复取最早时刻仅作为整日边界，不推定出生时刻。</p><div class="table-wrap"><table><thead><tr><th>模块</th><th>范围</th><th>门禁</th><th>状态</th></tr></thead><tbody><tr id="real-western-W1"><td>W1</td><td>' + esc(MODULES['W1'][2]) + '</td><td>W1真实档案冒烟10组、S1结构烟8与星盘C1烟7、五专项及Python/本地Cloud各完整60项，全部绑定最终W1构建。</td><td data-real-western-status="W1">' + row['status'] + links + '</td></tr></tbody></table></div><p>AI/托管/飞书继续暂停，本地实施、不发布、不打包。旧S1/C1C2/M1M5/F05 receipt与台账和旧ZIP原样保留；不把历史报告当本轮验收。</p><p><a href="06_验证与后续工作/真实星盘档案实施记录.json">W1台账</a> · <a href="02_需求与设计参考/出生城市离线索引来源-20261111.json">城市固定来源与许可</a> · <a href="06_验证与后续工作/完整星盘交付记录.json">S1历史交付</a></p><p class="meta">更新' + esc(record['updated_at']) + '；城市覆盖不含所有村庄/门牌，视觉待用户评价。</p></section><!-- real-western-20261111:end -->'

def planned_task_table(record):
    path = ROOT / '改动任务表-2026-10-22.html'
    text = path.read_text(encoding='utf-8')
    section = task_section(record)
    if '<!-- real-western-20261111:start -->' in text:
        text = re.sub(r'<!-- real-western-20261111:start -->[\s\S]*?<!-- real-western-20261111:end -->', lambda _: section, text, count=1)
    else:
        text, count = re.subn(r'(<main\b[^>]*>)', lambda match: match.group(1) + '\n' + section, text, count=1)
        need(count == 1, 'Existing task table main missing')
    return text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--module', choices=list(MODULES))
    parser.add_argument('--status', choices=['待实施', '实施中', '已通过'])
    parser.add_argument('--report', action='append', default=[])
    args = parser.parse_args()
    record = read(LEDGER) if (ROOT / LEDGER).exists() else new_ledger()
    now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    if args.module:
        prior = list(MODULES)[:list(MODULES).index(args.module)]
        need(all(record['modules'][key]['status'] == '已通过' for key in prior), 'Earlier module gates have not passed')
        entry = record['modules'][args.module]
        if args.status == '已通过':
            before = read(BASELINE)
            need(before['app_sha256'] == read(PREVIOUS)['app_build_sha256'], 'W1 checkpoint does not bind accepted S1 APP')
            record['baseline'] = {'report': BASELINE, 'sha256': sha(safe_file(BASELINE)), 'app_sha256': before['app_sha256'], 'status': '已冻结'}
            entry['reports'], entry['app_sha256'] = accepted_reports(args.module, args.report)
        need(not (entry['status'] == '已通过' and args.status != '已通过'), 'Do not overwrite accepted historical stage')
        if args.status:
            entry['status'] = args.status
        record['history'].append({'at': now, 'module': args.module, 'status': entry['status'], 'reports': entry['reports']})
    record['updated_at'] = now
    table = planned_task_table(record)
    (ROOT / LEDGER).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / '改动任务表-2026-10-22.html').write_text(table, encoding='utf-8')
    print(json.dumps({'modules': {key: row['status'] for key, row in record['modules'].items()}, 'published': False}, ensure_ascii=False))

if __name__ == '__main__':
    main()
