"""Default read-only validation; --write creates new LF-byte snapshots in existing 06 only."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent
PREFIX='负责人优化建议-到期清理';RECORD=HERE/(PREFIX+'-实施记录.json')
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha(path):return sha_bytes(path.read_bytes())
def safe(rel):
    path=(ROOT/rel).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():raise AssertionError('invalid evidence path '+str(rel))
    return path
def data(rel):return json.loads(safe(rel).read_bytes())
def rel(path):return path.relative_to(ROOT).as_posix()
def encoded(v):return json.dumps(v,ensure_ascii=False,indent=2).encode('utf-8')
def latest(v):return v.get('latest',v)
def passed(v,count,key='results'):
    rows=v.get(key)
    assert v.get('pass') is True and v.get('passed')==count and v.get('failed')==0
    assert isinstance(rows,list) and len(rows)==count and all(r.get('pass') is True for r in rows)

inputs={
 'Python全量':(PREFIX+'-本轮全量回归结果.json',60,PREFIX+'-本机全量验收.json'),
 'Cloud全量':(PREFIX+'-公网适配全量回归结果.json',60,PREFIX+'-本地Cloud全量验收.json'),
 'Python专项':(PREFIX+'实际专项-python.json',26,PREFIX+'-Python专项验收.json'),
 'Cloud专项':(PREFIX+'实际专项-cloud.json',26,PREFIX+'-Cloud专项验收.json'),
}
reports={};payloads={};verification={};history={}
for label,(name,count,target) in inputs.items():
    file=HERE/name;wrapped=json.loads(file.read_bytes());v=latest(wrapped);passed(v,count)
    b=encoded(v);payloads[HERE/target]=b;reports[label]=v
    verification[label]={'input':rel(file),'inputSha256':sha(file),'path':rel(HERE/target),'sha256':sha_bytes(b),'passed':count,'failed':0,'at':v.get('at')}
    if v.get('runId'):verification[label]['runId']=v['runId']
    history[label]={'path':rel(file),'sha256':sha(file),'runs':len(wrapped.get('runs',[v])),'failedRunsRetained':sum(not x.get('pass',False) for x in wrapped.get('runs',[v]))}

# Full gates must bind the actual current APP, review wrapper and staff HTML, not APP alone.
for label in ('Python全量','Cloud全量'):
    hashes=reports[label].get('buildHashes',{});assert len(hashes)>=3
    for name,expected in hashes.items():assert sha(safe('03_当前APP/'+name))==expected,'full APP/admin drift: '+name
cloud=reports['Cloud全量'].get('cloudBuildHashes',{});assert {'generated/experience.html','generated/admin.html','generated/review.html','lib/eastern-api.ts','worker/index.ts','dist/server/index.js'}<=set(cloud)
for name,expected in cloud.items():assert sha(safe('04_研发源码/app/cloud/'+name))==expected,'Cloud generated/worker drift: '+name

prepared=data('06_验证与后续工作/'+PREFIX+'准备记录.json');sources=prepared['sourceHashes']
assert len(sources)==5
for path,expected in sources.items():assert sha(safe(path))==expected,'module source drift: '+path
identity=None;screens=[];view_observations={}
for label,target in [('Python专项','python'),('Cloud专项','cloud')]:
    v=reports[label];assert v['target']==target and v['identityUnchanged'] is True
    assert v['syntheticOnly'] is True and v['originalDatabaseOpened'] is False and v['externalRequests']==0 and v['schedulerDeployed'] is False and v['errors']==[]
    hashes=v['sourceBuildTestHashes'];assert len(hashes)>20 and set(sources)<=set(hashes)
    for path,expected in hashes.items():assert re.fullmatch('[a-f0-9]{64}',expected) and sha(safe(path))==expected,'actual active source/build/test drift: '+path
    if identity is None:identity=hashes
    else:assert identity==hashes,'two actual runs used different active dependencies'
    for path,expected in sources.items():assert hashes[path]==expected
    assert '04_研发源码/app/cloud/dist/server/BUILD_ID' in hashes
    views=v.get('ownerViews');assert isinstance(views,list) and len(views)==16
    expected_views={(w,m,l) for w in (375,430) for m in ('day','night') for l in ('zh','zh-Hant','en','bo')}
    assert {(x['width'],x['mode'],x['lang']) for x in views}==expected_views
    for view in views:
        top,bottom=view['top'],view['bottom'];assert top['documentWidth']<=view['width']+2 and top['appScrollWidth']<=top['appWidth']+2 and top['rootWidth']<=top['appWidth']+2 and top['backCount']==1
        assert bottom['scrollTop']==bottom['maxScroll'] and bottom['lastReceiptBottom']<=bottom['appBottom']+2
        if view['lang']=='bo':
            font=view['font'];assert font['faces'] and all(f['status']=='loaded' and f['family']=='EW Tibetan' for f in font['faces']) and 'EW Tibetan' in font['computed']
    font=v['fontArtifact'];assert font['status']==200 and font['bytes']==772924 and font['sha256']==sha(safe('04_研发源码/app/r4/vendor/NotoSerifTibetan.woff2')) and v['realFontLoaded'] is True
    assert font['kind']==('HTTP asset' if target=='cloud' else 'served HTML embedded font')
    assert isinstance(v.get('browserVersion'),str) and v['browserExecutable']
    photos=v['screenshots'];assert len(photos)==6
    for photo in photos:
        file=safe(photo['path']);assert file.parent==HERE and file.suffix=='.png' and sha(file)==photo['sha256']
        assert file.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    screens+=photos;view_observations[target]={'runId':v['runId'],'views':16,'screenshots':6,'browserVersion':v['browserVersion'],'browserExecutable':v['browserExecutable'],'font':font}

# Preserve independent support evidence without inventing primary HTTP counts.
for label,suffix,count in [('Python内存','Python内存结果',46),('Cloud内存','Cloud内存结果',50),('UI组件','UI结果',16)]:
    file=HERE/(PREFIX+suffix+'.json');v=json.loads(file.read_bytes());passed(v,count,'checks')
    if label=='Python内存':assert v['sourceSHA256']==sources['04_研发源码/app/r4/backend/privacy_retention.py']
    if label=='Cloud内存':assert v['sourceSHA256']==sources['04_研发源码/app/cloud/lib/privacy-retention.ts']
    if label=='UI组件':
        for name,expected in v['sourceHashes'].items():assert sources['04_研发源码/app/r4/'+name]==expected
    b=encoded(v);out=HERE/(PREFIX+'-'+label+'验收.json');payloads[out]=b
    verification[label]={'input':rel(file),'inputSha256':sha(file),'path':rel(out),'sha256':sha_bytes(b),'passed':count,'failed':0}

visual_file=HERE/(PREFIX+'最终视觉核验.json');visual=json.loads(visual_file.read_bytes())
assert visual.get('pass') is True and visual['sourceHashes']==sources and len(visual['screenshots'])==12
assert {(x['path'],x['sha256']) for x in visual['screenshots']}=={(x['path'],x['sha256']) for x in screens}
for label,target in [('Python专项','python'),('Cloud专项','cloud')]:
    reference=visual['actualReports'][target];assert reference['runId']==reports[label]['runId'] and sha(safe(reference['path']))==reference['sha256']
visual_snapshot=HERE/(PREFIX+'-视觉验收.json');payloads[visual_snapshot]=encoded(visual)

record={
 'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),
 'module':'PR05 本方数据库到期清理与权威个人清理', 'pass':True,
 'scope':'默认关闭；本人或当前管理员明确授权现政策后，按服务器固定asOf与真实写入跟踪清六类过期资料；分批可续跑，金融/额度/源审计保留。未实现供应商/备份删除或生产cron部署。',
 'verification':verification,'source_hashes':sources,'final_identity':identity,
 'app_sha256':sha(safe('03_当前APP/东方智慧-首页体验R4.html')),
 'admin_sha256':sha(safe('03_当前APP/计时后台-开发联调.html')),
 'cloud_build_hashes':cloud,'screenshots':screens,
 'visual_review':'逐一实看两端12个最终PNG；四语、单一共享返回、底部计数与管理员当前导航均核对。16视图为真实DOM/字体/滚动测量，不假称16PNG。',
 'visual_review_evidence':{'input':rel(visual_file),'inputSha256':sha(visual_file),'path':rel(visual_snapshot),'sha256':sha_bytes(payloads[visual_snapshot])},
 'view_observations':view_observations,'failure_history':history,
 'limitations':['六类正式期限/政策由项目方确认，null跳过；旧未知年龄默认跳过，可明确server-now纳管。','供应商和备份仍pending-confirmation，本机副本不自动清。','无长期记忆或向量服务；本记录冻结时不伪称存在记忆正文。','生产调度/受管执行身份及外部清理连接器未部署。','最小card quota/zone/epoch、设备连接、金融/履约/售后资金关联等必要台账保留，正式期限待政策。'],
 'diagnostic_resolution':'早期合成timer.start_ms=1与当前last_seen造成跨56年汇总阻塞；仅修测试夹具为相对当前时间、保留45s租约与独立age跟踪。相同标准Chromium/字体/Playwright截图四语探针恢复正常；未据此归因藏文字体或SDK，未改计时业务公式。原失败及探针history保留。',
 'invariants':{'snapshotsUseWriteBytes':True,'existingEvidenceNotOverwritten':True,'freezerWritesTaskOrSharedFiles':False,'originalDatabaseOpened':False,'publicDeployed':False,'financialLedgersDeleted':False,'actualProviderDeletionClaimed':False},
 'freezer':{'path':rel(Path(__file__).resolve()),'sha256':sha(Path(__file__).resolve())},
}
if RECORD.exists():
    old=json.loads(RECORD.read_bytes());assert old['source_hashes']==sources and old['final_identity']==identity
    for v in old['verification'].values():assert sha(safe(v['path']))==v['sha256']
    assert sha(safe(old['visual_review_evidence']['path']))==old['visual_review_evidence']['sha256']
    print(json.dumps({'pass':True,'alreadyFrozen':True,'recordSHA256':sha(RECORD)},ensure_ascii=True));sys.exit(0)
payloads[RECORD]=encoded(record)
assert all(p.parent==HERE and not p.exists() for p in payloads),'final snapshot already exists; no overwrite permitted'
if '--write' in sys.argv:
    # All identities verified before the first write. Explicit binary writes prevent CRLF drift.
    for p,b in payloads.items():
        with p.open('xb') as file:file.write(b)
    for p,b in payloads.items():assert p.read_bytes()==b
print(json.dumps({'pass':True,'dryRun':'--write' not in sys.argv,'snapshots':len(payloads),'checks':{'full':[60,60],'actual':[26,26],'memory':[46,50],'UI':16,'views':[16,16],'screenshots':12},'record':rel(RECORD),'recordSHA256':sha_bytes(payloads[RECORD])},ensure_ascii=True))
