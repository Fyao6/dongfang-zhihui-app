"""Finite sandbox digital-use leases. A lease is an authenticated resource, not a bearer grant."""
import copy
import hashlib
import json
import re
import time
from urllib.parse import parse_qs, urlsplit, unquote
from uuid import uuid4

DEFAULT = {'revision':0,'enabled':False,'confirmed':False,'ruleVersion':'','environment':'sandbox',
    'validityDays':None,'usesPerUnit':None,'leaseSeconds':300,'consumption':'lease_acquisition',
    'anchor':'verified_payment_utc','refundPolicy':'cap_unconsumed','productionEnabled':False}
FIXED = {key:value for key,value in DEFAULT.items() if key not in ('revision','enabled','confirmed','ruleVersion','validityDays','usesPerUnit','leaseSeconds')}
DDL = """
CREATE TABLE IF NOT EXISTS digital_sandbox_assets(
 media_id TEXT PRIMARY KEY,content_id TEXT NOT NULL UNIQUE,owner TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','disabled')),created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS digital_order_snapshots(
 item_id TEXT PRIMARY KEY,owner TEXT NOT NULL,order_id TEXT NOT NULL,content_id TEXT NOT NULL,
 media_id TEXT NOT NULL,policy_snapshot TEXT NOT NULL,created INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS digital_entitlement_grants(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,order_id TEXT NOT NULL,item_id TEXT NOT NULL UNIQUE,
 content_id TEXT NOT NULL,media_id TEXT NOT NULL,policy_snapshot TEXT NOT NULL,
 uses_per_unit INTEGER NOT NULL CHECK(uses_per_unit>0),original_quantity INTEGER NOT NULL CHECK(original_quantity>0),
 used INTEGER NOT NULL DEFAULT 0 CHECK(used>=0),overused INTEGER NOT NULL DEFAULT 0 CHECK(overused>=0),
 starts INTEGER NOT NULL,expires INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS digital_grant_owner ON digital_entitlement_grants(owner,created,id);
CREATE TABLE IF NOT EXISTS digital_access_leases(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,grant_id TEXT NOT NULL,request_id TEXT NOT NULL,
 session_hash TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,UNIQUE(owner,request_id));
CREATE TABLE IF NOT EXISTS digital_entitlement_uses(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,grant_id TEXT NOT NULL,lease_id TEXT NOT NULL UNIQUE,
 action TEXT NOT NULL CHECK(action='lease_acquired'),created INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS digital_use_owner ON digital_entitlement_uses(owner,created,id);
CREATE TRIGGER IF NOT EXISTS digital_asset_identity BEFORE UPDATE OF media_id,content_id,owner,created ON digital_sandbox_assets
 BEGIN SELECT RAISE(ABORT,'digital_asset_immutable'); END;
CREATE TRIGGER IF NOT EXISTS digital_asset_no_reenable BEFORE UPDATE OF status ON digital_sandbox_assets
 WHEN OLD.status='disabled' AND NEW.status!='disabled' BEGIN SELECT RAISE(ABORT,'digital_asset_permanent_disable'); END;
CREATE TRIGGER IF NOT EXISTS digital_asset_no_delete BEFORE DELETE ON digital_sandbox_assets
 BEGIN SELECT RAISE(ABORT,'digital_asset_permanent_marker'); END;
CREATE TRIGGER IF NOT EXISTS digital_snapshot_identity BEFORE UPDATE ON digital_order_snapshots
 BEGIN SELECT RAISE(ABORT,'digital_snapshot_immutable'); END;
CREATE TRIGGER IF NOT EXISTS digital_snapshot_no_delete BEFORE DELETE ON digital_order_snapshots
 BEGIN SELECT RAISE(ABORT,'digital_snapshot_immutable'); END;
CREATE TRIGGER IF NOT EXISTS digital_grant_identity BEFORE UPDATE OF id,owner,order_id,item_id,content_id,media_id,
 policy_snapshot,uses_per_unit,original_quantity,starts,expires,created ON digital_entitlement_grants
 BEGIN SELECT RAISE(ABORT,'digital_grant_immutable'); END;
CREATE TRIGGER IF NOT EXISTS digital_grant_no_delete BEFORE DELETE ON digital_entitlement_grants
 BEGIN SELECT RAISE(ABORT,'digital_grant_immutable'); END;
CREATE TRIGGER IF NOT EXISTS digital_lease_identity BEFORE UPDATE ON digital_access_leases
 BEGIN SELECT RAISE(ABORT,'digital_lease_immutable'); END;
CREATE TRIGGER IF NOT EXISTS digital_lease_no_delete BEFORE DELETE ON digital_access_leases
 BEGIN SELECT RAISE(ABORT,'digital_lease_immutable'); END;
CREATE TRIGGER IF NOT EXISTS digital_use_identity BEFORE UPDATE ON digital_entitlement_uses
 BEGIN SELECT RAISE(ABORT,'digital_use_immutable'); END;
CREATE TRIGGER IF NOT EXISTS digital_use_no_delete BEFORE DELETE ON digital_entitlement_uses
 BEGIN SELECT RAISE(ABORT,'digital_use_immutable'); END;
"""
POLICY_GATE = """EXISTS(SELECT 1 FROM settings WHERE key='digital_entitlements'
 AND json_type(data,'$.enabled')='true' AND json_type(data,'$.confirmed')='true'
 AND json_extract(data,'$.environment')='sandbox' AND json_extract(data,'$.productionEnabled')=0
 AND json_type(data,'$.ruleVersion')='text' AND length(trim(json_extract(data,'$.ruleVersion')))>0
 AND json_type(data,'$.validityDays')='integer' AND json_extract(data,'$.validityDays') BETWEEN 1 AND 3650
 AND json_type(data,'$.usesPerUnit')='integer' AND json_extract(data,'$.usesPerUnit') BETWEEN 1 AND 1000
 AND json_type(data,'$.leaseSeconds')='integer' AND json_extract(data,'$.leaseSeconds') BETWEEN 30 AND 14400
 AND json_extract(data,'$.consumption')='lease_acquisition' AND json_extract(data,'$.anchor')='verified_payment_utc'
 AND json_extract(data,'$.refundPolicy')='cap_unconsumed')"""
