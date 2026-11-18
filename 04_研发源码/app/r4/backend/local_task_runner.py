"""One local authenticated task loop; credentials stay in this process memory."""
from __future__ import annotations

import argparse
import hashlib
from http.client import HTTPException
import json
import os
import queue
import re
import signal
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid

from local_task_bootstrap import ProtocolError, SafeArgumentParser, SAFE, fail, load_manifest, strict_json, valid_base, verify_marker

KINDS = {'payment_callbacks', 'payment_recovery', 'privacy_objects', 'payment_monitor', 'alert_notifications', 'idle'}
STATUSES = {'running', 'succeeded', 'skipped', 'failed', 'unknown', 'lease_lost'}
STOP = threading.Event()


class HttpFailure(Exception):
    def __init__(self, status):
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def now():
    return time.time_ns() // 1_000_000


def emit(status, **metadata):
    print(json.dumps({'at': now(), 'status': status, **metadata, 'productionEnabled': False}, ensure_ascii=False), flush=True)


class Runner:
    def __init__(self, document, base, worker, session):
        self.manifest = document
        self.core = document['core']
        self.base, self.worker, self.session = base, worker, session
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.pending = None
        self.last_notice = None
        self.needs_app_probe = True
        self.observed_expired = set()

    def notice(self, status):
        if self.last_notice != status:
            emit(status, workerId=self.worker)
            self.last_notice = status

    def http(self, path, body=None, *, app_digest=False, authenticated=True):
        result = queue.Queue(maxsize=1)

        def transport():
            try:
                result.put((True, self.http_once(path, body, app_digest=app_digest, authenticated=authenticated)))
            except Exception as error:
                result.put((False, error))

        # This transport thread can only return bytes/errors, never write a DB
        # or a completion receipt. A late response after this total deadline is
        # ignored, without claiming that the server operation was cancelled.
        threading.Thread(target=transport, daemon=True).start()
        try:
            ok, value = result.get(timeout=75)
        except queue.Empty:
            raise HttpFailure(0) from None
        if not ok:
            raise value
        return value

    def http_once(self, path, body=None, *, app_digest=False, authenticated=True):
        if not path.startswith('/') or path.startswith('//'):
            fail('fixed_local_route_required')
        headers = {'Accept': 'text/html' if app_digest else 'application/json', 'Cache-Control': 'no-store'}
        if authenticated:
            headers['Cookie'] = 'ew_session=' + self.session
        data = None
        if body is not None:
            data = json.dumps(body, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
            headers['Content-Type'] = 'application/json'
            # Matches the ordinary same-origin administrative boundary.
            headers['Origin'] = self.base
        request = Request(self.base + path, data=data, headers=headers,
                          method='POST' if body is not None else 'GET')
        try:
            with self.opener.open(request, timeout=75) as response:
                if response.status != 200:
                    raise HttpFailure(response.status)
                if app_digest:
                    # The standalone APP embeds its media and is currently over
                    # 40 MiB. Hash the complete artifact without retaining it.
                    actual = hashlib.sha256()
                    total = 0
                    while True:
                        chunk = response.read(65536)
                        if not chunk:
                            return actual.hexdigest()
                        total += len(chunk)
                        if total > 128 * 1024 * 1024:
                            fail('local_app_response_too_large')
                        actual.update(chunk)
                limit = 1024 * 1024
                value = response.read(limit + 1)
                if len(value) > limit:
                    fail('local_response_too_large')
                if response.headers.get_content_type().lower() != 'application/json':
                    fail('local_response_not_json')
                return strict_json(value, limit)
        except HTTPError as error:
            status = error.code
            error.close()
            raise HttpFailure(status) from None
        except (URLError, TimeoutError, OSError, HTTPException):
            raise HttpFailure(0) from None

    def runtime(self):
        data = self.http('/api/admin/local-tasks/runtime')
        if not isinstance(data, dict) or data.get('productionEnabled') is not False:
            fail('runtime_response_shape')
        runtime = data.get('runtime')
        if not isinstance(runtime, dict):
            fail('runtime_response_shape')
        if (runtime.get('runtimeId'), runtime.get('mode'), runtime.get('backend'), runtime.get('appSha256')) != (
                self.core['runtimeId'], 'local-isolated', self.core['backend'], self.core['appSha256']):
            fail('runtime_or_app_identity_changed')
        if runtime.get('productionEnabled') is not False or runtime.get('envEnabled') is not True:
            fail('runtime_environment_not_ready')
        if runtime.get('identityReady') is not True or runtime.get('manifestSha256') != self.manifest['manifestSha256']:
            fail('runtime_manifest_not_ready')
        config = data.get('config')
        if not isinstance(config, dict) or type(config.get('enabled')) is not bool:
            fail('runtime_config_shape')
        return config

    def validate_run(self, run):
        if not isinstance(run, dict) or not self.pending:
            fail('run_response_shape')
        if (run.get('runtimeId'), run.get('workerId'), run.get('requestId')) != (
                self.core['runtimeId'], self.worker, self.pending['requestId']):
            fail('run_identity_mismatch')
        if run.get('kind') not in KINDS or run.get('status') not in STATUSES:
            fail('run_response_shape')
        if not isinstance(run.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}', run['id']):
            fail('run_id_invalid')
        count = run.get('processed')
        if type(count) is not int or not 0 <= count <= SAFE:
            fail('run_count_invalid')
        lease = run.get('leaseUntil')
        if type(lease) is not int or not 0 <= lease <= SAFE:
            fail('run_lease_invalid')
        return run

    def finish(self, run):
        run = self.validate_run(run)
        if run['status'] == 'running' and run['leaseUntil'] > now():
            self.notice('awaiting_original_run')
            return False
        # Expired running is uncertain, not a failure or cancellation. A later
        # real authorized tick may reconcile it under the server's leases.
        status = 'unknown' if run['status'] == 'running' else run['status']
        if run['status'] == 'running':
            self.observed_expired.add(run['requestId'])
        emit(status, workerId=self.worker, runId=run['id'], kind=run['kind'], processed=run['processed'])
        self.pending = None
        self.last_notice = None
        return True

    def find_pending(self):
        query = urlencode({'workerId': self.worker, 'requestId': self.pending['requestId']})
        data = self.http('/api/admin/local-tasks/runs?' + query)
        if not isinstance(data, dict) or not isinstance(data.get('items'), list):
            fail('run_lookup_shape')
        items = data['items']
        if len(items) > 1:
            fail('duplicate_tick_fact')
        return self.validate_run(items[0]) if items else None

    def recover_existing(self):
        query = urlencode({'workerId': self.worker, 'status': 'running'})
        data = self.http('/api/admin/local-tasks/runs?' + query)
        if not isinstance(data, dict) or not isinstance(data.get('items'), list) or data.get('next'):
            fail('worker_inflight_lookup_shape')
        if any(not isinstance(r, dict) for r in data['items']):
            fail('worker_inflight_lookup_shape')
        rows = [r for r in data['items'] if isinstance(r, dict) and r.get('requestId') not in self.observed_expired]
        active = [r for r in rows if type(r.get('leaseUntil')) is int and r['leaseUntil'] > now()]
        if len(active) > 1:
            fail('worker_has_multiple_inflight_runs')
        for row in rows:
            request_id = row.get('requestId')
            if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9:_-]{8,100}', request_id):
                fail('original_request_id_invalid')
            self.pending = {'runtimeId': self.core['runtimeId'], 'workerId': self.worker,
                            'requestId': request_id, 'appSha256': self.core['appSha256']}
            self.validate_run(row)
            if row['leaseUntil'] <= now():
                self.finish(row)
        if active:
            row = active[0]
            self.pending = {'runtimeId': self.core['runtimeId'], 'workerId': self.worker,
                            'requestId': row['requestId'], 'appSha256': self.core['appSha256']}
            self.notice('awaiting_original_run')

    def run(self):
        # Verify the existing physical local marker without creating any state.
        from pathlib import Path
        verify_marker(Path(self.core['statePath']), self.manifest)
        self.runtime()
        if self.http('/experience', app_digest=True, authenticated=False) != self.core['appSha256']:
            fail('actual_app_bytes_mismatch')
        self.needs_app_probe = False
        emit('ready', workerId=self.worker, runtimeId=self.core['runtimeId'], pid=os.getpid())
        self.recover_existing()
        while not STOP.is_set():
            try:
                config = self.runtime()  # Always an actual current-session request.
                if self.needs_app_probe:
                    if self.http('/experience', app_digest=True, authenticated=False) != self.core['appSha256']:
                        fail('actual_app_bytes_mismatch')
                    self.needs_app_probe = False
                if self.pending:
                    previous = self.find_pending()
                    if previous:
                        if not self.finish(previous):
                            STOP.wait(1)
                            continue
                if config['enabled'] is not True:
                    self.notice('disabled')
                    STOP.wait(5)
                    continue
                if not self.pending:
                    self.recover_existing()
                    if self.pending:
                        STOP.wait(1)
                        continue
                    self.pending = {'runtimeId': self.core['runtimeId'], 'workerId': self.worker,
                                    'requestId': 'tick-' + str(uuid.uuid4()), 'appSha256': self.core['appSha256']}
                if STOP.is_set():
                    break
                result = self.http('/api/admin/local-tasks/tick', self.pending)
                if not isinstance(result, dict) or result.get('productionEnabled') is not False:
                    fail('tick_response_shape')
                self.finish(result.get('run'))
                next_due = result.get('nextDue')
                delay = min(5, max(0.5, (next_due - now()) / 1000)) if type(next_due) is int else 1
                STOP.wait(delay)
            except HttpFailure as error:
                if error.status in (401, 403):
                    self.notice('auth_required')
                    return 3
                if error.status in (400, 404, 409) or 300 <= error.status < 400:
                    self.notice('protocol_or_identity_conflict')
                    return 4
                # A timeout, aborted response, storage failure or rate limit is
                # never interpreted as payment/deletion/notification failure.
                self.notice('transport_unknown' if error.status != 429 else 'rate_limited')
                if error.status == 0 or error.status >= 500:
                    self.needs_app_probe = True
                STOP.wait(5)
        self.notice('stopped_with_original_run_pending' if self.pending else 'stopped')
        return 0


def main():
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--worker-id', required=True)
    parser.add_argument('--session-ref', required=True)
    args = parser.parse_args()
    try:
        _, document = load_manifest(args.manifest)
        base = valid_base(args.base)
        if base != document['core']['base']:
            fail('runner_base_mismatch')
        if not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}', args.worker_id):
            fail('explicit_worker_id_required')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,100}', args.session_ref):
            fail('explicit_session_reference_required')
        session = os.environ.get(args.session_ref, '')
        if not re.fullmatch(r'[A-Za-z0-9._~-]{16,512}', session):
            fail('session_environment_invalid')
        for name in ('SIGINT', 'SIGTERM'):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), lambda *_: STOP.set())
        return Runner(document, base, args.worker_id, session).run()
    except ProtocolError as error:
        emit('protocol_error', errorCode=str(error))
        return 2
    except HttpFailure as error:
        emit('auth_required' if error.status in (401, 403) else 'startup_unavailable')
        return 3 if error.status in (401, 403) else 2
    except (OSError, ValueError, TypeError, KeyError):
        emit('startup_invalid')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
