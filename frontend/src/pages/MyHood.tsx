import { useEffect, useState, useRef, ReactNode } from "react";
import FavHeart from "../components/FavHeart";
import { Link } from "react-router-dom";
import { Loading } from "../components/Loading";
import RequestCta from "../components/RequestCta";
import ShareBar from "../components/ShareBar";
import DealMiniMap from "../components/DealMiniMap";
import { MapPin, TrendingUp, BadgePercent, BarChart3, Trophy, Flame, ChevronRight, Search, Building2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { areaLabel } from "../lib/area";

const API = import.meta.env.VITE_API_BASE;
const LS = "koczip_myhood";

// 첫 로드(컴퓨터 켜고 처음 접속) 시 API/CF 연결이 아직 콜드라 fetch가 실패하면 홈 위젯이
// 빈 상태로 뜬다(새로고침하면 웜이라 정상). 네트워크 오류·게이트웨이(502/3/4)는 짧게
// 재시도해 첫 로드에도 데이터가 바로 뜨게 한다.
async function fetchJsonRetry(url: string, tries = 3): Promise<unknown | null> {
  for (let i = 1; i <= tries; i++) {
    try {
      const r = await fetch(url);
      if (!r.ok) {
        if ((r.status === 502 || r.status === 503 || r.status === 504) && i < tries) {
          await new Promise((res) => setTimeout(res, Math.min(500 * i, 1500)));
          continue;
        }
        return null;
      }
      return await r.json();
    } catch {
      // 콜드 첫 로드에 CF↔origin 연결이 아직 안 풀려 실패(net::ERR_FAILED)하는 창을 넘기려
      // 여러 번 재시도(연결이 warm될 시간을 준다). keep-warm 크론과 함께 이중 방어.
      if (i < tries) {
        await new Promise((res) => setTimeout(res, Math.min(500 * i, 1500)));
        continue;
      }
      return null;
    }
  }
  return null;
}

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
    fetchJsonRetry(`${API}/stats/changes/sido-list`).then((d) => setSidos((d as { items?: Region[] })?.items || []));
    try {
      const s = JSON.parse(localStorage.getItem(LS) || "{}");
      if (s.sido) { setSido(s.sido); setSigungu(s.sigungu || ""); setDong(s.dong || ""); }
    } catch { /* ignore */ }
    setReady(true);
  }, []);
  useEffect(() => {
    if (!API || !sido) { setSigungus([]); return; }
    fetchJsonRetry(`${API}/stats/sigungu-list?sido=${sido}`).then((d) => setSigungus((d as { items?: Region[] })?.items || []));
  }, [sido]);
  useEffect(() => {
    if (!API || !sigungu) { setDongs([]); return; }
    fetchJsonRetry(`${API}/stats/dong-list?sigungu=${sigungu}`).then((d) => setDongs((d as { items?: Region[] })?.items || []));
  }, [sigungu]);
  useEffect(() => {
    if (ready) localStorage.setItem(LS, JSON.stringify({ sido, sigungu, dong }));
  }, [sido, sigungu, dong, ready]);

  const pickSido = (v: string) => { setSido(v); setSigungu(""); setDong(""); };
  const pickSigungu = (v: string) => { setSigungu(v); setDong(""); };
  // 내위치 → 좌표를 읍면동으로 역변환해 3단 한 번에 지정(코드가 결정적이라 목록 로드 전에 값만 세팅해도 됨)
  const setByCoord = (r: { sido: string; sigungu: string; dong: string }) => {
    setSido(r.sido); setSigungu(r.sigungu); setDong(r.dong);
  };
  const query = dong ? `dong=${dong}` : sigungu ? `sigungu=${sigungu}` : sido ? `sido=${sido}` : "";
  const shortName = dongs.find((d) => d.code === dong)?.name
    || sigungus.find((s) => s.code === sigungu)?.name
    || sidos.find((s) => s.code === sido)?.name || "";
  const name = [sidos.find((s) => s.code === sido)?.name, sigungus.find((s) => s.code === sigungu)?.name,
    dongs.find((d) => d.code === dong)?.name].filter(Boolean).join(" ");
  return { sido, sigungu, dong, sidos, sigungus, dongs, pickSido, pickSigungu, setDong, setByCoord, query, name, shortName, ready };
}

type CxHit = { complex_no: string; complex_name: string; region: string; households: number; type_name?: string };

