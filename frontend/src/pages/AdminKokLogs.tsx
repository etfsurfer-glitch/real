import { useCallback, useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { useAuth } from "../auth";
import { Loading } from "../components/Loading";

const API = import.meta.env.VITE_API_BASE;

type Log = {
  id: number; office: string | null; realtor_id: string | null;
  query: string; answer: string | null; ok: number;
  duration_ms: number | null; ctx_len: number | null; created_at: string;
};
type Resp = { items: Log[]; total: number; today: number; offices: number; avg_ms: number | null };

export default function AdminKokLogs() {
  const { token } = useAuth();
  const [data, setData] = useState<Resp | null>(null);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback((kw = "") => {
    if (!API || !token) return;
    setErr("");
    fetch(`${API}/admin/kok-logs?limit=300${kw ? `&q=${encodeURIComponent(kw)}` : ""}`,
      { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setData).catch((e) => setErr(String(e)));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  if (err) return <div style={{ color: "crimson", padding: 20 }}>오류: {err}</div>;
  if (!data) return <Loading />;

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "18px 16px 60px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, margin: "4px 0 4px", display: "flex", alignItems: "center", gap: 7 }}>
        <Sparkles size={20} /> 콕비서 로그
      </h1>
      <p style={{ color: "var(--c-muted)", fontSize: 13.5, margin: "0 0 16px" }}>
        중개사 AI 비서(콕비서)의 질문·답변 기록 — 향후 개선·품질 점검용.
      </p>

      <div className="cards" style={{ marginBottom: 16 }}>
        <div className="card"><div className="label">누적 질문</div><div className="num">{data.total.toLocaleString()}</div></div>
        <div className="card"><div className="label">오늘</div><div className="num">{data.today.toLocaleString()}</div></div>
        <div className="card"><div className="label">사용 사무소</div><div className="num">{data.offices.toLocaleString()}</div></div>
        <div className="card"><div className="label">평균 응답</div><div className="num">{data.avg_ms ? `${(data.avg_ms / 1000).toFixed(1)}s` : "—"}</div></div>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); load(q); }} style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="질문·답변·사무소 검색"
          style={{ flex: 1, padding: "9px 12px", border: "1px solid var(--c-border)", borderRadius: 9, fontSize: 14, fontFamily: "inherit" }} />
        <button type="submit" className="ai-send" style={{ padding: "9px 16px" }}>검색</button>
      </form>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {data.items.map((l) => (
          <div key={l.id} className="card" style={{ padding: "12px 14px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--c-muted)", marginBottom: 6 }}>
              <span>{l.office || l.realtor_id || "-"}{!l.ok && <span style={{ color: "#c0392b", fontWeight: 700 }}> · 오류</span>}</span>
              <span>{(l.created_at || "").slice(0, 16)}{l.duration_ms != null ? ` · ${l.duration_ms}ms` : ""}</span>
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Q. {l.query}</div>
            <div style={{ fontSize: 13.5, color: "var(--c-text)", whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{l.answer}</div>
          </div>
        ))}
        {data.items.length === 0 && <div className="cled-empty">로그가 없습니다.</div>}
      </div>
    </div>
  );
}
