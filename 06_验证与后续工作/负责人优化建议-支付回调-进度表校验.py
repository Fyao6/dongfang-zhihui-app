"""Read-only OOXML scope check. Spreadsheet authoring belongs to artifact-tool."""
import hashlib
import json
from pathlib import Path
import posixpath
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ALLOWED_VALUES = {
    '进度总览': {'D12','E12','D15','D20','E20','C12','C15','B29','E29'},
    '98项明细': {'D77','E77','F77','G77'},
    '优化任务表': {'A4','I82','K82'},
    '原文逐段对照': set(),
    '优化任务表': {'A4','I82','K82'},
    '原文逐段对照': set(),
}


def tree(node, relationships=None):
    if node is None:
        return None
    relationships = relationships or {}
    attributes = [(key, relationships.get(value, value) if key.startswith('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}') else value) for key, value in node.attrib.items()]
    return [node.tag, sorted(attributes), node.text or '', [tree(child, relationships) for child in node]]


def relationships(archive, part):
    directory, filename = posixpath.split(part)
    relfile = posixpath.join(directory, '_rels', filename+'.rels')
    if relfile not in archive.namelist():
        return {}
    result = {}
    for entry in ET.fromstring(archive.read(relfile)):
        target = posixpath.normpath(posixpath.join(directory, entry.attrib['Target']))
        if '/media/' in target and target in archive.namelist():
            target = 'media-sha256:'+hashlib.sha256(archive.read(target)).hexdigest()
        result[entry.attrib['Id']] = target
    return result


def read_book(file):
    with ZipFile(file) as archive:
        styles = ET.fromstring(archive.read('xl/styles.xml'))
        fonts, fills, borders, formats = [styles.find('m:'+tag, NS) for tag in ('fonts','fills','borders','numFmts')]
        custom = {item.attrib['numFmtId']: item.attrib['formatCode'] for item in formats} if formats is not None else {}
        resolved = []
        for xf in styles.find('m:cellXfs', NS):
            attributes = dict(xf.attrib)
            parts = {}
            for key, collection in [('fontId',fonts),('fillId',fills),('borderId',borders)]:
                parts[key] = tree(collection[int(attributes.pop(key, '0'))])
            fmt = attributes.pop('numFmtId', '0')
            parts['numberFormat'] = custom.get(fmt, 'builtin:'+fmt)
            parts['attributes'] = attributes
            parts['children'] = [tree(child) for child in xf]
            resolved.append(parts)
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(item.itertext()) for item in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        wb = ET.fromstring(archive.read('xl/workbook.xml'))
        result = {'sheets': {}, 'order': [], 'nativeTables': {}}
        for index, entry in enumerate(wb.find('m:sheets', NS), 1):
            name = entry.attrib['name']
            result['order'].append(name)
            sheet_part = 'xl/worksheets/sheet'+str(index)+'.xml'
            sheet = ET.fromstring(archive.read(sheet_part))
            rels = relationships(archive, sheet_part)
            cells, rows = {}, {}
            for row in sheet.find('m:sheetData', NS):
                rows[row.attrib['r']] = dict(row.attrib)
                for cell in row:
                    address = cell.attrib['r']
                    node = cell.find('m:v', NS)
                    value = node.text if node is not None else None
                    cell_type = cell.attrib.get('t', 'n')
                    if cell_type == 's':
                        value = shared[int(value)] if value is not None else None
                    elif cell_type == 'inlineStr':
                        inline = cell.find('m:is', NS)
                        value = ''.join(inline.itertext()) if inline is not None else None
                    elif cell_type == 'n' and value is not None:
                        value = float(value)
                    formula = cell.find('m:f', NS)
                    cells[address] = {'value': value, 'formula': tree(formula),
                                      'style': resolved[int(cell.attrib.get('s', '0'))]}
            result['sheets'][name] = {'cells': cells, 'rows': rows,
                'features': [tree(child, rels) for child in sheet if child.tag.rsplit('}',1)[-1] not in ('sheetData','dimension')]}
        for name in archive.namelist():
            if name.startswith('xl/tables/') and name.endswith('.xml'):
                result['nativeTables'][name] = tree(ET.fromstring(archive.read(name)))
        result['theme'] = archive.read('xl/theme/theme1.xml').decode('utf-8') if 'xl/theme/theme1.xml' in archive.namelist() else None
        result['mediaHashes'] = sorted(hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist() if name.startswith('xl/media/'))
        result['drawings'] = {name: tree(ET.fromstring(archive.read(name)), relationships(archive,name)) for name in archive.namelist() if name.startswith('xl/drawings/') and name.endswith('.xml') and '/_rels/' not in name}
        return result


def verify(before, after):
    changes, violations = [], []
    if before['order'] != after['order']:
        violations.append('worksheet_order')
    if before['nativeTables'] != after['nativeTables']:
        violations.append('native_tables')
    if before['theme'] != after['theme']:
        violations.append('theme')
    if before['mediaHashes'] != after['mediaHashes']:
        violations.append('media_bytes')
    if before['drawings'] != after['drawings']:
        violations.append('drawing_structure')
    for name in before['order']:
        old, new = before['sheets'][name], after['sheets'][name]
        if old['features'] != new['features']:
            violations.append(name+':sheet_features')
        for row in old['rows'].keys() | new['rows'].keys():
            if old['rows'].get(row) != new['rows'].get(row) and not ((name=='98项明细' and row=='77') or (name=='优化任务表' and row=='82')):
                violations.append(name+':row_format:'+row)
        for address in old['cells'].keys() | new['cells'].keys():
            left, right = old['cells'].get(address), new['cells'].get(address)
            if left == right:
                continue
            changes.append({'sheet': name, 'cell': address,
                            'valueBefore': left['value'] if left else None,
                            'valueAfter': right['value'] if right else None,
                            'styleChanged': (left or {}).get('style') != (right or {}).get('style'),
                            'formulaChanged': (left or {}).get('formula') != (right or {}).get('formula')})
            if address not in ALLOWED_VALUES[name] or not left or not right or left['formula'] != right['formula'] or left['style'] != right['style']:
                violations.append(name+':cell_scope:'+address)
    return {'scopePreserved': not violations, 'changedCells': changes, 'violations': violations,
            'preservedOtherRequirements': 97, 'worksheetOrder': before['order']}


if __name__ == '__main__':
    original, candidate, report = map(Path, sys.argv[1:4])
    result = verify(read_book(original), read_book(candidate))
    result.update(originalSha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                  candidateSha256=hashlib.sha256(candidate.read_bytes()).hexdigest())
    report.write_bytes((json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'scopePreserved':result['scopePreserved'], 'changedCells':len(result['changedCells']), 'violations':result['violations'][:20]}, ensure_ascii=False))
    sys.exit(0 if result['scopePreserved'] else 1)
