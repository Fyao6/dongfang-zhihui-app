"""Record the user's explicit visual-theme clarification without changing website code."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / '06_验证与后续工作'
OLD = AREA / '官网功能一致性-待办.json'
NEW = AREA / '官网视觉主题-需求.json'
SNAPSHOT = AREA / '官网需求理解纠正前-20261118-161659.json.原字节'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def write(path, value): path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
assert SNAPSHOT.is_file()
requirement = {
    'source': '用户明确纠正：官网视觉和主题与APP约80%一致，就是主题上的问题',
    'scope': '视觉主题一致性；不是APP功能或业务流程覆盖比例',
    'visualFocus': ['配色体系', '字体与文字层级', '图形语言', '整体品牌气质'],
    'currentStatus': '待视觉主题对齐和用户评价',
    'existingWebsiteVerification': {
        'receipt': '06_验证与后续工作/官网接入-本地验收只读复核.json',
        'perBackendPassed': 66,
        'scope': '原展示官网与入口本地验证；不代表本条视觉主题已获用户认可'},
    'originalPremiumDirection': '基于现有官网统一APP品牌主题，保留高级大气的呈现节奏，不照搬第三方资产',
    'newBusinessFunctionsRequested': False, 'implementedDuringPackaging': False,
    'priorWrongInterpretationCorrected': True,
}
write(NEW, requirement)
if OLD.exists():
    assert sha(OLD) == sha(SNAPSHOT)
    OLD.unlink()
mapping_path = AREA / '文件命名对照.json'
mapping = json.loads(mapping_path.read_bytes())
row = next(x for x in mapping['records'] if x['originalPath'] == OLD.relative_to(ROOT).as_posix())
row.update(originalSHA256=sha(SNAPSHOT), bytes=SNAPSHOT.stat().st_size,
    currentSHA256=sha(NEW), contentChangedAsCurrentEntry=True, renamedBytesPreserved=False)
memory_path = AREA / '项目进度与记忆.json'
memory = json.loads(memory_path.read_bytes())
memory['progress']['workbookSha256'] = sha(ROOT / memory['progress']['workbook'])
memory['currentDeliveryPreparation']['websiteThemeCorrection'] = {
    'requirement': NEW.relative_to(ROOT).as_posix(),
    'tablesReceipt': '06_验证与后续工作/官网主题纠正-已应用-56f61762b37e4eadabaf5a843647bfa7.json',
    'businessFunctionExpansion': False}
write(memory_path, memory)
for item in mapping['records']:
    item['currentSHA256'] = sha(ROOT / item['currentPath'])
write(mapping_path, mapping)
print(json.dumps({'visualThemeRequirementRecorded': NEW.name, 'wrongFunctionTodoRetired': not OLD.exists(),
    'businessFilesChanged': False}, ensure_ascii=False))
