"""Explicit fresh, loopback-only task runtime bootstrap. Never opens a default DB."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / '06_验证与后续工作'
CLOUD = ROOT / '04_研发源码/app/cloud'
SAFE = 9_007_199_254_740_991
FORBIDDEN_PORTS = {8879, 8880, 8881}
MARKER_DDL = """
CREATE TABLE IF NOT EXISTS ops_runtime_identity(
 id INTEGER PRIMARY KEY CHECK(id=1),runtime_id TEXT NOT NULL UNIQUE,
 mode TEXT NOT NULL CHECK(mode='local-isolated'),created INTEGER NOT NULL,
 manifest_hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS ops_bootstrap_identity_insert BEFORE INSERT ON ops_runtime_identity
 WHEN EXISTS(SELECT 1 FROM ops_runtime_identity) BEGIN SELECT RAISE(ABORT,'ops_runtime_immutable'); END;
CREATE TRIGGER IF NOT EXISTS ops_bootstrap_identity_update BEFORE UPDATE ON ops_runtime_identity
 BEGIN SELECT RAISE(ABORT,'ops_runtime_immutable'); END;
CREATE TRIGGER IF NOT EXISTS ops_bootstrap_identity_delete BEFORE DELETE ON ops_runtime_identity
 BEGIN SELECT RAISE(ABORT,'ops_runtime_immutable'); END;
"""


class ProtocolError(Exception):
    """Only fixed, non-sensitive codes are ever sent to the CLI log."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Unknown CLI input might accidentally contain a credential. Never echo it.
        self.exit(2, json.dumps({'ok': False, 'errorCode': 'invalid_cli_arguments',
                                'productionEnabled': False}) + '\n')


def fail(code: str):
    raise ProtocolError(code)


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes, limit=65536):
    if len(data) > limit:
        fail('json_too_large')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail('json_duplicate_key')
            result[key] = value
        return result

    def constant(_):
        fail('json_nonfinite')

    try:
        return json.loads(data.decode('utf-8', errors='strict'), object_pairs_hook=pairs,
                          parse_constant=constant)
    except (UnicodeError, ValueError, TypeError):
        fail('invalid_json')


def valid_base(value: str) -> str:
    match = re.fullmatch(r'http://(?:127\.0\.0\.1|\[::1\]):([1-9][0-9]{0,4})', value)
    if not match or int(match[1]) > 65535 or int(match[1]) in FORBIDDEN_PORTS:
        fail('explicit_safe_loopback_port_required')
    return value


def workspace_path(value: str | Path, *, exists=False) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        fail('absolute_workspace_path_required')
    resolved = candidate.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        fail('path_outside_workspace')
    if any(part.lower() in {'.git', 'node_modules', 'rq01'} for part in resolved.relative_to(ROOT).parts):
        fail('protected_path')
    default_state = CLOUD / '.wrangler/state'
    if resolved == default_state or resolved.is_relative_to(default_state):
        fail('default_state_forbidden')
    forbidden = {ROOT / '04_研发源码/app/r4/backend/eastern-wisdom.sqlite3',
                 OUT / '负责人优化建议-隔离预览.sqlite3'}
    if resolved in forbidden:
        fail('original_database_forbidden')
    if exists and not resolved.exists():
        fail('explicit_path_missing')
    return resolved


def app_path(value: str, backend: str) -> Path:
    candidate = workspace_path(value, exists=True)
    expected = (ROOT / '03_当前APP/东方智慧-首页体验R4.html' if backend == 'python'
                else CLOUD / 'generated/experience.html').resolve()
    if candidate != expected or not candidate.is_file() or candidate.stat().st_size < 1000:
        fail('actual_app_artifact_required')
    return candidate


