import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { ShieldCheck, Phone, X } from "lucide-react";
import { useAuth, getReferral, clearReferral } from "../auth";

const API = import.meta.env.VITE_API_BASE;

// 로그인했지만 전화번호 미인증인 사용자에게 상단 배너 + 인증 모달을 제공.
// 인증 성공 시 refreshMe() 로 /me 를 재조회해 배너가 사라진다.
export default function PhoneVerify() {
  const { user, token, phoneVerified, meLoaded, refreshMe } = usePhoneState();
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  // 모달이 한 번 열린 뒤 token이 순간 흔들려도(모바일 키보드 포커스→onAuthStateChange 재호출)
  // PhoneModal이 리마운트되어 입력 단계(stage)가 초기화되지 않도록 마지막 token을 고정.
  const lastToken = useRef<string | null>(null);
  if (token) lastToken.current = token;

  // 인증 완료되면 모달 닫기.
  useEffect(() => { if (phoneVerified) setOpen(false); }, [phoneVerified]);

  // 배너: /me 로드 완료 + 미인증일 때만(첫 로드 깜빡임 방지).
  const showBanner = !!user && !!token && meLoaded && !phoneVerified && !dismissed && !open;
  // ⚠️ 모달은 한 번 열리면 인증상태가 일시적으로 바뀌어도(앱전환·토큰갱신으로 user/meLoaded가 잠깐
  //    흔들려도) 언마운트하지 않는다 — 그래야 SMS 보고 돌아와 코드 입력칸이 사라지지 않음.
  if (!showBanner && !open) return null;

  return (
    <>
      {showBanner && (
        <div className="phone-banner">
          <span className="phone-banner-msg">
            <Phone size={14} strokeWidth={2.2} aria-hidden /> 휴대폰 번호를 인증하면 맞춤 알림·기능을 이용할 수 있어요.
          </span>
          <span className="phone-banner-actions">
            <button className="auth-btn kakao" style={{ padding: "5px 12px" }} onClick={() => setOpen(true)}>
              번호 인증
            </button>
            <button className="phone-banner-x" aria-label="닫기" onClick={() => setDismissed(true)}>
              <X size={14} />
            </button>
          </span>
        </div>
      )}
      {open && lastToken.current && <PhoneModal token={lastToken.current} onClose={() => setOpen(false)} onDone={async () => { await refreshMe(); setOpen(false); }} />}
    </>
  );
}

// useAuth 가 phoneVerified/refreshMe 를 포함하도록 좁혀 쓰는 헬퍼
function usePhoneState() {
  const a = useAuth();
  return {
    user: a.user,
    token: a.token,
    phoneVerified: !!a.user?.phoneVerified,
    meLoaded: a.adminChecked,   // /me 응답 완료 시점 (token 있으면 mergeMe 후 true)
    refreshMe: a.refreshMe,
  };
}

export function PhoneModal({ token, onClose, onDone }: { token: string; onClose: () => void; onDone: () => void }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState<"phone" | "code">("phone");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const codeRef = useRef<HTMLInputElement>(null);

  // 인증번호 단계로 가면 입력칸에 자동 포커스 + 보이게 스크롤(모바일서 키보드에 가려 안 보이던 문제 보완)
  useEffect(() => {
    if (stage === "code") {
      const t = setTimeout(() => {
        codeRef.current?.scrollIntoView({ block: "center" });
        codeRef.current?.focus();
      }, 60);
      return () => clearTimeout(t);
    }
  }, [stage]);

  const auth = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  // FastAPI detail 은 문자열 또는 {code,message} 객체일 수 있음
  const errText = (d: { detail?: unknown }, status: number): string => {
    const det = d?.detail;
    if (typeof det === "string") return det;
    if (det && typeof det === "object" && "message" in det) return String((det as { message: unknown }).message);
    return `오류 ${status}`;
  };

  const sendCode = async () => {
    if (busy) return;
    setBusy(true); setMsg(""); setDevCode(null);
    try {
      const r = await fetch(`${API}/me/phone/send-code`, {
        method: "POST", headers: auth, body: JSON.stringify({ phone }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(errText(d, r.status));
      setStage("code");
      setMsg("인증번호를 발송했어요. 5분 안에 입력해주세요.");
      if (d.dev_code) setDevCode(d.dev_code); // 알리고 미설정(개발) 시 화면에 노출
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const verify = async () => {
    if (busy) return;
    setBusy(true); setMsg("");
    try {
      const r = await fetch(`${API}/me/phone/verify`, {
        method: "POST", headers: auth,
        body: JSON.stringify({ code, ref: getReferral() }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(errText(d, r.status));
      clearReferral();
      onDone();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  // 모달은 portal 로 document.body 에 렌더. 헤더(backdrop-filter)·계정 드롭다운
  // 안에서 열려도 그 containing block 에 갇히지 않고 viewport 기준 정중앙에 뜬다.
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title"><ShieldCheck size={16} strokeWidth={2.2} aria-hidden /> 휴대폰 번호 인증</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>

        {stage === "phone" ? (
          <>
            <label className="modal-label">휴대폰 번호</label>
            <input
              className="ai-input" inputMode="numeric" placeholder="01012345678"
              value={phone} onChange={(e) => setPhone(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") sendCode(); }}
            />
            <button className="auth-btn kakao modal-cta" disabled={busy || !phone} onClick={sendCode}>
              {busy ? "발송 중…" : "인증번호 받기"}
            </button>
          </>
        ) : (
          <>
            <label className="modal-label">인증번호 6자리</label>
            <input
              ref={codeRef}
              className="ai-input" inputMode="numeric" autoComplete="one-time-code" placeholder="● ● ● ● ● ●" maxLength={6}
              value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, ""))}
              onKeyDown={(e) => { if (e.key === "Enter") verify(); }}
            />
            <button className="auth-btn kakao modal-cta" disabled={busy || code.length < 6} onClick={verify}>
              {busy ? "확인 중…" : "인증 완료"}
            </button>
            <button className="auth-btn ghost" style={{ marginTop: 6, width: "100%" }} disabled={busy} onClick={() => setStage("phone")}>
              번호 다시 입력
            </button>
          </>
        )}

        {devCode && (
          <div className="modal-devcode">개발 모드 — 인증번호: <b>{devCode}</b></div>
        )}
        {msg && <div className="modal-msg">{msg}</div>}
      </div>
    </div>,
    document.body,
  );
}
