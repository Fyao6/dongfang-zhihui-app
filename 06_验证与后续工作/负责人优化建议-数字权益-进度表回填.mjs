import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const bundled=createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence=import.meta.dirname,prefix='负责人优化建议-数字权益';
const files=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const baseline=['3f290b34652cef4c7d3bbe0bb11ad45bddda2824bfe2e349b4aff859a8036f5b','85fda694fbe0488da998230500831604c0e31ebd58d65cc4e796848080493c65'];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const previews=[[0,'98项明细','A44:H46','SH06'],[1,'优化任务表','A49:N51','原任务SH06']];
try {
  for(let i=0;i<files.length;i++)if(sha(await fs.readFile(files[i]))!==baseline[i])throw new Error('Workbook baseline changed; reconcile first.');
  const books=await Promise.all(files.map(async file=>SpreadsheetFile.importXlsx(await FileBlob.load(file))));
  const mode=process.argv[2]||'inspect';
  if(mode==='inspect') {
    for(const [index,sheetName,range,suffix] of previews) {
      console.log((await books[index].inspect({kind:'table',range:`'${sheetName}'!${range}`,maxChars:6500,tableMaxRows:3,tableMaxCols:14,tableMaxCellChars:900})).ndjson);
      const blob=await books[index].render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填前${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));
    }
  } else if(mode==='apply'&&process.argv[3]==='--verified-by-root'&&process.argv[4]&&/^[a-f0-9]{64}$/.test(process.argv[5]||'')) {
    // Run the skill's single expected-output-count=2 edit marker immediately before this command.
    const receiptPath=path.resolve(process.argv[4]),bytes=await fs.readFile(receiptPath),receipt=JSON.parse(bytes);
    if(path.basename(receiptPath)!==prefix+'-实施记录.json'||sha(bytes)!==process.argv[5]||receipt.pass!==true||receipt.stage!==25||!(receipt.taskId==='SH06'||JSON.stringify(receipt.taskIds)===JSON.stringify(['SH06'])))throw new Error('Frozen, verified stage25 SH06 receipt required.');
    const detail=books[0].worksheets.getItem('98项明细'),overview=books[0].worksheets.getItem('进度总览'),tasks=books[1].worksheets.getItem('优化任务表');
    if(detail.getRange('A45').values[0][0]!=='SH06'||detail.getRange('D45').values[0][0]!=='进行中'||detail.getRange('E45').values[0][0]!=='已有证据'||tasks.getRange('A50').values[0][0]!=='SH06'||tasks.getRange('K50').values[0][0]!=='进行中')throw new Error('SH06 mapping or status changed.');
    const stamp=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
    const backups=[];
    for(let i=0;i<files.length;i++) {backups[i]=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);await fs.copyFile(files[i],backups[i],constants.COPYFILE_EXCL);}
    const receiptName=path.basename(receiptPath);
    const progress=`有限期限/次数的独立数字权益本地软件已验收：成交快照、普通及迟到付款唯一授予、原子取得访问租约、退款保留已用记录、每次媒体及Range重核；四语APP与中文后台可用。收据：${receiptName}。`;
    const remaining='正式版权、次数期限与退款政策待确认，真实验单及生产媒体接入仍须实施联调验收。当前默认关闭、仅隔离沙箱素材；旧订单不补造政策或额度。';
    detail.getRange('F45:G45').values=[[progress,remaining]];
    detail.getRange('A45:H45').format.rowHeight=115;
    const original=tasks.getRange('I50').values[0][0].split(/\n(?:现状|本轮)：/)[0];
    tasks.getRange('I50').values=[[`${original}\n本轮：${progress}\n剩余：${remaining}\n证据：06_验证与后续工作/${receiptName}`]];
    tasks.getRange('A50:N50').format.rowHeight=210;
    overview.getRange('D9:E9').values=[[
      '商城交易与多规格已有证据；本轮补齐独立数字商品期限、次数及最终媒体访问门禁，普通与迟到付款同事务授予。',
      '正式商品版权、次数期限/退款政策、真实支付与生产媒体服务待联调验收。仓配及售后完结继续按相应任务推进。',
    ]];
    overview.getRange('D15').values=[['本地证据含部分功能及沙箱测试，其余 31 项未计入此口径。25 个开发阶段已有本地验收记录。']];
    overview.getRange('D21:E21').values=[[
      '会员AI周期额度与独立数字商品次数/期限本地软件已验收，分账保留。数字访问按取得租约计次，可同会话回查续用。',
      '正式会员与数字内容政策、真实供应商费用、渠道验单及生产媒体接入另验。隔离素材不会授予真实会员媒体权限。',
    ]];
    const title=tasks.getRange('A4').values[0][0];if(!title.includes('24个本地实施阶段'))throw new Error('Legacy stage summary changed.');
    tasks.getRange('A4').values=[[title.replace('24个本地实施阶段','25个本地实施阶段')]];
    books.forEach(book=>book.recalculate());
    if(overview.getRange('C15').values[0][0]!==67||overview.getRange('B29').values[0][0]!=='进行中 69 项'||overview.getRange('E29').values[0][0]!=='待实施 4 项')throw new Error('Evidence/status counts must stay unchanged.');
    const outputs=[];
    for(let i=0;i<books.length;i++) {
      const errors=await books[i].inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
      if(errors.records.some(row=>row.kind==='match'))throw new Error('Formula error scan failed.');
      const candidate=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}待校验.xlsx`),report=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填校验.json`);
      await(await SpreadsheetFile.exportXlsx(books[i])).save(candidate);
      execFileSync('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',['-B',path.join(evidence,prefix+'-进度表校验.py'),backups[i],candidate,report],{encoding:'utf8',stdio:'pipe'});
      outputs.push({output:files[i],backup:backups[i],candidate,report});
    }
    for(const [index,sheetName,range,suffix] of [...previews,[0,'进度总览','A1:E29','汇总']]) {
      const blob=await books[index].render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填后${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));
    }
    for(const output of outputs){await fs.copyFile(output.candidate,output.output);await fs.unlink(output.candidate);delete output.candidate;output.sha256=sha(await fs.readFile(output.output));}
    console.log(JSON.stringify({updated:outputs,stage:25,rowsWithEvidence:67,otherRows:31,statusCounts:{进行中:69,待资料:16,待验收:9,待实施:4}}));
  } else throw new Error('Use inspect, or apply --verified-by-root <receipt> <SHA256> after final gates.');
} catch(error){console.error(error.message);process.exitCode=1;}
