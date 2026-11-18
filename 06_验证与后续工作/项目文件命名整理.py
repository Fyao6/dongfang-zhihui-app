"""本轮交付文件命名整理。只改交接入口、当前说明和相对链接，不改业务构建。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '06_验证与后续工作'
STAMP = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S-%f')
NOW = datetime.now(timezone(timedelta(hours=8))).isoformat()
def sha(data): return hashlib.sha256(data).hexdigest()
def write_text(path, value): path.write_bytes(value.encode('utf-8'))
mapping = {
    '公司同步-先读我.txt': '项目说明.txt',
    '回家继续-先读我.txt': '06_验证与后续工作/历史交接说明-20261113.txt',
    '先读我.txt': '项目资料说明.txt',
    '公司同步-包内文件清单.json': '06_验证与后续工作/历史交付文件清单-20261116.json',
    '回家继续-包内文件清单.json': '06_验证与后续工作/历史交付文件清单-20261113.json',
    '06_验证与后续工作/公司同步-进度与记忆.json': '06_验证与后续工作/项目进度与记忆.json',
    '06_验证与后续工作/回家继续-进度与记忆.json': '06_验证与后续工作/历史进度与记忆-20261113.json',
    '06_验证与后续工作/回家继续-历史规则原文.txt': '06_验证与后续工作/历史工作规则原文.txt',
    '在家启动APP.cmd': '启动APP.cmd',
    'start-home.ps1': 'start-app.ps1',
}
for p in ROOT.rglob('*'):
    if not p.is_file() or any(x in p.parts for x in ('.git', 'node_modules', '.wrangler')): continue
    rel = p.relative_to(ROOT).as_posix()
    if rel in mapping: continue
    if any(x in p.name for x in ('回家', '在家', '公司同步', '先读我', 'start-home')):
        name = p.name.replace('回家继续', '历史交付').replace('在家', '本地').replace('公司同步', '项目').replace('先读我', '说明').replace('start-home', 'start-app')
        mapping[rel] = p.with_name(name).relative_to(ROOT).as_posix()
resuming = not (ROOT / '公司同步-先读我.txt').exists() and (ROOT / '项目说明.txt').exists()
if resuming:
    # 首轮在写JSON前停止；已完成改名和原字节保全，继续时不重复移动。
    existing = sorted(OUT.glob('交付命名整理前-*-AGENTS.md.原字节'))
    assert len(existing) == 1, '必须唯一定位本轮修改前快照'
    STAMP = existing[0].name.removeprefix('交付命名整理前-').removesuffix('-AGENTS.md.原字节')
    for p in OUT.iterdir():
        if p.name.startswith('交付命名整理前-'): continue
        oldname = p.name
        for a, b in (('项目-进度与记忆', '公司同步-进度与记忆'), ('项目-说明', '公司同步-先读我'), ('项目说明前存', '公司同步先读我前存'), ('项目说明原字节', '公司同步先读我原字节')):
            oldname = oldname.replace(a, b)
        if p.name in ('历史交付-生成精简接续包.py', '历史交付-打包当前项目.py', '历史交付-保存规则并重打精简包.py'):
            oldname = p.name.replace('历史交付-', '回家继续-', 1)
        if oldname != p.name: mapping['06_验证与后续工作/' + oldname] = p.relative_to(ROOT).as_posix()
if (OUT / '文件命名对照.json').exists(): raise RuntimeError('命名整理已执行，不覆盖原映射')
assert len(set(mapping.values())) == len(mapping)
for old, new in mapping.items():
    if resuming:
        assert not (ROOT / old).exists() and (ROOT / new).is_file(), (old, new)
    else:
        if not (ROOT / old).is_file(): raise FileNotFoundError(old)
        if (ROOT / new).exists(): raise FileExistsError(new)

records = []
for old, new in sorted(mapping.items()):
    p, target = ROOT / old, ROOT / new
    saved = OUT / f'交付命名整理前-{STAMP}-{target.name}.原字节'
    before = (saved if saved.exists() else target).read_bytes() if resuming else p.read_bytes()
    if not resuming:
        p.rename(target)
        assert target.read_bytes() == before
    records.append({'originalPath': old, 'currentPath': new, 'originalSHA256': sha(before), 'bytes': len(before), 'renamedBytesPreserved': True})

# 当前说明重写前保留原字节，历史记录只改文件名，不改内容。
snapshots = []
mutable = ['AGENTS.md', 'README.md', '项目说明.txt', '项目资料说明.txt', '交付包说明.txt', '启动APP.cmd',
           '06_验证与后续工作/项目进度与记忆.json', '06_验证与后续工作/成长统计-当前接续.json',
           '06_验证与后续工作/强制成长树-当前接续.json']
for rel in mutable:
    p = ROOT / rel
    if not p.is_file(): continue
    target = OUT / f'交付命名整理前-{STAMP}-{p.name}.原字节'
    if not target.exists(): target.write_bytes(p.read_bytes())
    snapshots.append({'source': rel, 'snapshot': target.relative_to(ROOT).as_posix(), 'sha256': sha(target.read_bytes())})

replacements = dict(mapping)
for old, new in mapping.items():
    if '/' in old and Path(old).name != Path(new).name:
        # 对根之外的同级文件名引用保持目录相对性。
        replacements.setdefault(Path(old).name, Path(new).name)
replacements.update({'06/公司同步-进度与记忆.json': '06/项目进度与记忆.json',
                     '06/回家继续-进度与记忆.json': '06/历史进度与记忆-20261113.json',
                     '06/回家继续-历史规则原文.txt': '06/历史工作规则原文.txt'})
def replace_refs(text):
    # 编码路径、Windows分隔符以及普通相对路径都逐项修正。
    for old, new in sorted(replacements.items(), key=lambda x: -len(x[0])):
        for a, b in ((quote(old, safe='/'), quote(new, safe='/')), (old.replace('/', '\\'), new.replace('/', '\\')), (old, new)):
            text = text.replace(a, b)
    return text
def replace_json(value):
    if isinstance(value, str): return replace_refs(value)
    if isinstance(value, list): return [replace_json(x) for x in value]
    if isinstance(value, dict): return {k: replace_json(v) for k, v in value.items()}
    return value

changed_refs = []
for p in [*ROOT.glob('*.html'), *ROOT.glob('*.txt'), ROOT / 'AGENTS.md', ROOT / 'README.md', * (ROOT / '05_后台与研发说明').glob('*.txt'), * (ROOT / '05_后台与研发说明').glob('*.md')]:
    if not p.is_file(): continue
    before = p.read_bytes()
    try: text = before.decode('utf-8-sig')
    except UnicodeDecodeError: continue
    after = replace_refs(text)
    if after == text: continue
    if p.relative_to(ROOT).as_posix() not in mutable:
        target = OUT / f'交付命名整理前-{STAMP}-{p.name}.原字节'
        target.write_bytes(before)
        snapshots.append({'source': p.relative_to(ROOT).as_posix(), 'snapshot': target.relative_to(ROOT).as_posix(), 'sha256': sha(before)})
    write_text(p, after)
    changed_refs.append(p.relative_to(ROOT).as_posix())

for rel in ('06_验证与后续工作/项目进度与记忆.json', '06_验证与后续工作/成长统计-当前接续.json', '06_验证与后续工作/强制成长树-当前接续.json'):
    p = ROOT / rel
    data = replace_json(json.loads(p.read_text(encoding='utf-8-sig')))
    data['currentDeliveryPreparation'] = {'savedAt': NOW, 'scope': '中性命名、交接资料更新、按规则打包和同步既有GitHub；无新增业务实施或业务复测',
        'namingMap': '06_验证与后续工作/文件命名对照.json', 'currentGuide': '项目说明.txt',
        'githubSyncStatus': 'pending', 'packageStatus': 'pending',
        'historicalStatements': '其余已有未推送/未打包及旧阶段描述为相应保存时点；本轮结果以新的GitHub同步与交付校验记录为准',
        'meetingBackground': '已阅读2026-11-16会议纪要供理解团队背景；不将纪要建议视为本轮实施、改名、公开私有资料或正式服务上线授权'}
    write_text(p, json.dumps(data, ensure_ascii=False, indent=2) + '\n')

guide = '''东方智慧APP 项目说明
更新时间：{now}

本轮工作：按用户规则修正交接文件的场景化命名、保存当前进度、生成交付包，并同步既有GitHub仓库。未开展新的业务开发或业务回归。GitHub与打包当前正在办理，完成结果见06目录新增的同步记录和交付校验记录，不能据本说明预先认定成功。

当前进度
原98项需求共有72项含本地或沙箱证据（包括部分覆盖），26项不在此计数内；原台账状态为进行中70、待资料16、待验收9、待实施3。累计31个本地验证阶段。这些数字不等于98项全部完成，也不等于正式服务验收。
三项追加需求单独留证：官网双端各60完整+6专项；成长足迹统计双端各60完整+6专项；每日进入提醒双端各60完整+12专项，不虚增原98项或31阶段。
成长记录按最新2026-11-18要求采用东方智慧原创成长足迹：自然周/月/年/累计、练习与聆听两色堆叠柱、觉察回看和完整履历。保留原日期、全部字段和未知资料；默认计划与APP陪伴账本不计入练习时长。旧唯一分叉树仅代表历史实现。
每日首次进入提醒按本人服务端会员资格判断；沙箱权益明示“测试，未实际扣款”。真实模型、正式支付、生产服务、专业规则和内容授权、藏语母语、用户视觉、实机及跨设备同步仍分别待验，不用本地结果代替。

使用
Windows双击“启动APP.cmd”，调用根“start-app.ps1”，使用明确的06隔离预览库，在 http://127.0.0.1:8881/experience 查看APP，/admin查看后台。需要Python3.11+与时区数据。该库仅本地交付携带，不公开上传GitHub。
离线APP：03_当前APP/东方智慧-首页体验R4.html；评审查看页：03_当前APP/发给负责人-东方智慧首页R4.html。官网：根官网.html，服务路径/official。项目资料入口：打开这里.html；原需求与参考：01/02；当前源码：04；研发说明：05；验证与接续：06。
未安装的Node依赖按04既有package-lock和构建说明恢复，不能把机器缓存视为源码。不要复用生产库或未知旧测试state。

接续依据
先读AGENTS.md、本文件、06_验证与后续工作/项目进度与记忆.json，再按业务范围阅读原需求、历史工作规则原文、实际源码和冻结收据。文件命名历史见06_验证与后续工作/文件命名对照.json。旧报告中的路径按对照追溯，不回写冻结收据，也不要直接运行旧阶段接入或打包helper。
成长统计：06_验证与后续工作/成长统计-本地验收记录.json；稳定源码与构建：成长统计-兼容修复后稳定构建记录.json。
官网：06_验证与后续工作/官网接入-本地验收只读复核.json。
每日提醒：06_验证与后续工作/每日进入提醒-本地验收记录.json。
本地可靠性：06_验证与后续工作/负责人优化建议-当前产品可靠性-实施记录.json。选定负载使用每请求新TCP，不能声称原keepalive故障已经解决；备份后已确认写入的未恢复差异保留，不能声称零丢失或正式RPO/RTO达标。

交付规则
ZIP在唯一项目根生成，直接收录根入口和00—08用途目录，不加项目包装层。排除Git内部、依赖/运行缓存、旧压缩包/部署归档、06历史截图录像、安装器、环境原值、凭据、会话及其它数据库。本次仅携带8881隔离预览库的一致SQLite backup快照；浏览器localStorage未自动导出。原资料在本机保持，不把省略的历史媒体说成随包携带。GitHub公开内容继续排除私有数据库和环境等本地资料。
文件/目录采用用途明确的中性名称，不再按工作地点、出行或作者主观称呼命名。历史冻结内容保留原字节，文件名改动通过逐项SHA-256对照追溯。

会议纪要已作为团队思路与背景阅读；本轮不改产品名、不扩展业务需求、不纳入私有附件原文，也不据此启用真实服务。
'''.format(now=NOW)
write_text(ROOT / '项目说明.txt', guide)
write_text(ROOT / '交付包说明.txt', guide)
readme = '''# 东方智慧 APP

当前交付保留31个本地验证阶段。原98项中72项含本地或沙箱证据（含部分覆盖）；台账为进行中70、待资料16、待验收9、待实施3。正式服务、专业内容、用户视觉与实机仍按各项证据另验，不能据此认定需求全部完成。

新增官网、成长足迹统计、每日进入提醒已分别完成本地验证。成长记录采用2026-11-18确定的原创统计布局，练习与聆听时长取真实已保存记录，完整履历及未知字段保留；旧唯一树结构为历史实现。

请先读[项目说明](项目说明.txt)、[工作规则](AGENTS.md)和[当前进度与记忆](06_验证与后续工作/项目进度与记忆.json)。[命名对照](06_验证与后续工作/文件命名对照.json)记录历史文件名与中性名称，冻结旧报告按此追溯。

## 查看与启动

Windows运行[启动APP.cmd](启动APP.cmd)，调用根[start-app.ps1](start-app.ps1)，使用明确的本地隔离预览库。打开[APP](http://127.0.0.1:8881/experience)、[后台](http://127.0.0.1:8881/admin)或[官网](http://127.0.0.1:8881/official)。需Python3.11+及tzdata。GitHub不携带本地数据库、环境和凭据；从公开仓库启动时需按现有后端说明显式选择自己的新库，不猜用原库。

离线查看[独立APP](03_当前APP/东方智慧-首页体验R4.html)、[评审页面](03_当前APP/发给负责人-东方智慧首页R4.html)、[官网](官网.html)及[项目资料入口](打开这里.html)。账号、上传、后台和联网服务需要后端运行。

## 源码与验证

源码在04_研发源码，实际可查看构建在03_当前APP，说明在05_后台与研发说明，原需求在01/02，验证在06。构建按现有r4/build.py、Cloud prepare.py及package-lock恢复依赖和运行，不携带node_modules或运行缓存。

- [成长统计验收](06_验证与后续工作/成长统计-本地验收记录.json)：双端各60完整+6专项。
- [官网本地验收](06_验证与后续工作/官网接入-本地验收只读复核.json)：双端各60完整+6专项。
- [每日提醒验收](06_验证与后续工作/每日进入提醒-本地验收记录.json)：双端各60完整+12专项。

真实支付与模型、正式内容授权、专业样本、藏语母语、目标设备与跨设备同步仍待相应验收。测试会员提示明确未实际扣款，服务端判断资格。本地通过不等于生产服务上线。

## GitHub

复用[Fyao6/dongfang-zhihui-app](https://github.com/Fyao6/dongfang-zhihui-app)。[Pages静态预览](https://fyao6.github.io/dongfang-zhihui-app/)及[评审模式](https://fyao6.github.io/dongfang-zhihui-app/?view=review)沿用既有地址；静态预览不运行账号、数据库或真实支付。此次同步和打包尚在办理，最终提交与校验结果以06目录本轮新增记录为准。
'''
write_text(ROOT / 'README.md', readme)

ag = (ROOT / 'AGENTS.md').read_text(encoding='utf-8-sig')
heading, rest = ag.split('\n', 1)
addition = '''
## 2026-11-18 交付命名与本轮授权（最新）

用户要求按既定规则打包并同步现有GitHub，并明确不再出现按地点、出行或作者视角命名的交接文件和包装层。此后文件和目录使用用途清晰的中性名称，例如“项目说明”“项目进度与记忆”“历史工作规则原文”“启动APP”；不得再次生成已淘汰的场景化名称。当前入口为根项目说明.txt、项目资料说明.txt、启动APP.cmd和start-app.ps1，最新记忆为06_验证与后续工作/项目进度与记忆.json。
本轮只整理命名、当前交接资料、打包和同步GitHub，不开展新业务或无关业务复测。原03/04业务源码和构建、两份需求XLSX、冻结收据内容保持原字节；历史文件路径改动由06_验证与后续工作/文件命名对照.json逐项保留旧路径、新路径和SHA-256。旧报告及一次性helper内部旧路径按对照追溯，不自动重跑过期helper。当前先读取AGENTS.md、项目说明.txt、项目进度与记忆.json，再按模块阅读历史规则与原需求。
用户提供的2026-11-16会议纪要仅供理解团队背景，用户明确“让你了解了解”；不据此变更产品名、扩展本轮业务、公开私有纪要或启用真实服务。下文各阶段的未推送/未打包描述保留其保存时点，本轮同步与打包状态以新交付记录为准。
'''
write_text(ROOT / 'AGENTS.md', heading + '\n' + addition + '\n' + rest)
cmd = (ROOT / '启动APP.cmd').read_text(encoding='utf-8-sig').replace('start-home.ps1', 'start-app.ps1')
write_text(ROOT / '启动APP.cmd', cmd)

for rec in records:
    data = (ROOT / rec['currentPath']).read_bytes()
    rec['currentSHA256'] = sha(data)
    rec['contentChangedAsCurrentEntry'] = rec['currentSHA256'] != rec['originalSHA256']
    if rec['contentChangedAsCurrentEntry']:
        rec['snapshot'] = next((x['snapshot'] for x in snapshots if x['source'] == rec['currentPath']), None)
result = {'schemaVersion': 1, 'savedAt': NOW, 'scope': '文件与当前入口中性命名整理，不改业务源码构建或冻结历史内容',
          'records': records, 'beforeEditSnapshots': snapshots, 'currentReferenceFilesUpdated': changed_refs,
          'historicalReferencePolicy': '冻结历史正文及一次性helper保留原字节，内部旧路径按本表解析。不能直接重跑过期helper；当前打包使用本轮项目交付打包.py。',
          'unchangedBusinessReference': '03_当前APP/功能与使用说明-R4.txt中的历史根说明名按本表对应项目资料说明.txt，03/04全部字节保持。',
          'githubSyncStatus': 'pending', 'packageStatus': 'pending'}
write_text(OUT / '文件命名对照.json', json.dumps(result, ensure_ascii=False, indent=2) + '\n')
bad = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ('.git','node_modules','.wrangler')) and any(x in p.name for x in ('回家','在家','先读我','公司同步','start-home'))]
assert not bad, bad
print(json.dumps({'renamed': len(records), 'snapshots': len(snapshots), 'updatedReferenceFiles': changed_refs, 'forbiddenFilenames': bad}, ensure_ascii=False))
