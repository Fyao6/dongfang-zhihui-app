"""Read-only Stage30 reconciliation before local reliability exercises/delivery."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
NAME = '负责人优化建议-本地可靠性-实施前核对.json'
PROOF = '06_验证与后续工作/负责人优化建议-卡组迁移-最终交付核验.json'
EXPECTED = '752e36ad70d6812727849f0fa49262c426ef161a911b59f66831cd0617e12f07'
MUTABLE = {
    'AGENTS.md', '公司同步-先读我.txt',
    '06_验证与后续工作/东方智慧APP需求进度表-20261116.xlsx',
    '06_验证与后续工作/东方智慧APP优化任务表_依据v1.0_20261112.xlsx',
    '06_验证与后续工作/负责人优化建议-任务拆解.json',
    '06_验证与后续工作/负责人优化建议-98项最终覆盖审计.json',
    '06_验证与后续工作/负责人优化建议-98项最终覆盖审计.txt',
    '06_验证与后续工作/公司同步-进度与记忆.json',
    '06_验证与后续工作/负责人优化建议-交付收尾推进.json',
}

def sha(file):
    h = hashlib.sha256()
    with file.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def local(name):
    assert not Path(name).is_absolute()
    file = (ROOT / name).resolve()
    assert file.is_relative_to(ROOT) and file.is_file()
    return file

def main():
    target = OUT / NAME
    assert not target.exists(), 'Do not overwrite the pre-mutation baseline'
    assert sha(local(PROOF)) == EXPECTED
    proof = json.loads(local(PROOF).read_text('utf-8'))
    assert proof['pass'] and proof['stage'] == 30
    assert proof['perBackendPassed'] == {'Python': 195, 'Cloud': 195}
    checked = dict(proof['verifiedSHA256'])
    assert len(checked) == proof['verifiedFiles'] == 3426
    checked[PROOF] = EXPECTED
    for name, digest in checked.items():
        assert sha(local(name)) == digest, ('Stage30 input/evidence changed', name)
    assert MUTABLE <= checked.keys()
    result = {
        'pass': True, 'at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'module': 'SVT01/SVT03/X03 local reliability', 'nextLocalStage': 31,
        'previousFinalProof': {'path': PROOF, 'sha256': EXPECTED},
        'previousEvidenceCount': len(checked),
        'allStage30SourceBuildAndEvidenceSHA256': checked,
        'protectedHistoricalSHA256': {n: h for n, h in checked.items() if n not in MUTABLE},
        'authorizedWorkbookBaselineSHA256': {n: checked[n] for n in MUTABLE if n.endswith('.xlsx')},
        'mutableHandoffAtStartSHA256': {n: checked[n] for n in MUTABLE if not n.endswith('.xlsx')},
        'productChangesAuthorizedForThisExercise': False,
        'productionEnabled': False, 'zipRepacked': False, 'pushed': False,
    }
    target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'checked': len(checked),
                      'protected': len(result['protectedHistoricalSHA256']),
                      'sha256': sha(target)}, ensure_ascii=True))

if __name__ == '__main__':
    main()
