"""Record the verified chart release and refresh authored-file manifests in place."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv, hashlib, json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parent.parent
evidence=root/'06_验证与后续工作'
stamp=datetime.now(timezone(timedelta(hours=8))).isoformat()
def read(name): return json.loads((root/name).read_text(encoding='utf-8'))
def write(name,value): (root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
build=digest(root/'03_当前APP/东方智慧-首页体验R4.html')
assert build=='794a9f7341028e2aec33763d61dc74fff2e3215deed4d0ee8badab64ba499f42'
reports={}
for key,name,count in [
 ('python_full','本轮全量回归结果.json',56),('cloudflare_full','公网适配全量回归结果.json',56),
 ('chart_calculation_browser','三盘实际排盘联调.json',14),('existing_maps','APP功能框版式验收.json',9),
 ('back_navigation','玄金背景与返回逐页验收.json',12),('public_charts','三盘实际排盘公网联调.json',11),
 ('public_maps','APP功能框版式公网验收.json',8),('public_back_navigation','玄金背景与返回公网逐页验收.json',11),
 ('bazi_official_cases','八字计算样例核验.json',14),('birth_time_and_ziwei','出生时间与紫微计算核验.json',14),
 ('western_independent_reference','西方星盘引擎独立对照结果.json',17)]:
 d=read('06_验证与后续工作/'+name); s=d.get('latest',d)
 assert s['pass'] and s['passed']==count and s.get('failed',0)==0,name
 assert s['at']>='2026-11-05T02:29:00',name+' is from an older build'
 if s.get('buildSha256'): assert s['buildSha256']==build,name
 if s.get('buildHashes'):
  for file,h in s['buildHashes'].items(): assert digest(root/'03_当前APP'/file)==h,name+':'+file
 reports[key]={'report':'06_验证与后续工作/'+name,'at':s['at'],'pass':True,'passed':count,'failed':0}
 if 'readOnly' in s: reports[key]['read_only']=s['readOnly']
 if 'clientSideSyntheticCalculation' in s: reports[key]['client_side_synthetic_calculation']=s['clientSideSyntheticCalculation']
public=read('06_验证与后续工作/三套实际排盘公网构建一致性.json')['latest']
assert public['pass'] and len(public['checks'])==4
app=(root/'03_当前APP/东方智慧-首页体验R4.html').read_text(encoding='utf-8')
review=(root/'03_当前APP/发给负责人-东方智慧首页R4.html').read_text(encoding='utf-8')
embedded,_=json.JSONDecoder().raw_decode(review.split('const APP=',1)[1])
assert embedded.replace('__INITIAL__','{}')==app
for file in ['life-chart-core.js','life-chart-bazi.js','life-chart-western.js','life-charts.css','navigation-back.js']:
 assert (root/'04_研发源码/app/r4'/file).read_text(encoding='utf-8') in app,file
vendors={}
for name,version,filename,license_file in [
 ('iztro','2.6.2','iztro-2.6.2.min.js','iztro-LICENSE.txt'),
 ('lunar-javascript','1.7.7','lunar-1.7.7.js','lunar-1.7.7-LICENSE.txt'),
 ('Astronomy Engine','2.1.19','astronomy-engine-2.1.19.min.js','astronomy-engine-LICENSE.txt')]:
 folder=root/'04_研发源码/app/r4/vendor'
 assert (folder/license_file).read_text(encoding='utf-8') in app,license_file
 vendors[name]={'version':version,'license':'MIT','source_sha256':digest(folder/filename),'license_sha256':digest(folder/license_file)}
publication={'project_id':'appgprj_6ae7fec0e2588191ad3ca7369fb19d9a','source_commit':'155f0ce8908681d07faf6c6b9e9ae5d7dc8732c9',
 'sites_version':11,'sites_version_id':'appgprj_6ae7fec0e2588191ad3ca7369fb19d9a~appgver_e84f8a8842f081919ac54280ac724cee',
 'sites_deployment_id':'appgdep_6aebeb4b4038819184befd94b74f1cd6','sites_status':'succeeded',
 'netlify_site_id':'1d4967d8-cb7c-4106-a092-03b716c3340c','netlify_deploy_id':'6aebeb5eeed75b3267ebce2c','netlify_status':'ready',
 'archive':'06_验证与后续工作/三套实际排盘部署.tar.gz','archive_sha256':digest(evidence/'三套实际排盘部署.tar.gz'),
 'url':'https://eastern-wisdom-demo-fuyao.netlify.app/experience?lang=zh-Hans&page=lifeResult',
 'public_build_match_report':'06_验证与后续工作/三套实际排盘公网构建一致性.json'}
backup=read('06_验证与后续工作/三套实际排盘接入前备份核验.json')
western_report=read('06_验证与后续工作/西方星盘引擎独立对照结果.json')
western_report=western_report.get('latest',western_report)
record={'checked_beijing':stamp,'pass':True,'scope':'Three actual birth-chart tools within the existing life map; same map frames, back navigation and timer.',
 'app_build_sha256':build,'engines':vendors,
 'implemented':{'ziwei':['Confirmed civil birth input','Twelve actual palaces and traditional stars','Existing palace details and explicit legacy birth-profile import'],
 'bazi':['Four pillars and traditional detail fields','Fortune start','Actual selectable decade/year/solar-term month cycles','Selectable late-Zi and fortune-start conventions'],
 'western':['Ten planetary positions and retrograde','ASC and MC','Whole-sign and equal houses','Major aspects','Interactive native SVG wheel'],
 'shared':['IANA historical timezone gap/fold handling','UTC snapshot and fixed UTC+8 Chinese calculation','Local account-scoped archive, recomputation, explicit delete, maximum 20 without silent eviction','JSON export','Four-language day/night responsive UI']},
 'backup':{k:backup[k] for k in ['archive','sha256','archive_bytes','verified_files','sites_version','netlify_deploy_id','source_commit']},
 'verification':reports,'additional_gender_ui_check':'06_验证与后续工作/八字性别表单定点核验.json',
 'western_comparison':{k:western_report[k] for k in ['comparisonCases','independentPlanetComparisons','independentAngleComparisons','maxPlanetErrorDegrees','maxAngleErrorDegrees']},
 'failure_history':['Initial chart QA exposed a missing Tibetan five-element bureau term; all five terms added.',
 'Map regression exposed the omitted western notes entry; restored with existing persistence and full original note coverage.',
 'Two test harness corrections retained full intended assertions: numeric CSS attribute selectors and reopening note details after render.',
 'Direct Sites-origin build check returned Cloudflare bot-protection 403. Historical result retained; delivered Netlify origin four-page build checks and browser/API regression passed.'],
 'publication':publication,
 'limits':['Archives are local to the current browser and account scope; guest scope is shared by guests in that browser. No cross-device cloud sync or JSON import.',
 'Tropical geocentric apparent positions; whole-sign/equal houses only. No Placidus, synastry, transits or progressions.',
 'Historical timezone resolution depends on browser Intl/IANA data; saved UTC preserves reopening reproducibility.',
 'No true-solar-time adjustment, no unknown-time default, no generated chart data or automatic personality/future/medical interpretations.',
 'Tibetan text remains pending native-language review. Browser tests do not certify physical devices or astrological interpretations.',
 'No production credentials or database migration. Independent Swiss readings are reference fixtures, not a bundled runtime.']}
write('06_验证与后续工作/三套实际排盘交付记录.json',record)
identity=read('05_后台与研发说明/Netlify站点身份.json')
identity.update(previous_deploy_id=backup['netlify_deploy_id'],deploy_id=publication['netlify_deploy_id'],checked_at=stamp,status='deployed',latest_change='生命地图三套实际排盘：紫微、四柱八字及西方出生盘，含时区处理与本人本机排盘档案')
write('05_后台与研发说明/Netlify站点身份.json',identity)
handoff=read('交接资料验证.json');handoff['three_actual_birth_charts']=record;write('交接资料验证.json',handoff)
notice='\n\n### 2026年11月5日 三套实际排盘已接入并发布\n生命地图原有“我的紫微命盘／国学智慧／星盘探索”已接真实出生资料计算。固定MIT引擎iztro2.6.2、lunar-javascript1.7.7、Astronomy Engine2.1.19；八字含起运、大运、流年、流月，西方盘含十天体、ASC/MC、整宫/等宫和相位交互圆盘。原笔记保留。出生时区按IANA处理，中文计算固定UTC+8，未知时间不猜；档案仅当前浏览器按账号保存最多20份，可重算/导出，未做云同步。三地图4/4/3功能框、上方玄金、逐级返回和自动计时保留。改前1046文件备份在07目录，规则、许可、当前实测与回退见05/06同名“三套实际排盘”说明与交付记录。本机/本地Cloudflare各56、三盘14、地图9、返回12、固定计算45；公网三盘11、地图8、返回11通过，Sites v11、Netlify6aebeb5eeed75b3267ebce2c。所有旧“尚未接入八字/星盘计算”说明仅属历史状态；不将传统计算称为AI解读，不使用未授权AGPL运行时，藏语仍待母语审校。\n'
for name in ['AGENTS.md','先读我.txt','03_当前APP/功能与使用说明-R4.txt']:
 p=root/name;s=p.read_text(encoding='utf-8')
 if '2026年11月5日 三套实际排盘已接入并发布' not in s:p.write_text(s+notice,encoding='utf-8')
task=root/'改动任务表-2026-10-22.html';s=task.read_text(encoding='utf-8')
section='<section id="actual-three-birth-charts"><h2>三套实际排盘（2026-11-05）</h2><p>已发布：我的紫微命盘真实十二宫；国学智慧四柱八字、起运、大运、流年、流月；星盘探索实际行星、ASC/MC、整宫/等宫、相位和可点击圆盘。保留本人原笔记、地图4/4/3版式、上方玄金和逐级返回。</p><p>当前三盘档案仅浏览器本机按账号存储，最多20份并可重算、导出；不自动解读或生成预测。较早章节“未接入八字/星盘”属于历史状态。</p><p>本机/本地Cloudflare完整回归各56，计算样例45，三盘14、原地图9、返回12；公网三盘11、原地图8、返回11通过，含四语日夜与窄屏。改前1046文件已校验备份。</p><p><a href="https://eastern-wisdom-demo-fuyao.netlify.app/experience?lang=zh-Hans&amp;page=lifeResult">打开三个入口</a> · <a href="05_后台与研发说明/三套实际排盘使用与计算规则说明.txt">使用、规则与回退</a> · <a href="06_验证与后续工作/三套实际排盘交付记录.json">实际交付核验</a></p></section>'
if 'id="actual-three-birth-charts"' not in s:s=s.replace('<footer>',section+'<footer>',1);task.write_text(s,encoding='utf-8')
# Omit dependency trees, transient databases, credentials, deployment archives and prior archives.
skip_dirs={'.git','__pycache__','node_modules','.venv','.wrangler','.sites-runtime','.netlify','dist','.next','.vinext','.cache','coverage'}
skip_suffix={'.zip','.7z','.rar','.tar','.gz','.tgz','.pyc','.log','.db','.pem','.key','.pfx','.p12','.tsbuildinfo'}
skip_names={'资料校验清单.csv','原始来源与文件校验.json','desktop.ini','Thumbs.db','.DS_Store'}
files=[]
for folder,dirs,names in os.walk(root):
 dirs[:]=sorted(d for d in dirs if d not in skip_dirs and not (Path(folder)/d).is_symlink())
 for name in sorted(names):
  p=Path(folder)/name
  if p.is_symlink() or name in skip_names or p.suffix.lower() in skip_suffix or any(x in name.lower() for x in ['.sqlite','.env','.dev.vars']):continue
  files.append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)})
files.sort(key=lambda x:x['path'])
manifest=read('原始来源与文件校验.json');manifest['files']=files
manifest['current_revision']={'updated_beijing':stamp,'scope':'Actual Zi Wei, Four Pillars and Western birth-chart calculation with browser-local reproducible archives','public_deployment_pending':False,'delivery_record':'06_验证与后续工作/三套实际排盘交付记录.json'}
manifest['manifest_excludes']=['资料校验清单.csv','原始来源与文件校验.json','Dependency/build/cache/runtime directories','Archives, runtime SQLite/DB, credentials and private environment files']
write('原始来源与文件校验.json',manifest)
with (root/'资料校验清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['包内相对位置','字节数','SHA-256']);w.writerows((x['path'],x['bytes'],x['sha256']) for x in files)
for item in files:
 p=root/item['path'];assert p.stat().st_size==item['bytes'] and digest(p)==item['sha256'],item['path']
print(json.dumps({'pass':True,'verified_authored_files':len(files),'build_sha256':build,'sites_version':11,'netlify_deploy_id':publication['netlify_deploy_id']},ensure_ascii=False))
