from pathlib import Path
import json,base64,shutil,subprocess,re,runpy
ROOT=Path(__file__).resolve().parent
runpy.run_path(str(ROOT/'build_i18n.py'))
OUT=ROOT.parents[2]/'03_当前APP'
if not OUT.is_dir():
 raise RuntimeError('现有 03_当前APP 目录不存在，停止构建以避免另建项目目录。')
art=json.loads((ROOT/'assets.json').read_text(encoding='utf-8'))
art_vars={'quiet-hour':'--art-day','still-water':'--art-night','living-light':'--art-nature','quote-landscape':'--art-quote','map-life':'--art-life','map-body':'--art-body','map-mind':'--art-mind'}
for name in ['quote-landscape','map-life','map-body','map-mind']:
 art[name]='data:image/png;base64,'+base64.b64encode((ROOT/'images'/f'{name}.png').read_bytes()).decode()
css='\n'.join((ROOT/name).read_text(encoding='utf-8') for name in ['base.css','app.css','daily.css','music.css','life.css','body.css','mind.css','academy.css','gateway.css','homepage.css','service-social.css','time-bank.css','membership.css','profile.css','platform.css','xuanliu.css','journey.css','i18n.css','academy-teachers.css','community-feed.css','frame-layout.css','life-charts.css','life-chart-workspace.css','life-chart-bazi.css','life-chart-western.css','foundation-state.css','app-density.css'])
css=css.replace('__TIBETAN_FONT__','data:font/woff2;base64,'+base64.b64encode((ROOT/'vendor/NotoSerifTibetan.woff2').read_bytes()).decode())
for name,var in art_vars.items():css=css.replace("url('__ART_"+name+"__')",'var('+var+')')
license_text=(ROOT/'vendor'/'iztro-LICENSE.txt').read_text(encoding='utf-8')
vendor='/* iztro 2.6.2\n'+license_text+'\n*/\n'+(ROOT/'vendor'/'iztro-2.6.2.min.js').read_text(encoding='utf-8')
vendor+='\n'+(ROOT/'vendor/opencc-cn2t-1.0.5.js').read_text(encoding='utf-8')
for script,license_name,global_name in [('lunar-1.7.7.js','lunar-1.7.7-LICENSE.txt','LCLunar'),('astronomy-engine-2.1.19.min.js','astronomy-engine-LICENSE.txt','LCAstronomy')]:
 vendor+='\n/* '+global_name+'\n'+(ROOT/'vendor'/license_name).read_text(encoding='utf-8')+'\n*/\n;(function(){const module={exports:{}};const exports=module.exports;\n'+(ROOT/'vendor'/script).read_text(encoding='utf-8')+'\nwindow.'+global_name+'=module.exports;})();\n'
js=vendor+'\n'+'\n'.join((ROOT/name).read_text(encoding='utf-8') for name in ['i18n-catalog.js','i18n.js','base.js','app.js','daily.js','music.js','life.js','body.js','mind.js','academy.js','academy-teachers.js','gateway.js','service-social.js','homepage.js','time-bank.js','membership.js','profile.js','platform.js','xuanliu.js','journey.js','community-feed.js','frame-kit.js','frame-home-profile.js','frame-life.js','frame-body-mind.js','map-exploration.js','map-care-paths.js','life-chart-core.js','life-chart-ziwei.js','bazi-time.js','bazi-compare.js','bazi-glossary.js','life-chart-bazi.js','life-chart-bazi-annotations.js','life-chart-bazi-layout.js','life-chart-western.js','life-birth-entry.js','life-western-cities.js','life-western-profile.js','navigation-back.js','creator-app.js','analytics-app.js','foundation-state.js','i18n-ui.js'])
bundled_node=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
node=shutil.which('node') or (str(bundled_node) if bundled_node.is_file() else None)
admin_source=(ROOT/'time-bank-admin.html').read_text(encoding='utf-8').replace('/*__CREATOR_ADMIN__*/',(ROOT/'creator-admin.js').read_text(encoding='utf-8')).replace('/*__ANALYTICS_ADMIN__*/',(ROOT/'analytics-admin.js').read_text(encoding='utf-8'))
creator_source=(ROOT/'creator-center.html').read_text(encoding='utf-8')
admin_source=admin_source.replace('url(/assets/NotoSerifTibetan.woff2)','url(data:font/woff2;base64,'+base64.b64encode((ROOT/'vendor/NotoSerifTibetan.woff2').read_bytes()).decode()+')')
if node:
 scripts=[('APP',js)]+[('CREATOR',part) for part in re.findall(r'<script>([\s\S]*?)</script>',creator_source)]+[('ADMIN',part) for part in re.findall(r'<script>([\s\S]*?)</script>',admin_source)]
 for label,script in scripts:
  check=subprocess.run([node,'--check'],input=script,encoding='utf-8',capture_output=True)
  if check.returncode:
   raise RuntimeError(label+' JavaScript syntax check failed; current viewing pages were not overwritten.\n'+check.stderr)
