// 결정론적 프레임 캡처 → PNG 시퀀스. 이후 build.sh 가 ffmpeg 로 webm 인코딩.
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FPS = 30, DUR = 20, TOTAL = FPS * DUR;

const browser = await chromium.launch({ args: ['--force-color-profile=srgb', '--disable-lcd-text'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
await page.addInitScript(() => { window.__capture = true; });
await page.goto('file://' + path.join(__dirname, 'index.html'));
// 배경 이미지 로드(또는 실패) 대기
await page.waitForFunction(() => window.__ready && window.__ready(), null, { timeout: 15000 });
await page.waitForTimeout(300); // 폰트 안정화

const pad = n => String(n).padStart(5, '0');
for (let i = 0; i < TOTAL; i++) {
  const t = i / FPS;
  await page.evaluate(tt => window.renderAt(tt), t);
  await page.screenshot({ path: path.join(__dirname, 'frames', `f${pad(i)}.jpg`), type: 'jpeg', quality: 96, clip: { x:0, y:0, width:1920, height:1080 } });
  if (i % 30 === 0) process.stdout.write(`\r  frame ${i}/${TOTAL}`);
}
process.stdout.write(`\r  frame ${TOTAL}/${TOTAL}\n`);
await browser.close();
console.log('capture done');
