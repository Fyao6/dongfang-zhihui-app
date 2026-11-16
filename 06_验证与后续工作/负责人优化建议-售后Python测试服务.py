"""Prepared AfterSales isolated real-service wrapper. Does not run unless invoked explicitly."""
import argparse
import importlib.util
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "04_研发源码/app/r4/backend"
sys.path.insert(0, str(BACKEND))
parser = argparse.ArgumentParser()
parser.add_argument("--db", type=Path, required=True)
args = parser.parse_args()
assert not args.db.exists() and args.db.resolve().is_relative_to(ROOT / "06_验证与后续工作")
spec = importlib.util.spec_from_file_location("after_sales_actual_server", BACKEND / "server.py")
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
actual.urlopen = lambda *a, **k: (_ for _ in ()).throw(actual.URLError("AfterSales QA blocks external provider calls"))
handler = actual.make_handler(actual.Store(args.db), ROOT / "03_当前APP")
server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
print("APP: http://127.0.0.1:" + str(server.server_port), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()

