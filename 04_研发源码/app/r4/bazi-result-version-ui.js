// Optional B11 UI integration. Merely loading this file does nothing.
// Call BaziVersionUI.install({manifest}) only after core, birth-entry and chart scripts load.
(function (root) {
  'use strict';
  let installed = false, release = null, runtime = null;
  const clone = v => JSON.parse(JSON.stringify(v));
  const label = (en, zh, hant, bo) => lcText(en, zh, hant, bo);
  const problem = (code, message) => Object.assign(new Error(message), {code});
  function tokenState() {
    const t = psToken();
    if (!runtime || runtime.scope !== t.scope || runtime.epoch !== t.epoch)
      runtime = {scope: t.scope, epoch: t.epoch, sequence: 0, busy: false, pending: null, error: '', lockUnavailable: false};
    return runtime;
  }
  function begin() {
    const r = tokenState(), token = psToken();
    const context = {runtime: r, sequence: ++r.sequence, token, page: state.page};
    r.busy = true; r.error = ''; r.pending = null;
    return context;
  }
  function active(context) {
    return !!context && psCurrent(context.token) && runtime === context.runtime &&
      context.sequence === runtime.sequence && state.page === context.page;
  }
  function mustBeCurrent(context) { if (!active(context)) throw problem('VERSION_CONTEXT', 'Account or page changed.'); }
  function inputStamp(s) { return BaziResultVersion.canonical({normalized: s.normalized, options: s.options, result: s.result}); }
  function unchangedInput(s, stamp) { return lcGet('bazi') === s && inputStamp(s) === stamp; }
  function lockAvailable() {
    try { return !tokenState().lockUnavailable && typeof root.navigator?.locks?.request === 'function'; }
    catch (_) { return false; }
  }
  function lockError() {
    return problem('VERSION_LOCK_UNAVAILABLE', label('Safe archive writes are unavailable in this browser. Viewing and export remain available; reopen in a supported browser to save or delete.',
      '当前浏览器暂不能安全保存或删除档案。仍可查看和导出，请使用支持此功能的浏览器。',
      '目前瀏覽器暫不能安全儲存或刪除檔案。仍可查看和匯出，請使用支援此功能的瀏覽器。',
      'བཤར་ཆས་འདིར་ཟིན་ཐོ་མཉམ་ལས་ཀྱིས་ཉར་མི་ཐུབ། ལྟ་བ་དང་ཕྱིར་འདོན་བྱེད་ཐུབ། མཉམ་ལས་སྒོ་ལྕགས་ཡོད་པའི་བཤར་ཆས་བཀོལ་རོགས།'));
  }
  async function withArchiveWriteLock(context, work) {
    mustBeCurrent(context);
    if (!lockAvailable()) throw lockError();
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 10000);
    let acquired = false;
    try {
      return await navigator.locks.request('ew-life-charts-write-v1:' + encodeURIComponent(context.token.scope),
        {mode: 'exclusive', signal: controller.signal}, async () => {
          acquired = true; clearTimeout(timer); mustBeCurrent(context);
          return await work();
        });
    } catch (e) {
      if (!acquired && e.name === 'AbortError') throw problem('VERSION_LOCK_TIMEOUT', label('Another tab is saving. Retry after it finishes.', '另一页面正在保存，请稍后重试。', '另一頁面正在儲存，請稍後重試。', 'ཤོག་ངོས་གཞན་ཞིག་ཉར་བཞིན་ཡོད། རྗེས་སུ་སླར་ཚོད་བྱོས།'));
      if (!acquired && ['SecurityError', 'NotSupportedError', 'InvalidStateError'].includes(e.name)) {
        if (active(context)) tokenState().lockUnavailable = true;
        throw lockError();
      }
      throw e;
    } finally { clearTimeout(timer); }
  }
  function finish(context, error) {
    if (!active(context)) return;
    runtime.busy = false;
    if (error && error.code !== 'VERSION_CONTEXT') { runtime.error = error.message; toast(error.message); }
    render(false);
  }
  function readonlySnapshot(record, status) {
    const row = clone(record), s = lcGet('bazi');
    Object.assign(s, {input: {...row.birth, confirmed: true}, normalized: row.normalized, options: row.options || {},
      result: row.result, rangeResult: null, selection: row.view?.mode === 'manual' ? {...row.view.selection, mode: 'manual'} : {},
      savedId: row.id, editing: false, error: '', errorCode: '', errorTranslations: null, notice: '',
      calculatedAt: row.provenance?.calculatedAt ? Date.parse(row.provenance.calculatedAt) : null,
      b11Record: clone(row), b11Status: clone(status), b11Readonly: true});
    if (typeof lbState === 'function') lbState().archiveKind = 'bazi';
  }
  function download(record) {
    const blob = new Blob([JSON.stringify(record, null, 2)], {type: 'application/json'}), url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = 'eastern-wisdom-bazi-' + String(record.birth.date) + '-' + record.id + '.json'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function fullError() {
    return problem('VERSION_LIMIT', label('This browser already holds 20 charts. Export or explicitly delete one before saving a new version.',
      '当前浏览器已有20份排盘。请先导出或自行删除一份，再另存新版本。', '目前瀏覽器已有20份排盤。請先匯出或自行刪除一份，再另存新版本。',
      'བཤར་ཆས་འདིར་ས་ཁྲ་༢༠ ཉར་ཡོད། གསར་པ་ཉར་སྔོན་གཅིག་ཕྱིར་འདོན་ནམ་རང་གིས་སུབ་རོགས།'));
  }
  async function openArchive(button) {
    const context = begin();
    try {
      const row = lcRecords().find(r => r.kind === 'bazi' && r.id === button.dataset.id);
      if (!row) throw problem('VERSION_MISSING', label('This chart no longer exists.', '这份档案已不存在。', '這份檔案已不存在。', 'ཟིན་ཐོ་འདི་མེད།'));
      const copy = clone(row), original = BaziResultVersion.canonical(copy), status = await BaziResultVersion.inspectSnapshot(copy, release);
      mustBeCurrent(context);
      const current = lcRecords().find(r => r.kind === 'bazi' && r.id === row.id);
      if (!current || BaziResultVersion.canonical(current) !== original) throw problem('VERSION_ARCHIVE_CHANGED', 'Archive changed; reopen the chart.');
      readonlySnapshot(copy, status);
      runtime.busy = false;
      navigate('classicsWisdom');
    } catch (e) { finish(context, e); }
  }
  async function saveFresh(exportOnly = false) {
    const s = lcGet('bazi');
    if (!s.result || !s.normalized) return;
    if (s.b11Readonly) {
      if (exportOnly) download(s.b11Record);
      else toast(label('This saved snapshot is read-only. Recalculate explicitly to save a new version.',
        '原档案为只读快照，请明确确认重算后另存新版本。', '原檔案為唯讀快照，請明確確認重算後另存新版本。',
        'ཉར་བའི་ཟིན་ཐོ་ནི་ཀློག་ཙམ་ཡིན། བསྐྱར་རྩིས་ངེས་གཏན་བྱས་ནས་གསར་པ་ཉར་རོགས།'));
      return;
    }
    const context = begin(), stamp = inputStamp(s);
    try {
      if (!exportOnly && !lockAvailable()) throw lockError();
      if (!exportOnly && lcRecords().length >= BaziResultVersion.archiveLimit) throw fullError();
      const row = await BaziResultVersion.captureCalculation({id: 'bzv-' + crypto.randomUUID(), title: s.normalized.birth.name || lcKindName('bazi'),
        normalized: s.normalized, options: s.options, result: s.result, manifest: release,
        ...(Number.isFinite(s.calculatedAt) ? {calculatedAt: new Date(s.calculatedAt).toISOString()} : {}),
        view: {selection: {period: s.selection.period ?? null, year: s.selection.year ?? null, month: s.selection.month ?? null}, mode: s.selection.mode === 'manual' ? 'manual' : 'current'}});
      mustBeCurrent(context);
      if (!unchangedInput(s, stamp)) throw problem('VERSION_INPUT_CHANGED', 'Chart changed; save the new result again.');
      if (exportOnly) { download(row); finish(context); return; }
      await append(row, context);
      const status = await BaziResultVersion.inspectSnapshot(row, release);
      mustBeCurrent(context);
      readonlySnapshot(row, status); runtime.busy = false;
      toast(label('New chart version saved.', '新排盘版本已保存。', '新排盤版本已儲存。', 'ས་ཁྲའི་ཐོན་རིམ་གསར་པ་ཉར་ཟིན།'));
      render(false);
    } catch (e) { finish(context, e); }
  }
  async function append(row, context, expectedParent) {
    return withArchiveWriteLock(context, async () => {
      mustBeCurrent(context);
      const rows = lcRecords(), before = BaziResultVersion.canonical(rows);
      if (expectedParent) {
        const parent = rows.find(r => r.kind === 'bazi' && r.id === expectedParent.id);
        if (!parent || BaziResultVersion.canonical(parent) !== BaziResultVersion.canonical(expectedParent))
          throw problem('VERSION_ARCHIVE_CHANGED', 'The original archive changed while waiting for another tab. Reopen it.');
      }
      if (rows.length >= BaziResultVersion.archiveLimit) throw fullError();
      const next = await BaziResultVersion.appendVersion(rows, row, release);
      mustBeCurrent(context);
      if (BaziResultVersion.canonical(lcRecords()) !== before)
        throw problem('VERSION_ARCHIVE_CHANGED', label('Archive changed while saving. Retry; nothing was overwritten.',
          '保存期间档案已变更，请重试；未覆盖原档案。', '儲存期間檔案已變更，請重試；未覆蓋原檔案。',
          'ཉར་དུས་ཟིན་ཐོ་བསྒྱུར་ཟིན། སྔར་གྱི་ཐོ་མ་བསུབས། སླར་ཚོད་བྱོས།'));
      if (!lcWriteRecords(next)) throw problem('VERSION_STORAGE', label('Browser storage is unavailable. Export the chart first.',
        '浏览器存储不可用，请先导出排盘。', '瀏覽器儲存不可用，請先匯出排盤。', 'བཤར་ཆས་ཀྱི་ཉར་ས་མེད། ས་ཁྲ་ཕྱིར་འདོན་རོགས།'));
    });
  }
  async function deleteArchive(button, originalHandler) {
    const context = begin();
    try {
      await withArchiveWriteLock(context, async () => {
        mustBeCurrent(context);
        // The original handler re-reads the current account's archive synchronously while this lock is held.
        const target = lcRecords().find(row => row.kind === 'bazi' && row.id === button.dataset.id);
        if (!target) { closeSheet(); return; }
        originalHandler('delete-confirm', 'bazi', button);
        if (lcRecords().some(row => row.kind === 'bazi' && row.id === target.id))
          throw problem('VERSION_STORAGE', 'The chart could not be deleted from browser storage.');
      });
      finish(context);
    } catch (e) { finish(context, e); }
  }
  function requestRecalculation() {
    const s = lcGet('bazi'), r = tokenState();
    if (r.busy || !s.b11Readonly || !s.b11Record) return;
    if (!lockAvailable()) { r.error = lockError().message; toast(r.error); render(false); return; }
    if (!lcRecords().some(row => row.kind === 'bazi' && row.id === s.b11Record.id)) {
      r.error = label('The original chart has been deleted. You can still export the displayed snapshot.', '原档案已删除，仍可导出当前显示的快照。', '原檔案已刪除，仍可匯出目前顯示的快照。', 'སྔར་གྱི་ཐོ་བསུབས་ཟིན། ད་ལྟ་མཐོང་བའི་ཐོ་ཕྱིར་འདོན་བྱེད་ཐུབ།');toast(r.error);render(false);return;
    }
    if (lcRecords().length >= BaziResultVersion.archiveLimit) { r.error = fullError().message; toast(r.error); render(false); return; }
    const context = begin(); r.busy = false;
    r.pending = {context, record: clone(s.b11Record)};
    const b = s.b11Record.birth;
    sheet(label('Recalculate and save a new version?', '按当前版本重算并另存？', '按目前版本重算並另存？', 'ད་ལྟའི་ཐོན་རིམ་ལྟར་བསྐྱར་རྩིས་བྱས་ནས་གསར་པ་ཉར་རམ།'),
      '<p>' + esc(label('The original snapshot and its saved date stay unchanged. Use the archived UTC instant and saved options; save a separate new record.',
        '保留原结果及原保存日期，按存档UTC时刻和原选项实际复算，并另存一份新记录。', '保留原結果及原儲存日期，按存檔UTC時刻和原選項實際複算，並另存一份新紀錄。',
        'སྔར་གྱི་འབྲས་བུ་དང་ཉར་ཚེས་མི་བསྒྱུར། ཉར་བའི་UTC དུས་དང་འདེམས་སྟངས་ལྟར་བསྐྱར་རྩིས་ནས་ཟིན་ཐོ་གསར་པ་ཉར།')) + '</p><p>' +
        esc(b.date + ' ' + b.time + ' · ' + s.b11Record.normalized.utc) + '</p>' + manifestHtml(s.b11Record),
      '<button class="btn full" data-b11-action="recalculate-confirm">' + label('Confirm recalculation and new save', '确认重算并另存新版本', '確認重算並另存新版本', 'བསྐྱར་རྩིས་དང་གསར་པ་ཉར་ངེས་གཏན།') +
      '</button><button class="btn secondary full" data-b11-action="recalculate-cancel">' + label('Cancel', '取消', '取消', 'ཕྱིར་འཐེན།') + '</button>');
  }
  async function confirmedRecalculation() {
    const r = tokenState(), pending = r.pending;
    if (!pending || r.busy || !active(pending.context)) return;
    r.busy = true;
    const context = pending.context, original = BaziResultVersion.canonical(pending.record);
    try {
      if (!lockAvailable()) throw lockError();
      if (lcRecords().length >= BaziResultVersion.archiveLimit) throw fullError();
      const row = await BaziResultVersion.recalculate({record: pending.record, manifest: release, confirmed: true,
        context, isCurrent: c => active(c) && runtime.pending === pending,
        compute: (normalized, options) => lcBaziCalculate(normalized, options)});
      mustBeCurrent(context);
      const parent = lcRecords().find(x => x.kind === 'bazi' && x.id === pending.record.id);
      if (!parent || BaziResultVersion.canonical(parent) !== original) throw problem('VERSION_ARCHIVE_CHANGED', 'The original archive changed. Reopen it before recalculating.');
      await append(row, context, pending.record);
      const status = await BaziResultVersion.inspectSnapshot(row, release);
      mustBeCurrent(context);
      readonlySnapshot(row, status); r.busy = false; r.pending = null;
      closeSheet();
      toast(label('New version saved; the original snapshot is preserved.', '新版本已另存，原档案仍完整保留。', '新版本已另存，原檔案仍完整保留。', 'ཐོན་རིམ་གསར་པ་ཉར་ཟིན། སྔར་གྱི་ཐོ་མ་བསུབས།'));
      render(false);
    } catch (e) { if (active(context)) { r.pending = null; closeSheet(); } finish(context, e); }
  }
  function manifestHtml(record, introduction = '') {
    const p = record?.provenance;
    const fields = [
      [label('Saved engine', '存档引擎', '存檔引擎', 'ཉར་བའི་རྩིས་ཆས།'), record?.result?.engine ? record.result.engine.name + ' ' + record.result.engine.version : '—'],
      [label('Saved implementation rule version', '存档实现规则版本', '存檔實作規則版本', 'ཉར་བའི་རྩིས་ལུགས་ཐོན་རིམ།'), p?.manifest.ruleVersion || label('Unknown in original record', '原记录未提供', '原紀錄未提供', 'སྔར་གྱི་ཐོར་མེད།')],
      [label('Current engine', '当前引擎', '目前引擎', 'ད་ལྟའི་རྩིས་ཆས།'), release.engine.name + ' ' + release.engine.version],
      [label('Current implementation rules', '当前实现规则', '目前實作規則', 'ད་ལྟའི་རྩིས་ལུགས།'), release.ruleVersion],
      [label('Adapter release', '适配器发布版本', '適配器發行版本', 'སྒྱུར་ཆས་ཐོན་རིམ།'), release.adapterVersion],
      [label('Output fingerprint', '结果指纹', '結果指紋', 'འབྲས་བུའི་མཛུབ་རྗེས།'), p?.outputFingerprint || '—'],
      [label('Original saved date', '原保存日期', '原儲存日期', 'སྔར་ཉར་བའི་ཚེས།'), record?.savedAt ?? '—'],
      [label('Calculation time', '实际计算时间', '實際計算時間', 'རྩིས་བྱས་པའི་དུས།'), p?.calculatedAt || label('Unknown in original record', '原记录未提供', '原紀錄未提供', 'སྔར་གྱི་ཐོར་མེད།')]
    ];
    return '<details class="fl-guide-details b11-manifest" data-b11-manifest><summary>' + label('Result version and saving details', '结果版本与保存说明', '結果版本與儲存說明', 'འབྲས་བུའི་ཐོན་རིམ་དང་ཉར་སྟངས།') + '</summary>' + introduction + '<dl>' +
      fields.map(([k,v]) => '<dt>' + esc(k) + '</dt><dd><code>' + esc(v) + '</code></dd>').join('') + '</dl><p data-b11-teacher-confirmed="false">' +
      label('Implementation versions only. Teacher rules and reference cases have not been confirmed.', '以上为实现版本。老师规则及对照样本尚未确认。', '以上為實作版本。老師規則及對照樣本尚未確認。',
        'འདི་ནི་ལག་ལེན་ཐོན་རིམ་ཡིན། སློབ་དཔོན་གྱི་ལུགས་དང་དཔེ་མཚོན་ངེས་གཏན་མ་བྱས།') + '</p></details>';
  }
  function banner() {
    const s = lcGet('bazi'), r = tokenState();
    if (!s.result) return '';
    const record = s.b11Record, status = s.b11Status, readOnly = s.b11Readonly === true;
    const message = !readOnly ? label('Current calculation. Saving creates a versioned snapshot.', '当前计算结果，保存后形成可追溯快照。', '目前計算結果，儲存後形成可追溯快照。', 'ད་ལྟའི་རྩིས་འབྲས། ཉར་ན་ཐོན་རིམ་འཚོལ་ཐུབ།')
      : status?.state === 'legacy-unverified' ? label('Original saved snapshot: legacy version unknown. Opening has not recalculated it.', '原档案只读快照：历史规则版本未知，打开时未复算。', '原檔案唯讀快照：歷史規則版本未知，開啟時未複算。', 'སྔར་ཉར་བའི་ཐོ་ཀློག་ཙམ། སྔར་གྱི་ཐོན་རིམ་མི་ཤེས། ཁ་ཕྱེ་དུས་བསྐྱར་རྩིས་མ་བྱས།')
      : status?.state === 'outdated' ? label('Historical snapshot: current rules or engine differ. Its original result is preserved.', '旧版只读快照：当前引擎或规则已变化，原结果完整保留。', '舊版唯讀快照：目前引擎或規則已變化，原結果完整保留。', 'སྔར་གྱི་ཐོ་ཀློག་ཙམ། ད་ལྟའི་རྩིས་ཆས་སམ་ལུགས་བསྒྱུར་ཟིན། སྔར་གྱི་འབྲས་བུ་ཉར་ཡོད།')
      : label('Original saved snapshot: read-only, with verified fingerprints.', '原档案只读快照，版本指纹一致。', '原檔案唯讀快照，版本指紋一致。', 'སྔར་ཉར་བའི་ཐོ་ཀློག་ཙམ། ཐོན་རིམ་གྱི་མཛུབ་རྗེས་མཐུན།');
    const explanation = '<p>' + esc(message) + '</p>' +
      '<p class="lc-time-help" data-b11-write-support="' + (lockAvailable() ? 'cooperative-lock' : 'unavailable') + '">' + esc(lockAvailable() ?
        label('These updated Ba Zi pages coordinate saves across tabs. Older pages and other chart tools may not coordinate their changes; close them before editing archives.',
          '本版八字页面会协调多标签页保存。旧版页面及其他排盘工具可能不会协调修改，整理档案前请先关闭这些页面。',
          '本版八字頁面會協調多標籤頁儲存。舊版頁面及其他排盤工具可能不會協調修改，整理檔案前請先關閉這些頁面。',
          'ཐོན་རིམ་འདིའི་བ་ཙི་ཤོག་ངོས་ཀྱིས་མཉམ་ལས་ཉར། རྙིང་པ་དང་ས་ཁྲ་གཞན་གྱི་ཤོག་ངོས་སྔོན་ལ་སྒོ་རྒྱོབ།') : lockError().message) + '</p>' +
      '<p class="lc-time-help" data-b11-ai-version>' + label('An interpretation belongs to the chart result it used. An earlier or unverified interpretation is not reused for a new version.',
        '解读只对应其使用的排盘结果。旧版或尚未核对的解读，不会作为新版本的解读复用。',
        '解讀只對應其使用的排盤結果。舊版或尚未核對的解讀，不會作為新版本的解讀複用。',
        'འགྲེལ་བ་དེས་སྤྱད་པའི་ས་ཁྲའི་འབྲས་བུ་ལ་མཐུད། སྔར་གྱི་འགྲེལ་བ་གསར་པར་མི་བཀོལ།') + '</p>';
    return '<aside class="b11-provenance" data-b11-state="' + (readOnly ? 'snapshot-' + status?.state : 'fresh') + '">' +
      (r.busy ? '<p role="status">' + label('Checking version…', '正在校验版本…', '正在校驗版本…', 'ཐོན་རིམ་བསྐྱར་བཤེར།') + '</p>' : '') +
      (r.error ? '<p role="alert" class="lc-error">' + esc(r.error) + '</p>' : '') + manifestHtml(record, explanation) + '</aside>';
  }
  function readonlyNotice() {
    if (!lcGet('bazi').b11Readonly) return '';
    return '<p class="b11-readonly-notice" role="note" data-b11-readonly-notice>' +
      esc(label('Original snapshot · Read-only. Recalculate separately from Tools.',
        '原快照 · 只读。重算请在工具中另存。',
        '原快照 · 唯讀。重算請在工具中另存。',
        'སྔར་གྱི་ཐོ་ཀློག་ཙམ། བསྐྱར་རྩིས་ནས་གསར་པ་ཉར།')) + '</p>';
  }

  function install(config) {
    if (!root.BaziResultVersion || typeof psToken !== 'function' || typeof psCurrent !== 'function' ||
        typeof lcHandleAction !== 'function' || typeof lcWriteRecords !== 'function' || typeof lcBaziCalculate !== 'function')
      throw problem('VERSION_DEPENDENCY', 'Load the existing chart and account scripts before installing B11.');
    const m = BaziResultVersion.manifest(config?.manifest);
    if (installed) {
      if (BaziResultVersion.canonical(m) !== BaziResultVersion.canonical(release)) throw problem('VERSION_INSTALLED', 'Reload before changing the release manifest.');
      return;
    }
    release = Object.freeze({...m, engine: Object.freeze({...m.engine})}); installed = true;
    const beforeAction = lcHandleAction, beforeActions = lcResultActions, beforeArchive = lcChartArchive;
    lcHandleAction = function(action, kind, button) {
      if (kind !== 'bazi') return beforeAction(action, kind, button);
      if (action === 'open') return openArchive(button);
      if (action === 'save') return saveFresh(false);
      if (action === 'export') return saveFresh(true);
      if (action === 'delete-confirm') return deleteArchive(button, beforeAction);
      if (['new', 'edit'].includes(action)) {
        const r = tokenState(); r.sequence++; r.busy = false; r.pending = null; r.error = '';
        if (action !== 'delete-confirm') { const s = lcGet('bazi'); delete s.b11Record; delete s.b11Status; delete s.b11Readonly; }
      }
      return beforeAction(action, kind, button);
    };
    lcResultActions = function(kind) {
      const html = beforeActions(kind);
      if (kind !== 'bazi' || !lcGet('bazi').b11Readonly) return html;
      return html + '<button class="btn secondary full" data-b11-action="recalculate-request">' +
        label('Recalculate with current version and save separately', '按当前版本重算并另存', '按目前版本重算並另存', 'ད་ལྟའི་ཐོན་རིམ་ལྟར་བསྐྱར་རྩིས་དང་གསར་པ་ཉར།') + '</button>';
    };
    lcChartArchive = function() {
      return beforeArchive().replace(/<button\b(?=[^>]*data-lc-action="open")(?=[^>]*data-kind="bazi")[^>]*>[^<]*<\/button>/g,
        match => match.replace(/>[^<]*<\/button>$/, '>' + label('View original snapshot', '查看原快照', '查看原快照', 'སྔར་ཉར་བའི་ཐོ་ལྟ་བ།') + '</button>'));
    };
    if (typeof lbOptions === 'function') {
      const beforeOptions = lbOptions;
      lbOptions = function(kind) { return kind === 'bazi' && lcGet('bazi').b11Readonly ? '' : beforeOptions(kind); };
    }
    const beforeScreen = screens.classicsWisdom;
    screens.classicsWisdom = function() {
      const s = lcGet('bazi'); let html;
      if (!s.b11Readonly) html = beforeScreen();
      else try { html = lcBaziScreen(); }
      catch (_) {
        html = '<section class="page lc-page">' + pxTop(lcKindName('bazi'), '', 'lifeReview') +
          '<p>' + label('The historical display format is unsupported; view or export its original data.', '该历史格式暂不能用当前盘面展示，可查看或导出原数据。',
          '該歷史格式暫不能用目前盤面展示，可查看或匯出原資料。', 'སྔར་གྱི་རྣམ་པ་ད་ལྟ་སྟོན་མི་ཐུབ། སྔར་གྱི་གཞི་གྲངས་ལྟ་བའམ་ཕྱིར་འདོན་བྱོས།') +
          '</p><details class="b11-original-json"><summary>JSON</summary><pre>' + esc(JSON.stringify(s.b11Record.result, null, 2)) + '</pre></details>' + lcResultActions('bazi') + '</section>';
      }
      const closing = html.lastIndexOf('</section>');
      if (closing >= 0) html = html.slice(0, closing) + banner() + html.slice(closing);
      return html.replace(/(<section\b[^>]*>)/, '$1' + readonlyNotice());
    };
    document.addEventListener('click', event => {
      const button = event.target.closest?.('[data-b11-action]'); if (!button) return;
      event.preventDefault(); event.stopImmediatePropagation();
      const action = button.dataset.b11Action;
      if (action === 'recalculate-request') requestRecalculation();
      if (action === 'recalculate-confirm') void confirmedRecalculation();
      if (action === 'recalculate-cancel') { const r=tokenState(); r.sequence++; r.pending=null; r.busy=false; closeSheet(); }
    }, true);
    // On legacy archived pages no rule form is rendered. Also reject programmatically submitted stale forms before old document listeners run.
    root.addEventListener('submit', event => {
      if (event.target.matches?.('form[data-lb-options="bazi"],form[data-lc-form="bazi"]') && lcGet('bazi').b11Readonly) {
        event.preventDefault(); event.stopImmediatePropagation(); requestRecalculation();
      }
    }, true);
  }
  root.BaziVersionUI = Object.freeze({install, get installed() {return installed;}, get manifest() {return release ? clone(release) : null;},
    inspectInterpretation: (record, binding) => BaziResultVersion.interpretationStatus(record, binding, release)});
})(typeof globalThis === 'object' ? globalThis : this);

