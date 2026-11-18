"""Apply the approved v1.0 presentation contract without changing chart rules."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SRC=ROOT/'04_研发源码/app/r4'

def replace(text,before,after):
    assert text.count(before)==1, 'Source anchor must be unique: '+before[:100]
    return text.replace(before,after,1)

p=SRC/'life-chart-bazi.js'
s=p.read_text(encoding='utf-8')
s=replace(s,'data-lcb-layout="reference"','data-lcb-layout="reference" data-lcb-presentation="four-pillars"')
p.write_text(s,encoding='utf-8')

p=SRC/'life-chart-bazi-layout.js'
s=p.read_text(encoding='utf-8')
s=s.replace('// Reference-proportion Ba Zi workspace. The default table exposes all seven rows.','// Four natal pillars by default; complete comparisons remain available on demand.')
s=replace(s,'function lcbBoard(result,state,timing){', '''function lcbVisibleBoardColumns(comparison,state){const view=lcbTimelineView(state);return comparison.columns.slice(0,view.fullBoard?(view.showFlowMonth?7:6):4);}
function lcbElementLegend(){return `<div class="lcb-element-legend" data-lcb-element-legend aria-label="${lcbText('Five elements','五行图例','五行圖例','འབྱུང་བ་ལྔ།')}">${[['wood',lcbText('Wood','木','木','ཤིང་།')],['fire',lcbText('Fire','火','火','མེ།')],['earth',lcbText('Earth','土','土','ས།')],['metal',lcbText('Metal','金','金','ལྕགས།')],['water',lcbText('Water','水','水','ཆུ།')]].map(([element,label])=>`<span data-element="${element}"><i aria-hidden="true"></i>${label}</span>`).join('')}</div>`;}
function lcbBoard(result,state,timing){''')
s=replace(s,'columns=comparison.columns.slice(0,view.showFlowMonth?7:6)','columns=lcbVisibleBoardColumns(comparison,state)')
s=replace(s,'<section class="lcb-board" data-lcb-board><div','<section class="lcb-board" data-lcb-board data-lcb-board-mode="${view.fullBoard?\'full\':\'natal\'}"><div')
s=replace(s,"${lcbText('Natal and selected period table','四柱与所选运年表','四柱與所選運年表','ཀ་བ་བཞི་དང་དུས་རབས་རེའུ་མིག')}","${view.fullBoard?lcbText('Natal and selected periods','四柱与所选流运对照','四柱與所選流運對照','ཀ་བ་བཞི་དང་དུས་རབས།'):lcbText('Four natal pillars','本命四柱','本命四柱','སྐྱེས་དུས་ཀ་བ་བཞི།')}")
s=replace(s,'<span>${titles[p.key]}</span><small>${p.available?stamps[p.key]:\'—\'}</small>','<span>${titles[p.key]}</span>${view.fullBoard?`<small>${p.available?stamps[p.key]:\'—\'}</small>`:\'\'}')
s=replace(s,"lcbText('Hidden stems & details','藏干 · 纳音等','藏干 · 納音等','སྦས་སྡོང་དང་ཞིབ་ཕྲ།')","lcbText('Show details','展开详细字段','展開詳細欄位','ཞིབ་ཕྲ་སྟོན།')")
s=replace(s,'</button><button type="button" data-lcb-action="flow-month"','</button><button type="button" data-lcb-action="board-mode" aria-pressed="${!!view.fullBoard}" aria-controls="lcb-main-board"><span class="ew-disclosure-label">${view.fullBoard?lcbText(\'Four pillars\',\'回到四柱\',\'回到四柱\',\'ཀ་བ་བཞིར་ལོག\'):lcbText(\'Full comparison\',\'完整盘面对照\',\'完整盤面對照\',\'ཆ་ཚང་བསྡུར་བ།\')}</span>${icon(\'chevron\',\'ew-disclosure-icon\')}</button>${view.fullBoard?`<button type="button" data-lcb-action="flow-month"')
s=replace(s,"${icon('chevron','ew-disclosure-icon')}</button></div></section>`;","${icon('chevron','ew-disclosure-icon')}</button>`:''}</div>${lcbElementLegend()}</section>`;")
s=replace(s,'const start=result.startFortune;','const start=result.startFortune,range=year?lcbMonthInterval(year.year,monthIndex):null;')
s=replace(s,'<section class="lcb-time-axis" data-lcb-time-axis aria-label=','<section class="lcb-time-axis" data-lcb-time-axis aria-label=')
s=replace(s,' <section class="lcb-time-stage" data-lcb-stage="period"', ''' ${range?`<p class="lcb-selected-range" data-lcb-selected-range><strong>${year.year} · ${esc(range.startJie)}—${esc(range.endJie)}</strong><span>${esc(range.start)} — ${esc(range.end)}</span></p>`:''}
 <section class="lcb-time-stage" data-lcb-stage="period"''')
s=replace(s,'columns=comparison.columns.slice(0,lcbTimelineView(state).showFlowMonth?7:6)','columns=lcbVisibleBoardColumns(comparison,state)')
before="(annotations.columns.find(a=>a.key===c.key)?.stars||[]).map(entry=>`<details data-lcb-marker=\"${entry.rule}\"><summary>${esc(entry.name)}</summary>${lcbMarkerEvidence(entry,sourceById[entry.source])}</details>`).join('')||'<span class=\"lcb-no-star\">—</span>'"
s=replace(s,before,'lcbStarGroup(annotations.columns.find(a=>a.key===c.key),sourceById)')
s=replace(s,"context=columns.filter(c=>c.role==='flow').map(c=>titles[c.key]+' '+(c.key==='flowYear'?year.year+' ':'')+(c.available?c.ganZhi:'—')).join(' · ')","context=columns.some(c=>c.role==='flow')?columns.filter(c=>c.role==='flow').map(c=>titles[c.key]+' '+(c.key==='flowYear'?year.year+' ':'')+(c.available?c.ganZhi:'—')).join(' · '):lcbText('Natal pillars · use Full comparison for selected periods','本命四柱 · 完整盘面对照可查看所选流运','本命四柱 · 完整盤面對照可查看所選流運','སྐྱེས་དུས་ཀ་བ་བཞི། དུས་རབས་ཆ་ཚང་བསྡུར་བར་ལྟ།')")
s=replace(s,'function lcbAnnotationPanel(result,state,timing){', '''function lcbStarGroup(column,sourceById){const entries=column?.stars||[];if(!entries.length)return '<span class="lcb-no-star">—</span>';return `<details class="lcb-star-group" data-lcb-star-group="${column.key}"><summary><b>${entries.length}</b> ${lcbText('markers','项','項','རྣམས།')}<span class="lcb-star-expand">${lcbText('View','查看','查看','ལྟ་བ།')}</span></summary><div>${entries.map(entry=>`<details data-lcb-marker="${entry.rule}"><summary>${esc(entry.name)}</summary>${lcbMarkerEvidence(entry,sourceById[entry.source])}</details>`).join('')}</div></details>`;}
function lcbAnnotationPanel(result,state,timing){''')
p.write_text(s,encoding='utf-8')
print('Applied the four-pillar display, optional complete board, element legend and counted star groups. Calculation rules unchanged.')