BASE_JOIN = """FROM digital_entitlement_grants g
 JOIN commerce_order_items i ON i.id=g.item_id AND i.order_id=g.order_id
 JOIN commerce_orders o ON o.id=g.order_id AND o.owner=g.owner
 JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=g.owner AND e.environment='sandbox'
 JOIN commerce_payment_events pay ON pay.order_id=o.id AND pay.owner=g.owner AND pay.kind='sandbox_pay' AND pay.status='applied' AND pay.environment='sandbox'
 JOIN digital_sandbox_assets a ON a.media_id=g.media_id AND a.content_id=g.content_id
 JOIN contents c ON c.kind='courses' AND c.id=g.content_id
 JOIN commerce_products p ON p.id=i.product_id"""
BASE_GUARD = """o.environment='sandbox' AND o.payment_status IN ('paid','partially_refunded')
 AND i.type='digital' AND i.content_id=g.content_id AND i.quantity=g.original_quantity AND i.refunded_quantity<i.quantity
 AND p.type='digital' AND p.environment='sandbox' AND p.content_id=g.content_id
 AND e.type='digital' AND e.content_id=g.content_id AND e.status='active' AND e.remaining>0
 AND a.status='active' AND c.status='published' AND json_type(c.data,'$.sandboxOnly')='true'
 AND coalesce(json_extract(c.data,'$.mediaUrl'),'')='' AND coalesce(json_extract(c.data,'$.audioUrl'),'')=''
 AND coalesce(json_extract(c.data,'$.creatorId'),'')=''
 AND EXISTS(SELECT 1 FROM users u WHERE u.id=g.owner AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))
 AND EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1)
 AND """+POLICY_GATE


