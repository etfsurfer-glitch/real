// 단지 서랍 '단지정보' 탭 캡처 — PC·폰. 사용: node testv2/info_shot.mjs <outdir> [complex_no lat lng]
import { chromium } from "playwright";
const [out = "/tmp", cx = "104544", lat = "37.392859", lng = "126.63235"] = process.argv.slice(2);
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";
const b = await chromium.launch();
for (const [tag, vp, ua] of [["pc", { width: 1500, height: 1000 }, UA], ["phone", { width: 390, height: 844 }, "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"]]) {
  const ctx = await b.newContext({ viewport: vp, userAgent: ua, locale: "ko-KR", isMobile: tag === "phone", hasTouch: tag === "phone" });
  const p = await ctx.newPage();
  const errs = []; p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  await p.goto(`https://testv2.koczip.com/?cx=${cx}&lat=${lat}&lng=${lng}&lv=3`, { waitUntil: "networkidle", timeout: 60000 });
  await p.waitForTimeout(5000);
  const tab = p.locator(".t2-tabs button", { hasText: "단지정보" }).first();
  if (await tab.count()) await tab.click(); else console.log(tag, "no tab");
  await p.waitForTimeout(5000);
  const body = p.locator(".t2-dr-b").first();
  if (await body.count()) {
    const dr = p.locator(".t2-dr").first();
    await dr.screenshot({ path: `${out}/info_${tag}_1.png` });
    await body.evaluate((el) => { const h = [...el.querySelectorAll(".t2-pf-h h3")].find((x) => x.textContent.includes("관리")); h?.scrollIntoView(); });
    await p.waitForTimeout(400);
    await dr.screenshot({ path: `${out}/info_${tag}_2.png` });
    await body.evaluate((el) => { const h = [...el.querySelectorAll(".t2-pf-h h3")].find((x) => x.textContent.includes("걸어서")); h?.scrollIntoView(); });
    await p.waitForTimeout(400);
    await dr.screenshot({ path: `${out}/info_${tag}_3.png` });
    console.log(tag, "text:", (await body.innerText()).replace(/\n+/g, " | ").slice(0, 1200));
  } else console.log(tag, "no drawer body");
  console.log(tag, "console errors:", errs.length, errs.slice(0, 3));
  await ctx.close();
}
await b.close();
