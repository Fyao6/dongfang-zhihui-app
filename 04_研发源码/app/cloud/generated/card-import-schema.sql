-- Shared verbatim by SQLite and D1. Private import input is never public deck authority.
CREATE TABLE IF NOT EXISTS card_import_jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,request_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,canonical_sha256 TEXT NOT NULL,payload_data TEXT NOT NULL,raw_data TEXT NOT NULL,base_version_id TEXT NOT NULL,base_revision INTEGER,base_data TEXT NOT NULL,epoch INTEGER NOT NULL,preview_data TEXT NOT NULL,status TEXT NOT NULL,version INTEGER NOT NULL,result_version_id TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,erased_at INTEGER NOT NULL DEFAULT 0,UNIQUE(owner,request_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS card_deck_sources(id TEXT PRIMARY KEY,owner TEXT NOT NULL,deck_version_id TEXT NOT NULL,source_data TEXT NOT NULL,digest TEXT NOT NULL,created INTEGER NOT NULL);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS card_import_diagnostics(job_id TEXT NOT NULL,owner TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('issues','diff')),ordinal INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(job_id,kind,ordinal));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS card_import_receipts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,job_id TEXT NOT NULL,request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,result_data TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,request_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS card_deck_activation_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,request_id TEXT NOT NULL,fingerprint TEXT NOT NULL,result_data TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,request_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS card_import_guards(id TEXT PRIMARY KEY,owner TEXT NOT NULL,session_hash TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS card_import_erase_guards(id TEXT PRIMARY KEY,owner TEXT NOT NULL,source TEXT NOT NULL,receipt_id TEXT NOT NULL,created INTEGER NOT NULL);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS card_import_jobs_owner ON card_import_jobs(owner,created,id);
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_guard_check BEFORE INSERT ON card_import_guards BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.id=NEW.owner AND u.role='admin' AND s.token=NEW.session_hash AND s.expires>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)) AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')) THEN RAISE(ABORT,'account_actor_inactive') END;
 SELECT CASE WHEN json_type(NEW.data,'$.epoch') IS NOT NULL AND coalesce((SELECT revision FROM card_record_epochs WHERE owner=NEW.owner),0)!=json_extract(NEW.data,'$.epoch') THEN RAISE(ABORT,'card_import_erased') END;
 SELECT CASE WHEN json_extract(NEW.data,'$.jobId') IS NOT NULL AND NOT EXISTS(SELECT 1 FROM card_import_jobs j WHERE j.id=json_extract(NEW.data,'$.jobId') AND j.owner=NEW.owner AND j.erased_at=0 AND j.version=json_extract(NEW.data,'$.version') AND j.status=json_extract(NEW.data,'$.status')) THEN RAISE(ABORT,'card_import_changed') END;
 SELECT CASE WHEN json_extract(NEW.data,'$.baseId') IS NOT NULL AND NOT EXISTS(SELECT 1 FROM card_deck_versions b WHERE b.id=json_extract(NEW.data,'$.baseId') AND b.revision=json_extract(NEW.data,'$.baseRevision') AND b.data=json_extract(NEW.data,'$.baseData')) THEN RAISE(ABORT,'card_import_base_changed') END;
 SELECT CASE WHEN json_extract(NEW.data,'$.nextVersion') IS NOT NULL AND json_extract(NEW.data,'$.nextVersion')!=(SELECT coalesce(max(version),0)+1 FROM card_deck_versions WHERE deck_id=json_extract(NEW.data,'$.deckId') AND environment=json_extract(NEW.data,'$.environment')) THEN RAISE(ABORT,'card_import_version_changed') END;
 SELECT CASE WHEN json_extract(NEW.data,'$.configData') IS NOT NULL AND NOT EXISTS(SELECT 1 FROM settings WHERE key='card_service' AND data=json_extract(NEW.data,'$.configData')) THEN RAISE(ABORT,'card_activation_changed') END;
 SELECT CASE WHEN json_extract(NEW.data,'$.targetId') IS NOT NULL AND NOT EXISTS(SELECT 1 FROM card_deck_versions v WHERE v.id=json_extract(NEW.data,'$.targetId') AND v.environment=json_extract(NEW.data,'$.environment') AND v.status='published' AND v.revision=json_extract(NEW.data,'$.targetRevision') AND v.data=json_extract(NEW.data,'$.targetData')) THEN RAISE(ABORT,'card_activation_changed') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM json_each(NEW.data,'$.media') x WHERE NOT EXISTS(SELECT 1 FROM media m WHERE m.id=json_extract(x.value,'$.id') AND m.owner=json_extract(x.value,'$.owner') AND m.mime=json_extract(x.value,'$.mime') AND m.mime LIKE 'image/%' AND NOT EXISTS(SELECT 1 FROM privacy_media_tombstones t WHERE t.media_id=m.id) AND NOT EXISTS(SELECT 1 FROM digital_sandbox_assets d WHERE d.media_id=m.id))) THEN RAISE(ABORT,'card_import_media_changed') END;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM json_each(NEW.data,'$.courses') x WHERE NOT EXISTS(SELECT 1 FROM contents c WHERE c.kind='courses' AND c.id=x.value AND c.status='published')) THEN RAISE(ABORT,'card_import_course_changed') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_guard_forget AFTER INSERT ON card_import_guards BEGIN DELETE FROM card_import_guards WHERE id=NEW.id; END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_deck_frozen_update BEFORE UPDATE ON card_deck_versions WHEN OLD.status IN ('published','withdrawn') AND (NEW.id IS NOT OLD.id OR NEW.deck_id IS NOT OLD.deck_id OR NEW.version IS NOT OLD.version OR NEW.environment IS NOT OLD.environment OR NEW.data IS NOT OLD.data OR NEW.created IS NOT OLD.created) BEGIN SELECT RAISE(ABORT,'card_deck_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_deck_frozen_status BEFORE UPDATE ON card_deck_versions WHEN (OLD.status='published' AND NEW.status NOT IN ('published','withdrawn')) OR (OLD.status='withdrawn' AND NEW.status!='withdrawn') BEGIN SELECT RAISE(ABORT,'card_deck_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_deck_no_replace BEFORE INSERT ON card_deck_versions WHEN EXISTS(SELECT 1 FROM card_deck_versions v WHERE v.id=NEW.id OR (v.deck_id=NEW.deck_id AND v.version=NEW.version AND v.environment=NEW.environment)) BEGIN SELECT RAISE(ABORT,'card_deck_replace_forbidden'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_deck_withdrawal_monotonic BEFORE UPDATE ON card_deck_versions WHEN (OLD.status='withdrawn' AND NEW.status!='withdrawn') OR (CASE NEW.withdrawal_kind WHEN 'license' THEN 2 WHEN 'content-error' THEN 1 ELSE 0 END)<(CASE OLD.withdrawal_kind WHEN 'license' THEN 2 WHEN 'content-error' THEN 1 ELSE 0 END) BEGIN SELECT RAISE(ABORT,'card_withdrawal_downgrade'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_deck_protected_delete BEFORE DELETE ON card_deck_versions WHEN OLD.status IN ('published','withdrawn') OR EXISTS(SELECT 1 FROM card_draws WHERE deck_version_id=OLD.id) OR EXISTS(SELECT 1 FROM card_deck_sources WHERE deck_version_id=OLD.id) OR EXISTS(SELECT 1 FROM card_import_jobs WHERE base_version_id=OLD.id OR result_version_id=OLD.id) OR EXISTS(SELECT 1 FROM settings WHERE key='card_service' AND (json_extract(data,'$.activeSandboxDeck')=OLD.id OR json_extract(data,'$.activeProductionDeck')=OLD.id)) BEGIN SELECT RAISE(ABORT,'card_deck_protected'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_erase_check BEFORE INSERT ON card_import_erase_guards WHEN NOT ((NEW.source='privacy' AND EXISTS(SELECT 1 FROM privacy_requests WHERE id=NEW.receipt_id AND user_id=NEW.owner AND kind='delete-records')) OR (NEW.source='closure' AND EXISTS(SELECT 1 FROM account_closure_receipts WHERE id=NEW.receipt_id AND owner=NEW.owner))) BEGIN SELECT RAISE(ABORT,'card_import_erase_denied'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_erase_apply AFTER INSERT ON card_import_erase_guards BEGIN
 DELETE FROM card_import_diagnostics WHERE owner=NEW.owner;
 UPDATE card_import_jobs SET payload_data='{}',raw_data='',base_data='',preview_data='{}',status='erased',version=version+1,updated=NEW.created,erased_at=NEW.created WHERE owner=NEW.owner AND erased_at=0;
 UPDATE card_deck_sources SET source_data='{}' WHERE owner=NEW.owner AND source_data!='{}';
 UPDATE card_import_receipts SET result_data=json_object('receipt',json_extract(result_data,'$.receipt'),'erased',json('true')) WHERE owner=NEW.owner AND coalesce(json_extract(result_data,'$.erased'),0)!=1;
 UPDATE card_deck_activation_events SET result_data=json_remove(result_data,'$.receipt.reason') WHERE owner=NEW.owner AND json_type(result_data,'$.receipt.reason') IS NOT NULL;
 DELETE FROM card_import_erase_guards WHERE id=NEW.id;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_source_identity BEFORE UPDATE ON card_deck_sources WHEN NEW.id IS NOT OLD.id OR NEW.owner IS NOT OLD.owner OR NEW.deck_version_id IS NOT OLD.deck_version_id OR NEW.digest IS NOT OLD.digest OR NEW.created IS NOT OLD.created OR (NEW.source_data IS NOT OLD.source_data AND NOT EXISTS(SELECT 1 FROM card_import_erase_guards WHERE owner=OLD.owner)) BEGIN SELECT RAISE(ABORT,'card_import_source_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_job_identity BEFORE UPDATE ON card_import_jobs WHEN NEW.id IS NOT OLD.id OR NEW.owner IS NOT OLD.owner OR NEW.request_id IS NOT OLD.request_id OR NEW.source_sha256 IS NOT OLD.source_sha256 OR NEW.canonical_sha256 IS NOT OLD.canonical_sha256 OR NEW.base_version_id IS NOT OLD.base_version_id OR NEW.base_revision IS NOT OLD.base_revision OR NEW.epoch IS NOT OLD.epoch OR NEW.created IS NOT OLD.created OR ((NEW.payload_data IS NOT OLD.payload_data OR NEW.raw_data IS NOT OLD.raw_data OR NEW.base_data IS NOT OLD.base_data OR NEW.preview_data IS NOT OLD.preview_data) AND NOT EXISTS(SELECT 1 FROM card_import_erase_guards WHERE owner=OLD.owner)) BEGIN SELECT RAISE(ABORT,'card_import_job_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_receipt_identity BEFORE UPDATE ON card_import_receipts WHEN NOT EXISTS(SELECT 1 FROM card_import_erase_guards WHERE owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'card_import_receipt_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_activation_receipt_identity BEFORE UPDATE ON card_deck_activation_events WHEN NOT EXISTS(SELECT 1 FROM card_import_erase_guards WHERE owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'card_import_receipt_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_diagnostics_update BEFORE UPDATE ON card_import_diagnostics BEGIN SELECT RAISE(ABORT,'card_import_diagnostics_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_diagnostics_delete BEFORE DELETE ON card_import_diagnostics WHEN NOT EXISTS(SELECT 1 FROM card_import_erase_guards WHERE owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'card_import_diagnostics_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS card_import_diagnostics_parent BEFORE INSERT ON card_import_diagnostics WHEN NOT EXISTS(SELECT 1 FROM card_import_jobs j WHERE j.id=NEW.job_id AND j.owner=NEW.owner AND j.erased_at=0 AND j.epoch=coalesce((SELECT revision FROM card_record_epochs WHERE owner=NEW.owner),0)) BEGIN SELECT RAISE(ABORT,'card_import_erased'); END;
