import { useEffect, useMemo, useRef, useState } from "react";
import { Download, Image as ImageIcon } from "lucide-react";
import { CARD_BGS } from "../lib/cardBackgrounds";
import { downloadCardPng } from "../lib/share";

const API_BASE = import.meta.env.VITE_API_BASE;
const SITE = "koczip.com";

// ── 금액 포맷(원 → 억 소수1자리 통일: 13.5억·1.5억·0.5억) — 폭이 균일해 우측정렬 깔끔 ──
function eok(won: number | null | undefined): string {
  if (!won) return "-";
  return `${(won / 1e8).toFixed(1)}억`;
}
function pct(v: number | null | undefined, signed = false): string {
  if (v == null) return "-";
  const p = v * 100;
  return `${signed && p > 0 ? "+" : ""}${p.toFixed(1)}%`;
}

// ── 맞춤단지 조건 필터(ComplexFinder 로직 이식) ──
const PY = 3.305785;
const ageOf = (y?: string | null): number | null =>
  (y && y.length >= 4 ? new Date().getFullYear() - Number(y.slice(0, 4)) : null);
const supPyeong = (r: any): number | null => {
  const sa = r.sa ?? (r.ea != null ? r.ea / 0.78 : null);   // 공급면적㎡ (없으면 전용/0.78 환산)
  return sa != null ? sa / PY : null;
};
type FPreset = { label: string; min?: number; max?: number };
const inPreset = (v: number, p: FPreset): boolean =>
  (p.min == null || v >= p.min) && (p.max == null || (p.min != null && p.max <= p.min + 0.5 ? v <= p.max : v < p.max));
type FDim = { key: string; label: string; get: (r: any) => number | null | undefined; presets: FPreset[]; fmt: (mn?: number, mx?: number) => string };
// 인접 프리셋 다중선택 시 하나의 범위로 표기하기 위한 포맷터(예: 세대수 300~700+700~1,500 → 300~1,500)
const nf = (n: number) => n.toLocaleString();
// 공용 프리셋/포맷터 — 맞춤단지·급매 탭이 같은 기준 공유
const P_PY: FPreset[] = [
  { label: "10평대", min: 10, max: 20 }, { label: "20평대", min: 20, max: 30 }, { label: "30평대", min: 30, max: 40 },
  { label: "40평대", min: 40, max: 50 }, { label: "50평대", min: 50, max: 60 }, { label: "60평↑", min: 60 }];
const P_PRICE: FPreset[] = [
  { label: "3억↓", max: 3 }, { label: "3~5억", min: 3, max: 5 }, { label: "5~10억", min: 5, max: 10 },
  { label: "10~15억", min: 10, max: 15 }, { label: "15~25억", min: 15, max: 25 }, { label: "25억↑", min: 25 }];
const P_HH: FPreset[] = [
  { label: "300↓", max: 300 }, { label: "300~700", min: 300, max: 700 },
  { label: "700~1,500", min: 700, max: 1500 }, { label: "1,500↑", min: 1500 }];
const F_PY = (mn?: number, mx?: number) => mx == null ? `${mn}평↑` : mn == null ? `${mx}평↓` : `${mn}~${mx}평`;
const F_EOK = (mn?: number, mx?: number) => mx == null ? `${mn}억↑` : mn == null ? `${mx}억↓` : `${mn}~${mx}억`;
const F_HH = (mn?: number, mx?: number) => mx == null ? `${nf(mn!)}↑` : mn == null ? `${nf(mx)}↓` : `${nf(mn)}~${nf(mx)}`;
const F_PCT = (mn?: number, mx?: number) => mx == null ? `${mn}%↑` : mn == null ? `~${mx}%` : `${mn}~${mx}%`;

const FINDER_DIMS: FDim[] = [
  { key: "py10", label: "평형대", get: (r) => supPyeong(r), presets: P_PY, fmt: F_PY },
  { key: "ask", label: "매매가", get: (r) => (r.ask != null ? r.ask / 1e8 : null), presets: P_PRICE, fmt: F_EOK },
  { key: "age", label: "연식", get: (r) => ageOf(r.y), presets: [
    { label: "5년↓", max: 5 }, { label: "5~10년", min: 5, max: 10 }, { label: "10~20년", min: 10, max: 20 },
    { label: "20~30년", min: 20, max: 30 }, { label: "30년↑", min: 30 }],
    fmt: (mn, mx) => mx == null ? `${mn}년↑` : mn == null ? `${mx}년↓` : `${mn}~${mx}년` },
  { key: "hh", label: "세대수", get: (r) => r.hh, presets: P_HH, fmt: F_HH },
  { key: "jr", label: "전세가율", get: (r) => r.jr, presets: [
    { label: "~50%", max: 50 }, { label: "50~60%", min: 50, max: 60 }, { label: "60~70%", min: 60, max: 70 },
    { label: "70~80%", min: 70, max: 80 }, { label: "80%↑", min: 80 }], fmt: F_PCT },
  { key: "gap", label: "갭", get: (r) => (r.gap != null ? r.gap / 1e8 : null), presets: [
    { label: "1억↓", max: 1 }, { label: "1~3억", min: 1, max: 3 }, { label: "3~5억", min: 3, max: 5 },
    { label: "5~10억", min: 5, max: 10 }, { label: "10억↑", min: 10 }], fmt: F_EOK },
];
// 급매 탭 조건 — 공급면적(area1_m2)·급매호가(asking_min)·세대수(households)·할인율(급매호가 기준)
const QUICK_DIMS: FDim[] = [
  { key: "py10", label: "평형대", get: (r) => (r.area1_m2 != null ? r.area1_m2 / PY : null), presets: P_PY, fmt: F_PY },
  { key: "ask", label: "급매호가", get: (r) => (r.asking_min != null ? r.asking_min / 1e8 : null), presets: P_PRICE, fmt: F_EOK },
  { key: "hh", label: "세대수", get: (r) => r.households, presets: P_HH, fmt: F_HH },
  { key: "disc", label: "할인율", get: (r) => (r.avg_real > 0 && r.asking_min ? (r.avg_real - r.asking_min) / r.avg_real * 100 : null),
    presets: [{ label: "5~10%", min: 5, max: 10 }, { label: "10~15%", min: 10, max: 15 },
      { label: "15~20%", min: 15, max: 20 }, { label: "20%↑", min: 20 }], fmt: F_PCT },
];
const DIMS_BY_SRC: Record<string, FDim[]> = { finder: FINDER_DIMS, quick: QUICK_DIMS };
// 선택된 프리셋들을 인접끼리 병합해 라벨화(1개=원래 라벨, 2개↑ 연속=범위 fmt)
function mergeDimLabels(dim: FDim, indices: number[]): string[] {
  const sorted = [...indices].sort((a, b) => a - b);
  const runs: number[][] = [];
  for (const i of sorted) {
    const last = runs[runs.length - 1];
    if (last && i === last[last.length - 1] + 1) last.push(i);
    else runs.push([i]);
  }
  return runs.map((run) => run.length === 1
    ? dim.presets[run[0]].label
    : dim.fmt(dim.presets[run[0]].min, dim.presets[run[run.length - 1]].max));
}

