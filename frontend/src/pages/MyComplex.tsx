import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { Search, MapPin, Building2, Home, TrendingUp, BadgePercent, ChevronRight, X, Clock } from "lucide-react";

const API = import.meta.env.VITE_API_BASE;
const RECENT_KEY = "koczip_complex_recent";

type Result = { complex_no: string; complex_name: string; region: string; households: number | null; listings: number };
type Recent = { complex_no: string; complex_name: string; region: string };

function loadRecent(): Recent[] {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); } catch { return []; }
}

export default function MyComplex() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Result[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [recent, setRecent] = useState<Recent[]>(loadRecent);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  useEffect(() => {
    const kw = q.trim();
    if (kw.length < 2 || !API) { setItems(null); setLoading(false); return; }
    setLoading(true);
    const t = setTimeout(() => {
      fetch(`${API}/complexes/search?q=${encodeURIComponent(kw)}`)
        .then((r) => r.json()).then((d) => setItems(d.items || []))
        .catch(() => setItems([])).finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const remember = (it: Result) => {
    const rec: Recent = { complex_no: it.complex_no, complex_name: it.complex_name, region: it.region };
    const next = [rec, ...recent.filter((x) => x.complex_no !== it.complex_no)].slice(0, 8);
    setRecent(next);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)); } catch { /* ignore */ }
  };
  const clearRecent = () => { setRecent([]); try { localStorage.removeItem(RECENT_KEY); } catch { /* ignore */ } };

  return (
    <div className="mc">
      <div className="hood-hero">
        <h1 className="hood-h1">우리단지를<br />콕집이 분석해 드립니다</h1>
        <p className="hood-sub">아파트·오피스텔 단지를 검색하면 <b>실거래가 추이·평형별 시세·매물·급매·중개사</b>까지 한 번에.</p>
        <div className="hood-namesearch">
          <Search size={16} strokeWidth={2.2} aria-hidden />
          <input ref={inputRef} placeholder="단지명 검색 (예: 헬리오시티, 은마, 크로바)"
            value={q} onChange={(e) => setQ(e.target.value)} />
          {q && <button onClick={() => { setQ(""); inputRef.current?.focus(); }} aria-label="지우기"><X size={14} /></button>}
        </div>
      </div>

      {/* 검색 결과 */}
      {items != null && (
        <div className="mc-results">
          {loading && items.length === 0 ? <div className="mc-msg">검색 중…</div>
            : items.length === 0 ? <div className="mc-msg">‘{q}’ 검색 결과가 없어요. 단지명 일부만(예: ‘헬리오’) 다시 검색해 보세요.</div>
            : items.map((it) => (
              <Link key={it.complex_no} className="mc-card" to={`/complex/${it.complex_no}`} onClick={() => remember(it)}>
                <div className="mc-card-main">
                  <div className="mc-name">{it.complex_name}</div>
                  <div className="mc-meta"><MapPin size={12} strokeWidth={2.2} /> {it.region || "-"}</div>
                  <div className="mc-badges">
                    {it.households ? <span className="mc-badge"><Building2 size={11} /> {it.households.toLocaleString()}세대</span> : null}
                    <span className="mc-badge home"><Home size={11} /> 매물 {it.listings.toLocaleString()}</span>
                  </div>
                </div>
                <span className="mc-go">분석 보기 <ChevronRight size={15} /></span>
              </Link>
            ))}
        </div>
      )}

      {/* 검색 전: 최근 본 단지 + 무엇을 분석하는지 */}
      {items == null && (
        <>
          {recent.length > 0 && (
            <div className="mc-sec">
              <div className="mc-sec-h"><span><Clock size={14} strokeWidth={2.3} /> 최근 본 단지</span>
                <button className="mc-clearbtn" onClick={clearRecent}>지우기</button></div>
              <div className="mc-recent">
                {recent.map((r) => (
                  <Link key={r.complex_no} className="mc-chip" to={`/complex/${r.complex_no}`}>
                    <b>{r.complex_name}</b><span>{r.region}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
          <div className="mc-sec">
            <div className="mc-sec-h"><span>단지를 찾으면 이런 걸 볼 수 있어요</span></div>
            <div className="mc-feat-grid">
              <Feat icon={<TrendingUp size={18} />} accent="blue" title="실거래가 추이" desc="평형·층별 실거래를 시간순 그래프로. 신고가 경신도 한눈에." />
              <Feat icon={<Building2 size={18} />} accent="green" title="평형별 시세·세대" desc="평형 구성과 면적, 매매·전세 시세 분포." />
              <Feat icon={<Home size={18} />} accent="navy" title="매물 현황" desc="매매·전세·월세 매물 수와 가격대." />
              <Feat icon={<BadgePercent size={18} />} accent="pink" title="급매·중개사" desc="평균보다 싼 급매 매물과 이 단지 매물 많은 중개사." />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Feat({ icon, accent, title, desc }: { icon: React.ReactNode; accent: string; title: string; desc: string }) {
  return (
    <div className={`mc-feat a-${accent}`}>
      <div className="mc-feat-ic">{icon}</div>
      <div className="mc-feat-t">{title}</div>
      <div className="mc-feat-d">{desc}</div>
    </div>
  );
}
