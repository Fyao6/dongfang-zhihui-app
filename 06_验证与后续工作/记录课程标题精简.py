from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,csv,os
r=Path(__file__).resolve().parent.parent;q=r/'06_验证与后续工作';now=datetime.now(timezone(timedelta(hours=8))).isoformat()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
reg=read(q/'本轮全量回归结果.json')['latest'];ui=read(q/'课程标题精简核验.json')
assert reg['pass'] and reg['module']=='课程筛选标题精简' and ui['pass']
for name,digest in reg['buildHashes'].items():assert hashlib.sha256((r/'03_当前APP'/name).read_bytes()).hexdigest()==digest
record={'at':now,'changes':['筛选条全部改为全部课程','移除课程列表上方重复全部课程标题','课程数量合并到筛选条右侧'],'ui':ui,'local_full':{k:reg[k] for k in ('module','at','passed','failed','buildHashes')},'local_preview':'http://127.0.0.1:8765/experience?lang=zh-Hans&page=academy&v=course-heading-20261103','backup':str(sorted((r/'07_历史版本仅供追溯').glob('课程标题精简前-*.zip'))[-1].relative_to(r)),'public_deployment_pending':True,'cloud_prepared_not_deployed':True}
write(q/'课程标题精简交付记录.json',record)
for rel in ('05_后台与研发说明/动态分类与老师推荐使用说明.txt',):
 p=r/rel;s=p.read_text(encoding='utf-8').replace('全部／有声书／视频教程','全部课程／有声书／视频教程');p.write_text(s,encoding='utf-8')
note='\n\n2026年11月3日：课程标题精简\n按用户截图反馈，筛选条“全部”改为“全部课程”，课程列表上方重复标题移除；筛选结果数量移到同一筛选条右侧。源码、03查看页及云端待部署页面已同步，本次本机56项回归和四语筛选／计数检查通过。公网仍待原Sites发布工具恢复，未替换线上版本。验证见06_验证与后续工作/课程标题精简交付记录.json。\n'
for rel in ('AGENTS.md','先读我.txt','03_当前APP/功能与使用说明-R4.txt'):
 p=r/rel;s=p.read_text(encoding='utf-8')
 if '2026年11月3日：课程标题精简' not in s:p.write_text(s.rstrip()+note,encoding='utf-8')
p=r/'交接资料验证.json';d=read(p);d.update(updated_beijing=now,academy_heading_refinement=record);write(p,d)
skip_dirs={'.git','__pycache__','node_modules','.venv','.wrangler','.sites-runtime','.netlify','dist','.next','.vinext','.cache','coverage'}
skip_suffixes={'.zip','.7z','.rar','.tar','.gz','.tgz','.pyc','.log','.db','.pem','.key','.pfx','.p12','.tsbuildinfo'}
rows=[]
for current,dirs,names in os.walk(r):
 dirs[:]=[d for d in dirs if d not in skip_dirs and not (Path(current)/d).is_symlink()]
 for name in names:
  p=Path(current)/name
  if p.is_symlink() or p.suffix.lower() in skip_suffixes or any(x in name.lower() for x in ('.sqlite','.env','.dev.vars')) or name in {'资料校验清单.csv','原始来源与文件校验.json','.DS_Store','Thumbs.db'}:continue
  data=p.read_bytes();rows.append({'path':p.relative_to(r).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
rows.sort(key=lambda x:x['path'])
with (r/'资料校验清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['包内相对位置','字节数','SHA-256']);w.writerows((x['path'],x['bytes'],x['sha256']) for x in rows)
p=r/'原始来源与文件校验.json';d=read(p);d['files']=rows;d['current_revision']={'updated_beijing':now,'scope':'Current source/build; private runtime and archived ZIPs excluded','local_regression_pass':True,'public_deployment_pending':True,'delivery_record':'06_验证与后续工作/课程标题精简交付记录.json'};write(p,d)
print(json.dumps({'pass':True,'passed':reg['passed'],'ui_languages':len(ui['checks']),'public_deployment_pending':True}))

