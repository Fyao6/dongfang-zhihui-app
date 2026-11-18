"""Update current handoff/task text from frozen PAY08 evidence; preserve prior bytes."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-支付回调'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
stamp = datetime.now(timezone(timedelta(hours=8)))
tag = stamp.strftime('%Y%m%d-%H%M%S')
receipt_path = OUT / (PREFIX+'-实施记录.json')
receipt = load(receipt_path)
assert receipt['pass'] and receipt['stage'] == 21
assert load(OUT/(PREFIX+'-完整回归构建核对.json'))['pass']
for relative, expected in {**receipt['source_hashes'], **receipt['build_hashes']}.items():
    assert sha(ROOT/relative) == expected, relative

backups = {}


def backup(path):
    destination = OUT / (PREFIX+'回填前-'+tag+'-'+path.name)
    assert not destination.exists()
    destination.write_bytes(path.read_bytes())
    backups[path.relative_to(ROOT).as_posix()] = {'path': destination.relative_to(ROOT).as_posix(), 'sha256': sha(destination)}


def save(path, value):
    backup(path)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


scope = ('PAY08通用收件本地已验证：仅沙箱HMAC测试适配、提交后202、事件/交易双层去重、'
         '独立消费请求、租约恢复、有限退避和人工重试、数字/实物沙箱事务应用、后台列表详情与真实横滑。'
         '双端各60项完整、16项专项、31项交易兼容及4项补充检查通过；真实渠道验签、常驻调度和会员回调仍待接入。')
entry = {'path': receipt_path.relative_to(ROOT).as_posix(), 'sha256': sha(receipt_path),
         'module': PREFIX, 'pass': True, 'at': receipt['at_beijing'], 'scope': receipt['scope'],
         'limitations': receipt['limitations'],
         'verification': [{'name': name, **value} for name, value in receipt['verification'].items()]}

task_path = OUT/'负责人优化建议-任务拆解.json'
tasks = load(task_path)
original_tasks = copy.deepcopy(tasks)
task = next(r for r in tasks if r['id'] == 'PAY08')
assert task['status'] == '待实施'
task.update(status='进行中', progressNote=scope, localEvidence=[entry['path']],
            remainingSoftware=['正式渠道签名/验单与事件规范适配', '常驻消费者调度及运行监控', '会员回调事务适配'])
assert all(before == after for before, after in zip(original_tasks, tasks) if before['id'] != 'PAY08')
counts = dict(Counter(r['status'] for r in tasks))
assert counts == {'进行中':68, '待资料':16, '待验收':9, '待实施':5}
save(task_path, tasks)

audit_path = OUT/'负责人优化建议-98项最终覆盖审计.json'
audit = load(audit_path)
before_rows = copy.deepcopy(audit['rows'])
row = next(r for r in audit['rows'] if r['id'] == 'PAY08')
row.update(task_table_status_at_audit='进行中', declaredCurrentScope=scope, stage=scope,
    resolvedSoftware=['验签与字段限制通过后提交持久收件再202，事件/交易去重和冲突审计。',
                      '独立管理员消费、30秒租约、有限退避、累计最多5次及人工重试。',
                      '数字/实物沙箱订单、库存、权益、结果账和收件状态原子应用；后台桌面/360窄屏可操作。'],
    softwareNotImplemented=['真实渠道SDK验签/验单与平台事件适配尚未实现，当前HMAC明确只用于本地fixture。',
                            '常驻消费者、自动唤醒和监控告警连接器未部署；当前由独立管理员请求消费。',
                            '会员回调事务适配仍待接入，通知保留待人工核查。'],
    externalInputs=['正式商户/渠道协议、受控凭据引用、平台事件资料、运行与调度身份和部署授权。'],
    productionOrAcceptanceGates=['真实渠道通知重放、验签、验单及生产调度可靠性待联调。',
                                 'PAY09/PAY13迟到支付库存/权益补偿和真实资金结果另行实施；本轮未假报成功。'],
    softwareAssessmentBasis='需求表PAY08及P449—P451；冻结双端60/16/31/4与最终构建核对。',
    evidence=[entry], additionalEvidence=[{'path': '06_验证与后续工作/'+PREFIX+'-完整回归构建核对.json',
                                         'sha256': sha(OUT/(PREFIX+'-完整回归构建核对.json'))}])
assert all(before == after for before, after in zip(before_rows, audit['rows']) if before['id'] != 'PAY08')
audit.update(verifiedLocalStages=21, updatedTaskIds=['PAY08'], currentTaskStatusCounts=counts,
             latestUpdateAt=stamp.isoformat())
audit['evidenceCatalog'][receipt_path.name] = entry
audit['scopedLocalStageEvidence'].append(entry)
save(audit_path, audit)

text_path = OUT/'负责人优化建议-98项最终覆盖审计.txt'
backup(text_path)
lines = ['98 项当前覆盖与剩余工作', '21 个本地验证阶段。正式服务与生产验收见各项边界。', '']
for r in audit['rows']:
    lines += [f"{r['id']} | {r['task_table_status_at_audit']} | {r['title']}",
              '原文段落 '+', '.join(r['source_ids']), r['declaredCurrentScope']]
    for key, title in [('softwareNotImplemented','剩余软件'),('externalInputs','外部输入'),('productionOrAcceptanceGates','生产或验收')]:
        if r.get(key): lines += [title]+['- '+v for v in r[key]]
    lines += ['证据 '+v['path'] for v in r.get('evidence', [])]
    lines += ['']
text_path.write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))

memory_path = OUT/'公司同步-进度与记忆.json'
memory = load(memory_path)
memory['scope'] = '沿公司同步目录接续，追加需求表PAY08本地交付与冻结证据；原公司同步ZIP/清单保留冻结时点，本轮未重打包或发布。'
memory['development']['verifiedLocalStages'] = 21
memory['development']['stages'].append({'stage':21, 'id':'PAY08', 'module':'支付回调可靠接收',
    'implementation':scope, 'receipt':entry['path'], 'receiptSHA256':entry['sha256'],
    'python':{'regression':60,'special':16,'tradeCompatibility':31,'visualAndDigitalEntitlements':4},
    'localCloud':{'regression':60,'special':16,'tradeCompatibility':31,'visualAndDigitalEntitlements':4},
    'open':'真实渠道验签/验单、常驻调度、会员回调和迟到补偿尚未验收。'})
memory['development']['currentSourcesSHA256'].update(receipt['source_hashes'])
memory['development']['currentBuildsSHA256'].update(receipt['build_hashes'])
memory['development']['fullRegressionBuildIdentityAddendum'] = row['additionalEvidence'][0]
memory['progress'].update(rowsWithLocalOrSandboxEvidenceIncludingPartial=66, otherRows=32,
                          statusCounts=counts, note='包含部分覆盖的本地/沙箱证据；21个本地阶段为另一口径，正式服务按各条待验边界。')
for area in memory['progress']['evidenceByArea']:
    if area[0] == '支付与客服': area[2] = 18
memory['progress']['workbookSha256'] = sha(OUT/'东方智慧APP需求进度表-20261116.xlsx')
memory['github']['localChangesAfterPublishedCommit'] = 'PAY08及本轮表格/交接文件仅在本目录更新，未推送或发布；公开仓库与Pages保持此前公司同步版本。'
memory['next']['localSoftware'] = ['按需求表继续PAY05渠道能力矩阵、PAY09异常恢复及PAY10/PAY13迟到库存/权益补偿；PAY08通用本地部分已验证，不重复重做。',
    '准备真实渠道验签/验单和会员回调适配、常驻消费者与监控；正式资料未齐继续保持门禁。'] + memory['next']['localSoftware'][2:]
memory['packaging']['latestLocalUpdate'] = {'at':stamp.isoformat(), 'module':'PAY08', 'zipRepacked':False, 'originalPackageManifestUnchanged':True}
memory['savedAtBeijing'] = stamp.isoformat()
save(memory_path, memory)

agents = ROOT/'AGENTS.md'
backup(agents)
content = agents.read_text(encoding='utf-8')
marker = '## 2026-11-16 公司同步交接'
note = ('## 2026-11-16 PAY08恢复开发与本地交付\n\n'
        '用户已明确授权继续，并要求严格按需求表推进交付。PAY08异步回调可靠接收已完成通用本地实现，累计21个本地验证阶段；'
        'Python和本地Cloud分别通过完整60、专项16、原交易兼容31及补充视觉/数字权益4项。'
        '源码、03可查看后台和Cloud构建已更新，收据见06_验证与后续工作/负责人优化建议-支付回调-实施记录.json，完整回归另有12项构建哈希核对。\n\n'
        '两份当前需求表同步PAY08为进行中：98项中66项有本地或沙箱证据（含部分覆盖），其余32项未计入；'
        '进行中68、待资料16、待验收9、待实施5。真实渠道验签/验单、常驻调度、会员回调和迟到支付补偿仍待实施或联调。'
        '本轮未推送GitHub/Pages、未发布正式服务、未重打ZIP；下方公司同步20阶段和65项口径是本轮前的交接时点。\n\n')
assert content.count(marker) == 1
agents.write_bytes(content.replace(marker, note+marker).encode('utf-8'))

guide = ROOT/'公司同步-先读我.txt'
backup(guide)
content = guide.read_text(encoding='utf-8')
notice = ('\n本目录继续开发更新（2026-11-16）\n'
          '已按需求表PAY08追加通用回调可靠接收，本地累计21阶段；双端60/16/31/4通过。当前负责人表66项含部分本地证据，32项未计入，状态进行中68/待资料16/待验收9/待实施5。'
          '源码、03与Cloud构建和两份需求表已同步更新，正式渠道及常驻调度仍待接入。下文“本次同步”描述原ZIP冻结时点；该旧ZIP与包内清单未重写，本轮改动尚未推送或重打包。\n')
guide.write_bytes((content.split('\n',2)[0]+'\n'+content.split('\n',2)[1]+'\n'+notice+'\n'+content.split('\n',2)[2]).encode('utf-8'))

readme = ROOT/'README.md'
backup(readme)
content = readme.read_text(encoding='utf-8')
update = ('2026-11-16 本目录新增需求表 PAY08 支付回调可靠接收的本地交付：累计21阶段，双端完整60、专项16、交易兼容31及补充4项通过。'
          '后台在“商城与订单→支付回调收件箱”。真实渠道和常驻调度待接入；本轮未推送或更新公开预览，原ZIP保持旧快照。'
          '详见 [PAY08实施记录](06_验证与后续工作/负责人优化建议-支付回调-实施记录.json) 与 [使用和验收说明](05_后台与研发说明/支付回调收件与验收说明.txt)。\n\n')
head, rest = content.split('\n',1)
readme.write_bytes((head+'\n\n'+update+rest.lstrip('\n')).encode('utf-8'))

check = {'at_beijing':stamp.isoformat(), 'pass':True, 'taskId':'PAY08', 'verifiedLocalStages':21,
         'other97TaskRowsUnchanged':True, 'other97AuditRowsUnchanged':True, 'statusCounts':counts,
         'rowsWithLocalOrSandboxEvidenceIncludingPartial':66, 'notCounted':32, 'backups':backups,
         'receiptSHA256':entry['sha256'], 'updatedFilesSHA256':{p.relative_to(ROOT).as_posix():sha(p)
          for p in [task_path,audit_path,text_path,memory_path,agents,guide,readme]}}
target = OUT/(PREFIX+'-任务及交接回填核验.json')
assert not target.exists()
target.write_bytes((json.dumps(check,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'pass':True,'statusCounts':counts,'receiptSHA256':entry['sha256'],'report':str(target)},ensure_ascii=False))
