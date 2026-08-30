import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAuth, loginKakao, loginGoogle, logout } from "../auth";
import CallDetectCard from "../components/CallDetectCard";
import BizCalls, { QuickAddCustomer } from "../components/BizCalls";
import { STORE, isRealtorApp, isIOSApp } from "../lib/appmode";
import AppleLoginButton from "../components/AppleLoginButton";
import { enableCallDetect } from "../lib/callDetect";
import { PhoneModal } from "../components/PhoneVerify";
import { Loading } from "../components/Loading";
import { enablePush, pushOptedIn, pushSupported } from "../lib/push";
import { Building2, ClipboardList, ShieldCheck, MessageSquare, Globe, Star, Pencil, Bell, BellRing, ChevronLeft, LayoutDashboard, CheckCircle2, LogOut, Store, Users, Home, CalendarDays, FileText, Settings, Phone, User, Sparkles, LayoutGrid, TrendingUp, Presentation } from "lucide-react";
import {
  DashboardTab, ListingsTab, AuditTab, LeadsTab, EditTab, OfficeTab, HomepageTab,
  DocSubmit, AdminPick, FavManager, OfficeFavManager, Card, StaffJoin, StaffManageTab,
  type Office, type Status, type Tab, type Fav, type FavOffice,
} from "./Lounge";
import ContractCalendar from "../components/ContractCalendar";
import CustomerLedger from "../components/CustomerLedger";
import MatchBoard from "../components/MatchBoard";
import BizContracts from "../components/BizContracts";
import ListingAnalysis from "../components/ListingAnalysis";

const API_BASE = import.meta.env.VITE_API_BASE;

// 콕집 중개사 앱(/biz) — 라운지 기능을 '매물장 중심의 중개사 다이어리'로 재구성한 전용 셸.
// TWA(콕집 중개사 앱)의 start_url. 소비자용 크롬 없이 독립 동작.

type Screen = "diary" | "ledger" | "match" | "calendar" | "contracts" | "audit" | "leads" | "homepage" | "favs" | "fav-offices"
            | "office" | "edit" | "dash" | "staff" | "settings" | "calls" | "more" | "analyze" | "verify" | "brief";

const SCREENS: Record<Screen, { title: string }> = {
  diary: { title: "매물장" }, ledger: { title: "고객원장" }, match: { title: "고객·물건매칭" },
  calendar: { title: "계약캘린더" },
  contracts: { title: "계약관리" }, audit: { title: "매물점검" },
  leads: { title: "상담신청" },
  homepage: { title: "내 홈페이지" }, favs: { title: "관심단지" }, "fav-offices": { title: "관심중개사" },
  office: { title: "내 사무소" }, edit: { title: "정보수정요청" }, dash: { title: "대시보드" },
  staff: { title: "직원관리" },
  settings: { title: "설정" },
  calls: { title: "통화 기록" },
  more: { title: "더보기" },
  analyze: { title: "실거래분석" },
  verify: { title: "계약검증" },
  brief: { title: "매물 브리핑" },
};

