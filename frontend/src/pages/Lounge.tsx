import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import OfferForm from "../components/OfferForm";
import type { Offer as KOffer } from "../components/OfferForm";
import { PhoneModal } from "../components/PhoneVerify";
import SupportLink from "../components/SupportLink";
import { Loading } from "../components/Loading";
import ImportListings from "../components/ImportListings";
import { Building2, MessageSquare, Pencil, Globe, Phone, Share2, Link2, ClipboardList, Search, ExternalLink,
  MapPin, Map as MapIcon, LayoutDashboard, Star, TrendingUp, Award, Plus, Minus, X, ChevronRight, Flame, RefreshCw,
  ShieldCheck, Users, CalendarDays, FileText, Camera, Lock, Trash2, Sparkles, ChevronDown, Loader2,
  Folder, FolderOpen, Check, Upload, FileSpreadsheet } from "lucide-react";
import ListingAudit from "../components/ListingAudit";
import OfficeMap from "../components/OfficeMap";
import ContractCalendar from "../components/ContractCalendar";
import LoungeCalendarPanel from "../components/LoungeCalendarPanel";
import QuickAdd from "../components/QuickAdd";
import CustomerLedger from "../components/CustomerLedger";
import MatchBoard from "../components/MatchBoard";
import BizContracts from "../components/BizContracts";

const TT: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };
type ChgItem = { article_no: string; complex_no: string; complex_name?: string | null;
  trade_type: string; area_name: string | null; floor: string | null; price: string; building: string | null; direction: string | null };
import { copyText, shareUrlNative } from "../lib/share";
import { areaLabel } from "../lib/area";

function won(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8), m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
function ymd(s: string | null | undefined): string {
  if (!s) return "";
  const m = String(s).replace(/-/g, "").match(/^(\d{4})(\d{2})(\d{2})/);
  return m ? `${m[2]}.${m[3]}` : String(s).slice(5, 10);
}

const API_BASE = import.meta.env.VITE_API_BASE;

export type Office = {
  realtor_id: string; realtor_name: string | null; address?: string | null;
  representative?: string | null; tel?: string | null; cell?: string | null;
};
export type Status = {
  state: "need_phone" | "select" | "no_match" | "doc_pending" | "linked" | "admin_pick" | "staff_pending";
  phone_verified: boolean;
  office?: Office; method?: string; candidates?: Office[]; is_admin?: boolean; has_homepage?: boolean;
  role?: string;        // owner | assoc(소속공인중개사) | assist(중개보조원)
  staff_name?: string | null;
};
type EditReq = { id: number; content: string; status: string; admin_note: string | null; created_at: string; resolved_at: string | null };
type Lead = { id: number; name: string | null; phone: string | null; message: string | null; source: string | null; status: string; created_at: string };

export type Tab = "dashboard" | "listings" | "ledger" | "match" | "calendar" | "contracts" | "audit" | "office" | "edit" | "leads" | "homepage" | "staff" | "requests";
// 렌더되는 탭은 전부 여기 있어야 한다 — ?tab= 딥링크와 새로고침 복원이 이 목록으로 걸러진다
export const LOUNGE_TABS: Tab[] = ["dashboard", "listings", "ledger", "match", "calendar", "contracts",
  "requests", "audit", "office", "edit", "leads", "homepage", "staff"];
type Dash = {
  office: Office;
  stats: { total_listings: number; complex_listings?: number; national_rank: number | null; national_total: number;
    breakdown?: Record<string, number>;
    region: { sido_name: string; count: number; rank: number; total: number } | null };
  reviews: { total: number; avg: number | null; new_count: number;
    recent: { type: string; rating: number | null; body: string; created_at: string }[] };
  leads: { new_count: number; total: number; recent: Lead[] };
  homepage: { has: boolean; slug: string | null; published: boolean };
  favorites_count: number;
};
type TradeCnt = { A1: number; B1: number; B2: number; sum: number };
export type Fav = { complex_no: string; complex_name: string;
  record_high: { area_key: string; price: number; date: string } | null;
  total: TradeCnt; new_week: TradeCnt; today_change: number };
export type FavOffice = { realtor_id: string; realtor_name: string | null; address: string | null;
  representative: string | null; total: TradeCnt; today_change: number; national_rank: number | null };

export default function Lounge() {
  const { user, token, ready, configured, refreshMe, isAdmin } = useAuth();
  const [st, setSt] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [phoneOpen, setPhoneOpen] = useState(false);
  // 탭을 URL(?tab=)과 동기화 — 상단 '중개사라운지' 드롭다운 하위메뉴가 특정 탭으로 바로 진입.
  const [sp, setSp] = useSearchParams();
  const _initTab = ((): Tab => {
    const t = sp.get("tab") as Tab | null;
    return t && LOUNGE_TABS.includes(t) ? t : "dashboard";
  })();
  const [tab, setTabState] = useState<Tab>(_initTab);
  // 레일 접힘 — 좁은 화면·집중 작업 때 쓰고, 고른 상태는 기억한다
  const [railFold, setRailFold] = useState(() => {
    try { return localStorage.getItem("lounge_rail_fold") === "1"; } catch { return false; }
  });
  const setTab = useCallback((t: Tab) => {
    setTabState(t);
    setSp((prev) => {
      const n = new URLSearchParams(prev);
      if (t === "dashboard") n.delete("tab"); else n.set("tab", t);
      return n;
    }, { replace: true });
  }, [setSp]);
  // 라운지에 머문 채 드롭다운으로 다른 탭 URL을 열면(리마운트 없음) 탭 반영
  useEffect(() => {
    const t = sp.get("tab") as Tab | null;
    if (t && LOUNGE_TABS.includes(t) && t !== tab) setTabState(t);
  }, [sp]); // eslint-disable-line
  const [joinRole, setJoinRole] = useState<"owner" | "staff">("owner");  // 미연결 시 역할 선택

  const authH = useCallback(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const loadStatus = useCallback(() => {
    if (!token || !API_BASE) { setLoading(false); return; }
    setLoading(true);
    fetch(`${API_BASE}/lounge/status`, { headers: authH() })
      .then((r) => r.json()).then((d: Status) => setSt(d))
      .catch(() => setSt(null)).finally(() => setLoading(false));
  }, [token, authH]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  if (!configured) return <Box>로그인 서버가 설정되지 않았습니다.</Box>;
  if (!ready) return <Loading />;
  if (!user) return <Box>중개사 라운지는 로그인 후 이용할 수 있어요. 우측 상단에서 카카오/구글 로그인을 해주세요.</Box>;
  if (!API_BASE) return <Box>이 기능은 운영 환경에서만 동작합니다.</Box>;
  if (loading || !st) return <Loading />;

  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        <Building2 size={16} strokeWidth={2.2} aria-hidden /> 중개사 라운지
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>중개사무소 인증 회원 전용</span>
      </div>

      {/* 미연결: 역할 선택 — 대표는 전화매칭(vworld=대표 본인 번호만), 직원은 검색+승인制 */}
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
          <p className="muted" style={{ fontSize: 13 }}>
            {st.staff_name && <>신청자: <b>{st.staff_name}</b> · </>}
            대표님이 라운지 직원관리에서 승인하면 바로 이용할 수 있어요. (대표님께 푸시 알림이 발송됐습니다)
          </p>
          <button className="chip" style={{ width: "fit-content" }} onClick={unlink}>신청 취소 / 다른 사무소 다시 선택</button>
        <SupportLink variant="banner" sub="승인 문의는" label="고객센터" context="lounge-staff-pending" /></Card>
      )}

      {joinRole === "owner" && st.state === "need_phone" && (
        <Card>
          <p>중개사 라운지에 입장하려면 <b>본인 명의 휴대폰 인증</b>이 필요합니다.</p>
          <p className="muted" style={{ fontSize: 13 }}>
            인증하신 번호가 콕집에 등록된 중개사무소 연락처와 일치하면 자동으로 본인 사무소가 연결됩니다.
          </p>
          <button className="ai-send" style={{ padding: "8px 18px" }} onClick={() => setPhoneOpen(true)}>
            휴대폰 인증하기
          </button>
        </Card>
      )}

      {joinRole === "owner" && st.state === "select" && (
        <Card>
          <p>인증된 번호와 일치하는 중개사무소가 <b>{st.candidates?.length}곳</b> 있습니다. 본인 사무소를 선택해 주세요.</p>
          <p className="muted" style={{ fontSize: 13 }}>선택은 기억되어 다음 입장부터 바로 이어집니다. 나중에 변경할 수 있어요.</p>
          <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
            {st.candidates?.map((o) => (
              <div key={o.realtor_id} className="lounge-cand">
                <div>
                  <b>{o.realtor_name}</b>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {[o.address, o.representative ? `대표 ${o.representative}` : null].filter(Boolean).join(" · ")}
                  </div>
                </div>
                <button className="ai-send" style={{ padding: "6px 14px" }}
                  onClick={() => selectOffice(o.realtor_id)}>이 사무소</button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {joinRole === "owner" && st.state === "no_match" && (
        <Card>
          <p>인증된 번호와 일치하는 중개사무소를 찾지 못했습니다.</p>
          <p className="muted" style={{ fontSize: 13 }}>
            사무소 대표 연락처가 콕집 데이터와 다르거나 미등록일 수 있어요. 아래로 <b>사업자등록증</b>을 제출하시면
            관리자 확인 후 연결해 드립니다.
          </p>
          <DocSubmit authH={authH} onDone={loadStatus} />
          <SupportLink variant="banner" sub="사무소 연결이 계속 안 되시나요?" label="고객센터" context="lounge-no-match" />
        </Card>
      )}

      {st.state === "admin_pick" && (
        <Card>
          <p><b>관리자</b> — 인증 없이 입장했습니다. 둘러볼 중개사무소를 검색해 연결하세요.</p>
          <AdminPick authH={authH} onPicked={loadStatus} />
        </Card>
      )}

      {st.state === "doc_pending" && (
        <Card><p>제출하신 서류를 <b>관리자가 확인 중</b>입니다. 승인되면 라운지가 열립니다. (보통 1영업일 이내)</p>
          <SupportLink variant="banner" sub="승인이 지연되거나 문의가 있으시면" label="고객센터" context="lounge-doc-pending" />
        </Card>
      )}

      {st.state === "linked" && st.office && (
        <div className={"lrail-wrap" + (railFold ? " fold" : "")}>
          <LoungeRail authH={authH} tab={tab} setTab={setTab} isAdmin={isAdmin}
            hasHomepage={!!st.has_homepage} isOwner={(st.role ?? "owner") === "owner"}
            fold={railFold} onFold={() => { setRailFold(!railFold); try { localStorage.setItem("lounge_rail_fold", railFold ? "0" : "1"); } catch { /* 사파리 프라이빗 */ } }} />
          <div className="lrail-pane">
          {tab === "dashboard" && <DashboardTab authH={authH} office={st.office} onGoTab={setTab} />}
          {tab === "listings" && <ListingsTab authH={authH} office={st.office} />}
          {tab === "ledger" && <CustomerLedger authH={authH} onGoListings={() => setTab("listings")} />}
          {tab === "match" && <MatchBoard authH={authH} onGoLedger={() => setTab("ledger")} />}
          {tab === "calendar" && isAdmin && <ContractCalendar authH={authH} />}
          {tab === "contracts" && isAdmin && <BizContracts authH={authH} />}
          {tab === "requests" && <RequestsTab authH={authH} />}
          {tab === "audit" && <AuditTab authH={authH} />}
          {tab === "office" && <OfficeTab office={st.office} method={st.method} onUnlink={unlink} />}
          {tab === "edit" && <EditTab authH={authH} />}
          {tab === "leads" && <LeadsTab authH={authH} />}
          {tab === "staff" && <StaffManageTab authH={authH} office={st.office} />}
          {tab === "homepage" && <HomepageTab authH={authH} office={st.office} onStatusChange={loadStatus} />}
          </div>
        </div>
      )}

      {phoneOpen && token && (
        <PhoneModal token={token} onClose={() => setPhoneOpen(false)}
          onDone={async () => { await refreshMe(); setPhoneOpen(false); loadStatus(); }} />
      )}
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
    fetch(`${API_BASE}/lounge/unlink`, { method: "POST", headers: authH() })
      .then(() => { setTab("office"); loadStatus(); });
  }
}

function Box({ children }: { children: React.ReactNode }) {
  return <div className="muted" style={{ padding: 24 }}>{children}</div>;
}
export function Card({ children }: { children: React.ReactNode }) {
  return <div style={{ border: "1px solid var(--c-border)", borderRadius: 12, padding: 18, maxWidth: 640, display: "grid", gap: 8 }}>{children}</div>;
}

/** 라운지 메뉴 — 알약 14개가 두 줄로 흐르던 것을 세로 레일로 세운다.
 *  세로라야 ① 묶음 이름을 붙일 수 있고 ② 숫자 배지 자리가 생긴다. 지금은 들어가 봐야
 *  새 상담이 있는지 안다. 좁게 쓰고 싶으면 접어서 아이콘만 남긴다. */
function LoungeRail({ authH, tab, setTab, isAdmin, hasHomepage, isOwner, fold, onFold }: {
  authH: () => Record<string, string>; tab: Tab; setTab: (t: Tab) => void;
  isAdmin: boolean; hasHomepage: boolean; isOwner: boolean; fold: boolean; onFold: () => void;
}) {
  const [n, setN] = useState<Record<string, number>>({});
  useEffect(() => {
    let dead = false;
    fetch(`${API_BASE}/lounge/nav-counts`, { headers: authH() })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (j && !dead) setN(j); })
      .catch(() => { /* 숫자는 곁들이는 정보다 — 못 받아도 메뉴는 열린다 */ });
    return () => { dead = true; };
  }, [tab]);            // 탭을 옮길 때마다 다시 센다(상담을 읽으면 배지가 줄어야 한다)

  type Row = readonly [Tab, string, typeof Users, keyof typeof n | null];
  const groups: readonly (readonly [string, readonly Row[]])[] = [
    ["", [["dashboard", "대시보드", LayoutDashboard, null]]],
    ["영업", [
      ["listings", "매물장", ClipboardList, "listings"],
      ["ledger", "고객원장", Users, "ledger"],
      ["match", "고객·물건매칭", Sparkles, null],
      ["leads", "상담신청", MessageSquare, "leads"],
    ]],
    ["관리", [
      ...((isAdmin ? [["calendar", "계약캘린더", CalendarDays, null],
                      ["contracts", "계약관리", FileText, null]] : []) as Row[]),
      ["audit", "매물점검", ShieldCheck, null],
      ["homepage", hasHomepage ? "홈페이지관리" : "홈페이지생성", Globe, null],
      ["requests", "콕집요청", Sparkles, null],
    ]],
    ["사무소", [
      ...((isOwner ? [["staff", "직원관리", Users, null]] : []) as Row[]),
      ["office", "내 사무소", Building2, null],
      ["edit", "정보수정요청", Pencil, null],
    ]],
  ];

  return (
    <nav className="lrail" aria-label="라운지 메뉴">
      <button className="lrail-fold" onClick={onFold} title={fold ? "메뉴 펼치기" : "메뉴 접기"}
        aria-label={fold ? "메뉴 펼치기" : "메뉴 접기"}>
        {fold ? <ChevronRight size={14} /> : <><ChevronRight size={14} className="rot" />메뉴 접기</>}
      </button>
      {groups.map(([g, rows]) => rows.length === 0 ? null : (
        <div key={g || "home"} className="lrail-g">
          {g && <p className="lrail-lab">{g}</p>}
          {rows.map(([k, label, Icon, cnt]) => (
            <button key={k} className={"lrail-i" + (tab === k ? " on" : "")}
              onClick={() => setTab(k)}
              title={fold ? label + (cnt && n[cnt] ? ` ${n[cnt]}` : "") : undefined}>
              <Icon size={15} strokeWidth={2.1} aria-hidden />
              <span>{label}</span>
              {cnt && n[cnt]
                ? <i className={"lrail-n" + (cnt === "leads" ? " hot" : "")}>{n[cnt]}</i>
                : null}
            </button>
          ))}
        </div>
      ))}
    </nav>
  );
}

export function DashboardTab({ authH, office, onGoTab }: {
  authH: () => Record<string, string>; office: Office; onGoTab: (t: Tab) => void;
}) {
  const [d, setD] = useState<Dash | null>(null);
  const [favs, setFavs] = useState<Fav[] | null>(null);
  const [offices, setOffices] = useState<FavOffice[] | null>(null);
  const loadFavs = useCallback(() => {
    fetch(`${API_BASE}/lounge/favorites`, { headers: authH() })
      .then((r) => r.json()).then((x) => setFavs(x.items ?? [])).catch(() => setFavs([]));
  }, [authH]);
  const loadOffices = useCallback(() => {
    fetch(`${API_BASE}/lounge/fav-offices`, { headers: authH() })
      .then((r) => r.json()).then((x) => setOffices(x.items ?? [])).catch(() => setOffices([]));
  }, [authH]);
  useEffect(() => {
    fetch(`${API_BASE}/lounge/dashboard`, { headers: authH() })
      .then((r) => r.json()).then(setD).catch(() => setD(null));
    loadFavs();
    loadOffices();
  }, [authH, loadFavs, loadOffices]);

  if (!d) return <Loading />;
  const s = d.stats;
  const greetName = office.representative || office.realtor_name || "대표";
  const now = new Date();
  const dateStr = `${now.getMonth() + 1}월 ${now.getDate()}일 ${"일월화수목금토"[now.getDay()]}요일`;

  return (
    <div className="dash">
      {/* 위쪽 2단 — 왼쪽에 인사말과 현황, 오른쪽에 일정. 사무소 하루는
          '우리 상태'와 '오늘 할 일' 두 축이라 나란히 두는 편이 읽기 쉽다. */}
      <div className="dash-top">
        <div className="dash-top-l">
          <div className="dash-hero">
            <div className="dash-greet"><b>{greetName}</b> 대표님, 안녕하세요</div>
            <div className="dash-office">{office.realtor_name}</div>
            <div className="dash-date">{dateStr} · 오늘의 우리 사무소 현황입니다</div>
          </div>

          <QuickAdd authH={authH} onSaved={() => onGoTab("ledger")} />

          <div className="dash-stats">
            <StatCard icon={<Building2 size={18} />} accent="blue" label="우리 매물수"
              value={(s.total_listings || 0).toLocaleString()} unit="건"
              sub={`단지형 ${(s.complex_listings || 0).toLocaleString()} · 비단지 ${((s.total_listings || 0) - (s.complex_listings || 0)).toLocaleString()}`} />
            <StatCard icon={<Award size={18} />} accent="gold" label="전국 순위"
              value={s.national_rank ? s.national_rank.toLocaleString() : "-"} unit={s.national_rank ? "위" : ""}
              sub={`전국 ${s.national_total.toLocaleString()}개 중`} />
            <StatCard icon={<TrendingUp size={18} />} accent="green" label={s.region ? `${s.region.sido_name} 순위` : "지역 순위"}
              value={s.region ? s.region.rank.toLocaleString() : "-"} unit={s.region ? "위" : ""}
              sub={s.region ? `${s.region.count.toLocaleString()}건 · ${s.region.total.toLocaleString()}개 중` : "집계 전"} />
            <StatCard icon={<Star size={18} />} accent="pink" label="신규 리뷰" onClick={() => onGoTab("office")}
              value={`${d.reviews.new_count}`} unit="건"
              sub={d.reviews.avg ? `평점 ${d.reviews.avg} · 총 ${d.reviews.total}개` : `총 ${d.reviews.total}개 · 최근 30일`} />
          </div>

          {s.breakdown && s.total_listings > 0 && (
            <div className="rl-breakdown">
              <span className="rl-bd-title">매물 유형</span>
              {(([["단지형", "complex"], ["빌라", "villa"], ["단독", "house"], ["상가", "sangga"], ["사무실", "office"], ["빌딩", "building"], ["토지", "land"], ["공장", "factory"], ["지식산업센터", "knowledge"], ["재개발", "redev"], ["원룸", "oneroom"]] as const)
                .filter(([, k]) => (s.breakdown![k] || 0) > 0)
                .map(([label, k]) => (
                  <span key={k} className={`rl-bd-chip${k === "complex" ? " primary" : ""}`}>{label} <b>{s.breakdown![k].toLocaleString()}</b></span>
                )))}
            </div>
          )}
          {/* 상담신청 — 캘린더가 길어 현황 아래가 비었다. 그 자리를 채운다.
              상담은 '오늘 처리할 일'이라 일정 옆에 붙어 있는 편이 맞기도 하다. */}
          <div className="dash-sec-h">
            <h3><MessageSquare size={16} strokeWidth={2.3} /> 상담신청 {d.leads.new_count > 0 && <span className="dash-badge">{d.leads.new_count} 신규</span>}</h3>
            <button className="hood-more" onClick={() => onGoTab("leads")}>전체보기 <ChevronRight size={13} /></button>
          </div>
          {d.leads.recent.length === 0
            ? <div className="dash-empty">아직 들어온 상담신청이 없어요. 홈페이지를 만들면 상담이 여기로 쌓입니다.</div>
            : <div className="dash-leads">
                {d.leads.recent.map((l) => (
                  <div key={l.id} className="dash-lead">
                    <span className="ctx-badge" style={leadBadge(l.status)}>{leadKr(l.status)}</span>
                    <span className="dash-lead-name">{l.name ?? "익명"}</span>
                    <span className="dash-lead-msg">{l.message ?? "-"}</span>
                    {l.phone && <a className="dash-lead-tel" href={`tel:${l.phone.replace(/[^0-9+]/g, "")}`}>{l.phone}</a>}
                    <span className="muted dash-lead-date">{l.created_at?.slice(5, 10)}</span>
                  </div>
                ))}
              </div>}
        </div>

        <aside className="dash-top-r">
          <LoungeCalendarPanel authH={authH} onOpenFull={() => onGoTab("calendar")} />
        </aside>
      </div>

      <div className="dash-sec-h">
        <h3><Star size={16} strokeWidth={2.3} /> 관심단지 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>신고가·신규매물을 매일 체크</span></h3>
      </div>
      <FavManager authH={authH} favs={favs} onChange={loadFavs} />

      <div className="dash-sec-h">
        <h3><Building2 size={16} strokeWidth={2.3} /> 관심중개사무소 <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>주변 사무소 매물 증감을 매일 체크</span></h3>
      </div>
      <OfficeFavManager authH={authH} offices={offices} onChange={loadOffices} />

      <div className="dash-links">
        <button className="dash-link" onClick={() => onGoTab("homepage")}><Globe size={15} /> {d.homepage.has ? "내 홈페이지 관리" : "홈페이지 만들기"}</button>
        <Link className="dash-link" to={`/realtor/${encodeURIComponent(office.realtor_id)}`}><Building2 size={15} /> 내 사무소 상세</Link>
      </div>
    </div>
  );
}

function StatCard({ icon, accent, label, value, unit, sub, onClick }: {
  icon: React.ReactNode; accent: string; label: string; value: string; unit?: string; sub: string; onClick?: () => void;
}) {
  return (
    <div className={`stat-card a-${accent}${onClick ? " clickable" : ""}`} onClick={onClick}>
      <div className="stat-ic">{icon}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}{unit && <em>{unit}</em>}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}

function tradeStr(t: TradeCnt): string {
  return `매매 ${t.A1} · 전세 ${t.B1} · 월세 ${t.B2}`;
}

export function FavManager({ authH, favs, onChange }: {
  authH: () => Record<string, string>; favs: Fav[] | null; onChange: () => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ complex_no: string; complex_name: string; region: string | null; households: number | null }[]>([]);
  const [searched, setSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [detail, setDetail] = useState<{ url: string; title: string } | null>(null);
  const search = () => {
    if (q.trim().length < 2) return;
    setSearching(true);
    fetch(`${API_BASE}/lounge/complex-search?q=${encodeURIComponent(q)}`, { headers: authH() })
      .then((r) => r.json()).then((d) => setResults(d.items ?? []))
      .catch(() => setResults([])).finally(() => { setSearched(true); setSearching(false); });
  };
  const add = (cno: string) => {
    fetch(`${API_BASE}/lounge/favorites`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ complex_no: cno }),
    }).then((r) => { if (!r.ok) return r.json().then((e) => { throw new Error(e.detail); }); })
      .then(() => { setQ(""); setResults([]); setSearched(false); onChange(); }).catch((e) => alert(e.message || "추가 실패"));
  };
  const remove = (cno: string) =>
    fetch(`${API_BASE}/lounge/favorites/${cno}`, { method: "DELETE", headers: authH() }).then(() => onChange());

  return (
    <div>
      <div className="fav-add">
        <input className="ai-input" style={{ flex: 1 }} placeholder="관심단지 이름 검색 (예: 크로바, 헬리오시티)" value={q}
          onChange={(e) => { setQ(e.target.value); setSearched(false); }}
          onKeyDown={(e) => { if (e.key === "Enter") search(); }} />
        <button className="ai-send" style={{ padding: "0 16px" }} disabled={searching} onClick={search}>검색</button>
      </div>
      {results.length > 0 && (
        <div className="fav-results">
          {results.map((r) => (
            <button key={r.complex_no} className="fav-result" onClick={() => add(r.complex_no)}>
              <Plus size={13} className="fav-result-add" />
              <span className="fav-result-main"><b>{r.complex_name}</b>
                <span className="muted">{[r.region, r.households ? `${r.households.toLocaleString()}세대` : null].filter(Boolean).join(" · ")}</span>
              </span>
            </button>
          ))}
        </div>
      )}
      {searched && results.length === 0 && (
        <div className="fav-noresult">‘{q}’ 검색 결과가 없어요. 단지명 일부만(예: ‘크로바’) 다시 검색해 보세요.</div>
      )}
      {favs == null ? <Loading />
        : favs.length === 0 ? <div className="dash-empty">관심단지를 추가하면 그 단지의 <b>신고가·오늘 변화·신규매물</b>을 매일 한눈에 볼 수 있어요.</div>
        : (
          <div className="fav-grid">
            {favs.map((f) => (
              <div key={f.complex_no} className="fav-card">
                <button className="fav-x" onClick={() => remove(f.complex_no)} title="삭제"><X size={13} /></button>
                <Link to={`/complex/${f.complex_no}`} className="fav-name">{f.complex_name}</Link>
                <div className="fav-rows">
                  <div className="fav-row"><span className="fav-k"><Flame size={11} strokeWidth={2.4} /> 최근 신고가</span>
                    <span className="fav-v">{f.record_high ? `${won(f.record_high.price)} (${ymd(f.record_high.date)})` : "—"}</span></div>
                  <div className="fav-row"><span className="fav-k">오늘 매물 변화량</span>
                    <span className={`fav-v ${f.today_change > 0 ? "up" : f.today_change < 0 ? "down" : ""}`}>
                      {f.today_change > 0 ? `▲ +${f.today_change}건` : f.today_change < 0 ? `▼ ${f.today_change}건` : "변동 없음"}</span></div>
                </div>
                <div className="fav-tsec">
                  <div className="fav-tt"><span>이번주 신규 매물</span><b className={f.new_week.sum > 0 ? "hot" : ""}>{f.new_week.sum > 0 ? `+${f.new_week.sum}` : "0"}건</b></div>
                  <div className="fav-tb">{tradeStr(f.new_week)}</div>
                </div>
                <div className="fav-tsec">
                  <div className="fav-tt"><span>전체 매물</span><b>{f.total.sum.toLocaleString()}건</b></div>
                  <div className="fav-tb">{tradeStr(f.total)}</div>
                </div>
                <button className="fav-detail" onClick={() => setDetail({ url: `${API_BASE}/lounge/complex-changes?complex_no=${f.complex_no}`, title: f.complex_name })}>
                  매물 변화 세부내용 보기 →
                </button>
              </div>
            ))}
          </div>
        )}
      {detail && <ChangesModal url={detail.url} title={detail.title} showComplex={false} authH={authH} onClose={() => setDetail(null)} />}
    </div>
  );
}

