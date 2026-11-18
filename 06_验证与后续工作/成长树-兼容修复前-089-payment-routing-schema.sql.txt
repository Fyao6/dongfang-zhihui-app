-- Shared PAY05 schema. SQL guards preserve the original settlement path.
CREATE TABLE IF NOT EXISTS payment_routing_config(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT NOT NULL CHECK(json_valid(data)));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS payment_routing_versions(id TEXT PRIMARY KEY,revision INTEGER NOT NULL UNIQUE CHECK(revision>0),rule_version TEXT NOT NULL,context_digest TEXT NOT NULL,data TEXT NOT NULL CHECK(json_valid(data)),digest TEXT NOT NULL,actor TEXT NOT NULL,created INTEGER NOT NULL);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS payment_routing_quotes(id TEXT PRIMARY KEY,owner TEXT NOT NULL,request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,purpose TEXT NOT NULL CHECK(purpose IN ('new_order','order_reconfirm')),order_id TEXT NOT NULL DEFAULT '',mode TEXT NOT NULL CHECK(mode='enforced_sandbox'),policy_revision INTEGER NOT NULL,context_digest TEXT NOT NULL,snapshot_data TEXT NOT NULL CHECK(json_valid(snapshot_data)),created INTEGER NOT NULL,expires INTEGER NOT NULL CHECK(expires>created),UNIQUE(owner,request_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS commerce_order_payment_routes(order_id TEXT PRIMARY KEY,owner TEXT NOT NULL,mode TEXT NOT NULL CHECK(mode IN ('legacy_sandbox','enforced_sandbox')),quote_id TEXT UNIQUE,policy_revision INTEGER NOT NULL,context_digest TEXT NOT NULL,matrix_applied INTEGER NOT NULL CHECK(matrix_applied IN (0,1)),snapshot_data TEXT NOT NULL CHECK(json_valid(snapshot_data)),digest TEXT NOT NULL,created INTEGER NOT NULL,CHECK((mode='legacy_sandbox' AND matrix_applied=0 AND context_digest='') OR (mode='enforced_sandbox' AND matrix_applied=1 AND quote_id IS NOT NULL AND length(context_digest)=64)));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS payment_routing_quote_consumptions(quote_id TEXT PRIMARY KEY,order_id TEXT NOT NULL UNIQUE,owner TEXT NOT NULL,created INTEGER NOT NULL);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS payment_routing_confirmations(id TEXT PRIMARY KEY,owner TEXT NOT NULL,order_id TEXT NOT NULL,quote_id TEXT NOT NULL UNIQUE,request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,policy_revision INTEGER NOT NULL,context_digest TEXT NOT NULL,snapshot_data TEXT NOT NULL CHECK(json_valid(snapshot_data)),digest TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL CHECK(expires>created),UNIQUE(owner,request_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS payment_routing_atomic_guards(id TEXT PRIMARY KEY,ok INTEGER NOT NULL CHECK(ok=1));
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS payment_routing_quotes_owner ON payment_routing_quotes(owner,created,id);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS payment_routing_confirmations_order ON payment_routing_confirmations(owner,order_id,created,id);
--> statement-breakpoint
INSERT OR IGNORE INTO payment_routing_config VALUES(1,'{"revision":0,"mode":"legacy_sandbox","confirmed":false,"ruleVersion":"","contextDigest":"","rules":[],"productionEnabled":false}');
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_atomic_check BEFORE INSERT ON payment_routing_atomic_guards WHEN NEW.ok!=1
 BEGIN SELECT RAISE(ABORT,'payment_routing_changed'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_config_no_delete BEFORE DELETE ON payment_routing_config
 BEGIN SELECT RAISE(ABORT,'payment_routing_config_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_config_cas BEFORE UPDATE ON payment_routing_config BEGIN
 SELECT CASE WHEN NEW.id!=OLD.id OR json_type(NEW.data,'$.revision')!='integer'
 OR json_extract(NEW.data,'$.revision')!=json_extract(OLD.data,'$.revision')+1
 OR json_extract(NEW.data,'$.mode') NOT IN ('legacy_sandbox','enforced_sandbox','paused')
 OR json_type(NEW.data,'$.productionEnabled')!='false'
 OR NOT EXISTS(SELECT 1 FROM payment_routing_versions v WHERE v.revision=json_extract(NEW.data,'$.revision') AND v.data=NEW.data)
 THEN RAISE(ABORT,'payment_routing_changed') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_version_check BEFORE INSERT ON payment_routing_versions BEGIN
 SELECT CASE WHEN NEW.revision!=(SELECT json_extract(data,'$.revision')+1 FROM payment_routing_config WHERE id=1)
 OR json_extract(NEW.data,'$.revision')!=NEW.revision
 OR NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.actor AND u.role='admin' AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))
 THEN RAISE(ABORT,'payment_routing_changed') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_versions_no_update BEFORE UPDATE ON payment_routing_versions BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_versions_no_delete BEFORE DELETE ON payment_routing_versions BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_quotes_no_update BEFORE UPDATE ON payment_routing_quotes BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_quotes_no_delete BEFORE DELETE ON payment_routing_quotes BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS commerce_order_payment_routes_no_update BEFORE UPDATE ON commerce_order_payment_routes BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS commerce_order_payment_routes_no_delete BEFORE DELETE ON commerce_order_payment_routes BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_quote_consumptions_no_update BEFORE UPDATE ON payment_routing_quote_consumptions BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_quote_consumptions_no_delete BEFORE DELETE ON payment_routing_quote_consumptions BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_confirmations_no_update BEFORE UPDATE ON payment_routing_confirmations BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_confirmations_no_delete BEFORE DELETE ON payment_routing_confirmations BEGIN SELECT RAISE(ABORT,'payment_routing_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_quote_check BEFORE INSERT ON payment_routing_quotes BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.owner AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))
 OR NEW.expires<=(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)) OR NEW.expires!=NEW.created+300000
 OR NOT EXISTS(SELECT 1 FROM payment_routing_config c WHERE c.id=1
 AND json_extract(c.data,'$.mode')='enforced_sandbox' AND json_type(c.data,'$.confirmed')='true'
 AND json_extract(c.data,'$.revision')=NEW.policy_revision AND json_extract(c.data,'$.contextDigest')=NEW.context_digest
 AND json_extract(NEW.snapshot_data,'$.decision.policyRevision')=NEW.policy_revision
 AND json_extract(NEW.snapshot_data,'$.decision.contextDigest')=NEW.context_digest)
 OR (NEW.purpose='new_order' AND NEW.order_id!='')
 OR (NEW.purpose='order_reconfirm' AND NOT EXISTS(SELECT 1 FROM commerce_orders o
 JOIN commerce_order_payment_routes r ON r.order_id=o.id AND r.owner=o.owner AND r.mode='enforced_sandbox'
 WHERE o.id=NEW.order_id AND o.owner=NEW.owner AND o.environment='sandbox'
 AND o.status='awaiting_payment' AND o.payment_status='unpaid' AND o.reserved_until>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))
 AND o.fingerprint=json_extract(NEW.snapshot_data,'$.orderFingerprint')))
 OR NOT (
 json_type(NEW.snapshot_data,'$.bindings.skus')='array'
 AND json_array_length(NEW.snapshot_data,'$.bindings.skus')=json_array_length(NEW.snapshot_data,'$.items')
 AND NOT EXISTS(SELECT 1 FROM json_each(NEW.snapshot_data,'$.bindings.skus') b
 LEFT JOIN commerce_skus s ON s.id=json_extract(b.value,'$.skuId')
 LEFT JOIN commerce_products p ON p.id=s.product_id
 LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id
 WHERE s.id IS NULL OR p.id IS NULL OR p.status!='published' OR p.environment!='sandbox' OR s.environment!='sandbox'
 OR coalesce(v.active,1)!=1 OR p.id!=json_extract(b.value,'$.productId')
 OR p.version!=json_extract(b.value,'$.productVersion') OR s.version!=json_extract(b.value,'$.priceVersion')
 OR s.price_minor!=json_extract(b.value,'$.priceMinor') OR s.currency!=json_extract(b.value,'$.currency')
 OR p.type!=json_extract(b.value,'$.type') OR p.content_id!=json_extract(b.value,'$.contentId')
 OR coalesce(v.options,'[]')!=json_extract(b.value,'$.options')
 OR p.shipping_countries!=json_extract(b.value,'$.shippingCountries')
 OR p.shipping_minor!=json_extract(b.value,'$.shippingMinor') OR p.tax_minor!=json_extract(b.value,'$.taxMinor'))
 AND NOT EXISTS(SELECT 1 FROM json_each(NEW.snapshot_data,'$.bindings.plans') b
 LEFT JOIN membership_plans p ON p.id=json_extract(b.value,'$.planId')
 WHERE p.id IS NULL OR p.sku_id!=json_extract(b.value,'$.skuId') OR p.version!=json_extract(b.value,'$.version')
 OR p.status!=json_extract(b.value,'$.status') OR p.data!=json_extract(b.value,'$.data'))
 AND NOT EXISTS(SELECT 1 FROM json_each(NEW.snapshot_data,'$.bindings.digital') b
 LEFT JOIN digital_sandbox_assets a ON a.content_id=json_extract(b.value,'$.contentId')
 LEFT JOIN contents c ON c.kind='courses' AND c.id=a.content_id
 LEFT JOIN settings d ON d.key='digital_entitlements'
 WHERE a.media_id IS NULL OR c.id IS NULL OR d.data IS NULL OR a.media_id!=json_extract(b.value,'$.mediaId')
 OR a.owner!=json_extract(b.value,'$.assetOwner') OR a.status!=json_extract(b.value,'$.assetStatus')
 OR a.status!='active' OR a.updated!=json_extract(b.value,'$.assetUpdated')
 OR c.status!='published' OR c.updated!=json_extract(b.value,'$.courseUpdated')
 OR c.data!=json_extract(b.value,'$.courseData') OR d.data!=json_extract(b.value,'$.policyData'))
) THEN RAISE(ABORT,'payment_routing_changed') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_route_check BEFORE INSERT ON commerce_order_payment_routes BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM payment_routing_atomic_guards WHERE id=json_extract(NEW.snapshot_data,'$.admissionGuard') AND ok=1)
 OR NOT EXISTS(SELECT 1 FROM commerce_orders o WHERE o.id=NEW.order_id AND o.owner=NEW.owner AND o.environment='sandbox'
 AND o.status='awaiting_payment' AND o.payment_status='unpaid' AND o.created=NEW.created
 AND o.fingerprint=json_extract(NEW.snapshot_data,'$.orderFingerprint')
 AND o.currency=json_extract(NEW.snapshot_data,'$.totals.currency')
 AND o.total_minor=json_extract(NEW.snapshot_data,'$.totals.totalMinor')
 AND o.subtotal_minor=json_extract(NEW.snapshot_data,'$.totals.subtotalMinor')
 AND o.shipping_minor=json_extract(NEW.snapshot_data,'$.totals.shippingMinor')
 AND o.tax_minor=json_extract(NEW.snapshot_data,'$.totals.taxMinor'))
 OR NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.owner AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed'))
 OR NOT EXISTS(SELECT 1 FROM payment_routing_config c WHERE c.id=1 AND json_extract(c.data,'$.mode')=NEW.mode
 AND json_extract(c.data,'$.revision')=NEW.policy_revision AND (NEW.mode='legacy_sandbox' OR
 (json_type(c.data,'$.confirmed')='true' AND json_extract(c.data,'$.contextDigest')=NEW.context_digest)))
 OR (NEW.mode='enforced_sandbox' AND NOT EXISTS(SELECT 1 FROM payment_routing_quotes q WHERE q.id=NEW.quote_id AND q.owner=NEW.owner
 AND q.purpose='new_order' AND q.order_id='' AND q.policy_revision=NEW.policy_revision AND q.context_digest=NEW.context_digest
 AND q.expires>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)) AND json_type(q.snapshot_data,'$.decision.eligible')='true'
 AND json_extract(q.snapshot_data,'$.decision.channel')='sandbox'
 AND json_extract(q.snapshot_data,'$.items')=json_extract(NEW.snapshot_data,'$.items')
 AND json_extract(q.snapshot_data,'$.totals')=json_extract(NEW.snapshot_data,'$.totals')
 AND (
 json_type(q.snapshot_data,'$.bindings.skus')='array'
 AND json_array_length(q.snapshot_data,'$.bindings.skus')=json_array_length(q.snapshot_data,'$.items')
 AND NOT EXISTS(SELECT 1 FROM json_each(q.snapshot_data,'$.bindings.skus') b
 LEFT JOIN commerce_skus s ON s.id=json_extract(b.value,'$.skuId')
 LEFT JOIN commerce_products p ON p.id=s.product_id
 LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id
 WHERE s.id IS NULL OR p.id IS NULL OR p.status!='published' OR p.environment!='sandbox' OR s.environment!='sandbox'
 OR coalesce(v.active,1)!=1 OR p.id!=json_extract(b.value,'$.productId')
 OR p.version!=json_extract(b.value,'$.productVersion') OR s.version!=json_extract(b.value,'$.priceVersion')
 OR s.price_minor!=json_extract(b.value,'$.priceMinor') OR s.currency!=json_extract(b.value,'$.currency')
 OR p.type!=json_extract(b.value,'$.type') OR p.content_id!=json_extract(b.value,'$.contentId')
 OR coalesce(v.options,'[]')!=json_extract(b.value,'$.options')
 OR p.shipping_countries!=json_extract(b.value,'$.shippingCountries')
 OR p.shipping_minor!=json_extract(b.value,'$.shippingMinor') OR p.tax_minor!=json_extract(b.value,'$.taxMinor'))
 AND NOT EXISTS(SELECT 1 FROM json_each(q.snapshot_data,'$.bindings.plans') b
 LEFT JOIN membership_plans p ON p.id=json_extract(b.value,'$.planId')
 WHERE p.id IS NULL OR p.sku_id!=json_extract(b.value,'$.skuId') OR p.version!=json_extract(b.value,'$.version')
 OR p.status!=json_extract(b.value,'$.status') OR p.data!=json_extract(b.value,'$.data'))
 AND NOT EXISTS(SELECT 1 FROM json_each(q.snapshot_data,'$.bindings.digital') b
 LEFT JOIN digital_sandbox_assets a ON a.content_id=json_extract(b.value,'$.contentId')
 LEFT JOIN contents c ON c.kind='courses' AND c.id=a.content_id
 LEFT JOIN settings d ON d.key='digital_entitlements'
 WHERE a.media_id IS NULL OR c.id IS NULL OR d.data IS NULL OR a.media_id!=json_extract(b.value,'$.mediaId')
 OR a.owner!=json_extract(b.value,'$.assetOwner') OR a.status!=json_extract(b.value,'$.assetStatus')
 OR a.status!='active' OR a.updated!=json_extract(b.value,'$.assetUpdated')
 OR c.status!='published' OR c.updated!=json_extract(b.value,'$.courseUpdated')
 OR c.data!=json_extract(b.value,'$.courseData') OR d.data!=json_extract(b.value,'$.policyData'))
)
 AND NOT EXISTS(SELECT 1 FROM payment_routing_quote_consumptions x WHERE x.quote_id=q.id)))
 THEN RAISE(ABORT,'payment_routing_changed') END;
 SELECT CASE WHEN (SELECT count(*) FROM commerce_order_items WHERE order_id=NEW.order_id)!=json_array_length(NEW.snapshot_data,'$.items')
 OR EXISTS(SELECT 1 FROM json_each(NEW.snapshot_data,'$.items') j
 LEFT JOIN commerce_order_items i ON i.order_id=NEW.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 WHERE i.id IS NULL OR i.product_id!=json_extract(j.value,'$.productId') OR i.type!=json_extract(j.value,'$.type')
 OR i.quantity!=json_extract(j.value,'$.quantity') OR i.price_minor!=json_extract(j.value,'$.priceMinor')
 OR i.currency!=json_extract(j.value,'$.currency') OR i.unit_shipping_minor!=json_extract(j.value,'$.unitShippingMinor')
 OR i.unit_tax_minor!=json_extract(j.value,'$.unitTaxMinor') OR i.content_id!=json_extract(j.value,'$.contentId')
 OR i.price_version!=json_extract(j.value,'$.priceVersion')) THEN RAISE(ABORT,'payment_routing_changed') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_consumption_check BEFORE INSERT ON payment_routing_quote_consumptions BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM payment_routing_quotes q JOIN commerce_order_payment_routes r ON r.quote_id=q.id
 JOIN commerce_orders o ON o.id=r.order_id WHERE q.id=NEW.quote_id AND q.purpose='new_order' AND q.owner=NEW.owner
 AND r.order_id=NEW.order_id AND r.owner=NEW.owner AND r.mode='enforced_sandbox' AND o.payment_status='unpaid'
 AND q.expires>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)) AND NEW.created=o.created) THEN RAISE(ABORT,'payment_routing_changed') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_confirmation_check BEFORE INSERT ON payment_routing_confirmations BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM payment_routing_quotes q JOIN commerce_orders o ON o.id=q.order_id
 JOIN commerce_order_payment_routes r ON r.order_id=o.id AND r.mode='enforced_sandbox'
 JOIN payment_routing_config c ON c.id=1 WHERE q.id=NEW.quote_id AND q.purpose='order_reconfirm'
 AND q.order_id=NEW.order_id AND q.owner=NEW.owner AND o.owner=NEW.owner AND r.owner=NEW.owner
 AND o.status='awaiting_payment' AND o.payment_status='unpaid' AND o.reserved_until>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))
 AND q.expires>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)) AND NEW.expires=NEW.created+300000 AND NEW.expires>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))
 AND q.policy_revision=NEW.policy_revision AND q.context_digest=NEW.context_digest
 AND json_extract(c.data,'$.mode')='enforced_sandbox' AND json_type(c.data,'$.confirmed')='true'
 AND json_extract(c.data,'$.revision')=NEW.policy_revision AND json_extract(c.data,'$.contextDigest')=NEW.context_digest
 AND o.fingerprint=json_extract(q.snapshot_data,'$.orderFingerprint')
 AND json_type(q.snapshot_data,'$.decision.eligible')='true' AND json_extract(q.snapshot_data,'$.decision.channel')='sandbox'
 AND json_extract(NEW.snapshot_data,'$.items')=json_extract(q.snapshot_data,'$.items')
 AND (
 json_type(q.snapshot_data,'$.bindings.skus')='array'
 AND json_array_length(q.snapshot_data,'$.bindings.skus')=json_array_length(q.snapshot_data,'$.items')
 AND NOT EXISTS(SELECT 1 FROM json_each(q.snapshot_data,'$.bindings.skus') b
 LEFT JOIN commerce_skus s ON s.id=json_extract(b.value,'$.skuId')
 LEFT JOIN commerce_products p ON p.id=s.product_id
 LEFT JOIN commerce_sku_variants v ON v.sku_id=s.id
 WHERE s.id IS NULL OR p.id IS NULL OR p.status!='published' OR p.environment!='sandbox' OR s.environment!='sandbox'
 OR coalesce(v.active,1)!=1 OR p.id!=json_extract(b.value,'$.productId')
 OR p.version!=json_extract(b.value,'$.productVersion') OR s.version!=json_extract(b.value,'$.priceVersion')
 OR s.price_minor!=json_extract(b.value,'$.priceMinor') OR s.currency!=json_extract(b.value,'$.currency')
 OR p.type!=json_extract(b.value,'$.type') OR p.content_id!=json_extract(b.value,'$.contentId')
 OR coalesce(v.options,'[]')!=json_extract(b.value,'$.options')
 OR p.shipping_countries!=json_extract(b.value,'$.shippingCountries')
 OR p.shipping_minor!=json_extract(b.value,'$.shippingMinor') OR p.tax_minor!=json_extract(b.value,'$.taxMinor'))
 AND NOT EXISTS(SELECT 1 FROM json_each(q.snapshot_data,'$.bindings.plans') b
 LEFT JOIN membership_plans p ON p.id=json_extract(b.value,'$.planId')
 WHERE p.id IS NULL OR p.sku_id!=json_extract(b.value,'$.skuId') OR p.version!=json_extract(b.value,'$.version')
 OR p.status!=json_extract(b.value,'$.status') OR p.data!=json_extract(b.value,'$.data'))
 AND NOT EXISTS(SELECT 1 FROM json_each(q.snapshot_data,'$.bindings.digital') b
 LEFT JOIN digital_sandbox_assets a ON a.content_id=json_extract(b.value,'$.contentId')
 LEFT JOIN contents c ON c.kind='courses' AND c.id=a.content_id
 LEFT JOIN settings d ON d.key='digital_entitlements'
 WHERE a.media_id IS NULL OR c.id IS NULL OR d.data IS NULL OR a.media_id!=json_extract(b.value,'$.mediaId')
 OR a.owner!=json_extract(b.value,'$.assetOwner') OR a.status!=json_extract(b.value,'$.assetStatus')
 OR a.status!='active' OR a.updated!=json_extract(b.value,'$.assetUpdated')
 OR c.status!='published' OR c.updated!=json_extract(b.value,'$.courseUpdated')
 OR c.data!=json_extract(b.value,'$.courseData') OR d.data!=json_extract(b.value,'$.policyData'))
)
 AND json_extract(NEW.snapshot_data,'$.totals')=json_extract(q.snapshot_data,'$.totals'))
 OR EXISTS(SELECT 1 FROM payment_routing_quotes q,json_each(q.snapshot_data,'$.originalTerms.membership') b
 LEFT JOIN membership_order_snapshots m ON m.item_id=json_extract(b.value,'$.itemId') AND m.order_id=NEW.order_id
 WHERE q.id=NEW.quote_id AND (m.item_id IS NULL OR m.data!=json_extract(b.value,'$.data')))
 OR EXISTS(SELECT 1 FROM payment_routing_quotes q,json_each(q.snapshot_data,'$.originalTerms.digital') b
 LEFT JOIN digital_order_snapshots d ON d.item_id=json_extract(b.value,'$.itemId') AND d.order_id=NEW.order_id
 WHERE q.id=NEW.quote_id AND (d.item_id IS NULL OR d.content_id!=json_extract(b.value,'$.contentId')
 OR d.media_id!=json_extract(b.value,'$.mediaId') OR d.policy_snapshot!=json_extract(b.value,'$.policyData')))
 OR EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed')
 THEN RAISE(ABORT,'payment_routing_changed') END;
