"""Freeze PAY10/PAY13 only after current dual-backend gates; preserve history."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib,json

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-迟到补偿'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def freeze():
    specs=[('Python全量','-本轮全量回归结果.json',60),('Cloud全量','-公网适配全量回归结果.json',60),
           ('Python专项','专项-python.json',20),('Cloud专项','专项-cloud.json',20),
           ('Python交易兼容','交易兼容-python.json',31),('Cloud交易兼容','交易兼容-cloud.json',31),
           ('Python回调兼容','回调兼容-python.json',16),('Cloud回调兼容','回调兼容-cloud.json',16),
           ('Python恢复兼容','恢复兼容-python.json',19),('Cloud恢复兼容','恢复兼容-cloud.json',19),
           ('Python补充视觉','补充视觉-python.json',4),('Cloud补充视觉','补充视觉-cloud.json',4)]
    verification,images,build_checks,failures={},{},[],[]
    for label,suffix,minimum in specs:
        path=OUT/(PREFIX+suffix);raw=json.loads(path.read_text(encoding='utf-8'));run=raw.get('latest',raw)
        assert run['pass'] is True and run.get('failed',0)==0,(label,'not passed')
        assert len(run['results'])>=minimum and all(x['pass'] is True for x in run['results']),(label,'gate count')
        assert run.get('identityUnchanged',True),(label,'identity changed')
        for field in ['lateSources','recoverySources','callbackSources','sourceHashes']:
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
    sources=['04_研发源码/app/r4/'+name for name in ['payment-late-ui.js','payment-late-admin.js','commerce-ui.js','commerce-admin.js','payment-recovery-ui.js','payment-callback-admin.js','payment-recovery-admin.js','build.py']]
    sources+=['04_研发源码/app/r4/backend/'+name for name in ['payment_late.py','payment_callbacks.py','payment_recovery.py','commerce.py','server.py']]
    sources+=['04_研发源码/app/cloud/lib/'+name for name in ['payment-late.ts','payment-callbacks.ts','payment-recovery.ts','commerce-api.ts','eastern-api.ts']]
    sources+=['04_研发源码/app/cloud/prepare.py','06_验证与后续工作/全量回归.cjs','06_验证与后续工作/公网适配全量回归.cjs']
    sources+=[p.relative_to(ROOT).as_posix() for p in OUT.glob(PREFIX+'*') if p.suffix in ('.cjs','.py','.ts')]
    builds=['03_当前APP/'+name for name in ['东方智慧-首页体验R4.html','计时后台-开发联调.html','发给负责人-东方智慧首页R4.html','创作者中心.html']]
    builds+=['04_研发源码/app/cloud/'+name for name in ['generated/experience.html','generated/admin.html','generated/review.html','dist/server/index.js']]
    receipt={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':PREFIX,'taskIds':['PAY10','PAY13'],'stage':23,'pass':True,
       'status':'local-late-settlement-verified-real-payments-pending',
       'scope':'可信沙箱迟到付款、本单到期释放、逐SKU全量重核与原子扣库/原价接续/唯一权益；缺货与绑定变化持久退款待办，管理员幂等受理和本人订单回查；过期本人主动查单接同一安全收件路径。',
       'production':{'productionEnabled':False,'realProviderTested':False,'actualFundsMoved':False,'actualRefundExecuted':False,'originalDatabaseUsed':False,'automaticSchedulerDeployed':False},
       'verification':verification,'actualFullBuildIdentityChecks':build_checks,'source_hashes':{name:sha(ROOT/name) for name in sources},'build_hashes':{name:sha(ROOT/name) for name in builds},'visualEvidenceSHA256':images,'preservedHistoricalSHA256':preserved,'failureHistory':failures,
       'limitations':['验签和主动查单上游仅独立本地测试协议，非正式支付渠道。','退款队列及受理不等于真实退款、银行到账或售后结案；缺货未消费库存不调用普通退款回补。','会员订单、非到期关闭、已付款/退款、闭户及不同交易冲突保留人工核查，不扩展自动发放。','用户通知为本人订单内持久进度，非外发短信/推送。','专项实际重启Python进程并从原隔离库回查；Cloud验证独立请求的D1持久回查，未实际重启Worker进程，不能将条件执行的用例标题当作Cloud重启实证。','未部署生产常驻任务、真实渠道监控与外部告警；本机浏览器不等于实机及藏语母语审校。'],
       'compatibilityChanges':'原PAY08/PAY09仅把过期订单送人工的旧断言，在本轮派生兼容脚本中由迟到正向专项替代；旧脚本和旧报告保留。',
       'frozenBytes':'UTF-8 LF write_bytes; historical receipts, reports and preview DB verified unchanged'}
    target=OUT/(PREFIX+'-实施记录.json');assert not target.exists(),'Do not overwrite a frozen receipt'
    target.write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'pass':True,'stage':23,'receipt':str(target),'sha256':sha(target),'gates':{k:v['passed'] for k,v in verification.items()}},ensure_ascii=False))

if __name__=='__main__':freeze()
