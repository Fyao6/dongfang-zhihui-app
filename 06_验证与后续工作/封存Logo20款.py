from pathlib import Path
import json,zipfile,hashlib
from datetime import datetime,timezone,timedelta
p=next(Path.cwd().iterdir());ref=p/'02_需求与设计参考';qa=p/'06_验证与后续工作'
files=[ref/f'Logo20款-{i:02d}.png' for i in range(1,21)]+[ref/'Logo20款对比挑选.html',ref/'Logo20款编号与含义.json',ref/'Logo20款产品理念与完整提示词.json']+[qa/f'Logo20款-对比{i}.png' for i in range(1,5)]+[qa/'Logo20款-总览.png']
assert all(f.exists() for f in files)
with zipfile.ZipFile(ref/'Logo20款评审包-20261028.zip','w',zipfile.ZIP_DEFLATED) as z:
 for f in files:z.write(f,f.name)
with zipfile.ZipFile(ref/'Logo20款评审包-20261028.zip') as z:assert z.testzip() is None
f=ref/'Logo简化重跑记忆.json';r=json.loads(f.read_text(encoding='utf-8'));r['previous6ConceptOutput']=r['output'];r.update(status='按用户要求扩展为20套独立候选，已核对全部原图与对比展示，等待用户选择',output='02_需求与设计参考/Logo20款对比挑选.html',latestRequest='弄二十套案例，原6款太少不好选择',method='built-in image_gen；20款分别生成；浏览器制作4张对比图与1张总览',promptFile='02_需求与设计参考/Logo20款产品理念与完整提示词.json',concepts=json.loads((ref/'Logo20款编号与含义.json').read_text(encoding='utf-8')),review='20张均独立保存；20个编号及中文含义已完整显示；暂选、放大、手机布局及浏览器运行检查通过。生成位图为候选概念，非最终矢量定稿。');f.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
record={'atBeijing':datetime.now(timezone(timedelta(hours=8))).isoformat(),'requested':20,'delivered':20,'generation':'20 independent built-in image_gen calls','verification':json.loads((qa/'Logo20款展示验证.json').read_text(encoding='utf-8')),'files':[{'path':str(f.relative_to(p)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in files],'bundle':'02_需求与设计参考/Logo20款评审包-20261028.zip','productionAppChanged':False}
(qa/'Logo20款交付记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('20 distinct originals, four comparison boards, overview, gallery and review bundle saved.')
