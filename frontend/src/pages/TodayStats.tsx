import { useRef } from "react";
import { BarChart3 } from "lucide-react";
import { useFetchJson } from "../hooks/useFetchJson";
import ShareBar from "../components/ShareBar";

const API_BASE = import.meta.env.VITE_API_BASE;

type Stats = {
  ymd: string; total: number; sale: number; jeonse: number; wolse: number;
  by_sido: { sido_name: string; n: number }[];
  price_bands: { band: string; n: number }[];
};

function ymdDot(s: string): string {
  return s.length === 8 ? `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}` : s;
}

export default function TodayStats() {
  const statsRef = useRef<HTMLDivElement>(null);
  const stats = useFetchJson<Stats>(API_BASE ? `${API_BASE}/stats/today-listings-stats` : null);

  if (!API_BASE) return <div style={{ color: "crimson" }}>로컬 API가 설정되지 않았습니다.</div>;

  const s = stats.data;
  const maxBand = Math.max(1, ...(s?.price_bands ?? []).map((b) => b.n));

  return (
    <div ref={statsRef} className="share-target">
      <div className="section-head">
        <div className="section-title" style={{ marginTop: 4 }}>
          <BarChart3 size={15} strokeWidth={2.3} /> 오늘 매물 통계
          {s && <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}> · {ymdDot(s.ymd)}</span>}
        </div>
        <ShareBar targetRef={statsRef} title="오늘 매물 통계" fileName="콕집_오늘매물통계" />
      </div>
      {stats.loading ? <div className="muted">불러오는 중…</div> : s && (
        <>
          <div className="log-cards" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
            <div className="log-card"><div><div className="log-card-v">{s.total.toLocaleString()}</div><div className="log-card-l">총 신규</div></div></div>
            <div className="log-card"><div><div className="log-card-v" style={{ color: "#c0392b" }}>{s.sale.toLocaleString()}</div><div className="log-card-l">매매</div></div></div>
            <div className="log-card"><div><div className="log-card-v" style={{ color: "#1268d3" }}>{s.jeonse.toLocaleString()}</div><div className="log-card-l">전세</div></div></div>
            <div className="log-card"><div><div className="log-card-v" style={{ color: "#1a7f4b" }}>{s.wolse.toLocaleString()}</div><div className="log-card-l">월세</div></div></div>
          </div>

          <div className="log-grid2" style={{ marginTop: 12 }}>
            <div className="log-panel">
              <div className="log-panel-t">지역별 신규 매물 (상위)</div>
              {s.by_sido.map((r) => (
                <div key={r.sido_name} className="log-row">
                  <span>{r.sido_name}</span><b>{r.n.toLocaleString()}</b>
                </div>
              ))}
            </div>
            <div className="log-panel">
              <div className="log-panel-t">매매 가격대 분포</div>
              {s.price_bands.map((b) => (
                <div key={b.band} className="band-row">
                  <span className="band-label">{b.band}</span>
                  <span className="band-bar"><span className="band-fill" style={{ width: `${(b.n / maxBand) * 100}%` }} /></span>
                  <b className="band-n">{b.n}</b>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
