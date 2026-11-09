// 통계 창 — 옛 통계 페이지(실거래·매물호가·거래량·투자)를 지도 위 창으로 다시 만든 것.
// 운영 페이지를 불러오지 않고 같은 API 를 testv2 모양(평평한 표·얇은 줄·글자 세그먼트)으로 그린다.
// 4묶음 = 절충안의 실거래·시세분석 4탭: 실거래가 · 매물호가추이 · 시장흐름 · 투자분석.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, ComposedChart, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceArea, ReferenceLine, Cell } from "recharts";
import { Dd, getJson } from "./Drawer";
import { areaLabel } from "../src/lib/area";

export type StatsGroup = "price" | "hoga" | "flow" | "invest";
export type StatsKey = { g: StatsGroup; i: string };
export const STATS_GROUPS: { k: StatsGroup; l: string; items: { k: string; l: string }[] }[] = [
  { k: "price", l: "실거래가", items: [
    { k: "top", l: "실거래 최고가" }, { k: "rh", l: "단지별 신고가" }, { k: "ppy", l: "평당가" }, { k: "chg", l: "가격 변동률" },
    { k: "tm", l: "부동산타임머신" }, { k: "cancel", l: "취소거래" }, { k: "map", l: "실거래 지도" },
  ] },
  { k: "hoga", l: "매물호가추이", items: [
    { k: "sum", l: "가격 추이" }, { k: "rank", l: "지역별 순위" }, { k: "mov", l: "상승·하락" }, { k: "cnt", l: "지역별 매물수" },
  ] },
  { k: "flow", l: "시장흐름", items: [
    { k: "vol", l: "기간별 거래량" }, { k: "pulse", l: "신고 현황" }, { k: "topvol", l: "단지별 거래량" }, { k: "turn", l: "거래회전율" },
  ] },
  { k: "invest", l: "투자분석", items: [
    { k: "gap", l: "갭투자" }, { k: "yield", l: "월세수익률" }, { k: "low", l: "시세차이 저가" }, { k: "presale", l: "분양권" }, { k: "jeonse", l: "깡통전세지수" },
  ] },
];
export const statsKeyOf = (s: string | null): StatsKey | null => {
  if (!s) return null;
  const [g, i] = s.split(".");
  const grp = STATS_GROUPS.find((x) => x.k === g);
  if (!grp) return null;
  const it = grp.items.find((x) => x.k === i) ?? grp.items[0];
  return { g: grp.k, i: it.k };
};

// ── 공통 ──────────────────────────────────────────────
export type RegionSel = { sido: string; sgg: string; dong: string };   // 10자리 법정동 코드(빈 값=전국)
type Opt = { code: string; name: string };
const won = (v: number | null | undefined): string => {
  if (v == null) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8); const m = Math.floor((v % 1e8) / 1e4); return m > 0 ? `${e}억 ${m.toLocaleString()}` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
};
const wonS = (v: number | null | undefined) => (!v ? "-" : v >= 1e8 ? `${(v / 1e8).toFixed(1)}억` : `${Math.round(v / 1e4).toLocaleString()}만`);
const pct = (r: number | null | undefined, d = 1) => (r == null ? "-" : `${r > 0 ? "+" : ""}${(r * 100).toFixed(d)}%`);
const num = (n: number | null | undefined) => (n == null ? "-" : Math.round(n).toLocaleString());
const sgn = (v: number | null | undefined) => (v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "");
const AREA_CLASSES: Opt[] = [
  { code: "all", name: "면적 전체" }, { code: "under10", name: "10평 미만" }, { code: "10s", name: "10평대" }, { code: "20s", name: "20평대" },
  { code: "30s", name: "30평대" }, { code: "40s", name: "40평대" }, { code: "over50", name: "50평 초과" },
];
const SIDO_ORDER = ["11", "26", "27", "28", "29", "46", "30", "31", "36", "41", "42", "51", "43", "44", "45", "52", "47", "48", "50"];
const sidoRank = (c: string) => { const i = SIDO_ORDER.indexOf((c || "").slice(0, 2)); return i < 0 ? 99 : i; };

function useQ<T>(url: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!!url);
  const [err, setErr] = useState(false);
  useEffect(() => {
    if (!url) { setData(null); setLoading(false); return; }
    let off = false;
    setLoading(true); setErr(false);
    getJson(url).then((j) => { if (!off) { setData(j); setLoading(false); } }).catch(() => { if (!off) { setErr(true); setLoading(false); } });
    return () => { off = true; };
  }, [url]);
  return { data, loading, err };
}

// 지역 목록(시·도 → 시·군·구 → 읍·면·동). 코드는 10자리.
function useRegionLists(r: RegionSel) {
  const [sidos, setSidos] = useState<Opt[]>([]);
  const [sggs, setSggs] = useState<Opt[]>([]);
  const [dongs, setDongs] = useState<Opt[]>([]);
  useEffect(() => { getJson("/stats/changes/sido-list").then((j) => setSidos(j.items || [])).catch(() => {}); }, []);
  useEffect(() => { if (!r.sido) { setSggs([]); return; } getJson(`/stats/sigungu-list?sido=${r.sido}`).then((j) => setSggs(j.items || [])).catch(() => setSggs([])); }, [r.sido]);
  useEffect(() => { if (!r.sgg) { setDongs([]); return; } getJson(`/stats/dong-list?sigungu=${r.sgg}`).then((j) => setDongs(j.items || [])).catch(() => setDongs([])); }, [r.sgg]);
  return { sidos, sggs, dongs };
}
// 각 통계가 받는 지역 깊이만큼 쿼리로. depth: dong(동까지) / sgg(시군구까지) / sido(시도만)
const rq = (r: RegionSel, depth: "dong" | "sgg" | "sido" = "dong") => {
  if (depth === "dong" && r.dong) return `&dong=${r.dong}`;
  if (depth !== "sido" && r.sgg) return `&sigungu=${r.sgg}`;
  if (r.sido) return `&sido=${r.sido}`;
  return "";
};
const regionLabel = (r: RegionSel, L: ReturnType<typeof useRegionLists>) => {
  const a = L.sidos.find((x) => x.code === r.sido)?.name, b = L.sggs.find((x) => x.code === r.sgg)?.name, c = L.dongs.find((x) => x.code === r.dong)?.name;
  return [a, b, c].filter(Boolean).join(" ") || "전국";
};

// 글자 세그먼트(평평한 줄). 운영 '필터 순서 표준'(거래→지역→유형→면적→기간→세부→정렬)을 따른다.
function Seg<T extends string | number>({ opts, value, onChange }: { opts: { k: T; l: string }[]; value: T; onChange: (v: T) => void }) {
  return <div className="t2-fseg">{opts.map((o) => <button key={String(o.k)} className={o.k === value ? "on" : ""} onClick={() => onChange(o.k)}>{o.l}</button>)}</div>;
}
// 드롭다운(긴 목록용). open 상태는 바 단위로 하나만.
function Sel<T extends string | number>({ id, open, setOpen, opts, value, onChange, label }: { id: string; open: string | null; setOpen: (v: string | null) => void;
  opts: { k: T; l: string }[]; value: T; onChange: (v: T) => void; label?: string }) {
  const cur = opts.find((o) => o.k === value);
  return (
    <Dd id={id} open={open} setOpen={setOpen} label={cur?.l ?? label ?? ""} active={!!cur && opts[0].k !== value}>
      {opts.map((o) => <button key={String(o.k)} className={o.k === value ? "on" : ""} onClick={() => onChange(o.k)}>{o.l}</button>)}
    </Dd>
  );
}
function Bar_({ children, note }: { children: ReactNode; note?: ReactNode }) {
  return <div className="t2-sbar">{children}{note && <span className="t2-sbar-note">{note}</span>}</div>;
}
function Note({ children }: { children: ReactNode }) { return <p className="t2-snote">{children}</p>; }
function Empty({ loading, err, n }: { loading: boolean; err: boolean; n: number }) {
  if (loading) return <div className="t2-sload"><i /><i /><i /><i /></div>;
  if (err) return <p className="t2-sempty">불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.</p>;
  if (n === 0) return <p className="t2-sempty">이 조건에 맞는 자료가 없어요.</p>;
  return null;
}
function CxCell({ no, name, sub, onPick }: { no: string | null; name: string | null; sub?: string | null; onPick: (no: string, name: string) => void }) {
  return (
    <div className="t2-cx">
      {no ? <button onClick={() => onPick(no, name || no)}>{name ?? no}</button> : <span>{name ?? "-"}</span>}
      {sub && <small>{sub}</small>}
    </div>
  );
}
type PanelProps = { r: RegionSel; L: ReturnType<typeof useRegionLists>; onPick: (no: string, name: string) => void };