// ── 데이터 소스 정의 ──
type Col = { key: string; label: string; get: (it: any) => string; strong?: boolean };
type Mode = {
  key: string; label: string; defaultTitle: (region: string) => string;
  url: (p: URLSearchParams) => string;
  rows: (data: any) => any[];
  name: (it: any) => string; sub: (it: any) => string;
  cols: Col[];
  orders?: { key: string; label: string }[];
  trades?: boolean;
  period?: boolean;      // 기간(days) 선택 노출
  regionRank?: boolean;  // 지역 자체를 순위(전국→시도, 시도→시군구, 시군구→동)
};
type Src = Omit<Mode, "period" | "regionRank"> & {
  orderLabel?: string; orderParam?: string; noRegion?: boolean;
  period?: boolean; regionRank?: boolean;
  modes?: Mode[];        // 서브모드(실거래 탭 4종)
};

// dealing_gbn 표기
const dg = (g: string) => (g === "직거래" ? "직거래" : "중개");

const REC_MODES: Mode[] = [
  {
    key: "type_record", label: "타입별 신고가",
    defaultTitle: (r) => `${r} 타입별 신고가 경신 TOP`,
    url: (p) => `${API_BASE}/stats/tx-record-high?${p}`,
    rows: (d) => d.items ?? [],
    name: (it) => it.complex_name, sub: (it) => `${it.region_name} · 전용 ${it.area_key}㎡`,
    trades: true, period: true,
    orders: [{ key: "premium", label: "상승률순" }, { key: "price", label: "가격순" }, { key: "recent", label: "최신순" }],
    cols: [
      { key: "price", label: "신고가", get: (it) => eok(it.record_price), strong: true },
      { key: "premium", label: "상승률", get: (it) => pct(it.premium, true), strong: true },
      { key: "prev", label: "직전가", get: (it) => eok(it.prev_high) },
      { key: "area", label: "전용㎡", get: (it) => `${it.area_key}㎡` },
      { key: "floor", label: "층", get: (it) => (it.floor != null ? `${it.floor}층` : "-") },
      { key: "date", label: "경신일", get: (it) => (it.record_date || "").slice(2).replace(/-/g, ".") },
      { key: "gap", label: "경신간격", get: (it) => (it.months_since != null ? `${it.months_since.toFixed(0)}개월` : "-") },
      { key: "prevdate", label: "직전일", get: (it) => (it.prev_date || "").slice(2).replace(/-/g, ".") },
      { key: "ntotal", label: "거래수", get: (it) => (it.n_total ? `${it.n_total}건` : "-") },
      { key: "hh", label: "세대수", get: (it) => (it.households ? it.households.toLocaleString() : "-") },
    ],
  },
  {
    key: "complex_record", label: "단지별 신고가",
    defaultTitle: (r) => `${r} 단지별 신고가 경신 TOP`,
    url: (p) => `${API_BASE}/stats/tx-record-high?${p}`,
    // 단지×타입 신고가를 단지 단위로 축약 — 단지별 최고 상승률/최고가 1건만.
    rows: (d) => {
      const best = new Map<string, any>();
      for (const it of d.items ?? []) {
        const k = it.complex_no;
        if (!best.has(k) || (it.premium || 0) > (best.get(k).premium || 0)) best.set(k, it);
      }
      return [...best.values()];
    },
    name: (it) => it.complex_name, sub: (it) => it.region_name,
    trades: true, period: true,
    orders: [{ key: "premium", label: "상승률순" }, { key: "price", label: "가격순" }, { key: "recent", label: "최신순" }],
    cols: [
      { key: "price", label: "신고가", get: (it) => eok(it.record_price), strong: true },
      { key: "premium", label: "상승률", get: (it) => pct(it.premium, true), strong: true },
      { key: "prev", label: "직전가", get: (it) => eok(it.prev_high) },
      { key: "area", label: "전용㎡", get: (it) => `${it.area_key}㎡` },
      { key: "floor", label: "층", get: (it) => (it.floor != null ? `${it.floor}층` : "-") },
      { key: "date", label: "경신일", get: (it) => (it.record_date || "").slice(2).replace(/-/g, ".") },
      { key: "hh", label: "세대수", get: (it) => (it.households ? it.households.toLocaleString() : "-") },
    ],
  },
  {
    key: "top_price", label: "지역별 최고거래가",
    defaultTitle: (r) => `${r} 최고 거래가 TOP`,
    url: (p) => `${API_BASE}/stats/tx-top-price?${p}`,
    rows: (d) => d.items ?? [],
    name: (it) => it.complex_name,
    sub: (it) => `${it.region_name} · ${(it.deal_ymd || "").slice(2).replace(/-/g, ".")}`,
    trades: true, period: true,
    cols: [
      { key: "price", label: "거래가", get: (it) => eok(it.price), strong: true },
      { key: "area", label: "전용㎡", get: (it) => (it.excl_use_ar ? `${Math.round(it.excl_use_ar)}㎡` : "-") },
      { key: "floor", label: "층", get: (it) => (it.floor != null ? `${it.floor}층` : "-") },
      { key: "deal", label: "거래유형", get: (it) => dg(it.dealing_gbn) },
      { key: "yr", label: "준공", get: (it) => (it.build_year || "-") },
      { key: "date", label: "거래일", get: (it) => (it.deal_ymd || "").slice(2).replace(/-/g, ".") },
    ],
  },
  {
    key: "region_volume", label: "지역별 거래량순위",
    defaultTitle: (r) => `${r} 거래량 순위`,
    url: (p) => `${API_BASE}/stats/tx-region-volume?${p}`,
    rows: (d) => d.items ?? [],
    name: (it) => it.region_name, sub: () => "",
    trades: true, period: true, regionRank: true,
    cols: [
      { key: "count", label: "거래량", get: (it) => (it.count != null ? `${it.count.toLocaleString()}건` : "-"), strong: true },
    ],
  },
];

