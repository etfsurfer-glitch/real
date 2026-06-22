import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Building2, Store, Home, Warehouse } from "lucide-react";
import { Loading } from "../components/Loading";
import { useRegionFilter } from "../components/RegionSelect";

const API = import.meta.env.VITE_API_BASE;

// 메뉴 미노출(URL 직접 접근) — 상가·빌라·사무실 호가 통계. 실거래는 추후 추가.
const CATS = [
  { key: "sangga", label: "상가", icon: Store },
  { key: "office", label: "사무실", icon: Building2 },
  { key: "villa", label: "빌라·연립", icon: Home },
  { key: "house", label: "단독·다가구", icon: Warehouse },
];

type TradeRow = { trade: string; n: number; avg_price: number | null; avg_rent?: number | null; avg_pyeong?: number | null; avg_area_m2: number | null };
type Resp = { cat: string; label: string; cortar: string; region_name: string | null; total: number; by_trade: TradeRow[]; top_buildings: { name: string; n: number }[]; source: string; available?: boolean };

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
  const cortar = dong || sigungu || "";

  useEffect(() => {
    if (!API) return;
    setLoading(true);
    fetch(`${API}/stats/nonresi?cat=${cat}&cortar=${cortar}`)
      .then((r) => r.json()).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [cat, cortar]);

  return (
    <div style={{ maxWidth: 760, margin: "0 auto", padding: "6px 4px 40px" }}>
      <h2 style={{ fontSize: 20, fontWeight: 800, color: "#13294b", margin: "0 0 4px" }}>상가·빌라·사무실 시세</h2>
      <p className="muted" style={{ fontSize: 12.5, margin: "0 0 12px" }}>
        지역별 비단지 매물 <b>호가</b> 통계입니다 (실거래 아님). {data?.region_name || "전국"} 기준.
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
      {!loading && data && (
        <>
          <div className="nr-total">{data.region_name || "전국"} · {data.label} 매물 <b>{data.total.toLocaleString()}</b>건 (호가)</div>
          <div className="nr-cards">
            {data.by_trade.map((t) => (
              <div className="nr-card" key={t.trade}>
                <div className="nr-card-h">{t.trade} <span>{t.n.toLocaleString()}건</span></div>
                {t.trade === "월세" ? (
                  <div className="nr-card-v">보증 <b>{won(t.avg_price)}</b> / 월세 <b>{won(t.avg_rent)}</b></div>
                ) : (
                  <div className="nr-card-v"><b>{won(t.avg_price)}</b></div>
                )}
                <div className="nr-card-m">
                  {t.avg_pyeong ? `평당 ${won(t.avg_pyeong)} · ` : ""}평균 {t.avg_area_m2 ?? "-"}㎡
                </div>
              </div>
            ))}
          </div>
          {data.total === 0 && <div className="dong-empty">이 지역 {data.label} 매물이 없어요. 지역을 바꿔보세요.</div>}
          {data.top_buildings.length > 0 && data.total > 0 && (
            <>
              <div className="ats-section" style={{ marginTop: 16 }}>매물 많은 유형/건물</div>
              <div className="ats-paths">
                {data.top_buildings.map((b, i) => (
                  <div key={i} className="ats-path"><span className="ats-path-r">{i + 1}</span>
                    <span className="ats-path-p" style={{ fontFamily: "inherit" }}>{b.name}</span>
                    <span className="ats-path-n">{b.n.toLocaleString()}건</span></div>
                ))}
              </div>
            </>
          )}
          <p className="muted" style={{ fontSize: 11.5, marginTop: 14 }}>
            ※ 매물 호가 기준 통계입니다. 상가·사무실 임대는 실거래 공개가 없어 호가로 제공하며, 빌라·단독·상가 매매 실거래는 추후 추가됩니다.
          </p>
        </>
      )}
    </div>
  );
}
