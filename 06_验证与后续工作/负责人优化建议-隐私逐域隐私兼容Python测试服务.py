"""Isolated QA service: real server/SQLite, in-process provider mock, no network egress."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
backend = root / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(backend))
spec = importlib.util.spec_from_file_location('privacy_test_actual_server', backend / 'server.py')
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
parser = argparse.ArgumentParser()
parser.add_argument('--db', type=Path, required=True)
parser.add_argument('--token', required=True)
args = parser.parse_args()
assert not args.db.exists(), 'QA database must be new'
assert args.db.resolve().is_relative_to(root / '06_验证与后续工作'), 'QA database must stay inside validation directory'
calls, lock = [], threading.Lock()


class MockResponse:
    def __enter__(self):
        return self

    def __exit__(self, *unused):
        return False

    def read(self, limit=None):
        return json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'PRIVACY_LOCAL_MOCK_RESPONSE'}]}]}).encode()


def mock_urlopen(request, *unused, **options):
    url = request.full_url if hasattr(request, 'full_url') else str(request)
    if urlsplit(url).hostname != 'privacy-fixture.invalid':
        raise actual.URLError('QA blocks all external provider calls')
    with lock:
        calls.append({'url': url, 'payload': json.loads(request.data.decode())})
    return MockResponse()


actual.urlopen = mock_urlopen
actual.open_legacy_ai = mock_urlopen
base_handler = actual.make_handler(actual.Store(args.db), root / '03_当前APP')


class Handler(base_handler):
    def do_GET(self):
        if urlsplit(self.path).path == '/__privacy-test/mock':
            if self.headers.get('X-Privacy-Test') != args.token:
                return self.send(403, {'error': 'test token required'})
            with lock:
                return self.send(200, {'isolated': True, 'kind': 'local-process-mock', 'externalProviderTested': False, 'calls': list(calls)})
        return super().do_GET()


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
print('APP: http://127.0.0.1:' + str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
