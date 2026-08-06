import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { createPortal } from "react-dom";
import { GitCompareArrows, Search, X, TrendingUp } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { Loading } from "../components/Loading";
import { areaLabel } from "../lib/area";

const API = import.meta.env.VITE_API_BASE;

// 유사 단지 (관리자 가오픈) — 기준 단지·평형의 실거래가 흐름(월평균)과
// 상관도가 높은 단지를 찾아 비교. 유사도 클릭 → 두 단지 시계열 겹쳐보기.
type SearchItem = { complex_no: string; complex_name: string; region?: string; households?: number };
type AreaT = { pyeong_name: string; exclusive_area: number | null };
type SimItem = {
  complex_no: string; complex_name: string; region: string;
  households: number | null; approve_year: string | null;
  similarity: number; months: number;
  recent_avg: number | null; diff_pct: number | null;
  ask: { n: number; min: number | null };
  record_high: number | null; vs_peak_pct: number | null;
  series: [string, number][];
};
type SimRes = {
  reference: { complex_no: string; complex_name: string; excl: number;
    recent_avg: number | null; series: [string, number][] } | null;
  items: SimItem[]; note?: string; years: number; min_common_months: number;
};

function eok(won: number | null | undefined): string {
  if (won == null) return "—";
  const e = won / 100_000_000;
  return `${e >= 100 ? Math.round(e).toLocaleString() : e.toFixed(1)}억`;
}