art_script='const ART='+json.dumps(art,ensure_ascii=False)+';const ART_VARS='+json.dumps(art_vars)+';for(const [name,data] of Object.entries(ART)){const bytes=Uint8Array.from(atob(data.split(",")[1]),c=>c.charCodeAt(0));const url=URL.createObjectURL(new Blob([bytes],{type:"image/png"}));document.documentElement.style.setProperty(ART_VARS[name],\'url("\'+url+\'")\');}'
art_script+="const COMMUNITY_PREVIEW_VIDEO=URL.createObjectURL(new Blob([Uint8Array.from(atob("+json.dumps(base64.b64encode((ROOT/'images/community-preview.mp4').read_bytes()).decode())+"),c=>c.charCodeAt(0))],{type:'video/mp4'}));"
art_script+='const COMMUNITY_PREVIEW_POSTER='+json.dumps('data:image/jpeg;base64,'+base64.b64encode((ROOT/'images/community-preview-poster.jpg').read_bytes()).decode())+';'
app='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>东方智慧学院 · 日常陪伴</title><style>'''+css+'''</style></head><body data-mode="night" data-theme="xuanliu"><div class="status"><span id="status-time">09:41</span><span aria-hidden="true">•••　5G　▰</span></div><main id="app" class="app"></main><nav id="nav" class="nav" aria-label="Main navigation"></nav><dialog id="sheet" class="sheet" aria-labelledby="sheet-title"></dialog><div id="toast" class="toast" role="status" aria-live="polite"></div><script>'''+art_script+'''</script><script>window.INITIAL=__INITIAL__;</script><script>'''+js+'''</script></body></html>'''
academy_seed=json.loads((ROOT/'backend/initial-content.json').read_text(encoding='utf-8'))
academy_seed={key:academy_seed.get(key,[]) for key in ['courses','courseCategories']}
app=app.replace('<script>window.INITIAL=__INITIAL__;</script>','<script>const ACADEMY_CONTENT_SEED='+json.dumps(academy_seed,ensure_ascii=False).replace('</script','<\\/script')+';</script><script>window.INITIAL=__INITIAL__;</script>')
(OUT/'东方智慧-首页体验R4.html').write_text(app.replace('__INITIAL__','{}'),encoding='utf-8')
(OUT/'创作者中心.html').write_text(creator_source,encoding='utf-8')
admin=admin_source.replace('__SNAPSHOT__','null')
(OUT/'计时后台-开发联调.html').write_text(admin,encoding='utf-8')
data='const APP='+json.dumps(app,ensure_ascii=False).replace('</script','<\\/script')+';'
review=(ROOT/'review.html').read_text(encoding='utf-8').replace('__CSS__',(ROOT/'review.css').read_text(encoding='utf-8')).replace('__DATA__',data).replace('__JS__',(ROOT/'review.js').read_text(encoding='utf-8'))
(OUT/'发给负责人-东方智慧首页R4.html').write_text(review,encoding='utf-8')
print('Updated current APP, review and unified admin in existing 03_当前APP.')
