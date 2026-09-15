import { useState } from "react";
import { MoreVertical, Flag, Ban } from "lucide-react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

// 이용자 콘텐츠 신고·차단 메뉴 (App Store 지침 1.2). 로그인 사용자에게만 노출.
// targetType: forum_post | forum_comment | realtor_review | complex_review
export default function ReportBlock({ targetType, targetId, onBlocked }:
    { targetType: string; targetId: number | string; onBlocked?: () => void }) {
  const { token } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!token) return null;

  const report = async () => {
    setOpen(false);
    const reason = window.prompt("신고 사유를 적어주세요. (선택)", "");
    if (reason === null) return;   // 취소
    setBusy(true);
    try {
      await fetch(`${API}/content/report`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ target_type: targetType, target_id: targetId, reason }),
      });
      window.alert("신고가 접수되었습니다. 검토 후 조치하겠습니다.");
    } catch { window.alert("신고 처리에 실패했어요. 잠시 후 다시 시도해주세요."); }
    finally { setBusy(false); }
  };

  const block = async () => {
    setOpen(false);
    if (!window.confirm("이 사용자를 차단할까요?\n차단하면 이 사용자의 글·댓글·리뷰가 보이지 않습니다.")) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/content/block`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ target_type: targetType, target_id: targetId }),
      });
      if (r.ok) { window.alert("차단했습니다."); onBlocked?.(); }
      else window.alert("차단할 수 없는 대상이에요.");
    } catch { window.alert("차단 처리에 실패했어요."); }
    finally { setBusy(false); }
  };

  return (
    <span className="rbmenu">
      <button className="rbmenu-btn" onClick={() => setOpen((v) => !v)} disabled={busy} aria-label="신고·차단 메뉴">
        <MoreVertical size={15} strokeWidth={2.2} aria-hidden />
      </button>
      {open && (
        <>
          <span className="rbmenu-ov" onClick={() => setOpen(false)} />
          <div className="rbmenu-pop" role="menu">
            <button onClick={report}><Flag size={13} strokeWidth={2.2} aria-hidden /> 신고</button>
            <button onClick={block}><Ban size={13} strokeWidth={2.2} aria-hidden /> 사용자 차단</button>
          </div>
        </>
      )}
    </span>
  );
}
