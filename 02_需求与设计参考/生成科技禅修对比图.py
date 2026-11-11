from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import json
out=next(p for p in Path.cwd().iterdir() if p.is_dir())/'02_需求与设计参考'
F='C:/Windows/Fonts/msyh.ttc'
font=lambda n:ImageFont.truetype(F,n)
sets=[('科技禅修 · 方向参考  1—4',[
 ('1  Sleepscape','项目展示图 · 曼陀罗 / 光线 / 呼吸感',['Sleepscape-1'],['优先看：东方对称纹样与柔光的结合','用于禅修视觉；不能据此认定治疗效果'],'heelago/Sleepscape'),
 ('2  PauseState','实际演示动图截帧 · 呼吸引导',['PauseState-1'],['优先看：动作与呼吸节奏同步','借鉴反馈方式；光球外形不建议直接照搬'],'natebru/PauseState'),
 ('3  Uposath','项目公开 APP 界面 · 东方修习',['uposath-1','uposath-2'],['优先看：黑金层级与修习内容组织','东方语境较强；科技感需另行加强'],'Stonks007/uposath'),
 ('4  Sough','仓库品牌展示图 · 并非完整 APP 界面',['Sough-1'],['优先看：墨蓝、青绿与自然线条','用于配色方向参考，不能作为整页设计依据'],'martinhv/sough')]),
 ('身体康养 · 科技参考  5—8',[
 ('5  Edge / OpenStrap','项目公开 APP 界面 · 独立开源项目',['WHOOP-1','WHOOP-2'],['优先看：状态仪表与呼吸反馈的联动','适合身体地图与设备页；不是 WHOOP 官方 APP'],'jacobomolinaferrer/WHOOP'),
 ('6  Garmin Health Dashboard','项目公开界面 · 独立项目，非 Garmin 官方',['garmin-health-dashboard-1','garmin-health-dashboard-2'],['优先看：睡眠、压力、HRV 的信息层级','适合设备数据页；不照搬运动评分结论'],'cggmx/garmin-health-dashboard'),
 ('7  PulseCoach','项目公开桌面界面 · HRV 分析',['ha-garmin-fitness-coach-app-1'],['优先看：趋势曲线、状态与数据分区','只参考数据表达，不照搬密集桌面排版'],'askb/ha-garmin-fitness-coach-app'),
 ('8  WebGL Fluid Simulation','视觉效果项目 · 并非康养 APP',['WebGL-Fluid-Simulation-1'],['优先看：数字流体与水墨流动的相似性','建议降饱和、减亮度，局部用于呼吸 / 音景'],'PavelDoGreat/WebGL-Fluid-Simulation')])]
for page,(title,cards) in enumerate(sets,1):
 cv=Image.new('RGB',(2200,1920),'#0A1019');d=ImageDraw.Draw(cv)
 d.text((55,35),title,font=font(55),fill='#F0F5F8');d.text((58,110),'GitHub 公开项目原图整理 · 下方为借鉴判断，未修改东方智慧 APP · 2026-10-27',font=font(28),fill='#A6B5C4')
 for j,(name,typ,images,notes,repo)in enumerate(cards):
  x=40+j%2*1080;y=180+j//2*850;d.rounded_rectangle((x,y,x+1040,y+820),radius=22,fill='#131E2B',outline='#2B3B4B',width=2)
  d.text((x+28,y+20),name,font=font(37),fill='#EDF4F6');d.text((x+28,y+76),typ,font=font(24),fill='#8FC7C4')
  box=(x+25,y+122,990,540)
  if len(images)==2:
   for k,n in enumerate(images):
    im=Image.open(out/('科技禅修参考-'+n+'.png'));im.thumbnail((445,535),Image.Resampling.LANCZOS);cv.paste(im,(x+45+k*490+(445-im.width)//2,y+125+(535-im.height)//2))
  else:
   im=Image.open(out/('科技禅修参考-'+images[0]+'.png'));im.thumbnail((990,540),Image.Resampling.LANCZOS);cv.paste(im,(x+25+(990-im.width)//2,y+122+(540-im.height)//2))
  for k,line in enumerate(notes):d.text((x+28,y+685+k*40),line,font=font(26),fill='#E0E7EE')
  d.text((x+28,y+778),repo,font=font(21),fill='#8495A7')
 cv.save(out/f'科技禅修案例对比-{page}-2026-10-27.png')
notes='''2026-10-27 用户最新视觉要求：科技感强，同时贴合东方智慧、禅修、身体康养。此前普通冥想/效率工具三款参考不满足要求。当前仅调研展示，由用户选定后再实施。
本轮检索15个GitHub项目，选出8个图片候选；来源见科技禅修GitHub案例调研-2026-10-27.json、科技禅修截图来源-2026-10-27.json。
图片分为APP界面、演示动图截帧、品牌展示图和效果项目，图上逐一注明。品牌图不代表完整UI，视觉效果不证明医疗疗效。第三方设备项目不能写成品牌官方APP。
我的建议：Sleepscape作为东方禅修视觉的优先参考；Edge与Garmin Health Dashboard作为身体数据结构参考；PauseState作为呼吸同步反馈参考；流体效果需低饱和、局部化，不能直接照搬霓虹效果。以上为建议，未获用户选定。
未修改业务代码、构建页面或后台数据；未实施新的视觉方案。
'''
(out/'科技禅修案例选型说明-2026-10-27.txt').write_text(notes,encoding='utf-8')
print('Created 2 verified-source comparison sheets and selection notes.')
