import { useEffect, useState } from "react";
import FetchError from "../components/FetchError";
import { useStickyState } from "../hooks/useStickyState";
import { Link } from "react-router-dom";
import { Loading } from "../components/Loading";
import { ApplyButton } from "../hooks/useDeferredUrl";

const API_BASE = import.meta.env.VITE_API_BASE;

type Row = {
  name: string;
  region: string;
  umd_nm: string | null;
  excl_use_ar: number | null;
  pyeong: number | null;
  floor: number | null;
  deal_amount: number;
  deal_ymd: string;
  kind: string;            // 분양권 | 입주권
  dealing_gbn: string | null;
  complex_no: string | null;
};
type Resp = { total: number; offset: number; limit: number; count: number; items: Row[] };
type Summary = { total: number; n_bunyang: number; n_ipju: number; avg_amount: number | null };

const SIDO: { code: string; name: string }[] = [
  { code: "", name: "전국" },
  { code: "11", name: "서울" }, { code: "41", name: "경기" }, { code: "28", name: "인천" },
  { code: "26", name: "부산" }, { code: "27", name: "대구" }, { code: "29", name: "광주" },
  { code: "30", name: "대전" }, { code: "31", name: "울산" }, { code: "36", name: "세종" },
  { code: "43", name: "충북" }, { code: "44", name: "충남" }, { code: "52", name: "전북" },
  { code: "46", name: "전남" }, { code: "47", name: "경북" }, { code: "48", name: "경남" },
  { code: "51", name: "강원" }, { code: "50", name: "제주" },
];

const PERIODS: { m: number; label: string }[] = [
  { m: 3, label: "3달" }, { m: 6, label: "6달" }, { m: 12, label: "1년" }, { m: 0, label: "최대" },
];

const LIMIT = 50;

