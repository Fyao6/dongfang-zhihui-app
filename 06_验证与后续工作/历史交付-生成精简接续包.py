"""Repackage the verified portable snapshot without Git history, old deployment archives or test media."""
from pathlib import Path, PurePosixPath
from datetime import datetime,timezone,timedelta
import zipfile,json,hashlib,time

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'东方智慧APP_回家继续_20261113_125820.zip'
stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
folder='东方智慧APP_回家接续'
target=ROOT.parent/('东方智慧APP_接续精简包_'+stamp+'.zip')
temporary=target.with_suffix('.partial')
assert SOURCE.is_file() and not target.exists() and not temporary.exists()
media={'.png','.jpg','.jpeg','.gif','.webp','.svg','.mp4','.webm','.mov','.avi','.mp3','.m4a','.wav','.ogg'}
manifest={'type':'current-project-resume','createdAt':datetime.now(timezone(timedelta(hours=8))).isoformat(),'gitHistoryIncluded':False,'historicalVisualMediaIncluded':False,'currentSourceAndAppIncluded':True,'previewDatabaseIncluded':True,'developmentPaused':True,'verifiedStages':17,'memoryIntegrated':False,'files':[],'excluded':[],'manifestSelfHashExcluded':True}
with zipfile.ZipFile(SOURCE) as old,zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as new:
    for info in old.infolist():
        rel=info.filename.split('/',1)[-1]
        path=PurePosixPath(rel)
        reason=None
        if '.git' in path.parts:reason='Git history remains in the original full archive'
        elif rel=='回家继续-包内文件清单.json':continue
        elif rel.startswith('06_验证与后续工作/') and path.suffix.lower() in media:reason='Historical test output media; reports and rerun scripts retained'
        elif rel.lower().endswith(('.zip','.tar','.tar.gz','.tgz','.7z','.rar','.tar.bz2','.tar.xz')):reason='Historical deployment archive'
        elif rel.startswith('06_验证与后续工作/') and path.suffix.lower() in {'.msi','.exe','.dmg','.pkg'}:reason='Optional machine installer'
        if reason:
            manifest['excluded'].append({'path':rel,'bytes':info.file_size,'reason':reason});continue
        data=old.read(info)
        if rel=='回家继续-先读我.txt':
            text=data.decode('utf-8-sig')
            text=text.replace('Git提交历史随包保存；机器专属Git配置改为便携配置，远程地址可在家中重新设置。','本精简包不含Git提交历史；当前全部源码、未完成准备代码、报告与运行数据均保留。若要回滚旧提交，使用原大包或原机器。')
            text='精简接续包说明\n本包保留当前项目、源码、开发记忆、17阶段验收报告与本轮预览库。\n不带.git历史、旧部署压缩包、06历史截图录像或工具安装包。旧视觉报告仍保留原路径/SHA，但离线逐图复核需从原大包补媒体；正常运行和重新跑full60/实际专项不依赖这些旧图。\n解压后可直接按下面步骤启动，不必先恢复Git历史。\n\n'+text
            data=text.encode('utf-8-sig')
        elif rel=='06_验证与后续工作/回家继续-进度与记忆.json':
            state=json.loads(data)
            state['package_policy']['include']='当前全部源码/构建/原需求/说明/历史报告/未完成准备文件/本轮预览库一致快照'
            state['package_policy']['exclude']+=['所有层级的.git历史','历史部署tar.gz/压缩包','06历史验收图片/录像和可选安装包']
            state['package_policy']['gitHistoryIncluded']=False
            state['package_policy']['historicalVisualMediaIncluded']=False
            state['package_policy']['visualReviewNote']='旧报告作为历史声明保留；缺少旧截图时不可宣称已重新逐图复验。运行和新跑full60/actual所需输入媒体仍在02/04。'
            data=(json.dumps(state,ensure_ascii=False,indent=2)+'\n').encode()
        elif rel=='AGENTS.md':
            data+=('\n\n### 精简接续包边界\n用户指出原包过大，本包只省略Git历史、旧部署压缩包、06历史图像录像与可选安装包；当前源码、原需求、报告、开发记忆、未完成PR03准备代码及本轮预览库仍保留。开发仍暂停，不自动执行未完成helper。旧视觉报告的图片不在精简包，严格历史逐图复核须从原大包补齐；正常运行/重新生成测试截图不依赖旧图。\n').encode()
        out=zipfile.ZipInfo(folder+'/'+rel)
        out.date_time=info.date_time
        out.compress_type=info.compress_type
        out.external_attr=info.external_attr
        new.writestr(out,data)
        manifest['files'].append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    script=Path(__file__).resolve();data=script.read_bytes();rel=script.relative_to(ROOT).as_posix()
    new.writestr(folder+'/'+rel,data)
    manifest['files'].append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    new.writestr(folder+'/回家继续-包内文件清单.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'phase':'checking','MB':round(temporary.stat().st_size/1024**2,1),'files':len(manifest['files'])},ensure_ascii=False),flush=True)
with zipfile.ZipFile(temporary) as archive:
    assert archive.testzip() is None
    expected={x['path']:x for x in manifest['files']}
    critical=['AGENTS.md','回家继续-先读我.txt','start-home.ps1','在家启动APP.cmd','03_当前APP/东方智慧-首页体验R4.html','06_验证与后续工作/回家继续-进度与记忆.json','06_验证与后续工作/负责人优化建议-隔离预览.sqlite3','04_研发源码/app/r4/backend/memory_service.py','04_研发源码/app/cloud/lib/memory-service.ts','04_研发源码/app/r4/memory-service-ui.js','04_研发源码/app/r4/memory-service-ui.css','06_验证与后续工作/东方智慧APP优化任务表_依据v1.0_20261112.xlsx']
    for rel in critical:assert hashlib.sha256(archive.read(folder+'/'+rel)).hexdigest()==expected[rel]['sha256'],rel
    assert not any('/.git/' in x.filename for x in archive.infolist())
temporary.rename(target)
digest=hashlib.sha256()
with target.open('rb') as file:
    while True:
        data=file.read(8*1024*1024)
        if not data:break
        digest.update(data)
receipt={'pass':True,'archive':str(target),'bytes':target.stat().st_size,'MB':round(target.stat().st_size/1024**2,1),'sha256':digest.hexdigest(),'files':len(manifest['files'])+1,'allEntryCRCChecked':True,'criticalFilesSHA256Checked':len(critical),'gitHistoryIncluded':False,'originalLargeArchivePreserved':True,'excludedEntries':len(manifest['excluded'])}
(ROOT/'06_验证与后续工作/回家继续-精简包结果.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
target.with_suffix('.sha256.txt').write_bytes((receipt['sha256']+'  '+target.name+'\n').encode())
print(json.dumps(receipt,ensure_ascii=False),flush=True)
