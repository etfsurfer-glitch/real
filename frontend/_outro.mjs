// 콕집요청 광고 아웃트로 카드 — 핵심 문구 3줄 + 로고.
import { chromium } from "playwright";
const M = process.env.MOBILE === "1", SP = process.env.SP;
const BIN = process.env.HOME + "/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
const W = M ? 702 : 1280, H = M ? 1248 : 720;
const html = `<!doctype html><meta charset=utf-8><style>
@font-face{font-family:P;src:local("Pretendard")}
*{margin:0;box-sizing:border-box}
body{width:${W}px;height:${H}px;display:flex;flex-direction:column;align-items:center;
justify-content:center;gap:${M ? 34 : 26}px;background:linear-gradient(160deg,#0d3f86,#1268d3 60%,#1f7fe0);
font-family:Pretendard,-apple-system,"Apple SD Gothic Neo",sans-serif;color:#fff}
.l{display:flex;align-items:center;gap:${M ? 16 : 13}px;margin-bottom:${M ? 8 : 4}px}
.l svg{width:${M ? 66 : 54}px;height:${M ? 66 : 54}px;display:block}
.l b{font-size:${M ? 60 : 48}px;letter-spacing:-.045em}
p{font-size:${M ? 40 : 33}px;font-weight:800;letter-spacing:-.04em;line-height:1.45;text-align:center}
p span{opacity:.55;font-weight:600;margin:0 ${M ? 12 : 10}px}
u{text-decoration:none;font-size:${M ? 27 : 22}px;font-weight:600;opacity:.8;letter-spacing:-.02em;
margin-top:${M ? 12 : 6}px}
</style>
<div class=l>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" aria-hidden="true">
  <path d="M 50 10 L 92 46 L 92 92 L 8 92 L 8 46 Z" fill="#ffffff"/>
  <path d="M 28 58 L 44 73 L 74 42" stroke="#1268d3" stroke-width="10"
        stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg><b>콕집</b></div>
${M ? `<p>개인정보를 지킨다<br>급매를 잡는다<br>한번에 의뢰한다</p>`
    : `<p>개인정보를 지킨다<span>·</span>급매를 잡는다<span>·</span>한번에 의뢰한다</p>`}
<u>koczip.com</u>`;
const b = await chromium.launch({ executablePath: BIN });
const p = await (await b.newContext({ viewport: { width: W, height: H } })).newPage();
await p.setContent(html); await p.waitForTimeout(500);
await p.screenshot({ path: `${SP}/req_outro${M ? "_m" : ""}.png` });
await b.close(); console.log("outro ok");
