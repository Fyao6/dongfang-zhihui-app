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
assert not args.db.exists() and args.db.resolve().parent == root / '06_验证与后续工作'
assert args.db.name.startswith('负责人优化建议-卡组迁移注销兼容隔离-')
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
spec = importlib.util.spec_from_file_location('account_closure_test_actual_server', backend / 'server.py')
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
actual.open_legacy_ai=legacy_urlopen
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
assert getattr(actual,'AccountClosure',None), 'Closure must be integrated before HTTP test'
owned_store=actual.Store(args.db)
base_handler = actual.make_handler(owned_store, root / '03_当前APP')

# QA-only body gates at the real handler's read point, after require().
body_state={'path':'','attempts':0}
body_waiters=[]
def pause_body(handler):
    with lock:
        selected=body_state['path']==urlsplit(handler.path).path
        if selected:
            body_state['path']='';body_state['attempts']+=1
            release=threading.Event();body_waiters.append(release)
        else:release=None
    if release:release.wait(25)

def inspect_owner(owner):
    with owned_store.connect() as db:
        def n(table,where,column='count(*)',args=None):
            return db.execute('SELECT '+column+' FROM '+table+' WHERE '+where,args or (owner,)).fetchone()[0]
        p=db.execute('SELECT data,revision,policy_version,provider_binding FROM privacy_preferences WHERE user_id=?',(owner,)).fetchone()
        life=db.execute('SELECT status,epoch,closed_at FROM account_lifecycle WHERE owner=?',(owner,)).fetchone()
        wallet=db.execute('SELECT balance,reserved FROM ai_gateway_wallets WHERE owner=?',(owner,)).fetchone()
        return {'sessions':n('sessions','user_id=?'),'revokedSessions':n('account_revoked_sessions','owner=?'),
          'records':n('records','owner=?'),'measurements':n('measurements','connection_id IN (SELECT id FROM devices WHERE owner=?)'),'saved':n('privacy_conversations','user_id=?'),
          'receipts':n('account_closure_receipts','owner=?'),'mediaOwn':n('media','owner=?'),'lifecycle':dict(life) if life else None,
          'preferences':{'consents':json.loads(p['data']),'revision':p['revision'],'policyVersion':p['policy_version'],'providerBindingCleared':not p['provider_binding']} if p else None,
          'wallet':dict(wallet) if wallet else None,'fenceRows':db.execute('SELECT count(*) FROM account_action_fences').fetchone()[0]}



class Handler(base_handler):
    def body(self,*args,**kwargs):
        pause_body(self)
        return super().body(*args,**kwargs)
    def begin(self):
        super().begin()
        if self.command=='POST' and urlsplit(self.path).path=='/api/media':
            original=self.rfile
            class PausedReader:
                def __getattr__(inner,key):return getattr(original,key)
                def read(inner,*args):pause_body(self);return original.read(*args)
            self.rfile=PausedReader()

    def monitor(self):
        if self.headers.get('X-Privacy-Test') != args.token:
            self.send(403, {'error': 'test token required'})
            return
        if self.command == 'POST':
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            with lock:
                if data.get('holdBodyPath'):
                    body_state['path']=data['holdBodyPath']
                if data.get('releaseBody'):
                    for release in body_waiters:release.set()
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
        inspection=inspect_owner(data['inspectOwner']) if self.command=='POST' and data.get('inspectOwner') else None
        with lock:
            self.send(200, {'isolated': True, 'externalProviderTested': False, 'kind': 'local-process-mock', 'calls': list(calls), 'mode': state['mode'], 'legacySaveAttempts':legacy_save_state['attempts'], 'legacySaveHold':legacy_save_state['hold'],'bodyAttempts':body_state['attempts'],'inspection':inspection})

    def do_GET(self):
        if urlsplit(self.path).path == '/__closure-test/mock':
            return self.monitor()
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path == '/__closure-test/mock':
            return self.monitor()
        return super().do_POST()


server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
print('APP: http://127.0.0.1:' + str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
