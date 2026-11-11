"""Record the final document revision only after current gates; never build, test, deploy or ZIP."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote, urlsplit
import copy
import csv
import hashlib
import importlib.util
import io
import json
import math
import re
import sys
from lxml import html, etree

ROOT = Path(__file__).resolve().parent.parent
Q = ROOT / '06_验证与后续工作'
R4 = ROOT / '04_研发源码/app/r4'
OLD_UI = '06_验证与后续工作/原创命盘表达交付记录.json'
RECORD = '06_验证与后续工作/改动文档交付记录.json'
GUIDE = '05_后台与研发说明/改动文档实施与验收说明.txt'
GALLERY = '06_验证与后续工作/原创命盘效果查看.html'
MODULE = '改动文档M5-展开控件统一'
LEDGER = '06_验证与后续工作/改动文档实施记录.json'
MODULE_TASKS = {'M1':['D01','D02'],'M2':['D03'],'M3':['D04'],'M4':['D05'],'M5':['D06']}
FIXED_VENDOR = {
 'astronomy-engine-2.1.19.min.js':'f41139a87941ea017ab902b954c9389fa27ea72083d7fab4971756d7769d14e6',
 'astronomy-engine-LICENSE.txt':'690dd98cb13ba4db77c6327deea852a816892bb9debbad5943405c66972f8023',
 'iztro-2.6.2.min.js':'1a3c2e19e266feac498982423636131b7ae24226fc1bc7bf5e3a25286a78c5fb',
 'iztro-LICENSE.txt':'e6c7b6e313cbda3135b41bccc66c98be132cb8319d0d465903d17e669e748b36',
 'lunar-1.7.7.js':'9750324bfe1aa63c146f8c72b1143df924466c11c8a5277d7d9225c541a18aaa',
 'lunar-1.7.7-LICENSE.txt':'d9210caf1844dcf410095cea464b79800aad30dbd49df092076b9f0ddc015404',
 'NotoSerifTibetan-OFL.txt':'0077789fc3cb20f358278ba4c6437eb14ade97d4d3e3281eaa42853efcd9dc8b',
 'NotoSerifTibetan.ttf':'060ec022b04c306de3f58d051fb0e1cf81a5b610c5910fbfc43bba154c057cda',
 'NotoSerifTibetan.woff2':'539ab699f3f2d3844122f9d121f1812c74b51b034da2ccfcc8eaf8c978f72f1b',
 'opencc-cn2t-1.0.5.js':'6f8dc5cf43d72930a0449bde3e905c477601177165c11750dc44be853ff82fec',
 'opencc-data-LICENSE.txt':'b534e465949558eec2597b04f5092b5e161236a68dfbfd04d547592ac3964308',
 'opencc-LICENSE.txt':'960f7fc16d8baa126802316a7df9078a383af4fb6bc60033adb28e85c08d5e5e',
 'source.json':'883e8ca8b67e0e6f5e6fa8c04a261c9c81991751f8a93851706a71287a0d111c'
}
SPECIALTIES = {'birth':('出生资料地域移除核验-本机.json',8),'charts':('三盘实际排盘联调.json',14),'expression':('原创命盘交互核验.json',15),'layout':('页面长度与日间命盘优化核验.json',16),'bazi_reference':('八字参考排版核验.json',12)}
SCOPE = '用户改动文档六项要求按M1—M5完成本地实施与验收：首页卡片和三个快捷入口；三盘独立及真实地心/全天范围星盘；紫微日间白底；八字真实档案流运、十二类有依据神煞与删除关系；展开控件统一。原计算、档案、笔记、计时、三地图4/4/3及四语保留。未发布、未新打包、旧ZIP未改，AI继续暂缓。'

def need(ok, message):
    if not ok:
        raise AssertionError(message)

def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))

def sha(relative):
    with (ROOT / relative).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def latest(relative):
    data = read(relative)
    return data.get('latest', data)

def packager_module():
    spec = importlib.util.spec_from_file_location('document_delivery_packager', Q / '打包当前交付.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    return package

def safe_file(relative, package):
    need(isinstance(relative,str) and relative and not Path(relative).is_absolute(), 'Expected a project-relative file: '+str(relative))
    path = (ROOT / relative).resolve()
    need(path.is_relative_to(ROOT.resolve()) and path.is_file() and not package.unsafe(path), 'File missing or outside project: '+relative)
    return path

def current_run(path, minimum, app_hash, package):
    run = latest(path)
    need(run.get('pass') is True and run.get('failed')==0 and run.get('passed',0)>=minimum and run.get('module')==MODULE, 'Current M5 acceptance missing: '+path)
    need(package.report_app(run)==app_hash, 'Current M5 APP differs: '+path)
    need(run.get('sourceHashes'), 'Current specialty lacks source identity: '+path)
    for rel,value in run['sourceHashes'].items():
        safe_file(rel,package)
        need(sha(rel)==value, 'Current specialty source differs: '+rel)
    for folder,key in [('03_当前APP','buildHashes'),('04_研发源码/app/cloud','cloudBuildHashes')]:
        for rel,value in run.get(key,{}).items():
            full=folder+'/'+rel
            safe_file(full,package)
            need(sha(full)==value, 'Current specialty build differs: '+full)
    return run, {'report':path,'sha256':sha(path),'at':run['at'],'module':MODULE,'passed':run['passed']}

def length_summary(run):
    rows=run.get('measurements',[])
    comparisons=run.get('beforeAfterMeasures') or run.get('comparison') or []
    keys=[(row['id'],row.get('variant','default')) for row in rows]
    need(rows and len(keys)==len(set(keys)) and len(comparisons)==len(rows), 'Current measured routes missing or duplicated')
    for item in comparisons:
        row=next((r for r in rows if r['id']==item['id'] and r.get('variant','default')==item.get('variant','default')),None)
        need(row and item.get('afterScroll')==row['scrollDistance'] and item.get('afterScreens')==row['screens'], 'After measurement differs from current rows')
        need(row.get('documentOverflow') is False, 'Measured page has document overflow')
        for key in ['scrollDistance','scrollHeight','clientHeight']:
            need(isinstance(row[key],(int,float)) and not isinstance(row[key],bool) and math.isfinite(row[key]) and row[key]>=0, 'Invalid measured length')
        if item.get('baselineAvailable') is False:
            need(all(key in item and item[key] is None for key in ['beforeScroll','beforeScreens','reduction']), 'Missing baseline has invented prior values')
    mobile=next(row for row in rows if row['id']=='classicsWisdom' and row.get('variant','default')=='default')
    desktop=next(row for row in rows if row['id']=='classicsWisdom' and row.get('variant')=='desktop-958x676')
    need(mobile['scrollDistance']<=150 and desktop['scrollDistance']<=240, 'Current Ba Zi length budget failed')
    missing=sum(row.get('baselineAvailable') is False for row in comparisons)
    return '八字默认额外滚动实测：390×844为'+str(mobile['scrollDistance'])+'px，958×676为'+str(desktop['scrollDistance'])+'px。'+('其中'+str(missing)+'项没有同构建旧测量，不计算缩短比例。' if missing else '对照仅对应报告绑定的真实历史测量。')+'主动展开资料仍可滚动。'

def captures_from(runs, package):
    captures={}
    for run in runs:
        for item in [*run.get('captures',[]),*run.get('screenshots',[])]:
            name=item.get('file') if isinstance(item,dict) else item
            need(isinstance(name,str) and name, 'Malformed current screenshot')
            rel=name if name.startswith('06_验证与后续工作/') else '06_验证与后续工作/'+name
            path=safe_file(rel,package)
            need(path.is_relative_to(Q.resolve()) and path.suffix.lower()=='.png' and path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid current PNG: '+rel)
            captures[rel]=sha(rel)
    need(captures, 'Current-build screenshots absent')
    return captures

def prepare_delivery():
    package=packager_module()
    old=read(OLD_UI)
    need(old.get('pass') is True and old.get('ui_revision') is True, 'Previous immutable UI receipt missing')
    need(sha(old['foundation_baseline']['report'])==old['foundation_baseline']['sha256'], 'Original foundation baseline changed')
    app_hash=sha('03_当前APP/东方智慧-首页体验R4.html')
    stamp=datetime.now(timezone(timedelta(hours=8))).isoformat()
    full={}
    for key,name in [('local','本轮全量回归结果.json'),('cloudflare','公网适配全量回归结果.json')]:
        rel='06_验证与后续工作/'+name
        run=latest(rel)
        need(run.get('pass') is True and run.get('failed')==0 and run.get('passed',0)>=60 and run.get('module')==MODULE and package.report_app(run)==app_hash, 'Current M5 full regression missing: '+key)
        need(run.get('buildHashes') and (key!='cloudflare' or run.get('cloudBuildHashes')), 'Full regression build identity missing')
        for folder,field in [('03_当前APP','buildHashes'),('04_研发源码/app/cloud','cloudBuildHashes')]:
            for path,value in run.get(field,{}).items():
                safe_file(folder+'/'+path,package)
                need(sha(folder+'/'+path)==value, 'Full regression build differs: '+path)
        full[key]={'report':rel,'sha256':sha(rel),'at':run['at'],'module':MODULE,'passed':run['passed']}
    verification,runs={},{}
    for key,(name,count) in SPECIALTIES.items():
        runs[key],verification[key]=current_run('06_验证与后续工作/'+name,count,app_hash,package)
    ledger=read(LEDGER)
    for key,tasks in MODULE_TASKS.items():
        need(ledger['modules'].get(key,{}).get('tasks')==tasks, 'Six requirements are not mapped to five expected modules')
    need(sha(ledger['source'])==ledger['source_sha256'], 'User source document differs from ledger')
    record=copy.deepcopy(old)
    record.update({'checked_beijing':stamp,'pass':True,'scope':SCOPE,'ui_revision':True,'document_revision':True,'revision_module':MODULE,'guide':GUIDE,'preview_html':GALLERY,'app_build_sha256':app_hash,'local_scope_complete':True,'document_local_scope_complete':True,'all_planned_work_complete':False,'paused_by_user':False,'complete_document_modules':list(MODULE_TASKS),'document_module_ledger':{'report':LEDGER,'sha256':sha(LEDGER),'modules':copy.deepcopy(ledger['modules'])},'current_full':full,'verification':verification,'previous_ui_revision':{'report':OLD_UI,'sha256':sha(OLD_UI),'app_build_sha256':old['app_build_sha256'],'scope':'Original immutable receipt. Previous UI build identities are historical, not compared with the current APP.'},'zip_repacked':False,'production_writes':False,'deployment_attempted_this_revision':False,'visual_approved_by_user':False})
    checks,historical={},{}
    package.historical_foundation(record,checks,historical)
    package.document_modules(record,checks)
    smokes=[ref for ref in ledger['modules']['M5']['reports'] if '冒烟' in Path(ref['path']).name]
    need(smokes, 'Actual final M5 smoke missing')
    smoke_path=next((ref['path'] for ref in smokes if '本机' in Path(ref['path']).name),smokes[0]['path'])
    need(latest(smoke_path).get('productionWrites') is False, 'Final M5 smoke must be isolated')
    runs['document_smoke'],record['verification']['document_smoke']=current_run(smoke_path,1,app_hash,package)
    length=length_summary(runs['layout'])
    record['layout_measurement']={'report':verification['layout']['report'],'at':runs['layout']['at'],'viewport':runs['layout']['viewport'],'baseline':runs['layout'].get('baseline'),'comparison':runs['layout'].get('beforeAfterMeasures') or runs['layout'].get('comparison'),'summary':length}
    available=package.collect_files()
    sources=set(old['source_sha256'])
    for rel in available:
        pure=Path(rel)
        if rel.startswith('04_研发源码/app/r4/'):
            tail=pure.parts[3:]
            if len(tail)==1 or tail and tail[0] in {'backend','vendor'}:
                sources.add(rel)
        elif rel.startswith('04_研发源码/app/cloud/') and '/generated/' not in rel:
            if pure.suffix.lower() in {'.py','.js','.mjs','.cjs','.ts','.tsx','.css','.html','.json','.toml','.sql','.txt','.md'}:
                sources.add(rel)
    for run in runs.values():
        sources.update(run.get('sourceHashes',{}))
    sources.update(['06_验证与后续工作/记录改动文档交付.py','06_验证与后续工作/打包当前交付.py'])
    for name,value in FIXED_VENDOR.items():
        rel='04_研发源码/app/r4/vendor/'+name
        need(sha(rel)==value, 'Fixed vendor changed: '+name)
        sources.add(rel)
    for rel in sources:
        safe_file(rel,package)
        need(rel in available, 'Excluded runtime/private source: '+rel)
    record['source_sha256']={rel:sha(rel) for rel in sorted(sources)}
    record['vendored_fixed_sha256']={'04_研发源码/app/r4/vendor/'+name:value for name,value in FIXED_VENDOR.items()}
    inputs=package.build_inputs()
    record['embedded_sources']=['04_研发源码/app/r4/'+name for name in inputs]
    app=(ROOT/'03_当前APP/东方智慧-首页体验R4.html').read_text(encoding='utf-8')
    for name in inputs:
        need(package.embedded_text(name) in app, 'APP does not embed actual input: '+name)
    need(len(old['build_sha256'])==11, 'Expected eleven 03/Cloud build paths')
    record['build_sha256']={rel:sha(rel) for rel in old['build_sha256']}
    need((ROOT/'03_当前APP/创作者中心.html').read_bytes()==(R4/'creator-center.html').read_bytes(), 'Creator standalone mismatch')
    review=(ROOT/'03_当前APP/发给负责人-东方智慧首页R4.html').read_text(encoding='utf-8')
    embedded,_=json.JSONDecoder().raw_decode(review.split('const APP=',1)[1])
    need(embedded.replace('__INITIAL__','{}')==app, 'Review page embeds another APP')
    historical_keys=['checked_beijing','scope','revision_module','app_build_sha256','source_sha256','build_sha256','current_full','verification','layout_measurement','previous_zip','zip_repacked']
    record['previous_revisions']=[*copy.deepcopy(old.get('previous_revisions',[])),{key:copy.deepcopy(old[key]) for key in historical_keys}]
    record['publication'].update({'current_source_published':False,'current_chart_ui_published':False,'public_deployment_pending':True,'package_matches_public':False,'all_public_entry_points_current':False,'scope':'用户改动文档M1—M5仅本地完成，Sites v15/Netlify v14仍为旧公网。用户暂不处理托管或飞书，不发版、不重试、不监测、不购买。'})
    record['current_source_published']=False
    protected=[rel for rel in old['source_sha256'] if '/backend/' in rel or '/cloud/lib/' in rel or '/cloud/worker/' in rel]
    need(all(sha(rel)==old['source_sha256'][rel] for rel in protected), 'Backend changed; original recovery evidence cannot be reused')
    record['unchanged_backend_sha256']={rel:sha(rel) for rel in protected}
    prior_package=read('06_验证与后续工作/最新打包校验结果.json')
    zip_name=Path(prior_package['project_archive']).name
    need(Path(zip_name).suffix.lower()=='.zip' and sha(zip_name)==prior_package['sha256'], 'Earlier delivered ZIP changed')
    need(prior_package['app_build_sha256']==old['app_build_sha256'], 'Earlier delivered package does not match immutable UI receipt')
    record['previous_zip']={'path':zip_name,'sha256':prior_package['sha256'],'app_build_sha256':prior_package['app_build_sha256'],'unchanged':True}
    record['captures_sha256']=captures_from(list(runs.values()),package)
    record['limits']=['日间配色视觉仍待用户评价，测试通过不等于最终视觉认可。','未知时间星盘是当天25个整点边界样本的全天范围，不伪造精确盘/ASC/宫位；紫微/八字未知时刻不造盘。','藏文首页存在真实额外滚动，不称全语首屏；主动展开资料可以继续滚动。','本机个人资料不是完整跨设备同步或自动补传。','旧F05隔离SQLite/本地D1恢复只是未改后端的历史证据，不代表生产恢复、原生实机或AI/支付/硬件接通。','本轮本地完成，未更新公网、未修改旧ZIP、未生成新包；托管/飞书暂缓。']
    counts='Python 完整回归'+str(full['local']['passed'])+'项通过、0项失败，本地 Cloud 完整回归'+str(full['cloudflare']['passed'])+'项通过、0项失败；出生、三盘、交互、长度、八字专项分别'+'/'.join(str(verification[key]['passed']) for key in SPECIALTIES)+'项，M5冒烟'+str(record['verification']['document_smoke']['passed'])+'项通过。详细批次见交付记录。'
    return package,record,counts,length

def updated_block(relative,content,as_html=False):
    body=(ROOT/relative).read_text(encoding='utf-8-sig')
    for key in ['document-feedback-delivery','original-chart-expression']:
        body=re.sub(r'<!-- '+re.escape(key)+r':start -->[\s\S]*?<!-- '+re.escape(key)+r':end -->\s*','',body)
    marker='<!-- document-feedback-delivery:start -->\n'+content+'\n<!-- document-feedback-delivery:end -->\n'
    if as_html:
        document=html.fromstring(body)
        for element in document.xpath('//*[@id="current-delivery-package"]'):
            element.getparent().remove(element)
        for link in document.xpath('//a[@href]'):
            value=urlsplit(link.get('href'))
            if not(value.scheme or value.netloc) and Path(unquote(value.path)).suffix.lower() in {'.zip','.7z','.rar','.tar','.gz','.tgz'}:
                link.drop_tag()
        body='<!doctype html>\n'+etree.tostring(document,encoding='unicode',method='html')
        need(re.search(r'<main\b',body), 'Expected existing root main entry')
        return re.sub(r'(<main\b[^>]*>)',lambda m:m[1]+'\n'+marker,body,count=1)
    if relative=='先读我.txt':
        body=re.sub(r'【当前完整打包状态】[\s\S]*?【当前完整打包状态结束】\s*','',body,count=1)
    return marker+'\n以下为此前阶段历史说明，不代表本轮源码已发布或已重新打包。\n\n'+body

def planned_outputs(record,counts,length):
    esc=lambda value:__import__('html').escape(str(value),quote=True)
    guide='''东方智慧APP · 改动文档实施与验收说明
用户《改动.docx》的六项要求按M1—M5逐模块完成本地实施和验收。

M1：首页移除独立“一分钟，回到呼吸”板块，每日智慧卡片移到该位置；快捷入口只保留其余三个，去掉重复智慧课程/冥想音乐入口。
M2：紫微、八字、星盘各自独立，只展示对应模块。有准确时刻而无坐标时展示真实地心十天体及相位图，不猜ASC或宫位；未知时刻为当天25个整点边界样本的全天范围，不把中午或零点当精确出生时刻。旧完整星盘按原档案复算。
M3：紫微日间纯白及清楚文字层级，夜间保留；颜色舒适程度仍待用户视觉评价。
M4：档案与流运取当前实际保存的生辰和固定lunar1.7.7结果；八字为档案/流运/神煞三页，关系页与关系组合计算删除。十二类已收录神煞逐项查看锚点和原文来源，国印/金舆明确按本命年干，不混日干表，不冒称引擎原生完整神煞API。更多中可真实展开完整七列对照及三运概览；原本命字段、词典、辅助/小运、笔记、保存/导出与复算保留。
M5：展开/收起统一控件与状态；以实际键盘、焦点及原生内容操作验收，不以装饰或不可达隐藏DOM冒充功能。

资料与边界
必须本人先保存生日及性别；称呼和准确时间选填。保留出生四字段，不恢复地域输入。紫微/八字未知时间不造精确盘；西盘全天范围也不生成猜测的宫位/ASC。三地图4/4/3、真实计时、成熟创作者及真实数据中心保留，AI继续暂缓。
藏文首页存在真实额外滚动，不能说全部语言都一屏；展开完整资料后继续滚动正常。藏文仍待母语审校。
生辰、排盘与笔记仍按本浏览器账号保存，不代表完整跨设备同步或自动补传。
F01—F05及旧F05隔离SQLite/本地D1恢复保留原证据，本轮核后端未改，不冒充生产恢复、AI/支付/硬件或原生实机验收。

本轮只本地完成。Sites v15/Netlify v14没有本轮改动；托管、飞书暂不处理，不发布、不监测、不购买。旧ZIP和原原创receipt只读保护，本轮未生成或覆盖压缩包。
打开这里.html是当前入口。现有8880互动预览与8879静态资料服务为用户保留；接收方依启动脚本自行运行和创建管理员，不携带原账号/凭据。
'''
    guide+='\n实际验收：\n'+counts+'\n'+length+'\nAPP SHA-256：'+record['app_build_sha256']+'\n交付记录：'+RECORD+'\n阶段记录：'+LEDGER+'\n'
    links='<p><a href="'+GUIDE+'">本轮六项改动与说明</a> · <a href="'+RECORD+'">实际交付证据</a> · <a href="'+LEDGER+'">五模块台账</a> · <a href="'+GALLERY+'">当前效果图</a> · <a href="03_当前APP/发给负责人-东方智慧首页R4.html">离线APP</a></p>'
    section='<section id="document-feedback-delivery"><h2>用户改动文档 · M1—M5本地验收</h2><p>'+esc(SCOPE)+'</p><p>'+esc(counts)+'</p><p>'+esc(length)+'</p><p>未知西盘仅25样本全天范围，紫微/八字未知不造精确盘。日间视觉待评价，藏文首页允许真实滚动。本轮未发布、未新打包，旧ZIP保持原快照。</p>'+links+'</section>'
    gallery='<!doctype html><html lang="zh-Hans"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>改动文档 · 当前效果</title><style>body{margin:0;background:#f7f5ef;color:#25323b;font:15px/1.8 sans-serif}main{max-width:1050px;margin:auto;padding:24px}a{color:#866019}figure{margin:24px 0}img{display:block;width:100%;max-width:430px;height:auto;border:1px solid #aaa}figcaption{overflow-wrap:anywhere}</style><main><h1>用户改动文档 · 当前构建效果</h1><p>'+esc(SCOPE)+'</p><p>'+esc(counts)+'</p><p>'+esc(length)+'</p><p>合成资料截图仅作验收，不是业务默认或用户本人档案。截图取自当前通过报告；视觉仍待用户评价，未发布、未打包。</p><p><a href="../'+GUIDE+'">说明</a> · <a href="改动文档交付记录.json">证据</a></p>'
    for relative in record['captures_sha256']:
        name=Path(relative).relative_to(Path('06_验证与后续工作')).as_posix()
        gallery+='<figure><figcaption>'+esc(Path(name).stem)+'</figcaption><a href="'+esc(name)+'"><img loading="lazy" src="'+esc(name)+'" alt="'+esc(Path(name).stem)+'"></a></figure>'
    gallery+='</main></html>'
    notice=record['checked_beijing']+'\n'+SCOPE+'\n'+counts+'\n'+length+'\n说明：'+GUIDE+'\n证据：'+RECORD+'；台账：'+LEDGER+'\n旧ZIP仍为原快照，未生成新包；旧公网不含本轮改动。视觉待评价，藏文首页并非全部首屏。\n'
    outputs={GUIDE:guide,GALLERY:gallery,RECORD:json.dumps(record,ensure_ascii=False,indent=2)+'\n'}
    for relative in ['打开这里.html','改动任务表-2026-10-22.html']:
        outputs[relative]=updated_block(relative,section,True)
    for relative in ['先读我.txt','交付包说明.txt']:
        outputs[relative]=updated_block(relative,notice)
    agents=(ROOT/'AGENTS.md').read_text(encoding='utf-8-sig')
    agents=re.sub(r'<!-- document-feedback-final-verified:start -->[\s\S]*?<!-- document-feedback-final-verified:end -->\s*','',agents)
    agents+='\n\n<!-- document-feedback-final-verified:start -->\n### '+record['checked_beijing'][:10]+' 用户改动文档五模块本地验收\n'+SCOPE+'\n'+counts+'\n未知西盘为25样本全天范围；紫微/八字未知不造精确盘。日间视觉仍待评价，藏文首页存在真实额外滚动，不称全语首屏。旧ZIP/旧receipt保护，公网未更新。当前证据：'+RECORD+'，说明：'+GUIDE+'。\n<!-- document-feedback-final-verified:end -->\n'
    outputs['AGENTS.md']=agents
    return outputs

def validate_output_links(outputs,package):
    available=package.collect_files()
    for relative,text in outputs.items():
        target=(ROOT/relative).resolve()
        need(target.is_relative_to(ROOT.resolve()) and not target.is_symlink(), 'Unsafe output path')
        if not relative.endswith('.html'):
            continue
        document=html.fromstring(text)
        for value in document.xpath('//@href|//@src'):
            url=urlsplit(value)
            if url.scheme or url.netloc:
                continue
            path=((ROOT/relative).parent/unquote(url.path)).resolve() if url.path else (ROOT/relative).resolve()
            need(path.is_relative_to(ROOT.resolve()), 'Output link outside project: '+value)
            rel=path.relative_to(ROOT).as_posix()
            need(rel in outputs or rel in available, 'Output link missing/excluded: '+value)
            if url.fragment and Path(rel).suffix=='.html':
                body=outputs.get(rel) or path.read_text(encoding='utf-8-sig')
                need(html.fromstring(body).xpath('//*[@id=$anchor]',anchor=unquote(url.fragment)), 'Missing output anchor: '+value)

def refresh_manifests(package,record):
    files=[{'path':rel,'bytes':path.stat().st_size,'sha256':sha(rel)} for rel,path in sorted(package.collect_files().items()) if rel not in package.SELF]
    inventory=read('原始来源与文件校验.json')
    inventory['files']=files
    inventory['current_revision']={'updated_beijing':record['checked_beijing'],'scope':record['scope'],'delivery_record':RECORD,'app_build_sha256':record['app_build_sha256'],'local_scope_complete':True,'public_deployment_pending':True,'zip_repacked':False,'document_module_ledger':LEDGER}
    inventory['delivery_filter']={'manifest_scope':'Current authored project except two self manifests; no ZIP generated','private_runtime_excluded':True,'historical_zips_excluded':True,'no_wrapper':True,'zip_repacked':False}
    (ROOT/'原始来源与文件校验.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    out=io.StringIO(newline='')
    writer=csv.writer(out)
    writer.writerow(['包内相对位置','字节数','SHA-256'])
    writer.writerows((row['path'],row['bytes'],row['sha256']) for row in files)
    (ROOT/'资料校验清单.csv').write_text(out.getvalue(),encoding='utf-8-sig',newline='')
    for row in files:
        need((ROOT/row['path']).stat().st_size==row['bytes'] and sha(row['path'])==row['sha256'], 'Workspace changed during manifests: '+row['path'])
    return len(files)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    package,record,counts,length=prepare_delivery()
    outputs=planned_outputs(record,counts,length)
    validate_output_links(outputs,package)
    # Every acceptance/identity/archive/output-link gate completes before the first write.
    if '--validate-only' in sys.argv:
        print(json.dumps({'pass':True,'read_only':True,'module':MODULE,'app_build_sha256':record['app_build_sha256'],'source_count':len(record['source_sha256']),'build_count':len(record['build_sha256']),'scope':'Preparation only; no receipt, document, manifest, ZIP or publication writes.'},ensure_ascii=False))
        return
    for relative,text in outputs.items():
        (ROOT/relative).write_text(text,encoding='utf-8')
    count=refresh_manifests(package,record)
    need(sha(OLD_UI)==record['previous_ui_revision']['sha256'] and sha(record['previous_zip']['path'])==record['previous_zip']['sha256'], 'Historical receipt or ZIP changed')
    print(json.dumps({'pass':True,'record':RECORD,'module':MODULE,'app_build_sha256':record['app_build_sha256'],'sources':len(record['source_sha256']),'builds':len(record['build_sha256']),'manifest_files':count,'deployed':False,'zip_repacked':False},ensure_ascii=False))

if __name__=='__main__':
    main()

