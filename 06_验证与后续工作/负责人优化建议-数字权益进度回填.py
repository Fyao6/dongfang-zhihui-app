"""Prepare current task/handoff updates only after the frozen stage25 SH06 receipt.

Importing this file does not update anything. Run it only after both workbook
scope checks have passed and their checked bytes are the current workbooks.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-数字权益'
COUNTS = {'进行中': 69, '待资料': 16, '待验收': 9, '待实施': 4}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def checked_receipt():
    path = OUT / (PREFIX + '-实施记录.json')
    receipt = read(path)
    assert receipt.get('pass') is True and receipt.get('stage') == 25
    assert receipt.get('taskIds') == ['SH06']
    for field in ('source_hashes', 'build_hashes'):
        assert isinstance(receipt.get(field), dict) and receipt[field], field
        for name, expected in receipt[field].items():
            target = (ROOT / name).resolve()
            assert target.is_relative_to(ROOT) and sha(target) == expected, name
    assert {'Python全量', 'Cloud全量', 'Python专项', 'Cloud专项'} <= receipt['verification'].keys()
    for label, gate in receipt['verification'].items():
        report_path = (ROOT / gate['path']).resolve()
        assert report_path.is_relative_to(ROOT) and sha(report_path) == gate['sha256'], label
        report = read(report_path)
        run = report.get('latest', report)
        assert run.get('pass') is True and run.get('failed', 0) == 0, label
        assert gate['failed'] == 0 and len(run['results']) == gate['passed'], label
        assert all(result.get('pass') is True for result in run['results']), label
    for report_name, workbook in (
        ('-负责人进度表回填校验.json', '东方智慧APP需求进度表-20261116.xlsx'),
        ('-原98项任务表回填校验.json', '东方智慧APP优化任务表_依据v1.0_20261112.xlsx'),
    ):
        report = read(OUT / (PREFIX + report_name))
        assert report.get('pass') is True and report.get('scopePreserved') is True, report_name
        assert report.get('preservedOtherRequirements') == 97, report_name
        assert report['candidateSha256'] == sha(OUT / workbook), workbook
        if 'rowsWithEvidence' in report:
            assert report['rowsWithEvidence'] == 67 and report['otherRows'] == 31, report_name
        if 'statusCounts' in report:
            assert report['statusCounts'] == COUNTS, report_name
    return path, receipt


def update():
    receipt_path, receipt = checked_receipt()
    stamp = datetime.now(timezone(timedelta(hours=8)))
    tag = stamp.strftime('%Y%m%d-%H%M%S')
    report_path = OUT / (PREFIX + '-任务及交接回填核验.json')
    assert not report_path.exists(), 'Do not overwrite an existing delivery check.'
    paths = {
        'tasks': OUT / '负责人优化建议-任务拆解.json',
        'audit': OUT / '负责人优化建议-98项最终覆盖审计.json',
        'audit_text': OUT / '负责人优化建议-98项最终覆盖审计.txt',
        'memory': OUT / '公司同步-进度与记忆.json',
        'queue': OUT / '负责人优化建议-交付收尾推进.json',
        'readme': ROOT / '公司同步-先读我.txt',
        'rules': ROOT / 'AGENTS.md',
    }
    original = {key: path.read_bytes() for key, path in paths.items()}
    tasks, audit, memory, queue = (json.loads(original[key]) for key in ('tasks', 'audit', 'memory', 'queue'))
    old_tasks, old_rows = copy.deepcopy(tasks), copy.deepcopy(audit['rows'])
    assert len(tasks) == len(audit['rows']) == 98
    assert len({row['id'] for row in tasks}) == len({row['id'] for row in audit['rows']}) == 98
    assert sum(row['id'] == 'SH06' for row in tasks) == sum(row['id'] == 'SH06' for row in audit['rows']) == 1
    assert memory['development']['verifiedLocalStages'] == 24
    assert memory['progress']['rowsWithLocalOrSandboxEvidenceIncludingPartial'] == 67
    assert memory['progress']['otherRows'] == 31 and memory['progress']['statusCounts'] == COUNTS
    assert audit['verifiedLocalStages'] == 24
    assert queue['current'] == 'SH06' and queue['groups'][2]['ids'] == ['SH06']
    assert queue['groups'][3]['ids'] == ['PR04', 'PR05']
    assert not any(stage.get('stage') == 25 for stage in memory['development']['stages'])

    main = '独立数字作品次数与期限本地软件已验收：新单不可变使用规则快照、普通/回调/主动查单/迟到付款同事务唯一授予；签发访问时原子计次、同会话幂等恢复与逐GET/Range门禁、退款不回补used及超用记录、永久隔离测试素材、本人导出与完整分页、四语APP及中文后台。'
    scope = main + '当前默认关闭、仅明确隔离的沙箱音视频；旧无快照订单不补造政策或次数，原库存退款余量remaining与使用账分开。正式内容、版权和生产访问未接通。'
    remaining = ['正式数字内容版权、次数/期限/访问窗口及退款政策须确认；真实验单、生产媒体与CDN/目标设备访问仍须按确认规则实施联调验收。']
    entry = {'path': receipt_path.relative_to(ROOT).as_posix(), 'sha256': sha(receipt_path),
             'module': PREFIX, 'pass': True, 'at': receipt['at_beijing'], 'scope': receipt['scope'],
             'limitations': receipt['limitations'],
             'verification': [{'name': name, **gate} for name, gate in receipt['verification'].items()]}
    for row in tasks:
        if row['id'] == 'SH06':
            row.update(status='进行中', implementation_note=scope, progressNote=scope, remainingSoftware=remaining)
            row['localEvidence'] = list(dict.fromkeys(row.get('localEvidence', []) + [entry['path']]))
    assert [row['id'] for row in old_tasks] == [row['id'] for row in tasks]
    assert all(before == after for before, after in zip(old_tasks, tasks) if before['id'] != 'SH06')
    counts = dict(Counter(row['status'] for row in tasks))
    assert counts == COUNTS
    for row in audit['rows']:
        if row['id'] == 'SH06':
            row.update(declaredCurrentScope=scope, stage=scope, task_table_status_at_audit='进行中',
                       softwareNotImplemented=remaining,
                       currentSoftwareBoundary='有限沙箱数字访问本地软件已验收；正式版权、真实服务和生产访问另行配置、实施联调与验收。')
            row['resolvedSoftware'] = list(dict.fromkeys(row.get('resolvedSoftware', []) + [main]))
            row['additionalEvidence'] = [item for item in row.get('additionalEvidence', []) if item.get('path') != entry['path']] + [entry]
    assert [row['id'] for row in old_rows] == [row['id'] for row in audit['rows']]
    assert all(before == after for before, after in zip(old_rows, audit['rows']) if before['id'] != 'SH06')
    audit.update(verifiedLocalStages=25, updatedTaskIds=['SH06'], currentTaskStatusCounts=counts, latestUpdateAt=stamp.isoformat())
    audit['evidenceCatalog'][receipt_path.name] = entry
    audit['scopedLocalStageEvidence'] = [item for item in audit['scopedLocalStageEvidence'] if item.get('path') != entry['path']] + [entry]
    lines = ['98项当前覆盖与剩余工作', '25个本地验证阶段；67项含部分本地证据不等于整项完工。', '']
    for row in audit['rows']:
        lines += [f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}", row['declaredCurrentScope']]
        for key, label in [('softwareNotImplemented', '剩余软件'), ('externalInputs', '外部输入'), ('productionOrAcceptanceGates', '生产或验收')]:
            if row.get(key):
                lines += [label] + ['- ' + value for value in row[key]]
        lines += ['证据 ' + item['path'] for item in row.get('evidence', []) + row.get('additionalEvidence', [])] + ['']

    memory['scope'] = '公司同步后原位续作SH06独立数字作品次数期限；按用户授权继续8组本地收尾，旧ZIP与公开预览保持原冻结时点。'
    memory['development']['verifiedLocalStages'] = 25
    memory['development']['stages'].append({'stage': 25, 'ids': ['SH06'], 'module': '数字作品次数与期限',
        'implementation': main, 'receipt': entry['path'], 'receiptSHA256': entry['sha256'],
        'verification': receipt['verification'], 'open': '正式版权及商业次数期限/退款政策、真实支付与生产媒体和目标设备仍待实施联调验收。'})
    memory['development']['currentSourcesSHA256'].update(receipt['source_hashes'])
    memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
    memory['progress']['workbookSha256'] = sha(OUT / '东方智慧APP需求进度表-20261116.xlsx')
    memory['progress']['note'] = '67项含部分本地/沙箱证据，非67项整项完工；25本地验证阶段为另一口径。'
    memory['next']['localSoftware'] = ['按06/负责人优化建议-交付收尾推进.json继续后5组：下一组PR04/PR05本方个人资料逐域清点及导出删除回执，再内部监控、渠道框架、样本比对与卡组工具；最后补本地可靠性演练。',
        '支付可靠收件/恢复/迟到补偿、会员周期额度和独立数字作品次数期限已有通用本地证据；真实渠道、正式政策和生产运行分别追踪。']
    memory['github']['localChangesAfterPublishedCommit'] = 'PAY08/PAY09/PAY10/PAY13、MB01/AI05及SH06与本轮表格交接仅本目录更新，未推送或发布。'
    memory['workingRules'][1] = '保留历史冻结字节。当前25本地阶段覆盖早期交接时点，8组授权逐模块继续；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate'] = {'at': stamp.isoformat(), 'module': 'SH06', 'zipRepacked': False, 'originalPackageManifestUnchanged': True}
    memory['savedAtBeijing'] = stamp.isoformat()
    queue['groups'][2].update(status='本地已验证', receipt=entry['path'])
    queue['groups'][3]['status'] = '进行中'
    queue.update(current='PR04/PR05', at=stamp.isoformat())
    readme = '当前续作：SH06数字作品次数与期限已通过本地验收，累计25阶段；67项含部分证据，状态69/16/9/4。8组收尾按序继续，下一组PR04/PR05本方个人资料逐域清点及导出删除回执。当前仅有限隔离沙箱访问，不等于正式版权、真实收费或生产媒体接通；未推送、未重打包。详细见公司同步JSON及本模块冻结收据。\n\n' + original['readme'].decode('utf-8')
    rules = original['rules'].decode('utf-8')
    marker = '## 2026-11-16 会员AI周期额度'
    heading = '## 2026-11-16 数字作品次数与期限'
    assert marker in rules and heading not in rules
    rules = rules.replace(marker, heading + '\n\nSH06已通过本地验收：有限天数/次数的独立沙箱音视频、新单不可变快照、普通与回调/查单/迟到付款唯一授予、原子签发计次、会话绑定恢复、逐GET/Range权限重核、退款不回补used、永久素材隔离、本人导出/分页及四语APP和中文后台。累计25阶段，67项含部分证据、状态69/16/9/4；正式版权与商业规则、真实支付、生产媒体和目标设备仍待实施联调验收。继续用户已授权8组收尾，下一组PR04/PR05逐域清理与导出删除回执；队列见06_验证与后续工作/负责人优化建议-交付收尾推进.json。旧订单不补造数字政策，未推送或重打包。\n\n' + marker, 1)
    values = {'tasks': tasks, 'audit': audit, 'audit_text': '\n'.join(lines) + '\n',
              'memory': memory, 'queue': queue, 'readme': readme, 'rules': rules}
    backups = {}
    for key, path in paths.items():
        assert path.read_bytes() == original[key], f'Concurrent update: {path.name}'
        backup = OUT / (PREFIX + '回填前-' + tag + '-' + path.name)
        assert not backup.exists(), backup.name
        backup.write_bytes(original[key])
        backups[path.relative_to(ROOT).as_posix()] = {'path': backup.relative_to(ROOT).as_posix(), 'sha256': sha(backup)}
    for key, path in paths.items():
        value = values[key]
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        path.write_bytes(text.encode('utf-8'))
    result = {'pass': True, 'at': stamp.isoformat(), 'stage': 25, 'updatedTaskIds': ['SH06'],
              'other97TaskAndAuditRowsPreserved': True, 'counts': counts,
              'rowsWithEvidenceIncludingPartial': 67, 'otherRows': 31,
              'receipt': entry['path'], 'receiptSHA256': entry['sha256'],
              'verification': receipt['verification'], 'backups': backups,
              'hashes': {name: sha(ROOT / name) for name in backups},
              'published': False, 'zipRepacked': False}
    report_path.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'stage': 25, 'updatedTasks': ['SH06'], 'statusCounts': counts}, ensure_ascii=False))


if __name__ == '__main__':
    update()
