
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),r4=path.join(root,'04_研发源码/app/r4');
const acorn=require(path.join(root,'04_研发源码/app/cloud/node_modules/acorn'));
const pairs=new Map(),conditions=[];
function lit(n){if(n?.type==='Literal'&&typeof n.value==='string')return n.value;if(n?.type==='TemplateLiteral')return n.quasis.map((q,i)=>q.value.cooked+(i<n.expressions.length?'{'+i+'}':'')).join('');return null;}
function add(en,zh,file){if(zh&&/[\u3400-\u9fff]/u.test(zh)&&en!==null&&!zh.includes('data:')){if(!pairs.has(zh))pairs.set(zh,{zh,en,files:[file]});else if(!pairs.get(zh).files.includes(file))pairs.get(zh).files.push(file);}}
for(const file of fs.readdirSync(r4).filter(f=>f.endsWith('.js')&&!f.startsWith('i18n'))){
 const text=fs.readFileSync(path.join(r4,file),'utf8'),ast=acorn.parse(text,{ecmaVersion:'latest',locations:true});
 function walk(n){if(!n||!n.type)return;
 if(n.type==='CallExpression'&&['t','pxText','journeyMapTitle'].includes(n.callee.name)){
 const a=n.arguments;if(n.callee.name==='pxText')add(lit(a[1]),lit(a[0]),file);else if(n.callee.name==='t')add(lit(a[0]),lit(a[1]),file);else add(lit(a[1]),lit(a[2]),file);
 }
 if(n.type==='ObjectExpression'){
 const props=Object.fromEntries(n.properties.filter(p=>p.type==='Property').map(p=>[p.key.name||p.key.value,p.value]));
 for(const k of Object.keys(props)){const enKey=k==='zh'?'en':k.endsWith('Zh')?k.slice(0,-2)+'En':null;if(enKey&&props[enKey]){const z=props[k],e=props[enKey];if(z.type==='ArrayExpression'&&e.type==='ArrayExpression')z.elements.forEach((a,i)=>add(lit(e.elements[i]),lit(a),file));else add(lit(e),lit(z),file);}}
 }
 if(n.type==='ArrayExpression'&&n.elements.length>=2){const a=n.elements.map(lit);for(let i=0;i<a.length-1;i++){if(a[i]&&a[i+1]&&/[\u3400-\u9fff]/u.test(a[i])&&!/[\u3400-\u9fff]/u.test(a[i+1])){add(a[i+1],a[i],file);i++;}else if(a[i]&&a[i+1]&&!/[\u3400-\u9fff]/u.test(a[i])&&/[\u3400-\u9fff]/u.test(a[i+1])&&/\s/.test(a[i])){add(a[i],a[i+1],file);i++;}}}
 if(n.type==='ConditionalExpression'&&/state\.lang/.test(text.slice(n.test.start,n.test.end)))conditions.push({file,line:n.loc.start.line,test:text.slice(n.test.start,n.test.end),yes:text.slice(n.consequent.start,n.consequent.end).slice(0,160),no:text.slice(n.alternate.start,n.alternate.end).slice(0,160)});
 for(const [k,v] of Object.entries(n)){if(k==='loc')continue;if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')walk(v);}
 }walk(ast);
}
const list=[...pairs.values()].map((p,i)=>({id:i,...p}));
fs.writeFileSync(path.join(__dirname,'四语文案清单.json'),JSON.stringify(list,null,2));
fs.writeFileSync(path.join(__dirname,'语言分支清单.json'),JSON.stringify(conditions,null,2));
console.log(JSON.stringify({pairs:list.length,conditions:conditions.length,byFile:Object.fromEntries(fs.readdirSync(r4).filter(f=>f.endsWith('.js')).map(f=>[f,list.filter(p=>p.files.includes(f)).length]))},null,2));

