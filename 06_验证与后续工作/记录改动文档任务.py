"""Maintain the single project task table for the November 10 feedback."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse, hashlib, html, json, re

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / '06_验证与后续工作/改动文档实施记录.json'
MODULES = [
    ('M1', '首页卡片与三个快捷入口', [('D01','删除独立的一分钟练习板块，将每日智慧卡片移到原位置','智慧卡片在三地图上方且只有一处；实际抽卡、回看与收藏可用。'),('D02','首页快捷入口删除智慧课程、冥想音乐','仅每日签到、我的收藏、成长记录三个入口，五项主导航与原有课程/音乐功能保留。')]),
    ('M2', '三盘独立与真实星盘图形', [('D03','紫微、八字、星盘各自对应入口，星盘恢复图形','三页无跨盘切换；保留共同生辰门槛与逐级返回。无地点时只画真实地心黄道位置；未知时间显示日期范围，不伪造ASC、MC、宫位或精确盘；旧完整档案继续复算。')]),
    ('M3', '紫微日间配色与可读性', [('D04','紫微白天模式改纯白背景，优化字体与颜色','紫微页面、宫格与焦点区白底，深色正文、清晰边框和彩色标记；夜间效果保持，手机文字不重叠。')]),
    ('M4', '八字真实数据与移除关系', [('D05','核实6tail/lunar-javascript实际计算，完善档案、流运、神煞并删除关系','本命及运年月依据本人保存生辰真实联动；说明字段与库API来源，不把黄历日级吉凶神当四柱神煞。神煞只收录可核查规则；移除关系页与死入口，档案/流运/神煞保留。')]),
    ('M5', '展开收起控件统一', [('D06','优化展开收起详细字段等按钮的字体、符号与样式','使用统一文字和SVG箭头，去掉文本尖号/加号等拼凑符号；真实展开收起、键盘和触摸可用，四语不溢出，页面保持紧凑。')]),
]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--module',choices=[m[0] for m in MODULES]); ap.add_argument('--status',choices=['待实施','实施中','已通过']); ap.add_argument('--report',action='append',default=[]); args=ap.parse_args()
    if FILE.exists(): record=json.loads(FILE.read_text(encoding='utf8'))
    else:
        record={'source':'02_需求与设计参考/用户改动反馈-20261110.docx','source_sha256':sha(ROOT/'02_需求与设计参考/用户改动反馈-20261110.docx'),'scope':'仅本地APP实施；托管、飞书及公网发布暂不处理；AI仍暂缓。','modules':{m[0]:{'name':m[1],'tasks':[r[0] for r in m[2]],'status':'待实施','reports':[]} for m in MODULES},'history':[]}
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    if args.module:
        entry=record['modules'][args.module]
        previous=[m[0] for m in MODULES][:next(i for i,m in enumerate(MODULES) if m[0]==args.module)]
        assert all(record['modules'][m]['status']=='已通过' for m in previous), 'Earlier module gates have not passed'
        if args.status=='已通过':
            assert args.report,'Completion requires actual reports'
            reports=[]; full_targets=set(); smoke_count=0
            for name in args.report:
                p=(ROOT/name).resolve(); assert p.is_relative_to(ROOT)
                data=json.loads(p.read_text(encoding='utf8')); data=data.get('latest',data)
                results=data.get('results',data.get('checks',[])); assert results and all(x.get('pass') is True for x in results),name
                assert args.module in data.get('module',''), 'Wrong module report: '+name
                app_hash=sha(ROOT/'03_当前APP/东方智慧-首页体验R4.html')
                assert (data.get('buildSha256') or data.get('buildHashes',{}).get('东方智慧-首页体验R4.html'))==app_hash, 'Stale APP build: '+name
                if len(results)>=60: full_targets.add('cloud' if data.get('cloudWorker') else 'python')
                else: smoke_count+=1
                reports.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'count':len(results)})
            assert len(reports)>=3,'Need smoke plus both complete backend regressions'
            assert full_targets=={'cloud','python'} and smoke_count, 'Need current Python/Cloud full regressions and smoke'
            entry['reports']=reports
            entry['app_sha256']=sha(ROOT/'03_当前APP/东方智慧-首页体验R4.html')
        if args.status: entry['status']=args.status
        record['history'].append({'at':now,'module':args.module,'status':entry['status'],'reports':entry['reports']})
    record['updated_at']=now
    FILE.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    rows=[]
    for module,title,tasks in MODULES:
        current=record['modules'][module]
        links=''.join('<br><a href="'+html.escape(r['path'])+'">'+str(r['count'])+'项测试证据</a>' for r in current['reports'])
        for tid,requirement,accept in tasks:
            rows.append(f'<tr id="feedback-{tid}"><td>{tid}<br>{module}</td><td>{html.escape(title)}</td><td>{html.escape(requirement)}</td><td>{html.escape(accept)}</td><td data-feedback-status="{tid}">{current["status"]}{links}</td></tr>')
    evidence=json.loads((ROOT/'06_验证与后续工作/20261110改动文档逐项原文.json').read_text(encoding='utf8'))
    original=[]
    for p in evidence['paragraphs']:
        for image in p['images']: original.append('<figure><img loading="lazy" src="'+html.escape(image['path'])+'" alt="用户反馈截图"><figcaption>文档原图 '+html.escape(Path(image['path']).stem)+'</figcaption></figure>')
        if p['text'] and p['text']!='‘’': original.append('<p>'+html.escape(p['text'])+'</p>')
    section='''<!-- feedback-20261110:start -->
<section id="feedback-20261110"><h2>当前执行 11月10日改动文档</h2>
<p>已逐项阅读6组正文和9张原图，按5个模块依次实施。每模块先冒烟测试，再运行Python与本地Cloud两套完整回归；修复后重跑通过才推进下一模块。历史通过记录不代替本轮验证。</p>
<p>AI暂缓；生日/性别必填，称呼/时间选填，不恢复地点/时区/经纬度。未知时间不造精确盘。保留三地图4/4/3、计时和四语言。托管与飞书按用户最新安排暂不处理，本轮不发布公网，旧ZIP保留原快照。</p>
<div class="table-wrap"><table class="task-table"><thead><tr><th>编号</th><th>模块</th><th>原要求与实施范围</th><th>验收标准</th><th>状态与证据</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<p><a href="02_需求与设计参考/用户改动反馈-20261110.docx">原始反馈文档</a> · <a href="06_验证与后续工作/20261110改动文档逐项原文.json">逐图原文记录</a> · <a href="06_验证与后续工作/改动文档实施记录.json">本轮实施及测试记录</a> · <a href="http://127.0.0.1:8880/experience?lang=zh-Hans&amp;page=home">本机APP</a></p>
<details><summary>查看本轮全部原图与原文</summary>'''+''.join(original)+'''</details><p class="meta">最后更新 '''+html.escape(now)+'''；测试通过只说明本轮覆盖范围，视觉以用户实际查看为准。</p></section>
<!-- feedback-20261110:end -->'''
    table=ROOT/'改动任务表-2026-10-22.html'; text=table.read_text(encoding='utf8')
    if '<!-- feedback-20261110:start -->' in text: text=re.sub(r'<!-- feedback-20261110:start -->[\s\S]*?<!-- feedback-20261110:end -->',lambda _:section,text,count=1)
    else: text=text.replace('<body><main>','<body><main>\n'+section,1)
    table.write_text(text,encoding='utf8')
    print('Updated existing task table:',{k:v['status'] for k,v in record['modules'].items()})

if __name__=='__main__': main()
