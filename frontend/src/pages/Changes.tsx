import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useStickyState } from "../hooks/useStickyState";
import ShareBar from "../components/ShareBar";
import { Link, Outlet, useOutletContext, useLocation } from "react-router-dom";
import { SubNav } from "../components/SubNav";
import { ApplyButton } from "../hooks/useDeferredUrl";
import {
  Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts";
import { Select, AREA_CLASSES, type AreaClass } from "./TxStats";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";

const API_BASE = import.meta.env.VITE_API_BASE;

const TRADE_OPTS = [
  { value: "A1", label: "매매" },
  { value: "B1", label: "전세" },
  { value: "B2", label: "월세" },
] as const;

// 상승=빨강, 하락=파랑 (국내 관행)
const UP = "#c0392b";
const DOWN = "#1268d3";

function formatWon(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 100_000_000) {
    const eok = Math.floor(v / 100_000_000);
    const man = Math.floor((v % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(v / 10_000).toLocaleString()}만`;
}
function pct(r: number): string {
  return `${r >= 0 ? "+" : ""}${(r * 100).toFixed(1)}%`;
}

type TradeStat = {
  count: number; prev: number; delta: number;
  avg_price: number | null; avg_prev: number | null; avg_change: number | null;
  // B2 한정: 월세 평균 (보증금=avg_price와 별개).
  rent_avg?: number | null;
  rent_prev?: number | null;
  rent_change?: number | null;
};
type Summary = {
  latest_date: string | null;
  prev_date: string | null;
  prev_is_yesterday?: boolean;
  complex_count: number;
  total: number;
  trades: Record<string, TradeStat>;
  event_date: string | null;
  events_up: number;
  events_down: number;
};
type Sido = { code: string; name: string };
type RankItem = {
  region_code: string;
  region_name: string | null;
  avg_price: number;
  prev_avg: number | null;
  change: number | null;
  listings: number;
  complexes: number;
};
type MoverItem = {
  complex_no: string | null;
  complex_name: string | null;
  area_name: string | null;
  region_name: string | null;
  old_avg: number;
  new_avg: number;
  rate: number;
  listing_count: number;
  complex_listings: number;
};
function Section({ title, desc, children }: {
  title: string; desc?: string; children: ReactNode;
}) {
  return (
    <section style={{ marginBottom: 32 }}>
      <h3 style={{ margin: "0 0 2px", fontSize: 16 }}>{title}</h3>
      {desc && <div className="muted" style={{ marginBottom: 10 }}>{desc}</div>}
      {children}
    </section>
  );
}

// ───────────────────────── 요약 카드 + 추이 ─────────────────────────
function SummaryCards({ s, regionLabel }: { s: Summary; regionLabel: string }) {
  const b2 = s.trades.B2;
  const rentCh = b2?.rent_change ?? null;
  type CardSpec = {
    key: string;
    label: string;
    price: number | null | undefined;
    change: number | null | undefined;
    count: number;
  };
  const cards: CardSpec[] = [
    { key: "A1", label: "매매 평균가",
      price: s.trades.A1?.avg_price, change: s.trades.A1?.avg_change,
      count: s.trades.A1?.count ?? 0 },
    { key: "B1", label: "전세 평균가",
      price: s.trades.B1?.avg_price, change: s.trades.B1?.avg_change,
      count: s.trades.B1?.count ?? 0 },
    { key: "B2D", label: "월세 보증금 평균",
      price: b2?.avg_price, change: b2?.avg_change,
      count: b2?.count ?? 0 },
    { key: "B2R", label: "월세 평균",
      price: b2?.rent_avg, change: rentCh,
      count: b2?.count ?? 0 },
  ];
  return (
    <div className="cards">
      <div className="card">
        <div className="label">{regionLabel} 매물 수</div>
        <div className="num">{s.total.toLocaleString()}</div>
        <div className="sub">단지 {s.complex_count.toLocaleString()}개</div>
      </div>
      {cards.map((c) => (
        <div className="card" key={c.key}>
          <div className="label">{c.label}</div>
          <div className="num">{formatWon(c.price ?? null)}</div>
          <div className="sub">
            {c.change != null ? (
              <span style={{ color: c.change >= 0 ? UP : DOWN, fontWeight: 600 }}>
                {s.prev_is_yesterday === false ? "직전" : "전일"} {pct(c.change)}
              </span>
            ) : <span>{s.prev_is_yesterday === false ? "직전" : "전일"} 대비 –</span>}
            {" · 매물 "}{c.count.toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
}

type AvgPoint = {
  snapshot_date: string;
  A1: number | null; B1: number | null; B2: number | null; B2R: number | null;
};
type TradeKey = "A1" | "B1" | "B2" | "B2R";
const TREND_LINES: { key: TradeKey; label: string; color: string }[] = [
  { key: "A1", label: "매매", color: "#c0392b" },
  { key: "B1", label: "전세", color: "#1268d3" },
  { key: "B2", label: "월세 보증금", color: "#27ae60" },
  { key: "B2R", label: "월세", color: "#d97706" },
];
// 차트 라벨: dataKey(A1/B1/B2/B2R) → 사람이 읽는 이름.
const KEY_LABEL: Record<string, string> = {
  A1: "매매", B1: "전세", B2: "월세 보증금", B2R: "월세",
};

// 지역 prop: 차트와 summary 등에 공통으로 전달.
type RegionFilter = { sido: string; sigungu: string };

function regionQueryString(r: RegionFilter): string {
  const qs = new URLSearchParams();
  if (r.sigungu) qs.set("sigungu", r.sigungu);
  else if (r.sido) qs.set("sido", r.sido);
  return qs.toString();
}

const WEEKDAYS_KO = ["일", "월", "화", "수", "목", "금", "토"];

function formatKoCount(v: number): string {
  // 평균가 (원 단위) → 한국식 축약. 호가 스케일에 맞춰 억/만 우선.
  if (v === 0) return "0";
  const sign = v < 0 ? "-" : "";
  const a = Math.abs(v);
  if (a >= 100_000_000) {
    const n = a / 100_000_000;
    return `${sign}${n % 1 === 0 ? n.toFixed(0) : n.toFixed(1)}억`;
  }
  if (a >= 10_000) return `${sign}${Math.round(a / 10_000)}만`;
  if (a >= 1_000) return `${sign}${Math.round(a / 1_000)}천`;
  return `${sign}${a}`;
}

function AvgPriceChart({ region, regionLabel, asset }: { region: RegionFilter; regionLabel: string; asset: string }) {
  const [series, setSeries] = useState<AvgPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState<Record<TradeKey, boolean>>({
    A1: true, B1: true, B2: true, B2R: true,
  });
  useEffect(() => {
    if (!API_BASE) return;
    const qs = regionQueryString(region);
    setLoading(true);
    fetch(`${API_BASE}/stats/avg-price-trend?days=60&asset=${asset}${qs ? "&" + qs : ""}`)
      .then((r) => r.json()).then((d) => setSeries(d.series || []))
      .catch(() => {}).finally(() => setLoading(false));
  }, [region.sido, region.sigungu, asset]);
  // 로딩 중에는 박스만 먼저 뜨고 그래프가 비는 대신 스켈레톤+진행바를 보여준다.
  if (loading && series.length < 2) {
    return (
      <Section title={`${regionLabel} 매물평균 호가`} desc="일별 거래유형별 가중평균 호가를 불러오는 중입니다.">
        <div className="chart-skeleton" style={{ height: 240 }}>
          <div className="chart-skeleton-bar" />
          <span className="chart-skeleton-text">그래프 불러오는 중…</span>
        </div>
      </Section>
    );
  }
  if (series.length < 2) return null;
  const toggle = (k: TradeKey) => setVisible((v) => ({ ...v, [k]: !v[k] }));

  const tooltipLabelFmt = (label: unknown) => {
    const s = String(label);
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
    if (!m) return s;
    const wd = WEEKDAYS_KO[new Date(`${s}T00:00:00`).getDay()];
    return `${Number(m[2])}월 ${Number(m[3])}일 (${wd})`;
  };
  const tooltipValueFmt = (v: unknown, n: unknown): [string, string] => [
    v == null ? "–" : formatWon(Number(v)),
    KEY_LABEL[String(n)] ?? String(n),
  ];

  // 메인 차트: 매매·전세·보증금 — 같은 억 단위 스케일이라 dual-axis로 처리.
  // 월세는 보증금보다 100배 작아 별도 차트로 분리.
  const showMain = visible.A1 || visible.B1 || visible.B2;
  const showRent = visible.B2R;

  return (
    <Section title={`${regionLabel} 매물평균 호가`}
      desc="일별 거래유형별 가중평균 호가 (단지·면적타입 평균을 매물 수로 가중). 월세 보증금과 월세는 스케일이 달라 별도 차트로 분리. 칩을 눌러 보고 싶은 거래만 켤 수 있습니다.">
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
        {TREND_LINES.map((l) => {
          const on = visible[l.key];
          return (
            <button
              key={l.key}
              onClick={() => toggle(l.key)}
              style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                padding: "4px 12px", borderRadius: 16, cursor: "pointer",
                fontSize: 13, fontWeight: 600,
                border: `1px solid ${on ? l.color : "#ccc"}`,
                background: on ? l.color : "white",
                color: on ? "white" : "#999",
              }}
            >
              <span style={{
                width: 8, height: 8, borderRadius: "50%",
                background: on ? "white" : l.color, opacity: on ? 1 : 0.5,
              }} />
              {l.label}
            </button>
          );
        })}
      </div>

      {showMain && (
        <div style={{ width: "100%", height: 240 }}>
          <ResponsiveContainer>
            <LineChart data={series} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#eee" />
              <XAxis dataKey="snapshot_date" tick={{ fontSize: 11 }} tickFormatter={(d) => d?.slice(5)} />
              <YAxis
                yAxisId="sale"
                hide={!visible.A1}
                tick={{ fontSize: 11, fill: "#c0392b" }}
                width={56}
                // 데이터 범위 아래·위로 여백 → ±1% 미세 변동이 완만하게 보이도록.
                domain={[(min: number) => Math.floor(min * 0.85), (max: number) => Math.ceil(max * 1.15)]}
                tickFormatter={formatKoCount}
              />
              <YAxis
                yAxisId="rent"
                orientation="right"
                hide={!visible.B1 && !visible.B2}
                tick={{ fontSize: 11, fill: "#1268d3" }}
                width={56}
                domain={[(min: number) => Math.floor(min * 0.85), (max: number) => Math.ceil(max * 1.15)]}
                tickFormatter={formatKoCount}
              />
              <Tooltip
                formatter={tooltipValueFmt}
                labelFormatter={tooltipLabelFmt}
                labelStyle={{ fontSize: 12 }}
                contentStyle={{ fontSize: 12 }}
              />
              {visible.A1 && (
                <Line yAxisId="sale" type="monotone" dataKey="A1" name="A1" stroke="#c0392b" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              )}
              {visible.B1 && (
                <Line yAxisId="rent" type="monotone" dataKey="B1" name="B1" stroke="#1268d3" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              )}
              {visible.B2 && (
                <Line yAxisId="rent" type="monotone" dataKey="B2" name="B2" stroke="#27ae60" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {showRent && (
        <>
          <div className="muted" style={{ marginTop: 12, marginBottom: 4, fontSize: 12 }}>
            월세 (보증금 외 매달 지불)
          </div>
          <div style={{ width: "100%", height: 180 }}>
            <ResponsiveContainer>
              <LineChart data={series} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                <CartesianGrid stroke="#eee" />
                <XAxis dataKey="snapshot_date" tick={{ fontSize: 11 }} tickFormatter={(d) => d?.slice(5)} />
                <YAxis
                  tick={{ fontSize: 11, fill: "#d97706" }}
                  width={56}
                  domain={["auto", "auto"]}
                  tickFormatter={formatKoCount}
                />
                <Tooltip
                  formatter={tooltipValueFmt}
                  labelFormatter={tooltipLabelFmt}
                  labelStyle={{ fontSize: 12 }}
                  contentStyle={{ fontSize: 12 }}
                />
                <Line type="monotone" dataKey="B2R" name="B2R" stroke="#d97706" strokeWidth={2} dot={{ r: 3 }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </Section>
  );
}

// ───────────────────────── 지역별 가격 순위 ─────────────────────────
function RegionRank({ region, asset, trade }: { region: RegionFilter; asset: string; trade: string }) {
  // 상단 지역이 시도까지면 → 시군구 단위 순위, 시군구까지면 → 동 단위 순위, 없으면 → 시도 순위.
  const defaultLevel: "sido" | "sigungu" | "dong" =
    region.sigungu ? "dong" : region.sido ? "sigungu" : "sido";
  const [level, setLevel] = useState<"sido" | "sigungu" | "dong">(defaultLevel);
  const [areaClass, setAreaClass] = useStickyState<AreaClass>("changes:areaClass", "all");
  // 로컬필터(단위·면적)는 '적용' 으로만 갱신. 지역/거래/유형은 상단(레이아웃) 적용분이 props 로 들어옴.
  const [applied, setApplied] = useState<{ level: "sido" | "sigungu" | "dong"; area: AreaClass }>(
    { level: defaultLevel, area: "all" });
  useEffect(() => { setLevel(defaultLevel); setApplied((a) => ({ ...a, level: defaultLevel })); }, [defaultLevel]);
  const regionQ = region.sigungu
    ? `&sigungu=${region.sigungu}`
    : region.sido ? `&sido=${region.sido}` : "";
  const url = API_BASE
    ? `${API_BASE}/stats/changes/region-rank?level=${applied.level}&trade=${trade}&asset=${asset}${regionQ}&area_class=${applied.area}&min_listings=30&limit=30`
    : null;
  const { data, loading } = useFetchJson<{ items: RankItem[]; prev_is_yesterday?: boolean }>(url);
  const items = data?.items ?? [];
  const cmpLabel = data?.prev_is_yesterday === false ? "직전대비" : "전일대비";
  const max = useMemo(() => Math.max(1, ...items.map((i) => i.avg_price)), [items]);
  const dirty = level !== applied.level || areaClass !== applied.area;
  const apply = () => setApplied({ level, area: areaClass });
  return (
    <Section title="지역별 매물 가격 순위"
      desc="지역별 평균 매물 가격 순위. 시군구는 시도를 먼저 선택하면 볼 수 있어요.">
      <div className="filter-bar">
        <Select label="단위" value={level} onChange={setLevel}
          options={[{ value: "sido", label: "시도" }, { value: "sigungu", label: "시군구" }, { value: "dong", label: "동" }]} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass}
          options={AREA_CLASSES.map((a) => ({ value: a.code, label: a.label }))} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>
      {loading && <Loading />}
      <table>
        <thead>
          <tr>
            <th style={{ width: 40 }}>#</th><th>지역</th>
            <th className="num">평균 호가</th><th className="num">{cmpLabel}</th>
            <th className="num">매물</th><th className="num">단지</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={it.region_code}>
              <td style={{ color: "#999" }}>{i + 1}</td>
              <td style={{ position: "relative" }}>
                <div style={{
                  position: "absolute", left: 0, top: 3, bottom: 3,
                  width: `${(it.avg_price / max) * 100}%`,
                  background: trade === "A1" ? "rgba(192,57,43,0.08)" : "rgba(18,104,211,0.08)",
                  borderRadius: 3, zIndex: 0,
                }} />
                <span style={{ position: "relative", zIndex: 1 }}>{it.region_name ?? it.region_code}</span>
              </td>
              <td className="num" style={{ fontWeight: 600 }}>{formatWon(it.avg_price)}</td>
              <td className="num" style={{ color: it.change == null ? "#9ca3af" : it.change >= 0 ? UP : DOWN }}>
                {it.change == null ? "–" : pct(it.change)}
              </td>
              <td className="num">{it.listings.toLocaleString()}</td>
              <td className="num">{it.complexes.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

// ───────────────────────── 상승/하락 Top ─────────────────────────
function MoverTable({ title, items, color }: {
  title: string; items: MoverItem[]; color: string;
}) {
  return (
    <div style={{ flex: 1, minWidth: 300 }}>
      <div style={{ fontWeight: 600, marginBottom: 6, color }}>{title}</div>
      <table>
        <thead>
          <tr><th>단지</th><th>면적타입</th><th className="num">변동</th><th className="num">현재</th></tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 16 }}>데이터 없음</td></tr>
          )}
          {items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.area_name}-${i}`}>
              <td>
                {it.complex_no
                  ? <Link to={`/complex/${it.complex_no}`}>{it.complex_name ?? it.complex_no}</Link>
                  : (it.complex_name ?? "—")}
                <div className="muted" style={{ fontSize: 11 }}>
                  {it.region_name ?? ""}{it.complex_listings ? ` · 매물 ${it.complex_listings.toLocaleString()}건` : ""}
                </div>
              </td>
              <td>{it.area_name ?? "-"}㎡</td>
              <td className="num" style={{ fontWeight: 600, color }}>{pct(it.rate)}</td>
              <td className="num">{formatWon(it.new_avg)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Movers({ region, asset, trade }: { region: RegionFilter; asset: string; trade: string }) {
  const regionQ = region.sigungu
    ? `&sigungu=${region.sigungu}`
    : region.sido ? `&sido=${region.sido}` : "";
  const url = API_BASE
    ? `${API_BASE}/stats/changes/movers?trade=${trade}&asset=${asset}${regionQ}&min_listings=2&limit=5`
    : null;
  const { data, loading } = useFetchJson<{ up: MoverItem[]; down: MoverItem[] }>(url);
  const up = data?.up ?? [];
  const down = data?.down ?? [];
  return (
    <Section title="가격 변동 Top — 상승 / 하락"
      desc="최근 매물 가격이 많이 오르거나 내린 단지.">
      {loading && <Loading />}
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <MoverTable title="▲ 상승 Top 5" items={up} color={UP} />
        <MoverTable title="▼ 하락 Top 5" items={down} color={DOWN} />
      </div>
    </Section>
  );
}

// ───────────────────────── 레이아웃(공통 필터 + 요약) + 3개 하위탭 ─────────────────────────
const ASSET_OPTS = [
  { value: "apt", label: "아파트" },
  { value: "offi", label: "오피스텔" },
] as const;

type ChangesCtx = { region: RegionFilter; regionLabel: string; asset: string; trade: string };

export function ChangesLayout() {
  const shareRef = useRef<HTMLDivElement>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sidos, setSidos] = useState<Sido[]>([]);
  const [sigungus, setSigungus] = useState<Sido[]>([]);
  const [sido, setSido] = useState<string>("");
  const [sigungu, setSigungu] = useState<string>("");
  const [asset, setAsset] = useState<string>("apt");
  const [trade, setTrade] = useState<string>("A1");
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);
  // 필터 즉시 호출 방지 — '적용' 눌러야 summary·하위탭이 갱신(applied 기준).
  // 시군구 목록만은 즉시 로드(드롭다운 채우기용).
  const [applied, setApplied] = useState({ sido: "", sigungu: "", asset: "apt", trade: "A1" });
  const loc = useLocation();
  // 가격 추이 탭은 매매·전세·월세 3개 라인을 동시에 보여줘서 단일 거래필터가 없음.
  // 지역별 순위·상승하락 탭에서만 '거래'를 (표준 순서대로) 맨 앞에 노출.
  const showTrade = loc.pathname.includes("/region") || loc.pathname.includes("/movers");

  useEffect(() => {
    if (!API_BASE) { setError("로컬 API(VITE_API_BASE)가 설정되지 않았습니다."); return; }
    fetch(`${API_BASE}/stats/changes/sido-list`)
      .then((r) => r.json()).then((d) => setSidos(d.items || [])).catch(() => {});
  }, []);

  useEffect(() => {
    if (!API_BASE) return;
    setSigungu("");
    if (!sido) { setSigungus([]); return; }
    fetch(`${API_BASE}/stats/sigungu-list?sido=${sido}`)
      .then((r) => r.json()).then((d) => setSigungus(d.items || []))
      .catch(() => setSigungus([]));
  }, [sido]);

  useEffect(() => {
    if (!API_BASE) return;
    const qs = regionQueryString({ sido: applied.sido, sigungu: applied.sigungu });
    setFetching(true);
    fetch(`${API_BASE}/stats/changes/summary?asset=${applied.asset}${qs ? "&" + qs : ""}`)
      .then((r) => r.json()).then(setSummary)
      .catch((e) => setError(String(e))).finally(() => setFetching(false));
  }, [applied]);

  if (error) return <div style={{ color: "crimson" }}>오류: {error}</div>;
  if (!summary) return <Loading />;

  const sidoName = sidos.find((s) => s.code === applied.sido)?.name ?? "";
  const sigunguName = sigungus.find((s) => s.code === applied.sigungu)?.name ?? "";
  const regionLabel = applied.sigungu ? `${sidoName} ${sigunguName}`.trim() : applied.sido ? sidoName : "전국";
  const assetLabel = ASSET_OPTS.find((a) => a.value === applied.asset)?.label ?? "";
  const ctx: ChangesCtx = {
    region: { sido: applied.sido, sigungu: applied.sigungu },
    regionLabel, asset: applied.asset, trade: applied.trade,
  };
  const dirty = applied.sido !== sido || applied.sigungu !== sigungu
    || applied.asset !== asset || (showTrade && applied.trade !== trade);
  const apply = () => setApplied({ sido, sigungu, asset, trade });

  return (
    <div ref={shareRef} className="share-target">
      <h2 style={{ margin: "0 0 4px" }}>매물가격추이</h2>
      <div className="muted" style={{ marginBottom: 12 }}>
        {regionLabel} {assetLabel} 매물 가격 · 기준 {summary.latest_date}
      </div>
      <ShareBar targetRef={shareRef} title="매물 가격 변화" fileName="콕집_가격변화" />

      <SubNav tabs={[
        { to: "/changes/trend", label: "가격 추이" },
        { to: "/changes/region", label: "지역별 순위" },
        { to: "/changes/movers", label: "상승·하락" },
      ]} />

      <div className="filter-bar" style={{ marginBottom: 16, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        {showTrade && (
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span className="muted" style={{ fontSize: 12 }}>거래</span>
            <select value={trade} onChange={(e) => setTrade(e.target.value)}>
              {TRADE_OPTS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </label>
        )}
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>시도</span>
          <select value={sido} onChange={(e) => setSido(e.target.value)}>
            <option value="">전국</option>
            {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>시군구</span>
          <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}>
            <option value="">{sido ? "전체" : "(시도 선택)"}</option>
            {sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>유형</span>
          <select value={asset} onChange={(e) => setAsset(e.target.value)}>
            {ASSET_OPTS.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
        </label>
        {fetching && <span className="muted" style={{ fontSize: 12, color: "#1268d3" }}>불러오는 중…</span>}
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>

      <SummaryCards s={summary} regionLabel={`${regionLabel} ${assetLabel}`.trim()} />
      <Outlet context={ctx} />
    </div>
  );
}

export function ChangesTrend() {
  const { region, regionLabel, asset } = useOutletContext<ChangesCtx>();
  return <AvgPriceChart region={region} regionLabel={regionLabel} asset={asset} />;
}
export function ChangesRegion() {
  const { region, asset, trade } = useOutletContext<ChangesCtx>();
  return <RegionRank region={region} asset={asset} trade={trade} />;
}
export function ChangesMovers() {
  const { region, asset, trade } = useOutletContext<ChangesCtx>();
  return <Movers region={region} asset={asset} trade={trade} />;
}
