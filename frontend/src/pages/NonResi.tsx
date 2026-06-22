import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Building2, Store, Home, Warehouse, AlertTriangle } from "lucide-react";
import { Loading } from "../components/Loading";
import { useRegionFilter } from "../components/RegionSelect";

const API = import.meta.env.VITE_API_BASE;

// 메뉴 미노출(URL 직접 접근) — 상가·빌라·사무실. 비단지는 '평균'보다 '개별 실거래 사례'가 본질.
const CATS = [
  { key: "sangga", label: "상가", icon: Store },
  { key: "office", label: "사무실", icon: Building2 },
  { key: "villa", label: "빌라·연립", icon: Home },
  { key: "house", label: "단독·다가구", icon: Warehouse },
];

type TradeRow = { trade: string; n: number; avg_price: number | null; avg_rent?: number | null; avg_pyeong?: number | null; avg_area_m2: number | null };
type Sale = { n: number; avg: number | null; median: number | null; avg_pyeong?: number | null; avg_pyeong_land?: number | null; pyeong_label?: string };
type RealPrice = { window: string; sale: Sale; jeonse?: { n: number; avg_deposit: number | null }; wolse?: { n: number; avg_deposit: number | null; avg_rent: number | null }; yield_est?: number } | null;
type Resp = { cat: string; label: string; region_name: string | null; total: number; by_trade: TradeRow[]; top_buildings: { name: string; n: number }[]; realprice?: RealPrice };
type Deal = { date: string; umd: string; building: string; area_m2: number | null; build_year: number | null; amount?: number; pyeong?: number | null; deposit?: number; monthly_rent?: number; use?: string; land_use?: string; floor?: number | null; house_type?: string };
type Jeonse = { n_buildings: number; avg_ratio: number | null; risky_count: number; risky_pct: number; risky: { umd: string; building: string; area_m2: number; sale: number; jeonse: number; ratio: number }[] };

