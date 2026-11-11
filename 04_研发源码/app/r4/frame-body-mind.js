/* Map entrances match the user-provided three references exactly. */
function flBodyMap(){
 return `<section class="page px-map-page j-body fl-map fl-body fl-map-exact" data-map="body">
 ${flMapHeader(flText('Body map','身体地图','身體地圖','ལུས་ཀྱི་ས་ཁྲ།'),flText('Find balance through Chinese traditions, Tibetan traditions and tea.','以中医、藏医与茶道，修复身心的平衡','以中醫、藏醫與茶道，修復身心的平衡','རྒྱ་ནག་གསོ་རིག་དང་བོད་ཀྱི་གསོ་རིག ཇའི་རིག་གནས་བཅས་ལས་ལུས་སེམས་སྙོམས་པ།'))}
 ${flHero('leaf',flText('Tea life','茶道生活','茶道生活','ཇའི་རིག་གནས་དང་འཚོ་བ།'),flText('A cup of tea, a moment of balance','一杯茶，调和身心','一杯茶，調和身心','ཇ་ཕོར་པ་གང་གིས་ལུས་སེམས་སྙོམས་པ།'),'teaLife','px-map-hero j-body-intro')}
 <div class="fl-pair">${flCard('leaf',flText('Chinese wellbeing','中医养护','中醫養護','རྒྱ་ནག་གསོ་རིག་གི་གཅེས་སྐྱོང་།'),flText('Constitution · Food culture · Daoyin','体质 · 食养 · 导引','體質 · 食養 · 導引','ལུས་ཁམས། ཟས་ཀྱི་རིག་གནས། ཏའོ་ཡིན།'),'chineseCare')}${flCard('heart',flText('Tibetan wellbeing','藏医养护','藏醫養護','བོད་ཀྱི་གསོ་རིག་གཅེས་སྐྱོང་།'),flText('Breathing · Care · Everyday wisdom','调息 · 康养 · 生活智慧','調息 · 康養 · 生活智慧','དབུགས་སྙོམས། གཅེས་སྐྱོང་། འཚོ་བའི་ཤེས་རབ།'),'tibetanCare')}</div>
 ${flArchive('book',flText('My body care archive','我的身体养护档案','我的身體養護檔案','ངའི་ལུས་གཅེས་སྐྱོང་གི་ཟིན་ཐོ།'),flText('Care, practice and changes in how you feel','记录养护、练习与身心变化','記錄養護、練習與身心變化','གཅེས་སྐྱོང་དང་ཉམས་ལེན། ལུས་སེམས་ཀྱི་འགྱུར་བ་ཟིན་འགོད།'),'bodyHistory')}
 </section>`;
}
function flMindMap(){
 return `<section class="page px-map-page j-mind fl-map fl-mind fl-map-exact" data-map="mind">
 ${flMapHeader(flText('Mind map','心智地图','心智地圖','སེམས་ཀྱི་ས་ཁྲ།'),flText('Settle your mind and deepen awareness through care and meditation.','在疗愈与禅修中，安顿心灵、提升觉察','在療癒與禪修中，安頓心靈、提升覺察','གཅེས་སྐྱོང་དང་སྒོམ་སྒྲུབ་ཁྲོད་སེམས་ཞི་ཞིང་དྲན་ཤེས་གོང་འཕེལ།'))}
 <div class="fl-stack">${flHero('heart',flText('Healing space','疗愈空间','療癒空間','སེམས་གསོའི་བར་སྟོང་།'),flText('Emotional support · Relaxation · Inner growth','情绪陪伴 · 放松舒缓 · 内在建设','情緒陪伴 · 放鬆舒緩 · 內在建設','ཚོར་སྣང་ལ་རོགས་སྐྱོར། ལྷོད་ལྷོད། ནང་སེམས་སྐྱེད་སྲིང་།'),'healingSpace','px-map-hero j-mind-intro')}${flHero('lotus',flText('Meditation practice','禅修修习','禪修修習','ཞི་གནས་ཉམས་ལེན།'),flText('Courses · Daily sitting · Awareness','系统课程 · 日常静坐 · 觉照提升','系統課程 · 日常靜坐 · 覺照提升','རིམ་པའི་སློབ་ཚན། ཉིན་རེའི་ཞི་གནས། དྲན་ཤེས་གོང་འཕེལ།'),'meditationStudy')}</div>
 ${flArchive('book',flText('My mind practice archive','我的心智修习档案','我的心智修習檔案','ངའི་སེམས་ཉམས་ལེན་གྱི་ཟིན་ཐོ།'),flText('Practice records, learning progress and reflections','练习记录、学习进度与心得','練習記錄、學習進度與心得','ཉམས་ལེན་ཟིན་ཐོ་དང་སློབ་སྦྱོང་འཕེལ་རིམ། ཉམས་མྱོང་།'),'mindHistory')}
 </section>`;
}

