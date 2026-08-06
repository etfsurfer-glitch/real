import { createPortal } from "react-dom";
import { Heart } from "lucide-react";

// 관심단지 추가 성공 공용 효과 — 큰 버튼(FavButton)과 목록 미니 하트(FavHeart)가 같이 쓴다.
// ①안내 팝업(헤더 미니 모형으로 하트 위치를 그림으로) ②버튼→헤더 하트 비행 애니메이션
// ③도착 시 koczip:fav-added 이벤트 → 헤더 하트 맥동+말풍선(FavDashLink).
const HEART_SVG = '<svg viewBox="0 0 24 24" width="22" height="22" fill="#e0245e" stroke="#e0245e">'
  + '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>';

export function flyToHeart(fromEl: HTMLElement) {
  const target = document.querySelector(".fav-head");
  if (!target) { window.dispatchEvent(new CustomEvent("koczip:fav-added")); return; }
  const a = fromEl.getBoundingClientRect();
  const b = target.getBoundingClientRect();
  const el = document.createElement("span");
  el.className = "fav-fly";
  el.innerHTML = HEART_SVG;
  el.style.left = `${a.x + a.width / 2 - 11}px`;
  el.style.top = `${a.y + a.height / 2 - 11}px`;
  document.body.appendChild(el);
  const dx = (b.x + b.width / 2) - (a.x + a.width / 2);
  const dy = (b.y + b.height / 2) - (a.y + a.height / 2);
  const anim = el.animate([
    { transform: "translate(0,0) scale(1)", opacity: 1 },
    { transform: `translate(${dx * 0.55}px, ${dy * 0.55 - 46}px) scale(1.6)`, opacity: 1, offset: 0.55 },
    { transform: `translate(${dx}px, ${dy}px) scale(0.55)`, opacity: 0.3 },
  ], { duration: 1000, easing: "cubic-bezier(.3,.7,.35,1)" });
  anim.onfinish = () => {
    el.remove();
    window.dispatchEvent(new CustomEvent("koczip:fav-added"));   // 도착 → 헤더 하트 강조
  };
}

/** 추가 성공 팝업 — 클릭한 하트 근처(fixed)에 뜨고, 헤더 미니 모형으로 위치를 보여준다. */
export function FavAddedPop({ anchor, onClose }: { anchor: DOMRect; onClose: () => void }) {
  const W = 252;
  const left = Math.max(8, Math.min(anchor.x - 10, window.innerWidth - W - 12));
  const top = anchor.y + anchor.height + 10;
  const arrowX = Math.max(14, Math.min(anchor.x + anchor.width / 2 - left - 5, W - 24));
  return createPortal(
    <span className="favadd-pop" role="status" style={{ left, top, width: W }} onClick={onClose}>
      <i className="favadd-arrow" style={{ left: arrowX }} />
      <b>관심단지에 담았어요!</b>
      <span className="favadd-mock" aria-hidden>
        <span className="m-logo">콕집</span>
        <i className="m-pill" style={{ width: 30 }} />
        <i className="m-pill" style={{ width: 22 }} />
        <i className="m-pill" style={{ width: 26 }} />
        <span className="m-heart">
          <Heart size={13} strokeWidth={2.4} fill="#e0245e" color="#e0245e" />
          <em>여기!</em>
        </span>
        <span className="m-avatar" />
      </span>
      화면 <strong>오른쪽 위 하트</strong>를 누르면 언제든 모아볼 수 있어요
    </span>,
    document.body,
  );
}
