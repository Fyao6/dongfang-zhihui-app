"""Backfill task notes and audit from the verified local integration reports."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from runpy import run_path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
TASKS = OUT / '负责人优化建议-任务拆解.json'
AUDIT = OUT / '负责人优化建议-98项最终覆盖审计.json'
WORKBOOK = OUT / '东方智慧APP优化任务表_依据v1.0_20261112.xlsx'
MEMORY = '负责人优化建议-长期记忆-实施记录.json'
GATES = {
    'retention': ('到期清理', ('Python全量', 'Cloud全量', 'Python专项', 'Cloud专项'), 26),
    'closure': ('账号注销', ('pythonFull', 'cloudFull', 'pythonActual', 'cloudActual'), 27),
    'caseFinance': ('售后资金关联', ('pythonFull', 'cloudFull', 'pythonActual', 'cloudActual'), 24),
    'secretReferences': ('密钥引用', ('pythonFull', 'cloudFull', 'pythonActual', 'cloudActual'), 20),
    'memory': ('长期记忆', ('Python完整回归', 'Cloud完整回归', 'Python实际专项', 'Cloud实际专项'), 10),
}


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()


def verify_stage(name, labels, specific_count, frozen):
    path = OUT / f'负责人优化建议-{name}-实施记录.json'
    receipt = read(path)
    handoff = frozen.get(relative(path))
    if handoff:
        assert sha(path) == handoff['sha256'], path
    else:
        assert path.name == MEMORY and receipt['status'] == '本地验证通过'
        for group in ('buildAndSourceHashes', 'testSourceHashes', 'visualCaptures'):
            for item, digest in receipt[group].items():
                assert sha(ROOT / item) == digest, item
    verification = []
    for label, count in zip(labels, (60, 60, specific_count, specific_count)):
        item = (handoff or receipt)['verification'][label]
        report_path = ROOT / item['path']
        assert sha(report_path) == item['sha256'], report_path
        report = read(report_path)
        report = report.get('latest', report)
        assert item['passed'] == report['passed'] == count and report['failed'] == 0
        results = report['results']
        assert len(results) == count and all(result['pass'] is True for result in results)
        verification.append({'name': label, 'path': item['path'], 'sha256': item['sha256'],
                             'passed': count, 'failed': 0})
    return {'path': relative(path), 'sha256': sha(path), 'module': receipt['module'],
            'scope': receipt['scope'], 'verification': verification,
            'basis': '双端完整回归与实际专项的原始文本报告',
            'limitations': receipt.get('limitations', receipt.get('limits', []))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    handoff = read(OUT / '回家继续-进度与记忆.json')
    frozen = {stage['path']: stage for stage in handoff['verified_stages']}
    assert len(frozen) == 17
    for path, item in frozen.items():
        assert sha(ROOT / path) == item['sha256'], path
    stages = {key: verify_stage(*spec, frozen) for key, spec in GATES.items()}
    proposals = run_path(str(OUT / '负责人优化建议-五模块任务回填准备.py'))['proposals']()
    tasks, audit = read(TASKS), read(AUDIT)
    ids = [task['id'] for task in tasks]
    assert len(ids) == len(set(ids)) == 98
    assert [row['id'] for row in audit['rows']] == ids
    assert set(proposals) <= set(ids)
    for entry in stages.values():
        audit['evidenceCatalog'][Path(entry['path']).name] = entry
    changed = []
    for task, row in zip(tasks, audit['rows']):
        assert task['source_ids'] == row['source_ids'] and task['status'] == row['task_table_status_at_audit']
        change = proposals.get(task['id'])
        if not change:
            continue
        changed.append(task['id'])
        note = change['proposedImplementationNoteAfterGate']
        task['implementation_note'] = note
        row.update(declaredCurrentScope=note, stage=note,
                   resolvedSoftware=change['resolvedSoftwareAfterGate'],
                   softwareNotImplemented=change['softwareNotImplementedAfterGate'],
                   externalInputs=change['externalInputsAfterGate'],
                   productionOrAcceptanceGates=change['productionGatesAfterGate'],
                   softwareAssessmentBasis='任务原文、阶段范围及双端完整回归与实际专项',
                   softwareGapEvidence=[],
                   currentSoftwareBoundary=change['proposedCurrentSoftwareBoundaryAfterGate'])
        known = {entry['path'] for entry in row['evidence']}
        row['evidence'].extend(stages[key] for key in change['requiresFrozenRecords']
                               if stages[key]['path'] not in known)
    audit['critical'] = [
        {**item, **{field: row[field] for field in ('softwareNotImplemented', 'externalInputs')},
         'productionGates': row['productionOrAcceptanceGates']}
        for item in audit['critical']
        for row in audit['rows'] if row['id'] == item['taskIds'][0]
    ]
    now = datetime.now(timezone(timedelta(hours=8)))
    audit.update(at_beijing=now.isoformat(), verifiedLocalStages=18,
                 updatedTaskIds=changed, currentTaskStatusCounts=dict(Counter(t['status'] for t in tasks)),
                 scopedLocalStageEvidence=list(stages.values()))
    audit['scope']['taskJSONModified'] = True
    audit['limitations'].append('新增五阶段按冻结文本实证回填。精简包省略部分历史截图，未重新逐图核验。原有单元报告字段与专项报告分别保留。')
    if args.write:
        stamp = now.strftime('%Y%m%d-%H%M%S')
        for path in (TASKS, AUDIT, AUDIT.with_suffix('.txt'), WORKBOOK):
            previous = OUT / f'{path.stem}-回填前-{stamp}{path.suffix}'
            with previous.open('xb') as stream:
                stream.write(path.read_bytes())
            if path == AUDIT:
                audit['source_artifacts']['previousAudit'] = {'path': relative(previous), 'sha256': sha(previous)}
            elif path == AUDIT.with_suffix('.txt'):
                audit['source_artifacts']['previousAuditText'] = {'path': relative(previous), 'sha256': sha(previous)}
        TASKS.write_bytes(encode(tasks))
        audit['source_artifacts']['taskJSON'] = {'path': relative(TASKS), 'sha256': sha(TASKS)}
        AUDIT.write_bytes(encode(audit))
        lines = ['98 项当前覆盖与剩余工作', '18 个本地验证阶段。正式服务与生产验收见各项边界。', '']
        for row in audit['rows']:
            lines.extend([f'{row["id"]} | {row["task_table_status_at_audit"]} | {row["title"]}',
                          '原文段落 ' + ', '.join(row['source_ids']),
                          row['declaredCurrentScope']])
            for label, field in [('剩余软件', 'softwareNotImplemented'), ('外部输入', 'externalInputs'),
                                 ('生产或验收', 'productionOrAcceptanceGates')]:
                if row[field]:
                    lines.append(label)
                    lines.extend('- ' + value for value in row[field])
            lines.extend('证据 ' + entry['path'] for entry in row['evidence'])
            lines.append('')
        AUDIT.with_suffix('.txt').write_bytes(('\n'.join(lines) + '\n').encode())
    print(json.dumps({'verifiedStages': 18, 'updated': changed, 'written': args.write}, ensure_ascii=False))


if __name__ == '__main__':
    main()
