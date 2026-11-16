// Independent local QA Worker; actual API/builds, reserved .invalid transport only, no prompt logs.
import {handleAPI} from '../04_研发源码/app/cloud/lib/eastern-api';
import experience from '../04_研发源码/app/cloud/generated/experience.html';
import admin from '../04_研发源码/app/cloud/generated/admin.html';
import schema from '../04_研发源码/app/cloud/drizzle/0000_lethal_lucky_pierre.sql';
const calls:any[]=[],held:Array<()=>void>=[];let mode='success',initialization:Promise<any>|null=null;
const frame=(kind:string,data:any)=>'event: '+kind+'\ndata: '+JSON.stringify(data)+'\n\n';
globalThis.fetch=(async(input:any,options:any={})=>{
 const url=typeof input==='string'?input:input.url,u=new URL(url);if(!['alpha.memory.invalid','beta.memory.invalid','memory-legacy.invalid'].includes(u.hostname))throw Error('QA blocks all external HTTP');const payload=JSON.parse(options.body||'{}'),serialized=JSON.stringify(payload),providerId=u.hostname==='memory-legacy.invalid'?'legacy-memory':u.hostname.startsWith('alpha.')?'alpha':'beta',currentMode=mode;
 const selectedBodyPresent=serialized.includes('MEM_SELECTED_BODY_CANARY'),unselectedBodyPresent=serialized.includes('MEM_UNSELECTED_BODY_CANARY');
 calls.push({providerId,selectedBodyPresent,unselectedBodyPresent,localMemoryMetadataPresent:serialized.includes('memoryEpoch')||serialized.includes('memorySelection'),privacyTagsPresent:serialized.includes('consentEpoch')});
 if(providerId==='legacy-memory')return Response.json({output:[{type:'message',content:[{type:'output_text',text:'MEMORY_LOCAL_FIXTURE_LEGACY'}]}]});
 if(currentMode==='primary-fails'&&providerId==='alpha')return new Response('{}',{status:503});
 if(!payload.stream)return Response.json(providerId==='alpha'?{output:[{type:'message',content:[{type:'output_text',text:'AG_LOCAL_MOCK_甲'}]}],usage:{input_tokens:7,output_tokens:3}}:{content:[{type:'text',text:'AG_LOCAL_MOCK_乙'}],usage:{input_tokens:7,output_tokens:3}});
 return new Response(new ReadableStream({async start(controller){let closed=false,release:(()=>void)|undefined;const abort=()=>{release?.();if(!closed){closed=true;try{controller.error(Error('QA transport aborted'));}catch{}}};options.signal?.addEventListener('abort',abort,{once:true});const wait=()=>new Promise<void>(resolve=>{release=resolve;held.push(resolve);});const send=(text:string)=>{const bytes=new TextEncoder().encode(text);for(let i=0;i<bytes.length&&!closed;i+=7)controller.enqueue(bytes.slice(i,i+7));};try{if(currentMode==='hold-before-first')await wait();if(providerId==='alpha')send(frame('response.output_text.delta',{type:'response.output_text.delta',delta:'AG_LOCAL_MOCK_甲'}));else{send(frame('message_start',{type:'message_start',message:{usage:{input_tokens:7}}}));send(frame('content_block_delta',{type:'content_block_delta',delta:{type:'text_delta',text:'AG_LOCAL_MOCK_乙'}}));}if(currentMode==='hold')await wait();if(currentMode!=='partial'&&!closed){if(providerId==='alpha')send(frame('response.completed',{type:'response.completed',response:currentMode==='no-usage'?{}:{usage:{input_tokens:7,output_tokens:3}}}));else{send(frame('message_delta',{type:'message_delta',...(currentMode==='no-usage'?{}:{usage:{output_tokens:3}})}));send(frame('message_stop',{type:'message_stop'}));}}if(!closed){closed=true;controller.close();}}catch(error){if(!closed){closed=true;controller.error(error);}}finally{options.signal?.removeEventListener('abort',abort);}}}),{headers:{'Content-Type':'text/event-stream','request-id':'LOCAL_GATEWAY_FIXTURE'}});
}) as typeof fetch;
async function init(env:any){if(!initialization)initialization=(async()=>{const statements=schema.split('--> statement-breakpoint').map((s:string)=>s.trim()).filter(Boolean).map((s:string)=>s.replace(/CREATE TABLE /g,'CREATE TABLE IF NOT EXISTS ').replace(/CREATE UNIQUE INDEX /g,'CREATE UNIQUE INDEX IF NOT EXISTS ').replace(/CREATE INDEX /g,'CREATE INDEX IF NOT EXISTS '));await env.DB.batch(statements.map((s:string)=>env.DB.prepare(s)));})();await initialization;}
async function initMemoryFixture(request:Request,env:any,context:any){
 if(!initialization){
  const schemaReady=init(env);
  initialization=(async()=>{
   await schemaReady;
   const health=await handleAPI(new Request(new URL('/api/health',request.url)),env,context);
   if(!health.ok)throw Error('Actual Cloud API initialization failed');
   const ai={enabled:true,apiKeyRef:'EW_AI_MEMORY_QA_LEGACY',endpoint:'https://memory-legacy.invalid/v1/responses',model:'memory-legacy-model',providerId:'legacy-memory',processingRegions:['QA-LOCAL'],privacyPolicyVersion:'memory-fixture-v1',prompt:'Explicit local fixture only',knowledge:''};
   await env.DB.prepare("UPDATE settings SET data=? WHERE key='ai'").bind(JSON.stringify(ai)).run();
  })();
 }
 await initialization;
}
export default {async fetch(request:Request,env:any,context:any){const url=new URL(request.url);if(url.pathname.startsWith('/assets/')&&env.ASSETS)return env.ASSETS.fetch(request);if(url.pathname==='/__memory-test/mock'){if(request.headers.get('X-Memory-Test')!==env.MEMORY_TEST_TOKEN)return new Response('test token required',{status:403});if(request.method==='POST'){const d:any=await request.json();if(d.mode){if(!['success','primary-fails','partial','no-usage','hold','hold-before-first'].includes(d.mode))return new Response('bad mode',{status:400});mode=d.mode;}if(d.release)while(held.length)held.shift()!();}return Response.json({isolated:true,externalProviderTested:false,kind:'local-process-mock',calls,mode});}if(url.pathname.startsWith('/api/')){await initMemoryFixture(request,env,context);return (handleAPI as any)(request,env,context);}if(['/','/app','/experience'].includes(url.pathname))return new Response(experience,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});if(url.pathname==='/admin')return new Response(admin,{headers:{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'}});return new Response('QA route not found',{status:404});}};