export function OfficeFavManager({ authH, offices, onChange }: {
  authH: () => Record<string, string>; offices: FavOffice[] | null; onChange: () => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ realtor_id: string; realtor_name: string | null; location: string | null; representative: string | null; count: number }[]>([]);
  const [searched, setSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [detail, setDetail] = useState<{ url: string; title: string } | null>(null);
  const search = () => {
    if (q.trim().length < 2) return;
    setSearching(true);
    fetch(`${API_BASE}/stats/realtors/search?q=${encodeURIComponent(q)}&limit=100`)
      .then((r) => r.json()).then((d) => setResults(d.items ?? []))
      .catch(() => setResults([])).finally(() => { setSearched(true); setSearching(false); });
  };
  const add = (rid: string) => {
    fetch(`${API_BASE}/lounge/fav-offices`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ realtor_id: rid }),
    }).then((r) => { if (!r.ok) return r.json().then((e) => { throw new Error(e.detail); }); })
      .then(() => { setQ(""); setResults([]); setSearched(false); onChange(); }).catch((e) => alert(e.message || "추가 실패"));
  };
  const remove = (rid: string) =>
    fetch(`${API_BASE}/lounge/fav-offices/${rid}`, { method: "DELETE", headers: authH() }).then(() => onChange());

  return (
    <div>
      <div className="fav-add">
        <input className="ai-input" style={{ flex: 1 }} placeholder="중개사무소 이름 검색 (예: OO공인중개사)" value={q}
          onChange={(e) => { setQ(e.target.value); setSearched(false); }}
          onKeyDown={(e) => { if (e.key === "Enter") search(); }} />
        <button className="ai-send" style={{ padding: "0 16px" }} disabled={searching} onClick={search}>검색</button>
      </div>
      {results.length > 0 && (
        <div className="fav-results">
          {results.map((r) => (
            <button key={r.realtor_id} className="fav-result" onClick={() => add(r.realtor_id)}>
              <Plus size={13} className="fav-result-add" />
              <span className="fav-result-main"><b>{r.realtor_name}</b>
                <span className="muted">{[r.location, r.representative ? `대표 ${r.representative}` : null, `매물 ${r.count.toLocaleString()}`].filter(Boolean).join(" · ")}</span>
              </span>
            </button>
          ))}
        </div>
      )}
      {searched && results.length === 0 && (
        <div className="fav-noresult">‘{q}’ 검색 결과가 없어요. 사무소명 일부만 다시 검색해 보세요.</div>
      )}
      {offices == null ? <Loading />
        : offices.length === 0 ? <div className="dash-empty">관심중개사무소를 추가하면 그 사무소의 <b>매물 증감</b>을 매일 한눈에 볼 수 있어요.</div>
        : (
          <div className="fav-grid">
            {offices.map((o) => (
              <div key={o.realtor_id} className="fav-card">
                <button className="fav-x" onClick={() => remove(o.realtor_id)} title="삭제"><X size={13} /></button>
                <Link to={`/realtor/${encodeURIComponent(o.realtor_id)}`} className="fav-name">{o.realtor_name}</Link>
                {o.address && <div className="fav-addr">{o.address}</div>}
                <div className="fav-rows">
                  <div className="fav-row"><span className="fav-k">오늘 매물 변화량</span>
                    <span className={`fav-v ${o.today_change > 0 ? "up" : o.today_change < 0 ? "down" : ""}`}>
                      {o.today_change > 0 ? `▲ +${o.today_change}건` : o.today_change < 0 ? `▼ ${o.today_change}건` : "변동 없음"}</span></div>
                  {o.national_rank && <div className="fav-row"><span className="fav-k">전국 순위</span>
                    <span className="fav-v">{o.national_rank.toLocaleString()}위</span></div>}
                </div>
                <div className="fav-tsec">
                  <div className="fav-tt"><span>전체 매물</span><b>{o.total.sum.toLocaleString()}건</b></div>
                  <div className="fav-tb">{tradeStr(o.total)}</div>
                </div>
                <button className="fav-detail" onClick={() => setDetail({ url: `${API_BASE}/lounge/office-changes?realtor_id=${encodeURIComponent(o.realtor_id)}`, title: o.realtor_name ?? "중개사무소" })}>
                  매물 변화 세부내용 보기 →
                </button>
              </div>
            ))}
          </div>
        )}
      {detail && <ChangesModal url={detail.url} title={detail.title} showComplex authH={authH} onClose={() => setDetail(null)} />}
    </div>
  );
}

function tradeBreak(arr: ChgItem[]) {
  const b = { A1: 0, B1: 0, B2: 0 } as Record<string, number>;
  arr.forEach((x) => { if (b[x.trade_type] != null) b[x.trade_type]++; });
  return b;
}

function ChangesModal({ url, title, showComplex, authH, onClose }: {
  url: string; title: string; showComplex: boolean; authH: () => Record<string, string>; onClose: () => void;
}) {
  const [d, setD] = useState<{ added: ChgItem[]; removed: ChgItem[]; bumped?: ChgItem[]; dates?: { prev: string; current: string } | null; note?: string } | null>(null);
  const [tt, setTt] = useState<string>("all");
  const [dong, setDong] = useState<string>("all");
  const [area, setArea] = useState<string>("all");
  useEffect(() => {
    fetch(url, { headers: authH() }).then((r) => r.json()).then(setD).catch(() => setD({ added: [], removed: [], bumped: [] }));
  }, [url, authH]);

  const all = useMemo(() => [...(d?.added ?? []), ...(d?.removed ?? []), ...(d?.bumped ?? [])], [d]);
  const dongs = useMemo(() => Array.from(new Set(all.map((x) => x.building).filter(Boolean) as string[]))
    .sort((a, b) => (parseInt(a) || 0) - (parseInt(b) || 0) || a.localeCompare(b)), [all]);
  const areas = useMemo(() => Array.from(new Set(all.map((x) => x.area_name).filter(Boolean) as string[]))
    .sort((a, b) => (parseFloat(a) || 0) - (parseFloat(b) || 0) || a.localeCompare(b)), [all]);

  const match = (x: ChgItem) =>
    (tt === "all" || x.trade_type === tt) &&
    (dong === "all" || x.building === dong) &&
    (area === "all" || x.area_name === area);
  const added = (d?.added ?? []).filter(match);
  const removed = (d?.removed ?? []).filter(match);
  const bumped = (d?.bumped ?? []).filter(match);
  const filtering = tt !== "all" || dong !== "all" || area !== "all";

  return (
    <div className="cm-ov" onClick={onClose}>
      <div className="cm" onClick={(e) => e.stopPropagation()}>
        <div className="cm-head">
          <div>
            <div className="cm-title">{title}</div>
            {d?.dates && <div className="cm-sub">{d.dates.prev} → {d.dates.current} 매물 변화</div>}
          </div>
          <button className="cm-x" onClick={onClose} aria-label="닫기"><X size={18} /></button>
        </div>
        {!d ? <div style={{ padding: 40 }}><Loading /></div>
          : d.note ? <div className="dash-empty" style={{ margin: 16 }}>{d.note}</div>
          : (
            <>
              <div className="cm-stat">
                <span className="cm-stat-pill add">신규 +{d.added.length}</span>
                <span className="cm-stat-sub">매매 {tradeBreak(d.added).A1}·전세 {tradeBreak(d.added).B1}·월세 {tradeBreak(d.added).B2}</span>
                <span className="cm-stat-pill rm">빠짐 −{d.removed.length}</span>
                <span className="cm-stat-sub">매매 {tradeBreak(d.removed).A1}·전세 {tradeBreak(d.removed).B1}·월세 {tradeBreak(d.removed).B2}</span>
                {!!(d.bumped && d.bumped.length) && <span className="cm-stat-pill bump">끌올 {d.bumped.length}</span>}
              </div>
              {!!(d.bumped && d.bumped.length) && (
                <div className="cm-bumpnote">‘끌올’은 가격·동·평형·중개사가 같은 매물을 내렸다 다시 올린 것 — 실제 신규/빠짐에서 제외했어요.</div>
              )}
              <div className="cm-filters">
                <div className="cm-seg">
                  {[["all", "전체"], ["A1", "매매"], ["B1", "전세"], ["B2", "월세"]].map(([v, l]) => (
                    <button key={v} className={tt === v ? "on" : ""} onClick={() => setTt(v)}>{l}</button>
                  ))}
                </div>
                {dongs.length > 1 && (
                  <select value={dong} onChange={(e) => setDong(e.target.value)}>
                    <option value="all">전체 동</option>
                    {dongs.map((x) => <option key={x} value={x}>{x}</option>)}
                  </select>
                )}
                {areas.length > 1 && (
                  <select value={area} onChange={(e) => setArea(e.target.value)}>
                    <option value="all">전체 평형</option>
                    {areas.map((x) => <option key={x} value={x}>{/^\d/.test(x) ? `${x}㎡` : x}</option>)}
                  </select>
                )}
                {filtering && <button className="cm-reset" onClick={() => { setTt("all"); setDong("all"); setArea("all"); }}>초기화</button>}
              </div>
              <div className="cm-body">
                <ChangeList title="새로 나온 매물" kind="add" items={added} showComplex={showComplex} />
                <ChangeList title="빠진 매물" kind="rm" items={removed} showComplex={showComplex} />
                {!!(d.bumped && d.bumped.length) && <ChangeList title="끌올(재등록)" kind="bump" items={bumped} showComplex={showComplex} />}
              </div>
            </>
          )}
      </div>
    </div>
  );
}

function ChangeList({ title, kind, items, showComplex }: {
  title: string; kind: "add" | "rm" | "bump"; items: ChgItem[]; showComplex: boolean;
}) {
  return (
    <section className="cm-sec">
      <div className={`cm-sec-h ${kind}`}>
        {kind === "add" ? <Plus size={14} strokeWidth={2.6} /> : kind === "rm" ? <Minus size={14} strokeWidth={2.6} /> : <RefreshCw size={13} strokeWidth={2.6} />}
        {title} <b>{items.length}건</b>
      </div>
      {items.length === 0 ? <div className="cm-none">해당 조건의 매물이 없어요</div>
        : (
          <div className="cm-list">
            {items.map((x, i) => (
              <Link key={i} to={`/complex/${x.complex_no}`} className={`cm-row ${kind}`}>
                <span className={`cm-tt t-${x.trade_type}`}>{TT[x.trade_type] || x.trade_type}</span>
                <span className="cm-main">
                  {showComplex && x.complex_name && <b className="cm-cx">{x.complex_name}</b>}
                  <span className="cm-meta">{[x.area_name ? `${x.area_name}㎡` : null, x.floor, x.building, x.direction].filter(Boolean).join(" · ")}</span>
                </span>
                <span className="cm-price">{x.price}</span>
              </Link>
            ))}
          </div>
        )}
    </section>
  );
}

