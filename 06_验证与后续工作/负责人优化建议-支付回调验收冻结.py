"""Freeze PAY08 only after final actual dual-backend gates pass. No service starts."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
PREFIX = '负责人优化建议-支付回调'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def write(path, data):
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if path.exists():
        assert path.read_bytes() == raw, 'Do not rewrite an existing frozen receipt: ' + path.name
    else:
        path.write_bytes(raw)


def freeze():
    stamp = datetime.now(timezone(timedelta(hours=8))).isoformat()
    specs = [
        ('Python全量', PREFIX+'-本轮全量回归结果.json', 60),
        ('Cloud全量', PREFIX+'-公网适配全量回归结果.json', 60),
        ('Python专项', PREFIX+'专项-python.json', 16),
        ('Cloud专项', PREFIX+'专项-cloud.json', 16),
        ('Python交易兼容', PREFIX+'交易兼容-python.json', 31),
        ('Cloud交易兼容', PREFIX+'交易兼容-cloud.json', 31),
        ('Python补充视觉及数字权益', PREFIX+'补充视觉-python.json', 4),
        ('Cloud补充视觉及数字权益', PREFIX+'补充视觉-cloud.json', 4),
    ]
    verification = {}
    captures = {}
    for label, name, expected in specs:
        path = OUT / name
        raw = read(name)
        result = raw.get('latest', raw)
        results = result['results']
        assert result.get('pass') is True, (label, 'not passed')
        assert len(results) == expected and all(r.get('pass') is True for r in results), (label, 'gate count differs')
        assert result.get('failed', 0) == 0, label
        assert result.get('identityUnchanged', True), label
        identities = [result.get('callbackSources', {})]
        identities += list(result.get('identity', {}).values())
        for identities_part in identities:
            if not isinstance(identities_part, dict):
                continue
            for relative, recorded in identities_part.items():
                assert sha(ROOT / relative) == recorded, (label, 'source/build changed', relative)
        for filename in result.get('captures', []):
            image = OUT / filename
            assert image.is_file(), filename
            captures[str(image.relative_to(ROOT)).replace('\\', '/')] = sha(image)
        verification[label] = {'path': str(path.relative_to(ROOT)).replace('\\', '/'),
            'sha256': sha(path), 'passed': expected, 'failed': 0,
            'at': result.get('at'), 'runId': result.get('runId'),
            'scope': result.get('scope'),
            'recordedIdentityChecked': any(bool(part) for part in identities),
            'finalBuildBinding': 'Final local rebuild completed before this run; current source/build hashes frozen below.'}

    source_names = [
        '04_研发源码/app/r4/backend/payment_callbacks.py',
        '04_研发源码/app/r4/backend/server.py',
        '04_研发源码/app/cloud/lib/payment-callbacks.ts',
        '04_研发源码/app/cloud/lib/eastern-api.ts',
        '04_研发源码/app/r4/payment-callback-admin.js',
        '04_研发源码/app/r4/commerce-admin.js',
        '04_研发源码/app/r4/build.py', '04_研发源码/app/cloud/prepare.py',
        '06_验证与后续工作/全量回归.cjs',
        '06_验证与后续工作/公网适配全量回归.cjs',
        '06_验证与后续工作/'+PREFIX+'专项.cjs',
        '06_验证与后续工作/'+PREFIX+'验收启动.cjs',
        '06_验证与后续工作/'+PREFIX+'Python测试服务.py',
        '06_验证与后续工作/'+PREFIX+'Cloud测试服务.ts',
        '06_验证与后续工作/'+PREFIX+'补充视觉.cjs',
        '06_验证与后续工作/'+PREFIX+'验收冻结.py',
    ]
    builds = [
        '03_当前APP/东方智慧-首页体验R4.html',
        '03_当前APP/计时后台-开发联调.html',
        '03_当前APP/发给负责人-东方智慧首页R4.html',
        '03_当前APP/创作者中心.html',
        '04_研发源码/app/cloud/generated/experience.html',
        '04_研发源码/app/cloud/generated/admin.html',
        '04_研发源码/app/cloud/dist/server/index.js',
    ]
    limits = [
        '签名验证只针对本轮明确命名的sandbox HMAC fixture；Apple/Google/Stripe/PayPal等真实渠道验签、验单及收银尚未接入。',
        '收件先持久化后202；消费由独立管理员process请求触发。未部署常驻worker/cron、自动唤醒或外部告警，不宣称生产异步调度已完成。',
        '仅数字/实物沙箱订单安全应用。会员回调保留membership_requires_adapter，继续沿用原会员沙箱付款入口，未虚报会员回调接通。',
        '过期、关闭、已退款、金额币种冲突等进人工核查；未实现PAY09/PAY13迟到支付补库存、真实退款或资金补偿。',
        'Python执行过实际进程重启恢复；Cloud验证跨请求D1持久化和过期租约恢复，未执行worker进程重启或生产容灾演练。',
        '后台桌面及360窄屏使用原生点击和真实横滑验证；本机浏览器不代表iOS/Android实机、母语审校或生产服务验收。',
    ]
    data = {'at_beijing': stamp, 'module': PREFIX, 'taskId': 'PAY08', 'stage': 21,
        'pass': True, 'status': 'local-software-verified-real-channel-pending',
        'requirement': {'sourceIds': ['P449', 'P450', 'P451'],
            'title': '异步回调可靠接收',
            'acceptance': '同事件/同交易重复通知只处理一次且有接收记录。',
            'progressWorkbook': '06_验证与后续工作/东方智慧APP需求进度表-20261116.xlsx',
            'progressRange': '98项明细!A77:H77',
            'nextAtHandoff': '先做通用接收记录、幂等去重和重试，用合成事件验证。'},
        'scope': '默认关闭的沙箱HMAC签名适配、最小字段白名单与大小/时戳验证、提交后202、事件及交易双层去重和冲突审计、持久化inbox、独立消费/租约/有限退避和人工重试、数字实物沙箱事务应用、后台列表/详情/处理记录与窄屏横滑。',
        'production': {'productionEnabled': False, 'realProviderTested': False,
            'actualFundsMoved': False, 'automaticallyScheduled': False,
            'originalDatabaseUsed': False, 'sandboxFixtureOnly': True},
        'verification': verification,
        'source_hashes': {n: sha(ROOT/n) for n in source_names},
        'build_hashes': {n: sha(ROOT/n) for n in builds},
        'visualEvidenceSHA256': captures, 'limitations': limits,
        'failureHistory': [
            '首轮Python专项错误JSON的测试传输被Playwright重新编码，签名字节不符；改为Buffer逐字节发送后重跑，原失败run保留。',
            'Python初次完整脚本只选56项；原56范围报告另存，最终显式bazi-stage=4共60项通过。',
            'Cloud首轮57/3为隔离fixture的/app review与设备canary配置缺口；未放宽产品门禁，原失败报告与截图另存，修夹具后重跑。',
            '窄屏长编号和日期折行可读性问题已修为合理列宽与真实横滑；修复前报告/截图保留，最终两端在新构建上复验。'],
        'frozenBytes': 'UTF-8 LF; write_bytes; historical receipts and archives preserved'}
    receipt = OUT / (PREFIX+'-实施记录.json')
    write(receipt, data)
    print(json.dumps({'receipt': str(receipt), 'sha256': sha(receipt), 'passed': True,
        'stage': 21, 'gates': {k:v['passed'] for k,v in verification.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    freeze()
