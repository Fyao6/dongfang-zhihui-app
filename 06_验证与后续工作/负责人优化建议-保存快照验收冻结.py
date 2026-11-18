from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib
P=Path(__file__).resolve().parent.parent;D=P/'06_验证与后续工作'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();appsha=sha(P/'03_当前APP/东方智慧-首页体验R4.html')
specs=[('Python全量','负责人优化建议-保存快照-本轮全量回归结果.json','本机全量验收',60),('Cloud全量','负责人优化建议-保存快照-公网适配全量回归结果.json','本地Cloud全量验收',60),('Python专项','负责人优化建议-保存快照专项-python.json','Python专项验收',20),('Cloud专项','负责人优化建议-保存快照专项-cloud.json','Cloud专项验收',20)]
pending=[]
for label,name,suffix,count in specs:
 r=json.loads((D/name).read_text(encoding='utf-8-sig'));r=r.get('latest',r)
 assert r['pass'] is True and r['passed']==count and r['failed']==0,label
 if '全量' in label:assert r['buildHashes']['东方智慧-首页体验R4.html']==appsha
 else:
  assert r['identityUnchanged'] is True
  assert r['identity']['builds']['03_当前APP/东方智慧-首页体验R4.html']==appsha
  for n,v in r['identity']['sources'].items():assert sha(P/n)==v,(label,n,'changed')
  if label=='Cloud专项':assert r['localFontAssetVerified']
 out=D/('负责人优化建议-保存快照-'+suffix+'.json');assert not out.exists(),out
 pending.append((label,r,out,count))
verified={}
for label,r,out,count in pending:
 out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 verified[label]={'path':'06_验证与后续工作/'+out.name,'sha256':sha(out),'passed':count,'at':r['at']}
sources=['r4/backend/privacy_saved.py','cloud/lib/privacy-saved.ts','r4/privacy-saved.js','r4/privacy-saved.css','r4/backend/server.py','cloud/lib/eastern-api.ts','r4/build.py']
record={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':'负责人优化建议-保存快照','pass':True,'scope':'本人实际保存请求快照的元数据列表/主动查看/确认单删、关联AI正文清除与既有额度保留、幂等回执、全量删除后的旧详情失效；实际legacy保存入口接原子epoch/policy/provider校验，删除/撤回/配置变更后的旧回复不能重存。','verification':verified,'source_hashes':{'04_研发源码/app/'+s:sha(P/'04_研发源码/app'/s) for s in sources},'app_sha256':appsha,'limitations':['保存数据是请求时快照，可能包含近期消息；单删不会按字符串连删其他重叠快照，本机副本单独处理。','当前数据库的目标记录已实删；供应商和备份处理保留待确认，没有执行真实上游删除。','长期记忆服务未启用，本模块没有创建或伪称记忆/向量CRUD。','模型与供应商仅明示本机fixture，真实模型请求0；最终账号注销/全会话撤销执行与正式保留期清理仍未完成。','64视图为本机Chromium检查；藏文仍待母语审校。'],'failure_history':'首轮全局const pxApi重赋导致JS中断，已用可变privacyRequestSheet/成功privacyLoad回执进行目标失效；VM改lexical const覆盖。旧适配器单测同步mock新guarded入口并加调用断言。保留旧失败、Route夹具中断及最终UI文案调整前结果。'}
(D/'负责人优化建议-保存快照-实施记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
p=D/'负责人优化建议-任务拆解.json';tasks=json.loads(p.read_text(encoding='utf-8-sig'));by={x['id']:x for x in tasks}
notes={
'PR03':'撤回/删除后最终保存入口在事务/条件INSERT内再次核epoch、策略及真实provider配置，旧legacy迟到保存窗口已修；本人保存快照可查看/单删。长期记忆真实CRUD仍无服务、保持关闭，不以快照管理代替。',
'PR04':'本人元数据列表/主动看正文/单条确认删除/幂等回执已接，关联job正文为空、测试额度原账不变；全量删除成功后旧详情和迟到读失效。双端各60+20通过。供应商/备份确认、最终注销/全session撤销仍未完成。',
'PR01':'新增保存记录只列本人元数据，正文须主动查看且不恢复AI上下文；单删只影响明确ID，保护其他重叠记录与金融额度。全生态/供应商正式数据分类和保留政策仍待项目方补齐。'}
for ident,note in notes.items():by[ident]['status']='进行中';by[ident]['implementation_note']=note
p.write_text(json.dumps(tasks,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pass':True,'reports':len(verified),'tasks':len(tasks)},ensure_ascii=False))

