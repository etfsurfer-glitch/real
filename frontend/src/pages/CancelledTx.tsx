import { useEffect, useState, CSSProperties } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/Loading";
import { ApplyButton } from "../hooks/useDeferredUrl";

const API_BASE = import.meta.env.VITE_API_BASE;

type CancelType = "double" | "correction" | "plain";
type Row = {
  asset: "apt" | "offi";
  name: string;
  region: string;
  umd_nm: string | null;
  excl_use_ar: number | null;
  pyeong: number | null;
  floor: number | null;
  deal_amount: number;
  deal_ymd: string;
  cdeal_date: string | null;
  dealing_gbn: string | null;   // 직거래 | 중개거래
  build_year: number | null;
  complex_no: string | null;
  cancel_type: CancelType;
  dong: string | null;          // 동 (아파트 매매만)
  registered: boolean;          // 등기완료 여부
};

function dongLabel(dong: string | null): string {
  if (!dong) return "";
  const d = dong.trim();
  return d.endsWith("동") ? d : `${d}동`;
}
type Resp = { total: number; offset: number; limit: number; count: number; items: Row[] };
type Summary = {
  total: number; n_junggae: number; n_jikgeo: number;
  n_double: number; n_correction: number; n_plain: number;
};

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
  { m: 1, label: "1달" }, { m: 3, label: "3달" }, { m: 6, label: "6달" }, { m: 0, label: "최대" },
];

const CANCEL_BADGE: Record<CancelType, { label: string; style: CSSProperties }> = {
  double: { label: "이중신고 취소", style: { background: "#f3e8ff", color: "#7e22ce" } },
  correction: { label: "금액정정 신고", style: { background: "#fff4e6", color: "#d9480f" } },
  plain: { label: "취소", style: { background: "#fde8e8", color: "#c0392b" } },
};

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

