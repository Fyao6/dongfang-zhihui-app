"""Actual fixed-child lossless wire stress; component only, no database or API."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,os,subprocess,time,uuid

ROOT=Path(__file__).resolve().parent.parent
OUT=Path(__file__).resolve().parent
R4=ROOT/'04_研发源码/app/r4'
NODE=Path('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
WORKER=R4/'backend/card_import_worker.cjs'
spec=importlib.util.spec_from_file_location('actual_card_wire',R4/'backend/card_import_wire.py')
wire=importlib.util.module_from_spec(spec);spec.loader.exec_module(wire)
dump=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
sha=lambda v:hashlib.sha256(v).hexdigest()
environment={k:os.environ[k] for k in ('SystemRoot','WINDIR','TEMP','TMP') if k in os.environ}
environment.update(PATH=str(NODE.parent),TZ='UTC',LANG='C.UTF-8')
rows=[]
for index in range(500):
    rows.append({'id':'stress_'+str(index),'theme':'invalid','text':{lang:{k:None for k in ['name','prompt','meaning','question','action']} for lang in ['zh','zh-Hant','en']},'frontUrl':None,'backUrl':None,'alt':{lang:None for lang in ['zh','zh-Hant','en']},'author':None,'licenseReference':None,'licenseScope':None,'practiceKey':'invalid','courseId':1,'actionSeconds':0,'sandboxOnly':None})
payload={'schema':1,'deck':{'deckId':'synthetic-wire-stress','version':1,'environment':'sandbox','data':{'name':'','system':'daily-wisdom','expectedCount':None,'cards':rows,'rightsReference':'','artReviewNote':''}},'baseVersionId':None,'baseRevision':None,'provenance':{'sourceType':'synthetic_sandbox','sourceReference':'仅供无损诊断组件测试'*166+'长'*8,'sourceDocumentSha256':None,'fieldSources':[]}}
raw=dump(payload).encode();assert len(raw)<=262144
request=dump({'op':'inspect','payload':payload,'baseData':None}).encode()
started=time.monotonic()
process=subprocess.Popen([str(NODE),str(WORKER)],cwd=R4/'backend',env=environment,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
stdout,stderr=process.communicate(request,timeout=20)
assert process.returncode==0 and len(stdout)<=8*1024*1024 and len(stderr)<=65536
envelope=json.loads(stdout);assert envelope['ok'] is True and envelope['codec']==wire.CODEC
decoded=wire.worker_result(envelope)
assert decoded['payload']==payload and decoded['summary']['issues']==len(decoded['issues']) and decoded['summary']['diff']==len(decoded['diff'])
assert len(decoded['issues'])>20000 and len(decoded['diff'])>10000
def row_hash(values):
    h=hashlib.sha256()
    for row in values:h.update((dump(row)+'\n').encode())
    return h.hexdigest()
script="""const fs=require('node:fs'),crypto=require('node:crypto'),engine=require('./04_研发源码/app/r4/card-import-engine.js');const p=JSON.parse(fs.readFileSync(0,'utf8'));const r=engine.inspect(p,null),wire=engine.packWire(r),decoded=engine.decodeWire(wire);function h(rows){const h=crypto.createHash('sha256');for(const row of rows)h.update(engine.canonical(row)+'\\n');return h.digest('hex');}process.stdout.write(JSON.stringify({issues:r.issues.length,diff:r.diff.length,issuesHash:h(r.issues),diffHash:h(r.diff),decodedIssuesHash:h(decoded.issues),decodedDiffHash:h(decoded.diff),wireBytes:Buffer.byteLength(JSON.stringify(wire))}));"""
native=json.loads(subprocess.check_output([str(NODE),'-e',script],input=raw,cwd=ROOT,env=environment,timeout=30))
assert native['issues']==len(decoded['issues']) and native['diff']==len(decoded['diff'])
assert native['issuesHash']==native['decodedIssuesHash']==row_hash(decoded['issues'])
assert native['diffHash']==native['decodedDiffHash']==row_hash(decoded['diff'])
chunks=[decoded['issues'][i:i+50] for i in range(0,len(decoded['issues']),50)]
max_chunk=0
for chunk in chunks:
    encoded=wire.pack_wire(chunk);max_chunk=max(max_chunk,len(dump(encoded).encode()));assert wire.decode_wire(encoded)==chunk
bad_rejected=0
for bad in [{'codec':wire.CODEC,'dictionary':[],'result':[0,0]},{'codec':wire.CODEC,'dictionary':['x'],'result':[2,0,1,0,2]},{'codec':wire.CODEC,'dictionary':['__proto__'],'result':[2,0,None]}]:
    try:wire.decode_wire(bad)
    except ValueError:bad_rejected+=1
assert bad_rejected==3
report={'at':datetime.now(timezone.utc).isoformat(),'pass':True,'scope':'Actual fixed Node IPC + Python/JS codec and complete per-row hashes; no HTTP/DB/D1/browser or rights approval.','productionMaterialsVerifiedBySystem':False,'rawBytes':len(raw),'sourceReferenceCharacters':len(payload['provenance']['sourceReference']),'sourceReferenceUtf8Bytes':len(payload['provenance']['sourceReference'].encode()),'issues':len(decoded['issues']),'diff':len(decoded['diff']),'actualChild':{'pid':process.pid,'nodeSha256':sha(NODE.read_bytes()),'workerSha256':sha(WORKER.read_bytes()),'stdinBytes':len(request),'stdoutBytes':len(stdout),'stderrBytes':len(stderr),'exitCode':process.returncode,'environmentKeys':sorted(environment),'shell':False},'elapsedSeconds':time.monotonic()-started,'nativeEngine':native,'allIssueChunksRoundtrip':len(chunks),'maxEncodedChunkBytes':max_chunk,'invalidWireRejected':bad_rejected,'inputSHA256':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in [Path(__file__),R4/'card-import-engine.js',R4/'card-import-engine.d.ts',WORKER,R4/'backend/card_import_wire.py']}}
target=OUT/('负责人优化建议-卡组迁移字典组件-'+uuid.uuid4().hex[:10]+'.json');target.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'pass':True,'report':target.name,'rawBytes':len(raw),'issues':len(decoded['issues']),'diff':len(decoded['diff']),'wireBytes':len(stdout),'maxChunkBytes':max_chunk}))
