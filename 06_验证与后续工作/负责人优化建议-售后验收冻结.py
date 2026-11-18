"""Validate the final after-sales gate; --write creates six immutable snapshots and one implementation record.
Default validation performs no writes, starts no process/service and never opens a database.
Only existing 06 files are written, with no new subdirectory and no task/status/business-source changes.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'06_验证与后续工作'
APP=ROOT/'03_当前APP/东方智慧-首页体验R4.html'
ADMIN=ROOT/'03_当前APP/计时后台-开发联调.html'
CLOUD=ROOT/'04_研发源码/app/cloud'
MODULE_FILES=[
 '04_研发源码/app/r4/backend/after_sales.py','04_研发源码/app/cloud/lib/after-sales.ts',
 '04_研发源码/app/r4/after-sales-ui.js','04_研发源码/app/r4/after-sales-ui.css','04_研发源码/app/r4/after-sales-admin.js']
INTEGRATION_FILES=[
 '04_研发源码/app/r4/backend/server.py','04_研发源码/app/cloud/lib/eastern-api.ts',
 '04_研发源码/app/r4/backend/commerce.py','04_研发源码/app/cloud/lib/commerce-api.ts',
 '04_研发源码/app/r4/backend/privacy.py','04_研发源码/app/cloud/lib/privacy-api.ts',
 '04_研发源码/app/r4/platform.js','04_研发源码/app/r4/build.py',
 '04_研发源码/app/cloud/prepare.py','04_研发源码/app/r4/time-bank-admin.html']
TEST_FILES=['负责人优化建议-售后实际专项.cjs','负责人优化建议-售后HTTP专项.cjs',
 '负责人优化建议-售后浏览器专项.cjs','负责人优化建议-售后Python测试服务.py',
 '负责人优化建议-售后Cloud测试服务.ts','负责人优化建议-售后接入准备.py','负责人优化建议-售后验收冻结.py','负责人优化建议-售后交易兼容专项.cjs','负责人优化建议-售后交易兼容工具.cjs','负责人优化建议-售后交易兼容启动.cjs']
BUILD_FILES=[
 '03_当前APP/东方智慧-首页体验R4.html','03_当前APP/计时后台-开发联调.html',
 '04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/generated/admin.html',
 '04_研发源码/app/cloud/generated/review.html','04_研发源码/app/cloud/dist/server/index.js',
 '04_研发源码/app/cloud/dist/server/BUILD_ID','04_研发源码/app/cloud/worker/index.ts',
 '04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql',
 '04_研发源码/app/cloud/public/assets/NotoSerifTibetan.woff2',
 '04_研发源码/app/r4/vendor/NotoSerifTibetan.woff2']
CLOUD_FULL_REQUIRED={'generated/experience.html','generated/admin.html','generated/review.html',
 'lib/eastern-api.ts','worker/index.ts','dist/server/index.js'}
CAPTURE_LABELS={'实际逐项申请与进度','实际后台验收零入库','实际四语详情-zh',
 '实际四语详情-zh-Hant','实际四语详情-en','实际四语详情-bo','实际换账号旧读取不泄漏'}

class ValidationError(Exception):pass
def need(value,message):
    if not value:raise ValidationError(message)
def sha_bytes(value):return hashlib.sha256(value).hexdigest()
def sha(file):
    need(file.is_file(),'Required file missing: '+str(file.relative_to(ROOT) if file.is_relative_to(ROOT) else file))
    return sha_bytes(file.read_bytes())
def local(file):
    file=Path(file).resolve()
    need(file.is_relative_to(ROOT.resolve()),'Report/artifact outside this project: '+str(file))
    return file
def relative(file):return local(file).relative_to(ROOT.resolve()).as_posix()
def project_file(name):return local(ROOT/str(name).replace('\\','/'))
def payload(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def read(file):
    file=local(file);need(file.is_file(),'Required gate report missing: '+relative(file))
    raw=json.loads(file.read_text(encoding='utf-8-sig'))
    need(isinstance(raw,dict),'Expected a JSON report object: '+relative(file))
    value=raw.get('latest',raw);need(isinstance(value,dict),'Invalid latest report: '+relative(file))
    return value
def checked(file,count):
    report=read(file)
    need(report.get('pass') is True and type(report.get('passed')) is int and report['passed']==count
         and report.get('failed')==0,'Gate did not pass '+str(count)+' checks: '+relative(file))
    tests=report.get('results')
    need(isinstance(tests,list) and len(tests)==count and all(t.get('pass') is True for t in tests),
         'Missing/incomplete result list: '+relative(file))
    names=[t.get('name') for t in tests]
    need(all(isinstance(n,str) and n for n in names) and len(set(names))==count,
         'Repeated or unnamed checks: '+relative(file))
    return report
def verify_map(values,label,base=ROOT):
    need(isinstance(values,dict) and values,label+' identity map missing')
    for name,digest in values.items():
        need(isinstance(digest,str) and re.fullmatch(r'[a-f0-9]{64}',digest),label+' invalid digest: '+str(name))
        file=local(base/str(name).replace('\\','/'))
        need(sha(file)==digest,label+' identity drift: '+relative(file))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-full',type=Path,default=OUT/'负责人优化建议-售后-本轮全量回归结果.json')
    parser.add_argument('--cloud-full',type=Path,default=OUT/'负责人优化建议-售后-公网适配全量回归结果.json')
    parser.add_argument('--python-actual',type=Path,default=OUT/'负责人优化建议-售后实际专项-python.json')
    parser.add_argument('--cloud-actual',type=Path,default=OUT/'负责人优化建议-售后实际专项-cloud.json')
    parser.add_argument('--python-compat',type=Path,default=OUT/'负责人优化建议-售后交易兼容专项-python.json')
    parser.add_argument('--cloud-compat',type=Path,default=OUT/'负责人优化建议-售后交易兼容专项-cloud.json')
    parser.add_argument('--visual-review',type=Path,default=OUT/'负责人优化建议-售后最终视觉核验.json')
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    copies={};verification={};actual={};full={};identities={};screenshots=[]
    manifest=read(OUT/'负责人优化建议-售后准备核验.json')
    # Only new module/test files are pinned to preparation. Integration sources must change during apply/build.
    for name,digest in manifest.get('sources',{}).items():
        need(sha(project_file(name))==digest,'Prepared new source/test drift: '+name)
    for name in MODULE_FILES:need(name in manifest.get('sources',{}),'Prepared module hash missing: '+name)

    for target,file in [('python',args.python_full),('cloud',args.cloud_full)]:
        file=local(file);report=checked(file,60);builds=report.get('buildHashes')
        need(isinstance(builds,dict),'Full60 buildHashes missing: '+relative(file))
        need(builds.get(APP.name)==sha(APP) and builds.get(ADMIN.name)==sha(ADMIN),
             target+' full60 does not match BOTH current APP and admin builds')
        for name,digest in builds.items():
            candidate=ROOT/str(name)
            if not candidate.is_file():candidate=ROOT/'03_当前APP'/str(name)
            need(sha(local(candidate))==digest,target+' full60 build drift: '+name)
        cloud_builds=report.get('cloudBuildHashes')
        if target=='cloud':
            need(isinstance(cloud_builds,dict) and CLOUD_FULL_REQUIRED<=set(cloud_builds),
                 'Cloud full60 must bind generated APP/admin/review, API, worker and compiled server')
        if cloud_builds:verify_map(cloud_builds,target+' full60 Cloud',CLOUD)
        full[target]=report
        label='Python全量' if target=='python' else 'Cloud全量'
        suffix='本机全量验收' if target=='python' else '本地Cloud全量验收'
        dest=OUT/('负责人优化建议-售后-'+suffix+'.json');copies[dest]=report
        verification[label]={'input':relative(file),'inputSha256':sha(file),'path':relative(dest),
          'sha256':sha_bytes(payload(report)),'passed':60,'at':report.get('at')}

    required=set(MODULE_FILES+INTEGRATION_FILES+BUILD_FILES+
                 ['06_验证与后续工作/'+n for n in TEST_FILES])
    # The actual fixture runner records every Python backend and Cloud lib dependency, not just the five new modules.
    required.update(relative(p) for p in (ROOT/'04_研发源码/app/r4/backend').glob('*.py'))
    required.update(relative(p) for p in (CLOUD/'lib').glob('*.ts'))
    font_sha=sha(CLOUD/'public/assets/NotoSerifTibetan.woff2')
    need(font_sha==sha(ROOT/'04_研发源码/app/r4/vendor/NotoSerifTibetan.woff2'),'APP/Cloud Tibetan assets differ')
    font_size=(CLOUD/'public/assets/NotoSerifTibetan.woff2').stat().st_size
    for target,file in [('python',args.python_actual),('cloud',args.cloud_actual)]:
        file=local(file);report=checked(file,29)
        need(report.get('target')==target and report.get('identityUnchanged') is True,target+' actual29 target/identity invalid')
        need(report.get('syntheticDataOnly') is True and report.get('productionWrites') is False
             and report.get('realAIRequests')==0,target+' actual29 must use only synthetic local sandbox data')
        need(urlsplit(report.get('base','')).hostname in ('127.0.0.1','localhost'),target+' actual29 did not use an owned local service')
        run_id=report.get('runId');need(isinstance(run_id,str) and re.fullmatch(r'[a-z0-9]+_[a-f0-9]{6}',run_id),target+' invalid runId')
        if target=='python':
            database=project_file(report.get('ownedDatabase',''))
            need(database.parent==OUT.resolve() and database.name=='负责人优化建议-售后HTTP隔离-'+run_id+'.sqlite3',
                 'Python actual29 must identify a fresh owned fixture SQLite (not opened by this script)')
        else:
            state=project_file(report.get('ownedState',''))
            need(state.parent==(CLOUD/'.wrangler').resolve() and re.fullmatch(r'as[a-f0-9]{8}',state.name),
                 'Cloud actual29 must identify a fresh owned fixture state')
        identity=report.get('sourceBuildTestHashes')
        need(isinstance(identity,dict) and required<=set(identity),target+' actual29 missing critical source/worker/build/test/font identity')
        verify_map(identity,target+' actual29')
        identities[target]=identity
        app=APP if target=='python' else CLOUD/'generated/experience.html'
        admin=ADMIN if target=='python' else CLOUD/'generated/admin.html'
        need(report.get('servedBuildSha256')==sha(app),target+' actual29 served another APP build')
        need(report.get('servedAdminSha256')==sha(admin),target+' actual29 served another admin build')
        need(report.get('errors')==[],target+' actual29 browser errors')
        need(not any(t.get('status')==429 for t in report.get('traffic',[])),target+' actual29 had rate-limit failures')
        font=report.get('fontAsset' if target=='cloud' else 'embeddedFontAsset',{})
        need(font.get('sha256')==font_sha and font.get('bytes')==font_size
             and (font.get('status')==200 if target=='cloud' else font.get('verified') is True),
             target+' actual29 exact real Tibetan font was not verified')
        views=report.get('views',[])
        expected={(screen,width,mode,lang) for screen in ['closed','center','request','detail']
                  for width in [375,430] for mode in ['day','night'] for lang in ['zh','zh-Hant','en','bo']}
        tuples=[(v.get('screen'),v.get('width'),v.get('mode'),v.get('lang')) for v in views]
        need(len(tuples)==64 and set(tuples)==expected and all(v.get('noOverflow') is True for v in views),
             target+' actual29 missing actual 64-view layout observations')
        faces=report.get('fontObservations',[])
        expected_bo={x for x in expected if x[3]=='bo'}
        observed_bo=[(v.get('screen'),v.get('width'),v.get('mode'),v.get('lang')) for v in faces]
        need(len(faces)==16 and set(observed_bo)==expected_bo and all(
             type(v.get('faceCount')) is int and v['faceCount']>0 and v.get('statuses')
             and all(s=='loaded' for s in v['statuses']) and 'EW Tibetan' in v.get('fontFamily','') for v in faces),
             target+' actual29 real font face selection/load observations incomplete')
        history=report.get('timelineObservations',[])
        expected_history={(width,mode,lang) for width in [375,430] for mode in ['day','night'] for lang in ['zh','zh-Hant','en','bo']}
        need(len(history)==16 and {(v.get('width'),v.get('mode'),v.get('lang')) for v in history}==expected_history,
             target+' actual29 missing four-language controlled timeline observations')
        for item in history:
            labels=item.get('labels',[])
            need(len(labels)==4 and item.get('rawKeysExposed') is False and all(isinstance(label,str) and label and
                 not re.search(r'\b(?:submit|accept|reject|return-shipping|inspect)\b',label,re.I) for label in labels),
                 target+' actual29 exposed a raw action key instead of a localized label')
        timers=report.get('timerObservations',[])
        expected_timers={(width,mode,lang,shape) for width in [375,430] for mode in ['day','night']
                         for lang in ['zh','zh-Hant','en','bo'] for shape in ['compact','bar']}
        need(len(timers)==32 and {(v.get('width'),v.get('mode'),v.get('lang'),v.get('shape')) for v in timers}==expected_timers,
             target+' actual29 missing both actual timer shapes across the detail views')
        for item in timers:
            need(item.get('position')=='bottom-right via existing keyboard controls' and item.get('refreshResponseStatus')==200
                 and item.get('timerStateUnchanged') is True and item.get('running') is True,
                 target+' actual29 did not use the actual refresh control with the real running timer')
            for moment in ['pre','post']:
                rects=item.get(moment,{})
                need(rects.get('fullyVisible') is True and rects.get('noOverlap') is True and rects.get('allHit') is True,
                     target+' refresh button was out of viewport/covered/not hit-testable '+moment)
            before=item.get('stableBefore');after=item.get('stableAfter')
            need(isinstance(before,dict) and before==after and before.get('running') is True
                 and before.get('visible') is True and bool(before.get('collapsed'))==(item['shape']=='compact'),
                 target+' scroll/refetch altered stable timer state')
            runs=before.get('runs',[])
            need(runs and any(isinstance(r.get('id'),str) and type(r.get('start')) in (int,float) and r.get('end') is None for r in runs),
                 target+' actual running timer session ID/start was not preserved')
            early=item.get('totalMsBefore');late=item.get('totalMsAfter')
            need(type(early) in (int,float) and type(late) in (int,float) and math.isfinite(early) and math.isfinite(late) and late>=early,
                 target+' actual elapsed clock reset or was not recorded')
        expected_names={'负责人优化建议-售后-'+target+'-'+run_id+'-'+label+'.png' for label in CAPTURE_LABELS}
        captures=report.get('captures',[])
        need(isinstance(captures,list) and len(captures)==7 and set(captures)==expected_names,target+' actual29 screenshots missing/foreign run')
        hashes=report.get('captureHashes',[])
        need(isinstance(hashes,list) and len(hashes)==7,target+' actual29 screenshot hashes were not recorded at capture')
        seen=set()
        for image in hashes:
            image_file=project_file(image.get('path',''))
            need(image_file.parent==OUT.resolve() and image_file.name in expected_names and image_file.name not in seen,
                 target+' invalid/duplicate screenshot path')
            need(sha(image_file)==image.get('sha256'),target+' screenshot changed: '+image_file.name)
            need(image_file.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'),target+' screenshot is not PNG')
            seen.add(image_file.name);screenshots.append({'target':target,'runId':run_id,'path':relative(image_file),'sha256':image['sha256']})
        label='Python专项' if target=='python' else 'Cloud专项'
        suffix='Python专项验收' if target=='python' else 'Cloud专项验收'
        dest=OUT/('负责人优化建议-售后-'+suffix+'.json');copies[dest]=report
        verification[label]={'input':relative(file),'inputSha256':sha(file),'path':relative(dest),
          'sha256':sha_bytes(payload(report)),'passed':29,'runId':run_id,'at':report.get('at')}
        actual[target]=report
    need(identities['python']==identities['cloud'],'Actual Python/Cloud final source/build/test identities differ')
    # Require the full29 and full60 gates to identify the same final Cloud build, not just a shared main HTML.
    cloud_prefix='04_研发源码/app/cloud/'
    for name,digest in full['cloud']['cloudBuildHashes'].items():
        need(identities['cloud'].get(cloud_prefix+name)==digest,'full60/actual29 Cloud identity disagreement: '+name)
    for name in [relative(APP),relative(ADMIN)]:
        need(identities['python'].get(name)==sha(project_file(name)),'full60/actual29 APP/admin mismatch: '+name)

    for target,file in [('python',args.python_compat),('cloud',args.cloud_compat)]:
        file=local(file);report=checked(file,31)
        need(report.get('target')==target and report.get('identityUnchanged') is True
             and report.get('syntheticDataOnly') is True and report.get('productionWrites') is False
             and report.get('errors')==[],target+' actual31 compatibility target/sandbox/identity invalid')
        endpoint=urlsplit(report.get('base',''))
        need(endpoint.hostname in ('127.0.0.1','localhost') and endpoint.port!=8878,
             target+' compatibility must use its own local service, not root8878')
        need(report.get('coverage',{}).get('http') is True and report.get('coverage',{}).get('ui') is True,
             target+' compatibility must include actual HTTP and browser flow')
        identity=report.get('identity',{})
        for kind in ['sources','builds']:
            verify_map(identity.get(kind),target+' compatibility '+kind)
            for name,digest in identity[kind].items():
                need(identities[target].get(name)==digest,target+' actual29/31 source/build identity disagreement: '+name)
        need(set(MODULE_FILES)<=set(identity.get('sources',{})),target+' compatibility omitted new module source identity')
        test_hashes=report.get('harnessSha256',{})
        need({'06_验证与后续工作/'+n for n in ['负责人优化建议-售后交易兼容工具.cjs','负责人优化建议-售后交易兼容专项.cjs','负责人优化建议-售后交易兼容启动.cjs']}<=set(test_hashes),
             target+' compatibility launcher/contract/harness identity incomplete')
        verify_map(test_hashes,target+' compatibility tests')
        for name,digest in test_hashes.items():
            need(identities[target].get(name)==digest,target+' actual29/31 test identity disagreement: '+name)
        expected=APP if target=='python' else CLOUD/'generated/experience.html'
        need(report.get('servedBuildSha256')==sha(expected),target+' compatibility served another APP build')
        label='Python交易兼容' if target=='python' else 'Cloud交易兼容'
        suffix='交易兼容Python验收' if target=='python' else '交易兼容Cloud验收'
        dest=OUT/('负责人优化建议-售后-'+suffix+'.json');copies[dest]=report
        verification[label]={'input':relative(file),'inputSha256':sha(file),'path':relative(dest),
          'sha256':sha_bytes(payload(report)),'passed':31,'runId':report.get('runId'),'at':report.get('at')}

    visual_file=local(args.visual_review);visual=read(visual_file)
    need(visual.get('pass') is True and visual.get('all14ImagesViewed') is True
         and visual.get('runIds')=={target:r['runId'] for target,r in actual.items()},
         'Manual visual review must cover exactly these final two actual29 runs')
    reviewed=visual.get('images',[])
    expected_images={(i['target'],i['path'],i['sha256']) for i in screenshots}
    observed_images={(i.get('target'),i.get('path'),i.get('sha256')) for i in reviewed}
    need(len(reviewed)==14 and observed_images==expected_images and all(
         i.get('viewed') is True and isinstance(i.get('conclusion'),str) and i['conclusion'] for i in reviewed),
         'Manual review image paths/hashes/conclusions incomplete or from another run')
    for item in reviewed:need(sha(project_file(item['path']))==item['sha256'],'Reviewed screenshot changed after review: '+item['path'])

    # Read only integration markers; no application imports, builds or DB operations.
    markers={
     '04_研发源码/app/r4/backend/server.py':['init_after_sales_schema(db)','after_sales_result = AfterSales'],
     '04_研发源码/app/cloud/lib/eastern-api.ts':['await initAfterSales(this)','await afterSalesRoute(this,p,m,fail)'],
     '04_研发源码/app/r4/backend/commerce.py':['after-sales-legacy-guard:v1'],
     '04_研发源码/app/cloud/lib/commerce-api.ts':['legacyAfterSalesInsertGuard(a,owner,oid)','legacyGuard.sql'],
     '04_研发源码/app/r4/build.py':['after-sales-ui-install:v1',"'after-sales-ui.css'"],
     '04_研发源码/app/r4/backend/privacy.py':["'afterSalesCases'","'after-sales-ledger'"],
     '04_研发源码/app/cloud/lib/privacy-api.ts':['afterSalesCases:',"'after-sales-ledger'"]}
    for name,needles in markers.items():
        source=project_file(name).read_text(encoding='utf-8')
        need(all(n in source for n in needles),'After-sales integration marker missing: '+name)
    record={'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'module':'负责人优化建议-售后','pass':True,
      'scope':'隔离沙箱本人按项申请、管理员受理/理由驳回、本人物流登记、逐项实收与明确可入库数量的一次性库存事件；资金事实仍在原统一交易模块。',
      'verification':verification,'source_hashes':{n:sha(project_file(n)) for n in MODULE_FILES},
      'final_identity':identities['python'],'app_sha256':sha(APP),'admin_sha256':sha(ADMIN),
      'cloud_build_hashes':full['cloud']['cloudBuildHashes'],'screenshots':screenshots,
      'visual_review':visual,'visual_review_evidence':{'path':relative(visual_file),'sha256':sha(visual_file)},
      'task_disposition':{'SH03':'进行中','SH04':'进行中','SH05':'进行中','PAY19':'进行中'},
      'limitations':['生产售后/真实支付退款/正式承运商核验均未启用，模块初始沙箱默认关闭。',
        '受理、物流登记、实收不自动退款；累计原订单测试退款不证明本申请已退款或真实到账。',
        '同原订单收货号由事务/batch互斥；并发仅一个成功且只按明确restockQuantity加库存，不能证明外部物品已经真实收到。',
        '已发货/送达的原统一退款不回库存；未发货原退款已回库数量从申请余量扣除。',
        '正式期限、费用承担、退换货政策、真实仓库/承运身份与支付/拒付同步仍待资料和真实渠道；不以管理员测试记录代替。',
        '售后/库存与财务审计保留单独列明；正式保留期限待确认，未宣称供应商/备份已清除。',
        '本机Chromium四语/窄屏检查不等于目标地区真机或藏文母语审校。'],
      'failure_history':['原case范围receiptReference唯一不足以防同原订单拆两case重复实收，已双端复现[200,200]并保留失败runs；收紧原订单范围后并发[200,409]、库存仅+1及串行同号409。',
        '首次Python隔离夹具用了旧地址字段line1，原统一订单按address拒绝；夹具修正，未绕开原地址门禁。'],
      'invariants':['旧新售后入口在原事务/同D1 batch互斥，历史幂等重放保留；竞争不改变原money/fulfilment/stock。',
        '本人查询/导出账号隔离，管理员角色在写入批内再核；operator无资金/验收操作权。',
        '六份快照与14张截图均绑定本次精确源码/Worker/构建/测试/字体身份。',
        '四语受控历史事件不用API原键；32组默认底部位置的两形态计时浮层下末尾刷新按钮完全在视口、不相交且原生点击，实际回读后会话ID/start/运行状态不变，elapsed允许真实增长；不承诺任意拖动位置永不重叠。']}
    dest=OUT/'负责人优化建议-售后-实施记录.json';copies[dest]=record
    for file in copies:need(not file.exists(),'Refuse overwrite of frozen evidence: '+relative(file))
    # Validate-only stops here without creating any artifact. All writes remain flat in existing 06.
    if args.write:
        for file,value in copies.items():
            with file.open('xb') as output:output.write(payload(value))
    print(json.dumps({'mode':'write' if args.write else 'validate-only','pass':True,'verificationReports':6,
      'plannedEvidenceFiles':7,'written':7 if args.write else 0,'screenshotsVerified':14,
      'tasksChanged':False,'businessSourcesChanged':False,'databaseOpened':False,'newDirectoriesCreated':False},ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (ValidationError,FileNotFoundError,json.JSONDecodeError) as error:
        print('Validation failed: '+str(error),file=sys.stderr);sys.exit(1)

