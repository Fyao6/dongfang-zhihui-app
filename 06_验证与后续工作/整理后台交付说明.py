from pathlib import Path
p=Path(__file__).resolve().parents[1]
guide='''东方智慧统一管理后台 使用手册
交付日期：2026-10-28（北京时间）

打开与登录
1. 运行同目录“启动APP与后台.cmd”；服务仅在本机运行。
2. 浏览器打开 http://127.0.0.1:8765/admin 。APP查看页为 /app，独立体验为 /experience。
3. 当前正式库尚无管理员，首次进入请自行设置账号、昵称和至少10位密码。此流程只有首次开放，不预设或展示密码。
4. 后续登录后在“账号与权限”分配角色。普通账号可先通过APP注册，再由管理员调整为运营、审核员或老师。

运营工作
每日一句、地图、抽卡、音乐、课程、老师、签到、会员套餐及权益均在左侧对应栏目编辑。
列表支持名称、编号或关键词查找以及状态筛选；查找针对当前载入列表，计时页的原始记录载入最近500条。
编辑已有条目或新增内容；排序值越小越靠前。保存草稿不会在APP公开，发布后APP重新打开读取最新配置，归档后退出公开内容。
地图仅使用life、body、mind三个固定编号，不新增第四种地图。
图片、音乐、视频支持上传和预览，单文件上限50MB。上传完成后仍须保存或发布所属内容。
会员课程素材按权益限制读取；会员套餐配置不等于已开通正式支付或真实订阅。

社群审核与服务
老师和学员从APP自行发布，提交后由后台审核。通过审核才在公开社群显示；驳回及下架需要填写原因。
服务需求显示真实学员、老师、期望日期及需求内容，可受理和结束。没有真实需求时显示空状态。

账号权限
管理员：所有后台模块及角色/接口凭据管理。
运营：内容、社群审核、服务与记录管理；无角色及接口密钥设置权。
审核员：概览、社群审核和审计日志；无业务原始记录导出权。
老师：从APP发布并使用自己的功能，不进入管理员工作台。
学员：仅访问自身APP业务。当前管理员不能撤销自己的管理权限。

记录与导出
签到与计时显示账号昵称/标识、真实记录日期和累计汇总。记录列表同时显示总数，最多展示最近500条。
“完整JSON导出”和“完整CSV导出”均读取全部记录元数据及计时汇总，不受列表500条限制，也不受当前界面的关键词筛选影响。
导出不包含自评正文、好友对话正文或接口密钥。CSV兼容中文并防止昵称等字段被当作表格公式执行。
此页没有修改计时、暂停累计或编辑原始业务记录的按钮。

AI和设备
仅管理员进入“AI与接口配置”。填写实际Responses API地址、模型、密钥、提示词及参考知识后保存。
没有真实凭据时保持未连接，不能将本地适配测试当成真实AI联调。
设备先在“设备供应商”创建条目，再使用相同供应商编号配置密钥与字段映射。已有配置可点击“编辑配置”载入。
密钥留空保留原值；如需取消凭据，显式选择清除密钥。密钥不会返回页面明文或APP。
收到真实且已授权的设备数据前，APP显示等待接入；不会生成虚构检测数值。

追溯与数据
内容版本支持恢复之前的内容及发布状态；操作日志记录发布、审核、角色变更、配置及导出操作，不记录密钥。
正式库位于04_研发源码/app/r4/backend/eastern-wisdom.sqlite3，重新启动不会清空。
可运行同目录“备份后台数据库.py”，通过SQLite在线备份保存至07_历史版本仅供追溯，支持服务运行时备份。
备份包含账号与服务端配置，须按项目私密资料保管；不要将真实数据库当作公开评审素材。
本轮回归使用独立数据库，测试账号、素材及520条批量测试记录均不写入正式库。

交付边界
本机管理系统及APP联动已经实现。本次不是公网部署；域名、云服务和公开访问需另行配置。
真实AI调用、设备SDK、正式老师与课程素材、支付/订阅须提供真实资料再联调，不能以测试数据代替。
实际回归结果、截图和交付记录在06_验证与后续工作；未通过的早期尝试保留为历史，不替代最终通过报告。
'''
(p/'05_后台与研发说明/后台管理使用手册.txt').write_text(guide,encoding='utf-8')
backup='''"""SQLite consistent online backup; no deletion or restoration."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parent.parent
source=root/'04_研发源码/app/r4/backend/eastern-wisdom.sqlite3'
folder=root/'07_历史版本仅供追溯'
if not source.is_file() or not folder.is_dir():
 raise SystemExit('未找到正式数据库或现有历史目录；未执行备份。')
stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-%H%M%S-%f')
target=folder/('后台数据库备份-'+stamp+'.sqlite3')
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(target) as dest:
 src.backup(dest)
 if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
  raise SystemExit('备份完整性检查失败，请保留现场核查。')
print('备份完成，完整性检查通过：'+str(target))
'''
(p/'05_后台与研发说明/备份后台数据库.py').write_text(backup,encoding='utf-8')
f=p/'06_验证与后续工作/更新交付资料.py';s=f.read_text(encoding='utf-8');s=s.replace('内容可发布、归档和恢复历史版本。','内容可发布、归档和恢复历史版本。2026-10-28补齐列表关键词/编号查找、状态筛选、素材预览、供应商配置编辑及密钥清除；记录显示总数，完整JSON/CSV导出读取全部元数据而非仅最近500条。详细操作见05目录后台管理使用手册。')
s=s.replace('该脚本使用Edge无头浏览器','该脚本优先使用Edge，无可用Edge时使用Playwright Chromium无头浏览器')
s=s.replace('<a href="改动任务表-2026-10-22.html">查看任务及完成状态</a>', '<a href="改动任务表-2026-10-22.html">查看任务及完成状态</a><a href="http://127.0.0.1:8765/admin">打开统一管理后台</a>')
s=s.replace('详细方法见 <a href="05_后台与研发说明/接口与验收说明.txt">后台与接口说明</a>。','详细方法见 <a href="05_后台与研发说明/后台管理使用手册.txt">后台操作手册</a>及<a href="05_后台与研发说明/接口与验收说明.txt">接口说明</a>。')
pos=s.index("visual=doc.xpath")
s=s[:pos]+'''doc.xpath('//tr[@id="B02"]/td')[2].text='统一管理后台覆盖每日一句、地图、卡池、课程、音乐、老师、会员权益、社群审核及素材上传预览；支持关键词/编号查找、状态筛选、排序、草稿、发布、归档及历史恢复。2026-10-28运营收尾已实现。'
doc.xpath('//tr[@id="B03"]/td')[2].text='管理员、运营、审核员、老师和学员权限实际隔离；管理账号角色、老师服务需求、签到与计时。记录显示总数，完整JSON/CSV导出不受最近500条列表限制；不导出自评与对话正文。'
'''+s[pos:];f.write_text(s,encoding='utf-8')
f=p/'05_后台与研发说明/接口与验收说明.txt';s=f.read_text(encoding='utf-8').replace('该脚本使用Edge无头浏览器和独立SQLite测试库','该脚本优先使用已安装Edge，否则使用Playwright Chromium无头浏览器和独立SQLite测试库');s+='\n2026-10-28后台运营收尾\nGET /api/admin/records 返回最近500条元数据及total总数；GET /api/admin/records/export返回全部元数据与计时汇总，管理员/运营可读，审核员及普通用户不可读。两者不返回自评正文和私密消息。导出操作留审计记录。\n设备配置新增clearSecret显式清除凭据，留空仍保留；错误账号或服务编号返回404，供应商编号校验格式。前台支持完整JSON/CSV导出、列表查找及筛选、素材预览和已存供应商配置编辑。后台JS已纳入构建前语法验证。\n';f.write_text(s,encoding='utf-8')
print('Operator manual, online database backup tool and current delivery descriptions prepared.')
