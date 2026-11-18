"""Run only after all round2 owned gates stop; preserve bytes before QA fixes."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
PREFIX='负责人优化建议-卡组迁移'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())


def preserve():
    snapshot=read(OUT/(PREFIX+'-round2完整依赖诊断.json'))
    for name,digest in snapshot['sourceAndBuildHashes'].items():
        assert sha(ROOT/name)==digest,('Round1 input changed before preservation',name)
    baseline=read(OUT/(PREFIX+'-实施前核对.json'))
    for name,digest in baseline['protectedHistoricalSHA256'].items():
        assert sha(ROOT/name)==digest,('Earlier evidence changed',name)
    tag=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    target=OUT/(PREFIX+'-round2保全-'+tag+'.json');assert not target.exists()
    copies={};origins={};reports=[];runtime={}
    def copy(path):
        relative=path.relative_to(ROOT).as_posix()
        if relative in origins:return
        destination=OUT/(PREFIX+'-round2保全-'+tag+'-'+str(len(copies)+1).zfill(4)+path.suffix)
        assert path.parent==OUT and not destination.exists()
        shutil.copyfile(path,destination);assert sha(path)==sha(destination)
        origins[relative]=destination.relative_to(ROOT).as_posix()
        copies[origins[relative]]=sha(destination)
    suites=[('-本轮全量回归结果','full'),('-公网适配全量回归结果','full')]
    suites += [(title+'-'+backend,suite) for backend in ('python','cloud') for title,suite in [('专项','special'),('补充视觉','visual'),('B11兼容','b11-compat'),('抽卡兼容','card-compat'),('逐域兼容','privacy-compat'),('注销兼容','closure-compat')]]
    for suffix,suite in suites:
        path=OUT/(PREFIX+suffix+'.json')
        if not path.exists():continue
        document=read(path);run=document.get('latest',document)
        identity=run.get('cardMigrationLauncher',{}).get('sourceAndBuildHashes') or run.get('cardMigrationSources')
        assert identity==snapshot['sourceAndBuildHashes'],('Different round2 identity',path.name)
        copy(path);reports.append({'original':path.relative_to(ROOT).as_posix(),'copy':origins[path.relative_to(ROOT).as_posix()],'pass':run.get('pass'),'passed':run.get('passed'),'failed':run.get('failed'),'suite':suite,'failedNames':[r['name'] for r in run.get('results',[]) if not r.get('pass')]})
        for artifact in run.get('cardMigrationLauncher',{}).get('runtimeArtifacts',run.get('runtimeArtifacts',[])):
            for key in ('bundle','metafile'):
                anchor=artifact.get(key)
                if isinstance(anchor,dict) and anchor.get('path') and anchor.get('sha256'):
                    p=ROOT/anchor['path'];assert sha(p)==anchor['sha256'];runtime[anchor['path']]=anchor['sha256']
                elif isinstance(anchor,str) and artifact.get(key+'Sha256'):
                    p=ROOT/anchor;assert sha(p)==artifact[key+'Sha256'];runtime[anchor]=artifact[key+'Sha256']
            for field in ('inputHashes','runtimeDependencyHashes'):
                for name,digest in artifact.get(field,{}).items():assert sha(ROOT/name)==digest;runtime[name]=digest
    # Deterministic full/compat names may otherwise be replaced on a fresh retry.
    for path in list(OUT.glob(PREFIX+'*')):
        if path.is_file() and path.suffix.lower() in {'.png','.webm'} and not any(tag in path.name for tag in ('-round1保全-','-round2保全-')):
            copy(path)
    for path in list(OUT.glob(PREFIX+'*')):
        if path.is_file() and path.suffix=='.json' and not any(tag in path.name for tag in ('-round1保全-','-round2保全-')) and ('接口实测证据' in path.name or '启动诊断' in path.name):copy(path)
    for suffix in ('夹具控制.ts',):
        original=OUT/(PREFIX+suffix)
        destination=OUT/(PREFIX+'-round2保全-'+tag+'-'+suffix.replace('.ts','源.txt'))
        assert sha(original)==snapshot['sourceAndBuildHashes'][original.relative_to(ROOT).as_posix()] and not destination.exists()
        destination.write_bytes(original.read_bytes());copies[destination.relative_to(ROOT).as_posix()]=sha(destination);origins[original.relative_to(ROOT).as_posix()]=destination.relative_to(ROOT).as_posix()
    record={'at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'pass':True,'scope':'Immutable round2 original reports/native media and the original changed QA observer before any fix/retry; no source, book, handoff or earlier frozen byte mutation.','snapshotCanonicalSHA256':snapshot['canonicalSHA256'],'snapshotSHA256':sha(OUT/(PREFIX+'-round2完整依赖诊断.json')),'reports':reports,'originalToPreservedCopy':origins,'preservedReportCopiesSHA256':copies,'nativeEvidenceSHA256':runtime,'protectedHistoricalFilesUnchanged':len(baseline['protectedHistoricalSHA256'])}
    target.write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'pass':True,'reports':len(reports),'copies':len(copies),'path':target.name,'sha256':sha(target)}))


if __name__=='__main__':preserve()
