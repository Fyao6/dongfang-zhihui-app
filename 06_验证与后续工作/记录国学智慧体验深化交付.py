"""Write this release's delivery records only after all real evidence gates pass.

Root reviews and executes this script after M4 and publication; merely importing it
does not change files. It never builds, publishes, changes credentials or touches a DB.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
import csv
import hashlib
import html
import io
import json
import os
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / '06_验证与后续工作'
WEB = ROOT / '03_当前APP'
R4 = ROOT / '04_研发源码/app/r4'
CLOUD = ROOT / '04_研发源码/app/cloud'
RECORD = '06_验证与后续工作/国学智慧体验深化交付记录.json'
GUIDE = '05_后台与研发说明/国学智慧体验深化使用与回退说明.txt'
HEX64 = re.compile(r'^[0-9a-f]{64}$')


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def project_path(relative):
    p = ROOT / str(relative)
    resolved = p.resolve()
    need(resolved.is_relative_to(ROOT.resolve()), 'Path escapes project: ' + str(relative))
    need(not p.is_symlink(), 'Symlink is not a delivery file: ' + str(relative))
    return p


def evidence_path(relative):
    p = project_path(relative) if '/' in str(relative).replace('\\', '/') else EVIDENCE / relative
    need(p.resolve().parent == EVIDENCE.resolve(), 'Report must be in the existing evidence directory: ' + str(relative))
    return p


def read(relative):
    return json.loads(project_path(relative).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def instant(value):
    d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    need(d.tzinfo is not None, 'Evidence timestamp must specify a time zone: ' + str(value))
    return d


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def report_file(relative):
    p = evidence_path(relative)
    data = json.loads(p.read_text(encoding='utf-8-sig'))
    return p, data, data.get('latest', data)


def check_hashes(values, folder, label):
    need(isinstance(values, dict) and values, label + ': missing build hashes')
    for name, expected in values.items():
        p = folder / name
        need(p.resolve().is_relative_to(folder.resolve()), label + ': path escapes build directory')
        need(isinstance(expected, str) and HEX64.fullmatch(expected), label + ': invalid digest ' + name)
        need(p.is_file() and digest(p) == expected, label + ': current file differs: ' + name)


def checked_report(relative, count, build, since, stage=None):
    p, _, s = report_file(relative)
    need(s.get('pass') is True and s.get('passed') == count and s.get('failed') == 0, p.name + ': latest result is not fully passed')
    need(instant(s['at']) >= since, p.name + ': result predates this work')
    need(not s.get('errors'), p.name + ': browser errors remain')
    if 'results' in s:
        need(len(s['results']) == count and all(x.get('pass') is True for x in s['results']), p.name + ': underlying assertions disagree with the summary')
    if stage is not None:
        need(s.get('stage') == stage, p.name + ': wrong standalone stage')
    if 'buildSha256' in s:
        need(s['buildSha256'] == build, p.name + ': result is for another build')
    else:
        need('buildHashes' in s, p.name + ': no build identity')
        check_hashes(s['buildHashes'], WEB, p.name)
        need(s['buildHashes'].get('东方智慧-首页体验R4.html') == build, p.name + ': wrong app build')
    return p, s


def report_summary(p, s):
    keys = ['at', 'stage', 'base', 'module', 'pass', 'passed', 'failed', 'buildSha256', 'readOnly',
            'clientSideSyntheticCalculation', 'localRecordWriteChecks', 'noProductionDataWrite', 'scope']
    return {'report': p.relative_to(ROOT).as_posix(), 'report_sha256': digest(p),
            **{k: s[k] for k in keys if k in s}}


def numerical_report(relative, since, expected=None):
    p, _, s = report_file(relative)
    totals = s.get('totals', s)
    passed, failed = totals.get('passed'), totals.get('failed')
    need(isinstance(passed, int) and passed > 0 and failed == 0, p.name + ': numerical checks failed or absent')
    need(s.get('pass', True) is True, p.name + ': report is not passed')
    if 'total' in totals:
        need(totals['total'] == passed, p.name + ': numerical total disagrees with passed count')
    if expected is not None:
        need(passed == expected, p.name + ': unexpected number of checks')
    at = s.get('at', s.get('executedAt'))
    need(at is not None and instant(at) >= since, p.name + ': numerical evidence predates the work')
    rows = s.get('results', s.get('checks', []))
    need(len(rows) == passed, p.name + ': numerical assertions are incomplete')
    for row in rows:
        need(row.get('pass', row.get('passed')) is True, p.name + ': a numerical assertion is not passed')
    return {'report': p.relative_to(ROOT).as_posix(), 'report_sha256': digest(p),
            'at': at, 'pass': True, 'passed': passed, 'failed': failed, 'scope': s.get('scope', '')}


def notice_text(old, text):
    start, end = '<!-- guoxue-experience-delivery:start -->', '<!-- guoxue-experience-delivery:end -->'
    block = start + '\n' + text.strip() + '\n' + end
    if start in old:
        need(old.count(start) == 1 and old.count(end) == 1, 'Delivery notice marker is malformed')
        a, b = old.index(start), old.index(end) + len(end)
        return old[:a] + block + old[b:]
    return old.rstrip() + '\n\n' + block + '\n'


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    date = stamp[:10]
    build = digest(WEB / '东方智慧-首页体验R4.html')
    backup = read('06_验证与后续工作/国学智慧体验深化前备份核验.json')
    need(backup.get('pass') is True, 'The pre-change backup was not verified')
    since = instant(backup['at'])
    backup_file = project_path(backup['archive'])
    need(backup_file.is_file() and digest(backup_file) == backup['sha256'], 'Pre-change backup is missing or its digest differs')
    need(backup_file.stat().st_size == backup['archive_bytes'], 'Backup size differs')
    need(len(backup['files']) == backup['verified_files'], 'Backup verified-file count differs')

    # All four sequential module gates must be backed by the corresponding actual historical runs.
    ledger = read('06_验证与后续工作/国学智慧逐模块回归记录.json')
    modules = ledger.get('modules', [])
    need([m.get('module') for m in modules] == [1, 2, 3, 4], 'Module ledger must contain modules 1 through 4 in order')
    previous_completed = since
    for m in modules:
        n = m['module']
        need(m.get('pass') is True and HEX64.fullmatch(m.get('app_sha256', '')), 'Module ' + str(n) + ': not passed or missing build identity')
        completed = instant(m['completed_beijing'])
        need(completed >= previous_completed, 'Module completion order is inconsistent')
        for kind in ['python', 'cloudflare']:
            reference = m['checks'][kind]
            p, data, latest = report_file(reference['report'])
            runs = list(data.get('runs', [])) + [latest]
            matched = [s for s in runs if s.get('at') == reference['at']]
            need(matched, 'Module ' + str(n) + ': missing actual ' + kind + ' run')
            s = matched[-1]
            need(s.get('pass') is True and s.get('passed') == 56 + n and s.get('failed') == 0, 'Module ' + str(n) + ': failed full run')
            need(reference['passed'] == s['passed'] and reference['failed'] == 0, 'Ledger and report counts disagree')
            need(s.get('coverage', {}).get('baziStage') == n, 'Module ' + str(n) + ': wrong full-regression stage')
            need(s.get('buildHashes', {}).get('东方智慧-首页体验R4.html') == m['app_sha256'], 'Module ' + str(n) + ': run and ledger builds differ')
            need(previous_completed <= instant(s['at']) <= completed, 'Module ' + str(n) + ': actual run is outside its sequential gate')
        previous_completed = completed
    need(modules[-1]['app_sha256'] == build, 'M4 ledger does not identify the current build')

    reports = {}
    for key, filename, count, stage in [
        ('local_full', '本轮全量回归结果.json', 60, None),
        ('cloudflare_full', '公网适配全量回归结果.json', 60, None),
        ('standalone_bazi_stage4', '八字体验逐模块验收.json', 4, 4),
        ('three_charts_local', '三盘实际排盘联调.json', 14, None),
        ('three_charts_public', '三盘实际排盘公网联调.json', 11, None),
    ]:
        p, s = checked_report(filename, count, build, since, stage)
        reports[key] = report_summary(p, s)
        if key in ['local_full', 'cloudflare_full']:
            need(s.get('coverage', {}).get('baziStage') == 4 and s.get('baziExperience', {}).get('stage') == 4, p.name + ': final full run did not include all four stages')
            need(len(s.get('results', [])) == 60 and all(x.get('pass') is True for x in s['results']), p.name + ': full assertions are incomplete')
        if key == 'cloudflare_full':
            need(s.get('cloudWorker') is True, 'Cloudflare full report is not a worker run')
            check_hashes(s.get('cloudBuildHashes'), CLOUD, p.name)

    numeric = {
        'current_boundaries': numerical_report('八字当前运程边界核验.json', since, 20),
        'seven_column_relations': numerical_report('八字本命运程对照核验.json', since, 160),
        'glossary': numerical_report('八字术语词典定点核验.json', since, 12),
        'auxiliary_and_minor_periods': numerical_report('八字辅助与小运核验.json', since),
    }

    # Actual publication identifiers are supplied only after deployment and are never invented here.
    supplied = read('06_验证与后续工作/国学智慧本轮发布信息.json')
    required = ['project_id', 'source_commit', 'sites_version', 'sites_version_id', 'sites_deployment_id',
                'sites_status', 'netlify_site_id', 'netlify_deploy_id', 'netlify_status', 'archive', 'url',
                'public_build_match_report', 'public_bazi_report']
    for key in required:
        need(key in supplied and supplied[key] not in [None, ''], 'Missing actual publication field: ' + key)
    publication = {key: supplied[key] for key in required}
    need(publication['sites_status'] == 'succeeded' and publication['netlify_status'] == 'ready', 'Publication has not succeeded')
    need(isinstance(publication['sites_version'], int) and publication['sites_version'] > backup['baseline']['sites_version'], 'No newer Sites version is identified')
    need(re.fullmatch(r'[0-9a-f]{40}', publication['source_commit']), 'Invalid actual source commit')
    identity = read('05_后台与研发说明/Netlify站点身份.json')
    need(publication['netlify_site_id'] == identity['site_id'], 'Publication identifies another Netlify site')
    parsed = urlparse(publication['url'])
    need(parsed.scheme == 'https' and parsed.netloc == urlparse(identity['url']).netloc, 'Publication URL is not the existing public origin')
    need(parsed.path == '/experience' and parse_qs(parsed.query).get('page') == ['classicsWisdom'], 'Publication URL does not open the Ba Zi screen')
    archive = project_path(publication['archive'])
    need(archive.is_file(), 'The actual deployment archive is missing')
    archive_hash = digest(archive)
    if supplied.get('archive_sha256'):
        need(supplied['archive_sha256'] == archive_hash, 'Deployment archive digest differs')
    publication['archive_sha256'] = archive_hash

    p, _, public_build = report_file(publication['public_build_match_report'])
    need(p.name == '国学智慧公网构建一致性.json', 'Wrong public build report')
    need(public_build.get('pass') is True and public_build.get('localAppSha256') == build, 'Public build does not match the final local build')
    need(instant(public_build['at']) >= since, 'Public build evidence predates the work')
    need(public_build.get('netlifyDeployId') == publication['netlify_deploy_id'] and public_build.get('sourceCommit') == publication['source_commit'] and public_build.get('sitesVersion') == publication['sites_version'], 'Public build identities differ from publication')
    checks = public_build.get('checks', [])
    need(len(checks) == 4 and {c.get('route') for c in checks} == {'/experience', '/creator', '/admin', '/'}, 'Public build evidence does not cover all four routes')
    for check in checks:
        expected_hash = check.get('expectedNormalizedSha256', '')
        need(isinstance(expected_hash, str) and HEX64.fullmatch(expected_hash), 'A public route has no valid build digest')
        need(check.get('origin') == parsed.scheme + '://' + parsed.netloc, 'Public build check used another origin')
        need(check.get('status') == 200 and check.get('generatedMatch') is True and check.get('servedNormalizedSha256') == expected_hash, 'A delivered public page differs')
    reports['public_build'] = {'report': p.relative_to(ROOT).as_posix(), 'report_sha256': digest(p), 'at': public_build['at'], 'pass': True, 'routes': 4, 'buildSha256': build}
    need(evidence_path(publication['public_bazi_report']).name == '八字体验公网验收.json', 'Wrong public Ba Zi report')
    p, public_bazi = checked_report(publication['public_bazi_report'], 4, build, since, 4)
    need(public_bazi.get('clientSideSyntheticCalculation') is True and public_bazi.get('localRecordWriteChecks') is False and public_bazi.get('noProductionDataWrite') is True, 'Public Ba Zi scope must be synthetic client calculation without archive or production data writes')
    reports['public_bazi'] = report_summary(p, public_bazi)

    app = (WEB / '东方智慧-首页体验R4.html').read_text(encoding='utf-8')
    review = (WEB / '发给负责人-东方智慧首页R4.html').read_text(encoding='utf-8')
    embedded, _ = json.JSONDecoder().raw_decode(review.split('const APP=', 1)[1])
    need(embedded.replace('__INITIAL__', '{}') == app, 'Review page embeds another app build')
    sources = [R4 / name for name in ['life-chart-core.js', 'life-chart-bazi.js', 'life-charts.css', 'navigation-back.js']]
    sources += sorted(R4.glob('bazi-*.js'))
    for source in sources:
        need(source.read_text(encoding='utf-8') in app, 'Current source is absent from built HTML: ' + source.name)
    engine = read('06_验证与后续工作/八字引擎版本与来源.json')
    need(engine['version'] == '1.7.7' and engine['license'] == 'MIT', 'Pinned engine or license changed')
    need(digest(R4 / 'vendor/lunar-1.7.7.js') == engine['sourceSha256'], 'Engine source differs from pinned evidence')
    need((R4 / 'vendor/lunar-1.7.7-LICENSE.txt').read_text(encoding='utf-8') in app, 'MIT license is missing from built app')
    issue_path = EVIDENCE / '八字M3-手选节令边界问题记录.json'
    issue = json.loads(issue_path.read_text(encoding='utf-8'))
    need(issue.get('actualTimePanel') != issue.get('expectedTimePanel'), 'The genuine M3 issue record is incomplete')

    capability_limits = [
        'Fixed lunar-javascript 1.7.7 MIT engine; IANA birth civil time is converted to fixed UTC+8, without true solar time.',
        'Current year/month changes at exact solar terms; manual selection is retained. Before-birth, before-first-start and unrepresented years are explicit states.',
        'Fortune table rows retain the library calendar-year and nominal-age convention; the actual first-start instant is checked separately.',
        'Seven columns compare four natal pillars and the selected major period, year and solar-term month using the same natal day master.',
        'Twenty-five glossary entries comprise ten basic terms, ten specific Ten Gods and five auxiliary terms; M3 originally delivered twenty and M4 added five. Labels explain traditional relationships without fate, personality or health predictions.',
        'Five-element labels have no strength weights or favorable-element inference. Each Xun Kong entry belongs to that pillar itself; no automatic natal-hit conclusion.',
        'Tai Yuan/Tai Xi and Ba Zi Ming Gong/Shen Gong are auxiliary traditional values, not actual conception dates, pregnancy records or health measurements, and are separate from Zi Wei palaces.',
        'Xiao Yun is derived from the natal hour pillar and remains separate from the year-based Liu Nian sequence.',
        'Archives remain browser-local and account-scoped, maximum twenty, with archived UTC recomputation; current-mode views reopen at today while saved manual views restore their selected period/year/month. No cloud sync, JSON import or production data migration.',
        'Chinese, Traditional Chinese, English and Tibetan; Tibetan still awaits native-language review. Browser fixtures do not certify physical devices, traditional interpretations, live AI or formal teachers.',
    ]
    record = {
        'checked_beijing': stamp, 'pass': True, 'scope': '国学智慧四柱八字体验深化；分模块实施并逐轮通过完整回归后发布',
        'app_build_sha256': build, 'source_sha256': {p.relative_to(ROOT).as_posix(): digest(p) for p in sources},
        'engine': {'name': 'lunar-javascript', 'version': engine['version'], 'license': engine['license'], 'source_sha256': engine['sourceSha256']},
        'backup': {k: backup[k] for k in ['archive', 'archive_bytes', 'sha256', 'verified_files', 'baseline', 'scope']},
        'module_ledger': {'report': '06_验证与后续工作/国学智慧逐模块回归记录.json', 'report_sha256': digest(EVIDENCE / '国学智慧逐模块回归记录.json'), 'modules': modules},
        'verification': reports, 'numerical_verification': numeric, 'publication': publication,
        'glossary': {'current_entries': 25, 'historical_m3_entries': 20, 'basic_terms': 10, 'ten_gods': 10, 'auxiliary_terms': 5},
        'implemented': {
            'M1': ['当前节令年月与实际交节起止', '合法手选保留及回到当前', '当前模式档案跟随今天，手动模式恢复所选年月', '未出生、尚未起运及运表缺项提示'],
            'M2': ['本命四柱与所选大运、流年、流月七列对照', '以本命日主计算十神、十二长生等传统字段', '当前尚未起运时不假称已入运'],
            'M3': ['本命三行摘要及展开详细资料', '运年月概览与可展开七列', '20项词条（10基础术语与10具体十神），可点查看解释', '沿用现有弹层关闭与焦点返回'],
            'M4': ['胎元、胎息、八字命宫、八字身宫及其纳音', '与所选年份联动的小运及传统关系字段', '新增5项辅助术语解释，当前词典合计25项', '档案重算与导出保留真实计算结果'],
        },
        'failure_history': [{
            'type': 'real_product_bug', 'module': 3, 'status': 'fixed_and_retested',
            'problem': '手动选择2014未月时，顶部标签已切换，但起止区间仍误用今天的寒露至立冬。',
            'cause': issue['cause'], 'expected': issue['expectedTimePanel'], 'observed': issue['actualTimePanel'],
            'original_report': issue_path.relative_to(ROOT).as_posix(), 'observed_build': issue['observedBuildSha256'],
            'fix': '手动模式使用所选年份与月份的真实节令起止；当前模式才使用今天区间。',
            'verification': ['最终独立stage4四组', '最终本机及本地Cloudflare各60项', '最终公网八字stage4四组'],
            'regression_assertion': issue['regressionAssertion'],
        }],
        'limits': capability_limits,
        'no_production_data_write': True,
    }

    guide = f'''国学智慧体验深化使用与回退说明
更新时间：{stamp}
打开：{publication['url']}

当前年月与回看
计算出生资料后，默认定位今天所在的节令年与节令月。年界为立春，月界为十二“节”，全部按固定UTC+8实际交节时刻切换；一月小寒后的丑月仍属上一节令年。流月并不等同公历月份或农历月份日期。
选择大运、流年、流月后保持手动回看，可点“回到当前”恢复今天。重开已存档排盘会按存档UTC重算；保存时为当前模式的档案重新定位今天，手动模式的档案恢复所选大运、年份与月份。出生尚在未来、尚未实际起运或当前年份未列入运表时明确提示，不伪造当前大运。
大运年份段与虚岁沿用计算库口径；首次起运的具体时刻另列。起运当年在该时刻之前仍显示尚未起运，不能只用年份判断已经入运。

本命与七列对照
本命默认显示干支、天干十神、五行三行，其他藏干、地支十神、纳音、十二长生、旬与旬空可展开。当前运年月先显示概览，完整七列可展开并横向查看：四柱本命、大运、流年、流月。所选后三列均以同一本命日干为参照，不改变本命四柱。

术语解释
当前词典共25项：10个基础术语、10个具体十神与5个辅助术语。M3完成前20项，M4追加后5项，原历史记录保留。点击术语标题或十神值查看解释，关闭后保留当前排盘选择。十二长生中的“病、死”等是传统阶段名，不表示现实疾病、生死或寿命；五行仅是对应分类，没有旺衰分数、喜用神或自动补五行结论。每列旬空属于该柱自身所属旬，不自动判为与本命发生空亡关系。

辅助干支与小运
胎元、胎息、八字命宫及八字身宫由固定库公式计算，显示相应纳音。胎元、胎息不是实际受孕日期、孕期记录或健康判断；这里的命宫、身宫与紫微斗数十二宫结构分开使用。
小运由本命时柱按起运顺逆逐年推移，与按年度干支形成的流年分开显示，随所选年份查看，不生成运势断言。

资料、规则与范围
引擎为lunar-javascript {engine['version']}（MIT），许可随源码与构建保留。出生资料仍填写当地公历日期、钟表时间和IANA时区，再换算UTC及固定UTC+8；不校正真太阳时，不猜测未知时辰。晚子时日柱及起运算法沿用用户所选规则。
排盘档案只保存在当前浏览器并按账号隔离，最多20份，满额不静默删除；可重算及导出JSON，没有跨设备云同步或JSON导入。本轮未更改生产数据库、凭据、AI接入或老师服务。藏语仍待母语审校；浏览器测试不等同实机或传统解释有效性认证。

实际修复
M3真实问题：手动年月标签已切换，但顶部节令区间误用今天，现已改为所选年份、月份的真实交节区间，并在后续四阶段专项及完整回归增加断言。修复前截图、问题单及失败运行保留在06目录，详见本轮交付记录。

本轮验证与发布
四模块均先通过当轮本机与本地Cloudflare完整回归再推进；最终两套各{reports['local_full']['passed']}项、独立八字stage4 {reports['standalone_bazi_stage4']['passed']}组、三盘本机{reports['three_charts_local']['passed']}组及公网{reports['three_charts_public']['passed']}组、新八字公网{reports['public_bazi']['passed']}组通过，均核对最终构建。公网四个入口构建一致。
Sites版本：{publication['sites_version']}；Netlify部署：{publication['netlify_deploy_id']}；源码提交：{publication['source_commit']}。
公网八字仅使用合成出生资料进行客户端计算，不进行公网档案保存、删除或生产数据写入。
本轮APP SHA-256：{build}
完整实际结果：{RECORD}

回退
改前备份：{backup['archive']}
已校验文件数：{backup['verified_files']}；ZIP SHA-256：{backup['sha256']}。
备份不含依赖、运行数据库、凭据、私有环境变量或旧归档。回退时保留生产数据库及个人浏览器档案，核对备份SHA后恢复相应源码与构建，再重新构建、完整回归和发布，不直接覆盖业务数据。
改前公网：Sites版本{backup['baseline']['sites_version']}；Netlify部署{backup['baseline']['netlify_deploy_id']}；源码提交{backup['baseline']['source_commit']}。
本轮未重打完整项目ZIP；发布归档：{publication['archive']}，SHA-256：{archive_hash}。
'''
    notice = f'''### {date} 国学智慧体验深化已验证并发布
国学智慧现默认定位当前节令年月，支持合法手选保留与回到当前；当前模式档案重开按今天查看，手动模式恢复保存的所选年月；本命三行摘要可展开，完整七列对照以同一本命日主计算；词典共25项，含10个基础术语、10个具体十神与5个辅助术语（M3历史20项，M4追加5项）。新增胎元、胎息、八字命宫/身宫及纳音、小运，均为传统关系计算，不推断命运、人格或健康，不把胎元胎息当实际受孕日期，也不把八字命身宫当紫微十二宫。
四模块逐轮完整回归通过后推进。最终本机/本地Cloudflare各{reports['local_full']['passed']}项、独立八字stage4四组、三盘本机{reports['three_charts_local']['passed']}/公网{reports['three_charts_public']['passed']}、新增八字公网{reports['public_bazi']['passed']}与四入口构建核验通过；公网只做合成客户端计算，不保存或删改生产资料。M3手动年月顶部误用今天节期的真实问题已修复并增加断言，历史失败与截图保留。
改前{backup['verified_files']}文件已校验备份；Sites v{publication['sites_version']}、Netlify {publication['netlify_deploy_id']}，最终构建SHA-256为{build}。详细范围、边界、真实结果及回退见{GUIDE}与{RECORD}。档案仍为当前浏览器按账号保存，藏语待母语审校；未作实机、正式AI或解释体系有效性认证。本次不代表用户已认可最终视觉。'''

    # Build all text updates only after validation, before touching any delivery documents.
    updates = {RECORD: json_bytes(record), GUIDE: guide.encode('utf-8')}
    identity.update(previous_deploy_id=backup['baseline']['netlify_deploy_id'], deploy_id=publication['netlify_deploy_id'],
                    checked_at=stamp, status='deployed', latest_change='国学智慧八字体验深化：当前节令定位、七列对照、术语解释、辅助干支与小运',
                    latest_delivery_record=RECORD)
    updates['05_后台与研发说明/Netlify站点身份.json'] = json_bytes(identity)
    handoff = read('交接资料验证.json')
    previous_publication = handoff.get('latest_publication')
    if previous_publication and previous_publication.get('netlify_deploy_id') != publication['netlify_deploy_id']:
        handoff['previous_publication'] = previous_publication
    handoff.update(updated_beijing=stamp, local_regression_pass=True, regression_groups_passed=60, regression_groups_failed=0,
                   guoxue_wisdom_experience_deepening=record,
                   latest_publication={'at': public_build['at'], 'pass': True, **publication, 'delivery_record': RECORD, 'app_build_sha256': build})
    updates['交接资料验证.json'] = json_bytes(handoff)
    for name in ['AGENTS.md', '先读我.txt', '03_当前APP/功能与使用说明-R4.txt']:
        updates[name] = notice_text(project_path(name).read_text(encoding='utf-8'), notice).encode('utf-8')
    task_name = '改动任务表-2026-10-22.html'
    task = project_path(task_name).read_text(encoding='utf-8')
    section = f'''<section id="guoxue-wisdom-deepening"><h2>国学智慧体验深化（{html.escape(date)}）</h2><p>已发布：当前节令年月与回看、七列本命/运年月对照、25项术语解释、胎元胎息与八字命身宫及纳音、小运。保留地图4/4/3框架、玄金标题背景、逐级返回与自动计时。</p><p>四模块逐轮完整回归后推进；最终本机/本地Cloudflare各60项、独立stage4四组、三盘本机14/公网11、新八字公网四组及四入口构建一致。M3手选区间误用今天的真实问题已修复并增加断言。具体批次、截图、历史失败与最终构建见交付记录。</p><p>25词条指10基础术语+10具体十神+5辅助术语（M3历史20词保留）；辅助值不作受孕日期或健康判断，不生成运势、人格、喜用神结论。档案仅当前浏览器按账号保存，藏语待母语审校，未作实机或解释体系有效性认证。</p><p><a href="{html.escape(publication['url'], quote=True)}">打开国学智慧</a> · <a href="{GUIDE}">使用与回退</a> · <a href="{RECORD}">真实交付核验</a></p></section>'''
    pattern = r'<section id="guoxue-wisdom-deepening">[\s\S]*?</section>'
    if re.search(pattern, task):
        task, count = re.subn(pattern, lambda _: section, task)
        need(count == 1, 'Duplicate delivery sections in the task ledger')
    else:
        need('<footer>' in task, 'The existing task ledger has no insertion footer')
        task = task.replace('<footer>', section + '<footer>', 1)
    updates[task_name] = task.encode('utf-8')

    # Preserve source history; refresh the two existing authored-file manifests in place.
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', '.wrangler', '.sites-runtime', '.netlify', 'dist', '.next', '.vinext', '.cache', 'coverage'}
    skip_suffix = {'.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.pyc', '.log', '.db', '.pem', '.key', '.pfx', '.p12', '.tsbuildinfo'}
    skip_names = {'资料校验清单.csv', '原始来源与文件校验.json', 'desktop.ini', 'thumbs.db', '.ds_store'}
    paths = set(updates)
    for folder, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d.lower() not in skip_dirs and not (Path(folder) / d).is_symlink())
        for name in sorted(names):
            p = Path(folder) / name
            lower = name.lower()
            if p.is_symlink() or lower in skip_names or p.suffix.lower() in skip_suffix or any(x in lower for x in ['.sqlite', '.db-', '.env', '.dev.vars']):
                continue
            paths.add(p.relative_to(ROOT).as_posix())
    files = []
    for name in sorted(paths):
        p = project_path(name)
        data = updates.get(name)
        files.append({'path': name, 'bytes': len(data) if data is not None else p.stat().st_size,
                      'sha256': hashlib.sha256(data).hexdigest() if data is not None else digest(p)})
    manifest = read('原始来源与文件校验.json')
    manifest['files'] = files
    manifest['current_revision'] = {'updated_beijing': stamp, 'scope': '国学智慧四模块体验深化：当前定位、七列对照、术语解释、辅助干支及小运',
                                    'public_deployment_pending': False, 'delivery_record': RECORD, 'app_build_sha256': build,
                                    'source_commit': publication['source_commit']}
    manifest['manifest_excludes'] = ['资料校验清单.csv', '原始来源与文件校验.json', 'Dependency/build/cache/runtime directories',
                                    'Archives, runtime SQLite/DB and sidecars, credentials and private environment files']
    updates['原始来源与文件校验.json'] = json_bytes(manifest)
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['包内相对位置', '字节数', 'SHA-256'])
    writer.writerows((item['path'], item['bytes'], item['sha256']) for item in files)
    updates['资料校验清单.csv'] = buffer.getvalue().encode('utf-8-sig')
    for name, data in updates.items():
        project_path(name).write_bytes(data)
    for item in files:
        p = project_path(item['path'])
        need(p.stat().st_size == item['bytes'] and digest(p) == item['sha256'], 'Manifest post-write mismatch: ' + item['path'])
    need(read('原始来源与文件校验.json')['files'] == files, 'JSON manifest differs after writing')
    with (ROOT / '资料校验清单.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    need(rows[0] == ['包内相对位置', '字节数', 'SHA-256'], 'CSV manifest header differs')
    need(rows[1:] == [[item['path'], str(item['bytes']), item['sha256']] for item in files], 'CSV and JSON manifests differ')
    print(json.dumps({'pass': True, 'verified_authored_files': len(files), 'app_build_sha256': build,
                      'sites_version': publication['sites_version'], 'netlify_deploy_id': publication['netlify_deploy_id'],
                      'record': RECORD, 'guide': GUIDE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
