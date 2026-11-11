import urllib.request,json,re,io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from PIL import Image,ImageOps,ImageDraw,ImageFont
root=next(p for p in Path.cwd().iterdir() if p.is_dir())
out=root/'02_需求与设计参考'
def get(u):
 return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=35).read()
med=json.loads(get('https://itunes.apple.com/lookup?id=1500780518&country=us'))['results'][0]['screenshotUrls']
class P(HTMLParser):
 urls=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='img' and 'creenshot' in a.get('alt','') and a.get('src') not in self.urls:self.urls.append(a['src'])
p=P();p.feed(get('https://play.google.com/store/apps/details?id=io.ente.ensu&hl=en').decode())
items=[('Medito',i+1,re.sub(r'/320x480bb.jpg$','/800x0w.jpg',u)) for i,u in enumerate(med[1:3])]+[('Ensu',i+1,u.split('=w526')[0]+'=w800') for i,u in enumerate(p.urls[:2])]+[('Mindful',i+1,'https://raw.githubusercontent.com/akaMrNagar/Mindful/main/docs/assets/screenshots/screenshot_'+str(n)+'.png') for i,n in enumerate([1,5])]
def dl(item):
 name,i,u=item;b=get(u);im=Image.open(io.BytesIO(b)).convert('RGB');path=out/f'GitHub主题参考-{name}-{i}.png';im.save(path);return dict(app=name,index=i,url=u,file=str(path),size=im.size)
with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(dl,items))
(out/'GitHub主题截图来源-2026-10-27.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
# First proof sheet, original screenshots are fitted without cropping.
canvas=Image.new('RGB',(1800,1100),'#EBECEF');d=ImageDraw.Draw(canvas)
font='C:/Windows/Fonts/msyh.ttc'
f=ImageFont.truetype(font,42);small=ImageFont.truetype(font,24)
d.text((55,30),'东方智慧 · APP 主题参考对比',font=f,fill='#171A20')
d.text((58,96),'官方商店 / 项目仓库公开截图 · 仅作选型参考 · 2026-10-27',font=small,fill='#60666E')
for c,name in enumerate(['Medito','Ensu','Mindful']):
 x=35+c*590;d.rounded_rectangle((x,160,x+565,1050),radius=22,fill='white');d.text((x+25,185),str(c+1)+'  '+name,font=f,fill='#171A20')
 for i in range(2):
  r=next(r for r in results if r['app']==name and r['index']==i+1);im=Image.open(r['file']);im.thumbnail((255,1050),Image.Resampling.LANCZOS);canvas.paste(im,(x+20+i*275+(255-im.width)//2,270))
 descriptions={'Medito':['炭灰界面 · 彩色内容插画','适合：冥想、音乐、课程'], 'Ensu':['暖白 / 炭黑 · 简洁文字层级','适合：阅读、AI 对话'], 'Mindful':['深灰底 · 淡紫 / 浅蓝点缀','适合：计时、记录、日常工具']}
 for k,line in enumerate(descriptions[name]):d.text((x+23,850+k*42),line,font=small,fill='#303741')
 d.text((x+23,1000),{'Medito':'来源：Apple App Store','Ensu':'来源：Google Play','Mindful':'来源：GitHub README'}[name],font=small,fill='#60666E')
path=out/'APP主题配色对比-2026-10-27.png';canvas.save(path)
print(json.dumps({'image':str(path),'screenshots':results},ensure_ascii=False))