def load_manifest(value: str | Path):
    path = workspace_path(value, exists=True)
    if not path.is_file() or path.suffix.lower() != '.json':
        fail('manifest_file_required')
    document = strict_json(path.read_bytes())
    if not isinstance(document, dict) or set(document) != {'schemaVersion', 'core', 'manifestSha256', 'productionEnabled'}:
        fail('manifest_shape')
    if type(document['schemaVersion']) is not int or document['schemaVersion'] != 1 or document['productionEnabled'] is not False:
        fail('manifest_version_or_production')
    core = document['core']
    if not isinstance(core, dict) or set(core) != {'created', 'runtimeId', 'mode', 'backend', 'appSha256', 'base', 'statePath'}:
        fail('manifest_core_shape')
    if core['mode'] != 'local-isolated' or core['backend'] not in ('python', 'cloud'):
        fail('manifest_mode')
    if type(core['created']) is not int or not 0 < core['created'] <= SAFE:
        fail('manifest_created')
    if not isinstance(core['runtimeId'], str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', core['runtimeId']):
        fail('manifest_runtime_id')
    if not isinstance(core['appSha256'], str) or not re.fullmatch('[0-9a-f]{64}', core['appSha256']):
        fail('manifest_app_hash')
    if not isinstance(core['base'], str):
        fail('manifest_base')
    valid_base(core['base'])
    if not isinstance(core['statePath'], str) or str(workspace_path(core['statePath'], exists=True)) != core['statePath']:
        fail('manifest_state')
    if document['manifestSha256'] != digest(canonical(core)):
        fail('manifest_hash')
    return path, document


def config_path(value: str | None) -> Path:
    if not value:
        fail('explicit_cloud_config_required')
    path = workspace_path(value, exists=True)
    if not path.is_file():
        fail('cloud_config_missing')
    document = strict_json(path.read_bytes(), 262144)
    if not isinstance(document, dict):
        fail('cloud_config_shape')

    def remote(value):
        if isinstance(value, dict):
            return value.get('remote') is True or any(remote(v) for v in value.values())
        return isinstance(value, list) and any(remote(v) for v in value)

    dbs = document.get('d1_databases')
    if remote(document) or not isinstance(dbs, list) or len(dbs) != 1 or not isinstance(dbs[0], dict) or dbs[0].get('binding') != 'DB':
        fail('single_local_DB_binding_required')
    return path


def cloud_database(state: Path) -> Path:
    if not state.is_dir():
        fail('cloud_state_directory_missing')
    candidates = [p.resolve() for p in state.rglob('*.sqlite')
                  if 'd1' in p.relative_to(state).parts and p.is_file()
                  and re.fullmatch(r'[0-9a-f]{64}\.sqlite', p.name)]
    if len(candidates) != 1 or not candidates[0].is_relative_to(state):
        fail('single_owned_d1_file_required')
    return candidates[0]


def verify_marker(state: Path, document):
    core = document['core']
    database = cloud_database(state) if core['backend'] == 'cloud' else state
    if not database.is_file():
        fail('state_file_missing')
    try:
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=10) as db:
            db.execute('PRAGMA query_only=ON')
            rows = db.execute('SELECT id,runtime_id,mode,created,manifest_hash FROM ops_runtime_identity').fetchall()
            guards = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name IN ('ops_bootstrap_identity_insert','ops_bootstrap_identity_update','ops_bootstrap_identity_delete')")}
    except sqlite3.Error:
        fail('marker_read_failed')
    if rows != [(1, core['runtimeId'], 'local-isolated', core['created'], document['manifestSha256'])] or len(guards) != 3:
        fail('immutable_marker_mismatch')


