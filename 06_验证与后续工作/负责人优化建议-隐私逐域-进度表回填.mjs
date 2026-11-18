import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const bundled=createRequire('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.artifact-author.cjs');
const {FileBlob,SpreadsheetFile}=await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
const evidence=import.meta.dirname,prefix='负责人优化建议-隐私逐域';
const files=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'].map(name=>path.join(evidence,name));
const baseline=['fef58048b8ba024ff3594d056f0be53f6972ef28397536125a62b5b85114a5e2','d3f23121677aa5bca5dc37bd43448038d251764c605b411907250ff616a306bd'];
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const previews=[[0,'98项明细','A36:H37','PR04PR05'],[1,'优化任务表','A41:N42','原任务PR04PR05'],[0,'进度总览','A5:E29','汇总']];
try {
  for(let i=0;i<files.length;i++)if(sha(await fs.readFile(files[i]))!==baseline[i])throw new Error('Workbook baseline changed; reconcile first.');
  const books=await Promise.all(files.map(async file=>SpreadsheetFile.importXlsx(await FileBlob.load(file))));
  const mode=process.argv[2]||'inspect';
  if(mode==='inspect') {
    for(const [index,sheetName,range,suffix] of previews) {
      console.log((await books[index].inspect({kind:'table',range:`'${sheetName}'!${range}`,maxChars:12000,tableMaxRows:25,tableMaxCols:14,tableMaxCellChars:1400})).ndjson);
      const blob=await books[index].render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填前${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));
    }
  } else if(mode==='apply'&&process.argv[3]==='--verified-by-root'&&process.argv[4]&&/^[a-f0-9]{64}$/.test(process.argv[5]||'')) {
    // Run the skill's single expected-output-count=2 edit marker immediately before this command.
    const receiptPath=path.resolve(process.argv[4]),bytes=await fs.readFile(receiptPath),receipt=JSON.parse(bytes);
    if(path.basename(receiptPath)!==prefix+'-实施记录.json'||sha(bytes)!==process.argv[5]||receipt.pass!==true||receipt.stage!==26||JSON.stringify([...(receipt.taskIds||[])].sort())!==JSON.stringify(['PR04','PR05']))throw new Error('Frozen, verified stage26 PR04/PR05 receipt required.');
    const detail=books[0].worksheets.getItem('98项明细'),overview=books[0].worksheets.getItem('进度总览'),tasks=books[1].worksheets.getItem('优化任务表');
    for(const [id,row,oldRow] of [['PR04',36,41],['PR05',37,42]])if(detail.getRange('A'+row).values[0][0]!==id||detail.getRange('D'+row).values[0][0]!=='进行中'||detail.getRange('E'+row).values[0][0]!=='已有证据'||tasks.getRange('A'+oldRow).values[0][0]!==id||tasks.getRange('K'+oldRow).values[0][0]!=='进行中')throw new Error('PR04/PR05 mapping/status changed.');
    const stamp=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replaceAll('-','').replaceAll(':','').replace(' ','-');
    const backups=[];
    for(let i=0;i<files.length;i++) {backups[i]=path.join(evidence,`${prefix}-${i?'原98项任务表':'负责人进度表'}回填前-${stamp}.xlsx`);await fs.copyFile(files[i],backups[i],constants.COPYFILE_EXCL);}
    const receiptName=path.basename(receiptPath);
    const local={
      PR04:'本方逐域清点/导出与实清本地软件已验收：原7scope及legacy AI正文、新4域私人草稿/未完成入驻/咨询正文/无引用素材；本人确认、分批幂等回执、闭户首100及后台受限续办、永久引用保护与Cloud对象核验队列接通。四语APP、中文后台。',
      PR05:'新4域真实写入跟踪、未知旧龄保护/明确纳管起点、独立nullable期限、确认政策/CAS和可续批清理本地软件已验收；原7scope及记忆独立期限保留。训练/营销仍默认关闭，新用途独立授权；未部署生产自动调度。',
    };
    const remaining={
      PR04:'公开/共享/金融/源审计等保留与匿名化策略及相应处理软件尚未完成；正式期限/用途待确认。供应商、备份/WAL、向量/外部缓存删除待独立实施验收，不称全域擦除或已取消第三方续费。',
      PR05:'公开/共享/金融/源审计等域的正式用途/保留期限与匿名化处理软件仍待明确和实施；生产调度、备份、供应商及向量/缓存清理仍待实施联调。当前本地逻辑删除不证明WAL/备份安全擦除。',
    };
    for(const [id,row,oldRow] of [['PR04',36,41],['PR05',37,42]]) {
      const progress=local[id]+' 收据：'+receiptName+'。';
      detail.getRange('F'+row+':G'+row).values=[[progress,remaining[id]]];
      detail.getRange('A'+row+':H'+row).format.rowHeight=130;
      const original=tasks.getRange('I'+oldRow).values[0][0].split(/\n(?:现状|本轮)：/)[0];
      tasks.getRange('I'+oldRow).values=[[original+'\n本轮：'+progress+'\n剩余：'+remaining[id]+'\n证据：06_验证与后续工作/'+receiptName]];
      tasks.getRange('A'+oldRow+':N'+oldRow).format.rowHeight=255;
    }
    overview.getRange('D8:E8').values=[[
      '网关、记忆与会员周期额度保留已验收范围；本轮本方逐域清点/导出、7旧域及4新域实清、闭户续办与对象核验已有本地证据。',
      '真实模型与费用对账待接入；公开/共享/金融及源审计的保留/匿名化处理软件仍待实施，供应商/备份等删除另验。',
    ]];
    overview.getRange('A8:E8').format.rowHeight=62;
    overview.getRange('D15').values=[['本地证据含部分功能及沙箱测试，其余 31 项未计入此口径。26 个开发阶段已有本地验收记录。']];
    overview.getRange('D22:E22').values=[[
      '本方逐域清理与可核对回执本地软件已验收；老师样本导入和命盘逐字段差异报告仍按对应任务推进。',
      '剩余保留/匿名化软件、正式期限和外部删除分别追踪；命盘差异仍需定位到输入、规则、算法或显示。',
    ]];
    overview.getRange('A22:E22').format.rowHeight=55;
    const title=tasks.getRange('A4').values[0][0];if(!title.includes('25个本地实施阶段'))throw new Error('Legacy stage summary changed.');
    tasks.getRange('A4').values=[[title.replace('25个本地实施阶段','26个本地实施阶段')]];
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
    for(const [index,sheetName,range,suffix] of previews) {
      const blob=await books[index].render({sheetName,range,scale:1,format:'png'});
      await fs.writeFile(path.join(evidence,`${prefix}-进度表-回填后${suffix}.png`),new Uint8Array(await blob.arrayBuffer()));
    }
    for(const output of outputs){await fs.copyFile(output.candidate,output.output);await fs.unlink(output.candidate);delete output.candidate;output.sha256=sha(await fs.readFile(output.output));}
    console.log(JSON.stringify({updated:outputs,stage:26,rowsWithEvidence:67,otherRows:31,statusCounts:{进行中:69,待资料:16,待验收:9,待实施:4}}));
  } else throw new Error('Use inspect, or apply --verified-by-root <receipt> <SHA256> after final gates.');
} catch(error){console.error(error.message);process.exitCode=1;}
