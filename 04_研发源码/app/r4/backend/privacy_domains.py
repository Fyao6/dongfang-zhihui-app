"""Owner-confirmed local domain cleanup. External erasure and secure media wiping are separate facts."""
import copy
import hashlib
import json
import re
import sqlite3
import time
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

DOMAINS=('creatorDrafts','creatorPrivateProfiles','serviceRequestContent','privateMedia')
SOURCES={'creatorDrafts':('creator_works','owner_id','id'),
    'creatorPrivateProfiles':('creator_profiles','user_id','user_id'),
    'serviceRequestContent':('service_requests','user_id','id'),'privateMedia':('media','owner','id')}
LABELS={'creatorDrafts':'未公开创作者草稿','creatorPrivateProfiles':'未完成入驻申请',
    'serviceRequestContent':'本人咨询申请正文','privateMedia':'无引用的本人素材'}
EXPORT_KEYS={'creatorDrafts':'creatorWorks','creatorPrivateProfiles':'creatorProfile',
    'serviceRequestContent':'serviceRequests','privateMedia':'uploadedMediaMetadata'}
DEFAULT={'revision':0,'enabled':False,'confirmed':False,'policyVersion':'','retentionDays':dict.fromkeys(DOMAINS)}
NOW_SQL="(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))"
DDL="""
CREATE TABLE IF NOT EXISTS privacy_domain_config(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS privacy_domain_jobs(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,actor TEXT NOT NULL,request_id TEXT NOT NULL,
 mode TEXT NOT NULL CHECK(mode IN ('manual','expiry','closure')),domains TEXT NOT NULL,as_of INTEGER NOT NULL,
 config_data TEXT NOT NULL,pref_revision INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,
 confirmed_by TEXT NOT NULL DEFAULT '',confirmed_at INTEGER NOT NULL DEFAULT 0,
 closure_receipt_id TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,updated INTEGER NOT NULL,
 UNIQUE(owner,request_id));
CREATE INDEX IF NOT EXISTS privacy_domain_job_owner ON privacy_domain_jobs(owner,created,id);
CREATE TABLE IF NOT EXISTS privacy_domain_targets(
 job_id TEXT NOT NULL,owner TEXT NOT NULL,domain TEXT NOT NULL,resource_id TEXT NOT NULL,
 write_at INTEGER,version INTEGER,nonce TEXT NOT NULL,processed INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(job_id,domain,resource_id));
CREATE TABLE IF NOT EXISTS privacy_domain_receipts(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,job_id TEXT,actor TEXT NOT NULL,request_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL,status TEXT NOT NULL,details TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,
 UNIQUE(actor,request_id));
CREATE INDEX IF NOT EXISTS privacy_domain_receipt_owner ON privacy_domain_receipts(owner,created,id);
CREATE TABLE IF NOT EXISTS privacy_media_tombstones(
 media_id TEXT PRIMARY KEY,owner TEXT NOT NULL,receipt_id TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS privacy_object_deletions(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,receipt_id TEXT NOT NULL,media_id TEXT NOT NULL UNIQUE,
 object_key TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN ('pending','processing','retry','completed','manual_review')),
 attempts INTEGER NOT NULL DEFAULT 0,lease_token TEXT NOT NULL DEFAULT '',lease_until INTEGER NOT NULL DEFAULT 0,
 next_attempt INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS privacy_object_queue ON privacy_object_deletions(status,next_attempt,created,id);
CREATE TABLE IF NOT EXISTS privacy_domain_guards(id TEXT PRIMARY KEY,ok INTEGER NOT NULL CHECK(ok=1));
CREATE TRIGGER IF NOT EXISTS privacy_domain_job_identity BEFORE UPDATE OF
 id,owner,actor,request_id,mode,domains,as_of,config_data,pref_revision,closure_receipt_id,created ON privacy_domain_jobs
 BEGIN SELECT RAISE(ABORT,'privacy_domain_job_immutable'); END;
CREATE TRIGGER IF NOT EXISTS privacy_domain_confirmation_identity BEFORE UPDATE OF confirmed_by,confirmed_at ON privacy_domain_jobs
 WHEN OLD.confirmed_at>0 AND (NEW.confirmed_by IS NOT OLD.confirmed_by OR NEW.confirmed_at IS NOT OLD.confirmed_at)
 BEGIN SELECT RAISE(ABORT,'privacy_domain_confirmation_immutable'); END;
CREATE TRIGGER IF NOT EXISTS privacy_domain_target_identity BEFORE UPDATE OF
 job_id,owner,domain,resource_id,write_at,version,nonce ON privacy_domain_targets
 BEGIN SELECT RAISE(ABORT,'privacy_domain_target_immutable'); END;
CREATE TRIGGER IF NOT EXISTS privacy_media_tombstone_identity BEFORE UPDATE ON privacy_media_tombstones
 BEGIN SELECT RAISE(ABORT,'privacy_media_tombstone_immutable'); END;
CREATE TRIGGER IF NOT EXISTS privacy_media_tombstone_no_delete BEFORE DELETE ON privacy_media_tombstones
 BEGIN SELECT RAISE(ABORT,'privacy_media_tombstone_permanent'); END;
CREATE TRIGGER IF NOT EXISTS privacy_object_identity BEFORE UPDATE OF id,owner,receipt_id,media_id,object_key,created
 ON privacy_object_deletions BEGIN SELECT RAISE(ABORT,'privacy_object_identity_immutable'); END;
"""
REFERENCE_FIELDS=[('contents','data'),('settings','data'),('posts','media_url'),('posts','body'),
    ('creator_works','data'),('creator_profiles','data'),('revisions','snapshot'),
    ('commerce_products','data'),('commerce_order_items','snapshot_data'),
    ('membership_plans','data'),('membership_plan_versions','data'),('membership_order_snapshots','data'),
    ('card_deck_versions','data'),('card_draws','snapshot'),('records','data'),
    ('privacy_conversations','data'),('messages','body'),('service_requests','body'),
    ('ai_gateway_jobs','output_text'),('payment_support_tickets','message'),('payment_support_actions','reply'),
    ('after_sales_actions','data')]
from card_imports import REF_FIELDS as card_import_ref_fields
from card_history_migration import REFERENCE_FIELDS as card_history_ref_fields
REFERENCE_FIELDS += card_import_ref_fields+card_history_ref_fields
REFERENCE_FIELDS += [(table,column) for table,columns in {'bazi_sample_versions':['data'],'bazi_sample_cases':['data'],'bazi_sample_results':['data'],'bazi_sample_raw_chunks':['data'],'bazi_sample_field_results':['data'],'bazi_sample_reviews':['evidence','note'],'bazi_sample_operations':['response_data']}.items() for column in columns]
DIRECT_MEDIA_FIELDS=[('digital_sandbox_assets','media_id'),('digital_order_snapshots','media_id'),
    ('digital_entitlement_grants','media_id')]


