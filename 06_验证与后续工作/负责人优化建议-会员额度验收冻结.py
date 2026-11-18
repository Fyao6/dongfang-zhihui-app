"""Freeze MB01/AI05 only after current dual-backend gates; preserve history."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib,json

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-会员额度'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def freeze():
    specs=[('Python全量','-本轮全量回归结果.json',60),('Cloud全量','-公网适配全量回归结果.json',60),
           ('Python专项','专项-python.json',21),('Cloud专项','专项-cloud.json',21),
           ('Python交易兼容','交易兼容-python.json',31),('Cloud交易兼容','交易兼容-cloud.json',31),
           ('Python会员兼容','会员兼容-python.json',29),('Cloud会员兼容','会员兼容-cloud.json',29),
           ('Python网关兼容','网关兼容-python.json',25),('Cloud网关兼容','网关兼容-cloud.json',25),
           ('Python补充视觉','补充视觉-python.json',4),('Cloud补充视觉','补充视觉-cloud.json',4)]
    verification,images,build_checks,failures={},{},[],[]
    for label,suffix,minimum in specs:
        path=OUT/(PREFIX+suffix);raw=json.loads(path.read_text(encoding='utf-8'));run=raw.get('latest',raw)
        assert run['pass'] is True and run.get('failed',0)==0,(label,'not passed')
        assert len(run['results'])>=minimum and all(x['pass'] is True for x in run['results']),(label,'gate count')
        assert run.get('identityUnchanged',True),(label,'identity changed')
        launcher=run.get('membershipQuotaLauncher',{});assert launcher.get('identityUnchanged') is True,(label,'launcher did not verify final identity')
        for name,expected in launcher.get('sourceAndBuildHashes',{}).items():assert sha(ROOT/name)==expected,(label,name)
        for field in ['quotaSources','membershipQuotaSources','membershipSources','gatewaySources','sourceHashes']:
            for name,expected in run.get(field,{}).items():assert sha(ROOT/name)==expected,(label,name)
        for group in run.get('identity',{}).values():
            if isinstance(group,dict):
                for name,expected in group.items():
                    if isinstance(expected,str) and len(expected)==64:assert sha(ROOT/name)==expected,(label,name)
        for field,base in [('buildHashes',ROOT/'03_当前APP'),('cloudBuildHashes',ROOT/'04_研发源码/app/cloud')]:
            for name,expected in run.get(field,{}).items():
                p=base/name;actual=sha(p);assert actual==expected,(label,p)
                build_checks.append({'gate':label,'path':p.relative_to(ROOT).as_posix(),'expected':expected,'actual':actual})
        for name in run.get('captures',[]):
            p=OUT/name;images[p.relative_to(ROOT).as_posix()]=sha(p)
        verification[label]={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'passed':len(run['results']),'failed':0,'at':run.get('at'),'runId':run.get('runId')}
        for item in raw.get('runs',[]):
            if item.get('pass') is not True:failures.append({'report':path.name,'at':item.get('at'),'passed':item.get('passed'),'failed':item.get('failed'),'failedNames':[x['name'] for x in item.get('results',[]) if x.get('pass') is not True]})
    assert len(build_checks)>=12,'Missing actual full-regression build identities'
    baseline=json.loads((OUT/(PREFIX+'-实施前核对.json')).read_text(encoding='utf-8'))
    preserved={}
    for name,expected in baseline['files'].items():
        if name.startswith('06_'):
            actual=sha(ROOT/name);assert actual==expected,('Historical record or preview DB changed',name);preserved[name]=actual
    sources=['04_研发源码/app/r4/'+name for name in ['membership-ai-quota-ui.js','membership-ai-quota-admin.js','membership-lifecycle-ui.js','membership-lifecycle-ui.css','ai-gateway-ui.js','ai-gateway-ui.css','ai-gateway-admin.js','commerce-ui.js','account-closure.js','build.py']]
    sources+=['04_研发源码/app/r4/backend/'+name for name in ['membership_ai_quota.py','membership_lifecycle.py','ai_gateway.py','server.py','account_write_guard.py','privacy.py']]
    sources+=['04_研发源码/app/cloud/lib/'+name for name in ['membership-ai-quota.ts','membership-lifecycle.ts','ai-gateway.ts','eastern-api.ts','account-write-guard.ts','privacy-api.ts']]
    sources+=['04_研发源码/app/cloud/prepare.py','06_验证与后续工作/全量回归.cjs','06_验证与后续工作/公网适配全量回归.cjs']
    sources+=[p.relative_to(ROOT).as_posix() for p in OUT.glob(PREFIX+'*') if p.suffix in ('.cjs','.py','.ts','.sql','.mjs')]
    builds=['03_当前APP/'+name for name in ['东方智慧-首页体验R4.html','计时后台-开发联调.html','发给负责人-东方智慧首页R4.html','创作者中心.html']]
    builds+=['04_研发源码/app/cloud/'+name for name in ['generated/experience.html','generated/admin.html','generated/review.html','dist/server/index.js']]
    receipt={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':PREFIX,'taskIds':['MB01','AI05'],'stage':24,'pass':True,
       'status':'local-membership-ai-period-quota-verified-production-pending',
       'scope':'已付沙箱成交快照的UTC周期额度、独立来源桶、唯一发放、服务端来源选择、原子预占/一次结算；提前续期、暂停/恢复、取消续费、退款/到期在途closing；本人导出、四语APP和中文后台配置。',
       'production':{'productionEnabled':False,'realProviderTested':False,'actualFundsMoved':False,'productionQuotaGranted':False,'originalDatabaseUsed':False},
       'verification':verification,'actualFullBuildIdentityChecks':build_checks,'source_hashes':{name:sha(ROOT/name) for name in sources},'build_hashes':{name:sha(ROOT/name) for name in builds},'visualEvidenceSHA256':images,'preservedHistoricalSHA256':preserved,'failureHistory':failures,
       'limitations':['正式价格、额度与供应商未验收，默认关闭的固定沙箱policy不代表正式商业政策。','流式测试上游为独立本地HTTP夹具，保留.invalid地址映射至本轮精确回环端点；不是正式供应商DNS/TLS或真实模型效果。','权益扣次与上游费用分账，未知成本仍保持未知。','独立测试钱包保留，会员来源用尽/暂停/退款/到期/策略关闭不自动回退；未实现的policy值拒绝，不暗设正式无限额度。','本机四语/日夜/窄宽浏览器检查不等于实机及藏语母语审校；生产调度、正式会员渠道与退款到账另行验收。'],
       'compatibilityChanges':'本轮派生会员与网关兼容工具只更换新隔离启动/HTTP测试流和报告接线，旧业务断言和历史脚本报告保留。',
       'additionalFailureEvidence':{'path':'06_验证与后续工作/负责人优化建议-会员额度-全量启动身份失败说明.json','sha256':sha(OUT/'负责人优化建议-会员额度-全量启动身份失败说明.json')},
       'transportRemediation':'Cloud网关fetch从workerd不支持的redirect:error改manual，原non-ok仍拒绝302；QA仅映射精确本地URL不覆盖产品options，最终专项包含真实302拒绝且不跟随。此前mask覆盖的中间结果只作历史，不代替最终原参数复验。',
       'uiIntegrationRemediation':'兼容验收发现并修复：支付时使旧order/recovery读取失效，防未付快照覆盖已付；新账号关闭表单恢复本人方案名/下次续期日/渠道管理与第三方未知完整提醒，密码和二次确认不变。',
       'uiRemediation':'实测新额度面板藏文font Range37px而原line-height24.7px，相邻P无间距；仅该面板藏文P提高行高至39px并加8px段距，不缩字号，最终完整重跑。',
       'staticBoundary':'本轮实际构建通过；不声明全项目TS零诊断，privacy-api既有TS2367及环境类型缺项未由本轮修改。',
       'frozenBytes':'UTF-8 LF write_bytes; previous receipts/reports and preview DB verified unchanged'}
    target=OUT/(PREFIX+'-实施记录.json');assert not target.exists(),'Do not overwrite a frozen receipt'
    target.write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'pass':True,'stage':24,'receipt':str(target),'sha256':sha(target),'gates':{k:v['passed'] for k,v in verification.items()}},ensure_ascii=False))

if __name__=='__main__':freeze()
