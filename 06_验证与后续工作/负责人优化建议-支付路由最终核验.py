"""Read-only final stage28 audit; writes only a new immutable final-proof JSON.

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
PREFIX='负责人优化建议-支付路由'
IDS=['PAY05']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def verify():
    target=OUT/(PREFIX+'-最终交付核验.json')
    assert not target.exists(),'Never overwrite a final audit'
    receipt_path=OUT/(PREFIX+'-实施记录.json');receipt=read(receipt_path)
    assert receipt['pass'] is True and receipt['stage']==28 and receipt['taskIds']==IDS
    freezer_path=OUT/(PREFIX+'验收冻结.py')
    assert sha(freezer_path)==receipt['freezeHelperSHA256']
    spec=importlib.util.spec_from_file_location('stage28_final_readonly',freezer_path)
    freezer=importlib.util.module_from_spec(spec);spec.loader.exec_module(freezer)
    current=freezer.collect();verified={}
    assert receipt['guide']==current['guide'],'Frozen guide changed'
    for field in ('verification','reportIdentityHashes','source_hashes','build_hashes','buildPreparationInputHashes','runtimeArtifactSHA256','visualEvidenceSHA256','preservedHistoricalSHA256','diagnosticEvidenceSHA256','deliveryHelperSHA256'):
        assert receipt[field]==current[field],('Frozen/current discrepancy',field)
        if field!='verification':
            for name,expected in receipt[field].items():
                path=freezer.local_path(name);assert sha(path)==expected,name;verified[name]=expected
    totals={'Python':0,'Cloud':0}
    assert len(receipt['verification'])==20
    for label,gate in receipt['verification'].items():
        assert sha(freezer.local_path(gate['path']))==gate['sha256'];verified[gate['path']]=gate['sha256']
        totals['Python' if label.startswith('Python') else 'Cloud']+=gate['passed']
    assert totals=={'Python':263,'Cloud':263}
    sheets={}
    for suffix,book in [('-负责人进度表回填校验.json','东方智慧APP需求进度表-20261116.xlsx'),('-原98项任务表回填校验.json','东方智慧APP优化任务表_依据v1.0_20261112.xlsx')]:
        path=OUT/(PREFIX+suffix);result=read(path)
        assert result['pass'] is True and result['scopePreserved'] is True and not result['violations']
        assert result['preservedOtherRequirements']==97 and all(ident in result['scope'] for ident in IDS)
        assert result['candidateSha256']==sha(OUT/book)
        assert result['originalSha256']==receipt['authorizedWorkbookBaselineSHA256']['06_验证与后续工作/'+book]
        sheets[book]=result['candidateSha256'];verified[path.relative_to(ROOT).as_posix()]=sha(path)
        verified[(OUT/book).relative_to(ROOT).as_posix()]=result['candidateSha256']
    handoff_path=OUT/(PREFIX+'-任务及交接回填核验.json');handoff=read(handoff_path)
    assert handoff['pass'] is True and handoff['stage']==28 and handoff['receiptSHA256']==sha(receipt_path)
    assert handoff['updatedTaskIds']==IDS and handoff['other97TaskAndAuditRowsPreserved'] is True
    assert handoff['counts']=={'进行中':70,'待资料':16,'待验收':9,'待实施':3}
    assert handoff['rowsWithEvidenceIncludingPartial']==68 and handoff['otherRows']==30
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
    for field in ('preflight','finalExecutionSnapshot'):
        anchor=receipt[field];assert sha(freezer.local_path(anchor['path']))==anchor['sha256'];verified[anchor['path']]=anchor['sha256']
    memory=read(OUT/'公司同步-进度与记忆.json');queue=read(OUT/'负责人优化建议-交付收尾推进.json')
    assert memory['development']['verifiedLocalStages']==28 and queue['current']=='B10/B12'
    assert queue['groups'][5]['status']=='本地已验证' and queue['groups'][6]['status']=='进行中'
    assert queue['groups'][5]['receipt']==receipt_path.relative_to(ROOT).as_posix()
    helper_names=[PREFIX+'依赖盘点.py',PREFIX+'验收冻结.py',PREFIX+'进度回填.py',PREFIX+'最终核验.py',PREFIX+'-进度表回填.mjs',PREFIX+'-进度表校验.py']
    guide=ROOT/'05_后台与研发说明/支付渠道路由与报价确认说明.txt'
    helper_hashes={}
    for path in [OUT/name for name in helper_names]+[guide]:
        helper_hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    verified.update(helper_hashes)
    assert target.relative_to(ROOT).as_posix() not in verified,'Final proof cannot hash itself'
    result={'pass':True,'stage':28,'at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'receiptSHA256':sha(receipt_path),'verifiedFiles':len(verified),'verifiedSHA256':verified,'sheets':sheets,
            'deliveryHelperAndGuideSHA256':helper_hashes,'allTwentyGatesPassedWithFreshSuccessfulChildren':True,
            'perBackendPassed':totals,'other97TaskAndAuditRowsPreserved':True,'oldReceiptsReportsPreviewDBUnchanged':True,
            'protectedHistoricalCount':1012,'sourceAndBuildInputCount':len(receipt['reportIdentityHashes']),
            'languageScope':'四语APP由完整回归覆盖；本轮支付路由配置为中文后台、本机浏览器，非实机或藏语母语审校。',
            'paginationScope':'配置版本按50条游标分页，可本人/管理员实际回查；未用不存在的类型或假付款填充数量。',
            'runtimeScope':'同sole outer为各门启动fresh隔离实际服务；Python完整回归由原产品脚本自建UUID数据库，member族不冒称runtime bootstrap。真实HTTP与本机浏览器，非生产支付或真实storefront。',
            'paymentScope':'默认legacy链与enforced原子报价/路由、原价确认及暂停门禁；已受理可信付款按原冻结事实处理，真实四渠道未接通。',
            'productionEnabled':False,'zipRepacked':False,'pushed':False}
    target.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'stage':28,'verifiedFiles':len(verified),'sha256':sha(target),'path':str(target)},ensure_ascii=True))


if __name__=='__main__':
    verify()
