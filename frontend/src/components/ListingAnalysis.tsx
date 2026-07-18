import { useEffect, useMemo, useState } from "react";
import {
  Bar, CartesianGrid, ComposedChart, Legend, Line,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE;

// 단지매물분석 — complex_daily_agg 일자별 원자료(면적×거래유형)로
// 매물수·실매물수·평균호가 1달 추이를 그린다. 대시보드(compact)와 탭 양쪽에서 사용.
type LDRow = {
  d: string; area: string; t: string;
  n: number; u: number | null;
  avg: number | null; min: number | null; max: number | null; ravg: number | null;
};

const TRADE_TABS = [["A1", "매매"], ["B1", "전세"], ["B2", "월세"]] as const;

function fmtEok(v: number): string {
  if (v >= 1e8) return `${(v / 1e8).toFixed(v < 10e8 ? 1 : 1)}억`;
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}

const areaNum = (a: string) => {
  const m = a.match(/[0-9.]+/);
  return m ? parseFloat(m[0]) : Number.MAX_SAFE_INTEGER;
};

export default function ListingAnalysis({ complexNo, compact, onMore }: {
  complexNo: string; compact?: boolean; onMore?: () => void;
}) {
  const [rows, setRows] = useState<LDRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState<"A1" | "B1" | "B2">("A1");
  const [area, setArea] = useState("");   // ""=전체(매물수 가중평균)

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/complex/${complexNo}/listing-daily?days=31`);
        if (!r.ok) throw new Error(String(r.status));
        const j = await r.json();
        if (!cancelled) setRows(j.rows as LDRow[]);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => { cancelled = true; };
  }, [complexNo]);

  const tradeRows = useMemo(() => (rows ?? []).filter((r) => r.t === tab), [rows, tab]);
  const areas = useMemo(
    () => Array.from(new Set(tradeRows.map((r) => r.area)))
      .sort((x, y) => areaNum(x) - areaNum(y) || x.localeCompare(y)),
    [tradeRows],
  );

  const data = useMemo(() => {
    const byDay = new Map<string, { n: number; u: number; uSeen: boolean; ps: number; pw: number }>();
    for (const r of tradeRows) {
      if (area && r.area !== area) continue;
      const e = byDay.get(r.d) ?? { n: 0, u: 0, uSeen: false, ps: 0, pw: 0 };
      e.n += r.n;
      if (r.u != null) { e.u += r.u; e.uSeen = true; }
      const price = tab === "B2" ? r.ravg : r.avg;   // 월세는 평균 월세로
      if (price != null && r.n > 0) { e.ps += price * r.n; e.pw += r.n; }
      byDay.set(r.d, e);
    }
    return Array.from(byDay.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([d, e]) => ({
        d, label: `${parseInt(d.slice(5, 7), 10)}.${d.slice(8, 10)}`,
        n: e.n, u: e.uSeen ? e.u : null,
        price: e.pw > 0 ? e.ps / e.pw : null,
      }));
  }, [tradeRows, area, tab]);

  if (failed) return null;
  if (!rows) return compact ? null : <div className="muted">매물 추이를 불러오는 중…</div>;
  if (data.length === 0) {
    return compact ? null : <div className="muted">최근 1달 {TRADE_TABS.find(([k]) => k === tab)?.[1]} 매물 데이터가 없습니다.</div>;
  }

  const last = data[data.length - 1];
  const first = data[0];
  const dN = last.n - first.n;
  const priceLabel = tab === "A1" ? "평균 매매호가" : tab === "B1" ? "평균 전세호가" : "평균 월세";
  const fmtPrice = (v: number) => (tab === "B2" ? `${Math.round(v / 1e4).toLocaleString()}만` : fmtEok(v));

  return (
    <div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
        <div className="chip-row" style={{ marginBottom: 0 }}>
          {TRADE_TABS.map(([k, label]) => (
            <button key={k} type="button" className={`chip ${tab === k ? "active" : ""}`}
              onClick={() => { setTab(k); setArea(""); }}>{label}</button>
          ))}
        </div>
        {!compact && areas.length > 1 && (
          <select value={area} onChange={(e) => setArea(e.target.value)} style={{ fontSize: 12 }}>
            <option value="">전체 면적</option>
            {areas.map((a) => <option key={a} value={a}>{a}㎡</option>)}
          </select>
        )}
        <span className="muted" style={{ fontSize: 12 }}>
          현재 광고 {last.n}건{last.u != null ? ` · 실매물 ${last.u}건` : ""}
          {dN !== 0 ? ` · 1달 ${dN > 0 ? "+" : ""}${dN}건` : " · 1달 보합"}
          {last.price != null ? ` · ${priceLabel} ${fmtPrice(last.price)}` : ""}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={compact ? 190 : 280}>
        <ComposedChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e8edf3" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={18} />
          <YAxis yAxisId="cnt" tick={{ fontSize: 11 }} allowDecimals={false} width={34} />
          <YAxis yAxisId="price" orientation="right" tick={{ fontSize: 11 }} width={46}
            domain={["auto", "auto"]} tickFormatter={(v: number) => fmtPrice(v)} />
          <Tooltip
            formatter={(v, name) => {
              const num = typeof v === "number" ? v : Number(v);
              return name === priceLabel ? [fmtPrice(num), name] : [`${num}건`, name];
            }}
            labelFormatter={(l) => `${l} 기준`} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar yAxisId="cnt" dataKey="n" name="광고매물" fill="#a8c6ec" radius={[2, 2, 0, 0]} />
          <Bar yAxisId="cnt" dataKey="u" name="실매물(중복 합침)" fill="#1268d3" radius={[2, 2, 0, 0]} />
          <Line yAxisId="price" dataKey="price" name={priceLabel} stroke="#e2574c"
            strokeWidth={2} dot={false} connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
      {!compact && (
        <div className="muted" style={{ fontSize: 11.5, marginTop: 4 }}>
          광고매물=네이버 광고 건수, 실매물=같은 집 중복 광고를 합친 수. {priceLabel}은 매물수 가중평균
          {area ? "" : " (면적 구성이 바뀌면 값이 출렁일 수 있어 면적을 선택하면 정확)"}.
        </div>
      )}
      {compact && onMore && (
        <button className="cdash-more" style={{ marginTop: 2 }} onClick={onMore}>자세히 보기 →</button>
      )}
    </div>
  );
}
