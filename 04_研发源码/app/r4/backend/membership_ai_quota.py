"""Finite, isolated sandbox membership AI periods. No production quota grants."""
import calendar
import copy
from datetime import datetime, timezone
import hashlib
import json
import time

DEFAULT = {'revision':0,'enabled':False,'confirmed':False,'ruleVersion':'','environment':'sandbox',
    'cycleAnchor':'paid_start_utc','unusedPolicy':'expire','inflightPolicy':'settle_reserved',
    'refundPolicy':'revoke_unused','pausePolicy':'freeze','gracePolicy':'no_new_grants',
    'postExpiryWalletPolicy':'no_automatic_fallback'}
FIXED = {key:value for key,value in DEFAULT.items() if key not in ('revision','enabled','confirmed','ruleVersion')}
ALLOWED_STATES = ('active','renewal_failed','cancelled_active')
DDL = """
CREATE TABLE IF NOT EXISTS membership_ai_periods(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,subscription_id TEXT NOT NULL,item_id TEXT NOT NULL,
 cycle_start INTEGER NOT NULL,cycle_end INTEGER NOT NULL,credits INTEGER NOT NULL CHECK(credits>=0),
 balance INTEGER NOT NULL CHECK(balance>=0),reserved INTEGER NOT NULL CHECK(reserved>=0 AND reserved<=balance),
 status TEXT NOT NULL CHECK(status IN ('active','frozen','closing','closed')),reason TEXT NOT NULL,
 policy_snapshot TEXT NOT NULL,benefits_snapshot TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,
 UNIQUE(owner,item_id,cycle_start)
);
CREATE INDEX IF NOT EXISTS membership_ai_owner ON membership_ai_periods(owner,cycle_end,id);
CREATE TABLE IF NOT EXISTS membership_ai_allocations(
 job_id TEXT PRIMARY KEY,owner TEXT NOT NULL,period_id TEXT NOT NULL,
 reserved_credits INTEGER NOT NULL CHECK(reserved_credits>=0),
 charged_credits INTEGER CHECK(charged_credits IS NULL OR (charged_credits>=0 AND charged_credits<=reserved_credits)),
 state TEXT NOT NULL CHECK(state IN ('reserved','settled')),created INTEGER NOT NULL,updated INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS membership_ai_events(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,period_id TEXT NOT NULL,job_id TEXT NOT NULL DEFAULT '',
 action TEXT NOT NULL,credits INTEGER NOT NULL,created INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS membership_ai_events_owner ON membership_ai_events(owner,created,id);
CREATE TRIGGER IF NOT EXISTS membership_ai_period_identity BEFORE UPDATE OF
 id,owner,subscription_id,item_id,cycle_start,cycle_end,credits,policy_snapshot,benefits_snapshot,created
 ON membership_ai_periods BEGIN SELECT RAISE(ABORT,'membership_ai_period_immutable'); END;
CREATE TRIGGER IF NOT EXISTS membership_ai_allocation_identity BEFORE UPDATE OF
 job_id,owner,period_id,reserved_credits,created ON membership_ai_allocations
 BEGIN SELECT RAISE(ABORT,'membership_ai_allocation_immutable'); END;
CREATE TRIGGER IF NOT EXISTS membership_ai_job_source_identity BEFORE UPDATE OF quota_source,quota_period_id
 ON ai_gateway_jobs BEGIN SELECT RAISE(ABORT,'membership_ai_job_source_immutable'); END;
CREATE TRIGGER IF NOT EXISTS membership_ai_job_binding_identity BEFORE UPDATE OF id,owner,reserve_credits,policy_snapshot
 ON ai_gateway_jobs WHEN OLD.quota_source='membership_period'
 BEGIN SELECT RAISE(ABORT,'membership_ai_job_binding_immutable'); END;
"""