def trigger_sql():
    return """
DROP TRIGGER IF EXISTS digital_snapshot_check;
CREATE TRIGGER digital_snapshot_check BEFORE INSERT ON digital_order_snapshots BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_items i
 JOIN commerce_orders o ON o.id=i.order_id AND o.owner=NEW.owner
 JOIN commerce_products p ON p.id=i.product_id AND p.type='digital' AND p.environment='sandbox' AND p.content_id=i.content_id
 JOIN digital_sandbox_assets a ON a.content_id=i.content_id AND a.media_id=NEW.media_id AND a.status='active'
 JOIN contents c ON c.kind='courses' AND c.id=i.content_id AND c.status='published'
 WHERE i.id=NEW.item_id AND i.order_id=NEW.order_id AND i.type='digital' AND i.content_id=NEW.content_id
 AND i.refunded_quantity=0 AND o.environment='sandbox' AND o.payment_status='unpaid' AND o.status='awaiting_payment'
 AND json_type(c.data,'$.sandboxOnly')='true' AND coalesce(json_extract(c.data,'$.mediaUrl'),'')=''
 AND coalesce(json_extract(c.data,'$.audioUrl'),'')='' AND coalesce(json_extract(c.data,'$.creatorId'),'')=''
 AND EXISTS(SELECT 1 FROM settings WHERE key='digital_entitlements' AND data=NEW.policy_snapshot)
 AND """+POLICY_GATE+""") THEN RAISE(ABORT,'digital_checkout_changed') END;
END;
DROP TRIGGER IF EXISTS digital_grant_check;
CREATE TRIGGER digital_grant_check BEFORE INSERT ON digital_entitlement_grants BEGIN
 SELECT CASE WHEN NEW.id!='digital:'||NEW.item_id OR NEW.used!=0 OR NEW.overused!=0 OR NOT EXISTS(
 SELECT 1 FROM digital_order_snapshots s
 JOIN commerce_order_items i ON i.id=s.item_id AND i.order_id=s.order_id AND i.type='digital'
 JOIN commerce_orders o ON o.id=s.order_id AND o.owner=s.owner AND o.environment='sandbox'
 JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=s.owner AND e.environment='sandbox'
 JOIN commerce_payment_events pay ON pay.order_id=o.id AND pay.owner=o.owner AND pay.kind='sandbox_pay' AND pay.status='applied' AND pay.environment='sandbox'
 WHERE s.item_id=NEW.item_id AND s.owner=NEW.owner AND s.order_id=NEW.order_id AND s.content_id=NEW.content_id
 AND s.media_id=NEW.media_id AND s.policy_snapshot=NEW.policy_snapshot AND i.content_id=s.content_id
 AND o.payment_status IN ('paid','partially_refunded') AND i.refunded_quantity=0 AND e.status='active'
 AND NEW.original_quantity=i.quantity AND NEW.uses_per_unit=json_extract(s.policy_snapshot,'$.usesPerUnit')
 AND NEW.starts=pay.created AND NEW.expires=pay.created+json_extract(s.policy_snapshot,'$.validityDays')*86400000
 AND NEW.expires>NEW.starts) THEN RAISE(ABORT,'digital_grant_changed') END;
END;
DROP TRIGGER IF EXISTS digital_entitlement_grant;
CREATE TRIGGER digital_entitlement_grant AFTER INSERT ON commerce_entitlements
WHEN NEW.type='digital' AND EXISTS(SELECT 1 FROM digital_order_snapshots WHERE item_id=NEW.item_id) BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_payment_events p JOIN commerce_orders o ON o.id=p.order_id
 WHERE p.order_id=NEW.order_id AND p.owner=NEW.owner AND p.kind='sandbox_pay' AND p.status='applied'
 AND p.environment='sandbox' AND o.payment_status IN ('paid','partially_refunded')) THEN RAISE(ABORT,'digital_payment_missing') END;
 INSERT INTO digital_entitlement_grants
 SELECT 'digital:'||NEW.item_id,NEW.owner,NEW.order_id,NEW.item_id,s.content_id,s.media_id,s.policy_snapshot,
 json_extract(s.policy_snapshot,'$.usesPerUnit'),NEW.quantity,0,0,p.created,
 p.created+json_extract(s.policy_snapshot,'$.validityDays')*86400000,NEW.created,NEW.created
 FROM digital_order_snapshots s JOIN commerce_payment_events p ON p.order_id=s.order_id AND p.owner=s.owner
 AND p.kind='sandbox_pay' AND p.status='applied' AND p.environment='sandbox' WHERE s.item_id=NEW.item_id;
END;
DROP TRIGGER IF EXISTS digital_refund_cap;
CREATE TRIGGER digital_refund_cap AFTER UPDATE OF refunded_quantity ON commerce_order_items
WHEN NEW.refunded_quantity>OLD.refunded_quantity BEGIN
 UPDATE digital_entitlement_grants SET overused=max(0,used-(NEW.quantity-NEW.refunded_quantity)*uses_per_unit),
 updated=coalesce((SELECT max(created) FROM commerce_payment_events WHERE order_id=NEW.order_id),updated)
 WHERE item_id=NEW.id;
END;
DROP TRIGGER IF EXISTS digital_use_check;
CREATE TRIGGER digital_use_check BEFORE INSERT ON digital_access_leases BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 """+BASE_JOIN+"""
 JOIN sessions ses ON ses.user_id=g.owner AND ses.token=NEW.session_hash
 WHERE g.id=NEW.grant_id AND g.owner=NEW.owner AND """+BASE_GUARD+"""
 AND ses.expires>CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)
 AND g.starts<=NEW.created AND g.expires>NEW.created
 AND g.used<(i.quantity-i.refunded_quantity)*g.uses_per_unit
 AND NEW.expires=min(NEW.created+json_extract(g.policy_snapshot,'$.leaseSeconds')*1000,g.expires)
 AND NEW.expires>NEW.created) THEN RAISE(ABORT,'digital_access_changed') END;
END;
DROP TRIGGER IF EXISTS digital_use_apply;
CREATE TRIGGER digital_use_apply AFTER INSERT ON digital_access_leases BEGIN
 UPDATE digital_entitlement_grants SET used=used+1,updated=NEW.created WHERE id=NEW.grant_id AND owner=NEW.owner;
 INSERT INTO digital_entitlement_uses VALUES('use:'||NEW.id,NEW.owner,NEW.grant_id,NEW.id,'lease_acquired',NEW.created);
END;
"""


