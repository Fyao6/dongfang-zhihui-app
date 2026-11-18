import ast,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
tree=ast.parse((root/'04_研发源码/app/r4/backend/reconciliation.py').read_text(encoding='utf-8'))
sources=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='SOURCES')
file=root/'04_研发源码/app/cloud/lib/reconciliation-api.ts';text=file.read_text(encoding='utf-8');start='/* RECONCILIATION_SOURCES_START */';end='/* RECONCILIATION_SOURCES_END */'
text=text[:text.index(start)]+start+'\nconst SOURCES:Record<string,[string,string,string]>='+json.dumps(sources,ensure_ascii=False)+';\n'+end+text[text.index(end)+len(end):]
file.write_text(text,encoding='utf-8');print(json.dumps({'readOnlySources':len(sources)}))
