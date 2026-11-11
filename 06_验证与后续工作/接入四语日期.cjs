
const fs=require('fs'),path=require('path');const r=path.resolve(__dirname,'../04_研发源码/app/r4'),acorn=require(path.join(r,'../cloud/node_modules/acorn'));
for(const file of fs.readdirSync(r).filter(f=>f.endsWith('.js')&&!f.startsWith('i18n'))){
 let text=fs.readFileSync(path.join(r,file),'utf8'),ast=acorn.parse(text,{ecmaVersion:'latest'}),edits=[];
 function src(n){return text.slice(n.start,n.end);}
 function walk(n){if(!n?.type)return;
 if(n.type==='CallExpression'&&n.callee.type==='MemberExpression'){
  const obj=n.callee.object,prop=n.callee.property.name;
  if(prop==='format'&&obj.type==='NewExpression'&&src(obj.callee)==='Intl.DateTimeFormat'&&src(obj.arguments[0])==='ewIntlLocale()')edits.push([n.start,n.end,'ewFormatDate('+src(n.arguments[0])+','+src(obj.arguments[1])+')']);
  if(['toLocaleDateString','toLocaleTimeString','toLocaleString'].includes(prop)&&n.arguments[0]&&src(n.arguments[0])==='ewIntlLocale()')edits.push([n.start,n.end,'ewFormatDate('+src(obj)+','+(n.arguments[1]?src(n.arguments[1]):'{}')+')']);
 }
 for(const v of Object.values(n)){if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);}
 }walk(ast);edits.sort((a,b)=>b[0]-a[0]);let before=Infinity;for(const[a,b,s]of edits){if(b>before)continue;text=text.slice(0,a)+s+text.slice(b);before=a;}fs.writeFileSync(path.join(r,file),text);
}

