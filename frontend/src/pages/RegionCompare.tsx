import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/Loading";
import {
  Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE;

// 지역비교 — 시도/시군구/동 임의 조합 2곳의 아파트 매매 지표 비교(/stats/region-compare2).
type Rg = {
  code: string; level: string; name: string;
  households: number; complexes: number;
  tx90: { n: number; avg: number | null; pyeong: number | null };
  n12: number; turnover: number | null;
  listings: Record<string, { n: number; units: number | null; avg: number | null }>;
  listing_per_hh: number | null; jeonse_rate: number | null;
  monthly: { m: string; n: number; avg: number | null }[];
};

const A_COLOR = "#1268d3", B_COLOR = "#e2882e";
type Opt = { code: string; name: string };

function won(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 1e8) {
    const eok = Math.floor(v / 1e8), man = Math.round((v % 1e8) / 1e4);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.round(v / 1e4).toLocaleString()}만`;
}

function RegionPicker({ label, color, onCode }: {
  label: string; color: string; onCode: (code: string | null) => void;
}) {
  const [sidos, setSidos] = useState<Opt[]>([]);
  const [sggs, setSggs] = useState<Opt[]>([]);
  const [dongs, setDongs] = useState<Opt[]>([]);
  const [sido, setSido] = useState("");
  const [sgg, setSgg] = useState("");
  const [dong, setDong] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/stats/changes/sido-list`).then((r) => r.json())
      .then((j) => setSidos(j.items ?? [])).catch(() => {});
  }, []);
  useEffect(() => {
    setSgg(""); setDong(""); setSggs([]); setDongs([]);
    if (!sido) return;
    fetch(`${API_BASE}/stats/sigungu-list?sido=${sido.slice(0, 2)}`).then((r) => r.json())
      .then((j) => setSggs(j.items ?? [])).catch(() => {});
  }, [sido]);
  useEffect(() => {
    setDong(""); setDongs([]);
    if (!sgg) return;
    fetch(`${API_BASE}/stats/dong-list?sigungu=${sgg.slice(0, 5)}`).then((r) => r.json())
      .then((j) => setDongs(j.items ?? [])).catch(() => {});
  }, [sgg]);
  useEffect(() => {
    onCode(dong ? dong.slice(0, 10) : sgg ? sgg.slice(0, 5) : sido ? sido.slice(0, 2) : null);
  }, [sido, sgg, dong]); // eslint-disable-line

  return (
    <div style={{ flex: "1 1 280px" }}>
      <div style={{ fontSize: 12.5, fontWeight: 750, color, marginBottom: 4 }}>{label}</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <select value={sido} onChange={(e) => setSido(e.target.value)}>
          <option value="">시·도 선택</option>
          {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value={sgg} onChange={(e) => setSgg(e.target.value)} disabled={!sido}>
          <option value="">시·군·구 전체</option>
          {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value={dong} onChange={(e) => setDong(e.target.value)} disabled={!sgg}>
          <option value="">읍·면·동 전체</option>
          {dongs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </div>
    </div>
  );
}

export default function RegionCompare() {
  const [codeA, setCodeA] = useState<string | null>(null);
  const [codeB, setCodeB] = useState<string | null>(null);
  const [data, setData] = useState<{ a: Rg; b: Rg } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!codeA || !codeB) { setData(null); return; }
    setLoading(true); setError(false);
    fetch(`${API_BASE}/stats/region-compare2?a=${codeA}&b=${codeB}`)
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setData).catch(() => { setData(null); setError(true); })
      .finally(() => setLoading(false));
  }, [codeA, codeB]);

  const chart = useMemo(() => {
    if (!data) return [];
    const m = new Map<string, any>();
    for (const p of data.a.monthly) m.set(p.m, { m: p.m, label: `${p.m.slice(2, 4)}.${p.m.slice(5, 7)}`, aN: p.n, aAvg: p.avg });
    for (const p of data.b.monthly) {
      const e = m.get(p.m) ?? { m: p.m, label: `${p.m.slice(2, 4)}.${p.m.slice(5, 7)}` };
      e.bN = p.n; e.bAvg = p.avg; m.set(p.m, e);
    }
    return [...m.values()].sort((x, y) => x.m.localeCompare(y.m));
  }, [data]);

  const rows: [string, (r: Rg) => string][] = [
    ["아파트 단지 수", (r) => r.complexes.toLocaleString()],
    ["총 세대수", (r) => r.households.toLocaleString()],
    ["90일 거래량", (r) => `${r.tx90.n.toLocaleString()}건`],
    ["90일 평균 거래가", (r) => won(r.tx90.avg)],
    ["평당 실거래가 (3.3㎡)", (r) => won(r.tx90.pyeong)],
    ["12개월 거래량", (r) => `${r.n12.toLocaleString()}건`],
    ["연 회전율 (거래/세대)", (r) => r.turnover != null ? `${r.turnover}%` : "-"],
    ["매매 매물 (광고/실)", (r) => r.listings.A1 ? `${r.listings.A1.n.toLocaleString()} / ${r.listings.A1.units?.toLocaleString() ?? "-"}건` : "-"],
    ["세대 대비 매물 비율", (r) => r.listing_per_hh != null ? `${r.listing_per_hh}%` : "-"],
    ["평균 매매호가", (r) => won(r.listings.A1?.avg)],
    ["평균 전세호가", (r) => won(r.listings.B1?.avg)],
    ["전세가율 (호가)", (r) => r.jeonse_rate != null ? `${r.jeonse_rate}%` : "-"],
  ];

  return (
    <div>
      <Link to="/finder" className="back">← 맞춤단지</Link>
      <div className="section-title" style={{ marginTop: 4 }}>
        지역비교 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>시·도, 시·군·구, 읍·면·동 어느 조합이든 두 지역을 비교</span>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 14 }}>
        <RegionPicker label="지역 A" color={A_COLOR} onCode={setCodeA} />
        <RegionPicker label="지역 B" color={B_COLOR} onCode={setCodeB} />
      </div>

      {!codeA || !codeB ? (
        <div className="muted">비교할 두 지역을 선택하세요 (시·도만 골라도 되고, 동까지 좁혀도 됩니다).</div>
      ) : error ? <div className="muted">비교 데이터를 불러오지 못했습니다 — 잠시 후 다시 선택해 주세요.</div>
      : loading || !data ? <Loading /> : (
        <>
          <table style={{ width: "100%" }}>
            <thead>
              <tr>
                <th style={{ width: "34%" }}>지표</th>
                <th style={{ color: A_COLOR }}>{data.a.name}</th>
                <th style={{ color: B_COLOR }}>{data.b.name}</th>
              </tr>
            </thead>
            <tbody>
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
                12개월 월별 거래량·평균가
              </div>
              <ResponsiveContainer width="100%" height={250}>
                <ComposedChart data={chart} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e8edf3" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={18} />
                  <YAxis yAxisId="n" tick={{ fontSize: 11 }} width={44} allowDecimals={false} />
                  <YAxis yAxisId="avg" orientation="right" tick={{ fontSize: 11 }} width={48}
                    domain={["auto", "auto"]} tickFormatter={(v: number) => `${(v / 1e8).toFixed(1)}억`} />
                  <Tooltip
                    formatter={(v, name) => {
                      const num = typeof v === "number" ? v : Number(v);
                      return String(name).includes("평균가") ? [won(num), name] : [`${num.toLocaleString()}건`, name];
                    }}
                    labelFormatter={(l) => `${l}월`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar yAxisId="n" dataKey="aN" name={`${data.a.name} 거래량`} fill="#a8c6ec" radius={[2, 2, 0, 0]} />
                  <Bar yAxisId="n" dataKey="bN" name={`${data.b.name} 거래량`} fill="#f2cd9e" radius={[2, 2, 0, 0]} />
                  <Line yAxisId="avg" dataKey="aAvg" name={`${data.a.name} 평균가`} stroke={A_COLOR} strokeWidth={2} dot={false} connectNulls />
                  <Line yAxisId="avg" dataKey="bAvg" name={`${data.b.name} 평균가`} stroke={B_COLOR} strokeWidth={2} dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </>
          )}
          <div className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>
            아파트 매매 기준. 거래량·거래가는 국토부 실거래 신고(해제 제외), 호가·매물은 현재 등록 매물의 콕집 집계.
            평균가는 거래 구성(단지·면적)에 따라 출렁일 수 있습니다.
          </div>
        </>
      )}
    </div>
  );
}
