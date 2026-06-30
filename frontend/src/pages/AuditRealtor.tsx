import { useState } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck, ChevronLeft, Loader2, Search } from "lucide-react";
import { useAuth } from "../auth";
import ListingAudit from "../components/ListingAudit";

const API_BASE = import.meta.env.VITE_API_BASE;
const PRIMARY = "#1268d3";
const BORDER = "#e4e9f0";
const SPIN: React.CSSProperties = { animation: "hp-spin .8s linear infinite" };

type Realtor = { realtor_id: string; realtor_name: string; count: number; address: string | null };

export default function AuditRealtor() {
  const { token } = useAuth();
  const authH = { Authorization: `Bearer ${token}` };
  const [q, setQ] = useState("");
  const [realtors, setRealtors] = useState<Realtor[]>([]);
  const [searching, setSearching] = useState(false);
  const [realtor, setRealtor] = useState<Realtor | null>(null);

  async function searchRealtors() {
    if (!q.trim() || !API_BASE) return;
    setSearching(true);
    try {
      const r = await fetch(`${API_BASE}/stats/realtors/search?q=${encodeURIComponent(q.trim())}&limit=20`);
      const j = await r.json();
      setRealtors(j.items ?? []);
    } catch { setRealtors([]); }
    setSearching(false);
  }

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "22px 16px" }}>
      <Link to="/admin" style={{ display: "inline-flex", alignItems: "center", gap: 3, fontSize: 13, color: "#64748b", marginBottom: 12 }}>
        <ChevronLeft size={15} /> 관리자
      </Link>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <ShieldCheck size={21} style={{ color: PRIMARY }} />
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#13294b" }}>매물 표시·광고 점검</h2>
        <span style={{ fontSize: 11, fontWeight: 700, color: PRIMARY, background: "#eef4ff", border: "1px solid #cfe0ff", borderRadius: 999, padding: "2px 8px" }}>가오픈 · 관리자</span>
      </div>
      <p className="muted" style={{ fontSize: 13, margin: "0 0 16px" }}>중개사무소를 검색 → 매물 유형·거래별로 골라 점검합니다.</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <div style={{ position: "relative", flex: 1 }}>
          <Search size={15} style={{ position: "absolute", left: 11, top: 10, color: "#94a3b8" }} />
          <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && searchRealtors()}
            placeholder="중개사무소 이름 (예: 시티오씨엘, 고덕탑)"
            style={{ width: "100%", padding: "9px 12px 9px 34px", borderRadius: 10, border: `1px solid ${BORDER}`, fontSize: 13, outline: "none", boxSizing: "border-box" }} />
        </div>
        <button onClick={searchRealtors} disabled={searching || !q.trim()}
          style={{ padding: "9px 18px", borderRadius: 10, border: "none", background: PRIMARY, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", opacity: searching || !q.trim() ? 0.5 : 1, whiteSpace: "nowrap" }}>
          {searching ? <Loader2 size={16} style={SPIN} /> : "검색"}
        </button>
      </div>

      {realtors.length > 0 && !realtor && (
        <div style={{ border: `1px solid ${BORDER}`, borderRadius: 12, overflow: "hidden", marginBottom: 16, maxHeight: 280, overflowY: "auto" }}>
          {realtors.map((rt) => (
            <button key={rt.realtor_id} onClick={() => { setRealtor(rt); setRealtors([]); }}
              style={{ width: "100%", textAlign: "left", padding: "10px 12px", background: "#fff", border: "none", borderTop: `1px solid #f1f5f9`, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "#334155", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{rt.realtor_name}
                {rt.address && <span className="muted" style={{ fontWeight: 400, fontSize: 12, marginLeft: 8 }}>{rt.address}</span>}</span>
              <span className="muted" style={{ fontSize: 12, flexShrink: 0 }}>매물 {rt.count.toLocaleString()}</span>
            </button>
          ))}
        </div>
      )}

      {realtor && (
        <div style={{ marginBottom: 14, padding: "11px 13px", borderRadius: 12, background: "#f8fafc", border: `1px solid ${BORDER}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: 13.5, fontWeight: 700, color: "#334155" }}>{realtor.realtor_name}</span>
          <button onClick={() => setRealtor(null)} className="muted" style={{ fontSize: 12, background: "none", border: "none", cursor: "pointer" }}>다른 사무소</button>
        </div>
      )}

      {realtor && (
        <ListingAudit
          authH={authH}
          breakdownUrl={`/admin/audit/breakdown?realtor_id=${encodeURIComponent(realtor.realtor_id)}`}
          buildAuditUrl={(kind, trade, offset, limit) =>
            `/admin/audit/realtor?realtor_id=${encodeURIComponent(realtor.realtor_id)}&kind=${kind}&trade=${trade}&offset=${offset}&limit=${limit}`}
        />
      )}
    </div>
  );
}
