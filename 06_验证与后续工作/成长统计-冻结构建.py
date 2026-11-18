from pathlib import Path
import json,hashlib,datetime
root=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((root/'06_验证与后续工作/当前产品可靠性-最终稳定构建记录.json').read_text(encoding='utf-8'))['actualSourceAndBuildHashes']
files={}
for name in old:
 if name.startswith('04_研发源码/app/cloud/dist/'):continue
 p=root/name
 assert p.is_file(),name
 files[name]=sha(p)
dist=root/'04_研发源码/app/cloud/dist'
for p in dist.rglob('*'):
 if p.is_file():files[p.relative_to(root).as_posix()]=sha(p)
assert '04_研发源码/app/r4/growth-tree.js' in files
assert b'data-growth-view="statistics"' in (root/'03_当前APP/东方智慧-首页体验R4.html').read_bytes()
record={'schemaVersion':1,'at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'status':'built-pending-local-acceptance','pass':True,'formalAcceptance':False,'localOnly':True,'scope':'用户2026-11-18最新参考：原创东方智慧成长足迹、自然周月年累计/履历、练习聆听两色时长柱及完整原资料；替代原分叉树理解；不照搬参考阅读页布局。','beforeProductManifest':'成长统计-改版前354源码保全-19f0fa5b3f2c.json','sourceChanges':['04_研发源码/app/r4/growth-tree.js','04_研发源码/app/r4/growth-tree.css'],'builds':['r4/build.py','cloud/prepare.py','cloud/scripts/run-framework.mjs build'],'strictTypeCheck':{'exitCode':0,'args':'--noEmit --incremental false --types node,@cloudflare/workers-types,vite/client','initialNoViteAmbientInvocation':'missing ?raw module declarations; not a backend code change'},'actualSourceAndBuildHashes':dict(sorted(files.items()))}
target=root/'06_验证与后续工作/成长统计-稳定构建记录.json'
with target.open('xb') as f:f.write((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'path':str(target),'sha256':sha(target),'productInputs':len(files)},ensure_ascii=False))
