"""Refresh existing documentation, task statuses and the current manifest in place."""
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import html as H
import json
from pathlib import Path
import sys
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parent.parent
stamp = datetime.now(timezone(timedelta(hours=8)))
date = stamp.strftime('%Y-%m-%d')
beijing = stamp.strftime('%Y-%m-%d %H:%M:%S +08:00')
regression_path = root / '06_验证与后续工作/本轮全量回归结果.json'
regression = json.loads(regression_path.read_text(encoding='utf-8'))['latest']
waiting = {'M04': '已实现，待真实设备联调', 'A02': '已实现，待真实AI联调', 'B04': '已实现，待真实配置联调'}

usage = '''东方智慧 APP 当前使用说明
更新日期 {date} 北京时间
社群发现页已加入用户提供的9.87秒短视频预览，点击播放；此预览不属于真实账号发帖，不写入我的发布。
智慧馆课程采用左图右文，后台课程支持上传封面，建议4:3；未设置或加载失败时显示现有主题插画。
智慧馆分类与首页统一为“认识自己、修复自己、提升自己”；课程筛选、列表标签及后台选项同步。现有课程编号和内容键保持兼容。
首页轮播：后台“首页轮播 / 每日一句”可编辑标题、图片、栏目标签、说明、跳转按钮和目标。目标可填 academy、dailyCard、music、body、mind、lifeResult、service、membership 或 HTTPS 网址；留空打开思考详情。排序、草稿、发布、归档沿用原后台流程。首页7秒轮播，支持暂停、滑动和圆点；减少动态效果时手动切换。
当前唯一项目位置：{project_root}
本机项目位置以本文件所在项目根目录为准；早期 D 盘路径只作历史记录。
本轮依据《东方智慧APP视觉与体验优化建议》完成自评—建议—练习—反馈—回访闭环、三图差异化、学习回访、内容出处与卡片行动；本地记录不代表完整账号云同步。
用户已选择“玄流”方向试做。当前实际APP为深墨、暖金、动态数字山水；默认夜间，仍可主动选择日间，当前待用户评价。

查看当前页面
直接打开本目录“发给负责人-东方智慧首页R4.html”，可以离线查看页面和本机体验。文件名沿用原入口，实际内容已更新。
需要账号、社群与后台时，运行“05_后台与研发说明/启动APP与后台.cmd”。
APP查看页 http://127.0.0.1:8765/app
独立APP http://127.0.0.1:8765/experience
统一后台 http://127.0.0.1:8765/admin

本轮改动
首页到每日签到、智慧课程、冥想音乐、我的收藏、成长记录这一行结束，下方不再堆叠内容。
2026-10-28 用户明确选择玄流方向试做，当前已落实到实际APP：深墨与暖金、强化流动的数字山水、沿山脊穿行的金色高光、触摸涟漪与拖动反馈、并列三大地图、地图及练习页山水反馈，以及智慧馆、AI、社群和我的统一视觉。新增xuanliu.css/js作为当前主题层；默认夜间，一次迁移后尊重用户后续日夜偏好；减少动态效果、后台隐藏与离开页面停止场景。原有真实计时、播放器、后台自定义封面和业务功能保留。当前仍待用户体验评价。
智慧馆压缩头部并改为紧凑课程列表；个人页偏好设置按需展开，调整时保持展开。整体减少说明和长页面，同时保留原有记录与操作入口。
抽卡进入即自动滚动；点击中心图片锁定当时居中的卡片。每天保留一张，可回看与收藏；卡片启发是预写内容，真实AI问答通过独立服务连接。
签到通过敲钟触发声音与签到反馈，同一天不重复记账，支持关闭声音。
音乐支持原有合成音景与后台上传音频，包含播放、暂停、切换、音量、定时、收藏及实际聆听时长记录。
全局计时打开APP自动累计，无人为暂停。轻点悬浮计时可在长条与56像素小正方形间切换，小方块也持续显示完整时分秒。两种形态整块均可跟手拖动，松手平滑吸附最近的左右屏幕边缘，保留高度；保存形态、贴边方向及高度，切换大小时继续贴边，拖动结束不会误触切换。可隐藏，多窗口不重复累计。实际退出与断线通过心跳结算，口径详见后台说明。
AI服务直接进入对话。未配置时显示未连接，不以预设回答冒充实时AI。
社群支持老师和学员自主发布视频及内容、提交审核、驳回修改和下架。保留好友申请、对话、分享与老师服务需求。
统一后台可管理内容、图文素材、卡池、课程、音乐、会员配置、老师、社群审核、角色权限、计时记录、AI和设备接口；内容可发布、归档和恢复历史版本。2026-10-28补齐列表关键词/编号查找、状态筛选、素材预览、供应商配置编辑及密钥清除；记录显示总数，完整JSON/CSV导出读取全部元数据而非仅最近500条。详细操作见05目录后台管理使用手册。2026-10-28进一步核对前后端契约，修复新增/归档套餐、会员课程归档、课程排序、每日一句空状态及记录失败提示；架构与联调范围见同目录后台架构规划与前后端联调报告。

数据与边界
个人原有觉察、收藏和偏好继续保存在当前浏览器。联网本地服务中的账号、发布、对话、服务需求、设备及计时保存在当前项目的SQLite数据库。
本轮回归使用独立测试库，不包含真实老师、真实设备检测值或付费AI调用。
仍待真实AI凭据、设备品牌SDK与实际数据联调；真实课程、老师资料及正式支付由相应真实服务另行配置与验收。
旧压缩包和10月15日报告保留为历史参考，不代表本次代码的最新交付。
'''.format(date=date, project_root=str(root))
(root / '03_当前APP/功能与使用说明-R4.txt').write_text(usage, encoding='utf-8')
(root / '先读我.txt').write_text('东方智慧 APP 当前资料入口\n更新时间：'+beijing+'\n当前唯一项目位置：'+str(root)+'\n本机以当前实际根目录为准，历史绝对路径不可用于写入。\n当前为用户选择的玄流试做：深墨、暖金和动态数字山水，默认夜间；保留日间选择，当前待用户评价。\n\n当前代码和实际查看页面已在本目录原位更新。\n先打开根目录“打开这里.html”，再查看“03_当前APP/发给负责人-东方智慧首页R4.html”。\n需要账号、社群和后台时运行“05_后台与研发说明/启动APP与后台.cmd”。\n任务及状态见根目录“改动任务表-2026-10-22.html”。\n每完成模块均运行全量回归，实际记录在“06_验证与后续工作/本轮全量回归结果.json”。\nAI与设备接口已实现，真实联调仍需相应凭据与设备资料。\n\n代码：04_研发源码/app/r4；实际构建直接更新03_当前APP。\n原始反馈、补充截图与图文顺序记录已随包保留。\n10月15日的报告、旧压缩包及原始校验信息属于历史依据，请以当前任务表、源码及本轮回归记录判断最新状态。\n所有修改、素材和交付物继续只在当前目录内完成；不要另起项目目录或套娃版本目录。\n', encoding='utf-8')
(root / '05_后台与研发说明/源码与构建说明.txt').write_text('源码和构建说明\n更新日期：'+date+' 北京时间\n\n1. 源码仍为04_研发源码/app/r4；platform.js与platform.css复用原评估、记录和播放器；当前主题层为xuanliu.css与xuanliu.js：深墨暖金、Canvas动态数字山水、三图并列、地图与禅修场景。默认夜间，appearanceRevision=xuanliu-1进行一次迁移，之后保留明确选择的日夜偏好；三大地图为两行四项操作。日夜配色、后台自定义封面与所有原交互继续保留。GitHub源码参考记录见02目录。\n2. 使用Python3运行该目录build.py，直接覆盖已有03_当前APP中的APP、负责人查看页和统一管理后台。可用Node存在时，先校验合并JS语法，失败不覆盖页面。不会另建output项目树。\n3. 后台server.py使用Python标准库和SQLite。运行05目录“启动APP与后台.cmd”，或原有兼容入口“启动本地计时后台.py”。\n4. 首次打开/admin由使用者创建管理员，不提供预设密码。后续按角色权限管理内容、审核及配置。\n5. 后台数据库在现有backend目录内产生，不创建额外data目录。上传素材保存在SQLite中。\n6. initial-content.json为首次初始化内容。需要从源码重新导出默认内容时，使用捆绑Node运行06目录“同步后台初始内容.cjs”；重启不会覆盖数据库中已有修改。\n7. 接口、计时口径、真实接入边界与回归方法见本目录“接口与验收说明.txt”。\n8. 根目录、素材链接与构建位置均基于相对路径；将来直接改根目录名称时不需复制项目。\n9. 本轮全量回归脚本与单元脚本保存在现有06目录，测试库在运行后清理。原验证脚本仍保留为历史参考。\n', encoding='utf-8')
(root / '04_研发源码/app/r4/backend/时间银行后台说明.txt').write_text('此文件名为历史兼容入口。\n本目录server.py现提供整个APP与统一后台，而非单独计时服务。\n默认数据库为本目录eastern-wisdom.sqlite3，无用户手动暂停计时接口。\n启动、权限、内容管理、API、心跳结算和回归说明见根目录下05_后台与研发说明/接口与验收说明.txt。\n', encoding='utf-8')
(root / '00_阅读与报告/新窗口启动提示词.txt').write_text('先阅读当前根目录AGENTS.md并遵守唯一目录和每模块全量回归要求。\n再阅读根目录改动任务表-2026-10-22.html、03_当前APP/功能与使用说明-R4.txt和05_后台与研发说明/接口与验收说明.txt。\n本轮已根据1016问题反馈及用户补充要求进行大改；当前源码和构建页面已经更新。任务表的实际状态及本轮全量回归结果是进度依据。\n原10月15日产品报告与完整背景正文作为历史资料；涉及首页长度、服务、抽卡、计时和社群时，以当前用户要求及已实现代码为准。\nAI和设备接口已实现但真实凭据、设备SDK及真实数据尚待联调，不得描述为正式接入完成。\n继续修改时直接修改当前目录里的文件，构建直接更新03_当前APP。每完成一个模块运行整套回归，有失败先修复重跑，再更新同一任务表。\n', encoding='utf-8')
bg = root / '00_阅读与报告/给新AI的完整项目背景.txt'
body = bg.read_text(encoding='utf-8')
marker = '【以下为2026年10月15日历史交接背景】'
if marker in body:
    body = body.split(marker, 1)[1].lstrip()
