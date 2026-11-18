"""Read-only final stage29 audit; writes only a new immutable final-proof JSON.

There is deliberately no directory glob of current delivery JSON: the proof is
not one of its own inputs and cannot acquire a circular self-hash.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-八字样本'
IDS=['B10','B12']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def verify():
    target=OUT/(PREFIX+'-最终交付核验.json')
    assert not target.exists(),'Never overwrite a final audit'
    receipt_path=OUT/(PREFIX+'-实施记录.json');receipt=read(receipt_path)
    assert receipt['pass'] is True and receipt['stage']==29 and receipt['taskIds']==IDS
    freezer_path=OUT/(PREFIX+'验收冻结.py')
    assert sha(freezer_path)==receipt['freezeHelperSHA256']
    spec=importlib.util.spec_from_file_location('stage29_final_readonly',freezer_path)
    freezer=importlib.util.module_from_spec(spec);spec.loader.exec_module(freezer)
    current=freezer.collect();verified={}
    assert receipt['guide']==current['guide'],'Frozen guide changed'
    for field in ('sampleTemplate','managedSourceReadHashes','sampleBuildPreparation','nodeExecutable','strictPreflight'):
        assert receipt[field]==current[field],('Stage29 identity metadata changed',field)
    for field in ('verification','reportIdentityHashes','source_hashes','build_hashes','buildPreparationInputHashes','runtimeArtifactSHA256','visualEvidenceSHA256','preservedHistoricalSHA256','diagnosticEvidenceSHA256','deliveryHelperSHA256'):
        assert receipt[field]==current[field],('Frozen/current discrepancy',field)
        if field!='verification':
            for name,expected in receipt[field].items():
                path=freezer.local_path(name);assert sha(path)==expected,name;verified[name]=expected
    totals={'Python':0,'Cloud':0}
    assert len(receipt['verification'])==14
    for label,gate in receipt['verification'].items():
        assert sha(freezer.local_path(gate['path']))==gate['sha256'];verified[gate['path']]=gate['sha256']
        totals['Python' if label.startswith('Python') else 'Cloud']+=gate['passed']
    assert totals=={'Python':186,'Cloud':186}
    sheets={}
    for suffix,book in [('-负责人进度表回填校验.json','东方智慧APP需求进度表-20261116.xlsx'),('-原98项任务表回填校验.json','东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        path=OUT/(PREFIX+suffix);result=read(path)
        assert result['pass'] is True and result['scopePreserved'] is True and not result['violations']
        assert result['preservedOtherRequirements']==96 and all(ident in result['scope'] for ident in IDS)
        assert result['candidateSha256']==sha(OUT/book)
        assert result['originalSha256']==receipt['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/'+book]
        sheets[book]=result['candidateSha256'];verified[path.relative_to(ROOT).as_posix()]=sha(path)
        verified[(OUT/book).relative_to(ROOT).as_posix()]=result['candidateSha256']
    handoff_path=OUT/(PREFIX+'-任务及交接回填核验.json');handoff=read(handoff_path)
    assert handoff['pass'] is True and handoff['stage']==29 and handoff['receiptSHA256']==sha(receipt_path)
    assert handoff['updatedTaskIds']==IDS and handoff['other96TaskAndAuditRowsPreserved'] is True
    assert handoff['counts']=={'进行中':70,'待资料':16,'待验收':9,'待实施':3}
    assert handoff['rowsWithEvidenceIncludingPartial']==70 and handoff['otherRows']==28
    verified[handoff_path.relative_to(ROOT).as_posix()]=sha(handoff_path)
    verified[receipt_path.relative_to(ROOT).as_posix()]=sha(receipt_path)
    for name,expected in handoff['hashes'].items():
        assert sha(freezer.local_path(name))==expected;verified[name]=expected
    preflight=read(freezer.local_path(receipt['preflight']['path']))
    assert len(handoff['backups'])==7 and len(handoff['workbookBackups'])==2
    for name,anchor in handoff['backups'].items():
        assert anchor['sha256']==preflight['mutableHandoffAtStartSHA256'][name]
        assert sha(freezer.local_path(anchor['path']))==anchor['sha256'],'Original handoff backup changed'
        verified[anchor['path']]=anchor['sha256']
    for book,anchor in handoff['workbookBackups'].items():
        assert anchor['sha256']==receipt['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/'+book]
        assert sha(freezer.local_path(anchor['path']))==anchor['sha256'],'Original workbook backup changed'
        verified[anchor['path']]=anchor['sha256']
    for field in ('preflight','finalExecutionSnapshot','strictPreflight'):
        anchor=receipt[field];assert sha(freezer.local_path(anchor['path']))==anchor['sha256'];verified[anchor['path']]=anchor['sha256']
    memory=read(OUT/'公司同步-进度与记忆.json');queue=read(OUT/'负责人优化建议-交付收尾推进.json')
    assert memory['development']['verifiedLocalStages']==29 and queue['current']=='DR03/DR08'
    assert queue['groups'][6]['status']=='本地已验证' and queue['groups'][7]['status']=='进行中'
    assert queue['groups'][6]['receipt']==receipt_path.relative_to(ROOT).as_posix()
    helper_names=[PREFIX+'依赖盘点.py',PREFIX+'验收冻结.py',PREFIX+'进度回填.py',PREFIX+'最终核验.py',PREFIX+'-进度表回填.mjs',PREFIX+'-进度表校验.py']
    guide=ROOT/'05_后台与研发说明/八字样本核对与临时视图说明.txt'
    helper_hashes={}
    for path in [OUT/name for name in helper_names]+[guide,ROOT/'02_需求与设计参考/八字样本导入模板-合成未确认.json']:
        helper_hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    verified.update(helper_hashes)
    assert target.relative_to(ROOT).as_posix() not in verified,'Final proof cannot hash itself'
    result={'pass':True,'stage':29,'at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'receiptSHA256':sha(receipt_path),'verifiedFiles':len(verified),'verifiedSHA256':verified,'sheets':sheets,
            'deliveryHelperAndGuideSHA256':helper_hashes,'allFourteenGatesPassedWithFreshSuccessfulChildren':True,
            'perBackendPassed':totals,'other96TaskAndAuditRowsPreserved':True,'oldReceiptsReportsPreviewDBUnchanged':True,
            'protectedHistoricalCount':len(receipt['preservedHistoricalSHA256']),'sourceAndBuildInputCount':len(receipt['reportIdentityHashes']),
            'languageScope':'四语APP由本轮完整回归和补充视觉覆盖；后台为中文，本机真实浏览器不代表手机实机或藏语母语审校。',
            'paginationScope':'版本/结果/字段与追加分类历史各50条游标分页；全部选择取完整冻结case顺序，完整原始运表按period读取与校验。',
            'runtimeScope':'sole outer fresh隔离真实HTTP与本机浏览器；Python full及closure族用原自管fresh脚本，closure编译元数据来自实际子报告；Node配置身份与实际子进程证据分开。',
            'sampleScope':'原始UTF8导入、同实现固定asOf回放、逐字段差异与临时原生核对，本地合成样本不代表老师标准批准。',
            'teacherConfirmed':False,'teacherConfirmedCaseCount':0,'professionalAgreementRate':None,
            'productionEnabled':False,'zipRepacked':False,'pushed':False}
    target.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'stage':29,'verifiedFiles':len(verified),'sha256':sha(target),'path':str(target)},ensure_ascii=True))


if __name__=='__main__':
    verify()