# All monetary/period table writes during streaming occur inside fixed database
# triggers caused by the original, narrowly authorized existing-job update.
LIVE = """EXISTS(SELECT 1 FROM membership_order_snapshots s
 JOIN membership_subscriptions sub ON sub.id=s.subscription_id AND sub.owner=s.owner
 JOIN commerce_orders o ON o.id=s.order_id AND o.owner=s.owner AND o.environment='sandbox'
 JOIN commerce_order_items i ON i.id=s.item_id AND i.order_id=o.id
 JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=s.owner AND e.environment='sandbox'
 JOIN commerce_payment_events pay ON pay.id=s.payment_event_id AND pay.order_id=o.id AND pay.owner=s.owner
 WHERE s.item_id=p.item_id AND s.owner=p.owner AND s.subscription_id=p.subscription_id
 AND s.environment='sandbox' AND s.state='active' AND sub.status IN ('active','renewal_failed','cancelled_active')
 AND i.type='membership' AND i.quantity=1 AND i.refunded_quantity=0 AND e.status='active' AND e.remaining=1
 AND o.payment_status IN ('paid','partially_refunded') AND pay.kind='sandbox_pay' AND pay.status='applied'
 AND pay.environment='sandbox' AND s.period_start<=NEW.created AND s.period_end>NEW.created
 AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=p.owner AND l.status='closed'))"""
CLOSING = """(p.status IN ('closing','closed') OR p.cycle_end<=NEW.updated
 OR EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=p.owner AND l.status='closed')
 OR NOT EXISTS(SELECT 1 FROM membership_order_snapshots s
 JOIN commerce_order_items i ON i.id=s.item_id JOIN commerce_orders o ON o.id=s.order_id
 JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=s.owner AND e.environment='sandbox'
 JOIN membership_subscriptions sub ON sub.id=s.subscription_id AND sub.owner=s.owner
 WHERE s.item_id=p.item_id AND s.owner=p.owner AND s.state='active' AND i.refunded_quantity=0
 AND o.payment_status IN ('paid','partially_refunded') AND e.status='active' AND e.remaining=1
 AND sub.status NOT IN ('expired','revoked')))"""

STICKY = """EXISTS(SELECT 1 FROM membership_order_snapshots s
 JOIN membership_subscriptions sub ON sub.id=s.subscription_id AND sub.owner=s.owner
 JOIN commerce_orders o ON o.id=s.order_id AND o.owner=s.owner AND o.environment='sandbox'
 JOIN commerce_order_items i ON i.id=s.item_id AND i.order_id=o.id AND i.type='membership' AND i.quantity=1
 JOIN commerce_payment_events pay ON pay.id=s.payment_event_id AND pay.order_id=o.id AND pay.owner=s.owner
 AND pay.kind='sandbox_pay' AND pay.status='applied' AND pay.environment='sandbox'
 WHERE s.owner=NEW.owner AND s.environment='sandbox' AND s.period_start<=NEW.created
 AND s.period_end>s.period_start AND json_type(s.data,'$.benefits.aiCredits')='integer'
 AND json_extract(s.data,'$.benefits.aiCredits')>=0
 AND json_extract(s.data,'$.benefits.aiResetCycle') IN ('month','year','billing_period'))"""


