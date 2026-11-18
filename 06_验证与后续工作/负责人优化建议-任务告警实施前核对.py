"""Capture stage27 inputs in place; preserve stage26 and all earlier frozen evidence."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-任务告警'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text(encoding='utf-8'))


def capture():
    target = OUT / (PREFIX + '-实施前核对.json')
    assert not target.exists(), 'Never replace a frozen preflight'
    contract = OUT / (PREFIX + '-接口合同.json')
    assert sha(contract) == '5cf969acc2e8eedbc93e973448a425b16d769dc777fb3aa9614335f0219b872b'
    assert read(contract)['revision'] == 4
    receipt_path = OUT / '负责人优化建议-隐私逐域-实施记录.json'
    assert sha(receipt_path) == '3140f3d5ca44e2675f4fe5478da3cdd3f0b7b5f9777981fb7740e41a041cac19'
    receipt = read(receipt_path)
    proof_path = OUT / '负责人优化建议-隐私逐域-最终交付核验.json'
    proof = read(proof_path)
    assert proof['pass'] is True and proof['stage'] == 26 and proof['verifiedFiles'] == 908
    assert proof['receiptSHA256'] == sha(receipt_path)
    assert proof['perBackendPassed'] == {'Python': 227, 'Cloud': 227}
    memory = read(OUT / '公司同步-进度与记忆.json')
    queue = read(OUT / '负责人优化建议-交付收尾推进.json')
    assert memory['development']['verifiedLocalStages'] == 26
    assert queue['current'] == 'PAY18/SV04' and queue['groups'][4]['status'] == '进行中'
    sources = dict(receipt['reportIdentityHashes'])
    builds = dict(receipt['build_hashes'])
    builds['04_研发源码/app/cloud/dist/server/BUILD_ID'] = sources['04_研发源码/app/cloud/dist/server/BUILD_ID']
    protected = {}
    for key in ('preservedHistoricalSHA256', 'visualEvidenceSHA256', 'diagnosticEvidenceSHA256'):
        protected.update(receipt[key])
    protected.update({gate['path']: gate['sha256'] for gate in receipt['verification'].values()})
    protected.update(proof['deliveryHelperAndGuideSHA256'])
    for p in [receipt_path, proof_path, OUT / '负责人优化建议-隐私逐域-任务及交接回填核验.json',
              OUT / '负责人优化建议-隐私逐域-负责人进度表回填校验.json',
              OUT / '负责人优化建议-隐私逐域-原98项任务表回填校验.json']:
        protected[p.relative_to(ROOT).as_posix()] = sha(p)
    books = {'06_验证与后续工作/' + name: digest for name, digest in proof['sheets'].items()}
    docs = {p.relative_to(ROOT).as_posix(): sha(p) for p in [ROOT / 'AGENTS.md', ROOT / '公司同步-先读我.txt',
        OUT / '公司同步-进度与记忆.json', OUT / '负责人优化建议-任务拆解.json',
        OUT / '负责人优化建议-98项最终覆盖审计.json', OUT / '负责人优化建议-98项最终覆盖审计.txt',
        OUT / '负责人优化建议-交付收尾推进.json']}
    files = {**sources, **builds, **protected, **books, **docs}
    for name, expected in files.items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT) and path.is_file() and sha(path) == expected, name
    preview = '06_验证与后续工作/负责人优化建议-隔离预览.sqlite3'
    assert protected[preview] == 'a19650e3079625ebf44be7b274acfb7932a506df29586a78726241915f0811c6'
    result = {'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'status': 'local-implementation-authorized-not-accepted', 'currentStage': 26, 'stageToImplement': 27,
        'taskIds': ['PAY18', 'SV04'], 'contract': {'path': contract.relative_to(ROOT).as_posix(), 'sha256': sha(contract)},
        'currentReceipt': {'path': receipt_path.relative_to(ROOT).as_posix(), 'sha256': sha(receipt_path)},
        'currentFinalProof': {'path': proof_path.relative_to(ROOT).as_posix(), 'sha256': sha(proof_path)},
        'sourceHashes': sources, 'buildHashes': builds, 'protectedHistoricalSHA256': protected,
        'authorizedWorkbookBaselineSHA256': books, 'mutableHandoffAtStartSHA256': docs,
        'previewDBSHA256': protected[preview], 'files': files,
        'boundaries': ['Original preview/production data is read-only; all tests use owned fresh DB/state/ports.',
            'Shared source/build inputs may change for this group; historical receipts/reports/helpers are frozen.',
            'No external recipient, production scheduler, real channel/refund or production deployment is authorized by this preflight.']}
    target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'stageToImplement': 27, 'files': len(files),
        'protectedHistory': len(protected), 'preflightSHA256': sha(target)}, ensure_ascii=False))


if __name__ == '__main__':
    capture()