export function OfficeTab({ office, method, onUnlink }: { office: Office; method?: string; onUnlink: () => void }) {
  return (
    <Card>
      <div style={{ fontSize: 18, fontWeight: 700 }}>{office.realtor_name}</div>
      <div className="muted" style={{ fontSize: 13 }}>
        {[office.address, office.representative ? `대표 ${office.representative}` : null].filter(Boolean).join(" · ")}
      </div>
      <div style={{ fontSize: 13 }}>
        {office.tel && <span style={{ marginRight: 12 }}><Phone size={12} aria-hidden /> {office.tel}</span>}
        {office.cell && <span>휴대폰 {office.cell}</span>}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <Link to={`/realtor/${encodeURIComponent(office.realtor_id)}`} className="ai-send" style={{ padding: "7px 14px", textDecoration: "none" }}>
          내 중개사무소 상세 보기
        </Link>
        <button className="auth-btn ghost" onClick={onUnlink}>사무소 변경/해제</button>
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
        인증방식: {method === "doc" ? "서류 승인" : "전화 인증"}
      </div>
    </Card>
  );
}

export function AuditTab({ authH }: { authH: () => Record<string, string> }) {
  return (
    <ListingAudit
      authH={authH()}
      title="매물 표시·광고 점검"
      intro="내 사무소 매물을 유형·거래별로 골라 표시·광고 의무사항(층·면적·주차·관리비·방향 등) 누락을 점검합니다. 건축물대장 기준값과 자동 대조해요."
      breakdownUrl="/lounge/audit/breakdown"
      buildAuditUrl={(kind, trade, offset, limit) =>
        `/lounge/audit/listings?kind=${kind}&trade=${trade}&offset=${offset}&limit=${limit}`}
    />
  );
}


