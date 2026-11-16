"""Fresh-DB QA entry. Real server for every route except token-only fault fixture."""
import argparse
import json
from pathlib import Path
import re
import sys
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'04_研发源码/app/r4/backend'))
import server as actual

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--token',required=True);args=p.parse_args()
    db=args.db.resolve();assert db.parent==Path(__file__).resolve().parent and not db.exists();assert len(args.token)>=32
    store=actual.Store(db);Base=actual.make_handler(store,ROOT/'03_当前APP')
    class Handler(Base):
        def route(self,method):
            parsed=urlsplit(self.path)
            if parsed.path=='/__commission-test/snapshot':
                if method!='GET' or self.headers.get('X-Commission-Test')!=args.token:return self.send(403,{'error':'QA token required'})
                oid=parse_qs(parsed.query).get('orderId',[''])[0]
                if not re.fullmatch('[a-f0-9-]{36}',oid):return self.send(400,{'error':'invalid QA order'})
                with store.connect() as conn:rows=[{'itemId':r['item_id'],'snapshot':json.loads(r['data'])} for r in conn.execute('SELECT item_id,data FROM commission_snapshots WHERE order_id=?',(oid,))]
                return self.send(200,{'isolated':True,'rows':rows})
            if parsed.path!='/__commission-test/fault':return super().route(method)
            if method!='POST' or self.headers.get('X-Commission-Test')!=args.token:return self.send(403,{'error':'QA token required'})
            try:
                data=self.body();oid=data.get('orderId','');stage=data.get('stage')
                if not re.fullmatch('[a-f0-9-]{36}',oid) or stage not in ('ledger','adjustment') or type(data.get('enabled')) is not bool:return self.send(400,{'error':'invalid QA fault fixture'})
                with store.connect() as conn:
                    if not conn.execute('SELECT 1 FROM commerce_orders WHERE id=?',(oid,)).fetchone():return self.send(404,{'error':'new QA order required'})
                    conn.execute('DROP TRIGGER IF EXISTS commission_qa_fault')
                    if data['enabled']:
                        table='commission_ledger' if stage=='ledger' else 'commission_adjustments'
                        condition="NEW.order_id='"+oid+"'" if stage=='ledger' else "EXISTS(SELECT 1 FROM commission_ledger WHERE id=NEW.ledger_id AND order_id='"+oid+"')"
                        conn.execute("CREATE TRIGGER commission_qa_fault BEFORE INSERT ON "+table+" WHEN "+condition+" BEGIN SELECT RAISE(ABORT,'commission_qa_fault'); END")
                return self.send(200,{'isolated':True,'enabled':data['enabled'],'stage':stage,'actualPaid':False})
            except Exception as error:return self.send(400,{'error':type(error).__name__})
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler);print('APP: http://127.0.0.1:'+str(http.server_port)+'/app',flush=True)
    try:http.serve_forever()
    finally:http.server_close()
if __name__=='__main__':main()
