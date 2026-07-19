import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/Loading";
import {
  CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE;

// 단지비교 — 두 단지의 개요·호가·실거래·유동성·입지를 한 표로. 데이터는 /stats/complex-compare.
type Cx = {
  complex_no: string; name: string; region: string; built: string | null;
  area: string | null; areas: { name: string; supply: number | null; excl: number | null; hh: number | null }[];
  households: number | null; buildings: number | null; parking: number | null;
  builder: string | null; type: string | null;
  listings: Record<string, { n: number; units: number | null; min: number | null; avg: number | null; rent_avg: number | null }>;
  jeonse_rate: number | null; gap: number | null;
  tx: {
    n12: number; avg6m: number | null; pyeong6m: number | null;
    latest: { date: string; price: number; area: number; floor: number } | null;
    record: { price: number; date: string; area: string } | null;
    turnover: number | null;
  };
  subway: { station: string; lines: string; walk: number } | null;
  school: { name: string; walk: number } | null;
  n_realtors: number; quick_deals: number | null;
  series: { d: string; n: number; u: number | null; avg: number | null }[];
};

const A_COLOR = "#1268d3", B_COLOR = "#e2882e";

function won(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 1e8) {
    const eok = Math.floor(v / 1e8), man = Math.round((v % 1e8) / 1e4);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}
const dot = (d?: string | null) => (d ? d.slice(2).replace(/-/g, ".") : "-");

function SearchBox({ label, color, sel, onSel }: {
  label: string; color: string; sel: any; onSel: (c: any) => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  useEffect(() => {
    const qq = q.trim();
    if (qq.length < 2 || (sel && qq === sel.complex_name)) { setResults([]); return; }
    const t = setTimeout(() => {
      fetch(`${API_BASE}/complexes/search?q=${encodeURIComponent(qq)}`)
        .then((r) => r.json()).then((j) => setResults(j.items ?? [])).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line
  return (
    <div style={{ flex: "1 1 260px" }}>
      <div style={{ fontSize: 12.5, fontWeight: 750, color, marginBottom: 4 }}>{label}</div>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="단지명 검색 (2자 이상)"
        style={{ width: "100%", boxSizing: "border-box" }} />
      {results.length > 0 && (
        <div className="chip-row" style={{ marginTop: 5 }}>
          {results.slice(0, 6).map((c) => (
            <button key={c.complex_no} type="button" className="chip"
              onClick={() => { onSel(c); setQ(c.complex_name); setResults([]); }}>
              {c.complex_name} <span style={{ color: "#8a97a8" }}>
                {(c.region || "").split(" ").slice(-1)[0]}{c.households ? `·${c.households}세대` : ""}</span>
            </button>
          ))}
        </div>
      )}
      {sel && <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>{sel.region}</div>}
    </div>
  );
}

export default function ComplexCompare() {
  const [selA, setSelARaw] = useState<any>(null);
  const [selB, setSelBRaw] = useState<any>(null);
  const [areaA, setAreaA] = useState("");
  const [areaB, setAreaB] = useState("");
  // 단지를 바꾸면 그 쪽 평형 선택은 초기화
  const setSelA = (c: any) => { setSelARaw(c); setAreaA(""); };
  const setSelB = (c: any) => { setSelBRaw(c); setAreaB(""); };
  const [data, setData] = useState<{ a: Cx; b: Cx } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!selA || !selB) { setData(null); return; }
    setLoading(true); setError(false);
    fetch(`${API_BASE}/stats/complex-compare?a=${selA.complex_no}&b=${selB.complex_no}`
      + `&a_area=${encodeURIComponent(areaA)}&b_area=${encodeURIComponent(areaB)}`)
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setData).catch(() => { setData(null); setError(true); })
      .finally(() => setLoading(false));
  }, [selA, selB, areaA, areaB]);

  const chart = useMemo(() => {
    if (!data) return [];
    const m = new Map<string, any>();
    for (const p of data.a.series) m.set(p.d, { d: p.d, label: `${parseInt(p.d.slice(5, 7), 10)}.${p.d.slice(8, 10)}`, aAvg: p.avg, aU: p.u });
    for (const p of data.b.series) {
      const e = m.get(p.d) ?? { d: p.d, label: `${parseInt(p.d.slice(5, 7), 10)}.${p.d.slice(8, 10)}` };
      e.bAvg = p.avg; e.bU = p.u; m.set(p.d, e);
    }
    return [...m.values()].sort((x, y) => x.d.localeCompare(y.d));
  }, [data]);

  const rows: [string, (c: Cx) => string][] = [
    ["준공", (c) => c.built ?? "-"],
    ["세대수", (c) => `${c.households?.toLocaleString() ?? "-"}${c.area ? " (평형)" : ""}`],
    ["동 수", (c) => c.buildings != null ? `${c.buildings}동` : "-"],
    ["세대당 주차", (c) => c.parking != null ? `${c.parking}대` : "-"],
    ["시공사", (c) => (c.builder ?? "-").split(",")[0]],
    ["매매 호가 (최저~평균)", (c) => c.listings.A1 ? `${won(c.listings.A1.min)} ~ ${won(c.listings.A1.avg)}` : "-"],
    ["전세 호가 (최저~평균)", (c) => c.listings.B1 ? `${won(c.listings.B1.min)} ~ ${won(c.listings.B1.avg)}` : "-"],
    ["평균 월세", (c) => c.listings.B2?.rent_avg ? `${Math.round(c.listings.B2.rent_avg / 1e4).toLocaleString()}만` : "-"],
    ["매매 매물 (광고/실)", (c) => c.listings.A1 ? `${c.listings.A1.n} / ${c.listings.A1.units ?? "-"}건` : "-"],
    ["전세가율 (호가)", (c) => c.jeonse_rate != null ? `${c.jeonse_rate}%` : "-"],
    ["갭 (매매-전세 평균)", (c) => won(c.gap)],
    ["최근 실거래", (c) => c.tx.latest ? `${won(c.tx.latest.price)} · ${dot(c.tx.latest.date)}` : "-"],
    ["6개월 실거래 평균", (c) => won(c.tx.avg6m)],
    ["평당 실거래가 (3.3㎡)", (c) => won(c.tx.pyeong6m)],
    ["역대 신고가", (c) => c.tx.record ? `${won(c.tx.record.price)} · ${dot(c.tx.record.date)}` : "-"],
    ["12개월 거래량", (c) => `${c.tx.n12.toLocaleString()}건`],
    ["연 회전율 (거래/세대)", (c) => c.tx.turnover != null ? `${c.tx.turnover}%` : "-"],
    ["급매 (실거래 대비 저가)", (c) => c.quick_deals != null ? `${c.quick_deals}건` : "-"],
    ["지하철", (c) => c.subway ? `${c.subway.station} 도보 ${c.subway.walk}분` : "-"],
    ["배정 초등학교", (c) => c.school ? `${c.school.name.replace("등학교", "")} 도보 ${c.school.walk}분` : "-"],
    ["취급 중개사무소", (c) => `${c.n_realtors}곳`],
  ];

  return (
    <div>
      <Link to="/finder" className="back">← 맞춤단지</Link>
      <div className="section-title" style={{ marginTop: 4 }}>
        단지비교 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>두 단지의 시세·실거래·매물·입지를 한 표로</span>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 14 }}>
        <SearchBox label="단지 A" color={A_COLOR} sel={selA} onSel={setSelA} />
        <SearchBox label="단지 B" color={B_COLOR} sel={selB} onSel={setSelB} />
      </div>

      {data && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
          {([["A", data.a, areaA, setAreaA], ["B", data.b, areaB, setAreaB]] as const).map(([lbl, c, val, set]) => (
            <label key={lbl} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, fontWeight: 700,
              color: lbl === "A" ? A_COLOR : B_COLOR }}>
              {c.name} 평형
              <select value={val} onChange={(e) => set(e.target.value)} style={{ fontSize: 12.5 }}>
                <option value="">전체 평형</option>
                {c.areas.map((ar) => (
                  <option key={ar.name} value={ar.name}>
                    {ar.name}{ar.excl != null ? ` · 전용 ${ar.excl}㎡` : ""}{ar.hh ? ` · ${ar.hh}세대` : ""}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      )}

      {!selA || !selB ? (
        <div className="muted">비교할 두 단지를 검색해 선택하세요.</div>
      ) : error ? <div className="muted">비교 데이터를 불러오지 못했습니다 — 잠시 후 다시 선택해 주세요.</div>
      : loading || !data ? <Loading /> : (
        <>
          <table style={{ width: "100%" }}>
            <thead>
              <tr>
                <th style={{ width: "34%" }}>지표</th>
                <th style={{ color: A_COLOR }}>{data.a.name}{data.a.area ? ` · ${data.a.area}` : ""}</th>
                <th style={{ color: B_COLOR }}>{data.b.name}{data.b.area ? ` · ${data.b.area}` : ""}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="muted">위치</td>
                <td style={{ fontSize: 12.5 }}>{data.a.region}</td>
                <td style={{ fontSize: 12.5 }}>{data.b.region}</td>
              </tr>
              {rows.map(([label, get]) => (
                <tr key={label}>
                  <td className="muted">{label}</td>
                  <td>{get(data.a)}</td>
                  <td>{get(data.b)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {chart.length > 1 && (
            <>
              <div className="section-title" style={{ marginTop: 18 }}>
                최근 1달 평균 매매호가 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>일자별</span>
              </div>
              <ResponsiveContainer width="100%" height={230}>
                <ComposedChart data={chart} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e8edf3" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={22} />
                  <YAxis tick={{ fontSize: 11 }} width={50} domain={["auto", "auto"]}
                    tickFormatter={(v: number) => `${(v / 1e8).toFixed(1)}억`} />
                  <Tooltip formatter={(v) => won(typeof v === "number" ? v : Number(v))}
                    labelFormatter={(l) => `${l} 기준`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line dataKey="aAvg" name={data.a.name} stroke={A_COLOR} strokeWidth={2} dot={false} connectNulls />
                  <Line dataKey="bAvg" name={data.b.name} stroke={B_COLOR} strokeWidth={2} dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </>
          )}
          <div className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>
            호가는 현재 등록 매물 기준(실매물=중복 광고 합침), 실거래는 국토부 신고(해제 제외).
            전세가율·갭은 선택 범위(전체/평형) 호가 가중평균. 평형 선택 시 실거래·신고가·회전율은 해당 평형 전용면적 ±1.5㎡ 기준.
          </div>
        </>
      )}
    </div>
  );
}
