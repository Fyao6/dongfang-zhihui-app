"""Additive check of build identities actually recorded by both full regressions."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

root = Path(__file__).resolve().parent.parent
out = root / '06_验证与后续工作'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
checks = []
reports = {}
for name in ['负责人优化建议-支付回调-本轮全量回归结果.json', '负责人优化建议-支付回调-公网适配全量回归结果.json']:
    path = out / name
    raw = json.loads(path.read_text(encoding='utf-8'))
    result = raw.get('latest', raw)
    assert result['pass'] and result['passed'] == 60 and result['failed'] == 0
    reports[name] = {'sha256': sha(path), 'latestAt': result['at']}
    assert result.get('buildHashes'), 'Missing real recorded identities'
    for field, base in [('buildHashes', root / '03_当前APP'), ('cloudBuildHashes', root / '04_研发源码/app/cloud')]:
        for relative, expected in result.get(field, {}).items():
            actual_path = base / relative
            actual = sha(actual_path)
            checks.append({'report': name, 'field': field, 'path': actual_path.relative_to(root).as_posix(),
                           'expected': expected, 'actual': actual, 'matches': actual == expected})
assert len(checks) == 12 and all(item['matches'] for item in checks)
receipt = out / '负责人优化建议-支付回调-实施记录.json'
data = {'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'pass': True, 'checked': len(checks), 'matched': len(checks),
        'receipt': {'path': receipt.relative_to(root).as_posix(), 'sha256': sha(receipt)},
        'scope': '完整60回归实际记录的buildHashes/cloudBuildHashes逐字节核对；本追加记录不改写原冻结收据，完整回归没有记录的callback源码身份由专项callbackSources与收据source_hashes单独绑定。',
        'reports': reports, 'checks': checks, 'checkerSHA256': sha(Path(__file__))}
target = out / '负责人优化建议-支付回调-完整回归构建核对.json'
assert not target.exists(), 'Preserve an existing additive receipt'
target.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'pass': True, 'checked': len(checks), 'path': str(target)}, ensure_ascii=False))
