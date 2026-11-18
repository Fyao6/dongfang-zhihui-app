// Narrow candidate builder. Existing workbooks are never overwritten here.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {constants} from 'node:fs';
import {createHash,randomUUID} from 'node:crypto';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
const OUT=import.meta.dirname,ROOT=path.dirname(OUT),runtime='C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies';
const python=path.join(runtime,'python/python.exe'),node=path.join(runtime,'node/bin/node.exe');
const names=['东方智慧APP需求进度表-20261116.xlsx','东方智慧APP优化任务表_依据v1.0_20261112.xlsx'];
const sha=b=>createHash('sha256').update(b).digest('hex'),relative=p=>path.relative(ROOT,p).replaceAll('\\','/');
const args=process.argv.slice(2),mode=args[0]||'describe';
const accepted=mode==='accepted';
const expected={B3:'成长足迹与时间统计',C3:accepted?'本地已验证':'待本轮验证',D3:accepted?'原创东方智慧成长足迹：周、月、年、总、履历5页签，练习与聆听两色柱，完整原资料与详情。按原保存日统计，重复去重、冲突排除、缺失时长不冒充零。Python与本地Cloud各60项全量及6项专项通过。每端24种总览与24种长详情布局，48种布局覆盖计入6项专项。':'参考数据易懂的理念，自主设计周、月、年、总、履历5个页签。练习与聆听两色时间柱，完整原资料与详情可达。按原保存日统计，重复资料去重、冲突排除，缺失时长不冒充零。本轮双端各60+6待验证。',E3:'用户视觉评价、真实手机与跨设备同步仍待验收。',F3:'成长统计-本地验收记录.json'};
if(mode==='describe'){
 if(args.length!==1&&args.length!==0)throw Error('No describe arguments');
 console.log(JSON.stringify({preparedOnly:true,writesOriginalWorkbook:false,scope:'追加需求!B3:F3',expected}));
}else{
 if(!['baseline','prepare','accepted'].includes(mode)||args.length!==(mode==='baseline'?1:accepted?3:2))throw Error('Use baseline, prepare <baseline manifest>, or accepted <pending manifest> <receipt SHA>');
 const id=randomUUID().replaceAll('-',''),temp=await fs.mkdtemp(path.join(os.tmpdir(),'codex-growth-stat-books-'));
 await fs.symlink(path.join(runtime,'node/node_modules'),path.join(temp,'node_modules'),'junction');
 const bundled=createRequire(path.join(temp,'author.cjs')),{FileBlob,SpreadsheetFile}=await import(pathToFileURL(bundled.resolve('@oai/artifact-tool')).href);
 if(mode==='baseline'){
  const books=[];
  for(let i=0;i<names.length;i++){
   const file=path.join(OUT,names[i]),raw=await fs.readFile(file),backup=path.join(OUT,`成长统计-表格原字节-${id}-${i}.xlsx`);
   await fs.copyFile(file,backup,constants.COPYFILE_EXCL);
   const book=await SpreadsheetFile.importXlsx(await FileBlob.load(file)),sheet=book.worksheets.getItem('追加需求');
   if(sheet.getRange('A3').values[0][0]!=='ADD-GROWTH')throw Error('Exact existing ADD-GROWTH row required');
   const preview=path.join(OUT,`成长统计-追加需求-修改前-${id}-${i}.png`);
   await fs.writeFile(preview,new Uint8Array(await(await book.render({sheetName:'追加需求',range:'A1:F4',scale:1,format:'png'})).arrayBuffer()),{flag:'wx'});
   books.push({path:relative(file),sha256:sha(raw),backup:relative(backup),values:sheet.getRange('A1:F4').values,preview:{path:relative(preview),sha256:sha(await fs.readFile(preview)),sheet:'追加需求',range:'A1:F4'}});
  }
  const file=path.join(OUT,`成长统计-表格基线-${id}.json`);await fs.writeFile(file,JSON.stringify({at:new Date().toISOString(),id,books},null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({manifest:relative(file),sha256:sha(await fs.readFile(file)),books:books.map(b=>({path:b.path,sha256:b.sha256,preview:b.preview}))}));
 }else{
  let baselineFile=path.resolve(args[1]),acceptance;
  if(accepted){
   if(path.dirname(baselineFile)!==OUT||!path.basename(baselineFile).startsWith('成长统计-表格待验证候选-'))throw Error('Actual pending candidate required');
   const pending=JSON.parse(await fs.readFile(baselineFile,'utf8'));if(pending.status!=='pending-business-acceptance'||pending.originalsApplied!==false)throw Error('Preserve pending candidate');
   const receipt=path.join(OUT,'成长统计-本地验收记录.json'),raw=await fs.readFile(receipt),data=JSON.parse(raw);
   if(!/^[a-f0-9]{64}$/.test(args[2])||sha(raw)!==args[2]||data.pass!==true||data.totalPassed!==132||data.totalFailed!==0)throw Error('Actual accepted 132/0 receipt required');
   for(const backend of ['Python','Cloud'])if(JSON.stringify(data.perBackend?.[backend])!==JSON.stringify({full:60,special:6,passed:66,failed:0}))throw Error('Actual dual 60+6 acceptance required');
   for(const role of Object.values(data.roles||{}))if(sha(await fs.readFile(path.join(ROOT,role.path)))!==role.sha256||role.failed!==0)throw Error('Accepted report bytes changed');
   acceptance={path:relative(receipt),sha256:args[2],pending:{path:relative(baselineFile),sha256:sha(await fs.readFile(baselineFile))}};
   baselineFile=path.join(ROOT,pending.baseline.path);if(sha(await fs.readFile(baselineFile))!==pending.baseline.sha256)throw Error('Pending baseline changed');
  }
  if(path.dirname(baselineFile)!==OUT||!path.basename(baselineFile).startsWith('成长统计-表格基线-'))throw Error('Owned baseline required');
  const baseline=JSON.parse(await fs.readFile(baselineFile,'utf8')),result={at:new Date().toISOString(),status:accepted?'business-accepted-candidate':'pending-business-acceptance',originalsApplied:false,acceptance,baseline:{path:relative(baselineFile),sha256:sha(await fs.readFile(baselineFile))},books:[]};
  const expectedFile=path.join(OUT,`成长统计-表格预期值-${id}.json`);await fs.writeFile(expectedFile,JSON.stringify(expected,null,2)+'\n',{flag:'wx'});
  const books=[];
  for(const item of baseline.books){const file=path.join(ROOT,item.path),backup=path.join(ROOT,item.backup);if(sha(await fs.readFile(file))!==item.sha256||sha(await fs.readFile(backup))!==item.sha256)throw Error('Exact workbook baseline changed');const book=await SpreadsheetFile.importXlsx(await FileBlob.load(file));if(book.worksheets.getItem('追加需求').getRange('A3').values[0][0]!=='ADD-GROWTH')throw Error('Exact additional row required');books.push(book);}
  const marker='C:/Users/Administrator/.codex/plugins/cache/openai-primary-runtime/spreadsheets/26.1112.11011/skills/spreadsheets/container_tools/mark_artifact_operation_started.mjs';
  // The first workbook edit starts here; exactly one marker covers these two candidate outputs.
  if(!accepted)execFileSync(node,[marker,'--operation-kind','edit','--expected-output-count','2','--output-format','xlsx'],{stdio:'pipe'});
  for(let i=0;i<books.length;i++){
   const book=books[i],sheet=book.worksheets.getItem('追加需求');sheet.getRange('B3:F3').values=[[expected.B3,expected.C3,expected.D3,expected.E3,expected.F3]];book.recalculate();
   const phase=accepted?'已验证':'待验证',candidate=path.join(OUT,`成长统计-追加需求-${phase}候选-${id}-${i}.xlsx`),preview=path.join(OUT,`成长统计-追加需求-${phase}-${id}-${i}.png`),report=path.join(OUT,`成长统计-追加需求-${phase}校验-${id}-${i}.json`);
   await fs.writeFile(preview,new Uint8Array(await(await book.render({sheetName:'追加需求',range:'A1:F4',scale:1,format:'png'})).arrayBuffer()),{flag:'wx'});
   await(await SpreadsheetFile.exportXlsx(book)).save(candidate);
   execFileSync(python,['-B',path.join(OUT,'成长统计-追加需求校验.py'),path.join(ROOT,baseline.books[i].backup),candidate,expectedFile,report],{stdio:'pipe'});
   result.books.push({original:baseline.books[i],candidate:{path:relative(candidate),sha256:sha(await fs.readFile(candidate))},validation:{path:relative(report),sha256:sha(await fs.readFile(report))},visualPreview:{path:relative(preview),sha256:sha(await fs.readFile(preview)),sheet:'追加需求',range:'A1:F4'}});
  }
  const file=path.join(OUT,`成长统计-表格${accepted?'已验证':'待验证'}候选-${id}.json`);await fs.writeFile(file,JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({manifest:relative(file),sha256:sha(await fs.readFile(file)),books:result.books}));
 }
}
