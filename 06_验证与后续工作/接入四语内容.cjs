
const fs=require('fs'),path=require('path');const r=path.resolve(__dirname,'../04_研发源码/app/r4'),acorn=require(path.join(r,'../cloud/node_modules/acorn'));
for(const file of fs.readdirSync(r).filter(f=>f.endsWith('.js')&&!f.startsWith('i18n'))){
 let text=fs.readFileSync(path.join(r,file),'utf8'),ast=acorn.parse(text,{ecmaVersion:'latest'}),edits=[];
 function walk(n){if(!n?.type)return;
 if(n.type==='CallExpression'&&n.callee.name==='t'&&n.arguments.length===2){
  const [en,zh]=n.arguments;
  if(zh?.type==='MemberExpression'&&!zh.computed){
   const prop=zh.property.name,field=prop==='zh'?'':prop.endsWith('Zh')?prop.slice(0,-2):null,object=text.slice(zh.object.start,zh.object.end);
   if(field!==null&&text.slice(en.start,en.end).includes(object+'.'+(field?field+'En':'en')))edits.push([n.start,n.end,'ewI18n.content('+object+','+JSON.stringify(field)+',state.lang)']);
  }
 }
 for(const v of Object.values(n)){if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);}
 }walk(ast);
 edits.sort((a,b)=>b[0]-a[0]);let before=Infinity;for(const [a,b,s] of edits){if(b>before)continue;text=text.slice(0,a)+s+text.slice(b);before=a;}
 if(file==='platform.js')text=text.replace("throw new Error(d.error||'Request failed')","throw new Error(ewI18n.error(d.error||'Request failed',state.lang))");
 if(file==='journey.js')text=text.replace("state.lang==='zh'&&name?esc(name):t(en,zh)","name?esc(ewI18n.text(en,name,state.lang)):t(en,zh)");
 fs.writeFileSync(path.join(r,file),text);
}
let review=fs.readFileSync(path.join(r,'review.html'),'utf8');
review=review.replace('<option value="zh">中文</option><option value="en">English</option>','<option value="zh">简体中文</option><option value="zh-Hant">繁體中文</option><option value="en">English</option><option value="bo">བོད་ཡིག</option>');
fs.writeFileSync(path.join(r,'review.html'),review);
let reviewJS=fs.readFileSync(path.join(r,'review.js'),'utf8');
reviewJS=reviewJS.replace("let previewState={lang:'zh',mode:'night'}","const requestedLanguage=new URLSearchParams(location.search).get('lang');\nlet previewState={lang:({'zh-Hans':'zh','zh-CN':'zh','zh-TW':'zh-Hant'}[requestedLanguage]||(['zh','zh-Hant','en','bo'].includes(requestedLanguage)?requestedLanguage:'zh')),mode:'night'}");
fs.writeFileSync(path.join(r,'review.js'),reviewJS);
console.log('Content fields and reviewer language controls updated.');

