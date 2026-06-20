import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth";

const API = import.meta.env.VITE_API_BASE;

/** 최초 로그인 온보딩 모달.
 *  - 약관/개인정보 미동의(needsConsent) 시: 필수 동의 + 선택(마케팅) 수집
 *  - 닉네임 미설정(needsNickname) 시: 닉네임 설정
 *  둘 다 필요하면 한 화면에서 동의 → 닉네임 순으로 처리한다. */
export default function NicknameModal() {
  const { user, token, refreshMe } = useAuth();
  const [name, setName] = useState("");
  const [state, setState] = useState<"idle" | "checking" | "ok" | "bad">("idle");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const timer = useRef<number | null>(null);

  const needConsent = !!user?.needsConsent;
  const needNick = !!user?.needsNickname;
  const open = !!token && !!user && (needConsent || needNick);

  // 닉네임 입력 → 디바운스 중복/형식 검사
  useEffect(() => {
    if (!open || !needNick) return;
    if (timer.current) window.clearTimeout(timer.current);
    const v = name.trim();
    if (!v) { setState("idle"); setMsg(""); return; }
    setState("checking");
    timer.current = window.setTimeout(async () => {
      try {
        const r = await fetch(`${API}/me/nickname/check?name=${encodeURIComponent(v)}`,
          { headers: { Authorization: `Bearer ${token}` } });
        const d = await r.json();
        if (d.available) { setState("ok"); setMsg("사용 가능한 닉네임이에요"); }
        else { setState("bad"); setMsg(d.reason || "사용할 수 없어요"); }
      } catch { setState("idle"); setMsg(""); }
    }, 350);
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [name, open, needNick, token]);

  if (!open) return null;

  const allAgreed = agreeTerms && agreePrivacy;
  const canSubmit =
    (!needConsent || allAgreed) &&
    (!needNick || state === "ok") &&
    !busy;

  const setAll = (v: boolean) => { setAgreeTerms(v); setAgreePrivacy(v); setMarketing(v); };

  const submit = async () => {
    if (!canSubmit) return;
    setBusy(true);
    setErr("");
    try {
      if (needConsent) {
        const r = await fetch(`${API}/me/consent`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ agree_terms: agreeTerms, agree_privacy: agreePrivacy, marketing }),
        });
        if (!r.ok) {
          const d = await r.json().catch(() => ({}));
          setErr(typeof d.detail === "string" ? d.detail : "동의 처리에 실패했어요");
          return;
        }
      }
      if (needNick) {
        const r = await fetch(`${API}/me/nickname`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ nickname: name.trim() }),
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) { setState("bad"); setMsg(typeof d.detail === "string" ? d.detail : "설정 실패"); return; }
      }
      await refreshMe();
    } finally { setBusy(false); }
  };

  return (
    <div className="nick-overlay">
      <div className="nick-modal">
        <h3>콕집에 오신 걸 환영해요</h3>

        {needConsent && (
          <div className="consent-box">
            <label className="consent-all">
              <input type="checkbox" checked={allAgreed && marketing} onChange={(e) => setAll(e.target.checked)} />
              <b>전체 동의</b> (선택 항목 포함)
            </label>
            <div className="consent-divider" />
            <label className="consent-row">
              <input type="checkbox" checked={agreeTerms} onChange={(e) => setAgreeTerms(e.target.checked)} />
              <span><em>[필수]</em> <a href="/terms" target="_blank" rel="noopener">이용약관</a>에 동의합니다</span>
            </label>
            <label className="consent-row">
              <input type="checkbox" checked={agreePrivacy} onChange={(e) => setAgreePrivacy(e.target.checked)} />
              <span><em>[필수]</em> <a href="/privacy" target="_blank" rel="noopener">개인정보 수집·이용</a>에 동의합니다</span>
            </label>
            <label className="consent-row">
              <input type="checkbox" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} />
              <span><em className="opt">[선택]</em> 마케팅·혜택 알림 수신에 동의합니다</span>
            </label>
          </div>
        )}

        {needNick && (
          <>
            <p className="muted" style={{ fontSize: 13, margin: needConsent ? "10px 0 -2px" : "-4px 0 0" }}>
              토론장 글·단지 리뷰·AI 답변에서 쓸 닉네임을 정해주세요. (한글·영문·숫자 2~12자)
            </p>
            <input
              className="nick-input" autoFocus={!needConsent} value={name} maxLength={12}
              placeholder="예: 둔산동부린이"
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
            {msg && <div className={`nick-msg ${state}`}>{msg}</div>}
          </>
        )}

        {err && <div className="nick-msg bad">{err}</div>}

        <button className="ai-send nick-submit" disabled={!canSubmit} onClick={submit}>
          {busy ? "처리 중…" : needNick ? "동의하고 시작" : "동의하고 시작"}
        </button>
      </div>
    </div>
  );
}
