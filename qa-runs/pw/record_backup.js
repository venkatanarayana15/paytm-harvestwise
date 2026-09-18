/* Stage fail-safe: record a real Full Auto demo run to video.
   Boots file://finale/ui/index.html in headed Chromium at 1360x850,
   clicks ⚡ Full Auto Demo, waits for the WhatsApp delivery state, saves
   video.webm + the DOM transcript of every narrated step.

   Run:  node record_backup.js            (from qa-runs/pw, API must be up)
   Out:  finale/backup_demo/video.webm + demo_transcript.txt (+ png stages)
*/
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const API = 'http://127.0.0.1:8000';
const UI  = 'file:///' + require('path').resolve(__dirname, '../../finale/ui/index.html').replace(/\\/g, '/');
const OUT = path.resolve(__dirname, '../../finale/backup_demo');
fs.mkdirSync(OUT, { recursive: true });

const logLines = [];
function note(msg) {
  const line = `[${new Date().toISOString().slice(11, 19)}] ${msg}`;
  console.log(line);
  logLines.push(line);
}

(async () => {
  // Clean seeded state so the recording starts like a fresh demo.
  try {
    await fetch(API + '/demo/reset', { method: 'POST' });
    note('demo state reset (seeded inventory, tokens cleared)');
  } catch (e) {
    console.error('FATAL: API not reachable on 127.0.0.1:8000 — start uvicorn first.');
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: false, args: ['--autoplay-policy=no-user-gesture-required'] });
  const ctx = await browser.newContext({
    viewport: { width: 1360, height: 850 },
    recordVideo: { dir: OUT, size: { width: 1360, height: 850 } },
  });
  const page = await ctx.newPage();
  page.on('pageerror', e => note('PAGE ERROR: ' + String(e).slice(0, 200)));
  page.on('console', m => { if (m.type() === 'error') note('CONSOLE: ' + m.text().slice(0, 160)); });

  note('boot dashboard: ' + UI);
  await page.goto(UI);
  await page.waitForFunction(() => {
    const t = document.getElementById('apiStatus').textContent;
    return t.includes('ok') || t.includes('offline');
  }, null, { timeout: 20000 });
  await page.waitForTimeout(2500);            // WhatsApp/Soundbox cards settle
  await page.screenshot({ path: path.join(OUT, 'stage_1_boot.png'), fullPage: true });

  note('clicking ⚡ Full Auto Demo');
  await page.click('button:has-text("Full Auto Demo")');

  // The pipeline: basket → approve → dispatch (n8n + Twilio round-trips).
  await page.waitForSelector('.total-line', { timeout: 60000 });
  note('basket rendered — engine quantities visible');
  await page.waitForFunction(() => document.getElementById('s2').className.includes('ok'), null, { timeout: 60000 });
  note('merchant approval (சரி) accepted — gate held, tokens issued');
  await page.waitForFunction(() => document.getElementById('s3').className.includes('ok'), null, { timeout: 90000 });
  note('dispatch complete — n8n fired, ledger updated');
  await page.waitForFunction(() => document.getElementById('s4').className.includes('ok'), null, { timeout: 30000 });
  note('memory/inventory panel updated');
  await page.waitForTimeout(4000);            // let the WhatsApp card show a real state
  await page.screenshot({ path: path.join(OUT, 'stage_2_dispatched.png'), fullPage: true });

  // Optional depth for judges: grounded reasoning (fast model, ~1-3s).
  try {
    await page.click('button:has-text("Reason (Sarvam-105B)")');
    await page.waitForFunction(() => document.getElementById('recallBox').textContent.includes('OBSERVATIONS'), null, { timeout: 45000 });
    note('grounded reasoning (Sarvam fast) rendered — observations + engine-locked quantity');
  } catch (e) {
    note('reason step skipped: ' + String(e).slice(0, 80));
  }
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(OUT, 'stage_3_reason.png'), fullPage: true });

  const ledger = await page.locator('#ledgerBox').innerText();
  const wa     = await page.locator('#waBox').innerText();
  note('LEDGER: ' + ledger.split('\n')[0] + ' …');
  note('WHATSAPP: ' + (wa.split('\n')[1] || wa.split('\n')[0]));

  await page.waitForTimeout(1500);
  await ctx.close();                           // flush video
  await browser.close();

  fs.writeFileSync(path.join(OUT, 'demo_transcript.txt'), logLines.join('\n') + '\n');
  const proof = [
    'HarvestWise — backup demo proof (generated ' + new Date().toISOString() + ')',
    '',
    'Ledger panel:',
    ledger,
    '',
    'WhatsApp panel:',
    wa,
  ].join('\n');
  fs.writeFileSync(path.join(OUT, 'proof_panel.txt'), proof);
  note('saved: video.webm, demo_transcript.txt, proof_panel.txt, stage_*.png in finale/backup_demo');
})().catch(e => { console.error('FATAL:', e); process.exit(1); });
