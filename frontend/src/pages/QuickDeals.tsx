import { useEffect, useMemo, useRef, useState } from "react";
import FetchError from "../components/FetchError";
import { useStickyState } from "../hooks/useStickyState";
import { Link } from "react-router-dom";
import ShareBar from "../components/ShareBar";
import { AlertTriangle } from "lucide-react";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";
import { useDeferredUrl, ApplyButton } from "../hooks/useDeferredUrl";

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

type Sido = { code: string; name: string };
type Sigungu = { code: string; name: string };

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
  // 지역: URL 쿼리(우리동네 '급매 더보기') > localStorage(마지막 선택) > 빈값. 뒤로가기·재접속 복원.
  const initRegion = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
  const _rls = (k: string) => { try { return window.localStorage.getItem("koczip:region:" + k) || ""; } catch { return ""; } };
  const _rsave = (k: string, v: string) => { try { window.localStorage.setItem("koczip:region:" + k, v); } catch { /* ignore */ } };
  const [sido, setSidoRaw] = useState<string>(() => initRegion.get("sido") || _rls("sido"));
  const [sigungu, setSigunguRaw] = useState<string>(() => initRegion.get("sigungu") || _rls("sigungu"));
  const setSido = (v: string) => { setSidoRaw(v); setSigunguRaw(""); _rsave("sido", v); _rsave("sigungu", ""); _rsave("dong", ""); };
  const setSigungu = (v: string) => { setSigunguRaw(v); _rsave("sigungu", v); _rsave("dong", ""); };
  const [minDiscount, setMinDiscount] = useStickyState<number>("quickdeals:minDiscount", 0.05);
  const [days, setDays] = useStickyState<number>("quickdeals:days", 90);

  // 시도 목록
  const sidoQ = useFetchJson<{ items: Sido[] }>(
    API_BASE ? `${API_BASE}/stats/changes/sido-list` : null
  );
  const sidos = sidoQ.data?.items ?? [];

  // 시군구 목록
  const sigunguUrl = useMemo(() => {
    if (!API_BASE) return null;
    return sido
      ? `${API_BASE}/stats/sigungu-list?sido=${sido}`
      : `${API_BASE}/stats/sigungu-list`;
  }, [sido]);
  const sigunguQ = useFetchJson<{ items: Sigungu[] }>(sigunguUrl);
  const sigungus = sigunguQ.data?.items ?? [];

  // 시도 변경 시 시군구 초기화 — 단, 첫 mount(URL 복원)에서는 건드리지 않음.
  const sidoFirst = useRef(true);
  useEffect(() => {
    if (sidoFirst.current) { sidoFirst.current = false; return; }
    setSigungu("");
  }, [sido]);

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
      limit: "500",
    });
    if (sigungu) qs.set("sigungu", sigungu);
    else if (sido) qs.set("sido", sido);
    return `${API_BASE}/stats/quick-deals?${qs.toString()}`;
  });
  const { data, loading, error } = useFetchJson<{ items: DealGroup[]; count: number }>(dealsUrl);

  // 클라이언트 필터: 기존 페이지 기준 유지 (표본 5건↑·매물 3개↑·선택 할인율·평형대)
  const items = useMemo(() => {
    let xs = data?.items ?? [];
    xs = xs.filter((x) => (x.n_real ?? 0) >= 5 && (x.n_listings ?? 0) >= 3);
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

  if (!API_BASE) {
    return <div style={{ color: "crimson" }}>로컬 API(VITE_API_BASE)가 설정되지 않았습니다.</div>;
  }

  return (
    <div ref={shareRef} className="share-target">
      <Link to="/overview" className="back">← 전국현황</Link>
      <h2 style={{ margin: "0 0 4px" }}>급매찾기</h2>
      <div className="muted" style={{ marginBottom: 16 }}>
        {tradeType === "A1"
          ? `최근 ${days}일 실거래 평균보다 싸게 나온 매물을 단지·면적별로 모았어요. 같은 단지·같은 면적에 매물이 3개 이상 있을 때만 보여드립니다.`
          : `최근 ${days}일 전세 평균(반전세 제외)보다 보증금이 낮은 매물을 단지·면적별로 모았어요. 같은 단지·같은 면적에 매물이 3개 이상 있을 때만 보여드립니다.`}
      </div>
      <ShareBar targetRef={shareRef} title="급매찾기" fileName="콕집_급매찾기" />

      <div className="filter-bar" style={{ marginBottom: 12, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 6 }}>
          {(["A1", "B1"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTradeType(t)}
              style={{
                padding: "5px 14px",
                border: `1px solid ${tradeType === t ? "#1268d3" : "#ccc"}`,
                borderRadius: 16,
                background: tradeType === t ? "#1268d3" : "white",
                color: tradeType === t ? "white" : "#333",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              {t === "A1" ? "매매" : "전세"}
            </button>
          ))}
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>시도</span>
          <select value={sido} onChange={(e) => setSido(e.target.value)}>
            <option value="">전국</option>
            {sidos.map((s) => (
              <option key={s.code} value={s.code}>{s.name}</option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>시군구</span>
          <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}>
            <option value="">{sido ? "전체" : "(시도 선택)"}</option>
            {sigungus.map((s) => (
              <option key={s.code} value={s.code}>{s.name}</option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>면적타입</span>
          <select value={pyeong} onChange={(e) => setPyeong(e.target.value)}>
            <option value="">전체</option>
            <option value="10">10평대</option>
            <option value="20">20평대</option>
            <option value="30">30평대</option>
            <option value="40">40평 이상</option>
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>실거래 기간</span>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={90}>3개월</option>
            <option value={180}>6개월</option>
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="muted" style={{ fontSize: 12 }}>최소 할인율</span>
          <select value={minDiscount} onChange={(e) => setMinDiscount(Number(e.target.value))}>
            <option value={0.05}>5% 이상</option>
            <option value={0.1}>10% 이상</option>
          </select>
        </label>
        <ApplyButton dirty={dirty} onApply={apply} />
      </div>

      {error && <FetchError message={String(error)} inline />}
      {loading && <Loading />}
      {!loading && items.length === 0 && (
        <div className="muted">조건에 맞는 단지·면적이 없습니다.</div>
      )}

      {items.length > 0 && (
        <>
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
                <tr key={`${d.complex_no}-${d.area_name}`}>
                  <td style={{ color: "#999" }}>{i + 1}</td>
                  <td>
                    <div style={{ fontSize: 11, color: "#666", marginBottom: 2 }}>
                      {d.region_name ?? ""}
                    </div>
                    {d.complex_no ? (
                      <Link to={`/complex/${d.complex_no}`} style={{ fontWeight: 600 }}>
                        {d.complex_name ?? d.complex_no}
                      </Link>
                    ) : (d.complex_name ?? "—")}
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{d.area_name}</div>
                    {d.area1_m2 && (
                      <div className="muted" style={{ fontSize: 11 }}>
                        공급 {d.area1_m2.toFixed(0)}㎡
                      </div>
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
        </>
      )}
    </div>
  );
}
