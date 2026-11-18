from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,shutil
P=Path(__file__).resolve().parent.parent;D=P/'06_验证与后续工作'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
appsha=sha(P/'03_当前APP/东方智慧-首页体验R4.html')
pairs=[
 ('Python全量','负责人优化建议-会员订阅-本轮全量回归结果.json','负责人优化建议-会员订阅-本机全量验收.json',60),
 ('Cloud全量','负责人优化建议-会员订阅-公网适配全量回归结果.json','负责人优化建议-会员订阅-本地Cloud全量验收.json',60),
 ('Python专项','负责人优化建议-会员专项-python.json','负责人优化建议-会员订阅-Python专项验收.json',29),
 ('Cloud专项','负责人优化建议-会员专项-cloud.json','负责人优化建议-会员订阅-Cloud专项验收.json',29),
 ('Python交易兼容','负责人优化建议-会员交易兼容-python.json','负责人优化建议-会员订阅-Python交易兼容验收.json',31),
 ('Cloud交易兼容','负责人优化建议-会员交易兼容-cloud.json','负责人优化建议-会员订阅-Cloud交易兼容验收.json',31)]
verified={}
for label,source,target,count in pairs:
 raw=json.loads((D/source).read_text(encoding='utf-8-sig'));r=raw.get('latest',raw)
 assert r.get('pass') is True and r['passed']==count and r['failed']==0,(label,'not all passed')
 if '全量' in label:assert r['buildHashes']['东方智慧-首页体验R4.html']==appsha
 else:
  assert r['identityUnchanged'] is True
  assert r['identity']['builds']['03_当前APP/东方智慧-首页体验R4.html']==appsha,(label,'stale build')
  if '交易兼容' not in label:assert r['testFilesUnchanged'] is True
 t=D/target
 assert not t.exists(),str(t)+' already frozen'
 t.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 verified[label]={'path':'06_验证与后续工作/'+target,'sha256':sha(t),'passed':count,'at':r['at']}
sources=['r4/backend/membership_lifecycle.py','cloud/lib/membership-lifecycle.ts','r4/membership-lifecycle-ui.js','r4/membership-lifecycle-ui.css','r4/membership-lifecycle-admin.js','r4/backend/commerce.py','cloud/lib/commerce-api.ts','r4/backend/server.py','cloud/lib/eastern-api.ts','r4/backend/privacy.py','cloud/lib/privacy-api.ts','r4/build.py','cloud/prepare.py','r4/platform.js','r4/time-bank-admin.html']
record={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':'负责人优化建议-会员订阅','pass':True,'scope':'统一SKU方案配置与版本、同订单成交条款快照、沙箱订阅生命周期、本人取消/退款申请/恢复与注销前续期提醒、后台与本人隐私导出。','verification':verified,'source_hashes':{'04_研发源码/app/'+s:sha(P/'04_研发源码/app'/s) for s in sources},'app_sha256':appsha,'limitations':['真实Apple/Google/Stripe/PayPal验单、通知及收费均未接入，production固定关闭；测试订阅不授予正式媒体权限或真实AI额度。','正式方案价格/权益/渠道商品ID及适用退款条款仍待项目方确认，试用与优惠默认关闭。','Cloud付款与订阅补接为可重试最终同步；未同步时如实保留已付款事实，不宣称订阅已生效。','四语界面通过Chromium375/430检查，藏文仍待母语审校；没有移动原生实机或多端真实支付验收。','注销弹窗只核对本方测试续期并链接原渠道说明，未实际提交/完成账号注销，也无法确认第三方续费已取消。'],'failure_history':'保留Route拦截清理夹具中断及共享读写30/min造成的真实429失败；正式实现已按账号读180/写30分桶并去除重复读取，最新版双端29专项与双60、双31全过。'}
(D/'负责人优化建议-会员订阅-实施记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
p=D/'负责人优化建议-任务拆解.json';tasks=json.loads(p.read_text(encoding='utf-8-sig'));by={x['id']:x for x in tasks}
notes={
'MB01':'已实现绑定统一SKU的方案/不可变版本、有限计费周期与逐项权益配置；双端全60+会员专项29通过。正式价格/权益尚未提供，生产、试用、优惠均关闭。',
'MB02':'会员中心按本人原成交快照展开首期/续期价、币种、周期、权益、渠道、试用和条款；渠道商品映射可配置，真实Apple/Google/网站验单尚未接通。见会员订阅实施记录。',
'MB03':'取消自动续期、申请退款、恢复购买三个独立真实入口已完成；沙箱取消保留已付周期、退款申请待处理不冒充资金退回，恢复不重置周期。正式渠道仅官方管理帮助，生产仍待接入。',
'MB04':'统一订单驱动active/失败/宽限/暂停/欠费/取消仍有效/到期/退款撤销；双端实际29项通过，支付取消竞态原子拒绝，Cloud补接中断可重试。试用未确认关闭，正式平台通知待接。',
'MB05':'本人原付款与账号归属验证、同一成交不重复领取、到期/退款不误删独立单购；注销弹窗核对本方仍续期测试订阅并明确第三方未知。双端验证通过，真实渠道恢复/最终注销未完成。',
'PAY11':'订阅沙箱生命周期已关联统一付款/退款，成交规则与价格快照不被当前改价覆盖；真实原生及网站平台通知未接通，不能标为正式同步完成。',
'PAY12':'本人沙箱已付原单可从服务器恢复，验证归属/幂等且不延长或复开续期；真实跨设备渠道receipt/token验单仍待配置。',
'PT01':'统一交易兼容两端各31、会员专项各29与完整回归各60通过；只证明隔离沙箱，不代表真实渠道、银行验证或生产付款全链路验收。',
'SV03':'已按P317–385形成业务/数据库/媒体/GPU隔离运行架构与两云同口径询价底稿；当前实际后端仍Python/SQLite与Cloud/D1，PostgreSQL生产迁移和资源部署未执行。',
'SV04':'本机/Cloud随机隔离测试库与默认生产关闭已有实际验证；生产密钥管理、TLS/私网/MFA、告警及可回滚部署尚需真实环境实施。',
'SV05':'已列两云共同资源、区域/配额、出网/日志/备份/GPU/API/运维分项询价字段；没有供应商正式报价或官方计算器实际价格，待容量输入与询价。',
'SVT01':'已在新隔离库进行100匿名逻辑访客、20RPS30秒本机探索：600/600成功、P95 15.57ms；非100登录并发、非目标国家、非30分钟，不能当正式容量达标。见SVT01本机探索报告。',
'SVT03':'隔离SQLite在线备份/恢复10项通过，实际恢复服务可读相同公开目录；显式记录备份后1条已确认写入未恢复。未演练PostgreSQL主备/GPU中断/支付流水核对或生产RPO/RTO。',
'SH07':'按P250/252的首期建议保持平台自营/授权作品范围；统一商品目前不接受服务预约类型，也无第三方自入驻入口。首批若包含预约或需入驻，须补时区/名额/改期及商家结算责任后另行启用。'
}
for ident,note in notes.items():by[ident]['status']='进行中';by[ident]['implementation_note']=note
p.write_text(json.dumps(tasks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pass':True,'reports':len(verified),'tasks':len(tasks)},ensure_ascii=False))

