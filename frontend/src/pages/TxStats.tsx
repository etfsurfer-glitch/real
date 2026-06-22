import { useRef, useState } from "react";
import { useStickyState } from "../hooks/useStickyState";
import { Link, NavLink, Outlet } from "react-router-dom";
import { Loading } from "../components/Loading";
import ShareBar from "../components/ShareBar";
import { useFetchJson } from "../hooks/useFetchJson";
import { RegionSelect, useRegionFilter } from "../components/RegionSelect";
import { useDeferredUrl, ApplyButton } from "../hooks/useDeferredUrl";

const API_BASE = import.meta.env.VITE_API_BASE;

const PERIODS: { label: string; days: number }[] = [
  { label: "1주", days: 7 },
  { label: "1개월", days: 30 },
  { label: "3개월", days: 90 },
  { label: "6개월", days: 180 },
  { label: "1년", days: 365 },
  { label: "전체", days: 0 },
];
const TRADES: { code: "A1" | "B1" | "B2"; label: string }[] = [
  { code: "A1", label: "매매" },
  { code: "B1", label: "전세" },
  { code: "B2", label: "월세" },
];
const ASSETS: { code: "all" | "apt" | "offi"; label: string }[] = [
  { code: "all", label: "통합" },
  { code: "apt", label: "아파트" },
  { code: "offi", label: "오피스텔" },
];
const DEALINGS: { code: "all" | "broker" | "direct"; label: string }[] = [
  { code: "all", label: "전체" },
  { code: "broker", label: "중개거래" },
  { code: "direct", label: "직거래" },
];
export type AreaClass = "all" | "under10" | "10s" | "20s" | "30s" | "40s" | "over50";
export const AREA_CLASSES: { code: AreaClass; label: string }[] = [
  { code: "all", label: "전체" },
  { code: "under10", label: "10평 미만" },
  { code: "10s", label: "10평대" },
  { code: "20s", label: "20평대" },
  { code: "30s", label: "30평대" },
  { code: "40s", label: "40평대" },
  { code: "over50", label: "50평 초과" },
];

