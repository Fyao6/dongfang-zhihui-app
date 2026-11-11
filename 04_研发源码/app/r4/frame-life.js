// Functional frames follow the supplied layout; all destinations retain their real data and actions.
function flLifeHome(){
 return `<section class="page px-map-page j-life fl-map fl-life fl-map-exact" data-map="life">
 ${flMapHeader(flText('Life map','生命地图','生命地圖','སྲོག་གི་ས་ཁྲ།'),flText('Explore life through Zi Wei, Chinese classics and astrology.','从紫微、国学与星盘，探索生命的规律','從紫微、國學與星盤，探索生命的規律','ཙི་ཝེ་དང་རྒྱ་ནག་རིག་གནས། སྐར་རྩིས་བཅས་ལས་མི་ཚེའི་ཆོས་ཉིད་འཚོལ་བ།'))}
 ${flHero('chart',flText('My Zi Wei chart','我的紫微命盘','我的紫微命盤','ངའི་ཙི་ཝེ་སྐར་རྩིས་ཀྱི་ས་ཁྲ།'),flText('Chart · Interpretation · Themes','排盘 · 解读 · 主题分析','排盤 · 解讀 · 主題分析','ས་ཁྲ་བཟོ་བ། འགྲེལ་བཤད། བརྗོད་གཞི་དཔྱད་པ།'),'ziweiChart','px-map-hero fl-life-feature')}
 <div class="fl-pair">${flCard('book',flText('Chinese classics','国学智慧','國學智慧','རྒྱ་ནག་གི་གཞུང་རིག་ཤེས་རབ།'),flText('Classics · Culture · Life','经典 · 文化 · 生活','經典 · 文化 · 生活','གཞུང་ལུགས། རིག་གནས། འཚོ་བ།'),'classicsWisdom')}${flCard('spark',flText('Astrology exploration','星盘探索','星盤探索','སྐར་རྩིས་ཀྱི་ས་ཁྲ་འཚོལ་ཞིབ།'),flText('Western charts · Personality · Themes','西方星盘 · 性格 · 议题','西方星盤 · 性格 · 議題','ནུབ་ཕྱོགས་སྐར་རྩིས། གཤིས་ཀ བརྗོད་གཞི།'),'westernAstrology')}</div>
 ${flArchive('book',flText('My integrated life archive','我的生命整合档案','我的生命整合檔案','ངའི་མི་ཚེའི་ཟིན་ཐོ་སྤྱི་བསྡུས།'),flText('Charts, learning and life records','整合命盘、学习与人生记录','整合命盤、學習與人生記錄','སྐར་རྩིས་དང་སློབ་སྦྱོང་། མི་ཚེའི་ཟིན་ཐོ་མཉམ་བསྡུ།'),'lifeReview')}
 </section>`;
}

function flLifeArchive(){
 const items=Object.entries(state.wellness.intentions).sort((a,b)=>b[0].localeCompare(a[0]));
 const links=[
  ['chart',flText('My Zi Wei chart','我的紫微命盘','我的紫微命盤','ངའི་ཙི་ཝེ་སྐར་རྩིས་ཀྱི་ས་ཁྲ།'),state.daily.birthProfile?t('Details saved locally','资料已保存在本地'):t('Explore traditional symbols','了解传统文化符号'),'ziweiChart'],
  ['book',flText('Chinese classics','国学智慧','國學智慧','རྒྱ་ནག་གི་གཞུང་རིག་ཤེས་རབ།'),t('Read, reflect and revisit','阅读、觉察与回看'),'classicsWisdom'],
  ['spark',flText('Astrology exploration','星盘探索','星盤探索','སྐར་རྩིས་ཀྱི་ས་ཁྲ་འཚོལ་ཞིབ།'),flText('My exploration notes','我的探索记录','我的探索記錄','ངའི་འཚོལ་ཞིབ་ཟིན་ཐོ།'),'westernAstrology']
 ];
 return `<section class="page fl-detail fl-life-archive">${pxTop(flText('My integrated life archive','我的生命整合档案','我的生命整合檔案','ངའི་མི་ཚེའི་ཟིན་ཐོ་སྤྱི་བསྡུས།'),t('Your own records, not a diagnosis or a score.','这些是自己的记录，不是诊断或评分。'),'lifeResult')}
 <div class="fl-list">${links.map(([symbol,title,copy,to])=>`<button class="fl-list-row" data-action="go" data-to="${to}"><span class="fl-row-icon">${icon(symbol)}</span><span class="fl-row-copy"><b>${title}</b><small>${copy}</small></span>${icon('arrow')}</button>`).join('')}</div>
 <div class="section-title"><h3>${t('Return to my own words','回到我自己的文字')}</h3></div>
 ${items.length?`<div class="fl-list fl-history-list">${items.map(([date,entry])=>`<button class="fl-list-row history-card" data-action="history-view" data-kind="life" data-date="${esc(date)}"><span class="fl-row-icon">${icon('bookmark')}</span><span class="fl-row-copy"><b>${dateLabel(date)}</b><small>${esc(entry.intention||entry.direction||entry.strength||entry.relation||'')}</small></span>${icon('arrow')}</button>`).join('')}</div>`:`<div class="empty-state fl-empty"><h3>${t('Begin with one small record.','从一条小记录开始。')}</h3><p>${t('Your own words and feelings will appear here.','你的文字与感受，会保存在这里。')}</p></div>`}
 ${go(t('Write and revisit my life notes','记录与回看生活觉察'),'lifeJournal','full mt24')}
 ${mapArchiveNotes(['classics','western'])}
 </section>`;
}

