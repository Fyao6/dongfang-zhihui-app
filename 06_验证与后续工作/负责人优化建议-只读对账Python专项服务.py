"""Fresh owned DB only. Actual integrated routes; token-only synthetic seed/damage/hash."""
import argparse,hashlib,json,re,sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'04_研发源码/app/r4/backend'))
import server as actual
def forbid_outbound(*args,**kwargs):raise RuntimeError('Reconciliation QA forbids external services')
actual.urlopen=forbid_outbound
FIXTURE=Path(__file__).with_name('负责人优化建议-只读对账合成夹具.json')
def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--token',required=True);a=p.parse_args();db_path=a.db.resolve()
    assert db_path.parent==Path(__file__).resolve().parent and not db_path.exists() and len(a.token)>=32
    fixture=json.loads(FIXTURE.read_text(encoding='utf-8'));assert fixture['syntheticOnly']
    store=actual.Store(db_path);Base=actual.make_handler(store,ROOT/'03_当前APP');actors={};baseline_triggers=None
    def financial(name):return name.startswith(('commerce_','membership_','commission_'))
    identity_fields={'owner','beneficiary','actor','approver','creator','user_id','owner_id','userId','ownerId','accountId','authorId','createdBy','approvedBy'}
    def rewrite(value,field=''):
        if isinstance(value,list):return [rewrite(v,field) for v in value]
        if isinstance(value,dict):return {k:rewrite(v,k) for k,v in value.items()}
        if isinstance(value,str):
            if field in identity_fields and value in actors:return actors[value]
            try:
                v=json.loads(value)
                if isinstance(v,(list,dict)):return json.dumps(rewrite(v),ensure_ascii=False,separators=(',',':'))
            except (ValueError,TypeError):pass
        return value
    class Handler(Base):
        def route(self,method):
            nonlocal actors,baseline_triggers
            path=urlsplit(self.path).path
            if not path.startswith('/__reconciliation-test/'):return super().route(method)
            if self.headers.get('X-Reconciliation-Test')!=a.token:return self.send(403,{'error':'QA token required'})
            try:
                if path.endswith('/hash') and method=='GET':
                    with store.connect() as db:
                        db.execute('BEGIN');tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") if financial(r[0])];values={}
                        for table in tables:values[table]=sorted(json.dumps(dict(r),sort_keys=True,ensure_ascii=False) for r in db.execute('SELECT * FROM '+table))
                    return self.send(200,{'isolated':True,'sha256':hashlib.sha256(json.dumps(values,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'tableCount':len(tables),'actualPaid':False})
                if method!='POST':return self.send(405,{'error':'QA method'})
                data=self.body()
                if path.endswith('/seed'):
                    mapping=data.get('actors',{});assert set(fixture['tables']['users']['rows'][i][0] for i in range(len(fixture['tables']['users']['rows'])))<=set(mapping)
                    assert all(isinstance(v,str) and re.fullmatch('[a-zA-Z0-9_-]{1,100}',v) for v in mapping.values());actors=mapping
                    with store.connect() as db:
                        triggers=[dict(r) for r in db.execute("SELECT name,tbl_name,sql FROM sqlite_master WHERE type='trigger'") if financial(r['tbl_name'])]
                        if baseline_triggers is None:baseline_triggers=triggers
                        db.execute('PRAGMA foreign_keys=OFF')
                        try:
                            for t in triggers:db.execute('DROP TRIGGER '+t['name'])
                            names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if financial(r[0])]
                            for name in names:db.execute('DELETE FROM '+name)
                            for name,t in fixture['tables'].items():
                                if not financial(name):continue
                                assert name in names
                                sql='INSERT INTO '+name+'('+','.join(t['columns'])+') VALUES('+','.join('?' for _ in t['columns'])+')'
                                db.executemany(sql,[[rewrite(v,k) for k,v in zip(t['columns'],row)] for row in t['rows']])
                            for uid,role in fixture['tables']['users']['rows']:db.execute('UPDATE users SET role=? WHERE id=?',(role,actors[uid]))
                            for key,value in fixture['tables'].get('settings',{}).get('rows',[]):
                                if key=='membership_lifecycle':db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,value))
                            for t in baseline_triggers:db.execute(t['sql'])
                            db.commit();assert not db.execute('PRAGMA foreign_key_check').fetchall()
                        finally:db.execute('PRAGMA foreign_keys=ON')
                    return self.send(200,{'isolated':True,'syntheticOnly':True,'actualPaid':False})
                if path.endswith('/damage'):
                    key=data.get('case');assert type(key) is int and 0<=key<len(fixture['cases']);case=fixture['cases'][key];sql=case.get('sql');assert sql
                    for source,target in actors.items():sql=sql.replace("'"+source+"'","'"+target+"'")
                    with store.connect() as db:db.execute(sql,tuple(actors.get(v,v) if isinstance(v,str) else v for v in case.get('params',[])))
                    return self.send(200,{'isolated':True,'case':key,'actualPaid':False})
                if path.endswith('/missing'):
                    assert data.get('table')=='commission_payments'
                    with store.connect() as db:
                        db.execute('ALTER TABLE commission_payments RENAME TO qa_held_commission_payments')
                        db.execute('CREATE VIEW commission_payments AS SELECT * FROM qa_held_commission_payments')
                    return self.send(200,{'isolated':True})
                if path.endswith('/truncate'):
                    with store.connect() as db:db.executemany('INSERT INTO commission_facts VALUES(?,?,?,?)',[('limit-http-'+str(i),'{}',0,'TEST') for i in range(5001)])
                    return self.send(200,{'isolated':True})
                return self.send(404,{'error':'QA route'})
            except Exception as error:return self.send(400,{'error':type(error).__name__+': '+str(error)})
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler);print('APP: http://127.0.0.1:'+str(http.server_port)+'/app',flush=True)
    try:http.serve_forever()
    finally:http.server_close()
if __name__=='__main__':main()
