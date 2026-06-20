import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Flame, ExternalLink } from "lucide-react";
import { useFetchJson } from "../hooks/useFetchJson";
import ShareBar from "../components/ShareBar";
import { openListingPopup } from "../lib/listingPopup";

const API_BASE = import.meta.env.VITE_API_BASE;

type Deal = {
  article_no: string; complex_no: string; complex_name: string;
  area_name: string; price: number; avg_real: number; discount: number;
  floor_info: string | null; direction: string | null;
  realtor_name: string | null; region_name: string | null; naver_url: string;
};
type DealResp = { trade: string; count: number; items: Deal[] };
type Stats = {
  ymd: string; total: number; sale: number; jeonse: number; wolse: number;
  by_sido: { sido_name: string; n: number }[];
  price_bands: { band: string; n: number }[];
};

function eok(v: number | null | undefined): string {
  if (v == null || v <= 0) return "—";
  const e = Math.floor(v / 100_000_000);
  const man = Math.round((v % 100_000_000) / 10_000);
  return e > 0 ? (man > 0 ? `${e}억 ${man.toLocaleString()}` : `${e}억`)
    : `${man.toLocaleString()}만`;
}
function ymdDot(s: string): string {
  return s.length === 8 ? `${s.slice(0, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}` : s;
}

function DealCard({ d, monthly }: { d: Deal; monthly?: boolean }) {
  const pct = Math.round(Math.abs(d.discount) * 100);
  const suf = monthly ? "/월" : "";
  return (
    <div className="news-card deal">
      <div className="deal-badge">-{pct}%</div>
      <div className="news-body">
        <div className="news-title">
          <Link to={`/complex/${d.complex_no}`}>{d.complex_name}</Link>
          <span className="news-area"> {d.area_name}㎡</span>
        </div>
        <div className="news-region">
          {d.region_name ?? ""}{d.floor_info ? ` · ${d.floor_info}` : ""}{d.direction ? ` · ${d.direction}` : ""}
        </div>
        <div className="news-price">
          <span className="news-amt sale">{eok(d.price)}{suf}</span>
          <span className="news-prev">실거래 {eok(d.avg_real)}{suf}</span>
        </div>
        <div className="deal-foot">
          <button className="deal-link" type="button"
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); openListingPopup(d.naver_url); }}>
            네이버 매물 보기 <ExternalLink size={11} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function TodayListings() {
  const [trade, setTrade] = useState<"A1" | "B1" | "B2">("A1");
  const [sort, setSort] = useState<"price" | "discount">("price"); // 기본 = 금액순
  const dealsRef = useRef<HTMLDivElement>(null);
  const deals = useFetchJson<DealResp>(API_BASE
    ? `${API_BASE}/stats/today-deals?trade=${trade}&min_discount=0.05&limit=24&sort=${sort}` : null);
  const stats = useFetchJson<Stats>(API_BASE ? `${API_BASE}/stats/today-listings-stats` : null);

  if (!API_BASE) return <div style={{ color: "crimson" }}>로컬 API가 설정되지 않았습니다.</div>;

  const items = deals.data?.items ?? [];
  const s = stats.data;  // 날짜 배지용

  return (
    <>
      <div ref={dealsRef} className="share-target">
        <div className="section-head">
          <div className="section-title" style={{ marginTop: 4 }}>
            <Flame size={16} strokeWidth={2.3} style={{ color: "#e8590c" }} /> 오늘 새로 나온 급매
            {s && <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}> · {ymdDot(s.ymd)} 신규 등록</span>}
          </div>
          <ShareBar targetRef={dealsRef} title="오늘 새로 나온 급매" fileName="콕집_오늘급매" />
        </div>
        <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
          오늘 새로 등록된 매물 중 같은 단지·평형 실거래 평균보다 5% 이상 싸게 나온 매물입니다.
        </div>

      <div className="today-filter">
        <div className="rc-toggle">
          {(["A1", "B1", "B2"] as const).map((t) => (
            <button key={t} className={trade === t ? "on" : ""} onClick={() => setTrade(t)}>
              {t === "A1" ? "매매" : t === "B1" ? "전세" : "월세"}
            </button>
          ))}
        </div>
        <div className="sort-toggle">
          <span className="sort-label">정렬</span>
          <button className={sort === "price" ? "on" : ""} onClick={() => setSort("price")}>금액순</button>
          <button className={sort === "discount" ? "on" : ""} onClick={() => setSort("discount")}>할인율순</button>
        </div>
      </div>

      {deals.loading ? <div className="muted">불러오는 중…</div>
        : items.length === 0 ? <div className="muted">오늘 등록된 급매가 아직 없습니다.</div>
        : <div className="news-grid deals">{items.map((d) => <DealCard key={d.article_no} d={d} monthly={trade === "B2"} />)}</div>}
      </div>
    </>
  );
}
