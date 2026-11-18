"""Package this paused project, full local Git objects and one consistent owned preview snapshot."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, os, subprocess, zipfile, time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent
now=datetime.now(timezone(timedelta(hours=8)))
name='东方智慧APP_回家继续_'+now.strftime('%Y%m%d_%H%M%S')
target=OUT/(name+'.zip')
temporary=OUT/(name+'.partial')
assert not target.exists() and not temporary.exists()
checkpoint=json.loads((ROOT/'06_验证与后续工作/回家继续-进度与记忆.json').read_bytes())
snapshot=ROOT/checkpoint['database_snapshot']['source']
assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==checkpoint['database_snapshot']['sha256']
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
skip_dirs={'node_modules','.wrangler','__pycache__','.pytest_cache','.venv','.next','.cache'}
compressed={'.png','.jpg','.jpeg','.gif','.webp','.mp4','.webm','.mp3','.m4a','.ogg','.pdf','.woff','.woff2','.gz','.7z','.rar'}
files=[];excluded=[]
for current,dirs,names in os.walk(ROOT,followlinks=False):
    base=Path(current)
    kept=[]
    for folder in dirs:
        path=base/folder
        rel=path.relative_to(ROOT).as_posix()
        junction=getattr(path,'is_junction',lambda:False)()
        if folder in skip_dirs or path.is_symlink() or junction or rel in ('.git/hooks','.git/logs'):
            excluded.append({'path':rel+'/', 'reason':'machine cache, optional local hooks/reflog or external link'})
        else:kept.append(folder)
    dirs[:]=kept
    for filename in names:
        file=base/filename;rel=file.relative_to(ROOT).as_posix();low=filename.lower()
        reason=None
        if file.is_symlink() or not file.resolve().is_relative_to(ROOT):reason='external link'
        elif low.endswith(('.zip','.partial')):reason='historical archive; avoid nested complete packages'
        elif low.endswith(('.sqlite','.sqlite3','.db','.db3','-wal','-shm','.pyc','.pyo')):reason='temporary/other database; owned preview is inserted from consistent snapshot'
        elif ((low.startswith('.env') or low.startswith('.dev.vars')) and not low.endswith(('.example','.sample'))):reason='machine environment or tunnel credential file'
        elif rel.startswith('.git/') and (low.endswith('.lock') or rel in ('.git/config','.git/config.worktree','.git/FETCH_HEAD','.git/COMMIT_EDITMSG','.git/objects/info/alternates')):reason='machine-specific Git metadata; portable config generated'
        elif low.startswith('回家继续-打包结果') or low.startswith('回家继续-压缩包校验'):reason='outer package receipt'
        if reason:excluded.append({'path':rel,'reason':reason});continue
        if file.is_file():files.append((rel,file))
files.append((checkpoint['database_snapshot']['archive_path'],snapshot))
assert len({rel for rel,_ in files})==len(files)
files.sort()
manifest={'createdAt':now.isoformat(),'root':name,'checkpointCommit':head,'verifiedStages':len(checkpoint['verified_stages']),'memoryIntegrated':False,'databaseSnapshot':checkpoint['database_snapshot'],'gitHistoryIncluded':True,'gitMachineConfigurationReplaced':True,'files':[],'excluded':excluded,'manifestSelfHashExcluded':True}
total=sum(file.stat().st_size for _,file in files)
print(json.dumps({'phase':'packing','files':len(files),'sourceMB':round(total/1024/1024,1),'destination':str(target)},ensure_ascii=False),flush=True)
last=time.monotonic()
with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as archive:
    for index,(rel,file) in enumerate(files,1):
        info=zipfile.ZipInfo(name+'/'+rel)
        source_time=time.localtime(file.stat().st_mtime)[:6]
        info.date_time=source_time if 1980<=source_time[0]<=2107 else (1980,1,1,0,0,0)
        info.compress_type=zipfile.ZIP_STORED if file.suffix.lower() in compressed or rel.startswith('.git/objects/') else zipfile.ZIP_DEFLATED
        info.external_attr=(0o100644<<16)
        digest=hashlib.sha256();size=0
        with file.open('rb') as source, archive.open(info,'w',force_zip64=True) as dest:
            while True:
                chunk=source.read(1024*1024)
                if not chunk:break
                dest.write(chunk);digest.update(chunk);size+=len(chunk)
        manifest['files'].append({'path':rel,'bytes':size,'sha256':digest.hexdigest()})
        if time.monotonic()-last>20:
            print(json.dumps({'phase':'packing','done':index,'total':len(files)},ensure_ascii=False),flush=True);last=time.monotonic()
    config=b'[core]\n\trepositoryformatversion = 0\n\tfilemode = false\n\tbare = false\n\tlogallrefupdates = true\n\tsymlinks = false\n\tignorecase = true\n'
    archive.writestr(name+'/.git/config',config)
    manifest['files'].append({'path':'.git/config','bytes':len(config),'sha256':hashlib.sha256(config).hexdigest(),'generatedPortableConfig':True})
    archive.writestr(name+'/回家继续-包内文件清单.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'phase':'checking_crc','archiveMB':round(temporary.stat().st_size/1024/1024,1)},ensure_ascii=False),flush=True)
with zipfile.ZipFile(temporary) as archive:
    assert archive.testzip() is None
    by_name={entry['path']:entry for entry in manifest['files']}
    critical=['AGENTS.md','回家继续-先读我.txt','start-home.ps1','在家启动APP.cmd','03_当前APP/东方智慧-首页体验R4.html','06_验证与后续工作/回家继续-进度与记忆.json',checkpoint['database_snapshot']['archive_path'],*checkpoint['memory_preparation']['files']]
    critical.extend(stage['path'] for stage in checkpoint['verified_stages'])
    for rel in critical:
        payload=archive.read(name+'/'+rel)
        assert hashlib.sha256(payload).hexdigest()==by_name[rel]['sha256'],rel
temporary.rename(target)
digest=hashlib.sha256()
with target.open('rb') as file:
    while True:
        data=file.read(8*1024*1024)
        if not data:break
        digest.update(data)
receipt={'pass':True,'archive':str(target),'bytes':target.stat().st_size,'MB':round(target.stat().st_size/1024/1024,1),'sha256':digest.hexdigest(),'files':len(manifest['files'])+1,'allEntryCRCChecked':True,'criticalFilesSHA256Checked':len(critical),'checkpointCommit':head,'verifiedStages':17,'memoryPreparationNotIntegrated':True,'gitHistoryIncluded':True,'originalFilesDeleted':False,'excludedCount':len(excluded)}
receipt_path=ROOT/'06_验证与后续工作/回家继续-打包结果.json'
receipt_path.write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
target.with_suffix('.sha256.txt').write_bytes((receipt['sha256']+'  '+target.name+'\n').encode())
print(json.dumps(receipt,ensure_ascii=False),flush=True)
