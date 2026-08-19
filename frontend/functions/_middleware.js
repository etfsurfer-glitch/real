// 검색봇 전용 동적 렌더링(Dynamic Rendering).
// 일반 사용자는 평소 SPA 그대로(next()), 검색/공유 봇만 서버에서 만든
// 콘텐츠+메타가 든 HTML을 받는다. 어떤 오류든 next()로 폴백 → 사용자 영향 0.

const API = "https://api.koczip.com";
const SITE = "https://koczip.com";
const SITE_REAL = "https://real.koczip.com";
const OG_IMG = "https://koczip.com/og.png";

// 검색 크롤러/링크 스크래퍼만 매칭. 네이버/다음 '앱 인앱 브라우저'(NAVER(inapp..)/DaumApps)는
// 실제 사용자이므로 제외 — 크롤러는 yeti(네이버)·daumoa(다음). bare 'naver'/'daum'은 인앱을 오인해 SPA 대신
// 봇용 텍스트 페이지를 줘서 "텍스트 몇 줄만 보임" 버그를 유발했음.
const BOT = /(yeti|googlebot|google-inspectiontool|bingbot|duckduckbot|daumoa|facebookexternalhit|facebot|twitterbot|slackbot|telegrambot|kakaotalk-scrap|line-poker|whatsapp|applebot)/i;

const STATIC_ROUTES = {
  "/": ["콕집 — 부동산 매물·실거래·중개사무소 분석", "전국 아파트·오피스텔 실거래가·매물·중개사무소를 매일 분석. 급매·저평가 단지, 시세 통계, AI 질의응답, 부동산 토론장까지 콕집에서."],
  "/overview": ["전국 부동산 현황 | 콕집", "전국 아파트 매물·실거래 현황과 지역별 거래량·국민평형 시세를 한눈에. 매일 갱신되는 부동산 데이터."],
  "/quick-deals": ["급매찾기 — 실거래 평균보다 싼 매물 | 콕집", "최근 실거래 평균보다 저렴하게 나온 급매 매물을 단지·평형별로 모았습니다. 매매·전세 급매를 한 곳에서."],
  "/map": ["지도보기 — 단지별 매물 지도 | 콕집", "지도에서 단지별 매매·전세·월세 매물 수와 시세를 확인하세요. 지역을 골라 탐색."],
  "/map/deal": ["급매 지도 | 콕집", "지도에서 실거래 평균 대비 저렴한 급매 매물이 있는 단지를 확인하세요."],
  "/changes": ["매물 가격 변화 — 추이·지역순위·상승하락 | 콕집", "전국·지역별 매물 가격 추이와 상승·하락 단지 순위를 매일 갱신해 보여드립니다."],
  "/realtors": ["중개사무소 매물 보유 순위 | 콕집", "전국 중개사무소의 보유 매물 수·업력·직원수 순위. 중개사무소 검색과 상세 실적 제공."],
  "/forum": ["부동산 토론장 | 콕집", "부동산 매물·실거래·시세에 대해 자유롭게 의견을 나누는 콕집 토론장."],
  "/terms": ["이용약관 | 콕집", "콕집 서비스 이용약관."],
  "/privacy": ["개인정보처리방침 | 콕집", "콕집 개인정보처리방침."],
};

