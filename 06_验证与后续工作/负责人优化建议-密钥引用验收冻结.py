"""Default read-only final gates; --write only after actual/full runs and visual checks are complete. No credential reads."""
import argparse,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'06_验证与后续工作';CLOUD=ROOT/'04_研发源码/app/cloud'
MODULE_FILES=['04_研发源码/app/r4/backend/secret_references.py','04_研发源码/app/cloud/lib/secret-references.ts','04_研发源码/app/r4/secret-references-admin.js','04_研发源码/app/r4/secret-references-admin.css']
TEST_FILES=['负责人优化建议-密钥引用Python专项.py','负责人优化建议-密钥引用Cloud专项.cjs','负责人优化建议-密钥引用前端专项.cjs','负责人优化建议-密钥引用后台拟议五单元.py','负责人优化建议-密钥引用接入准备.py','负责人优化建议-密钥引用回归兼容准备.py','负责人优化建议-密钥引用实际专项.cjs','负责人优化建议-密钥引用HTTP专项.cjs','负责人优化建议-密钥引用浏览器专项.cjs','负责人优化建议-密钥引用Python测试服务.py','负责人优化建议-密钥引用Cloud测试服务.ts','负责人优化建议-密钥引用测试环境.cjs','负责人优化建议-密钥引用验收冻结.py','负责人优化建议-密钥引用按钮可读性.cjs','负责人优化建议-密钥引用窄屏Smoke.cjs']
CAPTURES={'实际后台引用配置','实际明确确认迁移','实际四语安全配置-zh','实际四语安全配置-zh-Hant','实际四语安全配置-en','实际四语安全配置-bo','实际换号无迁移资料'}
def need(ok,msg):
 if not ok:raise ValueError(msg)
def local(p):
 p=Path(p).resolve();need(p.is_relative_to(ROOT.resolve()),'outside project '+str(p));return p
