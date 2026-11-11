
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {request}=require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root=path.resolve(__dirname,'..'),base=process.argv[2];
if(!['http://127.0.0.1:8878','https://eastern-wisdom-demo-fuyao.netlify.app'].includes(base))throw Error('Unexpected migration target');
const remote=base.startsWith('https:'),label=remote?'公网':'本地';
const teachers=JSON.parse(fs.readFileSync(path.join(__dirname,'老师分类示例资料.json'),'utf8'));
const ids=new Map(['ziwei','tcm','healing'].flatMap(theme=>['video','audio','practice'].map(format=>['academy-'+theme+'-'+format,({ziwei:'demo-qinghe',tcm:'demo-anran',healing:'demo-zhiwei'})[theme]])));
const sources={tcm:['NCCIH · 中医概览','https://www.nccih.nih.gov/health/traditional-chinese-medicine-what-you-need-to-know'],qigong:['NCCIH · 气功','https://www.nccih.nih.gov/health/qigong-what-you-need-to-know'],ziweiBasis:['iztro · 基础术语','https://www.iztro.com/learn/basis'],ziweiPalace:['iztro · 宫位系统','https://www.iztro.com/learn/palace']};
const clean=item=>Object.fromEntries(Object.entries(item).filter(([k])=>!k.startsWith('_')));
(async()=>{const api=await request.newContext({baseURL:base}),changes=[];try{
const credentials=JSON.parse(fs.readFileSync(path.join(root,'04_研发源码/app/cloud/.env.test'),'utf8'));assert.equal((await api.post('/api/auth/login',{data:credentials})).status(),200);
const previous={at:new Date().toISOString(),base,teachers:(await(await api.get('/api/admin/content/teachers')).json()).items,courses:(await(await api.get('/api/admin/content/courses')).json()).items};
const backup=path.join(__dirname,'老师分类内容迁移备份-'+label+'.json');if(!fs.existsSync(backup))fs.writeFileSync(backup,JSON.stringify(previous,null,2));
async function save(kind,item,status,position){const response=await api.post('/api/admin/content/'+kind,{data:{item:clean(item),status,position}});assert.equal(response.status(),200,kind+': '+await response.text());}
for(const [index,teacher] of teachers.entries()){
const old=previous.teachers.find(x=>x.id===teacher.id);if(old){assert.equal(old.profileType,'demo','Refuse to replace an unrelated real teacher');continue;}
await save('teachers',teacher,'published',index);changes.push({kind:'teachers',item:teacher,previous:null});
}
for(const course of previous.courses){
const teacherId=ids.get(course.id);if(!teacherId||course.teacherId)continue;
const item={...course,teacherId,sources:(course.sources||[]).map(s=>typeof s==='string'?(sources[s]||(()=>{throw Error('Unknown legacy source: '+s)})()):s)};
await save('courses',item,course._status,course._position||0);changes.push({kind:'courses',item,previous:course});
}
const publicContent=(await(await api.get('/api/public')).json()).content;
const counts=teachers.map(t=>({id:t.id,courses:publicContent.courses.filter(c=>c.teacherId===t.id).length}));
fs.writeFileSync(path.join(__dirname,'老师分类内容迁移结果-'+label+'.json'),JSON.stringify({at:new Date().toISOString(),base,pass:true,changed:changes.map(c=>({kind:c.kind,id:c.item.id})),counts},null,2));
console.log(JSON.stringify({pass:true,changed:changes.length,counts}));
}catch(e){
for(const c of changes.reverse()){const prior=c.previous,item=clean(prior||c.item);await api.post('/api/admin/content/'+c.kind,{data:{item,status:prior?prior._status:'archived',position:prior?prior._position:0}}).catch(()=>{});}
throw e;
}finally{await api.dispose();}})().catch(e=>{console.error(e.message);process.exitCode=1});

