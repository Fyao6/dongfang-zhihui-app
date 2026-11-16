// Standalone B11 provenance helpers. No storage, event handlers, calculation rules or network calls.
// Integration must supply a release manifest and continue using the existing account-scoped archive.
(function (root) {
  'use strict';
  const SCHEMA = 1, LIMIT = 20, MAX_CHARACTERS = 4500000;
  function fail(code, message) { const e = new Error(message); e.code = code; throw e; }
  function canonical(value) {
    const seen = new Set();
    function visit(v, depth) {
      if (depth > 64) fail('VERSION_DATA', 'Result data is too deeply nested.');
      if (v === null || typeof v === 'string' || typeof v === 'boolean') return JSON.stringify(v);
      if (typeof v === 'number' && Number.isFinite(v)) return JSON.stringify(v);
      if (!v || typeof v !== 'object' || seen.has(v)) fail('VERSION_DATA', 'Expected finite, acyclic JSON data.');
      const proto = Object.getPrototypeOf(v);
      if (!Array.isArray(v) && proto !== Object.prototype && proto !== null) fail('VERSION_DATA', 'Expected plain JSON objects.');
      seen.add(v);
      let answer;
      if (Array.isArray(v)) {
        const values = [];
        for (let i = 0; i < v.length; i++) {
          const d = Object.getOwnPropertyDescriptor(v, String(i));
          if (!d || !Object.prototype.hasOwnProperty.call(d, 'value')) fail('VERSION_DATA', 'Sparse arrays and accessors are unsupported.');
          values.push(visit(d.value, depth + 1));
        }
        answer = '[' + values.join(',') + ']';
      } else {
        answer = '{' + Object.keys(v).sort().map(k => {
          const d = Object.getOwnPropertyDescriptor(v, k);
          if (!d || !Object.prototype.hasOwnProperty.call(d, 'value')) fail('VERSION_DATA', 'Accessors are unsupported.');
          return JSON.stringify(k) + ':' + visit(d.value, depth + 1);
        }).join(',') + '}';
      }
      seen.delete(v);
      return answer;
    }
    const answer = visit(value, 0);
    if (answer.length > MAX_CHARACTERS) fail('VERSION_SIZE', 'Result exceeds the existing archive character limit.');
    return answer;
  }
  const copy = v => { canonical(v); return JSON.parse(JSON.stringify(v)); };
  const text = (v, code, max = 160) => {
    if (typeof v !== 'string' || !v.trim() || v.length > max) fail(code, 'A bounded, non-empty string is required.');
    return v;
  };
  const iso = (v, code) => {
    if (typeof v !== 'string' || !Number.isFinite(Date.parse(v))) fail(code, 'An explicit valid timestamp is required.');
    return new Date(v).toISOString();
  };
  const id = v => text(v, 'VERSION_ID', 99);
  function manifest(value) {
    if (!value || typeof value !== 'object') fail('VERSION_MANIFEST', 'The release manifest is required.');
    return {engine: {name: text(value.engine?.name, 'VERSION_MANIFEST'), version: text(value.engine?.version, 'VERSION_MANIFEST')},
      ruleVersion: text(value.ruleVersion, 'VERSION_MANIFEST'), adapterVersion: text(value.adapterVersion, 'VERSION_MANIFEST'), teacherConfirmed: false};
  }
  async function hash(value) {
    if (!root.crypto?.subtle) fail('VERSION_CRYPTO', 'SHA-256 is unavailable; provenance cannot be created.');
    const bytes = new TextEncoder().encode(canonical(value));
    const digest = await root.crypto.subtle.digest('SHA-256', bytes);
    return 'sha256:' + [...new Uint8Array(digest)].map(n => n.toString(16).padStart(2, '0')).join('');
  }
  function calculation(record) {
    if (!record || record.kind !== 'bazi' || !record.birth || !record.normalized || !record.result) fail('VERSION_CHART', 'A complete Ba Zi chart is required.');
    if (canonical(record.birth) !== canonical(record.normalized.birth)) fail('VERSION_INPUT', 'Archived birth values disagree with the normalized snapshot.');
    iso(record.normalized.utc, 'VERSION_INPUT');
    if (!record.normalized.china || !['male', 'female'].includes(record.birth.sex)) fail('VERSION_INPUT', 'Archived calculation input is incomplete.');
    return {birth: copy(record.birth), normalized: copy(record.normalized), options: copy(record.options || {})};
  }
  async function facts(record, release) {
    const input = calculation(record), m = manifest(release);
    if (!record.result.engine || !record.result.rules || record.result.kind !== 'bazi') fail('VERSION_RESULT', 'Result engine and rules are required.');
    if (record.result.engine.name !== m.engine.name || record.result.engine.version !== m.engine.version) fail('VERSION_ENGINE', 'The result does not match the declared engine.');
    const inputFingerprint = await hash(input), rulesFingerprint = await hash(record.result.rules), outputFingerprint = await hash(record.result);
    return {manifest: m, inputFingerprint, rulesFingerprint, outputFingerprint,
      cacheKey: 'bazi:v1:' + (await hash({schema: SCHEMA, input, manifest: m, rules: record.result.rules})).slice(7)};
  }
  async function captureCalculation(args) {
    if (!args || !args.normalized || !args.result) fail('VERSION_CHART', 'A freshly calculated input and result are required.');
    const normalized = copy(args.normalized), result = copy(args.result), recordId = id(args.id);
    const capturedAt = iso(args.capturedAt ?? new Date().toISOString(), 'VERSION_TIME');
    const record = {schema: 1, id: recordId, kind: 'bazi', title: String(args.title || normalized.birth?.name || 'Ba Zi chart'),
      birth: copy(normalized.birth), normalized, options: copy(args.options || {}), result,
      engine: copy(result.engine), rules: copy(result.rules), savedAt: capturedAt};
    if (args.view !== undefined) record.view = copy(args.view);
    const f = await facts(record, args.manifest);
    record.provenance = {schema: SCHEMA, recordId, rootRecordId: recordId, parentRecordId: null,
      capturedAt, calculatedAt: args.calculatedAt == null ? null : iso(args.calculatedAt, 'VERSION_TIME'), ...f};
    return record;
  }
  async function inspectSnapshot(source, currentManifest) {
    const record = copy(source);
    id(record.id);
    if (record.kind !== 'bazi' || !record.birth || !record.normalized || !record.result || typeof record.result !== 'object')
      fail('VERSION_CHART', 'An archived Ba Zi chart is required.');
    iso(record.normalized.utc, 'VERSION_INPUT');
    const p = record.provenance;
    if (!p) return {state: 'legacy-unverified', cacheReusable: false, recordId: record.id,
      calculatedAt: null, savedAt: record.savedAt ?? null, reason: 'The original record has no provenance; its original bytes and timestamps must remain unchanged.'};
    calculation(record);
    if (p.schema !== SCHEMA || p.recordId !== record.id) fail('VERSION_INTEGRITY', 'The provenance identity is invalid.');
    if (canonical(record.engine) !== canonical(record.result.engine) || canonical(record.rules) !== canonical(record.result.rules))
      fail('VERSION_INTEGRITY', 'Display metadata disagrees with the saved result.');
    id(p.rootRecordId);
    if (p.parentRecordId !== null) {
      id(p.parentRecordId);
      if (p.parentRecordId === record.id) fail('VERSION_INTEGRITY', 'A version cannot be its own parent.');
    } else if (p.rootRecordId !== record.id) fail('VERSION_INTEGRITY', 'An original version must be its own root.');
    iso(p.capturedAt, 'VERSION_TIME');
    if (p.calculatedAt !== null) iso(p.calculatedAt, 'VERSION_TIME');
    const f = await facts(record, p.manifest);
    for (const field of ['inputFingerprint', 'rulesFingerprint', 'outputFingerprint', 'cacheKey'])
      if (p[field] !== f[field]) fail('VERSION_INTEGRITY', 'The saved ' + field + ' no longer matches the snapshot.');
    const current = manifest(currentManifest), unchanged = canonical(current) === canonical(f.manifest);
    return {state: unchanged ? 'current' : 'outdated', cacheReusable: unchanged, recordId: record.id,
      cacheKey: f.cacheKey, outputFingerprint: f.outputFingerprint, calculatedAt: p.calculatedAt,
      savedAt: record.savedAt ?? null, manifest: f.manifest, currentManifest: current,
      engineChanged: canonical(current.engine) !== canonical(f.manifest.engine),
      ruleChanged: current.ruleVersion !== f.manifest.ruleVersion, adapterChanged: current.adapterVersion !== f.manifest.adapterVersion};
  }
  function active(args) {
    if (typeof args.isCurrent !== 'function' || args.isCurrent(args.context) !== true) fail('VERSION_CONTEXT', 'The account or action context changed.');
  }
  async function recalculate(args) {
    if (!args || args.confirmed !== true) fail('VERSION_CONFIRM', 'Explicit confirmation is required before recalculating.');
    active(args);
    if (typeof args.compute !== 'function') fail('VERSION_COMPUTE', 'The existing deterministic Ba Zi adapter is required.');
    const old = copy(args.record), release = manifest(args.manifest);
    await inspectSnapshot(old, release);
    active(args);
    const recordId = id(args.id || ('bzv-' + root.crypto.randomUUID()));
    if (recordId === old.id) fail('VERSION_OVERWRITE', 'Recalculation must use a new record ID.');
    const input = calculation(old), clock = args.clock || (() => Date.now()), startedAt = new Date(clock()).toISOString();
    const result = await args.compute(copy(input.normalized), copy(input.options));
    active(args);
    const next = await captureCalculation({id: recordId, title: old.title, normalized: input.normalized, options: input.options,
      result, manifest: release, calculatedAt: startedAt, capturedAt: new Date(clock()).toISOString(), ...(old.view ? {view: old.view} : {})});
    next.provenance.parentRecordId = old.id;
    next.provenance.rootRecordId = old.provenance?.rootRecordId || old.id;
    active(args);
    return next;
  }
  async function appendVersion(records, candidate, currentManifest) {
    if (!Array.isArray(records)) fail('VERSION_ARCHIVE', 'The existing account-scoped archive array is required.');
    const rows = copy(records), next = copy(candidate);
    const nextStatus = await inspectSnapshot(next, currentManifest);
    if (!next.provenance) fail('VERSION_ARCHIVE', 'A new version must have provenance.');
    if (!nextStatus.cacheReusable) fail('VERSION_STALE', 'The release changed before this new version was saved. Reconfirm recalculation.');
    if (rows.some(row => row?.id === next.id)) fail('VERSION_OVERWRITE', 'Existing archive IDs are immutable.');
    if (rows.length >= LIMIT) fail('VERSION_LIMIT', 'The 20-chart archive is full. Export or explicitly delete a record first.');
    if (next.provenance.parentRecordId !== null) {
      const parent = rows.find(row => row?.kind === 'bazi' && row.id === next.provenance.parentRecordId);
      if (!parent || (parent.provenance?.rootRecordId || parent.id) !== next.provenance.rootRecordId)
        fail('VERSION_LINEAGE', 'The original parent must still exist in this account archive.');
      await inspectSnapshot(parent, currentManifest);
      if (canonical(calculation(parent)) !== canonical(calculation(next)))
        fail('VERSION_INPUT', 'A version upgrade must preserve the archived calculation input.');
    }
    const answer = [next, ...rows];
    canonical(answer);
    return answer;
  }
  async function bindInterpretation(record, reference, currentManifest) {
    const status = await inspectSnapshot(record, currentManifest);
    if (!status.cacheReusable) fail('VERSION_AI_UNVERIFIED', 'Only a current, verified chart may bind a new interpretation.');
    return {schema: 1, interpretationId: text(reference?.id, 'VERSION_AI_ID', 160),
      recordId: status.recordId, cacheKey: status.cacheKey, outputFingerprint: status.outputFingerprint};
  }
  async function interpretationStatus(record, binding, currentManifest) {
    const status = await inspectSnapshot(record, currentManifest);
    if (!binding || binding.schema !== 1 || !status.cacheKey) return {state: 'unbound', reusable: false};
    const matches = binding.recordId === status.recordId && binding.cacheKey === status.cacheKey && binding.outputFingerprint === status.outputFingerprint;
    return {state: !matches ? 'mismatched' : status.cacheReusable ? 'current' : 'historical', reusable: matches && status.cacheReusable};
  }
  const api = Object.freeze({schema: SCHEMA, archiveLimit: LIMIT, canonical, fingerprint: hash, manifest, captureCalculation,
    inspectSnapshot, recalculate, appendVersion, bindInterpretation, interpretationStatus});
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.BaziResultVersion = api;
})(typeof globalThis === 'object' ? globalThis : this);

