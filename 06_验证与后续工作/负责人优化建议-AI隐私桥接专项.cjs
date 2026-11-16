// Pure fixtures + virtual actual API integration. Frozen source bytes and public entries are untouched.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict'),Module=require('node:module');
const {execFileSync}=require('node:child_process'),{DatabaseSync}=require('node:sqlite');
const ROOT=path.resolve(__dirname,'..'),CLOUD=path.join(ROOT,'04_研发源码/app/cloud'),ts=require(path.join(CLOUD,'node_modules/typescript'));
const sha=v=>crypto.createHash('sha256').update(v).digest('hex'),fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'负责人优化建议-AI隐私桥接夹具.json'))),results=[],bindings={};
const frozenNames=['04_研发源码/app/r4/backend/privacy.py','04_研发源码/app/cloud/lib/privacy-api.ts'],before=Object.fromEntries(frozenNames.map(n=>[n,sha(fs.readFileSync(path.join(ROOT,n)))]));
const priorTs=require.extensions['.ts'];require.extensions['.ts']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,filename);
const bridge=require(path.join(CLOUD,'lib/privacy-gateway-bridge.ts')),frozen=require(path.join(CLOUD,'lib/privacy-api.ts')),{aiGatewayRoute,initAIGateway}=require(path.join(CLOUD,'lib/ai-gateway.ts'));
async function check(name,action){try{const observed=await action();results.push({name,pass:true,...(observed===undefined?{}:{observed})});}catch(e){results.push({name,pass:false,error:e.stack||String(e)});}}
class StatusError extends Error{constructor(status,message){super(message);this.status=status;}}
const fail=(status,message)=>{throw new StatusError(status,message)};
async function refused(action,status){await assert.rejects(action,e=>e.status===status);}
function ownerAt(value,dotted){const parts=dotted.split('.');for(const key of parts.slice(0,-1))value=value[key];return [value,parts.at(-1)];}
const db=new DatabaseSync(':memory:');db.exec('CREATE TABLE settings(key TEXT PRIMARY KEY,data TEXT);CREATE TABLE users(id TEXT PRIMARY KEY);');for(const id of ['u1','u2'])db.prepare('INSERT INTO users VALUES(?)').run(id);
const set=(k,v)=>db.prepare('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET data=excluded.data').run(k,JSON.stringify(v));
function adapter(id='u1'){
 const a={user:{id,role:'user'},env:{},url:new URL('https://isolated.invalid/'),payload:{},require(roles){if(!this.user)fail(401,'login');if(roles&&!roles.includes(this.user.role))fail(403,'role');return this.user;},async one(sql,...args){return db.prepare(sql).get(...args)||null;},async all(sql,...args){return db.prepare(sql).all(...args);},async run(sql,...args){const r=db.prepare(sql).run(...args);return {meta:{changes:Number(r.changes)}};},stmt(sql,...args){return {sql,args}},async setting(k){const r=await this.one('SELECT data FROM settings WHERE key=?',k);return r?JSON.parse(r.data):{};},async body(){return structuredClone(this.payload)},async rate(){},async audit(){}};
 a.db={async batch(ops){db.exec('BEGIN IMMEDIATE');try{const r=ops.map(({sql,args})=>({meta:{changes:Number(db.prepare(sql).run(...args).changes)}}));db.exec('COMMIT');return r;}catch(e){db.exec('ROLLBACK');throw e;}}};return a;
}
let virtual;
const a=adapter(),b=adapter('u2');
const prefs=async c=>virtual.privacyRoute(c,'/api/privacy/preferences','GET',fail);
async function acknowledge(c,consents={},acknowledged=true){const p=await prefs(c);c.payload={revision:p.revision,policyVersion:fixture.privacy.policyVersion,consents,acknowledged};return virtual.privacyRoute(c,'/api/privacy/preferences','PATCH',fail);}
const capabilities=async c=>aiGatewayRoute(c,'/api/ai-gateway/capabilities','GET',fail);
async function main(){
 const base=await bridge.globalBinding(fixture.privacy,{},fixture.gateway);assert(base);
 for(const test of fixture.cases)await check('fixture: '+test.name,async()=>{
  const value=structuredClone(fixture);for(const [dotted,replacement] of test.set||[]){const [owner,key]=ownerAt(value,dotted);owner[key]=replacement;}for(const dotted of test.delete||[]){const [owner,key]=ownerAt(value,dotted);delete owner[key];}for(const dotted of test.reverse||[]){const [owner,key]=ownerAt(value,dotted);owner[key].reverse();}
  const actual=await bridge.globalBinding(value.privacy,test.legacy?value.legacy:{},value.gateway);assert.equal(!!actual,test.valid);if(actual){if(test.mode==='legacy')assert.equal(actual.details.mode,undefined);else{assert.equal(actual.details.mode,'gateway-registry');assert.equal(actual.details.providerId,undefined);assert(!JSON.stringify(actual).includes('secretRef'));assert(!JSON.stringify(actual).includes('SYNTHETIC_SECRET_NOT_IN_DIGEST'));}if('sameAsBase' in test)assert.equal(actual.digest===base.digest,test.sameAsBase);}bindings[test.name]=actual?.digest||null;
 });
 await check('deterministic aggregate and legacy digests match independently executed Python fixtures',async()=>{const py=JSON.parse(fs.readFileSync(path.join(__dirname,'负责人优化建议-AI隐私桥接专项-python.json'))).latest;assert.equal(py.pass,true);assert.deepEqual(bindings,py.bindings);});
 await check('virtual integration reuses the exact idempotent installer without source writes',async()=>{
  const python=path.join(require('node:os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'),code="import importlib.util,json,sys;spec=importlib.util.spec_from_file_location('bridge_installer',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);p=m.prepare();print(json.dumps(p[m.CLOUD]['updated'],ensure_ascii=True))";
  const text=JSON.parse(execFileSync(python,['-B','-c',code,path.join(__dirname,'负责人优化建议-AI隐私桥接接入.py')],{encoding:'utf8',windowsHide:true}));
  const filename=path.join(CLOUD,'lib/privacy-api.ts'),virtualModule=new Module(filename,module);virtualModule.filename=filename;virtualModule.paths=Module._nodeModulePaths(path.dirname(filename));virtualModule._compile(ts.transpileModule(text,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText,filename);virtual=virtualModule.exports;assert(virtual.privacyRoute&&virtual.authorizeAI&&virtual.savePrivacyConversation);
 });
 set('privacy',fixture.privacy);set('ai',{});set('ai_gateway',fixture.gateway);a.aiGatewayPrivacyResponse=()=>prefs(a);b.aiGatewayPrivacyResponse=()=>prefs(b);
 await check('registry-only actual preferences PATCH acknowledges aggregate without creating provider receipts',async()=>{
  const original=await frozen.privacyRoute(a,'/api/privacy/preferences','GET',fail);assert.equal(original.disclosure.configured,false);let p=await prefs(a);assert.equal(p.disclosure.configured,true);assert.equal(p.disclosure.activeAI.mode,'gateway-registry');assert.equal(p.policyAcknowledged,false);p=await acknowledge(a);assert.equal(p.policyAcknowledged,true);assert.equal(p.providerBinding,base.digest);assert(Object.values(p.consents).every(v=>v===false));assert.deepEqual(p.authorizedCategories,['general','card']);await initAIGateway(a);assert.equal(db.prepare('SELECT count(*) n FROM ai_gateway_provider_consents').get().n,0);
 });
 await check('pure response hook equals virtual API and rejects a different account',async()=>{
  const original=await frozen.privacyRoute(a,'/api/privacy/preferences','GET',fail),actual=await bridge.bridgePrivacyResponse(original,{},fixture.gateway,undefined,'u1');assert.deepEqual(actual,await prefs(a));await assert.rejects(()=>bridge.bridgePrivacyResponse(original,{},fixture.gateway,undefined,'u2'));
 });
 await check('global aggregate does not bypass individual receipt or frozen legacy outbound/save gates',async()=>{
  const cap=await capabilities(a);assert.equal(cap.providers.find(p=>p.id==='alpha').authorization.receiptValid,false);await acknowledge(a,{saveConversations:true});assert.equal(await frozen.savePrivacyConversation(a,'u1',[{role:'user',content:'must not save through legacy aggregate'}]),false);await refused(()=>frozen.authorizeAI(a,{messages:[]},fail,'alpha',fixture.legacy),503);assert.equal(db.prepare('SELECT count(*) n FROM ai_gateway_provider_consents').get().n,0);
 });
 await check('actual per-provider consent creates only its receipt and stays account isolated',async()=>{
  let cap=await capabilities(a),auth=cap.providers.find(p=>p.id==='alpha').authorization;assert.notEqual(auth.providerBinding,base.digest);a.payload={acknowledged:true,policyVersion:auth.policyVersion,providerBinding:auth.providerBinding,categories:['general']};await aiGatewayRoute(a,'/api/ai-gateway/providers/alpha/consent','POST',fail);cap=await capabilities(a);assert.equal(cap.providers.find(p=>p.id==='alpha').authorization.receiptValid,true);assert.equal(cap.providers.find(p=>p.id==='beta').authorization.receiptValid,false);await acknowledge(b);assert.equal((await capabilities(b)).providers.find(p=>p.id==='alpha').authorization.receiptValid,false);assert.equal(db.prepare('SELECT count(*) n FROM ai_gateway_provider_consents').get().n,1);
 });
 await check('withdrawal invalidates all provider receipts and reconfirmation does not restore them',async()=>{
  const before=await prefs(a),after=await acknowledge(a,{},false);assert.equal(after.policyAcknowledged,false);assert.equal(after.providerBinding,'');assert.notEqual(before.consentEpoch,after.consentEpoch);assert.equal((await capabilities(a)).providers.find(p=>p.id==='alpha').authorization,null);await acknowledge(a);assert.equal((await capabilities(a)).providers.find(p=>p.id==='alpha').authorization.receiptValid,false);
 });
 await check('provider mutation invalidates aggregate while valid legacy preserves its original save semantics',async()=>{
  const before=await prefs(a),changed=structuredClone(fixture.gateway);changed.providers[0].model='alpha-next';set('ai_gateway',changed);let p=await prefs(a);assert.equal(p.policyAcknowledged,false);assert.notEqual(p.consentEpoch,before.consentEpoch);set('ai_gateway',fixture.gateway);set('ai',fixture.legacy);p=await acknowledge(a,{saveConversations:true});assert.equal(p.disclosure.activeAI.mode,undefined);assert.equal(p.providerBinding,bindings['valid legacy takes precedence']);assert.equal(await frozen.savePrivacyConversation(a,'u1',[{role:'user',content:'explicit legacy save'}]),true);
 });
 await check('frozen privacy source bytes remain unchanged on disk',async()=>assert.deepEqual(Object.fromEntries(frozenNames.map(n=>[n,sha(fs.readFileSync(path.join(ROOT,n)))])),before));
}
(async()=>{try{await main();}catch(e){results.push({name:'bridge test environment',pass:false,error:e.stack||String(e)});}finally{require.extensions['.ts']=priorTs;db.close();const report={at:new Date().toISOString(),scope:'Pure fixtures and transformed-in-memory actual privacy API/gateway receipt hooks. No frozen-source writes, provider/network calls, public entry or original DB.',productionWrites:false,pass:results.length>0&&results.every(r=>r.pass),passed:results.filter(r=>r.pass).length,failed:results.filter(r=>!r.pass).length,results,bindings,frozenSourceHashes:before,helperHash:sha(fs.readFileSync(path.join(CLOUD,'lib/privacy-gateway-bridge.ts')))};const file=path.join(__dirname,'负责人优化建议-AI隐私桥接专项-cloud.json'),history=fs.existsSync(file)?JSON.parse(fs.readFileSync(file)).runs||[]:[];history.push(report);fs.writeFileSync(file,JSON.stringify({latest:report,runs:history},null,2)+'\n');console.log(JSON.stringify({pass:report.pass,passed:report.passed,failed:report.failed}));process.exitCode=report.pass?0:1;}})();