function formatWon(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 100_000_000) {
    const eok = Math.floor(v / 100_000_000);
    const man = Math.floor((v % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(v / 10_000).toLocaleString()}만`;
}

type PriceItem = {
  deal_ymd: string;
  price: number | null;
  monthly_rent: number | null;
  excl_use_ar: number | null;
  floor: number | null;
  build_year: number | null;
  complex_no: string | null;
  complex_name: string | null;
  region_name: string | null;
  dealing_gbn: string | null;
  asset: "apt" | "offi" | "silv";
};
type VolumeItem = {
  complex_no: string | null;
  complex_name: string | null;
  cortar_no: string | null;
  region_name: string | null;
  households: number | null;
  count: number;
  silv_count?: number;   // 거래수 중 분양권 건수(투명 표기)
};

function useFilters() {
  // sticky — 뒤로가기·재접속 시 마지막 필터 복원
  const [days, setDays] = useStickyState<number>("txstats:days", 30);
  const [trade, setTrade] = useStickyState<"A1" | "B1" | "B2">("txstats:trade", "A1");
  const [asset, setAsset] = useStickyState<"all" | "apt" | "offi">("txstats:asset", "all");
  const [dealing, setDealing] = useStickyState<"all" | "broker" | "direct">("txstats:dealing", "all");
  const [areaClass, setAreaClass] = useStickyState<AreaClass>("txstats:areaClass", "all");
  return { days, setDays, trade, setTrade, asset, setAsset, dealing, setDealing, areaClass, setAreaClass };
}

// ── 콕집 표준 필터 순서 (사이트 전역 일관 기준) ────────────────────────
// 사용자 사고 흐름: "무슨 거래 → 어디 → 무엇 → 얼마 → 언제 → 세부 → 정렬"
//   1.거래(매매/전세/월세) — 항상 맨 앞   2.지역(시도·시군구)
//   3.유형(아파트/오피스텔)  4.면적타입(평형)  5.기간
//   6.세부조건(거래방식·경신간격·할인율 등)  7.정렬
// 모든 필터바는 이 순서를 따른다. (없는 항목은 건너뜀)
function FilterBar(f: ReturnType<typeof useFilters> & {
  region?: ReturnType<typeof useRegionFilter>; dirty?: boolean; onApply?: () => void;
}) {
  return (
    <div className="filter-bar">
      <Select label="거래" value={f.trade} onChange={f.setTrade}
        options={TRADES.map((t) => ({ value: t.code, label: t.label }))} />
      {f.region && <RegionSelect {...f.region} />}
      <Select label="유형" value={f.asset} onChange={f.setAsset}
        options={ASSETS.map((a) => ({ value: a.code, label: a.label }))} />
      <Select label="면적타입" value={f.areaClass} onChange={f.setAreaClass}
        options={AREA_CLASSES.map((a) => ({ value: a.code, label: a.label }))} />
      <Select label="기간" value={f.days} onChange={f.setDays}
        options={PERIODS.map((p) => ({ value: p.days, label: p.label }))} />
      {f.trade === "A1" && (
        <Select label="거래방식" value={f.dealing} onChange={f.setDealing}
          options={DEALINGS.map((d) => ({ value: d.code, label: d.label }))} />
      )}
      {f.onApply && <ApplyButton dirty={!!f.dirty} onApply={f.onApply} />}
    </div>
  );
}

export type Opt<T> = { value: T; label: string };
export function Select<T extends string | number>({
  label, value, onChange, options,
}: { label: string; value: T; onChange: (v: T) => void; options: Opt<T>[] }) {
  return (
    <label className="filter-select">
      <span>{label}</span>
      <select
        value={String(value)}
        onChange={(e) => {
          const raw = e.target.value;
          const match = options.find((o) => String(o.value) === raw);
          if (match) onChange(match.value);
        }}
      >
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

const SUB_TABS: { to: string; label: string }[] = [
  { to: "/tx-stats/region-pulse", label: "지역별 거래량" },
  { to: "/tx-stats/top-price", label: "실거래가 최고" },
  { to: "/tx-stats/record-high", label: "단지별 신고가" },
  { to: "/tx-stats/top-volume", label: "거래량" },
  { to: "/tx-stats/turnover", label: "거래회전율" },
  { to: "/tx-stats/pyeong-price", label: "평당가" },
  { to: "/tx-stats/price-change", label: "가격 변동률" },
  { to: "/tx-stats/gap", label: "갭투자" },
  { to: "/tx-stats/yield", label: "월세수익률" },
  { to: "/tx-stats/low-price", label: "시세차이거래(20%↓)" },
  { to: "/tx-stats/cancelled", label: "취소거래" },
];

export function TxStatsLayout() {
  const shareRef = useRef<HTMLDivElement>(null);
  return (
    <div ref={shareRef} className="share-target">
      <Link to="/overview" className="back">← 전국현황</Link>
      <h2 style={{ margin: "0 0 12px", fontSize: 18, fontWeight: 700 }}>실거래 통계</h2>
      <nav className="sub-nav">
        {SUB_TABS.map((t) => (
          <NavLink key={t.to} to={t.to} className={({ isActive }) => isActive ? "active" : ""}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <ShareBar targetRef={shareRef} title="실거래 통계" fileName="콕집_실거래통계" />
      <Outlet />
    </div>
  );
}

export function TxTopPrice() {
  const f = useFilters();
  const region = useRegionFilter();
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-top-price?days=${f.days}&trade=${f.trade}&asset=${f.asset}&dealing=${f.dealing}&area_class=${f.areaClass}${region.query}&limit=100`
    : null);
  const { data, loading } = useFetchJson<{ items: PriceItem[] }>(url);
  const items = data?.items ?? [];

  return (
    <>
      <FilterBar {...f} region={region} dirty={dirty} onApply={apply} />
      {loading && <Loading />}
      <table>
        <thead>
          <tr>
            <th style={{ width: 40 }}>#</th>
            <th>단지</th>
            <th>유형</th>
            {f.trade === "A1" && <th>거래방식</th>}
            <th>면적</th>
            <th>층</th>
            <th>준공</th>
            <th className="num">{f.trade === "B2" ? "월세" : "가격"}</th>
            {f.trade === "B2" && <th className="num">보증금</th>}
            <th>거래일</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.deal_ymd}-${i}`}>
              <td style={{ color: "#999" }}>{i + 1}</td>
              <td>
                {it.complex_no ? (
                  <Link to={`/complex/${it.complex_no}`}>{it.complex_name ?? it.complex_no}</Link>
                ) : (it.complex_name ?? "—")}
                {it.region_name && (
                  <div className="muted" style={{ fontSize: 11 }}>{it.region_name}</div>
                )}
              </td>
              <td><span style={{ fontSize: 11, fontWeight: it.asset === "silv" ? 700 : undefined, color: it.asset === "silv" ? "#7c3aed" : it.asset === "offi" ? "#a06000" : "#1268d3" }}>{it.asset === "silv" ? "분양권" : it.asset === "offi" ? "오피" : "아파트"}</span></td>
              {f.trade === "A1" && (
                <td>
                  <span style={{
                    fontSize: 11, padding: "1px 6px", borderRadius: 4,
                    background: it.dealing_gbn === "직거래" ? "#ffe8e0" : "#e8f0ff",
                    color: it.dealing_gbn === "직거래" ? "#a03000" : "#1268d3",
                  }}>{it.dealing_gbn ?? "-"}</span>
                </td>
              )}
              <td>{it.excl_use_ar ? `${it.excl_use_ar.toFixed(1)}㎡` : "-"}</td>
              <td>{it.floor ?? "-"}</td>
              <td>{it.build_year ?? "-"}</td>
              <td className="num" style={{ fontWeight: 600 }}>
                {f.trade === "B2"
                  ? formatWon((it.monthly_rent || 0) * 10000)
                  : formatWon(it.price)}
              </td>
              {f.trade === "B2" && <td className="num">{formatWon(it.price)}</td>}
              <td style={{ fontSize: 12, color: "#666" }}>{it.deal_ymd}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

type LowPriceItem = {
  deal_ymd: string;
  deal_amount: number;
  avg_price: number;
  discount_rate: number;
  excl_use_ar: number | null;
  floor: number | null;
  dealing_gbn: string | null;
  complex_no: string | null;
  complex_name: string | null;
  region_name: string | null;
  group_size: number;
  asset: "apt" | "offi";
};

export function TxLowPrice() {
  const [days, setDays] = useState<number>(180);
  const [asset, setAsset] = useState<"all" | "apt" | "offi">("all");
  const [discount, setDiscount] = useState<number>(0.20);
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-low-price?days=${days}&asset=${asset}&discount=${discount}&area_class=${areaClass}&min_samples=3&limit=300`
    : null);
  const { data, loading } = useFetchJson<{ items: LowPriceItem[] }>(url);
  const items = data?.items ?? [];

  return (
    <>
      <div className="filter-bar">
        <Select label="유형" value={asset} onChange={setAsset}
          options={ASSETS.map((a) => ({ value: a.code, label: a.label }))} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass}
          options={AREA_CLASSES.map((a) => ({ value: a.code, label: a.label }))} />
        <Select label="기간" value={days} onChange={setDays} options={[
          { value: 90, label: "3개월" }, { value: 180, label: "6개월" },
          { value: 365, label: "1년" }, { value: 730, label: "2년" },
        ]} />
        <Select label="할인율" value={discount} onChange={setDiscount} options={[
          { value: 0.20, label: "20%↓" }, { value: 0.30, label: "30%↓" },
          { value: 0.40, label: "40%↓" }, { value: 0.50, label: "50%↓" },
        ]} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>
      <div className="muted" style={{ marginBottom: 8, fontSize: 12 }}>
        같은 단지·같은 면적타입의 평균 매매가 대비 {(discount * 100).toFixed(0)}% 이상 저렴한 거래.
        평균 신뢰도 위해 그룹당 최소 3건 이상의 거래가 있는 경우만 표시.
        증여·가족간 거래·특수관계 의심 케이스 포함 가능.
      </div>
      {loading && <Loading />}
      <table>
        <thead>
          <tr>
            <th style={{ width: 40 }}>#</th>
            <th>단지</th>
            <th>거래방식</th>
            <th>면적타입</th>
            <th>층</th>
            <th className="num">거래가</th>
            <th className="num">평균가</th>
            <th className="num">할인율</th>
            <th>거래일</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={`${it.complex_no}-${it.deal_ymd}-${i}`}>
              <td style={{ color: "#999" }}>{i + 1}</td>
              <td>
                {it.complex_no ? (
                  <Link to={`/complex/${it.complex_no}`}>{it.complex_name ?? it.complex_no}</Link>
                ) : (it.complex_name ?? "—")}
                <span style={{ fontSize: 10, color: "#aaa", marginLeft: 6 }}>
                  {it.asset === "offi" ? "오피" : "아파트"} · 평균 {it.group_size}건
                </span>
                {it.region_name && (
                  <div className="muted" style={{ fontSize: 11 }}>{it.region_name}</div>
                )}
              </td>
              <td>
                <span style={{
                  fontSize: 11, padding: "1px 6px", borderRadius: 4,
                  background: it.dealing_gbn === "직거래" ? "#ffd0c0" : "#e8f0ff",
                  color: it.dealing_gbn === "직거래" ? "#a03000" : "#1268d3",
                  fontWeight: it.dealing_gbn === "직거래" ? 600 : 400,
                }}>{it.dealing_gbn ?? "-"}</span>
              </td>
              <td>{it.excl_use_ar ? `${it.excl_use_ar.toFixed(1)}㎡` : "-"}</td>
              <td>{it.floor ?? "-"}</td>
              <td className="num" style={{ fontWeight: 600, color: "#c0392b" }}>{formatWon(it.deal_amount)}</td>
              <td className="num" style={{ color: "#666" }}>{formatWon(it.avg_price)}</td>
              <td className="num" style={{ fontWeight: 700, color: "#c0392b" }}>
                {(it.discount_rate * 100).toFixed(1)}%
              </td>
              <td style={{ fontSize: 12, color: "#666" }}>{it.deal_ymd}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}


