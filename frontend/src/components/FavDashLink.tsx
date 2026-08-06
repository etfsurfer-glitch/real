import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Heart } from "lucide-react";
import { useAuth } from "../auth";
import { subscribeFavs, loadFavs, favCount } from "../lib/favstore";
import { FavLoginModal } from "./FavHeart";

// 관심단지 대시보드 진입 버튼 — 헤더 아이콘(variant="head")과 목록 페이지 칩 두 모양.
// 하트 안에 등록 개수를 표시한다. 가오픈 동안은 관리자에게만 보임(정식 오픈 시 isAdmin 조건 제거
// — 아래 비로그인 분기는 그때를 위해 미리 둠).
export default function FavDashLink({ variant }: { variant?: "head" }) {
  const { token, isAdmin } = useAuth();
  const [, force] = useState(0);
  const [askLogin, setAskLogin] = useState(false);
  const [pulse, setPulse] = useState(false);
  useEffect(() => subscribeFavs(() => force((n) => n + 1)), []);
  useEffect(() => { if (token) loadFavs(token); }, [token]);
  // 관심단지 추가 성공(FavButton) → 헤더 하트를 잠깐 강조해 위치를 알려준다
  useEffect(() => {
    if (variant !== "head") return;
    let t: ReturnType<typeof setTimeout> | null = null;
    const h = () => {
      setPulse(true);
      if (t) clearTimeout(t);
      t = setTimeout(() => setPulse(false), 3600);
    };
    window.addEventListener("koczip:fav-added", h);
    return () => { window.removeEventListener("koczip:fav-added", h); if (t) clearTimeout(t); };
  }, [variant]);
  if (!isAdmin) return null;

  const n = favCount();
  const icon = (
    <span className={`favdash-ic${n > 0 ? " on" : ""}`}>
      <Heart size={variant === "head" ? 22 : 17} strokeWidth={2.2} fill={n > 0 ? "currentColor" : "none"} aria-hidden />
      {n > 0 && <i>{n > 99 ? "99" : n}</i>}
    </span>
  );
  const cls = (variant === "head" ? "fav-head" : "favdash") + (pulse ? " pulse" : "");
  const body = (
    <>
      {icon}
      {variant !== "head" && <span>관심단지</span>}
      {variant === "head" && pulse && <i className="fav-head-tag">여기에 모여요</i>}
    </>
  );

  if (!token) {
    return (
      <>
        <button type="button" className={cls} onClick={() => setAskLogin(true)} aria-label="관심단지">{body}</button>
        {askLogin && <FavLoginModal onClose={() => setAskLogin(false)} />}
      </>
    );
  }
  return (
    <Link to="/my/favorites" className={cls} aria-label={`관심단지 ${n}개 보기`} title="관심단지 대시보드">{body}</Link>
  );
}
