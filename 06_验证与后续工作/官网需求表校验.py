"""Read-only check: only 追加需求!B2:E2 values may change."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
spec=importlib.util.spec_from_file_location('website_book_reader', OUT/'负责人优化建议-支付回调-进度表校验.py')
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
original,candidate,expected_file,report=map(Path,sys.argv[1:])
before,after=reader.read_book(original),reader.read_book(candidate)
violations=[];changed=[];allowed={'B2','C2','D2','E2'}
for key in ('order','nativeTables','theme','mediaHashes','drawings'):
 if before[key]!=after[key]:violations.append(key)
if before['sheets'].keys()!=after['sheets'].keys():violations.append('sheet_set')
for name in before['order']:
 old,new=before['sheets'][name],after['sheets'].get(name,{})
 for key in ('rows','features'):
  if old[key]!=new.get(key):violations.append(name+':'+key)
 for address in old['cells'].keys()|new.get('cells',{}).keys():
  left,right=old['cells'].get(address),new.get('cells',{}).get(address)
  if left==right:continue
  changed.append({'sheet':name,'cell':address,'valueBefore':left['value'] if left else None,'valueAfter':right['value'] if right else None})
  if name!='追加需求' or address not in allowed or left is None or right is None:violations.append(name+':outside_value_scope:'+address)
  elif {k:v for k,v in left.items() if k!='value'}!={k:v for k,v in right.items() if k!='value'}:violations.append(name+':formula_or_style:'+address)
cells=after['sheets']['追加需求']['cells']
if cells['A2']['value']!='ADD-WEB':violations.append('row_identity')
for address,value in json.loads(expected_file.read_text('utf-8')).items():
 if cells.get(address,{}).get('value')!=value:violations.append('expected:'+address)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'pass':not violations,'violations':violations,'scope':'追加需求!B2:E2 values only','changedCells':changed,'allOtherValuesFormulasStylesPreserved':not violations,'original98And31StageCountsPreserved':not violations,'growthAndDailyRowsPreserved':not violations,'beforeSHA256':sha(original),'afterSHA256':sha(candidate)}
if report.exists():raise RuntimeError('Do not overwrite report')
report.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'pass':result['pass'],'changedCells':len(changed),'violations':violations},ensure_ascii=False))
sys.exit(0 if result['pass'] else 1)
