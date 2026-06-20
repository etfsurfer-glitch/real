import { NavLink } from "react-router-dom";

/** 페이지 상단 인-페이지 하위메뉴 (실거래 통계의 .sub-nav 와 동일 스타일).
 *  헤더 호버 드롭다운과 별개로, 페이지 안에서도 같은 하위메뉴를 보여준다. */
export function SubNav({ tabs }: { tabs: { to: string; label: string }[] }) {
  return (
    <nav className="sub-nav">
      {tabs.map((t) => (
        <NavLink key={t.to} to={t.to} end
          className={({ isActive }) => (isActive ? "active" : "")}>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
