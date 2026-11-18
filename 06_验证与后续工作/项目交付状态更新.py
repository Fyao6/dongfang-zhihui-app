"""Update delivery documentation only; keep frozen implementation receipts unchanged."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / '06_验证与后续工作'
parser = argparse.ArgumentParser()
parser.add_argument('--phase', choices=['prepare', 'synced'], required=True)
parser.add_argument('--commit')
args = parser.parse_args()
now = datetime.now(timezone(timedelta(hours=8))).isoformat()
read = lambda p: json.loads(p.read_bytes())
def write(p, value): p.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())

memory_path = AREA / '项目进度与记忆.json'
memory = read(memory_path)
if 'historicalPackagingBeforeCurrentDelivery' not in memory:
    memory['historicalPackagingBeforeCurrentDelivery'] = memory['packaging']
memory['packaging'] = {
    'type': 'normal-project-delivery', 'source': '直接从当前唯一项目工作目录的实际文件生成正常项目交付包，不从旧ZIP重包',
    'normalProjectArchive': True, 'wrapperDirectory': False,
    'script': '06_验证与后续工作/项目交付打包.py',
    'manifestInArchive': '包内文件清单.json',
    'previewDb': '06_验证与后续工作/负责人优化建议-隔离预览.sqlite3',
    'previewDbMethod': 'SQLite只读连接backup API的一致快照；最终SHA以本次ZIP清单为准，源库正常使用可继续更新',
    'previewDbPublicGitIncluded': False,
    'exclude': ['Git内部、依赖及运行缓存', '旧压缩包和部署归档', '06历史媒体与重复历史源码保全副本',
        '安装器、环境、凭据、会话、19项私有运行产物', '其它数据库及快照SQL/R2对象'],
    'redaction': '两份含历史测试会话的原报告排除，提供明确标注的脱敏副本；原件本机保持',
    'allFilesSHA256AndZIPCRCRequired': True, 'businessTestsRerun': False,
    'status': 'awaiting-archive-verification', 'updatedAtBeijing': now,
    'originalRequirementsAllComplete': False,
}
memory['currentDeliveryPreparation']['packageType'] = '正常项目交付包'
memory['currentDeliveryPreparation']['userCorrection'] = '不是生成接续包，要求正常的包'
memory['currentDeliveryPreparation']['updatedAtBeijing'] = now
if args.phase == 'synced':
    assert args.commit and len(args.commit) == 40
    receipt = read(AREA / 'GitHub本次同步记录.json')
    assert receipt['pass'] is True and receipt['commit'] == args.commit
    memory['github']['priorPublishedCommit'] = memory['github'].get('publishedCommit')
    memory['github']['publishedCommit'] = args.commit
    memory['github']['sourceSyncedAtBeijing'] = now
    memory['github']['scope'] = '当前源码、03和相关Cloud构建、需求素材与公开验证资料已同步现有main；数据库/环境/凭据/私有运行资料未上传。原Pages工作流由03变更触发；正式后端、支付和模型未发布验收。'
    memory['github']['localChangesAfterPublishedCommit'] = '本轮源码同步已核对；最终交付文档补充提交以ZIP内包内文件清单.gitCommit为准。'
    memory['github']['verification'] = '06_验证与后续工作/GitHub本次同步记录.json'
    memory['currentDeliveryPreparation']['githubStatus'] = 'source-synced-and-verified'
    memory['currentDeliveryPreparation']['sourceSnapshotCommit'] = args.commit
write(memory_path, memory)

for name in ['项目说明.txt', '交付包说明.txt']:
    p = ROOT / name
    text = p.read_text('utf-8').replace('接续依据\n', '查阅依据\n').replace('验证与接续：06', '验证与后续工作：06')
    marker = '本次交付类型：正常项目交付包，直接收录当前项目入口、源码、APP与官网、Cloud构建、需求素材、说明及验证资料；不增加外层包装目录。\n'
    if marker not in text: text = text.replace('本轮工作：', marker + '\n本轮工作：', 1)
    if args.phase == 'synced':
        text = text.replace('GitHub与打包当前正在办理，完成结果见06目录新增的同步记录和交付校验记录，不能据本说明预先认定成功。',
            '当前源码已同步GitHub main并逐文件核对，提交为' + args.commit + '；本轮交付文档另有补充提交，最终HEAD见ZIP内包内文件清单。压缩包校验结果见06目录项目交付-校验记录。')
    p.write_bytes(text.encode())

p = ROOT / 'AGENTS.md'
text = p.read_text('utf-8')
marker = '用户再次明确本次要正常项目交付包，不是接续包；使用“东方智慧APP项目交付-实际北京时间.zip”，直接从当前项目实际文件打包，沿用既定安全排除及逐文件SHA/CRC核验规则，不另造场景名称或外层目录。\n'
if marker not in text: text = text.replace('## 2026-11-18 交付命名与本轮授权（最新）\n', '## 2026-11-18 交付命名与本轮授权（最新）\n\n' + marker)
p.write_bytes(text.encode())
if args.phase == 'synced':
    p = ROOT / 'README.md'
    text = p.read_text('utf-8').replace('此次同步和打包尚在办理，最终提交与校验结果以06目录本轮新增记录为准。',
        '当前源码已同步main并完成逐文件核对，见[本次同步记录](06_验证与后续工作/GitHub本次同步记录.json)。正常项目交付包的最终Git提交、完整文件清单和SHA在ZIP内“包内文件清单.json”；外部校验记录另含ZIP整体SHA及CRC结果。')
    p.write_bytes(text.encode())
mapping_path = AREA / '文件命名对照.json'
mapping = read(mapping_path)
for item in mapping['records']:
    item['currentSHA256'] = hashlib.sha256((ROOT / item['currentPath']).read_bytes()).hexdigest()
mapping['completion']['packageType'] = 'normal-project-delivery'
mapping['completion']['githubSyncStatus'] = 'source-synced-and-verified' if args.phase == 'synced' else 'pending'
write(mapping_path, mapping)
print(json.dumps({'phase': args.phase, 'normalProjectDelivery': True, 'frozenReceiptsModified': False}, ensure_ascii=False))