END;
--> statement-breakpoint
-- Historical admission facts only: current routing mode/context/revision never rejects a trusted receipt.
CREATE TRIGGER IF NOT EXISTS payment_routing_settlement_check BEFORE INSERT ON commerce_payment_events
 WHEN NEW.kind='sandbox_pay' AND EXISTS(SELECT 1 FROM commerce_order_payment_routes WHERE order_id=NEW.order_id) BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_payment_routes r JOIN commerce_orders o ON o.id=r.order_id
 WHERE r.order_id=NEW.order_id AND r.owner=NEW.owner AND o.owner=NEW.owner AND o.environment='sandbox'
 AND o.fingerprint=json_extract(r.snapshot_data,'$.orderFingerprint')
 AND o.total_minor=NEW.amount_minor AND o.currency=NEW.currency
 AND o.total_minor=json_extract(r.snapshot_data,'$.totals.totalMinor')
 AND o.currency=json_extract(r.snapshot_data,'$.totals.currency')
 AND (r.mode='legacy_sandbox' OR (r.mode='enforced_sandbox' AND json_type(r.snapshot_data,'$.decision.eligible')='true'
 AND json_extract(r.snapshot_data,'$.decision.channel')='sandbox'
 AND EXISTS(SELECT 1 FROM payment_routing_quote_consumptions x JOIN payment_routing_quotes q ON q.id=x.quote_id
 WHERE x.quote_id=r.quote_id AND x.order_id=r.order_id AND x.owner=r.owner AND q.owner=r.owner AND q.purpose='new_order'
 AND q.policy_revision=r.policy_revision AND q.context_digest=r.context_digest
 AND json_extract(q.snapshot_data,'$.items')=json_extract(r.snapshot_data,'$.items')
 AND json_extract(q.snapshot_data,'$.totals')=json_extract(r.snapshot_data,'$.totals')))))
 OR EXISTS(SELECT 1 FROM commerce_order_payment_routes r,json_each(r.snapshot_data,'$.items') j
 LEFT JOIN commerce_order_items i ON i.order_id=r.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 WHERE r.order_id=NEW.order_id AND (i.id IS NULL OR i.type!=json_extract(j.value,'$.type')
 OR i.product_id!=json_extract(j.value,'$.productId') OR i.quantity!=json_extract(j.value,'$.quantity')
 OR i.price_minor!=json_extract(j.value,'$.priceMinor') OR i.currency!=json_extract(j.value,'$.currency')
 OR i.content_id!=json_extract(j.value,'$.contentId') OR i.price_version!=json_extract(j.value,'$.priceVersion')
 OR i.unit_shipping_minor!=json_extract(j.value,'$.unitShippingMinor') OR i.unit_tax_minor!=json_extract(j.value,'$.unitTaxMinor')))
 OR (SELECT count(*) FROM commerce_order_items WHERE order_id=NEW.order_id)!=(SELECT json_array_length(snapshot_data,'$.items') FROM commerce_order_payment_routes WHERE order_id=NEW.order_id)
 THEN RAISE(ABORT,'payment_routing_frozen_mismatch') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_late_fact_check BEFORE INSERT ON payment_late_cases
 WHEN EXISTS(SELECT 1 FROM commerce_order_payment_routes WHERE order_id=NEW.order_id) BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM commerce_order_payment_routes r JOIN commerce_orders o ON o.id=r.order_id
 WHERE r.order_id=NEW.order_id AND r.owner=NEW.owner AND o.owner=NEW.owner AND o.environment='sandbox'
 AND o.fingerprint=json_extract(r.snapshot_data,'$.orderFingerprint')
 AND o.total_minor=NEW.amount_minor AND o.currency=NEW.currency
 AND o.total_minor=json_extract(r.snapshot_data,'$.totals.totalMinor')
 AND o.currency=json_extract(r.snapshot_data,'$.totals.currency')
 AND (r.mode='legacy_sandbox' OR (r.mode='enforced_sandbox' AND json_type(r.snapshot_data,'$.decision.eligible')='true'
 AND json_extract(r.snapshot_data,'$.decision.channel')='sandbox'
 AND EXISTS(SELECT 1 FROM payment_routing_quote_consumptions x JOIN payment_routing_quotes q ON q.id=x.quote_id
 WHERE x.quote_id=r.quote_id AND x.order_id=r.order_id AND x.owner=r.owner AND q.owner=r.owner AND q.purpose='new_order'
 AND q.policy_revision=r.policy_revision AND q.context_digest=r.context_digest
 AND json_extract(q.snapshot_data,'$.items')=json_extract(r.snapshot_data,'$.items')
 AND json_extract(q.snapshot_data,'$.totals')=json_extract(r.snapshot_data,'$.totals')))))
 OR EXISTS(SELECT 1 FROM commerce_order_payment_routes r,json_each(r.snapshot_data,'$.items') j
 LEFT JOIN commerce_order_items i ON i.order_id=r.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 WHERE r.order_id=NEW.order_id AND (i.id IS NULL OR i.type!=json_extract(j.value,'$.type')
 OR i.product_id!=json_extract(j.value,'$.productId') OR i.quantity!=json_extract(j.value,'$.quantity')
 OR i.price_minor!=json_extract(j.value,'$.priceMinor') OR i.currency!=json_extract(j.value,'$.currency')
 OR i.content_id!=json_extract(j.value,'$.contentId') OR i.price_version!=json_extract(j.value,'$.priceVersion')
 OR i.unit_shipping_minor!=json_extract(j.value,'$.unitShippingMinor') OR i.unit_tax_minor!=json_extract(j.value,'$.unitTaxMinor')))
 OR (SELECT count(*) FROM commerce_order_items WHERE order_id=NEW.order_id)!=(SELECT json_array_length(snapshot_data,'$.items') FROM commerce_order_payment_routes WHERE order_id=NEW.order_id)
 THEN RAISE(ABORT,'payment_routing_frozen_mismatch') END;
