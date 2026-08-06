// 콕집 카드뉴스 배경 10종 — 브랜드 정체성(파랑 #1268d3, Pretendard) + 콕집명·접속주소 내장.
// 각 배경은 { key, name, page(카드 전체 배경 CSS), ink(본문 글자색), sub(보조색),
//   accent(강조색), band(제목띠 배경), bandInk(제목띠 글자), rowBg(행 배경), rowInk, chipBg, chipInk, logoInvert }.
// CardFrame 이 이 토큰으로 카드를 렌더 → 관리자가 배경만 바꿔도 전 카드 일관 적용.

export type CardBg = {
  key: string;
  name: string;
  page: React.CSSProperties;
  ink: string;
  sub: string;
  accent: string;
  band: string;      // 제목 영역 배경
  bandInk: string;
  rowBg: string;
  rowInk: string;
  rowSub: string;
  chipBg: string;
  chipInk: string;
  divider: string;
  logoInvert?: boolean;   // 어두운 배경이면 로고를 흰색 처리
};

const BLUE = "#1268d3";
const BLUE_DK = "#0c4ea0";
const NAVY = "#0b1f3a";

export const CARD_BGS: CardBg[] = [
  {
    key: "clean", name: "클린 화이트",
    page: { background: "#ffffff" },
    ink: "#16233b", sub: "#64748b", accent: BLUE,
    band: BLUE, bandInk: "#ffffff",
    rowBg: "#f5f8fd", rowInk: "#1a2942", rowSub: "#64748b",
    chipBg: "#e8f1fc", chipInk: BLUE_DK, divider: "#e8eef7",
  },
  {
    key: "brand-gradient", name: "브랜드 그라데이션",
    page: { background: `linear-gradient(155deg, ${BLUE} 0%, ${BLUE_DK} 60%, #08386f 100%)` },
    ink: "#ffffff", sub: "#c9dcf5", accent: "#ffd666",
    band: "rgba(255,255,255,.14)", bandInk: "#ffffff",
    rowBg: "rgba(255,255,255,.10)", rowInk: "#ffffff", rowSub: "#c2d6f2",
    chipBg: "rgba(255,255,255,.22)", chipInk: "#ffffff", divider: "rgba(255,255,255,.18)",
    logoInvert: true,
  },
  {
    key: "navy", name: "딥 네이비",
    page: { background: NAVY },
    ink: "#eef4ff", sub: "#8fa6c8", accent: "#4d9bff",
    band: BLUE, bandInk: "#ffffff",
    rowBg: "#13294a", rowInk: "#eef4ff", rowSub: "#8fa6c8",
    chipBg: "#1d3a63", chipInk: "#9cc4ff", divider: "#1f355e",
    logoInvert: true,
  },
  {
    key: "soft-tint", name: "소프트 블루",
    page: { background: "radial-gradient(120% 90% at 0% 0%, #eaf2fe 0%, #f7fafe 55%, #ffffff 100%)" },
    ink: "#16233b", sub: "#5d6f88", accent: BLUE,
    band: "#ffffff", bandInk: BLUE_DK,
    rowBg: "#ffffff", rowInk: "#1a2942", rowSub: "#64748b",
    chipBg: "#e8f1fc", chipInk: BLUE_DK, divider: "#dbe7f6",
  },
  {
    key: "ribbon", name: "다이애거널 리본",
    page: { background: `#ffffff` },
    ink: "#16233b", sub: "#64748b", accent: BLUE,
    band: `linear-gradient(100deg, ${BLUE} 0%, #2f86e6 100%)`, bandInk: "#ffffff",
    rowBg: "#f4f7fc", rowInk: "#1a2942", rowSub: "#64748b",
    chipBg: "#e8f1fc", chipInk: BLUE_DK, divider: "#e8eef7",
  },
  {
    key: "dots", name: "블루 도트",
    page: {
      background:
        `radial-gradient(circle, #d3e4fb 1.5px, transparent 1.6px) 0 0/26px 26px, #f4f8fe`,
    },
    ink: "#16233b", sub: "#5d6f88", accent: BLUE,
    band: BLUE_DK, bandInk: "#ffffff",
    rowBg: "#ffffff", rowInk: "#1a2942", rowSub: "#64748b",
    chipBg: "#e8f1fc", chipInk: BLUE_DK, divider: "#e2ebf7",
  },
  {
    key: "teal", name: "블루-틸 그라데이션",
    page: { background: "linear-gradient(150deg, #1268d3 0%, #1596b6 100%)" },
    ink: "#ffffff", sub: "#d6f0f4", accent: "#ffe27a",
    band: "rgba(255,255,255,.16)", bandInk: "#ffffff",
    rowBg: "rgba(255,255,255,.12)", rowInk: "#ffffff", rowSub: "#d6f0f4",
    chipBg: "rgba(255,255,255,.24)", chipInk: "#ffffff", divider: "rgba(255,255,255,.2)",
    logoInvert: true,
  },
  {
    key: "framed", name: "미니멀 프레임",
    page: { background: "#ffffff", boxShadow: "inset 0 0 0 10px #eaf1fb, inset 0 0 0 12px #1268d3" },
    ink: "#16233b", sub: "#64748b", accent: BLUE,
    band: "#f0f6fe", bandInk: BLUE_DK,
    rowBg: "#f7fafe", rowInk: "#1a2942", rowSub: "#64748b",
    chipBg: "#e8f1fc", chipInk: BLUE_DK, divider: "#e8eef7",
  },
  {
    key: "block", name: "볼드 블록",
    page: { background: "#f0f4f9" },
    ink: "#16233b", sub: "#5d6f88", accent: BLUE,
    band: NAVY, bandInk: "#ffffff",
    rowBg: "#ffffff", rowInk: "#1a2942", rowSub: "#64748b",
    chipBg: "#dfeaf8", chipInk: BLUE_DK, divider: "#e3e9f1",
  },
  {
    key: "sunrise", name: "선라이즈 코럴",
    page: { background: "linear-gradient(160deg, #1268d3 0%, #3f78d6 45%, #ff7e5f 130%)" },
    ink: "#ffffff", sub: "#e9dff5", accent: "#fff0a6",
    band: "rgba(255,255,255,.16)", bandInk: "#ffffff",
    rowBg: "rgba(255,255,255,.12)", rowInk: "#ffffff", rowSub: "#eadff3",
    chipBg: "rgba(255,255,255,.24)", chipInk: "#ffffff", divider: "rgba(255,255,255,.2)",
    logoInvert: true,
  },
];
