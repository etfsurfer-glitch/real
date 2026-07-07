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
  // 단계 전환 대신 '발송됨' 상태 — 번호는 계속 보이고 인증번호 칸이 아래 추가된다
  // (발송 후 화면이 통째로 바뀌어 번호가 사라지니 변화를 인지 못하던 문제, 2026-07-07).
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const codeRef = useRef<HTMLInputElement>(null);

  // 발송되면 인증번호 칸에 자동 포커스 + 보이게 스크롤(모바일서 키보드에 가려 안 보이던 문제 보완)
  useEffect(() => {
    if (sent) {
      const t = setTimeout(() => {
        codeRef.current?.scrollIntoView({ block: "center" });
        codeRef.current?.focus();
      }, 60);
      return () => clearTimeout(t);
    }
  }, [sent]);

  const auth = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  // FastAPI detail 은 문자열 또는 {code,message} 객체일 수 있음
  const errText = (d: { detail?: unknown }, status: number): string => {
    const det = d?.detail;
    if (typeof det === "string") return det;
    if (det && typeof det === "object" && "message" in det) return String((det as { message: unknown }).message);
    return `오류 ${status}`;
  };

  // 네트워크 실패(Failed to fetch — API 재시작 blip 등)는 1.2초 후 1회 자동 재시도.
  const fetchRetry = async (url: string, init: RequestInit): Promise<Response> => {
    try {
      return await fetch(url, init);
    } catch {
      await new Promise((res) => setTimeout(res, 1200));
      return fetch(url, init);
    }
  };

  const sendCode = async () => {
    if (busy) return;
    setBusy(true); setMsg(""); setDevCode(null);
    try {
      const r = await fetchRetry(`${API}/me/phone/send-code`, {
        method: "POST", headers: auth, body: JSON.stringify({ phone }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(errText(d, r.status));
      setSent(true);
      setCode("");
      if (d.dev_code) setDevCode(d.dev_code); // 알리고 미설정(개발) 시 화면에 노출
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const verify = async () => {
    if (busy) return;
    setBusy(true); setMsg("");
    try {
      const r = await fetchRetry(`${API}/me/phone/verify`, {
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
  const fmtPhone = (p: string) =>
    p.length === 11 ? `${p.slice(0, 3)}-${p.slice(3, 7)}-${p.slice(7)}` : p;

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      {/* 팝업 크게 — 번호+인증칸이 한 화면에 여유 있게 */}
      <div className="modal-card" onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 440, width: "calc(100vw - 32px)", padding: "22px 22px 20px" }}>
        <div className="modal-head">
          <span className="modal-title"><ShieldCheck size={16} strokeWidth={2.2} aria-hidden /> 휴대폰 번호 인증</span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>

        {/* ① 휴대폰 번호 — 발송 후에도 계속 표시(어디로 보냈는지 확인 가능) */}
        <label className="modal-label">휴대폰 번호</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            className="ai-input" inputMode="numeric" placeholder="" maxLength={11}
            value={phone} readOnly={sent}
            style={sent ? { background: "#f1f5f9", color: "#475569", flex: 1 } : { flex: 1 }}
            onChange={(e) => setPhone(e.target.value.replace(/[^0-9]/g, ""))}
            onKeyDown={(e) => { if (e.key === "Enter" && !sent) sendCode(); }}
          />
          {sent && (
            <button type="button" className="phone-banner-x"
              style={{ fontSize: 13, padding: "0 12px", whiteSpace: "nowrap" }}
              onClick={() => { setSent(false); setCode(""); setMsg(""); setDevCode(null); }}>
              번호 변경
            </button>
          )}
        </div>

        {!sent && (
          <button className="auth-btn kakao modal-cta" disabled={busy || phone.length < 10} onClick={sendCode}>
            {busy ? "발송 중…" : "인증번호 받기"}
          </button>
        )}

        {/* ② 발송되면 아래에 인증번호 칸이 '추가'됨 — 화면 변화가 분명히 보이게 */}
        {sent && (
          <>
            <div style={{ margin: "12px 0 4px", padding: "10px 12px", background: "#eefaf2",
              border: "1px solid #bfe8cf", borderRadius: 10, fontSize: 13.5, color: "#1f7a4d", lineHeight: 1.5 }}>
              ✓ <b>{fmtPhone(phone)}</b> 로 인증번호를 보냈어요.<br />
              문자를 확인하고 아래에 입력해주세요. (5분 유효)
            </div>
            <label className="modal-label" style={{ marginTop: 10 }}>인증번호 6자리</label>
            <input
              ref={codeRef}
              className="ai-input" inputMode="numeric" autoComplete="one-time-code" placeholder="" maxLength={6}
              style={{ letterSpacing: 6, fontSize: 18, textAlign: "center" }}
              value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, ""))}
              onKeyDown={(e) => { if (e.key === "Enter") verify(); }}
            />
            <button className="auth-btn kakao modal-cta" disabled={busy || code.length < 6} onClick={verify}>
              {busy ? "확인 중…" : "인증 완료"}
            </button>
            <button type="button" disabled={busy} onClick={sendCode}
              style={{ marginTop: 8, width: "100%", background: "none", border: "none",
                color: "#64748b", fontSize: 12.5, textDecoration: "underline", cursor: "pointer" }}>
              문자가 안 왔나요? 재발송
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
