
from pathlib import Path
import json,re,sys,unicodedata
p=Path(__file__).resolve().parent.parent;r=p/'04_研发源码/app/r4'
sys.path.insert(0,str(p/'04_研发源码/app/cloud/.sites-runtime/font-tools'))
from fontTools.ttLib import TTFont
text=(r/'i18n-catalog.js').read_text(encoding='utf-8')
catalog=json.loads(text[len('window.EW_LOCALE_CATALOG='):-2])
font=TTFont(r/'vendor/NotoSerifTibetan.woff2');cmap=font.getBestCmap()
missing=[k for k,v in catalog.items() if not v.get('bo')]
slots=[k for k,v in catalog.items() if sorted(re.findall(r'\{\d+\}',k))!=sorted(re.findall(r'\{\d+\}',v.get('bo','')))]
glyphs=sorted(set(ch for v in catalog.values() for ch in v.get('bo','') if '\u0f00'<=ch<='\u0fff' and ord(ch) not in cmap))
markup=[k for k,v in catalog.items() if re.search(r'<(?!/?(?:br|b|strong|em|i)\b)',v.get('bo',''))]
out={'catalogEntries':len(catalog),'TibetanEntries':sum(bool(v.get('bo')) for v in catalog.values()),'missing':missing,'placeholderMismatches':slots,'missingTibetanGlyphs':glyphs,'unexpectedMarkup':markup,'nativeSpeakerReview':False}
(p/'06_验证与后续工作/四语字典与字体校验.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:len(v) if isinstance(v,list) else v for k,v in out.items()}))
if missing or slots or glyphs or markup:sys.exit(1)

