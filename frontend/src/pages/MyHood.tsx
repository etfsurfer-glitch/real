import { useEffect, useState, useRef, ReactNode } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/Loading";
import ShareBar from "../components/ShareBar";
import EasterEgg from "../components/EasterEgg";
import { MapPin, TrendingUp, BadgePercent, BarChart3, Trophy, Flame, ChevronRight } from "lucide-react";

const API = import.meta.env.VITE_API_BASE;
const LS = "koczip_myhood";
type Region = { code: string; name: string };
type Item = Record<string, unknown>;
type Data = { volume: Item[]; price: Item[]; change: Item[]; deals: Item[] };

function won(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return "-";
  if (v >= 1e8) {
    const e = Math.floor(v / 1e8), m = Math.floor((v % 1e8) / 1e4);
    return m ? `${e}억 ${m.toLocaleString()}` : `${e}억`;
  }
  return `${Math.floor(v / 1e4).toLocaleString()}만`;
}

// 우리동네 지역상태 + localStorage 기억. 드롭다운 변경 시에만 하위 초기화(복원은 그대로).
function useMyRegion() {
  const [sido, setSido] = useState("");
  const [sigungu, setSigungu] = useState("");
  const [dong, setDong] = useState("");
  const [sidos, setSidos] = useState<Region[]>([]);
  const [sigungus, setSigungus] = useState<Region[]>([]);
  const [dongs, setDongs] = useState<Region[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!API) { setReady(true); return; }
    fetch(`${API}/stats/changes/sido-list`).then((r) => r.json()).then((d) => setSidos(d.items || [])).catch(() => {});
    try {
      const s = JSON.parse(localStorage.getItem(LS) || "{}");
      if (s.sido) { setSido(s.sido); setSigungu(s.sigungu || ""); setDong(s.dong || ""); }
    } catch { /* ignore */ }
    setReady(true);
  }, []);
  useEffect(() => {
    if (!API || !sido) { setSigungus([]); return; }
    fetch(`${API}/stats/sigungu-list?sido=${sido}`).then((r) => r.json()).then((d) => setSigungus(d.items || [])).catch(() => {});
  }, [sido]);
  useEffect(() => {
    if (!API || !sigungu) { setDongs([]); return; }
    fetch(`${API}/stats/dong-list?sigungu=${sigungu}`).then((r) => r.json()).then((d) => setDongs(d.items || [])).catch(() => {});
  }, [sigungu]);
  useEffect(() => {
    if (ready) localStorage.setItem(LS, JSON.stringify({ sido, sigungu, dong }));
  }, [sido, sigungu, dong, ready]);

  const pickSido = (v: string) => { setSido(v); setSigungu(""); setDong(""); };
  const pickSigungu = (v: string) => { setSigungu(v); setDong(""); };
  const query = dong ? `dong=${dong}` : sigungu ? `sigungu=${sigungu}` : sido ? `sido=${sido}` : "";
  const shortName = dongs.find((d) => d.code === dong)?.name
    || sigungus.find((s) => s.code === sigungu)?.name
    || sidos.find((s) => s.code === sido)?.name || "";
  const name = [sidos.find((s) => s.code === sido)?.name, sigungus.find((s) => s.code === sigungu)?.name,
    dongs.find((d) => d.code === dong)?.name].filter(Boolean).join(" ");
  return { sido, sigungu, dong, sidos, sigungus, dongs, pickSido, pickSigungu, setDong, query, name, shortName, ready };
}

