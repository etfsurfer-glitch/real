// 휴대폰 실기기 대신 Playwright iPhone 에뮬레이션으로 지도 시험판을 눌러 보며 캡처한다.
import { chromium, devices } from "playwright";
import fs from "node:fs";

const OUT = process.argv[2] || ".";
const BASE = "https://testv2.koczip.com/";
const Q = "layer=deals&lat=37.5160&lng=127.1020&lv=4";
const errors = [];
const bad = [];

const browser = await chromium.launch();
const ctx = await browser.newContext({ ...devices["iPhone 13"], locale: "ko-KR" });
const page = await ctx.newPage();
page.on("pageerror", (e) => errors.push(String(e.message).slice(0, 200)));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text().slice(0, 200)); });
page.on("response", (r) => { const u = r.url(); if (r.status() >= 400 && /api\.koczip\.com|testv2\.koczip\.com/.test(u)) bad.push(`${r.status()} ${u.slice(0, 140)}`); });

const settle = async (ms = 2500) => { try { await page.waitForLoadState("networkidle", { timeout: 15000 }); } catch { /* 지도 타일은 계속 와서 idle 이 안 될 수 있다 */ } await page.waitForTimeout(ms); };
const shot = async (name) => { await page.screenshot({ path: `${OUT}/pw_${name}.png` }); console.log("shot", name); };
const go = async (q) => { await page.goto(BASE + "?" + q, { waitUntil: "domcontentloaded" }); await settle(); };
const tapText = async (t, opts = {}) => { const l = page.getByText(t, { exact: true, ...opts }).first(); await l.waitFor({ timeout: 8000 }); await l.tap(); await settle(1500); };

try {
  await go(Q); await shot("01_deals");
  // 시트의 급매 목록에서 단지 열기
  try { await tapText("잠실주공5단지"); await shot("02_drawer_deals"); } catch (e) { console.log("drawer open fail", e.message); }
  try { await page.getByRole("tab", { name: "실거래" }).first().tap(); await settle(2000); await shot("03_drawer_tx"); } catch (e) { console.log("tx tab", e.message); }
  try { await page.getByRole("tab", { name: "단지정보" }).first().tap(); await settle(2000); await shot("04_drawer_info"); } catch (e) { console.log("info tab", e.message); }
  // 필터 드롭다운
  await go(Q);
  try { await tapText("단지정보"); await shot("05_filter_cx"); await page.keyboard.press("Escape"); } catch (e) { console.log("filter", e.message); }
  try { await tapText("방/욕실"); await shot("06_filter_rb"); await page.keyboard.press("Escape"); } catch (e) { console.log("filter2", e.message); }
  // 동·구 묶음
  await go("layer=deals&lat=37.5160&lng=127.1020&lv=6"); await shot("07_dong_agg");
  await go("layer=deals&lat=37.5500&lng=126.9800&lv=9"); await shot("08_gu_agg");
  // 시세분석
  await go("layer=price&m=tx&lat=37.5160&lng=127.1020&lv=4"); await shot("09_price_tx");
  await go("layer=price&m=vol&lat=37.5160&lng=127.1020&lv=4"); await shot("10_price_vol");
  // 중개사
  await go("layer=realtor&lat=37.5160&lng=127.1020&lv=4"); await shot("11_realtor");
  try { await tapText("구"); await shot("12_realtor_gu"); } catch (e) { console.log("gu", e.message); }
  // 통계 창
  await go(Q + "&stats=price.top"); await shot("13_stats_top");
  await go(Q + "&stats=flow.vol"); await shot("14_stats_vol");
  await go(Q + "&stats=hoga.sum"); await settle(2500); await shot("15_stats_hoga");
  // 안심
  await go(Q + "&safe=jeonse");
  try { await page.getByPlaceholder(/주소/).first().fill("화곡동 102-119"); await tapText("조회"); await settle(4000); await shot("16_safe_jeonse"); } catch (e) { console.log("jeonse", e.message); await shot("16_safe_jeonse"); }
  await go(Q + "&safe=calc"); await shot("17_safe_calc");
  // 매물의뢰
  await go(Q + "&ask=req"); await shot("18_ask_req");
  await page.mouse.wheel(0, 900); await page.waitForTimeout(800); await shot("19_ask_req_scrolled");
  await go(Q + "&ask=ai");
  try { await page.getByPlaceholder(/급매/).first().fill("송파구 30평대 급매 찾아줘"); await page.keyboard.press("Enter"); await page.waitForTimeout(25000); await shot("20_ask_ai"); } catch (e) { console.log("ai", e.message); await shot("20_ask_ai"); }
  await go(Q + "&ask=mine"); await shot("21_ask_mine");
  // 관심단지 · 사무소 상세
  await go(Q + "&fav=1"); await shot("22_fav");
  await go(Q + "&rt=opera4243002"); await settle(2500); await shot("23_realtor_win");
  await page.mouse.wheel(0, 1200); await page.waitForTimeout(800); await shot("24_realtor_win_scrolled");
  // 탭바 메뉴
  await go(Q);
  try { await tapText("의뢰"); await shot("25_tab_req_menu"); } catch (e) { console.log("tabbar", e.message); }
  try { await tapText("더보기"); await shot("26_tab_more"); } catch (e) { console.log("more", e.message); }
} finally {
  fs.writeFileSync(`${OUT}/pw_report.json`, JSON.stringify({ errors, bad }, null, 2));
  console.log("errors", errors.length, "bad", bad.length);
  await browser.close();
}
