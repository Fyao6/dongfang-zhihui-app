from pathlib import Path
import hashlib,json,datetime
root=Path(__file__).resolve().parents[1]; proof=root/'06_验证与后续工作'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=proof/'成长统计-本地验收记录.json'
r=json.loads(receipt.read_text(encoding='utf-8'))
assert r['pass'] is True and all(v['full']==60 and v['special']==6 and v['failed']==0 for v in r['perBackend'].values())
stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
saved=stamp.strftime('%Y%m%d-%H%M%S-%f')
backups={}
def preserve(p):
 target=proof/f'成长统计-接续回填前-{saved}-{p.name}.原字节'
 with target.open('xb') as f:f.write(p.read_bytes())
 backups[p.relative_to(root).as_posix()]={'sha256':sha(p),'backup':target.relative_to(root).as_posix()}
def write_json(p,value):p.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
title='成长足迹与时间统计'
summary='用户2026-11-18提供统计页参考，并明确“不要抄袭”，要求用自己的方式优化东方智慧成长记录。最新要求覆盖此前“唯一分叉关系树”的解释。当前采用东方智慧原创成长足迹布局：自然周/月/年/累计及完整履历，练习/聆听两色堆叠柱与觉察回看，按原日期及真实已保存时长统计；无日期、未知字段与全部原资料可查，默认计划与APP陪伴账本不加进练习时长。双端各60完整+6实际专项通过。用户视觉、藏语母语、实机及跨设备同步仍另验；原98项和31阶段计数保持，未推送、发布或重打包。'
p=root/'AGENTS.md';preserve(p)
old=p.read_text(encoding='utf-8');first,rest=old.split('\n',1)
p.write_text(first+'\n\n## 2026-11-18 最新成长记录视觉要求（优先于下文旧唯树描述）\n\n'+summary+'\n验收：06_验证与后续工作/成长统计-本地验收记录.json；本轮源码与03/Cloud构建以成长统计-兼容修复后稳定构建记录.json为准。旧成长树及31阶段收据保留原字节，代表各自历史构建。\n'+rest,encoding='utf-8',newline='\n')
p=root/'公司同步-先读我.txt';preserve(p)
p.write_text('当前成长记录更新（'+stamp.isoformat()+'）\n'+summary+'\n最新验收：06_验证与后续工作/成长统计-本地验收记录.json。下文唯树描述属于旧视觉验收时点。\n\n'+p.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
p=proof/'公司同步-进度与记忆.json';preserve(p);d=json.loads(p.read_text(encoding='utf-8'))
item=next(i for i in d['additionalRequirements'] if i['id']=='ADD-GROWTH')
item['previousImplementation']=dict(item)
item.update(title=title,status='本地已验证，待用户视觉与实机验收',scope=summary,perBackendPassed=66,receipt='06_验证与后续工作/成长统计-本地验收记录.json',receiptSHA256=sha(receipt),productionPublished=False)
d['savedAtBeijing']=stamp.isoformat();d['growthVisualLatest']={'request':'不要抄袭，我要的是你参考那张图 通过自己的方式去优化出来我们自己的成长记录','summary':summary,'build':'06_验证与后续工作/成长统计-兼容修复后稳定构建记录.json','receiptSHA256':sha(receipt)}
book=proof/'东方智慧APP需求进度表-20261116.xlsx'
d['progress']['workbookSha256']=sha(book)
write_json(p,d)
p=proof/'强制成长树-当前接续.json';preserve(p);d=json.loads(p.read_text(encoding='utf-8'))
d['savedAt']=stamp.isoformat();d['active']=summary
d['previousImplementationScheduling']=d.get('implementationScheduling')
d['implementationScheduling']='本轮成长统计、双端验证与书表交接完成；用户视觉、实机、藏语母语和正式服务按边界另验。'
for i,item in enumerate(d.get('newRequirements',[])):
 if item.get('id')=='growth-tree-only':d['newRequirements'][i]={'id':'growth-time-statistics','mandatory':True,'previousImplementation':item,'scope':summary,'status':'本地已验收，待视觉与实机','receipt':'成长统计-本地验收记录.json','receiptSHA256':sha(receipt),'perBackend':'60完整+6专项，66/0各端','onlyTree':False}
d['boundaries']=['未推送、公开发布或重打包','原98项和正式31阶段保持，追加成长视觉不虚增原任务计数','旧冻结收据及源码原字节保留；测试仅自有fresh DB/state','新统计布局按最新参考方向实现，不代表用户已认可视觉、实机或生产已验收']
d['growthIntegration']={'previousImplementation':d.get('growthIntegration'),'buildRecord':'成长统计-兼容修复后稳定构建记录.json','buildRecordSHA256':sha(proof/'成长统计-兼容修复后稳定构建记录.json'),'appSHA256':sha(root/'03_当前APP/东方智慧-首页体验R4.html'),'cloudHTMLSHA256':sha(root/'04_研发源码/app/cloud/generated/experience.html'),'latestStatistics':{'summary':summary,'receipt':'成长统计-本地验收记录.json','sha256':sha(receipt)},'finalVerification':'Python60+6与Cloud60+6实际通过，原98项与31阶段保持。'}
d['delivery']['workbooks']={p.name:sha(p) for p in [proof/'东方智慧APP需求进度表-20261116.xlsx',proof/'东方智慧APP优化任务表_依据v1.0_20261112.xlsx']}
write_json(p,d)
p=proof/'成长统计-当前接续.json';preserve(p);d=json.loads(p.read_text(encoding='utf-8-sig'))
d.update(savedAt=stamp.isoformat(),localComplete=True,userVisualApproved=False,implementation=summary,pythonFull='60/0，自然退出并清0；旧触摸失败已保留并确认实际提醒阻挡原CDP，最终仅原生关闭真实提醒后按原动作和1000ms通过',cloudFull='60/0，自然退出并清0',special='双端各6/0；每端24统计总览+24长详情布局覆盖，全部自有进程和vars清0',books='两份追加需求B3:F3已按实际结果回填，原98项/31阶段与其它所有内容保持',receipt='成长统计-本地验收记录.json',receiptSHA256=sha(receipt),next=['用户视觉评价、真实手机及藏语母语审校另验','后续按原98项待资料与正式服务边界接续，不将本地结果称为生产完成'])
write_json(p,d)
p=root/'05_后台与研发说明/成长足迹与统计口径说明.txt'
assert not p.exists()
p.write_text(summary+'\n\n统计口径\n1. 周为周一至周日，月和年为自然周期；累计按本人已保存的有效过去日期。未来日期与无日期原资料留在履历，不塞入今天。练习和聆听按原保存日期归桶，不倒推跨午夜分摊。\n2. 时长仅实际session/music安全非负整数seconds。无效或缺失显示“未记录时长”；默认计划、未完checkpoint、最后打开课程、自主行动和APP陪伴计时不增加时长。\n3. 觉察数量为原生活/身体/情绪记录；日常记录还含签到、旧抽卡和本人特质记录；特质只表示最后保存的一条资料，不补造历史。\n4. 仅原练习/聆听事件编号参与去重：同编号同内容计一次、冲突不纳统计并提示，原履历全部保留。内容编号和未知id不用于合并不同日子的资料。累计秒数用整数精确计算，超安全范围以精确十进制保存显示。\n5. 所有原字段、0/false/null/空值、失效素材引用、无日期资料保留原文详情；每页50可继续查看，账号scope/epoch保持隔离。\n6. 同轮修复旧growthEvents三层日期排序的undefined兼容，避免无日期旧练习导致返回我的页异常。\n7. 仅本地双端浏览器验证；藏语仍待母语审校，未做真实手机或完整跨设备同步。\n',encoding='utf-8',newline='\n')
result={'at':stamp.isoformat(),'pass':True,'receipt':sha(receipt),'priorMutableFiles':backups,'currentFiles':{name:sha(root/name) for name in backups},'bookSHA256s':{p.name:sha(p) for p in [proof/'东方智慧APP需求进度表-20261116.xlsx',proof/'东方智慧APP优化任务表_依据v1.0_20261112.xlsx']},'countsUnchanged':{'originalRequirements':98,'originalLocalStages':31}}
with (proof/'成长统计-交接与书表回填核验.json').open('xb') as f:f.write((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'pass':True,'handoffs':len(backups),'books':2,'originalRequirements':98,'originalLocalStages':31},ensure_ascii=False))
