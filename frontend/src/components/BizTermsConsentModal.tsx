// 신규 중개사 가입(사무소 연동·직원 신청) 시 중개사 약관 동의를 함께 받는 모달.
//  · 기존 회원의 '기능 접근 시 동의'는 BizTermsGate가 담당(소급).
//  · 이 모달은 '가입 시 번들' — 새 중개사가 연동을 확정하는 그 순간에 동의를 받는다.
//  · 동의 기록은 기존 엔드포인트(/biz/terms/agree, 버전별 biz_terms_agreements)를 그대로 쓴다.
// 이미 동의했거나 관리자면 호출부에서 이 모달을 건너뛰고 바로 진행한다.
import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;

export function BizTermsConsentModal({ authH, onAgree, onClose, confirmLabel = "동의하고 연동" }: {
  authH: () => Record<string, string>;
  onAgree: () => void;            // 동의 저장 성공 후 실제 가입 동작(연동/신청) 실행
  onClose: () => void;
  confirmLabel?: string;
}) {
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async () => {
    if (!checked || busy) return;
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API_BASE}/biz/terms/agree`, { method: "POST", headers: authH() });
      if (!r.ok) { setErr("동의 저장에 실패했습니다. 잠시 후 다시 시도해 주세요."); return; }
      onAgree();
    } catch { setErr("네트워크 오류로 저장하지 못했습니다."); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420 }}>
        <div className="modal-title" style={{ marginBottom: 8 }}>중개사 약관 동의</div>
        <p className="muted" style={{ fontSize: 12.5, lineHeight: 1.65, margin: "0 0 10px" }}>
          중개사 라운지·앱의 계약서 작성·확인설명서·계약캘린더 등은 <b>중개사 약관</b>
          (전자문서 작성 보조 도구 이용 조건, 임대인·임차인 개인정보 처리 위·수탁 포함)에
          동의한 뒤 이용할 수 있습니다. 작성 문서의 법적 책임은 개업공인중개사에게 있습니다.
        </p>
        <a href="/biz-terms" target="_blank" rel="noreferrer" style={{ fontSize: 12.5 }}>약관 전문 보기 ↗</a>
        <label style={{ display: "flex", gap: 8, alignItems: "flex-start", margin: "14px 0", fontSize: 13, cursor: "pointer" }}>
          <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} style={{ marginTop: 2 }} />
          <span>[필수] 중개사 약관을 확인했으며 이에 동의합니다.</span>
        </label>
        {err && <p className="modal-msg" style={{ marginTop: 0 }}>{err}</p>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 4 }}>
          <button className="chip" onClick={onClose} disabled={busy} style={{ cursor: "pointer" }}>취소</button>
          <button className="ai-send" style={{ padding: "8px 16px", opacity: checked && !busy ? 1 : 0.5, cursor: checked ? "pointer" : "default" }}
            disabled={!checked || busy} onClick={submit}>{busy ? "저장 중…" : confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}

// 가입 확정 전 약관 동의 여부 조회 — 이미 동의했거나 관리자면 모달을 건너뛴다.
export async function bizTermsAgreed(authH: () => Record<string, string>): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/biz/terms/status`, { headers: authH() });
    if (!r.ok) return false;
    const d = await r.json();
    return !!(d?.agreed || d?.is_admin);
  } catch { return false; }
}
