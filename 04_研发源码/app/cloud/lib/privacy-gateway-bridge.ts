// Global disclosure binding only. Never creates provider receipts, sends data or grants categories.
const SCENES=['chat','chart','course','card'];
const SUFFIXES:Record<string,string>={responses:'/responses',anthropic_messages:'/messages',chat_completions:'/chat/completions'};
const object=(v:any)=>!!v&&typeof v==='object'&&!Array.isArray(v);
const codepointCompare=(a:string,b:string)=>{const x=Array.from(a),y=Array.from(b);for(let i=0;i<Math.min(x.length,y.length);i++){const d=x[i].codePointAt(0)!-y[i].codePointAt(0)!;if(d)return d;}return x.length-y.length;};
const sorted=(v:string[])=>[...new Set(v)].sort(codepointCompare);
const endpoint=(v:any)=>{try{if(typeof v!=='string'||/\s/.test(v))return '';const u=new URL(v);return u.protocol==='https:'&&u.hostname&&!u.username&&!u.password&&!u.search&&!u.hash?u.origin+u.pathname:'';}catch{return '';}};
const policyURL=(v:any)=>{try{const u=new URL(v);return u.protocol==='https:'&&!!u.hostname&&!u.username&&!u.password;}catch{return false;}};
const regions=(v:any):string[]|null=>Array.isArray(v)&&v.length&&v.every(x=>typeof x==='string'&&x.trim())?sorted(v.map(x=>x.trim())):null;
const equal=(a:any,b:any)=>JSON.stringify(a)===JSON.stringify(b);
async function digest(s:string){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s))),x=>x.toString(16).padStart(2,'0')).join('');}
function canonical(v:any):string{if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(object(v))return '{'+Object.keys(v).sort(codepointCompare).map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
function ready(c:any){return object(c)&&['policyVersion','controllerName','contact'].every(k=>typeof c[k]==='string'&&c[k].trim())&&Array.isArray(c.recipients)&&c.recipients.length&&c.recipients.every((r:any)=>object(r)&&['id','name','purpose','policyUrl','endpoint'].every(k=>typeof r[k]==='string'&&r[k].trim())&&endpoint(r.endpoint)&&policyURL(r.policyUrl)&&regions(r.regions)&&Array.isArray(r.models)&&r.models.length&&r.models.every((m:any)=>typeof m==='string'&&m.trim()))&&new Set(c.recipients.map((r:any)=>r.id)).size===c.recipients.length;}
async function legacyBinding(c:any,ai:any){
 try{
  const target=endpoint(ai.endpoint),receiver=c.recipients.find((r:any)=>r.id===ai.providerId),r=ai.processingRegions;
  const legacyReady=!!(c.policyVersion&&c.controllerName&&c.contact&&c.recipients.length&&c.recipients.every((x:any)=>x.id&&x.name&&x.regions?.length&&x.purpose&&x.policyUrl&&x.endpoint&&x.models?.length));
  if(!legacyReady||!ai.providerId||!target||!ai.model||!receiver||!Array.isArray(r)||!r.length||r.some((x:any)=>typeof x!=='string'||!x.trim()))return null;
  // Preserve the frozen legacy serialization/order exactly. Integration injects actualBinding.
  const normalized=[...new Set(r.map((x:string)=>x.trim()))].sort();if(target!==endpoint(receiver.endpoint)||!receiver.models.includes(ai.model)||!equal(normalized,[...new Set(receiver.regions)].sort())||ai.privacyPolicyVersion!==c.policyVersion)return null;
  const details={providerId:ai.providerId,endpoint:target,model:ai.model,processingRegions:normalized,privacyPolicyVersion:ai.privacyPolicyVersion,policyVersion:c.policyVersion,receiverId:receiver.id};return {details,digest:await digest(JSON.stringify(details))};
 }catch{return null;}
}
export async function registryBinding(c:any,gateway:any){
 try{
  if(!ready(c)||!object(gateway)||gateway.environment!=='local-test'||!object(gateway.routes)||!equal(Object.keys(gateway.routes).sort(),[...SCENES].sort())||!Array.isArray(gateway.providers))return null;
  const byId=new Map<string,any>();for(const p of gateway.providers){if(!object(p)||typeof p.id!=='string'||!/^[A-Za-z0-9_-]{1,80}$/.test(p.id)||byId.has(p.id))return null;byId.set(p.id,p);}
  const referenced=new Set<string>();for(const r of Object.values(gateway.routes) as any[]){if(!object(r)||!equal(Object.keys(r).sort(),['fallback','primary'])||typeof r.primary!=='string'||!Array.isArray(r.fallback)||r.fallback.length>3||r.fallback.some((id:any)=>typeof id!=='string'||!id)||new Set(r.fallback).size!==r.fallback.length||r.fallback.includes(r.primary))return null;for(const id of [...(r.primary?[r.primary]:[]),...r.fallback])referenced.add(id);}
  if(!referenced.size||[...referenced].some(id=>!byId.has(id)))return null;
  const receipts=[];for(const id of [...referenced].sort(codepointCompare)){const p=byId.get(id),receiver=c.recipients.find((r:any)=>r.id===id),r=regions(p.processingRegions);if(!receiver||!Object.hasOwn(SUFFIXES,p.protocol)||!endpoint(p.endpoint)||!new URL(p.endpoint).pathname.endsWith(SUFFIXES[p.protocol])||p.endpoint!==receiver.endpoint||typeof p.model!=='string'||!p.model.trim()||!receiver.models.includes(p.model)||!r||!equal(r,sorted(receiver.regions))||p.privacyPolicyVersion!==c.policyVersion)return null;receipts.push({providerId:id,protocol:p.protocol,endpoint:p.endpoint,model:p.model,processingRegions:r,privacyPolicyVersion:p.privacyPolicyVersion,policyVersion:c.policyVersion,receiverId:receiver.id});}
  const details={mode:'gateway-registry',schemaVersion:1,policyVersion:c.policyVersion,providers:receipts};return {details,digest:await digest(canonical(details))};
 }catch{return null;}
}
export async function globalBinding(c:any,legacy:any,gateway:any,actualLegacy?:(c:any,ai:any)=>Promise<any>){let old:any=null;try{old=await (actualLegacy||legacyBinding)(c,legacy);}catch{}return old||registryBinding(c,gateway);}
export async function bridgePrivacyResponse(base:any,legacy:any,gateway:any,actualLegacy?:(c:any,ai:any)=>Promise<any>,accountId?:string){
 if(!object(base)||!object(base.disclosure)||!object(base.consents)||typeof base.accountId!=='string'||!base.accountId||accountId!==undefined&&base.accountId!==accountId)throw Error('A complete current-account privacy response is required');
 const c=base.disclosure,b=await globalBinding(c,legacy,gateway,actualLegacy),ack=!!(b&&base.policyVersion===c.policyVersion&&base.providerBinding===b.digest);return {...base,disclosure:{...c,configured:!!b,providerBinding:b?.digest||'',activeAI:b?.details||null},policyAcknowledged:ack,consentEpoch:base.revision+':'+c.policyVersion+':'+(b?.digest||''),authorizedCategories:ack?['general','card',...['chart','wellbeing'].filter(k=>base.consents[k]===true)]:[]};
}
