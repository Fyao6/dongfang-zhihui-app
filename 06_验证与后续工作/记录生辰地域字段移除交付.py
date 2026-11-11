"""Record this one-module change only after current tests and publication pass.

Preparation/import has no side effects. Root reviews the final calculation note,
sets FINAL_RECORD_READY, and runs this after publication. No build, deployment,
database, credential, archive or application-code mutation is performed here.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import csv
import hashlib
import html
import types
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
RECORD = '06_验证与后续工作/生辰地域字段移除交付记录.json'
PUBLICATION = '06_验证与后续工作/生辰地域字段移除发布身份.json'
BACKUP = '06_验证与后续工作/出生资料去除地域字段前备份核验.json'
LEDGER = '06_验证与后续工作/出生资料地域字段移除回归记录.json'
GUIDE = '05_后台与研发说明/生命地图生辰入口说明.txt'
FINAL_RECORD_READY = True
# Root fills this with the actual implementation's fixed reference / missing-data
# behavior. Never describe an internal default as the user's detected birthplace.
CALCULATION_REFERENCE_NOTE = '新建共享生辰内部固定使用Etc/GMT-8（UTC+08:00北京时间，不使用Asia/Shanghai历史夏令时），出生地、城市、时区选择及经纬度均无用户入口，地域/位置值留空，不自动定位或猜出生地。普通编辑既有共享资料保留其原有内部地域参数以兼容原计算，但新建资料绝不继承这些旧值；完整旧排盘档案仍按自身已存UTC和规则独立复算。新资料没有出生地点，西方页仅提供日期参考与笔记，不生成完整西方宫位，也不提示用户补填地点。'

# Reuse the established read-only evidence/path/hash helpers, without invoking its main.
prior_path = Q / '记录创作者APP功能对齐与数据中心交付.py'
prior = types.ModuleType('_prior_release_evidence')
prior.__file__ = str(prior_path)
exec(compile(prior_path.read_text(encoding='utf-8'), str(prior_path), 'exec'), prior.__dict__)
need, project_path, digest, json_bytes = prior.need, prior.project_path, prior.digest, prior.json_bytes
instant, read, report_file, checked_report = prior.instant, prior.read, prior.report_file, prior.checked_report
check_hashes, replace_section = prior.check_hashes, prior.replace_section


def notice_text(old, text):
    start, end = '<!-- birth-geography-removal:start -->', '<!-- birth-geography-removal:end -->'
    block = start + '\n' + text.strip() + '\n' + end
    if start in old:
        need(old.count(start) == old.count(end) == 1, 'Malformed release notice markers')
        return old[:old.index(start)] + block + old[old.index(end) + len(end):]
    return old.rstrip() + '\n\n' + block + '\n'


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    need(FINAL_RECORD_READY, 'Root must review final evidence and release prose before recording completion')
    need(CALCULATION_REFERENCE_NOTE.strip(), 'The actual fixed calculation reference / missing-data behavior is not documented')
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    date = stamp[:10]
    app_hash = digest(WEB / '东方智慧-首页体验R4.html')
    backup = read(BACKUP)
    need(backup.get('pass') is True, 'This round backup was not verified')
    since = instant(backup['checked_beijing'])
    archive_before = project_path(backup['archive'])
    need(archive_before.is_file() and digest(archive_before) == backup['archive_sha256'], 'This round backup archive differs')
    need(archive_before.stat().st_size == backup['archive_bytes'], 'Backup archive size differs')
    need(len(backup['files']) == backup['verified_files'], 'Backup verified-file count differs')

    ledger = read(LEDGER)
    modules = ledger.get('modules', [])
    need(len(modules) == 1 and modules[0].get('module') == 1 and modules[0].get('pass') is True,
         'This release requires its own single completed module ledger')
    module = modules[0]
    completed = instant(module['completed_beijing'])
    need(completed >= since, 'Module completion predates this round')
    check_hashes(module['source_sha256'], ROOT, 'Current single-module source')
    check_hashes(module['build_sha256'], ROOT, 'Current single-module build')
    need(module['build_sha256'].get('03_当前APP/东方智慧-首页体验R4.html') == app_hash, 'Module APP differs from current build')
    reports, failed_runs = {}, []
    for kind, key in [('python', 'local_full'), ('cloudflare', 'cloudflare_full')]:
        reference = module['checks'][kind]
        path, data, result, reports[key] = checked_report(reference['report'], since)
        need(result.get('at') == reference['at'] and result.get('module') == reference['module'],
             'Latest full report does not identify this module run: ' + kind)
        need(result.get('passed') == reference['passed'] and reference['failed'] == 0, 'Ledger assertion counts disagree')
        need(instant(result['at']) <= completed, 'Full run occurred after module completion')
        need(result.get('buildHashes', {}).get('东方智慧-首页体验R4.html') == app_hash, 'Full run tests another APP')
        if kind == 'cloudflare':
            need(result.get('cloudWorker') is True, 'Cloud full run must use actual local Worker runtime')
        for run in data.get('runs', []):
            if run.get('at') and instant(run['at']) >= since and run.get('pass') is False:
                failed_runs.append({'report': path.relative_to(ROOT).as_posix(), 'at': run['at'],
                                    'module': run.get('module'), 'failed': run.get('failed')})
    for key in ['birth_local', 'birth_cloud', 'charts_local']:
        reference = module.get('specialty', {}).get(key)
        need(reference, 'Current specialty reference is missing: ' + key)
        _, _, result, reports[key] = checked_report(reference, since)
        if key.startswith('birth_'):
            need(result.get('syntheticClientOnly') is True and not result.get('birthRequests'),
                 'Birth-entry test must keep synthetic birth data out of server requests')
    if module.get('specialty', {}).get('charts_cloud'):
        _, _, _, reports['charts_cloud'] = checked_report(module['specialty']['charts_cloud'], since)

    supplied = read(PUBLICATION)
    required = ['project_id', 'source_commit', 'sites_version', 'sites_version_id', 'sites_deployment_id', 'sites_status',
                'netlify_site_id', 'netlify_deploy_id', 'netlify_status', 'archive', 'url',
                'public_build_match_report', 'public_acceptance_report']
    for key in required:
        need(key in supplied and supplied[key] not in [None, ''], 'Missing actual publication field: ' + key)
    publication = {key: supplied[key] for key in required}
    need(publication['sites_status'] == 'succeeded' and publication['netlify_status'] == 'ready', 'Publication has not succeeded')
    need(isinstance(publication['sites_version'], int) and publication['sites_version'] > 0, 'Invalid Sites version')
    need(re.fullmatch(r'[0-9a-f]{40}', publication['source_commit']), 'Invalid actual pushed source commit')
    hosting = json.loads((CLOUD / '.openai/hosting.json').read_text(encoding='utf-8'))
    identity = read('05_后台与研发说明/Netlify站点身份.json')
    need(publication['project_id'] == hosting['project_id'], 'Publication points to another Sites project')
    need(publication['netlify_site_id'] == identity['site_id'], 'Publication points to another Netlify site')
    parsed = urlparse(publication['url'])
    need(parsed.scheme == 'https' and parsed.netloc == urlparse(identity['url']).netloc, 'Public origin differs')
    origin = parsed.scheme + '://' + parsed.netloc
    deploy_archive = project_path(publication['archive'])
    need(deploy_archive.is_file(), 'Actual deployment archive is missing')
    publication['archive_sha256'] = digest(deploy_archive)
    if supplied.get('archive_sha256'):
        need(supplied['archive_sha256'] == publication['archive_sha256'], 'Deployment archive digest differs')
    _, _, public_build, reports['public_build'] = checked_report(publication['public_build_match_report'], since)
    need(public_build.get('localAppSha256') == app_hash, 'Public APP build differs from this round')
    need(public_build.get('netlifyDeployId') == publication['netlify_deploy_id'] and
         public_build.get('sourceCommit') == publication['source_commit'] and
         public_build.get('sitesVersion') == publication['sites_version'], 'Public source/deployment identities differ')
    checks = public_build.get('checks', [])
    need({row.get('route') for row in checks} == {'/', '/experience', '/app', '/creator', '/admin'},
         'Five current public viewing routes must match')
    for row in checks:
        expected = row.get('expectedNormalizedSha256', '')
        need(re.fullmatch(r'[0-9a-f]{64}', expected), 'Public page digest is missing')
        need(row.get('origin') == origin and row.get('status') == 200 and row.get('generatedMatch') is True and
             row.get('servedNormalizedSha256') == expected, 'Public page differs from current generated source')
        filename = {'/': 'experience.html', '/experience': 'experience.html', '/app': 'review.html', '/creator': 'creator.html', '/admin': 'admin.html'}[row['route']]
        current = (CLOUD / 'generated' / filename).read_text(encoding='utf-8').replace('\r\n', '\n')
        current = re.sub(r'\n<!-- This site is hosted on Netlify\.[\s\S]*?-->', '', current)
        need(hashlib.sha256(current.encode('utf-8')).hexdigest() == expected, 'Public report tests an earlier generated page: ' + row['route'])
    _, _, public_result, reports['public_acceptance'] = checked_report(publication['public_acceptance_report'], since)
    need(public_result.get('origin') == origin and public_result.get('netlifyDeployId') == publication['netlify_deploy_id'] and public_result.get('sourceCommit') == publication['source_commit'], 'Public acceptance runtime identity differs')
    need(public_result.get('readOnly') is True or public_result.get('noProductionDataWrite') is True,
         'Public acceptance must identify a read-only/no-production-write scope')
    app = (WEB / '东方智慧-首页体验R4.html').read_text(encoding='utf-8')
    review = (WEB / '发给负责人-东方智慧首页R4.html').read_text(encoding='utf-8')
    embedded, _ = json.JSONDecoder().raw_decode(review.split('const APP=', 1)[1])
    need(embedded.replace('__INITIAL__', '{}') == app, 'Responsible-person entry embeds another APP')
    need((R4 / 'life-birth-entry.js').read_text(encoding='utf-8') in app, 'Current birth-entry source is absent from built APP')

    local_count, cloud_count = reports['local_full'].get('passed'), reports['cloudflare_full'].get('passed')
    limits = ['本轮移除用户界面的出生地、城市、时区和经纬度入口，不自动定位或声称获得真实出生地。',
              CALCULATION_REFERENCE_NOTE.strip(),
              '已知出生时间按当前参考规则实际计算，未知时间不填默认时辰或生成近似命盘。',
              '共享资料与既有排盘档案仍在当前浏览器按账号保存，未做全历史云同步或生产资料迁移。',
              '旧档案保留自身原始资料供独立复算；早先报告里的地域输入说明属于历史状态。',
              '浏览器测试不等同实机、正式AI或传统解释有效性认证；藏文仍待母语审校。']
    record = {'checked_beijing': stamp, 'pass': True, 'scope': '移除生辰地域字段及城市入口；单模块双后端完整回归后发布',
              'app_build_sha256': app_hash, 'source_sha256': module['source_sha256'], 'build_sha256': module['build_sha256'],
              'backup': {key: backup[key] for key in ['archive', 'archive_bytes', 'archive_sha256', 'verified_files', 'scope']},
              'module_ledger': {'report': LEDGER, 'report_sha256': digest(project_path(LEDGER)), 'modules': modules},
              'verification': reports, 'publication': publication, 'historical_failed_runs_this_round': failed_runs,
              'removed_visible_inputs': ['出生地', '城市参考/选择', '时区', '经度', '纬度'],
              'calculation_reference': CALCULATION_REFERENCE_NOTE.strip(),
              'visible_user_fields': ['date', 'sex', 'name', 'time'], 'new_birth_timezone_reference': 'Etc/GMT-8',
              'fresh_birth_geography_empty': True, 'legacy_shared_internal_geography_preserved_on_edit': True,
              'geographic_technical_display_hidden': ['结果摘要', '档案卡', '西方盘顶部'], 'limits': limits,
              'no_production_data_migration': True, 'complete_project_zip_repacked': False}
    notice = f"""### {date} 生辰地域字段与城市入口已移除并发布
