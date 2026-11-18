"""Independent real loopback JSON/SSE fixture. No quota logic, prompt logs or external calls."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ['PRIVACY_DOMAINS_TEST_TOKEN']
SAMPLE_TOKEN = os.environ['BAZI_SAMPLE_TEST_TOKEN']
SECRET = os.environ['PRIVACY_DOMAINS_PROVIDER_SECRET']
assert len(TOKEN) >= 32 and len(SAMPLE_TOKEN) >= 32 and len(SECRET) >= 32
lock = threading.RLock()
state = {'mode':'success','calls':[],'held':[],'redirectFollowed':0}
OUTPUT = 'PRIVACY_DOMAIN_GATEWAY_OUTPUT_CANARY'


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass

    def reply(self, code, value, headers=None):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        for key,value in (headers or {}).items():
            self.send_header(key,value)
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        if self.headers.get('Transfer-Encoding','').lower() == 'chunked':
            parts, size = [], 0
            while True:
                count = int(self.rfile.readline(100).split(b';',1)[0],16)
                if not count:
                    self.rfile.readline(100)
                    break
                size += count
                if size > 262144:
                    raise ValueError('oversize')
                parts.append(self.rfile.read(count))
                if self.rfile.read(2) != b'\r\n':
                    raise ValueError('chunk')
            return b''.join(parts)
        size = int(self.headers.get('Content-Length','0'))
        if not 0 < size <= 262144:
            raise ValueError('length')
        return self.rfile.read(size)

    def control(self):
        if self.headers.get('X-Privacy-Domains-Test') != TOKEN and self.headers.get('X-Bazi-Samples-Fixture') != SAMPLE_TOKEN:
            return self.reply(403,{'error':'fixture token required'})
        if self.command == 'POST':
            try:
                data = json.loads(self.read_body())
                assert set(data) <= {'mode','release'}
                with lock:
                    if 'mode' in data:
                        assert data['mode'] in ('success','hold','hold-before-first','http500','redirect','partial')
                        state['mode'] = data['mode']
                    if data.get('release'):
                        for gate in state['held']:
                            gate.set()
            except (ValueError,AssertionError):
                return self.reply(400,{'error':'invalid fixed fixture control'})
        with lock:
            return self.reply(200,{'isolated':True,'realHttp':True,'realSupplier':False,'externalProviderTested':False,'promptLogging':False,'mode':state['mode'],'calls':list(state['calls']),'held':sum(not gate.is_set() for gate in state['held']),'redirectFollowed':state['redirectFollowed']})

    def do_GET(self):
        if self.path == '/bazi-samples-fixture/control':
            return self.control()
        if self.path == '/bazi-samples-fixture/redirect-target':
            with lock:
                state['redirectFollowed'] += 1
            return self.reply(409,{'error':'redirect trap must not be followed'})
        return self.reply(404,{'error':'not found'})

    def do_POST(self):
        if self.path == '/bazi-samples-fixture/control':
            return self.control()
        if self.path not in ('/bazi-samples-fixture/alpha/responses','/bazi-samples-fixture/beta/messages','/bazi-samples-fixture/legacy/responses'):
            return self.reply(404,{'error':'not found'})
        if self.headers.get('Authorization') != 'Bearer '+SECRET and self.headers.get('X-Api-Key') != SECRET:
            return self.reply(401,{'error':'synthetic fixture authentication required'})
        try:
            payload = json.loads(self.read_body())
            assert isinstance(payload,dict)
        except (ValueError,AssertionError):
            return self.reply(400,{'error':'invalid JSON request'})
        provider = 'beta' if '/beta/' in self.path else 'legacy' if '/legacy/' in self.path else 'alpha'
        with lock:
            mode = state['mode']
            serialized = json.dumps(payload, ensure_ascii=False)
            state['calls'].append({'sequence':len(state['calls'])+1,'providerId':provider,'protocol':('legacy-responses' if payload.get('stream') is not True else 'anthropic_messages' if provider=='beta' else 'responses'),'streaming':payload.get('stream') is True,'payloadChars':len(serialized),
                'b11MetadataPresent':any(value in serialized for value in ('bazi:v1:','outputFingerprint','selectedViewFingerprint','baziInterpretation','replyFingerprint','adapterVersion','bzv-','live-b11-')),
                'privateB11BirthPresent':'PRIVATE_B11_BIRTH_CANARY' in serialized,
                'b11ExactBirthPresent':any(value in serialized for value in ('1990-06-15','23:30','15:30:00')),
                'privacyTagsPresent':'consentEpoch' in serialized,
                'samplePrivateBirthPresent':'SYNTHETIC_BAZI_PRIVATE_BIRTH' in serialized,
                'forbiddenLegacyPresent':'GW_LEGACY_PRIVATE_CANARY' in serialized,
                'forbiddenBirthPresent':'GW_LOCAL_BIRTH_CANARY' in serialized})
        if mode == 'http500':
            return self.reply(500,{'error':'explicit synthetic upstream failure'})
        if mode == 'redirect':
            return self.reply(302,{'error':'redirect is not a trusted result'},{'Location':'/bazi-samples-fixture/redirect-target'})

        def wait():
            gate = threading.Event()
            with lock:
                state['held'].append(gate)
            gate.wait(30)

        if mode == 'hold-before-first':
            wait()
        if payload.get('stream') is not True:
            if mode == 'hold':
                wait()
            value = {'content':[{'type':'text','text':OUTPUT}]} if provider == 'beta' else {'output':[{'type':'message','content':[{'type':'output_text','text':OUTPUT}]}]}
            value['usage'] = {'input_tokens':7,'output_tokens':3}
            return self.reply(200,value)
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream')
        self.send_header('Cache-Control','no-store')
        self.send_header('Connection','close')
        self.end_headers()

        def frame(kind,data):
            raw=('event: '+kind+'\ndata: '+json.dumps(data,ensure_ascii=False)+'\n\n').encode()
            for offset in range(0,len(raw),7):
                self.wfile.write(raw[offset:offset+7])
            self.wfile.flush()

        try:
            if provider == 'beta':
                frame('message_start',{'type':'message_start','message':{'usage':{'input_tokens':7}}})
                frame('content_block_delta',{'type':'content_block_delta','delta':{'type':'text_delta','text':OUTPUT}})
            else:
                frame('response.output_text.delta',{'type':'response.output_text.delta','delta':OUTPUT})
            if mode == 'hold':
                wait()
            if mode != 'partial':
                if provider == 'beta':
                    frame('message_delta',{'type':'message_delta','usage':{'output_tokens':3}})
                    frame('message_stop',{'type':'message_stop'})
                else:
                    frame('response.completed',{'type':'response.completed','response':{'usage':{'input_tokens':7,'output_tokens':3}}})
        except (BrokenPipeError,ConnectionResetError):
            pass
        finally:
            self.close_connection = True


server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
print('BAZI_SAMPLES_PROVIDER: http://127.0.0.1:'+str(server.server_port)+'/bazi-samples-fixture',flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
