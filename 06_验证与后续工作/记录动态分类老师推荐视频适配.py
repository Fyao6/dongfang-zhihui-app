from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,csv,os
from lxml import html,etree
r=Path(__file__).resolve().parent.parent;q=r/'06_验证与后续工作';now=datetime.now(timezone(timedelta(hours=8))).isoformat()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
local=read(q/'本轮全量回归结果.json')['latest'];cloud=read(q/'Netlify适配全量回归结果.json')['latest']
assert local['pass'] and cloud['pass'] and local['passed']==cloud['passed']==56
reports={n:read(q/n) for n in ('动态分类与老师认证-本机核验.json','动态分类与老师认证-云端适配核验.json','课程动态分类浏览器核验.json','视频比例与老师推荐核验.json','老师认证后台表单核验.json')}
assert all(v['pass'] for v in reports.values())
for name,digest in local['buildHashes'].items():assert hashlib.sha256((r/'03_当前APP'/name).read_bytes()).hexdigest()==digest
assert reports['视频比例与老师推荐核验.json']['buildSHA256']==local['buildHashes']['东方智慧-首页体验R4.html']
scan=read(q/'四语页面扫描.json');assert not scan['errors'] and not scan['missing'] and not any(x.get('error') or x.get('overflow') for x in scan['pages'])
record={'at':now,'status':'implemented_and_validated_locally_publication_blocked',
'approved_tasks':['智慧馆恢复图文全部课程列表','后台动态课程分类CRUD和课程多分类关联','初始有声书与视频教程分类及一次性迁移','社群四入口及老师推荐','真实认证推荐老师资料与咨询需求流程','竖屏方形横屏自适应和透明导航','保留自动播放暂停静音进度和左下标题','四语及完整回归'],
'backup':read(q/'课程动态分类改前存档核验.json')['archive'],
'verification':{'local_full':{k:local[k] for k in ('module','at','passed','failed','buildHashes')},'cloud_full':{k:cloud[k] for k in ('module','at','passed','failed','buildHashes')},'api_local_checks':len(reports['动态分类与老师认证-本机核验.json']['checks']),'api_cloud_checks':len(reports['动态分类与老师认证-云端适配核验.json']['checks']),'browser_course_checks':reports['课程动态分类浏览器核验.json']['checks'],'video_teacher_checks':reports['视频比例与老师推荐核验.json']['checks'],'admin_teacher_ui_checks':reports['老师认证后台表单核验.json']['checks'],'real_ratio_cases':len(reports['视频比例与老师推荐核验.json']['ratioCases']),'four_language_page_states':len(scan['pages'])},
'preview':{'app':'http://127.0.0.1:8765/experience?lang=zh-Hans&page=academy&v=dynamic-categories-20261103','admin':'http://127.0.0.1:8765/admin','community':'http://127.0.0.1:8765/experience?lang=zh-Hans&page=community&v=dynamic-categories-20261103'},
'publication':{'published':False,'frontend_replaced':False,'backend_replaced':False,'source_synced':False,'reason':'Current Sites get_site/create_source_repository_write_credential tools return not available to the model; plugin discovery tool also unavailable. Native app browser can open local preview, but Windows UI exposed no accessible publishing controls.','last_public_netlify_deploy':read(r/'05_后台与研发说明/Netlify站点身份.json')['deploy_id'],'preserved_public_url':'https://eastern-wisdom-demo-fuyao.netlify.app/'},
'limits':['现有老师均为示例，不自动认证；推荐页显示真实空状态，等待管理员配置实际认证老师','咨询沿用提交需求、后台受理与状态回看，未伪造成实时真人回复','藏文新界面词条为初稿修订，仍待母语审校','未重新打包旧桌面ZIP']}
write(q/'动态分类老师推荐视频适配交付记录.json',record)
usage="""动态课程分类、老师推荐与视频适配使用说明
本轮已在原项目实施并验证。当前公网发布受工具不可用影响，线上尚未替换。

一、查看
本机APP：http://127.0.0.1:8765/experience
本机后台：http://127.0.0.1:8765/admin
电脑查看：http://127.0.0.1:8765/app
03_当前APP目录两个APP查看页均已重建。离线页读取当前初始分类；管理与咨询等接口操作需要本机服务或后续部署后的公网服务。
本机后台沿用本机原账号；公网账号与密码未改变，也没有覆盖本机原账号。

二、课程筛选项
智慧馆进入后直接展示图文课程列表。原“按老师／全部课程”切换已移除，原位置为“全部／有声书／视频教程”等动态筛选条。
后台“课程筛选项”支持新增、查找、编辑、四语名称、排序、启停、草稿／发布及删除。
发布且启用的筛选项才显示在APP；“全部”是保留入口，不作为可删除业务分类。
后台编辑课程，在筛选分类中可多选所属项。以后新增茶道等分类，通过后台创建并给课程关联即可。
删除分类只移除该筛选项及其课程关联，课程本身继续保留。当前选中的分类失效后自动回到全部。
初始分类只迁移一次；以后删除默认项、修改名称或排序后，不会因重启又恢复默认。

三、老师推荐与咨询
社群顶部依次为“我的好友／我的对话／老师推荐／推荐视频”。
老师推荐只显示已发布、真实资料、已认证并开启推荐的老师。认证和推荐状态只能由管理员修改。
当前清和、安然、知微仍是示例老师，不能标成认证老师；推荐页显示空状态，直到后台维护实际老师。
点推荐老师查看介绍、擅长领域和认证标识，登录后提出咨询内容和期望日期。
咨询需求可在本人记录中查看和撤销，后台可受理／结束。当前流程是交流需求与状态回看，不代表已提供实时真人回复。

四、视频
依据真实媒体宽高选择适度铺满或等比居中；9:16、3:4、1:1和16:9均已使用真实录制视频核验。
长竖屏在裁切损失不超过18%时铺满，其他情况保留完整比例；顶部四标签透明叠加，选中项突出、其他项半透明。
默认自动静音播放，仅当前视频播放；保留切换自动播放、离页暂停、手动暂停意图、声音开关、底边细进度及左下标题说明。

五、验证与发布
两套完整回归各56项通过；课程后台浏览器联调8项、四语12尺寸组合通过。
本机和Worker分类认证接口专项通过；视频和老师页专项8项、64组真实比例／语言／尺寸组合通过。
83个页面×4语言共332状态扫描无运行错误、横向溢出或缺译键。藏文未经过母语逐条审校。
证据：06_验证与后续工作/动态分类老师推荐视频适配交付记录.json。
当前Sites发布工具不可调用，未推送新源码、未替换公网前台或后台。恢复工具后，复用原project_id和Netlify站点，完成源码同步、原Sites后端部署、Netlify部署及公网复测后才可标记公网完成。
"""
(r/'05_后台与研发说明/动态分类与老师推荐使用说明.txt').write_text(usage,encoding='utf-8')
note='\n\n2026年11月3日：已确认八项课程分类、老师推荐与视频适配改动\n用户已确认先前八项任务并授权实施。已恢复智慧馆图文全部课程列表，增加后台动态courseCategories及课程categoryIds，社群四标签、真实认证推荐老师和咨询需求、视频多比例适配及透明叠加。源码与03页面已更新。\n两套完整回归各56项通过，后台与浏览器专项通过，332个四语页面状态扫描无缺译或溢出。示例老师不自动认证，推荐页保持真实空状态。\n当前Sites发布工具返回not available to the model，插件发现工具同样不可用；公网前后台尚未替换、源码尚未推送，不能声称已发布。当前本地预览在http://127.0.0.1:8765/experience。恢复工具后沿用原站点身份完成发布及公网复测。\n具体操作见05_后台与研发说明/动态分类与老师推荐使用说明.txt；测试、回退及发布阻塞见06_验证与后续工作/动态分类老师推荐视频适配交付记录.json。未重新打包桌面旧ZIP。\n'
for rel in ('AGENTS.md','先读我.txt','03_当前APP/功能与使用说明-R4.txt'):
 p=r/rel;s=p.read_text(encoding='utf-8')
 if '2026年11月3日：已确认八项课程分类、老师推荐与视频适配改动' not in s:p.write_text(s.rstrip()+note,encoding='utf-8')
