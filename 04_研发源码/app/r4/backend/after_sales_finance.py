"""Explicit sandbox after-sales money attribution. Never creates refunds or touches original financial facts."""
import hashlib
import json
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

MAX_MINOR = 1_000_000_000
DDL = r'''
CREATE TABLE IF NOT EXISTS after_sales_finance_heads(case_id TEXT PRIMARY KEY REFERENCES after_sales_cases(id),owner TEXT NOT NULL,order_id TEXT NOT NULL REFERENCES commerce_orders(id),environment TEXT NOT NULL CHECK(environment='sandbox'),currency TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 0 CHECK(typeof(version)='integer' AND version>=0),approval_id TEXT,last_action TEXT,created INTEGER NOT NULL,updated INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS after_sales_finance_actions(id TEXT PRIMARY KEY,case_id TEXT NOT NULL REFERENCES after_sales_finance_heads(case_id),owner TEXT NOT NULL,actor TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),currency TEXT NOT NULL,request_id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('approve','link','reverse')),expected_version INTEGER NOT NULL CHECK(typeof(expected_version)='integer' AND expected_version>=0),fingerprint TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(actor,environment,request_id));
CREATE INDEX IF NOT EXISTS after_sales_finance_actions_case ON after_sales_finance_actions(case_id,created,id);
CREATE TABLE IF NOT EXISTS after_sales_finance_targets(approval_id TEXT NOT NULL REFERENCES after_sales_finance_actions(id),case_item_id TEXT NOT NULL REFERENCES after_sales_items(id),case_id TEXT NOT NULL,owner TEXT NOT NULL,approved_minor INTEGER CHECK(approved_minor IS NULL OR (typeof(approved_minor)='integer' AND approved_minor>=0 AND approved_minor<=1000000000)),PRIMARY KEY(approval_id,case_item_id));
CREATE TABLE IF NOT EXISTS after_sales_finance_links(id TEXT PRIMARY KEY,action_id TEXT NOT NULL REFERENCES after_sales_finance_actions(id),case_id TEXT NOT NULL,case_item_id TEXT NOT NULL REFERENCES after_sales_items(id),owner TEXT NOT NULL,environment TEXT NOT NULL CHECK(environment='sandbox'),currency TEXT NOT NULL,refund_event_id TEXT NOT NULL REFERENCES commerce_payment_events(id),order_item_id TEXT NOT NULL REFERENCES commerce_order_items(id),amount_minor INTEGER NOT NULL CHECK(typeof(amount_minor)='integer' AND amount_minor>0 AND amount_minor<=1000000000),created INTEGER NOT NULL,UNIQUE(action_id,case_item_id));
CREATE INDEX IF NOT EXISTS after_sales_finance_links_event ON after_sales_finance_links(refund_event_id,order_item_id);
CREATE INDEX IF NOT EXISTS after_sales_finance_links_case ON after_sales_finance_links(case_id,case_item_id);
CREATE TABLE IF NOT EXISTS after_sales_finance_reversals(id TEXT PRIMARY KEY,action_id TEXT NOT NULL REFERENCES after_sales_finance_actions(id),link_id TEXT NOT NULL REFERENCES after_sales_finance_links(id),case_id TEXT NOT NULL,owner TEXT NOT NULL,amount_minor INTEGER NOT NULL CHECK(typeof(amount_minor)='integer' AND amount_minor>0 AND amount_minor<=1000000000),created INTEGER NOT NULL,UNIQUE(action_id,link_id));
CREATE INDEX IF NOT EXISTS after_sales_finance_reversals_link ON after_sales_finance_reversals(link_id);
CREATE VIEW IF NOT EXISTS after_sales_finance_balances AS SELECT l.*,l.amount_minor-coalesce((SELECT sum(r.amount_minor) FROM after_sales_finance_reversals r WHERE r.link_id=l.id),0) AS net_minor FROM after_sales_finance_links l;

CREATE VIEW IF NOT EXISTS after_sales_finance_valid_refunds AS
 SELECT e.* FROM commerce_payment_events e JOIN commerce_orders o ON o.id=e.order_id AND o.owner=e.owner AND o.environment=e.environment AND o.currency=e.currency
 WHERE e.kind='refund' AND e.environment='sandbox' AND e.status='applied' AND typeof(e.amount_minor)='integer' AND e.amount_minor BETWEEN 0 AND 1000000000
 AND o.payment_status IN ('paid','partially_refunded','refunded')
 AND EXISTS(SELECT 1 FROM commerce_payment_events p WHERE p.order_id=o.id AND p.owner=o.owner AND p.environment=o.environment AND p.kind='sandbox_pay' AND p.status='applied' AND p.currency=o.currency AND p.amount_minor=o.total_minor)
 AND json_valid(e.items) AND json_type(CASE WHEN json_valid(e.items) THEN e.items ELSE '[]' END)='array' AND json_array_length(CASE WHEN json_valid(e.items) THEN e.items ELSE '[]' END) BETWEEN 1 AND 30
 AND NOT EXISTS(SELECT 1 FROM json_each(CASE WHEN json_valid(e.items) THEN e.items ELSE '[]' END) j LEFT JOIN commerce_order_items i ON i.id=json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.itemId') AND i.order_id=e.order_id WHERE j.type!='object' OR i.id IS NULL OR i.currency!=e.currency OR json_type(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.quantity') IS NOT 'integer' OR json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.quantity')<1 OR json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.quantity')>i.quantity OR typeof(i.price_minor)!='integer' OR typeof(i.unit_shipping_minor)!='integer' OR typeof(i.unit_tax_minor)!='integer' OR i.price_minor<0 OR i.unit_shipping_minor<0 OR i.unit_tax_minor<0)
 AND (SELECT count(*) FROM json_each(CASE WHEN json_valid(e.items) THEN e.items ELSE '[]' END))=(SELECT count(DISTINCT json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.itemId')) FROM json_each(CASE WHEN json_valid(e.items) THEN e.items ELSE '[]' END) j)
 AND e.amount_minor=(SELECT sum(json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.quantity')*(i.price_minor+i.unit_shipping_minor+i.unit_tax_minor)) FROM json_each(CASE WHEN json_valid(e.items) THEN e.items ELSE '[]' END) j JOIN commerce_order_items i ON i.id=json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.itemId') AND i.order_id=e.order_id);
CREATE VIEW IF NOT EXISTS after_sales_finance_refund_items AS SELECT e.id AS refund_event_id,e.owner,e.environment,e.currency,e.order_id,e.amount_minor AS event_minor,e.created,json_extract(j.value,'$.itemId') AS order_item_id,json_extract(j.value,'$.quantity') AS refunded_quantity,json_extract(j.value,'$.quantity')*(i.price_minor+i.unit_shipping_minor+i.unit_tax_minor) AS item_minor FROM after_sales_finance_valid_refunds e JOIN json_each(CASE WHEN json_valid(e.items) THEN e.items ELSE '[]' END) j JOIN commerce_order_items i ON i.id=json_extract(CASE WHEN j.type='object' THEN j.value ELSE '{}' END,'$.itemId') AND i.order_id=e.order_id;

CREATE TRIGGER IF NOT EXISTS after_sales_finance_head_check BEFORE INSERT ON after_sales_finance_heads BEGIN
 SELECT CASE WHEN NEW.version!=0 OR NEW.approval_id IS NOT NULL OR NEW.last_action IS NOT NULL OR NOT EXISTS(SELECT 1 FROM after_sales_cases c JOIN commerce_orders o ON o.id=c.order_id WHERE c.id=NEW.case_id AND c.owner=NEW.owner AND c.order_id=NEW.order_id AND c.environment=NEW.environment AND o.owner=NEW.owner AND o.environment=NEW.environment AND o.currency=NEW.currency) THEN RAISE(ABORT,'after_sales_finance_case_mismatch') END;
END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_head_update BEFORE UPDATE ON after_sales_finance_heads BEGIN
 SELECT CASE WHEN NEW.case_id!=OLD.case_id OR NEW.owner!=OLD.owner OR NEW.order_id!=OLD.order_id OR NEW.environment!=OLD.environment OR NEW.currency!=OLD.currency OR NEW.created!=OLD.created OR NEW.version!=OLD.version+1 OR NOT EXISTS(SELECT 1 FROM after_sales_finance_actions a WHERE a.id=NEW.last_action AND a.case_id=OLD.case_id AND a.expected_version=OLD.version) THEN RAISE(ABORT,'after_sales_finance_immutable_head') END;
END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_action_check BEFORE INSERT ON after_sales_finance_actions BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.actor AND role='admin') OR EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.actor AND status='closed') THEN RAISE(ABORT,'after_sales_finance_admin_required') END;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM after_sales_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1) OR NOT EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1) THEN RAISE(ABORT,'after_sales_finance_disabled') END;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM after_sales_finance_heads h JOIN after_sales_cases c ON c.id=h.case_id JOIN commerce_orders o ON o.id=c.order_id WHERE h.case_id=NEW.case_id AND h.owner=NEW.owner AND h.environment=NEW.environment AND h.currency=NEW.currency AND h.version=NEW.expected_version AND c.owner=h.owner AND c.environment=h.environment AND c.order_id=h.order_id AND c.state IN ('accepted','returning','partially_received','received') AND o.owner=h.owner AND o.environment=h.environment AND o.currency=h.currency AND EXISTS(SELECT 1 FROM commerce_payment_events p WHERE p.order_id=o.id AND p.owner=o.owner AND p.environment=o.environment AND p.kind='sandbox_pay' AND p.status='applied' AND p.currency=o.currency AND p.amount_minor=o.total_minor)) THEN RAISE(ABORT,'after_sales_finance_stale_case') END;
 SELECT CASE WHEN NOT json_valid(NEW.data) OR json_type(NEW.data)!='object' OR json_type(NEW.data,'$.reason') IS NOT 'text' OR length(trim(json_extract(NEW.data,'$.reason')))<1 OR json_type(NEW.data,'$.items') IS NOT 'array' OR json_array_length(NEW.data,'$.items') NOT BETWEEN 1 AND 30 THEN RAISE(ABORT,'after_sales_finance_invalid_payload') END;
 SELECT CASE WHEN NEW.kind='approve' AND (json_type(NEW.data,'$.ruleLabel') IS NOT 'text' OR length(trim(json_extract(NEW.data,'$.ruleLabel')))<1 OR json_array_length(NEW.data,'$.items')!=(SELECT count(*) FROM after_sales_items WHERE case_id=NEW.case_id) OR EXISTS(SELECT 1 FROM json_each(NEW.data,'$.items') j LEFT JOIN after_sales_items x ON x.id=json_extract(j.value,'$.caseItemId') AND x.case_id=NEW.case_id WHERE x.id IS NULL OR (json_type(j.value,'$.approvedMinor') IS NULL OR json_type(j.value,'$.approvedMinor') NOT IN ('integer','null'))) OR (SELECT count(DISTINCT json_extract(value,'$.caseItemId')) FROM json_each(NEW.data,'$.items'))!=json_array_length(NEW.data,'$.items')) THEN RAISE(ABORT,'after_sales_finance_invalid_approval') END;
 SELECT CASE WHEN NEW.kind='link' AND (json_extract(NEW.data,'$.approvalId') IS NULL OR json_extract(NEW.data,'$.approvalId')!=(SELECT approval_id FROM after_sales_finance_heads WHERE case_id=NEW.case_id) OR NOT EXISTS(SELECT 1 FROM after_sales_finance_valid_refunds e JOIN after_sales_finance_heads h ON h.order_id=e.order_id AND h.owner=e.owner AND h.currency=e.currency AND h.environment=e.environment WHERE h.case_id=NEW.case_id AND e.id=json_extract(NEW.data,'$.refundEventId')) OR (SELECT count(DISTINCT json_extract(value,'$.caseItemId')) FROM json_each(NEW.data,'$.items'))!=json_array_length(NEW.data,'$.items')) THEN RAISE(ABORT,'after_sales_finance_refund_source') END;
 SELECT CASE WHEN NEW.kind='reverse' AND (SELECT count(DISTINCT json_extract(value,'$.linkId')) FROM json_each(NEW.data,'$.items'))!=json_array_length(NEW.data,'$.items') THEN RAISE(ABORT,'after_sales_finance_invalid_reversal') END;
END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_target_check BEFORE INSERT ON after_sales_finance_targets BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM after_sales_finance_actions a JOIN after_sales_items x ON x.case_id=a.case_id JOIN commerce_order_items i ON i.id=x.order_item_id JOIN json_each(a.data,'$.items') j ON json_extract(j.value,'$.caseItemId')=x.id WHERE a.id=NEW.approval_id AND a.kind='approve' AND a.case_id=NEW.case_id AND a.owner=NEW.owner AND x.id=NEW.case_item_id AND json_extract(j.value,'$.approvedMinor') IS NEW.approved_minor AND (NEW.approved_minor IS NULL OR NEW.approved_minor<=x.quantity*(i.price_minor+i.unit_shipping_minor+i.unit_tax_minor))) THEN RAISE(ABORT,'after_sales_finance_target_mismatch') END;
 SELECT CASE WHEN (NEW.approved_minor IS NULL AND EXISTS(SELECT 1 FROM after_sales_finance_balances WHERE case_item_id=NEW.case_item_id AND net_minor>0)) OR (NEW.approved_minor IS NOT NULL AND NEW.approved_minor<coalesce((SELECT sum(net_minor) FROM after_sales_finance_balances WHERE case_item_id=NEW.case_item_id),0)) THEN RAISE(ABORT,'after_sales_finance_target_below_links') END;
END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_link_check BEFORE INSERT ON after_sales_finance_links BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM after_sales_finance_actions a JOIN after_sales_finance_heads h ON h.case_id=a.case_id JOIN after_sales_items x ON x.case_id=a.case_id JOIN after_sales_finance_targets t ON t.approval_id=h.approval_id AND t.case_item_id=x.id JOIN json_each(a.data,'$.items') j ON json_extract(j.value,'$.caseItemId')=x.id WHERE a.id=NEW.action_id AND a.kind='link' AND a.case_id=NEW.case_id AND a.owner=NEW.owner AND a.environment=NEW.environment AND a.currency=NEW.currency AND x.id=NEW.case_item_id AND x.order_item_id=NEW.order_item_id AND json_extract(a.data,'$.refundEventId')=NEW.refund_event_id AND json_type(j.value,'$.amountMinor')='integer' AND json_extract(j.value,'$.amountMinor')=NEW.amount_minor AND t.approved_minor>0 AND NEW.amount_minor+coalesce((SELECT sum(net_minor) FROM after_sales_finance_balances WHERE case_item_id=x.id),0)<=t.approved_minor) THEN RAISE(ABORT,'after_sales_finance_case_capacity') END;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM after_sales_finance_refund_items e JOIN after_sales_finance_heads h ON h.order_id=e.order_id WHERE h.case_id=NEW.case_id AND e.refund_event_id=NEW.refund_event_id AND e.order_item_id=NEW.order_item_id AND e.owner=NEW.owner AND e.environment=NEW.environment AND e.currency=NEW.currency AND NEW.amount_minor+coalesce((SELECT sum(net_minor) FROM after_sales_finance_balances WHERE refund_event_id=e.refund_event_id AND order_item_id=e.order_item_id),0)<=e.item_minor AND NEW.amount_minor+coalesce((SELECT sum(net_minor) FROM after_sales_finance_balances WHERE refund_event_id=e.refund_event_id),0)<=e.event_minor) THEN RAISE(ABORT,'after_sales_finance_event_capacity') END;
END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_reversal_check BEFORE INSERT ON after_sales_finance_reversals BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM after_sales_finance_actions a JOIN after_sales_finance_balances l ON l.case_id=a.case_id JOIN json_each(a.data,'$.items') j ON json_extract(j.value,'$.linkId')=l.id WHERE a.id=NEW.action_id AND a.kind='reverse' AND a.case_id=NEW.case_id AND a.owner=NEW.owner AND l.id=NEW.link_id AND l.owner=NEW.owner AND json_type(j.value,'$.amountMinor')='integer' AND json_extract(j.value,'$.amountMinor')=NEW.amount_minor AND NEW.amount_minor<=l.net_minor AND EXISTS(SELECT 1 FROM after_sales_finance_valid_refunds e WHERE e.id=l.refund_event_id AND e.order_id=(SELECT order_id FROM after_sales_finance_heads WHERE case_id=NEW.case_id) AND e.owner=l.owner AND e.environment=l.environment AND e.currency=l.currency)) THEN RAISE(ABORT,'after_sales_finance_reversal_capacity') END;
END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_action_apply AFTER INSERT ON after_sales_finance_actions BEGIN
 INSERT INTO after_sales_finance_targets SELECT NEW.id,json_extract(j.value,'$.caseItemId'),NEW.case_id,NEW.owner,json_extract(j.value,'$.approvedMinor') FROM json_each(NEW.data,'$.items') j WHERE NEW.kind='approve';
 INSERT INTO after_sales_finance_links SELECT 'link:'||NEW.id||':'||x.id,NEW.id,NEW.case_id,x.id,NEW.owner,NEW.environment,NEW.currency,json_extract(NEW.data,'$.refundEventId'),x.order_item_id,json_extract(j.value,'$.amountMinor'),NEW.created FROM json_each(NEW.data,'$.items') j JOIN after_sales_items x ON x.id=json_extract(j.value,'$.caseItemId') AND x.case_id=NEW.case_id WHERE NEW.kind='link';
 SELECT CASE WHEN NEW.kind='link' AND (SELECT count(*) FROM after_sales_finance_links WHERE action_id=NEW.id)!=json_array_length(NEW.data,'$.items') THEN RAISE(ABORT,'after_sales_finance_missing_link_item') END;
 INSERT INTO after_sales_finance_reversals SELECT 'reverse:'||NEW.id||':'||json_extract(j.value,'$.linkId'),NEW.id,json_extract(j.value,'$.linkId'),NEW.case_id,NEW.owner,json_extract(j.value,'$.amountMinor'),NEW.created FROM json_each(NEW.data,'$.items') j WHERE NEW.kind='reverse';
 UPDATE after_sales_finance_heads SET version=version+1,approval_id=CASE WHEN NEW.kind='approve' THEN NEW.id ELSE approval_id END,last_action=NEW.id,updated=NEW.created WHERE case_id=NEW.case_id;
END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_heads_no_delete BEFORE DELETE ON after_sales_finance_heads BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_actions_no_update BEFORE UPDATE ON after_sales_finance_actions BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_actions_no_delete BEFORE DELETE ON after_sales_finance_actions BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_targets_no_update BEFORE UPDATE ON after_sales_finance_targets BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_targets_no_delete BEFORE DELETE ON after_sales_finance_targets BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_links_no_update BEFORE UPDATE ON after_sales_finance_links BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_links_no_delete BEFORE DELETE ON after_sales_finance_links BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_reversals_no_update BEFORE UPDATE ON after_sales_finance_reversals BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
CREATE TRIGGER IF NOT EXISTS after_sales_finance_reversals_no_delete BEFORE DELETE ON after_sales_finance_reversals BEGIN SELECT RAISE(ABORT,'after_sales_finance_immutable'); END;
'''

