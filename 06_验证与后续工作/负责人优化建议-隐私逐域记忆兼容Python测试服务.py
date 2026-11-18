"""Prepared fresh actual memory server; explicit local legacy/gateway fixture only. No prompt logging or live provider."""
import argparse
import importlib.util
import json
import hashlib
import os
from pathlib import Path
import sys
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
backend = root / '04_研发源码/app/r4/backend'
sys.path.insert(0, str(backend))
import ai_gateway as gateway
parser = argparse.ArgumentParser()
parser.add_argument('--db', type=Path, required=True)
parser.add_argument('--token', required=True)
args = parser.parse_args()
assert not args.db.exists() and args.db.resolve().is_relative_to(root / '06_验证与后续工作')
lock, calls, held = threading.RLock(), [], []
state = {'mode': 'success'}
SELECTED='MEM_SELECTED_BODY_CANARY'
UNSELECTED='MEM_UNSELECTED_BODY_CANARY'


def event(kind, data):
    return ('event: ' + kind + '\ndata: ' + json.dumps(data, ensure_ascii=False) + '\n\n').encode()


class Response:
    headers = {'request-id': 'LOCAL_GATEWAY_FIXTURE'}

    def __init__(self, p, mode):
        self.p, self.mode = p, mode
        self.release = threading.Event()
        with lock:
            if mode in ('hold', 'hold-before-first'):
                held.append(self.release)

    def close(self):
        self.release.set()

    def read(self, limit):
        if self.p['protocol'] == 'anthropic_messages':
            return json.dumps({'content': [{'type': 'text', 'text': 'MEMORY_LOCAL_FIXTURE_BETA'}], 'usage': {'input_tokens': 7, 'output_tokens': 3}}).encode()
        return json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'MEMORY_LOCAL_FIXTURE_ALPHA'}]}], 'usage': {'input_tokens': 7, 'output_tokens': 3}}).encode()

    def __iter__(self):
        if self.mode == 'hold-before-first':
            self.release.wait(20)
        protocol = self.p['protocol']
        if protocol == 'anthropic_messages':
            frames = [event('message_start', {'type': 'message_start', 'message': {'usage': {'input_tokens': 7}}}), event('content_block_delta', {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': 'MEMORY_LOCAL_FIXTURE_BETA'}})]
            final = [event('message_delta', {'type': 'message_delta', **({} if self.mode == 'no-usage' else {'usage': {'output_tokens': 3}})}), event('message_stop', {'type': 'message_stop'})]
        else:
            frames = [event('response.output_text.delta', {'type': 'response.output_text.delta', 'delta': 'MEMORY_LOCAL_FIXTURE_ALPHA'})]
            final = [event('response.completed', {'type': 'response.completed', 'response': {} if self.mode == 'no-usage' else {'usage': {'input_tokens': 7, 'output_tokens': 3}}})]
        for frame in frames:
            for line in frame.splitlines(keepends=True):
                yield line
        if self.mode == 'hold':
            self.release.wait(20)
        if self.mode != 'partial':
            for frame in final:
                for line in frame.splitlines(keepends=True):
                    yield line


def transport(p, payload, deadline):
    assert urlsplit(p['endpoint']).hostname.endswith('.invalid'), 'QA reserved endpoints only'
    serialized = json.dumps(payload, ensure_ascii=False)
    with lock:
        mode = state['mode']
        calls.append({'providerId':p['id'],'protocol':p['protocol'],'payloadChars':len(serialized),'selectedBodyPresent':SELECTED in serialized,'unselectedBodyPresent':UNSELECTED in serialized,'localMemoryMetadataPresent':'memoryEpoch' in serialized or 'memorySelection' in serialized,'privacyTagsPresent':'consentEpoch' in serialized,'mode':mode})
    if mode == 'primary-fails' and p['id'] == 'alpha':
        raise gateway.GatewayFailure('upstream_http_503', True)
    return Response(p, mode)


original_init = gateway.AIGateway.__init__


def injected_init(self, *values, **options):
    options['test_transport'] = transport
    options['test_secret_resolver'] = lambda ref: 'SYNTHETIC_LOCAL_NOT_REAL' if ref in ('EW_AI_MEMORY_QA_ALPHA', 'EW_AI_MEMORY_QA_BETA') else ''
    original_init(self, *values, **options)


gateway.AIGateway.__init__ = injected_init
spec = importlib.util.spec_from_file_location('gateway_test_actual_server', backend / 'server.py')
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
assert getattr(actual, 'AIGateway', None) is gateway.AIGateway, 'Actual public gateway dispatcher must be integrated'
actual.urlopen = lambda *values, **options: (_ for _ in ()).throw(actual.URLError('QA blocks all external HTTP'))
class LegacyResponse:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,limit):return json.dumps({'output':[{'type':'message','content':[{'type':'output_text','text':'MEMORY_LOCAL_FIXTURE_LEGACY'}]}]}).encode()
def legacy_transport(request,*values,**options):
    assert request.full_url=='https://memory-legacy.invalid/v1/responses'
    assert request.get_header('Authorization')=='Bearer '+os.environ['EW_AI_MEMORY_QA_LEGACY']
    body=request.data.decode('utf-8')
    with lock:calls.append({'providerId':'legacy-memory','protocol':'responses','kind':'explicit-local-legacy-fixture','payloadChars':len(body),'selectedBodyPresent':SELECTED in body,'unselectedBodyPresent':UNSELECTED in body,'localMemoryMetadataPresent':'memoryEpoch' in body or 'memorySelection' in body,'privacyTagsPresent':'consentEpoch' in body})
    return LegacyResponse()
actual.open_legacy_ai=legacy_transport
store=actual.Store(args.db)
# All source/init integration must be in the actual public server before a wrapper can run.
with store.connect() as db:
    assert db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_entries'").fetchone(),'Integrate/build memory before real acceptance'
    config={'enabled':True,'apiKeyRef':'EW_AI_MEMORY_QA_LEGACY','endpoint':'https://memory-legacy.invalid/v1/responses','model':'memory-legacy-model','providerId':'legacy-memory','processingRegions':['QA-LOCAL'],'privacyPolicyVersion':'memory-fixture-v1','prompt':'Explicit local fixture only','knowledge':''}
    db.execute("UPDATE settings SET data=? WHERE key='ai'",(actual.dump(config),))
base_handler = actual.make_handler(store, root / '03_当前APP')



class Handler(base_handler):
    def monitor(self):
        if self.headers.get('X-Memory-Test') != args.token:
            self.send(403, {'error': 'test token required'})
            return
        if self.command == 'POST':
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            with lock:
                if 'mode' in data:
                    assert data['mode'] in ('success', 'primary-fails', 'partial', 'no-usage', 'hold', 'hold-before-first')
                    state['mode'] = data['mode']
                if data.get('release'):
                    for release in held:
                        release.set()
        with lock:
            with store.connect() as db:
                names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                metadata={name:[tuple(r) for r in db.execute('SELECT * FROM "'+name+'" ORDER BY 1')] for name in ('memory_actions','memory_tombstones','memory_provider_consents','memory_job_bindings','memory_cleanup_receipts','ai_gateway_jobs','ai_gateway_job_events','audits') if name in names}
                raw=actual.dump(metadata)
                financial={name:[tuple(r) for r in db.execute('SELECT * FROM "'+name+'" ORDER BY 1')] for name in sorted(names) if name.startswith(('commerce_','membership_','commission_','after_sales_'))}
                financial_hash=hashlib.sha256(actual.dump(financial).encode()).hexdigest()
                counts={name:db.execute('SELECT count(*) FROM "'+name+'"').fetchone()[0] for name in ('memory_entries','privacy_conversations','records','card_draws') if name in names}
            self.send(200,{'isolated':True,'externalProviderTested':False,'kind':'local-process-mock','calls':list(calls),'mode':state['mode'],'metadataContainsMemoryBody':SELECTED in raw or UNSELECTED in raw,'originalFinancialHash':financial_hash,'counts':counts})

    def do_GET(self):
        if urlsplit(self.path).path == '/__memory-test/mock':
            return self.monitor()
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path == '/__memory-test/mock':
            return self.monitor()
        return super().do_POST()


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
print('APP: http://127.0.0.1:' + str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
