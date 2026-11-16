"""Finite sandbox subscription lifecycle; all money and entitlements remain in commerce."""
import calendar,copy,hashlib,json,re,sqlite3,time
from datetime import datetime,timezone
from urllib.parse import parse_qs
from uuid import uuid4

DEFAULT={'sandboxEnabled':False,'productionEnabled':False,'revision':0}
STATES=('trialing','active','renewal_failed','grace','paused','past_due','cancelled_active','expired','revoked')
CHANNELS=('sandbox','apple','google','stripe','paypal')
DDL=r'''
CREATE TABLE IF NOT EXISTS membership_plans(id TEXT PRIMARY KEY,environment TEXT NOT NULL CHECK(environment IN ('sandbox','production')),status TEXT NOT NULL,version INTEGER NOT NULL,sku_id TEXT NOT NULL,group_id TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(environment,sku_id));
CREATE TABLE IF NOT EXISTS membership_plan_versions(id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,version INTEGER NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(plan_id,version));
CREATE TABLE IF NOT EXISTS membership_channel_mappings(id TEXT PRIMARY KEY,environment TEXT NOT NULL,channel TEXT NOT NULL,external_product_id TEXT NOT NULL,plan_id TEXT NOT NULL,plan_version INTEGER NOT NULL,status TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(environment,channel,external_product_id));
CREATE TABLE IF NOT EXISTS membership_order_snapshots(item_id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),order_id TEXT NOT NULL,plan_id TEXT NOT NULL,plan_version INTEGER NOT NULL,group_id TEXT NOT NULL,data TEXT NOT NULL,subscription_id TEXT,payment_event_id TEXT,period_start INTEGER,period_end INTEGER,state TEXT NOT NULL DEFAULT 'pending',created INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS membership_snapshot_owner ON membership_order_snapshots(owner,environment,order_id);
CREATE TABLE IF NOT EXISTS membership_subscriptions(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),group_id TEXT NOT NULL,original_item_id TEXT NOT NULL UNIQUE,current_item_id TEXT NOT NULL,plan_id TEXT NOT NULL,plan_version INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('trialing','active','renewal_failed','grace','paused','past_due','cancelled_active','expired','revoked')),auto_renew INTEGER NOT NULL,period_start INTEGER NOT NULL,period_end INTEGER NOT NULL,grace_end INTEGER,trial_end INTEGER,next_charge_at INTEGER,cancelled_at INTEGER,version INTEGER NOT NULL DEFAULT 1,created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS membership_one_live_group ON membership_subscriptions(owner,environment,group_id) WHERE status NOT IN ('expired','revoked');
CREATE TABLE IF NOT EXISTS membership_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),subscription_id TEXT NOT NULL,request_id TEXT NOT NULL,kind TEXT NOT NULL,fingerprint TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,environment,request_id));
CREATE TABLE IF NOT EXISTS membership_purchase_locks(owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),group_id TEXT NOT NULL,order_id TEXT NOT NULL,subscription_id TEXT,expires INTEGER NOT NULL,PRIMARY KEY(owner,environment,group_id));

CREATE TRIGGER IF NOT EXISTS membership_snapshot_check BEFORE INSERT ON membership_order_snapshots BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_orders o JOIN commerce_order_items i ON i.order_id=o.id WHERE o.id=NEW.order_id AND o.owner=NEW.owner AND o.environment=NEW.environment AND o.payment_status='unpaid' AND i.id=NEW.item_id AND i.type='membership' AND i.quantity=1 AND i.price_version=json_extract(NEW.data,'$.priceVersion') AND i.price_minor=json_extract(NEW.data,'$.firstPriceMinor') AND i.currency=json_extract(NEW.data,'$.currency')) THEN RAISE(ABORT,'membership_snapshot_order_mismatch') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM membership_subscriptions s WHERE s.owner=NEW.owner AND s.environment=NEW.environment AND s.group_id=NEW.group_id AND s.status NOT IN ('expired','revoked') AND (json_extract(NEW.data,'$.renewalOf') IS NULL OR s.id!=json_extract(NEW.data,'$.renewalOf') OR s.auto_renew!=1)) THEN RAISE(ABORT,'membership_duplicate_subscription') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM membership_purchase_locks l JOIN commerce_orders o ON o.id=l.order_id WHERE l.owner=NEW.owner AND l.environment=NEW.environment AND l.group_id=NEW.group_id AND (json_extract(NEW.data,'$.renewalOf') IS NULL OR l.subscription_id IS NULL OR l.subscription_id!=json_extract(NEW.data,'$.renewalOf') OR (EXISTS(SELECT 1 FROM membership_order_snapshots q WHERE q.order_id=l.order_id AND q.subscription_id IS NULL) AND (o.payment_status IN ('paid','partially_refunded') OR o.payment_status='unpaid' AND o.reserved_until>NEW.created)))) THEN RAISE(ABORT,'membership_duplicate_checkout') END;
END;
CREATE TRIGGER IF NOT EXISTS membership_snapshot_lock AFTER INSERT ON membership_order_snapshots BEGIN
 INSERT INTO membership_purchase_locks SELECT NEW.owner,NEW.environment,NEW.group_id,NEW.order_id,json_extract(NEW.data,'$.renewalOf'),o.reserved_until FROM commerce_orders o WHERE o.id=NEW.order_id ON CONFLICT(owner,environment,group_id) DO UPDATE SET order_id=excluded.order_id,expires=excluded.expires;
END;

CREATE TRIGGER IF NOT EXISTS membership_activation_check BEFORE UPDATE OF subscription_id ON membership_order_snapshots WHEN OLD.subscription_id IS NULL AND NEW.subscription_id IS NOT NULL BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM membership_subscriptions s JOIN commerce_order_items i ON i.id=NEW.item_id JOIN commerce_orders o ON o.id=i.order_id JOIN commerce_entitlements e ON e.item_id=i.id JOIN commerce_payment_events p ON p.id=NEW.payment_event_id WHERE s.id=NEW.subscription_id AND s.owner=NEW.owner AND s.environment=NEW.environment AND s.current_item_id=NEW.item_id AND s.period_start=NEW.period_start AND s.period_end=NEW.period_end AND s.status='active' AND i.type='membership' AND i.quantity=1 AND i.refunded_quantity=0 AND o.owner=NEW.owner AND o.payment_status IN ('paid','partially_refunded') AND e.owner=NEW.owner AND e.environment=NEW.environment AND e.status='active' AND e.remaining=1 AND p.order_id=NEW.order_id AND p.owner=NEW.owner AND p.environment=NEW.environment AND p.kind='sandbox_pay' AND p.status='applied') THEN RAISE(ABORT,'membership_activation_changed') END;
END;
CREATE TRIGGER IF NOT EXISTS membership_action_check BEFORE INSERT ON membership_events BEGIN
 SELECT CASE WHEN NEW.kind IN ('cancel_renewal','sandbox_state') AND json_extract(NEW.data,'$._expectedVersion') IS NOT NULL AND NOT EXISTS(SELECT 1 FROM membership_subscriptions s WHERE s.id=NEW.subscription_id AND s.owner=NEW.owner AND s.version=json_extract(NEW.data,'$._expectedVersion')) THEN RAISE(ABORT,'membership_state_changed') END;
 SELECT CASE WHEN NEW.kind='refund_request' AND NOT EXISTS(SELECT 1 FROM commerce_aftersale_requests a JOIN commerce_order_items i ON i.id=json_extract(NEW.data,'$.itemId') AND i.order_id=a.order_id JOIN commerce_orders o ON o.id=a.order_id WHERE a.id=json_extract(NEW.data,'$.id') AND a.owner=NEW.owner AND a.environment=NEW.environment AND o.payment_status IN ('paid','partially_refunded') AND i.quantity>i.refunded_quantity) THEN RAISE(ABORT,'membership_refund_request_changed') END;
END;

CREATE TRIGGER IF NOT EXISTS membership_payment_check BEFORE INSERT ON commerce_payment_events WHEN NEW.kind='sandbox_pay' AND EXISTS(SELECT 1 FROM commerce_order_items WHERE order_id=NEW.order_id AND type='membership') BEGIN
 SELECT CASE WHEN NEW.environment!='sandbox' OR NOT EXISTS(SELECT 1 FROM settings WHERE key='membership_lifecycle' AND json_extract(data,'$.sandboxEnabled')=1) THEN RAISE(ABORT,'membership_payment_disabled') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM commerce_order_items i JOIN commerce_orders o ON o.id=i.order_id LEFT JOIN membership_order_snapshots s ON s.item_id=i.id WHERE i.order_id=NEW.order_id AND i.type='membership' AND (s.item_id IS NULL OR s.owner!=NEW.owner OR s.environment!=NEW.environment OR o.owner!=NEW.owner OR o.payment_status!='unpaid' OR i.quantity!=1 OR i.refunded_quantity!=0 OR i.price_minor!=json_extract(s.data,'$.firstPriceMinor') OR i.price_version!=json_extract(s.data,'$.priceVersion') OR i.currency!=json_extract(s.data,'$.currency'))) THEN RAISE(ABORT,'membership_payment_snapshot_missing_or_changed') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM membership_order_snapshots s WHERE s.order_id=NEW.order_id AND NOT EXISTS(SELECT 1 FROM membership_purchase_locks l WHERE l.owner=s.owner AND l.environment=s.environment AND l.group_id=s.group_id AND l.order_id=s.order_id)) THEN RAISE(ABORT,'membership_payment_slot_changed') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM membership_order_snapshots s WHERE s.order_id=NEW.order_id AND json_extract(s.data,'$.renewalOf') IS NOT NULL AND NOT EXISTS(SELECT 1 FROM membership_subscriptions sub WHERE sub.id=json_extract(s.data,'$.renewalOf') AND sub.owner=NEW.owner AND sub.environment=NEW.environment AND sub.group_id=s.group_id AND sub.auto_renew=1 AND sub.status NOT IN ('expired','revoked') AND (sub.period_end>NEW.created OR sub.status='grace' AND sub.grace_end>NEW.created))) THEN RAISE(ABORT,'membership_payment_renewal_changed') END;
END;
CREATE TRIGGER IF NOT EXISTS membership_snapshot_immutable BEFORE UPDATE OF item_id,owner,environment,order_id,plan_id,plan_version,group_id,data,created ON membership_order_snapshots BEGIN SELECT RAISE(ABORT,'membership_snapshot_immutable'); END;
'''
def now():return time.time_ns()//1_000_000
def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def fingerprint(v):return hashlib.sha256(dump(v).encode()).hexdigest()
def init_schema(db):db.executescript(DDL)
def add_period(stamp,term):
    if term['unit']=='day':return stamp+term['count']*86400000
    d=datetime.fromtimestamp(stamp/1000,timezone.utc);months=term['count']*(12 if term['unit']=='year' else 1);year,month=divmod(d.year*12+d.month-1+months,12);month+=1
    return int(d.replace(year=year,month=month,day=min(d.day,calendar.monthrange(year,month)[1])).timestamp()*1000)