prefix = '【当前实施状态 '+beijing+'】\n本项目已按1016反馈完成本地功能，并于2026年10月27日获得用户授权试做科技禅修视觉；当前待用户体验反馈。改版前存档及SHA-256校验见07目录和06目录科技禅修改版前存档校验.json。请优先阅读AGENTS.md、根目录任务表、当前使用说明与本轮全量回归记录。首页在五项快捷功能行结束；三大地图精简；抽卡自动滚动并中心点停；钟声签到；全局自动计时且不能人为暂停；社群自主发布并经审核；统一后台与接口已经实现。真实AI及设备联调仍待凭据和设备资料。历史正文中的旧页面结构、暂停计时和离线假定不再代表当前实现。\n\n'+marker+'\n\n'
bg.write_text(prefix+body, encoding='utf-8')

from lxml import html, etree
task = root / '改动任务表-2026-10-22.html'
doc = html.fromstring(task.read_text(encoding='utf-8'))
for row in doc.xpath('//table[contains(@class,"task-table")]/tbody/tr'):
    cells = row.xpath('./td')
    if len(cells) == 4:
        number_cell = etree.Element('td');number_cell.text = row.get('id');row.insert(0, number_cell)
    assert len(row.xpath('./td')) == 5, 'Invalid task table columns: '+row.get('id')
    status = row.xpath('.//span[@class="status"]')[0]
    status.text = waiting.get(row.get('id'), '已实现，通过本地回归' if regression['pass'] else '已实现，等待最终回归通过')
    status.set('style', 'color:#916a20' if row.get('id') in waiting else 'color:#087568')