function flPracticeRows(keys){
 return `<div class="fl-list px-practice-choices">${keys.filter(key=>practices[key]).map(key=>{
  const practice=practices[key];
  return `<button class="fl-list-row" data-action="start-practice" data-practice="${key}"><span class="fl-row-icon">${icon(practice.icon||'leaf')}</span><span class="fl-row-copy"><b>${practiceName(key)}</b><small>${minutes(practice.seconds)}</small></span>${icon('play')}</button>`;
 }).join('')}</div>`;
}

function flBodyCulture(){
 return `<section class="page body4-page fl-detail fl-body-culture">
 ${pxTop(t('Daoyin','中医导引'),flText('Body, breath and attention.','身体、呼吸与注意力。','身體、呼吸與注意力。','ལུས་དང་། དབུགས། དོ་སྣང་།'),'body')}
 <article class="card fl-detail-card">
 <h2>${t('Choose a next step','可以选择的下一步')}</h2>
 ${flPracticeRows(['breath','scan','ground'])}
 ${button(t('Begin seated practice · 3 min','开始静坐调息 · 3 分钟'),'body4-start','data-practice="daoyin"','full')}
 </article>
 <details class="fl-guide-details"><summary>${pxText('了解中医与导引文化','About Chinese traditions and daoyin')}</summary><p>${pxText('导引是东方传统中结合身体活动、呼吸与注意力的练习方式。这里提供日常觉察练习，可从短时体验开始。','Daoyin brings together movement, breathing and attention. Begin here with a short everyday awareness practice.')}</p><a href="https://www.nccih.nih.gov/health/qigong-what-you-need-to-know" target="_blank" rel="noopener">NCCIH · Qigong</a></details>
 ${flArchive('book',flText('Body & practice records','身体与练习记录','身體與練習記錄','ལུས་དང་ཉམས་ལེན་གྱི་ཟིན་ཐོ།'),t('Revisit my body records','回看身体记录'),'bodyHistory')}
 </section>`;
}

function flBodyRecovery(){
 return `<section class="page body4-page fl-detail fl-body-recovery">
 ${pxTop(t('Sleep & stress','睡眠与压力'),flText('Choose the care you need now.','给此刻，合适的照顾。','給此刻，合適的照顧。','སྐབས་འདིར་རང་ལ་འཚམ་པའི་གཅེས་སྐྱོང་།'),'body')}
 <article class="card fl-detail-card">
 <h2>${t('Choose a restorative practice','选择修复练习')}</h2>
 ${flPracticeRows(['sleep','breath','scan'])}
 ${go(t('Choose a soundscape','选择放松音景'),'music','full')}
 </article>
 ${flArchive('book',flText('Body & practice records','身体与练习记录','身體與練習記錄','ལུས་དང་ཉམས་ལེན་གྱི་ཟིན་ཐོ།'),t('Revisit my practice records','回看练习记录'),'bodyHistory')}
 </section>`;
}

function flZenPractice(){
 return `<section class="page mind4-page fl-detail fl-zen">
 ${pxTop(t('Meditation','禅修静心'),pxText('选一段时间，安住此刻','Choose a little time to be here'),'mind')}
 <article class="card fl-detail-card">
 <div class="fl-course-intro"><span class="fl-row-icon">${icon('lotus')}</span><div><h2>${t('Return gently','让注意力轻轻回来')}</h2><p>${pxText('自然呼吸，按自己的节奏','Natural breathing, at your own pace')}</p></div></div>
 ${flPracticeRows(['breath','zen','focus'])}
 ${button(t('Begin five-minute practice','开始五分钟静坐'),'start-practice','data-practice="zen"','full')}
 </article>
 ${flArchive('book',t('Learning','修习课程'),t('Read about Chan in daily life','阅读：禅修与日常觉察'),'buddhistCourses')}
 ${flArchive('book',t('Mood & reflection','情绪与觉察'),t('Revisit mood and reflection','回看情绪与觉察'),'mindHistory')}
 </section>`;
}

