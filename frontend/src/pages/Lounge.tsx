import { useEffect, useState, useCallback, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { PhoneModal } from "../components/PhoneVerify";
import { Loading } from "../components/Loading";
import { Building2, MessageSquare, Pencil, Globe, Phone, Share2, Link2,
  LayoutDashboard, Star, TrendingUp, Award, Plus, Minus, X, ChevronRight, Flame, RefreshCw } from "lucide-react";

const TT: Record<string, string> = { A1: "매매", B1: "전세", B2: "월세" };
type ChgItem = { article_no: string; complex_no: string; complex_name?: string | null;
  trade_type: string; area_name: string | null; floor: string | null; price: string; building: string | null; direction: string | null };
import { copyText, shareUrlNative } from "../lib/share";

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

type Office = {
  realtor_id: string; realtor_name: string | null; address?: string | null;
  representative?: string | null; tel?: string | null; cell?: string | null;
};
type Status = {
  state: "need_phone" | "select" | "no_match" | "doc_pending" | "linked" | "admin_pick";
  phone_verified: boolean;
  office?: Office; method?: string; candidates?: Office[]; is_admin?: boolean; has_homepage?: boolean;
};
type EditReq = { id: number; content: string; status: string; admin_note: string | null; created_at: string; resolved_at: string | null };
type Lead = { id: number; name: string | null; phone: string | null; message: string | null; source: string | null; status: string; created_at: string };

type Tab = "dashboard" | "office" | "edit" | "leads" | "homepage";
type Dash = {
  office: Office;
  stats: { total_listings: number; national_rank: number | null; national_total: number;
    region: { sido_name: string; count: number; rank: number; total: number } | null };
  reviews: { total: number; avg: number | null; new_count: number;
    recent: { type: string; rating: number | null; body: string; created_at: string }[] };
  leads: { new_count: number; total: number; recent: Lead[] };
  homepage: { has: boolean; slug: string | null; published: boolean };
  favorites_count: number;
};
type TradeCnt = { A1: number; B1: number; B2: number; sum: number };
type Fav = { complex_no: string; complex_name: string;
  record_high: { area_key: string; price: number; date: string } | null;
  total: TradeCnt; new_week: TradeCnt; today_change: number };
type FavOffice = { realtor_id: string; realtor_name: string | null; address: string | null;
  representative: string | null; total: TradeCnt; today_change: number; national_rank: number | null };

export default function Lounge() {
  const { user, token, ready, configured, refreshMe } = useAuth();
  const [st, setSt] = useState<Status | null>(null);
  const [loading, setLoading] = useState(true);
  const [phoneOpen, setPhoneOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("dashboard");

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

      {st.state === "need_phone" && (
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

      {st.state === "select" && (
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

      {st.state === "no_match" && (
        <Card>
          <p>인증된 번호와 일치하는 중개사무소를 찾지 못했습니다.</p>
          <p className="muted" style={{ fontSize: 13 }}>
            사무소 대표 연락처가 콕집 데이터와 다르거나 미등록일 수 있어요. 아래로 <b>사업자등록증</b>을 제출하시면
            관리자 확인 후 연결해 드립니다.
          </p>
          <DocSubmit authH={authH} onDone={loadStatus} />
        </Card>
      )}

      {st.state === "admin_pick" && (
        <Card>
          <p><b>관리자</b> — 인증 없이 입장했습니다. 둘러볼 중개사무소를 검색해 연결하세요.</p>
          <AdminPick authH={authH} onPicked={loadStatus} />
        </Card>
      )}

      {st.state === "doc_pending" && (
        <Card><p>제출하신 서류를 <b>관리자가 확인 중</b>입니다. 승인되면 라운지가 열립니다. (보통 1영업일 이내)</p></Card>
      )}

      {st.state === "linked" && st.office && (
        <>
          <div className="chip-row" style={{ marginBottom: 12 }}>
            {([
              ["dashboard", "대시보드", LayoutDashboard],
              ["homepage", st.has_homepage ? "홈페이지관리" : "홈페이지생성", Globe],
              ["leads", "상담신청", MessageSquare],
              ["edit", "정보수정요청", Pencil],
              ["office", "내 사무소", Building2],
            ] as const).map(([k, label, Icon]) => (
              <button key={k} className={`chip ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>
                <Icon size={13} strokeWidth={2.2} aria-hidden style={{ marginRight: 4, verticalAlign: "-2px" }} />
                {label}
              </button>
            ))}
          </div>
          {tab === "dashboard" && <DashboardTab authH={authH} office={st.office} onGoTab={setTab} />}
          {tab === "office" && <OfficeTab office={st.office} method={st.method} onUnlink={unlink} />}
          {tab === "edit" && <EditTab authH={authH} />}
          {tab === "leads" && <LeadsTab authH={authH} />}
          {tab === "homepage" && <HomepageTab authH={authH} office={st.office} onStatusChange={loadStatus} />}
        </>
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
function Card({ children }: { children: React.ReactNode }) {
  return <div style={{ border: "1px solid var(--c-border)", borderRadius: 12, padding: 18, maxWidth: 640, display: "grid", gap: 8 }}>{children}</div>;
}

function DashboardTab({ authH, office, onGoTab }: {
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
      <div className="dash-hero">
        <div className="dash-greet"><b>{greetName}</b> 대표님, 안녕하세요</div>
        <div className="dash-office">{office.realtor_name}</div>
        <div className="dash-date">{dateStr} · 오늘의 우리 사무소 현황입니다</div>
      </div>

      <div className="dash-stats">
        <StatCard icon={<Building2 size={18} />} accent="blue" label="우리 매물수"
          value={(s.total_listings || 0).toLocaleString()} unit="건"
          sub={s.national_rank ? `전국 ${s.national_rank.toLocaleString()}위` : "순위 집계 전"} />
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

function FavManager({ authH, favs, onChange }: {
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

function OfficeFavManager({ authH, offices, onChange }: {
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
    fetch(`${API_BASE}/stats/realtors/search?q=${encodeURIComponent(q)}&limit=12`)
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

function OfficeTab({ office, method, onUnlink }: { office: Office; method?: string; onUnlink: () => void }) {
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

function EditTab({ authH }: { authH: () => Record<string, string> }) {
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

function LeadsTab({ authH }: { authH: () => Record<string, string> }) {
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

function AdminPick({ authH, onPicked }: { authH: () => Record<string, string>; onPicked: () => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ realtor_id: string; realtor_name: string | null; location?: string | null; representative?: string | null }[]>([]);
  const search = () => {
    if (!q.trim()) return;
    fetch(`${API_BASE}/stats/realtors/search?q=${encodeURIComponent(q)}&limit=10`)
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
        <input className="ai-input" style={{ flex: 1 }} placeholder="중개사무소명 검색" value={q}
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

function HomepageTab({ authH, office, onStatusChange }: { authH: () => Record<string, string>; office: Office; onStatusChange: () => void }) {
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

function DocSubmit({ authH, onDone }: { authH: () => Record<string, string>; onDone: () => void }) {
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
