"""Audit and package the current workspace without modifying business sources.

Default/dry-run writes a candidate manifest only. --package writes a root-level
ZIP with no wrapper, makes the one authorized SQLite backup, and verifies every
entry's CRC and SHA-256. The public list always excludes that private snapshot.
"""
from __future__ import annotations

import argparse
import collections
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import struct
import subprocess
import tempfile
import time
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / '06_验证与后续工作'
DB_REL = '06_验证与后续工作/负责人优化建议-隔离预览.sqlite3'
RECEIPT_REL = '06_验证与后续工作/成长统计-本地验收记录.json'
PRIVATE_REL = '06_验证与后续工作/负责人优化建议-当前产品可靠性-实施记录.json'
MANIFEST_NAME = '包内文件清单.json'
TZ = timezone(timedelta(hours=8))
SKIP_DIRS = {
    '.git', 'node_modules', '.wrangler', '.agents', '.codex', '__pycache__',
    '.pytest_cache', '.venv', 'venv', '.next', '.vinext', '.cache',
    '.sites-runtime', '.netlify', 'coverage', 'uploads', 'sessions', 'secrets',
}
ARCHIVES = ('.zip', '.7z', '.rar', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz', '.partial')
MEDIA = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.mp4', '.webm', '.mov', '.avi', '.mp3', '.m4a', '.wav', '.ogg'}
SKIP_SUFFIXES = {'.pyc', '.pyo', '.log', '.tsbuildinfo', '.pem', '.key', '.pfx', '.p12', '.msi', '.exe', '.dmg', '.pkg'}
SKIP_LEAVES = {'.ds_store', 'thumbs.db', 'desktop.ini', '.netrc', '.pypirc', 'credentials.json', 'id_rsa', 'id_ed25519'}
TEXT_SUFFIXES = {'.txt', '.md', '.json', '.jsonl', '.ndjson', '.csv', '.tsv', '.py', '.cjs', '.mjs', '.js', '.ts', '.tsx', '.css', '.html', '.yaml', '.yml', '.toml', '.sql', '.xml', '.cmd', '.ps1'}
HIGH_CONFIDENCE = [
    ('private-key', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')),
    ('github-token', re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b')),
    ('openai-key', re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{35,}\b')),
    ('aws-access-id', re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')),
    ('session-cookie', re.compile(rb'\bew_session=[A-Za-z0-9_.-]{32,}')),
    ('bearer-token', re.compile(rb'\bBearer\s+[A-Za-z0-9_.-]{48,}')),
]


def digest(path: Path) -> str:
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def encode(document) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def safe_path(name: str) -> Path:
    name = name.replace('\\', '/')
    pure = PurePosixPath(name)
    if pure.is_absolute() or '..' in pure.parts or ':' in name:
        raise ValueError('Unsafe project path')
    path = ROOT.joinpath(*pure.parts)
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError('Path escapes project root')
    return path


def unsafe(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400) or not path.resolve().is_relative_to(ROOT)


def png_metadata(data: bytes) -> bytes:
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return data
    result, pos = [], 8
    while pos + 12 <= len(data):
        size = struct.unpack('>I', data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        part = data[pos + 8:pos + 8 + size]
        pos += size + 12
        if kind in (b'tEXt', b'eXIf'):
            result.append(part)
        elif kind == b'zTXt':
            key, tail = part.split(b'\0', 1)
            result.extend((key, zlib.decompress(tail[1:])))
        elif kind == b'iTXt':
            key, tail = part.split(b'\0', 1)
            language, translated, text = tail[2:].split(b'\0', 2)
            result.extend((key, language, translated, zlib.decompress(text) if tail[0] else text))
    return b'\n'.join(result)


def collect_sensitive_values(paths: list[Path]) -> set[bytes]:
    values = set()
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str) and re.search(r'password|secret|token|private.?key|api.?key', key, re.I) and len(item) >= 8:
                    values.add(item.encode('utf-8'))
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for path in paths:
        text = path.read_text('utf-8-sig', errors='replace')
        try:
            visit(json.loads(text))
        except (ValueError, TypeError):
            pass
        for line in text.splitlines():
            match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
            if match and re.search(r'password|secret|token|private.?key|api.?key', match[1], re.I):
                value = match[2].strip().strip('\"\'')
                if len(value) >= 8:
                    values.add(value.encode('utf-8'))
    return values


def aliases_from(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    document = json.loads(path.read_bytes())
    if isinstance(document, dict) and isinstance(document.get('records'), list):
        document = {row['originalPath']: row['currentPath'] for row in document['records']}
    if isinstance(document, dict) and 'renames' in document:
        document = document['renames']
    if isinstance(document, list):
        document = {row['old']: row['new'] for row in document}
    if not isinstance(document, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in document.items()):
        raise ValueError('Aliases must be an old-path to new-path mapping')
    for old, new in document.items():
        safe_path(old)
        safe_path(new)
    return {k.replace('\\', '/'): v.replace('\\', '/') for k, v in document.items()}


def private_artifacts(aliases: dict[str, str]) -> set[str]:
    path = safe_path(aliases.get(PRIVATE_REL, PRIVATE_REL))
    document = json.loads(path.read_bytes())
    items = document.get('localOnlyArtifacts')
    if not isinstance(items, list) or len(items) != 19:
        raise AssertionError('Expected the frozen 19-artifact private runtime inventory')
    return {aliases.get(x['path'].replace('\\', '/'), x['path'].replace('\\', '/')) for x in items}


def reason_for(path: Path, private: set[str]) -> str | None:
    name, low = rel(path), path.name.lower()
    in06 = name.startswith('06_验证与后续工作/')
    if unsafe(path):
        return 'external link or reparse point'
    if name in private or any(name.startswith(x.rstrip('/') + '/') for x in private):
        return 'explicit private runtime artifact; original retained locally'
    if any(part.lower() in SKIP_DIRS for part in path.relative_to(ROOT).parts):
        return 'Git, dependencies, runtime state, cache, upload or session directory'
    if low.startswith(('.env', '.dev.vars')):
        return 'environment values; not part of delivery'
    if low.endswith(ARCHIVES) or low.endswith('.sha256.txt'):
        return 'archive or outer archive digest; no recursive packages'
    if re.search(r'\.(?:sqlite\d*|db\d*)(?:$|[.\-])', low) or low.endswith(('-wal', '-shm', '-journal')):
        return 'database or sidecar; authorized consistent preview snapshot inserted once'
    if low in SKIP_LEAVES or path.suffix.lower() in SKIP_SUFFIXES:
        return 'credential, installer, log, cache or system file'
    if in06 and path.suffix.lower() in MEDIA:
        return 'historical verification media; original reports and rerun scripts retained'
    if in06 and low.endswith('.原字节'):
        return 'historical byte backup; original retained locally, reports retain original hashes'
    if in06 and path.suffix.lower() in {'.txt', '.html'} and path.stat().st_size > 5 * 1024**2 and re.search(r'前|保全|backup|snapshot', path.name, re.I):
        return 'historical generated APP/source backup; original retained locally'
    if in06 and (low.endswith('.runtime-app.html') or (path.suffix.lower() == '.mjs' and path.stat().st_size > 5 * 1024 * 1024)):
        return 'generated runtime fixture or native bundle; source test scripts retained'
    if in06 and (low.endswith('-snapshot.sql') or low.endswith('-r2-private-manifest.json') or '-r2-' in low and low.endswith('.bin')):
        return 'private recovery database dump or object snapshot'
    if name == '06_验证与后续工作/负责人优化建议-到期清理实际专项-cloud.json':
        return 'historical report contains test session; existing redacted handoff copy retained'
    if name == '06_验证与后续工作/负责人优化建议-数字权益专项-python.json':
        return 'historical report contains test session; redacted handoff copy retained'
    if in06 and low.startswith('任务告警-bootstrap-') and low.endswith('.sql'):
        return 'generated runtime administrator bootstrap fixture'
    if in06 and path.suffix.lower() == '.txt' and path.stat().st_size > 10 * 1024 * 1024:
        return 'large historical source byte backup; original retained locally'
    if low == '负责人优化建议-到期清理实际专项-cloud.json':
        return 'historical session-bearing original; redacted handoff copy retained'
    if low == MANIFEST_NAME or low.endswith('-包内文件清单.json') or low.startswith(('项目交付-预检-', '项目交付-校验-')):
        return 'previous package inventory or outer packaging result; current inventory regenerated'
    return None


def current_integrity(aliases: dict[str, str], entry_baseline: Path | None = None) -> dict:
    receipt_path = safe_path(aliases.get(RECEIPT_REL, RECEIPT_REL))
    document = json.loads(receipt_path.read_bytes())
    entries = document['actualSourceAndBuildHashes']
    if document.get('pass') is not True or len(entries) != 354:
        raise AssertionError('Latest accepted 354-input build inventory missing')
    verified, entry_change = {}, None
    for original, expected in entries.items():
        current = aliases.get(original, original)
        path = safe_path(current)
        if unsafe(path) or not path.is_file():
            raise AssertionError('Accepted source/build mismatch: ' + current)
        actual = digest(path)
        if actual != expected:
            if original != '打开这里.html' or entry_baseline is None:
                raise AssertionError('Accepted source/build mismatch: ' + current)
            baseline = entry_baseline.resolve()
            if not baseline.is_relative_to(AREA) or not baseline.is_file() or unsafe(baseline) or digest(baseline) != expected:
                raise AssertionError('Intentional root entry update requires its exact accepted baseline copy')
            entry_change = {'path': current, 'oldSHA256': expected, 'newSHA256': actual,
                            'baselineCopy': rel(baseline), 'baselineCopySHA256': digest(baseline),
                            'scope': 'Root entry filename references intentionally updated in packaging; business source/build unchanged'}
        verified[current] = actual
    return {'receipt': rel(receipt_path), 'receiptSHA256': digest(receipt_path), 'verifiedFiles': len(verified) - bool(entry_change),
            'acceptedInputs': len(verified), 'intentionalEntryChange': entry_change, 'hashes': verified}


def audit(aliases: dict[str, str], entry_baseline: Path | None = None) -> dict:
    integrity = current_integrity(aliases, entry_baseline)
    private = private_artifacts(aliases)
    included, excluded, environments = [], [], []
    for folder, dirs, names in os.walk(ROOT, followlinks=False):
        base = Path(folder)
        kept = []
        for child in sorted(dirs):
            path = base / child
            if child.lower() in SKIP_DIRS or unsafe(path):
                excluded.append({'path': rel(path) + '/', 'reason': 'Git, dependency, runtime/cache, session directory or external link'})
            else:
                kept.append(child)
        dirs[:] = kept
        for child in sorted(names):
            path = base / child
            if not path.is_file() and not path.is_symlink():
                continue
            reason = reason_for(path, private)
            if reason:
                excluded.append({'path': rel(path), 'reason': reason, 'bytes': path.stat().st_size})
                if child.lower().startswith(('.env', '.dev.vars')):
                    environments.append(path)
                continue
            included.append({'path': rel(path), 'bytes': path.stat().st_size, 'sha256': digest(path)})
    by_path = {row['path']: row for row in included}
    if len(by_path) != len(included):
        raise AssertionError('Duplicate candidate path')
    for path, expected in integrity['hashes'].items():
        if path not in by_path or by_path[path]['sha256'] != expected:
            raise AssertionError('Accepted source/build omitted by delivery policy: ' + path)
    values = collect_sensitive_values(environments)
    issues = [{'path': row['path'], 'kind': 'file exceeds GitHub 100 MiB limit', 'valuePrinted': False}
              for row in included if row['bytes'] > 100 * 1024**2]
    last = time.monotonic()
    for index, row in enumerate(included, 1):
        path = safe_path(row['path'])
        if path.suffix.lower() not in TEXT_SUFFIXES | {'.png'}:
            continue
        data = png_metadata(path.read_bytes())
        for label, pattern in HIGH_CONFIDENCE:
            if pattern.search(data):
                issues.append({'path': row['path'], 'kind': label, 'valuePrinted': False})
        for value in values:
            found = value in data if len(value) >= 12 else bool(re.search(rb'(?<![A-Za-z0-9_])' + re.escape(value) + rb'(?![A-Za-z0-9_])', data))
            if found:
                issues.append({'path': row['path'], 'kind': 'literal environment credential value', 'valuePrinted': False})
                break
        if time.monotonic() - last > 20:
            print(json.dumps({'phase': 'audit', 'scanned': index, 'total': len(included)}), flush=True)
            last = time.monotonic()
    return {
        'schemaVersion': 1, 'createdAtBeijing': datetime.now(TZ).isoformat(),
        'mode': 'delivery-preflight', 'pass': not issues, 'flatProjectRoot': True,
        'businessTestsRun': False, 'businessFilesModified': False,
        'files': included, 'excluded': excluded, 'credentialScan': {
            'environmentFilesRead': len(environments), 'knownValuesChecked': len(values),
            'highConfidenceFormatsChecked': len(HIGH_CONFIDENCE), 'issues': issues,
            'privateValuesPrinted': False, 'independentReportReviewRequired': True,
        }, 'integrity': integrity,
        'authorizedPreviewSnapshot': {'archivePath': aliases.get(DB_REL, DB_REL), 'deferredUntilPackaging': True, 'publicGitIncluded': False},
        'publicGitCandidates': [row['path'] for row in included],
        'gitFiles': list(included),
        'sourceBytes': sum(row['bytes'] for row in included),
        'candidateCount': len(included),
        'excludedByReason': dict(collections.Counter(row['reason'] for row in excluded)),
    }


def package(document: dict, aliases: dict[str, str], preflight_path: Path) -> dict:
    if document['pass'] is not True:
        raise AssertionError('Preflight has credential scan issues')
    now = datetime.now(TZ)
    stamp = now.strftime('%Y-%m-%d-%H时%M分%S秒')
    destination = ROOT / ('东方智慧APP项目交付-' + stamp + '.zip')
    temporary = destination.with_suffix('.partial')
    if destination.exists() or temporary.exists():
        raise FileExistsError('Destination already exists')
    git_dir = ROOT / '.git'
    if not git_dir.is_dir() or unsafe(git_dir):
        raise AssertionError('Owned .git temporary directory required for private snapshot')
    snapshot_rel = aliases.get(DB_REL, DB_REL)
    source = safe_path(snapshot_rel)
    if not source.is_file() or unsafe(source):
        raise AssertionError('Authorized preview database missing')
    manifest = {key: value for key, value in document.items() if key not in ('publicGitCandidates', 'gitFiles', 'authorizedPreviewSnapshot')}
    manifest.update({'mode': 'exact-delivery-payload', 'createdAtBeijing': now.isoformat(), 'archive': destination.name, 'manifestSelfHashExcluded': True})
    manifest['gitCommit'] = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    manifest['files'] = list(document['files'])
    with tempfile.TemporaryDirectory(prefix='delivery-snapshot-', dir=git_dir) as work:
        snapshot = Path(work) / 'preview.sqlite3'
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
            with sqlite3.connect(snapshot) as copied:
                original.backup(copied, pages=256, sleep=0.02)
                result = copied.execute('PRAGMA integrity_check').fetchone()[0]
                if result != 'ok':
                    raise AssertionError('SQLite backup integrity check failed')
        snapshot_row = {'path': snapshot_rel, 'bytes': snapshot.stat().st_size, 'sha256': digest(snapshot), 'consistentSQLiteBackup': True, 'privateLocalDeliveryOnly': True}
        manifest['files'].append(snapshot_row)
        manifest['databaseSnapshot'] = snapshot_row
        print(json.dumps({'phase': 'packing', 'files': len(manifest['files']) + 1, 'sourceMiB': round((document['sourceBytes'] + snapshot_row['bytes']) / 1024**2, 2)}), flush=True)
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            last = time.monotonic()
            for index, row in enumerate(manifest['files'], 1):
                path = snapshot if row is snapshot_row else safe_path(row['path'])
                if digest(path) != row['sha256'] or path.stat().st_size != row['bytes']:
                    raise AssertionError('Workspace changed after audit: ' + row['path'])
                archive.write(path, row['path'])
                if time.monotonic() - last > 20:
                    print(json.dumps({'phase': 'packing', 'done': index, 'total': len(manifest['files'])}), flush=True)
                    last = time.monotonic()
            archive.writestr(MANIFEST_NAME, encode(manifest))
        expected = {row['path']: row for row in manifest['files']}
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise AssertionError('ZIP CRC verification failed')
            actual = archive.namelist()
            if len(actual) != len(set(actual)) or set(actual) != set(expected) | {MANIFEST_NAME}:
                raise AssertionError('ZIP entries differ from exact manifest')
            last = time.monotonic()
            for index, (name, row) in enumerate(expected.items(), 1):
                pure = PurePosixPath(name)
                if pure.is_absolute() or '..' in pure.parts or any(x.lower() in SKIP_DIRS for x in pure.parts):
                    raise AssertionError('Unsafe ZIP entry')
                hasher, count = hashlib.sha256(), 0
                with archive.open(name) as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                        hasher.update(chunk)
                        count += len(chunk)
                if hasher.hexdigest() != row['sha256'] or count != row['bytes']:
                    raise AssertionError('ZIP entry byte mismatch: ' + name)
                if name != snapshot_rel and digest(safe_path(name)) != row['sha256']:
                    raise AssertionError('Workspace changed while packaging: ' + name)
                if time.monotonic() - last > 20:
                    print(json.dumps({'phase': 'verifying', 'done': index, 'total': len(expected)}), flush=True)
                    last = time.monotonic()
            if json.loads(archive.read(MANIFEST_NAME)) != manifest:
                raise AssertionError('Embedded inventory differs')
        temporary.rename(destination)
    receipt = {
        'pass': True, 'createdAtBeijing': datetime.now(TZ).isoformat(),
        'archive': str(destination), 'bytes': destination.stat().st_size,
        'MiB': round(destination.stat().st_size / 1024**2, 2), 'sha256': digest(destination),
        'files': len(manifest['files']) + 1, 'allEntryCRCChecked': True,
        'allFilesSHA256Checked': True, 'flatProjectRoot': True,
        'gitHistoryIncluded': False, 'nodeModulesIncluded': False,
        'historicalVerificationMediaIncluded': False,
        'historicalByteBackupsIncluded': False, 'privateRuntimeArtifactsIncluded': False,
        'authorizedPreviewSnapshot': snapshot_row,
        'gitCommit': manifest['gitCommit'],
        'acceptedSourceBuildVerified': document['integrity']['verifiedFiles'],
        'intentionalEntryChange': document['integrity']['intentionalEntryChange'],
        'preflight': {'path': rel(preflight_path), 'sha256': digest(preflight_path)},
        'businessTestsRun': False, 'originalHistoricalFilesDeleted': False,
    }
    receipt_path = AREA / ('项目交付-校验-' + stamp + '.json')
    receipt_path.write_bytes(encode(receipt))
    destination.with_suffix('.sha256.txt').write_bytes((receipt['sha256'] + '  ' + destination.name + '\n').encode('utf-8'))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Audit only (the default)')
    parser.add_argument('--package', action='store_true', help='Create and verify the final ZIP after a fresh audit')
    parser.add_argument('--aliases', type=Path, help='Neutral file-name mapping for unchanged historical source/build paths')
    parser.add_argument('--entry-baseline', type=Path, help='Exact accepted pre-rename 打开这里.html bytes stored directly under 06')
    parser.add_argument('--output', type=Path, help='New preflight JSON file directly under 06')
    args = parser.parse_args()
    if args.dry_run and args.package:
        parser.error('Choose dry-run or package')
    aliases = aliases_from(args.aliases)
    path = args.output or AREA / ('项目交付-预检-' + datetime.now(TZ).strftime('%Y-%m-%d-%H时%M分%S秒') + '.json')
    path = path.resolve()
    if path.parent != AREA or path.exists() or path.suffix.lower() != '.json':
        raise AssertionError('Preflight output must be a new JSON file directly under 06')
    document = audit(aliases, args.entry_baseline)
    path.write_bytes(encode(document))
    summary = {'pass': document['pass'], 'preflight': str(path), 'sha256': digest(path), 'candidateCount': document['candidateCount'], 'sourceMiB': round(document['sourceBytes'] / 1024**2, 2), 'credentialIssueCount': len(document['credentialScan']['issues']), 'verifiedSourceBuild': document['integrity']['verifiedFiles'], 'excludedByReason': document['excludedByReason']}
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if args.package:
        print(json.dumps(package(document, aliases, path), ensure_ascii=False), flush=True)
    elif document['pass'] is not True:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
