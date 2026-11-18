"""Local SQLite/API backup rehearsal. Creates fresh test files only, never opens a production DB."""
from pathlib import Path
import sys, json, sqlite3, hashlib, uuid, time, threading, importlib.util, urllib.request
from http.server import ThreadingHTTPServer
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parent.parent
QA=Path(__file__).resolve().parent
SERVER=ROOT/'04_研发源码/app/r4/backend/server.py'
sys.path.insert(0,str(SERVER.parent))
spec=importlib.util.spec_from_file_location('backup_rehearsal_server',SERVER)
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
run=uuid.uuid4().hex[:12]
paths=[QA/('负责人优化建议-隔离恢复-'+run+'-'+name+'.sqlite3') for name in ('live','backup','restored')]
for p in paths:
 if p.resolve().parent!=QA.resolve() or p.exists():raise RuntimeError('Test path must be fresh and inside QA.')
live,backup,restored=paths
checks=[];servers=[];report={'at':datetime.now(timezone.utc).isoformat(),'runId':run,'scope':'Local SQLite and actual read/write HTTP API only','syntheticDataOnly':True,'productionDatabaseOpened':False,'externalRequests':0,'paymentRecoveryVerified':False,'providerRecoveryVerified':False,'multiAZFailoverVerified':False}
def check(name,condition):
 checks.append({'name':name,'pass':bool(condition)})
 if not condition:raise AssertionError(name)
def serve(db):
 store=app.Store(db)
 handler=app.make_handler(store,ROOT/'03_当前APP')
 http=ThreadingHTTPServer(('127.0.0.1',0),handler)
 thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();servers.append(http)
 return 'http://127.0.0.1:'+str(http.server_port)
visitor=uuid.uuid4().hex
def api(base,path,data=None):
 raw=json.dumps(data).encode() if data is not None else None
 req=urllib.request.Request(base+'/api/'+path,raw,headers={'Cookie':'ew_visitor='+visitor,'Content-Type':'application/json','Origin':base},method='POST' if raw else 'GET')
 with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
def digest_rows(db):
 result={}
 with sqlite3.connect(db) as c:
  names=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
  for name in names:
   safe='"'+name.replace('"','""')+'"'
   rows=c.execute('SELECT * FROM '+safe).fetchall()
   canonical=sorted(json.dumps(list(r),ensure_ascii=False,sort_keys=True,default=lambda b:b.hex() if isinstance(b,bytes) else str(b)) for r in rows)
   result[name]={'count':len(rows),'sha256':hashlib.sha256('\n'.join(canonical).encode()).hexdigest()}
 return result
def owner_records(db):
 with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as c:return c.execute('SELECT kind,day,data FROM records WHERE owner=? ORDER BY day',('visitor:'+visitor,)).fetchall()
try:
 base=serve(live)
 for day in range(1,11):
  api(base,'records',{'kind':'checkin','date':'2026-10-'+str(day).zfill(2),'data':{'rehearsal':True,'index':day}})
 before=owner_records(live);public_before=api(base,'public')
 check('Actual write API acknowledged ten synthetic records present in owner DB',len(before)==10)
 started=time.perf_counter()
 with sqlite3.connect(live.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(backup) as target:source.backup(target)
 backup_seconds=time.perf_counter()-started
 baseline=digest_rows(live);backup_manifest=digest_rows(backup)
 check('Online backup contains identical logical tables and rows',baseline==backup_manifest)
 with sqlite3.connect(backup) as c:
  check('Backup integrity_check ok',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
  check('Backup has no foreign key violations',not c.execute('PRAGMA foreign_key_check').fetchall())
 api(base,'records',{'kind':'checkin','date':'2026-10-11','data':{'rehearsal':True,'index':11}})
 check('A post-backup acknowledged write exists only in live DB',len(owner_records(live))==11)
 started=time.perf_counter()
 with sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(restored) as target:source.backup(target)
 check('Restore targets a distinct new DB and preserves backup',restored!=live and digest_rows(restored)==backup_manifest and digest_rows(backup)==backup_manifest)
 restored_base=serve(restored)
 check('Restored DB contains precisely backed-up owner records',owner_records(restored)==before)
 check('Actual restored service serves the same public catalog',api(restored_base,'public')==public_before)
 restore_seconds=time.perf_counter()-started
 with sqlite3.connect(restored) as c:
  check('Restored DB integrity_check ok',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
  check('Restored DB has no foreign key violations',not c.execute('PRAGMA foreign_key_check').fetchall())
 report.update(pass_=True,backupSeconds=round(backup_seconds,4),localRestoreAndAPIVerificationSeconds=round(restore_seconds,4),restoredTables=backup_manifest,acknowledgedWritesAfterBackupNotRecovered=1,measuredProductionRPO=None,measuredProductionRTO=None)
except Exception as e:
 report.update(pass_=False,error=type(e).__name__+': '+str(e))
finally:
 for http in servers:http.shutdown();http.server_close()
report['pass']=report.pop('pass_',False);report['checks']=checks;report['passed']=sum(c['pass'] for c in checks);report['failed']=sum(not c['pass'] for c in checks)
report['testFiles']=[str(p.relative_to(ROOT)) for p in paths]
report['limitations']=['Only newly created isolated SQLite databases were opened.','The post-backup acknowledged write is intentionally absent after restore; no zero-loss claim.','No PostgreSQL/PITR, Cloud D1 backup, cross-region, live payments, real GPU interruption or production RPO/RTO was exercised.']
target=QA/('负责人优化建议-隔离备份恢复演练'+('' if report['pass'] else '-失败-'+run)+'.json')
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ('pass','passed','failed','externalRequests')},ensure_ascii=False))
if not report['pass']:raise SystemExit(1)

