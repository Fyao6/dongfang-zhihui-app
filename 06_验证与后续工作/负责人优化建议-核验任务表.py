from pathlib import Path
from io import BytesIO
from collections import Counter
import argparse
import hashlib, json, zipfile, xml.etree.ElementTree as ET

P = Path(__file__).resolve().parent.parent
D = P / '06_验证与后续工作'
rel = '06_验证与后续工作/东方智慧APP优化任务表_依据v1.0_20261112.xlsx'
parser = argparse.ArgumentParser()
parser.add_argument('--baseline', required=True, type=Path)
parser.add_argument('--report', default='负责人优化建议-五阶段回填-任务表核验.json')
args = parser.parse_args()
baseline_path = args.baseline.resolve(strict=True)
assert baseline_path.parent == D.resolve() and baseline_path.suffix == '.xlsx'
baseline = baseline_path.read_bytes()
current = (P / rel).read_bytes()
audit = json.loads((D / '负责人优化建议-98项最终覆盖审计.json').read_bytes())
updated_ids = set(audit['updatedTaskIds'])
N = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def read(data):
    z = zipfile.ZipFile(BytesIO(data))
    assert z.testzip() is None
    ss = []
    if 'xl/sharedStrings.xml' in z.namelist():
        ss = [''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', N)]
    sheets, validations = {}, {}
    for name in ['sheet1', 'sheet2']:
        root = ET.fromstring(z.read('xl/worksheets/'+name+'.xml'))
        cells = {}
        validations[name] = [ET.tostring(item) for item in root.findall('.//s:dataValidation', N)]
        for c in root.findall('.//s:sheetData/s:row/s:c', N):
            v = c.find('s:v', N)
            value = v.text if v is not None else ''
            if c.get('t') == 's':
                value = ss[int(value)]
            elif c.get('t') == 'inlineStr':
                value = ''.join(c.find('s:is', N).itertext())
            f = c.find('s:f', N)
            if value or f is not None:
                cells[c.attrib['r']] = (value, f.text if f is not None else None)
        sheets[name] = cells
    media = sorted(hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('xl/media/'))
    return sheets, media, validations

old, old_media, old_validations = read(baseline)
new, new_media, new_validations = read(current)
assert old['sheet2'] == new['sheet2'], 'source paragraph sheet changed'
assert old_media == new_media and len(new_media) == 4, 'original embedded images changed'
assert old_validations == new_validations, 'validation changed'
tasks = json.loads((D / '负责人优化建议-任务拆解.json').read_text(encoding='utf-8-sig'))
expected = {'I'+str(row) for row,t in enumerate(tasks, 11) if t['id'] in updated_ids}
changed = {cell for cell in old['sheet1'].keys() | new['sheet1'].keys()
           if old['sheet1'].get(cell) != new['sheet1'].get(cell)}
assert changed == expected | {'A4'}, changed ^ (expected | {'A4'})
assert str(audit['verifiedLocalStages'])+'个本地实施阶段' in new['sheet1']['A4'][0]
allowed = lambda cell: cell in expected | {'A4'}
for cell in old['sheet1'].keys() | new['sheet1'].keys():
    if not allowed(cell):
        assert old['sheet1'].get(cell) == new['sheet1'].get(cell), ('unrelated cell changed', cell)
for sheet, cells in old.items():
    for cell, (_, formula) in cells.items():
        if formula:
            assert new[sheet][cell][1] == formula, ('formula changed', sheet, cell)
assert len(tasks) == len({t['id'] for t in tasks}) == 98
for row, t in enumerate(tasks, 11):
    assert new['sheet1']['A'+str(row)][0] == t['id']
    assert new['sheet1']['K'+str(row)][0] == t['status']
    if t['id'] in updated_ids:
        assert new['sheet1']['I'+str(row)][0] == t['dependencies']+'\n本轮：'+t['implementation_note']
errors = ['#REF!', '#DIV/0!', '#VALUE!', '#NAME?', '#NUM!', '#SPILL!']
for sheet, cells in new.items():
    assert not [(a, v[0]) for a, v in cells.items() if v[0] in errors], ('formula errors', sheet)
report = {'tasks': len(tasks), 'statusCounts': dict(Counter(t['status'] for t in tasks)), 'updatedTaskIds': sorted(updated_ids), 'sourceCellsPreserved': True, 'embeddedImagesPreserved': len(new_media), 'unrelatedCellsPreserved': True, 'formulasPreserved': True, 'validationPreserved': True, 'formulaErrors': 0, 'changedColumns': ['I进度及依赖'], 'changedSummary': 'A4', 'workbookSha256': hashlib.sha256(current).hexdigest(), 'baselineSha256': hashlib.sha256(baseline).hexdigest(), 'verification': 'Artifact Tool重算和预览后，独立ZIP/XML核对逐项状态、说明、原文工作表、四张图片、公式和数据验证。'}
report_path = D / args.report
assert report_path.parent == D and report_path.suffix == '.json'
with report_path.open('xb') as stream:
    stream.write((json.dumps(report, ensure_ascii=False, indent=2)+'\n').encode())
print(json.dumps(report, ensure_ascii=False))
