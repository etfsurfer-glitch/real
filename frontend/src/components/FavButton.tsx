import { useEffect, useRef, useState } from "react";
import { Heart } from "lucide-react";
import { useAuth } from "../auth";
import { subscribeFavs, loadFavs, isFav, toggleFav } from "../lib/favstore";
import { FavLoginModal } from "./FavHeart";
import { flyToHeart, FavAddedPop } from "./favfx";

// 관심단지 토글(단지 상세 페이지용 라벨 버튼). 관심단지는 매일 16시 푸시알림 대상.
// 추가 성공 시 공용 효과(favfx): 안내 팝업 + 헤더 하트로 비행 애니메이션 + 하트 맥동.
export default function FavButton({ complexNo, complexName }: { complexNo: string; complexName?: string }) {
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

  const fav = !!token && isFav(complexNo);

  const onClick = async () => {
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
    <>
      <button ref={btnRef} className={`fav-btn${fav ? " on" : ""}`} onClick={onClick} disabled={busy} aria-label="관심단지">
        <Heart size={14} strokeWidth={2.4} fill={fav ? "currentColor" : "none"} aria-hidden />
        {fav ? "관심단지" : "관심단지 추가"}
      </button>
      {popAt && <FavAddedPop anchor={popAt} onClose={() => setPopAt(null)} />}
      {askLogin && <FavLoginModal onClose={() => setAskLogin(false)} />}
    </>
  );
}
