from pathlib import Path
import json,hashlib
from datetime import datetime,timezone,timedelta
from pypdf import PdfReader
p=next(Path.cwd().iterdir());qa=p/'06_验证与后续工作';guide=p/'05_后台与研发说明';latest=json.loads((qa/'本轮全量回归结果.json').read_text(encoding='utf-8'))['latest'];assert latest['pass'] and latest['passed']==49
pdf=guide/'后台架构规划与前后端联调报告.pdf';reader=PdfReader(pdf);assert len(reader.pages)==10;assert all(len(page.extract_text().strip())>350 for page in reader.pages)
assert '49' in reader.pages[0].extract_text();evidence=json.loads((qa/'前后端接口实测证据.json').read_text(encoding='utf-8'))
for name,digest in latest['buildHashes'].items():assert hashlib.sha256((p/'03_当前APP'/name).read_bytes()).hexdigest()==digest
record={'atBeijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'status':'本机主要业务接口已核对，修复发布契约差异，49组全量及联调通过','report':str(pdf.relative_to(p)),'reportPages':10,'reportSha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'visualReview':'10页全部渲染检查，无空白续页、裁切或表格溢出','passed':49,'failed':0,'backendUnitChecks':5,'browserRequests':sum(x['requests'] for x in evidence['items']),'browserMethodPathCombinations':len(evidence['items']),'buildHashes':latest['buildHashes'],'fixes':['新增套餐与发布顺序','套餐及会员课程归档可见性','课程顺序','每日一句全量下架空状态','前台记录失败反馈'],'testHarnessCorrection':'老师表单按钮为默认submit；将定位器改为实际按钮，使用Promise.all绑定响应等待，避免超时未处理。最终全量重跑通过。','remaining':['真实AI及设备、支付和公网部署未验收','浏览器本地档案尚无完整账号级隔离、访客迁移和跨设备读回','记录断网缺统一自动补传队列；已明确本机保存与未同步状态'],'testDatabaseClean':not (qa/'本轮回归专用.sqlite3').exists(),'productionDatabaseTestWrites':False}
(qa/'前后端全量联调交付记录-20261028.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
old=qa/'架构联调报告-页11.png'
if old.is_file():old.unlink()
f=p/'AGENTS.md'
with f.open('a',encoding='utf-8') as out:out.write('\n\n### 2026年10月28日前后端全量联调与架构规划\n用户要求核对前后端接口，提供后台框架具体思路及规划，并进行全量回归与联调。本轮修复会员新套餐/归档、会员课程归档可见性、课程排序、每日一句全部下架空状态、记录同步失败提示。49组完整回归与联调通过，另含5个后端单元测试；脱敏浏览器证据174次响应、35种方法/路径组合，不能称作穷尽全部接口输入。10页报告在05目录后台架构规划与前后端联调报告.pdf，附同名HTML和06目录契约/实测JSON。真实外部服务、公网、完整账号本地隔离/跨设备恢复与断网自动补传仍未完成，不得描述为完整云同步。正式库未写测试数据。\n')
f=qa/'更新交付资料.py';s=f.read_text(encoding='utf-8');s=s.replace('详细操作见05目录后台管理使用手册。','详细操作见05目录后台管理使用手册。2026-10-28进一步核对前后端契约，修复新增/归档套餐、会员课程归档、课程排序、每日一句空状态及记录失败提示；架构与联调范围见同目录后台架构规划与前后端联调报告。')
s=s.replace('<h2>历史资料</h2>', '<h2>后台架构与联调报告</h2><p><a href="05_后台与研发说明/后台架构规划与前后端联调报告.pdf">下载10页架构规划与联调报告</a> · <a href="05_后台与研发说明/后台架构规划与前后端联调报告.html">浏览报告</a> · <a href="06_验证与后续工作/前后端接口实测证据.json">接口实测证据</a></p><h2>历史资料</h2>')
f.write_text(s,encoding='utf-8')
f=guide/'后台管理使用手册.txt';s=f.read_text(encoding='utf-8');s+='\n前后端联调补充\n新增套餐、已归档套餐与会员课程可见性、智慧馆课程顺序及每日一句空状态已经对齐。记录写入失败会提示本机已保存但暂未同步；当前未提供统一自动补传和完整跨设备档案恢复。详细架构、接口、49组测试及规划见同目录《后台架构规划与前后端联调报告》。\n';f.write_text(s,encoding='utf-8')
print('10-page report verified, current builds matched final 49-group run, records and current entry updated.')