class Membership:
    def __init__(self,store,handler,Error,limiter,*,test_clock=None):
        self.store,self.h,self.Error,self.rate=store,handler,Error,limiter;self.owner=handler.user['id'] if handler.user else '';self.clock=test_clock or now
    def fail(self,status,message):raise self.Error(status,message)
    def text(self,v,n,minimum=0):
        if not isinstance(v,str) or not minimum<=len(v.strip())<=n:self.fail(400,'会员文字字段格式或长度不正确。')
        return v.strip()
    def integer(self,v,n=1000000000):
        if type(v) is not int or not 0<=v<=n:self.fail(400,'会员数值须为范围内整数。')
        return v
    def settings(self):return {**DEFAULT,**self.store.setting('membership_lifecycle'),'productionEnabled':False}
    def enabled(self,db):
        c=db.execute("SELECT data FROM commerce_config WHERE key='settings'").fetchone()
        if not self.settings()['sandboxEnabled'] or not c or not json.loads(c['data']).get('sandboxEnabled'):self.fail(503,'会员与统一交易沙箱尚未同时启用。')
    def own(self,db,sid):
        r=db.execute("SELECT * FROM membership_subscriptions WHERE id=? AND owner=? AND environment='sandbox'",(sid,self.owner)).fetchone()
        if not r:self.fail(404,'未找到本人的订阅。')
        return r
    def order(self,db,oid):
        r=db.execute("SELECT * FROM commerce_orders WHERE id=? AND owner=? AND environment='sandbox'",(oid,self.owner)).fetchone()
        if not r:self.fail(404,'未找到本人的统一订单。')
        return r
    def plan(self,db,pid):
        r=db.execute('SELECT * FROM membership_plans WHERE id=?',(pid,)).fetchone()
        if not r:self.fail(404,'未找到会员方案。')
        return {**json.loads(r['data']),'id':r['id'],'environment':r['environment'],'status':r['status'],'version':r['version'],'skuId':r['sku_id'],'groupId':r['group_id']}
    def sync(self,db):
        t=self.clock()
        db.execute("UPDATE membership_order_snapshots SET state='refunded' WHERE owner=? AND state='active' AND EXISTS(SELECT 1 FROM commerce_order_items i WHERE i.id=membership_order_snapshots.item_id AND i.refunded_quantity=i.quantity)",(self.owner,))
        for r in db.execute("SELECT * FROM membership_subscriptions WHERE owner=? AND environment='sandbox'",(self.owner,)).fetchall():
            periods=db.execute("SELECT * FROM membership_order_snapshots WHERE subscription_id=? AND owner=? AND state='active' ORDER BY period_end DESC,item_id",(r['id'],self.owner)).fetchall()
            if not periods:
                db.execute("UPDATE membership_subscriptions SET status='revoked',auto_renew=0,next_charge_at=NULL,version=version+1,updated=? WHERE id=? AND status!='revoked'",(t,r['id']));continue
            latest=periods[0];status='expired' if max(latest['period_end'],r['grace_end'] or 0)<=t else r['status']
            if latest['item_id']!=r['current_item_id'] or status!=r['status']:
                db.execute("UPDATE membership_subscriptions SET current_item_id=?,plan_id=?,plan_version=?,period_start=?,period_end=?,status=?,auto_renew=CASE WHEN ? IN ('expired','revoked') THEN 0 ELSE auto_renew END,next_charge_at=CASE WHEN ? IN ('expired','revoked') THEN NULL WHEN auto_renew=1 THEN ? ELSE NULL END,version=version+1,updated=? WHERE id=?",(latest['item_id'],latest['plan_id'],latest['plan_version'],latest['period_start'],latest['period_end'],status,status,status,latest['period_end'],t,r['id']))
        db.execute("DELETE FROM membership_purchase_locks WHERE owner=? AND (EXISTS(SELECT 1 FROM membership_subscriptions s WHERE s.id=membership_purchase_locks.subscription_id AND s.status IN ('expired','revoked')) OR (subscription_id IS NULL AND EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=membership_purchase_locks.order_id AND o.payment_status NOT IN ('paid','partially_refunded') AND (o.reserved_until<=? OR o.status='closed'))))",(self.owner,t))
    def snapshot_for_checkout(self,db,owner,items,environment,renewal_of=None):
        """Root calls inside commerce transaction before inserting membership order lines."""
        if owner!=self.owner:self.fail(403,'会员快照账号不符。')
        if environment!='sandbox':self.fail(403,'正式会员收费未开放。')
        self.enabled(db);self.sync(db);out={}
        for item in items:
            sku=db.execute('SELECT s.*,p.type,p.status product_status FROM commerce_skus s JOIN commerce_products p ON p.id=s.product_id WHERE s.id=?',(item.get('skuId'),)).fetchone()
            if not sku or sku['type']!='membership':continue
            if type(item.get('quantity')) is not int or item['quantity']!=1:self.fail(400,'订阅订单项数量必须为1。')
            row=db.execute("SELECT id FROM membership_plans WHERE sku_id=? AND environment='sandbox' AND status='published'",(sku['id'],)).fetchone()
            if not row:self.fail(503,'会员SKU尚未绑定已确认沙箱方案。')
            p=self.plan(db,row['id'])
            if p['priceVersion']!=sku['version'] or p['firstPriceMinor']!=sku['price_minor'] or p['currency']!=sku['currency'] or sku['product_status']!='published':self.fail(409,'会员价格或商品版本已变化。')
            live=db.execute("SELECT * FROM membership_subscriptions WHERE owner=? AND environment='sandbox' AND group_id=? AND status NOT IN ('expired','revoked')",(owner,p['groupId'])).fetchone()
            if live:
                if renewal_of!=live['id'] or p['billingMode']!='recurring' or live['auto_renew']!=1:self.fail(409,'已有同权益组订阅，请管理原订阅。')
                if p['renewalPriceMinor']!=sku['price_minor']:self.fail(503,'续费价尚无匹配统一SKU，不能按首期价格代扣。')
            elif renewal_of:self.fail(409,'未找到可关联的续费订阅。')
            if any(v['groupId']==p['groupId'] for v in out.values()):self.fail(409,'同一订单不能重复购买同权益组。')
            out[sku['id']]={**p,'renewalOf':renewal_of,'snapshotSchema':1,'snapshotAt':self.clock()}
        return out
    def capture_order_snapshots(self,db,owner,order_id,snapshots):
        """Root calls in SAME commerce transaction BEFORE payment. Never attach to a paid order."""
        if owner!=self.owner:self.fail(403,'会员成交快照账号不符。')
        order=self.order(db,order_id)
        if order['payment_status']!='unpaid':self.fail(409,'已付款订单不能按当前方案补写快照。')
        for line in db.execute("SELECT * FROM commerce_order_items WHERE order_id=? AND type='membership'",(order_id,)).fetchall():
            p=snapshots.get(line['sku_id'])
            if not p or p['environment']!='sandbox' or line['quantity']!=1 or line['price_version']!=p['priceVersion'] or line['price_minor']!=p['firstPriceMinor'] or line['currency']!=p['currency']:self.fail(409,'会员订单项与成交快照不一致。')
            old=db.execute('SELECT data FROM membership_order_snapshots WHERE item_id=?',(line['id'],)).fetchone()
            if old:
                if old['data']!=dump(p):self.fail(409,'成交快照不可覆盖。')
                continue
            lock=db.execute("SELECT * FROM membership_purchase_locks WHERE owner=? AND environment='sandbox' AND group_id=?",(owner,p['groupId'])).fetchone()
            if lock and not (p.get('renewalOf') and lock['subscription_id']==p['renewalOf']):self.fail(409,'该权益组已有待付款或有效订阅。')
            try:db.execute("INSERT INTO membership_order_snapshots(item_id,owner,environment,order_id,plan_id,plan_version,group_id,data,created) VALUES(?,?,'sandbox',?,?,?,?,?,?)",(line['id'],owner,order_id,p['id'],p['version'],p['groupId'],dump(p),self.clock()))
            except sqlite3.IntegrityError:self.fail(409,'会员成交或重复订阅状态已变化。')
    def event(self,db,sid,key,kind,data):
        token=fingerprint({'subscriptionId':sid,'kind':kind,'data':data});old=db.execute("SELECT * FROM membership_events WHERE owner=? AND environment='sandbox' AND request_id=?",(self.owner,key)).fetchone()
        if old:
            if old['fingerprint']!=token:self.fail(409,'会员幂等编号已用于其他操作。')
            return old,True
        eid=str(uuid4());db.execute("INSERT INTO membership_events VALUES(?,?,'sandbox',?,?,?,?,?,?)",(eid,self.owner,sid,key,kind,token,dump(data),self.clock()))
        return db.execute('SELECT * FROM membership_events WHERE id=?',(eid,)).fetchone(),False
    def activate_item(self,db,item_id):
        r=db.execute("SELECT s.*,i.refunded_quantity,i.quantity,i.type,o.owner order_owner,o.payment_status,e.status entitlement_status,e.remaining FROM membership_order_snapshots s JOIN commerce_order_items i ON i.id=s.item_id AND i.order_id=s.order_id JOIN commerce_orders o ON o.id=s.order_id JOIN commerce_entitlements e ON e.item_id=s.item_id AND e.owner=s.owner AND e.environment=s.environment WHERE s.item_id=? AND s.owner=? AND s.environment='sandbox'",(item_id,self.owner)).fetchone()
        if not r or r['type']!='membership' or r['order_owner']!=self.owner:self.fail(409,'缺本人统一会员权益或成交快照。')
        if r['subscription_id']:return r['subscription_id']
        payment=db.execute("SELECT * FROM commerce_payment_events WHERE order_id=? AND owner=? AND environment='sandbox' AND kind='sandbox_pay' AND status='applied'",(r['order_id'],self.owner)).fetchone()
        if not payment or r['payment_status'] not in ('paid','partially_refunded') or r['quantity']!=1 or r['refunded_quantity'] or r['entitlement_status']!='active' or r['remaining']!=1:self.fail(409,'仅本人已付款未退款统一沙箱会员项可激活。')
        p=json.loads(r['data']);sid=p.get('renewalOf');t=self.clock();start=payment['created']
        if sid:
            previous=self.own(db,sid)
            if previous['group_id']!=r['group_id'] or not previous['auto_renew'] or previous['status'] in ('revoked','expired'):self.fail(409,'原订阅不再接受此续期，需核对测试订单。')
            start=max(start,previous['period_end']);end=add_period(start,p['term'])
            db.execute("UPDATE membership_subscriptions SET current_item_id=?,plan_id=?,plan_version=?,status='active',period_start=?,period_end=?,grace_end=NULL,next_charge_at=?,version=version+1,updated=? WHERE id=? AND owner=?",(item_id,r['plan_id'],r['plan_version'],start,end,end,t,sid,self.owner))
        else:
            if db.execute("SELECT 1 FROM membership_subscriptions WHERE owner=? AND environment='sandbox' AND group_id=? AND status NOT IN ('expired','revoked')",(self.owner,r['group_id'])).fetchone():self.fail(409,'该权益组已有有效订阅。')
            sid=str(uuid4());end=add_period(start,p['term']);renew=p['billingMode']=='recurring'
            db.execute("INSERT INTO membership_subscriptions(id,owner,environment,group_id,original_item_id,current_item_id,plan_id,plan_version,status,auto_renew,period_start,period_end,next_charge_at,created,updated) VALUES(?,?,'sandbox',?,?,?,?,?,'active',?,?,?,?,?,?)",(sid,self.owner,r['group_id'],item_id,item_id,r['plan_id'],r['plan_version'],int(renew),start,end,end if renew else None,t,t))
        db.execute("UPDATE membership_order_snapshots SET subscription_id=?,payment_event_id=?,period_start=?,period_end=?,state='active' WHERE item_id=? AND subscription_id IS NULL",(sid,payment['id'],start,end,item_id))
        db.execute("UPDATE membership_purchase_locks SET subscription_id=?,expires=? WHERE owner=? AND environment='sandbox' AND group_id=?",(sid,end,self.owner,r['group_id']))
        self.event(db,sid,'activation:'+item_id,'sandbox_activation',{'itemId':item_id,'orderId':r['order_id'],'paymentEventId':payment['id'],'source':'unified-commerce-sandbox'});return sid
    def validate_commerce_payment(self,db,order_id):
        order=self.order(db,order_id);lines=db.execute("SELECT * FROM commerce_order_items WHERE order_id=? AND type='membership'",(order_id,)).fetchall()
        if not lines or order['payment_status'] in ('paid','partially_refunded','refunded'):return True
        self.enabled(db)
        for line in lines:
            row=db.execute('SELECT * FROM membership_order_snapshots WHERE item_id=? AND owner=?',(line['id'],self.owner)).fetchone()
            if not row:self.fail(409,'会员订单缺少付款前已确认快照，不能付款。')
            if row['subscription_id']:continue
            p=json.loads(row['data'])
            if p.get('renewalOf'):
                sub=self.own(db,p['renewalOf'])
                if sub['group_id']!=p['groupId'] or not sub['auto_renew'] or sub['status'] in ('expired','revoked') or sub['period_end']<=self.clock() and sub['status']!='grace':self.fail(409,'原订阅不再接受此续期，不能继续付款。')
            if not db.execute("SELECT 1 FROM membership_purchase_locks WHERE owner=? AND environment='sandbox' AND group_id=? AND order_id=?",(self.owner,p['groupId'],order_id)).fetchone():self.fail(409,'会员购买占位已变化，不能继续付款。')
        return True
    def on_commerce_payment(self,db,order_id):
        """Root uses verified commerce transaction; callback cannot create payments or paid time."""
        self.order(db,order_id);self.sync(db)
        return [self.activate_item(db,r['id']) for r in db.execute("SELECT id FROM commerce_order_items WHERE order_id=? AND type='membership'",(order_id,)).fetchall()]
    def on_commerce_refund(self,db,order_id):
        """Trusted refund callback: derive owner from the verified order, never the admin actor."""
        order=db.execute("SELECT owner,environment FROM commerce_orders WHERE id=?",(order_id,)).fetchone()
        if not order or order['environment']!='sandbox':self.fail(404,'未找到统一沙箱订单。')
        original=self.owner;self.owner=order['owner']
        try:
            self.sync(db)
            return {'environment':'sandbox','ownerId':self.owner,'subscriptionIds':[r['subscription_id'] for r in db.execute('SELECT DISTINCT subscription_id FROM membership_order_snapshots WHERE order_id=? AND subscription_id IS NOT NULL',(order_id,))],'productionEnabled':False}
        finally:self.owner=original
    def order_snapshots(self,db,order_id):
        self.order(db,order_id);lines=db.execute("SELECT * FROM commerce_order_items WHERE order_id=? AND type='membership'",(order_id,)).fetchall();items=[]
        for line in lines:
            row=db.execute("SELECT data,plan_id,plan_version FROM membership_order_snapshots WHERE item_id=? AND owner=?",(line['id'],self.owner)).fetchone()
            if not row:self.fail(409,'此会员订单缺少付款前成交条款快照，请勿付款。')
            p=json.loads(row['data']);items.append({'itemId':line['id'],'skuId':line['sku_id'],'planId':row['plan_id'],'planVersion':row['plan_version'],**{k:p[k] for k in ('ruleVersion','termsVersion','term','firstPriceMinor','renewalPriceMinor','currency','priceVersion','benefits','serviceTerms','refundPolicy')},'plan':p})
        return {'orderId':order_id,'environment':'sandbox','items':items,'grantsProductionAccess':False,'productionEnabled':False}
    def subscription(self,db,r):
        periods=db.execute("SELECT s.*,i.refunded_quantity,e.remaining,e.status entitlement_status FROM membership_order_snapshots s JOIN commerce_order_items i ON i.id=s.item_id JOIN commerce_entitlements e ON e.item_id=s.item_id AND e.owner=s.owner AND e.environment=s.environment WHERE s.subscription_id=? AND s.owner=? ORDER BY s.period_start,s.item_id",(r['id'],self.owner)).fetchall();current=next((x for x in periods if x['item_id']==r['current_item_id']),None);t=self.clock()
        access=r['status'] in ('trialing','active','renewal_failed','cancelled_active','grace') and (any(x['state']=='active' and not x['refunded_quantity'] and x['remaining']==1 and x['entitlement_status']=='active' and x['period_start']<=t<x['period_end'] for x in periods) or r['status']=='grace' and bool(r['grace_end'] and t<r['grace_end']) and any(x['state']=='active' and not x['refunded_quantity'] and x['remaining']==1 and x['entitlement_status']=='active' for x in periods))
        return {'id':r['id'],'accountId':self.owner,'environment':'sandbox','sandboxOnly':True,'productionEnabled':False,'grantsProductionAccess':False,'actualBillingEnabled':False,'plan':json.loads(current['data']) if current else {},'status':r['status'],'autoRenew':bool(r['auto_renew']),'periodStart':r['period_start'],'periodEnd':r['period_end'],'graceEnd':r['grace_end'],'trialEnd':r['trial_end'],'nextChargeAt':r['next_charge_at'],'nextChargeIsSandboxOnly':True,'cancelledAt':r['cancelled_at'],'hasSandboxAccess':bool(access),'version':r['version'],'periods':[{'orderId':x['order_id'],'itemId':x['item_id'],'planVersion':x['plan_version'],'ruleVersion':json.loads(x['data'])['ruleVersion'],'periodStart':x['period_start'],'periodEnd':x['period_end'],'state':x['state']} for x in periods],'events':[{'id':e['id'],'requestId':e['request_id'],'kind':e['kind'],'data':json.loads(e['data']),'createdAt':e['created']} for e in db.execute('SELECT * FROM membership_events WHERE subscription_id=? AND owner=? ORDER BY rowid',(r['id'],self.owner))],'management':{'channel':'sandbox','cancelAvailable':True,'refundRequestAvailable':True,'restoreAvailable':True,'providerVerified':False}}
    def save_plan(self,d):
        allowed={'id','version','environment','status','skuId','groupId','title','description','billingMode','term','renewalPriceMinor','benefits','ruleVersion','termsVersion','serviceTerms','refundPolicy','graceDays','trialDays','promotionsEnabled'}
        env=d.get('environment');status=d.get('status','draft');term=d.get('term',{})
        if set(d)-allowed or env not in ('sandbox','production') or status not in ('draft','published','archived'):self.fail(400,'会员方案字段、环境或状态不正确。')
        if not isinstance(term,dict) or set(term)!={'unit','count'} or term['unit'] not in ('day','month','year'):self.fail(400,'会员须明确有限周期。')
        count=self.integer(term['count'],366)
        if count<1 or term['unit']=='month' and count>12 or term['unit']=='year' and count>5:self.fail(400,'会员周期超限，不提供永久付费。')
        if d.get('billingMode') not in ('recurring','one_time') or type(d.get('trialDays',0)) is not int or d.get('trialDays',0)!=0 or d.get('promotionsEnabled',False) is not False:self.fail(400,'计费方式不正确，试用优惠未开放。')
        grace=self.integer(d.get('graceDays',0),30);benefits=d.get('benefits')
        if not isinstance(benefits,dict) or set(benefits)!={'catalogScope','courseIds','aiCredits','aiResetCycle','other'} or benefits['catalogScope'] not in ('none','selected','member_catalog') or benefits['aiResetCycle'] not in ('none','month','year','billing_period') or not isinstance(benefits['courseIds'],list) or len(benefits['courseIds'])>100 or any(not isinstance(x,str) or not 1<=len(x)<=100 for x in benefits['courseIds']) or not isinstance(benefits['other'],list) or len(benefits['other'])>30 or any(not isinstance(x,str) or not 1<=len(x)<=500 for x in benefits['other']):self.fail(400,'须逐项配置有限权益和AI重置周期。')
        if benefits['aiCredits'] is not None:self.integer(benefits['aiCredits'],1000000)
        renewal=d.get('renewalPriceMinor')
        if d['billingMode']=='recurring':self.integer(renewal)
        elif renewal is not None:self.fail(400,'一次购买不能填写续费价。')
        pid=self.text(d.get('id',str(uuid4())),100,1);group=self.text(d.get('groupId','membership'),80,1)
        if not re.fullmatch('[A-Za-z0-9_-]+',group):self.fail(400,'权益组编号不正确。')
        data={k:self.text(d.get(k,''),n,1 if status=='published' else 0) for k,n in [('title',160),('description',3000),('ruleVersion',100),('termsVersion',100),('serviceTerms',6000),('refundPolicy',6000)]}
        data.update({'billingMode':d['billingMode'],'term':term,'renewalPriceMinor':renewal,'benefits':benefits,'graceDays':grace,'trialDays':0,'promotionsEnabled':False,'channel':'sandbox' if env=='sandbox' else None,'actualBillingEnabled':False})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT * FROM membership_plans WHERE id=?',(pid,)).fetchone()
            if old and (type(d.get('version')) is not int or d['version']!=old['version']):self.fail(409,'会员方案版本已变化。')
            if old and (old['environment']!=env or old['group_id']!=group or old['sku_id']!=d.get('skuId')):self.fail(400,'既有方案不能换环境、权益组或SKU。')
            sku=db.execute('SELECT s.*,p.type FROM commerce_skus s JOIN commerce_products p ON p.id=s.product_id WHERE s.id=?',(d.get('skuId'),)).fetchone()
            if not sku or sku['type']!='membership' or sku['environment']!=env:self.fail(400,'须绑定同环境统一会员SKU。')
            if db.execute('SELECT 1 FROM membership_plans WHERE sku_id=? AND environment=? AND id!=?',(sku['id'],env,pid)).fetchone():self.fail(409,'同一SKU已有会员方案。')
            data.update({'firstPriceMinor':sku['price_minor'],'currency':sku['currency'],'priceVersion':sku['version']});version=old['version']+1 if old else 1;t=self.clock()
            db.execute('INSERT INTO membership_plans VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,version=excluded.version,data=excluded.data,updated=excluded.updated',(pid,env,status,version,sku['id'],group,dump(data),t,t))
            frozen={**data,'id':pid,'environment':env,'status':status,'version':version,'skuId':sku['id'],'groupId':group};db.execute('INSERT INTO membership_plan_versions VALUES(?,?,?,?,?)',(str(uuid4()),pid,version,dump(frozen),t));self.store.audit(db,self.owner,'membership.plan',pid,'方案版本；正式计费关闭')
            return {'item':self.plan(db,pid),'productionEnabled':False}
    def cancel(self,sid,d):
        if set(d)!={'requestId'}:self.fail(400,'取消续费只接受幂等编号。')
        key=self.text(d.get('requestId'),128,1)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.sync(db);r=self.own(db,sid);_,replay=self.event(db,sid,key,'cancel_renewal',{'source':'sandbox-self-service'})
            if not replay:
                status=('cancelled_active' if r['period_end']>self.clock() else 'expired') if r['status'] in ('active','renewal_failed','grace','cancelled_active') else r['status'];db.execute('UPDATE membership_subscriptions SET auto_renew=0,next_charge_at=NULL,cancelled_at=?,status=?,version=version+1,updated=? WHERE id=?',(self.clock(),status,self.clock(),sid));self.store.audit(db,self.owner,'membership.sandbox.cancel',sid,'只关闭沙箱续费，保留已付期')
            return self.subscription(db,self.own(db,sid))
    def refund_request(self,sid,d):
        if set(d)!={'requestId','reason'}:self.fail(400,'退款申请须包含编号和原因。')
        key=self.text(d.get('requestId'),128,1);reason=self.text(d.get('reason'),2000,1);request_token=fingerprint({'subscriptionId':sid,'reason':reason})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.sync(db);r=self.own(db,sid);old=db.execute("SELECT * FROM membership_events WHERE owner=? AND environment='sandbox' AND request_id=?",(self.owner,key)).fetchone()
            if old:
                stored=json.loads(old['data'])
                if old['kind']!='refund_request' or stored.get('requestFingerprint')!=request_token:self.fail(409,'退款申请编号已用于其他操作。')
                return {'request':stored,'subscription':self.subscription(db,r),'fundsRefunded':False}
            item=db.execute('SELECT * FROM commerce_order_items WHERE id=?',(r['current_item_id'],)).fetchone();order=self.order(db,item['order_id'])
            if item['quantity']<=item['refunded_quantity'] or order['payment_status'] not in ('paid','partially_refunded'):self.fail(409,'该周期无可申请退款数量。')
            aid=str(uuid4());t=self.clock()
            db.execute("INSERT INTO commerce_aftersale_requests VALUES(?,?,'sandbox',?,?,?,?,1,'pending',?,?)",(aid,self.owner,order['id'],'membership:'+key,fingerprint({'orderId':order['id'],'reason':reason,'quantity':1}),reason,t,t));db.execute("UPDATE commerce_orders SET aftersale_status='requested',updated=? WHERE id=?",(t,order['id']))
            response={'id':aid,'orderId':order['id'],'itemId':item['id'],'reason':reason,'status':'pending','environment':'sandbox','requestFingerprint':request_token,'fundsRefunded':False};db.execute("INSERT INTO membership_events VALUES(?,?,'sandbox',?,?,?,?,?,?)",(str(uuid4()),self.owner,sid,key,'refund_request',request_token,dump(response),t));self.store.audit(db,self.owner,'membership.refund_request',sid,'统一售后待处理，未退款')
            return {'request':response,'subscription':self.subscription(db,self.own(db,sid)),'fundsRefunded':False}
    def restore(self,d):
        if set(d)-{'requestId','environment','orderId'} or d.get('environment')!='sandbox':self.fail(403,'真实渠道恢复验单未接通，仅恢复本人统一沙箱订单。')
        key=self.text(d.get('requestId'),128,1);oid=self.text(d['orderId'],100,1) if d.get('orderId') else None
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.sync(db)
            if oid:self.order(db,oid)
            _,replay=self.event(db,'',key,'restore',{'orderId':oid})
            if not replay:
                rows=db.execute("SELECT s.item_id FROM membership_order_snapshots s JOIN commerce_orders o ON o.id=s.order_id WHERE s.owner=? AND s.environment='sandbox' AND o.payment_status IN ('paid','partially_refunded') AND (? IS NULL OR s.order_id=?)",(self.owner,oid,oid)).fetchall()
                for row in rows:self.activate_item(db,row['item_id'])
                self.sync(db);self.store.audit(db,self.owner,'membership.sandbox.restore',oid or 'own-orders','核本人已付订单，不重置有效期')
            return {'items':[self.subscription(db,r) for r in db.execute("SELECT * FROM membership_subscriptions WHERE owner=? ORDER BY created DESC",(self.owner,))],'environment':'sandbox','productionEnabled':False,'providerVerified':False}
    def sandbox_event(self,d):
        if set(d)-{'requestId','subscriptionId','event','environment'} or d.get('environment')!='sandbox':self.fail(403,'真实渠道未接入，不能模拟生产。')
        key=self.text(d.get('requestId'),128,1);sid=self.text(d.get('subscriptionId'),100,1);event=d.get('event')
        if event not in ('renewal_failed','grace_started','paused','account_hold','resumed','expired'):self.fail(400,'状态事件不能制造付款、试用、退款或加时。')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');self.enabled(db);target=db.execute("SELECT owner FROM membership_subscriptions WHERE id=? AND environment='sandbox'",(sid,)).fetchone()
            if not target:self.fail(404,'未找到测试订阅。')
            original=self.owner;self.owner=target['owner']
            try:
                self.sync(db);r=self.own(db,sid);p=json.loads(db.execute('SELECT data FROM membership_order_snapshots WHERE item_id=?',(r['current_item_id'],)).fetchone()['data']);_,replay=self.event(db,sid,key,'sandbox_state',{'event':event,'source':'sandbox-simulator','actorRole':'admin'})
                if not replay:
                    if r['status']=='revoked' or r['status']=='expired' and event!='expired':self.fail(409,'终态不能凭事件恢复。')
                    status=r['status'];grace=r['grace_end'];t=self.clock()
                    if event=='renewal_failed':
                        if not r['auto_renew'] or status not in ('active','renewal_failed'):self.fail(409,'该状态不接受续费失败。')
                        status='renewal_failed'
                    elif event=='grace_started':
                        if status!='renewal_failed' or not r['auto_renew'] or p['graceDays']<1:self.fail(409,'未确认宽限规则或无续费失败。')
                        status='grace';grace=r['period_end']+p['graceDays']*86400000
                    elif event in ('paused','account_hold'):status='paused' if event=='paused' else 'past_due'
                    elif event=='resumed':
                        if status not in ('paused','past_due','grace','renewal_failed') or t>=r['period_end']:self.fail(409,'恢复不能延长已付期，需新已付续期订单。')
                        status='active';grace=None
                    elif event=='expired':
                        if t<max(r['period_end'],grace or 0):self.fail(409,'权益尚未到期。')
                        status='expired'
                    db.execute("UPDATE membership_subscriptions SET status=?,grace_end=?,next_charge_at=CASE WHEN ? IN ('paused','past_due','expired') THEN NULL WHEN auto_renew=1 THEN period_end ELSE NULL END,version=version+1,updated=? WHERE id=?",(status,grace,status,t,sid));self.store.audit(db,original,'membership.sandbox.state',sid,'sandbox-simulator；'+event+'；不制造付款或加时')
                return self.subscription(db,self.own(db,sid))
            finally:self.owner=original
    def route(self,method,path):
        try:return self._route(method,path)
        except sqlite3.IntegrityError:self.fail(409,'会员订单或订阅状态已变化，请重新核对。')
    def _route(self,method,path):
        if not(path.startswith('/api/membership/') or path=='/api/admin/membership' or path.startswith('/api/admin/membership/')):return None
        self.h.require();self.rate(('membership-read:' if method=='GET' else 'membership-write:')+self.owner,180 if method=='GET' else 30)
        if path.startswith('/api/admin/'):
            self.h.require(['admin']);d=self.h.body() if method in ('POST','PATCH') else {}
            if path=='/api/admin/membership/plans' and method=='POST':return self.save_plan(d)
            if path=='/api/admin/membership/settings' and method=='PATCH':
                if set(d)-{'sandboxEnabled','productionEnabled','revision'} or type(d.get('sandboxEnabled')) is not bool or 'productionEnabled' in d and d['productionEnabled'] is not False:self.fail(400,'会员生产渠道不能启用。')
                with self.store.connect() as db:
                    db.execute('BEGIN IMMEDIATE');old=self.settings()
                    if type(d.get('revision')) is not int or d['revision']!=old['revision']:self.fail(409,'会员配置版本已变化。')
                    value={'sandboxEnabled':d['sandboxEnabled'],'productionEnabled':False,'revision':old['revision']+1};db.execute("INSERT INTO settings VALUES('membership_lifecycle',?) ON CONFLICT(key) DO UPDATE SET data=excluded.data",(dump(value),))
                return {'settings':value}
            if path=='/api/admin/membership/channel-mappings' and method=='POST':
                env=d.get('environment');channel=d.get('channel');status=d.get('status','draft')
                if set(d)-{'environment','channel','externalProductId','planId','planVersion','status'} or env not in ('sandbox','production') or channel not in CHANNELS or status not in ('draft','published') or channel!='sandbox' and status!='draft' or channel=='sandbox' and env!='sandbox':self.fail(400,'真实渠道只存未启用映射。')
                external=self.text(d.get('externalProductId'),200,1)
                with self.store.connect() as db:
                    db.execute('BEGIN IMMEDIATE');p=self.plan(db,d.get('planId'))
                    if p['environment']!=env or type(d.get('planVersion')) is not int or d['planVersion']!=p['version']:self.fail(409,'映射须引用同环境当前方案版本。')
                    old=db.execute('SELECT * FROM membership_channel_mappings WHERE environment=? AND channel=? AND external_product_id=?',(env,channel,external)).fetchone()
                    if old and old['plan_id']!=p['id']:self.fail(409,'同渠道商品不能映射多个方案。')
                    t=self.clock();db.execute('INSERT INTO membership_channel_mappings VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(environment,channel,external_product_id) DO UPDATE SET plan_version=excluded.plan_version,status=excluded.status,updated=excluded.updated',(old['id'] if old else str(uuid4()),env,channel,external,p['id'],p['version'],status,t,t))
                return {'item':{'planId':p['id'],'planVersion':p['version'],'environment':env,'channel':channel,'externalProductId':external,'status':status,'integrationEnabled':False},'productionEnabled':False}
            if path=='/api/admin/membership/sandbox-events' and method=='POST':return self.sandbox_event(d)
            if path=='/api/admin/membership' and method=='GET':
                with self.store.connect() as db:return {'settings':self.settings(),'plans':[self.plan(db,r['id']) for r in db.execute('SELECT id FROM membership_plans ORDER BY updated DESC')],'channelMappings':[dict(r) for r in db.execute('SELECT * FROM membership_channel_mappings')],'productionEnabled':False,'externalIntegrationsEnabled':False}
            self.fail(404,'未找到会员管理接口。')
        if path=='/api/membership/catalog' and method=='GET':
            env=parse_qs(getattr(self.h,'path','').partition('?')[2]).get('environment',['production'])[0]
            if env not in ('production','sandbox'):self.fail(400,'会员环境不正确。')
            with self.store.connect() as db:
                settings=self.settings();plans=[self.plan(db,r['id']) for r in db.execute("SELECT id FROM membership_plans WHERE environment=? AND status='published' ORDER BY updated DESC",(env,))]
                commerce=db.execute("SELECT data FROM commerce_config WHERE key='settings'").fetchone();commerce_enabled=bool(commerce and json.loads(commerce['data']).get('sandboxEnabled'))
                for p in plans:
                    sku=db.execute('SELECT s.version,p.status FROM commerce_skus s JOIN commerce_products p ON p.id=s.product_id WHERE s.id=?',(p['skuId'],)).fetchone();p['purchasable']=env=='sandbox' and settings['sandboxEnabled'] and commerce_enabled and bool(sku and sku['version']==p['priceVersion'] and sku['status']=='published');p['grantsProductionAccess']=False
                return {'items':plans if env=='production' or settings['sandboxEnabled'] else [],'environment':env,'settings':settings,'productionEnabled':False,'freeAccessPolicy':'existing-rules','productionPricingConfirmed':False}
        if path=='/api/membership/status' and method=='GET':
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE');self.sync(db);items=[self.subscription(db,r) for r in db.execute("SELECT * FROM membership_subscriptions WHERE owner=? ORDER BY created DESC",(self.owner,))]
                purchases=[{'id':r['id'],'orderId':r['order_id'],'contentId':r['content_id'],'environment':r['environment'],'remaining':r['remaining'],'status':r['status']} for r in db.execute("SELECT * FROM commerce_entitlements WHERE owner=? AND type='digital'",(self.owner,))]
                return {'accountId':self.owner,'items':items,'independentPurchases':purchases,'productionEnabled':False,'externalChannels':[{'channel':c,'verificationEnabled':False,'cancelConfirmed':False,'managementHelpUrl':'https://support.apple.com/en-us/118428' if c=='apple' else 'https://support.google.com/googleplay/answer/7018481?hl=en' if c=='google' else None} for c in CHANNELS if c!='sandbox'],'accountClosureReminder':{'renewingSubscriptions':[{'id':x['id'],'channel':'sandbox','periodEnd':x['periodEnd'],'nextChargeAt':x['nextChargeAt'],'actualBillingEnabled':False} for x in items if x['autoRenew'] and x['status'] not in ('expired','revoked')],'message':'卸载或注销本方账号不等于取消第三方订阅；正式渠道未接通，不能确认其续费状态。','thirdPartyRenewalStatus':'not-connected'}}
        if path=='/api/membership/restore' and method=='POST':return self.restore(self.h.body())
        match=re.fullmatch('/api/membership/subscriptions/([^/]+)/(cancel-renewal|refund-request)',path)
        if match and method=='POST':return self.cancel(match[1],self.h.body()) if match[2]=='cancel-renewal' else self.refund_request(match[1],self.h.body())
        snapshots=re.fullmatch('/api/membership/orders/([^/]+)/snapshots',path)
        if snapshots and method=='GET':
            with self.store.connect() as db:return self.order_snapshots(db,snapshots[1])
        match=re.fullmatch('/api/membership/orders/([^/]+)/activate',path)
        if match and method=='POST':
            if self.h.body() not in ({},{'environment':'sandbox'}):self.fail(400,'激活不接受客户端声明付款或有效期。')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE');self.enabled(db);ids=self.on_commerce_payment(db,match[1]);self.sync(db)
                return {'items':[self.subscription(db,self.own(db,sid)) for sid in ids],'environment':'sandbox','productionEnabled':False}
        self.fail(404,'未找到会员生命周期接口。')

