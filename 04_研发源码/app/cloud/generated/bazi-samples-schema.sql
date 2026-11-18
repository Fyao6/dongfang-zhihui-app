-- Private, owner-scoped sample evidence. Shared verbatim by SQLite and D1.
CREATE TABLE IF NOT EXISTS bazi_sample_owner_state(owner TEXT PRIMARY KEY,epoch INTEGER NOT NULL CHECK(epoch>=1),updated INTEGER NOT NULL);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_sets(id TEXT PRIMARY KEY,owner TEXT NOT NULL,set_key TEXT NOT NULL,title TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(owner,set_key));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_versions(id TEXT PRIMARY KEY,owner TEXT NOT NULL,set_id TEXT NOT NULL,version_key TEXT NOT NULL,source_sha256 TEXT NOT NULL,source_bytes INTEGER NOT NULL,canonical_sha256 TEXT NOT NULL,canonical_bytes INTEGER NOT NULL,case_order TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL,erased_at INTEGER NOT NULL DEFAULT 0,UNIQUE(owner,set_id,version_key));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_cases(version_id TEXT NOT NULL,case_id TEXT NOT NULL,owner TEXT NOT NULL,ordinal INTEGER NOT NULL,data TEXT NOT NULL,canonical_sha256 TEXT NOT NULL,canonical_bytes INTEGER NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(version_id,case_id),UNIQUE(version_id,ordinal));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_runs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,version_id TEXT NOT NULL,request_id TEXT NOT NULL,intent_fingerprint TEXT NOT NULL,case_ids TEXT NOT NULL,manifest_data TEXT NOT NULL,manifest_hash TEXT NOT NULL,epoch INTEGER NOT NULL,state TEXT NOT NULL CHECK(state IN ('pending','processing','completed','erased')),version INTEGER NOT NULL,total INTEGER NOT NULL,processed INTEGER NOT NULL DEFAULT 0,succeeded INTEGER NOT NULL DEFAULT 0,failed INTEGER NOT NULL DEFAULT 0,blocked INTEGER NOT NULL DEFAULT 0,counts TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,erased_at INTEGER NOT NULL DEFAULT 0,UNIQUE(owner,request_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_workitems(id TEXT PRIMARY KEY,owner TEXT NOT NULL,run_id TEXT NOT NULL,case_id TEXT NOT NULL,ordinal INTEGER NOT NULL,state TEXT NOT NULL CHECK(state IN ('pending','processing','succeeded','blocked','failed')),attempts INTEGER NOT NULL DEFAULT 0,lease_token TEXT NOT NULL DEFAULT '',lease_until INTEGER NOT NULL DEFAULT 0,last_error TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(run_id,case_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_results(id TEXT PRIMARY KEY,owner TEXT NOT NULL,run_id TEXT NOT NULL,case_id TEXT NOT NULL,status TEXT NOT NULL,error_code TEXT NOT NULL,data TEXT NOT NULL,raw_index TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(run_id,case_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_raw_chunks(id TEXT PRIMARY KEY,owner TEXT NOT NULL,result_id TEXT NOT NULL,section TEXT NOT NULL CHECK(section IN ('header','period')),period_index INTEGER NOT NULL,chunk_index INTEGER NOT NULL,data TEXT NOT NULL,sha256 TEXT NOT NULL,byte_length INTEGER NOT NULL CHECK(byte_length<=65536),created INTEGER NOT NULL,UNIQUE(result_id,section,period_index,chunk_index));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_field_results(id TEXT PRIMARY KEY,owner TEXT NOT NULL,result_id TEXT NOT NULL,path TEXT NOT NULL,data TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(result_id,path));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_reviews(id TEXT PRIMARY KEY,owner TEXT NOT NULL,result_id TEXT NOT NULL,field_id TEXT NOT NULL,request_id TEXT NOT NULL,intent_fingerprint TEXT NOT NULL,category TEXT NOT NULL,evidence TEXT NOT NULL,note TEXT NOT NULL,retest_run_id TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,request_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_operations(id TEXT PRIMARY KEY,owner TEXT NOT NULL,request_id TEXT NOT NULL,kind TEXT NOT NULL,intent_fingerprint TEXT NOT NULL,response_data TEXT NOT NULL,created INTEGER NOT NULL,UNIQUE(owner,kind,request_id));
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS bazi_sample_erase_guards(id TEXT PRIMARY KEY,owner TEXT NOT NULL,epoch INTEGER NOT NULL,source TEXT NOT NULL,receipt_id TEXT NOT NULL,created INTEGER NOT NULL);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS bazi_sample_versions_owner ON bazi_sample_versions(owner,created,id);
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS bazi_sample_runs_owner ON bazi_sample_runs(owner,created,id);
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_erase_check BEFORE INSERT ON bazi_sample_erase_guards BEGIN
 SELECT CASE WHEN NEW.epoch!=coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=NEW.owner),1) OR EXISTS(SELECT 1 FROM bazi_sample_operations WHERE owner=NEW.owner AND kind='erase' AND request_id=NEW.receipt_id) OR NOT ((NEW.source='privacy' AND EXISTS(SELECT 1 FROM privacy_requests WHERE id=NEW.receipt_id AND user_id=NEW.owner AND kind='delete-records')) OR (NEW.source='closure' AND EXISTS(SELECT 1 FROM account_closure_receipts WHERE id=NEW.receipt_id AND owner=NEW.owner))) THEN RAISE(ABORT,'bazi_sample_erase_denied') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_erase_apply AFTER INSERT ON bazi_sample_erase_guards BEGIN
 INSERT INTO bazi_sample_owner_state VALUES(NEW.owner,NEW.epoch+1,NEW.created) ON CONFLICT(owner) DO UPDATE SET epoch=excluded.epoch,updated=excluded.updated;
 INSERT INTO bazi_sample_operations VALUES(NEW.id,NEW.owner,NEW.receipt_id,'erase','',json_object('cases',(SELECT count(*) FROM bazi_sample_cases WHERE owner=NEW.owner),'results',(SELECT count(*) FROM bazi_sample_results WHERE owner=NEW.owner),'rawChunks',(SELECT count(*) FROM bazi_sample_raw_chunks WHERE owner=NEW.owner),'reviews',(SELECT count(*) FROM bazi_sample_reviews WHERE owner=NEW.owner),'retentionDays',NULL,'secureWipe',json('false')),NEW.created);
 DELETE FROM bazi_sample_field_results WHERE owner=NEW.owner;
 DELETE FROM bazi_sample_raw_chunks WHERE owner=NEW.owner;
 DELETE FROM bazi_sample_reviews WHERE owner=NEW.owner;
 DELETE FROM bazi_sample_results WHERE owner=NEW.owner;
 DELETE FROM bazi_sample_workitems WHERE owner=NEW.owner;
 DELETE FROM bazi_sample_cases WHERE owner=NEW.owner;
 UPDATE bazi_sample_versions SET data='{}',case_order='[]',version_key=id,erased_at=NEW.created WHERE owner=NEW.owner AND erased_at=0;
 UPDATE bazi_sample_sets SET title='',set_key=id,updated=NEW.created WHERE owner=NEW.owner;
 UPDATE bazi_sample_runs SET state='erased',case_ids='[]',erased_at=NEW.created,version=version+1,updated=NEW.created WHERE owner=NEW.owner AND erased_at=0;
 UPDATE bazi_sample_operations SET response_data='{}' WHERE owner=NEW.owner AND kind!='erase';
 DELETE FROM bazi_sample_erase_guards WHERE id=NEW.id;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_atomic_guard BEFORE INSERT ON bazi_sample_operations WHEN NEW.kind='guard' BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.id=NEW.owner AND u.role='admin' AND s.token=json_extract(NEW.response_data,'$.sessionHash') AND s.expires>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)) AND NOT EXISTS(SELECT 1 FROM account_lifecycle l WHERE l.owner=u.id AND l.status='closed')) THEN RAISE(ABORT,'account_actor_inactive') END;
 SELECT CASE WHEN coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=NEW.owner),1)!=json_extract(NEW.response_data,'$.epoch') THEN RAISE(ABORT,'bazi_sample_erased') END;
 SELECT CASE WHEN json_extract(NEW.response_data,'$.runId') IS NOT NULL AND NOT EXISTS(SELECT 1 FROM bazi_sample_runs r WHERE r.id=json_extract(NEW.response_data,'$.runId') AND r.owner=NEW.owner AND r.erased_at=0 AND r.epoch=json_extract(NEW.response_data,'$.epoch') AND r.version=json_extract(NEW.response_data,'$.version') AND r.manifest_hash=json_extract(NEW.response_data,'$.manifestHash')) THEN RAISE(ABORT,'bazi_sample_changed') END;
 SELECT CASE WHEN json_extract(NEW.response_data,'$.phase')='final' AND NOT EXISTS(SELECT 1 FROM bazi_sample_workitems w WHERE w.id=json_extract(NEW.response_data,'$.workId') AND w.owner=NEW.owner AND w.run_id=json_extract(NEW.response_data,'$.runId') AND w.state='processing' AND w.lease_token=json_extract(NEW.response_data,'$.leaseToken') AND w.lease_until>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))) THEN RAISE(ABORT,'bazi_sample_lease_lost') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_atomic_forget AFTER INSERT ON bazi_sample_operations WHEN NEW.kind='guard' BEGIN DELETE FROM bazi_sample_operations WHERE id=NEW.id; END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_case_parent BEFORE INSERT ON bazi_sample_cases BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_versions v WHERE v.id=NEW.version_id AND v.owner=NEW.owner AND v.erased_at=0) THEN RAISE(ABORT,'bazi_sample_parent_invalid') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_work_parent BEFORE INSERT ON bazi_sample_workitems BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_runs r JOIN bazi_sample_cases c ON c.version_id=r.version_id AND c.case_id=NEW.case_id AND c.owner=r.owner WHERE r.id=NEW.run_id AND r.owner=NEW.owner AND r.erased_at=0 AND r.epoch=coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=NEW.owner),1)) THEN RAISE(ABORT,'bazi_sample_parent_invalid') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_result_parent BEFORE INSERT ON bazi_sample_results BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_runs r JOIN bazi_sample_workitems w ON w.run_id=r.id AND w.case_id=NEW.case_id AND w.owner=r.owner WHERE r.id=NEW.run_id AND r.owner=NEW.owner AND r.erased_at=0 AND r.epoch=coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=NEW.owner),1) AND w.state='processing' AND w.lease_until>(CAST(strftime('%s','now') AS INTEGER)*1000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER))) THEN RAISE(ABORT,'bazi_sample_result_invalid') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_run_parent BEFORE INSERT ON bazi_sample_runs BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_versions v WHERE v.id=NEW.version_id AND v.owner=NEW.owner AND v.erased_at=0) OR NEW.epoch!=coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=NEW.owner),1) THEN RAISE(ABORT,'bazi_sample_erased') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_chunk_parent BEFORE INSERT ON bazi_sample_raw_chunks BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_results x JOIN bazi_sample_runs r ON r.id=x.run_id AND r.owner=x.owner WHERE x.id=NEW.result_id AND x.owner=NEW.owner AND r.erased_at=0 AND r.epoch=coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=NEW.owner),1)) THEN RAISE(ABORT,'bazi_sample_parent_invalid') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_field_parent BEFORE INSERT ON bazi_sample_field_results BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_results x JOIN bazi_sample_runs r ON r.id=x.run_id AND r.owner=x.owner WHERE x.id=NEW.result_id AND x.owner=NEW.owner AND r.erased_at=0 AND r.epoch=coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=NEW.owner),1)) THEN RAISE(ABORT,'bazi_sample_parent_invalid') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_review_parent BEFORE INSERT ON bazi_sample_reviews BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_field_results f JOIN bazi_sample_results x ON x.id=f.result_id AND x.owner=f.owner JOIN bazi_sample_runs r ON r.id=x.run_id AND r.owner=x.owner WHERE f.id=NEW.field_id AND x.id=NEW.result_id AND x.owner=NEW.owner AND r.erased_at=0 AND r.epoch=coalesce((SELECT epoch FROM bazi_sample_owner_state WHERE owner=NEW.owner),1)) OR (NEW.retest_run_id!='' AND NOT EXISTS(SELECT 1 FROM bazi_sample_runs WHERE id=NEW.retest_run_id AND owner=NEW.owner AND erased_at=0)) THEN RAISE(ABORT,'bazi_sample_parent_invalid') END;
