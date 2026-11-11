from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
p=Path(__file__).resolve().parent
canvas=Image.new('RGB',(2030,920),'#e4e5db');d=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
for i,n in enumerate(['首页','智慧馆','AI服务','社群','我的']):
 x=15+i*403;d.text((x,14),n,font=font,fill='#273d32');im=Image.open(p/f'统一界面-{n}.png').convert('RGB');canvas.paste(im,(x,50))
canvas.save(p/'五大主页面实际效果.png')