// 중개사라운지 하위메뉴별 OG(제목·부제·설명) — 백엔드 _LOUNGE_OG 와 동일하게 유지.
const LOUNGE_OG = {
  dashboard: ["중개사라운지", "내 사무소 매물·실적을 한눈에", "매물장·매물점검·상담관리·사무소 홈페이지까지 — 공인중개사 업무를 콕집 라운지에서."],
  listings: ["내 매물장", "내 매물을 다이어리처럼 관리", "네이버에 올린 내 매물을 콕집이 자동 수집·정리. 매물 현황과 시세를 한 화면에서."],
  audit: ["매물점검", "표시·광고 위반(과태료) 사전 자가점검", "중개대상물 표시·광고 의무사항을 자동 점검. 과태료 리스크를 미리 걸러냅니다."],
  leads: ["상담신청 관리", "고객 상담 문의를 라운지에서", "홈페이지·매물로 들어온 고객 상담을 놓치지 않고 한 곳에서 관리."],
  homepage: ["사무소 홈페이지", "무료 중개사무소 홈페이지 제작", "real.koczip.com/내주소 — 매물·소개·연락처를 담은 사무소 전용 홈페이지를 무료로."],
  staff: ["직원관리", "소속 공인중개사·중개보조원 관리", "사무소 소속 직원을 등록·관리하고 매물·상담을 함께 운영하세요."],
  edit: ["정보수정요청", "사무소 정보 수정 요청", "대표·연락처·주소 등 사무소 정보를 최신으로 유지하도록 수정 요청."],
};

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function page(title, desc, canonical, h1, bodyHtml, ogImage) {
  const img = ogImage || OG_IMG;
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}"/>
<link rel="canonical" href="${esc(canonical)}"/>
<meta name="robots" content="index, follow"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="콕집"/>
<meta property="og:locale" content="ko_KR"/>
<meta property="og:title" content="${esc(title)}"/>
<meta property="og:description" content="${esc(desc)}"/>
<meta property="og:url" content="${esc(canonical)}"/>
<meta property="og:image" content="${img}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="${esc(title)}"/>
<meta name="twitter:description" content="${esc(desc)}"/>
<meta name="twitter:image" content="${img}"/>
<meta name="naver-site-verification" content="3f4e9fd612c3c9dff35fd9a54c6689636326e375"/>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"콕집","alternateName":"koczip","url":"https://koczip.com/","inLanguage":"ko-KR","publisher":{"@type":"Organization","name":"콕집","alternateName":"koczip","url":"https://koczip.com/","logo":"https://koczip.com/icon-512.png"}}</script>
</head><body>
<h1>${esc(h1)}</h1>
${bodyHtml}
<nav><a href="${SITE}/overview">전국현황</a> · <a href="${SITE}/quick-deals">급매찾기</a> · <a href="${SITE}/tx-stats">실거래 통계</a> · <a href="${SITE}/realtors">중개사무소 랭킹</a> · <a href="${SITE}/map">지도보기</a></nav>
</body></html>`;
}

async function renderComplex(no, canonical) {
  const r = await fetch(`${API}/complex/${encodeURIComponent(no)}/seo`, { cf: { cacheTtl: 300 } });
  if (!r.ok) return null;
  const d = await r.json();
  const name = d.name || "단지";
  const region = d.dong ? `${d.dong} ` : "";
  const title = `${name} 시세·실거래가·매물 | 콕집`;
  const bits = [];
  if (d.address) bits.push(`주소 ${d.address}`);
  if (d.households) bits.push(`${Number(d.households).toLocaleString()}세대`);
  if (d.approve_year) bits.push(`${d.approve_year}년 준공`);
  const facts = bits.join(" · ");
  const desc = `${region}${name}의 실거래가, 매물 호가, 평형별 시세, 세대수 정보를 콕집에서 확인하세요.${facts ? " " + facts + "." : ""}`;
  const body = `<p>${esc(region)}<strong>${esc(name)}</strong> (${esc(d.kind || "아파트")})${facts ? " — " + esc(facts) : ""}</p>
<p>${esc(name)}의 최근 실거래가와 매물 호가, 평형별 평균 시세, 전세·월세 현황을 콕집에서 매일 갱신해 제공합니다.</p>
<p><a href="${canonical}">${esc(name)} 상세 보기 →</a></p>`;
  const ogImg = `${API}/complex/${encodeURIComponent(no)}/og.png`;   // 단지별 동적 OG 카드
  return page(title, desc, canonical, `${region}${name} 시세·실거래가`, body, ogImg);
}

// 중개사 홈페이지(real.koczip.com/{slug}) OG — 중개사 인적사항을 명함처럼, 콕집은 작게.
// 각 홈페이지가 개별 OG 카드 이미지(API가 생성)를 가진다.
async function renderHomepage(slug, canonical) {
  const r = await fetch(`${API}/public/homepage/${encodeURIComponent(slug)}`, { cf: { cacheTtl: 120 } });
  if (!r.ok) return null;
  const d = await r.json();
  const o = d.office || {}, c = d.config || {};
  const name = o.realtor_name || "공인중개사무소";
  const title = name + (o.representative ? ` · 대표 ${o.representative}` : "");
  const tel = c.consult_tel || o.tel || o.cell || "";
  const desc = [c.slogan, o.address, tel ? `전화 ${tel}` : null, c.specialties]
    .filter(Boolean).join(" · ").slice(0, 150) || `${name} 부동산 매물·시세`;
  const ogimg = `${API}/public/homepage/${encodeURIComponent(slug)}/og.png`;
  const body = `<p>${esc(o.address || "")}</p><p>${esc(c.slogan || "")}</p>
