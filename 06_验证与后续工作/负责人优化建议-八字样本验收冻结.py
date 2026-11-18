"""Read-only B10/B12 evidence gate; only main without --inspect writes a new receipt.

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
PREFIX='负责人优化建议-八字样本'
BASELINE_SHA256='00733f154ceebd034847e8837e5b574f6fa9d5f4830dbd990caa61085e72913f'
IDS=['B10','B12']
SUITES=[('full','全量',60),('special','专项',40),('visual','补充视觉',4),('b11-compat','B11兼容',11),('interpretation-compat','解读兼容',16),('privacy-compat','逐域兼容',28),('closure-compat','注销兼容',27)]
ENTRIES={'special':PREFIX+'专项.cjs','visual':PREFIX+'补充视觉.cjs','b11-compat':PREFIX+'B11兼容.cjs','interpretation-compat':PREFIX+'解读兼容.cjs','privacy-compat':'负责人优化建议-隐私逐域专项.cjs','closure-compat':PREFIX+'注销兼容.cjs'}
FINAL_SNAPSHOT=PREFIX+'-round4完整依赖诊断.json'
STRICT_PREFLIGHT='06_验证与后续工作/负责人优化建议-八字样本入口预检-all-mwk2yyy6-b6aeaef7.json'
STRICT_PREFLIGHT_SHA256='a194473e3f708a1d59b3961d4ce1f9a580661929fabc28ad190c1c001c2cdbf6'
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
    baseline_path=OUT/(PREFIX+'-实施前核对-rev2.json')
    assert sha(baseline_path)==BASELINE_SHA256,'Immutable preflight changed'
    baseline=read(baseline_path)
    hashes_match(baseline['protectedHistoricalSHA256'],'previous frozen history')
    hashes_match(baseline['authorizedWorkbookBaselineSHA256'],'books before authorized B10/B12 edit') if not (OUT/(PREFIX+'-实施记录.json')).exists() else None
    inventory=load('stage29_readonly_inventory',OUT/(PREFIX+'依赖盘点.py'))
    snapshot_path=OUT/FINAL_SNAPSHOT
    snapshot=read(snapshot_path)
    current=inventory.inventory()
    for field in ('sourceAndBuildHashes','canonicalSHA256','inputCount','independentRequiredCount','harnessCount','buildPreparationInputHashes','runtimeCompilerDependencyHashes','managedSourceReadHashes','sampleBuildPreparation','nodeExecutable'):
        assert current[field]==snapshot[field],('Final snapshot changed',field)
    assert snapshot['pass'] is True and not snapshot['missingFromHarness'] and not snapshot['harnessAdditional']
    common=snapshot['sourceAndBuildHashes'];hashes_match(common,'final execution map')
    preflight_path=local_path(STRICT_PREFLIGHT);assert sha(preflight_path)==STRICT_PREFLIGHT_SHA256
    preflight=read(preflight_path)
    assert preflight['pass'] is True and preflight['formalAcceptance'] is False and preflight['preparationOnly'] is False and preflight['incompleteMap'] is False
    assert len(preflight['results'])==4 and all(row['pass'] is True for row in preflight['results']) and len(preflight['entries'])==14
    assert preflight['sourceAndBuildHashes']==common and preflight['canonicalSHA256']==snapshot['canonicalSHA256']
    full_selection=preflight['pythonFullDatabaseSelection']
    assert full_selection['namespaceMatchesFreshBranch'] is True and full_selection['legacyNamedDatabaseSelected'] is False and full_selection['actualSourceAstVerified'] is True and full_selection['opensOrCreatesDatabase'] is False
    assert full_selection['sourceSha256']==common['06_验证与后续工作/全量回归.cjs']

    assert local_path('04_研发源码/app/r4/backend/bazi_samples_schema.sql').read_bytes()==local_path('04_研发源码/app/cloud/generated/bazi-samples-schema.sql').read_bytes(),'Shared SQL bytes diverged'
    source=read(local_path('04_研发源码/app/r4/bazi-sample-source-manifest.json'))
    hashes_match(source['sourceHashes'],'actual managed source manifest')
    assert source['implementationReady'] is True and source['teacherConfirmed'] is False and len(source['sourceHashes'])==21
    assert source['sourceHashes']==snapshot['managedSourceReadHashes']
    core={key:value for key,value in source.items() if key!='manifestSha256'}
    assert hashlib.sha256(json.dumps(core,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()==source['manifestSha256']
    assert local_path('04_研发源码/app/r4/bazi-sample-source-manifest.json').read_bytes()==local_path('04_研发源码/app/cloud/generated/bazi-sample-source-manifest.json').read_bytes()
    descriptor=read(local_path('04_研发源码/app/cloud/generated/bazi-sample-server-manifest.json'))
    assert descriptor['implementationReady'] and descriptor['sourceBindingVerified'] and descriptor['sourceManifest']==source
    assert descriptor['sourceManifestSha256']==source['manifestSha256'] and descriptor['appSha256']==sha(local_path('04_研发源码/app/cloud/generated/experience.html'))
    marker=('<meta name="ew-bazi-sample-source" content="'+source['manifestSha256']+'">').encode('utf-8')
    assert all(marker in local_path(name).read_bytes() for name in ('03_当前APP/东方智慧-首页体验R4.html','04_研发源码/app/cloud/generated/experience.html'))
    runtime_reader=load('stage27_readonly_compiler_validator',OUT/'负责人优化建议-任务告警验收冻结.py')
    start=stamp(snapshot['at']);verification={};captures={};runtime_hashes={};runtime_evidence={};compiler_common=None;invocations=set();native={};failures=[]
    preflight_artifacts,preflight_runtime,preflight_compiler=runtime_reader.validate_runtime_artifacts({'runtimeArtifacts':preflight['artifacts']},common,'cloud','严格入口预检Cloud')
    assert preflight_compiler==snapshot['runtimeCompilerDependencyHashes']
    runtime_hashes.update(preflight_runtime);runtime_evidence['严格入口预检Cloud']=preflight_artifacts

    for target in ('python','cloud'):
        for suite,title,count in SUITES:
            label=('Python' if target=='python' else 'Cloud')+title
            path=OUT/report_name(target,suite,title);raw=read(path);run=raw.get('latest',raw)
            assert run['pass'] is True and run['failed']==0 and run['passed']==count,(label,'not passed or wrong count')
            rows=run['results'];assert len(rows)==count and all(row['pass'] is True for row in rows),label
            assert len({row['name'] for row in rows})==count,(label,'duplicate case labels')
            outer=run['baziSampleLauncher']
            assert outer['suite']==suite and outer['expectedCount']==count and outer['identityUnchanged'] is True,label
            entry=('全量回归.cjs' if target=='python' else '公网适配全量回归.cjs') if suite=='full' else ENTRIES[suite]
            assert outer['entry']=='06_验证与后续工作/'+entry,(label,'different actual entry')
            family='closure' if suite=='closure-compat' else 'product-full' if suite=='full' and target=='python' else 'main'
            assert outer['family']==family,(label,'different wrapper family')
            assert outer['childExitCode']==0 and outer['reportFreshForInvocation'] is True,(label,'failed child or stale report')
            assert outer['syntheticOnly'] is True and outer['productionEnabled'] is False,label
            assert outer['sourceAndBuildHashes']==common,(label,'different final execution map')
            assert outer['buildPreparationInputs']==snapshot['sampleBuildPreparation'],(label,'managed FS input binding changed')
            configured=outer['configuredNodeRuntime'];assert configured['sha256']==snapshot['nodeExecutable']['sha256'] and configured['toolchainIncludedInHandoff'] is False,(label,'Node executable differs')
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
                assert run['baziSampleSourcesUnchanged'] is True and run['baziSampleSources']==common,(label,'inner/outer mismatch')
                native[label]={'coverage':run.get('coverage',{}),'actualRestarts':run.get('sampleProcessRestarts',[]),'paginationProof':run.get('paginationProof')}
            if suite=='full':
                assert {'东方智慧-首页体验R4.html','发给负责人-东方智慧首页R4.html','计时后台-开发联调.html'}<=set(run['buildHashes']),label
                if target=='cloud':assert {'generated/experience.html','generated/admin.html','generated/review.html','lib/eastern-api.ts','worker/index.ts','dist/server/index.js'}<=set(run['cloudBuildHashes']),label
                for field,folder in [('buildHashes','03_当前APP'),('cloudBuildHashes','04_研发源码/app/cloud')]:
                    for name,digest in run.get(field,{}).items():assert sha(local_path(folder+'/'+name))==digest,(label,'build changed',name)
            # Shared full runners retain deterministic screenshot names. Bind every
            # final actual capture after checking freshness; earlier attempts are
            # preserved under separate byte-copy names before any retry.
            if suite=='full':
                full_captures=[p for p in OUT.glob(PREFIX+'-'+target+'-*') if p.suffix.lower() in {'.png','.webm'}]
                assert full_captures,(label,'full native captures missing')
                for capture in full_captures:
                    assert capture.stat().st_mtime>=stamp(outer['invocationStarted']).timestamp(),(label,'stale full screenshot',capture.name)
                    captures[capture.relative_to(ROOT).as_posix()]=sha(capture)
                api_name=PREFIX+('-前后端接口实测证据.json' if target=='python' else '-公网适配接口实测证据.json')
                api_path=OUT/api_name;assert read(api_path)['at']==run['at'],(label,'stale browser HTTP evidence')
                captures[api_path.relative_to(ROOT).as_posix()]=sha(api_path)
                for name in run.get('baziExperience',{}).get('captures',[]):
                    assert '06_验证与后续工作/'+name in captures,(label,'Bazi capture not in final native map',name)
            for name in run.get('captures',[]):
                relative=name if name.startswith('06_') else '06_验证与后续工作/'+name
                captures[relative]=sha(local_path(relative))
            verification[label]={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'passed':count,'failed':0,'at':run['at'],'reportRunId':run.get('runId'),'launcherRunId':outer['runId'],'freshReportVerified':True,'entry':outer['entry']}
            for previous in raw.get('runs',[]):
                if previous.get('pass') is not True:failures.append({'path':path.relative_to(ROOT).as_posix(),'at':previous.get('at'),'passed':previous.get('passed'),'failed':previous.get('failed'),'failedNames':[row['name'] for row in previous.get('results',[]) if row.get('pass') is not True]})
    assert len(verification)==14 and all(sum(v['passed'] for k,v in verification.items() if k.startswith(t))==186 for t in ('Python','Cloud'))
    diagnostic={}
    for path in OUT.glob(PREFIX+'*.json'):
        if any(word in path.name for word in ('诊断','组件','入口预检','原报告前存','保全','场景','停止核验')) and path!=snapshot_path:
            diagnostic[path.relative_to(ROOT).as_posix()]=sha(path)
            document=read(path)
            for field in ('preservedReportCopiesSHA256','nativeEvidenceSHA256'):
                if document.get(field):
                    hashes_match(document[field],'preserved failure evidence '+field);diagnostic.update(document[field])
    for path in OUT.glob(PREFIX+'*构建.log'):diagnostic[path.relative_to(ROOT).as_posix()]=sha(path)
    # Keep actual component/author/test source bytes as evidence without claiming
    # their standalone scripts were executed by every formal gate.
    for path in OUT.glob(PREFIX+'*'):
        if path.is_file() and path.suffix in {'.py','.cjs','.mjs','.ts'}:
            diagnostic[path.relative_to(ROOT).as_posix()]=sha(path)
    helper_names=[PREFIX+'依赖盘点.py',PREFIX+'验收冻结.py',PREFIX+'进度回填.py',PREFIX+'最终核验.py',PREFIX+'-进度表回填.mjs',PREFIX+'-进度表校验.py']
    helpers={path.relative_to(ROOT).as_posix():sha(path) for path in [OUT/name for name in helper_names]}
    return {'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':PREFIX,'stage':29,'taskIds':IDS,'pass':True,
      'status':'local-sample-import-replay-field-diff-and-native-view-verified-teacher-pending',
      'scope':'本人管理员原字节样本导入、冻结运行、服务端同实现重算、完整原始分段、逐字段差异与追加分类建议、原生APP临时独立核对及隐私擦除/epoch；老师标准确认独立待完成；补修Cloud完整引用树深度与传统解读原生无重定向兼容。',
      'verification':verification,'perBackendGateCount':186,'recordedIdentityChecked':True,
      'identityMeaning':'All14 actual successful fresh child invocations bind the same complete independent pre-run execution map/current bytes. Actual Cloud bundles, compiler graph and four installed dependencies are verified separately.',
      'reportIdentityHashes':common,'source_hashes':{n:h for n,h in common.items() if not n.startswith('03_当前APP/') and '/node_modules/' not in n and '/dist/' not in n and '/generated/' not in n},
      'build_hashes':{n:sha(local_path(n)) for n in baseline['buildHashes']},'buildPreparationInputHashes':snapshot['buildPreparationInputHashes'],
      'runtimeArtifactSHA256':runtime_hashes,'runtimeArtifactEvidence':runtime_evidence,'visualEvidenceSHA256':captures,'nativeEvidence':native,
      'preservedHistoricalSHA256':baseline['protectedHistoricalSHA256'],'authorizedWorkbookBaselineSHA256':baseline['authorizedWorkbookBaselineSHA256'],
      'diagnosticEvidenceSHA256':diagnostic,'priorFailedRunsRetained':failures,'freezeHelperSHA256':sha(Path(__file__)),'deliveryHelperSHA256':helpers,
      'preflight':{'path':baseline_path.relative_to(ROOT).as_posix(),'sha256':sha(baseline_path)},
      'strictPreflight':{'path':STRICT_PREFLIGHT,'sha256':STRICT_PREFLIGHT_SHA256,'actualStartupChecks':4,'fullDatabaseSelection':full_selection},
      'finalExecutionSnapshot':{'path':snapshot_path.relative_to(ROOT).as_posix(),'sha256':sha(snapshot_path),'canonicalSHA256':snapshot['canonicalSHA256'],'inputCount':snapshot['inputCount']},
      'guide':{'path':'05_后台与研发说明/八字样本核对与临时视图说明.txt','sha256':sha(local_path('05_后台与研发说明/八字样本核对与临时视图说明.txt'))},
      'sampleTemplate':{'path':'02_需求与设计参考/八字样本导入模板-合成未确认.json','sha256':sha(local_path('02_需求与设计参考/八字样本导入模板-合成未确认.json')),'teacherConfirmed':False},
      'managedSourceReadHashes':snapshot['managedSourceReadHashes'],'sampleBuildPreparation':snapshot['sampleBuildPreparation'],'nodeExecutable':snapshot['nodeExecutable'],
      'productionEnabled':False,'teacherConfirmed':False,'teacherConfirmedCaseCount':0,'professionalAgreementRate':None,
      'productionPending':['老师规则与至少30个确认样本','约定规则下专业字段一致率目标的正式验收','藏语母语审校','手机实机及生产部署'],
      'limitations':['本机Python/本地Cloud/合成样本与真实浏览器的软件证据，不证明老师标准一致、预测效果或手机实机。',
                     '同库复算证明实现和字段映射可重复，不是独立专业正确性标准；所有teacherApproval为未核实声明。',
                     '服务端domStatus始终not_run；原生DOM由本地独立浏览器证据证明，不新增DOM上传审批。',
                     '默认规范导出精确去除已知称呼路径，原指纹对应原冻结内容；自由文本不因此匿名。',
                     '最小处理哈希与审计未知留存期限为null，不宣称备份或供应商已删除。'],
      'privacyBoundary':'Twelve explicit private/system/audit domains with same-transaction real privacy receipts, private-body erase and epoch fences; no public seed/model sending/localStorage sample caching.',
      'toolchainIncludedInHandoff':False}


if __name__=='__main__':
    result=collect()
    if '--inspect' in sys.argv:print(json.dumps({'pass':True,'gates':len(result['verification']),'perBackend':186,'inputs':len(result['reportIdentityHashes'])}));sys.exit(0)
    target=OUT/(PREFIX+'-实施记录.json');assert not target.exists(),'Never overwrite frozen receipt'
    target.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'path':str(target),'sha256':sha(target),'stage':29},ensure_ascii=True))
