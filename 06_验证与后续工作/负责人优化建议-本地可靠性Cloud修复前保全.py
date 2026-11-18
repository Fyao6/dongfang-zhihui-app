"""Preserve exact current Cloud source/build bytes before the bounded schema fix.

This command neither opens a database nor starts a service. Existing frozen
reports are read-only. Flat byte copies avoid another project directory.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PREFIX = '负责人优化建议-本地可靠性Cloud修复前'
MANIFEST = OUT / (PREFIX + '-原字节清单.json')
SOURCE = ROOT / '04_研发源码/app/cloud/lib/eastern-api.ts'
DIST = ROOT / '04_研发源码/app/cloud/dist'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    assert not MANIFEST.exists(), 'Never overwrite a preservation manifest'
    prior_path = OUT / '负责人优化建议-本地可靠性性能复验-round4-sdk-stop完整依赖诊断.json'
    prior = json.loads(prior_path.read_bytes())
    for name, digest in prior['sourceAndBuildHashes'].items():
        assert sha((ROOT / name).read_bytes()) == digest, name
    paths = [SOURCE, *sorted(p for p in DIST.rglob('*') if p.is_file())]
    assert len(paths) == len(set(paths)) and len(paths) > 30
    preserved = {}
    for index, path in enumerate(paths):
        assert not path.is_symlink()
        data = path.read_bytes()
        target = OUT / (PREFIX + '-' + str(index).zfill(3) + '-' + path.name + '.txt')
        with target.open('xb') as stream:
            stream.write(data)
        assert target.read_bytes() == data
        preserved[path.relative_to(ROOT).as_posix()] = {
            'sha256': sha(data), 'bytes': len(data),
            'originalBytes': {'path': target.relative_to(ROOT).as_posix(), 'sha256': sha(data)}
        }
    result = {'schemaVersion': 1, 'stage': 31, 'at': datetime.now(timezone.utc).isoformat(),
              'purpose': 'preserve exact Cloud source and complete dist before schema singleflight repair',
              'pass': True, 'servicesStarted': False, 'productChanged': False,
              'previousExecutionSnapshot': {'path': prior_path.relative_to(ROOT).as_posix(),
                                            'sha256': sha(prior_path.read_bytes())},
              'sourceAndBuildHashes': prior['sourceAndBuildHashes'], 'preserved': preserved}
    with MANIFEST.open('xb') as stream:
        stream.write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': True, 'files': len(preserved), 'manifest': str(MANIFEST),
                      'sha256': sha(MANIFEST.read_bytes())}, ensure_ascii=False))


if __name__ == '__main__':
    main()
