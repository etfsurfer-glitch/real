import { useEffect, useRef, useState, type ReactNode } from "react";
import { Loading } from "../components/Loading";
import { Link, Outlet, useOutletContext, useLocation } from "react-router-dom";
import { Crown, MapPin, X, Building2, Users, CalendarClock, Sparkles, Search } from "lucide-react";
import { SubNav } from "../components/SubNav";
import ShareBar from "../components/ShareBar";
import { useRegionFilter } from "../components/RegionSelect";
import { supabase } from "../supabase";

type DongRealtor = {
  realtor_id: string | null; sys_regno: string; realtor_name: string; listings: number;
  staff_count: number | null; established_year: number | null;
  tenure_years: number | null; phone: string | null; naver_linked: boolean; sido?: string;
};
type DongResp = { cortar_no: string; dong_name: string | null; sort: string; count: number; top: DongRealtor | null; items: DongRealtor[] };

// 매물 상세가 있는(naver 매칭) 곳만 링크, 아니면 일반 행.
function RealtorRowLink({ r, className, children }: { r: DongRealtor; className: string; children: ReactNode }) {
  return r.realtor_id
    ? <Link to={`/realtor/${r.realtor_id}`} className={className}>{children}</Link>
    : <div className={className}>{children}</div>;
}

// 분야별 랭크카드 — TODAY 우리동네 스타일(메달+막대바+값). 세 기준 동등.
function RealtorRankCard({ title, sub, icon, accent, items, val, valText }: {
  title: string; sub: string; icon: JSX.Element; accent: "blue" | "red" | "gold";
  items: DongRealtor[]; val: (r: DongRealtor) => number | null; valText: (r: DongRealtor) => string;
}) {
  const rows = topBy(items, val, 5);
  const max = Math.max(1, ...rows.map((r) => _num(val(r))));
  return (
    <section className={`rank-card a-${accent}`}>
      <div className="rank-h">
        <span className="rank-t"><span className="ic">{icon}</span>{title}<em>{sub}</em></span>
      </div>
      <div className="rank-rows">
        {rows.map((r, i) => (
          <RealtorRowLink r={r} className="rank-row" key={r.realtor_id || r.sys_regno}>
            <span className={`medal m${i < 3 ? i + 1 : 0}`}>{i + 1}</span>
            <span className="rank-body">
              <span className="rank-name">{r.realtor_name}</span>
              <span className="rank-bar"><i style={{ width: `${Math.max(6, (_num(val(r)) / max) * 100)}%` }} /></span>
            </span>
            <span className="rank-val">{valText(r)}</span>
          </RealtorRowLink>
        ))}
      </div>
    </section>
  );
}

const SORTS: [string, string][] = [["listings", "매물순"], ["staff", "직원순"], ["tenure", "업력순"]];
const _num = (v: number | null | undefined) => (v == null ? -1 : v);
function topBy(items: DongRealtor[], k: (r: DongRealtor) => number | null, n = 5): DongRealtor[] {
  return [...items].sort((a, b) => _num(k(b)) - _num(k(a))).slice(0, n);
}

// 더보기 모달 — 페이지 안 전체 랭킹 창. 정렬은 사용자가 직접(기본 강제 없음, 매물순으로 보기 시작).
function DongModal({ data, onClose }: { data: DongResp; onClose: () => void }) {
  const [sort, setSort] = useState("listings");
  const k = sort === "staff" ? (r: DongRealtor) => r.staff_count
    : sort === "tenure" ? (r: DongRealtor) => r.tenure_years
    : (r: DongRealtor) => r.listings;
  const rows = [...data.items].sort((a, b) => _num(k(b)) - _num(k(a)));
  return (
    <div className="dmodal-bg" onClick={onClose}>
      <div className="dmodal" onClick={(e) => e.stopPropagation()}>
        <div className="dmodal-head">
          <h3>{data.dong_name} 중개사 전체 ({data.count}곳)</h3>
          <button className="dmodal-x" onClick={onClose} aria-label="닫기"><X size={18} /></button>
        </div>
        <div className="dong-sort">
          {SORTS.map(([sk, label]) => (
            <button key={sk} className={sort === sk ? "on" : ""} onClick={() => setSort(sk)}>{label}</button>
          ))}
        </div>
        <div className="dmodal-list">
          {rows.map((r, i) => (
            <RealtorRowLink key={r.realtor_id || r.sys_regno} r={r} className="dong-row">
              <span className="dong-rank">{i + 1}</span>
              <span className="dong-name">{r.realtor_name}</span>
              <span className="dong-m">매물 {r.listings.toLocaleString()}</span>
              <span className="dong-m">직원 {r.staff_count ?? "-"}</span>
              <span className="dong-m">업력 {r.tenure_years ?? "-"}년</span>
            </RealtorRowLink>
          ))}
        </div>
      </div>
    </div>
  );
}