export default function CancelledTx() {
  const [asset, setAsset] = useState<"apt" | "offi" | "all">("apt");
  const [dealing, setDealing] = useState<"" | "중개거래" | "직거래">("");
  const [sido, setSido] = useState<string>("");
  const [months, setMonths] = useState<number>(3);
  const [offset, setOffset] = useState(0);
  // 필터 즉시 호출 방지 — '적용' 눌러야 fetch (applied 스냅샷 기준으로만 조회).
  const [applied, setApplied] = useState({ asset, dealing, sido, months });
  const dirty = applied.asset !== asset || applied.dealing !== dealing
    || applied.sido !== sido || applied.months !== months;
  const apply = () => setApplied({ asset, dealing, sido, months });
  const [data, setData] = useState<Resp | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 적용된 필터가 바뀌면 첫 페이지로
  useEffect(() => { setOffset(0); }, [applied]);

  // 통계표 (적용된 asset/지역/기간 기준)
  useEffect(() => {
    if (!API_BASE) return;
    let cancelled = false;
    setSummary(null);
    const q = `asset=${applied.asset}&months=${applied.months}`
      + (applied.sido ? `&sido=${applied.sido}` : "");
    fetch(`${API_BASE}/stats/cancelled-summary?${q}`)
      .then((r) => r.json())
      .then((j: Summary) => { if (!cancelled) setSummary(j); })
      .catch(() => { /* ignore */ });
    return () => { cancelled = true; };
  }, [applied]);

  // 목록
  useEffect(() => {
    if (!API_BASE) { setError("로컬 API(VITE_API_BASE) 미설정 — 이 기능은 로컬에서만 제공됩니다."); setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    const q = `asset=${applied.asset}&months=${applied.months}&limit=${LIMIT}&offset=${offset}`
      + (applied.dealing ? `&dealing=${encodeURIComponent(applied.dealing)}` : "")
      + (applied.sido ? `&sido=${applied.sido}` : "");
    fetch(`${API_BASE}/stats/cancelled-transactions?${q}`)
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
        실거래 취소조회{" "}
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
          국토부 신고 후 해제(취소)된 거래 · 해제일 기준
        </span>
      </div>
      <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
        같은 호실·계약일에 살아있는 신고가 또 있으면 <b>이중신고 취소</b>(금액 동일, 양쪽 동시신고)
        또는 <b>금액정정 신고</b>(금액 정정 후 옛 신고 해제)로 구분합니다. 그 외는 단순 취소입니다.
      </p>

      {/* 통계표 */}
      <div className="ctx-stats">
        <div><span>전체</span><b>{summary ? summary.total.toLocaleString() : "…"}</b></div>
        <div><span>중개거래</span><b>{summary ? summary.n_junggae.toLocaleString() : "…"}</b></div>
        <div><span>직거래</span><b>{summary ? summary.n_jikgeo.toLocaleString() : "…"}</b></div>
        <div className="dbl"><span>이중신고 취소</span><b>{summary ? summary.n_double.toLocaleString() : "…"}</b></div>
        <div className="corr"><span>금액정정 신고</span><b>{summary ? summary.n_correction.toLocaleString() : "…"}</b></div>
        <div><span>단순 취소</span><b>{summary ? summary.n_plain.toLocaleString() : "…"}</b></div>
      </div>

      <div className="dm-filters">
        <div className="map-metric">
          {([["apt", "아파트"], ["offi", "오피스텔"], ["all", "전체"]] as const).map(([k, label]) => (
            <button key={k} className={asset === k ? "on" : ""} onClick={() => setAsset(k)}>{label}</button>
          ))}
        </div>
        <span className="dm-sep" />
        <div className="map-metric">
          {PERIODS.map((p) => (
            <button key={p.m} className={months === p.m ? "on" : ""} onClick={() => setMonths(p.m)}>{p.label}</button>
          ))}
        </div>
        <span className="dm-sep" />
        <div className="map-metric">
          {([["", "거래 전체"], ["중개거래", "중개거래"], ["직거래", "직거래"]] as const).map(([k, label]) => (
            <button key={k || "all"} className={dealing === k ? "on" : ""} onClick={() => setDealing(k)}>{label}</button>
          ))}
        </div>
        <span className="dm-sep" />
        <select value={sido} onChange={(e) => setSido(e.target.value)}
                style={{ fontSize: 13, padding: "4px 8px", borderRadius: 8, border: "1px solid var(--c-border)" }}>
          {SIDO.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>

      {error ? <div style={{ color: "crimson" }}>{error}</div>
        : loading ? <Loading />
        : !data || data.items.length === 0 ? <div className="muted">해당 조건의 취소 거래가 없습니다.</div>
        : (
        <>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>구분</th>
                  <th>거래</th>
                  <th>단지/건물</th>
                  <th>지역</th>
                  <th className="num">전용</th>
                  <th className="num">층</th>
                  <th>등기</th>
                  <th className="num">거래금액</th>
                  <th>계약일</th>
                  <th>해제일</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((r, i) => {
                  const badge = CANCEL_BADGE[r.cancel_type];
                  return (
                  <tr key={`${r.name}-${r.deal_ymd}-${r.floor}-${r.deal_amount}-${i}`}>
                    <td><span className="ctx-badge" style={badge.style}>{badge.label}</span></td>
                    <td>
                      <span className="ctx-badge" style={r.dealing_gbn === "직거래"
                        ? { background: "#e7f5ff", color: "#1268d3" }
                        : { background: "#eef2f5", color: "#555" }}>
                        {r.dealing_gbn ?? "-"}
                      </span>
                    </td>
                    <td>
                      {r.complex_no
                        ? <Link to={`/complex/${r.complex_no}`}>{r.name}</Link>
                        : r.name}
                      {r.asset === "offi" && <span className="muted" style={{ fontSize: 11 }}> (오피)</span>}
                    </td>
                    <td className="muted" style={{ fontSize: 12 }}>{r.region}</td>
                    <td className="num">{r.excl_use_ar != null ? `${r.excl_use_ar}㎡` : "-"}<br />
                      <span className="muted" style={{ fontSize: 11 }}>{r.pyeong != null ? `${r.pyeong}평` : ""}</span></td>
                    <td className="num">{r.floor ?? "-"}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {r.asset === "offi" ? <span className="muted">-</span>
                        : r.registered ? (
                          <>
                            <span className="ctx-badge" style={{ background: "#e6f7ed", color: "#1a7f4b" }}>등기완료</span>
                            {r.dong && <span style={{ marginLeft: 5, fontWeight: 600, fontSize: 12 }}>{dongLabel(r.dong)}</span>}
                          </>
                        ) : <span className="ctx-badge" style={{ background: "#eef2f5", color: "#888" }}>미등기</span>}
                    </td>
                    <td className="num" style={{ fontWeight: 600 }}>{formatWon(r.deal_amount)}</td>
                    <td className="num" style={{ fontSize: 12 }}>{r.deal_ymd}</td>
                    <td className="num" style={{ fontSize: 12 }}>{r.cdeal_date ?? "-"}</td>
                  </tr>
                  );
                })}
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
