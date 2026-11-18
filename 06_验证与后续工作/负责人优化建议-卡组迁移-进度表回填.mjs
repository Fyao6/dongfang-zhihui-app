// Prepared stage30 narrow workbook edit. Inspect is read-only; apply needs the frozen root-verified receipt.
import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const bundled=createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence=import.meta.dirname,prefix='负责人优化建议-卡组迁移';
const files=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const baseline=["75e0392aad97afb715cc116a09c09529b97c0df2ab3ace17ae2a0762ce9f26df", "5088b8d4cca380979a07d2d57d628f4633101e27dd8d3eaf4d21eb6957d00f1c"];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const previews=[[0,'98项明细','A93:H98','DR03DR08'],[1,'优化任务表','A98:N103','原任务DR03DR08'],[0,'进度总览','A5:E29','汇总']];
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
  if(path.basename(receiptPath)!==prefix+'-实施记录.json'||sha(bytes)!==process.argv[5]||receipt.pass!==true||receipt.stage!==30||JSON.stringify([...(receipt.taskIds||[])].sort())!==JSON.stringify(['DR03','DR08'])||receipt.perBackendGateCount!==195)throw Error('Frozen, root-verified stage30 DR03/DR08 receipt required.');
  const detail=books[0].worksheets.getItem('98项明细'),overview=books[0].worksheets.getItem('进度总览'),tasks=books[1].worksheets.getItem('优化任务表');
  const rows=[['DR03',93,98],['DR08',98,103]];
  for(const [id,row,oldRow] of rows)if(detail.getRange('A'+row).values[0][0]!==id||detail.getRange('D'+row).values[0][0]!== (id==='DR03'?'待资料':'进行中')||detail.getRange('E'+row).values[0][0]!== (id==='DR03'?'未计入':'已有证据')||tasks.getRange('A'+oldRow).values[0][0]!==id||tasks.getRange('K'+oldRow).values[0][0]!== (id==='DR03'?'待资料':'进行中'))throw Error('Task mapping/status changed.');
  const stamp=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
  const backups=[];
  for(let i=0;i<files.length;i++){backups[i]=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);await fs.copyFile(files[i],backups[i],constants.COPYFILE_EXCL);}
  const local={DR03:'P528方向原段及逐字段来源已原样保存；文件导入、全部诊断、三语逐字段差异和待审核草稿已有本地软件证据，不生成正式卡文或翻译。',DR08:'严格原字节导入、全部问题与差异分页/导出、幂等草稿回执、数据库不可变版本、指针切换/回滚、完整历史分页及本人旧例续批/逆向撤销已本地验收；双端各195项通过。'};
  const remaining={DR03:'最终卡种与张数、全套简繁英审定文案、卡面/统一卡背、作者版权授权与真实审核人仍待资料；原文待审不代表正式36张已齐。',DR08:'正式全套文案与卡面、规则及授权审核、母语审校、手机实机和生产发布另验；本地导入/回滚回执不等于正式版权或内容通过。'};
  const receiptName=path.basename(receiptPath);
  for(const [id,row,oldRow] of rows){
   const progress=local[id]+' 收据：'+receiptName+'。';detail.getRange('E'+row).values=[['已有证据']];detail.getRange(`F${row}:G${row}`).values=[[progress,remaining[id]]];detail.getRange(`A${row}:H${row}`).format.rowHeight=145;
   const original=tasks.getRange('I'+oldRow).values[0][0].split(/\n(?:现状|本轮)：/)[0];
   tasks.getRange('I'+oldRow).values=[[original+'\n本轮：'+progress+'\n剩余：'+remaining[id]+'\n证据：06_验证与后续工作/'+receiptName]];tasks.getRange(`A${oldRow}:N${oldRow}`).format.rowHeight=285;
  }
  const [year,month,day]=receipt.at_beijing.slice(0,10).split('-');overview.getRange('A3').values=[['依据 v1.0 修改需求 · 截至 '+year+' 年 '+Number(month)+' 月 '+Number(day)+' 日（北京时间）']];
  overview.getRange('D13:E13').values=[['既有抽取防重与审核保留；本轮文件预览、全量诊断/逐字段差异、幂等独立草稿、不可变版本/指针回滚及旧例分批迁移撤销已有本地证据。','全套简繁英卡文/卡面/作者授权与最终卡种张数待确认；生产门禁保留，不默认36张。']];overview.getRange('A13:E13').format.rowHeight=100;
  overview.getRange('D15').values=[['本地证据含部分功能及沙箱测试，其余27项未计入此口径。30个开发阶段已有本地验收记录。']];
  overview.getRange('D23:E23').values=[['卡组导入及迁移回滚软件已本地验收，P528原文与来源模板已交付；下一步登录态压测、故障恢复、迁移预检及回滚演练。','正式卡文/图片/授权及生产验收仍待资料；本地可靠性演练范围与正式生产目标分别记录。']];overview.getRange('A23:E23').format.rowHeight=90;
  const title=tasks.getRange('A4').values[0][0];if(!title.includes('29个本地实施阶段'))throw Error('Original stage summary changed.');tasks.getRange('A4').values=[[title.replace('29个本地实施阶段','30个本地实施阶段')]];
  books.forEach(book=>book.recalculate());
  if(overview.getRange('C15').values[0][0]!==71||overview.getRange('C13').values[0][0]!==7||overview.getRange('B29').values[0][0]!=='进行中 70 项'||overview.getRange('C29').values[0][0]!=='待资料 16 项')throw Error('Expected partial card evidence counts did not recalculate; original statuses must remain.');
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
  console.log(JSON.stringify({updated:outputs,stage:30,rowsWithEvidence:71,otherRows:27,statusCounts:{进行中:70,待资料:16,待验收:9,待实施:3}}));
 }else throw Error('Use inspect; apply requires --verified-by-root <frozen receipt> <SHA256> after final gates.');
}catch(error){console.error(error.message);process.exitCode=1;}
