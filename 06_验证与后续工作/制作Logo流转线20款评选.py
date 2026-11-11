from pathlib import Path
import json,hashlib,shutil,html
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3,A4,landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from pypdf import PdfReader
import pypdfium2 as pdfium
root=Path(__file__).resolve().parent.parent;ref=root/'02_需求与设计参考';qa=root/'06_验证与后续工作'
data=json.loads((ref/'Logo流转线20款提示词与记录-20261030.json').read_text(encoding='utf-8-sig'));records=data['records'];assert len(records)==20
files=[Path(r['path']) for r in records];assert all(f.exists() for f in files);assert len({hashlib.sha256(f.read_bytes()).hexdigest() for f in files})==20
pdfmetrics.registerFont(TTFont('Chinese','C:/Windows/Fonts/simhei.ttf'))
out=ref/'东方智慧APP-Logo流转线20款评选-20261030.pdf'
c=canvas.Canvas(str(out));c.setTitle('东方智慧APP | 流转线Logo20款评选');c.setAuthor('东方智慧APP项目')
def text(x,y,t,size=12,color='#29473E'):
 c.setFont('Chinese',size);c.setFillColor(HexColor(color));c.drawString(x,y,t)
def page(size,n,title,sub):
 c.setPageSize(size);w,h=size;c.setFillColor(HexColor('#F8F5ED'));c.rect(0,0,w,h,fill=1,stroke=0)
 text(34,h-34,'东方智慧 APP  /  LOGO 形态探索  /  2026.10.30',10)
 text(34,h-69,title,25);text(34,h-92,sub,11,'#66776E')
 c.setStrokeColor(HexColor('#D3DCCF'));c.line(34,39,w-34,39);text(34,23,'概念筛选稿 · 先选轮廓与流转关系，再精修比例和配色 · 正式APP未替换',9,'#66776E');text(w-77,23,f'{n} / 6',9)
 return w,h
w,h=page(landscape(A3),1,'20款总览','保留流转线的表达，展开种核、共修组合与抽象几何。编号为后续讨论的唯一索引。')
cw=(w-68)/5;rh=(h-169)/4
for i,r in enumerate(records):
 col=i%5;row=i//5;x=34+col*cw;y=h-111-row*rh
 side=min(cw-18,rh-24)
 c.drawImage(str(files[i]),x+(cw-side)/2,y-side,width=side,height=side,preserveAspectRatio=True)
 text(x+12,y-side-17,r['id']+'  '+r['name'],12)
c.showPage()
for group in range(5):
 start=group*4;w,h=page(landscape(A4),group+2,f'{start+1:02d} - {start+4:02d}  /  分组对比','统一颜色与展示尺寸，以便集中比较造型、留白和识别感。')
 cw=(w-80)/2;rh=(h-151)/2
 for j,r in enumerate(records[start:start+4]):
  col=j%2;row=j//2;x=34+col*(cw+12);top=h-111-row*rh;side=rh-24
  c.drawImage(str(files[start+j]),x+42,top-side,width=side,height=side,preserveAspectRatio=True)
  text(x+side+55,top-48,r['id'],24)
  text(x+side+55,top-76,r['name'],15)
  text(x+side+55,top-103,'候选 / 待精修',9,'#66776E')
 c.showPage()
c.save();assert len(PdfReader(out).pages)==6
reader=PdfReader(out);alltext='\n'.join(p.extract_text() for p in reader.pages)
assert all(r['name'] in alltext for r in records)
doc=pdfium.PdfDocument(str(out))
for i in range(len(doc)):doc[i].render(scale=1.05).to_pil().save(qa/f'Logo20款新探索PDF核验-{i+1}.png')
cards=''.join('<article><img loading="lazy" src="'+html.escape(f.name)+'" alt="'+r['id']+' '+r['name']+'"><label><input type="checkbox" value="'+r['id']+'"> '+r['id']+' · '+r['name']+'</label><a href="'+html.escape(f.name)+'" target="_blank">查看原图</a></article>' for r,f in zip(records,files))
pagehtml='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>流转线Logo20款对比</title><style>*{box-sizing:border-box}body{margin:0;background:#f8f5ed;color:#29473e;font:15px/1.8 'Microsoft YaHei',sans-serif}main{max-width:1400px;margin:30px auto;padding:20px}h1{font-size:27px}section{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}article{border:1px solid #d3dccf;padding:12px;border-radius:10px}img{width:100%;display:block}label{display:block;font-weight:600}a{color:#48695e;font-size:12px}.selection{position:sticky;top:0;background:#f8f5edf5;border-bottom:1px solid #bccbbd;padding:12px;z-index:2;margin-bottom:20px}input{accent-color:#29473e}@media(max-width:850px){section{grid-template-columns:repeat(2,minmax(0,1fr))}}</style><main><h1>20款流转线Logo形态探索</h1><p>先比较轮廓、留白和共修关系，再选择候选精修。点击勾选后可按编号反馈。</p><div class="selection" id="selection">已选：暂无</div><section>CARDS</section><p>内置imagegen独立生成的概念稿。完整提示词：<a href="Logo流转线20款提示词与记录-20261030.json">查看记录</a></p></main><script>const boxes=[...document.querySelectorAll('input')];let saved=[];try{saved=JSON.parse(localStorage.getItem('logo20-flow-selection')||'[]')}catch{}boxes.forEach(b=>b.checked=saved.includes(b.value));function update(){const values=boxes.filter(b=>b.checked).map(b=>b.value);document.getElementById('selection').textContent='已选：'+(values.join('、')||'暂无');try{localStorage.setItem('logo20-flow-selection',JSON.stringify(values))}catch{}}boxes.forEach(b=>b.onchange=update);update();</script></html>'''.replace('CARDS',cards)
(ref/'Logo流转线20款并排挑选-20261030.html').write_text(pagehtml,encoding='utf-8')
desktop=Path.home()/'Desktop'/out.name;shutil.copy2(out,desktop)
assert hashlib.sha256(out.read_bytes()).digest()==hashlib.sha256(desktop.read_bytes()).digest()
print(str(desktop));print('20 unique PNGs / 6 PDF pages / bytes='+str(out.stat().st_size))
