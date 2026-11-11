from pathlib import Path
import json,re,base64,shutil,ast
R=Path(__file__).resolve().parent; source=R.parent/'r4'; project=R.parents[2]
public=R/'public'; public.mkdir(exist_ok=True); (public/'assets').mkdir(exist_ok=True)
generated=R/'generated';generated.mkdir(exist_ok=True)
html=(project/'03_当前APP/东方智慧-首页体验R4.html').read_text(encoding='utf-8')
html=re.sub(r'data:font/woff2;base64,[A-Za-z0-9+/=]+','/assets/NotoSerifTibetan.woff2',html)
shutil.copyfile(source/'vendor/NotoSerifTibetan.woff2',public/'assets/NotoSerifTibetan.woff2')
shutil.copyfile(source/'vendor/NotoSerifTibetan-OFL.txt',public/'assets/NotoSerifTibetan-OFL.txt')
for license_name in ['opencc-LICENSE.txt', 'opencc-data-LICENSE.txt']:
 shutil.copyfile(source/'vendor'/license_name,public/'assets'/license_name)
art=json.loads((source/'assets.json').read_text(encoding='utf-8'))
for k in ['quote-landscape','map-life','map-body','map-mind']:
 art[k]='data:image/png;base64,'+base64.b64encode((source/f'images/{k}.png').read_bytes()).decode()
for k,data in art.items():
 (public/f'assets/{k}.png').write_bytes(base64.b64decode(data.split(',')[1]));art[k]=f'/assets/{k}.png'
av={'quiet-hour':'--art-day','still-water':'--art-night','living-light':'--art-nature','quote-landscape':'--art-quote','map-life':'--art-life','map-body':'--art-body','map-mind':'--art-mind'}
asset_script='const ART='+json.dumps(art)+';const ART_VARS='+json.dumps(av)+';for(const [name,data] of Object.entries(ART)){document.documentElement.style.setProperty(ART_VARS[name],`url("${data}")`);}const COMMUNITY_PREVIEW_VIDEO="/assets/community-preview.mp4";const COMMUNITY_PREVIEW_POSTER="/assets/community-preview-poster.jpg";'
html=re.sub(r'<script>const ART=.*?</script>',lambda _: '<script>'+asset_script+'</script>',html,count=1,flags=re.S)
html=html.replace('window.INITIAL={};','window.INITIAL={backend:true};')
html=html.replace('<head>','<head><meta name="robots" content="noindex,nofollow">',1)
(generated/'experience.html').write_text(html,encoding='utf-8')
shutil.copyfile(source/'images/community-preview.mp4',public/'assets/community-preview.mp4')
shutil.copyfile(source/'images/community-preview-poster.jpg',public/'assets/community-preview-poster.jpg')
admin=(source/'time-bank-admin.html').read_text(encoding='utf-8').replace('__SNAPSHOT__','null').replace('/*__CREATOR_ADMIN__*/',(source/'creator-admin.js').read_text(encoding='utf-8')).replace('/*__ANALYTICS_ADMIN__*/',(source/'analytics-admin.js').read_text(encoding='utf-8'))
(generated/'creator.html').write_text((source/'creator-center.html').read_text(encoding='utf-8'),encoding='utf-8')
admin=admin.replace('<head>','<head><meta name="robots" content="noindex,nofollow">',1)
(generated/'admin.html').write_text(admin,encoding='utf-8')
review=(source/'review.html').read_text(encoding='utf-8').replace('__CSS__',(source/'review.css').read_text(encoding='utf-8'))
review=review.replace('__DATA__','').replace('__JS__',(source/'review.js').read_text(encoding='utf-8'))
review=re.sub(r'preview.srcdoc=APP.replace\(.*?;','preview.src="/experience?mode=night&lang="+encodeURIComponent(previewState.lang)+"&page="+encodeURIComponent(previewPage);',review,count=1)
review=review.replace('由本地服务管理','由云端服务管理').replace('2026年10月28日','公网演示')
review=review.replace('<head>','<head><meta name="robots" content="noindex,nofollow">',1)
(generated/'review.html').write_text(review,encoding='utf-8')
shutil.copyfile(source/'backend/initial-content.json',generated/'seed.json')
# Schema is derived from the existing server; only media bytes move from SQLite to R2.
tree=ast.parse((source/'backend/server.py').read_text(encoding='utf-8'))
sql=next(n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='executescript')
tables=re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)\((.*?)\);',sql,re.S)
schema=['import { sqliteTable, text, integer, real, primaryKey, uniqueIndex, index } from "drizzle-orm/sqlite-core";','import { sql } from "drizzle-orm";']
for name,body in tables:
 parts=re.split(r',(?![^()]*\))',body);fields=[];constraints=[]
 for part in parts:
  part=part.strip()
  if part.startswith('PRIMARY KEY'):
   cols=re.search(r'\((.*?)\)',part)[1].split(',');constraints.append('primaryKey({columns:['+','.join('t.'+x.strip() for x in cols)+']})');continue
  if part.startswith('UNIQUE'):
   cols=re.search(r'\((.*?)\)',part)[1].split(',');constraints.append(f'uniqueIndex("{name}_unique").on('+','.join('t.'+x.strip() for x in cols)+')');continue
  col,typ,*_=part.split();func={'TEXT':'text','INTEGER':'integer','REAL':'real','BLOB':'text'}[typ]
  if name=='media' and col=='data':col='object_key'
  v=f'{func}("{col}")'
  if 'PRIMARY KEY' in part:v+='.primaryKey()'
  if 'NOT NULL' in part:v+='.notNull()'
  if re.search(r'\bUNIQUE\b',part):v+='.unique()'
  m=re.search(r'DEFAULT\s+(\S+)',part)
  if m:v+=f'.default({m[1]})'
  m=re.search(r'REFERENCES (\w+)\((\w+)\)',part)
  if m:v+=f'.references(() => {m[1]}.{m[2]}'+(', {onDelete:"cascade"}' if 'ON DELETE CASCADE' in part else '')+')'
  fields.append(f'{col}: {v}')
 if name=='timer_runs':constraints.append('uniqueIndex("one_open_timer").on(t.owner).where(sql`${t.end_ms} IS NULL`)')
 if name=='users':constraints.append('uniqueIndex("one_bootstrap_admin").on(t.username)')
 schema.append(f'export const {name}=sqliteTable("{name}",{{'+','.join(fields)+'}'+(',t=>['+','.join(constraints)+']' if constraints else '')+');')
schema.append('export const rate_limits=sqliteTable("rate_limits",{key:text("key").primaryKey(),count:integer("count").notNull(),expires:integer("expires").notNull()});')
(R/'db/schema.ts').write_text('\n'.join(schema),encoding='utf-8')
hosting=json.loads((R/'.openai/hosting.json').read_text());hosting.update(d1='DB',r2='BUCKET');(R/'.openai/hosting.json').write_text(json.dumps(hosting,indent=2),encoding='utf-8')
print('Prepared cloud assets and schema; app HTML bytes',len(html.encode()))
