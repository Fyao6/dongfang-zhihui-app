// Prepared stage27 narrow workbook edit. Inspect is read-only; apply needs the frozen root-verified receipt.
import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const bundled=createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence=import.meta.dirname,prefix='负责人优化建议-任务告警';
const files=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const baseline=['06365d4790018efeeab3cda37b2e56c241fb6ecc0005b0aee8182ea2c280fa57','05d7067631ef619d37ca1d5f54e2274d7a94ea6fde7b5b97d44cf9c6f5db210b'];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const previews=[[0,'98项明细','A62:H62','SV04'],[0,'98项明细','A87:H87','PAY18'],[1,'优化任务表','A67:N67','原任务SV04'],[1,'优化任务表','A92:N92','原任务PAY18'],[0,'进度总览','A5:E29','汇总']];
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
  if(path.basename(receiptPath)!==prefix+'-实施记录.json'||sha(bytes)!==process.argv[5]||receipt.pass!==true||receipt.stage!==27||JSON.stringify([...(receipt.taskIds||[])].sort())!==JSON.stringify(['PAY18','SV04'])||receipt.perBackendGateCount!==239)throw Error('Frozen, root-verified stage27 PAY18/SV04 receipt required.');
  const detail=books[0].worksheets.getItem('98项明细'),overview=books[0].worksheets.getItem('进度总览'),tasks=books[1].worksheets.getItem('优化任务表');
  const rows=[['SV04',62,67],['PAY18',87,92]];
  for(const [id,row,oldRow] of rows)if(detail.getRange('A'+row).values[0][0]!==id||detail.getRange('D'+row).values[0][0]!=='进行中'||detail.getRange('E'+row).values[0][0]!=='已有证据'||tasks.getRange('A'+oldRow).values[0][0]!==id||tasks.getRange('K'+oldRow).values[0][0]!=='进行中')throw Error('Task mapping/status changed.');
  const stamp=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
  const backups=[];
  for(let i=0;i<files.length;i++){backups[i]=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);await fs.copyFile(files[i],backups[i],constants.COPYFILE_EXCL);}
  const local={
   SV04:'保留隔离、密钥引用和账号门禁证据；本轮显式fresh runtime/不可变manifest、真实管理员session的持续任务进程、重启恢复、逐单元双租约事务守卫、配置默认关闭、持久运行与异常受理记录已本地验收。中文后台可回查，APP四语兼容。',
   PAY18:'本地持续只读采集回调/查单积压、迟到退款待办、对账及有限数字权益/会员已物化事实；告警episode去重、版本化受理、有限重试和签名本机HTTP确认回执已验收。缺源/截断/未知指标不报健康0；不自动退款。',
  };
  const remaining={
   SV04:'远程KMS/IAM/MFA、生产私网/TLS、数据库迁移/PITR、受管常驻部署与外部通知、恢复/回滚编排软件及目标环境验收仍待实施；本机持续进程不等于生产cron。',
   PAY18:'正式渠道支付/退款失败事件连接器、真实外部收件与升级通知、生产部署和正式阈值仍待实施联调。当前仅loopback-fixture，externalSent=false；未配置阈值与未知来源保持明确未覆盖。',
  };
  const receiptName=path.basename(receiptPath);
  for(const [id,row,oldRow] of rows){
   const progress=local[id]+' 收据：'+receiptName+'。';detail.getRange(`F${row}:G${row}`).values=[[progress,remaining[id]]];detail.getRange(`A${row}:H${row}`).format.rowHeight=145;
   const original=tasks.getRange('I'+oldRow).values[0][0].split(/\n(?:现状|本轮)：/)[0];
   tasks.getRange('I'+oldRow).values=[[original+'\n本轮：'+progress+'\n剩余：'+remaining[id]+'\n证据：06_验证与后续工作/'+receiptName]];tasks.getRange(`A${oldRow}:N${oldRow}`).format.rowHeight=285;
  }
  overview.getRange('D11').values=[['两云架构/询价与本机短压测、SQLite恢复保留；本轮补齐隔离fresh runtime持续任务、真实授权、双租约和异常受理的本地软件证据。']];overview.getRange('A11:E11').format.rowHeight=70;
  overview.getRange('D12:E12').values=[['核价、建单、退款、对账、客服、回调/查单及迟到补偿保留；本轮本地持续监测、异常受理与签名本机通知回执已验收。','正式渠道、真实退款、会员适配与生产受管调度/监控/外部通知仍待实施联调。退款待办或告警受理不表示资金已退款。']];overview.getRange('A12:E12').format.rowHeight=70;
  overview.getRange('D15').values=[['本地证据含部分功能及沙箱测试，其余 31 项未计入此口径。27 个开发阶段已有本地验收记录。']];
  overview.getRange('D20:E20').values=[['通用回调、主动查单、迟到补偿和本地持续任务/只读告警已验收；版本化受理、有限重试与签名本机HTTP确认可持久回查。','继续正式渠道/真实退款/会员回调、生产调度与外部告警软件接入。SH06次数、期限和访问门禁已本地验收，正式版权和生产媒体另验。']];overview.getRange('A20:E20').format.rowHeight=70;
  const title=tasks.getRange('A4').values[0][0];if(!title.includes('26个本地实施阶段'))throw Error('Original stage summary changed.');tasks.getRange('A4').values=[[title.replace('26个本地实施阶段','27个本地实施阶段')]];
  books.forEach(book=>book.recalculate());
  if(overview.getRange('C15').values[0][0]!==67||overview.getRange('B29').values[0][0]!=='进行中 69 项'||overview.getRange('E29').values[0][0]!=='待实施 4 项')throw Error('Evidence/status counts must remain unchanged.');
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
  console.log(JSON.stringify({updated:outputs,stage:27,rowsWithEvidence:67,otherRows:31,statusCounts:{进行中:69,待资料:16,待验收:9,待实施:4}}));
 }else throw Error('Use inspect; apply requires --verified-by-root <frozen receipt> <SHA256> after final gates.');
}catch(error){console.error(error.message);process.exitCode=1;}
