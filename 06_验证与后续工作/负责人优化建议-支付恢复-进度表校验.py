"""Read-only PAY09 scope check, reusing the frozen PAY08 OOXML reader."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

source = Path(__file__).with_name('负责人优化建议-支付回调-进度表校验.py')
spec = importlib.util.spec_from_file_location('pay08_workbook_reader', source)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
reader.ALLOWED_VALUES = {
    '进度总览': {'D12','E12','D15','D20','E20','C12','C15','B29','E29','A28'},
    '98项明细': {'D78','E78','F78','G78'},
    '优化任务表': {'A4','I83','K83'},
    '原文逐段对照': set(),
}


def verify(original, candidate):
    before, after = reader.read_book(original), reader.read_book(candidate)
    raw_before = deepcopy(before)
    extra = []
    for name in before['order']:
        old, new = before['sheets'][name]['rows'], after['sheets'][name]['rows']
        target = '78' if name=='98项明细' else '83' if name=='优化任务表' else None
        for row in old.keys() | new.keys():
            left, right = dict(old.get(row,{})), dict(new.get(row,{}))
            if row==target:
                for key in ('ht','customHeight'):
                    left.pop(key,None); right.pop(key,None)
                old[row] = new.get(row)
            if left!=right:
                extra.append(name+':row_format:'+row)
    result = reader.verify(before, after)
    result['violations'].extend(extra)
    result['scopePreserved'] = not result['violations']
    result['originalSha256'] = hashlib.sha256(Path(original).read_bytes()).hexdigest()
    result['candidateSha256'] = hashlib.sha256(Path(candidate).read_bytes()).hexdigest()
    result['scope'] = 'Only PAY09, directly affected summaries and the PAY09 row height; PAY08 evidence preserved.'
    if '98项明细' in after['sheets']:
        cells = after['sheets']['98项明细']['cells']
        evidence = sum(cells['E'+str(row)]['value']=='已有证据' for row in range(6,104))
        statuses = {}
        for row in range(6,104):
            status = cells['D'+str(row)]['value']
            statuses[status] = statuses.get(status,0)+1
        result.update(rowsWithEvidence=evidence,otherRows=98-evidence,statusCounts=statuses)
        if evidence!=67 or statuses!={'进行中':69,'待资料':16,'待验收':9,'待实施':4}:
            result['violations'].append('PAY09_count_change')
            result['scopePreserved'] = False
    return result


if __name__=='__main__':
    original,candidate,report = sys.argv[1:4]
    result = verify(original,candidate)
    Path(report).write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'scopePreserved':result['scopePreserved'],'changedCells':len(result['changedCells']),'violations':result['violations'][:20]},ensure_ascii=True))
    sys.exit(0 if result['scopePreserved'] else 1)
