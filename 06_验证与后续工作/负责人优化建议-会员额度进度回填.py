"""Update current task/handoff records only after a frozen MB01/AI05 gate."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import copy,hashlib,json
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'06_验证与后续工作';PREFIX='负责人优化建议-会员额度'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def update():
    stamp=datetime.now(timezone(timedelta(hours=8)));tag=stamp.strftime('%Y%m%d-%H%M%S');backups={}
    receipt_path=OUT/(PREFIX+'-实施记录.json');receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    assert receipt['pass'] and receipt['stage']==24
    for name,expected in {**receipt['source_hashes'],**receipt['build_hashes']}.items():assert sha(ROOT/name)==expected,name
    for suffix in ['-负责人进度表回填校验.json','-原98项任务表回填校验.json']:
        report=json.loads((OUT/(PREFIX+suffix)).read_text(encoding='utf-8'));assert report.get('pass',report.get('scopePreserved')) is True,suffix
    def save(path,value):
        backup=OUT/(PREFIX+'回填前-'+tag+'-'+path.name);assert not backup.exists();backup.write_bytes(path.read_bytes())
        backups[path.relative_to(ROOT).as_posix()]={'path':backup.relative_to(ROOT).as_posix(),'sha256':sha(backup)}
        path.write_bytes(((json.dumps(value,ensure_ascii=False,indent=2)+'\n') if not isinstance(value,str) else value).encode())
    main='会员AI周期额度本地软件已验收：已付不可变快照与UTC锚定周期、独立额度桶、服务端来源、唯一发放和原子预占结算；提前续期不早发，取消保留已付期，暂停不重发，退款/到期在途原桶closing，来源粘连不改扣独立测试余额。'
    scopes={'MB01':'统一SKU会员方案与不可变版本、有限周期和逐项权益配置已有证据。'+main+'正式方案、价格和额度规则尚待确认，生产仍关闭。',
            'AI05':'既有独立测试credits预占/一次结算、用量和未知成本记录保持。'+main+'本人导出与四语APP与中文后台已接入，真实供应商成本对账待联调。'}
    remaining={'MB01':['正式会员价格、周期额度及渠道适配、真实支付验单与生产权益须按确认规则实际联调。'],
               'AI05':['真实模型/供应商费用、正式会员政策及生产渠道的结算与费用核对仍待实际接入验收。']}
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
            row.update(declaredCurrentScope=scopes[row['id']],stage=scopes[row['id']],task_table_status_at_audit='进行中',softwareNotImplemented=remaining[row['id']],currentSoftwareBoundary='会员AI周期额度本地软件已验收；正式政策、供应商与生产接入另行验收。')
            row['resolvedSoftware']=row.get('resolvedSoftware',[])+[main]
            row['additionalEvidence']=row.get('additionalEvidence',[])+[entry]
    assert all(a==b for a,b in zip(old,audit['rows']) if a['id'] not in scopes)
    audit.update(verifiedLocalStages=24,updatedTaskIds=list(scopes),currentTaskStatusCounts=counts,latestUpdateAt=stamp.isoformat())
    audit['evidenceCatalog'][receipt_path.name]=entry;audit['scopedLocalStageEvidence'].append(entry);save(path,audit)
    lines=['98项当前覆盖与剩余工作','24个本地验证阶段；67项含部分本地证据不等于整项完工。','']
    for row in audit['rows']:
        lines += [f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}",row['declaredCurrentScope']]
        for key,title in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
            if row.get(key):lines += [title]+['- '+v for v in row[key]]
        lines += ['证据 '+v['path'] for v in row.get('evidence',[])+row.get('additionalEvidence',[])]+['']
    save(OUT/'负责人优化建议-98项最终覆盖审计.txt','\n'.join(lines)+'\n')
    path=OUT/'公司同步-进度与记忆.json';memory=json.loads(path.read_text(encoding='utf-8'))
    assert memory['development']['verifiedLocalStages']==23
    memory['scope']='公司同步后原位续作会员AI周期额度；按用户授权继续8组本地收尾，旧ZIP与公开预览保持原冻结时点。'
    memory['development']['verifiedLocalStages']=24
    memory['development']['stages'].append({'stage':24,'ids':['MB01','AI05'],'module':'会员AI周期额度','implementation':main,'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'open':'正式会员规则、真实供应商与支付渠道和生产环境仍待联调验收。'})
    memory['development']['currentSourcesSHA256'].update(receipt['source_hashes']);memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
    memory['progress']['workbookSha256']=sha(OUT/'东方智慧APP需求进度表-20261116.xlsx')
    memory['progress']['note']='67项含部分本地/沙箱证据，非67项整项完工；24本地验证阶段为另一口径。'
    memory['next']['localSoftware']=['按06/负责人优化建议-交付收尾推进.json继续后6组：下一组数字权益次数期限，再隐私逐域清理、内部监控、渠道框架、样本比对与卡组工具，最后本地可靠性演练。','已完成支付可靠收件/恢复/迟到补偿和会员周期额度的通用本地软件；真实渠道、正式政策和生产运行分别追踪。']
    memory['github']['localChangesAfterPublishedCommit']='PAY08/PAY09/PAY10/PAY13及MB01/AI05与本轮表格交接仅本目录更新，未推送或发布。'
    memory['workingRules'][1]='保留历史冻结字节。当前24本地阶段覆盖早期交接时点，8组授权逐模块继续；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate']={'at':stamp.isoformat(),'module':'MB01/AI05','zipRepacked':False,'originalPackageManifestUnchanged':True}
    memory['savedAtBeijing']=stamp.isoformat();save(path,memory)
    path=OUT/'负责人优化建议-交付收尾推进.json';queue=json.loads(path.read_text(encoding='utf-8'));queue['groups'][1].update(status='本地已验证',receipt=entry['path']);queue['groups'][2]['status']='进行中';queue['current']='SH06';queue['at']=stamp.isoformat();save(path,queue)
    path=ROOT/'公司同步-先读我.txt';text=path.read_text(encoding='utf-8');save(path,'当前续作：MB01/AI05会员AI周期额度已通过本地验收，累计24阶段；67项含部分证据，状态69/16/9/4。8组收尾按序继续，下一组数字权益次数与期限。会员测试额度不等于正式AI/收费接通；未推送、未重打包。详细见公司同步JSON及本模块冻结收据。\n\n'+text)
    path=ROOT/'AGENTS.md';text=path.read_text(encoding='utf-8');marker='## 2026-11-16 交付收尾授权与迟到补偿';assert marker in text
    text=text.replace(marker,'## 2026-11-16 会员AI周期额度\n\nMB01/AI05已通过本地验收：已付成交快照周期额度、独立来源桶、唯一发放、原子预占结算、取消/暂停/退款/到期在途处理、本人导出及四语APP和中文后台。累计24阶段，67项含部分证据、状态69/16/9/4；正式政策、真实供应商/支付及生产运行待联调。继续用户已授权8组收尾，下一组SH06数字权益次数期限；完整队列见06_验证与后续工作/负责人优化建议-交付收尾推进.json。未推送或重打包。\n\n'+marker,1);save(path,text)
    target=OUT/(PREFIX+'-任务及交接回填核验.json');assert not target.exists();target.write_bytes((json.dumps({'pass':True,'at':stamp.isoformat(),'stage':24,'updatedTaskIds':list(scopes),'other96TaskAndAuditRowsPreserved':True,'counts':counts,'backups':backups,'hashes':{name:sha(ROOT/name) for name in backups}},ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'pass':True,'stage':24,'updatedTasks':list(scopes),'statusCounts':counts},ensure_ascii=False))

if __name__=='__main__':update()
