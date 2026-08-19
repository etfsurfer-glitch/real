import { chromium } from "playwright";
const BIN = process.env.HOME + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36";
const b = await chromium.launch({ executablePath: BIN });
const p = await (await b.newContext({ viewport: { width: 1280, height: 720 }, userAgent: UA })).newPage();
await p.goto("https://koczip.com/proposals/-L7kC1ldPtz8yvi2JL3sFRW0PhQY0cdI", { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
console.log(await p.evaluate(() => {
  const n = document.querySelector(".myoff-top b"), t = document.querySelector(".myoff-tel");
  return {
    b_html: n ? n.innerHTML : null,
    b_children: n ? [...n.childNodes].map(x => x.nodeName + ":" + JSON.stringify(x.textContent)) : null,
    tel_children: t ? [...t.childNodes].map(x => x.nodeName + ":" + JSON.stringify(x.textContent)) : null,
  };
}));
await b.close();
