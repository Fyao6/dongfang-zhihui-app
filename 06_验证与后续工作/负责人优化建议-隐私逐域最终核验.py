"""Read-only final stage26 audit; writes only a new, immutable audit receipt."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-隐私逐域'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text(encoding='utf-8'))


def verify():
    receipt_path = OUT / (PREFIX + '-实施记录.json')
    receipt = read(receipt_path)
    assert receipt['pass'] is True and receipt['stage'] == 26
    assert receipt['taskIds'] == ['PR04', 'PR05']
    freezer_path = OUT / (PREFIX + '验收冻结.py')
    assert sha(freezer_path) == receipt['freezeHelperSHA256']
    spec = importlib.util.spec_from_file_location('stage26_final_readonly', freezer_path)
    freezer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freezer)
    current = freezer.collect()
    verified = {}
    for field in ('verification', 'reportIdentityHashes', 'source_hashes', 'build_hashes',
                  'visualEvidenceSHA256', 'preservedHistoricalSHA256', 'diagnosticEvidenceSHA256'):
        assert receipt[field] == current[field], field
        if field != 'verification':
            for name, expected in receipt[field].items():
                path = (ROOT / name).resolve()
                assert path.is_relative_to(ROOT) and sha(path) == expected, name
                verified[name] = expected
    totals = {'Python': 0, 'Cloud': 0}
    assert len(receipt['verification']) == 18
    for label, gate in receipt['verification'].items():
        assert sha(ROOT / gate['path']) == gate['sha256'], label
        verified[gate['path']] = gate['sha256']
        totals['Python' if label.startswith('Python') else 'Cloud'] += gate['passed']
    assert totals == {'Python': 227, 'Cloud': 227}, totals
    sheets = {}
    for suffix, workbook in [('-负责人进度表回填校验.json', '东方智慧APP需求进度表-20261116.xlsx'),
                             ('-原98项任务表回填校验.json', '东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        report_path = OUT / (PREFIX + suffix)
        result = read(report_path)
        assert result['pass'] is True and result['scopePreserved'] is True and not result['violations']
        assert result['preservedOtherRequirements'] == 96
        assert result['candidateSha256'] == sha(OUT / workbook)
        assert result['originalSha256'] == receipt['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/' + workbook]
        sheets[workbook] = result['candidateSha256']
        verified[report_path.relative_to(ROOT).as_posix()] = sha(report_path)
        verified[(OUT / workbook).relative_to(ROOT).as_posix()] = result['candidateSha256']
    handoff_path = OUT / (PREFIX + '-任务及交接回填核验.json')
    handoff = read(handoff_path)
    assert handoff['pass'] is True and handoff['stage'] == 26
    assert handoff['receiptSHA256'] == sha(receipt_path)
    assert handoff['updatedTaskIds'] == ['PR04', 'PR05']
    assert handoff['other96TaskAndAuditRowsPreserved'] is True
    verified[handoff_path.relative_to(ROOT).as_posix()] = sha(handoff_path)
    verified[receipt_path.relative_to(ROOT).as_posix()] = sha(receipt_path)
    for name, expected in handoff['hashes'].items():
        assert sha(ROOT / name) == expected, name
        verified[name] = expected
    memory = read(OUT / '公司同步-进度与记忆.json')
    assert memory['development']['verifiedLocalStages'] == 26
    queue = read(OUT / '负责人优化建议-交付收尾推进.json')
    assert queue['groups'][3]['status'] == '本地已验证' and queue['current'] == 'PAY18/SV04'
    assert queue['groups'][4]['status'] == '进行中'
    for name in [PREFIX + '验收冻结.py', PREFIX + '进度回填.py', PREFIX + '最终核验.py',
                 PREFIX + '-进度表回填.mjs', PREFIX + '-进度表校验.py']:
        path = OUT / name
        verified[path.relative_to(ROOT).as_posix()] = sha(path)
    guide = ROOT / '05_后台与研发说明/本人资料逐域清点与清理说明.txt'
    verified[guide.relative_to(ROOT).as_posix()] = sha(guide)
    target = OUT / (PREFIX + '-最终交付核验.json')
    assert not target.exists(), 'Do not overwrite an existing final audit'
    result = {'pass': True, 'stage': 26, 'at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
              'receiptSHA256': sha(receipt_path), 'verifiedFiles': len(verified), 'sheets': sheets,
              'deliveryHelperAndGuideSHA256': {name: digest for name, digest in verified.items()
                  if Path(name).name in [PREFIX + '验收冻结.py', PREFIX + '进度回填.py', PREFIX + '最终核验.py',
                                        PREFIX + '-进度表回填.mjs', PREFIX + '-进度表校验.py', guide.name]},
              'allEighteenGatesPassedWithFreshSuccessfulChildren': True, 'perBackendPassed': totals,
              'oldReceiptsReportsPreviewDBUnchanged': True,
              'languageScope': 'APP四语与后台中文的本机浏览器验证；非实机或藏语母语审校。',
              'paginationScope': '记录列表实际跨50；其余元数据列表未专门做超过50条压力。',
              'erasureScope': '本方SQLite逻辑清理/Cloud当前对象删除及HEAD缺失；非安全擦除、备份或供应商删除。',
              'productionEnabled': False, 'zipRepacked': False, 'pushed': False}
    target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    verify()
