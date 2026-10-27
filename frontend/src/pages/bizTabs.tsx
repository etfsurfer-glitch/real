// 중개사 공용 탭 모듈(BizApp이 재사용하는 탭 컴포넌트·타입). 구 /lounge PC 셸
// (default Lounge·LoungeRail)은 통합 셸(/biz)로 흡수돼 제거됐고(2026-09-15),
// 그 정리 후 파일을 Lounge.tsx → bizTabs.tsx 로 리네이밍. 렌더 진입점은 BizApp/App.
import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { Link } from "react-router-dom";
import OfferForm from "../components/OfferForm";
import type { Offer as KOffer } from "../components/OfferForm";
import { Loading } from "../components/Loading";
import ImportListings from "../components/ImportListings";
import {
  ArrowLeft, Award, Building2, Camera, Check, ChevronDown, ChevronRight, Download, ExternalLink, FileSpreadsheet, Flame, Globe, Link2, Loader2, Lock, Map as MapIcon, MapPin, MessageSquare, Minus, Pencil, Phone, Plus, RefreshCw, Search, Share2, SlidersHorizontal, Sparkles, Star, Trash2, TrendingUp, Upload, Users, X,
} from "lucide-react";
import ListingAudit from "../components/ListingAudit";
import OfficeMap from "../components/OfficeMap";
import LoungeCalendarPanel from "../components/LoungeCalendarPanel";
import QuickAdd from "../components/QuickAdd";
import CustomerEdit, { type EditCustomer } from "../components/CustomerEdit";
import { BizTermsConsentModal, bizTermsAgreed } from "../components/BizTermsConsentModal";

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

// 회원 전용 GET. 200 이 아니면 사람이 읽을 수 있는 오류를 던진다.
// 401 응답을 그대로 r.json() 으로 흘려보내면 {detail:...} 이 데이터 자리에 앉아,
// 화면이 빈 채로 멈추거나 매물·상담이 '없음'으로 보인다 — 라운지 입구에서 겪은
// 그 구멍과 같은 모양이다(2026-10-22 전수 점검).
async function authGet<T>(url: string, h: Record<string, string>): Promise<T> {
  const r = await fetch(url, { headers: h });
  if (r.status === 401) throw new Error("세션이 만료됐어요. 다시 로그인해 주세요.");
  if (!r.ok) throw new Error(`불러오지 못했어요 (오류 ${r.status})`);
  return (await r.json()) as T;
}

// 못 불러왔을 때 — 이유를 말하고 다시 시도할 길을 준다.
function LoadError({ msg, onRetry }: { msg: string; onRetry?: () => void }) {
  return (
    <Card>
      <p style={{ margin: 0, fontWeight: 700 }}>{msg}</p>
      {onRetry && (
        <button className="chip" style={{ marginTop: 10, cursor: "pointer" }} onClick={onRetry}>
          다시 시도
        </button>
      )}
    </Card>
  );
}

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

export type Tab = "dashboard" | "listings" | "ledger" | "match" | "calendar" | "contracts" | "wcontracts" | "audit" | "office" | "edit" | "leads" | "homepage" | "staff" | "requests";
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

export function Card({ children }: { children: React.ReactNode }) {
  return <div style={{ border: "1px solid var(--c-border)", borderRadius: 12, padding: 18, maxWidth: 640, display: "grid", gap: 8 }}>{children}</div>;
}

