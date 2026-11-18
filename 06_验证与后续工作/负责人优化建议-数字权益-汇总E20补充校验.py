"""Read-only proof: the verified stage25 intermediate workbook changes only summary E20."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

source=Path(__file__).with_name('负责人优化建议-支付回调-进度表校验.py')
spec=importlib.util.spec_from_file_location('scope_ooxml_reader',source)
reader=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(intermediate,candidate,original_report):
    before,after=reader.read_book(intermediate),reader.read_book(candidate)
    reader.ALLOWED_VALUES={name:({'E20'} if name=='进度总览' else set()) for name in before['order']}
    result=reader.verify(before,after)
    for name in before['order']:
        if before['sheets'][name]['rows']!=after['sheets'][name]['rows']:
            result['violations'].append(name+':unexpected_row_format')
    if [(row['sheet'],row['cell']) for row in result['changedCells']]!=[('进度总览','E20')]:
        result['violations'].append('expected_exactly_summary_E20')
    baseline=json.loads(Path(original_report).read_text(encoding='utf-8'))
    if not baseline['pass'] or not baseline['scopePreserved'] or baseline['preservedOtherRequirements']!=97:
        result['violations'].append('intermediate_scope_report_not_passed')
    if baseline['candidateSha256']!=sha(intermediate):
        result['violations'].append('intermediate_bytes_do_not_match_passed_report')
    result.update(pass_=not result['violations'],scopePreserved=not result['violations'],preservedOtherRequirements=97,
        scope='Exactly one directly related summary value, 进度总览!E20; intermediate stage25 SH06 proof preserved.',
        intermediateSha256=sha(intermediate),candidateSha256=sha(candidate),finalActualSHA256=sha(candidate),
        intermediateScopeReport=str(Path(original_report).resolve()),intermediateScopeReportSha256=sha(original_report))
    result['pass']=result.pop('pass_')
    return result,baseline


if __name__=='__main__':
    intermediate,candidate,original_report,supplementary_report,final_report=sys.argv[1:6]
    result,baseline=verify(intermediate,candidate,original_report)
    supplement=Path(supplementary_report)
    supplement.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    if result['pass']:
        final={**baseline,'candidateSha256':result['candidateSha256'],'finalActualSHA256':result['finalActualSHA256'],
            'pass':True,'scopePreserved':True,'preservedOtherRequirements':97,
            'scope':baseline['scope']+' Authorized summary E20 correction verified separately.',
            'changedCells':baseline['changedCells']+result['changedCells'],
            'intermediateScopeReport':{'path':str(Path(original_report).resolve()),'sha256':sha(original_report)},
            'supplementaryEvidence':{'path':str(supplement.resolve()),'sha256':sha(supplement),'additionalCells':['进度总览!E20']}}
        Path(final_report).write_bytes((json.dumps(final,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':result['pass'],'scopePreserved':result['scopePreserved'],'preservedOtherRequirements':97,'violations':result['violations'],'finalActualSHA256':result['finalActualSHA256']},ensure_ascii=True))
    sys.exit(0 if result['pass'] else 1)
