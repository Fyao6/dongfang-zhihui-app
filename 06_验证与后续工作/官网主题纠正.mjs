// Correct only ADD-WEB values; preserve the prior misunderstanding and all other workbook content.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash,randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const OUT=import.meta.dirname,ROOT=path.dirname(OUT),runtime='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const node=path.join(runtime,'node/bin/node.exe'),python=path.join(runtime,'python/python.exe');
const names=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'];
const sha=b=>createHash('sha256').update(b).digest('hex'),rel=p=>path.relative(ROOT,p).replaceAll('\\','/');
const id=randomUUID().replaceAll('-',''),mode=process.argv[2];
if(!['baseline','prepare','apply'].includes(mode))throw Error('Use baseline / prepare <baseline> / apply <candidate>');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'codex-web-theme-books-'));
await fs.symlink(path.join(runtime,'node/node_modules'),path.join(temp,'node_modules'),'junction');
const require=createRequire(path.join(temp,'author.cjs')),{FileBlob,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const writeJSON=async(file,value)=>fs.writeFile(file,JSON.stringify(value,null,2)+'\n',{flag:'wx'});
if(mode==='baseline'){
 const data={at:new Date().toISOString(),books:[]};
 for(let i=0;i<names.length;i++){
  const file=path.join(OUT,names[i]),raw=await fs.readFile(file),backup=path.join(OUT,`官网主题纠正前-${id}-${i}.xlsx`);
  await fs.writeFile(backup,raw,{flag:'wx'});
  const book=await SpreadsheetFile.importXlsx(await FileBlob.load(file)),sheet=book.worksheets.getItem('追加需求');if(sheet.getRange('A2').values[0][0]!=='ADD-WEB')throw Error('ADD-WEB missing');
  const preview=path.join(OUT,`官网主题纠正-修改前-${id}-${i}.png`);await fs.writeFile(preview,new Uint8Array(await(await book.render({sheetName:'追加需求',range:'A1:F4',scale:1,format:'png'})).arrayBuffer()),{flag:'wx'});
  data.books.push({file:rel(file),sha256:sha(raw),backup:rel(backup),preview:rel(preview)});
 }
 const file=path.join(OUT,`官网主题纠正-基线-${id}.json`);await writeJSON(file,data);console.log(JSON.stringify({manifest:rel(file),books:data.books}));
}else if(mode==='prepare'){
 const baselinePath=path.resolve(process.argv[3]),baseline=JSON.parse(await fs.readFile(baselinePath,'utf8'));
 const expected={B2:'官网与APP视觉主题一致性',C2:'本地已验证，主题待评价/调整',D2:'既有展示官网、真实路由、原生菜单及APP与隐私入口已双端各60+6本地验证。旧证据不代表用户已认可新的主题一致性。',E2:'最新要求：官网视觉主题与APP约80%一致，包括配色、字体、图形语言及整体气质。待视觉评价并按反馈调整。本轮只记录与交付，不新增业务或80%功能覆盖要求。'};
 const expectedPath=path.join(OUT,`官网主题纠正-预期值-${id}.json`);await writeJSON(expectedPath,expected);
 const authoritative=JSON.parse(await fs.readFile(path.join(OUT,'官网需求表-基线-d3f2445de8f94ecf95d14857ad69f424.json'),'utf8'));
 const books=[];for(let i=0;i<baseline.books.length;i++){const item=baseline.books[i];if(sha(await fs.readFile(path.join(ROOT,item.file)))!==item.sha256||sha(await fs.readFile(path.join(ROOT,item.backup)))!==item.sha256)throw Error('Current baseline changed');if(sha(await fs.readFile(path.join(ROOT,authoritative.books[i].backup)))!==authoritative.books[i].sha256)throw Error('Growth-complete original baseline changed');books.push(await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(ROOT,item.file))));}
 execFileSync(node,['C:/Users/Administrator/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.1112.11011/skills/spreadsheets/container_tools/mark_artifact_operation_started.mjs','--operation-kind','edit','--expected-output-count','2','--output-format','xlsx'],{stdio:'pipe'});
 const data={at:new Date().toISOString(),scope:'追加需求!B2:E2 values only; visual theme clarification; no business implementation',baseline:rel(baselinePath),baselineSha256:sha(await fs.readFile(baselinePath)),applied:false,books:[]};
 for(let i=0;i<books.length;i++){
  const book=books[i];book.worksheets.getItem('追加需求').getRange('B2:E2').values=[[expected.B2,expected.C2,expected.D2,expected.E2]];book.recalculate();
  const candidate=path.join(OUT,`官网主题纠正-候选-${id}-${i}.xlsx`),preview=path.join(OUT,`官网主题纠正-更新预览-${id}-${i}.png`),validations=[];
  await fs.writeFile(preview,new Uint8Array(await(await book.render({sheetName:'追加需求',range:'A1:F4',scale:1,format:'png'})).arrayBuffer()),{flag:'wx'});await(await SpreadsheetFile.exportXlsx(book)).save(candidate);
  for(const [label,reference] of [['误解前成长基准',authoritative.books[i].backup],['本轮纠正前',baseline.books[i].backup]]){
   const report=path.join(OUT,`官网主题纠正-校验-${label}-${id}-${i}.json`);execFileSync(python,['-B','-X','utf8',path.join(OUT,'官网需求表校验.py'),path.join(ROOT,reference),candidate,expectedPath,report],{stdio:'pipe'});validations.push({reference,report:rel(report),sha256:sha(await fs.readFile(report))});
  }
  data.books.push({...baseline.books[i],candidate:rel(candidate),candidateSha256:sha(await fs.readFile(candidate)),preview:rel(preview),validations});
 }
 const file=path.join(OUT,`官网主题纠正-候选记录-${id}.json`);await writeJSON(file,data);console.log(JSON.stringify({manifest:rel(file),books:data.books}));
}else{
 const manifestPath=path.resolve(process.argv[3]),data=JSON.parse(await fs.readFile(manifestPath,'utf8'));if(data.applied!==false)throw Error('Expected unapplied');
 for(const item of data.books){if(sha(await fs.readFile(path.join(ROOT,item.file)))!==item.sha256||sha(await fs.readFile(path.join(ROOT,item.candidate)))!==item.candidateSha256)throw Error('Validated candidate changed');for(const check of item.validations){const raw=await fs.readFile(path.join(ROOT,check.report));if(sha(raw)!==check.sha256||JSON.parse(raw).pass!==true)throw Error('Validation failed');}}
 for(const item of data.books)await fs.writeFile(path.join(ROOT,item.file),await fs.readFile(path.join(ROOT,item.candidate)));
 const result={at:new Date().toISOString(),applied:true,scope:data.scope,sourceManifest:rel(manifestPath),sourceManifestSha256:sha(await fs.readFile(manifestPath)),books:data.books.map(x=>({file:x.file,sha256:x.candidateSha256,beforeSha256:x.sha256,backup:x.backup,visualPreview:x.preview,validations:x.validations}))};
 const file=path.join(OUT,`官网主题纠正-已应用-${id}.json`);await writeJSON(file,result);console.log(JSON.stringify({manifest:rel(file),books:result.books}));
}
