// 지도 개편 시험판(testv2) — design/map_ui/지도UI_개편안.html 을 실제 화면으로.
// 운영 API 는 읽기(GET)만 쓴다. 새 API 가 필요한 곳(구 랭킹·사무소 좌표·호가추이 집계·콕집 매물)은
// 자리만 두고 '준비 중' 으로 표시한다. 운영 페이지는 koczip.com 링크로만 연결.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { loadKakao, wonShort, geocodeRegion } from "../src/lib/kakaomap";
import { areaLabel } from "../src/lib/area";
import { ComplexDrawer, JibunDrawer, Skel, Dd, SPECIAL_KINDS, type DrawerTab, type Jibun } from "./Drawer";
import { useSession, authHeaders, LoginBox } from "./Request";

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
type PriceMetric = "tx" | "hoga" | "vol" | "gap" | "rh";   // rh=신고가 단지
// 시세분석 유형. 아파트·오피스텔은 동·구 버블(/stats/tx-map/agg), 빌라·상가·단독은 지번 핀(/stats/tx-map)
type PAsset = "apt" | "offi" | "villa" | "nrg" | "house";
const PASSETS: { k: PAsset; l: string }[] = [{ k: "apt", l: "아파트" }, { k: "offi", l: "오피스텔" }, { k: "villa", l: "빌라" }, { k: "nrg", l: "상가" }, { k: "house", l: "단독" }];
const isJibun = (a: PAsset) => a === "villa" || a === "nrg" || a === "house";
// 신고가 한 줄(/stats/tx-record-high) + 좌표(/complexes/coords)
type RH = { complex_no: string; complex_name: string; region_name: string; area_key: number; record_price: number; record_date: string; prev_high: number | null;
  premium: number; floor: number; n: number; lat: number; lng: number };
// 지번 핀(/stats/tx-map items)
type JPin = { lat: number; lng: number; name: string; ref: string; n: number; last: number; latest: string; ppy: number; avg: number; built: string | null };
// 매물찾기 필터(지도 위 필터 바). 값은 /map/listings 파라미터와 1:1.
type Trade = "A1" | "B1" | "B2";
type Flt = { types: string[]; trade: Trade; pmin: number; pmax: number; amin: number; amax: number; afrom: number; ato: number; hmin: number; hmax: number;
  only: boolean; disc: number; sp: string };   // only=급매만, disc=급매 할인 문턱, sp=특수조건(owner|tenant|loan|"")
const FLT0: Flt = { types: ["APT", "ABYG", "JGC"], trade: "A1", pmin: 0, pmax: 0, amin: 0, amax: 0, afrom: 0, ato: 0, hmin: 0, hmax: 0, only: false, disc: 0.03, sp: "" };
const CX_TYPES: { k: string; l: string }[] = [
  { k: "APT", l: "아파트" }, { k: "ABYG", l: "아파트분양권" }, { k: "JGC", l: "재건축" }, { k: "OPST", l: "오피스텔" }, { k: "OBYG", l: "오피스텔분양권" },
];
const TRADES: { k: Trade; l: string }[] = [{ k: "A1", l: "매매" }, { k: "B1", l: "전세" }, { k: "B2", l: "월세" }];
const E = 1e8;
const PRICE_OPTS: { l: string; a: number; b: number }[] = [
  { l: "전체", a: 0, b: 0 }, { l: "3억 이하", a: 0, b: 3 * E }, { l: "3~5억", a: 3 * E, b: 5 * E }, { l: "5~10억", a: 5 * E, b: 10 * E },
  { l: "10~15억", a: 10 * E, b: 15 * E }, { l: "15~20억", a: 15 * E, b: 20 * E }, { l: "20~30억", a: 20 * E, b: 30 * E }, { l: "30억 이상", a: 30 * E, b: 0 },
];
const AREA_OPTS: { l: string; a: number; b: number }[] = [
  { l: "전체", a: 0, b: 0 }, { l: "40㎡ 이하 (~12평)", a: 0, b: 40 }, { l: "40~60㎡ (12~18평)", a: 40, b: 60 }, { l: "60~85㎡ (18~25평)", a: 60, b: 85 },
  { l: "85~102㎡ (25~31평)", a: 85, b: 102 }, { l: "102~135㎡ (31~41평)", a: 102, b: 135 }, { l: "135㎡ 이상 (41평~)", a: 135, b: 0 },
];
const YEAR = new Date().getFullYear();
const APPROVE_OPTS: { l: string; a: number; b: number }[] = [
  { l: "전체", a: 0, b: 0 }, { l: "5년 이내", a: YEAR - 5, b: 0 }, { l: "10년 이내", a: YEAR - 10, b: 0 }, { l: "10~20년", a: YEAR - 20, b: YEAR - 10 },
  { l: "20~30년", a: YEAR - 30, b: YEAR - 20 }, { l: "30년 이상", a: 0, b: YEAR - 30 },
];
const HH_OPTS: { l: string; a: number; b: number }[] = [
  { l: "전체", a: 0, b: 0 }, { l: "100세대 이상", a: 100, b: 0 }, { l: "300세대 이상", a: 300, b: 0 }, { l: "500세대 이상", a: 500, b: 0 },
  { l: "1,000세대 이상", a: 1000, b: 0 }, { l: "2,000세대 이상", a: 2000, b: 0 },
];
const fltQs = (f: Flt) => new URLSearchParams({ types: f.types.join(","), trade: f.trade, price_min: String(f.pmin), price_max: String(f.pmax),
  area_min: String(f.amin), area_max: String(f.amax), approve_from: String(f.afrom), approve_to: String(f.ato), hh_min: String(f.hmin), hh_max: String(f.hmax) });
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
  const pm = (["tx", "hoga", "vol", "gap", "rh"].includes(p.get("m") || "") ? p.get("m") : "tx") as PriceMetric;
  const lat = parseFloat(p.get("lat") || ""), lng = parseFloat(p.get("lng") || ""), lv = parseInt(p.get("lv") || "");
  return { layer, pm, lat: isNaN(lat) ? 37.5045 : lat, lng: isNaN(lng) ? 127.1095 : lng, lv: isNaN(lv) ? 5 : lv, cx: p.get("cx") };
}