def init_schema(db):
    for name in ('commerce_payment_events', 'after_sales_cases', 'account_lifecycle'):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone():
            raise RuntimeError('Initialize required active dependency before after-sales finance: ' + name)
    db.executescript(DDL)

def stamp():
    return time.time_ns() // 1_000_000

def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def fingerprint(value):
    return hashlib.sha256(dump(value).encode('utf-8')).hexdigest()

# One statement returns one consistent financial projection; GET never calls mutable commerce serializers.
READ_CASE_SQL = r'''
SELECT c.id,c.owner,c.order_id,c.type,c.state,c.rule_version,o.currency,o.payment_status,o.fulfillment_status,o.total_minor,o.refunded_minor,
coalesce(h.version,0) AS finance_version,h.approval_id,h.last_action,h.updated AS finance_updated,
(SELECT json_group_array(json_object('id',x.id,'itemId',x.order_item_id,'quantity',x.quantity,'receivedQuantity',x.received_quantity,'restockedQuantity',x.restocked_quantity,'snapshot',x.snapshot_data,'grossCapMinor',x.quantity*(i.price_minor+i.unit_shipping_minor+i.unit_tax_minor))) FROM after_sales_items x JOIN commerce_order_items i ON i.id=x.order_item_id WHERE x.case_id=c.id) AS items_json,
(SELECT json_group_array(json_object('id',a.id,'kind',a.kind,'actorId',a.actor,'version',a.expected_version+1,'data',a.data,'created',a.created)) FROM after_sales_finance_actions a WHERE a.case_id=c.id) AS actions_json,
(SELECT json_group_array(json_object('approvalId',t.approval_id,'caseItemId',t.case_item_id,'approvedMinor',t.approved_minor)) FROM after_sales_finance_targets t WHERE t.case_id=c.id) AS targets_json,
(SELECT json_group_array(json_object('id',l.id,'actionId',l.action_id,'refundEventId',l.refund_event_id,'caseItemId',l.case_item_id,'itemId',l.order_item_id,'amountMinor',l.amount_minor,'netMinor',l.net_minor,'created',l.created)) FROM after_sales_finance_balances l WHERE l.case_id=c.id) AS links_json,
(SELECT json_group_array(json_object('id',r.id,'actionId',r.action_id,'linkId',r.link_id,'amountMinor',r.amount_minor,'created',r.created)) FROM after_sales_finance_reversals r WHERE r.case_id=c.id) AS reversals_json
FROM after_sales_cases c JOIN commerce_orders o ON o.id=c.order_id AND o.owner=c.owner AND o.environment=c.environment
LEFT JOIN after_sales_finance_heads h ON h.case_id=c.id WHERE c.id=? AND c.environment='sandbox'
'''

