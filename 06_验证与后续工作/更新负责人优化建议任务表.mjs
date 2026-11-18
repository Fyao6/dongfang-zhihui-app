import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
const dir=path.dirname(fileURLToPath(import.meta.url));
const runtime='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const req=createRequire(path.join(runtime,'@oai/artifact-tool/package.json'));
const {Workbook,SpreadsheetFile,FileBlob}=await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
const target=path.join(dir,'东方智慧APP优化任务表_依据v1.0_20261112.xlsx');
const tasks=JSON.parse(await fs.readFile(path.join(dir,'负责人优化建议-任务拆解.json'),'utf8'));
const audit=JSON.parse(await fs.readFile(path.join(dir,'负责人优化建议-98项最终覆盖审计.json'),'utf8'));
const frozenStages=audit.verifiedLocalStages;
if(!Number.isInteger(frozenStages))throw Error('Verified stage count is missing from the current audit');
const baseline=process.argv.find(arg=>arg.startsWith('--baseline='))?.slice('--baseline='.length);
const w=await SpreadsheetFile.importXlsx(await FileBlob.load(baseline||target));
const updatedIds=new Set(audit.updatedTaskIds);
const previewPrefix=process.argv.find(arg=>arg.startsWith('--preview-prefix='))?.slice('--preview-prefix='.length)||'负责人优化建议-五阶段回填';
const previewTask=process.argv.find(arg=>arg.startsWith('--preview-task='))?.slice('--preview-task='.length);
const previewRow=previewTask?tasks.findIndex(task=>task.id===previewTask)+11:40;
if(previewTask&&previewRow===10)throw Error('Unknown preview task '+previewTask);
const s=w.worksheets.getItem('优化任务表');
if(process.argv.includes('--before')){
 const preview=await w.render({sheetName:'优化任务表',range:'F38:K42',scale:1,format:'png'});
 await fs.writeFile(path.join(dir,'负责人优化建议-任务表更新前.png'),new Uint8Array(await preview.arrayBuffer()));
 console.log((await w.inspect({kind:'sheet',include:'id,name',maxChars:1200})).ndjson);
 process.exit(0);
}

for(let i=0;i<tasks.length;i++){
 const row=11+i,t=tasks[i];
 if(s.getRange(`A${row}`).values[0][0]!==t.id)throw Error('Task ID mismatch '+t.id);
 if(s.getRange(`K${row}`).values[0][0]!==t.status)throw Error('Task status mismatch '+t.id);
 const cell=s.getRange(`I${row}`);
 if(updatedIds.has(t.id)&&t.implementation_note){
  const value=t.dependencies+'\n本轮：'+t.implementation_note;
  if(cell.values[0][0]===value)continue;
  cell.values=[[value]];
  cell.format.wrapText=true;
  const rowFormat=s.getRange(`A${row}:N${row}`).format;
  rowFormat.rowHeightPx=Math.max(150,Math.ceil(value.length/23)*18+36,rowFormat.rowHeightPx||0);
 }
}
s.getRange('A4').values=[['原文已拆为'+tasks.length+'项并逐项保留出处；'+frozenStages+'个本地实施阶段已通过测试，'+tasks.filter(x=>x.status==='待验收').length+'项待验收。各项已实现范围、剩余软件和外部资料见I列；正式收费、真实AI及生产部署尚未完成。']];
w.recalculate();
console.log((await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:20},maxChars:1000})).ndjson);
console.log((await w.inspect({kind:'table',range:'优化任务表!I38:K40',tableMaxRows:2,tableMaxCols:14,maxChars:1500})).ndjson);
const r=await w.render({sheetName:'优化任务表',range:`F${previewRow-2}:K${previewRow+2}`,scale:1,format:'png'});
await fs.writeFile(path.join(dir,previewPrefix+'-任务进度预览.png'),new Uint8Array(await r.arrayBuffer()));
const header=await w.render({sheetName:'优化任务表',range:'A1:N10',scale:0.8,format:'png'});
await fs.writeFile(path.join(dir,previewPrefix+'-任务表标题预览.png'),new Uint8Array(await header.arrayBuffer()));
const shopRow=11+tasks.findIndex(t=>t.id==='SH03');
const shop=await w.render({sheetName:'优化任务表',range:`F${shopRow}:K${shopRow+3}`,scale:1,format:'png'});
await fs.writeFile(path.join(dir,previewPrefix+'-任务表售后预览.png'),new Uint8Array(await shop.arrayBuffer()));
await(await SpreadsheetFile.exportXlsx(w)).save(target);
console.log(JSON.stringify({edited:target,tasks:tasks.length,awaitingReview:tasks.filter(x=>x.status==='待验收').length}));