${tel ? `<p>전화 ${esc(tel)}</p>` : ""}<p><a href="${canonical}">${esc(name)} 홈페이지 →</a></p>`;
  // og:site_name = 중개사무소명(본인 브랜드처럼). 콕집은 카드 이미지에 작게.
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>${esc(title)} | ${esc(name)}</title>
<meta name="description" content="${esc(desc)}"/>
<link rel="canonical" href="${esc(canonical)}"/>
<meta name="robots" content="index, follow"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="${esc(name)}"/>
<meta property="og:locale" content="ko_KR"/>
<meta property="og:title" content="${esc(title)}"/>
<meta property="og:description" content="${esc(desc)}"/>
<meta property="og:url" content="${esc(canonical)}"/>
<meta property="og:image" content="${ogimg}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="${esc(title)}"/>
<meta name="twitter:description" content="${esc(desc)}"/>
<meta name="twitter:image" content="${ogimg}"/>
</head><body><h1>${esc(name)}</h1>${body}</body></html>`;
}

export async function onRequest(context) {
  const { request, next } = context;
  try {
    const ua = request.headers.get("user-agent") || "";
    const url = new URL(request.url);
    const path = url.pathname;
    // 중개사 홈페이지 호스트: 봇이면 개별 OG HTML, 사람이면 SPA
    if (url.hostname === "real.koczip.com") {
      if (!BOT.test(ua)) return next();
      if (path.includes(".") || path.startsWith("/assets")) return next();
      const slug = path.replace(/^\/+/, "").split("/")[0];
      const html = slug ? await renderHomepage(slug, `${SITE_REAL}/${slug}`) : null;
      if (!html) return next();
      return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "x-prerender": "homepage" } });
    }
    if (!BOT.test(ua)) return next();                 // 사람 → 평소 SPA
    // 정적 자원·API·sitemap 등은 그대로
    if (path.includes(".") || path.startsWith("/assets") || path.startsWith("/api")) return next();

    const canonical = SITE + path;
    let html = null;

    const mComplex = path.match(/^\/complex\/([^/]+)/);
    if (mComplex) {
      html = await renderComplex(mComplex[1], canonical);
    } else if (path === "/lounge") {
      const tab = url.searchParams.get("tab") || "dashboard";
      const [t, sub, desc] = LOUNGE_OG[tab] || LOUNGE_OG.dashboard;
      const title = `${t} | 콕집 중개사라운지`;
      const cano = SITE + "/lounge" + (tab === "dashboard" ? "" : `?tab=${tab}`);
      const ogImg = `${API}/public/lounge/og.png?tab=${encodeURIComponent(tab)}`;
      html = page(title, `${sub} — ${desc}`, cano, t, `<p>${esc(desc)}</p>`, ogImg);
    } else if (STATIC_ROUTES[path]) {
      const [t, dsc] = STATIC_ROUTES[path];
      html = page(t, dsc, canonical, t.split(" | ")[0].split(" — ")[0], `<p>${esc(dsc)}</p>`);
    } else if (path.startsWith("/tx-stats")) {
      html = page("실거래 통계 | 콕집", "전국 아파트 실거래 기반 갭·전세가율·평당가·거래량·신고가·회전율·월세수익률 통계.", canonical, "실거래 통계", "<p>전국 아파트 실거래 데이터로 만든 갭투자·전세가율·평당가·거래량·신고가·저평가 통계를 제공합니다.</p>");
    }

    if (!html) return next();                          // 매핑 없으면 평소 SPA
    return new Response(html, {
      headers: { "content-type": "text/html; charset=utf-8", "x-prerender": "bot" },
    });
  } catch (e) {
    return next();                                     // 어떤 오류든 안전 폴백
  }
}
