"""Update current task/handoff records only after a frozen PAY10/PAY13 gate."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import copy,hashlib,json
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'06_验证与后续工作';PREFIX='负责人优化建议-迟到补偿'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def update():
    stamp=datetime.now(timezone(timedelta(hours=8)));tag=stamp.strftime('%Y%m%d-%H%M%S');backups={}
    receipt_path=OUT/(PREFIX+'-实施记录.json');receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    assert receipt['pass'] and receipt['stage']==23
    for name,expected in {**receipt['source_hashes'],**receipt['build_hashes']}.items():assert sha(ROOT/name)==expected,name
    for suffix in ['-负责人进度表回填校验.json','-原98项任务表回填校验.json']:
        report=json.loads((OUT/(PREFIX+suffix)).read_text(encoding='utf-8'));assert report.get('pass',report.get('scopePreserved')) is True,suffix
    def save(path,value):
        backup=OUT/(PREFIX+'回填前-'+tag+'-'+path.name);assert not backup.exists();backup.write_bytes(path.read_bytes())
        backups[path.relative_to(ROOT).as_posix()]={'path':backup.relative_to(ROOT).as_posix(),'sha256':sha(backup)}
        path.write_bytes(((json.dumps(value,ensure_ascii=False,indent=2)+'\n') if not isinstance(value,str) else value).encode())
    main='迟到付款通用本地补偿已验收：到期本单释放后逐SKU重核、按原价全量原子扣库与唯一数字权益；缺货/绑定变化持久退款待办、管理员幂等受理和本人回查。过期本人真实HTTP查单接入同一可信收件。受理不等于真实退款或到账。'
    scopes={
      'PAY08':'通用本地回调可靠接收、去重/租约/退避与数字实物结算已有证据；本轮追加迟到付款补偿。'+main,
      'PAY09':'通用本地主动查单与持久恢复已有证据；本轮支持过期订单查询，并区分补偿履约与退款待办。'+main,
      'PAY10':'沙箱订单/权益原子发放、幂等与普通退款调整已有证据。'+main+'有限次数/期限数字权益仍归SH06继续实施。',
      'PAY13':'原子预占、并发防超卖、付款扣库及15分钟到期释放已有证据。'+main}
    remaining={
      'PAY08':['正式渠道验签/事件规范与会员回调适配仍待实施联调。','生产常驻消费、监控和真实退款资金衔接尚未验收。'],
      'PAY09':['正式渠道SDK验单/查单和会员订阅事务适配仍待实施联调。','本轮已支持通用迟到补偿；真实退款执行和到账确认仍待渠道。'],
      'PAY10':['正式渠道与会员回调事务适配、真实退款执行和到账状态衔接仍待实施联调。','有限次数/期限独立数字权益的消耗与最终访问门禁仍需继续实现，见SH06。'],
      'PAY13':['正式渠道迟到通知/查单及真实退款执行、到账回执仍待联调。','生产消费者常驻运行和异常监控仍需继续部署验收。']}
    entry={'path':receipt_path.relative_to(ROOT).as_posix(),'sha256':sha(receipt_path),'module':PREFIX,'pass':True,'at':receipt['at_beijing'],'scope':receipt['scope'],'limitations':receipt['limitations'],'verification':[{'name':k,**v} for k,v in receipt['verification'].items()]}
    path=OUT/'负责人优化建议-任务拆解.json';tasks=json.loads(path.read_text(encoding='utf-8'));old=copy.deepcopy(tasks)
    for row in tasks:
        if row['id'] in scopes:
            row.update(status='进行中',implementation_note=scopes[row['id']],progressNote=scopes[row['id']],remainingSoftware=remaining[row['id']])
            row['localEvidence']=list(dict.fromkeys(row.get('localEvidence',[])+[entry['path']]))
    assert all(a==b for a,b in zip(old,tasks) if a['id'] not in scopes)
    counts=dict(Counter(r['status'] for r in tasks));assert counts=={'进行中':69,'待资料':16,'待验收':9,'待实施':4};save(path,tasks)
    path=OUT/'负责人优化建议-98项最终覆盖审计.json';audit=json.loads(path.read_text(encoding='utf-8'));old=copy.deepcopy(audit['rows'])
    for row in audit['rows']:
        if row['id'] in scopes:
            row.update(declaredCurrentScope=scopes[row['id']],stage=scopes[row['id']],task_table_status_at_audit='进行中',softwareNotImplemented=remaining[row['id']],currentSoftwareBoundary='通用本地迟到路径已验收；正式适配/资金与其他软件缺口分列。')
            row['resolvedSoftware']=row.get('resolvedSoftware',[])+[main]
            row['additionalEvidence']=row.get('additionalEvidence',[])+[entry]
    assert all(a==b for a,b in zip(old,audit['rows']) if a['id'] not in scopes)
    audit.update(verifiedLocalStages=23,updatedTaskIds=list(scopes),currentTaskStatusCounts=counts,latestUpdateAt=stamp.isoformat())
    audit['evidenceCatalog'][receipt_path.name]=entry;audit['scopedLocalStageEvidence'].append(entry);save(path,audit)
    lines=['98项当前覆盖与剩余工作','23个本地验证阶段；67项含部分本地证据不等于整项完工。','']
    for row in audit['rows']:
        lines += [f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}",row['declaredCurrentScope']]
        for key,title in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
            if row.get(key):lines += [title]+['- '+v for v in row[key]]
        lines += ['证据 '+v['path'] for v in row.get('evidence',[])+row.get('additionalEvidence',[])]+['']
    save(OUT/'负责人优化建议-98项最终覆盖审计.txt','\n'.join(lines)+'\n')
    path=OUT/'公司同步-进度与记忆.json';memory=json.loads(path.read_text(encoding='utf-8'))
    assert memory['development']['verifiedLocalStages']==22
    memory['scope']='公司同步后原位续作PAY08/PAY09及PAY10/PAY13迟到补偿；按用户授权继续8组本地收尾，旧ZIP与公开预览保持原冻结时点。'
    memory['development']['verifiedLocalStages']=23
    memory['development']['stages'].append({'stage':23,'ids':['PAY10','PAY13'],'module':'迟到付款补偿','implementation':main,'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'open':'正式渠道、真实退款到账、生产调度和会员适配仍待实施或验收。'})
    memory['development']['currentSourcesSHA256'].update(receipt['source_hashes']);memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
    memory['progress']['workbookSha256']=sha(OUT/'东方智慧APP需求进度表-20261116.xlsx')
    memory['progress']['note']='67项含部分本地/沙箱证据，非67项整项完工；23本地验证阶段为另一口径。'
    memory['next']['localSoftware']=['按06/负责人优化建议-交付收尾推进.json继续后7组：下一组会员AI额度周期，再数字权益次数期限、隐私逐域清理、内部监控、渠道框架、样本比对与卡组工具。','PAY08/PAY09及PAY10/PAY13通用本地路径已有证据；真实渠道与会员适配、真实退款和生产运行分别追踪。']
    memory['github']['localChangesAfterPublishedCommit']='PAY08/PAY09/PAY10/PAY13与本轮表格交接仅本目录更新，未推送或发布。'
    memory['workingRules'][1]='保留历史冻结字节。当前23本地阶段覆盖早期交接时点，8组授权逐模块继续；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate']={'at':stamp.isoformat(),'module':'PAY10/PAY13','zipRepacked':False,'originalPackageManifestUnchanged':True}
    memory['savedAtBeijing']=stamp.isoformat();save(path,memory)
    path=OUT/'负责人优化建议-交付收尾推进.json';queue=json.loads(path.read_text(encoding='utf-8'));queue['groups'][0].update(status='本地已验证',receipt=entry['path']);queue['groups'][1]['status']='进行中';queue['current']='MB01/AI05';queue['at']=stamp.isoformat();save(path,queue)
    path=ROOT/'公司同步-先读我.txt';text=path.read_text(encoding='utf-8');save(path,'当前续作：PAY10/PAY13迟到补偿已通过本地验收，累计23阶段；67项含部分证据，状态69/16/9/4。8组收尾按序继续，下一组会员AI额度周期。退款待办不等于实际退款到账；未推送、未重打包。详细见公司同步JSON及本模块冻结收据。\n\n'+text)
    path=ROOT/'AGENTS.md';text=path.read_text(encoding='utf-8');marker='## 2026-11-16 PAY09继续实施与状态说明';assert marker in text
    text=text.replace(marker,'## 2026-11-16 交付收尾授权与迟到补偿\n\n用户在8组本地软件清单后明确说“那就开始呀”，已授权按序完成；每模块双端完整回归及相关专项通过再推进。PAY10/PAY13通用迟到补偿完成本地验收：重核库存、原价原子接续、缺货退款待办/管理员幂等受理/本人回查，过期主动查单接同一可信路径。累计23本地阶段，67项含部分证据，状态69/16/9/4。正式渠道、真实退款到账、会员适配和生产运行仍有缺口。下一组MB01/AI05，完整队列见06_验证与后续工作/负责人优化建议-交付收尾推进.json。旧ZIP/收据保留，未推送发布。\n\n'+marker,1);save(path,text)
    target=OUT/(PREFIX+'-任务及交接回填核验.json');assert not target.exists();target.write_bytes((json.dumps({'pass':True,'at':stamp.isoformat(),'stage':23,'updatedTaskIds':list(scopes),'other94TaskAndAuditRowsPreserved':True,'counts':counts,'backups':backups,'hashes':{name:sha(ROOT/name) for name in backups}},ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'pass':True,'stage':23,'updatedTasks':list(scopes),'statusCounts':counts},ensure_ascii=False))

if __name__=='__main__':update()
