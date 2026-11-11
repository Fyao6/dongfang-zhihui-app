"""Generate local UI catalog, keeping terminology edits separate from generated assets."""
from pathlib import Path
import json
r=Path(__file__).resolve().parent
p=r.parents[2]
inventory=json.loads((p/'06_验证与后续工作/四语文案清单.json').read_text(encoding='utf-8'))
bo=json.loads((r/'i18n-bo-draft.json').read_text(encoding='utf-8')) if (r/'i18n-bo-draft.json').exists() else {}
bo.update(json.loads((r/'i18n-bo.json').read_text(encoding='utf-8')))
extra=json.loads((r/'i18n-extra.json').read_text(encoding='utf-8')) if (r/'i18n-extra.json').exists() else {}
catalog={row['zh']:{'en':row['en']} for row in inventory}
for zh,item in extra.items(): catalog.setdefault(zh,{}).update(item)
for zh,value in bo.items(): catalog.setdefault(zh,{})['bo']=value
(r/'i18n-catalog.js').write_text('window.EW_LOCALE_CATALOG='+json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(f'Local catalog: {len(catalog)} entries, Tibetan: {len(bo)}')

