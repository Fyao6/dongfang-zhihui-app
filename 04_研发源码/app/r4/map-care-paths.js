// Named map destinations group the app's existing, working care and practice paths.
function mapChineseCare(){
 return `<section class="page fl-detail map-care-page" data-map-destination="chineseCare">${pxTop(flText('Chinese care','中医养护','中醫養護','ཀྲུང་དབྱིའི་གསོ་སྐྱོང་།'),flText('Constitution · Food · Daoyin','体质 · 食养 · 导引','體質 · 食養 · 導引','ལུས་ཁམས། བཟའ་བཏུང་། ལུས་སྦྱོང་།'),'body')}
 <div class="fl-list">${flRow('activity',flText('Notice my condition','体质自述','體質自述','རང་གི་ལུས་ཁམས་བརྗོད་པ།'),flText('Record sleep, energy, stress and comfort.','记录睡眠、精力、压力与舒适度。','記錄睡眠、精力、壓力與舒適度。','གཉིད་དང་། སྟོབས་ཤུགས། སེམས་གནོན། བདེ་ཚོར་བཅས་ཟིན་ཐོར་འགོད་པ།'),'bodyAssessment')}${flRow('leaf',flText('Daoyin practice','导引练习','導引練習','ལུས་སྦྱོང་ཉམས་ལེན།'),flText('Choose an existing short guided practice.','选择一段已有的短时引导练习。','選擇一段已有的短時引導練習。','ཡོད་མུས་ཀྱི་དུས་ཐུང་ཁྲིད་སྟོན་ཉམས་ལེན་ཞིག་འདེམས་པ།'),'bodyCulture')}</div>
 <details class="fl-guide-details"><summary>${flText('Food & daily observation','食养与生活观察','食養與生活觀察','བཟའ་བཏུང་དང་ཉིན་རེའི་ལྟ་ཞིབ།')}</summary><p>${flText('A reflection for today: When did I eat? How did I feel afterwards? What would I like to remember about this ordinary meal?','今日观察：我在什么时候用餐？餐后有什么感受？这顿日常饮食，有什么值得记住？','今日觀察：我在什麼時候用餐？餐後有什麼感受？這頓日常飲食，有什麼值得記住？','དེ་རིང་གི་ལྟ་ཞིབ། ག་དུས་ཟ་མ་ཟོས་སམ། ཟོས་རྗེས་ཚོར་བ་གང་འདྲ་བྱུང་ངམ། ཟ་མ་འདི་ལས་གང་ཞིག་དྲན་འདོད་དམ།')}</p></details>
 ${flArchive('book',flText('My body-care archive','我的身体养护档案','我的身體養護檔案','ངའི་ལུས་གསོ་སྐྱོང་གི་ཡིག་ཚགས།'),flText('Care, practice and changes I have recorded.','回看自己记录的养护、练习与身心变化。','回看自己記錄的養護、練習與身心變化。','རང་གིས་བཀོད་པའི་གསོ་སྐྱོང་དང་ཉམས་ལེན། ལུས་སེམས་ཀྱི་འགྱུར་བར་བལྟ་བ།'),'bodyHistory')}
 </section>`;
}

function mapHealingSpace(){
 return `<section class="page fl-detail map-care-page" data-map-destination="healingSpace">${pxTop(flText('Healing space','疗愈空间','療癒空間','སེམས་གསོའི་བར་སྟོང་།'),flText('Emotional companionship · Relaxation · Inner growth','情绪陪伴 · 放松舒缓 · 内在建设','情緒陪伴 · 放鬆舒緩 · 內在建設','སེམས་ཚོར་གྱི་གྲོགས། ལྷོད་ལ་འབེབས་པ། ནང་སེམས་སྐྱེད་སྲིང་།'),'mind')}
 <div class="fl-list">${flRow('heart',flText('A place for my feelings','安放此刻的情绪','安放此刻的情緒','སྐབས་འདིའི་སེམས་ཚོར་འཇོག་ས།'),flText('Choose a feeling and write in my own words.','选一种感受，用自己的话记下来。','選一種感受，用自己的話記下來。','ཚོར་བ་ཞིག་བདམས་ནས་རང་གི་སྐད་ཆས་ཟིན་ཐོ་འབྲི་བ།'),'emotionAwareness')}${flRow('moon',flText('Rest & ease','放松舒缓','放鬆舒緩','ངལ་གསོ་དང་ལྷོད་ཡངས།'),flText('Explore short practices and choose what suits this moment.','从短时练习中，选择适合此刻的一段。','從短時練習中，選擇適合此刻的一段。','དུས་ཐུང་ཉམས་ལེན་ལས་སྐབས་འདིར་འཚམ་པ་ཞིག་འདེམས་པ།'),'bodyRecovery')}${flRow('headphones',flText('Sound for a quiet moment','声音陪伴','聲音陪伴','སྒྲའི་འགྲོགས་རོགས།'),flText('Play an available soundscape.','播放已有的放松音景。','播放已有的放鬆音景。','ཡོད་མུས་ཀྱི་ལྷོད་ཡངས་སྒྲ་དབྱངས་གཏོང་བ།'),'music')}</div>
 ${flArchive('book',flText('My mind-practice archive','我的心智修习档案','我的心智修習檔案','ངའི་སེམས་ཉམས་ལེན་གྱི་ཡིག་ཚགས།'),flText('Return to my feelings and reflections.','回看自己的感受与心得。','回看自己的感受與心得。','རང་གི་ཚོར་བ་དང་མྱོང་བར་ཕྱིར་བལྟ་བ།'),'mindHistory')}
 </section>`;
}

