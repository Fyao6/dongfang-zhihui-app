"""Read-only final delivery audit, after the frozen receipt and narrow table updates."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-数字权益'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text(encoding='utf-8'))


def verify():
    receipt_path = OUT / (PREFIX + '-实施记录.json')
    receipt = read(receipt_path)
    assert receipt['pass'] is True and receipt['stage'] == 25
    verified = {}
    for field in ('source_hashes', 'build_hashes', 'visualEvidenceSHA256', 'preservedHistoricalSHA256'):
        for name, expected in receipt[field].items():
            path = (ROOT / name).resolve()
            assert path.is_relative_to(ROOT) and sha(path) == expected, name
            verified[name] = expected
    totals = {'Python': 0, 'Cloud': 0}
    for name, expected in receipt['privateDiagnosticBoundary']['documentsSHA256'].items():
        assert sha(ROOT / name) == expected, name
        verified[name] = expected
    assert len(receipt['verification']) == 14
    for label, gate in receipt['verification'].items():
        path = ROOT / gate['path']
        assert sha(path) == gate['sha256'], label
        raw = read(path)
        run = raw.get('latest', raw)
        assert run['pass'] is True and run.get('failed', 0) == 0
        assert len(run['results']) == gate['passed'] and all(r['pass'] for r in run['results'])
        launcher = run['digitalEntitlementsLauncher']
        assert launcher['identityUnchanged'] is True
        for name, expected in launcher['sourceAndBuildHashes'].items():
            assert sha(ROOT / name) == expected, (label, name)
            verified[name] = expected
        verified[gate['path']] = gate['sha256']
        totals['Python' if label.startswith('Python') else 'Cloud'] += gate['passed']
    assert totals == {'Python': 174, 'Cloud': 174}, totals
    sheets = {}
    for suffix, workbook in [('-负责人进度表回填校验.json', '东方智慧APP需求进度表-20261116.xlsx'),
                             ('-原98项任务表回填校验.json', '东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        result = read(OUT / (PREFIX + suffix))
        assert result['pass'] is True and result['scopePreserved'] is True
        assert result['preservedOtherRequirements'] == 97
        assert result['candidateSha256'] == sha(OUT / workbook)
        sheets[workbook] = result['candidateSha256']
    handoff = read(OUT / (PREFIX + '-任务及交接回填核验.json'))
    assert handoff['pass'] is True and handoff['stage'] == 25
    for name, expected in handoff['hashes'].items():
        assert sha(ROOT / name) == expected, name
        verified[name] = expected
    memory = read(OUT / '公司同步-进度与记忆.json')
    assert memory['development']['verifiedLocalStages'] == 25
    queue = read(OUT / '负责人优化建议-交付收尾推进.json')
    assert queue['groups'][2]['status'] == '本地已验证' and queue['current'] == 'PR04/PR05'
    target = OUT / (PREFIX + '-最终交付核验.json')
    assert not target.exists(), 'Do not overwrite a frozen delivery audit.'
    result = {'pass': True, 'stage': 25, 'at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
              'receiptSHA256': sha(receipt_path), 'verifiedFiles': len(verified), 'sheets': sheets,
              'allFourteenGatesPassedAndLauncherIdentitiesVerified': True,
              'perBackendPassed': totals, 'oldReceiptsReportsPreviewDBUnchanged': True,
              'languageScope': 'APP四语，后台中文；不代表实机或藏语母语审校',
              'productionEnabled': False, 'zipRepacked': False, 'pushed': False}
    target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    verify()
