from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re,hashlib
root=Path(__file__).resolve().parent.parent
qa=root/'06_验证与后续工作'
now=datetime.now(ZoneInfo('Asia/Shanghai'))
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
reports={name:read(qa/file) for name,file in {
'local':'本轮全量回归结果.json','cloud':'Netlify适配全量回归结果.json','gateway':'Netlify网关回归结果.json','language':'四语专项联调.json','public':'四语公网验收.json','admin':'四语公网后台核验.json','catalog':'四语字典与字体校验.json','pages':'四语页面扫描.json'}.items()}
assert reports['local']['latest']['pass'] and reports['cloud']['latest']['pass']
for name in ['gateway','language','public','admin']: assert reports[name]['pass']
for key in ['missing','placeholderMismatches','missingTibetanGlyphs','unexpectedMarkup']: assert not reports['catalog'][key]
assert not reports['pages']['errors'] and not reports['pages']['missing'] and not reports['pages']['residuals']
assert not any(p.get('error') or p.get('overflow') for p in reports['pages']['pages'])
identity_file=root/'05_后台与研发说明/Netlify站点身份.json'
identity=read(identity_file)
identity.update(deploy_id='6ae86574436a9c3518edaa5e',checked_at=now.isoformat(),languages=['zh-Hans','zh-Hant','en','bo'],language_quality='藏文为 AI 初译与术语/界面修订版本，尚待母语审校')
write(identity_file,identity)
record={
'updated_beijing':now.isoformat(),'url':identity['url'],'site_id':identity['site_id'],'deploy_id':identity['deploy_id'],
'languages':['简体中文','繁體中文','English','བོད་ཡིག'],
'source':'04_研发源码/app/r4','outputs':'03_当前APP',
'checks':{'local_full':reports['local']['latest']['passed'],'netlify_full':reports['cloud']['latest']['passed'],'gateway':len(reports['gateway']['checks']),'local_language':len(reports['language']['results']),'public_language':len(reports['public']['results']),'public_admin_fields':len(reports['admin']['fields']),'rendered_pages_and_languages':len(reports['pages']['pages']),'catalog':reports['catalog']},
'backup':'07_历史版本仅供追溯/四语改动前源码-20261102.zip',
'limits':['藏文未经过母语译者逐条审校；功能回归不替代译文质量审校','用户输入、聊天、社群原文及音视频声音/字幕未自动翻译','新增后台内容需维护对应语言字段，缺失时显示可用原文','真实 AI、实体设备及正式支付仍按原接入状态','公网访问检查来自本机直连，不代表所有地区运营商'],
'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'03_当前APP').glob('*.html')}}
write(qa/'四语版本交付记录.json',record)
handoff_file=root/'交接资料验证.json'
handoff=read(handoff_file)
handoff.update(updated_beijing=now.strftime('%Y-%m-%d %H:%M:%S +08:00'),scope='Current in-place four-language APP, local administration and existing Netlify deployment',local_regression_pass=True,regression_groups_passed=56,regression_groups_failed=0,four_language_delivery=record)
write(handoff_file,handoff)
intro=root/'先读我.txt'
text=intro.read_text(encoding='utf-8')
text=re.sub(r'更新时间：[^\n]+','更新时间：'+now.strftime('%Y-%m-%d %H:%M:%S +08:00'),text,count=1)
marker='\n2026年11月2日四语言更新\n'
if marker in text: text=text.split(marker)[0]
intro.write_text(text.rstrip()+'\n'+marker+"""公网 APP：https://eastern-wisdom-demo-fuyao.netlify.app/
后台：https://eastern-wisdom-demo-fuyao.netlify.app/admin
电脑查看：https://eastern-wisdom-demo-fuyao.netlify.app/app
支持简体中文、繁体中文、English、藏文。首页右上角语言按钮或“我的→设置”切换，刷新保留选择。
URL 可指定 ?lang=zh-Hans、?lang=zh-Hant、?lang=en、?lang=bo。
藏文采用书面藏文，已先查阅术语和排版规范，再进行 AI 初译与界面修订；尚待母语译者审校。
后台操作界面继续使用中文，运营内容支持四语言字段。用户原始记录和音视频保持原文。
研究来源、术语与维护方法见05_后台与研发说明/四语言实现与藏文术语说明.txt。
实际验证见06_验证与后续工作/四语版本交付记录.json；本机与Netlify完整回归各56项通过，公网四语验收8项通过。
本次未重新生成交付ZIP；旧ZIP仍是历史快照。
""",encoding='utf-8')
usage=root/'03_当前APP/功能与使用说明-R4.txt'
text=usage.read_text(encoding='utf-8')
if marker in text: text=text.split(marker)[0]
usage.write_text(text.rstrip()+'\n'+marker+"""首页右上角可选择简体中文、繁体中文、English、藏文；也可在“我的→设置”切换，刷新后保留。
课程、三大地图、导航、提示与日期支持四语；后台的课程标题、介绍、目标、章节和轮播等内容可维护独立译文。
藏文内置字体，支持离线查看；不依赖海外在线字体服务。藏文译文为初版，尚待母语审校。
公网入口及技术/术语说明见根目录“先读我.txt”和05目录“四语言实现与藏文术语说明.txt”。
""",encoding='utf-8')
ag=root/'AGENTS.md'
marker2='\n### 2026年11月2日四语言版本\n'
text=ag.read_text(encoding='utf-8')
if marker2 in text: text=text.split(marker2)[0]
ag.write_text(text.rstrip()+'\n'+marker2+"""用户要求APP支持简体中文、繁体中文、英文、藏文，强调必须先研究藏文再翻译。本轮先查阅W3C藏文排版、THL、Tsadra/Rangjung Yeshe词典与Noto规范，采用Monlam公开翻译服务形成初稿并完成术语和界面修订。只处理公开文案，未提交用户账号、聊天、出生资料、密钥或数据库。藏文是未经过母语逐条审校的初版，不得称“专业母语审核通过”。研究来源及术语选择见05目录“四语言实现与藏文术语说明.txt”。
四语引擎、字典、离线OpenCC、藏文完整字体、布局与语言选择落在原r4源码，03目录三个HTML已重建；后台中文操作界面增加四语内容字段及独立课程章节。URL lang、首页按钮和设置可切换，刷新保留，用户原始内容不自动翻译。词典2279条藏文完整，变量、字体字形与标记检查通过；79页面×4语言扫描无渲染错误、横向溢出或缺译键。两套56项全量回归、6项网关、9项本地四语专项及8项真实公网四语验收通过；公网后台登录与10个翻译字段只读检查通过。范围及限制见06目录“四语版本交付记录.json”。
沿用原Netlify站点，部署ID 6ae86574436a9c3518edaa5e；原Sites后端继续承载数据，未修改或上传本机原SQLite。改前源码存档为07目录“四语改动前源码-20261102.zip”。未重新打包旧交付ZIP。新增后台内容须维护对应译文，缺少译文时仍保留可用原文；音视频声音与字幕不属于本次文字国际化。
""",encoding='utf-8')
failure_file=qa/'藏文翻译待复核.json'
failures=read(failure_file)
catalog_text=(root/'04_研发源码/app/r4/i18n-catalog.js').read_text(encoding='utf-8')
for entry in failures:
 entry['followup']='初译分段异常已用修订译文补齐；保留原异常供追溯。最终缺译检查为0，所有藏文仍待母语质量审校。'
 entry['resolved_in_final_catalog']=True
 entry['checked_at']=now.isoformat()
write(failure_file,failures)
print(json.dumps({'pass':True,'deploy_id':identity['deploy_id'],'updated_beijing':now.isoformat(),'checks':{k:v for k,v in record['checks'].items() if k!='catalog'}},ensure_ascii=True))

