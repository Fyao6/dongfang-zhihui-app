"""Default read-only gate validation; --write creates immutable flat receipts and final local implementation record."""
import argparse,hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'06_验证与后续工作';CLOUD=ROOT/'04_研发源码/app/cloud'
MODULE_FILES=['04_研发源码/app/r4/backend/after_sales_finance.py','04_研发源码/app/cloud/lib/after-sales-finance.ts','04_研发源码/app/r4/after-sales-finance-money.js','04_研发源码/app/r4/after-sales-finance-ui.js','04_研发源码/app/r4/after-sales-finance-admin.js','04_研发源码/app/r4/after-sales-finance.css']
TEST_FILES=['负责人优化建议-售后资金关联Python专项.py','负责人优化建议-售后资金关联Cloud专项.cjs','负责人优化建议-售后资金关联前端专项.cjs','负责人优化建议-售后资金关联实际专项.cjs','负责人优化建议-售后资金关联HTTP专项.cjs','负责人优化建议-售后资金关联浏览器专项.cjs','负责人优化建议-售后资金关联Python测试服务.py','负责人优化建议-售后资金关联Cloud测试服务.ts','负责人优化建议-售后资金关联接入准备.py','负责人优化建议-售后资金关联SQL同步.py','负责人优化建议-售后资金关联验收冻结.py']
CAPTURES={'实际本人未知目标','实际后台撤销关联','实际四语金额进度-zh','实际四语金额进度-zh-Hant','实际四语金额进度-en','实际四语金额进度-bo','实际换号空态'}
def need(ok,message):
 if not ok:raise ValueError(message)
def local(p):
 p=Path(p).resolve();need(p.is_relative_to(ROOT.resolve()),'outside project '+str(p));return p