export function EditTab({ authH }: { authH: () => Record<string, string> }) {
  const [content, setContent] = useState("");
  const [items, setItems] = useState<EditReq[]>([]);
  const [sending, setSending] = useState(false);
  const load = useCallback(() => {
    fetch(`${API_BASE}/lounge/edit-requests`, { headers: authH() })
      .then((r) => r.json()).then((d) => setItems(d.items ?? [])).catch(() => {});
  }, [authH]);
  useEffect(() => { load(); }, [load]);
  const submit = () => {
    if (!content.trim()) return;
    setSending(true);
    fetch(`${API_BASE}/lounge/edit-request`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }).then((r) => { if (!r.ok) throw new Error(); setContent(""); load(); })
      .catch(() => alert("전송 실패")).finally(() => setSending(false));
  };
  return (
    <Card>
      <p style={{ margin: 0 }}>사무소 정보 중 수정이 필요한 내용을 적어주세요. <b>관리자에게 바로 전달</b>됩니다.</p>
      <textarea className="ai-input" rows={4} value={content} onChange={(e) => setContent(e.target.value)}
        placeholder="예: 대표 전화번호가 02-000-0000 으로 바뀌었습니다 / 주소가 변경되었습니다" />
      <button className="ai-send" style={{ padding: "7px 16px", justifySelf: "start" }} disabled={sending} onClick={submit}>
        수정요청 보내기
      </button>
      {items.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>요청 내역</div>
          {items.map((it) => (
            <div key={it.id} style={{ borderTop: "1px solid var(--c-border)", padding: "8px 0", fontSize: 13 }}>
              <span className="ctx-badge" style={badgeOf(it.status)}>{statusKr(it.status)}</span>
              <span style={{ marginLeft: 8 }}>{it.content}</span>
              {it.admin_note && <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>↳ 관리자: {it.admin_note}</div>}
              <div className="muted" style={{ fontSize: 11 }}>{it.created_at}</div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export function LeadsTab({ authH }: { authH: () => Record<string, string> }) {
  const [items, setItems] = useState<Lead[]>([]);
  const load = useCallback(() => {
    fetch(`${API_BASE}/lounge/leads`, { headers: authH() })
      .then((r) => r.json()).then((d) => setItems(d.items ?? [])).catch(() => {});
  }, [authH]);
  useEffect(() => { load(); }, [load]);
  const setStatus = (id: number, status: string) => {
    fetch(`${API_BASE}/lounge/leads/${id}/status`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }).then(() => load());
  };
  if (items.length === 0) return <Card><p className="muted" style={{ margin: 0 }}>아직 들어온 상담신청이 없습니다. 홈페이지를 만들면 상담신청이 여기로 쌓입니다.</p></Card>;
  return (
    <div style={{ overflowX: "auto" }}>
      <table>
        <thead><tr><th>상태</th><th>이름</th><th>연락처</th><th>문의내용</th><th>접수</th><th></th></tr></thead>
        <tbody>
          {items.map((l) => (
            <tr key={l.id}>
              <td><span className="ctx-badge" style={leadBadge(l.status)}>{leadKr(l.status)}</span></td>
              <td>{l.name ?? "-"}</td>
              <td>{l.phone ? <a href={`tel:${l.phone.replace(/[^0-9+]/g, "")}`}>{l.phone}</a> : "-"}</td>
              <td style={{ fontSize: 13, maxWidth: 320 }}>{l.message ?? "-"}</td>
              <td className="muted" style={{ fontSize: 12, whiteSpace: "nowrap" }}>{l.created_at}</td>
              <td style={{ whiteSpace: "nowrap" }}>
                {l.status !== "done" && <button className="chip" onClick={() => setStatus(l.id, "done")}>완료</button>}
                {l.status === "new" && <button className="chip" onClick={() => setStatus(l.id, "read")}>읽음</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AdminPick({ authH, onPicked }: { authH: () => Record<string, string>; onPicked: () => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ realtor_id: string; realtor_name: string | null; location?: string | null; representative?: string | null }[]>([]);
  const search = () => {
    if (!q.trim()) return;
    fetch(`${API_BASE}/stats/realtors/search?q=${encodeURIComponent(q)}&limit=100`)
      .then((r) => r.json()).then((d) => setResults(d.items ?? [])).catch(() => {});
  };
  const pick = (rid: string) => {
    fetch(`${API_BASE}/lounge/select`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ realtor_id: rid }),
    }).then((r) => { if (!r.ok) throw new Error(); onPicked(); }).catch(() => alert("연결 실패"));
  };
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <input className="ai-input" style={{ flex: 1 }} placeholder="상호 (+지역: 명가 군포)" value={q}
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") search(); }} />
        <button className="ai-send" style={{ padding: "0 16px" }} onClick={search}>검색</button>
      </div>
      {results.map((o) => (
        <div key={o.realtor_id} className="lounge-cand">
          <div><b>{o.realtor_name}</b>
            <div className="muted" style={{ fontSize: 12 }}>{[o.location, o.representative].filter(Boolean).join(" · ")}</div></div>
          <button className="ai-send" style={{ padding: "6px 14px" }} onClick={() => pick(o.realtor_id)}>연결</button>
        </div>
      ))}
    </div>
  );
}

// ── 직원(소속공인중개사·중개보조원) 가입 — 전화인증 → 사무소 검색 → 공부상 명단에서 본인 선택 → 대표 승인 대기
type RosterItem = { name: string; role: "assoc" | "assist"; role_kr: string };

export function StaffJoin({ authH, phoneVerified, onNeedPhone, onDone }: {
  authH: () => Record<string, string>; phoneVerified: boolean;
  onNeedPhone: () => void; onDone: () => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ realtor_id: string; realtor_name: string | null; location?: string | null; representative?: string | null }[]>([]);
  const [office, setOffice] = useState<{ realtor_id: string; realtor_name: string | null } | null>(null);
  const [roster, setRoster] = useState<RosterItem[] | null>(null);
  const [manual, setManual] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState<"assoc" | "assist">("assoc");
  const [busy, setBusy] = useState(false);

  if (!phoneVerified) {
    return (
      <Card>
        <p><b>소속공인중개사·중개보조원</b>도 본인 명의 <b>휴대폰 인증</b>이 먼저 필요합니다.</p>
        <p className="muted" style={{ fontSize: 13 }}>인증 후 사무소를 검색해 가입 신청하면, 대표님 승인 즉시 이용할 수 있어요.</p>
        <button className="ai-send" style={{ padding: "8px 18px" }} onClick={onNeedPhone}>휴대폰 인증하기</button>
      </Card>
    );
  }

  const search = () => {
    if (!q.trim()) return;
    fetch(`${API_BASE}/stats/realtors/search?q=${encodeURIComponent(q)}&limit=100`)
      .then((r) => r.json()).then((d) => setResults(d.items ?? [])).catch(() => {});
  };
  const pickOffice = (o: { realtor_id: string; realtor_name: string | null }) => {
    setOffice(o); setRoster(null); setManual(false); setName("");
    fetch(`${API_BASE}/lounge/office-roster?realtor_id=${encodeURIComponent(o.realtor_id)}`, { headers: authH() })
      .then((r) => r.json()).then((d) => setRoster(d.items ?? [])).catch(() => setRoster([]));
  };
  const apply = async (nm: string, rl: "assoc" | "assist") => {
    if (!office || busy) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/lounge/staff/apply`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ realtor_id: office.realtor_id, role: rl, name: nm }),
      });
      if (!r.ok) throw new Error();
      onDone();
    } catch { alert("신청에 실패했어요. 잠시 후 다시 시도해 주세요."); }
    finally { setBusy(false); }
  };

  return (
    <Card>
      {!office ? (
        <>
          <p><b>우리 사무소를 검색</b>해 주세요. (상호·대표자명)</p>
          <div style={{ display: "flex", gap: 6 }}>
            <input className="ai-input" style={{ flex: 1 }} placeholder="상호 (+지역·대표자: 명가 군포)" value={q}
              onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") search(); }} />
            <button className="ai-send" style={{ padding: "0 16px" }} onClick={search}>검색</button>
          </div>
          {results.map((o) => (
            <div key={o.realtor_id} className="lounge-cand">
              <div><b>{o.realtor_name}</b>
                <div className="muted" style={{ fontSize: 12 }}>{[o.location, o.representative ? `대표 ${o.representative}` : null].filter(Boolean).join(" · ")}</div></div>
              <button className="ai-send" style={{ padding: "6px 14px" }} onClick={() => pickOffice(o)}>이 사무소</button>
            </div>
          ))}
        </>
      ) : (
        <>
          <p><b>{office.realtor_name}</b> — 등록된 직원 명단에서 <b>본인을 선택</b>해 주세요.</p>
          <button className="chip" style={{ width: "fit-content" }} onClick={() => setOffice(null)}>← 사무소 다시 검색</button>
          {roster === null ? <Loading /> : (
            <div style={{ display: "grid", gap: 8 }}>
              {roster.map((p) => (
                <div key={p.name + p.role} className="lounge-cand">
                  <div><b>{p.name}</b> <span className="muted" style={{ fontSize: 12 }}>{p.role_kr}</span></div>
                  <button className="ai-send" style={{ padding: "6px 14px" }} disabled={busy}
                    onClick={() => apply(p.name, p.role)}>본인입니다</button>
                </div>
              ))}
              {roster.length === 0 && <p className="muted" style={{ fontSize: 13 }}>공부상 등록된 직원 명단이 없습니다. 아래로 직접 입력해 주세요.</p>}
              {!manual ? (
                <button className="chip" style={{ width: "fit-content" }} onClick={() => setManual(true)}>명단에 없어요 — 직접 입력</button>
              ) : (
                <div style={{ display: "grid", gap: 6 }}>
                  <input className="ai-input" placeholder="이름" value={name} onChange={(e) => setName(e.target.value)} />
                  <div style={{ display: "flex", gap: 6 }}>
                    {(["assoc", "assist"] as const).map((rl) => (
                      <button key={rl} className={`chip ${role === rl ? "active" : ""}`} onClick={() => setRole(rl)}>
                        {rl === "assoc" ? "소속공인중개사" : "중개보조원"}
                      </button>
                    ))}
                  </div>
                  <button className="ai-send" style={{ padding: "8px 16px", width: "fit-content" }}
                    disabled={busy || !name.trim()} onClick={() => apply(name.trim(), role)}>가입 신청</button>
                </div>
              )}
            </div>
          )}
          <p className="muted" style={{ fontSize: 12 }}>신청하면 대표님께 알림이 가고, 승인 즉시 이용할 수 있어요.</p>
          <StaffDocSubmit authH={authH} realtorId={office.realtor_id} onDone={onDone} />
        </>
      )}
    </Card>
  );
}

// 대표 승인 없이 — 개설등록증 + 본인 이름 제출 → 관리자 확인 후 연결
function StaffDocSubmit({ authH, realtorId, onDone }: {
  authH: () => Record<string, string>; realtorId: string; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState<"assoc" | "assist">("assoc");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = () => {
    if (!name.trim()) { alert("본인 이름을 입력해 주세요."); return; }
    if (!file) { alert("개설등록증 파일을 선택해 주세요."); return; }
    const fd = new FormData();
    fd.append("document", file);
    fd.append("claimed_name", name.trim());
    fd.append("realtor_id", realtorId);
    fd.append("role", role);
    setBusy(true);
    fetch(`${API_BASE}/lounge/verify-doc`, { method: "POST", headers: authH(), body: fd })
      .then((r) => { if (!r.ok) throw new Error(); onDone(); })
      .catch(() => alert("제출에 실패했어요.")).finally(() => setBusy(false));
  };
  if (!open) {
    return (
      <button className="chip" style={{ width: "fit-content" }} onClick={() => setOpen(true)}>
        대표 승인 없이 — 개설등록증으로 인증 (관리자 확인)
      </button>
    );
  }
  return (
    <div style={{ display: "grid", gap: 6, border: "1px dashed var(--c-border)", borderRadius: 10, padding: 12 }}>
      <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
        사무소 <b>개설등록증</b>과 본인 이름을 제출하면 관리자가 확인 후 연결해 드립니다. (보통 1영업일 이내)
      </p>
      <input className="ai-input" placeholder="본인 이름" value={name} onChange={(e) => setName(e.target.value)} />
      <div style={{ display: "flex", gap: 6 }}>
        {(["assoc", "assist"] as const).map((rl) => (
          <button key={rl} className={`chip ${role === rl ? "active" : ""}`} onClick={() => setRole(rl)}>
            {rl === "assoc" ? "소속공인중개사" : "중개보조원"}
          </button>
        ))}
      </div>
      <input type="file" accept=".png,.jpg,.jpeg,.webp,.pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <button className="ai-send" style={{ padding: "8px 16px", width: "fit-content" }} disabled={busy} onClick={submit}>
        {busy ? "제출 중…" : "제출하기"}
      </button>
    </div>
  );
}

// ── 직원관리(대표 전용) — 승인 대기·활동중 직원·초대장
type StaffMember = { user_id: string; role: string; role_kr: string; status: string;
  staff_name: string | null; nickname: string | null; matched_phone: string | null; created_at: string };
type StaffInvite = { id: number; phone_digits: string; role: string; role_kr: string; name: string | null; created_at: string };

export function StaffManageTab({ authH, office }: { authH: () => Record<string, string>; office: Office }) {
  const [data, setData] = useState<{ members: StaffMember[]; invites: StaffInvite[] } | null>(null);
  const [roster, setRoster] = useState<RosterItem[]>([]);
  const [invPhone, setInvPhone] = useState("");
  const [invName, setInvName] = useState("");
  const [invRole, setInvRole] = useState<"assoc" | "assist">("assoc");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetch(`${API_BASE}/lounge/staff`, { headers: authH() })
      .then((r) => r.json()).then(setData).catch(() => setData({ members: [], invites: [] }));
  }, [authH]);
  useEffect(() => {
    load();
    fetch(`${API_BASE}/lounge/office-roster?realtor_id=${encodeURIComponent(office.realtor_id)}`, { headers: authH() })
      .then((r) => r.json()).then((d) => setRoster(d.items ?? [])).catch(() => {});
  }, [load, authH, office.realtor_id]);

  const act = async (path: string, body: object) => {
    if (busy) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}${path}`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error();
      load();
    } catch { alert("처리에 실패했어요."); }
    finally { setBusy(false); }
  };
  const delInvite = (id: number) =>
    fetch(`${API_BASE}/lounge/staff/invite/${id}`, { method: "DELETE", headers: authH() }).then(load);
  const sendInvite = async () => {
    const digits = invPhone.replace(/\D/g, "");
    if (digits.length < 10) { alert("휴대폰 번호를 확인해 주세요."); return; }
    await act("/lounge/staff/invite", { phone: digits, role: invRole, name: invName.trim() });
    setInvPhone(""); setInvName("");
    alert("초대 문자를 보냈어요. 상대가 가입 후 전화인증하면 자동 승인됩니다.");
  };

  if (!data) return <Loading />;
  const pending = data.members.filter((m) => m.status === "pending");
  const active = data.members.filter((m) => m.status === "active");

  return (
    <div style={{ display: "grid", gap: 14, maxWidth: 680 }}>
      <div className="dash-sec-h"><h3><Users size={16} strokeWidth={2.3} /> 승인 대기 {pending.length > 0 && <span className="dash-badge">{pending.length}</span>}</h3></div>
      {pending.length === 0 ? <div className="dash-empty">대기 중인 가입 신청이 없습니다.</div> :
        pending.map((m) => (
          <div key={m.user_id} className="lounge-cand">
            <div><b>{m.staff_name || m.nickname || "이름없음"}</b> <span className="muted" style={{ fontSize: 12 }}>{m.role_kr}{m.matched_phone && ` · ${m.matched_phone}`} · 신청 {m.created_at?.slice(5, 10)}</span></div>
            <span style={{ display: "flex", gap: 6 }}>
              <button className="ai-send" style={{ padding: "6px 14px" }} disabled={busy}
                onClick={() => act("/lounge/staff/approve", { user_id: m.user_id })}>승인</button>
              <button className="chip" disabled={busy}
                onClick={() => confirm("이 신청을 거절할까요?") && act("/lounge/staff/reject", { user_id: m.user_id })}>거절</button>
            </span>
          </div>
        ))}

      <div className="dash-sec-h"><h3>활동 중인 직원</h3></div>
      {active.length === 0 ? <div className="dash-empty">아직 등록된 직원이 없습니다. 아래 초대장으로 초대해 보세요.</div> :
        active.map((m) => (
          <div key={m.user_id} className="lounge-cand">
            <div><b>{m.staff_name || m.nickname || "이름없음"}</b> <span className="muted" style={{ fontSize: 12 }}>{m.role_kr}{m.matched_phone && ` · ${m.matched_phone}`}</span></div>
            <button className="chip" disabled={busy}
              onClick={() => confirm("이 직원의 연결을 해제할까요?") && act("/lounge/staff/reject", { user_id: m.user_id })}>해제</button>
          </div>
        ))}

      <div className="dash-sec-h"><h3>초대장 보내기</h3></div>
      <div style={{ display: "grid", gap: 6, border: "1px solid var(--c-border)", borderRadius: 12, padding: 14 }}>
        {roster.length > 0 && (
          <select className="rl-sort" style={{ width: "100%" }} value=""
            onChange={(e) => {
              const p = roster.find((x) => x.name + x.role === e.target.value);
              if (p) { setInvName(p.name); setInvRole(p.role); }
            }}>
            <option value="">공부상 직원 명단에서 선택 (선택사항)</option>
            {roster.map((p) => <option key={p.name + p.role} value={p.name + p.role}>{p.name} — {p.role_kr}</option>)}
          </select>
        )}
        <input className="ai-input" placeholder="직원 휴대폰 번호 (01012345678)" inputMode="numeric"
          value={invPhone} onChange={(e) => setInvPhone(e.target.value)} />
        <div style={{ display: "flex", gap: 6 }}>
          <input className="ai-input" style={{ flex: 1 }} placeholder="이름" value={invName} onChange={(e) => setInvName(e.target.value)} />
          {(["assoc", "assist"] as const).map((rl) => (
            <button key={rl} className={`chip ${invRole === rl ? "active" : ""}`} onClick={() => setInvRole(rl)}>
              {rl === "assoc" ? "소속공인" : "보조원"}
            </button>
          ))}
        </div>
        <button className="ai-send" style={{ padding: "9px 16px" }} disabled={busy} onClick={sendInvite}>초대 문자 보내기</button>
        <p className="muted" style={{ fontSize: 12, margin: 0 }}>초대받은 번호로 콕집 가입 + 휴대폰 인증하면 <b>승인 절차 없이 바로</b> 연결됩니다.</p>
      </div>
      {data.invites.length > 0 && (
        <>
          <div className="dash-sec-h"><h3>보낸 초대장 (대기 중)</h3></div>
          {data.invites.map((iv) => (
            <div key={iv.id} className="lounge-cand">
              <div><b>{iv.name || iv.phone_digits}</b> <span className="muted" style={{ fontSize: 12 }}>{iv.role_kr} · {iv.phone_digits} · {iv.created_at?.slice(5, 10)}</span></div>
              <button className="chip" onClick={() => delInvite(iv.id)}>취소</button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

type HpCfg = {
  slug: string | null; slogan: string | null; intro: string | null; specialties: string | null;
  biz_hours: string | null; kakao_url: string | null; consult_tel: string | null;
  map_memo: string | null; has_photo: { apt?: boolean; rep?: boolean; office?: boolean };
  photos?: { apt?: string | null; rep?: string | null; office?: string | null }; published: boolean;
};
const PHOTO_LABELS: [string, string, string][] = [
  ["rep", "대표자 사진", "히어로(상단)와 콕집 자동생성 공유카드에 쓰입니다."],
  ["office", "사무소 사진", "히어로 배경으로 쓰입니다."],
  ["apt", "명함 / 홍보 이미지", "직접 만든 명함을 올리면 공유 카드(OG)로 그대로 쓰입니다. 안 올리면 공유 카드는 콕집이 자동 생성하고, 아래 기본 아파트 이미지가 배경으로 쓰여요."],
];
const PRESETS: Record<string, string[]> = {
  apt: ["apt1", "apt2", "apt3", "apt4"],
  rep: ["man1", "man2", "man3", "woman1", "woman2", "woman3"],
  office: ["office1", "office2", "office3", "office4", "office5"],
};

type HpForm = { slug: string; slogan: string; intro: string; specialties: string;
  biz_hours: string; kakao_url: string; consult_tel: string; map_memo: string; published: boolean };
type SetFn = (k: keyof HpForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;

const WSTEPS = [
  { title: "주소 정하기", desc: "고객이 접속할 인터넷 주소예요. 영문·숫자로 짧고 기억하기 쉽게 정해주세요." },
  { title: "사무소 소개", desc: "어떤 사무소인지 한 줄 슬로건과 소개글로 알려주세요. (나중에 수정 가능)" },
  { title: "연락처·위치", desc: "고객이 전화하고 찾아올 정보예요." },
  { title: "사진 고르기", desc: "사진을 올리거나, 없으면 준비된 기본 이미지를 골라주세요. (건너뛰어도 돼요)" },
  { title: "확인하고 게시", desc: "미리보기로 확인하고, 마음에 들면 게시하세요." },
];

export function HomepageTab({ authH, office, onStatusChange }: { authH: () => Record<string, string>; office: Office; onStatusChange: () => void }) {
  const [cfg, setCfg] = useState<HpCfg | null>(null);
  const [f, setF] = useState<HpForm>({ slug: "", slogan: "", intro: "", specialties: "", biz_hours: "", kakao_url: "", consult_tel: "", map_memo: "", published: false });
  const [slugMsg, setSlugMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [ver, setVer] = useState(0);   // 업로드 사진 캐시버스터
  const [delConfirm, setDelConfirm] = useState(false);
  const [step, setStep] = useState(0);

  const load = useCallback(() => {
    fetch(`${API_BASE}/lounge/homepage`, { headers: authH() })
      .then((r) => r.json()).then((d) => {
        const c: HpCfg = d.config;
        setCfg(c);
        setF({
          slug: c.slug ?? "", slogan: c.slogan ?? "", intro: c.intro ?? "",
          specialties: c.specialties ?? "", biz_hours: c.biz_hours ?? "",
          kakao_url: c.kakao_url ?? "", consult_tel: c.consult_tel ?? office.tel ?? "",
          map_memo: c.map_memo ?? "", published: c.published,
        });
      }).catch(() => {});
  }, [authH, office.tel]);
  useEffect(() => { load(); }, [load]);

  const refreshPhotos = useCallback(() => {
    fetch(`${API_BASE}/lounge/homepage`, { headers: authH() })
      .then((r) => r.json()).then((d) => { setCfg(d.config); setVer((v) => v + 1); }).catch(() => {});
  }, [authH]);

  const checkSlug = () => {
    if (!f.slug.trim()) { setSlugMsg(null); return; }
    fetch(`${API_BASE}/lounge/homepage/slug-check?slug=${encodeURIComponent(f.slug)}`, { headers: authH() })
      .then((r) => r.json()).then((d) => setSlugMsg(d.available
        ? { ok: true, text: `사용 가능합니다 — real.koczip.com/${d.slug}` }
        : { ok: false, text: `사용할 수 없어요 (${d.reason ?? "이미 사용중"})` }))
      .catch(() => {});
  };
  const postCfg = (publish: boolean) =>
    fetch(`${API_BASE}/lounge/homepage`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ ...f, published: publish }),
    }).then((r) => r.json().then((d) => ({ ok: r.ok, d })));
  // 마법사 단계 이동 시 조용히 임시저장(진행상황 보존 + 사진 업로드용 행 생성)
  const saveDraft = async () => {
    try { const { ok, d } = await postCfg(false); if (ok) setCfg(d.config); } catch { /* ignore */ }
  };
  const save = (publish: boolean) => {
    setSaving(true);
    postCfg(publish)
      .then(({ ok, d }) => { if (!ok) throw new Error(d.detail || ""); load(); onStatusChange(); alert(publish ? "홈페이지가 게시되었습니다!" : "저장되었습니다."); })
      .catch((e) => alert(`저장 실패: ${e.message || ""}`)).finally(() => setSaving(false));
  };
  const del = () => {
    fetch(`${API_BASE}/lounge/homepage`, { method: "DELETE", headers: authH() })
      .then((r) => { if (!r.ok) throw new Error(); setDelConfirm(false); setStep(0); load(); onStatusChange();
        alert("홈페이지가 삭제되었습니다. 새로 제작할 수 있어요."); })
      .catch(() => alert("삭제 실패"));
  };
  const upPhoto = (kind: string, file: File) => {
    const fd = new FormData(); fd.append("kind", kind); fd.append("document", file);
    return fetch(`${API_BASE}/lounge/homepage/photo`, { method: "POST", headers: authH(), body: fd })
      .then((r) => { if (!r.ok) throw new Error(); refreshPhotos(); })
      .catch(() => { alert("업로드 실패 — 다시 시도해주세요"); });
  };

  if (!cfg) return <Loading />;
  const set: SetFn = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const photos = (
    <PhotoFields cfg={cfg} ver={ver} authH={authH} upPhoto={upPhoto} refreshPhotos={refreshPhotos} />
  );

  // ───────── 게시 완료 → 한눈에 보는 관리뷰 ─────────
  if (cfg.published) {
    return (
      <div className="hpm">
        <div className="hpm-head">
          <div className="hpm-head-l">
            <span className="hpm-badge">공개중</span>
            <div className="hpm-title">{office.realtor_name} 홈페이지</div>
            <a className="hpm-url" href={`https://real.koczip.com/${cfg.slug}`} target="_blank" rel="noreferrer">
              real.koczip.com/{cfg.slug}
            </a>
          </div>
          <div className="hpm-head-actions">
            <a className="chip" href={`https://real.koczip.com/${cfg.slug}`} target="_blank" rel="noreferrer">홈페이지 열기 →</a>
          </div>
        </div>

        {cfg.slug && <ShareRow name={office.realtor_name ?? "공인중개사무소"} slug={cfg.slug} />}

        <div className="hpm-card">
          <h4>사무소 소개</h4>
          <BasicFields f={f} set={set} />
        </div>
        <div className="hpm-card">
          <h4>연락처 · 위치</h4>
          <ContactFields f={f} set={set} />
        </div>
        <div className="hpm-card">
          <h4>사진</h4>
          {photos}
        </div>

        <div className="hpm-save">
          <button className="ai-send" style={{ padding: "10px 22px" }} disabled={saving} onClick={() => save(true)}>변경사항 저장</button>
          <span className="muted" style={{ fontSize: 12 }}>저장하면 공개 홈페이지에 바로 반영됩니다.</span>
        </div>

        <DangerZone slug={cfg.slug} open={delConfirm} setOpen={setDelConfirm} onDelete={del} />
      </div>
    );
  }

  // ───────── 미게시 → 단계별 마법사 ─────────
  const isLast = step === WSTEPS.length - 1;
  const next = async () => {
    if (step === 0) {
      if (!f.slug.trim()) { alert("홈페이지 주소를 입력해주세요."); return; }
      if (slugMsg && !slugMsg.ok) { alert("사용할 수 있는 주소로 바꿔주세요."); return; }
    }
    await saveDraft();
    setStep((s) => s + 1);
  };

  return (
    <div className="hpw">
      <div className="hpw-top">
        <b>중개사무소 홈페이지 만들기</b>
        <span className="hpw-count">{step + 1} / {WSTEPS.length}</span>
      </div>
      <div className="hpw-bar"><i style={{ width: `${((step + 1) / WSTEPS.length) * 100}%` }} /></div>
      <div className="hpw-dots">
        {WSTEPS.map((s, i) => (
          <button key={i} className={`hpw-dot ${i === step ? "on" : i < step ? "done" : ""}`}
            onClick={() => i < step && setStep(i)} disabled={i > step}>
            <span className="hpw-dot-n">{i < step ? "✓" : i + 1}</span>
            <span className="hpw-dot-t">{s.title}</span>
          </button>
        ))}
      </div>

      <div className="hpw-body">
        <div className="hpw-h">{WSTEPS[step].title}</div>
        <div className="hpw-d">{WSTEPS[step].desc}</div>

        {step === 0 && (
          <>
            <label className="lf-label">홈페이지 주소</label>
            <div className="hpw-slug">
              <span className="muted">real.koczip.com/</span>
              <input className="ai-input" placeholder="koczip" value={f.slug}
                onChange={(e) => { set("slug")(e); setSlugMsg(null); }} onBlur={checkSlug} />
              <button className="chip" onClick={checkSlug}>중복확인</button>
            </div>
            {slugMsg && <div className={`hpw-slugmsg ${slugMsg.ok ? "ok" : "no"}`}>{slugMsg.text}</div>}
            <p className="hpw-tip">예) 사무소 이름·동네 이름을 영문으로 — <b>koczip</b>. 한 번 정하면 바꾸기 어려우니 신중히!</p>
          </>
        )}
        {step === 1 && <BasicFields f={f} set={set} />}
        {step === 2 && <ContactFields f={f} set={set} />}
        {step === 3 && photos}
        {step === 4 && (
          <div className="hpw-done">
            <p>거의 다 됐어요! 입력한 내용을 확인하고 <b>게시하기</b>를 누르면 홈페이지가 생성됩니다.</p>
            <ul className="hpw-recap">
              <li>주소 <b>real.koczip.com/{f.slug || "—"}</b></li>
              <li>슬로건 {f.slogan || <span className="muted">(없음)</span>}</li>
              <li>상담전화 {f.consult_tel || <span className="muted">(없음)</span>}</li>
            </ul>
            <p className="muted" style={{ fontSize: 12 }}>게시하면 누구나 접속할 수 있고, 상담신청은 ‘상담신청’ 탭으로 들어옵니다. 게시 후에도 언제든 수정할 수 있어요.</p>
          </div>
        )}
      </div>

      <div className="hpw-nav">
        {step > 0
          ? <button className="auth-btn ghost" onClick={() => setStep((s) => s - 1)}>← 이전</button>
          : <span />}
        {!isLast
          ? <button className="ai-send" style={{ padding: "10px 24px" }} onClick={next}>다음 →</button>
          : (
            <div className="hpw-nav-end">
              <button className="auth-btn ghost" disabled={saving} onClick={() => save(false)}>임시저장</button>
              <button className="ai-send" style={{ padding: "10px 24px" }} disabled={saving} onClick={() => save(true)}>게시하기</button>
            </div>
          )}
      </div>
    </div>
  );
}

function BasicFields({ f, set }: { f: HpForm; set: SetFn }) {
  return (
    <>
      <label className="lf-label">한줄 슬로건</label>
      <input className="ai-input" placeholder="둔촌동 재건축 전문, 30년 경력" value={f.slogan} onChange={set("slogan")} />
      <label className="lf-label">소개글</label>
      <textarea className="ai-input" rows={4} placeholder="우리 사무소를 소개하는 인사말, 강점 등을 적어주세요." value={f.intro} onChange={set("intro")} />
      <label className="lf-label">전문분야 <span className="muted">(쉼표로 구분)</span></label>
      <input className="ai-input" placeholder="아파트 매매, 재건축, 전월세" value={f.specialties} onChange={set("specialties")} />
    </>
  );
}

function ContactFields({ f, set }: { f: HpForm; set: SetFn }) {
  return (
    <>
      <div className="hp-grid2">
        <div><label className="lf-label">상담 전화</label>
          <input className="ai-input" placeholder="02-000-0000" value={f.consult_tel} onChange={set("consult_tel")} /></div>
        <div><label className="lf-label">영업시간</label>
          <input className="ai-input" placeholder="평일 09-18, 토 09-13" value={f.biz_hours} onChange={set("biz_hours")} /></div>
      </div>
      <label className="lf-label">카카오톡 채널/오픈채팅 URL <span className="muted">(선택)</span></label>
      <input className="ai-input" placeholder="https://pf.kakao.com/..." value={f.kakao_url} onChange={set("kakao_url")} />
      <label className="lf-label">오시는 길 메모 <span className="muted">(선택)</span></label>
      <input className="ai-input" placeholder="O호선 OO역 3번 출구 도보 2분, 건물 앞 주차" value={f.map_memo} onChange={set("map_memo")} />
    </>
  );
}

function PhotoFields({ cfg, ver, authH, upPhoto, refreshPhotos }: {
  cfg: HpCfg; ver: number; authH: () => Record<string, string>;
  upPhoto: (kind: string, f: File) => void; refreshPhotos: () => void;
}) {
  return (
    <>
      {PHOTO_LABELS.map(([kind, label, hint]) => (
        <PhotoSlot key={kind} kind={kind} label={label} hint={hint}
          marker={cfg.photos?.[kind as "apt" | "rep" | "office"] ?? null}
          slug={cfg.slug} ver={ver}
          authH={authH} onUpload={(file) => upPhoto(kind, file)} onChange={refreshPhotos} />
      ))}
    </>
  );
}

function DangerZone({ slug, open, setOpen, onDelete }: {
  slug: string | null; open: boolean; setOpen: (v: boolean) => void; onDelete: () => void;
}) {
  return (
    <div className="hpm-danger">
      {!open ? (
        <button className="chip" style={{ color: "#c0392b", borderColor: "#f0c8c8" }} onClick={() => setOpen(true)}>홈페이지 삭제</button>
      ) : (
        <div className="hpm-danger-box">
          <div style={{ color: "#c0392b", fontWeight: 700, marginBottom: 6 }}>정말 삭제하시겠어요?</div>
          <p className="muted" style={{ fontSize: 13, margin: "0 0 10px", lineHeight: 1.6 }}>
            홈페이지 내용·사진·주소(<b>real.koczip.com/{slug}</b>)가 <b style={{ color: "#c0392b" }}>영구 삭제</b>되며
            <b style={{ color: "#c0392b" }}> 절대 복원할 수 없습니다.</b> 삭제 후에는 처음부터 새로 제작해야 합니다.
          </p>
          <button className="ai-send" style={{ background: "#c0392b", padding: "7px 16px", marginRight: 8 }} onClick={onDelete}>영구 삭제합니다</button>
          <button className="auth-btn ghost" onClick={() => setOpen(false)}>취소</button>
        </div>
      )}
    </div>
  );
}

export function DocSubmit({ authH, onDone }: { authH: () => Record<string, string>; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = () => {
    if (!file) { alert("서류 파일을 선택해주세요."); return; }
    const fd = new FormData();
    fd.append("document", file);
    fd.append("claimed_name", name);
    setBusy(true);
    fetch(`${API_BASE}/lounge/verify-doc`, { method: "POST", headers: authH(), body: fd })
      .then((r) => { if (!r.ok) throw new Error(); onDone(); })
      .catch(() => alert("제출 실패")).finally(() => setBusy(false));
  };
  return (
    <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
      <input className="ai-input" placeholder="중개사무소명(선택)" value={name} onChange={(e) => setName(e.target.value)} />
      <input type="file" accept=".png,.jpg,.jpeg,.webp,.pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <button className="ai-send" style={{ padding: "7px 16px", justifySelf: "start" }} disabled={busy} onClick={submit}>
        서류 제출
      </button>
    </div>
  );
}

function PhotoSlot({ kind, label, hint, marker, slug, ver, authH, onUpload, onChange }: {
  kind: string; label: string; hint?: string; marker: string | null;
  slug?: string | null; ver?: number;
  authH: () => Record<string, string>; onUpload: (f: File) => void | Promise<void>; onChange: () => void;
}) {
  const [uploading, setUploading] = useState(false);
  const setPreset = (preset: string) => {
    fetch(`${API_BASE}/lounge/homepage/preset`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ kind, preset }),
    }).then((r) => { if (!r.ok) throw new Error(); onChange(); }).catch(() => alert("실패"));
  };
  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";  // 같은 파일 다시 선택 가능하게
    if (!f) return;
    if (f.size > 8_000_000) { alert("사진이 너무 큽니다 (최대 8MB). 더 작은 이미지로 올려주세요."); return; }
    setUploading(true);
    try { await onUpload(f); } finally { setUploading(false); }
  };
  const selPreset = marker?.startsWith("preset:") ? marker.slice(7) : null;
  const isUpload = marker === "upload";
  // 현재 선택된 이미지 미리보기 — 프리셋이면 그 썸네일, 업로드면 내 사진(slug 저장 시)
  const curSrc = selPreset ? `/presets/${selPreset}.webp`
    : (isUpload && slug) ? `${API_BASE}/public/homepage/${slug}/photo/${kind}?v=${ver ?? 0}` : null;
  return (
    <div style={{ border: "1px solid var(--c-border)", borderRadius: 10, padding: 10, marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <b style={{ fontSize: 13 }}>{label}</b>
        <span className="muted" style={{ fontSize: 11 }}>
          {isUpload ? "내 사진 사용중" : selPreset ? "기본 이미지 사용중" : "미선택"}
        </span>
      </div>
      {hint && <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>{hint}</div>}
      {curSrc && (
        <img className="hp-cur" src={curSrc} alt="현재 선택" style={{ marginBottom: 8 }} />
      )}
      {isUpload && !slug && (
        <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>※ 주소(slug) 저장 후 업로드 사진 미리보기가 표시됩니다.</div>
      )}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {PRESETS[kind].map((name) => (
          <button key={name} type="button" className="hp-thumb"
            style={selPreset === name ? { outline: "3px solid #1268d3" } : undefined}
            onClick={() => setPreset(name)}>
            <img src={`/presets/${name}.webp`} alt={label} loading="lazy" />
          </button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 8 }}>
        <label className={`chip${uploading ? " hp-uploading" : ""}`} style={{ cursor: uploading ? "default" : "pointer" }}>
          {uploading ? <span className="hp-upload-busy"><span className="hp-spin" /> 업로드 중…</span> : "내 사진 올리기"}
          <input type="file" accept=".png,.jpg,.jpeg,.webp" style={{ display: "none" }} disabled={uploading}
            onChange={handleFile} />
        </label>
        {marker && !uploading && <button type="button" className="chip" onClick={() => setPreset("")}>비우기</button>}
      </div>
      {uploading && <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>사진을 등록하고 있어요. 잠시만 기다려주세요…</div>}
    </div>
  );
}

function ShareRow({ name, slug }: { name: string; slug: string }) {
  const url = `https://real.koczip.com/${slug}`;
  const [copied, setCopied] = useState(false);
  const hasNative = typeof navigator !== "undefined" && "share" in navigator;
  const copy = async () => { const ok = await copyText(url); setCopied(ok); setTimeout(() => setCopied(false), 1500); };
  return (
    <div style={{ marginTop: 12, padding: "12px 14px", background: "#f7f9fc", borderRadius: 10 }}>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8, display: "flex", alignItems: "center", gap: 5 }}>
        <Share2 size={13} strokeWidth={2.2} aria-hidden /> 내 홈페이지 공유 — <b style={{ color: "#1268d3" }}>{url}</b>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {hasNative && (
          <button className="ai-send" style={{ padding: "7px 16px" }}
            onClick={() => shareUrlNative(name, url)}>
            <Share2 size={13} strokeWidth={2.4} aria-hidden style={{ verticalAlign: "-2px", marginRight: 4 }} />
            공유하기 (카카오톡·문자…)
          </button>
        )}
        <button className="chip" onClick={copy}>
          <Link2 size={12} strokeWidth={2.4} aria-hidden style={{ verticalAlign: "-2px", marginRight: 3 }} />
          {copied ? "복사됨!" : "URL 복사"}
        </button>
        <a className="chip" href={url} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>홈페이지 열기 →</a>
      </div>
      <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
        {hasNative
          ? "‘공유하기’ → 카카오톡을 고르면 링크가 전송되고, 명함 카드가 자동으로 붙습니다."
          : "PC에서는 URL을 복사해 카카오톡에 붙여넣으면 명함 카드가 자동으로 붙습니다."}
      </div>
    </div>
  );
}

function statusKr(s: string) { return s === "done" ? "처리완료" : s === "rejected" ? "반려" : "접수"; }
function badgeOf(s: string) {
  return s === "done" ? { background: "#e6f7ed", color: "#1a7f4b" }
    : s === "rejected" ? { background: "#fde8e8", color: "#c0392b" }
    : { background: "#fff4e6", color: "#d9480f" };
}
function leadKr(s: string) { return s === "done" ? "완료" : s === "read" ? "읽음" : "신규"; }
function leadBadge(s: string) {
  return s === "done" ? { background: "#e6f7ed", color: "#1a7f4b" }
    : s === "read" ? { background: "#eef2f5", color: "#555" }
    : { background: "#e7f5ff", color: "#1268d3" };
}

// ───────── 매물장: 내 사무소 매물 전체 + 메모/연락처 ─────────
type MLItem = {
  article_no: string; complex_no: string | null; complex_name: string | null; trade_type: string;
  type: string; area_name: string; area1_m2: number; area2_m2: number; floor_info: string;
  area_py?: number | null; room_cnt?: number | null; bath_cnt?: number | null;
  total_floor?: number | null; settle_ymd?: string; move_in?: string;
  maintenance_fee?: number | null; deposit?: number | null; owner_name?: string;
  heating?: string; elevator?: string; options?: string; ho?: string;
  ad_check?: { done: number; total: number; missing: { no: number; item: string }[] };
  direction: string; price_text: string; rent_price_text: string; price: number; confirm_ymd: string;
  building_name: string; tags: string[]; same_addr_cnt: number; same_addr_min: number; same_addr_max: number;
  price_change_state: string; feature_desc: string; naver_url: string; cp_name: string;
  verification_type: string; lat: number; lng: number; memo: string; contact: string; manager: string;
  dong: string; address: string;
  // 건축물대장 건물명 — 비단지 매물에만 붙는다(원천엔 이름이 없다)
  bld_name?: string;
  parking_total: number | null; parking_per: number | null; households: number | null;
  approve_ymd: string | number | null; builder: string | null; mgmt_tel: string | null;
  // 비공개매물(콕집 직접등록) 전용 — 네이버 매물엔 없다
  is_private?: boolean; private_id?: number; visibility?: string; created_by?: string;
  source_article_no?: string; source_saved_at?: string;
  // 같은 물건이 매물장에도 있고 네이버에도 광고 중이면 한 줄에 두 표시가 붙는다
  also_naver?: boolean; naver_article_no?: string;
  import_file?: string | null; import_at?: string | null;   // 엑셀에서 가져온 매물
  // 비주거 — 상가·사무실·토지·공장·건물에서만 뜻이 있다(주거 매물엔 값이 없다)
  premium?: number | null; bunyang_premium?: number | null; vat_separate?: string;
  current_biz?: string; tenant_until?: string; road_contact?: string;
  land_area_m2?: number | null; total_area_m2?: number | null;
  land_category?: string; land_use?: string;
  ceiling_h?: number | null; power_kw?: number | null;
  rent_income?: number | null; deposit_sum?: number | null;
  violation?: string; bc_rat?: number | null; vl_rat?: number | null;
  main_purpose?: string; height?: number | null; reg_kind?: string;
  loan_amount?: number | null;
  photos?: string[]; extra?: Record<string, any>;
};
type Manager = { name: string; position: string; role: string };
// 매물번호 조회 결과 — mine=false면 다른 사무소 물건(확인 후 열람)
type ForeignHit = { mine: boolean; article_no: string; realtor_id: string; realtor_name: string; listing: MLItem | null };
/** 전화 버튼에 넣을 번호. 하이픈만 정리하고 그대로 보여 준다(PC 는 폭이 넉넉하다). */
/** 행의 오른쪽 칸들 — 폴더 안이든 밖이든 같은 모양이라 한 군데로 모은다. */
function ListingCells({ l }: { l: MLItem }) {
  return (
    <>
      <span className="mjt-meta">
        <span className="c-ho">{unitOf(l)}</span>
        <span className="c-ar">{l.area2_m2 ? areaLabel(l.area2_m2, { supply: l.area1_m2 }) : "-"}</span>
        <span className="c-fl">{l.floor_info
          ? `${l.floor_info}${l.total_floor && !String(l.floor_info).includes("/") ? `/${l.total_floor}` : ""}층`
          : "-"}</span>
        <span className="c-st">{l.settle_ymd ? <><em className="lb">잔금</em>{l.settle_ymd}</> : null}</span>
      </span>
      {/* 전화 — PC 는 번호까지 보이고, 폰은 아이콘만. 누르면 바로 걸린다 */}
      <span className="c-ct" onClick={(e) => e.stopPropagation()}>
        {l.contact ? (
          <a className="mjt-call" href={`tel:${l.contact.replace(/[^\d+]/g, "")}`}
            title={`${l.contact} 로 전화`}>
            <Phone size={12} /><b>{fmtTelShort(l.contact)}</b>
          </a>
        ) : <span className="mjt-nocall">-</span>}
      </span>
      <span className="c-pr">
        {l.trade_type === "월세" && l.rent_price_text ? `${l.price_text}/${l.rent_price_text}` : l.price_text}
      </span>
    </>
  );
}

/** 폴더 머리에 붙는 한 줄 — 접어 둬도 무엇이 들었는지 알게 한다. */
function groupSummary(g: MLItem[]): string {
  const n: Record<string, number> = {};
  for (const l of g) n[l.trade_type || "기타"] = (n[l.trade_type || "기타"] || 0) + 1;
  const kinds = ["매매", "전세", "월세"].filter((k) => n[k]).map((k) => `${k} ${n[k]}`);
  const priv = g.filter((l) => l.is_private).length;
  if (priv) kinds.push(`직접등록 ${priv}`);
  return kinds.join(" · ");
}

/** 매물 출처 — 행마다 아이콘 하나. 자물쇠는 우리가 직접 적은 것(우리만 봄),
 *  지구본은 네이버에서 가져온 것(지금 광고 중). 뜻은 표 위 범례에 적어 뒀다. */
function SrcIcon({ l }: { l: MLItem }) {
  if (!l.is_private) {
    return <em className="c-src nv" title="네이버에서 가져온 매물 — 지금 광고 중"><Globe size={9} /></em>;
  }
  if (l.import_file) {
    return (
      <>
        <em className="c-src im" title={`엑셀에서 가져온 매물 — ${l.import_file}${l.import_at ? ` (${l.import_at})` : ""}`}>
          <FileSpreadsheet size={9} /></em>
        {l.also_naver && (
          <em className="c-src nv" title={`네이버에도 광고 중 — 매물번호 ${l.naver_article_no || ""}`}>
            <Globe size={9} /></em>
        )}
      </>
    );
  }
  return (
    <>
      <em className="c-src pv" title={`직접등록 — ${l.visibility === "me" ? "나만 보기" : "사무실 전체 공개"}`}>
        <Lock size={9} /></em>
      {/* 같은 물건이 네이버에도 올라가 있으면 둘 다 붙인다 — 광고 중인지 아닌지가
          매물장에서 바로 보여야 한다 */}
      {l.also_naver && (
        <em className="c-src nv" title={`네이버에도 광고 중 — 매물번호 ${l.naver_article_no || ""}`}>
          <Globe size={9} /></em>
      )}
    </>
  );
}

/** 표에 세울 이름. 단지형은 단지명이지만 단지가 없는 물건(빌라·상가·사무실·단독·토지…)은
 *  주소다. 그쪽 building_name 은 '일반상가'·'빌라' 같은 유형 딱지라(실측) 이름 자리에
 *  세우면 모든 행이 똑같아 보여 어느 물건인지 구별이 안 된다.
 *  주소는 시·도와 시군구를 떼고 '숭의동 121-7' 로 줄인다 — 한 사무소 물건은 대개
 *  같은 시군구라 앞부분이 매 행 반복될 뿐이다(전체 주소는 툴팁으로 남긴다). */
function isAddrFirst(l: { type?: string | null }) {
  return PL_ADDR_FIRST.includes(l.type || "");
}
function shortAddr(addr?: string | null): string {
  const t = (addr || "").trim().split(/\s+/).filter(Boolean);
  if (t.length <= 2) return t.join(" ");
  // '역삼동 산 12-3' 처럼 산번지는 세 토막이라야 동을 안 잃는다
  return t.slice(t[t.length - 2] === "산" ? -3 : -2).join(" ");
}
/** 비단지 매물의 building_name 은 이름이 아니라 유형 딱지다 — 실측한 값이 전부
 *  그랬다(일반상가·단지내상가 / 중소형사무실 / 대·전·답·임야 / 상가주택·빌딩…).
 *  반면 지번으로 등록한 물건은 건축물대장 건물명이 단지명 칸에 들어온다('휴먼빌파크').
 *  그런 진짜 이름만 골라 내려고 딱지 목록을 둔다 — 목록에 없으면 이름으로 본다. */
const ML_GENERIC_BLD = new Set([
  "일반상가", "단지내상가", "복합상가", "상가", "상가건물", "상가주택", "상업시설", "점포",
  "중소형사무실", "대형사무실", "일반사무실", "사무실", "오피스",
  "빌라", "연립", "다세대", "기타", "아파트", "오피스텔",
  "단독", "다가구", "전원주택", "일반원룸", "원룸", "고시원",
  "대", "전", "답", "임야", "잡종지", "과수원", "공장용지", "목장용지", "도로", "하천",
  "구거", "유지", "제방", "묘지", "주차장", "창고용지", "학교용지", "체육용지", "공원",
  "종교용지", "사적지", "양어장", "염전", "광천지", "수도용지", "주유소용지", "철도용지",
  "공장", "창고", "지식산업센터", "빌딩", "여관/모텔", "펜션", "콘도", "재개발",
]);
// 빌라 원천에는 '1동'·'가동'·'A동' 처럼 동 표기가 이름 칸에 들어온다 — 이름이 아니다
const ML_DONG_ONLY = /^(?:\d+|[A-Za-z]|[가-힣])동$/;
function realName(l: MLItem): string {
  // 중개사가 적은 이름 > 건축물대장 건물명 > 원천 값(대개 유형 딱지라 거의 걸러진다)
  const n = (l.complex_name || l.bld_name || l.building_name || "").trim();
  return !n || ML_GENERIC_BLD.has(n) || ML_DONG_ONLY.test(n) ? "" : n;
}
function mlName(l: MLItem): string {
  if (!isAddrFirst(l)) return l.complex_name || l.building_name || l.area_name || "매물";
  // 이름을 알면 이름이 먼저다 — '휴먼빌파크 (송도동 8-3)'. 주소만으로는 어느 건물인지
  // 중개사도 손님도 바로 못 떠올린다. 이름이 없을 때만 주소가 홀로 선다.
  const a = shortAddr(l.address), n = realName(l);
  return n && a ? `${n} (${a})` : a || n || l.area_name || "매물";
}
/** 동·호 칸. 단지 없는 물건은 주소를 이름 칸에 세웠으니 여기서 법정동을 또 쓰지 않는다. */
function unitOf(l: MLItem): string {
  if (!isAddrFirst(l)) return dongHo(l);
  const d = (l.dong || "").trim(), h = (l.ho || "").trim();
  const dd = d && !(l.address || "").includes(d) ? (/동$/.test(d) ? d : `${d}동`) : "";
  const hh = h ? (/호$/.test(h) ? h : `${h}호`) : "";
  return [dd, hh].filter(Boolean).join(" ") || "-";
}

/** 동·호 표기 통일 — '104 1103' 과 '104동 1103호' 가 섞여 있었다.
 *  네이버 매물의 dong 은 법정동('송도동')이라 이미 '동'으로 끝나면 그대로 둔다. */
function dongHo(l: { dong?: string | null; ho?: string | null; address?: string | null }): string {
  const d = (l.dong || "").trim(), h = (l.ho || "").trim();
  const dd = d && !/동$/.test(d) ? `${d}동` : d;
  const hh = h && !/호$/.test(h) ? `${h}호` : h;
  return [dd, hh].filter(Boolean).join(" ") || l.address || "-";
}

function fmtTelShort(p?: string): string {
  const d = (p || "").replace(/[^0-9]/g, "");
  if (d.length === 11) return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
  if (d.length === 10) return `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}`;
  return p || "";
}

function fmtYmd(s: string) { return s && s.length === 8 ? `${s.slice(4, 6)}/${s.slice(6, 8)}` : s; }
function eok(v: number) {
  if (!v) return "-";
  const e = Math.floor(v / 10000), man = v % 10000;
  return e ? `${e}억${man ? " " + man.toLocaleString() : ""}` : `${v.toLocaleString()}만`;
}
// same_addr_min/max_price는 원 단위(네이버 raw) — 만원으로 환산 후 표기
function eokWon(v: number) { return eok(Math.round((v || 0) / 10000)); }

const ML_CATS = ["", "아파트", "오피스텔", "분양권", "빌라", "상가", "사무실", "단독"];

export function ListingsTab({ authH, office }: { authH: () => Record<string, string>; office: Office }) {
  const [items, setItems] = useState<MLItem[] | null>(null);
  const [managers, setManagers] = useState<Manager[]>([]);
  const [q, setQ] = useState("");
  const [trade, setTrade] = useState("");
  const [cat, setCat] = useState("");
  const [manager, setManager] = useState("");
  const [sort, setSort] = useState("confirm");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<Record<string, boolean>>({});
  const [detail, setDetail] = useState<MLItem | null>(null);
  const [detailOwner, setDetailOwner] = useState("");            // 타 사무소 매물일 때 사무소명
  const [foreign, setForeign] = useState<ForeignHit | null>(null); // 매물번호가 남의 물건일 때
  const [lookErr, setLookErr] = useState("");
  const [priv, setPriv] = useState(true);             // 직접등록 매물을 기본으로 포함
  const [privOnly, setPrivOnly] = useState(false);   // 비공개매물만 보기
  const [mapOpen, setMapOpen] = useState(false);     // 사무소 매물 지도
  const [privMsg, setPrivMsg] = useState<Record<string, string>>({});
  const [plOpen, setPlOpen] = useState(false);        // 비공개매물 등록 모달
  const [impOpen, setImpOpen] = useState(false);      // 매물장 엑셀 가져오기
  const [editPL, setEditPL] = useState<MLItem | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/lounge/managers`, { headers: authH() })
      .then((r) => r.json()).then((d) => setManagers(d.managers || [])).catch(() => {});
  }, [authH]);

  // 매물번호로 소유 사무소 조회 — 내 물건이면 바로 보여주고, 아니면 확인을 받는다.
  const lookup = useCallback((an: string) => {
    fetch(`${API_BASE}/lounge/listings/lookup?article_no=${encodeURIComponent(an)}`, { headers: authH() })
      .then(async (r) => {
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d?.detail || "매물번호를 조회하지 못했어요");
        return d as ForeignHit;
      })
      .then((d) => { if (d.mine && d.listing) setItems([d.listing]); else setForeign(d); })
      .catch((e) => setLookErr(e.message || "조회 실패"));
  }, [authH]);

  const load = useCallback(() => {
    setBusy(true); setForeign(null); setLookErr("");
    const p = new URLSearchParams({ q, trade, cat, manager, sort,
      private: priv || privOnly ? "1" : "0", private_only: privOnly ? "1" : "0" });
    fetch(`${API_BASE}/lounge/listings?${p}`, { headers: authH() })
      .then((r) => r.json())
      .then((d) => {
        const list: MLItem[] = d.listings || [];
        setItems(list);
        // 내 매물장에 없고 매물번호 형태면 → 남의 물건인지 조회
        const an = q.trim();
        if (list.length === 0 && /^\d{6,}$/.test(an)) lookup(an);
      })
      .catch(() => setItems([]))
      .finally(() => setBusy(false));
  }, [authH, q, trade, cat, manager, sort, priv, privOnly, lookup]);
  useEffect(() => { load(); }, [trade, cat, manager, sort, priv, privOnly]); // eslint-disable-line react-hooks/exhaustive-deps

  const patch = (an: string, k: "memo" | "contact" | "manager", v: string) =>
    setItems((its) => its ? its.map((x) => x.article_no === an ? { ...x, [k]: v } : x) : its);
  const saveNote = async (l: MLItem) => {
    await fetch(`${API_BASE}/lounge/listings/note`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ article_no: l.article_no, memo: l.memo, contact: l.contact, manager: l.manager }),
    });
    setSaved((s) => ({ ...s, [l.article_no]: true }));
    setTimeout(() => setSaved((s) => ({ ...s, [l.article_no]: false })), 1500);
  };
  // 네이버 매물 → 비공개매물장 보관(목록에서 바로)
  const toPrivate = async (l: MLItem, visibility: "office" | "me") => {
    try {
      const r = await fetch(`${API_BASE}/lounge/private-listings/from-naver`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ article_no: l.article_no, visibility }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "보관 실패");
      setPrivMsg((m) => ({ ...m, [l.article_no]: d.duplicated ? "이미 보관됨" : "보관 완료" }));
      setTimeout(() => setPrivMsg((m) => ({ ...m, [l.article_no]: "" })), 2500);
      if (priv || privOnly) load();
    } catch (e: any) { alert(e.message || "보관 실패"); }
  };

  const [folded, setFolded] = useState<Set<string>>(new Set());   // 접어 둔 단지 폴더
  // 같은 단지 물건은 한 덩어리로 — 정렬 순서는 그대로 두고 첫 등장 자리에 모은다.
  // 단지가 없는 물건(상가·단독 등)은 각자 한 덩어리다.
  const groups = useMemo(() => {
    const by = new Map<string, MLItem[]>();
    const order: string[] = [];
    for (const l of items || []) {
      const k = isAddrFirst(l) ? (l.address || `#${l.article_no}`)
                              : (l.complex_no || l.complex_name || `#${l.article_no}`);
      if (!by.has(k)) { by.set(k, []); order.push(k); }
      by.get(k)!.push(l);
    }
    return order.map((k) => by.get(k)!);
  }, [items]);

  // 직접등록 매물 삭제 — 되돌릴 수 없으니 무엇을 지우는지 이름으로 확인받는다.
  // 서버는 status='closed' 로만 바꾼다(행은 남아 복구할 수 있다).
  const delPrivate = async (l: MLItem) => {
    const what = [mlName(l), unitOf(l)].filter((x) => x && x !== "-").join(" ");
    if (!window.confirm(`${what}\n\n매물장에서 지웁니다. 계속할까요?`)) return;
    try {
      const r = await fetch(`${API_BASE}/lounge/private-listings/${l.private_id}`,
                            { method: "DELETE", headers: authH() });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || `삭제 실패 (${r.status})`);
      setDetail(null);
      load();
    } catch (e: any) { alert(e?.message || "삭제하지 못했어요"); }
  };

  // 담당자 즉시 배정(저장까지)
  const assignManager = async (l: MLItem, v: string) => {
    patch(l.article_no, "manager", v);
    await fetch(`${API_BASE}/lounge/listings/note`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ article_no: l.article_no, memo: l.memo, contact: l.contact, manager: v }),
    });
  };

  return (
    <div className="mljang">
      {/* 필터는 전부 같은 세그먼트로, 켜진 색은 파랑 하나로 통일한다.
          등록은 필터가 아니라 액션이라 오른쪽 끝으로 뽑아냈다. */}
      <div className="mlj-tb">
        <span className="mlj-srch">
          <Search size={15} aria-hidden />
          <input placeholder="단지·건물·지역 또는 네이버 매물번호" value={q} inputMode="text"
            onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
          <kbd onClick={load}>Enter</kbd>
        </span>
        <span className="mlj-seg">
          {([["", "전체"], ["매매", "매매"], ["전세", "전세"], ["월세", "월세"]] as const).map(([k, l]) => (
            <button key={k} className={trade === k ? "on" : ""} onClick={() => setTrade(k)}>{l}</button>
          ))}
        </span>
        <span className="mlj-gsel">
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="정렬">
            <option value="confirm">최신확인순</option>
            <option value="price_desc">가격↓</option>
            <option value="price_asc">가격↑</option>
          </select>
          <ChevronDown size={11} aria-hidden />
        </span>
        <button className="mlj-gbtn" onClick={() => setMapOpen(true)}>
          <MapIcon size={13} aria-hidden /> 지도
        </button>
        <button className="mlj-gbtn" onClick={() => setImpOpen(true)}>
          <Upload size={13} aria-hidden /> 매물장 가져오기
        </button>
        <button className="mlj-gbtn pri" onClick={() => { setEditPL(null); setPlOpen(true); }}>
          <Plus size={13} aria-hidden /> 매물 직접등록
        </button>
      </div>
      <div className="mlj-tb2">
        <span className="mlj-seg">
          {ML_CATS.map((c) => (
            <button key={c || "all"} className={cat === c ? "on" : ""} onClick={() => setCat(c)}>
              {c || "전체유형"}</button>
          ))}
        </span>
        <i className="mlj-div" />
        <span className="mlj-glab">담당자</span>
        <span className="mlj-gsel" title="담당자를 고르면 그 사람 매물장만 보여요">
          <select value={manager} onChange={(e) => setManager(e.target.value)} aria-label="담당자">
            <option value="">전체</option>
            <option value="미지정">미지정</option>
            {managers.map((m) => <option key={m.name} value={m.name}>{m.name}{m.position === "대표" ? " (대표)" : ""}</option>)}
          </select>
          <ChevronDown size={11} aria-hidden />
        </span>
        {/* 포함/비공개만은 원래 하나의 축이다 — 셋 중 하나로 합친다 */}
        <span className="mlj-glab">직접등록</span>
        <span className="mlj-seg">
          <button className={!priv && !privOnly ? "on" : ""}
            onClick={() => { setPriv(false); setPrivOnly(false); }}>제외</button>
          <button className={priv && !privOnly ? "on" : ""}
            onClick={() => { setPriv(true); setPrivOnly(false); }}>포함</button>
          <button className={privOnly ? "on" : ""}
            onClick={() => { setPriv(true); setPrivOnly(true); }}>
            <Lock size={11} aria-hidden />직접등록만</button>
        </span>
      </div>
      {lookErr && <div className="mlj-foreign mlj-foreign-err">{lookErr}</div>}
      {foreign && (
        <div className="mlj-foreign">
          <div className="mlj-foreign-t">다른 사무실 물건입니다. 조회하시겠습니까?</div>
          <div className="mlj-foreign-s">
            매물번호 {foreign.article_no}
            {foreign.realtor_name ? ` · ${foreign.realtor_name}` : ""}
          </div>
          <div className="mlj-foreign-b">
            <button className="on" disabled={!foreign.listing}
              onClick={() => { if (foreign.listing) { setDetailOwner(foreign.realtor_name || "다른 중개사무소"); setDetail(foreign.listing); } }}>
              조회하기
            </button>
            <button onClick={() => setForeign(null)}>취소</button>
          </div>
          {!foreign.listing && <div className="mlj-foreign-s">※ 해당 매물의 상세를 불러올 수 없습니다(사무소 미귀속 매물).</div>}
        </div>
      )}
      <div className="mlj-count">{office.realtor_name ?? "내 사무소"} · {busy
        ? <span style={{ color: "var(--c-primary)", fontWeight: 700 }}>불러오는 중…</span>
        : <>총 <b>{items?.length ?? 0}</b>개</>}
        {/* 출처 범례 — 행마다 아이콘 하나가 붙으므로 그 뜻을 여기서 한 번 말해 둔다 */}
        <span className="mlj-legend">
          <i className="src pv"><Lock size={9} /></i>직접등록 — 우리만 봅니다
          <i className="src nv"><Globe size={9} /></i>네이버 — 지금 광고 중
          <i className="src im"><FileSpreadsheet size={9} /></i>가져옴 — 엑셀 매물장에서
          <b className="both"><i className="src pv"><Lock size={9} /></i><i className="src nv"><Globe size={9} /></i>둘 다 — 매물장에도 있고 광고도 중</b>
        </span>
      </div>
      {!items || (busy && items.length === 0) ? (
        <Loading label="내 매물을 불러오는 중이에요" slowHint="매물이 많으면 조금 더 걸릴 수 있어요" />
      ) : items.length === 0 ? (
        <div className="dash-empty">표시할 매물이 없습니다. 사무소 매물이 네이버에 등록되면 자동으로 매물장에 나옵니다.</div>
      ) : (
        <div className="mjt">
          {/* 표 머리 — 좁아지면 사라진다. 행 안의 배치만 바뀌고 데이터·상태는 하나다. */}
          <div className="mjt-head">
            <span />
            <span>단지·주소</span>
            <span className="h-ho">동·호</span>
            <span className="h-ar">전용</span>
            <span className="h-fl">층</span>
            <span className="h-st">잔금</span>
            <span className="h-ct">연락처</span>
            <span style={{ textAlign: "right" }}>가격</span>
          </div>
          {groups.flatMap((g) => {
            const key = isAddrFirst(g[0]) ? (g[0].address || `#${g[0].article_no}`)
                                          : (g[0].complex_no || g[0].complex_name || `#${g[0].article_no}`);
            const name = mlName(g[0]);
            // 한 건뿐이면 폴더로 감싸지 않는다 — 열고 닫을 것이 없다
            if (g.length < 2) {
              const l = g[0];
              return [
                <div key={l.article_no} className="mjt-r" onClick={() => { setDetailOwner(""); setDetail(l); }}>
                  <span className="c-tr"><i className={`mlj-trade tr-${l.trade_type}`}>{l.trade_type}</i></span>
                  <span className="c-nm" title={isAddrFirst(l) ? (l.address || "") : ""}>
                    {name}<SrcIcon l={l} />
                  </span>
                  <ListingCells l={l} />
                </div>,
              ];
            }
            const shut = folded.has(key);
            return [
              <div key={`g-${key}`} className={"mjt-g" + (shut ? " shut" : "")}
                onClick={() => setFolded((s) => {
                  const n = new Set(s); n.has(key) ? n.delete(key) : n.add(key); return n;
                })}>
                <ChevronDown size={14} className="chev" aria-hidden />
                {shut ? <Folder size={14} /> : <FolderOpen size={14} />}
                <b>{name}</b>
                <em className="c-gn">{g.length}</em>
                <span className="mjt-g-sum">{groupSummary(g)}</span>
              </div>,
              ...(shut ? [] : g.map((l) => (
                <div key={l.article_no} className="mjt-r child"
                  onClick={() => { setDetailOwner(""); setDetail(l); }}>
                  <span className="c-tr"><i className={`mlj-trade tr-${l.trade_type}`}>{l.trade_type}</i></span>
                  {/* 폴더 안이어도 단지명은 남긴다 — 행만 떼어 봐도 어느 단지인지 읽혀야 한다 */}
                  <span className="c-nm">
                    <em className="c-sub"><i /></em>
                    <span className="c-dim" title={isAddrFirst(l) ? (l.address || "") : ""}>{mlName(l)}</span>
                    <SrcIcon l={l} />
                  </span>
                  <ListingCells l={l} />
                </div>
              ))),
            ];
          })}
        </div>
      )}
      {impOpen && (
        <ImportListings authH={authH} onClose={() => setImpOpen(false)}
          onSaved={() => { setPriv(true); load(); }} />
      )}
      {detail && <ListingDetail l={detail} owner={detailOwner} authH={authH}
        managers={managers}
        onPatch={(k, v) => { patch(detail.article_no, k, v); setDetail({ ...detail, [k]: v } as MLItem); }}
        onSaveNote={() => saveNote(detail)}
        saved={!!saved[detail.article_no]}
        onAssign={(v) => { assignManager(detail, v); setDetail({ ...detail, manager: v }); }}
        onToPrivate={(vis) => toPrivate(detail, vis)}
        privMsg={privMsg[detail.article_no]}
        onFilled={load}
        onEditPrivate={() => { setEditPL(detail); setPlOpen(true); setDetail(null); }}
        onDeletePrivate={() => delPrivate(detail)}
        onSavedPrivate={() => { setPriv(true); load(); }}
        onClose={() => { setDetail(null); setDetailOwner(""); }} />}
      {mapOpen && <OfficeMap authH={authH} officeName={office.realtor_name} onClose={() => setMapOpen(false)} />}
      {plOpen && <PrivateListingForm authH={authH} init={editPL} managers={managers}
        onClose={() => setPlOpen(false)} onSaved={() => { setPlOpen(false); setPriv(true); load(); }} />}
    </div>
  );
}

// 매물 상세 모달 — 주소·가격·면적·층·방향·확인일·검증·태그·특징·동일주소·지도·바로가기 전부

// ── 비공개매물 등록/수정 ────────────────────────────────────────────────────
// 네이버 연동이 아니라 대표·직원이 직접 등록하는 매물. 항목은 네이버 수준으로 넓게 두되
// **필수 없음** — 현장에서 아는 만큼만 적고 나중에 채우는 실제 업무 흐름에 맞춘다.
const PL_TYPES = ["아파트", "오피스텔", "빌라", "단독", "상가", "사무실", "토지", "공장", "건물", "지식산업센터", "재개발", "원룸", "분양권"];
const PL_TRADES = ["매매", "전세", "월세", "단기임대"];



// 인증이 필요한 이미지 — <img src> 는 Authorization 헤더를 못 보내므로(401 → 높이 0)
// fetch 로 받아 blob URL 로 바꿔 표시한다. 비공개매물 사진은 소속 회원만 볼 수 있다.
function AuthImg({ authH, src, alt = "", className, onClick, title }: {
  authH: () => Record<string, string>; src: string; alt?: string;
  className?: string; onClick?: () => void; title?: string;
}) {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState(false);
  useEffect(() => {
    let alive = true; let obj = "";
    setUrl(""); setErr(false);
    fetch(src, { headers: authH() })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.blob(); })
      .then((b) => { if (!alive) return; obj = URL.createObjectURL(b); setUrl(obj); })
      .catch(() => { if (alive) setErr(true); });
    return () => { alive = false; if (obj) URL.revokeObjectURL(obj); };
  }, [src]); // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <div className={`${className || ""} authimg-err`} title="사진을 불러오지 못했어요">!</div>;
  if (!url) return <div className={`${className || ""} authimg-load`} />;
  return <img src={url} alt={alt} className={className} onClick={onClick} title={title} draggable={false} />;
}