export default function SimilarComplexes() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchItem[] | null>(null);
  const [base, setBase] = useState<SearchItem | null>(null);
  const [areas, setAreas] = useState<AreaT[]>([]);
  const [areaName, setAreaName] = useState("");
  const [years, setYears] = useState(3);
  const [scope, setScope] = useState("sido");
  const [res, setRes] = useState<SimRes | null>(null);
  const [busy, setBusy] = useState(false);
  const [chartOf, setChartOf] = useState<SimItem | null>(null);
  const timer = useRef<number>();

  // 검색 (디바운스)
  useEffect(() => {
    if (q.trim().length < 2) { setHits(null); return; }
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      fetch(`${API}/complexes/search?q=${encodeURIComponent(q.trim())}&limit=8`)
        .then((r) => r.json()).then((d) => setHits(d.items || [])).catch(() => setHits([]));
    }, 250);
  }, [q]);

  const pick = useCallback((it: SearchItem) => {
    setBase(it); setHits(null); setQ(""); setAreaName(""); setRes(null);
    setSp({ base: it.complex_no }, { replace: true });
    fetch(`${API}/complex/${it.complex_no}/areas`)
      .then((r) => r.json())
      .then((d) => setAreas((d.areas || d.items || []).filter((a: AreaT) => a.pyeong_name)))
      .catch(() => setAreas([]));
  }, [setSp]);

  // ?base= 딥링크 (관심단지 카드에서 진입)
  useEffect(() => {
    const b = sp.get("base");
    if (b && !base) {
      fetch(`${API}/complexes/search?q=${encodeURIComponent(b)}&limit=1`).catch(() => {});
      fetch(`${API}/complex/${b}/summary`)
        .then((r) => r.json())
        .then((d) => pick({ complex_no: b, complex_name: d.complex_name, region: d.region }))
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = useCallback(() => {
    if (!base) return;
    setBusy(true); setRes(null);
    const qs = `complex_no=${base.complex_no}&years=${years}&scope=${scope}` +
      (areaName ? `&area_name=${encodeURIComponent(areaName)}` : "");
    fetch(`${API}/stats/similar-complexes?${qs}`)
      .then((r) => r.json()).then(setRes)
      .catch(() => setRes({ reference: null, items: [], note: "조회 실패", years, min_common_months: 0 }))
      .finally(() => setBusy(false));
  }, [base, areaName, years, scope]);

  useEffect(() => { if (base) run(); }, [base, areaName, years, scope, run]);

  return (
    <section>
      <h2 style={{ display: "flex", alignItems: "center", gap: 8, margin: "0 0 4px" }}>
        <GitCompareArrows size={20} strokeWidth={2.2} aria-hidden /> 유사 단지
        <span className="admin-preview-badge">관리자 가오픈</span>
      </h2>
      <p className="muted" style={{ margin: "4px 0 14px", fontSize: 13 }}>
        기준 단지와 <b>실거래가 흐름이 비슷하게 움직인 단지</b>를 찾아드려요.
        유사도가 높은데 아직 덜 오른(차이 마이너스) 단지가 키맞추기 후보입니다.
      </p>

      {/* 기준 단지 검색 */}
      <div className="simx-search">
        <Search size={15} aria-hidden />
        <input
          value={q} onChange={(e) => setQ(e.target.value)}
          placeholder={base ? `기준: ${base.complex_name} — 다른 단지로 바꾸려면 검색` : "단지명 검색 (예: 헬리오시티)"}
        />
        {hits && hits.length > 0 && (
          <div className="simx-hits">
            {hits.map((h) => (
              <button key={h.complex_no} type="button" onClick={() => pick(h)}>
                <b>{h.complex_name}</b><span>{h.region || ""}{h.households ? ` · ${h.households.toLocaleString()}세대` : ""}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {base && (
        <div className="simx-controls">
          <span className="simx-base"><TrendingUp size={13} aria-hidden /> 기준 <b>{base.complex_name}</b>
            {res?.reference && <em> {areaLabel(res.reference.excl)} · 최근 6개월 평균 {eok(res.reference.recent_avg)}</em>}
          </span>
          <select value={areaName} onChange={(e) => setAreaName(e.target.value)}>
            <option value="">거래 최다 평형</option>
            {areas.map((a) => (
              <option key={a.pyeong_name} value={a.pyeong_name}>
                {a.pyeong_name}{a.exclusive_area ? ` · 전용 ${Math.round(a.exclusive_area)}㎡` : ""}
              </option>
            ))}
          </select>
          <select value={years} onChange={(e) => setYears(Number(e.target.value))}>
            <option value={1}>최근 1년</option><option value={3}>최근 3년</option><option value={5}>최근 5년</option>
          </select>
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="sigungu">같은 시군구</option><option value="sido">같은 시도</option><option value="national">전국</option>
          </select>
        </div>
      )}

      {busy && <Loading label="흐름이 비슷한 단지를 찾는 중…" />}
      {res?.note && <div className="modal-msg">{res.note}</div>}

      {res && res.items.length > 0 && (
        <div className="table-scroll">
          <table className="simx-table">
            <thead>
              <tr>
                <th>유사도</th><th>단지</th><th>지역</th><th className="num">연식</th>
                <th className="num">세대</th><th className="num">최근 평균가</th>
                <th className="num">기준 대비</th><th className="num">매물(최저)</th>
                <th className="num">전고점 대비</th>
              </tr>
            </thead>
            <tbody>
              {res.items.map((it) => (
                <tr key={it.complex_no}>
                  <td>
                    <button type="button" className="simx-sim" title="클릭하면 기준 단지와 실거래가 흐름을 겹쳐 보여드려요"
                      onClick={() => setChartOf(it)}>{it.similarity}%</button>
                  </td>
                  <td><Link to={`/complex/${it.complex_no}`}>{it.complex_name}</Link></td>
                  <td className="muted" style={{ fontSize: 12 }}>{it.region}</td>
                  <td className="num">{it.approve_year ?? "—"}</td>
                  <td className="num">{it.households?.toLocaleString() ?? "—"}</td>
                  <td className="num"><b>{eok(it.recent_avg)}</b></td>
                  <td className="num">
                    {it.diff_pct == null ? "—" : (
                      <span style={{ fontWeight: 700, color: it.diff_pct < 0 ? "#1268d3" : "#c0392b" }}>
                        {it.diff_pct > 0 ? "+" : ""}{it.diff_pct}%
                      </span>
                    )}
                  </td>
                  <td className="num">{it.ask.n > 0 ? <>{it.ask.n}건 {it.ask.min ? `(${eok(it.ask.min)})` : ""}</> : "—"}</td>
                  <td className="num">{it.vs_peak_pct == null ? "—" : `${it.vs_peak_pct}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {res && res.items.length > 0 && (
        <p className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>
          유사도 = 최근 {res.years}년 월평균 실거래가 흐름의 상관도(겹치는 관측월 {res.min_common_months}개 이상).
          최근 평균가 = 최근 6개월 실거래 가중평균. 해제거래·직거래 제외.
        </p>
      )}

      {chartOf && res?.reference && (
        <SimChartModal refItem={res.reference} cand={chartOf} onClose={() => setChartOf(null)} />
      )}
    </section>
  );
}

function SimChartModal({ refItem, cand, onClose }: {
  refItem: { complex_name: string; series: [string, number][] };
  cand: SimItem; onClose: () => void;
}) {
  const map = new Map<string, { ym: string; ref?: number; cand?: number }>();
  for (const [ym, v] of refItem.series) map.set(ym, { ym, ref: +(v / 1e8).toFixed(2) });
  for (const [ym, v] of cand.series) {
    const row = map.get(ym) || { ym };
    row.cand = +(v / 1e8).toFixed(2);
    map.set(ym, row);
  }
  const data = [...map.values()].sort((a, b) => a.ym.localeCompare(b.ym));
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: 640, width: "calc(100vw - 32px)" }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">실거래가 흐름 비교 · 유사도 {cand.similarity}%</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>
        <div style={{ width: "100%", height: 300 }}>
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef1f6" />
              <XAxis dataKey="ym" tick={{ fontSize: 10 }} minTickGap={28} />
              <YAxis tick={{ fontSize: 10 }} width={44} domain={["auto", "auto"]}
                tickFormatter={(v: number) => `${v}억`} />
              <Tooltip formatter={(v) => `${v}억`} labelStyle={{ fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line name={refItem.complex_name} type="monotone" dataKey="ref" stroke="#1268d3" strokeWidth={2} dot={false} connectNulls />
              <Line name={cand.complex_name} type="monotone" dataKey="cand" stroke="#e0245e" strokeWidth={2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="muted" style={{ fontSize: 11.5, margin: "6px 0 0" }}>
          월평균 실거래가(같은 평형 밴드) · 겹치는 관측월 {cand.months}개 기준 상관도
        </p>
      </div>
    </div>,
    document.body,
  );
}