def install_wallet_routing(db):
    sticky = STICKY if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='membership_order_snapshots'").fetchone() else '0'
    db.executescript("""
DROP TRIGGER IF EXISTS ai_gateway_reserve_check;
CREATE TRIGGER ai_gateway_reserve_check BEFORE INSERT ON ai_gateway_jobs
WHEN NEW.quota_source='test_wallet' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM ai_gateway_wallets WHERE owner=NEW.owner AND balance-reserved>=NEW.reserve_credits)
 THEN RAISE(ABORT,'ai_gateway_insufficient_credits') END;
END;
DROP TRIGGER IF EXISTS ai_gateway_reserve;
CREATE TRIGGER ai_gateway_reserve AFTER INSERT ON ai_gateway_jobs WHEN NEW.quota_source='test_wallet' BEGIN
 UPDATE ai_gateway_wallets SET reserved=reserved+NEW.reserve_credits,updated=NEW.created WHERE owner=NEW.owner;
 INSERT INTO ai_gateway_quota_events VALUES('reserve:'||NEW.id,NEW.owner,NEW.id,'reserve',NEW.reserve_credits,json_extract(NEW.policy_snapshot,'$.ruleVersion'),NEW.created);
END;
DROP TRIGGER IF EXISTS ai_gateway_settle;
CREATE TRIGGER ai_gateway_settle AFTER UPDATE OF status ON ai_gateway_jobs
WHEN OLD.quota_source='test_wallet' AND OLD.status IN ('queued','running') AND NEW.status IN ('succeeded','failed','partial','cancelled') BEGIN
 UPDATE ai_gateway_wallets SET reserved=reserved-OLD.reserve_credits,balance=balance-NEW.charged_credits,updated=NEW.updated WHERE owner=NEW.owner;
 INSERT INTO ai_gateway_quota_events VALUES('settle:'||NEW.id,NEW.owner,NEW.id,'settle',NEW.charged_credits,json_extract(NEW.policy_snapshot,'$.ruleVersion'),NEW.updated);
END;
DROP TRIGGER IF EXISTS membership_ai_source_check;
CREATE TRIGGER membership_ai_source_check BEFORE INSERT ON ai_gateway_jobs BEGIN
 SELECT CASE WHEN NEW.quota_source NOT IN ('test_wallet','membership_period')
 OR (NEW.quota_source='test_wallet' AND NEW.quota_period_id!='')
 OR (NEW.quota_source='membership_period' AND NEW.quota_period_id='')
 THEN RAISE(ABORT,'membership_ai_unknown_source') END;
 SELECT CASE WHEN NEW.quota_source='test_wallet' AND """+sticky+"""
 THEN RAISE(ABORT,'membership_ai_wallet_fallback_denied') END;
END;
""")