END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_epoch_update BEFORE UPDATE ON bazi_sample_owner_state WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards WHERE owner=OLD.owner AND epoch=OLD.epoch) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;
--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_epoch_delete BEFORE DELETE ON bazi_sample_owner_state BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_cases_update BEFORE UPDATE ON bazi_sample_cases WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_cases_delete BEFORE DELETE ON bazi_sample_cases WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_results_update BEFORE UPDATE ON bazi_sample_results WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_results_delete BEFORE DELETE ON bazi_sample_results WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_raw_chunks_update BEFORE UPDATE ON bazi_sample_raw_chunks WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_raw_chunks_delete BEFORE DELETE ON bazi_sample_raw_chunks WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_field_results_update BEFORE UPDATE ON bazi_sample_field_results WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_field_results_delete BEFORE DELETE ON bazi_sample_field_results WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_reviews_update BEFORE UPDATE ON bazi_sample_reviews WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_reviews_delete BEFORE DELETE ON bazi_sample_reviews WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_sets_delete BEFORE DELETE ON bazi_sample_sets WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_versions_delete BEFORE DELETE ON bazi_sample_versions WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_runs_delete BEFORE DELETE ON bazi_sample_runs WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_workitems_delete BEFORE DELETE ON bazi_sample_workitems WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_operations_delete BEFORE DELETE ON bazi_sample_operations WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) AND OLD.kind!='guard' BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_sets_identity BEFORE UPDATE OF id,owner,set_key,title,created ON bazi_sample_sets WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_versions_identity BEFORE UPDATE OF id,owner,set_id,version_key,source_sha256,source_bytes,canonical_sha256,canonical_bytes,case_order,data,created ON bazi_sample_versions WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_runs_identity BEFORE UPDATE OF id,owner,version_id,request_id,intent_fingerprint,case_ids,manifest_data,manifest_hash,epoch,total,created ON bazi_sample_runs WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_workitems_identity BEFORE UPDATE OF id,owner,run_id,case_id,ordinal,created ON bazi_sample_workitems WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_operations_identity BEFORE UPDATE OF id,owner,request_id,kind,intent_fingerprint,created ON bazi_sample_operations WHEN NOT EXISTS(SELECT 1 FROM bazi_sample_erase_guards g WHERE g.owner=OLD.owner) BEGIN SELECT RAISE(ABORT,'bazi_sample_immutable'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_sets_closed BEFORE INSERT ON bazi_sample_sets WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_versions_closed BEFORE INSERT ON bazi_sample_versions WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_runs_closed BEFORE INSERT ON bazi_sample_runs WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_workitems_closed BEFORE INSERT ON bazi_sample_workitems WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_results_closed BEFORE INSERT ON bazi_sample_results WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_raw_chunks_closed BEFORE INSERT ON bazi_sample_raw_chunks WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_field_results_closed BEFORE INSERT ON bazi_sample_field_results WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_reviews_closed BEFORE INSERT ON bazi_sample_reviews WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') BEGIN SELECT RAISE(ABORT,'account_closed'); END;

--> statement-breakpoint
CREATE TRIGGER IF NOT EXISTS bazi_sample_operations_closed BEFORE INSERT ON bazi_sample_operations WHEN EXISTS(SELECT 1 FROM account_lifecycle WHERE owner=NEW.owner AND status='closed') AND NEW.kind!='erase' BEGIN SELECT RAISE(ABORT,'account_closed'); END;
