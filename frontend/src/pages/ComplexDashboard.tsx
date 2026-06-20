import { useEffect, useState, useRef, ReactNode } from "react";
import { Loading } from "../components/Loading";
import ShareBar from "../components/ShareBar";
import { Trophy, TrendingUp, Home, BadgePercent, ChevronRight, Flame, Layers, MapPin } from "lucide-react";

const API = import.meta.env.VITE_API_BASE;

type RecordHigh = { area_key: number; price: number; date: string; prev_high: number | null };
type Tx = { date: string; price: number; area: number | null; floor: number | null; is_silv?: boolean };
type TypeRow = { area_name: string; sale_count: number; sale_min: number | null; sale_max: number | null;
  jeonse_count: number; jeonse_min: number | null; jeonse_max: number | null; rent_count: number;
  supply_area: number | null; exclusive_area: number | null; type_households: number | null };
type Summary = {
  complex_no: string; complex_name: string; region: string; households: number | null;
  use_approve_ymd: string | null; builder: string | null; asset_type: string | null;
  building_count: number | null; parking_per_household: number | null;
  latitude: number | null; longitude: number | null;
  record_high: RecordHigh | null; recent_tx: Tx[]; recent_high: number | null;
  listing_counts: { A1: number; B1: number; B2: number; total: number }; by_type: TypeRow[];
};
// /complex/{no}/quick-deals: price(원), discount(음수), avg_real(실거래평균), naver_url
type Deal = { area_name?: string; price?: number; discount?: number; floor_info?: string;
  direction?: string; avg_real?: number; naver_url?: string; realtor_name?: string };

function won(v: number | null | undefined): string {
  if (v == null) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8), m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
function ymd(s: string | null | undefined): string {
  if (!s) return "";
  const m = String(s).replace(/-/g, "").match(/^(\d{4})(\d{2})(\d{2})/);
  return m ? `${m[1].slice(2)}.${m[2]}.${m[3]}` : String(s);
}
function builtYM(s: string | null | undefined): string {
  if (!s) return "";
  const m = String(s).replace(/-/g, "").match(/^(\d{4})(\d{2})/);
  return m ? `${m[1]}.${m[2]}` : "";
}

