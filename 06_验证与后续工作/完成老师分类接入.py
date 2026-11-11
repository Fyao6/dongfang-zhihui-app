from pathlib import Path
import json
r=Path(__file__).resolve().parent.parent/'04_研发源码/app/r4'
p=r/'i18n-extra.json';d=json.loads(p.read_text(encoding='utf-8'));d.update(json.loads((r.parents[2]/'06_验证与后续工作/老师与社群新增四语.json').read_text(encoding='utf-8')));p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=r/'homepage.js';s=p.read_text(encoding='utf-8').replace("['academy','academyDetail','lesson'","['academy','academyTeacher','academyDetail','lesson'");p.write_text(s,encoding='utf-8')
p=r/'platform.js';s=p.read_text(encoding='utf-8')
s=s.replace('<h3>'+chr(36)+'{esc(x.name||x.title||\'\')}</h3>','<h3>'+chr(36)+'{esc(academyTeacherName(x))} '+chr(36)+'{academyTeacherBadge(x)}</h3>')
old='<button class="btn full" data-action="px-service-request" data-id="'+chr(36)+'{esc(x.id)}">'+chr(36)+"{pxText('提出交流需求','Request a conversation')}</button>"
new=chr(36)+"{x.profileType==='demo'?"+chr(96)+'<button class="btn full" data-action="at-open" data-id="'+chr(36)+'{esc(x.id)}">'+chr(36)+"{t('View courses','查看课程')}</button>"+chr(96)+':'+chr(96)+old+chr(96)+'}'
assert old in s;s=s.replace(old,new,1);p.write_text(s,encoding='utf-8')

