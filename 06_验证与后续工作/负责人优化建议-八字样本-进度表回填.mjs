// Prepared stage29 narrow workbook edit. Inspect is read-only; apply needs the frozen root-verified receipt.
import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const bundled=createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence=import.meta.dirname,prefix='负责人优化建议-八字样本';
const files=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const baseline=["e646886062be8c263a9648fbac8b2c88855872bb6e094b61a4d1d70ac9e5584d", "e713b77ab75e4f1a1c5c3fe766c07b3fd4be51e5ece0fb8c28e9055a8ee07ee8"];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const previews=[[0,'98项明细','A24:H26','B10B12'],[1,'优化任务表','A29:N31','原任务B10B12'],[0,'进度总览','A5:E29','汇总']];
try{
 for(let i=0;i<files.length;i++)if(sha(await fs.readFile(files[i]))!==baseline[i])throw Error('Workbook baseline changed; reconcile before authoring.');
 const books=await Promise.all(files.map(async file=>SpreadsheetFile.importXlsx(await FileBlob.load(file))));
 const mode=process.argv[2]||'inspect';
 if(mode==='inspect'){
  for(const [index,sheetName,range,suffix] of previews){
   console.log((await books[index].inspect({kind:'table',range:`'${sheetName}'!${range}`,maxChars:14000,tableMaxRows:25,tableMaxCols:14,tableMaxCellChars:1600})).ndjson);
   const blob=await books[index].render({sheetName,range,scale:1,format:'png'});
   await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填前${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));
  }
 }else if(mode==='apply'&&process.argv[3]==='--verified-by-root'&&process.argv[4]&&/^[a-f0-9]{64}$/.test(process.argv[5]||'')){
  // Execute the skill's single expected-output-count=2 marker before this command, after all gates pass.
  const receiptPath=path.resolve(process.argv[4]),bytes=await fs.readFile(receiptPath),receipt=JSON.parse(bytes);
  if(path.basename(receiptPath)!==prefix+'-实施记录.json'||sha(bytes)!==process.argv[5]||receipt.pass!==true||receipt.stage!==29||JSON.stringify([...(receipt.taskIds||[])].sort())!==JSON.stringify(['B10','B12'])||receipt.perBackendGateCount!==186)throw Error('Frozen, root-verified stage29 B10/B12 receipt required.');
  const detail=books[0].worksheets.getItem('98项明细'),overview=books[0].worksheets.getItem('进度总览'),tasks=books[1].worksheets.getItem('优化任务表');
  const rows=[['B10',24,29],['B12',26,31]];
  for(const [id,row,oldRow] of rows)if(detail.getRange('A'+row).values[0][0]!==id||detail.getRange('D'+row).values[0][0]!=='待资料'||detail.getRange('E'+row).values[0][0]!=='未计入'||tasks.getRange('A'+oldRow).values[0][0]!==id||tasks.getRange('K'+oldRow).values[0][0]!=='待资料')throw Error('Task mapping/status changed.');
  const stamp=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
  const backups=[];
  for(let i=0;i<files.length;i++){backups[i]=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);await fs.copyFile(files[i],backups[i],constants.COPYFILE_EXCL);}
  const local={B10:'原字节样本导入、冻结运行、服务端重算、完整原始运表分段、逐字段差异和追加分类建议、原生APP临时核对已本地验收；Python与本地Cloud各186项实际验证通过。',B12:'已提供合成导入模板、显式asOfUtc及边界样本回放、同实现双端回归和原生字段核对工具；老师确认数0、专业一致率未评定，不冒称专业算法已验证。'};
  const remaining={B10:'老师标准输入、流派/神煞规则与可信答案待确认；随后按具体证据完成专业差异定位与复测。现有分类建议仅proposed，服务端DOM仍not_run。',B12:'至少30个老师确认样本、规则约定和字段一致率100%目标仍须正式定稿验收；藏语母语与手机实机验收另行完成。'};
  const receiptName=path.basename(receiptPath);
  for(const [id,row,oldRow] of rows){
   const progress=local[id]+' 收据：'+receiptName+'。';detail.getRange('E'+row).values=[['已有证据']];detail.getRange(`F${row}:G${row}`).values=[[progress,remaining[id]]];detail.getRange(`A${row}:H${row}`).format.rowHeight=145;
   const original=tasks.getRange('I'+oldRow).values[0][0].split(/\n(?:现状|本轮)：/)[0];
   tasks.getRange('I'+oldRow).values=[[original+'\n本轮：'+progress+'\n剩余：'+remaining[id]+'\n证据：06_验证与后续工作/'+receiptName]];tasks.getRange(`A${oldRow}:N${oldRow}`).format.rowHeight=285;
  }
  const [year,month,day]=receipt.at_beijing.slice(0,10).split('-');overview.getRange('A3').values=[['依据 v1.0 修改需求 · 截至 '+year+' 年 '+Number(month)+' 月 '+Number(day)+' 日（北京时间）']];
  overview.getRange('D7:E7').values=[['既有四柱、流运、详情与追溯保留；本轮样本导入、冻结重算、逐字段差异、分类建议及APP临时核对已通过本地验证。','老师规则、神煞口径、至少30个确认样本及专业一致率目标仍待定稿；本地回放不等于老师确认。']];overview.getRange('A7:E7').format.rowHeight=80;
  overview.getRange('D15').values=[['本地证据含部分功能及沙箱测试，其余 28 项未计入此口径。29 个开发阶段已有本地验收记录。']];
  overview.getRange('D22:E22').values=[['本方逐域清理与回执保留；本轮样本导入、冻结运行、完整运表与逐字段差异、原生临时核对及样本正文擦除已有本地软件证据。','保留/匿名化剩余软件、正式期限及外部删除仍分别追踪；命盘专业差异定位仍待老师标准样本，不能从不一致直接断言算法错误。']];overview.getRange('A22:E22').format.rowHeight=80;
  const title=tasks.getRange('A4').values[0][0];if(!title.includes('28个本地实施阶段'))throw Error('Original stage summary changed.');tasks.getRange('A4').values=[[title.replace('28个本地实施阶段','29个本地实施阶段')]];
  books.forEach(book=>book.recalculate());
  if(overview.getRange('C15').values[0][0]!==70||overview.getRange('C7').values[0][0]!==9||overview.getRange('B29').values[0][0]!=='进行中 70 项'||overview.getRange('C29').values[0][0]!=='待资料 16 项')throw Error('Expected sample evidence counts did not recalculate; statuses must remain waiting for teacher data.');
  const outputs=[];
  for(let i=0;i<books.length;i++){
   const errors=await books[i].inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});if(errors.records.some(row=>row.kind==='match'))throw Error('Formula error scan failed.');
   const candidate=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}待校验.xlsx`),report=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填校验.json`);
   await(await SpreadsheetFile.exportXlsx(books[i])).save(candidate);
   execFileSync('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',['-B',path.join(evidence,prefix+'-进度表校验.py'),backups[i],candidate,report],{encoding:'utf8',stdio:'pipe'});
   outputs.push({output:files[i],backup:backups[i],candidate,report});
  }
  for(const [index,sheetName,range,suffix] of previews){const blob=await books[index].render({sheetName,range,scale:1,format:'png'});await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填后${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));}
  for(const output of outputs){await fs.copyFile(output.candidate,output.output);await fs.unlink(output.candidate);delete output.candidate;output.sha256=sha(await fs.readFile(output.output));}
  console.log(JSON.stringify({updated:outputs,stage:29,rowsWithEvidence:70,otherRows:28,statusCounts:{进行中:70,待资料:16,待验收:9,待实施:3}}));
 }else throw Error('Use inspect; apply requires --verified-by-root <frozen receipt> <SHA256> after final gates.');
}catch(error){console.error(error.message);process.exitCode=1;}