def rel(p):return local(p).relative_to(ROOT).as_posix()
def sha(p):p=local(p);need(p.is_file(),'missing '+rel(p));return hashlib.sha256(p.read_bytes()).hexdigest()
def payload(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def read(p):
 p=local(p);need(p.is_file(),'missing '+rel(p));v=json.loads(p.read_text(encoding='utf-8-sig'));return v.get('latest',v)
def mapcheck(values,base,label):
 need(isinstance(values,dict) and values,label+' map missing')
 for name,digest in values.items():need(sha(base/str(name).replace('\\','/'))==digest,label+' drift '+name)
def check(p,n,key='results'):
 r=read(p);need(r.get('passed')==n and r.get('failed')==0 and r.get('pass') is True and len(r.get(key,[]))==n and all(x.get('pass') is True for x in r[key]),'incomplete or failed '+rel(p));return r
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args();copies={};verification={};actuals={}
 manifest=read(OUT/'负责人优化建议-密钥引用准备核验.json');mapcheck(manifest['sources'],ROOT,'prepared4');need(set(MODULE_FILES)==set(manifest['sources']),'prepared scope mismatch')
 def receipt(label,source,value,suffix):
  destination=OUT/('负责人优化建议-密钥引用-'+suffix+'.json');copies[destination]=value;verification[label]={'input':rel(source),'inputSha256':sha(source),'path':rel(destination),'sha256':hashlib.sha256(payload(value)).hexdigest(),'passed':value.get('passed',value.get('ran')),'runId':value.get('runId',value.get('at'))}
 for name,n,label,suffix in [('Python专项',28,'pythonMemory','Python内存验收'),('Cloud专项',29,'cloudMemory','Cloud内存验收'),('前端专项',13,'component','组件验收')]:
  source=OUT/('负责人优化建议-密钥引用'+name+'.json');r=check(source,n,'checks');mapcheck(r['sourceSha256'],ROOT,'independent source');receipt(label,source,r,suffix)
 source=OUT/'负责人优化建议-密钥引用后台拟议五单元.json';unit=read(source);need(unit.get('pass') is True and unit.get('ran')==5 and unit.get('failed')==0 and unit.get('authMocked') is False,'original five units not real-auth passed');mapcheck({k:v for k,v in unit['sourceSha256'].items() if k in MODULE_FILES[:2]},ROOT,'executed backend unit source')
 need(unit['proposedUnitSha256']==sha(OUT/'后台单元回归.py') and unit['proposedServerSha256']==sha(ROOT/'04_研发源码/app/r4/backend/server.py'),'applied original units/server differ from tested exact proposed source');receipt('originalFiveUnits',source,unit,'原五单元验收')
 source=OUT/'负责人优化建议-密钥引用窄屏Smoke.json';smoke=read(source);need(smoke.get('pass') is True and smoke.get('passed')==16 and smoke.get('failed')==0 and len(smoke.get('views',[]))==16,'layout smoke incomplete');mapcheck(smoke['sourceSha256'],ROOT,'layout smoke source');receipt('layoutSmoke',source,smoke,'窄屏准备验收')
 for name,label,suffix in [('接入计划','integration','精确业务接入审计验收'),('回归兼容计划','regressionIntegration','精确回归接入审计验收')]:
  source=OUT/('负责人优化建议-密钥引用'+name+'.json');r=read(source);need(r.get('mode')=='apply','integration not applied '+name)
  for row in r.get('sourceChanges',[]):need(sha(ROOT/row['path'])==row['afterSha256'],'applied integration source drift '+row['path'])
  receipt(label,source,r,suffix)
 for target,name,suffix in [('python','本轮全量回归结果','本机全量验收'),('cloud','公网适配全量回归结果','本地Cloud全量验收')]:
  source=OUT/('负责人优化建议-密钥引用-'+name+'.json');r=check(source,60);need(r.get('module')=='负责人优化建议-密钥引用','wrong full module');build=r.get('buildHashes',{})
  for name in ['东方智慧-首页体验R4.html','计时后台-开发联调.html']:need(build.get(name)==sha(ROOT/'03_当前APP'/name),'full APP/admin mismatch')
  for name,digest in build.items():
   p=ROOT/name
   if not p.is_file():p=ROOT/'03_当前APP'/name
   need(sha(p)==digest,'full build drift '+name)
  cb=r.get('cloudBuildHashes')
  if target=='cloud':need(isinstance(cb,dict) and {'generated/experience.html','generated/admin.html','generated/review.html','lib/eastern-api.ts','worker/index.ts','dist/server/index.js'}<=set(cb),'Cloud complete build hashes absent')
  if cb:mapcheck(cb,CLOUD,'full Cloud')
  receipt(target+'Full',source,r,suffix)
 for target,suffix in [('python','本机实际专项验收'),('cloud','本地Cloud实际专项验收')]:
  source=OUT/('负责人优化建议-密钥引用实际专项-'+target+'.json');r=check(source,20);need(r.get('identityUnchanged') is True and r.get('target')==target,'actual target or identity mismatch');identity=r.get('sourceBuildTestHashes',{});mapcheck(identity,ROOT,'actual source/build/test')
  for name in MODULE_FILES+['04_研发源码/app/cloud/dist/server/index.js','04_研发源码/app/cloud/dist/server/BUILD_ID','04_研发源码/app/cloud/worker/index.ts']:need(name in identity,'actual identity absent '+name)
  need(r.get('errors')==[] and not any(x.get('status')==429 for x in r.get('traffic',[])),'actual error/429');need(r.get('syntheticDataOnly') is True and r.get('productionWrites') is False and r.get('realAIRequests')==0,'scope mismatch')
  current=ROOT/('03_当前APP/东方智慧-首页体验R4.html' if target=='python' else '04_研发源码/app/cloud/generated/experience.html');admin=ROOT/('03_当前APP/计时后台-开发联调.html' if target=='python' else '04_研发源码/app/cloud/generated/admin.html')
  need(r.get('servedBuildSha256')==sha(current) and r.get('servedAdminSha256')==sha(admin),'actual served APP/admin mismatch')
  views=r.get('views',[]);need(len(views)==16 and len({(x['width'],x['lang']) for x in views})==16 and all(x.get('noOverflow') is True for x in views),'16 views incomplete')
  readability=r.get('buttonReadability',[]);need(len(readability)==16 and len({(x['width'],x['lang']) for x in readability})==16,'16 button readability groups missing')
  for view in readability:
   need(len(view['reachability'])>=4 and all(x.get('fullyVisible') and x.get('allHit') for x in view['reachability']),'control not reachable by actual native scroll')
   need(view['noPageOverflow'] and all(x['width']>=44 and x['height']>=44 and x['noTextClip'] and (not x['critical'] or x['lineCount']==1) for x in view['buttons']),'button clipping/wrapping')
   if view['lang']=='en':need(all(x['lines']==1 for x in view['statusWords']),'status words split')
  fonts=r.get('fontObservations',[]);need(len(fonts)==4 and all(x.get('faceCount',0)>0 and 'EW-Tibetan' in x.get('fontFamily','') and all(s=='loaded' for s in x.get('statuses',[])) for x in fonts),'4 real Tibetan font observations missing')
  font=r.get('embeddedFontAsset' if target=='python' else 'fontAsset',{});need(font.get('sha256')==sha(ROOT/'04_研发源码/app/r4/vendor/NotoSerifTibetan.woff2') and font.get('bytes')==772924,'font bytes mismatch')
  need(font.get('verified') is True if target=='python' else font.get('status')==200,'font embedding/serving not proven')
  prefix='负责人优化建议-密钥引用-'+target+'-'+r['runId']+'-';names=r.get('captures',[]);hashes=r.get('captureHashes',[]);need(len(names)==7 and {n[len(prefix):-4] for n in names if n.startswith(prefix) and n.endswith('.png')}==CAPTURES,'capture set mismatch');need(len(hashes)==7 and {Path(x['path']).name for x in hashes}==set(names),'capture map mismatch')
  for row in hashes:need(sha(ROOT/row['path'])==row['sha256'],'capture drift')
  receipt(target+'Actual',source,r,suffix);actuals[target]=r
 source=OUT/'负责人优化建议-密钥引用最终视觉核验.json';visual=read(source);need(visual.get('completed') is True,'visual incomplete')
 for target,r in actuals.items():
  v=visual.get(target,{});need(v.get('runId')==r['runId'] and v.get('reportSha256')==sha(OUT/('负责人优化建议-密钥引用实际专项-'+target+'.json')),'visual report/run mismatch');rows=v.get('captures',[]);need(len(rows)==7 and {x['path'] for x in rows}=={x['path'] for x in r['captureHashes']},'visual set mismatch')
  for row in rows:need(row.get('viewed') is True and row.get('pass') is True and sha(ROOT/row['path'])==row.get('sha256'),'visual image unreviewed/drift')
 receipt('visual',source,visual,'最终视觉验收');verification['visual']['images']=14
 record={'module':'PR06 controlled legacy AI and device env credential references','at':datetime.now(timezone.utc).isoformat(),'pass':True,'stage':'local software verified; no original credential migration or managed cloud verification','sources':{p:sha(ROOT/p) for p in MODULE_FILES},'tests':{rel(OUT/p):sha(OUT/p) for p in TEST_FILES},'verification':verification,'verificationCounts':{'pythonFull':60,'cloudFull':60,'pythonActual':20,'cloudActual':20,'pythonMemory':28,'cloudMemory':29,'component':13,'layoutSmoke':16,'originalFiveUnits':5,'viewsPerBackend':16,'fontViewsPerBackend':4,'finalScreenshots':14},'scope':{'originalDatabaseUsed':False,'originalCredentialMigrated':False,'realProviderTested':False,'productionTLSVerified':False,'managedKMSVerified':False,'IAMOrMFAVerified':False,'realCredentialRotationPerformed':False,'serverControlledPurposeEnvOnly':True,'plaintextFallbackAllowed':False,'newPlaintextFieldsAllowed':False,'explicitExactValueCASMigration':True,'legacyRedirectsAllRejected':True,'mediaOrGlobalOpenerChanged':False,'oldUnmigratedValuesRemainAndBlockUse':True,'deviceProtocol':'actual Authorization Bearer; no invented HMAC protocol','authorizationMockedInOriginalUnits':False,'originalUnitEvidenceScope':'Backend-only: administrative CSS was not executed in the five backend tests; its old incidental identity is superseded by current13 component/16 smoke/dual actual UI checks.'},'limits':['Actual adapters use explicit local synthetic transport; no real AI provider request.','Only synthetic fresh databases migrated; original credentials were not read, exported or migrated.','Runtime env/Worker bindings are not proof of managed remote KMS, IAM, MFA, rotation or production TLS.','Historical frozen actual wrappers using plaintext must deliberately adopt ref/env/new transport before any future rerun; no fallback is enabled to satisfy obsolete fixtures.']}
 if args.write:
  for p,v in copies.items():need(not p.exists() or p.read_bytes()==payload(v),'refuse overwrite frozen evidence '+rel(p))
  dest=OUT/'负责人优化建议-密钥引用-实施记录.json'
  if dest.exists():record['at']=json.loads(dest.read_text(encoding='utf-8'))['at']
  raw=payload(record);need(not dest.exists() or dest.read_bytes()==raw,'refuse overwrite implementation record')
  for p,v in copies.items():p.write_bytes(payload(v));need(sha(p)==hashlib.sha256(payload(v)).hexdigest(),'receipt write mismatch')
  dest.write_bytes(raw)
 print(json.dumps({'mode':'write' if args.write else 'validate','pass':True,'gateSnapshots':4,'immutableReceipts':len(copies),'record':'06_验证与后续工作/负责人优化建议-密钥引用-实施记录.json'},ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,TypeError) as error:print(json.dumps({'pass':False,'validationError':str(error)},ensure_ascii=False));sys.exit(1)