const TRADES3 = [{ k: "A1", l: "매매" }, { k: "B1", l: "전세" }, { k: "B2", l: "월세" }] as const;
const ASSETS3 = [{ k: "all", l: "아파트·오피" }, { k: "apt", l: "아파트" }, { k: "offi", l: "오피스텔" }] as const;
const ASSETS2 = [{ k: "apt", l: "아파트" }, { k: "offi", l: "오피스텔" }] as const;
const AREA_OPTS = AREA_CLASSES.map((a) => ({ k: a.code, l: a.name }));
const DAYS6 = [{ k: 7, l: "1주" }, { k: 30, l: "1개월" }, { k: 90, l: "3개월" }, { k: 180, l: "6개월" }, { k: 365, l: "1년" }, { k: 0, l: "전체" }];
const DAYS3 = [{ k: 180, l: "6개월" }, { k: 365, l: "1년" }, { k: 730, l: "2년" }];

// ── 실거래가 ──────────────────────────────────────────
function TopPrice({ r, onPick }: PanelProps) {
  const [trade, setTrade] = useState<"A1" | "B1" | "B2">("A1");
  const [asset, setAsset] = useState<"all" | "apt" | "offi">("all");
  const [area, setArea] = useState("all");
  const [days, setDays] = useState(30);
  const [dealing, setDealing] = useState<"all" | "broker" | "direct">("all");
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-top-price?days=${days}&trade=${trade}&asset=${asset}&dealing=${dealing}&area_class=${area}${rq(r)}&limit=100`);
  const items = q.data?.items ?? [];
  return (
    <>
      <Bar_>
        <Seg opts={[...TRADES3]} value={trade} onChange={setTrade} />
        <Seg opts={[...ASSETS3]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Sel id="days" open={open} setOpen={setOpen} opts={DAYS6} value={days} onChange={setDays} />
        {trade === "A1" && <Seg opts={[{ k: "all", l: "거래방식 전체" }, { k: "broker", l: "중개거래" }, { k: "direct", l: "직거래" }]} value={dealing} onChange={setDealing} />}
      </Bar_>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th>유형</th>{trade === "A1" && <th>거래</th>}<th>면적</th><th className="num">층</th><th className="num">준공</th>
            <th className="num">{trade === "B2" ? "월세" : "가격"}</th>{trade === "B2" && <th className="num">보증금</th>}<th className="num">거래일</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.deal_ymd}-${i}`}>
              <td className="n">{i + 1}</td>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={it.region_name} onPick={onPick} /></td>
              <td className="mut">{it.asset === "silv" ? "분양권" : it.asset === "offi" ? "오피" : "아파트"}</td>
              {trade === "A1" && <td className={it.dealing_gbn === "직거래" ? "warn" : "mut"}>{it.dealing_gbn ?? "-"}</td>}
              <td>{it.excl_use_ar ? areaLabel(it.excl_use_ar) : "-"}</td>
              <td className="num">{it.floor ?? "-"}</td><td className="num mut">{it.build_year ?? "-"}</td>
              <td className="num b">{trade === "B2" ? won((it.monthly_rent || 0) * 1e4) : won(it.price)}</td>
              {trade === "B2" && <td className="num">{won(it.price)}</td>}
              <td className="num mut">{it.deal_ymd}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

