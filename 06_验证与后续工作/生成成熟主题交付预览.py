from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,datetime
r=next(p for p in Path.cwd().iterdir()if p.is_dir());v=r/'06_验证与后续工作';font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
cv=Image.new('RGB',(1320,1100),'#0d131b');d=ImageDraw.Draw(cv);d.text((32,25),'东方智慧 · 身心科技主题替换',font=font(36),fill='#edf2f7');d.text((34,82),'石墨蓝 / 冷白 · 功能分区 · 实际页面预览',font=font(22),fill='#a5b5c7')
for i,(title,name)in enumerate([('首页','试改-首页.png'),('身体地图','试改-身体地图.png'),('禅修练习','试改-禅修练习.png')]):
 x=25+i*435;d.rounded_rectangle((x,140,x+410,1080),radius=12,fill='#151e29',outline='#344457');d.text((x+20,157),title,font=font(25),fill='#b5cde7');im=Image.open(v/name).convert('RGB');im.thumbnail((382,855),Image.Resampling.LANCZOS);cv.paste(im,(x+(410-im.width)//2,213))
cv.save(v/'成熟身心科技主题预览.png')
j=json.loads((v/'本轮全量回归结果.json').read_text(encoding='utf-8'))['latest'];report={'atBeijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'reason':'用户否定莲花试改主题并要求换掉','status':'替换试改已实现，待用户视觉评价','changes':['移除重复莲花SVG、光圈、柔光和练习场景背景','石墨蓝、冷白与统一线性控件','首页三大地图改为纵向紧凑分区；保留五项快捷功能结束位置','身体、AI、音乐、签到、个人页和查看页统一样式','设备页移除装饰检测波形，维持授权与真实测量状态','修复社群内容未变化时重复刷新重建视频节点、打断播放的问题'],'regression':{'pass':j['pass'],'passed':j['passed'],'failed':j['failed'],'browser':j['coverage']['browser'],'backendUnitChecks':5,'liveAI':False,'realHardware':False},'rollbackArchives':['07_历史版本仅供追溯/科技禅修改版前可回退存档-2026-10-27-143214.zip','07_历史版本仅供追溯/莲花试改版-已否定-可回退-2026-10-27-153613.zip'],'preview':'成熟身心科技主题预览.png'}
(v/'成熟身心科技主题替换记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');f=v/'科技禅修试改交付记录.json';old=json.loads(f.read_text(encoding='utf-8'));old['status']='已被用户否定；已替换，见成熟身心科技主题替换记录.json';f.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
print('Current preview and rejection/replacement records saved.')
