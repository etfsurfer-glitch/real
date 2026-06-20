import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { useAuth } from "../auth";

const API_BASE = import.meta.env.VITE_API_BASE;

type U = {
  id: string; member_no?: number | null; email: string | null; phone: string | null;
  phone_verified?: boolean; name: string | null; avatar: string | null; provider: string | null;
  created_at: string | null; last_sign_in_at: string | null;
};

function fmt(ts: string | null): string {
  if (!ts) return "-";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts.replace("T", " ").slice(0, 16);
  // 한국시간(KST, UTC+9)으로 표시 — 브라우저 타임존과 무관하게 고정
  const kst = new Date(d.getTime() + 9 * 60 * 60 * 1000);
  return kst.toISOString().replace("T", " ").slice(0, 16);
}

export default function AdminUsers() {
  const { token } = useAuth();
  const [users, setUsers] = useState<U[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token || !API_BASE) return;
    fetch(`${API_BASE}/admin/users?per_page=500`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => { if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 160)}`); return r.json(); })
      .then((d) => setUsers(d.users ?? []))
      .catch((e) => setErr(String(e)));
  }, [token]);

  const grantPoints = async (u: U) => {
    const raw = window.prompt(
      `${u.name ?? (u.member_no ? "#" + u.member_no : u.id)} 님 포인트 지급/차감\n예: 1000 (지급) · -500 (차감)`);
    if (raw == null) return;
    const delta = parseInt(raw.trim(), 10);
    if (!delta || Number.isNaN(delta)) { alert("숫자를 입력하세요."); return; }
    const reason = window.prompt("사유(선택)", "관리자 조정") ?? "";
    try {
      const r = await fetch(`${API_BASE}/admin/users/${u.id}/points`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ delta, reason }),
      });
      if (r.ok) { const d = await r.json(); alert(`완료 — 새 잔액 ${Number(d.balance).toLocaleString()}P`); }
      else alert("실패: " + (await r.text()).slice(0, 140));
    } catch (e) { alert("오류: " + String(e)); }
  };

  const unverifyPhone = async (u: U) => {
    if (!window.confirm(`${u.name ?? (u.member_no ? "#" + u.member_no : "")} 님의 전화번호 인증(${u.phone ?? ""})을 해제할까요?\n번호가 비워지고 본인이 다시 인증해야 합니다. (회원번호·포인트는 유지)`)) return;
    try {
      const r = await fetch(`${API_BASE}/admin/users/${u.id}/unverify-phone`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        setUsers((us) => us ? us.map((x) => x.id === u.id ? { ...x, phone: null, phone_verified: false } : x) : us);
        alert("전화번호 인증을 해제했습니다.");
      } else alert("실패: " + (await r.text()).slice(0, 140));
    } catch (e) { alert("오류: " + String(e)); }
  };

  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        <Users size={15} strokeWidth={2.2} aria-hidden /> 가입 사용자 (관리자){" "}
        {users && <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>{users.length}명</span>}
      </div>

      {err ? <div style={{ color: "crimson", fontSize: 13 }}>{err}</div>
        : !users ? <div className="muted">불러오는 중…</div>
        : users.length === 0 ? <div className="muted">아직 가입한 사용자가 없습니다.</div>
        : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>#</th><th>회원번호</th><th>회원</th><th>이메일</th><th>전화</th>
                <th>가입경로</th><th>가입일</th><th>최근 로그인</th><th>포인트</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => (
                <tr key={u.id}>
                  <td style={{ color: "#999" }}>{i + 1}</td>
                  <td style={{ fontSize: 12, fontFamily: "monospace", color: u.member_no ? "#1268d3" : "#bbb" }}>
                    {u.member_no ? `#${u.member_no}` : "—"}
                  </td>
                  <td>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
                      {u.avatar
                        ? <img src={u.avatar} alt="" width={24} height={24} style={{ borderRadius: "50%" }} />
                        : <span style={{ width: 24, height: 24, borderRadius: "50%", background: "#e3e8ee", display: "inline-block" }} />}
                      <b>{u.name ?? "회원"}</b>
                    </span>
                  </td>
                  <td style={{ fontSize: 12 }}>{u.email ?? "-"}</td>
                  <td style={{ fontSize: 12 }}>
                    {u.phone ?? "-"}
                    {u.phone_verified && (
                      <span className="ctx-badge" style={{ background: "#e6f7ed", color: "#1a7f4b", marginLeft: 5 }}>인증</span>
                    )}
                  </td>
                  <td><span className="ctx-badge" style={{ background: "#fee500", color: "#3a1d1d" }}>{u.provider ?? "-"}</span></td>
                  <td className="num" style={{ fontSize: 12 }}>{fmt(u.created_at)}</td>
                  <td className="num" style={{ fontSize: 12 }}>{fmt(u.last_sign_in_at)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="contact-btn" style={{ background: "#eef5ff", color: "#1268d3", padding: "3px 9px", fontSize: 12 }}
                      onClick={() => grantPoints(u)}>지급/차감</button>
                    {u.phone_verified && (
                      <button className="contact-btn" style={{ background: "#fff0f0", color: "#c0392b", padding: "3px 9px", fontSize: 12, marginLeft: 6 }}
                        onClick={() => unverifyPhone(u)}>인증해제</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted" style={{ fontSize: 11, marginTop: 10 }}>
        Supabase Auth 기준 · 카카오 동의항목(닉네임·이메일·전화)을 수집합니다. 관리자만 조회 가능.
      </p>
    </>
  );
}
