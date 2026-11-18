'use strict';
// Fixed failed-snapshot diagnosis only; default invocation never creates a state.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud'),PREFIX='负责人优化建议-本地可靠性恢复';
const FAILED='d399983bcf4f4a66aaf1e26a77311767';
const REPORT=path.join(__dirname,PREFIX+'-'+FAILED+'-组件结果.json');
const REPORT_SHA='079233a7a0ed2dacd2c43c6cbdb0dd79db0f07b6295efb262a0c0f89635ae980';
const REPAIR_SHA='06e3519db0e08a94c10795e9b59b620b4a4289737c87ea09bb2157d0f1a00b5b';
const AUTH_SHA='1f8b83fa08f0d74dee7d1a1644e023f57b64263410b08fecc2ab202ef7f72edb';
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const relative=p=>path.relative(ROOT,p).replaceAll('\\','/');
function readChecked(entry){const p=path.resolve(ROOT,entry.path);assert(p.startsWith(ROOT+path.sep)&&fs.statSync(p).isFile());assert.equal(sha(fs.readFileSync(p)),entry.sha256);return JSON.parse(fs.readFileSync(p,'utf8'));}
function classify(text,known){
 const flags={syntaxError:/syntax error/i.test(text),incompleteInput:/incomplete input/i.test(text),foreignKey:/foreign key constraint/i.test(text),checkConstraint:/CHECK constraint/i.test(text),uniqueConstraint:/UNIQUE constraint/i.test(text),notAuthorized:/not authorized|authorization denied/i.test(text),missingTable:/no such table/i.test(text),tooManyStatements:/too many (?:statements|queries)/i.test(text),statementTooLong:/statement too (?:large|long)|SQLITE_TOOBIG/i.test(text),invalidOption:/unknown argument|unknown option|unrecognized argument/i.test(text),missingEnvironment:/environment variable|undefined.*path|path.*undefined/i.test(text)};
 const names=[...known].filter(n=>new RegExp('(^|[^A-Za-z0-9_])'+n.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'([^A-Za-z0-9_]|$)').test(text));
 const codes=[...new Set(text.match(/\b(?:SQLITE_[A-Z_]+|D1_[A-Z_]+|ERR_[A-Z_]+|ENOENT|EACCES|EPERM)\b/g)||[])];
 const ddlKinds=[...new Set((text.match(/\b(?:CREATE TABLE|CREATE TRIGGER|CREATE INDEX|ALTER TABLE|PRAGMA|INSERT INTO)\b/gi)||[]).map(s=>s.toUpperCase()))];
 return {category:flags.syntaxError?'native_sql_syntax_error':flags.incompleteInput?'native_sql_incomplete_input':Object.keys(flags).find(k=>flags[k])||'unclassified_native_cli_failure',flags,errorCodes:codes,schemaTableNames:names,errorReferencedDdlKinds:ddlKinds,rawTextPersisted:false,insertValuesPersisted:false};
}
function env(){const e={};for(const k of ['SystemRoot','WINDIR','TEMP','TMP','COMSPEC'])if(process.env[k])e[k]=process.env[k];e.PATH=path.dirname(process.execPath);e.WRANGLER_SEND_METRICS='false';e.CI='1';return e;}
async function main(){
 assert.deepEqual(process.argv.slice(2),['--probe-failed-owned-snapshot']);
 const repair=require('./负责人优化建议-本地可靠性修复基线.cjs').verifyRepairProof(REPAIR_SHA,AUTH_SHA);
 assert.equal(sha(fs.readFileSync(REPORT)),REPORT_SHA);const failed=JSON.parse(fs.readFileSync(REPORT,'utf8'));
 assert.equal(failed.runId,FAILED);assert.equal(failed.localDrillPassed,false);assert.equal(failed.failed,1);
 const manifest=readChecked(failed.labManifest),snapEntry=failed.artifacts.find(e=>path.basename(e.path).includes('-d1-snapshot-'));assert(snapEntry);
 const snapshot=readChecked(snapEntry),sql=path.resolve(ROOT,snapshot.sqlPath);
 assert.equal(path.dirname(sql),__dirname);assert.equal(path.basename(sql),PREFIX+'-'+FAILED+'-snapshot.sql');assert.equal(sha(fs.readFileSync(sql)),snapshot.sqlSha256);
 const id=crypto.randomUUID().replaceAll('-',''),state=path.join(CLOUD,'.wrangler','local-reliability-import-debug-'+id);
 const config=path.join(__dirname,PREFIX+'-D1导入诊断-'+id+'-wrangler.json'),output=path.join(__dirname,PREFIX+'-D1导入诊断-'+id+'.json');
 assert(!fs.existsSync(state)&&!fs.existsSync(config)&&!fs.existsSync(output));
 fs.writeFileSync(config,JSON.stringify({name:'local-reliability-import-debug-'+id,compatibility_date:'2026-05-15',d1_databases:[{binding:'DB',database_name:'local-reliability-debug-'+id,database_id:manifest.core.d1DatabaseId}]})+'\n',{flag:'wx'});
 const cli=path.join(CLOUD,'node_modules/wrangler/bin/wrangler.js'),argv=[cli,'d1','execute','DB','--local','--persist-to',state,'--config',config,'--file',sql,'--yes'];
 assert(!argv.includes('--remote'));const start=performance.now();
 const outcome=await new Promise(resolve=>{const child=spawn(process.execPath,argv,{cwd:ROOT,shell:false,windowsHide:true,env:env(),stdio:['ignore','pipe','pipe']});let bytes=0,parts=[],digest=crypto.createHash('sha256'),timedOut=false,startFailure=false;
   for(const s of [child.stdout,child.stderr])s.on('data',b=>{bytes+=b.length;digest.update(b);if(bytes<=2097152)parts.push(b);});
   const timer=setTimeout(()=>{timedOut=true;child.kill();},120000);child.once('error',()=>{startFailure=true;});
   child.once('close',(code,signal)=>{clearTimeout(timer);const text=Buffer.concat(parts).toString('utf8');resolve({childPid:child.pid||null,childExitCode:code,signal,timedOut,startFailure,logBytes:bytes,logSha256:digest.digest('hex'),retainedTextLimitBytes:2097152,diagnosis:classify(text,Object.keys(snapshot.facts.tables))});});
 });
 const report={schemaVersion:1,kind:'actual-native-d1-import-diagnosis',at:new Date().toISOString(),runId:id,componentOnly:true,formalAcceptance:false,productionEnabled:false,restoredApiClaimed:false,r2RecoveryClaimed:false,failedSourceReport:{path:relative(REPORT),sha256:REPORT_SHA},repairProof:{path:repair.repairProof.path,sha256:REPAIR_SHA},authorization:{path:repair.authorization.path,sha256:AUTH_SHA},source:{path:relative(__filename),sha256:sha(fs.readFileSync(__filename))},sql:{path:relative(sql),sha256:snapshot.sqlSha256,bytes:fs.statSync(sql).size,originalUnchanged:sha(fs.readFileSync(sql))===snapshot.sqlSha256},ownedState:relative(state),ownedConfig:{path:relative(config),sha256:sha(fs.readFileSync(config))},nativeCli:{path:relative(cli),sha256:sha(fs.readFileSync(cli))},outcome,elapsedMs:performance.now()-start,rawStdoutOrStderrPersisted:false};
 fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({path:relative(output),sha256:sha(fs.readFileSync(output)),outcome,elapsedMs:report.elapsedMs}));
}
if(require.main===module){if(process.argv.length===2)console.log(JSON.stringify({status:'prepared-not-run',startsService:false,restoresDatabase:false}));else main().catch(error=>{console.error(JSON.stringify({pass:false,errorCode:error.code||error.name,rawErrorSuppressed:true}));process.exitCode=1;});}
