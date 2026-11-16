// Real TypeScript + native SQLite atomic D1 batches. No service/network/original DB.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict'),{DatabaseSync}=require('node:sqlite');
const ROOT=path.resolve(__dirname,'..'),cloud=path.join(ROOT,'04_研发源码/app/cloud'),ts=require(path.join(cloud,'node_modules/typescript')),prev=require.extensions['.ts'];
require.extensions['.ts']=(m,f)=>{let source=fs.readFileSync(f,'utf8');if(f===path.join(cloud,'lib/eastern-api.ts'))source+='\nexport const closureQaOnly={API,password,equal};';m._compile(ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,resolveJsonModule:true,esModuleInterop:true}}).outputText,f);};
const W=require(path.join(cloud,'lib/account-write-guard.ts'));
const M=require(path.join(cloud,'lib/account-closure.ts')),R=require(path.join(cloud,'lib/privacy-retention.ts')),E=require(path.join(cloud,'lib/eastern-api.ts')).closureQaOnly,results=[];
class StatusError extends Error{constructor(status,message){super(message);this.status=status;}}
const fail=(n,s)=>{throw new StatusError(n,s)},hash=s=>crypto.createHash('sha256').update(s).digest('hex'),expect=(n,f)=>assert.rejects(f,e=>e.status===n);
async function check(name,fn){try{await fn();results.push({name,pass:true});}catch(e){results.push({name,pass:false,error:e.stack});}}
async function fixture(){
 const db=new DatabaseSync(':memory:');db.exec(fs.readFileSync(path.join(cloud,'drizzle/0000_lethal_lucky_pierre.sql'),'utf8'));
 const hooks={beforeBatch:null,beforeRun:null},adapter={
  prepare(sql){return {sql,args:[],bind(...args){this.args=args;return this;},async first(){return db.prepare(sql).get(...this.args)||null;},async all(){return {results:db.prepare(sql).all(...this.args)};},async run(){if(hooks.beforeRun)await hooks.beforeRun(sql,this.args);const r=db.prepare(sql).run(...this.args);return {meta:{changes:Number(r.changes)}};}}},
  async batch(ops){if(hooks.beforeBatch)await hooks.beforeBatch(ops);db.exec('BEGIN IMMEDIATE');try{const out=ops.map(x=>{if(/\bRETURNING\b|^\s*SELECT/i.test(x.sql)){const rows=db.prepare(x.sql).all(...x.args);return {results:rows,meta:{changes:db.prepare('SELECT changes() n').get().n}};}const r=db.prepare(x.sql).run(...x.args);return {meta:{changes:Number(r.changes)}}});db.exec('COMMIT');return out;}catch(e){db.exec('ROLLBACK');throw e;}}
 };
 const password=await E.password('fixture-password-123'),stamp=Date.now();
 let a=new E.API(new Request('https://fixture.invalid/api/health'),{DB:adapter,DEMO_ADMIN_HASH:password});await a.init();await R.initPrivacyRetention(a);await M.initAccountClosure(a);
 for(const [id,role] of [['buyer','user'],['other','user'],['admin2','admin']])db.prepare('INSERT INTO users VALUES(?,?,?,?,?,?)').run(id,'qa_'+id,password,'QA',role,stamp);
 for(const id of ['buyer','other','admin2','cloud-owner'])db.prepare('INSERT INTO sessions VALUES(?,?,?)').run(hash('fixture-session-'+id),id,stamp+86400000);
 db.prepare('INSERT INTO sessions VALUES(?,?,?)').run(hash('fixture-session-buyer-second'),'buyer',stamp+86400000);
 for(const id of ['buyer','other']){
  db.prepare('INSERT INTO records VALUES(?,?,?,?,?)').run(id,'life','2026-01-01','{"fixture":true}',stamp);
  db.prepare('INSERT INTO privacy_conversations VALUES(?,?,?,?)').run(id+'-snapshot',id,'[]',stamp);
  db.prepare('INSERT INTO privacy_preferences VALUES(?,?,?,?,?,?)').run(id,JSON.stringify({chart:true,wellbeing:true,saveConversations:true,longTermMemory:true,trainingImprovement:true,marketing:true}),'fixture',8,stamp,'binding');
  db.prepare('INSERT INTO ai_gateway_provider_consents VALUES(?,?,?,?,?,?,?,?,?)').run(id,'fixture','binding','fixture',8,'["general"]',stamp,stamp,'old-nonce');
 }
 function actor(id='buyer',token='fixture-session-'+id){
  const x=new E.API(new Request('https://fixture.invalid/api/account-closure/status'),{DB:adapter});
  x.user=db.prepare('SELECT * FROM users WHERE id=?').get(id);x.owner=id;x.visitor='a'.repeat(32);x.token=token;x.payload={};x.body=async()=>structuredClone(x.payload);x.rate=async()=>{};return x;
 }
 const f={db,hooks,actor,now:stamp};f.user=actor();f.call=async(p,d={},who=f.user,m='POST',cleanup)=>{who.payload=d;who.url=new URL('https://fixture.invalid/api/account-closure/'+p);who.method=m;return M.accountClosureRoute(who,who.url.pathname,m,fail,{verifyPassword:async(plain,stored)=>E.equal(stored,await E.password(plain,stored.split(':')[0])),clock:()=>f.now,...(cleanup?{cleanup}:{})});};
 f.prepare=async(who=f.user,key='fixture-request',nonce='a'.repeat(64))=>{const r=await f.call('prepare',{requestId:key,nonce,password:'fixture-password-123'},who);return {requestId:key,nonce,challengeId:r.challengeId,confirmed:true,renewalAcknowledged:true};};
 f.close=async(who=f.user)=>f.call('confirm',await f.prepare(who),who);
 f.scalar=(s,...args)=>Object.values(db.prepare(s).get(...args))[0];return f;
}
(async()=>{
await check('actual TS verifier, authority cleanup and all sessions revoked atomically; other owner kept',async()=>{const f=await fixture(),r=await f.close();assert.equal(r.receipt.accountClosed,true);assert.equal(r.receipt.providersStatus,'pending-confirmation');assert.equal(r.receipt.thirdPartyRenewalCancelled,false);assert.equal(f.scalar("SELECT count(*) FROM sessions WHERE user_id='buyer'"),0);assert.equal(f.scalar("SELECT count(*) FROM account_revoked_sessions WHERE owner='buyer'"),2);assert.equal(f.scalar("SELECT count(*) FROM records WHERE owner='buyer'"),0);assert.equal(f.scalar("SELECT count(*) FROM privacy_conversations WHERE user_id='buyer'"),0);assert.equal(f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'"),9);assert.equal(f.scalar("SELECT provider_binding FROM privacy_preferences WHERE user_id='buyer'"),'');assert.equal(f.scalar("SELECT global_revision FROM ai_gateway_provider_consents WHERE owner='buyer'"),-1);assert.notEqual(f.scalar("SELECT revision FROM ai_gateway_provider_consents WHERE owner='buyer'"),'old-nonce');assert.equal(f.scalar("SELECT count(*) FROM records WHERE owner='other'"),1);assert.equal(f.scalar("SELECT count(*) FROM users WHERE id='buyer'"),1);const invalidated=f.scalar("SELECT password FROM users WHERE id='buyer'");assert.equal(E.equal(invalidated,await E.password('fixture-password-123',invalidated.split(':')[0])),false);assert.deepEqual(f.user.cookies,[]);});
await check('password required and actual existing Cloud password verifier rejects wrong password',async()=>{const f=await fixture();await expect(401,()=>f.call('prepare',{requestId:'fixture-request',nonce:'a'.repeat(64),password:'wrong'}));assert.equal(f.scalar('SELECT count(*) FROM account_closure_challenges'),0);});
await check('both explicit confirmations are strict and do not create a closure claim',async()=>{const f=await fixture(),d=await f.prepare();for(const [key,value] of [['confirmed',false],['confirmed',1],['renewalAcknowledged',false]])await expect(400,()=>f.call('confirm',{...d,[key]:value}));assert.equal(f.scalar('SELECT count(*) FROM account_closure_receipts'),0);});
await check('challenge is owner/current-session bound; foreign owner and second session cannot confirm',async()=>{const f=await fixture(),d=await f.prepare();await expect(404,()=>f.call('confirm',d,f.actor('other')));await expect(404,()=>f.call('confirm',d,f.actor('buyer','fixture-session-buyer-second')));});
await check('expired final challenge rolls back complete D1 batch',async()=>{const f=await fixture(),d=await f.prepare();f.now+=M.CHALLENGE_TTL_MS;await expect(409,()=>f.call('confirm',d));assert.equal(f.scalar('SELECT count(*) FROM account_closure_receipts'),0);assert.equal(f.scalar("SELECT count(*) FROM records WHERE owner='buyer'"),1);});
await check('session/password revocation just before final D1 batch blocks all cleanup',async()=>{const f=await fixture(),d=await f.prepare();f.hooks.beforeBatch=async ops=>{if(ops[0]?.sql.startsWith('INSERT INTO account_closure_receipts')){f.hooks.beforeBatch=null;f.db.prepare("DELETE FROM sessions WHERE user_id='buyer'").run();}};await expect(409,()=>f.call('confirm',d));assert.equal(f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'"),8);});
await check('changing same request nonce/session returns conflict',async()=>{const f=await fixture();await f.prepare();await expect(409,()=>f.prepare(f.user,'fixture-request','b'.repeat(64)));});
await check('completed replay needs original strong nonce, returns same receipt without re-cleanup or Set-Cookie',async()=>{const f=await fixture(),d=await f.prepare(),r=await f.call('confirm',d);f.user.user=null;assert.deepEqual((await f.call('confirm',d)).receipt,r.receipt);assert.equal(f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'"),9);await expect(404,()=>f.call('confirm',{...d,nonce:'b'.repeat(64)}));await expect(404,()=>f.call('confirm',d,f.actor('other')));assert.deepEqual(f.user.cookies,[]);});
await check('two prepared administrators cannot close the last active admin',async()=>{const f=await fixture(),a=f.actor('cloud-owner'),b=f.actor('admin2'),da=await f.prepare(a),db=await f.prepare(b);await f.call('confirm',da,a);await expect(409,()=>f.call('confirm',db,b));assert.equal(f.scalar("SELECT count(*) FROM sessions WHERE user_id='admin2'"),1);assert.equal((await f.call('status',{},b,'GET')).lastActiveAdmin,true);});
await check('concurrent same challenge claims commit once and replay original receipt',async()=>{const f=await fixture(),d=await f.prepare(),out=await Promise.all([f.call('confirm',d,f.actor()),f.call('confirm',d,f.actor())]);assert.equal(out[0].receipt.id,out[1].receipt.id);assert.equal(f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'"),9);assert.equal(f.scalar('SELECT count(*) FROM account_closure_receipts'),1);});
await check('late owned INSERT/UPDATE and session issuance cannot resurrect closed personal data',async()=>{const f=await fixture();await f.close();for(const [s,args] of [["INSERT INTO records VALUES(?,?,?,?,?)",['buyer','life','2026-01-02','{}',f.now]],['INSERT INTO privacy_conversations VALUES(?,?,?,?)',['late','buyer','[]',f.now]],['INSERT INTO sessions VALUES(?,?,?)',['late','buyer',f.now+999]],["UPDATE privacy_preferences SET data='{}' WHERE user_id='buyer'",[]],["UPDATE users SET password='tamper' WHERE id='buyer'",[]]])assert.throws(()=>f.db.prepare(s).run(...args),/account_closed/);});
await check('old cookie cannot downgrade into visitor writes; static/public read and new login stay reachable',async()=>{const f=await fixture();await f.close();const a=f.actor();a.url=new URL('https://fixture.invalid/api/records');a.method='POST';await expect(401,()=>M.refreshAccountAuth(a,fail));assert.equal(a.user,null);a.url=new URL('https://fixture.invalid/api/public');a.method='GET';await M.refreshAccountAuth(a,fail);a.url=new URL('https://fixture.invalid/api/auth/login');a.method='POST';await M.refreshAccountAuth(a,fail);assert.deepEqual(a.cookies,[]);await expect(401,()=>M.requireAccountActive(a,'buyer',fail));});
await check('new closed account login cookie insert is denied by DB final guard',async()=>{const f=await fixture();await f.close();await assert.rejects(()=>f.user.login('buyer'),/account_closed/);assert.equal(f.scalar("SELECT count(*) FROM sessions WHERE user_id='buyer'"),0);});
await check('authority failure rolls full batch back including closure/nonce/session state',async()=>{const f=await fixture(),d=await f.prepare(),cleanup=async(...args)=>{const c=await R.closureCleanupStatements(...args);return {...c,statements:[...c.statements,f.user.stmt('INSERT INTO NONEXISTENT_TABLE VALUES(1)')]};};await assert.rejects(()=>f.call('confirm',d,f.user,'POST',cleanup));assert.equal(f.scalar('SELECT count(*) FROM account_closure_receipts'),0);assert.equal(f.scalar("SELECT count(*) FROM records WHERE owner='buyer'"),1);assert.equal(f.scalar("SELECT revision FROM privacy_preferences WHERE user_id='buyer'"),8);assert.equal(f.scalar("SELECT count(*) FROM sessions WHERE user_id='buyer'"),2);});
await check('response contains no password/session/nonce/hash and closure never rewrites wallet or source audit',async()=>{const f=await fixture();f.db.prepare('INSERT INTO ai_gateway_wallets VALUES(?,100,0,?)').run('buyer',f.now);const before=f.db.prepare('SELECT * FROM ai_gateway_wallets').all(),r=await f.close(),s=JSON.stringify(r);for(const k of ['fixture-password','fixture-session','nonce_hash','operation_nonce'])assert(!s.includes(k));assert.deepEqual(f.db.prepare('SELECT * FROM ai_gateway_wallets').all(),before);f.db.prepare("UPDATE ai_gateway_wallets SET balance=99 WHERE owner='buyer'").run();assert.equal(f.scalar("SELECT balance FROM ai_gateway_wallets WHERE owner='buyer'"),99);});

function guarded(f,id='buyer'){
 const a=f.actor(id),old=a.require.bind(a);a.db=W.bindAccountDatabase(a,a.db);a.require=roles=>{const u=old(roles);W.accountRequiredRoles(a,roles);return u;};return a;
}
async function bodyRace(kind){
 const f=await fixture(),id=['settings','role'].includes(kind)?'admin2':'buyer',a=guarded(f,id);a.method=kind==='role'?'PATCH':'POST';
 let release,readyResolve;const ready=new Promise(r=>readyResolve=r),body=new Promise(r=>release=r);
 a.body=()=>{readyResolve();return body;};
 let operation;
 const before={settings:f.db.prepare('SELECT * FROM settings').all(),role:f.scalar("SELECT role FROM users WHERE id='other'"),posts:f.scalar('SELECT count(*) FROM posts'),media:f.scalar('SELECT count(*) FROM media')};
 const objects=new Map();
 if(kind==='settings')operation=a.settings();
 else if(kind==='role')operation=a.admin('/api/admin/users/other');
 else if(kind==='community')operation=a.community('/api/community/posts');
 else{
  const bytes=new Uint8Array([137,80,78,71,13,10,26,10]);
  a.request={headers:new Headers({'content-length':'8','content-type':'image/png','x-filename':'fixture.png'}),arrayBuffer:()=>{readyResolve();return body;}};
  a.env.BUCKET={async put(k,v){objects.set(k,v);},async delete(k){objects.delete(k);}};
  operation=a.upload();
 }
 // Register rejection handling before releasing the body.
 const rejected=assert.rejects(operation,/account_actor_inactive|account_closed/);
 await ready;await f.close(f.actor(id));
 release(kind==='settings'?{theme:{'--bg':'#123456'}}:kind==='role'?{role:'teacher'}:kind==='community'?{title:'late',body:'late',status:'pending'}:new Uint8Array([137,80,78,71,13,10,26,10]).buffer);
 await rejected;
 assert.deepEqual(f.db.prepare('SELECT * FROM settings').all(),before.settings);
 assert.equal(f.scalar("SELECT role FROM users WHERE id='other'"),before.role);
 assert.equal(f.scalar('SELECT count(*) FROM posts'),before.posts);
 assert.equal(f.scalar('SELECT count(*) FROM media'),before.media);
 assert.equal(objects.size,0);assert.equal(f.scalar('SELECT count(*) FROM account_action_fences'),0);
}
await check('real API.settings require passed then body waited; closure wins and no settings change',()=>bodyRace('settings'));
await check('real API.admin role require passed then body waited; closure wins and target role unchanged',()=>bodyRace('role'));
await check('real API.community body waited after require; closed author cannot publish late',()=>bodyRace('community'));
await check('real API.upload arrayBuffer waited after require; closed user cannot upload; temporary R2 object cleaned',()=>bodyRace('upload'));
await check('guarded prepare.run, DML RETURNING all/first and batch all check final actor atomically',async()=>{
 const f=await fixture(),a=guarded(f,'admin2');a.require(['admin']);await f.close(f.actor('admin2'));
 for(const run of [()=>a.stmt("UPDATE settings SET data='{}' WHERE key='theme'").run(),()=>a.stmt("UPDATE settings SET data='{}' WHERE key='theme' RETURNING key").all(),()=>a.stmt("UPDATE settings SET data='{}' WHERE key='theme' RETURNING key").first(),()=>a.db.batch([a.stmt("UPDATE settings SET data='{}' WHERE key='theme'")])])await assert.rejects(run,/account_actor_inactive/);
 assert.equal(f.scalar('SELECT count(*) FROM account_action_fences'),0);
});
await check('fresh required role is checked at final statement even if account stays active',async()=>{
 const f=await fixture(),a=guarded(f,'admin2');a.require(['admin']);f.db.prepare("UPDATE users SET role='user' WHERE id='admin2'").run();
 await assert.rejects(()=>a.run("UPDATE settings SET data='{}' WHERE key='theme'"),/account_actor_inactive/);
});
await check('closure itself works through guarded D1 batch despite deleting its own session; no credential fence remains',async()=>{
 const f=await fixture(),a=guarded(f),d=await f.prepare(a);const r=await f.call('confirm',d,a);
 assert.equal(r.receipt.accountClosed,true);assert.equal(f.scalar('SELECT count(*) FROM account_action_fences'),0);
});
await check('existing gateway fact can finish charged settlement after closure; trusted scope cannot write settings/new jobs/body',async()=>{
 const f=await fixture();f.db.prepare('INSERT INTO ai_gateway_wallets VALUES(?,100,0,?)').run('buyer',f.now);
 const v={id:'existing-job',owner:'buyer',request_id:'job-request',fingerprint:'fixture',scene:'chat',environment:'local-test',status:'queued',cancel_requested:0,reserve_credits:5,charged_credits:null,policy_snapshot:'{"ruleVersion":"fixture","cancelCredits":2}',provider_snapshot:'{}',route_snapshot:'{}',config_revision:1,provider_id:'fixture',has_output:0,output_chars:0,output_text:null,usage:null,error_code:'',lease_until:f.now+10000,created:f.now,updated:f.now,saved_conversation_id:null};
 f.db.prepare('INSERT INTO ai_gateway_jobs('+Object.keys(v).join(',')+') VALUES('+Object.keys(v).map(()=>'?').join(',')+')').run(...Object.values(v));
 f.db.prepare("UPDATE ai_gateway_jobs SET status='running' WHERE id='existing-job'").run();
 const a=guarded(f);await f.close();const service=await W.trustedSettlementApi(a,'gateway','existing-job','buyer');
 await service.run("UPDATE ai_gateway_jobs SET status='cancelled',charged_credits=2,output_text=NULL,saved_conversation_id=NULL WHERE id='existing-job' AND owner='buyer' AND status='running'");
 assert.equal(f.scalar("SELECT balance FROM ai_gateway_wallets WHERE owner='buyer'"),98);
 assert.equal(f.scalar("SELECT reserved FROM ai_gateway_wallets WHERE owner='buyer'"),0);
 await assert.rejects(()=>service.run("UPDATE settings SET data='{}' WHERE key='theme'"),/account_settlement_denied/);
 await assert.rejects(()=>service.run("INSERT INTO privacy_conversations VALUES('bad','buyer','[]',1)"),/account_settlement_denied/);
 await assert.rejects(()=>service.run("INSERT INTO ai_gateway_jobs SELECT * FROM ai_gateway_jobs WHERE 0"),/account_settlement_denied/);
 await assert.rejects(()=>W.trustedSettlementApi(a,'gateway','nonexistent','buyer'),/account_settlement_denied/);
});
await check('verified-session internal path can issue after legitimate old-session deletion but cannot write arbitrary settings',async()=>{
 const f=await fixture(),a=guarded(f,'admin2');f.db.prepare("DELETE FROM sessions WHERE user_id='admin2'").run();
 const service=await W.verifiedSessionApi(a,'admin2');await service.run('INSERT INTO sessions VALUES(?,?,?)',hash('new-proof-session'),'admin2',f.now+10000);
 assert.equal(f.scalar("SELECT count(*) FROM sessions WHERE user_id='admin2'"),1);
 await assert.rejects(()=>service.run("UPDATE settings SET data='{}' WHERE key='theme'"),/account_settlement_denied/);
});
await check('closed recipients/teacher cannot receive new friend/message/booking/device facts; retained message remains',async()=>{
 const f=await fixture();
 f.db.prepare("INSERT INTO contents VALUES('teachers','fixture-teacher',?,'published',0,?)").run(JSON.stringify({id:'fixture-teacher',creatorId:'buyer',profileType:'real',verified:true}),f.now);
 f.db.prepare("INSERT INTO messages VALUES('retained','other','buyer','fixture',?)").run(f.now);
 await f.close();
 for(const [s,args] of [["INSERT INTO friendships VALUES('other','buyer','pending',?)",[f.now]],["INSERT INTO messages VALUES('late','other','buyer','fixture',?)",[f.now]],["INSERT INTO service_requests VALUES('late','other','fixture-teacher','QA','fixture','2026-12-01','pending',?)",[f.now]]])assert.throws(()=>f.db.prepare(s).run(...args),/account_target_closed/);
 assert.equal(await M.canBookTeacher(f.user,'fixture-teacher',{creatorId:'buyer'}),false);
 assert.equal(f.scalar("SELECT count(*) FROM messages WHERE id='retained'"),1);
 assert.throws(()=>f.db.prepare("UPDATE users SET role='admin' WHERE id='buyer'").run(),/account_closed/);
});


await check('actual unified refund kind is refund; internal order gate accepts that existing applied fact independently of pay match',async()=>{
 const f=await fixture(),C=require(path.join(cloud,'lib/commerce-api.ts')),admin=f.actor('cloud-owner');
 async function commerce(a,p,d,method='POST'){a.payload=d;a.url=new URL(p,'https://fixture.invalid');return C.commerceRoute(a,p,method,fail);}
 await commerce(admin,'/api/admin/commerce/settings',{sandboxEnabled:true,productionEnabled:false},'PATCH');
 const p=await commerce(admin,'/api/admin/commerce/products',{title:'QA',description:'QA',type:'physical',sku:'refund-kind-fixture',priceMinor:100,currency:'USD',stock:2,shippingCountries:['US'],shippingMinor:0,taxMinor:0,environment:'sandbox',status:'published'});
 const o=await commerce(f.user,'/api/commerce/orders',{requestId:'fixture-order-request',environment:'sandbox',items:[{skuId:p.item.skuId,quantity:1}],shippingAddress:{name:'QA',phone:'000000',country:'US',city:'QA',address:'QA',postalCode:'000'}});
 const paid=await commerce(f.user,'/api/commerce/orders/'+o.id+'/sandbox-pay',{requestId:'fixture-paid-request'});
 const refunded=await commerce(admin,'/api/admin/commerce/orders/'+o.id+'/refund',{requestId:'fixture-refund-request',items:[{itemId:paid.items[0].id,quantity:1}]});
 assert(refunded.events.some(e=>e.kind==='refund'&&e.status==='applied'));
 const raw=f.user.db,filtered=new Proxy(raw,{get(t,k){if(k==='prepare')return sql=>t.prepare(sql.includes('commerce_payment_events p')?sql.replace(/p\.kind IN \([^)]+\)/,"$& AND p.kind='refund'"):sql);const v=Reflect.get(t,k,t);return typeof v==='function'?v.bind(t):v;}});
 const actor=Object.create(f.user);actor.db=filtered;
 const service=await W.trustedSettlementApi(actor,'order',o.id,'buyer');
 await service.run("UPDATE membership_subscriptions SET updated=updated WHERE owner='buyer'");
});

const out=__filename.replace(/\.cjs$/,'.json'),report={scope:'actual TS+native SQLite/D1 atomic batches and existing Cloud password verifier; no HTTP/original DB/provider',passed:results.filter(x=>x.pass).length,failed:results.filter(x=>!x.pass).length,results,sourceSha256:Object.fromEntries(['account-closure.ts','account-write-guard.ts','privacy-retention.ts'].map(n=>[n,hash(fs.readFileSync(path.join(cloud,'lib',n)))]))},old=fs.existsSync(out)?JSON.parse(fs.readFileSync(out)):{};fs.writeFileSync(out,JSON.stringify({latest:report,runs:[...(old.runs||[]),report]},null,2)+'\n');console.log(JSON.stringify({passed:report.passed,failed:report.failed}));require.extensions['.ts']=prev;process.exitCode=report.failed?1:0;
})().catch(e=>{console.error(e);process.exitCode=1;});
