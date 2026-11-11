const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const root=path.resolve(__dirname,'..'),cloud=path.join(root,'04_研发源码/app/cloud');
const norm=s=>s.replace(/\r\n/g,'\n').replace(/\n<!-- This site is hosted on Netlify\.[\s\S]*?-->/g,'');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
(async()=>{const checks=[];for(const origin of ['https://eastern-wisdom-demo-fuyao.netlify.app'])for(const [route,file]of [['/experience','experience.html'],['/creator','creator.html'],['/admin','admin.html'],['/','experience.html']]){
 const response=await fetch(origin+route+'?chartBuildCheck='+Date.now()),served=norm(await response.text()),expected=norm(fs.readFileSync(path.join(cloud,'generated',file),'utf8'));
 const check={origin,route,status:response.status,generatedMatch:served===expected,servedNormalizedSha256:hash(served),expectedNormalizedSha256:hash(expected)};checks.push(check);console.log(JSON.stringify(check));
 }
 const report={at:new Date().toISOString(),pass:checks.every(c=>c.status===200&&c.generatedMatch),checks,netlifyDeployId:'6aebeb5eeed75b3267ebce2c',sourceCommit:'155f0ce8908681d07faf6c6b9e9ae5d7dc8732c9',sitesVersion:11,localAppSha256:hash(fs.readFileSync(path.join(root,'03_当前APP/东方智慧-首页体验R4.html')))};
 report.scope='Delivered Netlify public origin. Direct Sites-origin checks in the first historical run returned the Cloudflare bot-protection 403 page; this does not certify direct Sites-origin access.';
 const reportFile=path.join(__dirname,'三套实际排盘公网构建一致性.json');let runs=[];if(fs.existsSync(reportFile)){const old=JSON.parse(fs.readFileSync(reportFile));runs=old.runs||[old];}runs.push(report);fs.writeFileSync(reportFile,JSON.stringify({latest:report,runs},null,2)+'\n');assert(report.pass,'Every delivered public page must match the published generated source');
})().catch(e=>{console.error(e.message);process.exitCode=1;});
