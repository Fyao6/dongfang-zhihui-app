"""本轮中性命名、冻结字节、链接与业务构建只读核验，不启动业务服务。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote, urlsplit
import hashlib
import json
import os
import re

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
mapping = json.loads((OUT / '文件命名对照.json').read_text(encoding='utf-8'))
errors = []
renamed = []
for item in mapping['records']:
    old, new = ROOT / item['originalPath'], ROOT / item['currentPath']
    if old.exists(): errors.append('old-path-present:' + item['originalPath'])
    if not new.exists(): errors.append('new-path-missing:' + item['currentPath']); continue
    if not item['contentChangedAsCurrentEntry'] and sha(new) != item['originalSHA256']:
        errors.append('frozen-bytes-changed:' + item['currentPath'])
    renamed.append({'path': item['currentPath'], 'sha256': sha(new), 'historicalBytesPreserved': not item['contentChangedAsCurrentEntry']})
for item in mapping['beforeEditSnapshots']:
    if not (ROOT / item['snapshot']).exists() or sha(ROOT / item['snapshot']) != item['sha256']:
        errors.append('snapshot-mismatch:' + item['snapshot'])
forbidden = []
for directory, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in {'.git', '.wrangler', 'node_modules', '__pycache__'}]
    for name in [*dirs, *files]:
        if any(x in name for x in ('回家', '在家', '公司同步', '先读我', 'start-home')):
            forbidden.append((Path(directory) / name).relative_to(ROOT).as_posix())
errors += ['forbidden-name:' + x for x in forbidden]

json_entries = ['项目进度与记忆.json', '成长统计-当前接续.json', '强制成长树-当前接续.json']
for name in json_entries:
    json.loads((OUT / name).read_text(encoding='utf-8'))

# 只核验改名所涉及的当前链接，不把历史媒体省略项冒充随包文件。
new_paths = {x['currentPath'].replace('\\', '/') for x in mapping['records']}
old_paths = {x['originalPath'].replace('\\', '/') for x in mapping['records']}
links = []
for p in [ROOT / 'README.md', *ROOT.glob('*.html')]:
    text = p.read_text(encoding='utf-8-sig')
    urls = re.findall(r'(?:href|src)=[\"\']([^\"\']+)[\"\']', text) if p.suffix == '.html' else re.findall(r'\]\(([^)]+)\)', text)
    for url in urls:
        split = urlsplit(url)
        if split.scheme or split.netloc or not split.path: continue
        rel = unquote(split.path).replace('\\', '/')
        if rel in old_paths: errors.append('old-link:' + p.name + ':' + rel)
        if rel in new_paths:
            exists = (p.parent / rel).exists()
            links.append({'source': p.name, 'target': rel, 'exists': exists})
            if not exists: errors.append('missing-renamed-link:' + p.name + ':' + rel)

cmd = (ROOT / '启动APP.cmd').read_text(encoding='utf-8')
assert 'start-app.ps1' in cmd and 'start-home' not in cmd
assert (ROOT / 'start-app.ps1').exists()
stable = json.loads((OUT / '成长统计-兼容修复后稳定构建记录.json').read_text(encoding='utf-8'))
product = stable['actualSourceAndBuildHashes']
intentional_entry_changes = []
unchanged = 0
for rel, expected in product.items():
    actual = sha(ROOT / rel) if (ROOT / rel).is_file() else None
    if actual == expected:
        unchanged += 1
    elif rel == '打开这里.html':
        copies = [x for x in mapping['beforeEditSnapshots'] if x['source'] == rel and x['sha256'] == expected]
        if len(copies) != 1 or sha(ROOT / copies[0]['snapshot']) != expected:
            errors.append('entry-baseline-mismatch:' + rel)
        else:
            intentional_entry_changes.append({'path': rel, 'oldSHA256': expected, 'newSHA256': actual,
                'baselineCopy': copies[0]['snapshot'], 'reason': '按用户中性命名要求修正根入口链接；03/04业务源码与构建不变'})
    else:
        errors.append('product-input-mismatch:' + rel)
result = {'at': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'pass': not errors,
          'renamedFiles': len(mapping['records']), 'frozenNameChanges': sum(not x['contentChangedAsCurrentEntry'] for x in mapping['records']),
          'beforeEditSnapshots': len(mapping['beforeEditSnapshots']), 'forbiddenFilenames': forbidden,
          'renamedCurrentLinks': links, 'productSourceBuildInputsUnchanged': unchanged,
          'intentionalRootEntryChanges': intentional_entry_changes,
          'currentJSONParsed': json_entries, 'launcherReferenceCorrect': True, 'errors': errors,
          'files': renamed,
          'scope': '只读文件/哈希/链接核验，不是业务回归或实机验收；历史正文中的旧路径由文件命名对照解析'}
(OUT / '文件命名核验记录.json').write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps({k: v for k, v in result.items() if k not in ('files', 'renamedCurrentLinks')}, ensure_ascii=False))
if errors: raise SystemExit(1)