export default function BizApp() {
  const { user, token, ready, configured, refreshMe, isAdmin } = useAuth();
  const { screen } = useParams<{ screen: Screen }>();
  const nav = useNavigate();
  const [st, setSt] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [joinRole, setJoinRole] = useState<"owner" | "staff">("owner");
  const [sp, setSp] = useSearchParams();
  const callPhone = sp.get("call");
  const closeCallAdd = () => { const n = new URLSearchParams(sp); n.delete("call"); setSp(n, { replace: true }); };

  const authH = useCallback(() => ({ Authorization: `Bearer ${token}` }), [token]);

  // 중개사 앱 전용 manifest 로 교체(PWA/TWA 설치 정체성 분리)
  useEffect(() => {
    const link = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
    const prev = link?.href;
    if (link) link.href = "/biz.webmanifest";
    document.title = "콕집 중개사 — 매물장·매물점검·상담";
    return () => { if (link && prev) link.href = prev; };
  }, []);

  const loadStatus = useCallback(() => {
    if (!token || !API_BASE) { setLoading(false); return; }
    setLoading(true);
    fetch(`${API_BASE}/lounge/status`, { headers: authH() })
      .then((r) => r.json()).then((d: Status) => setSt(d))
      .catch(() => setSt(null)).finally(() => setLoading(false));
  }, [token, authH]);
  useEffect(() => { loadStatus(); }, [loadStatus]);

  if (!ready) return <div className="biz-shell"><Loading /></div>;

  // ── ① 비로그인: 중개사 전용 랜딩 ──
  if (!user || !configured) return <BizLanding />;

  if (loading || !st) return <div className="biz-shell"><BizTop /><Loading /></div>;

  // ── ② 사무소 연결 전 흐름 ──
  if (st.state !== "linked" || !st.office) {
    return (
      <div className="biz-shell">
        <BizTop />
        <div className="biz-body">
          {(st.state === "need_phone" || st.state === "select" || st.state === "no_match") && (
            <div className="chip-row" style={{ marginBottom: 12 }}>
              <button className={`chip ${joinRole === "owner" ? "active" : ""}`} onClick={() => setJoinRole("owner")}>대표님</button>
              <button className={`chip ${joinRole === "staff" ? "active" : ""}`} onClick={() => setJoinRole("staff")}>소속공인중개사·중개보조원</button>
            </div>
          )}
          {joinRole === "staff" && (st.state === "need_phone" || st.state === "select" || st.state === "no_match") && (
            <StaffJoin authH={authH} phoneVerified={st.phone_verified}
              onNeedPhone={() => setPhoneOpen(true)} onDone={loadStatus} />
          )}
          {st.state === "staff_pending" && st.office && (
            <Card>
              <p><b>{st.office.realtor_name}</b> 대표님의 <b>승인을 기다리는 중</b>입니다.</p>
              <p className="muted" style={{ fontSize: 13 }}>대표님이 직원관리에서 승인하면 바로 시작됩니다. (대표님께 알림이 발송됐어요)</p>
            </Card>
          )}
          {joinRole === "owner" && st.state === "need_phone" && (
            <Card>
              <p><b>중개사무소 확인</b>을 위해 본인 명의 휴대폰 인증이 필요합니다.</p>
              <p className="muted" style={{ fontSize: 13 }}>인증 번호가 콕집에 등록된 사무소 연락처와 일치하면 자동 연결됩니다.</p>
              <button className="ai-send" style={{ padding: "10px 18px" }} onClick={() => setPhoneOpen(true)}>휴대폰 인증하기</button>
            </Card>
          )}
          {joinRole === "owner" && st.state === "select" && (
            <Card>
              <p>일치하는 사무소가 <b>{st.candidates?.length}곳</b> 있습니다. 본인 사무소를 선택해 주세요.</p>
              <div style={{ display: "grid", gap: 8 }}>
                {st.candidates?.map((o) => (
                  <div key={o.realtor_id} className="lounge-cand">
                    <div><b>{o.realtor_name}</b>
                      <div className="muted" style={{ fontSize: 12 }}>{[o.address, o.representative ? `대표 ${o.representative}` : null].filter(Boolean).join(" · ")}</div>
                    </div>
                    <button className="ai-send" style={{ padding: "6px 14px" }} onClick={() => selectOffice(o.realtor_id)}>이 사무소</button>
                  </div>
                ))}
              </div>
            </Card>
          )}
          {joinRole === "owner" && st.state === "no_match" && (
            <Card>
              <p>인증 번호와 일치하는 사무소를 찾지 못했습니다.</p>
              <p className="muted" style={{ fontSize: 13 }}>사업자등록증을 제출하시면 관리자 확인 후 연결해 드립니다.</p>
              <DocSubmit authH={authH} onDone={loadStatus} />
            </Card>
          )}
          {st.state === "doc_pending" && (
            <Card><p>제출 서류를 <b>관리자가 확인 중</b>입니다. 승인되면 바로 열립니다. (보통 1영업일 이내)</p></Card>
          )}
          {st.state === "admin_pick" && (
            <Card><p><b>관리자</b> — 둘러볼 사무소를 검색해 연결하세요.</p><AdminPick authH={authH} onPicked={loadStatus} /></Card>
          )}

          {/* 중개사가 아니면 일반 앱으로 — 인증 흐름 중(승인대기·관리자 제외)에만 노출 */}
          {(st.state === "need_phone" || st.state === "select" || st.state === "no_match") && !isIOSApp() && (
            <div className="biz-notrealtor">
              <span>중개사가 아니신가요?</span>
              <a href={STORE.general} target="_blank" rel="noopener noreferrer">
                콕집 일반 앱에서 실거래·급매·시세 보기 →
              </a>
            </div>
          )}
        </div>
        {phoneOpen && token && (
          <PhoneModal token={token} onClose={() => setPhoneOpen(false)}
            onDone={async () => { await refreshMe(); setPhoneOpen(false); loadStatus(); }} />
        )}
      </div>
    );
  }

  const office = st.office;

  // ── ③ 기능 화면 ──
  if (screen && SCREENS[screen]) {
    return (
      <div className="biz-shell">
        <BizTop backTo="/biz" title={SCREENS[screen].title} />
        <div className="biz-body">
          {tabForScreen(screen) === "listings" && <BizSectionNav screen={screen} />}
          {tabForScreen(screen) === "contracts" && <BizContractNav screen={screen} isAdmin={isAdmin} />}
          {screen === "diary" && <ListingsTab authH={authH} office={office} />}
          {screen === "analyze" && <AnalyzeTab />}
          {screen === "verify" && <VerifyTab />}
          {screen === "brief" && <BriefTab authH={authH} office={office} />}
          {screen === "ledger" && <CustomerLedger authH={authH} onGoListings={() => nav("/biz/diary")} />}
          {screen === "match" && <MatchBoard authH={authH} onGoLedger={() => nav("/biz/ledger")} />}
          {/* 계약캘린더·계약관리 = 관리자 가오픈. 타일뿐 아니라 화면도 막는다
              (URL 직접 접근 차단 — 데이터는 백엔드 admin_user가 이미 막지만 화면도 노출 금지) */}
          {screen === "calendar" && (isAdmin ? <ContractCalendar authH={authH} /> : <AdminOnly />)}
          {screen === "contracts" && (isAdmin ? <BizContracts authH={authH} /> : <AdminOnly />)}
          {screen === "audit" && <AuditTab authH={authH} />}
          {screen === "leads" && <LeadsTab authH={authH} />}
          {screen === "homepage" && <HomepageTab authH={authH} office={office} onStatusChange={loadStatus} />}
          {screen === "favs" && <FavScreen authH={authH} />}
          {screen === "fav-offices" && <FavOfficeScreen authH={authH} />}
          {screen === "office" && <OfficeTab office={office} method={st.method} onUnlink={unlink} />}
          {screen === "staff" && <StaffManageTab authH={authH} office={office} />}
          {screen === "edit" && <EditTab authH={authH} />}
          {screen === "dash" && <DashboardTab authH={authH} office={office} onGoTab={goTab} />}
          {screen === "settings" && <BizSettings office={office} authH={authH} method={st.method} onUnlink={unlink} />}
          {screen === "calls" && <BizCalls />}
          {screen === "more" && <MoreHub authH={authH} hasHomepage={!!st.has_homepage} role={st.role ?? "owner"} isAdmin={isAdmin} onLogout={logout} />}
        </div>
        <BizTabBar active={tabForScreen(screen)} />
      </div>
    );
  }

  // ── ④ 홈: 버튼 그리드 ──
  return (
    <>
      <BizHome office={office} authH={authH} role={st.role ?? "owner"} staffName={st.staff_name ?? null} />
      {callPhone && <QuickAddCustomer phone={callPhone} onClose={closeCallAdd} />}
    </>
  );

  function selectOffice(rid: string) {
    fetch(`${API_BASE}/lounge/select`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ realtor_id: rid }),
    }).then((r) => { if (!r.ok) throw new Error(); loadStatus(); }).catch(() => alert("선택에 실패했습니다."));
  }
  function unlink() {
    if (!confirm("사무소 연결을 해제할까요? 다시 선택할 수 있어요.")) return;
    fetch(`${API_BASE}/lounge/unlink`, { method: "POST", headers: authH() }).then(() => { nav("/biz"); loadStatus(); });
  }
  function goTab(t: Tab) {
    const map: Record<Tab, string> = {
      dashboard: "dash", listings: "diary", ledger: "ledger", match: "match",
      calendar: "calendar",
      contracts: "contracts", audit: "audit", office: "office", requests: "requests",
      edit: "edit", leads: "leads", homepage: "homepage", staff: "staff",
    };
    nav(`/biz/${map[t]}`);
  }
}