p=r/'交接资料验证.json';d=read(p);d.update(updated_beijing=now,dynamic_categories_teacher_video=record);write(p,d)
for filename,element_id in [('打开这里.html','dynamic-categories-current'),('改动任务表-2026-10-22.html','dynamic-categories-tasks')]:
 p=r/filename;doc=html.fromstring(p.read_text(encoding='utf-8'))
 for old in doc.xpath('//*[@id="'+element_id+'"]'):old.getparent().remove(old)
 body='<section id="'+element_id+'"><h2>11月3日：动态课程分类、认证老师推荐与视频适配</h2><p>本地开发与验证完成：两套完整回归各56项通过。公网发布工具暂不可用，线上尚未替换。</p><p><a href="http://127.0.0.1:8765/experience?lang=zh-Hans&amp;page=academy&amp;v=dynamic-categories-20261103">查看本机新版APP</a> · <a href="05_后台与研发说明/动态分类与老师推荐使用说明.txt">使用说明</a> · <a href="06_验证与后续工作/动态分类老师推荐视频适配交付记录.json">验证和发布状态</a></p><ol>'+''.join('<li>'+item+'：本地已实施并验证，待公网发布。</li>' for item in record['approved_tasks'])+'</ol></section>'
 section=html.fragment_fromstring(body);(doc.xpath('//main') or doc.xpath('//body'))[0].insert(0,section);p.write_text('<!doctype html>\n'+etree.tostring(doc,encoding='unicode',method='html'),encoding='utf-8')
skip_dirs={'.git','__pycache__','node_modules','.venv','.wrangler','.sites-runtime','.netlify','dist','.next','.vinext','.cache','coverage'}
skip_suffixes={'.zip','.7z','.rar','.tar','.gz','.tgz','.pyc','.log','.db','.pem','.key','.pfx','.p12','.tsbuildinfo'}
rows=[]
for current,dirs,names in os.walk(r):
 dirs[:]=[d for d in dirs if d not in skip_dirs and not (Path(current)/d).is_symlink()]
 for name in names:
  p=Path(current)/name
  if p.is_symlink() or p.suffix.lower() in skip_suffixes or any(x in name.lower() for x in ('.sqlite','.env','.dev.vars')) or name in {'资料校验清单.csv','原始来源与文件校验.json','.DS_Store','Thumbs.db'}:continue
  data=p.read_bytes();rows.append({'path':p.relative_to(r).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
rows.sort(key=lambda x:x['path'])
with (r/'资料校验清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['包内相对位置','字节数','SHA-256']);w.writerows((x['path'],x['bytes'],x['sha256']) for x in rows)
p=r/'原始来源与文件校验.json';d=read(p);d['files']=rows;d['current_revision']={'updated_beijing':now,'scope':'Current source/build; private runtime and archived ZIPs excluded','local_regression_pass':True,'public_deployment_pending':True,'delivery_record':'06_验证与后续工作/动态分类老师推荐视频适配交付记录.json'};write(p,d)
print(json.dumps({'pass':True,'local_full':local['passed'],'cloud_full':cloud['passed'],'public_deployment_pending':True,'manifest_files':len(rows)}))