export function TxTopVolume() {
  const f = useFilters();
  const region = useRegionFilter();
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-top-volume?days=${f.days}&trade=${f.trade}&asset=${f.asset}&dealing=${f.dealing}&area_class=${f.areaClass}${region.query}&limit=100`
    : null);
  const { data, loading } = useFetchJson<{ items: VolumeItem[] }>(url);
  const items = data?.items ?? [];

  return (
    <>
      <FilterBar {...f} region={region} dirty={dirty} onApply={apply} />
      {loading && <Loading />}
      <table>
        <thead>
          <tr>
            <th style={{ width: 40 }}>#</th>
            <th>단지</th>
            <th className="num">세대</th>
            <th className="num">거래수</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={it.complex_no ?? i}>
              <td style={{ color: "#999" }}>{i + 1}</td>
              <td>
                {it.complex_no ? (
                  <Link to={`/complex/${it.complex_no}`}>{it.complex_name ?? it.complex_no}</Link>
                ) : (it.complex_name ?? "—")}
                {it.region_name && (
                  <div className="muted" style={{ fontSize: 11 }}>{it.region_name}</div>
                )}
              </td>
              <td className="num">{it.households?.toLocaleString() ?? "-"}</td>
              <td className="num" style={{ fontWeight: 600 }}>
                {it.count.toLocaleString()}
                {!!it.silv_count && <div className="tx-silv-note">분양권 {it.silv_count.toLocaleString()}</div>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
