from pathlib import Path
from datetime import datetime,timezone,timedelta
import csv,hashlib,json,os
root=Path(__file__).resolve().parent.parent;q=root/'06_验证与后续工作'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=datetime.now(timezone(timedelta(hours=8))).isoformat()
local=read(q/'本轮全量回归结果.json')['latest'];auto=read(q/'推荐视频自动播放-公网核验.json');smoke=read(q/'老师社群-公网验收.json')
assert local['pass'] and local['module']=='推荐视频进入自动播放' and auto['pass'] and smoke['pass']
deploy='6ae950bada2b958012da9597'
p=root/'05_后台与研发说明/Netlify站点身份.json';identity=read(p);old=identity['deploy_id'];identity.update(previous_deploy_id=old,deploy_id=deploy,checked_at=now,latest_change='推荐视频进入及切换自动播放');write(p,identity)
record={'at':now,'deploy_id':deploy,'previous_deploy_id':old,'site':identity['url'],
'changes':['进入推荐页及切换视频自动播放，默认静音','主动暂停在同页重绘后保留；离开社群暂停，重新进入自动播放','切换窗口时暂停，回来恢复此前播放意图；主动暂停不被取消','有声自动播放被拒时静音重试；完全禁止自动播放时保留手动播放入口','仅当前一条视频播放，旧页面的异步播放请求不影响新页面'],
'checks':{'local_full':{'passed':local['passed'],'failed':local['failed'],'at':local['at']},'local_autoplay':read(q/'推荐视频自动播放-本地核验.json'),'public_autoplay':auto,'public_existing':smoke},
'buildHashes':local['buildHashes'],'backup':'07_历史版本仅供追溯/推荐视频自动播放改前-20261103-110658.zip',
'limits':['四语自动播放及浏览器真实播放已验；两种拒绝播放分支通过模拟NotAllowedError验证，不能视为覆盖所有手机浏览器','本次仅前端播放逻辑，后端账号、数据和接口未更改；未重新打包旧桌面ZIP']}
write(q/'推荐视频自动播放交付记录.json',record)
note='\n\n2026年11月3日：推荐视频自动播放\n用户要求进入社群推荐视频后直接播放，已改为进入推荐页及切换视频自动播放、默认静音。此前“手动开始”的要求由本次明确指令更新。\n手动暂停、静音开关及进度拖动保留；离开社群暂停，回到推荐页自动播放；切到后台暂停，返回恢复此前的播放意图。浏览器拒绝有声播放时自动静音重试，完全禁止自动播放时保留可操作的播放入口。\n当前本机56项回归通过，本地和公网各14项自动播放检查通过，公网既有8项验收通过。部署ID为'+deploy+'，原公网地址不变。\n源码、03查看页和Netlify公网已同步；本次未重新打包旧桌面ZIP。证据见06_验证与后续工作/推荐视频自动播放交付记录.json。\n'
for rel in ('AGENTS.md','先读我.txt','03_当前APP/功能与使用说明-R4.txt','05_后台与研发说明/老师课程分类与社群视频使用说明.txt'):
 p=root/rel;s=p.read_text(encoding='utf-8')
 if '2026年11月3日：推荐视频自动播放' not in s:p.write_text(s.rstrip()+note,encoding='utf-8')
p=root/'交接资料验证.json';d=read(p);d.update(updated_beijing=now,community_autoplay_delivery=record);write(p,d)
skip_dirs={'.git','__pycache__','node_modules','.venv','.wrangler','.sites-runtime','.netlify','dist','.next','.vinext','.cache','coverage'}
skip_suffixes={'.zip','.7z','.rar','.tar','.gz','.tgz','.pyc','.log','.db','.pem','.key','.pfx','.p12','.tsbuildinfo'}
rows=[]
for current,dirs,names in os.walk(root):
 dirs[:]=[d for d in dirs if d not in skip_dirs and not (Path(current)/d).is_symlink()]
 for name in names:
  p=Path(current)/name
  if p.is_symlink() or p.suffix.lower() in skip_suffixes or any(x in name.lower() for x in ('.sqlite','.env','.dev.vars')) or name in {'资料校验清单.csv','原始来源与文件校验.json','.DS_Store','Thumbs.db'}:continue
  data=p.read_bytes();rows.append({'path':p.relative_to(root).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
rows.sort(key=lambda x:x['path'])
with (root/'资料校验清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['包内相对位置','字节数','SHA-256']);w.writerows((x['path'],x['bytes'],x['sha256']) for x in rows)
p=root/'原始来源与文件校验.json';d=read(p);d['files']=rows;d['current_revision']={'updated_beijing':now,'scope':'Current source, build and documentation; private runtime and archived ZIPs excluded','local_regression_pass':True,'delivery_record':'06_验证与后续工作/推荐视频自动播放交付记录.json'};write(p,d)
print(json.dumps({'pass':True,'deploy_id':deploy,'regression_passed':local['passed'],'public_autoplay_checks':len(auto['checks'])}))