def now():return time.time_ns()//1_000_000
def dump(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(dump(value).encode('utf-8')).hexdigest()
def tables(db):return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
def identifier(value):return '"'+value.replace('"','""')+'"'
def columns(db,table):return {row[1] for row in db.execute('PRAGMA table_info('+identifier(table)+')')}
def config(db):
    row=db.execute('SELECT data FROM privacy_domain_config WHERE id=1').fetchone()
    raw=json.loads(row['data']) if row else {}
    return {**copy.deepcopy(DEFAULT),**raw,'retentionDays':{**DEFAULT['retentionDays'],**raw.get('retentionDays',{})}}


def reference_match(expression,id_expression):
    reference="'/api/media/'||"+id_expression
    # json_tree decodes historical escaped slashes/unicode before checking URLs.
    return ("(instr(coalesce("+expression+",''),"+reference+")>0 OR CASE WHEN json_valid("+expression+")"
        " THEN EXISTS(SELECT 1 FROM json_tree("+expression+") jt WHERE jt.type='text' AND instr(jt.atom,"+reference+")>0) ELSE 0 END)")


def unknown_reference_match(expression,id_expression):
    return ('('+reference_match(expression,id_expression)+' OR instr(coalesce('+expression+",''),"+id_expression+
        ')>0 OR CASE WHEN json_valid('+expression+') THEN EXISTS(SELECT 1 FROM json_tree('+expression+
        ") jt WHERE jt.type='text' AND jt.atom="+id_expression+') ELSE 0 END)')


def media_reference_sql(available,id_expression='r.id'):
    clauses=[]
    for table,column in REFERENCE_FIELDS:
        if column in available.get(table,set()):
            clauses.append('EXISTS(SELECT 1 FROM '+table+' rf WHERE '+reference_match('rf.'+column,id_expression)+')')
    for table,column in DIRECT_MEDIA_FIELDS:
        if column in available.get(table,set()):
            clauses.append('EXISTS(SELECT 1 FROM '+table+' rd WHERE rd.'+column+'='+id_expression+')')
    # Unknown tables are never cleanup targets. Their possible media references are protected.
    for table,column in unknown_reference_fields(available):
        value='rf.'+identifier(column)
        clauses.append('EXISTS(SELECT 1 FROM '+identifier(table)+' rf WHERE '+unknown_reference_match(value,id_expression)+')')
    return '('+' OR '.join(clauses or ['0'])+')'


def eligibility_sql(domain,available,alias='r'):
    a=alias+'.'
    if domain=='creatorDrafts':
        return (a+"status='draft' AND NOT EXISTS(SELECT 1 FROM posts p WHERE p.id="+a+"id)"
            " AND NOT EXISTS(SELECT 1 FROM contents c WHERE c.id="+a+"id)"
            " AND NOT EXISTS(SELECT 1 FROM creator_reviews v WHERE v.work_id="+a+"id)"
            " AND NOT EXISTS(SELECT 1 FROM commerce_products p WHERE p.content_id="+a+"id)"
            " AND NOT EXISTS(SELECT 1 FROM commerce_order_items i WHERE i.content_id="+a+"id)"
            " AND NOT EXISTS(SELECT 1 FROM commerce_entitlements e WHERE e.content_id="+a+"id)")
    if domain=='creatorPrivateProfiles':
        return (a+"status IN ('pending','rejected') AND "+a+"teacher_id=''"
            " AND NOT EXISTS(SELECT 1 FROM contents c WHERE json_extract(c.data,'$.creatorId')="+a+"user_id)"
            " AND NOT EXISTS(SELECT 1 FROM creator_works w WHERE w.owner_id="+a+"user_id AND w.status='published')")
    if domain=='serviceRequestContent':
        return '('+a+"body!='' OR "+a+"preferred_date!='')"
    if domain=='privateMedia':
        managed='1'
        if 'object_key' in available.get('media',set()):
            managed=(a+"object_key='media/'||"+a+"id AND NOT EXISTS(SELECT 1 FROM media same"
                " WHERE same.object_key="+a+"object_key AND same.id!="+a+"id)")
        return '(NOT '+media_reference_sql(available,a+'id')+' AND '+managed+')'
    raise ValueError('unknown personal domain')


def tracking_sql(available):
    statements=[]
    for domain,(table,owner,key) in SOURCES.items():
        if table not in available:continue
        for action in ('INSERT','UPDATE'):
            name='privacy_domain_track_'+table+'_'+action.lower()
            statements.append('CREATE TRIGGER IF NOT EXISTS '+name+' AFTER '+action+' ON '+table+
                " BEGIN INSERT INTO privacy_retention_tracking VALUES(NEW."+owner+",'"+domain+"',NEW."+key+",'',"+NOW_SQL+",1,lower(hex(randomblob(16))),'observed-write')"
                " ON CONFLICT(owner,scope,k1,k2) DO UPDATE SET write_at=excluded.write_at,version=privacy_retention_tracking.version+1,nonce=excluded.nonce,basis=excluded.basis; END;")
        statements.append('CREATE TRIGGER IF NOT EXISTS privacy_domain_track_'+table+'_delete AFTER DELETE ON '+table+
            ' BEGIN DELETE FROM privacy_retention_tracking WHERE owner=OLD.'+owner+" AND scope='"+domain+"' AND k1=OLD."+key+" AND k2=''; END;")
    return statements


def reference_guard_sql(available):
    statements=[]
    for table,column in REFERENCE_FIELDS:
        if column not in available.get(table,set()):continue
        for action in ('INSERT','UPDATE'):
            name='privacy_deleted_reference_'+table+'_'+column+'_'+action.lower()
            statements.append('CREATE TRIGGER IF NOT EXISTS '+name+' BEFORE '+action+
                (' OF '+column if action=='UPDATE' else '')+' ON '+table+
                ' BEGIN SELECT CASE WHEN EXISTS(SELECT 1 FROM privacy_media_tombstones dead WHERE '+
                reference_match('NEW.'+column,'dead.media_id')+") THEN RAISE(ABORT,'privacy_deleted_media_reference') END; END;")
    for table,column in DIRECT_MEDIA_FIELDS:
        if column not in available.get(table,set()):continue
        for action in ('INSERT','UPDATE'):
            name='privacy_deleted_direct_'+table+'_'+action.lower()
            statements.append('CREATE TRIGGER IF NOT EXISTS '+name+' BEFORE '+action+
                (' OF '+column if action=='UPDATE' else '')+' ON '+table+
                ' BEGIN SELECT CASE WHEN EXISTS(SELECT 1 FROM privacy_media_tombstones WHERE media_id=NEW.'+column+
                ") THEN RAISE(ABORT,'privacy_deleted_media_reference') END; END;")
    if 'media' in available:
        for action in ('INSERT','UPDATE'):
            check='EXISTS(SELECT 1 FROM privacy_media_tombstones WHERE media_id=NEW.id)'
            if 'object_key' in available['media']:
                check+=' OR EXISTS(SELECT 1 FROM privacy_object_deletions WHERE object_key=NEW.object_key)'
            statements.append('CREATE TRIGGER IF NOT EXISTS privacy_deleted_media_'+action.lower()+' BEFORE '+action+
                " ON media BEGIN SELECT CASE WHEN "+check+" THEN RAISE(ABORT,'privacy_deleted_media_identity') END; END;")
    for table,column in unknown_reference_fields(available):
        for action in ('INSERT','UPDATE'):
            name='privacy_unknown_ref_'+hashlib.sha256((table+'\0'+column+'\0'+action).encode()).hexdigest()[:24]
            value='NEW.'+identifier(column)
            statements.append('CREATE TRIGGER IF NOT EXISTS '+name+' BEFORE '+action+
                (' OF '+identifier(column) if action=='UPDATE' else '')+' ON '+identifier(table)+
                ' BEGIN SELECT CASE WHEN EXISTS(SELECT 1 FROM privacy_media_tombstones dead WHERE '+
                unknown_reference_match(value,'dead.media_id')+") THEN RAISE(ABORT,'privacy_deleted_media_reference') END; END;")
    return statements


def init_schema(db):
    db.executescript(DDL)
    db.execute('INSERT OR IGNORE INTO privacy_domain_config VALUES(1,?)',(dump(DEFAULT),))
    available={table:columns(db,table) for table in tables(db)}
    for statement in tracking_sql(available)+reference_guard_sql(available):db.execute(statement)


def media_deleted(db,media_id):
    return bool(db.execute('SELECT 1 FROM privacy_media_tombstones WHERE media_id=?',(media_id,)).fetchone())


# Explicit ownership registry: schema discovery never invents a delete predicate.
REGISTRY={}
def _owned(group,column,names):
    for name in names.split():REGISTRY[name]=(group,'r.'+column+'=?')
_owned('identityAndSecurity','owner','account_closure_challenges account_closure_receipts account_lifecycle account_revoked_sessions')
_owned('identityAndSecurity','user_id','sessions')
REGISTRY['users']=('identityAndSecurity','r.id=?')
_owned('privacyAndSourceAudits','owner','privacy_record_epochs privacy_retention_jobs privacy_retention_receipts privacy_retention_targets privacy_retention_tracking privacy_saved_deletions memory_actions memory_cleanup_receipts memory_job_bindings memory_provider_consents memory_state memory_tombstones privacy_domain_jobs privacy_domain_targets privacy_domain_receipts privacy_media_tombstones privacy_object_deletions')
_owned('privacyAndSourceAudits','user_id','privacy_preferences privacy_events privacy_requests privacy_transfers')
_owned('privacyAndSourceAudits','actor','audits revisions secret_reference_actions secret_reference_plans commission_events commission_facts account_action_fences')
_owned('deviceConnections','owner','devices')
_owned('commerceAndFulfilment','owner','commerce_aftersale_requests commerce_carts commerce_entitlements commerce_inventory_events commerce_orders commerce_payment_events payment_late_cases payment_recovery_jobs payment_recovery_requests payment_support_tickets')
_owned('membershipQuotaCommissionAndAftersale','owner','membership_ai_allocations membership_ai_events membership_ai_periods membership_events membership_order_snapshots membership_purchase_locks membership_subscriptions digital_access_leases digital_entitlement_grants digital_entitlement_uses digital_order_snapshots digital_sandbox_assets ai_gateway_attempts ai_gateway_grants ai_gateway_jobs ai_gateway_provider_consents ai_gateway_quota_events ai_gateway_wallets after_sales_actions after_sales_cases after_sales_finance_actions after_sales_finance_heads after_sales_finance_links after_sales_finance_reversals after_sales_finance_targets after_sales_items after_sales_shipments card_daily_quota card_record_epochs card_zone_preferences')
_owned('membershipQuotaCommissionAndAftersale','beneficiary','commission_adjustments commission_invites commission_ledger commission_statements')
_owned('identityAndSecurity','user_id','commission_grants')
REGISTRY['commission_attributions']=('membershipQuotaCommissionAndAftersale','(r.owner=? OR r.beneficiary=?)')
REGISTRY['posts']=('communityAndShared','r.author_id=?')
REGISTRY['messages']=('communityAndShared','(r.sender=? OR r.recipient=?)')
REGISTRY['friendships']=('communityAndShared','(r.sender=? OR r.recipient=?)')
REGISTRY['creator_actions']=('communityAndShared','r.visitor=?')
REGISTRY['creator_events']=('communityAndShared','(r.owner_id=? OR r.visitor=?)')
REGISTRY['creator_follows']=('communityAndShared','(r.creator_id=? OR r.follower_id=?)')
REGISTRY['contents']=('publishedCreatorAndReviews',"json_extract(r.data,'$.creatorId')=?")
REGISTRY['creator_reviews']=('publishedCreatorAndReviews','EXISTS(SELECT 1 FROM creator_works w WHERE w.id=r.work_id AND w.owner_id=?)')
REGISTRY['creator_works']=('publishedCreatorAndReviews','r.owner_id=?')
REGISTRY['creator_profiles']=('publishedCreatorAndReviews','r.user_id=?')
REGISTRY['service_requests']=('commerceAndFulfilment','r.user_id=?')
REGISTRY['media']=('publishedCreatorAndReviews','r.owner=?')
REGISTRY['commerce_order_items']=('commerceAndFulfilment','EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=r.order_id AND o.owner=?)')
REGISTRY['commerce_reservations']=REGISTRY['commerce_order_items']
REGISTRY['payment_callback_inbox']=REGISTRY['commerce_order_items']
REGISTRY['payment_callback_transactions']=REGISTRY['commerce_order_items']
REGISTRY['payment_callback_attempts']=('commerceAndFulfilment','EXISTS(SELECT 1 FROM payment_callback_inbox i JOIN commerce_orders o ON o.id=i.order_id WHERE i.id=r.receipt_id AND o.owner=?)')
REGISTRY['payment_recovery_attempts']=('commerceAndFulfilment','EXISTS(SELECT 1 FROM payment_recovery_jobs j WHERE j.id=r.job_id AND j.owner=?)')
REGISTRY['payment_late_attempts']=('commerceAndFulfilment','EXISTS(SELECT 1 FROM payment_late_cases c WHERE c.id=r.case_id AND c.owner=?)')
REGISTRY['payment_support_actions']=('commerceAndFulfilment','EXISTS(SELECT 1 FROM payment_support_tickets t WHERE t.id=r.ticket_id AND t.owner=?)')
REGISTRY['after_sales_inspections']=('membershipQuotaCommissionAndAftersale','EXISTS(SELECT 1 FROM after_sales_cases c WHERE c.id=r.case_id AND c.owner=?)')
REGISTRY['after_sales_inspection_items']=('membershipQuotaCommissionAndAftersale','EXISTS(SELECT 1 FROM after_sales_items i WHERE i.id=r.case_item_id AND i.owner=?)')
REGISTRY['commission_snapshots']=('membershipQuotaCommissionAndAftersale','EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=r.order_id AND o.owner=?)')
REGISTRY['commission_payments']=('membershipQuotaCommissionAndAftersale','EXISTS(SELECT 1 FROM commission_statements s WHERE s.id=r.statement_id AND s.beneficiary=?)')
REGISTRY['commission_statement_lines']=REGISTRY['commission_payments']
OLD_SCOPES={'records':('records','owner'), 'conversations':('privacy_conversations','user_id'),
    'timer':('timer_runs','owner'),'activity':('activity_daily','user_id'),
    'measurements':('measurements','connection_id'),'cards':('card_draws','owner'),'memory':('memory_entries','owner')}
SYSTEM_TABLES=set('settings commerce_config commerce_prices commerce_products commerce_sku_variants commerce_skus after_sales_config commission_config commission_rules membership_channel_mappings membership_plans membership_plan_versions card_deck_versions secret_reference_state privacy_retention_config privacy_domain_config privacy_domain_guards payment_callback_guards __drizzle_migrations rate_limits'.split())
from local_tasks import privacy_registry as local_task_privacy_registry
REGISTRY.update(local_task_privacy_registry())
SYSTEM_TABLES.update(('ops_runtime_identity','ops_task_config','ops_task_schedules'))
from payment_routing import privacy_registry as routing_privacy_registry
REGISTRY.update(routing_privacy_registry())
from bazi_samples import privacy_registry as sample_privacy_registry
REGISTRY.update(sample_privacy_registry())
from card_imports import TABLES as card_import_tables
for table in card_import_tables:REGISTRY[table]=('privacyAndSourceAudits','r.owner=?')
from card_history_migration import privacy_registry as card_history_privacy_registry
REGISTRY.update(card_history_privacy_registry())
SYSTEM_TABLES.update(('payment_routing_config','payment_routing_atomic_guards'))
EXTRA_KNOWN={'card_draw_actions','card_practice_events','card_draw_requests'}
RETAINED_PURPOSES={
    'identityAndSecurity':'身份归属与账号安全；正式期限待确认',
    'privacyAndSourceAudits':'最小授权、安全及处理证明；正式期限待确认',
    'deviceConnections':'设备连接与授权归属；断连和保留政策待确认',
    'commerceAndFulfilment':'购物状态、成交履约、资金核对与售后；各类正式期限待确认',
    'membershipQuotaCommissionAndAftersale':'已确认权益、使用及资金归属；不抹掉已用或改余额',
    'communityAndShared':'公开或共有互动及对方权益；删除或匿名化政策待确认',
    'publishedCreatorAndReviews':'已公开、审核/申诉或尚有引用的数据；保留政策待确认'}


def unknown_reference_fields(available):
    known=set(REGISTRY)|SYSTEM_TABLES|EXTRA_KNOWN|{v[0] for v in OLD_SCOPES.values()}|{v[0] for v in SOURCES.values()}
    return [(table,column) for table,fields in available.items() if table not in known and not table.startswith('sqlite_') for column in fields]


def available_schema(db):return {table:columns(db,table) for table in tables(db)}
def source_rows(db,domain,owner):
    table,column,key=SOURCES[domain]
    return db.execute('SELECT r.*,r.'+key+' resource_id FROM '+table+' r WHERE r.'+column+'=? ORDER BY r.'+key,(owner,)).fetchall()
def tracker(db,owner,domain,resource_id):
    return db.execute("SELECT * FROM privacy_retention_tracking WHERE owner=? AND scope=? AND k1=? AND k2=''",(owner,domain,resource_id)).fetchone()


def reason_for(db,domain,row,available=None):
    available=available or available_schema(db)
    table,owner,key=SOURCES[domain]
    if db.execute('SELECT 1 FROM '+table+' r WHERE r.'+key+'=? AND '+eligibility_sql(domain,available),(row[key],)).fetchone():return ''
    if domain=='creatorDrafts':
        if row['status']!='draft' or db.execute('SELECT 1 FROM creator_reviews WHERE work_id=?',(row['id'],)).fetchone():return 'published_or_reviewed'
        return 'transaction_linked' if db.execute('SELECT 1 FROM commerce_order_items WHERE content_id=?',(row['id'],)).fetchone() else 'referenced'
    if domain=='creatorPrivateProfiles':return 'published_or_reviewed'
    if domain=='serviceRequestContent':return 'missing'
    if 'object_key' in available.get('media',set()):
        if row['object_key']!='media/'+row['id']:return 'unmanaged_object_key'
        if db.execute('SELECT 1 FROM media WHERE object_key=? AND id!=?',(row['object_key'],row['id'])).fetchone():return 'shared_object_key'
    if any(db.execute('SELECT 1 FROM '+table+' WHERE '+column+'=?',(row['id'],)).fetchone() for table,column in DIRECT_MEDIA_FIELDS if column in available.get(table,set())):return 'registered_digital_asset'
    return 'referenced'


def retained_inventory(db,owner,available=None):
    available=available or available_schema(db);counts=dict.fromkeys(RETAINED_PURPOSES,0)
    for table,(group,predicate) in REGISTRY.items():
        if table not in available:continue
        # New domains retain only their protected source records; service metadata is retained after scrub.
        if table in ('creator_works','creator_profiles','media'):
            domain=next(domain for domain,spec in SOURCES.items() if spec[0]==table)
            predicate+=' AND NOT ('+eligibility_sql(domain,available)+')'
        counts[group]+=db.execute('SELECT count(*) FROM '+table+' r WHERE '+predicate,[owner]*predicate.count('?')).fetchone()[0]
    return [{'id':key,'recordCount':count,'reasonCode':'policy_unconfirmed','purpose':RETAINED_PURPOSES[key],
        'retentionDays':None,'policyConfirmed':False} for key,count in counts.items()]


def inventory(db,owner,stamp):
    cfg=config(db);available=available_schema(db);domains=[]
    for domain in DOMAINS:
        rows=source_rows(db,domain,owner);reasons={};eligible=unknown=started=adoptable=0
        for row in rows:
            why=reason_for(db,domain,row,available);track=tracker(db,owner,domain,row['resource_id'])
            eligible+=not why
            if why:reasons[why]=reasons.get(why,0)+1
            unknown+=not track or track['basis']!='observed-write';started+=bool(track and track['basis']=='protection-start');adoptable+=track is None
        domains.append({'id':domain,'label':LABELS[domain],'total':len(rows),'eligible':eligible,'protected':len(rows)-eligible,
            'ageUnknown':unknown,'protectionStarted':started,'adoptableUnknown':adoptable,'retentionDays':cfg['retentionDays'][domain],
            'deleteMode':'scrub' if domain=='serviceRequestContent' else 'delete-with-object-queue' if domain=='privateMedia' else 'delete',
            'exportKey':EXPORT_KEYS[domain],'binaryIncluded':False,'blockedReasons':[{'code':key,'count':value} for key,value in sorted(reasons.items())],
            'entryPoint':'/api/privacy/domains/'+domain+'/records'})
    old_config_row=db.execute("SELECT data FROM settings WHERE key='privacy'").fetchone()
    old_cfg=json.loads(old_config_row['data']) if old_config_row else {}
    executor_row=db.execute('SELECT data FROM privacy_retention_config WHERE id=1').fetchone()
    old_executor=json.loads(executor_row['data']) if executor_row else {}
    for scope,(table,column) in OLD_SCOPES.items():
        if table not in available:continue
        predicate='EXISTS(SELECT 1 FROM devices d WHERE d.id=r.connection_id AND d.owner=?)' if scope=='measurements' else 'r.'+column+'=?'
        total=db.execute('SELECT count(*) FROM '+table+' r WHERE '+predicate,(owner,)).fetchone()[0]
        tracking=db.execute("SELECT count(*) n,coalesce(sum(basis='protection-start'),0) started FROM privacy_retention_tracking WHERE owner=? AND scope=?",(owner,scope)).fetchone()
        days=old_cfg.get('retention',{}).get(scope+'Days') if scope in ('records','conversations') else old_executor.get('retentionDays',{}).get(scope)
        extra={}
        if scope=='conversations':
            extra['legacyGatewayOutputs']=db.execute("SELECT count(*) FROM ai_gateway_jobs WHERE owner=? AND output_text IS NOT NULL AND output_text!=''",(owner,)).fetchone()[0]
        domains.append({'id':scope,'label':scope,'total':total,'eligible':total,'protected':0,'ageUnknown':max(0,total-tracking['n']),
            'retentionDays':days,'deleteMode':'existing-entry','exportKey':scope,'binaryIncluded':False,'blockedReasons':[],
            'entryPoint':'/api/memory' if scope=='memory' else '/api/privacy/requests' if scope=='records' else '/api/privacy/saved-conversations' if scope=='conversations' else '/api/privacy/retention',
            'protectionStarted':tracking['started'],'adoptableUnknown':max(0,total-tracking['n']),'details':extra})
    known=set(REGISTRY)|SYSTEM_TABLES|EXTRA_KNOWN|{value[0] for value in OLD_SCOPES.values()}|{value[0] for value in SOURCES.values()}
    unknown=sorted(table for table in available if table not in known and not table.startswith('sqlite_'))
    return {'accountId':owner,'asOf':stamp,'config':cfg,'domains':domains,'retained':retained_inventory(db,owner,available),
        'external':{'providers':'pending-confirmation','backupsAndWAL':'pending-confirmation','vectorIndex':'not-implemented',
            'externalCache':'not-implemented','browserLocalData':'not-automatically-cleared'},
        'unclassifiedOwnerTables':unknown,'schedulerDeployed':False}


def object_metadata(row):
    return {'id':row['id'],'receiptId':row['receipt_id'],'mediaId':row['media_id'],'status':row['status'],
        'attempts':row['attempts'],'leaseUntil':row['lease_until'],'nextAttempt':row['next_attempt'],
        'lastError':row['last_error'],'created':row['created'],'updated':row['updated']}


def objects_summary(db,job_id=None,*,receipt_id=None):
    result={'applicable':'object_key' in columns(db,'media'),'pending':0,'retry':0,'verified':0,'manualReview':0}
    for row in db.execute('''SELECT o.status,count(*) n FROM privacy_object_deletions o
        JOIN privacy_domain_receipts r ON r.id=o.receipt_id WHERE '''+('r.id=?' if receipt_id is not None else 'r.job_id=?')+' GROUP BY o.status',
        (receipt_id if receipt_id is not None else job_id,)):
        key='verified' if row['status']=='completed' else 'manualReview' if row['status']=='manual_review' else 'retry' if row['status']=='retry' else 'pending'
        result[key]+=row['n']
    return result


def job_item(db,row):
    counts=db.execute("""SELECT count(*) total,sum(CASE WHEN processed=0 AND domain!='privateMedia' THEN 1 ELSE 0 END) nonmedia,
        sum(CASE WHEN processed=0 AND domain='privateMedia' THEN 1 ELSE 0 END) media
        FROM privacy_domain_targets WHERE job_id=?""",(row['id'],)).fetchone()
    nonmedia,media=counts['nonmedia'] or 0,counts['media'] or 0
    objects=objects_summary(db,row['id']);pending_objects=objects['pending']+objects['retry']+objects['manualReview']
    status='preview' if not row['confirmed_at'] else 'ready' if nonmedia+media else 'manual_review' if objects['manualReview'] else 'objects_pending' if pending_objects else 'completed'
    frozen=json.loads(row['config_data'])
    processed={str(r['processed']):r['n'] for r in db.execute('SELECT processed,count(*) n FROM privacy_domain_targets WHERE job_id=? GROUP BY processed',(row['id'],))}
    return {'id':row['id'],'accountId':row['owner'],'mode':row['mode'],'domains':json.loads(row['domains']),
        'asOf':row['as_of'],'configRevision':frozen['revision'],'policyVersion':frozen['policyVersion'],
        'version':row['version'],'status':status,'phase':'non_media' if nonmedia else 'media' if media else 'completed',
        'planned':counts['total'],'pending':nonmedia+media,'pendingNonMedia':nonmedia,'pendingMedia':media,
        'pendingObjects':pending_objects,'truncated':bool(frozen.get('_truncated')),'confirmedAt':row['confirmed_at'],
        'confirmationSource':'account-closure' if row['closure_receipt_id'] else 'owner' if row['confirmed_at'] else 'none',
        'created':row['created'],'updated':row['updated'],'summary':{'processed':processed,'objects':objects}}


def receipt_item(db,row):
    details=json.loads(row['details'])
    if row['job_id'] is None:
        return {**details,'id':row['id'],'accountId':row['owner'],'requestId':row['request_id'],
            'mode':'adopt','jobId':None,'status':'local_completed','created':row['created']}
    objects=objects_summary(db,receipt_id=row['id'])
    status='manual_review' if objects['manualReview'] else 'objects_pending' if objects['pending']+objects['retry'] else 'local_completed'
    return {**details,'id':row['id'],'jobId':row['job_id'],'accountId':row['owner'],'status':status,
        'objects':objects,'created':row['created'],'updated':row['updated']}


def authorized_job(db,row,actor,admin=False,internal_closure=False):
    if not admin and actor!=row['owner']:return False
    if row['mode']=='closure':
        proof=db.execute('SELECT 1 FROM account_closure_receipts WHERE id=? AND owner=?',(row['closure_receipt_id'],row['owner'])).fetchone()
        if not proof or row['confirmed_by']!=row['owner'] or row['confirmed_at']<=0:return False
        if internal_closure:return actor==row['owner']
        return bool(db.execute("SELECT 1 FROM account_lifecycle WHERE owner=? AND status='closed' AND receipt_id=?",(row['owner'],row['closure_receipt_id'])).fetchone())
    if admin:return row['confirmed_by']==row['owner'] and row['confirmed_at']>0
    return True


def current_preference_revision(db,owner):
    row=db.execute('SELECT revision FROM privacy_preferences WHERE user_id=?',(owner,)).fetchone()
    return row['revision'] if row else 0


def create_job(db,owner,request_id,domains,mode,stamp,*,closure_receipt_id=''):
    frozen=config(db);available=available_schema(db);targets=[];truncated=False
    for domain in domains:
        days=frozen['retentionDays'][domain]
        for row in source_rows(db,domain,owner):
            # Closure freezes media candidates before selected private references are removed.
            if not (mode=='closure' and domain=='privateMedia') and reason_for(db,domain,row,available):continue
            track=tracker(db,owner,domain,row['resource_id'])
            if mode=='expiry' and (type(days) is not int or not track or track['basis'] not in ('observed-write','protection-start') or track['write_at']>stamp-days*86400000):continue
            targets.append((domain,row['resource_id'],track['write_at'] if track else None,track['version'] if track else None,track['nonce'] if track else ''))
    if mode!='closure' and len(targets)>1000:
        targets=targets[:1000];truncated=True
    frozen['_truncated']=truncated
    identifier=str(uuid4());confirmed=stamp if mode=='closure' else 0
    db.execute('INSERT INTO privacy_domain_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (identifier,owner,owner,request_id,mode,dump(domains),stamp,dump(frozen),current_preference_revision(db,owner),0,
         'ready' if confirmed else 'preview',owner if confirmed else '',confirmed,closure_receipt_id,stamp,stamp))
    db.executemany('INSERT INTO privacy_domain_targets VALUES(?,?,?,?,?,?,?,0)',
        [(identifier,owner,*target) for target in targets])
    return db.execute('SELECT * FROM privacy_domain_jobs WHERE id=?',(identifier,)).fetchone()


