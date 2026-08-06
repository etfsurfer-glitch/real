import { useEffect, useMemo, useRef, useState } from "react";
import { downloadCardPng } from "../lib/share";
import { areaLabel } from "../lib/area";

const API = import.meta.env.VITE_API_BASE;

type Region = { code: string; name: string };
type Deal = {
  complex_no: string; complex_name: string; avg_excl: number | null; area_name: string;
  asking_min: number; discount_min: number; region_name: string;
};
type Row = {
  name: string; price: number; up?: number; sgg: string; dong: string;
  area: number | null; floor: number | null; bunyang: boolean; complex_high?: boolean;
};
type Reg = { name: string; region: string; count: number; record: number; avg: number | null };
type Digest = {
  sido_name: string; city_name: string; dong_name: string | null; region_level: string;
  record_highs: Row[]; sizes: { label: string; items: Row[] }[]; by_sigungu: Reg[]; nearby: Reg[];
};

function won(v?: number | null): string {
  if (v == null || isNaN(v)) return "-";
  if (v >= 1e8) { const e = Math.floor(v / 1e8), m = Math.floor((v % 1e8) / 1e4); return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`; }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
function todayK(): string { const d = new Date(); return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`; }
function meta(r: Row): string {
  return [[r.sgg, r.dong].filter(Boolean).join(" "),
    [r.area ? areaLabel(r.area) : "", r.floor ? `${r.floor}층` : ""].filter(Boolean).join(" · "),
    r.bunyang ? "분양권" : ""].filter(Boolean).join(" · ");
}

/** 지역코드로 급매+실거래 요약 데이터를 받아온다(관리자 화면·렌더 라우트 공용). */
export function useNewsletterData(sido: string, sigungu: string, dong: string) {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [dig, setDig] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!sigungu) { setDeals([]); setDig(null); return; }
    setLoading(true);
    const s2 = sido.slice(0, 2), s5 = sigungu.slice(0, 5), d10 = dong ? dong.slice(0, 10) : "";
    const dq = d10 ? `&dong=${d10}` : "";
    Promise.all([
      fetch(`${API}/stats/quick-deals?sigungu=${s5}${dq}&asset=apt&days=90&min_samples=3&min_discount=0.05&limit=6`)
        .then((r) => r.json()).then((j) => (j.items || []) as Deal[]).catch(() => []),
      fetch(`${API}/stats/region-digest?sido=${s2}&sigungu=${s5}${dq}&days=30`)
        .then((r) => r.json()).catch(() => null),
    ]).then(([dl, dg]) => { setDeals(dl); setDig(dg); }).finally(() => setLoading(false));
  }, [sido, sigungu, dong]);
  return { deals, dig, loading };
}