EVENTS_SQL = r'''
SELECT e.id,e.amount_minor,e.currency,e.status,e.created,CASE WHEN v.id IS NOT NULL THEN 1 ELSE 0 END AS reliable,
CASE WHEN v.id IS NOT NULL THEN e.amount_minor-coalesce((SELECT sum(net_minor) FROM after_sales_finance_balances WHERE refund_event_id=e.id),0) ELSE NULL END AS available_minor,
(SELECT json_group_array(json_object('caseItemId',x.id,'itemId',x.order_item_id,'capacityMinor',f.item_minor,'availableMinor',f.item_minor-coalesce((SELECT sum(net_minor) FROM after_sales_finance_balances WHERE refund_event_id=e.id AND order_item_id=x.order_item_id),0))) FROM after_sales_items x JOIN after_sales_finance_refund_items f ON f.refund_event_id=e.id AND f.order_item_id=x.order_item_id WHERE x.case_id=c.id) AS items_json
FROM after_sales_cases c JOIN commerce_orders o ON o.id=c.order_id AND o.owner=c.owner AND o.environment=c.environment
JOIN commerce_payment_events e ON e.order_id=o.id AND e.owner=o.owner AND e.environment=o.environment AND e.currency=o.currency AND e.kind='refund' AND e.status='applied'
LEFT JOIN after_sales_finance_valid_refunds v ON v.id=e.id WHERE c.id=? AND c.environment='sandbox' ORDER BY e.created,e.id
'''

