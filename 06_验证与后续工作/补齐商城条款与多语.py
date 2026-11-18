from pathlib import Path
R=Path(__file__).resolve().parent.parent/'04_研发源码/app/r4'
def edit(p,before,after):
 s=p.read_text(encoding='utf-8')
 if after in s:return
 assert s.count(before)==1,(p.name,before[:90])
 p.write_text(s.replace(before,after,1),encoding='utf-8')
p=R/'commerce-admin.js'
edit(p,'<label>发布状态<select name="status">','''<label class="wide">退款与使用条款<textarea name="refundPolicy" maxlength="2000">${esc(p.refundPolicy||'')}</textarea></label><details class="wide"><summary>简繁英藏商品文案</summary><div class="grid-form">${[['Zh','简体中文'],['Hant','繁体中文'],['En','英文'],['Bo','藏文']].map(([suffix,label])=>`<label>${label}标题<input name="title${suffix}" value="${esc(p['title'+suffix]||'')}" maxlength="120"></label><label>${label}说明<textarea name="description${suffix}" maxlength="5000">${esc(p['description'+suffix]||'')}</textarea></label>`).join('')}</div></details><label>发布状态<select name="status">''')
edit(p,"p.title,'required maxlength=\"160\"'","p.title,'required maxlength=\"120\"'")
s=p.read_text(encoding='utf-8').replace('max="100000000000"','max="1000000000"')
p.write_text(s,encoding='utf-8')
p=R/'commerce-ui.js'
edit(p,"(o.items||[]).map(x=>x.title||x.product?.title||'').join('、')","(o.items||[]).map(x=>coProductTitle(x)).join('、')")
edit(p,"esc(x.title||x.snapshot?.title||x.product?.title||x.skuId||'')","esc(coProductTitle(x)||x.skuId||'')")
edit(p,'</div><dl class="co-facts">${[[', '''</div><details class="co-order-terms"><summary>${coText('Purchase terms at checkout','成交时的购买与退款条款','成交時的購買與退款條款','ཉོ་སྐབས་ཀྱི་སྒྲིག་གཞི།')}</summary>${(o.items||[]).map(x=>`<p><strong>${esc(coProductTitle(x))}</strong><br>${esc(x.refundPolicy||coText('No formal refund terms have been confirmed for this test item.','该测试商品尚未确认正式退款条款。','該測試商品尚未確認正式退款條款。','ཚོད་ལྟའི་དངོས་རྫས་ཀྱི་སྒྲིག་གཞི་ད་དུང་ངོས་མ་འཛིན།'))}</p>`).join('')}</details><dl class="co-facts">${[[''')
print('Added catalog translations, editable refund terms and historical order terms.')
