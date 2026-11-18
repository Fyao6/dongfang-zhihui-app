import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
const bundled=createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence=import.meta.dirname,prefix='负责人优化建议-本地可靠性';
const files=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(n=>path.join(evidence,n));
const baseline=['b6af34bae2e695bfe77f64d5f3404fcac62195258748ba51256854e524496cc4','75f383b023ebb2605e43323a5cc0824d983ab57a4ac1e70b7a43de05ba03f58c'];
const sha=b=>createHash('sha256').update(b).digest('hex');
const previews=[[0,'98项明细','A64:H66','SVT'],[0,'98项明细','A102:H102','X03'],[1,'优化任务表','A69:N71','原任务SVT'],[1,'优化任务表','A107:N107','原任务X03'],[0,'进度总览','A5:E29','汇总']];
const rows=[['SVT01',64,69],['SVT03',66,71],['X03',102,107]];
try{
 for(let i=0;i<files.length;i++)if(sha(await fs.readFile(files[i]))!==baseline[i])throw Error('Stage30 workbook baseline changed.');
 const books=await Promise.all(files.map(async f=>SpreadsheetFile.importXlsx(await FileBlob.load(f))));
 const mode=process.argv[2]||'inspect';
 if(mode==='inspect'){
  for(const [i,sheetName,range,label] of previews){
   console.log((await books[i].inspect({kind:'table',range:`'${sheetName}'!${range}`,maxChars:12000,tableMaxRows:25,tableMaxCols:14,tableMaxCellChars:1500})).ndjson);
   const f=path.join(evidence,`${prefix}-进度表-回填前${label}.png`);
   try{await fs.access(f);throw Error('Preserve existing before preview.');}catch(e){if(e.code!=='ENOENT')throw e;}
   await fs.writeFile(f,new Uint8Array(await(await books[i].render({sheetName,range,scale:1,format:'png'})).arrayBuffer()),{flag:'wx'});
  }
 }else if(mode==='apply'&&process.argv[3]==='--verified-by-root'&&process.argv[4]&&/^[a-f0-9]{64}$/.test(process.argv[5]||'')){
  const receiptFile=path.resolve(process.argv[4]),raw=await fs.readFile(receiptFile),receipt=JSON.parse(raw);
  if(path.basename(receiptFile)!==prefix+'-实施记录.json'||sha(raw)!==process.argv[5]||receipt.pass!==true||receipt.stage!==31||JSON.stringify(receipt.taskIds)!==JSON.stringify(rows.map(r=>r[0]))||receipt.productSourceBuildUnchanged!==true)throw Error('Root-verified Stage31 receipt required.');
  for(const [id]of rows)if(typeof receipt.taskProgress?.[id]!=='string'||typeof receipt.taskRemaining?.[id]!=='string')throw Error('Verified scope text missing.');
  const detail=books[0].worksheets.getItem('98项明细'),overview=books[0].worksheets.getItem('进度总览'),tasks=books[1].worksheets.getItem('优化任务表');
  for(const [id,row,old]of rows)if(detail.getRange('A'+row).values[0][0]!==id||detail.getRange('D'+row).values[0][0]!=='进行中'||detail.getRange('E'+row).values[0][0]!== (id==='X03'?'未计入':'已有证据')||tasks.getRange('A'+old).values[0][0]!==id||tasks.getRange('K'+old).values[0][0]!=='进行中')throw Error('Requirement row baseline changed.');
  const stamp=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
  const backups=[];
  for(let i=0;i<files.length;i++){backups[i]=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);await fs.copyFile(files[i],backups[i],constants.COPYFILE_EXCL);}
  for(const [id,row,old]of rows){
   const note=receipt.taskProgress[id]+' 收据：'+path.basename(receiptFile)+'。';
   detail.getRange('E'+row).values=[['已有证据']];detail.getRange(`F${row}:G${row}`).values=[[note,receipt.taskRemaining[id]]];detail.getRange(`A${row}:H${row}`).format.rowHeight=160;
   const original=tasks.getRange('I'+old).values[0][0].split(/\n(?:现状|本轮)：/)[0];
   tasks.getRange('I'+old).values=[[original+'\n本轮：'+note+'\n剩余：'+receipt.taskRemaining[id]+'\n证据：06_验证与后续工作/'+path.basename(receiptFile)]];tasks.getRange(`A${old}:N${old}`).format.rowHeight=310;
  }
  const [y,m,d]=receipt.at_beijing.slice(0,10).split('-');overview.getRange('A3').values=[['依据 v1.0 修改需求 · 截至 '+y+' 年 '+Number(m)+' 月 '+Number(d)+' 日（北京时间）']];
  overview.getRange('D11:E11').values=[[receipt.overview.server,receipt.overview.serverRemaining]];overview.getRange('A11:E11').format.rowHeight=125;
  overview.getRange('D14:E14').values=[[receipt.overview.delivery,receipt.overview.deliveryRemaining]];overview.getRange('A14:E14').format.rowHeight=100;
  overview.getRange('D15').values=[['本地证据含部分功能及沙箱测试，其余26项未计入此口径。31个开发阶段已有本地验收记录。']];
  overview.getRange('A23').values=[['本地可靠性与交付准备']];overview.getRange('D23:E23').values=[[receipt.overview.next,receipt.overview.nextRemaining]];overview.getRange('A23:E23').format.rowHeight=120;
  const title=tasks.getRange('A4').values[0][0];if(!title.includes('30个本地实施阶段'))throw Error('Stage30 summary changed.');tasks.getRange('A4').values=[[title.replace('30个本地实施阶段','31个本地实施阶段')]];
  books.forEach(book=>book.recalculate());
  if(overview.getRange('C15').values[0][0]!==72||overview.getRange('C14').values[0][0]!==4||overview.getRange('B29').values[0][0]!=='进行中 70 项'||overview.getRange('C29').values[0][0]!=='待资料 16 项')throw Error('Recalculated scoped count mismatch.');
  const outputs=[];
  for(let i=0;i<books.length;i++){
   const errors=await books[i].inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});if(errors.records.some(r=>r.kind==='match'))throw Error('Formula error.');
   const candidate=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}待校验.xlsx`),report=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填校验.json`);
   await(await SpreadsheetFile.exportXlsx(books[i])).save(candidate);
   execFileSync('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',['-B',path.join(evidence,prefix+'-进度表校验.py'),backups[i],candidate,report],{encoding:'utf8',stdio:'pipe'});
   outputs.push({output:files[i],backup:backups[i],candidate,report});
  }
  for(const [i,sheetName,range,label]of previews)await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填后${label}.png`),new Uint8Array(await(await books[i].render({sheetName,range,scale:1,format:'png'})).arrayBuffer()),{flag:'wx'});
  for(const item of outputs){await fs.copyFile(item.candidate,item.output);await fs.unlink(item.candidate);delete item.candidate;item.sha256=sha(await fs.readFile(item.output));}
  console.log(JSON.stringify({updated:outputs,stage:31,rowsWithEvidence:72,otherRows:26,statusCounts:{进行中:70,待资料:16,待验收:9,待实施:3}}));
 }else throw Error('Use inspect; apply requires exact root-verified frozen receipt and SHA.');
}catch(e){console.error(e.message);process.exitCode=1;}
