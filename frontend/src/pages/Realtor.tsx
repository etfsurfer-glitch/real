import { useEffect, useState } from "react";
import { MapPin, Phone, Smartphone, MessageSquare, Search, X } from "lucide-react";
import { Loading } from "../components/Loading";
import { RealtorReviews, type ReviewSummary } from "../components/RealtorReviews";
import { Link, useParams } from "react-router-dom";

type SidoRank = {
  sido_code: string;
  sido_name: string;
  count: number;
  rank: number;
  total_in_sido: number;
};

type ComplexAgg = {
  complex_no: string | null;
  complex_name: string | null;
  A1: number;
  B1: number;
  B2: number;
  total: number;
};

type VworldCandidate = { sys_regno: string; name: string | null; rep: string | null };
type VworldEmployees = { licensed: number; assistant: number; total: number };

type VworldMatch = {
  match_type: string;
  sys_regno: string | null;
  name: string | null;
  representative: string | null;
  address: string | null;
  phone: string | null;
  status: string | null;
  registered_ymd: string | null;
  ra_regno: string | null;
  candidates: VworldCandidate[];
  employees?: VworldEmployees;
};

type NaverInfo = {
  name: string | null;
  representative: string | null;
  address: string | null;
  tel: string | null;
  cell: string | null;
  homepage: string | null;
  latitude: number | null;
  longitude: number | null;
  deal_count: number | null;
  lease_count: number | null;
  rent_count: number | null;
};

type Breakdown = { complex: number; villa: number; house: number; sangga: number; office: number; land: number; factory: number; building: number; knowledge: number; redev: number; total: number };
type RankInfo = { count: number; national_rank: number; national_total: number };
type RepRank = RankInfo & { type: string; type_key: string; sido_name: string | null; sido_rank: number | null };
type RealtorDetail = {
  realtor_id: string;
  realtor_name: string | null;
  total_count: number;
  listing_breakdown?: Breakdown;
  trade_totals?: { A1: number; B1: number; B2: number };
  rep_rank?: RepRank | null;
  total_rank?: RankInfo | null;
  national_rank: number | null;
  national_total: number;
  by_sido: SidoRank[];
  by_complex: ComplexAgg[];
  vworld: VworldMatch | null;
  naver: NaverInfo | null;
};

const API_BASE = import.meta.env.VITE_API_BASE;

function telHref(s: string | null | undefined): string | null {
  if (!s) return null;
  const first = s.split(/\s+/)[0].replace(/[^\d]/g, "");
  return first.length >= 7 ? first : null;
}

