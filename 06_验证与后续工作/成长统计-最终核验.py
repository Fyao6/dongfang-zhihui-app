from pathlib import Path
import json,hashlib,datetime
root=Path(__file__).resolve().parents[1];proof=root/'06_验证与后续工作'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
stable=proof/'成长统计-兼容修复后稳定构建记录.json'
assert sha(stable)=='b575c7f8990e5f64785a9726131b92b020e4811c00cf63ca34342e82cf67ed55'
product=json.loads(stable.read_text(encoding='utf-8'))['actualSourceAndBuildHashes']
for name,digest in product.items():assert sha(root/name)==digest,name
base=json.loads((proof/'成长统计-改版前354源码保全-19f0fa5b3f2c.json').read_text(encoding='utf-8'))
baseCopies={e['source']:e for e in base['entries']}
changes=json.loads((proof/'成长统计-v1失败原源码差异保全.json').read_text(encoding='utf-8'))
v1=json.loads((proof/'成长统计-稳定构建记录.json').read_text(encoding='utf-8'))['actualSourceAndBuildHashes']
for name,digest in v1.items():
 alias=changes[name]['savedAs'] if name in changes else baseCopies[name]['preservedCopy']
 assert sha(root/alias)==digest,('v1 historical source',name)
for e in base['entries']:assert sha(root/e['preservedCopy'])==e['stableSha256'],e['source']
receipts={};roles={}
for target in ['python','cloud']:
 for suite,count in [('full',60),('special',6)]:
  name=('负责人优化建议-卡组迁移-成长统计全量-'+('本轮' if target=='python' else '公网适配')+'全量回归结果.json') if suite=='full' else '成长统计-总览补充专项-'+target+'.json'
  p=proof/name;d=json.loads(p.read_text(encoding='utf-8'));r=d.get('latest',d)
  assert r.get('pass') is True and r.get('passed')==count and r.get('failed')==0,(name,r.get('passed'),r.get('failed'))
  key='growthStatisticsFullLauncher' if suite=='full' else 'growthStatisticsLauncher'
  launch=r[key]
  assert launch['childExitCode']==0 and launch['reportFreshForInvocation'] and launch['identityUnchanged']
  binding=launch['growthStatisticsBuildRecord'];assert binding['sha256']==sha(stable) and binding['path'].endswith(stable.name)
  inputs=launch['sourceAndBuildHashes']
  for n,s in product.items():assert inputs[n]==s,(name,n)
  assert launch['cleanup']['remainingOwnedPids']==[] and launch['cleanup']['privateVarsRemaining']==[]
  for a in launch['runtimeArtifacts']:
   assert sha(root/a['bundle'])==a['bundleSha256'] and sha(root/a['metafile'])==a['metafileSha256']
   for n,s in a['inputHashes'].items():assert inputs[n]==s
   for n,s in a['runtimeDependencyHashes'].items():assert sha(root/n)==s
  roles[target+'-'+suite]={'path':p.relative_to(root).as_posix(),'sha256':sha(p),'passed':count,'failed':0,'childExitCode':0,'sourceUnchanged':True,'ownedProcessAndVarsRemaining':0,'resourceRunId':launch['resourceRunId'],'compiledArtifacts':launch['runtimeArtifacts']}
receipt={'schemaVersion':1,'at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'kind':'growth-statistics-local-acceptance','pass':True,'localOnly':True,'production':False,'userVisualApproval':False,'scope':'按用户最新截图参考理念，原创东方智慧成长足迹；自然周/月/年/累计/履历、精确时长、练习聆听两色柱、觉察回看、所有原资料与日期未知/异常值可达；替代旧分叉树。','perBackend':{n:{'full':60,'special':6,'passed':66,'failed':0} for n in ['Python','Cloud']},'totalPassed':132,'totalFailed':0,'build':{'path':stable.relative_to(root).as_posix(),'sha256':sha(stable)},'actualSourceAndBuildHashes':product,'inputCount':len(product),'roles':roles,'compatibilityFix':'daily/homepage/journey原growthEvents日期排序对undefined安全；仅真实session/music事件id去重，原值不改。','originalCountsUnchanged':{'requirements':98,'localStages':31},'boundaries':['浏览器本地合成历史只证明展示与统计，不冒充真实用户活动','本人资料仍本浏览器按账号隔离；完整跨设备同步未实现','藏语母语审校、真实手机、用户视觉评价与正式服务另验','未推送、未公开发布、未重打ZIP'],'history':['成长树-本地验收记录.json为旧分叉树历史验收','成长统计-稳定构建记录.json为首轮构建，不引用其未通过项为当前通过','成长统计-v1失败原源码差异保全.json + 成长统计-改版前354源码保全-19f0fa5b3f2c.json覆盖全部原源码字节','首轮真实无日期profile异常及全量触摸失败与新QA接线失败保留']}
out=proof/'成长统计-本地验收记录.json'
with out.open('xb') as f:f.write((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'pass':True,'passed':132,'failed':0,'sha256':sha(out),'productInputs':len(product)},ensure_ascii=False))
