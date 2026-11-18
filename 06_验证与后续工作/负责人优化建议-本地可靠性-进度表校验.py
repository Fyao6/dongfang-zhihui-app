"""Read-only OOXML preservation check for three scoped Stage31 rows."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

source = Path(__file__).with_name('负责人优化建议-支付回调-进度表校验.py')
spec = importlib.util.spec_from_file_location('stage31_book_reader', source)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
reader.ALLOWED_VALUES = {
    '进度总览': {'A3', 'C14', 'C15', 'D11', 'E11', 'D14', 'E14', 'D15', 'A23', 'D23', 'E23'},
    '98项明细': {col+str(row) for row in (64,66,102) for col in ('E','F','G')},
    '优化任务表': {'A4','I69','I71','I107'},
    '原文逐段对照': set(),
}
ROOT = Path(__file__).resolve().parents[1]
ROWS = [('SVT01',64,69),('SVT03',66,71),('X03',102,107)]

def verify(original,candidate):
    before,after = reader.read_book(original),reader.read_book(candidate)
    extra=[]
    for name in before['order']:
        old,new=before['sheets'][name]['rows'],after['sheets'][name]['rows']
        allowed = {'64','66','102'} if name=='98项明细' else {'69','71','107'} if name=='优化任务表' else {'11','14','23'} if name=='进度总览' else set()
        for row in old.keys()|new.keys():
            left,right=dict(old.get(row,{})),dict(new.get(row,{}))
            if row in allowed:
                for key in ('ht','customHeight'):
                    left.pop(key,None);right.pop(key,None)
                old[row]=deepcopy(new.get(row))
            if left!=right:extra.append(name+':row_format:'+row)
    result=reader.verify(before,after)
    result['violations'].extend(extra)
    result.update(preservedOtherRequirements=95,scope='SVT01/SVT03/X03 local reliability evidence and related stage summaries; all other 95 rows, source text, formulas, styles and media preserved.')
    if '98项明细' in after['sheets']:
        cells=after['sheets']['98项明细']['cells'];statuses={}
        evidence=sum(cells['E'+str(row)]['value']=='已有证据' for row in range(6,104))
        for row in range(6,104):
            state=cells['D'+str(row)]['value'];statuses[state]=statuses.get(state,0)+1
        result.update(rowsWithEvidence=evidence,otherRows=98-evidence,statusCounts=statuses)
        if evidence!=72 or statuses!={'进行中':70,'待资料':16,'待验收':9,'待实施':3}:result['violations'].append('unexpected_status_or_evidence_count')
        for identifier,row,_ in ROWS:
            if any(cells[col+str(row)]['value']!=expected for col,expected in [('A',identifier),('D','进行中'),('E','已有证据')]):result['violations'].append(identifier+'_state')
    if '优化任务表' in after['sheets']:
        cells=after['sheets']['优化任务表']['cells']
        for identifier,_,row in ROWS:
            if cells['A'+str(row)]['value']!=identifier or cells['K'+str(row)]['value']!='进行中':result['violations'].append(identifier+'_original_state')
    result['pass']=result['scopePreserved']=not result['violations']
    result.update(originalPath=Path(original).resolve().relative_to(ROOT).as_posix(),originalSha256=hashlib.sha256(Path(original).read_bytes()).hexdigest(),candidateSha256=hashlib.sha256(Path(candidate).read_bytes()).hexdigest())
    return result

if __name__=='__main__':
    original,candidate,report=sys.argv[1:4];result=verify(original,candidate)
    Path(report).write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':result['pass'],'changedCells':len(result['changedCells']),'violations':result['violations'][:20]},ensure_ascii=True))
    sys.exit(0 if result['pass'] else 1)
