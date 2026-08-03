import { useMemo, useRef, useState } from "react";
import FavHeart from "../components/FavHeart";
import FetchError from "../components/FetchError";
import { useStickyState } from "../hooks/useStickyState";
import { Link } from "react-router-dom";
import ShareBar from "../components/ShareBar";
import FavDashLink from "../components/FavDashLink";
import DealMiniMap from "../components/DealMiniMap";
import { AlertTriangle, MapPin } from "lucide-react";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";
import { useDeferredUrl, ApplyButton } from "../hooks/useDeferredUrl";
import { Select } from "./TxStats";
import { coordToRegion } from "../lib/kakaomap";
import { RegionSelect, useRegionFilter } from "../components/RegionSelect";
import RequestCta from "../components/RequestCta";
import { areaLabel } from "../lib/area";

const API_BASE = import.meta.env.VITE_API_BASE;

const UP = "#c0392b";
const DOWN = "#1268d3";

function formatWon(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 100_000_000) {
    const eok = Math.floor(v / 100_000_000);
    const man = Math.floor((v % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억${man.toLocaleString()}` : `${eok}억`;
  }
  return `${Math.floor(v / 10_000).toLocaleString()}만`;
}
function pct(r: number | null | undefined): string {
  if (r == null) return "-";
  return `${r >= 0 ? "+" : ""}${(r * 100).toFixed(1)}%`;
}
function formatRange(lo: number, hi: number, fmt: (v: number) => string): string {
  return lo === hi ? fmt(lo) : `${fmt(lo)} ~ ${fmt(hi)}`;
}

type DealGroup = {
  complex_no: string;
  area_name: string;
  area1_m2: number | null;
  n_listings: number;
  asking_min: number;
  asking_max: number;
  asking_avg: number;
  avg_real: number;
  min_real: number;
  max_real: number;
  n_real: number;
  avg_excl: number | null;
  discount_min: number;   // 최저 호가 매물의 할인율 (가장 음수)
  discount_max: number;   // 최고 호가 매물의 할인율
  discount_avg: number;
  complex_name: string | null;
  cortar_no: string | null;
  region_name: string | null;
  naver_complex_url: string;
};

export default function QuickDeals() {
  const shareRef = useRef<HTMLDivElement>(null);
  const [tradeType, setTradeType] = useStickyState<"A1" | "B1">("quickdeals:trade", "A1");
  const [pyeong, setPyeong] = useStickyState<string>("quickdeals:pyeong", "");  // "" | "10" | "20" | "30" | "40" | "50"
  // 랜딩 '우리동네 급매'는 아파트/오피스텔을 골라 보는데 여기선 무시돼, 더보기로 넘어오면
  // 다른 목록이 나왔다. URL로 이어받고 화면에서도 바꿀 수 있게 한다.
  const [asset, setAsset] = useStickyState<string>("quickdeals:asset", "apt");
  // 지역: URL 쿼리(우리동네 '급매 더보기') → localStorage → 빈값. 공용 훅으로 통일(뒤로가기·재접속 복원 포함).
  const region = useRegionFilter();
  const [minDiscount, setMinDiscount] = useStickyState<number>("quickdeals:minDiscount", 0.05);
  const [days, setDays] = useStickyState<number>("quickdeals:days", 90);
  const [mapOpen, setMapOpen] = useStickyState<boolean>("quickdeals:map", true);
  const [pickCx, setPickCx] = useState<string>("");   // 지도 핀 → 표 행 강조(지속)
  // 지도 '내 위치' → 그 읍면동으로 URL 이동(리로드) — useRegionFilter가 URL에서 확정 초기화되어
  // 필터·데이터·적용까지 한 번에 반영(세터 경유는 간헐 미반영 이슈가 있어 URL 방식으로 고정)
  const onMapLocate = (lat: number, lng: number) => {
    coordToRegion(lat, lng).then((r) => {
      if (!r) return;
      const qs = new URLSearchParams(window.location.search);
      qs.set("sido", r.sido); qs.set("sigungu", r.sigungu); qs.set("dong", r.dong);
      window.location.search = qs.toString();
    });
  };
  const [flashCx, setFlashCx] = useState<string>("");  // 눌린 직후 잠깐 번쩍

  // 와이드 캐시 키로만 fetch — 야간 사전계산(build_api_cache --quick-deals-sgg)과
  // 정확히 같은 키(지역×기간×거래유형, min_samples=3·할인3%·전평형·limit=500)라
  // 항상 캐시 HIT(~20ms). 평형·할인율·표본수·매물수는 아래에서 브라우저 필터.
  // → 필터 클릭이 서버 요청을 안 만들어 미스 폭풍/디스크 경합도 사라짐.
  // 서버 호출은 와이드 캐시키(거래·지역·기간)에만 의존 → '적용' 으로만 갱신.
  // 면적·할인율은 아래에서 브라우저 필터(서버요청 0)라 즉시 반영(적용 불필요).
  const { url: dealsUrl, dirty, apply } = useDeferredUrl(() => {
    if (!API_BASE) return null;
    const qs = new URLSearchParams({
      days: String(days),
      min_samples: "3",
      min_discount: "0.03",
      min_listings: "1",
      trade_type: tradeType,
      asset,
      limit: "500",
    });
    if (region.dong) qs.set("dong", region.dong);
    else if (region.sigungu) qs.set("sigungu", region.sigungu);
    else if (region.sido) qs.set("sido", region.sido);
    return `${API_BASE}/stats/quick-deals?${qs.toString()}`;
  });
  const { data, loading, error } = useFetchJson<{ items: DealGroup[]; count: number }>(dealsUrl);

  // 클라이언트 필터: 기존 페이지 기준 유지 (표본 5건↑·매물 3개↑·선택 할인율·평형대)
  const items = useMemo(() => {
    let xs = data?.items ?? [];
    // 랜딩 '우리동네 급매'는 표본 3건·매물 제한 없음으로 보여준다. 여기서만 5건·3개로
    // 더 조여 같은 지역인데 상위 항목이 통째로 사라졌다(서초구 8건 → 2건). 기준을 맞춘다.
    xs = xs.filter((x) => (x.n_real ?? 0) >= 3);
    xs = xs.filter((x) => Math.abs(x.discount_min ?? 0) >= minDiscount);
    if (pyeong) {
      const py = Number(pyeong);
      const lo = py * 3.3058;
      const hi = (py + 10) * 3.3058;
      xs = xs.filter((x) => {
        const a = x.area1_m2 ?? 0;
        return a >= lo && (py >= 40 || a < hi);
      });
    }
    return xs;
  }, [data, minDiscount, pyeong]);

  // 지도는 좌표를 60개까지만 받으니, 단지별로 할인율 가장 큰 것 하나만 골라 상위 60단지를 찍는다.
  const mapPins = useMemo(() => {
    const best = new Map<string, DealGroup>();
    for (const x of items) {
      const k = String(x.complex_no);
      const prev = best.get(k);
      if (!prev || Math.abs(x.discount_min ?? 0) > Math.abs(prev.discount_min ?? 0)) best.set(k, x);
    }
    return [...best.values()]
      .sort((a, b) => Math.abs(b.discount_min ?? 0) - Math.abs(a.discount_min ?? 0))
      .slice(0, 60)
      .map((x) => ({ complex_no: String(x.complex_no), complex_name: x.complex_name ?? "단지",
                     area_name: x.area_name, asking_min: x.asking_min, discount_min: x.discount_min }));
  }, [items]);

  if (!API_BASE) {
    return <div style={{ color: "crimson" }}>로컬 API(VITE_API_BASE)가 설정되지 않았습니다.</div>;
  }

  return (
    <div ref={shareRef} className="share-target">
      <Link to="/overview" className="back">← 전국현황</Link>
      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "0 0 4px" }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>급매찾기</h2>
        <FavDashLink />
      </div>
      <div className="muted" style={{ marginBottom: 16 }}>
        {tradeType === "A1"
          ? `최근 ${days}일 실거래 평균보다 싸게 나온 매물을 단지·면적별로 모았어요. 같은 단지·같은 면적에 매물이 3개 이상 있을 때만 보여드립니다.`
          : `최근 ${days}일 전세 평균(반전세 제외)보다 보증금이 낮은 매물을 단지·면적별로 모았어요. 같은 단지·같은 면적에 매물이 3개 이상 있을 때만 보여드립니다.`}
      </div>
      <ShareBar targetRef={shareRef} title="급매찾기" fileName="콕집_급매찾기" />

      <div className="filter-bar">
        <Select label="거래" value={tradeType} onChange={(v) => setTradeType(v as "A1" | "B1")}
          options={[{ value: "A1", label: "매매" }, { value: "B1", label: "전세" }]} />
        <RegionSelect {...region} />
        <Select label="유형" value={asset} onChange={setAsset}
          options={[{ value: "apt", label: "아파트" }, { value: "offi", label: "오피스텔" }, { value: "all", label: "전체" }]} />
        <Select label="면적타입" value={pyeong} onChange={setPyeong}
          options={[{ value: "", label: "전체" }, { value: "10", label: "10평대" }, { value: "20", label: "20평대" }, { value: "30", label: "30평대" }, { value: "40", label: "40평 이상" }]} />
        <Select label="실거래 기간" value={days} onChange={setDays}
          options={[{ value: 90, label: "3개월" }, { value: 180, label: "6개월" }]} />
        <Select label="최소 할인율" value={minDiscount} onChange={setMinDiscount}
          options={[{ value: 0.05, label: "5% 이상" }, { value: 0.1, label: "10% 이상" }]} />
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>

      {error && <FetchError message={String(error)} inline />}
      {loading && <Loading />}
      {!loading && items.length === 0 && (
        <>
          <div className="muted">조건에 맞는 단지·면적이 없습니다.</div>
          {/* 결과가 없을 때가 요청을 남기기에 가장 좋은 자리다 — 헛걸음으로 끝내지 않는다 */}
          <RequestCta
            title="지금은 조건에 맞는 급매가 없네요"
            sub="조건을 남겨 두시면 매물이 나올 때 그 동네 중개사무소가 연락드려요. 무료입니다."
            sido={region.sido} sigungu={region.sigungu} dong={region.dong}
            asset={asset} trade={tradeType} />
        </>
      )}

      {items.length > 0 && (
        <>
          {/* 위치 지도 — 어느 동네에 급매가 몰렸는지 먼저 본다. 결과가 많아 접을 수 있게 한다. */}
          <div className="qd-map-bar">
            <button type="button" className="qd-map-toggle" onClick={() => setMapOpen((v) => !v)}>
              <MapPin size={14} /> 지도 {mapOpen ? "접기" : "펼치기"}
              <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>
                할인율 상위 {Math.min(mapPins.length, 60)}곳
              </span>
            </button>
          </div>
          {mapOpen && (
            <DealMiniMap deals={mapPins} height={340} onLocate={onMapLocate}
              onPick={(cno) => {
                setPickCx(cno);
                setFlashCx("");                       // 같은 핀 재클릭에도 애니메이션이 다시 돌게 리셋
                requestAnimationFrame(() => setFlashCx(cno));
                document.getElementById(`qd-${cno}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
              }} />
          )}
          <table>
            <thead>
              <tr>
                <th style={{ width: 40 }}>#</th>
                <th>단지 · 지역</th>
                <th>면적</th>
                <th className="num">매물수</th>
                <th className="num">{tradeType === "A1" ? "호가" : "보증금 호가"} (최저~최고)</th>
                <th className="num">{tradeType === "A1" ? "실거래 평균" : "전세 평균"}</th>
                <th className="num">거래수</th>
                <th className="num">할인율 (최저~최고 호가 기준)</th>
              </tr>
            </thead>
            <tbody>
              {items.map((d, i) => (
                <tr key={`${d.complex_no}-${d.area_name}`} id={`qd-${d.complex_no}`}
                    className={(pickCx === String(d.complex_no) ? "qd-row-on" : "")
                      + (flashCx === String(d.complex_no) ? " qd-row-flash" : "")}>
                  <td style={{ color: "#999" }}>{i + 1}</td>
                  <td>
                    <div style={{ fontSize: 11, color: "#666", marginBottom: 2 }}>
                      {d.region_name ?? ""}
                    </div>
                    {d.complex_no ? (
                      <><Link to={`/complex/${d.complex_no}`} style={{ fontWeight: 600 }}>
                        {d.complex_name ?? d.complex_no}
                      </Link><FavHeart complexNo={String(d.complex_no)} complexName={d.complex_name ?? undefined} /></>
                    ) : (d.complex_name ?? "—")}
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{d.avg_excl ? areaLabel(d.avg_excl) : d.area_name}</div>
                    {d.area_name && (
                      <div className="muted" style={{ fontSize: 11 }}>타입 {d.area_name}</div>
                    )}
                  </td>
                  <td className="num">{d.n_listings}</td>
                  <td className="num">
                    {formatRange(d.asking_min, d.asking_max, formatWon)}
                    <div className="muted" style={{ fontSize: 11 }}>
                      평균 {formatWon(d.asking_avg)}
                    </div>
                  </td>
                  <td className="num">
                    {formatWon(d.avg_real)}
                    <div className="muted" style={{ fontSize: 11 }}>
                      {formatWon(d.min_real)} ~ {formatWon(d.max_real)}
                    </div>
                  </td>
                  <td className="num">{d.n_real}</td>
                  <td className="num" style={{ fontWeight: 700 }}>
                    <span style={{ color: d.discount_min < 0 ? DOWN : UP }}>
                      {pct(d.discount_min)}
                    </span>
                    {" ~ "}
                    <span style={{ color: d.discount_max < 0 ? DOWN : UP }}>
                      {pct(d.discount_max)}
                    </span>
                    <div className="muted" style={{ fontSize: 11 }}>
                      평균 {pct(d.discount_avg)}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="muted" style={{ marginTop: 12, fontSize: 11, display: "inline-flex", alignItems: "center", gap: 5 }}>
            <AlertTriangle size={12} strokeWidth={2.2} aria-hidden /> 같은 면적이라도 층·향·상태에 따라 호가 차이가 날수 있습니다.
          </div>
          {/* 급매를 훑어본 뒤 — 마음에 드는 게 없을 때 남길 곳 */}
          <RequestCta
            title="마음에 드는 매물이 없으세요?"
            sub="원하는 조건을 남기시면 그 동네 중개사무소가 찾아서 연락드려요. 아직 안 올라온 매물도 있습니다."
            sido={region.sido} sigungu={region.sigungu} dong={region.dong}
            asset={asset} trade={tradeType} />
        </>
      )}
    </div>
  );
}
