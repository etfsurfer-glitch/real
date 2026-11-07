// 지도 개편 시험판(testv2) — design/map_ui/지도UI_개편안.html 을 실제 화면으로.
// 운영 API 는 읽기(GET)만 쓴다. 새 API 가 필요한 곳(구 랭킹·사무소 좌표·호가추이 집계·콕집 매물)은
// 자리만 두고 '준비 중' 으로 표시한다. 운영 페이지는 koczip.com 링크로만 연결.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadKakao, wonShort, geocodeRegion } from "../src/lib/kakaomap";
import { areaLabel } from "../src/lib/area";
import { ComplexDrawer, Skel } from "./Drawer";

const API = "https://api.koczip.com";
const SITE = "https://koczip.com";

type Layer = "deals" | "price" | "realtor";
type View = { swLat: number; swLng: number; neLat: number; neLng: number; lat: number; lng: number; level: number };
type Region = { dong: string; dongName: string; sgg: string; sggName: string; sidoName: string };
type Cx = { complex_no: string; name: string; lat: number; lng: number; households?: number; listings?: number; c_sale?: number };
type Deal = {
  complex_no: string; complex_name: string | null; area_name: string; avg_excl: number | null; area1_m2: number | null;
  n_listings: number; asking_min: number; avg_real: number; n_real: number; discount_min: number; region_name: string | null;
};
// 시세분석 버블 한 칸. metric 에 따라 채워지는 값이 다르다(tx: change·ppy / vol: n·n_prev·pending·change /
// gap: ppy·jppy·gap84·rate / hoga: change·n(매물수)·cells).
type Agg = {
  code: string; name: string; lat: number; lng: number; n: number;
  change?: number | null; ppy?: number; n_prev?: number; pending?: number;
  jppy?: number; gap_ppy?: number; gap84?: number; rate?: number; n_jeonse?: number; cells?: number;
};
type PriceMetric = "tx" | "hoga" | "vol" | "gap";
// 기간 — 실거래 신고는 계약 후 30일 안에 해야 하고(실측 30일 내 91%·14일 70%), 동 단위 표본은 분기(90일)쯤
// 모여야 유의미하다. 기본 3개월, 더 넓게는 6·12개월. 호가는 스냅샷 보관 때문에 60일 고정.
const PRICE_WINDOWS: { d: number; l: string }[] = [{ d: 90, l: "3개월" }, { d: 180, l: "6개월" }, { d: 365, l: "12개월" }];
const REPORT_LAG = 30;
type Rk = { realtor_id: string; realtor_name: string; listings: number; staff_count?: number; tenure_years?: number; established_year?: number | string };

const LAYERS: { key: Layer; label: string }[] = [
  { key: "deals", label: "매물찾기" },
  { key: "price", label: "시세분석" },
  { key: "realtor", label: "중개사랭킹" },
];

const pct = (r: number | null | undefined, digits = 1) =>
  r == null ? "-" : `${r > 0 ? "+" : ""}${(r * 100).toFixed(digits)}%`;
const shortName = (s: string) => (s.length > 9 ? s.slice(0, 8) + "…" : s);
const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
const getJson = (u: string) => fetch(API + u).then((r) => (r.ok ? r.json() : Promise.reject(r.status)));

function useIsPhone() {
  const q = "(max-width: 899px)";
  const [m, setM] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return m;
}

// 공유 링크: ?layer=&lat=&lng=&lv=&cx=
function readUrl() {
  const p = new URLSearchParams(location.search);
  const layer = (["deals", "price", "realtor"].includes(p.get("layer") || "") ? p.get("layer") : "deals") as Layer;
  const pm = (["tx", "hoga", "vol", "gap"].includes(p.get("m") || "") ? p.get("m") : "tx") as PriceMetric;
  const lat = parseFloat(p.get("lat") || ""), lng = parseFloat(p.get("lng") || ""), lv = parseInt(p.get("lv") || "");
  return { layer, pm, lat: isNaN(lat) ? 37.5045 : lat, lng: isNaN(lng) ? 127.1095 : lng, lv: isNaN(lv) ? 5 : lv, cx: p.get("cx") };
}