export function DashboardTab({ authH, office, onGoTab }: {
  authH: () => Record<string, string>; office: Office; onGoTab: (t: Tab) => void;
}) {
  const [d, setD] = useState<Dash | null>(null);
  const [dErr, setDErr] = useState("");
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
  const loadDash = useCallback(() => {
    setDErr("");
    authGet<Dash>(`${API_BASE}/lounge/dashboard`, authH())
      .then(setD).catch((e: Error) => { setD(null); setDErr(e.message); });
  }, [authH]);
  useEffect(() => {
    loadDash();
    loadFavs();
    loadOffices();
  }, [loadDash, loadFavs, loadOffices]);

  if (dErr) return <LoadError msg={dErr} onRetry={loadDash} />;
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

// 전화번호에 하이픈 — 010/070 11자리, 02 지역, 그 외 지역번호 10자리. 형식을 못 맞추면(내부번호 등) 원본 그대로.
function fmtPhone(p?: string | null): string {
  const d = (p || "").replace(/[^0-9]/g, "");
  if (d.length === 11 && d.startsWith("0")) return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
  if (d.length === 10 && d.startsWith("02")) return `02-${d.slice(2, 6)}-${d.slice(6)}`;
  if (d.length === 10 && d.startsWith("0")) return `${d.slice(0, 3)}-${d.slice(3, 6)}-${d.slice(6)}`;
  if (d.length === 9 && d.startsWith("02")) return `02-${d.slice(2, 5)}-${d.slice(5)}`;
  return p || "";
}

// 접수시각 짧게 — "2026-09-05 05:40:00" → "09-05 05:40"
function fmtLeadTime(s?: string | null): string {
  if (!s) return "";
  const m = String(s).match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : String(s).slice(0, 16);
}

export function LeadsTab({ authH }: { authH: () => Record<string, string> }) {
  const [items, setItems] = useState<Lead[]>([]);
  const [ldErr, setLdErr] = useState("");
  const load = useCallback(() => {
    setLdErr("");
    authGet<{ items?: Lead[] }>(`${API_BASE}/lounge/leads`, authH())
      .then((d) => setItems(d.items ?? []))
      .catch((e: Error) => setLdErr(e.message));
  }, [authH]);
  useEffect(() => { load(); }, [load]);
  const [regDone, setRegDone] = useState<Record<number, boolean>>({});
  const [custEdit, setCustEdit] = useState<EditCustomer | null>(null);
  const [pendingLead, setPendingLead] = useState<number | null>(null);   // 등록 폼 저장 시 '등록됨' 표시할 리드
  const setStatus = (id: number, status: string) => {
    fetch(`${API_BASE}/lounge/leads/${id}/status`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }).then(() => load());
  };
  // 고객원장 등록 — 그냥 저장하지 않고, 리드 정보로 채운 등록 폼을 띄워 이름·요건을 받는다.
  const toCustomer = async (id: number) => {
    const r = await fetch(`${API_BASE}/lounge/leads/${id}/to-customer`, { method: "POST", headers: authH() });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.customer) { alert(d?.detail || "고객원장 등록에 실패했어요"); return; }
    setPendingLead(id);
    setCustEdit({ id: d.customer.id, name: d.customer.name, phone: d.customer.phone,
      memo: d.customer.memo, needs: [] });
  };
  const delLead = async (id: number) => {
    if (!window.confirm("이 상담신청을 삭제할까요? 되돌릴 수 없어요.")) return;
    const r = await fetch(`${API_BASE}/lounge/leads/${id}`, { method: "DELETE", headers: authH() });
    if (r.ok) load(); else alert("삭제에 실패했어요");
  };
  // 오류를 '없음'으로 보여주면 중개사는 상담이 안 들어온 줄 안다 — 먼저 오류를 말한다.
  if (ldErr) return <LoadError msg={ldErr} onRetry={load} />;
  if (items.length === 0) return <Card><p className="muted" style={{ margin: 0 }}>아직 들어온 상담신청이 없습니다. 홈페이지를 만들면 상담신청이 여기로 쌓입니다.</p></Card>;
  return (
    <div className="lead-list">
      {items.map((l) => (
        <div className="lead-card" key={l.id}>
          <div className="lead-top">
            <span className="ctx-badge" style={leadBadge(l.status)}>{leadKr(l.status)}</span>
            {l.phone
              ? <a className="lead-tel" href={`tel:${l.phone.replace(/[^0-9+]/g, "")}`}>{fmtPhone(l.phone)}</a>
              : <span className="lead-noname">번호 없음</span>}
            <span className="lead-acts">
              {regDone[l.id]
                ? <span className="lead-regok">등록됨</span>
                : <button className="chip lead-reg" onClick={() => toCustomer(l.id)}
                    title="고객원장에 등록">등록</button>}
              {l.status !== "done"
                ? <button className="chip lead-done" onClick={() => setStatus(l.id, "done")}>완료</button>
                : <button className="chip lead-del" onClick={() => delLead(l.id)}
                    title="상담신청 삭제">삭제</button>}
            </span>
          </div>
          <div className="lead-sub">
            <span className="lead-msg">{l.name ? `${l.name} · ` : ""}{l.message ?? "-"}</span>
            {l.created_at && <span className="lead-meta">{fmtLeadTime(l.created_at)}</span>}
          </div>
        </div>
      ))}
      {custEdit && (
        <CustomerEdit authH={authH} cust={custEdit}
          onClose={() => { setCustEdit(null); setPendingLead(null); }}
          onSaved={() => {
            if (pendingLead != null) setRegDone((s) => ({ ...s, [pendingLead]: true }));
            setCustEdit(null); setPendingLead(null);
          }} />
      )}
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
  const [consentApply, setConsentApply] = useState<null | { nm: string; rl: "assoc" | "assist" }>(null);

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
  // 신규가입 번들 — 직원 신청 확정 직전 약관 동의(미동의 시). 관리자·기동의는 통과.
  const apply = (nm: string, rl: "assoc" | "assist") => {
    if (!office || busy) return;
    bizTermsAgreed(authH).then((ok) => { if (ok) doApply(nm, rl); else setConsentApply({ nm, rl }); });
  };
  const doApply = async (nm: string, rl: "assoc" | "assist") => {
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
      {consentApply && (
        <BizTermsConsentModal authH={authH} confirmLabel="동의하고 신청"
          onClose={() => setConsentApply(null)}
          onAgree={() => { const c = consentApply; setConsentApply(null); doApply(c.nm, c.rl); }} />
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
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    authGet<{ members: StaffMember[]; invites: StaffInvite[] }>(`${API_BASE}/lounge/staff`, authH())
      .then((d) => setData({ members: d.members ?? [], invites: d.invites ?? [] }))
      .catch((e: Error) => { setData(null); setErr(e.message); });
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

  if (err) return <LoadError msg={err} onRetry={load} />;
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
  const [hpErr, setHpErr] = useState("");

  const load = useCallback(() => {
    setHpErr("");
    authGet<{ config: HpCfg }>(`${API_BASE}/lounge/homepage`, authH())
      .then((d) => {
        const c: HpCfg = d.config;
        setCfg(c);
        setF({
          slug: c.slug ?? "", slogan: c.slogan ?? "", intro: c.intro ?? "",
          specialties: c.specialties ?? "", biz_hours: c.biz_hours ?? "",
          kakao_url: c.kakao_url ?? "", consult_tel: c.consult_tel ?? office.tel ?? "",
          map_memo: c.map_memo ?? "", published: c.published,
        });
      }).catch((e: Error) => setHpErr(e.message));
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

  if (hpErr) return <LoadError msg={hpErr} onRetry={load} />;
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
  // 직접등록 매물 전용 — 네이버 매물엔 없다. visibility 는 옛 '나만 보기'(새로 안 만든다)
  is_private?: boolean; private_id?: number; visibility?: string; created_by?: string;
  source_article_no?: string; source_saved_at?: string;
  // 어느 매물장에 들어 있는지 — 비공개매물장(대표만) · 내 매물장(담기)
  in_private?: boolean; in_my?: boolean;
  // 같은 물건이 매물장에도 있고 네이버에도 광고 중이면 한 줄에 두 표시가 붙는다
  also_naver?: boolean; naver_article_no?: string;
  // 같은 물건을 CP(제휴 채널)마다 올려 매물번호가 따로 난 광고들 — 대표 줄에 접어 둔다
  ad_dupes?: MLItem[];
  rent_price?: number | null;
  // /biz/my-rank 에서 합쳐 넣는 값 — 매물장 응답을 느리게 하지 않으려고 따로 받는다
  rank_in_group?: number; group_size?: number; expose_left?: number; bump_needed?: boolean;
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


function fmtYmd(s: string) { return s && s.length === 8 ? `${s.slice(4, 6)}/${s.slice(6, 8)}` : s; }
function eok(v: number) {
  if (!v) return "-";
  const e = Math.floor(v / 10000), man = v % 10000;
  return e ? `${e}억${man ? " " + man.toLocaleString() : ""}` : `${v.toLocaleString()}만`;
}
// same_addr_min/max_price는 원 단위(네이버 raw) — 만원으로 환산 후 표기
function eokWon(v: number) { return eok(Math.round((v || 0) / 10000)); }

const ML_CATS = ["", "아파트", "오피스텔", "분양권", "빌라", "상가", "사무실", "단독"];

// ── 매물장 재설계(폴딩·카드) 보조 ─────────────────────────────────────────
/** 유형별 묶음 버킷 — 원천 type 을 사람이 읽는 큰 갈래로 정규화. */
function mlTypeBucket(l: MLItem): string {
  const t = (l.type || "").trim();
  if (t === "아파트") return "아파트";
  if (t === "오피스텔" || t === "분양권") return "오피스텔·분양권";
  if (["빌라", "연립", "다세대", "원룸", "재개발"].includes(t)) return "빌라·원룸";
  if (t === "상가") return "상가";
  if (["사무실", "오피스", "지식산업센터"].includes(t)) return "사무실";
  if (["단독", "다가구", "전원주택"].includes(t)) return "단독·다가구";
  if (["토지", "공장", "건물", "빌딩"].includes(t)) return "토지·건물";
  return t || "기타";
}
/** 카드 스펙 줄 — 전용 · 층 · 방향. */
function mlSpecLine(l: MLItem): string {
  const parts: string[] = [];
  if (l.area2_m2) parts.push(areaLabel(l.area2_m2, { supply: l.area1_m2 }));
  if (l.floor_info) {
    parts.push(`${l.floor_info}${l.total_floor && !String(l.floor_info).includes("/") ? `/${l.total_floor}` : ""}층`);
  }
  if (l.direction) parts.push(l.direction);
  return parts.join(" · ");
}
/** 카드 가격 표기 — 월세는 보증금/월세. */
function mlPriceMain(l: MLItem): string {
  return l.trade_type === "월세" && l.rent_price_text ? `${l.price_text}/${l.rent_price_text}` : l.price_text;
}
/** 어느 매물장에 들어 있는지 — 글자로 적는다. 툴팁에만 두면 폰에서는 확인할 길이 없다. */
function ShelfPills({ l }: { l: MLItem }) {
  return (
    <>
      {l.in_private && <span className="mlj2-src pvt" title="비공개매물장 — 대표만 보입니다">
        <Lock size={10} />비공개</span>}
      {l.in_my && <span className="mlj2-src my" title="내 매물장에 담은 매물">
        <Star size={10} />내 매물장</span>}
      {l.visibility === "me" && <span className="mlj2-src me" title="예전 '나만 보기' — 작성자만 보입니다">
        나만</span>}
    </>
  );
}
/** 출처 뱃지(카드 하단) — SrcIcon 과 같은 규칙, 라벨 달린 알약. */
function SrcPills({ l }: { l: MLItem }) {
  const nv = <span className="mlj2-src nv" title={l.is_private
    ? `네이버에도 광고 중 — 매물번호 ${l.naver_article_no || ""}` : "네이버 — 지금 광고 중"}>
    <Globe size={10} />광고중</span>;
  if (!l.is_private) {
    return <>{nv}<ShelfPills l={l} /></>;
  }
  return (
    <>
      {l.import_file
        ? <span className="mlj2-src im" title={`엑셀에서 가져온 매물 — ${l.import_file}${l.import_at ? ` (${l.import_at})` : ""}`}>
            <FileSpreadsheet size={10} />엑셀</span>
        : <span className="mlj2-src pv" title="콕집에 직접 등록한 매물"><Lock size={10} />직접등록</span>}
      {l.also_naver && nv}
      <ShelfPills l={l} />
    </>
  );
}

// 매물장은 셋이다 — 사무실(소속 전원) · 내 매물장(각자 담아 두는 작업 목록) · 비공개(대표만).
// 한 벌의 매물을 거른 것일 뿐이라 메모·담당·광고 접기는 세 곳에서 똑같이 보인다.
type Shelf = "office" | "my" | "private";
const SHELF_KR: Record<Shelf, string> = {
  office: "사무실 매물장", my: "내 매물장", private: "비공개매물장",
};

export function ListingsTab({ authH, office }: { authH: () => Record<string, string>; office: Office }) {
  const [items, setItems] = useState<MLItem[] | null>(null);
  const [loadErr, setLoadErr] = useState("");
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
  // 표(엑셀) 보기 — 2026-10-06 부터 매물장은 표 하나로 간다(카드·폴딩 제거).
  // 표에서 체크한 줄. 키는 줄의 article_no 다 — 네이버 광고도 골라야 하니(직접등록은 'P<id>').
  // 담기·비공개는 둘 다 되고, 삭제만 직접등록으로 한정된다.
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [pickMode, setPickMode] = useState(false);            // 고르기 모드(담기·비공개·삭제)
  const [shelf, setShelf] = useState<Shelf>("office");      // 지금 보고 있는 매물장
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [isOwner, setIsOwner] = useState(false);            // 비공개는 대표만 다룬다
  // 옮긴 뒤에 '그 매물장으로 갈까요'를 물어본다 — 어디로 갔는지 모르면 옮긴 게 사라진 걸로 보인다
  const [moveAsk, setMoveAsk] = useState<{ to: Shelf; msg: string } | null>(null);
  const [tSort, setTSort] = useState<{ k: string; asc: boolean }>({ k: "unit", asc: true });
  // 엑셀처럼 열마다 거르기 — 서버가 준 items 위에서 바로 건다(요청 때마다 다시 부르지 않는다).
  const [cx, setCx] = useState("");                      // 단지 — 상단에서 고른다
  const [colF, setColF] = useState<Record<string, string[]>>({});
  // 체크박스 드롭다운 — 표가 overflow 컨테이너 안이라 position:fixed 로 띄워야 안 잘린다.
  // 관리자 '사무소로 보기'(?as=<realtor_id>) — 민원 때 그 사무소가 실제로 뭘 보는지 확인한다.
  // 남의 계정으로 들어가는 게 아니라 읽기만 한다. 고치는 기능은 전부 잠근다.
  const asRid = useMemo(() => {
    try { return new URLSearchParams(window.location.search).get("as") || ""; } catch { return ""; }
  }, []);
  const [asName, setAsName] = useState("");
  const ro = !!asRid;                     // 읽기 전용
  const [chkOpen, setChkOpen] = useState<{ k: string; x: number; y: number } | null>(null);
  const [chkQ, setChkQ] = useState("");
  // 건축물대장으로 빈 칸 채우기 — 매물장을 열었을 때 한 번 물어본다.
  const [fillAsk, setFillAsk] = useState(true);
  const [filling, setFilling] = useState<{ done: number; total: number; ok: number } | null>(null);
  const fillStop = useRef(false);
  // 보여줄 열 고르기 — 표가 화면을 넘어가 잘리는 걸 사람이 직접 줄일 수 있게.
  // 처음 열 때는 화면 폭을 보고 정한다(좁으면 부가 열을 접는다). 고른 값은 기기에 남긴다.
  const [cols, setCols] = useState<Record<string, boolean>>(() => {
    try {
      const v = localStorage.getItem("ml.cols");
      if (v) return JSON.parse(v);
    } catch { /* 저장소를 못 쓰는 환경 — 기본값으로 */ }
    return {};
  });
  // 자동 = 표가 들어갈 폭을 실제로 재서 들어가는 만큼 띄운다. 넓은 모니터면 9개 전부 나온다.
  // 예전에는 처음 열 때 innerWidth 를 한 번만 보고 localStorage 에 굳혀서, 창을 넓혀도
  // 안 늘고 좁은 창에서 처음 들어온 사람은 큰 화면에서도 계속 접힌 표를 봤다(2026-10-06 수정).
  const [colAuto, setColAuto] = useState<boolean>(() => {
    try { return localStorage.getItem("ml.colauto") !== "0"; } catch { return true; }
  });
  const [tw, setTw] = useState(0);              // 표가 쓸 수 있는 폭(px)
  const [colsOpen, setColsOpen] = useState(false);
  useEffect(() => {
    try { localStorage.setItem("ml.cols", JSON.stringify(cols)); } catch { /* 무시 */ }
  }, [cols]);
  useEffect(() => {
    try { localStorage.setItem("ml.colauto", colAuto ? "1" : "0"); } catch { /* 무시 */ }
  }, [colAuto]);

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

  // 한 물건을 CP(우리집부동산·부동산뱅크·매경 등)마다 올리면 네이버 매물번호가 따로 생긴다.
  // 중개사 눈에는 똑같은 줄이 둘·셋으로 겹쳐 보인다(실측: 광고 610건 중 겹치는 줄 40조).
  // 지우지 않고 한 줄로 접는다 — 네이버는 호를 주지 않아 '정말 같은 집'인지 단정할 수
  // 없다. 다른 집이 잘못 묶였을 수 있으니 펼쳐 볼 수 있어야 한다.
  const adKey = (l: MLItem) => [l.complex_no, l.building_name, l.trade_type, l.price,
    l.rent_price ?? "", l.area_name, l.floor_info, l.direction].join("|");
  const foldAdDupes = (list: MLItem[]): MLItem[] => {
    const g = new Map<string, MLItem[]>(); const order: string[] = [];
    for (const l of list) {
      // 매물장 매물(직접등록·엑셀)은 손대지 않는다 — CP 중복이라는 개념이 없다
      const k = l.is_private ? `P${l.article_no}` : adKey(l);
      if (!g.has(k)) { g.set(k, []); order.push(k); }
      g.get(k)!.push(l);
    }
    return order.map((k) => {
      const v = g.get(k)!;
      if (v.length === 1) return v[0];
      const srt = [...v].sort((a, b) => (b.confirm_ymd || "").localeCompare(a.confirm_ymd || ""));
      return { ...srt[0], ad_dupes: srt.slice(1) };   // 확인일이 가장 최근인 광고가 대표
    });
  };
  const rawRef = useRef<MLItem[]>([]);
  const [foldAds, setFoldAds] = useState(true);
  // load 는 useCallback 이라 foldAds 를 그대로 읽으면 옛 값이 박힌다 — '펼침'으로 바꾼 뒤
  // 필터를 건드리면 다시 접힌 채로 돌아온다(버튼 글자와 화면이 어긋난다). ref 로 읽는다.
  const foldRef = useRef(true);
  // 순위·광고 잔여일은 /biz/my-rank 가 계산한다. 자동으로 부르지 않는다 — 한 단지의
  // 등수를 내려면 그 단지의 **모든 중개사 매물**을 읽어야 해서, 77개 단지를 다루는
  // 사무소면 매물장을 열 때마다 77개 단지를 통째로 읽게 된다.
  // 버튼을 눌렀을 때 **화면에 보이는 줄의 단지만** 점검한다.
  const [rankBy, setRankBy] = useState<Record<string, any>>({});
  const [rankBusy, setRankBusy] = useState(false);
  const [rankMsg, setRankMsg] = useState("");

  const load = useCallback(() => {
    setBusy(true); setForeign(null); setLookErr("");
    const p = new URLSearchParams({ q, trade, cat, manager, sort, shelf,
      private: priv || privOnly ? "1" : "0", private_only: privOnly ? "1" : "0" });
    if (asRid) p.set("as_realtor", asRid);
    setLoadErr("");
    authGet<{ listings?: MLItem[]; as_realtor?: string; realtor_name?: string;
              counts?: Record<string, number>; is_owner?: boolean }>(
      `${API_BASE}/lounge/listings?${p}`, authH())
      .then((d) => {
        const list: MLItem[] = d.listings || [];
        rawRef.current = list;
        setItems(foldRef.current ? foldAdDupes(list) : list);
        if (d.counts) setCounts(d.counts);
        setIsOwner(!!d.is_owner);
        if (d.as_realtor) setAsName(d.realtor_name || asRid);
        // 내 매물장에 없고 매물번호 형태면 → 남의 물건인지 조회
        const an = q.trim();
        if (list.length === 0 && /^\d{6,}$/.test(an)) lookup(an);
      })
      .catch((e: Error) => { setItems(null); setLoadErr(e.message); })
      .finally(() => setBusy(false));
  }, [authH, q, trade, cat, manager, sort, priv, privOnly, shelf, lookup]);
  useEffect(() => { load(); }, [trade, cat, manager, sort, priv, privOnly, shelf]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // 고른 줄을 비공개매물장·내 매물장으로 넣고 뺀다. 네이버 광고도 대상이다 —
  // 콕집 화면에서만 옮겨지고 네이버에 올라간 광고는 손대지 않는다.
  const shelfSet = async (to: "private" | "my", action: "add" | "remove") => {
    const nos = [...sel];
    if (!nos.length) return;
    if (to === "private" && action === "add" && !window.confirm(
      `${nos.length}건을 비공개매물장으로 보냅니다.\n\n` +
      `사무실 매물장·사무소 지도·손님 매칭에서 빠지고 대표만 보게 됩니다.\n` +
      `네이버에 올라간 광고는 그대로 남습니다.`)) return;
    try {
      const r = await fetch(`${API_BASE}/lounge/listings/shelf`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ shelf: to, action, article_nos: nos }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || `바꾸지 못했어요 (${r.status})`);
      const n = d?.n ?? nos.length;
      setSel(new Set()); setPickMode(false); load();
      setMoveAsk(action === "add"
        ? { to, msg: `${n}건을 ${SHELF_KR[to]}으로 보냈어요.` }
        : { to: shelf, msg: `${n}건을 ${SHELF_KR[to]}에서 뺐어요.` });
    } catch (e: any) { alert(e?.message || "바꾸지 못했어요"); }
  };

  const [focusKey, setFocusKey] = useState<string | null>(null);   // 큰 폴더 전체보기
  const [sheetOpen, setSheetOpen] = useState(false);               // 필터 바텀시트
  // 자동 묶음: 비단지(빌라·상가·사무실 등)가 절반 넘으면 유형별, 아니면 단지별
  const autoMode: "complex" | "type" = useMemo(() => {
    const list = items || [];
    if (!list.length) return "complex";
    return list.filter(isAddrFirst).length > list.length / 2 ? "type" : "complex";
  }, [items]);
  const mode = autoMode;

  // 같은 단지(또는 같은 유형) 물건을 한 덩어리로 — 정렬 순서는 두고 첫 등장 자리에 모은다.
  const groups = useMemo(() => {
    const by = new Map<string, MLItem[]>();
    const order: string[] = [];
    for (const l of items || []) {
      const k = mode === "type"
        ? `T:${mlTypeBucket(l)}`
        : (isAddrFirst(l) ? (l.address || `#${l.article_no}`)
                          : (l.complex_no || l.complex_name || `#${l.article_no}`));
      if (!by.has(k)) { by.set(k, []); order.push(k); }
      by.get(k)!.push(l);
    }
    return order.map((k) => ({ key: k, items: by.get(k)! }));
  }, [items, mode]);
  // 묶음이 바뀌면 펼침/포커스 초기화
  useEffect(() => { setFocusKey(null); }, [mode]);

  const groupName = (g: MLItem[]) => mode === "type" ? mlTypeBucket(g[0]) : mlName(g[0]);
  // 활성 필터 개수(시트 뱃지)
  const activeFilters = (trade ? 1 : 0) + (cat ? 1 : 0) + (manager ? 1 : 0) + (privOnly || !priv ? 1 : 0);
  const focusGroup = focusKey ? groups.find((g) => g.key === focusKey) : null;

  // 매물 카드 하나
  const Card = (l: MLItem, showName: boolean) => (
    <div key={l.article_no} className={`mlj2-card tr-${l.trade_type}`}
      onClick={() => { setDetailOwner(""); setDetail(l); }}>
      <div className="mlj2-c-top">
        <i className={`mlj2-badge b-${l.trade_type}`}>{l.trade_type}</i>
        <div className="mlj2-c-mid">
          <div className="mlj2-c-unit">
            {showName && <span className="mlj2-c-nm" title={isAddrFirst(l) ? (l.address || "") : ""}>{mlName(l)}</span>}
            {unitOf(l) !== "-"
              ? <span>{unitOf(l)}</span>
              : (!showName && <span className="mlj2-c-nm">{mlName(l)}</span>)}
          </div>
          {mlSpecLine(l) && <div className="mlj2-c-spec">{mlSpecLine(l)}</div>}
        </div>
        <div className="mlj2-c-price">
          {mlPriceMain(l)}{l.trade_type === "전세" && <small>보증금</small>}
        </div>
      </div>
      <div className="mlj2-c-meta">
        <SrcPills l={l} />
        {l.manager && <span className="mlj2-mgr"><i className="mlj2-av">{l.manager[0]}</i>{l.manager}</span>}
        {l.settle_ymd && <span className="mlj2-dday">잔금 {fmtYmd(l.settle_ymd)}</span>}
        {l.ad_check && (l.ad_check.missing?.length || 0) > 0 &&
          <span className="mlj2-chk">점검 {l.ad_check.missing.length}건</span>}
      </div>
    </div>
  );

  // 표에 뿌릴 행 — 필터는 서버가 걸러 준 items 를 그대로 쓰고 여기서는 정렬만 한다.
  const num = (v?: string | null) => { const m = String(v || "").match(/\d+/); return m ? +m[0] : 0; };
  // 열마다 고를 수 있는 값 — 지금 불러온 매물에서 실제로 쓰인 것만 세운다.
  // dong 칸에는 두 가지가 섞여 들어온다 — 아파트 '101동'(건물 동)과 '송도동'(법정동).
  // 원천이 그렇게 생겼다(네이버 비단지 매물은 법정동을 dong 에 담는다). 거르는 칸을 둘로 가른다.
  // 건물 동 판정 — '101동'·'A동'·'가동'은 건물 동, '송도동'·'안서동'은 법정동.
  // 가르는 기준은 **동 앞 글자 수**다. 법정동은 두 음절 이상이고(한 음절짜리 법정동은 없다)
  // 건물 동은 숫자이거나 한 글자다. 숫자로만 보면 A동·가동을 법정동으로 오인한다(2026-10-06).
  const BLD_DONG = /^(\d+(?:-\d+)?|[A-Za-z]|[가-힣])\s*동?$/;
  const isBldDong = (v: string) => BLD_DONG.test(v.trim());
  // 표의 '동·호' 칸은 건물 동만 세운다. 법정동('송도동')이 같은 칸에 섞여 나오면
  // 101동과 송도동이 한 줄에 뒤섞여 무엇을 가리키는지 알 수 없다(2026-10-06 지적).
  // 법정동은 단지명·주소가 이미 알려 주므로 여기서 또 쓰지 않는다.
  // 단지형(아파트·오피스텔)은 네이버 building_name 이 곧 '101동'이다 — 상세의 '건물명' 칸과
  // 같은 값이다. dong 이 비어 '—'로 남던 줄을 여기서 채운다(2026-10-06 요청).
  // 비단지는 building_name 이 '일반상가' 같은 유형 딱지라 쓰지 않는다.
  const bldDongOf = (l: MLItem) => {
    const v = (l.dong || "").trim();
    if (isBldDong(v)) return v;
    if (!isAddrFirst(l)) { const b = (l.building_name || "").trim(); if (isBldDong(b)) return b; }
    return "";
  };
  const floorCell = (l: MLItem) => {
    if (!l.floor_info) return "";
    const tot = l.total_floor && !String(l.floor_info).includes("/") ? `/${l.total_floor}` : "";
    return `${l.floor_info}${tot}층`;
  };
  const unitCell = (l: MLItem) => {
    const d = bldDongOf(l), h = (l.ho || "").trim();
    const dd = d ? (/동$/.test(d) ? d : `${d}동`) : "";
    const hh = h ? (/호$/.test(h) ? h : `${h}호`) : "";
    return [dd, hh].filter(Boolean).join(" ") || "";
  };
  // 법정동만 띄우면 어느 동네인지 가릴 수 없다 — 같은 이름의 동이 전국에 여럿이고,
  // 동 바로 위가 구인 곳도 있고(서초구 양재동) 시인 곳도 있다(김포시 북변동).
  // 주소에서 동 앞 토막을 붙여 '서초구 양재동'으로 보여 준다(2026-10-26 지적).
  // 주소를 못 받은 매물은 종전대로 동만 쓴다. 선택지와 거르기가 이 함수 하나를 쓰므로
  // 표기를 바꿔도 어긋나지 않는다.
  const areaDongOf = (l: MLItem) => {
    const v = (l.dong || "").trim();
    if (!v || isBldDong(v)) return "";
    const parts = (l.address || "").trim().split(/\s+/);
    const i = parts.indexOf(v);
    const up = i > 0 ? parts[i - 1] : "";
    return up && up !== v ? `${up} ${v}` : v;
  };
  // 열 머리 필터 가운데 "값이 같으냐"로 안 되는 것들 — 파생값(출처)·유무(연락처·메모)·구간(가격).
  // price 는 원 단위다(API 가 price_man = price/10000 로 함께 내려준다).
  const PRICE_BANDS: [string, number, number][] = [
    ["1억 미만", 0, 1e8], ["1~3억", 1e8, 3e8], ["3~5억", 3e8, 5e8],
    ["5~10억", 5e8, 10e8], ["10~20억", 10e8, 20e8], ["20억 이상", 20e8, Infinity],
  ];
  const COLPRED: Record<string, (l: MLItem, v: string) => boolean> = {
    // 광고중은 "네이버 매물"과 "매물장에 있고 네이버에도 광고 중"을 함께 잡는다(뱃지와 같은 규칙).
    src: (l, v) => v === "광고중" ? (!l.is_private || !!l.also_naver)
                 : v === "엑셀" ? !!l.import_file
                 : !!l.is_private && !l.import_file,
    // 접힌 광고의 CP 까지 본다. 대표만 보면 '부동산뱅크'로 걸러도 접힌 줄이 빠진다.
    cp_name: (l, v) => [l, ...(l.ad_dupes || [])].some((x) => (x.cp_name || "") === v),
    contact_has: (l, v) => (v === "있음") === !!(l.contact || "").trim(),
    memo_has: (l, v) => (v === "있음") === !!(l.memo || "").trim(),
    price_band: (l, v) => {
      const b = PRICE_BANDS.find((x) => x[0] === v);
      return !!b && (l.price || 0) >= b[1] && (l.price || 0) < b[2];
    },
  };

  // 한 열의 값을 꺼내는 규칙 — 거르기와 선택지 만들기가 같은 규칙을 써야 어긋나지 않는다.
  const colVal = (k: string, l: MLItem) =>
    k === "dong" ? bldDongOf(l)
    : k === "areaDong" ? areaDongOf(l)
    : k === "supply" ? String(l.area1_m2 || "")
    : k === "excl" ? String(l.area2_m2 || "")
    : k === "floor" ? String(l.floor_info || "")
    : String((l as any)[k] || "");

  // 걸린 조건을 적용한다. skip 을 주면 그 열의 조건만 빼고 적용한다
  // (엑셀처럼 — 자기 열의 선택지는 자기 조건에 깎이면 안 된다).
  const applyColF = (list: MLItem[], skip?: string) => {
    for (const [k, vs] of Object.entries(colF)) {
      if (!vs || !vs.length || k === skip) continue;
      const pred = COLPRED[k];
      if (pred) { list = list.filter((l) => vs.some((v) => pred(l, v))); continue; }
      list = list.filter((l) => vs.includes(colVal(k, l)));
    }
    return list;
  };

  // 단지를 고르면 그 단지 안에서만 선택지를 만든다 — 전체 기준으로 만들면
  // 다른 단지의 동·평형이 떠서 고르면 0건이 된다(2026-10-06 지적).
  // 단지를 바꾸면 열 조건을 비운다 — 앞 단지의 '103동'이 남아 있으면 새 단지에선 0건이 된다.
  // 조건이 바뀌면 삭제 선택을 비운다. 안 그러면 3건을 고른 뒤 필터를 바꿔 그 줄이
  // 화면에서 사라져도 선택은 남아, 보이지 않는 매물이 지워진다(확인창의 목록도 어긋난다).
  useEffect(() => { setSel(new Set()); }, [cx, colF, q, trade, cat, manager, priv, privOnly, shelf]);

  const cxPrev = useRef(cx);
  useEffect(() => {
    if (cxPrev.current !== cx) { cxPrev.current = cx; setColF({}); setChkOpen(null); }
  }, [cx]);

  const base = useMemo(() => (cx ? (items || []).filter((l) => mlName(l) === cx) : (items || [])),
                       [items, cx]);

  const opts = useMemo(() => {
    const srt = (a: string, b: string) => { const x = num(a), y = num(b);
      return (x || y) && x !== y ? x - y : a.localeCompare(b, "ko"); };
    const pick = (f: (l: MLItem) => string, skip?: string) =>
      [...new Set(applyColF(base.slice(), skip).map(f).filter(Boolean))].sort(srt);
    const has = (k: string, v: string) => applyColF(base.slice(), k).some((l) => COLPRED[k](l, v));
    return {
      // 단지 목록만은 전체 기준이다 — 그래야 다른 단지로 옮겨 갈 수 있다
      cx: [...new Set((items || []).map(mlName).filter(Boolean))].sort(srt),
      trade_type: pick((l) => l.trade_type || "", "trade_type"),
      dong: pick(bldDongOf, "dong"),
      areaDong: pick(areaDongOf, "areaDong"),
      area_name: pick((l) => l.area_name || "", "area_name"),
      direction: pick((l) => l.direction || "", "direction"),
      manager: pick((l) => l.manager || "", "manager"),
      cp_name: [...new Set(applyColF(base.slice(), "cp_name")
        .flatMap((l) => [l, ...(l.ad_dupes || [])]).map((x) => x.cp_name || "").filter(Boolean))].sort(srt),
      src: ["광고중", "엑셀", "직접등록"].filter((v) => has("src", v)),
      priceBand: PRICE_BANDS.map((b) => b[0]).filter((v) => has("price_band", v)),
      contactHas: ["있음", "없음"].filter((v) => has("contact_has", v)),
      memoHas: ["있음", "없음"].filter((v) => has("memo_has", v)),
    };
  }, [items, cx, colF]);

  const rows = useMemo(() => {
    const list = applyColF(base.slice());
    const dir = tSort.asc ? 1 : -1;
    const k = tSort.k;
    return list.sort((a, b) => {
      if (k === "price") return ((a.price || 0) - (b.price || 0)) * dir;
      if (k === "unit") {                      // 법정동은 숫자가 없어 0 으로 묶인다(의도)
        const d = num(bldDongOf(a)) - num(bldDongOf(b)); if (d) return d * dir;
        return (num(a.ho) - num(b.ho)) * dir;
      }
      if (k === "name") return mlName(a).localeCompare(mlName(b), "ko") * dir;
      if (k === "supply") return ((a.area1_m2 || 0) - (b.area1_m2 || 0)) * dir;
      if (k === "excl") return ((a.area2_m2 || 0) - (b.area2_m2 || 0)) * dir;
      if (k === "floor") return (num(a.floor_info) - num(b.floor_info)) * dir;
      if (k === "rank") return ((bestRank(a)?.rank_in_group ?? 10 ** 9)
                              - (bestRank(b)?.rank_in_group ?? 10 ** 9)) * dir;
      if (k === "left") return ((soonLeft(a) ?? 10 ** 9) - (soonLeft(b) ?? 10 ** 9)) * dir;
      if (k === "src") {
        // 'src' 라는 칸은 없다. 뱃지를 만드는 규칙(SrcPills)과 같은 값으로 정렬해야
        // 머리글을 눌렀을 때 실제로 줄이 움직인다(전에는 전부 "" 라 꿈쩍도 안 했다).
        const g = (x: MLItem) => (!x.is_private ? "1광고중" : x.import_file ? "2엑셀" : "3직접등록");
        return g(a).localeCompare(g(b), "ko") * dir;
      }
      if (k === "area_name") {               // '110' 이 '59' 보다 뒤여야 한다
        const d2 = num(a.area_name) - num(b.area_name);
        if (d2) return d2 * dir;
      }
      return String((a as any)[k] || "").localeCompare(String((b as any)[k] || ""), "ko") * dir;
    });
  }, [base, tSort, colF, rankBy]);

  // 열 머리 아래 드롭다운 한 칸 — 고른 값만 남긴다(엑셀 자동필터와 같은 쓰임).
  const colSel = (k: string, list: string[], label?: string) => (
    <select className={"mlt-fsel" + (colF[k]?.length ? " on" : "")} value={colF[k]?.[0] || ""}
      aria-label={`${label || k} 거르기`}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => setColF((f) => ({ ...f, [k]: e.target.value ? [e.target.value] : [] }))}>
      <option value="">{label || "전체"}</option>
      {list.map((v) => <option key={v} value={v}>{v}</option>)}
    </select>
  );
  // 여러 개 고르는 필터(네이버 동·타입 선택과 같은 방식). 고른 개수를 버튼에 적는다.
  const colChk = (k: string, label: string) => {
    const cur = colF[k] || [];
    return (
      <button className={"mlt-fsel mlt-fchk" + (cur.length ? " on" : "")}
        aria-label={`${label} 거르기`}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation();
          setChkQ("");
          if (chkOpen?.k === k) { setChkOpen(null); return; }
          const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
          setChkOpen({ k, x: Math.min(r.left, window.innerWidth - 212), y: r.bottom + 4 });
        }}>
        {cur.length ? `${label} ${cur.length}` : label}<ChevronDown size={11} aria-hidden />
      </button>
    );
  };
  // 실제로 그릴 열. 순서는 동·호를 앞으로 — 가로로 밀려도 왼쪽에 '어느 집인지'가 남는다.
  const ALLCOLS: [string, string][] = [
    ["trade_type", "거래"], ["unit", "동·호"], ["name", "단지·건물"],
    // 면적은 쪼개 둔다 — 한 칸에 묶으면 공급·전용이 안 보이고 정렬·거르기도 못 한다(2026-10-06 요청).
    ["area_name", "평형"], ["supply", "공급"], ["excl", "전용"], ["floor", "층"], ["direction", "향"],
    ["price", "가격"], ["rank", "순위"], ["left", "광고잔여"], ["src", "출처"], ["cp_name", "광고채널"],
    ["manager", "담당자"], ["contact", "연락처"], ["memo", "메모"], ["act", "수정"],
  ];
  const ALWAYS = new Set(["trade_type", "unit", "price", "act"]);   // 이 넷은 끌 수 없다

  // 열이 실제로 차지하는 최소 폭(px). 좁은 화면에서는 글자·여백이 줄어 함께 줄인다.
  const COLW: Record<string, number> = { trade_type: 56, unit: 94, name: 180,
                                         area_name: 88, supply: 106, excl: 106, floor: 84, direction: 74,
                                         price: 124, rank: 96, left: 92, src: 104, cp_name: 112, manager: 112,
                                         contact: 128, memo: 170, act: 48 };
  // 자리가 모자랄 때 접는 순서의 거꾸로 — 앞쪽이 먼저 살아남는다.
  const COLPRIO = ["name", "excl", "floor", "area_name", "supply", "direction",
                   "rank", "left", "contact", "src", "cp_name", "manager", "memo"];
  const autoCols = useMemo(() => {
    const dense = tw > 0 && tw < 900 ? 0.86 : 1;         // CSS 와 같은 구간에서 패딩이 줄어든다
    const w = (k: string) => COLW[k] * dense;
    const on: Record<string, boolean> = {};
    // 거래·동·호·가격은 늘 보이고, 단지명도 단지를 고르지 않았다면 뺄 수 없다.
    let used = w("trade_type") + w("unit") + w("price") + w("act") + (pickMode ? 40 : 0);
    if (!cx) { on.name = true; used += w("name"); }
    for (const k of COLPRIO) {
      if (k === "name") continue;
      if (tw > 0 && used + w(k) > tw) continue;          // 안 들어가면 접는다
      on[k] = true; used += w(k);
    }
    return on;
  }, [tw, cx, pickMode]);

  const effCols = colAuto ? autoCols : cols;
  // 표 최소폭도 고른 열에 맞춘다. CSS 에 760px 을 박아 두면 폰에서 자동 맞춤이 무의미해진다
  // (열을 접어도 760px 로 늘어나 결국 가로로 넘친다).
  const minW = useMemo(() => {
    const dense = tw > 0 && tw < 900 ? 0.86 : 1;
    const ks = ALLCOLS.map(([k]) => k).filter((k) =>
      ALWAYS.has(k) ? true
      : k === "name" ? !cx && effCols.name !== false
      : colAuto ? !!effCols[k] : effCols[k] !== false);
    return Math.round(ks.reduce((a, k) => a + COLW[k] * dense, 0) + (pickMode ? 40 : 0));
  }, [tw, cx, pickMode, colAuto, effCols]);
  const VIEWCOLS = ALLCOLS.filter(([k]) =>
    ALWAYS.has(k) ? true
    : k === "name" ? !cx && effCols.name !== false      // 단지를 골랐으면 단지 열은 군더더기
    : colAuto ? !!effCols[k] : effCols[k] !== false);

  const colFilterCount = Object.values(colF).filter((a) => a && a.length).length + (cx ? 1 : 0);
  const clearColF = () => { setColF({}); setCx(""); setChkOpen(null); };

  // 표를 끌어서 좌우로 민다 + 오른쪽에 더 있다는 표시.
  // 가로 스크롤막대는 눈에 잘 안 띄어 "오른쪽이 없는 줄 안다"는 지적이 있었다(2026-10-06).
  // 손가락은 원래 스크롤이 되므로 마우스일 때만 끌기를 건다.
  const wrapRef = useRef<HTMLDivElement>(null);
  const outerRef = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef({ on: false, x: 0, left: 0, moved: false });
  const [edge, setEdge] = useState<{ l: boolean; r: boolean }>({ l: false, r: false });

  const syncEdge = useCallback(() => {
    const el = wrapRef.current; if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    setEdge({ l: el.scrollLeft > 4, r: max > 4 && el.scrollLeft < max - 4 });
    // clientWidth 는 스크롤막대가 생겼다 없어질 때 값이 흔들려 열이 깜빡인다. offsetWidth 로 고정.
    setTw(Math.max(0, el.offsetWidth - 18));
  }, []);
  useEffect(() => {
    syncEdge();
    const el = wrapRef.current; if (!el) return;
    const ro = new ResizeObserver(syncEdge);
    ro.observe(el);
    return () => ro.disconnect();
  }, [syncEdge, rows.length, VIEWCOLS.length, cx, pickMode]);

  const onDragDown = (e: React.PointerEvent) => {
    if (e.pointerType !== "mouse") return;            // 터치는 기본 스크롤에 맡긴다
    const el = wrapRef.current; if (!el) return;
    dragRef.current = { on: true, x: e.clientX, left: el.scrollLeft, moved: false };
    hideTip();
  };
  const hideTip = () => { const t = tipRef.current; if (t) t.style.opacity = "0"; };
  const moveTip = (e: React.PointerEvent) => {
    const t = tipRef.current, box = outerRef.current;
    if (!t || !box) return;
    // 끌 수 있을 때만, 마우스일 때만, 끌고 있지 않을 때만 보여준다.
    if (e.pointerType !== "mouse" || dragRef.current.on || (!edge.l && !edge.r)) { hideTip(); return; }
    const r = box.getBoundingClientRect();
    t.style.left = e.clientX - r.left + "px";
    t.style.top = e.clientY - r.top + "px";
    t.style.opacity = "1";
  };

  const onDragMove = (e: React.PointerEvent) => {
    moveTip(e);
    const d = dragRef.current; const el = wrapRef.current;
    if (!d.on || !el) return;
    const dx = e.clientX - d.x;
    if (Math.abs(dx) > 4) d.moved = true;
    el.scrollLeft = d.left - dx;
  };
  const onDragUp = () => { dragRef.current.on = false; };
  const nudge = (dir: number) => {
    const el = wrapRef.current; if (!el) return;
    el.scrollBy({ left: dir * Math.max(200, el.clientWidth * 0.6), behavior: "smooth" });
  };

  const sortBy = (k: string) =>
    setTSort((s2) => (s2.k === k ? { k, asc: !s2.asc } : { k, asc: true }));

  // 선택 삭제 — 되돌릴 수 없다. 무엇을 지우는지 보여 주고 두 번 확인받는다.
  const deleteSelected = async () => {
    // 지울 수 있는 건 직접등록뿐 — 네이버 광고는 수집분이라 우리가 못 지운다
    const picked = rows.filter((l) => sel.has(l.article_no) && l.private_id);
    const ids = picked.map((l) => l.private_id as number);
    if (!ids.length) { alert("고른 것 중 지울 수 있는 매물(직접등록)이 없어요."); return; }
    const names = picked.slice(0, 5).map((l) => `· ${mlName(l)} ${unitOf(l)}`).join("\n");
    if (!window.confirm(
      `매물장에서 ${ids.length}건을 지웁니다.\n\n${names}` +
      (ids.length > 5 ? `\n· 외 ${ids.length - 5}건` : "") +
      `\n\n네이버에 광고 중인 매물은 그대로 남습니다.`)) return;
    if (!window.confirm(
      `정말 지울까요?\n\n한 번 지우면 되돌릴 수 없습니다.\n` +
      `${ids.length}건을 삭제하려면 확인을 눌러 주세요.`)) return;
    try {
      const r = await fetch(`${API_BASE}/lounge/private-listings/bulk-close`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ ids }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || `지우지 못했어요 (${r.status})`);
      if (d?.blocked) alert(`${d.closed}건을 지웠습니다.\n(${d.blocked}건은 다른 분의 개인 매물이라 남겼습니다)`);
      setSel(new Set()); setPickMode(false); load();
    } catch (e: any) { alert(e?.message || "지우지 못했어요"); }
  };

  // 지금 보이는 그대로 엑셀로 — 필터·정렬이 반영된 행만 담는다.
  // 접힌 CP 광고까지 본다 — 표·정렬·엑셀받기가 **같은 규칙**을 써야 숫자가 어긋나지 않는다.
  const bestRank = (l: MLItem) =>
    [l, ...(l.ad_dupes || [])].map((x) => rankBy[x.article_no]).filter(Boolean)
      .sort((a, b) => (a.rank_in_group || 99) - (b.rank_in_group || 99))[0];
  const soonLeft = (l: MLItem) => {
    const v = [l, ...(l.ad_dupes || [])].map((x) => rankBy[x.article_no]?.expose_left)
      .filter((x) => x != null) as number[];
    return v.length ? Math.min(...v) : null;
  };

  // 화면에 보이는 줄만 점검한다. 접힌 CP 광고도 함께 — 채널마다 등수가 다르다.
  const checkRank = async () => {
    const vis = rows.flatMap((l) => [l, ...(l.ad_dupes || [])]).filter((l) => !l.is_private);
    if (!vis.length) { setRankMsg("점검할 네이버 광고가 화면에 없습니다."); return; }
    const cx = [...new Set(vis.map((l) => l.complex_no).filter(Boolean))] as string[];
    const an = [...new Set(vis.map((l) => l.article_no))];
    setRankBusy(true); setRankMsg("");
    try {
      const p = new URLSearchParams();
      if (cx.length && cx.length <= 200) p.set("complexes", cx.join(","));
      if (an.length <= 1500) p.set("articles", an.join(","));
      if (asRid) p.set("as_realtor", asRid);      // 사무소로 보기도 그 사무소 기준으로 점검
      const r = await fetch(`${API_BASE}/biz/my-rank?${p}`, { headers: authH() });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "점검하지 못했어요");
      const m: Record<string, any> = { ...rankBy };
      for (const x of d.items || []) m[x.article_no] = x;
      setRankBy(m);
      const got = (d.items || []).length;
      const bump = (d.items || []).filter((x: any) => x.bump_needed).length;
      setRankMsg(`광고 ${got}건 점검 · 단지 ${cx.length}곳`
        + (bump ? ` · 끌올 권장 ${bump}건` : " · 끌올 필요 없음")
        + (d.any_estimated ? " (일부 단지는 확인일 기준 추정)" : ""));
    } catch (e: any) {
      setRankMsg(e.message || "점검하지 못했어요");
    } finally { setRankBusy(false); }
  };

  const downloadCsv = () => {
    const head = ["거래", "단지·건물", "지역(시군구·법정동)", "동", "호", "평형", "공급(㎡)", "전용(㎡)", "층", "향",
                  "가격", "월세", "순위", "경쟁", "광고잔여(일)", "출처", "광고채널", "담당자", "연락처", "메모"];
    const cell = (v: any) => {
      const t = v == null ? "" : String(v);
      return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
    };
    const body = rows.map((l) => [
      l.trade_type, mlName(l), areaDongOf(l), bldDongOf(l), l.ho || "", l.area_name || "",
      l.area1_m2 || "", l.area2_m2 || "",
      l.floor_info || "", l.direction || "", l.price_text || "", l.rent_price_text || "",
      bestRank(l)?.rank_in_group ?? "", bestRank(l)?.group_size ?? "", soonLeft(l) ?? "",
      l.is_private ? (l.import_file ? "엑셀" : "직접등록") : "광고중",
      [l, ...(l.ad_dupes || [])].map((x) => x.cp_name || "").filter(Boolean).join(" / "),
      l.manager || "", l.contact || "", (l.memo || "").replace(/\n/g, " "),
    ].map(cell).join(","));
    const csv = "\uFEFF" + [head.join(","), ...body].join("\r\n");   // BOM — 엑셀 한글 깨짐 방지
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.download = `매물장_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };

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

  // ── 표에서 바로 고치기(엑셀처럼) ───────────────────────────────────────────
  // 연락처·메모·담당자는 lounge_notes 라 네이버 매물에도 쓸 수 있다. 나머지 항목은
  // 매물장 매물(직접등록·엑셀)만 고칠 수 있어 '수정' 버튼이 등록 폼을 연다.
  const [cellEdit, setCellEdit] = useState<{ an: string; k: "contact" | "memo" } | null>(null);
  const [draft, setDraft] = useState("");
  const beginEdit = (l: MLItem, k: "contact" | "memo") => {
    if (ro) return;
    setCellEdit({ an: l.article_no, k }); setDraft((l[k] || "") as string);
  };
  const commitEdit = async () => {
    const e = cellEdit; if (!e) return;
    setCellEdit(null);
    const l = (items || []).find((x) => x.article_no === e.an);
    if (!l || (l[e.k] || "") === draft) return;          // 안 바뀌었으면 보내지 않는다
    patch(e.an, e.k, draft);
    await fetch(`${API_BASE}/lounge/listings/note`, {
      method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
      body: JSON.stringify({
        article_no: e.an,
        memo: e.k === "memo" ? draft : l.memo,
        contact: e.k === "contact" ? draft : l.contact,
        manager: l.manager,
      }),
    });
    setSaved((x) => ({ ...x, [e.an]: true }));
    setTimeout(() => setSaved((x) => ({ ...x, [e.an]: false })), 1200);
  };
  const editKey = (ev: React.KeyboardEvent) => {
    if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); (ev.target as HTMLElement).blur(); }
    else if (ev.key === "Escape") { setCellEdit(null); }
  };

  useEffect(() => {
    if (!chkOpen) return;
    const away = (e: Event) => {
      if (!(e.target as HTMLElement)?.closest?.(".mlt-chkmenu,.mlt-fchk")) setChkOpen(null);
    };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setChkOpen(null); };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc); };
  }, [chkOpen]);

  // 대장으로 채울 수 있는 건 매물장 매물(직접등록·엑셀)뿐이다. 네이버 광고 매물은
  // 네이버가 준 값이라 우리가 덮지 않는다. 전유부 조회는 호가 있어야 한 집을 특정한다.
  const needFill = useMemo(() => (items || []).filter((l) =>
    l.is_private && l.private_id && (l.ho || "").trim() && (!l.area2_m2 || !l.floor_info)
  ), [items]);

  const runFill = async () => {
    if (ro) return;
    fillStop.current = false;
    const list = needFill.slice(0, 500);
    setFilling({ done: 0, total: list.length, ok: 0 });
    let ok = 0;
    for (let i = 0; i < list.length; i++) {
      if (fillStop.current) break;
      try {
        // 한 건씩 부른다 — 한 번에 몰면 외부 API 응답을 기다리다 게이트웨이가 끊는다.
        const r = await fetch(`${API_BASE}/lounge/private-listings/${list[i].private_id}/enrich`, {
          method: "POST", headers: { ...authH(), "Content-Type": "application/json" }, body: "{}",
        });
        const d = await r.json().catch(() => null);
        if (d?.filled?.length) ok++;
      } catch { /* 한 건 실패가 전체를 멈추지 않는다 */ }
      setFilling({ done: i + 1, total: list.length, ok });
    }
    setFilling(null); setFillAsk(false);
    load();
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
    <div className="mljang mlj2">
      {focusGroup ? (
        // ── 큰 폴더 전체보기 ──
        <div className="mlj2-focus">
          <div className="mlj2-fbar">
            <button className="mlj2-back" onClick={() => setFocusKey(null)}><ArrowLeft size={18} />매물장</button>
            <b>{groupName(focusGroup.items)}</b>
            <span className="mlj2-fbar-n">{focusGroup.items.length}건</span>
          </div>
          <div className="mlj2-list">{focusGroup.items.map((l) => Card(l, mode === "type"))}</div>
        </div>
      ) : (
        <>
          {/* 어느 매물장을 볼지 — 사무실 / 내 매물장 / 비공개(대표만) */}
          <div className="mlj2-shelf" role="tablist" aria-label="매물장 고르기">
            {(["office", "my", ...(isOwner ? ["private"] : [])] as Shelf[]).map((k) => (
              <button key={k} role="tab" aria-selected={shelf === k}
                className={shelf === k ? "on" : ""}
                onClick={() => { if (k === shelf) return; setShelf(k); setSel(new Set()); setPickMode(false); setMoveAsk(null); }}>
                {k === "private" && <Lock size={12} aria-hidden />}
                {k === "my" && <Star size={12} aria-hidden />}
                {SHELF_KR[k]}
                {counts[k] != null && <i>{counts[k]}</i>}
              </button>
            ))}
            <span className="mlj2-shelf-n">
              {shelf === "private" ? "대표만 보입니다 — 사무실 매물장·지도·손님 매칭에서 빠집니다."
                : shelf === "my" ? "내가 담은 것만 보입니다. 사무실 매물장에도 그대로 있어요."
                : "소속 직원 모두가 봅니다."}
            </span>
          </div>
          {moveAsk && (
            <div className="mlj2-movebar">
              <span><b>{moveAsk.msg}</b>{moveAsk.to !== shelf ? " 지금 보시겠어요?" : ""}</span>
              {moveAsk.to !== shelf && (
                <button className="mv-go" onClick={() => { setShelf(moveAsk.to); setMoveAsk(null); }}>
                  {SHELF_KR[moveAsk.to]}으로 이동
                </button>
              )}
              <button className="mv-x" onClick={() => setMoveAsk(null)}>닫기</button>
            </div>
          )}
          {/* 검색 · 정렬 · 필터 */}
          <div className="mlj2-top">
            <span className="mlj2-srch">
              <Search size={16} aria-hidden />
              <input placeholder="단지·건물·지역 또는 매물번호" value={q} inputMode="text"
                onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
            </span>
            <span className="mlj2-cxsel">
              <select value={cx} onChange={(e) => setCx(e.target.value)} aria-label="단지 선택">
                <option value="">단지 전체 ({opts.cx.length}곳)</option>
                {opts.cx.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
              <ChevronDown size={12} aria-hidden />
            </span>
            <span className="mlj2-sort">
              <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="정렬">
                <option value="confirm">최신확인순</option>
                <option value="price_desc">가격↓</option>
                <option value="price_asc">가격↑</option>
              </select>
              <ChevronDown size={12} aria-hidden />
            </span>
            <button className="mlj2-filt" onClick={() => setSheetOpen(true)}>
              <SlidersHorizontal size={15} aria-hidden />필터{activeFilters > 0 && <i className="mlj2-fb">{activeFilters}</i>}
            </button>
          </div>
          {/* 묶는 단위 + 보조 액션(거래유형은 필터 시트로 이동해 중복 제거) */}
          <div className="mlj2-tools">
            <span className="mlj2-count-act">
              <button onClick={() => setMapOpen(true)}><MapIcon size={13} aria-hidden />지도</button>
              {!ro && <button onClick={() => setImpOpen(true)}><Upload size={13} aria-hidden />가져오기</button>}
              <span className="mlt-colsbtn">
                <button onClick={() => setColsOpen((v) => !v)}>
                  <SlidersHorizontal size={13} aria-hidden />열 고르기
                </button>
                {colsOpen && (
                  <div className="mlt-colsmenu" onMouseLeave={() => setColsOpen(false)}>
                    <div className="mlt-colsmenu-h">표에 보여줄 열</div>
                    <div className="mlt-colmode">
                      <button className={colAuto ? "on" : ""} onClick={() => setColAuto(true)}>
                        화면에 맞춤
                      </button>
                      <button className={colAuto ? "" : "on"}
                        onClick={() => { setCols({ ...autoCols }); setColAuto(false); }}>
                        직접 고르기
                      </button>
                    </div>
                    {colAuto && (
                      <div className="mlt-colmode-n">
                        지금 폭({tw ? Math.round(tw) + "px" : "측정 중"})에 {VIEWCOLS.length}개가 들어갑니다.
                        창을 넓히면 저절로 늘어납니다.
                      </div>
                    )}
                    {ALLCOLS.filter(([k]) => !ALWAYS.has(k)).map(([k, t]) => {
                      const shown = VIEWCOLS.some(([v]) => v === k);
                      return (
                        <label key={k} className={(k === "name" && cx) || colAuto ? "off" : ""}>
                          <input type="checkbox" checked={shown}
                            disabled={colAuto || (k === "name" && !!cx)}
                            onChange={(e) => setCols((c) => ({ ...c, [k]: e.target.checked }))} />
                          {t}
                          {k === "name" && cx && <i>단지를 골라 숨김</i>}
                          {colAuto && !shown && !(k === "name" && cx) && <i>자리 부족</i>}
                        </label>
                      );
                    })}
                    {!colAuto && (
                      <button className="mlt-colsmenu-r"
                        onClick={() => setCols({ spec: true, src: true, manager: true, contact: true, memo: true, name: true })}>
                        전부 보이기
                      </button>
                    )}
                  </div>
                )}
              </span>
              <button className={foldAds ? "on" : ""} title="같은 물건을 CP 채널마다 올린 광고를 한 줄로 접습니다"
                onClick={() => { const n = !foldAds; setFoldAds(n); foldRef.current = n;
                  setItems(n ? foldAdDupes(rawRef.current) : rawRef.current.slice()); }}>
                <Link2 size={13} aria-hidden />{foldAds ? "광고 접음" : "광고 펼침"}
              </button>
              {(
                <button className={rankBusy ? "on" : ""} disabled={rankBusy}
                  title="화면에 보이는 매물의 네이버 순위와 광고 잔여일을 점검합니다"
                  onClick={checkRank}>
                  <TrendingUp size={13} aria-hidden />{rankBusy ? "점검 중…" : "순위 점검"}
                </button>
              )}
              <button onClick={downloadCsv}><Download size={13} aria-hidden />엑셀받기</button>
              {!ro && <button className={pickMode ? "on" : ""}
                title="체크해서 내 매물장에 담거나, 비공개로 보내거나, 지웁니다"
                onClick={() => { setPickMode((v) => !v); setSel(new Set()); }}>
                <Check size={13} aria-hidden />{pickMode ? "선택 끝내기" : "고르기"}
              </button>}
            </span>
          </div>
          {pickMode && (
            <div className="mlj2-delbar">
              <span><b>{sel.size}건</b> 선택</span>
              <button className="mlj2-delall" onClick={() => {
                const ans = rows.map((l) => l.article_no);
                setSel((s) => s.size === ans.length ? new Set() : new Set(ans));
              }}>{sel.size && sel.size === rows.length ? "선택 해제" : "보이는 것 전체"}</button>
              {shelf !== "my" && (
                <button className="mlj2-shelfgo" disabled={!sel.size}
                  onClick={() => shelfSet("my", "add")}>
                  <Star size={13} aria-hidden />내 매물장에 담기
                </button>
              )}
              {shelf === "my" && (
                <button className="mlj2-shelfgo" disabled={!sel.size}
                  onClick={() => shelfSet("my", "remove")}>
                  <Minus size={13} aria-hidden />내 매물장에서 빼기
                </button>
              )}
              {isOwner && shelf !== "private" && (
                <button className="mlj2-shelfgo pv" disabled={!sel.size}
                  onClick={() => shelfSet("private", "add")}>
                  <Lock size={13} aria-hidden />비공개로 보내기
                </button>
              )}
              {isOwner && shelf === "private" && (
                <button className="mlj2-shelfgo pv" disabled={!sel.size}
                  onClick={() => shelfSet("private", "remove")}>
                  <Globe size={13} aria-hidden />비공개 해제
                </button>
              )}
              <button className="mlj2-delgo" disabled={!sel.size} onClick={deleteSelected}>
                <Trash2 size={13} aria-hidden />삭제
              </button>
            </div>
          )}

          {ro && (
            <div className="mlt-asbar">
              <b>사무소로 보기</b>
              <span>{asName || asRid} 사장님이 보는 매물장입니다 — <b>읽기 전용</b>(고치기·삭제·가져오기 잠김)</span>
            </div>
          )}
          {fillAsk && !ro && !filling && needFill.length > 0 && (
            <div className="mlt-fill">
              <span>
                전용면적·층이 비어 있는 매물이 <b>{needFill.length}건</b> 있습니다.
                건축물대장에서 채울까요?
              </span>
              <button className="on" onClick={runFill}>채우기</button>
              <button onClick={() => setFillAsk(false)}>나중에</button>
            </div>
          )}
          {filling && (
            <div className="mlt-fill run">
              <span>건축물대장 조회 중… <b>{filling.done}/{filling.total}</b> · 채움 {filling.ok}건</span>
              <button onClick={() => { fillStop.current = true; }}>중단</button>
            </div>
          )}
          {rankMsg && (
            <div className="mlt-rkbar">
              <span>{rankMsg}</span>
              <button onClick={() => setRankMsg("")}>닫기</button>
            </div>
          )}
          {colFilterCount > 0 && (
            <div className="mlt-fbar">
              <span>표에서 거른 조건 <b>{colFilterCount}개</b> · <b>{rows.length}</b>건 보임</span>
              <button onClick={clearColF}>조건 지우기</button>
            </div>
          )}
          {lookErr && <div className="mlj-foreign mlj-foreign-err">{lookErr}</div>}
          {foreign && (
            <div className="mlj-foreign">
              <div className="mlj-foreign-t">다른 사무실 물건입니다. 조회하시겠습니까?</div>
              <div className="mlj-foreign-s">매물번호 {foreign.article_no}{foreign.realtor_name ? ` · ${foreign.realtor_name}` : ""}</div>
              <div className="mlj-foreign-b">
                <button className="on" disabled={!foreign.listing}
                  onClick={() => { if (foreign.listing) { setDetailOwner(foreign.realtor_name || "다른 중개사무소"); setDetail(foreign.listing); } }}>조회하기</button>
                <button onClick={() => setForeign(null)}>취소</button>
              </div>
              {!foreign.listing && <div className="mlj-foreign-s">※ 해당 매물의 상세를 불러올 수 없습니다(사무소 미귀속 매물).</div>}
            </div>
          )}

          <div className="mlj2-count">
            <span>{busy
              ? <b style={{ color: "var(--c-primary)" }}>불러오는 중…</b>
              : <>총 <b>{items?.length ?? 0}</b>개{(items?.length ?? 0) > 0 && ` · ${mode === "type" ? "유형" : "단지"} ${groups.length}곳`}
                  {foldAds && rawRef.current.length > (items?.length ?? 0)
                    && <i className="mlt-foldn"> · 겹친 광고 {rawRef.current.length - (items?.length ?? 0)}건 접음</i>}</>}</span>
          </div>

          {loadErr ? (
            /* 예전엔 여기서 '매물 없음'이 떴다 — 세션이 끊긴 건데 매물이 사라진 줄 안다. */
            <LoadError msg={loadErr} onRetry={load} />
          ) : !items || (busy && items.length === 0) ? (
            <Loading label="내 매물을 불러오는 중이에요" slowHint="매물이 많으면 조금 더 걸릴 수 있어요" />
          ) : items.length === 0 ? (
            <div className="dash-empty">표시할 매물이 없습니다. 사무소 매물이 네이버에 등록되면 자동으로 매물장에 나옵니다.</div>
          ) : (
            <div className="mlt-outer" ref={outerRef}>
            <div className="mlt-wrap" ref={wrapRef} onScroll={syncEdge}
              onPointerDown={onDragDown} onPointerMove={onDragMove}
              onPointerUp={onDragUp}
              onPointerLeave={() => { onDragUp(); hideTip(); }}>
              <table className="mlt" style={{ minWidth: minW }}>
                <thead>
                  <tr>
                    {pickMode && <th className="mlt-ck" />}
                    {VIEWCOLS.map(([k, t]) => (
                      k === "act"
                        ? <th key={k} className="c-act">{t}</th>
                        : <th key={k} className={`c-${k}`} onClick={() => sortBy(k)} title="눌러서 정렬">
                            {t}{tSort.k === k && <i className="mlt-ar">{tSort.asc ? "▲" : "▼"}</i>}
                          </th>
                    ))}
                  </tr>
                  <tr className="mlt-f">
                    {pickMode && <th className="mlt-ck" />}
                    {VIEWCOLS.map(([k]) => (
                      <th key={k} className={`c-${k}`}>
                        {k === "trade_type" && colSel("trade_type", opts.trade_type)}
                        {k === "unit" && (opts.dong.length > 0 ? colChk("dong", "동") : null)}
                        {k === "name" && (opts.areaDong.length > 0
                          ? colSel("areaDong", opts.areaDong, "지역")
                          : <span className="mlt-f-cx">{cx || "전체"}</span>)}
                        {k === "area_name" && opts.area_name.length > 0 && colChk("area_name", "평형")}
                        {k === "direction" && opts.direction.length > 0 && colSel("direction", opts.direction, "향")}
                        {k === "price" && opts.priceBand.length > 1 && colSel("price_band", opts.priceBand, "가격")}
                        {k === "src" && opts.src.length > 1 && colSel("src", opts.src, "출처")}
                        {k === "cp_name" && opts.cp_name.length > 0 && colChk("cp_name", "광고채널")}
                        {k === "manager" && colSel("manager", opts.manager)}
                        {k === "contact" && opts.contactHas.length > 1 && colSel("contact_has", opts.contactHas, "연락처")}
                        {k === "memo" && opts.memoHas.length > 1 && colSel("memo_has", opts.memoHas, "메모")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((l) => {
                    const an = l.article_no;
                    const picked = sel.has(an);
                    return (
                      <tr key={l.article_no} className={picked ? "on" : ""}
                        onClick={() => {
                          if (dragRef.current.moved) { dragRef.current.moved = false; return; }
                          if (pickMode) {
                            setSel((x) => { const n = new Set(x); n.has(an) ? n.delete(an) : n.add(an); return n; });
                            return;
                          }
                          setDetailOwner(""); setDetail(l);
                        }}>
                        {pickMode && (
                          <td className="mlt-ck"><input type="checkbox" checked={picked} readOnly /></td>
                        )}
                        {VIEWCOLS.map(([k]) => {
                          if (k === "trade_type") return <td key={k} className="c-trade_type"><i className={`mlj2-badge b-${l.trade_type}`}>{l.trade_type || "미정"}</i></td>;
                          if (k === "unit") return <td key={k} className="c-unit">{unitCell(l) || <span className="mlt-no">—</span>}</td>;
                          if (k === "name") return <td key={k} className="c-name mlt-nm">{mlName(l)}{l.type && <em>{l.type}</em>}</td>;
                          if (k === "area_name") return <td key={k} className="c-area_name mlt-spec">{l.area_name || <span className="mlt-no">—</span>}</td>;
                          if (k === "supply") return <td key={k} className="c-supply mlt-spec">{l.area1_m2 ? areaLabel(l.area1_m2) : <span className="mlt-no">—</span>}</td>;
                          if (k === "excl") return <td key={k} className="c-excl mlt-spec">{l.area2_m2 ? areaLabel(l.area2_m2) : <span className="mlt-no">—</span>}</td>;
                          if (k === "floor") return <td key={k} className="c-floor mlt-spec">{floorCell(l) || <span className="mlt-no">—</span>}</td>;
                          if (k === "direction") return <td key={k} className="c-direction mlt-spec">{l.direction || <span className="mlt-no">—</span>}</td>;
                          if (k === "price") return <td key={k} className="c-price mlt-price">{mlPriceMain(l) || <span className="mlt-no">—</span>}</td>;
                          if (k === "src") return (
                            <td key={k} className="c-src mlt-src">
                              <SrcPills l={l} />
                              {!!l.ad_dupes?.length && (
                                <i className="mlt-adn" title={`같은 조건의 광고 ${l.ad_dupes.length + 1}건을 한 줄로 접었습니다 — ${
                                  [l, ...l.ad_dupes].map((x) => `${x.cp_name || "네이버"} ${x.article_no}`).join(", ")}`}>
                                  광고 {l.ad_dupes.length + 1}
                                </i>
                              )}
                            </td>
                          );
                          if (k === "rank") {
                            const rk = bestRank(l);      // 채널마다 등수가 다르다 — 가장 좋은 것
                            return (
                              <td key={k} className="c-rank mlt-spec">
                                {rk ? (
                                  <span className={rk.bump_needed ? "mlt-rk warn" : "mlt-rk"}
                                    title={rk.bump_needed ? "확인일을 갱신(끌올)하면 위로 올라갈 수 있습니다" : ""}>
                                    {rk.group_size > 1 ? `${rk.group_size}곳 중 ${rk.rank_in_group}등` : "단독"}
                                    {rk.bump_needed && <i>끌올</i>}
                                  </span>
                                ) : (
                                  <button className="mlt-rkask" onClick={(e) => { e.stopPropagation(); checkRank(); }}
                                    title="누르면 화면에 보이는 매물의 순위를 점검합니다">점검</button>
                                )}
                              </td>
                            );
                          }
                          if (k === "left") {
                            const d = soonLeft(l);       // 가장 임박한 쪽을 보여 준다
                            return (
                              <td key={k} className="c-left mlt-spec">
                                {d == null ? (l.is_private && !l.also_naver
                                    ? <span className="mlt-no">—</span>
                                    : <button className="mlt-rkask" onClick={(e) => { e.stopPropagation(); checkRank(); }}
                                        title="누르면 화면에 보이는 매물의 광고 잔여일을 점검합니다">점검</button>)
                                  : <span className={d <= 3 ? "mlt-lf bad" : d <= 7 ? "mlt-lf warn" : "mlt-lf"}
                                      title="확인일 + 30일 기준. 네이버가 만료일을 주지 않아 실측 노출기간으로 계산합니다">
                                      {d < 0 ? "지남" : `${d}일`}
                                    </span>}
                              </td>
                            );
                          }
                          if (k === "cp_name") return (
                            <td key={k} className="c-cp_name mlt-spec"
                              title={[l, ...(l.ad_dupes || [])].map((x) => `${x.cp_name || "네이버"} ${x.article_no}`).join("\n")}>
                              {l.cp_name || <span className="mlt-no">—</span>}
                              {!!l.ad_dupes?.length && <i className="mlt-cpn"> 외 {l.ad_dupes.length}</i>}
                            </td>
                          );
                          if (k === "manager") return (
                            <td key={k} className="c-manager" onClick={(e) => e.stopPropagation()}>
                              {pickMode || ro ? (l.manager || <span className="mlt-no">—</span>) : (
                                <select className="mlt-cell-sel" value={l.manager || ""}
                                  onChange={(e) => assignManager(l, e.target.value)}>
                                  <option value="">미지정</option>
                                  {managers.map((m) => <option key={m.name} value={m.name}>{m.name}</option>)}
                                </select>
                              )}
                            </td>
                          );
                          if (k === "contact" || k === "memo") {
                            const on = cellEdit?.an === l.article_no && cellEdit.k === k;
                            return (
                              <td key={k} className={k === "contact" ? "c-contact mlt-tel mlt-ed" : "c-memo mlt-memo mlt-ed"}
                                title={pickMode ? undefined : "눌러서 바로 고치기"}
                                onClick={(e) => { if (pickMode || ro) return; e.stopPropagation(); if (!on) beginEdit(l, k); }}>
                                {on ? (
                                  <input className="mlt-cell-in" autoFocus value={draft}
                                    onClick={(e) => e.stopPropagation()}
                                    onChange={(e) => setDraft(e.target.value)}
                                    onKeyDown={editKey} onBlur={commitEdit} />
                                ) : (
                                  (l[k] || "") || <span className="mlt-no">{k === "contact" ? "—" : ""}</span>
                                )}
                                {saved[l.article_no] && !on && <i className="mlt-okdot" title="저장됨">✓</i>}
                              </td>
                            );
                          }
                          return (
                            <td key={k} className="c-act">
                              <button className="mlt-edbtn"
                                title={l.is_private ? "매물 수정" : "상세 보기 — 네이버 광고 매물은 내용을 못 고칩니다"}
                                aria-label={l.is_private ? "매물 수정" : "상세 보기"}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (l.is_private && !ro) { setEditPL(l); setPlOpen(true); }
                                  else { setDetailOwner(""); setDetail(l); }
                                }}>
                                <Pencil size={13} aria-hidden />
                              </button>
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                  {!rows.length && (
                    <tr><td colSpan={VIEWCOLS.length + (pickMode ? 1 : 0)} className="mlt-empty">
                      조건에 맞는 매물이 없습니다.
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="mlt-grabtip" ref={tipRef} aria-hidden>↔ 끌어서 좌우로</div>
            {edge.r && <div className="mlt-fade r" aria-hidden />}
            {edge.r && (
              <button className="mlt-nudge r" title="오른쪽 열 보기" aria-label="오른쪽 열 보기"
                onClick={() => nudge(1)}>›</button>
            )}
            </div>
          )}
          {(edge.r || edge.l) && (
            <div className="mlt-hint">표를 좌우로 끌어 옮길 수 있습니다{edge.r ? " — 오른쪽에 열이 더 있습니다" : ""}</div>
          )}

          {/* 필터 바텀시트 */}
          {sheetOpen && (
            <div className="mlj2-sheet-wrap" onClick={() => setSheetOpen(false)}>
              <div className="mlj2-sheet" onClick={(e) => e.stopPropagation()}>
                <div className="mlj2-grab" />
                <div className="mlj2-sheet-h"><b>필터</b><button onClick={() => setSheetOpen(false)} aria-label="닫기"><X size={18} /></button></div>
                <div className="mlj2-fg"><div className="mlj2-fl">거래 유형</div>
                  <div className="mlj2-chips">
                    {([["", "전체"], ["매매", "매매"], ["전세", "전세"], ["월세", "월세"]] as const).map(([k, l]) => (
                      <button key={k} className={"mlj2-chip" + (trade === k ? " on blue" : "")} onClick={() => setTrade(k)}>{l}</button>
                    ))}
                  </div></div>
                <div className="mlj2-fg"><div className="mlj2-fl">매물 유형</div>
                  <div className="mlj2-chips">
                    {ML_CATS.map((c) => (
                      <button key={c || "all"} className={"mlj2-chip" + (cat === c ? " on" : "")} onClick={() => setCat(c)}>{c || "전체"}</button>
                    ))}
                  </div></div>
                <div className="mlj2-fg"><div className="mlj2-fl">담당자</div>
                  <div className="mlj2-chips">
                    <button className={"mlj2-chip" + (manager === "" ? " on" : "")} onClick={() => setManager("")}>전체</button>
                    <button className={"mlj2-chip" + (manager === "미지정" ? " on" : "")} onClick={() => setManager("미지정")}>미지정</button>
                    {managers.map((m) => (
                      <button key={m.name} className={"mlj2-chip" + (manager === m.name ? " on" : "")} onClick={() => setManager(m.name)}>{m.name}{m.position === "대표" ? "(대표)" : ""}</button>
                    ))}
                  </div></div>
                <div className="mlj2-fg"><div className="mlj2-fl">출처</div>
                  <div className="mlj2-chips">
                    <button className={"mlj2-chip" + (priv && !privOnly ? " on" : "")} onClick={() => { setPriv(true); setPrivOnly(false); }}>전체</button>
                    <button className={"mlj2-chip" + (!priv && !privOnly ? " on" : "")} onClick={() => { setPriv(false); setPrivOnly(false); }}>네이버만</button>
                    <button className={"mlj2-chip" + (privOnly ? " on" : "")} onClick={() => { setPriv(true); setPrivOnly(true); }}>직접등록만</button>
                  </div></div>
                <div className="mlj2-sheet-cta">
                  <button className="sc-reset" onClick={() => { setTrade(""); setCat(""); setManager(""); setPriv(true); setPrivOnly(false); }}>초기화</button>
                  <button className="sc-apply" onClick={() => setSheetOpen(false)}>{items?.length ?? 0}건 보기</button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* 매물 직접등록 — 플로팅 */}
      {!ro && <button className="mlj2-fab" onClick={() => { setEditPL(null); setPlOpen(true); }}>
        <Plus size={18} aria-hidden />직접등록
      </button>}
      {impOpen && (
        <ImportListings authH={authH} onClose={() => setImpOpen(false)}
          onSaved={() => { setPriv(true); load(); }} />
      )}
      {detail && <ListingDetail l={detail} owner={detailOwner} authH={authH}
        managers={managers}
        onPatch={ro ? undefined
          : (k, v) => { patch(detail.article_no, k, v); setDetail({ ...detail, [k]: v } as MLItem); }}
        onSaveNote={ro ? undefined : () => saveNote(detail)}
        saved={!!saved[detail.article_no]}
        onAssign={ro ? undefined : (v) => { assignManager(detail, v); setDetail({ ...detail, manager: v }); }}
        onToPrivate={ro ? undefined : (vis) => toPrivate(detail, vis)}
        privMsg={privMsg[detail.article_no]}
        onFilled={ro ? undefined : load}
        onEditPrivate={ro ? undefined : () => { setEditPL(detail); setPlOpen(true); setDetail(null); }}
        onDeletePrivate={ro ? undefined : () => delPrivate(detail)}
        onSavedPrivate={() => { setPriv(true); load(); }}
        onClose={() => { setDetail(null); setDetailOwner(""); }} />}
      {chkOpen && (() => {
        const k = chkOpen.k;
        const all = k === "dong" ? opts.dong : k === "area_name" ? opts.area_name
                  : k === "cp_name" ? opts.cp_name : [];
        const q = chkQ.trim().toLowerCase();
        const list = q ? all.filter((v) => v.toLowerCase().includes(q)) : all;
        const cur = colF[k] || [];
        const label = k === "dong" ? "동" : k === "cp_name" ? "광고채널" : "평형";
        const flip = (v: string) => setColF((f) => {
          const n = new Set(f[k] || []);
          n.has(v) ? n.delete(v) : n.add(v);
          return { ...f, [k]: [...n] };
        });
        return (
          <div className="mlt-chkmenu" style={{ left: chkOpen.x, top: chkOpen.y }}>
            <div className="mlt-chkmenu-h">
              <b>{label}</b>
              <span>{cur.length ? `${cur.length}개 선택` : "전체"}</span>
              <button onClick={() => setColF((f) => ({ ...f, [k]: [] }))}>해제</button>
            </div>
            {all.length > 10 && (
              <input className="mlt-chkmenu-q" autoFocus value={chkQ} placeholder="찾기"
                onChange={(e) => setChkQ(e.target.value)} />
            )}
            <div className="mlt-chkmenu-l">
              {list.map((v) => (
                <label key={v}>
                  <input type="checkbox" checked={cur.includes(v)} onChange={() => flip(v)} />
                  <span>{v}</span>
                </label>
              ))}
              {!list.length && <div className="mlt-chkmenu-e">{q ? "찾는 값이 없습니다." : "고를 값이 없습니다."}</div>}
            </div>
          </div>
        );
      })()}
      {mapOpen && <OfficeMap authH={authH} officeName={office.realtor_name} onClose={() => setMapOpen(false)} />}
      {plOpen && <PrivateListingForm authH={authH} init={editPL} managers={managers} isOwner={isOwner}
        onClose={() => setPlOpen(false)}
        onSaved={(toPriv) => {
          setPlOpen(false); setPriv(true); load();
          if (toPriv) setMoveAsk({ to: "private", msg: "비공개매물장에 등록했어요." });
        }} />}
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
function T({ f, set, k, label, wide, ...rest }: any) {
  return (
    <label className={"pl-f" + (wide ? " wide" : "")}><span>{label}</span>
      <input className="ai-input" value={f[k] ?? ""} onChange={set(k)} {...rest} /></label>
  );
}

// 유형별 소재지 세부칸 — 어떤 매물이든 '이 세대/이 점포/이 필지'까지 특정할 수 있게
// 유형에 맞는 칸(동·호·층·실)을 내고, 구조 칸으로 안 잡히는 건 상세주소로 받는다.
const PL_UNIT_CFG: Record<string, { dong?: [string, string]; ho?: [string, string]; hint: string }> = {
  토지:  { hint: "지번까지면 특정됩니다. 필지가 여럿이면 상세주소에 적어 주세요." },
  공장:  { hint: "지번까지면 특정됩니다." },
  건물:  { hint: "지번까지면 특정됩니다(통건물)." },
  단독:  { ho: ["호 (다가구만)", "101"], hint: "단독은 지번까지, 다가구는 호까지 적어 주세요." },
  상가:  { dong: ["동·블록", "A"], ho: ["호·실", "101"], hint: "지번 + 호·실까지 적으면 그 점포로 특정됩니다." },
  사무실: { dong: ["동·블록", "A"], ho: ["호·실", "302"], hint: "지번 + 호·실까지 적어 주세요." },
  지식산업센터: { dong: ["동", "A"], ho: ["호", "1203"], hint: "동·호까지 적어 주세요." },
};
const PL_UNIT_DEFAULT = { dong: ["동", "104"] as [string, string], ho: ["호", "1103"] as [string, string],
  hint: "동·호까지 적으면 그 세대로 특정됩니다." };
function PLUnit({ f, set }: any) {
  const cfg = PL_UNIT_CFG[f.type || ""] || PL_UNIT_DEFAULT;
  return (
    <>
      {cfg.dong && <T f={f} set={set} k="dong" label={cfg.dong[0]} placeholder={cfg.dong[1]} />}
      {cfg.ho && <T f={f} set={set} k="ho" label={cfg.ho[0]} placeholder={cfg.ho[1]} />}
      <label className="pl-f wide"><span>상세주소
        <em style={{ color: "#9aa4b0", fontWeight: 500, fontStyle: "normal" }}> · 동·호로 특정 안 되면</em></span>
        <input className="ai-input" value={f.address_detail ?? ""} onChange={set("address_detail")}
          placeholder="예: B동 201호 안쪽 · ○○빌딩 3층 · 왼쪽 점포" /></label>
      <p className="pl-addrmsg" style={{ gridColumn: "1/-1", marginTop: 0 }}>{cfg.hint}</p>
    </>
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

function PrivateListingForm({ authH, init, managers, isOwner, onClose, onSaved }: {
  authH: () => Record<string, string>; init: MLItem | null; managers: Manager[];
  isOwner?: boolean; onClose: () => void; onSaved: (toPrivate?: boolean) => void;
}) {
  const [f, setF] = useState<Record<string, any>>(() => ({
    // 공개범위는 더 고르지 않는다 — 사무실 공개가 기본이고, 숨기는 건 대표가 비공개매물장으로
    // 보내는 길 하나다(아래 체크). 예전에 '나만 보기'로 저장된 건은 그대로 작성자만 본다.
    visibility: "office", trade_type: "매매", type: "아파트",
    ...(init ? { ...init, id: init.private_id } : {}),
  }));
  const [toPriv, setToPriv] = useState(!!init?.in_private);
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
      // 대표가 비공개로 체크했으면 저장된 id 로 선반까지 옮긴다(체크를 풀면 되돌린다)
      if (isOwner && d?.id && toPriv !== !!init?.in_private) {
        await fetch(`${API_BASE}/lounge/listings/shelf`, {
          method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
          body: JSON.stringify({ shelf: "private", action: toPriv ? "add" : "remove",
                                 article_nos: [`P${d.id}`] }),
        }).catch(() => { /* 매물은 이미 저장됐다 — 선반은 매물장에서 다시 바꿀 수 있다 */ });
      }
      onSaved(isOwner && toPriv);
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

        {isOwner && (
          <>
            <div className="pl-sec">공개 범위</div>
            <label className="pl-privchk">
              <input type="checkbox" checked={toPriv} onChange={(e) => setToPriv(e.target.checked)} />
              <b><Lock size={12} aria-hidden /> 비공개매물장에 넣기</b>
              <span>대표만 보입니다. 체크하지 않으면 소속 직원 모두가 보는 사무실 매물장에 들어갑니다.</span>
            </label>
          </>
        )}

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
          <PLUnit f={f} set={set} />
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
        <div className="pl-sec">주소 (지번 전체)</div>
        <div className="pl-grid">
          <T f={f} set={set} k="address" label="지번 주소" placeholder="서울 강남구 역삼동 222" wide />
          <T f={f} set={set} k="building_name" label="동 이름·건물명" placeholder="예: 101동 / ○○빌딩" />
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

/** 매물장 매물 ↔ 네이버 광고 수동 연결. 자동으로 못 가린 짝을 중개사가 고른다. */
function LinkNaver({ pid, authH, onClose, onDone }: {
  pid: number; authH: () => Record<string, string>; onClose: () => void; onDone: () => void;
}) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetch(`${API_BASE}/lounge/private-listings/${pid}/link-candidates`, { headers: authH() })
      .then((r) => r.json()).then(setD).catch(() => setErr("후보를 불러오지 못했어요"));
  }, [pid, authH]);
  const link = async (an: string) => {
    setBusy(true); setErr("");
    try {
      const r = await fetch(`${API_BASE}/lounge/private-listings/${pid}/link`, {
        method: "POST", headers: { ...authH(), "Content-Type": "application/json" },
        body: JSON.stringify({ article_no: an }),
      });
      const j = await r.json().catch(() => null);
      if (!r.ok) throw new Error(j?.detail || "연결하지 못했어요");
      onDone(); onClose();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="mld-ov" onClick={onClose}>
      <div className="mld-lk" onClick={(e) => e.stopPropagation()}>
        <div className="mld-lk-h">
          <b>네이버 광고 연결</b>
          {d?.listing && <span>{d.listing.dong} {d.listing.ho} · {d.listing.trade_type} · {d.listing.price_text}</span>}
          <button onClick={onClose}><X size={16} /></button>
        </div>
        {err && <div className="mld-lk-err">{err}</div>}
        {!d ? <Loading /> : (
          <>
            {d.linked && (
              <div className="mld-lk-cur">
                지금 연결됨 — 매물번호 {d.linked}
                <button disabled={busy} onClick={() => link("")}>연결 해제</button>
              </div>
            )}
            <div className="mld-lk-l">
              {d.candidates.map((c: any) => (
                <button key={c.article_no} className="mld-lk-i" disabled={busy}
                  onClick={() => link(c.article_no)}>
                  <div className="mld-lk-i1">
                    <b>{c.trade_type} {c.price_text}{c.rent_price_text ? `/${c.rent_price_text}` : ""}</b>
                    <span>{c.building_name} · {c.area_name} · {c.floor_info}층 · {c.direction}</span>
                  </div>
                  <div className="mld-lk-i2">
                    <i>{c.why}</i>
                    <span>{c.cp_name} · {c.article_no} · 확인 {fmtYmd(c.confirm_ymd || "")}</span>
                  </div>
                  {c.feature_desc && <div className="mld-lk-i3">{c.feature_desc}</div>}
                </button>
              ))}
              {!d.candidates.length && <div className="mld-lk-e">이을 만한 우리 사무소 광고가 없습니다.</div>}
            </div>
          </>
        )}
      </div>
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
  // 네이버 연동매물 → 우리 매물장 보관. 네이버에서 내려가도 사무소가 계속 관리할 수 있게
  // 현재 값을 그대로 떠서 저장한다(복사). 내 사무소 매물에만 노출.
  const [savePick, setSavePick] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
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
                  <button onClick={() => onToPrivate("office")}>
                    <Lock size={12} /> 우리 매물장에 보관</button>
                </div>
              )
            )}
          </div>
        )}

        {/* 보조 패널·안내는 고정 버튼 바 '위'에 둔다 — 아래에 두면 sticky 푸터에 가린다 */}
        {savePick && (
          <div className="mld-topriv-pick">
            <div className="mld-topriv-t">우리 매물장에 보관할까요?</div>
            <div className="pl-vis">
              <button disabled={saving} onClick={() => toPrivate("office")}>
                <b>보관하기</b><span>사무실 매물장에 들어갑니다</span></button>
            </div>
            <div className="mld-topriv-n">
              네이버에서 내려가도 우리 매물장에 남아 계속 관리할 수 있어요.
              대표만 보게 하려면 매물장에서 <b>고르기 → 비공개로 보내기</b>를 쓰세요.
            </div>
          </div>
        )}
        {saveMsg && <div className="pl-msg" style={{ marginTop: 8 }}>{saveMsg}</div>}
        {l.is_private && l.source_article_no && (
          <div className="mld-srcnote">네이버 매물 {l.source_article_no} 에서 보관됨</div>
        )}

        <div className="mld-actions">
          {l.contact && <a className="mlj-call" href={`tel:${l.contact.replace(/[^\d+]/g, "")}`}><Phone size={14} /> 전화</a>}
          {kakao && <a className="mlj-naver" href={kakao} target="_blank" rel="noreferrer"><MapIcon size={14} /> 지도</a>}
          {route && <a className="mlj-naver" href={route} target="_blank" rel="noreferrer"><MapPin size={14} /> 길찾기</a>}
          {l.naver_url && <a className="mlj-naver" href={l.naver_url} target="_blank" rel="noreferrer"><ExternalLink size={14} /> 네이버 매물</a>}
          {canSave && <button className="mlj-topriv" onClick={() => setSavePick((v) => !v)}>
            <Lock size={14} /> 우리 매물장에 보관</button>}
          {/* 직접등록한 물건만 고치고 지울 수 있다. 네이버 매물은 수집분이라 우리가 못 지운다 */}
          {l.is_private && onEditPrivate && (
            <button className="mlj-naver" onClick={onEditPrivate}><Pencil size={14} /> 수정</button>
          )}
          {l.is_private && onDeletePrivate && (
            <button className="mld-del" onClick={onDeletePrivate}><Trash2 size={14} /> 삭제</button>
          )}
          {/* 자동 짝 맞추기가 못 가린 것은 사람이 가장 잘 안다 — 중개사가 직접 잇는다 */}
          {l.is_private && !!l.private_id && onEditPrivate && (
            <button className="mlj-naver" onClick={() => setLinkOpen(true)}>
              <Link2 size={14} /> {l.also_naver ? "네이버 광고 연결 바꾸기" : "네이버 광고 연결"}
            </button>
          )}
        </div>
      </div>
      {linkOpen && !!l.private_id && authH && (
        <LinkNaver pid={l.private_id} authH={authH}
          onClose={() => setLinkOpen(false)}
          onDone={() => { onSavedPrivate?.(); onClose(); }} />
      )}
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