// 사진 수동 보정 — 자동 검출이 놓친 곳(작은 글자·측면 얼굴 등)을 손으로 덧칠한다.
// 좌표는 **상대좌표(0~1)** 로 보내 기기·표시크기와 무관하게 같은 지점을 가리키게 한다.
function PhotoMaskEditor({ authH, name, onClose, onDone }: {
  authH: () => Record<string, string>; name: string; onClose: () => void; onDone: () => void;
}) {
  const [rects, setRects] = useState<{ x: number; y: number; w: number; h: number }[]>([]);
  const [draw, setDraw] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [ver, setVer] = useState(0);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const rel = (e: React.PointerEvent) => {
    const b = wrapRef.current!.getBoundingClientRect();
    return { x: Math.min(1, Math.max(0, (e.clientX - b.left) / b.width)),
             y: Math.min(1, Math.max(0, (e.clientY - b.top) / b.height)) };
  };
  const down = (e: React.PointerEvent) => {
    e.preventDefault(); (e.target as Element).setPointerCapture?.(e.pointerId);
    const p = rel(e); setDraw({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
  };
  const move = (e: React.PointerEvent) => { if (!draw) return; const p = rel(e); setDraw({ ...draw, x1: p.x, y1: p.y }); };
  const up = () => {
    if (!draw) return;
    const x = Math.min(draw.x0, draw.x1), y = Math.min(draw.y0, draw.y1);
    const w = Math.abs(draw.x1 - draw.x0), h = Math.abs(draw.y1 - draw.y0);
    if (w > 0.015 && h > 0.015) setRects((r) => [...r, { x, y, w, h }]);
    setDraw(null);
  };

  const apply = async () => {
    if (!rects.length) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/lounge/private-listings/photo/${name}/mask`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ rects }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "보정 실패");
      setRects([]); setVer((v) => v + 1); onDone();
    } catch (e: any) { alert(e.message || "보정 실패"); }
    finally { setBusy(false); }
  };

  const box = draw ? {
    left: `${Math.min(draw.x0, draw.x1) * 100}%`, top: `${Math.min(draw.y0, draw.y1) * 100}%`,
    width: `${Math.abs(draw.x1 - draw.x0) * 100}%`, height: `${Math.abs(draw.y1 - draw.y0) * 100}%`,
  } : null;

  return (
    <div className="mld-ov" onClick={onClose}>
      <div className="mld pme" onClick={(e) => e.stopPropagation()}>
        <button className="mld-x" onClick={onClose} aria-label="닫기"><X size={18} /></button>
        <h3 className="mld-title">사진 보정</h3>
        <p className="pl-hint">가릴 곳을 손가락(또는 마우스)으로 <b>드래그</b>하세요. 자동으로 못 가린 작은 글자·얼굴을 덧칠할 수 있어요.</p>
        <div className="pme-wrap" ref={wrapRef}
          onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up}>
          <AuthImg authH={authH} src={`${API_BASE}/lounge/private-listings/photo/${name}?v=${ver}`}
            className="pme-img" />
          {rects.map((r, i) => (
            <div key={i} className="pme-rect" style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`,
              width: `${r.w * 100}%`, height: `${r.h * 100}%` }} />
          ))}
          {box && <div className="pme-rect pme-live" style={box} />}
        </div>
        <div className="pme-bar">
          <span>{rects.length ? `${rects.length}곳 지정됨` : "지정된 영역 없음"}</span>
          <button className="pme-undo" disabled={!rects.length} onClick={() => setRects((r) => r.slice(0, -1))}>
            <RefreshCw size={12} /> 마지막 취소
          </button>
        </div>
        <div className="pl-warn">적용하면 사진에 확정 반영되어 <b>되돌릴 수 없습니다</b>.</div>
        <div className="pl-actions">
          <button className="pl-save" disabled={busy || !rects.length} onClick={apply}>
            {busy ? "적용 중…" : "모자이크 적용"}
          </button>
          <button className="pl-cancel" onClick={onClose}>닫기</button>
        </div>
      </div>
    </div>
  );
}

