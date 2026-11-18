"""Describe software gaps from explicit, passing local stage receipts only."""
import json


def remaining_software(root):
    out = root / '06_验证与后续工作'

    def passed(name):
        file = out / ('负责人优化建议-' + name + '-实施记录.json')
        if not file.is_file():
            return False
        return json.loads(file.read_text(encoding='utf-8-sig')).get('pass') is True

    local = [
        ('账号注销', '最终账号关闭与全会话撤销'),
        ('到期清理', '本方数据库实际到期清理执行器'),
        ('售后资金关联', '售后申请逐笔退款关联、关联纠错和资金匹配状态'),
        ('长期记忆', '本人长期记忆CRUD、关闭/撤回保护及新对话受控选取'),
        ('密钥引用', '原有AI和设备明文凭据改为服务端引用及受控迁移'),
    ]
    gaps = [description for module, description in local if not passed(module)]
    gaps += [
        '商品运营分类/规格、有限会员额度履约及单购期限的剩余适配',
        '重复扣款、未到账、无法恢复和退订的结构化支持分流',
        '可信支付事件收件、补偿队列及持久告警任务的剩余适配',
        '生产常驻调度、实际供应商/备份删除连接器及核验回执',
        '真实支付SDK验签、回调、主动查单、日账与差异处置及告警投递',
        '生产受管密钥、TLS/存储加密、后台MFA及安全/容量/容灾验收',
    ]
    return '；'.join(gaps)
