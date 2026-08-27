import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { X, Gift, Coffee, Candy, Check } from "lucide-react";

const KEY = "koczip_evpopup_hide";   // 영구 숨김 — '다시 보지 않기'를 체크하고 닫은 사람만
const SEEN = "koczip_evpopup_seen";  // 이번 세션엔 한 번만(같은 방문 중 새로고침해도 재노출 X)

// 출시 기념 이벤트 접속 팝업.
//  - '다시 보지 않기' 체크 후 닫음 → 영구 숨김(localStorage).
//  - 그냥 닫으면 → 다음 방문 때 다시 노출(이번 세션에는 다시 안 뜸).
// 이벤트/쿠폰함/관리자/중개사앱 화면과 첫실행 인트로 스플래시 중엔 뜨지 않는다.
export default function EventPopup() {
  const loc = useLocation();
  const nav = useNavigate();
  const [show, setShow] = useState(false);
  const [dontShow, setDontShow] = useState(false);

  useEffect(() => {
    const p = loc.pathname;
    if (typeof location !== "undefined" && location.search.includes("shot=1")) return;  // 스크린샷 모드
    if (p.startsWith("/event") || p.startsWith("/me/coupons")
        || p.startsWith("/admin") || p.startsWith("/biz")) return;
    try {
      if (localStorage.getItem(KEY)) return;        // 영구 숨김한 사람
      if (sessionStorage.getItem(SEEN)) return;     // 이번 세션에 이미 봄
    } catch { return; }
    // 첫실행 인트로 스플래시(sessionStorage koczip_intro, ~3.4s) 뒤에 뜨도록 지연.
    const t = setTimeout(() => {
      setShow(true);
      try { sessionStorage.setItem(SEEN, "1"); } catch { /* ignore */ }
    }, 1400);
    return () => clearTimeout(t);
    // 최초 1회만 판단(경로 이동마다 재평가하지 않음)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const close = () => {
    if (dontShow) { try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } }
    setShow(false);
  };
  const go = () => { close(); nav("/event"); };

  if (!show) return null;
  return createPortal(
    <div className="evpop-ov" onClick={close} role="presentation">
      <div className="evpop" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="출시 기념 이벤트">
        <button className="evpop-x" onClick={close} aria-label="닫기"><X size={17} /></button>
        <div className="evpop-kicker">콕집 앱 출시 기념</div>
        <h2 className="evpop-title">미션 깨고<br />커피 쿠폰 받아가세요</h2>
        <div className="evpop-rewards">
          <span className="evpop-rw coffee"><Coffee size={22} strokeWidth={2.2} aria-hidden /><b>커피 최대 2잔</b></span>
          <span className="evpop-plus">+</span>
          <span className="evpop-rw candy"><Candy size={22} strokeWidth={2.2} aria-hidden /><b>추파춥스</b></span>
        </div>
        <p className="evpop-desc">앱에서 미션을 달성하면 쿠폰함에 바로 담겨요.</p>
        <button className="evpop-cta" onClick={go}><Gift size={17} strokeWidth={2.4} aria-hidden /> 이벤트 보러가기</button>
        <label className="evpop-dont">
          <input type="checkbox" checked={dontShow} onChange={(e) => setDontShow(e.target.checked)} />
          <span className="evpop-dont-box" aria-hidden><Check size={11} strokeWidth={3.4} /></span>
          다시 보지 않기
        </label>
      </div>
    </div>,
    document.body,
  );
}
