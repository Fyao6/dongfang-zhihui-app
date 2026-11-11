from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,datetime
r=next(p for p in Path.cwd().iterdir() if p.is_dir());v=r/'06_验证与后续工作';font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
cv=Image.new('RGB',(1720,1110),'#091a1d');d=ImageDraw.Draw(cv);d.text((38,24),'东方智慧 · 科技禅修试改',font=font(40),fill='#edf6ef');d.text((40,85),'改版前版本已归档 · 原创东方线纹 / 青玉柔光 / 身体数据层级 · 2026-10-27',font=font(22),fill='#abc2b9')
for i,(title,name)in enumerate([('改版前','改版前-首页.png'),('当前首页','试改-首页.png'),('身体地图','试改-身体地图.png'),('禅修练习','试改-禅修练习.png')]):
 x=30+i*425;d.rounded_rectangle((x,143,x+405,1090),radius=18,fill='#11282b',outline='#304b49');d.text((x+22,161),title,font=font(26),fill='#a5e5cd'if i else '#abc2b9');im=Image.open(v/name).convert('RGB');im.thumbnail((377,856),Image.Resampling.LANCZOS);cv.paste(im,(x+(405-im.width)//2,218))
cv.save(v/'科技禅修改版前后预览.png')
reg=json.loads((v/'本轮全量回归结果.json').read_text(encoding='utf-8'))['latest'];backup=json.loads((v/'科技禅修改版前存档校验.json').read_text(encoding='utf-8'))
report={'atBeijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'status':'用户授权试改，待视觉反馈','changes':['原创参数化东方对称SVG线纹；未复制第三方代码或素材','墨青、青玉、暖金、雾紫统一日夜主题','首页、三大地图、AI、钟声签到、音乐及个人页统一视觉','装饰线纹尊重减少动态效果；练习装饰沿用真实播放暂停状态','设备等待、授权和真实测量数据分开呈现','保留五项快捷功能首页结束位置、全局自动计时与磁吸规则','修复旧测试脚本写死用户名与Edge依赖的问题，当前机器用Chromium回归'],'regression':{'pass':reg['pass'],'passed':reg['passed'],'failed':reg['failed'],'browser':reg['coverage']['browser'],'backendUnitChecks':5,'liveAI':False,'realHardware':False},'rollbackArchive':backup['archive'],'rollbackArchiveSha256':backup['archiveSha256'],'archivedFilesVerified':backup['verifiedFiles'],'archivedDatabaseIntegrity':backup.get('archivedDatabaseIntegrity'),'preview':'科技禅修改版前后预览.png','localPreview':'http://127.0.0.1:8765/app'}
(v/'科技禅修试改交付记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved clean before/after preview and actual delivery record.')
