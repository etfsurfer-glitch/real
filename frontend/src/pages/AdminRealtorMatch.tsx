import { useEffect, useState } from "react";
import { Wrench, CheckCircle2 } from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type Row = {
  realtor_id: string; naver_name: string; sgg_cd: string | null; sido: string | null;
  total_listings: number; address: string | null; rep: string | null;
  regno: string | null; tel: string | null;
};
type Vw = {
  sys_regno: string; business_name: string; representative: string | null;
  address: string | null; status: string | null; registered_ymd: string | null;
  phone: string | null; sgg_cd: string | null; reasons?: string[];
};

export default function AdminRealtorMatch() {
  const { token } = useAuth();
  const auth = { Authorization: `Bearer ${token}` };
  const [queue, setQueue] = useState<Row[]>([]);
  const [sel, setSel] = useState<Row | null>(null);
  const [cands, setCands] = useState<Vw[] | null>(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Vw[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!API_BASE || !token) return;
    fetch(`${API_BASE}/admin/realtor-match/unmatched?limit=500`, { headers: auth })
      .then((r) => r.json()).then((d) => setQueue(d.items ?? [])).catch(() => {});
  }, [token]);

  const pick = (row: Row) => {
    setSel(row); setCands(null); setResults(null); setQ(""); setMsg("");
    fetch(`${API_BASE}/admin/realtor-match/candidates?realtor_id=${encodeURIComponent(row.realtor_id)}`, { headers: auth })
      .then((r) => r.json()).then((d) => setCands(d.candidates ?? [])).catch(() => setCands([]));
  };

  const search = () => {
    if (!sel) return;
    const url = `${API_BASE}/admin/vworld/search?q=${encodeURIComponent(q)}`
      + (sel.sgg_cd ? `&sgg=${sel.sgg_cd}` : "");
    fetch(url, { headers: auth }).then((r) => r.json()).then((d) => setResults(d.items ?? [])).catch(() => setResults([]));
  };

  const apply = async (sys_regno: string | null) => {
    if (!sel || busy) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/admin/realtor-match/${encodeURIComponent(sel.realtor_id)}`, {
        method: "POST", headers: { "Content-Type": "application/json", ...auth },
        body: JSON.stringify({ sys_regno }),
      });
      if (!r.ok) throw new Error(await r.text());
      setQueue((Q) => Q.filter((x) => x.realtor_id !== sel.realtor_id));
      setMsg(sys_regno ? `매칭 완료 → ${sys_regno}` : "매칭 없음으로 처리됨");
      setSel(null); setCands(null); setResults(null);
    } catch (e) {
      setMsg("실패: " + String(e).slice(0, 120));
    } finally { setBusy(false); }
  };

  const vwCard = (v: Vw) => (
    <div key={v.sys_regno} className="vw-card">
      <div>
        <b>{v.business_name}</b>{" "}
        {v.status && <span className="ctx-badge" style={{ background: v.status === "영업" ? "#e6f7ed" : "#fde8e8", color: v.status === "영업" ? "#1a7f4b" : "#c0392b" }}>{v.status}</span>}
        {v.reasons && v.reasons.map((rs) => <span key={rs} className="ctx-badge" style={{ background: "#eef5ff", color: "#1268d3", marginLeft: 4 }}>{rs}</span>)}
      </div>
      <div className="muted" style={{ fontSize: 12 }}>
        대표 {v.representative ?? "-"} · {v.registered_ymd ?? "-"} 개설 · {v.phone ?? "-"}
      </div>
      <div className="muted" style={{ fontSize: 12 }}>{v.address ?? "-"}</div>
      <button className="nv-btn" style={{ marginTop: 6 }} disabled={busy} onClick={() => apply(v.sys_regno)}>이 사무소로 매칭</button>
    </div>
  );

  if (!API_BASE) return <div className="muted">로컬 API 미설정 — 이 기능은 로컬에서만 동작합니다.</div>;

  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        <Wrench size={15} strokeWidth={2.2} aria-hidden /> 중개사 vworld 매칭 (관리자){" "}
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>미매칭 {queue.length}건</span>
      </div>
      {msg && <div className="muted" style={{ fontSize: 13, marginBottom: 8 }}>{msg}</div>}

      <div className="rm-grid">
        {/* 큐 */}
        <div className="rm-queue">
          {queue.length === 0 && (
            <div className="muted" style={{ padding: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <CheckCircle2 size={14} style={{ color: "#1a7f4b" }} aria-hidden /> 미매칭 없음
            </div>
          )}
          {queue.map((r) => (
            <button key={r.realtor_id} className={`rm-item${sel?.realtor_id === r.realtor_id ? " on" : ""}`} onClick={() => pick(r)}>
              <b>{r.naver_name}</b>
              <span className="muted" style={{ fontSize: 11 }}>{r.sido} · 매물 {r.total_listings}{r.regno ? ` · ${r.regno}` : ""}</span>
            </button>
          ))}
        </div>

        {/* 상세 + 후보 */}
        <div className="rm-detail">
          {!sel ? <div className="muted" style={{ padding: 16 }}>왼쪽에서 중개사를 선택하세요.</div> : (
            <>
              <div className="rm-naver">
                <div><b>{sel.naver_name}</b></div>
                <div className="muted" style={{ fontSize: 13 }}>대표 {sel.rep ?? "-"} · 등록 {sel.regno ?? "-"} · {sel.tel ?? "-"}</div>
                <div className="muted" style={{ fontSize: 13 }}>{sel.address ?? "-"}</div>
              </div>

              <div className="rm-section-t">자동 추천 후보</div>
              {cands === null ? <div className="muted">불러오는 중…</div>
                : cands.length === 0 ? <div className="muted" style={{ fontSize: 13 }}>자동 후보 없음 — 아래에서 직접 검색하세요.</div>
                : cands.map(vwCard)}

              <div className="rm-section-t" style={{ marginTop: 14 }}>직접 검색 (이름·대표·주소)</div>
              <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                <input className="ai-input" style={{ padding: "8px 12px" }} value={q} placeholder="예: 트리우스 / 대표명 / 주소"
                  onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") search(); }} />
                <button className="ai-send" style={{ padding: "0 16px" }} onClick={search}>검색</button>
              </div>
              <label className="muted" style={{ fontSize: 12, display: "block", marginBottom: 8 }}>
                <input type="checkbox" defaultChecked disabled /> 같은 시군구({sel.sgg_cd})로 한정
              </label>
              {results && (results.length === 0 ? <div className="muted" style={{ fontSize: 13 }}>검색 결과 없음</div> : results.map(vwCard))}

              <div style={{ marginTop: 16, borderTop: "1px solid var(--c-border)", paddingTop: 12 }}>
                <button className="auth-btn ghost" disabled={busy} onClick={() => apply(null)}>
                  vworld에 없음 — 매칭 없음으로 처리
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
