"""Four real SQLite request-lease groups over a newly owned synthetic Store.

This is not an HTTP/Cloud/authorization acceptance suite. Real role/closure and
erasure races remain required in the separate unchanged 40/28/27 HTTP gates.
Default/import does not load the product, open a database, or start a service.
"""
from pathlib import Path
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
BACKEND = ROOT / '04_研发源码/app/r4/backend'
PREFIX = '负责人优化建议-本地可靠性性能复验'
NODE = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def execute(authorization_sha):
    env = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP') if k in os.environ}
    env['PATH'] = str(NODE.parent)
    script = "const g=require('./06_验证与后续工作/负责人优化建议-本地可靠性修复基线.cjs');g.verifyAuthorization(process.argv[1]);process.stdout.write('VERIFIED');"
    proof = subprocess.run([str(NODE), '-e', script, authorization_sha], cwd=ROOT,
                           env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=60, shell=False,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert proof.returncode == 0 and proof.stdout == b'VERIFIED', 'root repair authorization refused'
    run = uuid.uuid4().hex
    db_path = OUT / (PREFIX + '原生连接隔离-' + run + '.sqlite3')
    report_path = OUT / (PREFIX + '原生连接组件-' + run + '.json')
    fd = os.open(db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    source_before = sha(BACKEND / 'server.py')
    report = {'runId': run, 'componentOnly': True, 'nativeSQLiteOnly': True,
              'actualHttpCovered': False, 'cloudNativeReuseCovered': False,
              'roleClosureRaceCoveredByThisComponent': False,
              'requiredSeparateHttpSuites': ['special40', 'privacy28', 'closure27'],
              'productionEnabled': False, 'syntheticOnly': True, 'results': [],
              'authorizationSha256': authorization_sha,
              'source': {'path': (BACKEND / 'server.py').relative_to(ROOT).as_posix(), 'sha256': source_before},
              'helper': {'path': Path(__file__).relative_to(ROOT).as_posix(), 'sha256': sha(__file__)},
              'localOnlyDatabase': db_path.relative_to(ROOT).as_posix(),
              'databaseIncludedInHandoffByDefault': False}
    sys.path.insert(0, str(BACKEND))
    spec = importlib.util.spec_from_file_location('owned_request_scope_component_server', BACKEND / 'server.py')
    product = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(product)
    store = product.Store(db_path)
    with store.connect() as db:
        db.execute('CREATE TABLE qa_request_scope_probe(id INTEGER PRIMARY KEY,owner TEXT,body TEXT)')

    @contextmanager
    def scope():
        token = store.begin_request_scope()
        try:
            yield
        finally:
            store.end_request_scope(token)

    def closed(fn):
        try:
            fn()
        except sqlite3.ProgrammingError:
            return True
        raise AssertionError('escaped lease/cursor/native unexpectedly remained usable')

    def check(name, fn):
        started = time.perf_counter()
        try:
            observed = fn()
            report['results'].append({'name': name, 'pass': True, 'observed': observed,
                                      'ms': (time.perf_counter() - started) * 1000})
        except Exception as error:
            report['results'].append({'name': name, 'pass': False, 'errorCode': type(error).__name__,
                                      'errorMessage': str(error)[:300], 'sourceLine': traceback.extract_tb(error.__traceback__)[-1].lineno,
                                      'ms': (time.perf_counter() - started) * 1000})

    def transaction_group():
        with scope():
            with store.connect() as first:
                native = first._db
                cursor = first.execute('SELECT 1 UNION ALL SELECT 2')
                method = first.execute
                commit = first.commit
                first.execute("INSERT INTO qa_request_scope_probe VALUES(1,'synthetic-component','committed')")
            assert closed(lambda: cursor.fetchone())
            assert closed(lambda: method('SELECT 1'))
            assert closed(commit)
            with store.connect() as second:
                assert second._db is native
                assert second.execute('SELECT body FROM qa_request_scope_probe WHERE id=1').fetchone()[0] == 'committed'
                second.execute('PRAGMA query_only=ON')
            assert closed(lambda: native.execute('SELECT 1'))
            with store.connect() as third:
                clean = third._db
                assert clean is not native
                assert third.execute('PRAGMA query_only').fetchone()[0] == 0
            try:
                with store.connect() as failing:
                    poisoned = failing._db
                    failing.execute("INSERT INTO qa_request_scope_probe VALUES(2,'synthetic-component','must-rollback')")
                    raise RuntimeError('fixed synthetic rollback')
            except RuntimeError:
                pass
            with store.connect() as after:
                assert after._db is not poisoned
                assert after.execute('SELECT 1 FROM qa_request_scope_probe WHERE id=2').fetchone() is None
                assert after.execute('PRAGMA foreign_keys').fetchone()[0] == 1
                assert after.execute('PRAGMA defer_foreign_keys').fetchone()[0] == 0
                after_native = after._db
        assert closed(lambda: after_native.execute('SELECT 1'))
        return {'sameRequestIdleReuseObserved': True, 'commitPreserved': True, 'exceptionRolledBack': True,
                'dirtyQueryOnlyConnectionDiscarded': True, 'escapedCursorAndMethodsRejected': True,
                'requestFinallyClosedNative': True, 'businessActorFabricated': False}

    def nested_group():
        with scope():
            with store.connect() as outer:
                outer_native = outer._db
                outer.execute('BEGIN')
                before = outer.execute('SELECT count(*) FROM qa_request_scope_probe').fetchone()[0]
                with store.connect() as inner:
                    inner_native = inner._db
                    assert inner_native is not outer_native and not inner.in_transaction
                    inner.execute("INSERT INTO qa_request_scope_probe VALUES(3,'synthetic-component','nested-commit')")
                assert outer.execute('SELECT count(*) FROM qa_request_scope_probe').fetchone()[0] == before
            with store.connect() as current:
                assert current.execute('SELECT body FROM qa_request_scope_probe WHERE id=3').fetchone()[0] == 'nested-commit'
        return {'activeNativeNeverReborrowed': True, 'nestedCommitIndependent': True,
                'outerReadSnapshotPreserved': True, 'nestedWaitOrMergedTransactionUsed': False}

    def isolation_group():
        barrier = threading.Barrier(2, timeout=8)
        natives = []
        lock = threading.Lock()

        def worker():
            with scope():
                with store.connect() as db:
                    native = db._db
                    with lock:
                        natives.append(native)
                    barrier.wait()
                    assert db.execute('SELECT count(*) FROM qa_request_scope_probe').fetchone()[0] >= 2
                with store.connect() as again:
                    assert again._db is native
            assert closed(lambda: native.execute('SELECT 1'))
            return {'threadId': threading.get_ident(), 'nativeId': id(native), 'closedInOwningThread': True}

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker) for _ in range(2)]
            observed = [future.result(timeout=15) for future in futures]
        assert natives[0] is not natives[1]
        with scope():
            with store.connect() as later:
                assert all(later._db is not old for old in natives)
        with store.connect() as non_http:
            raw = non_http._db
        assert closed(lambda: raw.execute('SELECT 1'))
        return {'actualThreads': observed, 'differentRequestsDidNotShareNative': True,
                'newRequestDoesNotReusePreviousNative': True, 'nonHttpOriginalClosePreserved': True}

    def schema_group():
        with scope():
            with store.connect() as db:
                native = db._db
                db.execute('CREATE TABLE qa_request_scope_late(id INTEGER PRIMARY KEY,owner TEXT,body TEXT)')
            with store.connect() as next_lease:
                assert next_lease._db is native
                before = next_lease.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND tbl_name='qa_request_scope_late' AND sql LIKE '%privacy_deleted_media_reference%'").fetchone()[0]
                assert before > 0
                next_lease.execute('ALTER TABLE qa_request_scope_late ADD COLUMN extra TEXT')
            with store.connect() as after:
                count = after.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND tbl_name='qa_request_scope_late' AND sql LIKE '%privacy_deleted_media_reference%'").fetchone()[0]
                assert count > before
                schema_version = after.execute('PRAGMA schema_version').fetchone()[0]
                assert store._privacy_reference_schema_version == schema_version
        return {'sameRequestSchemaRefreshObserved': True, 'unknownTableReferenceGuards': before,
                'afterAddedTextColumnReferenceGuards': count,
                'actualPrivateMediaDeletionClaimed': False,
                'actualReferenceRejectionRequiredSeparatelyInHttpPrivacySuite': True}

    try:
        check('logical-transaction-and-clean-state', transaction_group)
        check('nested-leases-and-current-authorization', nested_group)
        check('cross-request-owner-isolation-and-finally', isolation_group)
        check('dynamic-schema-and-final-erasure-guards', schema_group)
    finally:
        report['sourceUnchangedDuringComponent'] = sha(BACKEND / 'server.py') == source_before
        report['passed'] = sum(row['pass'] for row in report['results'])
        report['failed'] = sum(not row['pass'] for row in report['results'])
        report['pass'] = report['passed'] == 4 and report['failed'] == 0 and report['sourceUnchangedDuringComponent']
        report['processOrServiceStarted'] = False
        report['finishedAtNs'] = time.time_ns()
        with report_path.open('xb') as stream:
            stream.write((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({'pass': report['pass'], 'componentOnly': True, 'nativeSQLiteOnly': True,
                      'path': report_path.relative_to(ROOT).as_posix(), 'sha256': sha(report_path),
                      'passed': report['passed'], 'failed': report['failed']}, ensure_ascii=False))
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute-native-component', action='store_true')
    parser.add_argument('--authorization-sha256')
    args = parser.parse_args()
    if not args.execute_native_component:
        print(json.dumps({'status': 'prepared-not-run', 'actualNativeGroups': 0, 'plannedGroups': 4,
                          'actualHttpCovered': False, 'cloudNativeReuseCovered': False}))
    else:
        try:
            raise SystemExit(execute(args.authorization_sha256))
        except Exception as error:
            print(json.dumps({'pass': False, 'componentOnly': True, 'errorCode': type(error).__name__}))
            raise SystemExit(1)