def rel(p):return local(p).relative_to(ROOT).as_posix()
def sha(p):p=local(p);need(p.is_file(),'missing '+rel(p));return hashlib.sha256(p.read_bytes()).hexdigest()
def payload(v):return (json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def read(p):
 p=local(p);need(p.is_file(),'missing '+rel(p));v=json.loads(p.read_text(encoding='utf-8-sig'));return v.get('latest',v)
def mapcheck(values,base,label):
 need(isinstance(values,dict) and values,label+' empty')
 for name,digest in values.items():need(sha(base/str(name).replace('\\','/'))==digest,label+' drift '+name)
def check(p,n,key='results',actual=True):
 r=read(p);need(r.get('passed')==n and r.get('failed')==0 and len(r.get(key,[]))==n and all(x.get('pass') is True for x in r[key]),'failed/incomplete '+rel(p))
 if actual:need(r.get('pass') is True,'actual pass missing '+rel(p))
 return r
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
 manifest=read(OUT/'负责人优化建议-售后资金关联准备状态.json');mapcheck(manifest['sourceSha256'],ROOT,'prepared six sources');need(set(MODULE_FILES)<=set(manifest['sourceSha256']),'manifest scope incomplete')
 copies={};verification={};actuals={}
 integration_path=OUT/'负责人优化建议-售后资金关联接入计划.json';integration=read(integration_path)
 need(integration.get('mode')=='apply' and len(integration.get('sourceChanges',[]))==9,'precise integration apply receipt missing')
 applied={x['path'].replace('\\','/'):x for x in integration['sourceChanges']}
 for name,value in applied.items():need(sha(ROOT/name)==value['afterSha256'],'applied source drift '+name)
 def independent_identity(values):
  need(isinstance(values,dict) and values,'independent source map empty')
  for name,digest in values.items():
   name=name.replace('\\','/')
   if sha(ROOT/name)==digest:continue
   # Only the two precisely integrated read-only legacy serializers differ from the independent pre-integration fixture.
   need(name in ['04_研发源码/app/r4/backend/after_sales.py','04_研发源码/app/cloud/lib/after-sales.ts'] and name in applied and applied[name]['beforeSha256']==digest and applied[name]['afterSha256']==sha(ROOT/name),'independent source drift '+name)

 def receipt(label,source,value,suffix):
  destination=OUT/('负责人优化建议-售后资金关联-'+suffix+'.json');copies[destination]=value
  verification[label]={'input':rel(source),'inputSha256':sha(source),'path':rel(destination),'sha256':hashlib.sha256(payload(value)).hexdigest(),'passed':value.get('passed'),'runId':value.get('runId')}
 for name,n,label,suffix in [('Python专项',32,'pythonMemory','Python内存验收'),('Cloud专项',32,'cloudMemory','Cloud内存验收'),('前端专项',25,'component','组件验收')]:
  source=OUT/('负责人优化建议-售后资金关联'+name+'.json');r=check(source,n,'checks',False);independent_identity(r['sourceSha256']);receipt(label,source,r,suffix)
 receipt('integration',integration_path,integration,'精确接入审计验收')
 for target,name,suffix in [('python','本轮全量回归结果','本机全量验收'),('cloud','公网适配全量回归结果','本地Cloud全量验收')]:
  source=OUT/('负责人优化建议-售后资金关联-'+name+'.json');r=check(source,60);build=r.get('buildHashes',{});need(r.get('module')=='负责人优化建议-售后资金关联','wrong full60 module')
  for name in ['东方智慧-首页体验R4.html','计时后台-开发联调.html']:need(build.get(name)==sha(ROOT/'03_当前APP'/name),'full60 APP/admin mismatch '+target)
  for name,digest in build.items():
   candidate=ROOT/name
   if not candidate.is_file():candidate=ROOT/'03_当前APP'/name
   need(sha(candidate)==digest,'full60 build drift '+name)
  cb=r.get('cloudBuildHashes')
  if target=='cloud':need(isinstance(cb,dict) and {'generated/experience.html','generated/admin.html','generated/review.html','lib/eastern-api.ts','worker/index.ts','dist/server/index.js'}<=set(cb),'Cloud full60 incomplete worker/build identity')
  if cb:mapcheck(cb,CLOUD,'Cloud full60')
  receipt(target+'Full',source,r,suffix)
 for target,suffix in [('python','本机实际专项验收'),('cloud','本地Cloud实际专项验收')]:
  source=OUT/('负责人优化建议-售后资金关联实际专项-'+target+'.json');r=check(source,24);need(r.get('target')==target and r.get('identityUnchanged') is True,'actual target/identity drift')
  identity=r.get('sourceBuildTestHashes');mapcheck(identity,ROOT,'actual source/build/test')
  for name in MODULE_FILES:need(name in identity,'actual lacks module '+name)
  for name in ['03_当前APP/东方智慧-首页体验R4.html','03_当前APP/计时后台-开发联调.html','04_研发源码/app/cloud/generated/experience.html','04_研发源码/app/cloud/generated/admin.html','04_研发源码/app/cloud/dist/server/index.js','04_研发源码/app/cloud/dist/server/BUILD_ID','04_研发源码/app/cloud/worker/index.ts']:need(name in identity,'actual identity incomplete '+name)
  need(r.get('errors')==[] and not any(x.get('status')==429 for x in r.get('traffic',[])),'actual errors/rate limit')
  need(r.get('syntheticDataOnly') is True and r.get('productionWrites') is False and r.get('realAIRequests')==0,'actual scope mismatch')
  current=ROOT/('03_当前APP/东方智慧-首页体验R4.html' if target=='python' else '04_研发源码/app/cloud/generated/experience.html');admin=ROOT/('03_当前APP/计时后台-开发联调.html' if target=='python' else '04_研发源码/app/cloud/generated/admin.html')
  need(r.get('servedBuildSha256')==sha(current) and r.get('servedAdminSha256')==sha(admin),'actual served APP/admin mismatch')
  views=r.get('views',[]);need(len(views)==64 and all(x.get('noOverflow') is True for x in views),'64 views missing or overflow')
  need(len({(x['screen'],x['width'],x['mode'],x['lang']) for x in views})==64,'duplicate/missing layout view')
  fonts=r.get('fontObservations',[]);need(len(fonts)==16 and all(x.get('faceCount',0)>0 and all(y=='loaded' for y in x.get('statuses',[])) and 'EW Tibetan' in x.get('fontFamily','') for x in fonts),'real16 Tibetan font views incomplete')
  font=r.get('embeddedFontAsset' if target=='python' else 'fontAsset',{});need(font.get('sha256')==sha(ROOT/'04_研发源码/app/r4/vendor/NotoSerifTibetan.woff2') and font.get('bytes')==772924,'real font exact bytes mismatch')
  need(font.get('verified') is True if target=='python' else font.get('status')==200,'font embedding/serving not confirmed')
  timers=r.get('timerObservations',[]);need(len(timers)==32 and {x['shape'] for x in timers}=={'compact','bar'},'32 real timer groups missing')
  need(len({(x['screen'],x['width'],x['mode'],x['lang'],x['shape']) for x in timers})==32,'duplicate timer group')
  need({x['nativeAction'] for x in timers}=={'refresh','case','open'},'native critical actions not all exercised')
  for x in timers:
   need(len(x['operations'])==3 and {z['action'] for z in x['operations']}=={'refresh','case','open'},'critical operation missing')
   need(all(z.get('fullyVisible') and z.get('noOverlap') and z.get('allHit') for z in x['operations']+[x['post']]),'critical operation not visible/hittable')
   need(x.get('responseStatus')==200 and x.get('timerStateUnchanged') is True and x['stableBefore']==x['stableAfter'] and x['stableBefore']['running'] is True and x['totalMsAfter']>=x['totalMsBefore'],'timer session or native action mismatch')
  prefix='负责人优化建议-售后资金关联-'+target+'-'+r['runId']+'-';names=r.get('captures',[]);hashes=r.get('captureHashes',[])
  need(len(names)==7 and {n[len(prefix):-4] for n in names if n.startswith(prefix) and n.endswith('.png')}==CAPTURES,'7 final capture set mismatch')
  need(len(hashes)==7 and {Path(x['path']).name for x in hashes}==set(names),'7 capture hashes incomplete')
  for row in hashes:need(sha(ROOT/row['path'])==row['sha256'],'capture drift '+row['path'])
  receipt(target+'Actual',source,r,suffix);actuals[target]=r
 source=OUT/'负责人优化建议-售后资金关联最终视觉核验.json';visual=read(source);need(visual.get('completed') is True,'visual not completed')
 for target,r in actuals.items():
  v=visual.get(target,{});need(v.get('runId')==r['runId'] and v.get('reportSha256')==sha(OUT/('负责人优化建议-售后资金关联实际专项-'+target+'.json')),'visual run/report mismatch')
  images=v.get('captures',[]);need(len(images)==7 and {x['path'] for x in images}=={x['path'] for x in r['captureHashes']},'visual image set mismatch')
  for image in images:need(image.get('viewed') is True and image.get('pass') is True and sha(ROOT/image['path'])==image.get('sha256'),'visual image unreviewed/drift')
 receipt('visual',source,visual,'最终视觉验收');verification['visual']['images']=14
 record={'module':'SH03/SH04/PAY19 explicit sandbox case-refund attribution','at':datetime.now(timezone.utc).isoformat(),'pass':True,'stage':'local software verified; no real refunds or payment-channel verification','sources':{p:sha(ROOT/p) for p in MODULE_FILES},'tests':{rel(OUT/p):sha(OUT/p) for p in TEST_FILES},'verification':verification,
 'scope':{'originalDatabasesUsed':False,'freshIsolatedServices':True,'productionEnabled':False,'actualFundsMoved':False,'realChannelVerified':False,'shippingOrDeductionsPolicyConfirmed':False,'automaticAllocation':False,'automaticLogisticsClosure':False,'newAndOriginalCaseApiSamePureSummary':True,'originalOrderLedgerAndStockUnchangedByAttribution':True,'explicitApprovalNullable':True,'zeroMeansNoRefundDue':True,'appliedOriginalRefundEventItemCapacityOnly':True,'appendOnlyReversalMeansUnlinkNotUndoRefund':True,'activeAdminFinalSQLGuard':True,'closedBuyerOwnerAndFinancialAuditRetained':True},
 'verificationCounts':{'pythonFull':60,'cloudFull':60,'pythonActual':24,'cloudActual':24,'pythonMemory':32,'cloudMemory':32,'component':25,'viewsPerBackend':64,'fontsPerBackend':16,'timerGroupsPerBackend':32,'threeActionGeometryGroupsPerBackend':96,'nativeClicksPerBackend':32,'finalScreenshots':14},
 'limits':['Production and external payment channels remain disabled/unverified.','Only explicit targets and reliable original sandbox refund item facts are matched; incomplete legacy allocation remains unknown.','Real carrier confirmation, formal shipping/deduction policy and automatic completion rules are not supplied.','The floating timer may temporarily cover scrollable noninteractive body text; scoped critical actions are verified after actual scrolling, not an all-page no-overlap claim.','Tibetan glyph/layout verified, not professional language certification.']}
 if args.write:
  for destination,value in copies.items():need(not destination.exists() or destination.read_bytes()==payload(value),'refuse overwrite frozen receipt '+rel(destination))
  destination=OUT/'负责人优化建议-售后资金关联-实施记录.json'
  if destination.exists():record['at']=json.loads(destination.read_text(encoding='utf-8'))['at']
  raw=payload(record);need(not destination.exists() or destination.read_bytes()==raw,'refuse overwrite implementation record')
  for file,value in copies.items():file.write_bytes(payload(value));need(sha(file)==hashlib.sha256(payload(value)).hexdigest(),'snapshot write mismatch')
  destination.write_bytes(raw)
 print(json.dumps({'mode':'write' if args.write else 'validate','pass':True,'immutableReceipts':len(copies),'gateSnapshots':4,'record':'06_验证与后续工作/负责人优化建议-售后资金关联-实施记录.json'},ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,TypeError) as error:print(json.dumps({'pass':False,'validationError':str(error)},ensure_ascii=False));sys.exit(1)
