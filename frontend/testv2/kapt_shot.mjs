import { chromium } from "playwright";
const out = process.argv[2] || "/tmp";
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1500, height: 1000 }, userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", locale: "ko-KR" });
const p = await ctx.newPage();
const errs = []; p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
await p.goto("https://testv2.koczip.com/?cx=104544&lat=37.392859&lng=126.63235&lv=3", { waitUntil: "networkidle", timeout: 60000 });
await p.waitForTimeout(6000);
// 서랍 급매 탭 맨 위의 콕집매물 행 클릭
const row = p.locator(".t2-drawer .t2-kok-row, .t2-drawer [class*='kok'] button, .t2-drawer [class*='kok-row']").first();
if (await row.count()) { await row.click(); } else {
  const any = p.locator(".t2-drawer").getByText(/콕집/).first(); await any.click();
}
await p.waitForTimeout(9000);
await p.screenshot({ path: `${out}/kapt_pane.png` });
const pane = p.locator(".t2-drawer2");
if (await pane.count()) {
  const shot = async (txt, name) => {
    await pane.evaluate((el, t) => { const h = [...el.querySelectorAll("h3")].find((x) => x.textContent.includes(t)); if (h) h.scrollIntoView(); }, txt);
    await p.waitForTimeout(400); await pane.screenshot({ path: `${out}/${name}.png` });
  };
  await shot("실제 관리비", "kapt_pane_mgmt");
  await shot("단지", "kapt_pane_cx");
  await shot("드는 돈", "kapt_pane_money");
  console.log("pane text:", (await pane.innerText()).slice(0, 1800));
} else { console.log("no pane"); console.log(await p.locator(".t2-drawer").innerText().catch(() => "no drawer")); }
console.log("console errors:", errs.length, errs.slice(0, 3));
await b.close();
