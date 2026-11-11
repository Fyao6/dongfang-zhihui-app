"""Validate this release's actual evidence before updating delivery documents.

The root agent reviews and executes this script after publication. Importing this
file has no side effects. This script never builds, publishes, changes credentials,
creates a complete project ZIP, or opens a runtime database.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import csv
import hashlib
import html
import io
import json
import os
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / '06_验证与后续工作'
WEB = ROOT / '03_当前APP'
R4 = ROOT / '04_研发源码/app/r4'
CLOUD = ROOT / '04_研发源码/app/cloud'
RECORD = '06_验证与后续工作/创作者APP功能对齐与数据中心交付记录.json'
GUIDE = '05_后台与研发说明/创作者与APP功能对齐及后台数据中心说明.txt'
LIFE_GUIDE = '05_后台与研发说明/生命地图生辰入口说明.txt'
LEDGER = '06_验证与后续工作/创作者精简与数据中心逐模块回归记录.json'
PUBLICATION = '06_验证与后续工作/创作者APP功能对齐与数据中心发布身份.json'
HEX64 = re.compile(r'^[0-9a-f]{64}$')
# User corrected the product scope after M2: rewrite final release prose after alignment.
FINAL_ALIGNMENT_TEXT_READY = True


def need(value, message):
    if not value:
        raise AssertionError(message)


def project_path(relative):
    path = ROOT / str(relative)
    need(path.resolve().is_relative_to(ROOT.resolve()), 'Path escapes project: ' + str(relative))
    need(not path.is_symlink(), 'Symlinks are not deliverable evidence: ' + str(relative))
    return path


def evidence_path(relative):
    text = str(relative).replace('\\', '/')
    path = project_path(text) if '/' in text else Q / text
    need(path.resolve().parent == Q.resolve(), 'Report must be in existing evidence directory: ' + text)
    need(path.is_file(), 'Required report is missing: ' + text)
    return path


def read(relative):
    return json.loads(project_path(relative).read_text(encoding='utf-8-sig'))


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def instant(value):
    value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    need(value.tzinfo is not None, 'Evidence time must specify a time zone')
    return value


def report_file(relative):
    path = evidence_path(relative)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    return path, data, data.get('latest', data)


def check_hashes(values, folder, label):
    need(isinstance(values, dict) and bool(values), label + ': missing hashes')
    for relative, expected in values.items():
        path = folder / relative
        need(path.resolve().is_relative_to(folder.resolve()), label + ': hash path escapes directory')
        need(isinstance(expected, str) and HEX64.fullmatch(expected), label + ': malformed digest ' + relative)
        need(path.is_file() and digest(path) == expected, label + ': current file differs: ' + relative)


def success(path, result, since):
    totals = result.get('totals', result)
    need(result.get('pass') is True, path.name + ': latest result is not passed')
    need(totals.get('failed', result.get('failed', 0)) == 0, path.name + ': failures remain')
    need(not result.get('errors') and not result.get('error'), path.name + ': runtime errors remain')
    at = result.get('at', result.get('executedAt', result.get('checked_beijing')))
    need(at and instant(at) >= since, path.name + ': evidence predates this work')
    passed = totals.get('passed')
    rows = result.get('results', result.get('checks', []))
    if passed is not None:
        need(isinstance(passed, int) and passed > 0, path.name + ': no successful assertions')
        if 'results' in result:
            need(len(result['results']) == passed, path.name + ': assertion count differs')
    need(rows, path.name + ': actual assertions are absent')
    for row in rows:
        if isinstance(row, dict):
            need(row.get('pass', row.get('passed', True)) is True, path.name + ': assertion failed')
    return at


def checked_report(relative, since, require_identity=True):
    path, data, result = report_file(relative)
    at = success(path, result, since)
    identified = False
    for key, folder in [('sourceHashes', ROOT), ('source_sha256', ROOT), ('buildHashes', WEB), ('cloudBuildHashes', CLOUD)]:
        if key in result:
            check_hashes(result[key], folder, path.name)
            identified = True
    if 'creatorSourceSha256' in result:
        need(result['creatorSourceSha256'] == digest(R4 / 'creator-center.html'), path.name + ': creator source differs')
        identified = True
    if isinstance(result.get('sourceSha256'), str):
        target = R4 / 'creator-center.html' if '创作者' in path.name else project_path(result.get('sourcePath', '__missing_source_path__'))
        need(target.is_file() and result['sourceSha256'] == digest(target), path.name + ': source identity differs or lacks sourcePath')
        identified = True
    for key in ['buildSha256', 'appBuildSha256', 'app_build_sha256', 'localAppSha256']:
        if key in result:
            need(result[key] == digest(WEB / '东方智慧-首页体验R4.html'), path.name + ': APP build differs')
            identified = True
    need(identified or not require_identity, path.name + ': missing current source/build identity')
    summary = {'report': path.relative_to(ROOT).as_posix(), 'report_sha256': digest(path), 'at': at,
               'pass': True, 'failed': 0, 'checks': len(result.get('results', result.get('checks', [])))}
    for key in ['module', 'passed', 'scope', 'mode', 'cloudWorker', 'readOnly', 'noProductionDataWrite']:
        if key in result:
            summary[key] = result[key]
    return path, data, result, summary


def notice_text(old, text):
    start, end = '<!-- creator-analytics-delivery:start -->', '<!-- creator-analytics-delivery:end -->'
    block = start + '\n' + text.strip() + '\n' + end
    if start in old:
        need(old.count(start) == 1 and old.count(end) == 1, 'Malformed delivery notice markers')
        return old[:old.index(start)] + block + old[old.index(end) + len(end):]
    return old.rstrip() + '\n\n' + block + '\n'


def replace_section(text, identifier, section, insertion):
    pattern = r'<section id="' + re.escape(identifier) + r'">[\s\S]*?</section>'
    if re.search(pattern, text):
        text, count = re.subn(pattern, lambda _: section, text)
        need(count == 1, 'Duplicate section: ' + identifier)
        return text
    need(insertion in text, 'Missing insertion anchor for ' + identifier)
    return text.replace(insertion, section + insertion, 1)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    need(FINAL_ALIGNMENT_TEXT_READY, 'Final creator-to-APP alignment text is not reviewed; do not record the abandoned simplified direction')
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    date = stamp[:10]
    app_hash = digest(WEB / '东方智慧-首页体验R4.html')
    creator_hash = digest(R4 / 'creator-center.html')
    backup = read('06_验证与后续工作/创作者精简与数据中心改前备份核验.json')
    need(backup.get('pass') is True, 'Pre-change backup was not verified')
    since = instant(backup.get('checked_beijing', backup.get('at')))
    backup_archive = project_path(backup['archive'])
    need(backup_archive.is_file() and digest(backup_archive) == backup['archive_sha256'], 'Pre-change backup differs')
    need(backup_archive.stat().st_size == backup['archive_bytes'], 'Pre-change archive size differs')
    need(len(backup['files']) == backup['verified_files'], 'Backup verified-file count differs')

    # Historical module gates use their exact timestamped runs, never a later "latest" result.
    ledger = read(LEDGER)
    modules = ledger.get('modules', [])
    need(len(modules) >= 4 and [module.get('module') for module in modules] == list(range(1, len(modules) + 1)), 'Sequential module gates 1 through N are required')
    previous_completed = since
    failures = []
    for module in modules:
        number = module['module']
        need(module.get('pass') is True, 'Module ' + str(number) + ' did not pass')
        completed = instant(module['completed_beijing'])
        need(completed >= previous_completed, 'Module order is inconsistent')
        need(module.get('source_sha256') and module.get('build_sha256'), 'Module identity is incomplete')
        for kind in ['python', 'cloudflare']:
            reference = module['checks'][kind]
            path, data, latest = report_file(reference['report'])
            runs = list(data.get('runs', [])) + [latest]
            matched = [run for run in runs if run.get('at') == reference['at'] and run.get('module') == reference['module']]
            need(matched, 'Module ' + str(number) + ': actual ' + kind + ' run is absent')
            result = matched[-1]
            actual_at = success(path, result, previous_completed)
            need(instant(actual_at) <= completed, 'Module run occurred after its completion')
            need(result.get('passed') == reference['passed'] and reference['failed'] == 0, 'Ledger assertion counts disagree')
            if kind == 'cloudflare':
                need(result.get('cloudWorker') is True, 'The cloud gate is not an actual local Worker run')
            for name, value in result.get('buildHashes', {}).items():
                key = '03_当前APP/' + name
                need(module['build_sha256'].get(key) == value, 'Module ledger and tested build differ: ' + key)
            for run in data.get('runs', []):
                if run.get('at') and instant(run['at']) >= since and run.get('pass') is False:
                    item = {'report': path.relative_to(ROOT).as_posix(), 'at': run['at'],
                            'module': run.get('module'), 'failed': run.get('failed'), 'status': 'historical_failed_run_retained'}
                    if item not in failures:
                        failures.append(item)
        previous_completed = completed
    check_hashes(modules[-1]['source_sha256'], ROOT, 'Final module source')
    check_hashes(modules[-1]['build_sha256'], ROOT, 'Final module builds')
    need(modules[-1]['build_sha256'].get('03_当前APP/东方智慧-首页体验R4.html') == app_hash, 'Final APP differs from module gate')

    reports = {}
    for key, filename in [('local_full', '本轮全量回归结果.json'), ('cloudflare_full', '公网适配全量回归结果.json')]:
        _, _, result, reports[key] = checked_report(filename, since)
        need(result.get('module') == modules[-1]['checks']['python' if key == 'local_full' else 'cloudflare']['module'], 'Latest full report belongs to another module')
        need(result.get('buildHashes', {}).get('东方智慧-首页体验R4.html') == app_hash, 'Final full report tests another APP')
        if key == 'cloudflare_full':
            need(result.get('cloudWorker') is True, 'Final Cloudflare test did not use Worker runtime')

    # M1/M2 references preserve historical evidence; final alignment uses new current reports.
    specialties = {}
    for module in modules:
        specialties.update(module.get('specialty', {}))
    historical_specialties = {}
    for key in ['creator_ui_local', 'creator_ui_cloud', 'creator_real_local', 'creator_real_cloud']:
        reference = modules[0].get('specialty', {}).get(key)
        if not reference:
            continue
        path, _, result = report_file(reference)
        at = success(path, result, since)
        historical_specialties[key] = {'report': path.relative_to(ROOT).as_posix(), 'report_sha256': digest(path),
                                       'at': at, 'pass': True, 'scope': 'Historical earlier-stage result; not the final product proof'}
    for key in ['creator_alignment_ui', 'creator_alignment_local', 'creator_alignment_cloud', 'creator_saved_exact',
                'life_birth_local', 'life_birth_cloud', 'charts_local']:
        need(specialties.get(key), 'Missing final specialty reference: ' + key)
        _, _, result, reports[key] = checked_report(specialties[key], since)
        if key in ['creator_alignment_local', 'creator_alignment_cloud']:
            need(result.get('mode') == ('cloud' if key.endswith('_cloud') else 'python'), 'Creator real workflow tested the wrong runtime: ' + key)
        if key == 'life_birth_cloud':
            need(result.get('base') == 'http://127.0.0.1:8877' and result.get('remote') is False, 'Life cloud workflow did not use the actual local Worker')
            need(specialties['life_birth_cloud'] != specialties['life_birth_local'], 'Life cloud/local proof must be distinct actual runs')
        if key in ['life_birth_local', 'life_birth_cloud']:
            need(result.get('syntheticClientOnly') is True and not result.get('birthRequests'),
                 'Life-entry checks must not submit birth data over the network')
    _, _, _, reports['analytics_exact'] = checked_report(specialties.get('analytics_exact', '后台数据中心确定性核验.json'), since)
    need(project_path(LIFE_GUIDE).is_file(), 'The life birth-entry usage guide is missing')

    supplied = read(PUBLICATION)
    required = ['project_id', 'source_commit', 'sites_version', 'sites_version_id', 'sites_deployment_id', 'sites_status',
                'netlify_site_id', 'netlify_deploy_id', 'netlify_status', 'archive', 'url',
                'public_build_match_report', 'public_acceptance_report']
    for key in required:
        need(key in supplied and supplied[key] not in [None, ''], 'Missing actual publication field: ' + key)
    publication = {key: supplied[key] for key in required}
    need(publication['sites_status'] == 'succeeded' and publication['netlify_status'] == 'ready', 'Publication has not succeeded')
    need(isinstance(publication['sites_version'], int) and publication['sites_version'] > 0, 'Invalid Sites version')
    need(re.fullmatch(r'[0-9a-f]{40}', publication['source_commit']), 'Invalid actual source commit')
    hosting = json.loads((CLOUD / '.openai/hosting.json').read_text(encoding='utf-8'))
    identity = read('05_后台与研发说明/Netlify站点身份.json')
    need(publication['project_id'] == hosting['project_id'], 'Publication points to another Sites project')
    need(publication['netlify_site_id'] == identity['site_id'], 'Publication points to another Netlify site')
    public_origin = urlparse(publication['url'])
    need(public_origin.scheme == 'https' and public_origin.netloc == urlparse(identity['url']).netloc, 'Public origin differs')
    origin = public_origin.scheme + '://' + public_origin.netloc
    archive = project_path(publication['archive'])
    need(archive.is_file(), 'Actual deployment archive is absent')
    publication['archive_sha256'] = digest(archive)
    if supplied.get('archive_sha256'):
        need(supplied['archive_sha256'] == publication['archive_sha256'], 'Deployment archive digest differs')

    extra = {**specialties, **supplied.get('additional_reports', {})}
    # The producer may choose filenames; required semantic keys make missing work explicit.
    for key in ['analytics_ui_local', 'analytics_real_local', 'analytics_real_cloud']:
        need(extra.get(key), 'Supply additional_reports or module specialty reference: ' + key)
        _, _, result, reports[key] = checked_report(extra[key], since)
        need(result.get('mode') == ('cloud' if key.endswith('_cloud') else 'python'), 'Analytics real workflow tested the wrong runtime: ' + key)
    _, _, public_build, reports['public_build'] = checked_report(publication['public_build_match_report'], since)
    need(public_build.get('localAppSha256') == app_hash, 'Public APP build differs')
    need(public_build.get('netlifyDeployId') == publication['netlify_deploy_id'], 'Public Netlify deployment differs')
    need(public_build.get('sourceCommit') == publication['source_commit'] and public_build.get('sitesVersion') == publication['sites_version'], 'Public source/version differs')
    checks = public_build.get('checks', [])
    need({check.get('route') for check in checks} == {'/experience', '/creator', '/admin', '/', '/app'}, 'All five public routes must be checked')
    for check in checks:
        expected = check.get('expectedNormalizedSha256', '')
        need(isinstance(expected, str) and HEX64.fullmatch(expected), 'Public route digest is absent')
        need(check.get('origin') == origin and check.get('status') == 200 and check.get('generatedMatch') is True,
             'Public route was not verified against the generated page')
        need(check.get('servedNormalizedSha256') == expected, 'Public HTML differs from the deployed build')
        generated_name = {'/': 'experience.html', '/experience': 'experience.html', '/creator': 'creator.html', '/admin': 'admin.html', '/app': 'review.html'}[check['route']]
        generated = (CLOUD / 'generated' / generated_name).read_text(encoding='utf-8').replace('\r\n', '\n')
        generated = re.sub(r'\n<!-- This site is hosted on Netlify\.[\s\S]*?-->', '', generated)
        need(hashlib.sha256(generated.encode('utf-8')).hexdigest() == expected, 'Public report targets an earlier generated page: ' + check['route'])
    _, _, public_result, reports['public_acceptance'] = checked_report(publication['public_acceptance_report'], since)
    need(public_result.get('origin') == origin and public_result.get('netlifyDeployId') == publication['netlify_deploy_id'] and public_result.get('sourceCommit') == publication['source_commit'], 'Public acceptance belongs to another origin/deployment/source')
    need(public_result.get('readOnly') is True or public_result.get('noProductionDataWrite') is True,
         'Public acceptance must explicitly identify its read-only/no-write scope')

    # Source, local browser entry and cloud generated creator page stay tied to this revision.
    need(digest(WEB / '创作者中心.html') == creator_hash, 'Local creator entry differs from creator source')
    app = (WEB / '东方智慧-首页体验R4.html').read_text(encoding='utf-8')
    review = (WEB / '发给负责人-东方智慧首页R4.html').read_text(encoding='utf-8')
    embedded, _ = json.JSONDecoder().raw_decode(review.split('const APP=', 1)[1])
    need(embedded.replace('__INITIAL__', '{}') == app, 'Review entry embeds another APP')
    need((R4 / 'creator-app.js').read_text(encoding='utf-8') in app, 'Current creator APP integration is absent from build')

    limits = ['仅从统计启用时间起记录真实APP活动，不反推或补造历史活跃。',
              '活跃按已登录user/teacher账号去重；匿名浏览器与公司后台操作不计入账号活跃。',
              '自然周从周一开始，全部边界按Asia/Shanghai；周/月/年不能将每日人数相加。',
              '留存只含采集启用后注册且观察日已完整结束的样本，未成熟样本不显示虚假比例。',
              'CSV只导出汇总，不包含账号标识、私聊、自评、出生或排盘资料。',
              '共享出生资料和原排盘档案仅在当前浏览器按账号保存；时间未知不生成近似命盘，不上传出生资料。',
              '创作者收藏以当前账号服务端记录为准，原有平台本机收藏不冒充全历史云同步。',
              '没有迁移生产业务数据或更改原登录username、认证及推荐权限。',
              '浏览器检查不等同实机；正式AI、硬件及外部服务依赖原配置与独立验收。']
    record = {'checked_beijing': stamp, 'pass': True,
              'scope': '成熟创作者中心与APP功能接口对齐、公司后台数据中心、生命地图强制出生入口及自动排盘；分模块逐轮完整回归后发布',
              'app_build_sha256': app_hash, 'creator_source_sha256': creator_hash,
              'source_sha256': modules[-1]['source_sha256'], 'build_sha256': modules[-1]['build_sha256'],
              'backup': {key: backup[key] for key in ['archive', 'archive_bytes', 'archive_sha256', 'verified_files', 'scope']},
              'module_ledger': {'report': LEDGER, 'report_sha256': digest(project_path(LEDGER)), 'modules': modules},
              'verification': reports, 'historical_specialty_evidence': historical_specialties, 'publication': publication, 'historical_failed_runs': failures,
              'implemented': {
                  'creator': ['保留成熟工作台主辅结构、发布/审核/作品/互动咨询/账号和12类本人真实指标',
                              '按作品类型显示适用指标，账号汇总/逐日/作品CSV真实导出并防注入',
                              'APP服务端收藏进入我的收藏及我的课程，详情/导读同一收藏来源且按账号隔离',
                              '实际章节阅读计学习、作者页作品曝光、短视频有效90%完播回流',
                              '作者/视频/老师/课程公开资料同源，认证推荐与登录username保持平台权限',
                              '作者页进入已有真实老师咨询需求；审核撤回申诉及素材归属仍强制校验',
                              '旧图文媒体、隐藏分类与双语章节保存保留；分享口径为访客作品去重有效记录'],
                  'admin_analytics': ['今日/本自然周/本自然月/本自然年活跃账号去重',
                                      '日周月年趋势、真实新增及功能使用',
                                      '次日/七日成熟队列留存、采集覆盖与历史缺口标记',
                                      '管理员/运营权限及汇总CSV导出'],
                  'life_birth_entry': ['生命地图及三盘深链先校验已实际保存的共享出生资料，无跳过入口',
                                       '生日及性别必填，姓名/出生时间可选，资料按浏览器账号隔离',
                                       '已知准确时间保存后立即自动生成紫微，三套入口共享同一出生资料',
                                       '时间未知仅显示日期基础信息，不填默认时辰、不生成近似命盘',
                                       '在线身份加载前不闪现游客资料，删除或更改资料时旧盘不能绕过入口',
                                       '原有已保存完整排盘档案仍可独立复算，出生资料不发往服务器']},
              'limits': limits, 'no_production_data_migration': True, 'complete_project_zip_repacked': False}
    local_count, cloud_count = reports['local_full'].get('passed'), reports['cloudflare_full'].get('passed')
    notice = f"""### {date} 创作者APP功能对齐、后台数据中心与生命地图出生入口已验证并发布
