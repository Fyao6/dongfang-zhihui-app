// Pure VM checks with synthetic storage. No browser, original user data or network.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),storage=new Map(),checks=[];
const state={lang:'zh',page:'privacyCenter',support:{ai:[{text:'new-unsaved'}],profile:{name:'self'},messages:{other:[{text:'OTHER-PRIVATE'}]}},daily:{},wellness:{},answers:{sleep:'SENSITIVE-SLEEP',energy:'SENSITIVE-ENERGY',stress:'SENSITIVE-STRESS',comfort:'SENSITIVE-COMFORT'}};
const context={console,URL,Blob,crypto:require('node:crypto').webcrypto,setTimeout,queueMicrotask:()=>{},state,screens:{},personalStorage:{scope:'one',epoch:0},px:{user:{id:'one'}},initial:{},
 document:{addEventListener(){},getElementById(){return null}},
 localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},
 esc:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
 pxTop:title=>'<h1>'+title+'</h1>',go:label=>'<button>'+label+'</button>',icon:()=>'<i></i>',render(){},toast(){},closeSheet(){},
 ewI18n:{normalize:x=>x,error:x=>x},psKey:scope=>'ew-personal-v1:'+scope,defaultWellness:()=>({body:{},mind:{},intentions:{},sessions:[],plan:[],continuity:{cardActions:[]}}),
 psClone:x=>JSON.parse(JSON.stringify(x)),psSnapshot:()=>({support:state.support,daily:state.daily,wellness:state.wellness,answers:state.answers}),
 psRead:key=>{try{return JSON.parse(storage.get(key)||'null')}catch{return null}},
 psToken(){return {scope:context.personalStorage.scope,epoch:context.personalStorage.epoch}},
 psCurrent(token){return token.scope!==null&&token.scope===context.personalStorage.scope&&token.epoch===context.personalStorage.epoch},
 flText(en,zh,hant,bo){return ({en,zh,'zh-Hant':hant,bo})[state.lang]||zh},
 psCommit(change){change();const data=context.psSnapshot();data.support={...data.support,ai:context.privacyConversationForStorage(data.support.ai)};storage.set('ew-personal-v1:'+context.personalStorage.scope,JSON.stringify({scope:context.personalStorage.scope,data}));return true;}
};
context.window=context;
storage.set('ew-personal-v1:one',JSON.stringify({scope:'one',data:{support:{ai:[{text:'old-saved'}]}}}));
storage.set('ew-life-birth-v1:one',JSON.stringify({name:'mine'}));
storage.set('ew-life-birth-v1:two',JSON.stringify({name:'OTHER-BIRTH'}));
const originalStorage=JSON.stringify([...storage]);vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root,'04_研发源码/app/r4/privacy-center.js'),'utf8'),context);
function check(name,condition){assert.ok(condition,name);checks.push({name,passed:true});}
check('module initialization does not delete or modify stored user data',JSON.stringify([...storage])===originalStorage);
check('privacy screen registers in actual screens map',typeof context.screens.privacyCenter==='function');
const exported=context.privacyLocalExport(context.psToken());
check('local export includes current account birth data',exported.scopedRecords['ew-life-birth-v1:'].name==='mine');
check('local export excludes other accounts and other people private messages',!JSON.stringify(exported).includes('OTHER-'));
check('saving off preserves previously saved chat while excluding new chat',context.privacyConversationForStorage([{text:'new-unsaved'}])[0].text==='old-saved');
context.privacyState().data={policyAcknowledged:true,consents:{saveConversations:true}};
check('saving on allows new current account conversation',context.privacyConversationForStorage([{text:'new-consented'}])[0].text==='new-consented');
context.privacyState().data={policyAcknowledged:true,consents:{saveConversations:false}};
check('explicit local chat clearing removes old saved copy',context.privacyClearLocal('conversations',context.psToken())&&JSON.parse(storage.get('ew-personal-v1:one')).data.support.ai.length===0);
check('explicit local records clearing removes retained self-assessment values',context.privacyClearLocal('records',context.psToken())&&!JSON.stringify(context.privacyLocalExport(context.psToken())).includes('SENSITIVE-')&&!storage.get('ew-personal-v1:one').includes('SENSITIVE-'));
check('local records clearing preserves other account birth data',storage.get('ew-life-birth-v1:two').includes('OTHER-BIRTH'));
const auth={accountId:'one',consentEpoch:'1:policy:binding',providerId:'fixture',providerBinding:'binding',policyVersion:'policy',authorizedCategories:['general','card']},tag={...auth,source:'user',category:'general'};
const valid={role:'user',text:'typed current',privacy:tag};
check('new marked request history can be sent while legacy remains display-only',context.privacyAIHistory([{role:'user',text:'legacy report'},valid],auth).length===1);
check('withdrawal or policy epoch change drops old tagged history',context.privacyAIHistory([valid],{...auth,consentEpoch:'2:policy:binding'}).length===0);
check('unauthorized report category excluded from ordinary chat history',context.privacyAIHistory([{...valid,privacy:{...tag,source:'report',category:'chart'}}],auth).length===0);
check('automatic report cannot masquerade as general history',context.privacyAIHistory([{...valid,privacy:{...tag,source:'report'}}],auth).length===0);
const stale=context.psToken();context.personalStorage.scope='two';context.personalStorage.epoch++;
const before=JSON.stringify([...storage]);check('account switch invalidates local mutation token',context.privacyClearLocal('conversations',stale)===false&&before===JSON.stringify([...storage]));
assert.throws(()=>context.privacyLocalExport(stale));checks.push({name:'account switch invalidates local export token',passed:true});
context.personalStorage.scope='one';context.personalStorage.epoch++;context.px.user={id:'one'};
for(const lang of ['zh','zh-Hant','en','bo']){
 state.lang=lang;const runtime=context.privacyState();runtime.status='ready';runtime.data={policyAcknowledged:false,revision:0,consents:{},disclosure:{policyVersion:'',controllerName:'',contact:'',recipients:[],purposeDetails:{},configured:false,retention:{recordsDays:null,conversationsDays:null,backupDays:null,financeDays:null}}};runtime.requests=[];
 const html=context.privacyCenter();check(lang+' privacy screen renders explicit language and real pending state',html.includes(context.privacyTitle())&&!html.includes('undefined')&&html.includes('privacy-preferences-form'));
}
context.personalStorage.scope='two';context.personalStorage.epoch++;check('account scoped runtime clears cached permissions',context.privacyState().data===null);
async function finish(){
 context.personalStorage.scope='one';context.personalStorage.epoch++;context.px.user={id:'one'};let destination='';context.navigate=page=>{destination=page;};context.pxApi=async()=>({policyAcknowledged:false,disclosure:{configured:true},consents:{chart:false}});
 let blocked=false;try{await context.privacyBeforeAI();}catch{blocked=true;}
 check('overall acknowledgment withdrawal blocks frontend AI and returns to privacy settings',blocked&&destination==='privacyCenter');
 const result={kind:'isolated-frontend-vm-checks',passed:checks.length,failed:0,networkCalls:0,originalUserDataAccessed:false,checks};
 fs.writeFileSync(path.join(__dirname,'负责人优化建议-隐私前端隔离自检.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({passed:checks.length,failed:0}));
}
finish().catch(error=>{console.error(error);process.exitCode=1;});