def project_case_finance(row, admin=False):
    actions = sorted(json.loads(row['actions_json']), key=lambda x: (x['version'], x['id']))
    for action in actions:
        action['data'] = json.loads(action['data'])
        if not admin:
            action.pop('actorId', None)
    targets = json.loads(row['targets_json'])
    links = sorted(json.loads(row['links_json']), key=lambda x: (x['created'], x['id']))
    reversals = sorted(json.loads(row['reversals_json']), key=lambda x: (x['created'], x['id']))
    latest = next((x for x in actions if x['id'] == row['approval_id']), None)
    target_map = {x['caseItemId']: x['approvedMinor'] for x in targets if x['approvalId'] == row['approval_id']}
    items = []
    for item in json.loads(row['items_json']):
        snapshot = json.loads(item.pop('snapshot'))
        approved = target_map.get(item['id'])
        linked = sum(x['netMinor'] for x in links if x['caseItemId'] == item['id'])
        state = 'unknown' if approved is None else 'no_refund_due' if approved == 0 else 'sandbox_matched' if linked == approved else 'partially_matched' if linked else 'awaiting_allocation'
        items.append({**item, 'title': snapshot.get('title', ''), 'approvedMinor': approved, 'linkedMinor': linked,
                      'remainingMinor': None if approved is None else approved - linked, 'status': state})
    items.sort(key=lambda x: x['id'])
    complete_targets = bool(latest) and bool(items) and all(x['approvedMinor'] is not None for x in items)
    positive = [x for x in items if x['approvedMinor'] is not None and x['approvedMinor'] > 0]
    known_total = sum(x['approvedMinor'] for x in items if x['approvedMinor'] is not None)
    linked_total = sum(x['netMinor'] for x in links)
    status = 'unknown' if not complete_targets else 'no_refund_due' if not positive else 'sandbox_matched' if all(x['status'] == 'sandbox_matched' for x in positive) else 'partially_matched' if linked_total else 'awaiting_allocation'
    return {'caseId': row['id'], 'ownerId': row['owner'], 'orderId': row['order_id'], 'environment': 'sandbox', 'currency': row['currency'],
            'sandboxOnly': True, 'productionEnabled': False, 'actualFundsMoved': False, 'logisticsStatus': row['state'],
            'financialVersion': row['finance_version'], 'latestApproval': latest, 'approvals': [x for x in actions if x['kind'] == 'approve'],
            'actions': actions, 'items': items, 'links': links, 'reversals': reversals, 'status': status,
            'approvedMinor': known_total if complete_targets else None, 'knownApprovedMinor': known_total, 'linkedMinor': linked_total,
            'remainingMinor': known_total - linked_total if complete_targets else None,
            'financialDecisionComplete': status in ('sandbox_matched', 'no_refund_due'), 'caseRefundLinked': linked_total > 0,
            'caseRefundConfirmed': False, 'caseRefundMatched': status == 'sandbox_matched', 'policyConfirmed': False,
            'originalOrderPaymentStatus': row['payment_status'], 'originalOrderRefundedMinor': row['refunded_minor'],
            'notice': '仅对明确批准目标与原已应用沙箱退款事件做金额关联；不发起退款、不代表真实到账。物流与资金状态独立。'}


