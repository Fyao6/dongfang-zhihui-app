import urllib.request,urllib.parse,json,io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageDraw,ImageFont
out=next(p for p in Path.cwd().iterdir() if p.is_dir())/'02_需求与设计参考'
rs=json.loads((out/'科技禅修GitHub案例调研-2026-10-27.json').read_text(encoding='utf-8'))
picks={'Stonks007/uposath':['src/screenshots/home.jpeg','src/screenshots/sati.jpeg'],'ronynn/kisoku':['fastlane/metadata/android/en-US/images/phoneScreenshots/1.jpg'],'natebru/PauseState':['demo/pausestate-demo.gif'],'Kirankumarvel/celebratebreath':['screenshot.png'],'jacobomolinaferrer/WHOOP':['screenshots/today.png','screenshots/breathing.png'],'cggmx/garmin-health-dashboard':['docs/screenshots/01-dashboard.jpeg','docs/screenshots/04-sleep-detail.jpeg'],'askb/ha-garmin-fitness-coach-app':['docs/screenshots/hrv-desktop.png']}
items=[]
for r in rs:
 for i,p in enumerate(picks.get(r['repo'],[])):items.append((r['repo'],i,urllib.parse.urljoin(r['base'],p)))
def dl(t):
 repo,i,u=t
 try:
  b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=35).read();im=Image.open(io.BytesIO(b))
  if getattr(im,'n_frames',1)>1: im.seek(min(30,im.n_frames-1))
  im=im.convert('RGB');f=out/('科技禅修参考-'+repo.split('/')[-1]+'-'+str(i+1)+'.png');im.save(f);return dict(repo=repo,url=u,file=str(f),size=im.size)
 except Exception as e:return dict(repo=repo,url=u,error=str(e))
with ThreadPoolExecutor(max_workers=8) as p:imgs=list(p.map(dl,items))
(out/'科技禅修截图来源-2026-10-27.json').write_text(json.dumps(imgs,ensure_ascii=False,indent=2),encoding='utf-8')
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',24)
cv=Image.new('RGB',(2000,1800),'#ddd');d=ImageDraw.Draw(cv)
for j,r in enumerate(imgs):
 x=(j%4)*500;y=(j//4)*600;d.text((x+12,y+10),r['repo'].split('/')[-1],font=font,fill='black')
 if 'file'in r:
  im=Image.open(r['file']);im.thumbnail((475,545));cv.paste(im,(x+10,y+45))
cv.save(out/'科技禅修候选校对.png')
print(json.dumps([{k:v for k,v in r.items() if k!='file'} for r in imgs],ensure_ascii=True))
