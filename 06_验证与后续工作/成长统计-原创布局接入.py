from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[1]
source=root/'04_研发源码/app/r4/growth-tree.js'
raw=source.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='46e1daeccf8e473a31f7a944f709ce7e2d70fb74bb64b4714e72d751ff824423','One-time layout patch requires the reviewed statistics implementation.'
s=raw.decode('utf-8')
start=s.index('      let html=nav+')
end=s.index('      const undated=',start)
hero=r'''      let html=nav+'<section class="gs-summary" data-gs-summary data-from="'+bounds.from+'" data-to="'+bounds.to+'" '+Object.entries(summary).map(([key,value])=>'data-'+key+'="'+value+'"').join(' ')+'><p class="gs-masthead">'+escape(text('GROWTH · YOUR EVERYDAY','成长足迹 · 日常里的积累','成長足跡 · 日常裡的積累','འཚར་ལོངས་ཀྱི་རྗེས་ཤུལ།'))+'</p><h2 class="gs-message">'+escape(text('Every mindful moment leaves a trace.','把用心，留成看得见的日常。','把用心，留成看得見的日常。','ཉིན་རེའི་སེམས་འཇོག་ཟིན་ཐོར་འཇོག'))+'</h2><p class="gs-eyebrow">'+escape(text('Time in practice & listening','练习与聆听时长','練習與聆聽時長','ཉམས་ལེན་དང་ཉན་པའི་དུས་ཡུན།'))+'</p><div class="gs-total-time" aria-label="'+escape(duration(seconds))+'">'+[[h,text('h','小时','小時','ཆུ་ཚོད།')],[m,text('m','分','分','སྐར་མ།')],[s,text('s','秒','秒','སྐར་ཆ།')]].map(([n,unit])=>'<span><strong>'+escape(numberLabel(n))+'</strong><small>'+escape(unit)+'</small></span>').join('')+'</div><p class="gs-date-caption">'+escape(bounds.from+' — '+(bounds.to>today?today:bounds.to))+'</p><div class="gs-growth-footnote"><span><strong>'+escape(numberLabel(summary.days))+'</strong>'+escape(text('recorded days','个记录日','個記錄日','ཟིན་ཐོའི་ཉིན།'))+'</span><span><strong>'+escape(numberLabel(summary.records))+'</strong>'+escape(text('saved moments','条日常记录','條日常記錄','ཉིན་རེའི་ཟིན་ཐོ།'))+'</span></div><div class="gs-stat-grid">'+[['reflection',summary.reflections,text('Reflections','觉察','覺察','ལྟ་ཞིབ།')],['session',summary.practices,text('Practices','练习','練習','ཉམས་ལེན།')],['music',summary.listens,text('Listening','聆听','聆聽','ཉན་པ།')]].map(([key,value,label])=>button('', 'data-gs-stat="'+key+'"','gs-stat').replace('></button>','><span>'+escape(label)+'</span><strong>'+escape(numberLabel(value))+'</strong><span aria-hidden="true">›</span></button>')).join('')+'</div></section>';
      html+=chart(r,buckets(r.range,bounds,records,today));
      if(r.range==='all') {
        const years=buckets('all',bounds,records,today).filter(b=>b.records>0).reverse();
        if(years.length)html+='<section class="gs-year-strip"><h3>'+escape(text('Revisit a year','回望某一年','回望某一年','ལོ་གཅིག་ལ་ཕྱིར་ལྟ།'))+'</h3><div>'+years.map(y=>button(y.label,'data-gs-year="'+y.label+'"')).join('')+'</div></section>';
      }
'''
s=s[:start]+hero+s[end:]
start=s.index('    series.forEach((b,i)=>')
end=s.index("    html+='</div></div>",start)
bars=r'''    series.forEach((b,i)=>{
      const value=values[i],selected=r.selection?.from===b.from&&r.selection?.to===b.to,total=exactSeconds(b.seconds);
      const listeningShare=total>0n?Number(exactSeconds(b.listeningSeconds))/Number(total)*100:0;
      const layers=durationMetric?'<span class="gs-listening-segment" style="height:'+listeningShare+'%"></span><span class="gs-practice-segment" style="height:'+(100-listeningShare)+'%"></span>':'';
      const caption=b.from+' — '+b.to+' · '+(durationMetric?duration(value)+' · '+text('Practice ','练习 ','練習 ','ཉམས་ལེན། ')+duration(b.practiceSeconds)+' · '+text('Listening ','聆听 ','聆聽 ','ཉན་པ། ')+duration(b.listeningSeconds):numberLabel(value)+' '+text('records','条记录','條記錄','ཟིན་ཐོ།'));
      html+='<button type="button" class="gs-bar" data-gs-bar data-from="'+b.from+'" data-to="'+b.to+'" data-value="'+value+'" data-practice-seconds="'+b.practiceSeconds+'" data-listening-seconds="'+b.listeningSeconds+'" aria-pressed="'+selected+'" aria-label="'+escape(caption)+'"><span class="gs-bar-track"><span class="gs-bar-fill" style="height:'+(precise[i]>0n?Math.max(.6,Number(precise[i])/Number(axisMax)*100):0)+'%">'+layers+'</span></span><span class="gs-bar-label">'+escape(b.label)+'</span></button>';
    });
'''
s=s[:start]+bars+s[end:]
needle='    html+=\'<div class="gs-plot">'
start=s.index(needle)
legend=r'''    if(durationMetric)html+='<div class="gs-chart-legend"><span><i aria-hidden="true"></i>'+escape(text('Practice','练习','練習','ཉམས་ལེན།'))+'</span><span><i class="gs-listen-key" aria-hidden="true"></i>'+escape(text('Listening','聆听','聆聽','ཉན་པ།'))+'</span></div>';
'''
s=s[:start]+legend+s[start:]
s=s.replace("text('Your growth over time','成长分布','成長分布','འཚར་ལོངས་ཁྱབ་ཚུལ།')", "text('A rhythm of your own','日常的节奏','日常的節奏','ཉིན་རེའི་འགྲོས།')")
s=s.replace("records.filter(n=>r.filter==='all'||r.filter==='undated'?!n.day||r.filter==='all':n.recordKind===r.filter)","records.filter(n=>r.filter==='all'?true:r.filter==='undated'?!n.day:n.recordKind===r.filter)")
source.write_text(s,encoding='utf-8',newline='\n')
print('Original Eastern Wisdom journal layout and two-part chart applied; reviewed data logic retained.')
