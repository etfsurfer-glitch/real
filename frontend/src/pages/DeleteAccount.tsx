import { useState } from "react";
import { Link } from "react-router-dom";
import { Trash2, ShieldCheck, Mail } from "lucide-react";
import { useAuth, logout } from "../auth";

// 계정·데이터 삭제 안내(공개 페이지) — Google Play "데이터 삭제" 정책용.
// 로그인 사용자는 여기서 바로 탈퇴, 미로그인은 절차 안내.
export default function DeleteAccount() {
  const { user, token } = useAuth();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const withdraw = async () => {
    if (!token) return;
    if (!window.confirm("정말 탈퇴하시겠어요?\n회원정보·포인트·작성한 글/리뷰가 모두 삭제되며 되돌릴 수 없습니다.")) return;
    setBusy(true);
    try {
      const r = await fetch(`${import.meta.env.VITE_API_BASE}/me`, {
        method: "DELETE", headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) { alert("탈퇴 처리에 실패했어요. 잠시 후 다시 시도해주세요."); setBusy(false); return; }
      setDone(true);
      await logout();
    } catch { alert("네트워크 오류로 탈퇴에 실패했어요."); }
    setBusy(false);
  };

  return (
    <div className="legal">
      <h1><Trash2 size={22} strokeWidth={2.2} style={{ verticalAlign: "-4px", marginRight: 6 }} />계정 및 데이터 삭제</h1>
      <p>
        콕집(koczip.com) 계정과 관련된 모든 개인정보를 삭제할 수 있습니다. 삭제는 즉시 처리되며 되돌릴 수 없습니다.
      </p>

      {done ? (
        <div className="legal-box ok">
          <ShieldCheck size={20} /> 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.
        </div>
      ) : (
        <>
          <h2>삭제되는 데이터</h2>
          <ul>
            <li>계정 정보 — 이메일, 전화번호, 닉네임, 프로필</li>
            <li>활동 데이터 — 포인트, 작성한 글·댓글·리뷰, 관심 단지·사무소</li>
            <li>인증 계정 — 카카오/구글 연동 로그인 정보(Supabase 인증)</li>
            <li>접속 로그의 개인정보(이메일·IP 등)는 비식별화 처리</li>
          </ul>
          <p className="legal-note">
            ※ 전자상거래법 등 관련 법령상 보존 의무가 있는 거래·결제 기록은 해당 법정 기간 동안 분리 보관 후 파기될 수 있습니다.
          </p>

          <h2>삭제 방법</h2>
          {user ? (
            <>
              <p>현재 <b>{user.name || user.email}</b> 님으로 로그인되어 있습니다. 아래 버튼으로 즉시 탈퇴할 수 있어요.</p>
              <button className="legal-danger-btn" disabled={busy} onClick={withdraw}>
                <Trash2 size={16} /> {busy ? "처리 중…" : "계정 영구 삭제(탈퇴)"}
              </button>
            </>
          ) : (
            <>
              <p>① 앱에서 <b>카카오/구글로 로그인</b> → 하단 <b>‘회원 탈퇴’</b> 버튼으로 직접 삭제할 수 있습니다.</p>
              <p>② 또는 아래 이메일로 가입하신 계정(이메일/전화번호)을 알려주시면 확인 후 삭제해 드립니다.</p>
              <a className="legal-mail" href="mailto:etfsurfer@gmail.com?subject=콕집 계정 삭제 요청">
                <Mail size={16} /> etfsurfer@gmail.com 으로 삭제 요청
              </a>
            </>
          )}

          <p className="legal-note" style={{ marginTop: 18 }}>
            처리 기간: 요청 즉시(앱 내) 또는 이메일 요청 후 영업일 기준 3일 이내.
          </p>
        </>
      )}

      <p style={{ marginTop: 24 }}>
        <Link to="/privacy">개인정보처리방침</Link> · <Link to="/">홈으로</Link>
      </p>
    </div>
  );
}
