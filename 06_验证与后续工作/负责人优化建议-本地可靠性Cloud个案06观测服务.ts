// Diagnostic-only stable binding observer. No SQL, statement, binding or options changes.
import nativeService from './负责人优化建议-卡组迁移Cloud测试服务';
const dbIds=new WeakMap<object,number>(),envIds=new WeakMap<object,number>(),proxies=new WeakMap<object,any>();
let dbSerial=0,envSerial=0,requestCount=0;
const counts:Record<string,number>={},batches={count:0,elapsedMs:0,maxMs:0,failed:0};
const phases:Record<string,number>={};
let lastPhase='',lastStatus:number|null=null;
function observed(db:any){let proxy=proxies.get(db);if(proxy)return proxy;
 proxy=new Proxy(db,{get(target,key){if(key==='prepare')return(sql:string)=>{const kind=/^\s*([A-Za-z]+)/.exec(sql)?.[1]?.toUpperCase()||'OTHER';counts[kind]=(counts[kind]||0)+1;return target.prepare(sql);};if(key==='batch')return async(...args:any[])=>{const start=performance.now();batches.count++;try{return await target.batch(...args);}catch(error){batches.failed++;throw error;}finally{const ms=performance.now()-start;batches.elapsedMs+=ms;batches.maxMs=Math.max(batches.maxMs,ms);}};const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;}});
 proxies.set(db,proxy);return proxy;
}
export default {async fetch(request:Request,env:any,ctx:any){const url=new URL(request.url);
 if(url.pathname==='/__local-case06-observer'){
  if(url.hostname!=='127.0.0.1'||request.method!=='GET'||request.headers.get('X-Card-Migration-Test')!==env.CARD_MIGRATION_TEST_TOKEN)return new Response('',{status:403});
  return Response.json({componentOnly:true,requestCount,rawDatabaseBindingDistinct:dbSerial,rawEnvironmentDistinct:envSerial,prepareCounts:{...counts},batches:{...batches},phases:{...phases},lastPhase,lastStatus,nativePerformanceMemoryAvailable:!!(performance as any).memory,performanceMemory:(performance as any).memory||null,sqlTextRecorded:false,bindingsRecorded:false,originalStatementsReturned:true,originalBatchArgumentsForwarded:true});
 }
 if(!dbIds.has(env.DB))dbIds.set(env.DB,++dbSerial);if(!envIds.has(env))envIds.set(env,++envSerial);
 const phase=url.pathname.startsWith('/api/admin/cards/imports/')?(url.pathname.endsWith('/export')?'ndjson-export':url.searchParams.has('issuesBefore')?'issues-page':url.searchParams.has('diffBefore')?'diff-page':url.pathname.endsWith('/preview')?'preview':url.pathname.endsWith('/apply')?'apply':'detail'):url.pathname.startsWith('/api/')?'other-api':'other';
 requestCount++;phases[phase]=(phases[phase]||0)+1;lastPhase=phase;
 const response=await nativeService.fetch(request,{...env,DB:observed(env.DB)},ctx);lastStatus=response.status;return response;
}};