const SOURCES: Src[] = [
  {
    key: "record", label: "실거래",
    defaultTitle: (r) => `${r} 실거래`,
    url: (p) => `${API_BASE}/stats/tx-record-high?${p}`,
    rows: (d) => d.items ?? [], name: (it) => it.complex_name, sub: (it) => it.region_name,
    cols: REC_MODES[0].cols, modes: REC_MODES,
  },
  {
    key: "quick", label: "급매",
    defaultTitle: (r) => `${r} 급매 매물 (실거래 대비 할인)`,
    url: (p) => `${API_BASE}/stats/quick-deals?${p}`,
    rows: (d) => d.items ?? [],
    name: (it) => it.complex_name, sub: (it) => it.region_name,
    cols: [
      { key: "asking", label: "급매호가", get: (it) => eok(it.asking_min), strong: true },
      // 할인율 = 카드에 표기되는 급매호가(asking_min) ÷ 실거래평균 기준 → 항상 양수(할인) 일관.
      // (discount_avg는 평균 호가 기준이라 부호가 뒤섞여 -가 붙던 문제 수정)
      { key: "disc", label: "할인율", get: (it) => (it.avg_real > 0 && it.asking_min ? pct((it.avg_real - it.asking_min) / it.avg_real, false) : "-"), strong: true },
      { key: "real", label: "실거래평균", get: (it) => eok(it.avg_real) },
      { key: "askavg", label: "호가평균", get: (it) => eok(it.asking_avg) },
      { key: "askmax", label: "호가최고", get: (it) => eok(it.asking_max) },
      { key: "realmin", label: "실거래최저", get: (it) => eok(it.min_real) },
      { key: "realmax", label: "실거래최고", get: (it) => eok(it.max_real) },
      { key: "area", label: "평형", get: (it) => it.area_name || "-" },
      { key: "excl", label: "전용㎡", get: (it) => (it.avg_excl ? `${Math.round(it.avg_excl)}㎡` : "-") },
      { key: "n", label: "매물수", get: (it) => (it.n_listings ? `${it.n_listings}건` : "-") },
      { key: "nreal", label: "실매물수", get: (it) => (it.n_real ? `${it.n_real}건` : "-") },
      { key: "hh", label: "세대수", get: (it) => (it.households ? it.households.toLocaleString() : "-") },
    ],
  },
  {
    // 강점: 매물 호가 + 실거래가를 함께 보유 → 단지×평형별 괴리율. 경쟁사는 한쪽만.
    key: "gap", label: "호가·실거래 괴리",
    defaultTitle: (r) => `${r} 호가 vs 실거래 괴리 TOP`,
    url: (p) => `${API_BASE}/stats/tx-asking-vs-real?${p}`,
    rows: (d) => d.items ?? [],
    name: (it) => it.complex_name, sub: (it) => `${it.region_name} · 전용 ${it.area_key}㎡`,
    period: true, orderParam: "order", orderLabel: "관점",
    orders: [{ key: "desc", label: "호가 프리미엄(매도우위)" }, { key: "asc", label: "저평가 역전(호가<실거래)" }],
    cols: [
      { key: "gap", label: "괴리율", get: (it) => pct(it.gap_rate, true), strong: true },
      { key: "ask", label: "매물호가", get: (it) => eok(it.avg_asking), strong: true },
      { key: "real", label: "실거래가", get: (it) => eok(it.avg_real) },
      { key: "area", label: "전용㎡", get: (it) => `${it.area_key}㎡` },
      { key: "nask", label: "매물수", get: (it) => (it.n_asking ? `${it.n_asking}건` : "-") },
      { key: "nreal", label: "실거래수", get: (it) => (it.n_real ? `${it.n_real}건` : "-") },
    ],
  },
  {
    // 강점: 단지×평형 롤업으로 평당 실거래가 정확 산출.
    key: "pyeong", label: "평당가 순위",
    defaultTitle: (r) => `${r} 평당가 순위`,
    url: (p) => `${API_BASE}/stats/tx-pyeong-price?${p}`,
    rows: (d) => d.items ?? [],
    name: (it) => it.complex_name, sub: (it) => it.region_name,
    period: true, orderParam: "order", orderLabel: "정렬",
    orders: [{ key: "desc", label: "비싼 순" }, { key: "asc", label: "싼 순" }],
    cols: [
      { key: "py", label: "평당가", get: (it) => eok(it.pyeong_price), strong: true },
      { key: "avg", label: "평균거래가", get: (it) => eok(it.avg_price), strong: true },
      { key: "area", label: "전용㎡", get: (it) => `${it.area_key}㎡` },
      { key: "n", label: "거래수", get: (it) => (it.n ? `${it.n}건` : "-") },
    ],
  },
  {
    key: "realtor", label: "중개사 랭킹",
    defaultTitle: () => `전국 중개사무소 매물 보유 TOP`,
    url: (p) => `${API_BASE}/stats/realtors/national?${p}`,
    rows: (d) => d.items ?? [],
    name: (it) => it.realtor_name, sub: (it) => it.sido || "",
    noRegion: true, orderLabel: "매물 범위", orderParam: "scope",
    orders: [
      { key: "complex", label: "단지형" }, { key: "all", label: "전체매물" },
      { key: "house", label: "주거(빌라·단독)" }, { key: "comm", label: "상가·사무실" }],
    cols: [
      { key: "count", label: "매물수", get: (it) => (it.count != null ? `${it.count.toLocaleString()}건` : "-"), strong: true },
      { key: "total", label: "전체매물", get: (it) => (it.total_count != null ? `${it.total_count.toLocaleString()}건` : "-"), strong: true },
      { key: "staff", label: "직원수", get: (it) => (it.staff_count != null ? `${it.staff_count}명` : "-") },
      { key: "est", label: "업력", get: (it) => (it.established_year ? `${new Date().getFullYear() - +it.established_year}년` : "-") },
      { key: "estyr", label: "개업연도", get: (it) => it.established_year || "-" },
      { key: "sido", label: "지역", get: (it) => it.sido || "-" },
    ],
  },
  {
    key: "finder", label: "맞춤단지",
    defaultTitle: (r) => `${r} 추천 단지`,
    url: (p) => `${API_BASE}/stats/complex-finder?${p}`,
    // 최근실거래(la) 있는 단지만(카드에 "-" 빈칸 방지 — 실거래 이력 없는 단지 제외) → 실거래가 높은 순.
    rows: (d) => (d.rows ?? []).filter((r: any) => r.la).sort((a: any, b: any) => (b.la || 0) - (a.la || 0)),
    name: (it) => it.n, sub: (it) => it.d || "",
    // 맞춤단지 표에서 사용자가 보는 전 컬럼(단지명·동은 행 제목이라 제외).
    cols: [
      { key: "ask", label: "매매최저", get: (it) => eok(it.ask), strong: true },
      { key: "la", label: "최근실거래", get: (it) => eok(it.la), strong: true },
      { key: "pk", label: "신고가", get: (it) => eok(it.pk) },
      { key: "js", label: "전세최저", get: (it) => eok(it.js) },
      { key: "gap", label: "갭", get: (it) => eok(it.gap) },
      { key: "jr", label: "전세가율", get: (it) => (it.jr != null ? `${it.jr}%` : "-") },
      { key: "vp", label: "전고점比", get: (it) => (it.vp != null ? `${it.vp > 0 ? "+" : ""}${it.vp}%` : "-") },
      { key: "n12", label: "12개월거래", get: (it) => (it.n12 ? `${it.n12}건` : "-") },
      { key: "py", label: "평형", get: (it) => (it.py ? `${it.py}평` : "-") },
      { key: "ea", label: "전용㎡", get: (it) => (it.ea != null ? `${it.ea}㎡` : "-") },
      { key: "hh", label: "세대수", get: (it) => (it.hh ? it.hh.toLocaleString() : "-") },
      { key: "ah", label: "평형세대", get: (it) => (it.ah != null ? `${it.ah}세대` : "-") },
      { key: "age", label: "연식", get: (it) => (it.y ? `${new Date().getFullYear() - +String(it.y).slice(0, 4)}년` : "-") },
      { key: "rc", label: "방/욕실", get: (it) => (it.rc != null ? `${it.rc}/${it.bc ?? "-"}` : "-") },
      { key: "et", label: "현관", get: (it) => it.et || "-" },
      { key: "an", label: "매물", get: (it) => (it.an > 0 ? `${it.an}/${it.au}` : "-") },
      { key: "sw", label: "지하철", get: (it) => (it.sw ? `${it.swm}분` : "-") },
      { key: "sc", label: "배정초", get: (it) => (it.scm != null ? `${it.scm}분` : "-") },
    ],
  },
  {
    // 단지 1곳의 일자별 매물수·실매물·호가 추이 차트 카드(리스트가 아닌 차트 본문)
    key: "cxlisting", label: "단지매물분석",
    defaultTitle: () => "단지 매물 분석",
    url: () => "", rows: () => [], name: () => "", sub: () => "",
    cols: [], noRegion: true, trades: true,
  },
];

