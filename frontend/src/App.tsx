import { type ReactNode, useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { Link, NavLink, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { SubNav } from "./components/SubNav";
import {
  Sparkles, LayoutDashboard, BadgePercent,
  TrendingUp, BarChart3, Award, Users, Wrench, ShieldAlert,
  ClipboardCheck, ScrollText, Menu as MenuIcon, X as XIcon,
  ChevronDown, Home as HomeIcon, MessagesSquare, Building2, Database, Bell, type LucideIcon,
} from "lucide-react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { PerfBadge } from "./components/PerfBadge";
import { AuthProvider, useAuth, logout, loginKakao, loginGoogle } from "./auth";
import PhoneVerify from "./components/PhoneVerify";
import AccountMenu from "./components/AccountMenu";
import Overview from "./pages/Overview";
import ComplexDetail from "./pages/ComplexDetail";
import Terms from "./pages/Terms";
import Privacy from "./pages/Privacy";
import { ChangesLayout, ChangesTrend, ChangesRegion, ChangesMovers } from "./pages/Changes";
import QuickDeals from "./pages/QuickDeals";
import RealtorRanks, { RealtorNational, RealtorBySido, RealtorByTenure, RealtorByStaff, RealtorByDong } from "./pages/RealtorRanks";
import Realtor from "./pages/Realtor";
import SuspiciousRealtors from "./pages/SuspiciousRealtors";
import AdminDashboard from "./pages/AdminDashboard";
import AdminReviews from "./pages/AdminReviews";
import AdminRealtorMatch from "./pages/AdminRealtorMatch";
import AdminUsers from "./pages/AdminUsers";
import AdminLogs from "./pages/AdminLogs";
import AdminResident from "./pages/AdminResident";
import AdminRealtorRequests from "./pages/AdminRealtorRequests";
import AdminDataSources from "./pages/AdminDataSources";
import AdminPush from "./pages/AdminPush";
import MapView from "./pages/MapView";
import CancelledTx from "./pages/CancelledTx";
import PresaleTx from "./pages/PresaleTx";
import Lounge from "./pages/Lounge";
import RealtorHomepage from "./pages/RealtorHomepage";
import MyHood from "./pages/MyHood";
import MyComplex from "./pages/MyComplex";
import InAppAutoExternal from "./components/InAppAutoExternal";
import TodayDeals from "./pages/TodayDeals";
import TodayListings from "./pages/TodayListings";
import TodayStats from "./pages/TodayStats";
import AiChat from "./pages/AiChat";
import ForumList from "./pages/ForumList";
import ForumPost from "./pages/ForumPost";
import ForumCompose from "./pages/ForumCompose";
import NicknameModal from "./components/NicknameModal";
import PointsToast from "./components/PointsToast";
import InAppBrowserBanner from "./components/InAppBrowserBanner";
import RealtorPromoBanner from "./components/RealtorPromoBanner";
import { TxStatsLayout, TxTopPrice, TxTopVolume, TxLowPrice } from "./pages/TxStats";
import {
  TxGapRank, TxPriceChange,
  TxPyeongPrice, TxTurnover, TxYield, TxRecordHigh,
} from "./pages/TxStatsMore";
import { TxRegionPulse } from "./pages/TxRegionPulse";

// 하위메뉴(드롭다운 자식)는 아이콘 없는 게 표준 — icon 필드를 두지 않아 구조적으로 통일.
type NavChild = { to: string; label: string };
type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean; children?: NavChild[] };

const NAV_ITEMS: NavItem[] = [
  { to: "/ai", label: "AI 분석", icon: Sparkles, end: true },
  { to: "/today", label: "TODAY", icon: LayoutDashboard, children: [
    { to: "/today", label: "우리동네" },
    { to: "/today/find", label: "우리단지찾기" },
    { to: "/today/old/deals", label: "전국실거래" },
    { to: "/today/old/listings", label: "전국급매" },
    { to: "/today/old/stats", label: "오늘 매물 통계" },
  ] },
  { to: "/realtors", label: "중개사무소 랭킹", icon: Award, children: [
    { to: "/realtors/national", label: "매물보유순위(전국)" },
    { to: "/realtors/region", label: "매물보유순위(지역별)" },
    { to: "/realtors/tenure", label: "업력순위" },
    { to: "/realtors/staff", label: "직원수순위" },
  ] },
  { to: "/quick-deals", label: "급매찾기", icon: BadgePercent },
  { to: "/changes", label: "매물가격추이", icon: TrendingUp, children: [
    { to: "/changes/trend", label: "가격 추이" },
    { to: "/changes/region", label: "지역별 순위" },
    { to: "/changes/movers", label: "상승·하락" },
  ] },
  { to: "/tx-stats", label: "실거래 통계", icon: BarChart3, children: [
    { to: "/tx-stats/region-pulse", label: "지역별 거래량" },
    { to: "/tx-stats/record-high", label: "단지별 신고가" },
    { to: "/tx-stats/top-price", label: "실거래 최고가" },
    { to: "/tx-stats/top-volume", label: "거래량" },
    { to: "/tx-stats/low-price", label: "시세차이 저가" },
    { to: "/tx-stats/gap", label: "갭투자" },
    { to: "/tx-stats/price-change", label: "가격변동률" },
    { to: "/tx-stats/pyeong-price", label: "평당가" },
    { to: "/tx-stats/turnover", label: "거래회전율" },
    { to: "/tx-stats/yield", label: "월세수익률" },
    { to: "/tx-stats/cancelled", label: "취소거래" },
    { to: "/tx-stats/presale", label: "분양권" },
  ] },
  { to: "/forum", label: "토론장", icon: MessagesSquare },
  { to: "/lounge", label: "중개사 라운지", icon: Building2 },
];

function TodayLayout() {
  return (
    <div>
      <SubNav tabs={[
        { to: "/today/old/deals", label: "전국실거래" },
        { to: "/today/old/listings", label: "전국급매" },
        { to: "/today/old/stats", label: "오늘 매물 통계" },
      ]} />
      <Outlet />
    </div>
  );
}

function MapLayout() {
  // 급매지도는 매물지도에 통합됨 — 탭 제거(단일 지도)
  return (
    <div>
      <Outlet />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}

function AppShell() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  // 라우트 바뀌면 모바일 드로어 자동 닫힘(뒤로가기 포함)
  useEffect(() => { setMenuOpen(false); }, [location.pathname]);
  // real.koczip.com 은 중개사 홈페이지 전용 호스트 — 루트 /{slug} 가 곧 홈페이지.
  const isRealHost = typeof window !== "undefined" && window.location.hostname === "real.koczip.com";
  if (isRealHost) {
    return (
      <ErrorBoundary key={location.pathname}>
        <InAppAutoExternal />
        <Routes>
          <Route path="/:slug" element={<RealtorHomepage />} />
          <Route path="*" element={<RealtorHomepage />} />
        </Routes>
      </ErrorBoundary>
    );
  }
  // koczip.com/r/{slug} (서브도메인 외 접근) 도 동일하게 크롬 없이 렌더.
  if (location.pathname.startsWith("/r/")) {
    return (
      <ErrorBoundary key={location.pathname}>
        <InAppAutoExternal />
        <Routes><Route path="/r/:slug" element={<RealtorHomepage />} /></Routes>
      </ErrorBoundary>
    );
  }
  return (
    <div className="layout">
      <header className="top">
        <h1>
          <Link to="/" style={{ color: "inherit", display: "inline-flex", alignItems: "center", gap: 8 }}>
            <img src="/logo.svg" alt="" width="28" height="28" style={{ verticalAlign: "middle" }} />
            <span>콕집</span>
          </Link>
        </h1>
        <nav>
          {NAV_ITEMS.map((item) => item.children ? (
            <div className="nav-group" key={item.to}>
              <NavLink to={item.to} className={({ isActive }) => isActive ? "nav-parent active" : "nav-parent"}>
                <item.icon size={14} strokeWidth={2.2} aria-hidden />
                {item.label}
                <ChevronDown size={12} strokeWidth={2.4} className="nav-caret" aria-hidden />
              </NavLink>
              <div className="nav-dropdown">
                {item.children.map((ch) => (
                  <NavLink key={ch.to} to={ch.to} end={ch.to === item.to} className={({ isActive }) => isActive ? "active" : ""}>
                    {ch.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => isActive ? "active" : ""}
            >
              <item.icon size={14} strokeWidth={2.2} aria-hidden />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <button className="nav-burger" aria-label="메뉴 열기" onClick={() => setMenuOpen(true)}>
          <MenuIcon size={19} strokeWidth={2.4} aria-hidden />
          <span className="nav-burger-label">메뉴</span>
        </button>
        <AuthControl />
      </header>

      {menuOpen && createPortal(
        <div className="mdrawer-ov" onClick={() => setMenuOpen(false)}>
          <nav className="mdrawer" onClick={(e) => e.stopPropagation()}>
            <div className="mdrawer-head">
              <span className="mdrawer-title">메뉴</span>
              <button className="phone-banner-x" aria-label="닫기" onClick={() => setMenuOpen(false)}>
                <XIcon size={18} />
              </button>
            </div>
            {NAV_ITEMS.map((item) => (
              <div className="mdrawer-sec" key={item.to}>
                <NavLink to={item.to} end={item.end}
                  className={({ isActive }) => "mdrawer-parent" + (isActive ? " active" : "")}
                  onClick={() => setMenuOpen(false)}>
                  <item.icon size={17} strokeWidth={2.2} aria-hidden /> {item.label}
                </NavLink>
                {item.children && (
                  <div className="mdrawer-children">
                    {item.children.map((ch) => (
                      <NavLink key={ch.to} to={ch.to} end={ch.to === item.to}
                        className={({ isActive }) => "mdrawer-child" + (isActive ? " active" : "")}
                        onClick={() => setMenuOpen(false)}>
                        {ch.label}
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </nav>
        </div>,
        document.body,
      )}
      <InAppBrowserBanner />
      <AdminBar />
      <PhoneVerify />
      <NicknameModal />
      <PointsToast />
      <RealtorPromoBanner />
      <ErrorBoundary key={location.pathname}>
      <Routes>
        <Route path="/" element={<MyHood />} />
        <Route path="/today" element={<MyHood />} />
        <Route path="/today/find" element={<MyComplex />} />
        <Route path="/today/old" element={<TodayLayout />}>
          <Route index element={<Navigate to="deals" replace />} />
          <Route path="deals" element={<TodayDeals />} />
          <Route path="listings" element={<TodayListings />} />
          <Route path="stats" element={<TodayStats />} />
        </Route>
        <Route path="/overview" element={<Overview />} />
        <Route path="/ai" element={<AiChat />} />
        <Route path="/map" element={<MapLayout />}>
          <Route index element={<MapView />} />
          <Route path="deal" element={<Navigate to="/map" replace />} />
        </Route>
        <Route path="/deal-map" element={<Navigate to="/map" replace />} />
        <Route path="/cancelled" element={<Navigate to="/tx-stats/cancelled" replace />} />
        <Route path="/complex/:complexNo" element={<ComplexDetail />} />
        <Route path="/changes" element={<ChangesLayout />}>
          <Route index element={<Navigate to="trend" replace />} />
          <Route path="trend" element={<ChangesTrend />} />
          <Route path="region" element={<ChangesRegion />} />
          <Route path="movers" element={<ChangesMovers />} />
        </Route>
        <Route path="/quick-deals" element={<QuickDeals />} />
        <Route path="/realtors" element={<RealtorRanks />}>
          <Route index element={<Navigate to="dong" replace />} />
          <Route path="dong" element={<RealtorByDong />} />
          <Route path="national" element={<RealtorNational />} />
          <Route path="region" element={<RealtorBySido />} />
          <Route path="tenure" element={<RealtorByTenure />} />
          <Route path="staff" element={<RealtorByStaff />} />
        </Route>
        <Route path="/realtor/:realtorId" element={<Realtor />} />
        <Route path="/terms" element={<Terms />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/forum" element={<ForumList />} />
        <Route path="/forum/new" element={<ForumCompose />} />
        <Route path="/forum/:id" element={<ForumPost />} />
        <Route path="/lounge" element={<Lounge />} />
        <Route path="/admin" element={<RequireAdmin><AdminDashboard /></RequireAdmin>} />
        <Route path="/admin/suspicious" element={<RequireAdmin><SuspiciousRealtors /></RequireAdmin>} />
        <Route path="/suspicious" element={<Navigate to="/admin/suspicious" replace />} />
        <Route path="/admin/reviews" element={<RequireAdmin><AdminReviews /></RequireAdmin>} />
        <Route path="/admin/realtor-match" element={<RequireAdmin><AdminRealtorMatch /></RequireAdmin>} />
        <Route path="/admin/users" element={<RequireAdmin><AdminUsers /></RequireAdmin>} />
        <Route path="/admin/resident" element={<RequireAdmin><AdminResident /></RequireAdmin>} />
        <Route path="/admin/realtor-requests" element={<RequireAdmin><AdminRealtorRequests /></RequireAdmin>} />
        <Route path="/admin/logs" element={<RequireAdmin><AdminLogs /></RequireAdmin>} />
        <Route path="/admin/data-sources" element={<RequireAdmin><AdminDataSources /></RequireAdmin>} />
        <Route path="/admin/push" element={<RequireAdmin><AdminPush /></RequireAdmin>} />
        <Route path="/tx-stats" element={<TxStatsLayout />}>
          <Route index element={<Navigate to="region-pulse" replace />} />
          <Route path="region-pulse" element={<TxRegionPulse />} />
          <Route path="top-price" element={<TxTopPrice />} />
          <Route path="record-high" element={<TxRecordHigh />} />
          <Route path="top-volume" element={<TxTopVolume />} />
          <Route path="low-price" element={<TxLowPrice />} />
          <Route path="gap" element={<TxGapRank />} />
          <Route path="price-change" element={<TxPriceChange />} />
          <Route path="pyeong-price" element={<TxPyeongPrice />} />
          <Route path="turnover" element={<TxTurnover />} />
          <Route path="yield" element={<TxYield />} />
          <Route path="cancelled" element={<CancelledTx />} />
          <Route path="presale" element={<PresaleTx />} />
        </Route>
      </Routes>
      </ErrorBoundary>
      <Footer />
      <PerfBadge />
      <AiFab />
    </div>
  );
}

// 콕집 AI 플로팅 버튼 — 모든 페이지 우하단. 누르면 AI로 이동(AI 페이지에선 숨김).
function AiFab() {
  const location = useLocation();
  if (location.pathname === "/ai") return null;
  return (
    <Link to="/ai" className="ai-fab" aria-label="콕집 AI에게 물어보기">
      <Sparkles size={20} strokeWidth={2.4} aria-hidden />
      <span>AI</span>
    </Link>
  );
}

// 관리자 전용 라우트 가드 — 로그인 + is_admin(백엔드 /me) 통과해야 표시
function RequireAdmin({ children }: { children: ReactNode }) {
  const { configured, ready, adminChecked, user, isAdmin } = useAuth();
  const box = (msg: string) => <div className="muted" style={{ padding: 24 }}>{msg}</div>;
  if (!configured) return box("로그인 서버가 설정되지 않았습니다.");
  if (!ready || (user && !adminChecked)) return box("확인 중…");
  if (!user) return box("관리자 로그인이 필요합니다 — 우측 상단에서 카카오 로그인 후 이용하세요.");
  if (!isAdmin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

// 관리자에게만 보이는 관리자 메뉴 바
const ADMIN_NAV: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: "/admin", label: "대시보드", icon: LayoutDashboard, end: true },
  { to: "/admin/users", label: "사용자", icon: Users },
  { to: "/admin/logs", label: "활동 로그", icon: ScrollText },
  { to: "/admin/data-sources", label: "수집 현황", icon: Database },
  { to: "/admin/push", label: "알림 발송", icon: Bell },
  { to: "/admin/realtor-match", label: "중개사 매칭", icon: Wrench },
  { to: "/admin/suspicious", label: "의심 중개사", icon: ShieldAlert },
  { to: "/admin/reviews", label: "리뷰 검수", icon: ClipboardCheck },
  { to: "/admin/resident", label: "입주민 인증", icon: HomeIcon },
  { to: "/admin/realtor-requests", label: "중개사 라운지", icon: Building2 },
];

function AdminBar() {
  const { isAdmin } = useAuth();
  if (!isAdmin) return null;
  return (
    <div className="admin-bar">
      <span className="admin-bar-label"><Wrench size={12} strokeWidth={2.4} /> 관리자</span>
      {ADMIN_NAV.map((it) => (
        <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => isActive ? "active" : ""}>
          <it.icon size={13} strokeWidth={2.2} aria-hidden /> {it.label}
        </NavLink>
      ))}
    </div>
  );
}

function AuthControl() {
  const { user, ready, configured } = useAuth();
  if (!configured) return null;            // Supabase 미설정 시 숨김
  if (!ready) return <span className="auth-area muted">…</span>;
  if (user) return <AccountMenu />;
  return (
    <span className="auth-area">
      <button className="auth-btn kakao" onClick={() => loginKakao()}>
        {/* 카카오 말풍선 심볼 (인라인 SVG) */}
        <svg className="kakao-icon" aria-hidden width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 3C6.48 3 2 6.36 2 10.5c0 2.66 1.8 5 4.51 6.32-.15.52-.97 3.36-1 3.59 0 0-.02.17.09.24.11.07.24.02.24.02.32-.05 3.74-2.45 4.33-2.87.59.08 1.2.13 1.83.13 5.52 0 10-3.36 10-7.5S17.52 3 12 3z" />
        </svg>
        카카오 로그인
      </button>
      <button className="auth-btn google" onClick={() => loginGoogle()}>
        {/* 구글 G 로고 (멀티컬러 SVG) */}
        <svg className="google-icon" aria-hidden width="14" height="14" viewBox="0 0 48 48">
          <path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z"/>
          <path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z"/>
          <path fill="#FBBC05" d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34A21.99 21.99 0 0 0 2 24c0 3.55.85 6.91 2.34 9.88l7.35-5.7z"/>
          <path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z"/>
        </svg>
        구글 로그인
      </button>
    </span>
  );
}

function Footer() {
  const { user, token } = useAuth();
  const withdraw = async () => {
    if (!token) return;
    if (!window.confirm("정말 탈퇴하시겠어요?\n회원정보·포인트·작성한 글/리뷰가 모두 삭제되며 되돌릴 수 없습니다.")) return;
    try {
      const r = await fetch(`${import.meta.env.VITE_API_BASE}/me`, {
        method: "DELETE", headers: { Authorization: `Bearer ${token}` },
      });
      if (!r.ok) { alert("탈퇴 처리에 실패했어요. 잠시 후 다시 시도해주세요."); return; }
      alert("탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.");
      await logout();
    } catch { alert("네트워크 오류로 탈퇴에 실패했어요."); }
  };
  return (
    <footer className="site-footer">
      <div className="footer-brand">
        <strong>콕집</strong> — 부동산 매물·실거래·중개사 분석
      </div>
      <div className="footer-company">
        <span>런투온라인</span>
        <span className="sep">·</span>
        <span>대표 황인찬</span>
        <span className="sep">·</span>
        <span>사업자등록번호 628-11-03169</span>
        <span className="sep">·</span>
        <span>통신판매업신고 2026-진건퇴계원-114</span>
        <span className="sep">·</span>
        <span>문의 runtoonline@gmail.com</span>
      </div>
      <div className="footer-links">
        <Link to="/terms">이용약관</Link>
        <span className="sep">·</span>
        <Link to="/privacy"><strong>개인정보처리방침</strong></Link>
        {token && user && (
          <>
            <span className="sep">·</span>
            <button type="button" className="footer-withdraw" onClick={withdraw}>회원 탈퇴</button>
          </>
        )}
      </div>
      <div className="footer-disclaimer">
        매물 정보는 참고용이며 거래 전 반드시 현장 확인 바랍니다.
      </div>
    </footer>
  );
}
