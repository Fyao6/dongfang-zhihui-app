
from pathlib import Path
import sys
p=Path(__file__).resolve().parent.parent
r=p/'04_研发源码/app/r4'
f=r/'time-bank-admin.html';s=f.read_text(encoding='utf-8')
s='\n'.join(line.replace(chr(92)*2+'n',chr(92)+'n').replace(chr(92)*2+'s',chr(92)+'s') if 'localized-chapters' in line else line for line in s.split('\n'))
f.write_text(s,encoding='utf-8')
f=r/'academy.js';s=f.read_text(encoding='utf-8').replace('t(section[1],section[0])','ewI18n.section(l,index,0,state.lang)').replace('t(section[3],section[2])','ewI18n.section(l,index,1,state.lang)');f.write_text(s,encoding='utf-8')
f=r/'homepage.js';s=f.read_text(encoding='utf-8').replace('q?.bannerLabel||','ewI18n.field(q,"bannerLabel",state.lang)||').replace('esc(q.description)','esc(ewI18n.field(q,"description",state.lang))').replace('q?.buttonLabel||','ewI18n.field(q,"buttonLabel",state.lang)||');f.write_text(s,encoding='utf-8')
f=r/'platform.js';s=f.read_text(encoding='utf-8')
s=s.replace("['zh','en','descZh','descEn','audioUrl']","['zh','en','bo','hant','descZh','descEn','descBo','descHant','audioUrl']")
s=s.replace("return {id:q.id,zh:q.zh||q.title,en:q.en||q.zh||q.title};","return {...q,id:q.id,zh:q.zh||q.title,en:q.en||q.zh||q.title};")
s=s.replace("if(config&&state.lang==='zh'){info[0]=esc(config.name);info[1]=esc(config.heroTitle);}","if(config){info[0]=esc(ewI18n.field(config,'name',state.lang));info[1]=esc(ewI18n.field(config,'heroTitle',state.lang));}")
s=s.replace("esc(x.bio||x.body||'')","esc(ewI18n.field(x,'bio',state.lang)||x.body||'')").replace("esc(x.specialty||'')","esc(ewI18n.field(x,'specialty',state.lang))")
s=s.replace("config?.heroText&&state.lang==='zh'","config?.heroText").replace("p.textContent=config.heroText","p.textContent=ewI18n.field(config,'heroText',state.lang)")
f.write_text(s,encoding='utf-8')
# Compact the full font without changing its glyph set.
sys.path.insert(0,str(p/'04_研发源码/app/cloud/.sites-runtime/font-tools'))
from fontTools.ttLib import TTFont
font=TTFont(r/'vendor/NotoSerifTibetan.ttf');font.flavor='woff2';font.save(r/'vendor/NotoSerifTibetan.woff2')
f=r/'build.py';s=f.read_text(encoding='utf-8').replace('data:font/ttf;base64,','data:font/woff2;base64,').replace('vendor/NotoSerifTibetan.ttf','vendor/NotoSerifTibetan.woff2');f.write_text(s,encoding='utf-8')
f=r/'i18n.css';s=f.read_text(encoding='utf-8').replace("format('truetype')","format('woff2')");f.write_text(s,encoding='utf-8')
f=p/'04_研发源码/app/cloud/prepare.py';s=f.read_text(encoding='utf-8').replace('data:font/ttf;base64,','data:font/woff2;base64,').replace('NotoSerifTibetan.ttf','NotoSerifTibetan.woff2');f.write_text(s,encoding='utf-8')
print('CMS localized fields connected; full Tibetan WOFF2 bytes', (r/'vendor/NotoSerifTibetan.woff2').stat().st_size)

