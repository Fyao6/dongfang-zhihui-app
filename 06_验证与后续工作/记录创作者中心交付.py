from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,csv,os
r=Path(__file__).resolve().parent.parent;q=r/'06_验证与后续工作';now=datetime.now(timezone(timedelta(hours=8))).isoformat()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
local=read(q/'本轮全量回归结果.json')['latest'];cloud=read(q/'公网适配全量回归结果.json')['latest'];public=read(q/'创作者公网验收.json')
assert local['pass'] and local['passed']==56 and cloud['pass'] and cloud['passed']==56 and public['pass']
for name,digest in local['buildHashes'].items():assert hashlib.sha256((r/'03_当前APP'/name).read_bytes()).hexdigest()==digest,name
proofs={}
for name in ['创作者中心接口核验','创作者云端接口核验','创作者前端隔离核验','创作者公司后台界面核验','创作者真实界面联调','创作者云端真实界面联调']:
 d=read(q/(name+'.json'));assert d['pass'];proofs[name]={'pass':True,'checks':len(d['checks']),'at':d['at'],'scope':d.get('scope','')}
record={'at':now,'status':'published_and_verified','public_deployment_pending':False,'creator_url':public['base']+'/creator','admin_url':public['base']+'/admin','netlify_deploy_id':'6aea92540403e5da6591e1c7','sites_project_id':'appgprj_6ae7fec0e2588191ad3ca7369fb19d9a','sites_version_id':'appgprj_6ae7fec0e2588191ad3ca7369fb19d9a~appgver_8160b879b63c81918b5d6b8c443f34dd','sites_deployment_id':'appgdep_6aea923430cc8191a1ef48def0aba506','commit_sha':'28161ff457f019f40171471361c4570b01d9c021','local_full':{'passed':local['passed'],'failed':local['failed'],'at':local['at'],'buildHashes':local['buildHashes']},'cloud_full':{'passed':cloud['passed'],'failed':cloud['failed'],'at':cloud['at'],'buildHashes':cloud.get('cloudBuildHashes')},'specialized':proofs,'public':public,'limits':['AI模型、公司审核规则与知识库尚未配置，自动审核关闭；当前由人工复核','AI支持可配置的文字/章节审核；音视频和图片识别未接入，转人工复核','AI供应商模拟测试不能证明真实模型判断质量','仅统计APP从上线起真实采集的数据，浏览器访客不等于跨设备唯一人数','作品评论、支付与收益结算尚未实现','本轮未重打完整交付ZIP'],'backup':str(sorted((r/'07_历史版本仅供追溯').glob('创作者中心开发前-*.zip'))[-1].relative_to(r))}
archive=q/'创作者中心部署.tar.gz';record['archive']={'path':str(archive.relative_to(r)),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()};write(q/'创作者中心交付记录.json',record)
p=r/'05_后台与研发说明/Netlify站点身份.json';d=read(p);d.update(previous_deploy_id=d['deploy_id'],deploy_id=record['netlify_deploy_id'],checked_at=now,creator_url=record['creator_url'],latest_change='创作者中心、APP真实数据、入驻与两级内容审核',status='deployed');write(p,d)
note='\n\n2026年11月4日：创作者中心已开发并发布\n用户明确要求开发独立创作者后台，仅统计本APP账号数据，并采用AI初审与人工复核。现已实现APP入口、独立/creator工作台、申请认证、本人作品与数据、课程/图文/视频上传送审、申诉、关注互动与咨询；公司/admin新增创作者管理、创作者内容审核、审核规则与知识库。后端强制账号隔离、版本校验与素材归属，旧入口不能绕过审核。\n本机和真实本地Cloudflare环境完整回归各56项通过，两套创作者实际界面联调各8项通过，公网7项只读验收通过。具体测试范围和其他专项见06_验证与后续工作/创作者中心交付记录.json。AI模型与公司知识库当前未配置，自动审核默认关闭；文字审核接入可配置，音视频和图片尚不能自动完整审核，均转人工。未用模拟结果冒充真实AI接通。\n原账号数据保留，统计只从实际采集开始；未实现评论/收益结算，不伪造历史数据。本次未重打完整ZIP。使用说明在05_后台与研发说明/创作者中心使用与审核说明.txt。\n'
for rel in ['AGENTS.md','先读我.txt','03_当前APP/功能与使用说明-R4.txt','05_后台与研发说明/公网发布续接说明.txt']:
 p=r/rel;s=p.read_text(encoding='utf-8')
 if '2026年11月4日：创作者中心已开发并发布' not in s:p.write_text(s.rstrip()+note,encoding='utf-8')
p=r/'改动任务表-2026-10-22.html';s=p.read_text(encoding='utf-8');section='<section id="creator-center-delivery"><h2>2026-11-04 创作者中心</h2><p>已发布：独立创作者工作台、账号隔离、本人数据、作品提交/审核/申诉、入驻管理、公司审核规则和知识库。</p><p>本机/云端完整回归各56项及公网验收通过。真实AI模型和公司知识库待配置，音视频与图片转人工；不将模拟AI测试记为真实服务验收。</p><p><a href="https://eastern-wisdom-demo-fuyao.netlify.app/creator">打开创作者中心</a> · <a href="05_后台与研发说明/创作者中心使用与审核说明.txt">使用说明</a></p></section>'
if 'id="creator-center-delivery"' not in s:p.write_text(s.replace('</body>',section+'</body>'),encoding='utf-8')
p=r/'交接资料验证.json';d=read(p);d.update(updated_beijing=now,creator_center_delivery=record);write(p,d)
skip_dirs={'.git','__pycache__','node_modules','.venv','.wrangler','.sites-runtime','.netlify','dist','.next','.vinext','.cache','coverage'}
skip_suffixes={'.zip','.7z','.rar','.tar','.gz','.tgz','.pyc','.log','.db','.pem','.key','.pfx','.p12','.tsbuildinfo'};rows=[]
for current,dirs,names in os.walk(r):
 dirs[:]=[d for d in dirs if d not in skip_dirs and not (Path(current)/d).is_symlink()]
 for name in names:
  p=Path(current)/name
  if p.is_symlink() or p.suffix.lower() in skip_suffixes or any(x in name.lower() for x in ('.sqlite','.env','.dev.vars')) or name in {'资料校验清单.csv','原始来源与文件校验.json','.DS_Store','Thumbs.db'}:continue
  data=p.read_bytes();rows.append({'path':p.relative_to(r).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
rows.sort(key=lambda x:x['path'])
with (r/'资料校验清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['包内相对位置','字节数','SHA-256']);w.writerows((x['path'],x['bytes'],x['sha256']) for x in rows)
p=r/'原始来源与文件校验.json';d=read(p);d['files']=rows;d['current_revision']={'updated_beijing':now,'scope':'Creator center published, validated source and builds; private runtime excluded','public_deployment_pending':False,'delivery_record':'06_验证与后续工作/创作者中心交付记录.json'};write(p,d)
assert all(hashlib.sha256((r/x['path']).read_bytes()).hexdigest()==x['sha256'] for x in rows)
print(json.dumps({'pass':True,'manifest_files':len(rows),'local_full':local['passed'],'cloud_full':cloud['passed'],'public_checks':len(public['checks'])}))
