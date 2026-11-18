'use strict';
// Four real SQLite groups only; the unchanged fourteen HTTP gates remain separate.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'..'),PREFIX='负责人优化建议-本地可靠性性能复验',sha=b=>crypto.createHash('sha256').update(b).digest('hex');
async function run(expected){
 const authorization=require('./负责人优化建议-本地可靠性修复基线.cjs').verifyAuthorization(expected);
 const python=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'),file=path.join(__dirname,PREFIX+'原生连接组件.py'),before=sha(fs.readFileSync(file)),runId=crypto.randomUUID().replaceAll('-','');
 const report={at:new Date().toISOString(),runId,componentOnly:true,nativeSQLiteOnly:true,actualHttpCovered:false,cloudNativeReuseCovered:false,authorization,componentSource:{path:path.relative(ROOT,file),sha256:before},pythonExecutableSha256:sha(fs.readFileSync(python)),passed:0,pass:false};
 const env={};for(const k of ['SystemRoot','WINDIR','TEMP','TMP'])if(process.env[k])env[k]=process.env[k];env.PATH=path.dirname(process.execPath);env.PYTHONIOENCODING='utf-8';
 const child=spawn(python,['-B',file,'--execute-native-component','--authorization-sha256',expected],{cwd:ROOT,env,windowsHide:true,shell:false,stdio:['ignore','pipe','pipe']});let stdout='',stderr='',bytes=0,startError=null;const hash=crypto.createHash('sha256');
 for(const [stream,kind]of [[child.stdout,'stdout'],[child.stderr,'stderr']])stream.on('data',data=>{bytes+=data.length;hash.update(data);if(bytes<=65536){if(kind==='stdout')stdout+=data;else stderr+=data;}else child.kill();});
 const timer=setTimeout(()=>child.kill(),60000);child.once('error',error=>{startError=error.code||'SPAWN_ERROR';});const code=await new Promise(resolve=>child.once('close',resolve));clearTimeout(timer);
 Object.assign(report,{childExitCode:code,startError,actualChildPid:child.pid||null,outputBytes:bytes,outputSha256:hash.digest('hex'),fixedSyntheticComponentOutput:stdout.slice(-16384),stderr:stderr.slice(-16384)});
 let component;try{component=JSON.parse(stdout.trim().split(/\r?\n/).at(-1));}catch{}
 if(component?.path){const source=path.resolve(ROOT,component.path);assert(path.dirname(source)===__dirname&&path.basename(source).startsWith(PREFIX));assert.equal(sha(fs.readFileSync(source)),component.sha256);report.componentReport={path:component.path,sha256:component.sha256};report.passed=component.passed||0;report.failed=component.failed||0;}
 report.sourceUnchanged=sha(fs.readFileSync(file))===before;report.pass=code===0&&component?.pass===true&&report.passed===4&&report.failed===0&&report.sourceUnchanged;
 const output=path.join(__dirname,PREFIX+'-原生安全启动诊断-'+runId+'.json');fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({pass:report.pass,componentOnly:true,passed:report.passed,failed:report.failed,report:path.relative(ROOT,output),sha256:sha(fs.readFileSync(output)),componentReport:report.componentReport}));return report;
}
module.exports={run,implementationReady:true,scope:'Python native lease safety; not Cloud or HTTP authorization acceptance'};
if(require.main===module){const args=process.argv.slice(2);if(!args.length)console.log(JSON.stringify({status:'prepared-not-run',actualNativeGroups:0,plannedGroups:4,componentOnly:true,nativeSQLiteOnly:true}));else{assert.equal(args.length,1);assert(args[0].startsWith('--authorization-sha256='));run(args[0].split('=')[1]).then(r=>{process.exitCode=r.pass?0:1;}).catch(error=>{console.error(JSON.stringify({pass:false,errorCode:error.code||error.name,componentOnly:true}));process.exitCode=1;});}}
