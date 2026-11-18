"""Refresh existing progress TXT/HTML using frozen passing evidence; does not modify the workbook."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone,timedelta
import json,re,argparse,html
from 负责人优化建议剩余工作 import remaining_software
P=Path(__file__).resolve().parent.parent;D=P/'06_验证与后续工作'
parser=argparse.ArgumentParser();parser.add_argument('--active',default='');parser.add_argument('--preview',default='');args=parser.parse_args()
tasks=json.loads((D/'负责人优化建议-任务拆解.json').read_text(encoding='utf-8-sig'));counts=Counter(t['status'] for t in tasks)
names=['负责人优化建议-实施记录.json','负责人优化建议-统一交易-实施记录.json','负责人优化建议-隐私设置-实施记录.json','负责人优化建议-首页视频-实施记录.json','负责人优化建议-统一AI网关-实施记录.json','负责人优化建议-会员订阅-实施记录.json','负责人优化建议-分佣-实施记录.json','负责人优化建议-抽卡-实施记录.json','负责人优化建议-八字版本追溯-实施记录.json','负责人优化建议-保存快照-实施记录.json','负责人优化建议-只读对账-实施记录.json','负责人优化建议-八字解读关联-实施记录.json','负责人优化建议-售后-实施记录.json']
names += ['负责人优化建议-到期清理-实施记录.json','负责人优化建议-账号注销-实施记录.json','负责人优化建议-售后资金关联-实施记录.json','负责人优化建议-密钥引用-实施记录.json','负责人优化建议-长期记忆-实施记录.json']
verified=[]
for name in names:
 p=D/name
 if not p.exists():continue
 r=json.loads(p.read_text(encoding='utf-8-sig'))
 if r.get('pass') is not True:continue
 checks='，'.join(str(k)+' '+str(v['passed'])+'项' for k,v in r.get('verification',{}).items() if isinstance(v,dict) and type(v.get('passed')) is int)
 verified.append({'module':r['module'],'scope':r.get('scope',''),'checks':checks,'proof':'06_验证与后续工作/'+name})
now=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
state='；'.join(k+' '+str(v)+'项' for k,v in counts.items())
lines=['东方智慧APP负责人优化建议实施进度',now,'','依据负责人v1.0原文689段、21表、4图和26项参考资料，逐项拆为98项任务并保留出处。','当前任务状态：'+state+'。状态与逐项外部缺口以任务表I/K列为准。','','已通过本地阶段门禁的实际范围：']
for v in verified:lines+=['',v['module'],v['scope'],v['checks'],'证据：'+v['proof']]
if args.active:lines+=['','当前继续实施：'+args.active]
lines+=['','未完成的软件与部署工作：'+remaining_software(P)+'。不能全部归为等资料。','未完成的外部条件：老师确认规则和至少30个标准命盘、Claude接口及数据条款、实际DeepSeek/GPU模型与预算、正式会员价格权益和分佣文档、签约/银行/发行渠道与商品ID、首发商品履约与授权、完整卡组规则文案与美术授权、视频审定旁白音乐及各语言校对、目标国家负载及数据期限/供应商信息。','正式支付、真实模型请求、生产资源部署和目标地区容量/容灾验收均未完成。已完成的软件沙箱与实际生产渠道分别登记。','本机SQLite备份恢复及30秒匿名访客探索见各自报告；不据此承诺生产RPO/RTO或海外承载能力。','','本轮未更新公网、未购买资源、未重打完整项目ZIP；原8880/8879未重新绑定，旧冻结收据与历史完整ZIP保留。']
if args.preview:lines+=['','本轮独立测试预览：'+args.preview]
lines+=['','完整任务表：06_验证与后续工作/东方智慧APP优化任务表_依据v1.0_20261112.xlsx','原文逐段对照：02_需求与设计参考/负责人优化建议-逐段原文.json']
(P/'05_后台与研发说明/负责人优化建议实施进度.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
items=''.join('<li><strong>'+html.escape(v['module'])+'</strong>：'+html.escape(v['scope'])+' <a href="'+html.escape(v['proof'],quote=True)+'">阶段验收证据</a></li>' for v in verified)
block='<section class="intro" aria-labelledby="manager-v1-heading"><h2 id="manager-v1-heading">当前负责人优化建议 v1.0 实施进度</h2><p>'+html.escape(now)+'；98项任务，'+html.escape(state)+'。软件沙箱通过情况、视觉待验收及正式资料缺口分别记录。</p><ul>'+items+'</ul>'+('<p>继续实施：'+html.escape(args.active)+'</p>' if args.active else '')+'<p><a href="06_验证与后续工作/东方智慧APP优化任务表_依据v1.0_20261112.xlsx">查看当前98项任务表</a>　<a href="05_后台与研发说明/负责人优化建议实施进度.txt">本轮进度与外部缺口</a></p><p>正式收费、真实模型和生产部署尚未完成。下方历史阶段按各自记录日期追溯。</p></section>'
p=P/'改动任务表-2026-10-22.html';old=p.read_text(encoding='utf-8-sig');pattern=r'(?<=<!-- manager-v1-current:start -->).*?(?=<!-- manager-v1-current:end -->)'
assert len(re.findall(pattern,old,re.S))==1
p.write_text(re.sub(pattern,lambda _:'\n'+block+'\n',old,flags=re.S),encoding='utf-8')
print(json.dumps({'verifiedStages':len(verified),'taskCount':len(tasks),'statusCounts':dict(counts)},ensure_ascii=False))

