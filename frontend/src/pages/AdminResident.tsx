import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Home, CheckCircle2, XCircle, FileText } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

type Item = {
  id: number; user_id: string; complex_no: string; complex_name: string | null;
  doc_name: string | null; created_at: string; member_no: number | null;
};

export default function AdminResident() {
  const { token } = useAuth();
  const [items, setItems] = useState<Item[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    if (!token || !API) return;
    fetch(`${API}/admin/resident-verifications`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then((d) => setItems(d.items ?? []))
      .catch((e) => setErr(String(e)));
  }, [token]);
  useEffect(() => { load(); }, [load]);

  const decide = async (id: number, action: "approve" | "reject") => {
    if (!token || busy) return;
    setBusy(id);
    try {
      await fetch(`${API}/admin/resident-verifications/${id}/${action}`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      });
      setItems((xs) => (xs ?? []).filter((x) => x.id !== id));
    } finally { setBusy(null); }
  };

  if (!API) return <div className="muted">로컬 API 미설정 — 이 기능은 로컬에서만 동작합니다.</div>;

  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        <Home size={15} strokeWidth={2.2} /> 입주민 인증 검수 (관리자)
        {items && <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}> · 대기 {items.length}건</span>}
      </div>

      {err ? <div style={{ color: "crimson", fontSize: 13 }}>{err}</div>
        : !items ? <div className="muted">불러오는 중…</div>
        : items.length === 0 ? (
          <div className="muted" style={{ display: "flex", alignItems: "center", gap: 6, padding: 12 }}>
            <CheckCircle2 size={14} style={{ color: "#1a7f4b" }} /> 대기중인 인증이 없습니다.
          </div>
        ) : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr><th>회원</th><th>단지</th><th>서류</th><th>신청일</th><th>처리</th></tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id}>
                  <td style={{ fontSize: 12 }}>{it.member_no ? `#${it.member_no}` : it.user_id.slice(0, 8)}</td>
                  <td>
                    <Link to={`/complex/${it.complex_no}`} style={{ fontSize: 13 }}>
                      {it.complex_name ?? `단지 ${it.complex_no}`}
                    </Link>
                  </td>
                  <td>
                    <a href={`${API}/admin/resident-verifications/${it.id}/doc`} target="_blank" rel="noreferrer"
                      className="deal-link" style={{ fontSize: 12 }}>
                      <FileText size={12} /> 서류 보기
                    </a>
                  </td>
                  <td className="num" style={{ fontSize: 12 }}>{(it.created_at ?? "").slice(0, 10)}</td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="ai-send" style={{ padding: "4px 10px", fontSize: 12 }} disabled={busy === it.id}
                        onClick={() => decide(it.id, "approve")}>
                        <CheckCircle2 size={12} /> 승인
                      </button>
                      <button className="auth-btn ghost" style={{ padding: "4px 10px", fontSize: 12 }} disabled={busy === it.id}
                        onClick={() => decide(it.id, "reject")}>
                        <XCircle size={12} /> 거부
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
        승인 시 사용자에게 입주민 뱃지 + {50}P가 부여되고 서류는 즉시 폐기됩니다. 관리자 전용.
      </p>
    </>
  );
}
