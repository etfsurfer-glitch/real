import { useEffect, useState } from "react";
import { Link2, CheckCircle2 } from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

// 실거래 추가 매칭 — 단지에 못 붙은 거래(국토부 단지 번호별 묶음)를 관리자가 단지에 잇는다.
// 고르면 그 번호의 지난 거래가 바로 붙고, 새 거래도 매일 재매칭에서 같은 단지로 간다.
type Cand = { complex_no: string; complex_name: string; dong: string; jibun: string; score?: number; reasons?: string[] };
type Grp = {
  apt_seq: string; sgg_cd: string; sido: string | null; umd_nm: string;
  names: [string, number][]; jibuns: [string, number][]; areas: number[];
  n_sale: number; n_rent: number; first_ymd: string | null; last_ymd: string | null; build_year: number | null;
  cands: Cand[]; status: string | null; r_cno: string | null; n_applied: number | null;
};
const SIDO: [string, string][] = [["", "전국"], ["11", "서울"], ["26", "부산"], ["27", "대구"], ["28", "인천"], ["29", "광주"], ["30", "대전"],
  ["31", "울산"], ["36", "세종"], ["41", "경기"], ["51", "강원"], ["43", "충북"], ["44", "충남"], ["52", "전북"], ["46", "전남"],
  ["47", "경북"], ["48", "경남"], ["50", "제주"]];

