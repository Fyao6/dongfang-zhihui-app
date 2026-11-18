from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, json

P = Path(__file__).resolve().parent.parent
D = P / '06_验证与后续工作'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
app_sha = sha(P / '03_当前APP/东方智慧-首页体验R4.html')
specs = [
    ('Python全量', '负责人优化建议-八字版本追溯-本轮全量回归结果.json', '本机全量验收', 60),
    ('Cloud全量', '负责人优化建议-八字版本追溯-公网适配全量回归结果.json', '本地Cloud全量验收', 60),
    ('Python专项', '负责人优化建议-B11实际专项-python.json', 'Python专项验收', 11),
    ('Cloud专项', '负责人优化建议-B11实际专项-cloud.json', 'Cloud专项验收', 11),
]
pending = []
for label, name, suffix, count in specs:
    r = json.loads((D / name).read_text(encoding='utf-8-sig'))
    r = r.get('latest', r)
    assert r['pass'] is True and r['passed'] == count and r['failed'] == 0, label
    if '全量' in label:
        assert r['buildHashes']['东方智慧-首页体验R4.html'] == app_sha
    else:
        assert r['identityUnchanged'] is True
        for n, h in r['sourceBuildTestHashes'].items():
            assert sha(P / n) == h, (label, n, 'changed')
        if label == 'Cloud专项':
            assert r['fontAsset']['status'] == 200, r['fontAsset']
    out = D / ('负责人优化建议-八字版本追溯-' + suffix + '.json')
    assert not out.exists(), out
    pending.append((label, r, out, count))
verified = {}
for label, r, out, count in pending:
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
    verified[label] = {'path': '06_验证与后续工作/' + out.name, 'sha256': sha(out), 'passed': count, 'at': r['at']}
record = {
    'at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
    'module': '负责人优化建议-八字版本追溯', 'pass': True,
    'scope': 'B11档案追溯阶段：输入/UTC/选项与引擎、规则、实现版本进入缓存键；真实结果指纹；旧档案只读保留，明确确认后重算另存并关联父档案；本人多标签协作保存与容量拒绝。',
    'verification': verified, 'app_sha256': app_sha,
    'source_hashes': {n: sha(P / n) for n in pending[2][1]['sourceBuildTestHashes']},
    'limitations': [
        '实际AI回复的版本绑定尚未接入，本阶段不宣称B11全部完成；纯元数据bind/status函数不替代真实客户端联调。',
        '原五个计算/出生源未改，出生输入保持四项。老师规则和30条确认样本尚未提供，teacherConfirmed恒为false。',
        'Web Locks仅保护当前同源同账户合作的八字写入；旧标签页和其他命盘不参与，不能宣称全局CAS。',
        '无法获取锁时停止写入；20份/4.5M容量超限明确拒绝，不静默丢旧记录。',
        '四语本机Chromium布局已检查，藏文仍需母语审校；真实模型请求0。',
    ],
    'failure_history': '首次全量各59/60，长版本说明挤占干支首屏；已改为主盘后折叠详情。专项首轮将七列误当六列已修夹具，四柱8格/七列14格/显式关闭流月六列12格均实测。历史失败保留。旧回归仅适配异步保存与历史只读/显式另存语义，保留原算法和辅助项断言。',
}
(D / '负责人优化建议-八字版本追溯-实施记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
f = D / '负责人优化建议-任务拆解.json'
tasks = json.loads(f.read_text(encoding='utf-8-sig'))
t = next(x for x in tasks if x['id'] == 'B11')
t['status'] = '进行中'
t['implementation_note'] = '档案缓存键/原规则版本/结果指纹已接，旧档案只读、确认后重算另存关联父档；多标签协作写与满容量拒绝实测。双端各60+11通过。实际AI回复版本绑定待独立联调，老师规则/30条样本未齐。'
f.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'pass': True, 'reports': len(verified), 'tasks': len(tasks)}, ensure_ascii=False))
