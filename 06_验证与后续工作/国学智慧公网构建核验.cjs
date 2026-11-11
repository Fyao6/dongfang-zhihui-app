const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const root=path.resolve(__dirname,'..'),cloud=path.join(root,'04_研发源码/app/cloud');
const norm=s=>s.replace(/\r\n/g,'\n').replace(/\n<!-- This site is hosted on Netlify\.[\s\S]*?-->/g,'');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
(async()=>{const checks=[];for(const origin of ['https://eastern-wisdom-demo-fuyao.netlify.app'])for(const [route,file]of [['/experience','experience.html'],['/creator','creator.html'],['/admin','admin.html'],['/','experience.html']]){
 const response=await fetch(origin+route+'?chartBuildCheck='+Date.now()),served=norm(await response.text()),expected=norm(fs.readFileSync(path.join(cloud,'generated',file),'utf8'));
 const check={origin,route,status:response.status,generatedMatch:served===expected,servedNormalizedSha256:hash(served),expectedNormalizedSha256:hash(expected)};checks.push(check);console.log(JSON.stringify(check));
 }
 const report={at:new Date().toISOString(),pass:checks.every(c=>c.status===200&&c.generatedMatch),checks,netlifyDeployId:'6aec43f8ba067c3e66b1e1e4',sourceCommit:'25d2515330b4e1ca8bf5ce0eec485a616f4ca235',sitesVersion:12,localAppSha256:hash(fs.readFileSync(path.join(root,'03_当前APP/东方智慧-首页体验R4.html')))};
 report.scope='Delivered Netlify public origin. The delivered Netlify origin is verified; direct Sites-origin bot-protection behavior is outside this check.';
 const reportFile=path.join(__dirname,'国学智慧公网构建一致性.json');let runs=[];if(fs.existsSync(reportFile)){const old=JSON.parse(fs.readFileSync(reportFile));runs=old.runs||[old];}runs.push(report);fs.writeFileSync(reportFile,JSON.stringify({latest:report,runs},null,2)+'\n');assert(report.pass,'Every delivered public page must match the published generated source');
})().catch(e=>{console.error(e.message);process.exitCode=1;});
