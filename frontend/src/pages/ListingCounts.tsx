import { useRef } from "react";
import { useStickyState } from "../hooks/useStickyState";
import FetchError from "../components/FetchError";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";
import ShareBar from "../components/ShareBar";
import { SubNav } from "../components/SubNav";
import FavDashLink from "../components/FavDashLink";
import { CHANGES_TABS } from "./Changes";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, Legend, CartesianGrid,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE;

// 지역별 매물수 — 실거래통계 '지역별 거래량'과 같은 순서(전국 먼저, 시도는 통계청 관례).
// 광고수(기본)와 실매물수(중복 광고 합침)를 함께 보여 콕집의 광고배율 관점을 유지한다.
const UP = "#c0392b";
const DOWN = "#1268d3";
// 거래유형 색 = 전역 디자인 토큰(--c-sale/--c-jeonse/--c-wolse)과 동일
const C_SALE = "#d23b3b";
const C_JEONSE = "#1268d3";
const C_WOLSE = "#1f9d63";

const SIDO_ORDER = ["11", "26", "27", "28", "29", "30", "31", "36",
  "41", "42", "51", "43", "44", "45", "52", "46", "47", "48", "50"];
function sidoRank(code: string): number {
  const i = SIDO_ORDER.indexOf((code || "").slice(0, 2));
  return i < 0 ? SIDO_ORDER.length : i;
}
const SIDO_SHORT: Record<string, string> = {
  "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주", "30": "대전",
  "31": "울산", "36": "세종", "41": "경기", "42": "강원", "51": "강원", "43": "충북",
  "44": "충남", "45": "전북", "52": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
};

type Row = {
  sido_code: string; sido_name: string;
  A1: number; B1: number; B2: number;
  A1_u: number; B1_u: number; B2_u: number;
  total: number; total_u: number; prev_total: number; week_total: number;
};
type CountsRes = {
  as_of: string | null; prev_date: string | null; week_date: string | null;
  national: Row | null; regions: Row[];
};
type TrendRes = {
  days: number;
  series: { snapshot_date: string; A1: number; B1: number; B2: number;
    A1_u?: number; B1_u?: number; B2_u?: number }[];
};

const fmt = (n: number | null | undefined) => (n == null ? "-" : Math.round(n).toLocaleString());
const man = (n: number) => (n >= 10000 ? `${Math.round(n / 10000)}만` : n.toLocaleString());

function Delta({ cur, base, label }: { cur: number; base: number; label: string }) {
  if (!base) return null;
  const d = cur - base;
  if (d === 0) return <span className="lc-delta flat">{label} ±0</span>;
  return (
    <span className="lc-delta" style={{ color: d > 0 ? UP : DOWN }}>
      {label} {d > 0 ? "▲" : "▼"}{Math.abs(d).toLocaleString()}
    </span>
  );
}