def case_finance_summary(db, case_id, owner, order_id):
    """Pure same-case read for an already-authorized serializer; no sync, init or writes."""
    unknown = {'caseRefundLinked': False, 'caseRefundConfirmed': False, 'caseRefundMatched': False,
               'caseRefundStatus': 'unknown', 'caseLinkedMinor': None, 'caseApprovedMinor': None,
               'caseRemainingMinor': None, 'caseFinancialVersion': None, 'caseFinancialDecisionComplete': False}
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='after_sales_finance_action_apply'").fetchone():
        return unknown
    row = db.execute(READ_CASE_SQL + ' AND c.owner=? AND c.order_id=?', (case_id, owner, order_id)).fetchone()
    if not row:
        return unknown
    value = project_case_finance(row)
    return {'caseRefundLinked': value['caseRefundLinked'], 'caseRefundConfirmed': False,
            'caseRefundMatched': value['caseRefundMatched'], 'caseRefundStatus': value['status'],
            'caseLinkedMinor': value['linkedMinor'], 'caseApprovedMinor': value['approvedMinor'],
            'caseRemainingMinor': value['remainingMinor'], 'caseFinancialVersion': value['financialVersion'],
            'caseFinancialDecisionComplete': value['financialDecisionComplete']}

class AfterSalesFinance:
    def __init__(self, store, handler, error, limiter):
        self.store, self.h, self.Error, self.rate = store, handler, error, limiter

    @property
    def actor(self):
        return self.h.user['id']

    def fail(self, status, message):
        raise self.Error(status, message)

    def text(self, value, limit=2000):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            self.fail(400, '请填写明确的文本，长度或字符不符合要求。')
        return value.strip()

    def integer(self, value, minimum=0, maximum=MAX_MINOR):
        if type(value) is not int or not minimum <= value <= maximum:
            self.fail(400, '金额须为明确币种最小单位的安全整数，不接受布尔、字符串或小数。')
        return value

    def body(self):
        value = self.h.body()
        if not isinstance(value, dict):
            self.fail(400, '请求必须为JSON对象。')
        return value

    def own(self, db, case_id, admin=False):
        row = db.execute('SELECT c.*,o.currency FROM after_sales_cases c JOIN commerce_orders o ON o.id=c.order_id AND o.owner=c.owner AND o.environment=c.environment WHERE c.id=?' + ('' if admin else ' AND c.owner=?'), (case_id,) if admin else (case_id, self.actor)).fetchone()
        if not row:
            self.fail(404, '未找到本人可查看的售后申请。')
        return row

    def actor_active(self, db):
        if not db.execute("SELECT 1 FROM users u WHERE u.id=? AND u.role='admin' AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')", (self.actor,)).fetchone():
            self.fail(403, '管理员权限或账号状态已变化。')

    def availability(self, db):
        row = db.execute("SELECT EXISTS(SELECT 1 FROM after_sales_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1) AND EXISTS(SELECT 1 FROM commerce_config WHERE key='settings' AND json_extract(data,'$.sandboxEnabled')=1) AS enabled").fetchone()
        return {'sandboxEnabled': bool(row['enabled']), 'productionEnabled': False, 'actualFundsMoved': False, 'explicitApprovalRequired': True}

    def projection(self, db, case_id, admin=False):
        self.own(db, case_id, admin)
        value = project_case_finance(db.execute(READ_CASE_SQL, (case_id,)).fetchone(), admin)
        return {**value, 'availability': self.availability(db)}

    def events(self, db, case_id):
        self.own(db, case_id, True)
        return {'items': [{'id': r['id'], 'kind': 'refund', 'environment': 'sandbox', 'status': r['status'], 'currency': r['currency'],
                           'amountMinor': r['amount_minor'], 'availableMinor': r['available_minor'], 'sourceReliable': bool(r['reliable']),
                           'items': json.loads(r['items_json']), 'created': r['created']} for r in db.execute(EVENTS_SQL, (case_id,))],
                'productionEnabled': False, 'actualFundsMoved': False, 'automaticAllocation': False}

    def normalized(self, kind, data):
        allowed = {'requestId', 'environment', 'currency', 'expectedVersion', 'reason', 'items'} | ({'ruleLabel'} if kind == 'approve' else {'approvalId', 'refundEventId'} if kind == 'link' else set())
        if set(data) - allowed:
            self.fail(400, '请求中有不允许的字段。')
        if data.get('environment') != 'sandbox':
            self.fail(403, '本模块仅允许沙箱关联，不启用生产退款。')
        request_id = self.text(data.get('requestId'), 128)
        currency = self.text(data.get('currency'), 3)
        if not re.fullmatch('[A-Z]{3}', currency):
            self.fail(400, '请明确使用原订单的三位大写币种。')
        expected = self.integer(data.get('expectedVersion'), 0, 2_147_483_646)
        payload = {'reason': self.text(data.get('reason'))}
        if kind == 'approve':
            payload['ruleLabel'] = self.text(data.get('ruleLabel'), 120)
        elif kind == 'link':
            payload.update(approvalId=self.text(data.get('approvalId'), 100), refundEventId=self.text(data.get('refundEventId'), 100))
        values = data.get('items')
        if not isinstance(values, list) or not 1 <= len(values) <= 30:
            self.fail(400, '须明确填写1至30个项目。')
        key = 'linkId' if kind == 'reverse' else 'caseItemId'
        field = 'approvedMinor' if kind == 'approve' else 'amountMinor'
        items = []
        for value in values:
            if not isinstance(value, dict) or set(value) != {key, field}:
                self.fail(400, '项目字段不完整或含未允许内容。')
            amount = None if kind == 'approve' and value[field] is None else self.integer(value[field], 0 if kind == 'approve' else 1)
            items.append({key: self.text(value[key], 200 if kind == 'reverse' else 100), field: amount})
        items.sort(key=lambda x: x[key])
        if len({x[key] for x in items}) != len(items):
            self.fail(400, '同一操作不可重复项目。')
        payload['items'] = items
        return request_id, currency, expected, payload

    def mutate(self, case_id, kind, data):
        request_id, currency, expected, payload = self.normalized(kind, data)
        token = fingerprint({'caseId': case_id, 'kind': kind, 'environment': 'sandbox', 'currency': currency, 'expectedVersion': expected, **payload})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.actor_active(db)
            case = self.own(db, case_id, True)
            if case['currency'] != currency:
                self.fail(409, '币种与原订单不一致。')
            old = db.execute("SELECT * FROM after_sales_finance_actions WHERE actor=? AND environment='sandbox' AND request_id=?", (self.actor, request_id)).fetchone()
            if old:
                if old['case_id'] != case_id or old['kind'] != kind or old['fingerprint'] != token:
                    self.fail(409, '该幂等编号已用于其他资金关联操作。')
                return {'actionId': old['id'], 'appliedVersion': old['expected_version'] + 1, 'replayed': True, 'item': self.projection(db, case_id, True)}
            action_id, timestamp = str(uuid4()), stamp()
            db.execute('INSERT OR IGNORE INTO after_sales_finance_heads(case_id,owner,order_id,environment,currency,created,updated) VALUES(?,?,?,?,?,?,?)', (case_id, case['owner'], case['order_id'], 'sandbox', currency, timestamp, timestamp))
            db.execute('INSERT INTO after_sales_finance_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (action_id, case_id, case['owner'], self.actor, 'sandbox', currency, request_id, kind, expected, token, dump(payload), timestamp))
            self.store.audit(db, self.actor, 'after-sales-finance.' + kind, case_id, '仅沙箱原事件关联/撤销关联；无退款、库存或权益操作')
            return {'actionId': action_id, 'appliedVersion': expected + 1, 'replayed': False, 'item': self.projection(db, case_id, True)}

    def route(self, method, path):
        if not (path.startswith('/api/after-sales-finance/') or path == '/api/admin/after-sales-finance' or path.startswith('/api/admin/after-sales-finance/')):
            return None
        self.h.require()
        admin = path.startswith('/api/admin/')
        if admin:
            self.h.require(['admin'])
        self.rate('after-sales-finance:' + ('read:' if method == 'GET' else 'write:') + self.actor, 180 if method == 'GET' else 30)
        try:
            if path == '/api/admin/after-sales-finance' and method == 'GET':
                with self.store.connect() as db:
                    db.execute('BEGIN')
                    self.actor_active(db)
                    rows = db.execute("SELECT id FROM after_sales_cases WHERE environment='sandbox' ORDER BY created DESC,id LIMIT 100").fetchall()
                    return {'items': [self.projection(db, r['id'], True) for r in rows], 'limit': 100, 'environment': 'sandbox', 'productionEnabled': False, 'actualFundsMoved': False}
            match = re.fullmatch(r'/api/(admin/)?after-sales-finance/cases/([^/]+)(/(events|approve|link|reverse))?', path)
            if match:
                _, case_id, _, action = match.groups()
                if method == 'GET' and (not action or admin and action == 'events'):
                    with self.store.connect() as db:
                        db.execute('BEGIN')
                        if admin:
                            self.actor_active(db)
                        return self.events(db, case_id) if action == 'events' else self.projection(db, case_id, admin)
                if admin and method == 'POST' and action in ('approve', 'link', 'reverse'):
                    return self.mutate(case_id, action, self.body())
            self.fail(405, '不支持的售后资金关联操作。')
        except sqlite3.IntegrityError as error:
            message = str(error)
            if 'after_sales_finance_admin_required' in message:
                self.fail(403, '管理员权限或账号状态已变化。')
            if 'after_sales_finance_disabled' in message:
                self.fail(503, '售后或统一交易沙箱已关闭。')
            if re.search(r'after_sales_finance_|UNIQUE|CHECK constraint', message):
                self.fail(409, '目标、关联容量、版本或退款事实已变化，请刷新后使用原编号重试。')
            raise
