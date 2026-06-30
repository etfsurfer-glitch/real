import React, { useEffect, useMemo, useState } from "react";
import { Flame, ExternalLink, Phone, MapPin } from "lucide-react";
import { Loading } from "../components/Loading";
import { Link, useParams } from "react-router-dom";
import ComplexDashboard from "./ComplexDashboard";
import { usePageMeta } from "../lib/pageMeta";
import ComplexReviews from "../components/ComplexReviews";
import FavButton from "../components/FavButton";
import {
  CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { supabase, TRADE_LABEL } from "../supabase";

type Complex = {
  complex_no: string;
  complex_name: string;
  total_household_count: number | null;
  total_building_count: number | null;
  use_approve_ymd: string | null;
  detail_address: string | null;
  road_address: string | null;
  dong_name: string | null;
  latitude: number | null;
  longitude: number | null;
};

type AggRow = {
  area_name: string;
  trade_type: string;
  listing_count: number;
  price_min: number | null;
  price_max: number | null;
  price_avg: number | null;
  rent_min: number | null;
  rent_max: number | null;
  rent_avg: number | null;
};

type TrendRow = {
  snapshot_date: string;
  trade_type: string;
  area_name: string | null;
  listing_count: number;
  price_avg: number | null;
  rent_avg: number | null;
};

type AreaType = {
  pyeong_name: string | null;
  supply_area: number | null;
  exclusive_area: number | null;
  household_count: number | null;
};
type AreaResp = { complex_no: string; items: AreaType[] };


type Sale = {
  deal_ymd: string;
  deal_amount: number;
  excl_use_ar: number | null;
  floor: number | null;
  dealing_gbn: string | null;
  build_year: number | null;
  asset: "apt" | "offi";
  dong: string | null;          // 동 (아파트 매매만, 등기완료 시 공개)
  registered: boolean;          // 등기완료 여부
};

// 동 표기 정규화: "171" → "171동", "102동" → 그대로, "라" → "라동"
function dongLabel(dong: string | null): string {
  if (!dong) return "";
  const d = dong.trim();
  return d.endsWith("동") ? d : `${d}동`;
}

// 등기완료/미등기 + 동 셀 (아파트 매매만 의미 있음)
function RegiCell({ registered, dong, asset }: { registered: boolean; dong: string | null; asset: "apt" | "offi" }) {
  if (asset === "offi") return <span className="muted">-</span>;
  if (registered) {
    return (
      <span style={{ whiteSpace: "nowrap" }}>
        <span className="ctx-badge" style={{ background: "#e6f7ed", color: "#1a7f4b" }}>등기완료</span>
        {dong && <span style={{ marginLeft: 6, fontWeight: 600 }}>{dongLabel(dong)}</span>}
      </span>
    );
  }
  return <span className="ctx-badge" style={{ background: "#eef2f5", color: "#888" }}>미등기</span>;
}

type Rent = {
  deal_ymd: string;
  deposit: number;
  monthly_rent: number;
  excl_use_ar: number | null;
  floor: number | null;
  build_year: number | null;
  contract_type: string | null;
  contract_term: string | null;
  use_rr_right: string | null;
  pre_deposit: number | null;
  pre_monthly_rent: number | null;
  asset: "apt" | "offi";
};

type Silv = {
  deal_ymd: string;
  deal_amount: number;
  excl_use_ar: number | null;
  floor: number | null;
  dealing_gbn: string | null;
  kind: string;   // '분양권' | '입주권'
};

// 매매 실거래 행 — 일반 매매(silv_kind 없음) + 분양권/입주권(silv_kind) 통합. 분양권은 레코드별 뱃지로 구분.
type SaleRow = Sale & { silv_kind?: string };

/** 일반 매매 + 분양권/입주권을 하나의 매매 실거래 리스트로 통합(계약일 내림차순). 분양권 거래금액은
 *  실제 총거래액이라 매매와 같은 scale → 함께 보여도 왜곡 없음(해제건은 백엔드에서 이미 제외). */
function mergeSaleSilv(sale: Sale[], silv?: Silv[]): SaleRow[] {
  const rows: SaleRow[] = sale.map((r) => ({ ...r }));
  for (const v of silv ?? []) {
    rows.push({
      deal_ymd: v.deal_ymd, deal_amount: v.deal_amount, excl_use_ar: v.excl_use_ar,
      floor: v.floor, dealing_gbn: v.dealing_gbn, build_year: null, asset: "apt",
      dong: null, registered: false, silv_kind: v.kind || "분양권",
    });
  }
  return rows.sort((a, b) => b.deal_ymd.localeCompare(a.deal_ymd));
}

type TxBundle = { complex_no: string; months: number; sale: Sale[]; jeonse: Rent[]; wolse: Rent[]; silv?: Silv[] };

type RealtorRow = {
  realtor_id: string;
  realtor_name: string | null;
  count: number;
  n_sale: number | null;
  n_jeonse: number | null;
  n_wolse: number | null;
  avg_sale_price: number | null;
  sido: string | null;
  established_year: string | null;
  staff_count: number | null;
  tel: string | null;
  total_listings: number | null;
};
type RealtorResp = { complex_no: string; items: RealtorRow[] };

type DealRow = {
  article_no: string;
  area_name: string;
  floor_info: string | null;
  direction: string | null;
  price: number;
  price_text: string | null;
  discount: number;          // 음수 (예: -0.068)
  avg_real: number;
  n_real: number;
  realtor_id: string | null;
  realtor_name: string | null;
  tel: string | null;
  addr: string | null;
  confirm_ymd: string | null;
  article_url: string | null;
  naver_url: string | null;
  dong: string | null;
  dup_count?: number;        // 동일매물 묶인 게시물 수
  realtor_count?: number;    // 동일매물 보유 중개사무소 수
};
type DealResp = { complex_no: string; count: number; items: DealRow[] };


const API_BASE = import.meta.env.VITE_API_BASE;

function formatWon(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 100_000_000) {
    const eok = Math.floor(v / 100_000_000);
    const man = Math.floor((v % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(v / 10_000).toLocaleString()}만`;
}

function describeError(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (e && typeof e === "object") {
    const o = e as Record<string, unknown>;
    const parts = [o.message, o.details, o.hint, o.code].filter(Boolean);
    if (parts.length) return parts.join(" · ");
    try { return JSON.stringify(e); } catch { /* ignore */ }
  }
  return String(e);
}

export default function ComplexDetail() {
  const { complexNo } = useParams();
  const [complex, setComplex] = useState<Complex | null>(null);
  const [agg, setAgg] = useState<AggRow[]>([]);
  const [trend, setTrend] = useState<TrendRow[]>([]);
  const [snapshotDate, setSnapshotDate] = useState<string | null>(null);
  const [tx, setTx] = useState<TxBundle | null>(null);
  // 분양권/입주권은 별도 탭이 아니라 매매 실거래에 통합(레코드별 뱃지) — 사용자에겐 "실거래" 하나.
  const [txTab, setTxTab] = useState<"A1" | "B1" | "B2">("A1");
  const [section, setSection] = useState<"summary" | "info" | "tx" | "nearby" | "trend" | "realtor" | "review">("summary");
  const [realtors, setRealtors] = useState<RealtorRow[] | null>(null);
  const [deals, setDeals] = useState<DealRow[] | null>(null);
  const [areaTypes, setAreaTypes] = useState<AreaType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 단지별 동적 메타(검색 색인용) — 본문은 그대로, head 의 제목/설명만 단지에 맞게
  const cname = complex?.complex_name;
  const cregion = complex?.dong_name || "";
  usePageMeta(
    cname ? `${cname} 시세·실거래가·매물 | 콕집` : undefined,
    cname ? `${cname}${cregion ? " " + cregion : ""} 아파트 시세, 실거래가, 매물 호가, 세대수 정보를 콕집에서 한눈에 확인하세요.` : undefined,
    complexNo ? `/complex/${complexNo}` : undefined,
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!complexNo) return;
      try {
        const latestRes = await supabase
          .from("complex_daily_agg")
          .select("snapshot_date")
          .eq("complex_no", complexNo)
          .order("snapshot_date", { ascending: false })
          .limit(1);
        if (latestRes.error) throw latestRes.error;
        const date = latestRes.data?.[0]?.snapshot_date ?? null;
        if (cancelled) return;
        setSnapshotDate(date);

        const cplxRes = await supabase
          .from("complexes")
          .select("*")
          .eq("complex_no", complexNo)
          .single();
        if (cplxRes.error) throw cplxRes.error;
        if (cancelled) return;
        setComplex(cplxRes.data as Complex);

        if (date) {
          const aggRes = await supabase
            .from("complex_daily_agg")
            .select("*")
            .eq("complex_no", complexNo)
            .eq("snapshot_date", date);
          if (aggRes.error) throw aggRes.error;
          if (cancelled) return;
          setAgg((aggRes.data ?? []) as AggRow[]);
        }

        // 매물가격 변동 이력 (전체 스냅샷)
        const trendRes = await supabase
          .from("complex_daily_agg")
          .select("snapshot_date, trade_type, area_name, listing_count, price_avg, rent_avg")
          .eq("complex_no", complexNo)
          .order("snapshot_date", { ascending: true });
        if (trendRes.error) throw trendRes.error;
        if (cancelled) return;
        setTrend((trendRes.data ?? []) as unknown as TrendRow[]);

        // 실거래 이력 + 중개사 랭킹 (로컬 API에서만 제공)
        if (API_BASE) {
          try {
            const r = await fetch(`${API_BASE}/complex/${complexNo}/transactions?months=24`);
            if (r.ok && !cancelled) setTx(await r.json());
          } catch { /* ignore */ }
          try {
            const r = await fetch(`${API_BASE}/complex/${complexNo}/realtors?limit=10`);
            if (r.ok && !cancelled) {
              const j = (await r.json()) as RealtorResp;
              setRealtors(j.items);
            }
          } catch { /* ignore */ }
          try {
            const r = await fetch(`${API_BASE}/complex/${complexNo}/areas`);
            if (r.ok && !cancelled) {
              const j = (await r.json()) as AreaResp;
              setAreaTypes(j.items);
            }
          } catch { /* ignore */ }
          try {
            const r = await fetch(`${API_BASE}/complex/${complexNo}/quick-deals?min_discount=0.05`);
            if (r.ok && !cancelled) {
              const j = (await r.json()) as DealResp;
              setDeals(j.items);
            }
          } catch { /* ignore */ }
        }

        setLoading(false);
      } catch (e: unknown) {
        if (!cancelled) {
          setError(describeError(e));
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [complexNo]);

  if (loading) return <Loading />;
  if (error) return <div style={{ color: "crimson" }}>오류: {error}</div>;
  if (!complex) return <div className="muted">단지를 찾지 못했습니다.</div>;

  const tradeAggs: Record<string, AggRow[]> = { A1: [], B1: [], B2: [] };
  for (const r of agg) {
    if (tradeAggs[r.trade_type]) tradeAggs[r.trade_type].push(r);
  }
  for (const k of Object.keys(tradeAggs)) {
    tradeAggs[k].sort((a, b) => b.listing_count - a.listing_count);
  }
  // 면적타입 → 세대수 매핑 (complex_areas)
  const householdByType: Record<string, number> = {};
  for (const a of areaTypes) {
    if (a.pyeong_name && a.household_count != null) householdByType[a.pyeong_name] = a.household_count;
  }

  return (
    <>
      <Link to="/overview" className="back">← 전국현황</Link>
      <div className="cx-title-row">
        <h2 style={{ margin: "0 0 4px" }}>{complex.complex_name}</h2>
        {complexNo && <FavButton complexNo={complexNo} complexName={complex.complex_name} />}
      </div>
      <div className="muted" style={{ marginBottom: 14 }}>
        {(complex.road_address
          || [complex.dong_name, complex.detail_address].filter(Boolean).join(" ")
          || "주소 미상")} · 세대 {complex.total_household_count ?? "?"} · 동{" "}
        {complex.total_building_count ?? "?"} · 준공 {complex.use_approve_ymd?.slice(0, 4) ?? "?"}{" "}
        · 기준 {snapshotDate ?? "-"}
      </div>

      {/* 소메뉴 탭 — 세로로 길던 섹션들을 탭으로 분리 */}
      <nav className="sub-nav">
        {([
          ["summary", "종합"],
          ["info", "시세"],
          ["tx", "실거래"],
          ["nearby", "인근단지"],
          ["trend", "호가추이"],
          ["realtor", "중개사무소"],
          ["review", "리뷰"],
        ] as const).map(([k, label]) => (
          <button key={k} type="button"
            className={section === k ? "active" : ""}
            onClick={() => setSection(k)}>
            {label}
          </button>
        ))}
      </nav>

      {section === "summary" && complexNo && (
        <>
          <ComplexDashboard complexNo={complexNo} onGo={setSection} />
          <NearbyTransactions complexNo={complexNo} />
        </>
      )}

      {section === "nearby" && complexNo && <NearbyTransactions complexNo={complexNo} />}

      {section === "info" && (
        <>
          {deals && deals.length > 0 && <QuickDealSection deals={deals} />}
          {(["A1", "B1", "B2"] as const).map((t) => (
            <AreaAggSection key={t} tradeType={t} rows={tradeAggs[t]} householdByType={householdByType} />
          ))}
        </>
      )}

      {section === "tx" && (
        tx ? (
          <>
            <div className="section-title" style={{ marginTop: 4 }}>
              실거래 이력 (최근 {tx.months}개월, 국토부 신고 기준)
            </div>
            <div className="chip-row" style={{ marginBottom: 12 }}>
              {(() => {
                const saleN = tx.sale.length + (tx.silv?.length ?? 0);  // 매매+분양권 통합 카운트
                return [
                  ["A1", `매매 (${saleN})`],
                  ["B1", `전세 (${tx.jeonse.length})`],
                  ["B2", `월세 (${tx.wolse.length})`],
                ] as const;
              })().map(([k, label]) => (
                <button key={k} type="button"
                  className={`chip ${txTab === k ? "active" : ""}`}
                  onClick={() => setTxTab(k)}>
                  {label}
                </button>
              ))}
            </div>
            {txTab === "A1" && <SaleSection rows={mergeSaleSilv(tx.sale, tx.silv)} />}
            {txTab === "B1" && <RentSection rows={tx.jeonse} kind="jeonse" />}
            {txTab === "B2" && <RentSection rows={tx.wolse} kind="wolse" />}
          </>
        ) : <div className="muted">실거래 이력을 불러올 수 없습니다.</div>
      )}

      {section === "trend" && (
        trend.length > 0 ? <PriceTrendSection trend={trend} />
          : <div className="muted">가격 변동 이력이 없습니다.</div>
      )}

      {section === "realtor" && (
        realtors && realtors.length > 0 ? (
          <>
            <div className="section-title" style={{ marginTop: 4 }}>이 단지 매물을 많이 가진 중개사무소</div>
            <table>
              <thead>
                <tr>
                  <th style={{ width: 32 }}>#</th><th>중개사무소</th><th>전화</th>
                  <th className="num">매매</th><th className="num">전세</th><th className="num">월세</th>
                  <th className="num">총 매물</th><th className="num">전국 보유</th>
                </tr>
              </thead>
              <tbody>
                {realtors.map((r, i) => {
                  const meta = [
                    r.sido,
                    r.established_year ? `${r.established_year}년 개업` : null,
                    r.staff_count ? `직원 ${r.staff_count}명` : null,
                  ].filter(Boolean).join(" · ");
                  const telDigits = r.tel ? r.tel.replace(/[^0-9+]/g, "") : "";
                  return (
                    <tr key={r.realtor_id}>
                      <td style={{ color: "#999" }}>{i + 1}</td>
                      <td style={{ fontSize: 13 }}>
                        <Link to={`/realtor/${encodeURIComponent(r.realtor_id)}`}>
                          {r.realtor_name ?? r.realtor_id}
                        </Link>
                        {meta && <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{meta}</div>}
                      </td>
                      <td style={{ fontSize: 13 }}>
                        {r.tel ? <a href={`tel:${telDigits}`} style={{ color: "#1268d3", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4, whiteSpace: "nowrap" }}><Phone size={12} strokeWidth={2.4} aria-hidden /> {r.tel}</a>
                          : <span className="muted">-</span>}
                      </td>
                      <td className="num">{r.n_sale ?? 0}</td>
                      <td className="num">{r.n_jeonse ?? 0}</td>
                      <td className="num">{r.n_wolse ?? 0}</td>
                      <td className="num" style={{ fontWeight: 600 }}>{r.count.toLocaleString()}</td>
                      <td className="num muted">{r.total_listings?.toLocaleString() ?? "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        ) : <div className="muted">이 단지 매물 보유 중개사무소 정보가 없습니다.</div>
      )}

      {section === "review" && complexNo && <ComplexReviews complexNo={complexNo} />}
    </>
  );
}

type NearbyDeal = { deal_ymd: string; deal_amount: number | null; excl_use_ar: number | null; floor: number | null };
type NearbyComplex = {
  complex_no: string; complex_name: string; dong_name: string | null; distance_m: number;
  households: number | null; use_approve_ymd: string | null;
  deal_count: number; avg_amount: number | null; max_amount: number | null;
  all_time_max: number | null; recent: NearbyDeal[];
};

// 사용승인 "202608"/"20140403" → "2026.08"
function fmtApprove(v: string | null): string {
  if (!v) return "";
  const s = String(v);
  if (s.length >= 6) return `${s.slice(0, 4)}.${s.slice(4, 6)}`;
  return s;
}
type NearbyAreaOpt = { pyeong_name: string; exclusive_area: number; household_count: number | null };
type NearbyResp = { target_name: string | null; areas: NearbyAreaOpt[]; nearby: NearbyComplex[] };

// 단지상세 맨 아래 — 반경 내 같은유형 단지의 최근 매매 실거래(평형 선택 가능).
function NearbyTransactions({ complexNo }: { complexNo: string }) {
  const [data, setData] = useState<NearbyResp | null>(null);
  const [area, setArea] = useState(0); // 0 = 전체 평형
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (!API_BASE || !complexNo) return;
    let alive = true;
    setLoading(true);
    fetch(`${API_BASE}/complex/${complexNo}/nearby-transactions?area=${area}&months=12&radius_km=1.5&limit=12`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive) setData(j); })
      .catch(() => { if (alive) setData(null); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [complexNo, area]);

  if (!API_BASE) return null;
  const areas = data?.areas ?? [];
  // 전용면적 기준으로 묶기 — 같은 전용은 하나로(타입 A/B/C 분리 안 함). [반올림㎡, 대표전용]
  const areaChips: [number, number][] = [];
  const seenAreas = new Set<number>();
  for (const a of areas) {
    const k = Math.round(a.exclusive_area);
    if (!seenAreas.has(k)) { seenAreas.add(k); areaChips.push([k, a.exclusive_area]); }
  }
  areaChips.sort((x, y) => x[0] - y[0]);
  // 전체평형이면 거리순 전부, 특정평형이면 그 평형 거래 있는 단지만.
  const shown = (data?.nearby ?? []).filter((n) => area === 0 || n.deal_count > 0);

  return (
    <div style={{ marginTop: 18 }}>
      <div className="cdash-h">
        <h3><MapPin size={15} strokeWidth={2.3} /> 인근 단지 실거래{" "}
          <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>· 반경 1.5km · 최근 12개월 매매</span>
        </h3>
      </div>
      <div className="chip-row" style={{ marginBottom: 12, flexWrap: "wrap", gap: 6 }}>
        <button type="button" className={`chip ${area === 0 ? "active" : ""}`} onClick={() => setArea(0)}>전체 평형</button>
        {areaChips.map(([k, ex]) => (
          <button type="button" key={k}
            className={`chip ${area === ex ? "active" : ""}`}
            onClick={() => setArea(ex)}>
            전용 {k}㎡
          </button>
        ))}
      </div>
      {loading ? (
        <div className="muted">불러오는 중…</div>
      ) : shown.length === 0 ? (
        <div className="muted">인근 단지 실거래가 없습니다{area > 0 ? " (이 평형)" : ""}.</div>
      ) : (
        <table style={{ tableLayout: "fixed" }}>
          <thead>
            <tr>
              <th>단지</th>
              <th className="num" style={{ width: 84 }}>최고</th>
              <th className="num" style={{ width: 84 }}>평균</th>
              <th className="num" style={{ width: 48 }}>거래</th>
              <th className="num" style={{ width: 60 }}>거리</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((n) => (
              <React.Fragment key={n.complex_no}>
                <tr style={{ cursor: "pointer" }}
                  onClick={() => setOpen(open === n.complex_no ? null : n.complex_no)}>
                  <td>
                    <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      <span className="muted" style={{ marginRight: 4, fontSize: 11 }}>{open === n.complex_no ? "▾" : "▸"}</span>
                      <span style={{ fontWeight: 600 }}>{n.complex_name}</span>
                      {n.dong_name && <span className="muted" style={{ fontSize: 11, marginLeft: 4 }}>{n.dong_name}</span>}
                    </div>
                    {(n.households || n.use_approve_ymd) && (
                      <div className="muted" style={{ fontSize: 10, marginLeft: 16, lineHeight: 1.4 }}>
                        {n.households ? `${n.households.toLocaleString()}세대` : ""}
                        {n.households && n.use_approve_ymd ? " · " : ""}
                        {n.use_approve_ymd ? `사용승인 ${fmtApprove(n.use_approve_ymd)}` : ""}
                      </div>
                    )}
                  </td>
                  <td className="num">{formatWon(n.max_amount)}</td>
                  <td className="num">{formatWon(n.avg_amount)}</td>
                  <td className="num">{n.deal_count || "-"}</td>
                  <td className="num muted">{n.distance_m < 1000 ? `${n.distance_m}m` : `${(n.distance_m / 1000).toFixed(1)}km`}</td>
                </tr>
                {open === n.complex_no && (
                  <>
                    {n.recent.map((d, i) => (
                      <tr key={i} style={{ background: "#fafbfc", fontSize: 12 }}>
                        <td className="muted" style={{ paddingLeft: 20 }}>
                          {d.deal_ymd} · {d.floor != null ? `${d.floor}층` : "-"} · {d.excl_use_ar != null ? `${Math.round(d.excl_use_ar)}㎡` : ""}
                        </td>
                        <td className="num" colSpan={4} style={{ fontWeight: 600 }}>
                          {formatWon(d.deal_amount)}
                          {n.all_time_max != null && d.deal_amount != null && d.deal_amount >= n.all_time_max && (
                            <span style={{
                              marginLeft: 4, fontSize: 10, fontWeight: 700, color: "#d4380d",
                              background: "#fff1f0", border: "1px solid #ffccc7",
                              borderRadius: 4, padding: "0 4px", whiteSpace: "nowrap",
                            }}>역대최고</span>
                          )}
                        </td>
                      </tr>
                    ))}
                    <tr style={{ background: "#fafbfc" }}>
                      <td colSpan={5} style={{ paddingLeft: 20, paddingTop: 4, paddingBottom: 7 }}>
                        {n.deal_count === 0 && <span className="muted" style={{ fontSize: 12, marginRight: 10 }}>최근 12개월 거래 없음</span>}
                        <Link to={`/complex/${n.complex_no}`} className="chip" style={{ fontSize: 12 }}>
                          해당 단지 상세보기 →
                        </Link>
                      </td>
                    </tr>
                  </>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const AGG_DEFAULT_LIMIT = 5;

function AreaAggSection({
  tradeType, rows, householdByType,
}: {
  tradeType: "A1" | "B1" | "B2";
  rows: AggRow[];
  householdByType: Record<string, number>;
}) {
  const [expanded, setExpanded] = useState(false);
  const priceLabel = tradeType === "A1" ? "매매가" : "보증금";
  const visible = expanded ? rows : rows.slice(0, AGG_DEFAULT_LIMIT);
  const hiddenCount = rows.length - visible.length;

  return (
    <div style={{ marginBottom: 28 }}>
      <div className="section-title">
        <span className={`badge ${tradeType.toLowerCase()}`}>{TRADE_LABEL[tradeType]}</span>{" "}
        면적타입별 집계
      </div>
      {rows.length === 0 ? (
        <div className="muted">매물 없음</div>
      ) : (
        <>
          <table style={{ tableLayout: "fixed" }}>
            <thead>
              <tr>
                <th>면적타입</th>
                <th className="num">세대수</th>
                <th className="num">매물</th>
                <th className="num">{priceLabel} 최저</th>
                <th className="num">{priceLabel} 최고</th>
                <th className="num">{priceLabel} 평균</th>
                {tradeType === "B2" && <th className="num">월세 최저</th>}
                {tradeType === "B2" && <th className="num">월세 최고</th>}
                {tradeType === "B2" && <th className="num">월세 평균</th>}
              </tr>
            </thead>
            <tbody>
              {visible.map((r) => (
                <tr key={`${tradeType}-${r.area_name}`}>
                  <td>{r.area_name || "-"}</td>
                  <td className="num muted">{householdByType[r.area_name]?.toLocaleString() ?? "-"}</td>
                  <td className="num">{r.listing_count}</td>
                  <td className="num">{formatWon(r.price_min)}</td>
                  <td className="num">{formatWon(r.price_max)}</td>
                  <td className="num">{formatWon(r.price_avg)}</td>
                  {tradeType === "B2" && <td className="num">{formatWon(r.rent_min)}</td>}
                  {tradeType === "B2" && <td className="num">{formatWon(r.rent_max)}</td>}
                  {tradeType === "B2" && <td className="num">{formatWon(r.rent_avg)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > AGG_DEFAULT_LIMIT && (
            <button
              type="button"
              className="chip"
              style={{ marginTop: 8 }}
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "접기" : `더보기 (+${hiddenCount})`}
            </button>
          )}
        </>
      )}
    </div>
  );
}

/** 면적타입별·매물유형별 평균가격 변동표. complex_daily_agg 의 전체 스냅샷을
 *  날짜 컬럼으로 펼쳐, 각 면적타입의 평균가가 어떻게 변했는지 보여준다. */
// 네이버 매물을 별도 팝업창(window.open)으로 — 탭이 아닌 작은 창으로 열려 내 페이지는 뒤에 남는다.
function openListingPopup(url: string) {
  const w = 900, h = 860;
  const left = window.screenX + Math.max(0, (window.outerWidth - w) / 2);
  const top = window.screenY + Math.max(0, (window.outerHeight - h) / 2);
  const win = window.open(
    url, "kokzip_listing",
    `popup=yes,width=${w},height=${h},left=${left},top=${top},scrollbars=yes,resizable=yes`,
  );
  if (!win) window.open(url, "_blank", "noopener");   // 팝업 차단 시 새 탭 폴백
}

function QuickDealSection({ deals }: { deals: DealRow[] }) {
  return (
    <>
      <div className="section-title" style={{ marginTop: 28 }}>
        <Flame size={15} strokeWidth={2.4} style={{ color: "#e8590c" }} aria-hidden /> 급매 보유 중개사무소{" "}
        <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}>
          (최근 실거래 평균 대비 5%↑ 저렴 · {deals.length}건 · 동일매물 묶음)
        </span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>평형</th>
              <th>층</th>
              <th className="num">호가</th>
              <th className="num">실거래 평균</th>
              <th className="num">할인율</th>
              <th>급매 보유 중개사무소</th>
              <th>전화</th>
              <th>매물</th>
            </tr>
          </thead>
          <tbody>
            {deals.map((d) => (
              <tr key={d.article_no}>
                <td>{d.area_name}</td>
                <td>{d.floor_info ?? "-"}</td>
                <td className="num">{d.price_text || formatWon(d.price)}</td>
                <td className="num">{formatWon(d.avg_real)}</td>
                <td className="num" style={{ fontWeight: 700, color: "#d6336c" }}>
                  {`${Math.round(d.discount * 100)}%`}
                </td>
                <td>
                  {d.realtor_id
                    ? <Link to={`/realtor/${encodeURIComponent(d.realtor_id)}`}>{d.realtor_name ?? "-"}</Link>
                    : <span title="중개사무소 정보 없음 — '네이버 매물 보기'에서 연락처 확인"
                            style={{ borderBottom: "1px dotted #bbb", cursor: "help" }}>{d.realtor_name ?? "-"}</span>}
                  {d.realtor_count && d.realtor_count > 1 ? (
                    <span title={`같은 매물(동·층·평형·방향·가격 동일)을 ${d.realtor_count}개 중개사무소가 게시`}
                      style={{ marginLeft: 6, fontSize: 11, fontWeight: 700, color: "#1268d3",
                        background: "#eef4ff", border: "1px solid #cfe0ff", borderRadius: 10, padding: "1px 6px", whiteSpace: "nowrap" }}>
                      외 {d.realtor_count - 1}곳
                    </span>
                  ) : null}
                </td>
                <td>
                  {d.tel
                    ? <a href={`tel:${d.tel}`} style={{ whiteSpace: "nowrap" }}>{d.tel}</a>
                    : <span className="muted">-</span>}
                </td>
                <td>
                  {(d.naver_url || d.article_url)
                    ? <button className="nv-btn" onClick={() => openListingPopup((d.naver_url || d.article_url) as string)}>
                        <ExternalLink size={11} strokeWidth={2.4} aria-hidden /> 네이버 매물 보기
                      </button>
                    : <span className="muted">-</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function PriceTrendSection({ trend }: { trend: TrendRow[] }) {
  const [tab, setTab] = useState<"A1" | "B1" | "B2">("A1");
  const priceLabel = tab === "A1" ? "매매가" : "보증금";

  // 해당 거래유형 행만 추리고, 주차·면적타입별 평균가 인덱싱.
  // 날짜별은 의미가 약해 "5월 1주/2주…" 주차 단위로 묶는다.
  const rows = trend.filter((r) => r.trade_type === tab);

  // snapshot_date → 월·주차 버킷 ("2026-05-W2", 라벨 "5월 2주")
  const weekOf = (d: string) => {
    const day = parseInt(d.slice(8, 10), 10);
    const wk = Math.min(5, Math.ceil(day / 7));
    return { key: `${d.slice(0, 7)}-W${wk}`, label: `${parseInt(d.slice(5, 7), 10)}월 ${wk}주` };
  };
  const weekLabel: Record<string, string> = {};
  const dateToWeek: Record<string, string> = {};
  for (const d of Array.from(new Set(rows.map((r) => r.snapshot_date)))) {
    const w = weekOf(d);
    weekLabel[w.key] = w.label;
    dateToWeek[d] = w.key;
  }
  // 컬럼이 너무 많아지면 최근 8주만
  const shownWeeks = Object.keys(weekLabel).sort().slice(-8);
  const areas = Array.from(new Set(rows.map((r) => r.area_name ?? "-")));
  // (area_name|week) → 그 주 스냅샷 평균가들의 평균
  const acc: Record<string, { s: number; n: number }> = {};
  for (const r of rows) {
    if (r.price_avg == null) continue;
    const k = `${r.area_name ?? "-"}|${dateToWeek[r.snapshot_date]}`;
    if (!acc[k]) acc[k] = { s: 0, n: 0 };
    acc[k].s += r.price_avg;
    acc[k].n += 1;
  }
  const cell: Record<string, number | null> = {};
  for (const k of Object.keys(acc)) cell[k] = acc[k].n ? acc[k].s / acc[k].n : null;

  return (
    <>
      <div className="section-title" style={{ marginTop: 4 }}>
        면적타입별 평균 {priceLabel} 추이
      </div>
      <div className="chip-row" style={{ marginBottom: 12 }}>
        {([
          ["A1", "매매"],
          ["B1", "전세"],
          ["B2", "월세"],
        ] as const).map(([k, label]) => (
          <button
            key={k}
            type="button"
            className={`chip ${tab === k ? "active" : ""}`}
            onClick={() => setTab(k)}
          >
            {label}
          </button>
        ))}
      </div>
      {areas.length === 0 || shownWeeks.length === 0 ? (
        <div className="muted">변동 이력 없음</div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>면적타입</th>
                {shownWeeks.map((w) => (
                  <th key={w} className="num">{weekLabel[w]}</th>
                ))}
                <th className="num">변동</th>
              </tr>
            </thead>
            <tbody>
              {areas.map((a) => {
                const series = shownWeeks.map((w) => cell[`${a}|${w}`] ?? null);
                const first = series.find((v) => v != null) ?? null;
                const lastIdx = [...series].reverse().findIndex((v) => v != null);
                const last = lastIdx === -1 ? null : series[series.length - 1 - lastIdx];
                const pct =
                  first != null && last != null && first !== 0
                    ? ((last - first) / first) * 100
                    : null;
                return (
                  <tr key={a}>
                    <td>{a}</td>
                    {series.map((v, i) => (
                      <td key={i} className="num">{formatWon(v)}</td>
                    ))}
                    <td
                      className="num"
                      style={{
                        fontWeight: 600,
                        color: pct == null ? "#bbb" : pct > 0 ? "#c0392b" : pct < 0 ? "#1268d3" : "#888",
                      }}
                    >
                      {pct == null ? "—" : `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

const AREA_COLORS = ["#1268d3", "#c0392b", "#27ae60", "#e67e22", "#8e44ad",
                     "#16a085", "#f39c12", "#2c3e50", "#d35400", "#7f8c8d"];

/** 실거래 면적은 모두 전용면적 — 실제값(소수점 2자리)으로 그룹화해 전용면적을 그대로 보여준다. */
function areaKey(m2: number | null | undefined): number | null {
  if (m2 == null) return null;
  return Math.round(m2 * 100) / 100;
}

function m2ToPyeong(m2: number): number {
  return m2 / 3.3058;
}

function areaLabel(key: number): string {
  // 실거래 면적은 전용면적 기준 — '전용 OO.OO㎡'로 소수점까지 표시.
  return `전용 ${key.toFixed(2)}㎡ (${m2ToPyeong(key).toFixed(0)}평)`;
}

function ymdToTs(s: string): number {
  return new Date(s).getTime();
}

function AreaChipRow({
  groups, selected, onPick,
}: {
  groups: { key: number; count: number; color: string }[];
  selected: number | null;
  onPick: (k: number | null) => void;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "8px 0" }}>
      <button
        onClick={() => onPick(null)}
        style={chipStyle(selected === null, "#444")}
      >
        전체
      </button>
      {groups.map((g) => (
        <button
          key={g.key}
          onClick={() => onPick(g.key)}
          style={chipStyle(selected === g.key, g.color)}
        >
          {areaLabel(g.key)} ({g.count})
        </button>
      ))}
    </div>
  );
}

function chipStyle(active: boolean, color: string): React.CSSProperties {
  return {
    padding: "4px 12px",
    border: `1px solid ${active ? color : "#ccc"}`,
    borderRadius: 16,
    background: active ? color : "white",
    color: active ? "white" : "#333",
    cursor: "pointer",
    fontSize: 12,
  };
}

function priceFmt(v: number): string {
  if (v >= 100_000_000) return `${(v / 100_000_000).toFixed(1)}억`;
  return `${Math.round(v / 10_000).toLocaleString()}만`;
}

function SaleSection({ rows }: { rows: SaleRow[] }) {
  const [area, setArea] = useState<number | null>(null);

  const groups = useMemo(() => {
    const m = new Map<number, number>();
    for (const r of rows) {
      const k = areaKey(r.excl_use_ar);
      if (k != null) m.set(k, (m.get(k) ?? 0) + 1);
    }
    return Array.from(m.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([key, count], i) => ({ key, count, color: AREA_COLORS[i % AREA_COLORS.length] }));
  }, [rows]);

  const colorOf = useMemo(() => {
    const m = new Map<number, string>();
    for (const g of groups) m.set(g.key, g.color);
    return (k: number | null) => (k != null ? m.get(k) ?? "#888" : "#888");
  }, [groups]);

  const filtered = useMemo(() => {
    if (area == null) return rows;
    return rows.filter((r) => areaKey(r.excl_use_ar) === area);
  }, [rows, area]);

  if (rows.length === 0) return <div className="muted">최근 거래 없음</div>;

  return (
    <>
      <AreaChipRow groups={groups} selected={area} onPick={setArea} />
      <SaleChart rows={filtered} colorOf={colorOf} />
      <table>
        <thead>
          <tr>
            <th>계약일</th>
            <th className="num">전용(㎡)</th>
            <th className="num">층</th>
            <th className="num">금액</th>
            <th>형태</th>
            <th>등기</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((r, i) => (
            <tr key={i} className={r.silv_kind ? "tx-silv" : undefined}>
              <td>
                {r.deal_ymd}
                {r.silv_kind && <span className="ctx-badge tx-silv-badge">{r.silv_kind}</span>}
              </td>
              <td className="num">{r.excl_use_ar?.toFixed(2) ?? "-"}</td>
              <td className="num">{r.floor ?? "-"}</td>
              <td className="num">{formatWon(r.deal_amount)}</td>
              <td>{r.dealing_gbn ?? "-"}{r.asset === "offi" ? " · 오피스텔" : ""}</td>
              <td>{r.silv_kind ? <span className="muted">-</span> : <RegiCell registered={r.registered} dong={r.dong} asset={r.asset} />}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function RentSection({ rows, kind }: { rows: Rent[]; kind: "jeonse" | "wolse" }) {
  const [area, setArea] = useState<number | null>(null);

  const groups = useMemo(() => {
    const m = new Map<number, number>();
    for (const r of rows) {
      const k = areaKey(r.excl_use_ar);
      if (k != null) m.set(k, (m.get(k) ?? 0) + 1);
    }
    return Array.from(m.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([key, count], i) => ({ key, count, color: AREA_COLORS[i % AREA_COLORS.length] }));
  }, [rows]);

  const colorOf = useMemo(() => {
    const m = new Map<number, string>();
    for (const g of groups) m.set(g.key, g.color);
    return (k: number | null) => (k != null ? m.get(k) ?? "#888" : "#888");
  }, [groups]);

  const filtered = useMemo(() => {
    if (area == null) return rows;
    return rows.filter((r) => areaKey(r.excl_use_ar) === area);
  }, [rows, area]);

  if (rows.length === 0) return <div className="muted">최근 거래 없음</div>;

  return (
    <>
      <AreaChipRow groups={groups} selected={area} onPick={setArea} />
      <RentChart rows={filtered} kind={kind} colorOf={colorOf} />
      <table>
        <thead>
          <tr>
            <th>계약일</th>
            <th className="num">전용(㎡)</th>
            <th className="num">층</th>
            <th className="num">보증금</th>
            {kind === "wolse" && <th className="num">월세</th>}
            <th>구분</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((r, i) => (
            <tr key={i}>
              <td>{r.deal_ymd}</td>
              <td className="num">{r.excl_use_ar?.toFixed(2) ?? "-"}</td>
              <td className="num">{r.floor ?? "-"}</td>
              <td className="num">{formatWon(r.deposit)}</td>
              {kind === "wolse" && <td className="num">{formatWon(r.monthly_rent)}</td>}
              <td>{r.contract_type ?? "-"}{r.asset === "offi" ? " · 오피스텔" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

type ChartPoint = { ts: number; price: number; area: number; floor: number | null; date: string; direct: boolean };

function SaleChart({ rows, colorOf }: { rows: Sale[]; colorOf: (k: number | null) => string }) {
  const byArea = useMemo(() => {
    const m = new Map<number, ChartPoint[]>();
    for (const r of rows) {
      const k = areaKey(r.excl_use_ar);
      if (k == null) continue;
      const p: ChartPoint = { ts: ymdToTs(r.deal_ymd), price: r.deal_amount, area: k, floor: r.floor, date: r.deal_ymd, direct: r.dealing_gbn === "직거래" };
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(p);
    }
    for (const [, arr] of m) arr.sort((a, b) => a.ts - b.ts);
    return Array.from(m.entries()).sort((a, b) => a[0] - b[0]);
  }, [rows]);

  if (byArea.length === 0) return null;
  return <PriceScatter byArea={byArea} colorOf={colorOf} yLabel="금액" />;
}

function RentChart({ rows, kind, colorOf }: { rows: Rent[]; kind: "jeonse" | "wolse"; colorOf: (k: number | null) => string }) {
  const byArea = useMemo(() => {
    const m = new Map<number, ChartPoint[]>();
    for (const r of rows) {
      const k = areaKey(r.excl_use_ar);
      if (k == null) continue;
      const p: ChartPoint = {
        ts: ymdToTs(r.deal_ymd),
        price: kind === "wolse" ? r.monthly_rent : r.deposit,
        area: k, floor: r.floor, date: r.deal_ymd, direct: false,
      };
      if (!m.has(k)) m.set(k, []);
      m.get(k)!.push(p);
    }
    for (const [, arr] of m) arr.sort((a, b) => a.ts - b.ts);
    return Array.from(m.entries()).sort((a, b) => a[0] - b[0]);
  }, [rows, kind]);

  if (byArea.length === 0) return null;
  return <PriceScatter byArea={byArea} colorOf={colorOf} yLabel={kind === "wolse" ? "월세" : "보증금"} />;
}

function PriceScatter({
  byArea, colorOf, yLabel,
}: {
  byArea: [number, ChartPoint[]][];
  colorOf: (k: number | null) => string;
  yLabel: string;
}) {
  // 거래가 많으면 recharts 가 점마다 X축 라벨을 찍어 날짜가 겹친다(월세 487건
  // = 라벨 487개). 월초로 스냅한 균등 간격 틱 ≤7개를 명시해서 해결.
  const ticks = useMemo(() => {
    let lo = Infinity, hi = -Infinity;
    for (const [, pts] of byArea) for (const p of pts) {
      if (p.ts < lo) lo = p.ts;
      if (p.ts > hi) hi = p.ts;
    }
    if (!isFinite(lo) || hi <= lo) return undefined;
    const start = new Date(lo);
    start.setDate(1); start.setHours(0, 0, 0, 0);
    const end = new Date(hi);
    const months = (end.getFullYear() - start.getFullYear()) * 12
      + (end.getMonth() - start.getMonth()) + 1;
    const step = Math.max(1, Math.ceil(months / 7));
    const out: number[] = [];
    const d = new Date(start);
    while (d.getTime() <= hi) {
      out.push(d.getTime());
      d.setMonth(d.getMonth() + step);
    }
    return out;
  }, [byArea]);

  return (
    <div style={{ width: "100%", height: 280, marginBottom: 12 }}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#eee" />
          <XAxis
            dataKey="ts"
            type="number"
            domain={["dataMin", "dataMax"]}
            ticks={ticks}
            tickFormatter={(v: number) => {
              const d = new Date(v);
              return `${String(d.getFullYear()).slice(2)}/${String(d.getMonth() + 1).padStart(2, "0")}`;
            }}
            scale="time"
            tick={{ fontSize: 11 }}
          />
          <YAxis
            dataKey="price"
            tickFormatter={(v: number) => priceFmt(v)}
            tick={{ fontSize: 11 }}
            width={60}
          />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload || !payload.length) return null;
              const p = payload[0].payload as ChartPoint;
              return (
                <div style={{ background: "white", border: "1px solid #ccc", padding: 8, fontSize: 12 }}>
                  <div>{p.date}{p.direct ? " · 직거래" : ""}</div>
                  <div>{areaLabel(p.area)} · {p.floor ?? "-"}층</div>
                  <div><b>{yLabel}: {priceFmt(p.price)}</b></div>
                </div>
              );
            }}
          />
          <Legend
            verticalAlign="top"
            align="right"
            wrapperStyle={{ fontSize: 11, paddingBottom: 4 }}
            iconSize={10}
          />
          {byArea.map(([k, points]) => (
            <Scatter
              key={k}
              name={areaLabel(k)}
              data={points}
              fill={colorOf(k)}
              line={{ stroke: colorOf(k), strokeWidth: 1.5, strokeOpacity: 0.55 }}
              lineType="joint"
              lineJointType="monotoneX"
              shape={<DealDot />}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Scatter 점 모양: 직거래는 점 위에 '직' 글자를 표기. */
function DealDot(props: {
  cx?: number;
  cy?: number;
  fill?: string;
  payload?: ChartPoint;
}) {
  const { cx, cy, fill, payload } = props;
  if (cx == null || cy == null) return <g />;
  return (
    <g>
      <circle cx={cx} cy={cy} r={4.5} fill={fill} fillOpacity={0.8} stroke={fill} />
      {payload?.direct && (
        <text
          x={cx}
          y={cy - 7}
          textAnchor="middle"
          fontSize={10}
          fontWeight={700}
          fill={fill}
        >
          직
        </text>
      )}
    </g>
  );
}
