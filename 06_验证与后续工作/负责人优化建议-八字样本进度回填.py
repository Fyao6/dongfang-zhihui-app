"""B10/B12 handoff update, guarded by frozen final evidence and two verified books.

Import writes nothing. Product code, reports, old receipts and previous books are not changed.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import copy,hashlib,importlib.util,json,re

ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-八字样本';IDS=['B10','B12']
BEFORE={'进行中':70,'待资料':16,'待验收':9,'待实施':3}
AFTER={'进行中':70,'待资料':16,'待验收':9,'待实施':3}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def checked_receipt():
    path=OUT/(PREFIX+'-实施记录.json');receipt=read(path)
    assert receipt['pass'] is True and receipt['stage']==29 and receipt['taskIds']==IDS
    helper=OUT/(PREFIX+'验收冻结.py');assert sha(helper)==receipt['freezeHelperSHA256']
    spec=importlib.util.spec_from_file_location('stage29_readonly_freezer',helper)
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier);current=verifier.collect()
    for field in ('verification','reportIdentityHashes','source_hashes','build_hashes','buildPreparationInputHashes','runtimeArtifactSHA256','runtimeArtifactEvidence','visualEvidenceSHA256','diagnosticEvidenceSHA256','finalExecutionSnapshot','preservedHistoricalSHA256','authorizedWorkbookBaselineSHA256','deliveryHelperSHA256','guide','sampleTemplate','managedSourceReadHashes','sampleBuildPreparation','nodeExecutable','strictPreflight'):
        assert receipt[field]==current[field],('Frozen/current changed',field)
    book_backups={}
    for suffix,book in [('-负责人进度表回填校验.json','东方智慧APP需求进度表-20261116.xlsx'),('-原98项任务表回填校验.json','东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        result=read(OUT/(PREFIX+suffix));assert result['pass'] is True and result['scopePreserved'] is True and not result['violations']
        assert result['preservedOtherRequirements']==96 and all(identifier in result['scope'] for identifier in IDS)
        assert result['candidateSha256']==sha(OUT/book)
        assert result['originalSha256']==receipt['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/'+book]
        backup=verifier.local_path(result['originalPath'])
        assert backup.parent==OUT and backup.name.startswith(PREFIX+'-') and backup.suffix=='.xlsx'
        assert sha(backup)==result['originalSha256'],'Original workbook backup changed'
        book_backups[book]={'path':result['originalPath'],'sha256':result['originalSha256']}
        if '负责人' in suffix:assert result['rowsWithEvidence']==70 and result['otherRows']==28 and result['statusCounts']==AFTER
    return path,receipt,book_backups


def update():
    receipt_path,receipt,book_backups=checked_receipt();now=datetime.now(timezone(timedelta(hours=8)));tag=now.strftime('%Y%m%d-%H%M%S')
    report_path=OUT/(PREFIX+'-任务及交接回填核验.json');assert not report_path.exists(),'Never overwrite delivery check'
    paths={'tasks':OUT/'负责人优化建议-任务拆解.json','audit':OUT/'负责人优化建议-98项最终覆盖审计.json','audit_text':OUT/'负责人优化建议-98项最终覆盖审计.txt',
           'memory':OUT/'公司同步-进度与记忆.json','queue':OUT/'负责人优化建议-交付收尾推进.json','readme':ROOT/'公司同步-先读我.txt','rules':ROOT/'AGENTS.md'}
    original={key:path.read_bytes() for key,path in paths.items()}
    approved=read(OUT/(PREFIX+'-实施前核对-rev2.json'))['mutableHandoffAtStartSHA256']
    assert all(sha(path)==approved[path.relative_to(ROOT).as_posix()] for path in paths.values()),'Handoff changed since the authorized preflight'
    tasks,audit,memory,queue=(json.loads(original[key]) for key in ('tasks','audit','memory','queue'))
    old_tasks,old_rows,old_critical,old_queue=copy.deepcopy(tasks),copy.deepcopy(audit['rows']),copy.deepcopy(audit['critical']),copy.deepcopy(queue)
    assert len(tasks)==len(audit['rows'])==98 and len({r['id'] for r in tasks})==len({r['id'] for r in audit['rows']})==98
    assert dict(Counter(r['status'] for r in tasks))==dict(Counter(r['task_table_status_at_audit'] for r in audit['rows']))==memory['progress']['statusCounts']==audit['currentTaskStatusCounts']==BEFORE
    assert memory['development']['verifiedLocalStages']==audit['verifiedLocalStages']==28
    assert memory['progress']['rowsWithLocalOrSandboxEvidenceIncludingPartial']==68 and memory['progress']['otherRows']==30
    assert queue['current']=='B10/B12' and queue['groups'][6]['ids']==IDS and queue['groups'][7]['ids']==['DR03','DR08']
    assert not any(r.get('stage')==29 for r in memory['development']['stages'])
    main='本人管理员原字节样本导入、冻结运行、服务端重算、完整运表分段、逐字段差异与追加分类建议、原生APP临时独立核对、样本私有正文清理及epoch已本地验收；Python与本地Cloud各186项实际验证通过。'
    remaining=['老师规则、神煞口径与至少30个确认样本尚待资料，之后按可信同规则标准进行专业差异定位、修复与复验。',
               '老师确认数0、专业一致率未评定；藏语母语审校、手机实机与生产部署另验。本地同实现回放不代表专业算法已验证。']
    entry={'path':receipt_path.relative_to(ROOT).as_posix(),'sha256':sha(receipt_path),'module':PREFIX,'pass':True,'at':receipt['at_beijing'],
           'scope':receipt['scope'],'limitations':receipt['limitations'],'verification':[{'name':n,**v} for n,v in receipt['verification'].items()]}
    for row in tasks:
        if row['id'] in IDS:
            assert row['status']=='待资料'
            row.update(implementation_note=main,progressNote=main,remainingSoftware=[],pendingExternalInputsAndAcceptance=remaining,verification_record=receipt_path.name)
            row['localEvidence']=list(dict.fromkeys(row.get('localEvidence',[])+[entry['path']]))
    for row in audit['rows']:
        if row['id'] in IDS:
            row.update(declaredCurrentScope=main,stage=main,task_table_status_at_audit='待资料',softwareNotImplemented=[],
                       currentSoftwareBoundary='样本导入、回放、差异与原生临时核对工具已本地验收；老师标准、专业差异修复与正式一致率验收待资料后继续。',
                       externalInputs=['老师确认的规则/神煞口径、至少30个普通与边界标准样本及可核验批准来源。'],
                       productionOrAcceptanceGates=['约定规则下专业字段一致率目标验收、藏语母语审校、手机实机及生产部署。'],unclassifiedDependencies='')
            row['resolvedSoftware']=list(dict.fromkeys(row.get('resolvedSoftware',[])+[main]))
            row['additionalEvidence']=[e for e in row.get('additionalEvidence',[]) if e.get('path')!=entry['path']]+[entry]
    assert all(a==b for a,b in zip(old_tasks,tasks) if a['id'] not in IDS) and all(a==b for a,b in zip(old_rows,audit['rows']) if a['id'] not in IDS)
    assert old_critical==audit['critical']
    counts=dict(Counter(r['status'] for r in tasks));assert counts==AFTER
    audit.update(verifiedLocalStages=29,updatedTaskIds=IDS,currentTaskStatusCounts=counts,latestUpdateAt=now.isoformat())
    audit['evidenceCatalog'][receipt_path.name]=entry
    audit['scopedLocalStageEvidence']=[e for e in audit['scopedLocalStageEvidence'] if e.get('path')!=entry['path']]+[entry]
    lines=['98项当前覆盖与剩余工作','29个本地验证阶段；70项含部分本地证据不等于整项完工。','']
    for row in audit['rows']:
        lines.extend([f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}",row['declaredCurrentScope']])
        for key,label in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
            if row.get(key):lines.extend([label]+['- '+v for v in row[key]])
        lines.extend(['证据 '+e['path'] for e in row.get('evidence',[])+row.get('additionalEvidence',[])]+[''])
    memory['scope']='公司同步后原位续作B10/B12样本导入、冻结回放、逐字段差异与APP临时核对；继续8组授权，旧ZIP与公开预览保持原冻结时点。'
    memory['development']['verifiedLocalStages']=29
    memory['development']['stages'].append({'stage':29,'ids':IDS,'module':'八字样本核对与冻结回放','implementation':main,'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'open':'老师规则、至少30个确认样本及专业一致率目标仍待资料后正式验收，藏语母语及手机实机另验。'})
    # Keep emitted artifacts in the actual execution/build evidence, rather than
    # retaining a stale hashed chunk/BUILD_ID under the current-source heading.
    memory['development']['currentSourcesSHA256']={n:h for n,h in memory['development']['currentSourcesSHA256'].items() if not n.startswith('03_当前APP/') and '/dist/' not in n and '/generated/' not in n}
    memory['development']['currentSourcesSHA256'].update(receipt['source_hashes']);memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
    memory['progress'].update(rowsWithLocalOrSandboxEvidenceIncludingPartial=70,otherRows=28,statusCounts=counts,workbookSha256=sha(OUT/'东方智慧APP需求进度表-20261116.xlsx'),note='70项含部分本地/沙箱证据，非70项整项完工；29本地验证阶段为另一口径。B10/B12软件工具有证据，状态仍待资料。')
    area=[row for row in memory['progress']['evidenceByArea'] if row[0]=='八字与排盘'];assert len(area)==1 and area[0][2]==7;area[0][2]=9
    memory['next']['localSoftware']=['继续最后1组DR03/DR08：卡组批量校验、导入与旧收藏迁移/回滚；之后补登录态并发、故障、重启、迁移恢复/回滚的本地可靠性演练。',
                                      'B10/B12样本工具已本地验证，老师标准与专业差异复验仍待资料，不声称专业算法、藏语母语或手机实机已验收。']
    memory['github']['localChangesAfterPublishedCommit']='PAY08/PAY09/PAY10/PAY13、MB01/AI05、SH06、PR04/PR05、PAY18/SV04、PAY05、B10/B12及表格交接仅本目录更新，未推送或发布。'
    memory['workingRules'][1]='保留历史冻结字节。当前29本地阶段覆盖早期交接时点，8组授权逐模块继续；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate']={'at':now.isoformat(),'module':'B10/B12','zipRepacked':False,'originalPackageManifestUnchanged':True};memory['savedAtBeijing']=now.isoformat()
    queue['groups'][6].update(status='本地已验证',receipt=entry['path'])
    record=queue['groups'][6].pop('inProgressRecord',None)
    if record:queue['groups'][6]['historicalInProgressRecord']=record
    queue['groups'][7]['status']='进行中';queue.update(current='DR03/DR08',at=now.isoformat())
    assert all(a==b for i,(a,b) in enumerate(zip(old_queue['groups'],queue['groups'])) if i not in (6,7))
    readme='当前续作：B10/B12样本导入、冻结回放、逐字段差异、追加分类建议和APP临时核对已本地验收，累计29阶段；70项含部分证据，状态70/16/9/3。B10/B12仍待老师规则及至少30个确认样本，专业一致率未评定。下一组DR03/DR08卡组导入与迁移回滚，然后做本地可靠性演练；未推送、未发布、未重打包。详见公司同步JSON及本模块冻结收据。\n\n'+original['readme'].decode('utf-8')
    rules=original['rules'].decode('utf-8');heading='## '+now.strftime('%Y-%m-%d')+' 八字样本核对与冻结回放'
    marker=re.search(r'^## .*支付渠道路由与报价确认\s*$',rules,re.M);assert marker and heading not in rules
    rules=rules[:marker.start()]+heading+'\n\nB10/B12本人管理员样本导入、冻结运行、服务端重算、完整原始分段、逐字段差异与追加分类建议、原生APP临时核对及清理epoch已本地验收，双端各186项。老师确认数0、专业一致率未评定；至少30个标准样本/规则、藏语母语与手机实机仍待完成，状态保持待资料。累计29阶段，70项含部分证据；继续DR03/DR08及本地可靠性演练。未推送、发布或重打包。\n\n'+rules[marker.start():]
    values={'tasks':tasks,'audit':audit,'audit_text':'\n'.join(lines)+'\n','memory':memory,'queue':queue,'readme':readme,'rules':rules};backups={}
    for key,path in paths.items():
        assert path.read_bytes()==original[key],('Concurrent update',path.name)
        backup=OUT/(PREFIX+'回填前-'+tag+'-'+path.name);assert not backup.exists();backup.write_bytes(original[key]);backups[path.relative_to(ROOT).as_posix()]={'path':backup.relative_to(ROOT).as_posix(),'sha256':sha(backup)}
    for key,path in paths.items():
        value=values[key];text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n';path.write_bytes(text.encode('utf-8'))
    result={'pass':True,'at':now.isoformat(),'stage':29,'updatedTaskIds':IDS,'other96TaskAndAuditRowsPreserved':True,'counts':counts,'rowsWithEvidenceIncludingPartial':70,'otherRows':28,
            'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'backups':backups,'workbookBackups':book_backups,'hashes':{name:sha(ROOT/name) for name in backups},'published':False,'zipRepacked':False}
    report_path.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));print(json.dumps({'pass':True,'stage':29,'updatedTasks':IDS,'statusCounts':counts},ensure_ascii=True))


if __name__=='__main__':update()