/** 매물장 금액은 만원 단위다. 사람은 '10억'이라 적고 우리는 100,000 으로 저장한다.
 *  → 억·천·만을 읽어 만원으로 바꾸고, 화면에는 천단위 쉼표로 보여 준다. */
export function parseMan(raw: string): number | null {
  const t = (raw || "").replace(/[\s,]/g, "");
  if (!t) return null;
  if (/^\d+(\.\d+)?$/.test(t)) return Math.round(parseFloat(t));   // 숫자만 = 이미 만원
  let v = 0, hit = false;
  const e = t.match(/(\d+(?:\.\d+)?)억/);
  if (e) { v += parseFloat(e[1]) * 10000; hit = true; }
  const ch = t.match(/억(\d+(?:\.\d+)?)천/) || (!e && t.match(/(\d+(?:\.\d+)?)천/));
  if (ch) { v += parseFloat(ch[1]) * 1000; hit = true; }
  const m = t.match(/(\d+(?:\.\d+)?)만/);
  if (m && !ch) { v += parseFloat(m[1]); hit = true; }
  else if (e && !ch) {
    const rest = t.slice(t.indexOf("억") + 1).match(/^(\d+)$/);
    if (rest) { v += Number(rest[1]); hit = true; }      // '10억5000' → 5,000만
  }
  return hit ? Math.round(v) : null;
}
const manText = (v: any) => {
  const n = Number(v);
  return !v || isNaN(n) ? "" : n.toLocaleString();
};
/** 억 단위 되읽기 — 100,000 이 얼마인지 눈으로 확인시켜 준다 */
const manHint = (v: any) => {
  const n = Number(v);
  if (!n || isNaN(n)) return "";
  if (n >= 10000) {
    const e = Math.floor(n / 10000), r = n % 10000;
    return r ? `${e}억 ${r.toLocaleString()}만` : `${e}억`;
  }
  return `${n.toLocaleString()}만`;
};

/** 입력 칸 — 모듈 레벨에 둔다. 컴포넌트 안에서 만들면 렌더마다 새 타입이 되어
 *  글자를 한 자 칠 때마다 다시 그려지고 포커스가 빠진다. */
