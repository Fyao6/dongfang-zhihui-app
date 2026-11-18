"""Default read-only gate validation. --write freezes four snapshots and implementation record in existing 06."""
import argparse,hashlib,json,re,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'06_验证与后续工作';CLOUD=ROOT/'04_研发源码/app/cloud'
MODULE_FILES=['04_研发源码/app/r4/backend/account_closure.py','04_研发源码/app/r4/backend/account_write_guard.py','04_研发源码/app/cloud/lib/account-closure.ts','04_研发源码/app/cloud/lib/account-write-guard.ts','04_研发源码/app/r4/account-closure.js','04_研发源码/app/r4/account-closure.css']
TEST_FILES=['负责人优化建议-账号注销内存专项.py','负责人优化建议-账号注销Cloud内存专项.cjs','负责人优化建议-账号注销前端专项.cjs','负责人优化建议-账号注销网关接入内存专项.py','负责人优化建议-账号注销专项.cjs','负责人优化建议-账号注销测试工具.cjs','负责人优化建议-账号注销Python测试服务.py','负责人优化建议-账号注销Cloud测试服务.ts','负责人优化建议-账号注销接入准备.py','负责人优化建议-账号注销验收冻结.py']
CAPTURES={'实际密码验证与留存说明','实际二次明确确认','实际四语关闭回执-zh','实际四语关闭回执-zh-Hant','实际四语关闭回执-en','实际四语关闭回执-bo','实际第二标签停用隔离','实际换号后关闭回复迟到不退出新号'}
def need(ok,message):
 if not ok:raise ValueError(message)
def local(p):
 p=Path(p).resolve();need(p.is_relative_to(ROOT.resolve()),'outside project: '+str(p));return p
