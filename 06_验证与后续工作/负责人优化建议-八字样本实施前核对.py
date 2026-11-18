"""Stage29 baseline: verify stage28 bytes and classify mutable delivery inputs.

No business service, test, product mutation or artifact author is started here.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-八字样本'
RECEIPT = OUT / '负责人优化建议-支付路由-实施记录.json'
PROOF = OUT / '负责人优化建议-支付路由-最终交付核验.json'
CONTRACT = OUT / (PREFIX + '-实施合同.json')
RECEIPT_SHA = '876beea0dcd59e2ab0c70df47f3561b61e9ba156080ad33f60189fceb105acc6'
PROOF_SHA = '96ea609a28c18be0c89f18a7a6c41e5b47687cffb2d5c77a7d8b2dc899bb5177'
CONTRACT_SHA = '59c220962dbe03b774da553495c79beed3dd47010ae84d82b6ef42e5b310a9dc'


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
    assert receipt['stage'] == proof['stage'] == 28 and receipt['pass'] and proof['pass']
    assert proof['verifiedFiles'] == len(proof['verifiedSHA256']) == 1719
    assert contract['stage'] == 29 and contract['qaPlan']['perBackend'] == 186
    assert sum(contract['qaPlan']['suites'].values()) == 186
    previous = dict(proof['verifiedSHA256'])
    for name, expected in previous.items():
        assert sha(local(name)) == expected, ('Stage28 current byte mismatch', name)
    previous[PROOF.relative_to(ROOT).as_posix()] = PROOF_SHA
    input_map = receipt['reportIdentityHashes']
    assert len(input_map) == 393
    shared_tests = {'06_验证与后续工作/全量回归.cjs', '06_验证与后续工作/公网适配全量回归.cjs'}
    source_names = {name for name in input_map if name.startswith(('03_', '04_')) or name in shared_tests}
    # Stage29 may add locale entries, not silently replace the vendor or original media.
    locale_names = {
        '04_研发源码/app/r4/i18n-extra.json',
        '04_研发源码/app/r4/i18n-bo.json',
        '04_研发源码/app/r4/i18n-bo-draft.json',
        '06_验证与后续工作/四语文案清单.json',
    }
    source_names.update(name for name in locale_names if name in previous)
    build_names = set(receipt['build_hashes'])
    handoff = read(OUT / '负责人优化建议-支付路由-任务及交接回填核验.json')
    handoff_names = set(handoff['hashes'])
    assert len(handoff_names) == 7
    books = {
        '06_验证与后续工作/东方智慧APP需求进度表-20261116.xlsx':
            'e646886062be8c263a9648fbac8b2c88855872bb6e094b61a4d1d70ac9e5584d',
        '06_验证与后续工作/东方智慧APP优化任务表_依据v1.0_20261112.xlsx':
            'e713b77ab75e4f1a1c5c3fe766c07b3fd4be51e5ece0fb8c28e9055a8ee07ee8',
    }
    for name, expected in books.items():
        assert sha(local(name)) == expected
    mutable = source_names | build_names | handoff_names | set(books)
    protected = {name: value for name, value in previous.items() if name not in mutable}
    # Every owned stage28 QA/helper/receipt remains immutable. Shared full scripts
    # may only gain the fresh namespace; old functional assertions stay intact.
    for name in protected:
        assert sha(local(name)) == protected[name]
    for name in ('负责人优化建议-支付路由测试工具.cjs', '负责人优化建议-支付路由验收冻结.py'):
        assert '06_验证与后续工作/' + name in protected
    preview = OUT / '负责人优化建议-隔离预览.sqlite3'
    assert sha(preview) == 'a19650e3079625ebf44be7b274acfb7932a506df29586a78726241915f0811c6'
    return {
        'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'status': 'authorized-local-implementation-not-accepted',
        'currentStage': 28, 'stageToImplement': 29, 'taskIds': ['B10','B12'],
        'metadataCorrection': {'previousBaseline':'06_验证与后续工作/负责人优化建议-八字样本-实施前核对.json','previousSHA256':'4ba7e86c9a76710fbc978918c498ab42a58ff4875937e3a62a7e5c875dd6aa6c','meaning':'Only inherited descriptive stage labels corrected to28; all previous receipt/proof/byte checks and stageToImplement29 were already correct. Previous baseline bytes preserved.'},
        'contract': {'path': CONTRACT.relative_to(ROOT).as_posix(), 'sha256': CONTRACT_SHA},
        'previousReceipt': {'path': RECEIPT.relative_to(ROOT).as_posix(), 'sha256': RECEIPT_SHA},
        'previousFinalProof': {'path': PROOF.relative_to(ROOT).as_posix(), 'sha256': PROOF_SHA},
        'sourceHashes': {name: sha(local(name)) for name in sorted(source_names)},
        'buildHashes': {name: sha(local(name)) for name in sorted(build_names)},
        'protectedHistoricalSHA256': protected,
        'authorizedWorkbookBaselineSHA256': books,
        'mutableHandoffAtStartSHA256': {name: sha(local(name)) for name in sorted(handoff_names)},
        'files': previous, 'previousVerifiedFiles': 1719,
        'previewDBSHA256': sha(preview),
        'qaPlan': contract['qaPlan'],
        'boundaries': ['No original/preview DB or default Wrangler state used for tests.',
                       'Frozen stage28 QA, receipts, reports, runtime bundles and media are preserved.',
                       'Same-library sample recomputation is not professional validation;teacherConfirmed=false; no automatic personal birth upload.',
                       'No service/test/build/sheet author was started by this preflight.'],
    }


if __name__ == '__main__':
    target = OUT / (PREFIX + '-实施前核对-rev2.json')
    assert not target.exists(), 'Never replace a baseline'
    result = collect()
    target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'stage': 29, 'files': len(result['files']),
                      'protected': len(result['protectedHistoricalSHA256']), 'sha256': sha(target)}))