export default function ListingCounts() {
  const shareRef = useRef<HTMLDivElement>(null);
  const [asset, setAsset] = useStickyState<"apt" | "offi" | "all">("lcnt:asset", "apt");
  const q = useFetchJson<CountsRes>(
    API_BASE ? `${API_BASE}/stats/listing-counts?asset=${asset}` : null);
  const trendQ = useFetchJson<TrendRes>(
    API_BASE ? `${API_BASE}/stats/listing-trend?days=60` : null);

  // 그래프 인터랙션 — 기준(광고/실매물) 세그먼트 + 거래유형 토글(두 차트 동시 반응)
  const [basis, setBasis] = useStickyState<"ads" | "units">("lcnt:basis", "ads");
  const [sel, setSel] = useStickyState<Record<"A1" | "B1" | "B2", boolean>>("lcnt:sel", { A1: true, B1: true, B2: true });
  const toggleTrade = (t: "A1" | "B1" | "B2") => setSel((s) => {
    const next = { ...s, [t]: !s[t] };
    return next.A1 || next.B1 || next.B2 ? next : s;   // 최소 1개는 유지
  });
  const basisLabel = basis === "ads" ? "광고 건수" : "실매물";

  const nat = q.data?.national;
  const regions = (q.data?.regions ?? []).slice()
    .sort((a, b) => sidoRank(a.sido_code) - sidoRank(b.sido_code));
  const pick = (r: Row, t: "A1" | "B1" | "B2") => (basis === "ads" ? r[t] : r[`${t}_u`]);
  const chartData = regions.map((r) => ({
    name: SIDO_SHORT[r.sido_code] || r.sido_name,
    매매: pick(r, "A1"), 전세: pick(r, "B1"), 월세: pick(r, "B2"),
  }));
  const TRADES: { t: "A1" | "B1" | "B2"; name: string; color: string }[] = [
    { t: "A1", name: "매매", color: C_SALE },
    { t: "B1", name: "전세", color: C_JEONSE },
    { t: "B2", name: "월세", color: C_WOLSE },
  ];

  return (
    <div ref={shareRef} className="share-target">
      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "0 0 4px" }}>
        <h2 style={{ margin: 0 }}>지역별 매물수</h2>
        <FavDashLink />
      </div>
      <div className="muted" style={{ marginBottom: 12 }}>
        전국·시도별 현재 매물 — 광고 건수 기준, 실매물(같은 집 중복 광고 합침) 병기
        {q.data?.as_of ? ` · 기준 ${q.data.as_of}` : ""}
      </div>
      <ShareBar targetRef={shareRef} title="지역별 매물수" fileName="콕집_지역별매물수" />

      <SubNav tabs={CHANGES_TABS} />

      <div className="filter-bar" style={{ marginBottom: 14, display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>자산</span>
          <select value={asset} onChange={(e) => setAsset(e.target.value as "apt" | "offi" | "all")}>
            <option value="apt">아파트</option>
            <option value="offi">오피스텔</option>
            <option value="all">통합</option>
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>기준</span>
          <span className="lc-seg" role="group" aria-label="집계 기준">
            <button type="button" className={basis === "ads" ? "on" : ""} onClick={() => setBasis("ads")}>전체매물</button>
            <button type="button" className={basis === "units" ? "on" : ""} onClick={() => setBasis("units")}>실매물</button>
          </span>
        </label>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>유형</span>
          {TRADES.map(({ t, name, color }) => (
            <button key={t} type="button" onClick={() => toggleTrade(t)}
              className={`lc-chip${sel[t] ? " on" : ""}`}
              style={sel[t] ? { background: color, borderColor: color } : undefined}
              aria-pressed={sel[t]}>
              <i style={{ background: sel[t] ? "#fff" : color }} />{name}
            </button>
          ))}
        </span>
      </div>

      {q.error && <FetchError message={q.error} inline />}
      {q.loading && <Loading />}

      {nat && (
        <>
          {/* 전국 히어로 — 실거래통계 지역별 거래량의 전국 카드와 같은 자리·역할 */}
          <div className="lc-hero">
            <div className="lc-hero-main">
              <span className="lc-hero-label">전국 매물</span>
              <span className="lc-hero-num">{fmt(nat.total)}<em>건</em></span>
              <span className="lc-hero-sub">
                실매물 {fmt(nat.total_u)}건
                {nat.total_u > 0 && <> · 광고배율 ×{(nat.total / nat.total_u).toFixed(1)}</>}
              </span>
              <span className="lc-hero-deltas">
                <Delta cur={nat.total} base={nat.prev_total} label="전일" />
                <Delta cur={nat.total} base={nat.week_total} label="7일" />
              </span>
            </div>
            <div className="lc-hero-split">
              <div className="lc-kp" style={{ borderTopColor: C_SALE }}>
                <span className="lc-kp-label">매매</span>
                <span className="lc-kp-val">{fmt(nat.A1)}</span>
                <span className="lc-kp-sub">실매물 {fmt(nat.A1_u)}</span>
              </div>
              <div className="lc-kp" style={{ borderTopColor: C_JEONSE }}>
                <span className="lc-kp-label">전세</span>
                <span className="lc-kp-val">{fmt(nat.B1)}</span>
                <span className="lc-kp-sub">실매물 {fmt(nat.B1_u)}</span>
              </div>
              <div className="lc-kp" style={{ borderTopColor: C_WOLSE }}>
                <span className="lc-kp-label">월세</span>
                <span className="lc-kp-val">{fmt(nat.B2)}</span>
                <span className="lc-kp-sub">실매물 {fmt(nat.B2_u)}</span>
              </div>
            </div>
          </div>

          {/* 전국 매물수 추이(60일) — 거래유형별 광고 건수 */}
          {trendQ.data && trendQ.data.series.length > 1 && (
            <div className="lc-card">
              <h3 className="lc-card-h">전국 매물수 추이 <span className="muted">최근 60일 · {basisLabel}</span></h3>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trendQ.data.series} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#eef2f8" vertical={false} />
                  <XAxis dataKey="snapshot_date" tick={{ fontSize: 11, fill: "#8593a9" }}
                    tickFormatter={(d: string) => d.slice(5)} minTickGap={28} />
                  <YAxis tick={{ fontSize: 11, fill: "#8593a9" }} tickFormatter={(v: number) => man(v)} width={44} />
                  <Tooltip formatter={(v) => Number(v ?? 0).toLocaleString()}
                    labelStyle={{ fontWeight: 700 }} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  {TRADES.filter(({ t }) => sel[t]).map(({ t, name, color }) => (
                    <Line key={`${t}:${basis}`} type="monotone"
                      dataKey={basis === "ads" ? t : `${t}_u`} name={name}
                      stroke={color} strokeWidth={2} dot={false}
                      connectNulls />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 시도별 그래프 — 매매/전세/월세 누적 가로막대 */}
          <div className="lc-card">
            <h3 className="lc-card-h">시도별 매물수 <span className="muted">{basisLabel} · {TRADES.filter(({ t }) => sel[t]).map((x) => x.name).join("/")}</span></h3>
            <ResponsiveContainer width="100%" height={regions.length * 27 + 60}>
              <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 56, bottom: 0, left: 0 }} barCategoryGap={5}>
                <CartesianGrid stroke="#eef2f8" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#8593a9" }} tickFormatter={(v: number) => man(v)} />
                <YAxis type="category" dataKey="name" width={42} tick={{ fontSize: 12, fill: "#33415b", fontWeight: 600 }} />
                <Tooltip formatter={(v) => Number(v ?? 0).toLocaleString()}
                  labelStyle={{ fontWeight: 700 }} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {TRADES.filter(({ t }) => sel[t]).map(({ t, name, color }, i, arr) => (
                  <Bar key={`${t}:${basis}`} dataKey={name} stackId="t" fill={color}
                    radius={i === arr.length - 1 ? [0, 3, 3, 0] : undefined} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* 시도별 표 — 광고·실매물·광고배율·증감 */}
          <div className="lc-card" style={{ overflowX: "auto" }}>
            <h3 className="lc-card-h">시도별 상세 <span className="muted">광고배율 = 광고 ÷ 실매물(높을수록 매도 경쟁 심함)</span></h3>
            <table className="lc-table">
              <thead>
                <tr>
                  <th>지역</th><th>매매</th><th>전세</th><th>월세</th>
                  <th>전체(광고)</th><th>실매물</th><th>광고배율</th><th>전일比</th><th>7일比</th>
                </tr>
              </thead>
              <tbody>
                <tr className="lc-nat">
                  <td>전국</td>
                  <td>{fmt(nat.A1)}</td><td>{fmt(nat.B1)}</td><td>{fmt(nat.B2)}</td>
                  <td><b>{fmt(nat.total)}</b></td><td>{fmt(nat.total_u)}</td>
                  <td>{nat.total_u > 0 ? `×${(nat.total / nat.total_u).toFixed(1)}` : "-"}</td>
                  <td><Delta cur={nat.total} base={nat.prev_total} label="" /></td>
                  <td><Delta cur={nat.total} base={nat.week_total} label="" /></td>
                </tr>
                {regions.map((r) => (
                  <tr key={r.sido_code}>
                    <td>{SIDO_SHORT[r.sido_code] || r.sido_name}</td>
                    <td>{fmt(r.A1)}</td><td>{fmt(r.B1)}</td><td>{fmt(r.B2)}</td>
                    <td><b>{fmt(r.total)}</b></td><td>{fmt(r.total_u)}</td>
                    <td>{r.total_u > 0 ? `×${(r.total / r.total_u).toFixed(1)}` : "-"}</td>
                    <td><Delta cur={r.total} base={r.prev_total} label="" /></td>
                    <td><Delta cur={r.total} base={r.week_total} label="" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="muted" style={{ fontSize: 11.5, margin: "10px 0 0" }}>
            광고 건수 = 네이버 노출 광고 수 · 실매물 = 같은 집의 중복 광고를 하나로 합친 수 ·
            단지형(아파트·오피스텔) 기준 · 매일 수집 스냅샷
          </p>
        </>
      )}

      <style>{`
        .lc-hero{display:flex;gap:18px;flex-wrap:wrap;align-items:stretch;background:linear-gradient(135deg,#13294b,#1b3a6b);border-radius:14px;padding:20px 24px;margin-bottom:14px;color:#fff}
        .lc-hero-main{display:flex;flex-direction:column;gap:3px;min-width:220px;flex:1}
        .lc-hero-label{font-size:12.5px;font-weight:700;letter-spacing:.06em;color:#9ec5f5}
        .lc-hero-num{font-size:40px;font-weight:800;line-height:1.1;font-variant-numeric:tabular-nums}
        .lc-hero-num em{font-style:normal;font-size:17px;font-weight:700;margin-left:3px;color:#c9dcf7}
        .lc-hero-sub{font-size:13px;color:#c9dcf7}
        .lc-hero-deltas{display:flex;gap:12px;margin-top:6px;font-size:12.5px;font-weight:700}
        .lc-hero .lc-delta{background:rgba(255,255,255,.92);border-radius:999px;padding:2px 10px}
        .lc-delta.flat{color:#66748a}
        .lc-hero-split{display:flex;gap:10px;align-items:stretch}
        .lc-kp{background:#fff;border-radius:10px;border-top:3px solid #1268d3;padding:9px 14px;min-width:96px;display:flex;flex-direction:column;gap:1px;text-align:center}
        .lc-kp-label{font-size:11.5px;font-weight:700;color:#66748a}
        .lc-kp-val{font-size:18px;font-weight:800;color:#1f2a37;font-variant-numeric:tabular-nums}
        .lc-kp-sub{font-size:10.5px;color:#8593a9;font-variant-numeric:tabular-nums}
        .lc-seg{display:inline-flex;border:1px solid #cdd9ea;border-radius:8px;overflow:hidden}
        .lc-seg button{border:none;background:#fff;padding:5px 12px;font-size:12.5px;font-weight:700;color:#66748a;cursor:pointer}
        .lc-seg button.on{background:#1268d3;color:#fff}
        .lc-chip{display:inline-flex;align-items:center;gap:6px;border:1.5px solid #cdd9ea;background:#fff;border-radius:999px;padding:4px 12px;font-size:12.5px;font-weight:700;color:#66748a;cursor:pointer;line-height:1}
        .lc-chip.on{color:#fff}
        .lc-chip i{width:8px;height:8px;border-radius:50%;flex:none}
        .lc-card{background:#fff;border:1px solid #e3e9f2;border-radius:12px;padding:14px 16px;margin-bottom:14px}
        .lc-card-h{margin:0 0 10px;font-size:14.5px;font-weight:800;color:#1f2a37}
        .lc-card-h .muted{font-size:11.5px;font-weight:500;margin-left:6px}
        .lc-table{width:100%;border-collapse:collapse;font-size:13px}
        .lc-table th{text-align:right;font-size:11.5px;color:#66748a;font-weight:700;padding:6px 8px;border-bottom:1.5px solid #e3e9f2;white-space:nowrap}
        .lc-table th:first-child,.lc-table td:first-child{text-align:left}
        .lc-table td{text-align:right;padding:6px 8px;border-bottom:1px solid #f0f4fa;font-variant-numeric:tabular-nums;white-space:nowrap}
        .lc-table td:first-child{font-weight:700;color:#1f2a37}
        .lc-table .lc-nat{background:#f3f8ff}
        .lc-table .lc-nat td{border-bottom:1.5px solid #dbe7f7}
        .lc-table .lc-delta{font-size:12px;font-weight:700}
        @media (max-width:640px){.lc-hero{padding:16px 18px}.lc-hero-num{font-size:32px}.lc-hero-split{width:100%}.lc-kp{flex:1;min-width:0}}
      `}</style>
    </div>
  );
}
