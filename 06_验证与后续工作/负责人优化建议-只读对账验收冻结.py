"""Validate final identities first; --write snapshots evidence. No business/DB/build mutation."""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'06_验证与后续工作'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    r=json.loads(p.read_text(encoding='utf-8-sig'));return r.get('latest',r)
def checked(p,count):
    r=load(p);assert r.get('pass') is True and r['passed']==count and r['failed']==0,(p.name,'gate failed');return r
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--python-full',type=Path,default=OUT/'负责人优化建议-只读对账-本轮全量回归结果.json');p.add_argument('--cloud-full',type=Path,default=OUT/'负责人优化建议-只读对账-公网适配全量回归结果.json');p.add_argument('--write',action='store_true');a=p.parse_args()
    manifest=load(OUT/'负责人优化建议-只读对账模块准备记录.json')
    for name,value in manifest['sourceSha256'].items():assert sha(ROOT/name)==value,('source drift',name)
    app=ROOT/'03_当前APP/东方智慧-首页体验R4.html';admin=ROOT/'03_当前APP/计时后台-开发联调.html'
    required=['04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/eastern-api.ts','04_研发源码/app/r4/build.py','04_研发源码/app/cloud/prepare.py','04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/generated/admin.html','04_研发源码/app/cloud/dist/server/index.js','04_研发源码/app/cloud/dist/server/BUILD_ID',*manifest['sourceSha256']]
    verified={};copies={};identities={};actual={}
    for label,file in [('Python全量',a.python_full),('Cloud全量',a.cloud_full)]:
        file=file.resolve();assert file.is_relative_to(ROOT.resolve()),'Outside project report';r=checked(file,60)
        for output in [app,admin]:assert r['buildHashes'][output.name]==sha(output),(label,output.name,'wrong build')
        # Optional hashes reported by the root must also match. The actual gate below
        # requires generated/worker/build/prepare fingerprints even if full60 has only HTML.
        for key,value in r.get('buildHashes',{}).items():
            target=ROOT/key if (ROOT/key).is_file() else ROOT/'03_当前APP'/key
            if target.is_file():assert sha(target)==value,(label,key,'build drift')
        for key,value in r.get('cloudBuildHashes',{}).items():
            assert sha(ROOT/'04_研发源码/app/cloud'/key)==value,(label,key,'Cloud build drift')
        suffix='本机全量验收' if label=='Python全量' else '本地Cloud全量验收';copies[OUT/('负责人优化建议-只读对账-'+suffix+'.json')]=r;verified[label]={'input':str(file.relative_to(ROOT)),'passed':60,'at':r.get('at')}
    for target,label in [('python','Python专项'),('cloud','Cloud专项')]:
        file=OUT/('负责人优化建议-只读对账实际专项-'+target+'.json');r=checked(file,42);actual[target]=r
        assert r['identityUnchanged'] and r['syntheticDataOnly'] and not r['originalDatabaseOpened']
        assert r.get('realAdminFontLoaded') and r.get('fontAssetVerified' if target=='cloud' else 'embeddedAdminFontVerified')
        for name in required:assert name in r['identity'],(label,'missing identity',name)
        for name,value in r['identity'].items():assert sha(ROOT/name)==value,(label,'identity drift',name)
        for name,value in r['testHashes'].items():assert sha(ROOT/name)==value,(label,'test/fixture drift',name)
        assert r['servedAdminSha']==sha(ROOT/('04_研发源码/app/cloud/generated/admin.html' if target=='cloud' else '03_当前APP/计时后台-开发联调.html'))
        assert not r['browserErrors'];assert len(r['screenshots'])==3
        copies[OUT/('负责人优化建议-只读对账-'+label+'验收.json')]=r;verified[label]={'input':str(file.relative_to(ROOT)),'passed':42,'runId':r['runId'],'at':r['at']};identities[target]=r['identity']
    assert identities['python']==identities['cloud'],'Cross-backend final identities differ'
    for file,count,key in [('负责人优化建议-只读对账Python专项.json',42,'04_研发源码/app/r4/backend/reconciliation.py'),('负责人优化建议-只读对账Cloud专项.json',46,'04_研发源码/app/cloud/lib/reconciliation-api.ts'),('负责人优化建议-只读对账后台专项.json',15,'04_研发源码/app/r4/reconciliation-admin.js')]:
        r=load(OUT/file);assert r['passed']==count and r['failed']==0;assert r['sourceSha256']==sha(ROOT/key)
    visual=load(OUT/'负责人优化建议-只读对账最终视觉核验.json');assert visual['allSixImagesViewed'] and visual['pass']
    assert visual['runIds']=={k:r['runId'] for k,r in actual.items()}
    for image in visual['images']:assert sha(ROOT/image['path'])==image['sha256']
    for label,item in verified.items():
        suffix={'Python全量':'本机全量验收','Cloud全量':'本地Cloud全量验收','Python专项':'Python专项验收','Cloud专项':'Cloud专项验收'}[label]
        file=OUT/('负责人优化建议-只读对账-'+suffix+'.json')
        item['path']=file.relative_to(ROOT).as_posix()
        item['sha256']=hashlib.sha256(json.dumps(copies[file],ensure_ascii=False,indent=2).encode('utf-8')).hexdigest()
    record={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':'负责人优化建议-只读对账','pass':True,'scope':'沙箱原订单/付款退款/权益/会员/佣金/结算的当前只读一致性与本地异常面板；不自动补账、不真实渠道对账、不发送告警。','verification':verified,'source_hashes':manifest['sourceSha256'],'final_identity':identities['python'],'app_sha256':sha(app),'admin_sha256':sha(admin),'visual_review':visual,'task_disposition':{'PAY16':'进行中','PAY18':'进行中'},'limitations':['productionEnabled/realChannelReconciliationEnabled/externalAlertsEnabled/actualPaid均false。','未知费用/到账/真实打款为null；缺表或截断依赖的对应汇总null，不能看作0差异。','当前同一只读快照，不是历史as-of重建；每表上限5000，partial不可称全账一致。','100 HTTP读刷新由4个真实测试身份各25次完成，保留30/min限流，不是压测。','生产渠道每日账单、银行到账、回调队列/真实失败/拒付事件及外部告警仍未实现。'],'failure_history':['首轮QA身份映射误改finance等枚举，原CHECK拒绝；已按列/JSON身份白名单修夹具，失败run保留。','修前actual42/42曾因覆盖不足漏断言截断佣金小计0；视觉发现后加aggregateCoverage修复并重建、全新实际42及双60，旧42不得当最终门禁。']}
    target=OUT/'负责人优化建议-只读对账-实施记录.json';copies[target]=record
    for file in copies:assert not file.exists(),('Refuse overwrite frozen evidence',file.name)
    if a.write:
        for file,r in copies.items():file.write_bytes(json.dumps(r,ensure_ascii=False,indent=2).encode('utf-8'))
    print(json.dumps({'mode':'write' if a.write else 'validate-only','pass':True,'reports':len(verified),'plannedEvidenceFiles':len(copies),'written':len(copies) if a.write else 0,'taskStatusesChanged':False,'businessSourcesChanged':False,'databaseOpened':False},ensure_ascii=False))
if __name__=='__main__':main()