meta = doc.xpath('//header/p[@class="meta"]')[0]
meta.text = '更新：北京时间 '+beijing+' ｜ 28项任务：25项本地验收通过，3项待真实AI或设备联调' if regression['pass'] else '实施中，最终回归尚未通过'
for paragraph in doc.xpath('//p'):
    if paragraph.get('class') == 'section-note' and '本轮“大后台”' in ''.join(paragraph.itertext()):
        paragraph.clear();paragraph.set('class', 'section-note');paragraph.text = '当前已实现Python、SQLite与统一管理页面：内容发布及版本恢复、账号角色、社群审核、业务记录、AI与设备配置均通过本地接口联通APP。默认内容用于首次初始化，之后后台修改不会被重启覆盖。下表区分固定交互、运营配置和系统记录；真实AI与设备仍需联调。'
    if paragraph.text and ('所有条目均需落实。编号用于逐项验收' in paragraph.text or paragraph.text.startswith('编号用于逐项验收，来源用于追溯。')):
        paragraph.text = '编号用于逐项验收，来源用于追溯。本轮已实施，实际状态以每行标记及最新回归记录为准。最新全量回归：'+str(regression['passed'])+'组通过，'+str(regression['failed'])+'组失败；另含5项后台单元检查。'
    if paragraph.text and '本轮先完成任务表。' in ''.join(paragraph.itertext()):
        paragraph.clear();paragraph.text = '本轮已进入实施并更新APP源码与实际页面；每模块完成运行全量回归。真实AI与设备联调另行记录，不计为已完成正式接入。'
    if paragraph.text and '尚未明确的生命周期口径' in paragraph.text:
        paragraph.text = '计时已按会话心跳实现，断线超过45秒结算至最后一次心跳；多个窗口不重复计时。实际设备的后台限制仍需实机验证。'
