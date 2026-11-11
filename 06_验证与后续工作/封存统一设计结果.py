from pathlib import Path
import json,hashlib,zipfile
from datetime import datetime,timezone,timedelta
p=Path(__file__).resolve().parents[1];qa=p/'06_验证与后续工作';r=json.loads((qa/'本轮全量回归结果.json').read_text(encoding='utf-8'))['latest'];assert r['pass'] and r['passed']==45
backup=p/'07_历史版本仅供追溯/整套界面设计前-可回退-2026-10-27-173929.zip'
with zipfile.ZipFile(backup) as z: assert z.testzip() is None; count=len(z.namelist())
record={'atBeijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'status':'统一界面已实现，等待用户评价，不代表视觉认可','direction':'沿用当前纸玉东方主题，不新增图片；完成主内页结构和控件设计','changes':['智慧馆：三主题入口、实际短练习筛选、课程权益和单列内容目录','AI服务：实际连接状态、真实问题入口、对话和输入区','社群：老师、好友、对话、分享分层，保留实际审核发布流程','我的：身份与真实累计集中，内容/服务和偏好分组','统一页眉、排版层级、边界、间距和控件；保留首页、地图、禅修和磁吸计时规则'],'rollback':str(backup.relative_to(p)),'backupFiles':count,'backupSha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'regression':{'passed':r['passed'],'failed':r['failed'],'browser':r['coverage']['browser'],'realAI':False,'realHardware':False},'preview':'06_验证与后续工作/五大主页面实际效果.png','previewUrl':'http://127.0.0.1:8765/app?theme=coherent-paper-20261027'}
(qa/'五大主页面统一设计交付记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('Latest 45 checks passed. Archive integrity checked:',count,'files.')
