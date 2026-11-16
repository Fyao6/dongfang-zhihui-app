"""Real local server with QA-only constructor transport/secret injection. No prompt logging."""
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
import ai_gateway as gateway
parser = argparse.ArgumentParser()
parser.add_argument('--db', type=Path, required=True)
parser.add_argument('--token', required=True)
args = parser.parse_args()
assert not args.db.exists() and args.db.resolve().is_relative_to(root / '06_验证与后续工作')
lock, calls, held = threading.RLock(), [], []
state = {'mode': 'success'}


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
            return json.dumps({'content': [{'type': 'text', 'text': 'AG_LOCAL_MOCK_乙'}], 'usage': {'input_tokens': 7, 'output_tokens': 3}}).encode()
        return json.dumps({'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'AG_LOCAL_MOCK_甲'}]}], 'usage': {'input_tokens': 7, 'output_tokens': 3}}).encode()

    def __iter__(self):
        if self.mode == 'hold-before-first':
            self.release.wait(20)
        protocol = self.p['protocol']
        if protocol == 'anthropic_messages':
            frames = [event('message_start', {'type': 'message_start', 'message': {'usage': {'input_tokens': 7}}}), event('content_block_delta', {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': 'AG_LOCAL_MOCK_乙'}})]
            final = [event('message_delta', {'type': 'message_delta', **({} if self.mode == 'no-usage' else {'usage': {'output_tokens': 3}})}), event('message_stop', {'type': 'message_stop'})]
        else:
            frames = [event('response.output_text.delta', {'type': 'response.output_text.delta', 'delta': 'AG_LOCAL_MOCK_甲'})]
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
        calls.append({'providerId': p['id'], 'protocol': p['protocol'], 'payloadChars': len(serialized), 'privacyTagsPresent': 'consentEpoch' in serialized, 'forbiddenLegacyPresent': 'GW_LEGACY_PRIVATE_CANARY' in serialized, 'forbiddenBirthPresent': 'GW_LOCAL_BIRTH_CANARY' in serialized})
    if mode == 'primary-fails' and p['id'] == 'alpha':
        raise gateway.GatewayFailure('upstream_http_503', True)
    return Response(p, mode)


original_init = gateway.AIGateway.__init__


def injected_init(self, *values, **options):
    options['test_transport'] = transport
    options['test_secret_resolver'] = lambda ref: 'SYNTHETIC_LOCAL_NOT_REAL' if ref in ('EW_AI_GATEWAY_QA_ALPHA', 'EW_AI_GATEWAY_QA_BETA') else ''
    original_init(self, *values, **options)


gateway.AIGateway.__init__ = injected_init
spec = importlib.util.spec_from_file_location('saved_snapshot_test_actual_server', backend / 'server.py')
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
assert getattr(actual, 'AIGateway', None) is gateway.AIGateway, 'Actual public gateway dispatcher must be integrated'
assert getattr(actual,'SavedConversations',None), 'Saved snapshot API must be integrated before this real HTTP test'
class LegacyResponse:
    def __init__(self):
        with lock:current=state['mode']
        self.release=threading.Event() if current in ('hold','hold-before-first') else None
        if self.release:
            with lock:held.append(self.release)
    def __enter__(self):return self
    def __exit__(self,*unused):return False
    def read(self,limit=None):
        if self.release:self.release.wait(20)
        return json.dumps({'output':[{'type':'message','content':[{'type':'output_text','text':'SAVED_SNAPSHOT_LOCAL_LEGACY'}]}]}).encode()
def legacy_urlopen(request,*values,**options):
    url=request.full_url if hasattr(request,'full_url') else str(request)
    if not urlsplit(url).hostname.endswith('.invalid'):raise actual.URLError('QA blocks all external HTTP')
    payload=json.loads(request.data.decode());serialized=json.dumps(payload);response=LegacyResponse()
    with lock:calls.append({'providerId':'alpha','protocol':'legacy-responses','payloadChars':len(serialized),'privacyTagsPresent':'consentEpoch' in serialized,'forbiddenLegacyPresent':False,'forbiddenBirthPresent':False})
    return response
actual.urlopen=legacy_urlopen
# QA-only timing gate at the actual legacy save entry. The real guard still decides and writes.
legacy_save_state={'hold':False,'attempts':0};legacy_save_held=[]
original_legacy_save=actual.guarded_legacy_save
def paused_legacy_save(*values,**options):
    with lock:
        release=threading.Event() if legacy_save_state['hold'] else None
        if release:legacy_save_held.append(release)
        legacy_save_state['attempts']+=1
    if release:release.wait(20)
    return original_legacy_save(*values,**options)
actual.guarded_legacy_save=paused_legacy_save
base_handler = actual.make_handler(actual.Store(args.db), root / '03_当前APP')


class Handler(base_handler):
    def monitor(self):
        if self.headers.get('X-Privacy-Test') != args.token:
            self.send(403, {'error': 'test token required'})
            return
        if self.command == 'POST':
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            with lock:
                if 'mode' in data:
                    assert data['mode'] in ('success', 'primary-fails', 'partial', 'no-usage', 'hold', 'hold-before-first')
                    state['mode'] = data['mode']
                if 'holdSave' in data:
                    assert isinstance(data['holdSave'],bool)
                    legacy_save_state['hold']=data['holdSave']
                if data.get('releaseSave'):
                    for release in legacy_save_held:release.set()
                if data.get('release'):
                    for release in held:
                        release.set()
        with lock:
            self.send(200, {'isolated': True, 'externalProviderTested': False, 'kind': 'local-process-mock', 'calls': list(calls), 'mode': state['mode'], 'legacySaveAttempts':legacy_save_state['attempts'], 'legacySaveHold':legacy_save_state['hold']})

    def do_GET(self):
        if urlsplit(self.path).path == '/__saved-test/mock':
            return self.monitor()
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path == '/__saved-test/mock':
            return self.monitor()
        return super().do_POST()


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
print('APP: http://127.0.0.1:' + str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