REFERENCE_FIELDS = [('contents','data'),('settings','data'),('posts','media_url'),('creator_works','data'),
    ('creator_profiles','data'),('commerce_products','data'),('card_deck_versions','data'),('card_draws','snapshot'),
    ('revisions','snapshot'),('commerce_order_items','snapshot_data')]


def reference_sql(db):
    fields = [(table,column) for table,column in REFERENCE_FIELDS
              if column in {row[1] for row in db.execute('PRAGMA table_info('+table+')')}]
    references = ' OR '.join("EXISTS(SELECT 1 FROM "+table+" WHERE instr(coalesce("+column+",''),'/api/media/'||NEW.media_id)>0)" for table,column in fields) or '0'
    statements = ["""DROP TRIGGER IF EXISTS digital_asset_check;""",
    """CREATE TRIGGER digital_asset_check BEFORE INSERT ON digital_sandbox_assets BEGIN
 SELECT CASE WHEN NEW.status!='active' OR NOT EXISTS(SELECT 1 FROM media m JOIN users u ON u.id=m.owner
 WHERE m.id=NEW.media_id AND m.owner=NEW.owner AND u.role='admin' AND (m.mime LIKE 'audio/%' OR m.mime LIKE 'video/%')
 AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))
 OR NOT EXISTS(SELECT 1 FROM contents c WHERE c.kind='courses' AND c.id=NEW.content_id AND c.status='published'
 AND json_type(c.data,'$.sandboxOnly')='true' AND coalesce(json_extract(c.data,'$.mediaUrl'),'')=''
 AND coalesce(json_extract(c.data,'$.audioUrl'),'')='' AND coalesce(json_extract(c.data,'$.creatorId'),'')='')
 OR """+references+""" THEN RAISE(ABORT,'digital_asset_not_isolated') END;
 END;"""]
    for table,column in fields:
        for operation in ('INSERT','UPDATE'):
            name = 'digital_private_'+table+'_'+operation.lower()
            statements.extend(['DROP TRIGGER IF EXISTS '+name+';',
                'CREATE TRIGGER '+name+' BEFORE '+operation+(' OF '+column if operation=='UPDATE' else '')+' ON '+table+" BEGIN SELECT CASE WHEN EXISTS(SELECT 1 FROM digital_sandbox_assets WHERE instr(coalesce(NEW."+column+",''),'/api/media/'||media_id)>0) THEN RAISE(ABORT,'digital_private_asset_reference') END; END;"])
    statements.extend(["DROP TRIGGER IF EXISTS digital_sandbox_course_guard;",
        """CREATE TRIGGER digital_sandbox_course_guard BEFORE UPDATE OF data,kind,id ON contents
 WHEN OLD.kind='courses' AND EXISTS(SELECT 1 FROM digital_sandbox_assets WHERE content_id=OLD.id) BEGIN
 SELECT CASE WHEN NEW.kind!='courses' OR NEW.id!=OLD.id OR coalesce(json_type(NEW.data,'$.sandboxOnly'),'')!='true'
 OR coalesce(json_extract(NEW.data,'$.mediaUrl'),'')!='' OR coalesce(json_extract(NEW.data,'$.audioUrl'),'')!=''
 OR coalesce(json_extract(NEW.data,'$.creatorId'),'')!='' THEN RAISE(ABORT,'digital_sandbox_course_immutable') END; END;"""])
    for operation in ('INSERT','UPDATE'):
        name='digital_course_boolean_'+operation.lower()
        statements.extend(['DROP TRIGGER IF EXISTS '+name+';',
            'CREATE TRIGGER '+name+' BEFORE '+operation+(' OF data,kind' if operation=='UPDATE' else '')+" ON contents WHEN NEW.kind='courses' BEGIN SELECT CASE WHEN json_type(NEW.data,'$.sandboxOnly') IS NOT NULL AND json_type(NEW.data,'$.sandboxOnly') NOT IN ('true','false') THEN RAISE(ABORT,'digital_sandbox_bool_required') END; END;"])
    statements.extend(['DROP TRIGGER IF EXISTS digital_sandbox_course_insert;',
        """CREATE TRIGGER digital_sandbox_course_insert BEFORE INSERT ON contents
 WHEN NEW.kind='courses' AND EXISTS(SELECT 1 FROM digital_sandbox_assets WHERE content_id=NEW.id) BEGIN
 SELECT CASE WHEN coalesce(json_type(NEW.data,'$.sandboxOnly'),'')!='true'
 OR coalesce(json_extract(NEW.data,'$.mediaUrl'),'')!='' OR coalesce(json_extract(NEW.data,'$.audioUrl'),'')!=''
 OR coalesce(json_extract(NEW.data,'$.creatorId'),'')!='' THEN RAISE(ABORT,'digital_sandbox_course_immutable') END; END;"""])
    return '\n'.join(statements)


