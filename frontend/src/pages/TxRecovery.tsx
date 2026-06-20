import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { TrendingDown, TrendingUp } from "lucide-react";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";

const API_BASE = import.meta.env.VITE_API_BASE;

type Sido = { code: string; name: string };
type Row = {
  complex_no: string; complex_name: string; region_name: string | null;
  pyeong: string; peak_amt: number; cur_avg: number; n: number;
  last_ymd: string | null; recovery_rate: number; gap_from_peak: number;
};
type Resp = { days: number; order: string; count: number; items: Row[] };

function eok(v: number | null): string {
  if (v == null || v <= 0) return "—";
  return v >= 100_000_000 ? `${(v / 100_000_000).toFixed(1)}억`
    : `${Math.round(v / 10_000).toLocaleString()}만`;
}

export default function TxRecovery() {
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [sido, setSido] = useState<string>("");

  const sidoQ = useFetchJson<{ items: Sido[] }>(
    API_BASE ? `${API_BASE}/stats/changes/sido-list` : null
  );
  const sidos = sidoQ.data?.items ?? [];

  const url = useMemo(() => {
    if (!API_BASE) return null;
    const qs = new URLSearchParams({ order, limit: "200" });
    if (sido) qs.set("sido", sido);
    return `${API_BASE}/stats/tx-recovery?${qs.toString()}`;
  }, [order, sido]);
  const { data, loading, error } = useFetchJson<Resp>(url);

  if (!API_BASE) return <div style={{ color: "crimson" }}>로컬 API가 설정되지 않았습니다.</div>;

  const items = data?.items ?? [];
  const asc = order === "asc";

  return (
    <>
      <Link to="/overview" className="back">← 전국현황</Link>
      <h2 style={{ margin: "0 0 4px" }}>전고점 대비 {asc ? "저평가 단지" : "회복 단지"}</h2>
      <div className="muted" style={{ marginBottom: 14, fontSize: 13 }}>
        단지·평형별 <b>역대 최고 실거래가(전고점)</b> 대비 최근 90일 평균가의 비율입니다.
        회복률 100% = 전고점 회복, 낮을수록 전고점 대비 싸게 거래되는 중.
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div className="rc-toggle">
          <button className={asc ? "on" : ""} onClick={() => setOrder("asc")}>
            <TrendingDown size={13} strokeWidth={2.3} style={{ verticalAlign: "-2px" }} /> 저평가순
          </button>
          <button className={!asc ? "on" : ""} onClick={() => setOrder("desc")}>
            <TrendingUp size={13} strokeWidth={2.3} style={{ verticalAlign: "-2px" }} /> 회복순
          </button>
        </div>
        <select className="ai-input" style={{ padding: "6px 10px", maxWidth: 160 }}
          value={sido} onChange={(e) => setSido(e.target.value)}>
          <option value="">전국</option>
          {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </div>

      {loading ? <Loading />
        : error ? <div style={{ color: "crimson", fontSize: 13 }}>오류: {String(error)}</div>
        : items.length === 0 ? <div className="muted">데이터가 없습니다.</div>
        : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>단지 / 평형</th><th>지역</th>
                <th className="num">전고점</th><th className="num">최근평균</th>
                <th className="num">회복률</th><th className="num">거래</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => {
                const rate = r.recovery_rate;
                const color = rate < 80 ? "#c0392b" : rate < 95 ? "#a06000" : "#1a7f4b";
                return (
                  <tr key={r.complex_no + r.pyeong}>
                    <td>
                      <Link to={`/complex/${r.complex_no}`} style={{ fontSize: 13 }}>{r.complex_name}</Link>
                      <span className="muted" style={{ fontSize: 12 }}> {r.pyeong}㎡</span>
                    </td>
                    <td style={{ fontSize: 12, color: "#555", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {r.region_name ?? "—"}
                    </td>
                    <td className="num" style={{ fontSize: 13 }}>{eok(r.peak_amt)}</td>
                    <td className="num" style={{ fontSize: 13 }}>{eok(r.cur_avg)}</td>
                    <td className="num" style={{ fontWeight: 700, color }}>{rate}%</td>
                    <td className="num" style={{ fontSize: 12, color: "#888" }}>{r.n}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
        전고점은 해당 단지·평형의 역대 최고 실거래가(중개거래 기준). 거래 표본이 적은 단지는 변동이 클 수 있습니다.
      </p>
    </>
  );
}
