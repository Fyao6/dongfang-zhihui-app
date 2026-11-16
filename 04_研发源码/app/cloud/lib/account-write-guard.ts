// Atomic actor fences. Trusted adapters are server-only and limited to existing facts.
export const ACCOUNT_WRITE_DDL:string[]=["CREATE TABLE IF NOT EXISTS account_action_fences(id TEXT PRIMARY KEY,actor TEXT NOT NULL,session_hash TEXT NOT NULL,roles TEXT NOT NULL,created INTEGER NOT NULL)","CREATE TRIGGER IF NOT EXISTS account_action_fence_check BEFORE INSERT ON account_action_fences BEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.id=NEW.actor AND s.token=NEW.session_hash AND s.expires>NEW.created AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed') AND (json_array_length(NEW.roles)=0 OR u.role IN (SELECT value FROM json_each(NEW.roles)))) THEN RAISE(ABORT,'account_actor_inactive') END;\n END","CREATE TRIGGER IF NOT EXISTS account_action_fence_forget AFTER INSERT ON account_action_fences BEGIN DELETE FROM account_action_fences WHERE id=NEW.id; END"];
const rawDatabases=new WeakMap<object,any>(),statements=new WeakMap<object,{raw:any,sql:string}>();
const hash=async(s:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)))).map(n=>n.toString(16).padStart(2,'0')).join('');
const mutation=(s:string)=>/^\s*(INSERT|UPDATE|DELETE|REPLACE)\b/i.test(s);
function target(s:string){return /^\s*(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|REPLACE\s+INTO|UPDATE(?:\s+OR\s+\w+)?|DELETE\s+FROM)\s+([a-z_][a-z_0-9]*)/i.exec(s)?.[1]?.toLowerCase()||'';}
function serviceAllowed(sql:string,kind:string){
 const table=target(sql),op=sql.trimStart().split(/\s/)[0].toUpperCase();
 if(table==='audits'&&op==='INSERT')return true;
 if(kind==='session')return table==='sessions'&&['INSERT','DELETE'].includes(op);
 if(kind==='gateway'){
  if(table==='ai_gateway_jobs')return op==='UPDATE';
  if(table==='ai_gateway_attempts')return ['INSERT','UPDATE'].includes(op);
  if(table==='privacy_transfers')return op==='INSERT';
  return table==='privacy_conversations'&&op==='INSERT'&&sql.toUpperCase().includes('SELECT')&&['revision','provider_binding','saveConversations'].every(s=>sql.includes(s));
 }
 return kind==='order'&&(table.startsWith('membership_')||table.startsWith('commission_'));
}
type Scope={kind:'gateway'|'order'|'session',id:string,owner:string};
async function validateFact(db:any,s:Scope){
 let sql:string,args:any[];
 if(s.kind==='gateway'){sql='SELECT 1 FROM ai_gateway_jobs WHERE id=? AND owner=?';args=[s.id,s.owner];}
 else if(s.kind==='order'){sql="SELECT 1 FROM commerce_orders o WHERE o.id=? AND o.owner=? AND EXISTS(SELECT 1 FROM commerce_payment_events p WHERE p.order_id=o.id AND p.status='applied' AND p.kind IN ('sandbox_pay','refund'))";args=[s.id,s.owner];}
 else{sql="SELECT 1 FROM users u WHERE id=? AND NOT EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=u.id AND status='closed')";args=[s.owner];}
 if(!await db.prepare(sql).bind(...args).first())throw Error('account_settlement_denied');
}
export async function initAccountWriteGuard(a:any){await a.db.batch(ACCOUNT_WRITE_DDL.map(s=>a.stmt(s)));}
export function accountRequiredRoles(a:any,roles?:string[]){if(roles?.length)a.accountRequiredRoles=[...roles];}
function databaseProxy(a:any,db:any,scope?:Scope):any{
 async function batch(ops:any[]){
  const descriptions=ops.map(s=>statements.get(s)||{raw:s,sql:''}),writes=descriptions.filter(x=>mutation(x.sql));
  if(descriptions.some(x=>!x.sql)&&a.user)throw Error('account_untracked_statement');
  const raw=descriptions.map(x=>x.raw);
  if(!writes.length)return db.batch(raw);
  if(scope){
   if(writes.some(x=>!serviceAllowed(x.sql,scope.kind)))throw Error('account_settlement_denied');
   await validateFact(db,scope);
   return db.batch(raw);
  }
  if(!a.user||writes.every(x=>target(x.sql)==='audits'&&x.sql.trimStart().toUpperCase().startsWith('INSERT')))return db.batch(raw);
  const fence=db.prepare('INSERT INTO account_action_fences VALUES(?,?,?,?,?)').bind(crypto.randomUUID(),a.user.id,await hash(a.token||''),JSON.stringify(a.accountRequiredRoles||[]),Date.now());
  return (await db.batch([fence,...raw])).slice(1);
 }
 function wrap(raw:any,sql:string):any{
  const proxy=new Proxy(raw,{get(t,k){
   if(k==='bind')return(...args:any[])=>wrap(t.bind(...args),sql);
   if(k==='run')return async()=>{if(!mutation(sql))return t.run();return (await batch([proxy]))[0];};
   if(k==='all')return async()=>{if(!mutation(sql))return t.all();return (await batch([proxy]))[0];};
   if(k==='first')return async(column?:string)=>{if(!mutation(sql))return t.first(column);const r=(await batch([proxy]))[0],row=r.results?.[0]||null;return column&&row?row[column]:row;};
   if(k==='raw')return async(options?:any)=>{if(!mutation(sql))return t.raw(options);const r=(await batch([proxy]))[0],rows=r.results||[],keys=rows.length?Object.keys(rows[0]):[];return options?.columnNames?[keys,...rows.map((r:any)=>keys.map(k=>r[k]))]:rows.map((r:any)=>keys.map(k=>r[k]));};
   const value=Reflect.get(t,k,t);return typeof value==='function'?value.bind(t):value;
  }});
  statements.set(proxy,{raw,sql});return proxy;
 }
 return new Proxy(db,{get(t,k){
  if(k==='prepare')return(sql:string)=>wrap(t.prepare(sql),sql);
  if(k==='batch')return batch;
  if(k==='exec')return async(sql:string)=>{if(a.user&&/\b(INSERT|UPDATE|DELETE|REPLACE)\b/i.test(sql))throw Error('account_use_tracked_statements');return t.exec(sql);};
  const value=Reflect.get(t,k,t);return typeof value==='function'?value.bind(t):value;
 }});
}
export function bindAccountDatabase(a:any,db:any){rawDatabases.set(a,db);return databaseProxy(a,db);}
export async function trustedSettlementApi(a:any,kind:'gateway'|'order',id:string,owner:string){
 const raw=rawDatabases.get(a)||a.db,scope={kind,id,owner};await validateFact(raw,scope);
 const copy=Object.create(a);copy.db=databaseProxy(copy,raw,scope);rawDatabases.set(copy,raw);return copy;
}
export async function verifiedSessionApi(a:any,owner:string){
 // Only called by server login after its actual password verifier succeeds.
 const raw=rawDatabases.get(a)||a.db,scope:Scope={kind:'session',id:owner,owner};await validateFact(raw,scope);
 const copy=Object.create(a);copy.db=databaseProxy(copy,raw,scope);rawDatabases.set(copy,raw);return copy;
}
