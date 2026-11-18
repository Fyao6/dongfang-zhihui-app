"""Freeze SH06 only after current dual-backend gates; preserve history."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib,json

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-数字权益'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def freeze():
    specs=[('Python全量','-本轮全量回归结果.json',60),('Cloud全量','-公网适配全量回归结果.json',60),
           ('Python专项','专项-python.json',24),('Cloud专项','专项-cloud.json',24),
           ('Python交易兼容','交易兼容-python.json',31),('Cloud交易兼容','交易兼容-cloud.json',31),
           ('Python回调兼容','回调兼容-python.json',16),('Cloud回调兼容','回调兼容-cloud.json',16),
           ('Python恢复兼容','恢复兼容-python.json',19),('Cloud恢复兼容','恢复兼容-cloud.json',19),
           ('Python迟到兼容','迟到兼容-python.json',20),('Cloud迟到兼容','迟到兼容-cloud.json',20),
           ('Python补充视觉','补充视觉-python.json',4),('Cloud补充视觉','补充视觉-cloud.json',4)]
    verification,images,build_checks,failures={},{},[],[]
    for label,suffix,minimum in specs:
        path=OUT/(PREFIX+suffix);raw=json.loads(path.read_text(encoding='utf-8'));run=raw.get('latest',raw)
        assert run['pass'] is True and run.get('failed',0)==0,(label,'not passed')
        assert len(run['results'])>=minimum and all(x['pass'] is True for x in run['results']),(label,'gate count')
        assert run.get('identityUnchanged',True),(label,'identity changed')
        if suffix.startswith(('专项','补充视觉')):assert run.get('digitalSourcesUnchanged') is True,(label,'digital source identity was not stable')
        launcher=run.get('digitalEntitlementsLauncher',{});assert launcher.get('identityUnchanged') is True,(label,'launcher did not verify final identity')
        for name,expected in launcher.get('sourceAndBuildHashes',{}).items():assert sha(ROOT/name)==expected,(label,name)
        for field in ['digitalSources','sourceHashes']:
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
    sources=['04_研发源码/app/r4/'+name for name in ['digital-entitlements-ui.js','digital-entitlements-ui.css','digital-entitlements-admin.js','commerce-ui.js','commerce-admin.js','time-bank-admin.html','build.py']]
    sources+=['04_研发源码/app/r4/backend/'+name for name in ['digital_entitlements.py','commerce.py','server.py','privacy.py','payment_callbacks.py','payment_late.py','payment_recovery.py']]
    sources+=['04_研发源码/app/cloud/lib/'+name for name in ['digital-entitlements.ts','commerce-api.ts','eastern-api.ts','privacy-api.ts','payment-callbacks.ts','payment-late.ts','payment-recovery.ts']]
    sources+=['04_研发源码/app/cloud/prepare.py','06_验证与后续工作/全量回归.cjs','06_验证与后续工作/公网适配全量回归.cjs','06_验证与后续工作/负责人优化建议-支付恢复HTTP查询夹具.py']
    sources+=['05_后台与研发说明/数字作品次数期限与访问说明.txt']
    sources+=[p.relative_to(ROOT).as_posix() for p in OUT.glob(PREFIX+'*') if p.suffix in ('.cjs','.py','.ts','.sql','.mjs')]
    builds=['03_当前APP/'+name for name in ['东方智慧-首页体验R4.html','计时后台-开发联调.html','发给负责人-东方智慧首页R4.html','创作者中心.html']]
    builds+=['04_研发源码/app/cloud/'+name for name in ['generated/experience.html','generated/admin.html','generated/review.html','dist/server/index.js']]
    diagnostics={}
    for name in [PREFIX+'-诊断资料边界.json',PREFIX+'-首轮隔离会话清理.json']:
        path=OUT/name;assert path.exists(),name;diagnostics[path.relative_to(ROOT).as_posix()]=sha(path)
    receipt={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':PREFIX,'taskIds':['SH06'],'stage':25,'pass':True,
       'status':'local-finite-digital-access-verified-production-pending',
       'requirement':{'sourceIds':['P249','P251','P255'],'title':'关联数字作品与独立购买权益'},
       'scope':'有限天数/次数的独立沙箱音视频购买、下单规则不可变快照、普通与回调/查单/迟到付款同事务唯一grant；按签发访问计次、会话绑定幂等租约、逐GET/Range最终门禁、部分退款不回补used及overused、永久资产隔离、本人导出/恢复/分页、四语APP和中文后台。',
       'production':{'productionEnabled':False,'realPaymentProviderTested':False,'realCopyrightConfirmed':False,'actualThirdPartyAssetUsed':False,'originalDatabaseUsed':False},
       'verification':verification,'actualFullBuildIdentityChecks':build_checks,'source_hashes':{name:sha(ROOT/name) for name in sources},'build_hashes':{name:sha(ROOT/name) for name in builds},'visualEvidenceSHA256':images,'preservedHistoricalSHA256':preserved,'failureHistory':failures,
       'limitations':['当前仅明确隔离的自有沙箱音视频资产，未打开真实production会员媒体；正式支付/版权课程/商业期限与次数仍待确认和验收。','计次在取得访问权限时发生，不代表媒体已播放完成；同一有效lease的Range和重试不重复扣。','资源ID不是匿名bearer凭据，每次媒体请求仍需原有效本人session及全部授权事实。','服务端门禁只能约束后续请求，不能收回已传输或已下载缓冲的字节，不宣称DRM或第三方删除完成。','旧无成交快照订单不追溯补造有限权益；库存退款余量remaining与实际used使用账分开。','本机四语/日夜/窄宽与实际音频检查不等于实机/真实CDN或藏语母语审校。'],
       'staticBoundary':'本轮实际构建通过；不声明全项目TS零诊断，原privacy-api TS2367及环境类型缺项仍按既有边界。',
       'privateDiagnosticBoundary':{'documentsSHA256':diagnostics,'privateRawReports':['06_验证与后续工作/'+PREFIX+'专项-python.json'],'rule':'原Python首轮失败包含已失效的合成会话，原字节仅本机保留，不进入公网或交付包；实际交付时须另生成脱敏派生并说明来源，不假称原raw已脱敏。'},
       'compatibilityChanges':'新数字权益报告复验原交易及已接受的回调/恢复/迟到通用逻辑，原历史脚本/报告保留，临时控制仅在本轮自有隔离服务。',
       'frozenBytes':'UTF-8 LF write_bytes; previous receipts/reports and preview DB verified unchanged'}
    target=OUT/(PREFIX+'-实施记录.json');assert not target.exists(),'Do not overwrite a frozen receipt'
    target.write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'pass':True,'stage':25,'receipt':str(target),'sha256':sha(target),'gates':{k:v['passed'] for k,v in verification.items()}},ensure_ascii=False))

if __name__=='__main__':freeze()
