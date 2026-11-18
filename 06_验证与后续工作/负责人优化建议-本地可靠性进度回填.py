"""Narrow Stage31 handoff update after the frozen receipt and two verified books."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import copy,hashlib,importlib.util,json,re

ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
PREFIX='负责人优化建议-本地可靠性';IDS=['SVT01','SVT03','X03']
COUNTS={'进行中':70,'待资料':16,'待验收':9,'待实施':3}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text('utf-8'))

def checked_receipt():
    path=OUT/(PREFIX+'-实施记录.json');frozen=read(path)
    assert frozen['pass'] is True and frozen['stage']==31 and frozen['taskIds']==IDS
    assert frozen['productSourceBuildUnchanged'] is True
    helper=OUT/(PREFIX+'验收冻结.py');assert sha(helper)==frozen['freezeHelperSHA256']
    spec=importlib.util.spec_from_file_location('stage31_frozen_verifier',helper)
    verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
    current=verifier.collect()
    for key,value in frozen.items():
        if key!='at_beijing':assert value==current[key],('Frozen evidence changed',key)
    backups={}
    for label,book in [('负责人进度表','东方智慧APP需求进度表-20261116.xlsx'),('原98项任务表','东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        result=read(OUT/(PREFIX+'-'+label+'回填校验.json'))
        assert result['pass'] and result['scopePreserved'] and not result['violations']
        assert result['preservedOtherRequirements']==95 and all(i in result['scope'] for i in IDS)
        assert result['candidateSha256']==sha(OUT/book)
        assert result['originalSha256']==frozen['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/'+book]
        backup=(ROOT/result['originalPath']).resolve();assert backup.parent==OUT and backup.name.startswith(PREFIX+'-') and backup.suffix=='.xlsx'
        assert sha(backup)==result['originalSha256']
        backups[book]={'path':result['originalPath'],'sha256':result['originalSha256']}
        if label=='负责人进度表':assert result['rowsWithEvidence']==72 and result['otherRows']==26 and result['statusCounts']==COUNTS
    return path,frozen,backups

def update():
    receipt_path,receipt,book_backups=checked_receipt()
    report_path=OUT/(PREFIX+'-任务及交接回填核验.json');assert not report_path.exists()
    baseline=read(OUT/(PREFIX+'-实施前核对.json'))
    paths={'tasks':OUT/'负责人优化建议-任务拆解.json','audit':OUT/'负责人优化建议-98项最终覆盖审计.json','audit_text':OUT/'负责人优化建议-98项最终覆盖审计.txt','memory':OUT/'公司同步-进度与记忆.json','queue':OUT/'负责人优化建议-交付收尾推进.json','readme':ROOT/'公司同步-先读我.txt','rules':ROOT/'AGENTS.md'}
    original={k:p.read_bytes() for k,p in paths.items()}
    assert all(sha(p)==baseline['mutableHandoffAtStartSHA256'][p.relative_to(ROOT).as_posix()] for p in paths.values())
    tasks,audit,memory,queue=(json.loads(original[k]) for k in ('tasks','audit','memory','queue'))
    previous=copy.deepcopy((tasks,audit['rows'],audit['critical'],queue['groups']))
    assert len(tasks)==len(audit['rows'])==98
    assert len({r['id'] for r in tasks})==len({r['id'] for r in audit['rows']})==98
    assert dict(Counter(r['status'] for r in tasks))==dict(Counter(r['task_table_status_at_audit'] for r in audit['rows']))==COUNTS
    assert audit['verifiedLocalStages']==memory['development']['verifiedLocalStages']==30
    assert memory['progress']['rowsWithLocalOrSandboxEvidenceIncludingPartial']==71
    assert queue['current']=='SVT01/SVT03/X03' and queue['finalLocalChecks']['status']=='进行中'
    assert all(r['status']=='本地已验证' for r in queue['groups'])
    now=datetime.now(timezone(timedelta(hours=8)));tag=now.strftime('%Y%m%d-%H%M%S')
    entry={'path':receipt_path.relative_to(ROOT).as_posix(),'sha256':sha(receipt_path),'module':PREFIX,'pass':True,'at':receipt['at_beijing'],'scope':receipt['scope'],'limitations':receipt['limitations'],'verification':receipt['verification']}
    for row in tasks:
        if row['id'] in IDS:
            i=row['id'];assert row['status']=='进行中'
            row.update(implementation_note=receipt['taskProgress'][i],progressNote=receipt['taskProgress'][i],remainingSoftware=receipt['remainingLocalSoftware'][i],pendingExternalInputsAndAcceptance=[receipt['taskRemaining'][i]],verification_record=receipt_path.name)
            row['localEvidence']=list(dict.fromkeys(row.get('localEvidence',[])+[entry['path']]))
    for row in audit['rows']:
        if row['id'] in IDS:
            i=row['id'];assert row['task_table_status_at_audit']=='进行中'
            row.update(declaredCurrentScope=receipt['taskProgress'][i],stage=receipt['taskProgress'][i],softwareNotImplemented=receipt['remainingLocalSoftware'][i],currentSoftwareBoundary=receipt['taskBoundary'][i],externalInputs=receipt['externalInputs'][i],productionOrAcceptanceGates=[receipt['taskRemaining'][i]],unclassifiedDependencies='')
            row['resolvedSoftware']=list(dict.fromkeys(row.get('resolvedSoftware',[])+[receipt['taskProgress'][i]]))
            row['additionalEvidence']=[e for e in row.get('additionalEvidence',[]) if e.get('path')!=entry['path']]+[entry]
    assert all(a==b for a,b in zip(previous[0],tasks) if a['id'] not in IDS)
    assert all(a==b for a,b in zip(previous[1],audit['rows']) if a['id'] not in IDS)
    assert previous[2]==audit['critical'] and previous[3]==queue['groups']
    audit.update(verifiedLocalStages=31,updatedTaskIds=IDS,currentTaskStatusCounts=COUNTS,latestUpdateAt=now.isoformat())
    audit['evidenceCatalog'][receipt_path.name]=entry
    audit['scopedLocalStageEvidence']=[e for e in audit['scopedLocalStageEvidence'] if e.get('path')!=entry['path']]+[entry]
    lines=['98项当前覆盖与剩余工作','31个本地验证阶段；72项含部分本地证据不等于整项完工。','']
    for row in audit['rows']:
        lines.extend([f"{row['id']} | {row['task_table_status_at_audit']} | {row['title']}",row['declaredCurrentScope']])
        for key,label in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
            if row.get(key):lines.extend([label]+['- '+v for v in row[key]])
        lines.extend(['证据 '+e['path'] for e in row.get('evidence',[])+row.get('additionalEvidence',[])]+[''])
    memory['scope']='8组授权本地软件及登录负载/故障恢复/迁移预检/回滚本地演练完成；真实服务、正式内容规则及生产与实机验收仍按98项明细待完成。'
    memory['development']['verifiedLocalStages']=31
    memory['development']['stages'].append({'stage':31,'ids':IDS,'module':'本地可靠性与交付核验','implementation':receipt['scope'],'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'open':receipt['limitations']})
    memory['development']['currentSourcesSHA256'].update({n:h for n,h in receipt['sourceAndBuildSHA256'].items() if n.startswith('04_研发源码/') and '/node_modules/' not in n and '/generated/' not in n and '/dist/' not in n})
    memory['progress'].update(rowsWithLocalOrSandboxEvidenceIncludingPartial=72,otherRows=26,statusCounts=COUNTS,workbookSha256=sha(OUT/'东方智慧APP需求进度表-20261116.xlsx'),note='72项含部分本地/沙箱证据，非72项整项完工；31个本地阶段为另一口径。真实服务、专业资料及生产/实机另验。')
    area=[r for r in memory['progress']['evidenceByArea'] if r[0]=='跨模块'];assert len(area)==1 and area[0][2]==3;area[0][2]=4
    memory['next']['localSoftware']=list(receipt['nextActions'])
    memory['workingRules'][1]='保留历史冻结字节。当前31本地阶段覆盖早期交接时点，8组软件及本地可靠性验证完成；公开提交与旧ZIP仍按各自记录。'
    memory['packaging']['latestLocalUpdate']={'at':now.isoformat(),'module':'SVT01/SVT03/X03','zipRepacked':False,'originalPackageManifestUnchanged':True}
    memory['savedAtBeijing']=now.isoformat()
    queue['finalLocalChecks'].update(status='本地已验证',scope=receipt['scope'],receipt=entry['path'])
    queue.update(current='待真实资料与正式验收',at=now.isoformat())
    readme='当前交付：8组本地软件与SVT01/SVT03/X03本地可靠性演练已逐项验证，累计31阶段；72项含部分证据，原台账状态70/16/9/3保持。真实服务、专业规则与授权、目标地区/实机/生产验收仍待完成，不代表98项全部完成。最新结果见公司同步JSON、本地可靠性实施记录及最终交付核验；未推送、发布或重打ZIP。\n\n'+original['readme'].decode('utf-8')
    rules=original['rules'].decode('utf-8');heading='## '+now.strftime('%Y-%m-%d')+' 本地可靠性与交付核验'
    marker=re.search(r'^## .*卡组导入与本人旧例迁移回滚\s*$',rules,re.M);assert marker and heading not in rules
    rules=rules[:marker.start()]+heading+'\n\n8组本地软件和SVT01/SVT03/X03登录态完整负载、故障恢复、迁移预检及隔离回滚已有本地证据，累计31阶段、72项含部分证据；原任务状态保持70/16/9/3。实际负载、恢复及媒体覆盖以本地可靠性实施记录为准，生产/真实支付/模型、专业内容及实机另验。保留快照后已确认写入未恢复的真实差异，不冒称零丢失或正式RPO/RTO达标。未推送、发布或重打ZIP。\n\n'+rules[marker.start():]
    values={'tasks':tasks,'audit':audit,'audit_text':'\n'.join(lines)+'\n','memory':memory,'queue':queue,'readme':readme,'rules':rules};backups={}
    for k,p in paths.items():
        assert p.read_bytes()==original[k]
        backup=OUT/(PREFIX+'回填前-'+tag+'-'+p.name);assert not backup.exists();backup.write_bytes(original[k])
        backups[p.relative_to(ROOT).as_posix()]={'path':backup.relative_to(ROOT).as_posix(),'sha256':sha(backup)}
    for k,p in paths.items():
        v=values[k];p.write_bytes((v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    result={'pass':True,'at':now.isoformat(),'stage':31,'updatedTaskIds':IDS,'other95TaskAndAuditRowsPreserved':True,'counts':COUNTS,'rowsWithEvidenceIncludingPartial':72,'otherRows':26,'receipt':entry['path'],'receiptSHA256':entry['sha256'],'verification':receipt['verification'],'backups':backups,'workbookBackups':book_backups,'hashes':{n:sha(ROOT/n) for n in backups},'published':False,'zipRepacked':False}
    report_path.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'stage':31,'ids':IDS},ensure_ascii=True))

if __name__=='__main__':update()
