from pathlib import Path
import re
p=Path(__file__).resolve().parent
s=(p/'全量回归.cjs').read_text(encoding='utf-8')
a=s.index('async function start(){');b=s.index('browser=await chromium.launch',a)
s=s[:a]+"async function start(){base='http://127.0.0.1:8877';"+s[b:]
a=s.index('function cleanDb(){');b=s.index('\n',a);s=s[:a]+'function cleanDb(){}'+s[b:]
s=s.replace("'本轮全量回归结果.json'","'公网适配全量回归结果.json'").replace("'前后端接口实测证据.json'","'公网适配接口实测证据.json'")
s=s.replace("const includeAdmin=process.argv.includes('--admin');","const includeAdmin=true;const cloudCred=JSON.parse(fs.readFileSync(path.join(source,fs.existsSync(path.join(source,'../cloud/.env.local-test'))?'../cloud/.env.local-test':'../cloud/.env.test'),'utf8'));")
s=s.replace("call(admin,'auth/setup',{username:'reg_admin',password:'Regression_Only_2026',name:'回归管理员'})","call(admin,'auth/login',cloudCred)")
old="await step('并发 跨天 持久化及AI适配单测',async()=>{execFileSync(python,['-B',path.join(__dirname,'后台单元回归.py')],{cwd:root,windowsHide:true,stdio:'pipe'});});"
new="await step('云端并发计时与时区切换',async()=>{const values=await Promise.all(Array.from({length:8},()=>call(user,'time-bank/heartbeat',{zone:'Asia/Shanghai'})));assert(values.every(v=>v.r.status()===200));assert.equal(values[0].d.runs.filter(r=>r.end===null).length,1);const zone=await call(user,'time-bank/heartbeat',{zone:'America/New_York'});assert.equal(zone.d.zone,'America/New_York');assert.equal(zone.d.runs.filter(r=>r.end===null).length,1);await call(user,'time-bank/heartbeat',{zone:'Asia/Shanghai'});});"
assert old in s;s=s.replace(old,new)
s=re.sub(r' execFileSync\(python,\[\x27-c\x27,.*?\{windowsHide:true\}\);'," for(let i=0;i<520;i++){const d=new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10);const r=await call(user,'records',{kind:'mind',date:d,data:{private:'not-in-admin-export'}});assert.equal(r.r.status(),200);}",s)
s=re.sub(r"'([^']+\.png)'",lambda m:"'公网-"+m[1]+"'" if '/' not in m[1] else m[0],s)
s=s.replace("module:moduleName,coverage:","module:moduleName,cloudWorker:true,coverage:")
s=s.replace("let history=[];", "report.cloudBuildHashes=Object.fromEntries(['generated/experience.html','generated/admin.html','generated/review.html','lib/eastern-api.ts','worker/index.ts','dist/server/index.js'].map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(source,'../cloud',name))).digest('hex')]));let history=[];")
(p/'公网适配全量回归.cjs').write_text(s,encoding='utf-8')
print('Prepared cloud regression using full existing UI and API cases; no production database access.')
