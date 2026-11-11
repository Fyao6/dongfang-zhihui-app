"""Record only a verified framework release; never builds, publishes or touches databases."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import importlib.util
import io
import json
import re

ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / '06_验证与后续工作'
FINAL_RECORD_READY = False
LEDGER = '基础框架逐模块回归记录.json'
PUBLICATION = '基础框架发布身份.json'
RECORD = '基础框架交付记录.json'
GUIDE = '05_后台与研发说明/基础框架阶段说明与验收.txt'


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def path(relative):
    value = (ROOT / relative).resolve()
    need(value.is_relative_to(ROOT.resolve()), 'Path outside project')
    return value


def sha(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(file):
    return json.loads(file.read_text(encoding='utf-8-sig'))


def write(file, data):
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(reference):
    document = read(Q / reference['report'])
    candidates = [document.get('latest', document), *document.get('runs', [])]
    found = next((item for item in candidates if item.get('at') == reference['at'] and item.get('module') == reference.get('module')), None)
    need(found and found.get('pass') and found.get('failed', 0) == 0, 'Missing passed run: ' + reference['report'])
    return found


def bind_run(item, module):
    for field in ['buildHashes', 'cloudBuildHashes']:
        if field in item:
            need(item[field] and all(module[field].get(relative) == expected for relative, expected in item[field].items()), 'Historical build identity differs: ' + module['id'])
    for relative, expected in item.get('sourceHashes', {}).items():
        need(module['sourceHashes'].get(relative) == expected, 'Historical source identity differs: ' + relative)
    if 'buildSha256' in item:
        need(item['buildSha256'] == module['buildHashes']['东方智慧-首页体验R4.html'], 'Historical APP differs')


def replace_block(text, key, content):
    block = f'<!-- {key}:start -->\n{content}\n<!-- {key}:end -->'
    pattern = rf'<!-- {re.escape(key)}:start -->[\s\S]*?<!-- {re.escape(key)}:end -->'
    return re.sub(pattern, lambda _: block, text) if re.search(pattern, text) else text.rstrip() + '\n\n' + block + '\n'


def main():
    need(FINAL_RECORD_READY, 'Review actual final tests, publication and wording before recording')
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    ledger = read(Q / LEDGER)
    modules = {item['id']: item for item in ledger['modules']}
    need(set(modules) >= {'F01', 'F02', 'F03', 'F04'}, 'Four implemented modules required')
    last_sources = {}
    for identity in ['F01', 'F02', 'F03', 'F04']:
        module = modules[identity]
        need(module.get('pass') and module.get('final'), 'Incomplete module: ' + identity)
        need(module.get('sourceHashes') and module.get('buildHashes') and module.get('cloudBuildHashes'), 'Module identity missing')
        for target in ['local', 'cloud']:
            full = run(module['full'][target])
            need(full['passed'] >= 60, 'Full regression scope reduced')
            bind_run(full, module)
        need(len(module.get('specialty', {})) >= 2, 'Both backend specialties required: ' + identity)
        for ref in module.get('specialty', {}).values():
            bind_run(run(ref), module)
        last_sources.update(module['sourceHashes'])
    for relative, expected in last_sources.items():
        need(sha(path(relative)) == expected, 'Untested source mutation: ' + relative)
    builds = {}
    for name, base, field in [('本轮全量回归结果.json', '03_当前APP', 'buildHashes'), ('公网适配全量回归结果.json', '04_研发源码/app/cloud', 'cloudBuildHashes')]:
        current = read(Q / name)['latest']
        need(current.get('pass') and current.get('failed', 0) == 0, 'Latest regression failed')
        target = 'local' if field == 'buildHashes' else 'cloud'
        need(current['at'] == modules['F04']['full'][target]['at'] and current['module'] == modules['F04']['full'][target]['module'], 'Latest full is not final F04')
        required = {'东方智慧-首页体验R4.html', '发给负责人-东方智慧首页R4.html', '计时后台-开发联调.html'} if target == 'local' else {'generated/experience.html', 'generated/admin.html', 'generated/review.html', 'dist/server/index.js'}
        need(set(current[field]) >= required and all(modules['F04'][field].get(relative) == expected for relative, expected in current[field].items()), 'Final build identity incomplete')
        for relative, expected in current[field].items():
            file = path(base + '/' + relative)
            need(sha(file) == expected, 'Current build differs from tested build')
            builds[file.relative_to(ROOT).as_posix()] = expected
    app = path('03_当前APP/东方智慧-首页体验R4.html')
    app_hash, app_text = sha(app), app.read_text(encoding='utf-8')
    for relative in last_sources:
        if relative.startswith('04_研发源码/app/r4/') and path(relative).suffix in ['.js', '.css'] and not path(relative).name.endswith('-admin.js'):
            need(path(relative).read_text(encoding='utf-8') in app_text, 'Source not embedded: ' + relative)
    for relative in ['03_当前APP/创作者中心.html', '04_研发源码/app/cloud/generated/creator.html']:
        need(path(relative).read_bytes() == path('04_研发源码/app/r4/creator-center.html').read_bytes(), 'Creator build differs')
        builds[relative] = sha(path(relative))
    publication = read(Q / PUBLICATION)
    need(publication['sites_status'] == 'succeeded' and publication['netlify_status'] == 'ready', 'Release not published')
    need(sha(path(publication['archive'])) == publication['archive_sha256'], 'Deployment archive differs')
    public = read(path(publication['public_build_match_report']))
    public = public.get('latest', public)
    need(public['pass'] and public['localAppSha256'] == app_hash and public['sourceCommit'] == publication['source_commit'], 'Public provenance differs')
    need({item['route'] for item in public['checks']} == {'/', '/experience', '/creator', '/admin', '/app'}, 'Public routes incomplete')
    need(all(item['generatedMatch'] and item['status'] == 200 and item['servedNormalizedSha256'] == item['expectedNormalizedSha256'] for item in public['checks']), 'Public build mismatch')
    acceptance = read(path(publication['public_acceptance_report']))
    acceptance = acceptance.get('latest', acceptance)
    need(acceptance['pass'] and acceptance['localAppSha256'] == app_hash, 'Current public acceptance missing')
    for evidence in [public, acceptance]:
        need(evidence['netlifyDeployId'] == publication['netlify_deploy_id'] and evidence['sourceCommit'] == publication['source_commit'] and evidence['sitesVersion'] == publication['sites_version'] and evidence['origin'].rstrip('/') == publication['url'].rstrip('/'), 'Public release identity differs')
    need(not acceptance.get('errors') and acceptance.get('readOnly') and acceptance.get('noProductionDataWrite'), 'Public read-only/error boundary missing')
    foundation_file = Q / '基础框架F05契约与恢复核验.json'
    foundation_document = read(foundation_file)
    foundation = foundation_document.get('latest', foundation_document)
    need(foundation['pass'] is True and foundation.get('failed') == 0 and foundation.get('buildSha256') == app_hash and foundation.get('module') == '基础框架F05', 'Contract/restore verification incomplete')
    need(foundation.get('contracts', {}).get('equal') is True and foundation['contracts'].get('sqlite') and foundation['contracts'].get('d1'), 'Both actual restored backend contracts required')
    restore_reference = foundation['restoreReport']
    restore = run(restore_reference)
    need(restore.get('mode') == 'both' and restore.get('buildSha256') == app_hash and restore.get('productionWrites') is False, 'Actual two-backend restore reference differs')
    need(foundation.get('sourceHashes') and foundation.get('buildHashes') and foundation.get('cloudBuildHashes'), 'Contract/restore identities missing')
    for relative, expected in foundation['sourceHashes'].items():
        need(sha(path(relative)) == expected, 'Contract/restore source differs')
        need(restore.get('sourceHashes', {}).get(relative) == expected, 'Actual restore source differs')
        last_sources[relative] = expected
    for field, base in [('buildHashes', '03_当前APP'), ('cloudBuildHashes', '04_研发源码/app/cloud')]:
        for relative, expected in foundation[field].items():
            need(restore.get(field, {}).get(relative) == expected, 'Actual restore build identity differs')
            file = path(base + '/' + relative)
            need(sha(file) == expected, 'Contract/restore build changed')
            builds[file.relative_to(ROOT).as_posix()] = expected
    need(foundation.get('productionWrites') is False and foundation.get('isolation', {}).get('servicesStopped') is True, 'Restore isolation/cleanup evidence missing')
    backup = read(Q / '基础框架实施前备份核验.json')
    need(backup['verified_files'] == len(backup['files']) and sha(path(backup['archive'])) == backup['archive_sha256'], 'Pre-change archive differs')
    text = path(GUIDE).read_text(encoding='utf-8')
    need('AI' in text and '本机' in text and '游客' in text, 'Delivery guide incomplete')
    record = {'checked_beijing': stamp, 'pass': True, 'scope': 'AI暂缓，现有APP/创作者/公司后台基础框架', 'app_build_sha256': app_hash,
              'source_sha256': last_sources, 'build_sha256': builds, 'module_ledger': ledger, 'publication': publication,
              'guide': GUIDE, 'backup_report': '06_验证与后续工作/基础框架实施前备份核验.json',
              'verification': {'foundation': {'report': '06_验证与后续工作/基础框架F05契约与恢复核验.json', 'at': foundation['at'], 'module': foundation['module'], 'sha256': sha(foundation_file)},
                               'restore': {'report': '06_验证与后续工作/' + restore_reference['report'], 'at': restore['at'], 'module': restore['module'], 'sha256': sha(Q / restore_reference['report'])}},
              'limits': ['AI问答和AI审核暂缓，人工审核保留', '生辰/排盘/笔记仍保存在本浏览器；没有完整跨设备同步或自动补传', '旧未标明账号的共享记录保留游客归属，不推断到登录账号', '浏览器测试与本地Cloudflare不等同原生实机或生产数据恢复演练', '现有ZIP仍是其原打包时间快照，本轮未重打包']}
    write(Q / RECORD, record)
    note = f'### {stamp[:10]} 基础框架已验证并发布\nF01连接恢复、F02账号与保存、F03创作者人工发布闭环、F04后台读取与登录恢复已按模块完成本轮双端完整回归及专项，F05契约与隔离恢复核验通过。AI接入继续暂缓；三地图4/4/3、生辰保存门禁与四字段、自动累计计时和成熟创作者结构保留。当前APP SHA-256 {app_hash}；Sites v{publication["sites_version"]}；Netlify {publication["netlify_deploy_id"]}。详见{GUIDE}与06_验证与后续工作/{RECORD}，各轮失败及修复记录保留。未重打完整ZIP，不将本机测试称为全部实机、生产数据库恢复或真实外部服务已接通。'
    for relative in ['AGENTS.md', '先读我.txt']:
        p = path(relative)
        p.write_text(replace_block(p.read_text(encoding='utf-8'), 'foundation-delivery', note), encoding='utf-8')
    p = path('打开这里.html')
    entry = p.read_text(encoding='utf-8')
    section = '<section id="foundation-current-delivery"><h2>当前基础框架</h2><p>账号数据隔离、真实保存状态、连接恢复、人工发布审核与后台读取恢复已完成本轮验证并发布，AI接入暂缓。已有ZIP保留原快照时间。</p><p><a href="改动任务表-2026-10-22.html#foundation-first-ai-deferred">查看当前任务表</a> · <a href="' + GUIDE + '">本轮说明与数据归属</a> · <a href="06_验证与后续工作/' + RECORD + '">实际交付记录</a></p></section>'
    entry = re.sub(r'<section id="foundation-current-delivery">[\s\S]*?</section>', '', entry)
    need('<main' in entry, 'Root entry main missing')
    entry = re.sub(r'(<main[^>]*>)', lambda m: m[0] + section, entry, count=1)
    p.write_text(entry, encoding='utf-8')
    spec = importlib.util.spec_from_file_location('_package_inventory', Q / '打包当前交付.py')
    inventory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inventory)
    files = [{'path': rel, 'bytes': file.stat().st_size, 'sha256': sha(file)} for rel, file in sorted(inventory.collect_files().items()) if rel not in inventory.SELF]
    manifest = read(path('原始来源与文件校验.json'))
    manifest['files'] = files
    previous_filter = manifest.get('delivery_filter')
    if previous_filter and previous_filter.get('archive_name'):
        manifest['previous_packaged_snapshot'] = previous_filter
    manifest['delivery_filter'] = {'manifest_scope': 'Current authored workspace inventory except two self manifests; existing ZIP remains its earlier snapshot', 'zip_repacked': False, 'private_runtime_excluded': True, 'historical_zips_excluded': True, 'no_wrapper': True}
    manifest['current_revision'] = {'updated_beijing': stamp, 'scope': record['scope'], 'delivery_record': '06_验证与后续工作/' + RECORD, 'public_deployment_pending': False, 'app_build_sha256': app_hash, 'zip_repacked': False}
    write(path('原始来源与文件校验.json'), manifest)
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(['包内相对位置', '字节数', 'SHA-256'])
    writer.writerows([item['path'], item['bytes'], item['sha256']] for item in files)
    path('资料校验清单.csv').write_text(buffer.getvalue(), encoding='utf-8-sig', newline='')
    for item in files:
        need(path(item['path']).stat().st_size == item['bytes'] and sha(path(item['path'])) == item['sha256'], 'Manifest mismatch')
    print(json.dumps({'pass': True, 'record': RECORD, 'manifest_files': len(files), 'app_build_sha256': app_hash}, ensure_ascii=False))


if __name__ == '__main__':
    main()
