"""Read-only final stage27 audit; writes only a new immutable final-proof JSON.

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
PREFIX='负责人优化建议-任务告警'
IDS=['PAY18','SV04']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def verify():
    target=OUT/(PREFIX+'-最终交付核验.json')
    assert not target.exists(),'Never overwrite a final audit'
    receipt_path=OUT/(PREFIX+'-实施记录.json');receipt=read(receipt_path)
    assert receipt['pass'] is True and receipt['stage']==27 and receipt['taskIds']==IDS
    freezer_path=OUT/(PREFIX+'验收冻结.py')
    assert sha(freezer_path)==receipt['freezeHelperSHA256']
    spec=importlib.util.spec_from_file_location('stage27_final_readonly',freezer_path)
    freezer=importlib.util.module_from_spec(spec);spec.loader.exec_module(freezer)
    current=freezer.collect();verified={}
    for field in ('verification','reportIdentityHashes','source_hashes','build_hashes','buildPreparationInputHashes','runtimeArtifactSHA256','visualEvidenceSHA256','preservedHistoricalSHA256','diagnosticEvidenceSHA256','deliveryHelperSHA256'):
        assert receipt[field]==current[field],('Frozen/current discrepancy',field)
        if field!='verification':
            for name,expected in receipt[field].items():
                path=freezer.local_path(name);assert sha(path)==expected,name;verified[name]=expected
    totals={'Python':0,'Cloud':0}
    assert len(receipt['verification'])==18
    for label,gate in receipt['verification'].items():
        assert sha(freezer.local_path(gate['path']))==gate['sha256'];verified[gate['path']]=gate['sha256']
        totals['Python' if label.startswith('Python') else 'Cloud']+=gate['passed']
    assert totals=={'Python':239,'Cloud':239}
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
    assert handoff['pass'] is True and handoff['stage']==27 and handoff['receiptSHA256']==sha(receipt_path)
    assert handoff['updatedTaskIds']==IDS and handoff['other96TaskAndAuditRowsPreserved'] is True
    assert handoff['counts']=={'进行中':69,'待资料':16,'待验收':9,'待实施':4}
    assert handoff['rowsWithEvidenceIncludingPartial']==67 and handoff['otherRows']==31
    verified[handoff_path.relative_to(ROOT).as_posix()]=sha(handoff_path)
    verified[receipt_path.relative_to(ROOT).as_posix()]=sha(receipt_path)
    for name,expected in handoff['hashes'].items():
        assert sha(freezer.local_path(name))==expected;verified[name]=expected
    for field in ('preflight','fullInputPreRunSnapshot'):
        anchor=receipt[field];assert sha(freezer.local_path(anchor['path']))==anchor['sha256'];verified[anchor['path']]=anchor['sha256']
    memory=read(OUT/'公司同步-进度与记忆.json');queue=read(OUT/'负责人优化建议-交付收尾推进.json')
    assert memory['development']['verifiedLocalStages']==27 and queue['current']=='PAY05'
    assert queue['groups'][4]['status']=='本地已验证' and queue['groups'][5]['status']=='进行中'
    assert queue['groups'][4]['receipt']==receipt_path.relative_to(ROOT).as_posix()
    helper_names=[PREFIX+'依赖盘点.py',PREFIX+'验收冻结.py',PREFIX+'进度回填.py',PREFIX+'最终核验.py',PREFIX+'-进度表回填.mjs',PREFIX+'-进度表校验.py']
    guide=ROOT/'05_后台与研发说明/本地持续任务与支付异常处置说明.txt'
    helper_hashes={}
    for path in [OUT/name for name in helper_names]+[guide]:
        helper_hashes[path.relative_to(ROOT).as_posix()]=sha(path)
    verified.update(helper_hashes)
    assert target.relative_to(ROOT).as_posix() not in verified,'Final proof cannot hash itself'
    result={'pass':True,'stage':27,'at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'receiptSHA256':sha(receipt_path),'verifiedFiles':len(verified),'verifiedSHA256':verified,'sheets':sheets,
            'deliveryHelperAndGuideSHA256':helper_hashes,'allEighteenGatesPassedWithFreshSuccessfulChildren':True,
            'perBackendPassed':totals,'other96TaskAndAuditRowsPreserved':True,'oldReceiptsReportsPreviewDBUnchanged':True,
            'protectedHistoricalCount':612,'sourceAndBuildInputCount':len(receipt['reportIdentityHashes']),
            'languageScope':'四语APP由完整回归覆盖；本轮任务操作台仅中文后台、本机浏览器，非实机或藏语母语审校。',
            'paginationScope':'实际51个worker、run与告警跨50分页；通知每项有限5attempt，不伪造超过50的不可能尝试记录。',
            'runtimeScope':'显式fresh本机隔离持续进程、原状态重启恢复与真实当前管理员授权；非生产受管服务/cron。',
            'notificationScope':'签名loopback-fixture真实HTTP持久确认；externalSent=false，不宣称真实渠道失败源或外部通知。',
            'productionEnabled':False,'zipRepacked':False,'pushed':False}
    target.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'stage':27,'verifiedFiles':len(verified),'sha256':sha(target),'path':str(target)},ensure_ascii=True))


if __name__=='__main__':
    verify()
