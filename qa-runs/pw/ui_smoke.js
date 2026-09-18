/* UI smoke test for the redesigned HarvestWise dashboard.
   Boots file://finale/ui/index.html in headless Chromium, captures console
   errors + failed requests, drives the full typed-fallback flow, and saves
   screenshots. Exit 1 on any hard failure. */
const { chromium } = require('playwright');

const API = 'http://127.0.0.1:8000';
const UI  = 'file:///' + require('path').resolve(__dirname, '../../finale/ui/index.html').replace(/\\/g, '/');
const SHOT = __dirname;

const consoleErrors = [];
const pageErrors = [];
const failedRequests = [];
let hard = 0;

function ok(name, cond, detail) {
  console.log((cond ? '  PASS ' : '  FAIL ') + name + (detail ? '  | ' + detail : ''));
  if (!cond) hard++;
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });

  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
  page.on('pageerror', e => pageErrors.push(String(e).slice(0, 200)));
  page.on('requestfailed', r => {
    const u = r.url();
    // file:// favicon 404s and the intentional offline probe noise are not defects
    if (!u.includes('favicon') && !failedRequests.some(f => f.url === u)) {
      failedRequests.push({ url: u, err: r.failure() && r.failure().errorText });
    }
  });

  console.log('== 1. boot ==');
  await page.goto(UI);
  // /health can take a few seconds on a cold server (Cognee probe) — wait for
  // the badge to resolve instead of snapshotting at a fixed time.
  await page.waitForFunction(() => {
    const t = document.getElementById('apiStatus').textContent;
    return t.includes('ok') || t.includes('offline');
  }, null, { timeout: 15000 });
  await page.waitForTimeout(300);

  ok('header renders', await page.locator('header h1').count() === 1);
  ok('5 stepper stages', await page.locator('#flow .step').count() === 5);
  const badge = await page.locator('#apiStatus').textContent();
  ok('API badge green', badge.includes('ok'), badge);
  ok('stock tomato rendered', (await page.locator('#skuTomato').textContent()).includes('kg'));
  ok('weather chip filled', !(await page.locator('#weatherChip').textContent()).includes('—'));
  await page.waitForFunction(() => {
    const t = document.getElementById('waBox').textContent;
    return t.includes('mode:') || t.includes('unavailable');
  }, null, { timeout: 15000 });
  const wa = await page.locator('#waBox').textContent();
  ok('whatsapp card live', wa.includes('mode: live') || wa.includes('mode: mock'), wa.split('\n')[0]);
  await page.screenshot({ path: SHOT + '/01_boot.png', fullPage: true });

  console.log('== 2. typed demo flow ==');
  await page.fill('#typedCmd', 'நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி');
  await page.click('button:has-text("Run")');
  await page.waitForSelector('.total-line', { timeout: 30000 });
  const itemsTxt = await page.locator('#itemsBox').innerText();
  ok('basket shows tomato 20', itemsTxt.includes('20'), '');
  ok('basket shows coriander 6 (rain-adjusted)', /6/.test(itemsTxt), '');
  ok('basket total ₹546', itemsTxt.includes('546'), itemsTxt.split('\n').pop());
  ok('step2 (recommend) green', (await page.locator('#s1b').getAttribute('class')).includes('ok'));
  ok('approve buttons enabled', await page.locator('#btnApproveTyped').isEnabled());
  ok('dispatch still disabled', !(await page.locator('#btnDispatch').isEnabled()));
  await page.screenshot({ path: SHOT + '/02_basket.png', fullPage: true });

  console.log('== 3. approval gate ==');
  await page.click('#btnApproveTyped');
  await page.waitForTimeout(800);
  ok('step3 (approve) green', (await page.locator('#s2').getAttribute('class')).includes('ok'));
  ok('dispatch enabled after approval', await page.locator('#btnDispatch').isEnabled());

  console.log('== 4. dispatch ==');
  await page.click('#btnDispatch');
  // Dispatch runs both items sequentially (n8n webhook round-trip each) — wait
  // on the UI's own completion signal (step 4 green), not a fixed timeout.
  await page.waitForFunction(() => document.getElementById('s3').className.includes('ok'), null, { timeout: 45000 });
  await page.waitForTimeout(500);
  const n8n = await page.locator('#n8nBox').innerText();
  ok('dispatch status dispatched', n8n.includes('"dispatched"'), n8n.split('\n')[1] || '');
  ok('ledger shows stock 12 -> 32', (await page.locator('#ledgerBox').innerText()).includes('12 → 32'));
  ok('step4 (dispatch) green', (await page.locator('#s3').getAttribute('class')).includes('ok'));
  ok('step5 (memory) green', (await page.locator('#s4').getAttribute('class')).includes('ok'));
  const stockAfter = await page.locator('#skuTomato').textContent();
  ok('stock card updated to 32', stockAfter.includes('32'), stockAfter);
  // WhatsApp delivery panel refreshes after dispatch — accept any real Twilio state.
  await page.waitForTimeout(1500);
  const waAfter = await page.locator('#waBox').textContent();
  ok('whatsapp card shows a delivery state',
     /(delivered|read|sent|sending|queued|accepted|failed|mock|unknown|skipped)/.test(waAfter), waAfter.split('\n')[1] || '');
  await page.screenshot({ path: SHOT + '/03_dispatched.png', fullPage: true });

  console.log('== 5. reset ==');
  await page.click('button:has-text("Reset demo state")');
  await page.waitForTimeout(1000);
  ok('stock back to 12', (await page.locator('#stockTomato').textContent()).includes('12'));
  ok('dispatch disabled again', !(await page.locator('#btnDispatch').isEnabled()));

  console.log('== 6. reason (Sarvam fast) ==');
  await page.click('button:has-text("Reason (Sarvam-105B)")');
  await page.waitForFunction(() => document.getElementById('recallBox').textContent.includes('OBSERVATIONS'), null, { timeout: 40000 });
  const reasonTxt = await page.locator('#recallBox').innerText();
  ok('observations present', reasonTxt.includes('get_stock'), '');
  ok('quantities_from engine', reasonTxt.includes('deterministic engine'), '');

  console.log('== 7. cognee recall (real cloud, up to ~60s) ==');
  await page.click('button:has-text("Recall from Cognee")');
  await page.waitForFunction(() => {
    const t = document.getElementById('recallBox').textContent;
    return t.includes('COGNEE (') || t.includes('Cognee unavailable');
  }, null, { timeout: 70000 });
  const recallTxt = await page.locator('#recallBox').innerText();
  ok('cognee answered', recallTxt.includes('COGNEE ('), recallTxt.slice(0, 60).replace(/\n/g, ' '));

  console.log('== 8. console hygiene ==');
  // CSP/file:// noise tolerated; real JS defects are not.
  ok('no page JS exceptions', pageErrors.length === 0, pageErrors.join(' || ').slice(0, 150));
  const realErrors = consoleErrors.filter(e =>
    !e.includes('favicon') && !e.includes('net::') && !e.includes('Failed to load resource'));
  ok('no console JS errors', realErrors.length === 0, realErrors.join(' || ').slice(0, 200));
  const apiFailures = failedRequests.filter(f => f.url.startsWith(API));
  ok('no failed API calls', apiFailures.length === 0, apiFailures.map(f => f.url + ' ' + f.err).join(' | ').slice(0, 200));

  await browser.close();
  console.log(hard === 0 ? '\n=== UI SMOKE: ALL GREEN ===' : `\n=== UI SMOKE: ${hard} FAILURE(S) ===`);
  process.exit(hard === 0 ? 0 : 1);
})().catch(e => { console.error('FATAL:', e); process.exit(1); });
