// Final local closure; third-party renewals/providers/backups remain unverified.
import {closureCleanupStatements} from './privacy-retention';
import {initAccountWriteGuard} from './account-write-guard';
export const ACCOUNT_CLOSURE_DDL:string[]=["CREATE TABLE IF NOT EXISTS account_revoked_sessions(token_hash TEXT PRIMARY KEY,owner TEXT NOT NULL,revoked_at INTEGER NOT NULL)","CREATE TABLE IF NOT EXISTS account_lifecycle(owner TEXT PRIMARY KEY REFERENCES users(id),status TEXT NOT NULL CHECK(status IN ('active','closed')),epoch INTEGER NOT NULL CHECK(epoch>=1),closed_at INTEGER,receipt_id TEXT)","CREATE TABLE IF NOT EXISTS account_closure_challenges(id TEXT PRIMARY KEY,owner TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,nonce_hash TEXT NOT NULL,session_hash TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,consumed INTEGER NOT NULL DEFAULT 0,UNIQUE(owner,request_id))","CREATE TABLE IF NOT EXISTS account_closure_receipts(id TEXT PRIMARY KEY,owner TEXT NOT NULL REFERENCES users(id),challenge_id TEXT NOT NULL UNIQUE,request_id TEXT NOT NULL,nonce_hash TEXT NOT NULL,operation_nonce TEXT NOT NULL,created INTEGER NOT NULL,details TEXT NOT NULL,UNIQUE(owner,request_id))","CREATE TRIGGER IF NOT EXISTS account_closure_claim BEFORE INSERT ON account_closure_receipts BEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM account_closure_challenges c JOIN sessions s ON s.token=c.session_hash AND s.user_id=c.owner JOIN users u ON u.id=c.owner WHERE c.id=NEW.challenge_id AND c.owner=NEW.owner AND c.request_id=NEW.request_id AND c.nonce_hash=NEW.nonce_hash AND c.consumed=0 AND c.expires>NEW.created AND s.expires>NEW.created) THEN RAISE(ABORT,'account_closure_challenge_invalid') END;\n SELECT CASE WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') THEN RAISE(ABORT,'account_closed') END;\n SELECT CASE WHEN EXISTS(SELECT 1 FROM users WHERE id=NEW.owner AND role='admin') AND (SELECT count(*) FROM users u WHERE u.role='admin' AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))<=1 THEN RAISE(ABORT,'account_closure_last_admin') END;\n END","CREATE TRIGGER IF NOT EXISTS account_lifecycle_no_reopen BEFORE UPDATE ON account_lifecycle WHEN OLD.status='closed' BEGIN SELECT RAISE(ABORT,'account_closed'); END"];
const GUARDS:Record<string,[string,string]>={"users":["NEW.id","both"],"sessions":["NEW.user_id","both"],"records":["NEW.owner","both"],"timer_runs":["NEW.owner","both"],"activity_daily":["NEW.user_id","both"],"devices":["NEW.owner","both"],"measurements":["(SELECT owner FROM devices WHERE id=NEW.connection_id)","both"],"privacy_preferences":["NEW.user_id","both"],"privacy_conversations":["NEW.user_id","both"],"ai_gateway_provider_consents":["NEW.owner","both"],"card_draws":["NEW.owner","both"],"card_draw_actions":["NEW.owner","both"],"card_practice_events":["NEW.owner","both"],"card_draw_requests":["NEW.owner","both"],"posts":["NEW.author_id","insert"],"messages":["NEW.sender","insert"],"service_requests":["NEW.user_id","insert"],"media":["NEW.owner","insert"],"creator_works":["NEW.owner_id","insert"]};
export const CHALLENGE_TTL_MS=300000;
const hash=async(s:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))).map(x=>x.toString(16).padStart(2,'0')).join('');
const uuid=()=>crypto.randomUUID(),json=JSON.stringify;
const randomHex=(n:number)=>Array.from(crypto.getRandomValues(new Uint8Array(n))).map(x=>x.toString(16).padStart(2,'0')).join('');
export function accountGuardStatements(tables:Set<string>){
 const out:string[]=[];
 for(const [table,[owner,mode]] of Object.entries(GUARDS))if(tables.has(table))for(const action of mode==='both'?['INSERT','UPDATE']:['INSERT'])
  out.push(`CREATE TRIGGER IF NOT EXISTS account_closed_${table}_${action.toLowerCase()} BEFORE ${action} ON ${table} WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=${owner} AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END`);
 if(tables.has('ai_gateway_jobs'))out.push(
 "CREATE TRIGGER IF NOT EXISTS account_closed_ai_job_insert BEFORE INSERT ON ai_gateway_jobs WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END",
 "CREATE TRIGGER IF NOT EXISTS account_closed_ai_job_body BEFORE UPDATE OF output_text,saved_conversation_id ON ai_gateway_jobs WHEN (NEW.output_text IS NOT NULL OR NEW.saved_conversation_id IS NOT NULL) AND EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END");
 if(tables.has('friendships'))for(const action of ['INSERT','UPDATE'])out.push(`CREATE TRIGGER IF NOT EXISTS account_closed_friend_target_${action.toLowerCase()} BEFORE ${action} ON friendships WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE status='closed' AND owner IN (NEW.sender,NEW.recipient)) BEGIN SELECT RAISE(ABORT,'account_target_closed'); END`);
 if(tables.has('messages'))out.push("CREATE TRIGGER IF NOT EXISTS account_closed_message_target BEFORE INSERT ON messages WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.recipient AND status='closed') BEGIN SELECT RAISE(ABORT,'account_target_closed'); END");
 if(tables.has('service_requests')&&tables.has('creator_profiles'))out.push("CREATE TRIGGER IF NOT EXISTS account_closed_service_target BEFORE INSERT ON service_requests WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE status='closed' AND (owner=NEW.teacher_id OR owner IN (SELECT user_id FROM creator_profiles WHERE teacher_id=NEW.teacher_id) OR owner IN (SELECT json_extract(data,'$.creatorId') FROM contents WHERE kind='teachers' AND id=NEW.teacher_id))) BEGIN SELECT RAISE(ABORT,'account_target_closed'); END");
 return out;
}
export async function initAccountClosure(a:any,guards=true){
 // Called once before session lookup, again after all personal schemas for guards.
 if(!await a.one("SELECT 1 FROM settings WHERE key='account_closure_schema_v1'")){
  await a.db.batch(ACCOUNT_CLOSURE_DDL.map(s=>a.stmt(s)));
  await a.run("INSERT OR IGNORE INTO settings VALUES('account_closure_schema_v1','true')");
 }
 await initAccountWriteGuard(a);
 if(guards){
  const tables=new Set<string>((await a.all("SELECT name FROM sqlite_master WHERE type='table'")).map((r:any)=>r.name));
  const statements=accountGuardStatements(tables);
  if(statements.length)await a.db.batch(statements.map(s=>a.stmt(s)));
 }
}
export async function canBookTeacher(a:any,teacherId:string,profile:any){
 const owners=[teacherId,profile.creatorId,...(await a.all('SELECT user_id FROM creator_profiles WHERE teacher_id=?',teacherId)).map((r:any)=>r.user_id)].filter(Boolean);
 for(const owner of owners)if(!await accountIsActive(a,owner))return false;return true;
}
export async function accountIsActive(a:any,owner:string){return !await a.one("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed'",owner);}
export async function requireAccountActive(a:any,owner:string,fail:(n:number,s:string)=>never){if(!await accountIsActive(a,owner))fail(401,'账号已关闭，请使用其他账号。');}
export async function refreshAccountAuth(a:any,fail:(n:number,s:string)=>never){
 const token=a.token||'';
 if(a.user&&!await accountIsActive(a,a.user.id)){a.user=null;a.owner='visitor:'+a.visitor;}
 if(token){a.user=await a.one("SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')",await hash(token),Date.now());a.owner=a.user?.id||'visitor:'+a.visitor;}
 if(!token)return;
 const revoked=await a.one('SELECT 1 FROM account_revoked_sessions WHERE token_hash=?',await hash(token));
 const p=a.url.pathname.replace(/\/+$/,'');
 if(revoked&&!['GET','HEAD'].includes(a.method)&&!['/api/public','/api/health','/api/auth/status','/api/auth/login','/api/auth/register','/api/auth/setup','/api/auth/logout','/api/account-closure/confirm'].includes(p)){
  fail(401,'账号已关闭，请使用其他账号。');
 }
}
function validate(d:any,keys:string[],fail:(n:number,s:string)=>never){
 if(!d||typeof d!=='object'||Array.isArray(d)||Object.keys(d).some(k=>!keys.includes(k)))fail(400,'请求包含不支持的字段。');
 if(typeof d.requestId!=='string'||! /^[A-Za-z0-9_.:-]{8,100}$/.test(d.requestId))fail(400,'需要8至100位幂等编号。');
 if(typeof d.nonce!=='string'||! /^[a-f0-9]{64}$/.test(d.nonce))fail(400,'需要本次确认凭证。');
}
function receipt(r:any){
 return {receipt:{id:r.id,status:'closed',accountClosed:true,sessionsRevoked:true,credentialVerifierInvalidated:true,closedAt:r.created,local:JSON.parse(r.details),
 providersStatus:'pending-confirmation',backupsStatus:'pending-confirmation',thirdPartyRenewalCancelled:false,localBrowserCleared:false},reauthenticate:true};
}
type Options={verifyPassword:(plain:string,stored:string)=>Promise<boolean>,clock?:()=>number,cleanup?:typeof closureCleanupStatements};
export async function accountClosureRoute(a:any,p:string,m:string,fail:(n:number,s:string)=>never,options:Options){
 if(!p.startsWith('/api/account-closure'))return undefined;
 const stamp=options.clock?.()??Date.now();
 if(p==='/api/account-closure/status'&&m==='GET'){
  const u=a.require();await requireAccountActive(a,u.id,fail);
  const count=await a.one("SELECT count(*) n FROM users u WHERE role='admin' AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')");
  return {accountId:u.id,accountClosed:false,canClose:u.role!=='admin'||count.n>1,lastActiveAdmin:u.role==='admin'&&count.n<=1,
  passwordConfirmationSeconds:CHALLENGE_TTL_MS/1000,thirdPartyRenewalCancelled:false,providersStatus:'pending-confirmation',backupsStatus:'pending-confirmation'};
 }
 if(m!=='POST'||!['/api/account-closure/prepare','/api/account-closure/confirm'].includes(p))fail(404,'未找到此账号关闭接口。');
 const d=await a.body();
 if(p.endsWith('/prepare')){
  validate(d,['requestId','nonce','password'],fail);
  const u=a.require(),owner=u.id;await a.rate('closure-prepare:'+owner,5);
  if(typeof d.password!=='string'||d.password.length<1||d.password.length>128)fail(400,'需要本人当前密码。');
  await requireAccountActive(a,owner,fail);
  const live=await a.one('SELECT * FROM users WHERE id=?',owner);
  if(!live||!await options.verifyPassword(d.password,live.password))fail(401,'当前密码不正确。');
  const nh=await hash(d.nonce),sh=await hash(a.token||''),id=uuid();
  // Final conditional INSERT also guards password change/session/closure during verifier await.
  await a.run("INSERT OR IGNORE INTO account_closure_challenges SELECT ?,?,?,?,?,?,?,0 WHERE EXISTS(SELECT 1 FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.user_id=? AND s.expires>? AND u.password=?) AND NOT EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed')",
   id,owner,d.requestId,nh,sh,stamp,stamp+CHALLENGE_TTL_MS,sh,owner,stamp,live.password,owner);
  const row=await a.one('SELECT * FROM account_closure_challenges WHERE owner=? AND request_id=?',owner,d.requestId);
  if(!row)fail(409,'账号状态已变化，请重新登录确认。');
  if(row.nonce_hash!==nh||row.session_hash!==sh)fail(409,'确认编号已用于另一操作。');
  return {challengeId:row.id,expiresAt:row.expires,secondConfirmationRequired:true,accountClosed:false,thirdPartyRenewalCancelled:false};
 }
 validate(d,['requestId','nonce','challengeId','confirmed','renewalAcknowledged'],fail);
 if(d.confirmed!==true||d.renewalAcknowledged!==true)fail(400,'请明确确认关闭账号及第三方续费提示。');
 if(typeof d.challengeId!=='string'||d.challengeId.length<1||d.challengeId.length>100)fail(400,'确认凭证无效。');
 const nh=await hash(d.nonce),cid=d.challengeId;
 await a.rate('closure-confirm:'+(await hash(cid)).slice(0,24),10);
 let old=await a.one('SELECT * FROM account_closure_receipts WHERE challenge_id=?',cid);
 if(old){if((a.user&&a.user.id!==old.owner)||old.request_id!==d.requestId||old.nonce_hash!==nh)fail(404,'确认凭证无效。');return receipt(old);}
 const u=a.require(),owner=u.id;await requireAccountActive(a,owner,fail);
 const challenge=await a.one('SELECT * FROM account_closure_challenges WHERE id=? AND owner=?',cid,owner);
 if(!challenge||challenge.request_id!==d.requestId||challenge.nonce_hash!==nh||challenge.session_hash!==await hash(a.token||''))fail(404,'确认凭证无效。');
 const rid=uuid(),operationNonce=uuid();
 const cleanup=await (options.cleanup||closureCleanupStatements)(a,owner,rid,stamp,{sql:'EXISTS(SELECT 1 FROM account_closure_receipts WHERE id=? AND owner=? AND challenge_id=? AND operation_nonce=?)',bindings:[rid,owner,cid,operationNonce]});
 const statements=[
  a.stmt('INSERT INTO account_closure_receipts VALUES (?,?,?,?,?,?,?,?)',rid,owner,cid,d.requestId,nh,operationNonce,stamp,'{}'),
  ...cleanup.statements,
  a.stmt('UPDATE account_closure_receipts SET details='+cleanup.receiptJSONSql.sql+' WHERE id=?',...cleanup.receiptJSONSql.bindings,rid),
  a.stmt('UPDATE users SET password=? WHERE id=?',randomHex(16)+':'+randomHex(32),owner),
  a.stmt('UPDATE account_closure_challenges SET consumed=1 WHERE owner=?',owner),
  a.stmt('INSERT OR IGNORE INTO account_revoked_sessions SELECT token,user_id,? FROM sessions WHERE user_id=?',stamp,owner),
  a.stmt('DELETE FROM sessions WHERE user_id=?',owner),
  a.stmt("INSERT INTO account_lifecycle VALUES (?,'closed',1,?,?) ON CONFLICT(owner) DO UPDATE SET status='closed',epoch=epoch+1,closed_at=excluded.closed_at,receipt_id=excluded.receipt_id",owner,stamp,rid)
 ];
 try{await a.db.batch(statements);}catch(e){
  old=await a.one('SELECT * FROM account_closure_receipts WHERE challenge_id=?',cid);
  if(!old||old.request_id!==d.requestId||old.nonce_hash!==nh){const msg=String((e as any)?.message||e);if(msg.includes('account_closure_last_admin'))fail(409,'这是最后一个有效管理员，请先移交管理权限。');if(msg.includes('account_closure_'))fail(409,'确认已失效或账号状态已变化，请重新登录确认。');if(msg.includes('account_closed'))fail(401,'账号已关闭，请使用其他账号。');throw e;}
 }
 const row=await a.one('SELECT * FROM account_closure_receipts WHERE challenge_id=?',cid);
 if(!row)fail(409,'账号状态已变化，请重新确认。');
 return receipt(row);
}

export function accountFailure(error:any):{status:number,message:string}|null{
 const value=String(error?.message||error?.cause?.message||error);
 if(/account_actor_inactive|account_closed/.test(value))return {status:401,message:'账号或权限已失效，请重新登录。'};
 if(value.includes('account_target_closed'))return {status:409,message:'对方账号已关闭，暂不可继续此操作。'};
 if(value.includes('account_closure_last_admin'))return {status:409,message:'这是最后一个有效管理员，请先移交管理权限。'};
 return value.includes('account_')?{status:409,message:'账号状态已变化，请重新确认。'}:null;
}