function won(v: number | null | undefined): string {
  if (!v) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8); const m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억${m.toLocaleString()}` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}

export default function NonResi() {
  const { cat = "sangga" } = useParams();
  const nav = useNavigate();
  const { sidos, sigungus, dongs, sido, setSido, sigungu, setSigungu, dong, setDong } = useRegionFilter();
  const [data, setData] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [dealTrade, setDealTrade] = useState<"sale" | "rent">("sale");
  const [dealSort, setDealSort] = useState("recent");
  const [q, setQ] = useState("");
  const [jeonse, setJeonse] = useState<Jeonse | null>(null);
  const cortar = dong || sigungu || "";
  const hasRent = cat === "villa" || cat === "house";

  useEffect(() => {
    if (!API) return;
    setLoading(true);
    fetch(`${API}/stats/nonresi?cat=${cat}&cortar=${cortar}`)
      .then((r) => r.json()).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [cat, cortar]);

  useEffect(() => {
    if (!API) return;
    const t = dealTrade === "rent" && !hasRent ? "sale" : dealTrade;
    fetch(`${API}/stats/nonresi/deals?cat=${cat}&cortar=${cortar}&trade=${t}&sort=${dealSort}&q=${encodeURIComponent(q)}&limit=60`)
      .then((r) => r.json()).then((d) => setDeals(d.deals || [])).catch(() => setDeals([]));
  }, [cat, cortar, dealTrade, dealSort, q, hasRent]);

  useEffect(() => {
    if (!API || cat !== "villa" || !cortar) { setJeonse(null); return; }
    fetch(`${API}/stats/nonresi/jeonse-ratio?cortar=${cortar}`)
      .then((r) => r.json()).then(setJeonse).catch(() => setJeonse(null));
  }, [cat, cortar]);

  const rp = data?.realprice;

  return (
    <div style={{ maxWidth: 820, margin: "0 auto", padding: "6px 4px 40px" }}>
      <h2 style={{ fontSize: 20, fontWeight: 800, color: "#13294b", margin: "0 0 4px" }}>상가·빌라·사무실 실거래</h2>
      <p className="muted" style={{ fontSize: 12.5, margin: "0 0 12px" }}>
        비단지는 매물마다 제각각이라 <b>평균보다 실제 거래 사례</b>가 중요합니다. {data?.region_name || "전국"} 기준.
      </p>

      <div className="nr-cats">
        {CATS.map((c) => (
          <button key={c.key} className={cat === c.key ? "on" : ""} onClick={() => nav(`/nonresi/${c.key}`)}>
            <c.icon size={14} aria-hidden /> {c.label}
          </button>
        ))}
      </div>

      <div className="dong-pick" style={{ marginTop: 10 }}>
        <select value={sido} onChange={(e) => setSido(e.target.value)}>
          <option value="">시·도</option>
          {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value={sigungu} onChange={(e) => setSigungu(e.target.value)} disabled={!sido}>
          <option value="">시·군·구</option>
          {sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value={dong} onChange={(e) => setDong(e.target.value)} disabled={!sigungu}>
          <option value="">읍·면·동(선택)</option>
          {dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
        </select>
      </div>

      {loading && <Loading />}

      {/* 실거래 시세 요약 */}
      {rp && (
        <>
          <div className="ats-section" style={{ marginTop: 16 }}>실거래 시세 <span className="nr-rp-tag">실거래 · {rp.window}</span></div>
          <div className="nr-cards">
            <div className="nr-card nr-rp">
              <div className="nr-card-h">매매 <span>{rp.sale.n.toLocaleString()}건</span></div>
              <div className="nr-card-v"><b>{won(rp.sale.avg)}</b></div>
              <div className="nr-card-m">중위 {won(rp.sale.median)}{rp.sale.avg_pyeong ? ` · 평당 ${won(rp.sale.avg_pyeong)}` : ""}{rp.sale.avg_pyeong_land ? ` · ${rp.sale.pyeong_label} ${won(rp.sale.avg_pyeong_land)}` : ""}</div>
            </div>
            {rp.jeonse && rp.jeonse.n > 0 && (
              <div className="nr-card nr-rp">
                <div className="nr-card-h">전세 <span>{rp.jeonse.n.toLocaleString()}건</span></div>
                <div className="nr-card-v"><b>{won(rp.jeonse.avg_deposit)}</b></div>
                <div className="nr-card-m">평균 보증금</div>
              </div>
            )}
            {rp.wolse && rp.wolse.n > 0 && (
              <div className="nr-card nr-rp">
                <div className="nr-card-h">월세 <span>{rp.wolse.n.toLocaleString()}건</span></div>
                <div className="nr-card-v">보증 <b>{won(rp.wolse.avg_deposit)}</b> / 월 <b>{won(rp.wolse.avg_rent)}</b></div>
                <div className="nr-card-m">평균</div>
              </div>
            )}
          </div>
          {rp.yield_est != null && (
            <div className="nr-yield">참고 임대수익률 추정 ≈ <b>{rp.yield_est}%</b>/년
              <span className="muted"> (매매 실거래 ÷ 임대 호가, 면적기준 차이로 참고용)</span></div>
          )}
        </>
      )}

      {/* 빌라 전세가율(깡통전세) */}
      {cat === "villa" && jeonse && jeonse.n_buildings > 0 && (
        <>
          <div className="ats-section" style={{ marginTop: 18 }}>전세가율 · 깡통전세 위험 <span className="nr-rp-tag">건물단위 매칭</span></div>
          <div className="nr-jeonse">
            <div className="nr-j-stat"><span>평균 전세가율</span><b>{jeonse.avg_ratio}%</b></div>
            <div className="nr-j-stat"><span>위험 건물(80%↑)</span><b className={jeonse.risky_pct >= 30 ? "danger" : ""}>{jeonse.risky_pct}%</b></div>
            <div className="nr-j-stat"><span>분석 건물</span><b>{jeonse.n_buildings.toLocaleString()}곳</b></div>
          </div>
          {jeonse.risky.length > 0 && (
            <div className="nr-risky">
              <div className="nr-risky-h"><AlertTriangle size={13} /> 전세가율 높은 건물 (전세 ≥ 매매가의 80%)</div>
              {jeonse.risky.slice(0, 8).map((r, i) => (
                <div className="nr-risky-row" key={i}>
                  <span className="nr-risky-b">{r.umd} {r.building} <em>{r.area_m2}㎡</em></span>
                  <span className="nr-risky-d">매매 {won(r.sale)} · 전세 {won(r.jeonse)}</span>
                  <span className={`nr-risky-r ${r.ratio >= 100 ? "danger" : ""}`}>{r.ratio}%</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* 개별 실거래 사례 */}
      <div className="ats-section" style={{ marginTop: 18 }}>개별 실거래 사례</div>
      <div className="nr-deal-bar">
        {hasRent && (
          <div className="nr-seg">
            <button className={dealTrade === "sale" ? "on" : ""} onClick={() => setDealTrade("sale")}>매매</button>
            <button className={dealTrade === "rent" ? "on" : ""} onClick={() => setDealTrade("rent")}>전월세</button>
          </div>
        )}
        <select value={dealSort} onChange={(e) => setDealSort(e.target.value)}>
          <option value="recent">최신순</option>
          <option value="price_high">높은가격순</option>
          <option value="price_low">낮은가격순</option>
          {dealTrade === "sale" && <option value="pyeong">평당높은순</option>}
        </select>
        <input placeholder="건물명·동 검색" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="nr-deals">
        {deals.length === 0 && <div className="dong-empty">조건에 맞는 실거래가 없어요.</div>}
        {deals.map((d, i) => (
          <div className="nr-deal" key={i}>
            <div className="nr-deal-l">
              <div className="nr-deal-b">{d.umd} {d.building}{d.house_type ? ` (${d.house_type})` : ""}</div>
              <div className="nr-deal-s">
                {d.date} · {d.area_m2}㎡{d.floor ? ` · ${d.floor}층` : ""}{d.build_year ? ` · ${d.build_year}년` : ""}
                {d.use ? ` · ${d.use}` : ""}
              </div>
            </div>
            <div className="nr-deal-r">
              {dealTrade === "rent" ? (
                <b>{won(d.deposit)}{d.monthly_rent ? ` / ${won(d.monthly_rent)}` : ""}</b>
              ) : (
                <><b>{won(d.amount)}</b>{d.pyeong ? <span className="nr-deal-py">평당 {won(d.pyeong)}</span> : null}</>
              )}
            </div>
          </div>
        ))}
      </div>

      <p className="muted" style={{ fontSize: 11.5, marginTop: 16 }}>
        ※ 국토교통부 실거래가 기반(해제거래 제외). 상가·사무실 임대는 실거래 공개가 없어 호가로만 제공됩니다.
        지번이 일부 가려진 항목(단독·일부 상가)은 정부 비공개 정책에 따른 것입니다.
      </p>
    </div>
  );
}
