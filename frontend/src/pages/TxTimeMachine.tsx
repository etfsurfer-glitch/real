import { useEffect, useMemo, useRef, useState } from "react";
import { Loading } from "../components/Loading";
import {
  Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE;

// 부동산타임머신 — 정책·규제 연대기(발표일 기준 큐레이션) + 시장 반응(전국 아파트 월별).
// 이벤트 날짜·내용은 백엔드 _TIMEMACHINE_EVENTS(공식 발표 검증)만 사용 — 프론트에서 임의 추가 금지.
type Ev = { d: string; cat: string; title: string; desc: string; src: string };
type Pt = { m: string; n: number; avg: number };

const CAT_COLOR: Record<string, string> = {
  강화: "#d23b3b", 완화: "#1268d3", 공급: "#159570", 거시: "#6b7a90", 제도: "#8250c8",
};

const fmtEok = (v: number) => `${(v / 1e8).toFixed(1)}억`;
const monLabel = (m: string) => `${m.slice(2, 4)}.${m.slice(5, 7)}`;

export default function TxTimeMachine() {
  const [data, setData] = useState<{ series: Pt[]; events: Ev[]; data_from: string | null } | null>(null);
  const [failed, setFailed] = useState(false);
  const [sel, setSel] = useState<string | null>(null);   // 선택 이벤트 날짜
  const [catFilter, setCatFilter] = useState<string>("");
  const [span, setSpan] = useState<number>(0);   // 0=전체, N=최근 N개월
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/stats/timemachine`).then((r) => r.json())
      .then(setData).catch(() => setFailed(true));
  }, []);

  const fullSeries = data?.series ?? [];
  const series = span > 0 ? fullSeries.slice(-span) : fullSeries;
  const dataFrom = data?.data_from ?? "";
  const chartFrom = series[0]?.m ?? dataFrom;
  const events = useMemo(
    () => [...(data?.events ?? [])].sort((a, b) => b.d.localeCompare(a.d)),
    [data],
  );
  const inRange = (e: Ev) => dataFrom !== "" && e.d.slice(0, 7) >= dataFrom;
  const inChart = (e: Ev) => chartFrom !== "" && e.d.slice(0, 7) >= chartFrom;
  const chartEvents = useMemo(() => (data?.events ?? []).filter(inChart), [data, span]); // eslint-disable-line

  // 연도별 그룹(내림차순)
  const byYear = useMemo(() => {
    const g = new Map<string, Ev[]>();
    for (const e of events) {
      if (catFilter && e.cat !== catFilter) continue;
      const y = e.d.slice(0, 4);
      (g.get(y) ?? g.set(y, []).get(y)!).push(e);
    }
    return [...g.entries()];
  }, [events, catFilter]);

  if (failed) return <div className="muted">타임머신 데이터를 불러오지 못했습니다.</div>;
  if (!data) return <Loading />;

  const selEv = sel ? events.find((e) => e.d === sel) : null;
  const selMonth = selEv?.d.slice(0, 7);
  const selPt = selMonth ? series.find((p) => p.m === selMonth) : null;
  const prevPt = selMonth ? series[series.findIndex((p) => p.m === selMonth) - 1] : null;

  const pickEvent = (e: Ev) => {
    const next = e.d === sel ? null : e.d;
    setSel(next);
    if (next && inRange(e)) {
      if (!inChart(e)) setSpan(0);   // 현재 구간 밖 → 전체 구간으로 펼쳐 마커 노출
      chartRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <div>
      <div className="section-title" style={{ marginTop: 4 }}>
        부동산타임머신 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>
          20년 정책·규제 연대기와 시장 반응 · 발표일 기준</span>
      </div>

      {/* 시장 반응 차트 — 콕집 DB 구간 */}
      <div ref={chartRef} style={{ scrollMarginTop: 70 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 4 }}>
          <div className="chip-row" style={{ marginBottom: 0 }}>
            {([[0, "전체"], [120, "10년"], [60, "5년"], [36, "3년"]] as const).map(([n, l]) => (
              <button key={n} type="button" className={`chip ${span === n ? "active" : ""}`}
                onClick={() => setSpan(n)}>{l}</button>
            ))}
          </div>
          <span className="muted" style={{ fontSize: 12 }}>
            전국 아파트 매매 거래량·평균 거래가 (월별, {dataFrom.replace("-", ".")}~ · 해제거래 제외 · 최근 1~2개월은 신고 진행 중)
          </span>
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={series} margin={{ top: 22, right: 6, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e8edf3" />
            <XAxis dataKey="m" tickFormatter={monLabel} tick={{ fontSize: 11 }} minTickGap={26} />
            <YAxis yAxisId="n" tick={{ fontSize: 11 }} width={44}
              tickFormatter={(v: number) => `${Math.round(v / 1000)}천`} />
            <YAxis yAxisId="avg" orientation="right" tick={{ fontSize: 11 }} width={44}
              domain={["auto", "auto"]} tickFormatter={(v: number) => fmtEok(v)} />
            <Tooltip
              formatter={(v, name) => {
                const num = typeof v === "number" ? v : Number(v);
                return name === "평균 거래가" ? [fmtEok(num), name] : [`${num.toLocaleString()}건`, name];
              }}
              labelFormatter={(m) => `${String(m).replace("-", "년 ")}월`} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar yAxisId="n" dataKey="n" name="거래량" fill="#a8c6ec" radius={[2, 2, 0, 0]} />
            <Line yAxisId="avg" dataKey="avg" name="평균 거래가" stroke="#e2574c" strokeWidth={2} dot={false} />
            {chartEvents.map((e) => {
              const on = sel === e.d;
              return (
                <ReferenceLine key={e.d} yAxisId="n" x={e.d.slice(0, 7)}
                  stroke={CAT_COLOR[e.cat] ?? "#888"} strokeWidth={on ? 2.4 : 1.2}
                  strokeDasharray={on ? undefined : "4 3"} opacity={on ? 1 : 0.75}
                  label={{
                    value: `${parseInt(e.d.slice(5, 7), 10)}·${parseInt(e.d.slice(8, 10), 10)}`,
                    position: "top", fontSize: on ? 12 : 10.5,
                    fill: CAT_COLOR[e.cat] ?? "#888", fontWeight: on ? 800 : 600,
                  }} />
              );
            })}
          </ComposedChart>
        </ResponsiveContainer>
        {selEv && (
          <div style={{ background: "#f2f6fb", borderRadius: 12, padding: "10px 14px", margin: "6px 0 2px", fontSize: 13 }}>
            <b style={{ color: CAT_COLOR[selEv.cat] }}>{selEv.d.replace(/-/g, ".")} {selEv.title}</b>
            {" — "}{selEv.desc}
            {selPt && (
              <span className="muted" style={{ display: "block", marginTop: 3, fontSize: 12 }}>
                당월 전국 거래 {selPt.n.toLocaleString()}건
                {prevPt ? ` (전월 ${prevPt.n.toLocaleString()}건)` : ""} · 평균 {fmtEok(selPt.avg)}
              </span>
            )}
            {!inRange(selEv) && (
              <span className="muted" style={{ display: "block", marginTop: 3, fontSize: 12 }}>
                콕집 실거래 데이터 구간({dataFrom.replace("-", ".")}~) 이전의 사건이라 차트에는 표시되지 않습니다.
              </span>
            )}
          </div>
        )}
      </div>

      {/* 연대기 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "16px 0 8px", flexWrap: "wrap" }}>
        <div className="section-title" style={{ margin: 0 }}>연대기</div>
        <div className="chip-row" style={{ marginBottom: 0 }}>
          <button type="button" className={`chip ${catFilter === "" ? "active" : ""}`} onClick={() => setCatFilter("")}>전체</button>
          {Object.keys(CAT_COLOR).map((c) => (
            <button key={c} type="button" className={`chip ${catFilter === c ? "active" : ""}`}
              onClick={() => setCatFilter(catFilter === c ? "" : c)}>{c}</button>
          ))}
        </div>
      </div>

      {byYear.map(([year, evs]) => (
        <div key={year} style={{ marginBottom: 10 }}>
          <div style={{ fontWeight: 800, fontSize: 15, color: "#33415b", margin: "10px 0 6px" }}>{year}</div>
          {evs.map((e) => (
            <button key={e.d} type="button" onClick={() => pickEvent(e)}
              style={{
                display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                background: sel === e.d ? "#eef4fc" : "#fff",
                border: `1px solid ${sel === e.d ? "#b9d2f0" : "#e5ebf3"}`,
                borderLeft: `4px solid ${CAT_COLOR[e.cat] ?? "#888"}`,
                borderRadius: 10, padding: "9px 12px", marginBottom: 6, fontFamily: "inherit",
              }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span style={{ fontSize: 12.5, fontWeight: 700, color: "#5a6b80", fontVariantNumeric: "tabular-nums" }}>
                  {e.d.replace(/-/g, ".")}
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 750, color: "#fff", borderRadius: 999,
                  padding: "1.5px 8px", background: CAT_COLOR[e.cat] ?? "#888",
                }}>{e.cat}</span>
                <span style={{ fontSize: 14, fontWeight: 750, color: "#1f2c40" }}>{e.title}</span>
                {inRange(e) && <span style={{ fontSize: 11, color: "#1268d3", fontWeight: 650 }}>차트 연동</span>}
              </div>
              <div style={{ fontSize: 12.5, color: "#5f6e83", marginTop: 3, lineHeight: 1.5 }}>
                {e.desc} <span style={{ color: "#9aa4b0" }}>· {e.src}</span>
              </div>
            </button>
          ))}
        </div>
      ))}

      <div className="muted" style={{ fontSize: 11.5, marginTop: 10, lineHeight: 1.6 }}>
        이벤트는 정부·한국은행 등 공식 발표(발표일 기준)만 수록한 큐레이션이며, 시장 해석을 담지 않습니다.
        거래량·평균가는 국토교통부 실거래 신고(해제거래 제외)를 콕집이 집계한 것으로, 데이터 구간은
        {" "}{dataFrom.replace("-", ".")}부터입니다. 평균 거래가는 거래 구성(지역·면적)에 따라 출렁일 수 있습니다.
      </div>
    </div>
  );
}
