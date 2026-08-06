import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAuth, loginKakao, loginGoogle, logout } from "../auth";
import CallDetectCard from "../components/CallDetectCard";
import BizCalls, { QuickAddCustomer } from "../components/BizCalls";
import { STORE, isRealtorApp } from "../lib/appmode";
import { enableCallDetect } from "../lib/callDetect";
import { PhoneModal } from "../components/PhoneVerify";
import { Loading } from "../components/Loading";
import { enablePush, pushOptedIn, pushSupported } from "../lib/push";
import { Building2, ClipboardList, ShieldCheck, MessageSquare, Globe, Star, Pencil, Bell, BellRing, ChevronLeft, LayoutDashboard, CheckCircle2, LogOut, Store, Users, Home, CalendarDays, FileText, Settings, Phone, User, Sparkles } from "lucide-react";
import {
  DashboardTab, ListingsTab, AuditTab, LeadsTab, EditTab, OfficeTab, HomepageTab,
  DocSubmit, AdminPick, FavManager, OfficeFavManager, Card, StaffJoin, StaffManageTab,
  type Office, type Status, type Tab, type Fav, type FavOffice,
} from "./Lounge";
import ContractCalendar from "../components/ContractCalendar";
import CustomerLedger from "../components/CustomerLedger";
import MatchBoard from "../components/MatchBoard";
import BizCustomers from "../components/BizCustomers";
import BizContracts from "../components/BizContracts";

const API_BASE = import.meta.env.VITE_API_BASE;

// 콕집 중개사 앱(/biz) — 라운지 기능을 '매물장 중심의 중개사 다이어리'로 재구성한 전용 셸.
// TWA(콕집 중개사 앱)의 start_url. 소비자용 크롬 없이 독립 동작.

type Screen = "diary" | "ledger" | "match" | "calendar" | "customers" | "contracts" | "audit" | "leads" | "homepage" | "favs" | "fav-offices"
            | "office" | "edit" | "dash" | "staff" | "settings" | "calls";

const SCREENS: Record<Screen, { title: string }> = {
  diary: { title: "매물장" }, ledger: { title: "고객원장" }, match: { title: "고객·물건매칭" },
  calendar: { title: "계약캘린더" },
  customers: { title: "고객관리" }, contracts: { title: "계약관리" }, audit: { title: "매물점검" },
  leads: { title: "상담신청" },
  homepage: { title: "내 홈페이지" }, favs: { title: "관심단지" }, "fav-offices": { title: "관심중개사" },
  office: { title: "내 사무소" }, edit: { title: "정보수정요청" }, dash: { title: "대시보드" },
  staff: { title: "직원관리" },
  settings: { title: "설정" },
  calls: { title: "통화 기록" },
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
          {(st.state === "need_phone" || st.state === "select" || st.state === "no_match") && (
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
          {screen === "diary" && <ListingsTab authH={authH} office={office} />}
          {screen === "ledger" && <CustomerLedger authH={authH} onGoListings={() => nav("/biz/diary")} />}
          {screen === "match" && <MatchBoard authH={authH} onGoLedger={() => nav("/biz/ledger")} />}
          {/* 계약캘린더·고객관리·계약관리 = 관리자 가오픈. 타일뿐 아니라 화면도 막는다
              (URL 직접 접근 차단 — 데이터는 백엔드 admin_user가 이미 막지만 화면도 노출 금지) */}
          {screen === "calendar" && (isAdmin ? <ContractCalendar authH={authH} /> : <AdminOnly />)}
          {screen === "customers" && (isAdmin ? <BizCustomers authH={authH} /> : <AdminOnly />)}
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
        </div>
      </div>
    );
  }

  // ── ④ 홈: 버튼 그리드 ──
  return (
    <>
      <BizHome office={office} authH={authH} hasHomepage={!!st.has_homepage} role={st.role ?? "owner"} staffName={st.staff_name ?? null} onLogout={logout} />
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
      calendar: "calendar", customers: "customers",
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
      encodeURIComponent("https://play.google.com/store/apps/details?id=com.koczip.app") + ";end";
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
        계약캘린더·고객관리·계약관리는 현재 관리자 가오픈 단계입니다. 곧 열어드릴게요.
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

function BizHome({ office, authH, hasHomepage, role, staffName, onLogout }: {
  office: Office; authH: () => Record<string, string>; hasHomepage: boolean; role: string;
  staffName: string | null; onLogout: () => void;
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
          <div className="biz-greet-date">{dateStr}{total != null && <> · 우리 매물 <b>{total.toLocaleString()}</b>건</>}</div>
        </div>

        <CallDetectCard token={token} />

        <div className="biz-grid">
          <BizBtn to="/biz/diary" icon={<ClipboardList size={22} />} label="매물장" desc="내 매물 다이어리" primary />
          <BizBtn to="/biz/ledger" icon={<Users size={22} />} label="고객원장" desc="손님 요건·내놓은 물건" primary />
          <BizBtn to="/biz/match" icon={<Sparkles size={22} />} label="고객·물건매칭" desc="손님 조건에 맞는 매물 찾기" primary />
          {isAdmin && <BizBtn to="/biz/calendar" icon={<CalendarDays size={22} />} label="계약캘린더" desc="계약서 → 일정 (가오픈)" />}
          {isAdmin && <BizBtn to="/biz/customers" icon={<Users size={22} />} label="고객관리" desc="임대인·임차인 고객DB (가오픈)" />}
          {isAdmin && <BizBtn to="/biz/contracts" icon={<FileText size={22} />} label="계약관리" desc="계약서·조건·당사자 (가오픈)" />}
          <BizBtn to="/biz/homepage" icon={<Globe size={22} />} label={hasHomepage ? "내 홈페이지" : "홈페이지 만들기"} desc="사무소 홈페이지" />
          <BizBtn to="/biz/audit" icon={<ShieldCheck size={22} />} label="매물점검" desc="표시광고 자가점검" />
          <BizBtn to="/biz/leads" icon={<MessageSquare size={22} />} label="상담신청" desc="고객 상담 리드" badge={leadNew || undefined} />
          <BizBtn to="/biz/favs" icon={<Star size={22} />} label="관심단지" desc="신고가·신규매물 체크" />
          <BizBtn to="/biz/fav-offices" icon={<Store size={22} />} label="관심중개사" desc="주변 사무소 증감" />
          {role === "owner" && <BizBtn to="/biz/staff" icon={<Users size={22} />} label="직원관리" desc="소속공인·보조원 승인" />}
          <BizBtn to="/biz/office" icon={<Building2 size={22} />} label="내 사무소" desc="연결·리뷰 관리" />
          <BizBtn to="/biz/dash" icon={<LayoutDashboard size={22} />} label="대시보드" desc="오늘의 사무소 현황" />
          <BizBtn to="/biz/edit" icon={<Pencil size={22} />} label="정보수정요청" desc="사무소 정보 정정" />
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
      </div>
    </div>
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
