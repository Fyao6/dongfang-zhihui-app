'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
// The values below are declared synthetic inputs. Limits are proved through the actual HTTP importer.
module.exports=async function sampleImportChecks({h,a,f,api,check,key}){
 const base=f.base,copy=v=>JSON.parse(JSON.stringify(v)),C=p=>f.context(p),tables=['bazi_sample_sets','bazi_sample_versions','bazi_sample_cases'];
 for(const value of f.fixture.privateCanaries||[])h.addPrivateValue(value);
 const counts=async()=>{const s=await f.snapshot(tables);return Object.fromEntries(tables.map(t=>[t,s[t].length]));};
 async function rejected(data,{raw,expected=400,headers={}}={}){const before=await counts();await f.importSet(a.admin,data,{raw,expected,headers});assert.deepEqual(await counts(),before,'Rejected input creates no set, version or case');}
 const cases=n=>Array.from({length:n},(_,i)=>f.case('ordinary-male',{caseId:'cap_'+String(i).padStart(3,'0')}));
 const expectedFields=n=>Object.fromEntries(Array.from({length:n},(_,i)=>['/rawOutput/periods/1/years/'+i+'/age',{state:'value',value:0}]));
 function depth(v){return v&&typeof v==='object'?Math.max(0,...Object.values(v).map(x=>1+depth(x))):0;}
 await check('01 默认仅当前管理员本人可读写，实际实现与二十一源绑定且没有专业验收声明',async()=>{
  await api(a.anonymous,base,undefined,'GET',401);await api(a.user,base,undefined,'GET',403);
  await f.importSet(a.user,f.dataset(),{expected:403});await f.importSet(a.anonymous,f.dataset(),{expected:401});
  const d=(await api(a.admin,base)).data;assert(Array.isArray(d.items));assert.equal(d.next,null);assert.equal(h.report.sourceBinding.verified,true);assert.equal(h.report.sourceBinding.managedInputs,21);
  assert.equal(h.report.coverage.teacherConfirmed,false);assert.equal(h.report.coverage.teacherConfirmedCaseCount,0);assert.equal(h.report.coverage.professionalAgreementRate,null);assert.equal(h.report.coverage.professionalValidation,false);
 });
 await check('02 原UTF8字节SHA与长度真实冻结，空白和键序同义重放不覆盖首份来源',async()=>{
  const d=f.dataset(),raw=Buffer.from(' \n'+JSON.stringify(d,null,2)+'\n\t'),requestId=key('source_bytes'),first=await f.importSet(a.admin,d,{raw,requestId});
  assert.equal(first.duplicate,false);assert.equal(first.item.sourceBytesSha256,f.sha(raw));assert.equal(first.item.sourceByteLength,raw.length);assert.equal(first.item.canonicalSha256,f.sha(f.canonical(d)));assert.equal(first.item.canonicalByteLength,Buffer.byteLength(f.canonical(d)));
  const reordered=Object.fromEntries(Object.entries(d).reverse()),second=await f.importSet(a.admin,reordered,{requestId,raw:Buffer.from(f.canonical(reordered))});assert.deepEqual(second,first,'Same import intent returns the exact original receipt');const newIntent=await f.importSet(a.admin,reordered,{raw:Buffer.from(f.canonical(reordered))});assert.equal(newIntent.duplicate,true);assert.equal(newIntent.item.id,first.item.id);assert.equal(newIntent.item.sourceBytesSha256,first.item.sourceBytesSha256);assert.equal(newIntent.item.sourceByteLength,raw.length);
  h.report.originalByteEvidence={sourceBytesSha256:first.item.sourceBytesSha256,sourceByteLength:raw.length,canonicalSha256:first.item.canonicalSha256,rawAndCanonicalDiffer:first.item.sourceBytesSha256!==first.item.canonicalSha256,originalSourceBytesRetained:false};
 });
 await check('03 set/version及requestId精确幂等，异内容409，新版本独立且旧版本内容不变',async()=>{
  const d=f.dataset(),requestId=key('version_request'),first=await f.importSet(a.admin,d,{requestId}),before=(await api(a.admin,base+'/'+first.item.id)).data;
  const same=await f.importSet(a.admin,d);assert.equal(same.item.id,first.item.id);assert.equal(same.duplicate,true);
  const changed=copy(d);changed.cases[0].label+=' changed';await f.importSet(a.admin,changed,{requestId,expected:409});await f.importSet(a.admin,changed,{expected:409});
  changed.version='v2';const next=await f.importSet(a.admin,changed);assert.notEqual(next.item.id,first.item.id);assert.deepEqual((await api(a.admin,base+'/'+first.item.id)).data,before);
 });
 await check('04 老师来源和证据只作外部未验证声明，伪专业批准字段逐层拒绝',async()=>{
  const c=f.case();c.teacherApproval={claimedReviewer:'SYNTHETIC_UNVERIFIED_REVIEWER',evidenceReference:'owned-fixture-reference',evidenceSha256:'a'.repeat(64),verification:'unverified-external-claim'};const d=f.dataset([c]);d.source.kind='teacher-provided';const imported=await f.importSet(a.admin,d);assert.equal(imported.item.teacherConfirmed,false);
  const created=await f.createRun(a.admin,imported.item,{caseIds:[c.caseId]});assert.equal(created.run.teacherConfirmed,false);assert.equal(created.run.professionalValidation,false);assert.equal(created.run.counts.teacherAgreementRate,null);
  for(const field of ['teacherConfirmed','professionalValidation','teacherConfirmedCaseCount']){const bad=copy(d);bad[field]=true;await rejected(bad);}const bad=copy(d);bad.cases[0].teacherApproval.verification='approved';await rejected(bad);
  const run=await f.process(a.admin,created.run),x=await f.exportCase(a.admin,run.run,c.caseId);assert.equal(x.report.teacherConfirmed,false);assert.equal(x.report.professionalValidation,false);assert.equal(x.report.counts.teacherAgreementRate,null);
 });
 await check('05 HTTP原文UTF8/BOM/MIME与精确2MiB上限，拒绝后没有半份版本',async()=>{
  const d=f.dataset(),raw=Buffer.from(JSON.stringify(d)),exact=Buffer.concat([raw,Buffer.alloc(2*1024*1024-raw.length,32)]),ok=await f.importSet(a.admin,d,{raw:exact});assert.equal(ok.item.sourceByteLength,2097152);assert.equal(ok.item.sourceBytesSha256,f.sha(exact));
  await rejected(f.dataset(),{raw:Buffer.concat([exact,Buffer.from(' ')]),expected:413});await rejected(f.dataset(),{raw:Buffer.concat([Buffer.from([0xef,0xbb,0xbf]),raw])});await rejected(f.dataset(),{raw:Buffer.concat([raw,Buffer.from([0xff])])});await rejected(d,{raw,expected:415,headers:{'Content-Type':'text/plain'}});
  h.report.importByteLimits={httpMaxBytes:2097152,exactBoundaryAccepted:true,oneByteOverRejected:true,invalidUtf8Rejected:true,bomRejected:true,nodeIpcLimitIsSeparate:true};
 });
 await check('06 decoded重复键、Unicode转义重复及原型污染和非JSON数字拒绝',async()=>{
  const d=f.dataset(),text=JSON.stringify(d),raws=[text.replace('"schema":1','"schema":1,"schema":1'),text.replace('"schema":1','"schema":1,"sch\\u0065ma":1'),text.replace('"schema":1','"schema":1,"__proto__":{}'),text.replace('"schema":1','"schema":1,"constructor":{}'),text.replace('"schema":1','"schema":1,"prototype":{}'),text.replace('"schema":1','"schema":NaN'),text.replace('"schema":1','"schema":Infinity')];
  for(const raw of raws)await rejected(d,{raw:Buffer.from(raw)});assert.equal({}.polluted,undefined);h.report.decodedKeyProtection={duplicateDecodedKeyRejected:true,rawEscapesPreservedInRequest:true,prototypeKeysRejected:true,nonJsonNumbersRejected:true};
 });
 await check('07 exact DTO与ID约束，未知字段/缺字段/重复caseId及无效request header拒绝',async()=>{
  const d=f.dataset();for(const mutate of [x=>x.extra=true,x=>delete x.source,x=>x.source.extra=true,x=>x.cases[0].extra=true,x=>x.cases[0].input.region='client-place',x=>x.cases[0].context.extra=true,x=>x.cases[0].options.extra=true,x=>x.cases[0].caseId='bad/id',x=>x.cases.push(copy(x.cases[0]))]){const x=copy(d);mutate(x);await rejected(x);}
  await rejected(d,{headers:{'X-EW-Request-ID':'invalid/id'}});await rejected(d,{headers:{'X-EW-Request-ID':'x'.repeat(101)}});
 });
 await check('08 一百例可导入与101例拒绝，每例canonical精确256KiB独立于HTTP上限',async()=>{
  const hundred=f.dataset(cases(100)),accepted=await f.importSet(a.admin,hundred);assert.equal(accepted.item.caseCount,100);await rejected(f.dataset(cases(101)));
  const c=f.case();c.expected=expectedFields(2000);const target=262144,initial=Buffer.byteLength(f.canonical(c));assert(initial<target);let remaining=target-initial;for(const row of Object.values(c.expected)){if(!remaining)break;const increase=Math.min(remaining,8000);row.value='x'.repeat(increase-1);remaining-=increase;}assert.equal(remaining,0);assert.equal(Buffer.byteLength(f.canonical(c)),target);
  const exact=f.dataset([c]),v=await f.importSet(a.admin,exact);assert.equal(v.item.caseCount,1);const over=copy(c);Object.values(over.expected)[0].value+='x';assert.equal(Buffer.byteLength(f.canonical(over)),target+1);await rejected(f.dataset([over]),{expected:413});h.report.caseLimits={maxCases:100,maxCaseCanonicalBytes:262144,exactCaseBoundaryAccepted:true,oneByteOverRejected:true};
 });
 await check('09 JSON深度32、2000 provided字段与每值8192字节边界均实际HTTP验证',async()=>{
  const c=f.case();c.expected=expectedFields(2000);await f.importSet(a.admin,f.dataset([c]));const tooMany=copy(c);tooMany.expected['/rawOutput/periods/1/years/2000/age']={state:'value',value:0};await rejected(f.dataset([tooMany]));
  const value=f.case();value.expected={'/originalInput/name':{state:'value',value:'x'.repeat(8190)}};assert.equal(Buffer.byteLength(f.canonical(Object.values(value.expected)[0].value)),8192);await f.importSet(a.admin,f.dataset([value]));Object.values(value.expected)[0].value+='x';await rejected(f.dataset([value]),{expected:413});
  const nested=f.dataset();nested.cases[0].expected={'/originalInput/name':{state:'value',value:null}};const row=nested.cases[0].expected['/originalInput/name'];while(depth(nested)<32)row.value=[row.value];assert.equal(depth(nested),32);await f.importSet(a.admin,nested);row.value=[row.value];assert.equal(depth(nested),33);await rejected(nested);
  h.report.structuralLimits={maximumDepth:32,maximumExpectedFields:2000,maximumExpectedValueBytes:8192,allPositiveAndNegativeBoundariesThroughHttp:true};
 });
 await check('10 私有出生只在本人样本，未进初始seed/外发fixture/普通用户导出或其他账号',async()=>{
  const d=f.dataset(),v=(await f.importSet(a.admin,d)).item,read=(await api(a.admin,base+'/'+v.id)).data;assert.equal(read.header.source.kind,'synthetic');await api(a.other,base+'/'+v.id,undefined,'GET',403);
  const provider=await h.mockCalls();assert.equal(provider.length,0,'Sample import and computation never contact AI');const seed=fs.readFileSync(path.join(h.ROOT,'04_研发源码/app/r4/backend/initial-content.json'),'utf8');for(const value of f.fixture.privateCanaries||[])assert(!seed.includes(value));
  const ordinary=await f.ownExport(a.user);assert(!JSON.stringify(ordinary).includes(d.cases[0].input.name));assert(!JSON.stringify(ordinary).includes(v.id));h.report.privateBirthBoundary={syntheticDataOnly:true,sampleProviderCalls:0,productionSeedUnchanged:true,ordinaryOwnerCannotExportAnotherOwnerSample:true};
 });
 await check('11 分页保留原case顺序与本人归属，外国版本和游标不能读取私有记录',async()=>{
  const p=await f.admin('import_owner'),d=f.dataset(cases(51)),v=(await f.importSet(p,d)).item,one=(await api(C(p),base+'/'+v.id)).data;assert.equal(one.cases.length,50);assert.deepEqual(one.header.caseIds,d.cases.map(c=>c.caseId));assert(one.next);const two=(await api(C(p),base+'/'+v.id+'?before='+encodeURIComponent(one.next))).data;assert.equal(two.cases.length,1);assert.equal(two.next,null);const paged=[...one.cases,...two.cases];assert.deepEqual(paged.map(c=>c.caseId),d.cases.map(c=>c.caseId).sort().reverse());assert.deepEqual([...paged].sort((a,b)=>a.ordinal-b.ordinal).map(c=>c.caseId),d.cases.map(c=>c.caseId));
  await api(a.admin,base+'/'+v.id,undefined,'GET',404);await api(C(p),base+'/'+v.id+'?before=foreign_case',undefined,'GET',400);const foreign=(await api(a.admin,base)).data;assert(!foreign.items.some(r=>r.id===v.id));
 });
 await check('12 公历/时间/性别/上下文校验拒绝非法输入，未知时间合法但不补时辰',async()=>{
  for(const patch of [{date:'1900-02-29'},{date:'2024-02-30'},{date:'1899-12-31'},{date:'2100-01-01'},{time:'24:00'},{time:'12:00:00'},{sex:'unknown'},{timezone:'Asia/Shanghai'},{latitude:30}]){const c=f.case();Object.assign(c.input,patch);await rejected(f.dataset([c]));}
  const unknown=f.case('unknown-time');const v=await f.importSet(a.admin,f.dataset([unknown]));assert.equal(v.item.caseCount,1);const bad=f.case();bad.context.mode='shared-current';bad.context.archivedUtc='1990-01-01T00:00:00Z';await rejected(f.dataset([bad]));const solar=f.case();solar.options.trueSolarTime=true;await rejected(f.dataset([solar]));
 });
};