export function RealtorByDong() {
  const { sidos, sigungus, dongs, sido, setSido, sigungu, setSigungu, dong, setDong } = useRegionFilter();
  const [autoLoc, setAutoLoc] = useState<{ cortar: string; name: string } | null>(null);
  const [data, setData] = useState<DongResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);
  const [q, setQ] = useState("");
  const [qRes, setQRes] = useState<DongRealtor[] | null>(null);
  const [mode, setMode] = useState<"dong" | "name">("dong");  // 찾는 방법 — 둘을 한 덩어리로 안 쌓고 토글
  const shareRef = useRef<HTMLDivElement>(null);

  // 이름 검색 — 동네 찾기와 한 화면에서. 결과도 매물·직원·업력 같은 카드 톤.
  useEffect(() => {
    const t = q.trim();
    if (t.length < 1 || !API_BASE) { setQRes(null); return; }
    const id = window.setTimeout(() => {
      fetch(`${API_BASE}/stats/realtors/search?q=${encodeURIComponent(t)}&limit=40`)
        .then((r) => r.json()).then((j) => {
          const yr = new Date().getFullYear();
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          setQRes((j.items || []).map((x: any) => {
            const ey = x.established_year ? parseInt(String(x.established_year).slice(0, 4), 10) : null;
            return {
              realtor_id: x.realtor_id, sys_regno: x.realtor_id || x.realtor_name,
              realtor_name: x.realtor_name || "공인중개사", listings: x.count || 0,
              staff_count: x.staff_count ?? null, established_year: ey,
              tenure_years: ey ? yr - ey : null, phone: null,
              naver_linked: !!x.realtor_id, sido: x.sido,
            } as DongRealtor & { sido?: string };
          }));
        }).catch(() => setQRes([]));
    }, 300);
    return () => window.clearTimeout(id);
  }, [q]);

  // 진입 시 접속 위치(CF IP) → 가장 가까운 동을 기본값으로(허전함 방지). 사용자가 드롭다운으로 수정 가능.
  useEffect(() => {
    if (!API_BASE) return;
    fetch("/geo").then((r) => r.json()).then((g) => {
      if (g && g.lat && g.lng) {
        return fetch(`${API_BASE}/stats/nearest-dong?lat=${g.lat}&lng=${g.lng}`)
          .then((r) => r.json()).then((d) => {
            if (d.found) setAutoLoc({ cortar: d.cortar_no, name: d.region_name || d.dong_name });
          });
      }
    }).catch(() => {});
  }, []);

  const activeCortar = dong || autoLoc?.cortar || "";

  // 한 번만 받아서 세 기준으로 클라이언트 정렬(서버 기본정렬 없음 = 어느 기준도 안 밀어줌).
  useEffect(() => {
    if (!activeCortar || !API_BASE) { setData(null); setLoading(false); return; }
    setLoading(true);
    fetch(`${API_BASE}/stats/realtors/by-dong?cortar=${activeCortar}&limit=1000`)
      .then((r) => r.json()).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [activeCortar]);

  const items = data?.items ?? [];
  const topL = items.length ? [...items].sort((a, b) => b.listings - a.listings)[0] : null;
  const locName = (autoLoc && !dong) ? autoLoc.name : (data?.dong_name || "");
  const scope = data?.dong_name || "우리동네";

  return (
    <div className="hood share-target" ref={shareRef}>
      <div className="hood-hero">
        <div className="hood-hero-top">
          <span className="hood-loc"><MapPin size={15} strokeWidth={2.5} aria-hidden /> {locName || "동네 선택"}</span>
        </div>
        <h1 className="hood-h1">우리동네 좋은 중개사를<br />콕집이 찾아드립니다</h1>
        <div className="hood-modes">
          <button className={mode === "dong" ? "on" : ""} onClick={() => { setMode("dong"); setQ(""); }}>
            <MapPin size={14} strokeWidth={2.4} /> 우리 동네로
          </button>
          <button className={mode === "name" ? "on" : ""} onClick={() => setMode("name")}>
            <Search size={14} strokeWidth={2.4} /> 중개사무소명으로 찾기
          </button>
        </div>
        {mode === "dong" ? (
          <div className="hood-region">
            <select value={sido} onChange={(e) => setSido(e.target.value)}>
              <option value="">시·도</option>
              {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
            <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}>
              <option value="">시·군·구</option>
              {sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
            <select value={dong} onChange={(e) => setDong(e.target.value)} disabled={!sigungu}>
              <option value="">읍·면·동</option>
              {dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
            </select>
          </div>
        ) : (
          <div className="hood-namesearch">
            <Search size={15} aria-hidden />
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="중개사무소 이름 (예: 래미안, 자이…)" />
            {q && <button onClick={() => setQ("")} aria-label="지우기"><X size={14} /></button>}
          </div>
        )}
        {mode === "dong" && autoLoc && !dong && <div className="hood-hint">접속 위치 기준이에요 · 동을 바꾸면 그 동네로 기억해 드려요</div>}
      </div>

      {mode === "name" ? (
        !q.trim() ? (
          <div className="dong-empty">중개사무소 이름을 입력하면 결과가 나와요.</div>
        ) : (
          <div className="qres">
            <p className="muted" style={{ margin: "2px 0 8px", fontSize: 12.5 }}>
              <b>'{q.trim()}'</b> 검색 결과 {qRes?.length ?? 0}곳
            </p>
            {qRes && qRes.length === 0 && <div className="dong-empty">일치하는 중개사무소가 없어요.</div>}
            <div className="dong-list">
              {(qRes ?? []).map((r, i) => (
                <RealtorRowLink key={r.sys_regno} r={r} className="dong-row">
                  <span className="dong-rank">{i + 1}</span>
                  <span className="dong-name">{r.realtor_name}{r.sido && <em style={{ color: "#9aa7b8", fontWeight: 400 }}> {r.sido}</em>}</span>
                  <span className="dong-m">매물 {r.listings.toLocaleString()}</span>
                  <span className="dong-m">직원 {r.staff_count ?? "-"}</span>
                  <span className="dong-m">업력 {r.tenure_years ?? "-"}년</span>
                </RealtorRowLink>
              ))}
            </div>
          </div>
        )
      ) : loading ? <div className="hood-loading"><Loading /></div> : data && items.length > 0 ? (
        <>
          <div className="hood-digest">
            <span className="hood-digest-ic"><Sparkles size={16} strokeWidth={2.4} aria-hidden /></span>
            <span className="hood-digest-tx">
              <b className="scope">{scope}</b>엔 등록 중개사 <b>{data.count.toLocaleString()}곳</b>
              {topL && <> · 매물이 가장 많은 곳은 <b>{topL.realtor_name}</b> <b className="hot">{topL.listings.toLocaleString()}개</b>예요</>}
            </span>
          </div>
          <div className="hood-share"><ShareBar targetRef={shareRef} title={`${scope} 우리동네 중개사`} fileName={`콕집_우리동네중개사_${scope}`} /></div>
          <p className="muted" style={{ margin: "0 0 8px", fontSize: 12 }}>매물·직원·업력 세 기준을 나란히 — 무엇이 중요한지는 직접 정하세요.</p>
          <div className="rank-wrap">
            <RealtorRankCard title="매물 많은 곳" sub="현재 보유" icon={<Building2 size={16} strokeWidth={2.3} />} accent="blue"
              items={items} val={(r) => r.listings} valText={(r) => `${r.listings.toLocaleString()}개`} />
            <RealtorRankCard title="직원 많은 곳" sub="소속 인원" icon={<Users size={16} strokeWidth={2.3} />} accent="red"
              items={items} val={(r) => r.staff_count} valText={(r) => `${r.staff_count ?? "-"}명`} />
            <RealtorRankCard title="업력 깊은 곳" sub="개설 등록" icon={<CalendarClock size={16} strokeWidth={2.3} />} accent="gold"
              items={items} val={(r) => r.tenure_years} valText={(r) => `${r.tenure_years ?? "-"}년`} />
          </div>
          <button className="dong-more" onClick={() => setModal(true)}>전체 {data.count.toLocaleString()}곳 자세히 보기 →</button>
        </>
      ) : data ? (
        <div className="dong-empty">이 동에 등록된 중개사가 아직 없어요. 다른 동을 골라보세요.</div>
      ) : (
        <div className="dong-empty">동네를 선택하면 우리동네 중개사가 나옵니다.</div>
      )}
      {modal && data && <DongModal data={data} onClose={() => setModal(false)} />}
    </div>
  );
}

/** 순위 메달 — TOP 5 를 특별하게(금·은·동 + 1위 왕관). 6위부터는 숫자. */
function RankMedal({ rank }: { rank: number }) {
  if (rank > 5) return <span style={{ color: "#999" }}>{rank}</span>;
  const tier = rank === 1 ? "gold" : rank === 2 ? "silver" : rank === 3 ? "bronze" : "top";
  return (
    <span className={`rank-medal rank-${tier}`} title={`${rank}위`}>
      {rank === 1 ? <Crown size={13} strokeWidth={2.5} aria-hidden /> : rank}
    </span>
  );
}

type RealtorCtx = { national: RealtorRow[]; sidoEntries: [string, RealtorRow[]][] };

type RealtorRow = {
  realtor_id: string | null;
  realtor_name: string | null;
  count: number;
  sido?: string | null;
  staff_count?: number | null;
  established_year?: string | null;
  established_date?: string | null;
  representative?: string | null;
  location?: string | null;
  address?: string | null;
};

type NationalResp = { limit: number; items: RealtorRow[] };
type BySidoResp = { limit: number; groups: Record<string, RealtorRow[]> };
type SearchResp = { q: string; sido: string; items: RealtorRow[] };

type Sido = { cortar_no: string; cortar_name: string };

const API_BASE = import.meta.env.VITE_API_BASE;

export default function RealtorRanks() {
  const shareRef = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();
  const onDong = pathname === "/realtors" || pathname.endsWith("/dong");  // 우리동네 탭은 자체 히어로·검색
  const [national, setNational] = useState<RealtorRow[] | null>(null);
  const [bySido, setBySido] = useState<Record<string, RealtorRow[]> | null>(null);
  const [sidos, setSidos] = useState<Sido[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // search state
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [sidoFilter, setSidoFilter] = useState<string>(""); // "" = 전국, else cortar_no
  const [searchResults, setSearchResults] = useState<RealtorRow[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!API_BASE) {
      setError("local API가 설정되어 있지 않습니다 (VITE_API_BASE).");
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const [rNat, rSidoStats, rSidos] = await Promise.all([
          fetch(`${API_BASE}/stats/realtors/national?limit=20`),
          fetch(`${API_BASE}/stats/realtors/by-sido?limit=10`),
          supabase
            .from("regions")
            .select("cortar_no, cortar_name")
            .eq("cortar_type", "city")
            .order("cortar_no", { ascending: true }),
        ]);
        if (!rNat.ok) throw new Error(`national: ${rNat.status}`);
        if (!rSidoStats.ok) throw new Error(`by-sido: ${rSidoStats.status}`);
        const nat = (await rNat.json()) as NationalResp;
        const sidoStats = (await rSidoStats.json()) as BySidoResp;
        if (cancelled) return;
        setNational(nat.items);
        setBySido(sidoStats.groups);
        if (!rSidos.error && rSidos.data) setSidos(rSidos.data as Sido[]);
        setLoading(false);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // debounce search input
  useEffect(() => {
    const t = window.setTimeout(() => setSearchTerm(searchInput.trim()), 300);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  // run search whenever term or sido filter changes
  useEffect(() => {
    let cancelled = false;
    if (!API_BASE) return;
    if (searchTerm.length < 1) {
      setSearchResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const sidoCode = sidoFilter ? sidoFilter.slice(0, 2) : "";
    // API_BASE 가 "/api" 같은 상대경로라 new URL() 은 쓸 수 없다 (base 없으면 예외).
    // URLSearchParams 로 쿼리만 만들어 상대경로에 붙인다.
    const params = new URLSearchParams({ q: searchTerm, limit: "50" });
    if (sidoCode) params.set("sido", sidoCode);
    const url = `${API_BASE}/stats/realtors/search?${params.toString()}`;
    (async () => {
      try {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`search: ${r.status}`);
        const j = (await r.json()) as SearchResp;
        if (!cancelled) setSearchResults(Array.isArray(j.items) ? j.items : []);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setSearching(false);
      }
    })();
    return () => { cancelled = true; };
  }, [searchTerm, sidoFilter]);

  if (loading) return <Loading />;
  if (error) return <div style={{ color: "crimson" }}>오류: {error}</div>;

  const sidoEntries = bySido
    ? Object.entries(bySido).sort((a, b) => {
        const sumA = a[1].reduce((s, r) => s + r.count, 0);
        const sumB = b[1].reduce((s, r) => s + r.count, 0);
        return sumB - sumA;
      })
    : [];

  return (
    <div ref={shareRef} className="share-target">
      <Link to="/overview" className="back">← 전국현황</Link>
      {!onDong && <>
      <h2 style={{ margin: "0 0 4px" }}>중개사무소 매물 보유 순위</h2>
      <div className="muted" style={{ marginBottom: 16 }}>
        중개사무소별 보유 매물 수 기준. 같은 상호라도 사무소가 다르면 따로 집계됩니다.
      </div>
      <ShareBar targetRef={shareRef} title="중개사무소 매물 보유 순위" fileName="콕집_중개사무소랭킹" />

      <div className="section-title">중개사무소 검색</div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "8px 0" }}>
        <select
          value={sidoFilter}
          onChange={(e) => setSidoFilter(e.target.value)}
          style={{
            padding: "6px 10px",
            border: "1px solid #ccc",
            borderRadius: 6,
            fontSize: 13,
            background: "white",
          }}
        >
          <option value="">전국</option>
          {sidos.map((s) => (
            <option key={s.cortar_no} value={s.cortar_no}>{s.cortar_name}</option>
          ))}
        </select>
        <input
          className="search"
          placeholder="중개사무소 이름 (예: 래미안, 자이, 현대…)"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          style={{ flex: 1, margin: 0 }}
        />
      </div>
      {(searchInput.trim().length > 0 || searchResults !== null) && (
        <div style={{ marginBottom: 24 }}>
          {(searching || searchInput.trim() !== searchTerm) && (
            <div className="progress-bar" />
          )}
          <div className="muted" style={{ marginBottom: 4 }}>
            {searching || searchInput.trim() !== searchTerm
              ? `'${searchInput.trim()}' 검색 중…`
              : searchResults
                ? `'${searchTerm}' 결과 ${searchResults.length}건`
                : ""}
            {sidoFilter && (() => {
              const name = sidos.find((s) => s.cortar_no === sidoFilter)?.cortar_name;
              return name ? ` · ${name}` : "";
            })()}
          </div>
          {searchResults && searchResults.length === 0 && !searching && searchInput.trim() === searchTerm ? (
            <div className="muted">일치하는 중개사무소가 없습니다.</div>
          ) : searchResults ? (
            <RealtorTable rows={searchResults} search />
          ) : null}
        </div>
      )}
      </>}

      <SubNav tabs={[
        { to: "/realtors/dong", label: "우리동네" },
        { to: "/realtors/national", label: "매물보유(전국)" },
        { to: "/realtors/region", label: "매물보유(지역별)" },
        { to: "/realtors/tenure", label: "업력순위" },
        { to: "/realtors/staff", label: "직원수순위" },
      ]} />
      <Outlet context={{ national: national ?? [], sidoEntries }} />
    </div>
  );
}

export function RealtorNational() {
  const { national } = useOutletContext<RealtorCtx>();
  return (
    <>
      <div className="section-title">전국 TOP 20</div>
      <RealtorTable rows={national} detailed />
    </>
  );
}

export function RealtorBySido() {
  const { sidoEntries } = useOutletContext<RealtorCtx>();
  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>시도별 TOP 10</div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
        gap: 16,
        marginTop: 8,
      }}>
        {sidoEntries.map(([sidoName, rows]) => (
          <div key={sidoName}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{sidoName}</div>
            <RealtorTable rows={rows} compact />
          </div>
        ))}
      </div>
    </>
  );
}

function useRealtorList(path: string) {
  const [rows, setRows] = useState<RealtorRow[] | null>(null);
  useEffect(() => {
    if (!API_BASE) { setRows([]); return; }
    let alive = true;
    fetch(`${API_BASE}${path}`)
      .then((r) => r.json()).then((d) => { if (alive) setRows(d.items ?? []); })
      .catch(() => { if (alive) setRows([]); });
    return () => { alive = false; };
  }, [path]);
  return rows;
}

export function RealtorByStaff() {
  const rows = useRealtorList("/stats/realtors/by-staff?limit=20");
  return (
    <>
      <div className="section-title">직원수 TOP 20</div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        vworld 등록 소속 인원(공인중개사·중개보조원) 기준.
      </div>
      {rows ? <RealtorTable rows={rows} detailed /> : <Loading />}
    </>
  );
}

export function RealtorByTenure() {
  const rows = useRealtorList("/stats/realtors/by-tenure?limit=20");
  return (
    <>
      <div className="section-title">업력 TOP 20 (개업 빠른 순)</div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        vworld 개업신고일 기준 — 가장 오래 영업한 순.
      </div>
      {rows ? <RealtorTable rows={rows} detailed tenure /> : <Loading />}
    </>
  );
}

function RealtorTable(
  { rows, compact = false, detailed = false, tenure = false, search = false }:
  { rows: RealtorRow[]; compact?: boolean; detailed?: boolean; tenure?: boolean; search?: boolean },
) {
  if (rows.length === 0) return <div className="muted">데이터 없음</div>;
  const ranked = detailed || compact;  // 순위표(검색결과 제외)에서만 메달 표시
  return (
    <div className="rank-scroll">
    <table>
      <thead>
        <tr>
          <th style={{ width: 32 }}>#</th>
          <th>중개사무소</th>
          {detailed && <th>소재지</th>}
          {search && <th>소재지</th>}
          {search && <th>대표</th>}
          {detailed && <th className="num">소속인원</th>}
          {detailed && <th className="num">{tenure ? "개업일" : "개업연도"}</th>}
          <th className="num">매물</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={r.realtor_id ?? `row-${i}`} className={ranked && i < 5 ? `rank-row rank-row-${i + 1}` : undefined}>
            <td>{ranked ? <RankMedal rank={i + 1} /> : <span style={{ color: "#999" }}>{i + 1}</span>}</td>
            <td style={{
              fontSize: compact ? 12 : 13,
              maxWidth: compact ? 220 : detailed ? 280 : search ? 220 : undefined,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}>
              {r.realtor_id ? (
                <Link to={`/realtor/${encodeURIComponent(r.realtor_id)}`}>
                  {r.realtor_name ?? r.realtor_id}
                </Link>
              ) : (
                <span>{r.realtor_name ?? "-"}</span>
              )}
            </td>
            {detailed && <td>{r.sido ?? "-"}</td>}
            {search && (
              <td style={{ fontSize: 12, color: "#475569", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  title={r.address ?? undefined}>
                {r.location ?? "-"}
              </td>
            )}
            {search && <td style={{ fontSize: 12, color: "#475569" }}>{r.representative ?? "-"}</td>}
            {detailed && <td className="num">{r.staff_count != null ? `${r.staff_count}명` : "-"}</td>}
            {detailed && <td className="num">{(tenure ? r.established_date : r.established_year) ?? "-"}</td>}
            <td className="num">{(r.count ?? 0).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}
