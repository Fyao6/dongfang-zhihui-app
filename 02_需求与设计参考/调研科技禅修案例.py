import urllib.request,json,base64,re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
repos=['Stonks007/uposath','ronynn/kisoku','martinhv/sough','natebru/PauseState','Kirankumarvel/celebratebreath','heelago/Sleepscape','jacobomolinaferrer/WHOOP','cggmx/garmin-health-dashboard','askb/ha-garmin-fitness-coach-app','TamesB/breathe','udirobert/brume']
def one(repo):
 try:
  req=urllib.request.Request('https://api.github.com/repos/'+repo+'/readme',headers={'User-Agent':'Codex-reference-research'})
  j=json.load(urllib.request.urlopen(req,timeout=25));txt=base64.b64decode(j['content']).decode();imgs=re.findall(r'!\[[^\]]*\]\(([^\s)]+)',txt)+re.findall(r'<img[^>]+src=[\"\x27]([^\"\x27]+)',txt)
  return dict(repo=repo,base=j['download_url'],images=imgs,readme=txt)
 except Exception as e:return dict(repo=repo,error=str(e))
with ThreadPoolExecutor(max_workers=8) as p:rs=list(p.map(one,repos))
out=next(p for p in Path.cwd().iterdir() if p.is_dir())/'02_需求与设计参考'
(out/'科技禅修GitHub案例调研-2026-10-27.json').write_text(json.dumps(rs,ensure_ascii=False,indent=2),encoding='utf-8')
for r in rs: print(json.dumps({k:v for k,v in r.items() if k!='readme'},ensure_ascii=False))
