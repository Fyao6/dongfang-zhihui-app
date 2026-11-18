"""PAY05 handoff update, guarded by frozen final evidence and two verified books.

Import writes nothing. Product code, reports, old receipts and previous books are not changed.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import copy,hashlib,importlib.util,json,re

ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-支付路由';IDS=['PAY05']
BEFORE={'进行中':69,'待资料':16,'待验收':9,'待实施':4}
AFTER={'进行中':70,'待资料':16,'待验收':9,'待实施':3}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def checked_receipt():
    path=OUT/(PREFIX+'-实施记录.json');receipt=read(path)
    assert receipt['pass'] is True and receipt['stage']==28 and receipt['taskIds']==IDS
    helper=OUT/(PREFIX+'验收冻结.py');assert sha(helper)==receipt['freezeHelperSHA256']
    spec=importlib.util.spec_from_file_location('stage28_readonly_freezer',helper)
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier);current=verifier.collect()
    for field in ('verification','reportIdentityHashes','source_hashes','build_hashes','buildPreparationInputHashes','runtimeArtifactSHA256','runtimeArtifactEvidence','visualEvidenceSHA256','diagnosticEvidenceSHA256','finalExecutionSnapshot','preservedHistoricalSHA256','authorizedWorkbookBaselineSHA256','deliveryHelperSHA256','guide'):
        assert receipt[field]==current[field],('Frozen/current changed',field)
    book_backups={}
    for suffix,book in [('-负责人进度表回填校验.json','东方智慧APP需求进度表-20261116.xlsx'),('-原98项任务表回填校验.json','东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        result=read(OUT/(PREFIX+suffix));assert result['pass'] is True and result['scopePreserved'] is True and not result['violations']
        assert result['preservedOtherRequirements']==97 and 'PAY05' in result['scope']
        assert result['candidateSha256']==sha(OUT/book)
        assert result['originalSha256']==receipt['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/'+book]
        backup=verifier.local_path(result['originalPath'])
        assert backup.parent==OUT and backup.name.startswith(PREFIX+'-') and backup.suffix=='.xlsx'
        assert sha(backup)==result['originalSha256'],'Original workbook backup changed'
        book_backups[book]={'path':result['originalPath'],'sha256':result['originalSha256']}
        if '负责人' in suffix:assert result['rowsWithEvidence']==68 and result['otherRows']==30 and result['statusCounts']==AFTER
    return path,receipt,book_backups


def update():
    receipt_path,receipt,book_backups=checked_receipt();now=datetime.now(timezone(timedelta(hours=8)));tag=now.strftime('%Y%m%d-%H%M%S')
    report_path=OUT/(PREFIX+'-任务及交接回填核验.json');assert not report_path.exists(),'Never overwrite delivery check'
    paths={'tasks':OUT/'负责人优化建议-任务拆解.json','audit':OUT/'负责人优化建议-98项最终覆盖审计.json','audit_text':OUT/'负责人优化建议-98项最终覆盖审计.txt',
           'memory':OUT/'公司同步-进度与记忆.json','queue':OUT/'负责人优化建议-交付收尾推进.json','readme':ROOT/'公司同步-先读我.txt','rules':ROOT/'AGENTS.md'}
    original={key:path.read_bytes() for key,path in paths.items()}
    approved=read(OUT/(PREFIX+'-实施前核对.json'))['mutableHandoffAtStartSHA256']
    assert all(sha(path)==approved[path.relative_to(ROOT).as_posix()] for path in paths.values()),'Handoff changed since the authorized preflight'
    tasks,audit,memory,queue=(json.loads(original[key]) for key in ('tasks','audit','memory','queue'))
    old_tasks,old_rows,old_critical,old_queue=copy.deepcopy(tasks),copy.deepcopy(audit['rows']),copy.deepcopy(audit['critical']),copy.deepcopy(queue)
    assert len(tasks)==len(audit['rows'])==98 and len({r['id'] for r in tasks})==len({r['id'] for r in audit['rows']})==98
    assert dict(Counter(r['status'] for r in tasks))==dict(Counter(r['task_table_status_at_audit'] for r in audit['rows']))==memory['progress']['statusCounts']==audit['currentTaskStatusCounts']==BEFORE
    assert memory['development']['verifiedLocalStages']==audit['verifiedLocalStages']==27
    assert memory['progress']['rowsWithLocalOrSandboxEvidenceIncludingPartial']==67 and memory['progress']['otherRows']==31
    assert queue['current']=='PAY05' and queue['groups'][5]['ids']==IDS and queue['groups'][6]['ids']==['B10','B12']
    assert not any(r.get('stage')==28 for r in memory['development']['stages'])
    main='原沙箱链兼容、服务器固定沙箱上下文与精确矩阵、只读不可变报价、订单/预占/成交条款/路由/单次消费同事务、原价重新确认及暂停与可信付款事实隔离已本地验收；前后台按同一安全决策显示，双端各263项实际验证通过。'
    remaining=['真实Apple/Google/Stripe/PayPal适配、渠道SDK/商店验单、正式产品ID映射及真实支付/退款事件仍待实施联调。',
               'PC01/PC02主体、银行、地区、业务、币种准入资料及正式价格条款、手机实机/商店上架和生产部署/银行到账仍待完成；server_fixed_sandbox不等于实际storefront。']
    entry={'path':receipt_path.relative_to(ROOT).as_posix(),'sha256':sha(receipt_path),'module':PREFIX,'pass':True,'at':receipt['at_beijing'],
           'scope':receipt['scope'],'limitations':receipt['limitations'],'verification':[{'name':n,**v} for n,v in receipt['verification'].items()]}
    for row in tasks:
        if row['id']=='PAY05':
            assert row['status']=='待实施'
            row.update(status='进行中',implementation_note=main,progressNote=main,remainingSoftware=remaining,verification_record=receipt_path.name)
            row['localEvidence']=list(dict.fromkeys(row.get('localEvidence',[])+[entry['path']]))
    for row in audit['rows']:
        if row['id']=='PAY05':
            row.update(declaredCurrentScope=main,stage=main,task_table_status_at_audit='进行中',softwareNotImplemented=remaining,
                       currentSoftwareBoundary='本地服务器渠道框架与沙箱执行已验收；真实四渠道适配与正式准入、设备和生产环境继续按未接入或待验收。',
                       externalInputs=['PC01/PC02正式准入资料、商户和应用/商品标识、发行地区/币种/业务与价格条款确认。'],
                       productionOrAcceptanceGates=['真实渠道与商店验单、手机实机、生产部署、银行到账。'],unclassifiedDependencies='')
            row['resolvedSoftware']=list(dict.fromkeys(row.get('resolvedSoftware',[])+[main]))
            row['additionalEvidence']=[e for e in row.get('additionalEvidence',[]) if e.get('path')!=entry['path']]+[entry]
    assert all(a==b for a,b in zip(old_tasks,tasks) if a['id']!='PAY05') and all(a==b for a,b in zip(old_rows,audit['rows']) if a['id']!='PAY05')
    assert old_critical==audit['critical']
    counts=dict(Counter(r['status'] for r in tasks));assert counts==AFTER
    audit.update(verifiedLocalStages=28,updatedTaskIds=IDS,currentTaskStatusCounts=counts,latestUpdateAt=now.isoformat())
    audit['evidenceCatalog'][receipt_path.name]=entry
    audit['scopedLocalStageEvidence']=[e for e in audit['scopedLocalStageEvidence'] if e.get('path')!=entry['path']]+[entry]
    lines=['98项当前覆盖与剩余工作','28个本地验证阶段；68项含部分本地证据不等于整项完工。','']
    for row in audit['rows']:
        lines.extend([f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}",row['declaredCurrentScope']])
        for key,label in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
            if row.get(key):lines.extend([label]+['- '+v for v in row[key]])
        lines.extend(['证据 '+e['path'] for e in row.get('evidence',[])+row.get('additionalEvidence',[])]+[''])
    memory['scope']='公司同步后原位续作PAY05沙箱支付路由、服务器报价和原价确认；继续8组授权，旧ZIP与公开预览保持原冻结时点。'
    memory['development']['verifiedLocalStages']=28
    memory['development']['stages'].append({'stage':28,'ids':IDS,'module':'支付渠道路由与服务器报价','implementation':main,'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'open':'真实渠道适配/验单、当前准入、正式价格条款、手机实机与生产到账待联调验收。'})
    # Keep emitted artifacts in the actual execution/build evidence, rather than
    # retaining a stale hashed chunk/BUILD_ID under the current-source heading.
    memory['development']['currentSourcesSHA256']={n:h for n,h in memory['development']['currentSourcesSHA256'].items() if not n.startswith('03_当前APP/') and '/dist/' not in n and '/generated/' not in n}
    memory['development']['currentSourcesSHA256'].update(receipt['source_hashes']);memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
    memory['progress'].update(rowsWithLocalOrSandboxEvidenceIncludingPartial=68,otherRows=30,statusCounts=counts,workbookSha256=sha(OUT/'东方智慧APP需求进度表-20261116.xlsx'),note='68项含部分本地/沙箱证据，非68项整项完工；28本地验证阶段为另一口径。')
    area=[row for row in memory['progress']['evidenceByArea'] if row[0]=='支付与客服'];assert len(area)==1 and area[0][2]==19;area[0][2]=20
    memory['next']['localSoftware']=['继续后2组：B10/B12标准样本导入与命盘逐字段比对，再DR03/DR08卡组导入、迁移与回滚；最后补登录态并发/故障/重启/迁移恢复本地可靠性演练。',
                                      'PAY05本地矩阵与报价已验证；真实渠道SDK/验单、当前准入、外部通知及生产部署按实际缺口继续联调，未声称已接通。']
    memory['github']['localChangesAfterPublishedCommit']='PAY08/PAY09/PAY10/PAY13、MB01/AI05、SH06、PR04/PR05、PAY18/SV04、PAY05及表格交接仅本目录更新，未推送或发布。'
    memory['workingRules'][1]='保留历史冻结字节。当前28本地阶段覆盖早期交接时点，8组授权逐模块继续；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate']={'at':now.isoformat(),'module':'PAY05','zipRepacked':False,'originalPackageManifestUnchanged':True};memory['savedAtBeijing']=now.isoformat()
    queue['groups'][5].update(status='本地已验证',receipt=entry['path'])
    record=queue['groups'][5].pop('inProgressRecord',None)
    if record:queue['groups'][5]['historicalInProgressRecord']=record
    queue['groups'][6]['status']='进行中';queue.update(current='B10/B12',at=now.isoformat())
    assert all(a==b for i,(a,b) in enumerate(zip(old_queue['groups'],queue['groups'])) if i not in (5,6))
    readme='当前续作：PAY05本地渠道矩阵、服务器报价、订单路由和原价重新确认已验收，累计28阶段；68项含部分证据，状态70/16/9/3。真实四渠道、准入/价格条款、实机和生产到账仍待联调验收。下一组B10/B12样本导入与逐字段比对；未推送、未发布、未重打包。详见公司同步JSON及本模块冻结收据。\n\n'+original['readme'].decode('utf-8')
    rules=original['rules'].decode('utf-8');heading='## '+now.strftime('%Y-%m-%d')+' 支付渠道路由与报价确认'
    marker=re.search(r'^## .*本地任务持续运行与异常记录\s*$',rules,re.M);assert marker and heading not in rules
    rules=rules[:marker.start()]+heading+'\n\nPAY05默认原沙箱链、服务器声明上下文、精确矩阵与不可变报价、单次原子消费/成交路由、原价确认、暂停与可信付款事实隔离已本地验收，双端各263项。实际四渠道SDK/验单和当前准入、正式价格条款、实机及生产到账仍待完成；固定沙箱上下文不等于真实storefront。累计28阶段，68项含部分证据，状态70/16/9/3；继续B10/B12、DR03/DR08及本地可靠性演练。未推送、发布或重打包。\n\n'+rules[marker.start():]
    values={'tasks':tasks,'audit':audit,'audit_text':'\n'.join(lines)+'\n','memory':memory,'queue':queue,'readme':readme,'rules':rules};backups={}
    for key,path in paths.items():
        assert path.read_bytes()==original[key],('Concurrent update',path.name)
        backup=OUT/(PREFIX+'回填前-'+tag+'-'+path.name);assert not backup.exists();backup.write_bytes(original[key]);backups[path.relative_to(ROOT).as_posix()]={'path':backup.relative_to(ROOT).as_posix(),'sha256':sha(backup)}
    for key,path in paths.items():
        value=values[key];text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n';path.write_bytes(text.encode('utf-8'))
    result={'pass':True,'at':now.isoformat(),'stage':28,'updatedTaskIds':IDS,'other97TaskAndAuditRowsPreserved':True,'counts':counts,'rowsWithEvidenceIncludingPartial':68,'otherRows':30,
            'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'backups':backups,'workbookBackups':book_backups,'hashes':{name:sha(ROOT/name) for name in backups},'published':False,'zipRepacked':False}
    report_path.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));print(json.dumps({'pass':True,'stage':28,'updatedTasks':IDS,'statusCounts':counts},ensure_ascii=True))


if __name__=='__main__':update()
