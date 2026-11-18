"""Stage an audited public allowlist and verify byte identities; never add runtime files."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / '06_验证与后续工作'
GIT = ROOT / '.git'

def run(*args, input=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=input, capture_output=True, check=True).stdout

def sha256(path):
    with path.open('rb') as source: return hashlib.file_digest(source, 'sha256').hexdigest()

def blob_sha(path):
    value = hashlib.sha1()
    value.update(('blob ' + str(path.stat().st_size) + '\0').encode())
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''): value.update(chunk)
    return value.hexdigest()

def stage(plan_path):
    plan = json.loads(plan_path.read_bytes())
    assert plan['pass'] is True and not plan['credentialScan']['issues']
    files = plan['gitFiles']
    assert files and {x['path'] for x in files} <= {x['path'] for x in plan['files']}
    assert all(x in plan['files'] for x in files)
    for item in files:
        path = ROOT / item['path']
        assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
        assert path.stat().st_size == item['bytes'] and sha256(path) == item['sha256'], item['path']
        assert path.stat().st_size < 100 * 1024**2
    tracked = set(run('ls-files', '-z').decode('utf-8').rstrip('\0').split('\0'))
    mapping = json.loads((AREA / '文件命名对照.json').read_bytes())
    original_paths = {x['originalPath'] for x in mapping['records']}
    removed = original_paths & tracked
    for old in removed:
        assert not (ROOT / old).exists()
    if removed: run('--literal-pathspecs', 'update-index', '--force-remove', '--', *sorted(removed))
    paths = GIT / 'delivery-public-paths.nul'
    paths.write_bytes(b'\0'.join(x['path'].encode('utf-8') for x in files) + b'\0')
    run('--literal-pathspecs', 'add', '-f', '--pathspec-from-file=' + str(paths), '--pathspec-file-nul')
    index = {}
    for row in run('ls-files', '--stage', '-z').split(b'\0'):
        if not row: continue
        metadata, name = row.split(b'\t', 1)
        mode, digest, level = metadata.decode().split()
        assert level == '0' and mode == '100644'
        index[name.decode('utf-8')] = digest
    for item in files:
        assert index.get(item['path']) == blob_sha(ROOT / item['path']), item['path']
    assert not (removed & set(index))
    assert not any(any(x in Path(p).name for x in ('回家', '在家', '公司同步', '先读我', 'start-home')) for p in index)
    staged = set(run('-c', 'diff.renames=false', 'diff', '--cached', '--no-renames', '--name-only', '-z').decode().rstrip('\0').split('\0')) - {''}
    staged_old_paths = staged - {x['path'] for x in files}
    assert staged_old_paths <= original_paths
    assert all(not (ROOT / p).exists() and p not in index for p in staged_old_paths)
    record = {'atBeijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'pass': True, 'mode': 'audited-public-allowlist', 'candidateCount': len(files),
        'stagedChanges': len(staged), 'renamedOldTrackedPathsRemoved': sorted(staged_old_paths),
        'allCandidateIndexBlobIdentitiesVerified': True, 'previewDatabasePublic': False,
        'sourcePlan': plan_path.relative_to(ROOT).as_posix(), 'sourcePlanSHA256': sha256(plan_path),
        'priorRemoteMediaRetainedInIndex': True}
    (GIT / 'delivery-staging-verification.json').write_bytes((json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps(record, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    stage(args.plan.resolve())