def apply_batch(db,row,actor,request_id,stamp,error,*,admin=False,internal_closure=False):
    """Caller owns BEGIN IMMEDIATE; targets, claim, actual deletion, receipt and version share that transaction."""
    if not authorized_job(db,row,actor,admin,internal_closure):raise error(404,'未找到本人已确认的清理作业。')
    if not row['confirmed_at']:
        if actor!=row['owner'] or admin:raise error(403,'管理员不能代替本人确认删除。')
        db.execute('UPDATE privacy_domain_jobs SET confirmed_by=?,confirmed_at=? WHERE id=? AND confirmed_at=0',(actor,stamp,row['id']))
        row=db.execute('SELECT * FROM privacy_domain_jobs WHERE id=?',(row['id'],)).fetchone()
    frozen=json.loads(row['config_data']);frozen_public={key:value for key,value in frozen.items() if not key.startswith('_')}
    if row['mode']=='expiry':
        global_row=db.execute("SELECT data FROM settings WHERE key='privacy'").fetchone()
        policy_version=json.loads(global_row['data']).get('policyVersion','') if global_row else ''
        if config(db)!=frozen_public or not frozen['enabled'] or not frozen['confirmed'] or not policy_version or frozen['policyVersion']!=policy_version or current_preference_revision(db,row['owner'])!=row['pref_revision']:
            raise error(409,'到期政策、授权或预览版本已变化，请重新预览。')
    rid=str(uuid4());fingerprint=digest({'jobId':row['id'],'owner':row['owner'],'version':row['version'],'action':'apply'})
    db.execute('INSERT INTO privacy_domain_receipts VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,row['owner'],row['id'],actor,request_id,fingerprint,'claimed','{}',stamp,stamp))
    pending_nonmedia=db.execute("SELECT 1 FROM privacy_domain_targets WHERE job_id=? AND processed=0 AND domain!='privateMedia' LIMIT 1",(row['id'],)).fetchone()
    selected=db.execute('SELECT * FROM privacy_domain_targets WHERE job_id=? AND processed=0 AND domain'+("!='privateMedia'" if pending_nonmedia else "='privateMedia'")+' ORDER BY domain,resource_id LIMIT 100',(row['id'],)).fetchall()
    counts=dict.fromkeys(DOMAINS,0);changed=referenced=missing=0;available=available_schema(db)
    for target in selected:
        domain=target['domain'];table,owner,key=SOURCES[domain]
        source=db.execute('SELECT * FROM '+table+' WHERE '+owner+'=? AND '+key+'=?',(row['owner'],target['resource_id'])).fetchone()
        processed=4
        if source:
            live=tracker(db,row['owner'],domain,target['resource_id'])
            same=(not target['nonce'] and live is None) or bool(live and live['nonce']==target['nonce'] and live['version']==target['version'] and live['write_at']==target['write_at'])
            if not same:processed=2
            elif reason_for(db,domain,source,available):processed=3
            else:
                if domain=='privateMedia':
                    db.execute('INSERT INTO privacy_media_tombstones VALUES(?,?,?,?)',(source['id'],row['owner'],rid,stamp))
                    if 'object_key' in available['media']:
                        db.execute('''INSERT INTO privacy_object_deletions
                            (id,owner,receipt_id,media_id,object_key,status,created,updated) VALUES(?,?,?,?,?,'pending',?,?)''',
                            (str(uuid4()),row['owner'],rid,source['id'],source['object_key'],stamp,stamp))
                if domain=='serviceRequestContent':
                    sql="UPDATE service_requests AS r SET body='',preferred_date='' WHERE user_id=? AND id=? AND "+eligibility_sql(domain,available)
                else:sql='DELETE FROM '+table+' AS r WHERE r.'+owner+'=? AND r.'+key+'=? AND '+eligibility_sql(domain,available)
                deleted=db.execute(sql,(row['owner'],target['resource_id'])).rowcount
                if deleted!=1:raise error(409,'资料状态已变化，本批未完成。')
                counts[domain]+=1;processed=1
        changed+=processed==2;referenced+=processed==3;missing+=processed==4
        db.execute('UPDATE privacy_domain_targets SET processed=? WHERE job_id=? AND domain=? AND resource_id=? AND processed=0',
            (processed,row['id'],domain,target['resource_id']))
    pending=db.execute('SELECT count(*) FROM privacy_domain_targets WHERE job_id=? AND processed=0',(row['id'],)).fetchone()[0]
    details={'mode':row['mode'],'asOf':row['as_of'],'jobVersion':row['version']+1,
        'localDatabase':{'status':'batch-completed' if pending else 'completed','counts':counts,'skippedChanged':changed,
            'skippedReferenced':referenced,'missing':missing,'pending':pending},
        'retained':retained_inventory(db,row['owner'],available),'providersStatus':'pending-confirmation',
        'backupsStatus':'pending-confirmation','vectorIndexStatus':'not-implemented','externalCacheStatus':'not-implemented',
        'localBrowserCleared':False,'allFirstPartyDataErased':False,'receiptContainsBody':False}
    objects=objects_summary(db,row['id']);status='ready' if pending else 'objects_pending' if objects['pending']+objects['retry'] else 'completed'
    db.execute('UPDATE privacy_domain_receipts SET status=?,details=?,updated=? WHERE id=?',('objects_pending' if status=='objects_pending' else 'local_completed',dump(details),stamp,rid))
    changed_job=db.execute('UPDATE privacy_domain_jobs SET version=version+1,status=?,updated=? WHERE id=? AND version=?',
        (status,stamp,row['id'],row['version'])).rowcount
    if changed_job!=1:raise error(409,'清理作业版本已变化，本批未完成。')
    return db.execute('SELECT * FROM privacy_domain_receipts WHERE id=?',(rid,)).fetchone()


def append_closure_cleanup(db,owner,closure_receipt_id,stamp):
    if 'privacy_domain_jobs' not in tables(db):return None
    if not db.in_transaction:raise ValueError('domain closure cleanup requires original transaction')
    if not db.execute('SELECT 1 FROM account_closure_receipts WHERE id=? AND owner=?',(closure_receipt_id,owner)).fetchone():raise ValueError('missing actual closure receipt')
    job=create_job(db,owner,'closure:'+closure_receipt_id,list(DOMAINS),'closure',stamp,closure_receipt_id=closure_receipt_id)
    class ClosureError(Exception):pass
    receipt=apply_batch(db,job,owner,'closure-first:'+closure_receipt_id,stamp,lambda status,message:ClosureError(message),internal_closure=True)
    return {'job':job_item(db,db.execute('SELECT * FROM privacy_domain_jobs WHERE id=?',(job['id'],)).fetchone()),'receipt':receipt_item(db,receipt)}


def closure_snapshot(db,owner,closure_receipt_id):
    if 'privacy_domain_jobs' not in tables(db):return None
    row=db.execute('SELECT * FROM privacy_domain_jobs WHERE owner=? AND closure_receipt_id=?',(owner,closure_receipt_id)).fetchone()
    if not row:return None
    latest=db.execute("SELECT * FROM privacy_domain_receipts WHERE job_id=? ORDER BY coalesce(json_extract(details,'$.jobVersion'),0) DESC,created DESC,id DESC LIMIT 1",(row['id'],)).fetchone()
    return {'job':job_item(db,row),'receipt':receipt_item(db,latest) if latest else None}


def export_metadata(db,owner):
    if 'privacy_domain_jobs' not in tables(db):return {}
    return {
        'privacyRetentionJobs':[dict(row) for row in db.execute('SELECT id,scopes,as_of,status,version,summary,created FROM privacy_retention_jobs WHERE owner=? ORDER BY created,id',(owner,))],
        'privacyRetentionReceipts':[dict(row) for row in db.execute('SELECT id,operation_id,status,details,created FROM privacy_retention_receipts WHERE owner=? ORDER BY created,id',(owner,))],
        'privacyDomainJobs':[job_item(db,row) for row in db.execute('SELECT * FROM privacy_domain_jobs WHERE owner=? ORDER BY created,id',(owner,))],
        'privacyDomainReceipts':[receipt_item(db,row) for row in db.execute('SELECT * FROM privacy_domain_receipts WHERE owner=? ORDER BY created,id',(owner,))],
        'privacyObjectDeletions':[object_metadata(row) for row in db.execute('SELECT * FROM privacy_object_deletions WHERE owner=? ORDER BY created,id',(owner,))]}


AUTH_JOB_SQL="""r.confirmed_by=r.owner AND r.confirmed_at>0 AND
 (r.mode!='closure' OR EXISTS(SELECT 1 FROM account_closure_receipts c
 JOIN account_lifecycle l ON l.owner=c.owner AND l.receipt_id=c.id AND l.status='closed'
 WHERE c.id=r.closure_receipt_id AND c.owner=r.owner))"""


class PrivacyDomains:
    def __init__(self,store,handler,error,rate,*,test_clock=None):
        self.store,self.h,self.Error,self.rate=store,handler,error,rate
        self.owner=handler.user['id'] if handler.user else ''
        self.clock=test_clock or now
    def fail(self,status,message):raise self.Error(status,message)
    def key(self,value):
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',value):self.fail(400,'需要8至100位有效的幂等请求号。')
        return value
    def domain_ids(self,value):
        if not isinstance(value,list) or not value or any(not isinstance(item,str) or item not in DOMAINS for item in value) or len(set(value))!=len(value):self.fail(400,'请明确选择支持的个人资料域。')
        return sorted(value)
    def ident(self,value):
        result=unquote(value)
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,150}',result):self.fail(400,'资源编号无效。')
        return result
    def own_job(self,db,ident,admin=False):
        row=db.execute('SELECT * FROM privacy_domain_jobs WHERE id=?',(ident,)).fetchone()
        if not row or not authorized_job(db,row,self.owner,admin):self.fail(404,'未找到本人已授权的清理作业。')
        return row
    def page(self,db,table,where,args,before='',limit=50):
        args=list(args)
        if before:
            cursor=db.execute('SELECT r.created,r.id FROM '+table+' r WHERE '+where+' AND r.id=?',(*args,before)).fetchone()
            if not cursor:self.fail(400,'分页位置不属于当前范围。')
            where+=' AND (r.created,r.id)<(?,?)';args.extend((cursor['created'],cursor['id']))
        rows=db.execute('SELECT r.* FROM '+table+' r WHERE '+where+' ORDER BY r.created DESC,r.id DESC LIMIT '+str(limit+1),args).fetchall()
        return rows[:limit],rows[limit-1]['id'] if len(rows)>limit else None
    def job_detail(self,db,row,query):
        receipts,next_receipt=self.page(db,'privacy_domain_receipts','r.job_id=?',[row['id']],query.get('receiptsBefore',[''])[0])
        objects,next_object=self.page(db,'privacy_object_deletions',
            'EXISTS(SELECT 1 FROM privacy_domain_receipts d WHERE d.id=r.receipt_id AND d.job_id=?)',[row['id']],query.get('objectsBefore',[''])[0])
        return {'job':job_item(db,row),'receipts':[receipt_item(db,item) for item in receipts],'receiptsNext':next_receipt,
            'objects':[object_metadata(item) for item in objects],'objectsNext':next_object}
    def preview(self,db,data):
        if set(data)!={'requestId','domains','mode'} or data.get('mode') not in ('manual','expiry'):self.fail(400,'预览只接受请求号、明确域和手动/到期模式。')
        key=self.key(data['requestId']);domains=self.domain_ids(data['domains']);mode=data['mode']
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT * FROM privacy_domain_jobs WHERE owner=? AND request_id=?',(self.owner,key)).fetchone()
        if old:
            if old['mode']!=mode or json.loads(old['domains'])!=domains:self.fail(409,'预览编号已用于其他范围。')
            return {'job':job_item(db,old)}
        if mode=='expiry':
            cfg=config(db);row=db.execute("SELECT data FROM settings WHERE key='privacy'").fetchone();version=json.loads(row['data']).get('policyVersion','') if row else ''
            if not cfg['enabled'] or not cfg['confirmed'] or not version or cfg['policyVersion']!=version:self.fail(409,'到期执行尚未获得当前政策的明确授权。')
        row=create_job(db,self.owner,key,domains,mode,self.clock())
        return {'job':job_item(db,row)}
    def adopt(self,db,data):
        if set(data)!={'requestId','domains','confirmed'} or data['confirmed'] is not True:self.fail(400,'纳管旧记录须明确确认，只建立服务端保护起点。')
        key=self.key(data['requestId']);domains=self.domain_ids(data['domains']);fp=digest({'action':'adopt','owner':self.owner,'domains':domains})
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT * FROM privacy_domain_receipts WHERE actor=? AND request_id=?',(self.owner,key)).fetchone()
        if old:
            if old['fingerprint']!=fp:self.fail(409,'请求号已用于其他操作。')
            return {'item':receipt_item(db,old),'replayed':True}
        stamp=self.clock();counts={};skipped={}
        for domain in domains:
            counts[domain]=skipped[domain]=0
            for row in source_rows(db,domain,self.owner):
                if tracker(db,self.owner,domain,row['resource_id']):skipped[domain]+=1;continue
                db.execute('INSERT INTO privacy_retention_tracking VALUES(?,?,?,?,?,1,?,?)',
                    (self.owner,domain,row['resource_id'],'',stamp,uuid4().hex,'protection-start'))
                counts[domain]+=1
        rid=str(uuid4());details={'domains':domains,'adoptedCounts':counts,'alreadyKnownSkipped':skipped,
            'protectionStart':stamp,'historicalLastWriteKnown':False,'deleted':0}
        db.execute('INSERT INTO privacy_domain_receipts VALUES(?,?,NULL,?,?,?,?,?,?,?)',
            (rid,self.owner,self.owner,key,fp,'local_completed',dump(details),stamp,stamp))
        return {'item':receipt_item(db,db.execute('SELECT * FROM privacy_domain_receipts WHERE id=?',(rid,)).fetchone()),'replayed':False}
    def apply(self,db,ident,data,admin=False):
        expected={'requestId','version'} if admin else {'requestId','version','confirmed'}
        if set(data)!=expected or (not admin and data.get('confirmed') is not True) or type(data.get('version')) is not int:self.fail(400,'执行须明确确认当前预览与版本。')
        key=self.key(data['requestId'])
        db.execute('BEGIN IMMEDIATE');row=self.own_job(db,ident,admin)
        fp=digest({'jobId':ident,'owner':row['owner'],'version':data['version'],'action':'apply'})
        old=db.execute('SELECT * FROM privacy_domain_receipts WHERE actor=? AND request_id=?',(self.owner,key)).fetchone()
        if old:
            if old['fingerprint']!=fp:self.fail(409,'请求编号已用于不同批次。')
            return {'job':job_item(db,row),'receipt':receipt_item(db,old),'replayed':True}
        if row['version']!=data['version']:self.fail(409,'作业版本已变化，请刷新。')
        # Only expiry depends on the frozen retention policy/config/preference revision.
        # Manual cleanup retains the owner confirmation, frozen targets and live nonce guards.
        receipt=apply_batch(db,row,self.owner,key,self.clock(),self.Error,admin=admin)
        return {'job':job_item(db,db.execute('SELECT * FROM privacy_domain_jobs WHERE id=?',(ident,)).fetchone()),'receipt':receipt_item(db,receipt),'replayed':False}
    def records(self,db,domain,query):
        if domain not in DOMAINS:self.fail(400,'该域保留原入口或尚未授权清理。')
        table,owner,key=SOURCES[domain];where='r.'+owner+'=?';args=[self.owner]
        before=query.get('before',[''])[0]
        if before:
            if not db.execute('SELECT 1 FROM '+table+' WHERE '+owner+'=? AND '+key+'=?',(self.owner,before)).fetchone():self.fail(400,'分页位置不属于当前本人范围。')
            where+=' AND r.'+key+'<?';args.append(before)
        rows=db.execute('SELECT r.* FROM '+table+' r WHERE '+where+' ORDER BY r.'+key+' DESC LIMIT 51',args).fetchall();available=available_schema(db)
        items=[]
        for row in rows[:50]:
            why=reason_for(db,domain,row,available)
            items.append({'id':row[key],'status':row['status'] if 'status' in row.keys() else 'uploaded',
                'created':row['created'],'updated':row['updated'] if 'updated' in row.keys() else row['created'],
                'eligibility':not why,'reason':why,'blockedReasons':[why] if why else []})
        return {'items':items,'next':rows[49][key] if len(rows)>50 else None,'accountId':self.owner}
    def own_object_job(self,db,row,admin):
        receipt=db.execute('SELECT * FROM privacy_domain_receipts WHERE id=?',(row['receipt_id'],)).fetchone()
        job=db.execute('SELECT * FROM privacy_domain_jobs WHERE id=?',(receipt['job_id'],)).fetchone() if receipt and receipt['job_id'] else None
        return bool(job and row['owner']==job['owner'] and authorized_job(db,job,self.owner,admin))
    def process_objects(self,data,admin=False,*,claim_guard=None):
        limit=data.get('limit')
        if set(data)!={'limit'} or type(limit) is not int or not 1<=limit<=10:self.fail(400,'每次须处理1至10个已确认对象任务。')
        items=[]
        # The Python runtime stores media inside SQLite. It never pretends to operate a Cloud bucket.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');stamp=self.clock()
            rows=db.execute("SELECT * FROM privacy_object_deletions WHERE (status IN ('pending','retry') AND next_attempt<=?) OR (status='processing' AND lease_until<=?) ORDER BY created,id",(stamp,stamp)).fetchall()
            for row in rows:
                if len(items)>=limit:break
                if not self.own_object_job(db,row,admin):continue
                if claim_guard is not None:claim_guard(db)
                attempts=row['attempts']+1
                status='manual_review' if attempts>=5 else 'retry';code='retry_exhausted' if attempts>=5 else 'storage_delete_failed'
                db.execute("UPDATE privacy_object_deletions SET attempts=?,status=?,lease_token='',lease_until=0,next_attempt=?,last_error=?,updated=? WHERE id=? AND attempts=?",
                    (attempts,status,stamp+1000*2**(attempts-1) if status=='retry' else 0,code,stamp,row['id'],row['attempts']))
                items.append(object_metadata(db.execute('SELECT * FROM privacy_object_deletions WHERE id=?',(row['id'],)).fetchone()))
        return {'items':items,'processed':len(items)}
    def export(self):
        from privacy import Privacy
        result=Privacy(self.store,self.h,self.Error,self.rate).export()
        with self.store.connect() as db:
            files=[{'id':row['id'],'mime':row['mime'],'filename':row['filename'],'url':'/api/media/'+row['id']}
                for row in db.execute('SELECT id,mime,filename FROM media WHERE owner=? ORDER BY created,id',(self.owner,))
                if not db.execute('SELECT 1 FROM digital_sandbox_assets WHERE media_id=?',(row['id'],)).fetchone() and not media_deleted(db,row['id'])]
            return {'accountId':self.owner,'asOf':self.clock(),'inventory':inventory(db,self.owner,self.clock()),
                'serverData':result['serverData'],'files':files,'binaryIncluded':False,'credentialsIncluded':False}
    def route(self,method,path):
        public,admin='/api/privacy/domains','/api/admin/privacy/domains'
        if path not in (public,admin) and not path.startswith(public+'/') and not path.startswith(admin+'/'):return None
        is_admin=path==admin or path.startswith(admin+'/')
        self.owner=self.h.require(['admin'] if is_admin else None)['id']
        self.rate('privacy-domains:'+('read:' if method=='GET' else 'write:')+self.owner,180 if method=='GET' else 60)
        query=parse_qs(urlsplit(self.h.path).query)
        if path in (public+'/objects/process',admin+'/objects/process') and method=='POST':return self.process_objects(self.h.body(),is_admin)
        if path==public+'/export' and method=='GET':
            self.rate('privacy-domain-export:'+self.owner,3)
            return self.export()
        with self.store.connect() as db:
            if path==public and method=='GET':return inventory(db,self.owner,self.clock())
            if path==admin+'/config' and method in ('GET','PATCH'):
                if method=='PATCH':
                    data=self.h.body()
                    if set(data)!=set(DEFAULT) or type(data.get('revision')) is not int or type(data.get('enabled')) is not bool or type(data.get('confirmed')) is not bool or not isinstance(data.get('policyVersion'),str) or len(data['policyVersion'])>80 or not isinstance(data.get('retentionDays'),dict) or set(data['retentionDays'])!=set(DOMAINS) or any(v is not None and (type(v) is not int or not 0<=v<=36500) for v in data['retentionDays'].values()):self.fail(400,'逐域执行配置或独立天数无效。')
                    db.execute('BEGIN IMMEDIATE');old=config(db)
                    if data['revision']!=old['revision']:self.fail(409,'配置已更新，请刷新。')
                    global_row=db.execute("SELECT data FROM settings WHERE key='privacy'").fetchone();version=json.loads(global_row['data']).get('policyVersion','') if global_row else ''
                    if data['enabled'] and (not data['confirmed'] or not version or data['policyVersion']!=version):self.fail(409,'启用到期执行须确认当前全局政策。')
                    db.execute('UPDATE privacy_domain_config SET data=? WHERE id=1',(dump({**data,'revision':old['revision']+1}),))
                return {'config':config(db),'schedulerDeployed':False}
            if path==public+'/preview' and method=='POST':return self.preview(db,self.h.body())
            if path==public+'/adopt' and method=='POST':return self.adopt(db,self.h.body())
            if path in (public+'/jobs',admin+'/jobs') and method=='GET':
                rows,next_id=self.page(db,'privacy_domain_jobs',AUTH_JOB_SQL if is_admin else 'r.owner=?',[] if is_admin else [self.owner],query.get('before',[''])[0])
                return {'items':[job_item(db,row) for row in rows],'next':next_id}
            if path==public+'/receipts' and method=='GET':
                rows,next_id=self.page(db,'privacy_domain_receipts','r.owner=?',[self.owner],query.get('before',[''])[0])
                return {'items':[receipt_item(db,row) for row in rows],'next':next_id}
            prefix=admin if is_admin else public
            match=re.fullmatch(re.escape(prefix)+r'/jobs/([^/]+)(/apply)?',path)
            if match:
                ident=self.ident(match[1])
                if method=='GET' and not match[2]:return self.job_detail(db,self.own_job(db,ident,is_admin),query)
                if method=='POST' and match[2]:return self.apply(db,ident,self.h.body(),is_admin)
            match=re.fullmatch(re.escape(public)+r'/([^/]+)/records',path)
            if match and method=='GET':return self.records(db,self.ident(match[1]),query)
            match=re.fullmatch(re.escape(admin)+r'/objects/([^/]+)/retry',path)
            if match and method=='POST':
                if self.h.body():self.fail(400,'重试不接受其他字段。')
                db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM privacy_object_deletions WHERE id=?',(self.ident(match[1]),)).fetchone()
                if not row or not self.own_object_job(db,row,True):self.fail(404,'未找到已授权对象任务。')
                if row['status'] not in ('retry','manual_review') or row['attempts']>=5:self.fail(409,'任务不可重排或已达到有限次数。')
                db.execute("UPDATE privacy_object_deletions SET status='retry',next_attempt=0,lease_token='',lease_until=0,updated=? WHERE id=?",(self.clock(),row['id']))
                return {'item':object_metadata(db.execute('SELECT * FROM privacy_object_deletions WHERE id=?',(row['id'],)).fetchone())}
        self.fail(405,'不支持的逐域隐私操作。')
