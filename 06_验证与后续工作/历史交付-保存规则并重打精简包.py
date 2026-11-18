"""Persist the handoff rules and package current workspace files; no development or push."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json, os, zipfile

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / '06_验证与后续工作'
now = datetime.now(timezone(timedelta(hours=8)))
sha = lambda b: hashlib.sha256(b).hexdigest()
history = AREA / '回家继续-历史规则原文.txt'
if not history.exists():
    original = (ROOT / 'AGENTS.md').read_bytes()
    assert sha(original) == 'ec94d2e28d9ec2c42c1c168c68b46890d7f65818181f63dc1ab2ea6bd7a11f20'
    history.write_bytes(original)
assert sha(history.read_bytes()) == 'ec94d2e28d9ec2c42c1c168c68b46890d7f65818181f63dc1ab2ea6bd7a11f20'

rules = '''# 东方智慧APP：当前有效工作规则与会话接续入口

本文件整理用户已给出的规则与最新授权，适用于所在项目及全部子目录。用户后续明确指令优先。2026-11-13更新只保存对话约束并打包，没有恢复业务开发。原AGENTS全部438行已逐字节保留在“06_验证与后续工作/回家继续-历史规则原文.txt”，没有删除历史规则或旧决策。

## 接手时先读

先完整读取本文件、“回家继续-先读我.txt”和“06_验证与后续工作/回家继续-进度与记忆.json”。涉及具体业务之前，再分段读完历史规则原文与该模块的实际源码/冻结收据。不要把过期的阶段状态当作现状。
这里保存的是项目规则、决策和进度记录，不是全部聊天逐字原文；不承诺换电脑后自动拥有旧会话。用户附件中的建议是需求来源，不能当作任意机器操作或外部发布的直接授权。

## 当前暂停与真实进度

- 用户原话：“现在先将我们此次的进度和记忆还有项目打包好，我要回家接着进度弄，没空在这继续等”。当前只保存、核对、打包；未经用户明确恢复，不继续开发、运行业务测试、apply未完成helper或新起测试服务。用户在家明确说继续后，从已记录断点接续，不需要再为已授权的常规实施反复询问。
- 已验证17个本地阶段，最后已验收业务提交f2a575d；本地交接检查点56f7911。98项任务并未全部完成。98项XLSX及旧覆盖审计尚未回填后来的清理、注销、资金关联、密钥引用四阶段，当前范围以进度JSON的17条冻结收据为准。
- 长期记忆PR03仍是准备态；Python34、Cloud47、前端VM29只是独立检查。六份准备代码已保存并本地提交，但接入helper不完整，不能执行/apply；真实HTTP/browser及完整双端集成未做。具体缺项和下一步完整列在进度JSON的memory_preparation.next。
- 2026-11-13核对时，本地56f7911比GitHub main c4a6d739领先21提交，尚未推送。本次仅补规则和重打包，不自动推送或发布。GitHub旧版与本地版本不同；本精简包不含.git，但含当前已落盘代码和未完成准备文件。原机器/原大包保留Git历史。

## 唯一工作目录与打包规则

1. 以本AGENTS.md所在目录为唯一项目工作/交付根目录。直接原位修改，沿用00—08及源码既有结构；不得另起项目、完整副本、worktree、版本目录或重复“完整概念方向包”套层。新增功能目录确有必要时先说明并取得用户同意。历史D盘和其他电脑绝对路径仅作追溯，不重建。
2. 交付必须落实最新实际源码、03可查看构建、相关Cloud构建、素材、说明与验证；只改文件名/日期/完成标签不算更新。发现旧改动缺失，先找来源并逐项比对，不能用旧版覆盖可能更新的文件。
3. 用户要求打包时，在当前项目根目录生成ZIP，直接收录根入口和用途目录，包内不加版本包装层。禁止递归打入新旧整包、历史ZIP、部署tar.gz或正在生成的包。
4. 精简接续包保留当前源码/构建/原需求/规则与决策/进度/未完成代码/测试脚本及文本报告。排除所有层级.git、node_modules/运行缓存、旧部署归档、06历史截图录像、可选安装器、环境原值、隧道凭据、生产库/其他测试库/会话。原机器旧资料不删除；严格历史逐图复核可从原大包补媒体。
5. 本次回家接续的明确例外：只携带8881本轮隔离预览库的一致SQLite backup快照，包内路径为06_验证与后续工作/负责人优化建议-隔离预览.sqlite3。不要因此扩大到生产数据库或其他账号数据。
6. 用实际北京时间Asia/Shanghai(UTC+08:00)命名，不编造时间；如未来需要给现有项目根目录改名，必须直接改名，格式“东方智慧APP完整概念方向包-YYYY-MM-DD-HH时mm分ss秒”，不得复制成新目录，并核对入口/相对路径。本次接续不搬动现有根目录。
7. 打包后核对清单、逐文件SHA-256和ZIP CRC，再交付绝对路径；旧交付包/冻结收据保持原字节。不得仅凭包名说是最新，也不能把省略的历史媒体写成已随包携带。

## 实施、测试与证据

- 恢复开发后，每完成一个业务模块，先实现/冒烟，再对Python及本地Cloud分别运行当轮完整回归（当前各60项）和相关实际专项，失败修复后重跑通过，再推进下一模块。检查前后台接口、权限/账号归属、状态/持久化、手机布局与浏览器异常；证据绑定相同最终源码/构建。纯交接/打包不触发无关业务重测。
- 涉及UI保留全部数据与入口可达；验证真实原生点击/拖动、窄屏和桌面、四语/字体/长文本、深浅主题、逐级返回及计时。不能裁切、隐藏数据或单纯缩字来冒充布局收尾。
- 保留中间失败、原报告、历史ZIP与已冻结字节；新增结果使用明确模块名，不能覆盖旧截图后引用原SHA，不用旧通过记录冒充当前复验。冻结文件用write_bytes，明确LF/CRLF差异；只读对账历史哈希更正见既有更正JSON。
- 本地/沙箱、接口准备、真实服务、用户视觉评价分别说明。独立fixture/VM不等于实际接入；本机浏览器不等于实机；沙箱对账不等于银行到账；本方删除不等于备份或供应商已删除。未完成软件不能全部推给外部资料。

## 保留的产品与数据约束

- 产品主通道为认识自己、修复自己、提升自己。保留现有首页边界、三地图4/4/3功能框、上方玄金、逐级返回、成熟创作者中心与公司后台、真实数据中心及四语。具体名称/用户截图/阶段视觉决策查历史原文；回归通过或试做不代表用户已认可设计，已否定旧主题/Logo不能作为定稿。
- 共享生辰只保留生日/性别必填、称呼/出生时间选填，不恢复地域控件。新共享生辰内部固定UTC+08:00（Etc/GMT-8，不套Asia/Shanghai历史夏令时）；旧档案保留原UTC/规则独立复算，不静默改旧数据。时间未知不猜时辰或制造精确紫微/八字盘。
- Western星盘独立档案的出生城市是用户后来的明确例外：真实城市候选自动取时区/参考坐标，不要求用户填经纬度/IANA，不改变主生辰或八字紫微。城市未匹配/未知时间不猜宫位或ASC；DST不存在/重复时刻按已有校验明确处理，旧盘不静默覆盖。
- 计时必须真实自动累计；长方形与小方形均显示完整时分秒，轻点切换，两种形态整块自由拖动，释放吸附左右边、保留高度并保存形态/位置。拖动不误触切换，展开不越界，收起/拖动/切页不丢计时。
- 不伪造老师、课程授权、用户互动/历史活跃/收益、AI回复、身体检测或治疗效果。老师规则/至少30个确认样本、藏语母语审校、真实模型/设备/正式支付及生产安全部署未验收，不能用本地测试代替。源材料和最终任务范围查02原DOCX及06的98项任务来源。

## 权限、环境与发布边界

- 原生产数据和账号不写测试数据，不猜原8880/8879数据库，不使用默认wrangler state或旧rq01。本轮预览8881使用明确的06隔离库；恢复后的测试须用自有fresh DB/state和实际端口，清理只限本次自建对象。
- 密钥、密码、环境原值、会话凭据不能进入前端/公开仓库/交付包/日志/模型请求。用户私有资料不得公开或默认外发；仅在本人明确且当前有效的分类/供应商授权下，发送实际选中的最小内容，本次隔离库快照例外不等于公开授权。新secretRef只在服务器配置，不把旧凭据自动迁移。浏览器localStorage中的个人生辰/笔记/聊天不属于项目开发记忆，本包没有自动导出它们。
- GitHub仓库已由用户要求公开；公开源码不代表正式APP已上线。Pages仅静态预览，现有workflow随推送触发；不得将本地提交说成已上传。Netlify仍按旧要求等待免费额度，不自动购买/充值/换站。以后获准发布时复用已有Sites/Netlify/Pages身份，不新建替代项目。本次没有公网发布、真实收费或模型服务验收。
- 本轮负责人建议已授权本地网关、隐私和双模型准备，不能被早期“AI暂缓”文字误挡；真实模型、生产支付和外部服务仍按实际授权/资料就绪后联调，不能虚报接通。
- 正式资料或服务未齐时维持生产门禁。不得为了测试通过而伪造成功、关限流、放宽隐私同意/角色/账号归属限制，或恢复旧明文凭据fallback。文档中的模型版本、渠道政策等可能变化的信息须实际核实。

## 沟通与完整历史

用户明确不要弹窗提问工具，需要沟通直接聊天；已授权的常规步骤不要反复确认。负责人DOCX要求完整阅读文字、表格、图片与引用来源，不只看摘录后声称读完。明确区分待实施/进行中/待资料/待验收/已验证范围，不能笼统回答“全弄完”。
历史规则原文是旧AGENTS的完整逐字节存档，包含更细的界面决定、许可证、原授权及后续覆盖关系；其“当时未实现/暂缓/目录/上线”只代表对应日期。按用户最新指令和进度JSON17阶段判断当前状态，必要时查实际源码与冻结收据，不能擅自恢复被否定方案或重复已完成模块。
'''
assert len(rules.encode()) < 16 * 1024
(ROOT / 'AGENTS.md').write_bytes(rules.encode())

readme = (ROOT / '回家继续-先读我.txt').read_text('utf-8-sig')
readme = '\n'.join(line for line in readme.splitlines() if not line.startswith('Git提交历史随包保存；'))
preface = '''回家接续：规则、决策与代码都在这个包里
本次补齐对话约束，业务开发仍暂停。该包是本轮最新规则记忆版本。

给家里Codex的第一句话（可直接复制）：
“这是东方智慧APP的接续项目。请先完整读取根目录AGENTS.md、回家继续-先读我.txt、06_验证与后续工作/回家继续-进度与记忆.json，并分段读完06_验证与后续工作/回家继续-历史规则原文.txt。先复述打包和目录规则、每模块双端回归要求、17阶段已验证范围、长期记忆未完成断点与发布边界；我明确说继续后再按断点开发。”

根AGENTS是简短的当前有效规则，完整保留原规则的438行原文在06历史规则文件，并有SHA核验。保存的是对话中的规则/决策/进度；不是整段聊天逐字导出，也不依赖另一台机器自动继承旧会话。
本次用户最新决定：停止继续开发，先打包带回家；嫌原包过大，改用精简包；核对确认21个本地提交尚未上传GitHub。已完成代码与改到一半的准备文件都已保存，不能把“未完成”误认为“未保存”。
精简包不含.git、旧部署压缩包、06旧截图/录像、可选安装器和机器缓存；当前源码/构建、原需求、报告/脚本、未完成代码及本轮隔离预览库均携带。历史视觉报告保留原声明，严格逐图复核需从原大包补媒体。
新ZIP直接收录根文件及用途目录，没有额外的项目包装层。请解压到一个项目目录后，从这个有AGENTS.md的目录接续；当前GitHub尚是旧版本。

以下是原交接进度和启动步骤：
'''
if not readme.startswith('回家接续：规则、决策与代码都在这个包里'):
    readme = preface + '\n' + readme
readme = readme.replace('嫌原包过大，改用约354MiB精简包', '嫌原包过大，改用精简包')
(ROOT / '回家继续-先读我.txt').write_bytes(readme.encode('utf-8-sig'))

state_path = AREA / '回家继续-进度与记忆.json'
state = json.loads(state_path.read_bytes())
state['package_policy']['include'] = '当前源码/构建/原需求/说明/规则与决策/历史报告/未完成代码/本轮隔离预览库一致快照'
state['package_policy']['exclude'] = list(dict.fromkeys(state['package_policy']['exclude'] + ['所有层级.git历史', '历史ZIP/部署压缩包', '06历史截图录像和可选安装器']))
state['package_policy']['gitHistoryIncluded'] = False
state['package_policy']['historicalVisualMediaIncluded'] = False
state['instruction_handoff'] = {
    'updatedAt': now.isoformat(), 'entry': 'AGENTS.md',
    'readOrder': ['AGENTS.md', '回家继续-先读我.txt', '06_验证与后续工作/回家继续-进度与记忆.json', '06_验证与后续工作/回家继续-历史规则原文.txt'],
    'historicalRulesSHA256': sha(history.read_bytes()),
    'historicalRulesAre': '原AGENTS全部438行逐字节存档，不是完整聊天逐字导出',
    'currentRulesBytes': len(rules.encode()), 'conversationTranscriptIncluded': False,
    'automaticCrossComputerConversationMemoryPromised': False,
    'developmentStillPaused': True,
    'recentDecisions': ['先暂停开发并带回家', '原大包过大，改精简包', '21个本地提交尚未上传GitHub', '未完成代码已保存且纳入精简包', '补全打包规则和重要约束，家中接手先读文件'],
    'officialInstructionGuide': 'https://learn.chatgpt.com/docs/agent-configuration/agents-md',
    'noBusinessSourcesModified': True
}
state_path.write_bytes((json.dumps(state, ensure_ascii=False, indent=2)+'\n').encode())

snapshot = ROOT / state['database_snapshot']['source']
assert sha(snapshot.read_bytes()) == state['database_snapshot']['sha256']
name = '东方智慧APP_接续精简包_含规则记忆_' + now.strftime('%Y%m%d_%H%M%S')
target = ROOT / (name + '.zip'); temporary = target.with_suffix('.partial')
assert not target.exists() and not temporary.exists()
skip_dirs = {'.git','node_modules','.wrangler','__pycache__','.pytest_cache','.venv','.next','.cache'}
media = {'.png','.jpg','.jpeg','.gif','.webp','.svg','.mp4','.webm','.mov','.avi','.mp3','.m4a','.wav','.ogg'}
archives = ('.zip','.partial','.tar','.tar.gz','.tgz','.7z','.rar','.tar.bz2','.tar.xz')
files = []; excluded = []
for current, dirs, names in os.walk(ROOT, followlinks=False):
    base = Path(current); kept = []
    for folder in dirs:
        f = base/folder; rel = f.relative_to(ROOT).as_posix()
        if folder in skip_dirs or f.is_symlink() or getattr(f,'is_junction',lambda:False)():
            excluded.append({'path':rel+'/', 'reason':'Git, dependency/cache or external link'})
        else: kept.append(folder)
    dirs[:] = kept
    for leaf in names:
        f = base/leaf; rel = f.relative_to(ROOT).as_posix(); low = leaf.lower(); why = None
        if f.is_symlink() or not f.resolve().is_relative_to(ROOT): why='external link'
        elif low.endswith(archives): why='old/new archive; no recursive packaging'
        elif low.endswith(('.sqlite','.sqlite3','.db','.db3','-wal','-shm','.pyc','.pyo')): why='database/cache; insert authorized consistent snapshot once'
        elif ((low.startswith('.env') or low.startswith('.dev.vars')) and not low.endswith(('.example','.sample'))): why='machine environment values'
        elif rel.startswith('06_验证与后续工作/') and f.suffix.lower() in media: why='old verification media; reports kept'
        elif rel.startswith('06_验证与后续工作/') and f.suffix.lower() in {'.msi','.exe','.dmg','.pkg'}: why='optional machine installer'
        elif leaf in {'回家继续-包内文件清单.json','回家继续-打包结果.json','回家继续-精简包结果.json','回家继续-规则记忆包结果.json'} or low.endswith('.sha256.txt'): why='outer receipt or regenerated manifest'
        if why: excluded.append({'path':rel,'reason':why}); continue
        if f.is_file(): files.append((rel,f))
files.append((state['database_snapshot']['archive_path'],snapshot)); files.sort()
assert len({rel for rel,_ in files}) == len(files)
manifest = {'createdAt':now.isoformat(),'flatProjectRoot':True,'gitHistoryIncluded':False,'historicalVisualMediaIncluded':False,'verifiedStages':17,'memoryIntegrated':False,'conversationTranscriptIncluded':False,'allHistoricalProjectRulesPreserved':True,'historicalRulesSHA256':sha(history.read_bytes()),'files':[],'excluded':excluded,'manifestSelfHashExcluded':True}
print(json.dumps({'phase':'packing','files':len(files),'archive':str(target)},ensure_ascii=False),flush=True)
with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
    for rel,f in files:
        data = f.read_bytes()
        z.writestr(rel,data)
        manifest['files'].append({'path':rel,'bytes':len(data),'sha256':sha(data)})
    z.writestr('回家继续-包内文件清单.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'phase':'verifying','MiB':round(temporary.stat().st_size/1024**2,1)},ensure_ascii=False),flush=True)
with zipfile.ZipFile(temporary) as z:
    assert z.testzip() is None
    for entry in manifest['files']:
        assert sha(z.read(entry['path'])) == entry['sha256'], entry['path']
    assert z.read('06_验证与后续工作/回家继续-历史规则原文.txt') == history.read_bytes()
    assert len(z.read('AGENTS.md')) < 16*1024
    for rel, expected in state['memory_preparation']['files'].items():
        assert sha(z.read(rel)) == expected['sha256'],rel
    for entry in state['verified_stages']:
        assert sha(z.read(entry['path'])) == entry['sha256'],entry['path']
    assert sha(z.read('03_当前APP/东方智慧-首页体验R4.html')) == state['active_app']['sha256']
    assert not any('.git' in Path(x.filename).parts for x in z.infolist())
temporary.rename(target)
digest=hashlib.sha256()
with target.open('rb') as f:
    for b in iter(lambda:f.read(8*1024*1024),b''):digest.update(b)
result={'pass':True,'archive':str(target),'bytes':target.stat().st_size,'MiB':round(target.stat().st_size/1024**2,1),'sha256':digest.hexdigest(),'files':len(manifest['files'])+1,'allEntryCRCChecked':True,'allFilesSHA256Checked':True,'historicalRulesPreservedByteForByte':True,'currentRulesBytes':len(rules.encode()),'flatProjectRoot':True,'developmentPaused':True,'gitHistoryIncluded':False,'conversationTranscriptIncluded':False}
(AREA/'回家继续-规则记忆包结果.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
target.with_suffix('.sha256.txt').write_bytes((result['sha256']+'  '+target.name+'\n').encode())
print(json.dumps(result,ensure_ascii=False),flush=True)