for li in doc.xpath('//li'):
    if ''.join(li.itertext()).startswith('本轮先完成任务表。'):
        li.clear();li.text = '本轮已实施并更新APP源码与实际页面；每完成一个模块运行全量回归，失败先修复再重跑。真实AI及设备另行联调。'
    if ''.join(li.itertext()).startswith(('计时边界。','计时边界：')):
        li.clear();li.text = '计时边界：打开自动累计、不可手动暂停、隐藏继续。长条和小正方形均显示完整时分秒，轻点切换；拖动时跟手，松手平滑吸附最近的左右屏幕边缘，保留高度和形态，拖动不会误触切换。通过心跳在超过45秒断连时结算旧会话，多窗口去重；移动端系统后台限制仍待实机验证。'
    if ''.join(li.itertext()).startswith('后台与内容。'):
        li.clear();li.text = '后台与内容：本地账号、素材存储、内容管理及审核已实现。真实课程媒体、老师资料、正式支付和上线环境仍需配置与验收；本地接口通过不能替代正式服务验收。'
doc.xpath('//tr[@id="B02"]/td')[2].text='统一管理后台覆盖每日一句、地图、卡池、课程、音乐、老师、会员权益、社群审核及素材上传预览；支持关键词/编号查找、状态筛选、排序、草稿、发布、归档及历史恢复。2026-10-28运营收尾已实现。'
doc.xpath('//tr[@id="B03"]/td')[2].text='管理员、运营、审核员、老师和学员权限实际隔离；管理账号角色、老师服务需求、签到与计时。记录显示总数，完整JSON/CSV导出不受最近500条列表限制；不导出自评与对话正文。'
visual=doc.xpath('//tr[@id="P03"]/td')[2]
visual.text='课程列表已支持左图右文，后台课程封面上传及缺图/加载失败回退。智慧馆三分类已统一为认识自己、修复自己、提升自己，并同步课程标签、筛选与后台选项。2026-10-29首页每日一句区域支持运营轮播，7秒自动切换、手势/圆点/键盘、暂停及后台配置跳转，固定保留练习入口。2026-10-28 按负责人优化建议实施真实体验闭环：自评到有依据的练习、离页继续、练后反馈影响下次推荐、成长分类回看；三图按档案探索/评估行动/即刻静心区分。课程可填出处且保留本机查看入口，卡片可自愿加入今日安排并单独标明完成；2026-10-29依负责人要求，AI页收为对话框和简短提示，移除推荐卡及规则练习区。用户选择玄流方向试做。实际APP已采用深墨暖金、强化山脊流光及触摸涟漪、并列地图入口及统一五个主页面、地图与练习体验；保持原有业务与首页结束范围。默认夜间且后续主动外观选择可保存；场景尊重减少动态效果并在离页/隐藏时停止。旧版有回退存档。试做待用户评价，功能回归不等于视觉已获最终认可。'
task.write_text('<!doctype html>\n'+etree.tostring(doc, encoding='unicode', method='html'), encoding='utf-8')

