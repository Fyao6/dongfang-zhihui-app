"""Maintain the existing task table for the single full-wheel structure revision."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parent.parent
LEDGER = '06_验证与后续工作/完整星盘实施记录.json'
PREVIOUS = '06_验证与后续工作/准了参考交付记录.json'
BASELINE = '06_验证与后续工作/完整星盘重做前核验.json'
MODULES = {
    'S1': ('完整星盘S1-盘面结构与连线', '星盘结构与中间连线',
           '依据用户补充星盘结构图完成盘面分区、标签及真实连线；黄道结构参考与真实宫位/相位明确区分，真实经度/算法/档案及未知全天范围边界不变。'),
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
    before = read(BASELINE)
    image = '02_需求与设计参考/准了参考-20261111-星盘结构补图.png'
    return {
        'scope': '用户补充星盘结构图；仅本地Western盘面结构与连线，不改变计算/API/生辰，AI/托管/飞书暂停，不打包不发布。',
        'references': [{'path': image, 'sha256': sha(safe_file(image))}],
        'baseline': {'report': BASELINE, 'sha256': sha(safe_file(BASELINE)), 'app_sha256': before['app_sha256']},
        'previous_reference_revision': {'report': PREVIOUS, 'sha256': sha(safe_file(PREVIOUS)), 'scope': '保留C1/C2真实验收与冻结身份；仅星盘视觉由最新补图要求替代，C2八字继续沿用。'},
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
    row = record['modules']['S1']
    links = ''.join('<br><a href="' + esc(ref['path'], quote=True) + '">' + str(ref['count']) + '项实际证据</a>' for ref in row['reports'])
    image = record['references'][0]['path']
    return '<!-- complete-western-20261111:start --><section id="complete-western-20261111"><h2>当前执行：完整星盘结构与连线</h2><p>用户进一步指出星盘空散并补充结构图。只重做Western盘面与中间线，不改变已验收八字或计算参数；C1/C2及M1—M5旧验收事实、原receipt/台账/ZIP完整保留，星盘视觉以本轮最新反馈为准。</p><p>lunar固定1.7.7用于历法和八字，不提供西方宫位/相位API。西盘仍用Astronomy2.1.19真实位置；结构分区不能冒充无地点时的宫位或未知相位。未知全天范围、四字段生辰、AI/托管/飞书暂停边界不变。</p><div class="table-wrap"><table><thead><tr><th>模块</th><th>实施与验收</th><th>门禁</th><th>状态</th></tr></thead><tbody><tr id="full-chart-S1"><td>S1</td><td>' + esc(MODULES['S1'][2]) + '</td><td>S1冒烟及Python/本地Cloud各完整60项通过；最终五专项与两套星盘烟同构建。</td><td data-structure-status="S1">' + row['status'] + links + '</td></tr></tbody></table></div><p><a href="06_验证与后续工作/完整星盘实施记录.json">本轮台账</a> · <a href="06_验证与后续工作/准了参考交付记录.json">C1/C2历史</a> · <a href="02_需求与设计参考/完整星盘数据来源核对-20261111.json">官方来源核对</a></p><details><summary>查看用户补充结构参考图</summary><img loading="lazy" src="' + esc(image, quote=True) + '" alt="用户星盘结构补图"></details><p class="meta">更新' + esc(record['updated_at']) + '；本地实施，不发布、不打包，视觉待用户评价。</p></section><!-- complete-western-20261111:end -->'

def planned_task_table(record):
    path = ROOT / '改动任务表-2026-10-22.html'
    text = path.read_text(encoding='utf-8')
    section = task_section(record)
    if '<!-- complete-western-20261111:start -->' in text:
        text = re.sub(r'<!-- complete-western-20261111:start -->[\s\S]*?<!-- complete-western-20261111:end -->', lambda _: section, text, count=1)
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