export default function App() {
  const init = useMemo(readUrl, []);
  const phone = useIsPhone();
  const [layer, setLayer] = useState<Layer>(init.layer);
  const [view, setView] = useState<View | null>(null);
  const [region, setRegion] = useState<Region | null>(null);
  const [sel, setSel] = useState<Cx | null>(null);
  const [inView, setInView] = useState<Cx[]>([]);
  const [agg, setAgg] = useState<Agg[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggMeta, setAggMeta] = useState<{ snapshot?: string; baseline?: string }>({});
  const [pm, setPm] = useState<PriceMetric>(init.pm);
  const [pw, setPw] = useState<number>(90);
  const [rkDong, setRkDong] = useState<{ code: string; name: string } | null>(null);
  const [mapErr, setMapErr] = useState("");
  const [hint, setHint] = useState("");
  const [sheet, setSheet] = useState<"peek" | "half" | "full">("half");
  const [more, setMore] = useState(false);
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const ovs = useRef<any[]>([]);

  // ── 지도 ───────────────────────────────────────────
  useEffect(() => {
    let off = false;
    loadKakao().then(() => {
      if (off || !mapEl.current) return;
      const k = window.kakao;
      const map = new k.maps.Map(mapEl.current, { center: new k.maps.LatLng(init.lat, init.lng), level: init.lv });
      mapRef.current = map;
      let t: ReturnType<typeof setTimeout>;
      const idle = () => {
        clearTimeout(t);
        t = setTimeout(() => {
          const b = map.getBounds(), c = map.getCenter();
          setView({ swLat: b.getSouthWest().getLat(), swLng: b.getSouthWest().getLng(), neLat: b.getNorthEast().getLat(),
            neLng: b.getNorthEast().getLng(), lat: c.getLat(), lng: c.getLng(), level: map.getLevel() });
        }, 200);
      };
      k.maps.event.addListener(map, "idle", idle);
      idle();
    }).catch(() => {
      // 지도 없이도 목록은 보이게: 처음 좌표 둘레를 화면으로 간주
      setMapErr("지도를 불러오지 못했어요. 카카오 개발자 콘솔에 이 주소(도메인)가 등록돼 있어야 합니다.");
      const d = 0.02 * Math.pow(2, init.lv - 4);
      setView({ swLat: init.lat - d / 2, swLng: init.lng - d, neLat: init.lat + d / 2, neLng: init.lng + d, lat: init.lat, lng: init.lng, level: init.lv });
    });
    return () => { off = true; };
  }, [init]);

  useEffect(() => {
    const m = mapRef.current;
    if (m) setTimeout(() => m.relayout(), 50);
  }, [phone, sel, sheet]);

  // 주소창 = 공유 링크
  useEffect(() => {
    if (!view) return;
    const p = new URLSearchParams({ layer, lat: view.lat.toFixed(5), lng: view.lng.toFixed(5), lv: String(view.level) });
    if (sel) p.set("cx", sel.complex_no);
    history.replaceState(null, "", "?" + p.toString());
  }, [layer, view, sel]);

  // 지도 가운데 → 동·구
  useEffect(() => {
    if (!view) return;
    let off = false;
    getJson(`/stats/nearest-dong?lat=${view.lat}&lng=${view.lng}`).then((d) => {
      if (off || !d.found) return;
      const parts = String(d.region_name || "").split(" ");
      const r: Region = { dong: d.cortar_no, dongName: d.dong_name || "", sgg: d.cortar_no.slice(0, 5) + "00000",
        sggName: parts[1] || "", sidoName: parts[0] || "" };
      setRegion((o) => (o && o.dong === r.dong ? o : r));
    }).catch(() => {});
    return () => { off = true; };
  }, [view?.lat, view?.lng]);   // eslint-disable-line react-hooks/exhaustive-deps

  const pickComplex = useCallback((c: Cx, pan = true) => {
    setSel(c);
    if (phone) setSheet("half");
    const m = mapRef.current;
    if ((pan || phone) && m && c.lat) {
      m.panTo(new window.kakao.maps.LatLng(c.lat, c.lng));
      // 휴대폰은 아래 시트가 지도 절반을 덮으니 핀을 위쪽 절반 가운데로
      if (phone) setTimeout(() => m.panBy(0, Math.round(window.innerHeight * 0.24)), 350);
    }
  }, [phone]);

  // 공유 링크로 들어온 단지
  useEffect(() => {
    if (!init.cx || sel) return;
    const hit = inView.find((c) => c.complex_no === init.cx);
    if (hit) setSel(hit);
  }, [inView]);   // eslint-disable-line react-hooks/exhaustive-deps

  // ── 레이어별 지도 표시 ────────────────────────────────
  const selNo = sel?.complex_no;
  useEffect(() => {
    const map = mapRef.current;
    if (!view) return;
    const k = window.kakao;
    let off = false;
    const bbox = `swlat=${view.swLat}&swlng=${view.swLng}&nelat=${view.neLat}&nelng=${view.neLng}`;
    const clear = () => { ovs.current.forEach((o) => o.setMap(null)); ovs.current = []; };
    const put = (lat: number, lng: number, html: string, onClick?: () => void, z = 1, yAnchor = 1) => {
      if (!map) return;
      const el = document.createElement("div");
      el.innerHTML = html;
      if (onClick) el.addEventListener("click", (e) => { e.stopPropagation(); onClick(); });
      const ov = new k.maps.CustomOverlay({ position: new k.maps.LatLng(lat, lng), content: el, yAnchor, clickable: true, zIndex: z });
      el.addEventListener("mouseenter", () => ov.setZIndex(999));
      el.addEventListener("mouseleave", () => ov.setZIndex(z));
      ov.setMap(map);
      ovs.current.push(ov);
    };

    if (layer === "deals") {
      // 지도에는 급매와 콕집 매물이 있는 단지만 올린다. 그 밖의 단지는 네이버 매물뿐이라 띄우지 않는다.
      // 콕집 매물(직접 등록)은 아직 원천이 없어 비어 있다 — 생기면 kokCx 에 합친다.
      getJson(`/stats/quick-deals-map?${bbox}&min_discount=0.03`).then((jd) => {
        if (off) return;
        clear();
        if (jd.too_wide) { setInView([]); setHint("지도를 조금 더 확대하면 급매 단지가 보여요"); return; }
        const by = new Map<string, Cx & { disc: number; n: number }>();
        for (const d of jd.items || []) {
          const o = by.get(d.complex_no);
          if (o) { o.disc = Math.min(o.disc, d.discount); o.n += 1; }
          else by.set(d.complex_no, { complex_no: d.complex_no, name: d.complex_name, lat: d.lat, lng: d.lng, disc: d.discount, n: 1 });
        }
        const kokCx: Cx[] = [];
        const items = [...by.values()];
        setInView(items);
        setHint(items.length ? "" : "이 지역엔 지금 급매가 없어요");
        for (const c of items) {
          const on = c.complex_no === selNo;
          put(c.lat, c.lng, `<div class="t2-pin deal${on ? " on" : ""}"><b>${esc(shortName(c.name))}</b><i>급매 ${pct(c.disc, 0)}</i></div>`,
            () => pickComplex(c, false), on ? 50 : 5);
        }
        for (const c of kokCx) {
          put(c.lat, c.lng, `<div class="t2-pin kok"><b>${esc(shortName(c.name))}</b><i>콕집</i></div>`, () => pickComplex(c, false), 6);
        }
        // 검색으로 고른 단지가 급매 단지가 아니면 그 하나만 표시(어디인지는 보여야 하니까)
        if (sel && sel.lat && !by.has(sel.complex_no)) {
          put(sel.lat, sel.lng, `<div class="t2-pin plain on"><b>${esc(shortName(sel.name))}</b></div>`, undefined, 50);
        }
      }).catch(() => {});
    } else {
      // 시세분석·중개사랭킹: 동(확대)·구(축소) 버블 — /stats/tx-map/agg. 시세분석은 칩(metric)·기간(window)에 따라
      // 같은 버블에 실거래가 변동률·호가 변동·거래량·갭을 바꿔 칠한다.
      const lv = view.level >= 7 ? "gu" : "dong";
      const isPrice = layer === "price";
      const qs = new URLSearchParams({ level: lv, asset: "apt", trade: "A1",
        metric: isPrice ? pm : "tx", window_days: String(isPrice ? pw : 120),
        sw_lat: String(view.swLat), sw_lng: String(view.swLng), ne_lat: String(view.neLat), ne_lng: String(view.neLng),
        min_n: lv === "gu" ? "8" : "3" });
      setAggLoading(true);
      getJson(`/stats/tx-map/agg?${qs}`).then((d) => {
        if (off) return;
        clear(); setInView([]);
        const items: Agg[] = d.items || [];
        setAgg(items); setAggMeta({ snapshot: d.snapshot, baseline: d.baseline }); setAggLoading(false);
        for (const a of items) {
          if (isPrice) {
            const b = bubble(pm, a);
            put(a.lat, a.lng, `<div class="t2-bub ${b.cls}"><b>${esc(a.name)}</b><span>${b.main}</span><em>${b.sub}</em></div>`,
              () => { map.setLevel(lv === "gu" ? 6 : 4, { anchor: new k.maps.LatLng(a.lat, a.lng) }); }, 1, 0.5);
          } else if (lv === "dong") {
            const on = (rkDong?.code || region?.dong) === a.code;
            put(a.lat, a.lng, `<div class="t2-dong${on ? " on" : ""}"><b>${esc(a.name)}</b><span>${on ? "랭킹 보는 중" : "랭킹 보기"}</span></div>`,
              () => setRkDong({ code: a.code, name: a.name }), on ? 50 : 1, 0.5);
          } else {
            put(a.lat, a.lng, `<div class="t2-dong gu"><b>${esc(a.name)}</b><span>확대해서 동 고르기</span></div>`,
              () => { map.setLevel(5, { anchor: new k.maps.LatLng(a.lat, a.lng) }); }, 1, 0.5);
          }
        }
      }).catch(() => { if (!off) { setAgg([]); setAggLoading(false); } });
    }
    return () => { off = true; };
  }, [layer, view, selNo, rkDong, region?.dong, pickComplex, pm, pw]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (layer !== "deals") setHint(""); }, [layer]);

  useEffect(() => { setRkDong(null); }, [region?.sgg]);

  // ── 화면 ─────────────────────────────────────────
  const panel = (
    <>
      {layer === "deals" && <DealsPanel region={region} inView={inView} onPick={pickComplex} zoomedOut={!!hint && inView.length === 0} />}
      {layer === "price" && <PricePanel region={region} agg={agg} level={view?.level ?? 5} metric={pm} onMetric={setPm}
        win={pw} onWin={setPw} loading={aggLoading} meta={aggMeta} />}
      {layer === "realtor" && <RealtorPanel region={region} dong={rkDong} />}
    </>
  );

  return (
    <div className={"t2" + (phone ? " phone" : " desk")}>
      <TopBar phone={phone} onPick={(c) => {
        const m = mapRef.current;
        if (m && c.lat) { m.setLevel(4); m.setCenter(new window.kakao.maps.LatLng(c.lat, c.lng)); }
        pickComplex(c, false);
      }} />
      <div className="t2-body">
        {!phone && <aside className="t2-side">{panel}</aside>}
        <main className="t2-mapwrap">
          <div ref={mapEl} className="t2-map" />
          {mapErr && <div className="t2-maperr">{mapErr}</div>}
          {hint && !mapErr && <div className="t2-hint">{hint}</div>}
          <div className="t2-layers" role="tablist">
            {LAYERS.map((l) => (
              <button key={l.key} role="tab" aria-selected={layer === l.key} className={layer === l.key ? "on" : ""}
                onClick={() => { setLayer(l.key); setSel(null); }}>{l.label}</button>
            ))}
          </div>
          <div className="t2-zoom">
            <button onClick={() => mapRef.current?.setLevel(mapRef.current.getLevel() - 1)} aria-label="확대">+</button>
            <button onClick={() => mapRef.current?.setLevel(mapRef.current.getLevel() + 1)} aria-label="축소">−</button>
          </div>
          {!phone && <a className="t2-fab" href={`${SITE}/request`} target="_blank" rel="noreferrer">콕집에 요청하기</a>}
          {!phone && sel && <aside className="t2-drawer"><ComplexDrawer cx={sel} onClose={() => setSel(null)} /></aside>}
          {phone && (
            <section className={"t2-sheet " + sheet}>
              <button className="t2-grab" aria-label="목록 크기 바꾸기"
                onClick={() => setSheet(sheet === "peek" ? "half" : sheet === "half" ? "full" : "peek")}><i /></button>
              <div className="t2-sheet-in">
                {sel ? <ComplexDrawer cx={sel} onClose={() => setSel(null)} /> : panel}
              </div>
            </section>
          )}
        </main>
      </div>
      {phone && (
        <nav className="t2-tabbar">
          <a className="on" href="/">지도</a>
          <a href={`${SITE}/tx-stats`} target="_blank" rel="noreferrer">통계</a>
          <a className="req" href={`${SITE}/request`} target="_blank" rel="noreferrer">요청</a>
          <a href={`${SITE}/today`} target="_blank" rel="noreferrer">TODAY</a>
          <button onClick={() => setMore(!more)}>더보기</button>
          {more && (
            <div className="t2-more" onClick={() => setMore(false)}>
              <a href={`${SITE}/buy-calculator`} target="_blank" rel="noreferrer">도구 · 매수 계산기</a>
              <a href={`${SITE}/jeonse-check`} target="_blank" rel="noreferrer">도구 · 전세 안전 점검</a>
              <a href={`${SITE}/settings`} target="_blank" rel="noreferrer">내 정보</a>
              <a href={`${SITE}/lounge`} target="_blank" rel="noreferrer">중개사라운지</a>
            </div>
          )}
        </nav>
      )}
    </div>
  );
}

