
from pathlib import Path
import json,re
p=Path(__file__).resolve().parent.parent;r=p/'04_研发源码/app/r4';q=p/'06_验证与后续工作'
old={x['zh']:x for x in json.loads((q/'四语初译来源.json').read_text(encoding='utf-8'))}
new={x['zh']:x for x in json.loads((q/'四语文案清单.json').read_text(encoding='utf-8'))}
draft=json.loads((r/'i18n-bo-draft.json').read_text(encoding='utf-8'))
changed=[k for k in old if k in new and old[k]['en']!=new[k]['en']]
for key in changed:draft.pop(key,None)
(r/'i18n-bo-draft.json').write_text(json.dumps(draft,ensure_ascii=False,indent=2),encoding='utf-8')
(q/'四语文案提取修正.json').write_text(json.dumps({'reason':'Prevent adjacent bilingual chapter titles being paired with the following paragraph. Re-translate affected paragraphs.', 'invalidated':changed},ensure_ascii=False,indent=2),encoding='utf-8')
print('Invalidated',len(changed),'paragraph translations; retained',len(draft))

