"""DR03/DR08 handoff update, guarded by frozen final evidence and two verified books.

Import writes nothing. Product code, reports, old receipts and previous books are not changed.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import copy,hashlib,importlib.util,json,re

ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-卡组迁移';IDS=['DR03','DR08']
BEFORE={'进行中':70,'待资料':16,'待验收':9,'待实施':3}
AFTER={'进行中':70,'待资料':16,'待验收':9,'待实施':3}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def checked_receipt():
    path=OUT/(PREFIX+'-实施记录.json');receipt=read(path)
    assert receipt['pass'] is True and receipt['stage']==30 and receipt['taskIds']==IDS
    helper=OUT/(PREFIX+'验收冻结.py');assert sha(helper)==receipt['freezeHelperSHA256']
    spec=importlib.util.spec_from_file_location('stage30_readonly_freezer',helper)
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier);current=verifier.collect()
    for field in ('verification','reportIdentityHashes','source_hashes','build_hashes','buildPreparationInputHashes','runtimeArtifactSHA256','runtimeArtifactEvidence','visualEvidenceSHA256','diagnosticEvidenceSHA256','finalExecutionSnapshot','preservedHistoricalSHA256','authorizedWorkbookBaselineSHA256','deliveryHelperSHA256','guide','sourceTemplatesSHA256','historicalInputRemapping','managedBaziCompatibilityInputs','cardBuildPreparation','nodeExecutable','strictPreflight'):
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
        if '负责人' in suffix:assert result['rowsWithEvidence']==71 and result['otherRows']==27 and result['statusCounts']==AFTER
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
    assert memory['development']['verifiedLocalStages']==audit['verifiedLocalStages']==29
    assert memory['progress']['rowsWithLocalOrSandboxEvidenceIncludingPartial']==70 and memory['progress']['otherRows']==28
    assert queue['current']=='DR03/DR08' and queue['groups'][7]['ids']==IDS and queue.get('finalLocalChecks',{}).get('status','待实施')=='待实施'
    assert not any(r.get('stage')==30 for r in memory['development']['stages'])
    main='严格原字节卡组文件预览、全部问题与逐字段三语/来源差异、幂等独立待审草稿、数据库不可变版本与严重下架单调、指针激活/回滚、完整历史分页、本人旧例归档与分批续办/冲突保护撤销、私有正文擦除及epoch已本地验收；Python与本地Cloud各195项实际验证通过。'
    remaining=['最终卡种与张数、全套简繁英文案/卡面/统一卡背、作者授权、经典准确出处与真实人工审核资料待确认，不默认36张。','藏语母语审校、手机实机和生产部署另验；本地软件与合成测试不证明版权成立或正式内容通过。']
    entry={'path':receipt_path.relative_to(ROOT).as_posix(),'sha256':sha(receipt_path),'module':PREFIX,'pass':True,'at':receipt['at_beijing'],
           'scope':receipt['scope'],'limitations':receipt['limitations'],'verification':[{'name':n,**v} for n,v in receipt['verification'].items()]}
    for row in tasks:
        if row['id'] in IDS:
            assert row['status']==('待资料' if row['id']=='DR03' else '进行中')
            row.update(implementation_note=main,progressNote=main,remainingSoftware=[],pendingExternalInputsAndAcceptance=remaining,verification_record=receipt_path.name)
            row['localEvidence']=list(dict.fromkeys(row.get('localEvidence',[])+[entry['path']]))
    for row in audit['rows']:
        if row['id'] in IDS:
            row.update(declaredCurrentScope=main,stage=main,task_table_status_at_audit=('待资料' if row['id']=='DR03' else '进行中'),softwareNotImplemented=[],
                       currentSoftwareBoundary='导入诊断/来源差异、版本与指针回滚、本人旧例迁移续批与撤销工具已本地验收；正式内容、规则、授权和生产验收仍待资料。',
                       externalInputs=['正式全套简繁英、卡面/背图、版权资料、经典准确出处及最终确认卡种/张数。'],
                       productionOrAcceptanceGates=['真实人工内容/版权审核、藏语母语审校、手机实机及生产部署。'],unclassifiedDependencies='')
            row['resolvedSoftware']=list(dict.fromkeys(row.get('resolvedSoftware',[])+[main]))
            row['additionalEvidence']=[e for e in row.get('additionalEvidence',[]) if e.get('path')!=entry['path']]+[entry]
    assert all(a==b for a,b in zip(old_tasks,tasks) if a['id'] not in IDS) and all(a==b for a,b in zip(old_rows,audit['rows']) if a['id'] not in IDS)
    assert old_critical==audit['critical']
    counts=dict(Counter(r['status'] for r in tasks));assert counts==AFTER
    audit.update(verifiedLocalStages=30,updatedTaskIds=IDS,currentTaskStatusCounts=counts,latestUpdateAt=now.isoformat())
    audit['evidenceCatalog'][receipt_path.name]=entry
    audit['scopedLocalStageEvidence']=[e for e in audit['scopedLocalStageEvidence'] if e.get('path')!=entry['path']]+[entry]
    lines=['98项当前覆盖与剩余工作','30个本地验证阶段；71项含部分本地证据不等于整项完工。','']
    for row in audit['rows']:
        lines.extend([f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}",row['declaredCurrentScope']])
        for key,label in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
            if row.get(key):lines.extend([label]+['- '+v for v in row[key]])
        lines.extend(['证据 '+e['path'] for e in row.get('evidence',[])+row.get('additionalEvidence',[])]+[''])
    memory['scope']='公司同步后8组本地软件收尾已逐组验证，DR03/DR08卡组导入与旧例迁移回滚已本地验收；继续登录并发、故障/重启/迁移恢复及回滚演练。旧ZIP与公开预览保持原冻结时点。'
    memory['development']['verifiedLocalStages']=30
    memory['development']['stages'].append({'stage':30,'ids':IDS,'module':'卡组导入与本人旧例迁移回滚','implementation':main,'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'open':';'.join(remaining)})
    # Keep emitted artifacts in the actual execution/build evidence, rather than
    # retaining a stale hashed chunk/BUILD_ID under the current-source heading.
    memory['development']['currentSourcesSHA256']={n:h for n,h in memory['development']['currentSourcesSHA256'].items() if not n.startswith('03_当前APP/') and '/dist/' not in n and '/generated/' not in n}
    memory['development']['currentSourcesSHA256'].update(receipt['source_hashes']);memory['development']['currentBuildsSHA256']=dict(receipt['build_hashes'])
    memory['progress'].update(rowsWithLocalOrSandboxEvidenceIncludingPartial=71,otherRows=27,statusCounts=counts,workbookSha256=sha(OUT/'东方智慧APP需求进度表-20261116.xlsx'),note='71项含部分本地/沙箱证据，非71项整项完工；30个本地验证阶段为另一口径。DR03保持待资料，DR08保持进行中，正式内容授权与生产验收待完成。')
    area=[row for row in memory['progress']['evidenceByArea'] if row[0]=='抽卡'];assert len(area)==1 and area[0][2]==6;area[0][2]=7
    memory['next']['localSoftware']=['继续SVT01/SVT03/X03：实际登录态并发、故障/重启、迁移预检、带订单/会员/佣金/抽卡事实的备份恢复及回滚本地演练；不替代目标地区或生产容量/RPO/RTO验收。','已完成8组本地软件，正式模型/支付/客服/仓配、老师规则及标准样本、正式卡文/版权、母语及实机与生产验收按任务明细待完成。']
    memory['github']['localChangesAfterPublishedCommit']='PAY08/PAY09/PAY10/PAY13、MB01/AI05、SH06、PR04/PR05、PAY18/SV04、PAY05、B10/B12、DR03/DR08及表格交接仅本目录更新，未推送或发布。'
    memory['workingRules'][1]='保留历史冻结字节。当前30本地阶段覆盖早期交接时点，8组授权逐模块继续；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate']={'at':now.isoformat(),'module':'DR03/DR08','zipRepacked':False,'originalPackageManifestUnchanged':True};memory['savedAtBeijing']=now.isoformat()
    queue['groups'][7].update(status='本地已验证',receipt=entry['path'])
    record=queue['groups'][7].pop('inProgressRecord',None)
    if record:queue['groups'][7]['historicalInProgressRecord']=record
    queue['finalLocalChecks']={'ids':['SVT01','SVT03','X03'],'status':'进行中','scope':'本地真实登录态并发/故障重启/带业务事实备份恢复/迁移预检及回滚；生产目标另验'};queue.update(current='SVT01/SVT03/X03',at=now.isoformat())
    assert all(a==b for i,(a,b) in enumerate(zip(old_queue['groups'],queue['groups'])) if i!=7)
    readme='当前续作：DR03/DR08卡组严格文件预览、全部问题/逐字段差异、幂等草稿、不可变版本/指针回滚及本人旧例续批迁移撤销已本地验收，累计30阶段；71项含部分证据，状态70/16/9/3。8组本地软件已逐组验证，继续SVT01/SVT03/X03登录并发、故障恢复及迁移回滚本地演练。正式卡文/版权与生产验收仍待资料；未推送、未发布、未重打包。详见公司同步JSON及本模块冻结收据。\n\n'+original['readme'].decode('utf-8')
    rules=original['rules'].decode('utf-8');heading='## '+now.strftime('%Y-%m-%d')+' 卡组导入与本人旧例迁移回滚'
    marker=re.search(r'^## .*八字样本核对与冻结回放\s*$',rules,re.M);assert marker and heading not in rules
    rules=rules[:marker.start()]+heading+'\n\nDR03/DR08严格文件导入与全部诊断/来源差异、幂等独立草稿、数据库不可变版本与严重下架单调、指针回滚、完整历史分页、本人旧例归档及分批续办/保护后写的撤销、清理和闭户epoch已本地验收，双端各195项。正式全套卡文/三语/卡面/授权与最终规则仍待资料，DR03待资料、DR08进行中保持。累计30阶段，71项含部分证据；8组本地软件完成后继续SVT01/SVT03/X03可靠性演练。未推送、发布或重打包。\n\n'+rules[marker.start():]
    values={'tasks':tasks,'audit':audit,'audit_text':'\n'.join(lines)+'\n','memory':memory,'queue':queue,'readme':readme,'rules':rules};backups={}
    for key,path in paths.items():
        assert path.read_bytes()==original[key],('Concurrent update',path.name)
        backup=OUT/(PREFIX+'回填前-'+tag+'-'+path.name);assert not backup.exists();backup.write_bytes(original[key]);backups[path.relative_to(ROOT).as_posix()]={'path':backup.relative_to(ROOT).as_posix(),'sha256':sha(backup)}
    for key,path in paths.items():
        value=values[key];text=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2)+'\n';path.write_bytes(text.encode('utf-8'))
    result={'pass':True,'at':now.isoformat(),'stage':30,'updatedTaskIds':IDS,'other96TaskAndAuditRowsPreserved':True,'counts':counts,'rowsWithEvidenceIncludingPartial':71,'otherRows':27,
            'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'backups':backups,'workbookBackups':book_backups,'hashes':{name:sha(ROOT/name) for name in backups},'published':False,'zipRepacked':False}
    report_path.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));print(json.dumps({'pass':True,'stage':30,'updatedTasks':IDS,'statusCounts':counts},ensure_ascii=True))


if __name__=='__main__':update()