function RecordHigh({ r, onPick }: PanelProps) {
  const [trade, setTrade] = useState<"A1" | "B1" | "B2">("A1");
  const [asset, setAsset] = useState<"all" | "apt" | "offi">("all");
  const [area, setArea] = useState("all");
  const [days, setDays] = useState(90);
  const [gap, setGap] = useState(0);
  const [order, setOrder] = useState<"premium" | "recent">("premium");
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-record-high?days=${days}&trade=${trade}&asset=${asset}&area_class=${area}${rq(r)}&max_gap_months=${gap}&order=${order}&min_prior=1&limit=300`);
  const items = q.data?.items ?? [];
  const toWon = (v: number | null) => (v == null ? null : trade === "B2" ? v * 1e4 : v);
  return (
    <>
      <Bar_>
        <Seg opts={[...TRADES3]} value={trade} onChange={setTrade} />
        <Seg opts={[...ASSETS3]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Sel id="days" open={open} setOpen={setOpen} opts={[{ k: 30, l: "최근 1개월 신고가" }, { k: 90, l: "최근 3개월 신고가" }, { k: 180, l: "최근 6개월 신고가" }, { k: 365, l: "최근 1년 신고가" }]} value={days} onChange={setDays} />
        <Sel id="gap" open={open} setOpen={setOpen} opts={[{ k: 0, l: "경신 간격 전체" }, { k: 3, l: "3개월 안에 경신" }, { k: 6, l: "6개월 안에 경신" }, { k: 12, l: "1년 안에 경신" }]} value={gap} onChange={setGap} />
        <Seg opts={[{ k: "premium", l: "상승률 순" }, { k: "recent", l: "최신 순" }]} value={order} onChange={setOrder} />
      </Bar_>
      <Note>최근 {days}일 안에 새 신고가가 나온 단지·타입. 직전 최고가는 더 과거일 수 있어요. 경신 간격은 직전 신고가에서 새 신고가까지 걸린 시간.</Note>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th>타입</th><th className="num">{trade === "B2" ? "신고 월세" : "신고가"}</th><th className="num">직전 최고가</th><th className="num">상승률</th><th className="num">경신 간격</th><th className="num">거래수</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
              <td className="n">{i + 1}</td>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={`${it.region_name ?? ""}${it.asset === "silv" ? " · 분양권" : ""}`} onPick={onPick} /></td>
              <td>{areaLabel(it.area_key)}</td>
              <td className="num"><b className="up">{won(toWon(it.record_price))}</b>{it.floor != null && <small> {it.floor}층</small>}<small className="blk">{it.record_date}</small></td>
              <td className="num mut">{won(toWon(it.prev_high))}{it.prev_floor != null && <small> {it.prev_floor}층</small>}<small className="blk">{it.prev_date}</small></td>
              <td className="num b up">+{(it.premium * 100).toFixed(1)}%</td>
              <td className="num">{it.months_since != null ? `${it.months_since}개월` : "-"}</td>
              <td className="num mut">{it.n_total}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

function PyeongPrice({ r, onPick }: PanelProps) {
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [area, setArea] = useState("all");
  const [days, setDays] = useState(365);
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-pyeong-price?days=${days}&asset=${asset}&order=${order}&area_class=${area}${rq(r)}&min_samples=3&limit=200`);
  const items = q.data?.items ?? [];
  return (
    <>
      <Bar_>
        <Seg opts={[...ASSETS2]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Sel id="days" open={open} setOpen={setOpen} opts={DAYS3} value={days} onChange={setDays} />
        <Seg opts={[{ k: "desc", l: "비싼 순" }, { k: "asc", l: "싼 순" }]} value={order} onChange={setOrder} />
      </Bar_>
      <Note>거래가 ÷ 평(전용면적 기준). 단지·면적타입별 평균, 거래 3건 이상만.</Note>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th>면적타입</th><th className="num">평균 매매</th><th className="num">평당가</th><th className="num">거래수</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
              <td className="n">{i + 1}</td>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={it.region_name} onPick={onPick} /></td>
              <td>{areaLabel(it.area_key)}</td>
              <td className="num">{won(it.avg_price)}</td>
              <td className="num b">{won(it.pyeong_price)}<small>/평</small></td>
              <td className="num mut">{it.n}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

function PriceChange({ r, onPick }: PanelProps) {
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [area, setArea] = useState("all");
  const [win, setWin] = useState(90);
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-price-change?window_days=${win}&asset=${asset}&order=${order}&area_class=${area}${rq(r)}&min_samples=3&limit=200`);
  const items = q.data?.items ?? [];
  return (
    <>
      <Bar_>
        <Seg opts={[...ASSETS2]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Seg opts={[{ k: 30, l: "1개월 비교" }, { k: 90, l: "3개월 비교" }, { k: 180, l: "6개월 비교" }]} value={win} onChange={setWin} />
        <Seg opts={[{ k: "desc", l: "상승 순" }, { k: "asc", l: "하락 순" }]} value={order} onChange={setOrder} />
      </Bar_>
      <Note>최근 {win}일 평균가와 그 이전 {win}일 평균가 비교. 단지·면적타입별.</Note>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th>면적타입</th><th className="num">최근 평균</th><th className="num">이전 평균</th><th className="num">변동률</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
              <td className="n">{i + 1}</td>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={it.region_name} onPick={onPick} /></td>
              <td>{areaLabel(it.area_key)}</td>
              <td className="num">{won(it.recent_avg)}</td>
              <td className="num mut">{won(it.prev_avg)}</td>
              <td className={"num b " + sgn(it.change_rate)}>{pct(it.change_rate)}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

// 부동산타임머신 — 정책 연대기 + 전국 아파트 월별 거래량·평균가. 이벤트는 서버 큐레이션만.
const CAT_COLOR: Record<string, string> = { 강화: "#d23b3b", 완화: "#1268d3", 공급: "#159570", 거시: "#6b7a90", 제도: "#8250c8" };
function TimeMachine() {
  type Ev = { d: string; cat: string; title: string; desc: string; src: string };
  type Pt = { m: string; n: number; avg: number };
  const q = useQ<{ series: Pt[]; events: Ev[]; data_from: string | null }>("/stats/timemachine");
  const [sel, setSel] = useState<string | null>(null);
  const [cat, setCat] = useState("");
  const [span, setSpan] = useState(0);
  const chartRef = useRef<HTMLDivElement>(null);
  const full = q.data?.series ?? [];
  const series = span > 0 ? full.slice(-span) : full;
  const dataFrom = q.data?.data_from ?? "";
  const chartFrom = series[0]?.m ?? dataFrom;
  const events = useMemo(() => [...(q.data?.events ?? [])].sort((a, b) => b.d.localeCompare(a.d)), [q.data]);
  const inRange = (e: Ev) => dataFrom !== "" && e.d.slice(0, 7) >= dataFrom;
  const inChart = (e: Ev) => chartFrom !== "" && e.d.slice(0, 7) >= chartFrom;
  const byYear = useMemo(() => {
    const g = new Map<string, Ev[]>();
    for (const e of events) { if (cat && e.cat !== cat) continue; const y = e.d.slice(0, 4); (g.get(y) ?? g.set(y, []).get(y)!).push(e); }
    return [...g.entries()];
  }, [events, cat]);
  if (q.loading || !q.data) return <Empty loading={q.loading} err={q.err} n={1} />;
  const selEv = sel ? events.find((e) => e.d === sel) : null;
  const selPt = selEv ? series.find((p) => p.m === selEv.d.slice(0, 7)) : null;
  const prevPt = selPt ? series[series.indexOf(selPt) - 1] : null;
  const pick = (e: Ev) => {
    const next = e.d === sel ? null : e.d; setSel(next);
    if (next && inRange(e)) { if (!inChart(e)) setSpan(0); chartRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  };
  return (
    <>
      <Bar_ note={<>전국 아파트 매매 · 월별 거래량과 평균 거래가 · {dataFrom.replace("-", ".")}~ · 해제거래 제외 · 최근 1~2개월은 신고 진행 중</>}>
        <Seg opts={[{ k: 0, l: "전체" }, { k: 120, l: "10년" }, { k: 60, l: "5년" }, { k: 36, l: "3년" }]} value={span} onChange={setSpan} />
      </Bar_>
      <div ref={chartRef} className="t2-chart" style={{ height: 300 }}>
        <ResponsiveContainer>
          <ComposedChart data={series} margin={{ top: 22, right: 6, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#eef1f5" vertical={false} />
            <XAxis dataKey="m" tickFormatter={(m: string) => `${m.slice(2, 4)}.${m.slice(5, 7)}`} tick={{ fontSize: 11, fill: "#6b7280" }} minTickGap={26} axisLine={false} tickLine={false} />
            <YAxis yAxisId="n" tick={{ fontSize: 11, fill: "#6b7280" }} width={40} tickFormatter={(v: number) => `${Math.round(v / 1000)}천`} axisLine={false} tickLine={false} />
            <YAxis yAxisId="avg" orientation="right" tick={{ fontSize: 11, fill: "#6b7280" }} width={44} domain={["auto", "auto"]} tickFormatter={(v: number) => `${(v / 1e8).toFixed(1)}억`} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={TT} formatter={(v: any, name: any) => (name === "평균 거래가" ? [`${(Number(v) / 1e8).toFixed(1)}억`, name] : [`${Number(v).toLocaleString()}건`, name])} labelFormatter={(m: any) => `${String(m).replace("-", "년 ")}월`} />
            <Bar yAxisId="n" dataKey="n" name="거래량" fill="#b9d1f0" radius={[2, 2, 0, 0]} />
            <Line yAxisId="avg" dataKey="avg" name="평균 거래가" stroke="#d23b3b" strokeWidth={2} dot={false} />
            {(q.data.events ?? []).filter(inChart).map((e) => {
              const on = sel === e.d;
              return <ReferenceLine key={e.d} yAxisId="n" x={e.d.slice(0, 7)} stroke={CAT_COLOR[e.cat] ?? "#888"} strokeWidth={on ? 2.2 : 1} strokeDasharray={on ? undefined : "4 3"} opacity={on ? 1 : .7}
                label={{ value: `${parseInt(e.d.slice(5, 7), 10)}·${parseInt(e.d.slice(8, 10), 10)}`, position: "top", fontSize: on ? 12 : 10.5, fill: CAT_COLOR[e.cat] ?? "#888", fontWeight: on ? 800 : 600 }} />;
            })}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {selEv && (
        <div className="t2-tmsel">
          <b style={{ color: CAT_COLOR[selEv.cat] }}>{selEv.d.replace(/-/g, ".")} {selEv.title}</b> {selEv.desc}
          {selPt && <small>당월 전국 거래 {selPt.n.toLocaleString()}건{prevPt ? ` (전월 ${prevPt.n.toLocaleString()}건)` : ""} · 평균 {(selPt.avg / 1e8).toFixed(1)}억</small>}
          {!inRange(selEv) && <small>콕집 실거래 구간({dataFrom.replace("-", ".")}~) 이전이라 차트엔 표시되지 않아요.</small>}
        </div>
      )}
      <div className="t2-sh"><h3>연대기</h3>
        <Seg opts={[{ k: "", l: "전체" }, ...Object.keys(CAT_COLOR).map((c) => ({ k: c, l: c }))]} value={cat} onChange={setCat} />
      </div>
      {byYear.map(([year, evs]) => (
        <div key={year} className="t2-tmy">
          <h4>{year}</h4>
          {evs.map((e) => (
            <button key={e.d} className={"t2-tmev" + (sel === e.d ? " on" : "")} onClick={() => pick(e)}>
              <span className="d">{e.d.replace(/-/g, ".")}</span>
              <span className="c" style={{ color: CAT_COLOR[e.cat] }}>{e.cat}</span>
              <span className="t">{e.title}{inRange(e) && <i>차트</i>}</span>
              <span className="x">{e.desc} <em>· {e.src}</em></span>
            </button>
          ))}
        </div>
      ))}
      <Note>이벤트는 정부·한국은행 등 공식 발표(발표일 기준)만 수록했고 시장 해석은 담지 않아요. 거래량·평균가는 국토교통부 실거래 신고를 콕집이 집계한 것.</Note>
    </>
  );
}

const SIDO_SHORT: { k: string; l: string }[] = [
  { k: "", l: "전국" }, { k: "11", l: "서울" }, { k: "41", l: "경기" }, { k: "28", l: "인천" }, { k: "26", l: "부산" }, { k: "27", l: "대구" }, { k: "29", l: "광주" }, { k: "46", l: "전남" },
  { k: "30", l: "대전" }, { k: "31", l: "울산" }, { k: "36", l: "세종" }, { k: "43", l: "충북" }, { k: "44", l: "충남" }, { k: "52", l: "전북" }, { k: "47", l: "경북" }, { k: "48", l: "경남" }, { k: "51", l: "강원" }, { k: "50", l: "제주" },
];
function Pager({ offset, total, limit, onOffset }: { offset: number; total: number; limit: number; onOffset: (o: number) => void }) {
  const page = Math.floor(offset / limit) + 1, pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="t2-pager">
      <button disabled={offset === 0} onClick={() => onOffset(Math.max(0, offset - limit))}>이전</button>
      <span>{page} / {pages} · {total.toLocaleString()}건</span>
      <button disabled={page >= pages} onClick={() => onOffset(offset + limit)}>다음</button>
    </div>
  );
}
function Cancelled({ r, onPick }: PanelProps) {
  const [asset, setAsset] = useState<"apt" | "offi" | "all">("apt");
  const [months, setMonths] = useState(3);
  const [dealing, setDealing] = useState<"" | "중개거래" | "직거래">("");
  const [offset, setOffset] = useState(0);
  const sido = r.sido.slice(0, 2);
  useEffect(() => setOffset(0), [asset, months, dealing, sido]);
  const base = `asset=${asset}&months=${months}${sido ? `&sido=${sido}` : ""}`;
  const s = useQ<any>(`/stats/cancelled-summary?${base}`);
  const q = useQ<{ total: number; items: any[] }>(`/stats/cancelled-transactions?${base}&limit=50&offset=${offset}${dealing ? `&dealing=${encodeURIComponent(dealing)}` : ""}`);
  const items = q.data?.items ?? [];
  const BADGE: Record<string, string> = { double: "이중신고 취소", correction: "금액정정 신고", plain: "취소" };
  return (
    <>
      <Bar_>
        <Seg opts={[{ k: "", l: "거래 전체" }, { k: "중개거래", l: "중개거래" }, { k: "직거래", l: "직거래" }]} value={dealing} onChange={setDealing} />
        <Seg opts={[{ k: "apt", l: "아파트" }, { k: "offi", l: "오피스텔" }, { k: "all", l: "전체" }]} value={asset} onChange={setAsset} />
        <Seg opts={[{ k: 1, l: "1달" }, { k: 3, l: "3달" }, { k: 6, l: "6달" }, { k: 0, l: "최대" }]} value={months} onChange={setMonths} />
      </Bar_>
      <Note>국토부 신고 뒤 해제(취소)된 거래, 해제일 기준. 같은 호실·계약일에 살아 있는 신고가 또 있으면 이중신고 취소(금액 같음) 또는 금액정정 신고(금액 다름)로 구분해요. 지역은 시·도까지만 걸러요.</Note>
      {s.data && (
        <div className="t2-kpis">
          <div><span>전체</span><b>{num(s.data.total)}</b></div><div><span>중개거래</span><b>{num(s.data.n_junggae)}</b></div><div><span>직거래</span><b>{num(s.data.n_jikgeo)}</b></div>
          <div><span>이중신고 취소</span><b>{num(s.data.n_double)}</b></div><div><span>금액정정 신고</span><b>{num(s.data.n_correction)}</b></div><div><span>단순 취소</span><b>{num(s.data.n_plain)}</b></div>
        </div>
      )}
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <>
          <table className="t2-tbl">
            <thead><tr><th>구분</th><th>거래</th><th>단지</th><th>면적</th><th className="num">층</th><th>등기</th><th className="num">거래금액</th><th className="num">계약일</th><th className="num">해제일</th></tr></thead>
            <tbody>{items.map((x, i) => (
              <tr key={`${x.name}-${x.deal_ymd}-${i}`}>
                <td className={x.cancel_type === "plain" ? "up" : "mut"}>{BADGE[x.cancel_type] ?? x.cancel_type}</td>
                <td className={x.dealing_gbn === "직거래" ? "warn" : "mut"}>{x.dealing_gbn ?? "-"}</td>
                <td><CxCell no={x.complex_no} name={x.name} sub={`${x.region}${x.asset === "offi" ? " · 오피" : ""}`} onPick={onPick} /></td>
                <td>{x.excl_use_ar != null ? areaLabel(x.excl_use_ar) : "-"}</td>
                <td className="num">{x.floor ?? "-"}</td>
                <td className="mut">{x.asset === "offi" ? "-" : x.registered ? `등기완료${x.dong ? ` ${x.dong}${String(x.dong).endsWith("동") ? "" : "동"}` : ""}` : "미등기"}</td>
                <td className="num b">{won(x.deal_amount)}</td>
                <td className="num mut">{x.deal_ymd}</td><td className="num mut">{x.cdeal_date ?? "-"}</td>
              </tr>
            ))}</tbody>
          </table>
          <Pager offset={offset} total={q.data?.total ?? 0} limit={50} onOffset={setOffset} />
        </>
      )}
    </>
  );
}

// ── 매물호가추이 ──────────────────────────────────────
const TT = { fontSize: 12, border: "1px solid #e3e8ee", borderRadius: 4, boxShadow: "none", padding: "6px 10px" };
function HogaSummary({ r, L }: PanelProps) {
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const qs = rq(r, "dong");
  const s = useQ<any>(`/stats/changes/summary?asset=${asset}${qs}`);
  const t = useQ<{ series: any[] }>(`/stats/avg-price-trend?days=60&asset=${asset}${qs}`);
  const [vis, setVis] = useState<Record<string, boolean>>({ A1: true, B1: true, B2: true, B2R: false });
  const LINES = [{ k: "A1", l: "매매", c: "#d23b3b", ax: "sale" }, { k: "B1", l: "전세", c: "#1268d3", ax: "rent" }, { k: "B2", l: "월세 보증금", c: "#1f9d63", ax: "rent" }, { k: "B2R", l: "월세", c: "#d97706", ax: "wol" }];
  const d = s.data;
  const prevL = d?.prev_is_yesterday === false ? "직전" : "전일";
  const series = t.data?.series ?? [];
  const showWol = vis.B2R;
  const dom = [(min: number) => Math.floor(min * 0.85), (max: number) => Math.ceil(max * 1.15)] as any;
  const Kpi = ({ l, v, ch, cnt, units }: { l: string; v: number | null; ch: number | null; cnt?: number; units?: number | null }) => (
    <div><span>{l}</span><b>{won(v)}</b>
      <em className={sgn(ch)}>{ch == null ? `${prevL} 대비 -` : `${ch > 0 ? "▲" : ch < 0 ? "▼" : ""} ${Math.abs(ch * 100).toFixed(1)}% ${prevL}`}</em>
      {cnt != null && <small>매물 {cnt.toLocaleString()}{units ? ` · 실매물 ${units.toLocaleString()}` : ""}</small>}
    </div>
  );
  return (
    <>
      <Bar_ note={d?.latest_date ? `${regionLabel(r, L)} · 기준 ${d.latest_date}` : undefined}>
        <Seg opts={[...ASSETS2]} value={asset} onChange={setAsset} />
      </Bar_>
      {d && (
        <div className="t2-kpis big">
          <div><span>매물 수</span><b>{num(d.total)}</b><em className="mut">단지 {num(d.complex_count)}곳</em>{d.total_units ? <small>실매물 {num(d.total_units)} · 1채당 광고 {(d.total / d.total_units).toFixed(1)}</small> : null}</div>
          <Kpi l="매매 평균" v={d.trades.A1?.avg_price} ch={d.trades.A1?.avg_change} cnt={d.trades.A1?.count} units={d.trades.A1?.units} />
          <Kpi l="전세 평균" v={d.trades.B1?.avg_price} ch={d.trades.B1?.avg_change} cnt={d.trades.B1?.count} units={d.trades.B1?.units} />
          <Kpi l="월세 보증금 평균" v={d.trades.B2?.avg_price} ch={d.trades.B2?.avg_change} cnt={d.trades.B2?.count} units={d.trades.B2?.units} />
          <Kpi l="월세 평균" v={d.trades.B2?.rent_avg} ch={d.trades.B2?.rent_change} />
        </div>
      )}
      <div className="t2-sh"><h3>매물 평균 호가 추이 <small>최근 60일 · 단지·면적타입 평균을 매물 수로 가중</small></h3>
        <div className="t2-fseg">{LINES.map((l) => <button key={l.k} className={vis[l.k] ? "on" : ""} style={vis[l.k] ? { color: l.c } : undefined} onClick={() => setVis({ ...vis, [l.k]: !vis[l.k] })}>{l.l}</button>)}</div>
      </div>
      {t.loading && <Empty loading err={false} n={1} />}
      {series.length > 1 && (vis.A1 || vis.B1 || vis.B2) && (
        <div className="t2-chart" style={{ height: 240 }}>
          <ResponsiveContainer>
            <LineChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#eef1f5" vertical={false} />
              <XAxis dataKey="snapshot_date" tick={{ fontSize: 11, fill: "#6b7280" }} tickFormatter={(x: string) => x.slice(5)} axisLine={false} tickLine={false} minTickGap={24} />
              <YAxis yAxisId="sale" hide={!vis.A1} tick={{ fontSize: 11, fill: "#d23b3b" }} width={48} domain={dom} tickFormatter={wonS} axisLine={false} tickLine={false} />
              <YAxis yAxisId="rent" orientation="right" hide={!vis.B1 && !vis.B2} tick={{ fontSize: 11, fill: "#1268d3" }} width={48} domain={dom} tickFormatter={wonS} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TT} formatter={(v: any, n: any) => [v == null ? "-" : won(Number(v)), LINES.find((l) => l.k === n)?.l ?? n]} />
              {vis.A1 && <Line yAxisId="sale" type="monotone" dataKey="A1" stroke="#d23b3b" strokeWidth={2} dot={false} connectNulls />}
              {vis.B1 && <Line yAxisId="rent" type="monotone" dataKey="B1" stroke="#1268d3" strokeWidth={2} dot={false} connectNulls />}
              {vis.B2 && <Line yAxisId="rent" type="monotone" dataKey="B2" stroke="#1f9d63" strokeWidth={2} dot={false} connectNulls />}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {series.length > 1 && showWol && (
        <div className="t2-chart" style={{ height: 160 }}>
          <ResponsiveContainer>
            <LineChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="#eef1f5" vertical={false} />
              <XAxis dataKey="snapshot_date" tick={{ fontSize: 11, fill: "#6b7280" }} tickFormatter={(x: string) => x.slice(5)} axisLine={false} tickLine={false} minTickGap={24} />
              <YAxis tick={{ fontSize: 11, fill: "#d97706" }} width={48} domain={["auto", "auto"]} tickFormatter={wonS} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={TT} formatter={(v: any) => [v == null ? "-" : won(Number(v)), "월세"]} />
              <Line type="monotone" dataKey="B2R" stroke="#d97706" strokeWidth={2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <Note>실매물은 같은 집을 여러 중개업소가 올린 중복 광고를 1건으로 합친 수. 1채당 광고가 높을수록 한 집이 여러 곳에 나와 있어요.</Note>
    </>
  );
}

function HogaRank({ r }: PanelProps) {
  const [trade, setTrade] = useState<"A1" | "B1" | "B2">("A1");
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [area, setArea] = useState("all");
  const def: "sido" | "sigungu" | "dong" = r.sgg ? "dong" : r.sido ? "sigungu" : "sido";
  const [level, setLevel] = useState(def);
  useEffect(() => setLevel(def), [def]);
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[]; prev_is_yesterday?: boolean }>(`/stats/changes/region-rank?level=${level}&trade=${trade}&asset=${asset}${rq(r, "sgg")}&area_class=${area}&min_listings=30&limit=30`);
  const items = q.data?.items ?? [];
  const max = Math.max(1, ...items.map((i) => i.avg_price));
  const cmp = q.data?.prev_is_yesterday === false ? "직전 대비" : "전일 대비";
  return (
    <>
      <Bar_>
        <Seg opts={[...TRADES3]} value={trade} onChange={setTrade} />
        <Seg opts={[{ k: "sido", l: "시·도 단위" }, { k: "sigungu", l: "시·군·구 단위" }, { k: "dong", l: "동 단위" }]} value={level} onChange={setLevel} />
        <Seg opts={[...ASSETS2]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
      </Bar_>
      <Note>지역별 평균 매물 호가 순위. 매물 30건 이상인 지역만.</Note>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>지역</th><th className="num">평균 호가</th><th className="num">{cmp}</th><th className="num">매물</th><th className="num">실매물</th><th className="num">1채당 광고</th><th className="num">단지</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={it.region_code}>
              <td className="n">{i + 1}</td>
              <td className="barcell"><i style={{ width: `${(it.avg_price / max) * 100}%`, background: trade === "A1" ? "rgba(210,59,59,.09)" : "rgba(18,104,211,.09)" }} /><span>{it.region_name ?? it.region_code}</span></td>
              <td className="num b">{won(it.avg_price)}</td>
              <td className={"num " + sgn(it.change)}>{pct(it.change)}</td>
              <td className="num">{num(it.listings)}</td><td className="num">{num(it.units)}</td>
              <td className="num">{it.units ? (it.listings / it.units).toFixed(2) : "-"}</td>
              <td className="num mut">{num(it.complexes)}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

function HogaMovers({ r, onPick }: PanelProps) {
  const [trade, setTrade] = useState<"A1" | "B1" | "B2">("A1");
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [days, setDays] = useState("7");
  const q = useQ<{ up: any[]; down: any[]; from_date?: string; to_date?: string }>(`/stats/changes/movers?trade=${trade}&asset=${asset}${rq(r, "sgg")}&days=${days}&min_listings=5&limit=10`);
  const period = q.data?.from_date && q.data?.to_date ? `${q.data.from_date.slice(5).replace("-", ".")} → ${q.data.to_date.slice(5).replace("-", ".")}` : "";
  const T = ({ title, items, cls }: { title: string; items: any[]; cls: string }) => (
    <div className="t2-half">
      <h3 className={cls}>{title}</h3>
      {items.length === 0 ? <p className="t2-sempty">자료 없음</p> : (
        <table className="t2-tbl">
          <thead><tr><th>단지</th><th>면적</th><th className="num">변동</th><th className="num">현재</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.area_name}-${i}`}>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={`${it.region_name ?? ""}${it.complex_listings ? ` · 매물 ${it.complex_listings.toLocaleString()}` : ""}`} onPick={onPick} /></td>
              <td>{it.area_name ?? "-"}㎡</td>
              <td className={"num b " + cls}>{pct(it.rate)}</td>
              <td className="num">{won(it.new_avg)}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
  return (
    <>
      <Bar_ note={period ? `${period} 매물 평균가 비교` : undefined}>
        <Seg opts={[...TRADES3]} value={trade} onChange={setTrade} />
        <Seg opts={[...ASSETS2]} value={asset} onChange={setAsset} />
        <Seg opts={[{ k: "7", l: "1주" }, { k: "14", l: "2주" }, { k: "30", l: "1개월" }]} value={days} onChange={setDays} />
      </Bar_>
      <Note>단지·면적타입별 매물 평균가 변동. 들어오고 나간 매물이 바뀌어도 평균이 움직일 수 있어 참고용이에요.</Note>
      <Empty loading={q.loading} err={q.err} n={1} />
      {q.data && <div className="t2-cols"><T title="상승" items={q.data.up} cls="up" /><T title="하락" items={q.data.down} cls="down" /></div>}
    </>
  );
}

function ListingCounts() {
  const [asset, setAsset] = useState<"apt" | "offi" | "all">("apt");
  const [basis, setBasis] = useState<"ads" | "units">("ads");
  const q = useQ<any>(`/stats/listing-counts?asset=${asset}`);
  const t = useQ<{ series: any[] }>("/stats/listing-trend?days=60");
  const nat = q.data?.national;
  const regions: any[] = (q.data?.regions ?? []).slice().sort((a: any, b: any) => sidoRank(a.sido_code) - sidoRank(b.sido_code));
  const TR = [{ k: "A1", l: "매매", c: "#d23b3b" }, { k: "B1", l: "전세", c: "#1268d3" }, { k: "B2", l: "월세", c: "#1f9d63" }];
  const D = ({ cur, base }: { cur: number; base: number }) => { if (!base) return <>-</>; const d = cur - base; return <span className={sgn(d)}>{d === 0 ? "±0" : `${d > 0 ? "▲" : "▼"}${Math.abs(d).toLocaleString()}`}</span>; };
  return (
    <>
      <Bar_ note={q.data?.as_of ? `기준 ${q.data.as_of}` : undefined}>
        <Seg opts={[{ k: "apt", l: "아파트" }, { k: "offi", l: "오피스텔" }, { k: "all", l: "아파트·오피" }]} value={asset} onChange={setAsset} />
        <Seg opts={[{ k: "ads", l: "광고 건수" }, { k: "units", l: "실매물" }]} value={basis} onChange={setBasis} />
      </Bar_>
      <Empty loading={q.loading} err={q.err} n={nat ? 1 : 0} />
      {nat && (
        <>
          <div className="t2-kpis big">
            <div><span>전국 매물</span><b>{num(nat.total)}</b><em className="mut">실매물 {num(nat.total_u)}{nat.total_u > 0 ? ` · 광고배율 ×${(nat.total / nat.total_u).toFixed(1)}` : ""}</em><small>전일 <D cur={nat.total} base={nat.prev_total} /> · 7일 <D cur={nat.total} base={nat.week_total} /></small></div>
            {TR.map((x) => <div key={x.k}><span style={{ color: x.c }}>{x.l}</span><b>{num(nat[x.k])}</b><em className="mut">실매물 {num(nat[`${x.k}_u`])}</em></div>)}
          </div>
          {t.data && t.data.series.length > 1 && (
            <>
              <div className="t2-sh"><h3>전국 매물수 추이 <small>최근 60일 · {basis === "ads" ? "광고 건수" : "실매물"}</small></h3></div>
              <div className="t2-chart" style={{ height: 200 }}>
                <ResponsiveContainer>
                  <LineChart data={t.data.series} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid stroke="#eef1f5" vertical={false} />
                    <XAxis dataKey="snapshot_date" tick={{ fontSize: 11, fill: "#6b7280" }} tickFormatter={(x: string) => x.slice(5)} axisLine={false} tickLine={false} minTickGap={28} />
                    <YAxis tick={{ fontSize: 11, fill: "#6b7280" }} width={44} tickFormatter={(v: number) => (v >= 1e4 ? `${Math.round(v / 1e4)}만` : v.toLocaleString())} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={TT} formatter={(v: any, n: any) => [Number(v ?? 0).toLocaleString(), TR.find((x) => x.k === String(n).replace("_u", ""))?.l ?? n]} />
                    {TR.map((x) => <Line key={x.k} type="monotone" dataKey={basis === "ads" ? x.k : `${x.k}_u`} stroke={x.c} strokeWidth={2} dot={false} connectNulls />)}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
          <div className="t2-sh"><h3>시·도별 <small>광고배율 = 광고 ÷ 실매물, 높을수록 매도 경쟁이 심해요</small></h3></div>
          <table className="t2-tbl">
            <thead><tr><th>지역</th><th className="num">매매</th><th className="num">전세</th><th className="num">월세</th><th className="num">전체(광고)</th><th className="num">실매물</th><th className="num">광고배율</th><th className="num">전일</th><th className="num">7일</th></tr></thead>
            <tbody>
              {[nat, ...regions].map((x: any, i: number) => (
                <tr key={x.sido_code ?? "nat"} className={i === 0 ? "sum" : ""}>
                  <td className="b">{i === 0 ? "전국" : SIDO_SHORT.find((s) => s.k === String(x.sido_code).slice(0, 2))?.l || x.sido_name}</td>
                  <td className="num">{num(x.A1)}</td><td className="num">{num(x.B1)}</td><td className="num">{num(x.B2)}</td>
                  <td className="num b">{num(x.total)}</td><td className="num">{num(x.total_u)}</td>
                  <td className="num">{x.total_u > 0 ? `×${(x.total / x.total_u).toFixed(1)}` : "-"}</td>
                  <td className="num"><D cur={x.total} base={x.prev_total} /></td><td className="num"><D cur={x.total} base={x.week_total} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <Note>광고 건수 = 노출 중인 광고 수 · 실매물 = 같은 집의 중복 광고를 하나로 합친 수 · 단지형(아파트·오피스텔) 기준 · 매일 수집.</Note>
        </>
      )}
    </>
  );
}

// ── 시장흐름 ──────────────────────────────────────────
const UNITS = [{ k: "day", l: "일별", d: "최근 60일" }, { k: "week", l: "주간", d: "최근 52주" }, { k: "month", l: "월별", d: "최근 36개월" }, { k: "quarter", l: "분기별", d: "최근 20분기" }, { k: "year", l: "연도별", d: "전체" }];
const VASSETS = [{ k: "apt", l: "아파트" }, { k: "offi", l: "오피스텔" }, { k: "silv", l: "분양권" }, { k: "villa", l: "빌라" }, { k: "house", l: "단독" }, { k: "nrg", l: "상가·사무실" }];
function bucketEnd(period: string, u: string): Date {
  if (u === "day") return new Date(period + "T23:59:59");
  if (u === "month") { const [y, m] = period.split("-").map(Number); return new Date(y, m, 0, 23, 59, 59); }
  if (u === "quarter") { const [y, q] = period.split("-Q").map(Number); return new Date(y, q * 3, 0, 23, 59, 59); }
  if (u === "year") return new Date(Number(period), 11, 31, 23, 59, 59);
  const [y, w] = period.split("-W").map(Number); const jan1 = new Date(y, 0, 1);
  return new Date(jan1.getTime() + ((w * 7 + (7 - jan1.getDay())) % 400) * 86400000 + 6 * 86400000);
}
const filing = (p: string, u: string) => { try { return bucketEnd(p, u).getTime() >= Date.now() - 30 * 86400000; } catch { return false; } };
function Volume({ r, L }: PanelProps) {
  const [unit, setUnit] = useState("month");
  const [asset, setAsset] = useState("apt");
  const [open, setOpen] = useState<string | null>(null);
  const p = new URLSearchParams({ unit, asset });
  if (r.sgg) p.set("sigungu", r.sgg.slice(0, 5)); else if (r.sido) p.set("sido", r.sido.slice(0, 2));
  const q = useQ<{ items: { period: string; count: number; avg_amt: number | null }[] }>(`/stats/tx-region-series?${p}`);
  const items = q.data?.items ?? [];
  const last = items[items.length - 1];
  const start = items.find((it) => filing(it.period, unit))?.period;
  const isDay = unit === "day";
  const sun = (ymd: string) => new Date(ymd + "T00:00:00").getDay() === 0;
  const u = UNITS.find((x) => x.k === unit)!;
  return (
    <>
      <Bar_ note={<>{regionLabel({ ...r, dong: "" }, L)} {VASSETS.find((a) => a.k === asset)?.l} · {u.d}{last && <> · 최신 {last.period} <b>{last.count.toLocaleString()}건</b></>}</>}>
        <Seg opts={UNITS} value={unit} onChange={setUnit} />
        <Sel id="asset" open={open} setOpen={setOpen} opts={VASSETS} value={asset} onChange={setAsset} />
      </Bar_>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <>
          <div className="t2-chart" style={{ height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={items} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="#eef1f5" vertical={false} />
                <XAxis dataKey="period" tick={{ fontSize: 10.5, fill: "#6b7280" }} minTickGap={18} axisLine={false} tickLine={false} tickFormatter={(v: string) => (unit === "day" ? v.slice(5) : unit === "month" ? v.slice(2) : v)} />
                <YAxis tick={{ fontSize: 10.5, fill: "#6b7280" }} width={48} tickFormatter={(v: number) => v.toLocaleString()} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TT} formatter={(v: any) => [`${Number(v).toLocaleString()}건`, "거래량"]} />
                {start && last && <ReferenceArea x1={start} x2={last.period} fill="#f2b25c" fillOpacity={0.12} label={{ value: "신고 진행 중", position: "insideTopRight", fill: "#b45309", fontSize: 11, fontWeight: 700 }} />}
                <Bar dataKey="count" fill="#1268d3" radius={[2, 2, 0, 0]}>
                  {isDay && items.map((it) => <Cell key={it.period} fill={sun(it.period) ? "#d23b3b" : "#1268d3"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="t2-tbl">
            <thead><tr><th>기간</th><th className="num">거래량</th><th className="num">평균가</th><th className="num">전기 대비</th></tr></thead>
            <tbody>{items.slice().reverse().map((it, i, arr) => {
              const prev = arr[i + 1]; const chg = prev && prev.count > 0 ? (it.count - prev.count) / prev.count : null;
              return (
                <tr key={it.period}>
                  <td className={isDay && sun(it.period) ? "up" : ""}>{it.period}{isDay && sun(it.period) ? " (일)" : ""}{filing(it.period, unit) && <small className="tag">신고중</small>}</td>
                  <td className="num b">{it.count.toLocaleString()}</td>
                  <td className="num">{wonS(it.avg_amt)}</td>
                  <td className={"num " + sgn(chg)}>{pct(chg)}</td>
                </tr>
              );
            })}</tbody>
          </table>
          <Note>해제거래 제외. 음영·신고중은 계약 후 30일 신고기간에 걸친 구간이라 수치가 아직 늘어나요. 지역은 시·군·구까지만 걸러요.</Note>
        </>
      )}
    </>
  );
}

function Pulse() {
  const [asset, setAsset] = useState("apt");
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<any>(`/stats/tx-region-pulse?asset=${asset}`);
  const c = useQ<{ items: { sido_code: string; avg59: number | null; avg84: number | null }[] }>(asset === "apt" || asset === "offi" || asset === "all" ? "/stats/region-compare?days=30&trade=A1" : null);
  const avg = new Map((c.data?.items ?? []).map((x) => [x.sido_code, x]));
  const d = q.data;
  const mon = (s: string) => { const m = /^\d{4}-(\d{2})$/.exec(s); return m ? `${Number(m[1])}월` : s; };
  const rows: any[] = d ? [d.national, ...(d.regions as any[]).slice().sort((a, b) => sidoRank(a.region_code) - sidoRank(b.region_code))] : [];
  const kp = asset === "apt" || asset === "offi" || asset === "all";
  const P = ({ v, a }: { v: number | null; a: number | null }) => <td className={"num " + sgn(v)}>{v == null ? "-" : `${v > 0 ? "▲" : "▼"}${Math.abs(v * 100).toFixed(1)}%`}<small className="blk mut">{num(a)}</small></td>;
  return (
    <>
      <Bar_ note={d ? `${d.as_of} 기준 · 최근 적재 ${d.filed_date}` : undefined}>
        <Sel id="asset" open={open} setOpen={setOpen} opts={[{ k: "apt", l: "아파트" }, { k: "offi", l: "오피스텔" }, { k: "all", l: "아파트·오피" }, { k: "villa", l: "빌라" }, { k: "house", l: "단독" }, { k: "nrg", l: "상가·사무실" }, { k: "silv", l: "분양권" }]} value={asset} onChange={setAsset} />
      </Bar_>
      <Note>오늘 국토부에 새로 신고 접수된 건수와 이번 달·지난달 누적, 월말 예측. 전년동월·3년평균 대비는 이번 달 예측 기준.</Note>
      <Empty loading={q.loading} err={q.err} n={rows.length} />
      {d && (
        <table className="t2-tbl">
          <thead><tr><th>지역</th><th className="num">오늘 신고접수</th>{kp && <th className="num">59㎡ · 84㎡ 평균</th>}<th className="num">{mon(d.prev_month)} 누적 / 예측</th><th className="num">{mon(d.current_month)} 누적 / 예측</th><th className="num">전년동월</th><th className="num">3년평균</th></tr></thead>
          <tbody>{rows.map((x, i) => {
            const a = avg.get(x.region_code);
            return (
              <tr key={x.region_code} className={i === 0 ? "sum" : ""}>
                <td className="b">{x.region_name}</td>
                <td className="num"><b>{num(x.filed_total)}</b><small className="blk mut">{mon(d.current_month)} {num(x.filed_current)} · {mon(d.prev_month)} {num(x.filed_prev)}</small></td>
                {kp && <td className="num">{a ? `${wonS(a.avg59)} · ${wonS(a.avg84)}` : "-"}</td>}
                <td className="num">{num(x.prev_month_count)} <span className="mut">/ {num(x.prev_month_pred)}</span></td>
                <td className="num">{num(x.current_month_count)} <span className="mut">/ {num(x.current_month_pred)}</span></td>
                <P v={x.yoy_cur_change} a={x.yoy_cur_actual} /><P v={x.avg3y_cur_change} a={x.avg3y_cur_actual} />
              </tr>
            );
          })}</tbody>
        </table>
      )}
    </>
  );
}

function TopVolume({ r, onPick }: PanelProps) {
  const [trade, setTrade] = useState<"A1" | "B1" | "B2">("A1");
  const [asset, setAsset] = useState<"all" | "apt" | "offi">("all");
  const [area, setArea] = useState("all");
  const [days, setDays] = useState(30);
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-top-volume?days=${days}&trade=${trade}&asset=${asset}&dealing=all&area_class=${area}${rq(r)}&limit=100`);
  const items = q.data?.items ?? [];
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <>
      <Bar_>
        <Seg opts={[...TRADES3]} value={trade} onChange={setTrade} />
        <Seg opts={[...ASSETS3]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Sel id="days" open={open} setOpen={setOpen} opts={DAYS6} value={days} onChange={setDays} />
      </Bar_>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th className="num">세대</th><th className="num">거래수</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={it.complex_no ?? i}>
              <td className="n">{i + 1}</td>
              <td className="barcell"><i style={{ width: `${(it.count / max) * 100}%` }} /><CxCell no={it.complex_no} name={it.complex_name} sub={it.region_name} onPick={onPick} /></td>
              <td className="num mut">{num(it.households)}</td>
              <td className="num b">{it.count.toLocaleString()}{!!it.silv_count && <small className="blk mut">분양권 {it.silv_count.toLocaleString()}</small>}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

function Turnover({ r, onPick }: PanelProps) {
  const [trade, setTrade] = useState<"A1" | "B1">("A1");
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [area, setArea] = useState("all");
  const [days, setDays] = useState(365);
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-turnover?days=${days}&trade=${trade}&asset=${asset}&area_class=${area}${rq(r)}&min_households=50&limit=200`);
  const items = q.data?.items ?? [];
  return (
    <>
      <Bar_>
        <Seg opts={[{ k: "A1", l: "매매" }, { k: "B1", l: "전세" }]} value={trade} onChange={setTrade} />
        <Seg opts={[...ASSETS2]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Sel id="days" open={open} setOpen={setOpen} opts={DAYS3} value={days} onChange={setDays} />
      </Bar_>
      <Note>거래량 ÷ 세대수. 손바뀜이 잦은 단지일수록 높아요. 50세대 이상만.</Note>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th className="num">세대수</th><th className="num">거래수</th><th className="num">회전율</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={it.complex_no ?? i}>
              <td className="n">{i + 1}</td>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={it.region_name} onPick={onPick} /></td>
              <td className="num mut">{num(it.households)}</td><td className="num">{num(it.tx_count)}</td>
              <td className="num b">{(it.turnover_rate * 100).toFixed(1)}%</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

// ── 투자분석 ──────────────────────────────────────────
function GapRank({ r, onPick }: PanelProps) {
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [area, setArea] = useState("all");
  const [days, setDays] = useState(365);
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-gap-rank?days=${days}&asset=${asset}&order=${order}&area_class=${area}${rq(r)}&min_samples=3&limit=200`);
  const items = q.data?.items ?? [];
  return (
    <>
      <Bar_>
        <Seg opts={[...ASSETS2]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Sel id="days" open={open} setOpen={setOpen} opts={DAYS3} value={days} onChange={setDays} />
        <Seg opts={[{ k: "asc", l: "갭 작은 순" }, { k: "desc", l: "갭 큰 순" }]} value={order} onChange={setOrder} />
      </Bar_>
      <Note>같은 단지·면적타입의 평균 매매가 − 평균 전세가 = 갭. 작을수록 적은 돈으로 살 수 있어요.</Note>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th>면적타입</th><th className="num">평균 매매</th><th className="num">평균 전세</th><th className="num">갭</th><th className="num">전세가율</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
              <td className="n">{i + 1}</td>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={it.region_name} onPick={onPick} /></td>
              <td>{areaLabel(it.area_key)}</td>
              <td className="num">{won(it.avg_sale)}</td><td className="num">{won(it.avg_jeonse)}</td>
              <td className="num b">{won(it.gap)}</td>
              <td className="num down">{(it.jeonse_rate * 100).toFixed(1)}%</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

function Yield({ r, onPick }: PanelProps) {
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [area, setArea] = useState("all");
  const [days, setDays] = useState(365);
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-yield?days=${days}&asset=${asset}&area_class=${area}${rq(r, "sido")}&min_samples=3&limit=200`);
  const items = q.data?.items ?? [];
  return (
    <>
      <Bar_>
        <Seg opts={[...ASSETS2]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Sel id="days" open={open} setOpen={setOpen} opts={DAYS3} value={days} onChange={setDays} />
      </Bar_>
      <Note>연 월세(월세 × 12) ÷ 평균 매매가 = 명목 임대수익률. 단지·면적타입별. 지역은 시·도까지만 걸러요.</Note>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th>면적타입</th><th className="num">세대</th><th className="num">매매</th><th className="num">보증금</th><th className="num">월세</th><th className="num">수익률</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
              <td className="n">{i + 1}</td>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={it.region_name} onPick={onPick} /></td>
              <td>{areaLabel(it.area_key)}</td>
              <td className="num mut">{num(it.households)}</td>
              <td className="num">{won(it.avg_sale)}</td><td className="num">{won(it.avg_deposit)}</td><td className="num">{((it.avg_monthly || 0) / 1e4).toFixed(0)}만</td>
              <td className="num b">{(it.yield_rate * 100).toFixed(2)}%</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

function LowPrice({ onPick }: PanelProps) {
  const [asset, setAsset] = useState<"all" | "apt" | "offi">("all");
  const [area, setArea] = useState("all");
  const [days, setDays] = useState(180);
  const [disc, setDisc] = useState(0.2);
  const [open, setOpen] = useState<string | null>(null);
  const q = useQ<{ items: any[] }>(`/stats/tx-low-price?days=${days}&asset=${asset}&discount=${disc}&area_class=${area}&min_samples=3&limit=300`);
  const items = q.data?.items ?? [];
  return (
    <>
      <Bar_>
        <Seg opts={[...ASSETS3]} value={asset} onChange={setAsset} />
        <Sel id="area" open={open} setOpen={setOpen} opts={AREA_OPTS} value={area} onChange={setArea} />
        <Sel id="days" open={open} setOpen={setOpen} opts={[{ k: 90, l: "3개월" }, { k: 180, l: "6개월" }, { k: 365, l: "1년" }, { k: 730, l: "2년" }]} value={days} onChange={setDays} />
        <Seg opts={[{ k: 0.2, l: "20% 이상 싸게" }, { k: 0.3, l: "30%" }, { k: 0.4, l: "40%" }, { k: 0.5, l: "50%" }]} value={disc} onChange={setDisc} />
      </Bar_>
      <Note>같은 단지·면적타입 평균 매매가보다 {(disc * 100).toFixed(0)}% 이상 싸게 거래된 건. 거래 3건 이상인 그룹만. 증여·가족 간 거래가 섞일 수 있어요. 전국 기준.</Note>
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <table className="t2-tbl">
          <thead><tr><th className="n">#</th><th>단지</th><th>거래</th><th>면적타입</th><th className="num">층</th><th className="num">거래가</th><th className="num">평균가</th><th className="num">할인율</th><th className="num">거래일</th></tr></thead>
          <tbody>{items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.deal_ymd}-${i}`}>
              <td className="n">{i + 1}</td>
              <td><CxCell no={it.complex_no} name={it.complex_name} sub={`${it.region_name ?? ""} · ${it.asset === "offi" ? "오피" : "아파트"} · 평균 ${it.group_size}건`} onPick={onPick} /></td>
              <td className={it.dealing_gbn === "직거래" ? "warn" : "mut"}>{it.dealing_gbn ?? "-"}</td>
              <td>{it.excl_use_ar ? areaLabel(it.excl_use_ar) : "-"}</td>
              <td className="num">{it.floor ?? "-"}</td>
              <td className="num b down">{won(it.deal_amount)}</td><td className="num mut">{won(it.avg_price)}</td>
              <td className="num b down">{(it.discount_rate * 100).toFixed(1)}%</td>
              <td className="num mut">{it.deal_ymd}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </>
  );
}

function Presale({ r, onPick }: PanelProps) {
  const [kind, setKind] = useState<"" | "분양권" | "입주권">("");
  const [months, setMonths] = useState(6);
  const [offset, setOffset] = useState(0);
  const sido = r.sido.slice(0, 2);
  useEffect(() => setOffset(0), [kind, months, sido]);
  const base = `months=${months}${sido ? `&sido=${sido}` : ""}`;
  const s = useQ<any>(`/stats/presale-summary?${base}`);
  const q = useQ<{ total: number; items: any[] }>(`/stats/presale-transactions?${base}&limit=50&offset=${offset}${kind ? `&kind=${encodeURIComponent(kind)}` : ""}`);
  const items = q.data?.items ?? [];
  return (
    <>
      <Bar_>
        <Seg opts={[{ k: "", l: "전체" }, { k: "분양권", l: "분양권" }, { k: "입주권", l: "입주권" }]} value={kind} onChange={setKind} />
        <Seg opts={[{ k: 3, l: "3달" }, { k: 6, l: "6달" }, { k: 12, l: "1년" }, { k: 0, l: "최대" }]} value={months} onChange={setMonths} />
      </Bar_>
      <Note>신축·재건축 단지의 입주 전 권리 거래. 청약 분양권과 재건축·재개발 입주권을 함께 보여요. 해제건 제외, 지역은 시·도까지만.</Note>
      {s.data && <div className="t2-kpis"><div><span>전체</span><b>{num(s.data.total)}</b></div><div><span>분양권</span><b>{num(s.data.n_bunyang)}</b></div><div><span>입주권</span><b>{num(s.data.n_ipju)}</b></div><div><span>평균 거래가</span><b>{won(s.data.avg_amount)}</b></div></div>}
      <Empty loading={q.loading} err={q.err} n={items.length} />
      {items.length > 0 && (
        <>
          <table className="t2-tbl">
            <thead><tr><th>종류</th><th>단지</th><th>면적</th><th className="num">층</th><th className="num">거래금액</th><th>거래</th><th className="num">계약일</th></tr></thead>
            <tbody>{items.map((x, i) => (
              <tr key={`${x.name}-${x.deal_ymd}-${i}`}>
                <td className={x.kind === "입주권" ? "warn" : "down"}>{x.kind}</td>
                <td><CxCell no={x.complex_no} name={x.name} sub={x.region} onPick={onPick} /></td>
                <td>{x.excl_use_ar != null ? areaLabel(x.excl_use_ar) : "-"}</td>
                <td className="num">{x.floor ?? "-"}</td>
                <td className="num b">{won(x.deal_amount)}</td>
                <td className="mut">{x.dealing_gbn ?? "-"}</td>
                <td className="num mut">{x.deal_ymd}</td>
              </tr>
            ))}</tbody>
          </table>
          <Pager offset={offset} total={q.data?.total ?? 0} limit={50} onOffset={setOffset} />
        </>
      )}
    </>
  );
}

// ── 창 ────────────────────────────────────────────────
export function StatsWindow({ open, onKey, region, onClose, onPick, onMapLayer, onSafe, phone }: {
  open: StatsKey; onKey: (k: StatsKey) => void; region: RegionSel; onClose: () => void;
  onPick: (no: string, name: string) => void; onMapLayer: () => void; onSafe: () => void; phone: boolean;
}) {
  // 지역은 지도가 보던 곳으로 시작한다. 창이 지도보다 먼저 떠서(공유 링크) 지역이 늦게 오면 따라가되, 사용자가 손댄 뒤엔 그대로 둔다.
  const [r, setR0] = useState<RegionSel>(region);
  const touched = useRef(false);
  const setR = (v: RegionSel) => { touched.current = true; setR0(v); };
  useEffect(() => { if (!touched.current) setR0(region); }, [region.sido, region.sgg]);   // eslint-disable-line react-hooks/exhaustive-deps
  const L = useRegionLists(r);
  const [dd, setDd] = useState<string | null>(null);
  const grp = STATS_GROUPS.find((g) => g.k === open.g)!;
  const item = grp.items.find((x) => x.k === open.i) ?? grp.items[0];
  const bodyRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bodyRef.current?.scrollTo({ top: 0 }); }, [open.g, open.i]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h); return () => document.removeEventListener("keydown", h);
  }, [onClose]);
  const props: PanelProps = { r, L, onPick };
  const panel = (() => {
    switch (`${open.g}.${item.k}`) {
      case "price.top": return <TopPrice {...props} />;
      case "price.rh": return <RecordHigh {...props} />;
      case "price.ppy": return <PyeongPrice {...props} />;
      case "price.chg": return <PriceChange {...props} />;
      case "price.tm": return <TimeMachine />;
      case "price.cancel": return <Cancelled {...props} />;
      case "price.map": return <div className="t2-sgo"><p>실거래 지도는 지도 화면의 시세분석 레이어예요. 동·구 버블과 단지 핀으로 실거래가·변동률을 봅니다.</p><button onClick={onMapLayer}>지도에서 보기</button></div>;
      case "hoga.sum": return <HogaSummary {...props} />;
      case "hoga.rank": return <HogaRank {...props} />;
      case "hoga.mov": return <HogaMovers {...props} />;
      case "hoga.cnt": return <ListingCounts />;
      case "flow.vol": return <Volume {...props} />;
      case "flow.pulse": return <Pulse />;
      case "flow.topvol": return <TopVolume {...props} />;
      case "flow.turn": return <Turnover {...props} />;
      case "invest.gap": return <GapRank {...props} />;
      case "invest.yield": return <Yield {...props} />;
      case "invest.low": return <LowPrice {...props} />;
      case "invest.presale": return <Presale {...props} />;
      case "invest.jeonse": return <div className="t2-sgo"><p>깡통전세지수는 안심 창으로 옮겼어요. 빌라를 고르고 보증금을 넣으면 공시가격 기준으로 위험을 판정합니다.</p><button onClick={onSafe}>안심 창 열기</button></div>;
      default: return null;
    }
  })();
  const noRegion = ["price.tm", "hoga.cnt", "flow.pulse", "invest.low", "price.map", "invest.jeonse"].includes(`${open.g}.${item.k}`);
  return (
    <section className={"t2-win" + (phone ? " phone" : "")} role="dialog" aria-label="통계">
      <header className="t2-win-h">
        <button className="t2-win-x" onClick={onClose} aria-label="지도로 돌아가기"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>지도</button>
        <h2>통계</h2>
        <nav className="t2-win-tabs" role="tablist">
          {STATS_GROUPS.map((g) => <button key={g.k} role="tab" aria-selected={g.k === open.g} className={g.k === open.g ? "on" : ""} onClick={() => onKey({ g: g.k, i: g.items[0].k })}>{g.l}</button>)}
        </nav>
        {!noRegion && (
          <div className="t2-win-region">
            <Dd id="sido" open={dd} setOpen={setDd} label={L.sidos.find((x) => x.code === r.sido)?.name ?? "전국"} active={!!r.sido}>
              <button className={!r.sido ? "on" : ""} onClick={() => setR({ sido: "", sgg: "", dong: "" })}>전국</button>
              {L.sidos.map((s) => <button key={s.code} className={s.code === r.sido ? "on" : ""} onClick={() => setR({ sido: s.code, sgg: "", dong: "" })}>{s.name}</button>)}
            </Dd>
            {r.sido && (
              <Dd id="sgg" open={dd} setOpen={setDd} label={L.sggs.find((x) => x.code === r.sgg)?.name ?? "시·군·구"} active={!!r.sgg}>
                <button className={!r.sgg ? "on" : ""} onClick={() => setR({ ...r, sgg: "", dong: "" })}>시·군·구 전체</button>
                {L.sggs.map((s) => <button key={s.code} className={s.code === r.sgg ? "on" : ""} onClick={() => setR({ ...r, sgg: s.code, dong: "" })}>{s.name}</button>)}
              </Dd>
            )}
            {r.sgg && (
              <Dd id="dong" open={dd} setOpen={setDd} label={L.dongs.find((x) => x.code === r.dong)?.name ?? "읍·면·동"} active={!!r.dong}>
                <button className={!r.dong ? "on" : ""} onClick={() => setR({ ...r, dong: "" })}>읍·면·동 전체</button>
                {L.dongs.map((s) => <button key={s.code} className={s.code === r.dong ? "on" : ""} onClick={() => setR({ ...r, dong: s.code })}>{s.name}</button>)}
              </Dd>
            )}
          </div>
        )}
      </header>
      <nav className="t2-win-sub">
        {grp.items.map((it) => <button key={it.k} className={it.k === item.k ? "on" : ""} onClick={() => onKey({ g: open.g, i: it.k })}>{it.l}</button>)}
      </nav>
      <div className="t2-win-b" ref={bodyRef}>
        <div className="t2-win-in">
          <h3 className="t2-win-ttl">{item.l}{!noRegion && <small>{regionLabel(r, L)}</small>}</h3>
          {panel}
        </div>
      </div>
    </section>
  );
}
