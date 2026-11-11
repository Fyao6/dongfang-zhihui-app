// Local UI dictionaries. Private input is never sent for translation.
const ewI18n=(()=>{
 const locales={zh:{tag:'zh-Hans',intl:'zh-CN',name:'简体中文'},'zh-Hant':{tag:'zh-Hant',intl:'zh-TW',name:'繁體中文'},en:{tag:'en',intl:'en-GB',name:'English'},bo:{tag:'bo',intl:'bo-CN',name:'བོད་ཡིག'}};
 const normalize=value=>({'zh-CN':'zh','zh-Hans':'zh','zh-TW':'zh-Hant','zh-HK':'zh-Hant','bo-CN':'bo'}[value]|| (locales[value]?value:'zh'));
 const traditional=OpenCC.Converter({from:'cn',to:'tw'});
 const missing=new Set(),used=new Set(),records=window.EW_LOCALE_CATALOG||{};
 const escapeRE=s=>s.replace(/[.*+?^\${}()|[\]\\]/g,'\\$&');
 const patterns=Object.keys(records).filter(k=>/\{\d+\}/.test(k)).map(key=>{
  const slots=[];let last=0,pattern='^';for(const m of key.matchAll(/\{(\d+)\}/g)){pattern+=escapeRE(key.slice(last,m.index))+'([\\s\\S]*?)';slots.push(m[1]);last=m.index+m[0].length;}
  return {key,slots,re:new RegExp(pattern+escapeRE(key.slice(last))+'$')};
 }).sort((a,b)=>b.key.length-a.key.length);
 function lookup(zh,en,lang){
  used.add(zh);const item=records[zh];if(lang==='en'&&en!==undefined)return en;if(item?.[lang])return item[lang];
  for(const p of patterns){const m=p.re.exec(zh);if(m&&records[p.key]?.[lang])return records[p.key][lang].replace(/\{(\d+)\}/g,(_,i)=>m[p.slots.indexOf(i)+1]??'');}
  if(lang==='zh-Hant')return traditional(zh);
  if(lang==='en')return en||item?.en||zh;
  if(lang==='bo'){missing.add(zh);return en||item?.en||zh;}
  return zh;
 }
 function text(en,zh,lang='zh'){
  lang=normalize(lang);
  if(Array.isArray(zh))return zh.map((v,i)=>text(Array.isArray(en)?en[i]:undefined,v,lang));
  if(zh&&typeof zh==='object'){const out={};for(const k of Object.keys(zh))out[k]=text(en?.[k],zh[k],lang);return out;}
  if(typeof zh!=='string')return lang==='en'?(en??zh):zh;
  if(!zh)return en||'';
  if(lang==='zh')return zh;
  return lookup(zh,typeof en==='string'?en:undefined,lang);
 }
 function content(item,field='',lang='zh'){
  const cap=s=>s[0].toUpperCase()+s.slice(1),key=s=>field?field+cap(s):s;lang=normalize(lang);
  const override=item?.[key(lang==='bo'?'bo':lang==='zh-Hant'?'hant':lang)];
  if(override!==undefined&&override!=='')return override;
  return text(item?.[key('en')],item?.[key('zh')]??'',lang);
 }
 function field(item,key,lang='zh'){
  const suffix={zh:'','zh-Hant':'Hant',en:'En',bo:'Bo'}[normalize(lang)];
  return item?.[key+suffix]||text(item?.[key+'En'],item?.[key]||'',lang);
 }
 function section(item,index,part,lang='zh'){
  const suffix={'zh-Hant':'Hant',en:'En',bo:'Bo'}[normalize(lang)],localized=suffix&&item?.['sections'+suffix]?.[index]?.[part],original=item?.sections?.[index]||[];
  return localized||text(original[part?3:1],original[part?2:0]||'',lang);
 }
 const error=(message,lang)=>normalize(lang)==='zh'?message:normalize(lang)==='zh-Hant'?traditional(message):records[message]?text(records[message].en,message,lang):text('The request could not be completed. Please try again.','请求未完成，请稍后重试。',lang);
 return {locales,normalize,text,content,field,section,traditional,missing,used,error};
})();
const ewIntlLocale=()=>ewI18n.locales[ewI18n.normalize(state.lang)].intl;

function ewFormatDate(value,options={}){
 const date=value instanceof Date?value:new Date(value);
 if(state.lang!=='bo')return new Intl.DateTimeFormat(ewIntlLocale(),options).format(date);
 const weekdays=['ཉི་མ།','ཟླ་བ།','མིག་དམར།','ལྷག་པ།','ཕུར་བུ།','པ་སངས།','སྤེན་པ།'],parts=[];
 if(options.year)parts.push(date.getFullYear()+' ལོ།');
 if(options.month)parts.push('ཟླ་ '+(date.getMonth()+1));
 if(options.day)parts.push('ཚེས་ '+date.getDate());
 if(options.weekday)parts.push((options.weekday==='long'?'གཟའ་':'')+weekdays[date.getDay()]);
 if(options.hour||options.minute||options.second){const time={};for(const k of ['hour','minute','second','hour12','hourCycle','timeZone'])if(options[k]!==undefined)time[k]=options[k];parts.push(new Intl.DateTimeFormat('en-GB',time).format(date));}
 return parts.join(' · ')||new Intl.DateTimeFormat('en-GB',options).format(date);
}

const ewLocaleOptions=()=>Object.entries(ewI18n.locales).map(([key,info])=>'<option value="'+key+'"'+(state.lang===key?' selected':'')+'>'+info.name+'</option>').join('');

