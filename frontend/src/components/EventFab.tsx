import { useLocation, useNavigate } from "react-router-dom";
import { Gift } from "lucide-react";

// 출시 기념 이벤트 플로팅 버튼 — 전 페이지 좌하단(우하단 도구 FAB 스택과 충돌 방지).
// 누르면 이벤트 페이지로. 앱 밖에서 눌러도 이벤트 페이지의 앱-게이트가 설치를 유도한다.
// 이벤트·쿠폰함·관리자·중개사앱 셸 화면에선 숨긴다.
export default function EventFab() {
  const loc = useLocation();
  const nav = useNavigate();
  const p = loc.pathname;
  if (typeof location !== "undefined" && location.search.includes("shot=1")) return null;  // 스크린샷 모드
  if (p.startsWith("/event") || p.startsWith("/me/coupons")
      || p.startsWith("/admin") || p.startsWith("/biz")) return null;
  return (
    <button className="event-fab" onClick={() => nav("/event")} aria-label="출시 기념 커피 쿠폰 이벤트">
      <span className="event-fab-ic"><Gift size={18} strokeWidth={2.5} aria-hidden /></span>
      <span className="event-fab-tx">커피 이벤트</span>
      <span className="event-fab-dot" aria-hidden />
    </button>
  );
}