按用户本次要求，生命地图共享生辰及排盘入口去掉出生地、城市、时区、经纬度输入和展开入口；较早说明中的这些表单字段仅属历史状态。表单只保留生日、性别及选填称呼/出生时间，时间直接显示且不嵌套折叠；准确时间保存后仍实际自动生成紫微，未知时间不猜时辰或造近似盘。结果摘要、档案卡与星盘顶部同步隐藏地域技术参数。
{CALCULATION_REFERENCE_NOTE.strip()}
本轮独立备份{backup['verified_files']}文件，当前本机{local_count}项/本地Cloudflare {cloud_count}项完整回归、本轮出生专项双端、三盘真实计算及五入口公网源码一致性/只读验收通过。所有结果核对本轮最终构建，不复用上一轮通过作为证明，历史记录保留。
Sites v{publication['sites_version']}；Netlify {publication['netlify_deploy_id']}；APP SHA-256 {app_hash}。使用与参考规则见{GUIDE}，实际证据见{RECORD}。本轮未重打完整项目ZIP，不迁移生产资料或改写旧排盘档案。"""
    guide = f"""生命地图统一出生资料入口
更新时间：{stamp}

当前输入
进入生命地图或三盘深链，必须先实际保存生日和性别；称呼/姓名、出生时间选填。表单只有date/sex/name/time四个用户字段；出生时间直接在表单选填，不再嵌套折叠。没有出生地、城市、时区、经纬度输入，也没有“城市参考”或“其他出生地设置”入口；结果摘要、档案卡、西方盘顶部也不再展示这些地域技术参数。返回键可以退出，未保存或无效资料不能绕过统一入口。

