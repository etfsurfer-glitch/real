import { useStickyState } from "../hooks/useStickyState";
import FetchError from "../components/FetchError";
import { Loading } from "../components/Loading";
import { useFetchJson } from "../hooks/useFetchJson";
import { Select } from "./TxStats";

const API_BASE = import.meta.env.VITE_API_BASE;

const UP = "#c0392b";
const DOWN = "#1268d3";

// 시도 표준 배열 순서(통계청·국토부 관례) — 강원(42→51)·전북(45→52) 개편코드 병기.
// 코드 숫자 정렬은 강원·전북이 제주 뒤로 밀려 이 표로 정렬한다. 서버(local_api SIDO_ORDER)와 동일 기준.
const SIDO_ORDER = ["11", "26", "27", "28", "29", "46", "30", "31", "36",
  "41", "42", "51", "43", "44", "45", "52", "47", "48", "50"];
function sidoRank(code: string): number {
  const i = SIDO_ORDER.indexOf((code || "").slice(0, 2));
  return i < 0 ? SIDO_ORDER.length : i;
}

type RegionPulse = {
  region_code: string;
  region_name: string;
  filed_total: number;
  filed_current: number;
  filed_prev: number;
  current_month_count: number;
  prev_month_count: number;
  current_month_pred: number | null;
  prev_month_pred: number | null;
  yoy_cur_actual: number | null;
  yoy_prev_actual: number | null;
  yoy_cur_change: number | null;
  yoy_prev_change: number | null;
  avg3y_cur_actual: number | null;
  avg3y_prev_actual: number | null;
  avg3y_cur_change: number | null;
  avg3y_prev_change: number | null;
};

type PulseResponse = {
  asset: string;
  as_of: string;
  filed_date: string;
  current_month: string;
  prev_month: string;
  yoy_cur_month: string;
  yoy_prev_month: string;
  national: RegionPulse;
  regions: RegionPulse[];
};

// 국민평형(전용 59/84㎡) 평균가 — region-compare 엔드포인트에서 시도코드별로 병합
type RegionCmpRow = { sido_code: string; avg59: number | null; avg84: number | null };
type RegionCmp = { items: RegionCmpRow[] };

function fmt(n: number | null | undefined): string {
  if (n == null) return "-";
  return Math.round(n).toLocaleString();
}
function eok(v: number | null | undefined): string {
  if (v == null || v <= 0) return "—";
  return v >= 100_000_000 ? `${(v / 100_000_000).toFixed(1)}억`
    : `${Math.round(v / 10_000).toLocaleString()}만`;
}
function pctSigned(r: number | null | undefined): string {
  if (r == null) return "-";
  const v = (r * 100).toFixed(2);
  return r >= 0 ? `▲${v}%` : `▼${Math.abs(Number(v))}%`;
}
function changeColor(r: number | null | undefined): string {
  if (r == null) return "#999";
  return r >= 0 ? UP : DOWN;
}

function pickMonth(label: string): string {
  // "2026-05" → "5월"
  const m = /^\d{4}-(\d{2})$/.exec(label);
  if (!m) return label;
  return `${Number(m[1])}월`;
}

