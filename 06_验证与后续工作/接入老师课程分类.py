from pathlib import Path
import json
root=Path(__file__).resolve().parent.parent;r=root/'04_研发源码/app/r4'
p=r/'academy.js';s=p.read_text(encoding='utf-8')
a=s.index('function academyResultCards()');b=s.index('function academyHome()',a)
old=s[a:b];body=old[old.index('$'+'{items.length?'):]
s=s[:a]+'function academyCourseList(items=academyResults()){return '+chr(96)+body+s[b:]
s=s.replace("academyCatalog.forEach(l=>{if(", "academyCatalog.forEach(l=>{l.teacherId=({ziwei:'demo-qinghe',tcm:'demo-anran',healing:'demo-zhiwei'})[l.theme];if(",1)
s=s.replace("if(!l)return;state.academyId=l.id;state.lessonId=l.id;return navigate('academyDetail');","if(!l)return;state.academyBack=state.page==='academyTeacher'?'academyTeacher':'academy';state.academyId=l.id;state.lessonId=l.id;return navigate('academyDetail');",1)
s=s.replace("ewI18n.content(l,'summary',lang)", "ewI18n.content(l,'summary',lang)+' '+ewI18n.field(academyTeachers().find(x=>x.id===l.teacherId),'name',lang)",1)
p.write_text(s,encoding='utf-8')
p=r/'platform.js';s=p.read_text(encoding='utf-8')
s=s.replace("pxTop(esc(ewI18n.content(item,\"\",state.lang)),'','academy')", "pxTop(esc(ewI18n.content(item,\"\",state.lang)),'',state.academyBack||'academy')",1)
start=s.index('function pxCourseDetail()');end=s.index('async function pxBootstrap',start)
part=s[start:end].replace('<div class="px-chips">','$'+'{academyCourseTeacher(item)}<div class="px-chips">',1)
s=s[:start]+part+s[end:];p.write_text(s,encoding='utf-8')
p=r/'build.py';s=p.read_text(encoding='utf-8')
s=s.replace("'academy.js','gateway.js'","'academy.js','academy-teachers.js','gateway.js'")
s=s.replace("'journey.css','i18n.css'","'journey.css','i18n.css','academy-teachers.css'")
p.write_text(s,encoding='utf-8')
p=r/'time-bank-admin.html';s=p.read_text(encoding='utf-8')
s=s.replace("courses:[['coverUrl'","courses:[['teacherId','所属老师','teacher'],['coverUrl'",1)
s=s.replace("teachers:[['name'","teachers:[['coverUrl','老师头像','image'],['profileType','资料类型','select:real=真实资料,demo=示例资料'],['name'",1)
s=s.replace("teachers:['specialty','bio']","teachers:['name','specialty','bio']",1)
s=s.replace("const d=await api('admin/content/'+nav);if(seq!==state.seq)return;state.items=d.items;","const d=await api('admin/content/'+nav);let teacherOptions;if(nav==='courses')teacherOptions=(await api('admin/content/teachers')).items;if(seq!==state.seq)return;if(teacherOptions)state.teacherOptions=teacherOptions;state.items=d.items;",1)
s=s.replace("if(type==='textarea')input=", """if(type==='teacher'){const options=state.teacherOptions||[];input='<select name="'+key+'"><option value="">平台课程（未关联老师）</option>'+options.map(x=>'<option value="'+esc(x.id)+'"'+(value===x.id?' selected':'')+'>'+esc(x.name||x.id)+(x._status==='published'?'':' · 未发布')+'</option>').join('')+(value&&!options.some(x=>x.id===value)?'<option value="'+esc(value)+'" selected>'+esc(value)+' · 资料不可用</option>':'')+'</select><span class="field-note">选择已发布老师后，课程会进入其课程页。未发布老师的课程仍归入平台课程。</span>';}
 else if(type==='textarea')input=""",1)
p.write_text(s,encoding='utf-8')
seed_path=r/'backend/initial-content.json';seed=json.loads(seed_path.read_text(encoding='utf-8'))
teachers=json.loads((root/'06_验证与后续工作/老师分类示例资料.json').read_text(encoding='utf-8'))
seed['teachers']=teachers+ [x for x in seed.get('teachers',[]) if x['id'] not in {t['id'] for t in teachers}]
for course in seed['courses']:
 if course['id'].startswith('academy-') and not course.get('teacherId'):course['teacherId']={'ziwei':'demo-qinghe','tcm':'demo-anran','healing':'demo-zhiwei'}[course['theme']]
seed_path.write_text(json.dumps(seed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for filename in ['全量回归.cjs','Netlify适配全量回归.cjs']:
 p=root/'06_验证与后续工作'/filename;s=p.read_text(encoding='utf-8')
 s=s.replace("await go('academy');", "await go('academy');await page.evaluate(()=>{state.academyView='courses';render(false)});")
 p.write_text(s,encoding='utf-8')
print('Teacher collections, course attribution, admin selector and seed updated.')