/** A4(1240×1754) 뉴스레터 카드 — 관리자 미리보기와 SNS 워커 캡처가 같은 컴포넌트를 쓴다. */
export function NewsletterCard({ regionName, deals, dig, cardRef }: {
  regionName: string; deals: Deal[]; dig: Digest | null;
  cardRef?: React.RefObject<HTMLDivElement>;
}) {
  const sizes2 = dig ? dig.sizes.filter((s) => ["59㎡", "84㎡"].includes(s.label)) : [];
  return (
    <div className="nl-card" ref={cardRef} id="nl-card">
      <div className="nl-head">
        <div className="nl-brand"><img src="/logo.svg" width={44} height={44} alt="" /><span>콕집</span></div>
        <div className="nl-title">{`${todayK()} ${regionName} 급매·실거래 정보`}</div>
        {/* 네이버 검색 유도 — 모든 뉴스레터 우측 상단 고정 */}
        <div className="nl-search">
          <div className="nl-search-box">
            <span>콕집</span>
            <i className="nl-search-ic" aria-hidden>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff"
                   strokeWidth="2.6" strokeLinecap="round">
                <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
              </svg>
            </i>
          </div>
          <small>네이버에서 <b>콕집</b>을 검색하세요</small>
        </div>
      </div>

      {deals.length > 0 && (
        <section className="nl-sec">
          <h3 className="nl-h nl-h-red">우리동네 급매</h3>
          <div className="nl-deals">
            {deals.slice(0, 6).map((x, i) => (
              <div className="nl-deal" key={i}>
                <div className="nl-deal-badge">{x.discount_min ? `${Math.round(Math.abs(x.discount_min) * 100)}% 싸요` : "급매"}</div>
                <div className="nl-deal-nm">{x.complex_name}</div>
                <div className="nl-deal-meta">{x.avg_excl ? areaLabel(x.avg_excl) : x.area_name}</div>
                <div className="nl-deal-price">{won(x.asking_min)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {dig && dig.record_highs.length > 0 && (
        <section className="nl-sec">
          <h3 className="nl-h nl-h-red">신고가 주요거래</h3>
          <div className="nl-rows">
            {dig.record_highs.slice(0, 7).map((r, i) => (
              <div className="nl-row" key={i}>
                <span className="nl-rk">{i + 1}</span>
                <span className="nl-nm">{r.name}
                  {r.complex_high
                    ? <b className="nl-b nl-b-cx">단지 신고가</b>
                    : <b className="nl-b nl-b-ty">타입 신고가</b>}
                  <em>{meta(r)}</em>
                </span>
                <span className="nl-val"><b>{won(r.price)}</b>{r.up && r.up > 0 ? <em>▲{won(r.up)}</em> : null}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {sizes2.length > 0 && (
        <section className="nl-sec">
          <h3 className="nl-h nl-h-blue">타입별 주요 실거래</h3>
          <div className="nl-types">
            {sizes2.map((s) => (
              <div className="nl-type" key={s.label}>
                <div className="nl-type-h">{s.label}</div>
                {s.items.slice(0, 3).map((r, i) => (
                  <div className="nl-row nl-row-sm" key={i}>
                    <span className="nl-rk">{i + 1}</span>
                    <span className="nl-nm">{r.name}<em>{[r.sgg, r.floor ? `${r.floor}층` : ""].filter(Boolean).join(" · ")}</em></span>
                    <span className="nl-val"><b>{won(r.price)}</b></span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>
      )}

      {dig && dig.by_sigungu.length > 0 && (
        <section className="nl-sec">
          <h3 className="nl-h nl-h-gold">{dig.region_level}별 거래 현황</h3>
          <div className="nl-gu">
            {dig.by_sigungu.slice(0, 4).map((b) => (
              <div className="nl-guitem" key={"o" + b.name}>
                <span className="nl-gunm">{b.name}</span>
                <span className="nl-gucnt">{b.count.toLocaleString()}건</span>
                <span className="nl-guavg">{b.avg ? won(b.avg) : ""}</span>
                <span className="nl-gurec">{b.record > 0 ? `신고가 ${b.record}` : ""}</span>
              </div>
            ))}
            {dig.nearby.length > 0 && <div className="nl-gu-sub">인접 지역</div>}
            {dig.nearby.slice(0, 2).map((b) => (
              <div className="nl-guitem nl-near" key={"n" + b.name}>
                <span className="nl-gunm"><em>{b.region}</em> {b.name}</span>
                <span className="nl-gucnt">{b.count.toLocaleString()}건</span>
                <span className="nl-guavg">{b.avg ? won(b.avg) : ""}</span>
                <span className="nl-gurec">{b.record > 0 ? `신고가 ${b.record}` : ""}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="nl-foot">
        <span><b>콕집</b> · koczip.com</span>
        <span>{todayK()} 기준 · 매물·실거래는 참고용, 거래 전 현장 확인</span>
      </div>
    </div>
  );
}

export default function AdminNewsletter() {
  const [sido, setSido] = useState("1100000000");
  const [sigungu, setSigungu] = useState("");
  const [dong, setDong] = useState("");
  const [sidos, setSidos] = useState<Region[]>([]);
  const [sggs, setSggs] = useState<Region[]>([]);
  const [dongs, setDongs] = useState<Region[]>([]);
  const cardRef = useRef<HTMLDivElement>(null);
  const { deals, dig, loading } = useNewsletterData(sido, sigungu, dong);

  useEffect(() => { fetch(`${API}/stats/changes/sido-list`).then((r) => r.json()).then((j) => setSidos(j.items || [])).catch(() => {}); }, []);
  useEffect(() => {
    if (!sido) return;
    fetch(`${API}/stats/sigungu-list?sido=${sido.slice(0, 2)}`).then((r) => r.json())
      .then((j) => setSggs(j.items || [])).catch(() => {});
  }, [sido]);
  useEffect(() => {
    if (!sigungu) { setDongs([]); return; }
    fetch(`${API}/stats/dong-list?sigungu=${sigungu.slice(0, 5)}`).then((r) => r.json())
      .then((j) => setDongs(j.items || [])).catch(() => {});
  }, [sigungu]);

  const regionName = useMemo(() => [
    sidos.find((s) => s.code === sido)?.name,
    sggs.find((s) => s.code === sigungu)?.name,
    dongs.find((s) => s.code === dong)?.name,
  ].filter(Boolean).join(" ") || "전국", [sido, sigungu, dong, sidos, sggs, dongs]);

  return (
    <div className="nl-page">
      <h2 style={{ margin: "4px 0 14px" }}>뉴스레터 이미지 생성 <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>(랜딩 급매+실거래 → A4 이미지)</span></h2>
      <div className="nl-controls">
        <select value={sido} onChange={(e) => { setSido(e.target.value); setSigungu(""); setDong(""); }}>
          {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value={sigungu} onChange={(e) => { setSigungu(e.target.value); setDong(""); }}>
          <option value="">시·군·구 선택</option>
          {sggs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <select value={dong} onChange={(e) => setDong(e.target.value)} disabled={!sigungu}>
          <option value="">동 전체</option>
          {dongs.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
        <button className="nl-dl" disabled={!dig || loading}
          onClick={() => cardRef.current && downloadCardPng(cardRef.current, `콕집_${regionName}_${todayK()}`.replace(/\s/g, "_"))}>
          이미지 다운로드
        </button>
        {loading && <span className="muted">불러오는 중…</span>}
        {!sigungu && <span className="muted">시·군·구 이상을 선택하세요.</span>}
      </div>

      <div className="nl-preview">
        <div className="nl-scale">
          <NewsletterCard regionName={regionName} deals={deals} dig={dig} cardRef={cardRef} />
        </div>
      </div>
    </div>
  );
}
