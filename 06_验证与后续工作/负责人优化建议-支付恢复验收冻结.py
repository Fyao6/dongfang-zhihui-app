"""Freeze final PAY09 software gates; never starts a service or alters old receipts."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'06_验证与后续工作'
PREFIX='负责人优化建议-支付恢复'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    specs=[('Python全量','-本轮全量回归结果.json',60),('Cloud全量','-公网适配全量回归结果.json',60),
           ('Python专项','专项-python.json',19),('Cloud专项','专项-cloud.json',19),
           ('Python交易兼容','交易兼容-python.json',31),('Cloud交易兼容','交易兼容-cloud.json',31),
           ('PythonPAY08兼容','-PAY08兼容-python.json',16),('CloudPAY08兼容','-PAY08兼容-cloud.json',16),
           ('Python补充视觉','补充视觉-python.json',4),('Cloud补充视觉','补充视觉-cloud.json',4)]
    verification={};images={};build_checks=[];history=[]
    for label,suffix,count in specs:
        path=OUT/(PREFIX+suffix)
        raw=json.loads(path.read_text(encoding='utf-8'));result=raw.get('latest',raw)
        assert result['pass'] is True and result.get('failed',0)==0,(label,'not passed')
        assert len(result['results'])==count and all(r['pass'] is True for r in result['results']),(label,'wrong gate count')
        assert result.get('identityUnchanged',True),(label,'identity changed')
        for part in [result.get('recoverySources',{}),result.get('callbackSources',{}),*result.get('identity',{}).values()]:
            if isinstance(part,dict):
                for name,expected in part.items():assert sha(ROOT/name)==expected,(label,name)
        for field,base in [('buildHashes',ROOT/'03_当前APP'),('cloudBuildHashes',ROOT/'04_研发源码/app/cloud')]:
            for name,expected in result.get(field,{}).items():
                p=base/name;actual=sha(p);assert actual==expected,(label,p)
                build_checks.append({'gate':label,'path':p.relative_to(ROOT).as_posix(),'expected':expected,'actual':actual})
        for name in result.get('captures',[]):
            p=OUT/name;images[p.relative_to(ROOT).as_posix()]=sha(p)
        verification[label]={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'passed':count,'failed':0,
                             'at':result.get('at'),'runId':result.get('runId')}
        for run in raw.get('runs',[]):
            if run.get('pass') is not True:
                history.append({'report':path.name,'at':run.get('at'),'passed':run.get('passed'),'failed':run.get('failed'),
                                'failedNames':[r['name'] for r in run.get('results',[]) if r.get('pass') is not True]})
    assert len(build_checks)>=12,'Missing actual full-regression build identities'
    sources=['04_研发源码/app/r4/backend/payment_recovery.py','04_研发源码/app/r4/backend/payment_callbacks.py',
             '04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/payment-recovery.ts',
             '04_研发源码/app/cloud/lib/payment-callbacks.ts','04_研发源码/app/cloud/lib/eastern-api.ts',
             '04_研发源码/app/r4/payment-recovery-ui.js','04_研发源码/app/r4/payment-recovery-admin.js',
             '04_研发源码/app/r4/commerce-ui.js','04_研发源码/app/r4/commerce-admin.js',
             '04_研发源码/app/r4/build.py','04_研发源码/app/cloud/prepare.py','06_验证与后续工作/全量回归.cjs',
             '06_验证与后续工作/公网适配全量回归.cjs']
    sources+=['06_验证与后续工作/'+PREFIX+n for n in ['专项.cjs','补充视觉.cjs','验收启动.cjs','Python测试服务.py','Cloud测试服务.ts','HTTP查询夹具.py','验收冻结.py']]
    builds=['03_当前APP/东方智慧-首页体验R4.html','03_当前APP/计时后台-开发联调.html',
            '03_当前APP/发给负责人-东方智慧首页R4.html','03_当前APP/创作者中心.html',
            '04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/generated/admin.html',
            '04_研发源码/app/cloud/generated/review.html','04_研发源码/app/cloud/dist/server/index.js']
    receipt={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':PREFIX,'taskId':'PAY09','stage':22,'pass':True,
             'status':'local-recovery-software-verified-real-channel-pending',
             'requirement':{'sourceIds':['P452','P453','P454','P501'],'title':'支付异常恢复与主动查单',
                            'acceptance':'关APP后重开仍见真实结果，延迟显示处理中。','workbookRange':'98项明细!A78:H78'},
             'scope':'本人订单主动查单和持久恢复任务、真实独立回环HTTP签名上游、请求幂等/有限退避/租约恢复、配置撤回指纹、可信paid结果原子进入PAY08并仅消费本人关联收件、乱序终态保护、APP四语日夜及后台原生回查/重试。',
             'production':{'productionEnabled':False,'realProviderTested':False,'actualFundsMoved':False,
                           'sandboxFixtureOnly':True,'originalDatabaseUsed':False,'automaticSchedulerDeployed':False},
             'verification':verification,'actualFullBuildIdentityChecks':build_checks,
             'source_hashes':{name:sha(ROOT/name) for name in sources},'build_hashes':{name:sha(ROOT/name) for name in builds},
             'visualEvidenceSHA256':images,'failureHistory':history,
             'limitations':['签名HTTP上游是独立本地测试协议，不是正式Apple/Google/Stripe/PayPal验单或查单适配；这些真实接口仍须实际接入验收。',
                            '查询由本人POST或独立管理员恢复请求执行，任务可回查和续跑；没有生产常驻调度/自动唤醒或外部告警。',
                            '成功查询仍复用原数字/实物沙箱结算门禁；会员、迟到/关闭/退款冲突保留人工核查，PAY13库存/真实退款补偿未在本轮实现。',
                            '进程内配置撤回和密钥引用轮换通过本地测试；不是生产KMS/IAM或跨部署吊销验收。',
                            '本机浏览器四语/主题/宽度和字体检查不等于iOS/Android实机或藏语母语审校。'],
             'frozenBytes':'UTF-8 LF write_bytes; old PAY08 receipts and report bytes preserved'}
    target=OUT/(PREFIX+'-实施记录.json');assert not target.exists(),'Do not overwrite a frozen receipt'
    target.write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps({'pass':True,'stage':22,'receipt':str(target),'sha256':sha(target),'gates':{k:v['passed'] for k,v in verification.items()}},ensure_ascii=False))


if __name__=='__main__':freeze()