// 콕집 일반 앱 열기 — 안드로이드(TWA)에선 intent://로 설치 시 앱 실행,
// 미설치 시 플레이스토어(browser_fallback_url). iOS·데스크톱은 웹으로.
function openConsumerApp() {
  if (/Android/i.test(navigator.userAgent)) {
    // 런처 인텐트로 앱 자체를 실행(https 인텐트는 같은 도메인이라 커스텀탭으로 새는 문제).
    // 미설치면 fallback으로 플레이스토어.
    window.location.href =
      "intent://koczip.com/#Intent;scheme=https;package=com.koczip.app;" +
      "S.browser_fallback_url=" +
      encodeURIComponent("https://play.google.com/store/apps/details?id=com.koczip.app&hl=ko") + ";end";
  } else {
    window.open("https://koczip.com/", "_blank", "noopener");
  }
}

// ── 상단바 ──
function BizTop({ backTo, title, settings }: { backTo?: string; title?: string; settings?: boolean }) {
  return (
    <header className="biz-top">
      {backTo
        ? <Link to={backTo} className="biz-back" aria-label="뒤로"><ChevronLeft size={20} /></Link>
        : <span style={{ width: 4 }} />}
      <Link to="/biz" className="biz-brand">
        <img src="/logo.svg" alt="" width="22" height="22" />
        <b>콕집</b><span className="biz-brand-tag">중개사</span>
      </Link>
      {title ? <span className="biz-top-title">{title}</span> : <span style={{ flex: 1 }} />}
      {settings && <Link to="/biz/settings" className="biz-gear" aria-label="설정"><Settings size={19} /></Link>}
    </header>
  );
}

// ── 비로그인 랜딩: 중개사 전용 강조 ──
function BizLanding() {
  return (
    <div className="biz-shell biz-landing">
      <div className="biz-hero">
        <img src="/logo.svg" alt="" width="52" height="52" />
        <h1>콕집 <span className="biz-hero-tag">중개사</span></h1>
        <p className="biz-hero-sub"><b>중개사무소 전용</b> 서비스입니다</p>
        <p className="biz-hero-desc">
          내 매물을 다이어리처럼 — 매물장·표시광고 점검·상담 관리·사무소 홈페이지까지,
          중개 업무에 필요한 것만 담았습니다.
        </p>
      </div>
      <ul className="biz-feats">
        <li><ClipboardList size={17} /><div><b>매물장</b><span>내 매물 검색·메모·담당자 배정 — 매물 다이어리</span></div></li>
        <li><ShieldCheck size={17} /><div><b>매물점검</b><span>표시·광고 위반(과태료) 사전 자가점검</span></div></li>
        <li><BellRing size={17} /><div><b>매일 10시·16시 브리핑</b><span>내 매물·관심단지·관심중개사 변동 알림</span></div></li>
        <li><Globe size={17} /><div><b>사무소 홈페이지</b><span>1분 만에 만드는 우리 사무소 홈페이지 + 상담접수</span></div></li>
      </ul>
      <div className="biz-login-btns">
        <button className="biz-login kakao" onClick={() => loginKakao()}>카카오로 시작</button>
        <button className="biz-login google" onClick={() => loginGoogle()}>구글로 시작</button>
        <AppleLoginButton className="biz-login" label="Apple로 시작" />
      </div>
      <p className="muted" style={{ fontSize: 12, textAlign: "center" }}>
        로그인 후 휴대폰 인증으로 사무소가 자동 연결됩니다 · 일반 사용자는 <a href="https://koczip.com/">콕집 홈</a>으로
      </p>
    </div>
  );
}

// ── 홈 그리드 ──
// 관리자 가오픈 기능에 비관리자가 URL로 접근했을 때
function AdminOnly() {
  return (
    <div className="bzc-card" style={{ textAlign: "center", padding: "28px 16px" }}>
      <div style={{ fontSize: 14, fontWeight: 800, color: "#13294b", marginBottom: 6 }}>준비 중인 기능입니다</div>
      <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
        계약캘린더·계약관리는 현재 관리자 가오픈 단계입니다. 곧 열어드릴게요.
      </p>
      <Link to="/biz" className="chip" style={{ marginTop: 12, display: "inline-flex" }}>홈으로</Link>
    </div>
  );
}

