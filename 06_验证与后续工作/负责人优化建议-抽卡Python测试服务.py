"""Fresh local-only actual card API service. No pre-existing DB, fake card results or external traffic."""
import argparse
import importlib.util
from pathlib import Path
import sys
from http.server import ThreadingHTTPServer
root=Path(__file__).resolve().parents[1]
backend=root/'04_研发源码/app/r4/backend'
sys.path.insert(0,str(backend))
parser=argparse.ArgumentParser()
parser.add_argument('--db',type=Path,required=True)
args=parser.parse_args()
assert not args.db.exists() and args.db.resolve().is_relative_to(root/'06_验证与后续工作')
spec=importlib.util.spec_from_file_location('card_qa_actual_server',backend/'server.py')
actual=importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
assert getattr(actual,'CardService',None), 'Card service is not integrated into the actual public Python entry yet'
actual.urlopen=lambda *values,**options: (_ for _ in ()).throw(actual.URLError('QA blocks all external HTTP'))
store=actual.Store(args.db)
handler=actual.make_handler(store,root/'03_当前APP')
server=ThreadingHTTPServer(('127.0.0.1',0),handler)
print('APP: http://127.0.0.1:'+str(server.server_port),flush=True)
try:server.serve_forever()
finally:server.server_close()