def init_schema(db):
    db.executescript(DDL)
    db.executescript(trigger_sql())
    db.executescript(reference_sql(db))


def now():
    return time.time_ns()//1_000_000


def dump(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def policy(db):
    row = db.execute("SELECT data FROM settings WHERE key='digital_entitlements'").fetchone()
    return {**copy.deepcopy(DEFAULT),**(json.loads(row['data']) if row else {})}


def ready(value):
    return (value.get('enabled') is True and value.get('confirmed') is True
        and isinstance(value.get('ruleVersion'),str) and bool(value['ruleVersion'].strip())
        and type(value.get('validityDays')) is int and 1<=value['validityDays']<=3650
        and type(value.get('usesPerUnit')) is int and 1<=value['usesPerUnit']<=1000
        and type(value.get('leaseSeconds')) is int and 30<=value['leaseSeconds']<=14400
        and all(value.get(key)==expected for key,expected in FIXED.items()))


def capture_order(db,owner,order_id,stamp,error):
    """Checkout-only, in the same new-unpaid-order transaction. Never backfill old orders."""
    config = policy(db)
    for item in db.execute("SELECT * FROM commerce_order_items WHERE order_id=? AND type='digital'",(order_id,)).fetchall():
        marked=db.execute("SELECT 1 FROM contents WHERE kind='courses' AND id=? AND json_type(data,'$.sandboxOnly')='true' UNION ALL SELECT 1 FROM digital_sandbox_assets WHERE content_id=?",(item['content_id'],item['content_id'])).fetchone()
        if not marked:
            continue
        if not ready(config):
            raise error(503,'隔离数字商品的有限沙箱政策尚未启用。')
        asset = db.execute("SELECT a.* FROM digital_sandbox_assets a JOIN contents c ON c.id=a.content_id AND c.kind='courses' WHERE a.content_id=? AND a.status='active' AND c.status='published' AND json_type(c.data,'$.sandboxOnly')='true'",(item['content_id'],)).fetchone()
        if not asset:
            raise error(409,'隔离数字商品尚无有效测试素材绑定。')
        db.execute('INSERT INTO digital_order_snapshots VALUES(?,?,?,?,?,?,?)',(item['id'],owner,order_id,item['content_id'],asset['media_id'],dump(config),stamp))


def is_private_media(db,media_id):
    return bool(db.execute('SELECT 1 FROM digital_sandbox_assets WHERE media_id=?',(media_id,)).fetchone())


def safe_course(value):
    return value.get('sandboxOnly') is not True


def order_item_data(db,item):
    value=json.loads(item['snapshot_data'])
    snapshot=db.execute('SELECT * FROM digital_order_snapshots WHERE item_id=?',(item['id'],)).fetchone()
    value['digitalTerms']={**json.loads(snapshot['policy_snapshot']),'contentId':snapshot['content_id'],'mediaId':snapshot['media_id'],'sandboxOnly':True} if snapshot else None
    return value


def catalog_ready(db,product):
    """None preserves legacy catalog semantics; marked products keep all stock data."""
    if product['type']!='digital' or product['environment']!='sandbox':
        return None
    asset=db.execute('SELECT * FROM digital_sandbox_assets WHERE content_id=?',(product['contentId'],)).fetchone()
    course=db.execute("SELECT * FROM contents WHERE kind='courses' AND id=?",(product['contentId'],)).fetchone()
    data=json.loads(course['data']) if course else {}
    if not asset and data.get('sandboxOnly') is not True:
        return None
    if not ready(policy(db)) or not asset or asset['status']!='active' or not course or course['status']!='published' or data.get('sandboxOnly') is not True or any(data.get(key) for key in ('mediaUrl','audioUrl','creatorId')):
        return False
    if not db.execute("SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1").fetchone():
        return False
    return bool(db.execute("SELECT 1 FROM media WHERE id=? AND owner=? AND (mime LIKE 'audio/%' OR mime LIKE 'video/%')",(asset['media_id'],asset['owner'])).fetchone())


class DigitalMediaReply:
    def __init__(self,status,data,mime,headers):
        self.status,self.data,self.mime,self.headers=status,data,mime,headers
    def send(self,handler):
        return handler.send(self.status,self.data,self.mime,self.headers)


class DigitalEntitlements:
    def __init__(self,store,handler,error,rate,*,test_clock=None):
        self.store,self.h,self.Error,self.rate=store,handler,error,rate
        self.clock=test_clock or now
        self.owner=handler.user['id'] if handler.user else ''
    def fail(self,status,message):
        raise self.Error(status,message)
    def session(self):
        return hashlib.sha256(self.h.session_token.encode('utf-8')).hexdigest()
    def row(self,db,ident,admin=False):
        row=db.execute('SELECT * FROM digital_entitlement_grants WHERE id=?'+('' if admin else ' AND owner=?'),(ident,) if admin else (ident,self.owner)).fetchone()
        if not row:self.fail(404,'未找到本人的数字购买权益。')
        return row
    def eligibility(self,db,row,stamp):
        return bool(db.execute('SELECT 1 '+BASE_JOIN+' WHERE g.id=? AND '+BASE_GUARD+' AND g.starts<=? AND g.expires>?',(row['id'],stamp,stamp)).fetchone())
    def item(self,db,row):
        stamp=self.clock();line=db.execute('SELECT * FROM commerce_order_items WHERE id=?',(row['item_id'],)).fetchone()
        content=db.execute("SELECT data FROM contents WHERE kind='courses' AND id=?",(row['content_id'],)).fetchone()
        media=db.execute('SELECT mime FROM media WHERE id=?',(row['media_id'],)).fetchone()
        terms=json.loads(row['policy_snapshot']);cap=max(0,(line['quantity']-line['refunded_quantity'])*row['uses_per_unit']) if line else 0
        live=self.eligibility(db,row,stamp)
        state='active' if live else 'expired' if stamp>=row['expires'] else 'disabled' if not ready(policy(db)) else 'revoked'
        if state=='active' and row['used']>=cap:state='exhausted'
        return {'id':row['id'],'orderId':row['order_id'],'itemId':row['item_id'],'contentId':row['content_id'],
            'title':(json.loads(content['data']).get('zh') or json.loads(content['data']).get('title') or line['title']) if content and line else row['content_id'],
            'mime':media['mime'] if media else '', 'quantity':row['original_quantity'],'refundedQuantity':line['refunded_quantity'] if line else row['original_quantity'],
            'usesPerUnit':row['uses_per_unit'],'totalUses':cap,'used':row['used'],'available':max(0,cap-row['used']) if live else 0,
            'overused':max(row['overused'],row['used']-cap),'starts':row['starts'],'expires':row['expires'],'status':state,
            'canAccess':live and row['used']<cap,'ruleVersion':terms['ruleVersion'],'environment':'sandbox','productionEnabled':False}
    def asset(self,db,row):
        content=db.execute("SELECT data FROM contents WHERE kind='courses' AND id=?",(row['content_id'],)).fetchone()
        media=db.execute('SELECT mime,filename FROM media WHERE id=?',(row['media_id'],)).fetchone()
        return {'mediaId':row['media_id'],'contentId':row['content_id'],'title':json.loads(content['data']).get('zh',row['content_id']) if content else row['content_id'],
            'mime':media['mime'] if media else '', 'filename':media['filename'] if media else '', 'status':row['status'],'created':row['created'],'updated':row['updated']}
    def admin_view(self,db):
        return {'policy':policy(db),'assets':[self.asset(db,row) for row in db.execute('SELECT * FROM digital_sandbox_assets ORDER BY created DESC,media_id')],
            'contents':[{'id':row['id'],'title':json.loads(row['data']).get('zh',row['id'])} for row in db.execute("SELECT id,data FROM contents WHERE kind='courses' AND status='published' AND json_type(data,'$.sandboxOnly')='true' AND coalesce(json_extract(data,'$.mediaUrl'),'')='' AND coalesce(json_extract(data,'$.audioUrl'),'')='' AND coalesce(json_extract(data,'$.creatorId'),'')='' ORDER BY id")],
            'productionEnabled':False}
    def public_settings(self,db):
        value=policy(db)
        return {key:value[key] for key in ('enabled','confirmed','ruleVersion','environment','consumption','productionEnabled')}
    def listing(self,db,admin,query):
        before=query.get('before',[''])[0];where,args=('1',[]) if admin else ('owner=?',[self.owner])
        if before:
            cursor=self.row(db,before,admin)
            where+=' AND (created,id)<(?,?)';args.extend((cursor['created'],cursor['id']))
        rows=db.execute('SELECT * FROM digital_entitlement_grants WHERE '+where+' ORDER BY created DESC,id DESC LIMIT 51',args).fetchall()
        return {'items':[self.item(db,row) for row in rows[:50]],'next':rows[49]['id'] if len(rows)>50 else None,'settings':self.public_settings(db)}
    def lease_view(self,row):
        return {'id':row['id'],'grantId':row['grant_id'],'url':'/api/digital-entitlements/leases/'+row['id']+'/media','created':row['created'],'expires':row['expires']}
    def detail(self,db,ident,admin,query):
        row=self.row(db,ident,admin);item=self.item(db,row);args=[ident];where='u.grant_id=?'
        before=query.get('usesBefore',[''])[0]
        if before:
            cursor=db.execute('SELECT * FROM digital_entitlement_uses WHERE id=? AND grant_id=?',(before,ident)).fetchone()
            if not cursor:self.fail(400,'使用记录分页位置无效。')
            where+=' AND (u.created,u.id)<(?,?)';args.extend((cursor['created'],cursor['id']))
        rows=db.execute('SELECT u.id use_id,l.* FROM digital_entitlement_uses u JOIN digital_access_leases l ON l.id=u.lease_id WHERE '+where+' ORDER BY u.created DESC,u.id DESC LIMIT 101',args).fetchall()
        uses=[];stamp=self.clock()
        for lease in rows[:100]:
            same=lease['owner']==self.owner and lease['session_hash']==self.session()
            reason='session_changed' if not same else 'lease_expired' if lease['expires']<=stamp else 'access_revoked' if not self.eligibility(db,row,stamp) or item['used']>item['totalUses'] else ''
            uses.append({'id':lease['use_id'],'leaseId':lease['id'],'requestId':lease['request_id'],'created':lease['created'],'expires':lease['expires'],
                'canResume':not reason,'url':self.lease_view(lease)['url'] if not reason else '', 'reason':reason})
        return {'item':item,'uses':uses,'usesNext':rows[99]['use_id'] if len(rows)>100 else None,'productionEnabled':False}
    def acquire(self,db,ident,data):
        if set(data)!={'requestId'} or not isinstance(data.get('requestId'),str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',data['requestId']):self.fail(400,'访问请求只接受有效的幂等编号。')
        db.execute('BEGIN IMMEDIATE');row=self.row(db,ident);stamp=self.clock();session=self.session()
        old=db.execute('SELECT * FROM digital_access_leases WHERE owner=? AND request_id=?',(self.owner,data['requestId'])).fetchone()
        if old:
            if old['grant_id']!=ident or old['session_hash']!=session:self.fail(409,'访问编号已用于其他权益或会话。')
            return {'item':self.item(db,row),'lease':self.lease_view(old),'duplicate':True,'productionEnabled':False}
        if not ready(policy(db)):self.fail(503,'数字沙箱使用政策尚未启用。')
        item=self.item(db,row)
        if item['status'] in ('revoked','expired','disabled'):self.fail(409,'数字权益已到期、撤销或暂不可访问。')
        if not item['canAccess']:self.fail(402,'当前可用访问次数不足。')
        lease_id=str(uuid4());expires=min(stamp+json.loads(row['policy_snapshot'])['leaseSeconds']*1000,row['expires'])
        db.execute('INSERT INTO digital_access_leases VALUES(?,?,?,?,?,?,?)',(lease_id,self.owner,ident,data['requestId'],session,stamp,expires))
        return {'item':self.item(db,self.row(db,ident)),'lease':self.lease_view(db.execute('SELECT * FROM digital_access_leases WHERE id=?',(lease_id,)).fetchone()),'duplicate':False,'productionEnabled':False}
    def media(self,db,lease_id):
        db.execute('BEGIN IMMEDIATE')
        lease=db.execute('SELECT * FROM digital_access_leases WHERE id=? AND owner=?',(lease_id,self.owner)).fetchone();stamp=self.clock()
        if not lease or lease['session_hash']!=self.session() or lease['expires']<=stamp:self.fail(403,'此访问凭据不属于当前有效会话或已到期。')
        row=self.row(db,lease['grant_id']);item=self.item(db,row)
        from privacy_domains import media_deleted
        if media_deleted(db,row['media_id']):self.fail(404,'测试素材已删除。')
        active=db.execute("SELECT 1 FROM sessions s WHERE s.token=? AND s.user_id=? AND s.expires>? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=s.user_id AND l.status='closed')",(self.session(),self.owner,time.time_ns()//1_000_000)).fetchone()
        if not active or not self.eligibility(db,row,stamp) or item['used']>item['totalUses']:self.fail(403,'当前数字访问权限已失效。')
        media=db.execute('SELECT mime,data FROM media WHERE id=?',(row['media_id'],)).fetchone()
        if not media:self.fail(404,'测试素材不存在。')
        data=media['data'];length=len(data);status=200
        headers={'Accept-Ranges':'bytes','Cache-Control':'private, no-store','Referrer-Policy':'no-referrer'}
        requested=self.h.headers.get('Range')
        if requested:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
            if not match or not any(match.groups()):self.fail(416,'无效媒体范围。')
            start=int(match[1]) if match[1] else max(0,length-int(match[2]))
            end=min(length-1,int(match[2])) if match[1] and match[2] else length-1
            if start>=length or end<start:self.fail(416,'媒体范围超出文件。')
            headers['Content-Range']=f'bytes {start}-{end}/{length}';data=data[start:end+1];status=206
        return DigitalMediaReply(status,data,media['mime'],headers)
    def route(self,method,path):
        public,admin='/api/digital-entitlements','/api/admin/digital-entitlements'
        if path!=public and not path.startswith(public+'/') and path!=admin and not path.startswith(admin+'/'):return None
        is_admin=path==admin or path.startswith(admin+'/')
        self.owner=self.h.require(['admin'] if is_admin else None)['id']
        self.rate('digital-entitlements:'+('read:' if method=='GET' else 'write:')+self.owner,240 if method=='GET' else 60)
        query=parse_qs(urlsplit(self.h.path).query)
        with self.store.connect() as db:
            if path==admin and method=='GET':return self.admin_view(db)
            if path==admin and method=='PATCH':
                data=self.h.body()
                if set(data)!=set(DEFAULT) or type(data.get('revision')) is not int or type(data.get('enabled')) is not bool or type(data.get('confirmed')) is not bool or not isinstance(data.get('ruleVersion'),str) or len(data['ruleVersion'])>100 or any(data.get(key)!=value for key,value in FIXED.items()):self.fail(400,'数字政策字段或固定沙箱规则无效。')
                if any(value is not None and (type(value) is not int or not minimum<=value<=maximum) for value,minimum,maximum in [(data['validityDays'],1,3650),(data['usesPerUnit'],1,1000)]) or type(data['leaseSeconds']) is not int or not 30<=data['leaseSeconds']<=14400:self.fail(400,'请配置有限天数、次数及访问时长。')
                if data['enabled'] and not ready(data):self.fail(400,'启用前必须明确确认有限的沙箱规则。')
                db.execute('BEGIN IMMEDIATE');current=policy(db)
                if data['revision']!=current['revision']:self.fail(409,'数字政策已更新，请刷新。')
                clean={**data,'revision':current['revision']+1,'ruleVersion':data['ruleVersion'].strip()}
                db.execute("INSERT INTO settings VALUES('digital_entitlements',?) ON CONFLICT(key) DO UPDATE SET data=excluded.data",(dump(clean),))
                self.store.audit(db,self.owner,'digital.policy','sandbox','finite sandbox policy; production disabled')
                return self.admin_view(db)
            if path==admin+'/assets' and method=='POST':
                data=self.h.body()
                if set(data)!={'mediaId','contentId','sandboxOnly'} or data['sandboxOnly'] is not True or any(not isinstance(data.get(key),str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',data[key]) for key in ('mediaId','contentId')):self.fail(400,'请明确登记隔离测试素材与内容。')
                db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT * FROM digital_sandbox_assets WHERE media_id=? OR content_id=?',(data['mediaId'],data['contentId'])).fetchone()
                if old:
                    if old['media_id']!=data['mediaId'] or old['content_id']!=data['contentId'] or old['owner']!=self.owner:self.fail(409,'素材或内容已有其他绑定。')
                    return {'item':self.asset(db,old),'duplicate':True,'productionEnabled':False}
                stamp=self.clock();db.execute('INSERT INTO digital_sandbox_assets VALUES(?,?,?,?,?,?)',(data['mediaId'],data['contentId'],self.owner,'active',stamp,stamp))
                self.store.audit(db,self.owner,'digital.asset',data['mediaId'],'permanent isolated sandbox marker')
                return {'item':self.asset(db,db.execute('SELECT * FROM digital_sandbox_assets WHERE media_id=?',(data['mediaId'],)).fetchone()),'duplicate':False,'productionEnabled':False}
            match=re.fullmatch(admin+'/assets/([^/]+)/disable',path)
            if match and method=='POST':
                if self.h.body():self.fail(400,'停用不接受其他字段。')
                db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM digital_sandbox_assets WHERE media_id=?',(match[1],)).fetchone()
                if not row:self.fail(404,'未找到测试素材。')
                db.execute("UPDATE digital_sandbox_assets SET status='disabled',updated=? WHERE media_id=?",(self.clock(),match[1]))
                self.store.audit(db,self.owner,'digital.asset.disable',match[1],'marker retained permanently')
                return {'item':self.asset(db,db.execute('SELECT * FROM digital_sandbox_assets WHERE media_id=?',(match[1],)).fetchone()),'productionEnabled':False}
            if method=='GET' and path in (public,admin+'/grants'):return self.listing(db,is_admin,query)
            match=re.fullmatch(public+'/leases/([^/]+)/media',path)
            if match and method=='GET':return self.media(db,match[1])
            prefix=admin+'/grants' if is_admin else public
            match=re.fullmatch(prefix+'/([^/]+)(/access)?',path)
            if match:
                try:ident=unquote(match[1],errors='strict')
                except UnicodeError:self.fail(400,'数字权益编号编码无效。')
                if not re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',ident):self.fail(400,'数字权益编号无效。')
                if method=='GET' and not match[2]:return self.detail(db,ident,is_admin,query)
                if method=='POST' and match[2] and not is_admin:return self.acquire(db,ident,self.h.body())
        self.fail(405,'不支持的数字权益操作。')