type Sido = { code: string; name: string };

const PERIODS: [number, string][] = [[7, "7일"], [30, "30일"], [90, "90일"], [180, "180일"], [365, "1년"], [3650, "전체"]];

export default function CardNews() {
  const [srcKey, setSrcKey] = useState("record");
  const src = SOURCES.find((s) => s.key === srcKey)!;
  const [subMode, setSubMode] = useState("type_record");
  // 실거래 탭은 서브모드가 실제 설정. 그 외 소스는 src 자체.
  const eff: Mode & { orderParam?: string; noRegion?: boolean } = src.modes
    ? { ...(src as any), ...(src.modes.find((m) => m.key === subMode) || src.modes[0]) }
    : (src as any);
  const [bg, setBg] = useState(0);
  const [ratio, setRatio] = useState<"4:5" | "1:1">("4:5");
  const [sido, setSido] = useState("1100000000");
  const [sigungu, setSigungu] = useState("");
  const [dong, setDong] = useState("");
  const [trade, setTrade] = useState("A1");
  const [order, setOrder] = useState("premium");
  const [days, setDays] = useState(90);
  const [selCols, setSelCols] = useState<string[]>(["price", "premium", "area"]);
  const [finderSel, setFinderSel] = useState<Record<string, number[]>>({});  // 맞춤단지 조건(dim→프리셋 인덱스[])
  const [title, setTitle] = useState("");
  const [nRows, setNRows] = useState(10);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  // ── 단지매물분석 전용 상태 ──
  const [cxQuery, setCxQuery] = useState("");
  const [cxResults, setCxResults] = useState<any[]>([]);
  const [cxSel, setCxSel] = useState<any>(null);
  const [cxDays, setCxDays] = useState(31);
  const [cxArea, setCxArea] = useState("");
  const [cxMetrics, setCxMetrics] = useState<string[]>(["n", "u", "price"]);

  const [sidos, setSidos] = useState<Sido[]>([]);
  const [sggs, setSggs] = useState<Sido[]>([]);
  const [dongs, setDongs] = useState<Sido[]>([]);
  useEffect(() => {
    fetch(`${API_BASE}/stats/changes/sido-list`).then((r) => r.json())
      .then((j) => setSidos(j.items ?? [])).catch(() => {});
  }, []);
  useEffect(() => {
    if (!sido) { setSggs([]); return; }
    fetch(`${API_BASE}/stats/sigungu-list?sido=${sido.slice(0, 2)}`).then((r) => r.json())
      .then((j) => setSggs(j.items ?? [])).catch(() => {});
  }, [sido]);
  useEffect(() => {
    if (!sigungu) { setDongs([]); return; }
    fetch(`${API_BASE}/stats/dong-list?sigungu=${sigungu.slice(0, 5)}`).then((r) => r.json())
      .then((j) => setDongs(j.items ?? [])).catch(() => {});
  }, [sigungu]);

  // 단지 검색(디바운스) — 선택된 이름 그대로면 재검색 안 함
  useEffect(() => {
    if (srcKey !== "cxlisting") return;
    const q = cxQuery.trim();
    if (q.length < 2 || (cxSel && q === cxSel.complex_name)) { setCxResults([]); return; }
    const tm = setTimeout(() => {
      fetch(`${API_BASE}/complexes/search?q=${encodeURIComponent(q)}`)
        .then((r) => r.json()).then((j) => setCxResults(j.items ?? [])).catch(() => {});
    }, 250);
    return () => clearTimeout(tm);
  }, [cxQuery, srcKey]); // eslint-disable-line

  // 소스·서브모드 바뀌면 컬럼·정렬·기간 기본값 리셋 + 이전 데이터 클리어(형식 불일치 렌더 방지)
  useEffect(() => {
    setSelCols(eff.cols.slice(0, 3).map((c) => c.key));
    if (eff.orders) setOrder(eff.orders[0].key);
    // 신고가는 전체기간(역대 신고가), 최고거래가·거래량은 최근 90일 기본
    const isRec = eff.key === "type_record" || eff.key === "complex_record";
    setDays(isRec ? 3650 : 90);
    setTitle(""); setData(null); setFinderSel({});
  }, [srcKey, subMode]); // eslint-disable-line

  const regionName = useMemo(() => {
    if (dong) return dongs.find((s) => s.code === dong)?.name ?? "";
    if (sigungu) return sggs.find((s) => s.code === sigungu)?.name ?? "";
    return sidos.find((s) => s.code === sido)?.name ?? "전국";
  }, [sido, sigungu, dong, sidos, sggs, dongs]);

  // ── 데이터 로드 ──
  const reqRef = useRef(0);   // stale 응답 가드 — 느린 이전 요청이 최신 데이터를 덮어쓰지 않게
  const load = () => {
    if (srcKey === "cxlisting") {
      if (!cxSel) { setData(null); setLoading(false); return; }
      setLoading(true);
      const myId = ++reqRef.current;
      fetch(`${API_BASE}/complex/${cxSel.complex_no}/listing-daily?days=${cxDays}`)
        .then((r) => r.json()).then((j) => { if (myId === reqRef.current) setData(j); })
        .catch(() => { if (myId === reqRef.current) setData(null); })
        .finally(() => { if (myId === reqRef.current) setLoading(false); });
      return;
    }
    const p = new URLSearchParams();
    if (srcKey === "finder") {
      // 맞춤단지는 시군구 단위 — 시군구 미선택 시 서울 전체(대용량) fetch 방지 + 안내
      if (!sigungu) { setData(null); setLoading(false); return; }
      p.set("sigungu", sigungu.slice(0, 5)); p.set("asset", "apt");
    } else if (eff.regionRank) {
      // 지역 순위 — 선택 지역의 하위를 랭킹(전국→시도, 시도→시군구, 시군구→동)
      if (sigungu) { p.set("level", "dong"); p.set("parent", sigungu.slice(0, 5)); }
      else if (sido) { p.set("level", "sigungu"); p.set("parent", sido.slice(0, 2)); }
      else p.set("level", "sido");
      if (eff.trades) p.set("trade", trade);
      p.set("days", String(days)); p.set("limit", "30");
    } else {
      if (!eff.noRegion) {
        if (dong) p.set("dong", dong.slice(0, 10));
        else if (sigungu) p.set("sigungu", sigungu.slice(0, 5));
        else if (sido) p.set("sido", sido.slice(0, 2));
      }
      if (eff.trades) p.set("trade", trade);
      if (eff.orders) p.set(src.orderParam || "order", order);
      if (eff.period) p.set("days", String(days));
      p.set("limit", eff.noRegion ? "80" : "60");
    }
    setLoading(true);
    const myId = ++reqRef.current;
    fetch(eff.url(p)).then((r) => r.json())
      .then((j) => { if (myId === reqRef.current) setData(j); })
      .catch(() => { if (myId === reqRef.current) setData(null); })
      .finally(() => { if (myId === reqRef.current) setLoading(false); });
  };
  useEffect(load, [srcKey, subMode, sido, sigungu, dong, trade, order, days, cxSel, cxDays]); // eslint-disable-line

  const rows = useMemo(() => {
    if (!data) return [];
    let rs = eff.rows(data);
    for (const dim of (DIMS_BY_SRC[srcKey] ?? [])) {   // 조건(AND) — 같은 조건 내 다중선택은 OR
      const picked = finderSel[dim.key];
      if (!picked || !picked.length) continue;
      rs = rs.filter((r: any) => {
        const v = dim.get(r);
        return v != null && picked.some((i) => inPreset(v as number, dim.presets[i]));
      });
    }
    if (srcKey === "finder") {
      // 동일 단지 내 유사평형(84A·84B 등 전용㎡ 근사)은 하나만 — 정렬(la/ask 내림차순) 첫 행=대표(최고가) 유지
      const seen = new Set<string>();
      rs = rs.filter((r: any) => {
        const areaK = r.ea != null ? Math.round(r.ea) : (supPyeong(r) != null ? Math.round(supPyeong(r) as number) : r.py);
        const k = `${r.c ?? r.n}|${areaK}`;
        if (seen.has(k)) return false;
        seen.add(k); return true;
      });
    }
    return rs.slice(0, nRows);
  }, [data, nRows, eff, srcKey, finderSel]);
  // 단지매물분석: 일자별 집계(면적 필터·매물수 가중평균 호가 — 상세페이지와 동일 산식)
  const cxSeries = useMemo(() => {
    if (srcKey !== "cxlisting" || !data?.rows) return [];
    const byDay = new Map<string, any>();
    for (const r of data.rows as any[]) {
      if (r.t !== trade) continue;
      if (cxArea && r.area !== cxArea) continue;
      const e = byDay.get(r.d) ?? { n: 0, u: 0, uSeen: false, ps: 0, pw: 0 };
      e.n += r.n;
      if (r.u != null) { e.u += r.u; e.uSeen = true; }
      const price = trade === "B2" ? r.ravg : r.avg;
      if (price != null && r.n > 0) { e.ps += price * r.n; e.pw += r.n; }
      byDay.set(r.d, e);
    }
    return [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b))
      .map(([d, e]) => ({ d, label: `${parseInt(d.slice(5, 7), 10)}.${d.slice(8, 10)}`,
        n: e.n, u: e.uSeen ? e.u : null, price: e.pw > 0 ? e.ps / e.pw : null }));
  }, [srcKey, data, trade, cxArea]);
  const cxAreas = useMemo(() => (srcKey !== "cxlisting" || !data?.rows) ? [] :
    Array.from(new Set((data.rows as any[]).filter((r) => r.t === trade).map((r) => r.area)))
      .sort((x: any, y: any) => (parseFloat(x) || 9e9) - (parseFloat(y) || 9e9) || String(x).localeCompare(String(y))),
    [srcKey, data, trade]);
  const cxPriceLabel = trade === "A1" ? "평균 매매호가" : trade === "B1" ? "평균 전세호가" : "평균 월세";
  const cxFmtPrice = (v: number) => (trade === "B2" ? `${Math.round(v / 1e4).toLocaleString()}만` : eok(v));

  const activeDims = DIMS_BY_SRC[srcKey] ?? [];
  const finderCond = activeDims
    .flatMap((dim) => { const idx = finderSel[dim.key] || []; return idx.length ? mergeDimLabels(dim, idx) : []; }).join(" · ");
  const cols = eff.cols.filter((c) => selCols.includes(c.key));
  const effRegion = eff.noRegion ? "전국" : regionName;
  const cardTitle = srcKey === "cxlisting"
    ? (title || (cxSel ? `${cxSel.complex_name} 매물·호가 추이` : "단지 매물 분석"))
    : title
    || (finderCond ? `${effRegion} ${finderCond} ${srcKey === "quick" ? "급매" : "아파트"}` : eff.defaultTitle(effRegion));
  const orderName = eff.orders?.find((o) => o.key === order)?.label ?? "";
  const periodLabel = days >= 3650 ? "전체 기간" : `최근 ${PERIODS.find((x) => x[0] === days)?.[1] ?? days + "일"}`;
  const subtitle = srcKey === "cxlisting" ? [
    cxSel?.region,
    ({ A1: "매매", B1: "전세", B2: "월세" } as any)[trade],
    cxArea ? `${cxArea}㎡` : "전체 면적",
    `최근 ${cxDays === 14 ? "2주" : cxDays === 31 ? "1달" : "2달"} 일자별`,
  ].filter(Boolean).join(" · ") : [
    effRegion,
    eff.trades ? ({ A1: "매매", B1: "전세", B2: "월세" } as any)[trade] : "",
    (eff.noRegion || eff.key === "gap") && orderName ? orderName : "",
    eff.period ? periodLabel : "",
  ].filter(Boolean).join(" · ");
  const t = CARD_BGS[bg];
  const W = 1080, H = ratio === "4:5" ? 1350 : 1080;
  const previewW = 380, scale = previewW / W;

  const toggleCol = (k: string) =>
    setSelCols((s) => (s.includes(k) ? s.filter((x) => x !== k) : [...s, k].slice(0, 4)));

  const dl = async () => {
    if (!cardRef.current) return;
    await downloadCardPng(cardRef.current, `콕집_${eff.label}_${srcKey === "cxlisting" ? (cxSel?.complex_name ?? "단지") : effRegion}_${ratio}`);
  };

  return (
    <div>
      <div className="section-title" style={{ marginTop: 4 }}>
        <ImageIcon size={16} strokeWidth={2.2} /> 카드뉴스 생성 <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>인스타그램용 · 관리자</span>
      </div>

      <div className="cn-wrap">
        {/* ── 컨트롤 ── */}
        <div className="cn-controls">
          <div className="cn-grp">
            <label>데이터</label>
            <div className="cn-seg">
              {SOURCES.map((s) => (
                <button key={s.key} className={srcKey === s.key ? "on" : ""} onClick={() => setSrcKey(s.key)}>{s.label}</button>
              ))}
            </div>
          </div>

          {src.modes && (
            <div className="cn-grp"><label>실거래 종류</label>
              <div className="cn-cols">
                {src.modes.map((m) => (
                  <button key={m.key} className={subMode === m.key ? "on" : ""} onClick={() => setSubMode(m.key)}>{m.label}</button>
                ))}
              </div>
            </div>
          )}

          {srcKey === "cxlisting" && (
            <>
              <div className="cn-grp">
                <label>단지 검색</label>
                <input value={cxQuery} onChange={(e) => setCxQuery(e.target.value)} placeholder="단지명 입력 (2자 이상)" />
                {cxResults.length > 0 && (
                  <div className="cn-cols" style={{ marginTop: 4 }}>
                    {cxResults.slice(0, 8).map((c: any) => (
                      <button key={c.complex_no} onClick={() => { setCxSel(c); setCxQuery(c.complex_name); setCxResults([]); setCxArea(""); }}>
                        {c.complex_name} <span style={{ color: "#8a97a8" }}>{(c.region || "").split(" ").slice(-1)[0]}{c.households ? ` · ${c.households}세대` : ""}</span>
                      </button>
                    ))}
                  </div>
                )}
                {cxSel && <div style={{ fontSize: 12, color: "#5a6b80" }}>선택: <b>{cxSel.complex_name}</b> · {cxSel.region}</div>}
              </div>
              <div className="cn-grp"><label>기간</label>
                <div className="cn-seg">
                  {([[14, "2주"], [31, "1달"], [62, "2달"]] as const).map(([d, l]) => (
                    <button key={d} className={cxDays === d ? "on" : ""} onClick={() => setCxDays(d)}>{l}</button>))}
                </div>
              </div>
              {cxAreas.length > 1 && (
                <div className="cn-grp"><label>면적</label>
                  <div className="cn-cols">
                    <button className={cxArea === "" ? "on" : ""} onClick={() => setCxArea("")}>전체</button>
                    {cxAreas.map((a: any) => (
                      <button key={a} className={cxArea === a ? "on" : ""} onClick={() => setCxArea(a)}>{a}㎡</button>))}
                  </div>
                </div>
              )}
              <div className="cn-grp"><label>표시 지표</label>
                <div className="cn-cols">
                  {([["n", "광고매물수"], ["u", "실매물수"], ["price", "평균호가"]] as const).map(([k, l]) => (
                    <button key={k} className={cxMetrics.includes(k) ? "on" : ""}
                      onClick={() => setCxMetrics((m) => m.includes(k) ? (m.length > 1 ? m.filter((x) => x !== k) : m) : [...m, k])}>{l}</button>))}
                </div>
              </div>
            </>
          )}

          {!eff.noRegion && (
            <div className="cn-grp">
              <label>지역 {eff.regionRank && <span className="muted">(선택 지역의 하위를 순위)</span>}</label>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <select value={sido} onChange={(e) => { setSido(e.target.value); setSigungu(""); setDong(""); }}>
                  <option value="">전국</option>
                  {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
                </select>
                <select value={sigungu} onChange={(e) => { setSigungu(e.target.value); setDong(""); }} disabled={!sido}>
                  <option value="">시 전체</option>
                  {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
                </select>
                {!eff.regionRank && (
                  <select value={dong} onChange={(e) => setDong(e.target.value)} disabled={!sigungu}>
                    <option value="">동 전체</option>
                    {dongs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
                  </select>
                )}
              </div>
            </div>
          )}

          {activeDims.length > 0 && (
            <div className="cn-grp">
              <label>조건 <span className="muted">(같은 줄 다중선택=OR · 줄 사이=AND)</span></label>
              {activeDims.map((dim) => (
                <div key={dim.key} style={{ display: "flex", alignItems: "flex-start", gap: 6, marginBottom: 5 }}>
                  <span style={{ fontSize: 11.5, color: "#64748b", width: 50, flexShrink: 0, paddingTop: 6 }}>{dim.label}</span>
                  <div className="cn-cols" style={{ flex: 1 }}>
                    {dim.presets.map((p, i) => {
                      const on = (finderSel[dim.key] || []).includes(i);
                      return (
                        <button key={i} className={on ? "on" : ""} onClick={() =>
                          setFinderSel((s) => {
                            const cur = s[dim.key] || [];
                            return { ...s, [dim.key]: cur.includes(i) ? cur.filter((x) => x !== i) : [...cur, i] };
                          })}>{p.label}</button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {eff.trades && (
            <div className="cn-grp"><label>거래유형</label>
              <div className="cn-seg">
                {[["A1", "매매"], ["B1", "전세"], ["B2", "월세"]].map(([k, l]) => (
                  <button key={k} className={trade === k ? "on" : ""} onClick={() => setTrade(k)}>{l}</button>))}
              </div>
            </div>
          )}
          {eff.period && (
            <div className="cn-grp"><label>기간 <span className="muted">{eff.regionRank || eff.key === "top_price" ? "(거래 집계 기간)" : "(신고가 경신 기간)"}</span></label>
              <div className="cn-seg">
                {PERIODS.map(([d, l]) => (
                  <button key={d} className={days === d ? "on" : ""} onClick={() => setDays(d)}>{l}</button>))}
              </div>
            </div>
          )}
          {eff.orders && (
            <div className="cn-grp"><label>{(eff as any).orderLabel || "정렬"}</label>
              <div className="cn-seg">
                {eff.orders.map((o) => <button key={o.key} className={order === o.key ? "on" : ""} onClick={() => setOrder(o.key)}>{o.label}</button>)}
              </div>
            </div>
          )}

          {eff.cols.length > 0 && (
          <div className="cn-grp">
            <label>표시 컬럼 <span className="muted">(최대 4)</span></label>
            <div className="cn-cols">
              {eff.cols.map((c) => (
                <button key={c.key} className={selCols.includes(c.key) ? "on" : ""} onClick={() => toggleCol(c.key)}>{c.label}</button>
              ))}
            </div>
          </div>
          )}

          <div className="cn-grp">
            <label>제목</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder={eff.defaultTitle(effRegion)} />
          </div>

          <div className="cn-grp">
            <label>행 수 · 비율</label>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {srcKey !== "cxlisting" && (
              <select value={nRows} onChange={(e) => setNRows(+e.target.value)}>
                {[5, 6, 7, 8, 10, 12].map((n) => <option key={n} value={n}>{n}행</option>)}
              </select>
              )}
              <div className="cn-seg">
                <button className={ratio === "4:5" ? "on" : ""} onClick={() => setRatio("4:5")}>4:5</button>
                <button className={ratio === "1:1" ? "on" : ""} onClick={() => setRatio("1:1")}>1:1</button>
              </div>
            </div>
          </div>

          <div className="cn-grp">
            <label>배경 <span className="muted">({t.name})</span></label>
            <div className="cn-bgs">
              {CARD_BGS.map((b, i) => (
                <button key={b.key} title={b.name} onClick={() => setBg(i)}
                  className={`cn-bg-th${bg === i ? " on" : ""}`} style={b.page} />
              ))}
            </div>
          </div>

          <button className="cn-dl" onClick={dl}><Download size={16} /> PNG 다운로드 ({W}×{H})</button>
        </div>

        {/* ── 미리보기 ── */}
        <div className="cn-preview">
          <div style={{ width: previewW, height: H * scale, position: "relative", overflow: "hidden" }}>
            <div style={{ transformOrigin: "top left", transform: `scale(${scale})` }}>
              <Card innerRef={cardRef} W={W} H={H} t={t} title={cardTitle} subtitle={subtitle}
                rows={rows} cols={cols} nameOf={src.name} subOf={src.sub} loading={loading}
                chartBody={srcKey === "cxlisting" ? (
                  !cxSel ? <div style={{ color: t.sub, fontSize: 26, marginTop: 40 }}>단지를 검색해 선택하세요.</div>
                  : loading ? <div style={{ color: t.sub, fontSize: 26, marginTop: 40 }}>불러오는 중…</div>
                  : cxSeries.length === 0 ? <div style={{ color: t.sub, fontSize: 26, marginTop: 40 }}>이 조건의 매물 데이터가 없습니다.</div>
                  : <CxChartBody series={cxSeries} metrics={cxMetrics} priceLabel={cxPriceLabel} fmtPrice={cxFmtPrice} />
                ) : undefined}
                emptyMsg={srcKey === "finder" && !sigungu ? "시·군·구를 선택하세요." : "데이터가 없습니다. 조건을 바꿔보세요."} />
            </div>
          </div>
        </div>
      </div>
      <style>{cardCss}</style>
    </div>
  );
}

// ── 카드 렌더 ──
const Card = ({ innerRef, W, H, t, title, subtitle, rows, cols, nameOf, subOf, loading, emptyMsg, chartBody }: any) => {
  const pad = 64, rowGap = 12;
  // 헤더+제목띠+푸터+여백(~460)을 뺀 나머지에 행을 균등 배치. 푸터 잘림 방지.
  const listAvail = H - 460;
  const n = Math.max(rows.length, 1);
  const rowH = Math.max(52, Math.min(92, (listAvail - (n - 1) * rowGap) / n));
  return (
    <div ref={innerRef} style={{ width: W, height: H, ...t.page, position: "relative", fontFamily: "Pretendard, sans-serif", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, padding: pad, display: "flex", flexDirection: "column" }}>
        {/* 헤더: 콕집 + 주소 */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
            {/* 기존 콕집 로고(파란 집+흰 체크) — html2canvas 안정성 위해 인라인 SVG.
                어두운 배경(logoInvert)엔 흰 pill로 가독성 확보. */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
              width: 52, height: 52, borderRadius: 13, background: t.logoInvert ? "#ffffff" : "transparent" }}>
              <svg width={t.logoInvert ? 40 : 50} height={t.logoInvert ? 40 : 50} viewBox="0 0 100 100">
                <path d="M 50 10 L 92 46 L 92 92 L 8 92 L 8 46 Z" fill="#1268d3" />
                <path d="M 28 58 L 44 73 L 74 42" stroke="#ffffff" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" fill="none" />
              </svg>
            </div>
            <span style={{ fontWeight: 800, fontSize: 32, color: t.ink }}>콕집</span>
          </div>
          <span style={{ fontSize: 24, fontWeight: 700, color: t.accent }}>{SITE}</span>
        </div>

        {/* 제목 띠 */}
        <div style={{ marginTop: 34, background: t.band, borderRadius: 20, padding: "26px 30px" }}>
          <div style={{ fontSize: 46, fontWeight: 900, lineHeight: 1.18, color: t.bandInk, letterSpacing: "-0.5px" }}>{title}</div>
          <div style={{ fontSize: 24, fontWeight: 600, color: t.bandInk, opacity: 0.82, marginTop: 8 }}>{subtitle}</div>
        </div>

        {/* 본문: 차트(단지매물분석) 또는 행 리스트 */}
        {chartBody ? (
          <div style={{ marginTop: 26, flex: 1, minHeight: 0, display: "flex", flexDirection: "column", justifyContent: "center" }}>
            {chartBody}
          </div>
        ) : (
        <div style={{ marginTop: 26, display: "flex", flexDirection: "column", gap: rowGap }}>
          {loading && <div style={{ color: t.sub, fontSize: 26, marginTop: 40 }}>불러오는 중…</div>}
          {!loading && rows.length === 0 && <div style={{ color: t.sub, fontSize: 26, marginTop: 40 }}>{emptyMsg}</div>}
          {rows.map((it: any, i: number) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 18, background: t.rowBg,
              borderRadius: 16, padding: `0 24px`, height: rowH, minHeight: 64 }}>
              <div style={{ width: 46, height: 46, borderRadius: 12, background: t.chipBg, color: t.chipInk,
                display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 900, fontSize: 26, flexShrink: 0 }}>{i + 1}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 30, fontWeight: 800, color: t.rowInk, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{nameOf(it)}</div>
                <div style={{ fontSize: 20, color: t.rowSub, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{subOf(it)}</div>
              </div>
              <div style={{ display: "flex", gap: 20, flexShrink: 0 }}>
                {cols.map((c: Col) => (
                  <div key={c.key} style={{ textAlign: "right", width: 112 }}>
                    <div style={{ fontSize: 17, color: t.rowSub, fontWeight: 600 }}>{c.label}</div>
                    <div style={{ fontSize: c.strong ? 29 : 25, fontWeight: c.strong ? 900 : 700,
                      color: c.strong ? t.accent : t.rowInk, whiteSpace: "nowrap",
                      fontVariantNumeric: "tabular-nums" }}>{c.get(it)}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        )}

        {/* 푸터 — marginTop auto로 카드 하단 고정 */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "auto", paddingTop: 18,
          borderTop: `2px solid ${t.divider}` }}>
          <span style={{ fontSize: 21, fontWeight: 700, color: t.ink }}>콕집 <span style={{ color: t.sub, fontWeight: 500 }}>· 부동산 매물·실거래·중개사 분석</span></span>
          <span style={{ fontSize: 21, fontWeight: 800, color: t.accent }}>{SITE}</span>
        </div>
      </div>
    </div>
  );
};

// ── 단지매물분석 차트 본문(카드 내부) ──
// html2canvas 캡처 안정성을 위해 recharts 대신 수제 SVG. 흰 패널 위에 그려 10종 배경 모두 가독.
const CxChartBody = ({ series, metrics, priceLabel, fmtPrice }: any) => {
  const has = (k: string) => metrics.includes(k);
  const first = series[0], last = series[series.length - 1];
  const ink = "#24344d", sub = "#7a8aa0", light = "#a8c6ec", dark = "#1268d3", red = "#e2574c";

  // 상단 요약 스탯
  const stats: { l: string; v: string; d: string | null; up: boolean | null }[] = [];
  if (has("n")) stats.push({ l: "현재 광고", v: `${last.n.toLocaleString()}건`,
    d: last.n !== first.n ? `${last.n > first.n ? "+" : ""}${(last.n - first.n).toLocaleString()}건` : "보합",
    up: last.n === first.n ? null : last.n > first.n });
  if (has("u") && last.u != null) stats.push({ l: "실매물(중복 합침)", v: `${last.u.toLocaleString()}건`,
    d: first.u != null && last.u !== first.u ? `${last.u > first.u ? "+" : ""}${(last.u - first.u).toLocaleString()}건` : (first.u != null ? "보합" : null),
    up: first.u == null || last.u === first.u ? null : last.u > first.u });
  if (has("price") && last.price != null) {
    const dp = first.price ? ((last.price - first.price) / first.price) * 100 : null;
    stats.push({ l: priceLabel, v: fmtPrice(last.price),
      d: dp != null && Math.abs(dp) >= 0.05 ? `${dp > 0 ? "+" : ""}${dp.toFixed(1)}%` : "보합",
      up: dp == null || Math.abs(dp) < 0.05 ? null : dp > 0 });
  }

  // SVG 좌표계
  const SW = 904, SH = 470;
  const padL = has("n") || has("u") ? 64 : 16;
  const padR = has("price") ? 92 : 16;
  const padT = 14, padB = 44;
  const plotW = SW - padL - padR, plotH = SH - padT - padB;
  const maxN = Math.max(1, ...series.map((s: any) =>
    Math.max(has("n") ? s.n : 0, has("u") ? (s.u ?? 0) : 0)));
  const prices = series.map((s: any) => s.price).filter((v: any) => v != null);
  const pMin0 = Math.min(...prices), pMax0 = Math.max(...prices);
  const pPad = Math.max((pMax0 - pMin0) * 0.18, pMax0 * 0.004 || 1);
  const pMin = pMin0 - pPad, pMax = pMax0 + pPad;
  const cx = (i: number) => padL + (plotW / series.length) * (i + 0.5);
  const bw = Math.max(3, Math.min(16, (plotW / series.length) * 0.34));
  const yN = (v: number) => padT + plotH * (1 - v / maxN);
  const yP = (v: number) => padT + plotH * (1 - (v - pMin) / (pMax - pMin));
  const xStep = Math.max(1, Math.ceil(series.length / 8));
  const nTicks = [0, 0.5, 1].map((f) => Math.round(maxN * f));
  const pTicks = prices.length ? [0.12, 0.5, 0.88].map((f) => pMin + (pMax - pMin) * f) : [];
  const linePts = series.map((s: any, i: number) => (s.price != null ? `${cx(i)},${yP(s.price)}` : null))
    .filter(Boolean).join(" ");
  const twoBars = has("n") && has("u");

  const legend = [
    has("n") && { c: light, l: "광고매물" },
    has("u") && { c: dark, l: "실매물(중복 합침)" },
    has("price") && { c: red, l: priceLabel },
  ].filter(Boolean) as { c: string; l: string }[];

  return (
    <div style={{ background: "rgba(255,255,255,.94)", borderRadius: 20, padding: "24px 24px 18px" }}>
      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        {stats.map((st, i) => (
          <div key={i} style={{ flex: 1, background: "#f2f6fb", borderRadius: 14, padding: "14px 18px" }}>
            <div style={{ fontSize: 19, fontWeight: 600, color: sub }}>{st.l}</div>
            <div style={{ fontSize: 34, fontWeight: 900, color: ink, fontVariantNumeric: "tabular-nums" }}>{st.v}</div>
            {st.d && <div style={{ fontSize: 20, fontWeight: 800,
              color: st.up == null ? sub : st.up ? "#d23b3b" : "#1a6fd4" }}>{st.d} <span style={{ color: sub, fontWeight: 500, fontSize: 17 }}>기간 내</span></div>}
          </div>
        ))}
      </div>
      <svg width={SW} height={SH} viewBox={`0 0 ${SW} ${SH}`}>
        {nTicks.map((v, i) => (
          <g key={`n${i}`}>
            <line x1={padL} x2={SW - padR} y1={yN(v)} y2={yN(v)} stroke="#e5ebf3" strokeWidth={i === 0 ? 2 : 1} />
            {(has("n") || has("u")) && <text x={padL - 10} y={yN(v) + 6} textAnchor="end" fontSize={17} fill={sub}>{v.toLocaleString()}</text>}
          </g>
        ))}
        {series.map((sr: any, i: number) => (
          <g key={sr.d}>
            {has("n") && <rect x={twoBars ? cx(i) - bw : cx(i) - bw / 2} y={yN(sr.n)} width={bw}
              height={Math.max(0, yN(0) - yN(sr.n))} fill={light} rx={2} />}
            {has("u") && sr.u != null && <rect x={twoBars ? cx(i) : cx(i) - bw / 2} y={yN(sr.u)} width={bw}
              height={Math.max(0, yN(0) - yN(sr.u))} fill={dark} rx={2} />}
            {i % xStep === 0 && <text x={cx(i)} y={SH - padB + 26} textAnchor="middle" fontSize={17} fill={sub}>{sr.label}</text>}
          </g>
        ))}
        {has("price") && prices.length > 0 && (
          <g>
            {pTicks.map((v, i) => (
              <text key={`p${i}`} x={SW - padR + 10} y={yP(v) + 6} textAnchor="start" fontSize={17} fill={red}>{fmtPrice(v)}</text>
            ))}
            {linePts && <polyline points={linePts} fill="none" stroke={red} strokeWidth={4}
              strokeLinejoin="round" strokeLinecap="round" />}
            {series.map((sr: any, i: number) => sr.price != null && (
              <circle key={`d${sr.d}`} cx={cx(i)} cy={yP(sr.price)} r={3.5} fill="#ffffff" stroke={red} strokeWidth={2.5} />
            ))}
          </g>
        )}
      </svg>
      <div style={{ display: "flex", gap: 22, justifyContent: "center", marginTop: 4 }}>
        {legend.map((lg) => (
          <span key={lg.l} style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 19, fontWeight: 650, color: ink }}>
            <span style={{ width: 16, height: 16, borderRadius: 4, background: lg.c, display: "inline-block" }} />{lg.l}
          </span>
        ))}
      </div>
    </div>
  );
};

const cardCss = `
.cn-wrap{display:flex;gap:22px;align-items:flex-start;flex-wrap:wrap}
.cn-controls{flex:1 1 340px;max-width:440px;display:flex;flex-direction:column;gap:14px}
.cn-grp{display:flex;flex-direction:column;gap:6px}
.cn-grp>label{font-size:12.5px;font-weight:700;color:#5a6b80}
.cn-grp .muted{font-weight:400;color:#9aa4b0}
.cn-grp select,.cn-grp input{padding:8px 10px;border:1px solid #d9e2ef;border-radius:9px;font-size:13.5px;flex:1}
.cn-seg{display:inline-flex;border:1px solid #cdd9ea;border-radius:9px;overflow:hidden;flex-wrap:wrap}
.cn-seg button{border:none;background:#fff;padding:8px 13px;font-size:13px;font-weight:700;color:#66748a;cursor:pointer}
.cn-seg button.on{background:#1268d3;color:#fff}
.cn-cols{display:flex;flex-wrap:wrap;gap:6px}
.cn-cols button{border:1px solid #d9e2ef;background:#fff;border-radius:999px;padding:6px 13px;font-size:13px;font-weight:650;color:#33415b;cursor:pointer}
.cn-cols button.on{border-color:#1268d3;background:#e8f1fc;color:#0b4ea2;font-weight:750}
.cn-bgs{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}
.cn-bg-th{height:38px;border-radius:9px;border:2px solid #e3e9f1;cursor:pointer;background-size:cover}
.cn-bg-th.on{border-color:#1268d3;box-shadow:0 0 0 2px rgba(18,104,211,.25)}
.cn-dl{margin-top:6px;display:inline-flex;align-items:center;justify-content:center;gap:8px;background:#1268d3;color:#fff;border:none;border-radius:11px;padding:13px;font-size:15px;font-weight:800;cursor:pointer}
.cn-dl:hover{background:#0c4ea0}
.cn-preview{flex:0 0 auto;padding:16px;background:#f0f3f8;border-radius:16px}
`;
