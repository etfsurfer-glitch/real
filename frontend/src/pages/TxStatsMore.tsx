import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AREA_CLASSES, AreaClass, Select } from "./TxStats";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";
import { RegionSelect, useRegionFilter } from "../components/RegionSelect";
import { useDeferredUrl, ApplyButton } from "../hooks/useDeferredUrl";

const API_BASE = import.meta.env.VITE_API_BASE;

const PERIOD_3 = [
  { value: 180, label: "6개월" }, { value: 365, label: "1년" }, { value: 730, label: "2년" },
];
const ASSET_OPTS = [
  { value: "apt" as const, label: "아파트" }, { value: "offi" as const, label: "오피스텔" },
];
const AREA_OPTS = AREA_CLASSES.map((a) => ({ value: a.code, label: a.label }));

function formatWon(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 100_000_000) {
    const eok = Math.floor(v / 100_000_000);
    const man = Math.floor((v % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(v / 10_000).toLocaleString()}만`;
}

function ComplexCell({ no, name, region }: { no: string | null; name: string | null; region?: string | null }) {
  const inner = no ? <Link to={`/complex/${no}`}>{name ?? no}</Link> : <span>{name ?? "—"}</span>;
  return (
    <>
      {inner}
      {region ? <div className="muted" style={{ fontSize: 11 }}>{region}</div> : null}
    </>
  );
}

// ============ 갭투자 (매매-전세 차이) ============
export function TxGapRank() {
  const [days, setDays] = useState<number>(365);
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const region = useRegionFilter();
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-gap-rank?days=${days}&asset=${asset}&order=${order}&area_class=${areaClass}${region.query}&min_samples=3&limit=200`
    : null);
  const { data, loading } = useFetchJson<{ items: any[] }>(url);
  const items = data?.items ?? [];
  return (
    <>
      <div className="filter-bar">
        <RegionSelect {...region} />
        <Select label="유형" value={asset} onChange={setAsset} options={ASSET_OPTS} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass} options={AREA_OPTS} />
        <Select label="기간" value={days} onChange={setDays} options={PERIOD_3} />
        <Select label="정렬" value={order} onChange={setOrder} options={[
          { value: "asc", label: "갭 작은 순" }, { value: "desc", label: "갭 큰 순" },
        ]} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        같은 단지·같은 면적타입의 평균 매매가 - 평균 전세가 = 갭. 갭이 작을수록 갭투자에 유리.
      </div>
      {loading && <Loading />}
      <table>
        <thead><tr><th style={{ width: 40 }}>#</th><th>단지</th><th>면적타입</th>
          <th className="num">평균 매매</th><th className="num">평균 전세</th>
          <th className="num">갭</th><th className="num">전세율</th></tr></thead>
        <tbody>{items.map((it, i) => (
          <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
            <td style={{ color: "#999" }}>{i + 1}</td>
            <td><ComplexCell no={it.complex_no} name={it.complex_name} region={it.region_name} /></td>
            <td>{it.area_key}㎡</td>
            <td className="num">{formatWon(it.avg_sale)}</td>
            <td className="num">{formatWon(it.avg_jeonse)}</td>
            <td className="num" style={{ fontWeight: 600 }}>{formatWon(it.gap)}</td>
            <td className="num" style={{ color: "#1268d3" }}>{(it.jeonse_rate * 100).toFixed(1)}%</td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}

// ============ 전세율 ============
export function TxJeonseRate() {
  const [days, setDays] = useState<number>(365);
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const url = API_BASE
    ? `${API_BASE}/stats/tx-jeonse-rate?days=${days}&asset=${asset}&order=${order}&area_class=${areaClass}&min_samples=3&limit=200`
    : null;
  const { data, loading } = useFetchJson<{ items: any[] }>(url);
  const items = data?.items ?? [];
  return (
    <>
      <div className="filter-bar">
        <Select label="기간" value={days} onChange={setDays} options={PERIOD_3} />
        <Select label="유형" value={asset} onChange={setAsset} options={ASSET_OPTS} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass} options={AREA_OPTS} />
        <Select label="정렬" value={order} onChange={setOrder} options={[
          { value: "desc", label: "전세율 높은 순" }, { value: "asc", label: "낮은 순" },
        ]} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        같은 단지·같은 면적타입의 평균 전세가 / 평균 매매가. 높을수록 갭투자 매력.
      </div>
      {loading && <Loading />}
      <table>
        <thead><tr><th style={{ width: 40 }}>#</th><th>단지</th><th>면적타입</th>
          <th className="num">평균 매매</th><th className="num">평균 전세</th>
          <th className="num">전세율</th></tr></thead>
        <tbody>{items.map((it, i) => (
          <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
            <td style={{ color: "#999" }}>{i + 1}</td>
            <td><ComplexCell no={it.complex_no} name={it.complex_name} region={it.region_name} /></td>
            <td>{it.area_key}㎡</td>
            <td className="num">{formatWon(it.avg_sale)}</td>
            <td className="num">{formatWon(it.avg_jeonse)}</td>
            <td className="num" style={{ fontWeight: 600, color: "#1268d3" }}>
              {(it.jeonse_rate * 100).toFixed(1)}%
            </td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}

// ============ 가격 변동률 ============
export function TxPriceChange() {
  const [windowDays, setWindowDays] = useState<number>(90);
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const region = useRegionFilter();
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-price-change?window_days=${windowDays}&asset=${asset}&order=${order}&area_class=${areaClass}${region.query}&min_samples=3&limit=200`
    : null);
  const { data, loading } = useFetchJson<{ items: any[] }>(url);
  const items = data?.items ?? [];
  return (
    <>
      <div className="filter-bar">
        <RegionSelect {...region} />
        <Select label="유형" value={asset} onChange={setAsset} options={ASSET_OPTS} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass} options={AREA_OPTS} />
        <Select label="비교 기간" value={windowDays} onChange={setWindowDays} options={[
          { value: 30, label: "1개월" }, { value: 90, label: "3개월" }, { value: 180, label: "6개월" },
        ]} />
        <Select label="정렬" value={order} onChange={setOrder} options={[
          { value: "desc", label: "상승률 순" }, { value: "asc", label: "하락률 순" },
        ]} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        최근 {windowDays}일 평균가 vs 이전 {windowDays}일 평균가 (단지·면적타입별).
      </div>
      {loading && <Loading />}
      <table>
        <thead><tr><th style={{ width: 40 }}>#</th><th>단지</th><th>면적타입</th>
          <th className="num">최근 평균</th><th className="num">이전 평균</th>
          <th className="num">변동률</th></tr></thead>
        <tbody>{items.map((it, i) => (
          <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
            <td style={{ color: "#999" }}>{i + 1}</td>
            <td><ComplexCell no={it.complex_no} name={it.complex_name} region={it.region_name} /></td>
            <td>{it.area_key}㎡</td>
            <td className="num">{formatWon(it.recent_avg)}</td>
            <td className="num" style={{ color: "#888" }}>{formatWon(it.prev_avg)}</td>
            <td className="num" style={{ fontWeight: 600,
              color: it.change_rate >= 0 ? "#c0392b" : "#1268d3" }}>
              {it.change_rate >= 0 ? "+" : ""}{(it.change_rate * 100).toFixed(1)}%
            </td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}

// ============ 평당가 순위 ============
export function TxPyeongPrice() {
  const [days, setDays] = useState<number>(365);
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const region = useRegionFilter();
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-pyeong-price?days=${days}&asset=${asset}&order=${order}&area_class=${areaClass}${region.query}&min_samples=3&limit=200`
    : null);
  const { data, loading } = useFetchJson<{ items: any[] }>(url);
  const items = data?.items ?? [];
  return (
    <>
      <div className="filter-bar">
        <RegionSelect {...region} />
        <Select label="유형" value={asset} onChange={setAsset} options={ASSET_OPTS} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass} options={AREA_OPTS} />
        <Select label="기간" value={days} onChange={setDays} options={PERIOD_3} />
        <Select label="정렬" value={order} onChange={setOrder} options={[
          { value: "desc", label: "비싼 순" }, { value: "asc", label: "싼 순" },
        ]} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        거래가 ÷ 면적타입(평) = 평당가. 단지·면적타입별 그룹 평균.
      </div>
      {loading && <Loading />}
      <table>
        <thead><tr><th style={{ width: 40 }}>#</th><th>단지</th><th>면적타입</th>
          <th className="num">평균 매매</th><th className="num">평당가</th><th className="num">거래수</th></tr></thead>
        <tbody>{items.map((it, i) => (
          <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
            <td style={{ color: "#999" }}>{i + 1}</td>
            <td><ComplexCell no={it.complex_no} name={it.complex_name} region={it.region_name} /></td>
            <td>{it.area_key}㎡</td>
            <td className="num">{formatWon(it.avg_price)}</td>
            <td className="num" style={{ fontWeight: 600, color: "#1268d3" }}>{formatWon(it.pyeong_price)}/평</td>
            <td className="num">{it.n}</td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}

// ============ 거래회전율 ============
export function TxTurnover() {
  const [days, setDays] = useState<number>(365);
  const [trade, setTrade] = useState<"A1" | "B1">("A1");
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const region = useRegionFilter();
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-turnover?days=${days}&trade=${trade}&asset=${asset}&area_class=${areaClass}${region.query}&min_households=50&limit=200`
    : null);
  const { data, loading } = useFetchJson<{ items: any[] }>(url);
  const items = data?.items ?? [];
  return (
    <>
      <div className="filter-bar">
        <Select label="거래" value={trade} onChange={setTrade} options={[
          { value: "A1", label: "매매" }, { value: "B1", label: "전세" },
        ]} />
        <RegionSelect {...region} />
        <Select label="유형" value={asset} onChange={setAsset} options={ASSET_OPTS} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass} options={AREA_OPTS} />
        <Select label="기간" value={days} onChange={setDays} options={PERIOD_3} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        거래량 ÷ 세대수 — 단지 유동성. 세대수 50+ 단지만.
      </div>
      {loading && <Loading />}
      <table>
        <thead><tr><th style={{ width: 40 }}>#</th><th>단지</th><th className="num">세대수</th>
          <th className="num">거래수</th><th className="num">회전율</th></tr></thead>
        <tbody>{items.map((it, i) => (
          <tr key={it.complex_no ?? i}>
            <td style={{ color: "#999" }}>{i + 1}</td>
            <td><ComplexCell no={it.complex_no} name={it.complex_name} region={it.region_name} /></td>
            <td className="num">{it.households?.toLocaleString()}</td>
            <td className="num">{it.tx_count?.toLocaleString()}</td>
            <td className="num" style={{ fontWeight: 600, color: "#1268d3" }}>
              {(it.turnover_rate * 100).toFixed(1)}%
            </td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}

// ============ 월세수익률 ============
type Sido = { code: string; name: string };
export function TxYield() {
  const [days, setDays] = useState<number>(365);
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const [sido, setSido] = useState<string>("");
  const [sidos, setSidos] = useState<Sido[]>([]);
  useEffect(() => {
    if (!API_BASE) return;
    fetch(`${API_BASE}/stats/changes/sido-list`)
      .then((r) => r.json()).then((d) => setSidos(d.items || [])).catch(() => {});
  }, []);
  const sidoQ = sido ? `&sido=${sido}` : "";
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-yield?days=${days}&asset=${asset}&area_class=${areaClass}${sidoQ}&min_samples=3&limit=200`
    : null);
  const { data, loading } = useFetchJson<{ items: any[] }>(url);
  const items = data?.items ?? [];
  return (
    <>
      <div className="filter-bar">
        <Select label="지역" value={sido} onChange={setSido}
          options={[{ value: "", label: "전국" }, ...sidos.map((s) => ({ value: s.code, label: s.name }))]} />
        <Select label="유형" value={asset} onChange={setAsset} options={ASSET_OPTS} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass} options={AREA_OPTS} />
        <Select label="기간" value={days} onChange={setDays} options={PERIOD_3} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        연 월세 (월세×12) ÷ 평균 매매가 = 명목 임대수익률. 단지·면적타입별.
      </div>
      {loading && <Loading />}
      <table>
        <thead><tr><th style={{ width: 40 }}>#</th><th>단지</th><th>면적타입</th>
          <th className="num">세대수</th>
          <th className="num">매매</th><th className="num">보증금</th><th className="num">월세</th>
          <th className="num">수익률</th></tr></thead>
        <tbody>{items.map((it, i) => (
          <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
            <td style={{ color: "#999" }}>{i + 1}</td>
            <td>
              <ComplexCell no={it.complex_no} name={it.complex_name} />
              {it.region_name && (
                <div className="muted" style={{ fontSize: 11 }}>{it.region_name}</div>
              )}
            </td>
            <td>{it.area_key}㎡</td>
            <td className="num">{it.households != null ? it.households.toLocaleString() : "-"}</td>
            <td className="num">{formatWon(it.avg_sale)}</td>
            <td className="num">{formatWon(it.avg_deposit)}</td>
            <td className="num">{((it.avg_monthly || 0) / 10000).toFixed(0)}만</td>
            <td className="num" style={{ fontWeight: 600, color: "#1268d3" }}>
              {(it.yield_rate * 100).toFixed(2)}%
            </td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}

// ============ 단지별 신고가 ============
const RECORD_PERIODS = [
  { value: 30, label: "최근 1개월" }, { value: 90, label: "최근 3개월" },
  { value: 180, label: "최근 6개월" }, { value: 365, label: "최근 1년" },
];
const TRADE_OPTS = [
  { value: "A1" as const, label: "매매" },
  { value: "B1" as const, label: "전세" },
  { value: "B2" as const, label: "월세" },
];
const ASSET_ALL_OPTS = [
  { value: "all" as const, label: "통합" },
  { value: "apt" as const, label: "아파트" },
  { value: "offi" as const, label: "오피스텔" },
];

export function TxRecordHigh() {
  const [days, setDays] = useState<number>(90);
  const [trade, setTrade] = useState<"A1" | "B1" | "B2">("A1");
  const [asset, setAsset] = useState<"all" | "apt" | "offi">("all");
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const [maxGap, setMaxGap] = useState<number>(0);
  const [order, setOrder] = useState<"premium" | "recent">("premium");
  const region = useRegionFilter();
  const { url, dirty, apply } = useDeferredUrl(() => API_BASE
    ? `${API_BASE}/stats/tx-record-high?days=${days}&trade=${trade}&asset=${asset}&area_class=${areaClass}${region.query}&max_gap_months=${maxGap}&order=${order}&min_prior=1&limit=300`
    : null);
  const { data, loading } = useFetchJson<{ items: any[] }>(url);
  const items = data?.items ?? [];
  // 월세는 monthly_rent(만원 단위), 그 외는 원 단위
  const toWon = (v: number | null) => (v == null ? null : trade === "B2" ? v * 10000 : v);
  return (
    <>
      <div className="filter-bar">
        <Select label="거래" value={trade} onChange={setTrade} options={TRADE_OPTS} />
        <RegionSelect {...region} />
        <Select label="유형" value={asset} onChange={setAsset} options={ASSET_ALL_OPTS} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass} options={AREA_OPTS} />
        <Select label="신고가 시점" value={days} onChange={setDays} options={RECORD_PERIODS} />
        <Select label="경신 간격" value={maxGap} onChange={setMaxGap} options={[
          { value: 0, label: "전체" }, { value: 3, label: "3개월 이내" },
          { value: 6, label: "6개월 이내" }, { value: 12, label: "1년 이내" },
        ]} />
        <Select label="정렬" value={order} onChange={setOrder} options={[
          { value: "premium", label: "상승률 큰 순" }, { value: "recent", label: "경신일 최신 순" },
        ]} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        <b>신고가 시점</b>: 새 신고가가 이 기간(최근 {days}일) 안에 나온 단지·타입(전용면적)만 표시.
        직전 최고가 거래일은 이 기간과 무관하게 더 과거일 수 있음.
        <b>경신 간격</b>: 직전 신고가가 처음 세워진 날 → 새 신고가까지 걸린 시간.
      </div>
      {loading && <Loading />}
      <table>
        <thead><tr>
          <th style={{ width: 40 }}>#</th><th>단지</th><th>타입</th>
          <th className="num">{trade === "B2" ? "신고 월세" : "신고가"}</th>
          <th className="num">직전고가</th><th className="num">상승률</th>
          <th className="num">경신 간격</th><th className="num">거래수</th>
        </tr></thead>
        <tbody>{items.map((it, i) => (
          <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
            <td style={{ color: "#999" }}>{i + 1}</td>
            <td>
              <ComplexCell no={it.complex_no} name={it.complex_name} />
              {it.asset === "silv" && <span className="ctx-badge tx-silv-badge">분양권</span>}
              {it.region_name && (
                <div className="muted" style={{ fontSize: 11 }}>{it.region_name}</div>
              )}
            </td>
            <td>{it.area_key}㎡<span style={{ color: "#aaa", fontSize: 11 }}> ({Math.round(it.area_key / 3.3058)}평)</span></td>
            <td className="num" style={{ fontWeight: 600, color: "#c0392b" }}>
              {formatWon(toWon(it.record_price))}
              {it.floor != null && <span style={{ fontSize: 11, fontWeight: 400, color: "#999" }}> {it.floor}층</span>}
              <div className="muted" style={{ fontSize: 11, fontWeight: 400 }}>{it.record_date}</div>
            </td>
            <td className="num" style={{ color: "#666" }}>
              {formatWon(toWon(it.prev_high))}
              {it.prev_floor != null && <span style={{ fontSize: 11, color: "#aaa" }}> {it.prev_floor}층</span>}
              <div className="muted" style={{ fontSize: 11 }}>{it.prev_date}</div>
            </td>
            <td className="num" style={{ fontWeight: 700, color: "#c0392b" }}>
              +{(it.premium * 100).toFixed(1)}%
            </td>
            <td className="num">{it.months_since != null ? `${it.months_since}개월` : "-"}</td>
            <td className="num" style={{ color: "#888" }}>{it.n_total}</td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}

// ============ 호가-실거래 갭 ============
export function TxAskingVsReal() {
  const [days, setDays] = useState<number>(90);
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [areaClass, setAreaClass] = useState<AreaClass>("all");
  const url = API_BASE
    ? `${API_BASE}/stats/tx-asking-vs-real?days=${days}&order=${order}&area_class=${areaClass}&min_samples=3&limit=200`
    : null;
  const { data, loading } = useFetchJson<{ items: any[] }>(url);
  const items = data?.items ?? [];
  return (
    <>
      <div className="filter-bar">
        <Select label="실거래 기간" value={days} onChange={setDays} options={[
          { value: 90, label: "3개월" }, { value: 180, label: "6개월" }, { value: 365, label: "1년" },
        ]} />
        <Select label="면적타입" value={areaClass} onChange={setAreaClass} options={AREA_OPTS} />
        <Select label="정렬" value={order} onChange={setOrder} options={[
          { value: "desc", label: "호가 비쌈 순" }, { value: "asc", label: "호가 저렴 순" },
        ]} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
        매물 호가(매매) 평균 vs 실거래가 평균 비교 (단지·면적타입). 양수 = 호가가 더 비쌈 (조정 압력).
      </div>
      {loading && <Loading />}
      <table>
        <thead><tr><th style={{ width: 40 }}>#</th><th>단지</th><th>면적타입</th>
          <th className="num">호가 평균</th><th className="num">실거래 평균</th>
          <th className="num">갭률</th></tr></thead>
        <tbody>{items.map((it, i) => (
          <tr key={`${it.complex_no}-${it.area_key}-${i}`}>
            <td style={{ color: "#999" }}>{i + 1}</td>
            <td><ComplexCell no={it.complex_no} name={it.complex_name} region={it.region_name} /></td>
            <td>{it.area_key}㎡</td>
            <td className="num">{formatWon(it.avg_asking)}</td>
            <td className="num">{formatWon(it.avg_real)}</td>
            <td className="num" style={{ fontWeight: 600,
              color: it.gap_rate >= 0 ? "#c0392b" : "#1268d3" }}>
              {it.gap_rate >= 0 ? "+" : ""}{(it.gap_rate * 100).toFixed(1)}%
            </td>
          </tr>
        ))}</tbody>
      </table>
    </>
  );
}
