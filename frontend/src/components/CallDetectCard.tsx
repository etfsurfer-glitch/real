import { useState } from "react";
import { Phone, X } from "lucide-react";
import { isRealtorApp } from "../lib/appmode";
import { enableCallDetect } from "../lib/callDetect";

const DISMISS_KEY = "koczip:callDetect:dismissed";

// 중개사앱에서만 뜨는 '전화 고객알림 켜기' 원터치 카드.
// 이미 웹에 로그인된 회원이므로 전화번호 재인증(OTP) 없이, 세션으로 네이티브 토큰을 발급받아
// koczip://call-enable 로 네이티브에 넘긴다(발신자확인 역할 요청은 네이티브가 처리).
export default function CallDetectCard({ token }: { token: string | null }) {
  const [busy, setBusy] = useState(false);
  const [gone, setGone] = useState(() => {
    try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; }
  });

  // 앱(중개사앱)에서만, 로그인 상태에서만 노출. 브라우저·미로그인엔 안 뜬다.
  if (!isRealtorApp() || !token || gone) return null;

  const dismiss = () => {
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
    setGone(true);
  };

  const enable = async () => {
    setBusy(true);
    const r = await enableCallDetect(token);
    if (!r.ok) { alert(`전화 알림을 켤 수 없어요 — ${r.error}`); setBusy(false); return; }
    try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
    setTimeout(() => setGone(true), 500);
  };

  return (
    <div className="cdc">
      <div className="cdc-ic"><Phone size={18} strokeWidth={2.3} /></div>
      <div className="cdc-txt">
        <b>전화 오면 고객정보 띄우기</b>
        <span>고객 전화가 오면 누구인지·무슨 문의였는지 화면에 띄워드려요. (재인증 없이 바로)</span>
      </div>
      <button className="cdc-cta" onClick={enable} disabled={busy}>{busy ? "…" : "켜기"}</button>
      <button className="cdc-x" onClick={dismiss} aria-label="닫기"><X size={15} /></button>
    </div>
  );
}
