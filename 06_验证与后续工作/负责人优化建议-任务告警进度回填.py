"""Prepared stage27 handoff update. Requires frozen final evidence and both validated books.

Importing writes nothing. No product, QA, build, receipt or historical report is changed.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import re

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-任务告警'
IDS=['PAY18','SV04']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def checked_receipt():
    path=OUT/(PREFIX+'-实施记录.json');receipt=read(path)
    assert receipt['pass'] is True and receipt['stage']==27 and receipt['taskIds']==IDS
    source=OUT/(PREFIX+'验收冻结.py')
    assert sha(source)==receipt['freezeHelperSHA256']
    spec=importlib.util.spec_from_file_location('stage27_readonly_freezer',source)
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    current=verifier.collect()
    for field in ('verification','reportIdentityHashes','source_hashes','build_hashes','buildPreparationInputHashes','runtimeArtifactSHA256','runtimeArtifactEvidence','preservedHistoricalSHA256','authorizedWorkbookBaselineSHA256','deliveryHelperSHA256'):
        assert receipt[field]==current[field],('Frozen evidence changed',field)
    checks=[]
    for suffix,book in [('-负责人进度表回填校验.json','东方智慧APP需求进度表-20261116.xlsx'),('-原98项任务表回填校验.json','东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        result=read(OUT/(PREFIX+suffix))
        assert result['pass'] is True and result['scopePreserved'] is True and not result['violations']
        assert result['preservedOtherRequirements']==96 and all(ident in result['scope'] for ident in IDS)
        assert result['candidateSha256']==sha(OUT/book)
        assert result['originalSha256']==receipt['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/'+book]
        checks.append(result)
    assert checks[0]['rowsWithEvidence']==67 and checks[0]['otherRows']==31
    assert checks[0]['statusCounts']=={'进行中':69,'待资料':16,'待验收':9,'待实施':4}
    return path,receipt,checks


def update():
    receipt_path,receipt,checks=checked_receipt()
    stamp=datetime.now(timezone(timedelta(hours=8)));tag=stamp.strftime('%Y%m%d-%H%M%S')
    report_path=OUT/(PREFIX+'-任务及交接回填核验.json')
    assert not report_path.exists(),'Do not overwrite a delivery check'
    paths={'tasks':OUT/'负责人优化建议-任务拆解.json','audit':OUT/'负责人优化建议-98项最终覆盖审计.json',
           'audit_text':OUT/'负责人优化建议-98项最终覆盖审计.txt','memory':OUT/'公司同步-进度与记忆.json',
           'queue':OUT/'负责人优化建议-交付收尾推进.json','readme':ROOT/'公司同步-先读我.txt','rules':ROOT/'AGENTS.md'}
    original={key:path.read_bytes() for key,path in paths.items()}
    tasks,audit,memory,queue=(json.loads(original[key]) for key in ('tasks','audit','memory','queue'))
    old_tasks,old_rows,old_critical,old_queue=copy.deepcopy(tasks),copy.deepcopy(audit['rows']),copy.deepcopy(audit['critical']),copy.deepcopy(queue)
    assert len(tasks)==len(audit['rows'])==98
    assert len({r['id'] for r in tasks})==len({r['id'] for r in audit['rows']})==98
    assert all(sum(r['id']==ident for r in tasks)==sum(r['id']==ident for r in audit['rows'])==1 for ident in IDS)
    counts=dict(Counter(r['status'] for r in tasks))
    assert counts==dict(Counter(r['task_table_status_at_audit'] for r in audit['rows']))==memory['progress']['statusCounts']==audit['currentTaskStatusCounts']=={'进行中':69,'待资料':16,'待验收':9,'待实施':4}
    assert memory['development']['verifiedLocalStages']==audit['verifiedLocalStages']==26
    assert memory['progress']['rowsWithLocalOrSandboxEvidenceIncludingPartial']==67 and memory['progress']['otherRows']==31
    assert queue['current']=='PAY18/SV04' and queue['groups'][4]['ids']==IDS and queue['groups'][5]['ids']==['PAY05']
    assert not any(row.get('stage')==27 for row in memory['development']['stages'])
    main='显式fresh隔离runtime/不可变manifest、当前真实管理员session的持续任务进程与重启恢复、五白名单任务、逐单元同事务双租约和最终权限门禁、默认关闭配置、持久运行与版本化异常受理、有限HMAC本机通知重试/确认回执已本地验收；四语APP兼容、中文后台。'
    scopes={
        'SV04':main+'保留原隔离、密钥引用、停用账号等证据；恢复不重置业务attempt或伪自动登录，旧领取按原30秒租约完成，未领取单元即时重新核权。',
        'PAY18':main+'持续只读采集回调/查单积压、迟到退款待办、原对账及有限数字grant/会员已物化桶和任务链接；episode幂等、未知/截断/坏JSON不报健康0，完整同规则及目标事实才解除。'}
    remaining={
        'SV04':['远程Secrets/KMS/IAM/MFA、生产私网/TLS、数据库迁移/PITR、生产受管持续服务与定时身份、备份和恢复/回滚编排软件及目标环境验收仍待实施；本机进程不等于生产cron。',
                '真实外部告警连接器、责任人/升级策略和生产运行阈值仍待确认并实施；当前显式loopback-fixture无真实外发。'],
        'PAY18':['正式支付/退款失败与拒付事件采集连接器、真实外部通知/升级渠道、生产部署和阈值政策仍待实施联调；未知来源保持null，不冒称0失败。',
                 '本轮只读核验已存在有限grant和已物化会员事实；不自动按时补授会员桶、不自动退款，也不声称所有配额账守恒或真实渠道全覆盖。']}
    entry={'path':receipt_path.relative_to(ROOT).as_posix(),'sha256':sha(receipt_path),'module':PREFIX,'pass':True,
           'at':receipt['at_beijing'],'scope':receipt['scope'],'limitations':receipt['limitations'],
           'verification':[{'name':name,**gate} for name,gate in receipt['verification'].items()]}
    for row in tasks:
        if row['id'] in IDS:
            ident=row['id'];row.update(status='进行中',implementation_note=scopes[ident],progressNote=scopes[ident],remainingSoftware=remaining[ident])
            row['localEvidence']=list(dict.fromkeys(row.get('localEvidence',[])+[entry['path']]))
    for row in audit['rows']:
        if row['id'] in IDS:
            ident=row['id'];row.update(declaredCurrentScope=scopes[ident],stage=scopes[ident],task_table_status_at_audit='进行中',softwareNotImplemented=remaining[ident],currentSoftwareBoundary='本机持续运行与本地监测/处置/签名fixture通知已验收；生产部署、正式渠道采集和真实外部通知软件仍待实施。')
            row['resolvedSoftware']=list(dict.fromkeys(row.get('resolvedSoftware',[])+[main]))
            row['additionalEvidence']=[e for e in row.get('additionalEvidence',[]) if e.get('path')!=entry['path']]+[entry]
    for item in audit['critical']:
        if item.get('taskIds') in [[ident] for ident in IDS]:item['softwareNotImplemented']=remaining[item['taskIds'][0]]
    assert [r['id'] for r in old_tasks]==[r['id'] for r in tasks] and [r['id'] for r in old_rows]==[r['id'] for r in audit['rows']]
    assert all(a==b for a,b in zip(old_tasks,tasks) if a['id'] not in IDS)
    assert all(a==b for a,b in zip(old_rows,audit['rows']) if a['id'] not in IDS)
    assert all(a==b for a,b in zip(old_critical,audit['critical']) if not set(a.get('taskIds',[]))&set(IDS))
    assert dict(Counter(r['status'] for r in tasks))==counts
    audit.update(verifiedLocalStages=27,updatedTaskIds=IDS,currentTaskStatusCounts=counts,latestUpdateAt=stamp.isoformat())
    audit['evidenceCatalog'][receipt_path.name]=entry
    audit['scopedLocalStageEvidence']=[e for e in audit['scopedLocalStageEvidence'] if e.get('path')!=entry['path']]+[entry]
    lines=['98项当前覆盖与剩余工作','27个本地验证阶段；67项含部分本地证据不等于整项完工。','']
    for row in audit['rows']:
        lines += [f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}",row['declaredCurrentScope']]
        for key,label in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
            if row.get(key):lines += [label]+['- '+value for value in row[key]]
        lines += ['证据 '+e['path'] for e in row.get('evidence',[])+row.get('additionalEvidence',[])]+['']
    memory['scope']='公司同步后原位续作PAY18/SV04本地任务持续运行、异常处理与签名本机通知回执；继续8组授权，旧ZIP及公开预览保持原冻结时点。'
    memory['development']['verifiedLocalStages']=27
    memory['development']['stages'].append({'stage':27,'ids':IDS,'module':'本地任务持续运行与异常处理记录','implementation':main,'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'open':'正式渠道失败源、真实外部通知、生产受管服务/KMS/网络/迁移恢复及目标设备仍待实施联调验收。'})
    memory['development']['currentSourcesSHA256'].update(receipt['source_hashes'])
    memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
    memory['progress']['workbookSha256']=sha(OUT/'东方智慧APP需求进度表-20261116.xlsx')
    memory['progress']['note']='67项含部分本地/沙箱证据，非67项整项完工；27本地验证阶段为另一口径。'
    memory['next']['localSoftware']=['继续后3组：下一组PAY05平台/地区/商品渠道框架，再B10/B12样本比对与DR03/DR08卡组迁移回滚；最后补本地可靠性演练。','本机持续任务与签名loopback通知已有本地证据；正式渠道采集、真实通知、生产部署与保护域/外部清理连接器仍按实际缺口实施。']
    memory['github']['localChangesAfterPublishedCommit']='PAY08/PAY09/PAY10/PAY13、MB01/AI05、SH06、PR04/PR05、PAY18/SV04及表格交接仅本目录更新，未推送或发布。'
    memory['workingRules'][1]='保留历史冻结字节。当前27本地阶段覆盖早期交接时点，8组授权逐模块继续；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate']={'at':stamp.isoformat(),'module':'PAY18/SV04','zipRepacked':False,'originalPackageManifestUnchanged':True}
    memory['savedAtBeijing']=stamp.isoformat()
    queue['groups'][4].update(status='本地已验证',receipt=entry['path'])
    record=queue['groups'][4].pop('inProgressRecord',None)
    if record:queue['groups'][4]['historicalInProgressRecord']=record
    queue['groups'][5]['status']='进行中';queue.update(current='PAY05',at=stamp.isoformat())
    assert all(a==b for i,(a,b) in enumerate(zip(old_queue['groups'],queue['groups'])) if i not in (4,5))
    readme='当前续作：PAY18/SV04本机持续任务、只读异常监测与签名本机通知回执已通过本地验收，累计27阶段；67项含部分证据，状态69/16/9/4。生产受管服务、正式渠道失败源和真实外部通知仍待实施，不伪生产cron或真实退款。下一组PAY05平台/地区/商品渠道框架；未推送、未发布、未重打包。详细见公司同步JSON及本模块冻结收据。\n\n'+original['readme'].decode('utf-8')
    rules=original['rules'].decode('utf-8');heading='## '+stamp.strftime('%Y-%m-%d')+' 本地任务持续运行与异常记录'
    marker=re.search(r'^## .*本人资料逐域清点与清理\s*$',rules,re.M)
    assert marker and heading not in rules
    rules=rules[:marker.start()]+heading+'\n\nPAY18/SV04本机持续任务、显式fresh manifest与当前真实授权、逐单元双租约、只读本地异常监测、版本化受理及有限签名loopback通知回执已验收。四语APP兼容，后台中文。未知/截断来源不报健康0；真实渠道失败源、外部通知及生产受管部署仍待实施。累计27阶段，67项含部分证据，状态69/16/9/4；按8组授权继续PAY05。未推送、发布或重打包。\n\n'+rules[marker.start():]
    values={'tasks':tasks,'audit':audit,'audit_text':'\n'.join(lines)+'\n','memory':memory,'queue':queue,'readme':readme,'rules':rules}
    backups={}
    for key,path in paths.items():
        assert path.read_bytes()==original[key],('Concurrent update',path.name)
        backup=OUT/(PREFIX+'回填前-'+tag+'-'+path.name);assert not backup.exists();backup.write_bytes(original[key])
        backups[path.relative_to(ROOT).as_posix()]={'path':backup.relative_to(ROOT).as_posix(),'sha256':sha(backup)}
    for key,path in paths.items():
        value=values[key];text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n';path.write_bytes(text.encode('utf-8'))
    result={'pass':True,'at':stamp.isoformat(),'stage':27,'updatedTaskIds':IDS,'other96TaskAndAuditRowsPreserved':True,'counts':counts,'rowsWithEvidenceIncludingPartial':67,'otherRows':31,'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'backups':backups,'hashes':{name:sha(ROOT/name) for name in backups},'published':False,'zipRepacked':False}
    report_path.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'stage':27,'updatedTasks':IDS,'statusCounts':counts},ensure_ascii=True))


if __name__=='__main__':
    update()
