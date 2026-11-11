
const fs=require('fs'),path=require('path');const root=path.resolve(__dirname,'..'),r=path.join(root,'04_研发源码/app/r4'),acorn=require(path.join(root,'04_研发源码/app/cloud/node_modules/acorn'));
for(const file of fs.readdirSync(r).filter(f=>f.endsWith('.js')&&!f.startsWith('i18n'))){
 let text=fs.readFileSync(path.join(r,file),'utf8'),ast=acorn.parse(text,{ecmaVersion:'latest'}),edits=[];
 function walk(n){if(!n?.type)return;
 if(n.type==='ConditionalExpression'&&/^state\.lang\s*===\s*'zh'$/.test(text.slice(n.test.start,n.test.end))){
  const zh=text.slice(n.consequent.start,n.consequent.end),en=text.slice(n.alternate.start,n.alternate.end);
  if(zh==="'zh-CN'")edits.push([n.start,n.end,'ewIntlLocale()']);
  else if(zh!=="'selected'"&&!(zh==='zh'&&en==='en')){
   if(['item.base','result.base'].includes(zh))edits.push([n.test.start,n.test.end,"['zh','zh-Hant'].includes(state.lang)"]);
   else edits.push([n.start,n.end,'t('+en+','+zh+')']);
  }
 }
 for(const [k,v] of Object.entries(n)){if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);}
 }walk(ast);
 edits.sort((a,b)=>b[0]-a[0]);let before=text.length+1;
 for(const [a,b,replacement] of edits){if(b>before)continue;text=text.slice(0,a)+replacement+text.slice(b);before=a;}
 text=text.replace(/<select id="language-select">[\s\S]*?<\/select>/g,'<select id="language-select">'+String.fromCharCode(36)+'{ewLocaleOptions()}</select>');
 if(file==='base.js'){
  text=text.replace("lang: initial.lang || stored.lang || 'zh'","lang: ewI18n.normalize(q.get('lang') || initial.lang || stored.lang || 'zh')");
  text=text.replace("const t = (en, zh) => state.lang === 'zh' ? zh : en;","const t = (en, zh) => ewI18n.text(en, zh, state.lang);");
  text=text.replace("document.documentElement.lang=ewIntlLocale()","document.documentElement.lang=ewI18n.locales[state.lang].tag");
  text=text.replace("state.lang=e.target.value;render(false);","ewChangeLanguage(e.target.value);");
  text=text.replace("if(['en','zh'].includes(d.lang))state.lang=d.lang","if(['en','zh','zh-Hant','bo','zh-Hans','zh-CN','zh-TW'].includes(d.lang))state.lang=ewI18n.normalize(d.lang)");
 }
 if(file==='life.js')text=text.replace("state.lang==='en'?window.iztro","['en','bo'].includes(state.lang)?window.iztro");
 fs.writeFileSync(path.join(r,file),text);
}
console.log('Replaced bilingual branches and selectors.');