def seed_cloud(state: Path, cfg: Path, document):
    node = (Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin'
            / ('node.exe' if os.name == 'nt' else 'node'))
    wrangler = CLOUD / 'node_modules/wrangler/bin/wrangler.js'
    if not node.is_file() or not wrangler.is_file():
        fail('bundled_local_toolchain_missing')
    core = document['core']
    # Every inserted string is generated UUID/literal/SHA, not command or SQL input.
    sql = MARKER_DDL + "\nINSERT INTO ops_runtime_identity VALUES(1,'" + core['runtimeId'] + "','local-isolated'," + str(core['created']) + ",'" + document['manifestSha256'] + "');\n"
    with tempfile.NamedTemporaryFile(mode='wb', prefix='任务告警-bootstrap-', suffix='.sql', dir=OUT, delete=False) as handle:
        handle.write(sql.encode('utf-8'))
        sql_path = Path(handle.name)
    arguments = [str(node), '--import', (CLOUD / 'scripts/sites-env.mjs').as_uri(), str(wrangler),
                 'd1', 'execute', 'DB', '--local', '--persist-to', str(state), '--config', str(cfg),
                 '--file', str(sql_path), '--yes', '--json']
    try:
        result = subprocess.run(arguments, cwd=CLOUD, capture_output=True, timeout=90,
            env={**os.environ, 'WRANGLER_SEND_METRICS': 'false', 'CI': '1', 'NO_COLOR': '1'},
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.TimeoutExpired):
        fail('local_d1_bootstrap_unknown_state_preserved')
    if result.returncode != 0:
        # Never echo tool output: environment/credentials may be present there.
        fail('local_d1_bootstrap_failed_state_preserved')
    verify_marker(state, document)
    sql_path.unlink()


def main():
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['python', 'cloud'], required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--app', required=True)
    parser.add_argument('--config')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    try:
        base = valid_base(args.base)
        state = workspace_path(args.state)
        manifest = workspace_path(args.manifest)
        app = app_path(args.app, args.backend)
        if manifest.parent != OUT or manifest.suffix.lower() != '.json' or not state.parent.is_dir():
            fail('existing_validation_parent_required')
        cfg = config_path(args.config) if args.backend == 'cloud' else None
        if args.backend == 'python' and args.config:
            fail('config_only_for_cloud')
        if args.verify_existing:
            _, document = load_manifest(manifest)
            core = document['core']
            if (core['backend'], core['base'], core['statePath'], core['appSha256']) != (args.backend, base, str(state), digest(app.read_bytes())):
                fail('restart_manifest_mismatch')
            verify_marker(state, document)
        else:
            if state.exists() or manifest.exists() or state == manifest or state == app:
                fail('fresh_state_and_manifest_required')
            core = {'created': time.time_ns() // 1_000_000, 'runtimeId': str(uuid.uuid4()),
                    'mode': 'local-isolated', 'backend': args.backend, 'appSha256': digest(app.read_bytes()),
                    'base': base, 'statePath': str(state)}
            document = {'schemaVersion': 1, 'core': core, 'manifestSha256': digest(canonical(core)), 'productionEnabled': False}
            with manifest.open('xb') as handle:
                handle.write((json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
            if args.backend == 'python':
                descriptor = os.open(state, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(descriptor)
                with sqlite3.connect(state) as db:
                    db.executescript(MARKER_DDL)
                    db.execute('INSERT INTO ops_runtime_identity VALUES(1,?,?,?,?)',
                               (core['runtimeId'], core['mode'], core['created'], document['manifestSha256']))
                verify_marker(state, document)
            else:
                seed_cloud(state, cfg, document)
        print(json.dumps({'ok': True, 'backend': core['backend'], 'runtimeId': core['runtimeId'],
            'manifest': str(manifest), 'manifestSha256': document['manifestSha256'],
            'appSha256': core['appSha256'], 'base': base, 'verifiedExisting': args.verify_existing,
            'productionEnabled': False}, ensure_ascii=False))
    except ProtocolError as error:
        print(json.dumps({'ok': False, 'errorCode': str(error), 'productionEnabled': False}))
        return 2
    except (OSError, ValueError, TypeError, sqlite3.Error):
        print(json.dumps({'ok': False, 'errorCode': 'bootstrap_failed_owned_resources_preserved', 'productionEnabled': False}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