计算参考
{CALCULATION_REFERENCE_NOTE.strip()}
这是本APP当前采用的计算参考，不表示自动定位、读取或核实了用户的真实出生地。旧报告里可手选城市/时区/坐标的界面是历史状态，不应再作为当前操作说明。

准确时间与未知时间
保存准确时间后，使用原有真实引擎立即生成紫微，三盘复用共享出生资料，不重复要求填写。出生时间留空仍可保存生日和性别并进入四张原有功能卡；未知时间只展示日期基础参考与缺项说明，不补默认零点/中午、不生成近似十二宫、时柱运表或ASC/MC/宫位。
原有底层计算引擎和合法档案兼容能力保留；新资料因没有地点，不生成西方完整宫位。只按当前已具备且经过验证的资料计算，不用默认地点造盘，也不把传统结果描述为AI预测或健康判断。

资料与旧档案
共享资料只保存在当前浏览器并按账号隔离，在线身份未识别时不借游客资料放行；本轮不上传出生资料、不做全历史云同步。修改当前共享资料会清理对应当前盘；旧完整排盘档案保留自己的出生资料、已存UTC和规则，可由本人明确打开后独立复算。普通编辑既有共享资料保留其内部原地域参数，新建资料不继承；完整旧档案按自身原有UTC独立复算。本轮不删除旧兼容数据、不把旧地域字段重新开放为新输入。

