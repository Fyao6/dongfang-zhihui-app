// Cultural vocabulary for the deterministic chart. Definitions describe relationships, not predictions.
var lcbGlossaryGods={比肩:'god-biJian',劫财:'god-jieCai',食神:'god-shiShen',伤官:'god-shangGuan',偏财:'god-pianCai',正财:'god-zhengCai',七杀:'god-qiSha',正官:'god-zhengGuan',偏印:'god-pianYin',正印:'god-zhengYin'};
var lcbGlossaryData={
 dayMaster:{title:['Day master','日主','日主','ཉིན་གྱི་གནམ་སྡོང་།'],copy:[
  'The heavenly stem of the natal day pillar. The chart uses this stem as the reference for Ten Gods relationships with other stems and hidden stems.',
  '本命日柱的天干。排盘以它为参照，计算其他天干及藏干与它的十神关系。',
  '本命日柱的天干。排盤以它為參照，計算其他天干及藏干與它的十神關係。',
  'སྐྱེས་དུས་ཉིན་གྱི་ཀ་བའི་གནམ་སྡོང་ཡིན། གནམ་སྡོང་གཞན་དང་སྦས་པའི་གནམ་སྡོང་གི་འབྲེལ་བ་རྩིས་སྐབས་འདི་གཞིར་འཛིན།']},
 ganZhi:{title:['Heavenly stems and earthly branches','干支','干支','གནམ་སྡོང་དང་ས་ཡལ།'],copy:[
  'Ten heavenly stems and twelve earthly branches combine in order to form a sixty-part cycle. Each year, month, day and hour pillar contains one stem and one branch; the four pillars together contain eight characters.',
  '十天干与十二地支按次序配合，组成六十甲子循环。年、月、日、时各柱分别由一个天干和一个地支组成，四柱合为八字。',
  '十天干與十二地支按次序配合，組成六十甲子循環。年、月、日、時各柱分別由一個天干和一個地支組成，四柱合為八字。',
  'གནམ་སྡོང་བཅུ་དང་ས་ཡལ་བཅུ་གཉིས་རིམ་པར་སྦྱར་ནས་རེས་འཁོར་དྲུག་ཅུ་གྲུབ། ལོ་ཟླ་ཉིན་དུས་ཀྱི་ཀ་བ་རེ་ལ་གནམ་སྡོང་གཅིག་དང་ས་ཡལ་གཅིག་ཡོད།']},
 hiddenStems:{title:['Hidden stems','藏干','藏干','སྦས་པའི་གནམ་སྡོང་།'],copy:[
  'Traditional stem assignments within an earthly branch. The calendar library lists one to three stems for each branch. This list does not supply numerical weights or percentages.',
  '传统规则中，各地支内对应的天干。历法库为每个地支列出一至三个藏干；列表本身不提供权重或占比。',
  '傳統規則中，各地支內對應的天干。曆法庫為每個地支列出一至三個藏干；列表本身不提供權重或佔比。',
  'སྲོལ་རྒྱུན་སྒྲིག་སྲོལ་ནང་ས་ཡལ་རེ་ལ་གནམ་སྡོང་གཅིག་ནས་གསུམ་བར་སྦས་པར་བརྩི། ཐོ་འདིས་ལྗིད་ཚད་དང་བརྒྱ་ཆ་མི་སྟོན།']},
 fiveElements:{title:['Five elements','五行','五行','འབྱུང་བ་ལྔ།'],copy:[
  'Wood, Fire, Earth, Metal and Water are traditional categories assigned to stems and branches. The chart displays those assignments. Counting these labels alone does not establish strength, balance or a need to add an element.',
  '木、火、土、金、水是干支对应的传统分类。本表展示这些对应关系；仅按字数统计，不能直接判断旺衰、平衡或需要补哪一行。',
  '木、火、土、金、水是干支對應的傳統分類。本表展示這些對應關係；僅按字數統計，不能直接判斷旺衰、平衡或需要補哪一行。',
  'ཤིང་མེ་ས་ལྕགས་ཆུ་ནི་གནམ་སྡོང་དང་ས་ཡལ་གྱི་སྲོལ་རྒྱུན་རིགས་དབྱེ་ཡིན། མིང་གྲངས་ཁོ་ནས་སྟོབས་དང་དོ་མཉམ་ཡང་ན་ཅི་ཞིག་ཁ་སྣོན་དགོས་པ་མི་ཐག་གཅོད།']},
 stemTenGod:{title:['Ten Gods · stems','天干十神','天干十神','གནམ་སྡོང་གི་འབྲེལ་བ་བཅུ།'],copy:[
  'Ten relationship labels compare a stem with the natal day master through five-element generation or control and matching or opposite Yin–Yang polarity. “Gods” is a traditional name for these categories, not a reference to deities. Expand a name below for its exact relationship.',
  '以本命日主为参照，按五行生克与阴阳同异，将某个天干归为十种关系之一。“十神”是传统分类名称，不指神灵。下方可展开每个名称的具体关系。',
  '以本命日主為參照，按五行生剋與陰陽同異，將某個天干歸為十種關係之一。「十神」是傳統分類名稱，不指神靈。下方可展開每個名稱的具體關係。',
  'སྐྱེས་དུས་ཉིན་གྱི་གནམ་སྡོང་གཞིར་བཞག་ནས་འབྱུང་བའི་སྐྱེད་འཇོམས་དང་阴阳 རིགས་མཚུངས་མི་མཚུངས་ལྟར་འབྲེལ་བ་བཅུར་དབྱེ། འདི་ལྷ་མིན་པར་རིགས་དབྱེའི་མིང་ཡིན། གཤམ་གྱི་མིང་ཁ་ཕྱེ་ནས་འགྲེལ་བཤད་ལ་ལྟ།'],related:Object.values(lcbGlossaryGods)},
 branchTenGods:{title:['Ten Gods · hidden stems','地支十神','地支十神','ས་ཡལ་གྱི་འབྲེལ་བ་བཅུ།'],copy:[
  'The library compares each hidden stem in the branch with the natal day master. A branch can therefore show several Ten Gods labels, in the same order as its hidden stems. The branch itself is not assigned just one label here.',
  '将该地支的各个藏干，逐一与本命日主对照所得的十神。因此可能有多个名称，顺序与藏干列表一致；这里不是给整个地支只贴一个十神标签。',
  '將該地支的各個藏干，逐一與本命日主對照所得的十神。因此可能有多個名稱，順序與藏干列表一致；這裡不是給整個地支只貼一個十神標籤。',
  'ས་ཡལ་ནང་གི་སྦས་པའི་གནམ་སྡོང་རེ་རེ་ཉིན་གྱི་གནམ་སྡོང་དང་བསྡུར་ནས་འབྲེལ་བ་རྩིས། དེས་མིང་མང་པོ་ཡོང་སྲིད་ཅིང་རིམ་པ་ནི་སྦས་སྡོང་གི་ཐོ་དང་མཐུན།'],related:Object.values(lcbGlossaryGods)},
 naYin:{title:['Na Yin','纳音','納音','ན་ཡིན།'],copy:[
  'A traditional classification assigning the sixty stem–branch combinations to thirty named pairs. The chart looks up the name attached to that pillar. It is not an audio frequency or a measured physical property.',
  '将六十甲子按相邻两项配为一组，共三十类名称的传统分类。表中按该柱干支查得对应纳音，不是音频频率或实际测量的物理属性。',
  '將六十甲子按相鄰兩項配為一組，共三十類名稱的傳統分類。表中按該柱干支查得對應納音，不是音頻頻率或實際測量的物理屬性。',
  'གནམ་སྡོང་དང་ས་ཡལ་གྱི་སྦྱོར་བ་དྲུག་ཅུ་ཟུང་སུམ་ཅུར་དབྱེ་བའི་སྲོལ་རྒྱུན་མིང་ཡིན། སྒྲའི་ཟློས་ཕྱོད་དམ་དངོས་སུ་ཚད་འཇལ་བའི་ཁྱད་ཆོས་མིན།']},
 growthStage:{title:['Twelve growth stages','十二长生','十二長生','འཚར་སྐྱེའི་རིམ་པ་བཅུ་གཉིས།'],copy:[
  'Twelve traditional stage names describe the day master’s relationship to a branch. The library uses the day stem and its Yin–Yang direction. The names are Chang Sheng, Mu Yu, Guan Dai, Lin Guan, Di Wang, Shuai, Bing, Si, Mu, Jue, Tai and Yang. “Bing” and “Si” are category names; they do not indicate illness, death or lifespan.',
  '以日干为参照，按其阴阳顺逆，描述它与某地支关系的十二个传统阶段名：长生、沐浴、冠带、临官、帝旺、衰、病、死、墓、绝、胎、养。其中“病、死”等只是分类名称，不表示现实疾病、生死或寿命。',
  '以日干為參照，按其陰陽順逆，描述它與某地支關係的十二個傳統階段名：長生、沐浴、冠帶、臨官、帝旺、衰、病、死、墓、絕、胎、養。其中「病、死」等只是分類名稱，不表示現實疾病、生死或壽命。',
  'ཉིན་གྱི་གནམ་སྡོང་དང་ས་ཡལ་གྱི་འབྲེལ་བ་སྟོན་པའི་སྲོལ་རྒྱུན་རིམ་པ་བཅུ་གཉིས་ཀྱི་མིང་ཡིན། གནམ་སྡོང་གི་阴阳 རིགས་ལྟར་མདུན་ཕྱིར་རྩིས། 病 དང་死 སོགས་རིགས་དབྱེའི་མིང་ཙམ་ཡིན་ཞིང་ནད་དང་འཆི་བའམ་ཚེ་ཚད་མི་སྟོན།']},
 xun:{title:['Ten-part cycle · Xun','旬','旬','བཅུ་ཚན་གྱི་རེས་འཁོར།'],copy:[
  'The sixty stem–branch combinations are divided into six groups of ten. Each group begins with a Jia stem: Jia-Zi, Jia-Xu, Jia-Shen, Jia-Wu, Jia-Chen or Jia-Yin. A pillar’s Xun is the group containing that stem–branch combination.',
  '每十个干支为一旬，六十甲子共六旬，称甲子旬、甲戌旬、甲申旬、甲午旬、甲辰旬、甲寅旬。某柱的旬，指该干支所属的十项分组。',
  '每十個干支為一旬，六十甲子共六旬，稱甲子旬、甲戌旬、甲申旬、甲午旬、甲辰旬、甲寅旬。某柱的旬，指該干支所屬的十項分組。',
  'སྦྱོར་བ་དྲུག་ཅུ་བཅུ་རེའི་ཚོ་དྲུག་ཏུ་དབྱེ། ཚོ་རེ་甲 ཡི་གནམ་སྡོང་ནས་འགོ་ཚུགས། ཀ་བའི་旬 ནི་དེའི་སྦྱོར་བ་ཚོ་གང་དུ་གཏོགས་པ་ཡིན།']},
 voidBranches:{title:['Void branches · Xun Kong','旬空／空亡','旬空／空亡','སྟོང་པའི་ས་ཡལ།'],copy:[
  'In one ten-part cycle, ten stems pair with ten of the twelve branches; the two unpaired branches are called Xun Kong. Each displayed entry belongs to that column’s own cycle. It does not automatically establish an interaction with the natal chart or predict a loss.',
  '一旬中，十天干配到十二地支中的十个，未配到的两个地支称为旬空。各列显示该柱自身所属旬的旬空，不自动判定与本命发生空亡关系，也不据此预言损失。',
  '一旬中，十天干配到十二地支中的十個，未配到的兩個地支稱為旬空。各欄顯示該柱自身所屬旬的旬空，不自動判定與本命發生空亡關係，也不據此預言損失。',
  'བཅུ་ཚན་གཅིག་ནང་གནམ་སྡོང་བཅུ་ས་ཡལ་བཅུ་དང་སྦྱར་སྐབས་ལྷག་པའི་ས་ཡལ་གཉིས་ལ་སྟོང་ཡལ་ཟེར། ཀ་བ་རེའི་རེས་འཁོར་རང་གི་འབྲས་བུ་ཡིན། དེས་གྱོང་གུན་སྔོན་བཤད་མི་བྱེད།'],related:['xun']},
 'god-biJian':{title:['Bi Jian · 比肩','比肩','比肩','比肩 · རིགས་མཚུངས་པ།'],copy:[
  'A stem with the same element and the same Yin–Yang polarity as the day master.',
  '与日主五行相同、阴阳属性也相同的天干关系。',
  '與日主五行相同、陰陽屬性也相同的天干關係。',
  'ཉིན་གྱི་གནམ་སྡོང་དང་འབྱུང་བ་དང་阴阳 རིགས་གཉིས་ཀ་མཚུངས་པའི་འབྲེལ་བ།']},
 'god-jieCai':{title:['Jie Cai · 劫财','劫财','劫財','劫财 · འབྱུང་བ་མཚུངས་པ།'],copy:[
  'A stem with the same element but opposite Yin–Yang polarity to the day master. The traditional name does not mean that money will be taken away.',
  '与日主五行相同、阴阳属性相反的天干关系。名称不表示现实中会被夺走钱财。',
  '與日主五行相同、陰陽屬性相反的天干關係。名稱不表示現實中會被奪走錢財。',
  'ཉིན་གྱི་གནམ་སྡོང་དང་འབྱུང་བ་མཚུངས་ཀྱང་阴阳 རིགས་མི་མཚུངས། མིང་འདིས་དངུལ་ཕྲོགས་པར་འགྱུར་བ་མི་སྟོན།']},
 'god-shiShen':{title:['Shi Shen · 食神','食神','食神','食神 · སྐྱེད་པའི་འབྲེལ་བ།'],copy:[
  'The day master’s element generates this stem’s element, and their Yin–Yang polarity is the same. This relationship label does not describe diet or health.',
  '日主五行所生、且与日主阴阳属性相同的天干关系。此名称不用于判断饮食或健康。',
  '日主五行所生、且與日主陰陽屬性相同的天干關係。此名稱不用於判斷飲食或健康。',
  'ཉིན་གྱི་གནམ་སྡོང་གི་འབྱུང་བས་འདིའི་འབྱུང་བ་སྐྱེད་ཅིང་阴阳 རིགས་མཚུངས། ཟས་དང་བདེ་ཐང་ལ་དཔྱད་པ་མིན།']},
 'god-shangGuan':{title:['Shang Guan · 伤官','伤官','傷官','伤官 · སྐྱེད་པའི་འབྲེལ་བ།'],copy:[
  'The day master’s element generates this stem’s element, and their Yin–Yang polarity is opposite. The name does not predict harm.',
  '日主五行所生、且与日主阴阳属性相反的天干关系。名称不表示现实中的伤害。',
  '日主五行所生、且與日主陰陽屬性相反的天干關係。名稱不表示現實中的傷害。',
  'ཉིན་གྱི་གནམ་སྡོང་གི་འབྱུང་བས་འདིའི་འབྱུང་བ་སྐྱེད་ཅིང་阴阳 རིགས་མི་མཚུངས། གནོད་པ་ཡོང་བ་སྔོན་བཤད་མི་བྱེད།']},
 'god-pianCai':{title:['Pian Cai · 偏财','偏财','偏財','偏财 · འཇོམས་པའི་འབྲེལ་བ།'],copy:[
  'The day master’s element controls this stem’s element, and their Yin–Yang polarity is the same. This is a relationship category, not an income forecast.',
  '日主五行所克、且与日主阴阳属性相同的天干关系。这是关系分类，不是收入预测。',
  '日主五行所剋、且與日主陰陽屬性相同的天干關係。這是關係分類，不是收入預測。',
  'ཉིན་གྱི་གནམ་སྡོང་གི་འབྱུང་བས་འདིའི་འབྱུང་བ་འཇོམས་ཤིང་阴阳 རིགས་མཚུངས། ཡོང་འབབ་ཀྱི་སྔོན་དཔག་མིན།']},
 'god-zhengCai':{title:['Zheng Cai · 正财','正财','正財','正财 · འཇོམས་པའི་འབྲེལ་བ།'],copy:[
  'The day master’s element controls this stem’s element, and their Yin–Yang polarity is opposite. The name does not establish an amount or source of wealth.',
  '日主五行所克、且与日主阴阳属性相反的天干关系。名称不用于判断实际财富数额或来源。',
  '日主五行所剋、且與日主陰陽屬性相反的天干關係。名稱不用於判斷實際財富數額或來源。',
  'ཉིན་གྱི་གནམ་སྡོང་གི་འབྱུང་བས་འདིའི་འབྱུང་བ་འཇོམས་ཤིང་阴阳 རིགས་མི་མཚུངས། ནོར་གྱི་གྲངས་དང་ཁུངས་མི་ཐག་གཅོད།']},
 'god-qiSha':{title:['Qi Sha · 七杀','七杀','七殺','七杀 · འཇོམས་པར་བྱེད་པའི་འབྲེལ་བ།'],copy:[
  'This stem’s element controls the day master’s element, and their Yin–Yang polarity is the same. Also called Pian Guan. The traditional name does not indicate violence or danger.',
  '克日主五行、且与日主阴阳属性相同的天干关系，也称偏官。名称不表示现实中的暴力或危险。',
  '剋日主五行、且與日主陰陽屬性相同的天干關係，也稱偏官。名稱不表示現實中的暴力或危險。',
  'གནམ་སྡོང་འདིའི་འབྱུང་བས་ཉིན་གྱི་གནམ་སྡོང་གི་འབྱུང་བ་འཇོམས་ཤིང་阴阳 རིགས་མཚུངས། 偏官 ཡང་ཟེར། དྲག་སྤྱོད་དམ་ཉེན་ཁ་མི་སྟོན།']},
 'god-zhengGuan':{title:['Zheng Guan · 正官','正官','正官','正官 · འཇོམས་པར་བྱེད་པའི་འབྲེལ་བ།'],copy:[
  'This stem’s element controls the day master’s element, and their Yin–Yang polarity is opposite. It is not a statement about a real official position or career.',
  '克日主五行、且与日主阴阳属性相反的天干关系，不是对现实官职或职业的判断。',
  '剋日主五行、且與日主陰陽屬性相反的天干關係，不是對現實官職或職業的判斷。',
  'གནམ་སྡོང་འདིའི་འབྱུང་བས་ཉིན་གྱི་གནམ་སྡོང་གི་འབྱུང་བ་འཇོམས་ཤིང་阴阳 རིགས་མི་མཚུངས། དཔོན་གནས་དང་ལས་རིགས་ལ་ཐག་གཅོད་མིན།']},
 'god-pianYin':{title:['Pian Yin · 偏印','偏印','偏印','偏印 · སྐྱེད་པར་བྱེད་པའི་འབྲེལ་བ།'],copy:[
  'This stem’s element generates the day master’s element, and their Yin–Yang polarity is the same.',
  '生日主五行、且与日主阴阳属性相同的天干关系。',
  '生日主五行、且與日主陰陽屬性相同的天干關係。',
  'གནམ་སྡོང་འདིའི་འབྱུང་བས་ཉིན་གྱི་གནམ་སྡོང་གི་འབྱུང་བ་སྐྱེད་ཅིང་阴阳 རིགས་མཚུངས་པའི་འབྲེལ་བ།']},
 'god-zhengYin':{title:['Zheng Yin · 正印','正印','正印','正印 · སྐྱེད་པར་བྱེད་པའི་འབྲེལ་བ།'],copy:[
  'This stem’s element generates the day master’s element, and their Yin–Yang polarity is opposite.',
  '生日主五行、且与日主阴阳属性相反的天干关系。',
  '生日主五行、且與日主陰陽屬性相反的天干關係。',
  'གནམ་སྡོང་འདིའི་འབྱུང་བས་ཉིན་གྱི་གནམ་སྡོང་གི་འབྱུང་བ་སྐྱེད་ཅིང་阴阳 རིགས་མི་མཚུངས་པའི་འབྲེལ་བ།']},
 taiYuan:{title:['Tai Yuan','胎元','胎元','ཐའེ་ཡོན།'],copy:[
  'A traditional stem–branch value derived by advancing the natal month stem by one and its branch by three. It is not an actual conception date, pregnancy record or health assessment.',
  '按本命月干进一位、月支进三位推得的传统干支。它不是实际受孕日期、孕期记录或健康判断。',
  '按本命月干進一位、月支進三位推得的傳統干支。它不是實際受孕日期、孕期紀錄或健康判斷。',
  'སྐྱེས་དུས་ཟླ་བའི་གནམ་སྡོང་གཅིག་དང་ས་ཡལ་གསུམ་མདུན་དུ་སྤོས་ནས་རྩིས་པའི་སྲོལ་རྒྱུན་སྦྱོར་བ་ཡིན། དངོས་སུ་མངལ་ཆགས་པའི་ཚེས་དང་མངལ་གྱི་ཟིན་ཐོའམ་བདེ་ཐང་ལ་དཔྱད་པ་མིན།']},
 taiXi:{title:['Tai Xi','胎息','胎息','ཐའེ་ཞི།'],copy:[
  'A traditional stem–branch value using the day stem’s five-combination partner and the day branch’s six-combination partner under the selected day rule. It is not an actual conception date or a description of fetal breathing or health.',
  '依所选日柱规则，取日干的五合配对、日支的六合配对，组成传统干支。它不是实际受孕日期，也不描述胎儿呼吸或健康。',
  '依所選日柱規則，取日干的五合配對、日支的六合配對，組成傳統干支。它不是實際受孕日期，也不描述胎兒呼吸或健康。',
  'བདམས་པའི་ཉིན་ཀ་བའི་སྲོལ་ལྟར་ཉིན་སྡོང་དང་ཉིན་ཡལ་གྱི་སྦྱོར་ཟླ་ལས་རྩིས་པའི་སྲོལ་རྒྱུན་མིང་ཡིན། མངལ་ཆགས་པའི་ཚེས་མིན་ཞིང་མངལ་གྱི་དབུགས་དང་བདེ་ཐང་མི་སྟོན།']},
 mingGong:{title:['Ba Zi Ming Gong','八字命宫','八字命宮','བ་ཙིའི་མིང་གོང་།'],copy:[
  'An additional stem–branch value calculated from the month branch, hour branch and year stem by this library’s Ba Zi formula. It is separate from the twelve-palace structure used in Zi Wei Dou Shu.',
  '依本库八字算法，结合月支、时支与年干推得的辅助干支。它与紫微斗数的十二宫结构分开使用。',
  '依本庫八字算法，結合月支、時支與年干推得的輔助干支。它與紫微斗數的十二宮結構分開使用。',
  'རྩིས་ཆས་འདིའི་བ་ཙི་ཐབས་ལྟར་ཟླ་ཡལ་དང་དུས་ཡལ། ལོ་སྡོང་བཅས་ལས་རྩིས་པའི་སྦྱོར་བ་ཡིན། ཙི་ཝེའི་ཕོ་བྲང་བཅུ་གཉིས་ཀྱི་སྒྲོམ་དང་ཁ་ཁ་ཡིན།']},
 shenGong:{title:['Ba Zi Shen Gong','八字身宫','八字身宮','བ་ཙིའི་ཤེན་གོང་།'],copy:[
  'An additional stem–branch value calculated from the month branch, hour branch and year stem by this library’s Ba Zi formula. “Body palace” is a traditional name, not a body measurement or a medical finding.',
  '依本库八字算法，结合月支、时支与年干推得的辅助干支。“身宫”是传统名称，不是身体测量或医学结果。',
  '依本庫八字算法，結合月支、時支與年干推得的輔助干支。「身宮」是傳統名稱，不是身體測量或醫學結果。',
  'རྩིས་ཆས་འདིའི་བ་ཙི་ཐབས་ལྟར་ཟླ་ཡལ་དང་དུས་ཡལ། ལོ་སྡོང་བཅས་ལས་རྩིས་པའི་སྦྱོར་བ་ཡིན། ལུས་ཀྱི་ཕོ་བྲང་ཞེས་པ་སྲོལ་རྒྱུན་མིང་ཙམ་ཡིན་ཞིང་ལུས་ཚད་དང་གསོ་རིག་གི་འབྲས་བུ་མིན།']},
 smallFortune:{title:['Xiao Yun · minor periods','小运','小運','དུས་རབས་ཆུང་བ།'],copy:[
  'A yearly stem–branch sequence obtained by moving from the natal hour pillar in the fortune direction. It differs from Liu Nian, which uses the year’s own stem–branch. These are separate traditional reference sequences.',
  '以本命时柱为起点，按起运顺逆逐年推移的干支序列。它不同于以当年干支为依据的流年，两者是不同的传统对照序列。',
  '以本命時柱為起點，按起運順逆逐年推移的干支序列。它不同於以當年干支為依據的流年，兩者是不同的傳統對照序列。',
  'སྐྱེས་དུས་དུས་ཀྱི་ཀ་བ་ནས་མདུན་ཕྱིར་སྐྱོད་ཕྱོགས་ལྟར་ལོ་རེར་སྤོ་བའི་སྦྱོར་བའི་རིམ་པ་ཡིན། ལོ་རང་གི་སྦྱོར་བ་བཀོལ་བའི་ལོའི་རིམ་པ་དང་མི་འདྲ།']}
};
function lcbGlossaryEntry(id){
 if(id==='branchTenGod')id='branchTenGods';
 if(!Object.prototype.hasOwnProperty.call(lcbGlossaryData,id))return null;
 const row=lcbGlossaryData[id];
 return {id,title:lcText(...row.title),copy:lcText(...row.copy),related:[...(row.related||[])]};
}
function lcbGlossaryEscape(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function lcbTermButton(id,label){
 const entry=lcbGlossaryEntry(id);
 if(!entry)return lcbGlossaryEscape(label??id);
 const text=label==null?entry.title:String(label),hint=lcText('View explanation: ','查看解释：','查看解釋：','འགྲེལ་བཤད་ལ་ལྟ། ')+entry.title;
 return `<button type="button" class="lcb-term-button" data-lcb-glossary="${entry.id}" aria-haspopup="dialog" aria-controls="sheet" aria-label="${lcbGlossaryEscape(hint)}">${lcbGlossaryEscape(text)}</button>`;
}
function lcbTenGodButtons(names){
 const list=(Array.isArray(names)?names:[names]).filter(v=>v!==undefined&&v!==null&&String(v).trim());
 return list.length?list.map(value=>{
  const name=String(value),id=name==='日主'?'dayMaster':lcbGlossaryGods[name]||(name==='偏官'?'god-qiSha':null);
  return id?lcbTermButton(id,name):lcbGlossaryEscape(name);
 }).join(' <span aria-hidden="true">·</span> '):'—';
}
function lcbOpenGlossary(id,trigger){
 const entry=lcbGlossaryEntry(id);if(!entry)return false;
 if(trigger?.focus)trigger.focus({preventScroll:true});
 const related=entry.related.map(key=>lcbGlossaryEntry(key)).filter(Boolean);
 const body=`<div class="lcb-glossary-copy lcb-glossary-content" data-lcb-glossary-entry="${entry.id}"><p>${lcbGlossaryEscape(entry.copy)}</p>${related.length?`<div class="lcb-glossary-related">${related.map(row=>`<details><summary>${lcbGlossaryEscape(row.title)}</summary><p>${lcbGlossaryEscape(row.copy)}</p></details>`).join('')}</div>`:''}<p class="small">${lcText('These terms describe traditional calculation relationships. They do not determine fate, personality or health.','以上术语用于说明传统计算关系，不据此判断命运、人格或健康。','以上術語用於說明傳統計算關係，不據此判斷命運、人格或健康。','མིང་ཚིག་འདི་དག་སྲོལ་རྒྱུན་རྩིས་ཀྱི་འབྲེལ་བ་འགྲེལ་པར་བཀོལ། ལས་དབང་དང་གཤིས་ཀ་ཡང་ན་བདེ་ཐང་ཐག་གཅོད་མི་བྱེད།')}</p></div>`;
 sheet(lcbGlossaryEscape(entry.title),body,`<button type="button" class="btn secondary full" data-action="close-sheet">${lcText('Close explanation','关闭解释','關閉解釋','འགྲེལ་བཤད་ཁ་རྒྱོབ།')}</button>`);
 return true;
}
function lcbCloseGlossary(){closeSheet();}
document.addEventListener('click',event=>{
 const trigger=event.target.closest('[data-lcb-glossary]');if(!trigger)return;
 event.preventDefault();event.stopImmediatePropagation();lcbOpenGlossary(trigger.dataset.lcbGlossary,trigger);
},true);