function mapLearningResume(){
 const last=state.wellness.continuity.learning,course=last&&academyCatalog.find(item=>item.id===last.id),visible=course&&(!px.loaded||(px.content.courses||[]).some(item=>item.id===course.id));
 const title=flText('Learning record','学习记录','學習記錄','སློབ་སྦྱོང་གི་ཟིན་ཐོ།');
 if(!visible)return `<article class="card fl-detail-card map-learning-record"><h2>${title}</h2><p class="small">${flText('No recent course viewing is saved on this device.','本机暂无最近查看的课程记录。','本機暫無最近查看的課程記錄。','སྒྲིག་ཆས་འདིར་ཉེ་ཆར་བལྟས་པའི་སློབ་ཚན་ཟིན་ཐོ་མེད།')}</p></article>`;
 return `<article class="card fl-detail-card map-learning-record"><h2>${title}</h2><p class="small">${flText('Last opened on this device','本机最近查看','本機最近查看','སྒྲིག་ཆས་འདིར་ཉེ་ཆར་བལྟས་པ།')}</p><h3>${esc(ewI18n.content(course,'',state.lang))}</h3><button class="btn secondary full" data-action="academy-open" data-id="${esc(course.id)}">${flText('Continue reading','继续阅读','繼續閱讀','ཀློག་པ་མུ་མཐུད།')}</button></article>`;
}

function mapMeditationStudy(){
 return `<section class="page fl-detail map-care-page" data-map-destination="meditationStudy">${pxTop(flText('Meditation practice','禅修修习','禪修修習','སྒོམ་སྒྲུབ་ཉམས་ལེན།'),flText('Courses · Daily sitting · Awareness','系统课程 · 日常静坐 · 觉照提升','系統課程 · 日常靜坐 · 覺照提升','སློབ་ཚན། ཉིན་རེའི་སྒོམ་སྡོད། རིག་པ་གོང་འཕེལ།'),'mind')}
 <div class="fl-list">${flRow('book',flText('Courses','系统课程','系統課程','སློབ་ཚན།'),flText('Read the existing introductory lessons and their sources.','阅读已有入门课程及参考出处。','閱讀已有入門課程及參考出處。','ཡོད་མུས་ཀྱི་འཇུག་སྒོའི་སློབ་ཚན་དང་ཁུངས་ཀློག་པ།'),'buddhistCourses')}${flRow('lotus',flText('Daily sitting','日常静坐','日常靜坐','ཉིན་རེའི་སྒོམ་སྡོད།'),flText('Choose a practice and a length that suits me.','选择适合自己的练习与时长。','選擇適合自己的練習與時長。','རང་ལ་འཚམ་པའི་ཉམས་ལེན་དང་དུས་ཡུན་འདེམས་པ།'),'zenPractice')}</div>
 <div class="j-mind-actions"><button class="btn full" data-action="journey-start" data-practice="breath">${icon('play')}${flText('Begin one quiet minute','开始一分钟静心','開始一分鐘靜心','སྐར་མ་གཅིག་སེམས་ཞི་བར་བྱེད་པ་འགོ་འཛུགས།')}</button></div>
 ${mapLearningResume()}
 ${flArchive('book',flText('My mind-practice archive','我的心智修习档案','我的心智修習檔案','ངའི་སེམས་ཉམས་ལེན་གྱི་ཡིག་ཚགས།'),flText('Practice records, learning and reflections.','练习记录、学习进度与心得。','練習記錄、學習進度與心得。','ཉམས་ལེན་ཟིན་ཐོ། སློབ་སྦྱོང་དང་མྱོང་བ།'),'mindHistory')}
 </section>`;
}

const mapBodyArchiveBefore=screens.bodyHistory,mapMindArchiveBefore=screens.mindHistory;
function mapCareArchive(kind){
 const mind=kind==='mind',title=mind?flText('My mind-practice archive','我的心智修习档案','我的心智修習檔案','ངའི་སེམས་ཉམས་ལེན་གྱི་ཡིག་ཚགས།'):flText('My body-care archive','我的身体养护档案','我的身體養護檔案','ངའི་ལུས་གསོ་སྐྱོང་གི་ཡིག་ཚགས།');
 const subtitle=mind?flText('Practice records, learning and reflections.','练习记录、学习进度与心得','練習記錄、學習進度與心得','ཉམས་ལེན་ཟིན་ཐོ། སློབ་སྦྱོང་དང་མྱོང་བ།'):flText('Care, practice and changes I have recorded.','记录养护、练习与身心变化','記錄養護、練習與身心變化','གསོ་སྐྱོང་དང་ཉམས་ལེན། ལུས་སེམས་ཀྱི་འགྱུར་བ་ཟིན་ཐོར་འགོད་པ།');
 let html=(mind?mapMindArchiveBefore:mapBodyArchiveBefore)().replace(/<header\b[\s\S]*?<\/header>/,pxTop(title,subtitle,kind));
 if(mind)html=html.replace(/<\/section>\s*$/,mapLearningResume()+'</section>');
 else html=html.replace(/<\/section>\s*$/,mapArchiveNotes(['tea','tibetan'])+'</section>');
 return html;
}
Object.assign(screens,{chineseCare:mapChineseCare,healingSpace:mapHealingSpace,meditationStudy:mapMeditationStudy,bodyHistory:()=>mapCareArchive('body'),mindHistory:()=>mapCareArchive('mind')});