function flMindCourses(){
 return `<section class="page mind4-page fl-detail fl-mind-courses">
 ${pxTop(t('BUDDHIST LEARNING','佛法修习'),flText('Read · reflect · practise','阅读 · 反思 · 实践','閱讀 · 反思 · 實踐','ཀློག་པ། བསམ་གཞིག ཉམས་ལེན།'),'mind')}
 <div class="fl-list daily-lesson-list">${mind4Lessons.map((lesson,index)=>`<article class="fl-list-row daily-lesson-card mind4-course"><span class="fl-row-icon">${icon(lesson.symbol)}</span><div class="fl-row-copy"><span class="eyebrow">0${index+1}</span><h3>${ewI18n.content(lesson,'',state.lang)}</h3><p>${ewI18n.content(lesson,'summary',state.lang)}</p>${button(t('Read this lesson','开始阅读'),'lesson-open',`data-id="${lesson.id}"`,'link')}</div></article>`).join('')}</div>
 <p class="mind4-context">${t('These texts are original introductions, not scripture quotations or authorised teachings by a master. Reference links accompany each reading.','内容为原创入门导读，不是经典原句或大师授权开示。每篇附有参考资料，便于继续了解。')}</p>
 </section>`;
}

function flRecordScreen(kind){
 const store=kind==='body'?'body':'mind';
 const month=today().slice(0,7);
 const entries=Object.keys(state.wellness[store]||{}).filter(date=>date.startsWith(month));
 const relevant=kind==='body'?['sleep','scan','daoyin','ground','breath']:['zen','breath','ground','focus'];
 const sessions=(state.wellness.sessions||[]).filter(session=>String(session.date||'').startsWith(month)&&relevant.includes(session.practice));
 const seconds=sessions.reduce((total,session)=>total+Math.max(0,Number(session.seconds)||0),0);
 const metrics=`<article class="card fl-record-summary"><h2>${flText('This month','本月记录','本月記錄','ཟླ་འདིའི་ཟིན་ཐོ།')}</h2><div class="fl-actions fl-record-metrics"><div><small>${kind==='body'?t('Body check-in','身心自评'):t('Emotional notes','情绪觉察')}</small><b>${entries.length}</b></div><div><small>${t('Practice moments','练习时刻')}</small><b>${sessions.length}</b></div><div><small>${t('Practice time','练习时间')}</small><b>${formatTime(seconds)}</b></div><div><small>${flText('Completed practices','完成练习','完成練習','ཉམས་ལེན་མཇུག་སྒྲིལ་བ།')}</small><b>${sessions.filter(session=>session.complete).length}</b></div></div></article>`;
 const html=historyScreen(kind).replace('<section class="page">',`<section class="page fl-detail fl-records fl-${kind}-records">`).replace('</header>','</header>'+metrics);
 return html.replace(/<\/section>\s*$/,`${go(flText('Continue practice','继续练习','繼續練習','ཉམས་ལེན་མུ་མཐུད།'),kind==='body'?'bodyRecovery':'zenPractice','full mt24')}</section>`);
}

const flPreviousBodyAssessment=screens.bodyAssessment;
const flPreviousEmotion=screens.emotionAwareness;
Object.assign(screens,{
 body:flBodyMap,
 mind:flMindMap,
 bodyCulture:flBodyCulture,
 bodyRecovery:flBodyRecovery,
 zenPractice:flZenPractice,
 buddhistCourses:flMindCourses,
 bodyHistory:()=>flRecordScreen('body'),
 mindHistory:()=>flRecordScreen('mind'),
 bodyAssessment:()=>flPreviousBodyAssessment().replace('class="page j-assessment"','class="page j-assessment fl-detail fl-body-assessment"'),
 emotionAwareness:()=>flPreviousEmotion().replace('<section class="page">','<section class="page fl-detail fl-emotion">')
});
