'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const previous=require('./负责人优化建议-卡组迁移测试工具.cjs');
const gate=require('./负责人优化建议-本地可靠性修复基线.cjs');
const ROOT=path.resolve(__dirname,'..'),PREFIX='负责人优化建议-本地可靠性性能复验';
const qaFiles=['测试工具.cjs','验收启动.cjs','入口预检.cjs','入口清单.json','安全专项.cjs','依赖盘点.py'];
const inventoryControlMetadata=['负责人优化建议-卡组迁移依赖盘点.py','负责人优化建议-八字样本依赖盘点.py','负责人优化建议-支付路由依赖盘点.py','负责人优化建议-任务告警依赖盘点.py','负责人优化建议-隐私逐域验收冻结.py'];
const fixedInputs=[gate.AUTH,gate.PROOF,gate.BASELINE,'06_验证与后续工作/负责人优化建议-卡组迁移-实施记录.json','06_验证与后续工作/负责人优化建议-本地可靠性修复基线.cjs',...inventoryControlMetadata.map(n=>'06_验证与后续工作/'+n)];
fixedInputs.push('06_验证与后续工作/'+PREFIX+'原生连接组件.py');
function sourceFiles(){
 const declared=[...qaFiles.map(n=>'06_验证与后续工作/'+PREFIX+n),...fixedInputs];
 const paths=new Set([...previous.sourceFiles(),...declared,...fixedInputs]);
 const receipt=JSON.parse(fs.readFileSync(path.join(ROOT,'06_验证与后续工作/负责人优化建议-卡组迁移-实施记录.json'),'utf8'));
 for(const v of Object.values(receipt.verification))paths.add(v.path);
 const authorization=JSON.parse(fs.readFileSync(path.join(ROOT,gate.AUTH),'utf8'));
 for(const value of Object.values(authorization.productChanges))paths.add(value.originalBytes.path);
 // Explicit Python imports/worker FS bytes remain inherited; new backend .py files
 // are also declared directly, independently of a regexp over arbitrary JS strings.
 for(const name of fs.readdirSync(path.join(ROOT,'04_研发源码/app/r4/backend')))if(name.endsWith('.py'))paths.add('04_研发源码/app/r4/backend/'+name);
 const ts=require(path.join(ROOT,'04_研发源码/app/cloud/node_modules/typescript/lib/typescript.js'));
 const queue=[...paths].filter(n=>/\.(?:[cm]?js|[cm]?ts)$/.test(n)),seen=new Set();
 const literal=n=>n&&(ts.isStringLiteral(n)||ts.isNoSubstitutionTemplateLiteral(n));
 while(queue.length){const name=queue.pop();if(seen.has(name))continue;seen.add(name);const file=gate.local(name),tree=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true,/\.[cm]?ts$/.test(name)?ts.ScriptKind.TS:ts.ScriptKind.JS),imports=[];
  const walk=n=>{if((ts.isImportDeclaration(n)||ts.isExportDeclaration(n))&&literal(n.moduleSpecifier))imports.push(n.moduleSpecifier.text);if(ts.isCallExpression(n)&&n.arguments.length===1&&literal(n.arguments[0])&&((ts.isIdentifier(n.expression)&&n.expression.text==='require')||n.expression.kind===ts.SyntaxKind.ImportKeyword))imports.push(n.arguments[0].text);ts.forEachChild(n,walk);};walk(tree);
  for(const spec of imports.filter(n=>n.startsWith('.'))){const base=path.resolve(path.dirname(file),spec.split('?')[0]);const candidate=[base,base.replace(/\.mjs$/,'.mts'),base.replace(/\.js$/,'.ts'),...['.cjs','.js','.mjs','.ts','.mts','.json','.html','.sql'].map(x=>base+x)].find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());assert(candidate,'Missing actual dependency '+name+' -> '+spec);const relative=path.relative(ROOT,candidate).replaceAll('\\','/');assert(!relative.startsWith('../'));if(!paths.has(relative)){paths.add(relative);if(/\.(?:[cm]?js|[cm]?ts)$/.test(relative))queue.push(relative);}}
 }
 return [...paths].sort();
}
const identity=()=>Object.fromEntries(sourceFiles().map(n=>[n,gate.sha(fs.readFileSync(gate.local(n)))]));
function verifySnapshot(file,expected){
 const relative=path.relative(ROOT,path.resolve(file)).replaceAll('\\','/'),bytes=fs.readFileSync(gate.local(relative));
 assert(path.dirname(path.resolve(file))===__dirname&&path.basename(file).startsWith(PREFIX+'-'));
 assert.equal(gate.sha(bytes),expected);const snapshot=JSON.parse(bytes);assert.equal(snapshot.pass,true);
 assert.deepEqual(snapshot.sourceAndBuildHashes,identity());assert.equal(snapshot.inputCount,Object.keys(snapshot.sourceAndBuildHashes).length);
 assert.equal(snapshot.canonicalSHA256,gate.sha(JSON.stringify(snapshot.sourceAndBuildHashes)));
 assert(Number.isFinite(Date.parse(snapshot.at))&&Date.parse(snapshot.at)<=Date.now());
 return {path:relative,sha256:expected,canonicalSHA256:snapshot.canonicalSHA256,inputCount:snapshot.inputCount,at:snapshot.at};
}
module.exports={ROOT,PREFIX,qaFiles,fixedInputs,sourceFiles,identity,verifySnapshot,buildPreparationInputs:previous.buildPreparationInputs,sha:gate.sha};
