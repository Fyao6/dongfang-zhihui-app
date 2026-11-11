from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,csv,os
from lxml import html,etree
root=Path(__file__).resolve().parent.parent
qa=root/'06_验证与后续工作'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,obj): p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
now=datetime.now(timezone(timedelta(hours=8))).isoformat()
reg=read(qa/'本轮全量回归结果.json')['latest']
local=read(qa/'社群底部布局-本地核验.json')
public=read(qa/'社群底部布局-公网核验.json')
smoke=read(qa/'老师社群-公网验收.json')
assert reg['pass'] and reg['module']=='社群视频底部细进度条与左下标题'
assert local['pass'] and public['pass'] and smoke['pass']
identity_path=root/'05_后台与研发说明/Netlify站点身份.json'
identity=read(identity_path)
previous=identity['deploy_id']
deploy='6ae9483475f9c5aec50232cc'
identity.update(deploy_id=deploy,previous_deploy_id=previous,checked_at=now,latest_change='社群底部细进度条与左下标题')
write(identity_path,identity)
record={'at':now,'deploy_id':deploy,'previous_deploy_id':previous,'site':identity['url'],
'changes':['进度条贴视频底边，默认2px淡白细线，无常驻时间、金色滑块及重复播放按钮','标题、作者与说明移至左下，标题和说明最多两行预览','进度交互时显示时间与滑块，鼠标触摸键盘均可跳转','三标签导航、声音、视频切换和离页暂停保留'],
'backup':'07_历史版本仅供追溯/社群视频底部布局改前-20261103-103119.zip',
'checks':{'local_full':{'passed':reg['passed'],'failed':reg['failed'],'at':reg['at']},'local_layout':len(local['results']),'public_layout':len(public['results']),'interactions':public['interactionChecks'],'public_existing':smoke['checks']},
'buildHashes':reg['buildHashes'],'limits':['本次只改前端样式与进度交互，未改变后端接口或云端内容','桌面10时13分ZIP是本次调整前的交付快照，本次未重打包；当前源码、03目录页面和公网已更新']}
write(qa/'社群底部布局交付记录.json',record)
note='''

2026年11月3日：社群视频底部布局
视频进度条贴在视频底边、底部导航上方，默认是2px淡色细线；拖动或键盘操作时才突出显示滑块与时间，结束后淡出。
作者、标题和说明移到左下角；移除旧的常驻播放/时间工具栏。鼠标、触摸、键盘跳转及画面点击播放暂停继续可用。
本机完整前后台56项回归通过；本地与公网各12组语言/尺寸布局、真实鼠标触摸键盘操作及公网8项既有验收通过。
公网已同步至部署6ae9483475f9c5aec50232cc，源码与03目录查看页一致。证据见06_验证与后续工作/社群底部布局交付记录.json。
桌面10时13分的ZIP为本次调整前快照，未覆盖；本次未重打包。
'''
for rel in ('AGENTS.md','先读我.txt','03_当前APP/功能与使用说明-R4.txt','05_后台与研发说明/老师课程分类与社群视频使用说明.txt'):
 p=root/rel;s=p.read_text(encoding='utf-8')
 if '2026年11月3日：社群视频底部布局' not in s:p.write_text(s.rstrip()+note,encoding='utf-8')
p=root/'交接资料验证.json';d=read(p);d.update(updated_beijing=now,community_bottom_layout=record);write(p,d)
p=root/'打开这里.html';doc=html.fromstring(p.read_text(encoding='utf-8'))
for old in doc.xpath('//*[@id="community-bottom-delivery"]'):old.getparent().remove(old)
section=html.fragment_fromstring('<section id="community-bottom-delivery"><h2>11月3日最新调整：社群视频底部布局</h2><p>底边弱化进度条，左下角标题与说明；四语布局及本机56项回归已通过。</p><p><a href="https://eastern-wisdom-demo-fuyao.netlify.app/?lang=zh-Hans&amp;page=community&amp;v=community-bottom-20261103">打开新版社群</a> · <a href="06_验证与后续工作/社群底部布局交付记录.json">本次验证记录</a></p></section>')
(doc.xpath('//main') or doc.xpath('//body'))[0].insert(0,section)
p.write_text('<!doctype html>\n'+etree.tostring(doc,encoding='unicode',method='html'),encoding='utf-8')
skip_dirs={'.git','__pycache__','node_modules','.venv','.wrangler','.sites-runtime','.netlify','dist','.next','.vinext','.cache','coverage'}
skip_suffixes={'.zip','.7z','.rar','.tar','.gz','.tgz','.pyc','.log','.db','.pem','.key','.pfx','.p12','.tsbuildinfo'}
manifest=[]
for current,dirs,names in os.walk(root):
 dirs[:]=[d for d in dirs if d not in skip_dirs and not (Path(current)/d).is_symlink()]
 for name in names:
  p=Path(current)/name
  if p.is_symlink() or p.suffix.lower() in skip_suffixes or any(x in name.lower() for x in ('.sqlite','.env','.dev.vars')) or name in {'资料校验清单.csv','原始来源与文件校验.json','.DS_Store','Thumbs.db'}:continue
  data=p.read_bytes();manifest.append({'path':p.relative_to(root).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
manifest.sort(key=lambda x:x['path'])
with (root/'资料校验清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.writer(f);writer.writerow(['包内相对位置','字节数','SHA-256']);writer.writerows((r['path'],r['bytes'],r['sha256']) for r in manifest)
p=root/'原始来源与文件校验.json';d=read(p);d['files']=manifest;d['current_revision']={'updated_beijing':now,'scope':'Current source, build and documentation; archived ZIPs excluded','local_regression_pass':True,'delivery_record':'06_验证与后续工作/社群底部布局交付记录.json'};write(p,d)
print(json.dumps({'pass':True,'manifest_files':len(manifest),'deploy_id':deploy,'regression_passed':reg['passed']}))