function T({ f, set, k, label, ...rest }: any) {
  return (
    <label className="pl-f"><span>{label}</span>
      <input className="ai-input" value={f[k] ?? ""} onChange={set(k)} {...rest} /></label>
  );
}

// 단지가 없는 유형 — 이름을 단지 목록에서 찾으면 안 된다('상가'라는 이름의 단지가 실제로 있다)
const PL_NO_COMPLEX = ["상가", "사무실", "단독", "토지", "공장", "건물", "빌딩", "지식산업센터"];
// 지번으로 등록하는 유형 — 빌라는 단지가 없어 '화곡동 123-45' 를 적고 그 건물 몇 호인지를 고른다
const PL_ADDR_FIRST = [...PL_NO_COMPLEX, "빌라", "원룸", "재개발"];

/** 지번 칸 — 주소를 적으면 건축물대장에서 그 건물의 호 목록을 가져와 고르게 한다.
 *  호를 고르면 건물명·전용면적·층·준공이 따라온다. 빌라 등록의 출발점이다. */
function PLAddr({ f, setF, authH }: any) {
  const [units, setUnits] = useState<any[]>([]);
  const [bld, setBld] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const addr = f.address || "";
  const asked = useRef("");

  useEffect(() => {
    const a = addr.trim();
    if (a.length < 6 || asked.current === a) return;
    let dead = false;
    const t = setTimeout(async () => {
      asked.current = a;
      setBusy(true); setMsg("");
      try {
        const r = await fetch(`${API_BASE}/lounge/addr-units?addr=${encodeURIComponent(a)}`,
                              { headers: authH() });
        const d = await r.json();
        if (dead) return;
        if (!r.ok) throw new Error(d?.detail || "조회 실패");
        setUnits(d.units || []); setBld(d.building || null);
        // 표제부는 호를 안 골라도 쓸 수 있다 — 총층수·준공은 광고 필수항목이다
        setF((s: any) => ({ ...s,
          total_floor: s.total_floor || d.building?.total_floor || null,
          approve_ymd: s.approve_ymd || d.building?.use_apr || null }));
        // 건물명을 알면 지번보다 그게 먼저다 — '휴먼빌파크 (송도동 8-3)'
        const bn = (d.building?.bld_name || d.units?.[0]?.bld_name || "").trim();
        setF((s: any) => ({ ...s, complex_name: s.complex_name || bn || null }));
        setMsg((d.units || []).length
          ? `${bn ? `${bn} — ` : ""}건축물대장에서 ${d.units.length}개 호를 찾았어요. 해당 호를 고르세요.`
          : bn ? `${bn} — 등기된 호가 없어요(단독·다가구일 수 있어요). 나머지는 직접 적어 주세요.`
               : "이 지번에는 등기된 호가 없어요(단독·다가구일 수 있어요). 나머지는 직접 적어 주세요.");
      } catch (e: any) {
        if (!dead) { setUnits([]); setBld(null); setMsg(e.message || "조회 실패"); }
      } finally { if (!dead) setBusy(false); }
    }, 700);
    return () => { dead = true; clearTimeout(t); };
  }, [addr]);

  const pick = (u: any) => setF((s: any) => ({ ...s,
    dong: u.dong || s.dong, ho: u.ho,
    area2_m2: u.area_m2 ?? s.area2_m2,
    floor_info: u.floor ? String(u.floor).replace("층", "") : s.floor_info,
    complex_name: s.complex_name || u.bld_name || null }));

  return (
    <>
      <label className="pl-f pl-cx wide"><span>지번 주소</span>
        <input className="ai-input" value={addr} placeholder="예: 서울 강서구 화곡동 123-45"
          onChange={(e) => setF((s: any) => ({ ...s, address: e.target.value }))} />
        {busy && <i className="pl-cxok busy"><Loader2 size={11} className="txm-spin" /></i>}
      </label>
      {msg && <p className={"pl-addrmsg" + (units.length ? "" : " bad")}>{msg}</p>}
      {(bld?.total_floor || bld?.bld_name) && (
        <p className="pl-addrmsg">
          {[bld.bld_name, bld.struct, bld.total_floor ? `지상 ${bld.total_floor}층` : null,
            bld.use_apr ? `${String(bld.use_apr).slice(0, 4)}년 준공` : null,
            bld.households ? `${bld.households}세대` : null].filter(Boolean).join(" · ")}
        </p>
      )}
      {units.length > 0 && (
        <div className="pl-units">
          {units.map((u) => (
            <button type="button" key={`${u.dong || ""}-${u.ho}`}
              className={f.ho === u.ho && (!u.dong || f.dong === u.dong) ? "on" : ""}
              onClick={() => pick(u)}>
              <b>{[u.dong, u.ho].filter(Boolean).join(" ")}</b>
              <span>{[u.area_m2 ? `${u.area_m2}㎡` : null, u.floor,
                      u.purpose].filter(Boolean).join(" · ")}</span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

/** 단지 칸 — 적는 즉시 찾아 확정한다. 이름만 남기면 같은 단지가 표기마다 갈려
 *  폴더도 매칭도 흩어진다. 후보가 여럿일 때만 고르게 한다(고객 요건과 같은 방식). */
function PLComplex({ f, setF, authH }: any) {
  const [hits, setHits] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [all, setAll] = useState(false);
  const [note, setNote] = useState("");
  const name = f.complex_name || "";
  const fixed = !!f.complex_no;
  const off = PL_NO_COMPLEX.includes(f.type || "");
  const take = (h: any) => {
    // 단지가 곧 지역이다 — 주소가 비어 있으면 단지 것으로 채운다
    setF((s: any) => ({ ...s, complex_name: h.complex_name, complex_no: h.complex_no,
      address: s.address || h.region || null }));
    setHits([]); setAll(false);
  };
  useEffect(() => {
    if (off || fixed || name.trim().length < 2) { setHits([]); return; }
    let dead = false;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await fetch(`${API_BASE}/lounge/complex-search?q=${encodeURIComponent(name.trim())}`,
                              { headers: authH() });
        const j = await r.json();
        if (dead) return;
        const got: any[] = j.items ?? [];
        setNote(j.note || "");
        if (got.length === 1) take(got[0]);
        else { setHits(got); setAll(false); }
      } catch { if (!dead) setHits([]); } finally { if (!dead) setBusy(false); }
    }, 350);
    return () => { dead = true; clearTimeout(t); };
  }, [name, fixed, off]);

  const list = all ? hits : hits.slice(0, 6);
  return (
    <label className={"pl-f pl-cx" + (fixed ? " fixed" : "")}>
      <span>{off ? "건물명" : "단지·건물명"}</span>
      <input className="ai-input" value={name} placeholder={off ? "예: 역삼빌딩" : "예: 헬리오시티"}
        onChange={(e) => setF((s: any) => ({ ...s, complex_name: e.target.value, complex_no: null }))} />
      {!off && (fixed
        ? <i className="pl-cxok" title="단지가 확정됐어요"><Check size={11} /></i>
        : busy ? <i className="pl-cxok busy"><Loader2 size={11} className="txm-spin" /></i>
        : hits.length > 0 ? <i className="pl-cxn" title="후보가 여럿이에요">{hits.length}</i>
        : null)}
      {!off && !fixed && hits.length > 0 && (
        <div className="pl-cxdrop" onMouseDown={(e) => e.preventDefault()}>
          <p>{note || "어느 단지인가요?"}</p>
          {list.map((h) => (
            <button type="button" key={h.complex_no} onClick={() => take(h)}>
              <b>{h.complex_name}</b>
              <span>{h.region}{h.households ? ` · ${h.households.toLocaleString()}세대` : ""}</span>
            </button>
          ))}
          {!all && hits.length > list.length && (
            <button type="button" className="more" onClick={() => setAll(true)}>
              후보 {hits.length}곳 모두 보기</button>
          )}
        </div>
      )}
    </label>
  );
}

function PLMoney({ f, setF, k, label }: any) {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft !== null ? draft : manText(f[k]);
  const hint = draft === null ? manHint(f[k]) : "";
  return (
    <label className="pl-f pl-money"><span>{label}<i>만원</i></span>
      <input className="ai-input" value={shown} inputMode="numeric" placeholder="10억 / 100000"
        onChange={(e) => { setDraft(e.target.value); setF((s: any) => ({ ...s, [k]: parseMan(e.target.value) })); }}
        onBlur={() => setDraft(null)} />
      {hint && <b>{hint}</b>}
    </label>
  );
}

function PrivateListingForm({ authH, init, managers, onClose, onSaved }: {
  authH: () => Record<string, string>; init: MLItem | null; managers: Manager[];
  onClose: () => void; onSaved: () => void;
}) {
  const [f, setF] = useState<Record<string, any>>(() => ({
    visibility: "office", trade_type: "매매", type: "아파트",
    ...(init ? { ...init, id: init.private_id } : {}),
  }));
  const [photos, setPhotos] = useState<string[]>(init?.photos || []);
  const [busy, setBusy] = useState(false);
  const [upBusy, setUpBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [editPhoto, setEditPhoto] = useState<string | null>(null);   // 수동 보정 대상
  const [phVer, setPhVer] = useState(0);                             // 보정 후 캐시 무효화
  const [nl, setNl] = useState("");                 // 자연어 한 줄
  const [nlBusy, setNlBusy] = useState(false);
  const [fillBusy, setFillBusy] = useState(false);  // 대장 조회
  const [plMsg, setPlMsg] = useState("");
  const [plMsgBad, setPlMsgBad] = useState(false);
  const [more, setMore] = useState(false);          // 상세 칸 펼침
  const set = (k: string) => (e: any) => setF((s) => ({ ...s, [k]: e.target.value }));

  // 자연어 → 항목. 빈 칸만 채운다(사람이 이미 고친 값을 덮지 않는다).
  const readNl = async () => {
    if (nl.trim().length < 2 || nlBusy) return;
    setNlBusy(true); setPlMsg(""); setPlMsgBad(false);
    try {
      const r = await fetch(`${API_BASE}/lounge/quick-parse`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ text: nl }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "인식 실패");
      const got = (d["매물"] || [])[0];
      if (!got) throw new Error("매물을 못 읽었어요. 단지·동호·가격을 넣어 보세요.");
      // 파서는 원 단위로 낸다. 매물장은 만원 단위라 여기서 옮긴다 —
      // 안 하면 10억이 1000000000(만원)으로 들어간다.
      const MONEY = ["price", "rent_price", "deposit", "maintenance_fee", "loan_amount"];
      setF((s) => {
        const n = { ...s };
        for (const [k, v] of Object.entries(got)) {
          if (k.startsWith("_") || v === null || v === "") continue;
          const val = MONEY.includes(k) && Number(v) >= 10000
            ? Math.round(Number(v) / 10000) : v;
          if (n[k] === undefined || n[k] === null || n[k] === "") n[k] = val;
        }
        return n;
      });
      const auto = Object.keys(got._auto || {});
      setPlMsg(`읽었어요${auto.length ? ` · 대장에서 ${auto.length}개 항목까지 채움` : ""}`);
      setNl("");
    } catch (e: any) { setPlMsg(e.message || "인식 실패"); setPlMsgBad(true); }
    finally { setNlBusy(false); }
  };

  // 단지+동+호가 갖춰지면 건축물대장에서 알아서 채운다 — 눌러야 하는 기능이 아니다.
  // 같은 조합은 한 번만 조회한다(칸을 고칠 때마다 다시 부르지 않게).
  const enriched = useRef("");
  useEffect(() => {
    const key = [f.complex_name, f.dong, f.ho].map((x) => (x || "").trim()).join("|");
    if (!f.complex_name || !f.dong || !f.ho || enriched.current === key) return;
    let dead = false;
    const t = setTimeout(async () => {
      enriched.current = key;
      setFillBusy(true); setPlMsg(""); setPlMsgBad(false);
      try {
        const r = await fetch(`${API_BASE}/lounge/listing-enrich`, {
          method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
          body: JSON.stringify(f),
        });
        const d = await r.json();
        if (dead) return;
        if (!r.ok) throw new Error(d?.detail || "조회 실패");
        // 사람이 적은 값은 덮지 않는다 — 서버가 빈 칸만 채워 돌려준다
        setF((s) => ({ ...s, ...d.listing }));
        const n = (d.filled || []).length;
        setPlMsg(n ? `건축물대장에서 ${n}개 항목을 채웠어요` : "건축물대장에 더 채울 항목이 없었어요");
        setPlMsgBad(!n);
      } catch (e: any) {
        if (!dead) { setPlMsg(e.message || "건축물대장 조회 실패"); setPlMsgBad(true); }
      } finally { if (!dead) setFillBusy(false); }
    }, 800);
    return () => { dead = true; clearTimeout(t); };
  }, [f.complex_name, f.dong, f.ho]);

  const upload = async (file: File) => {
    setUpBusy(true); setMsg("");
    try {
      const fd = new FormData(); fd.append("document", file);
      const r = await fetch(`${API_BASE}/lounge/private-listings/photo`, { method: "POST", headers: authH(), body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "업로드 실패");
      setPhotos((p) => [...p, d.photo]);
      const m = d.masked || {};
      setMsg(`자동 모자이크 적용 — 얼굴 ${m.faces || 0}곳 · 글자 ${m.texts || 0}곳`);
    } catch (e: any) { setMsg(e.message || "업로드 실패"); }
    finally { setUpBusy(false); }
  };
  const onPick = (e: any) => { const fl = [...(e.target.files || [])]; fl.forEach(upload); e.target.value = ""; };

  const save = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/lounge/private-listings`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ ...f, photos }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "저장 실패");
      onSaved();
    } catch (e: any) { alert(e.message || "저장 실패"); }
    finally { setBusy(false); }
  };


  return (
    // 보정 모달은 이 오버레이 **밖**(형제)에 둔다 — 안에 중첩하면 부모의 backdrop-filter 가
    // 컨테이닝 블록이 되어 position:fixed 가 갇히고 화면에 안 보인다(실측).
    <>
    <div className="mld-ov" onClick={onClose}>
      <div className="mld pl-modal" onClick={(e) => e.stopPropagation()}>
        <button className="mld-x" onClick={onClose} aria-label="닫기"><X size={18} /></button>
        <h3 className="mld-title"><Lock size={15} style={{ verticalAlign: "-2px" }} /> 매물 직접등록{f.id ? " 수정" : ""}</h3>
        <p className="pl-hint">한 줄로 적으면 나머지는 우리가 채웁니다. 아는 것만 적고 나중에 보태도 됩니다.</p>

        {/* 칸을 하나씩 채우게 하지 않는다 — 말하듯 적으면 읽어서 넣고, 동·호를 알면 대장에서 긁어온다 */}
        <div className="pl-quick">
          <Sparkles size={15} aria-hidden />
          <input value={nl} placeholder="한마루럭키 104동 1103호 매매 12억 남향 010-1234-5678"
            onChange={(e) => setNl(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); readNl(); } }} />
          <button onClick={readNl} disabled={nlBusy || nl.trim().length < 2}>
            {nlBusy ? <Loader2 size={13} className="txm-spin" /> : "읽기"}</button>
        </div>
        {(fillBusy || plMsg) && (
          <div className="pl-quick2">
            {fillBusy
              ? <span className="pl-qmsg"><Loader2 size={11} className="txm-spin" /> 건축물대장 확인 중…</span>
              : <span className={"pl-qmsg" + (plMsgBad ? " bad" : "")}>{plMsg}</span>}
          </div>
        )}

        <div className="pl-sec">공개 범위</div>
        <div className="pl-vis">
          {([["office", "사무실 전체", "같은 사무소 회원 모두가 봅니다"],
             ["me", "나만 보기", "작성자 본인만 보고 수정할 수 있어요"]] as const).map(([v, t, d]) => (
            <button key={v} className={f.visibility === v ? "on" : ""}
              onClick={() => setF((s) => ({ ...s, visibility: v }))}>
              <b>{t}</b><span>{d}</span>
            </button>
          ))}
        </div>

        <div className="pl-sec">기본</div>
        <div className="pl-grid">
          <label className="pl-f"><span>거래유형</span>
            <select className="ai-input" value={f.trade_type ?? ""} onChange={set("trade_type")}>
              <option value="">선택 안 함</option>
              {PL_TRADES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select></label>
          <label className="pl-f"><span>매물유형</span>
            <select className="ai-input" value={f.type ?? ""} onChange={set("type")}>
              <option value="">선택 안 함</option>
              {PL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select></label>
          {PL_ADDR_FIRST.includes(f.type || "")
            ? <PLAddr f={f} setF={setF} authH={authH} />
            : <PLComplex f={f} setF={setF} authH={authH} />}
          <T f={f} set={set} k="dong" label="동" placeholder="104" />
          <T f={f} set={set} k="ho" label="호" placeholder="1103" />
          <PLMoney f={f} setF={setF} k="price" label="매매가·보증금" />
          <PLMoney f={f} setF={setF} k="rent_price" label="월세" />
          <T f={f} set={set} k="contact" label="연락처" inputMode="tel" placeholder="010-0000-0000" />
        </div>

        {/* 나머지는 대장이 채워 주거나 나중에 보태는 것들이다 — 처음부터 다 보이면 겁먹는다 */}
        <button className="pl-more" onClick={() => setMore((v) => !v)}>
          {more ? "자세히 입력 접기" : "자세히 입력 (면적·구조·주소·융자 등)"}
          <ChevronDown size={13} className={more ? "rot" : ""} aria-hidden />
        </button>
        {more && (<>
        <div className="pl-sec">주소</div>
        <div className="pl-grid">
          <T f={f} set={set} k="building_name" label="동 이름" placeholder="예: 101동" />
          <T f={f} set={set} k="address" label="주소" placeholder="서울 강남구 역삼동 222" />
          <T f={f} set={set} k="address_detail" label="상세주소" />
        </div>

        <div className="pl-sec">가격</div>
        <div className="pl-grid">
          <PLMoney f={f} setF={setF} k="maintenance_fee" label="관리비" />
          <PLMoney f={f} setF={setF} k="loan_amount" label="융자금" />
        </div>

        <div className="pl-sec">면적·구조</div>
        <div className="pl-grid">
          <T f={f} set={set} k="area1_m2" label="공급면적(㎡)" inputMode="decimal" />
          <T f={f} set={set} k="area2_m2" label="전용면적(㎡)" inputMode="decimal" />
          <T f={f} set={set} k="area_name" label="평형" placeholder="84A" />
          <T f={f} set={set} k="floor_info" label="층 정보" placeholder="15/20" />
          <T f={f} set={set} k="room_cnt" label="방 수" inputMode="numeric" />
          <T f={f} set={set} k="bath_cnt" label="욕실 수" inputMode="numeric" />
          <T f={f} set={set} k="direction" label="방향" placeholder="남향" />
          <T f={f} set={set} k="heating" label="난방" placeholder="개별난방" />
          <T f={f} set={set} k="parking" label="주차(대)" inputMode="numeric" />
          <T f={f} set={set} k="elevator" label="엘리베이터" placeholder="있음" />
          <T f={f} set={set} k="settle_ymd" label="잔금시기" placeholder="11월 / 2026-11-20" />
          <T f={f} set={set} k="move_in" label="입주가능일" placeholder="즉시 / 2026-09-01" />
          <T f={f} set={set} k="approve_ymd" label="준공" placeholder="2019.05" />
        </div>
        </>)}

        <div className="pl-sec">소유자·담당</div>
        <div className="pl-grid">
          <T f={f} set={set} k="owner_name" label="소유자" />
          <T f={f} set={set} k="owner_tel" label="소유자 연락처" inputMode="tel" />
          <label className="pl-f"><span>담당자</span>
            <select className="ai-input" value={f.manager ?? ""} onChange={set("manager")}>
              <option value="">미지정</option>
              {managers.map((m) => <option key={m.name} value={m.name}>{m.name}</option>)}
            </select></label>
        </div>

        <div className="pl-sec">설명</div>
        <label className="pl-f"><span>특징</span>
          <textarea className="ai-input" rows={2} value={f.feature_desc ?? ""} onChange={set("feature_desc")}
            placeholder="급매 · 즉시입주 · 올수리" /></label>
        <label className="pl-f"><span>내부 메모</span>
          <textarea className="ai-input" rows={2} value={f.memo ?? ""} onChange={set("memo")}
            placeholder="집주인 오후 연락 선호 등" /></label>

        <div className="pl-sec">사진
          <span className="pl-sec-note">얼굴·간판 글자는 업로드 즉시 자동 모자이크됩니다</span>
        </div>
        <div className="pl-photos">
          {photos.map((p) => (
            <div key={p} className="pl-ph">
              <AuthImg authH={authH} src={`${API_BASE}/lounge/private-listings/photo/${p}?v=${phVer}`}
                onClick={() => setEditPhoto(p)} title="눌러서 보정" />
              <button onClick={() => setPhotos((x) => x.filter((y) => y !== p))} aria-label="삭제"><Trash2 size={12} /></button>
              <span className="pl-ph-edit" onClick={() => setEditPhoto(p)}>보정</span>
            </div>
          ))}
        </div>
        <div className="pl-upl">
          <label className="pl-upbtn">
            <Camera size={14} /> 사진 촬영
            <input type="file" accept="image/*" capture="environment" onChange={onPick} hidden />
          </label>
          <label className="pl-upbtn">
            <Plus size={14} /> 갤러리·파일 선택
            <input type="file" accept="image/*" multiple onChange={onPick} hidden />
          </label>
          {upBusy && <span className="pl-up-busy">모자이크 처리 중…</span>}
        </div>
        {msg && <div className="pl-msg">{msg}</div>}
        <div className="pl-warn">자동 모자이크는 대부분의 얼굴·글자를 가리지만 완전하지 않을 수 있어요.
          올리기 전에 확인해 주세요.</div>

        <div className="pl-actions">
          <button className="pl-save" disabled={busy || upBusy} onClick={save}>{busy ? "저장 중…" : "저장"}</button>
          <button className="pl-cancel" onClick={onClose}>취소</button>
        </div>
      </div>
    </div>
    {editPhoto && <PhotoMaskEditor authH={authH} name={editPhoto}
      onClose={() => setEditPhoto(null)} onDone={() => setPhVer((v) => v + 1)} />}
    </>
  );
}

/** 빈 칸 채우기 — 건축물대장·단지 DB 로 다시 시도한다.
 *  단지가 여러 곳이면 그 자리에서 고르게 한다(엉뚱한 단지를 붙이지 않기 위해). */
function FillInfo({ authH, pid, onDone }: {
  authH: () => Record<string, string>; pid: number; onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [cands, setCands] = useState<{ complex_no: string; name: string; region?: string }[]>([]);
  const run = async (complex_no?: string) => {
    setBusy(true); setMsg("");
    try {
      const r = await fetch(`${API_BASE}/lounge/private-listings/${pid}/enrich`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify(complex_no ? { complex_no } : {}),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || `오류 ${r.status}`);
      setCands(j.cands || []);
      if (j.filled?.length && !j.cands?.length) { setMsg(`${j.filled.length}개 항목을 채웠어요`); onDone(); }
      else if (j.note) setMsg(j.note);
      else setMsg("더 채울 정보가 없어요");
    } catch (e: any) {
      setMsg(e?.message || "실패했어요");
    } finally { setBusy(false); }
  };
  return (
    <div className="mlj-fill">
      <button onClick={() => run()} disabled={busy}>
        {busy ? "채우는 중…" : "건축물대장으로 정보 채우기"}
      </button>
      {msg && <span>{msg}</span>}
      {cands.map((c) => (
        <button key={c.complex_no} className="cand" disabled={busy} onClick={() => run(c.complex_no)}>
          {c.name}
        </button>
      ))}
    </div>
  );
}

function ListingDetail({ l, owner = "", authH, onSavedPrivate, onClose,
  managers = [], onPatch, onSaveNote, saved, onAssign, onToPrivate, privMsg, onFilled,
  onEditPrivate, onDeletePrivate }: {
  l: MLItem; owner?: string; authH?: () => Record<string, string>;
  onSavedPrivate?: () => void; onClose: () => void;
  managers?: { name: string; position?: string }[];
  onPatch?: (k: "contact" | "memo", v: string) => void;
  onSaveNote?: () => void; saved?: boolean;
  onAssign?: (v: string) => void;
  onToPrivate?: (vis: "office" | "me") => void;
  privMsg?: string; onFilled?: () => void;
  onEditPrivate?: () => void; onDeletePrivate?: () => void;
}) {
  const [keepPick, setKeepPick] = useState(false);
  // 네이버 연동매물 → 비공개매물장 보관. 네이버에서 내려가도 사무소가 계속 관리할 수 있게
  // 현재 값을 그대로 떠서 저장한다(복사). 내 사무소 매물에만 노출.
  const [savePick, setSavePick] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [saving, setSaving] = useState(false);
  const canSave = !!authH && !l.is_private && !owner && !!l.article_no;
  const toPrivate = async (visibility: "office" | "me") => {
    if (!authH) return;
    setSaving(true); setSaveMsg("");
    try {
      const r = await fetch(`${API_BASE}/lounge/private-listings/from-naver`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ article_no: l.article_no, visibility }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "저장 실패");
      setSaveMsg(d.duplicated ? "이미 비공개매물장에 있어요." : "비공개매물장에 저장했어요.");
      setSavePick(false);
      onSavedPrivate?.();
    } catch (e: any) { setSaveMsg(e.message || "저장 실패"); }
    finally { setSaving(false); }
  };
  const kakao = l.lat && l.lng ? `https://map.kakao.com/link/map/${encodeURIComponent(l.complex_name || l.building_name || "매물")},${l.lat},${l.lng}` : "";
  const route = l.lat && l.lng ? `https://map.kakao.com/link/to/${encodeURIComponent(l.complex_name || l.building_name || "매물")},${l.lat},${l.lng}` : "";
  const Row = ({ k, v }: { k: string; v: string | null }) => v ? <div className="mld-row"><span className="mld-k">{k}</span><span className="mld-v">{v}</span></div> : null;
  return (
    <div className="mld-ov" onClick={onClose}>
      <div className="mld" onClick={(e) => e.stopPropagation()}>
        <button className="mld-x" onClick={onClose} aria-label="닫기"><X size={18} /></button>
        {owner && <div className="mld-foreign">다른 중개사무소 매물 · {owner}</div>}
        <div className="mld-top">
          <span className={`mlj-trade tr-${l.trade_type}`}>{l.trade_type}</span>
          {l.type && <span className="mlj-type">{l.type}</span>}
          <span className="mld-price">{l.trade_type === "월세" && l.rent_price_text ? `${l.price_text}/${l.rent_price_text}` : l.price_text}</span>
        </div>
        <h3 className="mld-title">{mlName(l)}</h3>
        {l.address && <div className="mld-addr"><MapPin size={13} /> {l.address}</div>}
        <div className="mld-rows">
          <Row k="유형" v={l.type} />
          <Row k="거래" v={l.trade_type === "월세" ? `월세 보증 ${l.price_text} / 월 ${l.rent_price_text}` : `${l.trade_type} ${l.price_text}`} />
          <Row k="잔금시기" v={l.extra?.settle_ymd as string} />
          <Row k="총 층수" v={l.total_floor ? `${l.total_floor}층` : null} />
          <Row k="방·욕실" v={l.room_cnt ? `방 ${l.room_cnt}${l.bath_cnt ? ` / 욕실 ${l.bath_cnt}` : ""}` : null} />
          <Row k="관리비" v={l.maintenance_fee ? `${l.maintenance_fee.toLocaleString()}만원` : null} />
          <Row k="입주가능" v={l.move_in as string} />
          <Row k="승강기" v={l.elevator as string} />
          <Row k="공급면적" v={l.area1_m2 ? `${l.area1_m2}㎡` : null} />
          <Row k="전용면적" v={l.area2_m2 ? areaLabel(l.area2_m2, { supply: l.area1_m2 }) : null} />
          <Row k="평형" v={l.area_name} />
          <Row k="층" v={l.floor_info ? `${l.floor_info}층` : null} />
          <Row k="방향" v={l.direction} />
          <Row k="확인일" v={l.confirm_ymd ? fmtYmd(l.confirm_ymd) : null} />
          <Row k="검증" v={l.verification_type} />
          <Row k="건물명" v={l.building_name} />
          <Row k="동일주소" v={l.same_addr_cnt ? `${l.same_addr_cnt}건 · ${eokWon(l.same_addr_min)} ~ ${eokWon(l.same_addr_max)}` : null} />
          <Row k="세대수" v={l.households ? `${l.households.toLocaleString()}세대` : null} />
          <Row k="세대당 주차" v={l.parking_per ? `${l.parking_per}대${l.parking_total ? ` (총 ${l.parking_total.toLocaleString()}대)` : ""}` : null} />
          <Row k="준공" v={l.approve_ymd ? `${String(l.approve_ymd).slice(0, 4)}.${String(l.approve_ymd).slice(4, 6)}` : null} />
          <Row k="시공사" v={l.builder} />
          <Row k="관리실" v={l.mgmt_tel} />
          <Row k="담당자" v={l.manager} />
          <Row k="연락처" v={l.contact} />
          {/* 비주거 항목 — 저장은 되는데 화면에 안 실려 어디에도 안 보이던 것들.
              상가에 권리금이 없으면 그 매물은 값을 말하지 못하고, 부가세 별도인지
              포함인지에 따라 같은 월세 숫자가 다른 뜻이 된다. Row 는 값이 없으면 스스로 빠진다. */}
          <Row k="권리금" v={l.premium ? eok(l.premium) : null} />
          <Row k="분양 프리미엄" v={l.bunyang_premium ? eok(l.bunyang_premium) : null} />
          <Row k="부가세" v={l.vat_separate ?? null} />
          <Row k="현재 업종" v={l.current_biz ?? null} />
          <Row k="임차 만기" v={l.tenant_until ?? null} />
          <Row k="융자" v={l.loan_amount ? eok(l.loan_amount) : null} />
          <Row k="월 임대수입" v={l.rent_income ? eok(l.rent_income) : null} />
          <Row k="보증금 합계" v={l.deposit_sum ? eok(l.deposit_sum) : null} />
          <Row k="대지면적" v={l.land_area_m2 ? areaLabel(l.land_area_m2) : null} />
          <Row k="연면적" v={l.total_area_m2 ? areaLabel(l.total_area_m2) : null} />
          <Row k="지목" v={l.land_category ?? null} />
          <Row k="용도지역" v={l.land_use ?? null} />
          <Row k="도로" v={l.road_contact ?? null} />
          <Row k="층고" v={l.ceiling_h ? `${l.ceiling_h}m` : null} />
          <Row k="전기용량" v={l.power_kw ? `${l.power_kw}kW` : null} />
          <Row k="주용도" v={l.main_purpose ?? null} />
          <Row k="건폐율·용적률" v={l.bc_rat || l.vl_rat
            ? [l.bc_rat ? `건폐 ${l.bc_rat}%` : "", l.vl_rat ? `용적 ${l.vl_rat}%` : ""].filter(Boolean).join(" · ")
            : null} />
          <Row k="대장 종류" v={l.reg_kind ?? null} />
          <Row k="위반건축물" v={l.violation ?? null} />
        </div>
        {l.tags?.length > 0 && <div className="mlj-tags" style={{ marginTop: 10 }}>{l.tags.map((t, i) => <span key={i}>{t}</span>)}</div>}
        {l.feature_desc && <div className="mld-feat">{l.feature_desc}</div>}

        {/* 담당자·연락처·메모 — 목록에서 뺀 것들이 여기 모인다.
            훑을 땐 안 보이고, 한 건을 볼 땐 다 보이게. */}
        {onPatch && (
          <div className="mld-edit">
            <div className="mld-edit-r">
              <select className="mlj-assign" value={l.manager || ""}
                onChange={(e) => onAssign?.(e.target.value)}>
                <option value="">담당자 미지정</option>
                {managers.map((m) => (
                  <option key={m.name} value={m.name}>
                    {m.name}{m.position === "대표" ? " (대표)" : ""}</option>
                ))}
              </select>
              <input className="mlj-contact" placeholder="연락처(집주인·세입자 등)"
                value={l.contact || ""} inputMode="tel"
                onChange={(e) => onPatch("contact", e.target.value)} />
              {l.contact && (
                <a className="mlj-call" href={`tel:${l.contact.replace(/[^\d+]/g, "")}`}>
                  <Phone size={13} /> 전화</a>
              )}
            </div>
            <div className="mld-edit-r">
              <textarea className="mlj-memo" rows={2} placeholder="메모 (사무소 공유)"
                value={l.memo || ""} onChange={(e) => onPatch("memo", e.target.value)} />
              <button className={"mld-memo-save" + (saved ? " ok" : "")} onClick={onSaveNote}>
                {saved ? "저장됨" : "저장"}</button>
            </div>
            {l.is_private && !l.area2_m2 && (l.complex_name || l.building_name) && authH && (
              <FillInfo authH={authH} pid={l.private_id!} onDone={() => onFilled?.()} />
            )}
            {!l.is_private && onToPrivate && (
              privMsg ? <span className="mlj-keep-ok">{privMsg}</span> : (
                <div className="mlj-fill">
                  <button onClick={() => setKeepPick((v) => !v)}>
                    <Lock size={12} /> 비공개매물장에 보관</button>
                  {keepPick && (
                    <>
                      <button className="cand" onClick={() => onToPrivate("office")}>사무실 전체</button>
                      <button className="cand" onClick={() => onToPrivate("me")}>나만</button>
                    </>
                  )}
                </div>
              )
            )}
          </div>
        )}

        <div className="mld-actions">
          {l.contact && <a className="mlj-call" href={`tel:${l.contact.replace(/[^\d+]/g, "")}`}><Phone size={14} /> 전화</a>}
          {kakao && <a className="mlj-naver" href={kakao} target="_blank" rel="noreferrer"><MapIcon size={14} /> 지도</a>}
          {route && <a className="mlj-naver" href={route} target="_blank" rel="noreferrer"><MapPin size={14} /> 길찾기</a>}
          {l.naver_url && <a className="mlj-naver" href={l.naver_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> 네이버 매물</a>}
          {canSave && <button className="mlj-topriv" onClick={() => setSavePick((v) => !v)}>
            <Lock size={14} /> 비공개매물장에 보관</button>}
          {/* 직접등록한 물건만 고치고 지울 수 있다. 네이버 매물은 수집분이라 우리가 못 지운다 */}
          {l.is_private && onEditPrivate && (
            <button className="mlj-naver" onClick={onEditPrivate}><Pencil size={14} /> 수정</button>
          )}
          {l.is_private && onDeletePrivate && (
            <button className="mld-del" onClick={onDeletePrivate}><Trash2 size={14} /> 삭제</button>
          )}
        </div>
        {savePick && (
          <div className="mld-topriv-pick">
            <div className="mld-topriv-t">누구에게 보이게 할까요?</div>
            <div className="pl-vis">
              <button disabled={saving} onClick={() => toPrivate("office")}>
                <b>사무실 전체</b><span>같은 사무소 회원 모두가 봅니다</span></button>
              <button disabled={saving} onClick={() => toPrivate("me")}>
                <b>나만 보기</b><span>작성자 본인만 보고 수정할 수 있어요</span></button>
            </div>
            <div className="mld-topriv-n">네이버에서 내려가도 비공개매물장에 남아 계속 관리할 수 있어요.</div>
          </div>
        )}
        {saveMsg && <div className="pl-msg" style={{ marginTop: 8 }}>{saveMsg}</div>}
        {l.is_private && l.source_article_no && (
          <div className="mld-srcnote">네이버 매물 {l.source_article_no} 에서 보관됨</div>
        )}
      </div>
    </div>
  );
}


type KReq = {
  id: number; region: string; asset: string; trade: string;
  area: string; budget: string; memo: string; at: string; status: string; offer: KOffer | null;
};

/** 콕집요청 — 손님이 남긴 조건이 우리 사무소로 전달된 것. 연락처는 전달받은 곳만 볼 수 있다. */
export function RequestsTab({ authH }: { authH: () => Record<string, string> }) {
  const [items, setItems] = useState<KReq[]>([]);
  const [hint, setHint] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    fetch(`${API_BASE}/lounge/requests`, { headers: authH() })
      .then((r) => r.json()).then((d) => { setItems(d.items ?? []); setHint(d.suggest_contact || ""); })
      .catch(() => setItems([])).finally(() => setLoading(false));
  }, [authH]);
  useEffect(() => { load(); }, [load]);

  const [openId, setOpenId] = useState<number | null>(null);

  if (loading && items.length === 0) return <Card><p className="muted" style={{ margin: 0 }}>불러오는 중…</p></Card>;
  if (items.length === 0) {
    return (
      <Card>
        <p style={{ margin: 0 }}>아직 전달된 콕집요청이 없습니다.</p>
        <p className="muted" style={{ fontSize: 13, marginTop: 6 }}>
          손님이 콕집에서 원하는 조건을 남기면, 그 동네 사무소로 요청이 전달됩니다.
          매물이 많을수록 더 자주 전달됩니다.
        </p>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          손님이 남긴 조건입니다. <b>손님 연락처는 전달되지 않습니다</b> — 매물을 제안하시면
          손님이 보고 마음에 드는 곳에 직접 연락합니다.
        </p>
      </Card>
      {items.map((r) => (
        <Card key={r.id}>
          <div className="lreq-h">
            <b>{r.region || "지역 미지정"} · {r.asset} {r.trade}</b>
            <span className={`sns-st sns-st-${r.offer ? "done" : "pending"}`}>
              {r.offer ? "제안 보냄" : "새 요청"}
            </span>
          </div>
          <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
            {[r.area, r.budget].filter(Boolean).join(" · ")} · {(r.at || "").slice(5, 16)}
          </div>
          {r.memo && <p style={{ marginTop: 8, fontSize: 14, lineHeight: 1.6 }}>{r.memo}</p>}

          {r.offer && (
            <div className="lreq-mine">
              <b>보낸 제안</b>
              {r.offer.message && <p>{r.offer.message}</p>}
              <div className="muted">연락처 {r.offer.contact} · 매물 {r.offer.listings.length}건</div>
            </div>
          )}

          {openId === r.id ? (
            <div style={{ marginTop: 10 }}>
              <OfferForm
                listUrl={`${API_BASE}/lounge/my-listings`}
                postUrl={`${API_BASE}/lounge/requests/${r.id}/offer`}
                authH={authH}
                existing={r.offer}
                suggestContact={hint}
                onDone={() => { setOpenId(null); load(); }} />
              <button className="lreq-cancel" onClick={() => setOpenId(null)}>닫기</button>
            </div>
          ) : (
            <div className="lreq-btns">
              <button className="lreq-primary" onClick={() => setOpenId(r.id)}>
                {r.offer ? "제안 수정하기" : "매물 제안하기"}
              </button>
            </div>
          )}
        </Card>
      ))}
    </>
  );
}
