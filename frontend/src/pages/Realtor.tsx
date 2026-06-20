import { useEffect, useState } from "react";
import { MapPin, Phone, Smartphone, MessageSquare } from "lucide-react";
import { Loading } from "../components/Loading";
import { RealtorReviews } from "../components/RealtorReviews";
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

type RealtorDetail = {
  realtor_id: string;
  realtor_name: string | null;
  total_count: number;
  national_rank: number;
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
  const [reviewCount, setReviewCount] = useState<number | null>(null);

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

  const tradeTotals = data.by_complex.reduce(
    (acc, r) => ({ A1: acc.A1 + r.A1, B1: acc.B1 + r.B1, B2: acc.B2 + r.B2 }),
    { A1: 0, B1: 0, B2: 0 },
  );
  const grandTotal = tradeTotals.A1 + tradeTotals.B1 + tradeTotals.B2;

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
              <button type="button" className="review-jump-btn" onClick={scrollToReviews}>
                <MessageSquare size={13} strokeWidth={2.3} aria-hidden /> 리뷰
                <span className="review-jump-count">{reviewCount ?? 0}</span>
              </button>
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
        <div className="stat-box">
          <div className="stat-label">전체 매물</div>
          <div className="stat-value">{grandTotal.toLocaleString()}</div>
          <div className="stat-sub">{data.by_complex.length}개 단지</div>
        </div>
        {data.vworld?.employees && data.vworld.employees.total > 0 && (
          <div className="stat-box">
            <div className="stat-label">소속 인원</div>
            <div className="stat-value">{data.vworld.employees.total}<span style={{ fontSize: 14 }}>명</span></div>
            <div className="stat-sub">
              공인중개사 {data.vworld.employees.licensed}
              {data.vworld.employees.assistant > 0 && `, 중개보조 ${data.vworld.employees.assistant}`}
            </div>
          </div>
        )}
        <div className="stat-box">
          <div className="stat-label">전국매물수 기준</div>
          <div className="stat-value">#{data.national_rank.toLocaleString()}</div>
          <div className="stat-sub">{data.national_total.toLocaleString()}개 중</div>
        </div>
        {data.by_sido[0] && (
          <div className="stat-box">
            <div className="stat-label">{data.by_sido[0].sido_name}매물수 기준</div>
            <div className="stat-value">#{data.by_sido[0].rank.toLocaleString()}</div>
            <div className="stat-sub">{data.by_sido[0].total_in_sido.toLocaleString()}개 중</div>
          </div>
        )}
      </div>

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

      {/* ── 단지별 매물 ── */}
      <div className="section-title">단지별 보유 매물 ({data.by_complex.length}개 단지)</div>
      <table>
        <thead>
          <tr>
            <th>단지</th>
            <th className="num">매매</th>
            <th className="num">전세</th>
            <th className="num">월세</th>
            <th className="num">합계</th>
          </tr>
        </thead>
        <tbody>
          {data.by_complex.map((r) => (
            <tr key={r.complex_no ?? "__none__"}>
              <td>
                {r.complex_no ? (
                  <Link to={`/complex/${r.complex_no}`}>{r.complex_name ?? r.complex_no}</Link>
                ) : (r.complex_name ?? "—")}
              </td>
              <td className="num" style={{ color: r.A1 ? "#c0392b" : "#ccc" }}>{r.A1 || ""}</td>
              <td className="num" style={{ color: r.B1 ? "#1268d3" : "#ccc" }}>{r.B1 || ""}</td>
              <td className="num" style={{ color: r.B2 ? "#27ae60" : "#ccc" }}>{r.B2 || ""}</td>
              <td className="num" style={{ fontWeight: 700 }}>{r.total}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* ── 중개사무소 리뷰 ── */}
      <RealtorReviews realtorId={data.realtor_id} onSummary={setReviewCount} />

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
