import { chromium } from "playwright";
const SP="/private/tmp/claude-501/-Users-hcode-auto-naverreal/84bd098a-2780-407a-af1a-06575112e6c5/scratchpad";
const b=await chromium.launch();
for(const [suf,VW,mobile] of [["",{width:1280,height:720},false],["_m",{width:702,height:1248},true]]){
  const ctx=await b.newContext({viewport:VW});
  const p=await ctx.newPage();
  await p.setContent(`<body style="margin:0"><div style="position:fixed;inset:0;background:linear-gradient(135deg,#0f2c5c,#1268d3);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#fff;text-align:center">
    <div style="font-size:${mobile?64:78}px;font-weight:900;letter-spacing:-2px">콕집</div>
    <div style="font-size:${mobile?32:38}px;font-weight:900"><span style="color:#ffd76a">중개사 평생 무료</span></div>
    <div style="font-size:${mobile?22:26}px;font-weight:700;opacity:.95">매물 자동 점검으로 <span style="color:#ff9d9d">과태료 예방</span></div>
    <div style="margin-top:12px;font-size:${mobile?22:24}px;font-weight:800;background:rgba(255,255,255,.18);padding:11px 26px;border-radius:999px">koczip.com</div>
  </div></body>`);
  await p.waitForTimeout(300);
  await p.screenshot({path:`${SP}/audit_outro${suf}.png`, clip:{x:0,y:0,width:VW.width,height:VW.height}});
  await ctx.close();
  console.log("outro"+suf+" OK");
}
await b.close();
