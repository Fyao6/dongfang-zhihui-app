from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib
P=Path(__file__).resolve().parent.parent;D=P/'06_验证与后续工作'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();appsha=sha(P/'03_当前APP/东方智慧-首页体验R4.html')
specs=[('Python全量','负责人优化建议-抽卡-本轮全量回归结果.json','本机全量验收',60),('Cloud全量','负责人优化建议-抽卡-公网适配全量回归结果.json','本地Cloud全量验收',60),('Python专项','负责人优化建议-抽卡专项-python.json','Python专项验收',25),('Cloud专项','负责人优化建议-抽卡专项-cloud.json','Cloud专项验收',25)]
verified={}
for label,name,suffix,count in specs:
 r=json.loads((D/name).read_text(encoding='utf-8-sig'));r=r.get('latest',r)
 assert r['pass'] is True and r['passed']==count and r['failed']==0,label
 if '全量' in label:assert r['buildHashes']['东方智慧-首页体验R4.html']==appsha
 else:
  assert r['identityUnchanged'] is True
  assert r['identity']['builds']['03_当前APP/东方智慧-首页体验R4.html']==appsha
  for n,v in r['identity']['sources'].items():assert sha(P/n)==v,(label,n,'changed')
  if label=='Cloud专项':assert r['localFontAssetVerified']
 out=D/('负责人优化建议-抽卡-'+suffix+'.json');assert not out.exists(),out
 out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 verified[label]={'path':'06_验证与后续工作/'+out.name,'sha256':sha(out),'passed':count,'at':r['at']}
sources=['r4/backend/card_service.py','cloud/lib/card-service.ts','r4/card-service-ui.js','r4/card-service.css','r4/card-service-admin.js','r4/backend/server.py','cloud/lib/eastern-api.ts','r4/backend/privacy.py','cloud/lib/privacy-api.ts','r4/build.py','cloud/prepare.py','r4/platform.js','r4/time-bank-admin.html']
record={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':'负责人优化建议-抽卡','pass':True,'scope':'服务端随机/防重与幂等结果、明确规则与卡组版本、抽前/抽中/结果/已用状态、本人收藏感受练习历史、后台审核发布、最小分享与单独AI入口、隐私同batch删除及最小额度/时区/删除代际保留。','verification':verified,'source_hashes':{'04_研发源码/app/'+s:sha(P/'04_研发源码/app'/s) for s in sources},'app_sha256':appsha,'limitations':['正式卡种、完整36卡文案/授权美术、每日次数/主题/日界时区等规则未确认；默认关闭，仅明确合成测试卡组完成沙箱验证。','离线旧卡仅标本机示例；不会冒充服务器正式抽取。','删除历史后保留最小防重quota、时区与删除代际，保留期限仍待确认，不能用清记录或切时区重抽。','AI调用只验证独立点击/最小输入与同意路径，真实模型请求0；不代表实际输出安全或正式卡义审定。','四语日夜/四宽64视图为本机Chromium检查，藏文待母语审校，正式卡面视觉待项目方评价。'],'failure_history':'保留首次实际分享勾选被异步重读重置的失败；已保存shareFields并在读取/缺draw时禁提交、旧draw表单拒绝。另保留pxLoad夹具误名及Route清理中断，修夹具后双25全过。'}
(D/'负责人优化建议-抽卡-实施记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
p=D/'负责人优化建议-任务拆解.json';tasks=json.loads(p.read_text(encoding='utf-8-sig'));by={x['id']:x for x in tasks}
notes={
'DR04':'已实现卡面展示、卡组主题/规则待确认、历史与分享页面框架；四语/日夜/四宽64视图实测。正式图案、完整卡文与版权未提供，合成白底测试图不当正式视觉方案。',
'DR05':'抽取前/请求中/结果/当日已用/失败重试状态实际接服务端；弱网复用同requestId取原结果，分享选择跨异步读取保留。双端全60+专项25通过，生产规则仍待确认。',
'DR06':'本人收藏、感受、练习标记与原卡文/图片引用/规则版本历史实际保存；新卡组不覆盖旧结果；删除后结果清除但额度仍已用。未把加入练习当真实练习时长。',
'DR07':'两端服务器CSPRNG、跨主题/版本共用本人环境额度、原子唯一/幂等、时区冷却与删除代际防迟到已验证；删除不重抽，客户端指定结果/权重/日期拒绝。正式次数/日界未确认保持关。',
'DR08':'卡组规则/三语逐卡/审核/版本发布下架后台已接入，只有授权管理员可变更；未审核/资料不全不得发布。真实表单与媒体ACL验证通过，正式36卡与授权未提供。',
'DR09':'AI需另行点击且仅送当前卡最小字段；分享默认仅卡图，文字主动选择，不包含感受/出生/聊天。实际分享预览与隔离验证通过，未外发；真实AI与正式输出审定待接口。',
'PR04':'本人导出已含交易/订阅/佣金，清记录原子清卡历史/感受/收藏/练习并保留最小防重元数据；注销前动态核对本方续期。单条保存快照与旧legacy迟到保存窗口已备P1修复待下一模块接入；最终注销执行与供应商/备份仍未完成。'
}
for ident,note in notes.items():by[ident]['status']='进行中';by[ident]['implementation_note']=note
p.write_text(json.dumps(tasks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pass':True,'reports':len(verified),'tasks':len(tasks)},ensure_ascii=False))