task_rows = []
for row in doc.xpath('//table[contains(@class,"task-table")]/tbody/tr'):
    cells = row.xpath('./td')
    task_rows.append({'id': row.get('id'), 'module': ''.join(cells[1].itertext()), 'requirement': ''.join(cells[2].itertext()), 'acceptance': ''.join(cells[3].itertext()), 'state': row.xpath('.//span[@class="status"]')[0].text})
tracking_path = root / '06_验证与后续工作/需求追踪表.json'
tracking = json.loads(tracking_path.read_text(encoding='utf-8'))
history_tracking = tracking.get('historical_2026_10_15', tracking) if isinstance(tracking, dict) else tracking
tracking_path.write_text(json.dumps({'updated_beijing': beijing, 'authoritative_task_table': task.name, 'current_tasks': task_rows, 'historical_2026_10_15': history_tracking}, ensure_ascii=False, indent=2), encoding='utf-8')
changes_path = root / '06_验证与后续工作/关键修订追踪.json'
changes = json.loads(changes_path.read_text(encoding='utf-8'))
history_changes = changes.get('historical_2026_10_15', changes) if isinstance(changes, dict) else changes
changes_path.write_text(json.dumps({'updated_beijing': beijing, 'current_rules': ['当前根目录原位修改，不新增版本目录', '首页收在五项快捷功能行', '三大地图及主要功能精简，统一科技感视觉', '抽卡自动滚动，点击中心定格当前卡片', '签到敲钟，全局计时自动累计且不可手动暂停', '自主发布与后台审核分工，真实AI及设备待联调', '每完成模块运行全量回归，修复并重跑通过再推进'], 'historical_2026_10_15': history_changes}, ensure_ascii=False, indent=2), encoding='utf-8')
with (root / '06_验证与后续工作/模块状态与待办.csv').open('w', encoding='utf-8-sig', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['任务编号', '功能范围', '当前状态', '尚缺或边界'])
    for item in task_rows:
        boundary = {'M04': '需真实设备、SDK及供应商字段联调；未生成模拟测量冒充检测', 'A02': '需真实AI凭据、模型及获准知识资料，未使用付费调用', 'B04': '后台配置与接口已实现，需真实供应商凭据及连接验证', 'Q01': 'Edge或Chromium三种手机视口及本地文件/HTTP；真实手机、系统后台及输入法仍待实机验收', 'B03': '本地多账号角色及业务管理已验收；正式支付、续费和权益激活尚未接入', 'B02': '上传、发布、版本和审核已验收；正式老师、音视频及授权资料需运营配置', 'M01': '沿用文化排盘基础；深度真人解读及海外时间校正未接入'}.get(item['id'], '本地实现与回归范围，详见任务验收标准和接口说明')
        writer.writerow([item['id'], item['module'], item['state'], boundary])

