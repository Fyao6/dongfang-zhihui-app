// Finite sandbox access leases. They never grant production membership or public media access.
import {privacyMediaDeleted} from './privacy-domains';
export const DIGITAL_POLICY={revision:0,enabled:false,confirmed:false,ruleVersion:'',environment:'sandbox',validityDays:null as number|null,usesPerUnit:null as number|null,leaseSeconds:300,consumption:'lease_acquisition',anchor:'verified_payment_utc',refundPolicy:'cap_unconsumed',productionEnabled:false};
const MUTABLE=['revision','enabled','confirmed','ruleVersion','validityDays','usesPerUnit','leaseSeconds'];
const FIXED=Object.fromEntries(Object.entries(DIGITAL_POLICY).filter(([k])=>!MUTABLE.includes(k)));
const canonical=(v:any):any=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
const J=(v:any)=>JSON.stringify(canonical(v));
const uid=()=>crypto.randomUUID();
const hash=async(value:string)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),v=>v.toString(16).padStart(2,'0')).join('');
const validInt=(n:any,min:number,max:number)=>Number.isSafeInteger(n)&&n>=min&&n<=max;
const ready=(p:any)=>p.enabled===true&&p.confirmed===true&&typeof p.ruleVersion==='string'&&!!p.ruleVersion.trim()&&validInt(p.validityDays,1,3650)&&validInt(p.usesPerUnit,1,1000)&&validInt(p.leaseSeconds,30,14400)&&Object.entries(FIXED).every(([k,v])=>p[k]===v);
const title=(r:any)=>{let c:any={};try{c=JSON.parse(r.content_data||r.data||'{}');}catch{}return String(c.zh||c.title||c.name||r.item_title||r.content_id||r.id||'');};
const leaseUrl=(id:string)=>'/api/digital-entitlements/leases/'+encodeURIComponent(id)+'/media';
class DigitalAccessChanged extends Error{}
const DDL:string[]=[
 "CREATE TABLE IF NOT EXISTS digital_sandbox_assets(\n media_id TEXT PRIMARY KEY,content_id TEXT NOT NULL UNIQUE,owner TEXT NOT NULL,\n status TEXT NOT NULL CHECK(status IN ('active','disabled')),created INTEGER NOT NULL,updated INTEGER NOT NULL);",
 "CREATE TABLE IF NOT EXISTS digital_order_snapshots(\n item_id TEXT PRIMARY KEY,owner TEXT NOT NULL,order_id TEXT NOT NULL,content_id TEXT NOT NULL,\n media_id TEXT NOT NULL,policy_snapshot TEXT NOT NULL,created INTEGER NOT NULL);",
 "CREATE TABLE IF NOT EXISTS digital_entitlement_grants(\n id TEXT PRIMARY KEY,owner TEXT NOT NULL,order_id TEXT NOT NULL,item_id TEXT NOT NULL UNIQUE,\n content_id TEXT NOT NULL,media_id TEXT NOT NULL,policy_snapshot TEXT NOT NULL,\n uses_per_unit INTEGER NOT NULL CHECK(uses_per_unit>0),original_quantity INTEGER NOT NULL CHECK(original_quantity>0),\n used INTEGER NOT NULL DEFAULT 0 CHECK(used>=0),overused INTEGER NOT NULL DEFAULT 0 CHECK(overused>=0),\n starts INTEGER NOT NULL,expires INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL);",
 "CREATE INDEX IF NOT EXISTS digital_grant_owner ON digital_entitlement_grants(owner,created,id);",
 "CREATE TABLE IF NOT EXISTS digital_access_leases(\n id TEXT PRIMARY KEY,owner TEXT NOT NULL,grant_id TEXT NOT NULL,request_id TEXT NOT NULL,\n session_hash TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,UNIQUE(owner,request_id));",
 "CREATE TABLE IF NOT EXISTS digital_entitlement_uses(\n id TEXT PRIMARY KEY,owner TEXT NOT NULL,grant_id TEXT NOT NULL,lease_id TEXT NOT NULL UNIQUE,\n action TEXT NOT NULL CHECK(action='lease_acquired'),created INTEGER NOT NULL);",
 "CREATE INDEX IF NOT EXISTS digital_use_owner ON digital_entitlement_uses(owner,created,id);",
 "CREATE TRIGGER IF NOT EXISTS digital_asset_identity BEFORE UPDATE OF media_id,content_id,owner,created ON digital_sandbox_assets\n BEGIN SELECT RAISE(ABORT,'digital_asset_immutable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_asset_no_reenable BEFORE UPDATE OF status ON digital_sandbox_assets\n WHEN OLD.status='disabled' AND NEW.status!='disabled' BEGIN SELECT RAISE(ABORT,'digital_asset_permanent_disable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_asset_no_delete BEFORE DELETE ON digital_sandbox_assets\n BEGIN SELECT RAISE(ABORT,'digital_asset_permanent_marker'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_snapshot_identity BEFORE UPDATE ON digital_order_snapshots\n BEGIN SELECT RAISE(ABORT,'digital_snapshot_immutable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_snapshot_no_delete BEFORE DELETE ON digital_order_snapshots\n BEGIN SELECT RAISE(ABORT,'digital_snapshot_immutable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_grant_identity BEFORE UPDATE OF id,owner,order_id,item_id,content_id,media_id,\n policy_snapshot,uses_per_unit,original_quantity,starts,expires,created ON digital_entitlement_grants\n BEGIN SELECT RAISE(ABORT,'digital_grant_immutable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_grant_no_delete BEFORE DELETE ON digital_entitlement_grants\n BEGIN SELECT RAISE(ABORT,'digital_grant_immutable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_lease_identity BEFORE UPDATE ON digital_access_leases\n BEGIN SELECT RAISE(ABORT,'digital_lease_immutable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_lease_no_delete BEFORE DELETE ON digital_access_leases\n BEGIN SELECT RAISE(ABORT,'digital_lease_immutable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_use_identity BEFORE UPDATE ON digital_entitlement_uses\n BEGIN SELECT RAISE(ABORT,'digital_use_immutable'); END;",
 "CREATE TRIGGER IF NOT EXISTS digital_use_no_delete BEFORE DELETE ON digital_entitlement_uses\n BEGIN SELECT RAISE(ABORT,'digital_use_immutable'); END;",
 "DROP TRIGGER IF EXISTS digital_snapshot_check;",
 "CREATE TRIGGER digital_snapshot_check BEFORE INSERT ON digital_order_snapshots BEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items i\n JOIN commerce_orders o ON o.id=i.order_id AND o.owner=NEW.owner\n JOIN commerce_products p ON p.id=i.product_id AND p.type='digital' AND p.environment='sandbox' AND p.content_id=i.content_id\n JOIN digital_sandbox_assets a ON a.content_id=i.content_id AND a.media_id=NEW.media_id AND a.status='active'\n JOIN contents c ON c.kind='courses' AND c.id=i.content_id AND c.status='published'\n WHERE i.id=NEW.item_id AND i.order_id=NEW.order_id AND i.type='digital' AND i.content_id=NEW.content_id\n AND i.refunded_quantity=0 AND o.environment='sandbox' AND o.payment_status='unpaid' AND o.status='awaiting_payment'\n AND json_type(c.data,'$.sandboxOnly')='true' AND coalesce(json_extract(c.data,'$.mediaUrl'),'')=''\n AND coalesce(json_extract(c.data,'$.audioUrl'),'')='' AND coalesce(json_extract(c.data,'$.creatorId'),'')=''\n AND EXISTS(SELECT 1 FROM settings WHERE key='digital_entitlements' AND data=NEW.policy_snapshot)\n AND EXISTS(SELECT 1 FROM settings WHERE key='digital_entitlements'\n AND json_type(data,'$.enabled')='true' AND json_type(data,'$.confirmed')='true'\n AND json_extract(data,'$.environment')='sandbox' AND json_extract(data,'$.productionEnabled')=0\n AND json_type(data,'$.ruleVersion')='text' AND length(trim(json_extract(data,'$.ruleVersion')))>0\n AND json_type(data,'$.validityDays')='integer' AND json_extract(data,'$.validityDays') BETWEEN 1 AND 3650\n AND json_type(data,'$.usesPerUnit')='integer' AND json_extract(data,'$.usesPerUnit') BETWEEN 1 AND 1000\n AND json_type(data,'$.leaseSeconds')='integer' AND json_extract(data,'$.leaseSeconds') BETWEEN 30 AND 14400\n AND json_extract(data,'$.consumption')='lease_acquisition' AND json_extract(data,'$.anchor')='verified_payment_utc'\n AND json_extract(data,'$.refundPolicy')='cap_unconsumed')) THEN RAISE(ABORT,'digital_checkout_changed') END;\nEND;",
 "DROP TRIGGER IF EXISTS digital_grant_check;",
 "CREATE TRIGGER digital_grant_check BEFORE INSERT ON digital_entitlement_grants BEGIN\n SELECT CASE WHEN NEW.id!='digital:'||NEW.item_id OR NEW.used!=0 OR NEW.overused!=0 OR NOT EXISTS(\n SELECT 1 FROM digital_order_snapshots s\n JOIN commerce_order_items i ON i.id=s.item_id AND i.order_id=s.order_id AND i.type='digital'\n JOIN commerce_orders o ON o.id=s.order_id AND o.owner=s.owner AND o.environment='sandbox'\n JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=s.owner AND e.environment='sandbox'\n JOIN commerce_payment_events pay ON pay.order_id=o.id AND pay.owner=o.owner AND pay.kind='sandbox_pay' AND pay.status='applied' AND pay.environment='sandbox'\n WHERE s.item_id=NEW.item_id AND s.owner=NEW.owner AND s.order_id=NEW.order_id AND s.content_id=NEW.content_id\n AND s.media_id=NEW.media_id AND s.policy_snapshot=NEW.policy_snapshot AND i.content_id=s.content_id\n AND o.payment_status IN ('paid','partially_refunded') AND i.refunded_quantity=0 AND e.status='active'\n AND NEW.original_quantity=i.quantity AND NEW.uses_per_unit=json_extract(s.policy_snapshot,'$.usesPerUnit')\n AND NEW.starts=pay.created AND NEW.expires=pay.created+json_extract(s.policy_snapshot,'$.validityDays')*86400000\n AND NEW.expires>NEW.starts) THEN RAISE(ABORT,'digital_grant_changed') END;\nEND;",
 "DROP TRIGGER IF EXISTS digital_entitlement_grant;",
 "CREATE TRIGGER digital_entitlement_grant AFTER INSERT ON commerce_entitlements\nWHEN NEW.type='digital' AND EXISTS(SELECT 1 FROM digital_order_snapshots WHERE item_id=NEW.item_id) BEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_payment_events p JOIN commerce_orders o ON o.id=p.order_id\n WHERE p.order_id=NEW.order_id AND p.owner=NEW.owner AND p.kind='sandbox_pay' AND p.status='applied'\n AND p.environment='sandbox' AND o.payment_status IN ('paid','partially_refunded')) THEN RAISE(ABORT,'digital_payment_missing') END;\n INSERT INTO digital_entitlement_grants\n SELECT 'digital:'||NEW.item_id,NEW.owner,NEW.order_id,NEW.item_id,s.content_id,s.media_id,s.policy_snapshot,\n json_extract(s.policy_snapshot,'$.usesPerUnit'),NEW.quantity,0,0,p.created,\n p.created+json_extract(s.policy_snapshot,'$.validityDays')*86400000,NEW.created,NEW.created\n FROM digital_order_snapshots s JOIN commerce_payment_events p ON p.order_id=s.order_id AND p.owner=s.owner\n AND p.kind='sandbox_pay' AND p.status='applied' AND p.environment='sandbox' WHERE s.item_id=NEW.item_id;\nEND;",
 "DROP TRIGGER IF EXISTS digital_refund_cap;",
 "CREATE TRIGGER digital_refund_cap AFTER UPDATE OF refunded_quantity ON commerce_order_items\nWHEN NEW.refunded_quantity>OLD.refunded_quantity BEGIN\n UPDATE digital_entitlement_grants SET overused=max(0,used-(NEW.quantity-NEW.refunded_quantity)*uses_per_unit),\n updated=coalesce((SELECT max(created) FROM commerce_payment_events WHERE order_id=NEW.order_id),updated)\n WHERE item_id=NEW.id;\nEND;",
 "DROP TRIGGER IF EXISTS digital_use_check;",
 "CREATE TRIGGER digital_use_check BEFORE INSERT ON digital_access_leases BEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM digital_entitlement_grants g\n JOIN commerce_order_items i ON i.id=g.item_id AND i.order_id=g.order_id\n JOIN commerce_orders o ON o.id=g.order_id AND o.owner=g.owner\n JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=g.owner AND e.environment='sandbox'\n JOIN commerce_payment_events pay ON pay.order_id=o.id AND pay.owner=g.owner AND pay.kind='sandbox_pay' AND pay.status='applied' AND pay.environment='sandbox'\n JOIN digital_sandbox_assets a ON a.media_id=g.media_id AND a.content_id=g.content_id\n JOIN contents c ON c.kind='courses' AND c.id=g.content_id\n JOIN commerce_products p ON p.id=i.product_id\n JOIN sessions ses ON ses.user_id=g.owner AND ses.token=NEW.session_hash\n WHERE g.id=NEW.grant_id AND g.owner=NEW.owner AND o.environment='sandbox' AND o.payment_status IN ('paid','partially_refunded')\n AND i.type='digital' AND i.content_id=g.content_id AND i.quantity=g.original_quantity AND i.refunded_quantity<i.quantity\n AND p.type='digital' AND p.environment='sandbox' AND p.content_id=g.content_id\n AND e.type='digital' AND e.content_id=g.content_id AND e.status='active' AND e.remaining>0\n AND a.status='active' AND c.status='published' AND json_type(c.data,'$.sandboxOnly')='true'\n AND coalesce(json_extract(c.data,'$.mediaUrl'),'')='' AND coalesce(json_extract(c.data,'$.audioUrl'),'')=''\n AND coalesce(json_extract(c.data,'$.creatorId'),'')=''\n AND EXISTS(SELECT 1 FROM users u WHERE u.id=g.owner AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))\n AND EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1)\n AND EXISTS(SELECT 1 FROM settings WHERE key='digital_entitlements'\n AND json_type(data,'$.enabled')='true' AND json_type(data,'$.confirmed')='true'\n AND json_extract(data,'$.environment')='sandbox' AND json_extract(data,'$.productionEnabled')=0\n AND json_type(data,'$.ruleVersion')='text' AND length(trim(json_extract(data,'$.ruleVersion')))>0\n AND json_type(data,'$.validityDays')='integer' AND json_extract(data,'$.validityDays') BETWEEN 1 AND 3650\n AND json_type(data,'$.usesPerUnit')='integer' AND json_extract(data,'$.usesPerUnit') BETWEEN 1 AND 1000\n AND json_type(data,'$.leaseSeconds')='integer' AND json_extract(data,'$.leaseSeconds') BETWEEN 30 AND 14400\n AND json_extract(data,'$.consumption')='lease_acquisition' AND json_extract(data,'$.anchor')='verified_payment_utc'\n AND json_extract(data,'$.refundPolicy')='cap_unconsumed')\n AND ses.expires>CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)\n AND g.starts<=NEW.created AND g.expires>NEW.created\n AND g.used<(i.quantity-i.refunded_quantity)*g.uses_per_unit\n AND NEW.expires=min(NEW.created+json_extract(g.policy_snapshot,'$.leaseSeconds')*1000,g.expires)\n AND NEW.expires>NEW.created) THEN RAISE(ABORT,'digital_access_changed') END;\nEND;",
 "DROP TRIGGER IF EXISTS digital_use_apply;",
 "CREATE TRIGGER digital_use_apply AFTER INSERT ON digital_access_leases BEGIN\n UPDATE digital_entitlement_grants SET used=used+1,updated=NEW.created WHERE id=NEW.grant_id AND owner=NEW.owner;\n INSERT INTO digital_entitlement_uses VALUES('use:'||NEW.id,NEW.owner,NEW.grant_id,NEW.id,'lease_acquired',NEW.created);\nEND;"
];
const REFERENCE_BASE:string[]=[
 "DROP TRIGGER IF EXISTS digital_asset_check;",
 "CREATE TRIGGER digital_asset_check BEFORE INSERT ON digital_sandbox_assets BEGIN\n SELECT CASE WHEN NEW.status!='active' OR NOT EXISTS(SELECT 1 FROM media m JOIN users u ON u.id=m.owner\n WHERE m.id=NEW.media_id AND m.owner=NEW.owner AND u.role='admin' AND (m.mime LIKE 'audio/%' OR m.mime LIKE 'video/%')\n AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))\n OR NOT EXISTS(SELECT 1 FROM contents c WHERE c.kind='courses' AND c.id=NEW.content_id AND c.status='published'\n AND json_type(c.data,'$.sandboxOnly')='true' AND coalesce(json_extract(c.data,'$.mediaUrl'),'')=''\n AND coalesce(json_extract(c.data,'$.audioUrl'),'')='' AND coalesce(json_extract(c.data,'$.creatorId'),'')='')\n OR 0 THEN RAISE(ABORT,'digital_asset_not_isolated') END;\n END;",
 "DROP TRIGGER IF EXISTS digital_sandbox_course_guard;",
 "CREATE TRIGGER digital_sandbox_course_guard BEFORE UPDATE OF data,kind,id ON contents\n WHEN OLD.kind='courses' AND EXISTS(SELECT 1 FROM digital_sandbox_assets WHERE content_id=OLD.id) BEGIN\n SELECT CASE WHEN NEW.kind!='courses' OR NEW.id!=OLD.id OR coalesce(json_type(NEW.data,'$.sandboxOnly'),'')!='true'\n OR coalesce(json_extract(NEW.data,'$.mediaUrl'),'')!='' OR coalesce(json_extract(NEW.data,'$.audioUrl'),'')!=''\n OR coalesce(json_extract(NEW.data,'$.creatorId'),'')!='' THEN RAISE(ABORT,'digital_sandbox_course_immutable') END; END;",
 "DROP TRIGGER IF EXISTS digital_course_boolean_insert;",
 "CREATE TRIGGER digital_course_boolean_insert BEFORE INSERT ON contents WHEN NEW.kind='courses' BEGIN SELECT CASE WHEN json_type(NEW.data,'$.sandboxOnly') IS NOT NULL AND json_type(NEW.data,'$.sandboxOnly') NOT IN ('true','false') THEN RAISE(ABORT,'digital_sandbox_bool_required') END; END;",
 "DROP TRIGGER IF EXISTS digital_course_boolean_update;",
 "CREATE TRIGGER digital_course_boolean_update BEFORE UPDATE OF data,kind ON contents WHEN NEW.kind='courses' BEGIN SELECT CASE WHEN json_type(NEW.data,'$.sandboxOnly') IS NOT NULL AND json_type(NEW.data,'$.sandboxOnly') NOT IN ('true','false') THEN RAISE(ABORT,'digital_sandbox_bool_required') END; END;",
 "DROP TRIGGER IF EXISTS digital_sandbox_course_insert;",
 "CREATE TRIGGER digital_sandbox_course_insert BEFORE INSERT ON contents\n WHEN NEW.kind='courses' AND EXISTS(SELECT 1 FROM digital_sandbox_assets WHERE content_id=NEW.id) BEGIN\n SELECT CASE WHEN coalesce(json_type(NEW.data,'$.sandboxOnly'),'')!='true'\n OR coalesce(json_extract(NEW.data,'$.mediaUrl'),'')!='' OR coalesce(json_extract(NEW.data,'$.audioUrl'),'')!=''\n OR coalesce(json_extract(NEW.data,'$.creatorId'),'')!='' THEN RAISE(ABORT,'digital_sandbox_course_immutable') END; END;"
];
const REFERENCE_FIELDS:[string,string][]=[["contents","data"],["settings","data"],["posts","media_url"],["creator_works","data"],["creator_profiles","data"],["commerce_products","data"],["card_deck_versions","data"],["card_draws","snapshot"],["revisions","snapshot"],["commerce_order_items","snapshot_data"]];
const BASE_JOIN="FROM digital_entitlement_grants g\n JOIN commerce_order_items i ON i.id=g.item_id AND i.order_id=g.order_id\n JOIN commerce_orders o ON o.id=g.order_id AND o.owner=g.owner\n JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=g.owner AND e.environment='sandbox'\n JOIN commerce_payment_events pay ON pay.order_id=o.id AND pay.owner=g.owner AND pay.kind='sandbox_pay' AND pay.status='applied' AND pay.environment='sandbox'\n JOIN digital_sandbox_assets a ON a.media_id=g.media_id AND a.content_id=g.content_id\n JOIN contents c ON c.kind='courses' AND c.id=g.content_id\n JOIN commerce_products p ON p.id=i.product_id";
const BASE_GUARD="o.environment='sandbox' AND o.payment_status IN ('paid','partially_refunded')\n AND i.type='digital' AND i.content_id=g.content_id AND i.quantity=g.original_quantity AND i.refunded_quantity<i.quantity\n AND p.type='digital' AND p.environment='sandbox' AND p.content_id=g.content_id\n AND e.type='digital' AND e.content_id=g.content_id AND e.status='active' AND e.remaining>0\n AND a.status='active' AND c.status='published' AND json_type(c.data,'$.sandboxOnly')='true'\n AND coalesce(json_extract(c.data,'$.mediaUrl'),'')='' AND coalesce(json_extract(c.data,'$.audioUrl'),'')=''\n AND coalesce(json_extract(c.data,'$.creatorId'),'')=''\n AND EXISTS(SELECT 1 FROM users u WHERE u.id=g.owner AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))\n AND EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1)\n AND EXISTS(SELECT 1 FROM settings WHERE key='digital_entitlements'\n AND json_type(data,'$.enabled')='true' AND json_type(data,'$.confirmed')='true'\n AND json_extract(data,'$.environment')='sandbox' AND json_extract(data,'$.productionEnabled')=0\n AND json_type(data,'$.ruleVersion')='text' AND length(trim(json_extract(data,'$.ruleVersion')))>0\n AND json_type(data,'$.validityDays')='integer' AND json_extract(data,'$.validityDays') BETWEEN 1 AND 3650\n AND json_type(data,'$.usesPerUnit')='integer' AND json_extract(data,'$.usesPerUnit') BETWEEN 1 AND 1000\n AND json_type(data,'$.leaseSeconds')='integer' AND json_extract(data,'$.leaseSeconds') BETWEEN 30 AND 14400\n AND json_extract(data,'$.consumption')='lease_acquisition' AND json_extract(data,'$.anchor')='verified_payment_utc'\n AND json_extract(data,'$.refundPolicy')='cap_unconsumed')";
const FACT_COLUMNS=`g.*,i.quantity current_quantity,i.refunded_quantity,i.type item_type,i.content_id item_content_id,i.title item_title,
 o.owner order_owner,o.environment order_environment,o.payment_status,e.status entitlement_status,e.remaining,e.type entitlement_type,e.content_id entitlement_content_id,
 p.type product_type,p.environment product_environment,p.content_id product_content_id,
 asset.status asset_status,asset.content_id asset_content_id,m.mime,m.filename,m.object_key,c.status content_status,c.data content_data,
 coalesce((SELECT data FROM settings WHERE key='digital_entitlements'),'{}') current_policy,
 coalesce((SELECT data FROM commerce_config WHERE key='settings'),'{}') commerce_settings,
 EXISTS(SELECT 1 FROM commerce_payment_events pay WHERE pay.order_id=g.order_id AND pay.owner=g.owner AND pay.environment='sandbox' AND pay.kind='sandbox_pay' AND pay.status='applied') verified_payment,
 EXISTS(SELECT 1 FROM users u WHERE u.id=g.owner AND NOT EXISTS(SELECT 1 FROM account_lifecycle a WHERE a.owner=u.id AND a.status='closed')) owner_active`;
