import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { SlidersHorizontal, RotateCcw, ArrowUpDown, ArrowUp, ArrowDown, Share2 } from "lucide-react";
import FetchError from "../components/FetchError";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";
import FavHeart from "../components/FavHeart";
import FavDashLink from "../components/FavDashLink";
import RequestCta from "../components/RequestCta";
import { useStickyState } from "../hooks/useStickyState";

const API_BASE = import.meta.env.VITE_API_BASE;

// 맞춤단지 찾기 (관리자 가오픈) — 조건을 '가이드 범위 칩'으로 고르면 지역 전체
// 단지×평형에서 맞는 행만 남긴다. 같은 조건 안 다중선택 = OR, 조건 사이 = AND.
// 지역은 시도만 골라도 동작(시도는 매물·실거래 있는 행만 오는 lean 응답).
// 보기 = 목록(표) / 지도(단지 마커 + 클릭 정보카드).
type Row = {
  c: string; n: string; d?: string | null; y?: string | null; hh?: number | null;
  sp?: string | null;        // 주인 조건 — o=주인전세 t=세안고 l=주인대출 (조합 문자열)
  py: string; sa?: number | null; ea?: number | null; ah?: number | null;
  ask?: number | null; an: number; au: number; js?: number | null; jn: number;
  gap?: number | null; jr?: number | null;
  la?: number | null; ld?: string | null; n12: number; a12?: number | null;
  pk?: number | null; pd?: string | null; vp?: number | null;
  sw?: string | null; swm?: number | null; swl?: string | null;
  sc?: string | null; scm?: number | null; scd?: number | null;
  rc?: number | null; bc?: number | null; et?: string | null;
  lat?: number | null; lng?: number | null;
};
type Res = { sigungu: string; asset: string; n_complex: number; rows: Row[] };
type Sido = { code: string; name: string };

const PY = 3.305785;
const eok = (v: number | null | undefined): string => {
  if (v == null) return "-";
  const e = v / 1e8;
  return e >= 100 ? `${Math.round(e)}억` : e >= 10 ? `${e.toFixed(1)}억` : `${e.toFixed(2)}억`;
};
const yy = (y?: string | null): string => (y && y.length >= 6 ? `${y.slice(2, 4)}.${y.slice(4, 6)}` : "-");
const ageOf = (y?: string | null): number | null =>
  (y && y.length >= 4 ? new Date().getFullYear() - Number(y.slice(0, 4)) : null);
const dShort = (d?: string | null): string => (d ? d.slice(2).replace(/-/g, ".") : "");
const supPyeong = (r: Row, asset: string): number | null => {
  const sa = r.sa ?? (r.ea != null ? r.ea / (asset === "offi" ? 0.5 : 0.78) : null);
  return sa != null ? sa / PY : null;
};
const normLines = (swl?: string | null): string[] =>
  !swl ? [] : Array.from(new Set(
    swl.split("·").map((s) => s.replace(/수도권|서울|도시철도/g, "").replace(/\s+/g, " ").trim()).filter(Boolean)));