// ── 상단 바 ─────────────────────────────────────────
function TopBar({ phone, onPick }: { phone: boolean; onPick: (c: Cx) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const [tools, setTools] = useState(false);
  useEffect(() => {
    const kw = q.trim();
    if (kw.length < 2) { setHits([]); return; }
    const t = setTimeout(() => {
      getJson(`/complexes/search?q=${encodeURIComponent(kw)}&limit=8`).then((j) => setHits(j.items || [])).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [q]);
  const choose = async (h: any) => {
    setQ(""); setHits([]);
    const pos = await geocodeRegion(`${h.region} ${h.complex_name}`) || await geocodeRegion(h.region);
    onPick({ complex_no: h.complex_no, name: h.complex_name, lat: pos?.lat ?? 0, lng: pos?.lng ?? 0,
      households: h.households, listings: h.listings });
  };
  return (
    <header className="t2-top">
      <a className="t2-logo" href="/">콕집<span>지도 시험판</span></a>
      <div className="t2-search">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="단지 이름으로 찾기" aria-label="단지 검색" />
        {hits.length > 0 && (
          <ul className="t2-hits">
            {hits.map((h) => (
              <li key={h.complex_no}><button onClick={() => choose(h)}><b>{h.complex_name}</b><span>{h.region} · {h.type_name}</span></button></li>
            ))}
          </ul>
        )}
      </div>
      {!phone && (
        <nav className="t2-util">
          <a href={`${SITE}/today`} target="_blank" rel="noreferrer">TODAY</a>
          <a href={`${SITE}/tx-stats`} target="_blank" rel="noreferrer">통계</a>
          <span className="t2-dd">
            <button onClick={() => setTools(!tools)} aria-expanded={tools}>도구 ▾</button>
            {tools && (
              <span className="t2-ddm" onClick={() => setTools(false)}>
                <a href={`${SITE}/buy-calculator`} target="_blank" rel="noreferrer">매수 계산기</a>
                <a href={`${SITE}/jeonse-check`} target="_blank" rel="noreferrer">전세 안전 점검</a>
                <a href={`${SITE}/ai`} target="_blank" rel="noreferrer">AI 질문</a>
              </span>
            )}
          </span>
          <a className="lounge" href={`${SITE}/lounge`} target="_blank" rel="noreferrer">중개사라운지</a>
        </nav>
      )}
    </header>
  );
}

// ── 매물찾기: 위 2/3 급매, 아래 1/3 콕집 매물 ─────────────────
function DealsPanel({ region, inView, onPick, zoomedOut }: { region: Region | null; inView: Cx[]; onPick: (c: Cx) => void; zoomedOut: boolean }) {
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const [onlyView, setOnlyView] = useState(true);
  useEffect(() => {
    if (!region) return;
    setDeals(null);
    const qs = new URLSearchParams({ days: "90", min_samples: "3", min_discount: "0.03", min_listings: "1",
      trade_type: "A1", asset: "apt", limit: "300", sigungu: region.sgg });
    getJson(`/stats/quick-deals?${qs}`).then((j) => setDeals(j.items || [])).catch(() => setDeals([]));
  }, [region?.sgg]);   // eslint-disable-line react-hooks/exhaustive-deps

  const cxMap = useMemo(() => new Map(inView.map((c) => [c.complex_no, c])), [inView]);
  const rows = useMemo(() => {
    let xs = [...(deals || [])].sort((a, b) => a.discount_min - b.discount_min);
    if (onlyView && !zoomedOut && cxMap.size) xs = xs.filter((d) => cxMap.has(d.complex_no));
    return xs.slice(0, 60);
  }, [deals, onlyView, cxMap, zoomedOut]);

  return (
    <div className="t2-split">
      <section className="t2-split-a">
        <div className="t2-ph">
          <h2>급매 <small>{region ? `${region.sggName}` : ""}</small></h2>
          <label className="t2-chk"><input type="checkbox" checked={onlyView} onChange={(e) => setOnlyView(e.target.checked)} />지도 안만</label>
        </div>
        <p className="t2-note">최근 90일 실거래 평균보다 3% 이상 싼 매매 호가(평형별 최저가 기준)</p>
        {onlyView && deals && deals.length > 0 && (zoomedOut || !cxMap.size) && (
          <p className="t2-note warn">지도 안에는 급매가 없어 {region?.sggName || "이 구"} 전체를 보여 드려요.</p>
        )}
        {deals == null ? <Skel /> : rows.length === 0 ? (
          <p className="t2-empty">{onlyView ? "지도 안에 급매가 없어요. 지도를 옮기거나 '지도 안만'을 꺼 보세요." : "이 구에 급매가 없어요."}</p>
        ) : (
          <ul className="t2-list">
            {rows.map((d) => {
              const c = cxMap.get(d.complex_no);
              return (
                <li key={d.complex_no + d.area_name}>
                  <button onClick={() => onPick(c || { complex_no: d.complex_no, name: d.complex_name || "", lat: 0, lng: 0 })}>
                    <span className="nm"><b>{d.complex_name}</b><em>{areaLabel(d.avg_excl ?? d.area1_m2)} · 매물 {d.n_listings}</em></span>
                    <span className="pr"><b>{wonShort(d.asking_min)}</b><em>실거래 평균 {wonShort(d.avg_real)}</em></span>
                    <span className="dc">{pct(d.discount_min)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>
      <section className="t2-split-b">
        <div className="t2-ph"><h2><span className="t2-kz">콕집</span> 콕집 매물</h2></div>
        <p className="t2-empty sm">콕집에 직접 등록된 매물이 여기에 먼저 보여요. 아직 이 지역엔 없어요.</p>
        <div className="t2-cta">
          <a href={`${SITE}/request`} target="_blank" rel="noreferrer">이 동네 매물 요청하기</a>
          <a className="ghost" href={`${SITE}/lounge`} target="_blank" rel="noreferrer">중개사 · 매물 올리기</a>
        </div>
      </section>
    </div>
  );
}

// ── 시세분석 ───────────────────────────────────────
const eok = (v: number) => (v >= 1e8 ? `${(v / 1e8).toFixed(1)}억` : `${Math.round(v / 1e4).toLocaleString()}만`);
const signPct = (v: number | null | undefined) => (v == null ? "-" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`);
const chgCls = (v: number | null | undefined) => (v == null ? "flat" : v > 0.5 ? "up" : v < -0.5 ? "down" : "flat");

// 버블 한 칸의 글자·색. 변동률 칩(실거래가·호가·거래량)은 빨강 상승/파랑 하락, 갭은 전세가율 색(높을수록 진함).
function bubble(m: PriceMetric, a: Agg): { cls: string; main: string; sub: string } {
  if (m === "tx") return { cls: chgCls(a.change), main: signPct(a.change), sub: `${Math.round((a.ppy ?? 0) / 1e4).toLocaleString()}만/평` };
  if (m === "hoga") return { cls: chgCls(a.change), main: signPct(a.change), sub: `매물 ${a.n.toLocaleString()}건` };
  if (m === "vol") return { cls: chgCls(a.change), main: a.change == null ? `${a.n}건` : signPct(a.change), sub: `${a.n}건 (전 ${a.n_prev ?? 0})` };
  const r = a.rate ?? 0;
  return { cls: r >= 70 ? "gap hi" : r >= 55 ? "gap" : "gap lo", main: `${r.toFixed(0)}%`, sub: `갭 ${eok(a.gap84 ?? 0)}` };
}

const METRICS: { k: PriceMetric; l: string; h: string }[] = [
  { k: "tx", l: "실거래가", h: "실거래 평당가 변동" },
  { k: "hoga", l: "호가추이", h: "매물 호가 변동" },
  { k: "vol", l: "거래량", h: "거래량 변동" },
  { k: "gap", l: "갭·전세가율", h: "매매−전세 갭" },
];

function PricePanel({ region, agg, level, metric, onMetric, win, onWin, loading, meta }: {
  region: Region | null; agg: Agg[]; level: number; metric: PriceMetric; onMetric: (m: PriceMetric) => void;
  win: number; onWin: (d: number) => void; loading: boolean; meta: { snapshot?: string; baseline?: string };
}) {
  const unit = level >= 7 ? "구별" : "동별";
  const rows = useMemo(() => {
    const r = [...agg];
    if (metric === "gap") r.sort((a, b) => (b.rate ?? 0) - (a.rate ?? 0));
    else r.sort((a, b) => (b.change ?? -999) - (a.change ?? -999));
    return r;
  }, [agg, metric]);
  const m = METRICS.find((x) => x.k === metric)!;
  // 기간 설명 — 신고 기한(계약 후 30일)을 지표마다 다르게 다룬다.
  const note =
    metric === "tx" ? <>아파트 매매, 계약일 기준 최근 {win}일 vs 그 전 {win}일 평당가. 가격 평균은 신고 지연에 둔감해 오늘까지 세되, 최근 {REPORT_LAG}일 계약은 신고가 진행 중(약 70% 반영). <span className="up">빨강 상승</span> · <span className="down">파랑 하락</span></>
    : metric === "vol" ? <>신고 기한({REPORT_LAG}일)이 지난 계약만 셉니다: {REPORT_LAG}일 전부터 거꾸로 {win}일 vs 그 전 {win}일. 최근 {REPORT_LAG}일 계약은 '신고 중'으로 따로 — 지금 세면 30%쯤 모자라 보이기 때문.</>
    : metric === "gap" ? <>최근 {win}일 매매·전세 평당 평균의 차이. 갭 금액은 84㎡ 기준 환산, 색은 전세가율(전세÷매매). 매매·전세 각 3건 이상인 곳만.</>
    : <>매물 호가(같은 단지·평형 셀만 비교): {meta.baseline ?? "60일 전"} → {meta.snapshot ?? "오늘"}. 매물 스냅샷 보관 때문에 60일 고정.</>;
  return (
    <div className="t2-pad">
      <div className="t2-chips">
        {METRICS.map((c) => (
          <button key={c.k} className={metric === c.k ? "on" : ""} onClick={() => onMetric(c.k)}>{c.l}</button>
        ))}
      </div>
      <div className="t2-ph">
        <h2>{m.h} <small>{unit}</small></h2>
        {metric !== "hoga" && (
          <div className="t2-chips sm t2-period" role="radiogroup" aria-label="기간">
            {PRICE_WINDOWS.map((w) => (
              <button key={w.d} role="radio" aria-checked={win === w.d} className={win === w.d ? "on" : ""} onClick={() => onWin(w.d)}>{w.l}</button>
            ))}
          </div>
        )}
      </div>
      <p className="t2-note">{note}</p>
      {loading && rows.length === 0 ? <Skel /> : rows.length === 0 ? <div className="t2-empty">이 범위엔 표본이 모자라요. 지도를 조금 넓혀 보세요.</div> : (
        <ul className="t2-rows">
          {rows.map((a) => {
            const b = bubble(metric, a);
            const mid =
              metric === "tx" ? `${Math.round((a.ppy ?? 0) / 1e4).toLocaleString()}만/평 · ${a.n}건`
              : metric === "hoga" ? `매물 ${a.n.toLocaleString()}건 · ${a.cells ?? 0}평형`
              : metric === "vol" ? `${a.n}건 ← ${a.n_prev ?? 0}건${a.pending ? ` · 신고 중 ${a.pending}` : ""}`
              : `매매 ${Math.round((a.ppy ?? 0) / 1e4).toLocaleString()} · 전세 ${Math.round((a.jppy ?? 0) / 1e4).toLocaleString()}만/평 · 갭 ${eok(a.gap84 ?? 0)}`;
            return (
              <li key={a.code}>
                <span className="nm">{a.name}</span>
                <span className="mid">{mid}</span>
                <span className={metric === "gap" ? "" : b.cls}>{b.main}</span>
              </li>
            );
          })}
        </ul>
      )}
      <a className="t2-stat-link" href={`${SITE}/tx-stats`} target="_blank" rel="noreferrer">
        {region ? `${region.sggName} ` : "이 지역 "}통계 전체 보기 (표·그래프) ↗
      </a>
    </div>
  );
}

// ── 중개사랭킹 ─────────────────────────────────────
type Scope = "dong" | "gu" | "sido" | "nat";
function RealtorPanel({ region, dong }: { region: Region | null; dong: { code: string; name: string } | null }) {
  const [scope, setScope] = useState<Scope>("dong");
  const [sort, setSort] = useState<"listings" | "staff" | "tenure">("listings");
  const [rows, setRows] = useState<Rk[] | null>(null);
  const [apiName, setApiName] = useState("");
  const code = dong?.code || region?.dong;
  const name = dong?.name || region?.dongName || apiName;
  useEffect(() => {
    setRows(null);
    if (scope === "dong" && code) {
      getJson(`/stats/realtors/by-dong?cortar=${code}&scope=complex&limit=200`).then((j) => { setApiName(j.dong_name || ""); setRows(j.items || []); }).catch(() => setRows([]));
    } else if (scope === "sido" && region) {
      getJson(`/stats/realtors/by-sido?limit=50&scope=complex`).then((j) => {
        const g = j.groups?.[region.sidoName] || [];
        setRows(g.map((r: any) => ({ ...r, listings: r.count })));
      }).catch(() => setRows([]));
    } else if (scope === "nat") {
      getJson(`/stats/realtors/national?limit=50&scope=complex`).then((j) =>
        setRows((j.items || []).map((r: any) => ({ ...r, listings: r.count })))).catch(() => setRows([]));
    } else setRows([]);
  }, [scope, code, region?.sidoName]);   // eslint-disable-line react-hooks/exhaustive-deps

  const sorted = useMemo(() => {
    const xs = [...(rows || [])];
    if (sort === "staff") xs.sort((a, b) => (b.staff_count ?? 0) - (a.staff_count ?? 0));
    else if (sort === "tenure") xs.sort((a, b) => (b.tenure_years ?? 0) - (a.tenure_years ?? 0));
    else xs.sort((a, b) => b.listings - a.listings);
    return xs.slice(0, 50);
  }, [rows, sort]);
  const max = Math.max(1, ...sorted.map((r) => r.listings));
  const title = scope === "dong" ? name : scope === "gu" ? region?.sggName : scope === "sido" ? region?.sidoName : "전국";

  return (
    <div className="t2-pad">
      <div className="t2-seg">
        {([["dong", "동"], ["gu", region?.sggName || "구"], ["sido", region?.sidoName || "시도"], ["nat", "전국"]] as [Scope, string][]).map(([k, l]) => (
          <button key={k} className={scope === k ? "on" : ""} onClick={() => setScope(k)}>{l}</button>
        ))}
      </div>
      <div className="t2-ph"><h2>{title} 중개사 랭킹</h2></div>
      {scope === "dong" && (
        <div className="t2-chips sm">
          {([["listings", "매물 수"], ["staff", "직원 수"], ["tenure", "업력"]] as const).map(([k, l]) => (
            <button key={k} className={sort === k ? "on" : ""} onClick={() => setSort(k)}>{l}순</button>
          ))}
        </div>
      )}
      <p className="t2-note">
        {scope === "dong" ? "기준: 이 동 단지형 매물 수 · 지도에서 다른 동을 누르면 바뀌어요" : "기준: 단지형 매물 수"}
      </p>
      {scope === "gu" ? (
        <p className="t2-empty">구 단위 랭킹은 새 API 가 필요해요(B단계). 동·시도·전국으로 볼 수 있어요.</p>
      ) : rows == null ? <Skel /> : sorted.length === 0 ? <p className="t2-empty">랭킹 자료가 없어요.</p> : (
        <ol className="t2-rank">
          {sorted.map((r, i) => (
            <li key={r.realtor_id + i} className={i === 0 ? "top1" : ""}>
              <a href={`${SITE}/realtor/${encodeURIComponent(r.realtor_id)}`} target="_blank" rel="noreferrer">
                <span className="n">{i + 1}</span>
                <span className="o"><b>{r.realtor_name}</b>
                  <em>{[r.staff_count ? `직원 ${r.staff_count}명` : "", r.tenure_years ? `업력 ${r.tenure_years}년` :
                    r.established_year ? `${r.established_year}년 개업` : ""].filter(Boolean).join(" · ")}</em></span>
                <span className="bm"><i style={{ width: `${(r.listings / max) * 100}%` }} /></span>
                <span className="c">{r.listings.toLocaleString()}</span>
              </a>
            </li>
          ))}
        </ol>
      )}
      <p className="t2-foot">사무소 위치 핀은 좌표를 채운 뒤(B단계) 지도에 올라와요. 지금은 동 버블로 고릅니다.</p>
    </div>
  );
}