export default function ComplexDashboard({ complexNo, onGo }: {
  complexNo: string; onGo: (s: "tx" | "trend" | "realtor") => void;
}) {
  const [s, setS] = useState<Summary | null>(null);
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const shareRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!API) return;
    fetch(`${API}/complex/${complexNo}/summary`).then((r) => r.json()).then(setS).catch(() => setS(null));
    fetch(`${API}/complex/${complexNo}/quick-deals?min_discount=0.05`).then((r) => r.json())
      .then((d) => setDeals(d.items || [])).catch(() => setDeals([]));
  }, [complexNo]);
  if (!API) return null;
  if (!s) return <Loading />;

  const rec = s.record_high;
  const prem = rec && rec.prev_high ? Math.round(((rec.price - rec.prev_high) / rec.prev_high) * 100) : null;
  const latest = s.recent_tx[0];   // 가장 최근 실거래(날짜 내림차순 정렬)
  const c = s.listing_counts;
  const topTypes = s.by_type.slice(0, 7);

  // 급매의 타입명(공급기반 area_name="80")을 전용면적으로 보여주기 위한 매핑
  const exByType = new Map(s.by_type.map((t) => [t.area_name, t.exclusive_area]));
  const built = builtYM(s.use_approve_ymd);
  const info: [string, string][] = [];
  if (s.households) info.push(["세대수", `${s.households.toLocaleString()}세대`]);
  if (s.building_count) info.push(["동수", `${s.building_count}개 동`]);
  if (built) info.push(["준공", built]);
  if (s.parking_per_household) info.push(["주차", `세대당 ${s.parking_per_household.toFixed(2)}대`]);
  if (s.builder) info.push(["건설사", s.builder]);
  if (s.asset_type) info.push(["유형", s.asset_type]);

  return (
    <div className="cdash share-target" ref={shareRef}>
      <div className="cdash-share">
        <ShareBar targetRef={shareRef} title={`${s.complex_name} 단지 종합`} fileName={`콕집_${s.complex_name}`} />
      </div>
      {/* 단지 정보 */}
      <div className="cdash-info">
        {s.region && (
          <div className="cdash-info-loc">
            <span><MapPin size={13} strokeWidth={2.3} aria-hidden /> {s.region}</span>
          </div>
        )}
        {info.length > 0 && (
          <div className="cdash-info-grid">
            {info.map(([k, v]) => (
              <div key={k} className="cdash-info-item"><span className="cdash-info-k">{k}</span><span className="cdash-info-v">{v}</span></div>
            ))}
          </div>
        )}
      </div>

      {/* 와우 스탯 */}
      <div className="cdash-stats">
        <Stat accent="gold" icon={<Trophy size={17} />} label="역대 최고가"
          value={won(rec?.price)} sub={rec ? `전용 ${rec.area_key}㎡ · ${ymd(rec.date)}${prem != null ? ` · 직전 +${prem}%` : ""}` : "기록 없음"} />
        <Stat accent="red" icon={<TrendingUp size={17} />} label="최근 실거래가"
          value={won(latest?.price)} sub={latest ? `${ymd(latest.date)} 거래${latest.is_silv ? " · 분양권" : ""}` : "거래 없음"} onClick={() => onGo("tx")} />
        <Stat accent="blue" icon={<Home size={17} />} label="현재 매물"
          value={c.total.toLocaleString()} unit="건" sub={`매매 ${c.A1} · 전세 ${c.B1} · 월세 ${c.B2}`} onClick={() => onGo("realtor")} />
        <Stat accent="pink" icon={<BadgePercent size={17} />} label="급매"
          value={deals ? `${deals.length}` : "-"} unit="건" sub="실거래 평균보다 싼 매물" />
      </div>

      {/* 최근 실거래 (최고가 표시) */}
      <div className="cdash-h"><h3><TrendingUp size={15} strokeWidth={2.3} /> 최근 실거래</h3>
        <button className="cdash-more" onClick={() => onGo("tx")}>전체 실거래 <ChevronRight size={13} /></button></div>
      {s.recent_tx.length === 0 ? <div className="cdash-empty">최근 실거래가 없어요</div>
        : <div className="cdash-tx">
            {s.recent_tx.map((t, i) => (
              <div key={i} className="cdash-tx-row">
                <span className="cdash-tx-date">{ymd(t.date)}{t.is_silv && <span className="ctx-badge tx-silv-badge">분양권</span>}</span>
                <span className="cdash-tx-meta">전용 {t.area != null ? t.area.toFixed(2) : "-"}㎡ · {t.floor ?? "-"}층</span>
                <span className="cdash-tx-price">{won(t.price)}</span>
              </div>
            ))}
          </div>}

      {/* 평형별 호가 (최저~최고) */}
      <div className="cdash-h"><h3><Layers size={15} strokeWidth={2.3} /> 타입별 호가 <span className="muted">매매·전세 최저~최고</span></h3>
        <button className="cdash-more" onClick={() => onGo("trend")}>호가추이 <ChevronRight size={13} /></button></div>
      {topTypes.length === 0 ? <div className="cdash-empty">등록된 매물이 없어요</div>
        : <div className="cdash-types">
            {topTypes.map((t) => (
              <div key={t.area_name} className="cdash-type">
                <div className="cdash-type-name">{t.area_name} <span className="muted">매물 {t.sale_count + t.jeonse_count + t.rent_count}</span></div>
                <div className="cdash-type-area">{t.exclusive_area ? `전용 ${t.exclusive_area}㎡` : ""}{t.supply_area ? ` · 공급 ${t.supply_area}㎡` : ""}{t.type_households ? ` · ${t.type_households}세대` : ""}</div>
                <div className="cdash-type-rows">
                  <div className="cdash-type-row"><span className="tag sale">매매</span>
                    <b>{t.sale_min ? `${won(t.sale_min)} ~ ${won(t.sale_max)}` : "—"}</b></div>
                  <div className="cdash-type-row"><span className="tag jeonse">전세</span>
                    <b>{t.jeonse_min ? `${won(t.jeonse_min)} ~ ${won(t.jeonse_max)}` : "—"}</b></div>
                </div>
              </div>
            ))}
          </div>}

      {/* 급매 — 실거래 평균보다 싼 매물 전체. 전용면적·할인율·층/방향·네이버 매물 링크 */}
      {deals && deals.length > 0 && (
        <>
          <div className="cdash-h"><h3><BadgePercent size={15} strokeWidth={2.3} /> 급매 <span className="muted">실거래 평균보다 싼 매물 {deals.length}건</span></h3></div>
          <div className="cdash-deals">
            {deals.map((d, i) => {
              const ex = exByType.get(d.area_name || "");
              const pct = d.discount != null ? Math.round(-d.discount * 100) : null;
              const sub = [d.floor_info, d.direction].filter(Boolean).join(" · ");
              return (
                <div key={i} className="cdash-deal">
                  <div className="cdash-deal-top">
                    <span className="cdash-deal-area">{ex ? `전용 ${ex}㎡` : (d.area_name || "-")}</span>
                    {pct != null && <span className="cdash-deal-disc"><Flame size={10} strokeWidth={2.6} /> {pct}%↓</span>}
                  </div>
                  <div className="cdash-deal-price">{won(d.price)}</div>
                  <div className="cdash-deal-meta">
                    {sub && <span>{sub}</span>}
                    {d.avg_real ? <span>실거래 평균 {won(d.avg_real)}</span> : null}
                  </div>
                  {d.naver_url && (
                    <a className="cdash-deal-link" href={d.naver_url} target="_blank" rel="noopener noreferrer">
                      네이버 매물 보기 →
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ icon, accent, label, value, unit, sub, onClick }: {
  icon: ReactNode; accent: string; label: string; value: string; unit?: string; sub: string; onClick?: () => void;
}) {
  return (
    <div className={`cdash-stat a-${accent}${onClick ? " clickable" : ""}`} onClick={onClick}>
      <div className="cdash-stat-ic">{icon}</div>
      <div className="cdash-stat-label">{label}</div>
      <div className="cdash-stat-val">{value}{unit && <em>{unit}</em>}</div>
      <div className="cdash-stat-sub">{sub}</div>
    </div>
  );
}