export default function MyHood() {
  const r = useMyRegion();
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [data, setData] = useState<Data | null>(null);
  const shareRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!API || !r.ready) return;
    setData(null);
    const q = r.query ? `${r.query}&` : "";
    const get = (p: string) => fetch(`${API}/stats/${p}`).then((x) => x.json()).then((d) => (d.items || []) as Item[]).catch(() => [] as Item[]);
    let cancelled = false;
    Promise.all([
      get(`tx-top-volume?${q}asset=${asset}&limit=7`),
      get(`tx-top-price?${q}asset=${asset}&trade=A1&limit=7`),
      get(`tx-price-change?${q}asset=${asset}&order=desc&limit=7`),
      get(`quick-deals?${q}asset=${asset}&days=90&min_samples=3&min_discount=0.05&limit=8`),
    ]).then(([volume, price, change, deals]) => { if (!cancelled) setData({ volume, price, change, deals }); });
    return () => { cancelled = true; };
  }, [r.ready, r.query, asset]);

  if (!r.ready) return <Loading />;
  if (!API) return <div className="muted" style={{ padding: 24 }}>이 기능은 운영 환경에서만 동작합니다.</div>;
  const scope = r.shortName || "전국";
  const assetLabel = asset === "apt" ? "아파트" : "오피스텔";

  // 더보기로 넘어갈 때 선택 지역을 그대로 전달. tx-stats는 동까지, 급매는 시군구까지(급매 페이지는 시군구 캐시 설계).
  const txQ = [r.sido && `sido=${r.sido}`, r.sigungu && `sigungu=${r.sigungu}`, r.dong && `dong=${r.dong}`].filter(Boolean).join("&");
  const moreTx = txQ ? `?${txQ}` : "";
  const dealQ = [r.sido && `sido=${r.sido}`, r.sigungu && `sigungu=${r.sigungu}`].filter(Boolean).join("&");
  const moreDeal = dealQ ? `?${dealQ}` : "";

  // 헤드라인 — 최고가(이슈성 1위) → 상승률 → 거래량 순. 상승률은 소형·표본적은 단지에서 튀어 후순위.
  const hi = data?.price?.[0];
  const up = data?.change?.[0];
  const vol = data?.volume?.[0];
  let digest: ReactNode = null;
  let DigestIcon = Trophy;
  if (hi) {
    digest = <><b className="scope">{scope}</b>에서 가장 높은 실거래가는 <b>{hi.complex_name as string}</b>{hi.excl_use_ar ? <em> 전용 {Math.round(hi.excl_use_ar as number)}㎡</em> : null}{hi.asset === "silv" ? <em className="tx-silv-note" style={{ display: "inline" }}> 분양권</em> : null}, <b className="hot">{won(hi.price as number)}</b>에 거래됐어요</>;
  } else if (up) {
    DigestIcon = TrendingUp;
    digest = <><b className="scope">{scope}</b> <b>{up.complex_name as string}</b> {assetLabel}가 이번 분기 <b className="up">+{Math.round((up.change_rate as number) * 100)}%</b> 올라 가장 뜨거워요</>;
  } else if (vol) {
    DigestIcon = BarChart3;
    digest = <><b className="scope">{scope}</b> <b>{vol.complex_name as string}</b>이(가) <b>{(vol.count as number)?.toLocaleString()}건</b>으로 거래가 가장 활발해요</>;
  }

  return (
    <div className="hood share-target" ref={shareRef}>
      {/* 히어로 */}
      <div className="hood-hero">
        <div className="hood-hero-top">
          <span className="hood-loc"><MapPin size={15} strokeWidth={2.5} aria-hidden /> {r.name || "전국"}</span>
          <span className="hood-seg">
            {(["apt", "offi"] as const).map((a) => (
              <button key={a} className={asset === a ? "on" : ""} onClick={() => setAsset(a)}>{a === "apt" ? "아파트" : "오피스텔"}</button>
            ))}
          </span>
        </div>
        <h1 className="hood-h1">우리동네 실거래와 급매를<br />콕집이 찾아드립니다</h1>
        <div className="hood-region">
          <select value={r.sido} onChange={(e) => r.pickSido(e.target.value)}>
            <option value="">시도</option>
            {r.sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <select value={r.sigungu} onChange={(e) => r.pickSigungu(e.target.value)} disabled={!r.sido}>
            <option value="">{r.sido ? "시군구 전체" : "시군구"}</option>
            {r.sigungus.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <select value={r.dong} onChange={(e) => r.setDong(e.target.value)} disabled={!r.sigungu}>
            <option value="">{r.sigungu ? "읍·면·동 전체" : "읍·면·동"}</option>
            {r.dongs.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
          </select>
        </div>
        {!r.sido && <div className="hood-hint">동네를 고르면 다음에도 기억해서 바로 보여드려요</div>}
        <EasterEgg />
      </div>

      <div className="hood-share"><ShareBar targetRef={shareRef} title={`${scope} 우리동네 실거래·급매`} fileName={`콕집_우리동네_${scope}`} /></div>

      {data == null ? <div className="hood-loading"><Loading /></div> : (
        <>
          {/* 헤드라인 한 줄 */}
          {digest && (
            <div className="hood-digest">
              <span className="hood-digest-ic"><DigestIcon size={16} strokeWidth={2.4} aria-hidden /></span>
              <span className="hood-digest-tx">{digest}</span>
            </div>
          )}

          {/* 우리동네 급매 — 카드 */}
          <div className="hood-sec-h">
            <h2><span className="ic deal"><BadgePercent size={17} strokeWidth={2.3} /></span> 우리동네 급매</h2>
            <Link to={`/quick-deals${moreDeal}`} className="hood-more">전체보기 <ChevronRight size={14} /></Link>
          </div>
          {data.deals.length === 0
            ? <Empty text={`${scope} ${assetLabel} 급매가 아직 없어요`} sub="범위를 넓히면 더 많이 볼 수 있어요" />
            : (
              <div className="deal-grid">
                {data.deals.map((x, i) => (
                  <Link key={i} className="deal-card" to={`/complex/${x.complex_no as string}`}>
                    <div className="deal-badge"><Flame size={12} strokeWidth={2.6} />{x.discount_min ? `${Math.round((x.discount_min as number) * 100)}% 싸요` : "급매"}</div>
                    <div className="deal-name">{x.complex_name as string}</div>
                    <div className="deal-area">{x.area_name as string}</div>
                    <div className="deal-price">{won(x.asking_min as number)}</div>
                    {x.avg_real ? <div className="deal-cmp">평균 {won(x.avg_real as number)}</div> : null}
                  </Link>
                ))}
              </div>
            )}

          {/* 랭킹 3종 */}
          <div className="rank-wrap">
            <RankCard title="거래 많은 단지" sub="최근 거래량" icon={<BarChart3 size={16} strokeWidth={2.3} />} accent="blue"
              more={`/tx-stats/top-volume${moreTx}`} items={data.volume} empty={`${scope} 거래 데이터가 적어요`}
              map={(x) => ({ cno: x.complex_no as string, name: x.complex_name as string, meta: (x.region_name as string) || "",
                val: x.count as number, valText: `${(x.count as number)?.toLocaleString()}건` })} />
            <RankCard title="상승률 높은 단지" sub="이전 분기 대비" icon={<TrendingUp size={16} strokeWidth={2.3} />} accent="red"
              more={`/tx-stats/price-change${moreTx}`} items={data.change} empty={`${scope}는 표본이 적어 산출이 어려워요`}
              map={(x) => ({ cno: x.complex_no as string, name: x.complex_name as string, meta: x.area_key ? `전용 ${x.area_key}㎡` : "",
                val: x.change_rate as number, valText: `+${Math.round((x.change_rate as number) * 100)}%`, valColor: "#d6336c" })} />
            <RankCard title="최고가 거래" sub="실거래가 높은순" icon={<Trophy size={16} strokeWidth={2.3} />} accent="gold"
              more={`/tx-stats/top-price${moreTx}`} items={data.price} empty={`${scope} 최고가 데이터가 적어요`}
              map={(x) => ({ cno: (x.complex_no ?? x.matched_complex_no) as string, name: x.complex_name as string,
                meta: `${x.excl_use_ar ? `전용 ${x.excl_use_ar}㎡` : ""}${x.asset === "silv" ? `${x.excl_use_ar ? " · " : ""}분양권` : ""}`,
                val: x.price as number, valText: won(x.price as number) })} />
          </div>
        </>
      )}
    </div>
  );
}

type Mapped = { cno?: string; name: string; meta: string; val: number; valText: string; valColor?: string };
function RankCard({ title, sub, icon, accent, items, map, more, empty }: {
  title: string; sub: string; icon: ReactNode; accent: "blue" | "red" | "gold";
  items: Item[]; map: (x: Item) => Mapped; more: string; empty: string;
}) {
  const rows = items.map(map);
  const max = Math.max(1, ...rows.map((r) => r.val || 0));
  return (
    <section className={`rank-card a-${accent}`}>
      <div className="rank-h">
        <span className="rank-t"><span className="ic">{icon}</span>{title}<em>{sub}</em></span>
        <Link to={more} className="hood-more">더보기 <ChevronRight size={13} /></Link>
      </div>
      {rows.length === 0 ? <Empty text={empty} sub="동네 범위를 넓혀보세요" />
        : (
          <div className="rank-rows">
            {rows.map((row, i) => {
              const body = (
                <>
                  <span className={`medal m${i < 3 ? i + 1 : 0}`}>{i + 1}</span>
                  <span className="rank-body">
                    <span className="rank-name">{row.name ?? "-"}{row.meta && <em> {row.meta}</em>}</span>
                    <span className="rank-bar"><i style={{ width: `${Math.max(6, ((row.val || 0) / max) * 100)}%` }} /></span>
                  </span>
                  <span className="rank-val" style={row.valColor ? { color: row.valColor } : undefined}>{row.valText}</span>
                </>
              );
              return row.cno
                ? <Link key={i} className="rank-row" to={`/complex/${row.cno}`}>{body}</Link>
                : <div key={i} className="rank-row">{body}</div>;
            })}
          </div>
        )}
    </section>
  );
}

function Empty({ text, sub }: { text: string; sub: string }) {
  return <div className="hood-empty"><MapPin size={20} strokeWidth={1.8} aria-hidden /><div>{text}</div><small>{sub}</small></div>;
}
