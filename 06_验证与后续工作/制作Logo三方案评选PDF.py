from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4,landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from pypdf import PdfReader
import pypdfium2 as pdfium
import shutil,hashlib
root=Path(__file__).resolve().parent.parent
ref=root/'02_需求与设计参考'; qa=root/'06_验证与后续工作'
out=ref/'东方智慧APP-种子Logo三方案评选-20261030.pdf'
pdfmetrics.registerFont(TTFont('Chinese','C:/Windows/Fonts/simhei.ttf'))
W,H=landscape(A4);bg='#F8F5ED';ink='#293D3C';muted='#687873';line='#D9DDD4'
c=canvas.Canvas(str(out),pagesize=(W,H));c.setTitle('东方智慧APP | 种子Logo三方案评选');c.setAuthor('东方智慧APP项目')
items=[('A','本具','智慧本来就在里面','Logo规则重制-A本具-20261030.png','完整、横置的待萌发种子，将短流转脉络收在内部。','侧重个体内在潜能与日日滋养，保持安静、克制的第一感受。','内部脉络是否含蓄？种子是否易于识别？'),('B','相伴','独立生长，彼此滋养','Logo规则重制-B相伴-20261030.png','两颗独立种子彼此贴合，间隙形成柔和流转。','对应“各自生长、互相支持”的共修关系，强调陪伴与个体独立性。','两颗种子的关系是否有温度？是否符合松散陪伴的社群气质？'),('C','同源','同一根系，共同成长','Logo规则重制-C同源-20261030.png','两颗种子在共同基部相连，形成连续的整体。','对应“同源共生”的共修关系，强调共同场域、长期连接与共同成长。','连接结构是否自然？是否符合一体共生的产品方向？')]
def text(x,y,s,size=12,color=ink):
 c.setFillColor(HexColor(color));c.setFont('Chinese',size);c.drawString(x,y,s)
def para(s,x,y,width,size=12,color=ink,leading=None):
 style=ParagraphStyle('copy',fontName='Chinese',fontSize=size,leading=leading or size*1.65,textColor=HexColor(color),wordWrap='CJK')
 p=Paragraph(s,style);_,h=p.wrap(width,800);p.drawOn(c,x,y-h);return y-h

def page(n,title,subtitle):
 c.setFillColor(HexColor(bg));c.rect(0,0,W,H,fill=1,stroke=0)
 text(36,H-33,'东方智慧 APP  /  LOGO 方向评选',10,muted);text(36,H-73,title,25)
 text(36,H-99,subtitle,11,muted)
 c.setStrokeColor(HexColor(line));c.line(36,42,W-36,42)
 text(36,25,'概念评选稿  ·  2026.10.30  ·  未替换正式 APP 标识',9,muted)
 text(W-80,25,f'{n} / 4',9,muted)
page(1,'三个结构方向，一次对比','共同前提：种子为主，东方流转为隐性内核；待萌发、长期陪伴、日日滋养。')
col=(W-96)/3
for i,it in enumerate(items):
 key,name,tag,file,structure,meaning,question=it;x=36+i*(col+12)
 c.drawImage(str(ref/file),x,H-367,width=col,height=col,preserveAspectRatio=True,anchor='c')
 text(x,H-394,key+'  '+name,18)
 text(x,H-418,tag,12)
 para(structure,x,H-437,col-8,11,muted)
para('选择重点：先判断更符合产品定位的关系——个体内在成长（A）、独立个体的同行陪伴（B）、同源共生的共修场域（C）。',36,103,W-72,11)
c.showPage()
for idx,it in enumerate(items,2):
 key,name,tag,file,structure,meaning,question=it
 page(idx,key+'  '+name,tag)
 c.drawImage(str(ref/file),30,62,width=432,height=414,preserveAspectRatio=True,anchor='c')
 x=500;y=H-151
 text(x,y,'图形结构',13);y=para(structure,x,y-17,290,12)-28
 text(x,y,'产品含义',13);y=para(meaning,x,y-17,290,12)-28
 text(x,y,'建议关注',13);y=para(question,x,y-17,290,12)-28
 para('下方附单色与 APP 图标示意，供判断缩小后的识别感。',x,y,290,10,muted)
 if key=='C':para('反馈可直接写：首选 __，备选 __；希望保留 __，调整 __。',x,104,290,10,muted)
 c.showPage()
c.save()
reader=PdfReader(out);assert len(reader.pages)==4
for p in reader.pages:assert '本具' in p.extract_text() or '相伴' in p.extract_text() or '同源' in p.extract_text()
doc=pdfium.PdfDocument(str(out))
for i in range(len(doc)):
 image=doc[i].render(scale=1.2).to_pil();image.save(qa/f'Logo评选PDF核验-{i+1}.png')
desktop=Path.home()/'Desktop'/out.name
shutil.copy2(out,desktop);assert hashlib.sha256(out.read_bytes()).digest()==hashlib.sha256(desktop.read_bytes()).digest()
print(str(desktop));print('pages=4 bytes='+str(out.stat().st_size))
