from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import Counter
import hashlib, json, subprocess
from 负责人优化建议剩余工作 import remaining_software

P = Path(__file__).resolve().parent.parent
D = P / '06_验证与后续工作'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
tasks = json.loads((D / '负责人优化建议-任务拆解.json').read_text(encoding='utf-8-sig'))
t = next(x for x in tasks if x['id'] == 'X03')
t['status'] = '进行中'
t['implementation_note'] = '本轮已列APP/源码SHA、模块冻结证据、接口说明、环境变量名和无密钥交接/恢复步骤；原库与8880/8879未动，未重打完整ZIP。正式发布、数据库迁移/付款事实补偿及生产回滚演练尚未完成。'
proofs = []
for f in sorted(D.glob('负责人优化建议-*实施记录.json')):
    r = json.loads(f.read_text(encoding='utf-8-sig'))
    if r.get('pass') is not True:
        continue
    refs = []
    for label, item in r.get('verification', {}).items():
        if isinstance(item, dict) and item.get('path'):
            target = P / item['path']
            assert target.is_file(), (f.name, item['path'])
            reference = {'label': label, **item}
            if item.get('sha256') and sha(target) != item['sha256']:
                correction_file = D / '负责人优化建议-只读对账-归档哈希更正.json'
                correction = json.loads(correction_file.read_text(encoding='utf-8-sig'))
                assert correction['pass'] is True and correction['allOriginalEvidenceBytesPreserved'] is True
                assert correction['originalRecord'] == f.relative_to(P).as_posix()
                assert correction['originalRecordSha256'] == sha(f)
                candidates = [c for c in correction['corrections'] if c['path'] == item['path']]
                assert len(candidates) == 1
                entry = candidates[0]
                assert entry['originalRecordedSha256'] == item['sha256']
                assert entry['actualFileSha256'] == sha(target)
                assert entry['matchesOriginalCommitBytes'] is True
                assert hashlib.sha256(target.read_bytes().replace(b'\r\n', b'\n')).hexdigest() == entry['lfNormalizedSha256'] == item['sha256']
                reference['originalReceiptSha256'] = item['sha256']
                reference['sha256'] = sha(target)
                reference['archiveHashCorrection'] = {'path': correction_file.relative_to(P).as_posix(), 'sha256': sha(correction_file), 'reason': correction['reason']}
            refs.append(reference)
    proofs.append({'module': r.get('module', f.stem), 'path': f.relative_to(P).as_posix(), 'sha256': sha(f), 'scope': r.get('scope', ''), 'verification': refs})
artifacts = ['03_当前APP/东方智慧-首页体验R4.html', '03_当前APP/发给负责人-东方智慧首页R4.html', '03_当前APP/计时后台-开发联调.html', '04_研发源码/app/cloud/generated/experience.html']
for name in artifacts:
    assert (P / name).is_file(), name
report = {
    'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'head_before_handoff': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=P, text=True).strip(),
    'task_counts': dict(Counter(x['status'] for x in tasks)), 'tasks': len(tasks),
    'artifacts': {n: sha(P / n) for n in artifacts}, 'frozen_stages': proofs,
    'environment_names_only': {'Python': ['--port', '--db', 'provider.secretRef（后台配置指定的环境变量名）'], 'Cloud': ['DB（D1绑定）', 'BUCKET（R2绑定）', 'DEMO_ADMIN_HASH（仅隔离联调）', 'provider.secretRef（对应服务端secret绑定名）']},
    'production_release': False, 'real_model_or_payment_verification': False,
}
(D / '负责人优化建议-本轮交接清单.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['东方智慧APP负责人v1.0优化实施——本轮交接与恢复说明', report['at_beijing'], '',
    '交付范围：当前本机/H5与Cloud本地适配软件、98项任务表、逐段来源、分模块冻结报告及截图。不是生产上线收据。',
    '当前任务：'+ '；'.join(k+' '+str(v) for k,v in report['task_counts'].items()),
    'APP入口：03_当前APP/东方智慧-首页体验R4.html；负责人查看页与后台同目录。在线功能须配套本人测试服务，file打开仅能验证离线范围。',
    '源码：04_研发源码/app/r4（前端/Python后端）；04_研发源码/app/cloud（Cloud适配）。构建SHA见交接清单JSON。',
    '对账原记录的四个哈希因LF/CRLF计算口径差异有追加更正；四报告与0792e22原提交字节逐一相同。旧收据不改，实际文件哈希与核对依据见06/负责人优化建议-只读对账-归档哈希更正.json；交接清单同时列原声明和更正依据。', '',
    '已冻结的模块范围与证据：']
