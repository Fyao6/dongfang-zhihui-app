"""Inspect a candidate before writing the immutable performance repair acceptance."""
import argparse,hashlib,json,subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
PREFIX='负责人优化建议-本地可靠性'
NODE=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
AUTH='06_验证与后续工作/负责人优化建议-本地可靠性性能修复授权基线-rev2.json'
AUTH_SHA='1f8b83fa08f0d74dee7d1a1644e023f57b64263410b08fecc2ab202ef7f72edb'
SNAP='06_验证与后续工作/负责人优化建议-本地可靠性性能复验-round4-sdk-stop完整依赖诊断.json'
SNAP_SHA='460a22fd9cd30e686e8d0faf7b83909afc2093342db7ed85edb594c1503217ff'
COMP='06_验证与后续工作/负责人优化建议-本地可靠性性能复验原生连接组件-8358e47ef43e47c28b4f768e35287f02.json'
COMP_SHA='57823bf91e5262635d5d3b8ff6d342cc5205eeac9f4a2a1d66c63819aecbada7'
CANDIDATE=OUT/(PREFIX+'-性能修复复验-候选.json')
FINAL=OUT/(PREFIX+'-性能修复复验.json')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text('utf-8'))

def local(name):
    assert not Path(name).is_absolute()
    p=(ROOT/name).resolve();assert p.is_relative_to(ROOT) and p.is_file();return p

def inspect():
    command=[str(NODE),str(OUT/(PREFIX+'修复基线.cjs')),'--inspect-repair-proof',
             '--repair-proof-sha256='+sha(CANDIDATE),'--repair-authorization-sha256='+AUTH_SHA]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,('Read-only candidate inspection failed',result.stdout,result.stderr)
    value=json.loads(result.stdout);assert value['pass'] and value['inspectionOnly'] and value['opsExecutionAllowed'] is False
    return value

def candidate(preflight_name,preflight_sha):
    assert not CANDIDATE.exists() and not FINAL.exists()
    assert sha(local(AUTH))==AUTH_SHA and sha(local(SNAP))==SNAP_SHA and sha(local(COMP))==COMP_SHA
    preflight=local(preflight_name)
    assert preflight.parent==OUT and preflight.name.startswith(PREFIX+'性能复验-入口预检-')
    assert sha(preflight)==preflight_sha
    snapshot=read(local(SNAP));assert snapshot['pass'] and snapshot['inputCount']==548
    authorization=read(local(AUTH));base=read(OUT/(PREFIX+'-实施前核对.json'))
    delta=authorization['productChanges'];preserved={}
    for name,digest in base['protectedHistoricalSHA256'].items():
        path=delta[name]['originalBytes']['path'] if name in delta else name
        assert sha(local(path))==digest,('Historical evidence changed',name)
        preserved[path]=digest
    catalog=read(OUT/(PREFIX+'性能复验入口清单.json'));assert catalog['formalReady'] and len(catalog['entries'])==14
    verification={};totals={'Python':0,'Cloud':0}
    for entry in catalog['entries']:
        name='06_验证与后续工作/'+entry['report'];path=local(name);document=read(path);report=document.get('latest',document)
        assert report['pass'] and report['failed']==0 and report['passed']==entry['expectedCount']
        meta=report['localReliabilityRegressionLauncher'];assert meta['childExitCode']==0 and meta['reportFreshForInvocation'] and meta['identityUnchanged']
        assert meta['sourceAndBuildHashes']==snapshot['sourceAndBuildHashes']
        cleanup=meta['cleanup']
        assert cleanup['resourceFactoryFinallyCompleted'] and cleanup['ownedProcessInventoryComplete']
        assert cleanup['remainingOwnedPids']==[] and cleanup['privateVarsRemaining']==[]
        verification[entry['target']+'/'+entry['suite']]={'path':name,'sha256':sha(path),'passed':report['passed']}
        totals['Python' if entry['target']=='python' else 'Cloud']+=report['passed']
    assert totals=={'Python':195,'Cloud':195}
    value={'pass':True,'stage':31,'kind':'performance-fix-business-acceptance',
           'at_beijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),
           'perBackendPassed':totals,'authorization':{'path':AUTH,'sha256':AUTH_SHA},
           'executionSnapshot':{'path':SNAP,'sha256':SNAP_SHA},
           'strictPreflight':{'path':preflight_name,'sha256':preflight_sha},
           'nativeConnectionComponent':{'path':COMP,'sha256':COMP_SHA,'passed':4},
           'verification':verification,'reportIdentityHashes':snapshot['sourceAndBuildHashes'],
           'sourceChangedSinceStage30':True,'productChanges':delta,
           'protectedHistoricalSHA256':preserved,'freezeHelperSHA256':sha(Path(__file__)),
           'frontendBuildChanged':False,'cloudProductCodeChanged':False,
           'productionEnabled':False,'formalAcceptance':False,
           'boundary':'Actual business re-verification and native connection safety only. Full authenticated load, backup/restore, rollback and media observations are separate requirements.'}
    with CANDIDATE.open('xb') as f:f.write((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    result=inspect();print(json.dumps({'candidate':CANDIDATE.relative_to(ROOT).as_posix(),'sha256':sha(CANDIDATE),'inspectionPassed':result['pass'],'perBackendPassed':result['perBackendPassed'],'inputCount':result['inputCount']},ensure_ascii=True))

def freeze():
    assert not FINAL.exists();value=read(CANDIDATE)
    assert value['freezeHelperSHA256']==sha(Path(__file__))
    inspect()
    data=CANDIDATE.read_bytes()
    with FINAL.open('xb') as f:f.write(data)
    assert sha(FINAL)==sha(CANDIDATE)
    command=[str(NODE),str(OUT/(PREFIX+'修复基线.cjs')),'--verify-repair-proof',
             '--repair-proof-sha256='+sha(FINAL),'--repair-authorization-sha256='+AUTH_SHA]
    subprocess.run(command,cwd=ROOT,check=True)
    print(json.dumps({'pass':True,'path':FINAL.relative_to(ROOT).as_posix(),'sha256':sha(FINAL)},ensure_ascii=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',action='store_true');p.add_argument('--freeze',action='store_true');p.add_argument('--preflight');p.add_argument('--preflight-sha256');a=p.parse_args()
    assert a.candidate!=a.freeze
    if a.candidate:candidate(a.preflight,a.preflight_sha256)
    else:freeze()