export default function AdminTxMatch() {
  const { token } = useAuth();
  const auth = { Authorization: `Bearer ${token}` };
  const [sido, setSido] = useState("");
  const [status, setStatus] = useState("open");
  const [hasCand, setHasCand] = useState(false);
  const [q, setQ] = useState("");
  const [data, setData] = useState<{ total: number; n_sale: number; n_rent: number; built_at: string | null; items: Grp[] } | null>(null);
  const [sel, setSel] = useState<Grp | null>(null);
  const [sq, setSq] = useState("");
  const [found, setFound] = useState<Cand[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const load = () => {
    if (!API_BASE || !token) return;
    const u = new URLSearchParams({ sido, status, q, has_cand: hasCand ? "1" : "0", limit: "200" });
    fetch(`${API_BASE}/admin/tx-unmatched?${u}`, { headers: auth }).then((r) => r.json()).then(setData).catch(() => setData(null));
  };
  useEffect(load, [token, sido, status, hasCand]);   // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (g: Grp) => { setSel(g); setFound(null); setSq(g.names[0]?.[0] ?? ""); setMsg(""); };

  const search = () => {
    if (!sel) return;
    fetch(`${API_BASE}/admin/tx-unmatched/search?sgg=${sel.sgg_cd}&q=${encodeURIComponent(sq)}`, { headers: auth })
      .then((r) => r.json()).then((d) => setFound(d.items ?? [])).catch(() => setFound([]));
  };

  const post = async (path: string, complex_no: string | null) => {
    if (!sel || busy) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/admin/tx-unmatched/${path}`, {
        method: "POST", headers: { "Content-Type": "application/json", ...auth },
        body: JSON.stringify({ apt_seq: sel.apt_seq, complex_no }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setMsg(path === "undo" ? `되돌림 — 거래 ${d.reverted}건 미매칭으로` : complex_no ? `연결함 — 거래 ${d.applied}건이 붙었어요` : "단지 목록에 없음으로 처리");
      setData((D) => D && { ...D, items: D.items.filter((x) => x.apt_seq !== sel.apt_seq) });
      setSel(null); setFound(null);
    } catch (e) {
      setMsg("실패: " + String(e).slice(0, 140));
    } finally { setBusy(false); }
  };

  const card = (c: Cand) => (
    <div key={c.complex_no} className="vw-card">
      <div>
        <b>{c.complex_name}</b> <span className="muted" style={{ fontSize: 12 }}>#{c.complex_no}</span>{" "}
        {(c.reasons ?? []).map((x) => (
          <span key={x} className="ctx-badge" style={{ marginLeft: 4, background: x === "번호 다름" ? "#fde8e8" : "#eef5ff", color: x === "번호 다름" ? "#c0392b" : "#1268d3" }}>{x}</span>
        ))}
      </div>
      <div className="muted" style={{ fontSize: 12 }}>{c.dong} {c.jibun}</div>
      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
        <button className="nv-btn" disabled={busy} onClick={() => post("apply", c.complex_no)}>이 단지로 연결</button>
        <a className="nv-btn" href={`/complex/${c.complex_no}`} target="_blank" rel="noreferrer">단지 보기</a>
      </div>
    </div>
  );

  if (!API_BASE) return <div className="muted">로컬 API 미설정 — 이 기능은 로컬에서만 동작합니다.</div>;
  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        <Link2 size={15} strokeWidth={2.2} aria-hidden /> 실거래 추가 매칭{" "}
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
          {data ? `단지 번호 ${data.total.toLocaleString()}개 · 매매 ${data.n_sale.toLocaleString()} · 전월세 ${data.n_rent.toLocaleString()}건` : ""}
          {data?.built_at ? ` · 목록 ${data.built_at.slice(5, 16).replace("T", " ")} 기준` : ""}
        </span>
      </div>
      <p className="muted" style={{ fontSize: 13, margin: "0 0 8px" }}>
        단지에 못 붙은 거래를 국토부 단지 번호로 묶었어요. 단지를 고르면 지난 거래가 바로 붙고, 앞으로 들어오는 같은 번호 거래도 그 단지로 가요.
        공공임대·나홀로처럼 우리 단지 목록에 없는 곳은 '단지 목록에 없음'으로 넘기세요.
      </p>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8, alignItems: "center" }}>
        <select value={sido} onChange={(e) => setSido(e.target.value)}>{SIDO.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="open">미처리</option><option value="matched">연결함</option><option value="none">단지 없음</option><option value="all">전체</option>
        </select>
        <label className="muted" style={{ fontSize: 13 }}><input type="checkbox" checked={hasCand} onChange={(e) => setHasCand(e.target.checked)} /> 후보 있는 것만</label>
        <input className="ai-input" style={{ padding: "6px 10px", maxWidth: 220 }} value={q} placeholder="이름·동·단지 번호"
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") load(); }} />
        <button className="nv-btn" onClick={load}>찾기</button>
      </div>
      {msg && <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>{msg}</div>}

      <div className="rm-grid">
        <div className="rm-queue">
          {data && data.items.length === 0 && (
            <div className="muted" style={{ padding: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <CheckCircle2 size={14} style={{ color: "#1a7f4b" }} aria-hidden /> 해당 없음
            </div>
          )}
          {data?.items.map((g) => (
            <button key={g.apt_seq} className={`rm-item${sel?.apt_seq === g.apt_seq ? " on" : ""}`} onClick={() => pick(g)}>
              <b>{g.names[0]?.[0] || "(이름 없음)"}</b>
              <span className="muted" style={{ fontSize: 11 }}>
                {g.sido} {g.umd_nm} · 매매 {g.n_sale} · 전월세 {g.n_rent}{g.cands.length ? ` · 후보 ${g.cands.length}` : ""}
              </span>
            </button>
          ))}
        </div>

        <div className="rm-detail">
          {!sel ? <div className="muted" style={{ padding: 16 }}>왼쪽에서 거래 묶음을 고르세요.</div> : (
            <>
              <div className="rm-naver">
                <div><b>{sel.names.map(([n, c]) => `${n}(${c})`).join(" · ")}</b></div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {sel.sido} {sel.umd_nm} · 지번 {sel.jibuns.map(([j]) => j).join(", ") || "-"} · 건축 {sel.build_year ?? "-"}년
                </div>
                <div className="muted" style={{ fontSize: 13 }}>
                  매매 {sel.n_sale} · 전월세 {sel.n_rent}건 · {sel.first_ymd ?? ""} ~ {sel.last_ymd ?? ""} · 전용 {sel.areas.slice(0, 6).join(", ")}㎡ · 단지 번호 {sel.apt_seq}
                </div>
              </div>

              {sel.status ? (
                <div style={{ marginTop: 10 }}>
                  <div className="muted" style={{ fontSize: 13 }}>
                    {sel.status === "matched" ? `연결함 → #${sel.r_cno} (거래 ${sel.n_applied ?? 0}건)` : "단지 목록에 없음으로 처리함"}
                  </div>
                  <button className="auth-btn ghost" style={{ marginTop: 8 }} disabled={busy} onClick={() => post("undo", null)}>되돌리기</button>
                </div>
              ) : (
                <>
                  <div className="rm-section-t">자동 후보</div>
                  {sel.cands.length === 0 ? <div className="muted" style={{ fontSize: 13 }}>자동 후보 없음 — 아래에서 직접 찾으세요.</div> : sel.cands.map(card)}

                  <div className="rm-section-t" style={{ marginTop: 14 }}>같은 시군구에서 직접 찾기</div>
                  <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                    <input className="ai-input" style={{ padding: "8px 12px" }} value={sq} placeholder="단지 이름 또는 동"
                      onChange={(e) => setSq(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") search(); }} />
                    <button className="ai-send" style={{ padding: "0 16px" }} onClick={search}>검색</button>
                  </div>
                  {found && (found.length === 0 ? <div className="muted" style={{ fontSize: 13 }}>검색 결과 없음</div> : found.map(card))}

                  <div style={{ marginTop: 16, borderTop: "1px solid var(--c-border)", paddingTop: 12 }}>
                    <button className="auth-btn ghost" disabled={busy} onClick={() => post("apply", null)}>단지 목록에 없음 — 넘기기</button>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
