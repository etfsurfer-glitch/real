import { useEffect, useRef, useState } from "react";
import { Loading } from "../components/Loading";
import { Link, Outlet, useOutletContext } from "react-router-dom";
import { Crown } from "lucide-react";
import { SubNav } from "../components/SubNav";
import ShareBar from "../components/ShareBar";
import { useRegionFilter } from "../components/RegionSelect";
import { supabase } from "../supabase";

type DongRealtor = {
  realtor_id: string; realtor_name: string; listings: number;
  staff_count: number | null; established_year: number | null;
  tenure_years: number | null; phone: string | null; verified_office: boolean;
};
type DongResp = { cortar_no: string; dong_name: string | null; sort: string; count: number; top: DongRealtor | null; items: DongRealtor[] };

// 우리동네 중개사 — 사무소 소재 동 기준. 매물수·직원수·업력을 한눈에.
export function RealtorByDong() {
  const { sidos, sigungus, dongs, sido, setSido, sigungu, setSigungu, dong, setDong } = useRegionFilter();
  const [data, setData] = useState<DongResp | null>(null);
  const [sort, setSort] = useState("listings");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!dong || !API_BASE) { setData(null); return; }
    setLoading(true);
    fetch(`${API_BASE}/stats/realtors/by-dong?cortar=${dong}&sort=${sort}&limit=30`)
      .then((r) => r.json()).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [dong, sort]);

  return (
    <>
      <div className="section-title">우리동네 중개사 찾기</div>
      <p className="muted" style={{ margin: "2px 0 10px" }}>사무소가 있는 동을 고르면, 그 동네 중개사를 <b>매물수·직원수·업력</b>으로 한눈에 비교하세요.</p>
      <div className="dong-pick">
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

      {!dong && <div className="dong-empty">위에서 동을 선택하면 우리동네 중개사 랭킹이 나옵니다.</div>}
      {loading && <Loading />}
      {data && !loading && (
        <>
          <div className="dong-sort">
            {[["listings", "매물 많은순"], ["staff", "직원 많은순"], ["tenure", "업력순"]].map(([k, label]) => (
              <button key={k} className={sort === k ? "on" : ""} onClick={() => setSort(k)}>{label}</button>
            ))}
          </div>
          {data.top && (
            <div className="dong-top">
              <div className="dong-top-badge"><Crown size={16} aria-hidden /> {data.dong_name} 1등</div>
              <div className="dong-top-name">{data.top.realtor_name}</div>
              <div className="dong-top-stats">
                <span>매물 <b>{data.top.listings.toLocaleString()}</b></span>
                <span>직원 <b>{data.top.staff_count ?? "-"}</b></span>
                <span>업력 <b>{data.top.tenure_years ?? "-"}년</b></span>
              </div>
            </div>
          )}
          {data.items.length === 0 && <div className="dong-empty">이 동에 등록된 중개사 정보가 아직 없어요.</div>}
          <div className="dong-list">
            {data.items.map((r, i) => (
              <Link key={r.realtor_id} to={`/realtor/${r.realtor_id}`} className="dong-row">
                <span className="dong-rank">{i + 1}</span>
                <span className="dong-name">{r.realtor_name}{r.verified_office && <span className="dong-vf">인증</span>}</span>
                <span className="dong-m">매물 {r.listings.toLocaleString()}</span>
                <span className="dong-m">직원 {r.staff_count ?? "-"}</span>
                <span className="dong-m">업력 {r.tenure_years ?? "-"}년</span>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
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
