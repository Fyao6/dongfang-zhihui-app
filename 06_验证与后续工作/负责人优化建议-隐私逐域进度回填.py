"""Prepared stage26 progress update; do not run before the frozen receipt and both workbook checks.

Importing this module writes nothing. Other 96 task/audit rows and historical bytes stay unchanged.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import copy
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-隐私逐域'
IDS = ['PR04', 'PR05']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def checked_receipt():
    path = OUT / (PREFIX + '-实施记录.json')
    receipt = read(path)
    assert receipt['pass'] is True and receipt['stage'] == 26 and receipt['taskIds'] == IDS
    # Reuse the strict read-only collector, never its receipt writer.
    source = OUT / (PREFIX + '验收冻结.py')
    assert receipt['freezeHelperSHA256'] == sha(source), 'Freezer source changed after receipt creation'
    spec = importlib.util.spec_from_file_location('stage26_readonly_freezer', source)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    current = verifier.collect()
    for field in ('verification', 'reportIdentityHashes', 'source_hashes', 'build_hashes',
                  'preservedHistoricalSHA256', 'authorizedWorkbookBaselineSHA256'):
        assert receipt[field] == current[field], ('Frozen evidence no longer matches current bytes', field)
    checks = []
    for suffix, workbook in [('-负责人进度表回填校验.json', '东方智慧APP需求进度表-20261116.xlsx'),
                             ('-原98项任务表回填校验.json', '东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        report = read(OUT / (PREFIX + suffix))
        assert report['pass'] is True and report['scopePreserved'] is True and not report['violations'], suffix
        assert report['preservedOtherRequirements'] == 96, suffix
        assert all(ident in report['scope'] for ident in IDS), ('Workbook scope must name both tasks', suffix)
        assert report['candidateSha256'] == sha(OUT / workbook), workbook
        original = receipt['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/' + workbook]
        assert report['originalSha256'] == original, ('Wrong workbook baseline', workbook)
        checks.append(report)
    assert checks[0]['rowsWithEvidence'] == 67 and checks[0]['otherRows'] == 31
    return path, receipt, checks


def update():
    receipt_path, receipt, workbook_checks = checked_receipt()
    stamp = datetime.now(timezone(timedelta(hours=8)))
    tag = stamp.strftime('%Y%m%d-%H%M%S')
    report_path = OUT / (PREFIX + '-任务及交接回填核验.json')
    assert not report_path.exists(), 'Do not overwrite an existing delivery check'
    paths = {'tasks': OUT / '负责人优化建议-任务拆解.json',
             'audit': OUT / '负责人优化建议-98项最终覆盖审计.json',
             'audit_text': OUT / '负责人优化建议-98项最终覆盖审计.txt',
             'memory': OUT / '公司同步-进度与记忆.json',
             'queue': OUT / '负责人优化建议-交付收尾推进.json',
             'readme': ROOT / '公司同步-先读我.txt', 'rules': ROOT / 'AGENTS.md'}
    original = {key: path.read_bytes() for key, path in paths.items()}
    tasks, audit, memory, queue = (json.loads(original[k]) for k in ('tasks', 'audit', 'memory', 'queue'))
    old_tasks, old_rows, old_critical, old_queue = copy.deepcopy(tasks), copy.deepcopy(audit['rows']), copy.deepcopy(audit['critical']), copy.deepcopy(queue)
    assert len(tasks) == len(audit['rows']) == 98
    assert len({r['id'] for r in tasks}) == len({r['id'] for r in audit['rows']}) == 98
    assert all(sum(r['id'] == ident for r in tasks) == sum(r['id'] == ident for r in audit['rows']) == 1 for ident in IDS)
    counts = dict(Counter(r['status'] for r in tasks))
    assert counts == dict(Counter(r['task_table_status_at_audit'] for r in audit['rows']))
    assert counts == memory['progress']['statusCounts'] == audit['currentTaskStatusCounts']
    assert counts == {'进行中': 69, '待资料': 16, '待验收': 9, '待实施': 4}
    assert memory['development']['verifiedLocalStages'] == audit['verifiedLocalStages'] == 25
    assert memory['progress']['rowsWithLocalOrSandboxEvidenceIncludingPartial'] == workbook_checks[0]['rowsWithEvidence'] == 67
    assert memory['progress']['otherRows'] == workbook_checks[0]['otherRows'] == 31
    if 'statusCounts' in workbook_checks[0]:
        assert workbook_checks[0]['statusCounts'] == counts
    assert queue['current'] == 'PR04/PR05' and queue['groups'][3]['ids'] == IDS
    assert queue['groups'][4]['ids'] == ['PAY18', 'SV04']
    assert not any(s.get('stage') == 26 for s in memory['development']['stages'])

    main = '逐域清点与清理本地软件已验收：旧七类入口保留，四新增域真实写入跟踪、手动/确认期限预览与分批、历史未知年龄从现在纳管、nonce/版本/引用守卫、闭户首100及受限续办、永久媒体墓碑与Cloud实际对象删除及HEAD缺失核验、本人导出/分页回执和四语APP/中文后台。'
    scopes = {
        'PR04': main + '清空会话同时擦本人legacy AI正文和保存链接，保留配额费用账；私稿/未完成申请/服务正文/无引用素材按实际资格清理，公开共有、交易权益和最小审计继续保护。供应商、备份和浏览器不冒称已删。',
        'PR05': main + '新增四域期限独立且默认关闭/null，expiry须当前政策明确确认、真实跟踪/保护起点及最终事务校验；未知历史最后写入日不猜，未部署自动调度，正式天数和外部清理待确认与实施。'}
    remaining = {
        'PR04': ['供应商、备份/WAL、未来向量及外部缓存的真实删除连接器、确认和有限失败重试仍须实施联调；pending不代表已清。',
                 '身份骨架、设备连接、公开/共有内容、交易权益和审计等保护域的进一步删除或匿名化软件仍需明确政策后实施，不能称全部本方数据已擦除。',
                 '本地闭户不代替第三方订阅取消，浏览器及对方设备副本须单独处理。'],
        'PR05': ['常驻调度、受管执行身份、运行监控与失败告警仍须下一组及生产部署验证；当前schedulerDeployed=false。',
                 '正式各域保留天数/用途、备份/WAL/供应商生命周期策略和实际清理核验连接器仍待确认与实施，null不编正式天数。']}
    entry = {'path': receipt_path.relative_to(ROOT).as_posix(), 'sha256': sha(receipt_path),
             'module': PREFIX, 'pass': True, 'at': receipt['at_beijing'], 'scope': receipt['scope'],
             'limitations': receipt['limitations'],
             'verification': [{'name': name, **gate} for name, gate in receipt['verification'].items()]}
    for row in tasks:
        if row['id'] in IDS:
            ident = row['id']
            row.update(status='进行中', implementation_note=scopes[ident], progressNote=scopes[ident], remainingSoftware=remaining[ident])
            row['localEvidence'] = list(dict.fromkeys(row.get('localEvidence', []) + [entry['path']]))
    for row in audit['rows']:
        if row['id'] in IDS:
            ident = row['id']
            row.update(declaredCurrentScope=scopes[ident], stage=scopes[ident], task_table_status_at_audit='进行中',
                       softwareNotImplemented=remaining[ident], currentSoftwareBoundary='本方已列域的本地软件已验收；保护域、外部连接器、正式期限及生产运行按实际缺口继续推进。')
            row['resolvedSoftware'] = list(dict.fromkeys(row.get('resolvedSoftware', []) + [main]))
            row['additionalEvidence'] = [e for e in row.get('additionalEvidence', []) if e.get('path') != entry['path']] + [entry]
    for item in audit['critical']:
        if item.get('taskIds') in [[ident] for ident in IDS]:
            item['softwareNotImplemented'] = remaining[item['taskIds'][0]]
    assert [r['id'] for r in old_tasks] == [r['id'] for r in tasks]
    assert [r['id'] for r in old_rows] == [r['id'] for r in audit['rows']]
    assert all(before == after for before, after in zip(old_tasks, tasks) if before['id'] not in IDS)
    assert all(before == after for before, after in zip(old_rows, audit['rows']) if before['id'] not in IDS)
    assert all(before == after for before, after in zip(old_critical, audit['critical']) if not set(before.get('taskIds', [])) & set(IDS))
    assert dict(Counter(r['status'] for r in tasks)) == counts
    audit.update(verifiedLocalStages=26, updatedTaskIds=IDS, currentTaskStatusCounts=counts, latestUpdateAt=stamp.isoformat())
    audit['evidenceCatalog'][receipt_path.name] = entry
    audit['scopedLocalStageEvidence'] = [e for e in audit['scopedLocalStageEvidence'] if e.get('path') != entry['path']] + [entry]
    lines = ['98项当前覆盖与剩余工作', '26个本地验证阶段；67项含部分本地证据不等于整项完工。', '']
    for row in audit['rows']:
        lines += [f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}", row['declaredCurrentScope']]
        for key, label in [('softwareNotImplemented', '剩余软件'), ('externalInputs', '外部输入'), ('productionOrAcceptanceGates', '生产或验收')]:
            if row.get(key):
                lines += [label] + ['- ' + value for value in row[key]]
        lines += ['证据 ' + e['path'] for e in row.get('evidence', []) + row.get('additionalEvidence', [])] + ['']

    memory['scope'] = '公司同步后原位续作PR04/PR05本人资料逐域清点及导出清理回执；按用户授权继续8组本地收尾，旧ZIP及公开预览保持原冻结时点。'
    memory['development']['verifiedLocalStages'] = 26
    memory['development']['stages'].append({'stage': 26, 'ids': IDS, 'module': '本人资料逐域清点与清理',
        'implementation': main, 'receipt': entry['path'], 'receiptSHA256': entry['sha256'], 'verification': receipt['verification'],
        'open': '保护域进一步删除/匿名化、正式期限、外部供应商/备份及生产调度与目标设备仍待实施联调验收。'})
    memory['development']['currentSourcesSHA256'].update(receipt['source_hashes'])
    memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
    memory['progress']['workbookSha256'] = sha(OUT / '东方智慧APP需求进度表-20261116.xlsx')
    memory['progress']['note'] = '67项含部分本地/沙箱证据，非67项整项完工；26本地验证阶段为另一口径。'
    memory['next']['localSoftware'] = ['按交付收尾推进队列继续后4组：下一组PAY18/SV04内部任务持续运行与异常记录，再渠道框架、样本比对与卡组迁移回滚；最后补本地可靠性演练。',
        '本方已列个人域本地清理/导出已有证据，保护域进一步软件、外部清理连接器、正式政策和生产运行分别追踪，不能称全部个人数据已删。']
    memory['github']['localChangesAfterPublishedCommit'] = 'PAY08/PAY09/PAY10/PAY13、MB01/AI05、SH06、PR04/PR05与本轮表格交接仅本目录更新，未推送或发布。'
    memory['workingRules'][1] = '保留历史冻结字节。当前26本地阶段覆盖早期交接时点，8组授权逐模块继续；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate'] = {'at': stamp.isoformat(), 'module': 'PR04/PR05', 'zipRepacked': False, 'originalPackageManifestUnchanged': True}
    memory['savedAtBeijing'] = stamp.isoformat()
    queue['groups'][3].update(status='本地已验证', receipt=entry['path'])
    in_progress = queue['groups'][3].pop('inProgressRecord', None)
    if in_progress:
        queue['groups'][3]['historicalInProgressRecord'] = in_progress
    queue['groups'][4]['status'] = '进行中'
    queue.update(current='PAY18/SV04', at=stamp.isoformat())
    assert all(before == after for i, (before, after) in enumerate(zip(old_queue['groups'], queue['groups'])) if i not in (3, 4))
    readme = '当前续作：PR04/PR05本人资料逐域清点与清理已通过本地验收，累计26阶段；67项含部分证据，状态69/16/9/4。旧七类和四新增域、分批及真实文件核验有本地证据，保护域/外部供应商/备份/浏览器不冒称全删。下一组PAY18/SV04内部任务持续运行与异常记录；未推送、未发布、未重打包。详细见公司同步JSON及本模块冻结收据。\n\n' + original['readme'].decode('utf-8')
    rules = original['rules'].decode('utf-8')
    marker = '## 2026-11-16 数字作品次数与期限'
    heading = '## ' + stamp.strftime('%Y-%m-%d') + ' 本人资料逐域清点与清理'
    assert marker in rules and heading not in rules
    rules = rules.replace(marker, heading + '\n\nPR04/PR05已通过本地验收：逐域盘点、四新增域真实跟踪与手动/期限分批、历史纳管、闭户首100及受限续办、永久媒体墓碑、Cloud真实删除与HEAD缺失核验、本人导出与分页回执。旧七类及资金额度权益事实保留，外部供应商/备份/浏览器和保护域不冒称全删；正式期限未编，未部署自动调度。累计26阶段，67项含部分证据、状态69/16/9/4。按8组授权继续PAY18/SV04内部任务运行与异常记录；未推送或重打包。\n\n' + marker, 1)
    values = {'tasks': tasks, 'audit': audit, 'audit_text': '\n'.join(lines) + '\n', 'memory': memory,
              'queue': queue, 'readme': readme, 'rules': rules}
    backups = {}
    for key, path in paths.items():
        assert path.read_bytes() == original[key], ('Concurrent update', path.name)
        backup = OUT / (PREFIX + '回填前-' + tag + '-' + path.name)
        assert not backup.exists(), backup.name
        backup.write_bytes(original[key])
        backups[path.relative_to(ROOT).as_posix()] = {'path': backup.relative_to(ROOT).as_posix(), 'sha256': sha(backup)}
    for key, path in paths.items():
        value = values[key]
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        path.write_bytes(text.encode('utf-8'))
    result = {'pass': True, 'at': stamp.isoformat(), 'stage': 26, 'updatedTaskIds': IDS,
              'other96TaskAndAuditRowsPreserved': True, 'counts': counts, 'rowsWithEvidenceIncludingPartial': 67,
              'otherRows': 31, 'receipt': entry['path'], 'receiptSHA256': entry['sha256'],
              'verification': receipt['verification'], 'backups': backups,
              'hashes': {name: sha(ROOT / name) for name in backups}, 'published': False, 'zipRepacked': False}
    report_path.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'stage': 26, 'updatedTasks': IDS, 'statusCounts': counts}, ensure_ascii=False))


if __name__ == '__main__':
    update()