def rel(p):return local(p).relative_to(ROOT).as_posix()
def sha(p):p=local(p);need(p.is_file(),'missing '+rel(p));return hashlib.sha256(p.read_bytes()).hexdigest()
def payload(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def read(p):
 p=local(p);need(p.is_file(),'missing '+rel(p));v=json.loads(p.read_text(encoding='utf-8-sig'));return v.get('latest',v)
def mapcheck(values,base,label):
 need(isinstance(values,dict) and values,label+' empty')
 for name,digest in values.items():need(sha(base/str(name).replace('\\','/'))==digest,label+' drift '+name)
def check(p,n,actual=True):
 r=read(p);need(r.get('passed')==n and r.get('failed')==0 and len(r.get('results',[]))==n and all(x.get('pass') is True for x in r['results']),'failed/incomplete '+rel(p))
 if actual:need(r.get('pass') is True,'no actual pass '+rel(p))
 return r
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--python-full',type=Path,default=OUT/'负责人优化建议-账号注销-本轮全量回归结果.json')
 parser.add_argument('--cloud-full',type=Path,default=OUT/'负责人优化建议-账号注销-公网适配全量回归结果.json')
 parser.add_argument('--python-actual',type=Path,default=OUT/'负责人优化建议-账号注销专项-python.json')
 parser.add_argument('--cloud-actual',type=Path,default=OUT/'负责人优化建议-账号注销专项-cloud.json')
 parser.add_argument('--visual-review',type=Path,default=OUT/'负责人优化建议-账号注销最终视觉核验.json')
 parser.add_argument('--write',action='store_true');args=parser.parse_args()
 manifest=read(OUT/'负责人优化建议-账号注销准备核验.json');mapcheck(manifest['sources'],ROOT,'prepared sources')
 for p in MODULE_FILES:need(p in manifest['sources'],'module not pinned '+p)
 # Component reports are independent evidence; do not substitute them for HTTP/full60 gates.
 components={}
 for name,n in [('账号注销内存专项.py',22),('账号注销Cloud内存专项.cjs',26),('账号注销前端专项.cjs',11),('账号注销网关接入内存专项.py',3)]:
  file=OUT/('负责人优化建议-'+Path(name).with_suffix('.json').name);check(file,n,False);components[rel(file)]={'sha256':sha(file),'passed':n}
 copies={};verification={};actuals={}
 unit_proof_file=OUT/'负责人优化建议-账号注销后台原五单元拟议核验.json';unit_proof=read(unit_proof_file)
 need(unit_proof.get('pass') is True and unit_proof.get('ran')==5 and unit_proof.get('authMocked') is False,'original five units not real-auth verified')
 need(sha(OUT/'后台单元回归.py')==unit_proof.get('proposedUnitSha256'),'applied original adapter unit differs from verified proposed real-auth fixture')
 verification['originalUnitFixture']={'path':rel(unit_proof_file),'sha256':sha(unit_proof_file),'passed':5,'authMocked':False,'appliedUnitSha256':sha(OUT/'后台单元回归.py')}
 for target,p in [('python',args.python_full),('cloud',args.cloud_full)]:
  r=check(p,60);build=r.get('buildHashes',{})
  for name in ['东方智慧-首页体验R4.html','计时后台-开发联调.html']:need(build.get(name)==sha(ROOT/'03_当前APP'/name),'full60 APP/admin mismatch '+target)
  for name,digest in build.items():
   candidate=ROOT/name
   if not candidate.is_file():candidate=ROOT/'03_当前APP'/name
   need(sha(candidate)==digest,'full60 build drift '+name)
  cb=r.get('cloudBuildHashes')
  if target=='cloud':need(isinstance(cb,dict) and {'generated/experience.html','generated/admin.html','generated/review.html','lib/eastern-api.ts','worker/index.ts','dist/server/index.js'}<=set(cb),'Cloud full60 missing complete identity')
  if cb:mapcheck(cb,CLOUD,'full60 cloud')
  dest=OUT/('负责人优化建议-账号注销-'+('本机全量验收' if target=='python' else '本地Cloud全量验收')+'.json');copies[dest]=r
  verification[target+'Full']={'input':rel(p),'inputSha256':sha(p),'path':rel(dest),'sha256':hashlib.sha256(payload(r)).hexdigest(),'passed':60}
 for target,p in [('python',args.python_actual),('cloud',args.cloud_actual)]:
  r=check(p,27);need(r.get('identityUnchanged') is True,'actual identity changed '+target)
  need(r.get('coverage',{}).get('realHttp') is True and r['coverage'].get('realBrowser') is True,'actual HTTP/browser missing '+target)
  need(r.get('productionWrites') is False and r.get('externalProviderTested') is False,'scope mismatch '+target)
  need(r.get('errors')==[],'browser errors '+target)
  need(not any(x.get('status')==429 for x in r.get('traffic',[])),'actual rate limit '+target)
  identity=r.get('identity',{});mapcheck(identity.get('sources'),ROOT,'actual source');mapcheck(identity.get('builds'),ROOT,'actual build')
  mapcheck(r.get('testHashes'),OUT,'actual tests')
  for name in MODULE_FILES:need(name in identity.get('sources',{}),'actual did not bind module '+name)
  views=r.get('views',[]);need(len(views)==64 and all(v.get('pass') is True for v in views),'64 views missing '+target)
  keys={(x['stage'],x['lang'],x['mode'],x['width']) for x in views};need(len(keys)==64,'duplicate views '+target)
  fonts=r.get('fontChecks',[]);need(len(fonts)==64 and all(x.get('loaded') is True for x in fonts),'font checks incomplete '+target)
  if target=='cloud':need(r.get('localFontAssetVerified') is True,'Cloud real font asset not verified')
  prefix='负责人优化建议-账号注销-'+target+'-'+r['runId']+'-'
  hashes=r.get('captureHashes',{});names=r.get('captures',[])
  need(len(names)==8 and {n[len(prefix):-4] for n in names if n.startswith(prefix) and n.endswith('.png')}==CAPTURES,'final 8 captures mismatch '+target)
  for name in names:need(hashes.get(name)==sha(OUT/name),'capture hash mismatch '+name)
  actuals[target]=r
  dest=OUT/('负责人优化建议-账号注销-'+('本机实际专项验收' if target=='python' else '本地Cloud实际专项验收')+'.json');copies[dest]=r
  verification[target+'Actual']={'input':rel(p),'inputSha256':sha(p),'path':rel(dest),'sha256':hashlib.sha256(payload(r)).hexdigest(),'passed':27,'runId':r['runId']}
 visual=read(args.visual_review);need(visual.get('completed') is True,'visual review incomplete')
 for target,r in actuals.items():
  v=visual.get(target,{});need(v.get('runId')==r['runId'] and v.get('reportSha256')==sha(args.python_actual if target=='python' else args.cloud_actual),'visual/report run mismatch '+target)
  images=v.get('captures',[]);need(len(images)==8,'visual image count '+target)
  need({Path(x['path']).name for x in images}==set(r['captures']),'visual captures mismatch '+target)
  for row in images:need(row.get('viewed') is True and row.get('pass') is True and sha(ROOT/row['path'])==row.get('sha256'),'unreviewed visual '+str(row.get('path')))
 verification['visual']={'path':rel(args.visual_review),'sha256':sha(args.visual_review),'images':16}
 identity={name:sha(ROOT/name) for name in MODULE_FILES}
 tests={str((OUT/name).relative_to(ROOT)):sha(OUT/name) for name in TEST_FILES}
 record={'module':'PR04 final local account closure','at':datetime.now(timezone.utc).isoformat(),'pass':True,'stage':'local software verified; external erasure not claimed','sources':identity,'tests':tests,'components':components,'verification':verification,
 'scope':{'localAccountDisabled':True,'allServerSessionsRevoked':True,'oldPasswordVerifierInvalidated':True,'freshSyntheticDatabasesOnly':True,'originalAccountClosed':False,'originalDatabaseUsed':False,'productionPaymentEnabled':False,'realProviderTested':False,'providerErasure':'pending-confirmation','backupErasure':'pending-confirmation','thirdPartyRenewalCancelled':False,'financeAndFulfilmentRetained':True},
 'limits':['Unconfirmed legal retention periods are unknown.','No claim that other devices cookie bytes were erased.','New-version local marker is not a full-site CAS guarantee for obsolete tabs.','No external supplier/backup deletion or real subscription cancellation.']}
 if args.write:
  for p,value in copies.items():
   raw=payload(value)
   need(not p.exists() or p.read_bytes()==raw,'refuse overwrite frozen evidence '+rel(p))
  dest=OUT/'负责人优化建议-账号注销-实施记录.json'
  if dest.exists():record['at']=json.loads(dest.read_text(encoding='utf-8'))['at']
  raw=payload(record);need(not dest.exists() or dest.read_bytes()==raw,'refuse overwrite prior implementation record')
  for p,value in copies.items():
   p.write_bytes(payload(value));need(sha(p)==verification[('python' if '本机' in p.name and 'Cloud' not in p.name else 'cloud')+('Actual' if '实际专项' in p.name else 'Full')]['sha256'],'snapshot verification')
  dest.write_bytes(raw)
 print(json.dumps({'mode':'write' if args.write else 'validate','pass':True,'snapshots':4,'record':'06_验证与后续工作/负责人优化建议-账号注销-实施记录.json'},ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,TypeError) as e:print(json.dumps({'pass':False,'validationError':str(e)},ensure_ascii=False));sys.exit(1)
