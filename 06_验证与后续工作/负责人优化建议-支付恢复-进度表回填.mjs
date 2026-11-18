import fs from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';

const bundled = createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile} = await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence = import.meta.dirname;
const files = ['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const mode = process.argv[2]||'inspect';
try {
  const books = await Promise.all(files.map(async file=>SpreadsheetFile.importXlsx(await FileBlob.load(file))));
  if (mode==='inspect') {
    for (const [book,sheetName,range,suffix] of [[books[0],'98项明细','A76:H80','原表PAY09'],[books[1],'优化任务表','A81:N85','原任务表PAY09']]) {
      console.log((await book.inspect({kind:'table',range:`'${sheetName}'!${range}`,maxChars:6500,tableMaxRows:5,tableMaxCols:14,tableMaxCellChars:600})).ndjson);
      const image = await book.render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`负责人优化建议-支付恢复-进度表-${suffix}.png`),new Uint8Array(await image.arrayBuffer()));
    }
  } else if (mode==='apply' && process.argv[3]==='--verified-by-root' && process.argv[4]) {
    const receiptPath = path.resolve(process.argv[4]);
    const receipt = JSON.parse(await fs.readFile(receiptPath,'utf8'));
    if (receipt.pass!==true || receipt.stage!==22 || receipt.taskId!=='PAY09') throw new Error('A verified stage22 PAY09 receipt is required.');
    const receiptName = path.basename(receiptPath);
    const [workbook,legacy] = books;
    const detail = workbook.worksheets.getItem('98项明细');
    const overview = workbook.worksheets.getItem('进度总览');
    const tasks = legacy.worksheets.getItem('优化任务表');
    if (detail.getRange('A78').values[0][0]!=='PAY09' || detail.getRange('D78').values[0][0]!=='待实施' || detail.getRange('E78').values[0][0]!=='未计入'
       || tasks.getRange('A83').values[0][0]!=='PAY09' || tasks.getRange('K83').values[0][0]!=='待实施') throw new Error('PAY09 source rows changed; reconcile first.');
    const stamp = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
    const backups = [];
    for (let index=0;index<files.length;index++) {
      backups[index] = path.join(evidence,`负责人优化建议-支付恢复-${index?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);
      await fs.copyFile(files[index],backups[index],constants.COPYFILE_EXCL);
    }
    detail.getRange('D78:G78').values = [[
      '进行中','已有证据',
      `通用本地软件已验收：沙箱签名查单、本人幂等恢复、关页回查及限定收件消费。收据：${receiptName}。`,
      '正式渠道验单和主动查单适配仍待实施联调。PAY13迟到付款的库存与权益补偿另项继续；生产真实服务尚未验收。',
    ]];
    detail.getRange('A78:H78').format.rowHeight = 76;
    overview.getRange('D12:E12').values = [[
      '核价、建单、沙箱退款、只读对账、客服工单、回调收件及本人主动查单恢复已有本地验证。',
      '正式渠道验单与查单适配仍待实施联调。继续迟到付款库存复核、权益补偿、对账处置及告警。',
    ]];
    overview.getRange('D15').values = [['本地证据含部分功能及沙箱测试，其余 31 项未计入此口径。22 个开发阶段已有本地验收记录。']];
    overview.getRange('D20:E20').values = [[
      '通用回调与主动查单恢复软件已本地验收，可回查与恢复。继续迟到付款库存复核、权益补偿及告警。',
      '正式渠道验单和主动查单适配待实施联调。PAY13迟到补偿另项，真实资金及会员回调、常驻调度另验。',
    ]];
    if (!overview.getRange('A28').values[0][0].includes('有本地证据')) throw new Error('Summary footnote baseline changed.');
    overview.getRange('A28').values = [['「有本地证据」含局部实现。「进行中」表示整项尚未完工；本地已验收范围、剩余软件与正式接入/验收分别见「98项明细」。']];
    tasks.getRange('K83').values = [['进行中']];
    const dependency = tasks.getRange('I83').values[0][0];
    tasks.getRange('I83').values = [[`${dependency}\n本轮：通用本地软件已验收，沙箱签名查单、本人幂等恢复、关页回查及限定收件消费可用。正式渠道验单和主动查单适配仍待实施联调；PAY13迟到补偿另项继续。\n证据：06_验证与后续工作/${receiptName}`]];
    tasks.getRange('A83:N83').format.rowHeight = 145;
    const title = tasks.getRange('A4').values[0][0];
    if (!title.includes('21个本地实施阶段')) throw new Error('Legacy stage summary changed.');
    tasks.getRange('A4').values = [[title.replace('21个本地实施阶段','22个本地实施阶段')]];
    books.forEach(book=>book.recalculate());
    if (overview.getRange('C12').values[0][0]!==19 || overview.getRange('C15').values[0][0]!==67
       || overview.getRange('B29').values[0][0]!=='进行中 69 项' || overview.getRange('E29').values[0][0]!=='待实施 4 项') throw new Error('PAY09 summary did not recalculate correctly.');
    const results = [];
    for (let index=0;index<books.length;index++) {
      const errors = await books[index].inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
      if (errors.records.some(item=>item.kind==='match')) throw new Error('Workbook formula error scan failed.');
      const candidate = path.join(evidence,`负责人优化建议-支付恢复-${index?'原98项任务表':'负责人进度表'}待校验.xlsx`);
      await (await SpreadsheetFile.exportXlsx(books[index])).save(candidate);
      const report = path.join(evidence,`负责人优化建议-支付恢复-${index?'原98项任务表':'负责人进度表'}回填校验.json`);
      execFileSync('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',['-B',path.join(evidence,'负责人优化建议-支付恢复-进度表校验.py'),backups[index],candidate,report],{encoding:'utf8',stdio:'pipe'});
      results.push({output:files[index],backup:backups[index],candidate,report});
    }
    for (const [book,sheetName,range,suffix] of [[books[0],'进度总览','A1:E29','回填后汇总'],[books[0],'98项明细','A76:H80','回填后PAY09'],[books[1],'优化任务表','A81:N85','原任务表回填后PAY09']]) {
      const image = await book.render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`负责人优化建议-支付恢复-进度表-${suffix}.png`),new Uint8Array(await image.arrayBuffer()));
    }
    for (const result of results) {
      await fs.copyFile(result.candidate,result.output);
      await fs.unlink(result.candidate);
      delete result.candidate;
      result.sha256 = createHash('sha256').update(await fs.readFile(result.output)).digest('hex');
    }
    console.log(JSON.stringify({updated:results,rowsWithEvidence:67,otherRows:31,stage:22,statusCounts:{进行中:69,待资料:16,待验收:9,待实施:4}}));
  } else throw new Error('Use inspect, or apply --verified-by-root <final PAY09 receipt>.');
} catch (error) { console.error(error.message); process.exitCode=1; }