export function TxRegionPulse() {
  type Asset = "apt" | "offi" | "all" | "silv" | "villa" | "house" | "nrg";
  const [asset, setAsset] = useStickyState<Asset>("pulse:asset", "apt");
  const url = API_BASE
    ? `${API_BASE}/stats/tx-region-pulse?asset=${asset}`
    : null;
  const { data, loading, error } = useFetchJson<PulseResponse>(url);

  // 국민평형(전용 59/84㎡) 아파트 매매 평균가 — 시도코드(2자리)로 카드에 병합
  const cmpQ = useFetchJson<RegionCmp>(
    API_BASE ? `${API_BASE}/stats/region-compare?days=30&trade=A1` : null
  );
  const avgBySido = new Map<string, RegionCmpRow>(
    (cmpQ.data?.items ?? []).map((x) => [x.sido_code, x])
  );

  if (!API_BASE) {
    return <div style={{ color: "crimson" }}>로컬 API가 설정되지 않았습니다.</div>;
  }

  return (
    <>
      <div className="filter-bar">
        <Select label="자산" value={asset} onChange={(v) => setAsset(v as Asset)}
          options={[
            { value: "apt", label: "아파트" }, { value: "offi", label: "오피스텔" }, { value: "all", label: "아파트+오피스텔" },
            { value: "villa", label: "빌라·다세대" }, { value: "house", label: "단독·다가구" },
            { value: "nrg", label: "상가·사무실" }, { value: "silv", label: "분양권" },
          ]} />
        {data && (
          <span className="muted" style={{ fontSize: 12, alignSelf: "center" }}>
            {data.as_of} 기준 · 최근 적재({data.filed_date}) 분
          </span>
        )}
      </div>

      {error && <FetchError message={error} inline />}
      {loading && <Loading />}

      {/* 국민평형(59/84㎡) 대표가는 아파트 전용 지표 → 아파트 포함 자산에서만. 빌라·단독·상가·분양권엔 미표시(거래량 중심) */}
      {(() => { const kp = asset === "apt" || asset === "offi" || asset === "all"; return data && (
        <>
          <RegionCard r={data.national} cur={data.current_month} prev={data.prev_month}
            avg={kp ? avgBySido.get(data.national.region_code) : undefined}
            big />
          <div className="region-grid">
            {data.regions
              .slice()
              .sort((a, b) => sidoRank(a.region_code) - sidoRank(b.region_code))
              .map((r) => (
                <RegionCard key={r.region_code} r={r}
                  cur={data.current_month} prev={data.prev_month}
                  avg={kp ? avgBySido.get(r.region_code) : undefined} />
              ))}
          </div>
        </>
      ); })()}
      {(
        <>

          <style>{`
            .region-grid {
              display: grid;
              grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
              gap: 12px;
              margin-top: 16px;
            }
            .pulse-card {
              border: 1px solid #e0e0e0;
              border-radius: 8px;
              padding: 14px 16px;
              background: white;
            }
            .pulse-card.big {
              border: 2px solid #1268d3;
              padding: 20px 22px;
              margin-bottom: 12px;
            }
            .pulse-card .region {
              font-size: 16px;
              font-weight: 700;
              margin-bottom: 8px;
            }
            .pulse-card.big .region {
              font-size: 22px;
              margin-bottom: 12px;
            }
            .pulse-card .filed-now {
              font-size: 30px;
              font-weight: 800;
              color: #1268d3;
              line-height: 1.1;
            }
            .pulse-card.big .filed-now {
              font-size: 42px;
            }
            .pulse-card .split {
              font-size: 12px;
              color: #666;
              margin-top: 2px;
              margin-bottom: 10px;
            }
            .pulse-card .kp-price {
              display: flex; gap: 8px; margin-bottom: 12px;
            }
            .pulse-card .kp-item {
              flex: 1; background: #f5f8fc; border-radius: 7px;
              padding: 7px 10px; text-align: center;
            }
            .pulse-card.big .kp-item { padding: 10px 12px; }
            .pulse-card .kp-label { display: block; font-size: 11px; color: #6b7785; }
            .pulse-card .kp-val { display: block; font-size: 16px; font-weight: 700; color: #1f2a37; margin-top: 2px; }
            .pulse-card.big .kp-val { font-size: 20px; }
            .pulse-card .row {
              display: flex;
              justify-content: space-between;
              font-size: 12px;
              padding: 3px 0;
              border-bottom: 1px dashed #f0f0f0;
            }
            .pulse-card .row:last-child { border-bottom: none; }
            .pulse-card .row .label { color: #555; }
            .pulse-card .row .val { font-weight: 600; }
            .pulse-card .pred {
              font-size: 14px;
              font-weight: 700;
              color: #222;
            }
          `}</style>
        </>
      )}
    </>
  );
}


function RegionCard({ r, cur, prev, avg, big = false }: {
  r: RegionPulse; cur: string; prev: string;
  avg?: RegionCmpRow; big?: boolean;
}) {
  const curM = pickMonth(cur);
  const prevM = pickMonth(prev);
  return (
    <div className={`pulse-card${big ? " big" : ""}`}>
      <div className="region">{r.region_name}</div>
      {/* 오늘 '신고접수'된 건수 — 라벨 없이는 아래 월 숫자가 그 달 거래량으로 오독됨(전국 6월 439 사례) */}
      <div className="filed-label">오늘 신고접수</div>
      <div className="filed-now">{r.filed_total.toLocaleString()}건</div>
      <div className="split">
        이 중 {curM} 계약 {r.filed_current.toLocaleString()}건 · {prevM} 계약 {r.filed_prev.toLocaleString()}건
      </div>

      {avg && (avg.avg59 || avg.avg84) && (
        <div className="kp-price">
          <div className="kp-item">
            <span className="kp-label">전용 59㎡</span>
            <span className="kp-val">{eok(avg.avg59)}</span>
          </div>
          <div className="kp-item">
            <span className="kp-label">전용 84㎡</span>
            <span className="kp-val">{eok(avg.avg84)}</span>
          </div>
        </div>
      )}

      <div className="row">
        <span className="label">{prevM} 누적</span>
        <span className="val">{fmt(r.prev_month_count)}건</span>
      </div>
      <div className="row">
        <span className="label">{prevM} 거래량 예측</span>
        <span className="pred">{fmt(r.prev_month_pred)}건</span>
      </div>
      <div className="row">
        <span className="label">{curM} 누적</span>
        <span className="val">{fmt(r.current_month_count)}건</span>
      </div>
      <div className="row">
        <span className="label">{curM} 거래량 예측</span>
        <span className="pred">{fmt(r.current_month_pred)}건</span>
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <span className="label">전년동월 대비</span>
        <span className="val" style={{ color: changeColor(r.yoy_cur_change) }}>
          {pctSigned(r.yoy_cur_change)} <span className="muted" style={{ color: "#888", fontWeight: 400 }}>({fmt(r.yoy_cur_actual)})</span>
        </span>
      </div>
      <div className="row">
        <span className="label">3년평균 대비</span>
        <span className="val" style={{ color: changeColor(r.avg3y_cur_change) }}>
          {pctSigned(r.avg3y_cur_change)} <span className="muted" style={{ color: "#888", fontWeight: 400 }}>({fmt(r.avg3y_cur_actual)})</span>
        </span>
      </div>
    </div>
  );
}
