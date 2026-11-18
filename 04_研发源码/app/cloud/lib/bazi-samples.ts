// Private comparisons; no client actual-output input, DOM or teacher validation claim.
import schema from '../generated/bazi-samples-schema.sql?raw';
import experience from '../generated/experience.html?raw';
import descriptor from '../generated/bazi-sample-server-manifest.json';
import factoryText from '../../r4/bazi-sample-engine.js?raw';
import vendorText from '../../r4/vendor/lunar-1.7.7.js?raw';
// UMD files are shared byte-for-byte with the actual APP and managed Node worker.
// @ts-ignore CommonJS UMD adapter.
import Factory from '../../r4/bazi-sample-engine.js';
// @ts-ignore Bundled, pinned upstream CommonJS UMD vendor.
import lunar from '../../r4/vendor/lunar-1.7.7.js';
const J=(value:any):string=>engine.canonical(value),uuid=()=>crypto.randomUUID();
const enc=new TextEncoder(),NOW="(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))";
const sha=async(value:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',enc.encode(value))),x=>x.toString(16).padStart(2,'0')).join('');
const engine=Factory.createEngine({lunar,sha256:sha});
const COUNTS={equal:0,different:0,notCovered:0,notApplicable:0,blocked:0,provided:0,total:0};
export const BAZI_SAMPLE_TABLES=['owner_state','sets','versions','cases','runs','workitems','results','raw_chunks','field_results','reviews','operations','erase_guards'].map(s=>'bazi_sample_'+s);
export const SAMPLE_PRIVACY_QUERIES:Record<string,string>={
 baziSampleSets:'SELECT id,set_key,title,created,updated FROM bazi_sample_sets WHERE owner=?',
 baziSampleVersions:'SELECT id,set_id,version_key,source_sha256,source_bytes,canonical_sha256,canonical_bytes,case_order,data,created,erased_at FROM bazi_sample_versions WHERE owner=?',
 baziSampleCases:'SELECT version_id,case_id,ordinal,data,canonical_sha256,canonical_bytes,created FROM bazi_sample_cases WHERE owner=?',
 baziSampleRuns:'SELECT id,version_id,request_id,case_ids,manifest_data,manifest_hash,state,version,total,processed,succeeded,failed,blocked,counts,created,updated,erased_at FROM bazi_sample_runs WHERE owner=?',
 baziSampleResults:'SELECT id,run_id,case_id,status,error_code,data,raw_index,created FROM bazi_sample_results WHERE owner=?',
 baziSampleRawChunks:'SELECT id,result_id,section,period_index,chunk_index,data,sha256,byte_length,created FROM bazi_sample_raw_chunks WHERE owner=?',
 baziSampleFieldResults:'SELECT id,result_id,path,data,created FROM bazi_sample_field_results WHERE owner=?',
 baziSampleReviews:'SELECT id,result_id,field_id,category,evidence,note,retest_run_id,created FROM bazi_sample_reviews WHERE owner=?',
 baziSampleOwnerState:'SELECT epoch,updated FROM bazi_sample_owner_state WHERE owner=?'
};
export function redactSampleNames(value:any){
 const data=JSON.parse(JSON.stringify(value)),paths:string[]=[];
 const field=(f:any,path:string)=>{if(['/originalInput/name','/normalizedInput/birth/name'].includes(f?.path))for(const k of ['expected','actual'])if(k in f){f[k]=null;paths.push(path+'/'+k);}};
 const expectation=(e:any,path:string)=>{if(!e||typeof e!=='object')return;for(const k of ['/originalInput/name','/normalizedInput/birth/name'])if(e[k]&&'value' in e[k]){e[k].value=null;paths.push(path+'/'+k+'/value');}};
 for(const [obj,path] of [[data,''],[data.sampleCase,'/sampleCase']] as any[])if(obj){if(obj.input&&'name' in obj.input){delete obj.input.name;paths.push(path+'/input/name');}expectation(obj.expected,path+'/expected');}
 const report=data.report||data,stages=report.stages||{};for(const [obj,path] of [[stages.originalInput,'/stages/originalInput/name'],[stages.normalizedInput?.birth,'/stages/normalizedInput/birth/name']] as any[])if(obj&&'name' in obj){delete obj.name;paths.push(path);}
 expectation(report.expectations,'/expectations');(report.fieldResults||[]).forEach((f:any,i:number)=>field(f,'/fieldResults/'+i));field(data,'');return {data,paths};
}
export function samplePrivacyRedaction(serverData:any,includeNames=false){if(!includeNames)for(const key of ['baziSampleCases','baziSampleResults','baziSampleFieldResults'])for(const row of serverData[key]||[])row.data=J(redactSampleNames(JSON.parse(row.data)).data);serverData.baziSampleExportPrivacy={includesPrivateNames:includeNames,knownNameFieldsRedacted:!includeNames,freeTextAnonymized:false,originalSourceBytesAvailable:false};}
export class BaziSampleError extends Error{constructor(public status:number,public code:string){super(code);}}
const fail=(s:number,c:string):never=>{throw new BaziSampleError(s,c);};
export async function initBaziSamples(a:any){if(!await a.one("SELECT 1 FROM settings WHERE key='bazi_samples_schema_v1'")){await a.db.batch(schema.split('--> statement-breakpoint').filter(s=>s.trim()).map(s=>a.stmt(s)));await a.run("INSERT OR IGNORE INTO settings VALUES('bazi_samples_schema_v1','true')");}}
export function sampleEraseStatement(a:any,owner:string,source:string,receiptId:string,stamp:number){return a.stmt('INSERT INTO bazi_sample_erase_guards SELECT ?,?,coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=?),1),?,?,? WHERE NOT EXISTS(SELECT 1 FROM bazi_sample_operations WHERE owner=? AND kind=\'erase\' AND request_id=?)',uuid(),owner,owner,source,receiptId,stamp,owner,receiptId);}
const versionItem=(r:any)=>{const d=JSON.parse(r.data);return {id:r.id,setId:r.set_id,setKey:d.setId||'',version:d.version||'',title:d.title||'',caseCount:JSON.parse(r.case_order).length,sourceBytesSha256:r.source_sha256,sourceByteLength:r.source_bytes,canonicalSha256:r.canonical_sha256,canonicalByteLength:r.canonical_bytes,created:r.created,erased:!!r.erased_at,teacherConfirmed:false};};
const runItem=(r:any)=>({id:r.id,setVersionId:r.version_id,state:r.state,version:r.version,total:r.total,processed:r.processed,succeeded:r.succeeded,failed:r.failed,blocked:r.blocked,manifestHash:r.manifest_hash,manifest:JSON.parse(r.manifest_data),counts:{...JSON.parse(r.counts),teacherAgreementRate:null},created:r.created,updated:r.updated,teacherConfirmed:false,professionalValidation:false});
function split(text:string){const out:string[]=[];let part='',length=0;for(const char of text){const n=enc.encode(char).length;if(length+n>65536){out.push(part);part='';length=0;}part+=char;length+=n;}out.push(part);return out;}
export class BaziSamples{
 owner:string;
 constructor(public a:any){this.owner=a.user?.id||'';}
 clock(){return Date.now();}
 async live(){const r=await this.a.one('SELECT u.role FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.id=? AND s.token=? AND s.expires>'+NOW+" AND NOT EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=u.id AND status='closed')",this.owner,await sha(this.a.token||''));if(!r)fail(401,'auth_required');if(r.role!=='admin')fail(403,'admin_required');}
 async readBytes(limit:number){const reader=this.a.request.body?.getReader();if(!reader)fail(400,'invalid_length');const chunks:Uint8Array[]=[];let size=0;try{for(;;){const result=await reader!.read();if(result.done)break;size+=result.value.byteLength;if(size>limit){await reader!.cancel();fail(413,'request_too_large');}chunks.push(result.value);}}finally{reader!.releaseLock();}if(!size)fail(400,'invalid_length');const bytes=new Uint8Array(size);let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.length;}return bytes;}
 key(v:any){if(typeof v!=='string'||! /^[A-Za-z0-9:_-]{1,100}$/.test(v))fail(400,'invalid_request_id');return v as string;}
 async epoch(){return (await this.a.one('SELECT epoch FROM bazi_sample_owner_state WHERE owner=?',this.owner))?.epoch||1;}
 async manifest(){
  const d:any=descriptor,source=d.sourceManifest;
  if(d.implementationReady!==true||d.sourceBindingVerified!==true||source?.implementationReady!==true||!source.sourceHashes)fail(503,'implementation_not_ready');
  const hashes=source.sourceHashes;
  const core={...source};delete core.manifestSha256;if(await sha(J(core))!==source.manifestSha256||d.sourceManifestSha256!==source.manifestSha256)fail(503,'implementation_not_ready');
  const find=(suffix:string)=>Object.entries(hashes).find(([k])=>k.endsWith(suffix))?.[1];
  if(find('/bazi-sample-engine.js')!==await sha(factoryText)||find('/vendor/lunar-1.7.7.js')!==await sha(vendorText)||d.appSha256!==await sha(experience)||!experience.includes('name="ew-bazi-sample-source" content="'+d.sourceManifestSha256+'"'))fail(503,'implementation_not_ready');
  return {engine:Factory.ENGINE,adapterVersion:Factory.ADAPTER_VERSION,ruleVersion:Factory.RULE_VERSION,annotationRulesVersion:'eastern-bazi-annotations-2',manifest:source,sourceHashes:hashes,runtime:{node:null,icu:null,tz:null,unicode:null,backend:'cloud'},servedAppSha256:d.appSha256,sourceManifestSha256:d.sourceManifestSha256,sourceBindingVerified:true,implementationReady:true,teacherConfirmed:false,professionalValidation:false};
 }
 async processingManifest(){try{return await this.manifest();}catch(e){if(e instanceof BaziSampleError&&e.code==='implementation_not_ready')fail(409,'implementation_changed');throw e;}}
 async guard(proof:any){return this.a.stmt('INSERT INTO bazi_sample_operations VALUES(?,?,?,?,?,?,?)',uuid(),this.owner,uuid(),'guard','',J({...proof,sessionHash:await sha(this.a.token||'')}),this.clock());}
 async body(keys:string[],optional:string[]=[]){
  const content=this.a.request.headers.get('content-type')||'';if(!/^application\/json(?:\s*;|$)/i.test(content))fail(415,'json_required');
  const bytes=await this.readBytes(262144);
  let text;try{text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);}catch{fail(400,'invalid_utf8');}
  const d=engine.strictParse(text!,262144);if(!d||Array.isArray(d)||typeof d!=='object'||keys.some(k=>!(k in d))||Object.keys(d).some(k=>!keys.includes(k)&&!optional.includes(k)))fail(400,'invalid_fields');return d;
 }
 async owned(table:string,id:string){const r=await this.a.one('SELECT * FROM '+table+' WHERE id=? AND owner=?',id,this.owner);if(!r)fail(404,'sample_not_found');if(r.erased_at)fail(410,'sample_erased');return r;}
 async operation(kind:string,key:string,fp:string){const r=await this.a.one('SELECT * FROM bazi_sample_operations WHERE owner=? AND kind=? AND request_id=?',this.owner,kind,key);if(r&&r.intent_fingerprint!==fp)fail(409,'request_conflict');if(r&&r.response_data==='{}')fail(410,'sample_erased');return r?JSON.parse(r.response_data):null;}
 op(kind:string,key:string,fp:string,response:any){return this.a.stmt('INSERT INTO bazi_sample_operations VALUES(?,?,?,?,?,?,?)',uuid(),this.owner,key,kind,fp,J(response),this.clock());}
 async page(table:string,where:string,args:any[],before:string,order='id'){
  if(before){if(!await this.a.one('SELECT 1 FROM '+table+' WHERE '+where+' AND '+order+'=?',...args,before))fail(400,'invalid_cursor');where+=' AND '+order+'<?';args=[...args,before];}
  const rows=await this.a.all('SELECT * FROM '+table+' WHERE '+where+' ORDER BY '+order+' DESC LIMIT 51',...args);return {rows:rows.slice(0,50),next:rows.length>50?rows[49][order]:null};
 }
 async importDataset(){
  const key=this.key(this.a.request.headers.get('X-EW-Request-ID')),epoch=await this.epoch();
  if(!/^application\/json(?:\s*;|$)/i.test(this.a.request.headers.get('content-type')||''))fail(415,'json_required');
  const bytes=await this.readBytes(2097152);
  let text:string;try{text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);}catch{fail(400,'invalid_utf8');}
  const v=await engine.validateDataset(text!),data=v.dataset,fp=v.canonicalSha256,old=await this.operation('import',key,fp);if(old)return old;
  const parent=await this.a.one('SELECT * FROM bazi_sample_sets WHERE owner=? AND set_key=?',this.owner,data.setId),sid=parent?.id||uuid();
  const row=await this.a.one('SELECT * FROM bazi_sample_versions WHERE owner=? AND set_id=? AND version_key=?',this.owner,sid,data.version),stamp=this.clock();
  if(row&&row.canonical_sha256!==fp)fail(409,'version_conflict');
  const vid=row?.id||uuid(),header:any={...data};delete header.cases;const ops:any[]=[await this.guard({epoch})];
  if(!row){if(!parent)ops.push(this.a.stmt('INSERT INTO bazi_sample_sets VALUES(?,?,?,?,?,?)',sid,this.owner,data.setId,data.title,stamp,stamp));
   ops.push(this.a.stmt('INSERT INTO bazi_sample_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,0)',vid,this.owner,sid,data.version,await sha(text!),bytes.byteLength,fp,v.canonicalByteLength,J(data.cases.map((c:any)=>c.caseId)),J(header),stamp));
   for(let i=0;i<data.cases.length;i++){const c=data.cases[i],meta=v.cases[i];ops.push(this.a.stmt('INSERT INTO bazi_sample_cases VALUES(?,?,?,?,?,?,?,?)',vid,c.caseId,this.owner,i,J(c),meta.canonicalSha256,meta.canonicalByteLength,stamp));}
  }
  const item=row?versionItem(row):{id:vid,setId:sid,setKey:data.setId,version:data.version,title:data.title,caseCount:data.cases.length,sourceBytesSha256:await sha(text!),sourceByteLength:bytes.byteLength,canonicalSha256:fp,canonicalByteLength:v.canonicalByteLength,created:stamp,erased:false,teacherConfirmed:false};
  const response={item,duplicate:!!row};ops.push(this.op('import',key,fp,response));
  try{await this.a.db.batch(ops);}catch(e){const replay=await this.operation('import',key,fp);if(replay)return replay;const same=await this.a.one('SELECT v.* FROM bazi_sample_versions v JOIN bazi_sample_sets s ON s.id=v.set_id AND s.owner=v.owner WHERE v.owner=? AND s.set_key=? AND v.version_key=? AND v.erased_at=0',this.owner,data.setId,data.version);if(same&&same.canonical_sha256===fp){const reused={item:versionItem(same),duplicate:true};await this.a.db.batch([await this.guard({epoch}),this.op('import',key,fp,reused)]);return reused;}throw e;}return response;
 }
 async createRun(){
  const d=await this.body(['requestId','setVersionId','caseIds']),key=this.key(d.requestId),ids=d.caseIds;
  this.key(d.setVersionId);
  if(!Array.isArray(ids)||!ids.length||ids.length>100||ids.some(i=>typeof i!=='string')||new Set(ids).size!==ids.length)fail(400,'invalid_case_ids');
  const fp=await sha(J({setVersionId:d.setVersionId,caseIds:ids})),old=await this.a.one('SELECT * FROM bazi_sample_runs WHERE owner=? AND request_id=?',this.owner,key);
  if(old){if(old.intent_fingerprint!==fp)fail(409,'request_conflict');if(old.erased_at)fail(410,'sample_erased');return {run:runItem(old),duplicate:true};}
  await this.owned('bazi_sample_versions',d.setVersionId);const cases=await this.a.all('SELECT case_id FROM bazi_sample_cases WHERE owner=? AND version_id=?',this.owner,d.setVersionId);if(ids.some((i:any)=>!cases.some((c:any)=>c.case_id===i)))fail(400,'invalid_case_ids');
  const manifest=await this.manifest(),mh=await sha(J(manifest)),rid=uuid(),epoch=await this.epoch(),stamp=this.clock();
  const ops=[await this.guard({epoch}),this.a.stmt('INSERT INTO bazi_sample_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)',rid,this.owner,d.setVersionId,key,fp,J(ids),J(manifest),mh,epoch,'pending',1,ids.length,0,0,0,0,J(COUNTS),stamp,stamp)];
  for(const [ordinal,cid] of ids.entries())ops.push(this.a.stmt("INSERT INTO bazi_sample_workitems VALUES(?,?,?,?,?,?,0,'',0,'',?,?)",uuid(),this.owner,rid,cid,ordinal,'pending',stamp,stamp));
  try{await this.a.db.batch(ops);}catch(e){const r=await this.a.one('SELECT * FROM bazi_sample_runs WHERE owner=? AND request_id=?',this.owner,key);if(r&&r.intent_fingerprint===fp)return {run:runItem(r),duplicate:true};throw e;}
  return {run:runItem(await this.owned('bazi_sample_runs',rid)),duplicate:false};
 }
 resultItem(r:any,w?:any):any{if(!r)return {id:null,caseId:w.case_id,state:w.state,errorCode:w.last_error,counts:{...COUNTS,teacherAgreementRate:null},fingerprints:{},rawIndex:null,domStatus:'not_run',teacherConfirmed:false,professionalValidation:false,created:w.created,updated:w.updated};const d=JSON.parse(r.data);return {id:r.id,caseId:r.case_id,state:r.status,errorCode:r.error_code,counts:{...(d.counts||COUNTS),teacherAgreementRate:null},fingerprints:d.fingerprints||{},rawIndex:JSON.parse(r.raw_index),domStatus:'not_run',teacherConfirmed:false,professionalValidation:false,created:r.created,updated:r.created};}
 async computeCase(c:any){return engine.computeCase(c);}
 async process(rid:string){
  const d=await this.body(['requestId','version','limit']),key=this.key(d.requestId);if(!Number.isSafeInteger(d.version)||d.limit!==1)fail(400,'invalid_process');
  const fp=await sha(J({runId:rid,version:d.version,limit:1}));let run=await this.owned('bazi_sample_runs',rid),old=await this.operation('process',key,fp);if(old?.done)return {...old.response,duplicate:true};
  const mh=await sha(J(await this.processingManifest()));if(mh!==run.manifest_hash)fail(409,'implementation_changed');
  if(!old&&run.version!==d.version)fail(409,'run_version_changed');
  let work:any;if(old){work=await this.owned('bazi_sample_workitems',old.workId);if(['succeeded','blocked','failed'].includes(work.state)){const result=await this.a.one('SELECT * FROM bazi_sample_results WHERE run_id=? AND case_id=?',rid,work.case_id);if(!result)fail(409,'sample_result_invalid');const response={run:runItem(run),item:this.resultItem(result),duplicate:true};await this.a.db.batch([await this.guard({runId:rid,version:run.version,epoch:run.epoch,manifestHash:mh}),this.a.stmt("UPDATE bazi_sample_operations SET response_data=? WHERE owner=? AND kind='process' AND request_id=?",J({done:true,response}),this.owner,key)]);return response;}}else{
   if(await this.a.one("SELECT 1 FROM bazi_sample_workitems WHERE run_id=? AND state='processing' AND lease_until>"+NOW,rid))fail(409,'run_busy');
   work=await this.a.one("SELECT * FROM bazi_sample_workitems WHERE run_id=? AND state IN ('pending','processing') ORDER BY ordinal LIMIT 1",rid);
  }
  if(!work){const response={run:runItem(run),item:null,duplicate:false};await this.a.db.batch([await this.guard({runId:rid,version:run.version,epoch:run.epoch,manifestHash:mh}),this.op('process',key,fp,{done:true,response})]);return response;}
  const token=uuid(),stamp=this.clock(),proof={runId:rid,version:run.version,epoch:run.epoch,manifestHash:mh};
  const ops=[await this.guard(proof),this.a.stmt("UPDATE bazi_sample_workitems SET state='processing',attempts=min(attempts+1,5),lease_token=?,lease_until="+NOW+"+30000,updated=? WHERE id=? AND (state='pending' OR (state='processing' AND lease_until<="+NOW+'))',token,stamp,work.id),this.a.stmt("UPDATE bazi_sample_runs SET state='processing',version=version+1,updated=? WHERE id=?",stamp,rid)];
  if(!old)ops.push(this.op('process',key,fp,{done:false,workId:work.id}));
  // The trailing guard prevents a zero-row work claim from advancing the run.
  ops.push(await this.guard({...proof,version:proof.version+1,phase:'final',workId:work.id,leaseToken:token}));
  await this.a.db.batch(ops);
  const sample=await this.a.one('SELECT data FROM bazi_sample_cases WHERE version_id=? AND case_id=? AND owner=?',run.version_id,work.case_id,this.owner);if(!sample)fail(410,'sample_erased');
  const c=JSON.parse(sample.data);let report:any;
  try{if(work.attempts>=5)throw {code:'retry_exhausted'};const start=this.clock();report=await this.computeCase(c);if(this.clock()-start>15000)throw {code:'compute_timeout'};}catch(e:any){report={caseId:c.caseId,status:'failed',errorCode:e?.code||'calculation_failed',stages:{originalInput:c.input,domObserved:{status:'not_run'}},counts:{...COUNTS,teacherAgreementRate:null},fingerprints:{},fieldResults:[],fieldIndex:[],domStatus:'not_run',teacherConfirmed:false,professionalValidation:false};}
  if(await sha(J(await this.processingManifest()))!==mh)fail(409,'implementation_changed');
  const raw=report.stages.rawOutput;delete report.stages.rawOutput;const sections:any[]=[],rawIndex=raw?await engine.splitRaw(raw):null;
  let storedIndex:any=null;if(rawIndex){storedIndex={sha256:rawIndex.sha256,byteLength:rawIndex.byteLength,headerSha256:rawIndex.headerSha256,headerByteLength:rawIndex.headerByteLength,periods:rawIndex.periods.map((p:any)=>({index:p.index,sha256:p.sha256,byteLength:p.byteLength,chunkCount:split(J(p.data)).length}))};sections.push(['header',-1,J(rawIndex.header)]);for(const p of rawIndex.periods)sections.push(['period',p.index,J(p.data)]);}
  const resultId=uuid(),finished=this.clock(),finalProof={...proof,version:proof.version+1,phase:'final',workId:work.id,leaseToken:token};
  const final=[await this.guard(finalProof),this.a.stmt('INSERT INTO bazi_sample_results VALUES(?,?,?,?,?,?,?,?,?)',resultId,this.owner,rid,c.caseId,report.status,report.errorCode||'',J(report),J(storedIndex),finished)];
  for(const [section,index,text] of sections)for(const [ci,part] of split(text).entries())final.push(this.a.stmt('INSERT INTO bazi_sample_raw_chunks VALUES(?,?,?,?,?,?,?,?,?,?)',uuid(),this.owner,resultId,section,index,ci,part,await sha(part),enc.encode(part).length,finished));
  if(report.fieldResults?.length)final.push(this.a.stmt("INSERT INTO bazi_sample_field_results SELECT lower(hex(randomblob(16))),?,?,json_extract(value,'$.path'),value,? FROM json_each(?)",this.owner,resultId,finished,J(report.fieldResults)));
  const counts=JSON.parse(run.counts);for(const k of Object.keys(COUNTS))counts[k]+=report.counts?.[k]||0;counts.teacherAgreementRate=null;
  final.push(this.a.stmt("UPDATE bazi_sample_workitems SET state=?,last_error=?,lease_token='',lease_until=0,updated=? WHERE id=?",report.status,report.errorCode||'',finished,work.id),this.a.stmt("UPDATE bazi_sample_runs SET processed=processed+1,succeeded=succeeded+?,failed=failed+?,blocked=blocked+?,counts=?,version=version+1,state=CASE WHEN processed+1=total THEN 'completed' ELSE 'pending' END,updated=? WHERE id=?",+(report.status==='succeeded'),+(report.status==='failed'),+(report.status==='blocked'),J(counts),finished,rid));
  // Construct the response from the exact known final state, persist it with the result.
  const resultRow={id:resultId,case_id:c.caseId,status:report.status,error_code:report.errorCode||'',data:J(report),raw_index:J(storedIndex),created:finished};
  const after={...run,state:run.processed+1===run.total?'completed':'pending',processed:run.processed+1,succeeded:run.succeeded+(report.status==='succeeded'?1:0),failed:run.failed+(report.status==='failed'?1:0),blocked:run.blocked+(report.status==='blocked'?1:0),counts:J(counts),version:run.version+2,updated:finished};
  const response={run:runItem(after),item:this.resultItem(resultRow),duplicate:false};
  final.push(this.a.stmt("UPDATE bazi_sample_operations SET response_data=? WHERE owner=? AND kind='process' AND request_id=?",J({done:true,response}),this.owner,key));
  // Recheck actual implementation immediately before entering the final atomic batch.
  if(await sha(J(await this.processingManifest()))!==mh)fail(409,'implementation_changed');
  await this.a.db.batch(final);return response;
 }
 async raw(row:any){const rows=await this.a.all('SELECT * FROM bazi_sample_raw_chunks WHERE owner=? AND result_id=? ORDER BY section,period_index,chunk_index',this.owner,row.id);if(!rows.length)return null;const groups=new Map<string,string[]>();for(const c of rows){if(await sha(c.data)!==c.sha256||enc.encode(c.data).length!==c.byte_length)fail(409,'raw_integrity_error');const key=c.section+':'+c.period_index;if(!groups.has(key))groups.set(key,[]);groups.get(key)!.push(c.data);}const raw=JSON.parse(groups.get('header:-1')!.join(''));raw.periods=[...groups.keys()].filter(k=>k.startsWith('period:')).sort((a,b)=>+a.split(':')[1]-+b.split(':')[1]).map(k=>JSON.parse(groups.get(k)!.join('')));if(await sha(J(raw))!==JSON.parse(row.raw_index).sha256)fail(409,'raw_integrity_error');return raw;}
 async fields(row:any,report:any,before:string){if(before&&!report.fieldIndex.some((f:any)=>f.path===before))fail(400,'invalid_cursor');const page=engine.listFields(report,{before:before||null,limit:50}),provided=await this.a.all('SELECT id,path FROM bazi_sample_field_results WHERE result_id=? AND owner=?',row.id,this.owner);page.items=page.items.map((f:any)=>({...f,id:provided.find((p:any)=>p.path===f.path)?.id||null}));return page;}
 async review(finding:string){
  const d=await this.body(['requestId','category','evidence','note'],['retestRunId']),key=this.key(d.requestId),e=d.evidence;
  if(!['input','rule','algorithm','display','undetermined'].includes(d.category)||typeof d.note!=='string'||[...d.note].length>2000||!e||typeof e!=='object'||Array.isArray(e)||Object.keys(e).sort().join(',')!=='fingerprints,paths,reference'||!Array.isArray(e.paths)||!e.paths.length||e.paths.length>20||!e.fingerprints||typeof e.fingerprints!=='object'||Array.isArray(e.fingerprints)||(e.reference!==null&&(typeof e.reference!=='string'||e.reference.length>1000)))fail(400,'invalid_review');
  const content={...d};delete content.requestId;const fp=await sha(J({findingId:finding,...content})),old=await this.operation('review',key,fp);if(old)return old;
  const field=await this.owned('bazi_sample_field_results',finding),row=await this.owned('bazi_sample_results',field.result_id),report=JSON.parse(row.data);
  if(e.paths.some((p:any)=>!report.fieldIndex.some((f:any)=>f.path===p))||Object.entries(e.fingerprints).some(([k,v])=>report.fingerprints[k]!==v))fail(400,'invalid_evidence');if(d.retestRunId){await this.owned('bazi_sample_runs',d.retestRunId);if(d.retestRunId===row.run_id||!await this.a.one('SELECT 1 FROM bazi_sample_workitems WHERE run_id=? AND case_id=? AND owner=?',d.retestRunId,row.case_id,this.owner))fail(400,'invalid_retest_run');}
  const stamp=this.clock(),id=uuid(),response={item:{id,findingId:finding,category:d.category,evidence:e,note:d.note,retestRunId:d.retestRunId||null,classificationState:'proposed',created:stamp}};
  await this.a.db.batch([await this.guard({epoch:await this.epoch()}),this.a.stmt('INSERT INTO bazi_sample_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?)',id,this.owner,row.id,finding,key,fp,d.category,J(e),d.note,d.retestRunId||'',stamp),this.op('review',key,fp,response)]);return response;
 }
 async route(path:string,method:string){
  const base='/api/admin/bazi-samples';this.a.require(['admin']);await this.a.rate('bazi-samples:'+(method==='GET'?'read:':'write:')+this.owner,method==='GET'?180:30);
  const tail=path.slice(base.length),parts=tail?tail.replace(/^\//,'').split('/').map((s:string)=>{let v;try{v=decodeURIComponent(s);}catch{fail(400,'invalid_resource_id');}if(!/^[A-Za-z0-9:_-]{1,100}$/.test(v!))fail(400,'invalid_resource_id');return v!;}):[],before=this.a.url.searchParams.get('before')||'';
  if(method==='POST'&&parts.join('/')==='import')return this.importDataset();if(method==='POST'&&parts.join('/')==='runs')return this.createRun();if(method==='POST'&&parts.length===3&&parts[0]==='runs'&&parts[2]==='process')return this.process(parts[1]);if(method==='POST'&&parts.length===3&&parts[0]==='findings'&&parts[2]==='reviews')return this.review(parts[1]);if(method!=='GET')fail(405,'method_not_allowed');
  if(!parts.length){const p=await this.page('bazi_sample_versions','owner=? AND erased_at=0',[this.owner],before);return {items:p.rows.map(versionItem),next:p.next};}
  if(parts[0]!=='runs'){
   if(parts.length!==1)fail(404,'sample_not_found');const r=await this.owned('bazi_sample_versions',parts[0]),p=await this.page('bazi_sample_cases','owner=? AND version_id=?',[this.owner,r.id],before,'case_id');return {item:versionItem(r),header:{...JSON.parse(r.data),caseIds:JSON.parse(r.case_order)},cases:p.rows.map((c:any)=>({caseId:c.case_id,ordinal:c.ordinal,label:JSON.parse(c.data).label,tags:JSON.parse(c.data).tags,canonicalSha256:c.canonical_sha256,canonicalByteLength:c.canonical_bytes})),next:p.next};
  }
  if(parts.length<2)fail(404,'sample_not_found');const run=await this.owned('bazi_sample_runs',parts[1]);if(parts.length===2)return {run:runItem(run)};
  if(parts[2]==='export'){const rows=await this.a.all('SELECT * FROM bazi_sample_workitems WHERE run_id=? ORDER BY ordinal',run.id),results=await this.a.all('SELECT * FROM bazi_sample_results WHERE run_id=?',run.id);return {run:runItem(run),items:rows.map((w:any)=>this.resultItem(results.find((r:any)=>r.case_id===w.case_id),w)),canonicalExport:true,originalSourceBytesAvailable:false};}
  if(parts[2]!=='cases')fail(404,'sample_not_found');if(parts.length===3){const p=await this.page('bazi_sample_workitems','owner=? AND run_id=?',[this.owner,run.id],before),results=await this.a.all('SELECT * FROM bazi_sample_results WHERE run_id=?',run.id);return {items:p.rows.map((w:any)=>this.resultItem(results.find((r:any)=>r.case_id===w.case_id),w)),next:p.next};}
  const caseId=parts[3],sample=await this.a.one('SELECT * FROM bazi_sample_cases WHERE version_id=? AND case_id=? AND owner=?',run.version_id,caseId,this.owner),work=await this.a.one('SELECT * FROM bazi_sample_workitems WHERE run_id=? AND case_id=?',run.id,caseId);if(!sample||!work)fail(404,'sample_not_found');const row=await this.a.one('SELECT * FROM bazi_sample_results WHERE run_id=? AND case_id=?',run.id,caseId),item=this.resultItem(row,work);
  if(parts.length===4){const page=row?await this.page('bazi_sample_reviews','owner=? AND result_id=?',[this.owner,row.id],this.a.url.searchParams.get('reviewsBefore')||''):{rows:[],next:null};return {item,sampleCase:JSON.parse(sample.data),stages:row?JSON.parse(row.data).stages:null,reviews:page.rows.map((r:any)=>({id:r.id,findingId:r.field_id,category:r.category,evidence:JSON.parse(r.evidence),note:r.note,retestRunId:r.retest_run_id||null,classificationState:'proposed',created:r.created})),reviewsNext:page.next};}if(!row)fail(409,'case_not_completed');const report=JSON.parse(row.data),raw=await this.raw(row);
  if(parts[4]==='raw'){const index=JSON.parse(row.raw_index);if(parts.length===5){const header=raw?{...raw}:null;if(header)delete header.periods;return {header,index};}if(parts.length===7&&parts[5]==='periods'&&/^\d+$/.test(parts[6])&&raw?.periods[+parts[6]])return {...index.periods[+parts[6]],data:raw.periods[+parts[6]]};fail(404,'period_not_found');}
  report.stages.rawOutput=raw;if(parts[4]==='export'){let data:any={item,sampleCase:JSON.parse(sample.data),report,canonicalExport:true,originalSourceBytesAvailable:false};const include=this.a.url.searchParams.get('includeName')==='1';let paths:string[]=[];if(!include){const r=redactSampleNames(data);data=r.data;paths=r.paths;}return {...data,includesPrivateNames:include,completeFrozenReport:include,redactedPaths:paths,freeTextAnonymized:false};}if(parts[4]==='fields')return this.fields(row,report,before);fail(404,'sample_not_found');
 }
}
export async function baziSamplesRoute(a:any,path:string,method:string){if(path!=='/api/admin/bazi-samples'&&!path.startsWith('/api/admin/bazi-samples/'))return undefined;try{a.require(['admin']);const service=new BaziSamples(a);await service.live();const result=await service.route(path,method);await service.live();return result;}catch(e:any){if(e instanceof BaziSampleError)throw e;if(e?.code&&Number.isInteger(e.status))throw new BaziSampleError(e.status,e.code);const message=String(e?.message||'')+' '+String(e?.cause?.message||'');const code=/bazi_sample_[a-z_]+/.exec(message)?.[0];if(code)throw new BaziSampleError(409,code);throw e;}}
