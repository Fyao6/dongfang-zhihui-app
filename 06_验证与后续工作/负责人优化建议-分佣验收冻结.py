from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib
P=Path(__file__).resolve().parent.parent;D=P/'06_验证与后续工作'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();appsha=sha(P/'03_当前APP/东方智慧-首页体验R4.html')
specs=[('Python全量','负责人优化建议-分佣-本轮全量回归结果.json','本机全量验收',60),('Cloud全量','负责人优化建议-分佣-公网适配全量回归结果.json','本地Cloud全量验收',60),('Python专项','负责人优化建议-分佣实际专项-python.json','Python专项验收',31),('Cloud专项','负责人优化建议-分佣实际专项-cloud.json','Cloud专项验收',31),('Python交易兼容','负责人优化建议-分佣交易兼容-python.json','Python交易兼容验收',31),('Cloud交易兼容','负责人优化建议-分佣交易兼容-cloud.json','Cloud交易兼容验收',31)]
verified={}
specs += [('Python会员兼容','负责人优化建议-CM会员兼容专项-python.json','Python会员兼容验收',29),('Cloud会员兼容','负责人优化建议-CM会员兼容专项-cloud.json','Cloud会员兼容验收',29)]
for label,name,suffix,count in specs:
 r=json.loads((D/name).read_text(encoding='utf-8-sig'));r=r.get('latest',r)
 assert r['pass'] is True and r['passed']==count and r['failed']==0,label
 if '全量' in label:assert r['buildHashes']['东方智慧-首页体验R4.html']==appsha
 elif '交易兼容' in label or '会员兼容' in label:assert r['identityUnchanged'] is True and r['identity']['builds']['03_当前APP/东方智慧-首页体验R4.html']==appsha
 else:
  assert r['identityUnchanged'] is True
  for n,v in r['identity'].items():assert sha(P/n)==v,(label,n,'changed')
  if label=='Cloud专项':assert r['fontAssetVerified']
 out=D/('负责人优化建议-分佣-'+suffix+'.json');assert not out.exists(),out
 out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 verified[label]={'path':'06_验证与后续工作/'+out.name,'sha256':sha(out),'passed':count,'at':r['at']}
sources=['r4/backend/commission.py','cloud/lib/commission-api.ts','r4/commission-admin.js','r4/commission-center.js','r4/commission-center.css','r4/backend/server.py','cloud/lib/eastern-api.ts','r4/backend/commerce.py','cloud/lib/commerce-api.ts','r4/backend/privacy.py','cloud/lib/privacy-api.ts','r4/time-bank-admin.html','r4/build.py','cloud/prepare.py','r4/commerce-ui.js','r4/creator-center.html','r4/frame-home-profile.js','r4/navigation-back.js']
record={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':'负责人优化建议-分佣','pass':True,'scope':'复用统一订单/项/付款/退款的成交规则与归因快照、整数佣金台账、未知费用等待、冻结和双账号审批、结算记账与测试付款资料分开、按项退款冲正/已结算追偿、本人报表/CSV筛选、即时角色分权、隐私本人导出及金融原账保留。','verification':verified,'source_hashes':{'04_研发源码/app/'+s:sha(P/'04_研发源码/app'/s) for s in sources},'app_sha256':appsha,'limitations':['正式分佣文档、真实拒付/费用/税务与收款资料政策仍未提供，productionEnabled和actualPaymentsEnabled固定false。','审批/记账/沙箱凭证都不代表银行实际付款，actualPaid与proofVerified固定false。','佣金为统一交易提交后的可重试派生；派生失败如实sync_pending，不能据此重做付款或退款。','旧单无创建时快照不会以当前规则补造；真实渠道每日对账、回调和外部告警未完成。','四语界面通过本地Chromium检查；藏文仍待母语审校，未声称移动原生或生产财务验收。'],'failure_history':'已保留实际D1对相关子查询ORDER BY外层c.data解析失败的500与原夹具取消Route中断；SQL改本地配置别名并两端同构，最终实际D1 first/last_touch与双31专项通过。Cloud QA补真实public/assets字体绑定。'}
(D/'负责人优化建议-分佣-实施记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
p=D/'负责人优化建议-任务拆解.json';tasks=json.loads(p.read_text(encoding='utf-8-sig'));by={x['id']:x for x in tasks}
notes={
'CM01':'正式分佣文档仍缺；可配置沙箱框架已接入，生产计佣/真实打款固定关闭。双端全量各60、分佣专项各31、交易兼容各31通过。见分佣实施记录。',
'CM02':'规则按版本追加，服务端邀请码归因，成交快照与会员快照同订单事务/同D1 batch保存；first/last_touch在真实D1均验证。旧单不套当前规则，正式归因政策待确认。',
'CM03':'统一订单项整数最小币种台账，比例用整数/BigInt中间计算；未知渠道费null进入waiting_facts，不冒充0。计佣基数/费率正式文档待定。',
'CM04':'待确认/冻结/可结算/另一财务审批/结算记账/测试付款资料分别存储；自批拒绝，actualPaid和proofVerified均false，未实际转账。正式周期/冻结/收款资料仍待确认。',
'CM05':'实际统一按项退款按原成交规则累计冲正；已结算保留原账并产生待抵扣/追偿，重复重放不二次调整。真实拒付事件与渠道接口未接，不伪造拒付。',
'CM06':'本人报表、按作品/受益人/类型/币种/时间筛选和防公式CSV已实现；staff+显式business/finance/support分权，降权即时失效。隐私导出仅本人且金融账保留明确。',
'G03':'商城、会员及分佣复用统一商品/订单/付款/退款，会员/佣金保存独立状态和成交快照，失败派生可重试；双后端完整与实际专项通过。真实渠道/正式业务文档仍待补。',
'PAY14':'沙箱按项退款实际联动库存、独立数字权益、会员状态与佣金累计冲正/追偿；生产资金/真实拒付与平台退款适配仍未接入。',
'PAY17':'资金操作维持管理员门禁；分佣另按当前基础staff+显式专项grant鉴权，降级立即拒绝。生产与实际打款固定关闭，正式强认证/生产角色运营待配置。'}
for ident,note in notes.items():by[ident]['status']='进行中';by[ident]['implementation_note']=note
p.write_text(json.dumps(tasks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pass':True,'reports':len(verified),'tasks':len(tasks)},ensure_ascii=False))