const FACT_FROM=`FROM digital_entitlement_grants g LEFT JOIN commerce_order_items i ON i.id=g.item_id AND i.order_id=g.order_id
 LEFT JOIN commerce_orders o ON o.id=g.order_id LEFT JOIN commerce_entitlements e ON e.item_id=g.item_id AND e.owner=g.owner AND e.environment='sandbox'
 LEFT JOIN digital_sandbox_assets asset ON asset.media_id=g.media_id LEFT JOIN media m ON m.id=g.media_id
 LEFT JOIN contents c ON c.kind='courses' AND c.id=g.content_id LEFT JOIN commerce_products p ON p.id=i.product_id`;
function accessFacts(r:any,t:number){
 const cap=Math.max(0,(Number(r.current_quantity)||0)-(Number(r.refunded_quantity)||0))*r.uses_per_unit;
 let course:any={},policy:any={},commerce:any={};try{course=JSON.parse(r.content_data||'{}');policy={...DIGITAL_POLICY,...JSON.parse(r.current_policy)};commerce=JSON.parse(r.commerce_settings);}catch{}
 const revoked=!r.owner_active||!r.verified_payment||r.order_owner!==r.owner||r.order_environment!=='sandbox'||!['paid','partially_refunded'].includes(r.payment_status)||r.item_type!=='digital'||r.item_content_id!==r.content_id||r.current_quantity!==r.original_quantity||r.entitlement_type!=='digital'||r.entitlement_content_id!==r.content_id||r.entitlement_status!=='active'||r.remaining<=0||r.product_type!=='digital'||r.product_environment!=='sandbox'||r.product_content_id!==r.content_id||cap===0;
 const expired=t<r.starts||t>=r.expires;
 const disabled=!ready(policy)||commerce.sandboxEnabled!==true||r.asset_status!=='active'||r.asset_content_id!==r.content_id||r.content_status!=='published'||course.sandboxOnly!==true||!!course.creatorId||!!course.mediaUrl||!!course.audioUrl;
 return {cap,revoked,expired,disabled,policyReady:ready(policy),live:!revoked&&!expired&&!disabled,valid:!revoked&&!expired&&!disabled&&r.used<=cap};
}

