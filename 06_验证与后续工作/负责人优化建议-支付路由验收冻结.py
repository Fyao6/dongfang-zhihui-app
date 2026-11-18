"""Read-only PAY05 evidence gate; only main without --inspect writes a new receipt.

No business service, regression, spreadsheet author or progress update is started.
Previous frozen bytes and every final successful outer invocation must match.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
import sys

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-支付路由'
BASELINE_SHA256='8b8a4f7fa00bda60d1f33fb8841aabcc62f9b32f4463a544b82ba047a3028b2d'
IDS=['PAY05']
SUITES=[('full','全量',60),('special','专项',32),('visual','补充视觉',4),
        ('trade-compat','交易兼容',31),('member-compat','会员兼容',29),
        ('digital-compat','数字兼容',24),('callback-compat','回调兼容',16),
        ('recovery-compat','恢复兼容',19),('late-compat','迟到兼容',20),
        ('privacy-compat','逐域兼容',28)]
ENTRIES={'special':PREFIX+'专项.cjs','visual':PREFIX+'补充视觉.cjs','trade-compat':'负责人优化建议-交易专项.cjs',
         'member-compat':'负责人优化建议-会员额度会员兼容.cjs','digital-compat':'负责人优化建议-数字权益专项.cjs',
         'callback-compat':PREFIX+'回调兼容.cjs','recovery-compat':PREFIX+'恢复兼容.cjs',
         'late-compat':PREFIX+'迟到兼容.cjs','privacy-compat':'负责人优化建议-隐私逐域专项.cjs'}
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))


def local_path(name):
    assert isinstance(name,str) and name and '\\' not in name and '\x00' not in name,name
    relative=Path(name)
    assert not relative.is_absolute() and '..' not in relative.parts,name
    path=(ROOT/relative).resolve()
    assert path.is_relative_to(ROOT) and path.is_file(),name
    return path


def hashes_match(mapping,label):
    assert isinstance(mapping,dict) and mapping,(label,'empty identity')
    for name,digest in mapping.items():
        assert sha(local_path(name))==digest,(label,'bytes differ',name)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def stamp(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    assert result.tzinfo is not None
    return result


def report_name(target,suite,title):
    return PREFIX+'-'+('本轮' if target=='python' else '公网适配')+'全量回归结果.json' if suite=='full' else PREFIX+title+'-'+target+'.json'


def collect():
    baseline_path=OUT/(PREFIX+'-实施前核对.json')
    assert sha(baseline_path)==BASELINE_SHA256,'Immutable preflight changed'
    baseline=read(baseline_path)
    hashes_match(baseline['protectedHistoricalSHA256'],'previous frozen history')
    hashes_match(baseline['authorizedWorkbookBaselineSHA256'],'books before authorized PAY05 edit') if not (OUT/(PREFIX+'-实施记录.json')).exists() else None
    inventory=load('stage28_readonly_inventory',OUT/(PREFIX+'依赖盘点.py'))
    snapshot_path=OUT/(PREFIX+'-上下文复验完整依赖诊断.json')
    snapshot=read(snapshot_path)
    current=inventory.inventory()
    for field in ('sourceAndBuildHashes','canonicalSHA256','inputCount','independentRequiredCount','harnessCount','buildPreparationInputHashes','runtimeCompilerDependencyHashes'):
        assert current[field]==snapshot[field],('Final snapshot changed',field)
    assert snapshot['pass'] is True and not snapshot['missingFromHarness'] and not snapshot['harnessAdditional']
    common=snapshot['sourceAndBuildHashes'];hashes_match(common,'final execution map')
    assert local_path('04_研发源码/app/r4/backend/payment_routing_schema.sql').read_bytes()==local_path('04_研发源码/app/cloud/generated/payment-routing-schema.sql').read_bytes(),'Shared SQL bytes diverged'
    runtime_reader=load('stage27_readonly_compiler_validator',OUT/'负责人优化建议-任务告警验收冻结.py')
    start=stamp(snapshot['at']);verification={};captures={};runtime_hashes={};runtime_evidence={};compiler_common=None;invocations=set();native={};failures=[]
    for target in ('python','cloud'):
        for suite,title,count in SUITES:
            label=('Python' if target=='python' else 'Cloud')+title
            path=OUT/report_name(target,suite,title);raw=read(path);run=raw.get('latest',raw)
            assert run['pass'] is True and run['failed']==0 and run['passed']==count,(label,'not passed or wrong count')
            rows=run['results'];assert len(rows)==count and all(row['pass'] is True for row in rows),label
            assert len({row['name'] for row in rows})==count,(label,'duplicate case labels')
            outer=run['paymentRoutingLauncher']
            assert outer['suite']==suite and outer['expectedCount']==count and outer['identityUnchanged'] is True,label
            entry=('全量回归.cjs' if target=='python' else '公网适配全量回归.cjs') if suite=='full' else ENTRIES[suite]
            assert outer['entry']=='06_验证与后续工作/'+entry,(label,'different actual entry')
            family='member' if suite=='member-compat' else 'product-full' if suite=='full' and target=='python' else 'main'
            assert outer['family']==family,(label,'different wrapper family')
            assert outer['childExitCode']==0 and outer['reportFreshForInvocation'] is True,(label,'failed child or stale report')
            assert outer['syntheticOnly'] is True and outer['productionEnabled'] is False,label
            assert outer['sourceAndBuildHashes']==common,(label,'different final execution map')
            assert outer['runId'] and outer['runId'] not in invocations,(label,'duplicate invocation')
            invocations.add(outer['runId'])
            assert stamp(outer['invocationStarted'])>=start and stamp(run['at'])>=stamp(outer['invocationStarted']),(label,'predates snapshot/start')
            if raw.get('runs'):assert raw['runs'][-1]==run,(label,'latest/history mismatch')
            compiler_run=dict(run);compiler_run['taskAlertLauncher']=outer
            artifacts,artifact_hashes,compiler=runtime_reader.validate_runtime_artifacts(compiler_run,common,target,label)
            runtime_hashes.update(artifact_hashes)
            if family=='main':
                assert outer['actualBootstrapCli'] is True,(label,'actual bootstrap missing')
                anchor=outer['manifestFile'];manifest_path=local_path(anchor['path'])
                assert anchor['path'].startswith('06_验证与后续工作/'+PREFIX+'manifest-') and sha(manifest_path)==anchor['sha256'],(label,'runtime manifest changed')
                manifest=read(manifest_path);assert manifest['productionEnabled'] is False
                assert outer['runtimeManifest']=={key:manifest[key] for key in ('core','manifestSha256')},(label,'manifest payload mismatch')
                core=manifest['core'];app='03_当前APP/东方智慧-首页体验R4.html' if target=='python' else '04_研发源码/app/cloud/generated/experience.html'
                assert core['backend']==target and core['appSha256']==common[app],(label,'actual bootstrap APP/backend mismatch')
                expected_state=ROOT/outer['ownedDatabase'] if target=='python' else ROOT/outer['ownedState']/'state'
                assert Path(core['statePath']).resolve()==expected_state.resolve(),(label,'actual owned state differs')
                runtime_hashes[anchor['path']]=anchor['sha256']
            else:
                assert outer['actualBootstrapCli'] is False and outer['runtimeManifest'] is None and outer['manifestFile'] is None,(label,'unexpected bootstrap claim')
            if target=='cloud':
                runtime_evidence[label]=artifacts
                if compiler_common is None:compiler_common=compiler
                assert compiler==compiler_common==snapshot['runtimeCompilerDependencyHashes'],(label,'compiler changed')
            if suite in ('special','visual'):
                assert run['routingSourcesUnchanged'] is True and run['routingSources']==common,(label,'inner/outer mismatch')
                native[label]={'coverage':run.get('coverage',{}),'actualRestarts':run.get('processRestarts',[]),'paginationProof':run.get('paginationProof')}
            if suite=='full':
                assert {'东方智慧-首页体验R4.html','发给负责人-东方智慧首页R4.html','计时后台-开发联调.html'}<=set(run['buildHashes']),label
                if target=='cloud':assert {'generated/experience.html','generated/admin.html','generated/review.html','lib/eastern-api.ts','worker/index.ts','dist/server/index.js'}<=set(run['cloudBuildHashes']),label
                for field,folder in [('buildHashes','03_当前APP'),('cloudBuildHashes','04_研发源码/app/cloud')]:
                    for name,digest in run.get(field,{}).items():assert sha(local_path(folder+'/'+name))==digest,(label,'build changed',name)
            for name in run.get('captures',[]):
                relative=name if name.startswith('06_') else '06_验证与后续工作/'+name
                captures[relative]=sha(local_path(relative))
            verification[label]={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'passed':count,'failed':0,'at':run['at'],'reportRunId':run.get('runId'),'launcherRunId':outer['runId'],'freshReportVerified':True,'entry':outer['entry']}
            for previous in raw.get('runs',[]):
                if previous.get('pass') is not True:failures.append({'path':path.relative_to(ROOT).as_posix(),'at':previous.get('at'),'passed':previous.get('passed'),'failed':previous.get('failed'),'failedNames':[row['name'] for row in previous.get('results',[]) if row.get('pass') is not True]})
    assert len(verification)==20 and all(sum(v['passed'] for k,v in verification.items() if k.startswith(t))==263 for t in ('Python','Cloud'))
    diagnostic={}
    for path in OUT.glob(PREFIX+'*.json'):
        if any(word in path.name for word in ('诊断','组件','入口预检','原报告前存','保全','场景','停止核验')) and path!=snapshot_path:
            diagnostic[path.relative_to(ROOT).as_posix()]=sha(path)
            document=read(path)
            for field in ('preservedReportCopiesSHA256','nativeEvidenceSHA256'):
                if document.get(field):
                    hashes_match(document[field],'preserved failure evidence '+field);diagnostic.update(document[field])
    for path in OUT.glob(PREFIX+'*构建.log'):diagnostic[path.relative_to(ROOT).as_posix()]=sha(path)
    helper_names=[PREFIX+'依赖盘点.py',PREFIX+'验收冻结.py',PREFIX+'进度回填.py',PREFIX+'最终核验.py',PREFIX+'-进度表回填.mjs',PREFIX+'-进度表校验.py']
    helpers={path.relative_to(ROOT).as_posix():sha(path) for path in [OUT/name for name in helper_names]}
    return {'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':PREFIX,'stage':28,'taskIds':IDS,'pass':True,
      'status':'local-payment-routing-and-server-quotes-verified-production-pending',
      'scope':'原沙箱链兼容、服务器固定沙箱上下文与精确规则、不可变报价及单次原子消费、成交路由快照、原价重新确认、暂停与可信付款事实隔离；前后台按真实决策展示。',
      'verification':verification,'perBackendGateCount':263,'recordedIdentityChecked':True,
      'identityMeaning':'All20 actual successful fresh child invocations bind the same complete independent pre-run execution map/current bytes. Actual Cloud bundles, compiler graph and four installed dependencies are verified separately.',
      'reportIdentityHashes':common,'source_hashes':{n:h for n,h in common.items() if not n.startswith('03_当前APP/') and '/node_modules/' not in n and '/dist/' not in n and '/generated/' not in n},
      'build_hashes':{n:sha(local_path(n)) for n in baseline['buildHashes']},'buildPreparationInputHashes':snapshot['buildPreparationInputHashes'],
      'runtimeArtifactSHA256':runtime_hashes,'runtimeArtifactEvidence':runtime_evidence,'visualEvidenceSHA256':captures,'nativeEvidence':native,
      'preservedHistoricalSHA256':baseline['protectedHistoricalSHA256'],'authorizedWorkbookBaselineSHA256':baseline['authorizedWorkbookBaselineSHA256'],
      'diagnosticEvidenceSHA256':diagnostic,'priorFailedRunsRetained':failures,'freezeHelperSHA256':sha(Path(__file__)),'deliveryHelperSHA256':helpers,
      'preflight':{'path':baseline_path.relative_to(ROOT).as_posix(),'sha256':sha(baseline_path)},
      'finalExecutionSnapshot':{'path':snapshot_path.relative_to(ROOT).as_posix(),'sha256':sha(snapshot_path),'canonicalSHA256':snapshot['canonicalSHA256'],'inputCount':snapshot['inputCount']},
      'guide':{'path':'05_后台与研发说明/支付渠道路由与报价确认说明.txt','sha256':sha(local_path('05_后台与研发说明/支付渠道路由与报价确认说明.txt'))},
      'productionEnabled':False,'productionPending':['真实支付渠道与SDK/商店验单','主体银行地区业务币种等当前准入','正式价格与法律条款','手机实机与商店上架','生产部署及银行到账'],
      'limitations':['仅本机Python/本地Cloud和合成沙箱，不证明真实商店、支付供应商、手机实机或银行到账。',
                     'server_fixed_sandbox不是实际storefront；服务器环境在批前重读，SQL核当前确认摘要/模式，但不声称多部署环境变量切换的全局原子撤回；DB paused可挡未提交的新发起。',
                     '只有三种实际商品类型；未实现的AI额度/线下/一对一分类无正向SKU可达验收，不能借客户端分类字段或标题伪装。',
                     '正式渠道适配和准入仍未完成；规则匹配或本地确认不等于真实渠道批准。藏语母语审校与原生手机验收仍待完成。',
                     '隐私交易留存与未用报价清理期限未确定时保持null；不声称清除了备份或供应商数据。'],
      'privacyBoundary':'Seven explicit new system/audit/owner domains and safe summaries; no address body duplication in quotes, no secret/session export; unknown retention null.',
      'toolchainIncludedInHandoff':False}


if __name__=='__main__':
    result=collect()
    if '--inspect' in sys.argv:print(json.dumps({'pass':True,'gates':len(result['verification']),'perBackend':263,'inputs':len(result['reportIdentityHashes'])}));sys.exit(0)
    target=OUT/(PREFIX+'-实施记录.json');assert not target.exists(),'Never overwrite frozen receipt'
    target.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'path':str(target),'sha256':sha(target),'stage':28},ensure_ascii=True))
