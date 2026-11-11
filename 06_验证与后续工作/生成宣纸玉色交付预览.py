from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,datetime
r=next(p for p in Path.cwd().iterdir()if p.is_dir());v=r/'06_验证与后续工作';font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
cv=Image.new('RGB',(1320,1100),'#f7f3e9');d=ImageDraw.Draw(cv);d.text((32,25),'东方智慧 · 宣纸玉色主题',font=font(36),fill='#273d32');d.text((34,82),'默认日间 · 原创淡墨山水 / 玉绿 / 中文排版 · 实际页面预览',font=font(21),fill='#5e6d5f')
for i,(title,name)in enumerate([('首页','试改-首页.png'),('身体地图','试改-身体地图.png'),('禅修练习','试改-禅修练习.png')]):
 x=25+i*435;d.rounded_rectangle((x,140,x+410,1080),radius=12,fill='#fffdf7',outline='#d2d9c9');d.text((x+20,157),title,font=font(25),fill='#385f4c');im=Image.open(v/name).convert('RGB');im.thumbnail((382,855),Image.Resampling.LANCZOS);cv.paste(im,(x+(410-im.width)//2,213))
cv.save(v/'宣纸玉色东方康养主题预览.png')
j=json.loads((v/'本轮全量回归结果.json').read_text(encoding='utf-8'))['latest'];report={'atBeijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'reason':'用户否定黑色主题缺少东方文化辨识度，并明确要求立即改为明亮东方康养表达','status':'已实现，待用户视觉评价','changes':['宣纸白、玉绿、淡墨及少量古铜色统一主体验','中文标题、留白及原创每日一句SVG山水；没有重复莲花或光圈','APP和负责人查看页默认日间','旧默认外观按appearanceRevision迁移一次，之后主动日夜选择继续保存','三大地图、AI、课程、签到、音乐、个人页、计时浮层和练习页统一主题','业务交互、自动计时与设备真实数据状态保持原规则'],'regression':{'pass':j['pass'],'passed':j['passed'],'failed':j['failed'],'browser':j['coverage']['browser'],'backendUnitChecks':5,'liveAI':False,'realHardware':False},'rollbackArchives':['07_历史版本仅供追溯/科技禅修改版前可回退存档-2026-10-27-143214.zip','07_历史版本仅供追溯/莲花试改版-已否定-可回退-2026-10-27-153613.zip','07_历史版本仅供追溯/石墨蓝主题-已否定-可回退-2026-10-27-163957.zip'],'preview':'宣纸玉色东方康养主题预览.png','previewUrl':'http://127.0.0.1:8765/app?theme=paper-jade-20261027'}
(v/'宣纸玉色东方康养交付记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');f=v/'成熟身心科技主题替换记录.json';old=json.loads(f.read_text(encoding='utf-8'));old['status']='已被用户否定过黑、缺少东方文化感；已替换，见宣纸玉色东方康养交付记录.json';f.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
f=r/'07_历史版本仅供追溯/科技禅修改版回退说明.txt';s=f.read_text(encoding='utf-8');s+='\n2026-10-27 后续：石墨蓝主题被用户否定，源码和构建页面另存为“石墨蓝主题-已否定-可回退-2026-10-27-163957.zip”，72文件校验通过，不含数据库。当前为宣纸玉色明亮主题，具体变更见06目录宣纸玉色东方康养交付记录.json。\n';f.write_text(s,encoding='utf-8')
print('Bright-theme screenshots and actual delivery record saved.')
