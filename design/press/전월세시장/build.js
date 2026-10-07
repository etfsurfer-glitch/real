// 전월세 리포트 빌드: 데이터 주입(→ *_final.html) + PDF 렌더.
// 실행: node design/press/전월세시장/build.js   (맥 로컬, 이 폴더에서 cwd 무관)
// 선행: 박스에서 full.py/chart.py/listing.py/newshare.py 실행 후 JSON을 이 폴더로 회수.
const fs = require('fs');
const path = require('path');
const HERE = __dirname;
const R = f => fs.readFileSync(path.join(HERE, f), 'utf8');
const W = (f, s) => fs.writeFileSync(path.join(HERE, f), s);

// 1) PDF 리포트 템플릿 ← full.json(__DATA__) + listing.json(__LDATA__, newshare 병합)
const listing = JSON.parse(R('listing.json'));
listing.newshare = JSON.parse(R('newshare.json'));
W('listing.json', JSON.stringify(listing));           // newshare 병합 고정
let rep = R('report.html')
  .replace('__DATA__', R('full.json'))
  .replace('__LDATA__', JSON.stringify(listing));
W('report_final.html', rep);

// 2) 인터랙티브 보도자료(사라지는 전세) ← chart.json
W('press_final.html', R('press.html').replace('__DATA__', R('chart.json')));
console.log('injected: report_final.html, press_final.html');

// 3) PDF 렌더(headless Chrome). 순수 chromium 미설치라 channel:chrome 필수.
(async () => {
  const { chromium } = require('/Users/hcode/.npm/_npx/f0a362733743bae2/node_modules/playwright');
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage();
  await p.goto('file://' + path.join(HERE, 'report_final.html'), { waitUntil: 'networkidle' });
  await p.waitForFunction('window.__ready === true', { timeout: 8000 }).catch(() => {});
  await p.waitForTimeout(1200);
  await p.emulateMedia({ media: 'print' });
  await p.pdf({ path: path.join(HERE, '전월세시장_통계리포트_2026.pdf'),
    format: 'A4', printBackground: true, margin: { top: '0mm', bottom: '0mm', left: '0mm', right: '0mm' } });
  await b.close();
  console.log('pdf: 전월세시장_통계리포트_2026.pdf');
})();
