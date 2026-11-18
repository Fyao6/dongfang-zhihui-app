"""Read-only check: only 追加需求!B3:F3 values may change."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
spec = importlib.util.spec_from_file_location('growth_stats_book_reader', OUT / '负责人优化建议-支付回调-进度表校验.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
ALLOWED = {'B3', 'C3', 'D3', 'E3', 'F3'}


def verify(original, candidate, expected):
    before, after = reader.read_book(original), reader.read_book(candidate)
    violations, changed = [], []
    for key in ('order', 'nativeTables', 'theme', 'mediaHashes', 'drawings'):
        if before[key] != after[key]:
            violations.append(key)
    if before['sheets'].keys() != after['sheets'].keys():
        violations.append('worksheet_set')
    for name in before['order']:
        old, new = before['sheets'][name], after['sheets'].get(name, {})
        for key in ('rows', 'features'):
            if old[key] != new.get(key):
                violations.append(name + ':' + key)
        for address in old['cells'].keys() | new.get('cells', {}).keys():
            left, right = old['cells'].get(address), new.get('cells', {}).get(address)
            if left == right:
                continue
            changed.append({'sheet': name, 'cell': address, 'valueBefore': left['value'] if left else None, 'valueAfter': right['value'] if right else None})
            if name != '追加需求' or address not in ALLOWED or left is None or right is None:
                violations.append(name + ':outside_value_allowlist:' + address)
            elif {k: v for k, v in left.items() if k != 'value'} != {k: v for k, v in right.items() if k != 'value'}:
                violations.append(name + ':formula_or_style_changed:' + address)
    cells = after['sheets'].get('追加需求', {}).get('cells', {})
    if cells.get('A3', {}).get('value') != 'ADD-GROWTH':
        violations.append('additional_row_identity')
    for address, value in expected.items():
        if cells.get(address, {}).get('value') != value:
            violations.append('expected_value:' + address)
    return {'pass': not violations, 'scopePreserved': not violations,
            'scope': {'sheet': '追加需求', 'valueCells': sorted(ALLOWED)},
            'allOtherCellsFormulasStylesPreserved': not violations,
            'original98AndStage31Preserved': not violations,
            'changedCells': changed, 'violations': violations,
            'originalPath': Path(original).resolve().relative_to(ROOT).as_posix(),
            'originalSha256': sha(original), 'candidateSha256': sha(candidate)}


if __name__ == '__main__':
    assert len(sys.argv) == 5
    original, candidate, expected_file, report = sys.argv[1:]
    result = verify(original, candidate, json.loads(Path(expected_file).read_text('utf-8')))
    Path(report).write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8')) if not Path(report).exists() else sys.exit('Preserve prior report')
    print(json.dumps({'pass': result['pass'], 'changedCells': len(result['changedCells']), 'violations': result['violations']}, ensure_ascii=True))
    sys.exit(0 if result['pass'] else 1)