function formatWon(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 100_000_000) {
    const eok = Math.floor(v / 100_000_000);
    const man = Math.floor((v % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(v / 10_000).toLocaleString()}만`;
}

export default function PresaleTx() {
  const [kind, setKind] = useState<"" | "분양권" | "입주권">("");
  const [sido, setSido] = useState<string>("");
  const [months, setMonths] = useStickyState<number>("presale:months", 6);
  const [offset, setOffset] = useState(0);
  const [applied, setApplied] = useState({ kind, sido, months });
  const dirty = applied.kind !== kind || applied.sido !== sido || applied.months !== months;
  const apply = () => setApplied({ kind, sido, months });
  const [data, setData] = useState<Resp | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setOffset(0); }, [applied]);

  useEffect(() => {
    if (!API_BASE) return;
    let cancelled = false;
    setSummary(null);
    const q = `months=${applied.months}` + (applied.sido ? `&sido=${applied.sido}` : "");
    fetch(`${API_BASE}/stats/presale-summary?${q}`)
      .then((r) => r.json())
      .then((j: Summary) => { if (!cancelled) setSummary(j); })
      .catch(() => { /* ignore */ });
    return () => { cancelled = true; };
  }, [applied]);

  useEffect(() => {
    if (!API_BASE) { setError("로컬 API(VITE_API_BASE) 미설정 — 이 기능은 로컬에서만 제공됩니다."); setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    const q = `months=${applied.months}&limit=${LIMIT}&offset=${offset}`
      + (applied.kind ? `&kind=${encodeURIComponent(applied.kind)}` : "")
      + (applied.sido ? `&sido=${applied.sido}` : "");
    fetch(`${API_BASE}/stats/presale-transactions?${q}`)
      .then((r) => r.json())
      .then((j: Resp) => { if (!cancelled) { setData(j); setLoading(false); } })
      .catch((e) => { if (!cancelled) { setError(String(e)); setLoading(false); } });
    return () => { cancelled = true; };
  }, [applied, offset]);

  const total = data?.total ?? 0;
  const page = Math.floor(offset / LIMIT) + 1;
  const pages = Math.max(1, Math.ceil(total / LIMIT));

  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        분양권·입주권 전매{" "}
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
          국토부 신고 기준 · 해제건 제외
        </span>
      </div>
      <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
        신축·재건축 단지의 <b>입주 전 권리 거래</b>입니다. 청약 당첨 분양권과 재건축·재개발 입주권을 함께
        보여줍니다. (분양가 기준 프리미엄은 추후 제공 예정)
      </p>

      <div className="ctx-stats">
        <div><span>전체</span><b>{summary ? summary.total.toLocaleString() : "…"}</b></div>
        <div><span>분양권</span><b>{summary ? summary.n_bunyang.toLocaleString() : "…"}</b></div>
        <div><span>입주권</span><b>{summary ? summary.n_ipju.toLocaleString() : "…"}</b></div>
        <div><span>평균 거래가</span><b>{summary ? formatWon(summary.avg_amount) : "…"}</b></div>
      </div>

      <div className="dm-filters">
        <div className="map-metric">
          {([["", "전체"], ["분양권", "분양권"], ["입주권", "입주권"]] as const).map(([k, label]) => (
            <button key={k || "all"} className={kind === k ? "on" : ""} onClick={() => setKind(k)}>{label}</button>
          ))}
        </div>
        <span className="dm-sep" />
        <div className="map-metric">
          {PERIODS.map((p) => (
            <button key={p.m} className={months === p.m ? "on" : ""} onClick={() => setMonths(p.m)}>{p.label}</button>
          ))}
        </div>
        <span className="dm-sep" />
        <select value={sido} onChange={(e) => setSido(e.target.value)}
                style={{ fontSize: 13, padding: "4px 8px", borderRadius: 8, border: "1px solid var(--c-border)" }}>
          {SIDO.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>

      {error ? <FetchError message={error} inline />
        : loading ? <Loading />
        : !data || data.items.length === 0 ? <div className="muted">해당 조건의 분양권 전매 거래가 없습니다.</div>
        : (
        <>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>종류</th>
                  <th>단지</th>
                  <th>지역</th>
                  <th className="num">전용</th>
                  <th className="num">층</th>
                  <th className="num">거래금액</th>
                  <th>거래</th>
                  <th>계약일</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r, i) => (
                  <tr key={`${r.name}-${r.deal_ymd}-${r.floor}-${r.deal_amount}-${i}`}>
                    <td>
                      <span className="ctx-badge" style={r.kind === "입주권"
                        ? { background: "#fff3e0", color: "#b25d00" }
                        : { background: "#e8f0fe", color: "#1268d3" }}>{r.kind}</span>
                    </td>
                    <td>{r.complex_no ? <Link to={`/complex/${r.complex_no}`}>{r.name}</Link> : r.name}</td>
                    <td className="muted" style={{ fontSize: 12 }}>{r.region}</td>
                    <td className="num">{r.excl_use_ar != null ? `${r.excl_use_ar}㎡` : "-"}<br />
                      <span className="muted" style={{ fontSize: 11 }}>{r.pyeong != null ? `${r.pyeong}평` : ""}</span></td>
                    <td className="num">{r.floor ?? "-"}</td>
                    <td className="num" style={{ fontWeight: 600 }}>{formatWon(r.deal_amount)}</td>
                    <td>
                      <span className="ctx-badge" style={r.dealing_gbn === "직거래"
                        ? { background: "#e7f5ff", color: "#1268d3" }
                        : { background: "#eef2f5", color: "#555" }}>{r.dealing_gbn ?? "-"}</span>
                    </td>
                    <td className="num" style={{ fontSize: 12 }}>{r.deal_ymd}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
            <button className="auth-btn ghost" disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - LIMIT))}>← 이전</button>
            <span className="muted" style={{ fontSize: 13 }}>{page} / {pages} 페이지 · 총 {total.toLocaleString()}건</span>
            <button className="auth-btn ghost" disabled={page >= pages}
                    onClick={() => setOffset(offset + LIMIT)}>다음 →</button>
          </div>
        </>
      )}
    </>
  );
}
