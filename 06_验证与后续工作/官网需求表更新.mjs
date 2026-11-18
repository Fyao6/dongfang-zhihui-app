import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash,randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const OUT=import.meta.dirname,ROOT=path.dirname(OUT),runtime='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const python=path.join(runtime,'python/python.exe'),node=path.join(runtime,'node/bin/node.exe');
const names=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'];
const sha=b=>createHash('sha256').update(b).digest('hex'),rel=p=>path.relative(ROOT,p).replaceAll('\\','/');
const mode=process.argv[2];
if(!['baseline','prepare','apply'].includes(mode))throw Error('Use baseline, prepare <baseline>, apply <candidate manifest>');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'codex-web-requirement-books-'));
await fs.symlink(path.join(runtime,'node/node_modules'),path.join(temp,'node_modules'),'junction');
const require=createRequire(path.join(temp,'author.cjs'));
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const id=randomUUID().replaceAll('-','');
if(mode==='baseline'){
 const result={id,at:new Date().toISOString(),mode,books:[]};
 for(let i=0;i<names.length;i++){
  const file=path.join(OUT,names[i]),bytes=await fs.readFile(file),backup=path.join(OUT,`官网需求更新前-${id}-${i}.xlsx`);
  await fs.writeFile(backup,bytes,{flag:'wx'});
  const book=await SpreadsheetFile.importXlsx(await FileBlob.load(file)),sheet=book.worksheets.getItem('追加需求');
  if(sheet.getRange('A2').values[0][0]!=='ADD-WEB')throw Error('ADD-WEB identity missing');
  const preview=path.join(OUT,`官网需求表-修改前-${id}-${i}.png`);
  await fs.writeFile(preview,new Uint8Array(await(await book.render({sheetName:'追加需求',range:'A1:F4',scale:1,format:'png'})).arrayBuffer()),{flag:'wx'});
  result.books.push({file:rel(file),sha256:sha(bytes),backup:rel(backup),preview:rel(preview),values:sheet.getRange('A1:F4').values});
 }
 const file=path.join(OUT,`官网需求表-基线-${id}.json`);await fs.writeFile(file,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({manifest:rel(file),books:result.books.map(x=>({file:x.file,preview:x.preview}))}));
}else if(mode==='prepare'){
 const baselinePath=path.resolve(process.argv[3]),baseline=JSON.parse(await fs.readFile(baselinePath,'utf8'));
 const expected={B2:'官网与APP主要功能一致性',C2:'部分已验证，新增待实施',D2:'既有展示官网、真实路由、原生菜单、APP与隐私入口已双端各60+6本地验证。旧证据仅覆盖展示与入口，不覆盖新增的80%功能要求。',E2:'新增要求：官网主要功能与流程约80%与APP一致，当前展示页未达到，待实施并按功能清单逐项核验。80%不是视觉相似度或当前完成率。公网发布、视觉及终端另验。'};
 const expectedPath=path.join(OUT,`官网需求表-预期值-${id}.json`);await fs.writeFile(expectedPath,JSON.stringify(expected,null,2)+'\n',{flag:'wx'});
 const books=[];for(const item of baseline.books){const file=path.join(ROOT,item.file);if(sha(await fs.readFile(file))!==item.sha256||sha(await fs.readFile(path.join(ROOT,item.backup)))!==item.sha256)throw Error('Workbook baseline changed');books.push(await SpreadsheetFile.importXlsx(await FileBlob.load(file)));}
 // Exactly one successful marker precedes the first edit of these two outputs.
 execFileSync(node,['C:/Users/Administrator/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.1112.11011/skills/spreadsheets/container_tools/mark_artifact_operation_started.mjs','--operation-kind','edit','--expected-output-count','2','--output-format','xlsx'],{stdio:'pipe'});
 const result={at:new Date().toISOString(),baseline:rel(baselinePath),baselineSha256:sha(await fs.readFile(baselinePath)),books:[],applied:false,scope:'追加需求!B2:E2 values only; ADD-WEB row; no business development'};
 for(let i=0;i<books.length;i++){
  const book=books[i],sheet=book.worksheets.getItem('追加需求');if(sheet.getRange('A2').values[0][0]!=='ADD-WEB')throw Error('Row identity');
  sheet.getRange('B2:E2').values=[[expected.B2,expected.C2,expected.D2,expected.E2]];book.recalculate();
  const candidate=path.join(OUT,`官网需求表-候选-${id}-${i}.xlsx`),preview=path.join(OUT,`官网需求表-更新预览-${id}-${i}.png`),validation=path.join(OUT,`官网需求表-校验-${id}-${i}.json`);
  await fs.writeFile(preview,new Uint8Array(await(await book.render({sheetName:'追加需求',range:'A1:F4',scale:1,format:'png'})).arrayBuffer()),{flag:'wx'});
  await(await SpreadsheetFile.exportXlsx(book)).save(candidate);
  execFileSync(python,['-B','-X','utf8',path.join(OUT,'官网需求表校验.py'),path.join(ROOT,baseline.books[i].backup),candidate,expectedPath,validation],{stdio:'pipe'});
  result.books.push({...baseline.books[i],candidate:rel(candidate),candidateSha256:sha(await fs.readFile(candidate)),preview:rel(preview),validation:rel(validation),validationSha256:sha(await fs.readFile(validation))});
 }
 const file=path.join(OUT,`官网需求表-候选记录-${id}.json`);await fs.writeFile(file,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({manifest:rel(file),books:result.books.map(x=>({file:x.file,candidate:x.candidate,preview:x.preview,validation:x.validation}))}));
}else{
 const manifestPath=path.resolve(process.argv[3]),data=JSON.parse(await fs.readFile(manifestPath,'utf8'));if(data.applied!==false)throw Error('Expected unapplied manifest');
 for(const item of data.books){if(sha(await fs.readFile(path.join(ROOT,item.file)))!==item.sha256||sha(await fs.readFile(path.join(ROOT,item.candidate)))!==item.candidateSha256||sha(await fs.readFile(path.join(ROOT,item.validation)))!==item.validationSha256||JSON.parse(await fs.readFile(path.join(ROOT,item.validation),'utf8')).pass!==true)throw Error('Exact validated inputs required');}
 for(const item of data.books)await fs.writeFile(path.join(ROOT,item.file),await fs.readFile(path.join(ROOT,item.candidate)));
 const result={at:new Date().toISOString(),applied:true,sourceManifest:rel(manifestPath),sourceManifestSha256:sha(await fs.readFile(manifestPath)),scope:data.scope,books:data.books.map(x=>({file:x.file,sha256:x.candidateSha256,beforeSha256:x.sha256,backup:x.backup,validation:x.validation,visualPreview:x.preview}))};
 const file=path.join(OUT,`官网需求表-已应用-${id}.json`);await fs.writeFile(file,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({manifest:rel(file),books:result.books}));
}