for r in proofs:
    lines += [r['module']+'：'+r['scope'], '证据：'+r['path']]
lines += ['', '接口/管理员操作：各模块在06目录同名前缀的接口与接入说明/接入助手，源码API路由为最终依据。后台分佣/对账需管理员或当前员工另授财务权限；普通运营、老师和用户没有默认财务权限。',
    '测试账号：实际专项每次创建新随机合成账号，结束后不复用、不公开密码；隔离Cloud全量使用测试库初始化脚本且不输出凭据。没有把测试身份当成真实业务账号。',
    '环境信息：Python使用--port与明确的--db；Cloud使用DB/BUCKET绑定。新AI网关仅存secretRef名称并在服务端注入；DEMO_ADMIN_HASH只供隔离联调，不能作生产凭据。这里没有真密钥或用户/付款原始凭证。',
    '所有新增正式收费/真实AI/正式抽卡/售后等启用条件以各模块后台真实配置为准，默认关闭项不得为了演示伪装已审定。', '',
    '恢复步骤与界限：',
    '1. 先记录构建SHA、配置版本、数据库迁移和本次变更范围，备份并在独立恢复库检查。原有8880/8879与原数据库本轮不重绑、不清空。',
    '2. 页面异常先停用对应沙箱入口；可从本地提交查明该模块变更，在独立工作副本恢复代码并重新构建验证。不要对当前共享目录直接reset --hard或覆盖其他未提交工作。',
    '3. 账务异常先冻结新写和自动派生，保留原订单、付款/退款事件与权益事实。代码回退不等于数据库回退；禁止用旧整库覆盖上线后的已承认付款或库存变化。',
    '4. 按原事件/订单ID幂等补偿并复核会员、佣金和库存。没有真实渠道连接时，不标记银行到账、供应商删除或正式续费已停。',
    '5. 本轮隔离SQLite恢复演练明确保留一笔备份后写入未恢复的事实；没有执行生产RDS/Cloud SQL故障切换、目标地区网络或真实付款恢复。正式RPO/RTO仍未验收。', '',
    '未完成的软件：'+remaining_software(P)+'。',
    '未齐资料：老师规则/30个标准样本、实际AI服务及条款、商户/发行地区/商品渠道ID、价格权益及分佣文档、正式商品/36卡素材授权、视频审定与多语校对、目标国家容量和预算。详见任务表I/K列与阻塞证据说明。',
    '官方资料：S01—S26相关章节逐个复核记录见06/负责人优化建议-26项官方资料复核.txt；AWS计算器未读到交互内容，两云未产出实际报价，另行更新规则文档尚未收到。',
    '本轮未公网部署、未购买资源、未重打完整ZIP；X03保留进行中，正式发布回滚/完整上线交接仍需真实环境演练。']
(P / '05_后台与研发说明/负责人优化建议-本轮交接与恢复说明.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
t = next(x for x in tasks if x['id'] == 'X03')
t['status'] = '进行中'
t['implementation_note'] = '本轮已列APP/源码SHA、模块冻结证据、接口说明、环境变量名和无密钥交接/恢复步骤；原库与8880/8879未动，未重打完整ZIP。正式发布、数据库迁移/付款事实补偿及生产回滚演练尚未完成。'
(D / '负责人优化建议-任务拆解.json').write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'stages': len(proofs), 'artifacts': len(artifacts), 'productionRelease': False}, ensure_ascii=False))