function flLifeChart(){
 let source=ziweiChartPage().replace('class="page life4-page ziwei-page"','class="page life4-page ziwei-page fl-detail fl-life-chart"');
 source=source.replace(/<div class="ziwei-chart-actions">([\s\S]*?)<\/div>/,(_,actions)=>`<div class="ziwei-chart-actions fl-actions">${actions}${go(t('Culture & notes','文化与记录'),'ziweiCulture','secondary')}${actions.includes('data-action="ziwei-save"')?'':go(t('My notes','回看记录'),'lifeReview','secondary')}</div>`);
 return source;
}

function flLifeCulture(){
 const lessons=[
  ['compass',t('Life Palace · Ming Gong','命宫'),t('A central reference in the chart’s traditional interpretation. It is a cultural term, not a complete definition of who you are.','命盘传统解读的重要参照。它是文化术语，不是对一个人的完整定义。')],
  ['user',t('Body Palace · Shen Gong','身宫'),t('Another reference marked within a palace. It does not describe an organ or provide a physical assessment.','落在某个宫位中的另一项传统参照，不代表人体器官或身体检测结果。')],
  ['spark',t('Stars · Xing Yao','星曜'),t('Named symbols arranged according to traditional rules. A star name on this chart is not an observation of a physical object in the sky.','按传统规则排布的命名符号。盘中的星名不等于对天空实体天体的实时观测。')],
  ['chart',t('Twelve Palaces','十二宫'),t('Twelve areas organise the chart. Their traditional names offer a way to explore the culture; the reflection questions below are written for this app.','十二个宫位组织命盘结构。下方保留传统名称，觉察问题则是本应用提供的现代反思提示。')]
 ];
 let source=ziweiCulturePage().replace('class="page life4-page"','class="page life4-page fl-detail fl-life-culture"');
 source=source.replace(/<div class="life4-culture-lessons">[\s\S]*?<\/div>/,`<div class="life4-culture-lessons fl-list">${lessons.map(([symbol,title,copy])=>`<details class="fl-guide-row"><summary><span class="fl-row-icon">${icon(symbol)}</span><b>${title}</b>${icon('arrow')}</summary><p>${copy}</p></details>`).join('')}</div>`);
 source=source.replace('class="life4-palace-guide"','class="life4-palace-guide fl-actions"');
 return source;
}

const flLifeThemesBefore=screens.lifeThemes,flLifeTraitsBefore=screens.traits,flLifeJournalBefore=screens.lifeJournal;
Object.assign(screens,{lifeResult:flLifeHome,lifeReview:flLifeArchive,ziweiChart:flLifeChart,ziweiCulture:flLifeCulture,
 lifeThemes:()=>flLifeThemesBefore().replace('class="page"','class="page fl-detail fl-life-themes"'),
 traits:()=>flLifeTraitsBefore().replace('class="page"','class="page fl-detail fl-life-traits"'),
 lifeJournal:()=>flLifeJournalBefore().replace('class="page"','class="page fl-detail fl-life-journal"')
});