def member_triggers():
    closing_update = CLOSING.replace('p.','membership_ai_periods.')
    return """
DROP TRIGGER IF EXISTS membership_ai_grant_check;
CREATE TRIGGER membership_ai_grant_check BEFORE INSERT ON membership_ai_periods BEGIN
 SELECT CASE WHEN NEW.status!='active' OR NEW.reason!='' OR NEW.reserved!=0 OR NEW.balance!=NEW.credits
 OR NEW.cycle_start>NEW.created OR NEW.cycle_end<=NEW.created OR NEW.updated!=NEW.created
 OR NOT EXISTS(SELECT 1 FROM settings WHERE key='membership_ai_quota' AND data=NEW.policy_snapshot
 AND json_extract(data,'$.enabled')=1 AND json_extract(data,'$.confirmed')=1
 AND json_extract(data,'$.environment')='sandbox' AND length(json_extract(data,'$.ruleVersion'))>0)
 OR NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.owner
 AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))
 OR NOT EXISTS(SELECT 1 FROM membership_order_snapshots s
 JOIN membership_subscriptions sub ON sub.id=s.subscription_id AND sub.owner=s.owner
 JOIN commerce_orders o ON o.id=s.order_id AND o.owner=s.owner AND o.environment='sandbox'
 JOIN commerce_order_items i ON i.id=s.item_id AND i.order_id=o.id AND i.type='membership' AND i.quantity=1
 JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=s.owner AND e.environment='sandbox'
 JOIN commerce_payment_events pay ON pay.id=s.payment_event_id AND pay.order_id=o.id AND pay.owner=s.owner
 WHERE s.item_id=NEW.item_id AND s.owner=NEW.owner AND s.subscription_id=NEW.subscription_id
 AND s.environment='sandbox' AND s.state='active' AND sub.status IN ('active','renewal_failed','cancelled_active')
 AND s.period_start<=NEW.cycle_start AND s.period_end>=NEW.cycle_end
 AND s.period_start<=NEW.created AND s.period_end>NEW.created AND i.refunded_quantity=0
 AND e.status='active' AND e.remaining=1 AND o.payment_status IN ('paid','partially_refunded')
 AND pay.kind='sandbox_pay' AND pay.status='applied' AND pay.environment='sandbox'
 AND json_type(s.data,'$.benefits.aiCredits')='integer' AND json_extract(s.data,'$.benefits.aiCredits')=NEW.credits
 AND json_extract(s.data,'$.benefits.aiResetCycle') IN ('month','year','billing_period')
 AND json(json_extract(s.data,'$.benefits'))=json(NEW.benefits_snapshot))
 THEN RAISE(ABORT,'membership_ai_grant_denied') END;
END;
DROP TRIGGER IF EXISTS membership_ai_reserve_check;
CREATE TRIGGER membership_ai_reserve_check BEFORE INSERT ON ai_gateway_jobs
WHEN NEW.quota_source='membership_period' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM membership_ai_allocations a
 JOIN membership_ai_periods p ON p.id=a.period_id AND p.owner=a.owner
 WHERE a.job_id=NEW.id AND a.owner=NEW.owner AND a.period_id=NEW.quota_period_id
 AND a.reserved_credits=NEW.reserve_credits AND a.state='reserved' AND a.charged_credits IS NULL
 AND p.status='active' AND p.credits>0 AND NEW.reserve_credits>0
 AND p.cycle_start<=NEW.created AND p.cycle_end>NEW.created AND p.balance-p.reserved>=NEW.reserve_credits
 AND EXISTS(SELECT 1 FROM settings WHERE key='membership_ai_quota'
 AND json_extract(data,'$.enabled')=1 AND json_extract(data,'$.confirmed')=1
 AND json_extract(data,'$.environment')='sandbox' AND length(json_extract(data,'$.ruleVersion'))>0)
 AND """+LIVE+""") THEN RAISE(ABORT,'membership_ai_reserve_denied') END;
END;
DROP TRIGGER IF EXISTS membership_ai_reserve;
CREATE TRIGGER membership_ai_reserve AFTER INSERT ON ai_gateway_jobs
WHEN NEW.quota_source='membership_period' BEGIN
 UPDATE membership_ai_periods SET reserved=reserved+NEW.reserve_credits,updated=NEW.created
 WHERE id=NEW.quota_period_id AND owner=NEW.owner;
 INSERT INTO membership_ai_events VALUES('reserve:'||NEW.id,NEW.owner,NEW.quota_period_id,NEW.id,'reserve',NEW.reserve_credits,NEW.created);
 INSERT INTO ai_gateway_quota_events VALUES('reserve:'||NEW.id,NEW.owner,NEW.id,'reserve',NEW.reserve_credits,json_extract(NEW.policy_snapshot,'$.ruleVersion'),NEW.created);
END;
DROP TRIGGER IF EXISTS membership_ai_settle_check;
CREATE TRIGGER membership_ai_settle_check BEFORE UPDATE OF status ON ai_gateway_jobs
WHEN OLD.quota_source='membership_period' AND OLD.status IN ('queued','running')
 AND NEW.status IN ('succeeded','failed','partial','cancelled') BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM membership_ai_allocations a
 JOIN membership_ai_periods p ON p.id=a.period_id AND p.owner=a.owner
 WHERE a.job_id=OLD.id AND a.owner=OLD.owner AND a.period_id=OLD.quota_period_id
 AND a.state='reserved' AND a.charged_credits IS NULL AND a.reserved_credits=OLD.reserve_credits
 AND NEW.id=OLD.id AND NEW.owner=OLD.owner AND NEW.reserve_credits=OLD.reserve_credits
 AND NEW.quota_source=OLD.quota_source AND NEW.quota_period_id=OLD.quota_period_id
 AND p.reserved>=OLD.reserve_credits AND NEW.charged_credits>=0
 AND NEW.charged_credits<=OLD.reserve_credits) THEN RAISE(ABORT,'membership_ai_settle_denied') END;
END;
DROP TRIGGER IF EXISTS membership_ai_settle;
CREATE TRIGGER membership_ai_settle AFTER UPDATE OF status ON ai_gateway_jobs
WHEN OLD.quota_source='membership_period' AND OLD.status IN ('queued','running')
 AND NEW.status IN ('succeeded','failed','partial','cancelled') BEGIN
 INSERT INTO membership_ai_events VALUES('settle:'||OLD.id,OLD.owner,OLD.quota_period_id,OLD.id,'settle',NEW.charged_credits,NEW.updated);
 INSERT INTO membership_ai_events
 SELECT 'release:'||OLD.id,OLD.owner,OLD.quota_period_id,OLD.id,'expire_unused',
 p.balance-p.reserved+OLD.reserve_credits-NEW.charged_credits,NEW.updated FROM membership_ai_periods p
 WHERE p.id=OLD.quota_period_id AND p.owner=OLD.owner AND """+CLOSING+"""
 AND p.balance-p.reserved+OLD.reserve_credits-NEW.charged_credits>0;
 UPDATE membership_ai_periods SET
 balance=CASE WHEN """+closing_update+""" THEN reserved-OLD.reserve_credits ELSE balance-NEW.charged_credits END,
 reserved=reserved-OLD.reserve_credits,
 status=CASE WHEN """+closing_update+""" THEN CASE WHEN reserved-OLD.reserve_credits=0 THEN 'closed' ELSE 'closing' END ELSE status END,
 reason=CASE WHEN """+closing_update+""" THEN 'inactive_or_expired' ELSE reason END,updated=NEW.updated
 WHERE id=OLD.quota_period_id AND owner=OLD.owner;
 UPDATE membership_ai_allocations SET state='settled',charged_credits=NEW.charged_credits,updated=NEW.updated
 WHERE job_id=OLD.id AND owner=OLD.owner AND period_id=OLD.quota_period_id AND state='reserved';
 INSERT INTO ai_gateway_quota_events VALUES('settle:'||OLD.id,OLD.owner,OLD.id,'settle',NEW.charged_credits,json_extract(NEW.policy_snapshot,'$.ruleVersion'),NEW.updated);
END;
"""


