"""Stage28 baseline: verify stage27 bytes and classify mutable delivery inputs.

No business service, test, product mutation or artifact author is started here.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-支付路由'
RECEIPT = OUT / '负责人优化建议-任务告警-实施记录.json'
PROOF = OUT / '负责人优化建议-任务告警-最终交付核验.json'
CONTRACT = OUT / (PREFIX + '-实施合同.json')
RECEIPT_SHA = 'f722a22ca5a1b6f6dbcd71c79815c2d0a7d5cc084e06e84c08c8fa55eb0ff116'
PROOF_SHA = '715b2f89d2ccd5d7d5d0d6e6cd8f08306ae142454d4c8640904213c6b33c8da1'
CONTRACT_SHA = 'bc8e5a44aa4cbf900de29dc25e6fa8c18c3d3f2140a7802f41ca1508f4bd6d86'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def local(name):
    p = (ROOT / name).resolve()
    assert p.is_relative_to(ROOT) and p.is_file(), name
    return p


def collect():
    for path, expected in ((RECEIPT, RECEIPT_SHA), (PROOF, PROOF_SHA), (CONTRACT, CONTRACT_SHA)):
        assert sha(path) == expected, path.name
    receipt, proof, contract = read(RECEIPT), read(PROOF), read(CONTRACT)
    assert receipt['stage'] == proof['stage'] == 27 and receipt['pass'] and proof['pass']
    assert proof['verifiedFiles'] == len(proof['verifiedSHA256']) == 1257
    assert contract['stage'] == 28 and contract['qaPlan']['perBackend'] == 263
    assert sum(contract['qaPlan']['suites'].values()) == 263
    previous = dict(proof['verifiedSHA256'])
    for name, expected in previous.items():
        assert sha(local(name)) == expected, ('Stage27 current byte mismatch', name)
    previous[PROOF.relative_to(ROOT).as_posix()] = PROOF_SHA
    input_map = receipt['reportIdentityHashes']
    assert len(input_map) == 329
    shared_tests = {'06_验证与后续工作/全量回归.cjs', '06_验证与后续工作/公网适配全量回归.cjs'}
    source_names = {name for name in input_map if name.startswith(('03_', '04_')) or name in shared_tests}
    # Stage28 may add locale entries, not silently replace the vendor or original media.
    locale_names = {
        '04_研发源码/app/r4/i18n-extra.json',
        '04_研发源码/app/r4/i18n-bo.json',
        '04_研发源码/app/r4/i18n-bo-draft.json',
        '06_验证与后续工作/四语文案清单.json',
    }
    source_names.update(name for name in locale_names if name in previous)
    build_names = set(receipt['build_hashes'])
    handoff = read(OUT / '负责人优化建议-任务告警-任务及交接回填核验.json')
    handoff_names = set(handoff['hashes'])
    assert len(handoff_names) == 7
    books = {
        '06_验证与后续工作/东方智慧APP需求进度表-20261116.xlsx':
            '378cf3ea91e48971b7d67f31ededa74e493b9dc4145e695144045125e01f1f63',
        '06_验证与后续工作/东方智慧APP优化任务表_依据v1.0_20261112.xlsx':
            '29a8c4167a5ce59514690ab88b662e6f9c45a18f3f3e7eed462cd3a92a8c08b8',
    }
    for name, expected in books.items():
        assert sha(local(name)) == expected
    mutable = source_names | build_names | handoff_names | set(books)
    protected = {name: value for name, value in previous.items() if name not in mutable}
    # Every owned stage27 QA/helper/receipt remains immutable. Shared full scripts
    # may only gain the fresh namespace; old functional assertions stay intact.
    for name in protected:
        assert sha(local(name)) == protected[name]
    for name in ('负责人优化建议-任务告警测试工具.cjs', '负责人优化建议-任务告警验收冻结.py'):
        assert '06_验证与后续工作/' + name in protected
    preview = OUT / '负责人优化建议-隔离预览.sqlite3'
    assert sha(preview) == 'a19650e3079625ebf44be7b274acfb7932a506df29586a78726241915f0811c6'
    return {
        'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'status': 'authorized-local-implementation-not-accepted',
        'currentStage': 27, 'stageToImplement': 28, 'taskIds': ['PAY05'],
        'contract': {'path': CONTRACT.relative_to(ROOT).as_posix(), 'sha256': CONTRACT_SHA},
        'previousReceipt': {'path': RECEIPT.relative_to(ROOT).as_posix(), 'sha256': RECEIPT_SHA},
        'previousFinalProof': {'path': PROOF.relative_to(ROOT).as_posix(), 'sha256': PROOF_SHA},
        'sourceHashes': {name: sha(local(name)) for name in sorted(source_names)},
        'buildHashes': {name: sha(local(name)) for name in sorted(build_names)},
        'protectedHistoricalSHA256': protected,
        'authorizedWorkbookBaselineSHA256': books,
        'mutableHandoffAtStartSHA256': {name: sha(local(name)) for name in sorted(handoff_names)},
        'files': previous, 'previousVerifiedFiles': 1257,
        'previewDBSHA256': sha(preview),
        'qaPlan': contract['qaPlan'],
        'boundaries': ['No original/preview DB or default Wrangler state used for tests.',
                       'Frozen stage27 QA, receipts, reports, runtime bundles and media are preserved.',
                       'Only actual commerce types and sandbox adapter are executable; production is false.',
                       'No service/test/build/sheet author was started by this preflight.'],
    }


if __name__ == '__main__':
    target = OUT / (PREFIX + '-实施前核对.json')
    assert not target.exists(), 'Never replace a baseline'
    result = collect()
    target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'stage': 28, 'files': len(result['files']),
                      'protected': len(result['protectedHistoricalSHA256']), 'sha256': sha(target)}))
