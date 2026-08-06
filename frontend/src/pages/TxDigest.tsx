import { useEffect, useState, ReactNode } from "react";
import { Link } from "react-router-dom";
import { TrendingUp, Ruler, MapPinned } from "lucide-react";
import { areaLabel } from "../lib/area";

const API = import.meta.env.VITE_API_BASE;
const LS = "koczip_myhood";   // MyHood(우리동네) 지역 저장 키 — 지역 공유

type Row = {
  name: string; price: number; up?: number; sgg: string; dong: string;
  pyeong: number | null; area: number | null; floor: number | null; bunyang: boolean;
  complex_high?: boolean;
};
type Reg = { name: string; region: string; code: string; count: number; record: number; avg: number | null };

/** 동(10자리)/구(5자리) 코드 → 그 지역 실거래 통계 페이지 URL */
function regHref(code: string): string {
  const sido = code.slice(0, 2) + "00000000";
  const sigungu = code.slice(0, 5) + "00000";
  const q = [`sido=${sido}`, `sigungu=${sigungu}`, code.length >= 10 ? `dong=${code}` : ""]
    .filter(Boolean).join("&");
  return `/tx-stats/top-price?${q}`;
}
type Digest = {
  sido_name: string; city_name: string; dong_name: string | null;
  region_level: string; days: number;
  record_highs: Row[];
  sizes: { label: string; items: Row[] }[];
  by_sigungu: Reg[];
  nearby: Reg[];
};

