from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,csv,os,re
r=Path(__file__).resolve().parent.parent;q=r/'06_验证与后续工作';now=datetime.now(timezone(timedelta(hours=8))).isoformat()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
identity=read(q/'创作者平台改版发布身份.json');local=read(q/'本轮全量回归结果.json')['latest'];cloud=read(q/'公网适配全量回归结果.json')['latest'];public=read(q/'创作者公网验收.json')
assert local['pass'] and local['passed']==56 and cloud['pass'] and cloud['passed']==56 and public['pass']
assert '界面重构' in local['module'] and '界面重构' in cloud['module']
proofs={}
for name in ['创作者数据分析改版核验','创作者平台改版界面核验','创作者平台改版云端界面核验']:
 d=read(q/(name+'.json'));assert d['pass'];proofs[name]={'pass':True,'at':d['at'],'checks':len(d['checks']),'scope':d.get('scope'),'errors':d.get('errors',[])}
for name,digest in local['buildHashes'].items():assert hashlib.sha256((r/'03_当前APP'/name).read_bytes()).hexdigest()==digest
record={**identity,'at':now,'status':'published_and_verified','public_deployment_pending':False,'reference':'06_验证与后续工作/创作者平台参考拆解.json','scope':['整体登录与桌面导航重构','账号条、组合首页、审核动态与创作服务','封面作品列表与类型/状态/日期/排序/搜索','安全CSV导出与可交互指标趋势图','真实前一周期分析与每日指标','视频上传进度/预览与课程编辑'],'local_full':{'passed':local['passed'],'failed':local['failed'],'at':local['at'],'buildHashes':local['buildHashes']},'cloud_full':{'passed':cloud['passed'],'failed':cloud['failed'],'at':cloud['at'],'buildHashes':cloud.get('cloudBuildHashes')},'specialized':proofs,'public':public,'creator_source_sha256':hashlib.sha256((r/'04_研发源码/app/r4/creator-center.html').read_bytes()).hexdigest(),'visual_approval':'实现仍待用户视觉评价','limits':['AI模型/知识库当前未配置，仍由人工审核','图片与音视频自动识别审核尚未接入','无同类作者或外部平台基准、无收益结算数据','历史未采集数据不补算，上一周期不足时不生成涨幅'],'backup':str(sorted((r/'07_历史版本仅供追溯').glob('创作者平台重做前-*.zip'))[-1].relative_to(r))}
write(q/'创作者平台改版交付记录.json',record)
p=r/'05_后台与研发说明/Netlify站点身份.json';d=read(p);d.update(previous_deploy_id=d['deploy_id'],deploy_id=identity['netlify_deploy_id'],checked_at=now,latest_change='创作者平台整体界面重构与数据分析升级',status='deployed');write(p,d)
note='\n\n2026年11月4日：创作者平台按用户截图整体改版\n用户否定此前创作者界面过于简易，提供8张抖音截图要求类似的成熟创作者中心。本轮按其导航、账号条、主辅栏、发布入口、内容列表和数据分析结构重做实际页面，保留东方智慧品牌与真实业务。登录、首页、内容管理、数据中心、咨询、创作服务、账号设置和发布编辑界面均已更新。不是用户已认可的最终设计，后续按其视觉反馈继续调整。\n本机和真实本地Cloudflare完整回归各56通过，改版专项与真实前后台联调、公网验收通过，证据见06_验证与后续工作/创作者平台改版交付记录.json。原账号与云端数据保留。AI模型和公司知识库未配置，自动审核仍关闭；图片/音视频转人工。\n入口仍为https://eastern-wisdom-demo-fuyao.netlify.app/creator。未重打完整交付ZIP。\n'
for rel in ['AGENTS.md','先读我.txt','03_当前APP/功能与使用说明-R4.txt','05_后台与研发说明/公网发布续接说明.txt']:
 p=r/rel;s=p.read_text(encoding='utf-8')
 if '2026年11月4日：创作者平台按用户截图整体改版' not in s:p.write_text(s.rstrip()+note,encoding='utf-8')
p=r/'05_后台与研发说明/创作者中心使用与审核说明.txt';s=p.read_text(encoding='utf-8');extra='\n\n创作者平台改版操作\n首页采用固定顶部/左侧导航、账号概览、发布工具、数据卡片、审核动态与待办。作品发布菜单可选视频、图文、课程；创作服务内可查看实际操作指南。\n内容管理可按类型、审核状态、日期、排序和关键词组合筛选；数据导出遵循当前筛选，CSV文本已做公式注入防护。作品列表直接显示封面与近选定周期的单条表现。\n数据中心点击指标卡可切换真实趋势；鼠标悬停或键盘聚焦图表可看某日数值。支持7/30/90天与上一周期比较；采集历史不足时显示暂无完整上期数据。没有虚构同类作者基准。\n时长和完播率来自已采集的播放事件，分母为0时不生成百分比。新增关注是仍保留的关注关系在周期内建立的数量，不代表净增。\n发布编辑支持上传进度、素材预览、章节和草稿；提交后仍沿用原AI初审/人工复核流程。\n'
if '创作者平台改版操作' not in s:p.write_text(s.rstrip()+extra,encoding='utf-8')
p=r/'改动任务表-2026-10-22.html';s=p.read_text(encoding='utf-8');s=re.sub(r'(<section id="creator-platform-redesign">[\s\S]*?<p data-redesign-status>)[\s\S]*?(</p>)',r'\1已发布并通过本机/云端各56项回归及改版专项、公网验收：导航、组合首页、封面作品列表、可交互数据中心与完整登录/编辑页面已重做。\2',s);p.write_text(s,encoding='utf-8')
p=r/'交接资料验证.json';d=read(p);d.update(updated_beijing=now,creator_platform_redesign=record);write(p,d)
skip_dirs={'.git','__pycache__','node_modules','.venv','.wrangler','.sites-runtime','.netlify','dist','.next','.vinext','.cache','coverage'};skip_suffixes={'.zip','.7z','.rar','.tar','.gz','.tgz','.pyc','.log','.db','.pem','.key','.pfx','.p12','.tsbuildinfo'};rows=[]
for current,dirs,names in os.walk(r):
 dirs[:]=[d for d in dirs if d not in skip_dirs and not (Path(current)/d).is_symlink()]
 for name in names:
  p=Path(current)/name
  if p.is_symlink() or p.suffix.lower() in skip_suffixes or any(x in name.lower() for x in ('.sqlite','.env','.dev.vars')) or name in {'资料校验清单.csv','原始来源与文件校验.json','.DS_Store','Thumbs.db'}:continue
  data=p.read_bytes();rows.append({'path':p.relative_to(r).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
rows.sort(key=lambda x:x['path'])
with (r/'资料校验清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['包内相对位置','字节数','SHA-256']);w.writerows((x['path'],x['bytes'],x['sha256']) for x in rows)
p=r/'原始来源与文件校验.json';d=read(p);d['files']=rows;d['current_revision']={'updated_beijing':now,'scope':'Creator platform redesign published and verified; private runtime excluded','public_deployment_pending':False,'delivery_record':'06_验证与后续工作/创作者平台改版交付记录.json'};write(p,d)
assert all(hashlib.sha256((r/x['path']).read_bytes()).hexdigest()==x['sha256'] for x in rows)
print(json.dumps({'pass':True,'files':len(rows),'local_full':local['passed'],'cloud_full':cloud['passed'],'public':len(public['checks'])}))