validation_path = root / '交接资料验证.json'
old = json.loads(validation_path.read_text(encoding='utf-8'))
history = old.get('historical_2026_10_15', old)
current = {'updated_beijing': beijing, 'scope': 'Current in-place APP and local administration implementation', 'local_regression_pass': regression['pass'], 'regression_groups_passed': regression['passed'], 'regression_groups_failed': regression['failed'], 'unit_checks': 5, 'task_count': 28, 'local_accepted_tasks': 25, 'external_integration_tasks': waiting, 'no_live_ai_or_hardware_claim': True, 'historical_2026_10_15': history}
validation_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')

def collect():
    return sorted((p for p in root.rglob('*') if p.is_file() and not any(part in ('.git','__pycache__') for part in p.parts) and not any(x in p.name for x in ('.sqlite3', '.pyc'))), key=lambda p: str(p.relative_to(root)))

groups = {}
for file in collect():
    rel = file.relative_to(root).as_posix()
    group = rel.split('/')[0] if '/' in rel else '项目入口与规则'
    size = file.stat().st_size
    label = H.escape(file.name) + ('（历史交付快照）' if file.suffix == '.zip' else '')
    groups.setdefault(group, []).append(f'<li data-name="{H.escape(rel.lower())}"><a href="{quote(rel)}">{label}</a><span>{size/1024:.1f} KB</span></li>')
