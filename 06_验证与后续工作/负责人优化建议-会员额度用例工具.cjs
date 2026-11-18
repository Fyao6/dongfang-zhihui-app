'use strict';
const assert=require('node:assert/strict');
module.exports=function fixtures(h,a){
 const {api}=h,key=h.key,auths=new Map(),planAdmins=[a.admin];let serial=0,cfg;
 const quota=async(c,refresh=false)=>(await api(c,'membership/ai-quota'+(refresh?'/refresh':''),refresh?{}:undefined)).data.membershipQuota;
 const snapshot=async owner=>h.quotaControl({action:'snapshot',owner});
 const clock=async nowMs=>h.quotaControl({nowMs});
 async function preferences(c){const p=(await api(c,'privacy/preferences')).data;return (await api(c,'privacy/preferences',{revision:p.revision,policyVersion:p.disclosure.policyVersion,consents:{},acknowledged:true},'PATCH')).data;}
 async function consent(c,id='alpha'){const provider=(await api(c,'ai-gateway/capabilities')).data.providers.find(p=>p.id===id);assert(provider?.authorization);const auth=(await api(c,'ai-gateway/providers/'+id+'/consent',{acknowledged:true,policyVersion:provider.authorization.policyVersion,providerBinding:provider.authorization.providerBinding,categories:['general']})).data.authorization;let values=auths.get(c);if(!values){values={};auths.set(c,values);}values[id]=auth;return auth;}
 async function buyer(label){const p=await h.register(label);await preferences(p.c);await consent(p.c);return p;}
 function payload(c,label){const auth=auths.get(c)?.alpha;assert(auth?.receiptValid);return {requestId:key(label),scene:'chat',environment:'local-test',messages:[{role:'user',content:'MEMBER_QUOTA_SYNTHETIC_'+label,privacy:{accountId:auth.accountId,providerId:auth.providerId,providerBinding:auth.providerBinding,policyVersion:auth.policyVersion,consentEpoch:auth.consentEpoch,source:'user',category:'general'}}],context:null};}
 const create=async(c,body,expected=200)=>(await api(c,'ai-gateway/jobs',body,'POST',expected)).data;
 const detail=async(c,id)=>(await api(c,'ai-gateway/jobs/'+id)).data;
 const cancel=async(c,id)=>(await api(c,'ai-gateway/jobs/'+id+'/cancel',{})).data;
 async function stream(c,id,body,expected=200){const r=await c.post(h.base+'/api/ai-gateway/jobs/'+id+'/stream',{data:body,timeout:35000});assert.equal(r.status(),expected);if(expected!==200)return [];assert(r.headers()['content-type'].includes('text/event-stream'));return (await r.text()).replaceAll('\r\n','\n').split('\n\n').filter(Boolean).map(block=>{const lines=block.split('\n'),kind=lines.find(x=>x.startsWith('event:'))?.slice(6).trim(),raw=lines.filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trimStart()).join('\n');return {kind,data:raw?JSON.parse(raw):null};});}
 const done=events=>events.findLast(e=>e.kind==='gateway.done')?.data;
 async function policy(changes={}){const old=(await api(a.admin,'admin/membership-ai-quota')).data.policy;return (await api(a.admin,'admin/membership-ai-quota',{...old,...changes},'PATCH')).data.policy;}
 async function configure(){
  for(const label of ['planadmin1','planadmin2']){const p=await h.register(label);await api(a.admin,'admin/users/'+p.credential.id,{role:'admin'},'PATCH');planAdmins.push(p.c);}
  await api(a.admin,'admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
  const ms=(await api(a.admin,'admin/membership')).data.settings;await api(a.admin,'admin/membership/settings',{revision:ms.revision,sandboxEnabled:true,productionEnabled:false},'PATCH');
  const old=(await api(a.admin,'admin/ai-gateway')).data.config;
  const provider=(id,protocol)=>({id,name:'明确本机HTTP夹具 '+id,protocol,endpoint:'https://'+id+'.gateway.invalid/v1/'+(id==='alpha'?'responses':'messages'),model:id+'-qa-model',secretRef:'EW_AI_GATEWAY_QA_'+id.toUpperCase(),processingRegions:['QA-LOCAL'],privacyPolicyVersion:key('privacy'),enabled:true,streaming:true,authMode:id==='beta'?'x-api-key':'bearer',apiVersion:id==='beta'?'2026-10-21':'',timeoutSeconds:25,maxOutputTokens:128,prompt:'只验证本机协议和结算；不是真实模型。'});
  cfg=(await api(a.admin,'admin/ai-gateway/config',{revision:old.revision,enabled:true,allowExternalCalls:true,environment:'local-test',providers:[provider('alpha','responses'),provider('beta','anthropic_messages')],routes:Object.fromEntries(['chat','chart','course','card'].map(x=>[x,{primary:'alpha',fallback:[]} ])),requestTimeoutSeconds:25,charging:{confirmed:true,ruleVersion:key('charge'),successCredits:4,failureCredits:1,partialCredits:2,cancelCredits:1}},'PATCH')).data.config;
  const privacy=(await api(a.admin,'admin/privacy/config')).data.config;
  await api(a.admin,'admin/privacy/config',{revision:privacy.revision,policyVersion:key('privacy'),controllerName:'隔离测试主体',contact:'仅合成资料',recipients:cfg.providers.map(p=>({id:p.id,name:p.name,endpoint:p.endpoint,models:[p.model],regions:p.processingRegions,purpose:'本次本机HTTPfixture验证，不发给真实供应商',policyUrl:'https://'+p.id+'.gateway.invalid/privacy',retentionDays:null,deletionSupported:false})),retention:{recordsDays:null,conversationsDays:null,backupDays:null,financeDays:null},purposeDetails:{trainingImprovement:'',marketing:''}},'PATCH');
 }
 async function gatewayConfig(changes){cfg=(await api(a.admin,'admin/ai-gateway/config',{...cfg,...changes,revision:cfg.revision},'PATCH')).data.config;return cfg;}
 async function plan(label,{credits=20,cycle='billing_period',term={unit:'month',count:1},groupId,...extra}={}){
  const product=(await api(a.admin,'admin/commerce/products',{title:'合成会员额度商品 '+label,description:'仅本次新隔离库，不是正式定价。',type:'membership',environment:'sandbox',status:'published',sku:key(label),priceMinor:1000,currency:'USD',stock:100,contentId:'',shippingCountries:[],shippingMinor:0,taxMinor:0})).data.item;
  const input={environment:'sandbox',status:'published',skuId:product.skuId,groupId:groupId||key('group_'+label),title:'合成额度方案 '+label,description:'有限沙箱额度，不表示生产服务接通。',billingMode:'recurring',term,renewalPriceMinor:1000,benefits:{catalogScope:'none',courseIds:[],aiCredits:credits,aiResetCycle:cycle,other:[]},ruleVersion:key('benefit'),termsVersion:key('terms'),serviceTerms:'合成有限权益，仅本机。',refundPolicy:'真实资金仍未接通。',graceDays:2,trialDays:0,promotionsEnabled:false,...extra};
  const admin=planAdmins[(serial++)%planAdmins.length],item=(await api(admin,'admin/membership/plans',input)).data.item;return {product,plan:item,input,admin};
 }
 const order=async(c,p,label,renewalOf)=>(await api(c,'commerce/orders',{requestId:key(label),environment:'sandbox',items:[{skuId:(p.plan||p).skuId,quantity:1}],...(renewalOf?{membershipRenewalOf:renewalOf}:{})})).data;
 const pay=async(c,o,label)=>(await api(c,'commerce/orders/'+o.id+'/sandbox-pay',{requestId:key(label)})).data;
 const status=async c=>(await api(c,'membership/status')).data;
 async function purchase(p,label,options={}){const {anchor,...planOptions}=options;if(Object.hasOwn(options,'anchor'))await clock(anchor);const offer=await plan(label,planOptions),o=await order(p.c,offer,label+'_order');const paid=await pay(p.c,o,label+'_pay'),sub=(await status(p.c)).items.find(s=>s.periods.some(x=>x.orderId===o.id));assert(sub);return {...offer,order:paid,sub,person:p};}
 const refund=async bought=>(await api(a.admin,'admin/commerce/orders/'+bought.order.id+'/refund',{requestId:key('refund_'+bought.order.id),items:bought.order.items.map(i=>({itemId:i.id,quantity:1}))})).data;
 const grant=async(p,credits=100)=>(await api(a.admin,'admin/ai-gateway/grants',{requestId:key('manual_'+p.credential.id),accountId:p.credential.id,credits,environment:'local-test'})).data;
 const event=async(bought,kind)=>(await api(a.admin,'admin/membership/sandbox-events',{requestId:key('event_'+kind+'_'+bought.sub.id+'_'+Date.now()),subscriptionId:bought.sub.id,environment:'sandbox',event:kind})).data;
 return {quota,snapshot,clock,preferences,consent,buyer,payload,create,detail,cancel,stream,done,policy,configure,gatewayConfig,plan,order,pay,status,purchase,refund,grant,event,get cfg(){return cfg;}};
};
