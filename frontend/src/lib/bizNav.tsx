// 중개사앱 메뉴트리(단일 소스) + 형제 이동 서브네비.
// 하단 5탭(홈/매물/고객/계약/더보기) 아래 2단계 메뉴를 여기 한곳에서 정의한다.
// 어느 하위 화면에서도 같은 계층(형제) 메뉴로 바로 이동할 수 있게, 각 섹션 화면 상단에
// <BizSubNav>를 깔아 형제 메뉴를 칩으로 보여 준다.
import { Link } from "react-router-dom";
import {
  Home, LayoutDashboard, ClipboardList, TrendingUp, LineChart, Presentation, ShieldCheck,
  Users, Shuffle, MessageSquare, FileText, Files, CalendarDays, FileCheck, Send, Globe,
  Star, Store, Phone, UserCog, Pencil, Settings,
} from "lucide-react";

// 메뉴 key → 아이콘(레일·아이콘레일 공용)
const RAIL_ICON: Record<string, React.ReactNode> = {
  home: <Home size={17} />, dash: <LayoutDashboard size={17} />,
  diary: <ClipboardList size={17} />, rank: <TrendingUp size={17} />, analyze: <LineChart size={17} />,
  brief: <Presentation size={17} />, audit: <ShieldCheck size={17} />,
  ledger: <Users size={17} />, match: <Shuffle size={17} />, leads: <MessageSquare size={17} />,
  wcontracts: <FileText size={17} />, contracts: <Files size={17} />, calendar: <CalendarDays size={17} />,
  verify: <FileCheck size={17} />, requests: <Send size={17} />, homepage: <Globe size={17} />,
  favs: <Star size={17} />, "fav-offices": <Store size={17} />, calls: <Phone size={17} />,
  staff: <UserCog size={17} />, office: <Store size={17} />, edit: <Pencil size={17} />,
  settings: <Settings size={17} />,
};

export type BizNavItem = { key: string; to: string; label: string; ownerOnly?: boolean };
export type BizSection = "listings" | "customers" | "contracts" | "more";

export const BIZ_NAV: Record<BizSection, BizNavItem[]> = {
  listings: [
    { key: "diary", to: "/biz/diary", label: "매물장" },
    { key: "rank", to: "/biz/rank", label: "매물순위" },
    { key: "analyze", to: "/biz/analyze", label: "실거래분석" },
    { key: "brief", to: "/biz/brief", label: "브리핑" },
    { key: "audit", to: "/biz/audit", label: "매물점검" },
  ],
  customers: [
    { key: "ledger", to: "/biz/ledger", label: "고객원장" },
    { key: "match", to: "/biz/match", label: "물건매칭" },
    { key: "leads", to: "/biz/leads", label: "상담신청" },
  ],
  contracts: [
    { key: "wcontracts", to: "/biz/wcontracts", label: "계약서 작성" },
    { key: "contracts", to: "/biz/contracts", label: "계약관리" },
    { key: "calendar", to: "/biz/calendar", label: "계약캘린더" },
    { key: "verify", to: "/biz/verify", label: "계약검증" },
  ],
  more: [
    { key: "requests", to: "/biz/requests", label: "콕집요청" },
    { key: "homepage", to: "/biz/homepage", label: "홈페이지" },
    { key: "favs", to: "/biz/favs", label: "관심단지" },
    { key: "fav-offices", to: "/biz/fav-offices", label: "관심중개사" },
    { key: "calls", to: "/biz/calls", label: "통화기록" },
    { key: "staff", to: "/biz/staff", label: "직원관리", ownerOnly: true },
    { key: "office", to: "/biz/office", label: "내 사무소" },
    { key: "edit", to: "/biz/edit", label: "정보수정" },
    { key: "settings", to: "/biz/settings", label: "설정" },
  ],
};

// 하단 탭 → 그 섹션의 첫 화면(대표 진입점)
export const BIZ_SECTION_HOME: Record<BizSection, string> = {
  listings: "/biz/diary", customers: "/biz/ledger", contracts: "/biz/contracts", more: "/biz/more",
};

export function bizSectionOf(screen?: string): BizSection | null {
  if (!screen) return null;
  for (const sec of ["listings", "customers", "contracts", "more"] as BizSection[]) {
    if (BIZ_NAV[sec].some((i) => i.key === screen)) return sec;
  }
  return null;
}

// 데스크톱 레일(사이드바) — 통합 셸의 PC 네비게이션. 라우터 기반(Link),
// 전 메뉴를 그룹으로 세로 나열. 모바일 하단탭과 같은 메뉴트리(BIZ_NAV)를 공유한다.
const RAIL_GROUPS: { label: string; items: BizNavItem[] }[] = [
  { label: "", items: [{ key: "home", to: "/biz", label: "홈" }, { key: "dash", to: "/biz/dash", label: "대시보드" }] },
  { label: "매물", items: BIZ_NAV.listings },
  { label: "고객", items: BIZ_NAV.customers },
  { label: "계약", items: BIZ_NAV.contracts },
  { label: "더보기", items: BIZ_NAV.more },
];

export function BizRail({ screen, role, mini }: { screen?: string; role?: string; mini?: boolean }) {
  return (
    <nav className={`biz-rail${mini ? " mini" : ""}`} aria-label="중개사 메뉴">
      <div className="biz-rail-logo">{mini ? <span className="biz-rail-mark">콕</span> : <>콕집 <span>중개사</span></>}</div>
      {RAIL_GROUPS.map((g, gi) => (
        <div className="biz-rail-g" key={gi}>
          {g.label && !mini && <p className="biz-rail-lab">{g.label}</p>}
          {g.label && mini && gi > 0 && <div className="biz-rail-div" aria-hidden />}
          {g.items.filter((it) => !it.ownerOnly || role === "owner").map((it) => {
            const active = it.key === "home" ? !screen : screen === it.key;
            return (
              <Link key={it.key} to={it.to} className={`biz-rail-i${active ? " on" : ""}`}
                aria-current={active ? "page" : undefined} title={mini ? it.label : undefined}>
                <span className="biz-rail-ic">{RAIL_ICON[it.key]}</span>
                {!mini && <span className="biz-rail-tx">{it.label}</span>}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

// 형제 메뉴 서브네비 — screen 이 속한 섹션의 형제 칩을 그린다(현재 항목 강조).
export function BizSubNav({ screen, role }: { screen?: string; role?: string }) {
  const sec = bizSectionOf(screen);
  if (!sec) return null;
  const items = BIZ_NAV[sec].filter((i) => !i.ownerOnly || role === "owner");
  if (items.length < 2) return null;
  return (
    <nav className="biz-navtabs" aria-label="같은 메뉴 형제 이동">
      {items.map((it) => (
        <Link key={it.key} to={it.to}
          className={`biz-navtab${screen === it.key ? " on" : ""}`}
          aria-current={screen === it.key ? "page" : undefined}>{it.label}</Link>
      ))}
    </nav>
  );
}
