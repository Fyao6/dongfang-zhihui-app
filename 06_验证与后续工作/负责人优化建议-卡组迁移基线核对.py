from pathlib import Path
import json,hashlib
from datetime import datetime,timezone,timedelta
root=Path(__file__).resolve().parents[1]
d=root/'06_验证与后续工作'
p=d/'负责人优化建议-八字样本-最终交付核验.json'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='9d96d0f1b08f3fbff0128b282c0476783b10a33cd4b98a44e76a0a382cbc1894'
obj=json.loads(p.read_bytes()); files=dict(obj['verifiedSHA256']); files[str(p.relative_to(root)).replace('\\','/')]=hashlib.sha256(p.read_bytes()).hexdigest()
bad=[k for k,v in files.items() if not (root/k).is_file() or hashlib.sha256((root/k).read_bytes()).hexdigest()!=v]
assert not bad,bad
mutable={}
for k,v in files.items():
 if k.startswith(('03_当前APP/','04_研发源码/')) or k in ['AGENTS.md','公司同步-先读我.txt'] or (k.startswith('06_验证与后续工作/') and Path(k).name in ['公司同步-进度与记忆.json','负责人优化建议-交付收尾推进.json','负责人优化建议-98项任务来源.json','负责人优化建议-98项最终覆盖审计.json','负责人优化建议-98项最终覆盖审计.txt','东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx','负责人优化建议-全量回归.cjs']):
  mutable[k]=v
out={'pass':True,'stage':30,'at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'previousStage':29,'verifiedFiles':len(files),'baselineSHA256':files,'allowedMutable':mutable,'protectedSHA256':{k:v for k,v in files.items() if k not in mutable},'isolatedPreviewSHA256':hashlib.sha256((d/'负责人优化建议-隔离预览.sqlite3').read_bytes()).hexdigest()}
target=d/'负责人优化建议-卡组迁移-基线核对.json'
assert not target.exists()
target.write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({'pass':True,'verified':len(files),'mutable':len(mutable),'protected':len(out['protectedSHA256']),'reportSHA256':hashlib.sha256(target.read_bytes()).hexdigest()},ensure_ascii=False))
