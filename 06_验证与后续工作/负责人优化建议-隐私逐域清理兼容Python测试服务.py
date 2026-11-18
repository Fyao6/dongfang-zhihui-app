"""Prepared fresh-only loopback wrapper; actual integrated application, fixed synthetic fixture."""
import argparse,hashlib,json,sys,time
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'04_研发源码/app/r4/backend'))
import server as actual
def no_outbound(*a,**k):raise RuntimeError('retention QA forbids outbound')
actual.urlopen=no_outbound
def main():
 p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--token',required=True);args=p.parse_args();file=args.db.resolve()
 assert file.parent==Path(__file__).resolve().parent and not file.exists() and len(args.token)>=32
 fixture=json.loads(Path(__file__).with_name('负责人优化建议-隐私逐域清理兼容夹具.json').read_bytes());assert fixture['syntheticOnly']
 store=actual.Store(file);Base=actual.make_handler(store,ROOT/'03_当前APP')
 class Handler(Base):
  def route(self,method):
   path=urlsplit(self.path).path
   if not path.startswith('/__retention-test/'):return super().route(method)
   if self.headers.get('X-Retention-Test')!=args.token:return self.send(403,{'error':'test token'})
   try:
    d=self.body() if method=='POST' else {};owner=d.get('owner','');stamp=time.time_ns()//1000000
    if path.endswith('/command') and method=='POST':
     command=d['command'];assert command in fixture['commands'];mapping={'@OWNER':owner,'@OTHER':d.get('other'),'@TARGET':d.get('target'),'@NOW':stamp,'@STALE':stamp-50000,'@RECENT':stamp-120000,'@ENDED':stamp-110000,'@OLD':stamp-3*86400000,'@FUTURE':stamp+3600000}
     with store.connect() as db:
      db.execute('BEGIN IMMEDIATE')
      for sql,values in fixture['commands'][command]:db.execute(sql,[mapping.get(v,v) if isinstance(v,str) else v for v in values])
     return self.send(200,{'isolated':True,'syntheticOnly':True})
    if path.endswith('/inspect') and method=='POST':
     with store.connect() as db:
      db.execute('BEGIN');names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
      financial=[n for n in names if n.startswith(('commerce_','membership_','commission_','after_sales_')) or n in ('ai_gateway_wallets','ai_gateway_grants','ai_gateway_quota_events','ai_gateway_attempts','card_daily_quota','card_zone_preferences','audits')]
      values={n:sorted(json.dumps(dict(r),sort_keys=True) for r in db.execute('SELECT * FROM '+n)) for n in financial}
      counts={n:db.execute('SELECT count(*) FROM '+n+' WHERE '+w,(owner,)).fetchone()[0] for n,w in [('records','owner=?'),('privacy_conversations','user_id=?'),('timer_runs','owner=?'),('activity_daily','user_id=?'),('measurements','connection_id IN (SELECT id FROM devices WHERE owner=?)'),('card_draws','owner=?'),('card_draw_actions','owner=?'),('card_practice_events','owner=?'),('card_draw_requests','owner=?')]}
      job=db.execute("SELECT output_text IS NULL AND saved_conversation_id IS NULL AS cleared,cancel_requested FROM ai_gateway_jobs WHERE owner=? AND id='rt-job'",(owner,)).fetchone()
      epoch=db.execute('SELECT coalesce((SELECT revision FROM privacy_record_epochs WHERE owner=?),0)',(owner,)).fetchone()[0]
     return self.send(200,{'isolated':True,'counts':counts,'gateway':dict(job) if job else None,'recordEpoch':epoch,'financialHash':hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest(),'financialTables':financial})
    return self.send(404,{'error':'fixed QA endpoint'})
   except Exception as e:return self.send(400,{'error':str(e)})
 http=ThreadingHTTPServer(('127.0.0.1',0),Handler);print('APP: http://127.0.0.1:'+str(http.server_port)+'/app',flush=True)
 try:http.serve_forever()
 finally:http.server_close()
if __name__=='__main__':main()
