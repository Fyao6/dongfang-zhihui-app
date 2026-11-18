from pathlib import Path
import hashlib,json,datetime
root=Path(__file__).resolve().parents[1]
proof=root/'06_验证与后续工作'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
stable=json.loads((proof/'成长统计-稳定构建记录.json').read_text(encoding='utf-8'))['actualSourceAndBuildHashes']
base=json.loads((proof/'当前产品可靠性-最终稳定构建记录.json').read_text(encoding='utf-8'))['actualSourceAndBuildHashes']
saved={}
for i,(name,digest) in enumerate(stable.items()):
 p=root/name
 assert sha(p)==digest,name
 if base.get(name)==digest:continue
 target=proof/f'成长统计-v1原构建-{i:03d}-{p.name}.原字节'
 with target.open('xb') as f:f.write(p.read_bytes())
 saved[name]={'sha256':digest,'savedAs':target.relative_to(root).as_posix()}
with (proof/'成长统计-v1失败原源码差异保全.json').open('xb') as f:f.write((json.dumps(saved,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
for name in ['daily.js','homepage.js','journey.js']:
 p=root/'04_研发源码/app/r4'/name
 text=p.read_text(encoding='utf-8')
 assert text.count('b.date.localeCompare(a.date)')==1,name
 text=text.replace('b.date.localeCompare(a.date)',"String(b.date??'').localeCompare(String(a.date??''))")
 p.write_text(text,encoding='utf-8',newline='\n')
p=root/'04_研发源码/app/r4/growth-tree.js'
text=p.read_text(encoding='utf-8')
needle='    for(const node of candidates){\n      const id=isObject(node.value)?node.value.id:null;'
assert text.count(needle)==1
text=text.replace(needle,"    for(const node of candidates){\n      // Only native session/listening IDs identify events; other original id\n      // fields can refer to content or metadata and must not merge days.\n      if(!['session','music'].includes(node.recordKind))continue;\n      const id=isObject(node.value)?node.value.id:null;")
p.write_text(text,encoding='utf-8',newline='\n')
print(json.dumps({'preservedChangedInputs':len(saved),'safeSortModules':3,'deduplication':'native session and listening event IDs only'},ensure_ascii=False))