export default function Realtor() {
  const { realtorId } = useParams();
  const [data, setData] = useState<RealtorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(null);

  const scrollToReviews = () => {
    document.getElementById("realtor-reviews")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  useEffect(() => {
    let cancelled = false;
    if (!realtorId) return;
    if (!API_BASE) {
      setError("local API가 설정되어 있지 않습니다 (VITE_API_BASE).");
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/realtor/${encodeURIComponent(realtorId)}`);
        if (r.status === 404) throw new Error("중개사무소를 찾을 수 없습니다.");
        if (!r.ok) throw new Error(`status ${r.status}`);
        const j = (await r.json()) as RealtorDetail;
        if (!cancelled) { setData(j); setLoading(false); }
      } catch (e) {
        if (!cancelled) { setError(e instanceof Error ? e.message : String(e)); setLoading(false); }
      }
    })();
    return () => { cancelled = true; };
  }, [realtorId]);

  if (loading) return <Loading />;
  if (error) return <div style={{ color: "crimson" }}>오류: {error}</div>;
  if (!data) return <div className="muted">데이터 없음</div>;

  // 거래유형 분포 — 전 유형(백엔드 trade_totals). 없으면 단지형(by_complex)으로 폴백.
  const tradeTotals = data.trade_totals ?? data.by_complex.reduce(
    (acc, r) => ({ A1: acc.A1 + r.A1, B1: acc.B1 + r.B1, B2: acc.B2 + r.B2 }),
    { A1: 0, B1: 0, B2: 0 },
  );
  const grandTotal = tradeTotals.A1 + tradeTotals.B1 + tradeTotals.B2;
  // 업력 / 자격증 비율
  const regYear = data.vworld?.registered_ymd
    ? parseInt(String(data.vworld.registered_ymd).replace(/[^\d]/g, "").slice(0, 4), 10) : null;
  const tenureYears = regYear && regYear > 1900 ? new Date().getFullYear() - regYear + 1 : null;
  const emp = data.vworld?.employees;
  const licPct = emp && emp.total > 0 ? Math.round((emp.licensed / emp.total) * 100) : null;

  // 연락처: vworld phone 우선, 없으면 naver tel/cell
  const office = data.vworld?.phone || data.naver?.tel || null;
  const cell = data.naver?.cell || null;
  const rep = data.vworld?.representative || data.naver?.representative || null;
  const address = data.vworld?.address || data.naver?.address || null;
  const status = data.vworld?.status;
  const matched = data.vworld?.sys_regno && !data.vworld.match_type.startsWith("multi") && data.vworld.match_type !== "none";

  return (
    <>
      <Link to="/realtors" className="back">← 중개사무소 랭킹</Link>

      {/* 본인 사무소 주장 CTA — 중개사가 자기 사무소 보러 왔을 때 라운지로 유입 */}
      <Link to="/lounge" className="claim-cta">
        <span className="claim-cta-tx">
          <b>이 사무소가 본인 것인가요?</b><br />휴대폰 인증 한 번이면 <b>무료 홈페이지·매물·리뷰</b>를 관리할 수 있어요.
        </span>
        <span className="claim-cta-btn">내 사무소 관리 →</span>
      </Link>

      {/* ── 헤더 프로필 카드 ── */}
      <div className="realtor-hero">
        <div className="realtor-hero-main">
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="realtor-name-row">
              <h2 className="realtor-name">{data.realtor_name ?? data.realtor_id}</h2>
            </div>
            <div className="realtor-sub">
              {rep && <span>대표 <b>{rep}</b></span>}
              {status && (
                <span className={`status-pill ${status === "영업" || status === "영업중" ? "ok" : "warn"}`}>
                  {status}
                </span>
              )}
              {matched && data.vworld?.ra_regno && (
                <span className="muted">등록 {data.vworld.ra_regno}</span>
              )}
            </div>
            {address && (
              <div className="realtor-addr">
                <MapPin size={13} strokeWidth={2.2} aria-hidden /> {address}
              </div>
            )}
            <button type="button" className={`realtor-rating${reviewSummary && reviewSummary.total_count > 0 ? "" : " empty"}`} onClick={scrollToReviews}>
              {reviewSummary && reviewSummary.total_count > 0 ? (
                <>
                  {reviewSummary.avg_rating != null && (
                    <span className="rr-stars">
                      <span className="stars" aria-hidden>
                        {[1, 2, 3, 4, 5].map((n) => <span key={n} className={n <= Math.round(reviewSummary.avg_rating!) ? "on" : ""}>★</span>)}
                      </span>
                      <b>{reviewSummary.avg_rating.toFixed(1)}</b>
                    </span>
                  )}
                  <span className="rr-meta">
                    리뷰 <b>{reviewSummary.total_count}</b>
                    {reviewSummary.verified_count > 0 && <> · 거래인증 <b>{reviewSummary.verified_count}</b></>}
                  </span>
                  <span className="rr-go">보기 ›</span>
                </>
              ) : (
                <>
                  <MessageSquare size={14} strokeWidth={2.3} aria-hidden />
                  <span className="rr-meta">아직 리뷰가 없어요</span>
                  <span className="rr-go">첫 리뷰 남기기 ›</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* 연락처 버튼들 */}
        <div className="realtor-contacts">
          {office && telHref(office) && (
            <a className="contact-btn primary" href={`tel:${telHref(office)}`}>
              <Phone size={14} strokeWidth={2.2} aria-hidden /> {office.split(/\s+/)[0]}
            </a>
          )}
          {cell && telHref(cell) && (
            <a className="contact-btn" href={`tel:${telHref(cell)}`}>
              <Smartphone size={14} strokeWidth={2.2} aria-hidden /> {cell}
            </a>
          )}
        </div>
      </div>

      {/* ── 핵심 지표 ── */}
      <div className="stat-grid">
        {/* 1. 대표 분야 순위 (단지 수는 단지형이 대표일 때만) */}
        {data.rep_rank && (
          <div className="stat-box">
            <div className="stat-label">{data.rep_rank.type} 순위 <span className="stat-tag">대표분야</span></div>
            <div className="stat-value">#{data.rep_rank.national_rank.toLocaleString()}</div>
            <div className="stat-sub">
              {data.rep_rank.count.toLocaleString()}개
              {data.rep_rank.type_key === "complex" && ` · ${data.by_complex.length}개 단지`}
              {" · "}전국 {data.rep_rank.national_total.toLocaleString()}곳
              {data.rep_rank.sido_rank && <> · {data.rep_rank.sido_name} #{data.rep_rank.sido_rank.toLocaleString()}</>}
            </div>
          </div>
        )}
        {/* 2. 전체 매물 순위 */}
        {data.total_rank && (
          <div className="stat-box">
            <div className="stat-label">전체 매물 순위</div>
            <div className="stat-value">#{data.total_rank.national_rank.toLocaleString()}</div>
            <div className="stat-sub">{data.total_rank.count.toLocaleString()}개 · 전국 {data.total_rank.national_total.toLocaleString()}곳</div>
          </div>
        )}
        {/* 3. 소속 인원 + 자격증 비율 */}
        {emp && emp.total > 0 && (
          <div className="stat-box">
            <div className="stat-label">소속 인원</div>
            <div className="stat-value">{emp.total}<span style={{ fontSize: 14 }}>명</span>
              {licPct != null && <span className="stat-lic">자격증 {licPct}%</span>}
            </div>
            <div className="stat-sub">공인중개사 {emp.licensed}{emp.assistant > 0 && ` · 중개보조 ${emp.assistant}`}</div>
          </div>
        )}
        {/* 4. 업력 */}
        {tenureYears != null && (
          <div className="stat-box">
            <div className="stat-label">업력</div>
            <div className="stat-value">{tenureYears}<span style={{ fontSize: 14 }}>년차</span></div>
            <div className="stat-sub">개업 {regYear}년</div>
          </div>
        )}
      </div>

      {/* ── 매물 유형 breakdown (단지형 기본 + 비단지) ── */}
      {data.listing_breakdown && data.listing_breakdown.total > data.listing_breakdown.complex && (
        <div className="rl-breakdown">
          <span className="rl-bd-title">매물 유형</span>
          {(([["단지형", "complex"], ["빌라", "villa"], ["단독", "house"], ["상가", "sangga"], ["사무실", "office"], ["빌딩", "building"], ["토지", "land"], ["공장", "factory"], ["지식산업센터", "knowledge"], ["재개발", "redev"]] as const)
            .filter(([, k]) => (data.listing_breakdown![k] || 0) > 0)
            .map(([label, k]) => (
              <span key={k} className={`rl-bd-chip${k === "complex" ? " primary" : ""}`}>{label} <b>{data.listing_breakdown![k].toLocaleString()}</b></span>
            )))}
          <span className="rl-bd-chip total">전체 <b>{data.listing_breakdown.total.toLocaleString()}</b></span>
        </div>
      )}

      {/* ── 거래유형 분포 막대 ── */}
      {grandTotal > 0 && (
        <div className="trade-dist">
          <div className="trade-bar">
            {tradeTotals.A1 > 0 && <div className="seg a1" style={{ flex: tradeTotals.A1 }} title={`매매 ${tradeTotals.A1}`} />}
            {tradeTotals.B1 > 0 && <div className="seg b1" style={{ flex: tradeTotals.B1 }} title={`전세 ${tradeTotals.B1}`} />}
            {tradeTotals.B2 > 0 && <div className="seg b2" style={{ flex: tradeTotals.B2 }} title={`월세 ${tradeTotals.B2}`} />}
          </div>
          <div className="trade-legend">
            <span><i className="dot a1" />매매 {tradeTotals.A1.toLocaleString()}</span>
            <span><i className="dot b1" />전세 {tradeTotals.B1.toLocaleString()}</span>
            <span><i className="dot b2" />월세 {tradeTotals.B2.toLocaleString()}</span>
          </div>
        </div>
      )}

      {/* ── vworld 매칭 상태 (불완전한 경우만 노출) ── */}
      {data.vworld && !matched && <VworldUnmatched v={data.vworld} />}

      {/* ── 지역별 순위 ── */}
      {data.by_sido.length > 1 && (
        <>
          <div className="section-title">지역별 활동</div>
          <table>
            <thead>
              <tr><th>지역</th><th className="num">매물</th><th className="num">지역 순위</th></tr>
            </thead>
            <tbody>
              {data.by_sido.map((s) => (
                <tr key={s.sido_code}>
                  <td>{s.sido_name}</td>
                  <td className="num">{s.count.toLocaleString()}</td>
                  <td className="num">#{s.rank.toLocaleString()} <span className="muted">/ {s.total_in_sido.toLocaleString()}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* ── 보유 매물(전체 유형 + 필터) ── */}
      <RealtorListings realtorId={data.realtor_id} breakdown={data.listing_breakdown} />

      {/* ── 중개사무소 리뷰 ── */}
      <RealtorReviews realtorId={data.realtor_id} onSummary={setReviewSummary} />

      {/* ── 데이터 출처 ── */}
      <div className="muted" style={{ marginTop: 16, fontSize: 11 }}>
        ID {data.realtor_id}
        {data.vworld?.match_type && ` · 매칭: ${data.vworld.match_type}`}
        {data.vworld?.registered_ymd && ` · 등록일 ${data.vworld.registered_ymd}`}
      </div>
    </>
  );
}

function VworldUnmatched({ v }: { v: VworldMatch }) {
  const isMulti = v.match_type.startsWith("multi");
  return (
    <div className="vworld-warn">
      {isMulti ? (
        <>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>
            ⚠ 국토부 등록 사무소 후보 {v.candidates.length}개 (자동 확정 보류)
          </div>
          <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {v.candidates.map((c) => (
              <li key={c.sys_regno}>{c.name} <span className="muted">({c.rep})</span></li>
            ))}
          </ol>
        </>
      ) : (
        <div className="muted">국토부 부동산중개업 등록 정보와 매칭되지 않았습니다 (폐업/말소/미등록 가능).</div>
      )}
    </div>
  );
}

// ── 보유 매물(전체 유형 + 유형 필터) ──
type RLItem = {
  article_no: string; complex_no: string | null; complex_name: string | null; trade_type: string; type: string;
  area_name: string; area2_m2: number; floor_info: string; direction: string;
  price_text: string; rent_price_text: string; confirm_ymd: string; building_name: string;
  feature_desc: string; naver_url: string; address: string; parking_per: number | null;
};
function rlFmtYmd(s: string) { return s && s.length === 8 ? `${s.slice(4, 6)}/${s.slice(6, 8)}` : s; }

const RL_PAGE = 30;
function RealtorListings({ realtorId, breakdown }: { realtorId: string; breakdown?: Breakdown }) {
  const [cat, setCat] = useState("");
  const [trade, setTrade] = useState("");
  const [sort, setSort] = useState("confirm");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(RL_PAGE);
  const [items, setItems] = useState<RLItem[] | null>(null);
  useEffect(() => {
    if (!API_BASE) { setItems([]); return; }
    let alive = true;
    setItems(null); setShown(RL_PAGE);
    const p = new URLSearchParams({ cat, trade, sort, limit: "1500" });
    fetch(`${API_BASE}/realtor/${encodeURIComponent(realtorId)}/listings?${p}`)
      .then((r) => r.json()).then((d) => { if (alive) setItems(d.listings || []); })
      .catch(() => { if (alive) setItems([]); });
    return () => { alive = false; };
  }, [realtorId, cat, trade, sort]);

  const b = breakdown;
  const chips: [string, string, number][] = b
    ? ([["전체", "", b.total], ["단지형", "단지형", b.complex], ["빌라", "빌라", b.villa],
        ["단독", "단독", b.house], ["상가", "상가", b.sangga], ["사무실", "사무실", b.office],
        ["빌딩", "빌딩", b.building], ["토지", "토지", b.land], ["공장", "공장", b.factory],
        ["지식산업센터", "지식산업센터", b.knowledge], ["재개발", "재개발", b.redev]] as [string, string, number][])
        .filter(([, v, n]) => v === "" || n > 0)
    : [["전체", "", 0]];

  const ql = q.trim();
  const filtered = (items || []).filter((l) => !ql
    || (l.complex_name || "").includes(ql) || (l.building_name || "").includes(ql)
    || (l.address || "").includes(ql) || (l.area_name || "").includes(ql));
  const visible = filtered.slice(0, shown);

  return (
    <>
      <div className="section-title">보유 매물</div>
      <div className="rl-cats">
        {chips.map(([label, v, n]) => (
          <button key={v || "all"} className={cat === v ? "on" : ""} onClick={() => { setCat(v); setQ(""); }}>
            {label}{n > 0 && <em>{n.toLocaleString()}</em>}
          </button>
        ))}
      </div>
      <div className="rl-filterbar">
        <div className="rl-trades">
          {([["", "전체"], ["매매", "매매"], ["전세", "전세"], ["월세", "월세"]] as const).map(([k, l]) => (
            <button key={k || "all"} className={trade === k ? "on" : ""} onClick={() => setTrade(k)}>{l}</button>
          ))}
        </div>
        <select className="rl-sort" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="confirm">최신확인순</option>
          <option value="price_desc">가격↓</option>
          <option value="price_asc">가격↑</option>
        </select>
        <div className="rl-search">
          <Search size={14} aria-hidden />
          <input placeholder="단지·건물·지역 검색" value={q} onChange={(e) => setQ(e.target.value)} />
          {q && <button onClick={() => setQ("")} aria-label="지우기"><X size={13} /></button>}
        </div>
      </div>
      {!items ? <div className="muted" style={{ padding: 16 }}>불러오는 중…</div>
        : filtered.length === 0 ? <div className="dong-empty">표시할 매물이 없습니다.</div>
        : (
          <>
            <div className="rl-count">총 <b>{filtered.length.toLocaleString()}</b>개 {visible.length < filtered.length && `· ${visible.length}개 표시`}</div>
            <div className="rl-listings">
              {visible.map((l) => (
                <a key={l.article_no} className="rl-lcard" href={l.naver_url} target="_blank" rel="noreferrer">
                  <div className="rl-lc-head">
                    <span className={`mlj-trade tr-${l.trade_type}`}>{l.trade_type}</span>
                    <span className="rl-lc-type">{l.type}</span>
                    <b className="rl-lc-title">{l.complex_name || l.building_name || l.area_name || "매물"}</b>
                    <span className="rl-lc-price">{l.trade_type === "월세" && l.rent_price_text ? `${l.price_text}/${l.rent_price_text}` : l.price_text}</span>
                  </div>
                  {l.address && <div className="rl-lc-addr"><MapPin size={11} aria-hidden /> {l.address}</div>}
                  <div className="rl-lc-meta">
                    {[l.area2_m2 ? `전용 ${l.area2_m2}㎡` : "", l.floor_info ? `${l.floor_info}층` : "",
                      l.direction, l.confirm_ymd ? `확인 ${rlFmtYmd(l.confirm_ymd)}` : ""].filter(Boolean).join(" · ")}
                  </div>
                </a>
              ))}
            </div>
            {visible.length < filtered.length && (
              <button className="rl-more" onClick={() => setShown((s) => s + RL_PAGE * 2)}>
                더보기 ({(filtered.length - visible.length).toLocaleString()}개 더)
              </button>
            )}
          </>
        )}
      <p className="muted" style={{ fontSize: 11, marginTop: 8 }}>네이버 매물 기준 · 카드를 누르면 네이버 매물로 이동 (유형당 최대 1,500건)</p>
    </>
  );
}