本轮验证与发布
本机{local_count}项、本地Cloudflare {cloud_count}项完整回归；本轮出生专项双端、三盘实际计算与五入口公网源码一致性/只读验收已核对当前构建。具体实际断言、失败历史、截图、源码/构建哈希及发布身份见{RECORD}。不使用上一轮已发布结果代替本次验证。
公网：{origin}/experience?page=lifeResult
Sites版本：{publication['sites_version']}；Netlify部署：{publication['netlify_deploy_id']}。
APP SHA-256：{app_hash}

回退
本轮改前备份：{backup['archive']}
已逐项校验{backup['verified_files']}文件，SHA-256：{backup['archive_sha256']}。
仅按清单还原本轮受影响源码/构建后重新验证发布，不覆盖运行数据库、凭据和个人浏览器档案。原历史报告保留；本轮未重打完整项目ZIP。浏览器检查不等于全部实机、真实AI或传统解释有效性认证。
"""
    updates = {RECORD: json_bytes(record), GUIDE: guide.encode('utf-8')}
    for name in ['AGENTS.md', '先读我.txt', '交付包说明.txt', '03_当前APP/功能与使用说明-R4.txt']:
        updates[name] = notice_text(project_path(name).read_text(encoding='utf-8'), notice).encode('utf-8')
    section_id = 'birth-geography-inputs-removed'
    section = f'<section id="{section_id}"><h2>生辰地域字段移除（{date}）</h2><p>已按用户要求去掉出生地、城市、时区、经纬度输入与城市设置入口。保留生日、性别与选填称呼/时间；准确时间仍自动实际排紫微，未知时间不猜盘。内部计算参考与旧档案边界见当前说明。</p><p>本轮本机{local_count}项/本地Cloudflare {cloud_count}项完整回归、出生双端与三盘真实专项、五入口公网当前源码核验通过；早先字段说明仅作历史记录。</p><p><a href="{html.escape(origin + "/experience?page=lifeResult", quote=True)}">打开生命地图</a> · <a href="{GUIDE}">当前输入及计算规则</a> · <a href="{RECORD}">本轮实际交付核验</a></p></section>'
    task_name = '改动任务表-2026-10-22.html'
    updates[task_name] = replace_section(project_path(task_name).read_text(encoding='utf-8'), section_id, section, '<footer>').encode('utf-8')
    latest = f'<section id="current-delivery-package"><h1>当前项目更新 · {date}</h1><p>本轮已移除生辰出生地/城市/时区/经纬度入口；原创作者、数据中心与其余APP业务保留。Sites v{publication["sites_version"]}，本机{local_count}项/本地Cloudflare {cloud_count}项及本轮专项、公网源码核验通过。</p><p><a href="{origin}/experience?page=lifeResult">生命地图</a> · <a href="{origin}/creator">创作者中心</a> · <a href="{origin}/admin">公司后台</a> · <a href="03_当前APP/发给负责人-东方智慧首页R4.html">离线查看页</a></p><p><a href="{GUIDE}">当前生辰输入与计算参考</a> · <a href="{RECORD}">本轮真实交付记录</a> · <a href="资料校验清单.csv">当前文件校验清单</a></p><p>旧报告的地域表单说明属于历史状态。完整ZIP未重打，现有压缩包保留原快照时间。</p></section>'
    updates['打开这里.html'] = replace_section(project_path('打开这里.html').read_text(encoding='utf-8'), 'current-delivery-package', latest, '<h1>').encode('utf-8')
    if identity.get('deploy_id') != publication['netlify_deploy_id']:
        identity['previous_deploy_id'] = identity.get('deploy_id')
    identity.update(deploy_id=publication['netlify_deploy_id'], checked_at=stamp, status='deployed',
                    latest_change='生辰出生地/城市/时区/经纬度入口移除', latest_delivery_record=RECORD)
    updates['05_后台与研发说明/Netlify站点身份.json'] = json_bytes(identity)
    handoff = read('交接资料验证.json')
    old_publication = handoff.get('latest_publication')
    if old_publication and old_publication.get('netlify_deploy_id') != publication['netlify_deploy_id']:
        handoff['previous_publication'] = old_publication
    handoff.update(updated_beijing=stamp, local_regression_pass=True, regression_groups_passed=local_count,
                   regression_groups_failed=0, birth_geography_inputs_removed=record,
                   latest_publication={'pass': True, **publication, 'delivery_record': RECORD, 'app_build_sha256': app_hash})
    updates['交接资料验证.json'] = json_bytes(handoff)

    # Refresh the two existing authored-file manifests; exclude runtime/private material.
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
    manifest['current_revision'] = {'updated_beijing': stamp, 'scope': '生辰地域字段与城市入口移除', 'public_deployment_pending': False,
                                    'delivery_record': RECORD, 'app_build_sha256': app_hash, 'source_commit': publication['source_commit']}
    manifest['manifest_excludes'] = ['资料校验清单.csv', '原始来源与文件校验.json', 'Dependency/build/cache/runtime directories',
                                    'Archives, runtime SQLite/DB and sidecars, credentials and private environment files']
    updates['原始来源与文件校验.json'] = json_bytes(manifest)
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['包内相对位置', '字节数', 'SHA-256'])
    writer.writerows((item['path'], item['bytes'], item['sha256']) for item in files)
    updates['资料校验清单.csv'] = buffer.getvalue().encode('utf-8-sig')
    # No delivery-document write is allowed until all gates above have passed.
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
                      'sites_version': publication['sites_version'], 'netlify_deploy_id': publication['netlify_deploy_id'],
                      'record': RECORD, 'guide': GUIDE}, ensure_ascii=False))


if __name__ == '__main__':
    main()
