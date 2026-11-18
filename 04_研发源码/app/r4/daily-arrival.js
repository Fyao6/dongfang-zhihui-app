/* Explicit installation: no requests or writes until install() is called.
 * Daily acknowledgement lives at state.daily.arrivalSeen, inside the existing
 * account/device personal snapshot. It is technical metadata, not growth data.
 * This is a calendar and an optional practice greeting, never a fate forecast.
 */
(function (global) {
  'use strict';
  const SEEN_KEY='arrivalSeen',SHORTCUT_PAGES=new Set(['profile','profileSettings']);
  // Runtime flow guards, not an allowlist of ordinary reading pages. Unknown
  // pages with a visible form remain fail-closed until that form is gone.
  const SENSITIVE_PAGE=/^(?:account|devices|commerce|membership|member|payment|afterSales|privacy|serviceChat|conversation|publish|shareCompose|teacherRequest|profileName|profileAvatar)(?:[A-Z_-]|$)/;
  const PRACTICE_PAGES=new Set(['player','sessionDone']);
  let deferredObserver=null;
  const MIN_YEAR=1900,MAX_YEAR=2099;
  let installed=false,runtime=null,abort=null,pendingTimer=null,midnightTimer=null;
  const previous={};
  function text(en,zh,hant,bo){const lang=typeof state==='object'?state.lang:'zh',normalized=typeof ewI18n==='object'?ewI18n.normalize(lang):lang;if(normalized==='bo'&&bo)return bo;if(normalized==='zh-Hant'&&hant)return hant;return typeof ewI18n==='object'?ewI18n.text(en,zh,normalized):normalized==='en'?en:zh;}
  function el(tag,cls,value){const n=document.createElement(tag);if(cls)n.className=cls;if(value!==undefined)n.textContent=String(value);return n;}
  function button(label,action,cls=''){const n=el('button',cls,label);n.type='button';n.dataset.derAction=action;return n;}
  function token(){return typeof psToken==='function'?psToken():{scope:null,epoch:-1};}
  function dayKey(now=new Date()){return now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0');}
  function dateValue(day){if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day))return null;const d=new Date(day+'T12:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===day?d:null;}
  function identityReady(){const t=token();if(!t.scope||typeof px!=='object'||px.loaded!==true||px.authPending)return false;if(typeof pxConnection==='object'&&pxConnection.status!=='ready')return false;return px.user===null?t.scope==='guest':typeof px.user?.id==='string'&&px.user.id===t.scope;}
  function current(r,sequence){const t=token();return runtime===r&&t.scope===r.actor.scope&&t.epoch===r.actor.epoch&&r.day===dayKey()&&(sequence===undefined||r.sequence===sequence)&&identityReady();}
  function markerLevel(r){const marker=typeof state==='object'?state.daily?.[SEEN_KEY]:null;if(marker?.schema!==1||marker.day!==r.day||marker.accountId!==r.actor.scope||!Number.isFinite(Date.parse(marker.closedAt)))return -1;return marker.personal===true||['sandbox-member','production-member'].includes(marker.kind)?1:0;}
  const seen=(r,level=0)=>Math.max(markerLevel(r),r.closedLevel??-1)>=level;
  const personalLevel=r=>r.membership?.productionMember||r.membership?.sandboxMember?1:0;
  function ensure(){const t=token(),day=dayKey();if(!runtime||runtime.actor.scope!==t.scope||runtime.actor.epoch!==t.epoch||runtime.day!==day){if(runtime)close(runtime,'context');runtime={actor:t,day,sequence:0,entrySequence:0,checkedEntry:-1,lastPage:null,publicReady:null,loading:null,membership:null,error:null,panel:null,closedLevel:-1};}return runtime;}

  // Use server access facts, not status names, locally selected plans or badges.
  // The current product explicitly returns productionEnabled=false, therefore
  // it cannot qualify as a production paid subscription. Test-only membership
  // additionally requires the public sandbox-service flag mapped by pxBootstrap.
  function classifyMembership(dto,accountId,sandboxServiceReady=false){
    if(typeof accountId!=='string'||!accountId.trim()||!dto||dto.accountId!==accountId||!Array.isArray(dto.items)||typeof dto.productionEnabled!=='boolean')throw new Error('membership_owner_or_shape');
    if(dto.items.some(x=>!x||x.accountId!==accountId))throw new Error('membership_item_owner');
    const production=dto.productionEnabled===true&&dto.items.some(x=>x.environment==='production'&&x.productionEnabled===true&&x.grantsProductionAccess===true&&x.sandboxOnly!==true&&x.management?.providerVerified===true);
    const sandbox=dto.items.some(x=>x.environment==='sandbox'&&x.sandboxOnly===true&&x.hasSandboxAccess===true&&x.grantsProductionAccess===false);
    const sandboxMember=sandboxServiceReady===true&&sandbox;
    return {verified:true,kind:production?'production-member':sandboxMember?'sandbox-member':'general',productionMember:production,sandboxAccess:sandbox,sandboxMember};
  }
  async function status(r,force=false){
    if(!current(r))return false;if(!force&&r.membership)return true;if(r.loading)return r.loading;
    if(r.actor.scope==='guest'&&px.user===null){r.membership={verified:true,kind:'guest',productionMember:false,sandboxAccess:false,sandboxMember:false};r.checkedEntry=r.entrySequence;r.error=null;return true;}
    const seq=++r.sequence,entry=r.entrySequence;
    const task=(async()=>{try{const dto=await pxApi('membership/status');if(!current(r,seq))return false;r.membership=classifyMembership(dto,r.actor.scope,px.membershipServiceReady===true);r.checkedEntry=entry;r.error=null;return true;}catch(error){if(current(r,seq)){r.membership={verified:false,kind:'unconfirmed',productionMember:false,sandboxAccess:false,sandboxMember:false};r.checkedEntry=entry;r.error=error?.status===401||error?.status===403?'identity_recheck_required':'membership_unavailable';}return false;}finally{if(runtime===r&&r.sequence===seq)r.loading=null;}})();
    r.loading=task;return task;
  }
  function calendarDay(day,library){
    const d=dateValue(day);if(!d||d.getUTCFullYear()<MIN_YEAR||d.getUTCFullYear()>MAX_YEAR)throw new Error('calendar_date_range');
    const result={date:day,weekday:d.getUTCDay(),lunar:null,error:null};
    try{
      const lib=library===undefined?(typeof LCLunar!=='undefined'?LCLunar:null):library;
      if(!lib?.Solar?.fromYmd)throw new Error('calendar_engine_unavailable');
      const solar=lib.Solar.fromYmd(d.getUTCFullYear(),d.getUTCMonth()+1,d.getUTCDate()),lunar=solar.getLunar();
      const year=lunar.getYear(),month=lunar.getMonth(),number=lunar.getDay();
      if(!Number.isInteger(year)||!Number.isInteger(month)||!Number.isInteger(number))throw new Error('calendar_engine_result');
      result.lunar={year,month:Math.abs(month),day:number,leapMonth:month<0,ganZhi:{year:lunar.getYearInGanZhi(),month:lunar.getMonthInGanZhi(),day:lunar.getDayInGanZhi()},solarTerm:lunar.getJieQi(),festivals:[...new Set([...solar.getFestivals(),...solar.getOtherFestivals(),...lunar.getFestivals(),...lunar.getOtherFestivals()])]};
    }catch{result.error='calendar_engine_unavailable';}
    return result;
  }
  function calendarMonth(year,month,library){
    if(!Number.isInteger(year)||year<MIN_YEAR||year>MAX_YEAR||!Number.isInteger(month)||month<1||month>12)throw new Error('calendar_month_range');
    const days=new Date(Date.UTC(year,month,0,12)).getUTCDate(),first=new Date(Date.UTC(year,month-1,1,12)).getUTCDay();
    return {year,month,leading:(first+6)%7,days:Array.from({length:days},(_,i)=>calendarDay(year+'-'+String(month).padStart(2,'0')+'-'+String(i+1).padStart(2,'0'),library))};
  }
  function isBirthday(profile,day){return !!(dateValue(profile?.date)&&dateValue(day)&&profile.date.slice(5)===day.slice(5));}
  function practiceTheme(recommendation){const names={breath:['Today is your day for stillness','今天是你的静心之日','今天是你的靜心之日','དེ་རིང་ཁྱེད་ཀྱི་སེམས་ཞི་བའི་ཉིན་མོ་ཡིན།'],ground:['Today is your day for grounding','今天是你的安住之日','今天是你的安住之日','དེ་རིང་ཁྱེད་ཀྱི་ལྷིང་འཇགས་ཀྱི་ཉིན་མོ་ཡིན།'],scan:['Today is your day for awareness','今天是你的觉察之日','今天是你的覺察之日','དེ་རིང་ཁྱེད་ཀྱི་དྲན་ཤེས་ཀྱི་ཉིན་མོ་ཡིན།'],sleep:['Today is your day for rest','今天是你的休养之日','今天是你的休養之日','དེ་རིང་ཁྱེད་ཀྱི་ངལ་གསོའི་ཉིན་མོ་ཡིན།']};return Object.hasOwn(names,recommendation?.key)?{key:recommendation.key,title:text(...names[recommendation.key]),reason:typeof recommendation.reason==='string'?recommendation.reason:''}:null;}
  function personalGreeting(){
    let recommendation=null,profile=null;try{if(typeof journeyRecommendation==='function')recommendation=journeyRecommendation();}catch{}try{if(typeof lbProfile==='function')profile=lbProfile();}catch{}
    const theme=practiceTheme(recommendation),selfReport=typeof body4Entry==='function'?body4Entry():null;
    return {theme,birthday:isBirthday(profile,dayKey()),hasSelfReport:!!selfReport,hasPriorPractice:!!recommendation?.last};
  }
  function visible(node){if(!node||!node.isConnected||!node.getClientRects().length)return false;const style=getComputedStyle(node);return style.display!=='none'&&style.visibility!=='hidden'&&style.visibility!=='collapse';}
  function mediaPlaying(){
    if(typeof state==='object'&&state.audioPlaying===true)return true;
    if(typeof musicPlayback==='object'&&musicPlayback.playing===true)return true;
    if(typeof pxNative==='object'&&pxNative.audio&&!pxNative.audio.paused&&!pxNative.audio.ended)return true;
    return [...document.querySelectorAll('audio,video')].some(media=>!media.paused&&!media.ended);
  }
  function blockReason(r){
    if(!current(r))return 'identity_pending';if(document.hidden||typeof document.hasFocus==='function'&&!document.hasFocus())return 'not_foreground';if(r.panel)return 'reminder_open';
    if(document.querySelector('dialog[open]')||[...document.querySelectorAll('[aria-modal="true"]')].some(visible))return 'existing_dialog';
    if(px.busy||px.authPending)return 'active_request';if(PRACTICE_PAGES.has(String(state.page))||SENSITIVE_PAGE.test(String(state.page)))return 'sensitive_flow';
    if([...document.querySelectorAll('#app form')].some(visible))return 'visible_form';
    if(document.activeElement?.matches('input,textarea,select,[contenteditable="true"]')||document.activeElement?.isContentEditable)return 'editing';if(mediaPlaying())return 'media_playing';return null;
  }
  const blocked=r=>blockReason(r)!==null;
  function relevantMutation(record){
    const selector='form,dialog,audio,video,[aria-modal],[aria-busy],details';
    if(record.type==='attributes')return record.target?.matches?.(selector)||!!record.target?.querySelector?.(selector);
    return [...record.addedNodes,...record.removedNodes].some(node=>node.nodeType===1&&(node.matches(selector)||node.querySelector(selector)));
  }
  function acknowledge(r,panel){
    if(!current(r)||!panel.shown||panel.day!==r.day||panel.actor.scope!==r.actor.scope||panel.actor.epoch!==r.actor.epoch)return false;
    const prior=markerLevel(r),level=Math.max(prior,r.closedLevel,panel.personalPresented?1:0);r.closedLevel=level;
    if(typeof psCommit!=='function'||!state.daily||typeof state.daily!=='object')return false;
    const old=state.daily[SEEN_KEY],kind=level===1?(panel.personalPresented?panel.presentedKind:prior===1?old.kind:'sandbox-member'):(r.membership?.verified?r.membership.kind:'unconfirmed');
    return psCommit(()=>{state.daily[SEEN_KEY]={schema:1,day:r.day,accountId:r.actor.scope,closedAt:new Date().toISOString(),kind,personal:level===1};});
  }
  function close(r,reason='user'){
    const panel=r?.panel;if(!panel)return false;r.panel=null;
    const mark=reason==='user'&&panel.automatic;let saved=false;
    panel.abort.abort();if(panel.dialog.open)panel.dialog.close();panel.dialog.remove();
    if(mark)saved=acknowledge(r,panel);
    if(reason==='user'&&current(r)&&panel.focus?.isConnected&&!panel.focus.closest('[inert]'))panel.focus.focus({preventScroll:true});
    if(mark&&!saved&&current(r)&&typeof toast==='function')toast(text('Closed for now. The daily acknowledgement was not saved on this device.','本次已关闭；本机尚未保存今日已读标记。','本次已關閉；本機尚未儲存今日已讀標記。','ད་ལྟ་ཁ་བརྒྱབ་ཟིན། དེ་རིང་བལྟས་པའི་རྟགས་ཉར་མ་ཐུབ།'));
    if(installed)schedule();return true;
  }
  function selectedDetail(panel){
    const host=panel.dialog.querySelector('[data-der-day-detail]');host.replaceChildren();
    const value=calendarDay(panel.selected),dateTitle=el('h3','',value.date);host.append(dateTitle);
    if(!value.lunar){host.append(el('p','der-error',text('The lunar calendar engine is unavailable. Only the Gregorian date is shown; no lunar date has been estimated.','农历引擎暂不可用，仅显示公历日期，不推测农历。','農曆引擎暫不可用，僅顯示公曆日期，不推測農曆。','ཟླ་ཐོའི་རྩིས་འཁོར་སྤྱོད་མི་ཐུབ། སྤྱི་ལོའི་ཚེས་ཁོ་ན་སྟོན།')));return;}
    const l=value.lunar;host.append(el('p','der-lunar-date',text('Chinese lunar date','中国农历','中國農曆','རྒྱ་ནག་གི་ཟླ་ཐོ།')+' · '+l.year+' / '+l.month+' / '+l.day+(l.leapMonth?' · '+text('Leap month','闰月','閏月','བཤོལ་ཟླ།'):'')));
    const facts=el('dl','der-calendar-facts');for(const [name,number]of [[text('Year stem–branch','年干支','年干支','ལོའི་གནམ་ས་སྡེབ།'),l.ganZhi.year],[text('Month stem–branch','月干支','月干支','ཟླ་བའི་གནམ་ས་སྡེབ།'),l.ganZhi.month],[text('Day stem–branch','日干支','日干支','ཉིན་གྱི་གནམ་ས་སྡེབ།'),l.ganZhi.day]]){const row=el('div');row.append(el('dt','',name),el('dd','',number));facts.append(row);}host.append(facts);
    if(l.solarTerm)host.append(el('p','der-term',text('Solar term','节气','節氣','དུས་ཚིགས།')+' · '+l.solarTerm));
    if(l.festivals.length)host.append(el('p','der-festivals',text('Traditional / calendar observances','历法与民俗节日','曆法與民俗節日','ཟླ་ཐོ་དང་དམངས་སྲོལ་དུས་ཆེན།')+' · '+l.festivals.join(' · ')));
  }
  function monthLabel(year,month){try{const locale=typeof ewIntlLocale==='function'?ewIntlLocale():'zh-CN';return new Intl.DateTimeFormat(locale,{year:'numeric',month:'long',timeZone:'UTC'}).format(new Date(Date.UTC(year,month-1,1,12)));}catch{return year+' / '+month;}}
  function calendar(panel,focusDay){
    const host=panel.dialog.querySelector('[data-der-calendar]');host.replaceChildren();const data=calendarMonth(panel.year,panel.month);
    const nav=el('div','der-month-nav'),prev=button('‹','previous-month'),next=button('›','next-month'),heading=el('h3','',monthLabel(panel.year,panel.month));heading.id='der-month-label';
    prev.setAttribute('aria-label',text('Previous month','上个月','上個月','ཟླ་སྔོན་མ།'));next.setAttribute('aria-label',text('Next month','下个月','下個月','ཟླ་རྗེས་མ།'));prev.disabled=panel.year===MIN_YEAR&&panel.month===1;next.disabled=panel.year===MAX_YEAR&&panel.month===12;nav.append(prev,heading,next);host.append(nav);
    const pickerLabel=el('label','der-month-picker',text('Choose month','选择月份','選擇月份','ཟླ་བ་འདེམས།')),picker=el('input');picker.type='month';picker.min=MIN_YEAR+'-01';picker.max=MAX_YEAR+'-12';picker.value=panel.year+'-'+String(panel.month).padStart(2,'0');picker.dataset.derMonth='';pickerLabel.append(picker);host.append(pickerLabel);
    const grid=el('div','der-month-grid');grid.setAttribute('role','grid');grid.setAttribute('aria-labelledby','der-month-label');const headings=el('div','der-week');headings.setAttribute('role','row');
    for(let i=0;i<7;i++){let name;try{name=new Intl.DateTimeFormat(typeof ewIntlLocale==='function'?ewIntlLocale():'zh-CN',{weekday:'short',timeZone:'UTC'}).format(new Date(Date.UTC(2024,0,1+i,12)));}catch{name=String(i+1);}const col=el('span','der-weekday',name);col.setAttribute('role','columnheader');headings.append(col);}grid.append(headings);
    const cells=[...Array(data.leading).fill(null),...data.days];while(cells.length%7)cells.push(null);
    for(let start=0;start<cells.length;start+=7){const row=el('div','der-week');row.setAttribute('role','row');for(const value of cells.slice(start,start+7)){if(!value){const blank=el('span','der-blank');blank.setAttribute('role','gridcell');blank.setAttribute('aria-disabled','true');row.append(blank);continue;}
      const b=button('','select-date','der-day');b.dataset.derDate=value.date;b.setAttribute('role','gridcell');b.setAttribute('aria-selected',String(value.date===panel.selected));b.setAttribute('aria-label',value.date+(value.lunar?' · '+text('Lunar','农历','農曆','ཟླ་ཐོ།')+' '+value.lunar.month+'/'+value.lunar.day:''));b.tabIndex=value.date===panel.selected?0:-1;
      if(value.date===dayKey())b.setAttribute('aria-current','date');b.append(el('span','der-day-number',Number(value.date.slice(8))));b.append(el('small','der-day-lunar',value.lunar?(value.lunar.solarTerm||String(value.lunar.day)):'—'));row.append(b);}grid.append(row);}host.append(grid);
    const today=button(text('Return to today','回到今天','回到今天','དེ་རིང་ལ་ལོག'),'today','der-link');host.append(today);selectedDetail(panel);
    if(focusDay)host.querySelector('[data-der-date="'+focusDay+'"]')?.focus({preventScroll:true});
  }
  function greeting(r,panel){
    const host=panel.dialog.querySelector('[data-der-greeting]');host.replaceChildren();panel.sandbox=r.membership?.verified===true&&r.membership.sandboxMember===true&&!r.membership.productionMember;const member=r.membership?.productionMember===true||panel.sandbox;
    panel.personalActive=member;panel.activeKind=panel.sandbox?'sandbox-member':member?'production-member':r.membership?.kind||'unconfirmed';panel.dialog.dataset.derKind=panel.activeKind;
    if(panel.shown&&member){panel.personalPresented=true;panel.presentedKind=panel.activeKind;}
    if(panel.sandbox)host.append(el('p','der-test-note',text('TEST MEMBERSHIP REMINDER · NO ACTUAL CHARGE · no production paid entitlement','测试会员专属提醒 · 未实际扣款 · 不代表正式付费权益','測試會員專屬提醒 · 未實際扣款 · 不代表正式付費權益','ཚོད་ལྟའི་ཚོགས་མིའི་དྲན་སྐུལ། དངུལ་དངོས་མ་ལེན། ཁེ་དབང་དངོས་མ་ཡིན།')));
    if(!r.membership?.verified){host.append(el('p','der-unconfirmed',text('Membership could not be confirmed. This is the general calendar, not a confirmed membership decision.','暂未确认会员状态，先显示通用日历，不据此判定你是否为付费会员。','暫未確認會員狀態，先顯示通用日曆，不據此判定你是否為付費會員。','ཚོགས་མིའི་གནས་ཚུལ་ངེས་གཏན་མ་བྱས། སྤྱི་སྤྱོད་ཟླ་ཐོ་སྟོན།')));const retry=button(text('Retry membership check','重试会员状态','重試會員狀態','ཚོགས་མིའི་གནས་ཚུལ་བསྐྱར་བལྟ།'),'retry','der-link');retry.disabled=!!r.loading;host.append(retry);}
    if(member){const personal=personalGreeting();host.append(el('h2','der-personal-title',personal.theme?.title||text('A moment for yourself today','今天，给自己留一个片刻','今天，給自己留一個片刻','དེ་རིང་རང་ལ་དུས་ཐུང་ཞིག་སྟེར།')));
      host.append(el('p','der-basis',text('Based on your own check-ins and practice feedback, not a birth-chart or fortune calculation.','依据本人的自述与练习反馈，不作命理推算或吉凶判断。','依據本人的自述與練習回饋，不作命理推算或吉凶判斷。','རང་གི་ཚོར་བ་དང་ཉམས་ལེན་གྱི་ལན་ལ་གཞི་བཅོལ། ལས་དབང་རྩིས་མིན།')));
      if(personal.theme?.reason)host.append(el('p','der-reason',personal.theme.reason));if(!personal.hasSelfReport&&!personal.hasPriorPractice)host.append(el('p','der-basis',text('No personal check-in is available. This is an optional starting point, not a personalized calculation.','目前没有可用的个人自述；这是可选的练习起点，并非已替你推算。','目前沒有可用的個人自述；這是可選的練習起點，並非已替你推算。','རང་གི་ཚོར་བའི་ཟིན་ཐོ་མེད། འདི་གདམ་གའི་འགོ་འཛུགས་ཙམ་ཡིན།')));
      if(personal.birthday)host.append(el('p','der-birthday',text('Happy birthday. May you have a gentle moment for yourself today.','生日快乐。愿你今天也为自己留一点温柔的时间。','生日快樂。願你今天也為自己留一點溫柔的時間。','སྐྱེས་སྐར་བཀྲ་ཤིས། དེ་རིང་རང་ལ་བརྩེ་བའི་དུས་ཚོད་ཞིག་སྟེར།')));
      if(personal.theme){const practice=button(text('Begin this practice','开始这段练习','開始這段練習','ཉམས་ལེན་འདི་འགོ་འཛུགས།'),'practice','der-primary');practice.dataset.derPractice=personal.theme.key;host.append(practice);}
    }else host.append(el('h2','der-personal-title',text('A calendar for your day','今天的万年历','今天的萬年曆','དེ་རིང་གི་ཟླ་ཐོ།')));
    if(r.membership?.sandboxMember&&!panel.sandbox)host.append(button(text('Open sandbox reminder preview · not paid production access','查看测试提醒 · 不代表正式付费','查看測試提醒 · 不代表正式付費','ཚོད་ལྟའི་དྲན་སྐུལ་ལྟ།'),'sandbox','der-link'));
  }
  function show(r,{automatic=false,sandbox=false}={}){
    if(blocked(r)||sandbox&&!r.membership?.sandboxMember)return false;
    const dialog=el('dialog','der-dialog'),panel={dialog,actor:{...r.actor},day:r.day,page:state.page,automatic,sandbox,shown:false,focus:document.activeElement,abort:new AbortController(),selected:r.day,year:Number(r.day.slice(0,4)),month:Number(r.day.slice(5,7))};
    dialog.setAttribute('aria-labelledby','der-title');const header=el('header','der-header'),title=el('h1','',text('Today, at your own pace','今天，按自己的节奏','今天，按自己的節奏','དེ་རིང་རང་གི་གོམ་སྟབས་ལྟར།'));title.id='der-title';const x=button(text('Close','关闭','關閉','ཁ་རྒྱོབ།'),'close','der-close');header.append(title,x);
    const greet=el('section','der-greeting');greet.dataset.derGreeting='';const cal=el('section','der-calendar');cal.dataset.derCalendar='';const detail=el('section','der-selected-day');detail.dataset.derDayDetail='';detail.setAttribute('aria-live','polite');
    const note=el('p','der-source-note',text('Calendar facts from the bundled lunar-javascript engine. Traditional names are kept in the source language; these are not official holiday arrangements or personal fortune advice. The daily reminder follows this device’s local date.','历法来自本机内置农历引擎，民俗名称保留原文；不代表官方放假安排或个人吉凶建议。每日提醒按此设备的本地日期。','曆法來自本機內建農曆引擎，民俗名稱保留原文；不代表官方放假安排或個人吉凶建議。每日提醒按此裝置的本地日期。','ཟླ་ཐོ་རང་འཕྲུལ་གྱི་རྩིས་འཁོར་ལས་ཡིན། དམངས་སྲོལ་མིང་མ་ཡིག་ལྟར་ཡིན། ལས་དབང་བསླབ་བྱ་མིན། ཉིན་གྲངས་འཕྲུལ་ཆས་འདིའི་དུས་ཁུལ་ལྟར་ཡིན།'));
    const footer=el('footer','der-footer');footer.append(button(text('Return','返回','返回','ལོག'),'close','der-primary'));dialog.append(header,greet,cal,detail,note,footer);r.panel=panel;
    const opts={signal:panel.abort.signal};
    dialog.addEventListener('cancel',e=>{e.preventDefault();close(r,'user');},opts);
    dialog.addEventListener('close',()=>{if(r.panel===panel)close(r,'context');},opts);
    dialog.addEventListener('click',async event=>{const b=event.target.closest('[data-der-action]');if(!b||!current(r)||r.panel!==panel)return;const a=b.dataset.derAction;
      if(a==='close'){close(r,'user');return;}if(a==='retry'){b.disabled=true;await status(r,true);if(current(r)&&r.panel===panel)greeting(r,panel);return;}
      if(a==='sandbox'){panel.sandbox=true;greeting(r,panel);return;}
      if(a==='practice'){const key=b.dataset.derPractice;if(!['breath','ground','scan','sleep'].includes(key)||typeof journeyStart!=='function')return;close(r,'user');if(current(r))journeyStart(key);return;}
      if(a==='select-date')panel.selected=b.dataset.derDate;else if(a==='today'){panel.selected=r.day;panel.year=Number(r.day.slice(0,4));panel.month=Number(r.day.slice(5,7));}
      else if(a==='previous-month'||a==='next-month'){const d=new Date(Date.UTC(panel.year,panel.month-1+(a==='next-month'?1:-1),1,12));if(d.getUTCFullYear()<MIN_YEAR||d.getUTCFullYear()>MAX_YEAR)return;panel.year=d.getUTCFullYear();panel.month=d.getUTCMonth()+1;panel.selected=panel.year+'-'+String(panel.month).padStart(2,'0')+'-01';}else return;calendar(panel,panel.selected);
    },opts);
    dialog.addEventListener('change',event=>{const input=event.target.closest('[data-der-month]');if(!input||!current(r)||r.panel!==panel||!/^\d{4}-\d{2}$/.test(input.value))return;const [y,m]=input.value.split('-').map(Number);if(y<MIN_YEAR||y>MAX_YEAR||m<1||m>12)return;panel.year=y;panel.month=m;panel.selected=input.value+'-01';calendar(panel,panel.selected);},opts);
    dialog.addEventListener('keydown',event=>{const selected=event.target.closest('[data-der-date]');if(!selected||!current(r)||r.panel!==panel)return;const d=dateValue(selected.dataset.derDate);let changed=true;if(event.key==='ArrowRight')d.setUTCDate(d.getUTCDate()+1);else if(event.key==='ArrowLeft')d.setUTCDate(d.getUTCDate()-1);else if(event.key==='ArrowDown')d.setUTCDate(d.getUTCDate()+7);else if(event.key==='ArrowUp')d.setUTCDate(d.getUTCDate()-7);else if(event.key==='Home')d.setUTCDate(d.getUTCDate()-(d.getUTCDay()+6)%7);else if(event.key==='End')d.setUTCDate(d.getUTCDate()+6-(d.getUTCDay()+6)%7);else changed=false;if(!changed)return;event.preventDefault();if(d.getUTCFullYear()<MIN_YEAR||d.getUTCFullYear()>MAX_YEAR)return;panel.selected=d.toISOString().slice(0,10);panel.year=d.getUTCFullYear();panel.month=d.getUTCMonth()+1;calendar(panel,panel.selected);},opts);
    document.body.append(dialog);greeting(r,panel);calendar(panel);
    try{dialog.showModal();}catch{r.panel=null;panel.abort.abort();dialog.remove();return false;}
    requestAnimationFrame(()=>{if(current(r)&&r.panel===panel&&panel.page===state.page&&dialog.open&&!document.hidden&&dialog.getBoundingClientRect().height>0){panel.shown=true;dialog.dataset.derShown='true';if(panel.personalActive){panel.personalPresented=true;panel.presentedKind=panel.activeKind;}x.focus({preventScroll:true});}});return true;
  }
  async function openCalendar(){if(!installed||!identityReady())return false;const r=ensure(),page=state.page;if(blocked(r))return false;await status(r,true);if(!current(r)||state.page!==page)return false;return show(r,{automatic:!seen(r,personalLevel(r))});}
  async function openSandboxPreview(){if(!installed||!identityReady())return false;const r=ensure(),page=state.page;if(blocked(r))return false;await status(r,true);return current(r)&&state.page===page&&r.membership?.sandboxMember===true?show(r,{sandbox:true}):false;}
  function shortcut(){const host=document.querySelector('#app > section');if(!host||!SHORTCUT_PAGES.has(state.page)||host.querySelector('[data-der-shortcut]'))return;const b=button(text('Open calendar & today’s reminder','再看日历与今日提醒','再看日曆與今日提醒','ཟླ་ཐོ་དང་དེ་རིང་གི་དྲན་སྐུལ་ལྟ།'),'open','der-shortcut');b.dataset.derShortcut='';b.addEventListener('click',()=>{void openCalendar();},{signal:abort.signal});host.append(b);}
  async function check(){
    if(!installed)return;const r=ensure();if(r.panel&&!current(r))close(r,'context');
    if(seen(r,1)){r.deferredReason=null;return;}
    const before=blockReason(r);if(before){r.deferredReason=before;return;}r.deferredReason=null;
    await status(r,r.checkedEntry!==r.entrySequence);if(!current(r)||seen(r,personalLevel(r)))return;
    const after=blockReason(r);if(after){r.deferredReason=after;return;}show(r,{automatic:true});
  }
  function schedule(){if(!installed)return;clearTimeout(pendingTimer);pendingTimer=setTimeout(()=>{pendingTimer=null;void check();},120);}
  function refresh(){if(!installed)return;ensure().entrySequence++;schedule();}
  function nextDay(){clearTimeout(midnightTimer);const now=new Date(),next=new Date(now.getFullYear(),now.getMonth(),now.getDate()+1,0,0,1);midnightTimer=setTimeout(()=>{schedule();nextDay();},Math.max(1000,next-now));}
  function install(){
    if(installed)return true;if(typeof document!=='object'||typeof pxApi!=='function'||typeof renderNow!=='function'||typeof psToken!=='function')return false;
    installed=true;abort=new AbortController();previous.render=renderNow;
    renderNow=function(...args){const r=runtime;if(r?.panel&&(r.panel.page!==state.page||!current(r)))close(r,'context');const result=previous.render.apply(this,args),s=ensure(),ready=typeof px==='object'&&px.membershipServiceReady===true;if(s.lastPage!==state.page||s.publicReady!==ready){s.lastPage=state.page;s.publicReady=ready;s.entrySequence++;}shortcut();schedule();return result;};previous.renderWrapper=renderNow;
    if(typeof psSwitch==='function'){previous.switch=psSwitch;psSwitch=function(...args){if(args[0]!==token().scope){if(runtime)close(runtime,'context');if(runtime)runtime.sequence++;runtime=null;}const result=previous.switch.apply(this,args);schedule();return result;};previous.switchWrapper=psSwitch;}
    if(typeof mlLoad==='function'){previous.membershipLoad=mlLoad;mlLoad=async function(...args){const actor=token(),result=await previous.membershipLoad.apply(this,args),now=token();if(actor.scope===now.scope&&actor.epoch===now.epoch)refresh();return result;};previous.membershipLoadWrapper=mlLoad;}
    const options={signal:abort.signal};document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();},options);document.addEventListener('close',schedule,{...options,capture:true});document.addEventListener('focusout',schedule,options);
    for(const event of ['pause','ended','emptied'])document.addEventListener(event,schedule,{...options,capture:true});
    global.addEventListener('focus',refresh,options);global.addEventListener('blur',()=>{if(runtime)runtime.deferredReason='not_foreground';},options);global.addEventListener('pageshow',refresh,options);
    if(typeof MutationObserver==='function'){deferredObserver=new MutationObserver(records=>{if(runtime?.deferredReason&&records.some(relevantMutation))schedule();});deferredObserver.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['open','hidden','style','class','aria-hidden','aria-modal','aria-busy']});}global.addEventListener('pagehide',()=>{if(runtime)close(runtime,'context');},options);global.addEventListener('popstate',()=>{if(runtime?.panel)close(runtime,'user');schedule();},options);
    shortcut();nextDay();schedule();return true;
  }
  function uninstall(){if(!installed)return;installed=false;clearTimeout(pendingTimer);clearTimeout(midnightTimer);abort.abort();deferredObserver?.disconnect();deferredObserver=null;if(runtime)close(runtime,'context');runtime=null;if(renderNow===previous.renderWrapper)renderNow=previous.render;if(typeof psSwitch==='function'&&psSwitch===previous.switchWrapper)psSwitch=previous.switch;if(typeof mlLoad==='function'&&mlLoad===previous.membershipLoadWrapper)mlLoad=previous.membershipLoad;document.querySelectorAll('[data-der-shortcut]').forEach(n=>n.remove());}
  function snapshot(){return {candidateOnly:false,installed,actorCurrent:!!runtime&&current(runtime),day:runtime?.day||null,classification:runtime?.membership?.kind||'not_checked',verified:runtime?.membership?.verified===true,dialogOpen:!!runtime?.panel?.dialog.open,shown:runtime?.panel?.shown===true,acknowledgedLevel:runtime?Math.max(markerLevel(runtime),runtime.closedLevel):-1,seenField:'daily.'+SEEN_KEY,dayBasis:'device_local_date',serverDailyAcknowledgement:false,deferredReason:runtime?.deferredReason||null,manualEntryPages:['profile','profileSettings'],automaticReadOnlyDeepLinks:true};}
  const api=Object.freeze({install,uninstall,openCalendar,openSandboxPreview,refresh,snapshot,classifyMembership,calendarDay,calendarMonth,isBirthday,practiceTheme,dayKey,candidateOnly:false,explicitInstallationRequired:true,seenKey:SEEN_KEY});
  if(typeof module==='object'&&module.exports)module.exports=api;else global.DailyEntryReminderCandidate=api;
})(typeof window==='object'?window:globalThis);
