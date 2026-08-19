// 라우트별 OG 카드 — SPA는 크롤러(카톡/페북)가 JS를 안 돌리므로, 빌드 후
// dist/<route>/index.html 정적 사본에 그 페이지 전용 메타를 심는다.
// CF Pages가 정적 파일을 SPA 폴백보다 먼저 서빙 → 공유 시 전용 카드가 뜬다.
// 새 페이지 카드가 필요하면 PAGES에 한 항목 추가 + public/og/ 에 이미지.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";

const PAGES = [
  {
    path: "finder",
    title: "맞춤단지 찾기 — 조건만 고르면 딱 맞는 단지 | 콕집",
    desc: "평형대·가격·입주년차·세대수·전세가율·갭·방 개수·역세권·초등학교까지 — 조건을 고르면 지역 안 모든 단지·평형에서 꼭 맞는 것만 골라드립니다.",
    image: "https://koczip.com/og/finder.png",
    url: "https://koczip.com/finder",
  },
];

const src = readFileSync("dist/index.html", "utf8");
const put = (html, re, val) => html.replace(re, (_m, a, b) => a + val + b);

for (const p of PAGES) {
  let h = src;
  h = h.replace(/<title>[^<]*<\/title>/, () => `<title>${p.title}</title>`);
  h = put(h, /(<meta name="description" content=")[^"]*(")/, p.desc);
  h = put(h, /(<meta property="og:title" content=")[^"]*(")/, p.title);
  h = put(h, /(<meta property="og:description" content=")[^"]*(")/, p.desc);
  h = put(h, /(<meta property="og:url" content=")[^"]*(")/, p.url);
  h = put(h, /(<meta property="og:image" content=")[^"]*(")/, p.image);
  h = put(h, /(<meta name="twitter:title" content=")[^"]*(")/, p.title);
  h = put(h, /(<meta name="twitter:description" content=")[^"]*(")/, p.desc);
  h = put(h, /(<meta name="twitter:image" content=")[^"]*(")/, p.image);
  mkdirSync(`dist/${p.path}`, { recursive: true });
  writeFileSync(`dist/${p.path}/index.html`, h);
  console.log(`og page: dist/${p.path}/index.html`);
}