END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_terms_capture BEFORE INSERT ON commerce_order_payment_routes WHEN NEW.mode='enforced_sandbox' BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM json_each(NEW.snapshot_data,'$.items') j
 JOIN commerce_order_items i ON i.order_id=NEW.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 LEFT JOIN membership_order_snapshots m ON m.item_id=i.id
 WHERE  json_extract(j.value,'$.type')='membership' AND
 (m.item_id IS NULL OR m.owner!=NEW.owner OR m.order_id!=NEW.order_id
 OR m.plan_id IS NOT json_extract(j.value,'$.membershipTerms.id')
 OR m.plan_version IS NOT json_extract(j.value,'$.membershipTerms.version')
 OR m.group_id IS NOT json_extract(j.value,'$.membershipTerms.groupId')
 OR json_remove(m.data,'$.snapshotAt','$.snapshotSchema','$.renewalOf') IS NOT json_extract(j.value,'$.membershipTerms')))
 OR EXISTS(SELECT 1 FROM json_each(NEW.snapshot_data,'$.items') j
 JOIN commerce_order_items i ON i.order_id=NEW.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 LEFT JOIN digital_order_snapshots d ON d.item_id=i.id
 WHERE  json_extract(j.value,'$.type')='digital' AND
 ((d.item_id IS NULL AND coalesce(json_type(j.value,'$.digitalTerms'),'')!='null')
 OR (d.item_id IS NOT NULL AND (coalesce(json_type(j.value,'$.digitalTerms'),'')!='object'
 OR d.owner!=NEW.owner OR d.order_id!=NEW.order_id OR d.content_id IS NOT json_extract(j.value,'$.digitalTerms.contentId')
 OR d.media_id IS NOT json_extract(j.value,'$.digitalTerms.mediaId')
 OR json(d.policy_snapshot) IS NOT json_remove(json_extract(j.value,'$.digitalTerms'),'$.contentId','$.mediaId')))))
 THEN RAISE(ABORT,'payment_routing_terms_changed') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_terms_ledger BEFORE INSERT ON commerce_payment_events WHEN NEW.kind='sandbox_pay' AND EXISTS(SELECT 1 FROM commerce_order_payment_routes WHERE order_id=NEW.order_id AND mode='enforced_sandbox') BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM commerce_order_payment_routes r,json_each(r.snapshot_data,'$.items') j
 JOIN commerce_order_items i ON i.order_id=r.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 LEFT JOIN membership_order_snapshots m ON m.item_id=i.id
 WHERE r.order_id=NEW.order_id AND r.mode='enforced_sandbox' AND  json_extract(j.value,'$.type')='membership' AND
 (m.item_id IS NULL OR m.owner!=r.owner OR m.order_id!=r.order_id
 OR m.plan_id IS NOT json_extract(j.value,'$.membershipTerms.id')
 OR m.plan_version IS NOT json_extract(j.value,'$.membershipTerms.version')
 OR m.group_id IS NOT json_extract(j.value,'$.membershipTerms.groupId')
 OR json_remove(m.data,'$.snapshotAt','$.snapshotSchema','$.renewalOf') IS NOT json_extract(j.value,'$.membershipTerms')))
 OR EXISTS(SELECT 1 FROM commerce_order_payment_routes r,json_each(r.snapshot_data,'$.items') j
 JOIN commerce_order_items i ON i.order_id=r.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 LEFT JOIN digital_order_snapshots d ON d.item_id=i.id
 WHERE r.order_id=NEW.order_id AND r.mode='enforced_sandbox' AND  json_extract(j.value,'$.type')='digital' AND
 ((d.item_id IS NULL AND coalesce(json_type(j.value,'$.digitalTerms'),'')!='null')
 OR (d.item_id IS NOT NULL AND (coalesce(json_type(j.value,'$.digitalTerms'),'')!='object'
 OR d.owner!=r.owner OR d.order_id!=r.order_id OR d.content_id IS NOT json_extract(j.value,'$.digitalTerms.contentId')
 OR d.media_id IS NOT json_extract(j.value,'$.digitalTerms.mediaId')
 OR json(d.policy_snapshot) IS NOT json_remove(json_extract(j.value,'$.digitalTerms'),'$.contentId','$.mediaId')))))
 THEN RAISE(ABORT,'payment_routing_terms_changed') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS payment_routing_terms_late BEFORE INSERT ON payment_late_cases WHEN EXISTS(SELECT 1 FROM commerce_order_payment_routes WHERE order_id=NEW.order_id AND mode='enforced_sandbox') BEGIN
 SELECT CASE WHEN EXISTS(SELECT 1 FROM commerce_order_payment_routes r,json_each(r.snapshot_data,'$.items') j
 JOIN commerce_order_items i ON i.order_id=r.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 LEFT JOIN membership_order_snapshots m ON m.item_id=i.id
 WHERE r.order_id=NEW.order_id AND r.mode='enforced_sandbox' AND  json_extract(j.value,'$.type')='membership' AND
 (m.item_id IS NULL OR m.owner!=r.owner OR m.order_id!=r.order_id
 OR m.plan_id IS NOT json_extract(j.value,'$.membershipTerms.id')
 OR m.plan_version IS NOT json_extract(j.value,'$.membershipTerms.version')
 OR m.group_id IS NOT json_extract(j.value,'$.membershipTerms.groupId')
 OR json_remove(m.data,'$.snapshotAt','$.snapshotSchema','$.renewalOf') IS NOT json_extract(j.value,'$.membershipTerms')))
 OR EXISTS(SELECT 1 FROM commerce_order_payment_routes r,json_each(r.snapshot_data,'$.items') j
 JOIN commerce_order_items i ON i.order_id=r.order_id AND i.sku_id=json_extract(j.value,'$.skuId')
 LEFT JOIN digital_order_snapshots d ON d.item_id=i.id
 WHERE r.order_id=NEW.order_id AND r.mode='enforced_sandbox' AND  json_extract(j.value,'$.type')='digital' AND
 ((d.item_id IS NULL AND coalesce(json_type(j.value,'$.digitalTerms'),'')!='null')
 OR (d.item_id IS NOT NULL AND (coalesce(json_type(j.value,'$.digitalTerms'),'')!='object'
 OR d.owner!=r.owner OR d.order_id!=r.order_id OR d.content_id IS NOT json_extract(j.value,'$.digitalTerms.contentId')
 OR d.media_id IS NOT json_extract(j.value,'$.digitalTerms.mediaId')
 OR json(d.policy_snapshot) IS NOT json_remove(json_extract(j.value,'$.digitalTerms'),'$.contentId','$.mediaId')))))
 THEN RAISE(ABORT,'payment_routing_terms_changed') END;
END;
--> statement-breakpoint
INSERT OR IGNORE INTO settings VALUES('payment_routing_schema_v1','true');
