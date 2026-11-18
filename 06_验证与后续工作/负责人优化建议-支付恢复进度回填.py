"""Update only PAY09 and current handoff metadata after its frozen dual-backend gates."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import copy,hashlib,json

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-支付恢复'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
stamp=datetime.now(timezone(timedelta(hours=8)))
tag=stamp.strftime('%Y%m%d-%H%M%S')
receipt_path=OUT/(PREFIX+'-实施记录.json')
receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
assert receipt['pass'] and receipt['stage']==22 and receipt['taskId']=='PAY09'
for path,expected in {**receipt['source_hashes'],**receipt['build_hashes']}.items():assert sha(ROOT/path)==expected,path
backups={}


def save(path,value):
    backup=OUT/(PREFIX+'回填前-'+tag+'-'+path.name)
    assert not backup.exists();backup.write_bytes(path.read_bytes())
    backups[path.relative_to(ROOT).as_posix()]={'path':backup.relative_to(ROOT).as_posix(),'sha256':sha(backup)}
    path.write_bytes(((json.dumps(value,ensure_ascii=False,indent=2)+'\n') if not isinstance(value,str) else value).encode('utf-8'))


scope=('PAY09通用本地恢复软件已验收：本人真实服务端查单、持久任务、请求幂等、有限重试与租约恢复、'
       '配置撤回指纹及可信结果仅消费本人收件，APP四语/日夜与后台回查。双端完整60、专项19、原交易31、PAY08兼容16、视觉4通过。'
       '正式支付渠道验单/查单及会员权益衔接仍待实施联调；PAY13迟到库存/权益补偿另项推进。')
entry={'path':receipt_path.relative_to(ROOT).as_posix(),'sha256':sha(receipt_path),'module':PREFIX,'pass':True,
       'at':receipt['at_beijing'],'scope':receipt['scope'],'limitations':receipt['limitations'],
       'verification':[{'name':key,**value} for key,value in receipt['verification'].items()]}
tasks_path=OUT/'负责人优化建议-任务拆解.json'
tasks=json.loads(tasks_path.read_text(encoding='utf-8'));old=copy.deepcopy(tasks)
task=next(r for r in tasks if r['id']=='PAY09');assert task['status']=='待实施'
task.update(status='进行中',progressNote=scope,localEvidence=[entry['path']],
            remainingSoftware=['真实渠道验单/查单及事件规范适配','会员查询结果与订阅权益事务衔接','PAY13迟到库存/权益补偿另项'])
assert all(a==b for a,b in zip(old,tasks) if a['id']!='PAY09')
counts=dict(Counter(r['status'] for r in tasks));assert counts=={'进行中':69,'待资料':16,'待验收':9,'待实施':4}
save(tasks_path,tasks)

audit_path=OUT/'负责人优化建议-98项最终覆盖审计.json'
audit=json.loads(audit_path.read_text(encoding='utf-8'));old_rows=copy.deepcopy(audit['rows'])
row=next(r for r in audit['rows'] if r['id']=='PAY09')
row.update(task_table_status_at_audit='进行中',declaredCurrentScope=scope,stage=scope,
           resolvedSoftware=['本人订单主动查单与重开回查，稳定任务/请求幂等/有限退避/租约恢复。',
                             '独立真实HTTP签名测试上游，严格响应和配置撤回绑定，可信结果仅应用本人关联收件。',
                             '旧/未知/失败结果不回退已付订单；账号、订单与租约最终门禁；四语及后台操作通过。'],
           softwareNotImplemented=['正式支付渠道SDK验单/查单与平台事件适配仍待实施和联调，当前协议明确为本地fixture。',
                                   '会员查询结果的订阅权益事务衔接尚未接入；迟到付款的库存/权益补偿归PAY13，不能以本轮代替。'],
           externalInputs=['正式商户、渠道协议/交易映射、受控凭据引用、订阅政策与运行环境。'],
           productionOrAcceptanceGates=['真实渠道、资金事实、目标端/网络和生产运行可靠性需另行验收。'],
           softwareAssessmentBasis='P452—P454/P501、PAY09需求表与最终双端60/19/31/16/4冻结证据。',evidence=[entry])
assert all(a==b for a,b in zip(old_rows,audit['rows']) if a['id']!='PAY09')
audit.update(verifiedLocalStages=22,updatedTaskIds=['PAY09'],currentTaskStatusCounts=counts,latestUpdateAt=stamp.isoformat())
audit['evidenceCatalog'][receipt_path.name]=entry;audit['scopedLocalStageEvidence'].append(entry)
save(audit_path,audit)
lines=['98 项当前覆盖与剩余工作','22 个本地验证阶段。进行中表示整项尚未完成，本地软件、剩余实现及正式验收分别见明细。','']
for r in audit['rows']:
    lines += [f"{r['id']} | {r['task_table_status_at_audit']} | {r['title']}",'原文段落 '+', '.join(r['source_ids']),r['declaredCurrentScope']]
    for key,title in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
        if r.get(key):lines += [title]+['- '+v for v in r[key]]
    lines += ['证据 '+v['path'] for v in r.get('evidence',[])]+['']
save(OUT/'负责人优化建议-98项最终覆盖审计.txt','\n'.join(lines)+'\n')

memory_path=OUT/'公司同步-进度与记忆.json'
memory=json.loads(memory_path.read_text(encoding='utf-8'))
memory['scope']='公司同步后原位续作PAY08、PAY09；当前源码/构建与需求表更新，旧ZIP及公开预览保留此前冻结时点。'
memory['workingRules'][1]='保留历史冻结字节。当前22阶段覆盖早期17/20/21阶段的接续时点，公开提交与旧ZIP仍按各自记录。'
memory['development']['verifiedLocalStages']=22
memory['development']['stages'].append({'stage':22,'id':'PAY09','module':'支付异常恢复与主动查单','implementation':scope,
       'receipt':entry['path'],'receiptSHA256':entry['sha256'],
       'python':{'regression':60,'special':19,'tradeCompatibility':31,'pay08Compatibility':16,'visual':4},
       'localCloud':{'regression':60,'special':19,'tradeCompatibility':31,'pay08Compatibility':16,'visual':4},
       'open':'真实渠道验单/查单、会员权益衔接和迟到资金/库存补偿尚未完成，按实际任务继续。'})
memory['development']['currentSourcesSHA256'].update(receipt['source_hashes'])
memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
memory['development']['earlierAudit']='98项审计已按冻结记录累计回填清理、注销、资金关联、密钥引用、长期记忆、多规格、客服、PAY08回调和PAY09恢复。'
memory['progress'].update(rowsWithLocalOrSandboxEvidenceIncludingPartial=67,otherRows=31,statusCounts=counts,
    note='67项有含部分覆盖的本地/沙箱证据；不是67项整项完工。进行中表示仍有软件或正式接入/验收缺口，22本地阶段为另一口径。')
for area in memory['progress']['evidenceByArea']:
    if area[0]=='支付与客服':area[2]=19
memory['progress']['workbookSha256']=sha(OUT/'东方智慧APP需求进度表-20261116.xlsx')
memory['github']['localChangesAfterPublishedCommit']='PAY08/PAY09和本轮表格/交接文件仅本目录更新，未推送或发布；仓库和Pages保持此前公司同步版本。'
memory['next']['localSoftware'][0]='继续需求表PAY05渠道能力矩阵、PAY10/PAY13迟到库存/权益补偿；PAY08和PAY09通用本地部分已有最终证据，正式适配缺口分别追踪。'
memory['packaging']['latestLocalUpdate']={'at':stamp.isoformat(),'module':'PAY09','zipRepacked':False,'originalPackageManifestUnchanged':True}
memory['savedAtBeijing']=stamp.isoformat();save(memory_path,memory)

agents=ROOT/'AGENTS.md';content=agents.read_text(encoding='utf-8')
marker='## 2026-11-16 PAY08恢复开发与本地交付'
note=('## 2026-11-16 PAY09继续实施与状态说明\n\n'
      '用户追问进行中含义并要求把需求做完，已继续完成PAY09通用本地恢复软件：本人真实HTTP签名查单、持久任务/幂等/租约/退避、配置撤回、可信结果仅消费本人收件、重开回查及四语/后台。'
      '双端完整60、专项19、原交易31、PAY08兼容16及视觉4通过。累计22个本地验证阶段，67项有本地/沙箱证据（含部分），31项未计入；进行中69、待资料16、待验收9、待实施4。\n\n'
      '进行中是整项尚未完成，不代表所有软件未做。软件缺项必须继续实施，不能笼统推给资料；本地已验收范围、真实接入和视觉/业务验收须分别说明。'
      'PAY09真实渠道验单/查单与会员权益衔接、PAY13迟到补偿仍待推进。本轮源码/03/Cloud及两表原位更新，收据为06_验证与后续工作/负责人优化建议-支付恢复-实施记录.json；旧收据/ZIP保持，未推送或生产发布。\n\n')
assert content.count(marker)==1;save(agents,content.replace(marker,note+marker))
guide=ROOT/'公司同步-先读我.txt';content=guide.read_text(encoding='utf-8')
start=content.index('本目录继续开发更新（2026-11-16）');end=content.index('一、在公司接手')
notice=('本目录继续开发更新（2026-11-16）\n'
        '已追加PAY08/PAY09通用本地软件，累计22阶段；最新PAY09双端60/19/31/16/4通过。负责人表67项含部分本地证据、31项未计入，状态69/16/9/4。'
        '进行中是整项未完工，本地已验收范围、剩余软件与正式接入/验收分别见明细。当前源码/03/Cloud及两份表已更新，真实渠道及其他软件缺项继续推进。'
        '下文原同步描述旧ZIP冻结时点；未改旧ZIP/包清单，PAY08/PAY09尚未推送或重打包。\n\n')
save(guide,content[:start]+notice+content[end:])
readme=ROOT/'README.md';content=readme.read_text(encoding='utf-8');head,rest=content.split('\n',1)
note=('2026-11-16 当前本地接续已推进PAY09：本人支付恢复与主动查单通用软件双端完整60、专项19、交易兼容31、PAY08兼容16和视觉4通过；累计22阶段。'
      '正式渠道/会员权益衔接及PAY13补偿仍待实施联调。进行中表示整项未完工，明细分别记录本地范围与剩余项。本轮未推送或重打ZIP。'
      '见 [PAY09收据](06_验证与后续工作/负责人优化建议-支付恢复-实施记录.json) 与 [使用说明](05_后台与研发说明/支付异常恢复与主动查单说明.txt)。\n\n')
save(readme,head+'\n\n'+note+rest.lstrip('\n'))
report={'at_beijing':stamp.isoformat(),'pass':True,'taskId':'PAY09','verifiedLocalStages':22,'other97TaskRowsUnchanged':True,
        'other97AuditRowsUnchanged':True,'statusCounts':counts,'rowsWithLocalOrSandboxEvidenceIncludingPartial':67,
        'notCounted':31,'backups':backups,'receiptSHA256':entry['sha256']}
target=OUT/(PREFIX+'-任务及交接回填核验.json');assert not target.exists()
target.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'pass':True,'statusCounts':counts,'report':str(target)},ensure_ascii=False))
