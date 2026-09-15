// 신규 중개사 가입(사무소 연동·직원 신청) 시 중개사 약관 동의를 함께 받는 모달.
//  · 기존 회원의 '기능 접근 시 동의'는 BizTermsGate가 담당(소급).
//  · 이 모달은 '가입 시 번들' — 새 중개사가 연동을 확정하는 그 순간에 동의를 받는다.
//  · 동의 기록은 기존 엔드포인트(/biz/terms/agree, 버전별 biz_terms_agreements)를 그대로 쓴다.
//  · 부담 없이 '한 번 눌러 동의'(clickwrap) — 별도 체크박스 없이 버튼 누름이 곧 동의 의사표시.
//    고지(위수탁)·전문 링크는 그대로 보여 주므로 유효한 동의로 성립. 취소하면 저장 안 함.
// 이미 동의했거나 관리자면 호출부에서 이 모달을 건너뛰고 바로 진행한다.
import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;

export function BizTermsConsentModal({ authH, onAgree, onClose, confirmLabel = "동의하고 연동" }: {
  authH: () => Record<string, string>;
  onAgree: () => void;            // 동의 저장 성공 후 실제 가입 동작(연동/신청) 실행
  onClose: () => void;
  confirmLabel?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async () => {
    if (busy) return;
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
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 400 }}>
        <div className="modal-title" style={{ marginBottom: 8 }}>중개사 약관 동의</div>
        <p className="muted" style={{ fontSize: 12.5, lineHeight: 1.6, margin: "0 0 6px" }}>
          계약서 작성·확인설명서·계약캘린더 이용을 위한 <b>중개사 약관</b>(임대인·임차인
          개인정보 처리 위·수탁 포함)이에요. 작성 문서의 법적 책임은 개업공인중개사에게 있습니다.
          {" "}
          <a href="/biz-terms" target="_blank" rel="noreferrer" style={{ whiteSpace: "nowrap" }}>전문 보기 ↗</a>
        </p>
        <p className="muted" style={{ fontSize: 11.5, margin: "0 0 12px" }}>
          아래 <b>‘{confirmLabel}’</b>을 누르면 중개사 약관에 동의하는 것으로 처리됩니다.
        </p>
        {err && <p className="modal-msg" style={{ marginTop: 0 }}>{err}</p>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 2 }}>
          <button className="chip" onClick={onClose} disabled={busy} style={{ cursor: "pointer" }}>나중에</button>
          <button className="ai-send" style={{ padding: "9px 18px", fontWeight: 800, opacity: busy ? 0.6 : 1, cursor: "pointer" }}
            disabled={busy} onClick={submit}>{busy ? "처리 중…" : confirmLabel}</button>
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
