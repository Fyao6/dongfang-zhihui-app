"""Translate only bundled public UI copy; never read/send accounts, records or user text.
Drafts require terminology review in i18n-bo.json. Stop on quota/auth failures.
"""
from pathlib import Path
import urllib.request,urllib.parse,json,re,time,sys,hashlib
sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
p=Path(__file__).resolve().parent.parent;r=p/'04_研发源码/app/r4'
rows=json.loads((p/'06_验证与后续工作/四语文案清单.json').read_text(encoding='utf-8'))
live=json.loads((p/'06_验证与后续工作/四语实际页面文案.json').read_text(encoding='utf-8'))['pairs']
by={x['zh']:x for x in rows}
for x in live: by.setdefault(x['zh'],x)
priority={x['zh'] for x in live}
rows=sorted(by.values(),key=lambda x:(x['zh'] not in priority, x.get('id',9999)))
draft_file=r/'i18n-bo-draft.json'
draft=json.loads(draft_file.read_text(encoding='utf-8')) if draft_file.exists() else {}
manual=json.loads((r/'i18n-bo.json').read_text(encoding='utf-8'))
rows=[x for x in rows if x['zh'] not in draft and x['zh'] not in manual and x['zh'].strip()]
def request(text):
 url='https://monlam.ai/api/translation/stream?'+urllib.parse.urlencode({'target':'bo','model':'MONLAM-MELONG','text':text})
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/event-stream','Referer':'https://monlam.ai/model/mt'})
 with urllib.request.urlopen(req,timeout=100) as response:
  for raw in response:
   if raw.startswith(b'data:'):
    data=json.loads(raw[5:])
    if 'error' in data: raise RuntimeError(str(data['error']))
    if data.get('generated_text'): return data['generated_text']
 raise RuntimeError('Translation returned no completed text')
def source(row):
 # English definitions already authored in this app; use Chinese when inventory picked an identifier.
 en=row.get('en','')
 return en if re.search(r'[A-Za-z]{2}',en) and not re.fullmatch(r'[a-z0-9_-]+',en) else row['zh']
limit=int(sys.argv[1]) if len(sys.argv)>1 else 0
batches=[];batch=[];size=0
for row in rows:
 s=source(row)
 if batch and (size+len(s)>1100 or len(batch)>=14):batches.append(batch);batch=[];size=0
 batch.append(row);size+=len(s)+8
if batch:batches.append(batch)
failures=[]
for n,batch in enumerate(batches[:limit or None]):
 text='\n'.join(f'{i+1}. '+source(row).replace('\n',' ') for i,row in enumerate(batch))
 try:
  result=request(text)
  # The service may use Tibetan digits in a numbered list.
  normal=result.translate(str.maketrans('༠༡༢༣༤༥༦༧༨༩','0123456789'))
  chunks=re.split(r'(?:^|\s)\s*(\d{1,2})[.．、)།་:：]\s*',normal)
  translated={int(chunks[i]):chunks[i+1].strip() for i in range(1,len(chunks)-1,2)}
  if len(batch)==1 and not translated:translated={1:normal.strip()}
  if set(translated)!=set(range(1,len(batch)+1)):raise ValueError('Numbered segments changed: '+repr(normal[:180]))
  for i,row in enumerate(batch,1):
   bo=translated[i]
   if not re.search('[\u0f40-\u0fbc]',bo) and re.search('[\u3400-\u9fff]',row['zh']) and row['zh'] not in ['微信支付','支付宝']:raise ValueError('No Tibetan text')
   if set(re.findall(r'\{\d+\}',row['zh'])) != set(re.findall(r'\{\d+\}',bo)):raise ValueError('Placeholder mismatch')
  for i,row in enumerate(batch,1):draft[row['zh']]=translated[i]
  draft_file.write_text(json.dumps(draft,ensure_ascii=False,indent=2),encoding='utf-8')
  print(f'Batch {n+1}/{len(batches)}: saved {len(batch)}, total {len(draft)}',flush=True)
 except urllib.error.HTTPError as exc:
  print(f'Stopped: HTTP {exc.code}',flush=True);break
 except Exception as exc:
  failures.append({'keys':[x['zh'] for x in batch],'error':str(exc)})
  print(f'Batch {n+1}: needs manual review ({str(exc)[:100]})',flush=True)
 (p/'06_验证与后续工作/藏文翻译待复核.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2),encoding='utf-8')
 time.sleep(2)
print('Draft collection finished. No native-speaker certification.',flush=True)

