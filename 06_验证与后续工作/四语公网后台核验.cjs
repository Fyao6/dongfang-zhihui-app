const fs = require('fs'), path = require('path'), assert = require('assert/strict');
const { chromium, request } = require(path.join(require('os').homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const root = path.resolve(__dirname, '..');
const base = 'https://eastern-wisdom-demo-fuyao.netlify.app';
(async () => {
  const api = await request.newContext();
  let browser;
  try {
    const credentials = JSON.parse(fs.readFileSync(path.join(root, '04_研发源码/app/cloud/.env.test'), 'utf8'));
    assert.equal((await api.post(base + '/api/auth/login', { data: credentials })).status(), 200);
    browser = await chromium.launch({ headless: true, args: ['--no-proxy-server'] });
    const context = await browser.newContext({ storageState: await api.storageState(), viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto(base + '/admin');
    await page.locator('[data-nav=courses]').click();
    await page.locator('[data-edit]').first().click();
    const fields = ['zh', 'en', 'hant', 'bo', 'goalsEn', 'goalsHant', 'goalsBo', 'sectionsEn', 'sectionsHant', 'sectionsBo'];
    for (const name of fields) assert.equal(await page.locator('[name="' + name + '"]').count(), 1, name);
    assert.deepEqual(errors, []);
    const report = { at: new Date().toISOString(), base, pass: true, scope: 'Authenticated read-only admin UI; no content saved', fields, errors };
    fs.writeFileSync(path.join(__dirname, '四语公网后台核验.json'), JSON.stringify(report, null, 2));
    console.log('PASS deployed admin login and 10 multilingual course fields; no content changed');
  } finally { await browser?.close(); await api.dispose(); }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
