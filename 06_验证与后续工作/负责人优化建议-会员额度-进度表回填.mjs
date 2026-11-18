import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';

const bundled = createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile} = await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence = import.meta.dirname;
const prefix = '负责人优化建议-会员额度';
const files = ['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const sha = bytes=>createHash('sha256').update(bytes).digest('hex');
const baseline = ['42a3b0ba870a6d33f7bfc8c8d17a45e663e8c53439809e44a45c97ea27468956','d0be41ec6c5a82a13ebb97e87826bfaadc0d124649c9eceead3b6cb62ad9a366'];
const python = 'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const previews = [
  [0,'98项明细','A30:H32','AI05'],[0,'98项明细','A47:H49','MB01'],
  [1,'优化任务表','A35:N37','原任务AI05'],[1,'优化任务表','A52:N54','原任务MB01'],
];
try {
  for (let i=0;i<files.length;i++) if (sha(await fs.readFile(files[i]))!==baseline[i]) throw new Error('Workbook baseline changed; reconcile first.');
  const books = await Promise.all(files.map(async file=>SpreadsheetFile.importXlsx(await FileBlob.load(file))));
  const mode = process.argv[2]||'inspect';
  if (mode==='inspect') {
    for (const [index,sheetName,range,suffix] of previews) {
      console.log((await books[index].inspect({kind:'table',range:`'${sheetName}'!${range}`,maxChars:6500,tableMaxRows:3,tableMaxCols:14,tableMaxCellChars:700})).ndjson);
      const blob = await books[index].render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填前${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));
    }
    console.log((await books[0].inspect({kind:'table',range:"'进度总览'!A8:E15",maxChars:4000,tableMaxRows:8,tableMaxCols:5})).ndjson);
  } else if (mode==='apply' && process.argv[3]==='--verified-by-root' && process.argv[4] && /^[a-f0-9]{64}$/.test(process.argv[5]||'')) {
    // Run the skill's single expected-output-count=2 edit marker immediately before this authoring command.
    const receiptPath = path.resolve(process.argv[4]);
    const receiptBytes = await fs.readFile(receiptPath);
    const receipt = JSON.parse(receiptBytes);
    if (path.basename(receiptPath)!==prefix+'-实施记录.json' || sha(receiptBytes)!==process.argv[5]
        || receipt.pass!==true || receipt.stage!==24 || JSON.stringify(receipt.taskIds)!==JSON.stringify(['MB01','AI05'])) throw new Error('Frozen, verified stage24 MB01/AI05 receipt required.');
    const detail = books[0].worksheets.getItem('98项明细');
    const overview = books[0].worksheets.getItem('进度总览');
    const tasks = books[1].worksheets.getItem('优化任务表');
    const rows = [{id:'AI05',current:31,old:36},{id:'MB01',current:48,old:53}];
    for (const row of rows) if (detail.getRange('A'+row.current).values[0][0]!==row.id || detail.getRange('D'+row.current).values[0][0]!=='进行中'
      || detail.getRange('E'+row.current).values[0][0]!=='已有证据' || tasks.getRange('A'+row.old).values[0][0]!==row.id || tasks.getRange('K'+row.old).values[0][0]!=='进行中') throw new Error('Requirement rows changed: '+row.id);
    const stamp = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
    const backups = [];
    for (let i=0;i<files.length;i++) {
      backups[i] = path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);
      await fs.copyFile(files[i],backups[i],constants.COPYFILE_EXCL);
    }
    const receiptName = path.basename(receiptPath);
    const changes = [
      [`独立测试credits与用量/未知成本记录保留；已付会员快照的周期桶、服务端来源、原子预占/一次结算及本人导出已本地验收。收据：${receiptName}。`,
       '正式会员额度与扣次政策、真实供应商费用及成本对账、正式渠道和生产环境仍待确认与实际接入验收。'],
      [`统一SKU方案、不可变版本与有限周期权益保留；会员AI按UTC成交起点唯一发放，提前续期不早发，暂停/恢复不重发，退款/到期在途原桶结算已验收。收据：${receiptName}。`,
       '正式方案、价格与额度规则及渠道适配仍待确认联调；真实供应商与生产权益另验。默认关闭，不预设正式无限额度或优惠。'],
    ];
    rows.forEach((row,index)=>{
      detail.getRange(`F${row.current}:G${row.current}`).values = [changes[index]];
      detail.getRange(`A${row.current}:H${row.current}`).format.rowHeight = 100;
      const original = tasks.getRange('I'+row.old).values[0][0].split(/\n(?:现状|本轮)：/)[0];
      tasks.getRange('I'+row.old).values = [[`${original}\n本轮：${changes[index][0]}\n剩余：${changes[index][1]}\n证据：06_验证与后续工作/${receiptName}`]];
      tasks.getRange(`A${row.old}:N${row.old}`).format.rowHeight = 195;
    });
    overview.getRange('D8:E8').values = [[
      '网关、隐私与记忆已有证据；本轮接通会员周期额度的服务端预占/结算和本人导出，保留独立测试钱包与未知成本。',
      '真实模型、供应商费用及成本对账仍待接入验收，生产门禁保留。外部删除与其他隐私收尾另行推进。',
    ]];
    overview.getRange('D10:E10').values = [[
      '会员方案、有限周期与退款生命周期已有证据；本轮补齐已付会员AI周期额度、暂停/恢复及到期/退款在途处理。',
      '正式方案价格、额度政策、分佣规则与渠道适配须确认联调，真实退款到账及生产环境另验。',
    ]];
    overview.getRange('D15').values = [['本地证据含部分功能及沙箱测试，其余 31 项未计入此口径。24 个开发阶段已有本地验收记录。']];
    overview.getRange('D21:E21').values = [[
      '会员AI周期发放和结算已本地验收，用尽或失效不自动改扣独立测试余额。继续SH06独立单购的次数、期限与最终访问门禁。',
      '正式会员政策、真实供应商及生产渠道另验；数字单购的到期/退款/售后与访问一致性仍需实施复核。',
    ]];
    const oldTitle = tasks.getRange('A4').values[0][0];
    if (!oldTitle.includes('23个本地实施阶段')) throw new Error('Original stage summary changed.');
    tasks.getRange('A4').values = [[oldTitle.replace('23个本地实施阶段','24个本地实施阶段')]];
    books.forEach(book=>book.recalculate());
    if (overview.getRange('C15').values[0][0]!==67 || overview.getRange('B29').values[0][0]!=='进行中 69 项' || overview.getRange('E29').values[0][0]!=='待实施 4 项') throw new Error('Evidence/status counts must stay unchanged.');
    const outputs = [];
    for (let i=0;i<books.length;i++) {
      const errors = await books[i].inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
      if (errors.records.some(row=>row.kind==='match')) throw new Error('Formula error scan failed.');
      const candidate = path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}待校验.xlsx`);
      const report = path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填校验.json`);
      await (await SpreadsheetFile.exportXlsx(books[i])).save(candidate);
      execFileSync(python,['-B',path.join(evidence,prefix+'-进度表校验.py'),backups[i],candidate,report],{encoding:'utf8',stdio:'pipe'});
      outputs.push({output:files[i],backup:backups[i],candidate,report});
    }
    for (const [index,sheetName,range,suffix] of [...previews,[0,'进度总览','A1:E29','汇总']]) {
      const blob = await books[index].render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填后${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));
    }
    for (const output of outputs) {
      await fs.copyFile(output.candidate,output.output);
      await fs.unlink(output.candidate);
      delete output.candidate;
      output.sha256 = sha(await fs.readFile(output.output));
    }
    console.log(JSON.stringify({updated:outputs,stage:24,rowsWithEvidence:67,otherRows:31,statusCounts:{进行中:69,待资料:16,待验收:9,待实施:4}}));
  } else throw new Error('Use inspect, or apply --verified-by-root <frozen receipt> <expected SHA256> after final gates.');
} catch (error) { console.error(error.message);process.exitCode=1; }