// 랜딩 히어로의 단지 직접 검색. 지역 3단(시도→시군구→동)을 모르는 사용자가
// 단지명 하나로 바로 단지상세로 가게 하는 진입점.
function ComplexSearch() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<CxHit[]>([]);
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const kw = q.trim();
    if (kw.length < 2) { setHits([]); return; }
    const tm = setTimeout(() => {
      fetch(`${API}/complexes/search?q=${encodeURIComponent(kw)}&limit=8`)
        .then((r) => r.json()).then((j) => { setHits(j.items ?? []); setOpen(true); })
        .catch(() => {});
    }, 250);
    return () => clearTimeout(tm);
  }, [q]);

  // 바깥을 누르면 닫는다 — 히어로 위에 떠 있어 목록이 남아 있으면 아래 내용을 가린다
  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const go = (c: CxHit) => { setOpen(false); setQ(""); nav(`/complex/${c.complex_no}`); };

  return (
    <div className="hood-cxsearch" ref={boxRef}>
      <Search size={16} className="hood-cxsearch-ic" aria-hidden />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => hits.length && setOpen(true)}
        onKeyDown={(e) => { if (e.key === "Enter" && hits[0]) go(hits[0]); }}
        placeholder="단지명으로 찾기 (예: 헬리오시티)"
        aria-label="단지명으로 검색" />
      {open && hits.length > 0 && (
        <div className="hood-cxsearch-list">
          {hits.map((h) => (
            <button key={h.complex_no} onClick={() => go(h)}>
              <Building2 size={13} aria-hidden />
              <b>{h.complex_name}</b>
              {/* 주상복합은 같은 이름이 아파트·오피스텔로 갈려 배지 없이는 구분이 안 된다 */}
              {h.type_name && <i className={"hood-cx-ty ty-" + (h.type_name === "아파트" ? "apt" : "etc")}>{h.type_name}</i>}
              <span>{h.region}</span>
              {h.households > 0 && <em>{h.households.toLocaleString()}세대</em>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function MyHood({ digestSlot }: { digestSlot?: ReactNode } = {}) {
  const r = useMyRegion();
  const [asset, setAsset] = useState<"apt" | "offi">("apt");
  const [data, setData] = useState<Data | null>(null);
  const [pickCx, setPickCx] = useState<string>("");   // 지도 핀 → 카드 강조
  const shareRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!API || !r.ready) return;
    setData(null);
    const q = r.query ? `${r.query}&` : "";
    const get = (p: string) => fetchJsonRetry(`${API}/stats/${p}`).then((d) => ((d as { items?: Item[] })?.items || []) as Item[]);
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
  // 급매도 동까지·유형까지 그대로 넘긴다. 예전엔 시군구까지만 넘기고 유형을 버려서,
  // '더보기'를 누르면 여기서 보던 것과 다른 목록이 나왔다(서초구 8건 → 2건).
  const dealQ = [r.sido && `sido=${r.sido}`, r.sigungu && `sigungu=${r.sigungu}`,
                 r.dong && `dong=${r.dong}`, `asset=${asset}`].filter(Boolean).join("&");
  const moreDeal = dealQ ? `?${dealQ}` : "";

  // 헤드라인 — 최고가(이슈성 1위) → 상승률 → 거래량 순. 상승률은 소형·표본적은 단지에서 튀어 후순위.
  const hi = data?.price?.[0];
  const up = data?.change?.[0];
  const vol = data?.volume?.[0];
  let digest: ReactNode = null;
  let DigestIcon = Trophy;
  if (hi) {
    digest = <><b className="scope">{scope}</b>에서 가장 높은 실거래가는 <b>{hi.complex_name as string}</b>{hi.excl_use_ar ? <em> {areaLabel(hi.excl_use_ar as number)}</em> : null}{hi.asset === "silv" ? <em className="tx-silv-note" style={{ display: "inline" }}> 분양권</em> : null}, <b className="hot">{won(hi.price as number)}</b>에 거래됐어요</>;
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
        {/* 단지명 직접 검색 — 지역 3단을 거치지 않고 바로 단지로 가는 길.
            '단지찾기가 어디 있는지 모르겠다'는 피드백이 많아 랜딩 히어로에 노출한다. */}
        <ComplexSearch />
        {!r.sido && <div className="hood-hint">동네를 고르면 다음에도 기억해서 바로 보여드려요</div>}
      </div>

      {/* 관심단지 칩은 뺐다 — 헤더 하트(FavDashLink variant="head")와 같은 자리로 가는 중복 입구였고,
          히어로 바로 아래 떠 있어 어디에도 속하지 않아 보였다. */}
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
              <>
              {/* 위치 먼저, 목록은 그 아래 — 목록만 보면 어느 동네 물건인지 감이 안 온다 */}
              <DealMiniMap
                deals={data.deals.map((x) => ({
                  complex_no: String(x.complex_no), complex_name: x.complex_name as string,
                  area_name: x.area_name as string, asking_min: x.asking_min as number,
                  discount_min: x.discount_min as number,
                }))}
                onLocate={(lat, lng) => {
                  import("../lib/kakaomap").then(({ coordToRegion }) =>
                    coordToRegion(lat, lng).then((rr) => { if (rr) r.setByCoord(rr); }));
                }}
                onPick={(cno) => {
                  setPickCx(cno);
                  document.getElementById(`deal-${cno}`)?.scrollIntoView(
                    { behavior: "smooth", block: "center" });
                }} />
              <div className="deal-grid">
                {data.deals.map((x, i) => (
                  <Link key={i} id={`deal-${x.complex_no}`}
                    className={"deal-card" + (pickCx === String(x.complex_no) ? " on" : "")}
                    to={`/complex/${x.complex_no as string}`}>
                    <div className="deal-badge"><Flame size={12} strokeWidth={2.6} />{x.discount_min ? `${Math.round((x.discount_min as number) * 100)}% 싸요` : "급매"}</div>
                    <div className="deal-name">{x.complex_name as string}<FavHeart complexNo={String(x.complex_no)} complexName={x.complex_name as string} /></div>
                    <div className="deal-area">{x.avg_excl ? areaLabel(x.avg_excl as number) : (x.area_name as string)}</div>
                    <div className="deal-price">{won(x.asking_min as number)}</div>
                    {x.avg_real ? <div className="deal-cmp">평균 {won(x.avg_real as number)}</div> : null}
                  </Link>
                ))}
              </div>
              </>
            )}

          {/* 급매를 본 직후가 요청을 남기기에 가장 자연스러운 자리 */}
          <RequestCta
            title={`${scope}에서 원하는 조건만 남겨보세요`}
            sido={r.sido} sigungu={r.sigungu} dong={r.dong} asset={asset} />

          {digestSlot}

          {/* 랭킹 3종 */}
          <div className="rank-wrap">
            <RankCard title="거래 많은 단지" sub="최근 거래량" icon={<BarChart3 size={16} strokeWidth={2.3} />} accent="blue"
              more={`/tx-stats/top-volume${moreTx}`} items={data.volume} empty={`${scope} 거래 데이터가 적어요`}
              map={(x) => ({ cno: x.complex_no as string, name: x.complex_name as string, meta: (x.region_name as string) || "",
                val: x.count as number, valText: `${(x.count as number)?.toLocaleString()}건` })} />
            <RankCard title="상승률 높은 단지" sub="이전 분기 대비" icon={<TrendingUp size={16} strokeWidth={2.3} />} accent="red"
              more={`/tx-stats/price-change${moreTx}`} items={data.change} empty={`${scope}는 표본이 적어 산출이 어려워요`}
              map={(x) => ({ cno: x.complex_no as string, name: x.complex_name as string, meta: x.area_key ? areaLabel(x.area_key as number) : "",
                val: x.change_rate as number, valText: `+${Math.round((x.change_rate as number) * 100)}%`, valColor: "#d6336c" })} />
            <RankCard title="최고가 거래" sub="실거래가 높은순" icon={<Trophy size={16} strokeWidth={2.3} />} accent="gold"
              more={`/tx-stats/top-price${moreTx}`} items={data.price} empty={`${scope} 최고가 데이터가 적어요`}
              map={(x) => ({ cno: (x.complex_no ?? x.matched_complex_no) as string, name: x.complex_name as string,
                meta: `${x.excl_use_ar ? areaLabel(x.excl_use_ar as number) : ""}${x.asset === "silv" ? `${x.excl_use_ar ? " · " : ""}분양권` : ""}`,
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
                    <span className="rank-name">{row.name ?? "-"}{row.meta && <em> {row.meta}</em>}{row.cno ? <FavHeart complexNo={String(row.cno)} complexName={row.name ?? undefined} /> : null}</span>
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
