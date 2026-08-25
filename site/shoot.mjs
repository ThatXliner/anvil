// Screenshot anvil's site: scrolls through to trigger reveals, then captures.
//   node shoot.mjs --out /tmp/hero.png --sel "#masthead"
//   node shoot.mjs --out /tmp/full.png --full
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.resolve(ROOT, '../anvil/site');

const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf('--' + name);
  return i === -1 ? fallback : argv[i + 1];
};
const flag = (name) => argv.includes('--' + name);

const out = path.resolve(arg('out', '/tmp/page.png'));
const width = parseInt(arg('width', '1440'), 10);
const height = parseInt(arg('height', '900'), 10);

fs.mkdirSync(path.dirname(out), { recursive: true });

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 2 });
await page.goto('file://' + path.join(SITE, 'index.html'), { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts && document.fonts.ready);

// scroll through the page like a reader so every reveal fires
// (behavior:'instant' — html has scroll-behavior:smooth, which would lag)
await page.evaluate(async () => {
  const h = document.body.scrollHeight;
  for (let y = 0; y <= h; y += 250) {
    window.scrollTo({ top: y, behavior: 'instant' });
    await new Promise(r => setTimeout(r, 60));
  }
  window.scrollTo({ top: 0, behavior: 'instant' });
});
await page.waitForTimeout(1200);

if (flag('full')) {
  await page.screenshot({ path: out, fullPage: true });
} else {
  const sel = arg('sel', '#masthead');
  const el = page.locator(sel);
  await el.scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
  await el.screenshot({ path: out });
}
await browser.close();
console.log(out);
