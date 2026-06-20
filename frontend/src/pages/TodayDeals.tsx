import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import ShareBar from "../components/ShareBar";
import { Flame, TrendingUp } from "lucide-react";
import { useFetchJson } from "../hooks/useFetchJson";
import { TxRegionPulse } from "./TxRegionPulse";

const API_BASE = import.meta.env.VITE_API_BASE;

// 카테고리: 매매 / 전세 / 월세 신고가 (각 가격순/증가율순 정렬)
type Cat = "A1" | "B1" | "B2";
type Sort = "price" | "premium";
const CATS: { key: Cat; label: string; color: string }[] = [
  { key: "A1", label: "매매", color: "#c0392b" },
  { key: "B1", label: "전세", color: "#1268d3" },
  { key: "B2", label: "월세", color: "#1a7f4b" },
];

function urlFor(trade: Cat, sort: Sort): string {
  return `tx-record-high?days=7&trade=${trade}&asset=apt&order=${sort}&min_prior=1&limit=12`;
}

// tx-record-high 응답을 카드 모양으로 정규화 (월세는 금액이 월세료)
type Card = {
  complex_no: string; complex_name: string; region: string | null;
  area: string; floor: number | null; date: string;
  price: number; prev: number | null; trend: number[];
};
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function normalize(items: any[]): Card[] {
  return items.map((x) => ({
    complex_no: x.complex_no, complex_name: x.complex_name, region: x.region_name,
    area: String(x.area_key), floor: x.floor, date: (x.record_date ?? "").slice(5),
    price: x.record_price, prev: x.prev_high,
    trend: (x.trend ?? []).map((p: { avg: number }) => p.avg),
  }));
}

// 미니 가격변동 스파크라인 (외부 라이브러리 없이 인라인 SVG). 흐름만 표현.
function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length < 2) return <div className="spark-empty" />;
  const w = 84, h = 28, pad = 3;
  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (w - 2 * pad);
    const y = pad + (1 - (v - min) / rng) * (h - 2 * pad);
    return [x, y] as [number, number];
  });
  const last = pts[pts.length - 1];
  const rising = data[data.length - 1] >= data[0];
  return (
    <svg width={w} height={h} className="spark" aria-hidden>
      <polyline points={pts.map((p) => p.join(",")).join(" ")}
        fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r="2.4" fill={rising ? color : "#888"} />
    </svg>
  );
}

function eok(v: number | null | undefined): string {
  if (v == null || v <= 0) return "—";
  const e = Math.floor(v / 100_000_000);
  const man = Math.round((v % 100_000_000) / 10_000);
  return e > 0 ? (man > 0 ? `${e}억 ${man.toLocaleString()}` : `${e}억`) : `${man.toLocaleString()}만`;
}

// 주소를 '시 구'까지만 (구 없으면 시까지). "경기도 화성시 동탄구 목동" → "화성시 동탄구"
function shortRegion(r: string | null): string {
  if (!r) return "";
  let p = r.trim().split(/\s+/).filter(Boolean);
  if (p.length > 1) p = p.slice(0, -1);                  // 읍면동 제거
  if (p.length > 1 && /도$/.test(p[0])) p = p.slice(1);  // 시도(○○도) 제거
  p = p.filter((t, i) => i === 0 || t !== p[i - 1]);     // 중복(세종시 세종시) 제거
  return p.join(" ");
}

function HighCard({ c, rank, color, monthly }: { c: Card; rank: number; color: string; monthly?: boolean }) {
  const up = c.prev && c.prev > 0 ? c.price - c.prev : null;
  const pct = c.prev && c.prev > 0 ? ((c.price - c.prev) / c.prev) * 100 : null;
  const suf = monthly ? "/월" : "";
  return (
    <Link to={`/complex/${c.complex_no}`} className="news-card">
      <div className="news-rank" style={{ background: color + "14", color }}>{rank}</div>
      <div className="news-body">
        <div className="news-title"><span className="nm">{c.complex_name}</span></div>
        <div className="news-region">
          <span>{shortRegion(c.region)}</span>
          {c.floor ? <span className="news-chip">{c.floor}층</span> : null}
          <span className="news-chip">전용 {c.area}㎡</span>
          <span className="news-date">{c.date}</span>
        </div>
        <div className="news-price">
          <span className="news-amt" style={{ color }}>{eok(c.price)}{suf}</span>
          {up != null && pct != null && (
            <span className="news-up" style={{ background: color + "14", color }}>
              <TrendingUp size={11} strokeWidth={2.8} /> {eok(up)}{suf} · {pct.toFixed(0)}%
            </span>
          )}
          {c.prev ? <span className="news-prev">직전 {eok(c.prev)}{suf}</span> : null}
        </div>
      </div>
      <Sparkline data={c.trend} color={color} />
    </Link>
  );
}

export default function TodayDeals() {
  const shareRef = useRef<HTMLDivElement>(null);
  const [cat, setCat] = useState<Cat>("A1");
  const [sort, setSort] = useState<Sort>("price"); // 기본 = 거래가격순(이슈몰이)
  const active = CATS.find((x) => x.key === cat)!;
  const q = useFetchJson<{ items: unknown[] }>(
    API_BASE ? `${API_BASE}/stats/${urlFor(cat, sort)}` : null
  );
  const cards = useMemo(() => normalize((q.data?.items as unknown[]) ?? []), [q.data]);

  if (!API_BASE) return <div style={{ color: "crimson" }}>로컬 API가 설정되지 않았습니다.</div>;

  return (
    <div ref={shareRef} className="share-target">
      <div className="section-title" style={{ marginTop: 4 }}>
        <Flame size={16} strokeWidth={2.3} style={{ color: "#e8590c" }} /> 오늘의 주요 신고가
      </div>
      <ShareBar targetRef={shareRef} title="오늘의 주요 신고가" fileName="콕집_오늘신고가" />
      <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
        최근 공개된 아파트 실거래 중 그 단지·평형의 역대 최고가를 경신한 거래입니다. 단지를 누르면 상세로 이동합니다.
      </div>

      <div className="cat-toggle">
        {CATS.map((c) => (
          <button key={c.key} className={cat === c.key ? "on" : ""}
            style={cat === c.key ? { background: c.color, borderColor: c.color } : undefined}
            onClick={() => setCat(c.key)}>
            {c.label}
          </button>
        ))}
      </div>

      <div className="sort-toggle">
        <span className="sort-label">정렬</span>
        <button className={sort === "price" ? "on" : ""} onClick={() => setSort("price")}>거래가격순</button>
        <button className={sort === "premium" ? "on" : ""} onClick={() => setSort("premium")}>증가율순</button>
      </div>

      {q.loading ? <div className="muted">불러오는 중…</div>
        : cards.length === 0 ? <div className="muted">해당 거래가 아직 없습니다.</div>
        : <div className="news-grid">{cards.map((c, i) => <HighCard key={c.complex_no + c.area + i} c={c} rank={i + 1} color={active.color} monthly={cat === "B2"} />)}</div>}

      <div className="section-title" style={{ marginTop: 24 }}>지역별 거래량 · 국민평형 시세</div>
      <TxRegionPulse />
    </div>
  );
}
