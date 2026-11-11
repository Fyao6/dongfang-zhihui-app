from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib,sys,re
root=Path(__file__).resolve().parent.parent;q=root/'06_验证与后续工作'
deploy_id=sys.argv[1]
assert re.fullmatch('[a-f0-9]{24}',deploy_id)
now=datetime.now(ZoneInfo('Asia/Shanghai'))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
local=read(q/'本轮全量回归结果.json')['latest'];public=read(q/'老师社群-公网验收.json')
assert local['pass'] and local['module']=='老师社群含视频封面最终验收' and public['pass']
record_path=q/'老师分类与社群视频交付记录.json';record=read(record_path);old=record['deploy_id']
record.update(at=now.isoformat(),deploy_id=deploy_id,asset_hotfix_previous_deploy_id=old)
record['checks']['local_full']={'passed':local['passed'],'failed':local['failed'],'at':local['at']}
record['checks']['public']=public['checks'];record['checks']['public_at']=public['at']
record['checks']['poster']='真实公网四语预览视频封面均成功加载，尺寸1080×1920；社群播放专项与本机56项回归重新通过。'
record['checks']['cloud_full_scope']='云端56项回归对应同一老师/社群业务实现；随后只增加预览视频poster及静态图片资源，该差异由公网真实加载、四语页面及播放专项再次核验。'
poster=root/'04_研发源码/app/r4/images/community-preview-poster.jpg'
record['poster']={'source':'用户此前提供并已保存的community-preview.mp4实际视频帧','path':str(poster.relative_to(root)),'sha256':hashlib.sha256(poster.read_bytes()).hexdigest()}
record['output_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'03_当前APP').glob('*.html')}
write(record_path,record)
p=root/'05_后台与研发说明/Netlify站点身份.json';identity=read(p);identity.update(deploy_id=deploy_id,previous_deploy_id=old,checked_at=now.isoformat());write(p,identity)
p=root/'交接资料验证.json';d=read(p);d.update(updated_beijing=now.isoformat(),teacher_community_delivery=record);write(p,d)
for p in [root/'先读我.txt',root/'03_当前APP/功能与使用说明-R4.txt',root/'AGENTS.md']:
 s=p.read_text(encoding='utf-8').replace(old,deploy_id)
 if p.name=='先读我.txt':s=re.sub(r'更新时间：[^\n]+','更新时间：'+now.strftime('%Y-%m-%d %H:%M:%S +08:00'),s,count=1)
 p.write_text(s,encoding='utf-8')
p=root/'05_后台与研发说明/老师课程分类与社群视频使用说明.txt';s=p.read_text(encoding='utf-8');s+='\n视频预览已补充从原视频提取的真实封面，避免未播放时出现黑色首帧。封面随离线页面内嵌，公网由同站点提供。\n';p.write_text(s,encoding='utf-8')
p=root/'AGENTS.md';s=p.read_text(encoding='utf-8');s+='\n社群封面补充：最终公网截图发现未播放首帧偶有黑屏，已从用户原视频提取真实JPEG帧并接入原构建/公网资产。含封面的本机56项回归重新通过，公网四语封面加载与播放验收通过；云端56项业务回归在封面增补前完成，封面差异另有专项核验，不混同测试构建哈希。\n';p.write_text(s,encoding='utf-8')
print(json.dumps({'pass':True,'deploy_id':deploy_id,'local':local['passed'],'public':len(public['checks']),'poster_sha256':record['poster']['sha256']}))

