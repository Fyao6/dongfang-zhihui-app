
from pathlib import Path
r=Path(__file__).resolve().parent.parent/'04_研发源码/app/r4'
p=r/'time-bank-admin.html';s=p.read_text(encoding='utf-8')
insert="""// Translation fields share the original content's revision and publication lifecycle.
const translatedFields={quotes:['zh','bannerLabel','description','buttonLabel'],maps:['name','heroTitle','heroText'],cards:['zh','lineZh','readingZh','actionZh'],music:['zh','descZh'],courses:['zh','summaryZh','goalsZh'],teachers:['specialty','bio'],devices:['description'],signin:['name','description'],membership:['zh','periodZh','copyZh'],benefits:['zh','subZh','copyZh','ctaZh']};
for(const [kind,fields] of Object.entries(translatedFields)){for(const source of fields){const original=schemas[kind].find(x=>x[0]===source);if(!original)continue;const prefix=source==='zh'?'':source.endsWith('Zh')?source.slice(0,-2):source;for(const [suffix,label] of [['En','英文'],['Hant','繁体中文'],['Bo','藏文']]){const key=prefix?prefix+suffix:suffix.toLowerCase();if(!schemas[kind].some(x=>x[0]===key))schemas[kind].push([key,label+' · '+original[1],original[2]==='lines'?'lines':original[2]==='textarea'?'textarea':'text']);}}}
schemas.courses.push(['sectionsEn','英文章节（每段标题换行正文；空行分隔章节）','localized-chapters'],['sectionsHant','繁体章节（与原文章节顺序一致）','localized-chapters'],['sectionsBo','藏文章节（与原文章节顺序一致）','localized-chapters']);
"""
if insert not in s:s=s.replace("function editor(item){",insert+"function editor(item){")
s=s.replace("['textarea','audio','media','list','lines','chapters','image','sources']","['textarea','audio','media','list','lines','chapters','localized-chapters','image','sources']")
s=s.replace("else if(type==='chapters')input=", """else if(type==='localized-chapters')input='<textarea name="'+key+'" rows="6">'+esc((value||[]).map(v=>v[0]+'\\\\n'+v[1]).join('\\\\n\\\\n'))+'</textarea><span class="field-note">留空时使用内置译文；新增内容请补齐翻译。</span>';
 else if(type==='chapters')input=""")
s=s.replace("else if(type==='chapters')item[key]=", "else if(type==='localized-chapters')item[key]=String(values[key]||'').split(/\\\\n\\\\s*\\\\n/).filter(x=>x.trim()).map(block=>{const [title,...lines]=block.split('\\\\n');return [title,lines.join('\\\\n')];});else if(type==='chapters')item[key]=")
s=s.replace('编辑后选择保存草稿或发布。排序值越小越靠前；归档后不再出现在APP的新内容列表。','编辑后选择保存草稿或发布。排序值越小越靠前；归档后不再出现在APP的新内容列表。四语文案在同一条内容中维护，翻译留空时使用内置译文；新内容没有译文时显示原文。')
s=s.replace('</style>','@font-face{font-family:EW-Tibetan;src:url(/assets/NotoSerifTibetan.woff2) format("woff2")}textarea[name$=Bo],textarea[name=bo],input[name$=Bo],input[name=bo]{font-family:EW-Tibetan,"Microsoft Himalaya",serif;line-height:2;font-size:17px}</style>',1)
p.write_text(s,encoding='utf-8')
print('Admin supports four-language content in existing revision/publication workflow.')