export default function App() {
  const init = useMemo(readUrl, []);
  const phone = useIsPhone();
  const [layer, setLayer] = useState<Layer>(init.layer);
  // 단지를 누르면 서랍은 지금 보고 있는 레이어의 탭으로 연다
  const drawerTab: DrawerTab = layer === "price" ? "tx" : layer === "realtor" ? "realtor" : "deals";
  const [view, setView] = useState<View | null>(null);
  const [region, setRegion] = useState<Region | null>(null);
  const [sel, setSel] = useState<Cx | null>(null);
  const [inView, setInView] = useState<Cx[]>([]);
  const [agg, setAgg] = useState<Agg[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggMeta, setAggMeta] = useState<{ snapshot?: string; baseline?: string }>({});
  const [pm, setPm] = useState<PriceMetric>(init.pm);
  const [pw, setPw] = useState<number>(90);
  const [pa, setPa] = useState<PAsset>("apt");   // 시세분석 유형
  const [rhs, setRhs] = useState<RH[]>([]);          // 신고가 단지(지도 안)
  const [jpins, setJpins] = useState<JPin[]>([]);     // 빌라·상가·단독 지번 핀(지도 안)
  const [selJ, setSelJ] = useState<Jibun | null>(null);   // 고른 지번
  // 관심단지 — 운영 /me/favorites (로그인 필요). 로그인 전엔 하트를 누르면 로그인 안내.
  const session = useSession();
  const [favs, setFavs] = useState<{ complex_no: string; complex_name: string }[] | null>(null);
  const [askLogin, setAskLogin] = useState(false);
  const [flt, setFlt] = useState<Flt>(FLT0);
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
  }, [phone, sel, selJ, sheet]);

  useEffect(() => {
    if (!session) { setFavs(null); return; }
    fetch(`${API}/me/favorites`, { headers: authHeaders(session) }).then((r) => (r.ok ? r.json() : { items: [] })).then((j) => setFavs(j.items || [])).catch(() => setFavs([]));
  }, [session]);
  useEffect(() => { if (session) setAskLogin(false); }, [session]);
  const toggleFav = useCallback(async (c: Cx) => {
    if (!session) { setAskLogin(true); return; }
    const has = (favs || []).some((f) => f.complex_no === c.complex_no);
    setFavs((o) => has ? (o || []).filter((f) => f.complex_no !== c.complex_no) : [...(o || []), { complex_no: c.complex_no, complex_name: c.name }]);
    const r = await fetch(`${API}/me/favorites${has ? `/${c.complex_no}` : ""}`, { method: has ? "DELETE" : "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(session) }, body: has ? undefined : JSON.stringify({ complex_no: c.complex_no, complex_name: c.name }) }).catch(() => null);
    if (!r || !r.ok) {   // 실패(20개 초과 등)면 되돌리고 서버 상태로
      fetch(`${API}/me/favorites`, { headers: authHeaders(session) }).then((x) => x.json()).then((j) => setFavs(j.items || [])).catch(() => {});
      if (r) { const j = await r.json().catch(() => ({})); if (typeof j.detail === "string") setHint(j.detail); }
    }
  }, [session, favs]);
  // 관심단지 목록에서 고르면 좌표를 받아 지도를 옮긴다
  const goComplex = useCallback((no: string, name: string) => {
    getJson(`/complexes/coords?ids=${no}`).then((j) => {
      const h = j.items?.[0]; if (!h) return;
      const m = mapRef.current;
      if (m) { m.setLevel(4); m.setCenter(new window.kakao.maps.LatLng(h.lat, h.lng)); }
      pickComplex({ complex_no: no, name, lat: h.lat, lng: h.lng }, false);
    }).catch(() => {});
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  const goTo = useCallback((lat: number, lng: number, lv = 4) => {
    const m = mapRef.current; if (!m) return;
    m.setLevel(lv); m.setCenter(new window.kakao.maps.LatLng(lat, lng));
  }, []);

  // 주소창 = 공유 링크
  useEffect(() => {
    if (!view) return;
    const p = new URLSearchParams({ layer, lat: view.lat.toFixed(5), lng: view.lng.toFixed(5), lv: String(view.level) });
    if (layer === "price" && pm !== "tx") p.set("m", pm);
    if (sel) p.set("cx", sel.complex_no);
    history.replaceState(null, "", "?" + p.toString());
  }, [layer, view, sel, pm]);

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

  // 공유 링크로 들어온 단지 — 한 번만 연다(닫은 뒤 지도가 움직여도 다시 열리지 않게)
  const linkCx = useRef(init.cx);
  useEffect(() => {
    if (!linkCx.current || sel) return;
    const hit = inView.find((c) => c.complex_no === linkCx.current);
    if (hit) { linkCx.current = ""; setSel(hit); }
  }, [inView]);   // eslint-disable-line react-hooks/exhaustive-deps

  // ── 레이어별 지도 표시 ────────────────────────────────
  const selNo = sel?.complex_no;
  useEffect(() => {
    const map = mapRef.current;
    if (!view) return;
    const k = window.kakao;
    let off = false;
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
      // 필터에 맞는 매물이 있는 단지를 전부 올리고(최저가·매물수), 급매가 있는 단지는 빨간 핀으로 강조.
      // 콕집 매물(직접 등록)은 아직 원천이 없어 비어 있다 — 생기면 kokCx 에 합친다.
      const b2 = `swlat=${view.swLat}&swlng=${view.swLng}&nelat=${view.neLat}&nelng=${view.neLng}`;
      const qd = flt.trade === "B2" ? Promise.resolve({ items: [] })
        : getJson(`/stats/quick-deals-map?${b2}&min_discount=${flt.only ? flt.disc : 0.03}&trade_type=${flt.trade}`).catch(() => ({ items: [] }));
      // 특수조건(주인전세·세안고·대출승계): 구(축소 시 시도) 단위로 받아 단지별 건수 → 그 단지만 남기고 핀에 표시
      const regQ = view.level >= 7 ? `sido=${region?.dong.slice(0, 2) || ""}00000000` : `sigungu=${region?.sgg || ""}`;
      const sp = flt.sp && region ? getJson(`/stats/special-deals?kind=${flt.sp}&${regQ}&limit=200`).catch(() => ({ items: [] })) : Promise.resolve(null);
      Promise.all([getJson(`/map/listings?${b2}&${fltQs(flt)}`), qd, sp]).then(([ml, jd, sj]) => {
        if (off) return;
        clear();
        if (ml.too_wide) {
          // 축소 상태: 단지를 격자로 묶은 동그라미(/complexes/cluster). 누르면 그 자리로 3단계 확대.
          setInView([]); setHint("");
          getJson(`/complexes/cluster?${b2}&cols=7&rows=6`).then((cj) => {
            if (off) return;
            for (const c of cj.cells || []) {
              const sz = c.count >= 300 ? " xl" : c.count >= 100 ? " lg" : c.count >= 30 ? " md" : "";
              put(c.lat, c.lng, `<div class="t2-cl${sz}"><b>${c.count.toLocaleString()}</b><span>단지</span></div>`,
                () => map.setLevel(Math.max(3, map.getLevel() - 3), { anchor: new k.maps.LatLng(c.lat, c.lng) }), 1, 0.5);
            }
          }).catch(() => {});
          return;
        }
        const disc = new Map<string, number>();
        for (const d of jd.items || []) disc.set(d.complex_no, Math.min(disc.get(d.complex_no) ?? 0, d.discount));
        const spn = new Map<string, number>();
        for (const d of sj?.items || []) spn.set(d.complex_no, (spn.get(d.complex_no) || 0) + 1);
        let items: (Cx & { n: number; u: number; minp: number | null; minr: number | null; disc?: number; sp?: number })[] = (ml.items || []).map((m: any) => ({
          complex_no: m.complex_no, name: m.name, lat: m.lat, lng: m.lng, households: m.households, listings: m.n,
          n: m.n, u: Math.round(m.units || 0), minp: m.min_price, minr: m.min_rent, disc: disc.get(m.complex_no), sp: spn.get(m.complex_no),
        }));
        if (flt.only) items = items.filter((c) => c.disc);   // 급매만: 급매가 있는 단지만 남긴다
        if (flt.sp) items = items.filter((c) => c.sp);       // 특수조건: 해당 매물이 있는 단지만
        const kokCx: Cx[] = [];
        setInView(items);
        const spl = SPECIAL_KINDS.find((x) => x.k === flt.sp)?.l;
        setHint(items.length ? "" : flt.sp ? `이 범위엔 ${spl} 매물이 있는 단지가 없어요` : flt.only ? "이 범위엔 조건에 맞는 급매 단지가 없어요" : "이 조건에 맞는 매물이 이 범위엔 없어요");
        for (const c of items) {
          const on = c.complex_no === selNo;
          const price = c.minp ? wonShort(c.minp) + (flt.trade === "B2" && c.minr ? `/${Math.round(c.minr / 1e4)}` : "") : "-";
          put(c.lat, c.lng, `<div class="t2-pin lst${c.disc ? " deal" : ""}${c.sp ? " sp" : ""}${on ? " on" : ""}"><b>${esc(shortName(c.name))}</b><i>${price}</i><em>${c.n}건${c.u && c.u < c.n ? `·실${c.u}` : ""}${c.disc ? ` · 급매 ${pct(c.disc, 0)}` : ""}${c.sp ? ` · ${spl} ${c.sp}` : ""}</em></div>`,
            () => pickComplex(c, false), on ? 50 : c.disc || c.sp ? 6 : 5);
        }
        for (const c of kokCx) {
          put(c.lat, c.lng, `<div class="t2-pin kok"><b>${esc(shortName(c.name))}</b><i>콕집</i></div>`, () => pickComplex(c, false), 6);
        }
        if (sel && sel.lat && !items.some((c) => c.complex_no === sel.complex_no)) {
          put(sel.lat, sel.lng, `<div class="t2-pin plain on"><b>${esc(shortName(sel.name))}</b></div>`, undefined, 50);
        }
      }).catch(() => {});
    } else if (layer === "price" && isJibun(pa)) {
      // 빌라·상가·단독: 구 단위 지번 핀(/stats/tx-map, 시군구 필수). 너무 축소하면 핀 폭주라 확대를 안내.
      clear(); setAgg([]); setRhs([]);
      const maxLv = pa === "villa" ? 4 : 5;   // 빌라는 지번이 촘촘해 한 단계 더 확대해야 보인다
      if (view.level > maxLv) { setJpins([]); setHint(`${PASSETS.find((a) => a.k === pa)?.l} 실거래는 지도를 조금 더 확대하면 보여요`); return; }
      if (!region) return;
      setAggLoading(true);
      getJson(`/stats/tx-map?asset=${pa}&trade=A1&sigungu=${region.sgg}&months=${Math.round(pw / 30)}&limit=1500`).then((d) => {
        if (off) return;
        clear(); setAggLoading(false);
        const inb = (d.items || []).filter((p: JPin) => p.lat >= view.swLat && p.lat <= view.neLat && p.lng >= view.swLng && p.lng <= view.neLng);
        setJpins(inb);
        setHint(inb.length ? "" : `${region.sggName} 안 이 범위엔 최근 ${Math.round(pw / 30)}개월 거래가 없어요`);
        for (const p of inb) {
          const on = selJ?.ref === p.ref;
          put(p.lat, p.lng, `<div class="t2-pin jb${on ? " on" : ""}"><b>${esc(shortName(p.name))}</b><i>${wonShort(p.last)}</i><em>${p.n}건${p.built ? ` · ${p.built}년` : ""}</em></div>`,
            () => { setSel(null); setSelJ({ asset: pa as Jibun["asset"], ref: p.ref, name: p.name, sigungu: region.sgg, lat: p.lat, lng: p.lng }); }, on ? 50 : 5);
        }
      }).catch(() => { if (!off) { setJpins([]); setAggLoading(false); } });
    } else if (layer === "price" && pm === "rh") {
      // 신고가: 기간 안 신고가를 찍은 단지(/stats/tx-record-high) + 좌표(/complexes/coords, 60개씩) → 지도 안만
      clear(); setAgg([]); setJpins([]); setAggLoading(true);
      const regQ = view.level >= 8 ? `sido=${region?.dong.slice(0, 2) || ""}00000000` : `sigungu=${region?.sgg || ""}`;
      if (!region) return;
      getJson(`/stats/tx-record-high?days=${pw}&trade=A1&asset=${pa}&${regQ}&order=recent&limit=400`).then(async (d) => {
        // 단지당 한 줄(가장 최근), 평형 수는 n 으로
        const byCx = new Map<string, RH>();
        for (const r of d.items || []) {
          const o = byCx.get(r.complex_no);
          if (o) { o.n += 1; if (r.premium > o.premium) o.premium = r.premium; }
          else byCx.set(r.complex_no, { ...r, n: 1, lat: 0, lng: 0 });
        }
        const ids = [...byCx.keys()];
        const chunks: string[][] = []; for (let i = 0; i < ids.length; i += 60) chunks.push(ids.slice(i, i + 60));
        const cs = await Promise.all(chunks.map((c) => getJson(`/complexes/coords?ids=${c.join(",")}`).catch(() => ({ items: [] }))));
        for (const c of cs) for (const x of c.items || []) { const o = byCx.get(x.complex_no); if (o) { o.lat = x.lat; o.lng = x.lng; } }
        if (off) return;
        clear(); setAggLoading(false);
        const inb = [...byCx.values()].filter((r) => r.lat && r.lat >= view.swLat && r.lat <= view.neLat && r.lng >= view.swLng && r.lng <= view.neLng)
          .sort((a, b) => b.record_date.localeCompare(a.record_date));
        setRhs(inb);
        setHint(inb.length ? "" : `이 범위엔 최근 ${Math.round(pw / 30)}개월 신고가 단지가 없어요`);
        for (const r of inb) {
          const on = r.complex_no === selNo;
          put(r.lat, r.lng, `<div class="t2-pin rh${on ? " on" : ""}"><b>${esc(shortName(r.complex_name))}</b><i>${wonShort(r.record_price)}</i><em>${pct(r.premium, 0)}${r.n > 1 ? ` · ${r.n}평형` : ""}</em></div>`,
            () => pickComplex({ complex_no: r.complex_no, name: r.complex_name, lat: r.lat, lng: r.lng }, false), on ? 50 : 5);
        }
      }).catch(() => { if (!off) { setRhs([]); setAggLoading(false); } });
    } else {
      // 시세분석·중개사랭킹: 동(확대)·구(축소) 버블 — /stats/tx-map/agg. 시세분석은 칩(metric)·기간(window)에 따라
      // 같은 버블에 실거래가 변동률·호가 변동·거래량·갭을 바꿔 칠한다.
      const isPrice = layer === "price";
      setRhs([]); setJpins([]); if (isPrice) setHint("");
      // 시세분석은 단지까지 내려간다(확대 ≤4). 중개사랭킹은 동이 최소 단위.
      const lv = view.level >= 7 ? "gu" : (isPrice && view.level <= 4) ? "cx" : "dong";
      const qs = new URLSearchParams({ level: lv, asset: isPrice ? pa : "apt", trade: "A1",
        metric: isPrice ? pm : "tx", window_days: String(isPrice ? pw : 120),
        sw_lat: String(view.swLat), sw_lng: String(view.swLng), ne_lat: String(view.neLat), ne_lng: String(view.neLng),
        min_n: lv === "gu" ? "8" : lv === "cx" ? "2" : "3" });
      setAggLoading(true);
      getJson(`/stats/tx-map/agg?${qs}`).then((d) => {
        if (off) return;
        clear(); setInView([]);
        const items: Agg[] = d.items || [];
        setAgg(items); setAggMeta({ snapshot: d.snapshot, baseline: d.baseline }); setAggLoading(false);
        for (const a of items) {
          if (isPrice) {
            const b = bubble(pm, a);
            const on = lv === "cx" && a.code === selNo;
            put(a.lat, a.lng, `<div class="t2-bub ${b.cls}${lv === "cx" ? " cx" : ""}${on ? " on" : ""}"><b>${esc(lv === "cx" ? shortName(a.name) : a.name)}</b><span>${b.main}</span><em>${b.sub}</em></div>`,
              () => {
                if (lv === "cx") pickComplex({ complex_no: a.code, name: a.name, lat: a.lat, lng: a.lng }, false);
                else map.setLevel(lv === "gu" ? 6 : 4, { anchor: new k.maps.LatLng(a.lat, a.lng) });
              }, on ? 50 : 1, 0.5);
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
  }, [layer, view, selNo, selJ?.ref, rkDong, region?.dong, region?.sgg, pickComplex, pm, pw, pa, flt]);   // eslint-disable-line react-hooks/exhaustive-deps

  // 레이어·유형을 바꾸면 지번 서랍은 닫는다
  useEffect(() => { setSelJ(null); }, [layer, pa]);
  useEffect(() => { if (!isJibun(pa) && pm !== "rh") setHint((h) => (h.includes("실거래는") || h.includes("신고가") ? "" : h)); }, [pa, pm]);

  // 단지를 열면 그 단지의 가까운 역(1.5km·3곳)과 배정 초등학교·학구 경계를 지도에 같이 그린다. 닫으면 지운다.
  const cxOvs = useRef<any[]>([]);
  useEffect(() => {
    const map = mapRef.current, k = window.kakao;
    cxOvs.current.forEach((o) => o.setMap(null)); cxOvs.current = [];
    if (!selNo || !map || !k) return;
    let off = false;
    const add = (o: any) => { o.setMap(map); cxOvs.current.push(o); };
    const put = (lat: number, lng: number, html: string) => {
      const el = document.createElement("div"); el.innerHTML = html;
      add(new k.maps.CustomOverlay({ position: new k.maps.LatLng(lat, lng), content: el, yAnchor: 0.5, zIndex: 3 }));
    };
    getJson(`/complex/${selNo}/subway-nearby?radius_km=1.5&limit=3`).then((j) => {
      if (off) return;
      for (const s of j.items || []) put(s.lat, s.lng, `<div class="t2-poi st"><b>${esc(s.station)}</b><span>${esc(String(s.lines || "").split("·")[0])} · 도보 ${s.walk_min}분</span></div>`);
    }).catch(() => {});
    getJson(`/complex/${selNo}/school-map`).then((j) => {
      if (off) return;
      for (const z of j.zones || []) {
        // GeoJSON 폴리곤(링 목록) 또는 링 하나 — 바깥 링만 그린다
        const ring: number[][] = typeof z?.[0]?.[0] === "number" ? z : z?.[0];
        if (!ring?.length) continue;
        add(new k.maps.Polygon({ path: ring.map(([lng, lat]: number[]) => new k.maps.LatLng(lat, lng)),
          strokeWeight: 2, strokeColor: "#1f9d63", strokeOpacity: 0.8, strokeStyle: "shortdash", fillColor: "#1f9d63", fillOpacity: 0.07, zIndex: 0 }));
      }
      for (const sc of j.assigned || []) put(sc.lat, sc.lng, `<div class="t2-poi sc"><b>${esc(String(sc.name).replace("등학교", ""))}</b><span>${j.src === "near" ? "인근" : "배정"} · 도보 ${sc.walk_min}분</span></div>`);
    }).catch(() => {});
    return () => { off = true; };
  }, [selNo]);

  useEffect(() => { if (layer !== "deals") setHint(""); }, [layer]);

  useEffect(() => { setRkDong(null); }, [region?.sgg]);

  // ── 화면 ─────────────────────────────────────────
  const panel = (
    <>
      {layer === "deals" && <DealsPanel region={region} inView={inView} onPick={pickComplex} zoomedOut={!!hint && inView.length === 0} />}
      {layer === "price" && isJibun(pa) && <JibunPanel asset={pa} pins={jpins} region={region} win={pw} onWin={setPw} loading={aggLoading} zoomedOut={(view?.level ?? 5) > (pa === "villa" ? 4 : 5)}
        onPick={(p) => { setSel(null); setSelJ({ asset: pa as Jibun["asset"], ref: p.ref, name: p.name, sigungu: region?.sgg || "", lat: p.lat, lng: p.lng }); goTo(p.lat, p.lng, 3); }} />}
      {layer === "price" && !isJibun(pa) && pm === "rh" && <RecordHighPanel rows={rhs} region={region} win={pw} onWin={setPw} loading={aggLoading} onMetric={setPm} onPick={pickComplex} />}
      {layer === "price" && !isJibun(pa) && pm !== "rh" && <PricePanel region={region} agg={agg} level={view?.level ?? 5} metric={pm} onMetric={setPm}
        win={pw} onWin={setPw} loading={aggLoading} meta={aggMeta} onPick={pickComplex} />}
      {layer === "realtor" && <RealtorPanel region={region} dong={rkDong} />}
    </>
  );

  return (
    <div className={"t2" + (phone ? " phone" : " desk")}>
      <TopBar phone={phone} favs={favs} session={!!session} onGo={goComplex} onAddr={(lat, lng) => goTo(lat, lng, 4)} onLogin={() => setAskLogin(true)} onPick={(c) => {
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
          {/* 레이어 탭 + 그 레이어의 필터가 한 줄로 이어진다(폰은 두 줄) */}
          <div className={"t2-maptop" + (!phone && (sel || selJ) ? " narrow" : "")}>
            <div className="t2-layers" role="tablist">
              {LAYERS.map((l) => (
                <button key={l.key} role="tab" aria-selected={layer === l.key} className={layer === l.key ? "on" : ""}
                  onClick={() => { setLayer(l.key); setSel(null); }}>{l.label}</button>
              ))}
            </div>
            {layer === "deals" && <DealFilterBar flt={flt} onChange={setFlt} />}
            {layer === "price" && (
              <div className="t2-fbar price">
                <div className="t2-fseg">
                  {PASSETS.map((a) => <button key={a.k} className={pa === a.k ? "on" : ""} onClick={() => setPa(a.k)}>{a.l}</button>)}
                </div>
                {!isJibun(pa) && (
                  <div className="t2-fseg t2-period">
                    {METRICS.map((c) => <button key={c.k} className={pm === c.k ? "on" : ""} onClick={() => setPm(c.k)}>{c.l}</button>)}
                  </div>
                )}
                {(pm !== "hoga" || isJibun(pa)) && (
                  <div className="t2-fseg t2-period">
                    {PRICE_WINDOWS.map((w) => <button key={w.d} className={pw === w.d ? "on" : ""} onClick={() => setPw(w.d)}>{w.l}</button>)}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className={"t2-zoom" + (!phone && (sel || selJ) ? " narrow" : "")}>
            <button onClick={() => mapRef.current?.setLevel(mapRef.current.getLevel() - 1)} aria-label="확대">+</button>
            <button onClick={() => mapRef.current?.setLevel(mapRef.current.getLevel() + 1)} aria-label="축소">−</button>
          </div>
          {!phone && <a className={"t2-fab" + (sel || selJ ? " narrow" : "")} href={`${SITE}/request`} target="_blank" rel="noreferrer">콕집에 요청하기</a>}
          {!phone && sel && <aside className="t2-drawer"><ComplexDrawer cx={sel} initialTab={drawerTab} onClose={() => setSel(null)} onPick={(c) => pickComplex(c, true)}
            fav={favs ? favs.some((f) => f.complex_no === sel.complex_no) : null} onFav={() => toggleFav(sel)} /></aside>}
          {!phone && !sel && selJ && <aside className="t2-drawer"><JibunDrawer j={selJ} months={Math.round(pw / 30)} onClose={() => setSelJ(null)} /></aside>}
          {askLogin && (
            <div className="t2-modal" role="dialog" aria-modal="true" onClick={() => setAskLogin(false)}>
              <div className="t2-modal-in sm" onClick={(e) => e.stopPropagation()}>
                <div className="t2-ph"><h2>로그인</h2><button className="t2-x" onClick={() => setAskLogin(false)} aria-label="닫기">×</button></div>
                <LoginBox why="관심단지는 로그인한 계정에 저장돼요(최대 20곳). 콕집 계정 그대로 쓰세요." />
              </div>
            </div>
          )}
          {phone && (
            <section className={"t2-sheet " + sheet}>
              <button className="t2-grab" aria-label="목록 크기 바꾸기"
                onClick={() => setSheet(sheet === "peek" ? "half" : sheet === "half" ? "full" : "peek")}><i /></button>
              <div className="t2-sheet-in">
                {sel ? <ComplexDrawer cx={sel} initialTab={drawerTab} onClose={() => setSel(null)} onPick={(c) => pickComplex(c, true)}
                  fav={favs ? favs.some((f) => f.complex_no === sel.complex_no) : null} onFav={() => toggleFav(sel)} />
                  : selJ ? <JibunDrawer j={selJ} months={Math.round(pw / 30)} onClose={() => setSelJ(null)} /> : panel}
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
              {favs && favs.length > 0 && favs.map((f) => <button key={f.complex_no} onClick={() => goComplex(f.complex_no, f.complex_name)}>관심단지 · {f.complex_name}</button>)}
              {!session && <button onClick={() => setAskLogin(true)}>로그인 · 관심단지</button>}
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
function TopBar({ phone, onPick, favs, session, onGo, onAddr, onLogin }: { phone: boolean; onPick: (c: Cx) => void; favs: { complex_no: string; complex_name: string }[] | null;
  session: boolean; onGo: (no: string, name: string) => void; onAddr: (lat: number, lng: number) => void; onLogin: () => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const [tools, setTools] = useState(false);
  const [favOpen, setFavOpen] = useState(false);
  const [addrErr, setAddrErr] = useState("");
  // 주소·장소: 카카오 지오코더(주소 → 실패 시 장소 키워드). 단지 이름 결과 아래에 한 줄로 붙는다.
  const goAddr = async () => {
    const kw = q.trim(); if (!kw) return;
    const pos = await geocodeRegion(kw);
    if (!pos) { setAddrErr(`'${kw}' 주소나 장소를 찾지 못했어요`); setTimeout(() => setAddrErr(""), 2500); return; }
    setQ(""); setHits([]); onAddr(pos.lat, pos.lng);
  };
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
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="단지 이름 · 주소 · 역 이름으로 찾기" aria-label="단지·주소 검색"
          onKeyDown={(e) => { if (e.key === "Enter") { if (hits.length) choose(hits[0]); else goAddr(); } if (e.key === "Escape") { setQ(""); setHits([]); } }} />
        {(hits.length > 0 || q.trim().length >= 2) && (
          <ul className="t2-hits">
            {hits.map((h) => (
              <li key={h.complex_no}><button onClick={() => choose(h)}><b>{h.complex_name}</b><span>{h.region} · {h.type_name}</span></button></li>
            ))}
            {q.trim().length >= 2 && <li className="addr"><button onClick={goAddr}><b>'{q.trim()}' 주소·장소로 지도 이동</b><span>{addrErr || "도로명·지번 주소, 역·학교·건물 이름"}</span></button></li>}
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
          <span className="t2-dd" onMouseLeave={() => setFavOpen(false)}>
            <button className={"t2-favbtn" + (favs?.length ? " has" : "")} onClick={() => setFavOpen(!favOpen)} aria-expanded={favOpen}>관심단지{favs?.length ? ` ${favs.length}` : ""}</button>
            {favOpen && (
              <span className="t2-ddm favs">
                {!session ? <button onClick={() => { setFavOpen(false); onLogin(); }}>로그인하고 관심단지 담기</button>
                  : !favs?.length ? <span className="t2-ddm-note">단지 서랍의 하트를 누르면 여기에 모여요(최대 20곳)</span>
                  : favs.map((f) => <button key={f.complex_no} onClick={() => { setFavOpen(false); onGo(f.complex_no, f.complex_name); }}>{f.complex_name}</button>)}
                {session && <a href={`${SITE}/my/favorites`} target="_blank" rel="noreferrer">관심단지 대시보드 ↗</a>}
              </span>
            )}
          </span>
          <a className="lounge" href={`${SITE}/lounge`} target="_blank" rel="noreferrer">중개사라운지</a>
        </nav>
      )}
    </header>
  );
}

// ── 매물찾기 필터 바(지도 위) ────────────────────────
// 유형 드롭다운 이름: 전부면 '전체', 둘까지는 이름 나열, 그 이상은 '아파트 외 2'
function typeLabel(ts: string[]) {
  const ls = CX_TYPES.filter((t) => ts.includes(t.k)).map((t) => t.l);
  if (ls.length === CX_TYPES.length) return "유형 전체";
  return ls.length <= 2 ? ls.join("·") : `${ls[0]} 외 ${ls.length - 1}`;
}

function DealFilterBar({ flt, onChange }: { flt: Flt; onChange: (f: Flt) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const set = (patch: Partial<Flt>) => onChange({ ...flt, ...patch });
  const toggleType = (k: string) => {
    const has = flt.types.includes(k);
    if (has && flt.types.length === 1) return;          // 하나는 남긴다
    set({ types: has ? flt.types.filter((t) => t !== k) : [...flt.types, k] });
  };
  const pick = (opts: { l: string; a: number; b: number }[], a: number, b: number) => opts.find((o) => o.a === a && o.b === b)?.l;
  const priceL = pick(PRICE_OPTS, flt.pmin, flt.pmax);
  const areaL = pick(AREA_OPTS, flt.amin, flt.amax);
  const apprL = pick(APPROVE_OPTS, flt.afrom, flt.ato);
  const hhL = pick(HH_OPTS, flt.hmin, flt.hmax);
  const dirty = JSON.stringify(flt) !== JSON.stringify(FLT0);
  const opt = (o: { l: string }, on: boolean, f: () => void) => <button key={o.l} className={on ? "on" : ""} onClick={f}>{o.l}</button>;
  return (
    <div className="t2-fbar" onMouseLeave={() => setOpen(null)}>
      <Dd id="types" open={open} setOpen={setOpen} label={typeLabel(flt.types)} active={flt.types.join() !== FLT0.types.join()}>
        <span className="t2-ddm-in" onClick={(e) => e.stopPropagation()}>
          {CX_TYPES.map((t) => (
            <button key={t.k} className={flt.types.includes(t.k) ? "on chk" : "chk"} onClick={() => toggleType(t.k)}><i />{t.l}</button>
          ))}
        </span>
      </Dd>
      <Dd id="trade" open={open} setOpen={setOpen} label={TRADES.find((t) => t.k === flt.trade)!.l} active>
        {TRADES.map((t) => opt(t, flt.trade === t.k, () => set({ trade: t.k })))}
      </Dd>
      <Dd id="price" open={open} setOpen={setOpen} label={priceL && priceL !== "전체" ? priceL : (flt.trade === "A1" ? "가격대" : "보증금")} active={!!flt.pmin || !!flt.pmax}>
        {PRICE_OPTS.map((o) => opt(o, flt.pmin === o.a && flt.pmax === o.b, () => set({ pmin: o.a, pmax: o.b })))}
      </Dd>
      <Dd id="area" open={open} setOpen={setOpen} label={areaL && areaL !== "전체" ? areaL.split(" ")[0] : "면적"} active={!!flt.amin || !!flt.amax}>
        {AREA_OPTS.map((o) => opt(o, flt.amin === o.a && flt.amax === o.b, () => set({ amin: o.a, amax: o.b })))}
      </Dd>
      <Dd id="appr" open={open} setOpen={setOpen} label={apprL && apprL !== "전체" ? apprL : "사용승인일"} active={!!flt.afrom || !!flt.ato}>
        {APPROVE_OPTS.map((o) => opt(o, flt.afrom === o.a && flt.ato === o.b, () => set({ afrom: o.a, ato: o.b })))}
      </Dd>
      <Dd id="hh" open={open} setOpen={setOpen} label={hhL && hhL !== "전체" ? hhL : "세대수"} active={!!flt.hmin || !!flt.hmax}>
        {HH_OPTS.map((o) => opt(o, flt.hmin === o.a && flt.hmax === o.b, () => set({ hmin: o.a, hmax: o.b })))}
      </Dd>
      <button className={"t2-ftog" + (flt.only ? " on" : "")} onClick={() => set({ only: !flt.only })}>급매만</button>
      {flt.trade === "A1" && (
        <Dd id="sp" open={open} setOpen={setOpen} label={SPECIAL_KINDS.find((x) => x.k === flt.sp)?.l || "특수조건"} active={!!flt.sp}>
          {opt({ l: "전체" }, !flt.sp, () => set({ sp: "" }))}
          {SPECIAL_KINDS.map((x) => opt({ l: `${x.l} — ${x.h}` }, flt.sp === x.k, () => set({ sp: x.k })))}
        </Dd>
      )}
      {flt.only && (
        <Dd id="disc" open={open} setOpen={setOpen} label={`${Math.round(flt.disc * 100)}% 이상`} active={flt.disc > 0.03}>
          {[0.03, 0.05, 0.1].map((v) => opt({ l: `${Math.round(v * 100)}% 이상` }, flt.disc === v, () => set({ disc: v })))}
        </Dd>
      )}
      {dirty && <button className="t2-freset" onClick={() => onChange(FLT0)}>초기화</button>}
    </div>
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
  { k: "rh", l: "신고가", h: "신고가 단지" },
];

// ── 시세분석 · 신고가 단지 목록(지도 안) ─────────────────────
function RecordHighPanel({ rows, region, win, onWin, loading, onMetric, onPick }: { rows: RH[]; region: Region | null; win: number; onWin: (d: number) => void; loading: boolean;
  onMetric: (m: PriceMetric) => void; onPick: (c: Cx) => void }) {
  const [sort, setSort] = useState<"recent" | "premium" | "price">("recent");
  const xs = useMemo(() => [...rows].sort(sort === "premium" ? (a, b) => b.premium - a.premium : sort === "price" ? (a, b) => b.record_price - a.record_price
    : (a, b) => b.record_date.localeCompare(a.record_date)), [rows, sort]);
  return (
    <div className="t2-pad">
      <div className="t2-chips">
        {METRICS.map((c) => <button key={c.k} className={c.k === "rh" ? "on" : ""} onClick={() => onMetric(c.k)}>{c.l}</button>)}
      </div>
      <div className="t2-ph">
        <h2>신고가 단지 <small>지도 안 {rows.length}</small></h2>
        <div className="t2-chips sm t2-period" role="radiogroup" aria-label="기간">
          {PRICE_WINDOWS.map((w) => <button key={w.d} role="radio" aria-checked={win === w.d} className={win === w.d ? "on" : ""} onClick={() => onWin(w.d)}>{w.l}</button>)}
        </div>
      </div>
      <p className="t2-note">최근 {win}일 안에 같은 평형의 이전 최고가를 넘긴 매매(중개거래). 해제 거래 제외. 숫자는 이전 최고가 대비 상승률.</p>
      <div className="t2-chips sm">
        {([["recent", "최근순"], ["premium", "상승률순"], ["price", "가격순"]] as const).map(([k, l]) => <button key={k} className={sort === k ? "on" : ""} onClick={() => setSort(k)}>{l}</button>)}
      </div>
      {loading && rows.length === 0 ? <Skel /> : xs.length === 0 ? <div className="t2-empty">이 범위엔 신고가 단지가 없어요. 지도를 옮기거나 기간을 늘려 보세요.</div> : (
        <ul className="t2-list">
          {xs.map((r) => (
            <li key={r.complex_no}>
              <button onClick={() => onPick({ complex_no: r.complex_no, name: r.complex_name, lat: r.lat, lng: r.lng })}>
                <span className="nm"><b>{r.complex_name}</b><em>{areaLabel(r.area_key)} · {r.floor}층 · {r.record_date.slice(2).replace(/-/g, ".")}{r.n > 1 ? ` · ${r.n}평형` : ""}</em></span>
                <span className="pr"><b>{wonShort(r.record_price)}</b><em>이전 {r.prev_high ? wonShort(r.prev_high) : "-"}</em></span>
                <span className="dc up">{pct(r.premium)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <a className="t2-stat-link" href={`${SITE}/tx-stats/record-high`} target="_blank" rel="noreferrer">{region ? `${region.sggName} ` : ""}신고가 통계 전체 보기 ↗</a>
    </div>
  );
}

// ── 시세분석 · 빌라/상가/단독 지번 목록(지도 안) ─────────────────────
const JB_NAME: Record<string, string> = { villa: "빌라", nrg: "상가", house: "단독·다가구" };
function JibunPanel({ asset, pins, region, win, onWin, loading, zoomedOut, onPick }: { asset: PAsset; pins: JPin[]; region: Region | null; win: number; onWin: (d: number) => void;
  loading: boolean; zoomedOut: boolean; onPick: (p: JPin) => void }) {
  const [sort, setSort] = useState<"recent" | "n" | "price">("recent");
  const xs = useMemo(() => [...pins].sort(sort === "n" ? (a, b) => b.n - a.n : sort === "price" ? (a, b) => b.last - a.last : (a, b) => b.latest.localeCompare(a.latest)).slice(0, 80), [pins, sort]);
  return (
    <div className="t2-pad">
      <div className="t2-ph">
        <h2>{JB_NAME[asset]} 실거래 <small>지도 안 {pins.length}</small></h2>
        <div className="t2-chips sm t2-period" role="radiogroup" aria-label="기간">
          {PRICE_WINDOWS.map((w) => <button key={w.d} role="radio" aria-checked={win === w.d} className={win === w.d ? "on" : ""} onClick={() => onWin(w.d)}>{w.l}</button>)}
        </div>
      </div>
      <p className="t2-note">{region?.sggName ? `${region.sggName} ` : ""}국토부 매매 실거래를 지번 단위로 묶었어요. {asset === "nrg" ? "상가·사무실은 매매만(임대 실거래 원천이 없음)." : asset === "house" ? "단독·다가구는 임대 실거래에 지번이 없어 매매만." : "핀을 누르면 건축물대장과 거래 내역이 열려요."}</p>
      {zoomedOut ? <div className="t2-empty">지도를 조금 더 확대하면 지번 핀이 보여요(동 단위).</div>
        : loading && pins.length === 0 ? <Skel /> : xs.length === 0 ? <div className="t2-empty">이 범위엔 최근 {Math.round(win / 30)}개월 거래가 없어요.</div> : (
        <>
          <div className="t2-chips sm">
            {([["recent", "최근순"], ["n", "거래 많은 순"], ["price", "가격순"]] as const).map(([k, l]) => <button key={k} className={sort === k ? "on" : ""} onClick={() => setSort(k)}>{l}</button>)}
          </div>
          <ul className="t2-list">
            {xs.map((p) => (
              <li key={p.ref}>
                <button onClick={() => onPick(p)}>
                  <span className="nm"><b>{p.name}</b><em>{p.n}건 · 최근 {p.latest.slice(2).replace(/-/g, ".")}{p.built ? ` · ${p.built}년` : ""}</em></span>
                  <span className="pr"><b>{wonShort(p.last)}</b><em>평균 {wonShort(p.avg)}{p.ppy ? ` · ${Math.round(p.ppy / 1e4).toLocaleString()}만/평` : ""}</em></span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <a className="t2-stat-link" href={`${SITE}/tx-map`} target="_blank" rel="noreferrer">실거래 지도 전체 보기 ↗</a>
    </div>
  );
}

function PricePanel({ region, agg, level, metric, onMetric, win, onWin, loading, meta, onPick }: {
  region: Region | null; agg: Agg[]; level: number; metric: PriceMetric; onMetric: (m: PriceMetric) => void;
  win: number; onWin: (d: number) => void; loading: boolean; meta: { snapshot?: string; baseline?: string }; onPick: (c: Cx) => void;
}) {
  const isCx = level <= 4;
  const unit = level >= 7 ? "구별" : isCx ? "단지별" : "동별";
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
      {isCx && <p className="t2-note">단지 단위(최소 단위). 거래 2건 이상인 단지만 — 더 보려면 지도를 조금 넓혀 동·구 단위로.</p>}
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
              <li key={a.code} className={isCx ? "t2-click" : ""} onClick={isCx ? () => onPick({ complex_no: a.code, name: a.name, lat: a.lat, lng: a.lng }) : undefined}
                title={isCx ? "단지 열기" : undefined}>
                <span className="nm">{isCx ? shortName(a.name) : a.name}</span>
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