type Preset = { label: string; min?: number; max?: number };
type Dim = { key: string; label: string; presets: Preset[]; get: (r: Row, asset: string) => number | null | undefined; cap?: string };
const DIMS: Dim[] = [
  { key: "py10", label: "평형대", cap: "공급면적 기준 · 공급면적이 없는 평형은 전용면적으로 환산(아파트 78%, 오피스텔 50%)",
    presets: [
      { label: "10평대", min: 10, max: 20 }, { label: "20평대", min: 20, max: 30 },
      { label: "30평대", min: 30, max: 40 }, { label: "40평대", min: 40, max: 50 },
      { label: "50평대", min: 50, max: 60 }, { label: "60평 이상", min: 60 }],
    get: (r, asset) => supPyeong(r, asset) },
  { key: "ask", label: "매매가",
    presets: [
      { label: "3억 이하", max: 3 }, { label: "3~5억", min: 3, max: 5 },
      { label: "5~10억", min: 5, max: 10 }, { label: "10~15억", min: 10, max: 15 },
      { label: "15~25억", min: 15, max: 25 }, { label: "25억 이상", min: 25 }],
    get: (r) => (r.ask != null ? r.ask / 1e8 : null) },
  { key: "age", label: "입주년차",
    presets: [
      { label: "5년 이내", max: 5 }, { label: "5~10년", min: 5, max: 10 },
      { label: "10~20년", min: 10, max: 20 }, { label: "20~30년", min: 20, max: 30 },
      { label: "30년 이상", min: 30 }],
    get: (r) => ageOf(r.y) },
  { key: "hh", label: "세대수",
    presets: [
      { label: "300 미만", max: 300 }, { label: "300~700", min: 300, max: 700 },
      { label: "700~1,500", min: 700, max: 1500 }, { label: "1,500 이상", min: 1500 }],
    get: (r) => r.hh },
  { key: "jr", label: "전세가율",
    presets: [
      { label: "50% 미만", max: 50 }, { label: "50~60%", min: 50, max: 60 },
      { label: "60~70%", min: 60, max: 70 }, { label: "70~80%", min: 70, max: 80 },
      { label: "80% 이상", min: 80 }],
    get: (r) => r.jr },
  { key: "gap", label: "갭",
    presets: [
      { label: "1억 이하", max: 1 }, { label: "1~3억", min: 1, max: 3 },
      { label: "3~5억", min: 3, max: 5 }, { label: "5~10억", min: 5, max: 10 },
      { label: "10억 이상", min: 10 }],
    get: (r) => (r.gap != null ? r.gap / 1e8 : null) },
  { key: "rc", label: "방",
    presets: [
      { label: "1개", min: 1, max: 1.5 }, { label: "2개", min: 2, max: 2.5 },
      { label: "3개", min: 3, max: 3.5 }, { label: "4개 이상", min: 4 }],
    get: (r) => r.rc },
  { key: "bc", label: "욕실",
    presets: [
      { label: "1개", min: 1, max: 1.5 }, { label: "2개", min: 2, max: 2.5 },
      { label: "3개 이상", min: 3 }],
    get: (r) => r.bc },
  { key: "swm", label: "지하철 도보",
    presets: [
      { label: "5분 이내", max: 5 }, { label: "10분 이내", max: 10 }, { label: "15분 이내", max: 15 }],
    get: (r) => r.swm },
  { key: "scd", label: "초등학교",
    presets: [
      { label: "300m 이내", max: 300 }, { label: "500m 이내", max: 500 }, { label: "1km 이내", max: 1000 }],
    get: (r) => r.scd },
  { key: "vp", label: "전고점 대비",
    presets: [
      { label: "-30% 이하", max: -30 }, { label: "-30~-20%", min: -30, max: -20 },
      { label: "-20~-10%", min: -20, max: -10 }, { label: "-10~0%", min: -10, max: 0 },
      { label: "신고가권(0%)", min: 0 }],
    get: (r) => r.vp },
];
const ET_OPTS = ["계단식", "복도식", "복합식"];
// 주인 조건 — 서버가 단지별로 보내는 sp 문자열의 각 글자와 대응(/special-deals 와 같은 분류).
const SP_OPTS = [
  { k: "o", label: "주인전세" },
  { k: "t", label: "세안고" },
  { k: "l", label: "주인대출" },
];
const GROUPS: { id: string; label: string; dims: string[]; et?: boolean; lines?: boolean; askInput?: boolean; sp?: boolean }[] = [
  { id: "py10", label: "평형대", dims: ["py10"] },
  { id: "ask", label: "매매가", dims: ["ask"], askInput: true },
  { id: "age", label: "입주년차", dims: ["age"] },
  { id: "hh", label: "세대수", dims: ["hh"] },
  { id: "jg", label: "전세·갭", dims: ["jr", "gap"] },
  { id: "room", label: "방·욕실", dims: ["rc", "bc"] },
  { id: "et", label: "현관구조", dims: [], et: true },
  { id: "sp", label: "주인조건", dims: [], sp: true },
  { id: "subway", label: "지하철", dims: ["swm"], lines: true },
  { id: "school", label: "초등학교", dims: ["scd"] },
  { id: "vp", label: "전고점", dims: ["vp"] },
];
const dimOf = (k: string): Dim => DIMS.find((d) => d.key === k)!;
const inPreset = (v: number, p: Preset): boolean =>
  (p.min == null || v >= p.min) && (p.max == null || (p.min != null && p.max <= p.min + 0.5 ? v <= p.max : v < p.max));

const COLS: { key: string; label: string }[] = [
  { key: "n", label: "단지명" }, { key: "d", label: "동" }, { key: "y", label: "연식" },
  { key: "hh", label: "세대수" }, { key: "py", label: "평형" }, { key: "ea", label: "전용㎡" },
  { key: "ah", label: "평형세대" }, { key: "rc", label: "방/욕실" }, { key: "et", label: "현관" },
  { key: "ask", label: "매매 최저" }, { key: "an", label: "매물" }, { key: "js", label: "전세 최저" },
  { key: "gap", label: "갭" }, { key: "jr", label: "전세가율" }, { key: "la", label: "최근 실거래" },
  { key: "n12", label: "12개월" }, { key: "pk", label: "신고가" }, { key: "vp", label: "전고점比" },
  { key: "swm", label: "지하철" }, { key: "scm", label: "배정초" },
];
const COL_SORT: Record<string, string> = {
  n: "n", d: "d", y: "age", hh: "hh", py: "ea", ea: "ea", ah: "ah", rc: "rc", et: "et",
  ask: "ask", an: "an", js: "js", gap: "gap", jr: "jr",
  la: "la", n12: "n12", pk: "pk", vp: "vp", swm: "swm", scm: "scd",
};