function BizSettings({ office, authH, method, onUnlink }: {
  office: Office; authH: () => Record<string, string>; method?: string; onUnlink: () => void;
}) {
  void authH;
  const { user, token } = useAuth();
  const email = user?.email; const phone = user?.phone;
  const [pushOn, setPushOn] = useState(pushOptedIn());
  const [callBusy, setCallBusy] = useState(false);

  async function togglePush() {
    if (!pushSupported()) { alert("이 기기는 알림을 지원하지 않아요."); return; }
    const r = await enablePush(token);
    if (r.ok) { setPushOn(true); alert("알림이 켜졌습니다. 매일 10시·16시 매물 브리핑을 보내드려요."); }
    else alert("알림 설정에 실패했어요. 브라우저 알림 권한을 확인해 주세요.");
  }
  async function enableCall() {
    setCallBusy(true);
    const r = await enableCallDetect(token);
    if (!r.ok) alert(`전화 알림을 켤 수 없어요 — ${r.error}`);
    setCallBusy(false);
  }

  return (
    <div className="biz-settings">
      <section className="bs-sec">
        <h3><User size={15} /> 로그인 정보</h3>
        <div className="bs-row"><span>이름</span><b>{user?.name ?? "-"}</b></div>
        <div className="bs-row"><span>이메일</span><b>{email ?? "-"}</b></div>
        {phone && <div className="bs-row"><span>휴대폰</span><b>{phone}</b></div>}
        <button className="auth-btn ghost bs-btn" onClick={logout}><LogOut size={14} /> 로그아웃</button>
      </section>

      <section className="bs-sec">
        <h3><Bell size={15} /> 알림</h3>
        <div className="bs-toggle">
          <div className="bs-toggle-txt"><b>매물 브리핑·상담 알림</b><span>매일 10시·16시 요약, 상담 들어오면 즉시</span></div>
          <button className={"bs-sw" + (pushOn ? " on" : "")} onClick={togglePush} disabled={pushOn}>{pushOn ? "켜짐" : "켜기"}</button>
        </div>
      </section>

      {isRealtorApp() && (
        <section className="bs-sec">
          <h3><Phone size={15} /> 전화 고객알림</h3>
          <div className="bs-toggle">
            <div className="bs-toggle-txt"><b>전화 오면 고객정보 띄우기</b><span>고객 전화가 오면 누구인지·문의내용을 화면에 표시</span></div>
            <button className="bs-sw" onClick={enableCall} disabled={callBusy}>{callBusy ? "…" : "설정"}</button>
          </div>
          <p className="bs-note">한 번 설정하면 계속 유지돼요. 다시 켜거나 재설정하려면 '설정'을 누르세요.</p>
          <Link to="/biz/calls" className="bs-link">통화 기록 보기 →</Link>
        </section>
      )}

      <section className="bs-sec">
        <h3><Building2 size={15} /> 내 사무소</h3>
        <div className="bs-row"><span>사무소</span><b>{office.realtor_name}</b></div>
        <div className="bs-row"><span>인증방식</span><b>{method === "doc" ? "서류 승인" : "전화 인증"}</b></div>
        <button className="auth-btn ghost bs-btn" onClick={onUnlink}>사무소 변경/해제</button>
      </section>
    </div>
  );
}

// ── 하단 5탭 네비 ──
type BizTab = "home" | "listings" | "customers" | "contracts" | "more";
function tabForScreen(screen?: string): BizTab {
  if (!screen) return "home";
  if (screen === "diary" || screen === "audit" || screen === "analyze" || screen === "brief") return "listings";
  if (screen === "ledger" || screen === "match" || screen === "leads") return "customers";
  if (screen === "contracts" || screen === "calendar" || screen === "verify") return "contracts";
  return "more";
}
function BizTabBar({ active }: { active: BizTab }) {
  const items: { key: BizTab; to: string; icon: React.ReactNode; label: string }[] = [
    { key: "home", to: "/biz", icon: <Home size={20} />, label: "홈" },
    { key: "listings", to: "/biz/diary", icon: <Building2 size={20} />, label: "매물" },
    { key: "customers", to: "/biz/ledger", icon: <Users size={20} />, label: "고객" },
    { key: "contracts", to: "/biz/verify", icon: <FileText size={20} />, label: "계약" },
    { key: "more", to: "/biz/more", icon: <LayoutGrid size={20} />, label: "더보기" },
  ];
  return (
    <nav className="biz-tabbar" aria-label="중개사 앱 탭">
      {items.map((it) => (
        <Link key={it.key} to={it.to} className={`biz-tab${active === it.key ? " on" : ""}`} aria-current={active === it.key ? "page" : undefined}>
          <span className="biz-tab-ic">{it.icon}</span>
          <span className="biz-tab-lbl">{it.label}</span>
        </Link>
      ))}
    </nav>
  );
}

// ── 홈(요약) ──
function BizHome({ office, authH, role, staffName }: {
  office: Office; authH: () => Record<string, string>; role: string; staffName: string | null;
}) {
  const [leadNew, setLeadNew] = useState(0);
  const [total, setTotal] = useState<number | null>(null);
  const [pushOn, setPushOn] = useState(pushOptedIn());
  const { token, isAdmin } = useAuth();
  useEffect(() => {
    fetch(`${API_BASE}/lounge/dashboard`, { headers: authH() })
      .then((r) => r.json())
      .then((d) => { setLeadNew(d?.leads?.new_count || 0); setTotal(d?.stats?.total_listings ?? null); })
      .catch(() => {});
  }, [authH]);

  const now = new Date();
  const dateStr = `${now.getMonth() + 1}월 ${now.getDate()}일 ${"일월화수목금토"[now.getDay()]}요일`;

  async function togglePush() {
    const r = await enablePush(token);
    if (r.ok) { setPushOn(true); alert("알림이 켜졌습니다. 매일 10시·16시 매물 브리핑을 보내드려요."); }
    else alert("알림 설정에 실패했어요. 브라우저 알림 권한을 확인해 주세요.");
  }

  return (
    <div className="biz-shell">
      <BizTop settings />
      <div className="biz-body">
        <div className="biz-greet">
          <div className="biz-greet-name"><b>{role === "owner" ? `${office.representative || "대표"} 대표님` : `${staffName || "직원"}님`}</b>, 안녕하세요</div>
          <div className="biz-greet-office">{office.realtor_name}</div>
          <div className="biz-greet-date">{dateStr}</div>
        </div>

        {/* 오늘 요약 */}
        <div className="biz-today">
          <div className="biz-today-h">오늘 · 이번주</div>
          <Link to="/biz/leads" className="biz-today-row">
            <span>새 상담신청</span>
            <b className={leadNew ? "hot" : ""}>{leadNew ? `${leadNew}건` : "없음"}</b>
          </Link>
          <div className="biz-today-row">
            <span>우리 매물</span>
            <b>{total != null ? `${total.toLocaleString()}건` : "—"}</b>
          </div>
          {pushSupported() && (
            <button className="biz-today-row asbtn" onClick={togglePush} disabled={pushOn}>
              <span>매일 10·16시 브리핑 알림</span>
              <b className={pushOn ? "" : "hot"}>{pushOn ? "켜짐" : "켜기"}</b>
            </button>
          )}
        </div>

        <CallDetectCard token={token} />

        {/* 빠른 실행 */}
        <div className="biz-quick-h">빠른 실행</div>
        <div className="biz-quick">
          <BizQuick to="/biz/diary" icon={<ClipboardList size={20} />} label="매물장" />
          <BizQuick to="/biz/ledger" icon={<Users size={20} />} label="고객원장" />
          {isAdmin
            ? <BizQuick to="/biz/contracts" icon={<FileText size={20} />} label="AI 계약" />
            : <BizQuick to="/biz/match" icon={<Sparkles size={20} />} label="물건매칭" />}
          <BizQuick to="/biz/audit" icon={<ShieldCheck size={20} />} label="매물점검" />
        </div>

        <Link to="/biz/more" className="biz-more-link"><LayoutGrid size={16} /> 전체 메뉴 보기</Link>
      </div>
      <BizTabBar active="home" />
    </div>
  );
}

