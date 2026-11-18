"""Collect the fourteen actual new invocations; no services or old-file writes."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PREFIX = '负责人优化建议-本地可靠性Cloud复验'
NODE = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
AUTH = '06_验证与后续工作/' + PREFIX + '授权基线-rev3.json'
AUTH_SHA = '3f2d92040442fed4047ab1115ebe9301f449997507b4b89fe1d28f58384cbef7'
SNAPSHOT = '06_验证与后续工作/' + PREFIX + '-round1完整依赖诊断.json'
SNAPSHOT_SHA = '7c383abdbaad681f02fd3327ef2cbbfa4860a18859bc322e2fd52d1d7fbf8803'
CANDIDATE = OUT / (PREFIX + '-修复复验-候选.json')
FINAL = OUT / (PREFIX + '-修复复验.json')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_bytes())


def local(name):
    assert isinstance(name, str) and not Path(name).is_absolute() and '\\' not in name
    p = (ROOT / name).resolve()
    assert p.is_relative_to(ROOT) and p.is_file()
    return p


def inspect():
    command = [str(NODE), str(OUT / (PREFIX + '修复基线.cjs')), '--inspect-repair-proof',
               '--repair-proof-sha256=' + sha(CANDIDATE), '--repair-authorization-sha256=' + AUTH_SHA]
    r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, ('Read-only candidate inspection failed', r.stdout, r.stderr)
    value = json.loads(r.stdout)
    assert value['pass'] and value['inspectionOnly'] and value['opsExecutionAllowed'] is False
    return value


def candidate(preflight_name, preflight_sha):
    assert not CANDIDATE.exists() and not FINAL.exists()
    assert sha(local(AUTH)) == AUTH_SHA and sha(local(SNAPSHOT)) == SNAPSHOT_SHA
    preflight = local(preflight_name)
    assert preflight.parent == OUT and preflight.name.startswith(PREFIX + '-入口预检-')
    assert sha(preflight) == preflight_sha
    snapshot = read(local(SNAPSHOT))
    assert snapshot['pass'] and snapshot['inputCount'] == 672
    authorization = read(local(AUTH))
    base = read(local(authorization['previousBaseline']['path']))
    delta = authorization['productChanges']
    preserved = {}
    for name, digest in base['protectedHistoricalSHA256'].items():
        target = delta[name]['originalBytes']['path'] if name in delta else name
        assert sha(local(target)) == digest, ('Protected historical bytes changed', name)
        preserved[target] = digest
    catalog = read(OUT / (PREFIX + '入口清单.json'))
    assert catalog['formalReady'] and len(catalog['entries']) == 14
    verification, totals = {}, {'Python': 0, 'Cloud': 0}
    for entry in catalog['entries']:
        name = '06_验证与后续工作/' + entry['report']
        file = local(name)
        document = read(file)
        r = document.get('latest', document)
        m = r['cloudReliabilityRegressionLauncher']
        assert r['pass'] is True and r['failed'] == 0 and r['passed'] == entry['expectedCount']
        assert m['childExitCode'] == 0 and m['reportFreshForInvocation'] is True
        assert m['identityUnchanged'] and m['sourceUnchangedRelativeToRepairSnapshot']
        assert m['sourceAndBuildHashes'] == snapshot['sourceAndBuildHashes']
        assert m['preRunSnapshot']['path'] == SNAPSHOT and m['preRunSnapshot']['sha256'] == SNAPSHOT_SHA
        assert m['actualInvocation'] == entry
        assert m['repairAuthorization']['sha256'] == AUTH_SHA
        assert m['cleanup']['ownedProcessInventoryComplete'] and not m['cleanup']['remainingOwnedPids']
        assert not m['cleanup']['privateVarsRemaining']
        assert datetime.fromisoformat(m['invocationStarted'].replace('Z', '+00:00')) >= datetime.fromisoformat(snapshot['at'].replace('Z', '+00:00'))
        key = entry['target'] + '/' + entry['suite']
        assert key not in verification
        verification[key] = {'path': name, 'sha256': sha(file), 'passed': r['passed']}
        totals['Python' if entry['target'] == 'python' else 'Cloud'] += r['passed']
    assert totals == {'Python': 195, 'Cloud': 195}
    old = read(local(authorization['previousRepairProof']['path']))
    value = {'pass': True, 'stage': 31, 'kind': 'cloud-schema-singleflight-business-acceptance',
             'at': datetime.now(timezone.utc).isoformat(), 'formalAcceptance': False,
             'perBackendPassed': totals, 'authorization': {'path': AUTH, 'sha256': AUTH_SHA},
             'executionSnapshot': {'path': SNAPSHOT, 'sha256': SNAPSHOT_SHA},
             'strictPreflight': {'path': preflight_name, 'sha256': preflight_sha},
             'previousPythonNativeComponent': old['nativeConnectionComponent'],
             'cloudSchemaComponent': {'path': '06_验证与后续工作/负责人优化建议-本地可靠性Cloud安全短专项-35063d60f0cb42bb977e88c272be9d41.json', 'sha256': 'cdedfdf163525fd3be391e7d180ab33d67afd712626cc67eb0ad7a02d7e4188e'},
             'boundedCloudDiagnostic': {'path': '06_验证与后续工作/负责人优化建议-本地可靠性Cloud短诊断-802b7e53510d467582dce8e24a30fd5b.json', 'sha256': '13948d9bcbcb01f6ee1bdfdcea839621886ceebde8016cd74956a77006dd5fbd'},
             'verification': verification, 'reportIdentityHashes': snapshot['sourceAndBuildHashes'],
             'productChanges': delta, 'protectedHistoricalSHA256': preserved,
             'freezeHelper': {'path': Path(__file__).relative_to(ROOT).as_posix(), 'sha256': sha(Path(__file__))},
             'sourceChangedSinceStage30': True, 'originalStage30ProductUnchanged': False,
             'frontendBuildChanged': False, 'cloudProductCodeChanged': True, 'cloudBuildChanged': True,
             'productionEnabled': False,
             'boundary': 'Actual fourteen-suite business revalidation plus existing Python native safety and actual Cloud schema/auth safety. Long load, media and restore are separate evidence, never inferred here.'}
    with CANDIDATE.open('xb') as f:
        f.write((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
    try:
        inspect()
    except Exception as e:
        diagnostic = OUT / (PREFIX + '-候选拒绝-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')
        diagnostic.write_bytes((json.dumps({'pass': False, 'formalAcceptance': False, 'candidateSha256': sha(CANDIDATE), 'errorType': type(e).__name__, 'candidatePreserved': True}, ensure_ascii=False, indent=2) + '\n').encode())
        raise
    print(json.dumps({'candidate': CANDIDATE.relative_to(ROOT).as_posix(), 'sha256': sha(CANDIDATE), 'inspectionPassed': True, 'perBackendPassed': totals, 'inputCount': 672}))


def freeze():
    assert not FINAL.exists()
    value = read(CANDIDATE)
    assert value['freezeHelper']['sha256'] == sha(Path(__file__))
    inspect()
    data = CANDIDATE.read_bytes()
    with FINAL.open('xb') as f:
        f.write(data)
    assert sha(FINAL) == sha(CANDIDATE)
    subprocess.run([str(NODE), str(OUT / (PREFIX + '修复基线.cjs')), '--verify-repair-proof',
                    '--repair-proof-sha256=' + sha(FINAL), '--repair-authorization-sha256=' + AUTH_SHA], cwd=ROOT, check=True)
    print(json.dumps({'pass': True, 'path': FINAL.relative_to(ROOT).as_posix(), 'sha256': sha(FINAL)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', action='store_true')
    p.add_argument('--inspect', action='store_true')
    p.add_argument('--freeze', action='store_true')
    p.add_argument('--preflight')
    p.add_argument('--preflight-sha256')
    a = p.parse_args()
    if not any((a.candidate, a.inspect, a.freeze)):
        print(json.dumps({'status': 'prepared-not-run', 'startsService': False, 'candidateCreated': False, 'proofCreated': False}))
    else:
        assert sum((a.candidate, a.inspect, a.freeze)) == 1
        if a.candidate:
            candidate(a.preflight, a.preflight_sha256)
        elif a.inspect:
            print(json.dumps(inspect()))
        else:
            freeze()
