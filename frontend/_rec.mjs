// 콕집요청 15초 광고 — 실제 화면 녹화.
// 흐름: 조건 입력(번호 비공개 배지) → 받는 곳 선택 → 요청 → 제안 도착(매물·연락처).
// 로그인 없이 되는 구간만 쓴다(1~3단계 + /proposals 링크). 개인정보는 화면에 없다.
// env MOBILE=1 → 세로형. 콘솔에 컷 지점 타임스탬프. 스샷: req_outro(.m).png
import { chromium } from "playwright";

const MOBILE = process.env.MOBILE === "1";
const SP = process.env.SP;
const BIN = process.env.HOME
  + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/"
  + "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const DIR = MOBILE ? `${SP}/vreq_m` : `${SP}/vreq`;
const VW = MOBILE ? { width: 702, height: 1248 } : { width: 1280, height: 720 };
const SUF = MOBILE ? "_m" : "";
const PROPOSALS = "https://koczip.com/proposals/-L7kC1ldPtz8yvi2JL3sFRW0PhQY0cdI";

// 봇 가드가 헤드리스 UA를 막는다 — 실제 브라우저 UA 로 열어야 API 가 응답한다
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
  + "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36";
const browser = await chromium.launch({ executablePath: BIN });
const ctx = await browser.newContext({ viewport: VW, userAgent: UA, locale: "ko-KR",
                                       recordVideo: { dir: DIR, size: VW } });
const page = await ctx.newPage();
const T0 = Date.now();
const mark = (n) => console.log(`@${((Date.now() - T0) / 1000).toFixed(1)}s ${n}`);

// 커서·자막 주입 — 화면만 보면 무슨 일이 일어나는지 모른다
const inject = async () => {
  await page.evaluate((mobile) => {
    if (document.getElementById("__cur")) return;
    const c = document.createElement("div");
    c.id = "__cur";
    c.style.cssText = "position:fixed;z-index:2147483647;width:26px;height:26px;border-radius:50%;"
      + "background:rgba(18,104,211,.30);border:3px solid #1268d3;pointer-events:none;"
      + "transform:translate(-50%,-50%);left:-99px;top:-99px";
    document.body.appendChild(c);
    window.addEventListener("mousemove", (e) => {
      c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px";
    }, true);
    window.addEventListener("mousedown", () => {
      c.animate([{ boxShadow: "0 0 0 0 rgba(18,104,211,.55)" },
                 { boxShadow: "0 0 0 26px rgba(18,104,211,0)" }], { duration: 500 });
    }, true);
    const cap = document.createElement("div");
    cap.id = "__cap";
    cap.style.cssText = "position:fixed;left:50%;transform:translateX(-50%);z-index:2147483646;"
      + `bottom:${mobile ? 56 : 40}px;background:rgba(12,26,46,.92);color:#fff;`
      + `font:800 ${mobile ? 27 : 24}px Pretendard,-apple-system,sans-serif;letter-spacing:-.03em;`
      + "padding:13px 22px;border-radius:12px;opacity:0;transition:opacity .25s;white-space:nowrap";
    document.body.appendChild(cap);
    window.__say = (t) => {
      const e = document.getElementById("__cap");
      if (!t) { e.style.opacity = 0; return; }
      e.textContent = t; e.style.opacity = 1;
    };
  }, MOBILE);
};
const say = (t) => page.evaluate((x) => window.__say && window.__say(x), t);

// ── 1) 조건 입력 ────────────────────────────────────────────────────────
await page.goto("https://koczip.com/request", { waitUntil: "networkidle" });
await page.waitForSelector(".kreq-privacy", { timeout: 30000 });
await page.waitForTimeout(1200);
await inject();
mark("A0 시작");

await say("전화번호 없이 집을 구합니다");
await page.waitForTimeout(1600);

