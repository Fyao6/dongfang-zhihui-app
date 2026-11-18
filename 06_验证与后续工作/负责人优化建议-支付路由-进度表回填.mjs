// Prepared stage28 narrow workbook edit. Inspect is read-only; apply needs the frozen root-verified receipt.
import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const bundled=createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence=import.meta.dirname,prefix='负责人优化建议-支付路由';
const files=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const baseline=["378cf3ea91e48971b7d67f31ededa74e493b9dc4145e695144045125e01f1f63", "29a8c4167a5ce59514690ab88b662e6f9c45a18f3f3e7eed462cd3a92a8c08b8"];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const previews=[[0,'98项明细','A74:H74','PAY05'],[1,'优化任务表','A79:N79','原任务PAY05'],[0,'进度总览','A5:E29','汇总']];
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
  if(path.basename(receiptPath)!==prefix+'-实施记录.json'||sha(bytes)!==process.argv[5]||receipt.pass!==true||receipt.stage!==28||JSON.stringify([...(receipt.taskIds||[])].sort())!==JSON.stringify(['PAY05'])||receipt.perBackendGateCount!==263)throw Error('Frozen, root-verified stage28 PAY05 receipt required.');
  const detail=books[0].worksheets.getItem('98项明细'),overview=books[0].worksheets.getItem('进度总览'),tasks=books[1].worksheets.getItem('优化任务表');
  const rows=[['PAY05',74,79]];
  for(const [id,row,oldRow] of rows)if(detail.getRange('A'+row).values[0][0]!==id||detail.getRange('D'+row).values[0][0]!=='待实施'||detail.getRange('E'+row).values[0][0]!=='未计入'||tasks.getRange('A'+oldRow).values[0][0]!==id||tasks.getRange('K'+oldRow).values[0][0]!=='待实施')throw Error('Task mapping/status changed.');
  const stamp=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
  const backups=[];
  for(let i=0;i<files.length;i++){backups[i]=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);await fs.copyFile(files[i],backups[i],constants.COPYFILE_EXCL);}
  const local={PAY05:'默认原沙箱链兼容；本轮服务器固定沙箱上下文、精确渠道矩阵、不可变服务器报价、单次原子消费与成交路由、原价重新确认、暂停与可信支付事实隔离已本地验收。前后台同决策，Python与本地Cloud各263项实际验证通过。'};
  const remaining={PAY05:'真实Apple/Google/Stripe/PayPal适配、商店验单及各端商品渠道准入待实施联调；主体/银行/地区/业务/币种结论、正式价格条款、实机与生产验收仍待完成。server_fixed_sandbox不等于真实商店地区，生产支付关闭。'};
  const receiptName=path.basename(receiptPath);
  for(const [id,row,oldRow] of rows){
   const progress=local[id]+' 收据：'+receiptName+'。';detail.getRange('D'+row).values=[['进行中']];detail.getRange('E'+row).values=[['已有证据']];tasks.getRange('K'+oldRow).values=[['进行中']];detail.getRange(`F${row}:G${row}`).values=[[progress,remaining[id]]];detail.getRange(`A${row}:H${row}`).format.rowHeight=145;
   const original=tasks.getRange('I'+oldRow).values[0][0].split(/\n(?:现状|本轮)：/)[0];
   tasks.getRange('I'+oldRow).values=[[original+'\n本轮：'+progress+'\n剩余：'+remaining[id]+'\n证据：06_验证与后续工作/'+receiptName]];tasks.getRange(`A${oldRow}:N${oldRow}`).format.rowHeight=285;
  }
  const [year,month,day]=receipt.at_beijing.slice(0,10).split('-');overview.getRange('A3').values=[['依据 v1.0 修改需求 · 截至 '+year+' 年 '+Number(month)+' 月 '+Number(day)+' 日（北京时间）']];
  overview.getRange('D12:E12').values=[['原核价、建单、退款、对账、客服、回调查单、迟到补偿与持续监测保留；本轮精确渠道矩阵、服务器报价、原子路由快照和原价重新确认已本地验收。','真实渠道与会员回调适配、当前准入与商店验单、正式价格条款、银行到账、实机和生产受管调度/外部通知仍待完成。']];overview.getRange('A12:E12').format.rowHeight=70;
  overview.getRange('D15').values=[['本地证据含部分功能及沙箱测试，其余 30 项未计入此口径。28 个开发阶段已有本地验收记录。']];
  overview.getRange('D20:E20').values=[['通用回调、主动查单、迟到补偿、持续任务/告警已验收；本轮新增精确沙箱渠道矩阵、服务器报价、成交路由与原价确认，生产支付关闭。','真实支付SDK/商店验单及会员回调适配、当前准入、正式价格条款、实际退款到账与生产服务另行联调。报价确认及告警受理均不表示付款或退款完成。']];overview.getRange('A20:E20').format.rowHeight=70;
  const title=tasks.getRange('A4').values[0][0];if(!title.includes('27个本地实施阶段'))throw Error('Original stage summary changed.');tasks.getRange('A4').values=[[title.replace('27个本地实施阶段','28个本地实施阶段')]];
  books.forEach(book=>book.recalculate());
  if(overview.getRange('C15').values[0][0]!==68||overview.getRange('C12').values[0][0]!==20||overview.getRange('B29').values[0][0]!=='进行中 70 项'||overview.getRange('E29').values[0][0]!=='待实施 3 项')throw Error('Expected PAY05 evidence/status counts did not recalculate.');
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
  console.log(JSON.stringify({updated:outputs,stage:28,rowsWithEvidence:68,otherRows:30,statusCounts:{进行中:70,待资料:16,待验收:9,待实施:3}}));
 }else throw Error('Use inspect; apply requires --verified-by-root <frozen receipt> <SHA256> after final gates.');
}catch(error){console.error(error.message);process.exitCode=1;}
