from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PREFIX = '负责人优化建议-本地可靠性Cloud'
SOURCE = '04_研发源码/app/cloud/lib/eastern-api.ts'
DIST = '04_研发源码/app/cloud/dist/'
BEFORE = OUT / (PREFIX + '修复前-原字节清单.json')
TARGET = OUT / (PREFIX + '候选短诊断源码锚.json')
sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    assert not TARGET.exists()
    before = json.loads(BEFORE.read_bytes())
    assert sha(BEFORE.read_bytes()) == '7388e2d641f97b7bd146c22c2b4bfab790196abf24780c21b58d94008c27a9ce'
    inherited = before['sourceAndBuildHashes']
    actual = {}
    for name, digest in inherited.items():
        if name.startswith(DIST):
            continue
        current = sha((ROOT / name).read_bytes())
        if name != SOURCE:
            assert current == digest, 'Unexpected non-Cloud delta: ' + name
        actual[name] = current
    for path in sorted((ROOT / DIST).rglob('*')):
        if path.is_file():
            assert not path.is_symlink()
            actual[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    changes = {}
    prior = before['preserved']
    current_cloud = {name: digest for name, digest in actual.items() if name == SOURCE or name.startswith(DIST)}
    for name in sorted(set(prior) | set(current_cloud)):
        original = prior.get(name)
        current = current_cloud.get(name)
        if original:
            copy = original['originalBytes']
            assert sha((ROOT / copy['path']).read_bytes()) == copy['sha256'] == original['sha256']
        if (original or {}).get('sha256') != current:
            changes[name] = {'beforeSha256': (original or {}).get('sha256'), 'afterSha256': current,
                             'originalBytes': original['originalBytes'] if original else None}
    assert SOURCE in changes
    assert all(name == SOURCE or name.startswith(DIST) for name in changes)
    result = {'schemaVersion': 1, 'stage': 31, 'authorizedByRoot': True,
              'at': datetime.now(timezone.utc).isoformat(), 'diagnosticOnly': True,
              'businessAcceptance': False, 'productionEnabled': False,
              'purpose': 'same bounded native Cloud diagnostic and schema/auth safety checks after explicit preserved delta',
              'previousSnapshot': before['previousExecutionSnapshot'],
              'originalCloudBytes': {'path': BEFORE.relative_to(ROOT).as_posix(), 'sha256': sha(BEFORE.read_bytes())},
              'cloudProductChanges': changes,
              'currentSourceAndBuildHashes': dict(sorted(actual.items())),
              'boundary': 'Not an old repair-proof pass. All non-Cloud inputs remain exact; only listed Cloud source/build differences are authorized for diagnosis.'}
    with TARGET.open('xb') as stream:
        stream.write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'diagnosticOnly': True, 'files': len(actual),
                      'cloudChanged': len(changes), 'sha256': sha(TARGET.read_bytes())}))


if __name__ == '__main__':
    main()
