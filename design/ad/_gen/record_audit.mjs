// 매물점검 12초 광고 재작성 — 문제 매물 카드를 보여주고 마지막 클로즈업+홀드.
// 주소·매물번호는 블러(특정매물 노출 방지). 위반/주의 사유는 노출(가치 전달).
// env MOBILE=1 → 세로형. 콘솔에 장면 타임스탬프(편집 컷). 스샷: audit_card(.m).png, audit_outro(.m).png
import { chromium } from "playwright";

const MOBILE = process.env.MOBILE === "1";
const SP = "/private/tmp/claude-501/-Users-hcode-auto-naverreal/84bd098a-2780-407a-af1a-06575112e6c5/scratchpad";
const DIR = MOBILE ? `${SP}/vida_m` : `${SP}/vida`;
const VW = MOBILE ? { width: 702, height: 1248 } : { width: 1280, height: 720 };
const SUF = MOBILE ? "_m" : "";

const SB_URL = process.env.SUPABASE_URL, SB_KEY = process.env.SUPABASE_SECRET_KEY;
const r = await fetch(`${SB_URL}/auth/v1/admin/generate_link`, {
  method: "POST",
  headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}`, "Content-Type": "application/json" },
  body: JSON.stringify({ type: "magiclink", email: "hic0076@gmail.com" }),
});
const link = (await r.json()).action_link;

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: VW, recordVideo: { dir: DIR, size: VW } });
const page = await ctx.newPage();
const T0 = Date.now();
const mark = (n) => console.log(`@${((Date.now() - T0) / 1000).toFixed(1)}s ${n}`);

await page.goto(link, { waitUntil: "networkidle" });
await page.goto("https://koczip.com/lounge", { waitUntil: "networkidle" });
await page.waitForTimeout(4500);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector("text=매물점검", { timeout: 40000 });
await page.waitForTimeout(1000);
mark("준비완료");

// 커서·자막·PII블러 주입
await page.evaluate((mobile) => {
  const c = document.createElement("div");
  c.style.cssText = "position:fixed;z-index:2147483647;width:26px;height:26px;border-radius:50%;"
    + "background:rgba(18,104,211,.30);border:3px solid #1268d3;pointer-events:none;"
    + "transform:translate(-50%,-50%);left:340px;top:360px";
  document.body.appendChild(c);
  window.addEventListener("mousemove", (e) => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
  window.addEventListener("mousedown", () => {
    c.animate([{ boxShadow: "0 0 0 0 rgba(224,36,94,.55)" }, { boxShadow: "0 0 0 26px rgba(224,36,94,0)" }], { duration: 500 });
  }, true);
  const cap = document.createElement("div");
  cap.style.cssText = `position:fixed;left:${mobile ? 22 : 30}px;bottom:${mobile ? 26 : 28}px;z-index:2147483646;`
    + "background:#13294b;color:#fff;font-weight:800;"
    + `font-size:${mobile ? 26 : 30}px;letter-spacing:-.5px;padding:${mobile ? "13px 22px" : "14px 26px"};border-radius:16px;`
    + "box-shadow:0 12px 34px rgba(19,41,75,.45);pointer-events:none;opacity:0;transition:opacity .18s;"
    + "font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif";
  document.body.appendChild(cap);
  window.__cap = (t) => {
    if (!t) { cap.style.opacity = "0"; return; }
    cap.innerHTML = t; cap.style.opacity = "1";
    cap.animate([{ transform: "translateY(10px)" }, { transform: "translateY(0)" }], { duration: 240 });
  };
  // PII 블러: 주소(📍)·네이버매물번호 링크. 스타일 태그로 상시 적용(재렌더 대비).
  const st = document.createElement("style");
  st.textContent = ".koc-blur{filter:blur(6px)!important;user-select:none!important}";
  document.head.appendChild(st);
  window.__blur = () => {
    document.querySelectorAll("a[href*='land.naver.com']").forEach((a) => a.classList.add("koc-blur"));
    document.querySelectorAll("span").forEach((s) => {
      const t = (s.textContent || "").trim();
      const st = s.getAttribute("style") || "";
      if (t.startsWith("📍") || /^매물번호\s/.test(t)) s.classList.add("koc-blur");
      // 건물명(카드 헤더 span: ellipsis + font-weight 600) — 특정단지 식별 방지
      if (st.includes("text-overflow: ellipsis") && st.includes("font-weight: 600")) s.classList.add("koc-blur");
    });
  };
}, MOBILE);
const cap = (t) => page.evaluate((x) => window.__cap(x), t);
const blur = () => page.evaluate(() => window.__blur());
const move = async (loc) => { const b = await loc.boundingBox(); if (b) await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 14 }); };

// ── 매물점검 탭으로 바로 진입(라운지 대시보드 노출 없이) ──
const tab = page.locator("text=매물점검").first();
await tab.click();
await page.waitForSelector('button[title="유형 전체 선택/해제"]', { timeout: 30000 });
await page.waitForTimeout(300);
mark("A0-점검탭");   // ← 인트로 시작
await cap("표시·광고 <span style='color:#9ec5f5'>12항목 자동 검사</span>");
await page.waitForTimeout(700);

// ── 장면2: 유형 선택 (위반이 몰린 상가·사무실 계열 선택) ──
const boxes = page.locator('button[title="유형 전체 선택/해제"]');
const idx = await page.evaluate(() => {
  const btns = [...document.querySelectorAll('button[title="유형 전체 선택/해제"]')];
  return btns.findIndex((b) => ((b.closest("div")?.textContent) || "").includes("상가"));
});
const pick = idx >= 0 ? boxes.nth(idx) : boxes.nth(0);
await cap("유형 선택 후 <span style='color:#ffd76a'>클릭 한 번</span>");
await move(pick); await pick.click();
await page.waitForTimeout(600);

// ── 장면3: 일괄조회 ──
const run = page.locator("button", { hasText: "일괄조회" }).first();
await cap("<span style='color:#ffd76a'>일괄</span> 자동 점검");
await move(run); await run.click();
mark("A1-점검시작");
await cap("12개 법정 항목 <span style='color:#ffd76a'>검사 중…</span>");
await page.waitForTimeout(2000);
mark("A1끝-컷아웃");

// ── 점검 완료 대기 ──
await page.waitForSelector("text=점검 완료", { timeout: 300000 });
await blur();
await page.waitForTimeout(300);

// ── 도장 함수 주입: '위반' 고무도장이 쾅! 찍히는 애니메이션 ──
await page.evaluate(() => {
  window.__stamp = (rect, text, color) => {
    const s = document.createElement("div");
    s.textContent = text;
    s.style.cssText = `position:fixed;left:${rect.left + rect.width * 0.5 - 60}px;top:${rect.top - 4}px;`
      + `z-index:2147483641;color:${color};font-weight:900;font-size:34px;letter-spacing:3px;`
      + `border:5px solid ${color};border-radius:10px;padding:2px 16px;opacity:0;`
      + `font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;pointer-events:none;`
      + `transform:rotate(-13deg) scale(2.7);text-shadow:0 1px 0 rgba(255,255,255,.6)`;
    document.body.appendChild(s);
    s.animate([
      { transform: "rotate(-13deg) scale(2.7)", opacity: 0 },
      { transform: "rotate(-13deg) scale(0.9)", opacity: 1, offset: 0.55 },
      { transform: "rotate(-13deg) scale(1)", opacity: 1 },
    ], { duration: 240, fill: "forwards", easing: "cubic-bezier(.2,1.5,.35,1)" });
    // 쾅 임팩트: 화면 살짝 흔들림
    document.body.animate(
      [{ transform: "translateY(0)" }, { transform: "translateY(4px)" }, { transform: "translateY(0)" }],
      { duration: 130 });
    return s;
  };
});

// ── 위반 최다 카드를 펼친다 ──
mark("B0-카드펼침");
await page.evaluate(() => {
  const spans = [...document.querySelectorAll("span")];
  const badge = spans.find((s) => /^위반\s+\d+/.test((s.textContent || "").trim()));
  let hdr = badge;
  while (hdr && !((hdr.getAttribute && (hdr.getAttribute("style") || "").includes("cursor: pointer")))) hdr = hdr.parentElement;
  if (hdr) { hdr.scrollIntoView({ block: "start", behavior: "instant" }); window.scrollBy(0, -90); hdr.click(); }
});
await page.waitForTimeout(500);
await blur();
await cap("<span style='color:#ff6b6b'>반드시 고쳐야 할</span> 항목을 콕 집어");
await page.waitForTimeout(700);

// ── 위반 행들을 아래로 훑으며 '위반' 도장 쾅쾅쾅 ──
const vioCount = await page.evaluate(() =>
  [...document.querySelectorAll("li")].filter((li) =>
    [...li.querySelectorAll("span")].some((s) => (s.textContent || "").trim() === "위반")).length);
const N = Math.min(vioCount, 5);
for (let i = 0; i < N; i++) {
  await blur();
  const rect = await page.evaluate((idx) => {
    const rows = [...document.querySelectorAll("li")].filter((li) =>
      [...li.querySelectorAll("span")].some((s) => (s.textContent || "").trim() === "위반"));
    const li = rows[idx];
    if (!li) return null;
    li.scrollIntoView({ block: "center", behavior: "instant" });
    window.scrollBy(0, 40);
    const b = li.getBoundingClientRect();
    return { left: b.left, top: b.top, width: b.width, height: b.height };
  }, i);
  if (!rect) break;
  await page.waitForTimeout(120);
  await page.evaluate((r) => window.__stamp(r, "위반", "#e11d1d"), rect);
  mark(`도장${i + 1}`);
  await page.waitForTimeout(560);   // 쾅 인식 시간
}
await page.waitForTimeout(500);
mark("B1-도장끝");

// ── 아웃트로 스샷 ──
await page.evaluate((mobile) => {
  const o = document.createElement("div");
  o.style.cssText = "position:fixed;inset:0;z-index:2147483645;background:linear-gradient(135deg,#0f2c5c,#1268d3);"
    + "display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;"
    + "font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#fff;text-align:center";
  o.innerHTML = `<div style="font-size:${mobile ? 64 : 78}px;font-weight:900;letter-spacing:-2px">콕집</div>`
    + `<div style="font-size:${mobile ? 32 : 38}px;font-weight:900"><span style="color:#ffd76a">중개사 평생 무료</span></div>`
    + `<div style="font-size:${mobile ? 22 : 26}px;font-weight:700;opacity:.95">매물 자동 점검으로 <span style="color:#ff9d9d">과태료 예방</span></div>`
    + `<div style="margin-top:12px;font-size:${mobile ? 22 : 24}px;font-weight:800;background:rgba(255,255,255,.18);padding:11px 26px;border-radius:999px">koczip.com</div>`;
  document.body.appendChild(o);
}, MOBILE);
await page.waitForTimeout(400);
await page.screenshot({ path: `${SP}/audit_outro${SUF}.png`, clip: { x: 0, y: 0, width: VW.width, height: VW.height } });
mark("아웃트로 스샷 OK");
await page.waitForTimeout(200);

await ctx.close();
await browser.close();
console.log("recorded", MOBILE ? "portrait" : "landscape");