def now():
    return time.time_ns()//1_000_000


def dump(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def init_schema(db):
    db.executescript(DDL)
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='membership_order_snapshots'").fetchone():
        db.executescript(member_triggers())


def policy(db):
    row = db.execute("SELECT data FROM settings WHERE key='membership_ai_quota'").fetchone()
    return {**copy.deepcopy(DEFAULT),**(json.loads(row['data']) if row else {})}


def ready(value):
    return value.get('enabled') is True and value.get('confirmed') is True and bool(value.get('ruleVersion')) and all(value.get(key)==expected for key,expected in FIXED.items())


def add_months(stamp,months):
    date = datetime.fromtimestamp(stamp/1000,timezone.utc)
    year,month = divmod(date.year*12+date.month-1+months,12)
    month += 1
    return int(date.replace(year=year,month=month,day=min(date.day,calendar.monthrange(year,month)[1])).timestamp()*1000)


def bounds(start,end,cycle,stamp):
    if cycle=='billing_period':
        return start,end
    # Every boundary is recomputed from the original paid anchor, so Jan31 and
    # leap-day clamping never drift through a succession of shorter months.
    unit = 12 if cycle=='year' else 1
    moment = min(max(stamp,start),end-1)
    anchor,current = datetime.fromtimestamp(start/1000,timezone.utc),datetime.fromtimestamp(moment/1000,timezone.utc)
    offset = max(0,((current.year-anchor.year)*12+current.month-anchor.month)//unit)
    while offset>0 and add_months(start,offset*unit)>moment:
        offset -= 1
    while add_months(start,(offset+1)*unit)<=moment:
        offset += 1
    return add_months(start,offset*unit),min(end,add_months(start,(offset+1)*unit))


def facts(db,owner,stamp):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='membership_order_snapshots'").fetchone():
        return []
    rows = db.execute("""SELECT s.*,sub.status subscription_status,i.refunded_quantity,
        o.payment_status,e.status entitlement_status,e.remaining
        FROM membership_order_snapshots s
        JOIN membership_subscriptions sub ON sub.id=s.subscription_id AND sub.owner=s.owner
        JOIN commerce_orders o ON o.id=s.order_id AND o.owner=s.owner AND o.environment='sandbox'
        JOIN commerce_order_items i ON i.id=s.item_id AND i.order_id=o.id AND i.type='membership' AND i.quantity=1
        JOIN commerce_entitlements e ON e.item_id=i.id AND e.owner=s.owner AND e.environment='sandbox'
        JOIN commerce_payment_events pay ON pay.id=s.payment_event_id AND pay.order_id=o.id AND pay.owner=s.owner
        AND pay.kind='sandbox_pay' AND pay.status='applied' AND pay.environment='sandbox'
        WHERE s.owner=? AND s.environment='sandbox' AND s.subscription_id IS NOT NULL
        AND s.period_start<=? AND s.period_end>s.period_start""",(owner,stamp)).fetchall()
    result = []
    for row in rows:
        terms = json.loads(row['data']);benefits = terms.get('benefits',{})
        credits,cycle = benefits.get('aiCredits'),benefits.get('aiResetCycle')
        if type(credits) is not int or not 0<=credits<=1_000_000 or cycle not in ('month','year','billing_period'):
            continue
        value = dict(row)
        value.update(credits=credits,reset_cycle=cycle,benefits=benefits)
        value['cycle_start'],value['cycle_end'] = bounds(row['period_start'],row['period_end'],cycle,stamp)
        value['valid'] = row['state']=='active' and row['payment_status'] in ('paid','partially_refunded') and row['refunded_quantity']==0 and row['entitlement_status']=='active' and row['remaining']==1
        value['current'] = value['valid'] and row['subscription_status'] in ALLOWED_STATES and row['period_start']<=stamp<row['period_end']
        result.append(value)
    return sorted(result,key=lambda row:(row['cycle_end'],row['item_id']))


def active_owner(db,owner):
    return bool(db.execute("SELECT 1 FROM users u WHERE u.id=? AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')",(owner,)).fetchone())


def sync_owner(db,owner,stamp,grant=False):
    config = policy(db)
    sources = facts(db,owner,stamp)
    by_item = {item['item_id']:item for item in sources}
    for period in db.execute('SELECT * FROM membership_ai_periods WHERE owner=?',(owner,)).fetchall():
        source = by_item.get(period['item_id'])
        closing = period['status'] in ('closing','closed') or stamp>=period['cycle_end'] or not active_owner(db,owner) or not source or not source['valid'] or source['subscription_status'] in ('expired','revoked')
        if closing:
            if period['status']=='closed':
                continue
            expired = period['balance']-period['reserved']
            if expired:
                db.execute('INSERT OR IGNORE INTO membership_ai_events VALUES(?,?,?,?,?,?,?)',('close:'+period['id'],owner,period['id'],'','expire_unused',expired,stamp))
            db.execute("UPDATE membership_ai_periods SET balance=reserved,status=CASE WHEN reserved=0 THEN 'closed' ELSE 'closing' END,reason='inactive_or_expired',updated=? WHERE id=? AND owner=?",(stamp,period['id'],owner))
        else:
            frozen = not ready(config) or source['subscription_status'] not in ALLOWED_STATES
            state,reason = ('frozen','policy_disabled' if not ready(config) else 'paused_or_grace') if frozen else ('active','')
            if period['status']!=state or period['reason']!=reason:
                db.execute('UPDATE membership_ai_periods SET status=?,reason=?,updated=? WHERE id=? AND owner=? AND status IN (\'active\',\'frozen\')',(state,reason,stamp,period['id'],owner))
    if grant and ready(config) and active_owner(db,owner):
        for source in sources:
            if not source['current']:
                continue
            period_id = 'mai:'+hashlib.sha256(dump([owner,source['item_id'],source['cycle_start']]).encode('utf-8')).hexdigest()
            old = db.execute('SELECT id FROM membership_ai_periods WHERE owner=? AND item_id=? AND cycle_start=?',(owner,source['item_id'],source['cycle_start'])).fetchone()
            if old:
                continue
            db.execute('INSERT INTO membership_ai_periods VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (period_id,owner,source['subscription_id'],source['item_id'],source['cycle_start'],source['cycle_end'],source['credits'],source['credits'],0,'active','',dump(config),dump(source['benefits']),stamp,stamp))
            db.execute('INSERT INTO membership_ai_events VALUES(?,?,?,?,?,?,?)',('grant:'+period_id,owner,period_id,'','grant',source['credits'],stamp))
    return sources


def view(db,owner,stamp):
    config = policy(db);sources = facts(db,owner,stamp)
    result = {'enabled':config['enabled'],'confirmed':config['confirmed'],'ruleVersion':config['ruleVersion'],
        'environment':'sandbox','applicable':bool(sources),'quotaSource':'membership_period' if sources else 'test_wallet',
        'periodId':'','status':'disabled' if not ready(config) else 'not_applicable','credits':0,'balance':0,'reserved':0,
        'available':0,'cycleStart':0,'cycleEnd':0,'resetCycle':'none','subscriptionId':'','itemId':'',
        'grantPending':False,'postExpiryWalletPolicy':'no_automatic_fallback','productionEnabled':False}
    if not sources:
        return result
    current = [source for source in sources if source['current']]
    chosen = current[0] if current else max(sources,key=lambda row:(row['period_start'],row['item_id']))
    options = []
    for source in current:
        period = db.execute('SELECT * FROM membership_ai_periods WHERE owner=? AND item_id=? AND cycle_start=?',(owner,source['item_id'],source['cycle_start'])).fetchone()
        options.append((source,period))
    preferred = next(((source,period) for source,period in options if source['credits']>0 and (period is None or period['balance']-period['reserved']>0)),None)
    period = None
    if preferred:
        chosen,period = preferred
    else:
        period = db.execute('SELECT * FROM membership_ai_periods WHERE owner=? AND item_id=? AND cycle_start=?',(owner,chosen['item_id'],chosen['cycle_start'])).fetchone()
    result.update(credits=chosen['credits'],cycleStart=chosen['cycle_start'],cycleEnd=chosen['cycle_end'],
        resetCycle=chosen['reset_cycle'],subscriptionId=chosen['subscription_id'],itemId=chosen['item_id'])
    if period:
        result.update(periodId=period['id'],balance=period['balance'],reserved=period['reserved'])
        closing = period['status'] in ('closing','closed') or stamp>=period['cycle_end'] or not chosen['valid'] or chosen['subscription_status'] in ('expired','revoked') or not active_owner(db,owner)
        state = ('closing' if period['reserved'] else 'closed') if closing else 'disabled' if not ready(config) else 'frozen' if not chosen['current'] else 'active'
        available = period['balance']-period['reserved'] if state=='active' else 0
        result.update(status='exhausted' if state=='active' and available==0 else state,available=available)
    elif chosen['current'] and ready(config) and active_owner(db,owner):
        result.update(status='ready',grantPending=True)
    else:
        result['status'] = 'disabled' if not ready(config) else 'frozen' if chosen['valid'] and stamp<chosen['period_end'] else 'closed'
    return result


def allocate(db,owner,job_id,reserve,stamp,error):
    sources = sync_owner(db,owner,stamp,grant=True)
    if not sources:
        return 'test_wallet',''
    if not ready(policy(db)):
        raise error(503,'会员AI额度策略尚未启用；不会改扣独立测试余额。')
    if reserve<=0:
        raise error(503,'会员AI请求须有明确的正数预留扣次规则。')
    candidates = db.execute("SELECT * FROM membership_ai_periods WHERE owner=? AND status='active' AND cycle_start<=? AND cycle_end>? AND balance-reserved>=? AND credits>0 ORDER BY cycle_end,item_id,id",(owner,stamp,stamp,reserve)).fetchall()
    current_items = {source['item_id'] for source in sources if source['current']}
    period = next((candidate for candidate in candidates if candidate['item_id'] in current_items),None)
    if period is None:
        raise error(402,'会员当前周期额度不足或已失效；不会改扣独立测试余额。')
    db.execute('INSERT INTO membership_ai_allocations VALUES(?,?,?,?,?,?,?,?)',(job_id,owner,period['id'],reserve,None,'reserved',stamp,stamp))
    return 'membership_period',period['id']


class MembershipAIQuota:
    def __init__(self,store,handler,error,rate,*,test_clock=None):
        self.store,self.h,self.Error,self.rate = store,handler,error,rate
        self.clock = test_clock or now

    def fail(self,status,message):
        raise self.Error(status,message)

    def route(self,method,path):
        public,admin = '/api/membership/ai-quota','/api/admin/membership-ai-quota'
        if path not in (public,public+'/refresh',admin):
            return None
        actor = self.h.require(['admin'] if path==admin else None)['id']
        self.rate('membership-ai-quota:'+('read:' if method=='GET' else 'write:')+actor,180 if method=='GET' else 30)
        with self.store.connect() as db:
            if path==admin and method=='GET':
                return {'policy':policy(db),'productionEnabled':False}
            if path==admin and method=='PATCH':
                data = self.h.body()
                if set(data)!=set(DEFAULT) or type(data.get('revision')) is not int or type(data.get('enabled')) is not bool or type(data.get('confirmed')) is not bool or not isinstance(data.get('ruleVersion'),str) or len(data['ruleVersion'])>100 or any(data.get(key)!=value for key,value in FIXED.items()):
                    self.fail(400,'会员AI策略字段无效，必须明确固定的沙箱规则。')
                if data['enabled'] and (not data['confirmed'] or not data['ruleVersion'].strip()):
                    self.fail(400,'启用前须明确确认规则并填写版本。')
                db.execute('BEGIN IMMEDIATE')
                current = policy(db)
                if data['revision']!=current['revision']:
                    self.fail(409,'额度策略已更新，请刷新。')
                clean = {**data,'ruleVersion':data['ruleVersion'].strip(),'revision':current['revision']+1}
                db.execute("INSERT INTO settings VALUES('membership_ai_quota',?) ON CONFLICT(key) DO UPDATE SET data=excluded.data",(dump(clean),))
                self.store.audit(db,actor,'membership_ai.policy','sandbox','finite sandbox policy; production disabled')
                return {'policy':clean,'productionEnabled':False}
            if path==public and method=='GET':
                return {'membershipQuota':view(db,actor,self.clock()),'productionEnabled':False}
            if path==public+'/refresh' and method=='POST':
                if self.h.body():
                    self.fail(400,'额度刷新不接受客户端金额、周期或余额。')
                db.execute('BEGIN IMMEDIATE')
                sync_owner(db,actor,self.clock(),grant=True)
                return {'membershipQuota':view(db,actor,self.clock()),'productionEnabled':False}
        self.fail(405,'不支持的会员额度操作。')