export async function initDigitalEntitlements(a:any){
 if(await a.one("SELECT 1 FROM settings WHERE key='digital_entitlements_schema_v1'"))return;
 const fields:[string,string][]=[];
 for(const [table,column] of REFERENCE_FIELDS)if((await a.all('PRAGMA table_info('+table+')')).some((r:any)=>r.name===column))fields.push([table,column]);
 await a.db.batch([...DDL,...referenceStatements(fields)].map(sql=>a.stmt(sql)).concat([a.stmt("INSERT OR IGNORE INTO settings VALUES('digital_entitlements_schema_v1','true')")]));
}
function referenceStatements(fields:[string,string][]){
 const references=fields.map(([table,column])=>`EXISTS(SELECT 1 FROM ${table} WHERE instr(coalesce(${column},''),'/api/media/'||NEW.media_id)>0)`).join(' OR ')||'0';
 const out=REFERENCE_BASE.map(sql=>sql.replace("OR 0 THEN RAISE(ABORT,'digital_asset_not_isolated')",`OR (${references}) THEN RAISE(ABORT,'digital_asset_not_isolated')`));
 for(const [table,column] of fields)for(const operation of ['INSERT','UPDATE']){
  const name='digital_private_'+table+'_'+operation.toLowerCase();out.push('DROP TRIGGER IF EXISTS '+name);
  out.push(`CREATE TRIGGER ${name} BEFORE ${operation}${operation==='UPDATE'?' OF '+column:''} ON ${table} BEGIN SELECT CASE WHEN EXISTS(SELECT 1 FROM digital_sandbox_assets WHERE instr(coalesce(NEW.${column},''),'/api/media/'||media_id)>0) THEN RAISE(ABORT,'digital_private_asset_reference') END; END;`);
 }
 return out;
}
export async function isDigitalSandboxAsset(a:any,mediaId:string){return !!await a.one('SELECT 1 FROM digital_sandbox_assets WHERE media_id=?',mediaId);}
export async function digitalCatalogReadiness(a:any,contentIds:string[]){
 const ids=[...new Set(contentIds)],result=new Map<string,{marked:boolean,ready:boolean}>();if(!ids.length)return result;
 const [policy,rows]=await Promise.all([a.setting('digital_entitlements'),a.all(`SELECT wanted.value content_id,c.status,c.data,asset.media_id,asset.status asset_status,asset.owner asset_owner,m.owner media_owner,m.mime,
  coalesce((SELECT data FROM commerce_config WHERE key='settings'),'{}') commerce_settings
  FROM json_each(?) wanted LEFT JOIN contents c ON c.kind='courses' AND c.id=wanted.value
  LEFT JOIN digital_sandbox_assets asset ON asset.content_id=wanted.value LEFT JOIN media m ON m.id=asset.media_id`,J(ids))]);
 const policyReady=ready({...DIGITAL_POLICY,...policy});
 for(const r of rows){let course:any={},commerce:any={};try{course=JSON.parse(r.data||'{}');commerce=JSON.parse(r.commerce_settings);}catch{}
  const marked=!!r.media_id||course.sandboxOnly===true;
  result.set(r.content_id,{marked,ready:!!(policyReady&&commerce.sandboxEnabled===true&&r.status==='published'&&course.sandboxOnly===true&&!course.mediaUrl&&!course.audioUrl&&!course.creatorId&&r.asset_status==='active'&&r.asset_owner===r.media_owner&&/^(audio|video)\//.test(r.mime||''))});
 }
 return result;
}
export async function digitalOrderTerms(a:any,orderId:string,owner:string){
 const rows=await a.all('SELECT item_id,policy_snapshot,content_id,media_id FROM digital_order_snapshots WHERE order_id=? AND owner=?',orderId,owner);
 return Object.fromEntries(rows.map((r:any)=>[r.item_id,{...JSON.parse(r.policy_snapshot),contentId:r.content_id,mediaId:r.media_id,sandboxOnly:true}]));
}
export async function captureDigitalStatements(a:any,owner:string,orderId:string,lines:any[],stamp:number,fail:(s:number,m:string)=>never){
 const policy={...DIGITAL_POLICY,...await a.setting('digital_entitlements')},ops:any[]=[];
 for(const line of lines.filter(x=>x.type==='digital')){
  const marked=await a.one("SELECT 1 FROM contents WHERE kind='courses' AND id=? AND json_type(data,'$.sandboxOnly')='true' UNION ALL SELECT 1 FROM digital_sandbox_assets WHERE content_id=?",line.contentId,line.contentId);if(!marked)continue;
  if(!ready(policy))fail(503,'隔离数字商品的有限沙箱政策尚未启用。');
  const asset=await a.one("SELECT media_id FROM digital_sandbox_assets asset JOIN contents c ON c.id=asset.content_id AND c.kind='courses' WHERE asset.content_id=? AND asset.status='active' AND c.status='published' AND json_type(c.data,'$.sandboxOnly')='true'",line.contentId);
  if(!asset)fail(409,'隔离数字商品尚无有效测试素材绑定。');
  ops.push(a.stmt('INSERT INTO digital_order_snapshots VALUES(?,?,?,?,?,?,?)',line.id,owner,orderId,line.contentId,asset.media_id,J(policy),stamp));
 }
 return ops;
}

export class DigitalEntitlements{
 constructor(public a:any,public fail:(s:number,m:string)=>never){}
 clock(){return Date.now();}
 async policy(){return {...DIGITAL_POLICY,...await this.a.setting('digital_entitlements')};}
 async settings(){const p=await this.policy();return {enabled:!!p.enabled,confirmed:!!p.confirmed,ruleVersion:p.ruleVersion,environment:'sandbox',consumption:'lease_acquisition',productionEnabled:false};}
 async session(){return hash(this.a.token||'');}
 async batch(ops:any[]){try{return await this.a.db.batch(ops);}catch(e:any){const reason=String(e?.message||e?.cause?.message||'');if(/digital_access_changed/.test(reason))throw new DigitalAccessChanged('digital_access_changed');if(/digital_|UNIQUE|CHECK constraint/.test(reason))this.fail(409,'数字测试权益、使用凭证或资产状态已变化，请重新核对。');throw e;}}
 async find(id:string,admin=false){const r=await this.a.one('SELECT * FROM digital_entitlement_grants WHERE id=?'+(admin?'':' AND owner=?'),id,...(admin?[]:[this.a.user.id]));if(!r)this.fail(404,'未找到本人的数字测试权益。');return r;}
 async asset(mediaId:string){const r=await this.a.one(`SELECT s.*,m.mime,m.filename,c.data content_data FROM digital_sandbox_assets s LEFT JOIN media m ON m.id=s.media_id LEFT JOIN contents c ON c.kind='courses' AND c.id=s.content_id WHERE s.media_id=?`,mediaId);if(!r)this.fail(404,'未找到独立测试素材。');return this.assetItem(r);}
 assetItem(r:any){return {mediaId:r.media_id,contentId:r.content_id,title:title(r),mime:r.mime||'',filename:r.filename||'',status:r.status,created:r.created,updated:r.updated};}

 async facts(grant:any){return this.a.one('SELECT '+FACT_COLUMNS+' '+FACT_FROM+' WHERE g.id=? AND g.owner=?',grant.id,grant.owner);}
 async summary(grant:any):Promise<any>{
  const r=await this.facts(grant),t=this.clock(),f=accessFacts(r,t);let status=f.live?'active':t>=r.expires?'expired':!f.policyReady?'disabled':'revoked';if(status==='active'&&r.used>=f.cap)status='exhausted';
  return {id:r.id,orderId:r.order_id,itemId:r.item_id,contentId:r.content_id,title:title(r),mime:r.mime||'',quantity:r.original_quantity,refundedQuantity:r.refunded_quantity||0,usesPerUnit:r.uses_per_unit,totalUses:f.cap,used:r.used,available:f.live?Math.max(0,f.cap-r.used):0,overused:Math.max(r.overused,r.used-f.cap),starts:r.starts,expires:r.expires,status,canAccess:f.live&&r.used<f.cap,ruleVersion:JSON.parse(r.policy_snapshot).ruleVersion,environment:'sandbox',productionEnabled:false};
 }
 async validLease(id:string,owner:string,session:string,stamp:number):Promise<any>{
  return this.a.one('SELECT g.*,m.mime,m.object_key,l.id lease_id,l.created lease_created,l.expires lease_expires '+BASE_JOIN+` JOIN media m ON m.id=g.media_id JOIN digital_access_leases l ON l.grant_id=g.id AND l.owner=g.owner
   WHERE l.id=? AND l.owner=? AND l.session_hash=? AND l.created<=? AND l.expires>?
   AND EXISTS(SELECT 1 FROM sessions ses WHERE ses.token=l.session_hash AND ses.user_id=l.owner AND ses.expires>?)
   AND ${BASE_GUARD} AND g.starts<=? AND g.expires>? AND g.used<=(i.quantity-i.refunded_quantity)*g.uses_per_unit`,id,owner,session,stamp,stamp,Date.now(),stamp,stamp);
 }
 async detail(grant:any):Promise<any>{
  const a=this.a,before=a.url.searchParams.get('usesBefore'),where=['owner=?','grant_id=?'],args:any[]=[grant.owner,grant.id];
  if(before){const old=await a.one('SELECT created,id FROM digital_entitlement_uses WHERE id=? AND owner=? AND grant_id=?',before,grant.owner,grant.id);if(!old)this.fail(400,'使用记录游标无效。');where.push('(created,id)<(?,?)');args.push(old.created,old.id);}
  const rows=await a.all('SELECT * FROM digital_entitlement_uses WHERE '+where.join(' AND ')+' ORDER BY created DESC,id DESC LIMIT 101',...args),uses=[],session=await this.session();
  for(const use of rows.slice(0,100)){
   const lease=await a.one('SELECT * FROM digital_access_leases WHERE id=? AND owner=? AND grant_id=?',use.lease_id,grant.owner,grant.id);if(!lease)continue;
   const reason=lease.session_hash!==session?'session_changed':lease.expires<=this.clock()?'lease_expired':!await this.validLease(lease.id,a.user.id,session,this.clock())?'access_revoked':'';
   uses.push({id:use.id,leaseId:lease.id,requestId:lease.request_id,created:lease.created,expires:lease.expires,canResume:!reason,url:reason?'':leaseUrl(lease.id),reason});
  }
  return {item:await this.summary(grant),uses,usesNext:rows.length>100?rows[99].id:null,productionEnabled:false};
 }
 leaseItem(row:any){return {id:row.id,grantId:row.grant_id,url:leaseUrl(row.id),created:row.created,expires:row.expires};}
 async acquire(grant:any,requestId:string):Promise<any>{
  const a=this.a,owner=a.user.id,session=await this.session();let row=await a.one('SELECT * FROM digital_access_leases WHERE owner=? AND request_id=?',owner,requestId),duplicate=!!row;
  if(!row){
   if(!ready(await this.policy()))this.fail(503,'数字沙箱使用政策尚未启用。');
   const current=await this.summary(grant);if(['revoked','expired','disabled'].includes(current.status))this.fail(409,'当前数字测试权益已停用、到期或撤销。');if(!current.canAccess)this.fail(402,'当前可用访问次数不足。');
   const id=uid(),stamp=this.clock(),policy=JSON.parse(grant.policy_snapshot),expires=Math.min(grant.expires,stamp+policy.leaseSeconds*1000);
   try{await this.batch([a.stmt('INSERT INTO digital_access_leases VALUES(?,?,?,?,?,?,?)',id,owner,grant.id,requestId,session,stamp,expires)]);}catch(error){
    row=await a.one('SELECT * FROM digital_access_leases WHERE owner=? AND request_id=?',owner,requestId);
    if(!row){
     if(error instanceof DigitalAccessChanged){
      const stamp=this.clock(),current=await a.one('SELECT g.used,(i.quantity-i.refunded_quantity)*g.uses_per_unit total_uses '+BASE_JOIN+` JOIN sessions ses ON ses.user_id=g.owner AND ses.token=?
       WHERE g.id=? AND g.owner=? AND ${BASE_GUARD} AND g.starts<=? AND g.expires>? AND ses.expires>?
       AND g.used>=(i.quantity-i.refunded_quantity)*g.uses_per_unit`,session,grant.id,owner,stamp,stamp,Date.now());
      if(current&&current.used>=current.total_uses)this.fail(402,'当前可用访问次数不足。');
     }
     throw error;
    }
    duplicate=true;
   }
   if(!row)row=await a.one('SELECT * FROM digital_access_leases WHERE id=? AND owner=?',id,owner);
  }
  if(!row||row.grant_id!==grant.id)this.fail(409,'使用编号已用于其他数字权益。');
  if(row.session_hash!==session)this.fail(409,'使用编号属于旧登录会话，请核对记录后创建新编号。');
  return {item:await this.summary(grant),lease:this.leaseItem(row),duplicate,productionEnabled:false};
 }
 async media(id:string):Promise<Response>{
  const a=this.a,owner=a.user.id,session=await this.session();let r=await this.validLease(id,owner,session,this.clock());if(!r||await privacyMediaDeleted(a,r.media_id))this.fail(403,'使用凭证、会话或数字权益已失效。');
  const object=await a.env.BUCKET.head(r.object_key);if(!object)this.fail(404,'测试素材文件不存在。');
  let offset=0,length=object.size,status=200;const headers:Record<string,string>={'Content-Type':r.mime,'Accept-Ranges':'bytes','Cache-Control':'private, no-store','Referrer-Policy':'no-referrer'};
  const range=a.request.headers.get('range');if(range){const m=/^bytes=(\d*)-(\d*)$/.exec(range);if(!m||!m[1]&&!m[2]||[m[1],m[2]].some(v=>v&&!validInt(Number(v),0,Number.MAX_SAFE_INTEGER)))this.fail(416,'无效媒体范围。');offset=m![1]?Number(m![1]):Math.max(0,object.size-Number(m![2]));const end=m![1]&&m![2]?Math.min(object.size-1,Number(m![2])):object.size-1;if(offset>=object.size||end<offset)this.fail(416,'媒体范围超出文件。');length=end-offset+1;status=206;headers['Content-Range']=`bytes ${offset}-${end}/${object.size}`;}
  const data=await a.env.BUCKET.get(r.object_key,{range:{offset,length}});if(!data)this.fail(404,'测试素材文件不存在。');
  // No If-None-Match shortcut; the authorization is checked again after the asynchronous object reads.
  r=await this.validLease(id,owner,session,this.clock());if(!r||await privacyMediaDeleted(a,r.media_id)){try{await data.body.cancel();}catch{}this.fail(403,'使用凭证、会话或数字权益已失效。');}
  headers['Content-Length']=String(length);return new Response(data.body,{status,headers});
 }

 async route(path:string,method:string):Promise<any>{
  const a=this.a,admin=path.startsWith('/api/admin/');a.require(admin?['admin']:undefined);
  await a.rate('digital-entitlements:'+(method==='GET'?'read:':'write:')+a.user.id,method==='GET'?240:60);
  if(path==='/api/admin/digital-entitlements'&&['GET','PATCH'].includes(method)){
   if(method==='PATCH'){
    const d=await a.body();if(J(Object.keys(d).sort())!==J(Object.keys(DIGITAL_POLICY).sort())||typeof d.enabled!=='boolean'||typeof d.confirmed!=='boolean'||typeof d.ruleVersion!=='string'||d.ruleVersion.length>100||Object.entries(FIXED).some(([k,v])=>d[k]!==v)||!validInt(d.leaseSeconds,30,14400)||d.validityDays!==null&&!validInt(d.validityDays,1,3650)||d.usesPerUnit!==null&&!validInt(d.usesPerUnit,1,1000)||d.enabled&&!ready(d))this.fail(400,'请完整配置有限次数、有效期和使用窗口的沙箱规则。');
    const previous=await this.policy();if(!Number.isSafeInteger(d.revision)||d.revision!==previous.revision)this.fail(409,'数字权益规则已更新，请刷新。');
    const policy={...d,ruleVersion:d.ruleVersion.trim(),revision:d.revision+1};await a.run("INSERT OR IGNORE INTO settings VALUES('digital_entitlements',?)",J(DIGITAL_POLICY));const r=await a.run("UPDATE settings SET data=? WHERE key='digital_entitlements' AND json_extract(data,'$.revision')=?",J(policy),previous.revision);if(!r.meta.changes)this.fail(409,'数字权益规则已更新，请刷新。');await a.audit('digital.policy','sandbox','finite sandbox leases; production disabled');
   }
   const rows=await a.all("SELECT s.*,m.mime,m.filename,c.data content_data FROM digital_sandbox_assets s LEFT JOIN media m ON m.id=s.media_id LEFT JOIN contents c ON c.kind='courses' AND c.id=s.content_id ORDER BY s.created DESC,s.media_id");
   const courses=await a.all("SELECT id,data FROM contents WHERE kind='courses' AND status='published' AND json_type(data,'$.sandboxOnly')='true' AND coalesce(json_extract(data,'$.creatorId'),'')='' AND coalesce(json_extract(data,'$.mediaUrl'),'')='' AND coalesce(json_extract(data,'$.audioUrl'),'')='' ORDER BY id");
   return {policy:await this.policy(),assets:rows.map((r:any)=>this.assetItem(r)),contents:courses.map((r:any)=>({id:r.id,title:title(r)})),productionEnabled:false};
  }
  if(path==='/api/admin/digital-entitlements/assets'&&method==='POST'){
   const d=await a.body();if(Object.keys(d).sort().join(',')!=='contentId,mediaId,sandboxOnly'||d.sandboxOnly!==true||typeof d.mediaId!=='string'||!/^[A-Za-z0-9:_-]{1,100}$/.test(d.mediaId)||typeof d.contentId!=='string'||!/^[A-Za-z0-9:_-]{1,100}$/.test(d.contentId))this.fail(400,'请明确选择本人上传、独立隔离的测试素材和课程。');
   const old=await a.one('SELECT * FROM digital_sandbox_assets WHERE media_id=? OR content_id=?',d.mediaId,d.contentId);if(old){if(old.media_id!==d.mediaId||old.owner!==a.user.id||old.content_id!==d.contentId)this.fail(409,'此素材已绑定其他测试课程。');return {item:await this.asset(d.mediaId),duplicate:true,productionEnabled:false};}
   const stamp=this.clock();await this.batch([a.stmt("INSERT INTO digital_sandbox_assets VALUES(?,?,?,'active',?,?)",d.mediaId,d.contentId,a.user.id,stamp,stamp)]);await a.audit('digital.asset',d.mediaId,'permanently isolated sandbox asset');return {item:await this.asset(d.mediaId),duplicate:false,productionEnabled:false};
  }
  const disable=/^\/api\/admin\/digital-entitlements\/assets\/([a-f0-9-]{36})\/disable$/.exec(path);
  if(disable&&method==='POST'){if(Object.keys(await a.body()).length)this.fail(400,'停用测试素材不接受其他字段。');await this.asset(disable[1]);await a.run("UPDATE digital_sandbox_assets SET status='disabled',updated=? WHERE media_id=? AND status='active'",this.clock(),disable[1]);await a.audit('digital.asset.disable',disable[1],'marker retained permanently');return {item:await this.asset(disable[1]),productionEnabled:false};}
  const lease=/^\/api\/digital-entitlements\/leases\/([a-f0-9-]{36})\/media$/.exec(path);
  if(lease){if(method!=='GET')this.fail(405,'媒体访问仅支持GET。');return this.media(lease[1]);}
  const base=admin?'/api/admin/digital-entitlements/grants':'/api/digital-entitlements';
  if(path===base&&method==='GET'){
   const before=a.url.searchParams.get('before'),where=admin?[]:['owner=?'],args:any[]=admin?[]:[a.user.id];
   if(before){const r=await this.find(before,admin);where.push('(created,id)<(?,?)');args.push(r.created,r.id);}
   const rows=await a.all('SELECT * FROM digital_entitlement_grants'+(where.length?' WHERE '+where.join(' AND '):'')+' ORDER BY created DESC,id DESC LIMIT 51',...args),items=[];
   for(const r of rows.slice(0,50))items.push(await this.summary(r));return {items,next:rows.length>50?rows[49].id:null,settings:await this.settings()};
  }
  const match=new RegExp('^'+base+'/([^/]+)(/access)?$').exec(path);
  if(match){let id:string;try{id=decodeURIComponent(match[1]);}catch{this.fail(400,'数字权益编号编码无效。');}if(!/^[A-Za-z0-9:_-]{1,100}$/.test(id))this.fail(400,'数字权益编号无效。');const grant=await this.find(id,admin);if(!match[2]&&method==='GET')return this.detail(grant);if(!admin&&match[2]==='/access'&&method==='POST'){const d=await a.body();if(Object.keys(d).join(',')!=='requestId'||typeof d.requestId!=='string'||!/^[A-Za-z0-9:_-]{1,100}$/.test(d.requestId))this.fail(400,'使用数字权益仅接受幂等编号。');return this.acquire(grant,d.requestId);}}
  return this.fail(404,'未找到数字测试权益接口。');
 }
}

export async function digitalEntitlementsRoute(a:any,path:string,method:string,fail:(s:number,m:string)=>never){
 if(!(path==='/api/digital-entitlements'||path.startsWith('/api/digital-entitlements/')||path==='/api/admin/digital-entitlements'||path.startsWith('/api/admin/digital-entitlements/')))return undefined;
 await initDigitalEntitlements(a);return new DigitalEntitlements(a,fail).route(path,method);
}
