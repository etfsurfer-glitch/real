import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Heart, X } from "lucide-react";
import { useAuth, loginKakao, loginGoogle } from "../auth";
import { subscribeFavs, loadFavs, isFav, toggleFav } from "../lib/favstore";
import { flyToHeart, FavAddedPop } from "./favfx";
import CompareButton from "./CompareButton";

// 목록용 미니 관심단지 하트 — 단지명이 나오는 어디에나 끼워 넣는다.
// 비로그인: 하트는 보이되, 누르면 회원가입 안내 모달.
// 카드 전체가 <Link>인 곳에서도 동작하도록 클릭은 항상 preventDefault+stopPropagation.
// 추가 성공 시 공용 효과(favfx): 안내 팝업 + 헤더 하트 비행 + 맥동.
export default function FavHeart({ complexNo, complexName, noCompare }: { complexNo: string; complexName?: string; noCompare?: boolean }) {
  const { token } = useAuth();
  const [, force] = useState(0);
  const [busy, setBusy] = useState(false);
  const [askLogin, setAskLogin] = useState(false);
  const [popAt, setPopAt] = useState<DOMRect | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const hideT = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => subscribeFavs(() => force((n) => n + 1)), []);
  useEffect(() => { if (token) loadFavs(token); }, [token]);
  useEffect(() => () => { if (hideT.current) clearTimeout(hideT.current); }, []);

  const fav = isFav(complexNo);

  const onClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!token) { setAskLogin(true); return; }
    if (busy) return;
    setBusy(true);
    const res = await toggleFav(token, complexNo, complexName);
    if (res.error) alert(res.error);
    else if (res.fav && btnRef.current) {
      setPopAt(btnRef.current.getBoundingClientRect());
      flyToHeart(btnRef.current);
      if (hideT.current) clearTimeout(hideT.current);
      hideT.current = setTimeout(() => setPopAt(null), 6000);
    } else {
      setPopAt(null);
    }
    setBusy(false);
  };

  return (
    <span className="fav-cmp-wrap">
      <button
        ref={btnRef}
        type="button"
        className={`fav-heart${fav ? " on" : ""}`}
        onClick={onClick}
        disabled={busy}
        aria-label={fav ? "관심단지 해제" : "관심단지 추가"}
        title={fav ? "관심단지 해제" : "관심단지 추가"}
      >
        <Heart size={13} strokeWidth={2.4} fill={fav ? "currentColor" : "none"} aria-hidden />
      </button>
      {!noCompare && complexNo && <CompareButton complexNo={complexNo} complexName={complexName} />}
      {popAt && <FavAddedPop anchor={popAt} onClose={() => setPopAt(null)} />}
      {askLogin && <FavLoginModal onClose={() => setAskLogin(false)} />}
    </span>
  );
}

// 비로그인 안내 — 가입하면 관심단지에서 뭘 볼 수 있는지 알려주고 로그인으로 유도.
export function FavLoginModal({ onClose }: { onClose: () => void }) {
  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: 360 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">
            <Heart size={15} strokeWidth={2.4} fill="currentColor" style={{ color: "#e0245e" }} aria-hidden /> 관심단지
          </span>
          <button className="phone-banner-x" aria-label="닫기" onClick={onClose}><X size={16} /></button>
        </div>
        <p style={{ margin: "6px 0 4px", fontSize: 13.5, lineHeight: 1.65, color: "#46566b" }}>
          관심단지는 <b>회원가입 후</b> 볼 수 있어요.<br />
          가입하면 등록한 단지의 <b>시세·새 매물·급매·신고가</b>를
          한눈에 확인할 수 있습니다.
        </p>
        <button className="auth-btn kakao modal-cta" onClick={() => loginKakao()}>카카오로 시작하기</button>
        <button className="auth-btn google modal-cta" style={{ marginTop: 8 }} onClick={() => loginGoogle()}>구글로 시작하기</button>
      </div>
    </div>,
    document.body,
  );
}
