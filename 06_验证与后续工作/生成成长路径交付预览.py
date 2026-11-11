from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,datetime
r=next(p for p in Path.cwd().iterdir()if p.is_dir());v=r/'06_验证与后续工作';font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
cv=Image.new('RGB',(1320,1100),'#f7f3e9');d=ImageDraw.Draw(cv);d.text((32,25),'东方智慧 · 成长路径结构试改',font=font(36),fill='#273d32');d.text((34,82),'场景入口 / 觉察—实践—回看 / 真实练习计时 · 实际页面',font=font(21),fill='#5e6d5f')
for i,(title,name)in enumerate([('三大地图主通道','试改-首页.png'),('觉察、实践与回看','试改-身体地图.png'),('日常修习体验','试改-禅修练习.png')]):
 x=25+i*435;d.rounded_rectangle((x,140,x+410,1080),radius=12,fill='#fffdf7',outline='#d2d9c9');d.text((x+20,157),title,font=font(24),fill='#385f4c');im=Image.open(v/name).convert('RGB');im.thumbnail((382,855),Image.Resampling.LANCZOS);cv.paste(im,(x+(410-im.width)//2,213))
cv.save(v/'成长路径结构重构预览.png')
j=json.loads((v/'本轮全量回归结果.json').read_text(encoding='utf-8'))['latest'];report={'atBeijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'reason':'用户要求重新阅读产品理念并明确开始重做结构，不能继续在菜单上换皮','status':'结构试改已实现，待用户评价','changes':['首页三大地图改为主次场景入口，核心行动为认识、修复、提升自己','复用项目原有树、银杏、静坐、山水与静室自有图像，没有新增外部素材','地图内增加可操作的觉察、实践、回看记录路径','禅修页改为真实练习时间、播放状态、实际引导与节奏线；移除大空框','保留首页五项快捷功能结束范围、日间默认、主动外观偏好、后台封面和自动计时','新增真实连续导航及练习计时显示回归检查'],'regression':{'pass':j['pass'],'passed':j['passed'],'failed':j['failed'],'browser':j['coverage']['browser'],'backendUnitChecks':5,'liveAI':False,'realHardware':False},'rollback':'07_历史版本仅供追溯/宣纸菜单版-已否定-可回退-2026-10-27-170224.zip','rollbackVerifiedFiles':72,'preview':'成长路径结构重构预览.png','previewUrl':'http://127.0.0.1:8765/app?theme=growth-space-20261027'}
(v/'成长路径结构重构交付记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');f=v/'宣纸玉色东方康养交付记录.json';old=json.loads(f.read_text(encoding='utf-8'));old['status']='原菜单结构已被用户否定；已重构，见成长路径结构重构交付记录.json';f.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
f=r/'07_历史版本仅供追溯/科技禅修改版回退说明.txt';s=f.read_text(encoding='utf-8');s+='\n2026-10-27 后续：按用户要求重读产品方向后重做结构。改前源码和查看页已归档为“宣纸菜单版-已否定-可回退-2026-10-27-170224.zip”，72文件校验通过，不含运行数据库。新结构交付记录见06目录成长路径结构重构交付记录.json。\n';f.write_text(s,encoding='utf-8')
print('Current structural preview and delivery evidence saved.')
