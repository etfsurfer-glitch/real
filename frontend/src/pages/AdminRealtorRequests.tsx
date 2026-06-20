import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type EditReq = {
  id: number; user_id: string; realtor_id: string; member_no: number | null;
  content: string; status: string; admin_note: string | null; created_at: string;
  office?: { realtor_id: string; realtor_name: string | null; address?: string | null };
};
type Verif = {
  id: number; user_id: string; realtor_id: string | null; claimed_name: string | null;
  has_doc: boolean; status: string; admin_note: string | null; created_at: string;
};

export default function AdminRealtorRequests() {
  const { token } = useAuth();
  const [tab, setTab] = useState<"edit" | "verif">("edit");
  const auth = useCallback(() => ({ Authorization: `Bearer ${token}` }), [token]);
  if (!API_BASE) return <div className="muted">로컬 API 미설정.</div>;
  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>중개사 라운지 요청 (관리자)</div>
      <div className="chip-row" style={{ marginBottom: 12 }}>
        <button className={`chip ${tab === "edit" ? "active" : ""}`} onClick={() => setTab("edit")}>정보수정요청</button>
        <button className={`chip ${tab === "verif" ? "active" : ""}`} onClick={() => setTab("verif")}>서류 인증</button>
      </div>
      {tab === "edit" ? <EditReqs auth={auth} /> : <Verifs auth={auth} />}
    </>
  );
}

function EditReqs({ auth }: { auth: () => Record<string, string> }) {
  const [items, setItems] = useState<EditReq[]>([]);
  const [status, setStatus] = useState("pending");
  const load = useCallback(() => {
    fetch(`${API_BASE}/admin/realtor-edit-requests?status=${status}`, { headers: auth() })
      .then((r) => r.json()).then((d) => setItems(d.items ?? [])).catch(() => {});
  }, [auth, status]);
  useEffect(() => { load(); }, [load]);
  const resolve = (id: number, st: string) => {
    const note = st === "rejected" ? (prompt("반려 사유(선택)") ?? "") : "";
    fetch(`${API_BASE}/admin/realtor-edit-requests/${id}`, {
      method: "POST", headers: { ...auth(), "Content-Type": "application/json" },
      body: JSON.stringify({ status: st, admin_note: note }),
    }).then(() => load());
  };
  return (
    <>
      <select className="ai-input" style={{ maxWidth: 160, padding: "6px 10px", marginBottom: 10 }}
        value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="pending">접수(대기)</option><option value="done">처리완료</option>
        <option value="rejected">반려</option><option value="">전체</option>
      </select>
      {items.length === 0 ? <div className="muted">없음</div> : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>중개사무소</th><th>요청내용</th><th>회원</th><th>접수</th><th>상태/처리</th></tr></thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td style={{ fontSize: 13 }}>
                    <Link to={`/realtor/${encodeURIComponent(r.realtor_id)}`}>{r.office?.realtor_name ?? r.realtor_id}</Link>
                    <div className="muted" style={{ fontSize: 11 }}>{r.office?.address}</div>
                  </td>
                  <td style={{ fontSize: 13, maxWidth: 360 }}>{r.content}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{r.member_no ? `#${r.member_no}` : "-"}</td>
                  <td className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>{r.created_at}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {r.status === "pending" ? (
                      <>
                        <button className="chip" onClick={() => resolve(r.id, "done")}>완료</button>{" "}
                        <button className="chip" onClick={() => resolve(r.id, "rejected")}>반려</button>
                      </>
                    ) : <span className="ctx-badge" style={{ background: "#eef2f5", color: "#555" }}>{r.status}</span>}
                    {r.admin_note && <div className="muted" style={{ fontSize: 11 }}>{r.admin_note}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Verifs({ auth }: { auth: () => Record<string, string> }) {
  const [items, setItems] = useState<Verif[]>([]);
  const [status, setStatus] = useState("pending");
  const load = useCallback(() => {
    fetch(`${API_BASE}/admin/realtor-verifications?status=${status}`, { headers: auth() })
      .then((r) => r.json()).then((d) => setItems(d.items ?? [])).catch(() => {});
  }, [auth, status]);
  useEffect(() => { load(); }, [load]);
  const act = (id: number, action: string, cur: string | null) => {
    let rid = cur ?? "";
    if (action === "approve") {
      rid = prompt("연동할 중개사무소 realtor_id (비우면 제출값 사용)", cur ?? "") ?? cur ?? "";
      if (!rid) { alert("realtor_id가 필요합니다"); return; }
    }
    const note = action === "reject" ? (prompt("반려 사유(선택)") ?? "") : "";
    fetch(`${API_BASE}/admin/realtor-verifications/${id}`, {
      method: "POST", headers: { ...auth(), "Content-Type": "application/json" },
      body: JSON.stringify({ action, realtor_id: rid, admin_note: note }),
    }).then(() => load());
  };
  return (
    <>
      <select className="ai-input" style={{ maxWidth: 160, padding: "6px 10px", marginBottom: 10 }}
        value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="pending">심사대기</option><option value="approved">승인</option>
        <option value="rejected">반려</option><option value="">전체</option>
      </select>
      {items.length === 0 ? <div className="muted">없음</div> : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>주장 사무소</th><th>realtor_id</th><th>서류</th><th>회원</th><th>접수</th><th>처리</th></tr></thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.id}>
                  <td>{v.claimed_name ?? "-"}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{v.realtor_id ?? "-"}</td>
                  <td>{v.has_doc ? <a href={`${API_BASE}/admin/realtor-verifications/${v.id}/document`} target="_blank" rel="noreferrer">문서 보기</a> : "-"}</td>
                  <td className="muted" style={{ fontSize: 11 }}>{v.user_id.slice(0, 8)}</td>
                  <td className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>{v.created_at}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {v.status === "pending" ? (
                      <>
                        <button className="chip" onClick={() => act(v.id, "approve", v.realtor_id)}>승인·연동</button>{" "}
                        <button className="chip" onClick={() => act(v.id, "reject", v.realtor_id)}>반려</button>
                      </>
                    ) : <span className="ctx-badge" style={{ background: "#eef2f5", color: "#555" }}>{v.status}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
