"""Package the current authored files in the existing project root and verify every byte."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.parse import quote,unquote,urlsplit
from lxml import html,etree
import ast,base64,csv,hashlib,io,json,os,re,sys,struct,zlib
import html as H
import zipfile
ROOT=Path(__file__).resolve().parent.parent
WEB=ROOT/'03_当前APP';R4=ROOT/'04_研发源码/app/r4';CLOUD=ROOT/'04_研发源码/app/cloud'
REPORT='06_验证与后续工作/最新打包校验结果.json'
PREFLIGHT='06_验证与后续工作/本次打包内容核验.json'
DELIVERY=next(name for name in ['06_验证与后续工作/八字表留白与字号交付记录.json','06_验证与后续工作/真实星盘档案交付记录.json','06_验证与后续工作/完整星盘交付记录.json','06_验证与后续工作/准了参考交付记录.json','06_验证与后续工作/改动文档交付记录.json','06_验证与后续工作/原创命盘表达交付记录.json','06_验证与后续工作/基础框架交付记录.json','06_验证与后续工作/基础框架本地验收及发布待续记录.json','06_验证与后续工作/基础框架阶段打包交付记录.json'] if (ROOT/name).exists())
UI_SOURCES=['life-chart-core.js','life-chart-ziwei.js','life-chart-workspace.css','life-chart-bazi.js','life-chart-bazi-layout.js','life-chart-bazi-annotations.js','life-chart-bazi.css','life-chart-western.js','life-chart-western.css','life-birth-entry.js','app-density.css','academy.js','academy-teachers.js','frame-home-profile.js','homepage.js','frame-layout.css','homepage.css','xuanliu.js']
UI_REPORTS={'birth':('出生资料地域移除核验-本机.json',8),'charts':('三盘实际排盘联调.json',14),'expression':('原创命盘交互核验.json',15),'layout':('页面长度与日间命盘优化核验.json',16),'bazi_reference':('八字参考排版核验.json',12)}
SELF={'资料校验清单.csv','原始来源与文件校验.json'}
SKIP_DIRS={'.git','__pycache__','node_modules','.venv','.wrangler','.sites-runtime','.netlify','dist','.next','.vinext','.cache','coverage'}
SKIP_SUFFIX={'.zip','.7z','.rar','.tar','.gz','.tgz','.pyc','.log','.db','.pem','.key','.pfx','.p12','.tsbuildinfo'}
SKIP_NAMES={'.ds_store','thumbs.db','desktop.ini','最新打包校验结果.json','.netrc','.pypirc','credentials.json','id_rsa','id_ed25519'}
def need(ok,msg):
 if not ok:raise AssertionError(msg)
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def write(p,d):(ROOT/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def latest(p):
 d=read('06_验证与后续工作/'+p);return d.get('latest',d)
def unsafe(p):return p.is_symlink() or getattr(p,'is_junction',lambda:False)() or not p.resolve().is_relative_to(ROOT.resolve())
def allowed(p):
 n=p.name.lower();return not unsafe(p) and p.suffix.lower() not in SKIP_SUFFIX and n not in SKIP_NAMES and not any(x in n for x in ['.sqlite','.db-','.db.','.env','.dev.vars'])
def collect_files():
 out={}
 for folder,dirs,names in os.walk(ROOT):
  dirs[:]=sorted(d for d in dirs if d.lower() not in SKIP_DIRS and not unsafe(Path(folder)/d))
  for n in sorted(names):
   p=Path(folder)/n
   if allowed(p):out[p.relative_to(ROOT).as_posix()]=p
 return out

def credential_scan_bytes(data):
 # PNG IDAT is compressed pixel data, not plaintext; inspect its textual metadata instead.
 if not data.startswith(b'\x89PNG\r\n\x1a\n'):return data
 output=[];pos=8
 while pos+12<=len(data):
  size=struct.unpack('>I',data[pos:pos+4])[0];kind=data[pos+4:pos+8];part=data[pos+8:pos+8+size];pos+=size+12
  if kind in [b'tEXt',b'eXIf']:output.append(part)
  elif kind==b'zTXt':
   keyword,tail=part.split(b'\0',1);output.extend([keyword,zlib.decompress(tail[1:])])
  elif kind==b'iTXt':
   keyword,tail=part.split(b'\0',1);flag,method=tail[0],tail[1];language,translated,text=tail[2:].split(b'\0',2);output.extend([keyword,language,translated,zlib.decompress(text) if flag else text])
 return b'\n'.join(output)

def historical_foundation(delivery,checks,verified_reports):
 # Historical recovery evidence remains bound to its original immutable baseline,
 # not to the newly rendered APP. Only its unchanged backend/API sources apply now.
 reference=delivery['foundation_baseline'];baseline_path='06_验证与后续工作/基础框架本地验收及发布待续记录.json'
 need(reference['report']==baseline_path and digest(ROOT/baseline_path)==reference['sha256'],'Foundation baseline bytes changed')
 baseline=read(baseline_path)
 need(baseline.get('pass') is True and baseline['module_ledger']==delivery['module_ledger'] and baseline['complete_modules']==delivery['complete_modules'],'Foundation baseline/module provenance differs')
 for name in ['foundation','restore']:
  ref=baseline['verification'][name];path=(ROOT/ref['report']).resolve()
  need(path.is_relative_to((ROOT/'06_验证与后续工作').resolve()) and ref.get('sha256') and digest(path)==ref['sha256'],'Historical F05 report bytes changed: '+name)
  document=read(ref['report']);reports=[document.get('latest',document),*document.get('runs',[])]
  report=next((r for r in reports if r.get('at')==ref['at'] and r.get('module')==ref['module']),None)
  need(report is not None and report.get('pass') is True and report.get('failed')==0 and report.get('passed',0)>=4,'Historical F05 run missing or failed: '+name)
  report_app=report.get('buildSha256') or report.get('buildHashes',{}).get('东方智慧-首页体验R4.html')
  need(report_app==baseline['app_build_sha256'],'Historical F05 build differs from baseline: '+name)
  sources=report.get('sourceHashes',{});need(sources and all(baseline['source_sha256'].get(rel)==sha for rel,sha in sources.items()),'Historical F05 sources differ from baseline: '+name)
  checks[name]={'report':ref['report'],'at':report['at'],'module':report['module'],'passed':report['passed'],'sha256':digest(path),'historical_baseline':True,'current_ui_build_verified':False}
  verified_reports[name]=report
 backend_sources=['04_研发源码/app/r4/backend/'+n for n in ['server.py','creator.py','analytics.py']]+['04_研发源码/app/cloud/lib/'+n for n in ['eastern-api.ts','creator-api.ts','analytics-api.ts']]
 for rel in backend_sources:need(rel in baseline['source_sha256'] and digest(ROOT/rel)==baseline['source_sha256'][rel],'Backend/API differs from historical restore baseline: '+rel)
 f05=next(m for m in baseline['module_ledger']['modules'] if m['id']=='F05')
 worker='worker/index.ts';need(worker in f05['cloudBuildHashes'] and digest(CLOUD/worker)==f05['cloudBuildHashes'][worker],'Cloud API entry differs from historical restore baseline')
 checks['foundation_baseline']={'report':baseline_path,'sha256':reference['sha256'],'app_build_sha256':baseline['app_build_sha256'],'scope':'Historical F05 contracts and isolated restore only; unchanged backend/API verified, not current UI build acceptance.'}


DOCUMENT_MODULE='改动文档M5-展开控件统一'
DOCUMENT_LEDGER='06_验证与后续工作/改动文档实施记录.json'
DOCUMENT_NAMES={'M1':'改动文档M1-首页布局与三入口','M2':'改动文档M2-三盘独立与真实星盘','M3':'改动文档M3-紫微日间白底与可读性','M4':'改动文档M4-八字真实数据与三页对齐','M5':DOCUMENT_MODULE}

def report_app(run):return run.get('buildSha256') or run.get('appBuildSha256') or run.get('buildHashes',{}).get('东方智慧-首页体验R4.html')

def build_inputs():
 tree=ast.parse((R4/'build.py').read_text(encoding='utf-8-sig'));names=set()
 for node in ast.walk(tree):
  if isinstance(node,ast.comprehension) and isinstance(node.iter,(ast.List,ast.Tuple)):
   values=node.iter.elts
   if values and all(isinstance(x,ast.Constant) and isinstance(x.value,str) and Path(x.value).suffix in {'.js','.css'} for x in values):names.update(x.value for x in values)
 need({'base.js','base.css','life-chart-bazi-layout.js','life-chart-bazi-annotations.js'}<=names,'APP build input inventory is incomplete')
 need(all(Path(n).name==n and (R4/n).is_file() for n in names),'APP build input outside actual top-level source')
 return sorted(names)

def embedded_text(name):
 text=(R4/name).read_text(encoding='utf-8')
 if name.endswith('.css'):
  import base64
  text=text.replace('__TIBETAN_FONT__','data:font/woff2;base64,'+base64.b64encode((R4/'vendor/NotoSerifTibetan.woff2').read_bytes()).decode())
  tree=ast.parse((R4/'build.py').read_text(encoding='utf-8-sig'))
  art=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='art_vars' for t in n.targets))
  for label,var in art.items():text=text.replace("url('__ART_"+label+"__')",'var('+var+')')
 return text

def document_modules(delivery,checks,current_module=True):
 ref=delivery.get('document_module_ledger',{});need(ref.get('report')==DOCUMENT_LEDGER and digest(ROOT/DOCUMENT_LEDGER)==ref.get('sha256'),'Document module ledger bytes differ')
 ledger=read(DOCUMENT_LEDGER);need(ref.get('modules')==ledger.get('modules'),'Document module snapshot differs')
 need(delivery.get('complete_document_modules')==list(DOCUMENT_NAMES),'Document module completion list differs')
 verified={}
 for module_id,module_name in DOCUMENT_NAMES.items():
  row=ledger['modules'].get(module_id,{});expected=row.get('app_sha256');need(row.get('status')=='已通过' and re.fullmatch('[a-f0-9]{64}',str(expected)),'Document module not accepted: '+module_id)
  refs=row.get('reports',[]);need(refs,'Document module reports absent: '+module_id);items=[];full_targets=set();smokes=0
  for reference in refs:
   rel=reference['path'];path=(ROOT/rel).resolve();need(path.is_relative_to((ROOT/'06_验证与后续工作').resolve()) and not unsafe(path) and digest(path)==reference.get('sha256'),'Frozen document report changed: '+rel)
   data=read(rel);runs=[data.get('latest',data),*data.get('runs',[])];count=reference.get('count');need(isinstance(count,int) and not isinstance(count,bool) and count>0,'Invalid document report count: '+rel)
   run=next((r for r in runs if r.get('pass') is True and r.get('failed')==0 and r.get('passed')==count and r.get('module')==module_name and report_app(r)==expected),None)
   need(run is not None,'Frozen document report is not bound to its own module APP: '+rel)
   if '全量' in Path(rel).name:
    need(count>=60,'Document full regression incomplete: '+rel);full_targets.add('cloudflare' if 'cloud' in Path(rel).name.lower() else 'local')
   if '冒烟' in Path(rel).name:smokes+=1
   if module_id=='M5' and current_module:
    need(expected==delivery['app_build_sha256'],'Final document module APP differs')
    for source,value in run.get('sourceHashes',{}).items():need(digest(ROOT/source)==value,'Final M5 source differs: '+source)
    for folder,key in [(WEB,'buildHashes'),(CLOUD,'cloudBuildHashes')]:
     for source,value in run.get(key,{}).items():need((folder/source).resolve().is_relative_to(folder.resolve()) and digest(folder/source)==value,'Final M5 build differs: '+source)
   items.append({'report':rel,'sha256':reference['sha256'],'at':run.get('at'),'module':module_name,'passed':count,'app_build_sha256':expected,'historical_stage':module_id!='M5' or not current_module})
  need(full_targets=={'local','cloudflare'} and smokes>=1,'Document module needs both full regressions and actual smoke: '+module_id);verified[module_id]=items
 checks['document_modules']={'report':DOCUMENT_LEDGER,'sha256':ref['sha256'],'modules':verified,'scope':('Historical stages bind to their own frozen APP; only M5 sources/build are compared with current files.' if current_module else 'All M1–M5 stages are immutable historical evidence bound to their own APP; no current UI acceptance claimed.')}
 return verified

REFERENCE_MODULE='准了参考C2-八字比例重做'
REFERENCE_LEDGER='06_验证与后续工作/准了参考实施记录.json'
REFERENCE_NAMES={'C1':'准了参考C1-星盘盘面重做','C2':REFERENCE_MODULE}
REFERENCE_SMOKES={'reference_western_smoke':'06_验证与后续工作/准了参考星盘冒烟.json','reference_bazi_smoke':'06_验证与后续工作/准了参考八字冒烟.json'}

def reference_modules(delivery,checks,current_module=True):
 previous=delivery.get('previous_document_revision',{});path='06_验证与后续工作/改动文档交付记录.json'
 need(previous.get('report')==path and digest(ROOT/path)==previous.get('sha256'),'Previous document receipt changed')
 old=read(path);need(old.get('pass') is True and old.get('document_revision') is True and previous.get('app_build_sha256')==old.get('app_build_sha256'),'Previous document identity differs')
 for field in ['foundation_baseline','module_ledger','complete_modules','document_module_ledger','complete_document_modules']:
  need(delivery.get(field)==old.get(field),'Historical baseline snapshot differs: '+field)
 document_modules(old,checks,current_module=False)
 ref=delivery.get('reference_module_ledger',{});need(ref.get('report')==REFERENCE_LEDGER and digest(ROOT/REFERENCE_LEDGER)==ref.get('sha256'),'Reference ledger changed')
 ledger=read(REFERENCE_LEDGER);need(ref.get('modules')==ledger.get('modules') and delivery.get('complete_reference_modules')==list(REFERENCE_NAMES),'Reference module snapshot differs')
 need(ledger.get('previous_document_revision',{}).get('sha256')==previous['sha256'],'Reference ledger prior receipt differs')
 baseline=ledger.get('baseline',{});need(digest(ROOT/baseline['report'])==baseline.get('sha256'),'Reference pre-change identity changed')
 for reference in ledger.get('references',[]):need(digest(ROOT/reference['path'])==reference.get('sha256'),'User reference image changed')
 verified={}
 for module_id,module_name in REFERENCE_NAMES.items():
  row=ledger['modules'].get(module_id,{});expected=row.get('app_sha256');need(row.get('status')=='已通过' and re.fullmatch('[a-f0-9]{64}',str(expected)),'Reference module not accepted: '+module_id)
  targets=set();smokes=0;items=[]
  for reference in row.get('reports',[]):
   rel=reference['path'];path=(ROOT/rel).resolve();need(path.is_relative_to((ROOT/'06_验证与后续工作').resolve()) and not unsafe(path) and digest(path)==reference.get('sha256'),'Frozen reference report changed: '+rel)
   data=read(rel);runs=[data.get('latest',data),*data.get('runs',[])];count=reference.get('count');need(isinstance(count,int) and not isinstance(count,bool) and count>0,'Invalid reference count')
   run=next((r for r in runs if r.get('pass') is True and r.get('failed')==0 and r.get('passed')==count and r.get('module')==module_name and report_app(r)==expected),None)
   need(run is not None,'Reference report not bound to its stage APP: '+rel)
   if '全量' in Path(rel).name:
    need(count>=60,'Reference full incomplete');targets.add('cloudflare' if run.get('cloudWorker') or 'cloud' in Path(rel).name.lower() else 'local')
   if '冒烟' in Path(rel).name:need(run.get('productionWrites') is False,'Reference smoke not isolated');smokes+=1
   if module_id=='C2' and current_module:
    need(expected==delivery['app_build_sha256'],'Final C2 APP differs')
    for source,value in run.get('sourceHashes',{}).items():need(digest(ROOT/source)==value,'Final C2 source differs: '+source)
    for folder,key in [(WEB,'buildHashes'),(CLOUD,'cloudBuildHashes')]:
     for source,value in run.get(key,{}).items():need((folder/source).resolve().is_relative_to(folder.resolve()) and digest(folder/source)==value,'Final C2 build differs: '+source)
   items.append({'report':rel,'sha256':reference['sha256'],'at':run['at'],'module':module_name,'passed':count,'app_build_sha256':expected,'historical_stage':module_id=='C1' or not current_module})
  need(targets=={'local','cloudflare'} and smokes,'Reference module needs dual full and smoke: '+module_id);verified[module_id]=items
 checks['reference_modules']={'report':REFERENCE_LEDGER,'sha256':ref['sha256'],'modules':verified,'scope':('C1 binds its own frozen stage APP; C2 and both final smoke reruns bind current files.' if current_module else 'All C1/C2 evidence binds historical frozen stage APPs; no current Western UI acceptance claimed.')}
 return verified

STRUCTURE_MODULE='完整星盘S1-盘面结构与连线'
STRUCTURE_LEDGER='06_验证与后续工作/完整星盘实施记录.json'
STRUCTURE_SMOKES={'structure_smoke':('06_验证与后续工作/完整星盘结构冒烟.json',8),'reference_western_smoke':('06_验证与后续工作/准了参考星盘冒烟.json',7)}

def structure_module(delivery,checks,current_module=True):
 previous=delivery.get('previous_reference_revision',{});rel='06_验证与后续工作/准了参考交付记录.json'
 need(previous.get('report')==rel and digest(ROOT/rel)==previous.get('sha256'),'Previous C1/C2 receipt changed')
 old=read(rel);need(old.get('pass') is True and old.get('reference_revision') is True and previous.get('app_build_sha256')==old.get('app_build_sha256'),'Previous C1/C2 identity differs')
 for field in ['foundation_baseline','module_ledger','complete_modules','document_module_ledger','complete_document_modules','previous_document_revision','reference_module_ledger','complete_reference_modules']:
  need(delivery.get(field)==old.get(field),'Historical C1/C2 baseline differs: '+field)
 reference_modules(old,checks,current_module=False)
 ref=delivery.get('structure_module_ledger',{});need(ref.get('report')==STRUCTURE_LEDGER and digest(ROOT/STRUCTURE_LEDGER)==ref.get('sha256'),'S1 ledger changed')
 ledger=read(STRUCTURE_LEDGER);need(ref.get('modules')==ledger.get('modules') and delivery.get('complete_structure_modules')==['S1'],'S1 ledger snapshot differs')
 need(ledger.get('previous_reference_revision',{}).get('sha256')==previous['sha256'],'S1 previous receipt differs')
 baseline=ledger.get('baseline',{});need(digest(ROOT/baseline['report'])==baseline.get('sha256') and baseline.get('app_sha256')==old['app_build_sha256'],'S1 pre-change identity differs')
 for reference in ledger.get('references',[]):need(digest(ROOT/reference['path'])==reference.get('sha256'),'S1 user reference changed')
 row=ledger['modules'].get('S1',{});expected=row.get('app_sha256');need(row.get('status')=='已通过' and expected==delivery['app_build_sha256'],'S1 not accepted for final APP')
 targets=set();smokes=0;items=[]
 for reference in row.get('reports',[]):
  rel=reference['path'];path=(ROOT/rel).resolve();need(path.is_relative_to((ROOT/'06_验证与后续工作').resolve()) and not unsafe(path) and digest(path)==reference.get('sha256'),'Frozen S1 report changed: '+rel)
  data=read(rel);runs=[data.get('latest',data),*data.get('runs',[])];count=reference.get('count');need(isinstance(count,int) and not isinstance(count,bool) and count>0,'Invalid S1 report count')
  run=next((r for r in runs if r.get('pass') is True and r.get('failed')==0 and r.get('passed')==count and r.get('module')==STRUCTURE_MODULE and report_app(r)==expected),None)
  need(run is not None,'S1 report does not bind final APP: '+rel)
  if '全量' in Path(rel).name:
   need(count>=60,'S1 full incomplete');targets.add('cloudflare' if run.get('cloudWorker') or 'cloud' in Path(rel).name.lower() else 'local')
  if '冒烟' in Path(rel).name:need(run.get('productionWrites') is False,'S1 smoke not isolated');smokes+=1
  if current_module:
   for source,value in run.get('sourceHashes',{}).items():need(digest(ROOT/source)==value,'Final S1 source differs: '+source)
   for folder,key in [(WEB,'buildHashes'),(CLOUD,'cloudBuildHashes')]:
    for source,value in run.get(key,{}).items():need((folder/source).resolve().is_relative_to(folder.resolve()) and digest(folder/source)==value,'Final S1 build differs: '+source)
  items.append({'report':rel,'sha256':reference['sha256'],'at':run['at'],'module':STRUCTURE_MODULE,'passed':count,'app_build_sha256':expected,'historical_stage':not current_module})
 need(targets=={'local','cloudflare'} and smokes,'S1 needs dual full and isolated smoke')
 checks['structure_module']={'report':STRUCTURE_LEDGER,'sha256':ref['sha256'],'reports':items,'scope':('Only S1 binds current source/build; all previous chart/UI modules remain frozen historical evidence.' if current_module else 'S1 and previous stages bind their immutable historical APPs; no current W1 acceptance claimed.')}
 return items

REAL_WESTERN_MODULE='真实星盘W1-出生城市与完整档案'
REAL_WESTERN_LEDGER='06_验证与后续工作/真实星盘档案实施记录.json'
REAL_WESTERN_SMOKES={'real_western_smoke':('06_验证与后续工作/真实星盘档案冒烟.json',10),'structure_smoke':('06_验证与后续工作/完整星盘结构冒烟.json',8),'reference_western_smoke':('06_验证与后续工作/准了参考星盘冒烟.json',7)}

def city_snapshot(delivery,checks):
 ref=delivery.get('city_data_snapshot',{});rel='02_需求与设计参考/出生城市离线索引来源-20261111.json'
 need(ref.get('report')==rel and digest(ROOT/rel)==ref.get('sha256'),'City source snapshot changed')
 review=read(rel)
 time_ref=delivery.get('time_basis_review',{});time_path='02_需求与设计参考/出生城市时间口径核对-20261111.json'
 need(time_ref.get('report')==time_path and digest(ROOT/time_path)==time_ref.get('sha256') and delivery['source_sha256'].get(time_path)==time_ref['sha256'],'City birth-clock source evidence missing/changed')
 time_review=read(time_path);need(time_review.get('source')=='https://data.iana.org/time-zones/tzdb/asia' and {617,618,619}<=set(time_review.get('supporting_lines',[])),'IANA city clock-basis primary source differs')
 checks['birth_city_time_basis']={'report':time_path,'sha256':time_ref['sha256'],'source':time_review['source'],'scope':'Catalog Asia/Urumqi requires an explicit record-clock choice; GeoNames raw zone unchanged; other city zones automatic.'}
 for key,field in [('snapshot','snapshot'),('coverage','coverage'),('runtime','output'),('notice','notice'),('source_files','official_sources')]:need(ref.get(key)==review.get(field),'City source metadata differs: '+key)
 need(ref.get('raw_archives_in_payload') is False,'Raw city ZIP must stay excluded from payload')
 runtime=review['output'];need(runtime.get('path')=='04_研发源码/app/r4/life-western-cities.js' and digest(ROOT/runtime['path'])==runtime['sha256'] and (ROOT/runtime['path']).stat().st_size==runtime['bytes'],'City runtime differs from pinned source snapshot')
 notice=review['notice'];need(notice.get('path')=='04_研发源码/app/r4/vendor/geonames-LICENSE-NOTICE.txt' and digest(ROOT/notice['path'])==notice['sha256'],'GeoNames attribution changed')
 for path,source in review['official_sources'].items():
  need(path.startswith('04_研发源码/app/r4/vendor/geonames-') and (ROOT/path).resolve().is_relative_to((R4/'vendor').resolve()),'Unexpected city raw source path')
  if Path(path).suffix.lower()=='.zip':
   if (ROOT/path).exists():need(digest(ROOT/path)==source['sha256'],'Local city raw ZIP changed')
  else:need(digest(ROOT/path)==source['sha256'],'Fixed city source changed: '+path)
 need({'life-western-profile.js','life-western-cities.js'}<=set(build_inputs()),'W1 profile/data not included in actual APP build inputs')
 for path in [runtime['path'],notice['path'],'04_研发源码/app/r4/life-western-profile.js',rel]:need(delivery['source_sha256'].get(path)==digest(ROOT/path),'Required W1 city source identity absent: '+path)
 checks['city_data_snapshot']={'report':rel,'sha256':ref['sha256'],'snapshot':review['snapshot'],'coverage':review['coverage'],'raw_archives_in_payload':False,'license':'GeoNames CC BY 4.0; attribution and changes notice retained.'}
 return review

def real_western_module(delivery,checks,current_module=True):
 previous=delivery.get('previous_structure_revision',{});rel='06_验证与后续工作/完整星盘交付记录.json'
 need(previous.get('report')==rel and digest(ROOT/rel)==previous.get('sha256'),'Previous S1 receipt changed')
 old=read(rel);need(old.get('pass') is True and old.get('structure_revision') is True and previous.get('app_build_sha256')==old.get('app_build_sha256'),'Previous S1 receipt identity differs')
 for field in ['foundation_baseline','module_ledger','complete_modules','document_module_ledger','complete_document_modules','previous_document_revision','reference_module_ledger','complete_reference_modules','previous_reference_revision','structure_module_ledger','complete_structure_modules']:
  need(delivery.get(field)==old.get(field),'Historical S1 baseline differs: '+field)
 structure_module(old,checks,current_module=False)
 ref=delivery.get('real_western_module_ledger',{});need(ref.get('report')==REAL_WESTERN_LEDGER and digest(ROOT/REAL_WESTERN_LEDGER)==ref.get('sha256'),'W1 ledger changed')
 ledger=read(REAL_WESTERN_LEDGER);need(ref.get('modules')==ledger.get('modules') and delivery.get('complete_real_western_modules')==['W1'],'W1 ledger snapshot differs')
 need(ledger.get('previous_structure_revision',{}).get('sha256')==previous['sha256'],'W1 previous receipt differs')
 baseline=ledger.get('baseline',{});need(baseline.get('status')=='已冻结' and digest(ROOT/baseline['report'])==baseline.get('sha256') and baseline.get('app_sha256')==old['app_build_sha256'],'W1 pre-change checkpoint differs')
 row=ledger['modules'].get('W1',{});expected=row.get('app_sha256');need(row.get('status')=='已通过' and expected==delivery['app_build_sha256'],'W1 not accepted for final APP')
 targets=set();smokes=0;items=[]
 for reference in row.get('reports',[]):
  rel=reference['path'];path=(ROOT/rel).resolve();need(path.is_relative_to((ROOT/'06_验证与后续工作').resolve()) and not unsafe(path) and digest(path)==reference.get('sha256'),'Frozen W1 report changed: '+rel)
  data=read(rel);runs=[data.get('latest',data),*data.get('runs',[])];count=reference.get('count');need(isinstance(count,int) and not isinstance(count,bool) and count>0,'Invalid W1 report count')
  run=next((r for r in runs if r.get('pass') is True and r.get('failed')==0 and r.get('passed')==count and r.get('module')==REAL_WESTERN_MODULE and report_app(r)==expected),None)
  need(run is not None,'W1 report does not bind final APP: '+rel)
  if '全量' in Path(rel).name:
   need(count>=60,'W1 full incomplete');targets.add('cloudflare' if run.get('cloudWorker') or 'cloud' in Path(rel).name.lower() else 'local')
  if '冒烟' in Path(rel).name:need(run.get('productionWrites') is False,'W1 smoke not isolated');smokes+=1
  if current_module:
   for source,value in run.get('sourceHashes',{}).items():need(digest(ROOT/source)==value,'Final W1 source differs: '+source)
   for folder,key in [(WEB,'buildHashes'),(CLOUD,'cloudBuildHashes')]:
    for source,value in run.get(key,{}).items():need((folder/source).resolve().is_relative_to(folder.resolve()) and digest(folder/source)==value,'Final W1 build differs: '+source)
  items.append({'report':rel,'sha256':reference['sha256'],'at':run['at'],'module':REAL_WESTERN_MODULE,'passed':count,'app_build_sha256':expected,'historical_stage':not current_module})
 need(targets=={'local','cloudflare'} and smokes,'W1 needs both full regressions and actual smoke')
 checks['real_western_module']={'report':REAL_WESTERN_LEDGER,'sha256':ref['sha256'],'reports':items,'scope':('W1 alone binds current source/build; earlier S1/C1C2/M1M5/F05 evidence stays historical.' if current_module else 'W1 and preceding stages bind their frozen historical APPs/reports; no current CSS acceptance claimed.')}
 return items

BAZI_SPACING_MODULE='八字留白与字号优化'
BAZI_SPACING_RECORD='06_验证与后续工作/八字表留白与字号交付记录.json'
PAGES_URL='https://fyao6.github.io/dongfang-zhihui-app/'

def pages_artifact_identity():
 source=(WEB/'发给负责人-东方智慧首页R4.html').read_bytes();adapter=ROOT/'06_验证与后续工作/GitHub静态预览提示.js'
 tag=('<script src="./pages-preview.js?v='+digest(adapter)[:12]+'"></script>').encode('ascii')
 before,separator,after=source.rpartition(b'</body>');need(separator,'Preview closing body missing')
 return {'app_sha256':digest(WEB/'东方智慧-首页体验R4.html'),'preview_sha256':hashlib.sha256(source).hexdigest(),'index_sha256':hashlib.sha256(before+tag+separator+after).hexdigest(),'adapter_sha256':digest(adapter)}

def bazi_spacing_history(delivery,checks):
 previous=delivery.get('previous_real_western_revision',{});rel='06_验证与后续工作/真实星盘档案交付记录.json'
 need(previous.get('report')==rel and digest(ROOT/rel)==previous.get('sha256'),'Historical W1 receipt changed')
 old=read(rel);need(old.get('pass') is True and old.get('real_western_revision') is True and previous.get('app_build_sha256')==old.get('app_build_sha256'),'Historical W1 APP identity differs')
 for field in ['foundation_baseline','module_ledger','complete_modules','document_module_ledger','reference_module_ledger','structure_module_ledger','real_western_module_ledger']:
  need(delivery.get(field)==old.get(field),'Historical W1 provenance differs: '+field)
 real_western_module(old,checks,current_module=False)
 changed=[]
 for rel,value in old['source_sha256'].items():
  if rel.startswith('04_研发源码/app/r4/') and digest(ROOT/rel)!=value:
   need(Path(rel).parent==R4.relative_to(ROOT) and Path(rel).suffix=='.css','Non-CSS APP source changed in spacing-only revision: '+rel);changed.append(rel)
 need(changed and sorted(changed)==delivery.get('changed_app_sources'),'Actual CSS changes differ from receipt')
 for reference in delivery.get('preserved_archives',[]):
  path=ROOT/reference['path'];need(path.parent==ROOT and path.suffix=='.zip' and path.is_file() and digest(path)==reference['sha256'],'Protected delivery ZIP changed')
 need(any(r==old['previous_zip'] for r in delivery.get('preserved_archives',[])) and delivery.get('previous_zip') in delivery.get('preserved_archives',[]),'Historical/latest ZIP protection missing')
 checks['previous_real_western_revision']={'report':previous['report'],'sha256':previous['sha256'],'app_build_sha256':old['app_build_sha256'],'historical_only':True}

def bazi_spacing_pages(delivery,checks,reports):
 pages=delivery.get('pages_preview',{});status=pages.get('status');need(status in ['pending','published_verified'] and pages.get('url')==PAGES_URL,'Pages preview scope/state missing')
 expected=pages_artifact_identity();need(pages.get('artifact')==expected,'Current static preview artifact identity differs')
 phases=['local','public'] if status=='published_verified' else ['local']
 for phase in phases:
  key='pages_'+phase;run=reports.get(key);need(run and run.get('module')==BAZI_SPACING_MODULE and run.get('phase')==phase and run.get('passed',0)>=4 and run.get('productionWrites') is False,'Current Pages smoke missing: '+phase)
  if phase=='public':need(run.get('url')==PAGES_URL,'Public Pages smoke URL differs')
  identity=run.get('identity',{});version=identity.get('version',{})
  need(all(version.get(k)==v for k,v in expected.items()) and identity.get('indexSha')==expected['index_sha256'] and identity.get('adapterSha')==expected['adapter_sha256'] and identity.get('restoredSha')==expected['preview_sha256'],'Pages smoke does not bind current APP/preview/index/adapter: '+phase)
  need(not run.get('apiRequests') and not run.get('businessRequests') and not run.get('errors') and not run.get('httpErrors'),'Pages static preview made API writes or had browser failures')
  for rel,value in run.get('buildHashes',{}).items():need((ROOT/rel).is_file() and digest(ROOT/rel)==value,'Pages smoke build identity differs: '+rel)
 need(pages.get('published') is (status=='published_verified') and delivery.get('current_source_published') is (status=='published_verified'),'Pages publication boolean differs')
 if status=='published_verified':
  ref=pages.get('publication_record',{});path=(ROOT/ref.get('report','')).resolve()
  need(path.is_relative_to((ROOT/'06_验证与后续工作').resolve()) and path.is_file() and digest(path)==ref.get('sha256'),'Current Pages publication proof missing/changed')
  proof=read(ref['report']);deployment=proof.get('deployment',{});version=deployment.get('artifact_version',{});http=proof.get('public_http_verification',{})
  need(proof.get('published') is True and deployment.get('workflow_conclusion')=='success' and deployment.get('published_url')==PAGES_URL and re.fullmatch('[0-9a-f]{40}',deployment.get('source_commit','')),'Pages successful deployment proof missing')
  need(all(version.get(k)==v for k,v in expected.items()) and version.get('source_commit')==deployment['source_commit']==reports['pages_public']['identity']['version'].get('source_commit'),'Pages published version/commit differs')
  need(http.get('status')==200 and http.get('authenticated') is False and (http.get('ready') is True or http.get('pass') is True),'Anonymous Pages HTTP proof missing')
  checks['pages_publication']={'report':ref['report'],'sha256':ref['sha256'],'source_commit':deployment['source_commit'],'workflow_run_id':deployment.get('workflow_run_id'),'static_only':True}
 checks['pages_preview']={'status':status,'url':PAGES_URL,'artifact':expected,'scope':'GitHub Pages static preview only. Sites/Netlify/backend/AI not redeployed.'}

def bazi_spacing_baseline(delivery,checks,reports):
 ref=delivery.get('spacing_baseline',{});rel='06_验证与后续工作/八字留白字号优化-改前.json'
 need(ref.get('report')==rel and digest(ROOT/rel)==ref.get('sha256') and delivery['source_sha256'].get(rel)==ref['sha256'],'Spacing baseline source missing/changed')
 before=read(rel);old_app=delivery['previous_real_western_revision']['app_build_sha256']
 need(before.get('pass') is True and before.get('phase')=='before' and before.get('productionWrites') is False and before.get('buildSha256')==before.get('version',{}).get('app_sha256')==old_app,'Spacing before baseline does not bind original public APP')
 need(ref.get('at')==before.get('at') and ref.get('app_build_sha256')==old_app,'Spacing baseline provenance differs')
 run=reports.get('spacing',{});need(run.get('module')==BAZI_SPACING_MODULE and run.get('passed',0)>=6 and run.get('productionWrites') is False,'Current six-group spacing verification missing')
 expected={'file':Path(rel).name,'sha256':ref['sha256'],'at':before['at'],'buildSha256':old_app}
 need(run.get('baseline')==expected,'Spacing verification references another baseline')
 value=before.get('calculation',{}).get('resultSha256');need(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) and run.get('calculation',{}).get('resultSha256')==value,'Spacing revision calculation differs from measured before state')
 for phase,document in [('before',before),('after',run)]:
  captures=document.get('captures',[]);need(len(captures)>=2,'Spacing comparison captures missing: '+phase)
  for capture in captures:
   name=capture.get('file','');need(Path(name).name==name and name.endswith('.png'),'Spacing capture must be a PNG basename')
   path='06_验证与后续工作/'+name;need(digest(ROOT/path)==capture.get('sha256')==delivery.get('captures_sha256',{}).get(path),'Spacing capture changed/not bound: '+path)
 checks['spacing_baseline']={'report':rel,'sha256':ref['sha256'],'at':before['at'],'app_build_sha256':old_app,'current_result_matches_baseline':True,'scope':'Real old-public CSS measurements and screenshots; not current regression results.'}

def validate_delivery(delivery_path=None):
 """Read-only delivery/report validation. Never writes documents, manifests or archives."""
 delivery=read(delivery_path or DELIVERY);pub=delivery['publication'];checkpoint=delivery.get('paused_by_user',False);pending=not checkpoint and pub.get('public_deployment_pending') is True;app_hash=digest(WEB/'东方智慧-首页体验R4.html');need(delivery['pass'] and app_hash==delivery['app_build_sha256'],'Current app differs from latest delivery')
 ui_revision=delivery.get('ui_revision') is True;document_revision=delivery.get('document_revision') is True;reference_revision=delivery.get('reference_revision') is True;structure_revision=delivery.get('structure_revision') is True;real_western_revision=delivery.get('real_western_revision') is True;bazi_spacing_revision=delivery.get('bazi_spacing_revision') is True;checks={};verified_reports={}
 if ui_revision:
  need(pending and not checkpoint,'UI revision full-stack publication scope differs')
  if bazi_spacing_revision:need(delivery.get('current_full_stack_source_published') is False,'Spacing revision must not claim Sites/Netlify were updated')
  else:need(delivery.get('current_source_published',pub.get('current_source_published')) is False,'Original chart revision must remain explicitly unpublished')
  guide=delivery['guide'];need((ROOT/guide).resolve().is_relative_to((ROOT/'05_后台与研发说明').resolve()) and (ROOT/guide).is_file(),'Original chart guide missing or outside documentation directory')
  revision_module=delivery.get('revision_module');need(isinstance(revision_module,str) and revision_module.strip(),'Current UI revision module is missing')
  for name,(file,count) in UI_REPORTS.items():
   ref=delivery.get('verification',{}).get(name,{})
   need(ref.get('report')=='06_验证与后续工作/'+file and ref.get('sha256') and ref.get('at'),'Required current UI specialty reference missing: '+name)
  historical_foundation(delivery,checks,verified_reports)
  if bazi_spacing_revision:
   need(not any([document_revision,reference_revision,structure_revision,real_western_revision]) and revision_module==BAZI_SPACING_MODULE,'Current spacing module/flags differ');bazi_spacing_history(delivery,checks)
  if real_western_revision:
   need(not document_revision and not reference_revision and not structure_revision and revision_module==REAL_WESTERN_MODULE,'Final W1 module differs');real_western_module(delivery,checks)
  if structure_revision:
   need(not document_revision and not reference_revision and revision_module==STRUCTURE_MODULE,'Final S1 module differs');structure_module(delivery,checks)
  if reference_revision:
   need(not document_revision and revision_module==REFERENCE_MODULE,'Final reference module differs');reference_modules(delivery,checks)
  if document_revision:
   need(revision_module==DOCUMENT_MODULE,'Final document module name differs');document_modules(delivery,checks)
 for kind,file,base,key in [('local','本轮全量回归结果.json',WEB,'buildHashes'),('cloudflare','公网适配全量回归结果.json',CLOUD,'cloudBuildHashes')]:
  report=latest(file);need(report['pass'] and report['passed']>=60 and report['failed']==0,'Final full regression not passed: '+file)
  for rel,sha in report[key].items():need((base/rel).resolve().is_relative_to(base.resolve()) and digest(base/rel)==sha,'Build mismatch: '+rel)
  checks[kind]={'report':'06_验证与后续工作/'+file,'module':report['module'],'at':report['at'],'passed':report['passed']}
 for rel,sha in delivery['source_sha256'].items():need(digest(ROOT/rel)==sha,'Source mismatch: '+rel)
 app=(WEB/'东方智慧-首页体验R4.html').read_text(encoding='utf-8')
 for n in ['life-chart-core.js','life-chart-bazi.js','life-chart-western.js','bazi-time.js','bazi-compare.js','bazi-glossary.js','life-charts.css','navigation-back.js','creator-app.js','analytics-app.js','life-birth-entry.js','platform.js','i18n-ui.js','foundation-state.js','foundation-state.css']:
  need((R4/n).read_text(encoding='utf-8') in app,'Missing built source: '+n)
 if ui_revision:
  for n in UI_SOURCES:need((R4/n).read_text(encoding='utf-8') in app,'Missing original chart source in APP: '+n)
 need((WEB/'创作者中心.html').read_bytes()==(R4/'creator-center.html').read_bytes(),'Creator standalone differs')
 review=(WEB/'发给负责人-东方智慧首页R4.html').read_text(encoding='utf-8');embedded,_=json.JSONDecoder().raw_decode(review.split('const APP=',1)[1]);need(embedded.replace('__INITIAL__','{}')==app,'Review embeds another app')
 if document_revision or reference_revision or structure_revision or real_western_revision or bazi_spacing_revision:
  expected_inputs=['04_研发源码/app/r4/'+n for n in build_inputs()];need(delivery.get('embedded_sources')==expected_inputs,'Current APP build inputs differ from delivery')
  for name in build_inputs():need(embedded_text(name) in app,'Missing actual APP input: '+name)
 if real_western_revision or bazi_spacing_revision:city_snapshot(delivery,checks)
 for group in ['source_sha256','build_sha256']:
  for rel,sha in delivery[group].items():need((ROOT/rel).resolve().is_relative_to(ROOT.resolve()) and digest(ROOT/rel)==sha,'Current delivery mismatch: '+rel)
 for name,reference in delivery['verification'].items():
  report_path=(ROOT/reference['report']).resolve();need(report_path.is_relative_to((ROOT/'06_验证与后续工作').resolve()),'Specialty path outside verification directory')
  if reference.get('sha256'):need(digest(report_path)==reference['sha256'],'Specialty report bytes changed: '+name)
  document=read(reference['report']);report=document.get('latest',document)
  if reference.get('at'):
   candidates=[report,*document.get('runs',[]),*document.get('phases',{}).values()];report=next((item for item in candidates if item.get('at')==reference['at'] and (not reference.get('module') or item.get('module')==reference['module'])),None)
  need(report is not None,'Recorded specialty run missing: '+name)
  report_app=report.get('buildSha256') or report.get('appBuildSha256') or report.get('buildHashes',{}).get('东方智慧-首页体验R4.html')
  need(report['pass'] is True and report.get('failed',0)==0 and report_app==app_hash and report['at']==reference.get('at',report['at']),'Current specialty mismatch: '+name)
  for rel,sha in report.get('sourceHashes',{}).items():need(digest(ROOT/rel)==sha,'Specialty source differs: '+rel)
  if reference.get('module'):need(report.get('module')==reference['module'],'Specialty module differs: '+name)
  checks[name]={'report':reference['report'],'at':report['at'],'module':report.get('module'),'passed':report['passed'],'sha256':digest(report_path)}
  verified_reports[name]=report
 if ui_revision:
  for name,(file,count) in UI_REPORTS.items():
   need(verified_reports[name].get('passed',0)>=count,'Required current UI specialty coverage incomplete: '+name)
   if bazi_spacing_revision:need(verified_reports[name].get('module')==BAZI_SPACING_MODULE,'Current spacing specialty module differs: '+name)
   if document_revision:need(verified_reports[name].get('module')==DOCUMENT_MODULE,'Final document specialty module differs: '+name)
   if reference_revision:need(verified_reports[name].get('module')==REFERENCE_MODULE,'Final reference specialty module differs: '+name)
   if structure_revision:need(verified_reports[name].get('module')==STRUCTURE_MODULE,'Final S1 specialty module differs: '+name)
   if real_western_revision:need(verified_reports[name].get('module')==REAL_WESTERN_MODULE,'Final W1 specialty module differs: '+name)
  if bazi_spacing_revision:
   bazi_spacing_pages(delivery,checks,verified_reports);bazi_spacing_baseline(delivery,checks,verified_reports)
  if real_western_revision:
   for key,(path,minimum) in REAL_WESTERN_SMOKES.items():
    smoke=verified_reports.get(key);need(smoke and delivery['verification'][key].get('report')==path and smoke.get('module')==REAL_WESTERN_MODULE and smoke.get('passed',0)>=minimum and smoke.get('productionWrites') is False,'Final same-build W1 smoke missing: '+key)
  if structure_revision:
   for key,(path,minimum) in STRUCTURE_SMOKES.items():
    smoke=verified_reports.get(key);need(smoke and delivery['verification'][key].get('report')==path and smoke.get('module')==STRUCTURE_MODULE and smoke.get('passed',0)>=minimum and smoke.get('productionWrites') is False,'Final same-build S1 smoke missing: '+key)
  if reference_revision:
   for key,path in REFERENCE_SMOKES.items():
    smoke=verified_reports.get(key);need(smoke and delivery['verification'][key].get('report')==path and smoke.get('module')==REFERENCE_MODULE and smoke.get('passed',0)>0 and smoke.get('productionWrites') is False,'Final same-build reference smoke missing: '+key)
  if document_revision:
   smoke=verified_reports.get('document_smoke');need(smoke and smoke.get('module')==DOCUMENT_MODULE and smoke.get('passed',0)>0 and smoke.get('productionWrites') is False,'Current M5 smoke missing')
   old=delivery.get('previous_ui_revision',{});need(old.get('report')=='06_验证与后续工作/原创命盘表达交付记录.json' and digest(ROOT/old['report'])==old.get('sha256'),'Previous UI receipt changed')
  if revision_module=='八字紧凑同屏优化':
   layout=verified_reports['layout'];expected={'at':'2026-11-09T10:32:54.233Z','module':'八字参考排版重做','buildSha256':'44a328b1238a7dd652d87d7a95989deae5bd9312b12203227b5a838bbf4707eb','report':'06_验证与后续工作/页面长度与日间命盘优化核验.json'}
   need(layout.get('module')==revision_module and delivery.get('layout_measurement',{}).get('at')==layout['at'],'Compact measurement is not bound to current receipt')
   need(all(layout.get('baseline',{}).get(k)==v for k,v in expected.items()) and delivery['layout_measurement']['baseline']==layout['baseline'],'Compact measurement baseline differs from accepted 44a328 reference layout')
 ledger=delivery['module_ledger']['modules'];need(ledger and all(m['pass'] for m in ledger),'Module evidence missing')
 if checkpoint:
  need({m['id'] for m in ledger}=={'F01','F02'} and pub['public_deployment_pending'] and not pub['package_matches_public'],'Checkpoint boundary differs')
  saved=read('06_验证与后续工作/F03暂停源码保存与稳定版核验.json')
  need(digest(ROOT/saved['patch'])==saved['patch_sha256'],'Pending F03 patch differs')
  for rel,sha in saved['stable_sha256'].items():need(digest(ROOT/rel)==sha,'Unverified F03 source entered runtime: '+rel)
 elif pending:
  need(delivery.get('paused_by_user') is False and delivery.get('all_planned_work_complete') is False,'Public-pending scope differs')
  need(set(delivery.get('complete_modules',[]))=={'F01','F02','F03','F04','F05'},'Verified local modules incomplete')
  need({m['id'] for m in ledger}>={'F01','F02','F03','F04','F05'} and all(m.get('pass') is True and m.get('final') is True for m in ledger),'Pending release module evidence incomplete')
  if ui_revision:
   for key in ['local','cloudflare']:
    ref=delivery['current_full'][key];need(checks[key]['report']==ref.get('report') and digest(ROOT/ref['report'])==ref.get('sha256') and checks[key]['at']==ref['at'] and checks[key]['module']==ref['module']==revision_module,'Current full regression reference differs: '+key)
  else:
   f04=next(m for m in ledger if m['id']=='F04')
   for target,key in [('local','local'),('cloud','cloudflare')]:need(checks[key]['at']==f04['full'][target]['at'] and checks[key]['module']==f04['full'][target]['module'],'Pending release full regression differs')
  foundation=verified_reports.get('foundation',{});restore=verified_reports.get('restore',{})
  need(foundation.get('module')=='基础框架F05' and foundation.get('contracts',{}).get('equal') is True and foundation.get('productionWrites') is False and foundation.get('isolation',{}).get('servicesStopped') is True,'Actual F05 contract/restore verification missing')
  need(restore.get('module')=='基础框架F05' and restore.get('mode')=='both' and restore.get('productionWrites') is False,'Actual two-backend restore verification missing')
  need(foundation.get('restoreReport',{}).get('at')==restore['at'] and foundation['restoreReport'].get('module')==restore['module'],'F05 aggregate/raw restore binding differs')
  need(pub.get('sites_status')=='succeeded' and pub.get('netlify_status')=='blocked_credit_limit' and pub.get('package_matches_public') is False,'Public-pending deployment states differ')
  blocker_path=pub['blocker_report'];blocker_doc=read(blocker_path);blocker=blocker_doc.get('latest',blocker_doc)
  need(blocker.get('pass') is True and blocker.get('http_status')==403 and blocker.get('error')=='Account credit usage exceeded - new deploys are blocked until credits are added','Credit-limit blocker evidence missing')
  need(blocker.get('new_netlify_deploy_created') is False and blocker.get('old_netlify_deploy_id')==pub['netlify_deploy_id'] and blocker.get('old_netlify_status')=='ready','Old Netlify deploy provenance differs')
  need(blocker.get('sites_status')=='succeeded' and blocker.get('source_commit')==pub['source_commit'],'Sites deployment blocker identity differs')
  checks['publication_blocker']={'report':blocker_path,'sha256':digest(ROOT/blocker_path),'http_status':403,'new_netlify_deploy_created':False,'sites_status':pub['sites_status'],'netlify_status':pub['netlify_status']}
 else:
  public=latest(Path(pub['public_build_match_report']).name);need(public['pass'] and public['localAppSha256']==app_hash and public['sourceCommit']==pub['source_commit'] and public['netlifyDeployId']==pub['netlify_deploy_id'],'Public build evidence differs')
  need({r['route'] for r in public['checks']}=={'/','/experience','/creator','/admin','/app'} and all(r['status']==200 and r['generatedMatch'] and r['servedNormalizedSha256']==r['expectedNormalizedSha256'] for r in public['checks']),'Five public entry pages differ')
  acceptance=latest(Path(pub['public_acceptance_report']).name);need(acceptance['pass'] and acceptance['localAppSha256']==app_hash and acceptance['netlifyDeployId']==pub['netlify_deploy_id'],'Current public acceptance differs')
  need(pub['sites_status']=='succeeded' and pub['netlify_status']=='ready','Current release is not published')
 return {'delivery':delivery,'pub':pub,'checkpoint':checkpoint,'pending':pending,'ui_revision':ui_revision,'document_revision':document_revision,'reference_revision':reference_revision,'structure_revision':structure_revision,'real_western_revision':real_western_revision,'bazi_spacing_revision':bazi_spacing_revision,'checks':checks,'verified_reports':verified_reports,'app_hash':app_hash,'guide':locals().get('guide'),'revision_module':locals().get('revision_module')}

def main():
 sys.stdout.reconfigure(encoding='utf-8');validated=validate_delivery()
 if '--preflight-only' in sys.argv:
  print(json.dumps({'pass':True,'read_only':True,'delivery_record':DELIVERY,'app_build_sha256':validated['app_hash'],'checks':validated['checks'],'scope':'Delivery/report/source/build validation only; no document, manifest, PREFLIGHT or ZIP writes. Payload private-value scan and new ZIP CRC remain normal packaging checks.'},ensure_ascii=False),flush=True);return
 delivery=validated['delivery'];pub=validated['pub'];checkpoint=validated['checkpoint'];pending=validated['pending'];ui_revision=validated['ui_revision'];document_revision=validated['document_revision'];reference_revision=validated['reference_revision'];structure_revision=validated['structure_revision'];real_western_revision=validated['real_western_revision'];bazi_spacing_revision=validated['bazi_spacing_revision'];checks=validated['checks'];verified_reports=validated['verified_reports'];app_hash=validated['app_hash'];guide=validated['guide'];revision_module=validated['revision_module']
 now=datetime.now(timezone(timedelta(hours=8)));target=ROOT/('东方智慧APP完整概念方向包-'+now.strftime('%Y-%m-%d-%H时%M分%S秒')+'.zip');need(not target.exists(),'Archive already exists')
 print('当前源码、查看页、创作者中心、云端生成页及本轮完整回归构建已核对。',flush=True)
 notes=f'''东方智慧APP · 暂停阶段交付包
打包时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）

用户要求先暂停开发，记录当前进度并打包交付。解压后打开“打开这里.html”，包内直接是入口及00—07分类目录，无额外项目包装层。

本包运行版：已验收F01、F02
F01完成连接加载/失败重试、12秒读取超时、错误响应身份门禁及页面/草稿保留。
F02完成人账号/游客本机资料隔离、真实保存与失败手动重试、旧响应/媒体/弹层隔离、读取错误恢复、公共偏好及离线重开。
保留当前成熟创作者中心及APP真实闭环、公司数据中心、三地图4/4/3、生辰四字段/保存门禁/准确时间自动紫微、自动累计计时、四语及原有功能。
AI接入暂缓，人工审核保留；不代表真实AI、支付、硬件或原生实机验收。

当前验证
最终两套完整回归各60/0，实际构建账号专项两端各14/0、真实A/B迟媒体两端各4/0、当前连接恢复两端各14/0、真实离线按钮偏好门禁2/0。
当前源码、03可查看页面、Cloud生成页逐项匹配上述F02最终验收构建。
APP SHA-256：{app_hash}
本次只做阶段整理与打包字节核验，没有重跑业务或重新发布；历史失败及修复记录均保留。

未完成工作已明确保留
F03候选代码未完成整体验收，作为06_验证与后续工作/基础框架F03未完成改动.patch保留，未混入可运行源码；专项harness保留但尚待完成。
F04后台恢复增强、F05契约/隔离恢复仅方案准备，未实施或验收。基础框架F01—F05并未全部完成。
完整续接位置、两项F03审查问题和命令说明：05_后台与研发说明/基础框架阶段交付与续接说明.txt。
实际阶段记录：{DELIVERY}。

打开方式和公网边界
本包离线看界面：03_当前APP/发给负责人-东方智慧首页R4.html。
本机功能联调：05_后台与研发说明/启动APP与后台.cmd，按源码说明安装依赖；首次由接收人自行创建管理员。
原公网：https://eastern-wisdom-demo-fuyao.netlify.app/experience
公网仍为原Sites v{pub['sites_version']} / Netlify {pub['netlify_deploy_id']}；本次F01/F02未发布，包与公网尚未同步。不要用旧公网验收冒充本包上线验证。
本包不带原账号、密码、会话、运行数据库、环境文件或密钥。

数据边界
旧未标明账号的共享记录保留在游客档案，退出账号可回看；不推断并入任意账号。
生辰、排盘、学习笔记等仍在本浏览器按账号保存，没有完整跨设备云同步或自动补传。
新生辰不要求出生地/城市/时区/经纬度，不猜未知时间或地点；缺地点不生成新的完整西方宫位，旧完整档案保留。
藏语待母语审校，浏览器视口和本地Cloudflare不代表原生实机或生产恢复验收。

文件完整性
旧整包、改前ZIP和部署tar不嵌套；F03差异以可读.patch随包交付，原项目07目录另保留候选源ZIP。
依赖、数据库/sidecar/备份、环境、凭据、缓存、日志、Git内部状态均排除。
两份清单对应本包实际文件，06目录含打包预检；最终ZIP哈希/CRC/逐文件核验保存在原项目06_验证与后续工作/最新打包校验结果.json，不递归放进ZIP。
'''
 if not checkpoint and not pending:
  notes=f'''东方智慧APP · 基础框架交付包
打包时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）
F01—F04各业务模块已完成双端完整回归及专项，F05接口契约与隔离数据库恢复通过。AI接入暂缓，人工审核保留。
当前源码、03页面、Cloud生成页与测试记录一致，公网Sites v{pub['sites_version']} / Netlify {pub['netlify_deploy_id']}已核对。
APP SHA-256：{app_hash}
本次打包只做字节/清单核验，没有重跑业务或重新部署。

解压后打开“打开这里.html”。本机运行：05_后台与研发说明/启动APP与后台.cmd，首次自行创建管理员。
公网：https://eastern-wisdom-demo-fuyao.netlify.app/experience
本轮说明：05_后台与研发说明/基础框架阶段说明与验收.txt
实际记录：{DELIVERY}

保留成熟创作者工作台、公司真实数据中心、三地图4/4/3、四语和自动累计计时。
生辰生日/性别必填，称呼/时间选填；先保存再进入，有准确时间即自动生成紫微；无出生地/时区/经纬度控件。
旧未标明账号资料留在游客档案，不推断到登录账号。生辰/排盘/笔记按本浏览器账号保存；无完整跨设备同步或自动补传。
恢复验证仅隔离SQLite与本地D1数据库，未覆盖R2素材、浏览器资料或生产库恢复；未声称原生实机、正式AI、支付或设备接通。藏语待母语审校。

旧ZIP与部署归档不嵌套。11月6日暂停patch/报告仅作历史追溯，当前源码已继续完成。
包内不含原账号、运行数据库、密钥、环境文件、依赖或Git内部状态；接收方自行安装依赖并创建管理员。
资料校验清单.csv与原始来源与文件校验.json对应实际包内文件；最新ZIP哈希/CRC验证结果保存在原项目06目录，不递归收入ZIP。
'''
 if pending:
  notes=f'''东方智慧APP · 基础框架本地验收与发布待续包
打包时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）

F01—F05已完成本轮本机与本地Cloudflare验收：连接恢复、账号与真实保存、创作者人工闭环、后台读取/登录恢复、接口契约与隔离SQLite/D1恢复。AI接入继续暂缓，人工审核保留。
本包源码、03页面和Cloud生成页为已验收的新构建，APP SHA-256：{app_hash}。
Sites后台已部署成功：v{pub['sites_version']}；源提交：{pub['source_commit']}。
Netlify前台仍为旧部署 {pub['netlify_deploy_id']}，当前仍ready；本轮没有创建新Netlify部署。账户额度超限使create deploy实际返回HTTP403，完整公网同步仍待续。本包不能描述为Netlify前台已更新或所有计划工作已完成。
真实阻塞：Account credit usage exceeded - new deploys are blocked until credits are added
本次不会购买额度或另建站点；额度恢复后沿用原站点继续发布，再验证五入口与当前构建一致。

先打开“打开这里.html”。本机功能运行：05_后台与研发说明/启动APP与后台.cmd；离线界面：03_当前APP/发给负责人-东方智慧首页R4.html。
公网地址仍可访问，但Netlify前台是旧版：https://eastern-wisdom-demo-fuyao.netlify.app/experience
当前源码和Netlify前台不同；Sites后台新部署状态与Netlify前台旧版本分别记录，不使用旧公网验收冒充本轮发布通过。
实际记录：{DELIVERY}
发布阻塞核验：{pub['blocker_report']}
本轮说明：05_后台与研发说明/基础框架阶段说明与验收.txt

保留成熟创作者工作台、12类真实指标、公司数据中心、三地图4/4/3、四语及自动累计计时；生辰仅生日/性别和选填称呼/时间，先保存再进入，准确时间保存即自动紫微。无地点不生成新的完整西方宫位。
旧未标明账号资料仍留游客档案；生辰/排盘/笔记按浏览器账号保存，没有完整跨设备同步或自动补传。数据库恢复仅隔离SQLite和本地D1，不代表生产、R2或浏览器资料恢复，也不代表原生实机、AI、支付或设备接通。
旧ZIP、备份和部署归档不嵌套；11月6日暂停patch仅供追溯，F03—F05当前已经验收。本包不含原账号、数据库、凭据、环境文件或依赖，接收方首次启动自行创建管理员。
本次打包仅核对字节与清单，不重跑功能、不发布、不覆盖旧ZIP。两份清单对应包内文件，ZIP结果保存在原项目06目录。
'''
 if ui_revision:
  notes=f'''东方智慧APP · {revision_module}交付包
打包时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）

本包当前模块：{revision_module}。
范围以本轮实际交付记录为准：{delivery['scope']}。
当前源码、03可查看页面和Cloud生成页绑定本轮完整回归及出生资料、三盘、原创交互、页面测量、八字操作五类专项；八字操作复用八字参考排版核验报告并保留本轮新增组，不拿旧F04构建或前一轮专项代替本轮验收，不沿用旧页面缩短比例。
APP SHA-256：{app_hash}
本轮说明：{guide}
实际交付与验证记录：{DELIVERY}

本轮原创命盘尚未发布。已发布的Sites v{pub['sites_version']}（提交{pub['source_commit']}）是较早基础框架版本，不含本轮原创界面；Netlify仍为v{pub.get('netlify_published_frontend_version',14)}旧部署{pub['netlify_deploy_id']}。
Netlify免费额度不足的既有阻塞继续保留，等待用户恢复额度后沿原站点继续；不重试发布、不购买额度或另建站点。
公网仍可访问，但不能作为当前源码已发布的证明：https://eastern-wisdom-demo-fuyao.netlify.app/experience
发布阻塞记录：{pub['blocker_report']}

基础框架F01—F05的原模块台账保留。旧F05契约与隔离SQLite/本地D1恢复报告通过原基础交付记录的SHA-256绑定，另核本轮后端/API源码未变；它们是历史未改后端证据，不是本轮UI构建或生产恢复验收。
前一轮命盘UI的43份源码、11份构建和双端完整结果保留在交付记录previous_revisions。11月10日14:55交付ZIP保持原快照，不含其后的紧凑优化；本包如已生成，只由当前交付记录与实际字节校验证明内容，不改写旧包。
不代表R2素材、浏览器资料或生产库恢复，也不代表原生实机、AI、支付或设备接通。AI继续暂缓，人工审核和真实统计口径不变。
生日/性别必填、称呼/出生时间选填，先保存才能进入生命地图；准确时间保存即自动生成紫微，未知时间不猜完整命盘。不恢复出生地、时区或经纬度输入；没有地点不生成新的完整西方宫位，完整旧档案独立复算。
生辰、排盘和笔记仍按当前浏览器账号保存，没有完整跨设备同步或自动补传。藏语待母语审校，视觉仍待用户评价。

解压后打开“打开这里.html”；离线查看：03_当前APP/发给负责人-东方智慧首页R4.html。
本机联调：05_后台与研发说明/启动APP与后台.cmd，接收方安装依赖并自行创建首个管理员；以启动窗口实际显示地址为准。效果页的8880是当前开发机预览地址，不代表接收方已有后台服务。
本包不含原账号、数据库、凭据、环境文件、依赖或旧压缩包。11月6日ZIP及暂停patch仅作历史追溯。
本次打包仅核对实际文件、清单与ZIP字节，不重跑业务、不发布、不覆盖旧ZIP；最终ZIP核验记录留在原项目06目录，不递归收进ZIP。
'''
 if document_revision:
  notes=f'''东方智慧APP · 用户改动文档M1—M5本地交付包
打包时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）

范围：{delivery['scope']}
当前最终模块：{revision_module}；APP SHA-256：{app_hash}
最终双端完整回归、出生/三盘/原创交互/长度/八字五专项及M5冒烟均绑定当前构建；M1—M4按各自冻结构建保留历史，不把旧阶段hash冒充最终源码。
说明：{guide}
交付记录：{DELIVERY}；阶段台账：{DOCUMENT_LEDGER}

首页三个快捷入口、三盘各自独立、真实地心星盘及未知时间全天范围图、紫微日间白底、八字档案/流运/神煞三页与12类有来源规则、统一展开控件均以本轮实际记录为准。完整七列对照/三运概览移至更多，未删计算、笔记、档案和复算。
国印与金舆使用本命年干；其余规则明确日干/年支/节令月支，不冒称lunar原生完整神煞。AI继续暂缓。
出生资料仅生日、性别、选填称呼与时间；未知不造精确盘，无坐标不猜ASC/宫位。旧完整档案按自身资料复算。三地图4/4/3、真实计时、四语、创作者和数据中心保留。
本轮只本地验收，未更新原公网Sites v15/Netlify v14；托管和飞书暂不处理。旧ZIP保持原快照；本次打包只生成新的独立包，不覆盖或嵌套旧包。
旧F01—F05台账及F05隔离SQLite/本地D1恢复是原构建的历史证据，本轮只核未改后端，不冒充新UI恢复或生产恢复；不代表AI、支付、硬件或原生实机接通。个人本机资料不代表完整跨设备同步。
解压后打开“打开这里.html”；本机启动见05目录启动脚本，首次自行创建管理员。包内排除旧压缩包、数据库、凭据、环境文件、依赖和缓存。
本次仅字节/清单/CRC核验，不发布或重跑业务。最终ZIP核验结果留原项目06目录，不递归收入包。
'''
 if reference_revision:
  notes=f'''东方智慧APP · 11月11日准了参考星盘/八字比例本地交付包
打包时间：{now.isoformat()}（北京时间）
范围：{delivery['scope']}
最终模块：{revision_module}；APP SHA-256：{app_hash}
当前双端完整回归、五专项与星盘/八字两烟均绑定最终C2构建；C1和旧M1—M5仅按各自冻结APP保留历史。
说明：{guide}；交付记录：{DELIVERY}；两模块台账：{REFERENCE_LEDGER}
固定lunar1.7.7计算本人四柱与运年月；西盘仍Astronomy Engine2.1.19，不用日历库替代天文计算。12类神煞为APP明确锚点查表，非引擎原生完整神煞API。
生辰四字段、未知紫微/八字不造精确盘、未知西盘25样本全天范围与无坐标不猜ASC/宫位的边界不变。三地图4/4/3、计时、四语、保存/复算保留。
本轮仅本地验收；日间视觉待用户评价。AI、托管、飞书继续暂缓，Sites v15/Netlify v14没有本轮UI。
旧receipt/台账/ZIP完全保留，旧视觉已被最新反馈替代；本次仅在用户另行要求打包后生成独立新ZIP，不覆盖或嵌套旧包。
F05仍是未改后端的历史隔离SQLite/本地D1恢复证据，不代表当前UI新恢复/生产恢复/跨设备同步或实机验收。
包内直接是根入口和00—07，排除旧归档、运行库、凭据/环境、依赖及缓存；不部署、不联系平台、不购买额度。
'''
 if structure_revision:
  notes=f'''东方智慧APP · 完整星盘结构与连线本地交付包
打包时间：{now.isoformat()}（北京时间）
范围：{delivery['scope']}
最终模块：{revision_module}；APP SHA-256：{app_hash}
本轮双端完整回归、五专项、S1结构冒烟与星盘C1守护烟均绑定最终构建；旧C1/C2及M1—M5保持自身冻结证据，旧八字C2继续沿用。
说明：{guide}；记录：{DELIVERY}；台账：{STRUCTURE_LEDGER}
lunar1.7.7负责历法/八字，不提供西方天体经度/宫位/相位API。西盘仍Astronomy2.1.19真实位置，本APP按既定规则计算相位及旧完整档案宫位。
新增结构参照线与真实宫位/相位分开说明；不为填满盘面虚构关系。未知时间只有25样本全天范围，无坐标不猜ASC/宫位，四字段生辰不改。
本轮只本地验收，视觉待用户评价；AI/托管/飞书暂停，Sites v15/Netlify v14没有本轮UI。旧receipt/台账/ZIP均原样保留，不将历史恢复当当前新恢复。
仅用户以后明确要求打包才生成独立新包，不覆盖/递归旧包。包内根入口和00—07直接展开，排除运行库、凭据/环境、依赖、缓存及旧归档。本次不发布、不联系平台、不购买额度。
'''
 if real_western_revision:
  notes=f'''东方智慧APP · 真实星盘出生城市与完整档案本地交付包
打包时间：{now.isoformat()}（北京时间）
范围：{delivery['scope']}
最终模块：{revision_module}；APP SHA-256：{app_hash}
本轮双端完整、五专项、W1档案烟10/S1结构烟8/C1星盘烟7均绑定当前构建；旧S1/C1C2/M1M5/F05按自身冻结证据保留。
说明：{guide}；记录：{DELIVERY}；台账：{REAL_WESTERN_LEDGER}
用户最新仅授权星盘档案恢复出生城市。主生辰与紫微/八字原规则保留；星盘从实际选择的GeoNames城市id自动获取IANA时区和坐标，有准确时刻才能计算完整个人盘。仅目录Asia/Urumqi城市需明确出生记录用北京时间或新疆时间，未选不猜；目录原值与clockBasis保留，其他城市自动。未知时间不默认零点，城市未找到不猜。未建立星盘独立档案时保留原固定北京时间25点参考；独立城市档案未知时刻按该城市真实本地日期起止计算，常见23/24/25小时，也处理半小时等调整，以至多1小时步长加末端动态采样。当地午夜不存在则明确报错；午夜重复取最早时刻仅作为整日边界，不推定出生时刻。
城市离线固定索引含全球城市和原始多语言别名，同名需实际区分选择；坐标是城市代表位置，非出生门牌。GeoNames CC BY4.0来源/许可/改编说明保留，原始ZIP仅本地存留，不收入交付包。
西盘真实天体仍Astronomy2.1.19，本APP既定宫制与相位规则不冒充lunar API。AI/托管/飞书暂停，未更新Sites v15/Netlify v14，视觉仍待用户评价。
旧receipt/ledger/ZIP不覆盖不嵌套；本次仅用户另行授权打包后生成独立新包，不发布、不购买、不联系平台。排除运行数据库、凭据/环境、依赖、缓存及旧归档；历史F05恢复不等于当前UI新恢复、生产恢复、实机或跨设备同步。
'''
 if bazi_spacing_revision:
  pages_status='已发布并实际验收' if delivery['pages_preview']['published'] else '待发布；当前线上仍为前一版本'
  notes=f'''东方智慧APP · {revision_module}交付包
打包时间：{now.isoformat()}（北京时间）
范围：{delivery['scope']}；当前APP SHA-256：{app_hash}
本轮双端完整回归及五专项绑定新CSS与当前03/Cloud构建；Pages静态预览{pages_status}：{PAGES_URL}
说明：{guide}；记录：{DELIVERY}。Sites v15/Netlify v14与账号后台未更新，AI继续暂缓。
旧W1及更早收据、冻结报告、18:36及其他原ZIP保留，不把旧回归当本轮新结果。旧F05仅证明未改后端的历史隔离恢复。
本次打包只核字节/清单/CRC，不重跑功能或发布；排除旧ZIP、Git内部、数据库、环境凭据、依赖与缓存，不覆盖原包。
'''
 (ROOT/'交付包说明.txt').write_text(notes,encoding='utf-8')
 p=ROOT/'先读我.txt';body=re.sub(r'【当前完整打包状态】[\s\S]*?【当前完整打包状态结束】\s*','',p.read_text(encoding='utf-8'),count=1)
 status_text='暂停阶段包：F01/F02已验收，F03待续，F04/F05未实施，公网未同步。' if checkpoint else ('F01—F05本地验收完成；Sites后台新部署，Netlify额度403阻塞，前台仍旧版，公网同步待续。' if pending else '基础框架F01—F05已完成本轮验收并同步原公网。')
 if ui_revision:status_text=revision_module+'已本地验收并纳入本次交付包，尚未发布；Sites v15不含本轮界面，Netlify仍v14，旧F05恢复仅作未改后端的历史证据。'
 if bazi_spacing_revision:status_text=revision_module+'已验收；Pages静态预览'+('已更新' if delivery['pages_preview']['published'] else '待更新')+'，Sites/Netlify及后台保持旧版，AI暂缓。'
 p.write_text(f'【当前完整打包状态】\n{now.isoformat()}；{status_text}此前完整包说明均为历史快照。请先读交付包说明.txt。\n【当前完整打包状态结束】\n\n'+body,encoding='utf-8')
 write(PREFLIGHT,{'packaged_at':now.isoformat(),'app_build_sha256':app_hash,'sites_version':pub['sites_version'],'netlify_deploy_id':pub['netlify_deploy_id'],'checks':checks,'no_wrapper':True,'runtime_and_archives_excluded':True,'scope':'Packaging preflight only; no new functional regression or deployment.'})
 files=collect_files();doc=html.fromstring((ROOT/'打开这里.html').read_text(encoding='utf-8'));main=(doc.xpath('//main') or doc.xpath('//body'))[0]
 for old in doc.xpath('//*[@id="current-delivery-package"]'):old.getparent().remove(old)
 for a in doc.xpath('//a[@href]'):
  u=urlsplit(a.get('href'))
  if not(u.scheme or u.netloc) and Path(unquote(u.path)).suffix.lower() in SKIP_SUFFIX:
   li=a.getparent()
   if li.tag=='li':li.getparent().remove(li)
   else:a.drop_tag()
 for ul in doc.xpath('//ul[contains(concat(" ",normalize-space(@class)," ")," files ")]'):
  parent=ul.getparent()
  if parent.tag=='details':parent.getparent().remove(parent)
  else:parent.remove(ul)
 section=html.fragment_fromstring(f'<section id="current-delivery-package"><h1>暂停阶段交付 · {now.strftime("%Y-%m-%d")}</h1><p>本包运行版为已验收F01/F02，F03候选以待续patch保留，F04/F05未实施。源码与本轮最终两套60项回归构建一致；公网仍v{pub["sites_version"]}未同步。</p><p><a href="05_后台与研发说明/基础框架阶段交付与续接说明.txt">先看进度与续接说明</a> · <a href="06_验证与后续工作/基础框架F03未完成改动.patch">F03未完成代码差异</a></p><p><a href="交付包说明.txt">先读交付包说明</a> · <a href="03_当前APP/发给负责人-东方智慧首页R4.html">离线负责人查看页</a> · <a href="https://eastern-wisdom-demo-fuyao.netlify.app/experience">原公网APP（本轮未同步）</a> · <a href="https://eastern-wisdom-demo-fuyao.netlify.app/creator">创作者本人工作台</a> · <a href="https://eastern-wisdom-demo-fuyao.netlify.app/admin">公司内部总后台</a></p><p><a href="{DELIVERY}">当前功能交付记录</a> · <a href="{PREFLIGHT}">本次打包核验</a> · <a href="资料校验清单.csv">逐文件校验清单</a></p><p>历史压缩包、运行数据库、依赖和凭据不随包重复收录。下方带日期的旧说明仅作历史记录，当前状态以本节为准。</p></section>')
 if not checkpoint and not pending:
  section=html.fragment_fromstring(f'<section id="current-delivery-package"><h1>基础框架交付 · {now.strftime("%Y-%m-%d")}</h1><p>F01—F05已验收，源码、构建与原公网一致；AI接入暂缓，人工审核可用。</p><p><a href="05_后台与研发说明/基础框架阶段说明与验收.txt">本轮说明与数据归属</a> · <a href="{DELIVERY}">实际验证与发布记录</a> · <a href="交付包说明.txt">交付包说明</a> · <a href="https://eastern-wisdom-demo-fuyao.netlify.app/experience">公网APP</a></p><p>历史压缩包、运行数据库、依赖与凭据均排除。11月6日暂停资料仅供追溯。</p></section>')
 if pending:
  section=html.fragment_fromstring(f'<section id="current-delivery-package"><h1>基础框架本地验收 · 公网待续 · {now.strftime("%Y-%m-%d")}</h1><p>F01—F05已完成本地验收；本包源码为新构建，Sites后台v{pub["sites_version"]}已部署，Netlify额度HTTP403阻塞，前台仍为旧部署，本轮没有创建新Netlify部署。AI接入暂缓，人工审核可用。</p><p><a href="{DELIVERY}">本地验收与发布待续记录</a> · <a href="{pub["blocker_report"]}">实际阻塞核验</a> · <a href="05_后台与研发说明/基础框架阶段说明与验收.txt">本轮说明</a> · <a href="交付包说明.txt">交付包说明</a> · <a href="03_当前APP/发给负责人-东方智慧首页R4.html">本包新版离线界面</a> · <a href="https://eastern-wisdom-demo-fuyao.netlify.app/experience">Netlify前台（旧版）</a></p><p>公网同步尚未完成，不以旧公网验收替代新构建发布验证。11月6日暂停patch仅作历史追溯；运行数据库、凭据、依赖和旧压缩包不收录。</p></section>')
 if ui_revision:
  section=html.fragment_fromstring(f'<section id="current-delivery-package"><h1>{H.escape(revision_module)} · 交付包 · {now.strftime("%Y-%m-%d")}</h1><p>{H.escape(delivery["scope"])}</p><p>源码与本轮完整回归及五类当前专项绑定；当前界面尚未发布。已发布Sites v{pub["sites_version"]}不含本轮界面，Netlify仍为v14旧版，等待免费额度恢复。AI接入暂缓。</p><p><a href="{DELIVERY}">本轮实际交付记录</a> · <a href="{H.escape(guide,quote=True)}">当前模块使用说明</a> · <a href="交付包说明.txt">交付包说明</a> · <a href="03_当前APP/发给负责人-东方智慧首页R4.html">本包离线界面</a> · <a href="https://eastern-wisdom-demo-fuyao.netlify.app/experience">公网前台（旧版）</a></p><p>旧F05隔离恢复属于未改后端的历史证据，不冒充当前UI或生产恢复验收。旧压缩包、运行数据库、依赖和凭据不收录。</p></section>')
 if bazi_spacing_revision:
  section=html.fragment_fromstring(f'<section id="current-delivery-package"><h1>{H.escape(revision_module)} · 交付包</h1><p>{H.escape(delivery["scope"])}</p><p>Pages静态预览{"已更新并验收" if delivery["pages_preview"]["published"] else "待更新，线上仍为前一版本"}；Sites/Netlify和后台未更新。</p><p><a href="{DELIVERY}">本轮实际证据</a> · <a href="{H.escape(guide,quote=True)}">本轮说明</a> · <a href="{PAGES_URL}">纯APP静态预览</a></p><p>旧收据、冻结报告、ZIP保持历史时点，AI暂缓。</p></section>')
 main.insert(0,section)
 groups={}
 for rel in sorted(files):groups.setdefault(rel.split('/')[0] if '/' in rel else '项目入口与规则',[]).append(rel)
 for group,rows in sorted(groups.items()):
  detail=etree.SubElement(main,'details');etree.SubElement(detail,'summary').text=f'{group} · {len(rows)}项';ul=etree.SubElement(detail,'ul',{'class':'files'})
  for rel in rows:
   li=etree.SubElement(ul,'li',{'data-name':rel.lower()});etree.SubElement(li,'a',href=quote(rel,safe='/')).text=rel
 style=etree.SubElement(doc.xpath('//head')[0],'style');style.text='.files a{overflow-wrap:anywhere;min-width:0}.files li{display:block}'
 (ROOT/'打开这里.html').write_text('<!doctype html>\n'+etree.tostring(doc,encoding='unicode',method='html'),encoding='utf-8')
 files=collect_files();required={'AGENTS.md','打开这里.html','交付包说明.txt','先读我.txt',*SELF,PREFLIGHT,'03_当前APP/创作者中心.html','03_当前APP/东方智慧-首页体验R4.html','03_当前APP/计时后台-开发联调.html','03_当前APP/发给负责人-东方智慧首页R4.html','04_研发源码/app/r4/backend/requirements.txt','04_研发源码/app/r4/backend/initial-content.json','04_研发源码/app/cloud/.openai/hosting.json','04_研发源码/app/cloud/package-lock.json','04_研发源码/app/cloud/prepare.py','04_研发源码/app/cloud/prepare-netlify.mjs','04_研发源码/app/cloud/db/schema.ts',DELIVERY,'06_验证与后续工作/创作者APP功能对齐与数据中心交付记录.json'}
 required.update('04_研发源码/app/r4/'+n for n in ['life-chart-core.js','life-chart-bazi.js','life-chart-western.js','bazi-time.js','bazi-compare.js','bazi-glossary.js','life-charts.css','navigation-back.js','creator-center.html','creator-app.js','creator-admin.js','analytics-app.js','analytics-admin.js','life-birth-entry.js','backend/analytics.py'])
 required.update(['04_研发源码/app/r4/foundation-state.js','04_研发源码/app/r4/foundation-state.css','05_后台与研发说明/基础框架阶段交付与续接说明.txt','06_验证与后续工作/基础框架F03未完成改动.patch','06_验证与后续工作/F03暂停源码保存与稳定版核验.json','05_后台与研发说明/生命地图生辰入口说明.txt','05_后台与研发说明/创作者与APP功能对齐及后台数据中心说明.txt'])
 if not checkpoint:required.update(['05_后台与研发说明/基础框架阶段说明与验收.txt','06_验证与后续工作/基础框架F05契约与恢复核验.json'])
 if pending:required.add(pub['blocker_report'])
 if ui_revision:
  required.update('04_研发源码/app/r4/'+n for n in UI_SOURCES)
  required.update([guide,delivery['foundation_baseline']['report'],*[checks[n]['report'] for n in ['foundation','restore']]])
  required.update('06_验证与后续工作/'+file for file,count in UI_REPORTS.values())
  required.add('06_验证与后续工作/八字参考排版核验.cjs')
 if bazi_spacing_revision:
  required.update(delivery['source_sha256']);required.update(delivery['captures_sha256']);required.update([delivery['previous_real_western_revision']['report'],'06_验证与后续工作/记录八字表留白与字号交付.py','06_验证与后续工作/八字留白字号优化核验.cjs',delivery['spacing_baseline']['report']]);required.update(ref['report'] for ref in delivery['verification'].values())
  if delivery['pages_preview']['published']:required.add(delivery['pages_preview']['publication_record']['report'])
 if real_western_revision:
  required.update(delivery['source_sha256']);required.update([REAL_WESTERN_LEDGER,'06_验证与后续工作/记录真实星盘档案交付.py','06_验证与后续工作/记录真实星盘档案任务.py',delivery['previous_structure_revision']['report'],delivery['city_data_snapshot']['report'],delivery['city_data_snapshot']['runtime']['path'],delivery['city_data_snapshot']['notice']['path']]);required.update(ref['report'] for ref in delivery['verification'].values())
 if structure_revision:
  required.update(delivery['source_sha256']);required.update([STRUCTURE_LEDGER,'06_验证与后续工作/记录完整星盘交付.py','06_验证与后续工作/记录完整星盘任务.py',delivery['previous_reference_revision']['report']]);required.update(ref['report'] for ref in delivery['verification'].values())
 if reference_revision:
  required.update(delivery['source_sha256']);required.update([REFERENCE_LEDGER,'06_验证与后续工作/记录准了参考交付.py','06_验证与后续工作/记录准了参考任务.py',delivery['previous_document_revision']['report'],delivery['reference_module_ledger']['report']]);required.update(ref['report'] for ref in delivery['verification'].values())
 if document_revision:
  required.update(delivery['source_sha256']);required.update([DOCUMENT_LEDGER,'06_验证与后续工作/记录改动文档交付.py',delivery['previous_ui_revision']['report']]);required.update(ref['report'] for ref in delivery['verification'].values())
 required.update('04_研发源码/app/r4/vendor/'+n for n in ['iztro-2.6.2.min.js','iztro-LICENSE.txt','lunar-1.7.7.js','lunar-1.7.7-LICENSE.txt','astronomy-engine-2.1.19.min.js','astronomy-engine-LICENSE.txt','opencc-cn2t-1.0.5.js','opencc-LICENSE.txt','opencc-data-LICENSE.txt','NotoSerifTibetan.woff2','NotoSerifTibetan-OFL.txt'])
 required.update('04_研发源码/app/cloud/lib/'+n for n in ['eastern-api.ts','creator-api.ts','analytics-api.ts'])
 required.update('04_研发源码/app/cloud/generated/'+n for n in ['experience.html','creator.html','admin.html','review.html','seed.json']);need(required<=set(files),'Missing required payload: '+str(required-set(files)))
 for entry in ['打开这里.html','改动任务表-2026-10-22.html']:
  for value in html.fromstring((ROOT/entry).read_text(encoding='utf-8')).xpath('//@href|//@src'):
   u=urlsplit(value)
   if u.scheme or u.netloc:continue
   rel=unquote(u.path) or entry;need(rel in files,'Missing/excluded package link: '+value)
   if u.fragment and Path(rel).suffix=='.html':need(html.fromstring(files[rel].read_text(encoding='utf-8')).xpath('//*[@id=$anchor]',anchor=unquote(u.fragment)),'Missing anchor: '+value)
 private=set()
 def secrets(value):
  if isinstance(value,dict):
   for key,v in value.items():
    if isinstance(v,str) and re.search(r'password|secret|token|private.?key',key,re.I) and len(v)>=6:private.add(v.encode())
    elif isinstance(v,(dict,list)):secrets(v)
  elif isinstance(value,list):
   for v in value:secrets(v)
 for p in list(CLOUD.glob('.env*'))+list(CLOUD.glob('.dev.vars*')):
  if not p.is_file() or unsafe(p):continue
  text=p.read_text(encoding='utf-8-sig')
  try:secrets(json.loads(text))
  except ValueError:
   for line in text.splitlines():
    m=re.match(r'\s*([A-Za-z_][\w.-]*)\s*[:=]\s*(.*?)\s*$',line)
    if m and re.search(r'password|secret|token|private.?key|api.?key',m[1],re.I):
     v=m[2].strip().strip('"').strip("'")
     if len(v)>=6:private.add(v.encode())
 manifest=[]
 for rel,p in sorted(files.items()):
  data=p.read_bytes();scan=credential_scan_bytes(data)
  textual=p.suffix.lower() in {'.txt','.md','.json','.html','.js','.py','.css','.csv','.ts','.tsx','.mjs','.cjs','.toml','.yaml','.yml','.ini','.cmd','.bat','.ps1','.lock','.sh','.sql','.svg','.patch'} or p.name in {'.npmrc','.gitignore'} or data.startswith(b'\x89PNG')
  for secret in private:
   hit=(secret in scan if len(secret)>=12 else bool(re.search(rb'(?<![A-Za-z0-9_])'+re.escape(secret)+rb'(?![A-Za-z0-9_])',scan))) if textual else (secret in scan if len(secret)>=12 else any(q+secret+q in scan for q in [b'"',b"'"]))
   need(not hit,'Private runtime value in included file: '+rel)
  need(not re.search(rb'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----',data),'Private key in '+rel)
  if p.name=='.npmrc':need(not re.search(rb'(?m)^\s*(?:[^\n]*:)?(?:_authToken|_password|_auth)\s*=',data),'Authenticated npm config in '+rel)
  if rel not in SELF:manifest.append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 out=io.StringIO(newline='');w=csv.writer(out);w.writerow(['包内相对位置','字节数','SHA-256']);w.writerows((x['path'],x['bytes'],x['sha256']) for x in manifest);(ROOT/'资料校验清单.csv').write_bytes(out.getvalue().encode('utf-8-sig'))
 origin=read('原始来源与文件校验.json');origin['files']=manifest;origin['current_revision']={'updated_beijing':now.isoformat(),'scope':delivery['scope'],'paused_by_user':checkpoint,'all_planned_work_complete':not (checkpoint or pending),'sites_status':pub.get('sites_status'),'netlify_status':pub.get('netlify_status'),'public_deployment_pending':pub.get('public_deployment_pending',False),'delivery_record':DELIVERY,'app_build_sha256':app_hash};origin['delivery_filter']={'packaged_at':now.isoformat(),'archive_name':target.name,'historical_zips_excluded':True,'private_runtime_excluded':True,'no_wrapper':True,'manifest_scope':'Exact ZIP payload except two self manifests','final_zip_result_outside_payload':REPORT};origin['manifest_excludes']=[*sorted(SELF),REPORT,'Archives, dependencies, DB/sidecars/backups, credentials, caches and system files'];write('原始来源与文件校验.json',origin)
 payload={rel:{'bytes':p.stat().st_size,'sha256':digest(p)} for rel,p in sorted(files.items())}
 print(f'准备压缩{len(payload)}个文件；入口链接、运行值检查已通过，根目录无额外包装层。',flush=True)
 with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False) as z:
  for rel,p in sorted(files.items()):z.write(p,rel)
 print('压缩完成，正在验证CRC及全部文件大小/SHA-256。',flush=True)
 with zipfile.ZipFile(target) as z:
  need(z.testzip() is None,'CRC failure');names=z.namelist();need(len(names)==len(set(names)) and set(names)==set(payload),'Entry set differs')
  for rel in names:
   need(not rel.startswith(('/','\\')) and '..' not in Path(rel).parts and not any(x.lower() in SKIP_DIRS for x in Path(rel).parts),'Unsafe ZIP path')
   data=z.read(rel);need(len(data)==payload[rel]['bytes'] and hashlib.sha256(data).hexdigest()==payload[rel]['sha256'],'ZIP byte mismatch: '+rel);need(digest(files[rel])==payload[rel]['sha256'],'Workspace changed while packing: '+rel)
  need(json.loads(z.read('原始来源与文件校验.json'))['files']==manifest,'Embedded manifest differs');rows=list(csv.DictReader(io.StringIO(z.read('资料校验清单.csv').decode('utf-8-sig'))));need(len(rows)==len(manifest) and all(y['包内相对位置']==x['path'] and int(y['字节数'])==x['bytes'] and y['SHA-256']==x['sha256'] for x,y in zip(manifest,rows)),'CSV and JSON differ')
 result={'packaged_at':now.isoformat(),'project_archive':str(target),'bytes':target.stat().st_size,'verified_files':len(payload),'manifest_files':len(manifest),'archive_entries':len(payload),'sha256':digest(target),'crc_pass':True,'all_file_hashes_pass':True,'source_and_build_match':True,'entry_links_pass':True,'no_wrapper':True,'private_runtime_excluded':True,'private_runtime_values_checked':len(private),'private_scan_policy':'Runtime files excluded; text and PNG metadata scanned for literal values with word boundaries for short values; short values in binary font/media data require quoted string boundaries','project_only':True,'paused_by_user':checkpoint,'all_planned_work_complete':not (checkpoint or pending),'sites_status':pub.get('sites_status'),'netlify_status':pub.get('netlify_status'),'complete_modules':['F01','F02'] if checkpoint else ['F01','F02','F03','F04','F05'],'public_deployment_pending':pub.get('public_deployment_pending',False),'package_matches_public':not pub.get('public_deployment_pending',False),'delivery_record':DELIVERY,'app_build_sha256':app_hash,'sites_version':pub['sites_version'],'netlify_deploy_id':pub['netlify_deploy_id'],'tested_build_module':checks['local']['module'],'tested_build_at':checks['local']['at'],'preflight_report':PREFLIGHT,'preflight_report_sha256':digest(ROOT/PREFLIGHT),'scope':'Packaging and byte consistency checks only; no business-code changes, new functional regression or deployment. Final ZIP result intentionally outside payload.'};write(REPORT,result);print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
