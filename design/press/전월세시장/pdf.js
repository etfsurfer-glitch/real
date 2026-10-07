const { chromium } = require('/Users/hcode/.npm/_npx/f0a362733743bae2/node_modules/playwright');
(async () => {
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage();
  await p.goto('file://' + process.cwd() + '/report_final.html', { waitUntil: 'networkidle' });
  await p.waitForFunction('window.__ready === true', { timeout: 8000 }).catch(()=>{});
  await p.waitForTimeout(1500);
  await p.emulateMedia({ media: 'print' });
  await p.pdf({ path: '전월세시장_통계리포트_2026.pdf', format: 'A4', printBackground: true,
    margin: {top:'0mm',bottom:'0mm',left:'0mm',right:'0mm'} });
  await p.screenshot({ path: 'rep_shot.png', fullPage: true });
  await b.close();
  console.log("pdf done");
})();