// 개인정보 안내 배너를 잠깐 키워 시선을 준다
await page.evaluate(() => {
  const el = document.querySelector(".kreq-privacy");
  if (el) {
    el.style.transition = "transform .5s, box-shadow .5s";
    el.style.transform = "scale(1.035)";
    el.style.boxShadow = "0 8px 26px rgba(31,157,99,.35)";
  }
});
await page.waitForTimeout(1500);
await page.evaluate(() => {
  const el = document.querySelector(".kreq-privacy");
  if (el) { el.style.transform = ""; el.style.boxShadow = ""; }
});

await say("찾는 조건만 남기면");
const sels = await page.$$(".kreq-region select");
if (sels[0]) {
  await page.waitForFunction(() =>
    document.querySelectorAll(".kreq-region select")[0].options.length > 1,
    { timeout: 15000 });
  await sels[0].click(); await sels[0].selectOption("1100000000");   // 서울시
}
await page.waitForTimeout(900);
if (sels[1]) {
  await page.waitForFunction(() =>
    document.querySelectorAll(".kreq-region select")[1].options.length > 1, { timeout: 15000 });
  await sels[1].click();
  await sels[1].selectOption("1165000000");        // 서초구
}
await page.waitForTimeout(1100);
mark("A1 조건입력 끝");

// ── 2) 받는 곳 ──────────────────────────────────────────────────────────
await say("동네 중개사무소가 매물을 찾아줍니다");
const next = await page.$("button.kreq-primary, .kreq-nav button:last-child");
if (next) { await next.click(); await page.waitForTimeout(900); }
const next2 = await page.$(".kreq-nav button:last-child");
if (next2) { await next2.click(); await page.waitForTimeout(2200); }
mark("B0 받는곳");
await page.waitForTimeout(900);

// ── 3) 제안 도착 ────────────────────────────────────────────────────────
// 실제 사무소명·연락처는 광고에 쓸 수 없다. 렌더 직후 한 프레임도 새지 않도록
// 화면이 그려지기 전에 감시자를 심어 두고 바로 예시 값으로 바꾼다.
await page.addInitScript(() => {
  // React 가 텍스트를 여러 노드로 쪼개 둔다 — 공백 아닌 텍스트 노드를 찾아 바꾼다
  const put = (root, val) => {
    if (!root) return;
    for (const x of root.childNodes) {
      if (x.nodeType === 3 && x.textContent.trim()) { x.textContent = val; return; }
    }
  };
  const mask = () => {
    const n = document.querySelector(".myoff-top b");
    if (n && !/OO공인/.test(n.textContent)) put(n, "OO공인중개사사무소");
    const t = document.querySelector(".myoff-tel");
    if (t && !/0000/.test(t.textContent)) put(t, "010-0000-0000");
  };
  // addInitScript 시점엔 documentElement 가 없어 MutationObserver 를 못 건다.
  // 50ms 폴링이 단순하고 확실하다(녹화용 스크립트라 비용은 무시해도 된다).
  setInterval(mask, 50);
});
await page.goto(PROPOSALS, { waitUntil: "networkidle" });
await page.waitForSelector(".myoff-card, .kreq-card", { timeout: 30000 });
await page.waitForFunction(() =>
  /OO공인/.test(document.querySelector(".myoff-top b")?.textContent || ""), { timeout: 10000 });
await inject();
await page.waitForTimeout(700);
mark("C0 제안도착");
await say("제안을 보고, 내가 먼저 전화합니다");
await page.evaluate(() => {
  const el = document.querySelector(".myoff-tel");
  if (el) {
    el.style.transition = "transform .45s, box-shadow .45s";
    el.style.transform = "scale(1.18)";
    el.style.boxShadow = "0 6px 22px rgba(18,104,211,.45)";
  }
});
await page.waitForTimeout(2400);
await say("");
await page.waitForTimeout(500);
mark("C1 끝");

await ctx.close();
await browser.close();
console.log("recorded →", DIR);
