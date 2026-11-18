"""Run original five unit assertions against only in-memory proposed source and a fresh owned SQLite fixture. No shared edits/services/network."""
from pathlib import Path
from uuid import uuid4
import contextlib,hashlib,io,json,runpy,sys,types,unittest
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'06_验证与后续工作';RUN=str(uuid4())
def sha(s):return hashlib.sha256(s if isinstance(s,bytes) else s.encode('utf-8')).hexdigest()
argv=sys.argv[:];sys.argv=[__file__]
with contextlib.redirect_stdout(io.StringIO()):
 integration=runpy.run_path(str(OUT/'负责人优化建议-密钥引用接入准备.py'))
 regression=runpy.run_path(str(OUT/'负责人优化建议-密钥引用回归兼容准备.py'))
sys.argv=argv
server=ROOT/'04_研发源码/app/r4/backend/server.py';unit=OUT/'后台单元回归.py'
proposed=integration['changes'][server];test=regression['changes'][unit]
assert test.count('spec.loader.exec_module(app)')==1
test=test.replace('spec.loader.exec_module(app)',"exec(compile(_secret_proposed_server,str(root/'04_研发源码/app/r4/backend/server.py'),'exec'),app.__dict__)",1)
assert test.count("'本轮单元回归专用.sqlite3'")==1
owned='负责人优化建议-密钥引用拟议五单元隔离-'+RUN+'.sqlite3';test=test.replace("'本轮单元回归专用.sqlite3'",repr(owned),1)
assert "patch.object(app, 'open_legacy_ai'" in test
module=types.ModuleType('secret_proposed_units');module.__file__=str(unit);module._secret_proposed_server=proposed
exec(compile(test,str(unit),'exec'),module.__dict__)
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(module.BackendRegression))
report={'at':RUN,'kind':'in-memory-proposed-real-server-and-original-five-units','pass':result.wasSuccessful(),'ran':result.testsRun,'failed':len(result.failures)+len(result.errors),'authMocked':False,'providerTransport':'explicit open_legacy_ai only; no external request','originalUnitPath':str(unit.relative_to(ROOT)),'originalUnitSha256':sha(unit.read_bytes()),'proposedUnitSha256':sha(regression['changes'][unit]),'proposedServerSha256':sha(proposed),'ownedDatabase':str((OUT/owned).relative_to(ROOT)),'ownedDatabaseRemoved':not (OUT/owned).exists(),'sharedEdited':False,'serviceStarted':False,'productionDatabaseOpened':False,'sourceSha256':{p:sha((ROOT/p).read_bytes()) for p in ['04_研发源码/app/r4/backend/secret_references.py','04_研发源码/app/cloud/lib/secret-references.ts','04_研发源码/app/r4/secret-references-admin.js','04_研发源码/app/r4/secret-references-admin.css']},'detail':stream.getvalue()}
assert report['ran']==5
file=OUT/'负责人优化建议-密钥引用后台拟议五单元.json';old=json.loads(file.read_text(encoding='utf-8')) if file.exists() else {};file.write_bytes((json.dumps({'latest':report,'runs':old.get('runs',[])+[report]},ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'pass':report['pass'],'ran':report['ran'],'failed':report['failed'],'authMocked':False,'sharedEdited':False}));sys.exit(0 if report['pass'] else 1)