function BizQuick({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <Link to={to} className="biz-quick-tile">
      <span className="biz-quick-ic">{icon}</span>
      <b>{label}</b>
    </Link>
  );
}

// ── 매물 섹션 서브탭 ──
function BizSectionNav({ screen }: { screen?: string }) {
  const items = [
    { key: "diary", to: "/biz/diary", label: "매물장" },
    { key: "analyze", to: "/biz/analyze", label: "실거래분석" },
    { key: "brief", to: "/biz/brief", label: "브리핑" },
    { key: "audit", to: "/biz/audit", label: "매물점검" },
  ];
  return (
    <div className="biz-subnav">
      {items.map((it) => (
        <Link key={it.key} to={it.to} className={`biz-subnav-chip${screen === it.key ? " on" : ""}`}>{it.label}</Link>
      ))}
    </div>
  );
}

// ── 실거래분석: 단지 검색 → 시세·급매·호가 분석(콕집 데이터) ──
type CxHit = { complex_no: string; complex_name: string; region: string; households: number; type_name?: string };
function AnalyzeTab() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<CxHit[]>([]);
  const [open, setOpen] = useState(false);
  const [cx, setCx] = useState<CxHit | null>(null);
  useEffect(() => {
    if (!API_BASE || q.trim().length < 2 || (cx && q === cx.complex_name)) { setHits([]); return; }
    const t = setTimeout(() => {
      fetch(`${API_BASE}/complexes/search?q=${encodeURIComponent(q.trim())}&limit=8`)
        .then((r) => r.json()).then((j) => { setHits(j.items ?? []); setOpen(true); }).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q, cx]);
  const pick = (h: CxHit) => { setCx(h); setQ(h.complex_name); setHits([]); setOpen(false); };
  const region = (h: CxHit) => [h.region, h.households ? `${h.households.toLocaleString()}세대` : null].filter(Boolean).join(" · ");
  return (
    <div>
      <div className="biz-analyze-search">
        <input value={q} onChange={(e) => { setQ(e.target.value); setCx(null); }}
          placeholder="단지명 검색 (예: 마포래미안푸르지오)" />
        {open && hits.length > 0 && (
          <div className="biz-analyze-hits">
            {hits.map((h) => (
              <button key={h.complex_no} onClick={() => pick(h)}>
                <b>{h.complex_name}</b><span>{region(h)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {!cx && (
        <div className="biz-analyze-empty">
          단지를 검색하면 <b>실거래·시세·급매·호가</b> 분석을 보여드려요.<br />
          계약 전 시세 검증, 손님 브리핑에 그대로 쓰세요.
        </div>
      )}
      {cx && (
        <div className="biz-analyze-result">
          <div className="biz-analyze-head"><b>{cx.complex_name}</b><span>{region(cx)}</span></div>
          <ListingAnalysis complexNo={cx.complex_no} compact />
          <button className="biz-analyze-more"
            onClick={() => window.open(`https://koczip.com/complex/${cx.complex_no}`, "_blank", "noopener")}>
            전체 실거래·시세 자세히 보기 →
          </button>
        </div>
      )}
    </div>
  );
}

// ── 계약 섹션 서브탭 ──
function BizContractNav({ screen, isAdmin }: { screen?: string; isAdmin: boolean }) {
  const items = [
    { key: "verify", to: "/biz/verify", label: "계약검증", show: true },
    { key: "contracts", to: "/biz/contracts", label: "계약관리", show: isAdmin },
    { key: "calendar", to: "/biz/calendar", label: "계약캘린더", show: isAdmin },
  ].filter((x) => x.show);
  return (
    <div className="biz-subnav">
      {items.map((it) => (
        <Link key={it.key} to={it.to} className={`biz-subnav-chip${screen === it.key ? " on" : ""}`}>{it.label}</Link>
      ))}
    </div>
  );
}

// ── 계약검증: 계약금액이 실거래 시세 대비 적정한지 + 전세가율/깡통전세(콕집 데이터) ──
type VTx = { deal_ymd: string; amount: number; excl_use_ar: number; floor?: number | null };
const _man = (v: number) => {   // v: 만원 → "5억 3,000만"
  if (!v) return "-";
  const e = Math.floor(v / 10000), m = Math.round(v % 10000);
  return e ? (m ? `${e}억 ${m.toLocaleString()}만` : `${e}억`) : `${m.toLocaleString()}만`;
};
const _median = (arr: VTx[]): number | null => {
  const a = arr.map((s) => s.amount).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : Math.round((a[m - 1] + a[m]) / 2);
};
function VerifyTab() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<CxHit[]>([]);
  const [open, setOpen] = useState(false);
  const [cx, setCx] = useState<CxHit | null>(null);
  const [sale, setSale] = useState<VTx[] | null>(null);
  const [jeonse, setJeonse] = useState<VTx[] | null>(null);
  const [trade, setTrade] = useState<"sale" | "jeonse">("sale");
  const [areaKey, setAreaKey] = useState<number | null>(null);
  const [amtEok, setAmtEok] = useState("");

  useEffect(() => {
    if (!API_BASE || q.trim().length < 2 || (cx && q === cx.complex_name)) { setHits([]); return; }
    const t = setTimeout(() => {
      fetch(`${API_BASE}/complexes/search?q=${encodeURIComponent(q.trim())}&limit=8`)
        .then((r) => r.json()).then((j) => { setHits(j.items ?? []); setOpen(true); }).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q, cx]);

  useEffect(() => {
    setSale(null); setJeonse(null); setAreaKey(null);
    if (!cx || !API_BASE) return;
    const norm = (arr: any[], key: string): VTx[] => (arr ?? []).map((s: any) => ({
      deal_ymd: String(s.deal_ymd || ""),
      amount: Number(String(s[key]).replace(/[^0-9.]/g, "")) || 0,
      excl_use_ar: Number(s.excl_use_ar) || 0, floor: s.floor,
    })).filter((s: VTx) => s.excl_use_ar > 0 && s.amount > 0);
    fetch(`${API_BASE}/complex/${cx.complex_no}/transactions?months=12&limit=1500`)
      .then((r) => r.json())
      .then((j) => { setSale(norm(j.sale, "deal_amount")); setJeonse(norm(j.jeonse, "deposit")); })
      .catch(() => { setSale([]); setJeonse([]); });
  }, [cx]);

  const pick = (h: CxHit) => { setCx(h); setQ(h.complex_name); setHits([]); setOpen(false); };
  const rows = trade === "sale" ? sale : jeonse;
  const loaded = sale !== null && jeonse !== null;
  const areaGroups = useMemo(() => {
    const m = new Map<number, number>();
    [...(sale ?? []), ...(jeonse ?? [])].forEach((s) => { const k = Math.round(s.excl_use_ar); m.set(k, (m.get(k) || 0) + 1); });
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [sale, jeonse]);
  const matchIn = (arr: VTx[] | null) => (arr && areaKey != null)
    ? arr.filter((s) => Math.abs(s.excl_use_ar - areaKey) <= 1.5).sort((a, b) => b.deal_ymd.localeCompare(a.deal_ymd))
    : [];
  const matched = useMemo(() => matchIn(rows), [rows, areaKey]);
  const median = useMemo(() => _median(matched), [matched]);
  const saleMedian = useMemo(() => _median(matchIn(sale)), [sale, areaKey]);
  const jRatio = (trade === "jeonse" && median && saleMedian) ? (median / saleMedian * 100) : null;
  const jRisk = jRatio == null ? null : jRatio >= 80 ? { t: "깡통전세 위험", c: "hi" } : jRatio >= 70 ? { t: "다소 높음, 주의", c: "hi" } : { t: "양호한 전세가율", c: "ok" };

  const amt = amtEok ? Math.round(parseFloat(amtEok) * 10000) : null;
  const pct = (amt != null && median) ? ((amt - median) / median * 100) : null;
  const verdict = pct == null ? null
    : Math.abs(pct) <= 3 ? { t: "시세 적정", c: "ok" }
    : pct > 0 ? { t: "시세보다 높음", c: "hi" } : { t: "시세보다 낮음", c: "lo" };
  const fmtDate = (d: string) => (d.length >= 10 ? d.slice(2, 10).replace(/-/g, ".") : d);
  const tLabel = trade === "sale" ? "매매가" : "전세 보증금";

  return (
    <div>
      <p className="biz-verify-lead">계약 금액이 <b>실거래 시세 대비 적정한지</b>, 전세는 <b>전세가율(깡통전세)</b>까지 콕집 데이터로 확인하세요.</p>
      <div className="biz-analyze-search">
        <input value={q} onChange={(e) => { setQ(e.target.value); setCx(null); }}
          placeholder="단지명 검색 (예: 마포래미안푸르지오)" />
        {open && hits.length > 0 && (
          <div className="biz-analyze-hits">
            {hits.map((h) => (
              <button key={h.complex_no} onClick={() => pick(h)}>
                <b>{h.complex_name}</b>
                <span>{[h.region, h.households ? `${h.households.toLocaleString()}세대` : null].filter(Boolean).join(" · ")}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {!cx && <div className="biz-analyze-empty">단지를 검색하면 <b>평형별 실거래(매매·전세)</b>를 불러와<br />계약 금액과 비교해 드려요.</div>}
      {cx && !loaded && <p className="cled-empty">실거래 불러오는 중…</p>}
      {cx && loaded && areaGroups.length === 0 && <p className="cled-empty">최근 12개월 실거래가 없어요.</p>}

      {cx && loaded && areaGroups.length > 0 && (
        <>
          <div className="cled-seg" style={{ marginBottom: 12 }}>
            <button className={trade === "sale" ? "on" : ""} onClick={() => setTrade("sale")}>매매</button>
            <button className={trade === "jeonse" ? "on" : ""} onClick={() => setTrade("jeonse")}>전세</button>
          </div>

          <div className="biz-verify-label">평형(전용면적) 선택</div>
          <div className="biz-subnav" style={{ marginBottom: 12 }}>
            {areaGroups.map(([k, c]) => (
              <button key={k} className={`biz-subnav-chip${areaKey === k ? " on" : ""}`} onClick={() => setAreaKey(k)}>
                {k}㎡ ({Math.round(k / 3.3058)}평) <i style={{ opacity: .6 }}>{c}</i>
              </button>
            ))}
          </div>

          {areaKey != null && (
            <>
              <div className="biz-verify-input">
                <label>{tLabel}</label>
                <div className="biz-verify-amt">
                  <input type="number" inputMode="decimal" value={amtEok}
                    onChange={(e) => setAmtEok(e.target.value)} placeholder={trade === "sale" ? "예: 12.5" : "예: 6.5"} />
                  <span>억</span>
                </div>
              </div>

              {median != null ? (
                <div className="biz-verify-market">
                  최근 {trade === "sale" ? "매매" : "전세"} 중앙값 <b>{_man(median)}</b>
                  <span> · 매칭 {matched.length}건 (±1.5㎡)</span>
                </div>
              ) : (
                <div className="biz-verify-market">이 평형 {trade === "sale" ? "매매" : "전세"} 실거래가 없어요.</div>
              )}

              {verdict && median != null && (
                <div className={`biz-verify-verdict v-${verdict.c}`}>
                  <div className="vv-t">{verdict.t}</div>
                  <div className="vv-p">{pct! > 0 ? "+" : ""}{pct!.toFixed(1)}%
                    <span> (계약 {_man(amt!)} vs 시세 {_man(median)})</span></div>
                </div>
              )}

              {trade === "jeonse" && jRisk && jRatio != null && (
                <div className={`biz-verify-verdict v-${jRisk.c}`}>
                  <div className="vv-t">전세가율 {jRatio.toFixed(0)}% · {jRisk.t}</div>
                  <div className="vv-p">전세 시세 {_man(median!)} / 매매 시세 {_man(saleMedian!)}
                    {jRatio >= 80 && <span> — 보증금 회수 위험, 보증보험·선순위 확인 권장</span>}</div>
                </div>
              )}
              {trade === "jeonse" && median != null && saleMedian == null && (
                <div className="biz-verify-market">이 평형 매매 실거래가 없어 전세가율은 계산 못 했어요.</div>
              )}

              <div className="biz-verify-label">최근 {trade === "sale" ? "매매" : "전세"} 실거래 (이 평형)</div>
              <div className="biz-verify-list">
                {matched.slice(0, 12).map((s, i) => (
                  <div key={i} className="biz-verify-row">
                    <span>{fmtDate(s.deal_ymd)}</span>
                    <span>{s.floor ? `${s.floor}층` : ""}</span>
                    <b>{_man(s.amount)}</b>
                  </div>
                ))}
                {matched.length === 0 && <div className="cled-empty">이 평형 매칭 실거래가 없어요.</div>}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

// ── 매물 브리핑: 손님에게 보여줄 매물을 골라 깔끔한 화면으로 ──
type BriefItem = {
  article_no: string; complex_name: string | null; building_name?: string; dong?: string; ho?: string;
  trade_type: string; price_text?: string; rent_price_text?: string;
  area_name?: string; area2_m2?: number; floor_info?: string; direction?: string;
  room_cnt?: number | null; maintenance_fee?: number | null; move_in?: string; feature_desc?: string;
};
const TRADE_KOR2: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세", B3: "단기임대" };
function BriefTab({ authH, office }: { authH: () => Record<string, string>; office: Office }) {
  const [items, setItems] = useState<BriefItem[] | null>(null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [present, setPresent] = useState(false);
  useEffect(() => {
    fetch(`${API_BASE}/lounge/listings?sort=confirm`, { headers: authH() })
      .then((r) => r.json()).then((j) => setItems((j.items ?? []) as BriefItem[])).catch(() => setItems([]));
  }, [authH]);
  const toggle = (a: string) => setSel((prev) => { const n = new Set(prev); n.has(a) ? n.delete(a) : n.add(a); return n; });
  const chosen = (items ?? []).filter((it) => sel.has(it.article_no));
  const priceLine = (it: BriefItem) => {
    const t = TRADE_KOR2[it.trade_type] || it.trade_type;
    return (it.trade_type === "B2" || it.trade_type === "B3")
      ? `${t} ${it.price_text || ""}${it.rent_price_text ? " / " + it.rent_price_text : ""}`
      : `${t} ${it.price_text || ""}`;
  };
  const areaLine = (it: BriefItem) =>
    [it.area_name, it.area2_m2 ? `전용 ${Math.round(it.area2_m2 / 3.3058)}평(${it.area2_m2}㎡)` : null].filter(Boolean).join(" · ");
  const place = (it: BriefItem) =>
    [it.complex_name || it.building_name, it.dong ? `${it.dong}동` : null, it.ho ? `${it.ho}호` : null].filter(Boolean).join(" ") || "매물";

  if (present) {
    return (
      <div className="biz-brief-present">
        <div className="biz-brief-bar">
          <b>{office.realtor_name}</b>
          <button onClick={() => setPresent(false)}>편집</button>
        </div>
        {chosen.map((it) => (
          <div key={it.article_no} className="biz-brief-card">
            <div className="bb-place">{place(it)}</div>
            <div className="bb-price">{priceLine(it)}</div>
            <div className="bb-meta">
              {[areaLine(it), it.floor_info, it.direction ? `${it.direction}향` : null,
                it.room_cnt != null ? `방 ${it.room_cnt}` : null,
                it.maintenance_fee ? `관리비 ${Math.round(it.maintenance_fee / 1e4)}만` : null,
                it.move_in ? `입주 ${it.move_in}` : null].filter(Boolean).map((x, i) => <span key={i}>{x}</span>)}
            </div>
            {it.feature_desc && <div className="bb-feat">{it.feature_desc}</div>}
          </div>
        ))}
      </div>
    );
  }
  return (
    <div>
      <p className="biz-verify-lead">손님에게 보여줄 매물을 고르면 <b>깔끔한 브리핑 화면</b>으로 보여드려요. <span style={{ color: "#8b95a1" }}>(내부 메모·연락처는 안 보입니다)</span></p>
      {items === null && <p className="cled-empty">불러오는 중…</p>}
      {items !== null && items.length === 0 && <p className="cled-empty">매물장에 매물이 없어요.</p>}
      <div className="biz-brief-list">
        {(items ?? []).map((it) => (
          <label key={it.article_no} className={"biz-brief-pick" + (sel.has(it.article_no) ? " on" : "")}>
            <input type="checkbox" checked={sel.has(it.article_no)} onChange={() => toggle(it.article_no)} />
            <span className="bp-main"><b>{place(it)}</b><span>{priceLine(it)} · {areaLine(it)}</span></span>
          </label>
        ))}
      </div>
      {sel.size > 0 && (
        <button className="biz-brief-start" onClick={() => setPresent(true)}>
          <Presentation size={16} /> 브리핑 시작 ({sel.size})
        </button>
      )}
    </div>
  );
}

// ── 더보기: 전체 메뉴(기존 그리드) ──
function MoreHub({ authH, hasHomepage, role, isAdmin, onLogout }: {
  authH: () => Record<string, string>; hasHomepage: boolean; role: string; isAdmin: boolean; onLogout: () => void;
}) {
  const [leadNew, setLeadNew] = useState(0);
  const [pushOn, setPushOn] = useState(pushOptedIn());
  const { token } = useAuth();
  useEffect(() => {
    fetch(`${API_BASE}/lounge/dashboard`, { headers: authH() })
      .then((r) => r.json()).then((d) => setLeadNew(d?.leads?.new_count || 0)).catch(() => {});
  }, [authH]);
  async function togglePush() {
    const r = await enablePush(token);
    if (r.ok) { setPushOn(true); alert("알림이 켜졌습니다. 매일 10시·16시 매물 브리핑을 보내드려요."); }
    else alert("알림 설정에 실패했어요. 브라우저 알림 권한을 확인해 주세요.");
  }
  return (
    <>
      <div className="biz-grid">
        <BizBtn to="/biz/diary" icon={<ClipboardList size={22} />} label="매물장" desc="내 매물 다이어리" primary />
        <BizBtn to="/biz/ledger" icon={<Users size={22} />} label="고객원장" desc="손님 요건·내놓은 물건" primary />
        <BizBtn to="/biz/match" icon={<Sparkles size={22} />} label="고객·물건매칭" desc="손님 조건에 맞는 매물 찾기" primary />
        <BizBtn to="/biz/verify" icon={<FileText size={22} />} label="계약검증" desc="계약금액 시세 적정성" />
        {isAdmin && <BizBtn to="/biz/calendar" icon={<CalendarDays size={22} />} label="계약캘린더" desc="계약서 → 일정 (가오픈)" />}
        {isAdmin && <BizBtn to="/biz/contracts" icon={<FileText size={22} />} label="계약관리" desc="계약서·조건·당사자 (가오픈)" />}
        <BizBtn to="/biz/homepage" icon={<Globe size={22} />} label={hasHomepage ? "내 홈페이지" : "홈페이지 만들기"} desc="사무소 홈페이지" />
        <BizBtn to="/biz/analyze" icon={<TrendingUp size={22} />} label="실거래분석" desc="단지 시세·급매 분석" />
        <BizBtn to="/biz/brief" icon={<Presentation size={22} />} label="매물 브리핑" desc="손님에게 보여주기" />
        <BizBtn to="/biz/audit" icon={<ShieldCheck size={22} />} label="매물점검" desc="표시광고 자가점검" />
        <BizBtn to="/biz/leads" icon={<MessageSquare size={22} />} label="상담신청" desc="고객 상담 리드" badge={leadNew || undefined} />
        <BizBtn to="/biz/favs" icon={<Star size={22} />} label="관심단지" desc="신고가·신규매물 체크" />
        <BizBtn to="/biz/fav-offices" icon={<Store size={22} />} label="관심중개사" desc="주변 사무소 증감" />
        {role === "owner" && <BizBtn to="/biz/staff" icon={<Users size={22} />} label="직원관리" desc="소속공인·보조원 승인" />}
        <BizBtn to="/biz/office" icon={<Building2 size={22} />} label="내 사무소" desc="연결·리뷰 관리" />
        <BizBtn to="/biz/dash" icon={<LayoutDashboard size={22} />} label="대시보드" desc="오늘의 사무소 현황" />
        <BizBtn to="/biz/edit" icon={<Pencil size={22} />} label="정보수정요청" desc="사무소 정보 정정" />
        <BizBtn to="/biz/settings" icon={<Settings size={22} />} label="설정" desc="알림·계정" />
        <button className="biz-btn" onClick={openConsumerApp}>
          <span className="biz-btn-ic"><Home size={22} /></span>
          <b>콕집 (일반)</b>
          <span className="biz-btn-desc">일반 사용자 앱 열기</span>
        </button>
      </div>
      {pushSupported() && (
        <button className={`biz-push ${pushOn ? "on" : ""}`} onClick={togglePush} disabled={pushOn}>
          {pushOn ? <><CheckCircle2 size={16} /> 매일 10시·16시 매물 브리핑 알림 켜짐</>
                  : <><Bell size={16} /> 매일 10시·16시 매물 브리핑 알림 받기</>}
        </button>
      )}
      <div className="biz-foot" style={{ justifyContent: "flex-end" }}>
        <button onClick={onLogout}><LogOut size={12} /> 로그아웃</button>
      </div>
    </>
  );
}

function BizBtn({ to, icon, label, desc, badge, primary }: {
  to: string; icon: React.ReactNode; label: string; desc: string; badge?: number; primary?: boolean;
}) {
  return (
    <Link to={to} className={`biz-btn${primary ? " primary" : ""}`}>
      <span className="biz-btn-ic">{icon}{badge ? <em className="biz-btn-badge">{badge}</em> : null}</span>
      <b>{label}</b>
      <span className="biz-btn-desc">{desc}</span>
    </Link>
  );
}

// ── 관심단지/관심중개사 단독 화면 ──
function FavScreen({ authH }: { authH: () => Record<string, string> }) {
  const [favs, setFavs] = useState<Fav[] | null>(null);
  const load = useCallback(() => {
    fetch(`${API_BASE}/lounge/favorites`, { headers: authH() })
      .then((r) => r.json()).then((x) => setFavs(x.items ?? [])).catch(() => setFavs([]));
  }, [authH]);
  useEffect(() => { load(); }, [load]);
  return (
    <>
      <p className="muted" style={{ fontSize: 12.5, margin: "2px 2px 10px" }}>
        등록한 단지의 신고가·신규매물·증감을 매일 10시·16시 브리핑으로 알려드립니다.
      </p>
      <FavManager authH={authH} favs={favs} onChange={load} />
    </>
  );
}
function FavOfficeScreen({ authH }: { authH: () => Record<string, string> }) {
  const [items, setItems] = useState<FavOffice[] | null>(null);
  const load = useCallback(() => {
    fetch(`${API_BASE}/lounge/fav-offices`, { headers: authH() })
      .then((r) => r.json()).then((x) => setItems(x.items ?? [])).catch(() => setItems([]));
  }, [authH]);
  useEffect(() => { load(); }, [load]);
  return (
    <>
      <p className="muted" style={{ fontSize: 12.5, margin: "2px 2px 10px" }}>
        주변·경쟁 사무소의 매물 증감을 매일 10시·16시 브리핑으로 알려드립니다.
      </p>
      <OfficeFavManager authH={authH} offices={items} onChange={load} />
    </>
  );
}