export default function ComplexFinder() {
  // 지역·조건·정렬은 localStorage 유지 — 단지 상세 갔다 뒤로 와도 검색결과 보존
  const [sido, setSido] = useStickyState("finder:sido", "");
  const [sigungu, setSigungu] = useStickyState("finder:sigungu", "");
  const [asset, setAsset] = useStickyState<"apt" | "offi" | "all">("finder:asset", "apt");
  const region = sigungu ? sigungu.slice(0, 5) : sido ? sido.slice(0, 2) : "";
  const sidoQ = useFetchJson<{ items: Sido[] }>(API_BASE ? `${API_BASE}/stats/changes/sido-list` : null);
  const sggQ = useFetchJson<{ items: Sido[] }>(
    API_BASE && sido ? `${API_BASE}/stats/sigungu-list?sido=${sido.slice(0, 2)}` : null);
  const dataQ = useFetchJson<Res>(
    API_BASE && region ? `${API_BASE}/stats/complex-finder?sigungu=${region}&asset=${asset}` : null);

  const [sel, setSel] = useStickyState<Record<string, number[]>>("finder:sel", {});
  const [selEt, setSelEt] = useStickyState<string[]>("finder:et", []);
  const [selSp, setSelSp] = useStickyState<string[]>("finder:sp", []);
  const [selLine, setSelLine] = useStickyState<string[]>("finder:line", []);
  const [askMin, setAskMin] = useStickyState("finder:askMin", "");
  const [askMax, setAskMax] = useStickyState("finder:askMax", "");
  const [hlC, setHlC] = useState<string | null>(null);   // 지도에서 고른 단지 — 표 하이라이트
  const [sortKey, setSortKey] = useStickyState("finder:sortKey", "ask");
  const [sortDir, setSortDir] = useStickyState<1 | -1>("finder:sortDir", -1);
  const [limit, setLimit] = useState(300);
  const [openG, setOpenG] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const barRef = useRef<HTMLDivElement>(null);

  // ── 결과 공유(아파트매수계산기와 동일 방식) — 조건 전체를 서버에 저장하고
  //    짧은 코드(?s=)만 공유해 카카오톡 등에서 링크로 잘 인식되게 한다.
  const applyShared = (enc: string) => {
    try {
      const json = new TextDecoder().decode(
        Uint8Array.from(atob(decodeURIComponent(enc)), (c) => c.charCodeAt(0)));
      const p = JSON.parse(json);
      if (p.sido != null) setSido(p.sido);
      if (p.sigungu != null) setSigungu(p.sigungu);
      if (p.asset) setAsset(p.asset);
      if (p.sel) setSel(p.sel);
      if (p.selEt) setSelEt(p.selEt);
      if (p.selSp) setSelSp(p.selSp);
      if (p.selLine) setSelLine(p.selLine);
      if (p.askMin != null) setAskMin(p.askMin);
      if (p.askMax != null) setAskMax(p.askMax);
      if (p.sortKey) setSortKey(p.sortKey);
      if (p.sortDir) setSortDir(p.sortDir);
    } catch { /* 잘못된 링크는 무시 */ }
  };
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const s = q.get("s");
    if (s) {
      fetch(`${API_BASE}/share/${encodeURIComponent(s)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => { if (j?.payload) applyShared(j.payload); })
        .catch(() => {});
    } else {
      const d = q.get("d");
      if (d) applyShared(d);
    }
    if (s || q.get("d")) {  // 공유 파라미터는 복원 후 URL에서 제거(깔끔한 주소)
      window.history.replaceState(null, "", window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const buildShareUrl = async (): Promise<string> => {
    const json = JSON.stringify({ sido, sigungu, asset, sel, selEt, selSp, selLine, askMin, askMax, sortKey, sortDir });
    const enc = btoa(String.fromCharCode(...new TextEncoder().encode(json)));
    const base = `${window.location.origin}${window.location.pathname}`;
    try {
      const r = await fetch(`${API_BASE}/share`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload: enc }),
      });
      if (r.ok) { const j = await r.json(); if (j?.id) return `${base}?s=${j.id}`; }
    } catch { /* 폴백 */ }
    return `${base}?d=${encodeURIComponent(enc)}`;
  };
  const shareResult = async () => {
    const url = await buildShareUrl();
    const nav = navigator as Navigator & { share?: (d: { title?: string; url: string }) => Promise<void> };
    if (nav.share) {
      try { await nav.share({ title: "콕집 맞춤단지 찾기", url }); return; } catch { /* 취소 */ }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true); setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("아래 주소를 복사해 공유하세요", url);
    }
  };

  useEffect(() => {
    if (!openG) return;
    const h = (e: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(e.target as Node)) setOpenG(null);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [openG]);

  const togglePreset = (dim: string, i: number) => {
    setLimit(300);
    setSel((s) => {
      const cur = s[dim] ?? [];
      return { ...s, [dim]: cur.includes(i) ? cur.filter((x) => x !== i) : [...cur, i] };
    });
  };
  const toggleIn = (list: string[], set: (v: string[]) => void, v: string) => {
    setLimit(300);
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  };
  const resetAll = () => {
    setSel({}); setSelEt([]); setSelLine([]); setAskMin(""); setAskMax(""); setLimit(300);
  };
  const askCustom = askMin.trim() !== "" || askMax.trim() !== "";
  const nActive = Object.values(sel).filter((v) => v.length).length
    + (selEt.length ? 1 : 0) + (selSp.length ? 1 : 0) + (selLine.length ? 1 : 0) + (askCustom ? 1 : 0);

  const lineOpts = useMemo(() => {
    const cnt = new Map<string, number>();
    for (const r of dataQ.data?.rows ?? []) {
      for (const l of normLines(r.swl)) cnt.set(l, (cnt.get(l) ?? 0) + 1);
    }
    return Array.from(cnt.keys()).sort((a, b) => {
      const na = /^(\d+)호선$/.exec(a), nb = /^(\d+)호선$/.exec(b);
      if (na && nb) return Number(na[1]) - Number(nb[1]);
      if (na) return -1;
      if (nb) return 1;
      return a.localeCompare(b, "ko");
    });
  }, [dataQ.data]);

  const rows = useMemo(() => {
    let rs = dataQ.data?.rows ?? [];
    const cMn = askMin.trim() === "" ? null : Number(askMin);
    const cMx = askMax.trim() === "" ? null : Number(askMax);
    for (const dim of DIMS) {
      const picked = sel[dim.key] ?? [];
      const custom = dim.key === "ask" && askCustom;
      if (picked.length === 0 && !custom) continue;
      rs = rs.filter((r) => {
        const v = dim.get(r, asset);
        if (v == null) return false;
        if (picked.some((i) => inPreset(v, dim.presets[i]))) return true;
        if (custom && (cMn == null || v >= cMn) && (cMx == null || v <= cMx)) return true;
        return false;
      });
    }
    if (selEt.length) rs = rs.filter((r) => r.et != null && selEt.includes(r.et));
    if (selSp.length) rs = rs.filter((r) => !!r.sp && selSp.some((k) => r.sp!.includes(k)));
    if (selLine.length) rs = rs.filter((r) => normLines(r.swl).some((l) => selLine.includes(l)));
    const dim = DIMS.find((d) => d.key === sortKey);
    const get = dim ? (r: Row) => dim.get(r, asset)
      : (r: Row) => (r as unknown as Record<string, number | string | null | undefined>)[sortKey];
    return rs.slice().sort((a, b) => {
      const va = get(a), vb = get(b);
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return (va < vb ? -1 : va > vb ? 1 : 0) * sortDir;
    });
  }, [dataQ.data, sel, selEt, selSp, selLine, sortKey, sortDir, asset, askMin, askMax, askCustom]);

  // 지도 마커 클릭 → 표에서 그 단지 위치로 스크롤 + 반짝 하이라이트
  const pickFromMap = (cno: string) => {
    setHlC(cno);
    const idx = rows.findIndex((r) => r.c === cno);
    if (idx >= 0 && idx >= limit) setLimit(Math.ceil((idx + 1) / 300) * 300);
    setTimeout(() => {
      document.querySelector(`tr[data-c="${cno}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
  };

  const nComplex = useMemo(() => new Set(rows.map((r) => r.c)).size, [rows]);
  const sortBy = (key: string) => {
    if (sortKey === key) setSortDir((d) => (d === 1 ? -1 : 1));
    else { setSortKey(key); setSortDir(-1); }
  };
  const sortIc = (key: string) =>
    sortKey !== key ? <ArrowUpDown size={11} className="cf-sort-ic" />
      : sortDir === -1 ? <ArrowDown size={11} className="cf-sort-ic on" />
        : <ArrowUp size={11} className="cf-sort-ic on" />;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "0 0 4px" }}>
        <h2 style={{ margin: 0, display: "inline-flex", alignItems: "center", gap: 7 }}>
          <SlidersHorizontal size={18} strokeWidth={2.3} style={{ color: "#1268d3" }} aria-hidden />
          맞춤단지 찾기
        </h2>
        <FavDashLink />
        <button type="button" onClick={shareResult} disabled={!region}
          title={region ? "지금 조건을 링크로 공유" : "지역을 먼저 선택하세요"}
          className="cf-share-btn" style={{ marginLeft: "auto" }}>
          <Share2 size={15} /> {copied ? "복사됐어요!" : "결과 공유"}
        </button>
      </div>
      <div style={{ marginBottom: 10 }} />

      <div className="filter-bar" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
        <select className="fsel" value={sido} onChange={(e) => { setSido(e.target.value); setSigungu(""); }}>
          <option value="">시도 선택</option>
          {(sidoQ.data?.items ?? []).map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select className="fsel" value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}>
          <option value="">시 전체</option>
          {(sggQ.data?.items ?? []).map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select className="fsel" value={asset} onChange={(e) => setAsset(e.target.value as "apt" | "offi" | "all")}>
          <option value="apt">아파트</option>
          <option value="offi">오피스텔</option>
          <option value="all">통합</option>
        </select>
      </div>

      <div className={`cf-fbar${region ? "" : " off"}`} ref={barRef}>
        {GROUPS.map((g) => {
          const picked: string[] = [
            ...g.dims.flatMap((k) => (sel[k] ?? []).map((i) => dimOf(k).presets[i].label)),
            ...(g.et ? selEt : []),
            ...(g.lines ? selLine : []),
            ...(g.askInput && askCustom ? [`${askMin || ""}~${askMax || ""}억`] : []),
          ];
          const on = picked.length > 0;
          const label = on ? `${g.label} · ${picked.length === 1 ? picked[0] : `${picked.length}`}` : g.label;
          return (
            <span key={g.id} className="cf-fbtn-wrap">
              <button type="button" disabled={!region}
                className={`cf-fbtn${on ? " on" : ""}${openG === g.id ? " open" : ""}`}
                onClick={() => setOpenG(openG === g.id ? null : g.id)}>
                {label}<i className="cf-caret" />
              </button>
              {openG === g.id && region && (
                <div className="cf-fpop" style={g.lines ? { minWidth: 340 } : undefined}>
                  {g.dims.map((k) => {
                    const dim = dimOf(k);
                    return (
                      <div key={k} className="cf-fpop-sec">
                        {g.dims.length > 1 && <div className="cf-fpop-t">{dim.label}</div>}
                        <div className="cf-fchips">
                          {dim.presets.map((p, i) => (
                            <button key={p.label} type="button"
                              className={(sel[k] ?? []).includes(i) ? "on" : ""}
                              onClick={() => togglePreset(k, i)}>
                              {p.label}
                            </button>
                          ))}
                        </div>
                        {dim.cap && <div className="cf-fcap">{dim.cap}</div>}
                      </div>
                    );
                  })}
                  {g.askInput && (
                    <div className="cf-fpop-sec">
                      <div className="cf-fpop-t">직접 입력 (억)</div>
                      <div className="cf-askrow">
                        <input type="number" inputMode="decimal" placeholder="최소" value={askMin}
                          onChange={(e) => { setAskMin(e.target.value); setLimit(300); }} />
                        <span>~</span>
                        <input type="number" inputMode="decimal" placeholder="최대" value={askMax}
                          onChange={(e) => { setAskMax(e.target.value); setLimit(300); }} />
                        {askCustom && (
                          <button type="button" className="cf-askclr" onClick={() => { setAskMin(""); setAskMax(""); }}>지움</button>
                        )}
                      </div>
                      <div className="cf-fcap">범위 버튼과 함께 고르면 어느 한쪽만 맞아도 포함돼요</div>
                    </div>
                  )}
                  {g.et && (
                    <div className="cf-fpop-sec">
                      <div className="cf-fchips">
                        {ET_OPTS.map((e) => (
                          <button key={e} type="button" className={selEt.includes(e) ? "on" : ""}
                            onClick={() => toggleIn(selEt, setSelEt, e)}>{e}</button>
                        ))}
                      </div>
                    </div>
                  )}
                  {g.sp && (
                    <div className="cf-fpop-sec">
                      <div className="cf-fchips">
                        {SP_OPTS.map((o) => (
                          <button key={o.k} type="button" className={selSp.includes(o.k) ? "on" : ""}
                            onClick={() => toggleIn(selSp, setSelSp, o.k)}>{o.label}</button>
                        ))}
                      </div>
                      <div className="cf-fcap">
                        중개사가 매물 설명란에 적어 광고한 조건이에요. 해당 매물이 하나라도 있는 단지를 보여드려요
                      </div>
                    </div>
                  )}
                  {g.lines && lineOpts.length > 0 && (
                    <div className="cf-fpop-sec">
                      <div className="cf-fpop-t">노선 <span className="cf-fcap" style={{ display: "inline", margin: 0 }}>(가장 가까운 역 기준)</span></div>
                      <div className="cf-fchips">
                        {lineOpts.map((l) => (
                          <button key={l} type="button" className={selLine.includes(l) ? "on" : ""}
                            onClick={() => toggleIn(selLine, setSelLine, l)}>{l}</button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </span>
          );
        })}
        {region ? (
          <>
            {nActive > 0 && (
              <button type="button" className="cf-reset" onClick={resetAll}>
                <RotateCcw size={12} /> 초기화
              </button>
            )}
            {dataQ.data && (
              <span className="cf-fsum">
                <b>{rows.length.toLocaleString()}</b>개 평형 · 단지 {nComplex.toLocaleString()}곳
              </span>
            )}
          </>
        ) : null}
      </div>

      {dataQ.error && <FetchError message={dataQ.error} inline />}
      {dataQ.loading && <Loading />}

      {dataQ.data && region && (
        <>
          {/* 표 위 — 조건을 잔뜩 걸고도 원하는 게 없을 수 있으니, 목록을 훑기 전에
              '조건을 남기는 길'을 먼저 보여준다. 지역·유형은 보던 그대로 넘어간다. */}
          <RequestCta
            title="조건에 딱 맞는 곳이 없으면"
            sub="조건을 남기시면 아직 안 올라온 매물까지 이 동네 중개사무소가 찾아 제안합니다."
            sido={sido} sigungu={sigungu}
            asset={asset === "all" ? undefined : asset} />
          <div className="cf-tblwrap">
            <table className="cf-tbl">
              <thead>
                <tr>
                  {COLS.map((col) => (
                    <th key={col.key} onClick={() => sortBy(COL_SORT[col.key] || col.key)} className="cf-th">
                      {col.label} {sortIc(COL_SORT[col.key] || col.key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, limit).map((r) => (
                  <tr key={`${r.c}|${r.py}`} data-c={r.c} className={hlC === r.c ? "cf-hl" : ""}>
                    <td className="cf-name"><Link to={`/complex/${r.c}`}>{r.n}</Link><FavHeart complexNo={r.c} complexName={r.n} /></td>
                    <td className="cf-dim">{r.d || "-"}</td>
                    <td className="cf-dim">{yy(r.y)}</td>
                    <td>{r.hh?.toLocaleString() ?? "-"}</td>
                    <td className="cf-py">{r.py}{(() => { const p = supPyeong(r, asset); return p ? <span className="cf-sub">{Math.round(p)}평</span> : null; })()}</td>
                    <td>{r.ea ?? "-"}</td>
                    <td className="cf-dim">{r.ah ?? "-"}</td>
                    <td>{r.rc != null ? `${r.rc}/${r.bc ?? "-"}` : "-"}</td>
                    <td className="cf-dim">{r.et || "-"}</td>
                    <td className="cf-price">{eok(r.ask)}</td>
                    <td>{r.an > 0 ? <>{r.an}<span className="cf-sub">/{r.au}</span></> : "-"}</td>
                    <td>{eok(r.js)}</td>
                    <td>{eok(r.gap)}</td>
                    <td>{r.jr != null ? `${r.jr}%` : "-"}</td>
                    <td>{r.la ? <>{eok(r.la)}<span className="cf-sub">{dShort(r.ld)}</span></> : "-"}</td>
                    <td>{r.n12 > 0 ? <>{r.n12}건<span className="cf-sub">{eok(r.a12)}</span></> : "-"}</td>
                    <td>{r.pk ? <>{eok(r.pk)}<span className="cf-sub">{dShort(r.pd)}</span></> : "-"}</td>
                    <td className={r.vp != null ? (r.vp >= 0 ? "cf-up" : "cf-down") : ""}>
                      {r.vp != null ? `${r.vp > 0 ? "+" : ""}${r.vp}%` : "-"}
                    </td>
                    <td className="cf-dim">{r.sw ? <>{r.sw} {r.swm}분<span className="cf-sub">{normLines(r.swl).join("·")}</span></> : "-"}</td>
                    <td className="cf-dim">
                      {r.sc ? <>{r.sc.replace("등학교", "")} {r.scd != null && r.scd >= 1000 ? `${(r.scd / 1000).toFixed(1)}km` : `${r.scd ?? "?"}m`}<span className="cf-sub">{r.scm}분</span></> : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > limit && (
            <button type="button" className="cf-more" onClick={() => setLimit((l) => l + 300)}>
              더 보기 ({(rows.length - limit).toLocaleString()}행 남음)
            </button>
          )}
          <FinderMap rows={rows} onPick={pickFromMap} pickedC={hlC} />
        </>
      )}

      {dataQ.data && region && (
        <p className="muted" style={{ fontSize: 11.5, margin: "10px 0 0" }}>
          매매/전세 = 현재 최저 호가 · 매물 = 광고수/실매물 · 실거래는 해제거래 제외, 평형 전용 ±3.5㎡ 기준 ·
          전고점比 = 최근 실거래 vs 역대 신고가 · 도보 = 직선 ×1.25 ÷ 80m/분
          {sigungu === "" && " · 시 전체 보기는 매물·최근 실거래가 있는 평형만 포함"}
        </p>
      )}

      <style>{`
        .cf-share-btn{display:inline-flex;align-items:center;gap:6px;border:1px solid #cfe0f5;background:#eef5fe;border-radius:999px;padding:7px 15px;font-size:13px;font-weight:750;color:#0b4ea2;cursor:pointer;white-space:nowrap}
        .cf-share-btn:not(:disabled):hover{background:#1268d3;border-color:#1268d3;color:#fff}
        .cf-share-btn:disabled{opacity:.45;cursor:not-allowed}
        .cf-seg{display:inline-flex;border:1px solid #cdd9ea;border-radius:9px;overflow:hidden}
        .cf-seg button{display:inline-flex;align-items:center;gap:5px;border:none;background:#fff;padding:6px 14px;font-size:12.5px;font-weight:700;color:#66748a;cursor:pointer}
        .cf-seg button.on{background:#1268d3;color:#fff}
        .cf-fbar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:14px}
        .cf-fbar.off .cf-fbtn{opacity:.5;cursor:not-allowed}
        .cf-fhint{font-size:12.5px;color:#8fa0b8;margin-left:4px}
        .cf-fbtn-wrap{position:relative}
        .cf-fbtn{display:inline-flex;align-items:center;gap:5px;border:1px solid #d9e2ef;background:#fff;border-radius:999px;padding:6px 13px;font-size:13px;font-weight:650;color:#33415b;cursor:pointer;white-space:nowrap}
        .cf-fbtn:not(:disabled):hover{border-color:#1268d3;color:#1268d3}
        .cf-fbtn.on{border-color:#1268d3;background:#e8f1fc;color:#0b4ea2;font-weight:750}
        .cf-fbtn.open{border-color:#1268d3;box-shadow:0 0 0 2.5px rgba(18,104,211,.14)}
        .cf-caret{width:7px;height:7px;border-right:1.6px solid currentColor;border-bottom:1.6px solid currentColor;transform:rotate(45deg) translateY(-2px);opacity:.55}
        .cf-fpop{position:absolute;top:calc(100% + 7px);left:0;z-index:80;background:#fff;border:1px solid #d9e2ef;border-radius:13px;box-shadow:0 14px 36px -10px rgba(19,41,75,.28);padding:13px 15px;min-width:264px}
        .cf-fpop-sec + .cf-fpop-sec{margin-top:11px;padding-top:11px;border-top:1px solid #f2f5fa}
        .cf-fpop-t{font-size:11.5px;font-weight:800;color:#33415b;margin-bottom:7px}
        .cf-fchips{display:flex;flex-wrap:wrap;gap:6px}
        .cf-fchips button{border:1px solid #d9e2ef;background:#fff;border-radius:8px;padding:4.5px 12px;font-size:12.5px;font-weight:600;color:#4a5a74;cursor:pointer;line-height:1.35}
        .cf-fchips button:hover{border-color:#1268d3;color:#1268d3}
        .cf-fchips button.on{background:#1268d3;border-color:#1268d3;color:#fff;font-weight:700}
        .cf-fcap{font-size:10.5px;color:#8fa0b8;margin-top:6px}
        .cf-askrow{display:flex;align-items:center;gap:6px}
        .cf-askrow input{width:78px;padding:5px 8px;border:1px solid #d9e2ef;border-radius:7px;font-size:13px}
        .cf-askclr{border:1px solid #d9e2ef;background:#fff;border-radius:7px;padding:5px 9px;font-size:11.5px;color:#66748a;cursor:pointer}
        .cf-fcheck{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;color:#4a5a74;cursor:pointer;margin-left:6px}
        .cf-reset{display:inline-flex;align-items:center;gap:4px;border:none;background:none;color:#c0392b;font-size:12px;font-weight:700;cursor:pointer;padding:0}
        .cf-fsum{margin-left:auto;font-size:12.5px;color:#66748a;white-space:nowrap}
        .cf-fsum b{color:#1268d3;font-size:14px}
        .cf-tblwrap{overflow-x:auto;border:1px solid #e3e9f2;border-radius:12px;background:#fff}
        .cf-tbl{width:100%;border-collapse:collapse;font-size:12.5px;white-space:nowrap}
        .cf-tbl th{position:sticky;top:0;background:#f6f9fd;z-index:5;font-size:11px;color:#66748a;font-weight:700;padding:8px 9px;text-align:right;border-bottom:1.5px solid #dde5f0;cursor:pointer;user-select:none}
        .cf-tbl th:nth-child(-n+3){text-align:left}
        .cf-tbl td{padding:6px 9px;border-bottom:1px solid #f0f4fa;text-align:right;font-variant-numeric:tabular-nums}
        .cf-tbl td:nth-child(-n+3){text-align:left}
        .cf-tbl tbody tr:hover{background:#f6faff}
        .cf-tbl tbody tr.cf-hl{background:#fff6df}
        .cf-tbl tbody tr.cf-hl td{animation:cfFlash 0.55s ease 3}
        @keyframes cfFlash{50%{background:#ffe089}}
        .cf-name a{font-weight:700;color:#13294b;text-decoration:none}
        .cf-name a:hover{color:#1268d3;text-decoration:underline}
        .cf-dim{color:#66748a}
        .cf-py{font-weight:700;color:#1f2a37}
        .cf-price{font-weight:700;color:#13294b}
        .cf-sub{display:block;font-size:10px;color:#8fa0b8;font-weight:500;line-height:1.2}
        .cf-up{color:#c0392b;font-weight:700}
        .cf-down{color:#1268d3;font-weight:700}
        .cf-sort-ic{opacity:.35;vertical-align:-1px}
        .cf-sort-ic.on{opacity:1;color:#1268d3}
        .cf-more{display:block;margin:12px auto 0;border:1.5px solid #cdd9ea;background:#fff;border-radius:999px;padding:7px 22px;font-size:13px;font-weight:700;color:#1268d3;cursor:pointer}
        .cf-more:hover{border-color:#1268d3}
        .cf-mapwrap{position:relative;border:1px solid #e3e9f2;border-radius:12px;overflow:hidden;background:#fff}
        .cf-mapdiv{width:100%;height:620px}
        .cfm-marker{display:inline-flex;align-items:center;background:#fff;border:1.5px solid #1268d3;border-radius:999px;padding:0;overflow:hidden;box-shadow:0 2px 8px rgba(19,41,75,.22);cursor:pointer;white-space:nowrap}
        .cfm-px{font-size:11.5px;font-weight:800;color:#13294b;padding:3px 7px 3px 9px}
        .cfm-n{font-size:10px;font-weight:700;color:#fff;background:#1268d3;padding:4px 8px 4px 6px}
        .cfm-marker:hover{border-color:#0b4ea2}
        .cfm-marker.picked{border-color:#c0392b;box-shadow:0 0 0 3px rgba(192,57,43,.25)}
        .cfm-marker.picked .cfm-n{background:#c0392b}
        .cf-map-cap{position:absolute;left:12px;bottom:10px;z-index:40;background:rgba(255,255,255,.92);border-radius:8px;padding:4px 10px;font-size:11px;color:#66748a}
        @media (max-width:640px){.cf-fpop{min-width:230px}}
      `}</style>
    </div>
  );
}

// ── 지도 — 필터 결과를 단지 단위 시세 마커로. 클릭하면 위 표의 해당 단지로 스크롤+하이라이트 ──
type MapCx = {
  c: string; n: string; d?: string | null; y?: string | null; hh?: number | null;
  lat: number; lng: number; minAsk: number | null; rows: Row[];
};
const MAP_CAP = 400;

function FinderMap({ rows, onPick, pickedC }: {
  rows: Row[]; onPick: (cno: string) => void; pickedC: string | null;
}) {
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<unknown>(null);
  const ovsRef = useRef<{ setMap: (m: unknown) => void }[]>([]);
  const elsRef = useRef<Map<string, HTMLElement>>(new Map());
  const [mapErr, setMapErr] = useState("");

  const complexes = useMemo(() => {
    const by = new Map<string, MapCx>();
    for (const r of rows) {
      if (r.lat == null || r.lng == null) continue;
      let e = by.get(r.c);
      if (!e) {
        e = { c: r.c, n: r.n, d: r.d, y: r.y, hh: r.hh, lat: r.lat, lng: r.lng, minAsk: null, rows: [] };
        by.set(r.c, e);
      }
      e.rows.push(r);
      if (r.ask != null && (e.minAsk == null || r.ask < e.minAsk)) e.minAsk = r.ask;
    }
    // 표시 상한 — 세대수 큰 단지 우선(조건을 좁히면 전부 보임)
    const all = Array.from(by.values());
    all.sort((a, b) => (b.hh ?? 0) - (a.hh ?? 0));
    return { list: all.slice(0, MAP_CAP), total: all.length };
  }, [rows]);

  useEffect(() => {
    if (!mapEl.current) return;
    let cancelled = false;
    import("../lib/kakaomap").then(({ loadKakao, escapeHtml, attachMapControls }) => loadKakao().then(() => {
      if (cancelled || !mapEl.current) return;
      const kakao = (window as unknown as { kakao: any }).kakao;   // eslint-disable-line @typescript-eslint/no-explicit-any
      if (!mapRef.current) {
        mapRef.current = new kakao.maps.Map(mapEl.current, {
          center: new kakao.maps.LatLng(37.5, 127.0), level: 7,
        });
      }
      const map = mapRef.current;
      attachMapControls(map, mapEl.current);
      ovsRef.current.forEach((o) => o.setMap(null));
      ovsRef.current = [];
      elsRef.current = new Map();
      if (complexes.list.length === 0) return;
      const bounds = new kakao.maps.LatLngBounds();
      for (const cx of complexes.list) {
        const pos = new kakao.maps.LatLng(cx.lat, cx.lng);
        bounds.extend(pos);
        const el = document.createElement("button");
        el.type = "button";
        el.className = "cfm-marker";
        el.innerHTML = `<span class="cfm-px">${eok(cx.minAsk)}</span><span class="cfm-n">${cx.rows.length}</span>`;
        el.title = escapeHtml(cx.n);
        el.addEventListener("click", () => onPick(cx.c));
        elsRef.current.set(cx.c, el);
        const ov = new kakao.maps.CustomOverlay({ map, position: pos, yAnchor: 0.5, zIndex: 5, content: el });
        // 겹친 마커가 클릭을 가로채지 않게 — 호버한 마커를 맨 위로
        el.addEventListener("mouseenter", () => ov.setZIndex(120));
        el.addEventListener("mouseleave", () => ov.setZIndex(5));
        ovsRef.current.push(ov);
      }
      (map as { setBounds: (b: unknown, ...p: number[]) => void }).setBounds(bounds, 40, 40, 40, 40);
    })).catch(() => setMapErr("지도 로드 실패 — 목록 보기로 확인해주세요"));
    return () => { cancelled = true; };
  }, [complexes]);   // eslint-disable-line react-hooks/exhaustive-deps

  // 고른 단지 마커 강조 — 마커 재생성 없이 클래스만 토글(줌·중심 유지)
  useEffect(() => {
    elsRef.current.forEach((el, c) => el.classList.toggle("picked", c === pickedC));
  }, [pickedC, complexes]);

  return (
    <div className="cf-mapwrap" style={{ marginTop: 14 }}>
      <div ref={mapEl} className="cf-mapdiv" />
      {mapErr && <div className="modal-msg" style={{ margin: 10 }}>{mapErr}</div>}
      <div className="cf-map-cap">
        마커 = 매매 최저 호가 · 뱃지 = 조건에 맞는 평형 수 · 누르면 위 표의 해당 단지로 이동
        {complexes.total > MAP_CAP && ` · 세대수 상위 ${MAP_CAP}개 단지만 표시(조건을 좁혀보세요)`}
      </div>
    </div>
  );
}
