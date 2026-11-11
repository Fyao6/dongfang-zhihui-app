from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,hashlib,re
root=Path(__file__).resolve().parent.parent;q=root/'06_验证与后续工作';now=datetime.now(ZoneInfo('Asia/Shanghai'))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
local=read(q/'本轮全量回归结果.json')['latest'];cloud=read(q/'Netlify适配全量回归结果.json')['latest']
assert local['pass'] and cloud['pass'] and '老师分类与社群' in local['module'] and '老师分类与社群' in cloud['module']
scan=read(q/'四语页面扫描.json');assert not(scan['missing'] or scan['errors'] or scan['residuals'])
assert not any(p.get('error') or p.get('overflow') for p in scan['pages'])
for name in ['老师课程接口核验.json','老师分类页面核验.json','社群视频专项核验.json','老师社群-公网验收.json','四语专项联调.json']:
 assert read(q/name)['pass']
identity_path=root/'05_后台与研发说明/Netlify站点身份.json';identity=read(identity_path)
previous=identity['deploy_id'];identity.update(deploy_id='6ae86fd243806001ba18176e',checked_at=now.isoformat(),previous_deploy_id=previous,latest_change='老师课程分类与社群三标签竖屏视频')
write(identity_path,identity)
record={'at':now.isoformat(),'site':identity['url'],'deploy_id':identity['deploy_id'],'previous_deploy_id':previous,
'changes':['智慧馆默认按老师分类，老师页展示全部已发布相关课程，详情可返回老师页','后台老师资料四语字段、头像、示例/真实标识和课程所属老师选择','社群顶部三个入口：我的好友、我的对话、推荐视频','一屏一视频，进度/声音/播放与暂停，滑动切换和离页/隐藏暂停','去除社群分享心得与旧工具区，发布管理移入我的','保留四语言、原课程编号、权益和审核权限'],
'checks':{'local_full':{'passed':local['passed'],'failed':local['failed'],'at':local['at']},'cloud_full':{'passed':cloud['passed'],'failed':cloud['failed'],'at':cloud['at']},'teacher_ui':read(q/'老师分类页面核验.json')['checks'],'teacher_api':read(q/'老师课程接口核验.json')['checks'],'community':read(q/'社群视频专项核验.json')['checks'],'public':read(q/'老师社群-公网验收.json')['checks'],'four_language_checks':len(read(q/'四语专项联调.json')['results']),'pages_and_locales':len(scan['pages']),'catalog':read(q/'四语字典与字体校验.json')},
'content_migration':read(q/'老师分类内容迁移结果-公网.json'),
'backup':str(sorted((root/'07_历史版本仅供追溯').glob('老师课程与社群改版前-*.zip'))[-1].relative_to(root)),
'content_backup':'06_验证与后续工作/老师分类内容迁移备份-公网.json',
'limits':['清和、安然、知微为明确标注的示例老师，非真人任教或资质声明','推荐视频使用审核通过的视频及原有预览，未引入个性化推荐算法','新增藏文沿用初译与术语修订流程，尚待母语审校','未重新生成交付ZIP；真实AI、设备和正式支付接入状态不变'],
'output_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'03_当前APP').glob('*.html')}}
write(q/'老师分类与社群视频交付记录.json',record)
handoff_path=root/'交接资料验证.json';handoff=read(handoff_path);handoff.update(updated_beijing=now.isoformat(),scope='Current four-language APP with teacher course collections and vertical community video feed',local_regression_pass=True,regression_groups_passed=56,regression_groups_failed=0,teacher_community_delivery=record);write(handoff_path,handoff)
note="""
2026年11月2日：老师分类与社群视频更新
智慧馆默认按老师分类，点老师进入相关课程；“全部课程”可回到图文列表，保留三自我和权益筛选。
后台课程支持选择所属老师。当前3位老师为明确标记的示例资料，各关联3门已有课程，实际老师资料可在后台替换。
社群顶部仅保留“我的好友、我的对话、推荐视频”，推荐区改为竖屏视频。分享心得已从社群主页去除，发布记录和上传入口移到“我的→我的视频与发布”。
原公网地址已更新，部署ID为6ae86fd243806001ba18176e。本机与Netlify适配全量回归各56项通过，真实公网8项验收通过，四语324次页面渲染扫描通过。
使用和后台操作见05_后台与研发说明/老师课程分类与社群视频使用说明.txt；证据与回退记录见06_验证与后续工作/老师分类与社群视频交付记录.json。
"""
for p in [root/'先读我.txt',root/'03_当前APP/功能与使用说明-R4.txt']:
 s=p.read_text(encoding='utf-8')
 if note.splitlines()[1] not in s:s=s.rstrip()+'\n'+note
 if p.name=='先读我.txt':s=re.sub(r'更新时间：[^\n]+','更新时间：'+now.strftime('%Y-%m-%d %H:%M:%S +08:00'),s,count=1)
 p.write_text(s,encoding='utf-8')
p=root/'AGENTS.md';s=p.read_text(encoding='utf-8')
s+="""

### 2026年11月2日老师课程分类与社群视频
用户要求智慧馆按老师归类，点击查看老师相关课程；社群采用参考图的顶部横向导航，仅保留“我的好友、我的对话、推荐视频”，去掉“分享心得”。已在原源码及03构建页实施，并同步原Netlify站点，部署ID 6ae86fd243806001ba18176e。
智慧馆默认按老师展示，保留全部课程、三自我与权益/形式筛选；老师详情、课程详情与返回路径贯通。后台老师可维护头像、四语资料和示例标识；课程通过teacherId选择老师。无老师或未发布老师的课程归入平台课程。当前清和/安然/知微为明确标注的示例老师，各关联3门已有示例课程，不可称真人讲师或授权课程；示例老师不开放真人交流需求按钮。公网内容经管理员接口更新，原数据先保留备份，现有账号/聊天/数据库未搬移。
社群主界面采用一屏一视频和三标签入口；手动开始、默认静音，可切换声音、拖动进度、上下滑动/按钮/键盘切换。离页或隐藏页面暂停，只有当前视频播放。推荐区仅展示审核通过的带视频内容，并保留用户提供的短视频预览；不伪造互动数或声称存在个性化推荐算法。原发布/草稿/审核/撤回功能保留于“我的→我的视频与发布”，不再在社群堆叠入口。
老师模块单独56项回归通过；合并最终本机56项、云端适配56项、四语专项9项、公开网址8项验收通过，81页面×4语言扫描无缺译/溢出/运行异常，2300条藏文字典字形和变量检查通过，藏文仍待母语审校。途中失败与修复证据保留，不能引用中途报告宣称最终未通过，也不能拿旧版通过记录代替本轮。最新交付记录、内容迁移备份与专用测试在06目录；源码改前ZIP在07目录，未新打整包。
"""
p.write_text(s,encoding='utf-8')
print(json.dumps({'pass':True,'deploy_id':identity['deploy_id'],'local':local['passed'],'cloud':cloud['passed'],'public':len(record['checks']['public'])}))

