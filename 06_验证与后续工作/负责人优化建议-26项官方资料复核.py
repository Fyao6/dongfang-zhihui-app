from pathlib import Path
from datetime import datetime, timezone
import json, re
P = Path(__file__).resolve().parent.parent
D = P / '06_验证与后续工作'
source = json.loads((P / '02_需求与设计参考/负责人优化建议-逐段原文.json').read_text(encoding='utf-8-sig'))
facts = [
('已读相关原文', '官方2026-10-17发布页确认DeepSeek-V4.1-Flash-1017名称，并链接官方开源仓库；没有下载权重或执行部署。'),
('已读相关原文', 'deepseek-ai官方模型卡标明仓库和权重MIT许可，并列最小推理入口；许可证可用不代表当前机器能运行。'),
('已读相关原文', '推理README明确是可读参考实现，并非生产服务引擎；不能据此宣称流式服务、并发和成本已验收。'),
('已读相关原文', '商业条款纳入DPA；经第三方平台访问时受第三方条款约束。实际API运营方/转发关系仍待核。'),
('已读相关原文', '商业API通常30日内清除输入输出，但Files、另行协议、政策和法律等有例外；产品聊天及违规保留另有期限，不能统一写成零留存。'),
('已读相关原文', '3.1要求数字解锁走适用内购；3.1.3(d)区分实时两人和一对多，(e)实物/线下服务；外链规则随商店地区和资格不同，未据此打开外部收银。'),
('已读相关原文', 'Play数字功能/订阅使用适用结算系统；实物和线下服务另列，区域例外附条件。需先确认实际发行端和国家。'),
('已读相关原文', '一对一付费在线服务例外要求双方个人且不可在Play应用内回放；混合SKU仍需按数字/实物实际构成审核。'),
('已读相关原文', 'Apple官方取消入口适用于经Apple/App Store购买的订阅；本APP不能凭本地取消按钮伪称Apple续费已停。'),
('已读相关原文', 'Google说明卸载不取消订阅；应从购买所用Google账号管理。取消后权益期限和退款是不同流程。'),
('已读相关原文', 'Stripe全球可用性页面列商户地区；页面自动重定向en-nl，不能把用户所在地等同商户可签约地区。'),
('已读相关原文', 'Stripe限制业务按国家/业务分类，页面含部分国家对psychic/fortune类服务限制；自动重定向en-pl，仍须实际主体地区和业务书面审核，不能全地区一概推定。'),
('已读相关原文', 'Stripe回调须用原始请求体和官方验签机制；事件可能重复和乱序，按事件/业务对象去重并异步处理。当前代码无正式回调验收。'),
('已读相关原文', '官方.md说明API v1同键保存首次执行结果（含500），至少24小时后可清理；参数冲突需拒绝。API v2重试语义不同，不能混称。'),
('已读相关原文', 'Play订阅后端以purchases.subscriptionsv2.get为最新状态来源；RTDN是查询触发。须服务端验单及确认购买，不能仅凭通知/客户端发权益。'),
('已读相关原文', 'AWS区域选择应满足服务和用户位置；账号决定可用区域，中国/GovCloud与普通账号存在隔离。尚未查询用户云账号。'),
('已读相关原文', 'Google区域与可用区是不同故障范围；跨区/跨域冗余和配额需实际配置，选了区域不等于已获得GPU或容灾。'),
('已读相关原文', 'RDS单备用Multi-AZ实例负责故障接管而不服务读；双备用集群能力不同。现有SQLite/D1没有因此变成RDS HA。'),
('已读相关原文', 'Cloud SQL HA为同区域主备跨区同步；故障切换会断开连接，备份/PITR仍单列。首次抓取后两次超时，经hl=en官方地址复读相关原文。'),
('已读相关原文', 'CloudFront从边缘缓存或源站分发；没有证据说明会员私有媒体已配置正确的鉴权和缓存策略。'),
('已读相关原文', 'Cloud CDN与支持的外部应用负载均衡器配合；不是给私有视频添一个公开URL即可。未创建真实CDN配置。'),
('已打开但不可读', 'AWS计算器入口可达但抓取0行；未创建估算，不能声称已读交互项、取得报价或获批预算，须实际规格/账号价格复核。'),
('已读入口', 'Google计算器入口要求添加配置产品生成估算；账单账号价格需登录。未配置采购清单，月费仍未知。'),
('已读相关原文', 'AWS各区域实例类型表仅证明文档列出可用类型；实例实际配额、区内库存和租用价尚未核验。'),
('已读相关原文', 'Google GPU型号随区域/区变化；AI zones须可见且有预留容量，列表不保证当前项目能租到GPU。'),
('已读相关原文', 'PayPal美国AUP标注2026-11-04更新；直播、市场平台和分销等列审批条件。原文是美国页，实际商户所在地条款及业务批准仍未确定。'),
]
refs = [p for p in source['paragraphs'] if re.match(r'^S\d{2}\s', p['text'])]
assert len(refs) == len(facts) == 26
rows = []
for p, (status, fact) in zip(refs, facts):
    url = re.search(r'HYPERLINK "([^"]+)"', ' '.join(p['fields'])).group(1)
    rows.append({'id': p['text'].split()[0], 'source_id': p['id'], 'title': p['text'].split('\n')[0], 'url': url, 'status': status, 'finding': fact})
report = {'at_utc': datetime.now(timezone.utc).isoformat(), 'method': '本轮web工具逐个打开全部原链接，按相关章节find/open复读；Stripe幂等补官方.md，Cloud SQL补官方hl=en。记录的是相关实施条件复核，不宣称全部链接全文/交互已读。', 'references_attempted': 26, 'unreadable': ['S22'], 'external_purchases_or_writes': False, 'links': rows, 'remaining': ['AWS交互计算器不可读；两家云实际配置估算尚无。', '尚未收到另行更新的规则/分佣文档，未做不存在材料的差异比对。', '实际发行地区、商户主体、签约/审核、接口版本和厂商服务合同仍须在上线前复核，不能把资料阅读等同于上线许可。']}
(D / '负责人优化建议-26项官方资料复核.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['负责人v1.0引用S01—S26官方资料复核', report['at_utc'], report['method'], '']
for r in rows:
    lines += [r['title']+'（'+r['source_id']+'）', r['url'], r['status']+'：'+r['finding'], '']
lines += ['仍未完成：'] + report['remaining']
(D / '负责人优化建议-26项官方资料复核.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
f = D / '负责人优化建议-任务拆解.json'
tasks = json.loads(f.read_text(encoding='utf-8-sig'))
t = next(x for x in tasks if x['id'] == 'X04')
t['status'] = '进行中'
t['implementation_note'] = '26个原官方链接均逐个打开复核相关章节并存证；S22计算器0行不可读、实际报价未做，S23只读入口未估价。PayPal页11月4日更新已登记。新规则/分佣补充文档及实际主体地区未齐，上线前复核未结束。'
f.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'references': len(rows), 'unreadable': report['unreadable'], 'task': 'X04进行中'}, ensure_ascii=False))
