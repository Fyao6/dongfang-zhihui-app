// Distinct map destinations. Personal notes stay in this browser and are scoped to the current account.
function mxText(en,zh,hant,bo){return flText(en,zh,hant,bo);}
function mxStorageKey(){return 'ew-map-exploration-v1:'+String(personalStorage.scope||'pending');}
function mxReadRecords(){
 if(!personalStorage.scope)return [];
 try{const value=JSON.parse(localStorage.getItem(mxStorageKey())||'[]');return Array.isArray(value)?value.filter(x=>x&&['classics','western','tea','tibetan'].includes(x.kind)&&typeof x.id==='string'&&typeof x.title==='string'&&typeof x.note==='string'&&typeof x.at==='string'&&Number.isFinite(Date.parse(x.at))).slice(0,200):[];}catch{return [];}
}
function mapExplorationRecords(kind){return mxReadRecords().filter(x=>!kind||x.kind===kind).map(x=>({...x}));}
function mapExplorationSummary(){const records=mxReadRecords();return Object.fromEntries(['classics','western','tea','tibetan'].map(kind=>[kind,records.filter(x=>x.kind===kind).length]));}
function mxSaveRecords(records){if(!personalStorage.scope)return false;try{localStorage.setItem(mxStorageKey(),JSON.stringify(records.slice(0,200)));return true;}catch{return false;}}
function mxGuide(symbol,title,copy){return `<details class="fl-guide-row mx-guide"><summary><span class="fl-row-icon">${icon(symbol)}</span><b>${title}</b>${icon('arrow')}</summary><p>${copy}</p></details>`;}
function mxLocalNote(){return mxText('Saved only in this browser for the current account.','仅保存在当前浏览器，按当前账号分别记录。','僅保存在目前瀏覽器，按目前帳號分別記錄。','མིག་སྔའི་བཤར་ཆས་ནང་རྩིས་ཐོ་སོ་སོར་ཉར་ཚགས་བྱེད།');}
function mxHistory(kind){
 const entries=mapExplorationRecords(kind);
 const title=mxText('My notes','我的记录','我的記錄','ངའི་ཟིན་ཐོ།');
 const empty=mxText('Your saved notes will appear here.','保存后的记录会显示在这里。','儲存後的記錄會顯示在這裡。','ཉར་ཚགས་བྱས་པའི་ཟིན་ཐོ་འདིར་འཆར་ངེས།');
 const remove=mxText('Delete this note','删除这条记录','刪除這條記錄','ཟིན་ཐོ་འདི་སུབ་པ།');
 return `<section class="mx-history"><div class="section-title"><h2>${title}</h2><span>${entries.length}</span></div>${entries.length?entries.map(x=>`<article class="card mx-history-card"><header><b>${esc(x.title)}</b><button class="icon-btn flat" data-map-explore-action="delete" data-record-id="${esc(x.id)}" aria-label="${remove}">${icon('close')}</button></header><small>${esc(new Date(x.at).toLocaleDateString(ewI18n.locales[state.lang]?.intl||'zh-CN'))}</small>${x.note?`<p>${esc(x.note)}</p>`:''}</article>`).join(''):`<p class="mx-empty">${empty}</p>`}</section>`;
}
function mxForm(kind,title,label,placeholder){
 return `<form class="mx-form card" data-map-explore-form="${kind}"><h2>${title}</h2><label><span>${label}</span><input class="input" name="title" maxlength="80" required placeholder="${placeholder}" autocomplete="off"></label><label><span>${mxText('Notes and reflections','记录与心得','記錄與心得','ཟིན་ཐོ་དང་ཉམས་མྱོང་།')}</span><textarea class="input" name="note" rows="4" maxlength="1200" placeholder="${mxText('Write in your own words.','写下自己的观察与感受。','寫下自己的觀察與感受。','རང་གི་བསམ་ཚུལ་དང་ཚོར་བ་འབྲི་རོགས།')}"></textarea></label><button class="btn full" type="submit">${mxText('Save this note','保存这条记录','儲存這條記錄','ཟིན་ཐོ་འདི་ཉར་ཚགས།')}</button><p class="small mx-local-note">${mxLocalNote()}</p></form>`;
}
function mxClassics(){
 return `<section class="page fl-detail mx-page mx-classics">${pxTop(mxText('Chinese wisdom','国学智慧','國學智慧','རྒྱ་ནག་གི་རིག་གནས་ཤེས་རབ།'),mxText('Classics · Culture · Everyday life','经典 · 文化 · 生活','經典 · 文化 · 生活','གཞུང་དང་། རིག་གནས། འཚོ་བ།'),'lifeResult')}
 <div class="fl-list">
 ${mxGuide('book',mxText('Reading a classic','经典阅读','經典閱讀','གཞུང་ཀློག་པ།'),mxText('Choose a passage you want to understand. Keep its original words, commentary and your own interpretation separate in your notes. Return to the passage after reflecting on a real experience.','选一段自己想理解的经典原文。记录时区分原文、注释与自己的理解，再带着生活中的经历回看这段文字。','選一段自己想理解的經典原文。記錄時區分原文、註釋與自己的理解，再帶著生活中的經歷回看這段文字。','རང་གིས་གོ་བ་ལོན་འདོད་པའི་གཞུང་ཚིག་ཅིག་འདེམས། མ་ཡིག་དང་འགྲེལ་པ། རང་གི་གོ་བ་བཅས་ཁ་ཁར་བཀོད་ནས་འཚོ་བའི་ཉམས་མྱོང་དང་སྦྱར་ཏེ་བསྐྱར་ཀློག་བྱོས།'))}
 ${mxGuide('compass',mxText('Observing culture','文化观察','文化觀察','རིག་གནས་ལ་ལྟ་བ།'),mxText('Begin with one word, custom or object you encounter. Note where you found it, what you already understand and which questions you want to investigate.','从遇见的一个词、一种习俗或一件器物开始，记下资料出处、已经理解的部分，以及还想进一步了解的问题。','從遇見的一個詞、一種習俗或一件器物開始，記下資料出處、已經理解的部分，以及還想進一步了解的問題。','མཐོང་བའི་ཐ་སྙད་དམ་སྲོལ་རྒྱུན། ཡང་ན་དངོས་པོ་ཞིག་ནས་འགོ་བརྩམས་ཏེ། ཁུངས་དང་གོ་བ་ལོན་པ། མུ་མཐུད་ཤེས་འདོད་པ་བཅས་བཀོད།'))}
 ${mxGuide('leaf',mxText('Bringing learning into life','生活实践','生活實踐','འཚོ་བའི་ཉམས་ལེན།'),mxText('Choose one idea from your reading and one small action you can try. Afterwards, write what happened in your own words, including what did not fit your situation.','从阅读中选一个想法，试一个自己能做到的小行动。之后如实记下发生了什么，也可以记下不适合自己的部分。','從閱讀中選一個想法，試一個自己能做到的小行動。之後如實記下發生了什麼，也可以記下不適合自己的部分。','ཀློག་པའི་ནང་ནས་བསམ་ཚུལ་ཞིག་དང་བྱ་སྤྱོད་ཆུང་ངུ་ཞིག་འདེམས་ནས་ཚོད་ལྟ་བྱོས། དེ་ནས་རང་ལ་འཚམ་པ་དང་མི་འཚམ་པ་རྣམས་དྲང་པོར་བཀོད།'))}
 </div><p class="mx-original-note">${mxText('Original reading prompts for your own study.','以上为原创阅读提示，供自主学习与记录。','以上為原創閱讀提示，供自主學習與記錄。','གོང་གི་ནང་དོན་ནི་རང་ཉིད་སློབ་སྦྱོང་དང་ཟིན་ཐོའི་ཆེད་བྲིས་པའི་ཀློག་འདོན་གྱི་དྲན་སྐུལ་ཡིན།')}</p>
 ${mxForm('classics',mxText('Record my learning','记录我的学习','記錄我的學習','ངའི་སློབ་སྦྱོང་བཀོད་པ།'),mxText('Reading or topic','阅读篇目或主题','閱讀篇目或主題','ཀློག་གཞི་ཡང་ན་བརྗོད་གཞི།'),mxText('What did you read today?','今天阅读了什么？','今天閱讀了什麼？','དེ་རིང་ཅི་ཞིག་བཀླགས་སམ།'))}${mxHistory('classics')}</section>`;
}
function mxWestern(){
 return `<section class="page fl-detail mx-page mx-western">${pxTop(mxText('Western astrology','星盘探索','星盤探索','ནུབ་ཕྱོགས་རྩིས་ཀྱི་འཚོལ་ཞིབ།'),mxText('Western charts · Character · Questions','西方星盘 · 性格 · 议题','西方星盤 · 性格 · 議題','ནུབ་ཕྱོགས་རྩིས་དང་། གཤིས་ཀ བརྗོད་གཞི།'),'lifeResult')}
 <article class="card mx-status-card"><h2>${mxText('No Western chart generated yet','尚未生成西方星盘','尚未產生西方星盤','ནུབ་ཕྱོགས་ཀྱི་རྩིས་རིས་ད་དུང་བཟོས་མེད།')}</h2><p>${mxText('This page currently holds your exploration questions and notes. These notes do not calculate a chart or produce a personality assessment.','当前可记录自己的探索议题与观察。这些记录不会计算星盘，也不会自动生成性格判断。','目前可記錄自己的探索議題與觀察。這些記錄不會計算星盤，也不會自動產生性格判斷。','འདིར་རང་གི་འཚོལ་ཞིབ་བརྗོད་གཞི་དང་མཐོང་ཚུལ་བཀོད་ཆོག ཟིན་ཐོ་འདིས་རྩིས་རིས་དང་གཤིས་ཀའི་དཔྱད་འབྲས་བཟོ་མི་བྱེད།')}</p></article>
 <div class="fl-list">${mxGuide('compass',mxText('Keep the systems distinct','区分不同体系','區分不同體系','ལུགས་སྲོལ་ཁ་ཁར་འབྱེད་པ།'),mxText('Western chart exploration has its own space here. Your Zi Wei chart remains in “My Zi Wei chart”; it is not presented as a Western chart.','这里单独保存西方星盘相关的探索记录。紫微排盘仍在“我的紫微命盘”中查看，不会作为西方星盘展示。','這裡單獨儲存西方星盤相關的探索記錄。紫微排盤仍在「我的紫微命盤」中查看，不會作為西方星盤展示。','ནུབ་ཕྱོགས་རྩིས་ཀྱི་ཟིན་ཐོ་འདིར་ལོགས་སུ་ཉར། ཙི་ཝེའི་རྩིས་རིས་ནི་དེའི་ཤོག་ངོས་ནས་བལྟ་ཆོག་ལ་ནུབ་ཕྱོགས་རྩིས་སུ་སྟོན་མི་བྱེད།'))}
 ${mxGuide('spark',mxText('Observe character in context','观察自己的性格','觀察自己的性格','རང་གི་གཤིས་ཀ་ལ་ལྟ་བ།'),mxText('Choose one real situation. Record what you felt and did, without turning one experience into a fixed label about yourself.','选一件真实发生的事，记下当时的感受与行动，不急着用一次经历给自己贴上固定标签。','選一件真實發生的事，記下當時的感受與行動，不急著用一次經歷給自己貼上固定標籤。','དོན་དངོས་ཤིག་འདེམས་ནས་སྐབས་དེའི་ཚོར་བ་དང་བྱ་སྤྱོད་བཀོད། ཉམས་མྱོང་གཅིག་ལས་རང་ལ་ངོས་འཛིན་བརྟན་པོ་ཞིག་མ་བྱེད།'))}</div>
 ${mxForm('western',mxText('My exploration question','我的探索议题','我的探索議題','ངའི་འཚོལ་ཞིབ་བརྗོད་གཞི།'),mxText('Question or topic','问题或主题','問題或主題','དྲི་བ་ཡང་ན་བརྗོད་གཞི།'),mxText('What would you like to understand?','你现在想了解什么？','你現在想了解什麼？','ད་ལྟ་གང་ཞིག་ཤེས་འདོད་དམ།'))}${mxHistory('western')}</section>`;
}
function mxTea(){
 return `<section class="page fl-detail mx-page mx-tea">${pxTop(mxText('Tea life','茶道生活','茶道生活','ཇའི་འཚོ་བ།'),mxText('A cup of tea, a moment for yourself','一杯茶，调和身心','一杯茶，調和身心','ཇ་ཕོར་པ་གང་དང་རང་ལ་དུས་ཚོད་ཅིག'),'body')}
 <div class="fl-list">${mxGuide('leaf',mxText('Notice this cup','觉察这一杯','覺察這一杯','ཇ་ཕོར་པ་འདིར་དོ་སྣང་།'),mxText('Take a moment to notice the colour, aroma and flavour you actually experience. You can simply record what you notice, without giving it a score.','留一点时间，看看自己实际感受到的茶色、香气与滋味。可以只记录观察，不必给体验打分。','留一點時間，看看自己實際感受到的茶色、香氣與滋味。可以只記錄觀察，不必給體驗打分。','རང་གིས་ཚོར་བའི་ཇའི་ཁ་དོག་དང་དྲི་མ། རོ་བཅས་ལ་དོ་སྣང་བྱོས། སྐར་གྲངས་མི་དགོས་པར་མཐོང་ཚུལ་བཀོད་ཆོག'))}
 ${mxGuide('book',mxText('Keep a tea note','留下茶记','留下茶記','ཇའི་ཟིན་ཐོ་བཀོད་པ།'),mxText('Write the tea name and the details you want to remember. Your own notes build a record of your tea moments; they do not produce a health assessment.','记下茶名，以及自己想留下的细节。茶记只积累自己的生活体验，不自动生成健康评估。','記下茶名，以及自己想留下的細節。茶記只累積自己的生活體驗，不自動產生健康評估。','ཇའི་མིང་དང་དྲན་འདོད་པའི་ཆ་ཤས་བཀོད། ཇའི་ཟིན་ཐོས་རང་གི་འཚོ་བའི་ཉམས་མྱོང་བསགས་པ་ལས་བདེ་ཐང་གི་དཔྱད་འབྲས་བཟོ་མི་བྱེད།'))}</div>
 ${mxForm('tea',mxText('My tea note','我的茶记','我的茶記','ངའི་ཇའི་ཟིན་ཐོ།'),mxText('Tea name','茶名','茶名','ཇའི་མིང་།'),mxText('Which tea are you having?','此刻喝的是什么茶？','此刻喝的是什麼茶？','ད་ལྟ་ཇ་གང་འཐུང་གི་ཡོད་དམ།'))}${mxHistory('tea')}</section>`;
}
function mxTibetan(){
 return `<section class="page fl-detail mx-page mx-tibetan">${pxTop(mxText('Tibetan care','藏医养护','藏醫養護','བོད་ཀྱི་གསོ་རིག་གི་བདག་སྐྱོང་།'),mxText('Breathing · Wellbeing · Everyday wisdom','调息 · 康养 · 生活智慧','調息 · 康養 · 生活智慧','དབུགས་དང་། བདེ་ཐང་། འཚོ་བའི་ཤེས་རབ།'),'body')}
 <div class="fl-list">${mxGuide('book',mxText('A place for cultural study','文化学习','文化學習','རིག་གནས་སློབ་སྦྱོང་།'),mxText('Keep the title, author and source of what you read. Separate the source text from your own questions and reflections. This space does not provide a constitution diagnosis or prescription.','阅读时记下篇名、作者与资料出处，区分原文和自己的疑问、心得。这里不提供体质诊断或药方。','閱讀時記下篇名、作者與資料出處，區分原文和自己的疑問、心得。這裡不提供體質診斷或藥方。','ཀློག་སྐབས་ཁ་བྱང་དང་རྩོམ་པ་པོ། ཁུངས་བཅས་བཀོད། མ་ཡིག་དང་རང་གི་དྲི་བ་ཁ་ཁར་འབྱེད། འདིར་ལུས་ཁམས་ཀྱི་ངོས་འཛིན་དང་སྨན་ཐོ་མི་སྤྲོད།'))}
 <button class="fl-list-row" data-action="start-practice" data-practice="breath"><span class="fl-row-icon">${icon('leaf')}</span><span class="fl-row-copy"><b>${mxText('One natural minute','一分钟自然呼吸','一分鐘自然呼吸','སྐར་མ་གཅིག་གི་རང་བྱུང་དབུགས།')}</b><small>${mxText('An everyday awareness practice','日常觉察练习','日常覺察練習','ཉིན་རེའི་དོ་སྣང་ཉམས་ལེན།')}</small></span>${icon('play')}</button></div>
 ${mxForm('tibetan',mxText('My study and daily care notes','我的学习与养护记录','我的學習與養護記錄','ངའི་སློབ་སྦྱོང་དང་བདག་སྐྱོང་ཟིན་ཐོ།'),mxText('Reading or daily observation','阅读主题或生活观察','閱讀主題或生活觀察','ཀློག་གཞི་ཡང་ན་འཚོ་བའི་མཐོང་ཚུལ།'),mxText('What would you like to record?','今天想记下什么？','今天想記下什麼？','དེ་རིང་གང་ཞིག་བཀོད་འདོད་དམ།'))}${mxHistory('tibetan')}</section>`;
}
Object.assign(screens,{classicsWisdom:mxClassics,westernAstrology:mxWestern,teaLife:mxTea,tibetanCare:mxTibetan});
document.addEventListener('submit',event=>{
 const form=event.target.closest('form[data-map-explore-form]');if(!form)return;
 event.preventDefault();event.stopImmediatePropagation();
 if(!personalStorage.scope){toast(mxText('Reconnect to confirm the account before saving. Your input stays here.','请先重新连接确认账号再保存；当前输入仍保留。','請先重新連線確認帳號再儲存；目前輸入仍保留。','རྩིས་ཐོ་ངེས་གཏན་བྱེད་པར་སླར་མཐུད་རོགས། བཀང་བ་ཉར་ཡོད།'));return;}
 if(!form.reportValidity())return;
 const kind=form.dataset.mapExploreForm;if(!['classics','western','tea','tibetan'].includes(kind))return;
 const title=String(form.elements.title.value||'').trim().slice(0,80),note=String(form.elements.note.value||'').trim().slice(0,1200);
 if(!title){form.elements.title.focus();return;}
 const record={id:Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9),kind,title,note,at:new Date().toISOString()};
 if(!mxSaveRecords([record,...mxReadRecords()])){toast(mxText('Could not save in this browser.','当前浏览器无法保存，请检查存储空间。','目前瀏覽器無法儲存，請檢查儲存空間。','བཤར་ཆས་འདིར་ཉར་ཚགས་མ་ཐུབ། ཉར་ས་ལ་བལྟ་རོགས།'));return;}
 render(false);toast(mxText('Note saved','记录已保存','記錄已儲存','ཟིན་ཐོ་ཉར་ཚགས་བྱས་ཟིན།'));
},true);
document.addEventListener('click',event=>{
 const target=event.target.closest('[data-map-explore-action]');if(!target)return;
 event.preventDefault();event.stopImmediatePropagation();
 if(target.dataset.mapExploreAction==='delete'){
  if(mxSaveRecords(mxReadRecords().filter(x=>x.id!==target.dataset.recordId)))render(false);
 }
},true);
