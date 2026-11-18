"""Only prepare a new 06 draft. Never apply changes to tasks/template/audit.

All five immutable final records must pass before --check-ready can succeed.
Historical source/build hashes remain historical: they are NOT compared to
later integrated source. Use an explicitly selected last integration receipt.
"""
import argparse
import copy
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '06_验证与后续工作'
TASKS = OUT / '负责人优化建议-任务拆解.json'
TEMPLATE = OUT / '负责人优化建议-98项覆盖审计更新模板.json'
AUDIT = OUT / '负责人优化建议-98项最终覆盖审计.json'
SOURCE = ROOT / '02_需求与设计参考/负责人优化建议-逐段原文.json'
WRITER = OUT / '负责人优化建议-98项覆盖审计更新.py'
DEFAULT_DRAFT = OUT / '负责人优化建议-五模块任务回填草案.json'
RECORDS = {
    'retention': '负责人优化建议-到期清理-实施记录.json',
    'closure': '负责人优化建议-账号注销-实施记录.json',
    'caseFinance': '负责人优化建议-售后资金关联-实施记录.json',
    'secretReferences': '负责人优化建议-密钥引用-实施记录.json',
    'memory': '负责人优化建议-长期记忆-实施记录.json',
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def rel(p):
    return p.resolve().relative_to(ROOT.resolve()).as_posix()


def load_validator():
    # Execute declarations only; no import cache directory and no writer main.
    ns = {'__file__': str(WRITER), '__name__': '_five_module_evidence_validator'}
    exec(compile(WRITER.read_text(encoding='utf-8-sig'), str(WRITER), 'exec'), ns)
    return ns


def frozen_auxiliary_refs(value):
    """Only explicit frozen evidence links, never source/build/test identity maps."""
    found = []
    if isinstance(value, list):
        for item in value:
            found.extend(frozen_auxiliary_refs(item))
    elif isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            found.append(value)
        for key, item in value.items():
            if key not in ('input', 'inputSha256', 'source_hashes', 'sources', 'tests',
                           'final_identity', 'identity', 'cloud_build_hashes'):
                found.extend(frozen_auxiliary_refs(item))
    return found


def record_gate(key, validator):
    p = OUT / RECORDS[key]
    gate = {'key': key, 'path': rel(p), 'state': 'pending', 'validated': False}
    if not p.is_file():
        gate['reason'] = 'final-record-not-present; independent source/tests are not completion'
        return gate
    gate['sha256'] = sha(p)
    try:
        validator['final_record'](p, key)
        receipt = read(p)
        refs = validator['references'](receipt, p)
        component_refs = []
        for path, value in receipt.get('components', {}).items():
            if isinstance(value, dict) and isinstance(value.get('sha256'), str):
                entry = {**value, 'path': path}
                checked = validator['references']({'verification': {path: entry}}, p)
                assert len(checked) == 1 and checked[0]['validation']['validated'], ('component evidence failed', path)
                component_refs.extend(checked)
        scope = receipt.get('scope')
        assert scope is not None and scope != '' and scope != {}, 'missing explicit frozen scope'
        auxiliary = []
        for field in ('screenshots', 'visual_review_evidence'):
            for ref in frozen_auxiliary_refs(receipt.get(field)):
                target = (ROOT / ref['path']).resolve()
                assert target.is_relative_to(OUT.resolve()), 'frozen evidence outside 06'
                assert target.is_file() and sha(target) == ref['sha256'], ('frozen auxiliary mismatch', rel(target))
                auxiliary.append({'path': rel(target), 'sha256': ref['sha256']})
        # A valid final module needs both backends' full regression and actual
        # integrated specifics. Unit/VM records alone cannot satisfy this gate.
        full = [r for r in refs if r.get('declaredPassed') == 60]
        actual = [r for r in refs if any(w in r['name'].lower() for w in ('actual', '专项'))
                  and not any(w in r['name'].lower() for w in ('内存', 'unit', '组件', 'vm'))]
        assert len(full) >= 2, 'missing dual 60 full regression snapshots'
        assert len(actual) >= 2, 'missing dual integrated actual specifics'
        assert sha(p) == gate['sha256'], 'record changed while reading'
        gate.update(state='frozen-pass', validated=True, originalPass=True, scope=scope,
                    limitations=receipt.get('limitations', receipt.get('limits', [])),
                    references=refs, auxiliaryFrozenReferences=auxiliary,
                    componentFrozenReferences=component_refs,
                    historicalStageIdentityNotComparedToCurrentFiles=True)
    except (AssertionError, OSError, ValueError, KeyError, TypeError) as exc:
        gate['reason'] = str(exc)
    return gate


def proposal(keys, resolved, missing, external, production, note, boundary=None):
    return {'requiresFrozenRecords': keys,
            'resolvedSoftwareAfterGate': resolved,
            'softwareNotImplementedAfterGate': missing,
            'externalInputsAfterGate': external,
            'productionGatesAfterGate': production,
            'proposedImplementationNoteAfterGate': note,
            'proposedCurrentSoftwareBoundaryAfterGate': boundary or {}}


def proposals():
    privacy_external = ['正式用途/接收方/地区/政策与各数据域保留期限由项目方和供应商确认；null不编天数。']
    privacy_production = ['生产TLS/静态数据与备份加密、受管身份MFA/IAM、真实供应商及备份清理、定时执行身份/部署仍须单独实证。']
    finance_external = ['正式售后审批、退款/运费/扣费及完成政策；真实支付、仓储/承运、客服资料与授权。']
    finance_production = ['逐case本地sandbox匹配不是实际退款到账；真实渠道仍关闭。不得将金融匹配自动等同物流完成或正式售后完结。']
    finance_resolved = ['按管理员明确逐项批准目标，将原applied sandbox refund事件的可靠逐项容量与本case幂等关联；追加撤销关联释放净容量，unknown/null与明确0分开。',
                        '关联/冲销不新退款、不改原订单资金/库存/权益/会员/佣金或物流；原新summary与本人隔离、并发容量/版本和关闭/降权栅栏以最终专项scope为准。']
    finance_missing = ['真实渠道验单/退款/拒付/到账与仓储承运核验连接器未完成。',
                       '按正式政策自动/人工完结整个售后case与真实资金结果的状态衔接仍需实现/验收；当前金融匹配和物流分别展示。']
    p = {}
    p['PR03'] = proposal(['memory'],
        ['本人主动维护的长期记忆CRUD/清空/导出、分类与版本/epoch/tombstone，独立于会话保存；开关关闭后已有本人条目仍可管理，新增与AI外发受授权限制。',
         '新对话须显式选择记忆IDs；服务端fresh读取授权/owner/version/epoch/active，发送及回复存储再次核验；关闭或撤回不读旧记忆，不从聊天自动推断。'],
        ['未部署向量索引/自动检索；如今后启用须另实现其授权、删除及外部处理连接器，不能将本人显式选择CRUD称向量服务。'],
        privacy_external, privacy_production + ['真实提供方、真实新对话的受控记忆使用与撤回全链路生产验收仍待完成。'],
        '已接入本人主动维护的长期记忆与显式选择受控使用，默认关闭，与会话保存独立；版本/epoch/撤回/删除及两端实际门禁见长期记忆最终收据。未部署向量服务，真实供应商/生产全链路待验。')
    p['PR04'] = proposal(['closure', 'memory', 'retention'],
        ['本人当前密码验证+二次确认的实际本地账号关闭，权威清理仅已列六scope/AI输出及后续memory、全session撤销/旧口令失效/closed写入栅栏；最后有效管理员保护，关闭回执可重放。',
         '本人记录/会话/记忆正文的单删/清空/导出及关联job输出清理；金融/履约/源审计和最小额度防重保留并明确计数回执。'],
        ['供应商/备份/未来向量及外部缓存删除的实际执行、确认、失败重试连接器仍未完成；pending-confirmation不等于已清。',
         '第三方订阅取消仍需官方渠道处理；本地闭户不代替真实第三方退订。',
         '用户身份骨架、设备连接、公开作品和既有消息保留；未发布素材/creator草稿等其他数据域尚未证明已纳入清理，须逐域核对政策及实际执行范围，不能称全部本方个人数据已删除。'],
        privacy_external + ['财务/身份归属/审计留存例外及外部删除能力与授权。'], privacy_production,
        '本人当前密码和二次确认后可实际停用本地账号、原子撤销全部服务端session；权威清理限已列六scope、AI输出及后续记忆，不是全域擦除。用户骨架/设备连接/公开作品/既有消息/金融等保留，creator草稿等其他域尚未证明纳入；供应商/备份及第三方续费仍pending/未代取消。')
    p['PR05'] = proposal(['retention', 'memory'],
        ['期限明确配置后，按服务器fixed asOf、真实后续写入版本/nonce和保护起点，预览/分批实际执行/幂等回执/可续跑；旧age-unknown默认跳过，不猜天数。',
         '记录/会话/计时历史/活动/设备测量/卡片已具真实清理；活跃计时排除，stale复用原45s租约；记忆采用独立nullable期限及自身epoch，金融/额度/源审计不删。'],
        ['生产常驻调度、受管执行身份、备份/WAL/供应商清理与核验回执连接器仍未部署/完成；默认关闭或prepared scheduled入口不是正在运行的cron。'],
        privacy_external + ['财务/安全日志/设备连接及防重数据的正式期限和留存目的。'], privacy_production,
        '实际到期清理执行器已集成：服务器固定时点、真实写入跟踪、旧龄未知跳过、独立期限、分批可续跑与无正文回执；记忆独立期限以长期记忆最终记录为准。默认关闭，生产cron/备份/供应商清理及正式天数未验。')
    secret_resolved = ['AI/设备密钥使用受控EW_AI_*/EW_DEVICE_*服务端进程env或Worker显式绑定引用；状态脱敏，新设置禁止原值、无plain fallback。',
                       '本人有效管理员明确批准的旧值匹配/CAS原位迁移、环境/用途/引用校验与关闭/降权即时门禁；重定向不得携Authorization越过已绑定接收方。']
    secret_missing = ['远程受管Secrets/KMS读取与轮换/吊销、IAM凭据身份连接器仍未实现/部署；当前env resolver不是云KMS。',
                      '后台受管身份/MFA、生产可信代理/Cookie策略和受管敏感访问日志/告警连接器尚未完成。']
    p['PR06'] = proposal(['secretReferences'], secret_resolved, secret_missing,
        ['生产身份租户/MFA政策、云IAM/Secrets/KMS、域名入口、正式迁移/轮换及日志政策。'], privacy_production,
        'AI/设备凭据已支持受控服务端env引用、禁止新plain与无plain fallback，旧值须明确CAS迁移；关闭/降权及接收方重定向边界经最终门禁验证。远程KMS/轮换、MFA、生产TLS/静态加密和日志连接器仍未完成/部署。')
    p['SV04'] = proposal(['retention', 'closure', 'secretReferences'],
        secret_resolved[:1] + ['随机fresh测试环境、本地到期清理执行器及实际账号停用栅栏已验证；不是生产部署证明。'],
        secret_missing + ['生产数据库适配/迁移、私网与连接重建/故障恢复编排、生产备份/PITR、常驻cron/监控/告警和可回滚发布预检连接器仍缺。'],
        ['云账号/区域/网络/身份/域名、告警责任人、RPO/RTO、正式保留和部署授权。'], privacy_production + ['目标生产私网、隔离、多可用区恢复、PITR与付款事实保全仍待实际演练。'],
        '本地随机隔离、受控env密钥引用/CAS迁移、到期清理执行器和账号停用已具软件实证；不再将这些称纯配置。远程KMS/MFA、生产私网/TLS/备份PITR/常驻调度/告警及回滚恢复编排仍未完成。')
    p['AI03'] = proposal(['secretReferences', 'memory', 'closure'],
        ['既有统一网关/场景路由与逐provider receipt继续有效；新增受控env凭据解析、closed拦截、显式选择记忆的fresh授权/version/epoch快照；不默认同题双发。'],
        ['真实Claude/紫微代理和本方DeepSeek生产推理的协议/延迟/费用/权益及故障演练仍需适配联调，不能以本机mock传输认定两通道真实接通。'] + secret_missing[:1],
        ['真实接收方/模型/endpoint/地区/政策、服务凭据和本方GPU运行环境及额度。'],
        ['真实两通道与移动网络联调、生产部署与最小输入/撤回/费用验收。'],
        '统一场景网关已支持受控env凭据、closed栅栏及本人显式记忆选择的fresh授权与版本校验。真实Claude/DeepSeek及生产Secrets/KMS/移动联调未完成，不声称真实两通道可用。')
    for ident in ('SH03', 'SH04', 'SH05'):
        extra = ['商品规格/多变体结构与对应SKU选择、成交快照及后台维护仍需补齐；当前每product唯一SKU不能覆盖正式多规格要求。'] if ident in ('SH04', 'SH05') else []
        p[ident] = proposal(['caseFinance'], finance_resolved, finance_missing + extra,
                            finance_external, finance_production,
                            '既有售后申请/受理/物流/收货/防重复入库保持；新增逐case明确批准目标、原applied sandbox退款逐项容量关联及追加撤销，未知/0/部分匹配分别显示。未新动资金、未自动完结物流/售后；真实渠道/仓储政策仍待齐。',
                            {'moneySource': 'original-commerce-payment-events', 'allocationScope': 'explicit-case-item-net-allocation',
                             'actualFundsMovedByAllocation': False, 'productionEnabled': False,
                             'sandboxMatchedIsRealFundsConfirmation': False, 'logisticsCompletionIndependent': True})
    p['SH02'] = proposal([], ['既有图文/金额/库存/配送/退款条款及成交快照继续以统一交易收据为准。'],
        ['多规格/多变体商品模型、可选项与SKU对应、后台维护及订单原规格快照仍需软件实现；不能只归为首批商品资料未到。',
         '正式可用支付方式/优惠税运规则适配仍缺，不能用sandbox按钮替代。'],
        ['首批真实规格/SKU、价格币种、图片授权及税运规则。'], ['正式商品与真实渠道端到端验收。'],
        '图文/金额/库存配送与条款快照已有；多规格/多变体模型、SKU选项和成交规格快照仍是软件缺口，另有正式商品/价格/渠道资料及联调待完成。')
    p['SH06'] = proposal([], ['既有内容ID/无地址数字单、独立单购权益及退款冲正保持。'],
        ['有限有效期/有限次数的独立数字权益需按明确政策补齐期限或消耗账、到期/并发消费/恢复与最终访问门禁；现commerce remaining主要随退款量变化，不等于已实现有限额度履约。'],
        ['作品授权、内容ID、有效期/使用次数与转移/退款政策。'], ['正式数字内容与真实验单解锁/到期/消耗验收。'],
        '内容ID关联、数字无地址、单购权益及退款冲正已有。独立数字商品有限期限/次数的履约与消耗门禁仍需软件实现，不能将remaining退款余量称使用额度；真实解锁待渠道。')
    p['PAY10'] = proposal([], ['原统一sandbox付款/权益一次发放与退款联动保持，会员/分佣补接仍按已有收据。'],
        ['真实渠道回调与订单/权益补偿队列适配尚未完成；有限次数/期限数字权益的消费及最终门禁另见SH06。'],
        ['各渠道验单/通知协议、正式权益规则。'], ['真实重复回调/失败补偿与最终一致性演练。'],
        '沙箱订单/权益原子发放、幂等与退款调整已验证；真实回调和补偿仍缺，独立有限次数/期限履约不能由退款remaining字段代替。')
    p['PAY15'] = proposal(['caseFinance'], ['本人原订单/金额/状态及逐case原沙箱退款关联进度可查，跨账号隔离。'],
        ['正式渠道交易凭证/收据/适用票据的验证、关联、本人查询下载与重放适配仍未实现；本地退款关联不是票据。'],
        ['渠道票据格式/税务主体与适用规则。'], ['真实订单/凭证/票据及账号边界验收。'],
        '本人订单与沙箱退款及逐case关联可查；未将sandbox匹配称银行到账。渠道收据/发票等适用票据的实际验证关联与查询仍未接。')
    p['PAY16'] = proposal(['caseFinance'], ['原只读沙箱内部一致性/异常与CSV保持；新增case金融关联不改原账。'],
        ['真实渠道日账/手续费/银行到账接入、按日一致性与差异处理工作流仍未实现；当前手动sandbox检查不能称财务每日对账。'],
        ['正式账单/费用/结算格式、账户与日界线/税务差异政策。'], ['真实渠道和银行事实、日任务、差异处置与权限追溯验收。'],
        '现有只读沙箱内部账本一致性/异常面板与100次原账hash验证保持；case关联仅本地分配。真实渠道按日对账、手续费/银行到账与差异工作流仍未实现。')
    p['PAY18'] = proposal([], ['原后台手动沙箱差异/待核/未覆盖、CSV，不自动补账不外发告警。'],
        ['真实支付/回调积压/拒付等事件采集、常驻监测及告警投递/去重/重试/确认连接器仍未实现。'],
        ['渠道事件、告警接收端/责任人及阈值升级政策。'], ['真实异常注入、投递确认与订单事件定位演练。'],
        '手动沙箱内部异常可查；真实事件采集/常驻监测/外部告警投递与确认仍缺，不能以未发现记录称0失败。')
    p['PAY19'] = proposal(['caseFinance'], finance_resolved,
        ['重复扣款/未到账/无法恢复/退订四类结构化本人支持申请、订单/原事件定位、后台处理队列与处理回执仍未实现；现售后入口和case退款关联不能覆盖四类问题。'] + finance_missing,
        finance_external + ['真实客服联系方式、工单责任人与四类问题处理政策。'], finance_production + ['四类问题均须实际可达查询和客服路径，未知联系方式不造假。'],
        '新增逐case原沙箱退款明确分配与纠错，保留售后独立物流。重复扣款/未到账/无法恢复/退订四类结构化自助与后台工单队列仍是软件缺口；真实客服与资金渠道另待齐。')
    return p


def make_draft(last_record=None):
    protected = [TASKS, TEMPLATE, AUDIT, SOURCE, WRITER]
    before = {rel(p): sha(p) for p in protected}
    tasks, template, source = read(TASKS), read(TEMPLATE), read(SOURCE)
    ids = [t['id'] for t in tasks]
    assert len(ids) == 98 and len(set(ids)) == 98
    paragraph_map = {p['id']: p for p in source['paragraphs']}
    docx = ROOT / source['source']
    assert sha(docx) == source['sha256'], 'original DOCX no longer matches paragraph extraction'
    validator = load_validator()
    gates = {key: record_gate(key, validator) for key in RECORDS}
    last = None
    if last_record:
        path = last_record.resolve() if last_record.is_absolute() else (ROOT / last_record).resolve()
        matches = [g for g in gates.values() if (ROOT / g['path']).resolve() == path]
        assert len(matches) == 1, 'last integrated receipt must be one of the five named final records'
        last = copy.deepcopy(matches[0])
    all_ready = all(g['validated'] for g in gates.values())
    ready = bool(all_ready and last and last['validated'])
    changes = proposals()
    rows = []
    for task in tasks:
        row = {'id': task['id'], 'currentTaskUnmodified': copy.deepcopy(task)}
        if task['id'] in changes:
            change = copy.deepcopy(changes[task['id']])
            missing = [k for k in change['requiresFrozenRecords'] if not gates[k]['validated']]
            row.update(proposal=change, proposalState='ready-for-root-review' if ready else 'pending-five-final-gates',
                       missingRelevantFinalRecords=missing,
                       originalParagraphs=[copy.deepcopy(paragraph_map[s]) for s in task['source_ids']],
                       existingTemplateOverride=copy.deepcopy(template['rowOverrides'].get(task['id'], {})))
            # These are proposals only. Preserve every live task field verbatim.
            proposed = copy.deepcopy(task)
            proposed['implementation_note'] = change['proposedImplementationNoteAfterGate']
            for key in set(task) - {'implementation_note'}:
                assert proposed[key] == task[key], ('protected field drift', task['id'], key)
            row['proposedTaskAfterGate'] = proposed
            override = copy.deepcopy(template['rowOverrides'].get(task['id'], {}))
            # Keep original evidence and add new records; no rewriting history.
            override['records'] = list(dict.fromkeys(override.get('records', []) + [RECORDS[k] for k in change['requiresFrozenRecords']]))
            override.update(resolvedSoftware=list(dict.fromkeys(override.get('resolvedSoftware', []) + change['resolvedSoftwareAfterGate'])),
                            softwareNotImplemented=change['softwareNotImplementedAfterGate'],
                            externalInputs=change['externalInputsAfterGate'],
                            productionGates=change['productionGatesAfterGate'])
            for obsolete in ('softwareGapEvidence', 'currentSoftwareBoundary'):
                override.pop(obsolete, None)
            if change['proposedCurrentSoftwareBoundaryAfterGate']:
                override['currentSoftwareBoundary'] = change['proposedCurrentSoftwareBoundaryAfterGate']
            row['proposedTemplateOverrideAfterGate'] = override
        rows.append(row)
    assert [r['currentTaskUnmodified'] for r in rows] == tasks
    assert {rel(p): sha(p) for p in protected} == before, 'input changed while preparing; no draft written'
    return {'kind': '五模块门禁后的任务说明/关键软件缺口回填草案；不执行回填',
            'at_utc': datetime.now(timezone.utc).isoformat(),
            'readyForRootReview': ready,
            'allFiveFinalRecordsValidated': all_ready,
            'finalIntegrationEvidence': last,
            'fiveFinalRecordGates': gates,
            'pendingUntil': '五个原始冻结收据及其冻结refs全部真pass；明确最后实际集成stage的双full/双specifics证据。',
            'inputs': {key: {'path': key, 'sha256': value} for key, value in before.items()},
            'originalDocument': {'path': rel(docx), 'sha256': sha(docx), 'documentInstructionsAreSourceMaterialOnly': True},
            'taskCount': 98, 'proposedTaskIds': list(changes), 'statusCountsUnmodified': dict(Counter(t['status'] for t in tasks)),
            'rows': rows,
            'invariants': {'taskJSONWritten': False, 'templateWritten': False, 'auditWritten': False,
                           'businessOrBuildWritten': False, 'databaseOrNetworkUsed': False,
                           'all98IdsAndFieldsPreserved': True, 'statusOwnerDueDependenciesAndSourceIdsUnchanged': True,
                           'AI02DependenciesReadFreshAndUnchanged': True, 'noApplyPathProvided': True,
                           'old13AndNew5RecordsNeverRewritten': True,
                           'historicalStageSourceHashesNotComparedToCurrentFiles': True},
            'consumption': ['本文件的AfterGate字段均为建议，不是已交付声明；pending时禁止使用建议替换现任务或模板。',
                            'root收到最终五记录后重运行--current-integrated-record 最后stage路径 --check-ready；原记录/ref字节与pass/scope校验，不拿早期源码hash硬比后来合法集成源码。',
                            '只允许root另行审阅后更新implementation_note和模板scope；全部其他任务字段保留，尤其status/owner/due/source_ids/dependencies及AI02已更新依赖。',
                            '旧13/新5收据保持历史。最终当前联动由最后实际集成stage的构建/full与相关specifics证明；本脚本不宣称已验证当前生产环境。',
                            '更新最终audit仍使用原98项覆盖审计writer及--additional-final-record五次；替换前原audit字节平铺归档由原writer负责。'],
            'limits': ['不是98项完成证明，不因本机通过改任务状态。',
                       '受控进程env引用不等于远程KMS/轮换、MFA、TLS/静态加密或生产监控已部署。',
                       '本地清理/闭户/记忆不等于备份/供应商/向量已清；生产cron及各正式期限未知仍需落实。',
                       '原沙箱退款逐case匹配不等于发生真实资金移动、真实到账或整个售后完结。',
                       '商品多规格、独立有限期限/次数权益、PAY19四类结构化支持仍是软件剩余，不能全部归给外部资料。']}


def self_test():
    validator = load_validator()
    check = validator['reference_validation']
    base = {'exists': True, 'frozenShaMatches': True, 'declaredPassed': 60,
            'observedGate': {'pass': True, 'passed': 60, 'failed': 0, 'lists': {}}}
    assert check(base)['validated']
    bad = copy.deepcopy(base); bad['observedGate']['failed'] = 1
    assert not check(bad)['validated']
    bad = copy.deepcopy(base); bad['observedGate'].pop('pass')
    assert not check(bad)['validated']
    bad = copy.deepcopy(base); bad['frozenShaMatches'] = False
    assert not check(bad)['validated']
    assert not check({'exists': False})['validated']
    assert 'PR03' in proposals() and 'PAY19' in proposals()
    print(json.dumps({'selfTest': True, 'checks': 6, 'pass': True, 'writes': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-draft', action='store_true', help='Create a NEW flat draft only, refusing overwrite')
    parser.add_argument('--output', type=Path, default=DEFAULT_DRAFT)
    parser.add_argument('--current-integrated-record', type=Path)
    parser.add_argument('--check-ready', action='store_true', help='Fail closed unless all five frozen records and final integration receipt pass')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        assert not args.write_draft and not args.check_ready
        self_test(); return
    draft = make_draft(args.current_integrated_record)
    if args.check_ready:
        assert draft['readyForRootReview'], 'PENDING: five final frozen gates and explicit last integrated receipt are required; no apply/write'
    if args.write_draft:
        dest = args.output.resolve() if args.output.is_absolute() else (ROOT / args.output).resolve()
        assert dest.parent == OUT.resolve() and dest.suffix == '.json', 'only a new flat 06 JSON draft is permitted'
        assert dest not in (TASKS.resolve(), TEMPLATE.resolve(), AUDIT.resolve()), 'protected destination'
        with dest.open('xb') as stream:
            stream.write((json.dumps(draft, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        print(json.dumps({'path': rel(dest), 'sha256': sha(dest), 'readyForRootReview': draft['readyForRootReview'],
                          'frozenRecordCount': sum(g['validated'] for g in draft['fiveFinalRecordGates'].values()),
                          'protectedFilesWritten': False}, ensure_ascii=False))
    else:
        print(json.dumps({'mode': 'read-only', 'readyForRootReview': draft['readyForRootReview'],
                          'recordGates': {k: {'state': v['state'], 'reason': v.get('reason')} for k, v in draft['fiveFinalRecordGates'].items()},
                          'tasks': 98, 'proposals': len(draft['proposedTaskIds']), 'protectedFilesWritten': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
