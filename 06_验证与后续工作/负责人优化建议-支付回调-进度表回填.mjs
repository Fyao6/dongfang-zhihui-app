import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {constants} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';

const requireBundled = createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob, SpreadsheetFile} = await import(pathToFileURL(requireBundled.resolve('@oai/artifact-tool')).href);
const root = path.resolve(import.meta.dirname, '..');
const evidenceDir = path.join(root, '06_验证与后续工作');
const input = path.join(evidenceDir, '东方智慧APP需求进度表-20261116.xlsx');
try {
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
const mode = process.argv[2] || 'inspect';

if (mode === 'inspect') {
console.log((await workbook.inspect({kind:'workbook,sheet',maxChars:2000})).ndjson);
console.log((await workbook.inspect({kind:'table',range:"'98项明细'!A75:H79",include:'values,formulas',maxChars:7000,tableMaxRows:5,tableMaxCols:8,tableMaxCellChars:700})).ndjson);
console.log((await workbook.inspect({kind:'formula',sheetId:'进度总览',range:'A1:E29',maxChars:4000,options:{maxResults:30}})).ndjson);
for (const [sheetName, range, suffix] of [['进度总览','A1:E29','原表汇总'],['98项明细','A75:H79','原表PAY08']]) {
  const image = await workbook.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(path.join(evidenceDir,`负责人优化建议-支付回调-进度表-${suffix}.png`),new Uint8Array(await image.arrayBuffer()));
}
const legacy = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(evidenceDir,'东方智慧APP优化任务表_依据v1.0_20261112.xlsx')));
console.log((await legacy.inspect({kind:'workbook,sheet',maxChars:2500})).ndjson);
console.log((await legacy.inspect({kind:'match',searchTerm:'PAY08',options:{matchEntireCell:true,maxResults:5},maxChars:2000})).ndjson);
console.log((await legacy.inspect({kind:'table',range:"'优化任务表'!A1:L8",maxChars:7000,tableMaxRows:8,tableMaxCols:12,tableMaxCellChars:300})).ndjson);
console.log((await legacy.inspect({kind:'formula',maxChars:5000,options:{maxResults:30}})).ndjson);
console.log((await legacy.inspect({kind:'table',range:"'优化任务表'!A80:N84",maxChars:11000,tableMaxRows:5,tableMaxCols:14,tableMaxCellChars:1500})).ndjson);
for (const [range,suffix] of [['A1:N10','旧任务表表头'],['A80:N84','旧任务表PAY08']]) {
  const preview = await legacy.render({sheetName:'优化任务表',range,scale:1,format:'png'});
  await fs.writeFile(path.join(evidenceDir,`负责人优化建议-支付回调-进度表-${suffix}.png`),new Uint8Array(await preview.arrayBuffer()));
}
} else if (mode === 'finalize-summary' && process.argv[3] === '--verified-by-root') {
  const summary = workbook.worksheets.getItem('进度总览');
  if (summary.getRange('C15').values[0][0] !== 66) throw new Error('Expected completed PAY08 update.');
  summary.getRange('D15').values = [['本地证据含部分功能及沙箱测试，其余 32 项未计入此口径。21 个开发阶段已有本地验收记录。']];
  workbook.recalculate();
  const candidate = path.join(evidenceDir,'负责人优化建议-支付回调-负责人进度表待校验.xlsx');
  const backup = path.join(evidenceDir,'负责人优化建议-支付回调-负责人进度表回填前-20261116-154955.xlsx');
  const report = path.join(evidenceDir,'负责人优化建议-支付回调-负责人进度表回填校验.json');
  await (await SpreadsheetFile.exportXlsx(workbook)).save(candidate);
  execFileSync('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',['-B',path.join(evidenceDir,'负责人优化建议-支付回调-进度表校验.py'),backup,candidate,report],{encoding:'utf8',stdio:'pipe'});
  const preview = await workbook.render({sheetName:'进度总览',range:'A1:E29',scale:1,format:'png'});
  await fs.writeFile(path.join(evidenceDir,'负责人优化建议-支付回调-进度表-回填后汇总.png'),new Uint8Array(await preview.arrayBuffer()));
  await fs.copyFile(candidate,input);
  await fs.unlink(candidate);
  console.log(JSON.stringify({updated:input,sha256:createHash('sha256').update(await fs.readFile(input)).digest('hex'),report,rowsWithEvidence:66,otherRows:32}));
} else if (mode === 'apply' && process.argv[3] === '--verified-by-root') {
  const legacyPath = path.join(evidenceDir,'东方智慧APP优化任务表_依据v1.0_20261112.xlsx');
  const legacy = await SpreadsheetFile.importXlsx(await FileBlob.load(legacyPath));
  const detail = workbook.worksheets.getItem('98项明细');
  const summary = workbook.worksheets.getItem('进度总览');
  const originalTask = legacy.worksheets.getItem('优化任务表');
  if (detail.getRange('A77').values[0][0] !== 'PAY08' || detail.getRange('D77').values[0][0] !== '待实施'
      || detail.getRange('E77').values[0][0] !== '未计入' || originalTask.getRange('A82').values[0][0] !== 'PAY08'
      || originalTask.getRange('K82').values[0][0] !== '待实施') {
    throw new Error('Source PAY08 rows changed. Stop to reconcile before updating.');
  }
  const stamp = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
  const backups = [input,legacyPath].map((file,index)=>path.join(evidenceDir,`负责人优化建议-支付回调-${index?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`));
  await fs.copyFile(input,backups[0],constants.COPYFILE_EXCL);
  await fs.copyFile(legacyPath,backups[1],constants.COPYFILE_EXCL);
  const receiptName = '负责人优化建议-支付回调-实施记录.json';
  detail.getRange('D77:G77').values = [[
    '进行中','已有证据',
    `沙箱HMAC收件、事件与交易去重、独立消费、租约恢复、有限重试和后台核查已通过本地验证。收据：${receiptName}。`,
    '真实渠道验签与正式事件协议、会员回调及常驻调度待联调。迟到付款、主动查单及退款补偿按后续任务继续。',
  ]];
  detail.getRange('A77:H77').format.rowHeight = 76;
  summary.getRange('D12:E12').values = [[
    '核价、建单、模拟付款、沙箱退款、只读对账、四类客服工单及回调收件、去重、重试已验证。',
    '继续异常恢复、迟到付款库存复核、权益补偿、对账处置和告警。真实渠道验签、收银与银行验单待联调。',
  ]];
  summary.getRange('D15').values = [['本地证据含部分功能及沙箱测试，其余 32 项未计入此口径。21 个开发阶段已有本地验收记录。']];
  summary.getRange('D20:E20').values = [[
    '回调收件、事件与交易去重、有限重试已验证。继续异常恢复、迟到付款库存复核、权益补偿及告警。',
    '补充乱序、超时、迟到付款与对账处置演练。真实渠道验签、会员回调及常驻调度另验。',
  ]];
  originalTask.getRange('K82').values = [['进行中']];
  originalTask.getRange('I82').values = [[`回调签名与事件协议。\n本轮：沙箱HMAC收件、事件与交易去重、独立消费、租约恢复、有限重试和后台核查已通过本地验证。真实渠道验签、会员回调及常驻调度待联调；迟到付款、主动查单和补偿另验。\n证据：06_验证与后续工作/${receiptName}`]];
  originalTask.getRange('A82:N82').format.rowHeight = 148;
  const oldSummary = originalTask.getRange('A4').values[0][0];
  if (typeof oldSummary !== 'string' || !oldSummary.includes('20个本地实施阶段')) throw new Error('Legacy summary baseline changed.');
  originalTask.getRange('A4').values = [[oldSummary.replace('20个本地实施阶段','21个本地实施阶段')]];
  workbook.recalculate();
  legacy.recalculate();
  if (summary.getRange('C12').values[0][0] !== 18 || summary.getRange('C15').values[0][0] !== 66
      || summary.getRange('B29').values[0][0] !== '进行中 68 项' || summary.getRange('E29').values[0][0] !== '待实施 5 项') {
    throw new Error('Recalculated summary differs from the approved PAY08 count changes.');
  }
  const checks = [];
  const books = [workbook,legacy];
  const outputs = [input,legacyPath];
  for (let index=0;index<books.length;index++) {
    const errors = await books[index].inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
    if (errors.records.some(record=>record.kind==='match')) throw new Error('Workbook formula error scan failed.');
    const candidate = path.join(evidenceDir,`负责人优化建议-支付回调-${index?'原98项任务表':'负责人进度表'}待校验.xlsx`);
    const output = await SpreadsheetFile.exportXlsx(books[index]);
    await output.save(candidate);
    const report = path.join(evidenceDir,`负责人优化建议-支付回调-${index?'原98项任务表':'负责人进度表'}回填校验.json`);
    execFileSync('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',['-B',path.join(evidenceDir,'负责人优化建议-支付回调-进度表校验.py'),backups[index],candidate,report],{encoding:'utf8',stdio:'pipe'});
    checks.push({output:outputs[index],candidate,backup:backups[index],report});
  }
  for (const [book,sheetName,range,suffix] of [[workbook,'进度总览','A1:E29','回填后汇总'],[workbook,'98项明细','A75:H79','回填后PAY08'],[legacy,'优化任务表','A80:N84','旧任务表回填后PAY08']]) {
    const preview = await book.render({sheetName,range,scale:1,format:'png'});
    await fs.writeFile(path.join(evidenceDir,`负责人优化建议-支付回调-进度表-${suffix}.png`),new Uint8Array(await preview.arrayBuffer()));
  }
  for (const check of checks) {
    await fs.copyFile(check.candidate,check.output);
    await fs.unlink(check.candidate);
    const data = await fs.readFile(check.output);
    check.sha256 = createHash('sha256').update(data).digest('hex');
    delete check.candidate;
  }
  console.log(JSON.stringify({updated:checks,rowsWithEvidence:66,statusCounts:{进行中:68,待资料:16,待验收:9,待实施:5}}));
} else {
  throw new Error('Use inspect, or apply --verified-by-root only after final acceptance.');
}
} catch (error) { console.error(error.message); process.exitCode=1; }