创作者保留成熟工作台及12类真实指标，去掉重复宣传与没有对应APP业务的工具。视频/图文/课程发布、审核、申诉、咨询和账号管理完整保留；服务端收藏真实进入APP我的收藏/课程，课程导读学习、作者作品曝光、循环短视频90%有效观看均回流统计。公开作者资料在视频、老师、课程和作者主页同源，账号切换不会混入旧收藏或旧观看，登录username和认证推荐权限不变。有效分享按同访客同作品记录去重，不冒充每次重复分享次数。
公司总后台数据中心按北京时间显示今日/本自然周/本自然月/本自然年去重活跃、日周月年趋势、新增、功能使用、成熟次日/七日留存及汇总CSV。匿名和公司后台操作不计账号活跃；从启用开始实际采集，历史缺口与未成熟样本不造数。
生命地图及三盘深链必须先实际保存共享出生资料；生日、性别必填，出生时间可选。准确时间保存后立即自动生成紫微并供三盘复用；时间未知只显示日期基础信息，不猜时辰或造近似盘。共享资料在当前浏览器按账号隔离，不上传出生资料，原有完整排盘档案继续可复算。
各模块先通过当轮完整回归再推进；最终本机{local_count}项/本地Cloudflare {cloud_count}项、创作者与APP实际闭环、后台数据中心、共享生辰入口及三盘专项与公网只读验收通过，五入口构建一致。历史阶段及失败运行保留。Sites v{publication['sites_version']}，Netlify {publication['netlify_deploy_id']}；APP SHA-256 {app_hash}。
实际接口/APP入口/指标矩阵见{GUIDE}，出生入口详见{LIFE_GUIDE}，证据见{RECORD}。本轮未重打完整项目ZIP；现有ZIP保留其原快照时间。浏览器测试不等同实机、正式AI或其他外部服务已接通，本次不代表用户已认可最终视觉。"""
    updates = {RECORD: json_bytes(record)}
    guide = project_path(GUIDE).read_text(encoding='utf-8')
    guide = guide.replace('模块1、2的阶段回归属于各自当时构建；用户随后纠正方向，模块3已恢复成熟工作台并补齐APP链路。本文记录当前实现与接口约定，最终整套回归、真实闭环、公网发布状态以本轮最终交付记录为准；不能将旧“精简界面通过”写为最终产品验收。此稿尚未表示本轮最终版本已经发布。',
                          f'本轮当前源码与构建已完成实际验证并发布，最终本机{local_count}项、本地Cloudflare {cloud_count}项完整回归通过；实际闭环、当前构建、历史失败与发布身份见{RECORD}。旧阶段报告仅证明当时状态，不能替代最终版本。')
    guide = guide.replace('模块3及后续最终完整回归、公网构建一致性、最终发布身份，由根代理完成后记录；未通过的中间运行保留，不用历史通过替代本次当前构建。',
                          f'最终完整回归、实际专项及五入口公网构建一致性已经核对当前版本；真实发布身份、哈希与历史失败详见{RECORD}。')
    guide = notice_text(guide, notice + f'\n共享出生资料的具体使用与限制另见{LIFE_GUIDE}。')
    updates[GUIDE] = guide.encode('utf-8')
    life_notice = f'### {date} 本轮最终交付状态\n已发布；本机{local_count}项、本地Cloudflare {cloud_count}项完整回归、生辰入口及三盘专项和公网只读验收均已核对当前构建。准确时间保存即自动紫微，未知时间不猜盘；具体实际结果、哈希、历史失败及发布身份见{RECORD}。'
    updates[LIFE_GUIDE] = notice_text(project_path(LIFE_GUIDE).read_text(encoding='utf-8'), life_notice).encode('utf-8')
    for name in ['AGENTS.md', '先读我.txt', '交付包说明.txt', '03_当前APP/功能与使用说明-R4.txt']:
        updates[name] = notice_text(project_path(name).read_text(encoding='utf-8'), notice).encode('utf-8')
    section_id = 'creator-app-alignment-analytics-life-birth'
    section = f'<section id="{section_id}"><h2>创作者APP功能对齐、数据中心与生命入口（{date}）</h2><p>已发布：成熟创作者工作台及12类真实数据与APP收藏/课程学习/作者/咨询联调；公司后台日周月年活跃、趋势、功能使用、成熟留存及汇总导出。生命地图强制保存共享出生资料，准确时间保存即生成紫微，时间未知不猜时辰、不造盘。</p><p>各模块逐轮整套回归通过后推进；最终本机{local_count}项、本地Cloudflare {cloud_count}项和本轮专项、公网只读检查通过。统计从启用起采集，不补造历史活跃；账号去重，匿名和公司管理操作不计活跃。</p><p><a href="{html.escape(origin + "/creator", quote=True)}">创作者中心</a> · <a href="{html.escape(origin + "/admin", quote=True)}">公司后台数据中心</a> · <a href="{GUIDE}">使用与统计口径</a> · <a href="{RECORD}">本轮实际交付记录</a></p></section>'
    task_name = '改动任务表-2026-10-22.html'
    updates[task_name] = replace_section(project_path(task_name).read_text(encoding='utf-8'), section_id, section, '<footer>').encode('utf-8')
    opening = project_path('打开这里.html').read_text(encoding='utf-8')
    latest = f'<section id="current-delivery-package"><h1>当前项目更新 · {date}</h1><p>Sites v{publication["sites_version"]}；创作者与APP功能对齐、公司后台数据中心及生命地图出生入口已发布，最终本机{local_count}项、本地Cloudflare {cloud_count}项完整回归及本轮专项通过。</p><p><a href="{origin}/experience">APP</a> · <a href="{origin}/creator">创作者中心</a> · <a href="{origin}/admin">公司后台与数据中心</a> · <a href="03_当前APP/发给负责人-东方智慧首页R4.html">离线负责人查看页</a></p><p><a href="{GUIDE}">使用及统计口径</a> · <a href="{RECORD}">本轮真实交付记录</a> · <a href="资料校验清单.csv">当前文件校验清单</a></p><p>本轮未重打完整项目ZIP；现有压缩包保留其原打包时间。下方旧说明作历史记录，当前状态以本节与本轮交付记录为准。</p></section>'
    updates['打开这里.html'] = replace_section(opening, 'current-delivery-package', latest, '<h1>').encode('utf-8')
    previous = identity.get('deploy_id')
    if previous != publication['netlify_deploy_id']:
        identity['previous_deploy_id'] = previous
    identity.update(deploy_id=publication['netlify_deploy_id'], checked_at=stamp, status='deployed',
                    latest_change='创作者APP功能对齐、后台数据中心与生命地图共享出生入口', latest_delivery_record=RECORD)
    updates['05_后台与研发说明/Netlify站点身份.json'] = json_bytes(identity)
    handoff = read('交接资料验证.json')
    previous_publication = handoff.get('latest_publication')
    if previous_publication and previous_publication.get('netlify_deploy_id') != publication['netlify_deploy_id']:
        handoff['previous_publication'] = previous_publication
    handoff.update(updated_beijing=stamp, local_regression_pass=True, regression_groups_passed=local_count,
                   regression_groups_failed=0, creator_app_alignment_analytics_and_life_birth=record,
                   latest_publication={'pass': True, **publication, 'delivery_record': RECORD, 'app_build_sha256': app_hash})
    updates['交接资料验证.json'] = json_bytes(handoff)

    # Refresh existing manifests in place, excluding credentials, databases and generated dependency trees.
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', '.wrangler', '.sites-runtime', '.netlify', 'dist', '.next', '.vinext', '.cache', 'coverage'}
    skip_suffix = {'.zip', '.7z', '.rar', '.tar', '.gz', '.tgz', '.pyc', '.log', '.db', '.pem', '.key', '.pfx', '.p12', '.tsbuildinfo'}
    skip_names = {'资料校验清单.csv', '原始来源与文件校验.json', 'desktop.ini', 'thumbs.db', '.ds_store'}
    paths = set(updates)
    for folder, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(name for name in dirs if name.lower() not in skip_dirs and not (Path(folder) / name).is_symlink())
        for name in sorted(names):
            path = Path(folder) / name
            lower = name.lower()
            if path.is_symlink() or lower in skip_names or path.suffix.lower() in skip_suffix or any(value in lower for value in ['.sqlite', '.db-', '.env', '.dev.vars']):
                continue
            paths.add(path.relative_to(ROOT).as_posix())
    files = []
    for name in sorted(paths):
        path = project_path(name)
        data = updates.get(name)
        files.append({'path': name, 'bytes': len(data) if data is not None else path.stat().st_size,
                      'sha256': hashlib.sha256(data).hexdigest() if data is not None else digest(path)})
    manifest = read('原始来源与文件校验.json')
    manifest['files'] = files
    manifest['current_revision'] = {'updated_beijing': stamp, 'scope': '创作者APP功能接口对齐、公司后台数据中心与生命地图共享出生入口',
                                    'public_deployment_pending': False, 'delivery_record': RECORD,
                                    'app_build_sha256': app_hash, 'source_commit': publication['source_commit']}
    manifest['manifest_excludes'] = ['资料校验清单.csv', '原始来源与文件校验.json', 'Dependency/build/cache/runtime directories',
                                    'Archives, runtime SQLite/DB and sidecars, credentials and private environment files']
    updates['原始来源与文件校验.json'] = json_bytes(manifest)
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['包内相对位置', '字节数', 'SHA-256'])
    writer.writerows((item['path'], item['bytes'], item['sha256']) for item in files)
    updates['资料校验清单.csv'] = buffer.getvalue().encode('utf-8-sig')
    # All gates above must succeed before the first delivery-document mutation.
    for name, data in updates.items():
        project_path(name).write_bytes(data)
    for item in files:
        path = project_path(item['path'])
        need(path.stat().st_size == item['bytes'] and digest(path) == item['sha256'], 'Post-write manifest mismatch: ' + item['path'])
    need(read('原始来源与文件校验.json')['files'] == files, 'JSON manifest differs')
    with project_path('资料校验清单.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.reader(stream))
    need(rows[1:] == [[item['path'], str(item['bytes']), item['sha256']] for item in files], 'CSV manifest differs')
    print(json.dumps({'pass': True, 'verified_authored_files': len(files), 'app_build_sha256': app_hash,
                      'creator_source_sha256': creator_hash, 'sites_version': publication['sites_version'],
                      'netlify_deploy_id': publication['netlify_deploy_id'], 'record': RECORD, 'guide': GUIDE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
