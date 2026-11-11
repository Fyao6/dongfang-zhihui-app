from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,csv,os
r=Path(__file__).resolve().parent.parent;q=r/'06_验证与后续工作';now=datetime.now(timezone(timedelta(hours=8))).isoformat()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report=read(q/'本次公网发布核验.json');assert report['pass']
for name in ['课程标题精简交付记录.json','动态分类老师推荐视频适配交付记录.json','公网发布通道诊断.json']:
 p=q/name;d=read(p);d.update(public_deployment_pending=False,cloud_prepared_not_deployed=False,source_sync_pending=False,publication=report)
 if name=='公网发布通道诊断.json':d.update(status='resolved_and_published',resolved_at=now)
 write(p,d)
p=r/'05_后台与研发说明/Netlify站点身份.json';d=read(p);d.update(previous_deploy_id=d['deploy_id'],deploy_id=report['netlify_deploy_id'],checked_at=now,latest_change='动态课程分类、老师推荐、视频适配与课程标题精简',status='deployed');write(p,d)
note='\n\n2026年11月3日：待发布版本已上线\n原Sites发布通道恢复，最新源码已推送并完成云后台和原Netlify站点发布。公网地址 https://eastern-wisdom-demo-fuyao.netlify.app/ ，后台 /admin，电脑查看 /app。课程动态分类、老师推荐入口、视频适配及标题精简已上线。原账号与云端数据保留。实际无代理只读核验通过：三入口、健康接口、匿名权限、原管理员登录、后台分类与课程多选、四语课程列表与社群四标签和视频自动播放；浏览器无运行异常。本轮未重新执行完整业务回归，沿用发布前已通过的回归证据。本次发布与公网验证详情见06_验证与后续工作/本次公网发布核验.json。此前待发布和工具阻塞描述为历史状态。\n'
for rel in ['AGENTS.md','先读我.txt','03_当前APP/功能与使用说明-R4.txt','05_后台与研发说明/动态分类与老师推荐使用说明.txt','05_后台与研发说明/Netlify部署说明.txt']:
 p=r/rel;p.write_text(p.read_text(encoding='utf-8').rstrip()+note,encoding='utf-8')
(r/'05_后台与研发说明/公网发布续接说明.txt').write_text('当前待发布工作已完成。\n'+note+'\n源码提交：'+report['commit_sha']+'\nNetlify部署：'+report['netlify_deploy_id']+'\nSites部署：'+report['sites_deployment_id']+'\n',encoding='utf-8')
p=r/'交接资料验证.json';d=read(p);d.update(updated_beijing=now,latest_publication=report)
def resolve_flags(v):
 if isinstance(v,dict):
  for k in v:
   if k in ('public_deployment_pending','cloud_prepared_not_deployed','source_sync_pending'):v[k]=False
   else:resolve_flags(v[k])
 elif isinstance(v,list):
  for x in v:resolve_flags(x)
resolve_flags(d);write(p,d)
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
p=r/'原始来源与文件校验.json';d=read(p);d['files']=rows;d['current_revision']={'updated_beijing':now,'scope':'Published source and actual public verification; private runtime excluded','public_deployment_pending':False,'delivery_record':'06_验证与后续工作/本次公网发布核验.json'};write(p,d)
print('Publication recorded; manifest files:',len(rows))