catalog = ''.join('<details><summary>'+H.escape(group)+' · '+str(len(items))+'项</summary><ul class="files">'+''.join(items)+'</ul></details>' for group, items in groups.items())
index = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>东方智慧APP 当前项目入口</title><style>*{box-sizing:border-box}body{margin:0;background:#f2f7f7;color:#18383d;font:15px/1.8 "Microsoft YaHei",sans-serif}main{max-width:1080px;margin:40px auto;padding:30px}h1{font-size:30px;margin:0}h2{font-size:21px;margin:32px 0 12px}p{color:#526b70}.actions{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0}.actions a{background:#087f83;color:white;padding:11px 18px;border-radius:12px;text-decoration:none}a{color:#087f83}table{width:100%;border-collapse:collapse;background:white}td,th{padding:12px;border:1px solid #d5e3e4;text-align:left}th{background:#e6f0f1}details{margin:12px 0;border-bottom:1px solid #d5e3e4;padding:10px 0}summary{cursor:pointer;font-weight:600}.files{list-style:none;padding:0}.files li{display:flex;justify-content:space-between;gap:15px;font-size:12px;padding:5px 0}.files span{color:#658085;white-space:nowrap}input{width:100%;padding:12px;border:1px solid #b7d0d0;border-radius:12px;font:inherit}[hidden]{display:none!important}@media(max-width:650px){main{margin:0;padding:24px 16px}h1{font-size:25px}.files li{display:block}}</style></head><body><main><h1>东方智慧APP 当前项目入口</h1><p>更新时间：BEIJING<br>所有本轮改动均在当前项目原位完成，源码与实际查看页面已同步。</p><div class="actions"><a href="03_当前APP/发给负责人-东方智慧首页R4.html">打开当前APP查看页</a><a href="03_当前APP/东方智慧-首页体验R4.html">打开独立APP</a><a href="改动任务表-2026-10-22.html">查看任务及完成状态</a><a href="http://127.0.0.1:8765/admin">打开统一管理后台</a></div><h2>当前状态</h2><table><tr><th>内容</th><th>状态</th></tr><tr><td>首页、三大地图、抽卡、签到、音乐、自动计时</td><td>已实现并通过本地回归</td></tr><tr><td>自主发布、审核、好友对话、老师需求、统一后台</td><td>本地服务已实现并通过回归</td></tr><tr><td>最新全量回归</td><td>REGRESSION</td></tr><tr><td>真实AI及设备联调</td><td>接口已实现，待凭据、设备及供应商资料</td></tr></table><h2>使用后台与联网功能</h2><p>运行 <a href="05_后台与研发说明/启动APP与后台.cmd">启动APP与后台.cmd</a>，再访问 <a href="http://127.0.0.1:8765/app">本地APP</a> 或 <a href="http://127.0.0.1:8765/admin">统一后台</a>。首次由使用者创建管理员。详细方法见 <a href="05_后台与研发说明/后台管理使用手册.txt">后台操作手册</a>及<a href="05_后台与研发说明/接口与验收说明.txt">接口说明</a>。</p><p><a href="06_验证与后续工作/本轮全量回归结果.json">查看本轮实际回归记录</a> · <a href="02_需求与设计参考/1016问题反馈.docx">原始修改反馈</a> · <a href="AGENTS.md">项目工作规则</a></p><h2>后端具体设计与架构</h2><p><a href="05_后台与研发说明/后端总体设计与架构方案.pdf">下载后端总体设计与架构方案</a> · <a href="05_后台与研发说明/后端总体设计与架构方案.html">浏览架构方案</a>。独立说明业务拆分、数据、流程、部署与实施顺序，当前实现和目标设计分开标注。</p><h2>联调证据附件</h2><p><a href="05_后台与研发说明/后台架构规划与前后端联调报告.pdf">下载10页架构规划与联调报告</a> · <a href="05_后台与研发说明/后台架构规划与前后端联调报告.html">浏览报告</a> · <a href="06_验证与后续工作/前后端接口实测证据.json">接口实测证据</a></p><h2>历史资料</h2><p>10月15日产品报告、原始交接背景和旧压缩包保留作历史依据。涉及当前实现时，请优先参考当前任务表、源码、使用说明和本轮回归记录。</p><p><a href="00_阅读与报告/产品概念与功能全景报告.html">10月15日历史产品报告</a> · <a href="00_阅读与报告/给新AI的完整项目背景.txt">完整背景及当前状态前言</a></p><h2>包内文件目录</h2><input id="file-search" type="search" aria-label="查找文件" placeholder="查找文件或模块名称">CATALOG<p>运行时数据库和临时缓存不列入源码校验清单。根目录资料校验清单记录当前文件大小和SHA-256。</p></main><script>document.getElementById('file-search').addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();document.querySelectorAll('.files li').forEach(x=>x.hidden=!!q&&!x.dataset.name.includes(q));document.querySelectorAll('details').forEach(x=>{if(q)x.open=!!x.querySelector('li:not([hidden])');});});</script></body></html>'''
index = index.replace('BEIJING', beijing).replace('REGRESSION', str(regression['passed'])+'组通过，'+str(regression['failed'])+'组失败').replace('CATALOG', catalog)
(root / '打开这里.html').write_text(index, encoding='utf-8')

excludes = {'资料校验清单.csv', '原始来源与文件校验.json'}
manifest = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in collect() if p.name not in excludes]
with (root / '资料校验清单.csv').open('w', encoding='utf-8-sig', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['包内相对位置','字节数','SHA-256'])
    writer.writerows((item['path'], item['bytes'], item['sha256']) for item in manifest)
origin_path = root / '原始来源与文件校验.json'
origin = json.loads(origin_path.read_text(encoding='utf-8'))
origin['current_revision'] = {'updated_beijing': beijing, 'source_copy_hashes_are_historical': True, 'local_regression_pass': regression['pass'], 'external_integration_pending': ['real AI credentials', 'real devices and SDK'], 'runtime_database_excluded': True}
origin['files'] = manifest
origin_path.write_text(json.dumps(origin, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'updated_beijing': beijing, 'manifest_files': len(manifest), 'regression_pass': regression['pass'], 'passed_groups': regression['passed'], 'pending_external_tasks': waiting}, ensure_ascii=False, indent=2))
