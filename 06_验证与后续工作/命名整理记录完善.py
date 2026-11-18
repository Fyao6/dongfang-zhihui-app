"""补全本轮命名整理的当前说明和首轮异常记录，不更改历史字节。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
path = OUT / '文件命名对照.json'
data = json.loads(path.read_text(encoding='utf-8'))
p = ROOT / '项目资料说明.txt'
text = p.read_text(encoding='utf-8')
header = '''项目资料说明
当前使用与进度请先读根“项目说明.txt”、AGENTS.md及06_验证与后续工作/项目进度与记忆.json。
原需求、专业参考和设计素材在01/02；03为当前实际构建，04为源码，05为研发说明，06为验证与接续，07/08为历史资料。
下方长文保留历次资料说明和交付时点，不将其中旧“当前”表述视为最新进度。已淘汰的交接文件名按06_验证与后续工作/文件命名对照.json追溯，历史报告和一次性helper不回写、不自动重跑。

以下为历次项目资料说明：

'''
if not text.startswith('项目资料说明\n'): p.write_bytes((header + text).encode('utf-8'))
known = {x['snapshot'] for x in data['beforeEditSnapshots']}
for p in OUT.glob('交付命名整理前-*.原字节'):
    rel = p.relative_to(ROOT).as_posix()
    if rel in known: continue
    suffix = p.name.split('-', 4)[-1] if False else p.name.removeprefix('交付命名整理前-20261118-154340-253496-').removesuffix('.原字节')
    source = suffix
    if suffix in ('项目进度与记忆.json', '成长统计-当前接续.json', '强制成长树-当前接续.json'):
        source = '06_验证与后续工作/' + suffix
    data['beforeEditSnapshots'].append({'source': source, 'snapshot': rel, 'sha256': sha(p)})
    known.add(rel)
if '打开这里.html' not in data['currentReferenceFilesUpdated']: data['currentReferenceFilesUpdated'].append('打开这里.html')
for item in data['records']:
    item['currentSHA256'] = sha(ROOT / item['currentPath'])
    item['contentChangedAsCurrentEntry'] = item['currentSHA256'] != item['originalSHA256']
data['completion'] = {'at': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'namingStatus': 'complete',
    'githubSyncStatus': 'pending', 'packageStatus': 'pending', 'businessChanged': False,
    'historicalCode': '历史交付脚本和旧记录内部路径保持原字节，按映射追溯，当前不运行'}
data['initialAttempt'] = {'status': 'stopped-before-writing-current-JSON',
    'error': 'JSONDecodeError: Invalid escape at line 2467 column 35',
    'reason': '对含Windows反斜杠的JSON原文替换路径造成解析异常；原JSON未写入',
    'correction': '先解析原JSON，再递归替换字符串并用json.dumps编码；已完成改名与原字节快照继续使用，不重复覆盖',
    'businessAndFrozenBytesChanged': False}
path.write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
print(json.dumps({'records': len(data['records']), 'snapshots': len(data['beforeEditSnapshots'])}))
