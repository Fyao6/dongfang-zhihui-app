"""Maintain the existing task table for the two November 11 reference modules."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parent.parent
LEDGER = '06_验证与后续工作/准了参考实施记录.json'
PREVIOUS = '06_验证与后续工作/改动文档交付记录.json'
BASELINE = '06_验证与后续工作/准了参考重做前核验.json'
MODULES = {
    'C1': ('准了参考C1-星盘盘面重做', '星盘盘面比例与样式',
           '按11月11日用户星盘参考图调整真实星盘的盘面比例、层级和颜色；保留精确地心/旧完整档案和未知全天范围的数据边界、可达详情、键盘及四语。'),
    'C2': ('准了参考C2-八字比例重做', '八字比例与样式',
           '按11月11日用户八字参考图调整六列表及流运比例；固定lunar1.7.7真实本人四柱与运年月，保留档案/流运/神煞三页、12类规则、完整详情及真实保存复算。'),
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
    return {
        'scope': '2026-11-11用户两张准了参考图；只本地重做比例与样式，托管/飞书/AI继续暂缓，不打完整包。',
        'references': before['references'],
        'baseline': {'report': BASELINE, 'sha256': sha(safe_file(BASELINE)), 'app_sha256': before['app_sha256']},
        'previous_document_revision': {'report': PREVIOUS, 'sha256': sha(safe_file(PREVIOUS)), 'scope': '原M1—M5事实与冻结证据保留；星盘/八字视觉被最新用户反馈替代，不代表此前计算失效。'},
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
    rows = []
    for key, values in MODULES.items():
        row = record['modules'][key]
        links = ''.join('<br><a href="' + esc(ref['path'], quote=True) + '">' + str(ref['count']) + '项实际证据</a>' for ref in row['reports'])
        rows.append('<tr id="reference-' + key + '"><td>' + key + '</td><td>' + esc(values[1]) + '</td><td>' + esc(values[2]) + '</td><td>先本模块冒烟，再Python与本地Cloud各完整60项；缺陷修复重跑通过后才推进。</td><td data-reference-status="' + key + '">' + row['status'] + links + '</td></tr>')
    references = ''.join('<figure><img loading="lazy" src="' + esc(ref['path'], quote=True) + '" alt="用户11月11日参考图"><figcaption>' + esc(Path(ref['path']).name) + '</figcaption></figure>' for ref in record['references'])
    return '''<!-- reference-charts-20261111:start -->
<section id="reference-charts-20261111"><h2>当前执行：11月11日星盘与八字参考比例重做</h2>
<p>用户补充两张准了参考图，更新星盘和八字的盘面比例/样式要求。先C1星盘、通过后C2八字；本人真实资料与既定计算不变，不把截图示例当用户数据。旧M1—M5交付事实保留，其视觉以本次最新反馈为准。</p>
<p>出生仍仅生日、性别、选填称呼/时间；未知时刻不造精确紫微或八字，西盘仅真实25样本全天范围，无坐标不猜ASC/宫位。AI、托管、飞书暂缓，本轮不发布、不打完整包，旧ZIP和旧receipt原样保留。</p>
<div class="table-wrap"><table class="task-table"><thead><tr><th>顺序</th><th>模块</th><th>范围与验收边界</th><th>准入门禁</th><th>状态及证据</th></tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table></div>
<p><a href="06_验证与后续工作/准了参考实施记录.json">本轮两模块台账</a> · <a href="06_验证与后续工作/准了参考重做前核验.json">改前冻结身份</a> · <a href="06_验证与后续工作/改动文档交付记录.json">保留的M1—M5历史交付</a></p>
<details><summary>查看用户本轮两张参考原图</summary>''' + references + '</details><p class="meta">最后更新 ' + esc(record['updated_at']) + '''；视觉仍待用户实际评价。</p></section>
<!-- reference-charts-20261111:end -->'''

def planned_task_table(record):
    path = ROOT / '改动任务表-2026-10-22.html'
    text = path.read_text(encoding='utf-8')
    section = task_section(record)
    if '<!-- reference-charts-20261111:start -->' in text:
        text = re.sub(r'<!-- reference-charts-20261111:start -->[\s\S]*?<!-- reference-charts-20261111:end -->', lambda _: section, text, count=1)
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
