from pathlib import Path
root=next(p for p in Path.cwd().iterdir() if p.is_dir());src=root/'04_研发源码/app/r4'
# Original parametric linework, no third-party asset or code is copied.
f=src/'homepage.js';s=f.read_text(encoding='utf-8');s=s.replace('function dailyBanner(){', '''function ewZenSigil(kind='lotus'){
 const petals=Array.from({length:8},(_,i)=>`<path transform="rotate(${i*45} 100 100)" d="M100 100 C67 77 70 40 100 21 C130 40 133 77 100 100Z"/>`).join('');
 const inner=Array.from({length:8},(_,i)=>`<path transform="rotate(${i*45+22.5} 100 100)" d="M100 100 C84 81 85 61 100 46 C115 61 116 81 100 100Z"/>`).join('');
 return `<svg class="ew-zen-sigil ew-zen-${kind}" viewBox="0 0 200 200" fill="none" aria-hidden="true"><g class="ew-sigil-guide"><circle cx="100" cy="100" r="91"/><circle cx="100" cy="100" r="85"/><path d="M100 4v8m0 176v8M4 100h8m176 0h8"/></g><g class="ew-sigil-petals">${petals}</g><g class="ew-sigil-inner">${inner}</g><circle class="ew-sigil-heart" cx="100" cy="100" r="4"/></svg>`;
}
function dailyBanner(){''')
s=s.replace('<svg class="ew-contour"', '${ewZenSigil()}<svg class="ew-contour"');f.write_text(s,encoding='utf-8')
f=src/'platform.js';s=f.read_text(encoding='utf-8')
s=s.replace('<span class="ew-brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>','<span class="ew-brand-mark" aria-hidden="true">${icon(\'lotus\')}</span>')
s=s.replace("pxText('EASTERN WISDOM','EASTERN WISDOM')", "pxText('身心同频 · 日常修习','EASTERN WISDOM · DAILY PRACTICE')")
s=s.replace('<div class="px-map-hero"><span class="px-kicker">${info[3]}', '<div class="px-map-hero">${ewZenSigil(kind)}<span class="px-kicker">${info[3]}')
s=s.replace('<div class="px-map-hero"><span class="px-kicker">RETURN TO THIS MOMENT', '<div class="px-map-hero">${ewZenSigil(\'mind\')}<span class="px-kicker">RETURN TO THIS MOMENT')
s=s.replace('<div class="px-ai-core" aria-hidden="true"><i></i><i></i>${icon(\'spark\')}</div>', '<div class="px-ai-core" aria-hidden="true">${ewZenSigil(\'mind\')}</div>')
s=s.replace("${icon('bell')}</button><h2>${done?", "${ewZenSigil('bell')}${icon('bell')}</button><h2>${done?")
# A functional equipment status panel, never synthetic readings.
needle="${items.map(d=>`<article class=\"card px-device mb16\">"
replacement="""<div class="ew-device-scope"><span class="px-kicker">${pxText('身心数据连接','BODY DATA CONNECTION')}</span><div class="ew-signal-trace" aria-hidden="true"><svg viewBox="0 0 320 52"><path class="ew-signal-baseline" d="M0 26H320"/><path d="M0 26H65l9-6 9 12 10-22 11 33 10-17H320"/></svg></div><h2>${items.some(d=>d.measurements?.length)?pxText('已接收设备数据','Measurements received'):pxText('等待真实数据接入','Awaiting your data')}</h2><p>${pxText('仅展示你已授权设备提供的测量记录','Only measurements from devices you authorize')}</p></div>${items.map(d=>`<article class="card px-device mb16">"""
assert needle in s;s=s.replace(needle,replacement)
f.write_text(s,encoding='utf-8')
# Portable regression runtime discovery, required after moving computers.
f=root/'06_验证与后续工作/全量回归.cjs';s=f.read_text(encoding='utf-8');s=s.replace("require('C:/Users/YIT/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')", "require(path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'))");s=s.replace("const python='C:/Users/YIT/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';", "const python=process.env.EW_PYTHON||path.join(require('os').homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');")
f.write_text(s,encoding='utf-8')
f=src/'review.html';s=f.read_text(encoding='utf-8').replace('本地联调版 · 2026年10月23日','科技禅修体验版 · 2026年10月27日').replace('让东方智慧，进入每一天。','东方意境，与现代身心科技相遇。');f.write_text(s,encoding='utf-8')
print('Updated original linework, homepage, map and device composition; regression runtime is portable.')
