// 잠실 전월세 리포트 빌드: 데이터 주입(→ *_final.html) + PDF 렌더.
// 실행: node design/press/잠실전월세/build.js
// 선행: 박스에서 jamsil.py~jamsil4.py 실행 후 JSON을 이 폴더로 회수.
const fs = require('fs');
const path = require('path');
const HERE = __dirname;
const R = f => fs.readFileSync(path.join(HERE, f), 'utf8');
const W = (f, s) => fs.writeFileSync(path.join(HERE, f), s);
const J = ['jamsil.json', 'jamsil2.json', 'jamsil3.json', 'jamsil4.json'].map(R);

// 1) 인터랙티브 보도자료(잠실 전세, 광고와 실물 사이) — 서사 포함
W('jamsil_final.html', R('jamsil.html')
  .replace('__DATA__', J[0]).replace('__DATA2__', J[1]).replace('__DATA3__', J[2]).replace('__DATA4__', J[3]));

// 2) PDF 리포트(사실만·발행 조용호)
W('report_jamsil_final.html', R('report_jamsil.html')
  .replace('__J1__', J[0]).replace('__J2__', J[1]).replace('__J3__', J[2]).replace('__J4__', J[3]));
console.log('injected: jamsil_final.html, report_jamsil_final.html');

// 3) PDF 렌더(headless Chrome). 순수 chromium 미설치라 channel:chrome 필수.
(async () => {
  const { chromium } = require('/Users/hcode/.npm/_npx/f0a362733743bae2/node_modules/playwright');
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage();
  await p.goto('file://' + path.join(HERE, 'report_jamsil_final.html'), { waitUntil: 'networkidle' });
  await p.waitForFunction('window.__ready === true', { timeout: 8000 }).catch(() => {});
  await p.waitForTimeout(1200);
  await p.emulateMedia({ media: 'print' });
  await p.pdf({ path: path.join(HERE, '잠실_전월세통계_2026.pdf'),
    format: 'A4', printBackground: true, margin: { top: '0mm', bottom: '0mm', left: '0mm', right: '0mm' } });
  await b.close();
  console.log('pdf: 잠실_전월세통계_2026.pdf');
})();
