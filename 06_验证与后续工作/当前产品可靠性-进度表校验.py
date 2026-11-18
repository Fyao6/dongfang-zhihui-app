"""Read-only preservation check: original 98 requirements plus three appended requests."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
source = OUT / '负责人优化建议-支付回调-进度表校验.py'
spec = importlib.util.spec_from_file_location('current_reliability_book_reader', source)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
reader.ALLOWED_VALUES = {
    '进度总览': {'A3', 'C14', 'C15', 'D11', 'E11', 'D14', 'E14', 'D15', 'A23', 'D23', 'E23'},
    '98项明细': {col + str(row) for row in (64, 66, 102) for col in ('E', 'F', 'G')},
    '优化任务表': {'A4', 'I69', 'I71', 'I107'},
    '原文逐段对照': set(),
}
ROWS = [('SVT01', 64, 69), ('SVT03', 66, 71), ('X03', 102, 107)]
ADDITIONAL_IDS = ['ADD-WEB', 'ADD-GROWTH', 'ADD-DAILY']
STATUS = {'进行中': 70, '待资料': 16, '待验收': 9, '待实施': 3}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify(original, candidate, previews_file, detail_candidate):
    before, after = reader.read_book(original), reader.read_book(candidate)
    errors = []
    if after['order'] != before['order'] + ['追加需求']:
        errors.append('append_exact_one_sheet_without_reordering')
    if '追加需求' in before['sheets']:
        errors.append('original_already_contains_additional_sheet')
    extra = after['sheets'].get('追加需求', {}).get('cells', {})
    values = lambda row: [extra.get(col + str(row), {}).get('value') for col in 'ABCDEF']
    if values(1) != ['编号', '追加需求', '当前状态', '本地验证范围', '尚待范围', '证据']:
        errors.append('additional_headers')
    for row, identifier in enumerate(ADDITIONAL_IDS, 2):
        if values(row)[0] != identifier or values(row)[2] != '本地已验证':
            errors.append('additional_identity_or_state_' + identifier)
        if any(not isinstance(v, str) or not v.strip() for v in values(row)):
            errors.append('additional_empty_field_' + identifier)
    for address, cell in extra.items():
        if cell['formula'] is not None or (cell['value'] is not None and address not in {c + str(r) for c in 'ABCDEF' for r in range(1, 5)}):
            errors.append('additional_out_of_scope_cell_' + address)
    comparable = deepcopy(after)
    comparable['order'] = list(before['order'])
    comparable['sheets'].pop('追加需求', None)
    for name in before['order']:
        old, new = before['sheets'][name]['rows'], comparable['sheets'][name]['rows']
        allowed = {'64', '66', '102'} if name == '98项明细' else {'69', '71', '107'} if name == '优化任务表' else {'11', '14', '23'} if name == '进度总览' else set()
        for row in old.keys() | new.keys():
            left, right = dict(old.get(row, {})), dict(new.get(row, {}))
            if row in allowed:
                for key in ('ht', 'customHeight'):
                    left.pop(key, None)
                    right.pop(key, None)
                old[row] = deepcopy(new.get(row))
            if left != right:
                errors.append(name + ':row_format:' + row)
    result = reader.verify(before, comparable)
    result['violations'].extend(errors)
    detail = after if '98项明细' in after['sheets'] else reader.read_book(detail_candidate)
    cells = detail['sheets']['98项明细']['cells']
    evidence = sum(cells['E' + str(row)]['value'] == '已有证据' for row in range(6, 104))
    statuses = {}
    for row in range(6, 104):
        value = cells['D' + str(row)]['value']
        statuses[value] = statuses.get(value, 0) + 1
    if evidence != 72 or statuses != STATUS:
        result['violations'].append('original98_status_or_evidence_count')
    for identifier, row, _ in ROWS:
        if any(cells[col + str(row)]['value'] != value for col, value in [('A', identifier), ('D', '进行中'), ('E', '已有证据')]):
            result['violations'].append(identifier + '_detail_state')
    if '优化任务表' in after['sheets']:
        old_cells = after['sheets']['优化任务表']['cells']
        for identifier, _, row in ROWS:
            if old_cells['A' + str(row)]['value'] != identifier or old_cells['K' + str(row)]['value'] != '进行中':
                result['violations'].append(identifier + '_original_state')
    previews = json.loads(Path(previews_file).read_text('utf-8'))
    actual_previews = []
    for item in previews:
        if item['book'] != (0 if '98项明细' in after['sheets'] else 1):
            continue
        p = (ROOT / item['path']).resolve()
        if p.parent != OUT or p.suffix != '.png' or not p.name.startswith('当前产品可靠性-进度表-') or sha(p) != item['sha256'] or item['sheet'] not in after['sheets']:
            result['violations'].append('actual_visual_preview_binding')
        actual_previews.append({k: item[k] for k in ('path', 'sha256', 'sheet', 'range')})
    if not any(x['sheet'] == '追加需求' for x in actual_previews):
        result['violations'].append('additional_sheet_preview_missing')
    result.update(preservedOtherRequirements=95, scope='SVT01/SVT03/X03; original 98 requirement denominator and all other 95 rows preserved. Three user-added requests are isolated on the appended 追加需求 sheet.',
                  rowsWithEvidence=evidence, otherRows=98 - evidence, statusCounts=statuses,
                  additionalRequirements={'sheet': '追加需求', 'rows': 3, 'pass': not errors},
                  visualPreviews=actual_previews,
                  originalPath=Path(original).resolve().relative_to(ROOT).as_posix(), originalSha256=sha(original),
                  candidateSha256=sha(candidate), detailCandidateSha256=sha(detail_candidate))
    result['pass'] = result['scopePreserved'] = not result['violations']
    return result


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print(json.dumps({'status': 'prepared-not-run', 'writesWorkbook': False, 'scope': [r[0] for r in ROWS], 'additionalRequirements': 3}))
    else:
        assert len(sys.argv) == 6
        original, candidate, report, previews, detail = sys.argv[1:]
        result = verify(original, candidate, previews, detail)
        with Path(report).open('xb') as handle:
            handle.write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print(json.dumps({'pass': result['pass'], 'violations': result['violations'][:20]}, ensure_ascii=True))
        sys.exit(0 if result['pass'] else 1)