/** 콕집 공통 표기: 41.8억 → "41억 8,000" */
function won(v?: number | null): string {
  if (v == null || isNaN(v)) return "-";
  if (v >= 1e8) {
    const e = Math.floor(v / 1e8), m = Math.floor((v % 1e8) / 1e4);
    return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`;
  }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}
function metaOf(r: Row): string {
  const loc = [r.sgg, r.dong].filter(Boolean).join(" ");
  const size = [r.area ? areaLabel(r.area) : "", r.floor ? `${r.floor}층` : ""].filter(Boolean).join(" · ");
  return [loc, size, r.bunyang ? "분양권" : ""].filter(Boolean).join(" · ");
}

function DRow({ r, i, high }: { r: Row; i: number; high?: boolean }) {
  return (
    <div className="rank-row">
      <span className={`medal m${i < 3 ? i + 1 : 0}`}>{i + 1}</span>
      <span className="rank-body">
        <span className="rank-name">
          {r.name}
          {high && (r.complex_high
            ? <span className="txf-b" style={{ background: "#d23b3b", color: "#fff", marginLeft: 6 }}>단지 신고가</span>
            : <span className="txf-b" style={{ background: "#fef2f2", color: "#d23b3b", marginLeft: 6 }}>타입 신고가</span>)}
          <em> {metaOf(r)}</em>
        </span>
      </span>
      <span className="rank-val txd-val">
        <b>{won(r.price)}</b>
        {high && r.up != null && r.up > 0 && <em className="txd-up">▲{won(r.up)}</em>}
      </span>
    </div>
  );
}

/** 타입별 카드(내부 헤더 포함) — rank-wrap 그리드용 */
function TypeCard({ label, icon, rows }: { label: string; icon: ReactNode; rows: Row[] }) {
  return (
    <section className="rank-card a-blue">
      <div className="rank-h">
        <span className="rank-t"><span className="ic">{icon}</span>{label}</span>
      </div>
      {rows.length === 0 ? <div className="txd-none">거래가 아직 없어요</div>
        : <div className="rank-rows">{rows.map((r, i) => <DRow key={i} r={r} i={i} />)}</div>}
    </section>
  );
}

/** 우리동네 급매 아래에 붙는 '실거래 요약'. 지역은 MyHood(localStorage)와 공유·추종. */
export default function TxDigest() {
  const [region, setRegion] = useState<{ sido: string; sgg: string; dong: string }>({ sido: "", sgg: "", dong: "" });
  const [days, setDays] = useState(30);
  const [d, setD] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(false);

  // 우리동네 지역 읽기 + 변경 추종(같은 탭이라 storage 이벤트 대신 폴링). 동까지 선택하면 동 스코프.
  useEffect(() => {
    const read = () => {
      try {
        const s = JSON.parse(localStorage.getItem(LS) || "{}");
        const sido = String(s.sido || "").slice(0, 2);
        const dongFull = String(s.dong || "");
        const sgg = String(s.sigungu || dongFull).slice(0, 5);
        const dong = dongFull.length >= 10 ? dongFull.slice(0, 10) : "";
        setRegion((prev) => (prev.sido === sido && prev.sgg === sgg && prev.dong === dong
          ? prev : { sido, sgg, dong }));
      } catch { /* ignore */ }
    };
    read();
    const iv = setInterval(read, 1000);
    window.addEventListener("focus", read);
    return () => { clearInterval(iv); window.removeEventListener("focus", read); };
  }, []);

  useEffect(() => {
    if (!region.sido || !region.sgg) { setD(null); return; }
    setLoading(true);
    const dq = region.dong ? `&dong=${region.dong}` : "";
    fetch(`${API}/stats/region-digest?sido=${region.sido}&sigungu=${region.sgg}${dq}&days=${days}`)
      .then((r) => r.json()).then((j) => setD(j)).catch(() => setD(null))
      .finally(() => setLoading(false));
  }, [region.sido, region.sgg, region.dong, days]);

  const city = d ? [d.sido_name, d.city_name, d.dong_name].filter(Boolean).join(" ") : "우리동네";

  return (
    <>
      {!region.sgg && (
        <div className="txd-none">위 <b>우리동네</b>에서 시·군·구까지 선택하면 실거래 요약이 나와요</div>
      )}

      {region.sgg && (
        <>
          {/* ── 신고가 주요거래 : 단독 전체폭 섹션 ── */}
          <div className="hood-sec-h">
            <h2><span className="ic deal"><TrendingUp size={17} strokeWidth={2.3} /></span>{city} 신고가 주요거래</h2>
            <div className="txd-seg">
              {[7, 30, 90].map((n) => (
                <button key={n} className={days === n ? "on" : ""} onClick={() => setDays(n)}>{n}일</button>
              ))}
            </div>
          </div>
          {loading && <div className="txd-none">불러오는 중…</div>}
          {d && !loading && (
            <>
              <section className="rank-card a-red">
                {d.record_highs.length === 0 ? <div className="txd-none">신고가 경신 거래가 아직 없어요</div>
                  : <div className="rank-rows">{d.record_highs.map((r, i) => <DRow key={i} r={r} i={i} high />)}</div>}
              </section>

              {/* ── 타입별 주요 실거래 : 그리드 ── */}
              {d.sizes.length > 0 && (
                <>
                  <div className="hood-sec-h">
                    <h2><span className="ic deal"><Ruler size={17} strokeWidth={2.3} /></span>타입별 주요 실거래</h2>
                  </div>
                  <div className="rank-wrap">
                    {d.sizes.map((s) => (
                      <TypeCard key={s.label} label={s.label} rows={s.items}
                        icon={<Ruler size={16} strokeWidth={2.3} />} />
                    ))}
                  </div>
                </>
              )}

              {/* ── 지역별 거래 현황(구별/동별) + 인접 ── */}
              <div className="hood-sec-h">
                <h2><span className="ic deal"><MapPinned size={17} strokeWidth={2.3} /></span>{d.region_level}별 거래 현황</h2>
              </div>
              <section className="rank-card a-gold">
                <div className="txd-gu">
                  {d.by_sigungu.map((b, i) => (
                    <Link className="txd-guitem" to={regHref(b.code)} key={b.code}>
                      <span className={`medal m${i < 3 ? i + 1 : 0}`}>{i + 1}</span>
                      <span className="txd-gunm">{b.name}</span>
                      <span className="txd-gucnt" title="거래 건수">{b.count.toLocaleString()}건</span>
                      <span className="txd-guavg" title="평균 거래가">{b.avg ? won(b.avg) : ""}</span>
                      <span className="txd-gurec">{b.record > 0
                        ? <b className="txf-b" style={{ background: "#fef2f2", color: "#d23b3b" }} title="신고가 경신 건수">신고가 {b.record}</b>
                        : null}</span>
                    </Link>
                  ))}
                </div>
                {d.nearby && d.nearby.length > 0 && (
                  <>
                    <div className="txd-gu-sub">인접 {d.region_level === "동" ? "동네" : "지역"}</div>
                    <div className="txd-gu">
                      {d.nearby.map((b) => (
                        <Link className="txd-guitem txd-near" to={regHref(b.code)} key={b.code}>
                          <span className="txd-gunm">
                            {b.region && <em className="txd-gureg">{b.region}</em>} {b.name}
                          </span>
                          <span className="txd-gucnt" title="거래 건수">{b.count.toLocaleString()}건</span>
                          <span className="txd-guavg" title="평균 거래가">{b.avg ? won(b.avg) : ""}</span>
                          <span className="txd-gurec">{b.record > 0
                            ? <b className="txf-b" style={{ background: "#fef2f2", color: "#d23b3b" }} title="신고가 경신 건수">신고가 {b.record}</b>
                            : null}</span>
                        </Link>
                      ))}
                    </div>
                  </>
                )}
              </section>
            </>
          )}
        </>
      )}
    </>
  );
}
