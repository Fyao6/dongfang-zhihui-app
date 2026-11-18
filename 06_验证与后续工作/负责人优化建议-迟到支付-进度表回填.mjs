import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {constants} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';

const bundled = createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile} = await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence = import.meta.dirname;
const files = ['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const mode = process.argv[2]||'inspect';
try {
  const books = await Promise.all(files.map(async file=>SpreadsheetFile.importXlsx(await FileBlob.load(file))));
  if (mode==='apply' && process.argv[3]==='--verified-by-root' && process.argv[4]) {
    const receiptPath = path.resolve(process.argv[4]);
    const receipt = JSON.parse(await fs.readFile(receiptPath,'utf8'));
    if (receipt.pass!==true || receipt.stage!==23 || path.basename(receiptPath)!=='负责人优化建议-迟到补偿-实施记录.json') throw new Error('The verified stage23 late-payment receipt is required.');
    const receiptName = path.basename(receiptPath);
    const [workbook,legacy] = books;
    const detail = workbook.worksheets.getItem('98项明细');
    const overview = workbook.worksheets.getItem('进度总览');
    const tasks = legacy.worksheets.getItem('优化任务表');
    const current = [77,78,79,82];
    const old = [82,83,84,87];
    const ids = ['PAY08','PAY09','PAY10','PAY13'];
    ids.forEach((id,index)=>{
      if (detail.getRange('A'+current[index]).values[0][0]!==id || detail.getRange('D'+current[index]).values[0][0]!=='进行中' || detail.getRange('E'+current[index]).values[0][0]!=='已有证据'
          || tasks.getRange('A'+old[index]).values[0][0]!==id || tasks.getRange('K'+old[index]).values[0][0]!=='进行中') throw new Error('Source requirement mapping changed: '+id);
    });
    const stamp = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
    const backups = [];
    for (let index=0;index<files.length;index++) {
      backups[index] = path.join(evidence,`负责人优化建议-迟到补偿-${index?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);
      await fs.copyFile(files[index],backups[index],constants.COPYFILE_EXCL);
    }
    const changes = [
      [
        `收件、事件与交易去重、独立消费及有限重试已有本地验收；本轮补齐通用沙箱迟到补偿。收据：负责人优化建议-支付回调-实施记录.json；${receiptName}。`,
        '正式渠道验签/验单、会员回调、生产常驻调度与监控待实施联调。真实退款与资金到账另行验收。',
      ],[
        `本人沙箱签名查单、幂等恢复与关页回查已有本地验收；本轮过期订单也可真HTTP查单并走同一可信收件补偿。收据：负责人优化建议-支付恢复-实施记录.json；${receiptName}。`,
        '正式渠道验单与主动查单适配、会员适配、生产调度与监控仍待实施联调。真实退款到账另行验收。',
      ],[
        `可信沙箱迟到付款按原成交快照重核全部SKU，原子接续履约与唯一数字权益；退款待办及本人回查已验收。收据：${receiptName}。`,
        '正式渠道、会员回调及真实退款适配/到账待联调验收。SH06独立单购的有限次数、期限与访问校验仍待实施。',
      ],[
        `超时释放后可信沙箱付款重核全部SKU：有货按原价接续，无货、下架或绑定变化转持久退款待办，后台幂等受理、本人订单可查。收据：${receiptName}。`,
        '真实渠道迟到事件与退款资金闭环、会员适配、生产调度及监控须继续实施联调。退款待办受理不等于退款到账。',
      ],
    ];
    changes.forEach((values,index)=>{
      detail.getRange(`F${current[index]}:G${current[index]}`).values = [values];
      detail.getRange(`A${current[index]}:H${current[index]}`).format.rowHeight = 90;
      const source = tasks.getRange('I'+old[index]).values[0][0].split('\n本轮：')[0];
      tasks.getRange('I'+old[index]).values = [[`${source}\n本轮：${values[0]}\n剩余：${values[1]}\n证据：06_验证与后续工作/${receiptName}`]];
      tasks.getRange(`A${old[index]}:N${old[index]}`).format.rowHeight = 185;
    });
    overview.getRange('D12:E12').values = [[
      '核价、建单、退款、对账、客服、回调和主动查单已有本地验证；本轮补齐迟到库存重核与唯一数字权益。',
      '正式渠道、真实退款到账、会员适配、生产调度与监控仍待实施联调。退款待办可受理，不等于资金退款已完成。',
    ]];
    overview.getRange('D15').values = [['本地证据含部分功能及沙箱测试，其余 31 项未计入此口径。23 个开发阶段已有本地验收记录。']];
    overview.getRange('D20:E20').values = [[
      '通用回调、主动查单与迟到库存/权益补偿已本地验收；退款待办可幂等受理并在本人订单回查。',
      '继续正式渠道与真实退款适配、会员回调、生产调度和监控。SH06有限次数/期限等后续软件仍需实施。',
    ]];
    const title = tasks.getRange('A4').values[0][0];
    if (!title.includes('22个本地实施阶段')) throw new Error('Legacy stage summary changed.');
    tasks.getRange('A4').values = [[title.replace('22个本地实施阶段','23个本地实施阶段')]];
    books.forEach(book=>book.recalculate());
    if (overview.getRange('C12').values[0][0]!==19 || overview.getRange('C15').values[0][0]!==67
        || overview.getRange('B29').values[0][0]!=='进行中 69 项' || overview.getRange('E29').values[0][0]!=='待实施 4 项') throw new Error('Status/evidence counts must remain unchanged.');
    const outputs = [];
    for (let index=0;index<books.length;index++) {
      const errors = await books[index].inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
      if (errors.records.some(row=>row.kind==='match')) throw new Error('Formula error scan failed.');
      const candidate = path.join(evidence,`负责人优化建议-迟到补偿-${index?'原98项任务表':'负责人进度表'}待校验.xlsx`);
      await (await SpreadsheetFile.exportXlsx(books[index])).save(candidate);
      const report = path.join(evidence,`负责人优化建议-迟到补偿-${index?'原98项任务表':'负责人进度表'}回填校验.json`);
      execFileSync('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',['-B',path.join(evidence,'负责人优化建议-迟到补偿-进度表校验.py'),backups[index],candidate,report],{encoding:'utf8',stdio:'pipe'});
      outputs.push({output:files[index],backup:backups[index],candidate,report});
    }
    for (const [book,sheetName,range,suffix] of [[books[0],'进度总览','A1:E29','回填后汇总'],[books[0],'98项明细','A77:H82','回填后相关四项'],[books[1],'优化任务表','A82:N87','原任务表回填后相关四项']]) {
      const image = await book.render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`负责人优化建议-迟到补偿-进度表-${suffix}.png`),new Uint8Array(await image.arrayBuffer()));
    }
    for (const output of outputs) {
      await fs.copyFile(output.candidate,output.output);
      await fs.unlink(output.candidate);
      delete output.candidate;
      output.sha256 = createHash('sha256').update(await fs.readFile(output.output)).digest('hex');
    }
    console.log(JSON.stringify({updated:outputs,rowsWithEvidence:67,otherRows:31,stage:23,statusCounts:{进行中:69,待资料:16,待验收:9,待实施:4}}));
  } else if (mode==='inspect') {
  const details = books[0].worksheets.getItem('98项明细').getRange('A6:H103').values;
  console.log(JSON.stringify(details.map((row,index)=>({row:index+6,id:row[0],title:row[2],status:row[3],evidence:row[4],progress:row[5],remaining:row[6]})).filter(row=>['PAY08','PAY09','PAY10','PAY13'].includes(row.id))));
  const tasks = books[1].worksheets.getItem('优化任务表').getRange('A11:N108').values;
  console.log(JSON.stringify(tasks.map((row,index)=>({row:index+11,id:row[0],title:row[2],status:row[10],dependency:row[8],source:row[13]})).filter(row=>['PAY08','PAY09','PAY10','PAY13'].includes(row.id))));
  console.log((await books[0].inspect({kind:'table',range:"'进度总览'!A12:E15",maxChars:4000,tableMaxRows:4,tableMaxCols:5})).ndjson);
  for (const [book,sheetName,range,suffix] of [[books[0],'98项明细','A77:H82','原表相关四项'],[books[1],'优化任务表','A82:N87','原任务表相关四项']]) {
    const image = await book.render({sheetName,range,scale:1,format:'png'});
    await fs.writeFile(path.join(evidence,`负责人优化建议-迟到支付-进度表-${suffix}.png`),new Uint8Array(await image.arrayBuffer()));
  }
  } else throw new Error('Use inspect, or apply --verified-by-root <final stage23 receipt>.');
} catch (error) { console.error(error.message); process.exitCode=1; }
