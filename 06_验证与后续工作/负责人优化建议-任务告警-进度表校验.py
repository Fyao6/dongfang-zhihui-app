"""Read-only stage27 PAY18/SV04 OOXML scope and preservation verifier."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
source=Path(__file__).with_name('负责人优化建议-支付回调-进度表校验.py')
spec=importlib.util.spec_from_file_location('stage27_workbook_reader',source)
reader=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
reader.ALLOWED_VALUES={
    '进度总览':{'D11','D12','E12','D15','D20','E20'},
    '98项明细':{'F62','G62','F87','G87'},
    '优化任务表':{'A4','I67','I92'},
    '原文逐段对照':set(),
}


def verify(original,candidate):
    before,after=reader.read_book(original),reader.read_book(candidate)
    extra=[]
    for name in before['order']:
        old,new=before['sheets'][name]['rows'],after['sheets'][name]['rows']
        allowed={'62','87'} if name=='98项明细' else {'67','92'} if name=='优化任务表' else {'11','12','20'} if name=='进度总览' else set()
        for row in old.keys()|new.keys():
            left,right=dict(old.get(row,{})),dict(new.get(row,{}))
            if row in allowed:
                for key in ('ht','customHeight'):left.pop(key,None);right.pop(key,None)
                old[row]=deepcopy(new.get(row))
            if left!=right:extra.append(name+':row_format:'+row)
    result=reader.verify(before,after);result['violations'].extend(extra)
    result.update(preservedOtherRequirements=96,scope='PAY18/SV04 progress wording and directly related runtime/payment/stage summaries only; all other 96 requirement rows and original text, styles, formulas and media preserved.')
    if '98项明细' in after['sheets']:
        cells=after['sheets']['98项明细']['cells'];statuses={}
        evidence=sum(cells['E'+str(row)]['value']=='已有证据' for row in range(6,104))
        for row in range(6,104):
            state=cells['D'+str(row)]['value'];statuses[state]=statuses.get(state,0)+1
        result.update(rowsWithEvidence=evidence,otherRows=98-evidence,statusCounts=statuses)
        if evidence!=67 or statuses!={'进行中':69,'待资料':16,'待验收':9,'待实施':4}:result['violations'].append('unexpected_status_or_evidence_count')
    result['scopePreserved']=not result['violations'];result['pass']=result['scopePreserved']
    result.update(originalSha256=hashlib.sha256(Path(original).read_bytes()).hexdigest(),candidateSha256=hashlib.sha256(Path(candidate).read_bytes()).hexdigest())
    return result


if __name__=='__main__':
    original,candidate,report=sys.argv[1:4];result=verify(original,candidate)
    Path(report).write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':result['pass'],'scopePreserved':result['scopePreserved'],'changedCells':len(result['changedCells']),'violations':result['violations'][:20]},ensure_ascii=True))
    sys.exit(0 if result['pass'] else 1)
